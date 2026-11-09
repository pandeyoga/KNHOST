"""FIX-3a — integritas alur BARANG MASUK, penyimpanan, opname & validasi input (audit 9 Nov: B2a, B3b, B3a).

Setiap uji menyebut ID temuan yang ditutup. Uji ini GAGAL di dasar `main` (sebelum FIX-3a) dan LULUS sesudahnya.
Gudang, produk, tugas, roll, dan sesi UJI dibuat sendiri (tidak menyentuh data acuan) dan dibersihkan di akhir.
Jalankan (stack sementara):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix3a_inbound_integrity.py
"""
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6].upper()
OWNER = "ent_ksc"
OLD_TS = "2026-01-01T00:00:00+00:00"
W = f"wh_TFX3A_{TAG}"           # gudang simpan uji (struktur bin sendiri)
W_T = f"wh_TFX3A_T_{TAG}"       # gudang transit uji
P = f"prod_TFX3A_{TAG}"
TASKS, ROLLS, SESSIONS, TRANSFERS, PAS = [], [], [], [], []


def _b(i, code):
    return {"id": f"bin_fx3a_{TAG}_{i}", "code": f"{code}-{TAG}", "capacity_rolls": 0}


B1, B2, B3 = _b(1, "F1-01"), _b(2, "F1-02"), _b(3, "F2-01")
Z1, Z2 = f"zone_fx3a_{TAG}_1", f"zone_fx3a_{TAG}_2"


@pytest.fixture(scope="module", autouse=True)
def world():
    DB.warehouses.insert_many([
        {"id": W, "code": f"TFX3A-{TAG}", "name": f"TEST FIX3A {TAG}", "city": "Bandung", "sharing_mode": "shared",
         "entity_ids": [OWNER], "active": True, "roles": ["storage"], "created_at": OLD_TS,
         "zones": [{"id": Z1, "name": "Zona F1", "racks": [{"id": f"rack_fx3a_{TAG}_1", "name": "Rak F1", "bins": [B1, B2]}]},
                   {"id": Z2, "name": "Zona F2", "racks": [{"id": f"rack_fx3a_{TAG}_2", "name": "Rak F2", "bins": [B3]}]}]},
        {"id": W_T, "code": f"TFX3AT-{TAG}", "name": f"TEST FIX3A TRANSIT {TAG}", "city": "Bandung",
         "sharing_mode": "shared", "entity_ids": [OWNER], "active": True, "roles": ["transit"], "created_at": OLD_TS,
         "zones": []}])
    DB.products.insert_one({"id": P, "sku": f"TFX3A-{TAG}", "name": f"Kain Uji FIX3A {TAG}", "base_unit": "yard",
                            "status": "active", "stage": "finished", "grade": "A", "category": "Kain", "harga_pokok": 12500.0,
                            "created_at": OLD_TS})
    yield
    rolls = [r["id"] for r in DB.inventory_rolls.find({"$or": [{"warehouse_id": {"$in": [W, W_T]}}, {"product_id": P}]},
                                                       {"id": 1})] + ROLLS
    DB.inventory_rolls.delete_many({"id": {"$in": rolls}})
    DB.inventory_movements.delete_many({"$or": [{"roll_id": {"$in": rolls}}, {"warehouse_id": {"$in": [W, W_T]}}]})
    DB.rfid_tags.delete_many({"roll_id": {"$in": rolls}})
    DB.wms_tasks.delete_many({"id": {"$in": TASKS}})
    DB.inspections.delete_many({"task_id": {"$in": TASKS}})
    DB.cycle_count_sessions.delete_many({"$or": [{"id": {"$in": SESSIONS}}, {"warehouse_id": {"$in": [W, W_T]}}]})
    DB.initial_registration_lines.delete_many({"session_id": {"$in": SESSIONS}})
    DB.warehouse_transfers.delete_many({"id": {"$in": TRANSFERS}})
    DB.putaway_orders.delete_many({"id": {"$in": PAS}})
    DB.inventory_balances.delete_many({"warehouse_id": {"$in": [W, W_T]}})
    DB.inventory_lots.delete_many({"product_id": P})
    DB.journal_entries.delete_many({"source_id": {"$regex": "|".join(SESSIONS) or "x^"}})
    DB.journal_entries.delete_many({"source_id": {"$in": TASKS}})
    DB.purchase_returns.delete_many({"po_number": f"PO-FX3A-{TAG}"})
    DB.products.delete_many({"id": P})
    DB.warehouses.delete_many({"id": {"$in": [W, W_T]}})


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": os.environ.get("KN_DEMO_PW", "demo12345")})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": OWNER}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def mgr():
    return _login("manager@kainnusantara.id")


