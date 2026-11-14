"""KP-T6 — di MongoDB ASLI (lingkungan A) dengan data acuan: lapisan template PT unik, kop data acuan tidak berubah
diam-diam, skrip migrasi mode lapor tidak menulis.

Butir U1–U13 diuji di lingkungan B (`backend/tests_mem/test_KPT6_cetak_per_pt.py`). Berkas ini pelengkap yang hanya sah
di MongoDB asli: (1) indeks unik wajib `pdf_templates.uq_doctype_entity` terpasang dan enam simpan lapisan PT yang
bersamaan menghasilkan satu baris (database tiruan tidak menguji keunikan maupun balapan, `00_ATURAN_EKSEKUSI.md` §9);
(2) kop tiap PT data acuan (`scripts/dev_restore_demo.sh`) yang masih membawa teks lama tetap tercetak sama dan selisihnya
dilaporkan — identitas PT yang sudah memakai Profil PT sama dengan Profil PT; (3) skrip
`scripts/migrate_kpt6_template_pt.py` mode lapor di data acuan tidak mengubah satu dokumen pun (keluaran dicetak, `-s`).

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); pembacaan dan pembersihan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Lapisan PT uji dihapus lewat API. Tidak untuk database berisi data nyata (menjalankan
skrip di data nyata = titik henti H3).
"""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
ROOT = Path(__file__).resolve().parents[2]
PT = "ent_kanda"


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def test_KPT6_A_indeks_unik_dan_simpan_lapisan_pt_bersamaan():
    info = DB.pdf_templates.index_information()
    assert "uq_doctype_entity" in info and info["uq_doctype_entity"].get("unique"), sorted(info)
    h = _login()
    try:
        with ThreadPoolExecutor(max_workers=6) as ex:
            hasil = list(ex.map(lambda i: requests.put(
                f"{BASE}/pdf/templates/invoice", headers=h, params={"entity_id": PT}, timeout=60,
                json={"config": {"closing_note": f"Uji balapan KP-T6 {i}"}}), range(6)))
        kode = [x.status_code for x in hasil]
        # upsert bersamaan: indeks unik menolak sisipan kembar (galat duplikat → 500 pada kalah balapan) — yang dinilai
        # adalah BARIS: tepat satu lapisan PT invoice untuk PT itu.
        assert kode.count(200) >= 1, [(x.status_code, x.text[:120]) for x in hasil]
        assert DB.pdf_templates.count_documents({"doc_type": "invoice", "entity_id": PT}) == 1
    finally:
        requests.delete(f"{BASE}/pdf/templates/invoice", headers=h, params={"entity_id": PT}, timeout=60)
    assert DB.pdf_templates.count_documents({"doc_type": "invoice", "entity_id": PT}) == 0


def test_KPT6_A_kop_data_acuan_jujur():
    h = _login()
    rows = list(DB.business_entities.find({"status": {"$ne": "archived"}}, {"_id": 0}))
    assert rows
    for e in rows:
        r = requests.get(f"{BASE}/pdf/branding/{e['id']}", headers=h, timeout=30)
        assert r.status_code == 200, (e["id"], r.text[:200])
        b = r.json()
        row = DB.document_branding.find_one({"entity_id": e["id"]}, {"_id": 0}) or {}
        if b["identity_source"] == "teks_lama":
            # teks lama tetap tercetak sampai pemilik memilih; selisihnya dilaporkan
            assert not row.get("identity_resolved_at")
            for k in ("company_name", "address", "phone", "tagline", "website"):
                if str(row.get(k) or "").strip():
                    assert b[k] == str(row[k]).strip(), (e["id"], k)
        else:
            nama = (e.get("print_name") or e.get("legal_name") or e.get("short_name") or "").strip()
            assert b["company_name"] == nama and b["identity_conflicts"] == [], e["id"]
            assert b["npwp"] == str(e.get("npwp") or "").strip(), e["id"]


def test_KPT6_A_skrip_migrasi_mode_lapor_tidak_menulis():
    sebelum = list(DB.pdf_templates.find({}, {"_id": 0}).sort([("doc_type", 1), ("entity_id", 1)]))
    out = subprocess.run([sys.executable, str(ROOT / "scripts/migrate_kpt6_template_pt.py")], cwd=ROOT,
                         capture_output=True, text=True, timeout=300)
    print(out.stdout)
    assert out.returncode == 0, out.stderr
    assert "mode lapor" in out.stdout
    sesudah = list(DB.pdf_templates.find({}, {"_id": 0}).sort([("doc_type", 1), ("entity_id", 1)]))
    assert sesudah == sebelum
