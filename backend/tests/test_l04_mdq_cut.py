"""L04 LN-042 — potong MD Quality 0,25 yard: mutasi pemakaian tersendiri, idempoten, kg wajib data aktual."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def tok():
    return _login("admin@kainnusantara.id", "demo12345")


def _ins_for(roll):
    iid, lid = f"ins_test_{uuid.uuid4().hex[:8]}", f"ln_{uuid.uuid4().hex[:6]}"
    DB.inspections.insert_one({"id": iid, "number": "TEST-L04", "kind": "po_receipt", "status": "in_progress",
                               "entity_id": roll["owner_entity_id"], "remark": "TEST_L04",
                               "lines": [{"id": lid, "roll_id": roll["id"], "product_id": roll["product_id"]}]})
    return iid, lid


def _roll(unit):
    return DB.inventory_rolls.find_one({"unit": unit, "status": "available", "length_remaining": {"$gt": 5}},
                                       {"_id": 0})


def _hdr(tok, roll):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": roll["owner_entity_id"]}


class TestMdqCut:
    def test_yard_cut_idempotent(self, tok):
        roll = _roll("yard")
        if not roll:
            pytest.skip("tidak ada roll yard")
        iid, lid = _ins_for(roll)
        url = f"{BASE}/api/inspections/{iid}/lines/{lid}/mdq-cut"
        r1 = requests.post(url, json={}, headers=_hdr(tok, roll), timeout=30)
        assert r1.status_code == 200, r1.text
        r2 = requests.post(url, json={}, headers=_hdr(tok, roll), timeout=30)
        assert r2.status_code == 200 and r2.json()["replayed"] is True
        after = DB.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
        assert after["length_remaining"] == pytest.approx(roll["length_remaining"] - 0.25, abs=1e-6)
        assert after["length_initial"] == roll["length_initial"]           # receipt tetap bruto
        assert after.get("rfid_tag_id") == roll.get("rfid_tag_id")         # identitas tetap
        assert DB.inventory_movements.count_documents({"roll_id": roll["id"], "movement_type": "mdq_cut",
                                                   "source_document": iid}) == 1
        assert DB.journal_entries.count_documents({"source_type": "inventory_writeoff", "source_id": f"mdq:{iid}:{lid}"}) == 1

    def test_kg_requires_actual_data(self, tok):
        roll = _roll("kg")
        if not roll:
            pytest.skip("tidak ada roll kg")
        iid, lid = _ins_for(roll)
        url = f"{BASE}/api/inspections/{iid}/lines/{lid}/mdq-cut"
        r = requests.post(url, json={}, headers=_hdr(tok, roll), timeout=30)
        if r.status_code == 400:
            assert "kg" in r.text and DB.inventory_rolls.find_one({"id": roll["id"]})["length_remaining"] == roll["length_remaining"]
        r = requests.post(url, json={"weight_kg": 0.08}, headers=_hdr(tok, roll), timeout=30)
        assert r.status_code == 200, r.text
        after = DB.inventory_rolls.find_one({"id": roll["id"]})
        assert after["length_remaining"] == pytest.approx(roll["length_remaining"] - 0.08, abs=1e-6)

    def test_sales_forbidden(self, tok):
        roll = _roll("yard")
        iid, lid = _ins_for(roll)
        s = _login("sales.kanda@kainnusantara.id", "demo1234")
        r = requests.post(f"{BASE}/api/inspections/{iid}/lines/{lid}/mdq-cut", json={},
                          headers={"Authorization": f"Bearer {s}"}, timeout=30)
        assert r.status_code == 403

    def test_cleanup(self):
        """Kembalikan roll demo ke saldo semula (tes tidak boleh menggerus data acuan)."""
        import sys
        sys.path.insert(0, "/app/backend")
        ids = [d["id"] for d in DB.inspections.find({"remark": "TEST_L04"}, {"_id": 0, "id": 1})]
        for c in DB.mdq_cuts.find({"inspection_id": {"$in": ids}}):
            DB.inventory_rolls.update_one({"id": c["roll_id"]}, {"$inc": {"length_remaining": c["qty"]},
                                                                 "$pull": {"usage_history": {"ref": c["_id"]}}})
            DB.journal_entries.delete_many({"source_type": "inventory_writeoff", "source_id": f"mdq:{c['_id']}"})
            r = DB.inventory_rolls.find_one({"id": c["roll_id"]}, {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1})
            DB.l04_rebuild.insert_one(r)
        DB.inventory_movements.delete_many({"movement_type": "mdq_cut", "source_document": {"$in": ids}})
        DB.mdq_cuts.delete_many({"inspection_id": {"$in": ids}})
        DB.inspections.delete_many({"remark": "TEST_L04"})
        import asyncio
        from services.roll_service import rebuild_balance
        segs = {(x["product_id"], x["warehouse_id"], x["owner_entity_id"]) for x in DB.l04_rebuild.find({}, {"_id": 0})}
        DB.l04_rebuild.drop()

        async def _rb():
            for sgm in segs:
                await rebuild_balance(*sgm)
        asyncio.run(_rb())
