"""FIX-10 (audit 9 Nov 2026 — B3a SSOT-1; B2a §5/§6/§9) — satu penulis status roll + tabel transisi PA/SPK/opname.

Semua uji GAGAL di kode sebelum FIX-10 (modul `roll_state`, `putaway_state`, `inspection_state`, `cycle_count_state`
belum ada; `status_history` roll/PA/SPK/sesi opname tidak pernah ditulis; `allocated` ada di daftar status roll) dan
LULUS sesudahnya.

Cakupan:
  A. `roll_state` — daftar-izin (ilegal ditolak SEBELUM tulisan), CAS (status asal wajib cocok; paralel hanya satu
     menang), jejak `status_history` (asal/tujuan/pelaku/alasan/rujukan, dibatasi), saldo segmen dibangun ulang (termasuk
     pindah gudang), mode pipeline, kelahiran roll anak (status dikenal, jejak induk tidak diwarisi);
  B. penulis yang dimigrasi (tahan/lepas QC-06, ember tahan, reservasi roll pilihan + pelepasan per dokumen yang TIDAK
     melepas roll di Surat Jalan);
  C. Putaway Order — terbit → kirim → trip → tutup sisa: riwayat status PA & roll; batal draf (pembalikan jelas, klaim
     roll tidak ada); `finish_claimed` menolak status berubah di luar klaim; tabel menolak transisi ilegal;
  D. SPK inspeksi — mulai menulis riwayat; tulisan basi (status berubah) ditolak; transisi ilegal ditolak; dua "mulai"
     bersamaan hanya satu menang;
  E. sesi opname — kirim/tolak/buka kembali lewat API menulis riwayat; aksi opname tidak menyentuh sesi pendaftaran
     awal; dua "kirim" bersamaan hanya satu menang; opname RFID ber-riwayat;
  F. kosakata — registry (`ENTITY_REGISTRY.md`) & label FE (`statusVocab.js`) selaras `roll_state.STATUSES`; `allocated`
     keluar dari daftar status roll (`loading_check_service`, `rfid_service`);
  G. guardrail INV-ROLL-02 — merah untuk penulis baru, hijau di repo.

Jalankan (kontainer backend, DB uji, server :8001 hidup untuk bagian C/E):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix10_roll_state.py
"""
import asyncio
import os
import re
import subprocess
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import roll_service  # noqa: E402
from services import roll_state as rs  # noqa: E402

DB_NAME = os.environ.get("DB_NAME", "test_database")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[DB_NAME]
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/") + "/api"
PWD = "demo12345"
TAG = uuid.uuid4().hex[:8]
ENT = f"ent_TEST_FIX10_{TAG}"
WH_A, WH_B, WH_C = (f"wh_TEST_FIX10_{TAG}_{k}" for k in ("a", "b", "c"))
P = f"prod_TEST_FIX10_{TAG}"
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_N = {"n": 0}


def _nx() -> int:
    _N["n"] += 1
    return _N["n"]


@pytest.fixture(scope="module", autouse=True)
def seed():
    DB.business_entities.insert_one({"id": ENT, "short_name": f"UJI10-{TAG}", "code": f"T{TAG[:4].upper()}",
                                     "legal_name": "PT Uji FIX-10"})
    DB.warehouses.insert_many([
        {"id": WH_A, "name": f"Gudang A {TAG}", "code": f"FA{TAG[:4]}", "roles": ["storage"],
         "sharing_mode": "shared", "active": True},
        {"id": WH_B, "name": f"Gudang B {TAG}", "code": f"FB{TAG[:4]}", "roles": ["storage"],
         "sharing_mode": "shared", "active": True},
        {"id": WH_C, "name": f"Gudang C {TAG}", "code": f"FC{TAG[:4]}", "roles": ["storage"],
         "sharing_mode": "shared", "active": True}])
    DB.products.insert_one({"id": P, "sku": f"FIX10-{TAG}", "name": "Kain Uji FIX-10", "harga_pokok": 0,
                            "status": "active", "stage": "finished", "fabric_type": "woven", "base_unit": "yard"})
    yield
    rns = [r["roll_no"] for r in DB.inventory_rolls.find({"owner_entity_id": ENT}, {"roll_no": 1}) if r.get("roll_no")]
    DB.number_sequences.delete_many({"doc_type": {"$in": [f"ROLL_CHILD:{rn}" for rn in rns]}})
    for coll in ("inventory_rolls", "inventory_lots", "inventory_movements", "inventory_balances"):
        DB[coll].delete_many({"owner_entity_id": ENT})
    for coll in ("inspections", "cycle_count_sessions", "inventory_lots", "number_sequences", "audit_logs"):
        DB[coll].delete_many({"entity_id": ENT})
    DB.inspections.delete_many({"id": {"$regex": f"TEST_FIX10_{TAG}"}})
    DB.cycle_count_sessions.delete_many({"id": {"$regex": f"TEST_FIX10_{TAG}"}})
    DB.rfid_verify_sessions.delete_many({"id": {"$regex": f"TEST_FIX10_{TAG}"}})
    DB.products.delete_many({"id": P})
    DB.warehouses.delete_many({"id": {"$in": [WH_A, WH_B, WH_C]}})
    DB.business_entities.delete_many({"id": ENT})


