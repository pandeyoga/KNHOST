S = "so_c92387a4c25b"
wh = Api("warehouse@kainnusantara.id"); sa = Api("sampleadmin@kainnusantara.id"); whadm = Api("wh.admin@kainnusantara.id")
c, tasks = wh.get("/outbound/tasks"); t = [x for x in tasks if x.get("order_id") == S][0]
for who, a in (("sampleadmin", sa), ("whadmin", whadm), ("warehouse", wh)):
    c, b = a.post(f"/cutting/tasks/{t['id']}/receive", {"note": "UAT diterima Admin Cutting"})
    if step(f"{who}: Admin Cutting terima hasil potong", c, short(b, 200), (200, 400, 403, 404, 422)) and c == 200:
        break
c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
if c != 200 and "RFID" in short(b):
    whadm.post(f"/outbound/so/{S}/loading-check/override", {"reason": "UAT tanpa RFID - manual"}); c, b = wh.post(f"/outbound/tasks/{t['id']}/dispatch")
step("gudang: kirim sample", c, {"sj": (b.get("shipment") or {}).get("shipment_no")} if isinstance(b, dict) and "shipment" in b else b, (200, 400, 409))
c, so = sa.get(f"/sales-orders/{S}"); print("SOS:", so.get("status"), so.get("payment_status"))
