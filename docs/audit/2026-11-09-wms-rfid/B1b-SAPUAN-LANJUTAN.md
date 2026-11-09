# B1b — Sapuan peramban lanjutan: semua sel menu × peran × desktop/HP

- **Tanggal:** 9 Nov 2026 (WIB) · **Paket:** B1b (lanjutan B1) audit WMS-RFID · **Sifat:** AUDIT — tanpa ubah kode aplikasi,
  tanpa menyimpan data lewat UI (tidak ada Simpan/Terima/Ambil/Potong/Setujui/Kirim/Hapus yang ditekan), tanpa ubah setelan.
- **Basis kode:** `main@cb9f924` (worktree di-*rebase* ke `main` terbaru, memuat PREP-F printer CP30EN & PREP-G handheld
  C72). Sejak basis B1 (`5f1e36e`) yang berubah di `frontend/src` hanya berkas printer RFID (PREP-F), jadi rujukan
  `berkas:baris` B1 untuk layar lain tetap berlaku; rujukan baru di bawah = `main@cb9f924`.
- **Aplikasi:** stack bersama `kn-uji` — http://localhost:3063 (FE dev server) / :8063 (BE), DB `kn_test_trial`.
- **Lampiran:** [`B1-MATRIKS-CAKUPAN.md`](B1-MATRIKS-CAKUPAN.md) (diperbarui) · `scripts/audit/b1b_browser_measure.js`
  (pengukur di peramban) · `scripts/audit/b1b_build_matrix.py` + `b1b_matrix_notes.json` (matriks) ·
  `scripts/audit/b1b_skeleton.py` (kerangka 20 layar tambahan).
- **Melanjutkan:** [`B1-UI-MENU-PERAN.md`](B1-UI-MENU-PERAN.md) (UI-01…UI-43). Temuan baru mulai **UI-44**.

> **Riwayat stack (dibaca dulu).** Pukul ±06:49 WIB Docker engine memulai ulang dirinya; `kn-uji-frontend`,
> `kn-uji-backend`, `kn-dev-mongo-1` berhenti (`Exited 255`) sampai ±07:54 WIB. B1b **tidak** me-restart stack (sesuai
> instruksi); koordinator memulihkannya. Seluruh pengukuran peramban di bawah diambil **07:54–08:52 WIB**. Pukul
> 08:31:48 WIB backend di-restart koordinator (±1 menit, kode `main` baru: PREP-F/G); dua layar yang terukur saat jeda itu
> (`md-products` & `grade-master` untuk peran MD — "0 induk produk", "Tidak bisa menghubungi server") **diulang** dan hasil
> ulangnya yang dipakai. Tidak ada galat jaringan masa jeda yang dicatat sebagai temuan.

---

## 0. Metode

1. **Daftar sel dari kode** (`b1_matrix_report.rows()` — sama dengan B1): 37 baris × 12 peran; 166 sel tampil.
2. **Ganti akun** lewat `__b1bLogin` (`scripts/audit/b1b_browser_measure.js`): `POST /auth/login` dengan cookie
   (`credentials:'include'`, sama seperti layar login), simpan `kn_token`/`kn_user`/`kn_entity_ctx`, lalu **PT aktif =
   PT bawaan akun** (catatan UI-39). Percobaan pertama tanpa cookie memperlihatkan bahwa server memakai cookie sesi lama di
   atas token baru — jadi temuan **UI-44**. PT aktif tiap akun dicatat di §0.1.
3. **Ukur tiap sel** dengan membuka `?view=<view>` lalu `__s`/`__h`: tunggu sampai tidak ada "Memuat…"/spinner **dan**
   jaringan API diam ≥ 1,5 s; ukur di `<main>`: porsi teks < 12 px, huruf terkecil, tombol < 24/36/44/48 px (tinggi
   atau lebar), isian, cari, chip saringan, pager, ekspor, urut kolom, tabel mentah, id mentah, data uji, teks galat,
   keadaan kosong, **"kosong palsu"** (teks kosong yang tampil *selama* memuat), istilah Inggris, geser mendatar.
4. **HP:** aplikasi HP per peran di **390 × 844** (`__hp` mengetuk tiap tab bawah lalu mengukur); layar pindai gudang juga
   di **360 × 780**. Layar tanpa pintu di aplikasi HP diukur lewat "Tampilan desktop" (`kn_force_desktop=1`, preferensi
   tampilan — dihapus di akhir) atau lewat tombol "tampilan penuh" aplikasinya.
5. **Pop-up/detail** dibuka lalu ditutup (Esc/"Kembali") tanpa menyimpan: SPK, GRN, Retur Pelanggan, Order Makloon.
6. **Akhir:** login kembali sebagai admin, PT Sukacita, ukuran desktop; kunci `localStorage` pengukur (`b1b_fn`,
   `b1b_last`, `kn_force_desktop`) dihapus.

Catatan ukuran: lebar desktop = **1024 px** (lebar panel peramban; B1 juga 1024 — judul "1440 px" di matriks B1 keliru).
Frontend `kn-uji` adalah **dev server + React StrictMode** (`frontend/src/index.js:69`) — angka waktu muat & jumlah
panggilan API di bawah lebih besar daripada build produksi (lihat UI-51).

### 0.1 Log kunjungan (07:54–08:52 WIB)

| # | Akun (PT aktif dipasang) | Ukuran | Yang dikunjungi | Temuan utama |
|---|---|---|---|---|
| W1 | admin (Sukacita) | 1024 | 23 sel `K` + tab baru Tag RFID › Antrean Printer (PREP-F) + Monitor Gerbang › Antrean periksa / Alarm & Keamanan + detail GRN/Retur/Order Makloon + Data Gudang | UI-50, 52, 58, 59, 60 |
| W2 | manager (Sukacita; daftar PT memuat 3 PT "Uji Provisioning") | 1024 | 31 sel (29 `K`) | UI-47, 57, 61 |
| W3 | wh.admin (Sukacita; 2 PT) | 1024 | 32 sel | UI-45, 46, 48 |
| W4 | warehouse@ Jakarta (Sukacita, 1 PT, site Jakarta) | 1024 + 390 | 28 sel desktop + 28 sel HP lewat "Tampilan desktop" + aplikasi HP (5 tab, 3 sub-tab Pindai) + 360 × 780 | UI-45, 46, 53, 54 |
| W5 | warehouse.soreang (Kanda) | 1024 | 14 layar sensitif cakupan | UI-45, 46, 55 |
| W6 | warehouse.rancamalang (Cipta Sandang, 3 PT) | 1024 | 7 layar sensitif cakupan | UI-45, 46 |
| W7 | sales (Sukacita) | 1024 + 390 | 7 sel + Lainnya/Layar lengkap HP | UI-45; sel Lot & Silsilah `–(V)` |
| W8 | salesadmin (Sukacita) | 1024 + 390 | 13 sel + Lainnya/Layar lengkap HP (4 layar dibuka penuh) | UI-45, 48 |
| W9 | finance (Sukacita; 3 PT) | 1024 + 390 | 5 sel + aplikasi HP (4 tab) | UI-49 |
| W10 | md (Sukacita) | 1024 + 390 | 6 sel + Master Grade (dialihkan) + aplikasi HP (5 tab + Stok & ATP) | UI-35 (konfirmasi), UI-52 |
| W11 | mdquality (Sukacita) | 1024 + 390 | 2 sel + Master Grade (dialihkan) + HP | UI-37 (berlaku juga untuk MD Quality) |
| W12 | qc (Sukacita) | 1024 | Retur + Master Grade (dialihkan) | UI-35 |
| W13 | sampleadmin (Sukacita) | 1024 + 390 | 2 sel + aplikasi HP (2 tab) + Meja Admin Sample penuh | UI-50, 52 |
| W14 | driver (Sukacita) | 1024 | Pengiriman + Meja Saya | UI-56 |
| W15 | manager · whadmin (Cipta Sandang) | 390 | aplikasi HP (Persetujuan/Ringkas/Pintasan/Tanya/Lainnya; Masuk/Keluar/Sample) + 3 Pintasan tampilan penuh + 5 layar "Tampilan desktop" | UI-52 |
| W16 | admin | 390 | 5 layar "Tampilan desktop" (POS, Perangkat, Monitor Gerbang, Data Gudang, Aturan Gudang & Mutu) | UI-52 |

