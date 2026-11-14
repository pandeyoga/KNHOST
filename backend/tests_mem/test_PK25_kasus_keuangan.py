"""PK-25 — kasus keuangan: periksa dulu, efek kemudian; salah PT melahirkan dokumen antar-PT; pemindai tidak mengulang.

docs/blueprint/unit/PK-25.md, uji penerimaan U1–U13 (lingkungan B). Pesanan, kwitansi, mutasi titipan, dan kasus yang
sudah diputus = fixture (disisipkan); pembuatan kasus, penyelesaian, panel Posting Gagal, pelunasan antar-PT, dan
pemindai = alur lewat API. Tiap uji membuat pelanggan dan pesanannya sendiri.

Hitung tangan (contoh `00` §9):
  U1  A1 Rp 1.000.000, kwitansi 993.500 → sisa 6.500. Biaya bank 6.500 → baris `kasus` 6.500 di A1
      (1.000.000 − 993.500 − 6.500 = 0) + jurnal Dr 6-8000 Beban Administrasi Bank 6.500 / Cr 1-1200 Piutang 6.500.
  U5  kasus yang sama memuat A3 Rp 500.000 berkwitansi 498.000 (sisa 2.000): penyelesaian kedua → jurnal kedua
      Dr 6-8000 2.000 / Cr 1-1200 2.000 (kunci `…:chg:<n>` beda dari penyelesaian pertama); A3 sisa 0.
  U6  titipan Rp 2.000.000 di `ent_kanda` (Dr 1-1100 / Cr 2-1950) ternyata pelunasan A2 `ent_ksc` Rp 2.000.000:
      `ent_kanda` Dr 2-1950 2.000.000 / Cr 2-1250 Utang antar-PT 2.000.000;
      `ent_ksc`   Dr 1-1250 Piutang antar-PT 2.000.000 / Cr 1-1200 Piutang 2.000.000; A2 lunas;
      dokumen antar-PT `salah_transfer` sisa 2.000.000 = saldo non-dagang `ent_ksc` → `ent_kanda`.
  U7  pelunasan 2.000.000: `ent_kanda` Dr 2-1250 / Cr 1-1100 (kas keluar), `ent_ksc` Dr 1-1100 / Cr 1-1250 (kas
      masuk) → 1-1250 `ent_ksc` dan 2-1250 `ent_kanda` kembali ke saldo sebelum U6; saldo non-dagang 0.
"""
from __future__ import annotations

import datetime
import itertools
import uuid

import pytest

from core_utils import now_iso
from pembantu import aktifkan_akun, jurnal, nonaktifkan_akun, saldo_akun

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
JT = 1_000_000
PANEL = "/api/finance/posting-failures"
_n = itertools.count(1)


def _id(awal: str) -> str:
    return f"{awal}_pk25_{uuid.uuid4().hex[:8]}"


def _hari(geser: int = 0) -> str:
    from services.book_date import tanggal_buku
    return (datetime.date.fromisoformat(tanggal_buku()) + datetime.timedelta(days=geser)).isoformat()


def _h(kepala, ent=KSC):
    return {**kepala, "X-Entity-Id": ent}


@pytest.fixture(scope="module")
async def dunia(db):
    from services import amendment_service
    await amendment_service.ensure_reasons()
    await db.bank_accounts.insert_many([
        {"id": "rek_pk25_ksc", "name": "Bank KSC PK25", "entity_id": KSC, "account_type": "bank",
         "cash_type": "kas_besar", "is_active": True, "opening_balance": 0, "created_at": "2000-01-01T00:00:00"},
        {"id": "rek_pk25_kanda", "name": "Bank Kanda PK25", "entity_id": KANDA, "account_type": "bank",
         "cash_type": "kas_besar", "is_active": True, "opening_balance": 0, "created_at": "2000-01-01T00:00:00"}])
    return True


