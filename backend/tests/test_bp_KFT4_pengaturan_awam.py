"""KF-T4 — di MongoDB ASLI (lingkungan A) dengan data acuan: 13 kelompok bersub-judul, id kelompok lama, pengembali nilai
yang wajib beralasan, cakupan grup ber-daftar PT, "Coba dulu" pajak/QC = mesin, dan padanan kata pencarian.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`:
PT `ent_ksc` PKP dan `ent_kanda` bukan PKP). Nilai yang ditulis dikembalikan (lapisan PT dicabut, grup ditulis ulang ke
nilai awalnya) di akhir tiap uji. Tidak untuk database berisi data nyata.
"""
import os

import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
KELOMPOK = ["penjualan", "pembayaran-pelanggan", "retur-koreksi", "pembelian", "penerimaan", "kualitas", "stok",
            "persetujuan", "pajak-pembukuan", "bank-kasus", "sdm", "rnd", "sistem",
            "keamanan"]   # KF-T7 — kelompok ke-14 "Keamanan akun & sesi"


def _login(email="admin@kainnusantara.id", ent="ent_ksc"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


@pytest.fixture(scope="module")
def adm():
    return _login()


def _efektif(h, key, entity_id="", **extra):
    r = requests.get(f"{BASE}/config/effective", headers=h, params={"q": key, "entity_id": entity_id, **extra}, timeout=30)
    assert r.status_code == 200, r.text
    return next(it for it in r.json()["items"] if it["key"] == key)


def _put(h, key, value, scope_type="global", scope_id="", reason="uji KF-T4 lapis A"):
    return requests.put(f"{BASE}/config/values", headers=h, timeout=30, json={"items": [
        {"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]})


def test_bp_KFT4_U3_U4_kelompok_dan_alias(adm):
    r = requests.get(f"{BASE}/config/registry", headers=adm, timeout=30)
    assert r.status_code == 200, r.text
    assert [g["id"] for g in r.json()["groups"]] == KELOMPOK
    sub = {g["id"]: {s["id"] for s in g["sections"]} for g in r.json()["groups"]}
    assert all(e["section"] in sub[e["group"]] for e in r.json()["entries"])
    r = requests.get(f"{BASE}/config/effective", headers=adm, params={"group": "uang-masuk"}, timeout=30)
    assert r.status_code == 200 and {i["group"] for i in r.json()["items"]} == {"pembayaran-pelanggan"}


def test_bp_KFT4_U5_U13_kembalikan_beralasan_dan_cakupan_grup(adm):
    awal = _efektif(adm, "tax.ppn_mode")["value"]
    try:
        assert _put(adm, "tax.ppn_mode", "included", "entity", "ent_kanda").status_code == 200
        it = _efektif(adm, "tax.ppn_mode", "ent_kanda", scope="global", group="pajak-pembukuan")
        assert it["value"] == awal
        assert any(o["entity_id"] == "ent_kanda" and o["value"] == "included" for o in it["entity_overrides"])
        body = {"key": "tax.ppn_mode", "scope_type": "entity", "scope_id": "ent_kanda"}
        r = requests.post(f"{BASE}/config/values/clear", headers=adm, json=body, timeout=30)
        assert r.status_code == 400 and "alasan wajib diisi" in r.json()["detail"]
    finally:
        requests.post(f"{BASE}/config/values/clear", headers=adm, timeout=30, json={
            "key": "tax.ppn_mode", "scope_type": "entity", "scope_id": "ent_kanda", "reason": "uji KF-T4 kembalikan"})
    assert _efektif(adm, "tax.ppn_mode", "ent_kanda")["source_layer"] != "entity"


def test_bp_KFT4_U8_U9_coba_dulu_sama_dengan_mesin(adm):
    r = requests.post(f"{BASE}/config/simulate", headers=adm, timeout=30, json={
        "key": "qc.grade_thresholds.a_max", "sample": {"points": 25},
        "overrides": {"qc.grade_thresholds.a_max": 20, "qc.grade_thresholds.b_max": 40}})
    assert r.status_code == 200, r.text
    assert r.json()["result"].startswith("Grade ")
    for ent, ppn in (("ent_ksc", 1_100_000.0), ("ent_kanda", 0.0)):
        r = requests.post(f"{BASE}/config/simulate", headers=adm, timeout=30, json={
            "key": "tax.ppn_rate", "ctx": {"entity_id": ent}, "sample": {"subtotal": 10_000_000},
            "overrides": {"tax.ppn_rate": 12, "tax.dpp_nilai_lain": True, "tax.ppn_mode": "excluded"}})
        assert r.status_code == 200, r.text
        assert r.json()["breakdown"]["ppn_amount"] == ppn, (ent, r.json())


def test_bp_KFT4_U12_padanan_kata(adm):
    def keys(q):
        r = requests.get(f"{BASE}/config/registry", headers=adm, params={"q": q}, timeout=30)
        assert r.status_code == 200, r.text
        return {e["key"] for e in r.json()["entries"]}
    assert keys("supplier") == keys("pemasok") and keys("supplier")
    assert keys("roll") == keys("gulungan") and keys("roll")
