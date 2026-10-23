"""UAT 23 Okt (permintaan pemilik) — penyelesaian retur PER ROLL: outcome campuran (sebagian roll cutloss, sebagian
pengembalian dana / tukar barang / diskon) dan bertahap (P1, P2 …), satu Nota Kredit + satu jurnal per penyelesaian.

Jalankan: cd /app/backend && python -m pytest tests/test_uat23_roll_settlement.py -p no:randomly -n 0 -q
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
PID = "prod_batik_mega"   # satuan dasar yard
PRICE = 30000             # harga neto SO / yard


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


ADMIN, MD, FIN = _login("admin@kainnusantara.id"), _login("md@kainnusantara.id"), _login("finance@kainnusantara.id")


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    rets = [r["id"] for r in DB.sales_returns.find({"id": {"$regex": f"^sret_TEST_RS_{T}"}}, {"id": 1})]
    rolls = [r["id"] for r in DB.inventory_rolls.find({"$or": [{"id": {"$regex": f"^roll_TEST_RS_{T}"}},
                                                              {"return_id": {"$in": rets}}]}, {"id": 1})]
    DB.inventory_rolls.delete_many({"id": {"$in": rolls}})
    DB.inventory_movements.delete_many({"roll_id": {"$in": rolls}})
    DB.journal_entries.delete_many({"source_id": {"$regex": f"^sret_TEST_RS_{T}"}})
    DB.credit_notes.delete_many({"return_id": {"$in": rets}})
    DB.store_credit_ledger.delete_many({"ref_id": {"$regex": f"^sret_TEST_RS_{T}"}})
    DB.cash_transactions.delete_many({"ref_id": {"$regex": f"^sret_TEST_RS_{T}"}})
    DB.sales_returns.delete_many({"id": {"$in": rets}})
    DB.sales_orders.delete_many({"id": {"$regex": f"^so_TEST_RS_{T}"}})


def _seed(paid: bool, n=3, status="inspected"):
    """SO 3 roll × 100 yd @Rp30.000 + PPN 11%, retur 3 roll sudah diterima gudang & selesai QC (grade B)."""
    src = DB.sales_orders.find_one({"number": "KSC/SO-00003"}, {"_id": 0})
    tag = uuid.uuid4().hex[:4]
    so = f"so_TEST_RS_{T}_{tag}"
    DB.sales_orders.insert_one({**{k: src[k] for k in ("customer_id", "customer_name", "shipping_address_id", "entity_id")},
                                "id": so, "number": f"TEST_SO-{so}", "status": "done", "payment_term_code": "NET30",
                                "items": [{"product_id": PID, "quantity": 300, "base_quantity": 300, "line_total": 300 * PRICE}],
                                "ppn_rate": 11, "ppn_amount": 990000, "grand_total": 9990000, "qc_request": {"mode": "none"},
                                "payments": [{"amount": 9990000}] if paid else []})
    tmpl = DB.inventory_rolls.find_one({"product_id": PID, "owner_entity_id": "ent_ksc"}, {"_id": 0}) or {}
    rids, results, locs = [], {}, {}
    for i in range(n):
        rid = f"roll_TEST_RS_{T}_{tag}_{i}"
        DB.inventory_rolls.insert_one({**tmpl, "id": rid, "roll_no": f"TEST_RL-{tag}-{i}", "product_id": PID, "status": "delivered",
                                       "unit": "yard", "length": 100.0, "length_initial": 100.0, "length_remaining": 100.0,
                                       "owner_entity_id": "ent_ksc", "warehouse_id": "wh_jakarta", "unit_cost": 18000.0,
                                       "base_unit_cost": 18000.0, "grade": "A", "rfid_tag_id": None, "reserved_ref": None,
                                       "committed_to": None, "earmarked_for": None})
        rids.append(rid)
        results[rid] = {"roll_no": f"TEST_RL-{tag}-{i}", "grade": "B", "actual_qty": 100.0, "condition": "minor"}
        locs[rid] = {"stage": "arrived", "warehouse_id": "wh_jakarta"}
    ret = f"sret_TEST_RS_{T}_{tag}"
    DB.sales_returns.insert_one({"id": ret, "number": f"TEST_RET-RS-{tag}", "order_id": so, "order_number": f"TEST_SO-{so}",
                                 "entity_id": "ent_ksc", "customer_id": src["customer_id"], "customer_name": src["customer_name"],
                                 "return_type": "retur", "status": status, "roll_locations": locs,
                                 "items": [{"product_id": PID, "product_name": "TEST", "unit": "yard", "quantity_returned": 100.0 * n,
                                            "condition": "minor", "roll_ids": rids, "roll_qtys": {r: 100.0 for r in rids},
                                            "inspection": {"grade": "B", "accepted_qty": 100.0 * n, "roll_results": results,
                                                           "roll_actuals": {r: 100.0 for r in rids}}}]})
    return so, ret, rids


def _settle(ret, rolls, payout="store_credit", expect=200):
    r = requests.post(f"{BASE}/sales-returns/{ret}/roll-settlement", headers=ADMIN,
                      json={"rolls": [{"roll_id": k, "outcome": v} for k, v in rolls.items()], "payout": payout,
                            "decision_note": "uji per roll"})
    assert r.status_code == expect, r.text
    return r.json()


def _je(ret, ev):
    je = DB.journal_entries.find_one({"source_type": "sales_return", "source_id": f"{ret}:{ev['id']}"})
    assert je, "jurnal penyelesaian tidak ada"
    return {(ln["account_code"], "D" if ln["debit"] else "K"): round(ln["debit"] or ln["credit"], 2) for ln in je["lines"]}


def test_campuran_bertahap_cutloss_refund_lalu_tukar_barang():
    so, ret, (r1, r2, r3) = _seed(paid=True)
    c = requests.post(f"{BASE}/sales-returns/{ret}/cutloss", headers=MD, json={
        "product_id": PID, "roll_id": DB.inventory_rolls.find_one({"id": r1})["roll_no"], "defect_yard": 5, "treatment": "bs"})
    assert c.status_code == 200 and c.json()["roll_id"] == r1, c.text          # nomor roll klaim diterima
    d = requests.post(f"{BASE}/sales-returns/{ret}/compensation", headers=FIN,
                      json={"lines": [{"kind": "cutloss", "product_id": PID}], "note": "cutloss 5 yd"})
    assert d.status_code == 200, d.text
    st = requests.get(f"{BASE}/sales-returns/{ret}/roll-settlement", headers=ADMIN).json()
    opts = {r["roll_id"]: {o["value"] for o in r["options"] if o["ok"]} for r in st["rows"]}
    assert "cutloss" in opts[r1] and "cutloss" not in opts[r2] and "refund" in opts[r2]
    # P1 — roll 1 cutloss + roll 2 pengembalian dana (SO lunas → cutloss jadi saldo, refund ke kas)
    doc = _settle(ret, {r1: "cutloss", r2: "refund"})
    assert doc["status"] == "inspected" and len(doc["roll_outcomes"]) == 2
    ev1 = doc["settlements"][-1]
    p = ev1["plan"]
    assert p["net_amount"] == 5 * PRICE + 100 * PRICE and p["ppn_amount"] == round(p["net_amount"] * 0.11, 2)
    j = _je(ret, ev1)
    assert j[("4-1000", "D")] == p["net_amount"] and j[("2-1200", "D")] == p["ppn_amount"]
    assert j[("1-1100", "K")] == round(100 * PRICE * 1.11, 2)                 # refund tunai
    assert j[("2-1450", "K")] == round(5 * PRICE * 1.11, 2)                   # kompensasi cutloss jadi saldo
    # HPP balik ke stok hanya untuk roll refund (biaya rata-rata produk uji bisa 0 di DB uji → baris tidak terbentuk)
    assert j.get(("1-1300", "D"), 0.0) == j.get(("5-1000", "K"), 0.0) == p["cogs_amount"]
    assert all(r["cogs"] == 0 for r in p["rolls"] if r["outcome"] == "cutloss")
    assert DB.inventory_rolls.find_one({"id": r2})["status"] == "quarantine"
    assert DB.inventory_rolls.find_one({"id": r1})["status"] == "delivered"   # roll cutloss lewat pecah roll MD
    assert DB.cash_transactions.find_one({"ref_id": f"{ret}:{ev1['id']}", "direction": "out"})
    # roll yang sudah diputus tidak bisa diputus lagi
    _settle(ret, {r2: "store_credit"}, expect=400)
    # P2 — roll 3 tukar barang → retur selesai (campuran)
    doc = _settle(ret, {r3: "exchange"})
    assert doc["status"] == "settled" and doc["outcome"] == "mixed" and doc["exchange_pending"] is True
    assert len(doc["credit_note_ids"]) == 2
    ev2 = doc["settlements"][-1]
    assert _je(ret, ev2)[("2-1450", "K")] == doc["exchange_credit_open"] == round(100 * PRICE * 1.11, 2)
    ob = requests.get(f"{BASE}/sales-returns/{ret}/replacement", headers=ADMIN).json()["obligation"]
    assert [(x["qty_base"], x["roll_ids"]) for x in ob] == [(100.0, [r3])]
    # Jalur lama tertutup
    legacy = requests.post(f"{BASE}/sales-returns/{ret}/settle", headers=ADMIN, json={"outcome": "refund", "decision_note": "x"})
    assert legacy.status_code == 400
    # Koreksi: semua penyelesaian dibalik, roll kembali di pelanggan, retur batal
    rv = requests.post(f"{BASE}/sales-returns/{ret}/reverse", headers=ADMIN, json={"notes": "uji koreksi per roll"})
    assert rv.status_code == 200, rv.text
    assert rv.json()["status"] == "cancelled" and rv.json()["_reversal_summary"]["settlements"] == 2
    for ev in (ev1, ev2):
        assert DB.journal_entries.find_one({"source_type": "sales_return_reversal", "source_id": f"{ret}:{ev['id']}"})
    assert DB.inventory_rolls.find_one({"id": r2})["status"] == "delivered"
    assert not DB.credit_notes.find_one({"return_id": ret, "status": {"$ne": "void"}})


def test_so_belum_lunas_potong_tagihan_dulu_dan_tukar_tetap_berhak_pengganti():
    so, ret, (r1, r2) = _seed(paid=False, n=2)
    doc = _settle(ret, {r1: "refund", r2: "exchange"})
    p = doc["settlements"][-1]["plan"]
    assert [x["kind"] for x in p["split"]] == ["source_bill"] and p["bill_total"] == p["gross_amount"]
    assert doc["status"] == "credit_settled" or doc["status"] == "settled"
    assert doc["exchange_pending"] is True and doc["exchange_credit_open"] == 0      # nilai tukar memotong tagihan
    paid = sum(x["amount"] for x in DB.sales_orders.find_one({"id": so})["payments"])
    assert round(paid, 2) == p["gross_amount"]


def test_diskon_kurangi_piutang_ditolak_bila_so_lunas_dan_tolak_klaim_kirim_balik():
    so, ret, (r1, r2) = _seed(paid=True, n=2)
    d = requests.post(f"{BASE}/sales-returns/{ret}/compensation", headers=FIN, json={
        "lines": [{"kind": "discount", "product_id": PID, "qty": 10, "amount": 100000}], "note": "diskon noda"})
    assert d.status_code == 200, d.text
    pv = requests.post(f"{BASE}/sales-returns/{ret}/roll-settlement/preview", headers=ADMIN,
                       json={"rolls": [{"roll_id": r1, "outcome": "discount"}], "payout": ""}).json()
    assert "Jadi saldo" in pv["blocked"]
    doc = _settle(ret, {r1: "discount", r2: "reject"}, payout="refund")
    assert doc["status"] == "nego_settled"                        # tolak klaim tidak dihitung sebagai keluarga outcome
    assert doc["roll_outcomes"][r2]["back_pending"] and doc["roll_outcomes"][r1]["back_pending"]
    b = requests.post(f"{BASE}/sales-returns/{ret}/roll-settlement/back-shipment", headers=ADMIN, json={"roll_ids": [r1, r2]})
    assert b.status_code == 200 and len(b.json()["rolls"]) == 2, b.text
    assert not DB.sales_returns.find_one({"id": ret})["roll_outcomes"][r1]["back_pending"]
