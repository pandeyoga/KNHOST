"""Latihan Keuangan 17 Nov — `rupiah()` membulatkan setengah ke atas seperti layar (bukan pembulatan bankir)."""
from core_utils import rupiah


def test_rupiah_setengah_ke_atas_sama_dengan_layar():
    assert rupiah(3484012.5) == "Rp 3.484.013"      # dulu "Rp 3.484.012" (bankir: ke genap)
    assert rupiah(3484013.5) == "Rp 3.484.014"
    assert rupiah(2.5) == "Rp 3" and rupiah(0.5) == "Rp 1"
    assert rupiah(-1500.5) == "-Rp 1.501"
    assert rupiah(1000.49) == "Rp 1.000" and rupiah(None) == "Rp 0" and rupiah("x") == "Rp 0"
