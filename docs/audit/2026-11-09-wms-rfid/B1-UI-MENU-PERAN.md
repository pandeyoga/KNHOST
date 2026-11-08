# B1 — Peta menu, fitur & UI/UX WMS-RFID per peran (desktop & HP) + sensus elemen UI

- **Tanggal:** 9 Nov 2026 (WIB) · **Paket:** B1 audit WMS-RFID · **Sifat:** AUDIT (tanpa ubah kode aplikasi, tanpa simpan data, tanpa ubah setelan).
- **Basis kode:** `main@5f1e36e` (branch worktree audit di-*fast-forward* ke `main` supaya nomor baris = kode yang dijalankan
  stack uji). Semua rujukan `berkas:baris` di bawah = commit itu.
- **Aplikasi:** stack bersama `kn-uji` — http://localhost:3063 (FE) / :8063 (BE), DB `kn_test_trial`.
- **Lampiran:** [`B1-MATRIKS-CAKUPAN.md`](B1-MATRIKS-CAKUPAN.md) (menu/tab × peran × desktop/HP) · skrip
  `scripts/audit/b1_*.py` (sensus statis, matriks menu dari kode, kerangka halaman, guardrail).
- **Melanjutkan:** audit UI tahap 2 (`docs/uat/2026-10-21/hasil/UAT24-AUDIT-UI-2.md`, 243 butir, 13 pola). Temuan yang
  sudah dibereskan di sana tidak diulang kecuali muncul lagi (ditandai "muncul lagi").

> **Keterbatasan penting (dibaca dulu).** Status setiap temuan ditulis apa adanya:
> **terverifikasi** = direproduksi di peramban pada stack uji; **kandidat** = terbukti dari kode HEAD (statis) tetapi
> belum direproduksi di UI; **terukur statis** = angka sensus/guardrail. Stack sempat mati 05:35–06:18 WIB (Docker macet);
> semua bukti peramban diambil sesudah pulih (§0). Ringkasan jumlah di §8.

---

## 0. Metode & riwayat pelaksanaan

1. **Daftar menu dari kode, bukan ingatan.** `scripts/audit/b1_nav_matrix.py` meniru `roleCanSee` + `buildNavGroups` +
   `hubTabsForRole` (`frontend/src/config/roles.js:380-391`, `navigationConfig.js:22-24,70-73,130-170`) atas
   `navStructure.js`, `hubTabs.js`, `ROLE_NAV` → matriks menu × 13 peran. Aplikasi HP per peran dari
   `features/mobile/MobileAppSwitch.jsx:46-56`. Yang tidak bisa ditiru statis: `accessBlocks` (izin server per akun).
2. **Sensus statis** (sub-agen, hasil diverifikasi ulang): `b1_style_census.py`, `b1_screen_matrix.py`,
   `b1_run_guardrails.py`, ditambah `b1_skeleton.py` (kerangka halaman) dan `b1_matrix_report.py` (sel matriks). Keluaran
   mentah di folder scratchpad audit (tidak di-commit).
3. **Peramban bawaan** (satu-satunya pemakai): (a) **probe API hanya-GET** dari halaman — login per akun demo lewat
   `fetch(credentials:'omit')` sehingga token disimpan di memori halaman saja dan cookie sesi peramban tidak tersentuh,
   lalu `GET /wms/tasks`, `/outbound/tasks`, `/wms/my-location-scope`, `/warehouses`, `/goods-receipts`, `/rfid/*`,
   `/inventory/status-board`; (b) **UI** — logout/login lewat layar login aplikasi (akun demo), layar desktop 1024 px dan
   HP **390 × 844** (`resize_window`), ukur elemen (`getBoundingClientRect`/`getComputedStyle`), buka kartu/pop-up lalu
   tutup **tanpa menyimpan** (tidak ada tombol Terima/Ambil/Potong/Setujui yang ditekan). Satu-satunya perubahan keadaan
   = pilihan PT aktif di HP Admin Gudang (preferensi tampilan `localStorage`, bukan data/setelan). Di akhir: login kembali
   sebagai admin, PT Sukacita, ukuran desktop.
4. **Riwayat stack:** ≈05:35–06:18 WIB **Docker Desktop macet** (engine HTTP 500, semua port `000`); stack tidak
   di-restart oleh B1 — koordinator memulihkannya ±06:18. Seluruh pemeriksaan peramban di bawah dilakukan **sesudah**
   pemulihan (06:19–06:37 WIB); tidak ada galat jaringan masa jeda yang dicatat sebagai temuan.

### 0.1 Log verifikasi peramban (06:19–06:37 WIB, DB `kn_test_trial`)

| # | Akun / ukuran | Yang diperiksa | Hasil terukur (ringkas) | Temuan |
|---|---|---|---|---|
| V1 | API 16 akun | profil login | site dipetakan hanya untuk 3 akun `warehouse` (Jakarta `site_54bed…`, Soreang `site_fd9f…`, Rancamalang `site_c0c8…`); 13 akun lain `location_site_ids=[]`. `warehouse.soreang` = 1 PT (Kanda), `warehouse.rancamalang` = 3 PT, `wh.admin` 2 PT, `whadmin` 3 PT | UI-02, UI-03 |
| V2 | API `/wms/my-location-scope` | cakupan lokasi | setelan **ON**; warehouse Jakarta → `WH-JKT`; Soreang → `SRG-01`; Rancamalang → 5 gudang RCM; Admin Gudang/manajer/admin `supervisor · semua lokasi`; Admin Sales `restricted=false` (tanpa batas, bukan supervisor); sopir/QC/sales **403** | UI-02 |
| V3 | API `/wms/tasks` (PT Sukacita) | campuran gudang | admin, manager, wh.admin, salesadmin: **131 tugas terbuka di 5 gudang** — Jakarta 73, Rancamalang Transit 3, Rancamalang Woven 1, **TEST_WH B 20329F 16, TEST_WH B 420C35 38** (54 = 41 % di gudang uji). warehouse Jakarta: 73 (hanya Jakarta). Rancamalang (PT bawaan CST): **2** tugas; pada PT Sukacita **4** tugas lain di gedung yang sama; mode "Semua" 6 | UI-01, UI-03, UI-05 |
| V4 | API `/warehouses` | pemilih gudang | admin/sales/warehouse Jakarta: 12 gudang termasuk **6 `TEST_WH …`**; Soreang: 6 (5 RCM + SRG-01) — gudang di luar site tetap muncul di pemilih | UI-05 |
| V5 | HP 390 `warehouse.soreang` | aplikasi gudang | app bar "Kanda Fabric · Gudang" (tanpa lokasi); **tanpa** lencana cakupan; tab bawah 78 × 56 px; lonceng **36 × 36**; Masuk 2 tugas "**qty 0 kg**"; kartu terbuka = isian "Hitung fisik" 234 × 54 + **Terima 71 × 54**; Keluar: isian "Hitung ambil (kg)" + **Ambil 64 × 54 — tanpa isian pindai roll**; sub-tab Pindai/Belum Tag/Daftar Awal **37 px**; Belum Tag "Lebih dari 500 … 500 pertama dimuat" | UI-01, UI-11, UI-24, UI-43 |
| V6 | HP 390 `driver` | aplikasi sopir | `MobileWarehouseApp` (Masuk/Keluar/Sample/Pindai/Lainnya); Masuk, Keluar, Pindai menampilkan **"Permission ditolak: wms.view"** mentah + "Coba lagi"; app bar "**Kanda Fabric** · Sopir" padahal PT bawaan sopir Sukacita | UI-23, UI-39 |
| V7 | HP 390 `wh.admin` | aplikasi gudang | login mendarat di **Kanda Fabric** (PT akun sebelumnya); setelah pindah ke Sukacita: Masuk **87 terbuka** = Jakarta 30 · Rancamalang 3 · TEST_WH B 20329F 16 · TEST_WH B 420C35 38; status Menunggu Barang 70 / Menunggu QC 13 / **Ditolak QC 4** — semua pil warna sama `rgba(255,149,0,.1)`; Keluar 40 (Jakarta 39, Rancamalang 1) | UI-01, UI-05, UI-08, UI-39 |
| V8 | desktop `wh.admin` | menu & Meja Gudang | sidebar: Beranda, Meja Gudang, Meja Saya, Tanya KN, Retur, Kualitas, Pembelian, R&D, Gudang & Logistik (8, termasuk RFID), Akuntansi & Pajak, Kas & Aset, Analitik, Pusat Export, Pusat Dokumen, Pengaturan › Gudang & Mutu — **tanpa Perangkat**. Meja Gudang: 187 "perlu ditindak", baris `TEST/SO-2bea9e Uji KEB-PDPT`; **tanpa saring gudang**; 81 % teks < 12 px | UI-02, UI-05, UI-21 |
| V9 | desktop `manager` | menu RFID | Gudang & Logistik 7 menu, **tanpa RFID**; tautan `?view=cs-rfid-gate` **dialihkan diam-diam** ke Dasbor Manajer | UI-20 |
| V10 | desktop/HP `qc` | beranda & HP | desktop & HP mendarat di **SPK Inspeksi**; HP = layar desktop responsif (lebar dokumen 390 = layar), **81 dari 106 tombol < 44 px**, tanpa tab aplikasi HP | UI-19, UI-37 |
| V11 | HP 390 `sales` | Lainnya › Stok & ATP | catatan "Angka utama = total grup (semua PT)"; kartu pertama **9.083,79 kg (16 px)** lalu "PT saya (Sukacita): **0 kg** — stok ada di PT lain" (11 px); chip "Stok Habis **128**" | UI-06 |
| V12 | desktop admin (PT Sukacita) | 12 layar gudang | lihat tabel ukur §0.2 | UI-04, 05, 06, 14, 16, 18, 21, 22, 26, 29, 38, 40–42 |
| V13 | desktop admin | pengalih badan usaha | opsi: Semua Entitas · Sukacita · Kanda · Cipta Sandang · **PT Uji Provisioning F77512 / F10873 / F5880** | UI-05 |

### 0.2 Ukuran terukur layar desktop (admin, PT Sukacita, 1024 px)

| Layar | Angka tampil (token numerik) | Tombol (semua < 44 px?) | Teks < 12 px | Cari | Ekspor | Catatan terukur |
|---|---:|---|---:|---|---|---|
| Operasi Gudang › Stok | 182 | 52 (semua; 17–40 px) | 94 % | ya | **tidak** (ekspor hanya di sub-tab Roll & Mutasi) | 2 baris tab bertumpuk; papan "Antrean ACC · SEMUA GUDANG"; pemilih gudang 16 opsi termasuk 6 `TEST_WH`; judul kolom 10 px; transfer uji "M-3 test IC transfer", "iter_112 auto-elim test" di papan |
| Barang Keluar | 343 | 132 | 82 % | ya | tidak | "114 tugas" pada chip **Semua** termasuk status **Terkirim**; tugas Terkirim berlabel "TERTAHAN BAYAR · CBD" (KSC/SO-00520) |
| Cutting | 93 | 57 (semua) | 61 % | ya | tidak | 3 paket sample; **Antrean Potong Roll (34)** — tidak ada di HP |
| Barang Masuk (GRN) | 76 | 31 | 55 % | ya (placeholder "Nomor GRN / SJ / mitra") | tidak | 15 kartu — **tanpa gudang**; "0 halaman" pada kartu ditutup |
| Status Stok & ATP | 158 | 11 (semua) | 36 % | ya | tidak | 411 produk; halaman 1 dimulai produk bernilai **0 0 0 0 0**; Total ATP **60.996,16 kg** · 108 m · 1.314.153,95 yd; Stok Habis 292 |
| Stok Multi-Bucket | 78 | 32 | 72 % | ya | tidak | KPI "Total Tersedia" = KPI "ATP" = **61.071,16 kg** (berbeda 75 kg dari ATP tab sebelah) |
| Lokasi Rak | 24 | 51 (semua) | 51 % | – | tidak | gudang bawaan "Rancamalang · Gudang Knitting" (bukan lokasi pengguna); KPI "Belum Ditempatkan **2108 roll**" vs tab "Penempatan Rak (**14**)"; tab "Antrean Potong" (ganda dengan Cutting); produk `TEST_iter317_…` di antrean |
| Monitor Gerbang | 11 | 15 (semua) | 22 % | ya | tidak | subjudul "Simulasikan pembacaan tag di gerbang"; form "Simulasi Pembacaan Gate" di layar operasional; gate "UJI-CELUP gate-out" |
| Tag RFID | 15 | 60 (semua) | 16 % | ya | tidak | "Roll Belum Ber-tag 5.000+ · Belum Ber-tag (500 dari 5.000+)" |
| Antrean QC Kedatangan | 16 | 16 | 42 % | ya | tidak | 13 baris — **semua** tombolnya "Putuskan di SPK" |
| Eskalasi Gudang | 1 | 3 | 14 % | **tidak** | tidak | 0 tugas |
| Pengaturan › Perangkat › RFID | – | – | – | – | – | kartu perangkat → tombol "Integrasi reader U300" → pop-up kesehatan, riwayat lintasan, unggah profil (dibuka & ditutup Esc) |

