"""PK-37 serah-terima (b1) — pemakai tanggal buku: `_insert_entry`, `create_manual_entry`, penjaga periode,
`preflight_posting`, `closing_service.status_for_date`, "hari ini" antar-PT, periode pajak.

U4–U8 (lapis B). U14 (lapis A) ada di `backend/tests/test_bp_PK37_kas_tanggal_wib.py`.

Persiapan U4/U5 = 12 jurnal `docs/finance/bukti-2026-11-13/skenario1.py` (fixture, sisip lewat `_insert_entry`); jurnal
a9 = beban utilitas Rp 1.000.000 yang terjadi 1 Nov 00.30 WIB, berstempel `2026-10-31T17:30:00+00:00` (17.30 UTC).

Hitung tangan Laba-Rugi PT A
  Oktober : pendapatan 50 (a3) + 20 (a7) = 70 jt; HPP 30 (a4) + 12 (a8) = 42 jt → laba kotor 28 jt;
            beban operasional = sewa 4 jt (a5) → laba bersih 28 − 4 = 24 jt.
            (Sebelum unit: a9 terpotong ke "2026-10-31" → beban 5 jt, laba 23 jt.)
  November: pendapatan 10 jt (a10); HPP 6 jt (a11) → laba kotor 4 jt; beban = utilitas 1 jt (a9) → laba bersih 3 jt.
"""
import re

import pytest

from pembantu import AKTOR_UJI, jurnal, pt_uji, saldo_akun, tutup_periode
from services import financial_statement_service as fs
from services import gl_service as gl

JT = 1_000_000
STEMPEL_DINI_HARI = "2026-10-31T17:30:00+00:00"   # = 1 Nov 2026 00.30 WIB


def cocok(dapat, harap):
    return abs(float(dapat) - float(harap)) < 0.005


@pytest.fixture(scope="module")
async def skenario1(aplikasi):
    a, b = await pt_uji("P37A"), await pt_uji("P37B")
    for args in [
        (a, "2026-10-01", [("1-1100", 100 * JT, 0), ("3-1000", 0, 100 * JT)], "Setor modal", "p37_a1"),
        (a, "2026-10-05", [("1-1300", 60 * JT, 0), ("2-1100", 0, 60 * JT)], "Beli persediaan kredit", "p37_a2"),
        (a, "2026-10-10", [("1-1200", 55.5 * JT, 0), ("4-1000", 0, 50 * JT), ("2-1200", 0, 5.5 * JT)], "Jual kredit + PPN",
         "p37_a3"),
        (a, "2026-10-10", [("5-1000", 30 * JT, 0), ("1-1300", 0, 30 * JT)], "HPP", "p37_a4"),
        (a, "2026-10-20", [("6-2000", 4 * JT, 0), ("1-1100", 0, 4 * JT)], "Sewa tunai", "p37_a5"),
        (a, "2026-10-25", [("1-1100", 20 * JT, 0), ("1-1200", 0, 20 * JT)], "Terima piutang", "p37_a6"),
        (a, "2026-10-15", [("1-1250", 22.2 * JT, 0), ("4-1000", 0, 20 * JT), ("2-1200", 0, 2.2 * JT)], "Jual antar-PT",
         "p37_a7"),
        (a, "2026-10-15", [("5-1000", 12 * JT, 0), ("1-1300", 0, 12 * JT)], "HPP antar-PT", "p37_a8"),
        (b, "2026-10-15", [("1-1300", 20 * JT, 0), ("1-1500", 2.2 * JT, 0), ("2-1250", 0, 22.2 * JT)], "Beli antar-PT",
         "p37_b1"),
        (a, STEMPEL_DINI_HARI, [("6-3000", 1 * JT, 0), ("1-1100", 0, 1 * JT)], "Utilitas (1 Nov 00:30 WIB)", "p37_a9"),
        (a, "2026-11-03", [("1-1100", 10 * JT, 0), ("4-1000", 0, 10 * JT)], "Jual tunai Nov", "p37_a10"),
        (a, "2026-11-03", [("5-1000", 6 * JT, 0), ("1-1300", 0, 6 * JT)], "HPP Nov", "p37_a11"),
    ]:
        await jurnal(*args)
    return {"a": a, "b": b, "sa": {"entity_id": a}}


# ── U4 — Laba-Rugi Oktober tanpa beban dini hari 1 Nov; November memuatnya ───────────────────────────────────────────
async def test_PK37_U4_laba_rugi_oktober_dan_november(skenario1):
    okt = await fs.income_statement("2026-10-01", "2026-10-31", skenario1["sa"])
    assert cocok(okt["revenue_total"], 70 * JT) and cocok(okt["cogs_total"], 42 * JT)
    assert cocok(okt["gross_profit"], 28 * JT)
    assert cocok(okt["opex_total"], 4 * JT), f"beban Okt {okt['opex_total']:,.2f} (seharusnya 4.000.000)"
    assert cocok(okt["net_income"], 24 * JT), f"laba Okt {okt['net_income']:,.2f} (seharusnya 24.000.000)"
    nov = await fs.income_statement("2026-11-01", "2026-11-30", skenario1["sa"])
    assert cocok(nov["opex_total"], 1 * JT), f"beban Nov {nov['opex_total']:,.2f}"
    assert cocok(nov["net_income"], 3 * JT)                                     # 10 − 6 − 1
    # buku besar kas (1-1100) PT A: 31 Okt = 100 (a1) − 4 (a5) + 20 (a6) = 116 jt (sebelum unit: 115 jt, a9 ikut Okt);
    # 30 Nov = 116 + 10 (a10) − 1 (a9) = 125 jt
    assert cocok(await saldo_akun("1-1100", skenario1["a"], "2026-10-31"), 116 * JT)
    assert cocok(await saldo_akun("1-1100", skenario1["a"], "2026-11-30"), 125 * JT)


