"""FIX-1 (audit WMS-RFID 9 Nov 2026) — cakupan lokasi kerja, PT & keamanan akses.

Uji HTTP terhadap server hidup (stack sementara / salinan DB data acuan 8 Nov). Menutup & menjaga:
  * B3a SCP-1  — 5 endpoint roll RFID memakai dokumen roll asli (PT + lokasi), HPP tidak bocor.
  * B3b FRM-23 — `GET /inbound/qc/tasks/{id}/rolls` dijaga seperti `/plan`.
  * B3b FRM-01 — `PATCH /warehouses/{id}`: cakupan PT/lokasi, struktur hanya admin/Admin Gudang, zona lewat jalur
                 struktur berpenjaga, nama tidak kosong, lat/lng dalam batas.
  * B2a STM-IN-02 — cakupan lokasi di AKSI TULIS (PA, transfer, opname) bukan hanya daftar/pembuatan.
  * B3a SCP-2/SCP-3, B1 K-B1-01/02 — daftar per gedung lokasi kerja (lintas PT yang ditugaskan) + saringan tampilan
                 (`X-Location-Scope`); petugas berpagar tidak bisa melebar.
  * B1 K-B1-10 — penanda data uji `is_test` menyembunyikan gudang/PT dari pemilih & daftar bawaan.
  * G-SCOPE-01 (B3b §8) — sapuan otomatis endpoint `GET …/{id}` WMS-RFID dengan id milik PT/lokasi lain → 403/404.
Pelaksana: `cd /app/backend && KN_DEMO_PW=<sandi demo> python -m pytest -q -p no:cacheprovider -n0 tests/test_fix1_cakupan.py`.
"""
import os
import re

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
# Sandi akun demo TIDAK ditulis di berkas ini (aturan paket): diambil dari lingkungan (`KN_DEMO_PW`).
PW = os.environ.get("KN_DEMO_PW", "")
if not PW:
    pytest.skip("set KN_DEMO_PW (sandi akun demo data acuan) untuk menjalankan uji FIX-1", allow_module_level=True)
ACC = {
    "admin": "admin@kainnusantara.id", "soreang": "warehouse.soreang@kainnusantara.id",
    "rcm": "warehouse.rancamalang@kainnusantara.id", "jkt": "warehouse@kainnusantara.id",
    "whadmin": "wh.admin@kainnusantara.id", "driver": "driver@kainnusantara.id",
}
KSC, KANDA, CST = "ent_ksc", "ent_kanda", "ent_82b52ed6ee8b"
JKT, SRG = "wh_jakarta", "wh_40e831c5bb53"
PROTECTED = (403, 404)


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    yield cli[os.environ.get("DB_NAME", "test_database")]
    cli.close()


@pytest.fixture(scope="module")
def tok():
    out = {}
    for k, email in ACC.items():
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=30)
        assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"
        out[k] = r.json()["token"]
    return out


def H(t, ent=None, loc=None):
    h = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    if ent:
        h["X-Entity-Id"] = ent
    if loc is not None:
        h["X-Location-Scope"] = loc
    return h


def _jkt_roll(db, owner=KSC):
    r = db.inventory_rolls.find_one({"warehouse_id": JKT, "owner_entity_id": owner, "status": "available",
                                     "unit_cost": {"$gt": 0}}, {"_id": 0, "id": 1, "roll_no": 1})
    if not r:
        pytest.skip("data acuan tanpa roll Jakarta ber-HPP")
    return r


