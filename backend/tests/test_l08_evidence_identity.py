"""L08 LN-080 T03/T04 + LN-082 T01–T03 — bukti per tahap, hitungan sesuai saringan,
identitas roll retur, nomor potongan atomik, larangan kirim ulang ke pelanggan asal."""
import asyncio
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = "TEST_L08B"
SO = DB.sales_orders.find_one({"number": "KSC/SO-00001"})
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
LOOP = asyncio.new_event_loop()


def run(coro):
    return LOOP.run_until_complete(coro)


def login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def h():
    rolls_before = {r["id"]: r for r in DB.inventory_rolls.find({"status": "delivered"})}
    hh = login("admin@kainnusantara.id", "demo12345")
    yield hh
    ids = [d["id"] for d in DB.sales_returns.find({"notes": TAG}, {"id": 1})]
    DB.inventory_rolls.delete_many({"return_id": {"$in": ids}, "returned_identity": {"$ne": True}})
    DB.inventory_rolls.delete_many({"roll_no": {"$regex": "^TEST_L08B"}})
    for r in DB.inventory_rolls.find({"return_id": {"$in": ids}, "returned_identity": True}):
        DB.inventory_rolls.replace_one({"_id": r["_id"]}, rolls_before[r["id"]])
    for coll in ("credit_notes", "journal_entries", "cash_transactions", "inventory_movements"):
        DB[coll].delete_many({"$or": [{"return_id": {"$in": ids}}, {"ref_id": {"$in": ids}}, {"source_id": {"$in": ids}}]})
    DB.sales_returns.delete_many({"notes": TAG})
    DB.number_sequences.delete_many({"doc_type": {"$regex": "^ROLL_CHILD:TEST_L08B"}})
    for k in ("returns.evidence_required_submit", "returns.block_resend_to_origin_customer"):
        requests.post(f"{BASE}/config/values/clear", headers=hh, json={"key": k, "scope_type": "global", "reason": TAG})
    from services import roll_service
    for pid, wid, eid in {(r["product_id"], r["warehouse_id"], r["owner_entity_id"]) for r in rolls_before.values()}:
        run(roll_service.rebuild_balance(pid, wid, eid))


def set_cfg(h, key, value):
    r = requests.put(f"{BASE}/config/values", headers=h, json={"items": [
        {"key": key, "value": value, "scope_type": "global", "reason": f"{TAG} uji kebijakan retur"}]})
    return r


def shipped_roll(h, idx=0):
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": SO["id"]}).json()
    rolls = [r for r in data["rolls"] if r["remaining"] >= r["shipped_qty"] - 0.01]
    return rolls[idx]