def _roll(qty=50.0, wh=WH_A, status="available", **extra):
    r = run(roll_service.create_inbound_roll(P, wh, ENT, qty, lot=f"LOT-{TAG}-{_nx()}", unit="yard",
                                             unit_cost=1000.0, created_by="uji", status=status))
    if extra:
        DB.inventory_rolls.update_one({"id": r["id"]}, {"$set": extra})
    run(roll_service.rebuild_balance(P, wh, ENT))
    return DB.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0})


def _get(rid):
    return DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})


def _bal(wh=WH_A):
    return DB.inventory_balances.find_one({"product_id": P, "warehouse_id": wh, "owner_entity_id": ENT}, {"_id": 0}) or {}


# ═══ A. roll_state ═════════════════════════════════════════════════════════════════════════════════════════════
def test_illegal_transition_rejected_before_any_write():
    r = _roll(status="available")
    DB.inventory_rolls.update_one({"id": r["id"]}, {"$set": {"status": "delivered"}})
    with pytest.raises(rs.IllegalRollTransition):
        run(rs.transition(r["id"], "available", from_="delivered", reason="uji ilegal", actor="Penguji"))
    after = _get(r["id"])
    assert after["status"] == "delivered" and not after.get("status_history")
    # in_transit_sales → available dilarang (FIX-3b STM-OUT-1): roll di SJ tidak pernah "dilepas"
    assert not rs.allowed("in_transit_sales", "available")
    assert not rs.allowed("consumed", "reserved") and not rs.allowed("delivered", "available")
    # kosakata: status tak dikenal (mis. `allocated`, kode lama registry) tidak bisa menjadi tujuan
    for bad in ("allocated", "sold", "scrapped", "returned"):
        with pytest.raises(rs.IllegalRollTransition):
            rs.assert_known(bad)


def test_transition_requires_from_reason_and_no_status_in_filter():
    r = _roll()
    with pytest.raises(rs.IllegalRollTransition):
        run(rs.transition(r["id"], "hold", from_=[], reason="uji"))
    with pytest.raises(rs.IllegalRollTransition):
        run(rs.transition(r["id"], "hold", from_="available", reason="  "))
    with pytest.raises(rs.IllegalRollTransition):
        run(rs.transition(r["id"], "hold", from_="available", reason="uji", extra_filter={"status": "available"}))
    assert _get(r["id"])["status"] == "available"


def test_cas_from_mismatch_writes_nothing():
    r = _roll()
    n = run(rs.transition(r["id"], "available", from_="reserved", reason="lepas uji", actor="Penguji"))
    assert n == 0
    assert _get(r["id"])["status"] == "available" and not _get(r["id"]).get("status_history")
    # extra_filter ikut CAS: reservasi milik dokumen lain → tidak ditulis
    run(rs.transition(r["id"], "reserved", from_="available", reason="pesan uji", extra_set={"reserved_ref": {"id": "A"}}))
    n = run(rs.transition(r["id"], "available", from_="reserved", reason="lepas uji", extra_filter={"reserved_ref.id": "B"}))
    assert n == 0 and _get(r["id"])["status"] == "reserved"


