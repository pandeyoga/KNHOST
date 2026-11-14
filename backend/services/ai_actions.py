"""Tanya KN — draf tindakan dari jawaban AI. Tidak ada yang tersimpan/terkirim sebelum pengguna menekan Setujui.

Jenis: `draft_po` (PO ke supplier), `collection_followup` (pengingat tagih ke sales),
`customer_followup` (daftar follow-up pelanggan tidak aktif ke sales).

AG-T1 (AG-01, AG-02) — status kartu hanya maju: `pending → running → confirmed | failed`, `pending → dismissed | expired`;
tidak pernah kembali ke `pending`. Kartu berlaku `ai.kartu_masa_berlaku_jam` (per PT kartu) dan hanya bisa disetujui
saat PT aktif = PT kartu. Pemeriksaan izin & isian dijalankan SEBELUM klaim; hasil (nomor PO / pengingat) disimpan
bertahap, sehingga kartu yang gagal di tengah mencatat yang sudah jadi dan tidak bisa diulang.
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso
from dependencies import audit, denied, has_permission
from services import analytics_engine as engine
from services.analytics_time import now_wib
from services.config_resolver import value_of

TYPES = ("draft_po", "collection_followup", "customer_followup")
MAX_LINES = 30
#: Batas teknis (bukan aturan bisnis): kartu `running` yang tidak berubah selama ini dianggap prosesnya mati.
RUNNING_STALE_MINUTES = 10
KUNCI_MASA_BERLAKU = "ai.kartu_masa_berlaku_jam"
MSG_SEMUA_PT = "Pilih satu PT dulu. Tindakan tidak bisa disiapkan dalam mode Semua PT."
MSG_KEDALUWARSA = "Draf ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi."
MSG_SUDAH_DIPROSES = "Draf ini sudah diproses"
MSG_TANPA_AKSES_PT = "Anda tidak lagi punya akses ke PT draf ini."
MSG_PROSES_MATI = "Proses berhenti sebelum selesai. Periksa daftar PO sebelum meminta draf baru."
#: AG-T3 — kartu golongan A/B (`services/ai_cards.py`) yang prosesnya mati: hasilnya tidak pasti.
MSG_PROSES_MATI_KARTU = "Proses berhenti sebelum selesai. Periksa dokumennya sebelum meminta kartu baru."


async def _warehouse(entity_id: str) -> Dict[str, Any]:
    from services import warehouse_scope_service as whscope
    async for wh in db.warehouses.find({"active": {"$ne": False}}, {"_id": 0, "id": 1, "name": 1}).sort("id", 1):
        try:
            await whscope.assert_usable(wh["id"], entity_id, action="menerima barang di sini", field_label="Gudang")
            return wh
        except HTTPException:
            continue
    raise engine.AnalyticsError("Tidak ada gudang penerimaan yang boleh dipakai entitas ini.")


async def _draft_po(args, user, sc, entity_id) -> Dict[str, Any]:
    from services.pr_sourcing_service import resolve_line_sourcing
    from services.ai_forecast import _first_supplier
    if not await sc.allowed((("purchase_order", "create"),)):
        raise engine.AnalyticsError("Anda belum punya akses untuk membuat Pesanan Pembelian (PO), jadi draf PO tidak bisa "
                                    "disiapkan.")
    items = [i for i in (args.get("items") or []) if float(i.get("quantity") or 0) > 0][:MAX_LINES]
    if not items:
        raise engine.AnalyticsError("Draf PO butuh minimal satu barang dengan qty > 0.")
    prods = {p["id"]: p async for p in db.products.find({"id": {"$in": [i["product_id"] for i in items]}},
                                                          {"_id": 0, "id": 1, "name": 1, "base_unit": 1})}
    missing = [i["product_id"] for i in items if i["product_id"] not in prods]
    if missing:
        raise engine.AnalyticsError(f"Produk tidak dikenal: {', '.join(missing)} — pakai id dari find_entities/forecast.")
    fixed_sup = args.get("supplier_id") or ""
    auto = await _first_supplier(list(prods)) if not fixed_sup else {}
    wh = await _warehouse(entity_id)
    groups: Dict[str, Dict[str, Any]] = {}
    for it in items:
        sid = fixed_sup or (auto.get(it["product_id"]) or {}).get("supplier_id") or ""
        if not sid:
            raise engine.AnalyticsError(f"Supplier untuk {prods[it['product_id']]['name']} belum diketahui — sebutkan supplier_id.")
        g = groups.setdefault(sid, {"supplier_id": sid, "warehouse_id": wh["id"], "warehouse_name": wh.get("name"), "items": []})
        if any(x["product_id"] == it["product_id"] for x in g["items"]):
            continue
        qty = round(float(it["quantity"]), 2)
        src = await resolve_line_sourcing(supplier_id=sid, product_id=it["product_id"], qty=qty, entity_id=entity_id,
                                          unit=it.get("unit") or prods[it["product_id"]].get("base_unit") or "")
        g["items"].append({"product_id": it["product_id"], "product_name": prods[it["product_id"]]["name"], "quantity": qty,
                           "unit": src.get("unit") or it.get("unit") or prods[it["product_id"]].get("base_unit") or "meter",
                           "price": float(src.get("price") or 0), "price_source": src.get("source") or "",
                           "expected_grade": src.get("expected_grade") or "A"})
    names = {s["id"]: s.get("name", "") async for s in db.suppliers.find({"id": {"$in": list(groups)}}, {"_id": 0, "id": 1, "name": 1})}
    for sid, g in groups.items():
        if sid not in names:
            raise engine.AnalyticsError(f"Supplier {sid} tidak ditemukan.")
        g["supplier_name"] = names[sid]
    rows = [{"supplier": g["supplier_name"], "product": i["product_name"], "quantity": i["quantity"], "unit": i["unit"],
             "price": i["price"], "value": round(i["quantity"] * i["price"], 2)} for g in groups.values() for i in g["items"]]
    return {"pos": list(groups.values()), "rows": rows}


async def _reminders(action_type, args, user, sc) -> Dict[str, Any]:
    from services.ai_tools import _ar_orders
    if not await sc.allowed((("order", "view"),)):
        raise engine.AnalyticsError("Data pelanggan tidak tersedia untuk peran Anda.")
    cids = [c for c in (args.get("customer_ids") or []) if c][:50]
    cq: Dict[str, Any] = {"entity_id": {"$in": sc.entity_ids}}
    if sc.sales_only:
        cq["assigned_sales_id"] = sc.sales_only
    if cids:
        cq["id"] = {"$in": cids}
    custs = {c["id"]: c async for c in db.customers.find(cq, {"_id": 0, "id": 1, "name": 1, "assigned_sales_id": 1})}
    sales = {u["id"]: u.get("name", "") async for u in db.users.find(
        {"id": {"$in": [c.get("assigned_sales_id") for c in custs.values() if c.get("assigned_sales_id")]}}, {"_id": 0, "id": 1, "name": 1})}
    out: List[Dict[str, Any]] = []
    if action_type == "collection_followup":
        by_name: Dict[str, Dict[str, Any]] = {}
        for c in custs.values():
            by_name[c["name"]] = c
        for o in await _ar_orders(sc, True, 500, {"id": {"$in": list(custs)}}):
            c = by_name.get(o["customer"])
            if not c:
                continue
            r = next((x for x in out if x["customer_id"] == c["id"]), None)
            if not r:
                r = {"customer_id": c["id"], "customer": c["name"], "sales_id": c.get("assigned_sales_id") or "",
                     "sales": sales.get(c.get("assigned_sales_id"), ""), "orders": [], "outstanding": 0.0, "max_days_overdue": 0}
                out.append(r)
            r["orders"].append(o["number"])
            r["outstanding"] = round(r["outstanding"] + float(o["outstanding"] or 0), 2)
            r["max_days_overdue"] = max(r["max_days_overdue"], int(o["days_overdue"] or 0))
        out.sort(key=lambda r: -r["outstanding"])
    else:
        days = 60
        cut = (now_wib().date() - timedelta(days=days)).isoformat()
        last = {r["_id"]: r["last"] async for r in db.fact_sales_lines.aggregate([
            {"$match": {"customer_id": {"$in": list(custs)}, "is_live": True, "is_sample": False}},
            {"$group": {"_id": "$customer_id", "last": {"$max": "$date_wib"}}}])}
        for c in custs.values():
            lo = last.get(c["id"])
            if cids or not lo or lo < cut:
                out.append({"customer_id": c["id"], "customer": c["name"], "sales_id": c.get("assigned_sales_id") or "",
                            "sales": sales.get(c.get("assigned_sales_id"), ""), "last_order": lo or "—"})
    if not out:
        raise engine.AnalyticsError("Tidak ada pelanggan yang cocok untuk tindakan ini.")
    return {"reminders": out[:50], "rows": out[:50]}


def _waktu(iso: Any) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


async def _masa_berlaku(entity_id: str) -> timedelta:
    """Masa berlaku kartu untuk PT kartu (dipakai saat membaca kartu lama tanpa `expires_at`)."""
    return timedelta(hours=int(await value_of(KUNCI_MASA_BERLAKU, {"entity_id": entity_id})))


async def _nama_pt(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "name": 1, "legal_name": 1}) or {}
    return e.get("short_name") or e.get("name") or e.get("legal_name") or "PT lain"


async def propose_action(args, user, ctx, session_id=None) -> Dict[str, Any]:
    at = args.get("action_type")
    if at not in TYPES:
        raise engine.AnalyticsError("Jenis tindakan tidak dikenal.")
    # AG-T1 — kartu selalu milik PT aktif; mode "Semua PT" hanya baca (02 §3.4 N3), jadi tidak menyiapkan tindakan.
    if getattr(ctx, "view_all", False) or ctx.active_entity_id in ("", "all"):
        raise engine.AnalyticsError(MSG_SEMUA_PT)
    sc = await engine.build_scope(user, ctx)
    entity_id = ctx.active_entity_id
    body = await (_draft_po(args, user, sc, entity_id) if at == "draft_po" else _reminders(at, args, user, sc))
    title = {"draft_po": "Draf purchase order", "collection_followup": "Pengingat penagihan ke sales",
             "customer_followup": "Follow-up pelanggan tidak aktif"}[at]
    jam = int(await value_of(KUNCI_MASA_BERLAKU, {"entity_id": entity_id}))   # AG-T1 — nilai PT kartu saat dibuat
    dibuat = datetime.now(timezone.utc)
    doc = {"id": new_id("aiact"), "type": at, "status": "pending", "title": title,
           "reason": str(args.get("reason") or "")[:500], "note": str(args.get("note") or "")[:500],
           "payload": {k: v for k, v in body.items() if k != "rows"}, "user_id": user["id"], "user_name": user.get("name", ""),
           "entity_id": entity_id, "session_id": session_id or "", "created_at": dibuat.isoformat(),
           "expires_at": (dibuat + timedelta(hours=jam)).isoformat()}
    # AG-T3 — satu kartu `pending` per percakapan (indeks `uq_pending_session`): kartu sebelumnya `superseded`.
    from services.ai_cards import insert_card
    await insert_card(doc)
    return {"proposal_id": doc["id"], "action_type": at, "title": title, "rows": body["rows"],
            "instruction": f"Sisipkan blok ```kn-action\n{{\"proposal_id\": \"{doc['id']}\"}}\n``` agar pengguna bisa menyetujui."}


async def _segarkan(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Kedaluwarsa & proses mati diterapkan saat kartu dibaca (data lama ikut, tanpa skrip migrasi)."""
    now = datetime.now(timezone.utc)
    if doc.get("status") == "pending":
        exp = doc.get("expires_at") or ((_waktu(doc.get("created_at")) or now) + await _masa_berlaku(doc["entity_id"])).isoformat()
        doc["expires_at"] = exp   # kartu lama: dihitung dari created_at + pengaturan PT kartu, tidak disimpan
        if (_waktu(exp) or now) <= now:
            res = await db.ai_action_proposals.update_one(
                {"id": doc["id"], "status": "pending"},
                {"$set": {"status": "expired", "finished_at": now.isoformat(), "updated_at": now.isoformat()}})
            if res.modified_count:
                doc.update(status="expired", finished_at=now.isoformat())
            else:
                return await db.ai_action_proposals.find_one({"id": doc["id"]}, {"_id": 0}) or doc
    elif doc.get("status") == "running":
        terakhir = doc.get("updated_at") or doc.get("started_at") or doc.get("created_at")
        if (_waktu(terakhir) or now) < now - timedelta(minutes=RUNNING_STALE_MINUTES):
            flt: Dict[str, Any] = {"id": doc["id"], "status": "running"}
            if doc.get("updated_at"):
                flt["updated_at"] = doc["updated_at"]
            upd = {"status": "failed", "error": MSG_PROSES_MATI, "finished_at": now.isoformat(), "updated_at": now.isoformat()}
            if doc.get("class"):   # AG-T3 — kartu baru: galat bersandi `uncertain` (hasil tidak pasti)
                upd.update(error=MSG_PROSES_MATI_KARTU, error_code="uncertain",
                           result={"status_code": 0, "document": None, "gl_status": None, "message": MSG_PROSES_MATI_KARTU})
            res = await db.ai_action_proposals.update_one(flt, {"$set": upd})
            if res.modified_count:
                doc.update(upd)
            else:
                return await db.ai_action_proposals.find_one({"id": doc["id"]}, {"_id": 0}) or doc
    return doc


