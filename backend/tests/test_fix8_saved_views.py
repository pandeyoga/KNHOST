"""FIX-8 (audit WMS-RFID 9 Nov 2026 · K-B4-12 = YA) — TAMPILAN TERSIMPAN daftar utama gudang (`/api/saved-views`).

Uji HTTP terhadap server hidup (stack sementara, salinan DB data acuan 8 Nov). Menjaga:
  * CRUD pribadi: simpan · daftar · ubah · bawaan (satu per pengguna per daftar) · hapus; tampilan pribadi orang lain
    tidak terbaca/diubah (404, keberadaannya tidak bocor).
  * Isi di-whitelist per daftar; kunci CAKUPAN (PT/lokasi kerja — FIX-1) ditolak 400 → tampilan tidak bisa memperluas
    data yang terlihat. Badan permintaan dengan kunci asing → 422 (`extra="forbid"`).
  * Izin = izin LIHAT daftarnya (peran tanpa `transfer.view` → 403); berbagi ke peran/PT hanya admin; PT tujuan harus
    PT yang bisa dibaca admin; penerima = peran cocok DAN PT yang ia baca beririsan; tampilan bersama hanya diubah admin.
  * Bawaan: pribadi menang atas bawaan bersama; mode "Semua Entitas" boleh menyimpan (preferensi, bukan dokumen PT).
Pelaksana: `cd /app/backend && KN_DEMO_PW=<sandi demo> python -m pytest -q -p no:cacheprovider -n0 tests/test_fix8_saved_views.py`.
"""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
PW = os.environ.get("KN_DEMO_PW", "")
if not PW:
    pytest.skip("set KN_DEMO_PW (sandi akun demo data acuan) untuk menjalankan uji FIX-8", allow_module_level=True)
ACC = {"admin": "admin@kainnusantara.id", "jkt": "warehouse@kainnusantara.id",
       "soreang": "warehouse.soreang@kainnusantara.id", "whadmin": "wh.admin@kainnusantara.id",
       "sales": "sales@kainnusantara.id"}
LK = "wms.transfers"


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


def H(t, ent=None):
    h = {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}
    if ent:
        h["X-Entity-Id"] = ent
    return h


def lst(t, key=LK, **hdr):
    return requests.get(f"{API}/saved-views", params={"list_key": key}, headers=H(t, **hdr), timeout=30)


def create(t, body, **hdr):
    return requests.post(f"{API}/saved-views", json=body, headers=H(t, **hdr), timeout=30)


def put(t, vid, body):
    return requests.put(f"{API}/saved-views/{vid}", json=body, headers=H(t), timeout=30)


def delete(t, vid):
    return requests.delete(f"{API}/saved-views/{vid}", headers=H(t), timeout=30)


def nm(prefix="Uji"):
    return f"{prefix} {uuid.uuid4().hex[:6]}"


STATE = {"filters": {"status": "waiting_approval", "kind": "inter_entity"}, "sort": {"key": "created_at", "dir": "asc"},
         "columns": ["approved_by"], "mode": ""}


