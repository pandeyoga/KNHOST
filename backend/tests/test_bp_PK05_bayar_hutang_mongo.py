"""PK-05 U15, U17 — di MongoDB ASLI (lingkungan A): balapan bayar dan indeks unik nomor faktur pemasok.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan langsung ke database uji
lokal (`MONGO_URL`/`DB_NAME`). Tidak untuk database berisi data nyata.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests
from pymongo.errors import DuplicateKeyError

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
JT = 1_000_000


def _login(email="admin@kainnusantara.id"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _rekening():
    acc = DB.bank_accounts.find_one({"entity_id": "ent_ksc", "is_active": {"$ne": False}})
    if not acc:
        pytest.skip("tidak ada rekening aktif ent_ksc di database uji")
    return acc["id"]


def _bill(total):
    bid = f"vb_bp05_{uuid.uuid4().hex[:8]}"
    DB.vendor_bills.insert_one({"id": bid, "bill_number": bid.upper(), "entity_id": "ent_ksc",
                                "supplier_id": "sup_bp05", "supplier_name": "Pemasok Uji BP05", "status": "posted",
                                "grand_total": total, "subtotal": total, "amount_paid": 0.0, "payments": [],
                                "timeline": [], "po_id": None, "bill_date": "2026-11-01"})
    return bid


def test_U15_bayar_bersamaan_kunci_sama_dan_beda():
    h, rek = _login(), _rekening()
    bid = _bill(11.1 * JT)
    body = {"amount": 5 * JT, "bank_account_id": rek, "method": "transfer"}

    def bayar(key):
        return requests.post(f"{BASE}/vendor-bills/{bid}/pay", json=body, timeout=60,
                             headers={**h, "Idempotency-Key": key}).status_code
    with ThreadPoolExecutor(2) as ex:
        list(ex.map(bayar, ["bp05-sama", "bp05-sama"]))
    vb = DB.vendor_bills.find_one({"id": bid})
    assert vb["amount_paid"] == 5 * JT
    kas = list(DB.cash_transactions.find({"ref_id": bid}))
    assert len(kas) == 1
    assert DB.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                               "status": {"$ne": "void"}}) == 1
    with ThreadPoolExecutor(2) as ex:
        codes = list(ex.map(bayar, ["bp05-a", "bp05-b"]))
    vb = DB.vendor_bills.find_one({"id": bid})
    baru = DB.cash_transactions.count_documents({"ref_id": bid}) - 1
    assert baru == sum(1 for c in codes if c == 200) <= 2, codes
    assert vb["amount_paid"] <= 11.1 * JT + 0.01


def test_U17_indeks_unik_nomor_faktur_pemasok():
    info = DB.vendor_bills.index_information()
    assert "uq_supplier_invoice" in info, "indeks belum lahir — data kembar? (titik henti H6)"
    no = f"INV-BP05-{uuid.uuid4().hex[:6]}"
    doc = {"entity_id": "ent_ksc", "supplier_id": "sup_bp05", "supplier_invoice_no": no, "status": "posted"}
    DB.vendor_bills.insert_one({**doc, "id": f"vb_{uuid.uuid4().hex[:8]}"})
    with pytest.raises(DuplicateKeyError):
        DB.vendor_bills.insert_one({**doc, "id": f"vb_{uuid.uuid4().hex[:8]}"})
    # status batal tidak ikut indeks: faktur lama yang dibatalkan boleh dipakai ulang nomornya
    DB.vendor_bills.insert_one({**doc, "status": "cancelled", "id": f"vb_{uuid.uuid4().hex[:8]}"})
