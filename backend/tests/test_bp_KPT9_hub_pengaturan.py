"""KP-T9 — di MongoDB ASLI (lingkungan A, data acuan): menu Pengaturan sembilan hub dari sisi server.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); peran uji dibuat lewat API lalu dihapus lagi.
Tidak untuk database berisi data nyata. Padanan lapis B: `backend/tests_mem/test_KPT9_hub_pengaturan.py` (U6–U9).
Uji jalan layar U13 (peramban: admin, manager, warehouse_admin, sales_admin, satu peran Tanpa Acuan bermodul SDM) terpisah.

U6   peran Tanpa Acuan modul SDM "Lihat saja" → menu memuat Pengaturan › SDM termasuk Mesin Absen; tanpa hub Sistem.
U7   modul Data PT saja → Perusahaan (PT) tanpa Pengguna & Hak Akses; modul Peran & Hak Akses saja → sebaliknya.
U9   `hidden_views` menerima `settings-accounts`, menolak id tak dikenal (400).
+    kesiapan PT data acuan: butir profil/akun menuju tab baru (`settings-pt-profile`, `settings-accounts`).
"""
import os

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
SANDI = "demo12345"


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def adm():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": SANDI}, timeout=30)
    assert r.status_code == 200, r.text
    return _h(r.json()["token"])


@pytest.fixture
def peran(adm):
    dibuat = []

    def _buat(levels, label):
        r = requests.post(f"{BASE}/access/roles", headers=adm, timeout=30, json={
            "label": label, "base_role": "", "description": "peran uji KP-T9 (lapis A)", "levels": levels})
        assert r.status_code == 200, r.text
        rid = (r.json().get("role") or r.json())["id"]
        dibuat.append(rid)
        lst = requests.get(f"{BASE}/roles", headers=adm, timeout=30).json()
        lst = lst["roles"] if isinstance(lst, dict) else lst
        nav = next(x for x in lst if x["id"] == rid)["nav"]
        return rid, set(nav["add"])
    yield _buat
    for rid in dibuat:
        requests.delete(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30)


def test_KPT9_U6_modul_sdm_mesin_absen(peran):
    _, add = peran({"hr": "view"}, "BP KPT9 SDM")
    assert {"settings-hub", "settings-hr", "settings-cfg-hr", "hr-attendance-setup", "settings-attendance-devices"} <= add
    assert not ({"settings-system", "settings-devices"} & add)


def test_KPT9_U7_modul_pt_dan_peran(peran):
    _, pt = peran({"entities": "view"}, "BP KPT9 PT")
    assert {"settings-company", "settings-pt-profile", "settings-pt-readiness"} <= pt and "settings-access" not in pt
    _, pr = peran({"roles": "view"}, "BP KPT9 Peran")
    assert {"settings-access", "permission-matrix", "settings-role-check"} <= pr and "settings-pt-profile" not in pr


def test_KPT9_U9_hidden_views(adm, peran):
    rid, _ = peran({"accounts": "view"}, "BP KPT9 Sembunyi")
    r = requests.patch(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30, json={"hidden_views": ["settings-accounts"]})
    assert r.status_code == 200, r.text
    r = requests.patch(f"{BASE}/access/roles/{rid}", headers=adm, timeout=30, json={"hidden_views": ["settings-tidak-ada"]})
    assert r.status_code == 400 and "tidak dikenal" in r.text, r.text


def test_KPT9_kesiapan_menuju_tab_baru(adm):
    r = requests.get(f"{BASE}/entities/ent_ksc/readiness", headers=adm, timeout=60)
    assert r.status_code == 200, r.text
    tujuan = {i["key"]: i.get("view") for i in r.json()["items"]}
    assert tujuan["address"] == "settings-pt-profile" and tujuan["users"] == "settings-accounts"
