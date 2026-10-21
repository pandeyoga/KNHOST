# Uji ulang temuan terhadap kode yang berjalan (HEAD terbaru + perubahan lokal sesi lain).
import os, re, httpx
from pymongo import MongoClient
mdb = MongoClient(os.environ.get("MONGO_URL", "mongodb://mongo:27017"))[os.environ.get("DB_NAME", "test_database")]
R = {}

# F-01
r = httpx.post(BASE + "/auth/login", json={"email": "sales@kainnusantara.id", "password": "demo12345"})
R["F-01"] = f"sales+demo12345 -> {r.status_code}"

sales = Api("sales@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); mgr = Api("manager@kainnusantara.id")
wh = Api("warehouse@kainnusantara.id"); whadm = Api("wh.admin@kainnusantara.id"); qc = Api("qc@kainnusantara.id")

# F-03
c, b = sales.get("/products", params={"q": "DENIM TENCEL", "limit": 10})
txt = short(b, 200000)
R["F-03"] = "variant_label grade: " + str(sorted(set(re.findall(r'"variant_label": ?"([^"]*)"', txt)))[:3])
c, b = sales.get("/sales-orders/frequent-products", params={"customer_id": "cust_toko_kain"})
R["F-02"] = "frequent roll_count: " + str([x.get("roll_count") for x in (b if isinstance(b, list) else [])][:3])

# F-09
P = "prod_bffe7f853835"
c, so = sales.post("/sales-orders", {"customer_id": "cust_toko_kain", "shipping_address_id": "", "entity_id": "ent_ksc",
                                     "items": [{"product_id": P, "quantity": 30, "unit": "yard"}], "payment_term_code": "NET30", "confirm_mixed_lot": True})
SO = so["id"]
sales.post(f"/sales-orders/{SO}/request-special-price", {"product_id": P, "requested_price": 18000, "reason": "recheck"})
sadm.post(f"/sales-orders/{SO}/verify", {"note": "x"}); sadm.post(f"/sales-orders/{SO}/submit-for-approval")
c, o = mgr.get(f"/sales-orders/{SO}")
e = next(p for p in o["pending_approvals"] if p["status"] == "pending")
mgr.post(f"/sales-orders/{SO}/approvals/{e['id']}/decide", {"decision": "reject", "notes": "x"})
sales.post(f"/sales-orders/{SO}/request-special-price", {"product_id": P, "requested_price": 19000, "reason": "recheck 2"})
c, o = mgr.get(f"/sales-orders/{SO}")
e = next(p for p in o["pending_approvals"] if p["status"] == "pending")
c, o = mgr.post(f"/sales-orders/{SO}/approvals/{e['id']}/decide", {"decision": "approve"})
c2, b2 = mgr.post(f"/sales-orders/{SO}/approve")
R["F-09"] = f"{o.get('number')} after re-approve status={o.get('status')}; approve -> {c2} {short(b2, 80)}"

# F-10 + F-06 (CBD, whole roll)
P2 = "prod_a17bedf5b3f0"
roll = mdb.inventory_rolls.find_one({"product_id": P2, "owner_entity_id": "ent_ksc", "status": "available", "length_reserved": {"$in": [0, None]},
                                     "reserved_ref": {"$in": [None, {}]}, "length_remaining": {"$gt": 50}}, {"_id": 0, "id": 1, "length_remaining": 1})
c, so = sales.post("/sales-orders", {"customer_id": "cust_toko_kain", "shipping_address_id": "", "entity_id": "ent_ksc",
                                     "items": [{"product_id": P2, "quantity": roll["length_remaining"], "unit": "yard", "purchase_mode": "roll",
                                                "roll_lines": [{"roll_id": roll["id"], "take_qty": 0}], "target_quantity": roll["length_remaining"], "rounding_choice": "exact"}],
                                     "payment_term_code": "CBD", "confirm_mixed_lot": True})
SOC = so["id"]
sadm.post(f"/sales-orders/{SOC}/verify", {"note": "x"}); sadm.post(f"/sales-orders/{SOC}/submit-for-approval"); sadm.post(f"/sales-orders/{SOC}/confirm")
c, t = wh.get("/outbound/tasks"); t = [x for x in t if x.get("order_id") == SOC][0]
wh.post(f"/outbound/tasks/{t['id']}/scan-pick", params={"actual_qty": roll["length_remaining"], "roll_id": roll["id"]})
c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
if c != 200 and "RFID" in short(b):
    whadm.post(f"/outbound/so/{SOC}/loading-check/override", {"reason": "recheck tanpa RFID"}); c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
R["F-10"] = f"{so['number']} CBD unpaid dispatch -> {c} {(b.get('shipment') or {}).get('shipment_no') if isinstance(b, dict) else short(b, 120)}"
if c == 200:
    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000000000200015e2f3a8d0000000049454e44ae426082")
    c, dv = whadm.post("/logistics/deliveries", {"shipment_ids": [b["shipment"]["id"]], "mode": "own_fleet", "vehicle_plate": "D 2 RC", "driver_name": "Kurniawan"})
    D = dv["id"]
    whadm._do("POST", f"/logistics/deliveries/{D}/photos", data={"kind": "load"}, files={"file": ("m.png", png, "image/png")})
    whadm.post(f"/logistics/deliveries/{D}/transition", {"to": "loaded"}); whadm.post(f"/logistics/deliveries/{D}/transition", {"to": "in_transit"})
    whadm._do("POST", f"/logistics/deliveries/{D}/photos", data={"kind": "pod"}, files={"file": ("p.png", png, "image/png")})
    c, x = whadm.post(f"/logistics/deliveries/{D}/transition", {"to": "delivered", "receiver_name": "Pak Hendra"})
    c, o = sadm.get(f"/sales-orders/{SOC}")
    R["F-06"] = f"after POD delivered: SO status={o.get('status')}"

# F-11 / F-12
c, r = sales.post("/sales-returns", {"order_id": "so_d9aa799376ff", "return_type": "retur", "items": [
    {"product_id": "prod_c854e5856251", "quantity_returned": 1, "unit": "yard", "reason": "recheck", "condition": "ok",
     "roll_ids": ["roll_c0a6a0b383da"], "roll_qtys": {"roll_c0a6a0b383da": 1}}], "complaint_code": "lain", "submit_now": True})
RT = r.get("id") if isinstance(r, dict) else None
if RT:
    mgr.post(f"/sales-returns/{RT}/approve", {"notes": "x"})
    c1, b1 = wh.post(f"/sales-returns/{RT}/journey/scan", {"stage": "received", "codes": ["RL-36311"], "warehouse_id": "wh_jakarta"})
    c2, b2 = qc.post(f"/sales-returns/{RT}/inspect/start")
    R["F-11"] = f"warehouse scan -> {c1}; qc inspect/start -> {c2}"
    # pakai return baru untuk F-12 (belum ada scan)
    c, r2 = sales.post("/sales-returns", {"order_id": "so_d9aa799376ff", "return_type": "retur", "items": [
        {"product_id": "prod_c854e5856251", "quantity_returned": 1, "unit": "yard", "reason": "recheck", "condition": "ok",
         "roll_ids": ["roll_c0a6a0b383da"], "roll_qtys": {"roll_c0a6a0b383da": 1}}], "complaint_code": "lain", "submit_now": True})
    if isinstance(r2, dict) and r2.get("id"):
        mgr.post(f"/sales-returns/{r2['id']}/approve", {"notes": "x"})
        c3, b3 = sadm.post(f"/sales-returns/{r2['id']}/inspect/start")
        c4, b4 = sadm.post(f"/sales-returns/{r2['id']}/inspect/complete", {"inspections": [{"product_id": "prod_c854e5856251", "condition": "ok", "accepted_qty": 1}]})
        R["F-12"] = f"QC tanpa scan terima: start {c3}, complete {c4} {short(b4, 80)}"
else:
    R["F-11"] = "retur gagal dibuat: " + short(r, 200)

# F-05
P3 = "prod_c854e5856251"
c, so = sales.post("/sales-orders", {"customer_id": "cust_toko_kain", "shipping_address_id": "", "entity_id": "ent_ksc",
                                     "items": [{"product_id": P3, "quantity": 150, "unit": "yard"}], "payment_term_code": "NET30", "confirm_mixed_lot": True})
S5 = so["id"]
sadm.post(f"/sales-orders/{S5}/verify", {"note": "x"}); sadm.post(f"/sales-orders/{S5}/submit-for-approval"); sadm.post(f"/sales-orders/{S5}/confirm")
c, pc = wh.get("/inventory/pending-cuts", params={"order_id": S5})
items = pc.get("items", [])
for i in items:
    wh.post(f"/inventory/rolls/{i['roll_id']}/reservations/{i['reservation_id']}/cut", {"actual_length": i["qty"], "waste": 0})
c, o = sadm.get(f"/sales-orders/{S5}")
R["F-05"] = f"{so['number']} cuts={len(items)}; alloc rolls after cut: " + str([r.get("roll_no") for a in o.get("allocations", []) for r in a.get("rolls", [])])

# F-07
c, j = sales.get("/sales-orders/so_d9aa799376ff/journey")
st = next((s for s in j.get("steps", []) if s["key"] == "disiapkan"), {})
R["F-07"] = f"journey disiapkan done={st.get('done')} detail={st.get('detail')} progress={j.get('progress')}"

# F-16
c, desk = sadm.get("/sales-admin/desk")
q = next((x for x in desk.get("queues", []) if x.get("key") == "jatuh_tempo"), {})
R["F-16"] = "jatuh_tempo includes SO-00045 (backorder): " + str(any("SO-00045" in (r.get("number") or "") for r in q.get("rows", [])))

for k, v in R.items():
    print(k, "|", v)
