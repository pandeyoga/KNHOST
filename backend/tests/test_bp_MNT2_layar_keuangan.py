"""MN-T2 — di MongoDB ASLI (lingkungan A, data acuan): daftar kerja Kas Kecil dan tautan daftar periksa tutup buku.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`), hanya MEMBACA (tidak menulis data). Padanan
lapis B (angka dari fixture): `backend/tests_mem/test_MNT2_layar_keuangan.py` (U3–U8, U11). Uji jalan layar U16/U17
(peramban) terpisah.

U3  admin: `GET /api/petty-cash/worklist` 200; `total` = Σ `stage_counts` (tanpa saringan); tiap baris bertahap dikenal;
    jumlah per tahap = jumlah baris saringan tahap itu (halaman besar).
U7  `?stage=aneh` → 400 "Tahap tidak dikenal."
U6  akun seed sopir (driver@) → 403.
U8  daftar periksa bulan lalu: butir `suspense_nol` dan `stok_cocok` menunjuk `closing` + `preset.seksi`.
"""
import datetime
import os

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
SANDI = "demo12345"
TAHAP = {"diajukan", "dicairkan", "dipertanggungjawabkan", "selesai"}


def _login(email="admin@kainnusantara.id", password=SANDI):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def adm():
    return _h(_login()["token"])


def test_bp_MNT2_U3_worklist_admin(adm):
    r = requests.get(f"{BASE}/petty-cash/worklist", headers=adm, params={"page_size": 100}, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j["stage_counts"]) == TAHAP
    assert j["total"] == sum(j["stage_counts"].values())
    assert all(x["stage"] in TAHAP for x in j["items"])
    for st, n in j["stage_counts"].items():
        rs = requests.get(f"{BASE}/petty-cash/worklist", headers=adm, params={"stage": st, "page_size": 1}, timeout=60)
        assert rs.status_code == 200 and rs.json()["total"] == n, (st, rs.text)


def test_bp_MNT2_U7_tahap_aneh(adm):
    r = requests.get(f"{BASE}/petty-cash/worklist", headers=adm, params={"stage": "aneh"}, timeout=30)
    assert r.status_code == 400 and r.json()["detail"] == "Tahap tidak dikenal.", r.text


def test_bp_MNT2_U6_sopir_ditolak():
    try:
        tok = _login("driver@kainnusantara.id")["token"]
    except AssertionError:
        pytest.skip("akun seed driver@ tidak ada di data acuan ini")
    r = requests.get(f"{BASE}/petty-cash/worklist", headers=_h(tok), timeout=30)
    assert r.status_code == 403, r.text


def test_bp_MNT2_U8_tautan_daftar_periksa(adm):
    hari = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
    r = requests.get(f"{BASE}/finance/closing/checklist", headers=adm, timeout=120,
                     params={"period_type": "month", "period_key": hari.strftime("%Y-%m"), "entity_id": "ent_ksc"})
    assert r.status_code == 200, r.text
    butir = {it["key"]: it for it in r.json()["items"]}
    assert butir["suspense_nol"]["link"] == {"view": "closing", "preset": {"seksi": "akun-sementara"}}
    assert butir["stok_cocok"]["link"] == {"view": "closing", "preset": {"seksi": "persediaan"}}
    assert butir["posting_gagal"]["link"]["view"] == "posting-failures"
    assert butir["buka_periode_aktif"]["link"]["view"] == "period-unlock"
