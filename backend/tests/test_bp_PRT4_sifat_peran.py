"""PR-T4 — di MongoDB ASLI (lingkungan A, data acuan): sifat peran (cakupan data, kategori kerja, halaman awal,
alamat notifikasi). Pelengkap `tests_mem/test_PRT4_*.py` untuk butir yang tidak sah di database tiruan: kueri `$in`
pada larik (`sales_team.sales_id`), migrasi sekali jalan pada data acuan, dan sesi yang melewati `current_user` asli.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); akun, sesi, karyawan, unit organisasi, dan
pelanggan uji disisipkan langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) dan dihapus lagi; peran uji dibuat dan
dihapus lewat API. Tidak untuk database berisi data nyata.
"""
import datetime
import os
import uuid

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KPI_ROLES = ("admin", "manager", "sales_admin", "finance")
MILIK_SENDIRI = {"sales", "driver", "designer"}
KATEGORI = {"sales": "sales", "driver": "sopir", "designer": "desainer", "warehouse": "gudang", "admin": "pengawas",
            "manager": "pengawas"}


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _akun(rid, tag):
    uid = f"usr_bp_prt4_{tag}_{uuid.uuid4().hex[:6]}"
    now = datetime.datetime.now(datetime.timezone.utc)
    DB.users.insert_one({"id": uid, "name": f"Uji PR-T4 {tag}", "email": f"{uid}@uji.id", "role": rid,
                         "status": "active", "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
                         "created_at": now.isoformat()})
    tok = "tok_bp_prt4_" + uuid.uuid4().hex
    DB.sessions.insert_one({"token": tok, "user_id": uid, "created_at": now,
                            "expires_at": now + datetime.timedelta(hours=2)})
    return uid, {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


def test_migrasi_tercatat_sekali():
    rec = DB.permission_settings.find_one({"id": "default"})
    for mid in ("prt4:sifat-peran", "prt4:izin-kpi-sales"):
        assert rec["migrations_applied"].count(mid) == 1, mid
    for rid in KPI_ROLES:
        acts = (rec["matrix"].get(rid) or {}).get("order") or []
        assert "view" not in acts or "view_sales_kpi" in acts, rid


def test_sifat_bawaan_peran_bawaan():
    adm = _login()
    roles = {r["id"]: r for r in requests.get(f"{BASE}/access/roles", headers=adm, timeout=30).json()["roles"]}
    for rid, r in roles.items():
        if r["custom"] or r["traits_overridden"]:
            continue   # data acuan bisa sudah diatur Admin
        assert r["traits"]["data_scope"] == ("milik_sendiri" if rid in MILIK_SENDIRI else "semua"), rid
        assert r["traits"]["kategori_kerja"] == KATEGORI.get(rid, ""), rid
        assert r["traits"]["notify_like"] == [], rid


def test_cakupan_tim_di_mongodb_asli():
    """Peran kustom "Sales Tim" (dasar Sales, cakupan tim): kepala unit melihat pelanggan anggota tim lewat PIC maupun
    anggota `sales_team` (kueri `$in` pada larik — tidak sah di database tiruan)."""
    adm = _login()
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"Sales Tim BP {uuid.uuid4().hex[:4]}", "base_role": "sales", "traits": {"data_scope": "tim"}})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    kepala, h_kepala = _akun(rid, "kepala")
    anggota, h_anggota = _akun(rid, "anggota")
    tag = uuid.uuid4().hex[:6]
    try:
        DB.hr_employees.insert_many([
            {"id": f"emp_bp_prt4_k_{tag}", "name": "Kepala BP", "user_id": kepala, "entity_id": "ent_ksc",
             "department_id": f"org_bp_prt4_{tag}", "status": "active"},
            {"id": f"emp_bp_prt4_a_{tag}", "name": "Anggota BP", "user_id": anggota, "entity_id": "ent_ksc",
             "department_id": f"org_bp_prt4_{tag}", "status": "active"}])
        DB.hr_org_units.insert_one({"id": f"org_bp_prt4_{tag}", "name": "Tim BP PR-T4", "unit_type": "department",
                                    "parent_id": "", "head_employee_id": f"emp_bp_prt4_k_{tag}",
                                    "entity_id": "ent_ksc"})
        DB.customers.insert_many([
            {"id": f"cust_bp_prt4_pic_{tag}", "name": "Pelanggan PIC anggota", "entity_id": "ent_ksc",
             "assigned_sales_id": anggota, "status": "active"},
            {"id": f"cust_bp_prt4_tim_{tag}", "name": "Pelanggan tim anggota", "entity_id": "ent_ksc",
             "assigned_sales_id": "usr_lain", "sales_team": [{"sales_id": anggota, "split_pct": 100}],
             "status": "active"}])

        def ids(h):
            res = requests.get(f"{BASE}/customers", headers=h, timeout=60)
            assert res.status_code == 200, res.text
            return {c["id"] for c in res.json()}

        mine = {f"cust_bp_prt4_pic_{tag}", f"cust_bp_prt4_tim_{tag}"}
        assert mine <= ids(h_kepala)
        assert mine <= ids(h_anggota)
        # Kepala kehilangan tim bila cakupan dikembalikan ke turunan (milik sendiri dari Sales).
        assert requests.patch(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30,
                              json={"traits": {"data_scope": None}}).status_code == 200
        assert not (mine & ids(h_kepala))
    finally:
        DB.customers.delete_many({"id": {"$regex": f"^cust_bp_prt4_.*_{tag}$"}})
        DB.hr_org_units.delete_many({"id": f"org_bp_prt4_{tag}"})
        DB.hr_employees.delete_many({"id": {"$regex": f"^emp_bp_prt4_.*_{tag}$"}})
        for uid in (kepala, anggota):
            DB.sessions.delete_many({"user_id": uid})
            DB.users.delete_one({"id": uid})
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)


def test_meja_saya_tanpa_kategori_404_manusia():
    adm = _login()
    r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
        "label": f"Tanpa Meja BP {uuid.uuid4().hex[:4]}", "permissions": {"customer": ["view"]}})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    uid, h = _akun(rid, "meja")
    try:
        r = requests.get(f"{BASE}/desks/me", headers=h, timeout=30)
        assert r.status_code == 404 and "cr_" not in r.text
    finally:
        DB.sessions.delete_many({"user_id": uid})
        DB.users.delete_one({"id": uid})
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)
