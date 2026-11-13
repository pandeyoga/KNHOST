# Audit keuangan KNHOST — skema, duplikasi, kegagalan, multi-entitas, UI/UX, gap vs ERP matang, arsitektur database

**Tanggal:** 13 Nov 2026 · **Pelaksana:** Claude Code (sesi cloud) · **Baseline:** `cd6963a` · **Sifat:** analisis saja —
**tidak ada kode yang diubah**, tidak ada database yang dijalankan (MongoDB tidak tersedia di sesi ini).

Cara membaca: path tanpa awalan relatif ke `backend/`; path layar relatif ke `frontend/src/`. Tanda **✔** = jalur kodenya
saya baca ulang sendiri setelah dilaporkan agen audit; tanpa tanda = hasil agen audit yang menelusuri kode (belum saya
ulang). Tidak ada temuan yang dibuktikan dengan menjalankan aplikasi — skenario gagal adalah bacaan kode.

---

## 0. Ringkasan eksekutif

**Kesimpulan.** Modul keuangan sudah luas dan fondasinya masuk akal (jurnal seimbang divalidasi di satu pintu, jurnal
ganda dicegah indeks unik, baris jurnal tidak pernah diubah aplikasi, tutup buku per PT, eliminasi konsolidasi otomatis).
Kelemahannya ada di tiga kelas, dan **hanya satu kelas yang menyangkut pilihan database**:

1. **Tulisan lintas dokumen tidak atomik** (kelas database). Uang, stok, dan jurnal ditulis berurutan tanpa transaksi.
   Bila langkah tengah gagal, buku pembantu dan buku besar berbeda, dan sering tidak ada penanda maupun jalur ulang.
   Dua temuan kritis ada di sini: jurnal antar-PT bisa terbit di satu PT saja (IC-01), pembayaran kontrabon bisa
   meninggalkan kas tanpa jurnal dan potongan terpakai dua kali (SL-01).
2. **Logika akuntansi yang salah** (bukan kelas database). Landed cost untuk roll yang sudah terjual menggelembungkan
   persediaan (IV-01); scrap retur dihitung dua kali (IV-02); GR/IR tanpa akun varians dan tanpa kliring (IV-03);
   jurnal bisa dibalik dua kali lewat dua mekanisme (GL-01); eliminasi konsolidasi berubah mundur (IC-03).
3. **Kontrol dan batas entitas yang longgar** (bukan kelas database). Akuntan satu PT bisa memposting jurnal manual ke
   buku PT lain (IC-05); akun kontrol terbuka untuk jurnal manual (IC-06, SL-07); periode yang belum berakhir bisa
   ditutup (GL-04); admin bisa menyetujui usul buka-periodenya sendiri (GL-06).

**Jumlah temuan baru: 72** — 2 kritis, 29 tinggi, 33 sedang, 8 rendah (§3). 27 temuan keuangan lama (FN/CX/IX) umumnya
memang sudah diperbaiki di kode (§11), tetapi pola yang sama masih hidup di jalur lain.

**Jawaban soal database (§9).** Jangan memecah keuangan ke PostgreSQL sekarang. Alasannya: keuangan di kode ini bukan
modul terpisah — jurnal diposting dari dalam alur operasional (surat jalan, penerimaan, makloon, retur), dan buku pembantu
piutang/utang/kas hidup di dokumen operasional. Memindahkan buku besar saja ke PostgreSQL membuat kelas masalah nomor 1
menjadi lintas-database, yaitu lebih sulit, bukan lebih mudah. Urutan yang disarankan:

1. Perbaiki temuan kritis/tinggi kelas 2 dan 3 — tidak tergantung database.
2. Ubah MongoDB dari satu node biasa menjadi **replica set satu node** agar transaksi tersedia; bungkus jalur uang
   (dokumen + buku pembantu + jurnal, dan dua sisi antar-PT) dalam transaksi. Sekaligus pindah dari Motor (sudah
   usang) ke PyMongo Async.
3. Perkeras buku besar di MongoDB: nilai uang bulat/Decimal128, validator skema untuk keseimbangan, peran database
   tanpa hak ubah/hapus jurnal, indeks unik yang wajib ada, pemeriksaan invarian harian.
4. Tinjau ulang PostgreSQL setelah itu, bila ada tuntutan auditor atau kebutuhan pelaporan SQL — saat itu outbox
   transaksional sudah mungkin dibuat.

**Yang harus diputuskan pemilik** ada di §10.

---

## 1. Metode dan batas

- Tujuh agen bekerja paralel: lima audit kode (inti jurnal, buku pembantu, antar-PT, persediaan↔GL, UI/UX) dan dua riset
  (pembanding ERP matang, MongoDB vs PostgreSQL). Temuan terberat tiap area saya baca ulang di kode (tanda ✔).
- Saya periksa sendiri: konfigurasi MongoDB dan cadangan (`deploy/docker-compose.yml`, `deploy/backup.sh`), indeks
  (`indexes.py`), pustaka driver, dan menjalankan penjaga statis `scripts/guardrails/verify_atomic_claim.py`.
- **Tidak dilakukan:** menjalankan backend, tes, atau kueri data. "Cek duplikasi" dan "cek kegagalan" di laporan ini
  adalah cek **kode** (bisakah terjadi), bukan cek **data** (sudahkah terjadi). Untuk data nyata, jalankan kueri §12 di
  salinan database.
- Belum ditelusuri: `penalty_service`, `payment_plan_service`, `finance_case_actions`, `fixed_asset_service`,
  `budget_service`, nota kredit amandemen, posting gaji; di UI: kas kecil, aset tetap, pajak, anggaran, tampilan HP.
- Riset web terbatas: banyak situs dokumentasi resmi tidak terjangkau dari sesi ini; sumber dan tingkat keyakinannya
  ditandai di §8 dan §9.

---

## 2. Skema dan sumber kebenaran

### 2.1 Buku besar

| Koleksi | Isi | Catatan |
|---|---|---|
| `journal_entries` | Satu dokumen per jurnal dengan `lines[]` tertanam (akun, debit, kredit); `source_type` + `source_id` menunjuk dokumen asal; `entity_id`; status `posted`/`void` | `source` duplikat dari `source_type`. `total_debit/credit` disimpan tetapi laporan menghitung ulang. Dua set penanda pembalikan (`reversed*` dan `reversed_by_entry_id*`) → GL-01. Status `draft` ada di filter indeks tetapi tidak pernah ditulis |
| `gl_accounts` | Bagan akun; `entity_id` kosong = templat grup, terisi = akun/override khusus PT | Keunikan (kode, entitas) hanya cek-lalu-sisip; indeksnya tidak unik |
| `period_closings`, `period_unlock_requests`, `period_close_locks` | Tutup buku per PT, usul buka periode, kunci proses | Tidak ada indeks unik per periode |
| `number_sequences` | Nomor urut per (entitas, jenis dokumen), unik | Nomor diambil sebelum validasi → nomor bolong (GL-11) |
| `gl_postings` | Hanya definisi indeks | **Skema mati** — tidak ada pembaca/penulis |

Uang disimpan sebagai angka pecahan biasa (float) dibulatkan 2 desimal; hanya rekonsiliasi persediaan yang menjumlah
dalam sen bulat. `ENTITY_REGISTRY.md` untuk jurnal sudah usang (format nomor, daftar sumber, keunikan akun).

### 2.2 Buku pembantu — siapa pemegang angka

| Angka | Sumber otoritatif | Salinan / hitung ulang | Bisa berbeda? |
|---|---|---|---|
| Piutang per pesanan | `sales_orders.grand_total − Σ payments[]` | `paid_total`, `payment_status`, `ar_receipts.allocations`, jadwal cicilan, `fact_ar_daily`, aging | Ya — dua kosakata status (`partial` vs `paid_partial`); aging melewati pesanan ber-flag lunas |
| Piutang di buku besar (1-1200) | Jurnal surat jalan − jurnal kas | — | Ya — "belum lunas" mencakup pesanan belum dikirim |
| Deposit pelanggan | `customers.deposit_balance` (satu angka, tanpa entitas, tanpa riwayat) | Akun 2-1400 | Ya |
| Hutang per faktur | `vendor_bills.grand_total − amount_paid` | `outstanding/payment_status` ditulis sekali lalu basi; `purchase_orders.outstanding`; total kontrabon | Ya — nota debit retur menurunkan akun hutang saat disetujui, faktur baru turun saat dipotong di kontrabon |
| Kas/bank | `cash_transactions` + saldo awal rekening | Buku besar hanya dua akun kas (1-1100, 1-1110); saldo rekening dihitung saat baca | Ya — kas tanpa rekening tidak masuk saldo rekening mana pun (SL-11) |
| Persediaan | `inventory_rolls` (panjang sisa × biaya per roll) | `inventory_balances`, agregat lot (dihitung ulang dari roll), `fact_stock_daily` | Ya terhadap akun 1-1300 — IV-01, IV-02, IV-06 |
| Saldo antar-PT | Dokumen `interco_transactions` yang masih terbuka | `interco_accounts` (cache) | Ya terhadap akun 1-1250/2-1250 — IC-01, 06, 07, 09 |
| PPN | `tax_invoices`, `tax_invoices_in` | Akun PPN di buku besar | Ya — rekap tidak dibaca dari buku besar |

