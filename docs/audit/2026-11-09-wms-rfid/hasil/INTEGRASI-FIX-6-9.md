# Integrasi FIX-6 … FIX-10 (10 Nov 2026)

Koordinator: Claude Code. Status semua paket: **implemented_pending_review** (bukan `verified`).
Dasar pembanding: `cd6963a` (kode yang ter-deploy di produksi 9 Nov). Kepala integrasi: `882f9eb` (kode diuji di
`7dcc888`; sesudahnya hanya dokumen, guardrail & satu uji).

## 1. Paket yang digabung

| Paket | Isi | Laporan | Gabung |
|---|---|---|---|
| FIX-8 | Standar UI Gudang tahap 2: `StatusBadge` + kosakata status tunggal, `EmptyState` (memuat/kosong/saringan/galat/tanpa izin), satu pager & kotak cari, waktu WIB, tanpa id mentah, nomor dokumen satu skema, tampilan tersimpan (K-B4-12) | [FIX-8](FIX-8-STANDAR-UI-2.md) | `6b5929e` |
| FIX-6 | Keputusan pemilik 10 Nov: retur jual masuk stok saat dipindai (karantina retur, nilai saat settle), tolak QC + retur supplier dipilih per kasus (ganti barang / potong tagihan), GRN per PT, penanda minta inspeksi, izin ekspor MD, tabel transisi GRN/retur | [FIX-6](FIX-6-KEPUTUSAN-10NOV.md) | `76ada4d` |
| FIX-9 | Cadangan bahan makloon dikunci per roll (B3a SSOT-4 tuntas) + skrip migrasi | [FIX-9](FIX-9-KUNCI-MAKLOON.md) | `fd46c64` |
| FIX-7 | Performa sisa (cari roll, papan status, dasbor, pohon stok, mutasi berpagar), 17 daftar halaman server, masa simpan log, skrip data aman produksi, `uq_id` 62 koleksi | [FIX-7](FIX-7-PERFORMA-SISA.md) · [panduan produksi](PANDUAN-SKRIP-DATA-PRODUKSI.md) | `18698a8` |


## 2. Perubahan koordinator saat integrasi

| Commit | Perubahan | Alasan |
|---|---|---|
| `5b66fb8` | Tabel saldo stok memakai `EmptyState`; `loading` awal = `true` | Cek peramban: layar Stok sempat menulis "Tidak ada data stok" sebelum data tiba (UI-50). Sesudah: kosong → "Memuat data stok…" → baris |
| `5b66fb8` | Peringatan "Lokasi kerja belum diatur" dipendekkan, terpotong rapi, disembunyikan < 1180 px | Bug FIX-1 (sudah di produksi): kalimat panjang melebarkan bilah atas → halaman bergeser ke samping di 1024 px (scrollWidth 1140 > 1024). Sesudah: 1009 ≤ 1024 |
| `7ad4ac4` | Tombol **"Minta inspeksi"** di panel tugas penerimaan desktop & HP (`InspectionRequestToggle`, alasan wajib) + 5 uji Jest | Sisa FIX-6 (API sudah ada, tombol belum) |
| `7ad4ac4` | 4 pelanggaran G-UI dari FIX-6 (dibuat sebelum aturan FIX-8): penanda baris PO → `StatusBadge`; label PT GRN/kedatangan tanpa id mentah; latar `bg-kn-neutral` (abu tua + teks abu → tak terbaca) → `bg-kn-neutral-soft`; "0 tugas" saat memuat → "Memuat…" | `verify_ui_standard` merah sesudah gabung |
| 5 berkas | Konflik FIX-7 × FIX-8 (opname desktop & RFID, verifikasi cetak, HP gudang, barang keluar): dipertahankan **keduanya** — halaman server + jumlah sungguhan (FIX-7) dan keadaan memuat/galat/tanpa izin (FIX-8) | — |
| `7dcc888` | Skrip FIX-6 memakai pagar produksi bersama (`data_fix_guard`: `--production` + bukti backup; dulu `--allow-db`); panduan produksi memuat skrip FIX-6 & FIX-9 + urutan | Satu pola pagar untuk semua skrip data |
| `fe8c9a6` | `ENTITY_REGISTRY` memuat `material_reservations` + field kunci FIX-9; `CODEBASE_MAP` dibangkitkan ulang | Diminta FIX-9 |
| `3b4df45` | `verify_ref_unlink`: `log_retention` didaftarkan di `DYNAMIC_OK` (koleksi dibatasi `DELETABLE`/`PROTECTED`); saklar Kelompok/Daftar Stok › Roll → `FilterChips` baku + jumlah roll tidak "0" saat memuat | Guardrail naik sesudah gabung |
| `882f9eb` | `test_l10_ln101`: alasan finalisasi deskriptif | Uji tidak stabil: "ops01 <heksa acak>" kadang < 5 huruf → ditolak K-14 |

