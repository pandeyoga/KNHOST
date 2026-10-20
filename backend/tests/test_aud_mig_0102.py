"""AUD-MIG-01 / AUD-MIG-02 (review 2026-10-19) — migrasi `linked_po_id` → `fulfillment` (scripts/migrate_l03_ln033_fulfillment.py).

MIG-01: fulfillment `{}` dianggap kandidat tetapi update mensyaratkan field tidak ada → laporan "matched" tanpa tulisan.
MIG-02: rollback menghapus state migrasi walau sudah dipakai operasional (versi 2, route makloon, MKO, riwayat).
Migrasi dijalankan in-process terhadap DATABASE TERISOLASI (`kn_test_mig_<tag>`, dibuang di akhir) — data demo tidak
tersentuh; `db` modul skrip diganti klien Motor ke database itu. Satu event loop untuk seluruh modul.
Jalankan: cd /app/backend && python -m pytest tests/test_aud_mig_0102.py -p no:randomly -n 0 -q
"""
import asyncio
import importlib.util
import os
import uuid

import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
ISO = f"kn_test_mig_{uuid.uuid4().hex[:6]}"
DB = MongoClient(URL)[ISO]
LOOP = asyncio.new_event_loop()
SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                      "scripts", "migrate_l03_ln033_fulfillment.py")
_spec = importlib.util.spec_from_file_location("mig_ln033", SCRIPT)
mig = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mig)
PROD = "prod_TEST_MIG"


def run(coro):
    return LOOP.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def isolated_db():
    async def mk():
        return AsyncIOMotorClient(URL)[ISO]
    old, mig.db = mig.db, run(mk())
    yield
    mig.db = old
    MongoClient(URL).drop_database(ISO)
    LOOP.close()


@pytest.fixture(autouse=True)
def clean():
    for c in ("special_orders", "purchase_orders", "special_order_reconciliation"):
        DB[c].delete_many({})
    yield


def _od(n, fulfillment="__absent__", po_key=None):
    po = f"po_{n}"
    DB.purchase_orders.insert_one({"id": po, "po_number": f"PO-{n}", "status": "approved",
                                   "items": [{"product_id": PROD, "quantity": 10, "unit": "kg"}],
                                   **({"special_order_item_key": po_key} if po_key else {})})
    od = {"id": f"sord_{n}", "number": f"OD-{n}", "linked_po_id": po, "linked_po_number": f"PO-{n}",
          "items": [{"id": "it1"}], "pricing": {"product_id": PROD}}
    if fulfillment != "__absent__":
        od["fulfillment"] = fulfillment
    DB.special_orders.insert_one(od)
    return od["id"], po


def _f(od_id):
    return (DB.special_orders.find_one({"id": od_id}) or {}).get("fulfillment")


def _po_key(po):
    return DB.purchase_orders.find_one({"id": po}).get("special_order_item_key")


# ─── AUD-MIG-01 ────────────────────────────────────────────────────────────────
def test_tidak_ada_kosong_dan_null_semua_tertulis_dan_dilaporkan_applied():
    ids = [_od("absent"), _od("kosong", {}), _od("null", None)]
    rep = run(mig.main("apply"))
    for od_id, po in ids:
        f = _f(od_id)
        assert f and f["it1"]["docs"][0]["id"] == po and f["it1"]["version"] == 1, (od_id, f)
        assert _po_key(po) == "it1"
    assert len(rep["matched"]) == 3 and len(rep["applied"]) == 3 and rep["conflicts"] == []


def test_state_aktif_tidak_disentuh():
    active = {"it1": {"route": "makloon", "version": 3, "docs": [{"type": "mko", "id": "mko_x"}]}}
    od_id, po = _od("aktif", active)
    rep = run(mig.main("apply"))
    assert _f(od_id) == active and _po_key(po) is None
    assert rep["skipped_has_fulfillment"] == 1 and rep["applied"] == []


def test_perubahan_bersamaan_tidak_ditimpa_dan_dilaporkan_konflik(monkeypatch):
    od_id, po = _od("balapan", {})
    concurrent = {"it1": {"route": "makloon", "version": 1, "docs": [], "by": "proses lain"}}
    orig = mig.classify

    async def racing(od):
        out = await orig(od)
        DB.special_orders.update_one({"id": od["id"]}, {"$set": {"fulfillment": concurrent}})   # proses lain menang
        return out
    monkeypatch.setattr(mig, "classify", racing)
    rep = run(mig.main("apply"))
    assert _f(od_id) == concurrent and _po_key(po) is None
    assert len(rep["matched"]) == 1 and rep["applied"] == [] and len(rep["conflicts"]) == 1


