"""Panel Posting Gagal — daftar dokumen dengan jurnal gagal + ulang posting.

PK-18 (GL-02, IV-04) — jenis dokumen, saringan, nomor, nominal, dan jalur ulang dibaca dari SATU registri
`services/posting_registry.py` (`KINDS`); router ini tidak lagi menulis cara ulang per jenis. Ulang posting memakai
jalur idempotent masing-masing jenis (tidak menggandakan jurnal). Daftar berhalaman dari server; `counts`/`total` dari
`count_documents` atas semua jenis, bukan dari daftar yang dipotong (`02_STANDAR.md` D4).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from db import db
from dependencies import require_permission, audit
from pagination import build_search
from entity_scope import entity_ctx, resolve_scope_ids
from services import posting_registry as reg

router = APIRouter(prefix="/api")

#: Ukuran halaman daftar (bawaan dan batas atas). Batas teknis tampilan, bukan aturan bisnis.
PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 200

# Nama lama tetap ada untuk pembaca lain (dibentuk dari registri).
SOURCES = {k: (v["collection"], v["failed_query"], v["entity_field"], v["number_field"])
           for k, v in reg.KINDS.items()}
LABELS = reg.LABELS


def _query(kind: str, scope: List[str], extra: Optional[Dict[str, Any]] = None, q: str = "") -> Dict[str, Any]:
    spec = reg.KINDS[kind]
    base = {**spec["failed_query"], **(extra or {}), spec["entity_field"]: {"$in": scope}}
    cari = build_search(q, [spec["number_field"]])   # kotak cari panel: nomor dokumen
    return {"$and": [base, cari]} if cari else base


async def _count(kind: str, scope: List[str], q: str = "") -> int:
    coll = db[reg.KINDS[kind]["collection"]]
    if reg.KINDS[kind].get("per_step"):   # satu baris per langkah gagal, bukan per dokumen
        res = await coll.aggregate(reg.count_pipeline(kind, _query(kind, scope, q=q))).to_list(1)
        return int(res[0]["n"]) if res else 0
    return await coll.count_documents(_query(kind, scope, q=q))


async def _top(kind: str, scope: List[str], n: int, q: str = "") -> List[Dict[str, Any]]:
    cur = db[reg.KINDS[kind]["collection"]].find(_query(kind, scope, q=q), {"_id": 0}).sort(reg.sort_spec(kind))
    return await cur.limit(n).to_list(n)


@router.get("/finance/posting-failures")
async def list_posting_failures(request: Request, kind: str = Query(""), page: int = Query(1, ge=1),
                                page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
                                q: str = Query("", max_length=100)) -> Dict[str, Any]:
    await require_permission(request, "accounting", "view")
    if kind and kind not in reg.KINDS:
        raise HTTPException(status_code=400, detail="Jenis dokumen tidak dikenal")
    scope = resolve_scope_ids(await entity_ctx(request))
    counts = {k: await _count(k, scope, q) for k in reg.KINDS}
    start = (page - 1) * page_size
    # Cukup ambil `start + page_size` dokumen teratas tiap jenis (urutan kueri = urutan gabung; satu dokumen bisa
    # berbaris banyak, jadi baris yang terambil tidak pernah kurang dari yang dibutuhkan halaman ini).
    gabung = [(k, d) for k in ([kind] if kind else reg.KINDS) if counts[k]
              for d in await _top(k, scope, start + page_size, q)]
    gabung.sort(key=lambda kd: reg.sort_key(*kd), reverse=True)
    rows = [r for k, d in gabung for r in reg.rows_of(k, d)][start:start + page_size]
    total = counts[kind] if kind else sum(counts.values())
    return {"items": rows, "total": total, "counts": counts, "labels": reg.LABELS, "page": page,
            "page_size": page_size}


@router.post("/finance/posting-failures/{kind}/{doc_id}/retry")
async def retry_posting_failure(kind: str, doc_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "accounting", "manage")
    if kind not in reg.KINDS:
        raise HTTPException(status_code=400, detail="Jenis dokumen tidak dikenal")
    spec = reg.KINDS[kind]
    scope = resolve_scope_ids(await entity_ctx(request))
    doc = await db[spec["collection"]].find_one(_query(kind, scope, reg.lookup(kind, doc_id)), {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen gagal posting tidak ditemukan (atau sudah terposting)")
    try:
        await spec["retry"]({**doc, "_baris": doc_id}, actor)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=409, detail=f"Posting masih gagal: {exc}")
    await audit(actor["name"], "posting_failure_retried", kind, doc_id, {})
    fresh = await db[spec["collection"]].find_one({"id": doc["id"]}, {"_id": 0}) or {}
    return {"kind": kind, "id": doc_id, **reg.status_of(kind, fresh, doc_id)}


@router.get("/finance/posting-failures/count")
async def count_posting_failures(request: Request) -> Dict[str, Any]:
    """Lencana menu Keuangan — jumlah dokumen dengan jurnal gagal (terbatas entitas pengguna)."""
    await require_permission(request, "accounting", "view")
    scope = resolve_scope_ids(await entity_ctx(request))
    counts = {k: await _count(k, scope) for k in reg.KINDS}
    return {"total": sum(counts.values()), "counts": counts}
