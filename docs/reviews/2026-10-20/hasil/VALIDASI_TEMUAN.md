# Validasi temuan review 2026-10-20 — benar/false positive, perilaku sekarang, rencana implementasi

- Dikerjakan: 2026-10-20 oleh Claude Code (implementer), sebelum perubahan kode apa pun
- Kode yang divalidasi: `f4e8f0b` (commit sesudahnya hanya dokumen/setup dev)
- Lingkungan: Docker lokal (`docker-compose.dev.yml`), data acuan `restore_local_demo.sh` versi Docker
  (sebagian gagal — lihat ENV-01)
- Melengkapi [CEK_ULANG_HEAD.md](CEK_ULANG_HEAD.md) (cek tingkat diff). Dokumen ini menguji **apakah
  temuannya memang benar**, bukan sekadar kodenya belum berubah.

## Ringkasan

| Hasil | Jumlah | ID |
|---|---|---|
| Terbukti — direproduksi ulang di runtime lokal | 4 | FE-02 (browser), FE-05 (HTTP), FE-10 (data + kode), AUD-EXP-01 (HTTP) |
| Terbukti — jalur kode ditelusuri utuh, hasil deterministik | 15 | FE-01, FE-03, FE-04, FE-06, FE-07, FE-09, FE-11, FE-12, FE-13, AUD-RND-01, AUD-RND-02, AUD-MKL-01 (bagian 1), AUD-MKL-02, AUD-MIG-01, AUD-MIG-02 |
| Terbukti — kelas ketahanan (butuh gangguan/konkurensi untuk terpicu) | 5 | FE-08, AUD-SO-01, AUD-WMS-01, AUD-RET-01, AUD-EXP-02 |
| **False positive sebagian** | 1 | AUD-MKL-01 bagian 2 (ekspresi total) — kodenya benar |
| Menunggu keputusan bisnis | 1 | AUD-RND-03 |

Tidak ada temuan yang seluruhnya false positive. Dua catatan kalibrasi prioritas ada di bagian
"Catatan untuk reviewer".

Arti "kelas ketahanan": logikanya terbukti salah, tetapi baru berdampak bila terjadi gangguan
penulisan database di tengah proses, operasi lebih lama dari batas kunci, atau dua proses
bersamaan. Kemungkinannya rendah pada satu server, dampaknya ke integritas data tinggi.

## Frontend

