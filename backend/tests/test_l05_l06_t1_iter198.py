"""T1 iter 198 — L05 follow-ups (QC notif to qc users, delivery qc_status) + L06 cutting/catalogue API edge cases."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
CUST, ADDR, PROD = "cust_butik_bali", "addr_002", "prod_batik_mega"
REAL_TPL = (DB.products.find_one({"template_id": {"$nin": ["", None]}, "base_unit": "yard"}, {"template_id": 1}) or {}).get("template_id", "ptpl_a2cbc00d355e")


def _login(email, pw="demo1234"):
    DB.login_attempts.delete_many({})
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def created(admin):
    ids = []
    yield ids
    for sid in ids:
        requests.post(f"{BASE}/sales-orders/{sid}/cancel", json={"reason": "TEST T1 iter198 cleanup"}, headers=admin, timeout=60)
        DB.notifications.delete_many({"ref": {"$regex": f"^so_qc:{sid}"}})
        DB.wms_tasks.delete_many({"order_id": sid, "task_subtype": "sample_cut"})


def _so(admin, created, **body):
    payload = {"customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ENT, **body}
    r = requests.post(f"{BASE}/sales-orders", json=payload, headers=admin, timeout=120)
    if r.status_code == 200:
        created.append(r.json()["id"])
    return r


# ── L05: notification to qc.inspect holders, visible via API to qc@ ──
def test_qc_request_notifies_qc_user_via_api(admin, created):
    r = _so(admin, created, qc_request="full",
            items=[{"product_id": PROD, "quantity": 3.0, "unit": "yard", "base_quantity": 3.0}])
    assert r.status_code == 200, r.text[:300]
    so = r.json()
    qc = _login("qc@kainnusantara.id")
    notes = requests.get(f"{BASE}/notifications", headers=qc, timeout=30).json()
    mine = [n for n in notes if n.get("type") == "so_qc_requested" and so["number"] in n.get("title", "")]
    assert len(mine) == 1, [n.get("title") for n in notes[:5]]
    assert mine[0]["link"] == "inspections"
    recips = {n["recipient_user"] for n in DB.notifications.find({"type": "so_qc_requested", "ref": {"$regex": f"^so_qc:{so['id']}#"}})}
    qc_uid = DB.users.find_one({"email": "qc@kainnusantara.id"})["id"]
    assert qc_uid in recips
    # sales (no qc.inspect) must NOT see it
    sales = _login("sales@kainnusantara.id")
    snotes = requests.get(f"{BASE}/notifications", headers=sales, timeout=30).json()
    assert not [n for n in snotes if n.get("type") == "so_qc_requested" and so["number"] in n.get("title", "")]


def test_no_qc_request_no_notification(admin, created):
    r = _so(admin, created, items=[{"product_id": PROD, "quantity": 2.0, "unit": "yard", "base_quantity": 2.0}])
    assert r.status_code == 200, r.text[:300]
    assert DB.notifications.count_documents({"type": "so_qc_requested", "ref": {"$regex": f"^so_qc:{r.json()['id']}"}}) == 0


def test_deliveries_have_qc_status_field(admin):
    rows = requests.get(f"{BASE}/logistics/deliveries", headers=admin, timeout=30).json()
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    if not rows:
        pytest.skip("no deliveries in seed data")
    assert all("qc_status" in x and x["qc_status"] in ("", "required", "passed", "failed") for x in rows)


# ── L06 LN-061: cutting locations & desk ──
def test_cutting_locations_list(admin):
    r = requests.get(f"{BASE}/cutting/locations", headers=admin, timeout=30)
    assert r.status_code == 200
    rows = r.json()
    assert rows and all(set(x["cutting_caps"]) <= {"standard", "hanger", "catalogue"} for x in rows)


def test_cutting_caps_invalid_and_unknown(admin):
    wid = requests.get(f"{BASE}/cutting/locations", headers=admin, timeout=30).json()[0]["id"]
    bad = requests.put(f"{BASE}/cutting/locations/{wid}", json={"caps": ["laser"]}, headers=admin, timeout=30)
    assert bad.status_code == 400
    nf = requests.put(f"{BASE}/cutting/locations/wh_nope_x", json={"caps": ["standard"]}, headers=admin, timeout=30)
    assert nf.status_code == 404


def test_cutting_caps_forbidden_for_sampleadmin_and_sales():
    for email in ("sampleadmin@kainnusantara.id", "sales@kainnusantara.id"):
        h = _login(email)
        r = requests.put(f"{BASE}/cutting/locations/wh_bandung", json={"caps": ["standard"]}, headers=h, timeout=30)
        assert r.status_code == 403, (email, r.status_code)


def test_cutting_desk_queues_shape():
    h = _login("sampleadmin@kainnusantara.id")
    r = requests.get(f"{BASE}/cutting/desk", headers=h, timeout=30)
    assert r.status_code == 200, r.text[:200]
    assert [q["key"] for q in r.json()["queues"]] == ["awaiting_internal", "to_cut", "to_receive", "ready"]


def test_receive_unknown_task_404(admin):
    r = requests.post(f"{BASE}/cutting/tasks/wt_nope/receive", json={}, headers=admin, timeout=30)
    assert r.status_code == 404


# ── L06 LN-060: catalogue validation ──
def test_catalogue_preview_real_template(admin):
    r = requests.get(f"{BASE}/sample-orders/catalogue/preview", params={"template_id": REAL_TPL}, headers=admin, timeout=30)
    assert r.status_code in (200, 409), r.text[:300]
    if r.status_code == 200:
        c = r.json()
        assert c["colors_available"] == len(c["base"]) and all(x["quantity"] == 1.0 for x in c["base"])
        print("real template:", c["colors_total"], c["colors_available"], c.get("soft"), c["total_qty"])


def test_catalogue_preview_unknown_template_404(admin):
    r = requests.get(f"{BASE}/sample-orders/catalogue/preview", params={"template_id": "ptpl_nope"}, headers=admin, timeout=30)
    assert r.status_code == 404


def test_catalogue_on_regular_order_rejected(admin, created):
    r = _so(admin, created, order_type="regular", items=[], catalogue={"template_id": REAL_TPL, "soft_product_id": ""})
    assert r.status_code == 400


def test_catalogue_kind_without_catalogue_rejected(admin, created):
    r = _so(admin, created, order_type="sample", sample_billing="free",
            items=[{"product_id": PROD, "quantity": 1.0, "unit": "yard", "base_quantity": 1.0, "is_sample": True, "sample_kind": "catalogue"}])
    assert r.status_code == 400


def test_unknown_sample_kind_rejected(admin, created):
    r = _so(admin, created, order_type="sample", sample_billing="free",
            items=[{"product_id": PROD, "quantity": 1.0, "unit": "yard", "base_quantity": 1.0, "is_sample": True, "sample_kind": "xxl"}])
    assert r.status_code == 400, r.text[:200]


def test_soft_change_on_non_catalogue_rejected(admin, created):
    r = _so(admin, created, order_type="sample", sample_billing="free",
            items=[{"product_id": PROD, "quantity": 1.0, "unit": "yard", "base_quantity": 1.0, "is_sample": True, "sample_kind": "standard"}])
    assert r.status_code == 200, r.text[:300]
    s = requests.post(f"{BASE}/sample-orders/{r.json()['id']}/catalogue/soft", json={"product_id": PROD}, headers=admin, timeout=30)
    assert s.status_code == 400


def test_real_catalogue_soft_flow(admin, created):
    prev = requests.get(f"{BASE}/sample-orders/catalogue/preview", params={"template_id": REAL_TPL}, headers=admin, timeout=30)
    if prev.status_code != 200 or len(prev.json()["base"]) < 2:
        pytest.skip("real template has <2 available colors")
    base = prev.json()["base"]
    r = _so(admin, created, order_type="sample", sample_billing="paid", items=[],
            catalogue={"template_id": REAL_TPL, "soft_product_id": base[0]["product_id"]})
    if r.status_code == 409:
        pytest.skip(f"soft stock short: {r.text[:120]}")
    assert r.status_code == 200, r.text[:300]
    so = r.json()
    assert abs(sum(i["quantity"] for i in so["items"]) - (len(base) + 2)) < 1e-6
    bad = requests.post(f"{BASE}/sample-orders/{so['id']}/catalogue/soft", json={"product_id": PROD}, headers=admin, timeout=30)
    assert bad.status_code == 400
    ok = requests.post(f"{BASE}/sample-orders/{so['id']}/catalogue/soft", json={"product_id": base[1]["product_id"]}, headers=admin, timeout=30)
    assert ok.status_code in (200, 409), ok.text[:300]
    if ok.status_code == 200:
        q = {i["product_id"]: i["quantity"] for i in ok.json()["items"]}
        assert q[base[0]["product_id"]] == 1.0 and q[base[1]["product_id"]] == 3.0
        assert ok.json()["catalogue"]["base"] == so["catalogue"]["base"]
        assert ok.json()["grand_total"] > 0