# ─── B3a SCP-1 — endpoint roll RFID ─────────────────────────────────────────────
class TestScp1RfidRoll:
    def test_lookup_blocks_other_pt_and_location(self, tok, db):
        roll = _jkt_roll(db)
        r = requests.get(f"{API}/rfid/lookup", params={"code": roll["roll_no"], "record": "false"},
                         headers=H(tok["soreang"]), timeout=30)
        assert r.status_code in PROTECTED, f"petugas Soreang/Kanda membaca roll KSC Jakarta: {r.status_code}"

    def test_lookup_strips_cost_for_operator(self, tok, db):
        roll = _jkt_roll(db)
        r = requests.get(f"{API}/rfid/lookup", params={"code": roll["roll_no"], "record": "false"},
                         headers=H(tok["jkt"]), timeout=30)
        assert r.status_code == 200, r.text[:200]
        body = r.json()["roll"]
        assert "unit_cost" not in body and "base_unit_cost" not in body, "HPP roll bocor ke peran gudang"

    def test_roll_subresources_guarded(self, tok, db):
        roll = _jkt_roll(db)
        h = H(tok["soreang"])
        assert requests.get(f"{API}/rfid/rolls/{roll['id']}/print-history", headers=h, timeout=30).status_code in PROTECTED
        assert requests.get(f"{API}/rfid/roll-scans/{roll['id']}", headers=h, timeout=30).status_code in PROTECTED
        assert requests.post(f"{API}/rfid/rolls/{roll['id']}/label-prints", json={"channel": "browser"},
                             headers=h, timeout=30).status_code in PROTECTED
        assert requests.post(f"{API}/rfid/roll-scans", json={"code": roll["roll_no"]}, headers=h,
                             timeout=30).status_code in PROTECTED


# ─── B3b FRM-23 ─────────────────────────────────────────────────────────────────
def test_frm23_qc_task_rolls_guarded(tok, db):
    task = db.wms_tasks.find_one({"entity_id": CST, "flow_type": "inbound"}, {"_id": 0, "id": 1})
    if not task:
        pytest.skip("tanpa tugas masuk Cipta Sandang")
    r = requests.get(f"{API}/inbound/qc/tasks/{task['id']}/rolls", headers=H(tok["jkt"]), timeout=30)
    plan = requests.get(f"{API}/inbound/qc/tasks/{task['id']}/plan", headers=H(tok["jkt"]), timeout=30)
    assert plan.status_code in PROTECTED
    assert r.status_code in PROTECTED, f"/rolls {r.status_code} sementara /plan {plan.status_code}"


# ─── B3b FRM-01 ─────────────────────────────────────────────────────────────────
class TestFrm01WarehousePatch:
    def test_operator_cannot_patch_other_pt_dedicated(self, tok, db):
        wid = "wh_2328786267dd"   # GU-CST — khusus Cipta Sandang
        before = (db.warehouses.find_one({"id": wid}, {"_id": 0, "city": 1}) or {}).get("city")
        r = requests.patch(f"{API}/warehouses/{wid}", json={"data": {"city": "Uji FIX-1"}}, headers=H(tok["jkt"]), timeout=30)
        assert r.status_code == 403, r.text[:200]
        assert (db.warehouses.find_one({"id": wid}, {"_id": 0, "city": 1}) or {}).get("city") == before

    def test_operator_cannot_change_structure(self, tok, db):
        n_before = len((db.warehouses.find_one({"id": JKT}, {"_id": 0, "zones": 1}) or {}).get("zones") or [])
        r = requests.patch(f"{API}/warehouses/{JKT}", json={"data": {"zones": []}}, headers=H(tok["jkt"]), timeout=30)
        assert r.status_code == 403, r.text[:200]
        assert len((db.warehouses.find_one({"id": JKT}, {"_id": 0, "zones": 1}) or {}).get("zones") or []) == n_before

    def test_zones_replacement_uses_guarded_structure_path(self, tok, db):
        r = requests.patch(f"{API}/warehouses/{JKT}", json={"data": {"zones": []}}, headers=H(tok["admin"]), timeout=60)
        assert r.status_code == 409 and "LOCATION_IN_USE" in r.text, f"bin berisi roll terhapus: {r.status_code} {r.text[:200]}"
        assert (db.warehouses.find_one({"id": JKT}, {"_id": 0, "zones": 1}) or {}).get("zones")

    @pytest.mark.parametrize("data", [{"name": ""}, {"name": "   "}, {"code": ""}, {"lat": 999}, {"lng": -999}, {"lat": "x"}])
    def test_basic_field_validation(self, tok, data):
        r = requests.patch(f"{API}/warehouses/{JKT}", json={"data": data}, headers=H(tok["admin"]), timeout=30)
        assert r.status_code == 400, f"{data} → {r.status_code} {r.text[:160]}"


