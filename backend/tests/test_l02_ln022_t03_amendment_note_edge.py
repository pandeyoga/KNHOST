"""L02 LN-022-T03 (edge) — pending clash, stale approve, race, discount-level notes, cross-field double credit."""
import os
import threading
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
PFX = "so_TEST_l022t03e_"

SRC = DB.sales_orders.find_one({"status": "done", "items.0": {"$exists": True}, "customer_id": {"$nin": [None, ""]},
                                "id": {"$not": {"$regex": "TEST"}}}, {"_id": 0})
IT = SRC["items"][0]
PID = IT["product_id"]


def _h(email, pwd, ent):
    t = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": ent}


def _cleanup():
    sids = [s["id"] for s in DB.sales_orders.find({"id": {"$regex": "^" + PFX}}, {"id": 1})]
    notes = [n["id"] for n in DB.credit_notes.find({"order_id": {"$in": sids}}, {"id": 1})]
    amds = [a["id"] for a in DB.doc_amendments.find({"doc_id": {"$in": sids}}, {"id": 1})]
    DB.journal_entries.delete_many({"$or": [{"source_id": {"$in": notes}}, {"ref.order_id": {"$in": sids}}]})
    DB.store_credit_ledger.delete_many({"ref_id": {"$in": notes}})
    DB.credit_notes.delete_many({"order_id": {"$in": sids}})
    DB.doc_amendments.delete_many({"doc_id": {"$in": sids}})
    ids = sids + notes + amds
    DB.doc_refs.delete_many({"$or": [{"from_id": {"$in": ids}}, {"to_id": {"$in": ids}}]})
    DB.notifications.delete_many({"$or": [{"ref": {"$in": amds}}, {"action_id": {"$in": amds}}]})
    DB.sales_orders.delete_many({"id": {"$in": sids}})


@pytest.fixture(scope="module")
def H():
    _cleanup()  # sisa run yang crash
    yield {"admin": _h("admin@kainnusantara.id", "demo12345", SRC["entity_id"]),
           "manager": _h("manager@kainnusantara.id", "demo1234", SRC["entity_id"])}
    _cleanup()


def _mk(suffix, status="shipped"):
    sid = PFX + suffix
    so = {**SRC, "id": sid, "number": f"TEST/SO-E{suffix}-{uuid.uuid4().hex[:4]}", "status": status,
          "payments": [], "paid_total": 0, "payment_status": "pending", "amendment_count": 0, "timeline": [],
          "notes": "TEST_L022T03E", "backorders": [], "has_backorder": False}
    DB.sales_orders.insert_one(dict(so))
    return so


def _body(sid, changes=None, odp=None):
    b = {"doc_type": "sales_order", "doc_id": sid, "reason_code": "price_correction", "note": "TEST_L022T03E",
         "changes": changes or []}
    if odp is not None:
        b["order_discount_percent"] = odp
    return b


def _ch(field, to):
    return [{"product_id": PID, "field": field, "to": to}]


def _post(H, path, body, who="admin"):
    return requests.post(f"{BASE}{path}", headers=H[who], json=body)


def _approve(H, amd_id):
    return _post(H, f"/amendments/{amd_id}/decision", {"action": "approve"}, "manager")


def _cn_total(sid):
    return round(sum(n["gross_amount"] for n in DB.credit_notes.find({"order_id": sid, "kind": "credit_note"})), 2)


def _cfg(H, value):
    items = [{"key": k, "value": value, "scope_type": "entity", "scope_id": SRC["entity_id"],
              "reason": "TEST_L022T03E diskon untuk uji nota"} for k in
             ("sales.allow_item_discount", "sales.allow_order_discount")]
    return requests.put(f"{BASE}/config/values", headers=H["admin"], json={"items": items})


@pytest.fixture
def disc_on(H):
    r = _cfg(H, True)
    assert r.status_code == 200, r.text[:300]
    yield
    _cfg(H, False)
    DB.config_values.delete_many({"reason": {"$regex": "^TEST_L022T03E"}})


