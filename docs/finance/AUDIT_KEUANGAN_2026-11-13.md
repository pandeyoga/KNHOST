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

**Jumlah temuan baru: 111** — 2 kritis, 46 tinggi, 51 sedang, 12 rendah (§3; 72 dari putaran pertama, 39 dari
lanjutan §3.10–3.11). 27 temuan keuangan lama (FN/CX/IX) umumnya memang sudah diperbaiki di kode (§11), tetapi pola yang
sama masih hidup di jalur lain.

Dari lanjutan, yang paling perlu diketahui: setoran karyawan di Pusat Kasus dibukukan dua kali setiap kali dipakai
(FX-01); jurnal pembayaran denda kedua dilewati (FX-02); deposit satu pelanggan bisa melunasi pesanan pelanggan atau PT
lain (FX-05); nota kredit bisa melebihi faktur (FX-12); jurnal penyusutan dan gaji bertanggal hari posting, bukan
periodenya (FY-02); hutang BPJS dan PPh 21 tidak punya alur setor (FY-07).

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
  adalah cek **kode** (bisakah terjadi), bukan cek **data** (sudahkah terjadi). Untuk data nyata, jalankan §12 di
  salinan database.
- Putaran lanjutan (dua agen, §3.10–3.11) menutup: denda, rencana bayar, selisih bayar, kasus keuangan, nota kredit,
  aset tetap, anggaran, gaji dan insentif, kas kecil, pusat pajak, beserta layarnya.
- Masih belum ditelusuri: isi perhitungan komisi, alur bayar faktur kampanye, `store_credit_service` secara rinci,
  layar kasus/denda/slip gaji, tampilan HP.
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

### 3.10 Lanjutan — aset tetap, anggaran, gaji dan insentif, kas kecil, pusat pajak (FY)

Ditambahkan setelah laporan pertama; dibaca di `ec79643`. Sudah benar di area ini: cairkan uang muka dan bayar reimburse
(klaim, kas dipakai ulang, penanda gagal); penyusutan idempoten per aset+periode; posting/bayar gaji memakai penjaga
status; biaya kampanye punya kompensasi dan kunci idempotensi.

