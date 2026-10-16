"""T1 helper (not a test): create cancelled MKO with 60 yd at partner for L04 FE test; prints MKO id + rolls."""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
from test_p05_acceptance_acc31_33_34 import _create, BASE, DB, _tpl  # noqa: E402
out = DB.products.find_one({"id": _tpl()["steps"][0]["output_product_id"]}, {"_id": 0, "template_id": 1})
DB.product_templates.update_one({"id": out["template_id"]}, {"$set": {"restock_source": {"mode": "makloon", "note": "TEST_T1"}}})  # restored by restore_local_demo.sh

r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}
mko = _create(h, 60, "T1-FE-L04")
print(requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1, "doc_uom": "yard", "doc_qty": 60}, headers=h, timeout=60).status_code)
print(requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_T1 batal FE"}, headers=h, timeout=60).status_code)
rolls = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=h, timeout=30).json()["rolls"]
print("MKO", mko["id"], mko.get("mko_number"), mko.get("entity_id"))
for x in rolls:
    print("ROLL", x["id"], x.get("roll_no"), x["length_remaining"])