def _task(status, expected=100.0, received=0.0, **kw):
    tid = f"wms_fx3a_{uuid.uuid4().hex[:8]}"
    DB.wms_tasks.insert_one({"id": tid, "flow_type": "inbound", "source_type": "purchase_order", "status": status,
                             "product_id": P, "product_name": f"Kain Uji FIX3A {TAG}", "warehouse_id": W,
                             "entity_id": OWNER, "expected_qty": expected, "received_qty": received, "unit": "yard",
                             "legacy_in_flight": True, "po_number": f"PO-FX3A-{TAG}", "created_at": OLD_TS, **kw})
    TASKS.append(tid)
    return tid


def _roll(qty=10.0, bin_doc=None, wh=None, **kw):
    rid = f"roll_fx3a_{uuid.uuid4().hex[:8]}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"FX3A-{rid[-6:]}", "product_id": P, "warehouse_id": wh or W,
                                   "owner_entity_id": OWNER, "length_initial": qty, "length_remaining": qty, "unit": "yard",
                                   "status": "available", "bin_id": (bin_doc or {}).get("id"),
                                   "bin_code": (bin_doc or {}).get("code", ""), "grade": "A", "unit_cost": 10.0,
                                   "base_unit_cost": 10.0, "lot": f"LOT-{TAG}", "created_at": OLD_TS, **kw})
    ROLLS.append(rid)
    return rid


def _detail(resp):
    d = resp.json().get("detail")
    return d if isinstance(d, str) else (d.get("message") if isinstance(d, dict) else str(d))


# ─── K-14 / K-B3b-03 — satu validator alasan (huruf, bukan karakter) ─────────────────────────────────────────────
def test_reason_validator_counts_letters():
    from input_rules import count_letters, reason_problem, require_reason
    from fastapi import HTTPException
    assert count_letters("ab1.c") == 3
    assert reason_problem(".....") and reason_problem("12345") and reason_problem("     ") and reason_problem("x")
    assert reason_problem("rusak") is None and reason_problem("Roll basah kena hujan") is None
    with pytest.raises(HTTPException):
        require_reason("....")


# ─── B2a FLW-IN-01 / FLW-IN-06 — penjaga DAFTAR-IZIN pada pindai-terima ──────────────────────────────────────────
@pytest.mark.parametrize("status", ["qc_rejected", "qc_pending", "escalated", "completed"])
def test_scan_receive_rejected_for_posted_or_escalated_task(adm, status):
    tid = _task(status, expected=50, received=50, quantity=50)
    r = requests.post(f"{BASE}/inbound/tasks/{tid}/scan-receive", json={"product_id": P, "actual_qty": 1}, headers=adm)
    assert r.status_code == 400, r.text
    t = DB.wms_tasks.find_one({"id": tid})
    assert t["status"] == status and float(t["received_qty"]) == 50.0          # tidak menimpa status / qty
    rc = requests.post(f"{BASE}/inbound/tasks/{tid}/complete", json={}, headers=adm)
    assert rc.status_code == 400 and DB.inventory_rolls.count_documents({"grn_task_id": tid}) == 0


def test_escalate_only_before_posting_and_reason_k14(adm):
    tid = _task("qc_pending", expected=50, received=50)
    assert requests.post(f"{BASE}/inbound/tasks/{tid}/escalate", json={"reason": "Qty kurang dari PO"},
                         headers=adm).status_code == 400                          # FLW-IN-01 jalur eskalasi
    tid2 = _task("receiving", expected=50, received=10)
    assert requests.post(f"{BASE}/inbound/tasks/{tid2}/escalate", params={"reason": "x"}, headers=adm).status_code == 400
    ok = requests.post(f"{BASE}/inbound/tasks/{tid2}/escalate", json={"reason": "Supplier kirim kurang 40 yard"}, headers=adm)
    assert ok.status_code == 200 and ok.json()["status"] == "escalated", ok.text
    hist = DB.wms_tasks.find_one({"id": tid2})["status_history"]
    assert hist[-1]["status"] == "escalated" and hist[-1]["timestamp"]          # STM-IN-07 jejak status seragam
    # B3b INP-09 — qty pesanan negatif ditolak; catatan penyelesaian wajib K-14
    bad = requests.post(f"{BASE}/inbound/tasks/{tid2}/resolve-escalation",
                        params={"adjusted_qty": -10, "resolution_notes": "Disetujui manajer"}, headers=adm)
    assert bad.status_code == 400 and DB.wms_tasks.find_one({"id": tid2})["expected_qty"] == 50
    assert requests.post(f"{BASE}/inbound/tasks/{tid2}/resolve-escalation", params={"resolution_notes": "ok"},
                         headers=adm).status_code == 400
    good = requests.post(f"{BASE}/inbound/tasks/{tid2}/resolve-escalation",
                         params={"adjusted_qty": 10, "resolution_notes": "Sisa tidak dikirim supplier"}, headers=adm)
    assert good.status_code == 200 and good.json()["status"] == "qc_check" and good.json()["expected_qty"] == 10