| ID | Tingkat | Temuan | Bukti | Skenario | Rekomendasi |
|---|---|---|---|---|---|
| FY-01 ✔ | Tinggi | Aset tetap disimpan sebelum jurnal perolehan, tanpa penanda | `services/fixed_asset_service.py:129-137` | Tanggal perolehan di periode tertutup atau akun nonaktif → galat, baris aset tetap ada; ulang = aset kembar; aset tanpa jurnal tetap disusutkan dan bisa dilepas | Cek periode sebelum simpan; `gl_status` + tombol ulang; tolak susut/lepas bila belum berjurnal |
| FY-02 ✔ | Tinggi | Jurnal periodik bertanggal hari posting, bukan periodenya | Penyusutan `services/fixed_asset_service.py:263-267` → `services/gl_service.py:2391`; gaji `:3097`; juga insentif dan LPJ | Susut Jan–Okt dijalankan November: 10 bulan beban masuk November. Gaji Oktober diposting 3 Nov masuk November. Periode masa depan bisa dijalankan hari ini | Tanggal = akhir periode + cek periode; tolak periode depan dan yang melompat |
| FY-03 ✔ | Tinggi | Perolehan aset selalu mengkredit kas (1-1100) tanpa transaksi kas; akun dari API tidak divalidasi | `services/gl_service.py:2346-2362`; form tanpa pilihan sumber dana `features/finance/FixedAssetsParts.jsx:94-105` | Aset lama atau aset kredit mengurangi kas di buku besar; aset lewat faktur supplier mengkredit kas dua kali; buku kas ≠ buku besar | Sumber dana wajib (kas+rekening / hutang / saldo awal); batasi akun |
| FY-04 | Tinggi | Pindah aset antar-PT tidak atomik dan tidak idempoten | `services/fixed_asset_service.py:372, 399-408, 428-431, 444-446`; `routers/fixed_assets.py:188-199` | Periode PT pengirim tertutup atau klik ganda → aset dan utang antar-PT kembar di penerima, pengirim tanpa jurnal (kelas IC-01) | Klaim; cek periode dua PT; penjaga entitas di endpoint bayar |
| FY-06 | Tinggi | Penggajian tidak bisa dihitung ulang atau dibatalkan | `services/hr_payroll_service.py:370-372, 489-510`; layar menjanjikan "bisa diubah HR" `features/hr/PayrollRunsView.jsx:101` | Setelah koreksi tunjangan/lembur, slip tetap angka lama; setelah posting tidak ada pembalikan | Hitung ulang draf; batal sebelum posting; void + jurnal balik sesudahnya |
| FY-07 ✔ | Tinggi | Hutang BPJS (2-1700) dan PPh 21 (2-1800) hanya pernah dikredit; tidak ada alur setor | `services/gl_service.py:3084-3089` (satu-satunya pemakai kedua akun) | Setoran lewat layar Kas menjadi beban kedua dan hutangnya tidak pernah turun | Dokumen setor kewajiban (Dr hutang / Cr kas) per periode |
| FY-05 | Sedang | Status aset `transferred` tidak dijaga saat diubah/dilepas lewat API | `services/fixed_asset_service.py:58-59, 174-176, 317` | Aset yang sudah pindah disusutkan lagi di PT lama | Tolak ubah/lepas |
| FY-08 | Sedang | Hutang insentif: akrual dan gaji menghitung dari dua sumber berbeda; galat akrual ditelan | `services/gl_service.py:2909-2914, 3061-3067`; `services/hr_payroll_service.py:245-257` | Saldo 2-1500 menggantung atau berbalik; akrual manual pada mode beban = beban ganda | Satu sumber komisi; akrual gagal menggagalkan posting |
| FY-09 | Sedang | Kontrol gaji: ajukan, sahkan, posting, bayar satu izin; status tengah bisa macet; akun bayar tidak dibatasi ke kas | `services/hr_payroll_service.py:475-486, 521-551`; `services/gl_service.py:3119-3124` | Satu orang menggaji sampai kas keluar | Pemisahan tugas; daftar putih akun kas |
| FY-10 | Sedang | Anggaran kategori membaca tahun dari isian teks bebas "periode" LPJ | `services/budget_service.py:275-278, 327-329`; `features/pettycash/SettlementForm.jsx:102` | LPJ ber-periode teks hilang dari realisasi | Pakai tanggal jurnal |
| FY-11 | Sedang | Angka anggaran salah: akun persediaan memakai mutasi bersih; PO terima-sebagian dihitung dua kali; mode gabungan membandingkan pagu per PT dengan realisasi gabungan | `services/budget_service.py:40-41, 263, 288, 339-345`; `routers/budgets.py:121-125` | KPI dan peringatan anggaran tidak bisa dipercaya | Realisasi = debit penerimaan; komitmen = sisa PO; hitung per PT |
| FY-12 | Sedang | Anggaran hanya peringatan dan hanya di PO; pagu tanpa indeks unik dan tanpa jejak ubah | `services/budget_service.py:45-51`; `routers/purchase_orders.py:714-716`; `routers/budgets.py:99, 110` | Faktur non-PO, kas, LPJ, gaji lolos; pagu bisa dinaikkan tanpa bekas | Putuskan cakupan; riwayat pagu |
| FY-13 | Sedang | Peta kategori→akun saat posting LPJ mengabaikan lapisan entitas | `services/cash_advance_service.py:118-120` vs `:82-92` | LPJ PT-A terposting ke akun override PT-B | Pakai peta efektif per entitas |
| FY-14 | Sedang | LPJ tanpa bukti, vendor, PPN; masih bisa diubah setelah diajukan | `schemas_cash_advance.py:71-75`; `services/cash_advance_service.py:454, 486` | Penyetuju menyetujui isi yang berubah; PPN nota jadi beban | Lampiran wajib; kunci isi saat diajukan |
| FY-15 | Sedang | Pusat pajak: `entity_id=all` dan entitas dari klien tanpa cek penugasan; hapus rekaman PPh tanpa cek entitas | `routers/tax_center.py:23-45, 76-83`; `routers/input_tax.py:41-47` | Akun satu PT membaca omzet, PPh 21, PPN seluruh grup | Penjaga entitas di semua endpoint |
| FY-17 (layar) | Sedang | Aksi uang tanpa konfirmasi: setujui & posting LPJ, bayar reimburse, catat bayar pindah aset, hapus pagu, hapus rekaman PPh | `features/pettycash/SettlementDetail.jsx:52-61`; `features/finance/FixedAssetsView.jsx:345-347`; `features/finance/TaxCenterView.jsx:323-327` | Salah klik = jurnal atau kas keluar | Konfirmasi berisi nominal dan PT |
| FY-18 (layar) | Sedang | Tanpa kunci idempotensi di layar aset, kas kecil, pajak (lanjutan UX-02) | `idempotency.py:21-25` | Kirim ulang menggandakan aset, PD/LPJ | Kunci di layar + awalan di server |
| FY-16, 19, 20 | Rendah | Basis PPh 21 di rekap tidak sejalan buku; teks menyesatkan ("Sisa Dikembalikan" tanpa alurnya); sisa pembulatan susut tidak pernah disusutkan | `services/tax_center_service.py:24, 53`; `features/pettycash/SettlementDetail.jsx:102`; `services/fixed_asset_service.py:232, 257-259` | — | — |