**Rekonsiliasi buku pembantu ↔ akun kontrol hanya dilaporkan, tidak ditegakkan.** Skrip
`scripts/verify_data_integrity.py` memeriksa sebagian (piutang tidak bocor ke entitas "all", jurnal seimbang), tidak
membandingkan total aging dengan saldo akun, tidak punya padanan untuk hutang, dan tidak dijalankan otomatis oleh
aplikasi.

---

## 3. Temuan baru

Skala: **Kritis** = uang/buku salah dan tidak ada jalan memperbaiki dari aplikasi · **Tinggi** = buku salah pada kondisi
wajar, atau kontrol bisa dilewati · **Sedang** = keandalan, kontrol sekunder, atau salah pada kondisi tertentu ·
**Rendah** = kerapian.

### 3.1 Kritis

| ID | Temuan | Bukti | Skenario | Rekomendasi |
|---|---|---|---|---|
| **IC-01** ✔ | Jurnal antar-PT bisa terbit di satu PT saja, tanpa jalan memperbaiki | `services/interco_service.py:500-505` (status diubah dulu), `:645-647` (penjaga "penjual ATAU pembeli sudah ada → lewati dua-duanya"), `:670-693` (dua insert berurutan); pola sama di settlement `:1295-1297` dan retur `services/interco_return_service.py:516-518` | Jurnal penjual terbit, jurnal pembeli gagal (akun nonaktif di PT pembeli, periode PT pembeli tertutup pada settlement bertanggal mundur, proses mati). Status sudah `confirmed`; konfirmasi ulang ditolak ("hanya draf"); bila dipanggil lagi, penjaga melewati kedua sisi. Deteksi hanya skrip luring | Penjaga per sisi; cek periode kedua PT sebelum status diubah; klaim saga; `gl_status` + tombol ulang. Setelah replica set: satu transaksi untuk status + dua jurnal |
| **SL-01** ✔ | Bayar kontrabon: kas tanpa jurnal, potongan bisa terpakai dua kali, kas keluar kedua | `services/contra_bon_service.py:1195-1257` (potongan → faktur → kas → jurnal tanpa pengaman → pelunasan → simpan); `routers/vendor_bills.py:501-584` (`/pay` tidak dipagari untuk faktur yang dipegang kontrabon) | Jurnal kas gagal (tanggal bayar di periode tertutup): kas sudah "posted", hutang sudah turun oleh potongan, catatan pembayaran belum tersimpan, kunci tertinggal. Setelah kunci dilepas admin dan diulang, potongan menambah `amount_paid` lagi dan kas keluar kedua | Cek periode dulu; simpan niat bayar sebelum efek; cari ulang kas per `(ref_type, ref_id)`; validasi semua faktur sebelum kas; tolak `/pay` untuk faktur di kontrabon |

### 3.2 Tinggi — inti jurnal dan tutup buku

| ID | Temuan | Bukti | Skenario | Rekomendasi |
|---|---|---|---|---|
| GL-01 ✔ | Jurnal bisa dibalik dua kali lewat dua mekanisme yang tidak saling mengenal | `services/gl_service.py:819-826` (pembalik manual hanya cek `reversed_by_entry_id`, menolak tipe persis `closing`/`reversal`); `:1534-1536`, `:2249-2251` (pembalik dokumen hanya cek status, menulis penanda `reversed`) | Akuntan membalik manual jurnal kas otomatis; lalu kasnya di-void dari dokumen → dibalik lagi. Pembalik otomatis (`*_reversal`, `cash_transaction_void`) juga bisa dibalik manual. Pemeriksa data membuang tipe ini sehingga tidak terdeteksi | Satu penanda pembalikan; kedua mekanisme saling memeriksa; tolak pembalikan atas semua tipe pembalik |
| GL-02 | Jurnal yang gagal hilang tanpa penanda di banyak jalur | `routers/vendor_bills.py:423-427`; `services/bank_recon_service.py:1147-1151`; `services/ar_receipt_service.py:715-721, 768-783`; `services/roll_service.py:741-749`; panel hanya 5 jenis `routers/posting_failures.py:17-23` ✔ | Faktur "posted" tanpa jurnal hutang; kwitansi void tetapi jurnal kas tidak terbalik; nota kredit bertanda gagal tetapi tidak tampil di panel. Pemicu nyata: akun dinonaktifkan (tidak ada penjaga, termasuk akun sistem) | Penanda gagal untuk semua jenis; panel dan backfill mencakup semuanya; penjaga menonaktifkan akun yang bersaldo/terpetakan |
| GL-03 | Bayar faktur supplier: hutang lunas, kas tanpa jurnal dan tanpa penanda | `routers/vendor_bills.py:548, 562-584`; pola sama `services/payment_variance_service.py:608-609` | `paid_at` mundur ke periode tertutup → galat 500 setelah `amount_paid` naik dan kas tersimpan | Cek periode sebelum tulis; pakai `post_cash_durable` |
| GL-04 ✔ | Periode yang belum berakhir bisa ditutup | `services/closing_service.py:297-309` (tidak ada cek tanggal) | Menutup bulan berjalan membuat semua jurnal otomatis bertanggal hari ini ditolak, lalu ditelan pemanggil (GL-02). Posting yang menyusup saat proses tutup tidak ditandai basi | Tolak bila akhir periode ≥ hari ini; tulis catatan "sedang ditutup" lebih dulu sebagai kunci |

### 3.3 Tinggi — buku pembantu

| ID | Temuan | Bukti | Skenario | Rekomendasi |
|---|---|---|---|---|
| SL-02 | Bayar faktur tanpa kunci idempotensi; entitas kas dari klien | `routers/vendor_bills.py:536-540, 562-584` | Klik ganda nominal parsial → dua pembayaran. Kas tercatat di entitas kiriman klien, jurnal masuk buku entitas faktur | Kunci idempotensi; entitas kas = entitas faktur |
| SL-03 ✔ | Alokasi dana titipan bank: jurnal kedua dilewati diam-diam | `services/bank_recon_service.py:1225` (`source_id` memakai `len(done)` yang mulai 0 tiap panggilan), `:1234-1241` | Alokasi kedua dari titipan yang sama ke pesanan yang sama dianggap sudah diposting → piutang turun tanpa jurnal. Gagal di tengah: pesanan terbayar, sisa titipan belum ditulis → bisa dialokasikan penuh lagi | `source_id` unik per alokasi; tulis sisa per alokasi dengan syarat nilai lama |
| SL-04 | Biaya/bunga bank: kas tersisa bila jurnal gagal; ulang membuat kas kedua | `services/bank_recon_service.py:972-984` | Jurnal bertanggal mutasi di periode tertutup | Cek periode; pakai ulang kas per rujukan |
| SL-05 | Jalur lama "simulasi bayar" masih dipakai layar | `routers/invoices.py:37-155`; `frontend/src/hooks/useAppActions.js:485` | Pembayaran tanpa kwitansi, tanpa void, izin `order:update`, galat jurnal ditelan | Matikan atau alihkan ke kwitansi |
| SL-06 | Void kwitansi menggeser deposit sebelum status berubah | `services/ar_receipt_service.py:675-683, 746, 767-786` | Gagal di tengah meninggalkan kunci; void ulang menggeser deposit lagi; galat jurnal pembalik hanya di-log | Tandai tiap langkah di dokumen; gagal pembalik jadi `gl_status=failed` |

### 3.4 Tinggi — antar-PT dan batas entitas

