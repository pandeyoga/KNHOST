"""PK-20 — kas dibuat lewat SATU pembuat yang mewajibkan rekening (docs/blueprint/unit/PK-20.md).

Persiapan bersama (fixture, disisipkan langsung): `ent_ksc` punya satu rekening Kas Kecil R-K (saldo awal Rp 1.000.000)
dan dua rekening Bank R-B1, R-B2; `ent_kanda` punya satu rekening Bank R-X. U12 (dua permintaan bersamaan) di MongoDB
asli: `backend/tests/test_bp_PK20_kas_bersamaan_mongo.py`.
"""
import pytest

from pembantu import jumlah, tutup_periode
from services import cash_ledger
from services.cash_ledger import CashPostingError, CashRejected

KSC, KANDA = "ent_ksc", "ent_kanda"
PANEL = "/api/finance/posting-failures"
REKENING = [
    {"id": "rek_k", "name": "Kas Kecil KSC", "entity_id": KSC, "account_type": "cash", "cash_type": "kas_kecil",
     "bank_name": "", "account_number": "", "is_active": True, "opening_balance": 1_000_000.0},
    {"id": "rek_b1", "name": "BCA KSC", "entity_id": KSC, "account_type": "bank", "cash_type": "kas_besar",
     "bank_name": "BCA", "account_number": "111", "is_active": True, "opening_balance": 0.0},
    {"id": "rek_b2", "name": "Mandiri KSC", "entity_id": KSC, "account_type": "bank", "cash_type": "kas_besar",
     "bank_name": "Mandiri", "account_number": "222", "is_active": True, "opening_balance": 0.0},
    {"id": "rek_x", "name": "BCA Kanda", "entity_id": KANDA, "account_type": "bank", "cash_type": "kas_besar",
     "bank_name": "BCA", "account_number": "333", "is_active": True, "opening_balance": 0.0},
]


@pytest.fixture(scope="module")
async def rekening(db):
    await db.bank_accounts.insert_many([dict(r) for r in REKENING])
    return True


async def _saldo_rekening(account_id: str) -> float:
    """Saldo awal rekening + Σ mutasi kas yang MENUNJUK rekening itu (tanpa kas lama tak-berekening dari seed, yang
    `bank_service._txns_for` serap ke rekening tunggal PT)."""
    from services import bank_service
    led = await bank_service.account_ledger(account_id)
    sendiri = [t for t in led["transactions"] if t.get("account_id") == account_id]
    return round(float(led.get("opening_balance") or 0)
                 + sum(t["amount"] if t["direction"] == "in" else -t["amount"] for t in sendiri), 2)


def _sewa(**kw):
    base = dict(entity_id=KSC, direction="out", amount=250_000, cash_type="kas_kecil", category="sewa",
                description="Sewa gudang November", ref_type="manual", ref_id="pk20_u1", actor="Uji")
    base.update(kw)
    return base


async def test_PK20_U1_kas_keluar_rekening_tunggal(db, rekening):
    kas = await cash_ledger.create_cash(**_sewa())
    # Rekening tidak dikirim, PT punya SATU rekening Kas Kecil → R-K; akun kas dari jenis rekening (1-1110).
    assert kas["account_id"] == "rek_k" and kas["cash_type"] == "kas_kecil" and kas["account_code"] == "1-1110"
    assert kas["id"] == cash_ledger.cash_id("manual", "pk20_u1", "out", "") and kas["gl_status"] == "posted"
    jes = await db.journal_entries.find({"source_type": "cash_transaction", "source_id": kas["id"]}).to_list(5)
    assert len(jes) == 1
    baris = {(ln["account_code"], ln["debit"], ln["credit"]) for ln in jes[0]["lines"]}
    # kategori "sewa" → lawan 6-2000 (CASH_OUT_KEYWORDS): Dr 6-2000 250.000 / Cr 1-1110 250.000
    assert baris == {("6-2000", 250_000.0, 0.0), ("1-1110", 0.0, 250_000.0)}
    assert kas["journal_entry_id"] == jes[0]["id"]
    # saldo R-K = saldo awal 1.000.000 − 250.000 = 750.000
    assert await _saldo_rekening("rek_k") == 750_000.0


