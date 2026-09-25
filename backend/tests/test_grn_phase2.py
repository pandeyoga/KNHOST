"""GRN Fase 2 — Kedatangan Barang (backend, tanpa OCR).

Membuktikan: alur penuh draft→closed memposting stok/PO/GL IDENTIK dengan jalur lama (golden Fase 1),
hitung buta ditegakkan API, anti-duplikat SJ, selisih pemblokir + penyelesaian, kiriman parsial → tepat
satu tugas sisa, klik ganda close aman, batal membersihkan roll, pagar jalur lama & isolasi entitas.
Semua data uji dibersihkan (nol residu).
"""
import os
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock  # noqa: E402
from test_inbound_complete_characterization import BASE, GOLDEN_A, _fingerprint, _po_line_received  # noqa: E402

ENT = "ent_ksc"
NEW_COLLS = ["inventory_rolls", "inventory_movements", "inventory_lots", "journal_entries", "inspections",
             "notifications", "audit_logs", "rfid_tags", "doc_refs", "backorders", "qc_inspections",
             "goods_receipts", "supplier_dn_profiles"]
FULL_COLLS = ["inventory_balances", "number_sequences"]


def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT})
    return s


@pytest.fixture(scope="module")
def mdb():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def admin():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def wh():
    return _login("warehouse@kainnusantara.id")


@pytest.fixture()
def env(mdb):
    full = snapshot_stock(FULL_COLLS)
    assert full.get("__enabled__"), "restore harus aktif (DB uji)"
    ids = snapshot_new_ids(NEW_COLLS)
    kept, clones = {}, []

    def keep(coll, doc_id):
        if (coll, doc_id) not in kept:
            kept[(coll, doc_id)] = mdb[coll].find_one({"id": doc_id})

    def clone(product_id="prod_batik_mega", park_seed=False):
        seed = mdb.wms_tasks.find_one({"flow_type": "inbound", "product_id": product_id, "entity_id": ENT,
                                       "status": {"$in": ["waiting_goods", "receiving"]}, "po_id": {"$gt": ""},
                                       "id": {"$not": {"$regex": "^wms_grn2_"}}}, {"_id": 0})
        if not seed:
            pytest.skip(f"seed tak punya tugas inbound {product_id}")
        t = {**seed, "id": "wms_grn2_" + uuid.uuid4().hex[:6], "status": "waiting_goods", "received_qty": 0.0,
             "qty_rolls_scanned": 0, "scan_log": [], "refs": []}
        keep("wms_tasks", t["id"])
        keep("purchase_orders", t["po_id"])
        mdb.wms_tasks.insert_one(dict(t))
        clones.append(t["id"])
        if park_seed:   # tugas seed disisihkan supaya "tugas sisa" bisa diamati terisolasi
            keep("wms_tasks", seed["id"])
            mdb.wms_tasks.update_one({"id": seed["id"]}, {"$set": {"status": "cancelled"}})
        return t
    yield keep, clone
    mdb.wms_tasks.delete_many({"remainder_of": {"$in": clones}})
    purge_new_ids(ids)
    for (coll, doc_id), doc in kept.items():
        if doc is None:
            mdb[coll].delete_one({"id": doc_id})
        else:
            mdb[coll].replace_one({"id": doc_id}, doc)
    restore_stock(full)


def _ok(r, code=200):
    assert r.status_code == code, f"{r.status_code} {r.text}"
    return r.json()


def _supplier(mdb, task):
    return mdb.purchase_orders.find_one({"id": task["po_id"]}, {"_id": 0, "supplier_id": 1})["supplier_id"]


def _grn_review(admin, mdb, task, *, qty, rolls, dn=None):
    """Buat GRN → isi manual → kepala SJ → satu baris bertarget tugas. Return (grn, dn_number)."""
    dn = dn or f"SJ-T{uuid.uuid4().hex[:6]}"
    g = _ok(admin.post(f"{BASE}/goods-receipts", json={"partner_type": "supplier", "partner_id": _supplier(mdb, task),
                                                       "warehouse_id": task["warehouse_id"], "po_ids": [task["po_id"]]}))
    assert g["status"] == "draft" and g["number"].startswith("KSC/GRN-")
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/manual-entry", json={"expected_version": g["version"]}))
    g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": dn,
                                                                    "date": "2026-06-10"}))
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={
        "expected_version": g["version"], "declared": {"qty": qty, "unit": task.get("unit"), "rolls": rolls},
        "target": {"type": "po_task", "task_id": task["id"]}, "description": "TEST_ barang"}))
    ln = g["lines"][0]
    assert ln["decision"] == "accept" and ln["checks"]["uom"] == "ok" and ln["converted"]["qty"] == qty
    return g, dn


