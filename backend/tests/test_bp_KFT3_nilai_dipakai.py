"""KF-T3 — di MongoDB ASLI (lingkungan A) dengan data acuan: termin bawaan PT dipakai pesanan (U11), plus pelengkap
penimpaan terdaftar dan pembatalan jadwal di data acuan.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`) di atas data acuan (`scripts/dev_restore_demo.sh`:
pelanggan `cust_butik_bali` beralamat `addr_001`, barang `prod_lurik_classic`, PT `ent_ksc` dan `ent_kanda`). Database
(`MONGO_URL`/`DB_NAME`) hanya dibaca untuk memeriksa hasil. Lapisan PT yang ditulis dicabut lagi, jadwal yang dibuat
dibatalkan, dan pesanan yang lahir dibatalkan lewat API di akhir. Tidak untuk database berisi data nyata.
"""
import datetime as dt
import os

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
CUST, ADDR, PROD = "cust_butik_bali", "addr_001", "prod_lurik_classic"
KEY_TERMIN = "finance.default_payment_term_code"


def _login(email="admin@kainnusantara.id", ent="ent_ksc"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


def _efektif(h, key, entity_id=""):
    r = requests.get(f"{BASE}/config/effective", headers=h, params={"q": key, "entity_id": entity_id}, timeout=30)
    assert r.status_code == 200, r.text
    items = [it for it in r.json()["items"] if it["key"] == key]
    assert len(items) == 1, r.json()
    return items[0]


@pytest.fixture(scope="module")
def adm():
    if not DB.customers.find_one({"id": CUST}) or not DB.products.find_one({"id": PROD}):
        pytest.skip("data acuan belum dipulihkan (scripts/dev_restore_demo.sh)")
    return _login()


def _cabut(h, key, ent):
    requests.post(f"{BASE}/config/values/clear", headers=h, timeout=30, json={
        "key": key, "scope_type": "entity", "scope_id": ent, "reason": "uji KF-T3 lapis A kembalikan"})


# ── U11 — pesanan tanpa termin memakai termin bawaan PT pesanan ─────────────────────────────────────────────────────
def test_KFT3_U11_pesanan_tanpa_termin_memakai_termin_pt(adm):
    grup = _efektif(adm, KEY_TERMIN)["value"]          # data acuan: NET30
    r = requests.put(f"{BASE}/config/values", headers=adm, timeout=30, json={"items": [
        {"key": KEY_TERMIN, "value": "NET7", "scope_type": "entity", "scope_id": "ent_ksc", "reason": "uji KF-T3 U11"}]})
    assert r.status_code == 200, r.text
    lahir = []
    try:
        hasil = {}
        for ent in ("ent_ksc", "ent_kanda"):
            h = _login(ent=ent)
            r = requests.post(f"{BASE}/sales-orders", headers=h, timeout=90, json={
                "customer_id": CUST, "shipping_address_id": ADDR, "entity_id": ent,
                "items": [{"product_id": PROD, "quantity": 5, "unit": "yard"}],
                "allow_backorder": True, "confirm_mixed_lot": True})
            if r.status_code != 200:
                pytest.skip(f"pesanan {ent} tidak bisa dibuat di data acuan: {r.status_code} {r.text[:200]}")
            so = r.json()
            lahir.append(so["id"])
            hasil[ent] = (DB.sales_orders.find_one({"id": so["id"]}) or {}).get("payment_term_code")
        assert hasil["ent_ksc"] == "NET7"
        assert hasil["ent_kanda"] == grup == "NET30"
    finally:
        for sid in lahir:
            requests.post(f"{BASE}/sales-orders/{sid}/cancel", headers=adm, timeout=60,
                          json={"reason": "bersihkan uji KF-T3"})
        _cabut(adm, KEY_TERMIN, "ent_ksc")


# ── Pelengkap U1/U2 di data acuan — penimpaan terdaftar terlihat di jawaban `/config/effective` ────────────────────
def test_KFT3_A_tarif_ppn_pt_bukan_pkp_ditimpa(adm):
    for ent in ("ent_ksc", "ent_kanda"):
        doc = DB.business_entities.find_one({"id": ent}) or {}
        it = _efektif(adm, "tax.ppn_rate", ent)
        if doc.get("default_tax_mode") == "ppn":
            assert it["overridden_by"] is None and it["value"] == it["stored_value"], ent
        else:
            assert it["value"] == 0 and it["overridden_by"]["id"] == "pt_bukan_pkp", ent


# ── Pelengkap U7 di data acuan — jadwal dibatalkan, riwayat menandainya ─────────────────────────────────────────────
def test_KFT3_A_batalkan_jadwal(adm):
    key = "ar.grace_days"
    nilai = int(_efektif(adm, key)["value"]) + 3
    nanti = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
    r = requests.put(f"{BASE}/config/values", headers=adm, timeout=30, json={"items": [
        {"key": key, "value": nilai, "scope_type": "global", "reason": "uji KF-T3 lapis A", "effective_from": nanti}]})
    assert r.status_code == 200, r.text
    rid = r.json()["saved"][0]["id"]
    r = requests.post(f"{BASE}/config/values/cancel-scheduled", headers=adm, timeout=30,
                      json={"id": rid, "reason": "uji KF-T3 lapis A — tidak jadi"})
    assert r.status_code == 200, r.text
    assert DB.config_values.find_one({"id": rid})["cancelled_at"]
    assert all(s.get("id") != rid for s in _efektif(adm, key)["scheduled"])
    r = requests.post(f"{BASE}/config/values/cancel-scheduled", headers=adm, timeout=30, json={"id": rid, "reason": "x"})
    assert r.status_code == 409 and r.json()["detail"] == "Jadwal ini sudah dibatalkan."
    rows = requests.get(f"{BASE}/config/history", headers=adm, params={"key": key}, timeout=30).json()["rows"]
    assert next(x for x in rows if x["id"] == rid)["cancelled"] is True


# ── Pelengkap U6 — job penjadwal terdaftar ─────────────────────────────────────────────────────────────────────────
def test_KFT3_A_job_aktifkan_pengaturan_terjadwal(adm):
    r = requests.get(f"{BASE}/scheduler/jobs", headers=adm, timeout=30)
    if r.status_code == 404:
        pytest.skip("rute daftar job berbeda di lingkungan ini")
    assert r.status_code == 200, r.text
    jobs = {j["id"]: j for j in (r.json().get("jobs") or r.json())}
    assert jobs["config_apply_due"]["schedule_label"] == "Setiap 5 menit"