| ID | Putusan & bukti | Perilaku sekarang | Rencana implementasi |
|---|---|---|---|
| FE-01 | **Benar.** Rantai: `special_orders.py:221-223` header `custom_item` = qty/satuan **item pertama** → `special_order_phase2.py:274-283` biaya dari sampel **terakhir** × qty header → `special_orders.py:1087-1094` SO **satu baris** (`linked_product_id` × qty header). Menjelaskan persis hasil reviewer "B 100 yard". | OD A100+B200 → SO hanya B100; total & pajak dari satu baris. | Harga/produk hasil/qty per item stabil (kunci item), pratinjau & lock per item, konversi membawa semua item sah, total = jumlah rincian, retry idempoten. OD lama satu item tetap jalan. Fase UI-01. |
| FE-02 | **Benar, direproduksi di browser.** `KNSelect` hanya membaca `onValueChange` (tanpa `...rest`); scan repo menemukan tepat 9 pemakaian `onChange`, semua di Interco. Pilih "Kanda Fabric" sebagai PT Pembeli → tetap "Pilih...". | Pembeli/penerima/metode/mode harga/PPN/produk/filter Interco tidak bisa diganti. Penjual hanya terisi karena nilai awal. | Ganti ke `onValueChange` di 9 lokasi; uji sampai payload. Pertimbangkan dev-warning di `KNSelect` bila `onChange` diteruskan. Fase UI-02. |
| FE-03 | **Benar.** Grup menu `akuntansi` hanya tampil bila ID grup ada di daftar izin role; tidak ada satu modul pun di `access_modules.py` yang memuat `akuntansi`. Interco & Buku Besar dipindah ke grup itu (IA 2026-10) tetapi katalog modul masih menunjuk `pembelian`/`keuangan`. | Role kustom tanpa acuan dengan modul Interco/Akuntansi penuh tidak melihat transaksi Interco, Buku Besar, Laporan, Tutup Buku. | Satu kontrak: katalog modul ↔ grup induk ↔ tab hub; grup tampil bila ada anak sah. Preview role = menu akun nyata. Fase UI-03. |
| FE-04 | **Benar**, contoh dicocokkan dengan `permissions_config.py`: selisih bayar — finance punya `payment_variance.decide` tapi tombol tersembunyi, sales tidak punya tapi tombol tampil (klik → 403); transfer — admin punya `transfer.approve`, tombol hanya untuk manager; Pesanan Khusus — sales_admin punya `order.create`, tombol tidak tampil. | Tombol mengikuti nama role, bukan izin efektif `/auth/me`. | Pakai `can(perms, resource, action)` + status/penugasan/scope; daftar petugas dari akun aktif berkemampuan. Backend tetap penegak utama. Fase UI-03. |
| FE-05 | **Benar, direproduksi HTTP.** `whadmin@` (izin warehouse view/create/update): `GET /warehouses?scope=all` → 403; tanpa `scope=all` → 200, 8 gudang. Halaman selalu meminta `scope=all`. | Data Gudang kosong + pesan tolak untuk Admin Gudang. | FE meminta daftar sesuai scope pengguna (tanpa `scope=all` untuk non-master); backend menentukan dari izin, bukan nama role. Tidak membuka semua gudang. Fase UI-03. |
| FE-06 | **Benar.** `workDeskApi.js:217` → `view: "approvals"`; `openDocument` langsung memakai view itu; tidak ada renderer/alias `approvals` (hanya `price-approvals`). Tambahan: `PriceApprovals` belum menerima fokus ID. | Klik "Putuskan" di Meja Saya → layar kosong. | Target `price-approvals` + dukungan fokus ID pengajuan; uji semua target resolver antrean terhadap renderer. Fase UI-04. |
| FE-07 | **Benar.** `ReturnDetail` tidak menerima prop error; error hanya dirender di cabang daftar yang tidak tampil saat detail terbuka. `handleSettle` menelan error → modal menjalankan `onClose()`. | Aksi retur gagal tanpa pesan; modal settle menutup walau gagal. | Teruskan error ke detail/modal, lempar ulang dari handler, tutup modal hanya saat sukses. Fase UI-04. |
| FE-08 | **Benar (race).** `handleOrderChange` memasang respons tanpa cek SO yang masih aktif. | Pilih A lalu B; bila respons A datang belakangan, baris produk A muncul di bawah SO B. | Guard ID permintaan aktif / AbortController, reset roll/qty/bukti saat ganti SO. Fase UI-04. |
| FE-09 | **Benar.** `SalesReturns.jsx:110` `GET /sales-orders` tanpa filter/paging → backend `.to_list(200)` terbaru semua status → filter status di browser. Error dimuat ditelan (`catch (_) {}`). | SO terkirim yang lebih tua dari 200 SO terbaru tidak bisa diretur. | Pencarian/paging server (nomor/customer) + filter status eligible di server + sisa qty retur; tampilkan error. Fase UI-04. |
| FE-10 | **Benar, dengan data.** Antrean memakai `length_remaining` dalam satuan dasar roll; data acuan: 30.718 roll yard + 15.815 roll kg, **0 meter**; UI selalu menulis "m" dan menjumlah semua. | Label satuan salah untuk seluruh data; total kg+yard dicampur. | Satuan eksplisit per tugas/roll dari backend, total per satuan, tanpa konversi tebakan. Fase UI-05. |
| FE-11 | **Benar.** `if (!data) return Memuat…` (baris 55) sebelum `ErrorNotice` (baris 101). | GET pertama gagal → "Memuat penerimaan…" selamanya. | Pisahkan loading/error/kosong/data; tombol ulangi. Fase UI-05. |
| FE-12 | **Benar.** `balanced !== false`; KPI dirender tanpa syarat saat data belum ada/gagal. | Neraca belum dimuat/gagal tampil hijau "Seimbang". | Hanya `true` → Seimbang; `false` → Tidak seimbang; lainnya → status tidak diketahui. Fase UI-05. |
| FE-13 | **Benar.** Satu formatter `Math.abs(v)` untuk semua seri termasuk saldo kumulatif. | Defisit kas tampil positif saat di-hover. | Formatter per seri; saldo kumulatif mempertahankan tanda. Fase UI-05. |

