"""L05 LN-050-T01 — Request QC dari checkout SO: hanya kebutuhan relevan muncul, dispatch menunggu QC yang diwajibkan."""
import asyncio
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


_LOOP = asyncio.new_event_loop()


def _h():
    t = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30).json()["token"]
    return {"Authorization": f"Bearer {t}", "X-Entity-Id": "ent_ksc"}


def _guard(so_id):
    import sys
    sys.path.insert(0, "/app/backend")
    from services import loading_check_service as lc

    async def run():
        try:
            await lc.qc_request_guard(so_id)
            return None
        except Exception as exc:  # noqa: BLE001
            return getattr(exc, "detail", str(exc))
    return _LOOP.run_until_complete(run())


@pytest.fixture()
def so_factory():
    made = []

    def mk(mode, pct=10):
        rolls = list(DB.inventory_rolls.find({"status": "available", "owner_entity_id": "ent_ksc"}, {"_id": 0}).limit(3))
        sid = f"so_test_{uuid.uuid4().hex[:8]}"
        DB.sales_orders.insert_one({"id": sid, "number": f"TEST-SO-{sid[-4:]}", "entity_id": "ent_ksc", "status": "confirmed",
                                    "customer_id": "", "customer_name": "TEST QC", "created_at": "2026-10-16",
                                    "qc_request": ({"mode": mode, "sample_pct": pct, "status": "required"} if mode != "none"
                                                   else {"mode": "none", "status": "not_required"})})
        for r in rolls:
            DB.inventory_rolls.update_one({"id": r["id"]}, {"$set": {"status": "reserved", "reserved_ref": {"type": "sales_order", "id": sid}}})
        made.append((sid, rolls))
        return sid, rolls
    yield mk
    for sid, rolls in made:
        for r in rolls:
            DB.inventory_rolls.replace_one({"id": r["id"]}, r)
        DB.inspections.delete_many({"ref_doc_id": sid})
        DB.sales_orders.delete_one({"id": sid})


def _spk(h, sid):
    return requests.post(f"{BASE}/inspections", json={"kind": "sales_order", "ref_doc_id": sid}, headers=h, timeout=30)


def _finish(h, doc, decision):
    uid = DB.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0, "id": 1})["id"]
    requests.post(f"{BASE}/inspections/{doc['id']}/assign", json={"assigned_to": uid}, headers=h, timeout=30)
    requests.post(f"{BASE}/inspections/{doc['id']}/start", json={}, headers=h, timeout=30)
    for ln in doc["lines"]:
        r = requests.post(f"{BASE}/inspections/{doc['id']}/lines/{ln['id']}/inspect",
                          json={"part": "qc", "defects": [], "inspect_length_yard": 30}, headers=h, timeout=30)
        assert r.status_code == 200, r.text[:200]
    r = requests.post(f"{BASE}/inspections/{doc['id']}/finish", json={"decision": decision, "remark": "TEST alasan keputusan"}, headers=h, timeout=30)
    return r


def test_no_qc_request_no_need_and_no_block(so_factory):
    h = _h()
    sid, _ = so_factory("none")
    assert _spk(h, sid).status_code == 400
    opts = requests.get(f"{BASE}/inspections/meta/ref-docs", params={"kind": "sales_order"}, headers=h, timeout=30).json()
    assert sid not in [o["value"] for o in opts.get("items", [])]
    assert _guard(sid) is None


def test_full_qc_blocks_until_passed_and_covers_new_allocation(so_factory):
    h = _h()
    sid, rolls = so_factory("full")
    opts = requests.get(f"{BASE}/inspections/meta/ref-docs", params={"kind": "sales_order"}, headers=h, timeout=30).json()
    assert sid in [o["value"] for o in opts.get("items", [])]
    assert "meminta QC" in (_guard(sid) or "")
    r = _spk(h, sid)
    assert r.status_code == 200, r.text[:200]
    doc = r.json()
    assert {ln["roll_id"] for ln in doc["lines"]} == {x["id"] for x in rolls}
    assert _finish(h, doc, "terima").status_code == 200
    assert DB.sales_orders.find_one({"id": sid})["qc_request"]["status"] == "passed"
    assert _guard(sid) is None
    extra = DB.inventory_rolls.find_one({"status": "available", "owner_entity_id": "ent_ksc"}, {"_id": 0})
    DB.inventory_rolls.update_one({"id": extra["id"]}, {"$set": {"status": "reserved", "reserved_ref": {"type": "sales_order", "id": sid}}})
    try:
        assert "belum di-QC" in (_guard(sid) or "")                     # alokasi berubah → QC lagi
    finally:
        DB.inventory_rolls.replace_one({"id": extra["id"]}, extra)


def test_sampling_and_rejected_blocks(so_factory):
    h = _h()
    sid, _ = so_factory("sampling", 34)
    doc = _spk(h, sid).json()
    assert len(doc["lines"]) == 2                                          # ceil(3 × 34%) = 2
    assert _finish(h, doc, "tolak").status_code == 200
    assert DB.sales_orders.find_one({"id": sid})["qc_request"]["status"] == "failed"
    assert "meminta QC" in (_guard(sid) or "")


def test_cut_length_reservation_and_relisting_after_reallocation(so_factory):
    h = _h()
    sid, rolls = so_factory("full")
    cut = DB.inventory_rolls.find_one({"status": "available", "owner_entity_id": "ent_ksc", "length_remaining": {"$gt": 20}}, {"_id": 0})
    DB.inventory_rolls.update_one({"id": cut["id"]}, {"$set": {"length_reservations": [
        {"id": "rsv_test", "ref": {"type": "sales_order", "id": sid}, "qty": 10, "status": "reserved"}], "length_reserved": 10}})
    try:
        doc = _spk(h, sid).json()
        assert cut["id"] in {ln["roll_id"] for ln in doc["lines"]} and len(doc["lines"]) == 4   # roll potong ikut
        assert _finish(h, doc, "terima").status_code == 200
        assert _guard(sid) is None
        listed = lambda: sid in [o["value"] for o in requests.get(f"{BASE}/inspections/meta/ref-docs", params={"kind": "sales_order"}, headers=h, timeout=30).json()["items"]]  # noqa: E731
        assert not listed()
        extra = DB.inventory_rolls.find_one({"status": "available", "owner_entity_id": "ent_ksc", "id": {"$ne": cut["id"]}}, {"_id": 0})
        DB.inventory_rolls.update_one({"id": extra["id"]}, {"$set": {"status": "reserved", "reserved_ref": {"type": "sales_order", "id": sid}}})
        try:
            assert listed()                                                   # alokasi berubah → muncul lagi di pemilih
            assert "belum di-QC" in (_guard(sid) or "")
        finally:
            DB.inventory_rolls.replace_one({"id": extra["id"]}, extra)
    finally:
        DB.inventory_rolls.replace_one({"id": cut["id"]}, cut)
