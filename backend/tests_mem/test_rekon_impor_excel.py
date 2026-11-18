"""Rekonsiliasi Bank — unggah rekening koran Excel (.xlsx), 18 Nov 2026.

Unduhan internet banking umumnya Excel: baris pembuka (rekening, periode), tabel mutasi, lalu ringkasan saldo di bawah
baris kosong. `bank_statement_parser.xlsx_to_text` mengubah lembar itu menjadi teks CSV yang dibaca TEMPLATE yang sama
seperti CSV; endpoint pratinjau & impor menerima `file_b64`.

P1–P6 = pembaca murni (tanpa DB); A1–A5 = lewat API aplikasi utuh (pratinjau, impor, impor ulang, template eksplisit,
berkas rusak). Rekening `ba_rkx` milik `ent_ksc` disisip langsung.
"""
from __future__ import annotations

import base64
import io
from datetime import datetime

import pytest
from openpyxl import Workbook

from services import bank_statement_parser as parser

E1 = "ent_ksc"
R1 = "ba_rkx"


def _xlsx(sheets: dict) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for nama, rows in sheets.items():
        ws = wb.create_sheet(nama)
        for r in rows:
            ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# KlikBCA Bisnis: baris pembuka, nominal teks bergaya Inggris + penanda CR/DB menempel, ringkasan di bawah baris kosong.
BCA_ROWS = [
    ["Informasi Rekening - Mutasi Rekening"],
    ["No. rekening", "'7415595554"],
    ["Nama", "SUKACITA TEXTILE"],
    ["Periode", "18/11/2026 - 18/11/2026"],
    ["Kode Mata Uang", "IDR"],
    [],
    ["Tanggal Transaksi", "Keterangan", "Cabang", "Jumlah", "Saldo"],
    ["18/11/2026", "TRSF E-BANKING CR 1811/FTSCY/WS95051 TOKO KAIN MAJU", "0000", "1,500,000.00 CR", "10,000,000.00"],
    ["18/11/2026", "TRSF E-BANKING DB 1811/FTFVA/WS95031 CV BENANG", "0000", "2,250,500.00 DB", "7,749,500.00"],
    ["18/11/2026", "BIAYA ADM", "0000", "15,000.00 DB", "7,734,500.00"],
    [],
    ["Saldo Awal", "", "", "8,500,000.00"],
    ["Mutasi Kredit", "", "", "1,500,000.00"],
    ["Mutasi Debet", "", "", "2,265,500.00"],
    ["Saldo Akhir", "", "", "7,734,500.00"],
]

# Livin' Mandiri: sel tanggal & angka asli Excel, dua kolom nominal.
MANDIRI_ROWS = [
    ["Rekening Koran", "", "", "", "", ""],
    ["Tanggal", "Keterangan", "No. Referensi", "Debet", "Kredit", "Saldo"],
    [datetime(2026, 11, 18), "TRF DARI TOKO KAIN MAJU INV-0012", "FT26322ABC", 0, 2750000.5, 12750000.5],
    [datetime(2026, 11, 19), "BIAYA TRANSFER", "FT26323XYZ", 6500, 0, 12743500.5],
]

# BRI CMS: kolom Tipe D/K.
BRI_ROWS = [
    ["Tanggal Transaksi", "Uraian", "Tipe", "Jumlah", "Saldo"],
    ["18/11/2026", "SETORAN TUNAI TOKO", "K", 1250000, 5000000],
    ["18/11/2026", "PEMBAYARAN SUPPLIER", "D", 400000, 4600000],
]


def _baca(data: bytes):
    conv = parser.xlsx_to_text(data, parser.BUILTIN_FORMATS)
    fmt = parser.detect_format(conv["text"], parser.BUILTIN_FORMATS)
    rows, errors = parser.parse_rows(conv["text"], fmt, 2026)
    return conv, fmt, rows, errors


def test_P1_bca_baris_pembuka_dan_ringkasan_dilewati():
    conv, fmt, rows, errors = _baca(_xlsx({"Mutasi": BCA_ROWS}))
    assert conv["header_found"] and conv["header_row"] == 7 and conv["rows"] == 3, conv
    assert fmt["bank_code"] == "bca", fmt["name"]
    assert errors == [], errors
    assert [(r["stmt_date"], r["amount"], r["direction"]) for r in rows] == [
        ("2026-11-18", 1_500_000.0, "in"), ("2026-11-18", 2_250_500.0, "out"), ("2026-11-18", 15_000.0, "out")]


def test_P2_mandiri_sel_tanggal_dan_angka_excel():
    conv, fmt, rows, errors = _baca(_xlsx({"Sheet1": MANDIRI_ROWS}))
    assert fmt["bank_code"] == "mandiri" and conv["header_row"] == 2, (fmt["name"], conv)
    assert errors == [], errors
    assert [(r["stmt_date"], r["amount"], r["direction"], r["ref"]) for r in rows] == [
        ("2026-11-18", 2_750_000.5, "in", "FT26322ABC"), ("2026-11-19", 6_500.0, "out", "FT26323XYZ")]


def test_P3_bri_tipe_d_k():
    _conv, fmt, rows, errors = _baca(_xlsx({"Mutasi": BRI_ROWS}))
    assert fmt["bank_code"] == "bri" and errors == []
    assert [(r["amount"], r["direction"]) for r in rows] == [(1_250_000.0, "in"), (400_000.0, "out")]


def test_P4_tabel_di_lembar_kedua():
    conv, fmt, rows, _ = _baca(_xlsx({"Ringkasan": [["Laporan"], ["Saldo", 1]], "Mutasi": BCA_ROWS}))
    assert conv["sheet"] == "Mutasi" and fmt["bank_code"] == "bca" and len(rows) == 3