async def test_PK20_U2_rujukan_sama_dipakai_ulang(db, rekening):
    kas = await cash_ledger.create_cash(**_sewa())
    assert kas["id"] == cash_ledger.cash_id("manual", "pk20_u1", "out", "")
    assert await jumlah("cash_transactions", {"ref_type": "manual", "ref_id": "pk20_u1"}) == 1
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 1
    assert await _saldo_rekening("rek_k") == 750_000.0


async def test_PK20_U3_bank_tanpa_rekening_ditolak(db, rekening):
    je0 = await jumlah("journal_entries", {})
    with pytest.raises(CashRejected) as e:
        await cash_ledger.create_cash(**_sewa(cash_type="kas_besar", ref_id="pk20_u3"))
    assert e.value.status_code == 409
    assert e.value.detail.startswith("Pilih rekening kas/bank untuk transaksi ini.")
    assert "punya 2 rekening Bank" in e.value.detail
    assert await jumlah("cash_transactions", {"ref_id": "pk20_u3"}) == 0
    assert await jumlah("journal_entries", {}) == je0


async def test_PK20_U4_rekening_pt_lain_ditolak(db, rekening):
    with pytest.raises(CashRejected) as e:
        await cash_ledger.create_cash(**_sewa(account_id="rek_x", ref_id="pk20_u4"))
    assert e.value.status_code == 409
    assert "Rekening BCA Kanda bukan rekening aktif" in e.value.detail
    assert await jumlah("cash_transactions", {"ref_id": "pk20_u4"}) == 0
    # rekening nonaktif milik PT sendiri juga ditolak
    await db.bank_accounts.update_one({"id": "rek_b2"}, {"$set": {"is_active": False}})
    try:
        with pytest.raises(CashRejected) as e2:
            await cash_ledger.create_cash(**_sewa(account_id="rek_b2", ref_id="pk20_u4b"))
        assert "bukan rekening aktif" in e2.value.detail
    finally:
        await db.bank_accounts.update_one({"id": "rek_b2"}, {"$set": {"is_active": True}})


async def test_PK20_U5_periode_tertutup_ditolak(db, rekening):
    c = await tutup_periode(KSC, "2026-10")
    je0 = await jumlah("journal_entries", {})
    try:
        with pytest.raises(CashRejected) as e:
            await cash_ledger.create_cash(**_sewa(ref_id="pk20_u5", txn_date="2026-10-15"))
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert e.value.status_code == 409 and "DITUTUP" in e.value.detail
    assert await jumlah("cash_transactions", {"ref_id": "pk20_u5"}) == 0
    assert await jumlah("journal_entries", {}) == je0


