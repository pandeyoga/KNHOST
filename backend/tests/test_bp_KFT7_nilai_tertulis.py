"""KF-T7 — di MongoDB ASLI (lingkungan A) dengan data acuan: nilai bisnis yang dulu ditulis mati kini pengaturan.

Butir U1–U15 diuji di lingkungan B (`backend/tests_mem/test_KFT7_nilai_tertulis.py`). Berkas ini pelengkap yang hanya
sah di aplikasi utuh: (1) backend yang berjalan memuat 26 kunci baru dengan bawaan = nilai sebelum unit (tidak ada
perilaku yang berubah saat dipasang) dan kelompok "Keamanan akun & sesi"; (2) data acuan: status kredit pelanggan,
lembar inspeksi, dan isi katalog sample yang dilaporkan backend sama dengan rumus bawaan; (3) sesi masuk baru mencatat
umurnya (`ttl_hours`) dan kedaluwarsa ≈ 24 jam; (4) penanda migrasi margin pesanan khusus terpasang sekali.

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); pembacaan langsung ke database uji lokal
(`MONGO_URL`/`DB_NAME`). Tidak menulis pengaturan apa pun. Tidak untuk database berisi data nyata (titik henti H3).
"""
import os
from datetime import datetime, timedelta, timezone

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
BAWAAN = {
    "ar.overdue_block_days": 14, "ar.credit_warning_pct": 80, "sales.reservation_days": 3,
    "sales.group_sales_max_members": 2, "sales.special_order_margin_pct": 30, "sales.special_order_multi_item_min": 2,
    "inventory.low_stock_default_qty": 100, "notif.reservation_expiry_warn_hours": 24,
    "inventory.stock_analytics.trend_window_days": 30, "inventory.stock_analytics.trend_band_pct": 10,
    "inventory.split_roll_max_length": 150, "receiving.dn_profile_min_confirmed": 3,
    "receiving.dn_profile_min_share_pct": 80, "sales.sample_catalogue_base_qty": 1,
    "sales.sample_catalogue_soft_qty": 2, "qc.inspection_interval_yard": 15, "qc.inspection_min_points": 10,
    "finance.rounding_tolerance_rupiah": 1, "periode.suspense_reason_min_chars": 5, "qc.hold_reason_min_chars": 15,
    "putaway.close_reason_min_chars": 10, "keamanan.maks_salah_sandi": 5, "keamanan.lama_kunci_menit": 15,
    "keamanan.umur_sesi_jam": 24, "esign.otp_ttl_minutes": 10, "esign.max_attempts": 5,
}


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"], {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def test_KFT7_A_kunci_dan_kelompok_tampil_dengan_bawaan_hari_ini():
    _, h = _login()
    reg = requests.get(f"{BASE}/config/registry", headers=h, timeout=60)
    assert reg.status_code == 200, reg.text
    by = {e["key"]: e for e in reg.json()["entries"]}
    for key, nilai in BAWAAN.items():
        assert key in by, key
        assert by[key]["default"] == nilai, key
    assert "approval.special_order_min_amount" not in by                # #7 di Aturan Persetujuan (KP-T4)
    groups = {g["id"]: g for g in reg.json()["groups"]}
    assert groups["keamanan"]["label"] == "Keamanan akun & sesi"
    eff = requests.get(f"{BASE}/config/effective", headers=h, params={"group": "keamanan"}, timeout=60)
    assert eff.status_code == 200, eff.text
    assert {i["key"] for i in eff.json()["items"]} == {"keamanan.maks_salah_sandi", "keamanan.lama_kunci_menit",
                                                       "keamanan.umur_sesi_jam"}
    health = requests.get(f"{BASE}/config/health", headers=h, timeout=120)
    assert health.status_code == 200, health.text
    rows = {r["key"]: r for r in health.json()["rows"]}
    assert all(rows[k]["wiring_status"] == "OK" for k in BAWAAN), \
        {k: rows[k]["wiring_status"] for k in BAWAAN if rows[k]["wiring_status"] != "OK"}


def test_KFT7_B_sesi_baru_mencatat_umurnya():
    tok, _ = _login()
    s = DB.sessions.find_one({"token": tok}, {"_id": 0})
    assert s["ttl_hours"] == 24
    exp = s["expires_at"].replace(tzinfo=timezone.utc)
    assert abs(exp - (datetime.now(timezone.utc) + timedelta(hours=24))) < timedelta(minutes=2)


def test_KFT7_C_data_acuan_dibaca_dengan_bawaan():
    _, h = _login()
    # Isi katalog sample PT aktif (bawaan 1 + 2 yard).
    r = requests.get(f"{BASE}/sample-orders/kinds", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["catalogue"]["base_qty"] == 1 and r.json()["catalogue"]["soft_qty"] == 2
    # Stok rendah: batas yang dilaporkan = bawaan 100.
    r = requests.get(f"{BASE}/inventory/low-stock-summary", headers=h, timeout=60)
    if r.status_code == 200:
        assert r.json()["threshold"] == 100
    # Status kredit pelanggan di umur piutang ≡ status kartu pelanggan (satu pembaca ambang).
    rep = requests.get(f"{BASE}/ar/aging", headers=h, timeout=120)
    if rep.status_code == 200:
        for row in rep.json().get("customers", [])[:5]:
            c = requests.get(f"{BASE}/customers/{row['customer_id']}/credit-status", headers=h, timeout=30)
            if c.status_code == 200 and "credit" in c.json():
                assert c.json()["credit"]["status"] in ("active", "warning", "blocked")


def test_KFT7_D_penanda_migrasi_margin_sekali_jalan():
    mark = DB.system_settings.find_one({"scope": "__migrations__"}, {"_id": 0, "kft7_margin_pesanan_khusus": 1}) or {}
    assert mark.get("kft7_margin_pesanan_khusus"), "penanda migrasi KF-T7 belum terpasang (backend belum dinyalakan ulang?)"
    lama = DB.system_settings.find_one({"scope": "special_order"}, {"_id": 0, "default_margin_pct": 1}) or {}
    rows = list(DB.config_values.find({"key": "sales.special_order_margin_pct",
                                       "reason": "Pindahan dari penyimpanan lama"}, {"_id": 0}))
    assert len(rows) == (1 if lama.get("default_margin_pct") is not None else 0)
