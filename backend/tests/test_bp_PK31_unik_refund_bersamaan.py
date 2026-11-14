"""PK-31 U15 — di MongoDB ASLI: (1) indeks unik parsial `intercompany_eliminations` (`source_g6_pair_id`,
`period_key`) menolak sisipan kedua; (2) dua refund bersamaan atas retur Rp 4.000.000 setelah lunas → tepat satu
berhasil, `refund_paid` = 4.000.000 pada kedua dokumen kembar, satu pasang kas dan satu pasang jurnal.

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan ke database uji lokal.
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


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"},
                      timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def test_PK31_U15a_indeks_unik_pasangan_bulan():
    pid = f"pbp31_{uuid.uuid4().hex[:6]}"
    doc = {"source_g6_pair_id": pid, "period_key": "2026-12", "auto_generated": True, "lines": [],
           "effective_date": "2026-12-31"}
    DB.intercompany_eliminations.insert_one({**doc, "id": f"icelim_{pid}_1"})
    try:
        with pytest.raises(DuplicateKeyError):
            DB.intercompany_eliminations.insert_one({**doc, "id": f"icelim_{pid}_2"})
        # Entri lama tanpa period_key dan entri manual tanpa pasangan tidak ikut indeks (parsial).
        DB.intercompany_eliminations.insert_one({"id": f"icelim_{pid}_lama", "source_g6_pair_id": pid})
        DB.intercompany_eliminations.insert_one({"id": f"icelim_{pid}_lama2", "source_g6_pair_id": pid})
    finally:
        DB.intercompany_eliminations.delete_many({"source_g6_pair_id": pid})


def test_PK31_U15b_dua_refund_bersamaan():
    h = _login()
    pid = f"pbp31_{uuid.uuid4().hex[:6]}"
    # FIXTURE: A→B Rp 10.000.000 sudah lunas penuh lalu diretur Rp 4.000.000 (refund_due = 4.000.000).
    base = {"pair_id": pid, "seller_entity_id": "ent_ksc", "buyer_entity_id": "ent_kanda", "subtotal": 10 * JT,
            "tax_amount": 0.0, "grand_total": 10 * JT, "settled_amount": 10 * JT, "returned_amount": 4 * JT,
            "refund_due": 4 * JT, "refund_paid": 0.0, "status": "settled", "gl_status": "posted", "items": [],
            "seller_entity_name": "KSC", "buyer_entity_name": "Kanda"}
    DB.interco_transactions.insert_many([
        {**base, "id": f"{pid}_s", "role": "seller", "entity_id": "ent_ksc", "number": f"S/{pid}",
         "counterpart_id": f"{pid}_b"},
        {**base, "id": f"{pid}_b", "role": "buyer", "entity_id": "ent_kanda", "number": f"B/{pid}",
         "counterpart_id": f"{pid}_s"}])

    def refund(key):
        return requests.post(f"{BASE}/interco/refunds", timeout=60, headers={**h, "Idempotency-Key": key}, json={
            "payer_entity_id": "ent_ksc", "payee_entity_id": "ent_kanda",
            "transactions": [{"interco_id": f"{pid}_s"}], "method": "transfer"}).status_code
    with ThreadPoolExecutor(2) as ex:
        codes = list(ex.map(refund, [f"{pid}-a", f"{pid}-b"]))
    assert codes.count(200) == 1, codes
    assert all(d["refund_paid"] == 4 * JT for d in DB.interco_transactions.find({"pair_id": pid}))
    posted = list(DB.interco_settlements.find({"applied.pair_id": pid, "kind": "refund", "status": "posted"}))
    assert len(posted) == 1
    sid = posted[0]["id"]
    assert DB.cash_transactions.count_documents({"ref_id": sid}) == 2
    assert DB.journal_entries.count_documents({"source_type": "interco_settlement",
                                               "source_id": {"$regex": f"^{sid}:"}}) == 2
    for k in DB.interco_settlements.find({"applied.pair_id": pid, "kind": "refund", "status": {"$ne": "posted"}}):
        assert k["status"] == "cancelled"
        assert DB.cash_transactions.count_documents({"ref_id": k["id"]}) == 0
        assert DB.journal_entries.count_documents({"source_type": "interco_settlement",
                                                   "source_id": {"$regex": f"^{k['id']}:"}}) == 0