# --- pending clash ---
def test_pending_note_blocks_same_key_but_not_other_field(H, disc_on):
    so = _mk("clash")
    r = _post(H, "/amendments", _body(so["id"], _ch("price", round(IT["price"] * 0.9, 2))))
    assert r.status_code == 200, r.text[:300]
    a1 = r.json()
    assert a1["status"] == "pending_approval" and a1["method"] == "credit_note"
    for path in ("/amendments/preview", "/amendments"):
        r2 = _post(H, path, _body(so["id"], _ch("price", round(IT["price"] * 0.8, 2))))
        assert r2.status_code == 400 and "menunggu persetujuan" in r2.text, r2.text[:300]
    assert DB.doc_amendments.count_documents({"doc_id": so["id"]}) == 1
    # field lain (diskon baris) juga diblokir: satu nota pending per pesanan
    r3 = _post(H, "/amendments/preview", _body(so["id"], _ch("discount_percent", 5)))
    assert r3.status_code == 400 and "menunggu persetujuan" in r3.text, r3.text[:300]


def test_reject_frees_key(H):
    so = _mk("reject")
    a1 = _post(H, "/amendments", _body(so["id"], _ch("price", round(IT["price"] * 0.9, 2)))).json()
    assert a1["status"] == "pending_approval"
    r = _post(H, f"/amendments/{a1['id']}/decision", {"action": "reject", "note": "TEST"}, "manager")
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    r2 = _post(H, "/amendments/preview", _body(so["id"], _ch("price", round(IT["price"] * 0.9, 2))))
    assert r2.status_code == 200, r2.text[:300]
    assert r2.json()["changes"][0]["from"] == IT["price"]
    assert DB.credit_notes.count_documents({"order_id": so["id"]}) == 0


# --- stale approve ---
def test_stale_pending_note_cannot_be_approved(H):
    so = _mk("stale")
    a1 = _post(H, "/amendments", _body(so["id"], _ch("price", round(IT["price"] * 0.9, 2)))).json()
    assert a1["status"] == "pending_approval"
    # simulasikan nota lain (race) yang sudah diterapkan pada kunci yang sama
    DB.doc_amendments.insert_one({"id": "amd_TEST_stale", "doc_id": so["id"], "method": "credit_note",
                                  "status": "applied", "created_at": "2000-01-01T00:00:00+00:00",
                                  "changes": [{"product_id": PID, "field": "price", "from": IT["price"],
                                               "to": round(IT["price"] * 0.95, 2)}]})
    r = _approve(H, a1["id"])
    assert r.status_code == 400 and "sudah berubah" in r.text, r.text[:300]
    cur = DB.doc_amendments.find_one({"id": a1["id"]})
    assert cur["status"] == "pending_approval"
    assert DB.credit_notes.count_documents({"amendment_id": a1["id"]}) == 0


