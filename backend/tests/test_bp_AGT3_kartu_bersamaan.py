"""AG-T3 U5 & U13 — di MongoDB ASLI (lingkungan A).

U5: dua persetujuan sah kartu kwitansi dikirim BERSAMAAN → tepat satu 200 (`confirmed`) dan satu 409; `ar_receipts`
bertambah 1; satu baris `idempotency_keys` berkunci id kartu. Klaim `pending → running` atomik
(`find_one_and_update` bersyarat status) + `Idempotency-Key: <id kartu>` di satu panggilan tulis `POST /api/ar-receipts`.
Hitungan: pesanan 8.000.000, kwitansi 5.000.000 seluruhnya ke pesanan itu → sisa 3.000.000; satu kwitansi.

U13: dua kartu `pending` ber-`session_id` sama disisip langsung → sisipan kedua ditolak indeks unik parsial
`uq_pending_session` (`status = "pending"`, `session_id > ""`).

Uji HTTP terhadap backend yang sedang berjalan (`REACT_APP_BACKEND_URL`); pelanggan, pesanan, dan rekening uji disisipkan
langsung ke database uji lokal (`MONGO_URL`/`DB_NAME`) sebagai FIXTURE; sakelar akun admin dan `ai.tindakan_uang_masuk`
(PT `ent_ksc`) diubah lewat API lalu DIKEMBALIKAN; kartu disiapkan & disetujui lewat API (`POST /api/ai/tools/prepare_action`,
`POST /api/ai/actions/{id}/confirm`); semua data uji dihapus. Tidak untuk data nyata. Tidak memanggil layanan model.
"""
import datetime
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import pytest
import requests
from pymongo.errors import DuplicateKeyError

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
CUS, SO, REK = f"cus_agt3_{TAG}", f"so_agt3_{TAG}", f"rek_agt3_{TAG}"
KSC = "ent_ksc"
ALASAN = f"uji AG-T3 U5 {TAG}"


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
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
    h = _login()
    adm = DB.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0, "id": 1, "ai_finance": 1})
    lama_akun = adm.get("ai_finance")
    lama_sakelar = _efektif(h, "ai.tindakan_uang_masuk")
    r = requests.patch(f"{BASE}/users/{adm['id']}", headers=h, timeout=30,
                       json={"data": {"ai_finance": {"enabled": True, "classes": ["B"]}}})
    assert r.status_code == 200, r.text
    _atur(h, "ai.tindakan_uang_masuk", True)
    DB.bank_accounts.insert_one({"id": REK, "name": f"Bank Uji AG-T3 {TAG}", "entity_id": KSC, "account_type": "bank",
                                 "cash_type": "kas_besar", "is_active": True, "opening_balance": 0})
    DB.customers.insert_one({"id": CUS, "code": f"AGT3-{TAG}", "name": f"Toko Uji AG-T3 {TAG}", "entity_id": KSC,
                             "status": "active", "deposit_balance": 0.0, "payment_profile": {}, "created_at": NOW})
    DB.sales_orders.insert_one({"id": SO, "number": f"SO-AGT3-{TAG}", "entity_id": KSC, "customer_id": CUS,
                                "customer_name": f"Toko Uji AG-T3 {TAG}", "status": "shipped", "grand_total": 8_000_000.0,
                                "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "payment_term_code": "NET30",
                                "items": [], "order_type": "regular", "created_at": NOW})
    yield h
    rc = [x["id"] for x in DB.ar_receipts.find({"customer_id": CUS}, {"_id": 0, "id": 1})]
    kas = [x["id"] for x in DB.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": {"$in": rc}}, {"_id": 0, "id": 1})]
    DB.journal_entries.delete_many({"source_id": {"$in": rc + kas + [SO]}})
    DB.cash_transactions.delete_many({"id": {"$in": kas}})
    DB.ar_receipts.delete_many({"id": {"$in": rc}})
    DB.payment_variance_decisions.delete_many({"receipt_id": {"$in": rc}})
    DB.doc_refs.delete_many({"$or": [{"from_id": {"$in": rc}}, {"to_id": {"$in": rc}}]})
    kartu = [x["id"] for x in DB.ai_action_proposals.find({"request": ALASAN}, {"_id": 0, "id": 1})]
    DB.idempotency_keys.delete_many({"key": {"$in": kartu}})
    DB.ai_action_proposals.delete_many({"$or": [{"request": ALASAN}, {"session_id": f"aichat_agt3_{TAG}"}]})
    DB.sales_orders.delete_one({"id": SO})
    DB.customers.delete_one({"id": CUS})
    DB.bank_accounts.delete_one({"id": REK})
    _atur(h, "ai.tindakan_uang_masuk", bool(lama_sakelar))
    DB.users.update_one({"id": adm["id"]}, {"$set": {"ai_finance": lama_akun}} if lama_akun is not None
                        else {"$unset": {"ai_finance": ""}})


def test_AGT3_U5_dua_persetujuan_bersamaan_satu_kwitansi(siap):
    h = siap
    r = requests.post(f"{BASE}/ai/tools/prepare_action", headers=h, timeout=60, json={
        "action": "ar_receipt_create", "user_request": ALASAN,
        "args": {"customer_id": CUS, "amount": 5_000_000, "account_id": REK,
                 "allocations": [{"order_id": SO, "amount": 5_000_000}]}})
    assert r.status_code == 200, r.text
    kid = r.json()["card"]["id"]
    sebelum = DB.ar_receipts.count_documents({"customer_id": CUS})

    def setujui(_):
        return requests.post(f"{BASE}/ai/actions/{kid}/confirm", headers=h, timeout=120,
                             json={"reason": "pelanggan transfer pagi ini", "retype": "5.000.000"})

    with ThreadPoolExecutor(2) as ex:
        hasil = [f.result() for f in [ex.submit(setujui, i) for i in range(2)]]
    kode = sorted(x.status_code for x in hasil)
    print("kode:", kode, [x.text[:200] for x in hasil])
    assert kode == [200, 409], [x.text for x in hasil]
    ok = next(x for x in hasil if x.status_code == 200).json()
    assert ok["status"] == "confirmed", ok
    assert DB.ar_receipts.count_documents({"customer_id": CUS}) == sebelum + 1
    assert DB.ar_receipts.count_documents({"ai_card_id": kid}) == 1
    assert DB.idempotency_keys.count_documents({"key": kid}) == 1
    so = DB.sales_orders.find_one({"id": SO}, {"_id": 0, "payments": 1})
    assert round(sum(float(p.get("amount") or 0) for p in so.get("payments") or []), 2) == 5_000_000


def test_AGT3_U13_indeks_unik_satu_kartu_pending_per_percakapan(siap):
    info = DB.ai_action_proposals.index_information().get("uq_pending_session")
    assert info and info.get("unique") is True, info
    sid = f"aichat_agt3_{TAG}"
    dasar = {"type": "followup_note", "class": "A", "status": "pending", "session_id": sid, "user_id": "usr_uji_agt3",
             "entity_id": KSC, "created_at": NOW}
    DB.ai_action_proposals.insert_one({**dasar, "id": f"aiact_agt3_{TAG}_1"})
    with pytest.raises(DuplicateKeyError):
        DB.ai_action_proposals.insert_one({**dasar, "id": f"aiact_agt3_{TAG}_2"})
    # Kartu yang sudah tidak menunggu atau tanpa percakapan tidak ikut keunikan.
    DB.ai_action_proposals.insert_one({**dasar, "id": f"aiact_agt3_{TAG}_3", "status": "superseded"})
    DB.ai_action_proposals.insert_one({**dasar, "id": f"aiact_agt3_{TAG}_4", "session_id": ""})
    DB.ai_action_proposals.delete_one({"id": f"aiact_agt3_{TAG}_4"})
