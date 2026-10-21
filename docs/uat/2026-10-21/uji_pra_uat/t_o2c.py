# Skenario O2C-1: SO normal (stok cukup) -> verifikasi -> approval -> confirm -> pick -> loading check
# -> dispatch SJ -> pengiriman (armada) -> POD -> diterima -> pembayaran sampai lunas.
import os
PID = os.environ.get("PID", "prod_c854e5856251")   # DENIM TENCEL TAUPE A (Jakarta)
CUST = "cust_toko_kain"
TERM = os.environ.get("TERM_CODE", "NET30")
QTY = float(os.environ.get("QTY", "150"))

sales = Api("sales@kainnusantara.id")
sadm = Api("salesadmin@kainnusantara.id")
mgr = Api("manager@kainnusantara.id")
wh = Api("warehouse@kainnusantara.id")
fin = Api("finance@kainnusantara.id")

c, cust = sales.get(f"/customers/{CUST}")
addr = (cust.get("addresses") or [{}])[0] if isinstance(cust, dict) else {}
print("alamat:", short(addr, 300))

# 0. Pratinjau alokasi
c, b = sales.post("/sales-orders/preview-allocation", {"items": [{"product_id": PID, "quantity": QTY, "unit": "yard"}],
                                                        "entity_id": "ent_ksc", "customer_id": CUST})
step("preview-allocation", c, b)

# 1. Sales buat SO
RESUME = os.environ.get("RESUME", "")
payload = {"customer_id": CUST, "shipping_address_id": addr.get("id", ""), "entity_id": "ent_ksc",
           "items": [{"product_id": PID, "quantity": QTY, "unit": "yard"}],
           "payment_term_code": TERM, "qc_request": "none", "fulfillment_method": "kirim",
           "confirm_mixed_lot": True}
if RESUME:
    c, so = sadm.get(f"/sales-orders/{RESUME}")
else:
    c, so = sales.post("/sales-orders", payload)
so = need("sales: buat SO", c, so)
SO = so["id"]
print("SO", so["number"], so["status"], so.get("stage"), so.get("sub_status"), "grand", so.get("grand_total"),
      "ppn", so.get("ppn_amount"), "pending_appr", [p["type"] for p in so.get("pending_approvals", [])],
      "verif?", so.get("verification"))
print("items:", [(i.get("quantity"), i.get("unit"), i.get("price"), i.get("reserved_qty"), i.get("backorder_qty"), i.get("price_source")) for i in so["items"]])

if not RESUME:
  pass
# 1b. Sales mencoba approve sendiri (negatif)
c, b = sales.post(f"/sales-orders/{SO}/approve")
step("NEG sales approve sendiri ditolak", c, b, (403,))
# 1c. Confirm sebelum verifikasi (negatif)
c, b = sadm.post(f"/sales-orders/{SO}/confirm")
step("NEG confirm sebelum verifikasi ditolak", c, b, (409, 403))

# 2. Admin Sales verifikasi
c, b = sadm.get(f"/sales-orders/{SO}/verification")
step("sadm: pratinjau verifikasi", c, {k: b.get(k) for k in ("ready", "blocking_gaps", "warnings")} if isinstance(b, dict) else b)
c, b = sadm.post(f"/sales-orders/{SO}/verify", {"note": "UAT verifikasi"})
step("sadm: verifikasi", c, b)

# 3. Submit for approval
c, b = sadm.post(f"/sales-orders/{SO}/submit-for-approval")
step("sadm: ajukan persetujuan", c, {k: b.get(k) for k in ("status", "stage", "sub_status", "required_approval_role")} if isinstance(b, dict) else b)
# 3b Admin Sales approve? (harus ditolak bila butuh manager)
c, b = sadm.post(f"/sales-orders/{SO}/approve")
step("cek: admin sales approve", c, {k: b.get(k) for k in ("status",)} if isinstance(b, dict) and "status" in b else b, (200, 403, 409))
c, b = mgr.post(f"/sales-orders/{SO}/approve")
step("mgr: setujui SO", c, {k: b.get(k) for k in ("status", "stage", "sub_status")} if isinstance(b, dict) else b, (200,))

