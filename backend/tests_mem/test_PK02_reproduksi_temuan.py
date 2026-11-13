"""PK-02 U13 — sepuluh temuan audit ditulis sebagai PERILAKU BENAR dan ditandai "diharapkan gagal".

Unit yang memperbaiki temuannya mencabut tandanya (lihat `docs/blueprint/INDEKS_UNIT.md`). Tiap tes memakai PT sendiri.
Pesan gagal tanpa tanda (bukti sebab yang sama dengan temuannya) ada di `docs/reviews/2026-11-13/hasil/PK-02.md`.
"""
import pytest

import db as _dbmod
from core_utils import now_iso
from pembantu import AKTOR_UJI, aktifkan_akun, jumlah, jurnal, jurnal_dari, nonaktifkan_akun, pt_uji, saldo_akun
from services import gl_service as gl

JT = 1_000_000


def cocok(dapat, harap):
    return abs(float(dapat) - float(harap)) < 0.005


async def _kas(eid, sid, arah, nominal, tanggal, db):
    txn = {"id": sid, "number": f"UJI/CASH-{sid}", "cash_type": "kas_besar", "direction": arah, "amount": nominal,
           "category": "operasional", "description": "uji", "entity_id": eid, "txn_date": tanggal,
           "status": "posted", "ref_type": "", "ref_id": ""}
    await db.cash_transactions.insert_one(dict(txn))
    return await gl.post_cash_transaction(txn)


@pytest.mark.xfail(strict=True, reason="GL-01 — jurnal bisa dibalik dua kali lewat pembalik manual dan void dokumen")
async def test_PK02_GL01_dibalik_dua_kali(db):
    eid = await pt_uji("G01")
    hari_ini = now_iso()[:10]
    je = await _kas(eid, "cash_g01a", "in", 10 * JT, "2026-11-06T03:00:00+00:00", db)
    await gl.reverse_entry(je["id"], hari_ini, "uji pembalikan manual", AKTOR_UJI)
    try:
        await gl.post_cash_void("cash_g01a", label="void uji")
    except Exception:  # noqa: BLE001 — aksi kedua boleh ditolak
        pass
    saldo1 = await saldo_akun("1-1100", eid)
    await _kas(eid, "cash_g01b", "out", 2 * JT, "2026-11-08T03:00:00+00:00", db)
    v = await gl.post_cash_void("cash_g01b", label="void uji")
    try:
        await gl.reverse_entry(v["id"], hari_ini, "membalik pembalik otomatis", AKTOR_UJI)
    except Exception:  # noqa: BLE001
        pass
    saldo2 = await saldo_akun("1-1100", eid)
    assert cocok(saldo1, 0), f"sesudah rangkaian pertama saldo kas {saldo1:,.2f}, seharusnya 0"
    assert cocok(saldo2, 0), f"sesudah rangkaian kedua saldo kas {saldo2:,.2f}, seharusnya 0"


@pytest.mark.xfail(strict=True, reason="GL-04 — periode yang belum berakhir bisa ditutup")
async def test_PK02_GL04_tutup_bulan_berjalan(aplikasi):
    from services import closing_service as cs
    eid = await pt_uji("G04")
    with pytest.raises(ValueError):
        await cs.close_period("month", now_iso()[:7], AKTOR_UJI, eid,
                              suspense_override_reason="uji kerangka", can_override_suspense=True)
    await jurnal(eid, now_iso()[:10], [("6-2000", 1000, 0), ("1-1100", 0, 1000)], "jurnal hari ini", "g04")


@pytest.mark.xfail(strict=True, reason="GL-05 — tanggal buku campur UTC dan WIB")
async def test_PK02_GL05_tanggal_buku_wib(aplikasi):
    from services import financial_statement_service as fs
    eid = await pt_uji("G05")
    await jurnal(eid, "2026-10-20", [("6-2000", 4 * JT, 0), ("1-1100", 0, 4 * JT)], "Sewa", "g05a")
    await jurnal(eid, "2026-10-31T17:30:00+00:00", [("6-3000", 1 * JT, 0), ("1-1100", 0, 1 * JT)],
                 "Utilitas 1 Nov 00:30 WIB", "g05b")
    okt = await fs.income_statement("2026-10-01", "2026-10-31", {"entity_id": eid})
    nov = await fs.income_statement("2026-11-01", "2026-11-30", {"entity_id": eid})
    assert cocok(okt["opex_total"], 4 * JT), f"beban Okt {okt['opex_total']:,.2f}"
    assert cocok(nov["opex_total"], 1 * JT), f"beban Nov {nov['opex_total']:,.2f}"


