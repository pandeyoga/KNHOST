"""PK-08 — denda keterlambatan dihitung dan dijurnal dengan benar (docs/blueprint/unit/PK-08.md).

Tiap uji membuat nota denda `draft` 100.000 sendiri di `ent_ksc` lalu menerbitkannya lewat API; saldo 1-1270 dibaca
sebagai selisih terhadap saldo sebelum nota diterbitkan. Rekening dibuat per uji supaya saldo rekening terisolasi.
"""
from __future__ import annotations

import datetime
import itertools

import pytest

from pembantu import tutup_periode

pytestmark = pytest.mark.anyio
E1, E2 = "ent_ksc", "ent_kanda"
_n = itertools.count(1)


async def _saldo(db, akun: str = "1-1270", ent: str = E1) -> float:
    d = k = 0.0
    async for je in db.journal_entries.find({"entity_id": ent, "status": {"$ne": "void"}}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == akun:
                d += float(ln.get("debit") or 0)
                k += float(ln.get("credit") or 0)
    return round(d - k, 2)


async def _rekening(db, ent: str = E1) -> str:
    rid = f"ba_pk08_{next(_n)}"
    await db.bank_accounts.insert_one({"id": rid, "name": f"Bank Uji {rid}", "account_type": "bank",
                                       "cash_type": "kas_besar", "entity_id": ent, "is_active": True,
                                       "status": "active", "opening_balance": 0})
    return rid


@pytest.fixture(scope="module")
async def alasan(aplikasi, db):
    from services import amendment_service
    await amendment_service.ensure_reasons()
    # Rekening kas besar kedua: tanpa ini rekening uji pertama menjadi "satu-satunya rekening PT" dan menyerap kas
    # lama tanpa rekening (bank_service.sole_account_id), sehingga saldonya tidak bisa dibandingkan.
    await db.bank_accounts.insert_one({"id": "ba_pk08_pembanding", "name": "Bank Pembanding", "account_type": "bank",
                                       "cash_type": "kas_besar", "entity_id": E1, "is_active": True,
                                       "status": "active", "opening_balance": 0})


async def _nota(klien, db, h) -> dict:
    i = next(_n)
    nid = f"pnl_pk08_{i}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.penalties.insert_one({
        "id": nid, "number": f"DN-DENDA-PK08-{i}", "entity_id": E1, "doc_type": "sales_order",
        "doc_id": f"so_pk08_{i}", "doc_number": f"SO-PK08-{i}", "plan_id": "", "line_seq": 0,
        "due_date": "2026-10-01", "period_key": f"2026-10-01|2026-11", "customer_id": "cus_pk08",
        "customer_name": "Toko Denda", "base_amount": 5000000, "base": "installment", "amount": 100000.0,
        "original_amount": 100000.0, "days_late": 30, "billable_days": 30, "rate_pct_per_month": 2.0,
        "grace_days": 0, "cap_pct": 0, "status": "draft", "status_label": "Usulan", "paid_amount": 0.0,
        "je_id": "", "explain": [], "created_by": "uji", "created_at": now, "updated_at": now, "refs": []})
    awal = await _saldo(db)
    r = await klien.post(f"/api/penalties/{nid}/issue", headers=h)
    assert r.status_code == 200, r.text
    assert await _saldo(db) == awal + 100000
    return {"id": nid, "awal": awal, "number": f"DN-DENDA-PK08-{i}"}


async def _bayar(klien, h, nid, amount, account_id=None, key=None):
    body = {"amount": amount}
    if account_id is not None:
        body["account_id"] = account_id
    hh = dict(h)
    if key:
        hh["Idempotency-Key"] = key
    return await klien.post(f"/api/penalties/{nid}/pay", headers=hh, json=body)


async def _kas(db, nid):
    return [k async for k in db.cash_transactions.find({"ref_type": "penalty", "ref_id": nid}, {"_id": 0})]


async def _jurnal_kas(db, kid) -> int:
    return await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kid,
                                                     "status": {"$ne": "void"}})


async def test_U01_dua_kali_bayar_dua_jurnal(klien, db, kepala_admin, alasan):
    N = await _nota(klien, db, kepala_admin)
    ba = await _rekening(db)
    for n in (60000, 40000):
        r = await _bayar(klien, kepala_admin, N["id"], n, ba)
        assert r.status_code == 200, r.text
    kas = await _kas(db, N["id"])
    assert sorted(k["amount"] for k in kas) == [40000, 60000]
    for k in kas:
        assert await _jurnal_kas(db, k["id"]) == 1
    assert await _saldo(db) == N["awal"]
    p = await db.penalties.find_one({"id": N["id"]})
    assert p["status"] == "paid" and p["paid_amount"] == 100000
    assert [x["status"] for x in p["payments"]] == ["done", "done"]
    test_U01_dua_kali_bayar_dua_jurnal.rekening = ba