# 4. Confirm -> tugas gudang
c, b = sadm.post(f"/sales-orders/{SO}/confirm")
step("sadm: confirm", c, {k: b.get(k) for k in ("status", "stage", "sub_status")} if isinstance(b, dict) else b)
c, b = sadm.post(f"/sales-orders/{SO}/confirm")
step("cek: confirm ulang idempoten/ditolak", c, {k: b.get(k) for k in ("status",)} if isinstance(b, dict) and "status" in b else b, (200, 400, 409))

c, tasks = wh.get("/outbound/tasks", params={"order_id": SO})
tl = tasks if isinstance(tasks, list) else tasks.get("items", tasks.get("tasks", []))
tl = [t for t in tl if t.get("order_id") == SO]
step("wh: daftar tugas outbound SO", c, [(t["id"], t.get("status"), t.get("quantity"), t.get("warehouse_id")) for t in tl])

# 5. Pick per roll yang dialokasikan
c, sod = sales.get(f"/sales-orders/{SO}")
allocs = (sadm.get(f"/sales-orders/{SO}")[1] or {}).get("allocations", [])
print("alokasi:", [(a.get("warehouse_id"), a.get("quantity"), len(a.get("rolls") or a.get("roll_ids") or [])) for a in allocs])
import json
rolls = []
for a in allocs:
    for r in (a.get("rolls") or []):
        rolls.append((r.get("roll_id") or r.get("id"), float(r.get("length") or r.get("quantity") or 0)))
print("roll alokasi:", rolls[:10])
for t in tl:
    for rid, q in rolls:
        c, b = wh.post(f"/outbound/tasks/{t['id']}/scan-pick", params={"actual_qty": q, "roll_id": rid})
        step(f"wh: scan-pick {rid} {q}", c, {k: b.get(k) for k in ("status", "picked_qty", "quantity")} if isinstance(b, dict) else b)

c, b = sales.get(f"/sales-orders/{SO}")
print("SO setelah pick:", b.get("status"), b.get("stage"), b.get("sub_status"))

# 6. Loading check (manual/override bila RFID tidak ada)
c, b = wh.get(f"/outbound/so/{SO}/loading-check")
step("wh: status loading check", c, b, (200,))
# 7. Dispatch
for t in tl:
    c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
    ok = step("wh: dispatch -> SJ", c, {"task": (b.get("task") or {}).get("status"), "sj": (b.get("shipment") or {}).get("shipment_no"), "gl": (b.get("shipment") or {}).get("gl_status")} if isinstance(b, dict) and "task" in b else b, (200,))
    if not ok and c in (409, 400):
        c2, b2 = Api("wh.admin@kainnusantara.id").post(f"/outbound/so/{SO}/loading-check/override", {"reason": "UAT tanpa perangkat RFID - validasi manual"})
        step("whadmin: override loading check", c2, b2)
        c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
        step("wh: dispatch ulang -> SJ", c, {"task": (b.get("task") or {}).get("status"), "sj": (b.get("shipment") or {}).get("shipment_no"), "gl": (b.get("shipment") or {}).get("gl_status")} if isinstance(b, dict) and "task" in b else b)
c, b = sales.get(f"/sales-orders/{SO}")
print("SO setelah dispatch:", b.get("status"), b.get("stage"), "payment_status", b.get("payment_status"))
c, shp = wh.get("/shipments", params={"order_id": SO})
sl = shp if isinstance(shp, list) else shp.get("items", [])
sl = [s for s in sl if s.get("order_id") == SO]
step("wh: SJ untuk SO", c, [(s["shipment_no"], s.get("qty"), s.get("logistics_status")) for s in sl])

# 8. Logistik: buat pengiriman armada sendiri
whadm = Api("wh.admin@kainnusantara.id")
c, b = whadm.post("/logistics/deliveries", {"shipment_ids": [s["id"] for s in sl], "mode": "own_fleet",
                                             "vehicle_plate": "D 1234 UAT", "driver_name": "Kurniawan",
                                             "destination": addr.get("city", ""), "notes": "UAT O2C"})
