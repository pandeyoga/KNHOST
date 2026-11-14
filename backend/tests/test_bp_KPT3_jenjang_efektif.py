"""KP-T3 — di MongoDB ASLI (lingkungan A) dengan data acuan: jenjang efektif = keputusan mesin, daftar tanpa `discount`,
dan skrip migrasi mode lapor tidak menulis apa pun.

Unit ini tidak punya butir uji lapis A wajib; berkas ini pelengkap untuk data acuan (`scripts/dev_restore_demo.sh`),
karena data acuan bisa memuat aturan lama (`owner`/`discount`) yang tidak ada di benih lingkungan B.
Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); pembacaan langsung ke database uji lokal
(`MONGO_URL`/`DB_NAME`). Tidak menulis data. Tidak untuk database berisi data nyata.
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
JT = 1_000_000
NILAI = (0, 1, 49_999_999, 50 * JT, 99_999_999, 100 * JT, 499_999_999, 500 * JT, 2_000 * JT)


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _peran_untuk(tiers, nilai):
    """Cermin `config_service.required_role_for`: tingkat pertama (urutan server) yang mencakup nilai."""
    for t in tiers:
        hi = t["max_amount"] if t["max_amount"] is not None else float("inf")
        if t["min_amount"] <= nilai < hi:
            return t["required_role"] or None
    return None


def test_KPT3_A_jenjang_efektif_sama_dengan_mesin():
    h = _login()
    for ent in ("ent_ksc", "ent_kanda"):
        r = requests.get(f"{BASE}/approval-rules/effective", headers=h, params={"entity_id": ent}, timeout=30)
        assert r.status_code == 200, r.text
        for dt in r.json()["doc_types"]:
            for nilai in NILAI:
                m = requests.get(f"{BASE}/settings/evaluate-approval", headers=h, timeout=30,
                                 params={"doc_type": dt["doc_type"], "amount": nilai, "entity_id": ent})
                assert m.status_code == 200, m.text
                assert _peran_untuk(dt["tiers"], nilai) == m.json()["required_role"], (ent, dt["doc_type"], nilai)


def test_KPT3_A_daftar_tanpa_diskon_dan_berlabel():
    r = requests.get(f"{BASE}/approval-rules", headers=_login(), timeout=30)
    assert r.status_code == 200, r.text
    for row in r.json():
        assert row["doc_type"] in ("sales_order", "purchase_order", "purchase_requisition"), row
        assert isinstance(row["role_known"], bool) and row["required_role_label"], row


def test_KPT3_A_skrip_migrasi_mode_lapor_tidak_menulis():
    sebelum = sorted((d["id"], d.get("required_role"), d.get("active"), d.get("updated_at"))
                     for d in DB.approval_rules.find({}, {"_id": 0}))
    hasil = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_kpt3_aturan_persetujuan.py")], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    assert "mode lapor" in hasil.stdout
    sesudah = sorted((d["id"], d.get("required_role"), d.get("active"), d.get("updated_at"))
                     for d in DB.approval_rules.find({}, {"_id": 0}))
    assert sesudah == sebelum