async def _pelanggan(db, ent=KSC, deposit=0.0) -> str:
    cus = _id("cus")
    await db.customers.insert_one({"id": cus, "name": f"Toko PK25 {next(_n)}", "entity_id": ent, "status": "active",
                                   "deposit_balance": float(deposit), "created_at": now_iso()})
    return cus


async def _pesanan(db, cus, total, dibayar=0.0, ent=KSC) -> dict:
    """Fixture: pesanan terkirim + (bila `dibayar`) kwitansi kas yang menempel."""
    so, rc = _id("so"), _id("rc")
    i = next(_n)
    pays = []
    if dibayar:
        pays = [{"id": f"pay_{rc}", "kind": "kas", "amount": float(dibayar), "receipt_id": rc,
                 "receipt_number": f"KW-PK25-{i}", "method": "transfer", "date": now_iso(), "created_at": now_iso()}]
        await db.ar_receipts.insert_one({
            "id": rc, "number": f"KW-PK25-{i}", "entity_id": ent, "customer_id": cus, "amount": float(dibayar),
            "status": "posted", "receipt_date": _hari(-30), "created_at": "2026-01-01T00:00:00",
            "allocations": [{"order_id": so, "amount": float(dibayar)}]})
    await db.sales_orders.insert_one({
        "id": so, "number": f"SO-PK25-{i}", "entity_id": ent, "customer_id": cus, "customer_name": "Toko PK25",
        "status": "shipped", "grand_total": float(total), "payments": pays, "paid_total": float(dibayar),
        "payment_status": "partial" if dibayar else "unpaid", "payment_term_code": "NET30", "items": [],
        "created_at": now_iso()})
    return {"id": so, "rc": rc}


async def _baris_kasus(db, so):
    o = await db.sales_orders.find_one({"id": so}, {"_id": 0})
    return [p for p in o.get("payments") or [] if p.get("kind") == "kasus"]


async def _sisa(db, so) -> float:
    o = await db.sales_orders.find_one({"id": so}, {"_id": 0})
    return round(float(o["grand_total"]) - sum(float(p.get("amount") or 0) for p in o.get("payments") or []), 2)


async def _jurnal_kasus(db, cid):
    return [j async for j in db.journal_entries.find(
        {"source_type": "finance_case", "source_id": {"$regex": f"^{cid}:"}, "status": {"$ne": "void"}}, {"_id": 0})]


def _baris_je(je):
    return sorted((ln["account_code"], float(ln.get("debit") or 0), float(ln.get("credit") or 0))
                  for ln in je["lines"])


async def _kasus_biaya_bank(klien, kepala, cus, orders, rc, amount):
    r = await klien.post("/api/finance-cases", headers=_h(kepala), json={
        "case_type": "selisih_biaya_bank", "amount": amount, "customer_id": cus, "order_ids": orders,
        "source": {"kind": "ar_receipt", "id": rc, "label": "Kwitansi uji"}})
    assert r.status_code == 200, r.text
    return r.json()


async def _biaya_bank(klien, kepala, cid, so, amount):
    return await klien.post(f"/api/finance-cases/{cid}/resolve", headers=_h(kepala), json={
        "action": "bebankan_biaya_bank", "reason_code": "bank_charge", "order_id": so, "amount": amount})


# ── U1–U5: periksa dulu, efek kemudian; kunci jurnal per kejadian ────────────────────────────────────────────────────
async def test_PK25_U1_biaya_bank_satu_baris_satu_jurnal(klien, db, kepala_admin, dunia):
    cus = await _pelanggan(db)
    a1 = await _pesanan(db, cus, JT, 993_500)
    c = await _kasus_biaya_bank(klien, kepala_admin, cus, [a1["id"]], a1["rc"], 6_500)
    r = await _biaya_bank(klien, kepala_admin, c["id"], a1["id"], 6_500)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    assert [p["amount"] for p in await _baris_kasus(db, a1["id"])] == [6_500]
    assert await _sisa(db, a1["id"]) == 0          # 1.000.000 − 993.500 − 6.500
    jes = await _jurnal_kasus(db, c["id"])
    assert len(jes) == 1
    assert _baris_je(jes[0]) == [("1-1200", 0.0, 6_500.0), ("6-8000", 6_500.0, 0.0)]
    assert jes[0]["entity_id"] == KSC


