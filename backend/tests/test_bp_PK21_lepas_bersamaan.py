"""PK-21 U12–U13 — di MongoDB ASLI (lingkungan A): lepas-cocok BERSAMAAN.

U12: M1 ↔ K1 tercocok; dua permintaan lepas M1 bersamaan → tepat satu 200, satu 409; K1 `reconciled_amount = 0`.
U13: M2 dan M3 tercocok ke K2; lepas M2 dan lepas M3 bersamaan → keduanya 200; K2 `reconciled_amount = 0`,
     `matched_line_ids = []`. Hitungan: 600.000 − 400.000 − 200.000 = 0; tiap pengurangan bersyarat pada nilai
     sebelumnya sehingga urutan mana pun menghasilkan 0.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); data uji (rekening, kas, baris rekening koran)
disisipkan langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) sebagai FIXTURE, pencocokan & pelepasan lewat API,
lalu dihapus. Tidak untuk data nyata.
"""
import datetime
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
ACC = f"ba_pk21_{TAG}"


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def _kas(tid, nominal):
    return {"id": tid, "number": f"CASH-PK21-{tid[-6:]}", "cash_type": "kas_besar", "direction": "in",
            "amount": float(nominal), "category": "uji PK-21", "description": f"uji PK-21 {TAG}", "entity_id": "ent_ksc",
            "account_id": ACC, "ref_type": "", "ref_id": "", "txn_date": NOW[:10], "status": "posted",
            "reconciled": False, "reconciled_amount": 0.0, "created_by": "uji", "created_at": NOW, "updated_at": NOW}


def _baris(lid, nominal):
    return {"id": lid, "bank_account_id": ACC, "entity_id": "ent_ksc", "stmt_date": NOW[:10], "amount": float(nominal),
            "direction": "in", "description": f"uji PK-21 {lid}", "counterparty": "", "desc_key": "", "ref": "",
            "external_id": lid, "balance": 0.0, "status": "unmatched", "match_kind": "", "matched_txn_id": "",
            "matched_txn_ids": [], "allocations": [], "score": 0, "score_explain": [], "suggestions": [],
            "match_type": "", "matched_at": "", "matched_by": "", "holding": {}, "holding_allocated": [],
            "holding_remaining": 0.0, "import_batch": "pk21", "format_id": "", "created_at": NOW, "updated_at": NOW}


@pytest.fixture()
def siap():
    k1, k2 = f"cash_pk21_{TAG}_k1", f"cash_pk21_{TAG}_k2"
    m1, m2, m3 = (f"stl_pk21_{TAG}_m{i}" for i in (1, 2, 3))
    DB.bank_accounts.insert_one({"id": ACC, "name": f"Uji PK21 {TAG}", "account_type": "bank", "cash_type": "bank",
                                 "bank_name": "BCA", "entity_id": "ent_ksc", "is_active": True, "status": "active",
                                 "opening_balance": 0, "created_at": NOW, "updated_at": NOW})
    DB.cash_transactions.insert_many([_kas(k1, 1_000_000), _kas(k2, 600_000)])
    DB.bank_statement_lines.insert_many([_baris(m1, 1_000_000), _baris(m2, 400_000), _baris(m3, 200_000)])
    yield {"k1": k1, "k2": k2, "m1": m1, "m2": m2, "m3": m3}
    DB.bank_statement_lines.delete_many({"bank_account_id": ACC})
    DB.cash_transactions.delete_many({"id": {"$in": [k1, k2]}})
    DB.bank_accounts.delete_one({"id": ACC})
    DB.bank_match_rules.delete_many({"bank_account_id": ACC})


def _lepas_bersamaan(h, lids):
    def lepas(lid):
        return requests.post(f"{BASE}/bank-reconciliation/lines/{lid}/unmatch", headers=h, json={}, timeout=60)
    with ThreadPoolExecutor(len(lids)) as ex:
        return [f.result() for f in [ex.submit(lepas, x) for x in lids]]


def test_PK21_U12_dua_lepas_bersamaan_satu_baris(siap):
    h = _login()
    r = requests.post(f"{BASE}/bank-reconciliation/lines/{siap['m1']}/match", headers=h,
                      json={"txn_id": siap["k1"]}, timeout=60)
    assert r.status_code == 200, r.text
    assert DB.cash_transactions.find_one({"id": siap["k1"]})["reconciled_amount"] == 1_000_000
    hasil = _lepas_bersamaan(h, [siap["m1"], siap["m1"]])
    kode = sorted(x.status_code for x in hasil)
    print("kode:", kode, [x.text[:160] for x in hasil if x.status_code != 200])
    assert kode == [200, 409], [x.text for x in hasil]
    k1 = DB.cash_transactions.find_one({"id": siap["k1"]}, {"_id": 0})
    assert k1["reconciled_amount"] == 0 and k1["reconciled"] is False and k1["matched_line_ids"] == []
    m1 = DB.bank_statement_lines.find_one({"id": siap["m1"]}, {"_id": 0})
    assert m1["status"] == "unmatched" and "match_lock" not in m1


def test_PK21_U13_lepas_dua_baris_bersamaan_satu_transaksi(siap):
    h = _login()
    r = requests.post(f"{BASE}/bank-reconciliation/match-group", headers=h,
                      json={"line_ids": [siap["m2"], siap["m3"]], "txn_id": siap["k2"]}, timeout=60)
    assert r.status_code == 200, r.text
    k2 = DB.cash_transactions.find_one({"id": siap["k2"]}, {"_id": 0})
    assert k2["reconciled_amount"] == 600_000 and k2["reconciled"] is True     # 400.000 + 200.000
    hasil = _lepas_bersamaan(h, [siap["m2"], siap["m3"]])
    assert [x.status_code for x in hasil] == [200, 200], [x.text for x in hasil]
    k2 = DB.cash_transactions.find_one({"id": siap["k2"]}, {"_id": 0})
    # 600.000 − 400.000 − 200.000 = 0, urutan mana pun
    assert k2["reconciled_amount"] == 0 and k2["reconciled"] is False and k2["matched_line_ids"] == []
