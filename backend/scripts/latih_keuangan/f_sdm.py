"""Bagian SDM & GAJI (K09, H01–H04; keputusan pemilik K-SDM-01 17 Nov 2026: "SDM/HR itu dipegang finance juga").

Skenario SDM dikerjakan peserta SENDIRI dari awal (menambah karyawan, masukan gaji, proses gaji, bayar), jadi modul ini
TIDAK membuat dokumen apa pun — hanya menuliskan ke Kartu Peserta isian yang berbeda per peserta (nama karyawan baru,
NIK, NPWP, rekening, tanggal libur latihan) dan memeriksa prasyarat bersama:

* masa gaji latihan = **Oktober 2026**, proses **SUSULAN** per peserta. Proses reguler PT per masa hanya satu dan memuat
  semua karyawan (Oktober 2026 sudah diposting untuk F15; November = pekerjaan nyata akhir bulan). Masa November TIDAK
  dipakai: jurnal gaji bertanggal akhir masa (30 Nov) dan tanggal bayar tidak boleh sebelum tanggal jurnal, jadi gaji
  November belum bisa dibayar pada hari pelatihan. F18 hanya menutup September, jadi Oktober tetap terbuka.
  Cerita: karyawan baru masuk 1 Oktober 2026 dan terlewat proses reguler Oktober → gaji Oktobernya dibayar sebagai
  **Rapel** di proses susulan Oktober (H02–H04); lembur yang diajukan di H02 (16 Nov) masuk proses reguler November.
* proses susulan memuat SEMUA masukan yang sudah disahkan dan belum terpakai pada masa itu → `masukan_tersisa` di kartu
  harus 0 sebelum pelatihan (bila tidak: sahkan/hitung dulu oleh pelatih, atau batalkan).
* rekening berperuntukan Gaji PT Sukacita ada (bayar gaji H04).

Tanpa tulisan ke basis data → aman di VPS dan aman dijalankan ulang.
"""
from typing import Any, Dict

from db import db

from .konteks import KSC, PREFIX, LatihCtx, Peserta

MASA_SDM = "2026-10"
TANGGAL_MASUK = "2026-10-01"
GAJI_POKOK = 7_500_000.0
TUNJANGAN = ("Tunjangan transport", 500_000.0)
RAPEL = GAJI_POKOK + TUNJANGAN[1]   # gaji Oktober yang terlewat proses reguler


def data_karyawan(p: Peserta) -> Dict[str, Any]:
    """Isian H01–H04 per peserta (sama dengan `docs/pelatihan/2026-11-18_keuangan/uji/sdm/sdm_lib.js`)."""
    return {
        "nama": f"{PREFIX} {p.kode} · Andi Pratama", "nik": f"32730115089{p.no:05d}", "tanggal_masuk": TANGGAL_MASUK,
        "ptkp": "K/1", "npwp": f"09.254.294.3-4{p.no % 100:02d}.000", "bank": "BCA", "rekening": f"88000{p.no:05d}",
        "atas_nama": "Andi Pratama", "gaji_pokok": GAJI_POKOK, "tunjangan": TUNJANGAN[0], "tunjangan_nominal": TUNJANGAN[1],
        "masa_gaji": MASA_SDM, "masukan": "Rapel", "masukan_nominal": RAPEL,
        "lembur_tanggal": "2026-11-16", "lembur_jam": 2,
        "libur_latihan": f"2026-12-{10 + p.no % 15:02d}",
    }


async def karyawan_baru(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    d = data_karyawan(p)
    ada = await db.hr_employees.find_one({"name": d["nama"], "entity_id": KSC}, {"_id": 0, "id": 1, "code": 1})
    sisa = await db.hr_pay_inputs.count_documents({"entity_id": KSC, "pay_period": MASA_SDM, "status": "approved"})
    rek = await db.bank_accounts.find_one({"entity_id": KSC, "purposes": "gaji", "is_active": {"$ne": False}},
                                          {"_id": 0, "name": 1})
    if not rek:
        raise RuntimeError("PT Sukacita belum punya rekening berperuntukan Gaji (Keuangan › Kas & Bank › Rekening & Saldo).")
    return {**d, "rekening_gaji_pt": rek["name"], "masukan_tersisa": sisa,
            "sudah_dibuat": (ada or {}).get("code", ""), "karyawan_id": (ada or {}).get("id", "")}


PREPS = [("karyawan_baru", karyawan_baru)]
