fin = Api("finance@kainnusantara.id"); whadm = Api("wh.admin@kainnusantara.id"); mgr = Api("manager@kainnusantara.id")
# Faktur pajak untuk SO-00038
c, b = fin.post("/sales-orders/so_d9aa799376ff/tax-invoice", {"kode_transaksi": "04", "faktur_date": "2026-10-21", "nsfp": ""})
step("finance: terbitkan Faktur Pajak SO-00038", c, {k: b.get(k) for k in ("number", "status", "dpp", "ppn", "ppn_amount", "nsfp")} if isinstance(b, dict) and "number" in b else b, (200, 400, 409, 422))
c, b2 = fin.post("/sales-orders/so_d9aa799376ff/tax-invoice", {"kode_transaksi": "04", "faktur_date": "2026-10-21", "nsfp": ""})
step("CEK: terbitkan ulang (idempoten)", c, {k: b2.get(k) for k in ("number",)} if isinstance(b2, dict) and "number" in b2 else b2, (200, 400, 409))
# multi-SO dalam satu pengiriman: SJ CBD (SO-00041) + SJ QC? -> pakai dua SJ dari SO berbeda yang belum diangkut
c, shp = whadm.get("/logistics/shipments/unassigned")
rows = shp if isinstance(shp, list) else shp.get("items", shp.get("shipments", []))
by_so = {}
for s in rows:
    by_so.setdefault(s.get("order_id"), s)
two = list(by_so.values())[:2]
print("SJ belum diangkut:", [(s.get("shipment_no"), s.get("order_number")) for s in rows][:8])
if len(two) == 2:
    c, b = whadm.post("/logistics/deliveries", {"shipment_ids": [s["id"] for s in two], "mode": "own_fleet", "vehicle_plate": "D 9 UAT", "driver_name": "Kurniawan"})
    step("CEK: satu pengiriman berisi 2 SO berbeda", c, {k: b.get(k) for k in ("number", "order_ids")} if isinstance(b, dict) and "number" in b else b, (200, 400))