### 0.2 Ukuran terukur per layar (desktop 1024; satu peran per baris — peran lain berbeda ≤ 2 poin kecuali disebut)

| Layar (view) | Peran | Siap (s)¹ | Teks < 12 px | Huruf min | Tombol: n / < 24 px / < 44 px | Cari | Chip | Pager | Ekspor | Urut | Kosong palsu² | Data uji |
|---|---|---:|---:|---:|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Operasi Gudang › Stok (`operations`) | wh Jkt | 7,4 | 95 % | 9 | 46 / 2 / 46 | ✓ | – | ✓ | – | – | – | ✓ |
| Barang Masuk (`goods-receipts`) | mgr | 4,5 | 55 % | 10 | 30 / 0 / 15 | ✓ | 6 | – | – | – | – | – |
| Barang Keluar (`wms-outbound`) | mgr | 8,1 | 82 % | 9 | 132 / 1 / 18 | ✓ | sendiri | – | – | – | – | – |
| Cutting (`wms-cutting`) | mgr | 5,1 | 61 % | 10,5 | 57 / 6 / 57 | ✓ | sendiri | – | – | – | – | – |
| Perbaikan (`repair-orders`) | mgr | 4,6 | 26 % | 10,5 | 11 / 0 / 11 | ✓ | 5 | – | – | – | – | – |
| Status Stok & ATP (`inventory-board`) | wh Jkt | 11,1 | 40 % | 9,5 | 11 / 0 / 11 | ✓ | tab | – | – | – | – | – |
| Stok Multi-Bucket (`stock-buckets`) | wh Jkt | 3,3 | 72 % | 10 | 32 / 0 / 12 | ✓ | – | – | – | – | – | – |
| Lot & Silsilah (`inventory-lots`) | mgr | 5,3 | **94 %** | 9,5 | 44 / **20** / 44 | ✓ | – | ✓ | CSV | – | ✓ | ✓ |
| BOM Produksi (`production`) | wh Jkt | 4,5 | 52 % | 10 | 4 / 0 / 4 | ✓ | – | – | – | – | – | – |
| Lokasi Rak (`wms-locations`) | wh Jkt | **21,5** | 57 % | 10 | **1.509** / 0 / 1.509 | – | – | – | – | – | – | ✓ |
| Data Gudang (`md-warehouses`) | adm | 5,0 | **94–98 %** | 9,5 | 56 / **15** / 56 (hapus **11 × 11**) | ✓ | – | – | – | – | ✓ | ✓ |
| Pengiriman (`logistics`) | wha | 6,0 | 84 % | 9,5 | 34 / 8 / 31 | – | – | – | (tab daftar) | 5³ | – | – |
| Lokasi RFID (`cs-rfid-lokasi`) | wha | 5,8 | 28 % | 10 | 8 / 0 / 8 | ✓ | – | "Halaman 1/2" | – | – | – | – |
| Tag RFID (`cs-rfid-tags`) | wh Jkt | 6,2 | 16 % | 10,5 | 60 / 0 / 60 | ✓ | – | – | – | – | – | – |
| Monitor Gerbang (`cs-rfid-gate`) | wh Jkt | 6,1 | 22 % | 10 | 15 / 1 / 15 | ✓ | – | – | – | – | ✓ | ✓ |
| Eskalasi Gudang (`escalations`) | mgr | 5,4 | 13 % | 10,5 | 3 / 0 / 3 | – | 3 | – | – | – | – | – |
| Antrean QC (`qc-inspection`) | mgr | 3,6 | 42 % | 10 | 16 / 0 / 3 | ✓ | – | – | – | – | – | – |
| SPK Inspeksi (`inspections`) | mgr | 6,2 | 42 % | 10 | 82 / **25** / 82 | ✓ | 16 | ✓ | CSV | – | – | – |
| Retur Pelanggan (`returns`) | mgr | 4,5 | 45 % | 10 | 39 / 3 / 39 | ✓ | – | ✓ | CSV | – | – | ✓ |
| Retur Antar-PT (`interco-returns`) | mgr | 4,7 | 43 % | 10 | 10 / 3 / 8 | – | – | – | – | – | ✓ | – |
| Retur ke Supplier (`purchase-returns`) | mgr | 4,6 | 31 % | 10 | 51 / 0 / 51 | ✓ | – | ✓ | CSV | – | – | – |
| Meja Saya (`my-desk`) | mgr | 4,8 | 82 % | 9 | 29 / 4 / 24 | 3 kotak | – | – | – | – | – | ✓ |
| Meja Admin Sample (`sample-admin-desk`) | sma | 3,5 | 79 % | 9,5 | 23 / 3 / 18 | 2 | – | – | – | – | ✓ | – |
| Order Makloon (`makloon-orders`) | mgr | 6,7 | 42 % | 9,5 | 44 / **25** / 44 | ✓ | – | – | – | – | – | – |
| Kinerja Mitra Makloon (`makloon-claim-recap`) | mgr | 6,2 | 30 % | 10,5 | 13 / 0 / 13 | – | – | – | **Excel** | – | – | ✓ |
| Klaim Selisih Makloon (`makloon-claims`) | mgr | 3,5 | 47 % | 9,5 | 13 / 0 / 13 | ✓ | – | – | – | – | – | ✓ |
| Permintaan Pembelian (`purchase-requisitions`) | mgr | 4,6 | 46 % | 10 | 33 / **18** / 33 | ✓ | – | – | – | – | – | ✓ |
| Kontrabon (`contra-bons`) | mgr | 6,0 | 50 % | 10,5 | 18 / 0 / 17 | – | 9 | – | – | – | – | – |
| Antar Entitas (`interco-transactions`) | mgr | 5,9 | 15 % | 10,5 | 24 / 3 / 24 | ✓ | – | – | – | – | ✓ | – |
| Analitik Stok (`cs-stock-analytics`) | mgr | 7,6 | 39 % | 10 | 12 / 0 / 6 (tabel 128 baris tanpa pager) | ✓ | – | – | – | – | ✓ | ✓ |
| POS (`sales`) | adm | 4,6 | 58 % | 10,5 | 4 / 0 / 4 | – | – | – | – | – | **nol palsu** | – |
| Produk & Varian (`md-products`) | adm | 6,7 | 17 % | 10 | 164 / 3 / 140 | 3 kotak | – | "Sebelumnya 1/1 Berikutnya" | – | – | **nol palsu** | ✓ |
| Aturan Gudang & Mutu (`settings-cfg-warehouse`) | mgr | **13,4** | 30 % | 10,5 | 92 / **53** / 92 | ✓ | 4 | – | – | – | – | – |
| Penerimaan & OCR (`settings-receiving-ocr`) | mgr | 3,4 | 66 % | 9,5 | 13 / 4 / 13 (tinggi **13 px**) | 2 | – | – | – | – | – | – |
| Master Grade Mutu (`grade-master`) | mgr | 4,4 | 15 % | 10,5 | 3 / 0 / 3 (admin 18 / 0 / 18) | – | – | – | – | – | – | – |
| Perangkat (`settings-devices`) | mgr | 6,3 | 27 % | 9,5 | 8 / 1 / 8 | – | – | – | – | – | – | – |

¹ Detik sejak navigasi sampai layar diam (dev server). ² Teks "Belum ada…/Tidak ada…" atau angka 0 yang tampil selama
data masih dimuat (UI-50). ³ Hanya di tab "Daftar pengiriman" peran sopir — satu-satunya layar dengan kolom yang bisa diurut.

**Ringkas 37 layar:** teks < 12 px 13–98 % (median ≈ 45 %); **20 dari 37 layar punya tombol < 24 px** (batas minimum WCAG
2.5.8 / B4 §3.3 desktop); ekspor hanya di **6** layar (5 CSV + 1 Excel); urut kolom **1** layar; pager **3 gaya
berbeda**; "kosong/nol palsu" di **9** layar; data uji di **13** layar.