async def test_PK20_U6a_jurnal_gagal_kas_tersimpan_lalu_diulang(klien, kepala_admin, db, rekening,
                                                                paksa_jurnal_gagal):
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="6-2000"):
        with pytest.raises(CashPostingError) as e:
            await cash_ledger.create_cash(**_sewa(ref_id="pk20_u6a"))
    assert e.value.status_code == 409 and "Transaksi tersimpan dan bisa diulang dari Posting Gagal" in e.value.detail
    kas = e.value.txn
    assert kas["gl_status"] == "failed" and "6-2000" in kas["gl_error"]
    assert await jumlah("cash_transactions", {"ref_id": "pk20_u6a"}) == 1
    panel = (await klien.get(PANEL, headers=kepala_admin, params={"kind": "cash_transaction"})).json()
    assert any(i["id"] == kas["id"] for i in panel["items"])
    r = await klien.post(f"{PANEL}/cash_transaction/{kas['id']}/retry", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert (await db.cash_transactions.find_one({"id": kas["id"]}))["gl_status"] == "posted"
    assert await jumlah("cash_transactions", {"ref_id": "pk20_u6a"}) == 1
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 1


async def test_PK20_U7_rujukan_sama_nominal_beda_ditolak(db, rekening):
    with pytest.raises(CashRejected) as e:
        await cash_ledger.create_cash(**_sewa(amount=300_000))
    assert e.value.status_code == 409
    assert "sudah tercatat dengan nominal Rp 250.000" in e.value.detail
    assert await jumlah("cash_transactions", {"ref_id": "pk20_u1"}) == 1
    assert (await db.cash_transactions.find_one({"ref_id": "pk20_u1"}))["amount"] == 250_000


async def test_PK20_inti_id_seq_jurnal_induk_dan_void(db, rekening):
    # seq membedakan dua kas searah satu dokumen; rekening dikirim → jenis kas dari rekening (bukan dari pemanggil)
    a = await cash_ledger.create_cash(entity_id=KSC, direction="in", amount=100_000, ref_type="manual",
                                      ref_id="pk20_seq", seq="p1", account_id="rek_b1", cash_type="kas_kecil")
    b = await cash_ledger.create_cash(entity_id=KSC, direction="in", amount=50_000, ref_type="manual",
                                      ref_id="pk20_seq", seq="p2", account_id="rek_b1")
    assert a["id"] != b["id"] and a["cash_type"] == "kas_besar" and a["account_code"] == "1-1100"
    assert a["seq"] == "p1" and b["seq"] == "p2"
    # jurnal induk: tanpa jurnal kas kedua, gl_status not_required, tautan ke jurnal induk tetap
    from pembantu import jurnal
    induk = await jurnal(KSC, "2026-11-10", [("1-1100", 75_000, 0), ("4-1000", 0, 75_000)], "induk", "pk20_induk")
    c = await cash_ledger.create_cash(entity_id=KSC, direction="in", amount=75_000, ref_type="sales_return",
                                      ref_id="pk20_induk", cash_type="kas_besar", account_id="rek_b2",
                                      journal_by_parent=induk["id"])
    assert c["gl_status"] == "not_required" and c["gl_posted"] is True and c["journal_entry_id"] == induk["id"]
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": c["id"]}) == 0
    # jurnal induk memakai akun Bank → rekening Kas Kecil ditolak
    with pytest.raises(CashRejected):
        await cash_ledger.create_cash(entity_id=KSC, direction="in", amount=10_000, ref_type="sales_return",
                                      ref_id="pk20_induk2", cash_type="kas_besar", account_id="rek_k",
                                      journal_by_parent=induk["id"])
    # kas yang sudah void: rujukan yang sama melahirkan kejadian berikutnya di id generasi kedua
    await db.cash_transactions.update_one({"id": b["id"]}, {"$set": {"status": "void"}})
    b2 = await cash_ledger.create_cash(entity_id=KSC, direction="in", amount=50_000, ref_type="manual",
                                       ref_id="pk20_seq", seq="p2", account_id="rek_b1")
    assert b2["id"] == cash_ledger.cash_id("manual", "pk20_seq", "in", "p2#2") and b2["status"] == "posted"
    # `extra` tidak menimpa field inti; `number` yang sudah dipesan dipakai
    d = await cash_ledger.create_cash(entity_id=KSC, direction="out", amount=1_000, ref_type="manual",
                                      ref_id="pk20_extra", account_id="rek_b1",
                                      extra={"number": "CASH-PESAN-1", "amount": 9, "payment_intent_id": "x"})
    assert d["number"] == "CASH-PESAN-1" and d["amount"] == 1_000 and d["payment_intent_id"] == "x"
    # grup / nominal / arah / rujukan kosong
    for kw in ({"entity_id": "all"}, {"amount": 0}, {"direction": "x"}, {"ref_id": ""}):
        with pytest.raises(CashRejected):
            await cash_ledger.create_cash(**{**_sewa(ref_id="pk20_bad"), **kw})


async def test_PK20_ensure_posted(db, rekening):
    kas = await db.cash_transactions.find_one({"ref_id": "pk20_u1"}, {"_id": 0})
    je = await cash_ledger.ensure_posted(kas["id"])
    assert je and je["source_id"] == kas["id"]
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 1
    assert await cash_ledger.ensure_posted("cash_tidak_ada") is None


# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  Serah-terima (b) — pemanggil dialihkan ke pembuat kas
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
DIBUAT: list = []   # id kas yang lahir di modul ini (U11)


async def test_PK20_U6b_kas_manual_jurnal_gagal_tersimpan(klien, kepala_admin, db, rekening, paksa_jurnal_gagal):
    body = {"cash_type": "kas_kecil", "direction": "out", "amount": 250_000, "category": "sewa",
            "description": "Sewa gudang (U6b)"}
    h = {**kepala_admin, "Idempotency-Key": "pk20-u6b"}
    async with paksa_jurnal_gagal("akun", entity_id=KSC, kode_akun="6-2000"):
        r = await klien.post("/api/cash-transactions", headers=h, json=body)
    assert r.status_code == 409, r.text
    assert "Jurnal kas gagal" in r.text and "Transaksi tersimpan dan bisa diulang dari Posting Gagal" in r.text
    kas = await db.cash_transactions.find_one({"ref_type": "manual", "ref_id": "pk20-u6b"}, {"_id": 0})
    assert kas and kas["gl_status"] == "failed" and kas["account_id"] == "rek_k"
    panel = (await klien.get(PANEL, headers=kepala_admin, params={"kind": "cash_transaction"})).json()
    assert any(i["id"] == kas["id"] for i in panel["items"])
    r2 = await klien.post(f"{PANEL}/cash_transaction/{kas['id']}/retry", headers=kepala_admin)
    assert r2.status_code == 200, r2.text
    assert (await db.cash_transactions.find_one({"id": kas["id"]}))["gl_status"] == "posted"
    assert await jumlah("cash_transactions", {"ref_id": "pk20-u6b"}) == 1
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 1
    # kas manual tanpa rekening & PT punya dua rekening Bank → 409, tidak ada kas
    r3 = await klien.post("/api/cash-transactions", headers={**kepala_admin, "Idempotency-Key": "pk20-u6b-2"},
                          json={**body, "cash_type": "kas_besar"})
    assert r3.status_code == 409 and "Pilih rekening kas/bank" in r3.text, r3.text
    assert await jumlah("cash_transactions", {"ref_id": "pk20-u6b-2"}) == 0
    # batal kas manual (ref_type "manual") tetap bisa lewat layar kas
    r4 = await klien.post(f"/api/cash-transactions/{kas['id']}/void", headers=kepala_admin,
                          json={"reason": "uji batal PK-20"})
    assert r4.status_code == 200, r4.text
    assert await jumlah("journal_entries", {"source_type": "cash_transaction_void", "source_id": kas["id"]}) == 1


async def test_PK20_U8_refund_retur_berekening_dijurnal_induk(db, rekening):
    # Fixture: jurnal nota kredit retur (induk) yang sudah mengkredit 1-1110 Rp 400.000; kas refund lewat
    # `record_return_cash` (jalur yang dipanggil penyelesaian retur) — rekening dari jenis kas akun 1-1110.
    from pembantu import jurnal
    cn = await jurnal(KSC, "2026-11-12", [("4-1000", 400_000, 0), ("1-1110", 0, 400_000)], "CN retur uji",
                      "pk20_u8")
    kas = await cash_ledger.record_return_cash(
        direction="out", amount=400_000, account_code="1-1110", category="Refund Retur Jual",
        description="Refund tunai retur uji PK-20", entity_id=KSC, ref_type="sales_return", ref_id="sr_pk20_u8",
        journal_entry_id=cn["id"], created_by="Uji")
    DIBUAT.append(kas["id"])
    assert kas["account_id"] == "rek_k" and kas["account_code"] == "1-1110"
    assert kas["gl_status"] == "not_required" and kas["journal_entry_id"] == cn["id"]
    assert await jumlah("journal_entries", {"source_type": "cash_transaction", "source_id": kas["id"]}) == 0
    # idempoten per rujukan
    lagi = await cash_ledger.record_return_cash(
        direction="out", amount=400_000, account_code="1-1110", category="Refund Retur Jual",
        description="Refund tunai retur uji PK-20", entity_id=KSC, ref_type="sales_return", ref_id="sr_pk20_u8",
        journal_entry_id=cn["id"], created_by="Uji")
    assert lagi["id"] == kas["id"] and await jumlah("cash_transactions", {"ref_id": "sr_pk20_u8"}) == 1


async def test_PK20_U9_bayar_landed_cost_entitas_voucher(klien, kepala_admin, db, rekening):
    await db.landed_cost_vouchers.insert_one({
        "id": "lcv_pk20", "voucher_number": "LCV/PK20/1", "entity_id": KSC, "status": "applied",
        "total_cost": 500_000, "amount_paid": 0.0, "payments": [], "timeline": [], "provider_name": "Ekspedisi Uji"})
    r = await klien.post("/api/landed-costs/lcv_pk20/pay", headers=kepala_admin, json={
        "amount": 500_000, "entity_id": KANDA, "cash_type": "kas_kecil", "account_id": "rek_b1",
        "method": "transfer", "paid_at": "2026-11-13"})
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find_one({"ref_type": "landed_cost", "ref_id": "lcv_pk20"}, {"_id": 0})
    DIBUAT.append(kas["id"])
    assert kas["entity_id"] == KSC and kas["account_id"] == "rek_b1" and kas["cash_type"] == "kas_besar"
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas["id"]}, {"_id": 0})
    assert je["entity_id"] == KSC
    # Dr 2-1100 Hutang 500.000 / Cr 1-1100 Bank 500.000
    assert {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]} == \
        {("2-1100", 500_000.0, 0.0), ("1-1100", 0.0, 500_000.0)}
    v = await db.landed_cost_vouchers.find_one({"id": "lcv_pk20"}, {"_id": 0})
    assert v["payments"][0]["cash_txn_id"] == kas["id"] and kas["seq"] == v["payments"][0]["id"]
    assert await jumlah("cash_transactions", {"entity_id": KANDA, "ref_id": "lcv_pk20"}) == 0


