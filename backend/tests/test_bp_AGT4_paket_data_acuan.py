"""AG-T4 — di MongoDB ASLI (lingkungan A) dengan data acuan: paket tutup buku bulan lalu = angka layar, 12 lembar, indeks.

    docker compose -f docker-compose.dev.yml exec backend python -m pytest /app/backend/tests/test_bp_AGT4_paket_data_acuan.py -q

Butir U1–U15 diuji di lingkungan B (`backend/tests_mem/test_AGT4_paket.py`, `test_AGT4_ringkasan_pagi.py`). Berkas ini
pelengkap uji jalan layar U16 (dipotret integrator): di data acuan (`scripts/dev_restore_demo.sh`) paket bulan lalu untuk
`ent_ksc` memuat 12 lembar, Laba-Rugi-nya sama dengan `GET /api/finance/income-statement` bulan itu, unduhan Excel 12
lembar, dan indeks `ai_finance_packs.uq_id` terpasang. Sakelar Asisten Keuangan admin dinyalakan sementara lewat API dan
dipulihkan; paket uji dihapus sesudahnya. Tanpa penyedia model (ringkasan otomatis). Tidak untuk data nyata (H3).
"""
import calendar
import datetime
import io
import os

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}, r.json().get("user") or {}


def _bulan_lalu():
    hari = (datetime.datetime.utcnow() + datetime.timedelta(hours=7)).date().replace(day=1) - datetime.timedelta(days=1)
    akhir = calendar.monthrange(hari.year, hari.month)[1]
    return f"{hari.year}-{hari.month:02d}", f"{hari.year}-{hari.month:02d}-01", f"{hari.year}-{hari.month:02d}-{akhir:02d}"


def test_bp_AGT4_paket_bulan_lalu_data_acuan():
    from openpyxl import load_workbook
    h, me = _login()
    uid = me.get("id") or DB.users.find_one({"email": "admin@kainnusantara.id"})["id"]
    semula = bool(((DB.users.find_one({"id": uid}) or {}).get("ai_finance") or {}).get("enabled"))
    period, start, end = _bulan_lalu()
    pack = None
    try:
        r = requests.patch(f"{BASE}/users/{uid}", headers=h, json={"data": {"ai_finance": {"enabled": True}}}, timeout=30)
        assert r.status_code == 200, r.text
        r = requests.post(f"{BASE}/ai/finance/closing-pack", headers=h, json={"period": period}, timeout=600)
        assert r.status_code == 200, r.text
        pack = r.json()
        assert [s["title"] for s in pack["sections"]] == [
            "Ringkasan", "Laba-Rugi", "Neraca", "Arus Kas", "Umur Piutang", "Umur Hutang", "Pencocokan", "Antar-PT",
            "Kas & Bank", "Posting Gagal", "Jurnal Manual", "Status Periode"]
        assert all(s["status"] == "ok" for s in pack["sections"]), pack["sections"]   # admin memegang semua izin sumber
        doc = requests.get(f"{BASE}/ai/finance/closing-pack/{pack['id']}", headers=h, timeout=60).json()
        lr = doc["results"][next(s["result_id"] for s in doc["sections"] if s["key"] == "laba_rugi")]
        layar = requests.get(f"{BASE}/finance/income-statement", headers=h, params={"start": start, "end": end},
                             timeout=60).json()
        assert lr["totals"]["net_income"] == round(float(layar["net_income"]), 2)
        x = requests.get(f"{BASE}/ai/finance/closing-pack/{pack['id']}/export.xlsx", headers=h, timeout=120)
        assert x.status_code == 200, x.text
        wb = load_workbook(io.BytesIO(x.content))
        assert len(wb.sheetnames) == 12 and pack["period_label"] in str(wb["Ringkasan"]["A1"].value)
        info = DB.ai_finance_packs.index_information()
        assert "uq_id" in info and info["uq_id"].get("unique"), sorted(info)
    finally:
        requests.patch(f"{BASE}/users/{uid}", headers=h, json={"data": {"ai_finance": {"enabled": semula}}}, timeout=30)
        if pack:
            DB.ai_finance_packs.delete_one({"id": pack["id"]})