### 0.3 HP 390 × 844 (dan 360 × 780) — angka kunci

| Layar / aplikasi | Akun | Hasil terukur |
|---|---|---|
| `MobileWarehouseApp` Masuk/Keluar/Sample | warehouse Jakarta | Masuk "**30 terbuka**" = Menunggu Barang 13 · **Menunggu QC 13 · Ditolak QC 4** (UI-54); semua pil `rgba(255,149,0,.1)`; teks < 14 px **75 %**, huruf min **9 px**; kartu Ditolak QC hanya "Cetak ulang label QR roll"; app bar "Sukacita · Gudang" tanpa lokasi |
| Pindai (3 sub-tab) | warehouse Jakarta | 390: isian pindai 330 × 56 / 16 px (lolos), isian bin 50 px, tombol "Pindai" 330 × **44**, sub-tab **38** px, lonceng 36 × 36; teks < 14 px **89 %**. **360 × 780**: tanpa geser mendatar (lebar dokumen 360), isian 300 × 56, tombol 300 × 44, tab bawah 72 × 56 — tata letak lolos, target < 48 tetap sama |
| `MobileOpsApp` manajer | manager | Persetujuan: **Setujui 153 × 36, Tolak 151 × 36**, "Buka layar lengkap" **122 × 18**; Pintasan 4 tombol 322 × 36; chip PT 36 px (tanpa PT uji — berbeda dengan pengalih desktop); "Kembali ke aplikasi HP" **169 × 32** |
| `MobileOpsApp` finance · sample_admin | finance, sampleadmin | finance: 4 tab, **tanpa** pintu ke Barang Masuk/Retur/Kinerja Mitra/Antar Entitas; sample_admin: 2 tab, "Buka Meja Admin Sample" 338 × 36 |
| MD Quality di HP | mdquality | sama dengan QC (UI-37): mendarat di SPK desktop 390 (78/103 tombol < 48), tanpa tab aplikasi & tanpa tombol kembali |
| `MobileSalesApp` | salesadmin, sales | Lainnya › "Layar lengkap" memuat Operasi Gudang (pantau), Lot & Silsilah (sla), Pengiriman, Produk & Varian, PR, Transaksi Antar-PT — dibuka penuh: teks < 12 px 84–96 %; Stok & ATP dalam aplikasi = angka grup (UI-06) |
| `MobileMdApp` | md | 5 tab; tombol "Muat ulang" **15 × 15**; Stok & ATP = angka utama grup, satuan 10 px (UI-06 berlaku juga untuk MD) |
| "Tampilan desktop" 390 (36 layar) | warehouse, manager, admin | **tidak ada** geser mendatar dokumen di 36 layar; 14 layar punya tabel lebih lebar dari layar (bergulir di wadahnya); tombol < 48 px = 80–100 % per layar; Pengaturan menampilkan "Pengaturan paling nyaman di desktop" |

---

## 1. Temuan baru

Format sama dengan B1: **Area/layar** · **Peran** · **Ukuran** · **Klasifikasi** · **Keparahan** (P0 data salah/
kebocoran/hilang · P1 alur terhambat/menyesatkan · P2 tidak konsisten/merepotkan · P3 kosmetik) · **Bukti** · **Aturan**
· **Dampak** · **Rekomendasi** · **Status**.

### A. Sesi & cakupan

### UI-44 — "Keluar" tidak mengakhiri sesi server; cookie sesi lama mengalahkan token akun baru
- **Area/layar:** login/logout (desktop & HP — penting untuk HP bersama). **Peran:** semua. **Ukuran:** keduanya.
- **Klasifikasi:** bug (keamanan sesi) · **Keparahan:** P1 · **silang UI-39**.
- **Bukti:**
  - Langkah: login admin → klik **Keluar** (layar login tampil) → `fetch('/api/auth/me', {credentials:'include'})` →
    **200 `admin@kainnusantara.id`**. Sesi admin tetap hidup di server setelah keluar.
  - Logout di FE hanya mengosongkan state & `localStorage` (`frontend/src/hooks/useAppActions.js:121-127`); **tidak ada**
    panggilan ke `POST /auth/logout` di seluruh `frontend/src` (grep 0), padahal endpoint itu yang menghapus sesi &
    cookie (`backend/routers/auth.py:178-184`). `axios.defaults.withCredentials = true` (`services/apiClient.js:7`).
  - Server mengutamakan cookie di atas header Bearer (`backend/dependencies.py:26-33`). Teramati: `kn_token` = manajer,
    cookie = admin → semua layar tampil sebagai **admin** dan `kn_user` di peramban ditimpa kembali menjadi admin oleh
    penyegar sesi (`hooks/useSessionSync.js:30-37`).
- **Aturan:** KN_14 (sesi per pengguna), praktik dasar keamanan (logout = invalidasi sesi).
- **Dampak:** di HP gudang yang dipakai bergantian, setelah "Keluar" sesi orang sebelumnya masih bisa dipakai (mis. membuka
  `/api/...` langsung); bila set-cookie login berikutnya gagal, pengguna baru bekerja atas nama orang sebelumnya tanpa
  tanda apa pun. Bersama UI-39 (PT terbawa) → konteks sesi bocor dua lapis.
- **Rekomendasi:** `logout()` memanggil `POST /auth/logout` (lalu bersihkan `kn_*` termasuk `kn_entity`/`kn_entity_ctx`);
  server menolak bila cookie & Bearer menunjuk pengguna berbeda (atau pakai satu mekanisme saja).
- **Status:** **terverifikasi** (W1/W2, ±08:00 WIB).

### UI-45 — Status Stok & ATP: peran gudang/Admin Gudang/sales/Admin Sales melihat angka GRUP berlabel "Konteks: PT saya"
- **Area/layar:** Stok & ATP › Status Stok & ATP (desktop), HP Stok & ATP. **Peran:** warehouse (3 akun),
  warehouse_admin, sales, sales_admin (MD di HP). **Ukuran:** keduanya.
- **Klasifikasi:** inkonsistensi angka (menyesatkan) · **Keparahan:** P1 · **silang UI-40, B3a STK-5**.
- **Bukti (PT aktif sama — Sukacita):**

  | Peran | Status Stok & ATP: "Total ATP" | "Stok Habis" | Tab sebelah Multi-Bucket "ATP" |
  |---|---|---|---|
  | admin, manager | 60.996,16 kg · 108 m · 1.314.153,95 yd | 292 | 61.071,16 kg |
  | warehouse_admin, sales, sales_admin, warehouse Jakarta | **387.487,6 kg · 108 m · 2.462.184,32 yd** | 128 (sales, Admin Sales, gudang; bacaan Admin Gudang terpotong sesudah "12…") | 61.071,16 (wha) · **60.616,43 kg** (wh Jakarta) |
  | warehouse.soreang (Kanda) / warehouse.rancamalang (CST) | **387.487,6 kg** — label "Konteks: Kanda Fabric" / "Konteks: Cipta Sandang" | 128 | 73.427,87 kg / 253.035,84 kg |

  Petugas Jakarta melihat **6,4 ×** angka tab sebelahnya; angka yang sama persis muncul di tiga PT berbeda dengan label PT
  masing-masing. Penyebab: server memberi `detail_scope: "own_entity"` + `global_total` untuk peran non-lintas-PT
  (`backend/services/fulfillment_service.py:290-294, 382`; `routers/inventory.py:178`), lalu FE memakai `pv()` = total
  grup sebagai angka utama (`frontend/src/features/inventory/InventoryStatusBoard.jsx:26-27`) — aturan "POV sales"
  (W2-REQ-04) ikut berlaku untuk gudang — sementara kalimat di atas tabel tetap "Konteks: {PT}" (`:123`).
- **Aturan:** B4 §3.7 ADS-1 (setiap angka stok menyebut cakupannya); KN_14 §10 (konteks entitas terlihat & benar).
- **Dampak:** petugas/Admin Gudang membaca 387 ton sebagai stok PT-nya; "Stok Habis 128" vs 292 untuk PT yang sama →
  keputusan janji kirim/opname salah. Memperluas UI-40 dari "beda antar tab" menjadi "beda antar peran dengan label sama".
