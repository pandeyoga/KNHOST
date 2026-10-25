"""Audit UI tahap 2 (UAT 24 Okt) — grup G1 Keuangan: uji tingkat layanan (tanpa HTTP).

Memakai event loop BERSAMA `tests/_shared_loop.py` (klien Motor modul `db` terikat ke loop pertama) dan data
uji terisolasi (entitas/akun/supplier berawalan TEST_G1_ + akhiran acak), dibersihkan di akhir tiap uji.
Jalankan: cd /app/backend && python -m pytest tests/test_audit2_g1_finance.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid

from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6]


# ─── G1-08 — kandidat akun pendapatan tidak boleh kosong (registri `revenue` vs COA `income`) ─────────────────
def test_g108_income_candidates_not_empty():
    from services import gl_mapping_registry as reg
    from services import gl_mapping_service as svc
    eid = f"ent_TEST_G1_{TAG}"
    accs = [{"code": "4-8801", "name": "TEST_G1 Pendapatan baru", "type": "income"},
            {"code": "4-8802", "name": "TEST_G1 Pendapatan lama", "type": "revenue"},   # alias lama
            {"code": "1-8803", "name": "TEST_G1 Aset", "type": "asset"}]
    DB.gl_accounts.insert_many([{**a, "id": f"acc_TEST_G1_{TAG}_{a['code']}", "entity_id": eid, "is_active": True,
                                 "is_postable": True} for a in accs])
    try:
        assert reg.require("penjualan.pendapatan")["allowed_types"] == ["income"]
        assert reg.TYPE_LABEL["income"] == "Pendapatan"
        cands = {c["code"]: c for c in run(svc.candidates("penjualan.pendapatan", eid))}
        assert "4-8801" in cands and "4-8802" in cands, cands.keys()
        assert "1-8803" not in cands
        assert cands["4-8802"]["type"] == "income"   # dinormalkan
        # semua kebutuhan berjenis pendapatan punya kandidat
        for e in reg.ENTRIES:
            if "income" in e["allowed_types"]:
                assert run(svc.candidates(e["key"], eid)), e["key"]
    finally:
        DB.gl_accounts.delete_many({"entity_id": eid})


# ─── G1-02 — Jadwal Tukar Faktur: supplier milik grup ikut & "belum ditagih" = tab GR Belum Ditagih ─────────
def test_g102_schedules_include_group_supplier_and_match_unbilled_tab():
    from services import contra_bon_reminder as rem
    from services import contra_bon_service as cbs
    eid, other = f"ent_TEST_G1_{TAG}", f"ent_TEST_G1o_{TAG}"
    sup_grp, sup_own = f"sup_TEST_G1g_{TAG}", f"sup_TEST_G1e_{TAG}"
    DB.suppliers.insert_many([
        {"id": sup_grp, "name": f"TEST_G1 Supplier Grup {TAG}", "entity_id": "all"},
        {"id": sup_own, "name": f"TEST_G1 Supplier PT {TAG}", "entity_id": eid},
    ])
    pos = [  # PO entitas aktif (diterima sebagian, belum ditagih) + PO PT lain untuk supplier grup yang sama
        {"id": f"po_TEST_G1a_{TAG}", "po_number": f"TEST/PO-{TAG}-A", "supplier_id": sup_grp, "entity_id": eid,
         "status": "received", "items": [{"product_id": "p1", "received_qty": 10, "price": 1000}]},
        {"id": f"po_TEST_G1b_{TAG}", "po_number": f"TEST/PO-{TAG}-B", "supplier_id": sup_own, "entity_id": eid,
         "status": "partially_received", "items": [{"product_id": "p2", "received_qty": 4, "price": 2500}]},
        {"id": f"po_TEST_G1c_{TAG}", "po_number": f"TEST/PO-{TAG}-C", "supplier_id": sup_grp, "entity_id": other,
         "status": "received", "items": [{"product_id": "p3", "received_qty": 7, "price": 9999}]},
    ]
    DB.purchase_orders.insert_many([dict(p) for p in pos])
    try:
        res = run(rem.schedules(None, eid))
        by_sup = {r["supplier_id"]: r for r in res["rows"]}
        assert sup_grp in by_sup, "supplier milik grup (entity_id=all) harus ikut daftar jadwal"
        assert sup_own in by_sup
        assert by_sup[sup_grp]["unbilled_gr_value"] == 10000 and by_sup[sup_grp]["unbilled_gr_po_count"] == 1
        assert by_sup[sup_own]["unbilled_gr_value"] == 10000
        tab = run(cbs.unbilled_receipts(None, entity_id=eid))
        mine = [r for r in tab["rows"] if r["supplier_id"] in (sup_grp, sup_own)]
        assert round(sum(r["unbilled_value"] for r in mine), 2) == 20000
        assert sum(by_sup[s]["unbilled_gr_value"] for s in (sup_grp, sup_own)) == 20000
    finally:
        DB.suppliers.delete_many({"id": {"$in": [sup_grp, sup_own]}})
        DB.purchase_orders.delete_many({"id": {"$in": [p["id"] for p in pos]}})


# ─── G1-12 — Selisih Pembayaran "putus belakangan": satu sumber angka, boundary tidak boleh 0 ───────────────
def _pv_fixture(monkeypatch, outstanding):
    from services import payment_variance_service as pvs
    pol = {"tolerance": 5000.0, "underpay_default": "outstanding", "overpay_default": "deposit",
           "writeoff_requires_approval": False, "writeoff_approver_role": "manager", "writeoff_max_amount": 0.0,
           "reschedule_days": 14, "refund_method": "transfer", "ap_tolerance": 0.0}

    async def fake_policy(entity_id="", customer_id=""):
        return dict(pol)

    async def fake_targets(customer_id, allocations, as_of):
        return {"targets": [{"order_id": "so_T", "number": "TEST/SO-1", "entity_id": "ent_ksc",
                             "outstanding": outstanding, "expected": outstanding, "plan_id": "",
                             "due_now": outstanding}], "others": []}
    monkeypatch.setattr(pvs, "variance_policy", fake_policy)
    monkeypatch.setattr(pvs, "_targets", fake_targets)
    return pvs


def test_g112_allocation_without_amount_is_target_not_zero(monkeypatch):
    pvs = _pv_fixture(monkeypatch, 169830.0)
    a = run(pvs.pre_assess(f"cust_TEST_G1_{TAG}", 3331, [{"order_id": "so_T"}]))
    # dulu: capacity 0 → "seharusnya Rp 0", arah LEBIH bayar Rp 3.331
    assert a["capacity"] == 169830.0
    assert a["direction"] == "under" and a["delta"] == -166499.0
    assert a["boundary"] == 169830.0 and a["boundary"] > 0
    assert any("KURANG" in e for e in a["explain"]) and not any("LEBIH" in e for e in a["explain"])
    # alokasi bernominal tetap dihormati (kelebihan = lebih bayar)
    b = run(pvs.pre_assess(f"cust_TEST_G1_{TAG}", 200000, [{"order_id": "so_T", "amount": 150000}]))
    assert b["capacity"] == 150000.0 and b["direction"] == "over" and b["delta"] == 50000.0


def test_g112_stored_variance_is_single_source(monkeypatch):
    pvs = _pv_fixture(monkeypatch, 166499.0)   # takar ulang SESUDAH kwitansi dialokasikan
    stored = {"expected": 169830, "funds": 3331, "capacity": 3331, "boundary": 169830,
              "boundary_label": "tagihan yang jatuh tempo", "delta": -166499, "direction": "under",
              "explain": ["Uang masuk Rp 3.331", "Selisih Rp 166.499 KURANG bayar"]}
    fresh = run(pvs.pre_assess(f"cust_TEST_G1_{TAG}", 3331, [{"order_id": "so_T"}]))
    a = pvs.apply_stored_variance(fresh, stored)
    assert a["expected"] == 169830.0 and a["boundary"] == 169830.0 and a["delta"] == -166499.0
    assert a["direction"] == "under" and a["explain"] == stored["explain"]
    assert [o["value"] for o in a["options"]] == ["outstanding", "reschedule", "writeoff"]
    # blok lama tanpa boundary → pakai expected, bukan 0
    old = pvs.apply_stored_variance(fresh, {**stored, "boundary": 0})
    assert old["boundary"] == 169830.0


# ─── G1-13 — Control Tower: piutang di luar papan sales dihitung terpisah (definisi papan tetap, K-01) ────────
def test_g113_ar_outside_board_counts_customers_without_active_sales(monkeypatch):
    from services import home_service as hs
    eid = f"ent_TEST_G1_{TAG}"
    custs = [{"id": f"cust_TEST_G1a_{TAG}", "name": "TEST_G1 ber-sales", "entity_id": eid, "assigned_sales_id": "user_TEST_aktif"},
             {"id": f"cust_TEST_G1b_{TAG}", "name": "TEST_G1 tanpa sales", "entity_id": eid},
             {"id": f"cust_TEST_G1c_{TAG}", "name": "TEST_G1 sales nonaktif", "entity_id": eid, "assigned_sales_id": "user_TEST_off"}]
    DB.customers.insert_many([dict(c) for c in custs])
    credit = {custs[0]["id"]: (500.0, 100.0), custs[1]["id"]: (1193250.0, 1193250.0), custs[2]["id"]: (300.0, 0.0)}

    async def fake_credit(c, entity_id=None):
        ar, od = credit[c["id"]]
        return {"ar_outstanding": ar, "overdue_amount": od}
    monkeypatch.setattr(hs, "compute_customer_credit", fake_credit)
    try:
        out = run(hs._ar_outside_board({"user_TEST_aktif"}, eid))
        assert out["customers"] == 2 and out["outstanding"] == 1193550.0
        assert out["overdue"] == 1193250.0 and out["overdue_customers"] == 1
    finally:
        DB.customers.delete_many({"id": {"$in": [c["id"] for c in custs]}})


# ─── G1-31 — Saldo Antar-PT: angka tampil = dokumen terbuka saat ini (cache basi tidak dipakai) ─────────────
def test_g131_list_accounts_uses_live_open_documents():
    from services import interco_service as ics
    s_ent, b_ent = f"ent_TEST_G1s_{TAG}", f"ent_TEST_G1b_{TAG}"
    docs = [
        {"id": f"ict_TEST_G1a_{TAG}", "role": "seller", "seller_entity_id": s_ent, "buyer_entity_id": b_ent,
         "entity_id": s_ent, "status": "received", "grand_total": 6993000, "settled_amount": 0, "returned_amount": 0},
        {"id": f"ict_TEST_G1b_{TAG}", "role": "seller", "seller_entity_id": s_ent, "buyer_entity_id": b_ent,
         "entity_id": s_ent, "status": "draft", "grand_total": 62160, "settled_amount": 0},
    ]
    stale = {"id": f"ica_TEST_G1_{TAG}_ap", "entity_id": b_ent, "from_entity_id": b_ent, "to_entity_id": s_ent,
             "seller_entity_id": s_ent, "buyer_entity_id": b_ent, "role": "payable", "open_count": 2,
             "outstanding": 7015200.0, "last_activity_at": "2026-10-25"}
    DB.interco_transactions.insert_many([dict(d) for d in docs])
    DB.interco_accounts.insert_one(dict(stale))
    try:
        rows = [r for r in run(ics.list_accounts([b_ent])) if r["id"] == stale["id"]]
        assert rows and rows[0]["outstanding"] == 6993000.0 and rows[0]["open_count"] == 1
        assert rows[0]["cached_outstanding"] == 7015200.0
        # cache tidak ditulis oleh GET
        assert DB.interco_accounts.find_one({"id": stale["id"]})["outstanding"] == 7015200.0
    finally:
        DB.interco_transactions.delete_many({"id": {"$in": [d["id"] for d in docs]}})
        DB.interco_accounts.delete_many({"id": stale["id"]})


# ─── G1-38 — Dasbor Keuangan: "Hutang Terbesar" per pemasok, bukan per tagihan ───────────────────────────────
def test_g138_top_ap_grouped_per_supplier():
    from services import finance_tower_service as fts
    eid = f"ent_TEST_G1_{TAG}"
    bills = [{"id": f"vb_TEST_G1_{TAG}_{i}", "bill_number": f"TEST/VB-{TAG}-{i}", "entity_id": eid, "status": "posted",
              "supplier_id": sid, "supplier_name": name, "grand_total": amt, "amount_paid": 0,
              "due_date": "2026-10-01"}
             for i, (sid, name, amt) in enumerate([("sup_A", "CV Printing Sablon Cimahi", 100.0),
                                                   ("sup_A", "CV Printing Sablon Cimahi", 200.0),
                                                   ("sup_A", "CV Printing Sablon Cimahi", 300.0),
                                                   ("sup_B", "PT Lain", 250.0)])]
    DB.vendor_bills.insert_many([dict(b) for b in bills])
    try:
        out = run(fts._ap_summary({"entity_id": eid}))
        parties = [t["party"] for t in out["top"]]
        assert parties.count("CV Printing Sablon Cimahi") == 1, parties
        a = next(t for t in out["top"] if t["party"] == "CV Printing Sablon Cimahi")
        assert a["amount"] == 600.0 and a["bill_count"] == 3
        assert out["top"][0]["party"] == "CV Printing Sablon Cimahi" and out["outstanding"] == 850.0
    finally:
        DB.vendor_bills.delete_many({"id": {"$in": [b["id"] for b in bills]}})