def _start(admin, g):
    return _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))


def _scan(s, g, raw):
    return _ok(s.post(f"{BASE}/goods-receipts/{g['id']}/lines/1/scan-label", json={"raw": raw}))


def test_full_flow_matches_legacy_golden(admin, wh, mdb, env):
    keep, clone = env
    t = clone()
    before = _po_line_received(mdb, t["po_id"], t["product_id"])
    exp = float(t["expected_qty"])
    g, dn = _grn_review(admin, mdb, t, qty=exp, rolls=2)
    # PO lama tidak boleh menerima pesanan — penghitung (warehouse) tidak punya hak review/close
    assert wh.post(f"{BASE}/goods-receipts/{g['id']}/lines", json={"expected_version": g["version"]}).status_code == 403
    g = _start(admin, g)
    assert g["status"] == "counting"
    assert mdb.wms_tasks.find_one({"id": t["id"]})["grn_active_id"] == g["id"]
    tag = uuid.uuid4().hex[:4]
    for i, qty in enumerate([exp - 100, 100]):
        res = _scan(wh, g, f"CBN-MEGA-PREM|DL-CH|G2{tag}-R{i}|{qty:g}")
        assert res["roll"]["grn_id"] == g["id"] and res["roll"]["grn_line_no"] == 1
    g = _ok(wh.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": res["grn"]["version"]}))
    assert g["status"] == "reconcile"
    assert wh.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}).status_code == 403
    g = _ok(admin.get(f"{BASE}/goods-receipts/{g['id']}"))
    assert g["lines"][0]["recon"]["classes"] == ["match"] and not [d for d in g["discrepancies"] if d["blocking"]]
    out = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))
    assert out["grn"]["status"] == "closed", out
    assert out["grn"]["lines"][0]["posted"]["status"] == "done"
    # §6.1 — stok, PO & GL identik dengan jalur lama (nilai emas Fase 1)
    assert _fingerprint(mdb, t["id"], t["po_id"], t["product_id"], before) == GOLDEN_A(exp)
    task = mdb.wms_tasks.find_one({"id": t["id"]})
    assert task["supplier_dn_number"] == dn and dn in task["supplier_dn_numbers"]
    assert "grn_active_id" not in task and g["id"] in task["grn_ids"]
    # klik ganda close → tidak memposting lagi
    r = admin.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": out["grn"]["version"]})
    assert r.status_code == 409
    assert mdb.journal_entries.count_documents({"source_type": "goods_receipt", "source_id": t["id"]}) == 1
    assert mdb.supplier_dn_profiles.find_one({"entity_id": ENT, "partner_id": _supplier(mdb, t)})["confirmed_count"] >= 1


def test_blind_count_enforced_by_api(admin, wh, mdb, env):
    _, clone = env
    t = clone()
    g, _ = _grn_review(admin, mdb, t, qty=float(t["expected_qty"]), rolls=3)
    blind = _ok(wh.get(f"{BASE}/goods-receipts/{g['id']}?view=review"))
    assert blind["blind"] is True and "files" not in blind and "discrepancies" not in blind
    assert all(k not in blind["lines"][0] for k in ("declared", "read", "converted", "recon", "checks"))
    assert blind["lines"][0]["target"]["task_id"] == t["id"]
    full = _ok(admin.get(f"{BASE}/goods-receipts/{g['id']}?view=count"))
    assert full["blind"] is False and full["lines"][0]["declared"]["rolls"] == 3
    _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": full["version"],
                                                                   "reason": "TEST_ uji selesai"}))


def test_partial_delivery_discrepancies_and_single_remainder(admin, wh, mdb, env):
    _, clone = env
    t = clone(park_seed=True)
    exp = float(t["expected_qty"])
    g, _ = _grn_review(admin, mdb, t, qty=exp, rolls=2)
    g = _start(admin, g)
    res = _scan(wh, g, f"CBN-MEGA-PREM|DL-PT|P2{uuid.uuid4().hex[:4]}|100")
    g = _ok(wh.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": res["grn"]["version"]}))
    g = _ok(admin.get(f"{BASE}/goods-receipts/{g['id']}"))
    kinds = {d["kind"] for d in g["discrepancies"] if d["blocking"]}
    assert kinds == {"short_vs_dn", "rolls_mismatch"}, g["discrepancies"]
    r = admin.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]})
    assert r.status_code == 400 and r.json()["detail"]["code"] == "BLOCKERS_OPEN"
    r = admin.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/L1:short_vs_dn/resolve",
                   json={"expected_version": g["version"], "action": "reject_goods", "reason": "TEST_ salah aksi"})
    assert r.status_code == 400
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/L1:short_vs_dn/resolve",
                       json={"expected_version": g["version"], "action": "claim_supplier", "reason": "TEST_ kurang kirim"}))
    g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/L1:rolls_mismatch/resolve",
                       json={"expected_version": g["version"], "action": "accept_note", "reason": "TEST_ sisa menyusul"}))
    assert g["lines"][0]["claim"]["action"] == "claim_supplier"
    out = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))
    assert out["grn"]["status"] == "closed", out
    rem = out["results"][0]["remainder"]
    assert rem["created"] is True and rem["remaining"] == round(exp - 100, 2), rem
    task = mdb.wms_tasks.find_one({"id": t["id"]})
    assert task["status"] in ("qc_pending", "completed") and task["received_qty"] == 100
    active = list(mdb.wms_tasks.find({"po_id": t["po_id"], "product_id": t["product_id"], "flow_type": "inbound",
                                      "status": {"$in": ["waiting_goods", "receiving", "qc_check", "put_away"]}}))
    assert len(active) == 1 and active[0]["expected_qty"] == round(exp - 100, 2) and active[0]["remainder_of"] == t["id"]