| ID | Temuan | Bukti | Skenario | Rekomendasi |
|---|---|---|---|---|
| IC-02 ✔ (sebagian) | Roll dikirim utuh, dokumen memakai jumlah pesanan | `services/interco_service.py:747-760` (penerimaan pembeli = subtotal dokumen), `:1773-1791` (HPP dan revaluasi atas semua roll yang berpindah); `services/roll_service.py:1755-1757` | Pesan 100 m, roll pilihan 130 m: pembeli menerima 130 m di buku roll tetapi akun persediaan hanya naik senilai 100 m; penjual membebankan HPP 130 m, pendapatan 100 m | Sesuaikan dokumen ke panjang aktual sebelum jurnal barang, atau tolak selisih |
| IC-03 | Eliminasi konsolidasi berubah mundur | `services/consolidation_service.py:735-736` (satu entri per pasangan, diperbarui di tempat), `:520`, `:109-110` | Neraca konsolidasi 31 Des yang dibuka Februari memakai sisa saldo dan rasio belum-terjual hari ini | Simpan eliminasi per periode, atau hitung dari jurnal ≤ tanggal laporan |
| IC-04 | Laba antar-PT dianggap terealisasi pada rantai A→B→C | `services/interco_service.py:1783-1789` (`cost_basis` roll ditimpa pasangan baru); `services/interco_margin.py:80-87` | Barang masih di dalam grup tetapi margin A→B hilang dari "belum terealisasi" | Simpan rantai asal; hitung sampai barang keluar grup |
| IC-05 ✔ | Akuntan PT-A bisa memposting jurnal manual ke buku PT-B | `services/gl_service.py:665` (`payload.entity_id` menang), `routers/gl.py:147-159` (tidak diadu dengan penugasan); pagar tulis hanya mengenal mode "Semua Entitas" `entity_write_guard.py:193-203` | Kirim `entity_id` PT lain di isi permintaan. Hal serupa pada bagan akun: akun PT lain bisa dinonaktifkan → memicu IC-01 | `resolve_requested_entity()` di semua titik itu |
| IC-06 | Akun antar-PT terbuka untuk jurnal manual dan pembalikan sepihak | `services/gl_service.py:821`, `:666-673` | Membalik jurnal sisi penjual saja: piutang antar-PT hilang, utang di pembeli tetap; dokumen dan eliminasi tidak berubah | Tolak jurnal manual/pembalikan pada akun antar-PT kecuali lewat dokumen antar-PT |
| IC-07 | Retur setelah lunas menghasilkan saldo yang tak terlihat dan tak bisa dilunasi | `services/interco_return_service.py:58, 149`; `services/interco_service.py:804-812, 1010` | Penjual berutang refund di buku besar, layar Saldo Antar-PT menampilkan 0 | Catat sebagai klaim balik + jalur refund |

### 3.5 Tinggi — persediaan ↔ buku besar

| ID | Temuan | Bukti | Skenario | Rekomendasi |
|---|---|---|---|---|
| IV-01 ✔ | Landed cost untuk roll yang sudah terjual mengendap di persediaan | `services/landed_cost_service.py:62-63` (semua roll PO kecuali scrap/batal), `:130-141` (bobot `length_initial`), `:177-181`; `services/gl_service.py:2489` (debit persediaan penuh) | Buku besar didebit penuh; nilai roll hanya naik untuk sisa yang masih dimiliki. Porsi roll terjual tidak pernah jadi HPP | Pecah jurnal: stok hidup → persediaan, terjual → HPP/varians, di mitra → WIP makloon |
| IV-02 ✔ (sebagian) | Scrap retur dihapusbukukan tetapi roll tetap dihitung | `services/return_service.py:1299-1311` (jurnal hapus-buku, roll → `damaged`); `damaged` termasuk status yang dihitung rekonsiliasi (`services/gl_service.py:3282-3286`) | Nilai roll > buku besar sebesar hapus-buku; true-up lalu mengembalikannya ke persediaan lawan ekuitas | Nol-kan panjang/biaya saat scrap, atau keluarkan dari valuasi |
| IV-03 | GR/IR tanpa akun varians, tanpa umur, tanpa kliring | `services/gl_service.py:1832-1848, 2460-2464`; `services/vendor_bill_service.py:128-134`; `services/po_close_settlement_service.py:3` | Selisih harga faktur vs PO mengendap; retur sebelum ditagih lalu faktur penuh mendebit GR/IR dua kali; tutup-kurang PO tanpa jurnal | Laporan GR/IR per PO berumur; akun varians harga; kurangi jumlah tertagih dengan retur |
| IV-04 ✔ (landed cost) | Jurnal gagal setelah stok berubah, tanpa penanda dan tanpa jalur ulang | `routers/landed_cost.py:262-284` (kunci dilepas dan status `applied` sebelum jurnal, tanpa pengaman); `services/makloon_order_service.py:726-738`; `services/roll_service.py:741-749` | Biaya roll naik, jurnal gagal, setujui ulang ditolak. Kirim bahan makloon: roll sudah di mitra, langkah masih `pending` | Cek periode + status posting + masuk panel untuk semua jalur |

### 3.6 Tinggi — layar (UI/UX)

| ID | Temuan | Bukti | Dampak | Rekomendasi |
|---|---|---|---|---|
| UX-01 | "Catat Transaksi" kas tanpa penahan klik ganda | `features/purchasing/CashManagementView.jsx:81-93, 216-229` | Dua transaksi kas dan dua jurnal | Status sibuk + kunci idempotensi |
| UX-02 ✔ | Kunci idempotensi hanya di kwitansi piutang | Layar: `features/crm/ARReceiptModal.jsx:172` saja; server: `idempotency.py:21-25` tidak memuat `/api/gl`, `/api/cash`, `/api/vendor-bills`, `/api/contra-bons`, `/api/interco` | Kirim ulang setelah koneksi putus bisa menggandakan pembayaran, settlement, jurnal manual | Pakai `hooks/useIntentKey.js` dan tambah awalan di server |
| UX-03 | Setujui/batalkan faktur supplier sekali klik | `features/purchasing/VendorBillsView.jsx:126-139, 201`; `VendorBillDetailPanel.jsx:211, 221` | Hutang terposting atau dibatalkan tanpa konfirmasi dan alasan | Konfirmasi + alasan seperti pada jurnal |
| UX-04 | Panel Posting Gagal bilang "semua tercatat" saat gagal memuat | `features/finance/PostingFailuresView.jsx:18, 23-27, 76-78` | Kegagalan tersembunyi; dokumen sumber tidak menampilkan status jurnalnya | Pisahkan status memuat/galat; lencana status jurnal di dokumen |
| UX-05 | Mode "Semua Entitas": tombol buat aktif, ditolak setelah form diisi | `App.js:115`; `features/finance/GeneralLedger.jsx:143`; `features/purchasing/CashManagementView.jsx:198` | Kerja terbuang; pengguna tidak tahu harus memilih PT | Matikan tombol dengan petunjuk, atau minta pilih PT saat form dibuka |
| UX-06 | Form uang tidak menyebut PT tujuan | `features/finance/JournalEntryModal.jsx:73`; `features/purchasing/CashManagementView.jsx:246, 249` (bawaan "PT Kain Suka Cita" ditulis mati) | Risiko posting ke PT yang salah | Lencana entitas di kepala setiap form uang |
| UX-07 | Laporan keuangan tidak menyebut entitas atau "gabungan" | `features/finance/FinancialStatementsView.jsx:150, 285`; juga buku besar, rekening, dasbor, anggaran | Angka satu PT bisa dibaca sebagai angka grup, termasuk di berkas ekspor | Satu banner entitas untuk semua laporan dan ekspor |
| UX-08 | Settlement antar-PT: daftar kandidat tampaknya kosong dari sisi pembayar (perlu uji jalan) | `features/finance/interco/IntercoSettlementModal.jsx:44`; `IntercoView.jsx:127, 394` | Pembayar tidak bisa memilih dokumen yang mau dilunasi; form tanpa tanggal dan rekening | Muat kandidat per pasangan PT dari server |

### 3.7 Tinggi — database dan infrastruktur

| ID | Temuan | Bukti | Dampak | Rekomendasi |
|---|---|---|---|---|
| DB-01 ✔ | MongoDB satu node biasa, tanpa transaksi; penjaga pola pengganti sedang merah | `deploy/docker-compose.yml:10-14`; `services/atomic_claim.py:1-10`; `python3 scripts/guardrails/verify_atomic_claim.py` → 6 pelanggaran: 97 dari 194 endpoint tulis multi-koleksi belum ditinjau (≥14 menyentuh dokumen terkait keuangan, mis. `POST /sales-returns/{id}/settle`), 5 ketidakcocokan pada endpoint yang sudah tercatat | Akar kelas masalah nomor 1; penjagaannya sendiri tidak lagi dijalankan sampai hijau | §9 langkah 2; hijaukan penjaga |
| DB-03 ✔ | Cadangan hanya `mongodump` harian, simpan 14 hari | `deploy/backup.sh:2` | Data keuangan bisa hilang sampai sehari; tanpa oplog tidak ada pemulihan ke titik waktu | Replica set + `mongodump --oplog`; cadangan lebih sering; uji pemulihan |