async def test_PK20_U10_kwitansi_berekening(klien, kepala_admin, db, rekening):
    from core_utils import now_iso
    await db.customers.insert_one({"id": "cus_pk20", "name": "Toko PK20", "entity_id": KSC, "status": "active"})
    for so in ("so_pk20a", "so_pk20b"):
        await db.sales_orders.insert_one({
            "id": so, "number": f"SO-{so}", "entity_id": KSC, "customer_id": "cus_pk20", "customer_name": "Toko PK20",
            "status": "confirmed", "grand_total": 2_000_000, "payments": [], "paid_total": 0,
            "payment_status": "unpaid", "payment_term_code": "NET30", "created_at": now_iso()})
    r = await klien.post("/api/ar-receipts", headers=kepala_admin, json={
        "customer_id": "cus_pk20", "amount": 2_000_000, "method": "transfer", "entity_id": KSC,
        "account_id": "rek_b2", "allocations": [{"order_id": "so_pk20a", "amount": 2_000_000}]})
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": r.json()["id"]}, {"_id": 0})
    DIBUAT.append(kas["id"])
    assert kas["account_id"] == "rek_b2" and kas["gl_status"] == "posted"
    n_rc = await jumlah("ar_receipts", {"customer_id": "cus_pk20"})
    n_kas = await jumlah("cash_transactions", {"ref_type": "ar_receipt"})
    r2 = await klien.post("/api/ar-receipts", headers=kepala_admin, json={
        "customer_id": "cus_pk20", "amount": 2_000_000, "method": "transfer", "entity_id": KSC,
        "allocations": [{"order_id": "so_pk20b", "amount": 2_000_000}]})
    assert r2.status_code == 409 and "Pilih rekening kas/bank" in r2.text, r2.text
    assert await jumlah("ar_receipts", {"customer_id": "cus_pk20"}) == n_rc
    assert await jumlah("cash_transactions", {"ref_type": "ar_receipt"}) == n_kas
    so_b = await db.sales_orders.find_one({"id": "so_pk20b"}, {"_id": 0})
    assert so_b["payments"] == [] and so_b.get("paid_total", 0) == 0