Duplikasi tambahan di area ini: tiga wadah "uang dipegang orang" (1-1400, 1-1280, 2-1650) sehingga 1-1400 tidak bisa
dicocokkan dengan uang muka terbuka; tiga peta beban tunai (kategori LPJ, kata kunci kas manual, akun kampanye) — kata
"gaji" di kas manual bertabrakan dengan penggajian; dua konsep anggaran (`budgets` dan anggaran kampanye); dua rekap PPN
dengan penjaga entitas berbeda; rumus susut disalin dua kali; pindah aset = pola jurnal dua-buku keempat.

### 3.11 Lanjutan — denda, rencana bayar, selisih bayar, kasus keuangan, nota kredit, gerbang bayar-dulu (FX)

Dibaca di `ec79643`. Tidak ditemukan salah sisi debit/kredit pada jurnal denda, selisih, dan kasus; gerbang bayar-dulu
terpasang di ketiga jalur kirim.

| ID | Tingkat | Temuan | Bukti | Skenario | Rekomendasi |
|---|---|---|---|---|---|
| FX-01 ✔ | Tinggi | Setoran karyawan pada kasus keuangan dibukukan dua kali — terjadi setiap kali aksi dipakai, bukan hanya saat gagal | `services/finance_case_actions.py:355-361` lalu `:364-372` (dua panggilan kas masuk; id kas berurutan per panggilan `:76-80`) | Setor 10 jt → kas masuk 20 jt, piutang karyawan (1-1280) minus 10 jt | Hapus panggilan pertama; uji jumlah kas per aksi |
| FX-02 ✔ (kunci) | Tinggi | Kunci jurnal denda tetap per nota | `services/gl_service.py:2036-2037` (`id:pay`), `:2017-2018` (`id:adjust`); `services/penalty_service.py:414-418, 439-444` | Bayar parsial kedua atau ubah kedua: nota berubah, jurnal dilewati. Bebas-denda setelah bayar sebagian membalik nominal penuh → piutang denda negatif | Kunci per kejadian; bebas = sisa; tolak ubah di bawah terbayar |
| FX-03 | Tinggi | Hari telat dihitung kumulatif, tetapi satu nota per bulan kalender | `services/penalty_service.py:128-134, 151-164`; tanggal "hari ini" dari klien `routers/payment_plans.py:175-184` | Telat 49 hari lintas dua bulan: nota Januari 21 hari + nota Februari 49 hari | Hitung selisih dari nota sebelumnya; buang tanggal dari klien |
| FX-05 ✔ | Tinggi | Alokasi dari deposit tidak memeriksa pemilik pesanan; deposit dikurangi setelah semua alokasi | `services/ar_receipt_service.py:178-189` (tanpa pelanggan/entitas, sehingga cek `:337, 342` dilewati); `services/payment_variance_service.py:549-564` | Deposit pelanggan A melunasi pesanan pelanggan atau PT B. Alokasi kedua gagal → pesanan pertama lunas, deposit utuh, tanpa jurnal | Validasi semua target dulu; deposit berkurang per alokasi |
| FX-06 | Tinggi | Hapus sisa pembayaran tanpa klaim; keputusan disimpan paling akhir | `services/payment_variance_service.py:691-694, 747-757, 811-818` | Dua klik → dua hapus-buku. Jurnal gagal → pesanan lunas tanpa jejak | Klaim kwitansi; simpan keputusan `pending` dulu; penanda gagal |
| FX-07 | Tinggi | Membatalkan keputusan selisih hutang tidak membalik jurnalnya | `services/payment_variance_service.py:944-948` vs `:1043-1051`; `services/vendor_bill_service.py:200-206` | Hutang hidup lagi di faktur, tetap terhapus di buku besar | Cabang pembalik untuk sisi hutang |
| FX-08 | Tinggi | Aksi kasus mengambil pesanan, kwitansi, rekening, pelanggan dari isi permintaan tanpa diadu dengan kasus atau cakupan pengguna | `services/finance_case_actions.py:201, 227, 285-298, 319-326, 428-452`; kasus boleh tanpa PT `services/finance_case_service.py:273-275` | Pemegang izin kasus di PT-B membebankan piutang PT-A, membatalkan kwitansi PT lain, refund deposit pelanggan lain | Adu semua id; tolak kasus tanpa PT (kelas IC-05) |
| FX-09 | Tinggi | Kasus: efek dulu, syarat kemudian; jurnal ber-kunci sama dilewati diam-diam | `services/finance_case_actions.py:324-330, 430-436, 508-526`; `services/gl_service.py:2203-2205`; `services/finance_case_service.py:457-475` | Langkah dijalankan dua kali atau gagal lalu diulang → pesanan lunas tanpa jurnal | Cek dulu; id pembayaran deterministik |
| FX-10 | Tinggi | Batas wewenang kasus lebih longgar dari hapus sisa; penyelesai = penyetuju | `services/finance_case_service.py:405-418, 494`; `services/finance_case_playbooks.py:107-112, 152-156` | Manajer dibatasi 1 jt untuk hapus sisa, tetapi lewat "biaya bank" tanpa batas | Satu batas untuk semua pengurang piutang non-kas; pembuat ≠ penyelesai |
| FX-11 | Tinggi | Kasus "salah entitas" menjurnal akun antar-PT tanpa dokumen antar-PT | `services/finance_case_actions.py:508-529` | Saldo antar-PT tumbuh di luar layar, tanpa jalur pelunasan | Buat dokumen antar-PT kembar |
| FX-12 | Tinggi | Nota kredit bisa melebihi faktur | `services/amendment_service.py:899-901, 916-929`; `services/return_service.py:204-223` | Harga dikoreksi turun 20 %, lalu barang diretur → kredit 120 % | Retur memakai nilai efektif; batas Σ nota kredit ≤ nilai pesanan |
| FX-04 | Sedang | Bayar denda langsung mendebit kas tanpa transaksi kas, rekening, kwitansi | `services/penalty_service.py:485-488`; `services/gl_service.py:2040-2046` | Kas buku besar naik, saldo rekening tidak | Lewat kas/kwitansi |
| FX-13 | Sedang | Nota kredit gagal di tengah tanpa penanda | `services/amendment_service.py:755-762, 976-980`; `services/od_cancel_credit_note.py:113-117` | Piutang pesanan turun, buku besar tidak | Penanda gagal + ulang (GL-02) |
| FX-14 | Sedang | Nota kredit amandemen selalu membalik pendapatan + PPN walau pendapatan belum diakui | `services/gl_service.py:2613-2623`; `services/amendment_service.py:281-282` | Pesanan dibayar, belum dikirim, dikoreksi → pendapatan dan PPN negatif | Samakan aturan dua jenis nota kredit |
| FX-15 | Sedang | Nota debit kenaikan harga berhenti di "menunggu aturan tagih" tanpa jurnal dan piutang | `services/amendment_service.py:911-914` | Kenaikan harga tidak tertagih | Putuskan aturan tagih |
| FX-16 | Sedang | Gerbang bayar-dulu bisa dilewati dengan mengganti termin; "terbayar" mencakup hapus sisa, kasus, nota kredit | `services/so_override_service.py:87-93`; `services/dispatch_payment_gate.py:62` | Pesanan bayar-dulu yang belum dibayar: ganti termin sebelum picking → terkirim | Ganti termin ke yang lebih longgar = izin setara pelepasan |
| FX-17 | Sedang | Endpoint rencana bayar dan selisih bayar tanpa penjaga entitas; jadwal bisa digeser tanpa riwayat | `routers/payment_plans.py:137-171, 214-262`; `routers/payment_variance.py:145-183`; `services/payment_plan_service.py:205, 304-308, 363-380` | Pengguna PT-B bertindak atas dokumen PT-A | Penjaga entitas; ubah jadwal hanya lewat jalur beralasan |
| FX-18 | Sedang | Pemindai kasus hanya mengecek kembar terhadap kasus terbuka; membaca 5.000 kwitansi tertua | `services/finance_case_scan.py:42-45, 73-74` | Kasus "bayar dobel" yang sudah ditutup lahir lagi tiap hari → refund kedua mungkin | Simpan keputusan per kwitansi |
| FX-19 | Rendah | Tanpa indeks unik untuk nota denda per periode, rencana aktif per dokumen, kasus per sumber | `indexes.py` | Dokumen kembar pada balapan | Indeks unik parsial |

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
| 14 | Empat cara mengurangi piutang tanpa kas (hapus sisa, kasus biaya bank, kasus uang-dipegang-karyawan, nota kredit) dengan batas wewenang berbeda | FX-10 | Satu batas dan satu jalur persetujuan |
| 15 | Empat pembuat nota kredit dengan kosakata status berbeda; hanya dua yang punya penanda gagal | FX-12, FX-13 | Satu mesin nota kredit |
| 16 | Tiga jalur deposit → pesanan lain; dua jalur refund deposit; tiga pembungkus alokasi tanpa validasi | FX-05 | Satu fungsi dengan validasi pemilik |
| 17 | Layar: lima dasbor, tiga antrean, tiga angka kas di tiga layar, piutang di tiga menu, dua cara buka periode; `fmtDate` disalin ≥10 berkas (zona waktu perangkat, bukan WIB) | Angka "sama" tampil berbeda | §7 |

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
11. **Pengurang piutang tanpa kas** (hapus sisa, kasus biaya bank, uang dipegang karyawan, nota kredit): satu batas
    wewenang dan pembuat ≠ penyetuju untuk semuanya? (FX-10)
