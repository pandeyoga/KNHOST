# Cabang STOK KURANG: SO Sukacita untuk artikel yang stoknya hanya ada di CST -> backorder
# -> rencana pemenuhan Admin Sales (sebagian transfer PT lain + sebagian PO supplier) -> dokumen tertaut.
P = "prod_88616a316bcc"   # ALICE KNIT (94139 - 45) 14 A — stok hanya CST
sales = Api("sales@kainnusantara.id"); sadm = Api("salesadmin@kainnusantara.id"); mgr = Api("manager@kainnusantara.id")
c, b = sales.post("/sales-orders", {"customer_id": "cust_toko_kain", "shipping_address_id": "", "entity_id": "ent_ksc",
                                    "items": [{"product_id": P, "quantity": 100, "unit": "kg"}], "payment_term_code": "NET30"})
step("CEK: SO tanpa izin backorder saat stok kosong", c, {k: b.get(k) for k in ("number", "status")} if isinstance(b, dict) and "status" in b else b, (200, 400, 409))
c, so = sales.post("/sales-orders", {"customer_id": "cust_toko_kain", "shipping_address_id": "", "entity_id": "ent_ksc",
                                     "items": [{"product_id": P, "quantity": 100, "unit": "kg"}], "payment_term_code": "NET30",
                                     "allow_backorder": True})
so = need("sales: SO 100 kg allow_backorder", c, so)
SO = so["id"]
print("SO", so["number"], so["status"], so.get("stage"), so.get("sub_status"), "backorders", [(x["backorder_qty"]) for x in so.get("backorders", [])], "grand", so.get("grand_total"))
c, b = sadm.post(f"/sales-orders/{SO}/verify", {"note": "UAT"})
step("sadm: verifikasi SO backorder", c, {"v": (b.get("verification") or {}).get("status")} if isinstance(b, dict) and "verification" in b else b)
c, opt = sadm.get(f"/sales-admin/orders/{SO}/fulfillment-plan")
step("sadm: opsi rencana pemenuhan", c, short(opt, 1500))
c, fo = sadm.get(f"/sales-admin/orders/{SO}/fulfillment")
step("sadm: opsi keputusan pemenuhan", c, short(fo, 1200))
# rencana: 60 transfer CST + 40 PO supplier
c, b = sadm.post(f"/sales-admin/orders/{SO}/fulfillment-plan", {"lines": [{"product_id": P, "interco": [{"entity_id": "ent_a602991f8094", "qty": 70}],
                                                                           "reorder_qty": 40}], "note": "UAT lebih dari kekurangan"})
step("NEG rencana melebihi kekurangan (70+40>100)", c, b, (400,))
c, b = sadm.post(f"/sales-admin/orders/{SO}/fulfillment-plan", {"lines": [{"product_id": P, "interco": [{"entity_id": "ent_a602991f8094", "qty": 60}],
                                                                           "reorder_qty": 40}], "note": "UAT 60 CST + 40 supplier"})
step("sadm: jalankan rencana 60 CST + 40 PO", c, short(b, 1500), (200, 400))
c, so2 = sadm.get(f"/sales-orders/{SO}")
print("SO setelah rencana:", so2.get("status"), so2.get("stage"), so2.get("sub_status"), "decision", short(so2.get("fulfillment_decision"), 600))
c, b = sadm.post(f"/sales-admin/orders/{SO}/fulfillment-plan", {"lines": [{"product_id": P, "reorder_qty": 40}], "note": "UAT ulang"})
step("CEK: jalankan ulang rencana yang sama (tidak boleh dokumen ganda)", c, short(b, 600), (200, 400, 409))
c, pins = sales.get("/internal-requests")
pl = pins if isinstance(pins, list) else pins.get("items", [])
print("PIN terkait:", [(p.get("number"), p.get("status"), p.get("source_order_id")) for p in pl if p.get("source_order_id") == SO])
c, prs = mgr.get("/purchase-requisitions")
prl = prs if isinstance(prs, list) else prs.get("items", [])
print("PR terkait:", [(p.get("number"), p.get("status"), short(p.get("source"), 120)) for p in prl if SO in short(p, 5000)][:5])
print("SO_SHORT", SO)
dump("/tmp/uat_short.json")