def test_parallel_transitions_only_one_wins():
    r = _roll()

    async def race():
        return await asyncio.gather(*[rs.transition(
            r["id"], "reserved", from_="available", reason=f"pesan paralel {i}", actor=f"P{i}",
            ref={"type": "sales_order", "id": f"so_{i}"}, extra_set={"reserved_ref": {"type": "sales_order", "id": f"so_{i}"}},
            rebuild=False) for i in range(6)])

    res = run(race())
    assert sorted(res) == [0, 0, 0, 0, 0, 1]
    doc = _get(r["id"])
    hist = [h for h in doc.get("status_history") or [] if h["status"] == "reserved"]
    assert len(hist) == 1 and doc["reserved_ref"]["id"] == hist[0]["ref_id"]


def test_status_history_entry_shape_and_bound():
    r = _roll()
    run(rs.transition(r["id"], "hold", from_="available", reason="tahan pesanan pelanggan", actor="Admin Uji",
                      action="hold", ref={"type": "hold", "id": "hold_1", "number": "HLD-1"}))
    e = _get(r["id"])["status_history"][-1]
    assert e["status"] == "hold" and e["from"] == "available" and e["user"] == "Admin Uji"
    assert e["note"] == "tahan pesanan pelanggan" and e["action"] == "hold" and e["timestamp"]
    assert e["ref_type"] == "hold" and e["ref_id"] == "hold_1" and e["ref_no"] == "HLD-1"
    for i in range(rs.HISTORY_MAX + 6):   # bolak-balik → riwayat dibatasi HISTORY_MAX entri terakhir
        a, b = ("hold", "available") if i % 2 == 0 else ("available", "hold")
        run(rs.transition(r["id"], b, from_=a, reason=f"bolak {i}", rebuild=False))
    hist = _get(r["id"])["status_history"]
    assert len(hist) == rs.HISTORY_MAX and hist[-1]["note"] == f"bolak {rs.HISTORY_MAX + 5}"
    # status tidak berubah (frm == to) → tidak ada entri baru
    n0 = len(_get(r["id"])["status_history"])
    cur = _get(r["id"])["status"]
    assert run(rs.transition(r["id"], cur, from_=cur, reason="tanpa ubah status", extra_set={"x_uji": 1})) == 1
    assert len(_get(r["id"])["status_history"]) == n0 and _get(r["id"])["x_uji"] == 1


def test_balance_rebuilt_for_affected_segments_including_move():
    r = _roll(40.0)
    assert _bal()["available_qty"] >= 40.0
    before = _bal()["available_qty"]
    run(rs.transition(r["id"], "hold", from_="available", reason="tahan uji saldo"))
    b = _bal()
    assert round(b["available_qty"], 2) == round(before - 40.0, 2) and b["hold_qty"] >= 40.0
    # pindah gudang di tulisan yang sama → saldo gudang lama & baru dibangun ulang
    run(rs.transition(r["id"], "available", from_="hold", reason="pindah uji", extra_set={"warehouse_id": WH_B}))
    assert round(_bal(WH_A)["hold_qty"], 2) == round(b["hold_qty"] - 40.0, 2)
    assert _bal(WH_B)["available_qty"] >= 40.0


def test_pipeline_mode_and_return_doc():
    r = _roll(30.0)
    doc = run(rs.transition(r["id"], "consumed", from_="available", reason="habis dipakai uji", return_doc=True,
                            pipeline=[{"$set": {"length_remaining": {"$round": [{"$subtract": ["$length_remaining", 30]}, 2]}}}]))
    assert doc["status"] == "consumed" and doc["length_remaining"] == 0
    assert doc["status_history"][-1]["from"] == "available"
    with pytest.raises(rs.IllegalRollTransition):
        run(rs.transition(r["id"], "available", from_="consumed", reason="x", pipeline=[], unset=["a"]))


def test_child_roll_birth_known_status_and_fresh_history():
    parent = _roll(60.0)
    run(rs.transition(parent["id"], "hold", from_="available", reason="riwayat induk", rebuild=False))
    run(rs.transition(parent["id"], "available", from_="hold", reason="riwayat induk 2", rebuild=False))
    parent = _get(parent["id"])
    child = run(roll_service.insert_child_roll({**parent, "id": f"roll_c_{TAG}_{_nx()}", "status": "reserved",
                                                "length_initial": 5, "length_remaining": 5}, parent))
    got = _get(child["id"])
    assert [h["status"] for h in got["status_history"]] == ["reserved"]
    assert "potongan dari roll" in got["status_history"][0]["note"]
    with pytest.raises(rs.IllegalRollTransition):
        run(roll_service.insert_child_roll({**parent, "id": f"roll_c_{TAG}_{_nx()}", "status": "allocated"}, parent))