# ─── B2a STM-IN-02 — aksi tulis menghormati lokasi kerja ────────────────────────
class TestStmIn02WriteActions:
    def test_pa_actions_need_location_side(self, tok, db):
        pa = db.putaway_orders.find_one({"from_warehouse_id": JKT, "owner_entity_id": KSC}, {"_id": 0, "id": 1, "to_warehouse_id": 1})
        if not pa:
            pytest.skip("tanpa PA Jakarta di data acuan")
        h_rcm = H(tok["rcm"], KSC)   # PT KSC ditugaskan ke petugas Rancamalang → yang diuji murni LOKASI
        for path, body in (("dispatch", {}), ("publish", {}), ("cancel-draft", {"reason": "uji cakupan lokasi"})):
            r = requests.post(f"{API}/putaway-orders/{pa['id']}/{path}", json=body, headers=h_rcm, timeout=30)
            assert r.status_code == 403, f"{path} oleh petugas Rancamalang (asal Jakarta): {r.status_code} {r.text[:160]}"
        h_jkt = H(tok["jkt"], KSC)   # tujuan RCM-WOVEN di luar Jakarta
        for path, body in (("arrival-trips", {"epcs": [], "client_trip_id": "fix1-uji"}),
                           ("close", {"action": "return_transit", "reason": "uji cakupan lokasi"})):
            r = requests.post(f"{API}/putaway-orders/{pa['id']}/{path}", json=body, headers=h_jkt, timeout=30)
            assert r.status_code == 403, f"{path} oleh petugas Jakarta (tujuan Rancamalang): {r.status_code} {r.text[:160]}"

    def test_transfer_receive_needs_dest_location(self, tok, db):
        t = db.warehouse_transfers.find_one({"dest_warehouse_id": JKT, "entity_id": KSC}, {"_id": 0, "id": 1})
        if not t:
            pytest.skip("tanpa transfer ke Jakarta")
        r = requests.post(f"{API}/transfers/{t['id']}/receive", json={"lines": [{"code": "TIDAK-ADA"}]},
                          headers=H(tok["rcm"], KSC), timeout=30)
        assert r.status_code == 403, f"petugas Rancamalang menerima transfer Jakarta: {r.status_code} {r.text[:160]}"
        d = requests.get(f"{API}/transfers/{t['id']}", headers=H(tok["rcm"], KSC), timeout=30)
        assert d.status_code in PROTECTED, f"detail transfer Jakarta terbuka untuk Rancamalang: {d.status_code}"

    def test_cycle_count_session_location(self, tok, db):
        r = requests.post(f"{API}/cycle-count/sessions", json={"warehouse_id": JKT, "name": "FIX-1 uji lokasi"},
                          headers=H(tok["jkt"], KSC), timeout=30)
        assert r.status_code == 200, r.text[:200]
        sid = r.json()["id"]
        try:
            scan = requests.post(f"{API}/cycle-count/sessions/{sid}/roll-scans",
                                 json={"code": "TIDAK-ADA", "bin_id": "x"}, headers=H(tok["rcm"], KSC), timeout=30)
            assert scan.status_code in PROTECTED, f"petugas Rancamalang memindai opname Jakarta: {scan.status_code}"
            got = requests.get(f"{API}/cycle-count/sessions/{sid}", headers=H(tok["rcm"], KSC), timeout=30)
            assert got.status_code in PROTECTED
            mine = requests.get(f"{API}/cycle-count/sessions", headers=H(tok["rcm"], KSC), timeout=30).json()
            assert sid not in {s["id"] for s in mine}, "sesi Jakarta tampil di daftar petugas Rancamalang"
            other = requests.post(f"{API}/cycle-count/sessions", json={"warehouse_id": JKT, "name": "x"},
                                  headers=H(tok["rcm"], KSC), timeout=30)
            assert other.status_code == 403, f"petugas Rancamalang membuka opname Jakarta: {other.status_code}"
        finally:
            db.cycle_count_sessions.delete_one({"id": sid})


