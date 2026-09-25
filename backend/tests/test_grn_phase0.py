"""GRN Fase 0 — perbaikan prasyarat penerimaan (lihat memory/grn_ocr/Prompt_Implementasi_GRN_OCR_SJ.md §5 Fase 0)."""
import os
import uuid

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")


def _base():
    url = os.environ.get("REACT_APP_BACKEND_URL", "").strip()
    if not url:
        for ln in open("/app/frontend/.env"):
            if ln.startswith("REACT_APP_BACKEND_URL="):
                url = ln.split("=", 1)[1].strip()
    return url.rstrip("/") + "/api"


BASE = _base()
ENT = "ent_ksc"


def _session(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT})
    return s


@pytest.fixture(scope="module")
def admin():
    return _session("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def wh():
    return _session("warehouse@kainnusantara.id")


@pytest.fixture(scope="module")
def mdb():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture()
def synth_task(mdb):
    """Tugas inbound sintetis (tanpa PO) — dibuang setelah tiap test."""
    made = []

    def make(**over):
        base = mdb.wms_tasks.find_one({"flow_type": "inbound", "product_id": "prod_batik_mega"}, {"_id": 0})
        tid = "wms_grn0_" + uuid.uuid4().hex[:6]
        doc = {**base, "id": tid, "entity_id": ENT, "po_id": "", "po_number": "", "refs": [], "scan_log": [],
               "stages": ["waiting_goods", "receiving", "qc_check", "put_away", "completed"],
               "status": "receiving", "expected_qty": 100.0, "received_qty": 0.0, "unit": "yard", **over}
        mdb.wms_tasks.insert_one(dict(doc))
        made.append(tid)
        return tid
    yield make
    mdb.wms_tasks.delete_many({"id": {"$in": made}})


def _set_cfg(s, key, value):
    r = s.put(f"{BASE}/config/values", json={"items": [{"key": key, "value": value, "scope_type": "global",
                                                         "reason": "uji GRN fase 0"}]}, timeout=30)
    assert r.status_code == 200, r.text


# 0.1 ─ advance menolak tugas inbound
@pytest.mark.parametrize("status", ["qc_check", "put_away"])
def test_advance_rejects_inbound(admin, synth_task, mdb, status):
    tid = synth_task(status=status)
    r = admin.post(f"{BASE}/wms/tasks/{tid}/advance", timeout=30)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "USE_RECEIVING_FLOW"
    assert mdb.wms_tasks.find_one({"id": tid})["status"] == status


# 0.2 ─ receiving.block_over_remaining (lewat value_of) mengubah perilaku scan label
def test_block_over_remaining_changes_scan_label(admin, wh, mdb):
    t = mdb.wms_tasks.find_one({"flow_type": "inbound", "product_id": "prod_batik_mega", "status": "waiting_goods",
                                "po_id": {"$gt": ""}, "entity_id": ENT}, {"_id": 0, "id": 1})
    if not t:
        pytest.skip("seed tak punya tugas PO prod_batik_mega waiting_goods")
    LABEL_TASK = t["id"]  # noqa: N806 — tugas PO seed dengan kode supplier CBN-MEGA-PREM
    original = mdb.wms_tasks.find_one({"id": LABEL_TASK})
    raw = f"CBN-MEGA-PREM|DL-GRN0|GRN0-{uuid.uuid4().hex[:5]}|500"
    try:
        _set_cfg(admin, "receiving.block_over_remaining", True)
        r = wh.post(f"{BASE}/inbound/tasks/{LABEL_TASK}/scan-label", json={"raw": raw}, timeout=30)
        assert r.status_code == 400 and r.json()["detail"]["code"] == "OVER_PO", r.text
        _set_cfg(admin, "receiving.block_over_remaining", False)
        r = wh.post(f"{BASE}/inbound/tasks/{LABEL_TASK}/scan-label", json={"raw": raw}, timeout=30)
        assert r.status_code == 200, r.text
        rid = r.json()["roll"]["id"]
        assert wh.delete(f"{BASE}/inbound/rolls/{rid}/scan", timeout=30).status_code == 200
    finally:
        _set_cfg(admin, "receiving.block_over_remaining", True)
        mdb.wms_tasks.replace_one({"id": LABEL_TASK}, original)   # scan/hapus roll mengubah status & log tugas


# 0.3 ─ toleransi Σ roll dari receiving.line_qty_tolerance_pct
@pytest.mark.parametrize("pct", [5, 2])
def test_line_qty_tolerance_from_config(admin, synth_task, pct):
    tid = synth_task(status="qc_check", received_qty=100.0, quantity=100.0)
    try:
        _set_cfg(admin, "receiving.line_qty_tolerance_pct", pct)
        opts = admin.get(f"{BASE}/inbound/tasks/{tid}/uom-options", timeout=30)
        assert opts.status_code == 200 and opts.json()["line_qty_tolerance_pct"] == pct, opts.text
        r = admin.post(f"{BASE}/inbound/tasks/{tid}/complete",
                       json={"rolls": [{"length": 110, "weight": 0, "dye_lot": "DL", "grade": "A"}]},  # +10%
                       timeout=30)
        assert r.status_code == 400 and f"toleransi ±{pct:g}" in r.text, r.text
    finally:
        _set_cfg(admin, "receiving.line_qty_tolerance_pct", 2.0)


# 0.4 ─ grade mengikuti SSOT
def test_require_grade_legacy_map():
    import domain_registry as dr
    assert dr.require_grade("A+") == "A"
    assert dr.require_grade("C") == "BS"
    assert dr.require_grade("", "A") == "A"
    with pytest.raises(ValueError):
        dr.require_grade("Z")


def test_scan_receive_rejects_unknown_grade(wh, synth_task):
    tid = synth_task()
    r = wh.post(f"{BASE}/inbound/tasks/{tid}/scan-receive",
                json={"product_id": "prod_batik_mega", "actual_qty": 1, "grade": "Z"}, timeout=30)
    assert r.status_code == 400 and "Grade 'Z' tidak dikenal" in r.text, r.text


def test_scan_receive_maps_legacy_grade(wh, synth_task, mdb):
    tid = synth_task()
    r = wh.post(f"{BASE}/inbound/tasks/{tid}/scan-receive",
                json={"product_id": "prod_batik_mega", "actual_qty": 1, "grade": "A+"}, timeout=30)
    assert r.status_code == 200, r.text
    assert mdb.wms_tasks.find_one({"id": tid})["grade"] == "A"


# 0.6 ─ override pratinjau "block" hanya untuk pemegang wms.approve, alasan tercatat
def test_over_receipt_override_requires_approve(admin, wh, synth_task, mdb):
    tid = synth_task(expected_qty=10.0, received_qty=0.0)
    body = {"product_id": "prod_batik_mega", "actual_qty": 50, "variance_override_reason": "kiriman lebih disetujui"}
    r = wh.post(f"{BASE}/inbound/tasks/{tid}/scan-receive", json=body, timeout=30)
    assert r.status_code == 400, r.text
    r = admin.post(f"{BASE}/inbound/tasks/{tid}/scan-receive", json={**body, "variance_override_reason": ""}, timeout=30)
    assert r.status_code == 400, r.text
    r = admin.post(f"{BASE}/inbound/tasks/{tid}/scan-receive", json=body, timeout=30)
    assert r.status_code == 200, r.text
    t = mdb.wms_tasks.find_one({"id": tid})
    assert t["scan_log"][-1]["over_override_reason"] == "kiriman lebih disetujui"
    assert t["over_receipt"] is True


# 0.7 ─ indeks unik (supplier_id, supplier_sku) + lookup hanya status aktif
def test_supplier_item_unique_and_lookup_active(admin, mdb):
    assert "uq_supplier_sku" in mdb.supplier_items.index_information()
    src = mdb.supplier_items.find_one({"status": "active", "supplier_sku": {"$gt": ""}}, {"_id": 0})
    from pymongo.errors import DuplicateKeyError
    with pytest.raises(DuplicateKeyError):
        mdb.supplier_items.insert_one({**src, "id": "si_dup_" + uuid.uuid4().hex[:5]})
    sku = "GRN0-INACT-" + uuid.uuid4().hex[:5]
    mdb.supplier_items.insert_one({**src, "id": "si_" + sku, "supplier_sku": sku, "status": "inactive"})
    try:
        r = admin.get(f"{BASE}/supplier-items/lookup", params={"supplier_sku": sku, "supplier_id": src["supplier_id"]},
                      timeout=30)
        assert r.status_code in (200, 404), r.text
        body = r.json() if r.status_code == 200 else {}
        assert not (body or {}).get("item") and (body or {}).get("id") != "si_" + sku, r.text
    finally:
        mdb.supplier_items.delete_one({"id": "si_" + sku})


# 0.8 ─ KN-B15 di jalur amandemen PO (dan helper bersama untuk PR→PO)
def test_duplicate_line_helper():
    from services.po_line_guard import duplicate_line_message
    assert duplicate_line_message(["a", "b"]) == ""
    assert "a" in duplicate_line_message(["a", "b", "a"])


def test_amend_rejects_duplicate_product(admin, mdb):
    po = mdb.purchase_orders.find_one({"entity_id": ENT, "status": {"$in": ["pending", "receiving", "draft", "approved"]},
                                       "items.0": {"$exists": True}}, {"_id": 0, "id": 1, "items": 1})
    if not po:
        pytest.skip("tak ada PO terbuka di seed")
    it = po["items"][0]
    line = {"product_id": it["product_id"], "quantity": float(it.get("quantity") or 1), "unit": it.get("unit", "meter"),
            "price": float(it.get("price") or 0)}
    r = admin.post(f"{BASE}/purchase-orders/{po['id']}/amend",
                   json={"items": [line, line], "reason": "uji KN-B15"}, timeout=30)
    assert r.status_code == 400 and "lebih dari satu baris PO" in r.text, r.text
