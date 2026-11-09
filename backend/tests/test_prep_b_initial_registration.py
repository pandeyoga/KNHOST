"""PREP-B — opname awal: pendaftaran ulang stok dari fisik per gedung (KEPUTUSAN_GATE_RFID §8, K-OPN-01..05).

Cakupan: sesi (draft→running→pending→approved/ditolak), pembekuan zona/penuh menolak gerakan (K-OPN-03), baris lapangan
(EPC kanonik & unik, produk aktif/tergantikan/tanpa satuan, panjang & konversi, K-OPN-04), produk belum dikenali,
rekonsiliasi per produk×PT, persetujuan massal (roll+tag baru, roll lama dicocokkan dipakai ulang, roll lama tak
terdaftar dihapus, jurnal per produk idempoten), pengulangan sesudah gangguan, mode EPC sistem, HTTP + izin.
Gudang & produk UJI dibuat sendiri (tidak menyentuh data acuan). Jalankan:
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_prep_b_initial_registration.py
"""
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6].upper()
OWNER = "ent_ksc"
W, W2 = f"wh_TESTREG_{TAG}", f"wh_TESTREG2_{TAG}"
OLD_TS = "2026-01-01T00:00:00+00:00"
SESSIONS, ROLLS = [], []


def epc(n: int) -> str:
    return f"E2{TAG}{n:016X}"


def _b(i, code):
    return {"id": f"bin_{TAG}_{i}", "code": f"{code}-{TAG}", "capacity": 1000}


B11, B12, B21, B31, B32 = _b(11, "A1-01"), _b(12, "A1-02"), _b(21, "A2-01"), _b(31, "B1-01"), _b(32, "B1-02")
Z1, Z2, R1, R2 = f"zone_{TAG}_1", f"zone_{TAG}_2", f"rack_{TAG}_1", f"rack_{TAG}_2"
WB1 = _b(91, "C1-01")


# FIX-1 (B2a STM-IN-02) — pendaftaran awal kini berpagar LOKASI petugas gudang: gedung uji diletakkan di site lokasi
# kerja petugas `warehouse@` (data acuan: Jakarta) supaya uji tetap menguji alur, bukan pagar lokasi.
_WH_USER_SITE = ((DB.users.find_one({"email": "warehouse@kainnusantara.id"}, {"_id": 0, "location_site_ids": 1}) or {})
                 .get("location_site_ids") or [None])[0]


def _wh(wid, zones):
    return {"id": wid, "code": wid.upper(), "name": f"TEST_REG {wid[-6:]}", "city": "Bandung", "sharing_mode": "dedicated",
            "entity_ids": [OWNER], "active": True, "zones": zones, "created_at": OLD_TS, "site_id": _WH_USER_SITE}


def _prod(pid, sku, **kw):
    return {"id": pid, "sku": sku, "name": f"Kain Uji {sku}", "base_unit": "yard", "status": "active", "stage": "finished",
            "grade": "A", "category": "Kain", "created_at": OLD_TS, **kw}


P, P2, P_OLD, P_NEW, P_NOUNIT = (f"prod_TREG_{TAG}_{x}" for x in ("a", "b", "old", "new", "nounit"))


def _roll(rid, pid, qty, bin_doc, wh=W, cost=10.0, **kw):
    doc = {"id": rid, "roll_no": f"OLD-{TAG}-{rid[-4:]}", "product_id": pid, "warehouse_id": wh, "owner_entity_id": OWNER,
           "length_initial": qty, "length_remaining": qty, "unit": "yard", "status": "available",
           "bin_id": (bin_doc or {}).get("id"), "bin_code": (bin_doc or {}).get("code", ""), "grade": "A", "unit_cost": cost,
           "base_unit_cost": cost, "lot": f"LOT-{TAG}", "created_at": OLD_TS, "tracking_mode": "barcode", **kw}
    DB.inventory_rolls.insert_one(doc)
    ROLLS.append(rid)
    return rid