- **Rekomendasi:** angka utama = PT aktif (dan lokasi kerja); total grup hanya sebagai baris kedua berlabel "Grup (semua
  PT)"; label "Konteks" mengikuti angka yang benar-benar ditampilkan. Keputusan angka utama per peran tetap K-B1-03.
- **Status:** **terverifikasi** (W3–W8, W10 HP).

### UI-46 — Lokasi Rak: KPI per gedung (semua PT), antrean per PT aktif dan dipotong 500 diam-diam; layar 12–21 s, 1.509 tombol
- **Area/layar:** Gudang & Logistik › Lokasi Rak › Penempatan Rak. **Peran:** warehouse (3 akun), warehouse_admin,
  manager, admin. **Ukuran:** desktop & HP (Tampilan desktop).
- **Klasifikasi:** bug (data tak terlihat) + inkonsistensi + kinerja · **Keparahan:** P1 · **menjelaskan UI-42, silang
  UI-14/LST-01**.
- **Bukti:**

  | Akun (PT) | Gedung bawaan | KPI "Belum Ditempatkan" | Tab "Penempatan Rak (n)" | Siap |
  |---|---|---|---|---|
  | manager / wh.admin (Sukacita) | Rancamalang · Knitting | 2108 roll | **(14)** | 5–8 s |
  | warehouse.rancamalang (CST) | Rancamalang · Knitting | 2108 roll | **(500)** | 19,1 s |
  | warehouse Jakarta (Sukacita) | Jakarta · Sukacita | **4700 roll** | **(500)** | 21,5 s |
  | warehouse.soreang (Kanda) | Soreang · Kanda | 517 roll | **(500)** | 11,9 s |

  KPI dihitung per gedung untuk semua PT, antrean memakai PT aktif (`resolve_list_scope(..., entity_id)`) dan
  `to_list(limit=500)` (`backend/services/location_service.py:227, 237, 241`); label tab = panjang potongan
  (`frontend/src/features/wms/LocationPutawayView.jsx:62-67, 134`). Tanpa pesan "terpotong". Untuk 500 roll layar
  merender **1.509 tombol & 3.534 elemen teks** (3 tombol/baris, `:155`, `location/PutawayRow.jsx`) dan menghitung
  `_queue_block` per roll (`location_service.py:248`). Hasil yang sama di 390 px (17,5 s).
- **Aturan:** K-GDG-07 (gedung bersama, roll tetap milik PT); B4 §3.8 (ribuan roll: server-side, virtualisasi);
  LST-01/UI-14 (batas senyap).
- **Dampak:** petugas Jakarta hanya melihat 500 dari 4.700 roll yang harus ditempatkan, dan supervisor PT Sukacita di
  Rancamalang hanya 14 dari 2.108 (sisanya milik PT lain di gedung yang sama) — antrean tidak pernah "habis" sesuai KPI.
- **Rekomendasi:** KPI & antrean memakai cakupan yang sama dan disebut ("Gedung ini · semua PT" + saring PT); halaman
  server + total; render virtual; `_queue_block` dihitung batch.
- **Status:** **terverifikasi** (W2–W6).

### UI-47 — Manajer: menu Pengiriman tampil, layar menampilkan "Permission ditolak: logistics.view" mentah
- **Area/layar:** Gudang & Logistik › Pengiriman. **Peran:** manager. **Ukuran:** desktop.
- **Klasifikasi:** bug (menu ↔ izin tidak sinkron) · **Keparahan:** P2 · pola tahap 2 "galat izin mentah" (muncul lagi).
- **Bukti:** menu tampil karena `navStructure.js:287` memuat `manager`; layar hanya berisi judul + "Permission ditolak:
  logistics.view". Izin efektif manajer dari login (`/auth/login` → `permissions`, 74 sumber daya) **tidak** memuat
  `logistics`, padahal katalog bawaan memberi `logistics: view, manage, update` untuk manajer
  (`backend/permissions_config.py:312`) — izin tersimpan di DB uji berbeda dari katalog dan tidak disinkronkan.
- **Dampak:** manajer (penanggung jawab pengiriman) tidak bisa memantau pengiriman; pesan berbahasa kode.
- **Rekomendasi:** menu diturunkan dari izin efektif (`can(perms,'logistics','view')`), bukan daftar peran; migrasi izin
  peran bawaan saat katalog berubah; galat izin memakai `ErrorNotice` berbahasa pengguna.
- **Status:** **terverifikasi** (W2).

### UI-48 — "Meja Saya" untuk Admin Gudang & Admin Sales: galat dengan kunci peran mentah, lalu angka 0 dan "Belum ada antrean"
- **Area/layar:** (lepas) › Meja Saya. **Peran:** warehouse_admin, sales_admin. **Ukuran:** desktop.
- **Klasifikasi:** bug (menu ↔ server) · **Keparahan:** P2.
- **Bukti:** layar menampilkan bilah galat "Peran **'warehouse_admin'** memakai meja khususnya sendiri. · Coba lagi · ×"
  (juga "'sales_admin'") **di atas** kartu "PERLU DITINDAK 0 · ANTREAN 0" dan "Belum ada antrean untuk badan usaha yang
  sedang Anda lihat." Server menolak dengan 404 berteks kunci peran (`backend/routers/work_desks.py:257-260`); menu tampil
  karena peran turunan mewarisi entri `my-desk` (`frontend/src/config/navStructure.js:88-97`). Tombol "Coba lagi" tidak
  pernah berhasil.
- **Dampak:** dua pesan bertentangan (galat + kosong); pengguna mengira tidak ada pekerjaan.
- **Rekomendasi:** sembunyikan Meja Saya untuk peran yang punya meja khusus atau alihkan ke mejanya (Meja Gudang / Meja
  Admin Sales); pesan galat memakai label peran.
- **Status:** **terverifikasi** (W3, W8).

### UI-49 — Galat izin disamarkan sebagai data kosong
- **Area/layar:** Kinerja Mitra Makloon › Skor mitra (finance); pemilih grade di inspeksi (warehouse, FRM-18).
- **Klasifikasi:** bug (galat senyap) · **Keparahan:** P2 · **silang LST-06, FRM-18**.
- **Bukti:** finance: `GET /api/makloon-partners/scorecard?entity_id=ent_ksc` → **403** (2×, dari daftar jaringan), layar
  menampilkan "**Belum ada penerimaan makloon untuk dinilai.**" sedangkan admin/manajer/gudang melihat 2 mitra di tabel
  yang sama — `.catch(() => setRows([]))` (`frontend/src/features/purchasing/makloon/MakloonPartnerScorePanel.jsx:98`,
  teks kosong `:116`). warehouse: `GET /api/master/grades` → **403 "Permission ditolak: grade_master.view"** → pemilih grade
  `[]` (`InspectLineModal.jsx:50`, `InspectSheetGrid.jsx:60`, `RollInspectionModal.jsx:61`).
- **Dampak:** pengguna tidak tahu bahwa ia tidak berhak — mengira datanya memang kosong (pola terbalik dari UI-47).
- **Rekomendasi:** hook daftar baku `{rows, loading, error}`; 403 → `ErrorNotice` "Anda tidak punya akses …" (B4 §3.10
  "Kosong — di luar cakupan/izin"); atau panel disembunyikan bila tak berizin.
- **Status:** **terverifikasi** (W9, W4).

### B. Keadaan memuat, angka & format

