"""AUD-RET-01 (review 2026-10-19) — buang BS gagal di tengah dan tidak bisa dilanjutkan lewat retry.

Skenario reviewer: jurnal write-off & roll (nol/damaged) sudah tersimpan, insert movement gagal → klaim dihapus,
retry ditolak ("tidak sedang menunggu keputusan"). Kini: jejak operasi dipertahankan (tahap `supplier_dispose_failed`),
retry keputusan buang yang sama melanjutkan langkah tertinggal tanpa jurnal/pengurangan stok ganda.
Gangguan disuntikkan di tiap batas penulisan + kegagalan pada roll berikutnya; uji tingkat layanan memakai satu event
loop untuk seluruh modul (klien Motor modul `db` terikat ke loop pertama).
Jalankan: cd /app/backend && python -m pytest tests/test_aud_ret_01.py -p no:randomly -n 0 -q
"""
import asyncio
import os
import sys
import uuid

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import gl_service  # noqa: E402
from services import return_disposition_service as rds  # noqa: E402

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6]
WH, BUYER = "wh_jakarta", "ent_ksc"
# PT pemasok internal (CST) — id entitas diambil dari data (doc_prefix), bukan ditebak: kode nomor jurnal ikut entitas
SELLER = (DB.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}) or {}).get("id") or "ent_cst"
PROD = DB.products.find_one({"stage": "finished", "status": "active"}, {"_id": 0, "id": 1, "base_unit": 1})
PAIR = f"pair_TEST_RET_{TAG}"
ROLLS, RETS = [], []


@pytest.fixture(scope="module", autouse=True)
def seed():
    DB.interco_transactions.insert_many([
        {"id": f"ict_TEST_RET_{TAG}_s", "pair_id": PAIR, "role": "seller", "number": f"IC-T{TAG}", "status": "completed",
         "seller_entity_id": SELLER, "buyer_entity_id": BUYER},
        {"id": f"ict_TEST_RET_{TAG}_b", "pair_id": PAIR, "role": "buyer", "number": f"IC-T{TAG}-B", "status": "completed",
         "seller_entity_id": SELLER, "buyer_entity_id": BUYER}])
    yield
    DB.interco_transactions.delete_many({"pair_id": PAIR})
    DB.journal_entries.delete_many({"source_type": "inventory_writeoff", "source_id": {"$in": ROLLS}})
    DB.inventory_movements.delete_many({"roll_id": {"$in": ROLLS}})
    DB.inventory_rolls.delete_many({"id": {"$in": ROLLS}})
    DB.sales_returns.delete_many({"id": {"$in": RETS}})
    run(rds.rebuild_balance(PROD["id"], WH, SELLER))


def _case(n_rolls=1):
    rid = f"ret_TEST_RET_{TAG}_{len(RETS)}"
    DB.sales_returns.insert_one({"id": rid, "number": f"RTN-T{TAG}-{len(RETS)}", "entity_id": BUYER,
                                 "attachments": [{"id": "att_bukti", "content_type": "image/jpeg", "filename": "bukti.jpg"}]})
    RETS.append(rid)
    ids = []
    for _ in range(n_rolls):
        roll = f"roll_TEST_RET_{TAG}_{len(ROLLS)}"
        DB.inventory_rolls.insert_one({"id": roll, "roll_no": f"RTN-{TAG}-{len(ROLLS)}", "return_id": rid, "origin_type": "return",
                                       "product_id": PROD["id"], "warehouse_id": WH, "owner_entity_id": SELLER,
                                       "length_remaining": 100.0, "length_initial": 100.0, "unit": PROD.get("base_unit") or "yard",
                                       "unit_cost": 10, "grade": "BS", "status": "available", "origin_interco_pair_id": PAIR})
        ROLLS.append(roll)
        ids.append(roll)
    return DB.sales_returns.find_one({"id": rid}, {"_id": 0}), ids


def _dispose(ret, ids):
    return run(rds.decide_supplier(ret, ids, "dispose", "BS rusak berat uji", ["att_bukti"], "uji"))


def _stage(ret, roll):
    return {r["roll_id"]: r["stage"] for r in run(rds.view(ret))["rows"]}[roll]


def _assert_done_once(ret, ids):
    for roll in ids:
        assert DB.journal_entries.count_documents({"source_type": "inventory_writeoff", "source_id": roll,
                                                   "status": {"$ne": "void"}}) == 1, roll
        assert DB.inventory_movements.count_documents({"roll_id": roll, "movement_type": "return_disposal"}) == 1, roll
        r = DB.inventory_rolls.find_one({"id": roll})
        assert (r["status"], r["length_remaining"], r["disposed_qty"], r["writeoff_amount"]) == ("damaged", 0, 100.0, 1000.0)
        assert r["disposition"]["supplier"]["status"] == "done" and _stage(ret, roll) == "closed"


class _Coll:
    def __init__(self, coll, name, hook):
        self._c, self._name, self._hook = coll, name, hook

    def __getattr__(self, attr):
        fn = getattr(self._c, attr)
        if attr in ("insert_one", "update_one"):
            async def wrapped(*a, **kw):
                self._hook(self._name, attr, a)
                return await fn(*a, **kw)
            return wrapped
        return fn


class _DB:
    """Proksi `db` modul layanan: memanggil `hook` sebelum insert_one/update_one (untuk menyuntik gangguan)."""
    def __init__(self, real, hook):
        self._real, self._hook = real, hook

    def __getattr__(self, name):
        return _Coll(getattr(self._real, name), name, self._hook)

    def __getitem__(self, name):
        return _Coll(self._real[name], name, self._hook)