# ─── B3b INP-01 / B2a FLW-IN-08 — bin penerimaan = rujukan struktur ───────────────────────────────────────────────
def test_scan_receive_bin_must_exist_and_is_canonicalised(adm):
    tid = _task("waiting_goods", expected=20)
    r = requests.post(f"{BASE}/inbound/tasks/{tid}/scan-receive",
                      json={"product_id": P, "actual_qty": 5, "bin_id": "TIDAK-ADA-BIN"}, headers=adm)
    assert r.status_code == 400 and "struktur" in _detail(r)
    ok = requests.post(f"{BASE}/inbound/tasks/{tid}/scan-receive",
                       json={"product_id": P, "actual_qty": 5, "bin_id": B1["code"].lower()}, headers=adm)
    assert ok.status_code == 200, ok.text
    assert ok.json()["bin_id"] == B1["id"] and ok.json()["status"] == "receiving"   # kode rak → id kanonik


def test_complete_places_roll_via_evaluator_and_never_maps_roll_id_to_tag(monkeypatch):
    from services import inbound_qc_common as iqc
    from services.inbound_complete_service import complete_task

    async def _qc_off(_e):
        return False
    monkeypatch.setattr(iqc, "qc_on_receipt_enabled", _qc_off)
    tid = _task("qc_check", expected=10, received=10, quantity=10, bin_id=B2["id"], roll_id="SUP-ROLL-77")
    out = run(complete_task(tid, None, {"id": "u_fx3a", "name": "Uji FIX3A", "role": "admin"}))
    rid = out["created_rolls"][0]["id"]
    roll = DB.inventory_rolls.find_one({"id": rid})
    assert roll["bin_id"] == B2["id"] and roll["rfid_tag_id"] is None and roll["supplier_roll_no"] == "SUP-ROLL-77"
    assert DB.inventory_movements.find_one({"roll_id": rid, "movement_type": "putaway"})    # lewat place_roll
    assert DB.wms_tasks.find_one({"id": tid})["status_history"][-1]["status"] == "completed"


# ─── B2a FLW-IN-04 / B3b FRM-02 — rencana > 1 roll wajib rincian roll ─────────────────────────────────────────────
def test_complete_multi_roll_plan_requires_roll_details(adm):
    tid = _task("qc_check", expected=300, received=300, quantity=300, expected_rolls=3)
    r = requests.post(f"{BASE}/inbound/tasks/{tid}/complete", json={"supplier_lot": "X"}, headers=adm)
    assert r.status_code == 400 and "PER ROLL" in _detail(r)
    assert DB.inventory_rolls.count_documents({"grn_task_id": tid}) == 0