### UI-50 — Keadaan kosong / nol palsu saat memuat (LST-06 terverifikasi) — termasuk POS "Belum ada pelanggan — buat pelanggan baru"
- **Area/layar:** 9 layar. **Peran:** semua yang terukur. **Ukuran:** desktop.
- **Klasifikasi:** bug UX · **Keparahan:** P2 · **konfirmasi LST-06**.
- **Bukti (teks yang terbaca selama spinner/jaringan masih jalan, lalu hilang):** Lot & Silsilah "Tidak ada lot"
  (`components/PaginationBar.jsx:143` — `total === 0` sebelum data datang); Data Gudang "Belum ada lokasi."
  (`WarehouseMasterView.jsx:233`); Retur Antar-PT "Belum ada retur antar-PT"; Antar Entitas "Belum ada transaksi antar-PT."
  (`finance/interco/IntercoPanels.jsx:58`); Analitik Stok "Belum ada data persediaan…" (`StockAnalyticsView.jsx:331`);
  Monitor Gerbang "Belum ada gerbang di gudang ini…" (`rfid/RfidGateMonitorView.jsx:190`); Meja Admin Sample "Tidak ada SO
  aktif". **Nol palsu:** POS — "PRODUK AKTIF 0 · JML TERSEDIA 0 · GUDANG 0" dan pemilih pelanggan "**Belum ada pelanggan —
  buat pelanggan baru**" (`pos/PosStartGate.jsx:44`) selama 2–6 s, lalu 411 produk / 29 pelanggan; Produk & Varian
  "**0 induk produk · 0 dari 0 produk**" (`catalog/CatalogWorkspace.jsx:61`) sampai ±5 s, lalu 75. Tanpa indikator memuat.
- **Aturan:** B4 §3.10 ("jangan menampilkan kosong saat masih memuat"), INV-UI-03.
- **Dampak:** sales/admin bisa membuat pelanggan ganda karena layar menyatakan belum ada pelanggan; angka 0 dibaca sebagai
  fakta.
- **Rekomendasi:** status `loading` eksplisit (skeleton) di semua daftar/KPI; `PaginationBar` tidak menulis "Tidak ada …"
  saat `loading`; placeholder pemilih pelanggan "Memuat pelanggan…".
- **Status:** **terverifikasi** (W1–W13).

### UI-51 — Beban muat: `loadAll` berjalan 3× per buka halaman (≈ 1 MB dashboard tiap kali); layar Pengaturan 10–13 s
- **Area/layar:** semua layar desktop (kerangka aplikasi). **Klasifikasi:** kinerja · **Keparahan:** P3 · **terukur di dev
  server — produksi perlu diukur ulang**.
- **Bukti:** membuka Master Grade Mutu (admin) = **54 panggilan API** dalam 9 s; 19 endpoint dipanggil ≥ 2× — `/dashboard`,
  `/wms/tasks`, `/inventory/movements`, `/users`, `/permissions`, `/audit-logs`, `/notifications`, … masing-masing **3×**.
  `/dashboard?entity_id=ent_ksc` = **995 KB, 2,8 s** per panggilan. `loadAll` bergantung pada `[user?.role,
  selectedEntity]` dan efeknya pada `[loadAll, user]` (`hooks/useAppActions.js:144-243`) — objek `user` disegarkan
  `/auth/me` dan PT dari alamat diterapkan sesudah render pertama; StrictMode dev menggandakan efek (`index.js:69`).
  Waktu siap terukur: Aturan Gudang & Mutu **10,4–13,4 s**, Status Stok 8–11 s, Lokasi Rak 12–21 s (UI-46).
- **Dampak:** di HP/jaringan gudang, tiap pindah layar menarik ±3 MB yang tidak dipakai layar itu.
- **Rekomendasi:** ukur di build produksi; `loadAll` hanya saat login/ganti PT, kunci efek ke `user.id`; data dasbor dimuat
  oleh layar yang memakainya.
- **Status:** terukur (dev); kandidat untuk produksi.

### UI-52 — Target sentuh di bawah minimum: 20 dari 37 layar desktop punya tombol < 24 px; aksi keputusan HP 36 px
- **Area/layar:** lihat tabel §0.2 & §0.3. **Peran:** semua. **Ukuran:** keduanya.
- **Klasifikasi:** inkonsistensi (aksesibilitas) · **Keparahan:** P2 · **memperluas UI-24/UI-28, FRM-17**.
- **Bukti (terukur `getBoundingClientRect`):** desktop — Data Gudang tombol **Hapus lokasi 11 × 11 px** (merah, di samping
  3 `TEST_SITE`, **tanpa konfirmasi** — `WarehouseMasterView.jsx:205-208, 240`); detail GRN tombol "Kembali" **16 × 16**
  (`wms/grn/GrnDetail.jsx:51`); Penerimaan & OCR tombol setinggi **13 px**; Aturan Gudang & Mutu **53** tombol < 24 px;
  SPK Inspeksi 25; Order Makloon 25; Lot & Silsilah 20; PR 18. HP — Persetujuan manajer **Setujui 153 × 36 / Tolak 151 ×
  36**, "Buka layar lengkap" **122 × 18**; MD "Muat ulang" **15 × 15**; "Kembali ke aplikasi HP" **169 × 32**; Pintasan
  322 × 36; chip PT 36; lonceng 36 × 36; sub-tab Pindai 38; tombol Pindai 44.
- **Aturan:** B4 §3.3 (desktop ≥ 24 × 24, HP ≥ 48 × 48, aksi utama HP 56 px); WCAG 2.5.8 (AA) / 2.5.5; KN_08 §Mobile (44 px).
- **Dampak:** salah ketuk pada aksi merusak/keputusan (hapus lokasi tanpa konfirmasi; Setujui/Tolak harga) — pola "Error
  Prevention" B3b FRM-14.
- **Rekomendasi:** varian tombol baku `sm` (≥ 24 px desktop) dan `touch` (≥ 48 px HP); larang ikon-tombol tanpa padding;
  ratchet guardrail ukuran minimum; hapus lokasi lewat `askConfirm`.
- **Status:** **terverifikasi** (ukur).

### UI-53 — Huruf HP: 75–90 % teks aplikasi HP gudang < 14 px, terkecil 9 px
- **Area/layar:** `MobileWarehouseApp` (Masuk, Keluar, Sample, Pindai, Lainnya), `MobileOpsApp`, `MobileMdApp`.
  **Peran:** warehouse, warehouse_admin, manager, finance, md. **Ukuran:** HP 390 & 360.
- **Klasifikasi:** inkonsistensi · **Keparahan:** P2 · **memperluas UI-26 ke HP dengan patokan B4**.
- **Bukti:** gudang Jakarta: teks < 14 px Masuk **75 %**, Keluar 75 %, Sample 77 %, Pindai **89 %**, Lainnya 90 %; huruf min
  **9 px** di semua tab; jumlah/teks kartu `text-xs` (`features/mobile/MobileWarehouseApp.jsx:72, 96-98`). Manajer:
  Persetujuan 96 % < 14 px; MD Stok & ATP satuan "kg" **10 px**. Isian pindai sudah 16 px (lolos).