async def test_U02_saldo_rekening_ikut_bergerak(klien, kepala_admin):
    ba = test_U01_dua_kali_bayar_dua_jurnal.rekening
    r = await klien.get("/api/bank-accounts", headers=kepala_admin, params={"entity_id": E1})
    assert r.status_code == 200, r.text
    row = next(x for x in r.json() if x["id"] == ba)
    assert float(row["balance"]) == 100000


async def test_U03_bebas_hanya_sisa(klien, db, kepala_admin, alasan):
    N = await _nota(klien, db, kepala_admin)
    r = await _bayar(klien, kepala_admin, N["id"], 60000, await _rekening(db))
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/penalties/{N['id']}/waive", headers=kepala_admin,
                         json={"reason_code": "penalty_waiver", "note": "uji"})
    assert r.status_code == 200, r.text
    rev = [j async for j in db.journal_entries.find({"source_type": "penalty_reversal",
                                                     "source_id": {"$regex": f"^{N['id']}:"}}, {"_id": 0})]
    assert len(rev) == 1 and float(rev[0]["total_debit"]) == 40000
    assert await _saldo(db) == N["awal"]
    p = await db.penalties.find_one({"id": N["id"]})
    assert (p["status"], p["waived_amount"], p["amount"], p["paid_amount"]) == ("waived", 40000, 60000, 60000)


async def test_U04_ubah_dua_kali_dua_jurnal(klien, db, kepala_admin, alasan):
    N = await _nota(klien, db, kepala_admin)
    for n in (80000, 70000):
        r = await klien.post(f"/api/penalties/{N['id']}/adjust", headers=kepala_admin,
                             json={"amount": n, "reason_code": "penalty_negotiation"})
        assert r.status_code == 200, r.text
    rev = {j["source_id"]: float(j["total_debit"]) async for j in db.journal_entries.find(
        {"source_type": "penalty_reversal", "source_id": {"$regex": f"^{N['id']}:"}}, {"_id": 0})}
    assert rev == {f"{N['id']}:adjust:1": 20000, f"{N['id']}:adjust:2": 10000}
    assert await _saldo(db) == N["awal"] + 70000
    assert len((await db.penalties.find_one({"id": N["id"]}))["adjustments"]) == 2


async def test_U05_ubah_di_bawah_terbayar_ditolak(klien, db, kepala_admin, alasan):
    N = await _nota(klien, db, kepala_admin)
    r = await _bayar(klien, kepala_admin, N["id"], 60000, await _rekening(db))
    assert r.status_code == 200, r.text
    n_je = await db.journal_entries.count_documents({})
    r = await klien.post(f"/api/penalties/{N['id']}/adjust", headers=kepala_admin,
                         json={"amount": 50000, "reason_code": "penalty_negotiation"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Nominal baru tidak boleh lebih kecil dari yang sudah dibayar (Rp 60.000)."
    assert (await db.penalties.find_one({"id": N["id"]}))["amount"] == 100000
    assert await db.journal_entries.count_documents({}) == n_je


async def _rencana(db, pid: str, due: str = "2027-01-10") -> dict:
    so = f"so_{pid}"
    await db.sales_orders.insert_one({"id": so, "number": f"SO-{pid}", "entity_id": E1, "customer_id": "cus_pk08",
                                      "status": "confirmed", "grand_total": 3000000, "payments": [],
                                      "created_at": "2026-12-01T00:00:00+00:00"})
    plan = {"id": pid, "number": f"PP-{pid}", "entity_id": E1, "doc_type": "sales_order", "doc_id": so,
            "doc_number": f"SO-{pid}", "customer_id": "cus_pk08", "customer_name": "Toko Denda", "status": "active",
            "lines": [{"seq": 1, "label": "Cicilan 1", "due_date": due, "amount": 3000000, "paid_amount": 0,
                       "status": "open"}], "created_at": "2026-12-01T00:00:00+00:00"}
    await db.payment_plans.insert_one(dict(plan))
    return plan


async def test_U06_hari_telat_tidak_ditagih_dua_kali(db):
    from services import penalty_service as ps
    plan = await _rencana(db, "pp_pk08_u6")
    jan = (await ps.accrue_plan(plan, today="2027-01-31"))[0]
    feb = (await ps.accrue_plan(plan, today="2027-02-28"))[0]
    assert (jan["days_late"], jan["billable_days"], jan["amount"]) == (21, 21, 42000)
    assert (feb["days_late"], feb.get("days_prior"), feb["billable_days"], feb["amount"]) == (49, 21, 28, 56000)
    assert jan["billable_days"] + feb["billable_days"] == 49
    assert jan["amount"] + feb["amount"] == 98000


async def test_U07_tenggang_dipotong_sekali(db, kepala_admin, klien):
    from services import penalty_service as ps
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [
        {"key": "ar.grace_days", "value": 7, "scope_type": "entity", "scope_id": E1, "reason": "uji PK-08"}]})
    assert r.status_code == 200, r.text
    try:
        plan = await _rencana(db, "pp_pk08_u7")
        jan = (await ps.accrue_plan(plan, today="2027-01-31"))[0]
        feb = (await ps.accrue_plan(plan, today="2027-02-28"))[0]
        assert (jan["billable_days"], jan["amount"]) == (14, 28000)
        assert (feb["billable_days"], feb["amount"]) == (28, 56000)
        assert jan["billable_days"] + feb["billable_days"] == 42
    finally:
        await klien.post("/api/config/values/clear", headers=kepala_admin,
                         json={"key": "ar.grace_days", "scope_type": "entity", "scope_id": E1, "reason": "uji"})