def create(h, roll, qty=None, submit_now=False):
    q = qty if qty is not None else roll["remaining"]
    return requests.post(f"{BASE}/sales-returns", headers=h, json={
        "order_id": SO["id"], "return_type": "retur", "notes": TAG, "submit_now": submit_now,
        "items": [{"product_id": roll["product_id"], "quantity_returned": q, "unit": roll["unit"],
                   "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: q}, "reason": "cacat"}]})


# ── LN-080-T03 ────────────────────────────────────────────────────────────────
def test_t03_evidence_optional_by_default(h):
    r = create(h, shipped_roll(h), qty=1, submit_now=True)
    assert r.status_code == 200, r.text
    d = requests.get(f"{BASE}/sales-returns/{r.json()['id']}", headers=h).json()
    assert d["evidence"]["count"] == 0 and d["evidence"]["missing_for"] == []
    requests.post(f"{BASE}/sales-returns/{d['id']}/reject", headers=h, json={"notes": "uji T03 selesai"})


def test_t03_evidence_required_at_submit(h):
    assert set_cfg(h, "returns.evidence_required_submit", True).status_code == 200
    roll = shipped_roll(h)
    r = create(h, roll, qty=1, submit_now=True)
    assert r.status_code == 400 and "Bukti foto wajib" in r.json()["detail"]
    r = create(h, roll, qty=1)
    assert r.status_code == 200, r.text   # draf tetap boleh tanpa bukti
    rid = r.json()["id"]
    pol = requests.get(f"{BASE}/sales-returns/meta/evidence-policy", headers=h).json()
    assert pol["required"]["submit"] is True and pol["required"]["approve"] is False
    d = requests.get(f"{BASE}/sales-returns/{rid}", headers=h).json()
    assert d["evidence"]["missing_for"] == ["submit"]
    r = requests.post(f"{BASE}/sales-returns/{rid}/submit", headers=h)
    assert r.status_code == 400 and "Bukti foto wajib" in r.json()["detail"]
    up = requests.post(f"{BASE}/sales-returns/{rid}/attachments", headers={"Authorization": h["Authorization"]},
                       files={"file": ("bukti.png", PNG, "image/png")})
    assert up.status_code == 200, up.text
    r = requests.post(f"{BASE}/sales-returns/{rid}/submit", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "pending_approval"
    requests.post(f"{BASE}/sales-returns/{rid}/reject", headers=h, json={"notes": "uji T03 selesai"})
    set_cfg(h, "returns.evidence_required_submit", False)


# ── LN-080-T04 ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("rtype", ["", "retur", "bs", "garansi"])
def test_t04_counts_follow_list_filters(h, rtype):
    params = {"return_type": rtype} if rtype else {}
    counts = requests.get(f"{BASE}/sales-returns/status-counts", headers=h, params=params).json()
    lst = requests.get(f"{BASE}/sales-returns", headers=h, params={**params, "page": 1, "page_size": 5}).json()
    assert counts["all"] == lst["total"]
    for status in ("draft", "pending_approval", "rejected"):
        sub = requests.get(f"{BASE}/sales-returns", headers=h,
                           params={**params, "status": status, "page": 1, "page_size": 5}).json()
        assert counts.get(status, 0) == sub["total"]


# ── LN-082 ────────────────────────────────────────────────────────────────────
def _drive_to_settled(h, rid, roll_id, grade, actual):
    # F-12 — QC hanya sesudah barang diterima: scan terima di gudang asal SJ (wh_jakarta) dulu.
    scan = {"stage": "received", "codes": [roll_id], "warehouse_id": "wh_jakarta"}
    for path, body in (("approve", {"notes": ""}), ("journey/scan", scan), ("inspect/start", {}),
                       ("inspect/complete", {"inspections": [{"index": 0, "grade": grade, "condition": "ok",
                                                              "roll_actuals": {roll_id: actual}}]}),
                       ("settle", {"outcome": "refund"})):
        r = requests.post(f"{BASE}/sales-returns/{rid}/{path}", headers=h, json=body)
        assert r.status_code == 200, (path, r.text)
    return r.json()


def test_t01_whole_roll_keeps_identity_and_reverse_restores(h):
    roll = shipped_roll(h)
    orig = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    r = create(h, roll, submit_now=True)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    actual = round(roll["remaining"] - 0.5, 2)
    _drive_to_settled(h, rid, roll["roll_id"], "B", actual)
    back = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    assert back["roll_no"] == orig["roll_no"] and back.get("rfid_tag_id") == orig.get("rfid_tag_id")
    assert back["status"] == "quarantine" and back["return_id"] == rid
    assert back["length_remaining"] == actual and back["length_initial"] == orig["length_initial"]
    h0 = back["return_history"][-1]
    assert h0["qty_claimed"] == roll["remaining"] and h0["qty_actual"] == actual
    assert h0["qty_shipped_bruto"] == round(orig["length_initial"], 2)
    assert h0["grade_before"] == (orig.get("grade") or "") and h0["grade_after"] == "B"
    assert h0["order_number"] == SO["number"] and h0["shipment_no"]
    assert SO["customer_id"] in back["returned_from_customer_ids"]
    assert DB.inventory_rolls.count_documents({"return_id": rid}) == 1   # tidak ada roll RTN baru
    rev = requests.post(f"{BASE}/sales-returns/{rid}/reverse", headers=h, json={"notes": "uji identitas"})
    assert rev.status_code == 200, rev.text
    again = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    assert again["status"] == "delivered" and again["length_remaining"] == orig["length_remaining"]
    assert not again.get("returned_identity") and not again.get("return_id")


def test_t01_partial_claim_becomes_numbered_child(h):
    roll = shipped_roll(h, 1)
    orig = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    r = create(h, roll, qty=2, submit_now=True)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    _drive_to_settled(h, rid, roll["roll_id"], "A", 2)
    child = DB.inventory_rolls.find_one({"return_id": rid})
    assert child["roll_no"].startswith(orig["roll_no"] + "-") and child["parent_roll_id"] == orig["id"]
    assert child["length_remaining"] == 2 and child.get("rfid_tag_id") is None
    assert DB.inventory_rolls.find_one({"id": orig["id"]})["status"] == "delivered"
    assert SO["customer_id"] in child["returned_from_customer_ids"]


def test_t02_parallel_cuts_unique_sequential_and_conserved():
    from services import roll_service
    tmpl = DB.inventory_rolls.find_one({"status": "available"}, {"_id": 0})
    parent = {**tmpl, "id": "roll_TEST_L08B_parent", "roll_no": "TEST_L08B-P1", "length_initial": 20.0,
              "length_remaining": 20.0, "length_reserved": 0, "length_reservations": [], "active_movement": None,
              "weight_kg": None, "reserved_ref": None, "rfid_tag_id": None}
    DB.inventory_rolls.insert_one(dict(parent))

    async def go():
        return await asyncio.gather(*[roll_service._split_roll(parent, 3, "so_TEST_L08B") for _ in range(4)])
    kids = run(go())
    nos = sorted(k["roll_no"] for k in kids if k)
    assert nos == [f"TEST_L08B-P1-{i}" for i in range(1, 5)]
    left = DB.inventory_rolls.find_one({"id": parent["id"]})["length_remaining"]
    assert round(left + sum(k["length_remaining"] for k in kids), 2) == 20.0


def test_t03_block_resend_to_origin_customer(h):
    from services import roll_service
    returned = DB.inventory_rolls.find_one({"return_id": {"$exists": True}, "returned_from_customer_ids": SO["customer_id"]})
    assert returned, "butuh roll retur dari uji T01"
    DB.inventory_rolls.update_one({"id": returned["id"]}, {"$set": {"status": "available"}})
    pid, owner = returned["product_id"], returned["owner_entity_id"]

    def ids(cust):
        return {r["id"] for r in run(roll_service._available_rolls_for_order(pid, owner, "so_TEST_L08B", cust))}
    assert returned["id"] not in ids(SO["customer_id"])
    assert returned["id"] in ids("cust_TEST_L08B_other")
    # pengguna tanpa hak sales_return.policy tidak bisa mematikan toggle
    sales = login("sales@kainnusantara.id", "demo1234")
    assert set_cfg(sales, "returns.block_resend_to_origin_customer", False).status_code == 403
    assert set_cfg(h, "returns.block_resend_to_origin_customer", False).status_code == 200
    assert returned["id"] in ids(SO["customer_id"])
    assert set_cfg(h, "returns.block_resend_to_origin_customer", True).status_code == 200
    DB.inventory_rolls.update_one({"id": returned["id"]}, {"$set": {"status": "quarantine"}})