def test_duplicate_dn_and_cancel_cleans_up(admin, wh, mdb, env):
    _, clone = env
    t1, t2 = clone(), clone()
    g1, dn = _grn_review(admin, mdb, t1, qty=100, rolls=1)
    g2, _ = _grn_review(admin, mdb, t2, qty=100, rolls=1, dn=dn.lower().replace("-", " "))
    g1 = _start(admin, g1)
    r = admin.post(f"{BASE}/goods-receipts/{g2['id']}/start-count", json={"expected_version": g2["version"]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "DN_DUPLICATE"
    assert r.json()["detail"]["existing_number"] == g1["number"]
    # tugas milik GRN aktif → jalur lama ditolak
    r = wh.post(f"{BASE}/inbound/tasks/{t1['id']}/scan-label", json={"raw": "CBN-MEGA-PREM|DL-X|X1|10"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "GRN_MANAGED"
    res = _ok(wh.post(f"{BASE}/goods-receipts/{g1['id']}/lines/1/rolls", json={"length": 30, "lot": "DL-GC"}))
    assert res["grn"]["lines"][0].get("counted") is not None and mdb.inventory_rolls.count_documents({"grn_id": g1["id"]}) == 1
    assert mdb.wms_tasks.find_one({"id": t1["id"]})["received_qty"] > 0
    _ok(admin.post(f"{BASE}/goods-receipts/{g1['id']}/cancel", json={"expected_version": res["grn"]["version"],
                                                                    "reason": "TEST_ batal"}))
    assert mdb.inventory_rolls.count_documents({"grn_id": g1["id"]}) == 0
    t1d = mdb.wms_tasks.find_one({"id": t1["id"]})
    assert t1d["received_qty"] == 0 and "grn_active_id" not in t1d
    # setelah batal, SJ yang sama boleh dihitung lewat GRN lain
    g2 = _ok(admin.get(f"{BASE}/goods-receipts/{g2['id']}"))
    g2 = _start(admin, g2)
    _ok(admin.post(f"{BASE}/goods-receipts/{g2['id']}/cancel", json={"expected_version": g2["version"], "reason": "TEST_ batal"}))


def test_grn_mode_blocks_legacy_new_tasks(admin, wh, mdb, env):
    _, clone = env
    t = clone()

    def _mode(v):
        _ok(admin.put(f"{BASE}/config/values", json={"items": [{"key": "receiving.mode", "value": v,
                                                                 "scope_type": "global", "reason": "TEST_ uji GRN fase 2"}]}))
    try:
        _mode("grn")
        r = wh.post(f"{BASE}/inbound/tasks/{t['id']}/scan-label", json={"raw": "CBN-MEGA-PREM|DL-X|M1|10"})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "GRN_MODE", r.text
        r = wh.post(f"{BASE}/inbound/tasks/{t['id']}/complete", json={})
        assert r.status_code == 409
    finally:
        _mode("legacy")


def test_entity_isolation(admin, mdb, env):
    _, clone = env
    t = clone()
    g, _ = _grn_review(admin, mdb, t, qty=10, rolls=1)
    other = mdb.entities.find_one({"id": {"$ne": ENT}, "status": {"$ne": "archived"}}, {"_id": 0, "id": 1})
    if other:
        r = admin.get(f"{BASE}/goods-receipts/{g['id']}", headers={"X-Entity-Id": other["id"]})
        assert r.status_code in (403, 404)
        r = admin.get(f"{BASE}/goods-receipts/{g['id']}/files/1", headers={"X-Entity-Id": other["id"]})
        assert r.status_code in (403, 404)
    _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": g["version"], "reason": "TEST_ batal"}))
