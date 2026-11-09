# Audit & perbaikan WMS-RFID — ringkasan (9 Nov 2026)

- Pelaksana: Claude Code (koordinator) + agen paralel di worktree terpisah. Status: **implemented_pending_review**.
- Permintaan pemilik (9 Nov): audit menyeluruh fungsi WMS & RFID — semua fitur, menu, UI/UX & elemen UI; riset WMS
  profesional; SSOT, skema & duplikasi; alur & niat implementasi; input/output & form; pemicu status/efek; standar
  elemen (form, tombol, cari, saring, ekspor Excel); performa, data besar, kegagalan perangkat/koneksi. Pemilik AFK dan
  menyerahkan keputusan ke rekomendasi koordinator → [`KEPUTUSAN-KOORDINATOR.md`](KEPUTUSAN-KOORDINATOR.md).
- Bersamaan: **gelombang 3 persiapan perangkat** — printer CP30EN, handheld C72, performa & ketahanan gate
  ([`../../rfid/hasil/PREP-F-PRINTER-CP30EN.md`](../../rfid/hasil/PREP-F-PRINTER-CP30EN.md),
  [`PREP-G-HANDHELD-C72.md`](../../rfid/hasil/PREP-G-HANDHELD-C72.md),
  [`PREP-H-GATE-PERFORMA.md`](../../rfid/hasil/PREP-H-GATE-PERFORMA.md)).

## 1. Audit (baca saja) — 10 lensa
| Laporan | Fokus | P0 | P1 | P2 | P3 |
|---|---|---|---|---|---|
| [B1](B1-UI-MENU-PERAN.md) + [B1b](B1b-SAPUAN-LANJUTAN.md) | Menu × peran × desktop/HP di peramban (**166/166 sel desktop**, 51 sel HP, 360 & 390 px) + sensus elemen | 0 | 18 | 33 | 10 |
| [B2a](B2a-ALUR-MASUK-OPNAME.md) | Alur masuk → QC → putaway → simpan, transfer masuk, retur, opname, pendaftaran awal (dijalankan lewat API, 112 transisi) | 4 | 11 | 16 | 4 |
| [B2b](B2b-ALUR-KELUAR-POTONG-RFID.md) | SO/ambil/potong/sampel/cek muat/SJ, transfer/MKO/perbaikan keluar, siklus tag RFID, gate V2, handheld (±341 transisi) | 6 | 15 | 13 | 2 |
| [B3a](B3a-SSOT-SKEMA-STOK.md) | SSOT, sensus koleksi (184 DB vs 224 kode), profil field, penulis per fakta, **uji silang angka stok 895 perbandingan** | 7 | 13 | 17 | 8 |
| [B3b](B3b-FORM-INPUT-DAFTAR.md) | 122 form → payload → skema → koleksi, pemilih vs isian bebas, 59 uji masukan buruk, ±55 daftar (cari/saring/halaman/ekspor) | 3 | 13 | 26 | 14 |
| [B4](B4-RISET-STANDAR-UI.md) | Riset 205 sumber (SAP EWM/Fiori, Dynamics 365 WMS, Oracle, Odoo, Zebra/Impinj, WCAG 2.2, Material, HIG…) → **Standar UI Gudang v1** | — | — | — | — |
| Performa (dalam [PREP-H](../../rfid/hasil/PREP-H-GATE-PERFORMA.md) + FIX-5) | Uji beban gate 2.000 roll, 4 gate, puncak ×10; index, N+1, data sintetis 346.700 roll | — | — | — | — |
| **Jumlah** | | **20** | **70** | **105** | **38** |

**Delapan keluhan pemilik — semuanya terbukti** (B1 §ringkasan): tugas tercampur semua PT/gudang tanpa sadar
pengguna; angka stok terlalu banyak & saling beda; jenis tugas tidak dibedakan; alur QC/GRN/OCR tidak konsisten; RFID;
pindai satu per satu; melihat ribuan roll sulit; elemen UI tidak standar (21 ukuran huruf arbitrer / 8.903 pemakaian,
±700 warna hex, ±790 tombol bergaya sendiri, 0 ekspor Excel).

