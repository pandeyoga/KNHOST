"""AG-T5 U9 — di MongoDB ASLI (lingkungan A).

Kartu bayar tagihan pemasok (golongan C) `awaiting_second`; Manajer dan Admin menyetujui sebagai orang kedua BERSAMAAN →
tepat satu 200 (`confirmed`) dan satu 409; tepat SATU kas keluar ber-`ai_card_id`. Klaim `awaiting_second → running`
atomik (`find_one_and_update` bersyarat status + `expires_at`) + `Idempotency-Key: <id kartu>` di satu panggilan tulis
`POST /api/vendor-bills/{id}/pay`. Hitungan: tagihan 7.000.000 belum dibayar, bayar 7.000.000 → sisa 0; satu kas keluar.

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); tagihan pemasok dan rekening uji disisipkan
langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) sebagai FIXTURE; sakelar akun (Finance pembuat, Manajer & Admin
orang kedua), `ai.tindakan_uang_keluar` dan `kontrol.asisten_uang_keluar.min_orang` = "2" (PT `ent_ksc`) diubah lewat API
lalu DIKEMBALIKAN; kartu disiapkan, disetujui, dan diputus orang kedua lewat API; semua data uji dihapus. Tidak untuk data
nyata. Tidak memanggil layanan model.
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
VB, REK = f"vb_agt5_{TAG}", f"rek_agt5_{TAG}"
KSC = "ent_ksc"
ALASAN = f"uji AG-T5 U9 {TAG}"
AKUN = ("finance@kainnusantara.id", "manager@kainnusantara.id", "admin@kainnusantara.id")


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def _efektif(h, key):
    r = requests.get(f"{BASE}/config/effective", headers=h, params={"entity_id": KSC}, timeout=30)
    assert r.status_code == 200, r.text
    return next((it.get("value") for it in r.json()["items"] if it["key"] == key), None)


def _atur(h, key, value):
    r = requests.put(f"{BASE}/config/values", headers=h, timeout=30, json={"items": [{
        "key": key, "value": value, "scope_type": "entity", "scope_id": KSC, "reason": ALASAN}]})
    assert r.status_code == 200, r.text


@pytest.fixture()
def siap():
    h = {e: _login(e) for e in AKUN}
    adm = h["admin@kainnusantara.id"]
    lama = {e: DB.users.find_one({"email": e}, {"_id": 0, "id": 1, "ai_finance": 1}) for e in AKUN}
    lama_pt = _efektif(adm, "ai.tindakan_uang_keluar")
    lama_min = _efektif(adm, "kontrol.asisten_uang_keluar.min_orang")
    for e in AKUN:
        r = requests.patch(f"{BASE}/users/{lama[e]['id']}", headers=adm, timeout=30,
                           json={"data": {"ai_finance": {"enabled": True, "classes": ["B", "C"]}}})
        assert r.status_code == 200, r.text
    _atur(adm, "ai.tindakan_uang_keluar", True)
    _atur(adm, "kontrol.asisten_uang_keluar.min_orang", "2")
    DB.bank_accounts.insert_one({"id": REK, "name": f"Bank Uji AG-T5 {TAG}", "entity_id": KSC, "account_type": "bank",
                                 "cash_type": "kas_besar", "is_active": True, "opening_balance": 0})
    DB.vendor_bills.insert_one({"id": VB, "bill_number": f"VB-AGT5-{TAG}", "entity_id": KSC, "supplier_id": "sup_agt5",
                                "supplier_name": f"Pemasok Uji AG-T5 {TAG}", "status": "posted",
                                "grand_total": 7_000_000.0, "subtotal": 7_000_000.0, "amount_paid": 0.0,
                                "payments": [], "timeline": [], "po_id": None, "bill_date": NOW[:10], "created_at": NOW})
    yield h
    kas = [x["id"] for x in DB.cash_transactions.find({"ref_id": VB}, {"_id": 0, "id": 1})]
    DB.journal_entries.delete_many({"source_id": {"$in": kas + [VB]}})
    DB.cash_transactions.delete_many({"id": {"$in": kas}})
    DB.ap_payment_intents.delete_many({"target_id": VB})
    DB.doc_refs.delete_many({"$or": [{"from_id": VB}, {"to_id": VB}]})
    kartu = [x["id"] for x in DB.ai_action_proposals.find({"request": ALASAN}, {"_id": 0, "id": 1})]
    DB.idempotency_keys.delete_many({"key": {"$in": kartu}})
    DB.notifications.delete_many({"type": "ai_card_second", "ref": {"$regex": "|".join(kartu) or "^$"}})
    DB.ai_action_proposals.delete_many({"request": ALASAN})
    DB.vendor_bills.delete_one({"id": VB})
    DB.bank_accounts.delete_one({"id": REK})
    _atur(adm, "kontrol.asisten_uang_keluar.min_orang", str(lama_min or "1"))
    _atur(adm, "ai.tindakan_uang_keluar", bool(lama_pt))
    for e in AKUN:
        af = lama[e].get("ai_finance")
        DB.users.update_one({"id": lama[e]["id"]}, {"$set": {"ai_finance": af}} if af is not None
                            else {"$unset": {"ai_finance": ""}})


def test_AGT5_U9_dua_orang_kedua_bersamaan_satu_kas(siap):
    fin, mgr, adm = (siap[e] for e in AKUN)
    r = requests.post(f"{BASE}/ai/tools/prepare_action", headers=fin, timeout=60, json={
        "action": "vendor_bill_pay", "user_request": ALASAN,
        "args": {"bill_id": VB, "amount": 7_000_000, "bank_account_id": REK}})
    assert r.status_code == 200, r.text
    kid = r.json()["card"]["id"]
    r = requests.post(f"{BASE}/ai/actions/{kid}/confirm", headers=fin, timeout=60,
                      json={"reason": "pemasok minta dilunasi hari ini", "retype": "7.000.000"})
    assert r.status_code == 200 and r.json()["status"] == "awaiting_second", r.text

    def putus(h):
        return requests.post(f"{BASE}/ai/actions/{kid}/second", headers=h, timeout=120,
                             json={"decision": "approve", "reason": ""})

    with ThreadPoolExecutor(2) as ex:
        hasil = [f.result() for f in [ex.submit(putus, h) for h in (mgr, adm)]]
    kode = sorted(x.status_code for x in hasil)
    print("kode:", kode, [x.text[:200] for x in hasil])
    assert kode == [200, 409], [x.text for x in hasil]
    ok = next(x for x in hasil if x.status_code == 200).json()
    assert ok["status"] == "confirmed", ok
    assert DB.cash_transactions.count_documents({"ref_id": VB, "direction": "out", "status": {"$ne": "void"}}) == 1
    assert DB.cash_transactions.count_documents({"ai_card_id": kid}) == 1
    vb = DB.vendor_bills.find_one({"id": VB}, {"_id": 0, "amount_paid": 1})
    assert vb["amount_paid"] == 7_000_000