# ── U5 — jurnal beban tersimpan bertanggal buku 10 huruf; stempel UTC di created_at ──────────────────────────────────
async def test_PK37_U5_tanggal_jurnal_sepuluh_huruf(skenario1, db):
    je = await db.journal_entries.find_one({"source_type": "uji", "source_id": "p37_a9"}, {"_id": 0})
    assert je["date"] == "2026-11-01"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00", je["created_at"]), je["created_at"]


async def test_PK37_U5b_jurnal_manual_bertanggal_buku(aplikasi, db):
    from schemas_finance import JournalEntryCreate
    eid = await pt_uji("P37M")
    p = JournalEntryCreate(date=STEMPEL_DINI_HARI, description="uji manual PK-37", lines=[
        {"account_code": "6-2000", "debit": 1000, "credit": 0}, {"account_code": "1-1100", "debit": 0, "credit": 1000}])
    je = await gl.create_manual_entry(p, AKTOR_UJI, entity_id=eid)
    assert je["date"] == "2026-11-01"
    assert (await db.journal_entries.find_one({"id": je["id"]}, {"_id": 0}))["date"] == "2026-11-01"


# ── U6 / U7 — penjaga periode memakai tanggal buku WIB ───────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def okt_tertutup(aplikasi):
    eid = await pt_uji("P37C")
    await tutup_periode(eid, "2026-10")
    return eid


async def test_PK37_U6_dini_hari_1_nov_diterima_saat_oktober_tertutup(okt_tertutup):
    je = await jurnal(okt_tertutup, STEMPEL_DINI_HARI, [("6-2000", 1000, 0), ("1-1100", 0, 1000)], "dini hari", "p37_u6")
    assert je["date"] == "2026-11-01" and "backdated_in_unlock" not in je


async def test_PK37_U7_dini_hari_1_okt_ditolak_saat_oktober_tertutup(okt_tertutup, db):
    with pytest.raises(gl.ClosedPeriodError):
        await jurnal(okt_tertutup, "2026-09-30T18:00:00+00:00", [("6-2000", 1000, 0), ("1-1100", 0, 1000)],
                     "1 Okt 01.00 WIB", "p37_u7")
    assert await db.journal_entries.count_documents({"source_id": "p37_u7"}) == 0
    with pytest.raises(gl.ClosedPeriodError):                                    # pemeriksa di muka juga
        await gl.preflight_posting(okt_tertutup, "2026-09-30T18:00:00+00:00")
    await gl.preflight_posting(okt_tertutup, STEMPEL_DINI_HARI)                  # 1 Nov → lolos


# ── U8 — status periode untuk satu tanggal ───────────────────────────────────────────────────────────────────────────
async def test_PK37_U8_status_tanggal_lewat_api(klien, kepala_admin, okt_tertutup):
    h = {**kepala_admin, "X-Entity-Id": okt_tertutup}
    r = await klien.get("/api/finance/closing/status", headers=h,
                        params={"date": STEMPEL_DINI_HARI, "entity_id": okt_tertutup})
    assert r.status_code == 200, r.text
    assert r.json()["closed"] is False
    r = await klien.get("/api/finance/closing/status", headers=h,
                        params={"date": "2026-09-30T18:00:00+00:00", "entity_id": okt_tertutup})
    assert r.json()["closed"] is True                                            # 1 Okt 01.00 WIB
    r = await klien.get("/api/finance/closing/status", headers=h, params={"date": "2026-10-31", "entity_id": okt_tertutup})
    assert r.json()["closed"] is True


# ── Tambahan (tabel b1): "hari ini" antar-PT dan periode pajak di WIB ────────────────────────────────────────────────
async def test_PK37_b1_hari_ini_antar_pt_dan_periode_pajak_wib(monkeypatch):
    import datetime
    from services import book_date, input_tax_service, interco_return_service, interco_service, tax_center_service
    beku = datetime.datetime(2026, 10, 31, 17, 30, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)
    assert interco_service._today() == "2026-11-01"
    assert interco_return_service._today() == "2026-11-01"
    assert input_tax_service.period_of(STEMPEL_DINI_HARI) == "2026-11"
    assert input_tax_service.period_of("2026-10-31") == "2026-10"
    # bawaan "sekarang" mengikuti jam (dibekukan lewat book_date._sekarang)
    assert input_tax_service.period_of(None) == "2026-11"
    assert tax_center_service._cur_month() == "2026-11"


async def test_PK37_langkah6_tanggal_dokumen_keuangan_wib(aplikasi, monkeypatch):
    """Langkah 6: pemanggil `now_iso()[:10]`/`[:7]` yang menjadi tanggal jurnal atau periode keuangan dialihkan."""
    import datetime
    from services import book_date, input_tax_service, return_disposition_service
    beku = datetime.datetime(2026, 10, 31, 17, 30, tzinfo=datetime.timezone.utc)   # 1 Nov 00.30 WIB
    monkeypatch.setattr(book_date, "_sekarang", lambda: beku)
    assert return_disposition_service._today() == "2026-11-01"
    assert (await input_tax_service.vat_summary("", "ent_ksc"))["period"] == "2026-11"   # bulan pajak bawaan
