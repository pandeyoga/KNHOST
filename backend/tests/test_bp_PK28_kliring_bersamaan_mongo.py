"""PK-28 U15 — di MongoDB ASLI (lingkungan A): dua kliring GR/IR bersamaan atas PO yang sama.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.

Persiapan seperti U9: PO `closed_short` PT `ent_ksc` bersisa GR/IR kredit 10.000 (fixture: jurnal `goods_receipt`
Cr 2-1150 600.000 ber-`ref.po_id` + jurnal `vendor_bill` Dr 2-1150 590.000), akun fixture `5-9920` dipetakan ke
`pembelian.selisih_harga` lapisan `ent_ksc`. Harapan: tepat 1 jurnal `grir_clearing`; satu jawaban 200, lainnya 409
("sedang diproses" — niat bersyarat larik `grir_clearings` — atau "sudah nol" bila yang kedua membaca sesudah yang pertama
selesai). Pemetaan uji dicabut kembali di akhir.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KSC = "ent_ksc"
AKUN = "5-9920"


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _petakan(h):
    if not DB.gl_accounts.find_one({"code": AKUN}):
        DB.gl_accounts.insert_one({"id": f"gla_bp28_{uuid.uuid4().hex[:6]}", "code": AKUN, "name": "Uji selisih harga",
                                   "type": "expense", "normal_balance": "debit", "parent_code": "5-0000",
                                   "is_postable": True, "is_active": True, "entity_id": None, "created_at": _now()})
    r = requests.put(f"{BASE}/gl/account-mappings/pembelian.selisih_harga", headers=h, timeout=30,
                     json={"account_code": AKUN, "entity_id": KSC, "reason": "uji PK-28 U15 lapis A"})
    assert r.status_code == 200, r.text


def _lepas(h):
    requests.post(f"{BASE}/gl/account-mappings/pembelian.selisih_harga/reset", headers=h, timeout=30,
                  json={"entity_id": KSC, "reason": "uji PK-28 U15 selesai"})


def _po_bersisa() -> str:
    po = f"po_bp28_{uuid.uuid4().hex[:8]}"
    DB.purchase_orders.insert_one({"id": po, "po_number": f"PO/BP28/{po[-8:]}", "entity_id": KSC,
                                   "status": "closed_short", "supplier_name": "Pemasok Uji BP28", "items": [],
                                   "created_at": _now()})
    tgl = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for st, d, c in (("goods_receipt", 0, 600_000), ("vendor_bill", 590_000, 0)):
        DB.journal_entries.insert_one({
            "id": f"je_bp28_{uuid.uuid4().hex[:10]}", "number": f"JE/BP28/{uuid.uuid4().hex[:6]}", "date": tgl,
            "source_type": st, "source": st, "source_id": f"{st}_{po}", "ref": {"po_id": po}, "status": "posted",
            "entity_id": KSC, "total_debit": 600_000 if c else 590_000, "total_credit": 600_000 if c else 590_000,
            "lines": [{"account_code": "2-1150", "debit": d, "credit": c},
                      {"account_code": "1-1300" if c else "2-1100", "debit": c, "credit": d}],
            "created_by": "uji", "created_at": _now()})
    return po


def test_U15_dua_kliring_bersamaan_tepat_satu_jurnal():
    h = _login()
    _petakan(h)
    try:
        for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
            po = _po_bersisa()

            def kliring(i):
                return requests.post(f"{BASE}/finance/gr-ir/{po}/clear",
                                     headers={**h, "Idempotency-Key": f"bp28-{po}-{i}"},
                                     json={"reason": "uji kliring bersamaan"}, timeout=60)
            with ThreadPoolExecutor(2) as ex:
                res = list(ex.map(kliring, [0, 1]))
            codes = sorted(r.status_code for r in res)
            assert codes == [200, 409], [(r.status_code, r.text) for r in res]
            n = DB.journal_entries.count_documents({"source_type": "grir_clearing", "source_id": {"$regex": f"^{po}:"},
                                                    "status": {"$ne": "void"}})
            assert n == 1, (codes, n)
            doc = DB.purchase_orders.find_one({"id": po})
            assert len(doc["grir_clearings"]) == 1 and doc["grir_clearings"][0]["gl_status"] == "posted"
    finally:
        _lepas(h)