dv = need("logistik: buat pengiriman", c, b)
DV = dv["id"]
print("delivery", dv.get("number"), dv.get("status"))
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "loaded"})
step("NEG dimuat tanpa foto ditolak", c, b, (400,))
png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000000000200015e2f3a8d0000000049454e44ae426082")
c, b = whadm._do("POST", f"/logistics/deliveries/{DV}/photos", data={"kind": "load", "note": "muat"}, files={"file": ("muat.png", png, "image/png")})
step("logistik: foto muat", c, b)
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "loaded"})
step("logistik: dimuat", c, {"status": b.get("status")} if isinstance(b, dict) else b)
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "in_transit"})
step("logistik: berangkat", c, {"status": b.get("status")} if isinstance(b, dict) else b)
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "delivered", "receiver_name": "Pak Hendra"})
step("NEG terkirim tanpa POD ditolak", c, b, (400,))
c, b = whadm._do("POST", f"/logistics/deliveries/{DV}/photos", data={"kind": "pod", "note": "pod"}, files={"file": ("pod.png", png, "image/png")})
step("logistik: foto POD", c, b)
c, b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to": "delivered", "receiver_name": "Pak Hendra"})
step("logistik: terkirim (POD)", c, {"status": b.get("status")} if isinstance(b, dict) else b)
c, b = sales.get(f"/sales-orders/{SO}")
print("SO setelah POD logistik:", b.get("status"), b.get("stage"))

# 9. Tandai diterima (SO done)
c, b = sales.post(f"/sales-orders/{SO}/mark-delivered")
step("NEG sales tandai diterima ditolak", c, b, (403,))
c, b = sadm.post(f"/sales-orders/{SO}/mark-delivered")
step("sadm: tandai diterima customer", c, {k: b.get(k) for k in ("status", "stage")} if isinstance(b, dict) else b)

# 10. Finance: penerimaan pembayaran
c, oo = fin.get("/ar-receipts/open-orders", params={"customer_id": CUST})
row = next((o for o in (oo if isinstance(oo, list) else []) if o.get("order_id") == SO or o.get("id") == SO), None)
step("fin: SO muncul di order terbuka", c, row)
c, b = sadm.get(f"/sales-orders/{SO}")
grand = float(b.get("grand_total") or 0)
half = round(grand / 2, 2)
c, r1 = fin.post("/ar-receipts", {"customer_id": CUST, "amount": half, "method": "transfer", "entity_id": "ent_ksc",
                                  "notes": "UAT cicilan 1", "allocations": [{"order_id": SO, "amount": half}]})
step("fin: terima 50%", c, {k: r1.get(k) for k in ("number", "amount", "status", "gl_status")} if isinstance(r1, dict) else r1)
c, b = sadm.get(f"/sales-orders/{SO}")
print("setelah 50%:", b.get("payment_status"), b.get("paid_total"))
rest = round(grand - half, 2)
c, r2 = fin.post("/ar-receipts", {"customer_id": CUST, "amount": rest, "method": "transfer", "entity_id": "ent_ksc",
                                  "notes": "UAT pelunasan", "allocations": [{"order_id": SO, "amount": rest}]})
step("fin: pelunasan", c, {k: r2.get(k) for k in ("number", "amount", "status", "gl_status")} if isinstance(r2, dict) else r2)
c, b = sadm.get(f"/sales-orders/{SO}")
print("AKHIR:", b.get("number"), b.get("status"), b.get("stage"), "payment", b.get("payment_status"), b.get("paid_total"), "/", grand)
c, j = sales.get(f"/sales-orders/{SO}/journey")
step("journey SO", c, j, (200,))
c, inv = fin.get(f"/sales-orders/{SO}/invoices")
step("invoice SO", c, inv)
dump("/tmp/uat_o2c.json")
print("SO_ID", SO)
