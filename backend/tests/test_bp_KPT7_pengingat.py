"""KP-T7 — di MongoDB ASLI (lingkungan A) dengan data acuan: penjadwal & pengingat yang bisa diatur.

Butir U1–U13 diuji di lingkungan B (`backend/tests_mem/test_KPT7_*.py`). Berkas ini pelengkap yang hanya sah di aplikasi
utuh: (1) backend yang berjalan melaporkan satuan & selang yang dipakai, penerima, dan ambang tiap job, dan menolak
selang yang salah satuan tanpa mengubah dokumen `system_settings{scope:"alerts"}`; (2) skrip
`scripts/migrate_kpt7_jadwal.py` mode lapor di data acuan tidak mengubah dokumen itu (keluaran dicetak, `-s`, untuk
laporan unit); (3) 19 kunci baru tampil di Pusat Pengaturan dengan bawaan = perilaku sebelum unit.

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); pembacaan langsung ke database uji lokal
(`MONGO_URL`/`DB_NAME`). Tidak menulis pengaturan apa pun. Tidak untuk database berisi data nyata (menjalankan skrip di
data nyata = titik henti H3).
"""
import os
import subprocess
import sys
from pathlib import Path

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ROOT = Path(__file__).resolve().parents[2]
BAWAAN = {"notif.ap_due_soon_days": 7, "notif.wo_released_stale_days": 3, "notif.wo_draft_stale_days": 7,
          "notif.warehouse_task_stale_days": 2, "notif.ar_due_soon_offsets": [-3, -1, 0, 1],
          "notif.po_arrival_lookback_hours": 24, "notif.max_alerts_per_run": 40, "notif.turn_stale_days": 7,
          "notif.content_reminder_window_minutes": 60, "notif.content_on_time_grace_minutes": 60,
          "notif.campaign_budget_near_pct": 80, "notif.printer_stuck_minutes": 30,
          "inventory.drift_critical_multiplier": 10, "approval.reminder_max_listed": 3, "rnd.design_due_soon_days": 3,
          "notif.wa_broadcast_roles": ["admin", "manager"], "notif.wa_pic_number": ""}


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _alerts():
    return DB.system_settings.find_one({"scope": "alerts"}, {"_id": 0, "lock": 0, "updated_at": 0}) or {}


def test_KPT7_A_jobs_melaporkan_satuan_penerima_ambang_dan_menolak_satuan_salah():
    h = _login()
    sebelum = _alerts()
    rows = requests.get(f"{BASE}/scheduler/jobs", headers=h, timeout=60)
    assert rows.status_code == 200, rows.text
    jobs = {j["id"]: j for j in rows.json()["jobs"]}
    for j in jobs.values():
        assert j["interval_unit"] in ("menit", "jam", ""), j["id"]
        assert (j["interval_value"] is None) == (j["kind"] == "daily"), j["id"]
        assert j["schedule_label"].endswith(("menit", "jam", "WIB")), j["id"]
    assert jobs["reservation_expiry"]["interval_unit"] == "menit"
    assert {k for k, j in jobs.items() if j["locked"]} == {"rfid_reader_health_watch", "rfid_gate_txn_retry"}
    assert jobs["ap_due"]["recipients"] and jobs["ap_due"]["thresholds"][0]["key"] == "notif.ap_due_soon_days"
    for isi, pesan in (({"reservation_expiry": {"interval_hours": 2}}, "diatur dalam menit."),
                       ({"ops_stalled": {"interval_minutes": 10}}, "diatur dalam jam."),
                       ({"rfid_gate_txn_retry": {"interval_minutes": 5}}, "tidak bisa diubah dari layar.")):
        r = requests.put(f"{BASE}/scheduler/settings", headers=h, json={"jobs": isi}, timeout=30)
        assert r.status_code == 400 and r.json()["detail"].endswith(pesan), r.text
    assert _alerts() == sebelum


def test_KPT7_A_skrip_migrasi_mode_lapor_tidak_menulis():
    sebelum = _alerts()
    out = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_kpt7_jadwal.py")], capture_output=True,
                         text=True, timeout=120, env={**os.environ})
    print(out.stdout)
    assert out.returncode == 0, out.stderr
    assert "mode lapor" in out.stdout
    assert _alerts() == sebelum
    salah = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_kpt7_jadwal.py"), "--tulis"],
                           capture_output=True, text=True, timeout=60)
    assert salah.returncode == 2


def test_KPT7_A_kunci_baru_bawaan_perilaku_lama():
    h = _login()
    r = requests.get(f"{BASE}/config/effective", headers=h, params={"group": "notifikasi"}, timeout=60)
    assert r.status_code == 200, r.text
    nilai = {i["key"]: i for i in r.json()["items"]}
    for grup in ("keuangan-dasar", "persetujuan", "rnd"):
        g = requests.get(f"{BASE}/config/effective", headers=h, params={"group": grup}, timeout=60)
        assert g.status_code == 200, g.text
        nilai.update({i["key"]: i for i in g.json()["items"]})
    for key, bawaan in BAWAAN.items():
        assert nilai[key]["default"] == bawaan, key
    rows = nilai["notif.reminder_recipients"]["default"]
    assert {r["reminder"]: (r["mode"], r["roles"] or r["permission"]) for r in rows}["ar_due_soon"] == \
        ("izin", "ar_receipt.create")