## 3. Verifikasi

### 3.1 Uji lama — kode produksi `cd6963a` vs kepala integrasi (data acuan `kn_test_trial_2026-11-08`, 83 berkas)
| | Gagal | Lulus | Error |
|---|---|---|---|
| `cd6963a` | 118 | 474 | 21 |
| integrasi | 119 | 473 | 21 |

Satu-satunya beda: `test_l10_ln101_roll_count::test_ops01…` — uji tidak stabil (alasan acak, lihat `882f9eb`);
sesudah diperbaiki **lulus** (4/4). Tidak ada uji yang gagal karena kode baru. `test_iter117_p09` 18/18,
`test_iter118_p10` 8/8. Skrip gate V2: integrasi 54 PASS, extended 36 PASS (sama dengan sebelumnya).

### 3.2 Uji baru (per berkas, DB dipulihkan tiap berkas)
FIX-1 30 · FIX-2 16 · FIX-3a 28 · FIX-3b 26 · FIX-4 15 · FIX-5 31 · PREP-A 10 · B 3 · C 15 · D1 20 · D2 11 · F printer 22
· F connector e2e 5 · G 11 · freeze putaway 4 · H worker 7 · H perf 3 · FE-03 akses 6 · **FIX-6 16 · FIX-7 perf 33 · FIX-7
daftar 21 · FIX-7 skrip data 7² · FIX-8 tampilan tersimpan 19 · FIX-9 13** — semua lulus.

² butuh salinan data acuan bernama `kainnusantara` (prasyarat uji); putaran pertama tanpa salinan itu → 7 error
"DB salinan produksi tidak ada", diulang dengan salinan → 7/7.

### 3.3 Guardrail — `cd6963a` vs integrasi (kode di dalam kontainer, bukan bind mount)
Sama: `atomic_claim` 6, `auth_coverage` 28 (endpoint AI), `numeric_bounds` 3 (`SoOverrideLineIn`), `to_list_bound` 6,
`qty_dual` 4, `entity_label` (`docEntityRegistry.js:14` + 1 lama), `no_secrets` 8 (laporan pytest lama; +2 `.env` yang
disalin koordinator ke kontainer uji — bukan di git). Sesudah `3b4df45`: `page_tabs` **PASS** (dasar merah), `ref_unlink`
3 = dasar (yang ke-4 dari FIX-7 ditutup). `ui_standard` PASS 5.691 cek, `ui_contrast` 67/67, `scope_guard` PASS.

### 3.4 Jest
* Putaran pertama berbarengan dengan 44 guardrail di mesin yang sama: 57 gagal karena waktu habis; suite yang gagal lulus
  saat diulang sendiri (mis. `fe07ReturnErrors` 9/9).
* Putaran penuh tanpa beban (`--maxWorkers=2`): **648/649**, 89/90 suite. Satu gagal = hasil penyatuan konflik koordinator
  di `CycleCountPanel` (FIX-7 LST-06 mengharapkan galat muat riwayat di bilah galat panel; FIX-8 menaruhnya di keadaan
  daftar) → kini keduanya; `fix7DaftarServer` + `fix8StandarUi2` 29/29 → **649/649**.
* ESLint berkas yang diubah koordinator: 0 error.

### 3.6 Peramban (aplikasi uji bersama :3063, DB `kn_test_trial`)
* Diperiksa: Stok (memuat → baris, tanpa kosong palsu), bilah atas 1024 px tanpa geser samping, Stok › Roll (tampilan
  tersimpan "Tampilan: …", lencana status), panel tugas penerimaan + dialog "Minta inspeksi" (dibatalkan — data bersama
  tidak diubah).
* **Belum diperiksa di peramban:** lencana "Dicadangkan makloon" FIX-9 (butuh skrip migrasi → tidak dijalankan ke DB
  bersama), aplikasi HP akun gudang 360/390 px sesudah FIX-8, halaman server baru FIX-7 di layar. Ketiganya tertutup uji
  Jest/pytest, bukan pengamatan layar.

## 4. Yang menunggu pemilik
1. **Push** `main` ke GitHub lalu deploy ke VPS (`deploy/backup.sh` → `deploy/update.sh`).
2. **Skrip data produksi** (urutan & perintah di [panduan](PANDUAN-SKRIP-DATA-PRODUKSI.md)): FIX-1 tandai uji & gedung
   bersama, FIX-2 tahan inspeksi, FIX-3a, FIX-3b (wajib sebelum reader gate nyata), FIX-6 retur masuk stok, FIX-9 kunci
   makloon. Semua dry-run bawaan; produksi wajib `--production` + backup < 24 jam.