### 3.8 Sedang

| ID | Temuan | Bukti | Rekomendasi |
|---|---|---|---|
| GL-05 | Tanggal buku campur UTC dan WIB: transaksi 00:00–06:59 WIB tanggal 1 masuk bulan sebelumnya | `core_utils.py:15-16`; `services/gl_service.py:494` | Satu tanggal buku WIB yang eksplisit |
| GL-06 ✔ | "Wajib dua orang" tidak berlaku bagi admin; `reopen` cukup satu admin; jurnal manual langsung terposting | `services/period_unlock_service.py:197-198`; `routers/closing.py:104-109`; `services/gl_service.py:706` | Larang setujui-sendiri tanpa pengecualian; maker-checker jurnal manual |
| GL-07 ✔ | Jurnal manual tidak lewat validator pusat; selisih 1 sen lolos | `services/gl_service.py:684-691` (toleransi 0,01) vs `:555` (0,005) | Panggil validator pusat; bandingkan dalam sen bulat |
| GL-08 | Jurnal manual dan reklas suspense tanpa perlindungan kirim-ulang | `services/gl_service.py:701, 1481`; `idempotency.py:21-25` | Kunci idempotensi dari klien |
| GL-09 | Indeks unik gagal dibuat hanya di-log; aplikasi tetap jalan | `indexes.py:570-590`; `bootstrap.py:1793-1797` | Cek wajib-ada saat start; gagal start bila tidak ada |
| GL-10 | Akun khusus PT bisa dihapus tanpa cek pemakaian; barisnya hilang dari laporan | `services/gl_service.py:425-439`; `services/financial_statement_service.py:115-127` | Cek pemakaian |
| SL-07 | Kas manual menerima `ref_type`, entitas, rekening dari klien | `routers/cash.py:142, 160-163` | Larang `ref_type` dari klien; validasi entitas dan rekening |
| SL-08 | Uang bisa dialokasikan ke pesanan batal/draf | `services/ar_receipt_service.py:328-354` | Tolak status mati |
| SL-09 | Sisa uang muka karyawan tidak punya alur pengembalian; persetujuan tanpa pemisahan pembuat/penyetuju | `services/gl_service.py:3007-3010`; `services/cash_advance_service.py:391, 530-532` | Dokumen pengembalian sisa; pemisahan tugas |
| SL-10 | Lepas-cocok rekonsiliasi tanpa penjaga; dua mekanisme rekonsiliasi | `services/bank_recon_service.py:654-670, 860-874`; `services/bank_service.py:267-277` | Operasi atomik; hapus tombol manual |
| SL-11 | Kas tanpa rekening; kas refund menyimpan kode akun di field rekening | `services/ar_receipt_service.py:82-98`; `services/cash_ledger.py:61` | Wajibkan rekening |
| SL-12 | Kontrabon disimpan utuh tanpa versi; nomor faktur supplier tanpa indeks unik | `services/contra_bon_service.py:595-600`; `routers/vendor_bills.py:193-200` | Simpan bersyarat versi; indeks unik parsial |
| SL-13 | Pajak: satu faktur per pesanan cek-lalu-sisip; nomor seri tanpa cek kembar; rekap dipotong 5.000 baris; tidak ada ekspor Coretax, PPh 23, bukti potong | `services/tax_invoice_service.py:142-173`; `services/input_tax_service.py:131-132` | Indeks unik; filter periode di kueri; kunci masa pajak |
| IC-08 | Settlement antar-PT tidak membuat transaksi kas; pelunasan ganda mungkin | `services/interco_service.py:1098, 1326-1346, 1123-1137` | Kas kembar seperti pinjaman; operasi bersyarat |
| IC-09 | Jalur lama transfer antar-PT (harga pokok) masih dipakai kasir | `routers/transfers.py:337-345`; `frontend/src/features/pos/CheckoutDrawer.jsx` | Arahkan ke mesin antar-PT; matikan jalur lama |
| IC-10 | Harga dan mode PPN antar-PT bisa diatur pembuat per transaksi; status PKP tidak divalidasi | `services/interco_service.py:166-168, 306-312`; `services/interco_tax_service.py:241` | Override hanya dengan izin + alasan; validasi PKP dua sisi |
| IC-11 | Banyak endpoint antar-PT dan eliminasi tanpa penjaga pihak | `routers/interco.py:177-188` dst.; `routers/consolidation.py:59-62, 76-90` | Penjaga pihak di semua endpoint ber-id |
| IV-05 | Rekonsiliasi persediaan membaca kode akun tetap padahal akun bisa dipetakan per PT | `services/gl_service.py:3308` vs `services/gl_mapping_service.py:54-66` | Pakai akun hasil pemetaan |
| IV-06 | Retur beli mengkredit persediaan pada harga retur, bukan nilai buku roll | `services/purchase_return_service.py:107, 121-134` | Kredit pada nilai buku; selisih ke varians |
| IV-07 | Satu roll berbiaya 0 membuat seluruh HPP surat jalan jatuh ke rata-rata | `services/gl_service.py:1154-1159, 1237-1260` | Pakai biaya per roll apa adanya; laporkan roll berbiaya 0 |
| IV-08 | Barang retur masuk lagi pada rata-rata saat ini, bukan HPP asal | `services/return_service.py:244, 1126-1131` | Pakai biaya di surat jalan |
| IV-09 ✔ | "Sinkron" menjumlah selisih lintas PT; true-up membuang selisih ke ekuitas | `services/gl_service.py:3317-3321, 3609-3640` | `reconciled` per PT; true-up hanya untuk saldo awal |
| UX-09…17 | Galat tampil di belakang pop-up; bayar faktur tanpa tanggal/rekening; peringatan periode basi; daftar dipotong tanpa keterangan; laporan tanpa drill-down; angka lama tetap tampil saat gagal muat; piutang tanpa tombol catat bayar; tutup buku tanpa daftar periksa; saldo antar-PT tanpa indikator selisih; peran Finance tanpa menu Hutang/Rekonsiliasi/Buku Besar | Lihat §7 | Lihat §7 |
| DB-02 ✔ | Uang sebagai float | `services/gl_service.py:450-451`; komentar `core_utils.py:204-207` mencatat selisih nyata 1 sen | Rupiah bulat atau Decimal128 |
| DB-04 ✔ | Motor usang sejak Mei 2025; perbaikan bug berakhir Mei 2026, dukungan terakhir Mei 2027 | `requirements.txt:69` (`motor==3.3.1`); README resmi Motor | Pindah ke PyMongo Async |

### 3.9 Rendah

GL-11 nomor jurnal bolong dan dua deret untuk entitas kosong (`services/gl_service.py:607, 621`) · GL-12 `gl_status`
ditulis "posted" tanpa memeriksa hasil · GL-13 `to_list` berbatas memotong diam-diam (rekonsiliasi persediaan 100.000
roll, sementara uji beban 346.700 roll) · SL-14 urutan kas/deposit pada refund · IC-12 penomoran antar-PT tanpa indeks
unik, rujukan nyasar ke koleksi `entities` · IV-10 hapus-buku susut memakai biaya tanpa landed · IV-11 sisa sen per
penerimaan menumpuk · UX-18 kontrol mentah, istilah Inggris, isian uang tanpa pemisah ribuan.

---

## 4. Duplikasi (struktur dan logika ganda)

