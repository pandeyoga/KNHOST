"""Uji variasi isian pelatihan keuangan 18 Nov 2026 — Rekonsiliasi Bank (mode tempel), `bank_statement_parser`.

Peserta menempel rekening koran dengan bentuk yang beragam. Yang dulu salah dan kini diperbaiki:
1. Nominal bergaya Inggris ("1,500,000.00") ke template BCA (desimal koma) terbaca 0 → ditolak "Nominal tidak terbaca";
   kebalikannya ("1.500.000,00") ke template berdesimal titik. Kini gaya yang JELAS dibaca apa adanya; bentuk ambigu
   ("1.500" / "1,500") tetap mengikuti template.
2. Teks berpemisah TAB (salin dari Excel / KlikBCA), titik koma, atau spasi berderet (salin dari PDF) ke template ber-koma
   → setiap baris "Tanggal tidak terbaca". Kini pemisah yang ada dipakai.
3. Tanpa baris judul kolom → pratinjau diam-diam "Terbaca 0 baris". Kini ditolak dengan arahan.
4. Alasan baris yang ditolak menyebut isi selnya ("Tanggal tidak terbaca ('31/02/2026')").
Perilaku yang sudah benar (format tanggal, minus = keluar, penanda DB/CR, baris kosong) dikunci agar tidak mundur.
"""
from __future__ import annotations

import copy

import pytest

from services.bank_statement_parser import BUILTIN_FORMATS, parse_amount, parse_rows

BCA = copy.deepcopy(next(f for f in BUILTIN_FORMATS if f["bank_code"] == "bca"))
BCA["columns"]["direction"] = "db/cr"       # sama dengan template BCA di data acuan (kolom DB/CR)
PERMATA = copy.deepcopy(next(f for f in BUILTIN_FORMATS if f["bank_code"] == "permata"))
H = "Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo"


def _baca(baris, fmt=BCA):
    rows, errors = parse_rows("\n".join(baris), fmt, 2026)
    return [(r["stmt_date"], r["amount"], r["direction"]) for r in rows], errors


@pytest.mark.parametrize("teks,gaya,harap", [
    ("1.500.000,00", "id", 1500000.0), ("1500000", "id", 1500000.0), ("1.500.000", "id", 1500000.0),
    ("1,500,000.00", "id", 1500000.0), ("1,500,000", "id", 1500000.0), ("Rp 1.500.000,00", "id", 1500000.0),
    ("1,500,000.00", "en", 1500000.0), ("1.500.000,00", "en", 1500000.0), ("1.500.000", "en", 1500000.0),
    ("1.500", "id", 1500.0), ("1,5", "id", 1.5), ("1,500", "en", 1500.0), ("1.5", "en", 1.5),
    # titik/koma yang tidak diikuti 3 angka = desimal (dulu "3240090.00" ke template BCA → 324.009.000, ×100 diam-diam)
    ("3240090.00", "id", 3240090.0), ("3240090.5", "id", 3240090.5), ("1500000,00", "en", 1500000.0),
    ("1,5", "en", 1.5), ("1.500.00", "id", 0.0),
])
def test_nominal_gaya_jelas_dibaca_apa_adanya(teks, gaya, harap):
    assert parse_amount(teks, gaya) == (harap, False)


def test_nominal_minus_tetap_bertanda():
    assert parse_amount("-1.500.000,00", "id") == (1500000.0, True)


@pytest.mark.parametrize("tgl", ["17/11/2026", "2026-11-17", "17-11-2026", "17 Nov 2026", "17/11"])
def test_bentuk_tanggal(tgl):
    rows, errors = _baca([H, f'{tgl},TRSF A,0000,"1.500.000,00",CR,0'])
    assert rows == [("2026-11-17", 1500000.0, "in")] and errors == []


