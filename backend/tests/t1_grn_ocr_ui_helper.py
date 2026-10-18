"""T1 helper: prepare GRN OCR UI test. Usage: prep | restore <json-prev>"""
import json, os, sys
sys.path.insert(0, "/app/backend/tests")
import requests
from pymongo import MongoClient
from test_l04_ln040_real_ocr import sj_image

B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
tok = requests.post(f"{B}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}).json()["token"]
H = {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}
KEYS = ("receiving.ocr_enabled", "receiving.ocr_extract_packing_list", "receiving.ocr_second_reader_mode")


def put(vals):
    r = requests.put(f"{B}/config/values", headers=H, json={"items": [
        {"key": k, "value": v, "scope_type": "global", "reason": "TEST_ T1 iter192"} for k, v in vals.items()]})
    print("PUT", r.status_code, r.text[:150])


if sys.argv[1] == "prep":
    items = requests.get(f"{B}/config/effective", headers=H, params={"group": "penerimaan"}).json()["items"]
    prev = {i["key"]: i.get("value") for i in items if i["key"] in KEYS}
    print("PREV", json.dumps(prev))
    put({"receiving.ocr_enabled": True, "receiving.ocr_extract_packing_list": True, "receiving.ocr_second_reader_mode": "off"})
    wh_user = DB.users.find_one({"email": "warehouse@kainnusantara.id"}, {"_id": 0, "warehouse_ids": 1, "warehouse_id": 1, "role": 1})
    print("WH USER", wh_user)
    t = DB.wms_tasks.find_one({"flow_type": "inbound", "entity_id": "ent_ksc", "po_id": {"$gt": ""},
                               "status": {"$in": ["waiting_goods", "receiving"]}}, {"_id": 0})
    po = DB.purchase_orders.find_one({"id": t["po_id"]}, {"_id": 0, "po_number": 1, "supplier_id": 1, "supplier_name": 1})
    print("TASK", t["id"], t.get("warehouse_id"), t.get("product_name"), t.get("unit"), "PO", t["po_id"], po)
    open("/tmp/sj_t1.jpg", "wb").write(sj_image(po["po_number"], t["product_name"], "SJ/AK/T1ABC", smudge_seq=7))
    print("image written")
else:
    put(json.loads(sys.argv[2]))