| # | Yang ganda | Akibat | Saran |
|---|---|---|---|
| 1 | Dua jalur terima piutang: kwitansi (`ar_receipts`) dan "simulasi bayar" lewat `invoices` | Dua kosakata status; jalur kedua tanpa kwitansi dan void (SL-05) | Satu jalur: kwitansi |
| 2 | Lima sumber `payments[]` pesanan (kwitansi, deposit, titipan bank, kasus, store credit) | Validasi pelanggan/entitas tersebar di pemanggil | Satu fungsi alokasi dengan validasi di dalamnya |
| 3 | Dua saldo kredit pelanggan: `deposit_balance` (angka tunggal) dan buku store credit (per entitas) | Deposit tanpa riwayat dan tanpa entitas | Satukan ke buku berentitas |
| 4 | Dua pintu bayar hutang (langsung dan kontrabon) + kas manual + dari mutasi bank | Tidak saling mengunci (SL-01); empat form berbeda | Satu layanan pembayaran, satu form |
| 5 | Dua pembantu jurnal kas: `post_cash_durable` (5 pemanggil) dan `post_cash_transaction` (±10) | Hanya yang pertama meninggalkan penanda gagal | Semua lewat yang tahan-gagal |
| 6 | Pembuatan `cash_transactions` disalin di ±10 tempat | Field berbeda-beda (rekening, entitas) | Satu pembuat |
| 7 | Dua mekanisme rekonsiliasi bank (tombol `reconciled` dan alokasi `reconciled_amount`) | Angka tidak sejalan | Hapus tombol manual |
| 8 | Dua mekanisme pembalik jurnal | GL-01 | Satu mekanisme |
| 9 | Tiga pola jurnal dua-buku antar-PT; hanya dua yang aman per sisi | IC-01 | Satu pembantu "jurnal kembar" |
| 10 | Dua cara memindah stok antar-PT (transfer harga pokok lama vs transaksi antar-PT) | IC-09 | Matikan jalur lama |
| 11 | Dua konsolidasi (`gl_service.consolidation` tanpa eliminasi vs `consolidation_service`) dan tiga pembuat eliminasi | Angka grup bisa beda antar layar | Satu mesin |
| 12 | Dua sumber tahun buku (konfigurasi vs kolom entitas yang tidak dipakai) | Membingungkan | Hapus yang mati |
| 13 | Skema mati: `gl_postings`, field `source`, status `draft`, koleksi `entities` | Menyesatkan pembaca kode | Bersihkan |
| 14 | Layar: lima dasbor, tiga antrean, tiga angka kas di tiga layar, piutang di tiga menu, dua cara buka periode; `fmtDate` disalin ≥10 berkas (zona waktu perangkat, bukan WIB) | Angka "sama" tampil berbeda | §7 |

---

## 5. Pola kegagalan

Jurnal dipanggil dari ±131 titik. Polanya:

| Pola | Contoh | Bila langkah kedua gagal | Terdeteksi? |
|---|---|---|---|
| Tulis bisnis → jurnal, **dengan** penanda | Kas (`post_cash_durable`), kwitansi piutang, retur beli, penerimaan barang, surat jalan | Dokumen bertanda `gl_status=failed` | Ya, di panel Posting Gagal (5 jenis) |
| Tulis bisnis → jurnal, **tanpa** penanda | Faktur supplier, bayar faktur, kontrabon, landed cost, titipan bank, biaya bank, void kwitansi, susut potong, aset tetap, antar-PT | Dokumen "selesai", buku besar kurang | Tidak, kecuali skrip luring |
| Jurnal → status | Denda | Aman diulang | — |
| Klaim saga → tulis → lepas | Makloon, transfer, kontrabon | Kunci tertinggal; setelah dilepas admin, pengulangan tidak idempoten di SL-01, 03, 04, 06 | Kunci terlihat, akibatnya tidak |
| Dua jurnal di dua PT | Antar-PT, settlement, retur antar-PT | Satu sisi saja (IC-01) | Tidak |

Pemicu yang realistis dan berulang: tanggal dokumen mundur ke periode tertutup (cek periode dilakukan di dalam penyisipan
jurnal, **setelah** efek bisnis ditulis, kecuali ±10 berkas yang memakai `preflight_posting`); akun dinonaktifkan;
periode ditutup terlalu dini (GL-04); proses mati di antara dua tulisan.

Penguncian periode hanya berlaku pada jurnal. Dokumen, pembayaran, dan mutasi stok tidak ikut terkunci.

---

## 6. Multi-entitas dan antar-PT

**Alur satu jual-beli antar-PT** (dokumen kembar `interco_transactions`, satu `pair_id`):

```text
BUAT     dua dokumen: penjual (PT-S) dan pembeli (PT-B). Tanpa jurnal.
KONFIRM  status → confirmed, lalu:
           PT-S  Dr Piutang antar-PT / Cr Pendapatan + PPN Keluaran
           PT-B  Dr Persediaan dalam perjalanan + PPN Masukan / Cr Utang antar-PT
GUDANG   transfer antar-PT disetujui → roll pindah pemilik, dinilai ulang ke harga internal:
           PT-S  Dr HPP / Cr Persediaan (biaya nyata roll)
           PT-B  Dr Persediaan / Cr Persediaan dalam perjalanan (= subtotal dokumen)
LUNAS    settlement: PT-B Dr Utang antar-PT / Cr Kas; PT-S Dr Kas / Cr Piutang antar-PT (atau netting)
RETUR    dokumen retur kembar; jurnal balik dua sisi
```

Yang sudah benar: dokumen kembar otomatis, persediaan dalam perjalanan, eliminasi pendapatan/HPP, saldo antar-PT, dan
laba belum terealisasi dihitung otomatis; penomoran per PT; pagar "Semua Entitas hanya untuk melihat".

Yang belum:
- Dua sisi tidak atomik dan tidak bisa diperbaiki (IC-01); pihak penjual memposting ke buku pembeli tanpa persetujuan pembeli.
- Kesamaan piutang antar-PT = utang antar-PT hanya dilaporkan (teks "kedua sisi harus sama besar"), tidak dipaksa dan
  tidak ada alat pencocokan dengan toleransi dan alasan selisih (IC-06, UX-16).
- Saldo antar-PT dihitung dari dokumen, bukan dari jurnal, sehingga bisa berbeda dari buku besar (IC-01, 06, 07, 09).
- Eliminasi tidak disimpan per periode (IC-03); rantai A→B→C salah hitung (IC-04).
- Tidak ada persentase kepemilikan atau kepentingan non-pengendali.
- Tutup buku satu PT tidak memeriksa lawan transaksinya; PT lain masih bisa menghasilkan jurnal yang menyentuhnya.
- Batas entitas pada tulis: jurnal manual, kas manual, bayar faktur menerima entitas dari klien (IC-05, SL-02, SL-07).

---

## 7. UI/UX layar keuangan

Menu ada di `config/navStructure.js:290-333`; ±60 layar di `features/finance`, `purchasing`, `crm`, `pettycash`. Tidak
ada layar yatim.

**Tumpang-tindih:** lima dasbor (dua di antaranya sama-sama bernama "Control Tower") dan tiga antrean; tiga angka kas di
tiga layar; rekonsiliasi ganda; empat jalur bayar supplier dengan form berbeda; piutang tersebar di tiga grup menu; dua
cara membuka periode.

**Arus kerja:** jurnal manual + balik paling rapi (satu layar, ada konfirmasi dan alasan). Terima bayar pelanggan butuh
pindah menu (UX-15). Tutup buku tersebar di tiga menu tanpa tautan dan tanpa daftar periksa (UX-16). Mencari sebab
posting gagal tidak bisa dari dokumennya (UX-04).

**Temuan sedang (ringkas):** UX-09 galat tampil di belakang pop-up dan pembaruan optimistis pada tombol rekonsiliasi ·
UX-10 bayar faktur dan kas tanpa tanggal, rekening, catatan padahal API menerimanya · UX-11 peringatan "jurnal tetap
dapat diposting" sudah basi · UX-12 riwayat kwitansi dipotong 25 baris, kas 500, tanpa halaman · UX-13 laporan → akun →
jurnal → dokumen tidak bisa ditelusuri; buku besar tanpa filter tanggal · UX-14 Laba-Rugi menampilkan angka periode lama
saat gagal memuat · UX-15 · UX-16 · UX-17 cakupan menu peran Finance (butuh keputusan pemilik).

**Yang tidak ditemukan di kode layar:** jurnal berulang/templat, pembayaran massal, umur hutang per supplier, lampiran
bukti pada jurnal/kas/faktur/kwitansi, Laba-Rugi komparatif, filter dimensi, ekspor Neraca Saldo/Buku Besar/Piutang/
Konsolidasi (laporan keuangan hanya CSV), jejak audit selain rekening bank dan bagan akun.

**Perbaikan cepat (per berkas, tanpa ubah API):** UX-01, 02, 03, 04, 06, 09, 11, 14 dan satu `fmtDate` bersama.
**Struktural:** banner entitas di semua layar dan ekspor; satu form pembayaran; satu pusat piutang; rantai drill-down;
kandidat settlement dari server; daftar periksa tutup buku; perampingan dasbor.

---

## 8. Gap terhadap ERP matang

Pembanding: Odoo 18, Microsoft Dynamics 365 Finance, ERPNext (sebagian besar dibaca dari berkas dokumentasi/kode resmi
di GitHub), serta SAP S/4HANA, NetSuite, Accurate, Jurnal (hanya dari cuplikan penelusuran — keyakinan lebih rendah).