async def test_PK25_U1b_jawaban_memuat_status_jurnal(klien, db, kepala_admin, dunia):
    cus = await _pelanggan(db)
    a1 = await _pesanan(db, cus, JT, 993_500)
    c = await _kasus_biaya_bank(klien, kepala_admin, cus, [a1["id"]], a1["rc"], 6_500)
    r = await _biaya_bank(klien, kepala_admin, c["id"], a1["id"], 6_500)
    assert r.status_code == 200, r.text
    j = r.json()
    jes = await _jurnal_kasus(db, c["id"])
    assert (j["gl_status"], j["journal_entry_id"]) == ("posted", jes[0]["id"])
    assert j["resolution_intent"]["status"] == "done"
    assert j["resolution_intent"]["op_id"] == f"{c['id']}_bebankan_biaya_bank_0"


async def test_PK25_U2_periode_tertutup_tanpa_tulisan(klien, db, kepala_admin, dunia, paksa_jurnal_gagal):
    from services.book_date import periode_buku
    cus = await _pelanggan(db)
    a1 = await _pesanan(db, cus, JT, 993_500)
    c = await _kasus_biaya_bank(klien, kepala_admin, cus, [a1["id"]], a1["rc"], 6_500)
    sebelum = await db.sales_orders.find_one({"id": a1["id"]}, {"_id": 0})
    async with paksa_jurnal_gagal("periode", entity_id=KSC, period_key=periode_buku()):
        r = await _biaya_bank(klien, kepala_admin, c["id"], a1["id"], 6_500)
    assert r.status_code == 409, r.text
    assert await db.sales_orders.find_one({"id": a1["id"]}, {"_id": 0}) == sebelum
    assert await _jurnal_kasus(db, c["id"]) == []
    k = await db.finance_cases.find_one({"id": c["id"]}, {"_id": 0})
    assert k["status"] == "open" and "resolution_intent" not in k and "saga_lock" not in k


async def test_PK25_U2b_sakelar_kunci_dokumen_mati_tetap_diperiksa(klien, db, kepala_admin, dunia,
                                                                    paksa_jurnal_gagal):
    """Tambahan: `periode.kunci_dokumen` mati untuk PT itu (pemeriksa PK-37 meloloskan) — pemeriksa awal kasus tetap
    memeriksa periode jurnalnya, jadi pesanan tidak berubah dan tidak ada jurnal (dulu: baris pelunasan tertulis lalu
    jurnalnya ditolak penjaga periode)."""
    from services import config_resolver as resolver
    from services.book_date import periode_buku
    cus = await _pelanggan(db)
    a1 = await _pesanan(db, cus, JT, 993_500)
    c = await _kasus_biaya_bank(klien, kepala_admin, cus, [a1["id"]], a1["rc"], 6_500)
    sebelum = await db.sales_orders.find_one({"id": a1["id"]}, {"_id": 0})
    await resolver.set_value("periode.kunci_dokumen", False, scope_type="entity", scope_id=KSC, actor="uji",
                             reason="uji PK-25 U2b")
    try:
        async with paksa_jurnal_gagal("periode", entity_id=KSC, period_key=periode_buku()):
            r = await _biaya_bank(klien, kepala_admin, c["id"], a1["id"], 6_500)
    finally:
        await resolver.clear_layer("periode.kunci_dokumen", scope_type="entity", scope_id=KSC, actor="uji",
                                   reason="uji PK-25 U2b")
    assert r.status_code == 409, r.text
    assert await db.sales_orders.find_one({"id": a1["id"]}, {"_id": 0}) == sebelum
    assert await _jurnal_kasus(db, c["id"]) == []
    assert "resolution_intent" not in await db.finance_cases.find_one({"id": c["id"]}, {"_id": 0})


