import json
import kn

# PO baru KSC → kirim ke lokasi Rancamalang
c, po = kn.call("admin", "POST", "/purchase-orders", {
    "supplier_id": "sup_a47057e2dfc2", "ship_to_site_id": "site_c0c8400b0017",
    "items": [{"product_id": "prod_97ef39b63081", "quantity": 300, "unit": "yard", "price": 20000,
               "expected_grade": "A", "qty_rolls": 3}],
    "expected_delivery_date": "2026-11-12", "notes": "B2A audit alur masuk A"}, entity="ent_ksc")
if c == 200:
    print("PO", po.get("id"), po.get("po_number"), po.get("status"), po.get("warehouse_id"), po.get("approval_status"))
    json.dump(po, open("/tmp/b2a/po_a.json", "w"), default=str)
    print(kn.snap("wms_tasks", {"po_id": po["id"]}, ["id", "status", "warehouse_id", "expected_qty", "unit", "entity_id"]))