@pytest.mark.xfail(strict=True, reason="GL-07 — jurnal manual selisih 1 sen diterima")
async def test_PK02_GL07_selisih_satu_sen(aplikasi):
    from schemas_finance import JournalEntryCreate
    eid = await pt_uji("G07")
    p = JournalEntryCreate(date="2026-11-05", description="uji 1 sen", lines=[
        {"account_code": "6-2000", "debit": 1000.01, "credit": 0},
        {"account_code": "1-1100", "debit": 0, "credit": 1000.00}])
    with pytest.raises(Exception):
        await gl.create_manual_entry(p, AKTOR_UJI, entity_id=eid)
    assert await jumlah("journal_entries", {"entity_id": eid}) == 0


async def test_PK02_IC01_jurnal_satu_sisi(db):
    """Tanda "diharapkan gagal" dicabut PK-06: konfirmasi memeriksa jurnal kedua PT sebelum status berubah."""
    from services import interco_service as ics
    a, b = await pt_uji("I1A"), await pt_uji("I1B")
    base = {"pair_id": "pair_ic01", "status": "draft", "seller_entity_id": a, "buyer_entity_id": b,
            "subtotal": 20 * JT, "tax_amount": 2.2 * JT, "grand_total": 22.2 * JT, "seller_entity_name": "PT Uji I1A",
            "buyer_entity_name": "PT Uji I1B", "items": [], "created_at": now_iso()}
    await db.interco_transactions.insert_many([
        {**base, "id": "ict_ic01_s", "role": "seller", "entity_id": a, "number": "I1A/IC-00001"},
        {**base, "id": "ict_ic01_b", "role": "buyer", "entity_id": b, "number": "I1B/IC-00001"}])
    await nonaktifkan_akun(b, "2-1250")
    try:
        with pytest.raises(Exception):
            await ics.confirm("ict_ic01_s", AKTOR_UJI)
    finally:
        await aktifkan_akun(b, "2-1250")
    st = {d["id"]: d["status"] async for d in db.interco_transactions.find({"pair_id": "pair_ic01"}, {"_id": 0})}
    assert st == {"ict_ic01_s": "draft", "ict_ic01_b": "draft"}, st
    assert await jurnal_dari("interco_transaction", "pair_ic01") == []


async def test_PK02_IC05_pengguna_satu_pt_ditolak_penjaga_tulis(klien, akun, sesi, peran_tanpa_acuan):
    """Bukan tanda gagal: lewat HTTP, pengguna yang hanya ditugaskan di ent_ksc sudah ditolak penjaga tulis entitas
    (403) di HEAD `fb6bc75`. Tes ini menjaga perilaku itu; sisa temuannya ada di tes layanan di bawah."""
    p = await peran_tanpa_acuan({"accounting": ["view", "create"]})
    h = await sesi(await akun(p, entitas=("ent_ksc",)))
    r = await klien.post("/api/gl/journal", headers=h, json={
        "date": "2026-11-05", "description": "uji entitas", "entity_id": "ent_kanda",
        "lines": [{"account_code": "6-2000", "debit": 500000, "credit": 0},
                  {"account_code": "1-1100", "debit": 0, "credit": 500000}]})
    assert r.status_code == 403
    assert await jumlah("journal_entries", {"entity_id": "ent_kanda", "source_type": "manual"}) == 0


async def test_PK02_IC05_entitas_dari_isi(aplikasi):
    """Lapis layanan, persis bukti `skenario2.py`: konteks pemanggil PT A, isi permintaan menyebut PT B.
    IC-05 ditutup PK-09: layanan memakai PT dari router; isi berbeda → ditolak."""
    from schemas_finance import JournalEntryCreate
    a, b = await pt_uji("I5A"), await pt_uji("I5B")
    p = JournalEntryCreate(date="2026-11-05", description="uji entitas", entity_id=b, lines=[
        {"account_code": "6-2000", "debit": 500000, "credit": 0},
        {"account_code": "1-1100", "debit": 0, "credit": 500000}])
    try:
        await gl.create_manual_entry(p, AKTOR_UJI, entity_id=a)
    except Exception:  # noqa: BLE001 — ditolak juga perilaku benar
        pass
    assert await jumlah("journal_entries", {"entity_id": b, "source_type": "manual"}) == 0