def _tag(rid, e, wh=W):
    tid = f"rtag_{TAG}_{rid[-4:]}"
    DB.rfid_tags.insert_one({"id": tid, "epc": e, "roll_id": rid, "status": "active", "owner_entity_id": OWNER, "warehouse_id": wh,
                             "encoded_at": OLD_TS})
    DB.inventory_rolls.update_one({"id": rid}, {"$set": {"rfid_tag_id": tid, "tracking_mode": "rfid"}})


@pytest.fixture(scope="module", autouse=True)
def world():
    DB.warehouses.insert_many([
        _wh(W, [{"id": Z1, "name": "Zona A", "racks": [{"id": R1, "name": "Rak A1", "levels": [{"id": f"lv_{TAG}_1", "name": "T1",
                                                                                                "bins": [B11, B12]}]},
                                                       {"id": R2, "name": "Rak A2", "bins": [B21]}]},
                {"id": Z2, "name": "Zona B", "racks": [{"id": f"rack_{TAG}_3", "name": "Rak B1", "bins": [B31, B32]}]}]),
        _wh(W2, [{"id": f"zone_{TAG}_9", "name": "Zona C", "racks": [{"id": f"rack_{TAG}_9", "name": "Rak C1", "bins": [WB1]}]}])])
    DB.products.insert_many([_prod(P, f"TREG-A-{TAG}"), _prod(P2, f"TREG-B-{TAG}"),
                             _prod(P_OLD, f"TREG-OLD-{TAG}", status="inactive", superseded_by=P_NEW),
                             _prod(P_NEW, f"TREG-NEW-{TAG}", standard_cost=7.5), _prod(P_NOUNIT, f"TREG-NU-{TAG}", base_unit="")])
    yield
    rolls = [r["id"] for r in DB.inventory_rolls.find({"warehouse_id": {"$in": [W, W2]}}, {"id": 1})] + ROLLS
    DB.inventory_rolls.delete_many({"id": {"$in": rolls}})
    DB.inventory_movements.delete_many({"$or": [{"roll_id": {"$in": rolls}}, {"warehouse_id": {"$in": [W, W2]}}]})
    DB.rfid_tags.delete_many({"$or": [{"roll_id": {"$in": rolls}}, {"epc": {"$regex": f"^E2{TAG}"}}]})
    DB.journal_entries.delete_many({"source_type": "cycle_count_variance", "source_id": {"$regex": "|".join(SESSIONS) or "x^"}})
    DB.initial_registration_lines.delete_many({"session_id": {"$in": SESSIONS}})
    DB.cycle_count_sessions.delete_many({"id": {"$in": SESSIONS}})
    DB.registration_area_status.delete_many({"warehouse_id": {"$in": [W, W2]}})
    DB.inventory_balances.delete_many({"warehouse_id": {"$in": [W, W2]}})
    DB.inventory_lots.delete_many({"product_id": {"$in": [P, P2, P_NEW]}})
    DB.products.delete_many({"id": {"$in": [P, P2, P_OLD, P_NEW, P_NOUNIT]}})
    DB.warehouses.delete_many({"id": {"$in": [W, W2]}})


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": OWNER}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def whu():
    return _login("warehouse@kainnusantara.id")


def _new_session(h, **kw):
    body = {"warehouse_id": W, "name": f"TEST_REG {TAG}", "freeze_mode": "zone", "node_ids": [Z1], "epc_mode": "read", **kw}
    r = requests.post(f"{BASE}/registration/sessions", json=body, headers=h)
    assert r.status_code == 200, r.text
    SESSIONS.append(r.json()["id"])
    return r.json()


def _line(h, sid, **kw):
    return requests.post(f"{BASE}/registration/sessions/{sid}/lines", json=kw, headers=h)


def _detail(msg):
    d = msg.get("detail")
    return d.get("message", "") if isinstance(d, dict) else str(d)


