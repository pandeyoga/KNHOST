"""Perburuan 18 Nov (pukul 00.00–07.00 WIB) — "hari ini" dan tanggal dokumen memakai tanggal buku WIB, bukan jam UTC.

Pola cacat (kelanjutan 6d02792 `payment_variance_service._hari_buku` dan 74a492c `bank_recon_service._d`): `now_iso()[:10]`,
`datetime.now(timezone.utc).date()`, `date.today()` (zona mesin), atau 10/7 huruf pertama stempel UTC dipakai sebagai
tanggal buku. Pukul 00.00–07.00 WIB tanggal UTC masih KEMARIN (tanggal 1: bulan lalu; 1 Januari: tahun lalu).

Cara membekukan waktu: `book_date._sekarang` (satu-satunya jam hari ini WIB) DAN jam lama di modul yang diuji (`now_iso`,
`datetime`, `date` milik modul itu bila ada) dibekukan ke SAAT YANG SAMA, mesin dianggap ber-zona UTC (seperti mesin uji).
Kode lama membaca jam UTC yang dibekukan → tanggal kemarin → uji MERAH; kode baru membaca tanggal buku → HIJAU.
"""
from __future__ import annotations

import datetime as _dt
import uuid

import pytest

from services import book_date

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"


def _id(awal: str) -> str:
    return f"{awal}_tz_{uuid.uuid4().hex[:8]}"