# ─── CRUD pribadi ──────────────────────────────────────────────────────────────────────────────────────────────
class TestPersonalCrud:
    def test_create_list_update_default_delete(self, tok, db):
        name = nm("Menunggu ACC")
        r = create(tok["jkt"], {"list_key": LK, "name": name, "state": STATE})
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["mine"] is True and v["shared"] is False and v["can_edit"] is True
        assert v["state"] == STATE
        doc = db.saved_views.find_one({"id": v["id"]}, {"_id": 0})
        assert doc and doc["owner_user_id"] and doc["list_key"] == LK and "entity_id" not in doc
        items = lst(tok["jkt"]).json()["items"]
        assert v["id"] in [x["id"] for x in items]
        # ubah nama & isi
        st2 = {**STATE, "filters": {"status": "approved"}}
        r = put(tok["jkt"], v["id"], {"name": name + " 2", "state": st2})
        assert r.status_code == 200 and r.json()["name"] == name + " 2" and r.json()["state"]["filters"] == {"status": "approved"}
        # bawaan: satu per pengguna per daftar
        v2 = create(tok["jkt"], {"list_key": LK, "name": nm(), "state": {}, "is_default": True}).json()
        assert lst(tok["jkt"]).json()["default_id"] == v2["id"]
        assert put(tok["jkt"], v["id"], {"is_default": True}).status_code == 200
        out = lst(tok["jkt"]).json()
        assert out["default_id"] == v["id"]
        assert [x for x in out["items"] if x["id"] == v2["id"]][0]["is_default"] is False
        # audit tercatat
        assert db.audit_logs.find_one({"entity_type": "saved_views", "entity_id": v["id"]})
        # hapus
        assert delete(tok["jkt"], v["id"]).status_code == 200
        assert delete(tok["jkt"], v2["id"]).status_code == 200
        assert v["id"] not in [x["id"] for x in lst(tok["jkt"]).json()["items"]]
        assert db.saved_views.find_one({"id": v["id"]}) is None

    def test_private_view_invisible_and_untouchable_for_others(self, tok):
        v = create(tok["jkt"], {"list_key": LK, "name": nm("Pribadi"), "state": STATE}).json()
        try:
            other = lst(tok["soreang"]).json()["items"]
            assert v["id"] not in [x["id"] for x in other]
            assert put(tok["soreang"], v["id"], {"name": "Diambil alih"}).status_code == 404
            assert delete(tok["soreang"], v["id"]).status_code == 404
            assert put(tok["soreang"], v["id"], {"is_default": True}).status_code == 404
        finally:
            delete(tok["jkt"], v["id"])

    def test_all_entities_mode_can_save_preference(self, tok):
        r = create(tok["admin"], {"list_key": LK, "name": nm("Gabungan"), "state": {}}, ent="all")
        assert r.status_code == 200, r.text   # bukan 409 pagar tulis "Semua Entitas" — preferensi pengguna
        delete(tok["admin"], r.json()["id"])


# ─── Whitelist isi & cakupan (FIX-1) ───────────────────────────────────────────────────────────────────────────
class TestStateWhitelist:
    @pytest.mark.parametrize("state, word", [
        ({"filters": {"entity_id": "ent_ksc"}}, "cakupan"),
        ({"filters": {"location_view": True}}, "cakupan"),
        ({"filters": {"site_id": "site_x"}}, "cakupan"),
        ({"filters": {"warehouse_id": "wh1"}}, "tidak dikenal"),      # bukan saringan daftar transfer
        ({"sort": {"key": "total_value", "dir": "asc"}}, "Urutan"),
        ({"sort": {"key": "code", "dir": "sideways"}}, "Urutan"),
        ({"columns": ["harga_pokok"]}, "Kolom"),
        ({"mode": "group"}, "Mode"),
        ({"filters": {"status": "x" * 201}}, "terlalu panjang"),
        ({"rahasia": 1}, "tidak dikenal"),
    ])
    def test_bad_state_rejected(self, tok, state, word):
        r = create(tok["jkt"], {"list_key": LK, "name": nm(), "state": state})
        assert r.status_code == 400, r.text
        assert word.lower() in r.json()["detail"].lower()

    def test_roll_list_accepts_own_keys_and_rejects_scope(self, tok):
        ok = create(tok["jkt"], {"list_key": "wms.inventory_rolls", "name": nm("Roll"),
                                 "state": {"filters": {"warehouse_id": "wh_x", "line": "WOV", "check": "no_mdq", "peg_only": True},
                                           "columns": ["owner", "pegging"], "mode": "group"}})
        assert ok.status_code == 200, ok.text
        delete(tok["jkt"], ok.json()["id"])
        bad = create(tok["jkt"], {"list_key": "wms.inventory_rolls", "name": nm(), "state": {"filters": {"owner_entity_id": "ent_ksc"}}})
        assert bad.status_code == 400 and "cakupan" in bad.json()["detail"]

    def test_name_and_list_key_validation(self, tok):
        assert create(tok["jkt"], {"list_key": LK, "name": "   ", "state": {}}).status_code == 400
        assert create(tok["jkt"], {"list_key": LK, "name": "x" * 61, "state": {}}).status_code == 400
        assert create(tok["jkt"], {"list_key": "keuangan.jurnal", "name": nm(), "state": {}}).status_code == 400
        assert lst(tok["jkt"], key="keuangan.jurnal").status_code == 400
        r = create(tok["jkt"], {"list_key": LK, "name": nm(), "state": {}, "owner_user_id": "orang_lain"})
        assert r.status_code == 422           # kunci asing ditolak (extra="forbid"), pemilik selalu dari sesi


