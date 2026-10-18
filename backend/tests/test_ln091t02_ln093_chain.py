"""LN-091-T02 kerugian turun grade + LN-093 retur berantai Sukacita → CST → supplier."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = f"TEST_LN093_{uuid.uuid4().hex[:5]}"
KSC, CST = "ent_ksc", "ent_89cbf7444def"
PO = DB.purchase_orders.find_one({"po_number": "CST/PO-00001"})
TPL = DB.inventory_rolls.find_one({"owner_entity_id": CST, "status": "available"})
PRICE = float(DB.products.find_one({"id": TPL["product_id"]})["price"])
NOW = datetime.now(timezone.utc)


def _h(ent):
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


H_KSC, H_CST = _h(KSC), _h(CST)


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    srs = [d["id"] for d in DB.sales_returns.find({"notes": TAG}, {"id": 1})]
    pairs = [d["pair_id"] for d in DB.interco_transactions.find({"notes": TAG}, {"pair_id": 1})]
    rps = [d["return_pair_id"] for d in DB.interco_returns.find({"source_sales_return_id": {"$in": srs}}, {"return_pair_id": 1})]
    prs = [p["id"] for p in DB.purchase_returns.find({"origin_sales_return_id": {"$in": srs}}, {"id": 1})]
    rolls = [r["id"] for r in DB.inventory_rolls.find({"notes": TAG}, {"id": 1})]
    DB.journal_entries.delete_many({"$or": [{"source_id": {"$in": rolls + prs}},
                                            {"source_id": {"$regex": f"^sret_{TAG}"}}]})
    DB.interco_returns.delete_many({"return_pair_id": {"$in": rps}})
    DB.interco_transactions.delete_many({"pair_id": {"$in": pairs}})
    DB.warehouse_transfers.delete_many({"notes": TAG})
    DB.purchase_returns.delete_many({"id": {"$in": prs}})
    DB.inventory_movements.delete_many({"$or": [{"ref_id": {"$in": srs + prs}}, {"roll_id": {"$in": rolls}}]})
    DB.return_grade_impairments.delete_many({"return_id": {"$in": srs}})
    DB.roll_cost_history.delete_many({"roll_id": {"$in": rolls}})
    for coll in ("doc_refs", "document_refs"):
        DB[coll].delete_many({"$or": [{"from_id": {"$in": srs + prs}}, {"to_id": {"$in": srs + prs}}]})
    DB.inventory_rolls.delete_many({"notes": TAG})
    DB.sales_returns.delete_many({"notes": TAG})
    DB.atomic_claims.delete_many({"doc_id": {"$in": srs}})


def make_return(status="inspected"):
    rid = f"sret_{TAG}_{uuid.uuid4().hex[:6]}"
    DB.sales_returns.insert_one({"id": rid, "number": f"{TAG}-{rid[-6:]}", "notes": TAG, "entity_id": KSC,
                                 "status": status, "items": [], "created_at": NOW.isoformat(),
                                 "attachments": [{"id": "att_img", "filename": "bs.jpg", "content_type": "image/jpeg"}]})
    return rid


def make_roll(rid, owner, status="available", grade="A", unit_cost=None, pair="", receipt_days=1, **extra):
    doc = {k: v for k, v in TPL.items() if k not in ("_id", "acquired_history", "disposition", "reserved_ref")}
    doc.update({"id": f"roll_{TAG}_{uuid.uuid4().hex[:8]}", "roll_no": f"{TAG}-{uuid.uuid4().hex[:4]}",
                "owner_entity_id": owner, "status": status, "grade": grade, "origin_type": "return",
                "return_id": rid, "notes": TAG, "length_remaining": 10.0, "length": 10.0, "length_initial": 10.0,
                "length_reserved": 0, "unit_cost": unit_cost if unit_cost is not None else TPL.get("unit_cost") or 30000,
                "base_unit_cost": unit_cost if unit_cost is not None else TPL.get("unit_cost") or 30000,
                "origin_interco_pair_id": pair, "supplier_id": PO["supplier_id"], "po_id": PO["id"],
                "acquired": {"via": "inbound", "ref_id": PO["id"], "date": (NOW - timedelta(days=receipt_days)).isoformat()},
                "rfid_tag": "", "tag_id": ""}, **extra)
    DB.inventory_rolls.insert_one(doc)
    return doc["id"]


def make_interco(qty=100.0):
    pair = f"icp_{TAG}_{uuid.uuid4().hex[:6]}"
    base = {"pair_id": pair, "notes": TAG, "seller_entity_id": CST, "seller_entity_name": "Cipta Sandang",
            "buyer_entity_id": KSC, "buyer_entity_name": "Sukacita", "status": "received", "tax_apply": False,
            "tax_rate": 0, "items": [{"product_id": TPL["product_id"], "sku": "X", "product_name": "X",
                                      "unit": TPL.get("unit", "meter"), "quantity": qty, "unit_price": 30000}],
            "created_at": NOW.isoformat()}
    DB.interco_transactions.insert_many([{**base, "id": f"ict_{uuid.uuid4().hex[:8]}", "role": "seller", "number": f"{TAG}-S"},
                                         {**base, "id": f"ict_{uuid.uuid4().hex[:8]}", "role": "buyer", "number": f"{TAG}-B"}])
    DB.warehouse_transfers.insert_one({"id": f"trn_{uuid.uuid4().hex[:8]}", "interco_pair_id": pair, "status": "completed",
                                       "notes": TAG, "code": f"{TAG}-T"})
    return pair


def rows(rid, h=H_KSC):
    r = requests.get(f"{BASE}/sales-returns/{rid}/disposition", headers=h)
    assert r.status_code == 200, r.text
    return {x["roll_id"]: x for x in r.json()["rows"]}


# ── LN-091-T02 ───────────────────────────────────────────────────────────────
def test_grade_down_impairment_separate_from_customer_credit():
    rid = make_return()
    DB.sales_returns.update_one({"id": rid}, {"$set": {"credit_note_amount": 777.0}})
    roll = make_roll(rid, KSC, status="quarantine", grade="A", unit_cost=PRICE)
    je_before = DB.journal_entries.count_documents({"source_type": "sales_invoice"})
    r = requests.post(f"{BASE}/sales-returns/{rid}/quarantine/release", headers=H_KSC,
                      json={"decisions": [{"roll_id": roll, "action": "release", "grade": "B"}], "notes": TAG})
    assert r.status_code == 200, r.text
    f = requests.get(f"{BASE}/sales-returns/{rid}/grade-impairments", headers=H_KSC).json()["factors"]
    drop = (f["A"] - f["B"]) / 100
    expected = round(PRICE * drop, 2) * 10
    assert abs(r.json()["_release_summary"]["grade_impairment_total"] - expected) < 0.05
    je = DB.journal_entries.find_one({"source_type": "return_grade_impairment", "source_id": f"{rid}:{roll}"})
    assert je and abs(sum(l["debit"] for l in je["lines"]) - sum(l["credit"] for l in je["lines"])) < 0.01
    assert {l["account_code"] for l in je["lines"]} == {"5-9500", "1-1300"}
    rr = DB.inventory_rolls.find_one({"id": roll})
    assert abs(rr["unit_cost"] - (PRICE - round(PRICE * drop, 2))) < 0.02 and rr["grade"] == "B"
    sr = DB.sales_returns.find_one({"id": rid})
    assert sr["credit_note_amount"] == 777.0
    assert DB.journal_entries.count_documents({"source_type": "sales_invoice"}) == je_before
    g = requests.get(f"{BASE}/sales-returns/{rid}/grade-impairments", headers=H_KSC).json()
    assert len(g["items"]) == 1 and abs(g["total"] - expected) < 0.05 and g["factors"]["B"] == f["B"]
    again = requests.post(f"{BASE}/sales-returns/{rid}/quarantine/release", headers=H_KSC,
                          json={"decisions": [{"roll_id": roll, "action": "release", "grade": "C"}]})
    assert again.status_code in (400, 409)
    assert DB.journal_entries.count_documents({"source_type": "return_grade_impairment", "source_id": f"{rid}:{roll}"}) == 1


def test_impairment_capped_to_book_value_and_no_loss_on_upgrade():
    from services.return_grade_impairment import compute
    c = compute(100000, 20000, 100, 40, 5)
    assert c["unit_loss"] == 20000 and c["amount"] == 100000 and c["capped_to_book"]
    assert compute(100000, 50000, 40, 100, 5)["amount"] == 0


# ── LN-093-T01 / T04 ─────────────────────────────────────────────────────────
def test_stage1_keep_and_internal_return_idempotent():
    pair = make_interco()
    rid = make_return()
    keep, back, race = (make_roll(rid, KSC, pair=pair) for _ in range(3))
    wh_before = DB.inventory_rolls.find_one({"id": back})["warehouse_id"]
    v = rows(rid)
    assert v[keep]["stage"] == "internal_pending" and v[keep]["seller_name"]
    r = requests.post(f"{BASE}/sales-returns/{rid}/disposition/internal", headers=H_KSC,
                      json={"roll_ids": [keep], "decision": "keep", "reason": "disimpan Sukacita"})
    assert r.status_code == 200, r.text
    assert DB.inventory_rolls.find_one({"id": keep})["owner_entity_id"] == KSC
    assert rows(rid)[keep]["stage"] == "kept_internal"
    r = requests.post(f"{BASE}/sales-returns/{rid}/disposition/internal", headers=H_KSC,
                      json={"roll_ids": [back], "decision": "return_internal", "reason": "kembalikan ke CST"})
    assert r.status_code == 200, r.text
    icr = r.json()["interco_returns"][0]
    docs = list(DB.interco_returns.find({"source_sales_return_id": rid}))
    assert len(docs) == 2 and {d["role"] for d in docs} == {"returner", "receiver"}
    assert all(d["mandatory_accept"] for d in docs)
    assert docs[0]["items"][0]["roll_ids"] == [back]
    rb = DB.inventory_rolls.find_one({"id": back})
    assert rb["warehouse_id"] == wh_before and rb["disposition"]["internal"]["interco_return_number"] == icr["number"]
    dup = requests.post(f"{BASE}/sales-returns/{rid}/disposition/internal", headers=H_KSC,
                        json={"roll_ids": [back], "decision": "return_internal", "reason": "kembalikan lagi"})
    assert dup.status_code == 400
    with ThreadPoolExecutor(4) as ex:
        codes = list(ex.map(lambda _: requests.post(
            f"{BASE}/sales-returns/{rid}/disposition/internal", headers=H_KSC,
            json={"roll_ids": [race], "decision": "return_internal", "reason": "klik ganda"}).status_code, range(4)))
    assert codes.count(200) == 1, codes
    assert DB.interco_returns.count_documents({"source_sales_return_id": rid}) == 4
    receiver = next(d for d in docs if d["role"] == "receiver")
    c = requests.post(f"{BASE}/interco/returns/{receiver['id']}/cancel", headers=H_CST, json={"reason": "CST menolak"})
    assert c.status_code == 400 and "wajib menerima" in c.json()["detail"]
    returner = next(d for d in docs if d["role"] == "returner")
    c = requests.post(f"{BASE}/interco/returns/{returner['id']}/cancel", headers=H_KSC, json={"reason": "Sukacita batal"})
    assert c.status_code == 200, c.text
    assert rows(rid)[back]["stage"] == "internal_pending"


# ── LN-093-T03 ───────────────────────────────────────────────────────────────
def test_stage2_expired_window_auto_keeps_without_making_sellable():
    pair = make_interco()
    rid = make_return()
    old = make_roll(rid, CST, status="quarantine", grade="C", pair=pair, receipt_days=40,
                    disposition={"internal": {"decision": "return_internal", "status": "done"}})
    v = rows(rid, H_CST)[old]
    assert v["supplier_window_expired"] and v["stage"] == "supplier_keep" and v["supplier"]["auto"]
    assert not v["sellable"]
    assert DB.inventory_rolls.find_one({"id": old})["status"] == "quarantine"


def test_stage2_supplier_return_in_cst_entity_and_block_when_expired():
    pair = make_interco()
    rid = make_return()
    fresh = make_roll(rid, CST, pair=pair, receipt_days=2,
                      disposition={"internal": {"decision": "return_internal", "status": "done"}})
    assert rows(rid, H_CST)[fresh]["stage"] == "supplier_pending"
    r = requests.post(f"{BASE}/sales-returns/{rid}/disposition/supplier", headers=H_CST,
                      json={"roll_ids": [fresh], "decision": "supplier_return", "reason": "cacat ke supplier"})
    assert r.status_code == 200, r.text
    pr = DB.purchase_returns.find_one({"origin_sales_return_id": rid})
    assert pr["entity_id"] == CST and pr["supplier_id"] == PO["supplier_id"] and pr["po_id"] == PO["id"]
    assert rows(rid, H_CST)[fresh]["stage"] == "supplier_supplier_return"
    dup = requests.post(f"{BASE}/sales-returns/{rid}/disposition/supplier", headers=H_CST,
                        json={"roll_ids": [fresh], "decision": "supplier_return", "reason": "lagi"})
    assert dup.status_code == 400
    assert DB.purchase_returns.count_documents({"origin_sales_return_id": rid}) == 1


def test_stage2_dispose_requires_photo_and_writes_off():
    pair = make_interco()
    rid = make_return()
    bs = make_roll(rid, CST, grade="BS", pair=pair, unit_cost=1000,
                   disposition={"internal": {"decision": "return_internal", "status": "done"}})
    no_photo = requests.post(f"{BASE}/sales-returns/{rid}/disposition/supplier", headers=H_CST,
                             json={"roll_ids": [bs], "decision": "dispose", "reason": "BS dibuang"})
    assert no_photo.status_code == 400 and "foto" in no_photo.json()["detail"]
    r = requests.post(f"{BASE}/sales-returns/{rid}/disposition/supplier", headers=H_CST,
                      json={"roll_ids": [bs], "decision": "dispose", "reason": "BS dibuang", "attachment_ids": ["att_img"]})
    assert r.status_code == 200, r.text
    assert r.json()["writeoff_total"] == 10000
    rr = DB.inventory_rolls.find_one({"id": bs})
    assert rr["status"] == "damaged" and rr["length_remaining"] == 0
    assert DB.journal_entries.find_one({"source_type": "inventory_writeoff", "source_id": bs})
    assert DB.inventory_movements.find_one({"roll_id": bs, "movement_type": "return_disposal", "direction": "out"})


def test_wrong_owner_cannot_decide_stage2():
    pair = make_interco()
    rid = make_return()
    roll = make_roll(rid, CST, pair=pair, disposition={"internal": {"decision": "return_internal", "status": "done"}})
    r = requests.post(f"{BASE}/sales-returns/{rid}/disposition/internal", headers=H_KSC,
                      json={"roll_ids": [roll], "decision": "keep", "reason": "salah tahap"})
    assert r.status_code == 400


# ── Meja CST + pengingat batas supplier ─────────────────────────────────────
def test_cst_inbox_lists_incoming_and_pending_rolls():
    pair = make_interco()
    rid = make_return(status="refund_settled")
    back = make_roll(rid, KSC, pair=pair)
    r = requests.post(f"{BASE}/sales-returns/{rid}/disposition/internal", headers=H_KSC,
                      json={"roll_ids": [back], "decision": "return_internal", "reason": "kembalikan ke CST"})
    assert r.status_code == 200, r.text
    pend = make_roll(rid, CST, pair=pair, receipt_days=2,
                     disposition={"internal": {"decision": "return_internal", "status": "done"}})
    box = requests.get(f"{BASE}/return-dispositions/inbox", params={"entity_id": CST}, headers=H_CST)
    assert box.status_code == 200, box.text
    data = box.json()
    rc = next(x for x in data["incoming"] if x["source_sales_return_number"].startswith(TAG))
    assert rc["status"] == "draft" and "customer_name" not in rc
    case = next(c for c in data["cases"] if c["return_id"] == rid)
    assert [x["roll_id"] for x in case["rows"]] == [pend]
    ksc_box = requests.get(f"{BASE}/return-dispositions/inbox", params={"entity_id": KSC}, headers=H_KSC).json()
    assert not any(c["return_id"] == rid for c in ksc_box["cases"])


def test_disposition_photo_on_settled_return_then_dispose():
    pair = make_interco()
    rid = make_return(status="refund_settled")
    bs = make_roll(rid, CST, grade="BS", pair=pair, unit_cost=500,
                   disposition={"internal": {"decision": "return_internal", "status": "done"}})
    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
    up = requests.post(f"{BASE}/sales-returns/{rid}/disposition/photos", headers=H_CST,
                       files={"file": ("kamera.png", png, "image/png")})
    assert up.status_code == 200, up.text
    att = up.json()
    assert requests.get(f"{BASE}/sales-returns/{rid}/disposition/photos/{att['id']}", headers=H_CST).status_code == 200
    r = requests.post(f"{BASE}/sales-returns/{rid}/disposition/supplier", headers=H_CST,
                      json={"roll_ids": [bs], "decision": "dispose", "reason": "BS dibuang", "attachment_ids": [att["id"]]})
    assert r.status_code == 200, r.text


def test_supplier_deadline_reminder_job_notifies_cst_roles_once():
    import asyncio
    import sys
    sys.path.insert(0, "/app/backend")
    from services import return_disposition_service as rds
    pair = make_interco()
    rid = make_return()
    # supplier uji punya kebijakan 30 hari → terima 28 hari lalu = 2 hari lagi (≤ 3 hari pengingat)
    roll = make_roll(rid, CST, pair=pair, receipt_days=28,
                     disposition={"internal": {"decision": "return_internal", "status": "done"}})

    async def run():
        await rds.job_supplier_deadline_reminder()
        await rds.job_supplier_deadline_reminder()
    asyncio.run(run())
    notes = list(DB.notifications.find({"type": "return_supplier_deadline", "ref": {"$regex": f"^{roll}:"}}))
    assert {n["recipient_role"] for n in notes} == {"warehouse_admin", "admin", "finance"}
    assert all(n["entity_id"] == CST for n in notes)
    assert DB.notifications.count_documents({"type": "return_supplier_deadline", "ref": {"$regex": f"^{roll}:"}}) == 3
    DB.notifications.delete_many({"type": "return_supplier_deadline", "ref": {"$regex": f"^{roll}:"}})
