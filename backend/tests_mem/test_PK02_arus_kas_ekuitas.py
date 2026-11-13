"""PK-02 U12 — arus kas dan perubahan ekuitas (data `docs/finance/bukti-2026-11-13/skenario4.py`). 4 tes harus lulus."""
import pytest

from pembantu import jurnal, pt_uji, saldo_akun
from services import cash_flow_service as cf
from services import equity_statement_service as eq
from services import financial_statement_service as fs


def cocok(dapat, harap):
    return abs(float(dapat) - float(harap)) < 0.005


@pytest.fixture(scope="module")
async def pt(aplikasi):
    a = await pt_uji("CFA")
    for args in [
        ("2026-09-30", [("1-1100", 1000, 0), ("3-1000", 0, 1000)], "Setor modal", "m1"),
        ("2026-09-30", [("1-2100", 100, 0), ("1-1100", 0, 100)], "Beli mesin 100", "m2"),
        ("2026-09-30", [("6-6000", 20, 0), ("1-2900", 0, 20)], "Akumulasi susut 20", "m3"),
        ("2026-10-05", [("1-1100", 300, 0), ("4-1000", 0, 300)], "Jual tunai 300", "o1"),
        ("2026-10-06", [("6-2000", 50, 0), ("1-1100", 0, 50)], "Sewa tunai 50", "o2"),
        ("2026-10-10", [("1-1100", 130, 0), ("1-2900", 20, 0), ("1-2100", 0, 100), ("4-9100", 0, 50)], "Jual mesin", "o3"),
        ("2026-10-12", [("1-1100", 500, 0), ("2-1250", 0, 500)], "Pinjaman PT lain 500", "o4"),
        ("2026-10-15", [("1-1100", 200, 0), ("3-2900", 0, 200)], "Saldo awal rekening baru 200", "o5"),
    ]:
        await jurnal(a, *args)
    return {"a": a, "sa": {"entity_id": a}}


async def test_kas_akhir_sama_dengan_buku_besar(pt):
    r = await cf.cash_flow_statement("2026-10-01", "2026-10-31", pt["sa"])
    gl_kas = await saldo_akun("1-1100", pt["a"], "2026-10-31")
    assert cocok(gl_kas, 1980) and cocok(r["end_cash"], gl_kas)


async def test_arus_kas_tercocokkan(pt):
    assert (await cf.cash_flow_statement("2026-10-01", "2026-10-31", pt["sa"]))["reconciled"] is True


async def test_ekuitas_akhir_sama_dengan_neraca(pt):
    e = await eq.equity_statement("2026-10-01", "2026-10-31", pt["sa"])
    bs = await fs.balance_sheet("2026-10-31", scope=pt["sa"])
    assert cocok(e["end_total"], 1480) and cocok(bs["equity_total"], 1480)


async def test_laba_periode(pt):
    assert cocok((await eq.equity_statement("2026-10-01", "2026-10-31", pt["sa"]))["net_income"], 300)
