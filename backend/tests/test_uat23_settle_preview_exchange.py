"""UAT 23 Okt — modal "Selesaikan Retur": (1) pratinjau nilai keputusan (`/settle-preview`) SAMA dengan Nota Kredit &
jurnal yang benar-benar terbit; (2) "Tukar Barang" sebagai pilihan keputusan → Store Credit + tipe penggantian
(tercatat), lalu pesanan pengganti bisa dibuat; ditolak bila kebijakan retur tidak mengizinkan penggantian.

Jalankan: cd /app/backend && python -m pytest tests/test_uat23_settle_preview_exchange.py -p no:randomly -n 0 -q
"""
import os
import uuid

import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
T = uuid.uuid4().hex[:6]
PID = "prod_batik_mega"   # satuan dasar yard, stok tersedia di KSC (sama dengan tes LN-090)


def _login(email, pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


ADMIN = _login("admin@kainnusantara.id")


def _seed(paid: bool, rtype="retur", allowed_types=None):
    """SO 20 yd × Rp30.000 + PPN 11% (lunas / belum) dan retur 10 yd yang sudah selesai QC."""
    src = DB.sales_orders.find_one({"number": "KSC/SO-00003"}, {"_id": 0})
    so = f"so_TEST_SP_{T}_{uuid.uuid4().hex[:4]}"
    DB.sales_orders.insert_one({**{k: src[k] for k in ("customer_id", "customer_name", "shipping_address_id", "entity_id")},
                                "id": so, "number": f"TEST_SO-{so}", "status": "done", "payment_term_code": "NET30",
                                "items": [{"product_id": PID, "quantity": 20, "base_quantity": 20, "line_total": 600000}],
                                "ppn_rate": 11, "ppn_amount": 66000, "grand_total": 666000, "qc_request": {"mode": "none"},
                                "payments": [{"amount": 666000}] if paid else []})
    rid = f"sr_TEST_SP_{T}_{uuid.uuid4().hex[:4]}"
    doc = {"id": rid, "number": f"TEST_RET-SP-{rid[-4:]}", "order_id": so, "order_number": f"TEST_SO-{so}",
           "entity_id": "ent_ksc", "customer_id": src["customer_id"], "customer_name": src["customer_name"],
           "return_type": rtype, "status": "inspected",
           "items": [{"product_id": PID, "product_name": "TEST", "unit": "yard", "quantity_returned": 10.0,
                      "condition": "ok", "inspection": {"accepted_qty": 10.0, "grade": "A"}}]}
    if allowed_types is not None:
        doc["policy_snapshot"] = {"allowed_return_types": allowed_types}
    DB.sales_returns.insert_one(doc)
    return so, rid


def _preview(rid, **body):
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle-preview", headers=ADMIN, json={"outcome": "store_credit", **body})
    assert r.status_code == 200, r.text
    return r.json()


def test_preview_sama_dengan_nota_kredit_dan_jurnal_tukar_barang():
    _, rid = _seed(paid=True)
    pv = _preview(rid, exchange=True)
    assert pv["net_amount"] == 300000 and pv["ppn_amount"] == 33000 and pv["gross_amount"] == 333000
    assert [(x["kind"], x["amount"]) for x in pv["split"]] == [("store_credit", 333000)]   # SO lunas → semua jadi saldo
    assert pv["source_bill_checked"] is True and not pv["blocked"]
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN, json={
        "outcome": "store_credit", "exchange": True, "decision_note": "Tukar barang — uji pratinjau"})
    assert r.status_code == 200, r.text
    doc = DB.sales_returns.find_one({"id": rid})
    assert doc["status"] == "credit_settled" and doc["return_type"] == "penggantian"
    assert doc["return_type_history"][0]["from"] == "retur" and doc["decision"]["exchange"]["to"] == "penggantian"
    cn = DB.credit_notes.find_one({"id": doc["credit_note_id"]})
    assert cn["gross_amount"] == pv["gross_amount"] and cn["net_amount"] == pv["net_amount"] and cn["return_type"] == "penggantian"
    je = DB.journal_entries.find_one({"id": cn["journal_entry_id"]})
    posted = sorted((ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in je["lines"])
    preview = sorted((ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in pv["journal"])
    assert posted == preview
    # Pesanan pengganti kini terbuka untuk retur yang awalnya bertipe "retur".
    rp = requests.post(f"{BASE}/sales-returns/{rid}/replacement-order", headers=ADMIN,
                       json={"items": [{"product_id": PID, "qty_yard": 12}]})
    assert rp.status_code == 200, rp.text
    assert rp.json()["summary"]["to_bill"] > 0     # pengganti lebih banyak → selisih ditagih
    # Stok uji tidak boleh habis oleh putaran tes berulang (tes LN-090 memakai produk yang sama).
    requests.post(f"{BASE}/sales-orders/{rp.json()['order']['id']}/cancel", headers=ADMIN, json={"reason": "TEST bersihkan pengganti"})


def test_preview_so_belum_lunas_potong_tagihan_dulu():
    _, rid = _seed(paid=False)
    pv = _preview(rid)
    assert [(x["kind"], x["amount"]) for x in pv["split"]] == [("source_bill", 333000)]
    assert any(ln["account_code"] == "1-1200" and ln["credit"] == 333000 for ln in pv["journal"])


def test_nego_tanpa_keputusan_finance_diblokir_di_pratinjau():
    _, rid = _seed(paid=True)
    pv = _preview(rid, outcome="nego")
    assert "Finance" in pv["blocked"]


def test_tukar_barang_ditolak_bila_kebijakan_tidak_mengizinkan():
    _, rid = _seed(paid=True, allowed_types=["retur", "bs"])
    assert "tukar barang" in _preview(rid, exchange=True)["blocked"]
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN, json={
        "outcome": "store_credit", "exchange": True, "decision_note": "uji kebijakan"})
    assert r.status_code == 409, r.text
    assert DB.sales_returns.find_one({"id": rid})["status"] == "inspected"
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=ADMIN, json={
        "outcome": "refund", "exchange": True, "decision_note": "uji outcome"})
    assert r.status_code == 400 and "Store Credit" in r.text
