"""Uji cepat override SO (dijalankan manual). Membuat SO uji lalu membatalkannya di akhir."""
import json
import os
import sys

import requests

API = os.environ.get("API", "http://localhost:8001/api")


def login(email, pw="demo1234"):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": pw})
    r.raise_for_status()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    s.headers["X-Entity-Id"] = "ent_ksc"
    return s


sales = login("sales@kainnusantara.id")
adm = login("salesadmin@kainnusantara.id")
fin = login("finance@kainnusantara.id")

so = sales.post(f"{API}/sales-orders", json={
    "customer_id": "cust_toko_kain", "shipping_address_id": "addr_001", "entity_id": "ent_ksc",
    "allow_backorder": True, "notes": "TEST_override",
    "items": [{"product_id": "prod_lurik_classic", "quantity": 20, "unit": "meter"},
              {"product_id": "prod_batik_mega", "quantity": 10, "unit": "meter"}]})
print("create", so.status_code, so.text[:300] if so.status_code >= 300 else "")
so = so.json()
oid = so["id"]
print("SO", so["number"], so["status"], so["grand_total"])

print("sales override (expect 403):", sales.post(f"{API}/sales-orders/{oid}/override", json={"note": "x"}).status_code)
print("ctx", adm.get(f"{API}/sales-orders/{oid}/override-context").json().get("locked_reason"))

r = adm.post(f"{API}/sales-orders/{oid}/override", json={
    "note": "TEST override qty & harga",
    "header": {"delivery_date": "2030-01-15", "notes": "diubah admin"},
    "lines": [{"product_id": "prod_lurik_classic", "quantity": 30},
              {"product_id": "prod_batik_mega", "remove": True},
              {"product_id": "prod_lurik_classic", "price": 1000}],
    "add_items": [{"product_id": "prod_tenun_ikat", "quantity": 5}]})
print("override", r.status_code, r.text[:400] if r.status_code >= 300 else "")
if r.ok:
    d = r.json()
    o = d["order"]
    print("changes", json.dumps(d["changes"])[:500])
    print("items", [(i["product_id"], i["quantity"], i.get("reserved_qty"), i.get("backorder_qty"), i["price"]) for i in o["items"]])
    print("alloc", [(a["product_id"], a["quantity"]) for a in o["allocations"]], "total", o["grand_total"], o.get("delivery_date"))
    pa = d["price_amendment"]
    print("price amd", pa and (pa["number"], pa["status"], pa.get("approval_permission")))
    if pa:
        print("sales decide (expect 403):", sales.post(f"{API}/amendments/{pa['id']}/decision", json={"action": "approve"}).status_code)
        rr = fin.post(f"{API}/amendments/{pa['id']}/decision", json={"action": "approve", "note": "ok"})
        print("finance decide", rr.status_code, rr.json().get("status") if rr.ok else rr.text[:300])
        o2 = adm.get(f"{API}/sales-orders/{oid}").json()
        print("after approve", [(i["product_id"], i["price"]) for i in o2["items"]], o2["grand_total"])
    trail = adm.get(f"{API}/amendments/doc/sales_order/{oid}").json()
    print("trail", [(a["number"], a["reason_label"], a["status"]) for a in trail["amendments"]])

c = adm.post(f"{API}/sales-orders/{oid}/cancel", json={"reason": "TEST cleanup"})
print("cancel", c.status_code, c.json().get("status"), c.json().get("cancel_reason"))
sys.exit(0)