# ─── 1. Alur utama: sesi zona, pembekuan, baris lapangan, rekonsiliasi, persetujuan massal ───────────────────────
def test_main_flow(adm, whu):
    from services import putaway_order_service as pos
    from services import registration_freeze as rfz
    from services import roll_service
    r_no, r_tag = _roll(f"roll_T{TAG}_r001", P, 50, B11), _roll(f"roll_T{TAG}_r002", P, 40, B11)
    r_miss, r_p2 = _roll(f"roll_T{TAG}_r003", P, 30, B11), _roll(f"roll_T{TAG}_r004", P2, 20, B12, cost=5.0)
    r_alloc = _roll(f"roll_T{TAG}_r005", P, 25, B21, status="reserved", reserved_ref={"type": "sales_order", "id": f"so_{TAG}"})
    r_z2 = _roll(f"roll_T{TAG}_r006", P, 60, B31)
    _tag(r_tag, epc(900))
    _tag(r_z2, epc(901))
    # validasi pembuatan
    bad = requests.post(f"{BASE}/registration/sessions", json={"warehouse_id": W, "freeze_mode": "zone", "node_ids": []}, headers=whu)
    assert bad.status_code == 400
    bad = requests.post(f"{BASE}/registration/sessions", json={"warehouse_id": W, "freeze_mode": "x", "node_ids": [Z1]}, headers=whu)
    assert bad.status_code == 400
    assert requests.post(f"{BASE}/registration/sessions", json={"warehouse_id": W}).status_code == 401
    s = _new_session(whu)
    sid = s["id"]
    assert s["status"] == "draft" and s["freeze"]["active"] is False and s["number"].endswith(s["number"][-5:])
    assert {r["rack_id"] for r in s["progress"]["racks"]} == {R1, R2}
    # baris sebelum 'mulai' ditolak
    assert _line(whu, sid, epc=epc(1), product_id=P, qty=10, bin_id=B11["id"]).status_code == 400
    st = requests.post(f"{BASE}/registration/sessions/{sid}/start", headers=whu)
    assert st.status_code == 200 and st.json()["status"] == "running" and st.json()["freeze"]["active"] is True
    # sesi kedua beririsan → 409
    s2 = _new_session(whu, node_ids=[R1])
    assert requests.post(f"{BASE}/registration/sessions/{s2['id']}/start", headers=whu).status_code == 409

    # ── K-OPN-03: gerakan dari/ke zona beku ditolak; zona lain tetap melayani
    put = lambda rid, b: requests.post(f"{BASE}/inventory/putaway", json={"roll_id": rid, "bin_id": b["id"]}, headers=adm)  # noqa: E731
    r = put(r_z2, B11)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "REGISTRATION_FREEZE", r.text
    assert TAG in _detail(r.json()) or "Zona A" in _detail(r.json())
    assert put(r_miss, B32).status_code == 409                       # dari zona beku
    assert put(r_z2, B32).status_code == 200, put(r_z2, B32).text   # zona B bebas
    with pytest.raises(Exception) as ei:
        run(pos.create_order(W, "wh_jakarta", [r_miss], [OWNER], "uji"))
    assert getattr(ei.value, "status_code", 0) == 409
    DB.inventory_rolls.update_one({"id": r_miss}, {"$set": {"length_reservations": [{"id": f"rsv_{TAG}", "qty": 5}]}})
    with pytest.raises(Exception) as ei:
        run(roll_service.confirm_cut(r_miss, f"rsv_{TAG}", 5, 0, "uji"))
    assert getattr(ei.value, "status_code", 0) == 409
    DB.inventory_rolls.update_one({"id": r_miss}, {"$unset": {"length_reservations": ""}})
    DB.inventory_rolls.update_one({"id": r_miss}, {"$set": {"transfer_ref": {"id": f"trn_{TAG}"}}})
    with pytest.raises(Exception) as ei:
        run(rfz.assert_transfer_movable({"id": f"trn_{TAG}", "source_warehouse_id": W}, "out"))
    assert getattr(ei.value, "status_code", 0) == 409
    DB.inventory_rolls.update_one({"id": r_miss}, {"$unset": {"transfer_ref": ""}})
    with pytest.raises(Exception) as ei:
        run(rfz.assert_task_movable({"warehouse_id": W, "scan_log": []}, "pengambilan (picking) outbound", roll_id=r_miss))
    assert getattr(ei.value, "status_code", 0) == 409
    run(rfz.assert_task_movable({"warehouse_id": W, "scan_log": []}, "uji", roll_id=r_z2))   # zona B → lolos

    # ── baris lapangan
    assert _line(whu, sid, epc="ZZZ", product_id=P, qty=10, bin_id=B11["id"]).status_code == 400          # EPC tidak kanonik
    assert _line(whu, sid, epc=epc(2), product_id=P, qty=10, bin_id=B31["id"]).status_code == 400        # bin di luar cakupan
    assert _line(whu, sid, epc=epc(2), product_id=P_NOUNIT, qty=10, bin_id=B11["id"]).status_code == 400  # tanpa satuan dasar
    assert _line(whu, sid, epc=epc(901), product_id=P, qty=10, bin_id=B11["id"]).status_code == 409      # tag hidup di luar cakupan
    l1 = _line(whu, sid, epc=epc(1).lower(), product_id=P, qty=48, unit="yard", length_from_label=True, bin_id=B11["code"],
               old_roll_no=DB.inventory_rolls.find_one({"id": r_no})["roll_no"], lot="LOT-X", grade="A")
    assert l1.status_code == 200, l1.text
    l1 = l1.json()
    assert l1["epc"] == epc(1) and l1["matched_roll_id"] == r_no and l1["match_source"] == "old_no" and l1["length_verified"] is True
    assert _line(whu, sid, epc=epc(1), product_id=P, qty=5, bin_id=B11["id"]).status_code == 409         # EPC kembar
    l2 = _line(whu, sid, epc=epc(900), product_id=P, qty=40, bin_id=B12["id"]).json()                   # tag lama terbaca
    assert l2["matched_roll_id"] == r_tag and l2["match_source"] == "epc" and l2["length_verified"] is False
    l3 = _line(whu, sid, epc=epc(3), product_id=P, qty=35, unit="meter", bin_id=B12["id"], old_roll_no="TIDAK-ADA").json()
    assert l3["matched_roll_id"] == "" and l3["match_note"] and abs(l3["qty"] - 35 / 0.9144) < 0.01
    l4 = _line(whu, sid, epc=epc(4), unrecognized=True, note="kain biru motif bunga", qty=10, unit="yard", bin_id=B21["id"])
    assert l4.status_code == 200, l4.text
    l4 = l4.json()
    assert l4["product_id"] == "" and l4["unrecognized"]["note"]
    assert _line(whu, sid, epc=epc(6), unrecognized=True, note="", qty=10, bin_id=B21["id"]).status_code == 400
    l5 = _line(whu, sid, epc=epc(5), product_id=P_OLD, qty=12, bin_id=B21["id"]).json()                 # tergantikan → pengganti
    assert l5["product_id"] == P_NEW and l5["redirected_from"]["id"] == P_OLD
    chk = requests.post(f"{BASE}/registration/sessions/{sid}/epc-check", json={"codes": f"{epc(1)}\nBUKAN-EPC, {epc(77)}"}, headers=whu).json()
    assert [x["ok"] for x in chk["results"]] == [False, False, True]
    dec = requests.post(f"{BASE}/registration/sessions/{sid}/label-decode",
                        json={"raw": f"TREG-A-{TAG}|LOT9|SR-1|25.5"}, headers=whu).json()
    assert dec["product"]["id"] == P and dec["length"] == 25.5 and dec["old_roll_no"] == "SR-1"
    prog = requests.post(f"{BASE}/registration/sessions/{sid}/racks/{R1}", json={"done": True}, headers=whu).json()
    assert prog["racks_done"] == 1 and prog["lines"] == 5 and prog["unmapped"] == 1

    # ── ajukan → rekonsiliasi per produk×PT
    assert requests.post(f"{BASE}/registration/sessions/{sid}/submit", headers=whu).status_code == 200
    rec = requests.get(f"{BASE}/registration/sessions/{sid}/reconcile", headers=whu).json()
    g = {x["product_id"]: x for x in rec["groups"]}
    assert g[P]["old_rolls"] == 4 and g[P]["reuse"] == 2 and g[P]["new"] == 1 and g[P]["missing_rolls"] == 2
    assert g[P]["unit_cost"] == 10 and g[P]["cost_basis"] == "wac_gudang"                     # K-OPN-02
    assert g[P2]["missing_rolls"] == 1 and g[P2]["registered_rolls"] == 0
    assert g[P_NEW]["unit_cost"] == 7.5 and g[P_NEW]["cost_basis"] == "produk.standard_cost"
    assert len(rec["unmapped"]) == 1
    # izin & produk belum dikenali
    ap = lambda h, **kw: requests.post(f"{BASE}/registration/sessions/{sid}/approve", json={"reason": "ACC uji", **kw}, headers=h)  # noqa: E731
    assert ap(whu).status_code == 403
    assert ap(adm).status_code == 400                                                          # unmapped
    patch = lambda h: requests.patch(f"{BASE}/registration/sessions/{sid}/lines/{l4['id']}", json={"product_id": P2}, headers=h)  # noqa: E731
    assert patch(whu).status_code == 403
    pr_ = patch(adm)
    assert pr_.status_code == 200 and pr_.json()["product_id"] == P2 and pr_.json()["qty"] == 10, pr_.text
    # persetujuan per produk (P_NEW) → roll + tag + jurnal
    one = ap(adm, group_keys=[g[P_NEW]["key"]]).json()
    assert one["results"][g[P_NEW]["key"]]["status"] == "applied" and one["complete"] is False
    new5 = DB.inventory_rolls.find_one({"registration.line_id": l5["id"]})
    assert new5 and new5["unit_cost"] == 7.5 and new5["acquired"]["via"] == "initial_registration" and new5["bin_id"] == B21["id"]
    tag5 = DB.rfid_tags.find_one({"roll_id": new5["id"], "status": "active"})
    assert tag5 and tag5["epc"] == epc(5) and new5["rfid_tag_id"] == tag5["id"]
    # seluruh sesi: P punya roll lama teralokasi → pengecualian, sesi tetap menunggu
    allr = ap(adm).json()
    assert allr["complete"] is False and allr["results"][g[P]["key"]]["status"] == "exception", allr["results"]
    assert allr["results"][g[P2]["key"]]["status"] == "applied"
    no = DB.inventory_rolls.find_one({"id": r_no})
    assert no["length_remaining"] == 48 and no["length_verified"] is True and no["rfid_epc"] == epc(1), allr["results"]
    assert DB.rfid_tags.find_one({"id": no["rfid_tag_id"]})["epc"] == epc(1)
    assert DB.inventory_rolls.find_one({"id": r_tag})["bin_id"] == B12["id"]
    assert DB.inventory_rolls.find_one({"id": r_miss})["status"] == "consumed"
    assert DB.inventory_rolls.find_one({"id": r_alloc})["status"] == "reserved"
    assert DB.inventory_rolls.find_one({"id": r_p2})["status"] == "consumed"
    new3 = DB.inventory_rolls.find_one({"registration.line_id": l3["id"]})
    assert new3["length_verified"] is False and new3["unit_cost"] == 10
    assert not DB.journal_entries.find_one({"source_id": f"{sid}:reg:{g[P]['key']}"})          # jurnal menunggu tuntas
    je2 = DB.journal_entries.find_one({"source_id": f"{sid}:reg:{g[P2]['key']}"})
    assert je2 and round(sum(x["debit"] for x in je2["lines"]), 2) == 50.0                     # 10×5 − 20×5 = −50
    # terima pengecualian → tuntas
    fin = ap(adm, accept_exceptions=True).json()
    assert fin["complete"] is True and fin["session"]["status"] == "approved_with_exceptions"
    je = DB.journal_entries.find_one({"source_id": f"{sid}:reg:{g[P]['key']}"})
    exp = round((48 - 50) * 10 + 0 + round(35 / 0.9144, 4) * 10 - 30 * 10, 2)
    assert je and abs(round(sum(x["debit"] for x in je["lines"]), 2) - abs(exp)) < 0.02
    assert DB.cycle_count_sessions.find_one({"id": sid})["freeze"]["active"] is False
    assert DB.registration_area_status.find_one({"key": f"{W}:{Z1}"})["session_id"] == sid
    assert put(r_z2, B11).status_code == 200                                                   # pembekuan dilepas
    # idempoten: diulang tidak menggandakan apa pun
    assert ap(adm).status_code == 400
    assert DB.journal_entries.count_documents({"source_id": {"$regex": f"^{sid}:reg:"}}) == 3
    assert DB.inventory_rolls.count_documents({"registration.session_id": sid}) == 5
    fz = requests.get(f"{BASE}/registration/freeze", params={"warehouse_id": W}, headers=adm).json()
    assert fz["freezes"] == [] and fz["verified_areas"]
    requests.post(f"{BASE}/registration/sessions/{s2['id']}/reject", json={"reason": "uji selesai"}, headers=adm)