async def test_PK25_U3_jurnal_gagal_lalu_ulang_dari_panel(klien, db, kepala_admin, dunia):
    cus = await _pelanggan(db)
    a1 = await _pesanan(db, cus, JT, 993_500)
    c = await _kasus_biaya_bank(klien, kepala_admin, cus, [a1["id"]], a1["rc"], 6_500)
    await nonaktifkan_akun(KSC, "6-8000")
    try:
        r = await _biaya_bank(klien, kepala_admin, c["id"], a1["id"], 6_500)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] != "resolved" and j["gl_status"] == "failed", j
        assert "6-8000" in j["gl_error"]
        assert j["resolution_intent"]["status"] == "pending"
        assert [p["amount"] for p in await _baris_kasus(db, a1["id"])] == [6_500]
        assert await _jurnal_kasus(db, c["id"]) == []
        p = await klien.get(PANEL, headers=_h(kepala_admin), params={"kind": "finance_case"})
        assert p.status_code == 200, p.text
        assert c["id"] in [row["id"] for row in p.json()["items"]], p.json()
        # Isi berbeda selama niat belum tuntas → 409 (tidak ada efek baru).
        r2 = await _biaya_bank(klien, kepala_admin, c["id"], a1["id"], 6_000)
        assert r2.status_code == 409, r2.text
        assert r2.json()["detail"] == (f"Kasus {c['number']} punya penyelesaian \"Bebankan selisih ke biaya bank\" "
                                       "yang belum tuntas. Lanjutkan penyelesaian itu dari Posting Gagal.")
        assert [p["amount"] for p in await _baris_kasus(db, a1["id"])] == [6_500]
        # Ulang dari panel selagi akun masih nonaktif → masih gagal, tanpa baris baru.
        g = await klien.post(f"{PANEL}/finance_case/{c['id']}/retry", headers=_h(kepala_admin))
        assert g.status_code == 409, g.text
        assert [p["amount"] for p in await _baris_kasus(db, a1["id"])] == [6_500]
    finally:
        await aktifkan_akun(KSC, "6-8000")
    g = await klien.post(f"{PANEL}/finance_case/{c['id']}/retry", headers=_h(kepala_admin))
    assert g.status_code == 200, g.text
    assert g.json()["gl_status"] == "posted"
    assert [p["amount"] for p in await _baris_kasus(db, a1["id"])] == [6_500]
    jes = await _jurnal_kasus(db, c["id"])
    assert len(jes) == 1 and _baris_je(jes[0]) == [("1-1200", 0.0, 6_500.0), ("6-8000", 6_500.0, 0.0)]
    k = await db.finance_cases.find_one({"id": c["id"]}, {"_id": 0})
    assert (k["status"], k["gl_status"], k["resolution_intent"]["status"]) == ("resolved", "posted", "done")
    assert "saga_lock" not in k
    assert len([d for d in k["documents"] if d["kind"] == "journal_entry"]) == 1


async def test_PK25_U4_execute_diulang_mengadopsi(klien, db, kepala_admin, dunia):
    from services import finance_case_actions as acts
    cus = await _pelanggan(db)
    a1 = await _pesanan(db, cus, JT, 993_500)
    c = await _kasus_biaya_bank(klien, kepala_admin, cus, [a1["id"]], a1["rc"], 6_500)
    awal = await db.finance_cases.find_one({"id": c["id"]}, {"_id": 0})   # potret saat mulai (0 dokumen)
    r = await _biaya_bank(klien, kepala_admin, c["id"], a1["id"], 6_500)
    assert r.status_code == 200, r.text
    je1 = (await _jurnal_kasus(db, c["id"]))[0]
    # Aksi yang sama dengan op_id yang sama (`{kasus}_{aksi}_0`, dari potret awal) dijalankan lagi.
    res = await acts.execute("bebankan_biaya_bank", awal, {"order_id": a1["id"], "amount": 6_500},
                             {"name": "Uji", "role": "admin"})
    assert [p["amount"] for p in await _baris_kasus(db, a1["id"])] == [6_500]
    assert [d["id"] for d in res["documents"] if d["kind"] == "journal_entry"] == [je1["id"]]
    assert len(await _jurnal_kasus(db, c["id"])) == 1