| Kemampuan baku | Di sistem matang | Di KNHOST | Gap |
|---|---|---|---|
| Dokumen terposting tidak bisa diubah; koreksi lewat pembalikan | Odoo hash berantai; ERPNext "immutable ledger"; SAP tanpa hapus | Baris jurnal tidak diubah aplikasi; tanpa penegakan di database; dua mekanisme pembalik (GL-01) | Sedang |
| Penomoran berurutan dengan deteksi lompatan | D365 urutan kontinu; Odoo peringatan celah | Urut per PT; bolong saat ditolak (GL-11); tanpa laporan celah | Sedang |
| Akun kontrol tertutup dari jurnal manual | SAP akun rekonsiliasi; ERPNext menolak jurnal ke akun persediaan | Terbuka: piutang, hutang, persediaan, antar-PT (IC-06, SL-07) | **Tinggi** |
| Dokumen cermin antar-perusahaan | Odoo, D365, ERPNext, NetSuite | Ada (dokumen kembar) | — |
| Jurnal antar-perusahaan seimbang dan lengkap di tiap PT | NetSuite memvalidasi saat simpan; ERPNext jurnal lawan tertaut | Seimbang per jurnal; bisa sebelah (IC-01) | **Tinggi** |
| Akun due-to/due-from per pasangan PT | D365 | Satu akun untuk semua lawan; pasangan dilacak lewat dokumen | Sedang |
| Alat pencocokan saldo antar-perusahaan | SAP ICMR; laporan rekonsiliasi NetSuite | Tidak ada; hanya skrip luring | **Tinggi** |
| Persediaan dalam perjalanan | SAP, NetSuite | Ada (1-1310) | — |
| Eliminasi termasuk laba belum terealisasi | D365, NetSuite, SAP | Ada dan otomatis; tidak per periode (IC-03); rantai salah (IC-04) | Sedang |
| Konsolidasi dengan persentase kepemilikan | D365 | Tidak ada | Tergantung struktur grup |
| Kunci periode berlapis + tutup keras | Odoo 5 jenis kunci; D365 per modul | Hanya jurnal; dokumen dan stok tidak terkunci; bisa menutup periode berjalan (GL-04); admin melewati dua-orang (GL-06) | **Tinggi** |
| Daftar periksa tutup buku lintas PT | D365, NetSuite | Tidak ada | Sedang |
| Tutup persediaan (HPP tidak berubah setelah laporan) | D365, ERPNext | Tidak ada; landed cost dan true-up mengubah nilai kapan saja | Sedang |
| GR/IR + pencocokan tiga arah bertoleransi + akun varians | Odoo, D365, ERPNext | GR/IR ada; tanpa varians, umur, kliring (IV-03) | **Tinggi** |
| Rekonsiliasi buku pembantu ↔ buku besar | SAP satu tabel; ERPNext menolak selisih | Hanya laporan sebagian | **Tinggi** |
| Deteksi faktur supplier ganda | ERPNext, D365 | Cek-lalu-sisip tanpa indeks unik (SL-12) | Sedang |
| Persetujuan jurnal/pembayaran (maker-checker) | D365 | Jurnal manual langsung terposting; pembayaran faktur tanpa persetujuan | Sedang |
| Dimensi (pusat biaya/proyek) | D365, ERPNext, Odoo | Tidak ada (hanya field `job` opsional) | Sedang |
| Pencocokan bank otomatis | Odoo, D365 | Ada (aturan cocok) | — |
| Penagihan bertingkat | Odoo, ERPNext, D365 | Ada (tindak lanjut, denda) | — |
| Lampiran bukti dan jejak perubahan yang bisa dilihat | D365, Odoo | Log audit ada; lampiran dan penampil jejak terbatas | Sedang |
| Jurnal berulang, pembayaran massal | Umum | Tidak ada | Rendah–sedang |
| Pajak Indonesia: ekspor XML Coretax, riwayat tarif/DPP, PPh 23 + bukti potong | Odoo (modul Coretax), Accurate, Klikpajak | Faktur internal saja; tanpa ekspor; PPh rekam manual (SL-13) | **Tinggi** bila PKP |
| Multi mata uang | Umum | Hanya rupiah | Tidak mendesak |

Catatan standar (dari pengetahuan umum, belum dicek ke teks standar): PSAK 14 mengizinkan identifikasi khusus untuk
barang yang tidak dapat dipertukarkan — cocok dengan biaya per roll yang sudah dipakai; PSAK 65 mewajibkan eliminasi penuh
saldo dan laba intragrup yang belum terealisasi.

---

## 9. Database: tetap MongoDB, campur PostgreSQL, atau bagaimana

### 9.1 Fakta

- MongoDB 7, satu node biasa. Transaksi lintas dokumen hanya tersedia di replica set; dokumentasi resmi menulis
  "multiple node replica set", sedangkan tutorial resminya menunjukkan replica set satu anggota bisa dibuat dan praktik
  komunitas memakainya untuk transaksi. **Perlu diuji di versi yang dipakai.**
- Tulis satu dokumen bersifat atomik — itu sebabnya jurnal dengan `lines` tertanam selalu utuh. Yang tidak tercakup:
  jurnal + dokumen sumber + saldo, dan dua jurnal antar-PT.
- Dokumentasi MongoDB: float "tidak cocok untuk aritmetika uang"; validator skema boleh memakai ekspresi (bisa memaksa
  Σdebit = Σkredit dalam satu dokumen) tetapi tidak bisa aturan lintas dokumen (akun ada, periode terbuka).
- PostgreSQL: `numeric` eksak, kunci asing, pemicu batasan tertunda untuk "seimbang per jurnal", pemulihan ke titik
  waktu. Semua ERP sumber terbuka yang diperiksa memakai basis data relasional (Odoo, Tryton, LedgerSMB PostgreSQL;
  ERPNext MariaDB).
- Arsitektur campuran: tidak ada atomisitas antara dua basis data. Obat bakunya outbox transaksional — yang di MongoDB
  sendiri mensyaratkan transaksi (yaitu replica set). Dua cadangan tanpa titik waktu bersama; setelah pemulihan,
  keuangan bisa lebih maju atau mundur dari operasional.

### 9.2 Akar temuan audit ini

| Akar | Contoh | Teratasi oleh transaksi MongoDB | Teratasi oleh PostgreSQL untuk keuangan saja | Teratasi oleh perbaikan logika |
|---|---|---|---|---|
| Tulis lintas dokumen parsial | IC-01, SL-01…06, GL-02/03, IV-04 | Ya | **Tidak** — batasnya pindah ke antara dua basis data | Sebagian (urutan, penanda, cek periode dulu) |
| Logika akuntansi salah | IV-01/02/03/06/07, IC-02/03/04, GL-01 | Tidak | Tidak | Ya |
| Kontrol dan batas entitas | IC-05/06, SL-07, GL-04/06 | Tidak | Tidak (kecuali row-level security, yang tetap perlu logika) | Ya |
| Float | DB-02, GL-07 | Tidak | Ya | Ya (rupiah bulat/Decimal128) |
| Integritas rujukan dan keunikan | GL-09/10, SL-12/13 | Tidak | Ya (di dalam keuangan) | Ya (indeks unik wajib-ada) |
| Laporan terpotong / lambat | GL-13, SL-13 | Tidak | Ya (SQL) | Ya (agregasi di database) |

### 9.3 Rekomendasi

**Jangan campur sekarang.** Di kode ini buku besar tidak berdiri sendiri: ±131 titik panggil jurnal berada di dalam
alur operasional, dan buku pembantu (piutang di `sales_orders.payments[]`, hutang di `vendor_bills`, kas di
`cash_transactions`, persediaan di `inventory_rolls`) adalah dokumen operasional. Jika hanya `journal_entries` dan
`gl_accounts` pindah ke PostgreSQL, setiap jalur uang menjadi tulisan ke dua basis data — persis kelas masalah terbesar
audit ini, tetapi tanpa kemungkinan transaksi. Jika buku pembantu ikut pindah, itu praktis migrasi penuh.

Urutan yang disarankan:

