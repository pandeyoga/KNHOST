# L01 UI helper: create cancelled MKO with material still at partner (for MakloonReturnMaterial UI test)
import requests
from tests.test_p05_acceptance_acc31_33_34 import BASE, DB, _create, _login, _tpl

adm = _login("admin@kainnusantara.id", "demo12345")
out = DB.products.find_one({"id": _tpl()["steps"][0]["output_product_id"]}, {"_id": 0, "template_id": 1})
DB.product_templates.update_one({"id": out["template_id"]}, {"$set": {"restock_source": {"mode": "makloon", "note": "TEST_L01_UI"}}})
mko = _create(adm, 30, "TEST_L01_UI susut")
r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/issue", json={"step_seq": 1}, headers=adm, timeout=60)
print("issue", r.status_code)
r = requests.post(f"{BASE}/api/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_L01_UI batal"}, headers=adm, timeout=60)
print("cancel", r.status_code)
d = requests.get(f"{BASE}/api/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=adm, timeout=30).json()
print("MKO", mko["id"], mko["mko_number"], mko.get("entity_id"), "tol", d.get("tolerance_pct"), "rolls", [x["id"] for x in d["rolls"]][:5])