async def test_PK20_U11_saldo_rekening_sama_dengan_buku_besar(db, rekening):
    # Kas yang lahir di modul ini (U1, U2, U6a, U6b, U8–U10 dan uji inti): semuanya berekening milik ent_ksc, dan
    # per rekening Σ mutasi kas ber-gl_status posted = Σ (debit − kredit) baris jurnal kasnya pada akun kas rekening itu.
    rek_ksc = {r["id"]: r for r in REKENING if r["entity_id"] == KSC}
    kas = await db.cash_transactions.find(
        {"entity_id": KSC, "status": {"$ne": "void"}, "$or": [
            {"id": {"$in": DIBUAT}}, {"ref_type": "manual", "ref_id": {"$regex": "^pk20"}}]}, {"_id": 0}).to_list(None)
    assert len(kas) >= 6
    assert all(k["account_id"] in rek_ksc for k in kas), [(k["id"], k.get("account_id")) for k in kas]
    for rid, rk in rek_ksc.items():
        mine = [k for k in kas if k["account_id"] == rid and k.get("gl_status") == "posted"]
        mutasi = round(sum(k["amount"] if k["direction"] == "in" else -k["amount"] for k in mine), 2)
        kode = "1-1110" if rk["cash_type"] == "kas_kecil" else "1-1100"
        jes = await db.journal_entries.find({"source_type": "cash_transaction",
                                             "source_id": {"$in": [k["id"] for k in mine]}}, {"_id": 0}).to_list(None)
        buku = round(sum(ln["debit"] - ln["credit"] for je in jes for ln in je["lines"] if ln["account_code"] == kode), 2)
        assert mutasi == buku, (rid, mutasi, buku)
