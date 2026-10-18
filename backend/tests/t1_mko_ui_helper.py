"""T1 helper: create a cancelled MKO (ent_ksc) with material at partner for UI partial-return test."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import requests
import test_p05_acceptance_acc31_33_34 as P

B = f"{P.BASE}/api"
adm = P._login("admin@kainnusantara.id", "demo12345")
# output template must be 'makloon' for create (restored by restore_local_demo.sh)
out = P.DB.products.find_one({"id": P._tpl()["steps"][0]["output_product_id"]}, {"_id": 0, "template_id": 1})
P.DB.product_templates.update_one({"id": out["template_id"]}, {"$set": {"restock_source": {"mode": "makloon", "note": "TEST_T1"}}})
mko = P._create(adm, 60, "T1-UI-PARTIAL")
assert requests.post(f"{B}/makloon-orders/{mko['id']}/issue", json={"step_seq": 1, "doc_uom": "yard", "doc_qty": 60},
                     headers=adm, timeout=60).status_code == 200
assert requests.post(f"{B}/makloon-orders/{mko['id']}/cancel", json={"reason": "TEST_T1 batal UI"},
                     headers=adm, timeout=60).status_code == 200
rolls = requests.get(f"{B}/makloon-orders/{mko['id']}/steps/1/partner-rolls", headers=adm, timeout=30).json()["rolls"]
print("MKO", mko["id"], mko.get("mko_number"), "ROLLS", [(r["id"], r["roll_no"], r["length_remaining"]) for r in rolls])