def _fail_db(monkeypatch, coll, op, when=lambda args: True, nth=1):
    st = {"n": 0}

    def hook(name, attr, args):
        if name == coll and attr == op and when(args):
            st["n"] += 1
            if st["n"] == nth:
                raise RuntimeError(f"gangguan {coll}.{op} (uji AUD-RET-01)")
    monkeypatch.setattr(rds, "db", _DB(rds.db, hook))


def _fail_fn(monkeypatch, obj, name):
    orig, st = getattr(obj, name), {"n": 0}

    async def flaky(*a, **kw):
        st["n"] += 1
        if st["n"] == 1:
            raise RuntimeError(f"gangguan {name} (uji AUD-RET-01)")
        return await orig(*a, **kw)
    monkeypatch.setattr(obj, name, flaky)


# ─── Skenario reviewer + tiap batas penulisan ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("boundary", ["movement", "roll", "rebuild", "finish"])
def test_gangguan_sesudah_sebagian_tersimpan_dilanjutkan_retry(monkeypatch, boundary):
    ret, ids = _case()
    if boundary == "movement":      # skenario reviewer
        _fail_db(monkeypatch, "inventory_movements", "insert_one")
    elif boundary == "roll":
        _fail_db(monkeypatch, "inventory_rolls", "update_one", lambda a: "disposal_key" in (a[0] if a else {}))
    elif boundary == "rebuild":
        _fail_fn(monkeypatch, rds, "rebuild_balance")
    else:
        _fail_fn(monkeypatch, rds, "_finish")
    with pytest.raises(RuntimeError):
        _dispose(ret, ids)
    monkeypatch.undo()
    r = DB.inventory_rolls.find_one({"id": ids[0]})
    assert r["disposition"]["supplier"]["status"] == "failed" and r["disposition"]["supplier"]["plan"]["qty"] == 100
    assert _stage(ret, ids[0]) == "supplier_dispose_failed"           # jejak operasi tidak dihapus
    out = run(rds.decide_supplier(ret, ids, "dispose", "", [], "uji ulang"))   # retry sah: lanjutkan
    assert out["resumed"] is True and out["writeoff_total"] == 1000
    _assert_done_once(ret, ids)
    with pytest.raises(rds.DispositionError):                         # selesai → tidak bisa diulang lagi
        _dispose(ret, ids)
    _assert_done_once(ret, ids)


def test_gangguan_di_jurnal_sebelum_apa_pun_tersimpan_klaim_dilepas(monkeypatch):
    ret, ids = _case()
    _fail_fn(monkeypatch, gl_service, "post_inventory_writeoff")
    with pytest.raises(RuntimeError):
        _dispose(ret, ids)
    monkeypatch.undo()
    assert "supplier" not in (DB.inventory_rolls.find_one({"id": ids[0]}).get("disposition") or {})
    assert _stage(ret, ids[0]) == "supplier_pending"                  # belum ada yang tersimpan → keputusan bebas lagi
    _dispose(ret, ids)
    _assert_done_once(ret, ids)


def test_beberapa_roll_gagal_pada_roll_berikutnya(monkeypatch):
    ret, ids = _case(2)
    _fail_db(monkeypatch, "inventory_movements", "insert_one", nth=2)   # roll pertama tuntas, roll kedua terputus
    with pytest.raises(RuntimeError):
        _dispose(ret, ids)
    monkeypatch.undo()
    assert {_stage(ret, x) for x in ids} == {"supplier_dispose_failed"}
    assert DB.journal_entries.count_documents({"source_type": "inventory_writeoff", "source_id": {"$in": ids}}) == 2
    out = run(rds.decide_supplier(ret, ids, "dispose", "", [], "uji ulang"))
    assert out["writeoff_total"] == 2000
    _assert_done_once(ret, ids)


def test_proses_mati_klaim_kedaluwarsa_bisa_dilanjutkan(monkeypatch):
    ret, ids = _case()
    _fail_db(monkeypatch, "inventory_movements", "insert_one")
    with pytest.raises(RuntimeError):
        _dispose(ret, ids)
    monkeypatch.undo()
    # proses mati (tanpa sempat menandai gagal): klaim tertinggal "processing"
    DB.inventory_rolls.update_one({"id": ids[0]}, {"$set": {"disposition.supplier.status": "processing",
                                                           "disposition.supplier.at": rds.now_iso()}})
    assert _stage(ret, ids[0]) == "closed"                            # masih dalam lease → tidak diambil alih
    with pytest.raises(rds.DispositionError):
        run(rds.decide_supplier(ret, ids, "dispose", "", [], "uji ulang"))
    DB.inventory_rolls.update_one({"id": ids[0]}, {"$set": {"disposition.supplier.at": "2000-01-01T00:00:00+00:00"}})
    assert _stage(ret, ids[0]) == "supplier_dispose_failed"
    run(rds.decide_supplier(ret, ids, "dispose", "", [], "uji ulang"))
    _assert_done_once(ret, ids)


def test_dua_pengguna_bersamaan_sekali_saja():
    ret, ids = _case()

    async def both():
        return await asyncio.gather(*(rds.decide_supplier(ret, ids, "dispose", "BS rusak berat uji", ["att_bukti"], f"u{i}")
                                      for i in range(2)), return_exceptions=True)
    out = run(both())
    assert sum(isinstance(x, dict) for x in out) == 1 and sum(isinstance(x, rds.DispositionError) for x in out) == 1, out
    _assert_done_once(ret, ids)


def test_lanjutkan_hanya_untuk_keputusan_buang():
    ret, ids = _case()
    with pytest.raises(rds.DispositionError):                         # tidak ada yang terhenti → jalur normal, alasan wajib
        run(rds.decide_supplier(ret, ids, "dispose", "", [], "uji"))
    assert _stage(ret, ids[0]) == "supplier_pending"