## Backend

| ID | Putusan & bukti | Perilaku sekarang | Rencana implementasi |
|---|---|---|---|
| AUD-EXP-01 | **Benar, direproduksi HTTP** (admin, dataset `sales_finance`): tanpa grouping → unduh 200; `group_by: [sales_name]` → job `done`, kolom `['sales_name','grand_total','_rows']`, unduh **403 ACCESS_CHANGED `_rows`**. Penyebab: `export_engine.py:283` menambah `_rows` ke kolom job, pemeriksaan unduh hanya mengenal kolom dataset. | **Semua** export ber-grouping tidak bisa diunduh. | Kolom agregasi membawa metadata asal; pemeriksaan ulang izin memvalidasi kolom sumber/kunci grouping, bukan `_rows`. Keamanan unduh tetap. |
| AUD-EXP-02 | **Benar (konkurensi).** `fetch` membaca per 2.000 baris dengan `$skip/$limit` tanpa snapshot. | Export > 2.000 baris saat sumber berubah dapat menggandakan/melewati baris; jumlah tetap tampak cocok. | Keyset pagination + titik waktu (cutoff `updated_at`/snapshot id) dan verifikasi jumlah unik. |
| AUD-MKL-01 | **Benar sebagian.** Bagian 1 benar: route membaca `loss_claim_receivable`/`loss_claim_deducted`, service menyediakan `loss_claim`/`loss_deducted` → `KeyError` → 500 begitu ada baris mitra. **Bagian 2 false positive:** `p["receivable_total"] + p["deducted_total"]` sudah berada di dalam list (`supplier_contracts.py:237-239`), sintaks & semantik benar; berkas tidak berubah sejak `63c38bd`. | Excel rekap klaim makloon 500 bila ada data. | Samakan nama field; uji workbook dengan klaim piutang, potong tagihan, keduanya, kosong; cocokkan dengan JSON. |
| AUD-MKL-02 | **Benar.** `makloon_recap_service.py:97` `rows[:1000]` sementara total dari semua kejadian; Excel memakai daftar yang sama. | Rincian > 1.000 terpotong diam-diam, tidak sama dengan total. | Excel: iterasi semua rincian (pecah sheet); layar: paging + penanda jumlah. |
| AUD-RND-01 | **Benar.** `decide` meloloskan `pass` bila **ada** round ACC jenis apa pun, lalu menyimpan `round_id` round **terakhir**. Rancangan rev 1.3: "ACC teknis per labdip/proofing/handfeel" dan hasil gagal tidak boleh jadi bukti lulus. | Siklus labdip ACC + handfeel ditolak dapat dinyatakan lulus dengan referensi round yang ditolak. | Lulus mensyaratkan round final ACC untuk **setiap** jenis uji siklus; referensi = round final tiap jenis. Gagal tetap menunggu PIC (aturan owner dipertahankan). |
| AUD-RND-02 | **Benar.** `existing_artwork` menerima `design_version` dari body tanpa cek versi ada/ACC. | Proofing dapat menunjuk versi 999 yang tidak pernah ada. | Validasi versi terhadap riwayat versi desain + status ACC/HOLD. |
| AUD-RND-03 | **Menunggu keputusan** (lihat tracker). Kode di `rnd_revalidation_service.py:83`. | Kontrak terminated diterima backend, tidak muncul di daftar pilihan. | Ikuti jawaban owner. |
| AUD-SO-01 | **Benar (kunci).** `_release` menghapus kunci tanpa cek pemilik; TTL 120 dtk. | Proses > 120 dtk dapat melepas kunci proses baru. | Token pemilik + release bersyarat; validasi ulang state sesudah klaim. |
| AUD-WMS-01 | **Benar (gangguan).** Urutan roll → movement → jurnal → saldo tanpa transaksi; retry CAS → `recount`. Panel "Posting Gagal" (`routers/posting_failures.py`) **tidak** mencakup opname. | Jurnal opname gagal tidak tercatat di mana pun dan tidak bisa diulang. | Catatan operasi idempoten per baris scan (status per langkah) + lanjutkan langkah tertinggal; daftarkan ke Posting Gagal. |
| AUD-RET-01 | **Benar (gangguan).** `_dispose`: jurnal → roll damaged → movement → saldo; gagal di tengah → klaim dilepas, `_stage` menganggap roll `closed`, retry ditolak. | Buang BS gagal sebagian tidak bisa dipulihkan lewat UI. | Operasi buang dengan kunci idempoten per roll + resume langkah tertinggal. |
| AUD-MIG-01 | **Benar.** Kandidat `if od.get("fulfillment")` (objek kosong lolos) tetapi update mensyaratkan `$exists: False`; hasil update tidak diperiksa; PO tetap ditandai. | Laporan "matched" tetapi relasi OD tidak tertulis untuk `{}`/`null`. | Tangani absent/`{}`/`null` eksplisit, hitung `modified_count`, laporkan konflik. |
| AUD-MIG-02 | **Benar.** Rollback menghapus item ber-penanda `migrated`; `set_route` memperbarui field satu per satu sehingga penanda tetap ada sesudah perubahan operasional. | Rollback menghapus route/riwayat yang dibuat sesudah migrasi. | Simpan hash/versi hasil migrasi; rollback hanya bila belum berubah, sisanya ditandai konflik. |

