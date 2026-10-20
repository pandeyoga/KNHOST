"""AUD-WMS-01 (review 2026-10-19) — stok opname berubah sebelum jurnal berhasil; retry tidak memulihkan sisanya.

Kini tiap baris koreksi memakai catatan operasi bertahap (`roll_count.ops.<kunci>`) + penanda token di roll yang
ditulis atomik bersama perubahan roll. Retry sesudah gangguan di batas mana pun MELANJUTKAN langkah yang tertinggal
(pergerakan, jurnal, saldo agregat) — perubahan milik sendiri dibedakan dari perubahan transaksi lain.

Uji tingkat layanan memakai event loop BERSAMA `tests/_shared_loop.py` (klien Motor modul `db` terikat ke loop pertama);
gangguan disuntikkan dengan monkeypatch. Uji dua pengguna bersamaan juga dijalankan lewat API finalisasi.
Jalankan: cd /app/backend && python -m pytest tests/test_aud_wms_01.py -p no:randomly -n 0 -q
"""
import asyncio
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import gl_service as gl  # noqa: E402
from services import stock_count_roll_service as rcs  # noqa: E402

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
WH, OWNER = "wh_jakarta", "ent_ksc"
TAG = uuid.uuid4().hex[:6]
WH_DOC = DB.warehouses.find_one({"id": WH}, {"_id": 0})
LEVEL = next(z for z in WH_DOC["zones"] if z["id"] == "zone_sim_wh_jkt_w")["racks"][-1]["levels"][0]
B1, B2 = LEVEL["bins"][0], LEVEL["bins"][1]
PROD = DB.products.find_one({"stage": "finished", "status": "active"}, {"_id": 0, "id": 1, "base_unit": 1})
UNIT = PROD.get("base_unit") or "meter"
ROLLS, SESSIONS = [], []


def _roll(qty=100.0, bin_doc=B1):
    rid = f"roll_TEST_W1_{TAG}_{len(ROLLS)}"
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"TW1-{TAG}-{len(ROLLS)}", "product_id": PROD["id"], "warehouse_id": WH,
                                   "owner_entity_id": OWNER, "length_remaining": qty, "length_initial": qty, "unit": UNIT,
                                   "status": "available", "bin_id": bin_doc["id"], "bin_code": bin_doc["code"], "grade": "A",
                                   "unit_cost": 10})
    ROLLS.append(rid)
    return rid


def _session():
    sid = f"ccs_TEST_W1_{TAG}_{len(SESSIONS)}"
    DB.cycle_count_sessions.insert_one({"id": sid, "name": f"TEST_W1 {TAG}", "warehouse_id": WH, "status": "open",
                                        "roll_count": {"scans": [], "expected": []}})
    SESSIONS.append(sid)
    return DB.cycle_count_sessions.find_one({"id": sid}, {"_id": 0})


def _scan(rid, measured=90.0, live=100.0, bin_doc=B1, live_bin=B1):
    return {"id": f"scn_{uuid.uuid4().hex[:6]}", "roll_id": rid, "live_qty": live, "live_bin_id": live_bin["id"],
            "live_warehouse_id": WH, "measured_qty": measured, "bin_id": bin_doc["id"]}


def _ref(sess, rid, kind="roll"):
    return f"{sess['id']}:{kind}:{rid}"


def _counts(sess, rid, kind="roll"):
    ref = _ref(sess, rid, kind)
    return (DB.inventory_movements.count_documents({"source_document": ref}),
            DB.journal_entries.count_documents({"source_type": "cycle_count_variance", "source_id": ref, "status": {"$ne": "void"}}))


def _op(sess, key):
    return ((DB.cycle_count_sessions.find_one({"id": sess["id"]}) or {}).get("roll_count") or {}).get("ops", {}).get(key)


