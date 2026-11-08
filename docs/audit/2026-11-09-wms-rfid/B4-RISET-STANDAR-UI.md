# B4 — Riset UI/UX & elemen UI WMS/RFID profesional → usulan "Standar UI Gudang v1"

| | |
|---|---|
| Paket | B4 (audit WMS/RFID 9 Nov 2026) — **riset + analisis**, tidak ada perubahan kode aplikasi |
| Baseline kode | `70eb9fd` (HEAD worktree saat riset) |
| Tanggal akses sumber | 2026-11-09 (semua URL di §4) |
| Penulis | Claude Code (implementer), atas permintaan koordinator |
| Status usulan | **Draf untuk keputusan pemilik** (§5). Belum mengikat; belum ada guardrail yang dipasang |

**Cara membaca**

* `[KODE]` = sitasi ke daftar sumber §4. Tanda **†** = fakta hanya dari cuplikan hasil pencarian (halaman primer
  menolak dibuka: 403/PDF biner/JS) — **cek ulang sebelum dijadikan kontrak**.
* **Inferensi:** = analisis/penerapan saya, bukan klaim sumber.
* **KN:** = bukti di repo pada `70eb9fd` (berkas:baris). Angka "terukur" di §2 saya hitung ulang sendiri.
* Istilah antarmuka dikutip apa adanya dari `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` dan layar yang ada
  (**K-13: istilah tidak diubah**). Laporan ini tidak mengusulkan penggantian istilah; bila ada dua istilah untuk
  satu konsep, itu dicatat sebagai butir keputusan (§5), bukan diganti.

---

## 0. Ringkasan eksekutif

### 0.1 Sepuluh pola terpenting dari produk profesional

| # | Pola | Bukti utama |
|---|---|---|
| P1 | **Cakupan bawaan per pengguna** — satu gudang/PT bawaan + pindah cakupan secara eksplisit + cakupan selalu terlihat; "semua" bukan bawaan | D365 *Default warehouse* + aktivitas *Change warehouse* [MS2][MS1][MS3]; Odoo *Allowed/Default Company* + pemilih perusahaan [OD16][OD17]; tampilan tersimpan per *legal entity* [MS18] |
| P2 | **Angka stok bernama dan berumus**, dengan rincian per dimensi | D365: *Physical inventory − Physical reserved = Available physical*; *Total available = available physical + ordered in total − on order*; tombol *Dimensions* [MS15]; Odoo *On Hand / Free to Use / Incoming / Outgoing / Forecast* [OD10][OD11]; Zoho *Available for Sale = on hand − committed* [ZO1] |
| P3 | **Status stok = dimensi**, bukan kolom tambahan; stok berstatus blokir tetap dihitung fisik tetapi tidak bisa keluar | D365 *Inventory blocking* [MS16]; NetSuite inventory status [OR3]; SAP stok QC/blokir [SAP1][SAP2†] |
| P4 | **Menu per jenis tugas + pembatas jenis kerja**; mode "sistem mengarahkan tugas berikutnya" | D365 menu item mode *Work/Indirect*, *work class*, *Directed by* [MS1][MS13]; SAP EWM queue & interleaving [SAP5]; Infor interleaving [IN1] |
| P5 | **Satu input utama per langkah, konfirmasi dengan memindai** (lokasi → barang → jumlah) | D365 step ID/ikon/judul per langkah, *work confirmation* [MS7][MS1]; SAP *verification profile* [SAP4] |
| P6 | **Dokumen dulu, lalu pindai barisnya**; progres *x/y*; tiga kategori hasil: cocok / belum terbaca / di luar daftar | Odoo Barcode [OD1][OD2][OD3][OD5]; Zebra *Tag List Match* [ZB3†]; Checkpoint read-vs-expected [RF6†] |
| P7 | **Pengecualian terstruktur**: alasan wajib, tercatat, dibatasi izin per pekerja; selisih di atas ambang → review | D365 *Short pick* + *Work exceptions log*, izin override per pekerja, ambang opname [MS8][MS2][MS14] |
| P8 | **Hitung buta (blind count) sebagai bawaan** opname di HP | D365: angka harapan tidak pernah ditampilkan [MS14]; Odoo bisa disembunyikan [OD4] |
| P9 | **Daftar: saring → tampilan tersimpan → ekspor mengikuti saringan & kolom**; data besar diolah di server | D365 saved views + Export to Excel "persis seperti grid", batas bawaan 50.000 baris [MS18][MS19]; Fiori variant & export [FI8†][FI12†]; Zoho *Export Current View* [ZO2]; AG Grid SSRM [GR3] |
| P10 | **Status = warna + ikon/bentuk + teks**; target sentuh 44–48 px; **skala teks & tombol bisa diatur per pengguna/perangkat**; umpan balik bunyi/getar | Carbon status indicator [CB8]; WCAG 1.4.1 [W1]; Material 48 dp [MD3]; D365 *Text scale* 70–400 %, *Button scale* 50–200 %, bunyi/getar [MS4][MS5] |

Pola pendukung: offline-first (baca dari cache, tulis antre) [MD6][ZB8]; OCR menghasilkan **draf yang diperiksa
manusia** [OD24] dengan skor keyakinan per isian [MS23]; label kecil memakai **Data Matrix** (hemat tinggi) [GS8][GS11].

### 0.2 Inti usulan "Standar UI Gudang v1" (angka)

* **Huruf: 6 ukuran** — 12/16 · 13/18 · 14/20 · 16/24 · 20/28 · 24/32 px (+ 40 dan 64 khusus kios gate).
  **Minimum 12 px** di desktop; di HP info keputusan ≥ 16 px, pendukung ≥ 14 px. Angka selalu `tabular-nums`, rata kanan
  di tabel. (Sekarang: 21 ukuran, 8.863 pemakaian arbitrer, **76 % di bawah 12 px**.)
* **Spasi** 2 · 4 · 8 · 12 · 16 · 24 · 32 · 48 px. **Radius** 8 · 10 · 14 · 18 · 999 px (nilai KN sekarang, dibakukan).
* **Warna semantik** dengan kontras terhitung (WCAG AA): aksi `#0058CC` (6,43:1), hijau teks `#126E2C` (6,38:1),
  kuning teks `#8C4A00` (6,79:1), merah teks `#A8221A` (7,22:1), teks sekunder minimum `#6B6B73` (5,28:1),
  batas isian `#8A8A8E` (3,44:1). **Diganti**: isian tombol utama `#007AFF` (teks putih **4,02:1 — gagal AA**),
  tombol bahaya `#FF3B30` (**3,55:1 — gagal**), teks `#8E8E93`/`#9A9BA3` (3,26/2,77:1 — gagal).
* **Desktop (ringkas)**: tombol/isian 36 px (32 px kecil), baris tabel 36 px (32 rapat), target ≥ 24 × 24 px.
  **HP (nyaman)**: target ≥ 48 × 48 px dengan jarak ≥ 8 px; aksi utama/pindai **56 px**, lebar penuh, di bilah bawah;
  isian 48–56 px dengan teks 16 px. **Uji di 360 dan 390 px** (lebar CSS C72 belum diketahui — §1.9).
* **Halaman daftar**: Judul → **bilah cakupan** → ≤ 4 angka ringkas (roll dulu, lalu meter) → cari → chip saringan
  (+jumlah aktif, Reset) → urut/tampilan tersimpan → tabel (kepala lengket, kolom 1 = ID) → halaman 20/50/100/200 →
  **Ekspor Excel (bawaan) + CSV**, mengikuti saringan, urutan, kolom, dan cakupan; batas 50.000 baris per unduh;
  lembar "Info" berisi saringan & cakupan.
* **Aturan Dua Angka Stok**: setiap angka stok menyebut cakupannya — **angka A = cakupan kerja** (lokasi kerja + PT
  aktif) dan **angka B = total** — dalam **roll lalu panjang**; klik → rincian per lokasi, PT, status, dan barang akan datang.
* **Layar tugas HP**: satu tugas per layar, isian pindai selalu fokus (pemindai fisik utama, kamera cadangan),
  sesi **per dokumen** dengan progres *x/y roll · m*, hasil **ikon + judul + teks + bunyi/getar**, pengecualian lewat
  menu dengan alasan, selesai dengan selisih → kuning (bukan kunci).
