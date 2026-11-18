"""Rekening koran EXCEL (.xlsx) untuk latihan Rekonsiliasi Bank R1–R9 — dibuat dari Kartu Peserta (`g_rekon:*`).

Bentuknya meniru unduhan KlikBCA Bisnis: baris pembuka (rekening, nama, periode), tabel `Tanggal Transaksi · Keterangan
· Cabang · Jumlah · Saldo` dengan nominal bergaya "1,234,061.00 CR"/"DB", lalu ringkasan saldo di bawah baris kosong.
Layar Rekonsiliasi membacanya dengan template "BCA — Rekening Koran (CSV)" (dikenali otomatis).

Isi tiap berita transfer sengaja dirancang (lihat docs/pelatihan/2026-11-18_keuangan/rekonsiliasi/SKENARIO_UJI_REKONSILIASI.md):
R1 memuat kode bayar · R2 hanya nama pelanggan rekonsiliasi (usulan, skor 75) · R3 nomor tagihan pemasok · R4 satu transfer untuk dua
kwitansi · R5 dua transfer untuk satu kwitansi · R6 biaya administrasi + bunga · R7 setoran tanpa nama (titipan).
Semua berita memuat "LATIHAN NN" karena rekening BCA dipakai bersama semua peserta.

  cd /app/backend && python scripts/buat_mutasi_bank_latihan.py --mulai 61 --peserta 62 --keluar /tmp/mutasi_latihan
  (jalankan seed dulu: python scripts/seed_pelatihan_keuangan_kn.py --mulai 61 --peserta 62 --hanya a_dasar:akun,a_dasar:mitra,g_rekon)

Keluaran per peserta: `peserta_NN/R1_kode_bayar_NN.xlsx` … `R7_titipan_NN.xlsx`, `R0_rekening_koran_lengkap_NN.xlsx`
(semua baris sekaligus — pakai SALAH SATU: berkas lengkap ATAU berkas per skenario) dan `manifest_NN.json`.
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Font  # noqa: E402

from db import db  # noqa: E402

FLAG = "pelatihan_keuangan"
SALDO_AWAL = 50_000_000.00
BIAYA_ADM = 15_000.00
HEADER = ["Tanggal Transaksi", "Keterangan", "Cabang", "Jumlah", "Saldo"]

#: kode skenario → (nama berkas, judul)
SKENARIO = {
    "R1": ("kode_bayar", "Transfer masuk dengan kode bayar — cocok otomatis"),
    "R2": ("tanpa_kode", "Transfer masuk tanpa kode — usulan, tautkan manual"),
    "R3": ("bayar_pemasok", "Transfer keluar ke pemasok dengan nomor tagihan — cocok otomatis"),
    "R4": ("pecah", "Satu transfer untuk dua kwitansi — pecah 1:N"),
    "R5": ("gabung", "Dua transfer untuk satu kwitansi — gabung N:1"),
    "R6": ("biaya_bunga", "Biaya administrasi & bunga bank — catat dari layar rekonsiliasi"),
    "R7": ("titipan", "Setoran tanpa nama — titipkan lalu alokasikan"),
}


def _ribu(n: float) -> str:
    return f"{n:,.2f}"                         # gaya KlikBCA: 1,234,061.00


def _tgl(iso: str) -> str:
    return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")


def baris_peserta(no: int, k: Dict[str, Any]) -> Dict[str, List[Tuple[str, str, float, str]]]:
    """Baris mutasi per skenario: (tanggal ISO, keterangan, nominal, CR/DB). Tanpa kartu g_rekon lengkap → KeyError."""
    nn = f"{no:02d}"
    r1, r2, r3 = k["g_rekon:kode_bayar"], k["g_rekon:tanpa_kode"], k["g_rekon:bayar_pemasok"]
    r4, r5, r7 = k["g_rekon:pecah"], k["g_rekon:gabung"], k["g_rekon:titipan"]
    hari = r1["tanggal"]                       # baris tanpa catatan buku (R6, R7) bertanggal hari yang sama
    bunga = round(18_000 + no * 100 + 0.45, 2)
    return {
        "R1": [(r1["tanggal"], f"TRSF E-BANKING CR {r1['kode_bayar']} LATIHAN {nn} TOKO REKON PESERTA {nn}", r1["nominal"], "CR")],
        "R2": [(r2["tanggal"], f"TRSF E-BANKING CR LATIHAN {nn} TOKO REKON PESERTA {nn}", r2["nominal"], "CR")],
        "R3": [(r3["tanggal"], f"TRSF E-BANKING DB {r3['tagihan']} LATIHAN {nn} PEMASOK GREY PESERTA {nn}", r3["nominal"], "DB")],
        "R4": [(r4["tanggal"], f"TRSF E-BANKING CR LATIHAN {nn} TOKO REKON PESERTA {nn} DUA NOTA", r4["nominal"], "CR")],
        "R5": [(r5["tanggal"], f"TRSF E-BANKING CR LATIHAN {nn} TOKO REKON PESERTA {nn} TAHAP SATU", r5["bagian_1"], "CR"),
               (r5["tanggal"], f"TRSF E-BANKING CR LATIHAN {nn} TOKO REKON PESERTA {nn} TAHAP DUA", r5["bagian_2"], "CR")],
        "R6": [(hari, f"BIAYA ADM LATIHAN {nn}", BIAYA_ADM, "DB"), (hari, f"BUNGA LATIHAN {nn}", bunga, "CR")],
        "R7": [(hari, f"SETORAN TUNAI CDM LATIHAN {nn}", r7["nominal"], "CR")],
    }


def tulis_xlsx(path: Path, rekening: Dict[str, Any], rows: List[Tuple[str, str, float, str]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Mutasi Rekening"
    tgl = sorted(r[0] for r in rows)
    ws.append(["Informasi Rekening - Mutasi Rekening"])
    ws.append(["No. rekening", str(rekening.get("account_number") or "-")])   # teks (bukan angka) seperti unduhan bank
    ws.append(["Nama", "SUKACITA TEXTILE"])
    ws.append(["Periode", f"{_tgl(tgl[0])} - {_tgl(tgl[-1])}"])
    ws.append(["Kode Mata Uang", "IDR"])
    ws.append([])
    ws.append(HEADER)
    saldo, masuk, keluar = SALDO_AWAL, 0.0, 0.0
    for d, ket, amt, arah in rows:
        if arah == "CR":
            saldo, masuk = saldo + amt, masuk + amt
        else:
            saldo, keluar = saldo - amt, keluar + amt
        ws.append([_tgl(d), ket, "0000", f"{_ribu(amt)} {arah}", _ribu(saldo)])
    ws.append([])
    for label, nilai in (("Saldo Awal", SALDO_AWAL), ("Mutasi Kredit", masuk), ("Mutasi Debet", keluar), ("Saldo Akhir", saldo)):
        ws.append([label, "", "", _ribu(nilai)])
    ws["A1"].font = Font(bold=True, size=12)
    for c in ws[7]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDE", (18, 62, 8, 22, 18)):
        ws.column_dimensions[col].width = w
    for r in ws.iter_rows(min_row=8, min_col=4, max_col=5):
        for c in r:
            c.alignment = Alignment(horizontal="right")
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mulai", type=int, default=1)
    ap.add_argument("--peserta", type=int, default=1, help="nomor peserta terakhir")
    ap.add_argument("--keluar", default="/tmp/mutasi_latihan")
    a = ap.parse_args()
    state = (await db.migrations.find_one({"id": FLAG}, {"_id": 0}) or {}).get("peserta", {})
    rekening = await db.bank_accounts.find_one({"entity_id": "ent_ksc", "account_type": "bank", "is_active": {"$ne": False}},
                                               {"_id": 0}, sort=[("created_at", 1)]) or {}
    out = Path(a.keluar)
    gagal = []
    for no in range(a.mulai, a.peserta + 1):
        nn = f"{no:02d}"
        try:
            per = baris_peserta(no, state.get(nn, {}))
        except KeyError as e:
            gagal.append(f"{nn} (kartu belum punya {e}; jalankan seed --hanya a_dasar:akun,a_dasar:mitra,g_rekon)")
            continue
        folder = out / f"peserta_{nn}"
        manifest = {"peserta": nn, "rekening": rekening.get("name", ""), "nomor_rekening": rekening.get("account_number", ""),
                    "template": "BCA — Rekening Koran (CSV)", "dibuat": datetime.now().isoformat(timespec="seconds"),
                    "berkas": {}}
        semua: List[Tuple[str, str, float, str]] = []
        for kode, rows in per.items():
            nama, judul = SKENARIO[kode]
            berkas = f"{kode}_{nama}_{nn}.xlsx"
            tulis_xlsx(folder / berkas, rekening, rows)
            manifest["berkas"][kode] = {"berkas": berkas, "judul": judul,
                                        "baris": [{"tanggal": d, "keterangan": ket, "nominal": amt,
                                                   "arah": "masuk" if arah == "CR" else "keluar"} for d, ket, amt, arah in rows]}
            semua += rows
        tulis_xlsx(folder / f"R0_rekening_koran_lengkap_{nn}.xlsx", rekening, semua)
        manifest["berkas"]["R0"] = {"berkas": f"R0_rekening_koran_lengkap_{nn}.xlsx",
                                    "judul": "Semua baris R1–R7 dalam satu rekening koran", "baris_total": len(semua)}
        (folder / f"manifest_{nn}.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"peserta {nn}: {len(semua)} baris · {folder}")
    if gagal:
        sys.exit("Tidak dibuat: " + "; ".join(gagal))


if __name__ == "__main__":
    asyncio.run(main())