@pytest.mark.xfail(strict=True, reason="IV-01 — landed cost ke roll terjual menambah persediaan buku besar")
async def test_PK02_IV01_landed_cost_roll_terjual(db):
    from services import landed_cost_service as lcs
    from services.roll_service import roll_value_cents
    eid = await pt_uji("V01")

    def roll(i, st, sisa):
        return {"id": i, "roll_no": i, "product_id": "p_iv01", "status": st, "owner_entity_id": eid,
                "entity_id": eid, "length_initial": 100.0, "length_remaining": sisa, "unit_cost": 10000.0,
                "base_unit_cost": 10000.0, "acquired": {"ref_id": "po_iv01", "ref_type": "purchase_order"}}
    await db.inventory_rolls.insert_many([roll("r_iv01_jual", "delivered", 0.0), roll("r_iv01_stok", "available", 100.0)])

    async def nilai_roll():
        rolls = await db.inventory_rolls.find({"owner_entity_id": eid}, {"_id": 0}).to_list(100)
        return sum(roll_value_cents(r) for r in rolls) / 100
    await jurnal(eid, "2026-11-01", [("1-1300", 1 * JT, 0), ("3-2900", 0, 1 * JT)], "saldo awal roll", "iv01")
    s0, g0 = await nilai_roll(), await saldo_akun("1-1300", eid)
    rolls = await lcs.resolve_target_rolls(["po_iv01"], eid)
    alloc = lcs.compute_allocation(rolls, 3 * JT, "length")
    await lcs.apply_allocation_to_rolls("LC-IV01", alloc["allocations"])
    await gl.post_landed_cost({"id": "lc_iv01", "entity_id": eid}, amount=alloc["allocated_total"], label="LC-IV01")
    s1, g1 = await nilai_roll(), await saldo_akun("1-1300", eid)
    assert cocok(g1 - g0, s1 - s0), f"persediaan naik {g1 - g0:,.2f}, nilai roll naik {s1 - s0:,.2f}"


async def test_PK02_FX02_denda_dibayar_dua_kali(aplikasi):
    """FX-02 — ditutup PK-08: bayar denda lewat kas `cash_pnl_<id>` per pembayaran (jalur aplikasi), bukan lagi
    `gl.post_penalty_payment` berkunci tetap `<id>:pay`."""
    from services import penalty_service as ps
    from services.amendment_service import ensure_reasons
    await ensure_reasons()
    eid = await pt_uji("X02")
    await _dbmod.db.bank_accounts.insert_many([
        {"id": f"ba_fx02_{i}", "name": f"Bank FX02 {i}", "account_type": "bank", "cash_type": "kas_besar",
         "entity_id": eid, "is_active": True, "status": "active", "opening_balance": 0} for i in (1, 2)])
    await _dbmod.db.penalties.insert_one({
        "id": "pen_fx02", "number": "DN-FX02", "entity_id": eid, "doc_id": "so_fx02", "plan_id": "", "line_seq": 0,
        "due_date": "2026-10-01", "period_key": "2026-10-01|2026-11", "amount": 100000.0, "paid_amount": 0.0,
        "status": "draft", "customer_name": "Uji"})
    await ps.issue("pen_fx02", AKTOR_UJI)
    await ps.pay("pen_fx02", 60000, "transfer", AKTOR_UJI, account_id="ba_fx02_1")
    await ps.pay("pen_fx02", 40000, "transfer", AKTOR_UJI, account_id="ba_fx02_1")
    assert cocok(await saldo_akun("1-1270", eid), 0)