# ═══ B. penulis yang dimigrasi ═════════════════════════════════════════════════════════════════════════════════
def test_hold_release_qc06_write_history_once():
    from services import roll_hold_service as rh
    r = _roll(20.0)
    run(rh.hold_roll(r, "cacat noda terlihat", {"name": "QC Uji", "id": "u1"}))
    held = _get(r["id"])
    assert held["status"] == "blocked" and held["hold"]["prev_status"] == "available"
    run(rh.release_roll(held, "sudah dibersihkan, aman", {"name": "QC Uji", "id": "u1"}))
    doc = _get(r["id"])
    assert doc["status"] == "available"
    assert [(h["from"], h["status"]) for h in doc["status_history"]] == [("available", "blocked"), ("blocked", "available")]
    assert len(doc["hold_history"]) == 2   # jejak tahan domain tetap (alasan), bukan duplikat jejak status
    with pytest.raises(ValueError):        # tahan dari status di luar tabel (mis. terkirim) tetap ditolak
        run(rh.hold_roll({**doc, "status": "delivered"}, "uji tolak tahan", {"name": "QC Uji"}))


def test_bucket_hold_and_release_history():
    from services import stock_bucket_service as sb
    r = _roll(15.0, wh=WH_C)   # gudang khusus: FEFO tidak memilih roll uji lain
    res = run(sb.hold_stock({"product_id": P, "warehouse_id": WH_C, "owner_entity_id": ENT, "quantity": 15.0,
                             "reason": "tahan SO pending"}, "Admin Uji"))
    assert _get(r["id"])["status"] == "hold"
    run(sb.release_hold(res["hold_id"]))
    doc = _get(r["id"])
    assert doc["status"] == "available"
    assert [h["status"] for h in doc["status_history"]][-2:] == ["hold", "available"]


def test_release_by_ref_never_releases_shipped_roll():
    shipped = _roll(10.0)
    held = _roll(12.0)
    ref = f"xfer_TEST_FIX10_{TAG}"
    run(roll_service.reserve_specific_rolls([{"roll_id": held["id"], "take_qty": 0}], {"type": "transfer", "id": ref}))
    DB.inventory_rolls.update_one({"id": shipped["id"]}, {"$set": {"status": "in_transit_sales",
                                                                  "reserved_ref": {"type": "transfer", "id": ref}}})
    released = run(roll_service._release_rolls_by_ref_id(ref))
    assert released == 12.0
    assert _get(held["id"])["status"] == "available" and _get(shipped["id"])["status"] == "in_transit_sales"
    hist = _get(held["id"])["status_history"]
    assert [(h["from"], h["status"]) for h in hist][-2:] == [("available", "reserved"), ("reserved", "available")]


