"""PR-T6 — di MongoDB ASLI (lingkungan A, data acuan): bagian server dari uji jalan U18/U19 dan butir yang hanya sah di
basis data asli (`docs/blueprint/unit/PR-T6.md`). Pelengkap `tests_mem/test_PRT6_*.py`:

- U18 (server): peran baru ber-peran dasar Sales + hak akses disalin dari Admin Sales → ringkasan "Milik sendiri" dan
  kalimat "bisa … tidak bisa …" per modul; menu tersembunyi tersimpan dalam satu panggilan pembuatan.
- U19 (server): peran kustom ber-`permission.view` saja → daftar & ringkasan & riwayat 200, simpan 403 berkalimat (tanpa
  kode izin) + header `X-Permission-Denied`.
- Riwayat peran dari selisih potret `before`/`after` di `audit_logs` asli (urut `timestamp` menurun).
- Ringkasan memakai `approval_policies` asli bila koleksinya berisi (KP-T4), selain itu `follows_rank_of`.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`). Menulis HANYA peran/akun/sesi uji berawalan
`PR-T6 Uji` / `usr_bp_prt6_` dan menghapusnya lagi. Tidak untuk data nyata.
"""
import datetime
import os
import re
import uuid

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KODE = re.compile(r"[a-z_]+\.[a-z_]+")


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _sesi_peran(rid):
    uid = f"usr_bp_prt6_{uuid.uuid4().hex[:6]}"
    now = datetime.datetime.now(datetime.timezone.utc)
    DB.users.insert_one({"id": uid, "name": "Uji PR-T6", "email": f"{uid}@uji.id", "role": rid, "status": "active",
                         "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"], "created_at": now.isoformat()})
    tok = "tok_bp_prt6_" + uuid.uuid4().hex
    DB.sessions.insert_one({"token": tok, "user_id": uid, "created_at": now, "expires_at": now + datetime.timedelta(hours=2)})
    return uid, {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


def _hapus_peran(adm, rid, uid=""):
    if uid:
        DB.sessions.delete_many({"user_id": uid})
        DB.users.delete_one({"id": uid})
    requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)


def test_U18_peran_dasar_terpisah_dari_salin_hak_akses():
    adm = _login()
    roles = {r["id"]: r for r in requests.get(f"{BASE}/access/roles", headers=adm, timeout=30).json()["roles"]}
    izin_admin_sales = roles["sales_admin"]["permissions"]
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"PR-T6 Uji {uuid.uuid4().hex[:4]}", "base_role": "sales", "permissions": izin_admin_sales,
        "hidden_views": ["finance-cases"]})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    try:
        p = r.json()
        assert p["base_role"] == "sales" and p["hidden_views"] == ["finance-cases"]
        assert {k: sorted(v) for k, v in p["permissions"].items()} == {k: sorted(v) for k, v in izin_admin_sales.items()}
        s = requests.get(f"{BASE}/access/roles/{rid}/summary", headers=adm, timeout=30)
        assert s.status_code == 200, s.text
        s = s.json()
        assert s["data_scope"]["label"] == "Milik sendiri"
        assert any(pg["can"] and pg["cannot"] for m in s["modules"] for pg in m["pages"])   # "bisa … tidak bisa …"
        assert any("mengikuti Sales" in t for t in s["follows_base"])
        punya_kebijakan = DB.approval_policies.count_documents({}) > 0
        assert isinstance(s["approvals"], list) if punya_kebijakan else s["approvals"] == {"follows_rank_of": "Sales"}
        # Ganti peran dasar: izin tetap, riwayat mencatat perubahannya.
        r = requests.patch(f"{BASE}/access/roles/{rid}", headers=adm, json={"base_role": "finance"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["permissions"] == p["permissions"]
        h = requests.get(f"{BASE}/access/roles/{rid}/history", headers=adm, timeout=30).json()["items"]
        assert [x["action"] for x in h][:2] == ["role_access_updated", "custom_role_created"]
        assert "Peran dasar: Sales → Finance" in h[0]["other"]
    finally:
        _hapus_peran(adm, rid)


def test_U19_peran_lihat_saja_mode_baca_server():
    adm = _login()
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"PR-T6 Uji Lihat {uuid.uuid4().hex[:4]}", "base_role": "", "permissions": {"permission": ["view"]}})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    uid, h = _sesi_peran(rid)
    try:
        assert requests.get(f"{BASE}/access/roles", headers=h, timeout=30).status_code == 200
        assert requests.get(f"{BASE}/access/roles/sales/summary", headers=h, timeout=30).status_code == 200
        assert requests.get(f"{BASE}/access/roles/sales/history", headers=h, timeout=30).status_code == 200
        r = requests.patch(f"{BASE}/access/roles/sales", headers=h, json={"levels": {"hr": "view"}}, timeout=30)
        assert r.status_code == 403, r.text
        assert not KODE.search(r.json()["detail"]) and "Permission" not in r.json()["detail"]
        assert r.headers.get("X-Permission-Denied") == "permission.update"
    finally:
        _hapus_peran(adm, rid, uid)