# ─── B2a OPN-01 / STM-IN-01 — pembekuan pendaftaran awal di jalur terima PO lama ─────────────────────────────────
def test_receipt_into_frozen_area_rejected(adm, monkeypatch):
    sid = f"cc_fx3a_reg_{TAG}"
    SESSIONS.append(sid)
    DB.cycle_count_sessions.insert_one({"id": sid, "mode": "registration", "status": "running", "warehouse_id": W,
                                        "warehouse_name": f"TEST FIX3A {TAG}", "entity_id": OWNER, "name": "REG uji",
                                        "freeze": {"active": True, "mode": "zone", "warehouse_id": W,
                                                   "bin_ids": [B3["id"]], "label": "Zona F2"},
                                        "created_at": OLD_TS})
    try:
        tid = _task("waiting_goods", expected=20)
        r = requests.post(f"{BASE}/inbound/tasks/{tid}/scan-receive",
                          json={"product_id": P, "actual_qty": 20, "bin_id": B3["id"]}, headers=adm)
        assert r.status_code == 409 and (r.json()["detail"] or {}).get("code") == "REGISTRATION_FREEZE", r.text
        # data lama: bin beku sudah tersimpan di tugas → selesai terima ditolak (dulu roll lahir di rak beku)
        from services import inbound_qc_common as iqc
        from services.inbound_complete_service import complete_task
        from fastapi import HTTPException

        async def _qc_off(_e):
            return False
        monkeypatch.setattr(iqc, "qc_on_receipt_enabled", _qc_off)
        tid2 = _task("qc_check", expected=40, received=40, quantity=40, bin_id=B3["id"])
        with pytest.raises(HTTPException) as ei:
            run(complete_task(tid2, None, {"id": "u_fx3a", "name": "Uji FIX3A", "role": "admin"}))
        assert ei.value.status_code == 409
        assert DB.inventory_rolls.count_documents({"grn_task_id": tid2}) == 0
        # STM-IN-03 — sesi pendaftaran tidak bisa dibuka lewat opname biasa
        DB.cycle_count_sessions.update_one({"id": sid}, {"$set": {"status": "rejected", "freeze.active": False}})
        ro = requests.post(f"{BASE}/cycle-count/sessions/{sid}/reopen", headers=adm)
        assert ro.status_code == 400 and DB.cycle_count_sessions.find_one({"id": sid})["status"] == "rejected"
        # B3a keputusan 8 — stok awal manual ditutup untuk gedung yang memakai pendaftaran awal
        st = requests.post(f"{BASE}/inventory/initial-stock",
                           json={"product_id": P, "warehouse_id": W, "lot": "L1", "quantity": 5}, headers=adm)
        assert st.status_code == 410 and st.json()["detail"]["code"] == "INITIAL_STOCK_CLOSED"
    finally:
        DB.cycle_count_sessions.delete_one({"id": sid})


# ─── B2a FLW-IN-05 — batal PO membereskan roll `receiving` ────────────────────────────────────────────────────────
def test_cancel_po_undoes_receiving_rolls(adm):
    po_id = f"po_fx3a_{TAG}"
    DB.purchase_orders.insert_one({"id": po_id, "po_number": f"PO-FX3A-{TAG}", "status": "pending", "entity_id": OWNER,
                                   "items": [{"product_id": P, "quantity": 50, "price": 0}], "created_at": OLD_TS})
    try:
        tid = _task("receiving", expected=50, received=25, po_id=po_id)
        rid = _roll(25.0, status="receiving", grn_task_id=tid, declared_task_qty=25.0)
        r = requests.post(f"{BASE}/purchase-orders/{po_id}/cancel", headers=adm)
        assert r.status_code == 200, r.text
        assert DB.inventory_rolls.find_one({"id": rid}) is None                      # roll yatim dihapus
        t = DB.wms_tasks.find_one({"id": tid})
        assert t["status"] == "cancelled" and t["status_history"][-1]["status"] == "cancelled"
    finally:
        DB.purchase_orders.delete_one({"id": po_id})


# ─── B3b INP-02 / B2a OPN-05 — bin opname terikat struktur + pembekuan ───────────────────────────────────────────
def test_cycle_count_item_bin_resolved_and_frozen_area_rejected(adm):
    _roll(30.0, B1)
    r = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": W, "name": f"FX3A {TAG}"}, headers=adm)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    SESSIONS.append(sid)
    bad = requests.post(f"{BASE}/cycle-count/sessions/{sid}/items", json={"product_id": P, "bin_id": "W99-NGAWUR"},
                        headers=adm)
    assert bad.status_code == 400
    ok = requests.post(f"{BASE}/cycle-count/sessions/{sid}/items", json={"product_id": P, "bin_id": B1["code"]},
                       headers=adm)
    assert ok.status_code == 200, ok.text
    assert ok.json()["bin_id"] == B1["id"] and ok.json()["bin_code"] == B1["code"] and ok.json()["expected_qty"] == 30.0
    fz = f"cc_fx3a_regz_{TAG}"
    SESSIONS.append(fz)
    DB.cycle_count_sessions.insert_one({"id": fz, "mode": "registration", "status": "running", "warehouse_id": W,
                                        "entity_id": OWNER, "name": "REG uji 2",
                                        "freeze": {"active": True, "mode": "zone", "warehouse_id": W, "bin_ids": [B2["id"]],
                                                   "label": "Rak F1"}, "created_at": OLD_TS})
    try:
        r2 = requests.post(f"{BASE}/cycle-count/sessions/{sid}/items", json={"product_id": P, "bin_id": B2["id"]},
                           headers=adm)
        assert r2.status_code == 409, r2.text
    finally:
        DB.cycle_count_sessions.delete_one({"id": fz})
    # FRM-09 #10 — tolak opname wajib alasan ≥ 5 huruf
    DB.cycle_count_sessions.update_one({"id": sid}, {"$set": {"status": "submitted"}})
    assert requests.post(f"{BASE}/cycle-count/sessions/{sid}/reject", json={"reason": "....."},
                         headers=adm).status_code == 422


