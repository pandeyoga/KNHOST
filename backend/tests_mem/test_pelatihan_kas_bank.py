"""Pelatihan keuangan 18 Nov 2026 (Bagian B · Kas & Bank, F10 Rekonsiliasi) — dua perbaikan `bank_recon_service`.

1. M38 — rekening koran yang DITEMPEL ke kotak impor (tanpa nama berkas, `POST /bank-reconciliation/import-file`)
   tercatat `import_source = "tempel"`; unggah berkas (ada `file_name`) tetap `berkas`.
2. Ringkasan rekonsiliasi dengan saringan periode: sisi BUKU (`book`, `unmatched_book_txns`) ikut periode yang dipilih,
   sama dengan sisi mutasi (dulu buku selalu seluruh riwayat → "Selisih rekening vs buku" periode tidak bermakna).
   Tanpa saringan periode angka tidak berubah.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
R1 = "ba_latih_kb"
H = "/api/bank-reconciliation"
CSV = "Tanggal,Keterangan,Cabang,Jumlah,DB/CR,Saldo\n{tgl},{ket},0000,\"{nom}\",{arah},0\n"


def _kas(tid: str, tgl: str, nominal: float, arah: str) -> dict:
    return {"id": tid, "number": tid.upper(), "cash_type": "kas_besar", "direction": arah, "amount": nominal,
            "category": "uji", "description": f"kas uji {tid}", "entity_id": E1, "account_id": R1, "ref_type": "",
            "ref_id": "", "txn_date": tgl, "status": "posted", "reconciled_amount": 0.0, "created_by": "uji"}


@pytest.fixture(scope="module", autouse=True)
async def dasar(aplikasi, db):
    await db.bank_accounts.insert_one({"id": R1, "name": "BCA Latih KB", "account_type": "bank", "cash_type": "kas_besar",
                                       "bank_name": "BCA", "entity_id": E1, "is_active": True, "opening_balance": 0})
    # Buku: satu kas lama (1 Mar) dan dua kas sekitar hari periode (17 Mar, salah satunya stempel UTC malam = 18 Mar WIB).
    # Tanggal jauh di depan supaya kas dari modul uji lain (bertanggal hari ini) tidak masuk periode.
    await db.cash_transactions.insert_many([
        _kas("kas_kb_lama", "2031-03-01", 5_000_000, "in"),
        _kas("kas_kb_17", "2031-03-17T03:00:00+00:00", 1_250_000, "in"),
        _kas("kas_kb_18", "2031-03-17T18:30:00+00:00", 400_000, "out"),   # 18 Mar 01.30 WIB
    ])


async def test_tempel_tercatat_tempel_berkas_tetap_berkas(klien, kepala_admin, db):
    h = {**kepala_admin, "X-Entity-Id": E1}
    raw = CSV.format(tgl="17/03/2031", ket="TRSF E-BANKING CR UJI TEMPEL", nom="1.250.000,00", arah="CR")
    r = await klien.post(f"{H}/import-file", headers=h, json={"bank_account_id": R1, "raw": raw, "year_hint": 2031})
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    ln = await db.bank_statement_lines.find_one({"bank_account_id": R1, "description": "TRSF E-BANKING CR UJI TEMPEL"})
    assert ln["import_source"] == "tempel" and ln["import_file"] == ""
    raw2 = CSV.format(tgl="18/03/2031", ket="BIAYA ADM UJI BERKAS", nom="15.000,00", arah="DB")
    r = await klien.post(f"{H}/import-file", headers=h,
                         json={"bank_account_id": R1, "raw": raw2, "year_hint": 2031, "file_name": "koran-bca.csv"})
    assert r.status_code == 200, r.text
    ln2 = await db.bank_statement_lines.find_one({"bank_account_id": R1, "description": "BIAYA ADM UJI BERKAS"})
    assert ln2["import_source"] == "berkas" and ln2["import_file"] == "koran-bca.csv"
    st = (await klien.get(f"{H}/summary", headers=h, params={"bank_account_id": R1})).json()["statement"]
    assert st["sources"]["tempel"] == 1 and st["sources"]["berkas"] == 1 and st["user_lines"] == 2


async def test_ringkasan_periode_menyaring_buku(klien, kepala_admin):
    h = {**kepala_admin, "X-Entity-Id": E1}
    semua = (await klien.get(f"{H}/summary", headers=h, params={"bank_account_id": R1})).json()
    # Tanpa periode = seluruh riwayat (bisa memuat kas lama tanpa rekening dari modul uji lain: rekening tunggal PT).
    assert semua["book"]["in"] >= 6_250_000.0 and semua["book"]["out"] >= 400_000.0
    assert semua["unmatched_book_txns"] >= 3
    p17 = (await klien.get(f"{H}/summary", headers=h,
                           params={"bank_account_id": R1, "start": "2031-03-17", "end": "2031-03-17"})).json()
    assert p17["statement"]["net"] == 1_250_000.0
    assert p17["book"] == {"in": 1_250_000.0, "out": 0.0, "net": 1_250_000.0}   # kas 18 Mar WIB & 1 Mar tidak ikut
    assert p17["unmatched_book_txns"] == 1
    assert p17["difference"] == 0.0
    p18 = (await klien.get(f"{H}/summary", headers=h, params={"bank_account_id": R1, "start": "2031-03-18"})).json()
    assert p18["book"]["out"] == 400_000.0 and p18["book"]["in"] == 0.0
    assert p18["statement"]["out"] == 15_000.0 and p18["difference"] == round(-15_000.0 + 400_000.0, 2)


async def test_lpj_atas_nama_pemohon_pd(klien, kepala_admin, db):
    """F07 — Finance mengetik LPJ atas nama karyawan: penanggung jawab (`dibuat_oleh`, dipakai bilah "Sisa uang muka …
    harus dikembalikan …", deskripsi kas pengembalian, dan daftar hutang reimburse) = pemohon PD, bukan pengetiknya."""
    await db.bank_accounts.insert_one({"id": "rek_latih_kk", "name": "Kas Kecil Latih", "entity_id": E1,
                                       "account_type": "cash", "cash_type": "kas_kecil", "is_active": True})
    await db.cash_advances.insert_one({
        "id": "ca_latih_kb", "number": "PD-LATIH-KB", "entity_id": E1, "status": "disbursed", "kegiatan": "uji",
        "divisi": "Penjualan", "lines": [{"description": "uang jalan", "qty": 1, "unit_price": 500_000, "amount": 500_000}],
        "total_amount": 500_000.0, "approvals": [], "payment_method": "cash", "created_by": "Ayu Pemohon",
        "created_by_id": "usr_ayu_pemohon"})
    h = {**kepala_admin, "X-Entity-Id": E1}
    r = await klien.post("/api/cash-advance-settlements", headers=h, json={
        "cash_advance_id": "ca_latih_kb", "periode": "2031-03",
        "expense_lines": [{"date": "2031-03-17", "description": "bensin", "category": "transportasi", "amount": 232_000}]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["dibuat_oleh"] == "Ayu Pemohon"           # bukan nama admin pengetik
    assert d["created_by"] and d["created_by"] != "Ayu Pemohon"   # pengetik tetap tercatat di `created_by`
    r = await klien.post("/api/cash-advance-settlements", headers=h, json={   # isian eksplisit tetap menang
        "cash_advance_id": "ca_latih_kb", "dibuat_oleh": "Budi", "expense_lines": [{"amount": 1, "category": "atk"}]})
    assert r.status_code == 409   # satu LPJ aktif per PD (aturan lama) — tidak berubah