12. **Anggaran:** cukup peringatan atau memblokir, dan dokumen apa saja yang dicakup? (FY-12)
13. **Tanggal buku jurnal periodik** (penyusutan, gaji, insentif): akhir periode atau hari posting? (FY-02)
14. **Nota debit kenaikan harga:** aturan tagihnya apa? (FX-15) · **Ganti termin** ke yang lebih longgar: perlu izin
    setara pelepasan tanpa bayar? (FX-16)

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

## 12. Pemeriksaan data (baca-saja)

### 12.1 Pakai dulu penjaga data yang sudah ada

Repo sudah punya `scripts/verify_data_integrity.py` (229 invarian; tidak ada operasi tulis di dalamnya — dicek dengan
grep; lapisan bisa dipilih dengan `--only`). Lapisan keuangan hanya butuh `MONGO_URL` dan `DB_NAME`, tidak butuh login
API. Jalankan pada **salinan** data nyata (pulihkan cadangan ke nama database lain), dari dalam container backend:

```bash
docker compose -f docker-compose.dev.yml exec -e DB_NAME=<nama_db_salinan> backend \
  python /app/scripts/verify_data_integrity.py \
  --only gl,gl_audit,numbering,tax,asset,budget,payment,variance,bank,case,contrabon,interco,closing --timing
```

