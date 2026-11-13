"""PK-07 — setoran karyawan pada kasus keuangan dibukukan satu kali (docs/blueprint/unit/PK-07.md).

Tiap uji membuat kasus "rekening pribadi karyawan" sendiri (pelanggan, pesanan, rekening berakhiran unik) lalu langkah 1
"akui dipegang karyawan" 10.000.000. Saldo 1-1280 dibaca sebagai SELISIH terhadap saldo sebelum kasus dibuat.
"""
from __future__ import annotations

import datetime
import itertools

import pytest

from pembantu import aktifkan_akun, nonaktifkan_akun

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
_n = itertools.count(1)


async def _saldo(db, akun: str) -> float:
    d = k = 0.0
    async for je in db.journal_entries.find({"entity_id": E1, "status": {"$ne": "void"}}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == akun:
                d += float(ln.get("debit") or 0)
                k += float(ln.get("credit") or 0)
    return round(d - k, 2)


async def _kas(db, kasus: str):
    return [k async for k in db.cash_transactions.find({"ref_type": "finance_case", "ref_id": kasus}, {"_id": 0})]


@pytest.fixture(scope="module")
async def alasan(aplikasi):
    from services import amendment_service
    await amendment_service.ensure_reasons()


async def _kasus(klien, db, h, *, pelanggan: bool = True) -> dict:
    i = next(_n)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cus, so, ba = f"cus_pk07_{i}", f"so_pk07_{i}", f"ba_pk07_{i}"
    await db.customers.insert_one({"id": cus, "name": f"Toko Uji {i}", "entity_id": E1, "status": "active"})
    await db.sales_orders.insert_one({"id": so, "number": f"SO-PK07-{i}", "entity_id": E1, "customer_id": cus,
                                      "customer_name": f"Toko Uji {i}", "status": "confirmed",
                                      "grand_total": 10000000, "payments": [], "payment_status": "unpaid",
                                      "created_at": now})
    await db.bank_accounts.insert_one({"id": ba, "name": f"Bank Uji {i}", "account_type": "bank",
                                       "cash_type": "kas_besar", "entity_id": E1, "is_active": True,
                                       "opening_balance": 0})
    awal = await _saldo(db, "1-1280")
    body = {"case_type": "rekening_pribadi_karyawan", "amount": 10000000, "order_ids": [so],
            "attachments": [{"name": "bukti.pdf", "path": "uji/bukti.pdf"}]}
    if pelanggan:
        body["customer_id"] = cus
    r = await klien.post("/api/finance-cases", json=body, headers=h)
    assert r.status_code == 200, r.text
    k = r.json()["id"]
    r = await klien.post(f"/api/finance-cases/{k}/resolve", headers=h, json={
        "action": "akui_dipegang_karyawan", "reason_code": "case_employee_account", "amount": 10000000,
        "order_id": so, "employee_name": "Budi"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_progress"
    assert await _saldo(db, "1-1280") == awal + 10000000
    return {"id": k, "cus": cus, "ba": ba, "awal": awal}


async def _setor(klien, h, kasus: dict, n: float):
    return await klien.post(f"/api/finance-cases/{kasus['id']}/resolve", headers=h, json={
        "action": "setor_dari_karyawan", "reason_code": "case_employee_account", "amount": n,
        "account_id": kasus["ba"]})


async def test_U01_setor_penuh_satu_kas_satu_jurnal(klien, db, kepala_admin, alasan):
    K = await _kasus(klien, db, kepala_admin)
    r = await _setor(klien, kepala_admin, K, 10000000)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    kas = await _kas(db, K["id"])
    assert len(kas) == 1
    k = kas[0]
    assert (k["direction"], k["amount"], k["entity_id"], k["account_id"], k["contra_account_code"]) == (
        "in", 10000000, E1, K["ba"], "1-1280")
    je = [j async for j in db.journal_entries.find({"source_type": "cash_transaction", "source_id": k["id"],
                                                    "status": {"$ne": "void"}}, {"_id": 0})]
    assert len(je) == 1
    baris = {(ln["account_code"], float(ln.get("debit") or 0), float(ln.get("credit") or 0)) for ln in je[0]["lines"]}
    assert ("1-1280", 0.0, 10000000.0) in baris
    assert any(d == 10000000.0 and a != "1-1280" for a, d, _ in baris)
    assert await _saldo(db, "1-1280") == K["awal"]


async def test_U02_dokumen_langkah_dua(klien, db, kepala_admin, alasan):
    K = await _kasus(klien, db, kepala_admin)
    r = await _setor(klien, kepala_admin, K, 10000000)
    assert r.status_code == 200, r.text
    case = r.json()
    ex = (case.get("resolution") or {}).get("extra") or {}
    assert ex.get("settled_amount") == 10000000 and ex.get("remaining_amount") == 0
    kas_ids = {k["id"] for k in await _kas(db, K["id"])}
    docs = [d for d in case.get("documents") or [] if d.get("kind") == "cash_transaction" and d.get("id") in kas_ids]
    assert len(docs) == 1
    je_ids = {j["id"] async for j in db.journal_entries.find({"source_type": "cash_transaction",
                                                              "source_id": {"$in": list(kas_ids)}}, {"id": 1})}
    assert len([d for d in case.get("documents") or [] if d.get("kind") == "journal_entry" and d.get("id") in je_ids]) == 1


async def test_U03_setor_bertahap(klien, db, kepala_admin, alasan):
    K = await _kasus(klien, db, kepala_admin)
    r = await _setor(klien, kepala_admin, K, 4000000)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_progress"
    assert [k["amount"] for k in await _kas(db, K["id"])] == [4000000]
    assert await _saldo(db, "1-1280") == K["awal"] + 6000000
    assert r.json()["resolution"]["extra"]["remaining_amount"] == 6000000
    r = await _setor(klien, kepala_admin, K, 6000000)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    assert sorted(k["amount"] for k in await _kas(db, K["id"])) == [4000000, 6000000]
    assert await _saldo(db, "1-1280") == K["awal"]


async def test_U04_kelebihan_jadi_kredit_toko(klien, db, kepala_admin, alasan):
    K = await _kasus(klien, db, kepala_admin)
    kredit_awal = -(await _saldo(db, "2-1450"))
    r = await _setor(klien, kepala_admin, K, 12000000)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    kas = sorted(((k["amount"], k["contra_account_code"]) for k in await _kas(db, K["id"])))
    assert kas == [(2000000, "2-1450"), (10000000, "1-1280")]
    assert await _saldo(db, "1-1280") == K["awal"]
    assert -(await _saldo(db, "2-1450")) == kredit_awal + 2000000
    sc = [x async for x in db.store_credit_ledger.find({"customer_id": K["cus"]}, {"_id": 0})]
    assert len(sc) == 1 and float(sc[0].get("amount") or 0) == 2000000


async def test_U05_jurnal_gagal_lalu_diulang(klien, db, kepala_admin, alasan):
    K = await _kasus(klien, db, kepala_admin)
    await nonaktifkan_akun(E1, "1-1280")
    try:
        r = await _setor(klien, kepala_admin, K, 10000000)
        assert r.status_code == 400, r.text
        assert "Akun 1-1280 nonaktif" in str(r.json().get("detail"))
        assert (await db.finance_cases.find_one({"id": K["id"]}))["status"] == "in_progress"
        kas = await _kas(db, K["id"])
        assert len(kas) == 1
        assert not await db.journal_entries.count_documents({"source_type": "cash_transaction",
                                                             "source_id": kas[0]["id"]})
    finally:
        await aktifkan_akun(E1, "1-1280")
    r = await _setor(klien, kepala_admin, K, 10000000)
    assert r.status_code == 200, r.text
    kas = await _kas(db, K["id"])
    assert [k["amount"] for k in kas] == [10000000]
    assert await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                                     "status": {"$ne": "void"}}) == 1
    assert await _saldo(db, "1-1280") == K["awal"]


async def test_U06_kelebihan_tanpa_pelanggan_ditolak(klien, db, kepala_admin, alasan):
    K = await _kasus(klien, db, kepala_admin, pelanggan=False)
    r = await _setor(klien, kepala_admin, K, 12000000)
    assert r.status_code == 400, r.text
    assert "kelebihan tidak bisa dijadikan kredit toko" in str(r.json().get("detail"))
    assert await _kas(db, K["id"]) == []
    assert await _saldo(db, "1-1280") == K["awal"] + 10000000
