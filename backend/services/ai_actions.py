"""Tanya KN — draf tindakan dari jawaban AI. Tidak ada yang tersimpan/terkirim sebelum pengguna menekan Setujui.

Jenis: `draft_po` (PO ke supplier), `collection_followup` (pengingat tagih ke sales),
`customer_followup` (daftar follow-up pelanggan tidak aktif ke sales).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso
from dependencies import audit, has_permission
from services import analytics_engine as engine
from services.analytics_time import now_wib

TYPES = ("draft_po", "collection_followup", "customer_followup")
MAX_LINES = 30


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
        raise engine.AnalyticsError("Peran Anda tidak boleh membuat PO, jadi draf PO tidak bisa disiapkan.")
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


async def propose_action(args, user, ctx, session_id=None) -> Dict[str, Any]:
    at = args.get("action_type")
    if at not in TYPES:
        raise engine.AnalyticsError("Jenis tindakan tidak dikenal.")
    sc = await engine.build_scope(user, ctx)
    entity_id = ctx.active_entity_id if ctx.active_entity_id not in ("", "all") else sc.entity_ids[0]
    body = await (_draft_po(args, user, sc, entity_id) if at == "draft_po" else _reminders(at, args, user, sc))
    title = {"draft_po": "Draf purchase order", "collection_followup": "Pengingat penagihan ke sales",
             "customer_followup": "Follow-up pelanggan tidak aktif"}[at]
    doc = {"id": new_id("aiact"), "type": at, "status": "pending", "title": title,
           "reason": str(args.get("reason") or "")[:500], "note": str(args.get("note") or "")[:500],
           "payload": {k: v for k, v in body.items() if k != "rows"}, "user_id": user["id"], "user_name": user.get("name", ""),
           "entity_id": entity_id, "session_id": session_id or "", "created_at": now_iso()}
    await db.ai_action_proposals.insert_one(dict(doc))
    return {"proposal_id": doc["id"], "action_type": at, "title": title, "rows": body["rows"],
            "instruction": f"Sisipkan blok ```kn-action\n{{\"proposal_id\": \"{doc['id']}\"}}\n``` agar pengguna bisa menyetujui."}


async def load(pid: str, user: Dict[str, Any]) -> Dict[str, Any]:
    doc = await db.ai_action_proposals.find_one({"id": pid}, {"_id": 0})
    if not doc or (doc["user_id"] != user["id"] and user.get("role") != "admin"):
        raise HTTPException(status_code=404, detail="Draf tindakan tidak ditemukan")
    return doc


def _apply_edits(pos: List[Dict[str, Any]], edits: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for pi, po in enumerate((edits or {}).get("pos") or []):
        for ii, it in enumerate(po.get("items") or []):
            if pi < len(pos) and ii < len(pos[pi]["items"]) and it.get("quantity") is not None:
                pos[pi]["items"][ii]["quantity"] = max(0.0, float(it["quantity"]))
    for po in pos:
        po["items"] = [i for i in po["items"] if i["quantity"] > 0]
    return [po for po in pos if po["items"]]


async def _exec_po(doc, user, edits) -> List[str]:
    from routers.purchase_orders import _create_po_core
    from schemas_purchasing import POItemCreate, PurchaseOrderCreate
    if not await has_permission(user, "purchase_order", "create"):
        raise HTTPException(status_code=403, detail="Peran Anda tidak boleh membuat PO")
    pos = _apply_edits(doc["payload"]["pos"], edits)
    if not pos:
        raise HTTPException(status_code=400, detail="Semua qty nol — tidak ada PO yang dibuat")
    made = []
    for g in pos:
        payload = PurchaseOrderCreate(
            supplier_id=g["supplier_id"], warehouse_id=g["warehouse_id"], entity_id=doc["entity_id"], created_by=user.get("name", ""),
            notes=f"Disiapkan Tanya KN · {doc.get('reason') or doc['title']}"[:480],
            items=[POItemCreate(product_id=i["product_id"], quantity=i["quantity"], unit=i["unit"], price=i["price"],
                                expected_grade=i.get("expected_grade") or "A") for i in g["items"]])
        po = await _create_po_core(payload, user, active_entity_id=doc["entity_id"])
        made.append(po.get("po_number") or po.get("id"))
    return made


async def _exec_reminders(doc, user) -> List[str]:
    from services.notification_service import create_notification
    sent = []
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
            sent.append(f"{r['customer']} → {r.get('sales') or user.get('name', '')}")
    return sent


async def confirm(pid: str, user: Dict[str, Any], edits: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    doc = await load(pid, user)
    if doc["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Hanya pembuat draf yang boleh menyetujuinya")
    claimed = await db.ai_action_proposals.find_one_and_update({"id": pid, "status": "pending"}, {"$set": {"status": "running"}})
    if not claimed:
        raise HTTPException(status_code=409, detail="Draf ini sudah diproses")
    try:
        done = await (_exec_po(doc, user, edits) if doc["type"] == "draft_po" else _exec_reminders(doc, user))
    except Exception:
        await db.ai_action_proposals.update_one({"id": pid}, {"$set": {"status": "pending"}})
        raise
    upd = {"status": "confirmed", "result": done, "confirmed_at": now_iso()}
    await db.ai_action_proposals.update_one({"id": pid}, {"$set": upd})
    await audit(user.get("name", ""), "ai_action_confirmed", "ai_action_proposals", pid, {"type": doc["type"], "result": done})
    return {**doc, **upd}


async def dismiss(pid: str, user: Dict[str, Any]) -> Dict[str, Any]:
    doc = await load(pid, user)
    res = await db.ai_action_proposals.update_one({"id": pid, "status": "pending"}, {"$set": {"status": "dismissed"}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Draf ini sudah diproses")
    return {**doc, "status": "dismissed"}