def _once(monkeypatch, obj, name):
    """Gangguan sementara: panggilan pertama gagal, berikutnya normal."""
    orig, state = getattr(obj, name), {"n": 0}

    async def flaky(*a, **kw):
        state["n"] += 1
        if state["n"] == 1:
            raise RuntimeError(f"gangguan {name} (uji AUD-WMS-01)")
        return await orig(*a, **kw)
    monkeypatch.setattr(obj, name, flaky)


def _balance():
    return (DB.inventory_balances.find_one({"product_id": PROD["id"], "warehouse_id": WH, "owner_entity_id": OWNER},
                                           {"_id": 0, "on_hand_qty": 1}) or {}).get("on_hand_qty")


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    rx = "|".join(SESSIONS) or "x^"
    DB.inventory_rolls.delete_many({"id": {"$in": ROLLS}})
    DB.inventory_rolls.delete_many({"acquired_via": "cycle_count_found", "acquired.ref_id": {"$in": SESSIONS}})
    DB.inventory_movements.delete_many({"$or": [{"roll_id": {"$in": ROLLS}}, {"source_document": {"$regex": rx}}]})
    DB.journal_entries.delete_many({"source_type": "cycle_count_variance", "source_id": {"$regex": rx}})
    DB.cycle_count_sessions.delete_many({"id": {"$in": SESSIONS}})
    run(rcs.rebuild_balance(PROD["id"], WH, OWNER))


# ─── Gangguan di tiap batas penulisan sesudah roll berubah → retry melanjutkan ───────────────────────────────
@pytest.mark.parametrize("target", ["_movement", "post_cycle_count_variance", "rebuild_balance"])
def test_gangguan_sesudah_roll_berubah_dilanjutkan_retry(monkeypatch, target):
    sess, rid = _session(), _roll()
    run(rcs.rebuild_balance(PROD["id"], WH, OWNER))
    before = _balance()
    scan = _scan(rid)
    _once(monkeypatch, gl if target == "post_cycle_count_variance" else rcs, target)
    with pytest.raises(RuntimeError):
        run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))
    roll = DB.inventory_rolls.find_one({"id": rid})
    assert roll["length_remaining"] == 90                       # perubahan roll sudah tersimpan
    op = _op(sess, f"scan_{rid}")
    assert op["status"] == "pending" and roll["count_op"] == op["token"]
    res = run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))  # retry: BUKAN recount
    assert res["status"] == "applied" and res["qty_diff"] == -10 and res["value"] == -100 and res["journal_id"], res
    assert _counts(sess, rid) == (1, 1)
    je = DB.journal_entries.find_one({"source_id": _ref(sess, rid)})
    assert round(sum(ln["debit"] for ln in je["lines"]), 2) == 100
    roll = DB.inventory_rolls.find_one({"id": rid})
    assert roll["length_remaining"] == 90 and "count_op" not in roll
    assert _op(sess, f"scan_{rid}")["status"] == "done"
    after = _balance()
    run(rcs.rebuild_balance(PROD["id"], WH, OWNER))
    assert after == _balance() and after != before             # saldo agregat sudah konsisten tanpa rebuild manual
    assert run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))["journal_id"] == res["journal_id"]   # ulang lagi = sama
    assert _counts(sess, rid) == (1, 1)


def test_gangguan_sebelum_roll_berubah_retry_menjalankan_cas_yang_sama(monkeypatch):
    sess, rid = _session(), _roll()
    scan = _scan(rid)
    _once(monkeypatch, rcs, "_cas_op")                      # catatan operasi sudah ada, roll belum berubah
    with pytest.raises(RuntimeError):
        run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))
    assert DB.inventory_rolls.find_one({"id": rid})["length_remaining"] == 100 and _counts(sess, rid) == (0, 0)
    res = run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))
    assert res["status"] == "applied" and res["journal_id"]
    assert _counts(sess, rid) == (1, 1) and DB.inventory_rolls.find_one({"id": rid})["length_remaining"] == 90