Catatan: penjaga ini dirancang untuk data seed bersih, jadi pada data nyata bisa menuduh dokumen lama; bacalah
hasilnya sebagai daftar periksa, bukan vonis. Belum saya jalankan (tidak ada MongoDB di sesi ini). Kuitansi gerbang
terakhir yang tersimpan (`memory/GATE_RECEIPT.json`) bertanggal 22 Sep 2026: 111 gerbang, hasil keseluruhan MERAH karena
satu gerbang (INV-GATE-01 anti-residu); `verify_data_integrity` saat itu lulus pada data seed. Tidak ada kuitansi yang
lebih baru di repo.

**Cakupan penjaga itu terhadap temuan audit** (menurut deskripsi invariannya; isi tiap invarian tidak saya telusuri
baris demi baris):

| Kelas masalah | Invarian yang ada | Menangkap? |
|---|---|---|
| Jurnal antar-PT sebelah (IC-01) | INV-IC-01 (pasangan jurnal di dua buku), INV-IC-08 (retur) | Ya untuk jual-beli dan retur; settlement lewat INV-IC-04 |
| Piutang ≠ utang antar-PT (IC-06, IC-07) | INV-IC-02, INV-IC-04 | Ya |
| Eliminasi (IC-03, IC-04) | INV-IC-03 (kondisi saat ini) | Tidak untuk laporan historis dan rantai A→B→C |
| Kontrabon (SL-01, SL-12) | INV-CB-01…04 | Sebagian — total dan potongan ganda ya; kas tanpa jurnal tidak |
| Titipan bank tanpa jurnal (SL-03), biaya bank (SL-04) | INV-BNK-03, INV-BNK-04 | Ya |
| Jurnal ganda per dokumen | INV-GL-DUP-01, INV-CASH-02 | Ya, tetapi membuang tipe pembalik → **pembalikan ganda (GL-01) tidak** |
| Jurnal tidak seimbang | GL-1 | Hanya selisih > Rp 0,50 → **selisih 1 sen (GL-07) tidak** |
| Persediaan vs akun 1-1300 (IV-01, 02, 06) | GL-3 / INV-GL-DRIFT | Hanya peringatan (WARN), bukan gagal |
| Nomor kembar, counter tertinggal | INV-NUM-01, INV-NUM-02 | Ya |
| Jurnal menyusup ke periode tertutup; kontrol ganda buka periode | INV-CLS-01, INV-CLS-02 | Ya (INV-CLS-02 akan memerah bila admin menyetujui usulnya sendiri — GL-06) |
| Pesanan terkirim tanpa jurnal pendapatan; pembayaran yatim | INV-GL-REV-01, INV-AR-02 | Ya |
| Total aging piutang vs akun 1-1200; hutang vs akun 2-1100; deposit vs 2-1400 | INV-AR-01 (hanya bocor ke entitas "all" dan saldo negatif) | **Tidak** |
| Faktur supplier/landed cost/kas bayar tanpa jurnal (GL-02, GL-03, IV-04) | — | **Tidak** |
| GR/IR menggantung (IV-03); roll scrap masih bernilai (IV-02); HPP dari roll berbiaya 0 (IV-07) | — | **Tidak** |
| Dokumen berpenanda gagal di luar panel; kunci saga tertinggal | — | **Tidak** |
| Jurnal manual di buku PT lain (IC-05) | — | Tidak bisa dari data (jurnalnya sah secara bentuk) |
| Setoran karyawan ganda (FX-01); deposit lintas pelanggan (FX-05); nota kredit > faktur (FX-12) | INV-CASE-03 (kasus pemindah uang punya ≥ 1 jurnal seimbang), INV-VAR-02 | **Tidak** |
| Piutang denda vs nota (FX-02) | INV-PEN-03 | Ya, tetapi dijumlah lintas PT |
| Aset tanpa jurnal perolehan, jurnal periodik salah bulan, hutang BPJS/PPh menumpuk (FY-01, 02, 07) | INV-FA (konsistensi aset ↔ buku besar) | Belum dipastikan untuk FY-01; **tidak** untuk FY-02 dan FY-07 |

