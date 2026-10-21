# Lanjutan O2C dari SO yang sudah confirmed: potong -> verifikasi label -> pick -> loading check ->
# dispatch -> pengiriman -> POD -> diterima -> pembayaran.
import os
SO = os.environ["SO"]
CUST = os.environ.get("CUST", "cust_toko_kain")
sales = Api("sales@kainnusantara.id")
sadm = Api("salesadmin@kainnusantara.id")
wh = Api("warehouse@kainnusantara.id")
whadm = Api("wh.admin@kainnusantara.id")
fin = Api("finance@kainnusantara.id")
png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000000000200015e2f3a8d0000000049454e44ae426082")

# 5a. reservasi potong
c, pc = wh.get("/inventory/pending-cuts", params={"order_id": SO})
items = pc.get("items", []) if isinstance(pc, dict) else []
step("wh: daftar potong tertunda", c, [(i["roll_no"], i["qty"]) for i in items])
c, tasks = wh.get("/outbound/tasks")
tl = [t for t in (tasks if isinstance(tasks, list) else []) if t.get("order_id") == SO]
# coba pick roll induk yang belum dipotong (negatif)
for i in items:
    c, b = wh.post(f"/outbound/tasks/{tl[0]['id']}/scan-pick", params={"actual_qty": i["qty"], "roll_id": i["roll_id"]})
    step("NEG pick roll induk sebelum dipotong ditolak", c, b, (400,))
children = []
for i in items:
    c, b = wh.post(f"/inventory/rolls/{i['roll_id']}/reservations/{i['reservation_id']}/cut",
                   {"actual_length": i["qty"], "waste": 0, "note": "UAT potong"})
    if step(f"wh: konfirmasi potong {i['roll_no']} {i['qty']}", c, {"child": (b.get("child") or {}).get("roll_no"), "sisa_induk": b.get("parent_length_remaining")} if isinstance(b, dict) and "child" in b else b):
        children.append(b["child"])
for ch in children:
    c, b = wh.post(f"/inventory/rolls/{ch['id']}/verify-identity", {"scanned_code": "SALAH-123"})
    step("NEG verifikasi label salah ditolak", c, b, (400,))
    c, b = wh.post(f"/inventory/rolls/{ch['id']}/verify-identity", {"scanned_code": ch["roll_no"]})
    step(f"wh: verifikasi label roll anak {ch['roll_no']}", c, b)

# 5b. pick
c, sod = sadm.get(f"/sales-orders/{SO}")
rolls = []
for a in sod.get("allocations", []):
    for r in a.get("rolls") or []:
        rolls.append((r.get("roll_id"), float(r.get("length") or 0), r.get("roll_no")))
print("roll alokasi kini:", rolls)
for t in tl:
    for rid, q, rno in rolls:
        c, b = wh.post(f"/outbound/tasks/{t['id']}/scan-pick", params={"actual_qty": q, "roll_id": rid})
        step(f"wh: scan-pick {rno} {q}", c, {k: b.get(k) for k in ("status", "picked_qty", "quantity")} if isinstance(b, dict) and "status" in b else b)
c, b = sales.get(f"/sales-orders/{SO}")
print("SO setelah pick:", b.get("status"), b.get("stage"), b.get("sub_status"))

# 6-7. dispatch (dengan loading check)
for t in tl:
    c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
    if c != 200:
        step("info: dispatch tertahan", c, b, (400, 409))
        c2, b2 = whadm.post(f"/outbound/so/{SO}/loading-check/override", {"reason": "UAT tanpa perangkat RFID - validasi manual"})
        step("whadmin: override loading check", c2, {k: b2.get(k) for k in ("result", "reason")} if isinstance(b2, dict) else b2)
        c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
    step("wh: dispatch -> SJ", c, {"task": (b.get("task") or {}).get("status"), "sj": (b.get("shipment") or {}).get("shipment_no"),
                                    "qty": (b.get("shipment") or {}).get("qty"), "gl": (b.get("shipment") or {}).get("gl_status")} if isinstance(b, dict) and "task" in b else b)
c, b = sales.get(f"/sales-orders/{SO}")
print("SO setelah dispatch:", b.get("status"), b.get("stage"), "payment_status", b.get("payment_status"))
c, shp = wh.get("/shipments", params={"order_id": SO})
sl = [s for s in (shp if isinstance(shp, list) else []) if s.get("order_id") == SO]
step("SJ untuk SO", c, [(s["shipment_no"], s.get("qty"), s.get("logistics_status")) for s in sl])