def beku(monkeypatch, tanggal_wib: str, jam_wib: int = 1, *modul) -> _dt.datetime:
    """Bekukan jam ke `tanggal_wib` pukul `jam_wib` WIB untuk book_date dan jam lama di `modul` (mesin = UTC)."""
    d = _dt.date.fromisoformat(tanggal_wib)
    saat = _dt.datetime(d.year, d.month, d.day, jam_wib, 0, tzinfo=book_date.WIB).astimezone(_dt.timezone.utc)
    monkeypatch.setattr(book_date, "_sekarang", lambda: saat)

    class _DT(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return saat.astimezone(tz) if tz else saat.replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return saat.replace(tzinfo=None)

        @classmethod
        def today(cls):
            return saat.replace(tzinfo=None)

    class _D(_dt.date):
        @classmethod
        def today(cls):
            return saat.date()

    for m in modul:
        if hasattr(m, "now_iso"):
            monkeypatch.setattr(m, "now_iso", lambda: saat.isoformat())
        if getattr(m, "datetime", None) is _dt.datetime:
            monkeypatch.setattr(m, "datetime", _DT)
        if getattr(m, "date", None) is _dt.date:
            monkeypatch.setattr(m, "date", _D)
    return saat


# ── Jatuh tempo rencana pembayaran (uang: denda & selisih bayar) ───────────────────────────────────────────────────
async def test_TZ01_jatuh_tempo_rencana_dari_tanggal_buku_pesanan():
    """Pesanan dibuat 18 Nov 01.00 WIB (`created_at` 17 Nov 18.00 UTC). Termin 30 hari jatuh tempo 18 Des, uang muka
    18 Nov, cicilan bulanan 18 Des. Kode lama membaca jam UTC → semua sehari lebih awal (17 Nov / 17 Des)."""
    from services import payment_plan_service as pps
    dibuat = "2026-11-17T18:00:00.123456+00:00"
    assert pps.due_from_rule(dibuat, "net_days", net_days=30) == "2026-12-18"
    assert pps.due_from_rule(dibuat, "on_order") == "2026-11-18"
    assert pps.due_from_rule(dibuat, "monthly", 1) == "2026-12-18"
    pol = {"interval": "monthly", "dp_percent": 0, "installments": 1}
    baris = pps.build_lines("dp_installment", 1_000_000, base_date=dibuat, policy=pol, dp_percent=30,
                            installments=2, interval="monthly", net_days=0)
    assert [b["due_date"] for b in baris] == ["2026-11-18", "2026-12-18", "2027-01-18"], baris
    # Tanggal isian pengguna (tanpa zona) tetap apa adanya.
    assert pps.due_from_rule("2026-11-18", "net_days", net_days=30) == "2026-12-18"
    assert pps.due_from_rule("2026-11-18T23:30:00", "net_days", net_days=1) == "2026-11-19"


async def test_TZ02_baris_jatuh_tempo_dan_terlambat_hari_ini_wib(monkeypatch):
    """18 Nov 01.00 WIB: baris jatuh tempo 18 Nov SUDAH jatuh tempo; baris 17 Nov SUDAH terlambat.
    Kode lama (`now_iso()[:10]` = 17 Nov): baris 18 Nov belum jatuh tempo, baris 17 Nov belum terlambat."""
    from services import payment_plan_service as pps
    beku(monkeypatch, "2026-11-18", 1, pps)
    plan = {"lines": [
        {"seq": 1, "due_date": "2026-11-17", "amount": 100.0, "paid_amount": 0, "status": "open"},
        {"seq": 2, "due_date": "2026-11-18", "amount": 200.0, "paid_amount": 0, "status": "open"},
        {"seq": 3, "due_date": "2026-11-19", "amount": 300.0, "paid_amount": 0, "status": "open"}]}
    assert [ln["seq"] for ln in pps.due_lines(plan)] == [1, 2]
    assert pps.due_now_amount(plan) == 300.0
    assert [ln["seq"] for ln in pps.overdue_lines(plan)] == [1]


# ── Laporan: neraca, menara keuangan, konsolidasi, BI ──────────────────────────────────────────────────────────────
async def test_TZ03_neraca_tanpa_tanggal_memuat_jurnal_hari_ini(monkeypatch, aplikasi):
    """18 Nov 01.00 WIB, jurnal kas bertanggal buku 18 Nov. Neraca tanpa `as_of` = per 18 Nov dan memuatnya.
    Kode lama: as_of 17 Nov → jurnal hari ini hilang dari neraca."""
    from pembantu import jurnal
    from services import financial_statement_service as fss
    beku(monkeypatch, "2026-11-18", 1, fss)
    sebelum = await fss.balance_sheet(scope={"entity_id": KSC})
    await jurnal(KSC, "2026-11-18", [("1-1100", 777_000, 0), ("3-1000", 0, 777_000)], "uji TZ03", _id("je"))
    ns = await fss.balance_sheet(scope={"entity_id": KSC})
    assert ns["as_of"] == "2026-11-18"
    assert round(ns["assets_total"] - sebelum["assets_total"], 2) == 777_000


async def test_TZ04_menara_keuangan_bulan_berjalan_wib(monkeypatch, aplikasi):
    """1 Des 2026 01.00 WIB (30 Nov 18.00 UTC): MTD = Desember. Kode lama: masih November."""
    from services import finance_tower_service as fts
    beku(monkeypatch, "2026-12-01", 1, fts)
    hasil = await fts.finance_tower({"entity_id": KSC}, KSC)
    assert hasil["period"] == {"month": "2026-12", "year": 2026}


async def test_TZ05_konsolidasi_dan_bi_tahun_berjalan_wib(monkeypatch, klien, kepala_admin):
    """1 Jan 2027 01.00 WIB (31 Des 2026 18.00 UTC): tahun bawaan konsolidasi & BI keuangan = 2027. Kode lama: 2026."""
    from routers import consolidation as rc
    from routers import finance_bi as rbi
    beku(monkeypatch, "2027-01-01", 1, rc, rbi)
    r = await klien.get("/api/finance/consolidation/summary", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["year"] == 2027
    r = await klien.get("/api/finance/bi", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert r.json()["year"] == 2027


async def test_TZ06_omzet_pph_final_masa_wib(aplikasi, db):
    """Pesanan 1 Des 2026 00.30 WIB (`created_at` 30 Nov 17.30 UTC) masuk peredaran bruto Desember, bukan November."""
    from services import tax_center_service as tcs
    eid = "ent_uji_tz06"
    await db.sales_orders.insert_one({"id": _id("so"), "entity_id": eid, "status": "confirmed",
                                      "net_subtotal": 5_000_000.0, "created_at": "2026-11-30T17:30:00+00:00"})
    assert await tcs._period_omzet(eid, "2026-12") == 5_000_000.0
    assert await tcs._period_omzet(eid, "2026-11") == 0.0


async def test_TZ07_periode_aset_tanpa_tanggal_wib(monkeypatch):
    """1 Des 2026 01.00 WIB: periode bawaan aset = 2026-12 (kode lama: 2026-11)."""
    from services import fixed_asset_service as fas
    beku(monkeypatch, "2026-12-01", 1, fas)
    assert fas._period_of("") == "2026-12"
    assert fas._period_of("2026-11-30T17:30:00+00:00") == "2026-12"
    assert fas._period_of("2026-11-15") == "2026-11"


# ── Kontrabon: tanggal siklus & jatuh tempo bawaan ─────────────────────────────────────────────────────────────────
async def test_TZ08_kontrabon_tanggal_siklus_dan_jatuh_tempo_wib(monkeypatch, aplikasi, db):
    """18 Nov 01.00 WIB di mesin UTC: usulan tanggal siklus kontrabon = 18 Nov, jatuh tempo = 18 Nov + termin.
    Kode lama (`date.today()` zona mesin): 17 Nov dan sehari lebih awal."""
    from services import contra_bon_service as cbs
    beku(monkeypatch, "2026-11-18", 1, cbs)
    sid = _id("sup")
    await db.suppliers.insert_one({"id": sid, "code": "TZ08", "name": "Pemasok TZ08", "entity_id": KSC,
                                   "status": "active", "payment_term_code": "NET30"})
    siap = await cbs.prepare(sid, KSC)
    hari = siap["suggested"]["term_days"]
    assert siap["suggested"]["cycle_date"] == "2026-11-18"
    assert siap["suggested"]["due_date"] == (_dt.date(2026, 11, 18) + _dt.timedelta(days=hari)).isoformat()


async def test_TZ09_acuan_jadwal_tukar_faktur_wib(monkeypatch, aplikasi, db):
    """Jadwal tukar faktur dua pekanan disimpan 18 Nov 01.00 WIB tanpa tanggal acuan → acuan 18 Nov (kode lama 17 Nov)."""
    from services import contra_bon_reminder as cbr
    from services import contra_bon_service as cbs
    beku(monkeypatch, "2026-11-18", 1, cbr, cbs)
    sid = _id("sup")
    await db.suppliers.insert_one({"id": sid, "code": "TZ09", "name": "Pemasok TZ09", "entity_id": KSC,
                                   "status": "active"})
    await cbr.set_schedule(sid, {"mode": "biweekly", "weekday": 2}, {"name": "Uji"})
    sup = await db.suppliers.find_one({"id": sid}, {"_id": 0, "invoice_exchange": 1})
    assert sup["invoice_exchange"]["anchor_date"] == "2026-11-18"


# ── Kontrak, retur, ubah pesanan ───────────────────────────────────────────────────────────────────────────────────
async def test_TZ10_kontrak_berlaku_hari_ini_wib(monkeypatch, aplikasi, db):
    """18 Nov 01.00 WIB: kontrak beli mulai 18 Nov dipakai; kontrak yang berakhir 17 Nov tidak. Kode lama (tanggal UTC
    17 Nov): kontrak lama (harga lama) yang menang."""
    from services import contract_service as cs
    beku(monkeypatch, "2026-11-18", 1, cs)
    mitra = _id("sup")
    lama, baru = _id("sct"), _id("sct")
    await db.supplier_contracts.insert_many([
        {"id": lama, "contract_type": "purchase", "partner_id": mitra, "status": "active", "entity_id": KSC,
         "valid_from": "2026-10-01", "valid_to": "2026-11-17", "tariff_rate": 10_000},
        {"id": baru, "contract_type": "purchase", "partner_id": mitra, "status": "active", "entity_id": KSC,
         "valid_from": "2026-11-18", "valid_to": "", "tariff_rate": 12_000}])
    dipakai = await cs.resolve_active(partner_id=mitra, contract_type="purchase", entity_id=KSC)
    assert dipakai and dipakai["id"] == baru, dipakai


async def test_TZ11_penanda_retur_hari_ini_bukan_masa_depan(monkeypatch, aplikasi, db):
    """18 Nov 01.00 WIB: menandai "Barang dikirim/dijemput" bertanggal 18 Nov (hari ini WIB) diterima. Kode lama:
    ditolak "tidak boleh di masa depan" (dibanding tanggal UTC 17 Nov). 19 Nov tetap ditolak."""
    from services import return_service as rs
    beku(monkeypatch, "2026-11-18", 1, rs)
    rid = _id("ret")
    await db.sales_returns.insert_one({"id": rid, "status": "approved", "entity_id": KSC, "milestones": []})
    out = await rs.mark_milestone(rid, "shipped_to_store", "Uji", at="2026-11-18")
    assert out["shipped_to_store_at"] == "2026-11-18"
    out = await rs.mark_milestone(rid, "shipped_to_store", "Uji", at="2026-11-18T01:05")
    assert out["shipped_to_store_at"] == "2026-11-18T01:05"
    with pytest.raises(ValueError, match="masa depan"):
        await rs.mark_milestone(rid, "shipped_to_store", "Uji", at="2026-11-19")


async def test_TZ12_ubah_pesanan_tanggal_kemarin_ditolak(monkeypatch):
    """18 Nov 01.00 WIB: tanggal 17 Nov = masa lalu → ditolak (kode lama meloloskan karena tanggal UTC masih 17 Nov)."""
    from services import so_override_service as sos
    beku(monkeypatch, "2026-11-18", 1, sos)
    sos._check_date("2026-11-18", "Tanggal kirim")
    with pytest.raises(sos.OverrideError, match="masa lalu"):
        sos._check_date("2026-11-17", "Tanggal kirim")


# ── Keuangan: kasus otomatis & titipan ─────────────────────────────────────────────────────────────────────────────
async def test_TZ13_titipan_menganggur_umur_wib(monkeypatch, aplikasi, db):
    """18 Nov 01.00 WIB, titipan bank bertanggal 15 Nov, ambang 3 hari: sudah genap 3 hari → masuk pindaian kasus dan
    Ringkasan Titipan memberi umur 3 hari + perlu tindakan bila ambang 2. Kode lama (17 Nov UTC): belum / umur 2."""
    from services import bank_recon_service as brs
    from services import finance_case_scan as fcs
    beku(monkeypatch, "2026-11-18", 1, fcs, brs)
    lid = _id("bsl")
    await db.bank_statement_lines.insert_one({"id": lid, "status": "holding", "stmt_date": "2026-11-15",
                                              "amount": 250_000.0, "holding_remaining": 250_000.0,
                                              "entity_id": KSC, "bank_account_id": _id("ba")})
    baris = [r for r in await fcs.aged_holding_lines(3) if r["id"] == lid]
    assert baris and baris[0]["age_days"] == 3, baris
    ring = await brs.holding_summary([KSC])
    item = next(i for i in ring["items"] if i["id"] == lid)
    assert item["age_days"] == 3


# ── Harga berlaku per tanggal (uang: harga pesanan) ────────────────────────────────────────────────────────────────
async def test_TZ14_harga_tanggal_mulai_dan_akhir_hari_wib(monkeypatch, aplikasi, db):
    """Harga PT lama berlaku s/d 30 Nov, harga baru mulai 1 Des (isian tanggal saja). 1 Des 01.00 WIB (30 Nov 18.00 UTC)
    pesanan harus memakai harga baru. Kode lama membandingkan penanda `…T00:00:00+00:00`/`…T23:59:59+00:00` dengan
    stempel UTC → harga lama masih dipakai sampai 07.00 WIB. Aturan harga khusus yang berakhir 30 Nov juga sudah habis."""
    from services import price_approval_service as pas
    from services import pricelist_service as pls
    beku(monkeypatch, "2026-12-01", 1, pls, pas)
    pid = _id("prd")
    lama = {"id": _id("ep"), "entity_id": KSC, "product_id": pid, "status": "active", "is_listed": True,
            "sell_price": 10_000.0, "valid_from": pls._norm_dt("2026-10-01"),
            "valid_until": pls._norm_dt("2026-11-30", end_of_day=True), "created_at": "2026-10-01T03:00:00+00:00"}
    baru = {"id": _id("ep"), "entity_id": KSC, "product_id": pid, "status": "active", "is_listed": True,
            "sell_price": 12_000.0, "valid_from": pls._norm_dt("2026-12-01"), "valid_until": "",
            "created_at": "2026-11-20T03:00:00+00:00"}
    await db.entity_prices.insert_many([dict(lama), dict(baru)])
    harga = await pls.resolve_sell_price(KSC, pid, {"price": 9_000.0})
    assert harga["price"] == 12_000.0, harga
    assert pls.effective_status(lama) == "expired" and pls.effective_status(baru) == "current"
    aturan = {"status": "approved", "valid_from": "2026-11-01T03:00:00+00:00",
              "valid_until": pas.norm_until("2026-11-30")}
    assert pas.is_active(aturan) is False
    # Sebelum tengah malam WIB (30 Nov 23.30 WIB) harga lama masih berlaku.
    beku(monkeypatch, "2026-11-30", 23, pls, pas)
    assert (await pls.resolve_sell_price(KSC, pid, {"price": 9_000.0}))["price"] == 10_000.0
    assert pas.is_active(aturan) is True


# ── Usulan jatuh tempo: ubah jadwal selisih bayar & jatuh tempo bayar PO ─────────────────────────────────────────────
async def test_TZ15_usulan_jatuh_tempo_ubah_jadwal_dari_hari_ini_wib(monkeypatch, aplikasi, db):
    """18 Nov 01.00 WIB: usulan jatuh tempo baru dialog selisih bayar = 18 Nov + `reschedule_days` (kode lama: dari 17 Nov)."""
    from services import payment_variance_service as pvs
    beku(monkeypatch, "2026-11-18", 1, pvs)
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": "Toko TZ15", "entity_id": KSC, "status": "active",
                                   "payment_profile": {}, "deposit_balance": 0.0})
    hasil = await pvs.pre_assess(cid, 100_000, entity_id=KSC)
    hari = int((await pvs.variance_policy(KSC, cid))["reschedule_days"])
    assert hasil["suggested_due_date"] == (_dt.date(2026, 11, 18) + _dt.timedelta(days=hari)).isoformat(), hasil


async def test_TZ16_jatuh_tempo_bayar_po_tanpa_eta_wib(monkeypatch):
    """18 Nov 01.00 WIB, PO NET30 tanpa ETA: jatuh tempo bayar 18 Des (kode lama: 17 Des). ETA isian tetap acuan."""
    from services import supplier_service as ss
    beku(monkeypatch, "2026-11-18", 1, ss)
    assert ss.payment_due_date({"net_days": 30}) == "2026-12-18"
    assert ss.payment_due_date({"net_days": 30}, "2026-11-25") == "2026-12-25"


# ── Pengaturan terjadwal "berlaku sejak" (jam dinding WIB dari pemilih tanggal-jam layar) ─────────────────────────────
async def test_TZ17_pengaturan_terjadwal_berlaku_jam_wib(aplikasi):
    """Nilai dijadwalkan "berlaku sejak 2026-12-01T00:00" (isian layar, tanpa zona = WIB). 1 Des 01.00 WIB nilai baru
    sudah dipakai; 30 Nov 23.30 WIB belum. Kode lama menganggap isian itu UTC → baru berlaku 07.00 WIB."""
    from services import config_resolver as cr
    kunci = "payment.plan_tolerance_rupiah"
    lama = (await cr.resolve(kunci, {}))["value"]
    await cr.set_value(kunci, 4321, actor="Uji", reason="uji TZ17", effective_from="2026-12-01T00:00")
    wib = book_date.WIB
    assert (await cr.resolve(kunci, {}, at=_dt.datetime(2026, 12, 1, 1, 0, tzinfo=wib)))["value"] == 4321
    assert (await cr.resolve(kunci, {}, at=_dt.datetime(2026, 11, 30, 23, 30, tzinfo=wib)))["value"] == lama
    # Urutan baris = saat berlaku: jadwal 1 Des 00.30 WIB yang ditulis bertanda UTC (30 Nov 17.30Z) menang atas
    # jadwal 1 Des 00.00 WIB walau teksnya lebih "kecil".
    await cr.set_value(kunci, 5555, actor="Uji", reason="uji TZ17b", effective_from="2026-11-30T17:30:00+00:00")
    assert (await cr.resolve(kunci, {}, at=_dt.datetime(2026, 12, 1, 1, 0, tzinfo=wib)))["value"] == 5555


# ── Jadwal bayar antar-PT: periode cutoff dari tanggal buku WIB ─────────────────────────────────────────────────────
async def test_TZ18_periode_bayar_antar_pt_setelah_cutoff_wib():
    """Cutoff tanggal 25, bayar tanggal 10. Tagihan antar-PT 26 Nov 01.00 WIB (`invoiced_at` 25 Nov 18.00 UTC) sudah
    lewat cutoff → periode Desember, bayar 10 Des. Kode lama (10 huruf UTC = 25 Nov): periode November, bayar 10 Nov."""
    from services import interco_service as ics
    assert ics._period_for("2026-11-25T18:00:00+00:00", 25, 10) == {"period": "2026-12", "pay_date": "2026-12-10"}
    assert ics._period_for("2026-11-25T16:59:00+00:00", 25, 10) == {"period": "2026-11", "pay_date": "2026-11-10"}
    assert ics._period_for("2026-11-26", 25, None) == {"period": "2026-12", "pay_date": "2026-12-31"}


# ── Dokumen Faktur Pajak: tanggal tercetak ───────────────────────────────────────────────────────────────────────────
async def test_TZ19_tanggal_cetak_faktur_pajak_wib(aplikasi, db):
    """Faktur diterbitkan 18 Nov 01.34 WIB (`faktur_date` 17 Nov 18.34 UTC) tercetak bertanggal 2026-11-18.
    Kode lama: "Tanggal: 2026-11-17" (ditemukan pada data acuan malam ini, faktur fkt_86cc465fa55b)."""
    from services import tax_invoice_service as tis
    fid = _id("fkt")
    await db.tax_invoices.insert_one({"id": fid, "number": "FP-TZ19", "entity_id": KSC, "status": "normal",
                                      "faktur_date": "2026-11-17T18:34:15.706447+00:00", "items": [],
                                      "seller_address": "Jl. Uji, Bandung", "has_customer_npwp": True})
    html = await tis.render_faktur_html(fid)
    assert "Tanggal: 2026-11-18" in html and "Bandung, 2026-11-18" in html
    assert "2026-11-17" not in html


# ── Biaya kampanye tanpa tanggal: kas & jurnal bertanggal hari ini WIB ───────────────────────────────────────────────
async def test_TZ20_biaya_kampanye_tanpa_tanggal_wib(monkeypatch, klien, kepala_admin, db):
    """1 Des 2026 01.00 WIB, biaya kampanye dicatat tanpa tanggal: tanggal biaya & jurnal 2026-12-01 (kode lama:
    `now_iso()[:10]` = 2026-11-30 → beban masuk November)."""
    from services import marketing_cost_service as mcs
    r = await klien.post("/api/bank-accounts", headers=kepala_admin, json={
        "account_type": "bank", "bank_name": "BCA", "purposes": ["operasional"], "payment_method_codes": ["transfer"],
        "name": "BCA Pemasaran TZ20", "account_number": "741-000-2020", "holder_name": "PT Kain Suka Cita",
        "entity_id": KSC})
    assert r.status_code == 200, r.text
    beku(monkeypatch, "2026-12-01", 1, mcs)
    kampanye = {"id": _id("cmp"), "entity_id": KSC, "name": "Kampanye TZ20"}
    biaya = await mcs.record_cost(kampanye, {"amount": 150_000, "description": "Iklan dini hari",
                                             "cash_type": "kas_besar", "account_id": r.json()["id"]},
                                  {"name": "Uji"})
    assert biaya["date"] == "2026-12-01"
    je = await db.journal_entries.find_one({"id": biaya["journal_entry_id"]}, {"_id": 0, "date": 1})
    assert je and je["date"] == "2026-12-01", je