- **Aturan:** B4 §3.2a (HP: info keputusan ≥ 16 px, pendukung ≥ 14 px); KN_08 §Mobile ("Larger font sizes for scanning UI
  (16px+)").
- **Dampak:** di lantai gudang (sarung tangan, cahaya terang, jarak lengan) nomor PO/qty/lokasi sulit dibaca.
- **Rekomendasi:** token `fs-16` untuk qty/nomor/lokasi di kartu HP, `fs-14` pendukung; ratchet per berkas `features/mobile`.
- **Status:** terukur (W4, W15).

### UI-54 — HP Masuk: "30 terbuka" menghitung tugas Menunggu QC & Ditolak QC yang tidak bisa diterima
- **Area/layar:** HP gudang › Masuk. **Peran:** warehouse, warehouse_admin. **Ukuran:** HP.
- **Klasifikasi:** hambatan UX · **Keparahan:** P2 · **memperluas UI-08**.
- **Bukti:** gudang Jakarta "30 terbuka" = Menunggu Barang **13**, Menunggu QC **13**, Ditolak QC **4**; kartu Ditolak QC
  hanya "Cetak ulang label QR roll"; ketiga status berpil oranye sama `rgba(255,149,0,.1)`. Penyaring hanya membuang
  `completed/shipped/cancelled/done/dispatched` (`MobileWarehouseApp.jsx:49`), label jumlah `:72`, pil `:97`.
- **Dampak:** 57 % kartu "terbuka" bukan pekerjaan petugas; yang benar-benar perlu diterima tenggelam.
- **Rekomendasi:** pisahkan "Perlu diterima" dari "Menunggu QC/ditolak" (chip atau seksi), warna status per tahap (B4 §3.9).
- **Status:** **terverifikasi** (W4).

### UI-55 — Layar RFID tidak sadar lokasi/PT akun: petugas Soreang melihat gate & riwayat Jakarta/uji; kode perangkat sebagai nama
- **Area/layar:** RFID › Lokasi RFID, Tag RFID, Monitor Gerbang, Tag RFID › Antrean Printer (PREP-F). **Peran:** warehouse
  (Soreang, Jakarta, Rancamalang), warehouse_admin. **Ukuran:** desktop & HP.
- **Klasifikasi:** inkonsistensi cakupan · **Keparahan:** P2 · **verifikasi visual UI-02 untuk RFID**.
- **Bukti:** semua layar RFID bawaan "**Semua Gudang**" untuk akun berlokasi; petugas **Soreang (PT Kanda)** di Monitor
  Gerbang melihat pemilih gate "**DEV-84134 · KELUAR · Jakarta · Gudang Sukacita**" dan riwayat "UJI-CELUP gate-out",
  KPI "Gerbang Aktif 1"; Lokasi RFID Jakarta "Total Tag 35" sama dengan admin. Koleksi RFID tidak termasuk pembatasan
  lokasi (`backend/services/location_scope.py:20-28`). Kode perangkat `DEV-84134` dipakai sebagai nama gate. Antrean
  Printer: "Belum ada printer label terdaftar **di gudang ini**" saat pemilih = Semua Gudang
  (`features/rfid/PrinterQueuePanel.jsx:40`). Istilah Inggris di Alarm & Keamanan: "RED READS", "ROLL GATE EXCEPTION",
  "Di-ack", "Shrinkage", "Drift", "Riwayat Passage Gate" (UI-32).
- **Dampak:** petugas gedung tanpa gate (Jakarta) atau gedung lain dapat "mensimulasikan" bacaan di gate gedung lain;
  angka RFID tidak bisa dibaca sebagai "gedung saya".
- **Rekomendasi:** bawaan pemilih gudang = lokasi akun (B4 §3.4 ScopeBar); gate & printer disaring per lokasi; nama gate
  manusiawi; kalimat kosong mengikuti saringan.
- **Status:** **terverifikasi** (W4–W6, W1).

### UI-56 — Meja Pengemudi: "Kiriman hari ini 66" padahal Pengiriman "0 tujuan aktif"; sopir melihat 89 SO berikut nilai Rupiah
- **Area/layar:** Meja Saya (Meja Pengemudi) vs Pengiriman. **Peran:** driver. **Ukuran:** desktop.
- **Klasifikasi:** bug angka + paparan data · **Keparahan:** P2.
- **Bukti:** Meja Pengemudi "PERLU DITINDAK **66** · Kiriman hari ini · 66 dokumen · Tertua: —"; Pengiriman (peran yang
  sama, sesaat kemudian) "Tugas Saya Hari Ini · **0** tujuan aktif · Tidak ada pengiriman aktif yang ditugaskan kepada
  Anda." Penyebab: antrean meja memasukkan Surat Jalan **tanpa sopir** (`not s.get("driver_id")`) sebagai milik setiap sopir
  (`backend/services/role_desk_service.py:204-216`, baris `:211`). Meja yang sama memuat "Pelacak SO aktif 89" dengan
  kolom **NILAI Rp 1.110.000** dan SO uji `TEST/SO-…`.
- **Dampak:** sopir melihat 66 "kiriman" yang bukan tugasnya; nilai jual tampil ke peran yang izinnya hanya logistik
  (`backend/permissions_config.py:547-550`).
- **Rekomendasi:** antrean sopir = pengiriman dengan `driver_id` = sopir (SJ tanpa sopir → meja Admin Gudang); pelacak SO
  tidak dipasang di meja sopir atau tanpa kolom nilai.
- **Status:** **terverifikasi** (W14).

### UI-57 — Manajer di Pengaturan › Perangkat hanya melihat "Mesin absen": operasional gate U300 khusus admin
- **Area/layar:** Pengaturan › Integrasi & Sistem › Perangkat. **Peran:** manager (dan Admin Gudang tanpa menu — UI-21).
- **Klasifikasi:** butuh keputusan · **Keparahan:** P2 · **koreksi & perluasan UI-20/UI-21**.
- **Bukti:** manajer: tab tunggal "Mesin absen" (ZKTeco), **tidak ada** tab "RFID (pembaca/gerbang)"; tab RFID dipagari
  `roleCanSee(["admin"], role, "cs-rfid-devices")` (`frontend/src/features/settings/devices/DevicesView.jsx:21-27, 42`).
  Jadi kesehatan reader, kunci gate, sesi dokumen & riwayat lintasan (`U300Operations`) hanya bisa dibuka admin — padahal
  teks layar menyebut "Admin Gudang / Manajer" sebagai pembuka kunci (`U300Operations.jsx:32`). B1 UI-21 menulis
  Perangkat = admin & manajer; untuk RFID yang benar **admin saja**.
- **Dampak:** di operasional harian tidak ada pemegang peran gudang/manajer yang bisa membuka kunci gate dari layar
  operasional gate.
- **Rekomendasi:** sama dengan K-B1-07 — operasional gate pindah ke RFID › Monitor Gerbang untuk Admin Gudang & manajer.
- **Status:** **terverifikasi** (W2).

### UI-58 — Nomor dokumen dua skema: sebagian tanpa prefiks PT
- **Area/layar:** Retur ke Supplier (`PRET-00070`), Retur Pelanggan (`SRET-00167`), Permintaan Pembelian (`PR-00209`),
  Klaim Makloon lama (`MKO-00004`) vs `KSC/PO-00166`, `KSC/SO-00001`, `KSC/MKO-00082`, `KSC/GRN-00023`. **Peran:** semua.
- **Klasifikasi:** inkonsistensi / butuh keputusan · **Keparahan:** P3.
- **Bukti:** `next_doc_number(..., "PR-", scheme="shared")` (`backend/services/purchase_requisition_service.py:33`),
  `"PRET-"` (`purchase_return_service.py:32`), `"SRET-"` (`return_service.py:148`) — skema grup tanpa prefiks PT;
  dokumen lain per PT. Di satu baris tampil "SRET-00167 · KSC/SO-00001".
- **Dampak:** dari nomor saja tidak tahu PT pemilik; pencarian "KSC/" tidak menemukan retur/PR PT itu.
- **Rekomendasi:** putuskan satu skema (prefiks PT untuk semua dokumen transaksi) atau tampilkan chip PT di samping nomor.
- **Status:** **terverifikasi** (data + kode).

### UI-59 — Jumlah roll tanpa pemisah ribuan di tiga layar
- **Bukti:** Lot & Silsilah "ROLL DALAM LOT **23368**" (`features/inventory/lots/LotParts.jsx:15`); Lokasi Rak "Terisi di Rak
  **18482** roll", "Belum Ditempatkan **4700** roll" (`wms/LocationPutawayView.jsx:128-130`); Master Grade "Roll memakai
  **44905**" (`settings/masters/GradeMasterView.jsx:40`) — sementara POS "23.167 roll", Tag RFID "5.000+".
- **Aturan:** B4 §3.2a (pemisah ribuan gaya Indonesia, `formatQty`). **Klasifikasi:** inkonsistensi · **Keparahan:** P3.
- **Status:** **terverifikasi**.

### UI-60 — Pola detail campur: SPK = pop-up; GRN, Retur, Order Makloon = halaman sebaris; aksi merusak di kepala
- **Bukti:** SPK Inspeksi membuka `DetailModal` (dialog, tutup Esc). GRN, Retur Pelanggan, Order Makloon mengganti isi
  halaman dengan detail sebaris: tombol kembali GRN ikon **16 × 16** (`GrnDetail.jsx:51`) vs bilah "Kembali ke Daftar …"
  **749 × 32** (Retur, Makloon). "Batalkan Pesanan" (Makloon) dan "Tolak" (Retur) diletakkan bersebelahan dengan "Tanya KN"
  di kepala detail, sebelum aksi utama; istilah "Issue ke Makloon".
- **Aturan:** B4 §3.7 (satu pola object page/drawer), §3.3 (aksi merusak dijauhkan). **Klasifikasi:** inkonsistensi ·
  **Keparahan:** P3.
- **Status:** **terverifikasi**.

### UI-61 — Produk & Varian: "n induk produk · katalog bersama" berbeda per peran tanpa keterangan
- **Bukti:** PT Sukacita, saringan bawaan sama: admin **75**, manager **70**, Admin Sales **70**, sales **64** induk
  produk (`catalog/CatalogWorkspace.jsx:61`). Tidak ada teks yang menjelaskan mengapa sebagian tidak tampil (kemungkinan
  tahap R&D/lifecycle per izin).
- **Klasifikasi:** inkonsistensi (perlu konfirmasi aturan) · **Keparahan:** P3. **Status:** kandidat (angka terverifikasi,
  penyebab belum ditelusuri).

---

## 2. Kandidat B1 & butir B3b "→ B1": terkonfirmasi / gugur

| Butir | Status sebelum | Hasil B1b | Bukti |
|---|---|---|---|
| **UI-07** stok di ≥ 8 layar beda rumus | kandidat | **terverifikasi** | PT Sukacita: Operasi Gudang Tersedia 60.616,43 kg (wh Jkt) · Multi-Bucket 61.071,16 (adm) / 60.616,43 (wh Jkt) · Status Stok 60.996,16 (adm) / **387.487,6** (gudang/sales) · POS 60.996,16 · Lot "Sisa dalam lot" 61.297,96 · Lokasi Rak per gedung 199.432,59 + 50.575,5 kg — 6 nilai di 7 layar (UI-45) |
| **UI-08** HP Keluar tanpa jenis/warna | terverifikasi sebagian | diperkuat | Jakarta: pil semua oranye termasuk "Ditolak QC"; Masuk mencampur status QC (UI-54) |
| **UI-09** keluar tersebar 6 menu | kandidat | **terverifikasi** | sidebar & layar wh Jakarta: Barang Keluar, Cutting, Transfer (Operasi Gudang), Order Makloon, Perbaikan, Retur ke Supplier, Antar Entitas — semuanya dikunjungi, tidak ada antrean bersama |
| **UI-13** HP Masuk mode GRN = tautan `href` | kandidat | **tetap kandidat** (tak terjangkau dengan data sekarang) | PT Sukacita (Jakarta) memakai mode lama (kartu "Terima" qty, 312 × 54) **bersamaan** dengan kartu "Kedatangan Barang" GRN di atasnya; Kanda/CST: tab Masuk kosong |
| **UI-15** urut kolom | kandidat | **terverifikasi** | kolom bisa diurut hanya di Pengiriman (tab daftar, sopir: 5 kolom); 0 di 36 layar lain |
| **UI-25** id mentah | kandidat | **sebagian gugur** | pola `ent_/site_/wh_/bin_/prod_/uuid` = **0** kecocokan di teks 37 layar desktop & aplikasi HP; yang tersisa: kode perangkat `DEV-84134` sebagai nama gate (UI-55), id PT di alamat (`?entity=ent_82b52ed6ee8b`) |
| **UI-31** tabel mentah di 390 px | kandidat | **terverifikasi dengan koreksi** | 14 layar punya tabel lebih lebar dari 390 px, tetapi bergulir di wadahnya — dokumen **tidak** bergeser mendatar di 36 layar (lebih ringan dari dugaan "terpotong") |
| **UI-34** petugas gudang melihat menu di luar pekerjaan | kandidat | **terverifikasi** | sidebar warehouse: Pengadaan, Pesanan Pembelian, Hutang Pemasok, R&D, Antar Entitas (Grup), Kas & Aset; isi: Kontrabon (Rp, "GR belum ditagih"), Antar Entitas (piutang/utang Rp), Kinerja Mitra Makloon (nilai klaim Rp) |
| **UI-35** tab Master Grade untuk md/mdq/qc tak pernah berlaku | kandidat | **terverifikasi** | `?view=grade-master` dialihkan: md → Meja MD, md_quality & qc → SPK Inspeksi |
| **UI-37** HP QC | terverifikasi (koreksi) | berlaku juga untuk **MD Quality** | mdquality di HP mendarat di SPK desktop 390, tanpa tab aplikasi |
| **UI-21** Perangkat = admin & manajer | terverifikasi | **dikoreksi** | tab RFID hanya admin; manajer hanya "Mesin absen" (UI-57) |
| **UI-42** 2108 vs 14 | terverifikasi | **penyebab ditemukan** | KPI per gedung semua PT, antrean per PT aktif + batas 500 (UI-46) |
| **UI-05** data uji | terverifikasi | **diperluas** | data uji di 13 layar: Retur Pelanggan (`TEST_RET-…/TEST_SO-…`), PR (`TEST LN033`, gudang `TEST_WH`), Produk (`TEST_catalog_family_…`), Analitik Stok (`TEST_iter4_SKU…`), Kinerja/Klaim Makloon (`TEST_L01`, `TEST_iter280`), Lot (`UJI-CELUP-1..3`), Data Gudang (3 `TEST_SITE` — dengan tombol hapus), Meja (SO `TEST/SO-…`, pelanggan `Test_pelanggan_…`); daftar PT manajer di desktop juga memuat 3 PT "Uji Provisioning" (HP tidak); pemilih gudang Operasi Gudang memuat gudang lama tanpa lokasi ("Gudang Bandung Kopo", "Gudang Surabaya Rungkut", "Gudang Utama Sukacita/Kanda") |
| **FRM-04** paritas HP | terverifikasi kode | **terverifikasi visual** | tab HP gudang tetap Masuk/Keluar/Sample/Pindai/Lainnya (Jakarta, whadmin); Daftar Awal: "Admin gudang membuat & memulai sesi di desktop"; tanpa putaway/transfer/opname/cek muat |
| **FRM-14** aksi destruktif tanpa konfirmasi | terverifikasi kode | **terverifikasi sebagian** | "Hapus lokasi" 11 × 11 tampil untuk 3 lokasi (tanpa `askConfirm`, `WarehouseMasterView.jsx:205-208`) — tidak ditekan. Tutup Penerimaan, Buang BS, Validasi & tutup (BTG), Ulangi transaksi: tidak terjangkau tanpa membuat data uji (antrean periksa gate kosong, GRN terbuka 0) → tetap kandidat |
| **FRM-15** draf GRN ganda | kandidat UI | **tidak diuji** | butuh menekan "Buat" (menyimpan) — di luar batas audit |
| **FRM-16** 422 dirender objek | kandidat UI | **tidak diuji** | butuh mengirim form ke server |
| **FRM-17** ukuran piksel tombol/isian | terverifikasi kode | **terverifikasi** | desktop: tombol 11–38 px, 20/37 layar < 24 px; isian 30–36 px, huruf isian 11–14 px; HP: isian pindai 56/16 px, tab bawah 56, sub-tab 38, lonceng 36, Setujui/Tolak 36 (UI-52) |
| **FRM-18** pemilih grade kosong untuk akun gudang | terverifikasi kode | **terverifikasi (API)** | warehouse: `GET /api/master/grades` → 403 "Permission ditolak: grade_master.view" (izin `qc: view, inspect` ada) → pemilih `[]`; modal pemilih sendiri tidak dibuka karena tidak ada SPK QC 4-point terbuka (membuatnya = menyimpan) |
| **LST-06** kosong palsu saat memuat | terverifikasi kode | **terverifikasi** | 9 layar (UI-50) |

**Rekap:** 13 terkonfirmasi/diperkuat (UI-07, 08, 09, 15, 31, 34, 35, 37-mdq, FRM-04, FRM-17, FRM-18, LST-06, UI-05
diperluas), 2 dikoreksi (UI-21, UI-42 → penyebab), 1 sebagian gugur (UI-25), 1 sebagian terverifikasi (FRM-14),
tetap kandidat 3 (UI-13, FRM-15, FRM-16 — butuh data/menyimpan).

## 3. Pola kesalahan (lanjutan §3 B1 — nomor 16 dst.)

| # | Pola | Jumlah / contoh | Temuan |
|---|---|---|---|
| 16 | **Menu tampil, server menolak** (menu dari daftar peran, bukan izin efektif) — dua wujud: galat mentah *atau* kosong palsu | manajer › Pengiriman (galat mentah), Meja Saya wha/sla (galat + 0), finance › Skor mitra (kosong), warehouse › pemilih grade (kosong), sopir › aplikasi HP gudang (B1 UI-23) | UI-47, 48, 49 |
| 17 | **Label cakupan tidak sesuai angka** | "Konteks: Kanda" di atas angka grup; KPI Lokasi Rak per gedung vs antrean per PT; papan ACC "semua gudang" di atas stok lokasi; Meja Pengemudi 66 vs 0 | UI-45, 46, 56, (UI-04) |
| 18 | **Kosong/nol palsu saat memuat** | 9 layar, termasuk POS "Belum ada pelanggan — buat pelanggan baru" | UI-50 |
| 19 | **Batas senyap muncul di layar lain** | Lokasi Rak 500 (B1: GRN 100, tag 1.000, belum tag 500, Barang Keluar 200) | UI-46 |
| 20 | **Target sentuh di bawah minimum standar** | 20/37 layar desktop < 24 px, terkecil 11 px (tombol hapus); HP aksi keputusan 36 px, "Muat ulang" 15 px | UI-52 |
| 21 | **Kontrol daftar tiga gaya** | pager: `PaginationBar` "Menampilkan…", RFID "Halaman 1/2", katalog "Sebelumnya 1/1 Berikutnya"; ekspor 6/37 (5 CSV + 1 Excel); urut 1/37 | UI-15, 30 (B1), 52 |
| 22 | **Pola detail campur** | dialog vs halaman sebaris; tombol kembali 16 px vs bilah 749 px; aksi merusak di kepala | UI-60 |
| 23 | **Format angka/nomor tak seragam** | ribuan tanpa titik di 3 layar; nomor dokumen dua skema | UI-58, 59 |
| 24 | **Konteks sesi bocor dua lapis** | PT terbawa (UI-39) + sesi server tidak diakhiri & cookie mengalahkan token | UI-39, 44 |
| 25 | **Data uji di layar kerja** (diperluas) | 13 layar; 3 `TEST_SITE` lengkap dengan tombol hapus | UI-05 |

## 4. Koreksi atas B1 & matriks

1. Sel B1 yang benar-benar dikunjungi = **15 desktop + 3 HP** sel tampil (laporan B1 menulis 16 + 2; dua sel `–(V)` bukan
   sel tampil, dan sel HP sopir/QC/sales ada 3).
2. Lebar desktop = **1024 px** (judul matriks B1 "1440 px" keliru).
3. Legenda `K·p` B1 terlalu luas: `MobileOpsApp` hanya punya **Pintasan** untuk admin/manajer/md (4 layar: Produk & Varian,
   Kedatangan Barang, Order Makloon, SPK bila berizin QC — `features/mobile/MobileOpsApp.jsx:197-210`); finance &
   sample_admin tidak punya Pintasan. Sebaliknya `MobileSalesApp` punya "Layar lengkap" (Operasi Gudang (pantau), Lot &
   Silsilah, Pengiriman, Produk & Varian, PR, Transaksi Antar-PT) — beberapa sel `K·d` Admin Sales sebenarnya punya pintu.
4. Sel **sales › Lot & Silsilah** tampil menurut tiruan kode tetapi di peramban dialihkan ke beranda dan Stok & ATP sales
   tanpa tab (izin server) → `–(V)`.
5. UI-21 (tab Perangkat RFID) & UI-42 (penyebab angka) dikoreksi — §2.

## 5. Jumlah klik & waktu tugas (tambahan §2b B1)

| Tugas | Desktop | HP | Catatan |
|---|---|---|---|
| Buka antrean penempatan rak (petugas berlokasi) | Lokasi Rak (2 klik) → **12–21 s** sampai siap; antrean tampil maks. 500 | Tampilan desktop: 17,5 s | UI-46 |
| Hapus lokasi gudang kosong | **1 klik** pada ikon 11 × 11, tanpa konfirmasi | – | tidak ditekan (UI-52, FRM-14) |
| Setujui harga khusus (manajer) | Pusat Persetujuan | tab Persetujuan (1) → Setujui (1) = **2**, tombol 36 px | UI-52 |
| Ganti PT di HP | pengalih header (2) | Lainnya (1) → chip PT 36 px (1) = **2** | chip HP tanpa PT uji |
| Lihat stok satu produk "di PT saya" (petugas) | Status Stok menampilkan angka grup → harus membuka baris rincian (≥ 3) | Pindai per roll | UI-45 |
| Cek apakah pengiriman ada untuk sopir | Meja (66) → Pengiriman (0) → bingung | aplikasi HP sopir galat (UI-23) | UI-56 |

## 6. Ringkasan

**Cakupan sel (37 baris menu × 12 peran, 166 sel tampil):**

| | Sebelum (B1) | Sesudah (B1b) |
|---|---:|---:|
| Desktop — sel tampil dikunjungi | 15 / 166 | **166 / 166** (115 `T:`, 50 `V`, 1 `–(V)` = sales › Lot & Silsilah dialihkan) + 5 sel di luar matriks kode dipastikan tidak tampil (`–(V)`: manajer › Lokasi RFID, Admin Gudang › Perangkat, md/mdq/qc › Master Grade) |
| HP — sel diukur langsung di 390 untuk peran itu | 3 / 166 | **51 / 166** (37 lewat Tampilan desktop `T·d`, 14 dalam aplikasi/tampilan penuh `T:`) |
| HP — jalur dipastikan di aplikasi HP peran itu, tata letak 390 diukur pada peran lain | 0 | **114** (`d(V)` 98 tanpa pintu · `p(V)` 16 ada pintu) + 1 `–(V)` |
| Layar yang tata letak 390-nya diukur minimal sekali | – | **36 / 37** (kecuali Meja Gudang) |

Ditambah: 6 aplikasi HP dikunjungi ulang/baru (gudang Jakarta & whadmin, Ops manajer/finance/sample_admin, Sales Admin
Sales & sales, MD; MD Quality tanpa aplikasi), layar pindai di 360 × 780, 4 pop-up/detail, tab baru Antrean Printer
(PREP-F), 16 akun (15 + whadmin).

**Temuan baru: 18** (UI-44 … UI-61) — **P0 0 · P1 3** (UI-44 sesi tidak diakhiri, UI-45 angka grup berlabel PT, UI-46
antrean rak terpotong & beda cakupan) · **P2 10** (UI-47–50, 52–57) · **P3 5** (UI-51, 58–61). Terverifikasi di peramban
15, terukur 2 (UI-51 di dev server, UI-53), kandidat 1 (UI-61).

| Klasifikasi | Temuan |
|---|---|
| bug | UI-44, 46, 47, 48, 49, 50, 56 |
| inkonsistensi | UI-45, 52, 53, 55, 59, 60, 61 |
| hambatan UX | UI-54 |
| butuh keputusan | UI-57, 58 |
| kinerja | UI-51 (dan bagian UI-46) |

**Kandidat B1/B3b:** 13 terkonfirmasi/diperkuat, 2 dikoreksi, 1 sebagian gugur (UI-25), 1 sebagian (FRM-14), 3 tetap
kandidat (UI-13, FRM-15, FRM-16 — butuh data/menyimpan, di luar batas audit).

**Pola baru (§3 no. 16–25):** menu tampil tetapi server menolak (galat mentah atau kosong palsu); label cakupan tidak
sesuai angka; kosong/nol palsu saat memuat; batas senyap di layar baru; target sentuh < minimum; kontrol daftar tiga gaya;
pola detail campur; format angka/nomor tak seragam; konteks sesi bocor dua lapis; data uji meluas.

**Butuh keputusan pemilik (tambahan K-B1):** K-B1-11 skema nomor dokumen (prefiks PT untuk PR/PRET/SRET? — UI-58);
K-B1-12 apakah angka grup boleh tampil untuk peran gudang dan dengan label apa (UI-45, melengkapi K-B1-03); K-B1-07
diperkuat oleh UI-57 (tidak ada peran operasional yang bisa membuka kunci gate).