* **Label 70 × 22 mm**: Data Matrix 18 × 18 modul @ 0,5 mm (≈ 10 mm persegi termasuk zona sepi) + nomor roll ≥ 3 mm;
  template ZPL sekarang (4 × 2") **tidak muat** dan harus dibuat ulang.

### 0.3 Butir keputusan (rinci + rekomendasi di §5)
K-B4-01 status standar · K-B4-02 skala huruf · K-B4-03 warna aksi · K-B4-04 lebar acuan HP / ukur C72 ·
K-B4-05 arti "angka total" · K-B4-06 kosakata stok di komponen baru · K-B4-07 ekspor Excel · K-B4-08 hitung buta
opname HP · K-B4-09 jenis tugas di HP · K-B4-10 label 70 × 22 · K-B4-11 tanda wajib · K-B4-12 tampilan tersimpan.

### 0.4 Metode & batasan
* Empat alur riset paralel (WMS; RFID/perangkat/label; sistem desain/WCAG/riset UX; inventori kain/data besar/ekspor),
  hanya **WebSearch/WebFetch** (tanpa alat peramban — dipakai paket B1). Fakta kunci perangkat saya verifikasi ulang
  langsung: Chainway C72 [CW1] dan CP30 [CW3] (dibaca 9 Nov), Zebra Tag List Match [ZB3†], Odoo digitization [OD24],
  AI Builder [MS23], NN/g beban kognitif [NN13].
* Batasan sumber: `sap.com/design-system` menolak semua pengambilan (403) → angka Fiori bertanda †; `m3.material.io`
  dirender JS → Material memakai token resmi kode sumber androidx [MD1][MD2] dan halaman Android [MD3][MD4]; PDF GS1
  tidak terbaca → angka GS1 sebagian †; **Manhattan, Blue Yonder, Körber tidak punya dokumentasi produk publik** →
  hanya klaim pemasaran [VN1†][VN2†][VN3†], tidak dipakai sebagai dasar pola; teks ASTM D5430 berbayar → hanya abstrak.
* Kode KN dibaca langsung: dokumen `KN_08`, `KN_14`, `KN_32`, `rfid/KEPUTUSAN_GATE_RFID.md`; komponen baku di
  `frontend/src/components/`; `tailwind.config.js`, `src/index.css`, `src/styles/*.css`; layar `features/wms/*`,
  `features/mobile/MobileWarehouseApp.jsx`, `features/rfid/*`; backend `routers/wms.py`, `services/location_scope.py`,
  `services/rfid_print_service.py`.

---

## 1. Temuan riset per pertanyaan pemilik

### 1.1 (1) Tugas & data sadar pengguna — cakupan kerja sebagai tampilan bawaan

**Fakta**
* D365: setiap akun pengguna perangkat gudang punya **Default warehouse** dan *Menu name* (menu akar); gudang tambahan
  bisa diberikan; pindah gudang lewat aktivitas *Change warehouse* [MS2][MS1]. Saat masuk, aplikasi memuat preferensi
  pekerja termasuk gudang bawaan [MS3].
* D365 *Display open work list* hanya menampilkan pekerjaan yang boleh diakses pekerja; kolom (*Field list*), jumlah
  baris, dan saringan per jenis transaksi bisa diatur [MS1].
* D365 saved views: tampilan bisa disematkan sebagai bawaan (*Pin as default*), dibuat spesifik per *legal entity*, dan
  dipublikasikan ke peran keamanan + legal entity (terkunci) [MS18].
* Odoo: pengguna punya **Allowed Companies** (boleh banyak) dan **Default Company** (satu, konteks saat masuk); pemilih
  perusahaan di kepala layar memakai kotak centang [OD16][OD17]. Gudang bawaan per pengguna ada di preferensi (dokumen
  v16; keberlakuan di v18 tidak terverifikasi) [OD18].
* Oracle WMS Cloud: *RF Execute Task* bisa mewajibkan pindai lokasi dulu sehingga hanya tugas di lokasi itu yang tampil [OR1].
* Fiori variant management: hanya satu tampilan bawaan; tampilan bisa "terapkan otomatis" [FI8†].

**Inferensi.** Pola industri yang konsisten: (a) cakupan bawaan = **satu** gudang/site + PT aktif, (b) perpindahan
cakupan adalah **aksi eksplisit** (bukan saringan yang dilupakan), (c) cakupan aktif **selalu terlihat**, (d) tampilan
tersimpan bisa dibagikan per peran **dan** per PT. "Semua gudang/PT tercampur" tidak pernah menjadi bawaan pekerja
gudang; ia hanya dipilih secara sadar (supervisor/manajer).

### 1.2 (2) Angka stok — dua angka, rincian saat diklik

**Fakta**
* D365 *Inventory on-hand list* memisahkan: *Physical inventory*, *Physical reserved*, *Available physical*
  (= fisik − dipesan fisik), *Ordered in total* (masuk), *On order* (keluar), *Available for reservation*,
  *Total available* (= available physical + ordered in total − on order). Tombol **Dimensions** memilih rincian
  (site/gudang/lokasi/batch/status/license plate) dan bisa disimpan; saringan di panel bekerja **sebelum** agregasi,
  saringan di grid **sesudah**; ada tampilan *intercompany on-hand* [MS15].
* D365 *inventory status* adalah dimensi penyimpanan; opsi *Inventory blocking* membuat stok tetap terhitung fisik
  tetapi tidak bisa dipakai untuk pesanan keluar; status bawaan bisa per site/gudang/barang [MS16].
* Odoo stock report: *On Hand*, *Free to Use*, *Incoming*, *Outgoing*, dikelompokkan per gudang, tombol *Locations* per
  baris, dan *Forecast* [OD10]; laporan forecast: On Hand, Incoming, Outgoing, Forecasted [OD11].
* Zoho: dua mode stok (akuntansi vs fisik), masing-masing *Stock on Hand*, *Committed Stock*, *Available for Sale*
  (= on hand − committed) [ZO1].
* NetSuite: status yang tidak "tersedia untuk dikomit" mengurangi *available* tetapi tetap dihitung *on hand*; saldo per
  status/bin/lot terlihat di pencarian saldo [OR3].
* SAP: stok *unrestricted*, *quality inspection*, *blocked* (dua terakhir tidak tersedia untuk diambil) [SAP1]; app
  *Stock – Single Material* menampilkan stok per plant/lokasi simpan dengan kolom stok yang bisa diatur [SAP6].
* Oracle WMS Cloud: *lock code* di tingkat LPN/batch dengan penanda *Allocatable* — status menentukan boleh-tidaknya
  dialokasikan, bukan angka terpisah [OR2].

**Inferensi.** Tidak satu pun produk menampilkan "angka stok" tanpa **nama** dan **rumus**. "Dua angka" keinginan
pemilik paling dekat dengan pasangan D365 *Available physical* (di sini, sekarang) vs *Total available* (termasuk masuk/
keluar), ditambah sumbu cakupan (gudang ini vs seluruh grup — D365 *intercompany on-hand*). Rinciannya selalu **pivot
per dimensi** (lokasi, pemilik, status, lot), bukan halaman lain.

### 1.3 (3) Jenis tugas dibedakan jelas

**Fakta**
* D365: setiap menu item punya mode *Indirect* (penelusuran: *Location inquiry*, *Item inquiry*, *License plate inquiry*,
  *Change warehouse*, *Reprint label*, *Display open work list*) atau *Work* (membuat/menjalankan kerja: penerimaan PO,
  *Movement*, *Quarantine*, *Spot cycle counting*) [MS1]. Akses jenis kerja dibatasi **work class** yang dipasang di
  menu item [MS1][MS13]; contoh menu *Outbound > Sales Picking* [MS8]. Pilihan *Directed by*: sistem, pengguna,
  pengelompokan, *Cluster picking*, *Cycle count grouping* [MS1]. *Work template* dibuat per jenis pesanan kerja [MS9].
* D365: setiap langkah punya **ikon dan judul langkah** sendiri [MS7].
* Odoo: setiap *operation type* punya kartu sendiri; memindai barcode transfer langsung membuka operasinya [OD5]; satu
  *wave* hanya boleh satu jenis operasi [OD9].
* SAP EWM: tugas RF diatur lewat *queue* dan urutan queue; interleaving hanya pada mode diarahkan sistem [SAP5]; layar
  RF standar 8 × 40 karakter dengan profil tampilan & verifikasi per proses [SAP3][SAP4]. Infor: *Round Robin Task
  Interleaving* antar jenis tugas (pick, putaway, cycle count, move) [IN1]. NetSuite WMS membedakan *Single Order* dan
  *Multi-Order Picking* (pilih wave) di menu [OR4†].
* Penempatan terarah: D365 *location directive* bertingkat dengan strategi seperti *Consolidate* lalu *Empty location
  with no incoming work* [MS10]; Odoo *putaway rules* per produk/kategori/jenis kemasan dengan sublokasi *Closest
  Location* [OD8]. Pengambilan gabungan: D365 *cluster picking* (per lokasi atau per posisi) [MS11], *wave template*
  [MS22†]; Odoo batch & cluster picking [OD23†].

**Inferensi.** Jenis tugas adalah **atribut kelas satu** (menentukan menu, izin, alur langkah, dan ikon), bukan teks
tambahan di kartu. Untuk KN: "keluar SO", "keluar sampel", "potong", "penempatan rak", "transfer", "stock opname", dan
"QC" masing-masing perlu jenis tugas sendiri dengan lencana (ikon + label + pita warna kategori) dan alur langkahnya.

### 1.4 (4) Alur QC, GRN, OCR yang konsisten

**Fakta**
* D365 quality check di dock: lolos/gagal per license plate; gagal → penempatan dialihkan ke lokasi inspeksi dan
  *quality order* dibuat. Di HP, layar quality check hanya tombol konfirmasi lolos; tolak lewat menu [MS13]. Pengambilan
  sampel QC (*Full license plate* / *Per nth license plate*) [MS17].
* Odoo: *Quality Control Point* pada operasi Receipts, per operasi/produk/kuantitas, frekuensi (semua/acak/periodik),
  jenis (lolos-gagal, ukur, foto) [OD14]; *Failure Locations*: jumlah gagal dipindah ke lokasi kegagalan, sisanya
  disimpan normal [OD15].
* SAP: saat GR stok masuk **stok QC** + *inspection lot*; *usage decision* memindah ke unrestricted (putaway) atau
  blocked [SAP7]. NetSuite: contoh status "Inspection" untuk barang menunggu QC [OR3].
* OCR: Odoo *document digitization* membuat **draf** tagihan; pengguna menyunting isian yang salah, mencocokkan ke PO,
  lalu konfirmasi; e-invoice XML disarankan karena lebih akurat [OD24]. Microsoft AI Builder mengembalikan **skor
  keyakinan 0–1 per isian dan per sel tabel** [MS23].
* Kain: ASTM D5430 menilai kain secara visual dan bisa dipakai untuk penerimaan per roll/pengiriman bila disepakati;
  abstrak tidak memuat ambang penerimaan [TX4]. Sistem 4 poin: 1–4 poin menurut panjang cacat (≤ 3"/≤ 75 mm = 1 …
  > 9" = 4), rumus poin per 100 yd² = poin × 36 × 100 / (lebar inci × panjang yard); ambang ±40 lazim tetapi
  ditetapkan pembeli [TX5][TX6] (sumber sekunder). Gray scale AATCC 5–1 dengan setengah langkah [TX7]; beda warna CMC
  ISO 105-J03 [TX8†].

**Inferensi.** Empat vendor memakai satu pola: **terima → stok berstatus QC (tidak tersedia) → keputusan per unit
(lolos/gagal + alasan) → pemindahan otomatis ke lokasi simpan atau lokasi QC/retur**. Di HP "lolos" satu ketukan, "gagal"
lewat menu + alasan. OCR = **draf + tanda ragu per isian + manusia menyetujui** — tidak pernah langsung jadi stok.
Konsistensi lintas QC/GRN/OCR berarti tiga hal sama di ketiganya: status yang sama (`Menunggu QC` → `Lolos`/`Ditolak`),
komponen keputusan yang sama, dan tanda "ragu" yang sama.

### 1.5 (5) RFID

**Fakta**
* Zebra 123RFID Mobile: *Rapid Read* (total baca, tag unik, laju, waktu), *Inventory*, *Locate Tag*, *Pre-Filters*,
  *Tag Write* (read/write, lock, kill) [ZB1]; profil bernama *Fastest Read*, *Cycle Count*, *Dense Readers*, *Optimal
  Battery*, *Balanced Performance*, *User Defined* [ZB2]. *Tag List Match*: daftar harapan dari CSV; **cocok hijau,
  hilang/diharapkan merah, tak dikenal abu-abu**; opsi tampil "Missed"/"Unknown" [ZB3†]. *Locate*: batang kedekatan
  0–100 % [ZB4†].
* Zebra DataWedge RFID: session S0–S3 (bawaan S1), saring duplikat, pre-filter (pola heksa, bank EPC/TID/User), post-
  filter jumlah tag dan ambang RSSI −100…0, mode pemicu [ZB5].
* Impinj: verifikasi item-level karton 60 item logam di terowongan konveyor (< 1,5 s per karton): akurasi rata-rata
  91,7 % → 99,8 % dengan Gen2X; 100 % pada 90 dari 100 putaran (uji vendor) [IM1]. Bacaan nyasar disebut masalah
  enterprise yang persisten [IM2]. **Jumlah baca memperkirakan posisi tag lebih baik daripada RSSI**; menurunkan daya
  mengurangi nyasar tetapi juga keterbacaan [IM3†].
* Nedap: pelindung fisik masih bocor 15–20 %; hitung toko 2,5 jam → 25 menit dengan alokasi algoritmik (klaim vendor) [RF1].
* Akurasi: GS1 US Project Zipper — akurasi inventori 63 % → 95 %, out-of-stock turun hingga 50 %, waktu cycle count
  −96 % [RF2†]; Hardgrave dkk. 2013 — ketidakakuratan catatan turun ±26 % (13 toko, 23 minggu) [RF3†]; Auburn RFID Lab —
  audit kuantitas item-level layak pada > 99,99 % karton [RF4]. Semua dari ritel/DC apparel, bukan gudang roll kain.
* Encode: ZPL `^RS` — tag gagal diprogram → label dicetak "VOID" dan dicoba ulang 1–10 label (bawaan 3), lalu lewati/
  jeda/galat [ZB6]; semua label VOID → printer belum dikalibrasi; yield rendah → posisi inlay/daya [ZB7]. EPC Tag Data
  Standard terbaru 2.3.0 (31 Okt 2025) [GS1]; SGTIN-96: serial numerik ≤ 274.877.906.943, tanpa nol di depan [GS2];
  identitas di barcode dan di tag harus sama [GS3†].
* Offline: Android — sumber lokal = kebenaran untuk baca; tulis **online-only** (transaksi real-time, UI peringatan
  saat offline), **antre** (backoff), atau **lazy** (tulis lokal dulu, konflik diselesaikan) [MD6]; Zebra (aplikasi SAP):
  cache lokal, daftar transaksi tertunda, ikon status koneksi, sinkron manual [ZB8]; D365 v4: ketahanan jaringan dan
  diagnostik Wi-Fi [MS21][MS20].

**Inferensi.** Untuk KN (sejalan dengan K-RFID-09/10): UI RFID menampilkan **keyakinan** sebagai jumlah baca, antena,
dan waktu terakhir terlihat (RSSI pendukung, bukan angka utama); hasil verifikasi dalam **tiga kategori**; pengaturan
daya disajikan sebagai **profil bernama** (perubahan manual = "Kustom"); mode "cari roll" ala geiger; setiap tag yang
dicetak wajib **dibaca balik** sebelum dianggap aktif; pengumpulan bacaan = tulis lokal (lazy, idempoten per sesi),
posting yang mengubah stok = online-only.

### 1.6 (6) Pindai per dokumen, bukan satu per satu

**Fakta**
* Odoo Barcode: transfer dibuka dari kartu operasi **atau dengan memindai barcode dokumennya** (dokumen cetak berisi
  barcode) [OD5]; layar berisi baris produk dengan kuantitas harapan, tombol **+#** (isi sesuai harapan), editor ±1;
  untuk pengiriman lokasi sumber dipindai dulu [OD1]; progres pecahan "1/2", "3/3"; pada batch, warna batang kiri
  menandai dokumen asal, dokumen selesai disorot hijau [OD2]; contoh GS1 "50/50 Units processed" lalu Validate berwarna
  hijau [OD3]; pindai lot wajib/opsional (opsional disarankan di penerimaan karena label pemasok bisa rusak) [OD6];
  memindai lot menaikkan kuantitas sesuai kuantitas tercatat lot itu [OD7].
* Odoo opname: siklus hitung per lokasi; layar *Physical Inventory* berisi kuantitas tercatat, kuantitas dihitung
  (kosong bawaan), dan selisih, dengan konfirmasi bila stok berubah setelah dihitung [OD12][OD13].
* D365: konfirmasi lokasi/kuantitas wajib per jenis kerja; konfirmasi produk untuk pick/put [MS1]; ringkasan baris
  pick di awal/atas permintaan (*Show work line list*) [MS12].
* RFID: verifikasi isi kotak read-vs-expected dengan data harapan dari WMS/ERP [RF6†]; penolakan otomatis + penanganan
  pengecualian [RF5]; terowongan < 1,5 s per karton [IM1].

**Inferensi.** "Per dokumen" = **sesi dokumen**: buka (pindai QR/barcode dokumen atau pilih) → daftar harapan → pindai/
baca massal → selisih tiga kategori → tutup (dengan/tanpa selisih). KN sudah punya mesin sesinya (lihat §2.3: U300,
verifikasi cetak, opname per roll), tetapi belum satu **layar HP** yang seragam untuk semua jenis tugas.

### 1.7 (7) Melihat ribuan roll dengan mudah

**Fakta — model data kain**
* Infor WMS: *lottable* membuat lot unik; contoh resmi tekstil dibedakan per **dye lot**; lot internal dibuat saat
  penerimaan untuk setiap kombinasi barang/pemilik/lottable baru [IN2].
* Infor CloudSuite Distribution (*linear cut*): panjang awal lot jadi *cut piece* pertama; potong/sesuaikan mengurangi
  panjang; pecah satu potongan jadi dua; sisa tak terjual → scrap; ***Cut Replenishment Length*** memicu laporan bila
  potongan di bawah ambang; alokasi memilih potongan **paling dekat dengan panjang pesanan yang masih cukup** [IN3].
* Datatex: pelacakan SKU/quality level/lot/kontainer/nomor roll; saldo dalam tiga satuan; split/join elemen [TX1†].
* SAP: *batch determination* mencari batch menurut karakteristik lalu mengurutkan (contoh resmi: kedaluwarsa naik, lalu
  *color value* turun, lalu kuantitas turun untuk meminimalkan split) [SAP8][SAP9]; SAP Fashion: segmentasi stok
  menyaring batch [SAP10]; karakteristik panjang per batch untuk mill products [SAP11†].
* Odoo: lot = satu batch; daftar lot bisa dikelompokkan per produk [OD21]; contoh resmi kain dilacak dalam yard, dibeli
  dalam meter [OD22]. RFMS (roll goods): opsi **satu dye lot per baris pesanan**; sisa = awal − terpakai − dipesan [TX2†][TX3†].
  Halaman produk Infor CloudSuite Fashion hanya menyebut perencanaan dye lot; atribut per roll **tidak terverifikasi** [IN4].

**Fakta — tampilan data besar**
* AG Grid: hanya baris/kolom terlihat yang dirender (+ buffer 10 baris) [GR1]; *client-side* sanggup 100 rb+ baris,
  tetapi ekspor pada model server **hanya mencakup baris yang sudah dimuat** [GR2]; *Server-Side Row Model*: grouping,
  agregasi, saring, urut di server; anak grup dimuat saat grup dibuka [GR3]; agregasi sum/min/max/count/avg [GR4];
  grup bertingkat dengan bawaan tertutup [GR13].
* TanStack: contoh resmi 10.000 item tervirtualisasi [GR7]; TanStack Table tidak punya virtualisasi bawaan, tabel kecil
  lebih baik dirender biasa [GR8]. MUI DataGrid: virtualisasi, ekspor baris terfilter & terurut, kolom terlihat [GR9][GR10].
* Fiori: *responsive table* ±200 item untuk data berkompleksitas sedang; *grid table* untuk volume besar dengan lazy
  loading, hanya desktop/tablet [FI9†]; *analytical table* untuk grup bertingkat dengan subtotal [FI11†].
* NN/g: kolom pertama ID yang bisa dibaca manusia, kepala dan kolom pertama dibekukan, indikator saringan aktif jelas,
  rincian di panel samping nonmodal [NN4]; pagination lebih baik daripada infinite scroll untuk tugas bertujuan [NN10][NN11];
  saringan interaktif hanya bila hasil < 1 s, selain itu tombol Terapkan [NN6]; navigasi faset cocok untuk koleksi sangat
  besar tetapi mahal dibangun dan dirawat [NN12]; di HP kolom pertama dikunci dan kepala lengket [NN5].

**Inferensi.** Untuk ±6.000 roll/hari (±180 rb/bulan, tumbuh lintas PT/site): **saring/urut/kelompok/agregat di server**,
virtualisasi baris di klien, hierarki bawaan **Produk › Warna › Lot (dye lot) › Roll** dengan agregat *jumlah roll ·
total panjang · panjang tersedia*, grup tertutup, rincian roll di panel samping, dan aturan alokasi **satu lot per baris**.

### 1.8 (8) Standar elemen: form, tombol, cari, saring, ekspor, desain

**Fakta — angka sistem desain**

| Elemen | SAP Fiori | Fluent 2 | Carbon | Material 3 / Android | Apple HIG | Lainnya |
|---|---|---|---|---|---|---|
| Kerapatan | *cozy* (sentuh, kontrol 44 px) vs *compact* (mouse, 32 px); tidak boleh dicampur dalam satu hierarki; Launchpad: compact di desktop, cozy di mobile [FI4†][FI5][FI6] | — | ukuran XS 24 · S 32 · M 40 · L 48 [CB3][CB5] | density −1…−3 mengurangi 4 px per langkah [MD5] | — | Oracle JET: skala *Small* tidak ramah sentuh, hanya desktop [OR5] |
| Tombol | — | 24/32/40 px (hitungan dari kode) [FL4] | XS 24 · S 32 · M 40 · L 48 · XL 64; satu tombol primer per halaman [CB3][CB4] | — | — | GOV.UK: satu primer, label kata kerja, hindari tombol nonaktif [GV6] |
| Target sentuh | cozy 44 px [FI4†] | 44 (iOS/Web), 48 (Android) [FL2] | — | **48 × 48 dp**, jarak 8 dp, ±9 mm [MD3][MD4] | **44 × 44 pt** (min 28) [AP1] | WCAG 2.5.8: **24 × 24** (AA); 2.5.5: 44 × 44 (AAA) [W1][W2]; NN/g ≥ 1 × 1 cm [NN9] |
| Huruf | — | 10/14 · 12/16 · 14/20 · 16/22 · 20/26 · 24/32 · 28/36 · 32/40 [FL1] | 12/16 · 14/18 · 14/20 · 20/28 · 28/36 · 32/40 [CB1] | 11/16 · 12/16 · 14/20 · 16/24 · 22/28 · 24/32 … [MD1] | iOS default 17, min 11 pt [AP2] | Atlassian 12/16 · 14/20 · 16/24 [AT2] |
| Spasi | — | 2,4,6,8,10,12,16,20,24,28,32,… [FL2] | 2,4,8,12,16,24,32,40,48,64 [CB2] | — | — | Atlassian dasar 8 [AT1] |
| Radius | — | 0 · 2 · 4 · 8 · 12 · lingkaran [FL3] | — | — | — | — |
| Tabel | grid table untuk > ±1.000 baris [FI9†] | — | baris 24/32/**40 bawaan**/48/64; toolbar ≤ 5 aksi; bilah aksi massal; skeleton saat memuat [CB6][CB7] | — | — | GOV.UK angka rata kanan [GV7]; AG Grid baris 42 [GR11]; MUI 52 [GR12] |
| Status | satu state per elemen; biru dicadangkan untuk tautan [FI16†] | — | **≥ 2 dari warna/bentuk/simbol + teks**; kontras antar status ≥ 3:1 [CB8] | chip saring 32 dp [MD2] | — | Atlassian lozenge: neutral/success/warning/danger/information/discovery, tidak bergantung warna [AT3] |
| Saringan & tampilan tersimpan | live lebih disukai; jumlah saringan aktif; satu variant management per halaman, tanda `*` bila berubah [FI7†][FI8†] | — | *batch* (tombol Terapkan) untuk banyak kategori/data lambat, *instant* untuk satu pilihan; saringan tersembunyi wajib tampil jumlah + hapus [CB12] | — | — | D365 saved views `*` belum disimpan [MS18]; Odoo Filters/Group By/Favorites [OD19] |
| Ekspor | ikuti kolom, urutan, saringan; batas ±1 jt sel desktop; opsi lembar saringan [FI12†] | — | 2–5 format sebagai pilihan dengan bawaan; langsung jalan bila nama berkas jelas [CB14] | — | — | D365 persis grid, bawaan 50.000 baris (≤ 100.000) [MS19]; Zoho Export Current View [ZO2]; Odoo ekspor csv/xls + "import-compatible" [OD20]; AG Grid bawaan baris tersaring & terurut, Excel membawa tipe data [GR5][GR6]; CSV hanya satu lembar, pemisah ikut setelan regional Windows [EX2] |
| Form | — | — | label di atas, jarak label–isian 8 px; validasi saat blur; galat di bawah isian [CB5][CB13] | — | — | GOV.UK: label di atas tanpa titik dua, tanpa placeholder sebagai label, `inputmode`, validasi saat kirim, ringkasan galat di atas [GV1][GV2][GV3][GV4][GV5] |
| Kosong/memuat/galat | illustrated message, toast hanya untuk sukses [FI13†][FI14†] | — | empty state: tidak ada data / tidak ada hasil / galat, satu aksi; skeleton beberapa detik [CB10][CB11] | — | — | NN/g: < 1 s tanpa indikator, 2–10 s skeleton, > 10 s progres + batal [NN2][NN3] |

**Fakta — standar & riset**
* WCAG 2.2: 1.4.1 warna bukan satu-satunya penanda; 1.4.3 teks 4,5:1 (teks besar ≥ 24 px atau ≥ 18,66 px tebal 3:1;
  nilai tidak dibulatkan); 1.4.11 komponen & ikon bermakna 3:1 (termasuk batas isian bila itu satu-satunya penanda);
  1.4.10 reflow pada 320 CSS px (tabel boleh bergulir di wadahnya sendiri); 2.4.11 fokus tidak tertutup header/footer
  lengket; 3.3.1 galat dijelaskan dengan teks; 3.3.2 label wajib; 3.3.7 data yang sudah diisi jangan diminta ulang
  [W1][W3][W4][W5][W6][W7][W8].
* Nielsen: 10 heuristik — antara lain *visibility of system status*, *recognition rather than recall*, *error prevention*,
  *consistency and standards* [NN1]; beban kognitif: hindari kekacauan visual, bangun di atas model mental yang ada,
  alihkan beban (tampilkan ulang data yang sudah diisi, bawaan cerdas) [NN13].
* D365 aplikasi gudang: *Text scale* 70–400 %, *Button scale* 50–200 %, posisi tombol terbaik (bawaan kanan bawah),
  *Scan with camera* = No bila ada pemindai fisik, getar 0–5, bunyi 0–10, bunyi khusus bila perlu pindai ulang, tema
  kontras tinggi [MS4]; profil pengaturan per merek/model perangkat [MS5]; halaman aksesibilitasnya menyebut skala huruf
  50–400 % (berbeda dengan [MS4]) [MS6†].
* Fiori *list report*: untuk mencari dan menindaklanjuti item di set data besar dengan cari, saring, urut, kelompok;
  tidak untuk mencari satu item yang kodenya sudah diketahui [FI1†].

### 1.9 Perangkat, ergonomi, dan label 70 × 22 mm

**Fakta — Chainway C72** [CW1] (diverifikasi ulang 9 Nov): layar **5,2" IPS 1920 × 1080**, Gorilla Glass, *multi-touch*,
**mendukung sarung tangan dan tangan basah**; Android 11/13 (GMS, SOTI MobiControl); baterai 8.000 mAh (> 12 jam);
**375 g, 673 g dengan pegangan UHF**; IP65; jatuh berulang 1,5 m ke beton; −20…50 °C; **4 tombol depan, 2 tombol pindai,
1 tombol multifungsi**; UHF 1 W, 1.300+ tag/s; jangkauan 26–30 m (luar ruang, interferensi rendah). Halaman berita
Chainway memuat angka berbeda (−10…50 °C; 25 m/10 m; 200 tag/s) [CW2] → acuan = halaman produk [CW1].

**Fakta — Chainway CP30** [CW3]: 203/300 dpi; lebar cetak 108/106 mm; media lebar 25,4–118 mm, **tinggi label 20–250 mm**;
UHF EPC C1G2 (ISO 18000-6C), Gen2X; emulasi ZPL-II/TSPL/DPL/EPL. Verifikasi encode/VOID/kalibrasi RFID **tidak disebut**.

**Fakta — ergonomi**: target jempol satu tangan 9,2 mm (diskret) / 9,6 mm (serial) [RS1]; 49 % genggaman satu tangan,
36 % ditopang, 15 % dua tangan [RS2]; akurasi ±7 mm di tengah layar, ±12 mm di sudut, rancang ±20 % lebih besar untuk
kondisi buruk, aksi tak bisa dibatalkan dijauhkan dari kontrol yang sering dipakai [RS3]; dengan sarung tangan akurasi
turun, MIL-STD-1472: 15 mm tanpa / **20 mm dengan sarung tangan** [RS4†]. Angka khusus keterbacaan di cahaya terang:
**tidak ditemukan sumber primer** → pakai kontras AA sebagai lantai dan tema kontras tinggi seperti D365 [MS4].

**Fakta — label kecil**: GS1-128 logistik tinggi minimum 31,75 mm, X 0,495–1,016 mm, zona sepi 10X [GS4]; item terlalu
kecil boleh X ≥ 0,250 mm [GS4]; zona sepi Data Matrix 1 modul, QR 4 modul [GS6†]; DENSO: **≥ 4 titik per modul**
(203 dpi → 0,50 mm; 300 dpi → 0,33 mm) [GS8]; QR versi 1 = 21 × 21 modul [GS9]; rMQR untuk ruang sempit [GS10];
Data Matrix 18 × 18 = 36 digit / 25 alfanumerik [GS11]; teks terbaca manusia pada label logistik GS1 ≥ 3 mm [GS5†],
GS1 UK ≥ 2 mm untuk label QR [GS12†]; 203 dpi = 0,125 mm per titik, 300 dpi ≈ 0,085 mm [ZB9].

**Inferensi — lebar CSS C72.** 1920 × 1080 pada 5,2" = ±424 ppi; lebar fisik layar potret ±64,8 mm. Android biasanya
memberi kelas kepadatan 480 dpi (rasio 3 → **360 CSS px**) atau 420 dpi (rasio 2,625 → **411 CSS px**) — **belum
diketahui untuk C72**. Bila 360 px, standar KN "layak 390 px" **tidak cukup**: layar harus diuji di 360 px. Ukuran fisik:
48 px ≈ 8,6 mm (360) / 7,6 mm (411); 56 px ≈ 10,1 / 8,8 mm; 64 px ≈ 11,5 / 10,1 mm (Lampiran A).

---

## 2. Perbandingan dengan KN sekarang (HEAD `70eb9fd`)

### 2.1 Ukuran terukur (hitung ulang saya)

| Ukuran | Nilai | Cara ukur |
|---|---|---|
| Ukuran huruf arbitrer `text-[Npx]` | **21 ukuran, 8.863 pemakaian** (koordinator: 8.903 — beda cakupan pindai) | `grep -rhoE "text-\[[0-9.]+px\]"` di `frontend/src` (`.js`, `.jsx`) |
| … di bawah 12 px | **6.760 (76 %)**: 11 px 2.572 · 10,5 px 1.406 · 10 px 1.288 · 11,5 px 994 · 9,5 px 305 · 9 px 177 · 8,5 px 18 | idem |
| … di layar gudang (`features/mobile`, `wms`, `rfid`) | terbanyak 11 px (369), 12 px (209), 10 px (209), 10,5 px (159) | idem, per folder |
| Warna hex berbeda | **712** di .js/.jsx (**798** termasuk .css; koordinator: 649) | `grep -rhoE "#[0-9A-Fa-f]{6}"`, huruf besar, unik |
| Hex teratas | `#6B6B73` 2.627 · `#0058CC` 1.514 · `#8E8E93` 1.401 · `#EFF0F2` 1.204 · `#9A9BA3` 657 | idem |
| Tombol bergaya sendiri | 390 (bukti koordinator; tidak saya hitung ulang) | — |
| Tinggi tombol/isian desktop | ±35–36 px (padding 8/7 px + huruf 13 px × line-height 1,5 + batas) | `styles/components.css:67-79, 82-94, 125-140` |
| Baris tabel `.data-table` | ±36 px (huruf 12,5 px, padding 9 px); kepala 10,5 px kapital | `styles/components.css:743-755` |
| Chip saringan | min-height 28 px | `styles/components.css:970-972` |
| Tombol aksi modal HP | min-height 44 px | `styles/mobile.css:143` |
| Isian & tombol Pindai HP | ±56 px (`p-3.5`, 16 px) dan ±59 px (`py-4 text-lg`) | `MobileWarehouseApp.jsx:167, 174` |

### 2.2 Kontras warna yang dipakai sekarang (rumus WCAG, Lampiran A)

| Pemakaian KN | Pasangan | Rasio | Syarat | Hasil |
|---|---|---|---|---|
| `.primary-button` (13 px tebal) | putih di `#007AFF` | **4,02:1** | 4,5:1 (13 px tebal bukan "teks besar") | **gagal 1.4.3** |
| `.danger-button` | putih di `#FF3B30` | **3,55:1** | 4,5:1 | **gagal** |
| Teks abu (1.401 pemakaian) | `#8E8E93` di putih / `#F4F5F8` | 3,26 / 2,99:1 | 4,5:1 | **gagal** (lolos hanya untuk ikon, 3:1) |
| Teks abu & placeholder (`.field::placeholder`) | `#9A9BA3` di putih | **2,77:1** | 4,5:1 | **gagal** |
| Batas isian `.field` | `#D6D7DC` di putih | **1,44:1** | 3:1 bila batas satu-satunya penanda isian | **gagal 1.4.11** (isian putih di kartu putih) |
| `Pill` RFID hijau/oranye (10 px) | `#34C759` / `#FF9500` di latar 10 % | ±1,97 / ±1,95:1 | 4,5:1 | **gagal** — termasuk lencana "Kuning" gate V2 (`u300Labels.js:8` → `orange`) |
| Tanda "ragu" OCR | `#B26A00` di `#FFF6E5` | 3,95:1 | 4,5:1 | **gagal** |
| Teks sekunder baku | `#6B6B73` di putih / `#F4F5F8` | 5,28 / 4,85:1 | 4,5:1 | lolos |
| Aksi/tautan `#0058CC` | di putih; putih di atasnya | 6,43:1 | 4,5:1 | lolos |
| Hijau `#1B7F4B`, merah `#C0392B`, coklat `#8C4A00` | di putih | 5,02 / 5,44 / 6,79:1 | 4,5:1 | lolos |

### 2.3 Per area

| Area | Pola profesional (§1) | KN sekarang (bukti) | Celah |
|---|---|---|---|
| **Standar tertulis** | sistem desain bertoken & ditegakkan | `KN_08` v1.0 (Mei 2026): font Inter (`:64`), primer navy (`:33`), radius 6 px (`:101`), **"Camera-first scanner"** (`:407`). Nyatanya: Manrope/Outfit (`index.css:40,47`), primer iOS `#007AFF` (`tokens.css`), `--radius: 1rem` (`index.css:33`) dan `--r-md` 10 px. Tidak ada guardrail token | Dokumen dan kode berbeda arah; "kamera dulu" bertentangan dengan C72 yang punya pemindai fisik [CW1][MS4] |
| **Token** | skala terbatas (6–10 ukuran) [FL1][CB1] | `tokens.css`: spasi 4–32 px, radius 8/10/14/18, warna iOS; `tailwind.config.js` hanya warna shadcn, **tanpa skala `fontSize`** | Huruf & warna ditulis langsung di kelas (§2.1) |
| **Cakupan pengguna** (1) | gudang/PT bawaan + pindah eksplisit [MS2][OD16] | Pagar **lokasi kerja** IMP-20 hanya untuk peran `warehouse` saat setelan `wms.location_scope_enforced` aktif; supervisor/manajer/admin melihat semua (`services/location_scope.py:1-27`); indikator `LocationScopeBadge`; `EntitySwitcher` punya "Semua"; kartu tugas HP menulis nama gudang per kartu karena daftar bisa campuran (`MobileWarehouseApp.jsx:98`) | Cakupan = **pagar**, belum **tampilan bawaan**; peran non-gudang selalu melihat campuran; belum ada "Ganti lokasi" di HP selain ganti PT |
| **Angka stok** (2) | angka bernama, berumus, pivot per dimensi [MS15][OD10] | `InventorySummaryCards`: Total Stok Fisik / Tersedia / Dipesan / Stok Rendah **per satuan, tanpa jumlah roll** (`inventory/InventorySummaryCards.jsx:24-29`); `BalancesTable` per produk × gudang × pemilik dengan kolom "Lainnya" = Fisik − Dipesan − Tersedia (`inventory/BalancesTable.jsx:6-16`); `SalesStockSummary` memakai **Fisik / Dikunci / Bebas / Datang / Menunggu / ATP** pada 10,5 px (`components/SalesStockSummary.jsx:20-31`) | Belum ada pasangan angka "cakupan kerja vs total"; dua kosakata untuk konsep sama (Dipesan vs Dikunci, Tersedia vs Bebas) → butir K-B4-06; angka roll tidak di kartu ringkas |
| **Jenis tugas** (3) | jenis tugas kelas satu [MS1][OD5] | HP: tab **Masuk / Keluar / Sample / Pindai** (`MobileWarehouseApp.jsx:284-289`); `wms_tasks.flow_type` praktis hanya `inbound`/`outbound` + subtipe `sample_cut` (`routers/wms.py:27-55`); penempatan rak, transfer, stock opname, QC, potong ada sebagai **modul desktop** terpisah (`features/wms/*`) | Tugas non-masuk/keluar tidak muncul di HP sebagai tugas; penanda "SAMPEL" berupa teks tambahan di baris kartu (`:98`) |
| **QC/GRN/OCR** (4) | terima → status QC → keputusan per unit; OCR = draf diperiksa [MS13][OD15][OD24] | GRN wizard memakai `FormModal` (`grn/GrnCreateWizard.jsx:13-15`); OCR menandai "Angka ragu" & menghormati **hitung buta** (`grn/GrnOcrDraft.jsx:1-11`, `grn/GrnLineRow.jsx:29`); QC: barang GR ditahan karantina → terima/tolak (`QCInspection.jsx:16-20`); area QC bisa diatur (K-GDG-04) | Pola sudah **selaras**; yang kurang: warna "ragu" gagal kontras; komponen keputusan QC dan penanda "ragu" belum satu komponen bersama |
| **RFID** (5) | 3 kategori, keyakinan = jumlah baca, profil bernama [ZB3†][IM3†][ZB2] | Opname RFID: "Ditemukan x/y · hilang · asing/salah lokasi" (`rfid/CycleCountPanel.jsx:82`); verifikasi cetak "x/y cocok" + "Missing (n)" berbahasa Inggris (`rfid/RfidPrintVerifyPanel.jsx:281,308`); sesi dokumen gate "x/y roll lewat · sisa" + bar hijau (`rfid/U300DocSession.jsx:13-30`); kios V1 `GateLiveVerdict` **tanpa keadaan kuning** (`rfid/GateLiveVerdict.jsx:54-58`), V2 punya kuning (`u300Labels.js:3-8`); tombol sesi `!py-0.5 text-[11px]` (±20 px) | Pola 3 kategori sudah ada di 2 layar (istilah per konteks); kontras Pill gagal; kios V1 belum mengikuti K-RFID-09; tombol kecil di layar operasional |
| **Pindai** (6) | sesi per dokumen, scan-first [OD1][MS7] | HP `ScanPanel` = **satu kode → satu lookup** (`MobileWarehouseApp.jsx:118-137`); hasil besar ikon + judul + teks, "bukan warna saja" (`:160-182`) ✔; antre offline (`:130-134`) ✔; kamera `BarcodeDetector` QR/Code128 sebagai alternatif (`:142-159`) | Belum ada layar "sesi dokumen" di HP untuk SJ/putaway/transfer/opname |
| **Ribuan roll** (7) | server-side + virtualisasi + grup lot [GR3][FI11†] | Roll: `usePagedList` server-side, 100 per halaman (`InventoryStockView.jsx:112-113`); `BalancesTable` dirender lewat `PagedRows` 25 baris/halaman di klien (`components/PagedRows.jsx`); **tanpa pustaka virtualisasi** (`package.json`: hanya `@tanstack/react-query`); belum ada grup Produk › Warna › Lot dengan agregat | Daftar datar per halaman; tidak ada ringkasan per lot |
| **Daftar & ekspor** (8) | saring → tampilan tersimpan → ekspor ikut saringan [MS18][MS19] | Komponen baku ada: `PageHeader`/`MetricRow`/`SearchBox`/`StatusTabs` (`ListPageParts.jsx`) **dan** `SearchBox`/`StatusTabs` kedua (`ListControls.jsx`); `FilterChips`; tiga pager (`PaginationBar`, `KNPager`, `PagedRows`); ekspor **CSV saja** via `PaginationBar.exportConfig` (pilihan "Halaman ini/Semua hasil filter"), `fetchAll` 200 baris/permintaan, batas 50.000 (`hooks/usePagedList.js`), dijaga INV-UI-07 (`;`, BOM, desimal koma, anti-formula — `scripts/guardrails/verify_list_export.py`); `useViewPreset` = preset navigasi, **bukan** tampilan tersimpan | Tidak ada XLSX; tidak ada tampilan tersimpan; duplikasi komponen; ekspor data besar di peramban |
| **Form** | label di atas, validasi jelas, satu primer [GV5][CB13] | `FormModal` (pop-up baku, kaki lengket, galat di dalam, layar penuh ≤ 640 px, isian HP = desktop); `FormSection` bernomor bisa dilipat, tanda `*`; `.field-label` 11 px kapital (`components.css:828`); pemilih `KNSelect` (cari otomatis untuk daftar panjang), `ProductSelect` (portal), `RollPicker`, `SiteSelect` | **Selaras**; kurang: label 11 px, batas isian & placeholder gagal kontras, belum ada ringkasan galat untuk form panjang |
| **Kosong/memuat/galat** | 3 jenis kosong, skeleton 2–10 s [CB10][NN3] | `ErrorNotice` bilah menempel + "Coba lagi" (keputusan pemilik P5) ✔; `LoadingLine`, `ui/skeleton` ada; banyak layar menulis "Memuat…" teks (`MobileWarehouseApp.jsx:61,214`, `BalancesTable.jsx:39`); kosong tanpa aksi lanjutan (`:63`) | Belum seragam |
| **Label 70 × 22** | DM/Code128 sesuai lebar, HRI ≥ 2–3 mm [GS8][GS5†] | `generate_rfid_zpl` dirancang **4 × 2" (203 dpi)**: 6 baris teks + Code128 50 titik, sampai y ±214 titik (±27 mm) (`services/rfid_print_service.py:48-66`); label QR **58 × 40 mm** (`:69-87`); `label_printer_service.py:195` "4x2 inch" | Template **tidak muat** 22 mm (176 titik @203 dpi); belum ada template 70 × 22 |
| **Offline** | baca cache, tulis antre, status koneksi [MD6][ZB8] | `utils/offlineQueue` (`queueScan`), `OfflineBanner`, header `x-from-cache` → bilah "Offline — menampilkan daftar tugas terakhir… Aksi akan diantrekan" (`MobileWarehouseApp.jsx:79`) | **Selaras**; perlu aturan tegas mana yang online-only |

### 2.4 Yang sudah selaras (pertahankan, jangan dibongkar)
`FormModal`/`FormSection` (form HP = desktop), `ErrorNotice` (galat menempel + coba lagi), `QtyDual` (roll + ukuran,
aturan "—" vs "0 roll"), `ResponsiveTable` (satu definisi kolom → tabel/kartu HP), `FilterChips` vs `PageTabs`
(saringan ≠ tab), angka nol netral (`isZeroMetric`), hasil pindai "ikon + teks, bukan warna saja", hitung buta GRN,
antre offline, INV-UI-07 (CSV benar untuk Excel Indonesia), sesi dokumen gate bertahap (K-RFID-10).

---

## 3. Usulan "Standar UI Gudang v1"

### 3.0 Status & cakupan
* Berlaku untuk: layar gudang desktop (`features/wms`, `features/rfid`), aplikasi HP gudang (`features/mobile`), kios gate,
  dan komponen baku yang mereka pakai. Layar lain boleh mengikuti; guardrail ratchet berlaku per berkas (§3.14).
* Menggantikan bagian `KN_08` yang bertentangan (font, warna primer, radius, "camera-first") **setelah disetujui** (K-B4-01).
* Tidak mengubah istilah (K-13), definisi "Tersedia" (K-04), kebijakan gate (K-RFID-09/10), atau keputusan "form HP =
  form desktop".

### 3.1 Prinsip (diturunkan dari §1)
1. **Cakupan dulu**: setiap layar gudang tahu dan menampilkan lokasi kerja + PT aktif; "semua" dipilih sadar (P1).
2. **Angka punya nama, satuan, dan cakupan** — roll dulu, lalu panjang (P2, QtyDual).
3. **Status = ikon + teks + warna** — tidak pernah warna saja (P10, WCAG 1.4.1).
4. **Pindai dulu, ketik terakhir**: pemindai fisik utama, kamera cadangan, ketik manual paling akhir (P5).
5. **Per dokumen**: buka dokumen → harapan → baca → selisih → tutup (P6).
6. **Satu komponen per pola**: tidak ada varian kedua (pager, kotak cari, lencana) (Nielsen *consistency* [NN1]).
7. **Pengecualian bukan jalan buntu**: setiap penolakan menyebut alasan dan langkah berikutnya (NN/g [NN8]).
8. **Terukur & ditegakkan**: setiap aturan punya ukuran dan guardrail (§3.14).

### 3.2 Token

**a. Skala huruf (6 ukuran + 2 kios)**

| Token | px / line-height | Peran | Setara di sistem lain |
|---|---|---|---|
| `fs-12` | 12 / 16 | label isian, kepala kolom, chip, lencana, keterangan | Carbon label-01 [CB1]; Fluent Caption 1 [FL1]; Atlassian body.small [AT2]; M3 Body S [MD1] |
| `fs-13` | 13 / 18 | isi tabel & isian desktop (ringkas) | nilai KN sekarang 12,5–13 px |
| `fs-14` | 14 / 20 | teks badan, judul bagian, teks sekunder HP | Carbon body-01; Fluent Body 1; Atlassian body; M3 Body M |
| `fs-16` | 16 / 24 | badan & isian HP, subjudul desktop | M3 Body L; Atlassian body.large; Fluent Subtitle 2 (16/22) |
| `fs-20` | 20 / 28 | judul halaman desktop, judul hasil pindai HP | Carbon heading-03; Fluent Subtitle 1 (20/26) |
| `fs-24` | 24 / 32 | angka KPI, angka progres HP | Fluent Title 3; M3 Headline S |
| `fs-kiosk-40`, `fs-kiosk-64` | 40 / 48, 64 / 72 | kios gate (dibaca dari forklift) | *inferensi* — ukur jarak baca saat commissioning |

* **Minimum 12 px** di mana pun. HP: info untuk memutuskan (nomor roll, lokasi, jumlah, status) **≥ 16 px**; pendukung
  ≥ 14 px; 12 px hanya metadata (waktu, ID teknis).
* Berat huruf hanya 400 / 600 / 700. Kapital + jarak huruf hanya untuk kepala kolom (`fs-12`).
* Angka: `tabular-nums` wajib; rata kanan di kolom angka [GV7]; pemisah ribuan & desimal gaya Indonesia (`formatQty`).
* Pemetaan migrasi: 8,5–11,5 → `fs-12`; 12–13,5 → `fs-13`; 14–15 → `fs-14`; 16–18 → `fs-16`; 19–22 → `fs-20`; 24–26 → `fs-24`.
  *Inferensi:* 10 → 12 px menambah tinggi/lebar teks ±20 %; tabel padat perlu dicek (ratchet per berkas, §3.14).

**b. Spasi** — `2 · 4 · 8 · 12 · 16 · 24 · 32 · 48` px (subset Carbon [CB2], grid 4 px Fluent [FL2]). Tambah `--sp-0-5`
(2) dan `--sp-12` (48) ke `tokens.css`; selain nilai ini dilarang di kode baru.

**c. Radius** — `8` (lencana/chip persegi), `10` (tombol, isian — `--r-md` sekarang), `14` (kartu, modal), `18` (sheet HP),
`999` (pil, chip). Nilai KN sekarang dibakukan (tanpa perubahan visual); `rounded-[Npx]` lain dilarang. Catatan:
`--radius` shadcn = 1rem/16 px (`index.css:33`, dipakai `rounded-lg` Tailwind) → diselaraskan ke 14 px.

**d. Warna semantik** (rasio dihitung, Lampiran A; latar = putih kecuali disebut)

| Peran | Teks / ikon | Latar lembut (rasio teks di atasnya) | Isian solid (teks putih) | Pemakaian |
|---|---|---|---|---|
| Teks utama | `#1C1C1E` 17,01 | — | — | isi |
| Teks sekunder (minimum teks) | `#6B6B73` 5,28 (4,85 di `#F4F5F8`; 4,73 di `#F2F2F5`) | — | — | keterangan |
| Netral / draf | `#3C3C43` 10,94 | `#F2F2F5` 9,79 | `#3C3C43` | status netral |
| Aksi & info | `#0058CC` 6,43 | `#E6F0FF` 5,59 | **`#0058CC` 6,43** (ganti `#007AFF` 4,02) | tombol utama, tautan, fokus, info |
| Berhasil / hijau | `#126E2C` 6,38 | `#E6F6EC` 5,70 | `#1B7F4B` 5,02 | lolos, cocok, selesai |
| Perhatian / kuning | `#8C4A00` 6,79 | `#FFF4E5` 6,24 | kios: `#FFD60A` + teks `#1C1C1E` 12,05 | perlu diperiksa, ragu |
| Bahaya / merah | `#A8221A` 7,22 | `#FDECEC` 6,32 | **`#B42318` 6,57** (ganti `#FF3B30` 3,55) | pelanggaran, galat, hapus |
| Khusus / ungu | `#6B219A` 9,09 | `#F3E8FA` 7,68 | — | lot, sampel (kategori, bukan status) |
| Batas isian | `#8A8A8E` 3,44 (non-teks) | — | — | batas `.field`, kotak centang |
| Pemisah dekoratif | `#E5E5EA` 1,26 | — | — | garis tabel (bukan penanda komponen) |
| Fokus | `#0058CC` 2 px, offset 2 px | — | — | `:focus-visible`; tidak tertutup header lengket (2.4.11) |

* **Dilarang sebagai teks**: `#8E8E93`, `#9A9BA3`, `#34C759`, `#FF9500`, `#B26A00`, `#007AFF` (sebagai teks kecil di atas
  latar abu). `#8E8E93` masih boleh untuk **ikon** (3,26 ≥ 3:1).
* Kuning di atas putih (`#FFD60A` 1,41) bukan penanda yang cukup → selalu dengan ikon/teks gelap atau batas gelap.
* Warna kategori (jenis tugas) **tidak boleh** memakai hijau/kuning/merah (dicadangkan untuk status).

### 3.3 Densitas & ukuran

| | Desktop "ringkas" (mouse) | HP "nyaman" (sentuh, C72) |
|---|---|---|
| Tombol & isian | **36 px** (bawaan, ≈ sekarang); **32 px** kecil (toolbar tabel, dalam sel) | isian **48–56 px**, teks 16 px; tombol ≥ 48 px |
| Target minimum | **24 × 24 px** atau jarak setara (WCAG 2.5.8 [W2]) | **48 × 48 px**, jarak ≥ 8 px [MD3][MD4][FL2] |
| Aksi utama | satu per halaman/dialog [CB4][GV6] | **56 px** tinggi, lebar penuh, di bilah bawah tetap (zona jempol [RS2][RS3]) |
| Baris tabel / kartu | **36 px** (32 px rapat); kepala 32 px `fs-12` | baris kartu ketuk ≥ 56 px |
| Chip | 28 px | 36 px (*inferensi*: chip 32 dp M3 [MD2] + toleransi sarung tangan) |
| Ikon | 16 px dalam tombol 32–36 px | 20–24 px |
| Aksi merusak | tombol bahaya + konfirmasi | dijauhkan ≥ 1 target dari aksi utama [RS3]; tidak di posisi aksi utama |

* Alasan desktop 32–36 px: Fiori compact 32 [FI4†], Carbon S/M 32/40 [CB3][CB5], Fluent 24/32/40 [FL4]; KN sekarang ±36.
* Alasan HP 48/56 px: 48 dp Material/Fluent Android; Parhi 9,2–9,6 mm ≈ 51–53 px @360 / 58–61 px @411 [RS1]; Hoober
  +20 % untuk kondisi buruk [RS3]; sarung tangan 20 mm (MIL-STD via [RS4†]) hanya realistis untuk **1–2 aksi utama
  lebar penuh** (64 px × lebar layar ≈ 11,5 × 60 mm @360).
* **Lebar acuan HP**: uji **360 dan 390 px**; teks harus reflow pada 320 px (WCAG 1.4.10 [W5]; tabel boleh bergulir di
  wadahnya sendiri). Lebar CSS C72 diukur dulu (K-B4-04).
* **Setelan per pengguna/perangkat** (pola D365 [MS4][MS5]): "Ukuran tampilan: Normal / Besar" (skala teks & tombol
  ±125 %), bunyi & getar **berbeda** untuk berhasil / perlu pindai ulang / galat, tema kontras tinggi untuk area terang.

### 3.4 Anatomi halaman daftar

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ [1] Judul halaman                                        [+ Buat]  [⋯ aksi lain]     │
│ [2] Cakupan: 📍 Rancamalang ▾  ·  PT: PT aktif ▾          (selalu terlihat)          │
│ [3] Ringkasan (≤ 4): 1.240 roll · 58.310 m | Tersedia … | Dipesan … | Karantina …    │
│ [4] 🔍 Cari (≥ 280 px desktop)  [5] Chip saringan … [+ Saringan lain (2)] [Reset]    │
│ [6] Urut ▾   [7] Tampilan: "…" ▾ (* = berubah)   [8] Kolom ▾        [9] Ekspor ▾    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ [10] Tabel: kepala lengket · kolom 1 = ID · angka rata kanan · baris 36 px            │
│      ☐ pilih → bilah aksi massal menggantikan toolbar (Batal di kanan) [CB7]          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ [11] 1–100 dari 12.430 roll   ·   20 | 50 | 100 | 200   ·   ‹  ›                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

| Bagian | Aturan | Komponen |
|---|---|---|
| [1] Judul | judul + satu aksi utama; aksi lain di "⋯" | `PageHeader` |
| [2] Cakupan | bawaan = lokasi kerja + PT aktif; ganti = aksi eksplisit; perubahan tampil di URL/preset | **baru `ScopeBar`** (memakai `LocationScopeBadge`, `SiteSelect`, `EntitySwitcher`) |
| [3] Ringkasan | ≤ 4 angka, mengikuti saringan & cakupan, roll dulu (`QtyDual`); 0 netral | `MetricRow` / `InventorySummaryCards` |
| [4] Cari | kiri, debounce 350 ms, server; cari nomor roll/dokumen juga dengan **memindai** ke kotak cari | `SearchBox` (satu versi) |
| [5] Saringan | chip untuk ≤ 6 nilai; lebih → panel; jumlah saringan aktif + Reset [CB12][FI7†]; live bila hasil < 1 s, selain itu tombol Terapkan [NN6] | `FilterChips`, `TableFilter` |
| [6–8] Urut, tampilan, kolom | tampilan tersimpan pribadi + dibagikan per peran & PT; satu bawaan; tanda `*` bila berubah [MS18][FI8†] | **baru `SavedViews`** |
| [9] Ekspor | **Excel (.xlsx) bawaan + CSV**; mengikuti saringan, urutan, kolom terlihat, dan **cakupan**; pilihan "Halaman ini / Semua hasil filter" tetap; lembar "Info" (saringan, cakupan, pengguna, waktu, jumlah baris) [FI12†]; ID sebagai teks, angka sebagai angka [EX1]; CSV tetap INV-UI-07 (`;`, BOM [EX3], desimal koma, anti-formula [EX6]); **≤ 50.000 baris** langsung (= batas D365 [MS19] = `FETCH_ALL_HARD_CAP` KN), lebih → **job server** + notifikasi (ekspor model server di klien hanya baris termuat [GR2]); XLSX ditulis *streaming* [EX5]; batas Excel 1.048.576 baris [EX4] | `PaginationBar` + **baru `ExportMenu`** |
| [10] Tabel | kepala lengket; kolom 1 = ID manusia (nomor roll/dokumen, mono) [NN4]; ≤ 2 aksi inline, sisanya "⋯"; klik baris → panel samping; HP → kartu | `ResponsiveTable` (+ densitas, + virtualisasi) |
| [11] Halaman | 20/50/100/200 (bawaan 50; roll 100); tidak infinite scroll untuk tugas bertujuan [NN11] | `PaginationBar` (satu-satunya pager) |
| Keadaan | §3.10 | `EmptyState`, `ErrorNotice`, skeleton |

### 3.5 Anatomi form

1. **Wadah**: `FormModal` (desktop pop-up; HP layar penuh) + `FormSection` bernomor; bagian jarang dipakai boleh dilipat
   (isian tetap terpasang). **Isian HP = isian desktop** (keputusan pemilik); tata letak HP 1 kolom.
2. **Label** di atas isian, tanpa titik dua, `fs-12`/600 (huruf biasa, bukan kapital untuk label panjang); bantuan satu
   kalimat di bawah label; **placeholder bukan label** [GV5][CB5].
3. **Wajib**: tanda `*` + teks tersembunyi "wajib" (status quo `FormSection`); alternatif GOV.UK "(opsional)" [GV1] →
   K-B4-11.
4. **Rujukan selalu lewat pemilih** — produk (`ProductSelect`), roll (`RollPicker`), gudang/site (`SiteSelect`),
   lokasi (`LocationFields`), mitra/dokumen (`KNSelect` searchable). Tidak ada isian teks bebas untuk ID (*recognition
   rather than recall* [NN1]). Di HP, pemilih roll/lokasi menerima **pindaian**.
5. **Angka**: `DecimalInput`/`inputmode="decimal"`; satuan di label atau akhiran isian [GV5]; tampilan hasil memakai `QtyDual`.
6. **Validasi**: format saat keluar isian (Carbon [CB13]); kelengkapan saat Simpan (GOV.UK [GV2]); pesan **di bawah
   isian**, spesifik ("Isi panjang roll", bukan "tidak valid"), ikon + teks [W1][NN8][GV4]; form ≥ 2 bagian →
   **ringkasan galat** di atas yang menautkan ke isian [GV3]; isian pengguna **tidak pernah dihapus**.
7. **Tombol**: kaki lengket; satu tombol utama; desktop: Batal kiri, utama kanan; HP: lebar penuh ≥ 48 px, utama paling
   bawah; tombol nonaktif hanya dengan alasan tertulis di dekatnya (GOV.UK menyarankan menghindari tombol nonaktif [GV6]);
   aksi merusak → `danger-button` + `askConfirm`.
8. **Isi otomatis** dari dokumen/konteks (gudang = cakupan aktif, PO dari GRN, dsb.) — WCAG 3.3.7 [W8], NN/g [NN13].

### 3.6 Anatomi layar tugas HP (scan-first, per dokumen)

```
┌──────────────────────────────────────────────── 360–390 px ┐
│ ←  [ikon] Keluar SO · SJ-2611-0042             ● online     │  app bar
│ 📍 Rancamalang · Gedung Woven                               │  cakupan
├─────────────────────────────────────────────────────────────┤
│ Pelanggan X · 20 roll · 1.240 m                              │  ringkasan dokumen
│ 12/20 roll · 744/1.240 m   [██████████░░░░░░]                │  progres (fs-24)
├─────────────────────────────────────────────────────────────┤
│ [ Pindai roll / lokasi … (fokus otomatis, 56 px) ] [📷]      │  input utama
│ ✓ COCOK  R-2611-001234 · 62,0 m · Lot 7A                     │  hasil terakhir (ikon+teks+bunyi)
├─────────────────────────────────────────────────────────────┤
│ Belum (8) · Cocok (12) · Di luar dokumen (1) · Masalah (0)   │  chip kategori
│ ○ R-…0151  A-R01-T2   58,5 m                                 │  baris ≥ 56 px
│ ✓ R-…1234  A-R01-T3   62,0 m                                 │
├─────────────────────────────────────────────────────────────┤
│ [⋯ Pengecualian]              [   Selesai (12/20)   ] 56 px  │  bilah bawah tetap
└─────────────────────────────────────────────────────────────┘
```

| # | Aturan | Sumber pola |
|---|---|---|
| 1 | Satu tugas per layar, **satu input utama** per langkah; judul + ikon langkah | D365 [MS7] |
| 2 | **Pemindai fisik utama** (tombol pindai C72 [CW1]); kamera hanya cadangan; ketik manual terakhir — mengganti "camera-first" `KN_08:407` | D365 *Scan with camera = No* bila ada pemindai [MS4] |
| 3 | Buka dokumen dengan memindai QR/barcode dokumen atau memilih dari daftar tugas | Odoo [OD5] |
| 4 | Progres **roll dan panjang** (`x/y roll · a/b m`) | Odoo [OD2][OD3]; `QtyDual` |
| 5 | Hasil per bacaan: ikon + judul + teks + bunyi/getar berbeda; tidak hanya warna (sudah di `ScanPanel`) | WCAG 1.4.1 [W1]; D365 [MS4] |
| 6 | Tiga kategori harapan vs terbaca (+ "masalah" untuk status terlarang) — **istilah per konteks yang sudah ada**: opname "Ditemukan / hilang / asing" (`CycleCountPanel`), gate "sudah lewat / belum lewat" (`U300DocSession`) | Zebra [ZB3†]; Checkpoint [RF6†] |
| 7 | Pengecualian (kurang ambil, lokasi lain, label rusak, roll tak terbaca) lewat "⋯" dengan **alasan wajib**, tercatat, izin per peran | D365 [MS8][MS2] |
| 8 | Selesai dengan selisih diperbolehkan → **kuning, masuk antrean periksa, tidak mengunci** | K-RFID-09/10 |
| 9 | Opname: **hitung buta bawaan**, hitung ulang 1×, selisih di atas ambang → persetujuan | D365 [MS14][MS2]; Odoo [OD4] |
| 10 | Mode RFID: tekan pemicu → baca massal → daftar per EPC dengan **jumlah baca & terakhir terlihat**; profil daya bernama; "Cari roll" 0–100 % + bunyi | Zebra [ZB1][ZB2][ZB4†]; Impinj [IM3†] |
| 11 | Offline: daftar tugas dari cache + bilah offline + **jumlah antrean**; pindaian/bacaan antre (idempoten per sesi); **posting yang mengubah stok/dokumen = online-only** | Android [MD6]; Zebra [ZB8] |
| 12 | Daftar tugas: satu antrean "Tugas saya" di cakupan kerja, dikelompokkan per jenis tugas (lencana §3.9), urut prioritas/tenggat; tombol "Tugas berikutnya" + daftar penuh saat diminta | D365 *Display open work list* untuk layar ≥ 7" [MS1], *Show work line list* [MS12] |

### 3.7 Anatomi detail & Aturan Dua Angka Stok (ADS)

**Detail (objek: roll, produk, dokumen)** — pola *object page* [FI2†]: kepala (ID mono `fs-20`, lencana status, 3–4
fakta kunci), aksi kontekstual kanan atas, tab tingkat-2 (`PageTabs`: Ringkasan · Roll · Mutasi · Dokumen · Riwayat
`AuditHistoryPanel`). Dibuka sebagai `DetailModal` (rincian dokumen) atau panel samping `DetailDrawer` (rincian roll dari
tabel, nonmodal [NN4]); di HP layar penuh.

**Aturan Dua Angka Stok**

| ID | Aturan |
|---|---|
| ADS-1 | Setiap angka stok menyebut **cakupannya**: angka **A** = cakupan kerja (lokasi kerja + PT aktif); angka **B** = total (arti persis → K-B4-05). |
| ADS-2 | Satuan utama **roll**, lalu panjang (`QtyDual`); satuan berbeda tidak pernah dijumlahkan (aturan UAT 051 tetap). |
| ADS-3 | Nama angka dari kamus KN_32 (Stok Fisik · Tersedia · Dipesan · Dialokasikan · Karantina · Dalam Perjalanan); definisi di keterangan (pola `availHint`). Definisi "Tersedia" K-04 tidak diubah. |
| ADS-4 | Identitas terlihat: **Stok Fisik = Tersedia + Dipesan + Lainnya** (rincian "Lainnya" seperti `BalancesTable`). |
| ADS-5 | Klik angka → panel rincian dengan pivot: **per lokasi** (site → gedung → zona/bin), **per PT pemilik**, **per status**, dan **akan datang** (Dalam Perjalanan, GRN belum ditempatkan, PO terbuka) — tiap baris menuju daftar roll tersaring. |
| ADS-6 | Rincian roll milik PT/gudang di luar izin tidak dibuka; angka B boleh tampil sebagai agregat (→ K-B4-05). |
| ADS-7 | Stok transit tetap boleh dialokasikan (K-GDG-09) dan ditampilkan sebagai baris berlabel sendiri, bukan disembunyikan. |

```
Tersedia
  42 roll · 2.310 m      di Rancamalang
 118 roll · 6.540 m      seluruh PT saya   ›   (klik → per lokasi · per PT · per status · akan datang)
```
Pola acuan: D365 *Available physical* vs *Total available* + *Dimensions* [MS15]; Odoo On Hand / Free to Use / Forecast
[OD10][OD11]; Zoho [ZO1].

### 3.8 Penampil ribuan roll

| Aspek | Usulan |
|---|---|
| Model data | saring/urut/kelompok/agregat **di server** (pola SSRM [GR3], analytical table [FI11†]); klien merender hanya baris terlihat + buffer (virtualisasi [GR1][GR7][GR8]) bila satu halaman > 200 baris (batas praktis responsive table ±200 [FI9†]) |
| Hierarki bawaan | **Produk › Warna › Lot (dye lot) › Roll**, opsional Grade; grup **tertutup** [GR13] |
| Agregat per grup | jumlah roll · total panjang · panjang tersedia · min–maks panjang · jumlah lokasi |
| Kolom roll | Nomor roll (mono, kiri) · produk + `ProductColorChip` · Lot · Grade · **panjang sisa** (kanan, tabular) + panjang awal kecil · lokasi (gedung-zona-rak-bin) · status (lencana) · PT pemilik · umur (hari) |
| Chip cepat | status · grade · gedung/zona · "sisa < X m" (ambang sisa per produk — pola *Cut Replenishment Length* [IN3]) · "lot campur" |
| Alokasi | satu lot per baris pesanan sebagai bawaan; campur lot = konfirmasi (`MixedLotConfirmModal` yang ada) [TX3†][SAP9] |
| Rincian | panel samping nonmodal (`DetailDrawer`/`RollJourneyPopup`) [NN4] |
| Kinerja | respons saringan < 1 s, selain itu saringan batch + tombol Terapkan [NN2][NN6] |
| HP | kartu terkelompok per lot, "Tampilkan 30 lagi" (pola `UntaggedPanel`), cari dengan memindai |
| Ekspor | dari query server yang sama (bukan dari baris termuat [GR2]) |

### 3.9 Status, chip, lencana jenis tugas

* **Satu komponen `StatusBadge`** {nada, ikon, label}; 6 nada: netral, info, berhasil, perhatian, bahaya, khusus (warna
  §3.2d). Teks ≥ 4,5:1 di latar lembut; ikon selalu ada; maksimal 3 digit angka ("999+") [CB8][AT3][W1]. Menyatukan
  `Pill` (`rfid/rfidShared.jsx`), `status-pill`, `QcStatusBadge`, dan lencana buatan sendiri.
* **Chip saringan ≠ status ≠ tab**: `FilterChips` menyaring, `StatusBadge` menyatakan, `PageTabs` memindah isi (aturan KN).
* **Gate**: hijau = lolos; **merah = pelanggaran, terkunci sampai diakui**; **kuning = perlu diperiksa, barang jalan,
  gate tidak terkunci**; abu = tidak terhubung/offline → tahan (K-RFID-09; label dari `u300Labels.js`). Kios V1
  (`GateLiveVerdict`) perlu keadaan kuning. Kuning kios = `#FFD60A` + teks hitam + ikon.
* **Lencana jenis tugas** (kategori, bukan status): ikon + label jenis tugas **yang sudah dipakai layar terkait** + pita
  kiri warna kategori (biru/ungu/abu/biru tua — bukan hijau/kuning/merah):

| Jenis tugas (label mengikuti layar yang ada) | Ikon (lucide) | Dokumen sumber |
|---|---|---|
| Barang masuk / terima | `PackageCheck` | GRN / PO |
| Penempatan Rak | `MapPin` | Putaway order |
| Keluar (SO) | `ClipboardList` | SO / SJ |
| Sample (potong sampel) | `Scissors` + ungu | SO sampel |
| Potong | `Scissors` | permintaan potong |
| Transfer | `ArrowLeftRight` | transfer antar gudang |
| Stock Opname | `ClipboardCheck` | sesi opname |
| QC | `ShieldCheck` | antrean QC / inspeksi |

### 3.10 Keadaan kosong / memuat / galat

| Keadaan | Aturan | Komponen |
|---|---|---|
| Kosong — belum ada data | ikon + judul satu baris + 1–3 baris penjelasan + **satu aksi utama** [CB10][FI13†] | baru `EmptyState` |
| Kosong — tidak ada hasil saringan | sebut saringan aktif + tombol **Reset saringan** | `EmptyState` |
| Kosong — di luar cakupan/izin | sebut cakupan + **Ganti cakupan** (bila berwenang) | `EmptyState` + `ScopeBar` |
| Memuat < 1 s | tanpa indikator | — |
| Memuat 1–10 s | skeleton untuk tabel/halaman; spinner kecil untuk satu modul/tombol [NN3][CB11] | `ui/skeleton`, `LoadingLine` |
| Memuat > 10 s | progres + Batal; ekspor besar → job + notifikasi [NN2] | `ExportMenu`, `NotificationCenter` |
| Galat | bilah menempel + "Coba lagi" (keputusan P5); kalimat spesifik + langkah berikutnya; isian dipertahankan [NN8][GV4] | `ErrorNotice` |
| Jangan | menampilkan "kosong" saat masih memuat [NN7]; toast untuk galat [FI14†] | — |

### 3.11 Notifikasi

| Saluran | Untuk | Aturan |
|---|---|---|
| Inline | hasil aksi di form/halaman | `ErrorNotice` / `OkNotice`, di dekat sumber |
| Toast | sukses sesaat | hanya sukses [FI14†]; ≥ 5 s atau sampai ditutup [CB9]; nomor dokumen yang perlu disalin → inline, bukan toast |
| Pusat notifikasi | kejadian asinkron (ekspor selesai, tugas baru, alarm gate, persetujuan) | `NotificationCenter` + `navigation_target` (KN_14 §10); hanya **cakupan kerja** penerima |
| Kios gate | lintasan | visual + bunyi; merah tetap sampai diakui dengan catatan; kuning tidak mengunci |
| HP | tugas baru di lokasi kerja | lencana jumlah di tab bawah (maks "99+") |

### 3.12 Label roll 70 × 22 mm

**Ruang**: 70 × 22 mm = 560 × 176 titik @203 dpi; 827 × 260 titik @300 dpi (Lampiran A).

```
┌──────────────────────────────── 70 mm ──────────────────────────────────┐
│ ┌──────────┐  R-2611-001234                 ← nomor roll, tinggi ≥ 3,5 mm │  22
│ │ Data     │  BTK MEGA · NAVY                ← produk · warna, ≥ 2,5 mm  │  mm
│ │ Matrix   │  Lot 7A · Grade A · 62,0 m      ← ≥ 2,5 mm                  │
│ │ 18×18    │  PT … · 09/11/26                ← ≥ 2 mm (opsional)         │
│ └──────────┘                                                              │
└───────────────────────────────────────────────────────────────────────────┘
```

| Aturan | Nilai | Dasar |
|---|---|---|
| Kode utama | **Data Matrix ECC 200 18 × 18** (≤ 25 alfanumerik) berisi nomor roll (dan/atau EPC) | kapasitas [GS11]; hemat tinggi vs QR yang butuh zona sepi 4 modul [GS6†] |
| Ukuran modul | 0,50 mm (4 titik @203 dpi) → simbol 9 mm + zona sepi 1 modul = **10 × 10 mm**; @300 dpi: 6 titik = 0,508 mm | DENSO ≥ 4 titik/modul [GS8]; ukuran titik [ZB9] |
| Code 128 (opsional) | hanya bila ID **numerik** (Set C): 12 digit = 121 modul termasuk zona sepi → 45,4 mm @0,375 mm (3 titik @203) | struktur Code 128 [GS4]; Lampiran A |
| Hindari | GS1-128 logistik (tinggi min 31,75 mm tidak muat) [GS4]; Code 128 alfanumerik 12 karakter pada 203 dpi (butuh modul 0,25 mm = 2 titik) | Lampiran A |
| Teks | nomor roll ≥ 3 mm (≥ 24 titik @203); lainnya ≥ 2 mm | [GS5†][GS12†] |
| Konsistensi | isi Data Matrix dan EPC merujuk identitas yang sama | [GS3†]; K-OPN-05 |
| Encode | gagal encode → label VOID + coba ulang; jumlah VOID per job tampil; **baca balik dengan handheld** sebelum tag "aktif" (sesi `RfidPrintVerifyPanel` yang ada) | Zebra `^RS` [ZB6][ZB7]; perilaku VOID CP30 **belum terverifikasi** (emulasi ZPL-II [CW3]) |
| Media | 22 mm hanya 2 mm di atas tinggi minimum CP30 (20 mm) [CW3]; batas minimum untuk label **ber-inlay** belum diketahui → tanya Chainway | — |
| Kode KN | `generate_rfid_zpl` (4 × 2") dan `generate_qr_zpl` (58 × 40 mm) diganti template 70 × 22 (paket terpisah) | §2.3 |

### 3.13 Pemetaan ke komponen baku

| Komponen | Keputusan | Catatan |
|---|---|---|
| `FormModal`, `FormSection` | **pakai ulang** | ganti label 11 px → `fs-12`; tambah ringkasan galat opsional |
| `KNSelect`, `ProductSelect`, `RollPicker`, `SiteSelect`, `LocationFields` | **pakai ulang** | HP: terima pindaian; tinggi pemicu 48 px di HP |
| `ListPageParts` (`PageHeader`, `MetricRow`, `SearchBox`, `StatusTabs`) | **pakai ulang, jadikan satu-satunya** | `ListControls.jsx` punya `SearchBox` & `StatusTabs` kedua → gabung |
| `FilterChips`, `PageTabs`, `HubTabs` | **pakai ulang** | chip HP 36 px |
| `PaginationBar` | **pakai ulang + perluas** | tambah `ExportMenu` (xlsx + csv); `KNPager` & `PagedRows` dilebur ke sini |
| `ResponsiveTable` | **perluas** | prop `density` (36/32), virtualisasi opsional, kepala & kolom 1 lengket |
| `DetailModal`, `DetailDrawer` | **pakai ulang** | `DetailDrawer` jadi panel samping rincian roll |
| `ErrorNotice`, `OkNotice`, `LoadingLine`, `ui/skeleton` | **pakai ulang** | `ErrorNotice` di HP menempel di atas bilah bawah |
| `QtyDual` | **pakai ulang** | dasar `StockFigure` |
| `PrinterStatusWidget` | **pakai ulang** | ganti warna teks hijau/merah ke token |
| `LocationScopeBadge`, `EntitySwitcher` | **perluas → `ScopeBar`** | bawaan = lokasi kerja + PT aktif |
| `Pill` (`rfidShared`), `QcStatusBadge`, `status-pill` | **ganti → `StatusBadge`** | kontras & ikon wajib |
| **`ScopeBar`** | baru | §3.4 [2] |
| **`StockFigure`** | baru | ADS-1…7, popover/panel rincian |
| **`StatusBadge`**, **`TaskTypeBadge`** | baru | §3.9 |
| **`ExportMenu`** + job server XLSX | baru | §3.4 [9] |
| **`SavedViews`** | baru | butuh koleksi tampilan per pengguna/peran/PT |
| **`EmptyState`** | baru | §3.10 |
| **`ScanTaskScreen`** (HP), **`ExpectedVsReadList`**, **`ScanResultBanner`** | baru | §3.6; mesin sesi yang ada dipakai ulang (U300, verifikasi cetak, opname per roll) |
| **`RollGroupGrid`** | baru | §3.8; endpoint agregat server |

### 3.14 Guardrail terukur & urutan penerapan

| ID | Aturan | Ukuran | Baseline `70eb9fd` | Mode |
|---|---|---|---|---|
| G-UI-01 | Huruf hanya dari skala §3.2a; tidak < 12 px | `text-[Npx]` & `font-size: Npx` | 21 ukuran · 8.863 pemakaian · 6.760 < 12 px | ratchet per berkas (`_ratchet.py`); berkas baru = 0 |
| G-UI-02 | Warna hanya token | literal hex di .js/.jsx | 712 hex berbeda | ratchet |
| G-UI-03 | Pasangan token lolos kontras | skrip rasio WCAG (Lampiran A) atas tabel §3.2d | 7 pasangan gagal (§2.2) | keras |
| G-UI-04 | Tombol hanya kelas baku | `<button>` tanpa kelas baku / `ui/button` | 390 (koordinator) | ratchet |
| G-UI-05 | Target HP ≥ 48 px | di `features/mobile` & layar kelas B: larang `py-0.5`, `btn-xs`, `!py-0.5` pada elemen interaktif | dihitung saat penjaga dibuat | ratchet |
| G-UI-06 | Status tidak warna saja | `StatusBadge` wajib `label`; `Pill` tanpa teks | — | keras untuk berkas baru |
| G-UI-07 | Ekspor Excel | perluasan INV-UI-07: `exportConfig` wajib xlsx + csv, ikut saringan & cakupan | CSV saja | keras setelah `ExportMenu` ada |
| G-UI-08 | Cakupan terlihat | layar daftar gudang wajib `ScopeBar` | — | keras untuk layar gudang |
| G-UI-09 | Lebar 360 & 390 px | crawl peramban (paket B1/UAT): tanpa gulir horizontal halaman | — | gate visual |

**Urutan penerapan yang disarankan** (paket implementasi terpisah, bukan bagian B4):
1. Keputusan pemilik §5 → `KN_08` ditandai digantikan untuk lingkup §3.0.
2. Token (`tokens.css` + skala `fontSize`/warna di `tailwind.config.js`), perbaikan kontras tombol/isian/`Pill`, pasang
   G-UI-01…04 sebagai ratchet (hanya boleh turun).
3. `StatusBadge`, `ScopeBar`, `StockFigure`, `EmptyState`, `ExportMenu` (+ job XLSX), peleburan pager & kotak cari.
4. `ScanTaskScreen` + jenis tugas di HP (setelah ukur C72, K-B4-04).
5. `RollGroupGrid` + endpoint agregat server.
6. Template label 70 × 22 + uji baca C72 (setelah K-B4-10).

---

## 4. Daftar sumber (semua diakses 2026-11-09)

Status: **dibaca** = halaman dibuka dan dibaca; **cuplikan** (†) = hanya dari cuplikan hasil pencarian.

**Microsoft Dynamics 365 Supply Chain Management (learn.microsoft.com)**

| Kode | Judul | URL | Status |
|---|---|---|---|
| MS1 | Configure mobile devices for warehouse work | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/configure-mobile-devices-warehouse | dibaca |
| MS2 | Mobile device user accounts | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/mobile-device-work-users | dibaca |
| MS3 | Install and configure the Warehouse Management mobile app | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/install-configure-warehouse-management-app | dibaca |
| MS4 | Warehouse app user settings and themes | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/warehouse-app-user-settings-themes | dibaca |
| MS5 | Mobile device user settings | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/mobile-device-user-settings | dibaca |
| MS6 | Warehouse app accessibility | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/warehouse-app-accessibility | cuplikan † |
| MS7 | Step icons and titles | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/step-icons-titles | dibaca |
| MS8 | Work exceptions log | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/work-exceptions-log | dibaca |
| MS9 | Control warehouse location directives | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/control-warehouse-location-directives | dibaca |
| MS10 | Create location directive | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/create-location-directive | dibaca |
| MS11 | Set up cluster picking | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/set-up-cluster-picking | dibaca |
| MS12 | Pick line overview | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/pick-line-overview | dibaca |
| MS13 | Quality check | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/quality-check | dibaca |
| MS14 | Cycle counting | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/cycle-counting | dibaca |
| MS15 | Inventory on-hand list | https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/inventory-on-hand-list | dibaca |
| MS16 | Inventory statuses | https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/inventory-statuses | dibaca |
| MS17 | Quality management for warehouse processes | https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/quality-management-for-warehouses-processes | dibaca |
| MS18 | Saved views | https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/fin-ops/get-started/saved-views | dibaca |
| MS19 | Office integration troubleshooting (Export to Excel) | https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/office-integration/office-integration-troubleshooting | dibaca |
| MS20 | Warehouse app network diagnostics | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/warehouse-app-network-diagnostics | dibaca |
| MS21 | Release plan: Warehouse Management mobile app v4 | https://learn.microsoft.com/en-us/dynamics365/release-plan/2025wave1/finance-supply-chain/dynamics365-supply-chain-management/improve-operations-warehouse-management-mobile-app-v4 | dibaca |
| MS22 | Wave templates | https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/wave-templates | cuplikan † |
| MS23 | AI Builder: use the document processing model in Power Automate (skor keyakinan) | https://learn.microsoft.com/en-us/ai-builder/form-processing-model-in-flow | dibaca |

**Odoo (odoo.com/documentation)**

| Kode | Judul | URL | Status |
|---|---|---|---|
| OD1 | Barcode: receipts and deliveries | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/operations/receipts_deliveries.html | dibaca |
| OD2 | Barcode: process transfers | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/operations/process_transfers.html | dibaca |
| OD3 | Barcode: GS1 usage | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/operations/gs1_usage.html | dibaca |
| OD4 | Barcode: inventory adjustments | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/operations/adjustments.html | dibaca |
| OD5 | Barcode: operation types | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/setup/operation_types.html | dibaca |
| OD6 | Barcode: lots and serial numbers | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/setup/serial_numbers_lots.html | dibaca |
| OD7 | Barcode: transfers from scratch | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/barcode/operations/transfers_scratch.html | dibaca |
| OD8 | Putaway rules | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/shipping_receiving/daily_operations/putaway.html | dibaca |
| OD9 | Wave transfers | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/shipping_receiving/picking_methods/wave.html | dibaca |
| OD10 | Stock report | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/warehouses_storage/reporting/stock.html | dibaca |
| OD11 | Forecasted report | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/warehouses_storage/reporting/forecast.html | dibaca |
| OD12 | Cycle counts | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/warehouses_storage/inventory_management/cycle_counts.html | dibaca |
| OD13 | Count products | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/warehouses_storage/inventory_management/count_products.html | dibaca |
| OD14 | Quality control points | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/quality/quality_management/quality_control_points.html | dibaca |
| OD15 | Failure locations | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/quality/quality_management/failure_locations.html | dibaca |
| OD16 | Users (Allowed/Default Company) | https://www.odoo.com/documentation/18.0/applications/general/users.html | dibaca |
| OD17 | Multi-company | https://www.odoo.com/documentation/18.0/applications/general/companies/multi_company.html | dibaca |
| OD18 | Default warehouse (v16) | https://www.odoo.com/documentation/16.0/applications/services/field_service/default_warehouse.html | dibaca |
| OD19 | Search, filter, and group records | https://www.odoo.com/documentation/18.0/applications/essentials/search.html | dibaca |
| OD20 | Export and import data | https://www.odoo.com/documentation/18.0/applications/essentials/export_import_data.html | dibaca |
| OD21 | Lots (v19) | https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/product_management/product_tracking/lots.html | dibaca |
| OD22 | Units of measure (v19) | https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/product_management/configure/uom.html | dibaca |
| OD23 | Batch & cluster picking | https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/shipping_receiving/picking_methods/batch.html · …/cluster.html | cuplikan † |
| OD24 | Document digitization (OCR → draf) | https://www.odoo.com/documentation/18.0/applications/finance/accounting/vendor_bills/invoice_digitization.html | dibaca |

**SAP (help.sap.com, learning.sap.com) dan SAP Fiori / UI5**

| Kode | Judul | URL | Status |
|---|---|---|---|
| SAP1 | Stock types (4.6C) | https://help.sap.com/saphelp_46C/helpdata/EN/12/085d9e470311d1894a0000e8323352/content.htm | dibaca |
| SAP2 | EWM stock types F1/F2, Q1/Q2, B1/B2 | https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/2d95c3180a974e0aad07556ee4d28e94/db60b6531de6b64ce10000000a174cb4.html | cuplikan † |
| SAP3 | EWM RF framework (layar 8 × 40) | https://help.sap.com/doc/saphelp_ewm900/9.0/en-US/4d/4fa477c9c20c7ae10000000a42189c/content.htm?no_cache=true | dibaca |
| SAP4 | Using mobile devices (display & verification profile) | https://learning.sap.com/courses/resource-management-in-sap-ewm/using-mobile-devices | dibaca |
| SAP5 | Optimizing the work of resources (queue, interleaving) | https://learning.sap.com/courses/resource-management-in-sap-ewm/optimizing-the-work-of-resources | dibaca |
| SAP6 | Analytical apps for inventory management | https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/using-analytical-apps-for-inventory-management | dibaca |
| SAP7 | Quality management in warehousing | https://learning.sap.com/courses/implementing-sap-s-4hana-cloud-public-edition-warehouse-management/introducing-quality-management-in-warehousing_ead9d6f0-625c-4f6c-86bf-814be08a7715 | dibaca |
| SAP8 | Batch determination | https://help.sap.com/saphelp_46c/helpdata/en/4d/2b8c0443ad11d189410000e829fbbd/content.htm | dibaca |
| SAP9 | Batch selection & sort sequence (contoh) | https://help.sap.com/saphelp_470/helpdata/EN/25/283ae04f7811d18a150000e816ae6e/content.htm | dibaca |
| SAP10 | SAP Fashion Management: segmentation & batch determination | https://help.sap.com/saphelp_fms108/helpdata/en/0f/e5e654c9d7d877e10000000a423f68/content.htm | dibaca |
| SAP11 | Mill products: length characteristic | https://help.sap.com/saphelp_erp60_sp/helpdata/en/37/cfc353b677b44ce10000000a174cb4/content.htm | cuplikan † |
| FI1 | Fiori: List report floorplan | https://www.sap.com/design-system/fiori-design-web/v1-139/page-types/floorplans/list-report-floorplan-sap-fiori-element/usage | cuplikan † |
| FI2 | Fiori: When to use which floorplan | https://www.sap.com/design-system/fiori-design-web/v1-145/page-types/floorplans/when-to-use-which-floorplan | cuplikan † |
| FI4 | Fiori: Cozy and compact | https://www.sap.com/design-system/fiori-design-web/v1-151/foundations/visual/cozy-compact | cuplikan † |
| FI5 | UI5: Content densities | https://ui5.github.io/docs/04_Essentials/content-densities-e54f729.html | dibaca |
| FI6 | Launchpad: content density default | https://help.sap.com/saphelp_uiaddon20/helpdata/en/a0/83c2cda662496c86e8cd509848e8c3/content.htm | dibaca |
| FI7 | Fiori: Filter bar | https://www.sap.com/design-system/fiori-design-web/v1-148/ui-elements/filter-bar/usage | cuplikan † |
| FI8 | Fiori: Variant management | https://www.sap.com/design-system/fiori-design-web/v1-139/ui-elements/variant-management/usage | cuplikan † |
| FI9 | Fiori: Grid table | https://www.sap.com/design-system/fiori-design-web/v1-142/ui-elements/grid-table/usage | cuplikan † |
| FI11 | Fiori: Analytical table | https://www.sap.com/design-system/fiori-design-web/v1-148/ui-elements/analytical-table-alv/usage | cuplikan † |
| FI12 | Fiori: Export to spreadsheet | https://www.sap.com/design-system/fiori-design-web/v1-151/ui-elements/export-to-spreadsheet/usage | cuplikan † |
| FI13 | Fiori: Illustrated message | https://www.sap.com/design-system/fiori-design-web/v1-148/ui-elements/illustrated-message/usage | cuplikan † |
| FI14 | Fiori: Message toast | https://www.sap.com/design-system/fiori-design-web/v1-145/ui-elements/message-toast/usage | cuplikan † |
| FI16 | Fiori: How to use semantic colors | https://www.sap.com/design-system/fiori-design-web/v1-139/foundations/best-practices/ui-elements/how-to-use-semantic-colors | cuplikan † |

**Oracle, NetSuite, Zoho, Infor, vendor lain, tekstil**

| Kode | Judul | URL | Status |
|---|---|---|---|
| OR1 | Oracle WMS Cloud: RF Execute Task | https://docs.oracle.com/en/cloud/saas/warehouse-management/26b/owmim/exectue-task.html | dibaca |
| OR2 | Oracle WMS Cloud: Lock codes | https://docs.oracle.com/en/cloud/saas/warehouse-management/25d/owmim/lock-codes.html | dibaca |
| OR3 | NetSuite: Inventory status | https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1515696627.html | dibaca |
| OR4 | NetSuite WMS: multi-order picking | https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1541442950.html | cuplikan † |
| OR5 | Oracle JET: Scale and density | https://docs.oracle.com/en/middleware/developer-tools/jet/19/reference-api/ScaleAndDensity.html | dibaca |
| ZO1 | Zoho Inventory: stock tracking mode | https://www.zoho.com/us/inventory/kb/items/stock-tracking-mode.html | dibaca |
| ZO2 | Zoho Inventory: Export Current View | https://www.zoho.com/us/inventory/help/vendor-credits/manage.html | dibaca |
| IN1 | Infor WMS: task interleaving | https://docs.infor.com/wms/11.5.x/en-us/sceolh/gkk1612894202696.html | dibaca |
| IN2 | Infor WMS: lottables (tekstil per dye lot) | https://docs.infor.com/wms/2026.x/en-us/wmsolh/item_lottable.html | dibaca |
| IN3 | Infor CloudSuite Distribution: linear cut | https://docs.infor.com/csdis/latest/en-us/useradminlib_csd_cloud/icolh/oez1643152007148.html | dibaca |
| IN4 | Infor CloudSuite Fashion (produk) | https://www.infor.com/products/cloudsuite-fashion | dibaca |
| VN1 | Blue Yonder: warehouse execution | https://blueyonder.com/solutions/warehouse-management/warehouse-execution | cuplikan † |
| VN2 | Manhattan Active Labor Management | https://www.manh.com/products/manhattan-active-labor-management | cuplikan † |
| VN3 | Körber WMS | https://koerber-supplychain.com/supply-chain-solutions/supply-chain-software/warehouse-management/ | cuplikan † |
| TX1 | Datatex: inventory | https://datatex.com/portfolio-items/inventory | cuplikan † |
| TX2 | RFMS: roll fields | https://rfmsinc.zendesk.com/hc/en-us/articles/360047551214 | cuplikan † |
| TX3 | RFMS: batch inventory allocator by dye lot | https://rfms.support.cyncly.com/hc/en-us/articles/50197304598545-Batch-Inventory-Allocator-and-Batch-Inventory-Allocator-by-Dye-Lot | cuplikan † |
| TX4 | ASTM D5430-26 (abstrak) | https://store.astm.org/d5430-26.html | dibaca |
| TX5 | V-Trust: tabel 4-point (sekunder) | https://www.v-trust.com/en/our-services/inspection-standards/other-reference-standards | dibaca |
| TX6 | V-Trust: rumus 4-point (sekunder) | https://www.v-trust.com/en/blog/understanding-the-4-point-system-for-fabric-inspections | dibaca |
| TX7 | AATCC Gray Scale | https://members.aatcc.org/4DCGI/productinfo/Gray%20Scale.htm | dibaca |
| TX8 | ISO 105-J03:2009 (CMC) | https://www.iso.org/standard/51385.html | cuplikan † |

**Sistem desain**

| Kode | Judul | URL | Status |
|---|---|---|---|
| FL1 | Fluent 2: Typography | https://fluent2.microsoft.design/typography | dibaca |
| FL2 | Fluent 2: Layout (spasi, target sentuh) | https://fluent2.microsoft.design/layout | dibaca |
| FL3 | Fluent 2: Shapes (radius) | https://fluent2.microsoft.design/shapes | dibaca |
| FL4 | Fluent UI React button styles (kode 9.3.75) | https://cdn.jsdelivr.net/npm/@fluentui/react-button@9.3.75/lib/components/Button/useButtonStyles.styles.js | dibaca |
| CB1 | Carbon: Type sets | https://carbondesignsystem.com/elements/typography/type-sets/ | dibaca |
| CB2 | Carbon: Spacing | https://carbondesignsystem.com/elements/spacing/overview/ | dibaca |
| CB3 | Carbon: Button style | https://carbondesignsystem.com/components/button/style/ | dibaca |
| CB4 | Carbon: Button usage | https://carbondesignsystem.com/components/button/usage/ | dibaca |
| CB5 | Carbon: Text input style | https://carbondesignsystem.com/components/text-input/style/ | dibaca |
| CB6 | Carbon: Data table style | https://carbondesignsystem.com/components/data-table/style/ | dibaca |
| CB7 | Carbon: Data table usage | https://carbondesignsystem.com/components/data-table/usage/ | dibaca |
| CB8 | Carbon: Status indicator pattern | https://carbondesignsystem.com/patterns/status-indicator-pattern/ | dibaca |
| CB9 | Carbon: Notification usage | https://carbondesignsystem.com/components/notification/usage/ | dibaca |
| CB10 | Carbon: Empty states pattern | https://carbondesignsystem.com/patterns/empty-states-pattern/ | dibaca |
| CB11 | Carbon: Loading pattern | https://carbondesignsystem.com/patterns/loading-pattern/ | dibaca |
| CB12 | Carbon: Filtering pattern | https://carbondesignsystem.com/patterns/filtering/ | dibaca |
| CB13 | Carbon: Forms pattern | https://carbondesignsystem.com/patterns/forms-pattern/ | dibaca |
| CB14 | Carbon v10: Export pattern | https://v10.carbondesignsystem.com/community/patterns/export-pattern | dibaca |
| AT1 | Atlassian: Spacing | https://atlassian.design/foundations/spacing | dibaca |
| AT2 | Atlassian: Typography | https://atlassian.design/foundations/typography | dibaca |
| AT3 | Atlassian: Lozenge | https://atlassian.design/components/lozenge/usage | dibaca |
| MD1 | Material 3 type scale tokens (androidx) | https://android.googlesource.com/platform/frameworks/support/+/refs/heads/androidx-main/compose/material3/material3/src/commonMain/kotlin/androidx/compose/material3/tokens/TypeScaleTokens.kt | dibaca |
| MD2 | Material 3 filter chip tokens (androidx) | https://android.googlesource.com/platform/frameworks/support/+/refs/heads/androidx-main/compose/material3/material3/src/commonMain/kotlin/androidx/compose/material3/tokens/FilterChipTokens.kt | dibaca |
| MD3 | Android: Make apps more accessible | https://developer.android.com/guide/topics/ui/accessibility/apps | dibaca |
| MD4 | Google: touch target size | https://support.google.com/accessibility/android/answer/7101858?hl=en | dibaca |
| MD5 | Material Components web: density | https://cdn.jsdelivr.net/npm/@material/density@14.0.0/README.md | dibaca |
| MD6 | Android: Build an offline-first app | https://developer.android.com/topic/architecture/data-layer/offline-first | dibaca |
| AP1 | Apple HIG: Accessibility | https://developer.apple.com/design/human-interface-guidelines/accessibility | dibaca (via data JSON resmi) |
| AP2 | Apple HIG: Typography | https://developer.apple.com/design/human-interface-guidelines/typography | dibaca (via data JSON resmi) |
| GV1 | GOV.UK: Question pages | https://design-system.service.gov.uk/patterns/question-pages/ | dibaca |
| GV2 | GOV.UK: Validation | https://design-system.service.gov.uk/patterns/validation/ | dibaca |
| GV3 | GOV.UK: Error summary | https://design-system.service.gov.uk/components/error-summary/ | dibaca |
| GV4 | GOV.UK: Error message | https://design-system.service.gov.uk/components/error-message/ | dibaca |
| GV5 | GOV.UK: Text input | https://design-system.service.gov.uk/components/text-input/ | dibaca |
| GV6 | GOV.UK: Button | https://design-system.service.gov.uk/components/button/ | dibaca |
| GV7 | GOV.UK: Table | https://design-system.service.gov.uk/components/table/ | dibaca |

**Standar W3C & riset UX**

| Kode | Judul | URL | Status |
|---|---|---|---|
| W1 | WCAG 2.2 (Recommendation) | https://www.w3.org/TR/WCAG22/ | dibaca |
| W2 | Understanding 2.5.8 Target Size (Minimum) | https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html | dibaca |
| W3 | Understanding 1.4.3 Contrast (Minimum) | https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html | dibaca |
| W4 | Understanding 1.4.11 Non-text Contrast | https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html | dibaca |
| W5 | Understanding 1.4.10 Reflow | https://www.w3.org/WAI/WCAG22/Understanding/reflow.html | dibaca |
| W6 | Understanding 1.4.1 Use of Color | https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html | dibaca |
| W7 | Understanding 2.4.11 Focus Not Obscured (Minimum) | https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html | dibaca |
| W8 | Understanding 3.3.7 Redundant Entry | https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html | dibaca |
| NN1 | NN/g: 10 Usability Heuristics | https://www.nngroup.com/articles/ten-usability-heuristics/ | dibaca |
| NN2 | NN/g: Response times — 3 important limits | https://www.nngroup.com/articles/response-times-3-important-limits/ | dibaca |
| NN3 | NN/g: Skeleton screens | https://www.nngroup.com/articles/skeleton-screens/ | dibaca |
| NN4 | NN/g: Data tables | https://www.nngroup.com/articles/data-tables/ | dibaca |
| NN5 | NN/g: Mobile tables | https://www.nngroup.com/articles/mobile-tables/ | dibaca |
| NN6 | NN/g: Applying filters | https://www.nngroup.com/articles/applying-filters/ | dibaca |
| NN7 | NN/g: Empty state design | https://www.nngroup.com/articles/empty-state-interface-design/ | dibaca |
| NN8 | NN/g: Error message guidelines | https://www.nngroup.com/articles/error-message-guidelines/ | dibaca |
| NN9 | NN/g: Touch target size | https://www.nngroup.com/articles/touch-target-size/ | dibaca |
| NN10 | NN/g: Pagination vs View All | https://www.nngroup.com/articles/item-list-view-all/ | dibaca |
| NN11 | NN/g: Infinite scrolling tips | https://www.nngroup.com/articles/infinite-scrolling-tips/ | dibaca |
| NN12 | NN/g: Filters vs facets | https://www.nngroup.com/articles/filters-vs-facets/ | dibaca |
| NN13 | NN/g: Minimize cognitive load (Whitenton, 2013) | https://www.nngroup.com/articles/minimize-cognitive-load/ | dibaca |
| RS1 | Parhi, Karlson & Bederson (MobileHCI 2006): target size for one-handed thumb use | https://www.microsoft.com/en-us/research/?p=155150 (DOI 10.1145/1152215.1152260) | dibaca |
| RS2 | Hoober (2013): How do users really hold mobile devices? | https://www.uxmatters.com/mt/archives/2013/02/how-do-users-really-hold-mobile-devices.php | dibaca |
| RS3 | Hoober (2017): Design for fingers, touch, and people, part 3 | https://www.uxmatters.com/mt/archives/2017/07/design-for-fingers-touch-and-people-part-3.php | dibaca |
| RS4 | Ray, Michelson, Price & Fausset (DUXU 2016): touchscreen dengan sarung tangan (rujukan MIL-STD-1472) | https://researchr.org/publication/RayMPF16 | cuplikan † |

**Grid data & ekspor**

| Kode | Judul | URL | Status |
|---|---|---|---|
| GR1 | AG Grid: DOM virtualisation | https://www.ag-grid.com/javascript-data-grid/dom-virtualisation/ | dibaca |
| GR2 | AG Grid: Row models | https://www.ag-grid.com/javascript-data-grid/row-models/ | dibaca |
| GR3 | AG Grid: Server-side row model | https://www.ag-grid.com/javascript-data-grid/server-side-model/ | dibaca |
| GR4 | AG Grid: Aggregation | https://www.ag-grid.com/javascript-data-grid/aggregation/ | dibaca |
| GR5 | AG Grid: CSV export | https://www.ag-grid.com/javascript-data-grid/csv-export/ | dibaca |
| GR6 | AG Grid: Excel export | https://www.ag-grid.com/javascript-data-grid/excel-export/ | dibaca |
| GR7 | TanStack Virtual: introduction | https://tanstack.com/virtual/latest/docs/introduction | dibaca |
| GR8 | TanStack Table: virtualization guide | https://tanstack.com/table/latest/docs/framework/react/guide/virtualization | dibaca |
| GR9 | MUI X Data Grid: virtualization | https://mui.com/x/react-data-grid/virtualization/ | dibaca |
| GR10 | MUI X Data Grid: export | https://mui.com/x/react-data-grid/export/ | dibaca |
| GR11 | AG Grid: Row height | https://www.ag-grid.com/javascript-data-grid/row-height/ | dibaca |
| GR12 | MUI X Data Grid: Row height | https://mui.com/x/react-data-grid/row-height/ | dibaca |
| GR13 | AG Grid: Row grouping | https://www.ag-grid.com/javascript-data-grid/grouping/ | dibaca |
| EX1 | Microsoft: Keeping leading zeros and large numbers | https://support.microsoft.com/en-us/office/keeping-leading-zeros-and-large-numbers-1bf7b935-36e1-4985-842f-5dfa51f85fe7 | dibaca |
| EX2 | Microsoft: Import or export text (.txt/.csv) | https://support.microsoft.com/en-us/office/import-or-export-text-txt-or-csv-files-5250ac4c-663c-47ce-937b-339e391393ba | dibaca |
| EX3 | Microsoft: Opening CSV UTF-8 files correctly in Excel | https://support.microsoft.com/en-us/office/opening-csv-utf-8-files-correctly-in-excel-8a935af5-3416-4edd-ba7e-3dfd2bc4a032 | dibaca |
| EX4 | Microsoft: Excel specifications and limits | https://support.microsoft.com/en-us/office/excel-specifications-and-limits-1672b34d-7043-467e-8e27-269d656771c3 | dibaca |
| EX5 | ExcelJS README (streaming writer) | https://raw.githubusercontent.com/exceljs/exceljs/master/README.md | dibaca |
| EX6 | OWASP: CSV injection | https://community.owasp.org/attacks/CSV_Injection | dibaca |

**RFID, perangkat, label**

| Kode | Judul | URL | Status |
|---|---|---|---|
| CW1 | Chainway C72 (halaman produk) | https://www.chainway.net/Products/Info/42 | dibaca, diverifikasi ulang |
| CW2 | Chainway: berita C72 (angka berbeda) | https://www.chainway.net/News/Info/59 | dibaca |
| CW3 | Chainway CP30 RFID printer | https://chainway.net/Products/Info/138 | dibaca, diverifikasi ulang |
| ZB1 | Zebra 123RFID Mobile: RFID operations | https://docs.zebra.com/content/tcm/us/en/rfid/bm-123-rfid-mobile-application-user-guide-ditamap/123rfid-mobile-application/rfid-operations.html | dibaca |
| ZB2 | Zebra 123RFID Mobile: RFID settings (profil) | https://docs.zebra.com/content/tcm/us/en/rfid/bm-123-rfid-mobile-application-user-guide-ditamap/123rfid-mobile-application/settings/rfid-settings.html | dibaca |
| ZB3 | Zebra 123RFID Mobile: Tag List Match mode | https://docs.zebra.com/us/en/rfid/123rfid-mobile-application-user-guide/c-123rfid-mobile-application/c-123rfid-mobile-rfid--operations/c-123rfid-mobile-inventory/c-123rfid-mobile-tag-list-match-mode-operation.html | cuplikan † |
| ZB4 | Zebra 123RFID Mobile: Locate tag | https://docs.zebra.com/us/en/rfid/123rfid-mobile-application-user-guide/c-123rfid-mobile-application/c-123rfid-mobile-rfid--operations/c-123rfid-mobile-locate-tag.html | cuplikan † |
| ZB5 | Zebra DataWedge: RFID input | https://techdocs.zebra.com/datawedge/latest/guide/input/rfid/ | dibaca |
| ZB6 | Zebra ZPL: ^RS (RFID setup, VOID) | https://docs.zebra.com/us/en/printers/software/zpl-pg/c-zpl-rfid-zpl-rfid-commands/r-zpl-rfid-rs.html | dibaca |
| ZB7 | Zebra ZT231: RFID issues | https://docs.zebra.com/us/en/printers/industrial/zt231-industrial-printer-user-guide/c-zt4x1-troubleshoot/c-zt4x1-troubleshooting/r-zt4x1-rfid-issues.html | dibaca |
| ZB8 | Zebra blog: offline workflows with SAP mobile apps (2024) | https://www.zebra.com/us/en/blog/posts/2024/how-to-enable-offline-workflows-transactions-with-sap-mobile-apps.html | dibaca |
| ZB9 | Zebra ZT211: print specifications (ukuran titik) | https://docs.zebra.com/us/en/printers/industrial/zt211-industrial-printer-user-guide/r-2x1-specifications/r-zt2x1-print-specifications.html | dibaca |
| IM1 | Impinj: Item-level verification with Gen2X | https://www.impinj.com/library/blog/item-level-verification-with-gen2x | dibaca |
| IM2 | Impinj: Gen2X expands enterprise use cases (2025) | https://impinj.com/about-us/news-room/2025/impinj-expands-gen2x-to-unlock-new-enterprise-rain-rfid-use-cases | dibaca |
| IM3 | Impinj: Unlocking enterprise use cases with Gen2X (3Q25, PDF) | https://impinj.com/getmedia/2e03493d-ce91-4544-8404-c74733406deb/Unlocking-Enterprise-Use-Cases-with-Gen2X-3Q25-(1).pdf?ext=.pdf | cuplikan † |
| RF1 | Nedap: Virtual Shielding | https://www.nedap.com/en/retail/inventory-engine/articles/virtual-shielding-explaining-id-clouds-smart-allocaion-algorithm | dibaca |
| RF2 | GS1 US: Project Zipper executive summary (PDF) | https://documents.gs1us.org/adobe/assets/deliver/urn:aaid:aem:a8d86484-ffce-498d-8c59-fc1223437d58/Case-Study-Executive-Summary-EPC-RFID-Retail-Supply-Chain-Data-Exchange-Study.pdf | cuplikan † |
| RF3 | Hardgrave, Aloysius & Goyal (2013), POMS 22(4) | https://zendy.io/title/10.1111/poms.12010 | cuplikan † (abstrak) |
| RF4 | Auburn RFID Lab: item-level quantity auditing | https://rfid.auburn.edu/papers/pages/RFIDItem-levelQuantityAuditingforApparelSupplierDistributionCenters.php | dibaca |
| RF5 | Avery Dennison: inbound & outbound verification | https://www.averydennison.com/na/en/industries/apparel/solutions/supply-chain-solutions/inbound-and-outbound-verification | dibaca |
| RF6 | Checkpoint Systems: RFID (read vs expected) | https://view.ceros.com/checkpoint-systems/rfid | cuplikan † |
| GS1 | GS1 EPC Tag Data Standard: arsip versi | https://ref.gs1.org/standards/tds/archive | dibaca |
| GS2 | GS1: Serialisation considerations when encoding EPC | https://support.gs1.org/support/solutions/articles/43000740229-serialisation-considerations-when-encoding-epc-on-rain-rfid-tags | dibaca |
| GS3 | GS1: RFID/Barcode Interoperability Guidelines (PDF) | https://www.gs1.org/docs/barcodes/RFID_Barcode_Interoperability_Guidelines.pdf | cuplikan † |
| GS4 | GS1 Sweden: barcode size guide (GS1-128) | https://gs1.se/en/guides/how-to-guides/size-guide/ | dibaca |
| GS5 | GS1 Logistic Label Guideline | https://www.gs1.org/standards/gs1-logistic-label-guideline/current-standard | cuplikan † |
| GS6 | GS1 2D colour guide (zona sepi) | https://ref.gs1.org/docs/2025/GS1-2D-colour-guide-i10-f-25-02-10 | cuplikan † |
| GS8 | DENSO WAVE: QR cell (module) size | https://www.qrcode.com/en/howto/cell.html | dibaca |
| GS9 | DENSO WAVE: QR versions | https://www.qrcode.com/en/about/version.html | dibaca |
| GS10 | DENSO WAVE: rMQR (ISO/IEC 23941:2022) | https://www.denso-wave.com/en/adcd/info/detail__220525.html | dibaca |
| GS11 | Loftware: Data Matrix properties (kapasitas) | https://help.loftware.com/enterprise_sp/Content/Design/Barcodes/RefDataMatrixProperties.htm | dibaca |
| GS12 | GS1 UK: QR codes powered by GS1 — design guidelines | https://www.gs1uk.org/standards-services/get-market-ready/qr-codes-powered-by-gs1/design-guidelines | cuplikan † |

Jumlah: **205 sumber** (170 dibaca, 35 cuplikan †) — semuanya dirujuk di badan laporan.

---

## 5. Butir yang butuh keputusan pemilik + rekomendasi

| ID | Pertanyaan | Pilihan | Rekomendasi & alasan |
|---|---|---|---|
| **K-B4-01** | Apakah "Standar UI Gudang v1" (§3) dijadikan acuan wajib untuk layar gudang/HP/RFID dan menggantikan bagian `KN_08` yang bertentangan? | (a) ya, ditegakkan guardrail ratchet · (b) ya, sebagai panduan tanpa guardrail · (c) tidak | **(a)**. `KN_08` sudah tidak sesuai kode (font, warna, radius, "camera-first") dan tidak ditegakkan; ratchet KN (`_ratchet.py`) hanya memaksa angka turun, tidak memaksa bongkar massal. |
| **K-B4-02** | Skala huruf 6 ukuran dengan minimum 12 px (desktop) dan 16/14 px (HP)? Teks 10–11,5 px (6.760 pemakaian) akan membesar. | (a) ya, bertahap · (b) ya, minimum 11 px dulu · (c) tidak | **(a)**: berkas baru langsung patuh; layar HP & gudang dulu; layar lain saat disentuh. Minimum 12 px sejalan dengan Carbon, Atlassian, Fluent [CB1][AT2][FL1]. |
| **K-B4-03** | Ganti warna isian tombol utama `#007AFF` → `#0058CC`, tombol bahaya `#FF3B30` → `#B42318`, larang teks `#8E8E93`/`#9A9BA3`, batas isian `#8A8A8E`? Tampilan tombol jadi sedikit lebih gelap. | (a) ya · (b) tidak (tetap gagal WCAG AA) | **(a)**: tombol utama sekarang 4,02:1 dan tombol bahaya 3,55:1 (gagal 1.4.3); `#0058CC` sudah warna teks aksi KN (1.514 pemakaian). |
| **K-B4-04** | Lebar acuan HP: tambahkan **360 px** selain 390 px? Perlu satu pengukuran `window.innerWidth` di C72 (Chrome/WebView) dan pilihan "Ukuran tampilan" per perangkat. | (a) ukur dulu, sementara uji 360 & 390 · (b) tetap 390 | **(a)**: C72 1920 × 1080 / 5,2" kemungkinan 360 atau 411 px; bila 360, layar "layak 390" bisa terpotong. Pengukuran ±5 menit. |
| **K-B4-05** | Angka **B** ("global/benar-benar total") berarti: (a) semua gudang & PT **yang boleh dilihat** pengguna, atau (b) **total seluruh grup** termasuk PT/gudang di luar izin (angka agregat saja, rincian tidak dibuka)? | (a) · (b) | **(b) untuk peran sales/admin/manajer, (a) untuk peran gudang** — sesuai keinginan "benar-benar total" tanpa membuka roll PT lain (roll milik PT masing-masing, K-GDG-07). Butuh konfirmasi karena menyangkut kebijakan akses data. |
| **K-B4-06** | Komponen stok baru (`StockFigure`) memakai kosakata mana? Saat ini dua kosakata hidup: KN_32 (**Stok Fisik / Tersedia / Dipesan**, kartu & tabel stok) dan `SalesStockSummary` (**Fisik / Dikunci / Bebas / Datang / ATP**). | (a) kamus KN_32 · (b) kosakata Sales · (c) keduanya per peran | **(a)**: kamus KN_32 yang ditegakkan gate i18n; layar lama **tidak diubah** sampai pemilik memutuskan (K-13). |
| **K-B4-07** | Ekspor Excel: **XLSX bawaan + CSV tetap**, mengikuti saringan & cakupan, lembar "Info", ≤ 50.000 baris langsung, lebih besar lewat job server + notifikasi? | (a) ya · (b) CSV saja | **(a)**: keinginan pemilik "ekspor Excel"; D365 memakai batas bawaan yang sama [MS19]; job server menghindari ekspor parsial dari model server [GR2]. |
| **K-B4-08** | Stock opname di HP: **hitung buta** sebagai bawaan (angka harapan tidak ditampilkan)? | (a) ya, setelan per gedung · (b) tidak | **(a)** + hitung ulang 1× + persetujuan di atas ambang (pola D365 [MS14][MS2]). GRN sudah punya "hitung buta". |
| **K-B4-09** | Tambah jenis tugas di HP: **Penempatan Rak, Transfer, Stock Opname, QC, Potong** dalam satu antrean "Tugas saya" + tombol "Tugas berikutnya"? | (a) ya, bertahap · (b) tidak | **(a)**: urutan Penempatan Rak & Transfer dulu (terkait gate IN, K-GDG-02), lalu Stock Opname (opname awal §8 KEPUTUSAN_GATE_RFID), lalu QC & Potong. |
| **K-B4-10** | Label 70 × 22: **Data Matrix** sebagai kode utama (bukan QR), Code 128 hanya bila ID numerik; kepala cetak **300 dpi** bila pengadaan masih bisa dipilih; tanyakan Chainway batas minimum label ber-inlay; template ZPL baru + uji baca C72. | (a) ya · (b) QR · (c) Code 128 | **(a)**: QR versi kecil butuh zona sepi 4 modul (±16,5 mm tinggi pada 0,5 mm) sedangkan Data Matrix 18 × 18 cukup ±10 mm; perlu uji nyata dengan mesin pindai C72. Isi kode bergantung K-OPN-05 (keunikan EPC). |
| **K-B4-11** | Penanda isian wajib: tetap `*` (status quo) atau "(opsional)" ala GOV.UK? | (a) tetap `*` · (b) "(opsional)" | **(a)**: sudah konsisten di `FormSection`; perubahan tidak sebanding manfaatnya. |
| **K-B4-12** | Tampilan tersimpan (saringan + kolom + urutan) pribadi dan dibagikan per peran & PT untuk daftar roll, stok, dan tugas? | (a) ya · (b) tidak | **(a)**: pola D365/Fiori/Odoo [MS18][FI8†][OD19]; menjawab "data sadar pengguna" tanpa membuat menu baru. |

---

## Lampiran A — Perhitungan

**Kontras (WCAG 2.x)**: luminans relatif L = 0,2126 R + 0,7152 G + 0,0722 B dengan kanal sRGB c ≤ 0,04045 → c/12,92,
selain itu ((c + 0,055)/1,055)^2,4; rasio = (L terang + 0,05)/(L gelap + 0,05). Skrip yang dipakai ada di berkas
sementara (`scratchpad/audit-b4/contrast.py`), tidak di-commit; nilai di §2.2 dan §3.2d adalah keluarannya.

**C72**: diagonal 5,2", 16:9 → sisi pendek = 5,2 × 9/√(16² + 9²) = 2,549" = 64,75 mm; kepadatan = √(1920² + 1080²)/5,2 =
423,6 ppi. Rasio piksel 3 → 1080/3 = 360 CSS px (0,180 mm/px); rasio 2,625 → 411 CSS px (0,158 mm/px).
48 px = 8,6 / 7,6 mm; 56 px = 10,1 / 8,8 mm; 64 px = 11,5 / 10,1 mm. Parhi 9,6 mm = 53 px (360) / 61 px (411).

**Label**: 203 dpi = 8 titik/mm → 70 × 22 mm = 560 × 176 titik; 300 dpi = 11,81 titik/mm → 827 × 260 titik.
Template RFID KN sekarang menaruh elemen terakhir di y = 196 + 18 = 214 titik (26,8 mm) > 176 titik.
Data Matrix 18 × 18 @ 0,50 mm = 9,0 mm; + zona sepi 1 modul tiap sisi = 10,0 mm.
Code 128 Set C, 12 digit: start 11 + 6 simbol × 11 + cek 11 + stop 13 = 101 modul + zona sepi 2 × 10 = 121 modul →
45,4 mm @ 0,375 mm; 30,7 mm @ 0,254 mm (3 titik @300 dpi). Code 128 Set B, 12 karakter: 11 + 132 + 11 + 13 = 167 + 20 =
187 modul → 46,8 mm @ 0,25 mm; 70,1 mm @ 0,375 mm (tidak muat bersama Data Matrix).

**Pemakaian huruf < 12 px**: 2.572 + 1.406 + 1.288 + 994 + 305 + 177 + 18 = 6.760 dari 8.863 (76,3 %).