def test_P5_berkas_bukan_xlsx_ditolak_dengan_arahan():
    with pytest.raises(parser.StatementFileError, match=r"\.xls \(Excel 97–2003\)"):
        parser.xlsx_to_text(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 64, parser.BUILTIN_FORMATS)
    with pytest.raises(parser.StatementFileError, match="bukan Excel"):
        parser.xlsx_to_text(b"Tanggal,Keterangan\n", parser.BUILTIN_FORMATS)
    with pytest.raises(parser.StatementFileError, match="kosong"):
        parser.xlsx_to_text(_xlsx({"Kosong": []}), parser.BUILTIN_FORMATS)
    with pytest.raises(parser.StatementFileError, match="lebih dari 5 MB"):
        parser.xlsx_to_text(b"PK\x03\x04" + b"0" * (parser.XLSX_MAX_BYTES + 1), parser.BUILTIN_FORMATS)


def test_P6_judul_tidak_dikenali_jatuh_ke_baris_berisi_pertama():
    data = _xlsx({"Data": [[], ["Tgl", "Ket", "Nominal"], ["18/11/2026", "X", 1000]]})
    conv = parser.xlsx_to_text(data, parser.BUILTIN_FORMATS)
    assert not conv["header_found"] and conv["text"].splitlines()[0] == "Tgl,Ket,Nominal"


# ── Lewat API ────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def dasar(aplikasi, db):
    await db.bank_accounts.insert_one({"id": R1, "name": "BCA RKX", "account_type": "bank", "cash_type": "bank",
                                       "bank_name": "BCA", "entity_id": E1, "is_active": True, "status": "active",
                                       "opening_balance": 0})


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.mark.anyio
async def test_A1_pratinjau_excel_kenali_otomatis(dasar, klien, kepala_admin):
    r = await klien.post("/api/bank-reconciliation/preview", headers=kepala_admin,
                         json={"file_b64": _b64(_xlsx({"Mutasi": BCA_ROWS})), "year_hint": 2026})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["detected"] and d["format"]["bank_code"] == "bca" and d["total"] == 3 and d["error_count"] == 0, d
    assert d["source"] == {"file_kind": "xlsx", "sheet": "Mutasi", "header_row": 7, "header_found": True}
    assert d["sum_in"] == 1_500_000 and d["sum_out"] == 2_265_500


@pytest.mark.anyio
async def test_A2_impor_excel_tercatat_sebagai_berkas(dasar, klien, db, kepala_admin):
    r = await klien.post("/api/bank-reconciliation/import-file", headers=kepala_admin,
                         json={"bank_account_id": R1, "file_b64": _b64(_xlsx({"Mutasi": BCA_ROWS})),
                               "file_name": "mutasi_bca_18nov.xlsx", "year_hint": 2026})
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["imported"], d["skipped"], d["source"]["file_kind"]) == (3, 0, "xlsx"), d
    rows = await db.bank_statement_lines.find({"bank_account_id": R1}, {"_id": 0}).to_list(10)
    assert len(rows) == 3
    assert {(x["import_source"], x["import_file"]) for x in rows} == {("berkas", "mutasi_bca_18nov.xlsx")}


@pytest.mark.anyio
async def test_A3_impor_ulang_berkas_sama_dilewati(dasar, klien, kepala_admin):
    r = await klien.post("/api/bank-reconciliation/import-file", headers=kepala_admin,
                         json={"bank_account_id": R1, "file_b64": _b64(_xlsx({"Mutasi": BCA_ROWS})),
                               "file_name": "mutasi_bca_18nov.xlsx", "year_hint": 2026})
    assert r.status_code == 200, r.text
    assert (r.json()["imported"], r.json()["skipped"]) == (0, 3)


@pytest.mark.anyio
async def test_A4_template_dipilih_eksplisit(dasar, klien, kepala_admin):
    fmts = (await klien.get("/api/bank-reconciliation/formats", headers=kepala_admin)).json()
    mandiri = next(f for f in fmts if f["bank_code"] == "mandiri")
    bri = next(f for f in fmts if f["bank_code"] == "bri")
    data = _b64(_xlsx({"Sheet1": MANDIRI_ROWS}))
    r = await klien.post("/api/bank-reconciliation/preview", headers=kepala_admin,
                         json={"file_b64": data, "format_id": mandiri["id"]})
    assert r.status_code == 200 and r.json()["total"] == 2 and not r.json()["detected"], r.text
    # Template salah → tidak ada baris; alasannya disebut (judul kolom tidak dikenali), tidak diam-diam kosong.
    r = await klien.post("/api/bank-reconciliation/preview", headers=kepala_admin,
                         json={"file_b64": data, "format_id": bri["id"]})
    assert r.status_code == 200 and r.json()["total"] == 0, r.text
    assert "judul kolom tidak dikenali" in r.json()["errors"][0]["reason"]
    r = await klien.post("/api/bank-reconciliation/import-file", headers=kepala_admin,
                         json={"bank_account_id": R1, "file_b64": data, "format_id": bri["id"], "file_name": "x.xlsx"})
    assert r.status_code == 400 and "Tidak ada baris mutasi" in r.text


@pytest.mark.anyio
async def test_A5_berkas_rusak_atau_xls_lama_400(dasar, klien, kepala_admin):
    r = await klien.post("/api/bank-reconciliation/preview", headers=kepala_admin, json={"file_b64": "bukan base64!!"})
    assert r.status_code == 400 and "rusak" in r.text, r.text
    r = await klien.post("/api/bank-reconciliation/preview", headers=kepala_admin,
                         json={"file_b64": _b64(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 64)})
    assert r.status_code == 400 and "Simpan Sebagai" in r.text, r.text