# ─── B3a SCP-2/SCP-3 + K-B1-01/02 — daftar per gedung lokasi kerja ─────────────
class TestWorkLocationLists:
    def test_transfers_follow_location(self, tok, db):
        rows = requests.get(f"{API}/transfers", headers=H(tok["soreang"]), timeout=60).json()
        srg_ids = {w["id"] for w in db.warehouses.find({"site_id": "site_fd9f6aa41d36"}, {"_id": 0, "id": 1})}
        bad = [t["code"] for t in rows if t.get("source_warehouse_id") not in srg_ids and t.get("dest_warehouse_id") not in srg_ids]
        assert not bad, f"petugas Soreang melihat transfer di luar Soreang: {bad[:5]}"

    def test_rfid_lists_follow_location(self, tok, db):
        rcm_ids = {w["id"] for w in db.warehouses.find({"site_id": "site_c0c8400b0017"}, {"_id": 0, "id": 1})}
        tags = requests.get(f"{API}/rfid/tags", headers=H(tok["rcm"], KSC), timeout=60).json()["tags"]
        assert all(t.get("warehouse_id") in rcm_ids for t in tags), "tag RFID di luar Rancamalang tampil"
        jobs = requests.get(f"{API}/rfid/print-jobs", headers=H(tok["rcm"], KSC), timeout=60).json()["jobs"]
        assert all(j.get("warehouse_id") in rcm_ids for j in jobs), "job cetak di luar Rancamalang tampil"
        r = requests.get(f"{API}/rfid/tags", params={"warehouse_id": JKT}, headers=H(tok["rcm"], KSC), timeout=60)
        assert r.status_code == 403, "petugas berpagar meminta gudang di luar lokasi → harus 403"

    def test_physical_tasks_cross_pt_with_labels(self, tok, db):
        rows = requests.get(f"{API}/wms/tasks", headers=H(tok["rcm"]), timeout=60).json()
        open_rows = [t for t in rows if t.get("status") not in ("completed", "cancelled", "dispatched")]
        rcm_ids = {w["id"] for w in db.warehouses.find({"site_id": "site_c0c8400b0017"}, {"_id": 0, "id": 1})}
        assert open_rows and all(t["warehouse_id"] in rcm_ids for t in open_rows)
        ents = {t.get("entity_id") for t in open_rows}
        want = set(db.wms_tasks.distinct("entity_id", {"warehouse_id": {"$in": list(rcm_ids)},
                                                       "status": {"$nin": ["completed", "cancelled", "dispatched"]}}))
        assert ents == want & {KSC, KANDA, CST}, f"tugas gedung Rancamalang per PT tidak lengkap: {ents} vs {want}"
        assert all(t.get("work_entity_name") and t.get("task_kind_label") for t in open_rows), "label PT/jenis tugas hilang"

    def test_hard_scoped_cannot_widen_with_header(self, tok):
        rows = requests.get(f"{API}/wms/tasks", headers=H(tok["soreang"], loc="all"), timeout=60).json()
        assert rows and {t["warehouse_id"] for t in rows} == {SRG}
        s = requests.get(f"{API}/location-scope", headers=H(tok["soreang"], loc="all"), timeout=30).json()
        assert s["view"]["mode"] == "restricted" and s["can_pick_all"] is False

    def test_supervisor_default_home_and_explicit_all(self, tok, db):
        uid = db.users.find_one({"email": ACC["whadmin"]}, {"_id": 0, "id": 1})["id"]
        before = db.users.find_one({"id": uid}, {"_id": 0, "location_site_ids": 1, "location_warehouse_ids": 1})
        db.users.update_one({"id": uid}, {"$set": {"location_site_ids": ["site_54bed6261604"], "location_warehouse_ids": []}})
        try:
            s = requests.get(f"{API}/location-scope", headers=H(tok["whadmin"]), timeout=30).json()
            assert s["view"]["mode"] == "home" and s["home_set"] and s["can_pick_all"]
            home = requests.get(f"{API}/wms/tasks", headers=H(tok["whadmin"]), timeout=60).json()
            assert home and {t["warehouse_id"] for t in home} == {JKT}, "bawaan supervisor bukan lokasi kerjanya"
            allr = requests.get(f"{API}/wms/tasks", headers=H(tok["whadmin"], loc="all"), timeout=60).json()
            assert len({t["warehouse_id"] for t in allr}) > 1, "pilihan eksplisit 'Semua lokasi' tidak melebar"
        finally:
            db.users.update_one({"id": uid}, {"$set": {k: before.get(k, []) for k in ("location_site_ids", "location_warehouse_ids")}})

    def test_unset_location_is_flagged(self, tok):
        s = requests.get(f"{API}/location-scope", headers=H(tok["admin"]), timeout=30).json()
        assert s["view"]["mode"] == "unset" and s["home_set"] is False

    def test_driver_sees_only_deliveries_without_wms(self, tok):
        assert requests.get(f"{API}/logistics/deliveries", params={"mine": "true"}, headers=H(tok["driver"]),
                            timeout=30).status_code == 200
        assert requests.get(f"{API}/location-scope", headers=H(tok["driver"]), timeout=30).status_code == 200


