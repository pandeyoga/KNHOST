"""G3 Fase 03 — uji live V3-PO-01/02/03 (tugas selisih PO, amend qty→received, close setelah approve).

Jalankan: cd /app && REACT_APP_BACKEND_URL=https://internal-pricing.preview.emergentagent.com \
    python -m pytest backend/tests/test_g3_phase03b_live.py -q -n 0
"""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PO_ID = "po_TEST_variance01"
ENT = "ent_ksc"

if not BASE:
    pytest.skip("REACT_APP_BACKEND_URL kosong", allow_module_level=True)


def _login(email: str, pwd: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": email, "password": pwd}, timeout=20)
    assert r.status_code == 200, (email, r.status_code, r.text)
    s.headers.update({"X-Entity-Id": ENT, "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture(scope="module")
def manager():
    return _login("manager@kainnusantara.id", "demo1234")


@pytest.fixture(scope="module")
def md():
    return _login("md@kainnusantara.id", "demo1234")


def _get_po(sess: requests.Session) -> dict:
    r = sess.get(f"{BASE}/api/purchase-orders/{PO_ID}", timeout=20)
    assert r.status_code == 200, r.text
    return r.json()


def test_po_detail_and_variance_task_has_line_key(admin):
    po = _get_po(admin)
    assert po["id"] == PO_ID
    assert po["items"][0]["received_qty"] == 60
    r = admin.get(f"{BASE}/api/po-variance-tasks", params={"po_id": PO_ID, "status": "open"}, timeout=20)
    assert r.status_code == 200, r.text
    tasks = r.json()
    assert tasks, "tugas selisih PO belum terbuka — jalankan seed_test_po_variance.py"
    t = tasks[0]
    assert t.get("line_key"), f"line_key wajib pada tugas (V3-PO-01): {t}"
    assert t["status"] == "open"


def test_po_list_loads(admin):
    r = admin.get(f"{BASE}/api/purchase-orders", params={"entity_id": ENT, "page": 1, "page_size": 5}, timeout=30)
    assert r.status_code == 200, r.text


def test_decide_amend_moves_task_to_pending_amendment(admin):
    tasks = admin.get(f"{BASE}/api/po-variance-tasks", params={"po_id": PO_ID, "status": "open"}, timeout=20).json()
    if not tasks:
        # mungkin sudah diputus di run sebelumnya → cek pending_amendment
        pa = admin.get(f"{BASE}/api/po-variance-tasks", params={"po_id": PO_ID, "status": "pending_amendment"}, timeout=20).json()
        assert pa, "Tidak ada tugas open maupun pending_amendment"
        return
    tid = tasks[0]["id"]
    r = admin.post(f"{BASE}/api/po-variance-tasks/{tid}/decide",
                   json={"decision": "amend", "reason": "TEST_ amandemen qty ke penerimaan"}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "pending_amendment", body


def _amend_payload(po: dict, new_qty: float) -> dict:
    old = po["items"][0]
    item = {
        "product_id": old["product_id"],
        "quantity": new_qty,
        "unit": old.get("unit", "meter"),
        "price": float(old.get("price", 0) or 0),
        "discount_percent": float(old.get("discount_percent", 0) or 0),
        "expected_grade": old.get("expected_grade", ""),
    }
    return {"reason": "TEST_ amandemen uji V3-PO-02", "items": [item]}


def test_amend_qty_above_received_still_rejected(manager):
    po = _get_po(manager)
    r = manager.post(f"{BASE}/api/purchase-orders/{PO_ID}/amend",
                     json=_amend_payload(po, 70), timeout=30)
    # qty 70 > received 60 tapi ≠ received → masih terkunci (harga/satuan/diskon tidak diubah, tetapi qty di luar received dilarang).
    assert r.status_code == 400, f"qty 70 harus 400, dapat {r.status_code}: {r.text}"
    assert "terkunci" in r.text.lower() or "qty" in r.text.lower()


def test_amend_qty_equal_received_accepted(manager):
    po = _get_po(manager)
    if po.get("status") == "waiting_approval":
        pytest.skip("PO sudah dalam amendment waiting_approval dari run sebelumnya")
    r = manager.post(f"{BASE}/api/purchase-orders/{PO_ID}/amend",
                     json=_amend_payload(po, 60), timeout=60)
    assert r.status_code == 200, f"qty=60 (=received) harus diterima (V3-PO-02): {r.status_code} {r.text}"
    po2 = _get_po(manager)
    assert po2["items"][0]["quantity"] == 60
    # Setelah amend → needs re-approval
    assert po2.get("status") in {"waiting_approval", "pending", "receiving", "partial"}, po2.get("status")


def test_task_still_pending_amendment_before_approval(admin):
    po = _get_po(admin)
    if po.get("status") != "waiting_approval":
        pytest.skip("PO bukan waiting_approval")
    pa = admin.get(f"{BASE}/api/po-variance-tasks",
                   params={"po_id": PO_ID, "status": "pending_amendment"}, timeout=20).json()
    assert pa, "Tugas harus TETAP pending_amendment selama PO waiting_approval (V3-PO-03)"


def _approve_as(sess: requests.Session) -> requests.Response:
    return sess.post(f"{BASE}/api/purchase-orders/{PO_ID}/approve",
                     json={"note": "TEST_ approve V3-PO-03"}, timeout=60)


def test_approve_and_task_closed(manager, md, admin):
    po = _get_po(admin)
    if po.get("status") not in {"waiting_approval"}:
        pytest.skip("PO tidak dalam waiting_approval")
    # Seed dibuat oleh "TEST_seed" (bukan manager/md/admin) → SoD aman untuk semuanya.
    # Coba manager dulu, kalau 403 pakai md atau admin sebagai next approver.
    for sess, who in ((manager, "manager"), (md, "md"), (admin, "admin")):
        r = _approve_as(sess)
        if r.status_code == 200:
            break
    else:
        pytest.fail(f"Tidak ada approver yang berhasil: last={r.status_code} {r.text}")
    # Approval mungkin bertahap; lakukan loop sampai status keluar dari waiting_approval
    for sess in (md, admin, manager):
        p = _get_po(sess)
        if p.get("status") not in {"waiting_approval"}:
            break
        _approve_as(sess)
    final = _get_po(admin)
    assert final.get("status") not in {"waiting_approval"}, f"PO masih waiting_approval: {final.get('status')}"
    # Tugas pending_amendment → decided (V3-PO-03) karena qty baris=60=received
    pa = admin.get(f"{BASE}/api/po-variance-tasks",
                   params={"po_id": PO_ID, "status": "pending_amendment"}, timeout=20).json()
    assert not pa, f"Tugas pending_amendment harus tertutup setelah approval+qty cocok: {pa}"
    decided = admin.get(f"{BASE}/api/po-variance-tasks",
                        params={"po_id": PO_ID, "status": "decided"}, timeout=20).json()
    assert decided, "Harus ada tugas decided"