async def test_PK25_U5_penyelesaian_kedua_jurnal_kedua(klien, db, kepala_admin, dunia):
    cus = await _pelanggan(db)
    a1 = await _pesanan(db, cus, JT, 993_500)
    a3 = await _pesanan(db, cus, 500_000, 498_000)
    c = await _kasus_biaya_bank(klien, kepala_admin, cus, [a1["id"], a3["id"]], a1["rc"], 6_500)
    r = await _biaya_bank(klien, kepala_admin, c["id"], a1["id"], 6_500)
    assert r.status_code == 200, r.text
    # Fixture "kasus dibuka kembali": `reopen` menolak kasus yang sudah berdokumen (buku tambah-saja), jadi keadaan
    # terbuka-kembali disisipkan langsung (lihat laporan, usulan koreksi U5).
    await db.finance_cases.update_one({"id": c["id"]}, {"$set": {"status": "in_progress", "resolved_by": "",
                                                                "resolved_at": ""}})
    r = await _biaya_bank(klien, kepala_admin, c["id"], a3["id"], 2_000)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    assert await _sisa(db, a3["id"]) == 0          # 500.000 − 498.000 − 2.000
    jes = sorted(await _jurnal_kasus(db, c["id"]), key=lambda j: j["total_debit"])
    assert len(jes) == 2
    assert _baris_je(jes[0]) == [("1-1200", 0.0, 2_000.0), ("6-8000", 2_000.0, 0.0)]
    assert _baris_je(jes[1]) == [("1-1200", 0.0, 6_500.0), ("6-8000", 6_500.0, 0.0)]
    assert len({j["source_id"] for j in jes}) == 2


# ── U6–U9: salah PT melahirkan dokumen antar-PT ──────────────────────────────────────────────────────────────────────
async def _titipan_kanda(db, nominal=2 * JT, tanggal=None) -> str:
    """Fixture: mutasi masuk Rp 2.000.000 di rekening `ent_kanda` yang dititipkan (Dr 1-1100 / Cr 2-1950)."""
    ln = _id("bsl")
    await db.bank_statement_lines.insert_one({
        "id": ln, "entity_id": KANDA, "bank_account_id": "rek_pk25_kanda", "direction": "in", "amount": float(nominal),
        "status": "holding", "holding_remaining": float(nominal), "holding_allocated": [], "holding_settled": [],
        "stmt_date": tanggal or _hari(), "description": "TRF PELANGGAN PK25", "created_at": now_iso()})
    await jurnal(KANDA, _hari(), [("1-1100", nominal, 0), ("2-1950", 0, nominal)], "titipan uji PK-25", f"tit:{ln}")
    return ln


async def _kasus_salah_pt(klien, db, kepala):
    cus = await _pelanggan(db)
    a2 = await _pesanan(db, cus, 2 * JT)
    ln = await _titipan_kanda(db)
    r = await klien.post("/api/finance-cases", headers=_h(kepala, KANDA), json={
        "case_type": "salah_entitas", "amount": 2 * JT, "customer_id": cus, "order_ids": [a2["id"]],
        "entity_id": KANDA, "source": {"kind": "bank_holding", "id": ln, "label": "Mutasi uji"}})
    assert r.status_code == 200, r.text
    return {"case": r.json(), "a2": a2["id"], "ln": ln, "cus": cus}