Angka "token numerik" = jumlah angka yang tampil di `main` pada halaman pertama (regex angka berdiri sendiri), dipakai
sebagai ukuran kepadatan angka, bukan jumlah metrik bisnis.

---

## 1. Jawaban atas 8 keluhan pemilik (ringkas)

| # | Keluhan pemilik | Terbukti? | Temuan |
|---|---|---|---|
| 1 | Tugas masuk/keluar tercampur semua entitas & gudang, tanpa filter/sadar pengguna | **Ya, sebagian besar** — HP tanpa saring gudang/PT & tanpa penanda cakupan; pembatasan lokasi hanya peran `warehouse` dan bergantung setelan global; Admin Gudang/manajer/sales melihat semua gudang PT aktif; kartu GRN tidak menyebut gudang. Arah sebaliknya juga ada: tugas berpagar PT aktif padahal gedung dipakai bersama semua PT (K-GDG-07). **Terukur:** Admin Gudang di HP melihat 87 tugas Masuk dari 4 gudang, 54 di antaranya di gudang `TEST_WH`; petugas Rancamalang hanya melihat 2 dari 6 tugas gedungnya; login berikutnya di HP yang sama mewarisi PT pengguna sebelumnya. | UI-01, UI-02, UI-03, UI-04, UI-05, UI-39, UI-43 |
| 2 | Terlalu banyak angka stok; ingin angka lokal (lokasi/PT) + global, rincian saat klik | **Ya** — Multi-Bucket 10 kolom bucket, Status Stok 5 kolom + 4 KPI + rincian PT, HP angka utama = total grup; **dimensi lokasi pengguna hanya ada di kartu POS** (pola yang diminta pemilik sudah ada di sana), tidak di layar stok gudang. Stok tampil di ≥ 8 layar berbeda dan **angkanya berbeda**: ATP 60.996,16 kg (Status Stok) vs 61.071,16 kg (Multi-Bucket); "Stok Habis" 292 (desktop) vs 128 (HP sales). | UI-06, UI-07, UI-40 |
| 3 | Jenis tugas tidak dibedakan (keluar untuk SO vs Sampel; tugas potong) | **Ya** — HP "Keluar" tanpa penanda jenis/sumber & isinya beda dengan desktop; "Barang Keluar" hanya SO, keluar lain tersebar di 6 menu; potong roll SO (34 antrean di desktop) tidak ada di HP; daftar Barang Keluar "Semua" mencampur tugas terkirim. | UI-08, UI-09, UI-10, UI-41 |
| 4 | Alur QC, GRN, OCR — UI/UX & elemen tidak konsisten | **Ya** — kerangka halaman, kontrol daftar, tombol & chip berbeda per layar; "barang ditahan QC" punya 3 pintu; Antrean QC tidak bisa memutus (13/13 baris "Putuskan di SPK"). | UI-16, UI-17, UI-18, UI-19, UI-37, UI-38 |
| 5 | RFID juga | **Ya** — operasional gate (kunci, sesi dokumen, riwayat lintasan) ada di Pengaturan › Perangkat yang tidak bisa dibuka Admin Gudang; manajer tanpa menu RFID (tautan langsung dialihkan diam-diam); Monitor Gerbang dibingkai sebagai simulator; kerangka berbeda; batas server senyap. | UI-12, UI-14, UI-20, UI-21, UI-22 |
| 6 | Pindai masih satu per satu, bukan per dokumen | **Ya** — pindai HP satu kode per kali, Ambil HP bahkan tanpa pindai roll (ketik qty); mode per dokumen hanya ada di desktop (paket Cutting, sesi dokumen gate di Pengaturan). | UI-10, UI-11, UI-12, UI-13 |
| 7 | Melihat roll yang jumlahnya sangat banyak sulit | **Ya** — batas server senyap (GRN 100, tag 1.000, roll belum tag 500, lokasi 1.000, antrean gate 100, Barang Keluar 200), cari hanya atas potongan, hampir tanpa urut kolom (Status Stok membuka halaman 1 dengan produk bernilai 0). | UI-14, UI-15, UI-42 |
| 8 | Elemen UI tidak standar (form, ukuran tombol, cari/saring/ekspor) | **Ya, terukur** — 76 % ukuran huruf arbitrer < 12 px, 723 warna hex langsung, 794 tombol bergaya sendiri, 341 tombol baku dikecilkan, ekspor bersama hanya 5 layar cakupan, 70 tabel mentah vs 6 ResponsiveTable, target sentuh HP < 44 px (lonceng 36, sub-tab 37, SPK di HP 81/106 tombol); 0 tombol ekspor di 12 layar terukur. | UI-24, UI-26 … UI-33 |

---

## 2. Temuan

Format: **Area/layar** · **Peran** · **Ukuran** · **Klasifikasi** · **Keparahan** · **Bukti** · **Aturan** · **Dampak** ·
**Rekomendasi** · **Status**. Keparahan: P0 data salah/kebocoran/hilang · P1 alur terhambat/menyesatkan · P2 tidak
konsisten/merepotkan · P3 kosmetik.

### A. Cakupan data, lokasi & badan usaha (keluhan 1)

