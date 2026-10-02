"""GRN Fase 7 — beralih penuh: mode penerimaan per badan usaha.

Membuktikan: status mode per entitas, ganti mode butuh alasan & hak admin/manajer, tugas yang sudah dimulai ditandai
`legacy_in_flight` (tetap boleh jalur lama), tugas baru ditolak jalur lama (409 GRN_MODE), terima hasil MKO langsung
ditolak di mode GRN, dan kembali ke mode lama membuka jalur lama lagi.
"""
import sys

import pytest

sys.path.insert(0, "/app/backend/tests")
import test_grn_phase2 as _p2  # noqa: E402
from test_grn_phase2 import BASE, _ok  # noqa: E402

admin, wh, mdb, env = _p2.admin, _p2.wh, _p2.mdb, _p2.env
ENT = "ent_ksc"


@pytest.fixture()
def grn_mode(admin, mdb):
    before = set(mdb.wms_tasks.distinct("id", {"legacy_in_flight": True}))

    def _set(mode):
        return admin.put(f"{BASE}/goods-receipts/mode", json={"entity_id": ENT, "mode": mode, "reason": "TEST_ uji fase 7"})
    yield _set
    _set("legacy")   # lalu cabut lapisan entitas → kembali mewarisi global (uji lain mengatur mode global)
    _ok(admin.post(f"{BASE}/config/values/clear", json={"key": "receiving.mode", "scope_type": "entity", "scope_id": ENT,
                                                        "reason": "TEST_ bersih fase 7"}))
    mdb.wms_tasks.update_many({"legacy_in_flight": True, "id": {"$nin": list(before)}},
                              {"$unset": {"legacy_in_flight": "", "legacy_in_flight_at": ""}})


def test_mode_status_lists_entities(admin):
    st = _ok(admin.get(f"{BASE}/goods-receipts/mode"))
    row = next(r for r in st["entities"] if r["entity_id"] == ENT)
    assert row["mode"] == "legacy" and st["modes"][ENT] == "legacy"
    assert {"waiting_tasks", "started_legacy", "legacy_in_flight", "open_grns", "closed_grns"} <= set(row)


def test_switch_requires_reason_and_role(admin, wh):
    assert admin.put(f"{BASE}/goods-receipts/mode", json={"entity_id": ENT, "mode": "grn", "reason": ""}).status_code == 422
    assert wh.put(f"{BASE}/goods-receipts/mode", json={"entity_id": ENT, "mode": "grn",
                                                        "reason": "TEST_ tidak boleh"}).status_code == 403
    assert _ok(admin.get(f"{BASE}/goods-receipts/mode"))["modes"][ENT] == "legacy"


def test_grn_mode_blocks_new_legacy_receipts_but_not_in_flight(admin, wh, mdb, env, grn_mode):
    _, clone = env
    started = clone()
    fresh = clone(park_seed=True)
    mdb.wms_tasks.update_one({"id": started["id"]}, {"$set": {"status": "receiving", "received_qty": 10}})
    res = _ok(grn_mode("grn"))
    assert res["mode"] == "grn" and res["legacy_in_flight_marked"] >= 1
    assert mdb.wms_tasks.find_one({"id": started["id"]})["legacy_in_flight"] is True
    assert not mdb.wms_tasks.find_one({"id": fresh["id"]}).get("legacy_in_flight")
    st = _ok(admin.get(f"{BASE}/goods-receipts/mode"))
    assert st["modes"][ENT] == "grn"
    row = next(r for r in st["entities"] if r["entity_id"] == ENT)
    assert any(t["id"] == started["id"] for t in row["legacy_in_flight"])
    # jalur lama untuk tugas baru → 409 GRN_MODE
    r = wh.post(f"{BASE}/inbound/tasks/{fresh['id']}/scan-receive", json={"product_id": fresh["product_id"], "actual_qty": 1})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "GRN_MODE"
    r = wh.post(f"{BASE}/inbound/tasks/{fresh['id']}/complete", json={})
    assert r.status_code == 409
    # terima hasil MKO langsung → 409 (lewat Kedatangan)
    r = admin.post(f"{BASE}/makloon-orders/mko_e7566f649bf7/receive", json={"step_seq": 1, "actual_output_qty": 1, "rolls": []})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "GRN_MODE"
    # kedatangan tetap bisa dibuat untuk tugas baru
    g, _dn = _p2._grn_review(admin, mdb, fresh, qty=5, rolls=1)
    assert g["status"] == "review"
    _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/cancel", json={"expected_version": g["version"], "reason": "TEST_ batal"}))
    # kembali ke mode lama → jalur lama terbuka lagi (guard tidak menolak)
    _ok(grn_mode("legacy"))
    r = admin.post(f"{BASE}/makloon-orders/mko_e7566f649bf7/receive", json={"step_seq": 1, "actual_output_qty": 1, "rolls": []})
    d = r.json().get("detail")
    assert not (isinstance(d, dict) and d.get("code") == "GRN_MODE"), d