def test_proses_mati_lease_aktif_ditunda_lalu_diambil_alih_setelah_kedaluwarsa(monkeypatch):
    sess, rid = _session(), _roll()
    scan = _scan(rid)
    _once(monkeypatch, gl, "post_cycle_count_variance")
    with pytest.raises(RuntimeError):
        run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))
    path = f"roll_count.ops.scan_{rid}.lease"
    DB.cycle_count_sessions.update_one({"id": sess["id"]}, {"$set": {path: {"id": "lse_mati", "at": rcs.now_iso()}}})
    busy = run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))   # proses lain (mati) masih memegang lease
    assert busy["status"] == "recount" and "sedang diproses" in busy["message"] and _counts(sess, rid) == (1, 0)
    DB.cycle_count_sessions.update_one({"id": sess["id"]}, {"$set": {f"{path}.at": "2000-01-01T00:00:00+00:00"}})
    res = run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))
    assert res["status"] == "applied" and res["journal_id"] and _counts(sess, rid) == (1, 1)


def test_selesai_tetapi_penanda_tertinggal_dibersihkan():
    sess, rid = _session(), _roll()
    scan = _scan(rid)
    res = run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))
    tok = _op(sess, f"scan_{rid}")["token"]
    DB.inventory_rolls.update_one({"id": rid}, {"$set": {"count_op": tok}})     # proses mati sesudah tandai selesai
    assert run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji")) == res
    assert "count_op" not in DB.inventory_rolls.find_one({"id": rid}) and _counts(sess, rid) == (1, 1)


# ─── Perubahan milik sendiri vs transaksi lain ─────────────────────────────────────────────────────────────────
def test_transaksi_lain_sesudah_gangguan_tidak_menghapus_selisih_yang_belum_diposting(monkeypatch):
    sess, rid = _session(), _roll()
    scan = _scan(rid)
    _once(monkeypatch, gl, "post_cycle_count_variance")
    with pytest.raises(RuntimeError):
        run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))
    DB.inventory_rolls.update_one({"id": rid}, {"$inc": {"length_remaining": -5}})   # pengambilan lain sesudahnya
    res = run(rcs.apply_scan(sess, scan, ["qty_diff"], "uji"))
    assert res["status"] == "applied" and res["value"] == -100
    assert _counts(sess, rid) == (1, 1) and DB.inventory_rolls.find_one({"id": rid})["length_remaining"] == 85


def test_transaksi_lain_sebelum_finalisasi_tetap_recount():
    sess, rid = _session(), _roll()
    DB.inventory_rolls.update_one({"id": rid}, {"$set": {"length_remaining": 95}})
    res = run(rcs.apply_scan(sess, _scan(rid), ["qty_diff"], "uji"))
    assert res["status"] == "recount"
    assert _counts(sess, rid) == (0, 0) and _op(sess, f"scan_{rid}") is None


def test_dua_pemroses_bersamaan_satu_perubahan():
    sess, rid = _session(), _roll()
    scan = _scan(rid)

    async def both():
        return await asyncio.gather(*(rcs.apply_scan(sess, scan, ["qty_diff"], f"u{i}") for i in range(2)),
                                    return_exceptions=True)
    out = run(both())
    assert sorted(x["status"] for x in out) == ["applied", "recount"], out
    assert _counts(sess, rid) == (1, 1) and DB.inventory_rolls.find_one({"id": rid})["length_remaining"] == 90


def test_salah_alamat_dan_qty_gangguan_jurnal_satu_relokasi(monkeypatch):
    sess, rid = _session(), _roll()
    scan = _scan(rid, bin_doc=B2)
    _once(monkeypatch, gl, "post_cycle_count_variance")
    with pytest.raises(RuntimeError):
        run(rcs.apply_scan(sess, scan, ["qty_diff", "wrong_address"], "uji"))
    res = run(rcs.apply_scan(sess, scan, ["qty_diff", "wrong_address"], "uji"))
    assert res["relocated"] == {"from": B1["id"], "to": B2["id"]} and res["journal_id"]
    types = sorted(m["movement_type"] for m in DB.inventory_movements.find({"source_document": _ref(sess, rid)}))
    assert types == ["cycle_count_adjustment", "cycle_count_relocation"]
    assert DB.inventory_rolls.find_one({"id": rid})["bin_id"] == B2["id"]


