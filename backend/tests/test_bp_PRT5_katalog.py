"""PR-T5 — di MongoDB ASLI (lingkungan A, data acuan): katalog izin dirapikan, modul akses dipecah. Pelengkap
`tests_mem/test_PRT5_*.py` untuk butir yang hanya sah di basis data asli: migrasi sekali jalan `prt5:katalog` pada matriks
tersimpan data acuan (operator `$addToSet`, tulisan bersarang `custom_roles.levels`), dan sesi lewat login sungguhan.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); hanya MEMBACA basis data uji lokal
(`MONGO_URL`/`DB_NAME`) kecuali satu akun + sesi Sopir yang disisipkan dan dihapus lagi. Tidak untuk data nyata.
"""
import datetime
import os
import uuid

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
DIHAPUS = {("esign", "manage"), ("finance_case", "admin"), ("interco", "update"), ("inventory", "create"),
           ("order", "print"), ("tax_invoice", "print"), ("template", "print"), ("template", "import"),
           ("template", "export"), ("uom", "import"), ("uom", "export"), ("transfer", "complete"),
           ("reports", "export"), ("sales_pov", "commercial")}
LIMA = ("accounts", "roles", "entities", "settings", "scheduler")


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def test_migrasi_tercatat_sekali_dan_matriks_bersih():
    rec = DB.permission_settings.find_one({"id": "default"})
    assert rec["migrations_applied"].count("prt5:katalog") == 1
    for bagian in ("matrix", "defaults_applied"):
        for rid, perms in (rec.get(bagian) or {}).items():
            assert "sales_pov" not in (perms or {}), (bagian, rid)
            for res, act in DIHAPUS:
                assert act not in ((perms or {}).get(res) or []), (bagian, rid, res, act)
    for c in DB.custom_roles.find({}, {"_id": 0, "id": 1, "levels": 1}):
        assert "admin" not in (c.get("levels") or {}) and "sales_profile" not in (c.get("levels") or {}), c["id"]
        assert set(LIMA) <= set(c.get("levels") or {}), c["id"]


def test_katalog_lima_modul_dan_kamus_label():
    adm = _login()
    mods = {m["id"]: m for m in requests.get(f"{BASE}/access/modules", headers=adm, timeout=30).json()["modules"]}
    assert "admin" not in mods and "sales_profile" not in mods
    assert all(mid in mods for mid in LIMA)
    assert mods["field_visibility"]["levels_available"] == ["none", "manage"]
    uid = f"usr_bp_prt5_{uuid.uuid4().hex[:6]}"
    now = datetime.datetime.now(datetime.timezone.utc)
    DB.users.insert_one({"id": uid, "name": "Uji PR-T5 Sopir", "email": f"{uid}@uji.id", "role": "driver",
                         "status": "active", "home_entity_id": "ent_ksc", "allowed_entity_ids": ["ent_ksc"],
                         "created_at": now.isoformat()})
    tok = "tok_bp_prt5_" + uuid.uuid4().hex
    DB.sessions.insert_one({"token": tok, "user_id": uid, "created_at": now,
                            "expires_at": now + datetime.timedelta(hours=2)})
    try:
        r = requests.get(f"{BASE}/access/labels", headers={"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"},
                         timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["resources"]["permission"] == "Peran & Hak Akses"
    finally:
        DB.sessions.delete_many({"user_id": uid})
        DB.users.delete_one({"id": uid})


def test_ringkasan_laporan_dijaga_izin_laporan():
    """Akun data acuan: Admin & Admin Sales memegang `reports.view`; Sales tidak (kecuali diubah Admin di data acuan)."""
    roles = {r["id"]: r for r in requests.get(f"{BASE}/access/roles", headers=_login(), timeout=30).json()["roles"]}
    sales_boleh = "view" in (roles["sales"]["permissions"].get("reports") or [])
    assert requests.get(f"{BASE}/reports/summary", headers=_login(), timeout=30).status_code == 200
    kode = requests.get(f"{BASE}/reports/summary", headers=_login("sales@kainnusantara.id"), timeout=30).status_code
    assert kode == (200 if sales_boleh else 403), kode
    kode = requests.get(f"{BASE}/reports/order-velocity", headers=_login("sales@kainnusantara.id"), timeout=30)
    assert kode.status_code == 200, kode.text
