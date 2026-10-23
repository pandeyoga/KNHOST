"""UAT 23 Okt — temuan simulasi keputusan retur (cutloss · diskon · tukar barang):

1. Pecah roll cutloss: roll yang sudah diterima gudang lewat Perjalanan Retur masih `delivered` (Nego tidak
   me-restock) → dulu tidak pernah bisa dipecah. Kini masuk gudang dulu (Dr Persediaan / Cr HPP), lalu dipecah.
2. Nego "kurangi piutang SO asal" memotong sisa tagihan SO (dulu hanya GL 1-1200); melebihi sisa tagihan → 409.
3. Diskon dari foto (barang tidak kembali): SPK QC retur yang lahir saat ACC ditutup, tidak menggantung.
4. Pesanan pengganti memakai grade SAAT DIJUAL (return_history.grade_before), bukan grade hasil QC.
5. Lepas karantina: kerugian turun grade dihitung dari grade saat dijual (A→B), bukan B→B.

Jalankan: cd /app/backend && python -m pytest tests/test_uat23_retur_keputusan.py -p no:randomly -n 0 -q
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
PID = "prod_batik_mega"   # satuan dasar yard (sama dengan tes LN-090)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    """Roll uji tidak boleh tertinggal sebagai stok (tes LN-090 memilih roll tersedia produk yang sama)."""
    yield
    rolls = [r["id"] for r in DB.inventory_rolls.find({"$or": [{"id": {"$regex": "^roll_TEST_U23_"}},
                                                              {"cutloss_piece.return_id": {"$regex": "^sret_TEST_U23_"}}]}, {"id": 1})]
    DB.inventory_rolls.delete_many({"id": {"$in": rolls}})
    DB.inventory_movements.delete_many({"roll_id": {"$in": rolls}})
    DB.return_grade_impairments.delete_many({"return_id": {"$regex": "^sret_TEST_U23_"}})
    DB.journal_entries.delete_many({"source_type": {"$in": ["return_cutloss", "return_grade_impairment"]},
                                    "source_id": {"$regex": "roll_TEST_U23_|sret_TEST_U23_"}})
    DB.inspections.delete_many({"id": {"$regex": "^ins_TEST_U23_"}})


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


ADMIN = _login("admin@kainnusantara.id")
MD = _login("md@kainnusantara.id")


def _so(paid: bool) -> str:
    src = DB.sales_orders.find_one({"number": "KSC/SO-00003"}, {"_id": 0})
    so = f"so_TEST_U23_{T}_{uuid.uuid4().hex[:4]}"
    DB.sales_orders.insert_one({**{k: src[k] for k in ("customer_id", "customer_name", "shipping_address_id", "entity_id")},
                                "id": so, "number": f"TEST_SO-{so}", "status": "done", "payment_term_code": "NET30",
                                "items": [{"product_id": PID, "quantity": 20, "base_quantity": 20, "line_total": 600000}],
                                "ppn_rate": 11, "ppn_amount": 66000, "grand_total": 666000, "qc_request": {"mode": "none"},
                                "payments": [{"amount": 666000}] if paid else []})
    return so


def _ret(so: str, status: str, **extra) -> str:
    src = DB.sales_orders.find_one({"id": so}, {"_id": 0})
    rid = f"sret_TEST_U23_{T}_{uuid.uuid4().hex[:4]}"
    DB.sales_returns.insert_one({"id": rid, "number": f"TEST_RET-U23-{rid[-4:]}", "order_id": so, "order_number": src["number"],
                                 "entity_id": "ent_ksc", "customer_id": src["customer_id"], "customer_name": src["customer_name"],
                                 "return_type": "retur", "status": status,
                                 "items": [{"product_id": PID, "product_name": "TEST", "unit": "yard", "quantity_returned": 10.0,
                                            "condition": "ok"}], **extra})
    return rid


def _roll(status: str, **extra) -> dict:
    src = DB.inventory_rolls.find_one({"status": "available", "owner_entity_id": "ent_ksc", "unit": "yard",
                                       "length_remaining": {"$gte": 100}, "unit_cost": {"$gt": 0}}, {"_id": 0})
    assert src, "butuh roll yard ent_ksc ≥100"
    roll = {**src, "id": f"roll_TEST_U23_{T}_{uuid.uuid4().hex[:4]}", "roll_no": f"TEST_RL-U23-{uuid.uuid4().hex[:4]}",
            "status": status, "length_remaining": 120.0, "length": 120.0, "length_initial": 120.0, "rfid_tag_id": None,
            "weight_kg": 24.0, **extra}
    DB.inventory_rolls.insert_one(dict(roll))
    return roll


def _discount(rid: str, amount: float, evidence=None):
    DB.sales_returns.update_one({"id": rid}, {"$set": {"compensation": {
        "status": "decided", "total": amount, "note": "uji", "decided_by": "TEST",
        "lines": [{"kind": "discount", "product_id": PID, "product_name": "TEST", "unit": "yard", "qty": 2,
                   "amount": amount, "evidence_ids": evidence or []}]}}})


def test_pecah_roll_cutloss_yang_masih_delivered_masuk_gudang_dulu():
    so = _so(paid=False)
    roll = _roll("delivered", warehouse_id="wh_jakarta")
    cost = float(roll["unit_cost"])
    rid = _ret(so, "inspected")
    DB.sales_returns.update_one({"id": rid}, {"$set": {"items.0.quantity_returned": 120.0, "items.0.roll_ids": [roll["id"]]}})
    r = requests.post(f"{BASE}/sales-returns/{rid}/cutloss", headers=MD, json={
        "product_id": PID if roll["product_id"] == PID else roll["product_id"], "roll_id": roll["id"],
        "defect_from": 45, "defect_to": 60, "treatment": "bs"})
    if roll["product_id"] != PID:   # baris retur mengikuti produk roll uji
        DB.sales_returns.update_one({"id": rid}, {"$set": {"items.0.product_id": roll["product_id"]}})
        r = requests.post(f"{BASE}/sales-returns/{rid}/cutloss", headers=MD, json={
            "product_id": roll["product_id"], "roll_id": roll["id"], "defect_from": 45, "defect_to": 60, "treatment": "bs"})
    assert r.status_code == 200, r.text
    ctl = r.json()["id"]
    # Belum discan terima → ditolak dengan arahan yang jelas.
    sp = requests.post(f"{BASE}/sales-returns/{rid}/cutloss/{ctl}/split", headers=MD)
    assert sp.status_code == 400 and "belum diterima gudang" in sp.text, sp.text
    DB.sales_returns.update_one({"id": rid}, {"$set": {f"roll_locations.{roll['id']}": {
        "stage": "arrived", "warehouse_id": "wh_jakarta"}}})
    sp = requests.post(f"{BASE}/sales-returns/{rid}/cutloss/{ctl}/split", headers=MD)
    assert sp.status_code == 200, sp.text
    assert [(p["kind"], p["qty"]) for p in sp.json()["pieces"]] == [("good", 45), ("defect", 15), ("good", 60)]
    parent = DB.inventory_rolls.find_one({"id": roll["id"]})
    assert parent["cutloss_intake"]["return_id"] == rid and parent["warehouse_id"] == "wh_jakarta"
    je = DB.journal_entries.find_one({"source_type": "return_cutloss", "source_id": f"{ctl}:{roll['id']}:intake"})
    assert je, "jurnal roll masuk gudang tidak ada"
    dr = {ln["account_code"]: ln["debit"] for ln in je["lines"] if ln["debit"]}
    cr = {ln["account_code"]: ln["credit"] for ln in je["lines"] if ln["credit"]}
    assert dr == {"1-1300": round(120 * cost, 2)} and cr == {"5-1000": round(120 * cost, 2)}
    sj = requests.post(f"{BASE}/sales-returns/{rid}/cutloss/{ctl}/return-shipment", headers=MD)
    assert sj.status_code == 200, sj.text


def test_nego_kurangi_piutang_so_asal_memotong_sisa_tagihan():
    so = _so(paid=False)
    rid = _ret(so, "inspected")
    _discount(rid, 60000)
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN,
                      json={"outcome": "nego", "payout": "", "decision_note": "uji potong tagihan"})
    assert r.status_code == 200, r.text
    doc = DB.sales_orders.find_one({"id": so})
    assert round(sum(p.get("amount", 0) for p in doc.get("payments") or []), 2) == 66600   # 60.000 + PPN 11%


def test_nego_kurangi_piutang_ditolak_bila_so_asal_sudah_lunas():
    so = _so(paid=True)
    rid = _ret(so, "inspected")
    _discount(rid, 60000)
    pv = requests.post(f"{BASE}/sales-returns/{rid}/settle-preview", headers=ADMIN, json={"outcome": "nego", "payout": ""}).json()
    assert "Jadi saldo" in pv["blocked"]
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN,
                      json={"outcome": "nego", "payout": "", "decision_note": "uji lunas"})
    assert r.status_code == 409, r.text
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN,
                      json={"outcome": "nego", "payout": "store_credit", "decision_note": "uji lunas → saldo"})
    assert r.status_code == 200, r.text


def test_diskon_foto_menutup_spk_qc_yang_menggantung():
    so = _so(paid=True)
    att = f"att_TEST_U23_{T}"
    rid = _ret(so, "approved", attachments=[{"id": att, "filename": "noda.jpg", "content_type": "image/jpeg", "is_deleted": False}])
    _discount(rid, 50000, [att])
    spk = f"ins_TEST_U23_{T}_{uuid.uuid4().hex[:4]}"
    DB.inspections.insert_one({"id": spk, "number": f"TEST_INS-{spk[-4:]}", "kind": "return_customer", "ref_doc_id": rid,
                               "ref_doc_type": "sales_return", "entity_id": "ent_ksc", "status": "draft",
                               "lines": [{"id": "ln1", "product_id": PID, "quantity": 10}], "history": []})
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN,
                      json={"outcome": "nego", "payout": "store_credit", "decision_note": "diskon dari foto"})
    assert r.status_code == 200, r.text
    doc = DB.inspections.find_one({"id": spk})
    assert doc["status"] == "closed" and "foto" in doc["closed_reason"]


def test_pengganti_memakai_grade_saat_dijual_dan_karantina_mencatat_kerugian_turun_grade():
    so = _so(paid=True)
    rid = _ret(so, "credit_settled", return_type="penggantian")
    roll = _roll("quarantine", product_id=PID, grade="B", return_id=rid, origin_type="return", unit_cost=18000.0,
                 base_unit_cost=18000.0, return_history=[{"return_id": rid, "grade_before": "A", "grade_after": "B"}])
    DB.sales_returns.update_one({"id": rid}, {"$set": {"items.0.roll_ids": [roll["id"]],
                                                      "items.0.inspection": {"accepted_qty": 10.0, "grade": "B"}}})
    ob = requests.get(f"{BASE}/sales-returns/{rid}/replacement", headers=ADMIN).json()["obligation"][0]
    assert ob["sold_grade"] == "A"                       # dulu "B" → pengganti mencari stok grade B
    r = requests.post(f"{BASE}/sales-returns/{rid}/quarantine/release", headers=ADMIN,
                      json={"decisions": [{"roll_id": roll["id"], "action": "release", "grade": "B"}], "notes": "uji"})
    assert r.status_code == 200, r.text
    imp = DB.return_grade_impairments.find_one({"return_id": rid, "roll_id": roll["id"]})
    assert imp and imp["grade_before"] == "A" and imp["grade_after"] == "B" and imp["amount"] > 0
    assert DB.journal_entries.find_one({"source_type": "return_grade_impairment", "source_id": f"{rid}:{roll['id']}"})
