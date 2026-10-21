"""COMM-04 lanjutan — tagihan vendor kampanye tanpa PO (keputusan owner 2026-10-16).

Diajukan Marketing/Admin → disetujui Finance/Manager → Dr Beban Pemasaran + PPN Masukan / Cr Hutang;
dibayar lewat Vendor Bill → Dr Hutang / Cr Kas. Realisasi anggaran = tagihan disetujui (tanpa PPN).
"""
import os

import pytest
import requests
from pymongo import MongoClient

B = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _h(email, pw="demo12345"):
    t = requests.post(f"{B}/auth/login", json={"email": email, "password": pw}, timeout=30).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": "ent_ksc"}


def _bal(code):
    tot = 0.0
    for je in DB.journal_entries.find({"entity_id": "ent_ksc", "lines.account_code": code}):
        tot += sum(ln.get("debit", 0) - ln.get("credit", 0) for ln in je["lines"] if ln["account_code"] == code)
    return round(tot, 2)


@pytest.fixture(scope="module")
def ctx():
    a, f, m, s = _h("admin@kainnusantara.id", "demo12345"), _h("finance@kainnusantara.id"), _h("manager@kainnusantara.id"), _h("sales@kainnusantara.id")
    c = requests.post(f"{B}/marketing/campaigns", json={"name": "TEST_COMM04B", "budget": 1000000}, headers=m).json()
    vendors = requests.get(f"{B}/marketing/vendor-options", headers=m).json()
    yield {"a": a, "f": f, "m": m, "s": s, "c": c, "v": vendors}
    bills = [b["id"] for b in DB.vendor_bills.find({"campaign_id": c["id"]})]
    cash = [x["id"] for x in DB.cash_transactions.find({"ref_id": {"$in": bills}})]
    DB.journal_entries.delete_many({"source_id": {"$in": bills + cash}})
    DB.cash_transactions.delete_many({"id": {"$in": cash}})
    DB.vendor_bills.delete_many({"id": {"$in": bills}})
    DB.notifications.delete_many({"ref": {"$in": [f"mkt_bill:{b}" for b in bills]}})
    DB.mkt_campaigns.delete_one({"id": c["id"]})


def test_vendor_options_exclude_group_entities(ctx):
    assert ctx["v"] and not any(v["id"].startswith("sup_grp_") for v in ctx["v"])


def test_bill_lifecycle_approve_pay(ctx):
    cid = ctx["c"]["id"]
    b0, h0, k0 = _bal("6-4700"), _bal("2-1100"), _bal("1-1100")
    r = requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills", headers=ctx["m"], json={
        "supplier_id": ctx["v"][0]["id"], "supplier_invoice_no": "TEST-INV-B1", "description": "Iklan Meta",
        "amount": 500000, "ppn_amount": 55000})
    assert r.status_code == 200, r.text
    bill = r.json()
    assert bill["status"] == "pending_approval" and _bal("6-4700") == b0           # belum dijurnal
    s = requests.get(f"{B}/marketing/campaigns/{cid}/costs", headers=ctx["m"]).json()
    assert s["pending_bills"] == 500000 and s["realized"] == 0
    assert requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills/{bill['id']}/approve", headers=ctx["s"]).status_code == 403
    assert requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills/{bill['id']}/approve", headers=ctx["m"]).status_code == 403  # SoD
    r = requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills/{bill['id']}/approve", headers=ctx["f"])
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    assert requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills/{bill['id']}/approve", headers=ctx["f"]).status_code == 409
    je = DB.journal_entries.find({"source_type": "vendor_bill", "source_id": bill["id"]})
    je = list(je)
    assert len(je) == 1
    lines = {ln["account_code"]: (ln["debit"], ln["credit"]) for ln in je[0]["lines"]}
    assert lines["6-4700"] == (500000, 0) and lines["1-1500"] == (55000, 0) and lines["2-1100"] == (0, 555000)
    s = requests.get(f"{B}/marketing/campaigns/{cid}/costs", headers=ctx["m"]).json()
    assert s["realized"] == 500000 and s["realized_bills"] == 500000 and s["remaining"] == 500000
    r = requests.post(f"{B}/vendor-bills/{bill['id']}/pay", headers=ctx["a"],
                      json={"amount": 555000, "cash_type": "kas_besar", "method": "transfer"})
    assert r.status_code == 200 and r.json()["status"] == "paid", r.text
    assert _bal("2-1100") == h0 and _bal("1-1100") == round(k0 - 555000, 2) and _bal("6-4700") == b0 + 500000
    s = requests.get(f"{B}/marketing/campaigns/{cid}/costs", headers=ctx["m"]).json()
    assert s["realized"] == 500000                                                # bayar tidak menambah realisasi


def test_duplicate_invoice_reject_and_validation(ctx):
    cid, sup = ctx["c"]["id"], ctx["v"][0]["id"]
    assert requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills", headers=ctx["m"], json={
        "supplier_id": sup, "supplier_invoice_no": "TEST-INV-B1", "description": "dup", "amount": 1}).status_code == 409
    assert requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills", headers=ctx["m"], json={
        "supplier_id": sup, "description": "nol", "amount": 0}).status_code == 400
    assert requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills", headers=ctx["m"], json={
        "supplier_id": "sup_grp_ksc_kanda", "description": "grup", "amount": 10}).status_code == 409
    assert requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills", headers=ctx["f"], json={
        "supplier_id": sup, "description": "finance tak bisa buat", "amount": 10}).status_code == 403
    b = requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills", headers=ctx["m"], json={
        "supplier_id": sup, "description": "Endorse", "amount": 100000}).json()
    assert requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills/{b['id']}/reject", headers=ctx["f"], json={"reason": "x"}).status_code == 400
    r = requests.post(f"{B}/marketing/campaigns/{cid}/vendor-bills/{b['id']}/reject", headers=ctx["f"], json={"reason": "vendor salah"})
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert DB.journal_entries.count_documents({"source_id": b["id"]}) == 0