# ─── B2a OPN-02 (D8) — potret opname seluruh gedung memuat roll tanpa bin ────────────────────────────────────────
def test_roll_snapshot_full_scope_includes_unbinned_rolls():
    from services import stock_count_roll_service as rcs
    nobin = _roll(7.0, None)
    orphan = _roll(8.0, {"id": "bin_tidak_ada_fx3a", "code": "X"})
    rc = run(rcs.make_snapshot({"id": "cc_x", "warehouse_id": W}, "", None))
    ids = {e["roll_id"] for e in rc["expected"]}
    assert nobin in ids and orphan in ids and rc["unbinned_expected"] >= 2
    rc_zone = run(rcs.make_snapshot({"id": "cc_x", "warehouse_id": W}, Z1, None))
    assert nobin not in {e["roll_id"] for e in rc_zone["expected"]} and rc_zone["unbinned_outside_scope"] >= 1


# ─── B2a OPN-03 — nilai temuan membaca harga_pokok master ────────────────────────────────────────────────────────
def test_surplus_cost_falls_back_to_harga_pokok():
    from services.stock_count_service import surplus_unit_cost
    cost, basis = run(surplus_unit_cost(P, f"wh_kosong_{TAG}", "ent_tidak_ada"))
    assert cost == 12500.0 and basis == "produk.harga_pokok"


# ─── B2a OPN-04 — roll habis lewat opname: tag dicabut ───────────────────────────────────────────────────────────
def test_opname_write_off_retires_tag():
    from services import stock_count_roll_service as rcs
    rid = _roll(5.0, B1)
    DB.rfid_tags.insert_one({"id": f"rtag_fx3a_{TAG}", "epc": f"E2FX3A{TAG}0001", "roll_id": rid, "status": "active",
                             "owner_entity_id": OWNER, "warehouse_id": W})
    DB.inventory_rolls.update_one({"id": rid}, {"$set": {"rfid_tag_id": f"rtag_fx3a_{TAG}"}})
    sess = {"id": f"cc_fx3a_wo_{TAG}", "warehouse_id": W, "name": "WO uji"}
    SESSIONS.append(sess["id"])
    DB.cycle_count_sessions.insert_one({**sess, "status": "open", "entity_id": OWNER, "roll_count": {"ops": {}}})
    adj = run(rcs.write_off_missing(sess, {"roll_id": rid, "bin_id": B1["id"], "qty": 5.0}, "Uji", post_journal=False))
    assert adj["status"] == "applied"
    assert DB.rfid_tags.find_one({"id": f"rtag_fx3a_{TAG}"})["status"] == "retired"
    assert DB.inventory_rolls.find_one({"id": rid})["rfid_tag_id"] is None


# ─── B3b INP-05 / INP-10 — stok awal: satuan, grade, bin divalidasi; desimal koma ────────────────────────────────
def test_initial_stock_validates_unit_grade_bin(adm):
    base = {"product_id": P, "warehouse_id": W, "lot": f"L-{TAG}", "quantity": 1}
    assert requests.post(f"{BASE}/inventory/initial-stock", json={**base, "unit": "hasta"}, headers=adm).status_code == 400
    assert requests.post(f"{BASE}/inventory/initial-stock", json={**base, "grade": "ZZ"}, headers=adm).status_code == 400
    assert requests.post(f"{BASE}/inventory/initial-stock", json={**base, "bin_id": "bin_tidak_ada"},
                         headers=adm).status_code == 400
    ok = requests.post(f"{BASE}/inventory/initial-stock",
                       json={**base, "quantity": "12,5", "grade": "B", "bin_id": B1["code"]}, headers=adm)
    assert ok.status_code == 200, ok.text
    roll = DB.inventory_rolls.find_one({"product_id": P, "acquired.via": "initial", "lot": {"$exists": True},
                                        "length_initial": 12.5})
    assert roll and roll["unit"] == "yard" and roll["grade"] == "B" and roll["bin_id"] == B1["id"]