async def _salah_pt(klien, kepala, K):
    return await klien.post(f"/api/finance-cases/{K['case']['id']}/resolve", headers=_h(kepala, KANDA), json={
        "action": "settlement_antar_entitas", "reason_code": "case_wrong_entity", "owner_entity_id": KSC,
        "order_id": K["a2"], "amount": 2 * JT})


async def _non_dagang() -> float:
    from services import interco_money_service as money
    return (await money.non_trade_outstanding(KSC, KANDA))["non_trade_outstanding"]


SIMPAN: dict = {}


async def test_PK25_U6_salah_pt_jurnal_dua_buku_dan_dokumen_antar_pt(klien, db, kepala_admin, dunia):
    K = await _kasus_salah_pt(klien, db, kepala_admin)
    SIMPAN["awal"] = {"ar": await saldo_akun("1-1250", KSC), "ap": await saldo_akun("2-1250", KANDA),
                      "nt": await _non_dagang()}
    r = await _salah_pt(klien, kepala_admin, K)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    jes = {j["entity_id"]: j for j in await _jurnal_kasus(db, K["case"]["id"])}
    assert set(jes) == {KSC, KANDA}
    assert _baris_je(jes[KANDA]) == [("2-1250", 0.0, 2e6), ("2-1950", 2e6, 0.0)]
    assert _baris_je(jes[KSC]) == [("1-1200", 0.0, 2e6), ("1-1250", 2e6, 0.0)]
    o = await db.sales_orders.find_one({"id": K["a2"]}, {"_id": 0})
    assert o["payment_status"] == "paid" and await _sisa(db, K["a2"]) == 0
    pair = [d async for d in db.interco_loans.find({"pair_id": f"iclp_case_{K['case']['id']}"}, {"_id": 0})]
    assert sorted((d["role"], d["entity_id"]) for d in pair) == [("borrower", KANDA), ("lender", KSC)]
    for d in pair:
        assert (d["kind"], d["status"], d["outstanding"], d["principal"]) == ("salah_transfer", "disbursed", 2e6, 2e6)
        assert d["origin"] == {"kind": "finance_case", "id": K["case"]["id"], "number": K["case"]["number"]}
    assert await _non_dagang() == SIMPAN["awal"]["nt"] + 2 * JT
    assert round(await saldo_akun("1-1250", KSC) - SIMPAN["awal"]["ar"], 2) == 2 * JT
    assert round(await saldo_akun("2-1250", KANDA) - SIMPAN["awal"]["ap"], 2) == 2 * JT    # saldo normal kredit
    ln = await db.bank_statement_lines.find_one({"id": K["ln"]}, {"_id": 0})
    assert ln["holding_remaining"] == 0
    k = await db.finance_cases.find_one({"id": K["case"]["id"]}, {"_id": 0})
    tautan = [d for d in k["documents"] if d["kind"] == "interco_loan"]
    # Tautan ke dokumen di PT kasus (PT penerima uang = peminjam), yang terlihat oleh petugas kasus itu.
    assert [d["id"] for d in tautan] == [next(d["id"] for d in pair if d["role"] == "borrower")]
    assert tautan[0]["label"].startswith("Dokumen antar-PT ")
    SIMPAN["pinjaman"] = tautan[0]["id"]


async def test_PK25_U7_dokumen_antar_pt_dilunasi(klien, db, kepala_admin, dunia):
    loan = SIMPAN["pinjaman"]
    r = await klien.post(f"/api/interco/loans/{loan}/repay", headers=_h(kepala_admin), json={"amount": 2 * JT})
    assert r.status_code == 200, r.text
    pair_id = r.json()["pair_id"]
    kas = [k async for k in db.cash_transactions.find({"ref_type": "interco_loan_repayment",
                                                       "ref_id": f"{pair_id}:rp1"}, {"_id": 0})]
    assert sorted((k["entity_id"], k["direction"], k["amount"]) for k in kas) == [(KANDA, "out", 2e6),
                                                                                  (KSC, "in", 2e6)]
    assert round(await saldo_akun("1-1250", KSC) - SIMPAN["awal"]["ar"], 2) == 0
    assert round(await saldo_akun("2-1250", KANDA) - SIMPAN["awal"]["ap"], 2) == 0
    assert await _non_dagang() == SIMPAN["awal"]["nt"]
    assert r.json()["lender"]["status"] == "repaid"


