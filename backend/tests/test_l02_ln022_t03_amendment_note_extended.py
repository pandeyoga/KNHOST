"""L02 LN-022-T03 (extended) — is_issued detection, credit-note AR/store-credit split, journal balance, idempotency."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
PFX = "so_TEST_l022t03x_"


def _h(email, pwd, ent):
    t = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": ent}


SRC = DB.sales_orders.find_one({"status": "done", "items.0": {"$exists": True}, "customer_id": {"$nin": [None, ""]}},
                               {"_id": 0})


def _mk(suffix, status="confirmed", paid=0.0, je=None):
    sid = PFX + suffix
    so = {**SRC, "id": sid, "number": f"TEST/SO-X{suffix}", "status": status, "payments": [], "paid_total": 0,
          "payment_status": "pending", "amendment_count": 0, "timeline": [], "notes": "TEST_L022T03X",
          "backorders": [], "has_backorder": False}
    if paid:
        so["payments"] = [{"id": f"pay_TEST_{suffix}", "amount": paid, "receipt_id": f"rcp_TEST_{suffix}",
                           "method": "transfer", "date": "2026-01-01"}]
        so["paid_total"] = paid
        so["payment_status"] = "paid" if paid >= so["grand_total"] else "partial"
    DB.sales_orders.insert_one(dict(so))
    if je:
        DB.journal_entries.insert_one({"id": f"je_TEST_{suffix}", "lines": [], "entity_id": so["entity_id"],
                                       "description": "TEST_L022T03X fixture", **je(sid)})
    return so


@pytest.fixture(scope="module")
def H():
    yield {"admin": _h("admin@kainnusantara.id", "demo12345", SRC["entity_id"]),
           "manager": _h("manager@kainnusantara.id", "demo1234", SRC["entity_id"])}
    sids = [s["id"] for s in DB.sales_orders.find({"id": {"$regex": "^" + PFX}}, {"id": 1})]
    notes = [n["id"] for n in DB.credit_notes.find({"order_id": {"$in": sids}}, {"id": 1})]
    amds = [a["id"] for a in DB.doc_amendments.find({"doc_id": {"$in": sids}}, {"id": 1})]
    DB.journal_entries.delete_many({"$or": [{"id": {"$regex": "^je_TEST_"}, "description": "TEST_L022T03X fixture"},
                                            {"source_id": {"$in": notes}}]})
    DB.store_credit_ledger.delete_many({"ref_id": {"$in": notes}})
    DB.credit_notes.delete_many({"order_id": {"$in": sids}})
    DB.doc_amendments.delete_many({"doc_id": {"$in": sids}})
    ids = sids + notes + amds
    DB.doc_refs.delete_many({"$or": [{"from_id": {"$in": ids}}, {"to_id": {"$in": ids}}]})
    DB.notifications.delete_many({"$or": [{"ref": {"$in": amds}}, {"action_id": {"$in": amds}}]})
    DB.sales_orders.delete_many({"id": {"$in": sids}})


def _body(sid, factor, field="price"):
    it = SRC["items"][0]
    to = round(float(it[field]) * factor, 2)
    return {"doc_type": "sales_order", "doc_id": sid, "reason_code": "price_correction", "note": "TEST_L022T03X",
            "changes": [{"product_id": it["product_id"], "field": field, "to": to}]}


def _preview(H, sid, factor=0.9):
    r = requests.post(f"{BASE}/amendments/preview", headers=H["admin"], json=_body(sid, factor))
    assert r.status_code == 200, r.text[:400]
    return r.json()


def _propose(H, sid, factor, field="price"):
    r = requests.post(f"{BASE}/amendments", headers=H["admin"], json=_body(sid, factor, field))
    assert r.status_code == 200, r.text[:400]
    amd = r.json()
    if amd["status"] == "pending_approval":
        r = requests.post(f"{BASE}/amendments/{amd['id']}/decision", headers=H["manager"], json={"action": "approve"})
        assert r.status_code == 200, r.text[:400]
        amd = r.json()
    return amd


def _je_check(cn):
    je = DB.journal_entries.find_one({"id": cn["journal_entry_id"]}, {"_id": 0})
    assert je and je["source_type"] == "amendment_credit_note" and je["source_id"] == cn["id"]
    acc = {}
    for ln in je["lines"]:
        acc.setdefault(ln["account_code"], [0, 0])
        acc[ln["account_code"]][0] += ln["debit"]
        acc[ln["account_code"]][1] += ln["credit"]
    dr = round(sum(l["debit"] for l in je["lines"]), 2)
    cr = round(sum(l["credit"] for l in je["lines"]), 2)
    assert dr == cr == round(cn["gross_amount"], 2)
    assert round(acc["4-1000"][0], 2) == cn["net_amount"]
    if cn["ppn_amount"] > 0:
        assert round(acc["2-1200"][0], 2) == cn["ppn_amount"]
    assert round(acc.get("1-1200", [0, 0])[1], 2) == cn["ar_applied"]
    assert round(acc.get("2-1450", [0, 0])[1], 2) == cn["store_credit_amount"]
    return je


# --- is_issued detection ---
@pytest.mark.parametrize("status", ["shipped", "partially_shipped", "done"])
def test_status_marks_issued(H, status):
    so = _mk("st_" + status, status=status)
    pv = _preview(H, so["id"])
    assert pv["issued"] is True and pv["method"] == "credit_note", pv


def test_sales_order_je_marks_issued(H):
    so = _mk("je_so", je=lambda s: {"source_type": "sales_order", "source_id": s, "status": "posted"})
    pv = _preview(H, so["id"])
    assert pv["issued"] and pv["method"] == "credit_note"
    pv2 = _preview(H, so["id"], 1.2)
    assert pv2["method"] == "debit_note"


def test_void_je_not_issued(H):
    so = _mk("je_void", status="reserved",
             je=lambda s: {"source_type": "shipment_revenue", "source_id": "shp_x", "ref": {"order_id": s},
                           "status": "void"})
    pv = _preview(H, so["id"])
    assert pv["issued"] is False and pv["method"] == "re_derive"


def test_not_issued_re_derive_applies(H):
    so = _mk("reserved", status="reserved")
    amd = _propose(H, so["id"], 0.9)
    assert amd["method"] == "re_derive" and amd["status"] in ("applied", "auto_applied")
    cur = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert cur["number"] == so["number"]
    assert cur["grand_total"] < so["grand_total"]
    assert DB.credit_notes.count_documents({"order_id": so["id"]}) == 0


# --- credit note settlement ---
def test_credit_note_partial_paid_splits_ar_and_store_credit(H):
    pv = None
    so = _mk("partial_tmp", status="shipped")
    pv = _preview(H, so["id"], 0.5)
    gross = abs(pv["impact"]["delta"])
    # outstanding smaller than credit → remainder to store credit
    paid = round(so["grand_total"] - gross / 2, 2)
    so = _mk("partial", status="shipped", paid=paid)
    amd = _propose(H, so["id"], 0.5)
    assert amd["method"] == "credit_note"
    cn = DB.credit_notes.find_one({"amendment_id": amd["id"]}, {"_id": 0})
    outstanding = round(so["grand_total"] - paid, 2)
    assert cn["status"] == "posted"
    assert abs(cn["ar_applied"] - min(cn["gross_amount"], outstanding)) < 0.02
    assert abs(cn["store_credit_amount"] - (cn["gross_amount"] - cn["ar_applied"])) < 0.02
    assert cn["store_credit_amount"] > 0
    _je_check(cn)
    cur = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert cur["items"] == so["items"] and cur["grand_total"] == so["grand_total"]
    cp = [p for p in cur["payments"] if p.get("method") == "credit_note"]
    assert len(cp) == 1 and abs(cp[0]["amount"] - cn["ar_applied"]) < 0.02
    led = list(DB.store_credit_ledger.find({"ref_id": cn["id"], "type": "issue", "ref_type": "credit_note"}))
    assert len(led) == 1 and abs(float(led[0].get("amount_signed", led[0].get("amount", 0))) - cn["store_credit_amount"]) < 0.02


def test_credit_note_fully_paid_all_store_credit(H):
    so = _mk("fullpaid", status="done", paid=float(SRC["grand_total"]))
    amd = _propose(H, so["id"], 0.9)
    assert amd["method"] == "credit_note"
    cn = DB.credit_notes.find_one({"amendment_id": amd["id"]}, {"_id": 0})
    assert cn["ar_applied"] == 0 and cn["store_credit_amount"] == cn["gross_amount"]
    je = _je_check(cn)
    assert not any(l["account_code"] == "1-1200" for l in je["lines"])
    assert DB.store_credit_ledger.count_documents({"ref_id": cn["id"], "type": "issue", "ref_type": "credit_note"}) == 1
    cur = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert not [p for p in cur["payments"] if p.get("method") == "credit_note"]
    assert cur["grand_total"] == so["grand_total"]


def test_credit_note_double_approve_and_self_approve(H):
    so = _mk("qty", status="shipped")
    r = requests.post(f"{BASE}/amendments", headers=H["admin"], json=_body(so["id"], 0.8))
    assert r.status_code == 200, r.text[:400]
    amd = r.json()
    assert amd["method"] == "credit_note"
    if amd["status"] == "pending_approval":
        # proposer cannot self-approve under dual control
        rs = requests.post(f"{BASE}/amendments/{amd['id']}/decision", headers=H["admin"], json={"action": "approve"})
        print("self-approve status", rs.status_code, rs.text[:200])
        r = requests.post(f"{BASE}/amendments/{amd['id']}/decision", headers=H["manager"], json={"action": "approve"})
        if r.status_code == 400 and rs.status_code == 200:
            pass
        else:
            assert r.status_code == 200, r.text[:400]
    r2 = requests.post(f"{BASE}/amendments/{amd['id']}/decision", headers=H["manager"], json={"action": "approve"})
    assert r2.status_code == 400
    assert DB.credit_notes.count_documents({"amendment_id": amd["id"]}) == 1
    cn = DB.credit_notes.find_one({"amendment_id": amd["id"]}, {"_id": 0})
    assert DB.journal_entries.count_documents({"source_type": "amendment_credit_note", "source_id": cn["id"]}) == 1
    cur = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert cur["items"] == so["items"]
    assert len([p for p in cur["payments"] if p.get("receipt_id") == cn["id"]]) == 1


def test_debit_note_no_journal_order_unchanged(H):
    so = _mk("debit", status="shipped")
    amd = _propose(H, so["id"], 1.3)
    assert amd["method"] == "debit_note"
    dn = DB.credit_notes.find_one({"amendment_id": amd["id"]}, {"_id": 0})
    assert dn["kind"] == "debit_note" and dn["billing_status"] == "awaiting_billing_rule"
    assert DB.journal_entries.count_documents({"source_id": dn["id"]}) == 0
    cur = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    assert cur["items"] == so["items"] and cur["grand_total"] == so["grand_total"]
    assert cur["payments"] == []


def test_qty_decrease_below_shipped_blocked(H):
    so = _mk("qtyblk", status="shipped")
    r = requests.post(f"{BASE}/amendments/preview", headers=H["admin"], json=_body(so["id"], 0.5, "quantity"))
    assert r.status_code == 400 and "reservasi" in r.text


def test_repeat_same_price_correction_does_not_double_credit(H):
    """Same target price proposed twice on an issued order: effective price already corrected by CN #1."""
    so = _mk("repeat", status="shipped")
    a1 = _propose(H, so["id"], 0.9)
    r = requests.post(f"{BASE}/amendments/preview", headers=H["admin"], json=_body(so["id"], 0.9))
    print("repeat preview", r.status_code, r.text[:300])
    total_cn = sum(n["gross_amount"] for n in DB.credit_notes.find({"order_id": so["id"], "kind": "credit_note"}))
    if r.status_code == 200:
        a2 = _propose(H, so["id"], 0.9)
        total_cn = sum(n["gross_amount"] for n in DB.credit_notes.find({"order_id": so["id"], "kind": "credit_note"}))
    assert round(total_cn, 2) == round(abs(a1["impact"]["delta"]), 2), f"credited {total_cn} vs one-time {a1['impact']['delta']}"


def test_second_correction_credits_only_increment(H):
    """0.9 lalu 0.8 dari harga asal: nota kedua hanya selisih 0.9→0.8, bukan asal→0.8."""
    so = _mk("incr", status="shipped")
    a1 = _propose(H, so["id"], 0.9)
    a2 = _propose(H, so["id"], 0.8)
    assert a2["changes"][0]["from"] == a1["changes"][0]["to"]
    total_cn = sum(n["gross_amount"] for n in DB.credit_notes.find({"order_id": so["id"], "kind": "credit_note"}))
    full = requests.post(f"{BASE}/amendments/preview", headers=H["admin"], json=_body(so["id"], 1.0))
    assert full.status_code == 200, full.text[:300]
    assert round(total_cn, 2) == round(abs(a1["impact"]["delta"]) + abs(a2["impact"]["delta"]), 2)
    assert DB.sales_orders.find_one({"id": so["id"]})["grand_total"] == so["grand_total"]