**Pola kesalahan lintas laporan (terbanyak):** penjaga status berbentuk daftar-larang & penulis status tanpa CAS (roll
punya 63 penulis); cakupan lokasi hanya di daftar, tidak di aksi tulis; satu fakta dengan banyak rumus/nama ("Tersedia"
≥ 12 rumus); isian teks bebas mengisi rujukan (bin, satuan, grade); batas server senyap (100/200/500/5.000);
batal = "langsung tersedia di asal"; simulasi menulis jejak nyata; HP tidak setara desktop; alasan K-14 tidak
ditegakkan server; index `id` tidak ada di hampir semua koleksi.

## 2. Perbaikan — status semua P0
| ID | Masalah | Ditutup oleh |
|---|---|---|
| FRM-01 | `PATCH /warehouses` tembus PT & mengosongkan zona berisi roll | FIX-1 |
| FRM-23, SCP-1 | Roll tugas QC & 5 endpoint roll RFID bocor lintas PT (termasuk HPP) | FIX-1 |
| STM-IN-02 | Cakupan lokasi tidak dicek di aksi tulis (PA, transfer, opname) | FIX-1 |
| STK-1/2/6/13/14, SSOT-4 | Angka stok salah (katalog 0, Control Tower 0, Fisik tanpa committed, POS memakai panjang dipesan, untagged mentok 5.000, cadangan makloon tidak dikurangi di 9 endpoint) | FIX-2 (uji silang 64 → **0** selisih) |
| FLW-IN-01 | Tugas `qc_rejected/pending` bisa diterima ulang → roll & `received_qty` ganda tanpa jurnal | FIX-3a |
| OPN-01 / STM-IN-01 | Pembekuan pendaftaran ditembus terima PO jalur lama + bin teks bebas → stok ganda + jurnal | FIX-3a |
| INP-02 | Bin opname teks bebas → surplus fiktif + jurnal | FIX-3a |
| STM-OUT-1, STM-OUT-3, FLW-OUT-2 | Eskalasi mengembalikan roll yang sudah di SJ; override → roll yatim & reservasi ganda; SO backorder macet | FIX-3b |
| CUT-1, CUT-3 | Potong sampel memakan panjang SO lain; serah-terima tugas batal memindah roll tanpa dokumen | FIX-3b |
| RFID-2 (+ calon P0 MKO-03, PRT-01/02, ANOM-06, POT-05 — semua terbukti) | EPC pensiun dipakai ulang; roll `consumed` hidup lagi; reversal retur QC; GET yang menulis; rollback melepas semua reservasi | FIX-3b |

| Paket | Isi utama | Uji baru | Laporan |
|---|---|---|---|
| FIX-1 | Lokasi kerja untuk semua peran ("Lokasi: … ▾"), pekerjaan fisik per gedung lintas PT berlabel PT & jenis, cakupan di setiap aksi tulis, logout benar (sesi server dicabut, PT tidak terbawa), aplikasi sopir, data uji disembunyikan, guardrail `verify_scope_guard` | 30 | [FIX-1](hasil/FIX-1-CAKUPAN.md) |
| FIX-2 | Satu layanan `stock_figures`; API & komponen **dua angka** (LOKAL + "Total grup (semua PT)") + rincian (lokasi, PT, status, barang akan datang, ATP) | 16 | [FIX-2](hasil/FIX-2-ANGKA-STOK.md) |
| FIX-3a | Tabel transisi daftar-izin + CAS tugas masuk; kait pembekuan; bin dari struktur (`BinSelect`); validator alasan `ReasonStr` (huruf, server); pendaftaran awal dua langkah (Finance); form HP lengkap | 28 | [FIX-3a](hasil/FIX-3a-ALUR-MASUK.md) |
| FIX-3b | Tabel transisi keluar (`outbound_task_state`) + CAS; ambil wajib pindai roll; susut potong dijurnal; batal di jalan → `returning`; simulator terpagar; EPC tak dipakai ulang | 26 | [FIX-3b](hasil/FIX-3b-ALUR-KELUAR.md) |
| FIX-4 | Standar UI Gudang v1 tahap 1 ([`KN_37`](../../KN_37_STANDAR_UI_GUDANG.md)): token huruf/warna AA (58/58 pasangan lolos), **Unduh Excel/CSV** di 31/37 daftar WMS-RFID lewat Pusat Export, HP gudang ≥ 14/16 px & ≥ 48 px, guardrail ratchet `verify_ui_standard` + `verify_ui_contrast` | 15 + Jest 14 | [FIX-4](hasil/FIX-4-STANDAR-UI.md) |
| FIX-5 | Performa WMS: index, N+1 terima transfer/putaway, halaman server, layar roll besar | lihat laporan | [FIX-5](hasil/FIX-5-PERFORMA-WMS.md) |

