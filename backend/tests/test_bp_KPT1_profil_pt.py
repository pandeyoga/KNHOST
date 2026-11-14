"""KP-T1 — di MongoDB ASLI (lingkungan A) dengan data acuan: profil PT jujur, status PKP tahan balapan, skrip migrasi
mode lapor tidak menulis.

Butir U1–U16 diuji di lingkungan B (`backend/tests_mem/test_KPT1_*.py`). Berkas ini pelengkap yang hanya sah di MongoDB
asli: (1) dua "Ubah status PKP" bersamaan atas PT yang sama → tepat satu berhasil (ubah bersyarat `default_tax_mode`;
database tiruan tidak menguji balapan, `00_ATURAN_EKSEKUSI.md` §9); (2) data acuan (`scripts/dev_restore_demo.sh`) yang
masih membawa isian mati tidak bocor ke jawaban; (3) skrip `scripts/migrate_kpt1_profil_pt.py` mode lapor di data acuan
tidak mengubah satu dokumen pun (keluaran dicetak, `-s`, untuk laporan unit).

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); pembacaan dan pembersihan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). PT uji dibuat lewat API lalu dihapus beserta lapisan pengaturan dan jejaknya. Tidak untuk
database berisi data nyata (menjalankan skrip di data nyata = titik henti H3).
"""
import datetime
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ROOT = Path(__file__).resolve().parents[2]
MATI = ("numbering_scheme", "incentive_payer", "coa_template", "fiscal_year_start", "parent_entity_id")


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _hari_ini_wib() -> str:
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=7)).date().isoformat()


def test_KPT1_A_jawaban_pt_tanpa_isian_mati_di_data_acuan():
    h = _login()
    rows = requests.get(f"{BASE}/entities", headers=h, params={"status": "all", "include_test": "true"}, timeout=30)
    assert rows.status_code == 200, rows.text
    for e in rows.json():
        assert not [k for k in MATI if k in e], e["id"]
        assert e["currency"] == e["base_currency"] and 1 <= e["fiscal_year_end_month"] <= 12, e["id"]
        assert 0 < e["ownership_pct"] <= 100, e["id"]


def test_KPT1_A_ubah_status_pkp_bersamaan_satu_berhasil():
    h = _login()
    tag = str(int(time.time()))[-6:]
    r = requests.post(f"{BASE}/entities", headers=h, timeout=30, json={
        "legal_name": f"PT Uji Balapan KPT1 {tag}", "short_name": f"KPT1B{tag}", "doc_prefix": f"KB{tag}",
        "type": "PT", "default_tax_mode": "non_ppn", "npwp": "01.234.567.8-901.000"})
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    try:
        isi = {"to": "ppn", "effective_date": _hari_ini_wib(), "reason": "uji balapan KP-T1"}
        with ThreadPoolExecutor(max_workers=6) as ex:
            hasil = list(ex.map(lambda _: requests.post(f"{BASE}/entities/{eid}/tax-status", headers=h, json=isi,
                                                        timeout=60), range(6)))
        kode = sorted(x.status_code for x in hasil)
        assert kode.count(200) == 1, [(x.status_code, x.text[:120]) for x in hasil]
        assert set(kode) <= {200, 400, 409}, kode
        doc = DB.business_entities.find_one({"id": eid}, {"_id": 0})
        assert doc["default_tax_mode"] == "ppn" and len(doc["tax_status_history"]) == 1
    finally:
        DB.business_entities.delete_one({"id": eid})
        DB.system_settings.delete_one({"scope": eid})
        DB.config_values.delete_many({"scope_id": eid})
        DB.audit_logs.delete_many({"entity_type": "business_entity", "entity_id": eid})


def test_KPT1_A_skrip_migrasi_mode_lapor_tidak_menulis():
    sebelum = list(DB.business_entities.find({}, {"_id": 0}).sort("id", 1))
    out = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_kpt1_profil_pt.py")], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    print(out.stdout)
    assert out.returncode == 0, out.stderr
    assert "mode lapor" in out.stdout
    assert list(DB.business_entities.find({}, {"_id": 0}).sort("id", 1)) == sebelum
    salah = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_kpt1_profil_pt.py"), "--salah"], cwd=ROOT,
                           capture_output=True, text=True, timeout=60)
    assert salah.returncode == 2