# ─── B2a FLW-IN-02 — gudang "bermode tanpa daftar" bukan aturan spesifik ─────────────────────────────────────────
def test_putaway_rank_ignores_mode_without_list():
    from services.putaway_draft_service import _rank, is_specific
    knit = {"id": "a", "code": "RCM-KNITTING", "roles": ["storage"], "storage_rules": {"mode": "category", "categories": []}}
    woven = {"id": "b", "code": "RCM-WOVEN", "roles": ["storage"], "storage_rules": {"mode": "category", "categories": ["Woven"]}}
    assert not is_specific(knit) and is_specific(woven)
    assert sorted([knit, woven], key=lambda w: _rank(w, {}))[0]["code"] == "RCM-WOVEN"


# ─── B2a FLW-IN-03 (D3) — roll ditahan tidak mengunci keputusan QC; boleh ditolak ────────────────────────────────
def test_qc_decision_with_held_roll_keeps_hold_and_allows_reject(monkeypatch):
    from services import qc_service

    async def _cov(_t):
        return {"mode": "all", "inspected_rolls": 2, "required_rolls": 2, "total_rolls": 2, "met": True}
    monkeypatch.setattr(qc_service, "qc_coverage", _cov)
    tid = _task("qc_pending", expected=20, received=20)
    q = _roll(10.0, None, status="quarantine", qc_task_id=tid)
    h = _roll(10.0, None, status="blocked", qc_task_id=tid,
              hold={"held": True, "reason": "dicek ulang", "prev_status": "quarantine"})
    actor = {"id": "u_fx3a", "name": "Uji FIX3A"}
    task = DB.wms_tasks.find_one({"id": tid}, {"_id": 0})
    res = run(qc_service.process_qc_decision(task, 10.0, 0.0, "damaged", "Lulus inspeksi", actor))
    assert res["accepted_qty"] == 10.0 and res["held_rolls_kept"]
    assert DB.inventory_rolls.find_one({"id": q})["status"] == "available"
    assert DB.inventory_rolls.find_one({"id": h})["status"] == "blocked"         # tetap ditahan
    assert DB.wms_tasks.find_one({"id": tid})["status"] == "qc_pending"          # keputusan sebagian
    task = DB.wms_tasks.find_one({"id": tid}, {"_id": 0})
    res2 = run(qc_service.process_qc_decision(task, 0.0, 10.0, "damaged", "Roll ditahan ternyata rusak", actor,
                                              reject_held_roll_ids=[h]))
    assert res2["rejected_qty"] == 10.0 and DB.inventory_rolls.find_one({"id": h})["status"] == "damaged"
    t = DB.wms_tasks.find_one({"id": tid})
    assert t["status"] == "completed" and t["qc_accept_qty"] == 10.0 and t["qc_reject_qty"] == 10.0


# ─── B2a FLW-IN-10 (D10) / STM-IN-04 / FLW-IN-19 — penerimaan transfer ───────────────────────────────────────────
def test_transfer_all_returned_status_returned():
    from services import transfer_receipt_service as trs
    tr_id = f"trf_fx3a_{TAG}"
    TRANSFERS.append(tr_id)
    rid = _roll(9.0, None, wh=W_T, returned_from_transfer={"ref_id": tr_id})
    DB.warehouse_transfers.insert_one({"id": tr_id, "code": f"TRF-FX3A-{TAG}", "status": "dispatched",
                                       "source_warehouse_id": W_T, "dest_warehouse_id": W, "items": [], "created_at": OLD_TS})
    t = run(trs._refresh_status(tr_id, "Uji"))
    assert t["status"] == "returned" and t["completion_basis"] == "all_returned"
    assert t["status_history"][-1]["status"] == "returned"
    assert rid