# 8. pengiriman armada sendiri
c, b = whadm.post("/logistics/deliveries", {"shipment_ids": [s["id"] for s in sl], "mode": "own_fleet",
                                             "vehicle_plate": "D 1234 UAT", "driver_name": "Kurniawan", "notes": "UAT O2C"})
dv = need("logistik: buat pengiriman", c, b)
DV = dv["id"]
print("delivery", dv.get("number"), dv.get("status"))
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "loaded"})
step("NEG dimuat tanpa foto ditolak", c, b, (400,))
c, b = whadm._do("POST", f"/logistics/deliveries/{DV}/photos", data={"kind": "load", "note": "muat"}, files={"file": ("muat.png", png, "image/png")})
step("logistik: unggah foto muat", c, {"id": b.get("id")} if isinstance(b, dict) else b)
for to, extra in (("loaded", {}), ("in_transit", {})):
    c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": to, **extra})
    step(f"logistik: -> {to}", c, {"status": b.get("status")} if isinstance(b, dict) and "status" in b else b)
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "delivered", "receiver_name": "Pak Hendra"})
step("NEG terkirim tanpa POD ditolak", c, b, (400,))
c, b = whadm._do("POST", f"/logistics/deliveries/{DV}/photos", data={"kind": "pod", "note": "pod"}, files={"file": ("pod.png", png, "image/png")})
step("logistik: unggah foto POD", c, {"id": b.get("id")} if isinstance(b, dict) else b)
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "delivered", "receiver_name": "Pak Hendra"})
step("logistik: terkirim (POD)", c, {"status": b.get("status")} if isinstance(b, dict) and "status" in b else b)
c, b = sales.get(f"/sales-orders/{SO}")
print("SO setelah POD logistik:", b.get("status"), b.get("stage"))
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "completed"})
step("logistik: selesai", c, {"status": b.get("status")} if isinstance(b, dict) and "status" in b else b)
c, b = sales.get(f"/sales-orders/{SO}")
print("SO setelah delivery selesai:", b.get("status"), b.get("stage"))

# 9. tandai diterima
c, b = sales.post(f"/sales-orders/{SO}/mark-delivered")
step("NEG sales tandai diterima ditolak", c, b, (403,))
c, b = sadm.post(f"/sales-orders/{SO}/mark-delivered")
step("sadm: tandai diterima customer", c, {k: b.get(k) for k in ("status", "stage")} if isinstance(b, dict) and "status" in b else b, (200, 409))

# 10. pembayaran
c, oo = fin.get("/ar-receipts/open-orders", params={"customer_id": CUST})
row = next((o for o in (oo if isinstance(oo, list) else []) if SO in (o.get("order_id"), o.get("id"))), None)
step("fin: SO di daftar order terbuka", c, row)
c, b = sadm.get(f"/sales-orders/{SO}")
grand = float(b.get("grand_total") or 0)
half = round(grand / 2, 2)
c, r1 = fin.post("/ar-receipts", {"customer_id": CUST, "amount": half, "method": "transfer", "entity_id": "ent_ksc",
                                  "notes": "UAT cicilan 1", "allocations": [{"order_id": SO, "amount": half}]})
step("fin: terima 50%", c, {k: r1.get(k) for k in ("number", "amount", "status", "gl_status")} if isinstance(r1, dict) else r1)
c, b = sadm.get(f"/sales-orders/{SO}")
print("setelah 50%:", b.get("payment_status"), b.get("paid_total"))
c, r2 = fin.post("/ar-receipts", {"customer_id": CUST, "amount": grand - half + 1000, "method": "transfer", "entity_id": "ent_ksc",
                                  "notes": "UAT lebih bayar", "allocations": [{"order_id": SO, "amount": grand - half + 1000}]})
step("NEG alokasi melebihi sisa", c, r2, (400, 409, 422))
rest = round(grand - half, 2)
c, r2 = fin.post("/ar-receipts", {"customer_id": CUST, "amount": rest, "method": "transfer", "entity_id": "ent_ksc",
                                  "notes": "UAT pelunasan", "allocations": [{"order_id": SO, "amount": rest}]})
step("fin: pelunasan", c, {k: r2.get(k) for k in ("number", "amount", "status", "gl_status")} if isinstance(r2, dict) else r2)
c, b = sadm.get(f"/sales-orders/{SO}")
print("AKHIR:", b.get("number"), b.get("status"), b.get("stage"), "payment", b.get("payment_status"), b.get("paid_total"), "/", grand)
c, j = sales.get(f"/sales-orders/{SO}/journey")
step("journey SO", c, j)
c, inv = fin.get(f"/sales-orders/{SO}/invoices")
step("invoice SO", c, inv)
dump("/tmp/uat_o2c_cont.json")