def test_po_sudah_tertaut_item_lain_tidak_ditimpa():
    od_id, po = _od("po_lain", po_key="item_lain")
    rep = run(mig.main("apply"))
    assert not _f(od_id) and _po_key(po) == "item_lain"
    assert rep["applied"] == [] and "item lain" in rep["conflicts"][0]["why"]


# ─── AUD-MIG-02 ────────────────────────────────────────────────────────────────
def test_rollback_state_belum_berubah_dibatalkan_dan_tautan_po_dipulihkan():
    od_id, po = _od("murni")
    run(mig.main("apply"))
    rep = run(mig.main("rollback"))
    assert "it1" not in (_f(od_id) or {}) and _po_key(po) is None
    assert len(rep["rolled_back"]) == 1 and rep["rollback_conflicts"] == []


@pytest.mark.parametrize("change", ["route_versi2_mko_riwayat", "dokumen_baru"])
def test_rollback_sesudah_perubahan_operasional_tidak_menghapus(change):
    od_id, po = _od(f"ops_{change}")
    run(mig.main("apply"))
    if change == "route_versi2_mko_riwayat":   # skenario reviewer
        DB.special_orders.update_one({"id": od_id}, {"$set": {
            "fulfillment.it1.route": "makloon", "fulfillment.it1.version": 2,
            "fulfillment.it1.docs": [{"id": "mko-new", "type": "mko"}],
            "fulfillment.it1.history": [{"after": "makloon", "reason": "approved operational change"}]}})
    else:
        DB.special_orders.update_one({"id": od_id}, {"$push": {"fulfillment.it1.docs": {"type": "po", "id": "po_baru"}}})
    before = _f(od_id)
    rep = run(mig.main("rollback"))
    assert _f(od_id) == before and _po_key(po) == "it1"
    assert rep["rolled_back"] == [] and len(rep["rollback_conflicts"]) == 1
    rec = list(DB.special_order_reconciliation.find({"special_order_id": od_id, "reason": "rollback_conflict"}))
    assert len(rec) == 1
    rep2 = run(mig.main("rollback"))                                       # rollback ulang: tetap aman, tanpa duplikat
    assert _f(od_id) == before and len(rep2["rollback_conflicts"]) == 1
    assert DB.special_order_reconciliation.count_documents({"special_order_id": od_id, "reason": "rollback_conflict"}) == 1


def test_rollback_ulang_dan_apply_ulang():
    od_id, po = _od("ulang")
    run(mig.main("apply"))
    run(mig.main("rollback"))
    rep = run(mig.main("rollback"))
    assert rep["rolled_back"] == [] and rep["rollback_conflicts"] == []
    rep = run(mig.main("apply"))                                            # fulfillment {} → kandidat lagi
    assert len(rep["applied"]) == 1 and _f(od_id)["it1"]["version"] == 1 and _po_key(po) == "it1"


def test_rollback_migrasi_versi_lama_tanpa_salinan():
    pristine = {"route": "purchase", "default_route": "", "source_mode": "legacy", "reason": "migrasi linked_po_id",
                "deviation": False, "version": 1, "status": "realized", "migrated": True, "migrated_at": "2026-10-01",
                "pr_id": "", "pr_number": "", "docs": [{"type": "po", "id": "po_lama1"}]}
    a, _ = _od("lama1", {"it1": pristine})
    b, _ = _od("lama2", {"it1": {**pristine, "version": 2, "history": [{"after": "makloon"}]}})
    rep = run(mig.main("rollback"))
    assert "it1" not in (_f(a) or {}) and _f(b)["it1"]["version"] == 2
    assert [r["id"] for r in rep["rolled_back"]] == [a] and [r["id"] for r in rep["rollback_conflicts"]] == [b]


def test_opsi_only_membatasi_cakupan():
    a, _ = _od("only_a")
    b, _ = _od("only_b")
    rep = run(mig.main("apply", [a]))
    assert [r["id"] for r in rep["applied"]] == [a] and not _f(b)