async def test_U08_pesanan_tanpa_rencana(db):
    from services import penalty_service as ps
    order = {"id": "so_pk08_u8", "number": "SO-PK08-U8", "entity_id": E1, "customer_id": "cus_pk08",
             "status": "confirmed", "grand_total": 3000000, "payments": [], "payment_term_days": 0,
             "payment_term_code": "NET0", "created_at": "2027-01-10T00:00:00+00:00"}
    await db.sales_orders.insert_one(dict(order))
    jan = (await ps.accrue_order(order, today="2027-01-31"))[0]
    feb = (await ps.accrue_order(order, today="2027-02-28"))[0]
    assert (jan["billable_days"], jan["amount"]) == (21, 42000)
    assert (feb["billable_days"], feb["amount"]) == (28, 56000)


async def test_U09_hari_ini_dari_server(klien, db, kepala_admin):
    due = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)).date().isoformat()
    plan = await _rencana(db, "pp_pk08_u9", due=due)
    r = await klien.post(f"/api/payment-plans/{plan['id']}/accrue", headers=kepala_admin,
                         params={"today": "2099-01-01"})
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 0


async def test_U10_rekening_wajib_dan_milik_pt_nota(klien, db, kepala_admin, alasan):
    N = await _nota(klien, db, kepala_admin)
    r = await _bayar(klien, kepala_admin, N["id"], 60000)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Rekening penerima wajib dipilih."
    r = await _bayar(klien, kepala_admin, N["id"], 60000, await _rekening(db, E2))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Rekening tidak ditemukan atau bukan milik PT nota denda ini."
    assert await _kas(db, N["id"]) == []
    p = await db.penalties.find_one({"id": N["id"]})
    assert p["paid_amount"] == 0 and not p.get("payments")


async def test_U11_periode_tertutup(klien, db, kepala_admin, alasan):
    N = await _nota(klien, db, kepala_admin)
    ba = await _rekening(db)
    bulan = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
    c = await tutup_periode(E1, bulan)
    try:
        r = await _bayar(klien, kepala_admin, N["id"], 60000, ba)
        assert r.status_code == 409, r.text
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert await _kas(db, N["id"]) == []
    p = await db.penalties.find_one({"id": N["id"]})
    assert p["paid_amount"] == 0 and not p.get("payments")


async def test_U12_jurnal_gagal_lalu_diulang(klien, db, kepala_admin, alasan, paksa_jurnal_gagal):
    N = await _nota(klien, db, kepala_admin)
    ba = await _rekening(db)
    async with paksa_jurnal_gagal("sisip", entity_id=E1, source_type="cash_transaction", kali=1):
        r = await _bayar(klien, kepala_admin, N["id"], 60000, ba, key="k1")
    assert r.status_code == 409, r.text
    assert r.json()["detail"].startswith("Pembayaran denda sudah tercatat, tetapi jurnalnya gagal")
    kas = await _kas(db, N["id"])
    assert len(kas) == 1 and kas[0]["id"].startswith("cash_pnl_")
    assert (await db.cash_transactions.find_one({"id": kas[0]["id"]}))["gl_status"] == "failed"
    p = await db.penalties.find_one({"id": N["id"]})
    assert p["paid_amount"] == 60000 and [x["status"] for x in p["payments"]] == ["applied"]
    r = await _bayar(klien, kepala_admin, N["id"], 60000, ba, key="k1")
    assert r.status_code == 200, r.text
    kas = await _kas(db, N["id"])
    assert len(kas) == 1 and await _jurnal_kas(db, kas[0]["id"]) == 1
    p = await db.penalties.find_one({"id": N["id"]})
    assert p["paid_amount"] == 60000 and [x["status"] for x in p["payments"]] == ["done"]
    assert await _saldo(db) == N["awal"] + 40000


async def test_U13_kunci_sama_berurutan(klien, db, kepala_admin, alasan):
    N = await _nota(klien, db, kepala_admin)
    ba = await _rekening(db)
    for _ in range(2):
        r = await _bayar(klien, kepala_admin, N["id"], 60000, ba, key="k-sama")
        assert r.status_code == 200, r.text
    assert len(r.json()["payments"]) == 1
    assert len(await _kas(db, N["id"])) == 1
    assert (await db.penalties.find_one({"id": N["id"]}))["paid_amount"] == 60000
