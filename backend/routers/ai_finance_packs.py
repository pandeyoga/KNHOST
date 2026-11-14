"""AG-T4 — paket tutup buku bulanan Asisten Keuangan (Tanya KN › Laporan › Keuangan).

    POST /api/ai/finance/closing-pack                {period: "YYYY-MM"} → dokumen `ai_finance_packs`
         ?stream=1 → event `progress` per lembar ("Menyusun paket… (i dari 12)") lalu `done` {pack} (SSE)
    GET  /api/ai/finance/closing-pack/{id}           → dokumen + `results` (hanya pembuatnya)
    GET  /api/ai/finance/closing-pack/{id}/export.xlsx → `tutup-buku-{kode PT}-{period}.xlsx`, 12 lembar

Gerbang = Asisten Keuangan (`ai_finance.view` + sakelar akun, AG-T2) lalu `ai.view`. Angka dibaca lewat pintu baca-saja
`SelfApi` dengan sesi & PT permintaan ini (`services/ai_finance_reports.py`); bagian tanpa izin endpoint = "Tidak
disertakan". Mode "Semua PT" ditolak 409: paket dibuat per PT (N3).
"""
import json
import logging
import re
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request

from db import db
from dependencies import require_permission
from entity_scope import entity_ctx
from routers.ai_analytics import _DENY_AI, _fill_sheet, _finance_user, _owned_results, _xlsx_response
from services import ai_finance_reports as afr

router = APIRouter(prefix="/api/ai")
logger = logging.getLogger(__name__)
_EXPIRED = "Isi lembar ini sudah tidak tersimpan (hasil disimpan 30 hari). Buat paket baru."


async def _gate(request: Request) -> Dict[str, Any]:
    """Asisten Keuangan dulu (pesan Z6 / sakelar akun), lalu `ai.view` — urutan yang sama dengan mode Keuangan."""
    await _finance_user(request)
    return await require_permission(request, "ai", "view", detail=_DENY_AI)


@router.post("/finance/closing-pack")
async def create_closing_pack(payload: Dict[str, Any], request: Request, stream: bool = Query(False)):
    user = await _gate(request)
    ctx = await entity_ctx(request)
    if getattr(ctx, "view_all", False) or (request.headers.get("X-Entity-Id") or "").strip().lower() == "all":
        raise HTTPException(status_code=409, detail=afr.COMBINED_MESSAGE)
    period = str((payload or {}).get("period") or "").strip()
    try:
        afr.check_period(period)
    except afr.PackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from core_utils import entity_code
    from entity_scope import scope_meta
    from services.ai_self_api import SelfApi
    eid = ctx.active_entity_id
    meta = await scope_meta(ctx)
    kw = {"user": user, "entity_id": eid, "period": period, "entity_label": meta.get("label") or "",
          "entity_code": await entity_code(eid)}
    api = SelfApi.from_request(request)

    async def _store(pack: Dict[str, Any]) -> Dict[str, Any]:
        await db.ai_finance_packs.insert_one(dict(pack))
        pack.pop("_id", None)
        return pack

    if not stream:
        try:
            return await _store(await afr.build_closing_pack(api, **kw))
        except Exception as exc:  # noqa: BLE001 — galat tak terduga → kalimat baku, rincian di log
            logger.exception("paket tutup buku gagal")
            raise HTTPException(status_code=500, detail=afr.FAILED_MESSAGE) from exc
        finally:
            await api.aclose()

    from fastapi.responses import StreamingResponse

    async def gen():
        try:
            async for ev in afr.iter_closing_pack(api, **kw):
                if ev["type"] == "done":
                    ev = {"type": "done", "pack": await _store(ev["pack"])}
                yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
        except Exception:  # noqa: BLE001 — galat dikirim sebagai event, bukan koneksi putus
            logger.exception("paket tutup buku gagal")
            yield f"data: {json.dumps({'type': 'done', 'error': afr.FAILED_MESSAGE}, ensure_ascii=False)}\n\n"
        finally:
            await api.aclose()
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _own_pack(pack_id: str, request: Request) -> Dict[str, Any]:
    """Hanya pembuatnya (`user_id`); milik orang lain = 404 (tidak membocorkan keberadaannya)."""
    user = await require_permission(request, "ai", "view", detail=_DENY_AI)
    doc = await db.ai_finance_packs.find_one({"id": pack_id, "user_id": user["id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Paket tidak ditemukan.")
    return {**doc, "_user": user}


@router.get("/finance/closing-pack/{pack_id}")
async def get_closing_pack(pack_id: str, request: Request) -> Dict[str, Any]:
    doc = await _own_pack(pack_id, request)
    user = doc.pop("_user")
    ids = [s["result_id"] for s in doc.get("sections") or [] if s.get("result_id")]
    doc["results"] = {r["result_id"]: r for r in await _owned_results(ids, user, all_users=False)}
    return doc


@router.get("/finance/closing-pack/{pack_id}/export.xlsx")
async def export_closing_pack(pack_id: str, request: Request):
    from openpyxl import Workbook
    doc = await _own_pack(pack_id, request)
    user = doc.pop("_user")
    ids = [s["result_id"] for s in doc.get("sections") or [] if s.get("result_id")]
    results = {r["result_id"]: r for r in await _owned_results(ids, user, all_users=False)}
    wb = Workbook()
    wb.remove(wb.active)
    pt, bulan = doc.get("entity_label") or "", doc.get("period_label") or doc.get("period") or ""
    for sec in doc.get("sections") or []:
        ws = wb.create_sheet(re.sub(r"[\\/*?:\[\]]", " ", sec["title"])[:31])
        res = results.get(sec.get("result_id") or "")
        head = (f"Paket tutup buku · {pt} · {bulan}" if sec["key"] == "ringkasan"
                else f"{sec['title']} · {pt} · {bulan}")
        if res is None:
            _fill_sheet(ws, {"columns": [], "rows": [], "period": {"label": bulan}}, heading=head,
                        notes=[sec.get("note") or _EXPIRED] if sec.get("status") != "ok" else [_EXPIRED])
            continue
        _fill_sheet(ws, res, heading=head, notes=list(res.get("notes") or []))   # sel teks diamankan (`_safe_cell`)
    code = re.sub(r"[^\w-]+", "-", str(doc.get("entity_code") or "PT")).strip("-") or "PT"
    return _xlsx_response(wb, f"tutup-buku-{code}-{doc.get('period')}")