# ─── B1 K-B1-10 — penanda data uji ──────────────────────────────────────────────
def test_test_marker_hides_from_pickers_and_lists(tok, db):
    wh = db.warehouses.find_one({"code": {"$regex": "^TEST-"}, "active": True}, {"_id": 0, "id": 1})
    ent = db.business_entities.find_one({"legal_name": {"$regex": "^PT Uji Provisioning"}}, {"_id": 0, "id": 1})
    if not wh or not ent:
        pytest.skip("data acuan tanpa residu uji")
    db.warehouses.update_one({"id": wh["id"]}, {"$set": {"is_test": True}})
    db.business_entities.update_one({"id": ent["id"]}, {"$set": {"is_test": True}})
    try:
        import time
        time.sleep(16)   # cache penanda 15 dtk di location_scope
        ids = {w["id"] for w in requests.get(f"{API}/warehouses", headers=H(tok["admin"], KSC), timeout=30).json()}
        assert wh["id"] not in ids
        master = {w["id"] for w in requests.get(f"{API}/warehouses", params={"scope": "all"}, headers=H(tok["admin"], KSC), timeout=30).json()}
        assert wh["id"] in master, "layar master tetap melihat gudang uji"
        tasks = requests.get(f"{API}/wms/tasks", headers=H(tok["admin"], "all"), timeout=60).json()
        assert all(t.get("warehouse_id") != wh["id"] for t in tasks), "tugas gudang uji tampil di 'semua lokasi'"
        ents = {e["id"] for e in requests.get(f"{API}/entities", headers=H(tok["admin"]), timeout=30).json()}
        assert ent["id"] not in ents
        login = requests.post(f"{API}/auth/login", json={"email": ACC["admin"], "password": PW}, timeout=30).json()
        assert ent["id"] not in login["entity_context"]["allowed_entity_ids"]
    finally:
        db.warehouses.update_one({"id": wh["id"]}, {"$unset": {"is_test": ""}})
        db.business_entities.update_one({"id": ent["id"]}, {"$unset": {"is_test": ""}})


# ─── G-SCOPE-01 — sapuan GET /{id} WMS-RFID dengan id milik PT & lokasi lain ───
SWEEP = {
    # prefix path → (koleksi, saringan dokumen ASING bagi petugas Soreang/Kanda)
    "/api/wms/tasks/": ("wms_tasks", {"entity_id": KSC, "warehouse_id": JKT}),
    "/api/inbound/tasks/": ("wms_tasks", {"entity_id": KSC, "warehouse_id": JKT, "flow_type": "inbound"}),
    "/api/inbound/qc/tasks/": ("wms_tasks", {"entity_id": KSC, "warehouse_id": JKT, "flow_type": "inbound"}),
    "/api/outbound/tasks/": ("wms_tasks", {"entity_id": KSC, "warehouse_id": JKT, "flow_type": "outbound"}),
    "/api/putaway-orders/": ("putaway_orders", {"owner_entity_id": KSC}),
    "/api/transfers/": ("warehouse_transfers", {"entity_id": KSC, "source_warehouse_id": JKT, "dest_warehouse_id": JKT}),
    "/api/rfid/rolls/": ("inventory_rolls", {"owner_entity_id": KSC, "warehouse_id": JKT}),
    "/api/rfid/roll-scans/": ("inventory_rolls", {"owner_entity_id": KSC, "warehouse_id": JKT}),
    "/api/rfid/print-jobs/": ("rfid_print_jobs", {"owner_entity_id": KSC}),
    "/api/goods-receipts/": ("goods_receipts", {"entity_id": KSC, "warehouse_id": JKT}),
    "/api/logistics/deliveries/": ("logistics_deliveries", {"entity_id": KSC}),
    "/api/inventory/rolls/": ("inventory_rolls", {"owner_entity_id": KSC, "warehouse_id": JKT}),
    "/api/warehouses/": ("warehouses", {"id": JKT}),
    "/api/inspections/": ("inspections", {"entity_id": KSC}),
}
SKIP_SWEEP = {
    # endpoint publik/master yang SENGAJA tidak berpagar lokasi — alasan dicatat
    "/api/warehouses/{warehouse_id}/gate-policy": "kebijakan gate gedung = konfigurasi, dibaca semua pemakai gedung",
    "/api/goods-receipts/dn-profiles/{partner_id}": "param = id MITRA (bukan dokumen); profil dibaca per PT AKTIF pemanggil",
}