Satu-satunya pemeriksaan yang berjalan otomatis di aplikasi adalah pemindai kasus harian pukul 08:25
(`services/scheduler_service.py:148-151`): titipan bank menganggur lebih dari 3 hari dan dua kwitansi bernominal sama
dari pelanggan yang sama dalam 7 hari. Semua invarian lain hanya ada di skrip luring ini.

Batas penjaga itu sendiri: jurnal dimuat dengan `to_list(200000)` (`scripts/verify_data_integrity.py:1113`), jadi di
atas 200.000 jurnal pemeriksaannya terpotong tanpa peringatan.

### 12.2 Kueri tambahan untuk yang belum tercakup

**Belum dijalankan** — ditulis dari pembacaan kode. Uji dulu di salinan database (`mongosh`), bukan di produksi. Kueri
1–3, 9–10 tumpang-tindih dengan penjaga di 12.1 dan berguna bila ingin melihat datanya langsung; kueri 4–8 dan 11–17
menutup celah di tabel atas. Kueri untuk temuan lanjutan (FY, FX) ada di
[`KUERI_CEK_DATA_LANJUTAN_2026-11-13.md`](KUERI_CEK_DATA_LANJUTAN_2026-11-13.md).

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

1. Jalankan penjaga data yang sudah ada (§12.1), lalu kueri tambahan (§12.2), di salinan data nyata — mengetahui mana
   yang **sudah** terjadi menentukan prioritas.
2. Keputusan pemilik §10 (terutama 1–4).
3. Kritis: IC-01, SL-01.
4. Tinggi yang murah: FX-01 (hapus satu panggilan kas ganda), FX-02 (kunci jurnal denda per kejadian), FX-05 (cek
   pemilik pesanan), IC-05 dan FX-08 (validasi entitas), GL-04 (cek tanggal tutup), GL-01 (satu penanda pembalik),
   SL-03 (`source_id`), UX-01/02/03 (klik ganda, kunci idempotensi, konfirmasi), GL-09 (indeks wajib-ada).
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
