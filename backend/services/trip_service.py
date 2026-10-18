"""L07 LN-070/071 — picking list multi-gudang, cek kesiapan trip multi-SO, manifest armada."""
from typing import Any, Dict, List

from fastapi import HTTPException

from db import db
from core_utils import safe_doc
from services import loading_check_service as lcs
from services.shipment_service import picked_roll_ids

OPEN_TASK = {"$nin": ["dispatched", "cancelled", "done", "escalated"]}


async def trip_candidates(entity_ids: List[str]) -> List[Dict[str, Any]]:
    """SO yang masih punya tugas ambil (outbound) terbuka — bahan picking list / trip."""
    q: Dict[str, Any] = {"flow_type": "outbound", "status": OPEN_TASK}
    if entity_ids:
        q["entity_id"] = {"$in": entity_ids}
    out: Dict[str, Dict[str, Any]] = {}
    async for t in db.wms_tasks.find(q, {"_id": 0, "order_id": 1, "order_number": 1, "warehouse_id": 1,
                                         "warehouse_name": 1, "fulfillment_method": 1}):
        row = out.setdefault(t["order_id"], {"order_id": t["order_id"], "order_number": t.get("order_number", ""),
                                             "warehouses": [], "fulfillment_method": t.get("fulfillment_method") or "kirim"})
        if t.get("warehouse_name") and t["warehouse_name"] not in row["warehouses"]:
            row["warehouses"].append(t["warehouse_name"])
    names = {o["id"]: o.get("customer_name", "") async for o in db.sales_orders.find(
        {"id": {"$in": list(out)}}, {"_id": 0, "id": 1, "customer_name": 1})}
    for r in out.values():
        r["customer_name"] = names.get(r["order_id"], "")
    return sorted(out.values(), key=lambda r: r["order_number"])


