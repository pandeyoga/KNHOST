"""Pelatihan 18 Nov (uji F10 pukul 01.17 WIB) — skor rekonsiliasi bank membandingkan TANGGAL BUKU WIB.

Transaksi kas dicatat 18 Nov 01.17 WIB tersimpan `txn_date` = 2026-11-17T18:17Z. Dulu `_d()` memotong 10 huruf pertama
(17 Nov) sehingga mutasi bank 18 Nov dinilai "Tanggal beda 1 hari" dan skornya turun dari 60 ke 55.
"""
from services import bank_recon_service as brs

CFG = {"w_amount": 40, "w_date": 20, "w_ref": 30, "w_name": 10, "window_days": 3, "amount_tol": 0}


def test_tanggal_buku_wib_untuk_cap_waktu_utc():
    line = {"direction": "out", "amount": 310000, "stmt_date": "2026-11-18", "description": "TRSF E-BANKING DB"}
    txn = {"direction": "out", "amount": 310000, "txn_date": "2026-11-17T18:17:29.250673+00:00"}
    hasil = brs.score_pair(line, txn, CFG)
    assert hasil["day_diff"] == 0, hasil
    assert any(e["label"] == "Tanggal sama" for e in hasil["explain"]), hasil["explain"]


def test_tanggal_tetap_bila_sudah_tanggal_buku():
    assert brs._d("2026-11-18").date().isoformat() == "2026-11-18"
    assert brs._d("2026-11-18T09:00:00+07:00").date().isoformat() == "2026-11-18"
    assert brs._d("2026-11-17T16:59:59+00:00").date().isoformat() == "2026-11-17"   # 23.59 WIB
    assert brs._d("") is None and brs._d("bukan tanggal") is None