### UI-01 — Daftar tugas HP gudang tanpa saring gudang/PT dan tanpa penanda cakupan
- **Area/layar:** Aplikasi HP gudang — tab Masuk, Keluar, Sample (`MobileWarehouseApp`).
- **Peran:** warehouse (3 akun site), warehouse_admin, (driver — lihat UI-23). **Ukuran:** HP 390.
- **Klasifikasi:** hambatan UX (cakupan tak terlihat) · **Keparahan:** P1.
- **Bukti:**
  - Daftar dimuat dari `GET /wms/tasks` tanpa parameter gudang/lokasi, lalu hanya disaring jenis di klien
    (`frontend/src/features/mobile/MobileWarehouseApp.jsx:49`). Kotak cari baru muncul bila > 5 tugas (`:74-77`); tidak ada
    pemilih gudang, site, atau PT; tidak ada urut.
  - Kartu tugas menampilkan nama gudang + qty + no. SO/PO, **tidak** menampilkan PT pemilik (`:96-98`).
  - Indikator cakupan lokasi (`LocationScopeBadge`, "Lokasi tugas: …/Supervisor · semua lokasi/Pembatasan lokasi
    nonaktif") hanya dipasang di desktop `LocationPutawayView.jsx:119` dan `ScannerTaskPanel.jsx:242` — **tidak** di HP.
  - Server: `backend/routers/wms.py:27-42` → `resolve_list_scope` (PT aktif) + pagar lini; pembatasan lokasi hanya lewat
    `location_scope.warehouse_ids_for` (UI-02). Semua tugas aktif dikembalikan sampai 2.000 (`wms.py:38-39`).
- **Aturan:** keputusan pemilik "layar yang dibuka dari aplikasi HP layak 390 px"; KN_08 §Target Persona (operator gudang:
  *Speed + Clarity*); KN_14 §10 (Multi-Entity: query transaksi wajib filter entitas dari konteks — konteks harus terlihat).
- **Dampak:** petugas tidak tahu apakah daftarnya "gudang saya" atau "semua gudang"; Admin Gudang (supervisor, tanpa
  batas lokasi) melihat tugas semua gudang PT aktif bercampur dalam satu daftar.
- **Rekomendasi:** baris cakupan tetap di atas daftar ("Lokasi: Soreang · PT: Sukacita" / "Semua lokasi — supervisor"),
  pemilih gudang (bawaan = lokasi akun), chip PT bila akun multi-PT, dan PT di kartu.
- **Status:** **terverifikasi** (V5, V7 §0.1): HP Soreang & Admin Gudang tanpa lencana cakupan; Admin Gudang (PT Sukacita) melihat **87 tugas Masuk** dari 4 gudang (Jakarta 30, Rancamalang 3, 2 gudang `TEST_WH` 54) dalam satu daftar.

### UI-02 — Pembatasan lokasi hanya untuk peran `warehouse` & bergantung setelan global; peran lain tanpa "lokasi saya"
- **Area/layar:** semua daftar gudang (tugas, GRN, roll, transfer, putaway) — desktop & HP.
- **Peran:** warehouse_admin, manager, admin, sales, sales_admin, finance (tak terbatas); warehouse (terbatas bila setelan
  aktif). **Ukuran:** keduanya.
- **Klasifikasi:** butuh keputusan · **Keparahan:** P1.
- **Bukti:** `backend/services/location_scope.py:18-19` (`SCOPED_ROLES = {"warehouse"}`, `SUPERVISOR_ROLES = {warehouse_admin,
  manager, admin}`), `:47-56` (peran lain → `None` = tanpa batas; setelan mati → `None`). Setelan
  `wms.location_scope_enforced` bawaan **False** (`backend/config_catalog_ops.py:575`); hanya data acuan P01 yang
  menyalakannya (`backend/scripts/seed_p01_kn.py:41-43`). Koleksi yang ikut dibatasi hanya 8
  (`location_scope.py:20-28`: tugas, pengiriman, roll, mutasi, saldo, GRN, transfer, putaway) — retur pelanggan, order
  makloon, perbaikan, retur supplier, opname, RFID, meja kerja **tidak**. Bukti awal koordinator: 3 dari 22 akun
  dipetakan site.
- **Aturan:** K-GDG-01/05/08 (pengaturan per gedung) — operasi harian per gedung; KN_14 §10.
- **Dampak:** Admin Gudang Soreang (bila ada) melihat Rancamalang/Jakarta tanpa sadar; daftar & angka tidak bisa
  "angka lokal" (keluhan 2).
- **Rekomendasi:** pisahkan "boleh lihat semua" (supervisor) dari "bawaan tampilan": semua peran operasional punya
  **lokasi kerja bawaan** (site akun) sebagai saringan awal yang bisa dilepas; setelan per site, bukan satu sakelar global.
  **Butuh keputusan pemilik** (lihat §8 K-B1-01).
- **Status:** **terverifikasi** (V1, V2, V8): hanya 3 akun `warehouse` punya site; Admin Gudang/manajer/admin = "supervisor · semua lokasi"; Admin Sales `restricted=false`; Meja Gudang tanpa saring gudang.

### UI-03 — Tugas gudang berpagar PT aktif padahal gedung dipakai bersama semua PT
- **Area/layar:** HP gudang (semua tab), desktop Barang Keluar/Cutting/Barang Masuk.
- **Peran:** warehouse (akun 1 PT), warehouse_admin. **Ukuran:** keduanya.
- **Klasifikasi:** butuh keputusan · **Keparahan:** P1.
- **Bukti:** `wms.py:31` dan `outbound_picking.py:43-44` memakai `resolve_list_scope(…, ctx)` = PT **aktif**
  (`backend/entity_scope.py` `resolve_list_scope`); peran `warehouse` "1 badan usaha" (`frontend/src/config/roles.js:64-71`).
  Keputusan pemilik **K-GDG-07**: semua gedung dipakai bersama semua PT; roll tetap milik PT masing-masing
  (`docs/rfid/KEPUTUSAN_GATE_RFID.md:143`). Data acuan akun: `warehouse@` = KSC saja, `warehouse.soreang@` = **KANDA
  saja**, `warehouse.rancamalang@` = 3 PT (`backend/scripts/seed_demo_lengkap_kn.py:184-186`) — petugas Soreang tidak
  bisa melihat tugas PT lain di gedung Soreang sama sekali, petugas Rancamalang harus berganti PT.
- **Dampak:** petugas Soreang yang berdiri di PT A tidak melihat tugas PT B di gedung yang sama — harus ganti PT di menu
  "Lainnya" (HP) satu per satu; sebaliknya akun multi-PT di mode "Semua" melihat semua gudang semua PT. Kedua arah membuat
  daftar tugas tidak sama dengan pekerjaan fisik di gedung.
- **Rekomendasi:** untuk tugas fisik (terima, simpan, ambil, potong, kirim) cakupan = **lokasi/gedung**, PT sebagai label
  & saringan; aksi tetap dicek per PT di server. **Butuh keputusan pemilik** (§8 K-B1-02).
- **Status:** **terverifikasi** (V3): Rancamalang di PT bawaan (CST) 2 tugas, di PT Sukacita 4 tugas lain di gedung yang sama, mode "Semua" 6.

### UI-04 — Papan antrean ACC di Operasi Gudang selalu "semua gudang"
- **Area/layar:** Operasi Gudang › Stok, Transfer & Opname (papan `WaitingBoardsStrip`). **Peran:** admin, manager,
  warehouse_admin, warehouse. **Ukuran:** desktop.
- **Klasifikasi:** inkonsistensi · **Keparahan:** P2.
- **Bukti:** `frontend/src/features/wms/OperationsView.jsx:86-88` — catatan tetap
  `scopeNote="Antrean ACC · semua gudang (filter gudang di bawah hanya untuk daftar stok)"`: pengakuan bahwa papan dan
  daftar di bawahnya memakai cakupan berbeda.
- **Dampak:** dua angka berdampingan dengan dasar berbeda di satu layar (pola "angka sama berbeda antar layar" audit tahap 2).
- **Rekomendasi:** papan ikut saringan gudang/lokasi halaman (dan lokasi bawaan UI-02).
- **Status:** **terverifikasi** (§0.2): papan bertajuk "ANTREAN ACC · SEMUA GUDANG (FILTER GUDANG DI BAWAH HANYA UNTUK DAFTAR STOK)".

### UI-05 — Data uji tampil di pilihan pengguna (PT "Uji Provisioning", gudang `TEST_WH…`)
- **Area/layar:** pengalih badan usaha (semua layar), daftar gudang. **Peran:** admin (PT uji); semua pemilih gudang
  (TEST_WH). **Ukuran:** keduanya.
- **Klasifikasi:** bug data · **Keparahan:** P2 · **silang ke B3a**.
- **Bukti:** respons login admin yang tersimpan di peramban (`localStorage.kn_user.entity_context.entities`) memuat 6
  badan usaha aktif, 3 di antaranya data uji: "PT Uji Provisioning F77512" (`ent_9e9eedcd5450`, dibuat 23 Okt),
  "PT Uji Provisioning F10873" (`ent_0d23afab6ff0`, 24 Okt), "PT Uji Provisioning F5880" (`ent_8fdf6f2ea207`, 25 Okt) —
  ketiganya `status: active`, `location_status: unverified`. Gudang `TEST_WH …` (bukti awal koordinator) belum
  direproduksi di UI.
- **Dampak:** admin/manajer bisa memilih PT uji; angka "Semua entitas" ikut menjumlah data uji.
- **Rekomendasi:** arsipkan PT & gudang uji (izin pemilik — tindakan data), atau saring `TEST_`/"Uji Provisioning" dari
  pemilih. Uji regresi yang membuat entitas harus membersihkan diri.
- **Status:** **terverifikasi** (V3, V4, V7, V8, V13, §0.2): 3 PT uji di pengalih desktop; 6 gudang `TEST_WH` di pemilih gudang; 54 tugas terbuka di gudang uji; transfer "M-3 test IC transfer"/"iter_112 auto-elim test" di papan ACC; produk `TEST_iter…` di antrean penempatan rak; `TEST/SO-…` "Uji KEB-PDPT" di Meja Gudang; gate "UJI-CELUP".

### B. Angka stok (keluhan 2)

### UI-06 — Terlalu banyak angka stok per layar, tanpa "angka lokal" pengguna
- **Area/layar:** Stok & ATP › Status Stok & ATP, › Stok Multi-Bucket; Operasi Gudang › Stok; HP Stok & ATP (sales/MD).
- **Peran:** admin, manager, warehouse_admin, warehouse, sales, sales_admin, md. **Ukuran:** keduanya.
- **Klasifikasi:** hambatan UX + butuh keputusan · **Keparahan:** P1 · **silang ke B3a** (definisi angka).
- **Bukti:**
  - Status Stok & ATP: 4 KPI (Produk, Total Barang Masuk, Total ATP, Peluang Antar-PT) + 5 kolom angka per produk (Stok
    Fisik, Tersedia, Dipesan, Barang Masuk, ATP) + kolom Entitas + rincian per PT/gudang saat dibuka
    (`frontend/src/features/inventory/InventoryStatusBoard.jsx:131-136, 173-181`; judul kolom 10 px `:173`). Rumus ditulis
    sebagai paragraf di atas tabel (`:167-170`).
  - Stok Multi-Bucket: **10 bucket** (Tersedia, Dipesan, Ditahan, WIP, Di Makloon, Dialokasikan, Dalam Perjalanan,
    Karantina, Blokir, Rusak) `StockBucketsView.jsx:31-40`; tabel rincian 7 kolom dengan judul kolom **9 px**
    (`:208-212`).
  - HP: angka utama kartu = **total grup semua PT**, "PT saya" baris kecil 11 px (`sales/mobile/MobileStockAtp.jsx:60,
    96, 107-109`); desktop untuk sales juga memakai total grup (`InventoryStatusBoard.jsx:26-27` `pv()`).
  - Layar stok gudang **tidak** punya dimensi lokasi/site pengguna sebagai angka utama (saringan gudang ada di
    Multi-Bucket/Operasi Gudang, tetapi tidak bawaan ke lokasi akun). **Pola yang diminta pemilik sudah ada di satu
    tempat:** kartu produk POS menonjolkan "Di {lokasi}: x · n roll · PT lain di lokasi ini y", lalu "PT: …", lalu "Grup: n
    roll / x tersedia" (`frontend/src/features/pos/PosProductCard.jsx:103-120`, UAT 24 Okt P8) — tetapi Status Stok & ATP,
    Multi-Bucket, Operasi Gudang › Stok, HP Stok & ATP dan HP gudang tidak memakainya.
- **Aturan:** permintaan pemilik (angka lokal + global, rincian saat klik); KN_08 §Core Principles 2 *Progressive
  Disclosure*; keputusan pemilik "stok tersedia berbasis roll".
- **Dampak:** pengguna harus menafsirkan 5–10 angka per produk; angka utama di HP (grup) tidak sama dengan yang bisa ia
  jual/ambil (PT/lokasinya).
- **Rekomendasi:** satu pola kartu stok di semua layar — jadikan pola kartu POS (`PosProductCard.jsx:103-120`) komponen
  bersama: **angka utama = Tersedia di lokasi & PT saya** (+ jumlah roll), angka kedua = Tersedia grup; ATP/Dipesan/Barang
  Masuk/bucket lain di rincian (klik). Multi-Bucket tetap untuk analis, bukan layar
  harian. **Butuh keputusan pemilik** angka mana yang "utama" per peran (§8 K-B1-03).
- **Status:** **terverifikasi** (V11, §0.2): HP sales — 9.083,79 kg tampil besar padahal "PT saya: 0 kg"; Status Stok 158 angka di halaman 1, Multi-Bucket 78, Operasi Gudang › Stok 182.

### UI-07 — Stok yang sama tampil di ≥ 8 layar dengan label & rumus berbeda
- **Area/layar:** Operasi Gudang › Stok · Stok & ATP › Status Stok & ATP · › Stok Multi-Bucket · › Lot & Silsilah ·
  Analitik › Analitik Stok · Lokasi Rak (isi bin) · HP Stok & ATP (sales) · HP "Status Stok" (MD) · katalog POS/HP & pemilih
  roll SO.
- **Peran:** semua peran gudang + sales. **Klasifikasi:** duplikasi · **Keparahan:** P2 · **silang ke B3a**.
- **Bukti:** peta duplikasi §6 (pekerjaan "Berapa stok produk X?"); HP sales `MobileStockAtp.jsx:20` memakai
  `/inventory/status-board`, Operasi Gudang › Stok memakai endpoint & KPI sendiri (`InventoryStockView.jsx`), Multi-Bucket
  memakai bucket sendiri (`StockBucketsView.jsx:31-40`).
- **Rekomendasi:** satu komponen "kartu stok" + satu sumber angka (B3a), layar lain menautkan.
- **Status:** kandidat (statis) untuk jumlah layar; perbedaan angka antar layar **terverifikasi** → UI-40.

### C. Jenis tugas (keluhan 3)

### UI-08 — HP "Keluar" tidak membedakan jenis tugas dan isinya berbeda dengan desktop "Barang Keluar"
- **Area/layar:** HP gudang › Keluar vs desktop Operasi Gudang › Barang Keluar.
- **Peran:** warehouse, warehouse_admin. **Ukuran:** HP & desktop.
- **Klasifikasi:** inkonsistensi · **Keparahan:** P1.
- **Bukti:**
  - HP: `/wms/tasks` → semua `flow_type=outbound` kecuali `sample_cut`, **termasuk** status `scheduled` (ditahan) — hanya
    `completed/shipped/cancelled/done/dispatched` yang dibuang (`MobileWarehouseApp.jsx:49`); pagar lini berlaku
    (`wms.py:34-35`).
  - Desktop: `/outbound/tasks` → hanya `source_type=sales_order`, status ≠ `scheduled`, maks 200, **tanpa** pagar lini
    (`backend/routers/outbound_picking.py:36-46`), plus info tahan bayar CBD/DP (`:55-66`) yang **tidak** ada di HP.
  - Desktop punya chip jenis "Semua / Pesanan (SO) / Sample" dan pemilih gudang (`OutboundScanInterface.jsx:296-303`),
    plus lencana SAMPEL 9 px (`:333`); HP tidak punya penanda jenis selain teks " · SAMPEL" untuk `sample_cut`
    (`MobileWarehouseApp.jsx:98`).
  - Pil status HP: semua status selain `escalated` berwarna oranye `pill-warning` (`:97`) — "Menunggu", "Ambil", "Sudah
    diambil", "Sudah dikemas" tidak dibedakan warna.
- **Dampak:** jumlah & isi daftar "barang keluar" berbeda antara HP dan desktop untuk orang yang sama; HP menampilkan tugas
  yang ditahan bayar tanpa alasan tahan.
- **Rekomendasi:** satu endpoint daftar tugas keluar untuk keduanya; HP menampilkan chip jenis (SO / Sample / Potong /
  Transfer …), alasan tahan, dan warna status per tahap.
- **Status:** **terverifikasi sebagian** (V7): pil semua status sama warna (termasuk "Ditolak QC"); HP tanpa chip jenis. Pada data saat ini jumlah HP = desktop untuk Jakarta (39 + 4 = 43) karena tidak ada tugas `scheduled` — perbedaan aturan daftar tetap kandidat statis.

### UI-09 — "Barang Keluar" hanya untuk SO; pekerjaan keluar lain tersebar di 6 menu
- **Area/layar:** Operasi Gudang › Barang Keluar · Operasi Gudang › Stok, Transfer & Opname › Transfer · Pembelian ›
  Pesanan Pembelian › Order Makloon (kirim bahan) · Operasi Gudang › Perbaikan (kirim) · Retur › Retur ke Supplier ·
  Retur › Retur Antar-PT / Akuntansi › Antar Entitas (kirim antar-PT) · Operasi Gudang › Cutting (paket sample).
- **Peran:** warehouse, warehouse_admin. **Klasifikasi:** fitur belum ada / butuh keputusan · **Keparahan:** P1.
- **Bukti:** tugas WMS hanya lahir dari PO (inbound) dan SO (outbound) — `purchase_orders.py:153,170`,
  `outbound_picking_extra.py:117`, `sales_orders_extra.py:886`; dokumen keluar lain punya layar sendiri (matriks
  `scripts/audit/b1_matrix_report.py`). Desktop Barang Keluar menyaring `source_type: sales_order`
  (`outbound_picking.py:36`). Keputusan **K-GDG-02**: gate OUT memvalidasi SJ, transfer, makloon, perbaikan per trip →
  gate memperlakukannya sebagai satu jenis pekerjaan "keluar", layar tidak.
- **Dampak:** petugas gudang harus tahu menu mana untuk tiap jenis keluar; tidak ada satu antrean "yang harus keluar hari
  ini di gudang saya".
- **Rekomendasi:** satu antrean "Keluar" per lokasi dengan chip jenis & tautan ke dokumen asal (pola pick list per
  dokumen). **Butuh keputusan** (§8 K-B1-04).
- **Status:** kandidat (statis).

### UI-10 — Potong: desktop per paket pesanan + potong roll SO; HP per baris tanpa potong roll SO
- **Area/layar:** desktop Operasi Gudang › Cutting vs HP gudang › Sample.
- **Peran:** warehouse, warehouse_admin. **Klasifikasi:** inkonsistensi / fitur belum ada · **Keparahan:** P1.
- **Bukti:** desktop mengelompokkan per pesanan × gudang dan punya "Potong semua (n) · roll saran"
  (`frontend/src/features/wms/CuttingOpsView.jsx:60-86, 130-135`) serta bagian "Potong roll untuk pesanan (SO)"
  (`:169-176`, `PendingCutsPanel`). HP "Sample" menampilkan satu kartu per baris tugas `sample_cut` dan potong satu-satu
  (`MobileWarehouseApp.jsx:287`, `MobileTaskActions.jsx:105-141`); potong roll SO **tidak ada** di HP. Label tab
  "Cutting" (desktop) vs "Sample" (HP) untuk pekerjaan yang sama.
- **Dampak:** pesanan sample 9 baris = 9 kartu & 9 potong di HP (desktop 1 klik); potong roll SO hanya bisa di desktop.
- **Rekomendasi:** HP memakai paket per pesanan yang sama (satu "Potong semua", baris gagal → manual), tambah bagian potong
  roll SO, samakan nama tab ("Potong").
- **Status:** **terverifikasi** (§0.2): desktop Cutting = 3 paket "Potong semua" + **Antrean Potong Roll (34)**; HP Sample hanya kartu per baris, tanpa antrean potong roll SO.

### D. Pindai per dokumen (keluhan 6)

### UI-11 — Ambil di HP tanpa pindai roll (ketik qty); desktop wajib pindai roll
- **Area/layar:** HP gudang › Keluar (aksi "Ambil") vs desktop Barang Keluar.
- **Peran:** warehouse, warehouse_admin. **Klasifikasi:** butuh keputusan (aturan beda per perangkat) · **Keparahan:** P1.
- **Bukti:** HP mengirim `scan-pick` hanya dengan `actual_qty` (`MobileTaskActions.jsx:82-94`). Desktop menolak tanpa roll:
  "Scan roll terlebih dahulu — jumlah diambil mengikuti panjang roll, tidak diketik manual."
  (`OutboundScanInterface.jsx:128-131`). Server sengaja membolehkan: "Tanpa scan roll (alur cepat HP/legacy) tetap
  diizinkan … Mewajibkan scan per roll = keputusan kebijakan gudang (belum ada)." (`backend/routers/outbound_picking.py:120-123`).
- **Aturan:** prinsip RFID/roll-as-SSOT (stok tersedia berbasis roll — keputusan pemilik); KN_08 *Error Prevention >
  Error Handling*.
- **Dampak:** di HP roll yang diambil tidak tercatat saat ambil; roll dipilih server saat berangkat — roll fisik yang
  diangkut bisa beda dengan yang dicatat.
- **Rekomendasi:** HP = pindai roll (kamera/RFID) seperti desktop; ketik qty hanya untuk jalur darurat beralasan.
  **Butuh keputusan** (§8 K-B1-05).
- **Status:** **terverifikasi** (V5): kartu Keluar HP = isian "Hitung ambil (kg)" + tombol Ambil, tanpa isian/kamera pindai roll.

### UI-12 — Pindai HP satu kode per kali; mode per dokumen hanya di desktop/Pengaturan
- **Area/layar:** HP gudang › Pindai; RFID gate (sesi dokumen).
- **Peran:** warehouse, warehouse_admin. **Klasifikasi:** fitur belum ada · **Keparahan:** P1.
- **Bukti:** panel Pindai HP = satu isian + tombol "Pindai" → `GET /rfid/lookup` per kode (`MobileWarehouseApp.jsx:106-200`);
  tidak ada daftar "dokumen aktif → roll yang sudah/ belum terpindai". Satu-satunya layar HP yang menerima **banyak kode
  sekaligus** (antrean EPC) adalah Daftar Awal (`MobileRegistration.jsx:1-3`) — pola itu belum dipakai untuk terima,
  ambil, putaway, atau transfer. Progres per dokumen (K-RFID-10, "x/y roll lewat ·
  sisa n") ada di `U300DocSession.jsx` yang hanya dirender di pop-up perangkat **Pengaturan › Integrasi & Sistem ›
  Perangkat** (`RfidDevicesView.jsx:214` → `U300Operations.jsx:1-6,16`; tab `settings-devices` hanya admin/manajer,
  `hubTabs.js:303`).
- **Aturan:** K-RFID-10 (sesi dokumen bertahap), K-GDG-02 (handheld = cadangan gate & alat utama di gedung tanpa gate).
- **Dampak:** petugas handheld tidak bisa "pindai satu SJ/putaway sampai lengkap"; di gedung tanpa gate (Jakarta) tidak ada
  mode dokumen sama sekali.
- **Rekomendasi:** mode "Pindai per dokumen" di HP: pilih/ pindai dokumen → daftar roll target dengan centang otomatis
  per pindai (QR/RFID massal), sisa & salah-dokumen ditandai; pakai mesin sesi yang sama dengan gate.
- **Status:** **terverifikasi** (V5, §0.2): Pindai HP = satu isian + satu tombol; pop-up "Integrasi reader U300" (kesehatan, riwayat lintasan) hanya dari Pengaturan › Perangkat.

### UI-13 — HP "Masuk" saat mode GRN: kartu hanya tautan yang memuat ulang aplikasi
- **Area/layar:** HP gudang › Masuk. **Peran:** warehouse, warehouse_admin. **Klasifikasi:** hambatan UX · **Keparahan:** P2.
- **Bukti:** bila PT memakai GRN, kartu tugas berisi `<a href="?view=goods-receipts">` "Penerimaan memakai Kedatangan
  Barang — buka layar Kedatangan …" (`MobileTaskActions.jsx:52-57`) — tautan `href` = muat ulang halaman penuh, bukan
  `openFull` seperti kartu "Kedatangan Barang" di atas daftar (`MobileWarehouseApp.jsx:245-254, 285`). Mode lama: terima =
  ketik qty per tugas (`MobileTaskActions.jsx:59-66`), tanpa pindai label.
- **Dampak:** daftar Masuk berisi kartu yang tidak bisa dikerjakan di tempat; pindah layar memuat ulang aplikasi (status
  HP hilang, tombol kembali ke aplikasi HP tidak dijamin).
- **Rekomendasi:** dalam mode GRN, tab Masuk = daftar GRN terbuka per lokasi (hitung/pindai di tempat); tautan memakai
  `openFull`.
- **Status:** kandidat (statis).

### E. Roll sangat banyak (keluhan 7)

### UI-14 — Batas server senyap memotong daftar; cari & halaman hanya atas potongan
- **Area/layar & bukti:**
  - Barang Masuk (GRN): `limit=100` (`backend/routers/goods_receipts.py:47-48`), layar tanpa halaman.
  - Barang Keluar: `to_list(200)` (`outbound_picking.py:46`).
  - Tag RFID 1.000 (`backend/services/rfid_service.py:59-66`), roll belum bertag 500 (`:70-71`), Lokasi RFID 1.000
    (`:372-374`); HP "Belum Tag" menyebut batas 500 (`MobileWarehouseApp.jsx:219-225`) — layar desktop tidak.
  - Antrean periksa gate `limit: 100` (`frontend/src/features/rfid/GateReviewQueue.jsx:32`).
- **Peran:** semua peran gudang. **Klasifikasi:** bug (data tak terlihat) · **Keparahan:** P1 · **silang ke B3b**.
- **Dampak:** dengan volume 6.000 roll/hari (keputusan RFID terbaru) daftar berhenti diam-diam; pencarian tidak menemukan
  data di luar potongan.
- **Rekomendasi:** halaman/cari di server (pola `PaginationBar` + parameter `q`) untuk semua daftar roll/tag/dokumen.
- **Status:** **terverifikasi sebagian**: `/rfid/untagged-rolls` mengembalikan `count: 500` = panjang potongan (total sebenarnya tidak diketahui klien); `/inventory/rolls?limit=5000` penuh 5.000 → data melebihi batas. GRN (15) & Barang Keluar (117) belum mencapai batas di DB uji.

### UI-15 — Hampir tidak ada urut kolom di daftar gudang
- **Bukti:** dari 30 layar cakupan, urut oleh pengguna hanya di Pengiriman (`logistics/DeliveryTable.jsx:27-45`) dan meja kerja
  (`DeskQueueCard` `:52`); `ResponsiveTable` tidak punya urut (sensus `screen_matrix.csv`).
- **Di peramban:** Status Stok & ATP (411 produk, 292 habis) membuka halaman 1 dengan baris bernilai **0 · 0 · 0 · 0 · 0**
  (urutan SKU), tanpa cara mengurut per Tersedia/ATP.
- **Klasifikasi:** fitur belum ada · **Keparahan:** P2 · **silang ke B3b**. **Status:** kandidat (statis); contoh Status Stok
  **terverifikasi**.

### F. QC, GRN, OCR (keluhan 4)

### UI-16 — Kerangka halaman berbeda antar layar satu alur (GRN → QC → SPK → putaway)
- **Bukti (hitungan `scripts/audit/b1_skeleton.py`):**

  | Layar | kerangka `section-card/head` | kicker+h2 | tab | cari | saring | halaman | ekspor | tombol oranye sendiri | huruf < 12 px |
  |---|---|---|---|---|---|---|---|---|---|
  | Barang Masuk (GRN) `GoodsReceiptsView.jsx` | ya | ya | PageTabs | SearchBox | FilterChips | – | – | – | 6 |
  | GRN buat (wizard/OCR) `GrnCreateWizard.jsx` | **tidak** | – | – | – | – | – | – | – | 6 |
  | Antrean QC `QCInspection.jsx` | ya | h2 tanpa kicker | – | useListSearch | – | klien | – | – | 14 |
  | SPK Inspeksi `InspectionsView.jsx` | ya | ya | – | ya | FilterChips | PaginationBar | ya | – | 8 |
  | Barang Keluar `OutboundScanInterface.jsx` | **tidak** | – | chip sendiri | input mentah | chip oranye `#FF9500` | – | – | 3 | **37** |
  | Cutting `CuttingOpsView.jsx` | ya | ya | – | input mentah | chip oranye `#FF9500` | – | – | 2 | 9 |
  | Lokasi Rak (putaway) `LocationPutawayView.jsx` | ya (tanpa head) | h3 | PageTabs | – | – | – | – | – | 2 |
  | Monitor Gerbang `RfidGateMonitorView.jsx` | **tidak** | – | PageTabs | – | – | – | – | – | 9 |
- **Klasifikasi:** inkonsistensi · **Keparahan:** P2.
- **Aturan:** KN_08 §Core Principles 3 *Consistent Mental Models*; §Page Structure; §Quality Checklist.
- **Rekomendasi:** satu kerangka halaman daftar (judul+kicker, bilah cari/saring baku `ListControls`/`FilterChips`, pager +
  ekspor `PaginationBar`) untuk semua layar alur penerimaan & pengeluaran.
- **Status:** **terverifikasi** (§0.2): teks < 12 px 55 % (GRN) · 42 % (Antrean QC) · 82 % (Barang Keluar) · 61 % (Cutting) · 22 % (Monitor Gerbang); ekspor tidak ada di ke-12 layar terukur.

### UI-17 — Antrean QC Kedatangan: tanpa saring/ekspor, id mentah, huruf kecil
- **Bukti:** `frontend/src/features/wms/QCInspection.jsx:211-212` (cadangan `product_id`/`warehouse_id` mentah); tanpa
  saring status/gudang & tanpa ekspor (`screen_matrix.csv` baris qc-inspection); 14 pemakaian huruf < 12 px.
- **Peran:** qc, warehouse, warehouse_admin, admin, manager. **Klasifikasi:** inkonsistensi · **Keparahan:** P2.
- **Status:** **terverifikasi** (§0.2): 13 baris, tanpa saring & ekspor; setiap baris hanya "Putuskan di SPK".

### UI-18 — "Barang ditahan QC" punya tiga pintu
- **Bukti:** papan "Barang ditahan QC" di atas Operasi Gudang (tautan ke SPK, `OperationsView.jsx:80-97`), Kualitas › Antrean QC
  Kedatangan (`AppViewRouter.jsx:363-364`), Kualitas › SPK Inspeksi saringan "Hanya yang DITAHAN" (`preset {hold:true}`).
- **Klasifikasi:** duplikasi · **Keparahan:** P2. **Rekomendasi:** satu antrean "Ditahan QC" (Kualitas), dua lainnya = angka +
  tautan. **Status:** **terverifikasi**: papan Operasi Gudang "Barang ditahan QC (8)", SPK Inspeksi "BARANG DITAHAN 8", Antrean QC 13 baris yang semuanya "Putuskan di SPK".

### UI-19 — Beranda peran QC = SPK Inspeksi, bukan Antrean QC Kedatangan
- **Bukti:** `frontend/src/config/navMeta.js:238-239` (`qc`/`md_quality` → `inspections`). Peran QC punya tab "Antrean QC
  Kedatangan" (`roles.js:332`) yang merupakan pekerjaan hariannya. Keputusan K-GDG-04: MD Quality tidak perlu inspeksi.
- **Klasifikasi:** butuh keputusan · **Keparahan:** P3. **Status:** **terverifikasi** (V10).

### G. RFID (keluhan 5)

### UI-20 — Manajer tidak punya menu RFID
- **Bukti:** `navStructure.js:289` (`rfid-hub` roles `admin, warehouse`) dan `hubTabs.js:226-230` — manajer (supervisor
  lokasi `location_scope.py:19`, pemegang `wms.approve`) tidak melihat Lokasi RFID/Tag RFID/Monitor Gerbang, padahal teks
  layar menyebut "Admin Gudang / Manajer" sebagai pembuka kunci gate (`U300Operations.jsx:32`).
- **Klasifikasi:** butuh keputusan · **Keparahan:** P2. **Status:** **terverifikasi** (V9): menu RFID tidak ada; tautan langsung dialihkan ke Dasbor Manajer tanpa pesan.

### UI-21 — Operasional gate tersimpan di Pengaturan › Perangkat (tidak terjangkau Admin Gudang); "buka kunci" di dua tempat
- **Bukti:** `U300Operations.jsx:1-6` — kesehatan reader, kunci gate, **dokumen gate & sesi bertahap**, riwayat lintasan,
  parameter, simulator — dibuka dari pop-up kartu perangkat di `RfidDevicesView.jsx:214`; layar itu = tab
  `settings-devices` (admin, manager — `hubTabs.js:303`). Admin Gudang (pemegang `wms.approve`, `permissions_config.py`
  warehouse_admin) tidak bisa membukanya. Pembukaan kunci juga ada di Monitor Gerbang (`GateLiveVerdict.jsx:82-83`,
  `GateReviewDetail.jsx:28-29,69`) → dua pintu untuk satu tindakan.
- **Klasifikasi:** duplikasi + hambatan UX · **Keparahan:** P1.
- **Rekomendasi:** Pengaturan › Perangkat hanya konfigurasi; semua yang operasional (kesehatan, kunci, sesi dokumen,
  riwayat) di RFID › Monitor Gerbang untuk Admin Gudang.
- **Status:** **terverifikasi** (V8, §0.2): sidebar Admin Gudang tanpa Perangkat; pop-up U300 dibuka dari kartu perangkat di Pengaturan.

### UI-22 — Layar RFID tanpa kerangka baku & sangat padat huruf kecil
- **Bukti:** `b1_skeleton.py` — Monitor Gerbang, Tag RFID, Lokasi RFID, Perangkat RFID: 0 `section-card`/`section-head`;
  Perangkat RFID 19 huruf < 12 px; area `features/rfid` 49 % tombol buatan sendiri (35/71); istilah Inggris
  `u300Labels.js:74` (audit i18n). **Klasifikasi:** inkonsistensi · **Keparahan:** P2. **Status:** **terverifikasi sebagian** (§0.2): Monitor Gerbang berjudul "Simulasikan pembacaan tag di gerbang" dengan form "Simulasi Pembacaan Gate" di layar operasional; kerangka & huruf = statis.

### H. Aplikasi HP

### UI-23 — Sopir mendapat aplikasi HP gudang yang seluruh tabnya butuh izin gudang
- **Area/layar:** aplikasi HP peran `driver`. **Ukuran:** HP.
- **Klasifikasi:** bug · **Keparahan:** P1.
- **Bukti:** `frontend/src/features/mobile/MobileAppSwitch.jsx:49` (`warehouse, warehouse_admin, driver` →
  `MobileWarehouseApp`); izin sopir hanya `logistics: view, update` (+ field_visibility) — `backend/permissions_config.py:547-550`;
  semua tab memanggil `/wms/tasks` (izin `wms.view`, `wms.py:29`) atau `/rfid/lookup`. Aplikasi tidak punya tab
  Pengiriman, padahal beranda desktop sopir = Pengiriman (`navMeta.js:231`).
- **Dampak:** sopir yang membuka aplikasi di HP mendarat di layar galat; pekerjaannya (foto muat/POD) hanya lewat
  "Tampilan desktop".
- **Rekomendasi:** aplikasi HP sopir = daftar pengiriman hari ini + foto muat/POD (pakai komponen Logistik).
- **Status:** **terverifikasi** (V6): ketiga tab menampilkan "Permission ditolak: wms.view" mentah (pola tahap 2 "galat izin dipamerkan mentah" **muncul lagi**).

### UI-24 — Target sentuh < 44 px di aplikasi HP (muncul lagi sebagian)
- **Bukti (ukuran dari CSS):** tombol lonceng app bar 36 × 36 (`frontend/src/styles/mobile.css:27-28`); `.primary-button`
  padding 8 × 14 px huruf 13 px ≈ 35 px tinggi (`styles/components.css:67-79`), `.secondary-button` 7 × 12 px
  (`:82-94`), `.icon-button` 32 × 32 (`:111-116`); satu-satunya jaminan 44 px hanya tombol di `.modal-actions`
  (`mobile.css:143`). Tombol aksi HP gudang "Terima"/"Ambil" = `primary-button px-4` (`MobileTaskActions.jsx:64, 93`),
  isian lot/dye `p-2` (`:70-71`), "Potong roll ini" `py-2` (`:137`). Sensus: 149 elemen HP/GRN kandidat < 44 px
  (`touch_targets.csv`).
- **Ukur di peramban (390 × 844, V5/V10):** tab bawah **78 × 56** (lolos); "Terima" **71 × 54** & "Ambil" **64 × 54**
  (lolos — tinggi ikut isian di sebelahnya, jadi kandidat statis untuk dua tombol ini **gugur**); tombol "Pindai" 330 × 44
  (pas); **lonceng 36 × 36**, sub-tab Pindai/Belum Tag/Daftar Awal **37 px** (gagal); layar SPK Inspeksi yang dibuka QC
  di HP: **81 dari 106 tombol < 44 px** (gagal).
- **Aturan:** KN_08 §Mobile Adaptations "Touch target minimum: 44x44px"; WCAG 2.5.5 (44 × 44 CSS px, AAA).
- **Klasifikasi:** inkonsistensi · **Keparahan:** P2. **Status:** **terverifikasi** (ukur), dengan koreksi di atas.

### UI-25 — Label id mentah sebagai cadangan teks (gudang/RFID/HP)
- **Bukti (contoh):** `MobileWarehouseApp.jsx:96,190,231` (`product_name || product_id`), `:117,231` (`warehouse_id`),
  `QCInspection.jsx:211-212`, `wms/inventory/LedgerTable.jsx:46,49`, `InventoryStockView.jsx:137,141` (ikut ke CSV),
  `wms/inbound/InboundTaskPanel.jsx:205` ("Roll ID: {roll_id}"), `inventory/registration/RegistrationDetail.jsx:146`
  (`owner_entity_id` — guardrail `verify_entity_label` MERAH), `rfid/GatePassageHistory.jsx:36` (`device_id`); ±53 tempat
  tampil ke pengguna (`raw_id_labels.csv`). Di peramban: papan "Barang ditahan QC" Operasi Gudang menampilkan **kode gudang
  `WH-JKT`** sebagai judul kedua dua SPK (KSC/INS-00017, -00071) di tempat nama produk. **Klasifikasi:** inkonsistensi ·
  **Keparahan:** P3 (P2 untuk RegistrationDetail karena guardrail merah). **Status:** kandidat (statis); papan QC
  **terverifikasi**.

### I. Elemen UI tidak standar (keluhan 8)

### UI-26 — Skala huruf: 76 % ukuran arbitrer di bawah 12 px
- **Bukti (sensus `main@5f1e36e`):** `text-[Npx]` 8.903 pemakaian / 21 nilai; hanya 1.532 (17 %) pada skala KN_08 (12, 14,
  18, 20, 24); **6.779 (76 %) < 12 px**: 11 px (2.584), 10,5 (1.407), 10 (1.294), 11,5 (994), 9,5 (305), 9 (177), 8,5 (18).
  Area gudang 1.212/1.612 (75 %) < 12 px. Contoh: judul kolom 9 px Multi-Bucket (`StockBucketsView.jsx:208`), 10 px
  Status Stok (`InventoryStatusBoard.jsx:187`), Barang Keluar 37 pemakaian < 12 px.
- **Aturan:** KN_08 §Type Scale (small 12 px, body 14 px); §Mobile "Larger font sizes for scanning UI (16px+)".
- **Klasifikasi:** inkonsistensi · **Keparahan:** P2. **Status:** **terverifikasi** (§0.2): porsi teks < 12 px per layar 14–94 %.

### UI-27 — Warna ditulis hex langsung (bukan token)
- **Bukti:** 723 nilai hex berbeda / 16.887 pemakaian di JS/JSX (650 bila hanya `bg|text|border-[#…]`); terbanyak `#6B6B73`
  (2.642), `#0058CC` (1.510), `#8E8E93` (1.400), `#EFF0F2` (1.206). Area gudang 252 nilai / 2.803 pemakaian.
- **Aturan:** KN_08 §Color Palette (token `--primary`, `--muted-foreground`, …). **Klasifikasi:** inkonsistensi ·
  **Keparahan:** P3. **Status:** terukur statis.

### UI-28 — Tombol: gaya sendiri, tinggi beragam, tombol baku dikecilkan
- **Bukti:** dari 2.805 `<button` di `frontend/src`: 1.774 berkelas baku (`primary/secondary/danger/icon/ghost/link-button`
  `styles/components.css:53-913`; `.btn-*` `styles/purchasing.css:9-38`), **794 hanya Tailwind sendiri**, 104 tanpa class;
  **341 tombol baku dikecilkan** `!py-1` (171), `!py-1.5`, `!py-0.5`, `!h-8`, `!h-7`. Tinggi tombol buatan sendiri: tanpa
  padding 247, `py-1` 159, `py-1.5` 110, `py-2` 86, `py-0.5` 63 … Huruf tombol `text-[11px]` 153, `[10.5px]` 75, `[10px]` 35.
  shadcn `<Button>` 21 pemakaian (19 di `features/tanya`), **0** di cakupan B1 — KN_08 mewajibkan shadcn. Area `wms` 60 %
  tombol buatan sendiri (169/283), `rfid` 49 %. Chip saring oranye `bg-[#FF9500]` buatan sendiri di Barang Keluar
  (`OutboundScanInterface.jsx:282-288, 296-299`) & Cutting (`CuttingOpsView.jsx:108-111`) vs `FilterChips` baku di GRN/SPK.
- **Aturan:** KN_08 §Shadcn/UI "WAJIB", §Button Variants. **Klasifikasi:** inkonsistensi · **Keparahan:** P2.
- **Rekomendasi:** putuskan standar de facto (kelas CSS `primary-button` dkk. sudah 1.774 pemakaian) lalu perbarui KN_08;
  larang `!py-*`/`!h-*` pada tombol baku (guardrail ratchet), sediakan varian `sm`/`touch` resmi.
- **Status:** terukur statis.

### UI-29 — Tab buatan sendiri & tab-dalam-tab di Operasi Gudang
- **Bukti:** `OperationsView.jsx:100-115` (tab garis-bawah buatan sendiri Stok/Transfer/Stock Opname/Kesehatan) di bawah bilah
  tab hub "Stok, Transfer & Opname | Barang Masuk | …" → dua tingkat tab berbeda gaya. Juga `IntercoView.jsx:320`,
  `ColorLibraryView.jsx:127`. Guardrail `verify_page_tabs.py` lulus karena polanya (`:36-39`) tidak mengenali tab
  garis-bawah — **titik buta guardrail**. Kualitas sudah dikeluarkan dari tab-dalam-tab (hubTabs.js:147-149) tetapi Operasi
  Gudang belum.
- **Aturan:** KN_14 §5.3 (L3 = tab/panel); keputusan IA 23 Okt (tab-dalam-tab dihapus). **Klasifikasi:** inkonsistensi ·
  **Keparahan:** P2. **Status:** **terverifikasi** (§0.2): dua bilah tab bertumpuk di Operasi Gudang.

### UI-30 — Ekspor tidak merata; CSV logistik beda format
- **Bukti:** ekspor bersama (`utils/csvExport.js` lewat `PaginationBar`) hanya di 5 layar cakupan (Operasi Gudang › Stok,
  SPK Inspeksi, Lot & Silsilah, Retur Pelanggan, Retur Supplier). Tanpa ekspor: Barang Masuk, Barang Keluar, Cutting,
  Perbaikan, Antrean QC, Status Stok & ATP, Multi-Bucket, Lokasi Rak, Data Gudang, RFID (3 tab), Eskalasi, HP. Logistik
  membuat CSV sendiri berpemisah koma tanpa BOM (`logistics/LogisticsView.jsx:37-38`, `logistics/HistoryPanel.jsx:43-44`) — berbeda
  dari format ekspor bersama (`;` + BOM); guardrail `verify_list_export` hanya memeriksa `PaginationBar`.
- **Klasifikasi:** inkonsistensi / fitur belum ada · **Keparahan:** P2 · **silang ke B3b**. **Status:** **terverifikasi** (§0.2): 0 tombol ekspor di 12 layar terukur (Operasi Gudang › Stok punya ekspor hanya di sub-tab Roll/Mutasi).

### UI-31 — Tabel mentah vs ResponsiveTable
- **Bukti:** cakupan B1: 70 `<table` mentah vs 6 `ResponsiveTable` (seluruh src 197 vs 25) — mis. Status Stok
  (`InventoryStatusBoard.jsx:183`), Multi-Bucket (`StockBucketsView.jsx:207,251`), Retur Antar-PT
  (`IntercoReturnsPanel:43`), Master Grade Mutu (`:88`). **Dampak:** tabel melebar/terpotong di 390 px (pola tahap 2
  "tabel desktop terpotong di HP"). **Klasifikasi:** inkonsistensi · **Keparahan:** P2. **Status:** kandidat (statis).

### UI-32 — Istilah Inggris masih lolos (gate i18n MERAH)
- **Bukti:** `scripts/audit_i18n_id.py --strict` exit 1, 104 temuan di 63 berkas (64 FE, 40 BE); area gudang:
  `StockAnalyticsView:137`, `LogisticsView:31,122`, `rfid/u300Labels.js:74`, `PutawayOrdersPanel:262`, `GrnLineRow:175`,
  `GrnPackingChecklist:12`, `TransferReceiptPanel:98`. **Aturan:** KN_32 (gate harus 0). **Klasifikasi:** inkonsistensi ·
  **Keparahan:** P2. **Status:** terukur statis (guardrail).

### UI-33 — Guardrail entity_label MERAH (opname awal menampilkan id PT)
- **Bukti:** `verify_entity_label` gagal: `frontend/src/features/inventory/registration/RegistrationDetail.jsx:146` `{g.owner_entity_id}`
  (layar pendaftaran awal gedung, PREP-B). **Klasifikasi:** bug · **Keparahan:** P2. **Status:** terukur statis (guardrail).

### J. Navigasi & menu

### UI-34 — Petugas gudang melihat menu di luar pekerjaannya
- **Bukti (matriks dari kode):** peran `warehouse` melihat Akuntansi & Pajak › Antar Entitas (Grup)
  (`navStructure.js:323,332`), Pembelian › Hutang Pemasok › Kontrabon (`:222`, `hubTabs.js:86`), Kas & Aset › Kendaraan
  (`:345`), R&D (2 tab), Pembelian › Pengadaan (PR/RFQ), Kontrak Mitra & Barang Supplier. Total 17 entri sidebar menurut kode.
- **Klasifikasi:** butuh keputusan · **Keparahan:** P3 (KN_13 anti-pattern "Menu Redundan"). **Status:** kandidat (statis).

### UI-35 — Daftar peran di tab yang tidak pernah berlaku
- **Bukti:** tab Master Grade Mutu menyebut `md, md_quality, qc` (`hubTabs.js:261`) tetapi grup Pengaturan hanya
  `admin, manager, warehouse_admin` (`navStructure.js:407`) dan ROLE_NAV ketiganya tidak menambah `settings-hub` → tab tidak
  pernah tampil bagi mereka. **Klasifikasi:** inkonsistensi (kode) · **Keparahan:** P3. **Status:** kandidat (statis).

### UI-36 — Putaway, transfer, opname, makloon & retur tidak ada di aplikasi HP gudang
- **Area/layar:** aplikasi HP gudang (tab Masuk/Keluar/Sample/Pindai/Lainnya).
- **Peran:** warehouse, warehouse_admin. **Klasifikasi:** fitur belum ada · **Keparahan:** P1.
- **Bukti:** tab HP hanya Masuk (PO lama/kartu GRN), Keluar (SO), Sample, Pindai (Pindai · Belum Tag · Daftar Awal)
  (`MobileWarehouseApp.jsx:284-289`, `:261-271`). Penempatan rak (putaway, K-GDG-10 "draf otomatis … tiba bertahap per
  trip") hanya di desktop Lokasi Rak (`LocationPutawayView.jsx:134-155`); transfer kirim/terima, stock opname, kirim/terima
  makloon, perbaikan, terima retur — tidak ada tab HP (grep `putaway` di `features/mobile` = 0).
- **Aturan:** keputusan pemilik "form input di HP LENGKAP sama dengan desktop"; K-GDG-02 (handheld = alat utama di gedung
  tanpa gate).
- **Dampak:** pekerjaan lantai gudang selain terima PO/ambil SO harus lewat "Tampilan desktop" di HP (layar desktop di 390 px).
- **Rekomendasi:** tab "Tugas" HP berbasis antrean per lokasi (UI-09) yang memuat putaway, transfer, opname, makloon,
  perbaikan & retur — aksi pindai yang sama.
- **Status:** **terverifikasi** (V5): tab HP = Masuk · Keluar · Sample · Pindai (Pindai/Belum Tag/Daftar Awal) · Lainnya.

### UI-37 — Aplikasi HP QC hanya membuka SPK Inspeksi; Antrean QC Kedatangan tidak terjangkau dari HP
- **Area/layar:** aplikasi HP `MobileOpsApp` untuk peran qc / md_quality. **Ukuran:** HP.
- **Klasifikasi:** fitur belum ada · **Keparahan:** P2.
- **Bukti:** tab "QC" berisi satu tombol "Meja QC · SPK inspeksi & random check scan" → `openFull("quality-hub",
  "inspections")` (`frontend/src/features/mobile/MobileOpsApp.jsx:197, 213`); tidak ada pintu ke `qc-inspection` (Antrean QC
  Kedatangan) yang menjadi pekerjaan QC saat barang tiba (`roles.js:330-333`). Tombol satu-satunya itu `primary-button`
  (≈ 35 px, UI-24).
- **Status:** **terverifikasi dengan koreksi** (V10): QC di HP tidak pernah melihat tab "QC" `MobileOpsApp` — beranda `inspections` termasuk *responsive workspace* (`App.js:251`) sehingga HP langsung membuka SPK Inspeksi versi desktop (lebar 390 OK, **81/106 tombol < 44 px**, tanpa tab aplikasi HP & tanpa tombol kembali ke aplikasi HP).

### UI-38 — Kartu Barang Masuk (GRN) tidak menyebut gudang tujuan; daftar tanpa saring gudang
- **Area/layar:** Operasi Gudang › Barang Masuk (juga dibuka penuh dari HP). **Peran:** warehouse, warehouse_admin, admin,
  manager, finance. **Ukuran:** keduanya.
- **Klasifikasi:** hambatan UX · **Keparahan:** P2.
- **Bukti:** kartu menampilkan nomor, status, mitra, SJ, baris, halaman, pemblokir, waktu & pembuat — **tanpa gudang**
  (`frontend/src/features/wms/grn/GoodsReceiptsView.jsx:102-113`); bilah saring = cari + status saja (`:91-99`); daftar
  maks 100 tanpa halaman (UI-14).
- **Dampak:** petugas multi-gudang/Admin Gudang tidak bisa melihat kedatangan "gudang saya" (keluhan 1).
- **Status:** **terverifikasi** (§0.2): 15 kartu, tidak satu pun menyebut gudang.

### K. Temuan baru dari peramban (06:19–06:37 WIB)

### UI-39 — PT aktif akun sebelumnya terbawa setelah logout → login di perangkat yang sama
- **Area/layar:** login (desktop & HP) — penting untuk HP gudang yang dipakai bergantian. **Peran:** semua akun multi-PT
  (sopir, Admin Gudang, manajer, finance, MD, QC, petugas Rancamalang …).
- **Klasifikasi:** bug · **Keparahan:** P1 (data PT lain tampil & aksi tercatat di PT lain tanpa disadari — keluhan 1).
- **Bukti:** urutan uji di satu peramban: `warehouse.soreang` (PT Kanda) logout → `driver` login → app bar
  "**Kanda Fabric** · Sopir" (PT bawaan sopir = Sukacita) → logout → `wh.admin` login → "**Kanda Fabric** · Admin Gudang"
  (PT bawaan = Sukacita). Kode: logout hanya menghapus `kn_token` & `kn_user` (`frontend/src/hooks/useAppActions.js:118-124`);
  login memakai `localStorage.kn_entity` sisa sesi lalu dan hanya membersihkannya bila **tidak** termasuk PT akun baru
  (`:97-105`).
- **Dampak:** di HP bersama, petugas berikutnya bekerja di PT orang sebelumnya; daftar tugas (UI-01/03) berbeda tanpa ia tahu.
- **Rekomendasi:** logout menghapus `kn_entity`; login selalu mulai dari PT bawaan akun (atau pilihan terakhir **milik akun
  itu**, disimpan per id pengguna).
- **Status:** **terverifikasi** (V6, V7).

### UI-40 — Angka ATP & "Stok Habis" berbeda antar tab/aplikasi untuk konteks yang sama
- **Area/layar:** Stok & ATP › Status Stok & ATP vs › Stok Multi-Bucket (desktop admin, PT Sukacita); HP sales Stok & ATP.
- **Klasifikasi:** inkonsistensi angka · **Keparahan:** P1 · **silang ke B3a**.
- **Bukti:** Status Stok & ATP "Total ATP **60.996,16 kg** · 108 meter · 1.314.153,95 yard"; Multi-Bucket (tab sebelahnya)
  "ATP **61.071,16 kg** · 108 meter · 1.314.153,95 yard" — selisih 75 kg; Multi-Bucket juga menampilkan KPI "Total Tersedia"
  dengan angka yang **sama persis** dengan KPI "ATP". Chip "Stok Habis" = **292** (desktop, admin, PT Sukacita) vs **128** (HP,
  sales PT Sukacita, 411 produk yang sama) karena HP sales memakai total grup (`InventoryStatusBoard.jsx:26-27` `pv()`,
  `MobileStockAtp.jsx:13`).
- **Dampak:** "angka yang sama berbeda antar layar" (pola tahap 2) muncul lagi di modul stok; pengguna tidak tahu angka
  mana yang benar.
- **Rekomendasi:** satu definisi ATP & satu sumber (B3a); label chip menyebut cakupan ("Habis di PT saya" vs "Habis di grup").
- **Status:** **terverifikasi** (§0.2, V11).

### UI-41 — Barang Keluar: chip "Semua" mencampur tugas terkirim, dan tugas terkirim masih berlabel "TERTAHAN BAYAR"
- **Area/layar:** Operasi Gudang › Barang Keluar. **Peran:** admin, manager, warehouse, warehouse_admin, sales_admin.
  **Ukuran:** desktop.
- **Klasifikasi:** hambatan UX / bug label · **Keparahan:** P2.
- **Bukti:** bawaan `filterStatus = "all"` (`OutboundScanInterface.jsx:28`) → server mengembalikan semua status kecuali
  `scheduled` (`outbound_picking.py:39-40`) termasuk `dispatched`; layar: "**114 tugas**" dengan banyak kartu "Terkirim" di
  antara "Pengemasan"; kartu KSC/SO-00520 berstatus **Terkirim** menampilkan pita "TERTAHAN BAYAR · CBD".
- **Rekomendasi:** bawaan = tugas aktif; "Terkirim" di chip riwayat; pita tahan bayar hanya untuk tugas yang belum berangkat.
- **Status:** **terverifikasi** (§0.2).

### UI-42 — Lokasi Rak: gudang bawaan bukan lokasi pengguna, angka "belum ditempatkan" tidak cocok dengan antrean, antrean potong ganda
- **Area/layar:** Gudang & Logistik › Lokasi Rak. **Peran:** admin, manager, warehouse_admin, warehouse. **Ukuran:** desktop.
- **Klasifikasi:** inkonsistensi + duplikasi · **Keparahan:** P2.
- **Bukti:** admin (supervisor) mendarat di "Rancamalang · Gudang Knitting" (gudang pertama di daftar, bukan lokasi akun); KPI
  "Belum Ditempatkan **2108 roll** · 50.575,5 kg · 108 meter · 100 yard" sementara tab "Penempatan Rak (**14**)"; tab
  "**Antrean Potong**" di layar ini juga ada sebagai "Potong roll untuk pesanan (SO)" di Cutting (`CuttingOpsView.jsx:169-176`);
  antrean berisi produk uji `TEST_iter317_family_src_…`. 7 tab dalam satu layar.
- **Rekomendasi:** bawaan = lokasi akun; KPI dan antrean memakai definisi yang sama (atau label yang menjelaskan beda);
  potong roll SO hanya di satu tempat (Cutting).
- **Status:** **terverifikasi** (§0.2).

### UI-43 — Tugas barang masuk ber-qty 0 tampil di HP
- **Area/layar:** HP gudang › Masuk (Soreang). **Klasifikasi:** bug data/label · **Keparahan:** P2 · **silang ke B3a**.
- **Bukti:** dua kartu "LYFLEX ACTIVE BEIGE A / NAVY A · Menunggu Barang · Soreang · Gudang Kanda · **qty 0 kg** · KANDA/PO-00001"
  (V5). Kartu tidak menjelaskan sisa yang harus diterima; isian "Hitung fisik" tetap terbuka.
- **Rekomendasi:** tugas qty 0 tidak dibuat/ditutup otomatis, atau kartu menampilkan "dipesan x · diterima y · sisa z".
- **Status:** **terverifikasi** (data DB uji; asal data — B3a).

---

## 2b. Jumlah klik tugas umum (dari jalur kode + layar yang dikunjungi; tombol simpan tidak ditekan)

| Tugas | Desktop | HP | Catatan |
|---|---|---|---|
| Satu putaway (1 roll ke bin) | Gudang & Logistik › Lokasi Rak (2) → pilih gudang (2) → baris roll: Saran (1) → pilih bin KNSelect (2) → Tempatkan (1) ≈ **8** | **tidak ada** (UI-36) | per roll; 6.000 roll/hari × ±4 klik/roll (`location/PutawayRow.jsx:19-40`) |
| Satu ambil SO | Operasi Gudang (2) → Barang Keluar (1) → pilih tugas (1) → pindai/ketik roll + Enter (1) → Ambil (1) → Kirim (1) ≈ **7** | Keluar (1) → kartu (1) → ketik qty → Ambil (1) → Berangkatkan (1) = **4 + ketik** tanpa pindai roll (UI-11) | |
| Potong sample satu pesanan 9 baris | Cutting (3) → **Potong semua** (1) = **4** | Sample (1) → per baris: kartu (1) + Potong (1) → **19** | UI-10 |
| Satu GRN (kedatangan) | Barang Masuk (3) → Kedatangan baru (1) → mitra (2) + gudang (2) → Lanjut (1) → langkah 2 (foto/PO) → Buat (1) → hitung per baris → tutup ≈ **12 +** | kartu "Kedatangan Barang" (1) → layar GRN desktop di 390 px | `grn/GrnCreateWizard.jsx:87-129` (2 langkah) |
| Cek satu roll | Lot & Silsilah / Tag RFID / Lokasi Rak: cari (1+ketik) | Pindai (1) → ketik/kamera → Pindai (1) | 4 kotak cari roll berbeda |

---

## 3. Pola kesalahan (lintas layar)

| # | Pola | Jumlah / contoh | Temuan |
|---|---|---|---|
| 1 | **Cakupan data tidak terlihat** (gudang/site/PT): daftar tanpa penanda "lokasi/PT apa", saringan bawaan bukan lokasi pengguna | HP 3 tab, GRN (kartu tanpa gudang `GoodsReceiptsView.jsx:102-113`), Status Stok, Lokasi RFID; badge cakupan hanya di 2 layar | UI-01…04 |
| 2 | **Dua pintu/dua aturan untuk satu pekerjaan** (HP vs desktop beda endpoint/aturan) | Keluar (`/wms/tasks` vs `/outbound/tasks`), Ambil (qty vs pindai roll), Potong (per baris vs per paket), buka kunci gate (Monitor vs Perangkat), barang ditahan QC (3 pintu) | UI-08, 10, 11, 18, 21 |
| 3 | **Angka berlapis tanpa hierarki** | 10 bucket, 5 kolom + 4 KPI, rumus sebagai paragraf, angka utama HP = grup | UI-06, 07 |
| 4 | **Batas server senyap** | 6 daftar (100/200/500/1.000) tanpa pesan "terpotong" kecuali HP Belum Tag | UI-14 |
| 5 | **Huruf terlalu kecil** | 6.779 pemakaian < 12 px (76 %), judul kolom 9–10 px | UI-26 |
| 6 | **Elemen buatan sendiri di samping komponen baku** | 794 tombol, chip oranye sendiri (2 layar), tab garis-bawah sendiri (3 layar), 70 tabel mentah, 5 modal `fixed inset-0` | UI-28, 29, 31 |
| 7 | **Kontrol daftar tidak merata** (cari/saring/urut/halaman/ekspor) | ekspor 5 dari 30 layar, urut 2 dari 30, saring PT 1 dari 30 | UI-15, 30 |
| 8 | **Pekerjaan operasional terkubur di Pengaturan** | sesi dokumen & kunci gate di Perangkat; Penerimaan & OCR di Pengaturan (tautan `href` dari GRN `GoodsReceiptsView.jsx:66`) | UI-12, 21 |
| 9 | **HP tidak setara desktop untuk pekerjaan lantai gudang** | putaway, transfer, opname, makloon, retur, potong SO tidak ada; sopir salah aplikasi | UI-10, 23, 36 |
| 10 | **Id mentah sebagai cadangan teks** | ±53 tempat; guardrail entity_label merah | UI-25, 33 |
| 11 | **Tautan `href` memuat ulang aplikasi** (bukan navigasi internal) | `MobileTaskActions.jsx:54`, `GoodsReceiptsView.jsx:66` | UI-13 |
| 12 | **Data uji bercampur dengan data kerja** | 3 PT "Uji Provisioning" di pengalih; 6 gudang `TEST_WH` di pemilih; 54 dari 131 tugas terbuka PT Sukacita di gudang uji; transfer/SO/produk/gate uji di papan ACC, Meja Gudang, antrean rak, Monitor Gerbang | UI-05 |
| 13 | **Konteks sesi bocor antar pengguna** | PT aktif pengguna sebelumnya terbawa setelah logout (terulang 2×: sopir & Admin Gudang mendarat di Kanda) | UI-39 |
| 14 | **Angka sama, nilai beda** (muncul lagi dari tahap 2) | ATP 60.996,16 vs 61.071,16 kg (dua tab satu menu); Stok Habis 292 vs 128; KPI "Tersedia" = KPI "ATP"; "Belum Ditempatkan 2108" vs antrean 14 | UI-40, UI-42 |
| 15 | **Galat izin mentah / layar mati** (muncul lagi) | "Permission ditolak: wms.view" di 3 tab HP sopir; tautan RFID manajer dialihkan diam-diam | UI-20, UI-23 |

## 4. Peta duplikasi layar (per "pekerjaan")

| Pekerjaan | Layar yang menyelesaikannya (desktop) | HP | Catatan |
|---|---|---|---|
| Berapa stok produk X? | Operasi Gudang › Stok · Stok & ATP › Status Stok & ATP · › Stok Multi-Bucket · › Lot & Silsilah · Analitik › Analitik Stok · Lokasi Rak (isi bin) · POS katalog / pemilih roll SO | Sales: Stok & ATP; MD: Status Stok; Gudang: Pindai (per roll) | ≥ 8 tempat, rumus/label beda (UI-06/07, B3a) |
| Barang ditahan QC | Operasi Gudang (papan) · Kualitas › Antrean QC · Kualitas › SPK (ditahan) | – | UI-18 |
| Terima barang dari supplier | Barang Masuk › Kedatangan (GRN) · Barang Masuk › Scan Terima per PO (mode lama) | Masuk (tugas PO lama / tautan GRN) · kartu Kedatangan Barang | 2 mode hidup berdampingan (UI-13) |
| Keluarkan barang | Barang Keluar (SO) · Cutting (paket sample) · Transfer · Order Makloon · Perbaikan · Retur Supplier · Retur/Antar-PT | Keluar (SO) · Sample | UI-08/09 |
| Potong roll | Cutting › paket sample · Cutting › potong roll SO · Lokasi Rak (dulu) | Sample (per baris) | UI-10 |
| Buka kunci gate / periksa lintasan | RFID › Monitor Gerbang (`GateLiveVerdict`, Antrean periksa) · Pengaturan › Perangkat (`U300Operations`) | – | UI-21 |
| Cari roll by kode | Pindai di Barang Keluar · Lokasi Rak · Tag RFID · Lot & Silsilah | Pindai | 4 kotak cari roll berbeda perilaku |
| Pengaturan penerimaan/OCR | Pengaturan › Gudang & Mutu › Penerimaan & OCR · tautan dari Barang Masuk | – | dulu tab di Barang Masuk |

## 5. Sensus statis (angka kunci)

| Lingkup | Berkas | Huruf `text-[Npx]` (pakai/nilai) | Hex (pakai/nilai) | `<button` | baku | Tailwind sendiri | shadcn `<Button>` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `frontend/src` (main) | 1.095 | 8.903 / 21 | 16.887 / 723 | 2.805 | 1.774 | 794 | 21 |
| Area gudang (wms+inventory+inspections+rfid+mobile) | 156 | 1.612 / 18 | 2.803 / 252 | 492 | 246 | 219 | 0 |
| Cakupan layar B1 (288 berkas) | 288 | 2.792 / 20 | 5.147 / 423 | 883 | 496 | 330 | 0 |

Perbandingan dengan angka koordinator: font **sama** (8.903/21); hex 649 ≈ 650 (`bg|text|border-[#rrggbb]`) — semua konteks
= 723; "390 tombol" = grep satu-baris `<button[^>]*className="[^"]*(px-|py-)`, hasil parse tag = **794**; "1.254 kelas
baku" tidak tereproduksi (terdekat 1.265 baris berisi `(primary|secondary|danger)-button`; parse = 1.774).

**Guardrail (read-only, worktree):** lulus — custom_modals (ratchet 51 = baseline), detail_modal, error_notice (utang 6
modal), knselect_contract, list_export (16 daftar berhalaman), modal_dismiss, page_tabs (titik buta UI-29), picker_portal,
uom_vocab, role_label, view_aliases, blocking_dialogs, escape_layers, desk_targets, access_catalog_nav. **MERAH:**
entity_label (UI-33), numeric_bounds (3 HARD `schemas.py` SoOverrideLineIn — silang B3b), `audit_i18n_id --strict`
(UI-32). Tidak bisa dinilai di host Windows (artefak path `\`/modul hilang, perlu diulang di container): qty_dual,
to_list_bound, home_kpi.

## 6. Butir yang butuh keputusan pemilik (+ rekomendasi)

| ID | Pertanyaan | Rekomendasi B1 |
|---|---|---|
| K-B1-01 | Siapa yang dibatasi lokasi, dan apakah "lokasi bawaan" berlaku untuk semua peran operasional (Admin Gudang, sales, Admin Sales)? | Semua akun operasional punya site bawaan; daftar & angka bawaan = site itu; supervisor boleh melepas saringan. Setelan per site, bukan sakelar global. |
| K-B1-02 | Cakupan tugas fisik: per **gedung/lokasi** (semua PT) atau per **PT aktif**? (K-GDG-07 gedung dipakai bersama) | Per lokasi, PT sebagai label + saringan; validasi kepemilikan tetap di server. |
| K-B1-03 | Angka stok utama per peran: lokal (lokasi & PT saya) atau grup? Bucket mana yang tampil di layar harian? | Utama = Tersedia lokal; kedua = Tersedia grup; sisanya di rincian. Multi-Bucket = layar analis. |
| K-B1-04 | Satu antrean "Keluar"/"Masuk" per lokasi untuk semua jenis dokumen (SO, sample, transfer, makloon, perbaikan, retur)? | Ya — chip jenis + tautan dokumen; sejalan K-GDG-02 (gate menilai semua jenis sama). |
| K-B1-05 | Wajib pindai roll saat Ambil (HP & desktop)? | Ya untuk roll bertag/berlabel; ketik qty hanya jalur darurat beralasan. |
| K-B1-06 | Standar tombol resmi: kelas CSS (`primary-button` dkk.) atau shadcn `<Button>` seperti tertulis di KN_08? | Kelas CSS (sudah 1.774 pemakaian) + varian `sm`/`touch` resmi; perbarui KN_08; ratchet larang `!py-*`. |
| K-B1-07 | Operasional gate (kunci, sesi dokumen) di menu RFID untuk Admin Gudang & manajer? | Ya — Perangkat hanya konfigurasi. Manajer diberi menu RFID baca. |
| K-B1-08 | Aplikasi HP sopir: Pengiriman saja? | Ya — daftar pengiriman hari ini + foto muat/POD. |
| K-B1-09 | Ukuran huruf minimum UI (KN_08 menulis 12 px; 76 % pemakaian di bawahnya) | 12 px minimum desktop, 14–16 px untuk layar pindai HP; ratchet guardrail. |
| K-B1-10 | Izin tindakan data: arsipkan 3 PT "Uji Provisioning" & 6 gudang `TEST_WH` (beserta tugasnya) di DB uji/UAT, dan aturan agar uji otomatis membersihkan datanya | Ya — sebelum UAT berikutnya; tanpa ini setiap angka "semua gudang/semua PT" tercemar (54/131 tugas). |

## 7. Silang ke paket lain
- **B3a (SSOT/angka stok):** UI-05 (data uji ikut "Semua"), UI-06/07 (definisi angka, total grup vs lokal), UI-40 (ATP
  beda antar tab, Stok Habis 292 vs 128), UI-42 (belum ditempatkan 2108 vs 14), UI-43 (tugas qty 0), UI-04 (papan vs daftar).
- **B3b (form/daftar/ekspor):** UI-14 (batas server), UI-15 (urut), UI-30 (ekspor & format CSV logistik), UI-31 (tabel),
  numeric_bounds `schemas.py` SoOverrideLineIn.
- **B4 (riset eksternal):** pola "pick per dokumen"/"wave", target sentuh handheld, hierarki angka stok (on-hand vs
  available vs ATP) di WMS komersial — untuk UI-06, UI-09, UI-12.

## 8. Ringkasan

**Cakupan.** Menu/tab dari kode: 37 baris × 12 peran = 444 sel desktop (166 tampil) + matriks HP; dikunjungi di peramban:
**16 sel desktop + 2 sel HP**, **12 layar desktop terukur** (+1 pop-up U300, pengalih PT), **4 aplikasi HP** (gudang ×3 akun,
Ops admin, QC, sales) di 390 × 844, sidebar 4 peran, probe API hanya-GET untuk **16 akun**. Sensus statis 1.095 berkas FE,
288 berkas cakupan, 19 guardrail.

**Temuan: 43** (P0 0 · **P1 15** · P2 23 · P3 5).

| Klasifikasi | Jumlah | Temuan |
|---|---:|---|
| bug | 6 | UI-05, 14, 23, 33, 39, 43 |
| hambatan UX | 5 | UI-01, 06, 13, 38, 41 |
| inkonsistensi | 18 | UI-04, 08, 10, 16, 17, 22, 24, 25, 26, 27, 28, 29, 30, 31, 32, 35, 40, 42 |
| duplikasi | 3 | UI-07, 18, 21 |
| fitur belum ada | 5 | UI-09, 12, 15, 36, 37 |
| butuh keputusan | 6 | UI-02, 03, 11, 19, 20, 34 |

| Area | Jumlah | P1 |
|---|---:|---|
| Cakupan data/lokasi/PT | 6 | UI-01, 02, 03, 39 |
| Angka stok | 3 | UI-06, 40 |
| Jenis tugas keluar & potong | 4 | UI-08, 09, 10 |
| Pindai, terima, ambil | 4 | UI-11, 12 |
| Daftar besar (roll banyak) | 2 | UI-14 |
| QC / GRN / OCR | 5 | – |
| RFID | 3 | UI-21 |
| Aplikasi HP | 5 | UI-23, 36 |
| Elemen UI (huruf, warna, tombol, tab, tabel, ekspor, istilah, label) | 8 | – |
| Navigasi & Lokasi Rak | 3 | – |

**Status bukti:** 31 terverifikasi di peramban (3 di antaranya sebagian), 4 terukur statis (sensus/guardrail), 8 kandidat
statis (UI-07, 09, 13, 15, 25, 31, 34, 35). Satu klaim statis **gugur** saat diukur: tombol "Terima"/"Ambil" HP ternyata
54 px (UI-24 dikoreksi).

**10 pola teratas** (rinci §3): (1) cakupan gudang/PT tidak terlihat & bukan bawaan lokasi pengguna; (2) dua pintu/dua
aturan untuk satu pekerjaan (HP vs desktop); (3) angka stok berlapis tanpa hierarki; (4) angka sama bernilai beda; (5)
data uji bercampur dengan data kerja; (6) HP tidak setara desktop untuk pekerjaan lantai gudang; (7) batas server senyap;
(8) huruf < 12 px dominan (76 %); (9) elemen buatan sendiri di samping komponen baku (tombol, chip, tab, tabel); (10) kontrol
daftar tidak merata (ekspor 0 di 12 layar terukur, urut nyaris tidak ada).

**Butuh keputusan pemilik:** K-B1-01 … K-B1-10 (§6) — yang paling menentukan arah perbaikan: K-B1-02 (cakupan tugas per
lokasi vs per PT), K-B1-03 (angka stok utama lokal vs grup), K-B1-04 (satu antrean Masuk/Keluar per lokasi), K-B1-05 (wajib
pindai roll saat ambil), K-B1-10 (bersihkan data uji).