# ─── Roll hilang & roll ditemukan memakai jalur yang sama ─────────────────────────────────────────────────────
def test_hapus_roll_hilang_gangguan_jurnal_dilanjutkan(monkeypatch):
    sess, rid = _session(), _roll(40)
    e = {"roll_id": rid, "bin_id": B1["id"], "qty": 40}
    _once(monkeypatch, gl, "post_cycle_count_variance")
    with pytest.raises(RuntimeError):
        run(rcs.write_off_missing(sess, e, "uji"))
    assert DB.inventory_rolls.find_one({"id": rid})["status"] == "consumed"
    res = run(rcs.write_off_missing(sess, e, "uji"))
    assert res["status"] == "applied" and res["value"] == -400 and res["journal_id"]
    assert _counts(sess, rid, "missing") == (1, 1)
    assert run(rcs.write_off_missing(sess, e, "uji"))["journal_id"] == res["journal_id"]


def test_roll_ditemukan_gangguan_jurnal_tidak_membuat_roll_kedua(monkeypatch):
    sess = _session()
    scan = {"id": f"scn_{TAG}_f", "code": f"ASING-{TAG}", "bin_id": B1["id"], "measured_qty": 12}
    spec = {"product_id": PROD["id"], "owner_entity_id": OWNER, "qty": 12}
    _once(monkeypatch, gl, "post_cycle_count_variance")
    with pytest.raises(RuntimeError):
        run(rcs.create_found_roll(sess, scan, spec, "uji", "uji biaya nol"))
    res = run(rcs.create_found_roll(sess, scan, spec, "uji", "uji biaya nol"))
    assert res["status"] == "applied"
    assert DB.inventory_rolls.count_documents({"acquired.via": "cycle_count_found", "acquired.ref_id": sess["id"]}) == 1
    src = f"{sess['id']}:found:{scan['id']}"
    assert DB.journal_entries.count_documents({"source_id": src, "status": {"$ne": "void"}}) == (1 if res["value"] else 0)


# ─── Dua pengguna menekan finalisasi bersamaan (API) ───────────────────────────────────────────────────────────
def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": OWNER}


def test_finalisasi_bersamaan_lewat_api_sekali_saja():
    adm = _login("admin@kainnusantara.id", "demo12345")
    rid = _roll(50)
    s = requests.post(f"{BASE}/cycle-count/sessions", json={"warehouse_id": WH, "name": f"TEST_W1 api {TAG}"}, headers=adm).json()
    SESSIONS.append(s["id"])
    assert requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scope", json={"node_id": LEVEL["id"]},
                         headers=adm).status_code == 200
    r = requests.post(f"{BASE}/cycle-count/sessions/{s['id']}/roll-scans",
                      json={"code": rid, "bin_id": B1["id"], "measured_qty": 44, "tag": "ok"}, headers=adm)
    assert "qty_diff" in r.json()["scan"]["kinds"], r.text
    url = f"{BASE}/cycle-count/sessions/{s['id']}/roll-finalize"
    with ThreadPoolExecutor(2) as ex:
        rs = [f.result() for f in [ex.submit(requests.post, url, json={"reason": f"bersamaan {TAG}"}, headers=adm)
                                   for _ in range(2)]]
    codes = sorted(x.status_code for x in rs)
    assert codes[0] == 200 and codes[1] in (400, 409), [x.text[:200] for x in rs]
    assert DB.inventory_rolls.find_one({"id": rid})["length_remaining"] == 44
    sess = {"id": s["id"]}
    assert _counts(sess, rid) == (1, 1)