async def _tidak_ada_jejak(db, K, sebelum_a2):
    assert await _jurnal_kasus(db, K["case"]["id"]) == []
    assert await db.sales_orders.find_one({"id": K["a2"]}, {"_id": 0}) == sebelum_a2
    assert await db.interco_loans.count_documents({"pair_id": f"iclp_case_{K['case']['id']}"}) == 0
    ln = await db.bank_statement_lines.find_one({"id": K["ln"]}, {"_id": 0})
    assert ln["holding_remaining"] == 2 * JT
    k = await db.finance_cases.find_one({"id": K["case"]["id"]}, {"_id": 0})
    assert k["status"] == "open" and "resolution_intent" not in k and "saga_lock" not in k


async def test_PK25_U8_periode_pt_pemilik_tertutup(klien, db, kepala_admin, dunia, paksa_jurnal_gagal):
    from services.book_date import periode_buku
    K = await _kasus_salah_pt(klien, db, kepala_admin)
    sebelum = await db.sales_orders.find_one({"id": K["a2"]}, {"_id": 0})
    async with paksa_jurnal_gagal("periode", entity_id=KSC, period_key=periode_buku()):
        r = await _salah_pt(klien, kepala_admin, K)
    assert r.status_code == 409, r.text
    await _tidak_ada_jejak(db, K, sebelum)


async def test_PK25_U9_akun_pt_pemilik_nonaktif(klien, db, kepala_admin, dunia):
    K = await _kasus_salah_pt(klien, db, kepala_admin)
    sebelum = await db.sales_orders.find_one({"id": K["a2"]}, {"_id": 0})
    await nonaktifkan_akun(KSC, "1-1250")
    try:
        r = await _salah_pt(klien, kepala_admin, K)
    finally:
        await aktifkan_akun(KSC, "1-1250")
    assert r.status_code == 400, r.text
    assert "1-1250" in r.text
    await _tidak_ada_jejak(db, K, sebelum)


# ── U10–U13: pemindai mengingat keputusan ────────────────────────────────────────────────────────────────────────────
async def _kwitansi_kembar(db, cus, nominal, tanggal=None):
    t = tanggal or _hari()
    ids = []
    for i in range(2):
        rc = _id("rc")
        await db.ar_receipts.insert_one({
            "id": rc, "number": f"KW-DOBEL-{next(_n)}", "entity_id": KSC, "customer_id": cus, "amount": float(nominal),
            "status": "posted", "receipt_date": t, "created_at": f"{t}T0{i + 1}:00:00+07:00", "allocations": []})
        ids.append(rc)
    return ids


async def _pindai(klien, kepala):
    r = await klien.post("/api/finance-cases/scan", headers=_h(kepala))
    assert r.status_code == 200, r.text
    return r.json()


async def _kasus_dobel(db, rc):
    return [c async for c in db.finance_cases.find({"case_type": "bayar_dobel", "source.id": rc}, {"_id": 0})]


async def test_PK25_U10_kasus_dobel_selesai_tidak_lahir_lagi(klien, db, kepala_admin, dunia):
    cus = await _pelanggan(db, deposit=750_000)
    so = await _pesanan(db, cus, 750_000)
    _, rc2 = await _kwitansi_kembar(db, cus, 750_000)
    await _pindai(klien, kepala_admin)
    [c] = await _kasus_dobel(db, rc2)
    r = await klien.post(f"/api/finance-cases/{c['id']}/resolve", headers=_h(kepala_admin), json={
        "action": "alokasi_uang_muka", "reason_code": "case_duplicate_payment", "customer_id": cus,
        "allocations": [{"order_id": so["id"], "amount": 750_000}]})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    hasil = await _pindai(klien, kepala_admin)
    assert hasil["duplicate_cases"] == 0, hasil
    assert len(await _kasus_dobel(db, rc2)) == 1
    rc = await db.ar_receipts.find_one({"id": rc2}, {"_id": 0})
    assert (rc["dup_decision"]["status"], rc["dup_decision"]["case_id"]) == ("resolved", c["id"])


