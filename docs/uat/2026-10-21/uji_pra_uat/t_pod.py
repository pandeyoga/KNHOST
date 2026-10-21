SO="so_d9aa799376ff"
whadm = Api("wh.admin@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); sales=Api("sales@kainnusantara.id"); drv=Api("driver@kainnusantara.id")
png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000000000200015e2f3a8d0000000049454e44ae426082")
c, shp = whadm.get("/shipments", params={"order_id": SO})
sl = [s for s in shp if s.get("order_id")==SO and not s.get("logistics_status")]
print("SJ belum dikirim:", [(s["shipment_no"], s.get("qty")) for s in sl])
c, b = whadm.post("/logistics/deliveries", {"shipment_ids":[s["id"] for s in sl], "mode":"expedition", "courier_name":"JNE Cargo", "shipping_cost": 75000})
dv = need("logistik: pengiriman ekspedisi", c, b); DV=dv["id"]
c,b = whadm._do("POST", f"/logistics/deliveries/{DV}/photos", data={"kind":"load"}, files={"file":("m.png",png,"image/png")})
c,b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to":"loaded"}); step("-> loaded", c, {"s":b.get("status")} if isinstance(b,dict) else b)
c,b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to":"in_transit"}); step("NEG berangkat tanpa resi", c, b, (400,))
c,b = whadm._do("PATCH", f"/logistics/deliveries/{DV}", json={"tracking_no":"JNE123UAT"}); step("isi resi", c, {"t":b.get("tracking_no")} if isinstance(b,dict) else b)
c,b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to":"in_transit"}); step("-> in_transit", c, {"s":b.get("status")} if isinstance(b,dict) else b)
c,b = whadm._do("POST", f"/logistics/deliveries/{DV}/photos", data={"kind":"pod"}, files={"file":("p.png",png,"image/png")})
c,b = whadm.post(f"/logistics/deliveries/{DV}/transition", {"to":"delivered","receiver_name":"Pak Hendra"}); step("-> delivered", c, {"s":b.get("status")} if isinstance(b,dict) else b)
c, so = sales.get(f"/sales-orders/{SO}"); print("SO setelah semua SJ POD:", so.get("status"), so.get("stage"))
c, b = sadm.post(f"/sales-orders/{SO}/mark-delivered"); step("sadm: tandai diterima", c, {k:b.get(k) for k in ("status","stage")} if isinstance(b,dict) and "status" in b else b)
c, so = sales.get(f"/sales-orders/{SO}"); print("SO akhir:", so.get("status"), so.get("stage"), so.get("payment_status"))
c, j = sales.get(f"/sales-orders/{SO}/journey"); print(short(j, 2500))