# ═══ C. Putaway Order (HTTP, data acuan Rancamalang) ═══════════════════════════════════════════════════════════
def _login(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": PWD}, timeout=60)
    assert r.status_code == 200, r.text[:300]
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"})
    return s


@pytest.fixture(scope="module")
def admin():
    try:
        return _login("admin@kainnusantara.id")
    except requests.RequestException:
        pytest.skip("server :8001 tidak hidup")


@pytest.fixture(scope="module")
def ref_env():
    from poc_stock_guard import purge_new_ids, restore_stock, snapshot_new_ids, snapshot_stock
    stock = snapshot_stock(["inventory_balances", "number_sequences"])
    if not stock.get("__enabled__"):
        pytest.skip("restore tidak aktif (bukan DB uji)")
    ids = snapshot_new_ids(["inventory_rolls", "inventory_movements", "putaway_orders", "audit_logs", "notifications",
                            "cycle_count_sessions", "rfid_verify_sessions", "rfid_cycle_counts", "inventory_lots"])
    yield
    purge_new_ids(ids, verbose=False)
    restore_stock(stock)


@pytest.fixture(scope="module")
def W(ref_env):
    tr = DB.warehouses.find_one({"code": "RCM-TRANSIT"}, {"_id": 0})
    if not tr:
        pytest.skip("data acuan tidak punya RCM-TRANSIT")
    by = {w["code"]: w for w in DB.warehouses.find({"site_id": tr["site_id"]}, {"_id": 0})}
    return {"transit": tr, "storage": [w for c, w in sorted(by.items())
                                       if "storage" in (w.get("roles") or []) and c != "RCM-RETUR"]}


def _seed_transit(W, n):
    src = list(DB.inventory_rolls.find({"warehouse_id": {"$in": [w["id"] for w in W["storage"]]}, "status": "available",
                                        "owner_entity_id": "ent_ksc", "grade": {"$in": ["A", None, ""]},
                                        "length_remaining": {"$gt": 1}, "length_reserved": {"$in": [0, None]}},
                                       {"_id": 0}).limit(8))
    if not src:
        pytest.skip("tidak ada roll sumber")
    out = []
    for i in range(n):
        k = _nx()
        r = dict(src[k % len(src)])
        for x in ("inspection", "hold", "qc_hold_pending", "four_point_pending", "last_pa_landed", "transfer_ref",
                  "status_history"):
            r.pop(x, None)
        r.update({"id": f"roll_TEST_FIX10_{TAG}_{k}", "roll_no": f"TF10{TAG.upper()}{k}", "warehouse_id": W["transit"]["id"],
                  "status": "available", "bin_id": None, "rfid_tag_id": None, "active_movement": None, "grade": "A",
                  "journey": {"stage": "received_transit", "routing": "store"}, "length_reserved": 0,
                  "length_reservations": [], "earmarked_for": None, "reserved_ref": None, "qc_task_id": None})
        DB.inventory_rolls.insert_one(dict(r))
        out.append(r)
    return out


def _open_pa(admin, W, n, dispatch=True):
    rolls = _seed_transit(W, n)
    r = admin.post(f"{BASE}/putaway-orders/verify-labels", json={"warehouse_id": W["transit"]["id"],
                                                                 "codes": [x["roll_no"] for x in rolls]}, timeout=60)
    assert r.status_code == 200 and len(r.json()["verified"]) == n, r.text
    r = admin.post(f"{BASE}/putaway-orders", json={"from_warehouse_id": W["transit"]["id"],
                                                   "to_warehouse_id": W["storage"][0]["id"],
                                                   "roll_ids": [x["id"] for x in rolls]}, timeout=60)
    assert r.status_code == 200, r.text
    pa = r.json()
    if dispatch:
        assert admin.post(f"{BASE}/putaway-orders/{pa['id']}/dispatch", timeout=60).status_code == 200
    return pa, rolls


def test_putaway_flow_status_history_pa_and_rolls(admin, W):
    pa, rolls = _open_pa(admin, W, 2)
    url = f"{BASE}/putaway-orders/{pa['id']}"
    r = admin.post(f"{url}/arrival-trips", json={"epcs": [rolls[0]["roll_no"]], "client_trip_id": f"T{TAG}"}, timeout=60)
    assert r.status_code == 200, r.text
    r = admin.post(f"{url}/close", json={"action": "return_transit", "reason": "roll kedua tertinggal di transit"},
                   timeout=60)
    assert r.status_code == 200 and r.json()["status"] == "completed", r.text
    doc = DB.putaway_orders.find_one({"id": pa["id"]}, {"_id": 0})
    assert [(h.get("from", ""), h["status"]) for h in doc["status_history"]] == [
        ("", "open"), ("open", "in_transit"), ("in_transit", "partially_received"), ("partially_received", "completed")]
    assert all(h.get("timestamp") and "user" in h for h in doc["status_history"])
    r0, r1 = _get(rolls[0]["id"]), _get(rolls[1]["id"])
    assert [(h["from"], h["status"]) for h in r0["status_history"]] == [("available", "in_transit_transfer"),
                                                                       ("in_transit_transfer", "available")]
    assert r0["status_history"][-1]["ref_type"] == "putaway_order" and r0["warehouse_id"] == W["storage"][0]["id"]
    assert r1["status"] == "available" and r1["warehouse_id"] == W["transit"]["id"] and not r1.get("active_movement")
    assert r1["status_history"][-1]["action"] == "putaway_return_transit"


def test_putaway_draft_cancel_reverses_cleanly(admin, W):
    from services import inbound_qc_common as iqc
    rolls = _seed_transit(W, 1)
    admin.post(f"{BASE}/putaway-orders/verify-labels", json={"warehouse_id": W["transit"]["id"],
                                                             "codes": [rolls[0]["roll_no"]]}, timeout=60)
    run(iqc.auto_draft_after_release([rolls[0]["id"]], {"type": "test", "id": f"fix10-{TAG}"}, "Penguji"))
    d = DB.putaway_orders.find_one({"status": "draft", "items.roll_id": rolls[0]["id"]}, {"_id": 0})
    if not d:
        pytest.skip("draf otomatis tidak aktif di data acuan")
    assert d["status_history"][0]["status"] == "draft" and d["status_history"][0]["action"] == "create_draft"
    r = admin.post(f"{BASE}/putaway-orders/{d['id']}/cancel-draft", json={"reason": "salah tujuan, buat ulang"}, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "cancelled", r.text
    doc = DB.putaway_orders.find_one({"id": d["id"]}, {"_id": 0})
    assert doc["status_history"][-1]["from"] == "draft" and doc["status_history"][-1]["status"] == "cancelled"
    assert doc["status_history"][-1]["note"] == "salah tujuan, buat ulang"
    roll = _get(rolls[0]["id"])
    assert roll["status"] == "available" and not roll.get("active_movement")   # draf tidak pernah mengklaim roll
    assert admin.post(f"{BASE}/putaway-orders/{d['id']}/publish", json={}, timeout=30).status_code == 400


def test_putaway_table_and_finish_claimed_cas():
    from fastapi import HTTPException
    from services import putaway_state as pst
    assert pst.allowed("dispatch", "open", "in_transit") and not pst.allowed("dispatch", "in_transit", "in_transit")
    for action, frm, to in (("dispatch", "draft", "in_transit"), ("publish", "open", "open"),
                            ("cancel_draft", "open", "cancelled"), ("arrival_trip", "completed", "completed"),
                            ("close_remaining", "in_transit", "draft"), ("resolve_exception", "draft", "completed")):
        with pytest.raises(ValueError):
            pst.check(action, frm, to)
    oid = f"pa_TEST_FIX10_{TAG}_{_nx()}"
    DB.putaway_orders.insert_one({"id": oid, "status": "open", "owner_entity_id": ENT, "items": [],
                                  "saga_lock": {"action": "uji", "token": "t"}})
    DB.putaway_orders.update_one({"id": oid}, {"$set": {"status": "in_transit"}})   # berubah di luar klaim
    with pytest.raises(HTTPException) as e:
        run(pst.finish_claimed(oid, "open", "dispatch", {"$set": {"status": "in_transit"}, "$unset": {"saga_lock": ""}}))
    assert e.value.status_code == 409
    doc = DB.putaway_orders.find_one({"id": oid})
    assert doc.get("saga_lock", {}).get("failed_at") and not doc.get("status_history")
    DB.putaway_orders.delete_many({"id": oid})


# ═══ D. SPK inspeksi ═══════════════════════════════════════════════════════════════════════════════════════════
def _ins(status="assigned", **extra):
    iid = f"ins_TEST_FIX10_{TAG}_{_nx()}"
    DB.inspections.insert_one({"id": iid, "number": f"INS-T10-{TAG}-{_N['n']}", "entity_id": ENT, "kind": "po_receipt",
                               "status": status, "assigned_to": "u1", "assigned_name": "Petugas Uji", "lines": [],
                               "history": [], "started_at": "", **extra})
    return DB.inspections.find_one({"id": iid}, {"_id": 0})


def test_inspection_start_writes_status_history():
    from services import inspection_service as ins
    doc = _ins("assigned")
    out = run(ins.start(doc["id"], {"name": "Petugas Uji"}))
    assert out["status"] == "in_progress"
    h = DB.inspections.find_one({"id": doc["id"]})["status_history"]
    assert len(h) == 1 and h[0]["from"] == "assigned" and h[0]["status"] == "in_progress" and h[0]["action"] == "start"


def test_inspection_stale_save_rejected():
    from services import inspection_service as ins
    doc = _ins("assigned")
    DB.inspections.update_one({"id": doc["id"]}, {"$set": {"status": "closed"}})   # ditutup orang lain
    with pytest.raises(ins.InspectionError):
        run(ins._save(doc, "started", "Pemeriksaan dimulai", {"name": "Petugas Uji"}, status="in_progress"))
    after = DB.inspections.find_one({"id": doc["id"]})
    assert after["status"] == "closed" and not after.get("status_history")


def test_inspection_illegal_transition_rejected():
    from services import inspection_service as ins
    from services import inspection_state as ist
    doc = _ins("draft")
    with pytest.raises(ins.InspectionError):   # draf → selesai tanpa ditugaskan/diperiksa
        run(ins._save(doc, "finished", "Keputusan", {"name": "Petugas Uji"}, status="done"))
    assert DB.inspections.find_one({"id": doc["id"]})["status"] == "draft"
    assert not ist.allowed("reopen", "in_progress", "in_progress") and not ist.allowed("finish", "closed", "done")
    assert ist.allowed("close_unneeded", "draft", "closed") and not ist.allowed("close_unneeded", "done", "closed")


def test_inspection_parallel_start_one_winner():
    from services import inspection_service as ins
    doc = _ins("assigned")

    async def race():
        return await asyncio.gather(*[ins._save(doc, "started", "mulai", {"name": f"P{i}"}, status="in_progress")
                                      for i in range(4)], return_exceptions=True)

    res = run(race())
    ok = [x for x in res if isinstance(x, dict)]
    assert len(ok) >= 1 and all(isinstance(x, (dict, ins.InspectionError)) for x in res)
    h = [e for e in DB.inspections.find_one({"id": doc["id"]}).get("status_history") or [] if e["status"] == "in_progress"]
    # CAS daftar-izin `start` (draft/assigned): sesudah pemenang menulis in_progress, sisanya ditolak
    assert len(h) == 1 and len(ok) == 1


# ═══ E. sesi opname ════════════════════════════════════════════════════════════════════════════════════════════
def _cc(status="open", mode="", **extra):
    sid = f"cc_TEST_FIX10_{TAG}_{_nx()}"
    wh = DB.warehouses.find_one({"code": "RCM-TRANSIT"}, {"_id": 0, "id": 1, "name": 1}) or {"id": WH_A, "name": "A"}
    DB.cycle_count_sessions.insert_one({"id": sid, "entity_id": "ent_ksc", "warehouse_id": wh["id"],
                                        "warehouse_name": wh.get("name", ""), "name": f"Opname uji {TAG}",
                                        "status": status, "items": [], **({"mode": mode} if mode else {}), **extra})
    return sid


def test_cycle_count_submit_reject_reopen_history(admin, ref_env):
    sid = _cc("open")
    r = admin.post(f"{BASE}/cycle-count/sessions/{sid}/submit", timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "submitted", r.text
    r = admin.post(f"{BASE}/cycle-count/sessions/{sid}/reject", json={"reason": "hitungan rak A meragukan"}, timeout=30)
    assert r.status_code == 200 and r.json()["status"] == "rejected", r.text
    r = admin.post(f"{BASE}/cycle-count/sessions/{sid}/reopen", timeout=60)
    assert r.status_code == 200 and r.json()["status"] == "open", r.text
    h = DB.cycle_count_sessions.find_one({"id": sid})["status_history"]
    assert [(e["from"], e["status"], e["action"]) for e in h] == [
        ("open", "submitted", "submit"), ("submitted", "rejected", "reject"), ("rejected", "open", "reopen")]
    assert h[1]["note"] == "hitungan rak A meragukan"
    # pembalikan jelas: tolak → buka kembali tidak mengubah stok (selisih baru diterapkan saat disetujui)
    assert admin.post(f"{BASE}/cycle-count/sessions/{sid}/approve", json={"reason": "uji tanpa submit"},
                      timeout=30).status_code == 400


def test_cycle_count_actions_never_touch_registration_session():
    from services import cycle_count_state as ccs
    sid = _cc("rejected", mode="registration")
    assert run(ccs.transition(sid, "reopen", "open", actor_name="Penguji")) is None
    assert DB.cycle_count_sessions.find_one({"id": sid})["status"] == "rejected"
    sid2 = _cc("draft", mode="registration")
    assert run(ccs.transition(sid2, "reg_start", "running", actor_name="Penguji"))["status"] == "running"
    with pytest.raises(ValueError):
        ccs.check("reg_submit", "draft", "pending_approval")
    with pytest.raises(ValueError):
        ccs.check("approve", "open", "approved")


def test_cycle_count_parallel_submit_one_winner():
    from services import cycle_count_state as ccs
    sid = _cc("open")

    async def race():
        return await asyncio.gather(*[ccs.transition(sid, "submit", "submitted", actor_name=f"P{i}")
                                      for i in range(5)])

    res = run(race())
    assert sum(1 for x in res if x) == 1
    h = DB.cycle_count_sessions.find_one({"id": sid})["status_history"]
    assert len(h) == 1 and h[0]["status"] == "submitted"


def test_rfid_cycle_count_session_history():
    from services import cycle_count_state as ccs
    sid = f"rvs_TEST_FIX10_{TAG}_{_nx()}"
    DB.rfid_verify_sessions.insert_one({"id": sid, "kind": "cycle_count", "status": "open",
                                        "status_history": ccs.initial_history("open", "Penguji", "rfid_create"),
                                        "saga_lock": {"action": "cycle_count_complete", "token": "t"}})
    out = run(ccs.transition(sid, "rfid_complete", "completed", actor_name="Penguji", claimed=True,
                             collection="rfid_verify_sessions", extra_filter={"kind": "cycle_count"},
                             set_fields={"completed_at": "x"}))
    assert out["status"] == "completed" and "saga_lock" not in out
    assert [e["status"] for e in out["status_history"]] == ["open", "completed"]


# ═══ F. kosakata status roll ═══════════════════════════════════════════════════════════════════════════════════
def test_registry_and_fe_vocab_aligned_with_roll_state():
    reg = open(os.path.join(REPO, "ENTITY_REGISTRY.md"), encoding="utf-8").read()
    m = re.search(r"### inventory_rolls .*?status\s+enum\s+(.*?)\n\s+tracking_mode", reg, re.S)
    assert m, "blok status inventory_rolls di ENTITY_REGISTRY.md tidak ditemukan"
    listed = set(re.findall(r"[a-z_]+", m.group(1).split("—")[0]))
    assert listed == set(rs.STATUSES), sorted(listed ^ set(rs.STATUSES))
    vocab = open(os.path.join(REPO, "frontend", "src", "utils", "statusVocab.js"), encoding="utf-8").read()
    block = vocab.split("roll: {", 1)[1].split("},", 1)[0]
    fe = set(re.findall(r"\b([a-z_]+):\s*\"", block))
    assert set(rs.STATUSES) <= fe, sorted(set(rs.STATUSES) - fe)
    buckets = (set(roll_service.PHYSICAL_STATUS_TO_BUCKET) | set(roll_service.TRANSIT_STATUS_TO_BUCKET)
               | set(roll_service.OFFSITE_OWNED_STATUS_TO_BUCKET))
    assert buckets <= set(rs.STATUSES)
    for frm, tos in rs.ROLL_TRANSITIONS.items():
        assert frm in rs.STATUSES and set(tos) <= set(rs.STATUSES), frm


def test_allocated_removed_from_roll_status_lists():
    from services import loading_check_service as lc
    from services import rfid_service
    assert "allocated" not in lc.EXPECTED_STATUSES and "allocated" not in rfid_service.PHYSICAL_STATUSES
    assert set(lc.EXPECTED_STATUSES) == set(roll_service.RELEASABLE_HELD_STATUSES)
    assert set(rfid_service.PHYSICAL_STATUSES) <= set(rs.STATUSES)


# ═══ G. guardrail INV-ROLL-02 ══════════════════════════════════════════════════════════════════════════════════
def _guard(*args):
    return subprocess.run([sys.executable, os.path.join(REPO, "scripts", "guardrails", "verify_roll_status_writer.py"),
                           *args], capture_output=True, text=True, env={**os.environ, "PYTHONUTF8": "1"}, timeout=120)


def test_guardrail_red_green():
    sys.path.insert(0, os.path.join(REPO, "scripts", "guardrails"))
    import verify_roll_status_writer as g
    red = 'async def f(db):\n    st = {"status": "available"}\n    await db.inventory_rolls.update_one({"id": 1}, {"$set": st})\n'
    assert len(g.scan_source(red)) == 1
    assert g.scan_source(red.replace("inventory_rolls", "wms_tasks")) == []
    res = _guard()
    assert res.returncode == 0, res.stdout[-2000:]
    assert _guard("--self-test").returncode == 0
    naik, baru, _ = g.compare({"backend/services/baru.py": 1}, g.load_baseline(g.NAME))
    assert baru and not naik   # berkas baru dengan penulis status roll = MERAH