def test_g_scope_01_sweep_get_by_id(tok, db):
    spec = requests.get(f"{BASE}/openapi.json", timeout=60).json()
    checked, leaks = [], []
    for path, ops in spec.get("paths", {}).items():
        if "get" not in ops or path in SKIP_SWEEP:
            continue
        params = re.findall(r"{([^}]+)}", path)
        prefix = next((p for p in SWEEP if path.startswith(p)), None)
        if len(params) != 1 or not prefix:
            continue
        if any(p.get("required") and p.get("in") == "query" for p in ops["get"].get("parameters", [])):
            continue
        coll, flt = SWEEP[prefix]
        doc = db[coll].find_one(flt, {"_id": 0, "id": 1})
        if not doc:
            continue
        url = BASE + path.replace("{" + params[0] + "}", doc["id"])
        r = requests.get(url, headers=H(tok["soreang"]), timeout=60)
        checked.append(path)
        if r.status_code not in PROTECTED:
            leaks.append(f"{path} → {r.status_code}")
    assert len(checked) >= 10, f"sapuan terlalu sedikit: {checked}"
    assert not leaks, "endpoint /{id} membuka dokumen PT/lokasi lain:\n" + "\n".join(leaks)


# ─── B1b UI-44 — sesi: Bearer diutamakan, logout & login mencabut sesi lama ────
def _fresh_token(email):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": PW}, timeout=30).json()["token"]


class TestUi44Session:
    def test_bearer_wins_over_stale_cookie(self, tok):
        old = _fresh_token(ACC["admin"])
        me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok['jkt']}"},
                          cookies={"session_token": old}, timeout=30)
        assert me.status_code == 200 and me.json()["email"] == ACC["jkt"], "cookie sesi lama mengalahkan Bearer akun baru"

    def test_logout_revokes_bearer_and_cookie(self):
        a, b = _fresh_token(ACC["admin"]), _fresh_token(ACC["jkt"])
        r = requests.post(f"{API}/auth/logout", headers={"Authorization": f"Bearer {b}"}, cookies={"session_token": a}, timeout=30)
        assert r.status_code == 200
        for t in (a, b):
            assert requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {t}"}, timeout=30).status_code == 401

    def test_login_revokes_previous_cookie_session(self):
        old = _fresh_token(ACC["admin"])
        r = requests.post(f"{API}/auth/login", json={"email": ACC["jkt"], "password": PW}, cookies={"session_token": old}, timeout=30)
        assert r.status_code == 200
        assert requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {old}"}, timeout=30).status_code == 401


# ─── B1b UI-56 / UI-47 — data & menu mengikuti izin ────────────────────────────
def test_ui56_driver_cannot_read_so_tracker(tok):
    r = requests.get(f"{API}/desks/so-tracker", params={"desk": "me"}, headers=H(tok["driver"]), timeout=30)
    assert r.status_code == 403, f"sopir membaca pelacak SO (nilai Rupiah): {r.status_code}"


def test_ui47_logistics_menu_follows_logistics_permission(tok):
    me = requests.get(f"{API}/auth/me", headers=H(tok["whadmin"]), timeout=30).json()
    assert (me.get("view_resources") or {}).get("logistics") == ["logistics"], \
        f"menu Pengiriman terbuka lewat izin lain: {(me.get('view_resources') or {}).get('logistics')}"
