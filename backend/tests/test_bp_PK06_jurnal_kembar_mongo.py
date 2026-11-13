"""PK-06 U17 — di MongoDB ASLI: dua pelunasan antar-PT penuh bersamaan atas transaksi yang sama.

Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`); fixture disisipkan ke database uji lokal.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
JT = 1_000_000


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"},
                      timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_kanda"}


def test_U17_dua_pelunasan_bersamaan():
    h = _login()
    pid = f"pbp06_{uuid.uuid4().hex[:6]}"
    base = {"pair_id": pid, "seller_entity_id": "ent_ksc", "buyer_entity_id": "ent_kanda", "subtotal": 20 * JT,
            "tax_amount": 0.0, "grand_total": 20 * JT, "settled_amount": 0.0, "returned_amount": 0.0,
            "status": "confirmed", "gl_status": "posted", "items": [], "seller_entity_name": "KSC",
            "buyer_entity_name": "Kanda"}
    DB.interco_transactions.insert_many([
        {**base, "id": f"{pid}_s", "role": "seller", "entity_id": "ent_ksc", "number": f"S/{pid}",
         "counterpart_id": f"{pid}_b"},
        {**base, "id": f"{pid}_b", "role": "buyer", "entity_id": "ent_kanda", "number": f"B/{pid}",
         "counterpart_id": f"{pid}_s"}])

    def lunasi(key):
        return requests.post(f"{BASE}/interco/settlements", timeout=60, headers={**h, "Idempotency-Key": key}, json={
            "payer_entity_id": "ent_kanda", "payee_entity_id": "ent_ksc", "transactions": [{"interco_id": f"{pid}_s"}],
            "method": "transfer"}).status_code
    with ThreadPoolExecutor(2) as ex:
        codes = list(ex.map(lunasi, [f"{pid}-a", f"{pid}-b"]))
    assert codes.count(200) == 1, codes
    docs = list(DB.interco_transactions.find({"pair_id": pid}))
    assert all(d["settled_amount"] == 20 * JT for d in docs)
    posted = list(DB.interco_settlements.find({"applied.pair_id": pid, "status": "posted"}))
    assert len(posted) == 1
    sid = posted[0]["id"]
    assert DB.cash_transactions.count_documents({"ref_id": sid}) == 2
    assert DB.journal_entries.count_documents({"source_type": "interco_settlement",
                                               "source_id": {"$regex": f"^{sid}:"}}) == 2
    kalah = list(DB.interco_settlements.find({"applied.pair_id": pid, "status": {"$ne": "posted"}}))
    for k in kalah:   # yang kalah: dibatalkan tanpa sisa efek
        assert k["status"] == "cancelled"
        assert DB.cash_transactions.count_documents({"ref_id": k["id"]}) == 0
        assert DB.journal_entries.count_documents({"source_type": "interco_settlement",
                                                   "source_id": {"$regex": f"^{k['id']}:"}}) == 0