async def _orders_in_scope(order_ids: List[str], entity_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    ids = [o for o in dict.fromkeys(order_ids) if o]
    if not ids:
        raise HTTPException(status_code=400, detail="Pilih minimal 1 pesanan.")
    sos = {o["id"]: o for o in await db.sales_orders.find(
        {"id": {"$in": ids}}, {"_id": 0, "id": 1, "number": 1, "customer_name": 1, "entity_id": 1}).to_list(200)}
    missing = [i for i in ids if i not in sos]
    if missing:
        raise HTTPException(status_code=404, detail=f"Pesanan tidak ditemukan: {', '.join(missing)}")
    if entity_ids:
        foreign = [s["number"] for s in sos.values() if s.get("entity_id") and s["entity_id"] not in entity_ids]
        if foreign:
            raise HTTPException(status_code=403, detail=f"Pesanan di luar badan usaha Anda: {', '.join(foreign)}")
    return sos


async def picking_list(order_ids: List[str], entity_ids: List[str]) -> Dict[str, Any]:
    """Daftar ambil per gudang sumber; tiap roll tetap milik SO-nya (komitmen tidak digabung)."""
    sos = await _orders_in_scope(order_ids, entity_ids)
    tasks = await db.wms_tasks.find({"order_id": {"$in": list(sos)}, "flow_type": "outbound", "status": OPEN_TASK},
                                    {"_id": 0}).to_list(1000)
    picked = {rid for t in tasks for rid in picked_roll_ids(t)}
    rolls = await db.inventory_rolls.find(
        {"reserved_ref.type": "sales_order", "reserved_ref.id": {"$in": list(sos)},
         "status": {"$in": lcs.EXPECTED_STATUSES}, "length_remaining": {"$gt": 0}},
        {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "warehouse_id": 1, "bin_id": 1, "bin_code": 1,
         "length_remaining": 1, "unit": 1, "status": 1, "lot": 1, "reserved_ref": 1, "rfid_tag_id": 1}).to_list(5000)
    from services.location_service import flatten_bins
    bins: Dict[str, str] = {}
    async for wh in db.warehouses.find({"id": {"$in": list({r["warehouse_id"] for r in rolls})}}, {"_id": 0}):
        bins.update({b["bin_id"]: b.get("code", "") for b in flatten_bins(wh)})
    whs: Dict[str, Dict[str, Any]] = {}
    for t in tasks:
        w = whs.setdefault(t["warehouse_id"], {"warehouse_id": t["warehouse_id"], "warehouse_name": t.get("warehouse_name", ""),
                                               "lines": [], "rolls": []})
        w["lines"].append({"task_id": t["id"], "order_id": t["order_id"], "order_number": t.get("order_number", ""),
                           "product_id": t["product_id"], "product_name": t.get("product_name", ""), "sku": t.get("sku", ""),
                           "quantity": t.get("quantity"), "picked_qty": t.get("picked_qty"), "shipped_qty": t.get("shipped_qty"),
                           "unit": t.get("unit"), "status": t.get("status")})
    pnames = {ln["product_id"]: ln["product_name"] for w in whs.values() for ln in w["lines"]}
    for r in rolls:
        oid = r["reserved_ref"]["id"]
        w = whs.setdefault(r["warehouse_id"], {"warehouse_id": r["warehouse_id"], "warehouse_name": "", "lines": [], "rolls": []})
        w["rolls"].append({"roll_id": r["id"], "roll_no": r.get("roll_no", ""), "order_id": oid,
                           "order_number": sos[oid].get("number", ""), "product_id": r.get("product_id"),
                           "product_name": pnames.get(r.get("product_id"), ""), "lot": r.get("lot", ""),
                           "bin": bins.get(r.get("bin_id")) or r.get("bin_code") or "", "length": r.get("length_remaining"),
                           "unit": r.get("unit"), "status": r.get("status"), "picked": r["id"] in picked,
                           "tagged": bool(r.get("rfid_tag_id"))})
    for w in whs.values():
        if not w["warehouse_name"]:
            wh = await db.warehouses.find_one({"id": w["warehouse_id"]}, {"_id": 0, "name": 1})
            w["warehouse_name"] = (wh or {}).get("name", "")
        w["rolls"].sort(key=lambda x: (x["bin"], x["order_number"], x["roll_no"]))
        w["roll_count"] = len(w["rolls"])
        w["picked_count"] = sum(1 for x in w["rolls"] if x["picked"])
    return {"orders": [{"order_id": s["id"], "order_number": s.get("number", ""), "customer_name": s.get("customer_name", "")}
                       for s in sos.values()],
            "warehouses": sorted(whs.values(), key=lambda w: w["warehouse_name"]),
            "note": "Picking list bukan Surat Jalan — SJ terbit per SO per keberangkatan saat dispatch."}


async def trip_check(order_ids: List[str], entity_ids: List[str]) -> Dict[str, Any]:
    """Cek kesiapan berangkat per SO × gudang memakai pagar dispatch yang sama (multi-SO tidak melonggarkan)."""
    sos = await _orders_in_scope(order_ids, entity_ids)
    tasks = await db.wms_tasks.find({"order_id": {"$in": list(sos)}, "flow_type": "outbound", "status": OPEN_TASK},
                                    {"_id": 0, "order_id": 1, "warehouse_id": 1, "warehouse_name": 1}).to_list(1000)
    pairs = list(dict.fromkeys((t["order_id"], t["warehouse_id"], t.get("warehouse_name", "")) for t in tasks))
    rows = []
    for oid, wid, wname in pairs:
        try:
            await lcs.dispatch_guard(oid, wid)
            ok, reason = True, ""
        except HTTPException as e:
            ok, reason = False, e.detail if isinstance(e.detail, str) else str(e.detail)
        rows.append({"order_id": oid, "order_number": sos[oid].get("number", ""), "warehouse_id": wid,
                     "warehouse_name": wname, "ready": ok, "reason": reason})
    return {"ready": bool(rows) and all(r["ready"] for r in rows), "rows": rows,
            "no_open_tasks": [s.get("number", "") for oid, s in sos.items() if oid not in {p[0] for p in pairs}]}


async def manifest(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Manifest satu armada: semua SJ (per SO) yang diangkut + roll aktualnya."""
    ships = await db.shipments.find({"id": {"$in": doc.get("shipment_ids") or []}}, {"_id": 0}).to_list(500)
    rids = [r["roll_id"] for s in ships for r in (s.get("rolls") or []) if r.get("roll_id")]
    rnos = {r["id"]: r.get("roll_no", "") async for r in db.inventory_rolls.find(
        {"id": {"$in": rids}}, {"_id": 0, "id": 1, "roll_no": 1})}
    by_order: Dict[str, Dict[str, Any]] = {}
    for s in sorted(ships, key=lambda x: (x.get("order_number", ""), x.get("shipment_no", ""))):
        o = by_order.setdefault(s["order_id"], {"order_id": s["order_id"], "order_number": s.get("order_number", ""),
                                                "shipments": [], "roll_count": 0})
        rolls = [{"roll_id": r["roll_id"], "roll_no": rnos.get(r["roll_id"], ""), "length": r.get("length"),
                  "unit": r.get("unit"), "lot": r.get("lot", "")} for r in (s.get("rolls") or [])]
        o["shipments"].append({"shipment_id": s["id"], "shipment_no": s.get("shipment_no", ""),
                               "warehouse_name": s.get("warehouse_name", ""), "product_name": s.get("product_name", ""),
                               "sku": s.get("sku", ""), "qty": s.get("qty"), "unit": s.get("unit"),
                               "is_partial": s.get("is_partial", False), "rolls": rolls})
        o["roll_count"] += len(rolls)
    meta = {o["order_id"]: o for o in (doc.get("orders") or [])}
    for oid, o in by_order.items():
        o["customer_name"] = (meta.get(oid) or {}).get("customer_name") or doc.get("customer_name", "")
        o["destination"] = (meta.get(oid) or {}).get("destination") or doc.get("destination", "")
    return safe_doc({"delivery_id": doc["id"], "number": doc.get("number"), "mode_label": doc.get("mode_label"),
                     "vehicle_plate": doc.get("vehicle_plate"), "driver_name": doc.get("driver_name"),
                     "courier_name": doc.get("courier_name"), "tracking_no": doc.get("tracking_no"),
                     "status_label": doc.get("status_label"), "orders": list(by_order.values()),
                     "totals": {"orders": len(by_order), "shipments": len(ships),
                                "rolls": sum(o["roll_count"] for o in by_order.values())}})
