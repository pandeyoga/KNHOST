"""Integrasi PREP-B × PREP-C — pembekuan pendaftaran awal (K-OPN-03) juga berlaku di jalur putaway baru PREP-C:
terbit draf (`putaway_draft_service.publish`), trip tiba (`putaway_arrival_service.confirm_arrival_trip`), dan tutup
sisa (`close_remaining`). Dokumen uji disisipkan langsung (id berprefiks TEST_INTFZ_) dan dihapus di akhir.
"""
import os
import sys
import uuid

import pytest
from fastapi import HTTPException
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

from services import putaway_arrival_service as arr  # noqa: E402
from services import putaway_draft_service as drf  # noqa: E402
from services import registration_freeze as rfz  # noqa: E402

T = f"TEST_INTFZ_{uuid.uuid4().hex[:6]}"
WH = f"{T}_wh"
ENT = "ent_ksc"


@pytest.fixture(scope="module")
def mdb():
    m = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    yield m
    m.cycle_count_sessions.delete_many({"id": {"$regex": f"^{T}"}})
    m.putaway_orders.delete_many({"id": {"$regex": f"^{T}"}})


def _freeze(mdb, active=True):
    mdb.cycle_count_sessions.update_one(
        {"id": f"{T}_sess"},
        {"$set": {"id": f"{T}_sess", "name": f"{T} sesi", "mode": "registration", "warehouse_id": WH,
                  "freeze": {"active": active, "mode": "warehouse", "bin_ids": []}}}, upsert=True)


def _order(mdb, oid, status, items):
    mdb.putaway_orders.replace_one({"id": oid}, {
        "id": oid, "pa_number": oid, "status": status, "owner_entity_id": ENT, "entity_id": ENT,
        "from_warehouse_id": f"{T}_src", "to_warehouse_id": WH, "items": items}, upsert=True)


def _code(exc: HTTPException) -> str:
    d = exc.detail
    return d.get("code", "") if isinstance(d, dict) else ""


def test_trip_tiba_ditolak_saat_gudang_tujuan_beku(mdb):
    _freeze(mdb, True)
    _order(mdb, f"{T}_pa1", "in_transit", [{"roll_id": f"{T}_r1", "status": "pending", "epc": "E1"}])
    with pytest.raises(HTTPException) as e:
        run(arr.confirm_arrival_trip(f"{T}_pa1", ["E1"], {"type": "handheld", "client_trip_id": "t1"}, "uji"))
    assert e.value.status_code == 409 and _code(e.value) == rfz.FREEZE_CODE
    assert mdb.putaway_orders.find_one({"id": f"{T}_pa1"})["status"] == "in_transit"   # tidak ada efek


def test_tutup_sisa_ditolak_saat_beku(mdb):
    _freeze(mdb, True)
    _order(mdb, f"{T}_pa2", "partially_received", [{"roll_id": f"{T}_r2", "status": "pending", "epc": "E2"}])
    with pytest.raises(HTTPException) as e:
        run(arr.close_remaining(f"{T}_pa2", "return_transit", "uji pembekuan tutup sisa", None, "uji"))
    assert e.value.status_code == 409 and _code(e.value) == rfz.FREEZE_CODE


def test_terbit_draf_ditolak_saat_beku(mdb, monkeypatch):
    _freeze(mdb, True)
    order = {"id": f"{T}_pa3", "pa_number": f"{T}_pa3", "status": "draft", "draft_rev": 0, "owner_entity_id": ENT,
             "from_warehouse_id": f"{T}_src", "to_warehouse_id": WH, "items": [{"roll_id": f"{T}_r3"}]}

    async def _draft(order_id, scope_ids):
        return order

    async def _ready(o, wh_to):
        return {f"{T}_r3": (None, {"epc": "E3"})}

    monkeypatch.setattr(drf, "_draft", _draft)
    monkeypatch.setattr(drf, "_readiness", _ready)
    with pytest.raises(HTTPException) as e:
        run(drf.publish(f"{T}_pa3", [ENT], "uji"))
    assert e.value.status_code == 409 and _code(e.value) == rfz.FREEZE_CODE


def test_tanpa_pembekuan_kait_lolos(mdb):
    _freeze(mdb, False)
    order = {"id": f"{T}_pa4", "to_warehouse_id": WH, "items": [{"roll_id": f"{T}_r4"}]}
    run(rfz.assert_order_movable(order, "mencatat trip tiba perintah putaway"))   # tidak melempar