def test_transfer_land_hold_uses_blocked_and_recomputes_journey():
    from services import transfer_receipt_service as trs
    tr_id = f"trf_fx3a_h_{TAG}"
    TRANSFERS.append(tr_id)
    rid = _roll(6.0, None, wh=W_T, status="in_transit_transfer", transfer_ref={"id": tr_id}, journey={"stage": "stored"})
    roll = DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    dest = DB.warehouses.find_one({"id": W}, {"_id": 0})
    landed = run(trs._land(roll, {"id": tr_id, "code": "TRF-H"}, dest, "hold", {"name": "Uji"}))
    doc = DB.inventory_rolls.find_one({"id": rid})
    assert landed is not None and landed["status"] == "blocked"
    assert doc["status"] == "blocked" and doc["hold"]["held"] is True and doc["journey"]["stage"] == "stored"
    # dilepas lewat jalur tahan tunggal (QC-06) → kembali tersedia
    from services.roll_hold_service import release_roll
    rel = run(release_roll(doc, "Pengecualian disetujui supervisor", {"name": "Uji"}))
    assert rel["status"] == "available"


# ─── B2a FLW-IN-16 / FLW-IN-15 — trip duplikat sesudah PA selesai = idempoten ────────────────────────────────────
def test_arrival_trip_duplicate_after_completion_is_idempotent():
    from services import putaway_arrival_service as arr
    pa_id = f"pa_fx3a_{TAG}"
    PAS.append(pa_id)
    DB.putaway_orders.insert_one({"id": pa_id, "_id": f"pakey_{TAG}", "pa_number": f"PA-FX3A-{TAG}", "status": "completed",
                                  "owner_entity_id": OWNER, "from_warehouse_id": W_T, "to_warehouse_id": W, "items": [],
                                  "arrival_trips": [{"trip_no": 1, "source": {"type": "handheld",
                                                                              "client_trip_id": "b2a-trip-1"},
                                                     "arrived_roll_nos": ["X"]}]})
    out = run(arr.confirm_arrival_trip(pa_id, ["E2X"], {"type": "handheld", "client_trip_id": "b2a-trip-1"}, "Uji",
                                       [OWNER]))
    assert out["duplicate_trip"] is True and out["trip"]["trip_no"] == 1


# ─── Persetujuan pendaftaran awal dua langkah (keputusan koordinator) ────────────────────────────────────────────
def test_registration_two_step_finance_gate():
    from fastapi import HTTPException
    from services import initial_registration_service as irs
    s = {"id": "cc_fx", "status": "pending_approval", "entity_id": OWNER, "registration": {}}
    assert irs.approval_step(s, True) == "count" and irs.approval_step(s, False) == "single"
    with pytest.raises(HTTPException) as e1:
        run(irs.assert_finance_ready(s, {"id": "u1", "name": "A"}))
    assert e1.value.status_code == 400
    s2 = {**s, "registration": {"count_approval": {"by": "A", "by_id": "u1"}}}
    assert irs.approval_step(s2, True) == "finance"
    with pytest.raises(HTTPException) as e2:
        run(irs.assert_finance_ready(s2, {"id": "u1", "name": "A"}))   # orang yang sama
    assert e2.value.status_code == 403
    run(irs.assert_finance_ready(s2, {"id": "u2", "name": "B"}))       # orang berbeda → boleh
    with pytest.raises(HTTPException):
        irs.assert_lines_editable(s2)


# ─── B3b FRM-19 — setelan regex/JSON divalidasi; konsumen tahan data lama rusak ──────────────────────────────────
def test_config_regex_and_json_validated_and_ocr_config_robust():
    import config_registry as cr
    import config_catalog_ops  # noqa: F401 — mendaftarkan kunci
    pats = cr._REGISTRY["receiving.client_po_patterns"]
    with pytest.raises(ValueError):
        cr.coerce(pats, [r"(?P<core>\d{3"])
    assert cr.coerce(pats, [r"(?P<core>\d{3,5})/(CST|SCB)/\d{4}"])
    with pytest.raises(ValueError):
        cr.coerce(cr._REGISTRY["receiving.ocr_price_table"], "{rusak")
    from services import dn_rules
    assert dn_rules.po_cores(["123/CST/2026"], [r"(?P<core>\d{3", r"(?P<core>\d{3,5})/CST/\d{4}"]) == ["123"]


# ─── B3b FRM-12 — perangkat baru tidak memalsukan detak ──────────────────────────────────────────────────────────
def test_new_device_has_no_fake_heartbeat():
    from services import rfid_service
    dev = run(rfid_service.create_device({"type": "gate", "warehouse_id": W, "code": f"FX3A-{TAG}"}, "Uji"))
    try:
        assert dev["status"] == "offline" and not dev.get("last_heartbeat")
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            run(rfid_service.update_device(dev["id"], {"status": "online"}, sim_entity=f"ent_tanpa_sim_{TAG}"))
    finally:
        DB.rfid_devices.delete_one({"id": dev["id"]})