def test_concurrent_proposals_same_key_single_pending(H):
    """TOCTOU: dua usulan identik dikirim bersamaan → idealnya hanya satu yang tercatat."""
    so = _mk("race")
    body = _body(so["id"], _ch("price", round(IT["price"] * 0.9, 2)))
    res = []
    ts = [threading.Thread(target=lambda: res.append(_post(H, "/amendments", body))) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    codes = sorted(r.status_code for r in res)
    pend = list(DB.doc_amendments.find({"doc_id": so["id"], "status": "pending_approval"}, {"_id": 0, "id": 1}))
    print("race codes", codes, "pending", len(pend))
    # walau race lolos, approve kedua harus ditolak (stale guard) → total kredit = sekali
    for p in pend:
        _approve(H, p["id"])
    one_time = round(abs(next(r.json() for r in res if r.status_code == 200)["impact"]["delta"]), 2)
    assert _cn_total(so["id"]) == one_time
    assert len(pend) == 1, f"{len(pend)} pending amendments for the same key created concurrently"


# --- discount-level notes ---
def test_line_discount_credit_note_and_repeat_blocked(H, disc_on):
    so = _mk("disc")
    r = _post(H, "/amendments", _body(so["id"], _ch("discount_percent", 10)))
    assert r.status_code == 200, r.text[:300]
    a = r.json()
    if a["status"] == "pending_approval":
        a = _approve(H, a["id"]).json()
    assert a["method"] == "credit_note" and a["status"] in ("applied", "auto_applied")
    cn = DB.credit_notes.find_one({"amendment_id": a["id"]}, {"_id": 0})
    assert cn["gross_amount"] == round(abs(a["impact"]["delta"]), 2) > 0
    je = DB.journal_entries.find_one({"id": cn["journal_entry_id"]}, {"_id": 0})
    assert round(sum(l["debit"] for l in je["lines"]), 2) == round(sum(l["credit"] for l in je["lines"]), 2) == cn["gross_amount"]
    r2 = _post(H, "/amendments/preview", _body(so["id"], _ch("discount_percent", 10)))
    assert r2.status_code == 400 and "sudah dikoreksi oleh nota sebelumnya" in r2.text, r2.text[:300]
    assert DB.sales_orders.find_one({"id": so["id"]})["grand_total"] == so["grand_total"]


def test_order_discount_credit_note_and_repeat_blocked(H, disc_on):
    so = _mk("odisc")
    r = _post(H, "/amendments", _body(so["id"], odp=10))
    assert r.status_code == 200, r.text[:300]
    a = r.json()
    if a["status"] == "pending_approval":
        a = _approve(H, a["id"]).json()
    assert a["method"] == "credit_note" and a["changes"][0]["field"] == "order_discount_percent"
    assert DB.credit_notes.count_documents({"amendment_id": a["id"]}) == 1
    r2 = _post(H, "/amendments/preview", _body(so["id"], odp=10))
    assert r2.status_code == 400 and "sudah dikoreksi" in r2.text, r2.text[:300]
    # pending clash on order-level discount
    r3 = _post(H, "/amendments", _body(so["id"], odp=20)).json()
    assert r3["status"] == "pending_approval" and r3["changes"][0]["from"] == 10
    r4 = _post(H, "/amendments/preview", _body(so["id"], odp=25))
    assert r4.status_code == 400 and "menunggu persetujuan" in r4.text, r4.text[:300]


# --- cross-field: price & discount on same line, both pending, approved sequentially ---
def test_cross_field_pending_notes_do_not_over_credit(H, disc_on):
    so = _mk("xfield")
    a_price = _post(H, "/amendments", _body(so["id"], _ch("price", round(IT["price"] * 0.9, 2)))).json()
    rd = _post(H, "/amendments", _body(so["id"], _ch("discount_percent", 10)))
    assert rd.status_code == 400, rd.text[:300]
    assert _approve(H, a_price["id"]).status_code == 200
    a_disc = _post(H, "/amendments", _body(so["id"], _ch("discount_percent", 10))).json()
    if a_disc.get("status") == "pending_approval":
        assert _approve(H, a_disc["id"]).status_code == 200
    credited = _cn_total(so["id"])
    # nilai efektif akhir (harga 0.9, diskon 10%) dihitung lewat SO tak-terbit (re_derive preview)
    ref = _mk("xfield_ref", status="reserved")
    pv = _post(H, "/amendments/preview", _body(ref["id"], [{"product_id": PID, "field": "price",
                                                           "to": round(IT["price"] * 0.9, 2)},
                                                          {"product_id": PID, "field": "discount_percent", "to": 10}]))
    assert pv.status_code == 200, pv.text[:300]
    true_reduction = round(abs(pv.json()["impact"]["delta"]), 2)
    assert credited <= true_reduction + 0.02, f"over-credit: credited {credited} vs true reduction {true_reduction}"


# --- debit note (unbilled) followed by credit note ---
def test_unbilled_debit_note_then_credit_note_ar(H):
    so = _mk("dn_cn")
    a1 = _post(H, "/amendments", _body(so["id"], _ch("price", round(IT["price"] * 1.2, 2)))).json()
    if a1["status"] == "pending_approval":
        a1 = _approve(H, a1["id"]).json()
    assert a1["method"] == "debit_note"
    a2 = _post(H, "/amendments", _body(so["id"], _ch("price", IT["price"]))).json()
    if a2["status"] == "pending_approval":
        a2 = _approve(H, a2["id"]).json()
    assert a2["method"] == "credit_note"
    cn = DB.credit_notes.find_one({"amendment_id": a2["id"]}, {"_id": 0})
    print("CN after unbilled DN", cn["gross_amount"], "ar_applied", cn["ar_applied"], "sc", cn["store_credit_amount"])
    # harga kembali ke asal: tagihan riil (AR) tidak pernah naik, jadi AR tidak boleh berkurang
    assert cn["ar_applied"] == 0, f"AR reduced by {cn['ar_applied']} for a debit note that was never billed"


# --- regression ---
def test_unissued_re_derive_still_recalculates(H):
    so = _mk("rederive", status="reserved")
    a = _post(H, "/amendments", _body(so["id"], _ch("price", round(IT["price"] * 0.99, 2)))).json()
    if a["status"] == "pending_approval":
        a = _approve(H, a["id"]).json()
    assert a["method"] == "re_derive" and a["status"] in ("applied", "auto_applied")
    cur = DB.sales_orders.find_one({"id": so["id"]})
    assert cur["items"][0]["price"] == round(IT["price"] * 0.99, 2) and cur["grand_total"] < so["grand_total"]
    assert DB.credit_notes.count_documents({"order_id": so["id"]}) == 0
