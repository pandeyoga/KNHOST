"""PK-02 U11 — laporan inti di atas jurnal contoh `docs/finance/bukti-2026-11-13/skenario1.py`, dibandingkan hitungan
tangan. 15 tes yang harus SELALU lulus. a9 bertanggal 2026-10-31 tanpa jam (zona waktu diuji terpisah di GL-05)."""
import pytest

from pembantu import AKTOR_UJI, jurnal, pt_uji, saldo_akun
from services import closing_service as cs
from services import financial_statement_service as fs
from services import gl_service as gl
from services.gl_service import ClosedPeriodError

JT = 1_000_000


def cocok(dapat, harap):
    return abs(float(dapat) - float(harap)) < 0.005


@pytest.fixture(scope="module")
async def pt(aplikasi):
    a, b = await pt_uji("AAA"), await pt_uji("BBB")
    for args in [
        (a, "2026-10-01", [("1-1100", 100 * JT, 0), ("3-1000", 0, 100 * JT)], "Setor modal", "a1"),
        (a, "2026-10-05", [("1-1300", 60 * JT, 0), ("2-1100", 0, 60 * JT)], "Beli persediaan kredit", "a2"),
        (a, "2026-10-10", [("1-1200", 55.5 * JT, 0), ("4-1000", 0, 50 * JT), ("2-1200", 0, 5.5 * JT)], "Jual kredit + PPN", "a3"),
        (a, "2026-10-10", [("5-1000", 30 * JT, 0), ("1-1300", 0, 30 * JT)], "HPP", "a4"),
        (a, "2026-10-20", [("6-2000", 4 * JT, 0), ("1-1100", 0, 4 * JT)], "Sewa tunai", "a5"),
        (a, "2026-10-25", [("1-1100", 20 * JT, 0), ("1-1200", 0, 20 * JT)], "Terima piutang", "a6"),
        (a, "2026-10-15", [("1-1250", 22.2 * JT, 0), ("4-1000", 0, 20 * JT), ("2-1200", 0, 2.2 * JT)], "Jual antar-PT", "a7"),
        (a, "2026-10-15", [("5-1000", 12 * JT, 0), ("1-1300", 0, 12 * JT)], "HPP antar-PT", "a8"),
        (b, "2026-10-15", [("1-1300", 20 * JT, 0), ("1-1500", 2.2 * JT, 0), ("2-1250", 0, 22.2 * JT)], "Beli antar-PT", "b1"),
        (a, "2026-10-31", [("6-3000", 1 * JT, 0), ("1-1100", 0, 1 * JT)], "Utilitas", "a9"),
        (a, "2026-11-03", [("1-1100", 10 * JT, 0), ("4-1000", 0, 10 * JT)], "Jual tunai Nov", "a10"),
        (a, "2026-11-03", [("5-1000", 6 * JT, 0), ("1-1300", 0, 6 * JT)], "HPP Nov", "a11"),
    ]:
        await jurnal(*args)
    return {"a": a, "b": b, "sa": {"entity_id": a}}


async def test_pendapatan_okt(pt):
    assert cocok((await fs.income_statement("2026-10-01", "2026-10-31", pt["sa"]))["revenue_total"], 70 * JT)


async def test_hpp_okt(pt):
    assert cocok((await fs.income_statement("2026-10-01", "2026-10-31", pt["sa"]))["cogs_total"], 42 * JT)


async def test_laba_kotor_okt(pt):
    assert cocok((await fs.income_statement("2026-10-01", "2026-10-31", pt["sa"]))["gross_profit"], 28 * JT)


async def test_total_aset_31_okt(pt):
    # kas 115 + piutang 35,5 + piutang antar-PT 22,2 + persediaan 18
    assert cocok((await fs.balance_sheet("2026-10-31", scope=pt["sa"]))["assets_total"], 190.7 * JT)


async def test_total_kewajiban_31_okt(pt):
    assert cocok((await fs.balance_sheet("2026-10-31", scope=pt["sa"]))["liabilities_total"], 67.7 * JT)


async def test_ekuitas_31_okt(pt):
    assert cocok((await fs.balance_sheet("2026-10-31", scope=pt["sa"]))["equity_total"], 123 * JT)


async def test_neraca_saldo_debit(pt):
    assert cocok((await gl.trial_balance("2026-10-31", pt["sa"]))["total_debit"], 237.7 * JT)


async def test_neraca_saldo_kredit(pt):
    assert cocok((await gl.trial_balance("2026-10-31", pt["sa"]))["total_credit"], 237.7 * JT)


async def test_saldo_kas_buku_besar(pt):
    assert cocok(await saldo_akun("1-1100", pt["a"], "2026-10-31"), 115 * JT)


@pytest.fixture(scope="module")
async def tutup_okt(pt):
    return await cs.close_period("month", "2026-10", AKTOR_UJI, pt["a"])


async def test_tutup_lr_okt_tetap(pt, tutup_okt):
    assert cocok((await fs.income_statement("2026-10-01", "2026-10-31", pt["sa"]))["net_income"], 23 * JT)


async def test_tutup_ekuitas_tetap(pt, tutup_okt):
    assert cocok((await fs.balance_sheet("2026-10-31", scope=pt["sa"]))["equity_total"], 123 * JT)


async def test_tutup_laba_berjalan_nol(pt, tutup_okt):
    assert cocok((await fs.balance_sheet("2026-10-31", scope=pt["sa"]))["equity"]["current_earnings"], 0)


async def test_tutup_laba_ditahan(pt, tutup_okt):
    bs = await fs.balance_sheet("2026-10-31", scope=pt["sa"])
    assert cocok(next((x["amount"] for x in bs["equity"]["lines"] if x["code"] == "3-2000"), 0), 23 * JT)


async def test_tutup_jurnal_mundur_ditolak(pt, tutup_okt):
    with pytest.raises(ClosedPeriodError):
        await jurnal(pt["a"], "2026-10-28", [("6-2000", 1 * JT, 0), ("1-1100", 0, 1 * JT)], "Mundur", "a12")


async def test_laba_bersih_jan_nov(pt, tutup_okt):
    assert cocok((await fs.income_statement("2026-01-01", "2026-11-30", pt["sa"]))["net_income"], 27 * JT)
