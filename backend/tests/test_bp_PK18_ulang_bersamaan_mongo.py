"""PK-18 U13 — di MongoDB ASLI (lingkungan A): dua "Ulang Posting" bersamaan atas faktur pemasok yang jurnalnya gagal.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.

Persiapan seperti U2: faktur contoh (neto 10.000.000 + PPN 1.100.000 = 11.100.000) sudah `posted` dengan
`gl_status="failed"` (fixture — akun 2-1100 sudah aktif lagi). Harapan: tepat 1 jurnal `vendor_bill`; satu jawaban 200,
lainnya 200 atau 404 (jurnal kedua dicegah `_already_posted` + indeks unik `source_type`+`source_id`, PK-14 W1).
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
JT = 1_000_000


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _faktur_gagal() -> str:
    bid = f"vb_bp18_{uuid.uuid4().hex[:8]}"
    DB.vendor_bills.insert_one({
        "id": bid, "bill_number": f"VB/BP18/{bid[-8:]}", "entity_id": "ent_ksc", "status": "posted", "po_id": "",
        "supplier_id": "sup_bp18", "supplier_name": "Pemasok Uji BP18", "items": [], "subtotal": 10 * JT,
        "ppn_amount": 1.1 * JT, "grand_total": 11.1 * JT, "total_amount": 11.1 * JT, "amount_paid": 0.0,
        "payments": [], "timeline": [], "bill_date": "2026-11-14", "posted_at": "2026-11-14T03:00:00+00:00",
        "gl_status": "failed", "gl_error": "Akun 2-1100 nonaktif", "gl_failed_at": "2026-11-14T03:00:00+00:00"})
    return bid


def test_U13_dua_ulang_bersamaan_tepat_satu_jurnal():
    h = _login()
    for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
        bid = _faktur_gagal()

        def ulang(_i):
            return requests.post(f"{BASE}/finance/posting-failures/vendor_bill/{bid}/retry", headers=h,
                                 timeout=60).status_code
        with ThreadPoolExecutor(2) as ex:
            codes = list(ex.map(ulang, [0, 1]))
        assert 200 in codes and all(c in (200, 404) for c in codes), codes
        n = DB.journal_entries.count_documents({"source_type": "vendor_bill", "source_id": bid,
                                                "status": {"$ne": "void"}})
        assert n == 1, (codes, n)
        vb = DB.vendor_bills.find_one({"id": bid})
        assert vb["gl_status"] == "posted" and vb["journal_entry_id"]