3. **Masa simpan log** (FIX-7) — job malam `log_retention`, bawaan `ops.log_retention_mode = delete`: sesudah deploy,
   malam pertama **menghapus permanen** log teknis lama (`sys_scheduler_runs` sukses > 30 hari, gagal > 90 hari, outbox
   WhatsApp > 90 hari, klaim digest > 30 hari; di uji ±36.600 dari ±73.000 baris). Jejak bisnis (audit, jurnal, mutasi,
   roll) dilindungi. Bila ingin melihat dulu: set `ops.log_retention_mode = dry_run` di Pengaturan sebelum malam pertama.
4. **Finance:** jurnal retur beli manual sebelum ditagih (PPN), angka hutang PO tutup kurang (FIX-6 §sisa); 4 retur
   beli tolak-QC tanpa pilihan penyelesaian di data acuan (`PRET-00037/49/69/70`).
5. **Mockup Pusat Tugas Gudang** — 9 butir untuk dinilai: [mockup](../mockup/README.md).

## 5. Sisa (paket berikut)
FIX-10 tabel transisi PA/SPK/opname + satu penulis status roll (SSOT-1); Pusat Tugas Gudang terpadu (setelah mockup
dinilai); UI-50 di luar gudang (POS `PosStartGate` "Belum ada pelanggan" saat memuat — risiko pelanggan ganda, Produk &
Varian, Antar Entitas, Meja Admin Sample); `StatusPill` lama di 47 berkas non-gudang; `TaskTypeBadge`; ±10 daftar
tanpa halaman server; retensi notifikasi/ekspor/log AI; `rebuild_balance` per lot.

## 6. Tambahan: FIX-10 (digabung sesudah §1–§5)

| Paket | Isi | Laporan | Gabung |
|---|---|---|---|
| FIX-10 | Satu penulis status roll `services/roll_state.py` (19 status, daftar-izin + CAS + `status_history` ≤ 30 entri + saldo dibangun ulang; **74 titik tulis di 21 berkas dipindah**, sisa 0), tabel transisi PA (`putaway_state`), SPK inspeksi/QC (`inspection_state`), sesi opname (`cycle_count_state`); `allocated` dibuang dari daftar status roll; enum registry = kode; guardrail INV-ROLL-02 `verify_roll_status_writer` (baseline 0) | [FIX-10](FIX-10-TRANSISI-ROLL.md) | `f1e7c73` |

**Transisi ilegal yang ditutup (perilaku yang terlihat):** roll di Surat Jalan (`in_transit_sales`) tidak lagi bisa
"dilepas" ke `available`; pecah cutloss atas roll yang dipesan/terkomit/ditahan ditolak dengan pesan (dulu reservasinya
hilang diam-diam); 14 penulis tanpa CAS kini CAS — balapan yang dulu menimpa diam-diam menjadi 409/dilewati; respons API
roll membawa `status_history`; status `wip` berlabel "WIP (Proses)". Tanpa migrasi data.

**Integrasi koordinator:** `4d74a28` — migrasi FIX-2 merekam `status_history` (kini ditulis `roll_state`) agar `--undo`
memulihkan roll persis (`test_fix7_data_scripts::test_migrate_fix2_inspection_hold_undo_exact` merah sesudah gabung →
hijau).

**Verifikasi ulang `main` (`4d74a28`) vs kode produksi `cd6963a`:**
* Uji lama 83 berkas: **118 gagal / 474 lulus / 21 error — daftar gagal IDENTIK** dengan `cd6963a` (tidak ada yang gagal
  karena kode baru). `iter117` 18/18, `iter118` 8/8, gate V2 54/36.
* Uji baru per berkas (DB dipulihkan tiap berkas): semua lulus, termasuk FIX-10 26/26 dan FIX-7 skrip data 7/7 (sesudah
  `4d74a28`).
* Guardrail: `verify_roll_status_writer` PASS (baru), `ui_standard` PASS, `scope_guard` HIJAU, `page_tabs` PASS,
  `ref_unlink` 3 = dasar, `atomic_claim` 6 = dasar.
* Jest penuh: **653/653** (§6.1).

### 6.1 Jest penuh sesudah FIX-10
Tanpa beban lain (`--maxWorkers=2`): **653/653**, 91/91 suite.

**Catatan lingkungan:** backend uji bersama `kn-uji-backend` (DB `kn_test_trial`) masih menjalankan kode sesudah FIX-6
(tidak di-restart sesudah FIX-7…10). Bila kontainer itu ter-restart, kode terbaru termuat — termasuk job malam
`log_retention` (bawaan `delete`) yang akan menghapus log teknis lama di DB uji bersama.