async def test_PK25_U11_kasus_dobel_ditolak_tidak_lahir_lagi(klien, db, kepala_admin, dunia):
    cus = await _pelanggan(db)
    _, rc2 = await _kwitansi_kembar(db, cus, 810_000)
    await _pindai(klien, kepala_admin)
    [c] = await _kasus_dobel(db, rc2)
    r = await klien.post(f"/api/finance-cases/{c['id']}/reject", headers=_h(kepala_admin), json={
        "reason_code": "case_duplicate_payment", "note": "cicilan kedua, bukan dobel"})
    assert r.status_code == 200, r.text
    hasil = await _pindai(klien, kepala_admin)
    assert hasil["duplicate_cases"] == 0, hasil
    assert len(await _kasus_dobel(db, rc2)) == 1
    rc = await db.ar_receipts.find_one({"id": rc2}, {"_id": 0})
    assert rc["dup_decision"]["status"] == "rejected"


async def test_PK25_U12_kembar_terbaru_di_balik_5001_kwitansi_lama(klien, db, kepala_admin, dunia, monkeypatch):
    # Database tiruan mengabaikan batas `to_list(n)`; Motor asli tidak. Batasnya dipasang seperti aslinya supaya uji
    # membaca perilaku yang sama dengan MongoDB.
    import mongomock_motor
    asli = mongomock_motor.AsyncCursor.to_list

    async def _to_list(self, length=None, *a, **kw):
        rows = await asli(self)
        return rows if length is None else rows[:length]
    monkeypatch.setattr(mongomock_motor.AsyncCursor, "to_list", _to_list)
    lama = _hari(-90)
    await db.ar_receipts.insert_many([
        {"id": _id("rcl"), "number": f"KW-LAMA-{i}", "entity_id": KSC, "customer_id": f"cus_lama_{i}",
         "amount": float(10_000 + i), "status": "posted", "receipt_date": lama,
         "created_at": f"{lama}T00:00:00+07:00", "allocations": []} for i in range(5_001)])
    cus = await _pelanggan(db)
    _, rc2 = await _kwitansi_kembar(db, cus, 920_000)
    await _pindai(klien, kepala_admin)
    assert len(await _kasus_dobel(db, rc2)) == 1


async def test_PK25_U13_titipan_menganggur_ditolak_lahir_lagi(klien, db, kepala_admin, dunia):
    ln = _id("bsl")
    await db.bank_statement_lines.insert_one({
        "id": ln, "entity_id": KSC, "bank_account_id": "rek_pk25_ksc", "direction": "in", "amount": 300_000.0,
        "status": "holding", "holding_remaining": 300_000.0, "holding_allocated": [], "holding_settled": [],
        "stmt_date": _hari(-10), "description": "TRF TANPA NAMA", "created_at": now_iso()})
    await db.finance_cases.insert_one({
        "id": _id("fcs"), "number": f"KSC/CASE-PK25-{next(_n)}", "entity_id": KSC, "case_type": "dana_tak_dikenal",
        "status": "rejected", "amount": 300_000.0, "source": {"kind": "bank_holding", "id": ln, "label": ""},
        "documents": [], "attachments": [], "timeline": [], "created_at": now_iso()})
    hasil = await _pindai(klien, kepala_admin)
    assert hasil["holding_cases"] >= 1, hasil
    baru = [c async for c in db.finance_cases.find({"case_type": "dana_tak_dikenal", "source.id": ln,
                                                    "status": "open"}, {"_id": 0})]
    assert len(baru) == 1