| Langkah | Isi | Menghapus | Usaha |
|---|---|---|---|
| **0. Perbaikan tanpa ubah arsitektur** | Temuan kritis dan tinggi kelas logika/kontrol; cek periode sebelum efek bisnis; penanda gagal + panel untuk semua jenis; penjaga atomisitas dihijaukan; cadangan lebih sering | Sebagian besar risiko salah buku hari ini | Sedang, bertahap |
| **1. Replica set satu node + transaksi di jalur uang** | Ubah `mongod` ke replica set; bungkus: dokumen + buku pembantu + jurnal; dua sisi antar-PT; pembayaran multi-faktur. Sekaligus pindah Motor → PyMongo Async (lapisan yang sama disentuh). `mongodump --oplog` untuk cadangan konsisten | Tulis parsial; jurnal sebelah; sebagian besar kebutuhan kunci saga | Infrastruktur kecil; kode sedang. Butuh jendela henti dan uji |
| **2. Perkeras buku besar di MongoDB** | Uang sebagai rupiah bulat atau Decimal128; validator skema keseimbangan; peran database aplikasi tanpa hak ubah/hapus pada jurnal; indeks unik wajib-ada (gagal start bila tidak ada); pemeriksaan invarian harian (akun kontrol = buku pembantu per PT, pasangan antar-PT, jurnal ganda) dengan notifikasi | Float; jurnal tak seimbang; duplikat diam-diam; penyimpangan lama tak terlihat | Sedang |
| **3. Titik keputusan PostgreSQL** | Setelah 0–2 stabil. Pindahkan buku besar sebagai konteks terpisah lewat outbox transaksional **hanya bila** ada pemicu di bawah | Integritas rujukan di database; pelaporan SQL | Besar |

Pemicu untuk langkah 3: auditor menuntut imutabilitas/pemulihan titik-waktu yang dibuktikan di tingkat database; akuntan
butuh pelaporan SQL/BI langsung; jumlah PT dan volume membuat laporan agregasi lambat; tim punya orang yang menguasai
PostgreSQL dan sanggup merawat dua basis data di satu server.

Yang tidak diperbaiki oleh pilihan database apa pun: akun salah, aturan posting salah, periode salah, batas entitas.
Itu sebabnya langkah 0 didahulukan.

Batas rekomendasi ini: taksiran usaha adalah penilaian saya, belum diuji; replica set satu node di luar rumusan resmi
"multiple node" dan tetap tanpa ketersediaan tinggi (sama seperti sekarang).

---

## 10. Keputusan yang dibutuhkan dari pemilik

1. **Arsitektur database:** setuju urutan §9.3 (tetap MongoDB + replica set satu node + perkeras), atau ingin
   PostgreSQL lebih awal?
2. **Akun kontrol:** tutup piutang, hutang, persediaan, dan antar-PT dari jurnal manual? (rekomendasi: ya, dengan jalur
   koreksi resmi lewat dokumen)
3. **Tutup buku:** apakah dokumen, pembayaran, dan mutasi stok ikut terkunci di periode tertutup, atau hanya jurnal?
4. **Dua-orang untuk buka periode dan `reopen`:** berlaku juga bagi admin?
5. **Landed cost setelah barang terjual:** porsi terjual ke HPP periode berjalan atau ke akun varians?
6. **True-up persediaan:** dibatasi untuk saldo awal saja?
7. **Antar-PT:** selisih panjang roll vs pesanan — dokumen menyesuaikan panjang aktual, atau transfer ditolak?
8. **Pajak:** entitas mana yang PKP, dan apakah ekspor Coretax + PPh 23 masuk lingkup?
9. **Peran Finance:** perlu menu Hutang Pemasok, Rekonsiliasi Bank, Buku Besar? (UX-17)
10. **Kepemilikan grup:** semua PT 100 % satu pemilik, atau perlu persentase kepemilikan di konsolidasi?

---

## 11. Status temuan lama (cek kode di `cd6963a`, bukan validasi)

Semua masih `ready_for_validation` di `audit/tracker.json`.

| Temuan | Di kode | Sisa |
|---|---|---|
| FN-15 validator pusat | Ada | Tidak dipakai jurnal manual (GL-07) |
| FN-09 void menjaga periode | Ada | — |
| FN-13 kunci tutup buku | Ada | `finally` menghapus kunci tanpa cek pemilik; tanpa indeks unik periode |
| FN-07 / FN-10 kas tahan-gagal | Ada | Belum dipakai faktur, kontrabon, rekonsiliasi bank (GL-03) |
| FN-05 / FN-16 akun efektif di laporan | Ada | Belum di neraca saldo |
| FN-01 landed cost ganda | Diperbaiki | IV-01 |
| FN-02 tagih lebih | Diperbaiki | Dua faktur bersamaan tidak diuji |
| FN-11 HPP per roll | Diperbaiki untuk surat jalan baru | IV-07 |
| CX-01, CX-04, CX-05, CX-07 | Tampak diperbaiki | Pola sama di SL-01, 04, 09, 10 |
| IX-08, IX-14, IX-16, IX-17 | Diperbaiki | IX-14: pola sama di luar penerimaan (IV-04); IX-17: cek periode memakai tanggal sekarang, jurnal memakai tanggal setuju |
| CX-09, FN-06, GN-08, temuan entitas IC-G1…G4, G13 | Diperbaiki | IC-G10 sisi pelanggan belum ditemukan |

Imutabilitas: tidak ditemukan kode aplikasi yang mengubah `lines` atau menghapus `journal_entries`; hanya status dan
penanda (satu pengecualian kecil: field `reason` ditulis setelah jurnal true-up terbit, `services/gl_service.py:3643`).

---

## 12. Kueri pemeriksaan data (baca-saja)

**Belum dijalankan** — ditulis dari pembacaan kode. Uji dulu di salinan database (`mongosh`), bukan di produksi.