# ─── B2a FLW-IN-05 — batal/tutup-kurang PO tidak membatalkan barang yang sudah diposting ─────────────────────────
def test_po_cancel_refused_when_goods_posted_and_close_keeps_qc_pending(adm):
    po_id = f"po_fx3a_b_{TAG}"
    DB.purchase_orders.insert_one({"id": po_id, "po_number": f"PO-FX3A-B-{TAG}", "status": "receiving", "entity_id": OWNER,
                                   "items": [{"product_id": P, "quantity": 50, "price": 0}], "created_at": OLD_TS})
    try:
        posted = _task("qc_pending", expected=25, received=25, po_id=po_id)
        waiting = _task("waiting_goods", expected=25, po_id=po_id)
        r = requests.post(f"{BASE}/purchase-orders/{po_id}/cancel", headers=adm)
        assert r.status_code == 409 and DB.purchase_orders.find_one({"id": po_id})["status"] == "receiving"
        from routers.purchase_orders_extra import cancel_open_inbound_tasks
        run(cancel_open_inbound_tasks(po_id, "Uji", "PO ditutup-kurang"))
        assert DB.wms_tasks.find_one({"id": waiting})["status"] == "cancelled"
        assert DB.wms_tasks.find_one({"id": posted})["status"] == "qc_pending"     # karantina tidak yatim
    finally:
        DB.purchase_orders.delete_one({"id": po_id})


# ─── B2a FLW-IN-13 (D4) — konversi baku tanpa barang supplier ────────────────────────────────────────────────────
def test_fixed_pair_conversion_allowed_without_supplier_item():
    from services.receiving_uom_service import is_fixed_pair
    assert run(is_fixed_pair("meter", "yard")) is True
    assert run(is_fixed_pair("Yard", "METER")) is True
    assert run(is_fixed_pair("cone", "kg")) is False


# ─── B2a FLW-IN-09 (D6) — roll retur lepas karantina diarahkan sesuai grade ──────────────────────────────────────
def test_released_return_rolls_routed_by_grade():
    from services.return_service import route_released_return_rolls
    w_r = f"wh_TFX3A_R_{TAG}"
    DB.warehouses.insert_one({"id": w_r, "code": f"TFX3AR-{TAG}", "name": f"TEST RETUR {TAG}", "active": True,
                              "sharing_mode": "shared", "entity_ids": [OWNER], "roles": ["return"],
                              "storage_rules": {"mode": "grade", "grades": ["B", "BS", "C"]}, "zones": []})
    try:
        b = _roll(4.0, None, wh=w_r, grade="B", journey={"stage": "received_transit"})
        a = _roll(4.0, None, wh=w_r, grade="A", journey={"stage": "received_transit"})
        out = run(route_released_return_rolls([a, b], {"id": "sret_x", "number": "SRET-X"}, "Uji"))
        assert out["stay"] == 1 and out["putaway"] == 1
        assert DB.inventory_rolls.find_one({"id": b})["journey"]["stage"] == "stored"          # B tetap di Gedung Retur
        ja = DB.inventory_rolls.find_one({"id": a})["journey"]
        assert ja["stage"] == "received_transit" and ja["return_routed"] == "putaway"        # A → gudang simpan (draf PA)
    finally:
        DB.warehouses.delete_one({"id": w_r})


# ─── B3b FRM-09 — alasan K-14 di jalur GRN (dulu `min_length=5` tanpa strip: 5 spasi lolos) ─────────────────────
def test_grn_reject_reason_spaces_rejected_by_model():
    from pydantic import ValidationError
    import schemas_goods_receipt as sg
    cases = [(sg.GRNReasonIn, {"expected_version": 1}), (sg.GRNResolveIn, {"expected_version": 1, "action": "accept_note"}),
             (sg.GRNModeIn, {"entity_id": OWNER, "mode": "grn"})]
    for m, base in cases:
        for bad in ("     ", ".....", "x"):
            with pytest.raises(ValidationError):
                m(**base, reason=bad)
        assert m(**base, reason=" Supplier salah kirim warna ").reason == "Supplier salah kirim warna"