# ─── 2. Beku penuh, cakupan seluruh gedung (roll tanpa bin ikut), EPC sistem, retry sesudah gangguan ─────────────
def test_full_freeze_system_epc_and_retry(adm, whu, monkeypatch):
    from services import gl_service
    from services import initial_registration_approve as ira
    from services import initial_registration_service as irs
    old_nobin = _roll(f"roll_T{TAG}_w001", P, 15, None, wh=W2)
    s = _new_session(whu, warehouse_id=W2, freeze_mode="warehouse", node_ids=[], epc_mode="system")
    sid = s["id"]
    assert requests.post(f"{BASE}/registration/sessions/{sid}/start", headers=whu).status_code == 200
    grn = _roll(f"roll_T{TAG}_w002", P, 9, None, wh=W2, created_at="2099-01-01T00:00:00+00:00", status="receiving")
    r = requests.post(f"{BASE}/inventory/putaway", json={"roll_id": grn, "bin_id": WB1["id"]}, headers=adm)
    assert r.status_code == 409 and "beku penuh" in _detail(r.json())                       # GRN baru: tak boleh ke bin beku
    a = _line(whu, sid, product_id=P, qty=20, bin_id=WB1["id"]).json()
    b = _line(whu, sid, product_id=P, qty=22, bin_id=WB1["id"]).json()
    assert a["epc_source"] == "system" and a["tag_state"] == "pending_write" and len(a["epc"]) == 24 and a["epc"] != b["epc"]
    assert requests.post(f"{BASE}/registration/sessions/{sid}/submit", headers=whu).status_code == 200
    rec = requests.get(f"{BASE}/registration/sessions/{sid}/reconcile", headers=whu).json()
    grp = rec["groups"][0]
    assert grp["old_rolls"] == 1 and grp["missing"][0]["roll_id"] == old_nobin                # roll tanpa bin ikut; GRN baru tidak

    calls = {"n": 0}
    real = gl_service.post_cycle_count_variance

    async def flaky(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("gangguan jurnal (uji)")
        return await real(**kw)

    monkeypatch.setattr(gl_service, "post_cycle_count_variance", flaky)
    sess = run(irs.load(sid))
    with pytest.raises(RuntimeError):
        run(ira.approve(sess, [], "Uji Penyetuju", None, reason="ACC uji", zero_cost_reason="", accept_exceptions=False))
    assert "saga_lock" not in DB.cycle_count_sessions.find_one({"id": sid})                     # kunci dilepas → bisa diulang
    out = run(ira.approve(run(irs.load(sid)), [], "Uji Penyetuju", None, reason="ACC uji", zero_cost_reason="", accept_exceptions=False))
    assert out["complete"] is True and out["session"]["status"] == "approved"
    assert DB.inventory_rolls.count_documents({"registration.session_id": sid}) == 2            # tidak ada roll ganda
    assert DB.journal_entries.count_documents({"source_id": {"$regex": f"^{sid}:reg:"}}) == 1
    assert DB.inventory_rolls.find_one({"id": old_nobin})["status"] == "consumed"
    roll_a = DB.inventory_rolls.find_one({"registration.line_id": a["id"]})
    assert roll_a["id"] == ira.new_roll_id(sid, a["id"])
    tag_a = DB.rfid_tags.find_one({"id": roll_a["rfid_tag_id"]})
    assert tag_a["status"] == "pending_print" and tag_a["epc"] == a["epc"]                    # menunggu ditulis
    mw = requests.post(f"{BASE}/registration/sessions/{sid}/lines/mark-written", json={"line_ids": [a["id"]]}, headers=whu).json()
    assert mw == {"written": 1, "activated_tags": 1}
    assert DB.rfid_tags.find_one({"id": roll_a["rfid_tag_id"]})["status"] == "active"
    after = requests.post(f"{BASE}/inventory/putaway", json={"roll_id": grn, "bin_id": WB1["id"]}, headers=adm)
    assert after.status_code != 409 or (after.json().get("detail") or {}).get("code") != "REGISTRATION_FREEZE", after.text
    from services import registration_freeze as rfz
    run(rfz.assert_movable(action="uji", to_warehouse_id=W2, to_bin_id=WB1["id"]))           # beku sudah dilepas


# ─── 3. Tolak: pembekuan dilepas, baris batal, EPC bebas lagi; kembalikan ke berjalan ────────────────────────────
def test_reject_and_return(adm, whu):
    s = _new_session(whu, node_ids=[Z2])
    sid = s["id"]
    requests.post(f"{BASE}/registration/sessions/{sid}/start", headers=whu)
    ln = _line(whu, sid, epc=epc(50), product_id=P, qty=5, bin_id=B32["id"])
    assert ln.status_code == 200, ln.text
    assert requests.post(f"{BASE}/registration/sessions/{sid}/submit", headers=whu).status_code == 200
    assert requests.post(f"{BASE}/registration/sessions/{sid}/return", json={"reason": "cek ulang"}, headers=whu).status_code == 403
    back = requests.post(f"{BASE}/registration/sessions/{sid}/return", json={"reason": "cek ulang rak"}, headers=adm)
    assert back.status_code == 200 and back.json()["status"] == "running"
    assert requests.delete(f"{BASE}/registration/sessions/{sid}/lines/{ln.json()['id']}", headers=whu).status_code == 200
    ln2 = _line(whu, sid, epc=epc(50), product_id=P, qty=6, bin_id=B32["id"])
    assert ln2.status_code == 200                                                                # EPC baris batal bebas lagi
    rj = requests.post(f"{BASE}/registration/sessions/{sid}/reject", json={"reason": "salah cakupan"}, headers=adm)
    assert rj.status_code == 200 and rj.json()["status"] == "rejected" and rj.json()["freeze"]["active"] is False
    assert DB.initial_registration_lines.find_one({"id": ln2.json()["id"]})["status"] == "void"
    lst = requests.get(f"{BASE}/registration/sessions", params={"warehouse_id": W}, headers=whu).json()
    assert sid in {x["id"] for x in lst}
    classic = requests.get(f"{BASE}/cycle-count/sessions", headers=adm).json()
    assert sid not in {x["id"] for x in classic}                                                 # tidak bercampur opname biasa
