# Tracker Temuan Review — KNHOST

Satu tracker untuk semua paket review. ID tidak pernah diganti atau dipakai ulang.
Arti status & aturan: [`README.md`](README.md).

**Review aktif:** [`2026-10-20/`](2026-10-20/) — mulai dari `2026-10-20/README.md`,
lalu `AUDIT_FRONTEND_2026-10-20.md` dan `PROMPT_PERBAIKAN_FRONTEND_2026-10-20.md`.

| Paket | Baseline review | Posisi terhadap `f4e8f0b` (HEAD saat paket diterima) |
|---|---|---|
| Frontend (FE-xx) | `8dab383` | 17 commit di belakang — wajib cek ulang |
| Backend (AUD-xx) | `63c38bd` | 42 commit di belakang — wajib cek ulang |

## Frontend — paket 2026-10-20 (baseline `8dab383`)

| ID | Judul | Prio | Fase | Status | Berlaku di HEAD | Commit perbaikan | Laporan |
|---|---|---|---|---|---|---|---|
| FE-01 | Special Order multi-produk kehilangan item/qty saat pricing dan konversi | P1 | UI-01 | open | belum dicek | | |
| FE-02 | Kontrol pilihan Interco tidak memperbarui nilai | P1 | UI-02 | open | belum dicek | | |
| FE-03 | Peta modul akses tidak mengikuti menu/hub terbaru | P1 | UI-03 | open | belum dicek | | |
| FE-04 | Tombol/petugas dibatasi nama role meski izin efektif berbeda | P2 | UI-03 | open | belum dicek | | |
| FE-05 | Data Gudang menolak Admin Gudang yang berizin | P2 | UI-03 | open | belum dicek | | |
| FE-06 | Target Harga Khusus dari Meja Saya tidak dirender | P2 | UI-04 | open | belum dicek | | |
| FE-07 | Error retur tidak terlihat dan modal menutup saat gagal | P2 | UI-04 | open | belum dicek | | |
| FE-08 | Respons SO lama menimpa pilihan SO baru di form retur | P2 | UI-04 | open | belum dicek | | |
| FE-09 | Pemilih SO retur diam-diam terbatas 200 pesanan | P2 | UI-04 | open | belum dicek | | |
| FE-10 | Antrean QC salah label satuan dan agregasi campuran | P2 | UI-05 | open | belum dicek | | |
| FE-11 | Error awal penerimaan transfer tertutup loading | P2 | UI-05 | open | belum dicek | | |
| FE-12 | Neraca unknown ditampilkan Seimbang | P2 | UI-05 | open | belum dicek | | |
| FE-13 | Tooltip defisit kas menghapus tanda negatif | P2 | UI-05 | open | belum dicek | | |

## Backend — paket 2026-10-19 (baseline `63c38bd`, ikut dalam folder 2026-10-20)

Detail & arahan perbaikan: `2026-10-20/TEMUAN_TERVERIFIKASI.md`,
`2026-10-20/LANJUTAN_WMS_SPECIAL_ORDER_MIGRASI.md`. Belum ada prompt per fase untuk
kelompok ini — urutan pengerjaan menunggu arahan reviewer/owner.

| ID | Judul | Fase | Status | Berlaku di HEAD | Commit perbaikan | Laporan |
|---|---|---|---|---|---|---|
| AUD-RND-01 | ACC labdip dapat meluluskan siklus yang handfeel-nya ditolak | BE | open | belum dicek | | |
| AUD-RND-02 | Versi artwork yang tidak ada diterima sebagai referensi proofing ulang | BE | open | belum dicek | | |
| AUD-RND-03 | Referensi kontrak terminated diterima `_validate_contract_ref` tetapi tidak muncul di daftar pilihan | BE | pending_decision | belum dicek | | |
| AUD-EXP-01 | Ekspor berkelompok selesai tetapi unduhan ditolak 403 | BE | open | belum dicek | | |
| AUD-EXP-02 | Ekspor dapat menggandakan baris saat sumber berubah, jumlah baris tetap cocok | BE | open | belum dicek | | |
| AUD-SO-01 | Proses lama dapat melepas kunci realisasi milik proses baru | BE | open | belum dicek | | |
| AUD-WMS-01 | Stok opname berubah sebelum jurnal berhasil; retry tidak memulihkan | BE | open | belum dicek | | |
| AUD-MKL-01 | Excel rekap klaim makloon gagal saat memiliki baris mitra | BE | open | belum dicek | | |
| AUD-MKL-02 | Rincian rekap klaim dipotong 1.000 baris, berbeda dari total | BE | open | belum dicek | | |
| AUD-MIG-01 | Apply migrasi menyatakan matched tetapi melewatkan fulfillment kosong | BE | open | belum dicek | | |
| AUD-MIG-02 | Rollback menghapus perubahan operasional setelah migrasi | BE | open | belum dicek | | |
| AUD-RET-01 | Pembuangan BS gagal di tengah proses dan retry tidak memulihkan | BE | open | belum dicek | | |

## Keputusan yang ditunggu

| ID | Pertanyaan untuk owner | Dicatat |
|---|---|---|
| AUD-RND-03 | Apakah kontrak berstatus *terminated* boleh dipakai sebagai referensi historis? Bila ya, daftar pilihan perlu menampilkannya; bila tidak, validasi backend harus menolaknya. | 2026-10-20 |

## Riwayat perubahan tracker

| Tanggal | Oleh | Perubahan |
|---|---|---|
| 2026-10-20 | Claude Code | Tracker dibuat dari paket 2026-10-20 (13 FE + 12 AUD); semua `open` kecuali AUD-RND-03 `pending_decision` |