## Temuan tambahan selama validasi (diajukan, perlu konfirmasi reviewer)

| ID usulan | Temuan | Bukti |
|---|---|---|
| ENV-01 | **Data acuan tidak lagi bisa dipulihkan utuh di HEAD.** Rantai `restore_local_demo.sh` (dijalankan versi Docker) gagal di 3 dari 12 skrip: `seed_demo_transaksi_kn` (9 skenario 403: `purchase_order.create`, `order.confirm`, `wms.approve`, "tidak ditugaskan di badan usaha"), `seed_p04_kn` (403 `order.verify`), `seed_p05_kn` (403 `order.confirm`). Contoh: akun `md@` kini hanya `purchase_order: ["view"]`. Akar masalah (skrip seed tertinggal dari matriks izin vs regresi izin) belum ditentukan. Akibat: tidak ada transaksi Interco/makloon/kas demo; reproduksi beberapa alur bergantung fixture langsung. | log restore lokal; `/auth/me` md@ |
| ENV-02 | `scripts/restore_local_demo.sh` & `.restore_env.sh` terikat lingkungan Emergent (`supervisorctl`, `localhost:27017`). Perlu varian Docker agar reviewer & implementer memakai data acuan yang sama. | isi skrip |
| ENV-03 | `seed_realistic.py` (seed bawaan) melewati data Interco (stok entitas sumber 0) dan SPK printing (resep/yield belum dipilih). | log seed lokal |

Catatan non-temuan: dropdown PT Interco sempat kosong saat uji karena sesi browser basi sesudah
database di-reset (`/auth/me` 401). Sesudah login ulang pilihan muncul — bukan bug aplikasi.

## Catatan untuk reviewer

1. AUD-MKL-01 bagian 2 mohon ditinjau ulang — kemungkinan salah baca baris.
2. Usulan kalibrasi: AUD-SO-01 (butuh operasi > 120 dtk) dan AUD-EXP-02 (butuh > 2.000 baris +
   penulisan bersamaan) tetap benar tetapi kemungkinannya rendah; prioritas "tinggi" dapat
   dipertimbangkan menjadi "sedang". Implementer tidak mengubah prioritas di tracker.
3. FE-06 dan FE-01 tidak saya ulang di browser karena butuh antrean harga khusus & siklus R&D
   lengkap (data acuan gagal sebagian, ENV-01); bukti kode bersifat deterministik dan sejalan
   dengan bukti browser/HTTP reviewer. Reproduksi runtime akan dibuat saat fasenya dikerjakan.