```js
// 1. Indeks unik yang wajib ada: uq_je_source_active, uq_number, uq_entity_doctype
db.journal_entries.getIndexes().filter(i => i.unique); db.number_sequences.getIndexes()

// 2. Jurnal ganda per dokumen sumber
db.journal_entries.aggregate([{$match:{status:{$ne:"void"},source_id:{$gt:""}}},
 {$group:{_id:{t:"$source_type",s:"$source_id"},n:{$sum:1},no:{$push:"$number"}}},{$match:{n:{$gt:1}}}])

// 3. Nomor jurnal kembar
db.journal_entries.aggregate([{$group:{_id:"$number",n:{$sum:1}}},{$match:{n:{$gt:1}}}])

// 4. Jurnal tidak seimbang (sen bulat, tanpa toleransi)
db.journal_entries.aggregate([{$match:{status:{$ne:"void"}}},{$project:{number:1,
 d:{$sum:{$map:{input:"$lines",in:{$round:[{$multiply:["$$this.debit",100]},0]}}}},
 c:{$sum:{$map:{input:"$lines",in:{$round:[{$multiply:["$$this.credit",100]},0]}}}}}},
 {$match:{$expr:{$ne:["$d","$c"]}}}])

// 5. Pembalikan ganda atau menggantung (GL-01)
db.journal_entries.find({status:{$ne:"void"},reversed:true,reversed_by_entry_id:{$exists:true}},{number:1,source_type:1})
db.journal_entries.find({source_type:/(_reversal|_void)$/,reversed_by_entry_id:{$exists:true}},{number:1})
db.journal_entries.find({reversed_by_entry_id:"pending"},{number:1})

// 6. Faktur supplier terposting tanpa jurnal (ganti koleksi/filter untuk dokumen lain)
db.vendor_bills.aggregate([{$match:{status:{$in:["posted","paid"]}}},
 {$lookup:{from:"journal_entries",let:{i:"$id"},pipeline:[{$match:{$expr:{$eq:["$source_id","$$i"]},status:{$ne:"void"}}}],as:"je"}},
 {$match:{je:{$size:0}}},{$project:{bill_number:1,grand_total:1,entity_id:1}}])

// 7. Kas tanpa jurnal, per jenis rujukan
db.cash_transactions.aggregate([{$match:{status:{$ne:"void"}}},
 {$lookup:{from:"journal_entries",let:{i:"$id"},pipeline:[{$match:{$expr:{$eq:["$source_id","$$i"]},source_type:"cash_transaction",status:{$ne:"void"}}}],as:"je"}},
 {$match:{je:{$size:0}}},{$group:{_id:"$ref_type",n:{$sum:1},total:{$sum:"$amount"}}}])

// 8. Kas ganda per dokumen (SL-01, SL-04)
db.cash_transactions.aggregate([{$match:{status:{$ne:"void"},ref_type:{$in:["contra_bon","bank_statement_line","vendor_bill"]}}},
 {$group:{_id:{t:"$ref_type",r:"$ref_id",d:"$direction"},n:{$sum:1},no:{$push:"$number"}}},{$match:{n:{$gt:1}}}])

// 9. Jurnal antar-PT sebelah (IC-01): kelompokkan per awalan source_id sebelum ":"
db.journal_entries.aggregate([{$match:{status:{$ne:"void"},source_type:{$in:["interco_transaction","interco_settlement","interco_return"]}}},
 {$project:{source_type:1,pair:{$arrayElemAt:[{$split:["$source_id",":"]},0]},side:{$arrayElemAt:[{$split:["$source_id",":"]},1]}}},
 {$group:{_id:{t:"$source_type",p:"$pair"},sides:{$addToSet:"$side"}}}])
// lalu tandai: ada "seller" tanpa "buyer", "payer" tanpa "payee", "cogs" tanpa "receipt"

// 10. Dokumen antar-PT kembar tidak sinkron
db.interco_transactions.aggregate([{$group:{_id:"$pair_id",n:{$sum:1},st:{$addToSet:"$status"},
 gt:{$addToSet:"$grand_total"},sa:{$addToSet:"$settled_amount"}}},
 {$match:{$or:[{n:{$ne:2}},{"st.1":{$exists:true}},{"gt.1":{$exists:true}},{"sa.1":{$exists:true}}]}}])

// 11. Jurnal di buku yang salah atau kosong; jurnal manual/pembalik pada akun antar-PT
db.journal_entries.countDocuments({status:{$ne:"void"},entity_id:{$in:["all","",null]}})
db.journal_entries.find({status:{$ne:"void"},source_type:{$in:["manual","reversal"]},
 "lines.account_code":{$in:["1-1250","2-1250"]}},{number:1,entity_id:1,source_type:1})

// 12. Selisih persediaan per PT: nilai roll vs saldo akun 1-1300 (jangan pakai bendera "reconciled")
db.inventory_rolls.aggregate([{$match:{status:{$nin:["scrapped","cancelled","delivered","consumed"]}}},
 {$group:{_id:"$owner_entity_id",nilai:{$sum:{$multiply:["$length_remaining",{$ifNull:["$unit_cost","$base_unit_cost"]}]}}}}])
// sesuaikan daftar status dengan OWNED_ROLL_STATUSES di gl_service.py:3286, lalu bandingkan dengan:
db.journal_entries.aggregate([{$match:{status:{$ne:"void"}}},{$unwind:"$lines"},{$match:{"lines.account_code":"1-1300"}},
 {$group:{_id:"$entity_id",saldo:{$sum:{$subtract:["$lines.debit","$lines.credit"]}}}}])

// 13. Besar true-up ke ekuitas per PT (IV-09)
db.journal_entries.aggregate([{$match:{status:{$ne:"void"},source_type:"inventory_opening"}},
 {$group:{_id:"$entity_id",n:{$sum:1},total:{$sum:"$total_debit"}}}])

// 14. Roll scrap yang masih bernilai (IV-02); roll hidup berbiaya 0 (IV-07)
db.inventory_rolls.find({status:"damaged",writeoff_je_id:{$exists:true},length_remaining:{$gt:0}},{roll_no:1,writeoff_amount:1})
db.shipments.find({"rolls.unit_cost":{$lte:0}},{shipment_no:1})

// 15. Flag lunas basi; hutang tidak cocok dengan pembayarannya
db.sales_orders.find({payment_status:"paid",$expr:{$gt:[{$subtract:["$grand_total",{$sum:"$payments.amount"}]},0.01]}},{number:1})
db.vendor_bills.find({$expr:{$ne:["$amount_paid",{$sum:"$payments.amount"}]}},{bill_number:1,amount_paid:1})
// catatan: kueri hutang belum menyaring pembayaran yang dibatalkan — sesuaikan dengan field void di payments[]

// 16. Dokumen berpenanda gagal di luar panel; dokumen dengan kunci tertinggal
db.credit_notes.find({gl_status:"failed"},{number:1,gl_error:1})
["contra_bons","bank_statement_lines","landed_cost_vouchers","makloon_orders","ar_receipts"].forEach(c =>
  print(c, db[c].countDocuments({saga_lock:{$exists:true}})))

// 17. Pajak: faktur kembar per pesanan dan per nomor seri
db.tax_invoices.aggregate([{$match:{status:{$ne:"cancelled"}}},{$group:{_id:"$order_id",n:{$sum:1}}},{$match:{n:{$gt:1}}}])
db.tax_invoices.aggregate([{$match:{nsfp:{$gt:""}}},{$group:{_id:"$nsfp",n:{$sum:1}}},{$match:{n:{$gt:1}}}])
```

GR/IR menggantung per PO, sisa persediaan dalam perjalanan, saldo deposit vs akun 2-1400, dan saldo titipan bank butuh
penggabungan beberapa koleksi; rumusannya ada di laporan agen dan sebaiknya dibuat sebagai skrip baca-saja tersendiri.

---

## 13. Urutan kerja yang disarankan

1. Jalankan kueri §12 di salinan data nyata — mengetahui mana yang **sudah** terjadi menentukan prioritas.
2. Keputusan pemilik §10 (terutama 1–4).
3. Kritis: IC-01, SL-01.
4. Tinggi yang murah: IC-05 (validasi entitas), GL-04 (cek tanggal tutup), GL-01 (satu penanda pembalik), SL-03
   (`source_id`), UX-01/02/03 (klik ganda, kunci idempotensi, konfirmasi), GL-09 (indeks wajib-ada).
5. Pola: cek periode sebelum efek bisnis + penanda gagal + panel untuk semua jenis (GL-02/03, IV-04, SL-02/04/06).
6. Valuasi: IV-01, IV-02, IV-03, IC-02, lalu IV-09 (true-up dan "sinkron" per PT).
7. Hijaukan `verify_atomic_claim.py`; cadangan lebih sering (DB-03).
8. Replica set satu node + transaksi di jalur uang + PyMongo Async (§9.3 langkah 1), lalu perkeras buku besar (langkah 2).
9. Kontrol: akun kontrol tertutup, kunci periode untuk dokumen, maker-checker, alat pencocokan antar-PT.
10. Layar: banner entitas, satu form pembayaran, drill-down, daftar periksa tutup buku.
11. Gap fitur sesuai kebutuhan: pajak Coretax/PPh, eliminasi per periode, dimensi, lampiran.

---

## Lampiran — sumber riset

Tingkat keyakinan: **[S]** dibaca langsung dari berkas sumber dokumentasi/kode resmi di GitHub · **[S\*]** hanya cuplikan
penelusuran (situs resminya tidak terjangkau dari sesi ini).

- MongoDB [S]: `github.com/mongodb/docs` (v8.0) — `core/transactions-production-consideration.txt`,
  `tutorial/convert-standalone-to-replica-set.txt`, `tutorial/model-monetary-data.txt`,
  `core/schema-validation/specify-query-expression-rules.txt`, `core/write-operations-atomicity.txt`,
  `tutorial/backup-and-restore-tools.txt`. Motor usang [S, dicek ulang]: `github.com/mongodb/motor` README.
- PostgreSQL [S]: `github.com/postgres/postgres` REL_17 — `datatype.sgml`, `ddl.sgml`, `ref/create_trigger.sgml`,
  `mvcc.sgml`, `backup.sgml`. Contoh buku besar SQL [S]: `github.com/pgr0ss/pgledger`.
- Basis data ERP sumber terbuka [S]: dokumentasi Odoo 17, Tryton, README LedgerSMB, README Frappe.
- Outbox dan CDC [S]: dokumentasi Debezium (konektor MongoDB, outbox event router). Pola dual-write, Jepsen 4.2.6,
  Square Books, Modern Treasury [S\*].
- Odoo 18 [S]: `github.com/odoo/documentation` (data_inalterability, year_end, multi_company, inventory_valuation,
  indonesia) dan `github.com/odoo/odoo` (`account/models/company.py`, `l10n_id_efaktur_coretax`).
- Dynamics 365 [S]: `github.com/MicrosoftDocs/dynamics-365-unified-operations-public` (number-sequence-overview,
  intercompany-accounting-setup, elimination-rules, financial-period-close-workspace, year-end-close,
  accounts-payable-invoice-matching, inventory-close).
- ERPNext [S]: `github.com/frappe/erpnext` dan dokumentasi v13 (inter-company-invoices, inter-company-journal-entry,
  accounting-period, period-closing-voucher, perpetual-inventory).
- SAP S/4HANA, NetSuite, Accurate, Jurnal, aturan pajak (PMK 131/2024, Coretax) [S\*] — perlu dicek ke sumber asli
  sebelum dijadikan spesifikasi.