@pytest.mark.xfail(strict=True, reason="RC-01 — mode Semua Entitas menjumlah tanpa eliminasi dan tanpa keterangan")
async def test_PK02_RC01_gabungan_tanpa_eliminasi(aplikasi):
    """Selisih sebelum/sesudah data dimasukkan, supaya jurnal PT lain di modul ini tidak ikut terhitung."""
    from services import financial_statement_service as fs
    pl0 = await fs.income_statement("2026-10-01", "2026-10-31", {})
    bs0 = await fs.balance_sheet("2026-10-31", scope={})
    a, b = await pt_uji("R1A"), await pt_uji("R1B")
    for args in [
        (a, "2026-10-01", [("1-1100", 100 * JT, 0), ("3-1000", 0, 100 * JT)], "Setor modal", "rc_a1"),
        (a, "2026-10-05", [("1-1300", 60 * JT, 0), ("2-1100", 0, 60 * JT)], "Beli persediaan kredit", "rc_a2"),
        (a, "2026-10-10", [("1-1200", 55.5 * JT, 0), ("4-1000", 0, 50 * JT), ("2-1200", 0, 5.5 * JT)], "Jual kredit", "rc_a3"),
        (a, "2026-10-10", [("5-1000", 30 * JT, 0), ("1-1300", 0, 30 * JT)], "HPP", "rc_a4"),
        (a, "2026-10-20", [("6-2000", 4 * JT, 0), ("1-1100", 0, 4 * JT)], "Sewa", "rc_a5"),
        (a, "2026-10-25", [("1-1100", 20 * JT, 0), ("1-1200", 0, 20 * JT)], "Terima piutang", "rc_a6"),
        (a, "2026-10-15", [("1-1250", 22.2 * JT, 0), ("4-1000", 0, 20 * JT), ("2-1200", 0, 2.2 * JT)], "Jual antar-PT", "rc_a7"),
        (a, "2026-10-15", [("5-1000", 12 * JT, 0), ("1-1300", 0, 12 * JT)], "HPP antar-PT", "rc_a8"),
        (b, "2026-10-15", [("1-1300", 20 * JT, 0), ("1-1500", 2.2 * JT, 0), ("2-1250", 0, 22.2 * JT)], "Beli antar-PT", "rc_b1"),
        (a, "2026-10-31", [("6-3000", 1 * JT, 0), ("1-1100", 0, 1 * JT)], "Utilitas", "rc_a9"),
    ]:
        await jurnal(*args)
    pl = await fs.income_statement("2026-10-01", "2026-10-31", {})
    bs = await fs.balance_sheet("2026-10-31", scope={})
    berlabel = pl.get("eliminated") is False and bs.get("eliminated") is False
    benar = (cocok(pl["revenue_total"] - pl0["revenue_total"], 50 * JT)
             and cocok(bs["assets_total"] - bs0["assets_total"], (115 + 35.5 + 18) * JT + (20 - 8) * JT + 2.2 * JT))
    assert berlabel or benar, (f"pendapatan +{pl['revenue_total'] - pl0['revenue_total']:,.2f}, "
                               f"aset +{bs['assets_total'] - bs0['assets_total']:,.2f}, tanpa penanda eliminated")


@pytest.mark.xfail(strict=True, reason="RP-06 — klasifikasi arus kas menyimpang dari hitungan baku")
async def test_PK02_RP06_klasifikasi_arus_kas(aplikasi):
    from services import cash_flow_service as cf
    eid = await pt_uji("P06")
    for args in [
        ("2026-09-30", [("1-1100", 1000, 0), ("3-1000", 0, 1000)], "Setor modal", "p06m1"),
        ("2026-09-30", [("1-2100", 100, 0), ("1-1100", 0, 100)], "Beli mesin", "p06m2"),
        ("2026-09-30", [("6-6000", 20, 0), ("1-2900", 0, 20)], "Akumulasi susut", "p06m3"),
        ("2026-10-05", [("1-1100", 300, 0), ("4-1000", 0, 300)], "Jual tunai", "p06o1"),
        ("2026-10-06", [("6-2000", 50, 0), ("1-1100", 0, 50)], "Sewa", "p06o2"),
        ("2026-10-10", [("1-1100", 130, 0), ("1-2900", 20, 0), ("1-2100", 0, 100), ("4-9100", 0, 50)], "Jual mesin", "p06o3"),
        ("2026-10-12", [("1-1100", 500, 0), ("2-1250", 0, 500)], "Pinjaman PT lain", "p06o4"),
        ("2026-10-15", [("1-1100", 200, 0), ("3-2900", 0, 200)], "Saldo awal rekening", "p06o5"),
    ]:
        await jurnal(eid, *args)
    r = await cf.cash_flow_statement("2026-10-01", "2026-10-31", {"entity_id": eid})
    got = {k: r[k]["total"] for k in ("operating", "investing", "financing")}
    assert cocok(got["operating"], 250) and cocok(got["investing"], 130) and cocok(got["financing"], 500), got