## 3. Verifikasi gabungan (koordinator)
- Kode `main` lengkap (F, G, H, FIX-1/2/3a/3b) vs dasar `cb9f924` (audit + F + G, sebelum perbaikan), salinan DB acuan
  sama, server bersih per putaran (dipastikan lewat rute baru), **83 berkas uji lama** WMS-RFID-stok: daftar gagal/error
  **identik** (118 / 474 / 21 di keduanya). Uji lama yang perilakunya sengaja diubah disesuaikan & dicatat
  (commit `252303e`: alasan K-14, cadangan makloon, lokasi kerja, loop bersama, urutan roll). Satu perbaikan kode dari
  verifikasi: alasan finalisasi opname dicek sesudah izin/cakupan.
- Uji baru per berkas (DB dipulihkan tiap berkas): FIX-1 30/30, FIX-2 16/16, FIX-3a 28/28, FIX-3b 26/26, PREP-A…G,
  integrasi pembekuan, worker gate H 7/7 — **lulus semua**; `test_iter117/118` 18/18 & 8/8; skrip gate V2 54/54 & 36/36.
  **Merah:** 1 dari 3 uji batas kinerja H (transaksi latar terima transfer 2.000 roll 148 dtk > target 120 dtk) →
  sasaran FIX-5.
- Peramban (stack `kn-uji`, akun petugas Soreang & admin): bilah "Lokasi: Soreang"; daftar Barang Keluar hanya
  gedung Soreang, berlabel PT + chip "Pesanan (SO) / Sample"; gate & riwayat ikut lokasi; tab Operasional Gate &
  Antrean Printer; "Belum Ber-tag (500 dari 2.900)"; papan stok dua angka berlabel; logout → `/auth/me` 401 & PT tidak
  terbawa; HP 360 & 390 px tanpa geser mendatar, tombol ≥ 44 px; tombol Unduh Excel/CSV di daftar desktop.

## 4. Yang perlu dilakukan pemilik / admin
1. **Push** ke GitHub (ditolak pemeriksa izin otomatis — balas "push").
2. **Skrip perbaikan data** (semua dry-run bawaan; jalankan `--apply` di DB uji dulu, lalu produksi setelah dicadangkan):
   `scripts/fix_data_2026_11_09_gedung_bersama.py` (SRG-01, WH-JKT → bersama), `…_tandai_data_uji.py` (12 data uji
   disembunyikan), `…_fix3a_alur_masuk.py`, `…_fix3b_alur_keluar.py` (**`rfid_simulation_off` wajib sebelum pilot
   reader nyata**), `backend/scripts/migrate_fix2_inspection_hold_status.py`.
3. **Isi lokasi kerja** akun non-gudang (admin › Pengguna) & penugasan PT petugas Soreang.
4. **VPS dedicated** (rekomendasi PREP-H): 4 vCPU (8 untuk tumbuh), 16 GB RAM, NVMe 200 GB, MongoDB replica set
   dengan cache 4–6 GB, 2–4 worker uvicorn + penjadwal & worker transaksi gate terpisah, cadangan off-site + uji pulih
   bulanan, lokasi Jakarta/Singapura.
5. Keputusan yang sengaja tidak diambil: lihat [`KEPUTUSAN-KOORDINATOR.md`](KEPUTUSAN-KOORDINATOR.md) §"Masih butuh pemilik".

## 5. Belum dikerjakan (tahap berikut)
Pusat Tugas Gudang terpadu & tugas berikutnya (HP web), tampilan tersimpan, penampil roll penuh produk → lot → lokasi
(sebagian di FIX-5), Standar UI tahap 2 (StatusBadge/EmptyState/peleburan pager, migrasi 12 px saat layar disentuh),
tabel transisi untuk dokumen lain (GRN, PA, SPK, retur — SSOT-1), kunci makloon per roll, D2/D5 (Finance), SSE push
(butuh replica set), dan semua yang butuh perangkat nyata (uji meja U300/C72/CP30EN, kalibrasi, pilot).
