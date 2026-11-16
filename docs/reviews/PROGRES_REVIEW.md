# Kemajuan review & audit domain (dihasilkan `scripts/review/periksa_selesai.py progres`)

Dihasilkan 2026-11-16 07:42 UTC pada commit `2cb6434c`. Angka dihitung dari berkas validasi/audit dan tracker — bukan klaim. Jangan disunting tangan.

## Batch review

| Batch | Isi | Butir lengkap | Baris kode dibaca | Uji lulus / gagal | Putusan | Status | Belum lengkap (maks. 8) |
|---|---|---|---|---|---|---|---|
| B0 | R0 — 8 keputusan integrasi FIX-6…FIX-10 + fungsi yang diubah dua sisi | 9/9 | 1,083 | 72 / 0 | {'benar': 4, 'perlu_keputusan_pemilik': 1, 'terhambat_lingkungan': 3} | SELESAI | — |
| B1 | Keuangan Kritis/Tinggi — kas, pembayaran, piutang & hutang | 17/17 | 4,508 | 155 / 6 | {'reopened': 4, 'verified': 10, 'perlu_keputusan_pemilik': 3} | SELESAI | — |
| B2 | Keuangan Kritis/Tinggi — jurnal, periode, posting, laporan | 0/33 | 0 | 0 / 0 | — | belum | FX-01, FX-02, FX-03, IC-05, FX-08, GL-01, GL-04, UX-01 |
| B3 | Keuangan Kritis/Tinggi — antar-PT, persediaan, retur, nota | 0/7 | 0 | 0 / 0 | — | belum | IC-01, IV-01, IV-02, IV-03, IC-02, FX-12, DB-01 |
| B4 | Riset modul Tinggi — kredit, insentif, pajak pesanan, pembayaran, gaji | 0/14 | 0 | 0 / 0 | — | belum | CR-02, CR-05, KM-01, KM-02, CR-01, TX-01, TX-03, TX-04 |
| B5 | Konfigurasi & peran Tinggi | 0/23 | 0 | 0 / 0 | — | belum | KF-01, KF-02, KF-09, KF-10, KF-11, KP-05, KP-01, KP-02 |
| B6 | Keuangan Sedang/Rendah | 0/77 | 0 | 0 / 0 | — | belum | GL-06, UX-17, IA-06, IA-15, SL-12, UX-10, IC-08, FX-04 |
| B7 | Riset modul Sedang/Rendah | 0/32 | 0 | 0 / 0 | — | belum | AG-01, AG-02, AG-04, AG-05, AG-03, CR-06, CR-09, CR-04 |
| B8 | Konfigurasi & peran Sedang/Rendah | 0/44 | 0 | 0 / 0 | — | belum | KF-03, KF-05, KF-06, KP-13, KP-29, KP-30, KF-04, KP-11 |

## Audit domain

### `docs/audit/2026-11-16-domain` — SELESAI

| Domain | Skenario dijalankan | Gagal | Terhambat | Form diinventaris | Baris dropdown | Temuan | Baris dibaca |
|---|---|---|---|---|---|---|---|
| A A-MASTER-STAGE.md | 9/9 | 1 | 2 | 8/8 | 30 | {'Tinggi': 4, 'Sedang': 2} | 0 |
| B B-MAKLOON.md | 10/10 | 2 | 7 | 6/6 | 26 | {'Sedang': 3, 'Tinggi': 3} | 0 |
| C C-RND.md | 6/6 | 1 | 5 | 5/5 | 17 | {'Tinggi': 2} | 0 |
| D D-RETUR.md | 8/8 | 3 | 2 | 4/4 | 12 | {'Rendah': 3, 'Sedang': 3, 'Tinggi': 2} | 0 |
| E E-QC-MDQ.md | 6/6 | 3 | 3 | 3/3 | 8 | {'Tinggi': 2, 'Sedang': 1, 'Rendah': 1} | 0 |
| F F-PESANAN-SESUDAH-POS.md | 8/8 | 3 | 3 | 4/4 | 7 | {'Tinggi': 3, 'Rendah': 1} | 0 |