@pytest.mark.parametrize("baris,harap", [
    ('17/11/2026,TRSF A,0000,1500000,DB,0', ("2026-11-17", 1500000.0, "out")),
    ('17/11/2026,TRSF A,0000,1.500.000,CR,0', ("2026-11-17", 1500000.0, "in")),
    ('17/11/2026,TRSF A,0000,"1,500,000.00",CR,0', ("2026-11-17", 1500000.0, "in")),
    ('17/11/2026,TRSF A,0000,3240090.00,CR,0', ("2026-11-17", 3240090.0, "in")),
    ('17/11/2026,TRSF A,0000,"-1.500.000,00",,0', ("2026-11-17", 1500000.0, "out")),
    ('17/11/2026,TRSF A,0000,"1.500.000,00 DB",,0', ("2026-11-17", 1500000.0, "out")),
])
def test_bentuk_nominal_dan_arah(baris, harap):
    rows, errors = _baca([H, baris])
    assert rows == [harap] and errors == []


@pytest.mark.parametrize("pisah", ["\t", ";", "|"])
def test_pemisah_lain_dari_excel(pisah):
    rows, errors = _baca([H.replace(",", pisah), pisah.join(["17/11/2026", "TRSF A", "0000", "1.500.000,00", "DB", "0"]),
                          pisah.join(["18/11/2026", "BIAYA ADM", "0000", "15.000,00", "DB", "0"])])
    assert rows == [("2026-11-17", 1500000.0, "out"), ("2026-11-18", 15000.0, "out")] and errors == []


def test_kolom_dipisah_spasi_dari_pdf():
    rows, errors = _baca(["Tanggal    Keterangan    Cabang    Jumlah    DB/CR    Saldo",
                          "17/11/2026    TRSF E-BANKING CR A    0000    1.500.000,00    CR    0"])
    assert rows == [("2026-11-17", 1500000.0, "in")] and errors == []


def test_koma_di_keterangan_tidak_mengganti_pemisah():
    rows, errors = _baca([H, '17/11/2026,"TRSF A; B; C",0000,"1.500.000,00",CR,0'])
    assert rows == [("2026-11-17", 1500000.0, "in")] and errors == []


def test_tanpa_judul_kolom_ditolak_dengan_arahan():
    rows, errors = _baca(['17/11/2026,TRSF A,0000,"1.500.000,00",CR,0'])
    assert rows == [] and len(errors) == 1
    assert "judul kolom" in errors[0]["reason"] and "tanggal" in errors[0]["reason"]


def test_template_salah_kolom_nominal_hilang():
    rows, errors = _baca(["Tanggal,Keterangan,Debet,Kredit,Saldo", '17/11/2026,TRSF A,,"1.500.000,00",0'])
    assert rows == [] and "nominal" in errors[0]["reason"]


def test_baris_kosong_dilewati_dan_alasan_menyebut_isi_sel():
    rows, errors = _baca([H, "", '31/02/2026,TRSF A,0000,"1.500.000,00",CR,0', "  ",
                          '17/11/2026,TRSF B,0000,"abc",CR,0', '17/11/2026,TRSF C,0000,"20.000,00",DB,0', ""])
    assert rows == [("2026-11-17", 20000.0, "out")]
    alasan = [e["reason"] for e in errors]
    assert alasan[0].startswith("Tanggal tidak terbaca ('31/02/2026')")
    assert alasan[1].startswith("Nominal tidak terbaca / nol ('abc')")


def test_koma_desimal_tanpa_kutip_tetap_ditolak_dengan_arahan():
    rows, errors = _baca([H, "17/11/2026,TRSF A,0000,1.500.000,00,CR,0"])
    assert rows == [] and "tanda kutip" in errors[0]["reason"]


def test_template_berdesimal_titik_permata():
    rows, errors = _baca(["Date,Description,Debit,Credit,Balance,Reference",
                          '2026-11-17,TRSF A,,"1.500.000,00",0,R1', '2026-11-17,FEE,"1,500.50",,0,R2'], PERMATA)
    assert rows == [("2026-11-17", 1500000.0, "in"), ("2026-11-17", 1500.5, "out")] and errors == []