# ─── Izin & berbagi ke peran/PT ────────────────────────────────────────────────────────────────────────────────
class TestPermissionsAndSharing:
    def test_list_permission_required(self, tok):
        assert lst(tok["sales"]).status_code == 403                    # sales tanpa transfer.view
        assert create(tok["sales"], {"list_key": LK, "name": nm(), "state": {}}).status_code == 403
        assert lst(tok["sales"], key="wms.inventory_rolls").status_code == 200   # product.view ada

    def test_only_admin_can_share(self, tok):
        r = create(tok["jkt"], {"list_key": LK, "name": nm(), "state": {}, "share": {"roles": ["warehouse"]}})
        assert r.status_code == 403 and "admin" in r.json()["detail"]
        r = create(tok["whadmin"], {"list_key": LK, "name": nm(), "state": {}, "share": {"roles": ["warehouse"]}})
        assert r.status_code == 403

    def test_role_share_visible_readonly_and_shared_default(self, tok):
        v = create(tok["admin"], {"list_key": LK, "name": nm("Bersama gudang"), "state": STATE,
                                  "share": {"roles": ["warehouse"], "is_default": True}}).json()
        try:
            for who in ("jkt", "soreang"):
                out = lst(tok[who]).json()
                mine = [x for x in out["items"] if x["id"] == v["id"]]
                assert mine and mine[0]["shared"] and mine[0]["applies_to_me"] and not mine[0]["can_edit"]
            assert v["id"] not in [x["id"] for x in lst(tok["whadmin"]).json()["items"]]   # peran lain
            assert put(tok["jkt"], v["id"], {"name": "Diubah gudang"}).status_code == 403
            assert delete(tok["jkt"], v["id"]).status_code == 403
            # bawaan bersama berlaku bila belum ada bawaan pribadi; bawaan pribadi menang
            assert lst(tok["soreang"]).json()["default_id"] == v["id"]
            own = create(tok["soreang"], {"list_key": LK, "name": nm("Milik"), "state": {}, "is_default": True}).json()
            assert lst(tok["soreang"]).json()["default_id"] == own["id"]
            delete(tok["soreang"], own["id"])
            assert put(tok["admin"], v["id"], {"name": v["name"] + " (ubah admin)"}).status_code == 200
        finally:
            delete(tok["admin"], v["id"])

    def test_pt_share_respects_entity_access(self, tok, db):
        u = db.users.find_one({"email": ACC["jkt"]}, {"_id": 0, "allowed_entity_ids": 1, "home_entity_id": 1})
        mine = set(u.get("allowed_entity_ids") or ([u["home_entity_id"]] if u.get("home_entity_id") else []))
        others = [e["id"] for e in db.business_entities.find({"status": {"$nin": ["archived", "closed"]}}, {"_id": 0, "id": 1})
                  if e["id"] not in mine]
        assert mine, "akun gudang Jakarta tanpa PT di data acuan"
        own_pt = sorted(mine)[0]
        v_in = create(tok["admin"], {"list_key": LK, "name": nm("PT sendiri"), "state": {},
                                     "share": {"entity_ids": [own_pt]}}).json()
        try:
            assert v_in["id"] in [x["id"] for x in lst(tok["jkt"]).json()["items"]]
            if others:
                v_out = create(tok["admin"], {"list_key": LK, "name": nm("PT lain"), "state": {},
                                              "share": {"entity_ids": [others[0]]}}).json()
                try:
                    assert v_out["id"] not in [x["id"] for x in lst(tok["jkt"]).json()["items"]]
                    adm = [x for x in lst(tok["admin"]).json()["items"] if x["id"] == v_out["id"]]
                    assert adm and adm[0]["can_edit"]                      # admin melihat & mengelola semua tampilan bersama
                finally:
                    delete(tok["admin"], v_out["id"])
        finally:
            delete(tok["admin"], v_in["id"])
        r = create(tok["admin"], {"list_key": LK, "name": nm(), "state": {}, "share": {"entity_ids": ["ent_tidak_ada"]}})
        assert r.status_code == 403
        r = create(tok["admin"], {"list_key": LK, "name": nm(), "state": {}, "share": {"roles": ["peran_fiktif"]}})
        assert r.status_code == 400