async def load(pid: str, user: Dict[str, Any]) -> Dict[str, Any]:
    doc = await db.ai_action_proposals.find_one({"id": pid}, {"_id": 0})
    from dependencies import has_permission
    if not doc or (doc["user_id"] != user["id"] and not await has_permission(user, "ai", "configure")):   # PR-T2
        raise HTTPException(status_code=404, detail="Draf tindakan tidak ditemukan")
    doc = await _segarkan(doc)
    doc["entity_name"] = await _nama_pt(doc.get("entity_id") or "")
    return doc


def _apply_edits(pos: List[Dict[str, Any]], edits: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for pi, po in enumerate((edits or {}).get("pos") or []):
        for ii, it in enumerate(po.get("items") or []):
            if pi < len(pos) and ii < len(pos[pi]["items"]) and it.get("quantity") is not None:
                pos[pi]["items"][ii]["quantity"] = max(0.0, float(it["quantity"]))
    for po in pos:
        po["items"] = [i for i in po["items"] if i["quantity"] > 0]
    return [po for po in pos if po["items"]]


Simpan = Callable[[str], Awaitable[None]]


async def _po_siap(doc, user, edits) -> List[Dict[str, Any]]:
    """Langkah 4 `confirm`: izin & isian diperiksa sebelum klaim — galat di sini tidak mengubah status kartu."""
    if not await has_permission(user, "purchase_order", "create"):
        raise denied([("purchase_order", "create")])   # 02 §3.1 Z6 — kalimat izin, bukan "peran Anda tidak boleh"
    pos = _apply_edits(copy.deepcopy(doc["payload"]["pos"]), edits)
    if not pos:
        raise HTTPException(status_code=400, detail="Semua qty nol — tidak ada PO yang dibuat")
    return pos


async def _exec_po(doc, user, pos, simpan: Simpan) -> None:
    from routers import purchase_orders as po_router
    from schemas_purchasing import POItemCreate, PurchaseOrderCreate
    for g in pos:
        payload = PurchaseOrderCreate(
            supplier_id=g["supplier_id"], warehouse_id=g["warehouse_id"], entity_id=doc["entity_id"], created_by=user.get("name", ""),
            notes=f"Disiapkan Tanya KN · {doc.get('reason') or doc['title']}"[:480],
            items=[POItemCreate(product_id=i["product_id"], quantity=i["quantity"], unit=i["unit"], price=i["price"],
                                expected_grade=i.get("expected_grade") or "A") for i in g["items"]])
        po = await po_router._create_po_core(payload, user, active_entity_id=doc["entity_id"])
        await simpan(po.get("po_number") or po.get("id"))   # langsung tersimpan sebelum PO berikutnya


async def _exec_reminders(doc, user, simpan: Simpan) -> None:
    from services.notification_service import create_notification
    for r in doc["payload"]["reminders"]:
        to = r.get("sales_id") or user["id"]
        if doc["type"] == "collection_followup":
            title = f"Tagih {r['customer']}"
            body = (f"{len(r['orders'])} pesanan lewat jatuh tempo (terlama {r['max_days_overdue']} hari): {', '.join(r['orders'][:5])}. "
                    f"Diminta oleh {user.get('name', '')} lewat Tanya KN.")
        else:
            title = f"Follow-up {r['customer']}"
            body = f"Pesanan terakhir: {r.get('last_order')}. Hubungi pelanggan ini. Diminta oleh {user.get('name', '')} lewat Tanya KN."
        if doc.get("note"):
            body += f" Catatan: {doc['note']}"
        n = await create_notification(notif_type="ai_followup", title=title, body=body, severity="warning", link="customers",
                                      entity_id=doc["entity_id"], recipient_role="", recipient_user=to,
                                      ref=f"{doc['id']}:{r['customer_id']}")
        if n:
            await simpan(f"{r['customer']} → {r.get('sales') or user.get('name', '')}")


def _galat(exc: Exception) -> str:
    teks = exc.detail if isinstance(exc, HTTPException) else str(exc)
    return (teks if isinstance(teks, str) else str(teks)).strip() or type(exc).__name__


def _pesan_gagal(error: str, result: List[str]) -> str:
    if not result:
        return error
    return f"{error.rstrip('.')}. Yang sudah dibuat: {', '.join(result)}."


async def confirm(pid: str, user: Dict[str, Any], edits: Optional[Dict[str, Any]], ctx) -> Dict[str, Any]:
    # 1. muat (kedaluwarsa & proses mati diterapkan di `load`)
    doc = await load(pid, user)
    if doc["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Hanya pembuat draf yang boleh menyetujuinya")
    # 2. kedaluwarsa / sudah diproses
    if doc["status"] == "expired":
        raise HTTPException(status_code=409, detail=MSG_KEDALUWARSA)
    if doc["status"] != "pending":
        raise HTTPException(status_code=409, detail=MSG_SUDAH_DIPROSES)
    # 3. PT kartu diadu dengan akses & PT aktif pengguna SAAT INI (02 §3.4 N1, N5)
    eid = doc.get("entity_id") or ""
    if eid not in (ctx.allowed_entity_ids or []):
        raise HTTPException(status_code=403, detail=MSG_TANPA_AKSES_PT)
    if getattr(ctx, "view_all", False) or ctx.active_entity_id != eid:
        raise HTTPException(status_code=409, detail=(
            f"Draf ini disiapkan untuk {doc.get('entity_name') or await _nama_pt(eid)}. Pindah ke PT itu lalu setujui lagi."))
    # 4. izin & isian — galat di sini tidak mengubah status
    pos = await _po_siap(doc, user, edits) if doc["type"] == "draft_po" else None
    # 5. klaim atomik pending → running
    mulai = now_iso()
    claimed = await db.ai_action_proposals.find_one_and_update(
        {"id": pid, "status": "pending"}, {"$set": {"status": "running", "started_at": mulai, "updated_at": mulai, "result": []}})
    if not claimed:
        raise HTTPException(status_code=409, detail=MSG_SUDAH_DIPROSES)
    # 6. jalankan; tiap butir yang berhasil langsung disimpan
    done: List[str] = []

    async def simpan(butir: str) -> None:
        done.append(butir)
        await db.ai_action_proposals.update_one({"id": pid}, {"$push": {"result": butir}, "$set": {"updated_at": now_iso()}})

    error = ""
    try:
        await (_exec_po(doc, user, pos, simpan) if doc["type"] == "draft_po" else _exec_reminders(doc, user, simpan))
    except Exception as exc:  # noqa: BLE001 — galat pelaksana dicatat di kartu (status `failed`), bukan dilempar
        error = _galat(exc)[:500]
    # 7. selesai: confirmed, atau failed dengan galat asli + yang sudah jadi
    selesai = now_iso()
    upd: Dict[str, Any] = {"status": "failed" if error else "confirmed", "finished_at": selesai, "updated_at": selesai}
    if error:
        upd["error"] = error
    else:
        upd["confirmed_at"] = selesai
    await db.ai_action_proposals.update_one({"id": pid, "status": "running"}, {"$set": upd})
    await audit(user.get("name", ""), "ai_action_failed" if error else "ai_action_confirmed", "ai_action_proposals", pid,
                {"type": doc["type"], "result": done, **({"error": error} if error else {})})
    out = {**doc, "result": done, "started_at": mulai, **upd}
    if error:
        out["message"] = _pesan_gagal(error, done)
    return out


async def dismiss(pid: str, user: Dict[str, Any]) -> Dict[str, Any]:
    doc = await load(pid, user)
    if doc["status"] == "expired":
        raise HTTPException(status_code=409, detail=MSG_KEDALUWARSA)
    selesai = now_iso()
    res = await db.ai_action_proposals.update_one(
        {"id": pid, "status": "pending"}, {"$set": {"status": "dismissed", "finished_at": selesai, "updated_at": selesai}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail=MSG_SUDAH_DIPROSES)
    return {**doc, "status": "dismissed", "finished_at": selesai}
