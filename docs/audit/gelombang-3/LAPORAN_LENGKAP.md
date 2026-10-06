# KNHOST — Paket perbaikan Gelombang 3

Audit dihentikan atas permintaan pengguna pada 6 Oktober 2026. Paket ini memuat **101 catatan perbaikan: 78 dari checkpoint sebelumnya + 23 tambahan lanjutan**. Angka ini tidak berarti 101 bug baru muncul setelah patch: 19 dari checkpoint sebelumnya berasal dari temuan lama yang masih terbuka; label asal dan bukti ada pada tracker. Seluruh ID dipertahankan agar mudah ditautkan saat validasi berikutnya. Prioritas seluruh register: {'P1': 63, 'P2': 37, 'P3': 1}; tambahan: {'P2': 12, 'P1': 11}.

Snapshot source yang diaudit: `a904d989b622f7da14c4892d03cf6ef0c43f3084`. **Target 90% belum tercapai.** Cakupan eksekusi backend runtime/startup ketika dihentikan: **82.52% statement** (59,594/72,221) dan **68.35% cabang** (15,727/23,008), denominator tetap 480 berkas. Ini bukan persentase kebenaran bisnis atau jaminan semua flow telah diuji. Register cakupan mencatat pekerjaan yang masih terbuka.

## Cara import dan mulai

1. Ekstrak ZIP ke root repo sehingga folder baru menjadi `docs/audit/gelombang-3/`. Pertahankan folder Gelombang 1 dan 2. Tidak ada patch kode aplikasi di paket ini.
2. Baca [register](DAFTAR_TEMUAN.md), [laporan lengkap](LAPORAN_LENGKAP.md), dan [batas cakupan](CAKUPAN_DAN_BATAS.md).
3. Berikan [prompt awal](PROMPT_MULAI_AGENT.md) ke agent; kerjakan [fase 01](prompts/FASE-01.md) lebih dulu, kemudian fase 02–04 dengan prasyarat yang tercatat. Fase 05 menutup regresi dan bukti validasi.
4. Agent memperbarui `findings-tracker.json` dan bukti implementasi per ID. Gunakan `implemented_pending_validation`, lalu kirim repo/commit dan template permintaan validasi kepada reviewer. `verified_fixed` memerlukan verifikasi independen.

## Isi paket

- `TEMUAN_TAMBAHAN_23.md`: lokasi kode, sebab, rantai masalah, bukti expected/actual, batas klaim, prompt dan acceptance bagi 23 tambahan.
- `baseline-78/`: paket checkpoint sebelumnya beserta 78 detail, 137 register revalidasi Gelombang 1/2, bukti dan skrip; dipertahankan sebagai referensi historis. README/count di subfolder itu hanya menjelaskan checkpoint lama.
- `findings-tracker.json` / CSV, `repair-phases.json`, lima prompt fase, dan template status/validasi: sumber kendali kerja Gelombang 3.
- `evidence/repro/`: hasil counterexample dan kontrol tambahan; `evidence/continuation-90/`: hasil suite native, adapters, hipotesis ditolak, dan cakupan. Nonpass suite lama tidak otomatis dimasukkan sebagai temuan baru.
- `repro/`: skrip counterexample/runner dan petunjuk rerun. Gunakan database audit lokal; jangan jalankan pada produksi. Bukti historis tidak boleh ditimpa.
- `manifest.json` dan `VERIFY_PACKAGE.md`: identitas snapshot, hash file, dan hasil pemeriksaan paket.


---

# Cakupan dan batas saat audit dihentikan

Denominator backend runtime/startup tetap 480 berkas, 72,221 statement dan 23,008 cabang. Tercakup 59,594 statement (82.52%) dan 15,727 cabang (68.35%). Belum tercakup 12,627 statement serta 7,281 cabang. Target 90% belum tercapai; audit tidak diberi label selesai menyeluruh.

Inventory seluruh file, parse, pencarian literal API, pembacaan source, eksekusi statement, eksekusi cabang, dan kebenaran angka UI adalah jenis bukti yang berbeda. Pemetaan frontend statis 1.431/1.477 panggilan (96,89%) tidak membuktikan 96,89% angka rendered benar. Sebanyak 46 pemetaan belum terselesaikan. Denominator seluruh tracked backend berisi 603 file, 102.029 statement dan 29.916 cabang, termasuk 107 native/POC test dan 16 skrip offline; pemisahan ini tidak diubah untuk menaikkan angka.

## Pekerjaan yang belum dinyatakan selesai

- Cabang/fungsi yang masih kosong di `evidence/continuation-90/function-gaps90.json` dan laporan coverage per file. Register dihasilkan dari tracing; daftar gap harus diperbarui terhadap commit sesudah perbaikan.
- Penelaahan semua kegagalan suite lama. Replay tambahan 49 modul menghasilkan 551 kasus: 357 lulus, 157 nonpass, 37 skip. Ini snapshot replay, bukan seluruh jumlah testcase unik audit. Sebagian memakai fixture lama/hardcoded resource atau kontrak lama; tetap terbuka untuk adjudikasi. Sampling performer adapter tercatat dan assertion asli dipertahankan.
- Browser/DOM numerik seluruh dashboard, RFID/gate fisik, pembacaan tag nyata, printer/stiker, dan integrasi AI/OCR provider nyata. Pemeriksaan source/ekspresi bukan uji perangkat atau browser.
- Dua jalur PDF OCR belum diuji karena PyMuPDF tidak tersedia dan instalasi mengalami batas lingkungan/TLS. Native mock OCR 67 kontrol lulus tidak membuktikan akurasi ekstraksi dokumen nyata.
- Data produksi dan migrasi produksi belum diuji. Fixture master/legacy yang sengaja tidak konsisten digunakan hanya untuk menguji scanner/backfill; tidak membuktikan producer normal membuat kerusakan tersebut.
- Semua temuan Gelombang 3 masih berstatus open sampai perbaikan dan validasi independen. Register 137 ID lama memiliki tingkat bukti berbeda; status historis bukan klaim terbaru bahwa seluruh acceptance sudah lulus.

## Kontrol yang lulus pada lanjutan

Label/master/tarif: 134 kontrol lulus. R&D edit dan feedback counter: 98 lulus. Cash-advance lifecycle: 52 lulus. Budget/GL/policy: 214 observasi, termasuk kontrol account direction, jumlah seimbang, anti-duplikasi replay dan batas amount; tujuh perbedaan menghasilkan tiga temuan. HR KPI: 36 observasi dengan tujuh perbedaan yang menghasilkan tiga temuan. Jumlah observasi bukan jumlah bug, bukan persentase kebenaran sistem, dan bukan penjumlahan testcase unik dari berbagai replay.

Beberapa hipotesis ditolak: kewenangan lintas entitas manager yang memang disengaja, helper gudang bersama yang bukan validator entitas, dan dua label dengan ekspektasi tes salah. Bukti awal dipertahankan sebagai histori, sementara hasil final menggunakan oracle/fixture yang dikoreksi. Penolakan otomatis saat membuat probe QC/CRM/config baru membuat aksi itu tidak dijalankan; probe tersebut tidak dimasukkan sebagai hasil pengujian.


---

# Register seluruh temuan Gelombang 3

| ID | Prioritas | Fase | Domain | Asal | Temuan |
|---|---|---|---|---|---|
| V3-PROD-01 | P1 | 01 | MD, R&D dan master komersial | checkpoint sebelumnya | Konsumsi bahan dapat berulang setelah movement insert gagal |
| V3-PROD-02 | P1 | 01 | MD, R&D dan master komersial | checkpoint sebelumnya | Reversal dianggap selesai sebelum panjang roll dipulihkan |
| V3-MRES-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Dua PR mencadangkan bahan lebih banyak daripada stok |
| V3-AR-01 | P1 | 01 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh |
| V3-BANK-01 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh |
| V3-WEIGHT-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Split bersamaan menggandakan berat walaupun panjang benar |
| V3-PO-01 | P2 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Task selisih PO tidak refresh dan kehilangan identitas baris |
| V3-MKO-01 | P1 | 01 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Retry penerimaan maklon menambah output fisik dan nilai stok |
| V3-RFID-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Read green dari passage lama dipakai kembali pada passage baru |
| V3-CF-01 | P1 | 03 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Jurnal campuran kas/nonkas menghasilkan klasifikasi arus kas salah |
| V3-DATE-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Jurnal date-only pada awal periode hilang dari laporan |
| V3-WMS-02 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Loading gudang siap ditahan oleh pending cut gudang lain |
| V3-MASTER-01 | P2 | 01 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Apply master mengubah produk sebelum snapshot batch durable |
| V3-PO-02 | P2 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pilihan amend ke jumlah diterima bertentangan dengan guard PO lama |
| V3-CUT-01 | P1 | 01 | RFID, WMS dan stok | checkpoint sebelumnya | Gagal membuat child cut menghilangkan stok dan reservasi |
| V3-MRES-02 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Total cadangan maklon tetap terpotong pada batas query |
| V3-PO-03 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Tugas selisih selesai meski amendment belum disetujui dan qty belum berubah |
| V3-DUP-01 | P3 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Helper _clean_perms didefinisikan dua kali |
| V3-BUILD-01 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Dependency build frontend tidak mempunyai lockfile terlacak |
| D4-STOCK-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Nilai dan kecepatan stok terhitung dua kali ketika pemilik berbagi SKU dan gudang |
| D4-STOCK-02 | P2 | 04 | RFID, WMS dan stok | checkpoint sebelumnya | Filter kategori tidak diterapkan pada bucket umur stok |
| D4-STOCK-03 | P2 | 04 | RFID, WMS dan stok | checkpoint sebelumnya | Nilai persediaan analitik mengabaikan landed cost |
| D4-STOCK-04 | P2 | 04 | RFID, WMS dan stok | checkpoint sebelumnya | Tanggal roll tanpa timezone dapat menjatuhkan laporan umur stok |
| D4-FIN-01 | P1 | 03 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Control Tower menggabungkan AR semua entitas ketika parameter entitas dihilangkan |
| D4-SALES-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Target penjualan dan penagihan tidak mengikuti scope entitas |
| D4-SALES-02 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Sales Home masih menampilkan order dan piutang lintas entitas di kartu pelanggan |
| D4-SALES-03 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Komisi per-SKU memasukkan SO tim sales milik entitas lain |
| D4-FIN-02 | P1 | 03 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Forecast kas memakai basis AR dan termin berbeda dari AR kanonis |
| D4-FIN-03 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Revenue profitabilitas memasukkan PPN included dan mengabaikan diskon header legacy |
| D4-FIN-04 | P2 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Label pendapatan realisasi sebenarnya memakai pesanan reserved dan WAC terkini |
| D4-AI-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Analytics AP mengabaikan fallback vendor bill yang masih dipakai sumber kanonis |
| D4-AI-02 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Metric pelanggan baru mengabaikan scope lini |
| D4-AI-03 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Refresh fact sales menghapus data lama sebelum replacement berhasil |
| D4-AI-04 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pembulatan alokasi tim sales tidak mengonservasi nilai dokumen |
| D4-AI-05 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Stok tersedia dan reserved di live analytics serta snapshot mengabaikan reservasi parsial |
| D4-AI-06 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Total quantity lintas produk menjumlahkan meter dengan kilogram |
| D4-CASH-01 | P1 | 03 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Saldo awal kas kecil berpindah menjadi kas besar setelah transaksi terakhir di-void |
| D4-DASH-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Batas katalog 3.000 SKU masih menghilangkan master dan cadangan pada KPI |
| D4-HR-01 | P1 | 04 | HR dan KPI | checkpoint sebelumnya | Payroll gabungan memakai satu run pada KPI dan menimpa run lain pada trend |
| D4-HR-02 | P2 | 04 | HR dan KPI | checkpoint sebelumnya | Turnover menggunakan waktu edit data sebagai waktu karyawan keluar |
| D4-WMS-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | RFID RED hari ini pada Warehouse Health memakai hari UTC |
| D4-WMS-02 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Cycle count terbaru yang belum selesai menghapus angka akurasi terakhir |
| D4-WMS-03 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Utilisasi gudang mengabaikan struktur Rack→Level→Bin yang didukung master |
| D4-MKT-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Reach agregat post disajikan ulang sebagai reach tiap platform dan akun |
| D4-RND-01 | P2 | 04 | MD, R&D dan master komersial | checkpoint sebelumnya | KPI R&D menggabungkan orang berbeda yang mempunyai nama sama |
| D4-FE-01 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Grafik velocity Manager selalu memotong menjadi14hari |
| D4-FE-02 | P1 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Respons periode lama dapat menimpa grafik setelah periode diganti |
| D4-TEST-01 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Tes konsistensi ATP dapat lulus walaupun mencatat mismatch |
| D4-DATE-01 | P2 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Penjualan dan Home menggunakan bulan/tahun UTC yang berbeda dari periode bisnis WIB |
| D4-PLAN-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Rencana pembelian mencatat qty yang berbeda dari PR yang dirujuk |
| D4-PLAN-02 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Baris produk ganda pada API rencana dapat membuat pembelian melebihi kekurangan |
| D4-PLAN-03 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Riwayat mengatakan pemenuhan penuh walaupun sebagian eksekusi gagal |
| D4-PLAN-04 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pesan kegagalan pemenuhan parsial terhapus oleh refresh otomatis |
| D4-PLAN-05 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pasokan masuk yang sama dapat direncanakan penuh untuk beberapa SO |
| D4-GLOBAL-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Barang datang 100 yard dilabelkan 100 meter pada katalog stok global |
| D4-SUPPLY-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Sisa PO diterima sebagian hilang dari incoming karena definisi status berbeda |
| D4-BACKORDER-01 | P1 | 01 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pemenuhan stok bersamaan mereservasi 160 untuk SO yang hanya kurang 100 |
| D4-CAP-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | SKU yang benar-benar ada ditolak saat membuat PO setelah 1.000 master pertama |
| D4-ORDER-01 | P1 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Rata-rata pesanan membagi revenue seluruh pesanan dengan hanya 20 pesanan terbaru |
| D4-CASE-01 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Refund store credit menjurnal pengurangan kewajiban dua kali dan menciptakan pendapatan semu |
| D4-CASE-02 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Penyelesaian kasus keuangan dapat mengulang kas yang sudah tercatat setelah konflik atau kegagalan |
| D4-INTERCO-01 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Transfer roll retur dapat selesai memindahkan pemilik tetapi kehilangan jurnal pasangan dan dokumen pemulihan |
| D4-INTERCO-02 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Nilai transfer antarentitas memakai WAC sesudah stok sumber dipindahkan |
| D4-DOC-01 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pratinjau Template Dokumen Dasar memanggil endpoint yang tidak tersedia dan mengabaikan jenis template |
| D4-CASE-03 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Alur dana dipegang karyawan tidak menjaga urutan langkah dan sisa piutang |
| D4-CLOSE-01 | P2 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Reopen bulan tidak menandai penutupan tahun yang bergantung padanya sebagai basi |
| D4-CLOSE-02 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Tutup ulang gagal mengadopsi jurnal yang sudah tersimpan sehingga recovery admin tetap gagal |
| D4-GL-01 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Jurnal manual yang sudah dibalik masih dapat dianulir dan membentuk pembatalan dua kali |
| D4-GL-02 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Jurnal manual meloloskan NaN/Infinity dan menghilangkan angka transaksi sah dari laporan |
| D4-EQ-01 | P1 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | KPI Laba Periode Berjalan pada perubahan ekuitas berubah menjadi nol sesudah tutup buku |
| D4-COA-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Mode Semua Entitas pada laporan keuangan menghilangkan akun khusus entitas yang sah |
| D4-PA-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Reservasi SO mengambil roll yang sudah diklaim putaway dan meninggalkan lokasi alokasi lama |
| D4-PA-02 | P1 | 01 | RFID, WMS dan stok | checkpoint sebelumnya | Putaway kehilangan checkpoint setelah roll berpindah sehingga recovery stok dan tag gagal |
| D4-PA-03 | P2 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Total putaway menjumlahkan meter dan yard lalu memberi satu label satuan |
| D4-WMS-04 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | KPI antrean simpan menghitung roll reserved yang tidak boleh diputaway |
| D4-RFID-01 | P1 | 01 | RFID, WMS dan stok | checkpoint sebelumnya | Deduplikasi event RFID melewati recovery keputusan, insiden dan status passage |
| D4-CC-01 | P2 | 01 | RFID, WMS dan stok | checkpoint sebelumnya | Recovery cycle count membuat dua laporan dan nomor untuk satu sesi |
| D4-TAG-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Verifikasi tag lama tetap berlaku setelah tag dihapus atau diganti dengan tag pending |
| D4-SIM-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | tambahan | Simulator menyatakan 3-way match lolos saat barang belum diterima |
| D4-BANK-01 | P2 | 04 | Finance dan kontrol pembayaran | tambahan | Tanggal kalender yang tidak mungkin masuk ke data rekonsiliasi bank |
| D4-BANK-02 | P2 | 04 | Finance dan kontrol pembayaran | tambahan | Parser MT940 tidak membaca kode pembalikan transaksi RC dan RD |
| D4-ASSET-01 | P1 | 01 | Finance dan kontrol pembayaran | tambahan | Penyusutan yang gagal mengunci periode sehingga retry tidak memperbaiki aset |
| D4-ASSET-02 | P1 | 01 | Finance dan kontrol pembayaran | tambahan | Penyusutan dua periode bersamaan membuat register aset tertinggal dari jurnal |
| D4-ICLOAN-01 | P1 | 02 | Finance dan kontrol pembayaran | tambahan | Akun Finance dapat mengubah pinjaman entitas yang tidak ditugaskan kepadanya |
| D4-RFQ-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Award RFQ tetap membuat PO untuk item yang dinyatakan tidak tersedia |
| D4-RFQ-02 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Perbandingan dan pembatalan RFQ tidak mengikuti pembatasan entitas pada halaman detail |
| D4-CB-01 | P2 | 05 | Finance dan kontrol pembayaran | tambahan | Pemeriksa kontrabon dapat memberi hasil bersih karena hanya memeriksa 2.000 dokumen pertama |
| D4-UOM-BF-01 | P2 | 03 | Sales, procurement, logistik dan consumer lain | tambahan | Backfill jumlah roll memakai panjang daftar ID mentah, berbeda dari resolver roll nyata |
| D4-RET-CHAIN-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | tambahan | Ringkasan fisik rantai retur menjumlahkan barang berlainan satuan menjadi satu angka |
| D4-ALERT-DATE-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | tambahan | Peringatan AP menyebut jatuh tempo hari ini sudah terlambat satu hari |
| D4-ALERT-AMT-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | tambahan | Peringatan utang menampilkan nominal penuh meskipun pembayaran sebagian sudah tercatat |
| D4-ALERT-WMS-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Notifikasi tugas WMS mencampur pesanan dua entitas yang memakai gudang sama |
| D4-PRICE-SCOPE-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Scope harga khusus berbeda antara detail, perubahan, harga efektif dan ringkasan |
| D4-OD-LOCK-01 | P1 | 01 | MD, R&D dan master komersial | tambahan | Kegagalan pembaruan SKU meninggalkan harga OD terkunci dan pengulangan tidak dapat memulihkannya |
| D4-COMM-BOUNDS-01 | P1 | 03 | MD, R&D dan master komersial | tambahan | Perubahan master komersial melewati batas angka dan dapat menghasilkan ongkos makloon negatif |
| D4-KPI-WEIGHT-01 | P2 | 04 | HR dan KPI | tambahan | Bobot KPI nol menjadi satu dan mengubah rata-rata tertimbang |
| D4-KPI-PERIOD-01 | P2 | 04 | HR dan KPI | tambahan | Periode KPI yang bukan bulan kalender diterima dan dipilih sebagai periode terbaru |
| D4-KPI-SCORE-01 | P2 | 04 | HR dan KPI | tambahan | Skor otomatis KPI dapat negatif meskipun kontrak fungsi menyatakan rentang 0–150 |
| D4-BUD-EDIT-01 | P1 | 03 | Finance dan kontrol pembayaran | tambahan | Perubahan anggaran melewati keunikan periode/kunci dan batas tahun |
| D4-BUD-THRESHOLD-01 | P2 | 04 | Finance dan kontrol pembayaran | tambahan | Ambang peringatan anggaran 0% berubah menjadi 85% pada laporan |
| D4-RET-POLICY-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Deadline retur dapat berubah karena PO terbaru entitas lain dengan produk yang sama |


---

# Gelombang 3 — 23 temuan tambahan

Snapshot audit: `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Seluruh temuan memiliki counterexample; jenis bukti dan batas fixture dibedakan. Status tes negatif atau error suite lama tidak otomatis dianggap bug.

## D4-SIM-01 — Simulator menyatakan 3-way match lolos saat barang belum diterima

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Pusat Pengaturan → simulator pencocokan Tagihan Supplier.

**Rantai kejadian:** Simulator received_qty 0/billed_qty 10 → selisih dianggap0 → LOLOS; evaluator bill operasional → blocked.

**Letak kesalahan dan penyebab:** Cabang pembagi nol mengubah selisih kuantitas menjadi nol. Simulator memakai rumus tersendiri yang berbeda dari evaluator transaksi sebenarnya.

**Dampak, hasil reproduksi, dan batas klaim:** Public simulate menerima received 0/billed 10 dengan toleransi qty0 dan memberi verdict ok. Evaluator layanan vendor bill asli untuk kondisi yang sama memblokir. Kontrol received100/billed 100 lolos; billed 101/received100 melampaui toleransi ditolak. Ini informasi konfigurasi yang salah, bukan bukti tagihan operasional ini otomatis lolos.

**Lokasi source pada commit audit:**

- [backend/services/config_simulator.py:192](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/config_simulator.py#L192) — `dq = ((bill_q - recv_q) / recv_q * 100) if recv_q else 0`.
- [backend/services/vendor_bill_service.py:96](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/vendor_bill_service.py#L96) — `def evaluate_match(`.
- [backend/routers/config.py:160](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/config.py#L160) — `async def simulate(`.

```python
190:     tq = _f(c.get("purchasing.bill_qty_tolerance_percent"), 0)
191:     tp = _f(c.get("purchasing.bill_price_tolerance_percent"), 5)
192:     dq = ((bill_q - recv_q) / recv_q * 100) if recv_q else 0
193:     dp = ((bill_p - po_p) / po_p * 100) if po_p else 0
194:     steps = [{"label": "Selisih qty", "value": f"{_num(dq)}% (toleransi {_num(tq)}%)"},
195:              {"label": "Selisih harga", "value": f"{_num(dp)}% (toleransi {_num(tp)}%)"}]
196:     bad = []
197:     if abs(dq) > tq:
198:         bad.append("qty")
```

**Bukti asli:** [evidence/repro/config-bank-oracles90-results.json](evidence/repro/config-bank-oracles90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| SIM90-ar_penalty-0 | "ok" | "ok" | pass |
| SIM90-ar_penalty-1 | "warn" | "warn" | pass |
| SIM90-ar_penalty-2 | "block" | "block" | pass |
| SIM90-ar_bucket-3 | "ok" | "ok" | pass |
| SIM90-pricing-4 | "warn" | "warn" | pass |
| SIM90-pricing-5 | "ok" | "ok" | pass |
| SIM90-commission_cap-6 | "warn" | "warn" | pass |
| SIM90-commission_cap-7 | "ok" | "ok" | pass |
| SIM90-commission_discount-8 | "warn" | "warn" | pass |
| SIM90-commission_discount-9 | "warn" | "warn" | pass |

**Prompt agent development:**

Gunakan evaluator aturan yang sama untuk simulator dan transaksi, dengan konteks simulasi eksplisit. Saat received 0/billed>0, hasil harus menyatakan belum ada penerimaan dan blokir sesuai basis matching. Jangan mengisi delta0 untuk menghindari pembagi nol.

**Kriteria penerimaan untuk reviewer:**

received 0/billed 10/tolerance0 harus block; nol/nol dijelaskan tanpa NaN. Uji partial receipt, billing cumulatif, qty sisa, tolerance, harga, basis ordered vs received, return/short-close. Hasil simulator dan evaluator harus sesuai untuk input bisnis ekuivalen.

## D4-BANK-01 — Tanggal kalender yang tidak mungkin masuk ke data rekonsiliasi bank

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Keuangan → Rekonsiliasi Bank → preview/import mutasi.

**Rantai kejadian:** Tanggal mentah → format string ISO tanpa validasi kalender → preview valid → import persisten.

**Letak kesalahan dan penyebab:** Parser hanya merapikan komponen tanggal untuk beberapa format. Validasi import memeriksa tanggal tidak kosong, sehingga string tanggal yang bukan tanggal kalender tetap disimpan.

**Dampak, hasil reproduksi, dan batas klaim:** Public preview dan import menerima serta menyimpan 2026-02-30, 2026-99-99, 2026-13-01. Kontrol 2026-02-28 diparsing dan disimpan dengan benar. Ini merusak dimensi periode dan kualitas source rekonsiliasi; skenario tidak melakukan transfer dana atau posting GL.

**Lokasi source pada commit audit:**

- [backend/services/bank_statement_parser.py:179](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_statement_parser.py#L179) — `return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"`.
- [backend/services/bank_recon_service.py:348](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_recon_service.py#L348) — `async def import_lines(`.
- [backend/routers/bank_reconciliation.py:38](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/bank_reconciliation.py#L38) — `class StatementLineIn(`.

```python
177:     m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
178:     if m:
179:         return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
180:     if fmt == "yyyymmdd" and re.fullmatch(r"\d{8}", s):
181:         return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
182:     if fmt == "yymmdd" and re.fullmatch(r"\d{6}", s):
183:         return f"20{s[0:2]}-{s[2:4]}-{s[4:6]}"
184:     if re.fullmatch(r"\d{8}", s):
185:         return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
```

**Bukti asli:** [evidence/repro/config-bank-oracles90-results.json](evidence/repro/config-bank-oracles90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| SIM90-zero-receipt-public-verdict | "block" | "ok" | observed_difference |
| BANK90-date-preview-2026-02-30 | 0 | 1 | observed_difference |
| BANK90-date-persistence-2026-02-30 | 0 | 1 | observed_difference |
| BANK90-date-preview-2026-99-99 | 0 | 1 | observed_difference |
| BANK90-date-persistence-2026-99-99 | 0 | 1 | observed_difference |
| BANK90-date-preview-2026-13-01 | 0 | 1 | observed_difference |
| BANK90-date-persistence-2026-13-01 | 0 | 1 | observed_difference |
| BANK90-mt940-RC | "out" | "not_parsed" | observed_difference |
| BANK90-mt940-RD | "in" | "not_parsed" | observed_difference |
| BANK90-mt940-reversal-net | 0 | -100.0 | observed_difference |

**Prompt agent development:**

Validasi semua jalur tanggal lewat satu parser kalender yang ketat, termasuk model input langsung. Kembalikan error per baris untuk tanggal tidak sah; jangan normalize ke bulan berikutnya. Pertahankan year_hint dan locale yang eksplisit; tanggal ambigu membutuhkan format yang dipilih.

**Kriteria penerimaan untuk reviewer:**

Tanggal mustahil ditolak preview/import/direct-line; leap-year 2024-02-29 sah dan 2026-02-29 ditolak. Uji ISO, compact, dd/mm, mm/dd, teks bulan, MT940, OFX, timestamp, tahun kosong, whitespace, error parsial dan filter periode.

## D4-BANK-02 — Parser MT940 tidak membaca kode pembalikan transaksi RC dan RD

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Keuangan → Rekonsiliasi Bank → import MT940.

**Rantai kejadian:** Field61 D100 + RD100 → hanya D terbaca → preview/import saldo bersih keluar100.

**Letak kesalahan dan penyebab:** Regex menerima huruf C/D lalu R opsional. Format pembalikan MT940 memakai RC/RD, dengan R sebelum C/D; arah transaksi pembalikan juga harus dibalik.

**Dampak, hasil reproduksi, dan batas klaim:** Kontrol mutasi C/D biasa lolos. Statement sintetik D100 dan RD100 menghasilkan hanya1 mutasi dengan error1 dan net keluar100, padahal pasangan itu net0. Public import mengimpor baris biasa dan mengembalikan error pembalikan; error terlihat, sehingga temuan tidak menyebut hilangnya baris secara diam-diam. Standar primer: UniCredit MT94x General V1.1, Field61 (https://www.unicredit.ro/content/dam/cee2020-pws-ro/DocumentePDF/DocumenteCIB/MT94x_General_V1.1.pdf).

**Lokasi source pada commit audit:**

- [backend/services/bank_statement_parser.py:416](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_statement_parser.py#L416) — `(?P<mark>[CD])R?`.
- [backend/routers/bank_reconciliation.py:202](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/bank_reconciliation.py#L202) — `async def import_file(`.

```python
414: 
415: RE_MT940_61 = re.compile(
416:     r"^:61:(?P<vdate>\d{6})(?P<edate>\d{4})?(?P<mark>[CD])R?(?P<amt>[\d.,]+)"
417:     r"(?P<code>[A-Z]\w{3})?(?P<rest>.*)$")
418: 
419: 
420: def parse_mt940(raw: str, fmt: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
421:     rows: List[Dict[str, Any]] = []
422:     errors: List[Dict[str, Any]] = []
```

**Bukti asli:** [evidence/repro/config-bank-oracles90-results.json](evidence/repro/config-bank-oracles90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| BANK90-mt940-C | "in" | "in" | pass |
| BANK90-mt940-D | "out" | "out" | pass |
| BANK90-mt940-RC | "out" | "not_parsed" | observed_difference |
| BANK90-mt940-RD | "in" | "not_parsed" | observed_difference |
| BANK90-mt940-reversal-net | 0 | -100.0 | observed_difference |

**Prompt agent development:**

Parse debit/credit marker sebagai D, C, RC, RD sesuai format; RC berarti debit dan RD berarti credit. Pertahankan error per baris dan status import parsial yang jelas. Rekonsiliasikan opening/movement/closing balance sebelum pengguna menganggap file lengkap.

**Kriteria penerimaan untuk reviewer:**

D100+RD100 menghasilkan2 baris/net0; C100+RC100 juga0. Uji funds-code, entry date, references, :86:, multiple statements, malformed marker, duplicate import, saldo akhir dan kebijakan partial vs atomic.

Rujukan Field 61: [UniCredit MT94x General V1.1](https://www.unicredit.ro/content/dam/cee2020-pws-ro/DocumentePDF/DocumenteCIB/MT94x_General_V1.1.pdf). Error parser memang terlihat; temuan ini tidak menyatakan kehilangan data tanpa peringatan.

## D4-ASSET-01 — Penyusutan yang gagal mengunci periode sehingga retry tidak memperbaiki aset

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Keuangan → Aset Tetap → jalankan penyusutan.

**Rantai kejadian:** Klaim periode → posting jurnal gagal → klaim tertinggal → retry skip → akumulasi/entri tetap0.

**Letak kesalahan dan penyebab:** Periode dimasukkan ke depreciation_periods sebelum jurnal dan register penyusutan selesai. Kegagalan tidak melepas klaim atau menyediakan status saga yang dapat dilanjutkan.

**Dampak, hasil reproduksi, dan batas klaim:** Fault satu kali hanya pada batas post_depreciation: public run500. Setelah batas normal dipulihkan, public retry200 tetapi posted0, accumulated0 dan tidak ada entri untuk periode itu. Kontrol proses normal memposting100 dan retry periode yang sudah selesai tidak menggandakan jurnal.

**Lokasi source pada commit audit:**

- [backend/services/fixed_asset_service.py:244](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L244) — `"depreciation_periods": {"$ne": period}`.
- [backend/services/fixed_asset_service.py:256](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L256) — `je = await gl_service.post_depreciation(`.
- [backend/services/gl_service.py:2286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2286) — `async def post_depreciation(`.

```python
242:         won = await db.fin_fixed_assets.find_one_and_update(
243:             {"id": a["id"], "status": a.get("status", "active"),
244:              "depreciation_periods": {"$ne": period}},
245:             {"$addToSet": {"depreciation_periods": period}},
246:             projection={"_id": 0, "id": 1})
247:         if not won:
248:             skipped += 1
249:             continue
250:         monthly = _monthly_amount(cost, salvage, life)
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Buat operasi penyusutan dapat dipulihkan: preflight, operation ID per aset/periode, status started/GL posted/register applied/completed, dan resume yang idempoten. Jangan melepas klaim secara buta setelah jurnal mungkin terbentuk; bedakan kegagalan sebelum dan sesudah side effect.

**Kriteria penerimaan untuk reviewer:**

Fault sebelum posting, sesudah journal tersimpan, sebelum register, sebelum finalize: retry menghasilkan tepat1 jurnal+1 entri dan akumulasi100. Uji restart/timeout, periode tertutup, akun invalid, single-asset dan batch, duplicate same-period concurrency.

## D4-ASSET-02 — Penyusutan dua periode bersamaan membuat register aset tertinggal dari jurnal

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Keuangan → Aset Tetap → register, nilai buku dan penyusutan.

**Rantai kejadian:** Dua periode membaca acc0 → keduanya klaim periode berbeda → dua entri100 → keduanya set acc100.

**Letak kesalahan dan penyebab:** CAS hanya melindungi period key masing-masing. Perhitungan akumulasi dan bulan memakai snapshot yang dibaca sebelum klaim, lalu disimpan dengan $set, sehingga update lintas periode dapat saling menimpa.

**Dampak, hasil reproduksi, dan batas klaim:** Aset300/life3: dua public run periode Jan dan Feb dengan barrier di batas jurnal menghasilkan2 entri penyusutan. Register menunjukkan accumulated100/book200/months1, seharusnya accumulated200/book100/months2. Kontrol run normal dan duplicate same-period tetap benar. Barrier menyinkronkan urutan; perhitungan asli tidak diganti.

**Lokasi source pada commit audit:**

- [backend/services/fixed_asset_service.py:261](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L261) — `new_acc = round(acc + amt, 2)`.
- [backend/services/fixed_asset_service.py:262](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L262) — `new_months = int(a.get("depreciated_months", 0)) + 1`.
- [backend/services/fixed_asset_service.py:274](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L274) — `"accumulated_depreciation": new_acc`.

```python
259:             dep_exp_acc=a.get("gl_account_dep_exp", gl_service.ACC_DEP_EXPENSE),
260:             acc_dep_acc=a.get("gl_account_acc_dep", gl_service.ACC_FA_ACCUM_DEP))
261:         new_acc = round(acc + amt, 2)
262:         new_months = int(a.get("depreciated_months", 0)) + 1
263:         new_book = round(cost - new_acc, 2)
264:         status = "fully_depreciated" if (new_acc >= depreciable - EPS or new_months >= life) else "active"
265:         await db.fin_depreciation_entries.insert_one({
266:             "id": new_id("depe"),
267:             "asset_id": a["id"], "asset_number": a.get("number", ""),
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Serialisasikan mutasi per aset atau gunakan update atomik/optimistic version dengan resume idempoten per periode. Hindari snapshot stale; batas depreciable amount/salvage/life harus berlaku terhadap akumulasi final setelah semua operasi, termasuk disposal/capitalization.

**Kriteria penerimaan untuk reviewer:**

Jan/Feb concurrent:2 entri, akumulasi200, nilai buku100 dan2 bulan; GL-register-detail-summary harus merekonsiliasi. Uji last-month concurrent, salvage, disposal vs depreciation, amendment vs run, same-period retries dan interrupted batch.

## D4-ICLOAN-01 — Akun Finance dapat mengubah pinjaman entitas yang tidak ditugaskan kepadanya

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Keuangan → Antar Entitas → Pinjaman Uang; API repay/cancel.

**Rantai kejadian:** Finance hanyaA → detail pinjamanB/C ditolak → repayB/C diterima → kedua sisi kas dan saldo berubah.

**Letak kesalahan dan penyebab:** Mutating handlers memeriksa izin fitur tetapi tidak memagari dokumen pinjaman memakai konteks entitas. Layanan mengambil loan berdasarkan ID, tanpa verifikasi bahwa pihak transaksi berada dalam penugasan actor.

**Dampak, hasil reproduksi, dan batas klaim:** Akun Finance allowed_entity_ids=[A]: GET loan B/C404 sebagai kontrol. Public repay10 pada loan50 memberi200, outstanding40 dan2 transaksi kas baru. Public cancel draftB/C juga200. Akun manager tidak dipakai sebagai bukti bypass karena role itu memang diizinkan lintas entitas oleh desain sistem; hipotesis awal manager ditarik.

**Lokasi source pada commit audit:**

- [backend/routers/interco_loans.py:96](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L96) — `async def repay_loan(`.
- [backend/routers/interco_loans.py:71](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L71) — `async def get_loan(`.
- [backend/routers/interco_loans.py:109](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L109) — `async def cancel_loan(`.
- [backend/services/interco_loan_service.py:200](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/interco_loan_service.py#L200) — `async def repay(`.

```python
94: 
95: @router.post("/interco/loans/{loan_id}/repay")
96: async def repay_loan(loan_id: str, payload: IntercoLoanRepay, request: Request) -> Dict[str, Any]:
97:     actor = await require_permission(request, "interco", "settle")
98:     try:
99:         res = await svc.repay(loan_id, actor, float(payload.amount or 0), payload.note)
100:     except (svc.LoanError, money.IntercoMoneyError) as exc:
101:         raise _fail(exc) from exc
102:     await audit(actor.get("name", ""), "interco_loan_repaid", "interco_loan",
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Terapkan aturan akses yang sama untuk pasangan lender/borrower pada seluruh mutasi dan layer layanan bila dipanggil lewat jalur lain. Gunakan resolver dokumen/policy yang konsisten dengan GET dan penugasan, tanpa memblokir role lintas entitas yang sah. Audit disburse, repay, cancel, list/detail dan side effects.

**Kriteria penerimaan untuk reviewer:**

Finance hanyaA tidak dapat repay/cancel/disburse loanB/C; tidak ada perubahan saldo/kas/jurnal/timeline ketika ditolak. Lender/borrower yang sah dan manager/admin lintas entitas tetap bekerja; uji akses melalui kedua paired IDs, closed entity dan concurrency.

## D4-RFQ-01 — Award RFQ tetap membuat PO untuk item yang dinyatakan tidak tersedia

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Pembelian → RFQ → perbandingan supplier → Award & Buat PO.

**Rantai kejadian:** Quote availableFalse/price20 → compare tidak lengkap → full award hanya membaca harga → PO dibuat.

**Letak kesalahan dan penyebab:** Perbandingan dan supplier_total menolak baris unavailable, tetapi pemilihan harga award mengabaikan flag available. Sisa harga lama yang positif menjadi dasar PO walaupun supplier menyatakan tidak dapat memasok.

**Dampak, hasil reproduksi, dan batas klaim:** Public quote dua baris: L1 availableTrue/price10, L2 availableFalse/price20. Public compare completeFalse sebagai kontrol. Public award full tetap200 dan membuat1 PO yang mencakup L2. Kontrol quote kedua baris availableTrue memberi full PO50 dan split termurah menghasilkan2 PO total46. UI saat ini membentuk available dari harga; skenario flagFalse dengan retained price terutama kontrak API/data, bukan klaim pengguna UI dapat mengetik kombinasi itu.

**Lokasi source pada commit audit:**

- [backend/services/rfq_service.py:296](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfq_service.py#L296) — `def _price_of(sid: str, lid: str)`.
- [backend/services/rfq_service.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfq_service.py#L90) — `if ln.get("available", True) and float(ln.get("price", 0) or 0) > 0:`.
- [backend/routers/rfq.py:184](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L184) — `async def award(`.
- [frontend/src/features/purchasing/RFQDetailPanel.jsx:77](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/purchasing/RFQDetailPanel.jsx#L77) — `async function doAward()`.

```python
294:     grouped: Dict[str, List[Dict[str, Any]]] = {}
295: 
296:     def _price_of(sid: str, lid: str) -> float:
297:         s = sup_by_id.get(sid, {})
298:         for ln in s.get("lines", []):
299:             if ln["line_id"] == lid:
300:                 return float(ln.get("price", 0) or 0)
301:         return 0.0
302: 
```

**Bukti asli:** [evidence/repro/procurement-lifecycle90-results.json](evidence/repro/procurement-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| rfq.full_unavailable_rejected | 400 | 200 | observed_difference |
| rfq.full_unavailable_no_po | 0 | 1 | observed_difference |
| rfq.foreign_compare_denied | true | false | observed_difference |
| rfq.foreign_cancel_denied | true | false | observed_difference |
| rfq.foreign_state_preserved | "draft" | "cancelled" | observed_difference |

**Prompt agent development:**

Gunakan satu resolusi kelayakan quote untuk compare, rekomendasi dan award. Supplier/baris harus quoted, availableTrue dan harga valid. Cek validitas quote/masa berlaku serta duplicate line; line override harga tidak boleh memulihkan availability tanpa keputusan eksplisit yang tercatat.

**Kriteria penerimaan untuk reviewer:**

Full/line award atas unavailable ditolak sebelum PO/price-list/PR berubah; status RFQ dan saga tetap dapat diperbaiki. Quote valid full50/split46 tetap lolos. Uji harga lama positif, unavailable0, missing quote, expiry, override, duplicate quote lines dan multi-supplier partial failure.

## D4-RFQ-02 — Perbandingan dan pembatalan RFQ tidak mengikuti pembatasan entitas pada halaman detail

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Pembelian → RFQ → perbandingan harga dan aksi status.

**Rantai kejadian:** Finance hanyaKSC → detail RFQ entitaslain404 → compare200 → cancel200 dan status cancelled.

**Letak kesalahan dan penyebab:** GET detail memanggil entity_ctx/assert_entity_access. Compare dan beberapa mutasi langsung _get(id) setelah izin fitur, sehingga aturan penugasan dokumen tidak diterapkan konsisten.

**Dampak, hasil reproduksi, dan batas klaim:** Akun Finance ditugaskan hanya ent_ksc. RFQ fixture yang awalnya lahir dari producer publik diberi owner entitaslain yang memang ada. Detail ditolak403/404, tetapi compare diterima dan cancel200 mengubah draft menjadi cancelled. Izin fitur sengaja diberikan lewat matriks; role lintas entitas tidak dipakai untuk membuktikan penolakan.

**Lokasi source pada commit audit:**

- [backend/routers/rfq.py:56](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L56) — `return build_compare(await _get(rfq_id))`.
- [backend/routers/rfq.py:49](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L49) — `assert_entity_access(rfq, "rfqs", ctx)`.
- [backend/routers/rfq.py:205](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L205) — `async def cancel_rfq(`.
- [backend/routers/rfq.py:135](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L135) — `async def send_rfq(`.

```python
54: async def compare_rfq(rfq_id: str, request: Request) -> Dict[str, Any]:
55:     await require_permission(request, "rfq", "view")
56:     return build_compare(await _get(rfq_id))
57: 
58: 
59: @router.post("/rfqs")
60: async def create_rfq(payload: RFQCreate, request: Request) -> Dict[str, Any]:
61:     """Buat RFQ dari PR approved (tarik item) atau standalone manual."""
62:     actor = await require_permission(request, "rfq", "create")
```

**Bukti asli:** [evidence/repro/procurement-lifecycle90-results.json](evidence/repro/procurement-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| rfq.foreign_detail_denied_control | true | true | pass |
| rfq.foreign_compare_denied | true | false | observed_difference |
| rfq.foreign_cancel_denied | true | false | observed_difference |
| rfq.foreign_state_preserved | "draft" | "cancelled" | observed_difference |

**Prompt agent development:**

Gunakan _get_scoped atau guard bersama pada compare/send/quote/award/cancel serta validasi entitas saat create dari PR. Verifikasi scope sebelum state/price-list/PO/PR/saga/timeline berubah. Pertahankan akses role lintas entitas yang sah dan penugasan MD multi-entitas.

**Kriteria penerimaan untuk reviewer:**

Detail/compare dan semua mutasi harus menolak actor di luar penugasan; status dan seluruh side effects tidak berubah. Positive control entitas milik actor tetap berfungsi. Uji foreign PR→RFQ, explicit entity_id, supplier entity sharing, line scope dan kedua policy aktor multi-entitas/lintas entitas.

## D4-CB-01 — Pemeriksa kontrabon dapat memberi hasil bersih karena hanya memeriksa 2.000 dokumen pertama

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_scanner_or_migration_with_explicit_legacy_fixture`.

**Layar/alur:** Gate integritas kontrabon; cakupan validasi produksi/data lama.

**Rantai kejadian:** 2.000 kontrabon tanpa pelanggaran → dua kontrabon terakhir memakai bill sama → detector menghasilkan0 pelanggaran.

**Letak kesalahan dan penyebab:** Cursor dibatasi to_list(2000) tanpa pemeriksaan total/paginasi; dokumen di luar jendela tidak dievaluasi.

**Dampak, hasil reproduksi, dan batas klaim:** Fixture sengaja dibuat korup untuk menguji pemeriksa, bukan membuktikan producer publik dapat membuat kontrabon ganda. Pada dataset kecil duplicate aktif terdeteksi; cancelled dikecualikan. Pada2.002 live records, duplicate bill di tail terlewat dan detector memberi0.

**Lokasi source pada commit audit:**

- [backend/services/contra_bon_scan.py:24](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contra_bon_scan.py#L24) — `return await db[COLL].find(`.
- [backend/services/contra_bon_scan.py:29](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contra_bon_scan.py#L29) — `async def bills_in_multiple_contra_bons`.
- [scripts/verify_data_integrity.py:3642](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/scripts/verify_data_integrity.py#L3642) — `async def layer_contra_bon_invariants`.

```python
22: async def _live_contra_bons() -> List[Dict[str, Any]]:
23:     """Kontrabon yang masih 'memegang' dokumen (semua kecuali `cancelled`)."""
24:     return await db[COLL].find(
25:         {"status": {"$in": list(svc.HOLDING_STATUSES)}}, {"_id": 0}).to_list(2000)
26: 
27: 
28: # ── INV-CB-01 ────────────────────────────────────────────────────────────────
29: async def bills_in_multiple_contra_bons() -> List[Dict[str, Any]]:
30:     """Satu faktur supplier tidak boleh berada di dua kontrabon yang belum dibatalkan.
```

**Bukti asli:** [evidence/repro/contra-bon-invariants90-results.json](evidence/repro/contra-bon-invariants90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| contra.scale_duplicate_2002 | 1 | 0 | observed_difference |

**Prompt agent development:**

Iterasi seluruh cursor/aggregation atau pagination stabil; jika harus membatasi, tampilkan incomplete dan jangan meluluskan gate. Terapkan pada seluruh detector yang memakai _live_contra_bons, serta batas lain yang belum dibuktikan.

**Kriteria penerimaan untuk reviewer:**

Duplicate yang berada pada awal/tengah/akhir dari >2.000 data harus terdeteksi. Fixture valid tidak memberi false positive, cancelled dikecualikan. Laporkan scanned/total dan pastikan incomplete tidak boleh berstatus hijau.

## D4-UOM-BF-01 — Backfill jumlah roll memakai panjang daftar ID mentah, berbeda dari resolver roll nyata

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_scanner_or_migration_with_explicit_legacy_fixture`.

**Layar/alur:** Migrasi dua satuan → dokumen retur/transfer/SJ lama → kolom jumlah roll.

**Rantai kejadian:** roll_ids R1,R1,MISSING → helper actual-roll1 → backfill qty_rolls3.

**Letak kesalahan dan penyebab:** Backfill menganggap setiap elemen daftar mewakili satu roll, tanpa deduplikasi/verifikasi, sedangkan rolls_of_ids memakai count_documents atas ID nyata.

**Dampak, hasil reproduksi, dan batas klaim:** Terbukti pada fixture data lama yang sengaja memiliki referensi duplikat/hilang; tidak ada klaim producer normal menghasilkan referensi tersebut. Ini kegagalan alat pemulihan data untuk mendeteksi/menandai data lama tidak valid; hasil3 dapat terlihat sebagai angka roll pasti.

**Lokasi source pada commit audit:**

- [backend/services/dual_qty_service.py:169](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/dual_qty_service.py#L169) — `async def backfill(`.
- [backend/services/dual_qty_service.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/dual_qty_service.py#L129) — `async def rolls_of_ids`.
- [scripts/migrate_qty_rolls.py:54](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/scripts/migrate_qty_rolls.py#L54) — `backfill`.

```python
167: 
168: 
169: async def backfill(dbx, *, demo_plan: bool = False, dry_run: bool = False) -> Dict[str, int]:
170:     """Isi `qty_rolls` (dan `secondary_measures`) DARI ROLL NYATA — bukan menebak.
171: 
172:     Aturan (dan alasan tiap aturan):
173:       * `inventory_movements` : baris yang menunjuk satu `roll_id` = **1 roll**.
174:       * `wms_tasks`           : jumlah roll yang lahir dari tugas itu (`grn_task_id`).
175:       * `purchase_orders`     : `items[].received_rolls` = roll nyata ber-`po_id` + produk.
```

**Bukti asli:** [evidence/repro/quantity-provenance90-results.json](evidence/repro/quantity-provenance90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| backfill.dry_run_has_no_write | false | false | pass |
| backfill.dry_run_matches_write_counts | {"inventory_movements": 1, "wms_tasks": 1, "purchase_orders": 1, "sales_returns": 1, "purchase_returns": 1, "interco_returns": 1, "warehouse_transfers": 1, "shipments": 1, "makloon_orders": 1, "inventory_rolls": 1} | {"inventory_movements": 1, "wms_tasks": 1, "purchase_orders": 1, "sales_returns": 1, "purchase_returns": 1, "interco_returns": 1, "warehouse_transfers": 1, "shipments": 1, "makloon_orders": 1, "inventory_rolls": 1} | pass |
| backfill.movement_is_single_roll | 1 | 1 | pass |
| backfill.task_real_count | 2 | 2 | pass |
| backfill.received_real_count | 2 | 2 | pass |
| backfill.production_plan_not_guessed | false | false | pass |
| backfill.actual_weight | 12.346 | 12.346 | pass |
| backfill.preserve_existing_count | 7 | 7 | pass |
| backfill.no_rolls_no_task_guess | false | false | pass |
| backfill.shipment_actual_rolls | 2 | 2 | pass |

**Prompt agent development:**

Satukan derivasi jumlah roll dan aturan ID unik. Untuk referensi hilang/arsip yang tidak bisa dibuktikan, jangan menebak: laporkan conflict/incomplete dan butuh keputusan. Jangan mengganti jumlah historis sah tanpa bukti rekonsiliasi.

**Kriteria penerimaan untuk reviewer:**

Dry-run tidak menulis; duplikat tidak dihitung dua kali; dangling/archived references dilaporkan jelas. Dokumen historis valid tetap benar; migration berulang idempoten, qty_rolls yang sudah diketahui tidak ditimpa.

## D4-RET-CHAIN-01 — Ringkasan fisik rantai retur menjumlahkan barang berlainan satuan menjadi satu angka

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Retur → perjalanan barang → posisi barang yang masih ditahan.

**Rantai kejadian:** Owner sama:100yard kain +5kg barang lain → satu langkah held berlabel105yard.

**Letak kesalahan dan penyebab:** Bucket hanya berdasarkan pemilik dan memakai satuan dari roll pertama, kemudian menjumlahkan length_remaining tanpa pemisahan satuan.

**Dampak, hasil reproduksi, dan batas klaim:** Pada fixture linked-roll dua produk, ringkasan satu owner menunjukkan105yard; tidak dapat ditafsirkan sebagai panjang fisik. Source records100yard dan5kg tidak berubah. Kontrol rantai sama satuan dan redaksi lintas entitas lulus; browser/hardware tidak dibuktikan oleh probe ini.

**Lokasi source pada commit audit:**

- [backend/services/return_chain_service.py:223](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_chain_service.py#L223) — `held.setdefault(`.
- [backend/services/return_chain_service.py:224](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_chain_service.py#L224) — `row["qty"]`.
- [backend/services/return_chain_service.py:159](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_chain_service.py#L159) — `"unit"`.

```python
221:             continue
222:         own = r.get("owner_entity_id", "")
223:         row = held.setdefault(own, {"qty": 0.0, "rolls": 0, "unit": r.get("unit", "")})
224:         row["qty"] = round(row["qty"] + float(r.get("length_remaining") or 0), 2)
225:         row["rolls"] += 1
226:     for own, row in held.items():
227:         if row["qty"] <= 0.01:
228:             continue
229:         steps.append({
```

**Bukti asli:** [evidence/repro/quantity-provenance90-results.json](evidence/repro/quantity-provenance90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| chain.no_document | false | false | pass |
| chain.full_stages | ["sales_return", "interco_return", "purchase_return", "kept", "kept"] | ["sales_return", "interco_return", "purchase_return", "kept", "kept"] | pass |
| chain.full_root | 150 | 150 | pass |
| chain.complete_route | true | true | pass |
| chain.resolve_from_purchase | "SR1" | "SR1" | pass |
| chain.resolve_from_interco | "SR1" | "SR1" | pass |
| chain.foreign_amount_hidden | null | null | pass |
| chain.foreign_supplier_hidden | false | false | pass |
| chain.foreign_po_hidden | false | false | pass |
| chain.foreign_lot_hidden | "" | "" | pass |

**Prompt agent development:**

Pisahkan agregasi berdasarkan pemilik+satuan, dan produk bila konteks tampilan memerlukannya. Konversi hanya lewat UoM yang sah dengan jejak; jangan menjumlahkan kg dan yard. Lengkapi struktur response agar UI menampilkan setiap kelompok tanpa parsing teks.

**Kriteria penerimaan untuk reviewer:**

100yard +5kg harus tampil sebagai100yard dan5kg. Same-unit sums tetap benar, redaksi informasi entitas lain tetap bekerja, rollcount dan complete-chain memakai definisi yang konsisten.

## D4-ALERT-DATE-01 — Peringatan AP menyebut jatuh tempo hari ini sudah terlambat satu hari

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Scheduler → notifikasi tagihan supplier jatuh tempo.

**Rantai kejadian:** bill_date tanggal kalender +NET30 =hari ini00:00UTC → now siang → timedelta.days=-1 → critical LEWAT1hari.

**Letak kesalahan dan penyebab:** Selisih datetime dibulatkan ke bawah oleh .days, sementara jatuh tempo dokumen merupakan tanggal kalender.

**Dampak, hasil reproduksi, dan batas klaim:** Public source fields valid berupa tanggal YYYY-MM-DD. Original alert generator memberi critical/LEWAT1hari pada due-date yang sama dengan hari pengujian. Kontrol tanggal3hari mendatang/3hari lewat dan tagihan paid/draft lulus.

**Lokasi source pada commit audit:**

- [backend/services/alert_service.py:144](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L144) — `left = (due - now).days`.
- [backend/services/alert_service.py:120](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L120) — `async def job_ap_due`.
- [backend/services/alert_service.py:150](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L150) — `overdue = left < 0`.

```python
142:         days = tmaps[ent].get(sup_term.get(b.get("supplier_id", ""), ""), 0)
143:         due = bd + timedelta(days=days)
144:         left = (due - now).days
145:         if left > AP_DUE_SOON_DAYS:
146:             continue
147:         scanned += 1
148:         if scanned > MAX_ALERTS_PER_JOB:
149:             break
150:         overdue = left < 0
```

**Bukti asli:** [evidence/repro/alert-numeric90-results.json](evidence/repro/alert-numeric90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| alerts.ap_due_calendar_today | true | false | observed_difference |
| alerts.ap_today_not_overdue | "warning" | "critical" | observed_difference |

**Prompt agent development:**

Gunakan definisi hari dan zona waktu bisnis yang konsisten untuk tanggal dokumen, bukan usia24jam yang dibulatkan ke bawah. Pusatkan due-date/day-delta untuk AP board, aging dan scheduler.

**Kriteria penerimaan untuk reviewer:**

Jatuh tempo hari ini =HARI INI/warning/0hari; besok=1; kemarin=1hari terlambat. Uji UTC vs zona waktu bisnis, cutoff malam, term override perentitas dan tahun kabisat.

## D4-ALERT-AMT-01 — Peringatan utang menampilkan nominal penuh meskipun pembayaran sebagian sudah tercatat

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Pembayaran supplier → saldo AP → notifikasi jatuh tempo.

**Rantai kejadian:** Tagihan100, amount_paid70, statusposted → peringatan jatuh tempo tetap menampilkan100.

**Letak kesalahan dan penyebab:** Query tidak membawa amount_paid/remaining, kemudian isi peringatan memakai grand_total tanpa menghitung saldo.

**Dampak, hasil reproduksi, dan batas klaim:** Original alert body memakai100 pada partial-payment fixture70; saldo yang perlu ditagih/dibayar30. Statuspaid dikecualikan dengan benar sebagai kontrol. Jika nominal dokumen sengaja ditampilkan, ia harus diberi label dan saldo30 tetap jelas, bukan memberi kesan100 perlu dibayar.

**Lokasi source pada commit audit:**

- [backend/services/alert_service.py:124](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L124) — `"supplier_id": 1, "supplier_name": 1, "entity_id": 1`.
- [backend/services/alert_service.py:157](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L157) — `_rp(b.get('grand_total'))`.
- [backend/routers/vendor_bills.py:97](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/vendor_bills.py#L97) — `"amount_paid"`.

```python
122:         {"status": "posted"},
123:         {"_id": 0, "id": 1, "bill_number": 1, "bill_date": 1, "grand_total": 1,
124:          "supplier_id": 1, "supplier_name": 1, "entity_id": 1}).to_list(5000)
125:     if not bills:
126:         return {"created": 0, "scanned": 0, "detail": "tidak ada tagihan supplier terposting"}
127:     sup_ids = [b.get("supplier_id") for b in bills if b.get("supplier_id")]
128:     sups = await db.suppliers.find(
129:         {"id": {"$in": sup_ids}}, {"_id": 0, "id": 1, "payment_term_code": 1}).to_list(2000)
130:     sup_term = {s["id"]: s.get("payment_term_code", "") for s in sups}
```

**Bukti asli:** [evidence/repro/alert-numeric90-results.json](evidence/repro/alert-numeric90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| alerts.ap_partial_reports_outstanding | true | false | observed_difference |

**Prompt agent development:**

Ambil outstanding dari SSOT yang sama dengan AP aging/pembayaran/kontrabon. Jika tampilkan gross, paid, deduction dan balance, labeli masing-masing. Jangan menghitung ulang dari payments yang voided tanpa aturan yang sama.

**Kriteria penerimaan untuk reviewer:**

100-70 → saldo30 pada peringatan; full payment tidak membuat peringatan; void/payment reversal/deductions/makloon claims dan term override harus konsisten dengan AP ledger.

## D4-ALERT-WMS-01 — Notifikasi tugas WMS mencampur pesanan dua entitas yang memakai gudang sama

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** WMS multi-entitas/shared warehouse → scheduler ops_stalled → bell gudang.

**Rantai kejadian:** SO-A ownerKSC +SO-B ownerlain, warehouse/flow sama → satu bucket entityKSC berisi2 tugas dan nomorSO-B.

**Letak kesalahan dan penyebab:** Pengelompokan tidak memasukkan entity_id. Entitas bucket ditetapkan dari tugas pertama, sedangkan hitungan dan daftar order mencakup pemilik lain.

**Dampak, hasil reproduksi, dan batas klaim:** Pada dua business_entities yang nyata di fixture, original generator membuat satu notifikasi entitas pertama, memuat nomor pesanan kedua; owner kedua tidak mendapat kelompoknya sendiri. Ini selain salah hitung juga mengaburkan batas tugas entitas. Kontrol dua flow milik satu entitas menghasilkan dua kelompok dengan dedupe harian.

**Lokasi source pada commit audit:**

- [backend/services/alert_service.py:286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L286) — `key = (t.get("warehouse_id", ""), t.get("flow_type", ""))`.
- [backend/services/alert_service.py:302](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L302) — `ref=f"task_stalled:{wid}:{flow}"`.
- [backend/services/alert_service.py:289](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L289) — `"entity_id": t.get("entity_id")`.

```python
284:     groups: Dict[tuple, Dict[str, Any]] = {}
285:     for t in tasks:
286:         key = (t.get("warehouse_id", ""), t.get("flow_type", ""))
287:         g = groups.setdefault(key, {"count": 0, "oldest": None, "orders": [],
288:                                     "warehouse_name": t.get("warehouse_name", ""),
289:                                     "entity_id": t.get("entity_id")})
290:         g["count"] += 1
291:         dt = _parse(t.get("created_at"))
292:         if dt and (g["oldest"] is None or dt < g["oldest"]):
```

**Bukti asli:** [evidence/repro/alert-numeric90-results.json](evidence/repro/alert-numeric90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| alerts.ops_shared_warehouse_separate_owners | 2 | 1 | observed_difference |
| alerts.ops_foreign_order_not_in_owner_notice | false | true | observed_difference |

**Prompt agent development:**

Kelompokkan berdasarkan entity_id+warehouse_id+flow dan masukkan entity pada ref/dedupe. Pertahankan gudang bersama, tentukan audience sesuai penugasan pengguna dan line/warehouse role; jangan mengandalkan nama gudang sebagai pemilik.

**Kriteria penerimaan untuk reviewer:**

Dua owner satu gudang menghasilkan notifikasi masing-masing dengan count/order sendiri. Actor entitasA tidak memperoleh nomorSO-B dari notifikasiA. User multi-entitas/lintas-entitas sah tetap dapat melihat kelompok yang diizinkan; rerun harian tidak duplikat.

## D4-PRICE-SCOPE-01 — Scope harga khusus berbeda antara detail, perubahan, harga efektif dan ringkasan

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Persetujuan Harga Khusus → daftar, statistik, detail dan keputusan.

**Rantai kejadian:** Sales dengan kemampuan custom hanyaA → detailB ditolak → patch/submit/approve/deleteB diterima; stats/effective juga membacaB.

**Letak kesalahan dan penyebab:** Sebagian handler hanya memeriksa permission dan requested_by. entity_ctx/assert_entity_access yang dipakai GET detail tidak diterapkan pada mutasi/resolver/statistik.

**Dampak, hasil reproduksi, dan batas klaim:** Original ASGI: user Sales onlyA diberi capability yang diuji. Create asing ditolak sebagai kontrol; foreign fixtureB ownerU disiapkan eksplisit. GET B ditolak, listA benar, tetapi PATCH/SUBMIT/DELETEB200; distinct approver onlyA menyetujuiB200; effectiveB mengembalikan hargaB dan statsA menghitung2 alih-alih1. Manager/admin cross-entity tidak dipakai sebagai bypass.

**Lokasi source pada commit audit:**

- [backend/routers/price_approvals.py:263](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L263) — `async def patch_price_approval(`.
- [backend/routers/price_approvals.py:182](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L182) — `async def price_approval_stats`.
- [backend/routers/price_approvals.py:157](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L157) — `async def effective_price`.
- [backend/routers/price_approvals.py:257](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L257) — `assert_entity_access(doc, "price_approvals", ctx)`.
- [backend/routers/price_approvals.py:331](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L331) — `async def approve_price_approval`.

```python
261: 
262: @router.patch("/price-approvals/{approval_id}")
263: async def patch_price_approval(approval_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
264:     user = await require_permission(request, "price_approval", "update")
265:     doc = await _get_or_404(approval_id)
266:     _ensure_owner_or_privileged(doc, user)
267:     if doc["status"] not in EDITABLE_STATUSES:
268:         raise HTTPException(status_code=409, detail=f"Pengajuan status '{doc['status']}' tidak dapat diubah")
269:     allowed = {"requested_price", "min_quantity", "reason", "valid_until"}
```

**Bukti asli:** [evidence/repro/price-approval-scope90-results.json](evidence/repro/price-approval-scope90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| price.foreign_create_rejected | true | true | pass |
| price.foreign_get_control | true | true | pass |
| price.stats_scope | 1 | 2 | observed_difference |
| price.foreign_patch_rejected | true | false | observed_difference |
| price.foreign_submit_rejected | true | false | observed_difference |
| price.foreign_approve_rejected | true | false | observed_difference |
| price.foreign_effective_hidden | false | true | observed_difference |
| price.foreign_delete_rejected | true | false | observed_difference |

**Prompt agent development:**

Pusatkan scoped document resolver, terapkan sebelum setiap read/mutation/attachment/status effect dan supersede. Effective/stats harus mengikuti active/allowed entity scope; permission fitur bukan izin semua dokumen. Pertahankan custom capabilities sah, SOD dan role cross-entity.

**Kriteria penerimaan untuk reviewer:**

Detail/list/effective/stats/mutasi sepakat pada scope; ditolak tanpa perubahan harga,status,customer-price,SO,supersede,notifikasi atau file. Own-entity lifecycle draft→evidence→submit→distinct approval→effective tetap lulus, minqty4/5 dan approved edit/delete guards tetap benar.

## D4-OD-LOCK-01 — Kegagalan pembaruan SKU meninggalkan harga OD terkunci dan pengulangan tidak dapat memulihkannya

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Pesanan Khusus → keputusan pelanggan → kunci harga final → katalog SKU.

**Rantai kejadian:** Customer ACC → lockprice commitOD130 → DBwrite SKU gagal → SKU100 → retry sudahterkunci.

**Letak kesalahan dan penyebab:** Harga OD dan akhir claim dicatat sebelum pembaruan produk. Kegagalan di write produk tidak ditangani dengan resume/rollback; pengecekan awal locked menolak retry.

**Dampak, hasil reproduksi, dan batas klaim:** Fault hanya di boundary database products.update_one, bisnis asli tidak diganti. PersistedOD price_locked=True/final130, SKUprice100; retry gagal already-locked. Kontrol normal lock menghasilkanOD1300/SKU130, dan unlock memerlukanadmin+reason serta menolak bila PR/PO/SO sudah lahir. Pemulihan manual lewat unlock dapat diperlukan; bukan klaim tidak mungkin dipulihkan sama sekali.

**Lokasi source pada commit audit:**

- [backend/services/special_order_phase2.py:235](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L235) — `_saga.finish_set({"pricing": pricing`.
- [backend/services/special_order_phase2.py:244](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L244) — `await db.products.update_one({"id": pid_final}`.
- [backend/services/special_order_phase2.py:216](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L216) — `Harga OD ini sudah dikunci.`.

```python
233:                       precondition={"price_locked": {"$ne": True}}, actor=actor.get("name", ""))
234:     _res = await db.special_orders.update_one({"id": od["id"], "price_locked": {"$ne": True}}, {
235:         **_saga.finish_set({"pricing": pricing, "final_price": pricing["final_unit_price"], "total_amount": pricing["total"],
236:                  "price_locked": True, "updated_at": now_iso(),
237:                  **({"linked_product_id": pv["product_id"], "linked_product_sku": pv["product_sku"]} if pv["product_id"] else {})}),
238:         "$push": {"status_history": {"status": od.get("status"), "timestamp": now_iso(), "user": actor.get("email", ""),
239:                                      "note": f"Harga final dikunci: {rupiah(pricing['final_unit_price'])}/{pricing['unit']} (kontrak {rupiah(pricing['cost_price'])} + margin {pricing['margin_pct']:g}%)"}}})
240:     if _res.matched_count == 0:
241:         raise ODError("Harga OD ini baru saja dikunci oleh pihak lain. Muat ulang.")
```

**Bukti asli:** [evidence/repro/special-order-chain90-results.json](evidence/repro/special-order-chain90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| od.latest_revision_blocks_old_winner | false | false | pass |
| od.decision_guard_locked | true | true | pass |
| od.lock_needs_acc | true | true | pass |
| od.lock_needs_winning_contract | true | true | pass |
| od.lock_total | 1300 | 1300.0 | pass |
| od.lock_sku_price | 130 | 130.0 | pass |
| od.lock_repeat_guard | true | true | pass |
| od.locked_preview_snapshot | 1300 | 1300.0 | pass |
| od.unlock_requires_admin | true | true | pass |
| od.unlock_requires_reason | true | true | pass |

**Prompt agent development:**

Gunakan saga/checkpoint yang selesai hanya setelah semua effect harga/SKU tersimpan, atau transaksi dengan recovery yang jelas. Retry harus mengenali partial commit dan menyelesaikannya sekali tanpa duplicateprocurement. Jangan mengubah snapshot dokumen historis melalui repairmassal.

**Kriteria penerimaan untuk reviewer:**

Fault sebelum/sesudah OD commit, SKUwrite dan autoPO: state konsisten atau pending dan dapat dipulihkan. Retry tidak ditolak ketika pekerjaan belum selesai; harga akhir OD/SKU/PR/PO konsisten, idempotent dan SOD/lock rules tetap berlaku.

## D4-COMM-BOUNDS-01 — Perubahan master komersial melewati batas angka dan dapat menghasilkan ongkos makloon negatif

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Barang Supplier dan Kontrak Supplier → perubahan data → simulasi tarif makloon.

**Rantai kejadian:** Create menolak tarif -5 → PATCH menerimanya → tariff-preview qty 10 menghasilkanamount -50; barang supplier PATCH harga/MOQ/lead negatifjuga diterima.

**Letak kesalahan dan penyebab:** Create schemas menetapkan ge/le, Patch optional types tidak mempertahankannya. Service patch tidak mengulangi validasi domain numerik; kalkulator menggunakan nilai tersimpan.

**Dampak, hasil reproduksi, dan batas klaim:** Original API kontrol create negative/percentage 101 → 422 dan normal create200. PATCH contract menerima tarif/mincharge/yield/MOQ/leadnegative serta shrinkage/tolerance/byproduct101. Tarif negatif memberi pratinjauamount -50. SupplierItem PATCH menerima harga/MOQ/lead-1 walaupun create menolak422 dan CSVharga-1 dinyatakaninvalid. Tidak ada klaim jurnal negatif sudah terposting dari kasus ini.

**Lokasi source pada commit audit:**

- [backend/schemas_contracts.py:62](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_contracts.py#L62) — `class SupplierContractPatch`.
- [backend/schemas_contracts.py:28](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_contracts.py#L28) — `class SupplierContractCreate`.
- [backend/schemas_supplier_items.py:41](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_supplier_items.py#L41) — `class SupplierItemPatch`.
- [backend/services/contract_service.py:246](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contract_service.py#L246) — `async def patch_contract`.
- [backend/services/supplier_item_service.py:232](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/supplier_item_service.py#L232) — `async def patch_item`.
- [backend/services/contract_service.py:530](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contract_service.py#L530) — `"amount": total`.

```python
60: 
61: 
62: class SupplierContractPatch(BaseModel):
63:     title: Optional[str] = None
64:     partner_name: Optional[str] = None
65:     process_type: Optional[str] = None
66:     product_id: Optional[str] = None
67:     input_product_id: Optional[str] = None
68:     tariff_basis: Optional[str] = None
```

**Bukti asli:** [evidence/repro/commercial-patch-bounds90-results.json](evidence/repro/commercial-patch-bounds90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| bounds.item_patch_reject_last_price | true | false | observed_difference |
| bounds.item_patch_reject_moq | true | false | observed_difference |
| bounds.item_patch_reject_lead_time_days | true | false | observed_difference |
| bounds.contract_patch_reject_tariff_rate | true | false | observed_difference |
| bounds.contract_patch_reject_min_charge | true | false | observed_difference |
| bounds.contract_patch_reject_shrinkage_pct | true | false | observed_difference |
| bounds.contract_patch_reject_tolerance_pct | true | false | observed_difference |
| bounds.contract_patch_reject_byproduct_pct | true | false | observed_difference |
| bounds.contract_patch_reject_yield_factor | true | false | observed_difference |
| bounds.contract_patch_reject_moq | true | false | observed_difference |

**Prompt agent development:**

Pertahankan constraint producer pada patch dan validasi service sebelum persist/calculation. Definisikan validator domain bersama bagi CRUD/import/snapshot/override. Data lama invalid harus diidentifikasi dan ditangani tanpa mengubah dokumen posted secara senyap.

**Kriteria penerimaan untuk reviewer:**

Invalid numericpatch ditolak400/422 dan DB tidak berubah. Normal patch tetap berfungsi; semua tarif/resultfinite dan valid. Uji negative, 0, percentage100/101, null/empty, currencyprecision, CSV/XLSX, contract override, mincharge, biaya tambahan dan seluruh consumer PR/PO/MKO/HPP.

## D4-KPI-WEIGHT-01 — Bobot KPI nol menjadi satu dan mengubah rata-rata tertimbang

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** HR → KPI → input/edit bobot → Self Service → KPI Saya.

**Rantai kejadian:** KPI 20 berbobot 1 + KPI 80 berbobot 3 → rata-rata 65; tambah KPI 150 berbobot 0 → API menyimpan bobot 1 dan rata-rata menjadi 82.

**Letak kesalahan dan penyebab:** Fallback berbasis truthiness menganggap nol sebagai nilai kosong, baik pada input frontend, producer service, maupun perhitungan agregat backend dan frontend periode historis. Schema saat ini secara eksplisit mengizinkan bobot >= 0.

**Dampak, hasil reproduksi, dan batas klaim:** Original ASGI create menerima weight=0 namun mengembalikan weight=1. Setelah PUT menyimpan weight=0, GET /hr/kpi/me tetap memberikan latest_score=82, seharusnya 65 berdasarkan rata-rata tertimbang dengan bobot nol. Kontrol bobot positif menghasilkan 65. Tidak dilakukan verifikasi DOM browser; ekspresi frontend ditelaah pada source. Jika bisnis ingin melarang nol, larangan harus eksplisit dan konsisten pada kontrak, bukan perubahan nilai senyap.

**Lokasi source pada commit audit:**

- [backend/services/hr_kpi_service.py:123](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L123) — `tw = sum(float(r.get("weight") or 1)`.
- [backend/services/hr_kpi_service.py:50](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L50) — `"score": score, "weight": float(payload.get("weight") or 1)`.
- [backend/schemas_hr_kpi.py:19](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_hr_kpi.py#L19) — `weight: float = Field(1, ge=0)`.
- [frontend/src/features/hr/KpiView.jsx:73](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/hr/KpiView.jsx#L73) — `weight: parseFloat(form.weight) || 1`.
- [frontend/src/features/hr/MyKpiCard.jsx:27](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/hr/MyKpiCard.jsx#L27) — `Number(r.weight) || 1`.

```python
121:     if not rows:
122:         return 0.0
123:     tw = sum(float(r.get("weight") or 1) for r in rows) or 1
124:     s = sum(float(r.get("score") or 0) * float(r.get("weight") or 1) for r in rows)
125:     return round(s / tw, 1)
```

**Bukti asli:** [evidence/repro/hr-kpi-projection90-results.json](evidence/repro/hr-kpi-projection90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| kpi.zero_weight_retained | 0 | 1.0 | observed_difference |
| kpi.zero_weight_aggregate | 65 | 82.0 | observed_difference |
| kpi.zero_weight_projection_after_patch | 65 | 82.0 | observed_difference |

**Prompt agent development:**

Tetapkan semantik bobot nol: bila diterima, pertahankan nol dari input sampai agregat dan abaikan kontribusinya; bedakan null/missing dari 0. Jika bisnis memilih bobot wajib positif, validasi UI/API/service dan migrasi data lama secara terkontrol. Gunakan evaluator rata-rata yang sama untuk periode terbaru dan historis.

**Kriteria penerimaan untuk reviewer:**

Dengan semantik nol valid: input/edit bobot 0 tetap 0 dan rata-rata contoh tetap 65 pada API serta tampilan periode terbaru/historis. Uji seluruh bobot nol, satu/dua metrik, bobot desimal, null, nilai negatif, rounding, penghapusan, filter karyawan/entitas/periode.

## D4-KPI-PERIOD-01 — Periode KPI yang bukan bulan kalender diterima dan dipilih sebagai periode terbaru

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** HR → KPI → periode input/edit → daftar KPI dan kartu KPI Saya.

**Rantai kejadian:** POST period=2026-99 diterima → my_kpi mengurutkan teks → latest_period=2026-99, menggeser Oktober 2026; PUT menerima period=bad dan metric kosong.

**Letak kesalahan dan penyebab:** Create memeriksa panjang/pemisah saja; patch tidak mengulang validasi periode maupun nama metrik. Pemilihan periode terbaru mengandalkan urutan string tanpa jaminan kalender valid.

**Dampak, hasil reproduksi, dan batas klaim:** Original API menerima 2026-99 dan GET /hr/kpi/me menjadikannya periode terbaru. PUT period=bad/metric kosong juga 200. Kontrol create periode x dan metrik kosong ditolak. Frontend memeriksa pola digit/pemisah, sehingga validitas bulan belum terjaga; bulan pada native input date tidak membuktikan kontrak API aman.

**Lokasi source pada commit audit:**

- [backend/services/hr_kpi_service.py:39](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L39) — `if len(period) != 7 or period[4] != "-":`.
- [backend/services/hr_kpi_service.py:64](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L64) — `for f in ("metric", "period", "note")`.
- [backend/services/hr_kpi_service.py:109](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L109) — `periods = sorted(`.
- [frontend/src/features/hr/KpiView.jsx:68](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/hr/KpiView.jsx#L68) — `if (!/^\d{4}-\d{2}$/.test(form.period))`.

```python
37:         raise ValueError("Nama metrik KPI wajib diisi.")
38:     period = (payload.get("period") or "")[:7]
39:     if len(period) != 7 or period[4] != "-":
40:         raise ValueError("Periode harus format YYYY-MM.")
41:     target = float(payload.get("target") or 0)
42:     actual = float(payload.get("actual") or 0)
43:     score = compute_score(target, actual, payload.get("score"))
44:     entity_id = emp.get("entity_id", "")
45:     doc = {
```

**Bukti asli:** [evidence/repro/hr-kpi-projection90-results.json](evidence/repro/hr-kpi-projection90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| kpi.patch_empty | 400 | 400 | pass |
| kpi.calendar_period_rejected | true | false | observed_difference |
| kpi.latest_period_real_calendar | "2026-10" | "2026-99" | observed_difference |
| kpi.patch_empty_metric_bad_period_rejected | true | false | observed_difference |

**Prompt agent development:**

Gunakan validator kalender YYYY-MM bersama untuk create/update/import dan validasi metrik nonkosong. Identifikasi periode lama invalid, pisahkan dari laporan sampai diperbaiki secara tercatat. Pilih periode terbaru dari data yang valid; jangan mengubah tanggal historis dengan tebakan.

**Kriteria penerimaan untuk reviewer:**

Bulan 00/13/99, tahun nonnumerik, panjang tidak tepat, serta metrik whitespace ditolak tanpa perubahan DB. Periode valid tetap diterima; latest_period dan filter konsisten; uji pergantian tahun, PUT parsial, data lama invalid dan tampilan historis.

## D4-KPI-SCORE-01 — Skor otomatis KPI dapat negatif meskipun kontrak fungsi menyatakan rentang 0–150

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** HR → KPI → target dan aktual → skor otomatis → KPI Saya.

**Rantai kejadian:** Target 100, aktual -10 → skor otomatis -10; skor manual negatif pada evaluator yang sama dibatasi menjadi 0.

**Letak kesalahan dan penyebab:** Jalur otomatis hanya membatasi nilai maksimum. Jalur skor eksplisit membatasi maksimum sekaligus minimum; keduanya berbeda dari kontrak rentang yang didokumentasikan.

**Dampak, hasil reproduksi, dan batas klaim:** Original API menerima target=100/actual=-10 dan menyimpan score=-10. Kontrol aktual 200 dibatasi 150, target nol/nonpositif menjadi 0, dan skor manual -1 menjadi 0. Metrik bebas bisa mempunyai aktual negatif; temuan menyangkut konsistensi rentang skor, bukan anggapan bahwa semua aktual negatif harus dilarang. Definisi rentang bisnis perlu ditegaskan bila ingin mengizinkan skor negatif.

**Lokasi source pada commit audit:**

- [backend/services/hr_kpi_service.py:31](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L31) — `return round(min(a / t, 1.5) * 100, 1)`.
- [backend/services/hr_kpi_service.py:21](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_kpi_service.py#L21) — `return round(max(0.0, min(float(score), 150.0)), 1)`.
- [backend/schemas_hr_kpi.py:18](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_hr_kpi.py#L18) — `score: Optional[float] = None`.

```python
29:     if t <= 0:
30:         return 0.0
31:     return round(min(a / t, 1.5) * 100, 1)
32: 
33: 
34: async def submit_kpi(emp: Dict[str, Any], payload: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
35:     metric = (payload.get("metric") or "").strip()
36:     if not metric:
37:         raise ValueError("Nama metrik KPI wajib diisi.")
```

**Bukti asli:** [evidence/repro/hr-kpi-projection90-results.json](evidence/repro/hr-kpi-projection90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| kpi.auto_score_lower_bound | 0 | -10.0 | observed_difference |

**Prompt agent development:**

Samakan aturan rentang evaluator otomatis dan manual sesuai definisi KPI yang disetujui. Pertahankan angka aktual asli; jangan mengubah aktual negatif menjadi nol untuk menutupi perhitungan. Jika rentang sengaja boleh negatif, sesuaikan kontrak, badge, ambang dan dokumentasi secara konsisten.

**Kriteria penerimaan untuk reviewer:**

Untuk kontrak 0–150, target100/aktual-10 menghasilkan skor0, aktual200 menghasilkan150. Uji target/aktual 0 dan negatif, manual vs otomatis, reset skor manual, bobot/rata-rata, rounding, nilai tidak finite dan tampilan badge.

## D4-BUD-EDIT-01 — Perubahan anggaran melewati keunikan periode/kunci dan batas tahun

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Finance → Anggaran → ubah tahun/bulan → kontrol PO dan laporan anggaran.

**Rantai kejadian:** Create dua anggaran Januari150 dan Februari200 untuk kunci yang sama → PATCH Februari menjadi Januari diterima → dua envelope pada kombinasi yang seharusnya tunggal; PATCH year1900 juga diterima.

**Letak kesalahan dan penyebab:** Create memeriksa duplikasi entity/year/month/dimension/key dan tahun 2000–2999. Update hanya memeriksa batas bulan dan amount, tidak memeriksa kombinasi hasil merge atau batas tahun; indeks unik komposit tidak ditemukan pada indeks bootstrap.

**Dampak, hasil reproduksi, dan batas klaim:** Original API menolak duplicate create dan tahun1900/3000. PATCH month menjadi1 pada anggaran Februari mengembalikan200 dan query DB menemukan dua anggaran Januari pada kunci yang sama; PATCH year1900 juga200. Laporan menjumlahkan setiap baris, sementara check_budget menggunakan find_one untuk envelope bulanan: duplicate membuat SSOT budget tidak lagi tunggal. Tidak diklaim ada PO over-budget yang benar-benar terposting pada skenario ini.

**Lokasi source pada commit audit:**

- [backend/services/budget_service.py:209](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L209) — `async def update_budget(`.
- [backend/services/budget_service.py:175](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L175) — `if year < 2000 or year > 2999:`.
- [backend/services/budget_service.py:183](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L183) — `dupe = await db.budgets.find_one(`.
- [backend/services/budget_service.py:434](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L434) — `monthly = await db.budgets.find_one(`.
- [backend/services/budget_service.py:352](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L352) — `for b in budgets:`.

```python
207: 
208: 
209: async def update_budget(budget_id: str, patch: Dict[str, Any],
210:                         scope: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
211:     q = {"id": budget_id, **(scope or {})}
212:     upd: Dict[str, Any] = {"updated_at": now_iso()}
213:     if patch.get("amount") is not None:
214:         amount = _r(patch["amount"])
215:         if amount <= 0:
```

**Bukti asli:** [evidence/repro/budget-ledger-policy90-results.json](evidence/repro/budget-ledger-policy90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| budget.patch_duplicate_rejected | true | false | observed_difference |
| budget.single_envelope_per_key | 1 | 2 | observed_difference |
| budget.patch_invalid_year_rejected | true | false | observed_difference |

**Prompt agent development:**

Validasi hasil merge patch dengan invariant create, termasuk rentang tahun dan keunikan komposit. Tambahkan constraint database yang sesuai setelah konflik lama direkonsiliasi; buat respons 400/409 yang dapat dipahami pengguna. Jangan diam-diam menjumlahkan atau menghapus anggaran konflik. Pastikan report dan check_budget memakai envelope kanonik yang sama.

**Kriteria penerimaan untuk reviewer:**

PATCH konflik ditolak dan kedua anggaran asli tetap utuh; year1900/3000 ditolak. Uji concurrent create/update, annual month0 dan monthly1–12, rename periode, filter entitas/dimensi, rollback kegagalan DB dan kesesuaian laporan vs enforcement PO.

## D4-BUD-THRESHOLD-01 — Ambang peringatan anggaran 0% berubah menjadi 85% pada laporan

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Finance → Aturan Anggaran → ambang peringatan → laporan vs pratinjau kontrol anggaran.

**Rantai kejadian:** Simpan warn_threshold_pct=0 → check_budget memberi peringatan → budget_vs_actual memberi status ok pada penggunaan20%.

**Letak kesalahan dan penyebab:** Fallback truthiness pada report memperlakukan nilai 0 yang sah sebagai missing lalu menggantinya dengan85. Evaluator check_budget membaca nol apa adanya.

**Dampak, hasil reproduksi, dan batas klaim:** Public schema dan set_rules mengizinkan 0–100. Fixture actual10/commitment20/budget150 memberi check.warning terisi pada ambang0, namun report row.status=ok. Angka actual/commitment/remaining pada kontrol normal benar; kesalahannya pada status/peringatan konfigurasi, bukan jumlah jurnal.

**Lokasi source pada commit audit:**

- [backend/services/budget_service.py:347](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L347) — `warn_pct = float(rules.get("warn_threshold_pct", 85.0) or 85.0)`.
- [backend/services/budget_service.py:475](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L475) — `near = out["used_pct_after"] is not None`.
- [backend/routers/budgets.py:35](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/budgets.py#L35) — `warn_threshold_pct: Optional[float] = Field(None, ge=0, le=100)`.

```python
345:     rules = await get_rules(entity_id_for_rules) if entity_id_for_rules else \
346:         {"entity_id": "", **DEFAULT_RULES, "is_default": True}
347:     warn_pct = float(rules.get("warn_threshold_pct", 85.0) or 85.0)
348: 
349:     rows: List[Dict[str, Any]] = []
350:     tot = {"budget": 0.0, "committed": 0.0, "actual": 0.0}
351:     per_dim: Dict[str, Dict[str, float]] = {}
352:     for b in budgets:
353:         dim = b.get("dimension") or DIM_ACCOUNT
```

**Bukti asli:** [evidence/repro/budget-ledger-policy90-results.json](evidence/repro/budget-ledger-policy90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| budget.zero_threshold_check_warning | true | true | pass |
| budget.zero_threshold_report_warning | "warning" | "ok" | observed_difference |

**Prompt agent development:**

Bedakan None/missing dari0 dan gunakan evaluator status/threshold bersama untuk report, preview dan enforcement. Terapkan pola yang sama untuk seluruh konfigurasi yang mengizinkan nol; jangan menaikkan batas minimum tanpa keputusan bisnis.

**Kriteria penerimaan untuk reviewer:**

Ambang0 tersimpan0 dan report/check memberi warning secara konsisten untuk contoh penggunaan positif. Uji0/85/100, empty/null, usage di bawah/tepat/di atas threshold, mode off/warn/block dan filter bulanan/tahunan.

## D4-RET-POLICY-01 — Deadline retur dapat berubah karena PO terbaru entitas lain dengan produk yang sama

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Retur Jual → evaluasi kelayakan → policy link_to_supplier_window → deadline dan status eligible.

**Rantai kejadian:** SO A memakai roll dari PO A/supplierA (window30) → eligible pada hari kedua; PO terbaru B/supplierB pada SKU sama (window1, receipt lama) → deadline A berubah dan retur yang sama menjadi tidak eligible.

**Letak kesalahan dan penyebab:** Resolver linked-supplier memilih PO terbaru berdasarkan product_id dan status tanpa membatasi entitas atau menelusuri asal roll yang memenuhi SO. Proxy produk sama tidak setara dengan asal fisik barang yang diretur.

**Dampak, hasil reproduksi, dan batas klaim:** Original service dengan policy A dan roll milik A yang mengacu OWN-PO menghasilkan supplierSA dan eligibleTrue. Penambahan FOREIGN-PO milik B mengubah supplier menjadiSB, deadline dan eligibleFalse, meski SO/roll/PO A tidak berubah. Fixture provenance dinyatakan eksplisit; tidak diklaim seluruh producer normal menghasilkan hubungan salah atau bahwa browser telah diuji. Mode linked bersifat opsional; mode nonlinked tidak terdampak oleh jalur ini.

**Lokasi source pada commit audit:**

- [backend/services/return_policy_service.py:241](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L241) — `po = await db.purchase_orders.find_one(`.
- [backend/services/return_policy_service.py:242](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L242) — `"items.product_id": {"$in": product_ids}`.
- [backend/services/return_policy_service.py:299](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L299) — `deadline = min(d1, d2).isoformat()`.
- [backend/services/return_policy_service.py:327](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L327) — `blocked = bool(enforce and dl is not None and not within_window)`.

```python
239: 
240:     # Cari PO terbaru yang memuat produk-produk ini (sebagai proxy asal beli).
241:     po = await db.purchase_orders.find_one(
242:         {"items.product_id": {"$in": product_ids},
243:          "status": {"$in": ["receiving", "partial", "completed", "closed", "closed_short"]}},
244:         {"_id": 0}, sort=[("created_at", -1)])
245:     if not po or not po.get("supplier_id"):
246:         return {"deadline": "", "supplier_id": "", "window_days": window_fallback, "source": "none"}
247: 
```

**Bukti asli:** [evidence/repro/budget-ledger-policy90-results.json](evidence/repro/budget-ledger-policy90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| return_policy.foreign_unrelated_po_not_selected | "SA" | "SB" | observed_difference |
| return_policy.eligibility_not_changed_by_foreign_po | true | false | observed_difference |
| return_policy.deadline_not_changed_by_foreign_po | "2026-01-31T00:00:00+00:00" | "2025-12-02T00:00:00+00:00" | observed_difference |

**Prompt agent development:**

Telusuri source PO/receipt/supplier dari roll atau shipment yang benar-benar memenuhi SO, termasuk lineage intercompany. Untuk item bersumber majemuk, hitung deadline per asal dan jelaskan basis penggabungannya. Jangan memakai PO terbaru SKU sebagai sumber keputusan blokir. Jika provenance belum tersedia, tampilkan unresolved/advisory sesuai keputusan bisnis; jangan mengarang deadline.

**Kriteria penerimaan untuk reviewer:**

Menambah/mengubah PO yang tidak terkait, termasuk entitas lain dan PO baru SKU yang sama, tidak mengubah eligibility SO A. Uji mixed suppliers, partial shipment, intercompany chain, retur sebagian roll, supplier window0, missing provenance, import/local, tenant boundary dan mode linked/nonlinked.



---

# Detail checkpoint 78 (referensi historis)

Jumlah dan cakupan pada bagian historis berikut adalah checkpoint lama; angka terbaru hanya ada di bagian Gelombang 3 di atas.

# Audit lanjutan KNHOST — data frontend dan rantai bisnis

**Kesimpulan: sistem belum dapat dinyatakan seluruh data dan flow-nya benar.** Sebanyak 19 temuan validasi sebelumnya masih terbuka; audit ini menambah 59 catatan yang membedakan counterexample, kompatibilitas legacy, gap definisi metrik dan kelemahan oracle tes. Daftar tidak menyamakan seluruh kegagalan pytest dengan bug.

**Commit diperiksa:** `a904d989b622f7da14c4892d03cf6ef0c43f3084`. **Pembanding:** `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`. Tanggal audit 2026-10-05. Semua bukti dibuat memakai source candidate asli, database lokal sintetis dan fixture terpisah. Perubahan aplikasi tidak diimplementasikan atau dipush dalam audit ini.

Prioritas utama: jendela kegagalan stock/production/receipt yang tetap terbuka; komisi lintas entitas; grain per pemilik pada valuasi/velocity; reservasi parsial yang diabaikan analitik; perkiraan AR/termin; pendapatan bersih diskon; target/scope; dan agregat versus halaman data. Chart bisa menghitung formula dengan benar tetapi mengambil cakupan, unit, status atau sumber yang salah.

**Cakupan 100% perilaku belum tercapai.** Inventaris seluruh 5.824 file dan parse 2.119 file code tersedia; 589 dari 638 GET dieksekusi, sementara 49 memerlukan fixture atau parameter khusus. Full pytest dan replay dijalankan, tetapi ada error fixture, skip, branch belum teruji dan belum ada browser/perangkat RFID/printer E2E. Jangan memakai laporan ini sebagai sertifikasi seluruh flow benar. Rincian coverage ada pada dokumen 04 dan CSV per file.


## Hasil utama current commit

Audit dimulai 5 Oktober 2026 dan paket diperbarui 6 Oktober 2026. Seluruh verdict dan permalink di bagian current tetap mengacu pada source beku `a904d989b622f7da14c4892d03cf6ef0c43f3084`; bukan sertifikasi commit lain yang mungkin diterbitkan setelah snapshot.

Tracker memuat **78 catatan terbuka**: 19 temuan validasi sebelumnya dan 59 catatan tambahan. Ini termasuk bug terukur, gap definisi metrik, kompatibilitas legacy dan kelemahan test/build; tidak seluruhnya bug runtime. Koreksi entity-switch dicatat pada dokumen 08.

Core **309/310**, W2 **82/82**, extended **414/455** lulus. Full pytest **1.539 pass/484 fail/76 skip/173 error**. Backend statement **49.31%**, branch **39.77%** dari denominator tetap. Coverage 100% belum terbukti. Detail remaining ada pada dokumen 13 dan register route/file.

Masalah yang baru diperjelas oleh patch: qty rencana versus PR, partial execution berlabel full, double promised incoming, raw yard berlabel meter, POpartial kehilangan sisa, concurrent stock fill melampaui demand dan denominator OrderDashboard dari window 20. Follow-up menambah lima temuan signifikan tentang refund store credit, durability aksi kasus, lifecycle dana dipegang karyawan, incomplete journal pair/ownership recovery dan valuasi transfer memakai WAC setelah perpindahan; lihat dokumen 14.

Satu tambahan frontend adalah D4-DOC-01: tombol Pratinjau Template Dokumen Dasar menuju endpoint yang tidak tersedia dan mengirim invoice walaupun template Surat Jalan dipilih. Existing document preview renderer lulus sebagai kontrol. Detail pada dokumen 15. Peta API sekarang mencakup 1431/1477 caller berdasarkan registered routes dan binding Babel yang konservatif; 46 unresolved tetap mempunyai register.

Tambahan enam temuan pada dokumen 16 memperluas rantai finance sampai reopen/reclose dan tampilan laporan: parent closing tidak diinvalidasi, recovery tidak mengadopsi JE yang telah tersimpan, anulir sesudah reversal membatalkan dua kali, input non-finite menghilangkan akun dari laporan, KPI laba ekuitas memakai perubahan laba belum ditutup, serta mode Semua Entitas kehilangan akun khusus PT. Kontrol normal dan batas fault/input dijelaskan terpisah.

Dokumen 17 menambah tujuh temuan WMS/RFID (empatP 1, tigaP 2): konflik PA/SO pada qty dan explicit-roll, recovery lokasi/tag/mutasi/saldo yang gagal, total unit campuran, KPI ready yang tidak sama dengan eligibility, checkpoint ingest sebelum read/incident/passage selesai, laporan count ganda saat retry, dan bukti verifikasi tag lama yang dipakai untuk identitas baru. Public producers diuji dengan kontrol normal; seluruh DOM dan perangkat fisik tetap belum diverifikasi.

## Cara membaca paket

| Berkas | Isi |
|---|---|
| `02-TEMUAN-DATA-FRONTEND.md` | Temuan baru: letak kode, source, expected/actual, dampak, prompt dan acceptance |
| `03-TEMUAN-LAMA-MASIH-TERBUKA.md` | 19 catatan lama yang belum tertutup |
| `04-CAKUPAN-DAN-BUKTI.md` | Angka coverage nyata dan batas pengujian |
| `05-RANTAI-MODUL-DAN-METRIK.md` | Hubungan antarmodul dan source-flow |
| `06-TRIAGE-PENGUJIAN.md` | Hasil current pytest/replay dan pemisahan kegagalan |
| `07-WORKFLOW-AGENT.md` / `prompts/` | Urutan fase dan aturan bukti closure |
| `findings-tracker.json` | Tracker 78 catatan; agent melengkapi bukti implementasi |
| `wave-1-2-revalidation-register.json` | Semua ID historis, verdict lama dan bukti replay terbaru dibedakan |
| `frontend-api-lineage.csv` | Mapping consumer literal ke handler, collection sumber langsung, unresolved eksplisit |
| `all-file-coverage.csv` | Semua file/hash/metode pemeriksaan; tidak disamaratakan telaah manual |
| `latest/`, `history/` | Output asli dan skrip pembanding, termasuk hasil nonpass |

## Daftar catatan terbuka

| ID | Prioritas | Catatan |
|---|---|---|
| V3-PROD-01 | P1 | Konsumsi bahan dapat berulang setelah movement insert gagal |
| V3-PROD-02 | P1 | Reversal dianggap selesai sebelum panjang roll dipulihkan |
| V3-MRES-01 | P1 | Dua PR mencadangkan bahan lebih banyak daripada stok |
| V3-AR-01 | P1 | Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh |
| V3-BANK-01 | P1 | Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh |
| V3-WEIGHT-01 | P1 | Split bersamaan menggandakan berat walaupun panjang benar |
| V3-PO-01 | P2 | Task selisih PO tidak refresh dan kehilangan identitas baris |
| V3-MKO-01 | P1 | Retry penerimaan maklon menambah output fisik dan nilai stok |
| V3-RFID-01 | P1 | Read green dari passage lama dipakai kembali pada passage baru |
| V3-CF-01 | P1 | Jurnal campuran kas/nonkas menghasilkan klasifikasi arus kas salah |
| V3-DATE-01 | P1 | Jurnal date-only pada awal periode hilang dari laporan |
| V3-WMS-02 | P1 | Loading gudang siap ditahan oleh pending cut gudang lain |
| V3-MASTER-01 | P2 | Apply master mengubah produk sebelum snapshot batch durable |
| V3-PO-02 | P2 | Pilihan amend ke jumlah diterima bertentangan dengan guard PO lama |
| V3-CUT-01 | P1 | Gagal membuat child cut menghilangkan stok dan reservasi |
| V3-MRES-02 | P1 | Total cadangan maklon tetap terpotong pada batas query |
| V3-PO-03 | P1 | Tugas selisih selesai meski amendment belum disetujui dan qty belum berubah |
| V3-DUP-01 | P3 | Helper _clean_perms didefinisikan dua kali |
| V3-BUILD-01 | P2 | Dependency build frontend tidak mempunyai lockfile terlacak |
| D4-STOCK-01 | P1 | Nilai dan kecepatan stok terhitung dua kali ketika pemilik berbagi SKU dan gudang |
| D4-STOCK-02 | P2 | Filter kategori tidak diterapkan pada bucket umur stok |
| D4-STOCK-03 | P2 | Nilai persediaan analitik mengabaikan landed cost |
| D4-STOCK-04 | P2 | Tanggal roll tanpa timezone dapat menjatuhkan laporan umur stok |
| D4-FIN-01 | P1 | Control Tower menggabungkan AR semua entitas ketika parameter entitas dihilangkan |
| D4-SALES-01 | P1 | Target penjualan dan penagihan tidak mengikuti scope entitas |
| D4-SALES-02 | P1 | Sales Home masih menampilkan order dan piutang lintas entitas di kartu pelanggan |
| D4-SALES-03 | P1 | Komisi per-SKU memasukkan SO tim sales milik entitas lain |
| D4-FIN-02 | P1 | Forecast kas memakai basis AR dan termin berbeda dari AR kanonis |
| D4-FIN-03 | P1 | Revenue profitabilitas memasukkan PPN included dan mengabaikan diskon header legacy |
| D4-FIN-04 | P2 | Label pendapatan realisasi sebenarnya memakai pesanan reserved dan WAC terkini |
| D4-AI-01 | P1 | Analytics AP mengabaikan fallback vendor bill yang masih dipakai sumber kanonis |
| D4-AI-02 | P2 | Metric pelanggan baru mengabaikan scope lini |
| D4-AI-03 | P2 | Refresh fact sales menghapus data lama sebelum replacement berhasil |
| D4-AI-04 | P2 | Pembulatan alokasi tim sales tidak mengonservasi nilai dokumen |
| D4-AI-05 | P1 | Stok tersedia dan reserved di live analytics serta snapshot mengabaikan reservasi parsial |
| D4-AI-06 | P1 | Total quantity lintas produk menjumlahkan meter dengan kilogram |
| D4-CASH-01 | P1 | Saldo awal kas kecil berpindah menjadi kas besar setelah transaksi terakhir di-void |
| D4-DASH-01 | P1 | Batas katalog 3.000 SKU masih menghilangkan master dan cadangan pada KPI |
| D4-HR-01 | P1 | Payroll gabungan memakai satu run pada KPI dan menimpa run lain pada trend |
| D4-HR-02 | P2 | Turnover menggunakan waktu edit data sebagai waktu karyawan keluar |
| D4-WMS-01 | P2 | RFID RED hari ini pada Warehouse Health memakai hari UTC |
| D4-WMS-02 | P2 | Cycle count terbaru yang belum selesai menghapus angka akurasi terakhir |
| D4-WMS-03 | P1 | Utilisasi gudang mengabaikan struktur Rack→Level→Bin yang didukung master |
| D4-MKT-01 | P2 | Reach agregat post disajikan ulang sebagai reach tiap platform dan akun |
| D4-RND-01 | P2 | KPI R&D menggabungkan orang berbeda yang mempunyai nama sama |
| D4-FE-01 | P2 | Grafik velocity Manager selalu memotong menjadi 14 hari |
| D4-FE-02 | P1 | Respons periode lama dapat menimpa grafik setelah periode diganti |
| D4-TEST-01 | P2 | Tes konsistensi ATP dapat lulus walaupun mencatat mismatch |
| D4-DATE-01 | P2 | Penjualan dan Home menggunakan bulan/tahun UTC yang berbeda dari periode bisnis WIB |
| D4-PLAN-01 | P1 | Rencana pembelian mencatat qty yang berbeda dari PR yang dirujuk |
| D4-PLAN-02 | P1 | Baris produk ganda pada API rencana dapat membuat pembelian melebihi kekurangan |
| D4-PLAN-03 | P1 | Riwayat mengatakan pemenuhan penuh walaupun sebagian eksekusi gagal |
| D4-PLAN-04 | P2 | Pesan kegagalan pemenuhan parsial terhapus oleh refresh otomatis |
| D4-PLAN-05 | P1 | Pasokan masuk yang sama dapat direncanakan penuh untuk beberapa SO |
| D4-GLOBAL-01 | P1 | Barang datang 100 yard dilabelkan 100 meter pada katalog stok global |
| D4-SUPPLY-01 | P1 | Sisa PO diterima sebagian hilang dari incoming karena definisi status berbeda |
| D4-BACKORDER-01 | P1 | Pemenuhan stok bersamaan mereservasi 160 untuk SO yang hanya kurang 100 |
| D4-CAP-01 | P1 | SKU yang benar-benar ada ditolak saat membuat PO setelah 1.000 master pertama |
| D4-ORDER-01 | P1 | Rata-rata pesanan membagi revenue seluruh pesanan dengan hanya 20 pesanan terbaru |
| D4-CASE-01 | P1 | Refund store credit menjurnal pengurangan kewajiban dua kali dan menciptakan pendapatan semu |
| D4-CASE-02 | P1 | Penyelesaian kasus keuangan dapat mengulang kas yang sudah tercatat setelah konflik atau kegagalan |
| D4-INTERCO-01 | P1 | Transfer roll retur dapat selesai memindahkan pemilik tetapi kehilangan jurnal pasangan dan dokumen pemulihan |
| D4-INTERCO-02 | P1 | Nilai transfer antarentitas memakai WAC sesudah stok sumber dipindahkan |
| D4-DOC-01 | P2 | Pratinjau Template Dokumen Dasar memanggil endpoint yang tidak tersedia dan mengabaikan jenis template |
| D4-CASE-03 | P1 | Alur dana dipegang karyawan tidak menjaga urutan langkah dan sisa piutang |
| D4-CLOSE-01 | P2 | Reopen bulan tidak menandai penutupan tahun yang bergantung padanya sebagai basi |
| D4-CLOSE-02 | P1 | Tutup ulang gagal mengadopsi jurnal yang sudah tersimpan sehingga recovery admin tetap gagal |
| D4-GL-01 | P1 | Jurnal manual yang sudah dibalik masih dapat dianulir dan membentuk pembatalan dua kali |
| D4-GL-02 | P1 | Jurnal manual meloloskan NaN/Infinity dan menghilangkan angka transaksi sah dari laporan |
| D4-EQ-01 | P1 | KPI Laba Periode Berjalan pada perubahan ekuitas berubah menjadi nol sesudah tutup buku |
| D4-COA-01 | P1 | Mode Semua Entitas pada laporan keuangan menghilangkan akun khusus entitas yang sah |
| D4-PA-01 | P1 | Reservasi SO mengambil roll yang sudah diklaim putaway dan meninggalkan lokasi alokasi lama |
| D4-PA-02 | P1 | Putaway kehilangan checkpoint setelah roll berpindah sehingga recovery stok dan tag gagal |
| D4-PA-03 | P2 | Total putaway menjumlahkan meter dan yard lalu memberi satu label satuan |
| D4-WMS-04 | P2 | KPI antrean simpan menghitung roll reserved yang tidak boleh diputaway |
| D4-RFID-01 | P1 | Deduplikasi event RFID melewati recovery keputusan, insiden dan status passage |
| D4-CC-01 | P2 | Recovery cycle count membuat dua laporan dan nomor untuk satu sesi |
| D4-TAG-01 | P1 | Verifikasi tag lama tetap berlaku setelah tag dihapus atau diganti dengan tag pending |


---

# Audit sumber data, angka dan tampilan frontend

Semua permalink dikunci pada commit yang diaudit. Expected pada gap definisi memakai makna label; keputusan bisnis yang berbeda harus didokumentasikan dan dilabelkan, bukan diasumsikan. Bukti function-level JavaScript tidak setara uji React di browser.

## D4-STOCK-01 — Nilai dan kecepatan stok terhitung dua kali ketika pemilik berbagi SKU dan gudang

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:137](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L137).



**Tampilan / rantai terkait:** Stock Analytics: nilai persediaan, sold_qty_window, fast/slow/dead · Intercompany / multi-owner → balances → analitik stok.

**Penyebab:** Roll dan movement diagregasikan menurut product_id + warehouse_id tanpa owner_entity_id, lalu hasil gabungan ditambahkan lagi untuk setiap balance pemilik. On-hand balance sendiri benar; nilai dan velocity salah.

**Dampak dan batas interpretasi:** Dua pemilik: A 10×10 dan B 20×20 seharusnya bernilai 500, tampil 1000. Penjualan 3+7 menjadi 20, bukan 10. Klasifikasi fast/slow/dead dan prioritas pembelian ikut dapat berubah.

- `D4-STOCK-01-value` — expected `500`; actual `1000.0`; `observed_difference`.
- `D4-STOCK-01-velocity` — expected `10`; actual `20.0`; `observed_difference`.
- `D4-STOCK-01-onhand-control` — expected `30`; actual `30.0`; `pass`.

```python
 134:         resolve_list_scope("inventory_movements", mv_query, ctx, entity_id),
 135:         {"_id": 0, "product_id": 1, "warehouse_id": 1, "timestamp": 1, "quantity": 1, "movement_type": 1}
 136:     ).to_list(20000)
 137:     # seg key = (product, warehouse) → recency/velocity penjualan
 138:     last_sale: Dict[tuple, datetime] = {}
 139:     sold_window: Dict[tuple, float] = {}
 140:     for m in movements:
 141:         if m.get("movement_type") not in SALE_MOVEMENT_TYPES:
 142:             continue
 143:         key = (m.get("product_id"), m.get("warehouse_id"))
 144:         dt = _parse_ts(m.get("timestamp"))
```

**Prompt perbaikan:**

> Periksa `D4-STOCK-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan grain product + warehouse + owner sampai tahap agregasi akhir. Jangan join aggregate dengan grain yang lebih kasar ke beberapa balance lalu menjumlahkannya lagi. Terapkan pola yang sama untuk movement, oldest-age dan WAC. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** SKU/gudang sama dengan dua pemilik: qty 30, nilai 500 dan sold 10; filter A=100/3, B=400/7. Tambahkan gudang kedua dan movement reversal; grouped total harus sama dengan penjumlahan partisi yang sah.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-STOCK-02 — Filter kategori tidak diterapkan pada bucket umur stok

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:175](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L175).



**Tampilan / rantai terkait:** Stock Analytics: filter kategori vs chart aging · Master kategori → stok fisik → chart umur.

**Penyebab:** Aging diakumulasi sebelum row product diperiksa terhadap category. Tabel kategori woven sudah difilter, bucket aging masih berisi kategori lain.

**Dampak dan batas interpretasi:** Fixture woven bernilai 100, knitting 400: memilih woven menghasilkan aging 500. Manajer membandingkan dua visual dengan cakupan berbeda.

- `D4-STOCK-02-filter` — expected `100`; actual `500.0`; `observed_difference`.

```python
 172:             seg_oldest_age[key] = age
 173:         b = _age_bucket(age)
 174:         aging[b]["qty"] += length
 175:         aging[b]["value"] += value
 176: 
 177:     # ── Agregasi per PRODUK (lintas gudang di scope) ──────────────────────────
 178:     prod_rows: Dict[str, Dict[str, Any]] = {}
 179:     for b in balances:
 180:         pid = b.get("product_id")
 181:         prod = products.get(pid, {})
 182:         if category and prod.get("category") != category:
```

**Prompt perbaikan:**

> Periksa `D4-STOCK-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bentuk product whitelist/filter yang sama sebelum mengambil roll, balance dan movement. Semua KPI/chart harus memakai filter yang sama, atau labelkan secara eksplisit jika global. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Filter woven: total rows 100 = sum aging 100; filter knitting 400. Uji kategori kosong, SKU tanpa kategori dan kombinasi entitas/gudang.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-STOCK-03 — Nilai persediaan analitik mengabaikan landed cost

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/stock_analytics_service.py:166](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L166).



**Tampilan / rantai terkait:** Stock Analytics: nilai stok · Receiving → landed cost → roll valuation → analitik.

**Penyebab:** Valuasi memakai base_unit_cost meskipun unit_cost roll sudah memuat landed cost. Basis ini berbeda dengan nilai penuh costing/GL; tampilan nilai persediaan tidak menyatakan hanya biaya dasar.

**Dampak dan batas interpretasi:** Roll 10, biaya dasar 10, biaya penuh 12: tabel nilai 100, biaya persediaan penuh 120. Rekonsiliasi dengan laporan biaya penuh tidak cocok.

- `D4-STOCK-03-landed` — expected `120`; actual `100.0`; `observed_difference`.

```python
 163:             continue
 164:         key = (r.get("product_id"), r.get("warehouse_id"))
 165:         length = float(r.get("length_remaining", 0) or 0)
 166:         cost = float(r.get("base_unit_cost", 0) or 0)
 167:         value = length * cost
 168:         seg_value[key] = seg_value.get(key, 0.0) + value
 169:         dt = _parse_ts(r.get("created_at")) or _parse_ts((r.get("acquired") or {}).get("date"))
 170:         age = (now - dt).days if dt else 9999
 171:         if key not in seg_oldest_age or age > seg_oldest_age[key]:
 172:             seg_oldest_age[key] = age
 173:         b = _age_bucket(age)
```

**Prompt perbaikan:**

> Periksa `D4-STOCK-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tetapkan kontrak nilai persediaan: tampilkan biaya penuh dari sumber biaya kanonis; bila perlu pisahkan dasar, landed dan total. Jangan menjumlahkan landed dua kali. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Roll 10×12 menghasilkan 120, split dasar 100 + landed 20. Uji voucher landed apply/void dan per-entitas. Jika bisnis memilih base-only, label dan rekonsiliasi harus menyatakan basis tersebut.

**Hubungan dengan catatan lain:** D4-STOCK-01

## D4-STOCK-04 — Tanggal roll tanpa timezone dapat menjatuhkan laporan umur stok

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_legacy_compatibility.

**Letak:** [backend/services/stock_analytics_service.py:33](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L33).



**Tampilan / rantai terkait:** Stock Analytics aging · Import/legacy roll → parsing tanggal → laporan.

**Penyebab:** Parser mengembalikan datetime naive untuk string YYYY-MM-DD, lalu dikurangkan dari now yang timezone-aware.

**Dampak dan batas interpretasi:** Satu roll legacy/import created_at date-only menghasilkan TypeError. Ini bukan klaim bahwa create roll normal menghasilkan tanggal tersebut; producer normal menggunakan timestamp ISO.

- `D4-STOCK-04-date-only` — expected `null`; actual `"TypeError: can't subtract offset-naive and offset-aware datetimes"`; `observed_difference`.

```python
  30: ]
  31: 
  32: 
  33: def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
  34:     if not ts:
  35:         return None
  36:     try:
  37:         return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
  38:     except Exception:
  39:         return None
  40: 
```

**Prompt perbaikan:**

> Periksa `D4-STOCK-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Normalisasi timezone pada boundary parsing dan tentukan kebijakan tanggal legacy. Jangan mengubah data historis diam-diam tanpa aturan timezone yang disetujui. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Date-only, ISO dengan offset, Z, kosong dan tanggal invalid ditangani deterministik tanpa exception server; aging hari diperiksa di batas WIB.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FIN-01 — Control Tower menggabungkan AR semua entitas ketika parameter entitas dihilangkan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/finance_analytics.py:68](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/finance_analytics.py#L68).



**Tampilan / rantai terkait:** Finance Tower: outstanding, overdue, working capital, per-entity BI · Entity context → GL/AP/AR → tower.

**Penyebab:** Scope journal menggunakan konteks aktif, tetapi ent=None diteruskan ke aging_report, dan comparison memakai semua allowed_entity_ids. Scope komponen dalam satu respons berbeda.

**Dampak dan batas interpretasi:** Header aktif A dengan hak A+B: tanpa query param AR1000; explicit entity_id=A AR100. GL/AP bisa tetap A. Working capital dan perbandingan tidak punya cakupan konsisten. UI yang selalu mengirim A tidak otomatis terdampak jalur default ini.

- `D4-FIN-01-tower` — expected `{"omitted": 100, "explicit": 100}`; actual `{"omitted": 1000.0, "explicit": 100.0}`; `observed_difference`.

```python
  65:     ctx = await entity_ctx(request)
  66:     scope = resolve_list_scope("journal_entries", {}, ctx, entity_id)
  67:     ent = entity_id if entity_id and entity_id != "all" else None
  68:     comp_ids = [entity_id] if ent else list(ctx.allowed_entity_ids)
  69:     return await tower.finance_tower(scope=scope, entity_id=ent, entity_ids=comp_ids)
```

**Prompt perbaikan:**

> Periksa `D4-FIN-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Resolve effective scope sekali dan teruskan ke setiap service. Bedakan active, selected dan all secara eksplisit. All harus tetap dibatasi allowed entity set dan tidak memakai None ambigu. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Default/header A sama dengan explicit A; B dan all memiliki angka terpisah yang benar. Rekonsiliasi cash+AR−AP dalam scope identik. Uji allowed subset.

**Hubungan dengan catatan lain:** D4-SALES-02

## D4-SALES-01 — Target penjualan dan penagihan tidak mengikuti scope entitas

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:155](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L155).



**Tampilan / rantai terkait:** Sales Home / Sales Force: target, achievement, komisi tier · Target entitas → KPI scoped → denominator target.

**Penyebab:** Lookup target hanya sales_id dan period, tanpa entity_id. Target A dapat menjadi pembagi KPI B. Probe menggunakan satu target sah di A, tidak mengasumsikan public API mampu membuat dua target paralel yang tidak didukung.

**Dampak dan batas interpretasi:** B tidak punya target namun memperoleh 100 dari A. Achievement dan ambang insentif tier dapat salah walaupun numerator KPI sudah benar.

- `D4-SALES-01-target-scope` — expected `0`; actual `100.0`; `observed_difference`.

```python
 152:     return total
 153: 
 154: 
 155: async def _target_sales_for(sales_id: str, period: str) -> float:
 156:     """Target PENJUALAN (omzet) dalam periode — terpisah dari target penagihan."""
 157:     targets = await db.sales_targets.find({"sales_id": sales_id}, {"_id": 0}).to_list(400)
 158:     return sum(float(t.get("target_sales_amount") or 0) for t in targets if _period_contains(period, t.get("period", "")))
 159: 
 160: 
 161: async def _scheme_for(sales_id: str, period: str) -> Dict[str, Any]:
 162:     """Skema insentif: exact period -> skema terbaru sales -> default tiers."""
```

**Prompt perbaikan:**

> Periksa `D4-SALES-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan kontrak target per-entity/global; selaraskan schema, uniqueness/upsert dan query untuk target_sales serta target_collection. Nilai tidak dikonfigurasi harus dibedakan dari nol. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Target A100; B tidak ada → B tidak memakai 100. A/B/all, period month/quarter/year, fallback legacy dan tier boundary diuji tanpa penggandaan target.

**Hubungan dengan catatan lain:** D4-SALES-03

## D4-SALES-02 — Sales Home masih menampilkan order dan piutang lintas entitas di kartu pelanggan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/home_service.py:59](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/home_service.py#L59).



**Tampilan / rantai terkait:** Sales Home: pelanggan, AR, recent_orders · Customer master → SO entity → credit → home.

**Penyebab:** Home memfilter customer menurut A, tetapi memanggil compute_customer_credit tanpa entity dan mengambil recent SO customer tanpa entity. Perbaikan KPI di sales_force tidak menyelesaikan consumer home ini.

**Dampak dan batas interpretasi:** Customer A mempunyai SO A100 dan SO B700: kartu A outstanding 800, seharusnya 100; recent_orders berisi SO B. Dalam model pelanggan lintas entitas ini bukan pelanggaran producer, tetapi consumer tidak membatasi dokumen.

- `D4-SALES-02-recent-orders` — expected `false`; actual `true`; `observed_difference`.
- `D4-SALES-02-credit-cards` — expected `100`; actual `800.0`; `observed_difference`.

```python
  56:     customers = await db.customers.find(cust_filter, {"_id": 0}).to_list(2000)
  57:     cust_rows: List[Dict[str, Any]] = []
  58:     for c in customers:
  59:         cc = await compute_customer_credit(c)
  60:         cust_rows.append({
  61:             "id": c["id"], "name": c.get("name", ""),
  62:             "credit_limit": cc["credit_limit"], "ar_outstanding": cc["ar_outstanding"],
  63:             "overdue_amount": cc["overdue_amount"], "status": cc["status"],
  64:         })
  65:     cust_rows.sort(key=lambda r: r["overdue_amount"], reverse=True)
  66:     collections = [r for r in cust_rows if r["overdue_amount"] > 0][:8]
```

**Prompt perbaikan:**

> Periksa `D4-SALES-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Teruskan effective entity ke credit helper dan query recent orders. Selaraskan home/KPI/aging sehingga konteks aktif bermakna sama, serta lindungi all dengan allowed scope. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Home A AR100 dan hanya SO A; Home B700; all 800 bila diizinkan. Customer dengan assigned-sales berubah dan SO tim lintas entitas tidak menghasilkan salah atribusi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-SALES-03 — Komisi per-SKU memasukkan SO tim sales milik entitas lain

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:253](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L253).



**Tampilan / rantai terkait:** Sales Force: incentive, commission history dan accrual · SO sales_team → payment → incentive rate → payroll/finance liability.

**Penyebab:** Query komisi OR customer assigned / sales_team tidak menambahkan entity_id pada SO. KPI dan rate scoped A, tetapi basis commission dapat berasal dari B.

**Dampak dan batas interpretasi:** SO B paid 900 dengan 9 unit, sales S100% dan rate A1: KPI collected A0, insentif 9. Angka ini dapat dipakai proses accrual; bukan hanya chart kosmetik.

- `D4-SALES-03-commission-entity` — expected `{"commission": 0, "collected_basis": 0}`; actual `{"commission": 9.0, "collected_basis": 0.0}`; `observed_difference`.

```python
 250:     return per_unit, float(cfg.get("discount_factor", 1.0) or 0)  # tier_factor
 251: 
 252: 
 253: async def _compute_commission_per_sku(
 254:     sales_id: str, period: str, entity_id: Optional[str], settings: Dict[str, Any]
 255: ) -> Dict[str, Any]:
 256:     """Engine per-SKU, 3 faktor, margin-aware, on-collection (EPIC4).
 257: 
 258:     Untuk tiap order, fraksi terbayar = Σpembayaran-dalam-periode / grand_total (≤1).
 259:     Per line: qty_terbayar = base_quantity × fraksi; komisi = qty × per_unit × factor,
 260:     di-cap oleh margin (margin_cap_pct% × margin line terbayar; pakai WAC EPIC3).
```

**Prompt perbaikan:**

> Periksa `D4-SALES-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan satu eligible-order scope untuk KPI, collection allocation dan komisi. Query OR attribution harus dibungkus scope entity/status/period. Hitung cost per SO owner; jangan rate A mengalikan transaksi B. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** A tanpa SO memperoleh 0 walau S masuk tim B. A/B/all, shared customer, split team, partial receipt, return/void dan accrual ulang harus memenuhi konservasi serta idempotensi.

**Hubungan dengan catatan lain:** D4-SALES-01

## D4-FIN-02 — Forecast kas memakai basis AR dan termin berbeda dari AR kanonis

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/cashflow_forecast_service.py:66](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cashflow_forecast_service.py#L66).



**Tampilan / rantai terkait:** Finance Cashflow Forecast: inflow, due bucket, projected cash · Payment profile/SO terms → outstanding AR → cash forecast.

**Penyebab:** NON_AR_METHODS didefinisikan tetapi tidak dipakai, projection tidak memuat payment_profile_method. Due date dihitung dari default pelanggan terkini, mengabaikan payment_term_days snapshot SO; term 0 juga berubah 30 karena or30.

**Dampak dan batas interpretasi:** SO tunai unpaid 200 menjadi inflow AR200. SO tempo dengan snapshot 90 hari/default customer 30 diproyeksikan60 hari terlalu cepat. Risiko optimisme likuiditas dan bucket overdue salah.

- `D4-FIN-02-cash-order-as-ar` — expected `0`; actual `200.0`; `observed_difference`.
- `D4-FIN-02-order-terms` — expected `"2027-01-03"`; actual `"2026-11-04"`; `observed_difference`.

```python
  63: 
  64:     # Peta term_days per customer utk estimasi jatuh tempo AR.
  65:     cust_rows = await db.customers.find({}, {"_id": 0, "id": 1, "payment_profile": 1}).to_list(20000)
  66:     term_map = {c["id"]: int((c.get("payment_profile") or {}).get("term_days", 30) or 30)
  67:                 for c in cust_rows}
  68: 
  69:     buckets: Dict[str, Dict[str, Any]] = {
  70:         k: {"key": k, "label": lbl, "inflow": 0.0, "outflow": 0.0}
  71:         for k, lbl, _lo, _hi in BUCKETS
  72:     }
  73:     ar_items: List[Dict[str, Any]] = []
```

**Prompt perbaikan:**

> Periksa `D4-FIN-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Reuse sumber AR kanonis untuk eligibility, net outstanding, method dan due date. Forecast boleh punya skenario sendiri hanya jika dipisahkan dari confirmed receivables dan diberi label/asumsi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Tunai tidak masuk AR forecast; tempo 90 mengikuti SO meski profile diubah 30; termin 0 tetap 0. Return/credit note, DP, partial receipt dan closing/reversal harus cocok dengan aging pada snapshot yang sama.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FIN-03 — Revenue profitabilitas memasukkan PPN included dan mengabaikan diskon header legacy

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/profitability_service.py:118](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/profitability_service.py#L118).



**Tampilan / rantai terkait:** Profitability: revenue, margin, dimension totals dan monthly trend · SO pricing/discount → profitability → management decision.

**Penyebab:** Revenue langsung menjumlahkan line_total. Pada harga tax included, field ini masih memuat PPN; revenue kanonis adalah grand_total−ppn_amount. Shape legacy dengan diskon order terpisah juga tidak dialokasikan. Current create_order memaksa manual order discount=0, sehingga contoh diskon header tidak digeneralisasi sebagai alur SO baru.

**Dampak dan batas interpretasi:** Pricing producer asli pada entitas PKP dengan pengaturan ppn_mode=included menghasilkan revenue laporan 1000 meski nilai net setelah PPN lebih kecil. Semua dimensi/trend mewarisi PPN sebagai pendapatan. Contoh legacy baris 1000−diskonheader 100 menjadi 1000 vs net 900 dipertahankan dengan label legacy.

- `D4-FIN-03-order-discount-legacy` — expected `900`; actual `1000.0`; `observed_difference`.
- `D4-FIN-03-tax-included` — expected `900.9`; actual `1000.0`; `observed_difference`.

```python
 115:             pid = it.get("product_id") or ""
 116:             # Tanya KN F0.4 — WAC per satuan DASAR → HPP memakai base_quantity (qty jual bisa roll/meter).
 117:             qty = float(it.get("base_quantity") or it.get("quantity") or 0)
 118:             revenue = float(it.get("line_total", it.get("subtotal", 0)) or 0)
 119:             if qty <= 0 and revenue <= 0:
 120:                 continue
 121:             ck = f"{pid}::{ent or ''}"
 122:             if ck in wac_cache:
 123:                 wb, wl = wac_cache[ck]
 124:             else:
 125:                 w = await wac_for_product(pid, entity_id=ent)
```

**Prompt perbaikan:**

> Periksa `D4-FIN-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan shared net revenue allocation seperti fact sales dengan residual rounding yang terkontrol. Ambil grand_total−ppn_amount sesuai kontrak kanonis, dan jangan mengurangi diskon item dua kali ketika line_total sudah net. Jelaskan return/void dan legacy header discount. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Harga included 1000: Σrevenue harus grand_total−ppn_amount dari producer pricing; excluded dan non-PKP tetap benar. Legacy ordergross 1000−headerdisc 100=net 900 bila shape masih didukung. Semua dimensi, residual cent dan credit return direkonsiliasi.

**Hubungan dengan catatan lain:** D4-AI-04, D4-FIN-04

## D4-FIN-04 — Label pendapatan realisasi sebenarnya memakai pesanan reserved dan WAC terkini

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/profitability_service.py:19](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/profitability_service.py#L19).



**Tampilan / rantai terkait:** Profitability: Pendapatan (Realisasi), HPP (WAC), Marjin Kotor · SO reserved/confirmation → shipment/GL → report definition.

**Penyebab:** SOLD_STATUSES memasukkan confirmed dan reserved, tanggal memakai created_at SO, biaya dihitung dari WAC saat query. Ini analisis nilai pesanan dengan biaya kini, bukan otomatis realisasi shipment/GL historis.

**Dampak dan batas interpretasi:** SO reserved 100 tanpa shipment/GL memberi Pendapatan (Realisasi)100. Current WAC bukan dengan sendirinya bug untuk estimasi; masalahnya kontrak label dan interpretasi. Probe hanya membuktikan reserved revenue, bukan semua skenario historical cost.

- `D4-FIN-04-unshipped-as-realisation` — expected `0`; actual `100.0`; `observed_difference`.

```python
  16: 
  17: EPS = 0.005
  18: # Status SO yang dianggap penjualan (revenue-recognized / dalam pemenuhan).
  19: SOLD_STATUSES = ["confirmed", "reserved", "partially_shipped", "shipped", "done"]
  20: MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
  21: 
  22: 
  23: def _pct(margin: float, revenue: float) -> Optional[float]:
  24:     return round(margin / revenue * 100, 1) if revenue > EPS else None
  25: 
  26: 
```

**Prompt perbaikan:**

> Periksa `D4-FIN-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pilih dan dokumentasikan metrik booked-order estimate vs realised revenue/margin. Jika realisasi, gunakan shipped/recognized amount serta cost snapshot yang sesuai. Jika tetap SO/WAC kini, ubah label/basis dan pisahkan estimator dari GL. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Reserved menunjukkan estimasi 100 dan realisasi 0 dalam metrik berbeda. Partial shipment, tanggal order vs dispatch, return, landed adjustment dan perubahan WAC memiliki perilaku terdefinisi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-01 — Analytics AP mengabaikan fallback vendor bill yang masih dipakai sumber kanonis

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_legacy_compatibility.

**Letak:** [backend/services/analytics_engine.py:288](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L288).



**Tampilan / rantai terkait:** Tanya KN / metric AP outstanding · Vendor bill legacy → bill_financials → analytics AP.

**Penyebab:** AP analytics hanya grand_total−amount_paid. bill_financials mendukung grand_total0 dengan total_amount fallback. Dokumen legacy yang sah jadi hilang dari analytics.

**Dampak dan batas interpretasi:** Billtotal 125, paid 25, grand_total0: sumber kanonis outstanding 100, analytics tidak menghasilkan baris (praktis 0).

- `D4-AI-01-ap-fallback` — expected `100`; actual `null`; `observed_difference`.

```python
 285: 
 286: async def _src_ap(metrics, dims, grain, p: Period, filters, sc, w, _s):
 287:     fq = _match_filters("ap", filters, w)
 288:     remaining = {"$subtract": [{"$ifNull": ["$grand_total", 0]}, {"$ifNull": ["$amount_paid", 0]}]}
 289:     due_field = {"$ifNull": ["$due_date", "$bill_date"]}
 290:     pre = [{"$match": {"entity_id": {"$in": sc.entity_ids},
 291:                        "status": {"$nin": ["draft", "cancelled", "void", "paid", "rejected"]}, **fq}},
 292:            {"$addFields": {"_rem": remaining, "_due": due_field}}, {"$match": {"_rem": {"$gt": 0.005}}}]
 293:     if grain:
 294:         w.append("Hutang adalah posisi saat ini; tidak dipecah per waktu.")
 295:     if p.date_to < now_wib().date():   # KN-E36 — hutang tidak punya snapshot historis
```

**Prompt perbaikan:**

> Periksa `D4-AI-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Normalisasi amount melalui satu kontrak bill financials yang juga dapat dieksekusi agregasi. Jangan membuat fallback berbeda antar aging, forecast, BI dan Tanya. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Grand_total positif, grand_total0 dengan total_amount, paid partial, legacy missing field, posted/void dan multicurrency jika didukung: outstanding konsisten dengan canonical.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-02 — Metric pelanggan baru mengabaikan scope lini

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_engine.py:168](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L168).



**Tampilan / rantai terkait:** Tanya KN / Analytics: new customer by line · Custom role line → fact_sales_lines → customer metric.

**Penyebab:** _src_fact_new tidak memakai sc.line_q sebagaimana sumber fact lain. Filter woven tetap menghitung customer knitting-only.

**Dampak dan batas interpretasi:** Dalam scope woven, satu customer yang hanya membeli knitting terhitung sebagai pelanggan baru 1, seharusnya 0 sesuai scope yang diminta.

- `D4-AI-02-new-customer-line` — expected `0`; actual `1`; `observed_difference`.

```python
 165:     return out
 166: 
 167: 
 168: async def _src_fact_new(metrics, dims, grain, p: Period, filters, sc: Scope, w, include_samples):
 169:     match: Dict[str, Any] = {"entity_id": {"$in": sc.entity_ids}, "is_live": True, "is_sample": False}
 170:     if sc.sales_only:
 171:         match["sales_id"] = sc.sales_only
 172:     fq = _match_filters("fact", filters, w)
 173:     fmap = cat.SOURCE_DIMS["fact"]
 174:     first = {fmap[d]: {"$first": f"${fmap[d]}"} for d in dims if d != "customer"}
 175:     pipe = [{"$match": {**match, **({"$and": fq["$and"]} if fq else {})}}, {"$sort": {"date_wib": 1}},
```

**Prompt perbaikan:**

> Periksa `D4-AI-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan scope/line policy bersama sebelum first-purchase grouping, termasuk keputusan apakah first berarti first ever atau first di lini. Jangan hanya filter sesudah agregasi first. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Knitting-only excluded woven; customer pernah membeli knitting lalu pertama woven diuji menurut definisi yang disetujui. Entity/owned-customer/role dimensi tetap enforced.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-03 — Refresh fact sales menghapus data lama sebelum replacement berhasil

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_facts.py:146](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_facts.py#L146).



**Tampilan / rantai terkait:** Tanya KN / analytics fact refresh · SO source → ETL/fact refresh → dashboards.

**Penyebab:** _write melakukan delete semua fact SO yang direfresh lalu insert_many. Bila insert gagal sebelum write, projection lama hilang walaupun source SO tetap ada.

**Dampak dan batas interpretasi:** Factrow 1 menjadi 0 setelah fault insert. Analitik/AI dapat memberi angka 0 saat refresh gagal; ini kerusakan read model, bukan bukti GL atau SO hilang.

- `D4-AI-03-durable-refresh` — expected `1`; actual `0`; `observed_difference`.

```python
 143:     rows: List[Dict[str, Any]] = []
 144:     for o in orders:
 145:         rows.extend(build_rows(o, customers.get(o.get("customer_id") or "") or {}, products, users, mode))
 146:     await db.fact_sales_lines.delete_many({"so_id": {"$in": [o["id"] for o in orders]}})
 147:     if rows:
 148:         await db.fact_sales_lines.insert_many(rows, ordered=False)
 149:     return len(rows)
 150: 
 151: 
 152: async def _process(cursor_query: Dict[str, Any]) -> Tuple[int, int, str]:
 153:     mode = (await ai_policy())["sales_attribution"]
```

**Prompt perbaikan:**

> Periksa `D4-AI-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan generation staging + atomic publish pointer, transaction, atau deterministic upsert + retire stale rows hanya setelah replacement lengkap. Simpan sync progress dan expose freshness/error. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/sesudah tiap write tidak membuat complete snapshot lama hilang. Retry dan dua worker tidak duplicate fact; Σfact sama source valid, invalid schema tidak menurunkan seluruh dataset.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-04 — Pembulatan alokasi tim sales tidak mengonservasi nilai dokumen

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_facts.py:118](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_facts.py#L118).



**Tampilan / rantai terkait:** Fact Sales / Tanya KN: revenue by sales dan total · SO split sales → rounded fact rows → analytics sums.

**Penyebab:** Setiap bagian dibulatkan independen ke2 desimal tanpa menempatkan residual pada baris deterministik.

**Dampak dan batas interpretasi:** Tim dua anggota PIC/co dengan split 50/50 memenuhi aturan maksimaldua anggota saatini. Net 1.01 menjadi 0.51+0.51=1.02. Perbedaan kecil per dokumen dapat terakumulasi; gunakan satuan uang sesuai kontrak sebenarnya.

- `D4-AI-04-money-conservation` — expected `1.01`; actual `1.02`; `observed_difference`.

```python
 115:                 "qty_base": round(qty_base * split, 4),
 116:                 "rolls": round(_f(it.get("qty_rolls")) * split, 4),
 117:                 "gross": round(gross_alloc, 2),
 118:                 "net_alloc": round(net_alloc, 2),
 119:                 "discount": round(gross_alloc - net_alloc, 2),
 120:                 "ppn_alloc": round(ppn * share * split, 2),
 121:                 "cost": round(_f(it.get("unit_cost")) * qty_base * split, 2),
 122:             })
 123:     return rows
 124: 
 125: 
```

**Prompt perbaikan:**

> Periksa `D4-AI-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Alokasikan dalam minor units/Decimal, gunakan largest-remainder atau residual akhir deterministik untuk gross/net/PPN. Konservasi harus terjaga pada semua grouping. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Net 1.01 dibagi 2 anggota 50/50 tetap total 1.01; fractionaldiscount+tax,10 lines×2 sales, negative return dan replay sync tidak mengubah total/identity. Data legacy dengan anggota lebihbanyak, bila masihdibaca, tidak boleh merusak konservasi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-05 — Stok tersedia dan reserved di live analytics serta snapshot mengabaikan reservasi parsial

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_snapshots.py:18](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_snapshots.py#L18).



**Tampilan / rantai terkait:** Tanya KN: available/reserved stock dan historical stock · Partial cut reservation → inventory_balances / rolls → live/snapshot analytics.

**Penyebab:** Live _src_stock dan snapshot_stock menggolongkan seluruh length_remaining menurut status roll. Roll available dengan length_reserved3 tetap dihitung available 10/reserved 0.

**Dampak dan batas interpretasi:** Original roll helper membuat roll 10 dan reserve 3; SSOTbalance free 7/reserved 3. Analytics dan snapshot masing-masing 10/0. Sales/MD mendapat available yang berlebihan.

- `D4-AI-05-partial-cut-live` — expected `{"stock_available_qty": 7, "stock_reserved_qty": 3}`; actual `{"stock_available_qty": 10.0, "stock_reserved_qty": 0}`; `observed_difference`.
- `D4-AI-05-partial-cut-snapshot` — expected `{"avail": 7, "reserved": 3}`; actual `{"avail": 10.0, "reserved": 0}`; `observed_difference`.

```python
  15:     pipe = [{"$match": {"status": {"$in": list(cat.PHYSICAL_ROLL_STATUSES)}}},
  16:             {"$group": {"_id": {k: f"${k}" for k in _STOCK_KEYS}, "qty": {"$sum": rem}, "rolls": {"$sum": 1},
  17:                         "value": {"$sum": {"$multiply": [rem, {"$ifNull": ["$unit_cost", 0]}]}},
  18:                         "avail": {"$sum": {"$cond": [{"$eq": ["$status", "available"]}, rem, 0]}},
  19:                         "reserved": {"$sum": {"$cond": [{"$in": ["$status", list(cat.RESERVED_ROLL_STATUSES)]}, rem, 0]}}}}]
  20:     rows = [{"date": day, **{k: r["_id"].get(k) or "" for k in _STOCK_KEYS},
  21:              **{k: r[k] for k in ("qty", "rolls", "value", "avail", "reserved")}}
  22:             async for r in db.inventory_rolls.aggregate(pipe)]
  23:     await db.fact_stock_daily.delete_many({"date": day})
  24:     if rows:
  25:         await db.fact_stock_daily.insert_many(rows)
```

**Prompt perbaikan:**

> Periksa `D4-AI-05` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan canonical physical/free/reserved definition yang mengakomodasi whole-roll dan partial-length. Pisahkan availability fisik vs ATP vs ready-to-dispatch; jangan memperbaiki hanya snapshot sementara live tetap berbeda. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Available roll 10 reservedlength 3 → free 7/reserved 3; whole reserved 10→free 0/reserved 10. Hold/quarantine, makloon-reserved, cut complete/release dan snapshotday diuji live=historical snapshot saat titik waktu sama.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-AI-06 — Total quantity lintas produk menjumlahkan meter dengan kilogram

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/analytics_engine.py:565](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L565).



**Tampilan / rantai terkait:** Tanya KN metric tables: totals dan shares · Product base UOM → query group_by product → quantity total.

**Penyebab:** Unit guard hanya menambahkan unit ketika group_by tidak memuat product/unit. Mixed-unit detection hanya berjalan jika unit menjadi dimensi. Group product dapat mengembalikan meter/kg dengan total tunggal.

**Dampak dan batas interpretasi:** Stock 10 meter +5kg tampiltotal 15, yang tidak punya arti dimensional. Row bisa benar tetapi total/share menyesatkan.

- `D4-AI-06-mixed-product-total` — expected `null`; actual `15.0`; `observed_difference`.

```python
 562:     shares = bool(dims or grain)
 563:     # KN-E34 — baris sudah per satuan; total/pembanding/porsi qty juga tidak boleh lintas satuan.
 564:     ui = dims.index("unit") if "unit" in dims else None
 565:     mixed = ui is not None and len({k[ui] for k in keys}) > 1
 566:     unit_tot: Dict[Any, Dict[str, float]] = {}
 567:     if mixed:
 568:         for k, cur in rows.items():
 569:             for m in shown:
 570:                 if m in cat.QTY_METRICS:
 571:                     unit_tot.setdefault(k[ui], {})[m] = unit_tot.get(k[ui], {}).get(m, 0.0) + float(cur.get(m) or 0)
 572:         warnings.append("Total qty tidak ditampilkan karena lintas satuan; porsi dihitung per satuan.")
```

**Prompt perbaikan:**

> Periksa `D4-AI-06` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Lacak unit fisik dari metadata row walau dimensi product dipilih. Quantity mixed tidak memiliki grand total; kelompokkan per unit atau konversi eksplisit hanya dalam dimensi kompatibel dengan faktor tersimpan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Product 10m+5kg → total null/N/A dan per-unit 10m/5kg;10m+5m→15m. Shares mixed quantity tidak dihitung silang unit; salesmoney tetap boleh dijumlah.

**Hubungan dengan catatan lain:** D4-WMS-03

## D4-CASH-01 — Saldo awal kas kecil berpindah menjadi kas besar setelah transaksi terakhir di-void

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/cash.py:103](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/cash.py#L103).



**Tampilan / rantai terkait:** Cash Dashboard: opening kas kecil/besar dan saldo · Bank/cash account opening → petty transactions → void → summary.

**Penyebab:** Jenis saldo awal ditentukan oleh account_id yang muncul pada transaksi kas kecil aktif. Master tidak memiliki field cash_type untuk klasifikasi tetap; void transaksi terakhir membuat account keluar dari kecil_ids.

**Dampak dan batas interpretasi:** Opening 1000 yang semula kas kecil menjadi kasbesar 1000 setelah transaksi 10 di-void, padahal opening master tidak berubah. Total cash bisa tetap benar namun split kategori salah.

- `D4-CASH-01-opening-reclass` — expected `{"before_kecil_opening": 1000, "after_kecil_opening": 1000, "after_besar_opening": 0}`; actual `{"before_kecil_opening": 1000.0, "after_kecil_opening": 0, "after_besar_opening": 1000.0}`; `observed_difference`.

```python
 100:     # Saldo = saldo awal rekening + masuk − keluar (dulu saldo awal diabaikan).
 101:     accounts = await db.bank_accounts.find({"entity_id": {"$in": list(entities)}},
 102:                                            {"_id": 0, "id": 1, "opening_balance": 1}).to_list(500)
 103:     kecil_ids = {r.get("account_id") for r in kecil_q if r.get("account_id")}
 104:     open_kecil = sum(float(a.get("opening_balance") or 0) for a in accounts if a["id"] in kecil_ids)
 105:     open_besar = sum(float(a.get("opening_balance") or 0) for a in accounts if a["id"] not in kecil_ids)
 106:     for eid, v in per_entity.items():
 107:         ob = sum(float(a.get("opening_balance") or 0) for a in accounts
 108:                  if a["id"] in kecil_ids and any(r.get("account_id") == a["id"] and r.get("entity_id") == eid for r in kecil_q))
 109:         v["balance"] = round(v["balance"] + ob, 2)
 110:     return {
```

**Prompt perbaikan:**

> Periksa `D4-CASH-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tetapkan account classification atau mapping eksplisit yang tidak bergantung ada/tidak transaksi. Rancang migration/legacy unknown; jangan menebak dari transaksi terkini atau mengarang field schema sudah ada. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Void/delete transaksi terakhir tidak mengubah jenis opening. Account tanpa transaksi, legacy tanpa mapping, beberapa entitas, cash deposit transfer dan preview compare harus konsisten.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-DASH-01 — Batas katalog 3.000 SKU masih menghilangkan master dan cadangan pada KPI

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/dashboard.py:37](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/dashboard.py#L37).



**Tampilan / rantai terkait:** Dashboard summary: total available dan product lookup · Product master → makloon reservation → dashboard ATP/availability.

**Penyebab:** Patch menaikkan batas master dari 100 ke3000. KPI balance menghitung semua 3003 SKU, tetapi pengurangan material reservation hanya menjelajah 3000 master yang dimuat. Respons tidak menyediakan continuation untuk master yang hilang.

**Dampak dan batas interpretasi:** Kasus 103 SKU sekarang PASS. Pada 3003 SKU ×10 dengan cadangan 8 yang sah pada SKU terakhir, KPI tersedia 30030 padahal seharusnya 30022; hanya 3000 master dikirim. Ini perbaikan parsial, bukan temuan cap 100 yang masih diklaim terbuka.

- `D4-DASH-01-master-window-reservation` — expected `850`; actual `850.0`; `pass`.
- `D4-DASH-01-master-completeness` — expected `103`; actual `103`; `pass`.
- `D4-DASH-01-latest-cap-master` — expected `3003`; actual `3000`; `observed_difference`.
- `D4-DASH-01-latest-cap-reservation` — expected `30022`; actual `30030.0`; `observed_difference`.

```python
  34:     # `apply_scope` hanya mengikat peran `sales`; sales_admin/finance/manager/
  35:     # admin/warehouse tetap melihat keseluruhan pesanan seperti sebelumnya.
  36:     order_scope = sales_ownership.apply_scope(scope, actor)
  37:     products_raw = await db.products.find({}, {"_id": 0}).to_list(3000)
  38:     # S#096 — HPP turunan pembelian (WAC roll) untuk layar Master Produk; diredaksi strip_cost_fields per peran.
  39:     from services import costing_service as _cs
  40:     for _p in products_raw:
  41:         try:
  42:             _w = await _cs.wac_for_product(_p["id"], product=_p)
  43:             _p["hpp"], _p["hpp_source"] = float(_w.get("wac") or 0), _w.get("source", "")
  44:         except Exception:  # noqa: BLE001
```

**Prompt perbaikan:**

> Periksa `D4-DASH-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Agregasi summary harus memakai seluruh scope yang sama dan sumber reservasi kanonis. Pagination untuk daftar tidak boleh mempengaruhi total. Uji semua bounded helper yang dipakai metrik. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Kasus 103 serta 3003 SKU lengkap lewat pagination/search yang benar; KPI 30022 dihitung independen dari window master. Uji juga lebih dari 5000 balance agar agregasi tidak bergantung batas client list.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-HR-01 — Payroll gabungan memakai satu run pada KPI dan menimpa run lain pada trend

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/hr_analytics_service.py:146](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_analytics_service.py#L146).



**Tampilan / rantai terkait:** HR Analytics: payroll cost, gross/net/BPJS/employee trend · Payroll runs perentity → grouped period → HR cards/charts.

**Penyebab:** KPI find_one(period); trend map period diberi assignment sehingga run berikut menimpa sebelumnya. Dua entitas dalam bulan sama tidak diaggregate.

**Dampak dan batas interpretasi:** RunA 100 +B200: kartu 100, trend 200, total seharusnya 300. Ini error analitik; probe tidak membuktikan GL payroll posting salah.

- `D4-HR-01-multi-run-trend` — expected `300`; actual `200.0`; `observed_difference`.
- `D4-HR-01-multi-run-kpi` — expected `300`; actual `100.0`; `observed_difference`.

```python
 143:     }
 144: 
 145:     # ── Payroll cost (run periode terpilih) + tren ──
 146:     run = await db.hr_payroll_runs.find_one({**pay_scope, "period": sel}, {"_id": 0})
 147:     t = (run or {}).get("totals", {}) or {}
 148:     payroll = {
 149:         "period": sel, "has_run": bool(run),
 150:         "status": (run or {}).get("status", ""),
 151:         "employees": int(t.get("employees") or 0),
 152:         "gross": round(float(t.get("gross") or 0), 0),
 153:         "net": round(float(t.get("net") or 0), 0),
```

**Prompt perbaikan:**

> Periksa `D4-HR-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Aggregate posted/eligible runs perperiod/selectedentity dengan lifecycle jelas, hindari menghitung draft+replacement ganda. Bedakan sum employees vs distinctpeople jika employee shared. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** All gross 300/net 270, A100/B200, chart=card. Draft/replaced/void run tidak double-count; BPJS/PPH dan employee basis diuji.

**Hubungan dengan catatan lain:** D4-HR-02

## D4-HR-02 — Turnover menggunakan waktu edit data sebagai waktu karyawan keluar

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/hr_analytics_service.py:136](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/hr_analytics_service.py#L136).



**Tampilan / rantai terkait:** HR Analytics: separations/turnover · Employee status transition → edit profile → turnover.

**Penyebab:** Inactive/resigned dihitung berdasarkan updated_at, bukan effective separation event. Schema saat ini tidak menyediakan termination_date yang kanonis; field tersebut pada probe hanya menjelaskan tanggal bisnis, bukan field publik yang diklaim sudah ada.

**Dampak dan batas interpretasi:** Karyawan keluarbulanJuli tetapi profil dieditOktober dianggap separasiOktober. Ini gap sumber data/definition, bukan sekadar salah operator.

- `D4-HR-02-separation-date` — expected `0`; actual `1`; `observed_difference`.

```python
 133: 
 134:     # ── Turnover (separations = status non-active pada periode; new hires periode) ──
 135:     separations = sum(1 for e in employees if (e.get("status") or "active") != "active"
 136:                       and (e.get("updated_at") or "")[:7] == sel)
 137:     hires_period = sum(1 for e in active if _join(e)[:7] == sel)
 138:     base_hc = len(active) or 1
 139:     turnover = {
 140:         "period": sel, "separations": separations, "headcount": len(active),
 141:         "new_hires": hires_period,
 142:         "turnover_rate": round(separations / base_hc * 100, 1),
 143:     }
```

**Prompt perbaikan:**

> Periksa `D4-HR-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tambahkan effective status-transition/separationdate dengan audit history dan backfill yang eksplisit. Perubahan profil tidak mengubah tanggal keluar. Definisikan numerator/denominator turnover. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** KeluarJuli lalu editOktober: Juli 1, Oktober 0. Rehire, koreksi status, delete/archival dan transferentity memiliki treatment terdefinisi.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-01 — RFID RED hari ini pada Warehouse Health memakai hari UTC

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/wms_health_service.py:28](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L28).



**Tampilan / rantai terkait:** Warehouse Health: red_reads_today · RFID timestamp UTC → business day WIB → health card.

**Penyebab:** Filter today memakai prefix tanggal UTC. Operasi gudang lokal menggunakan WIB sehingga antara 00:00–06:59 WIB hari bisnis berbeda.

**Dampak dan batas interpretasi:** Freeze 01Oct01:00WIB: read 30Sept23:00WIB dihitung hariini. Dua read menghasilkan 2, seharusnya hanya 1.

- `D4-WMS-01-wib-day` — expected `1`; actual `2`; `observed_difference`.

```python
  25:         "last_cc": None, "devices_total": 0, "devices_stale": 0,
  26:     } for w in whs}
  27: 
  28:     today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
  29:     async for r in db.rfid_incidents.aggregate([
  30:             {"$match": {"status": "open"}},
  31:             {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}]):
  32:         if r["_id"] in rows:
  33:             rows[r["_id"]]["open_incidents"] = r["n"]
  34:     async for r in db.rfid_reads.aggregate([
  35:             {"$match": {"result": "red", "timestamp": {"$gte": today},
```

**Prompt perbaikan:**

> Periksa `D4-WMS-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan range [WIBdaystart, nextdaystart) dikonversi UTC. Jangan memakai regex prefix date atau mencampur string timestamp offset berbeda. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 23:59WIB yesterday excluded;00:00/06:59 todayincluded; timezone UTC/Z/offsetnormalized. Chart dan KPI memakai satu batas hari bisnis.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-02 — Cycle count terbaru yang belum selesai menghapus angka akurasi terakhir

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/wms_health_service.py:71](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L71).



**Tampilan / rantai terkait:** Warehouse Health: last cycle count / accuracy · Cycle count open → assessed/approved → warehouse health.

**Penyebab:** Service memilih dokumen terbaru tanpa mensyaratkan accuracy valid/status selesai dan tidak mengirim status. Frontend memasang suffix% walau accuracy tidak ada.

**Dampak dan batas interpretasi:** Count terukur 95%, lalu count baruopen: last_cc memilihopen tanpa angka. Hasilnya angka akurasi hilang/placeholder ambigu, bukan bukti 0% ditampilkan.

- `D4-WMS-02-last-measured-cc` — expected `"CCOK"`; actual `"CCOPEN"`; `observed_difference`.

```python
  68:             {"$group": {"_id": "$warehouse_id", "doc": {"$first": "$$ROOT"}}}]):
  69:         if cc["_id"] in rows:
  70:             d = cc["doc"]
  71:             rows[cc["_id"]]["last_cc"] = {"cc_number": d.get("cc_number"),
  72:                                           "accuracy_pct": d.get("accuracy_pct"),
  73:                                           "missing_count": d.get("missing_count"),
  74:                                           "at": d.get("created_at")}
  75:     now = datetime.now(timezone.utc)
  76:     async for d in db.rfid_devices.find({}, {"_id": 0, "warehouse_id": 1,
  77:                                              "last_heartbeat": 1, "status": 1}):
  78:         if d.get("warehouse_id") not in rows:
```

**Prompt perbaikan:**

> Periksa `D4-WMS-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan latestcountstatus dan lastmeasuredaccuracy. Pilih count terukur sesuai lifecycle bisnis (bukan secara arbitrer selaluapproved) dan tampilkan N/A untuk belum dinilai. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Openbaru tidak menimpa lastmeasured 95%; UI menunjukkan statusopen. Measured 0% harus tetap 0% dan dibedakan darinull; rejected/void count tidak dijadikan valid measurement.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-WMS-03 — Utilisasi gudang mengabaikan struktur Rack→Level→Bin yang didukung master

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/reporting.py:203](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/reporting.py#L203).



**Tampilan / rantai terkait:** Manager Dashboard: warehouse capacity/utilization · Warehouse structure → location flattening → capacity dashboard.

**Penyebab:** Producer warehouse_structure menyimpan bins di rack.levels[].bins. Consumer reporting hanya rack.bins legacy, sehingga capacity 0 dan utilization 0 meski lokasi punya capacity.

**Dampak dan batas interpretasi:** Struktur dibuat melalui helperoriginal: warehouse_locations capacity 100; /reports/warehouse-utilization capacity 0. Dapat menyamarkan penuh/tidaknya gudang.

- `D4-WMS-03-level-capacity` — expected `{"locations": 100, "manager_report": 100}`; actual `{"locations": 100.0, "manager_report": 0.0}`; `observed_difference`.

```python
 200:         total_capacity = 0.0
 201:         for zone in warehouse.get("zones", []):
 202:             for rack in zone.get("racks", []):
 203:                 for bin_ in rack.get("bins", []):
 204:                     total_capacity += float(bin_.get("capacity", 0))
 205:         bal_scope = resolve_list_scope(
 206:             "inventory_balances", {"warehouse_id": warehouse["id"]}, ctx, entity_id)
 207:         balances = await db.inventory_balances.find(bal_scope, {"_id": 0}).to_list(1000)
 208:         on_hand_total = sum(float(b.get("on_hand_qty", 0)) for b in balances)
 209:         reserved_total = sum(float(b.get("reserved_qty", 0)) for b in balances)
 210:         available_total = sum(float(b.get("available_qty", 0)) for b in balances)
```

**Prompt perbaikan:**

> Periksa `D4-WMS-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Reuse canonical location traversal yang mendukung legacy dan level. Tegaskan unit kapasitas dan pisahkan mixedunitstock; jangan membagi meter+kg terhadap denominator yang tidak jelas. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Rack→Level→Bins 100 tampilcapacity 100; legacyrack.bins tetap benar dan tidak dihitungdua kali. Multiunit/capacity 0/owner shares/locationinactive diuji.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-MKT-01 — Reach agregat post disajikan ulang sebagai reach tiap platform dan akun

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** runtime_metric_definition.

**Letak:** [backend/services/marketing_ext.py:137](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/marketing_ext.py#L137).



**Tampilan / rantai terkait:** Marketing Dashboard: by_platform dan by_account · Post multi-platform → aggregate metrics → channel breakdown.

**Penyebab:** Satu metrics aggregate post ditambahkan penuh ke setiap platform/account. Tidak ada pengukuran per-channel tersimpan, sehingga channel reach bukan actual channel measurement. Kelompok overlapping boleh nonadditive hanya bila kontraknya jelas.

**Dampak dan batas interpretasi:** Post reach 100 padaIG+TikTok: KPI 100, jumlahbyplatform 200 dan byaccount 200. Jangan menebak channel reach 50/50; data actual belum tersedia.

- `D4-MKT-01-attribution-conservation` — expected `{"total_reach": 100, "platform_reach_sum": 100, "account_reach_sum": 100}`; actual `{"total_reach": 100.0, "platform_reach_sum": 200.0, "account_reach_sum": 200.0}`; `observed_difference`.

```python
 134:         rows = [r for r in six if (r.get("publish_at") or "")[:7] == mm]
 135:         k = _kpi(rows)
 136:         trend.append({"month": mm, "label": f"{MONTHS_ID[int(mm[5:7]) - 1][:3]} {mm[2:4]}", "posts": k["posts"], "published": k["published"], "reach": k["reach"], "engagement": k["engagement"]})
 137:     by_platform: Dict[str, Dict[str, Any]] = {}
 138:     by_account: Dict[str, Dict[str, Any]] = {}
 139:     by_entity: Dict[str, Dict[str, Any]] = {}
 140:     for r in cur:
 141:         pub = r["status"] == "published"; mt = r.get("metrics") or {}
 142:         for pl in r.get("platforms") or []:
 143:             b = by_platform.setdefault(pl, {"posts": 0, "published": 0, "reach": 0.0, "engagement": 0.0, "clicks": 0.0})
 144:             b["posts"] += 1
```

**Prompt perbaikan:**

> Periksa `D4-MKT-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan apakah breakdown merupakan shared post attribution atau measurement perchannel. Jika shared, label nonadditive dan jangan total ulang. Jika actual, simpan metrics perplatform/account dengan provenance/time dan aggregate dedup sesuai definisi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Postmulti-channel 100 tidak ditampilkan seolah masing-masingpunya actual 100 tanpa keterangan. Separate metrics 30/70 hanya jika benar-benar diukur. Reachunique crosschannel tidak disimpulkan dari penjumlahan biasa.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-RND-01 — KPI R&D menggabungkan orang berbeda yang mempunyai nama sama

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/rnd_kpi_service.py:153](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rnd_kpi_service.py#L153).



**Tampilan / rantai terkait:** R&D designer/MD KPI, approval performance · Round performer identity → names → KPI groups.

**Penyebab:** Round producer menyimpan performed_by_user_id, tetapi KPI memakai performed_by/opened_by/created_by displayname sebagai identity. Dua user dengan nama sama menjadi satu baris.

**Dampak dan batas interpretasi:** Dua round dengan U1 danU 2 sama displayname menghasilkan 1 pelaksana, seharusnya 2. Nama berubah juga dapat memecah histori orang yang sama.

- `D4-RND-01-person-identity` — expected `2`; actual `1`; `observed_difference`.

```python
 150:     return max((today - due).days, 0)
 151: 
 152: 
 153: def designer_of(sample: Dict[str, Any], rd: Dict[str, Any]) -> str:
 154:     """Penanggung jawab round — lihat catatan desain di docstring modul."""
 155:     for cand in (rd.get("performed_by"), rd.get("opened_by"), sample.get("created_by")):
 156:         name = str(cand or "").strip()
 157:         if name:
 158:             return name
 159:     return "(tanpa nama)"
 160: 
```

**Prompt perbaikan:**

> Periksa `D4-RND-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Group stable user_id/employee_id dan render displayname sebagai label. Legacy name-only perlu mapping ambiguity explicit, bukan autojoin semua nama. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** U1/U2 nama sama→2KPI; U1 ganti nama→1 history. Fallbacklegacyambiguous ditandai, customroleline/roundtypefilter tetap berlaku.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FE-01 — Grafik velocity Manager selalu memotong menjadi 14 hari

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:100](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/manager/ManagerDashboard.jsx#L100).



**Tampilan / rantai terkait:** Manager Dashboard: periode 7/30/90 vs velocity chart · Period selector → reporting velocity → frontend slicing.

**Penyebab:** Dataset velocity dari API dipotong slice(-14) tanpa mengikuti period pilihan.

**Dampak dan batas interpretasi:** JavaScript asli expression diuji: input 7 tampil 7(control), input 30/90 masing-masing 14. Judul/periode dapat memberikan kesan dataset lengkap.

- `D4-FE-01-chart-7` — expected `7`; actual `7`; `pass`.
- `D4-FE-01-chart-30` — expected `30`; actual `14`; `observed_difference`.
- `D4-FE-01-chart-90` — expected `90`; actual `14`; `observed_difference`.

```javascript
  97:   useEffect(() => { load(); }, [period, agingDays, selectedEntity]);
  98: 
  99:   const funnelChartData = (funnel?.funnel || []).filter(f => !["cancelled", "expired"].includes(f.status));
 100:   const velocityData = (velocity?.velocity || []).slice(-14); // last 14 days
 101:   const utilizationData = utilization.map(w => ({
 102:     name: w.warehouse_city || w.warehouse_name,
 103:     on_hand: w.on_hand_qty,
 104:     capacity: w.total_capacity,
 105:     pct: w.utilization_pct,
 106:   }));
 107: 
```

**Prompt perbaikan:**

> Periksa `D4-FE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan range period yang sama dengan request atau label 14 hari terakhir secara eksplisit jika itu tujuan grafik. Jangan memotong data tanpa indikasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Periode 7/30/90 menunjukkan dataset sesuai tanggalpilihan; emptydays tetapkontrak API, batas tanggal/label tooltip diperiksa diUI.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-FE-02 — Respons periode lama dapat menimpa grafik setelah periode diganti

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [frontend/src/features/manager/ManagerDashboard.jsx:69](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/manager/ManagerDashboard.jsx#L69).



**Tampilan / rantai terkait:** Manager Dashboard → pilihan periode / aging days pada entitas yang sama · Period 30 → period 90 → concurrent API load → old 30 response → React state.

**Penyebab:** load/useEffect tidak membatalkan request lama atau menjaga generation. Pergantian periode tidak remount komponen; request 30 yang selesai setelah 90 menulis ulang data. App.js L528 memakai key selectedEntity, sehingga hipotesis awal pergantian entitas ditarik: probe lama melewati remount.

**Dampak dan batas interpretasi:** Original function load pada entitas A: respons periode 90 selesai dan field total_orders yang dipakai UI bernilai 90; respons periode 30 selesai belakangan lalu total_orders menjadi 30 saat pilihan masih 90. Bukti ini JavaScript function-level dengan transport terkontrol, bukan browser E2E. Klaim entity-overwrite pada draf historis tidak dipakai sebagai temuan.

- `D4-FE-02-after-current-period-response` — expected `90`; actual `90`; `pass`.
- `D4-FE-02-stale-period-overwrite` — expected `90`; actual `30`; `observed_difference`.

```javascript
  66: 
  67:   const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
  68: 
  69:   const load = async () => {
  70:     setLoading(true);
  71:     // F0-E: laporan ter-scope per entitas aktif ('all' = oversight lintas-PT).
  72:     const ent = selectedEntity || "all";
  73:     const cfg = { headers, params: { entity_id: ent } };
  74:     try {
  75:       const [sumRes, funnelRes, velRes, custRes, utilRes, agingRes] = await Promise.all([
  76:         axios.get(`${API}/reports/summary`, cfg),
```

**Prompt perbaikan:**

> Periksa `D4-FE-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Implement generation guard/AbortController yang melindungi seluruh setters termasuk loading/error pada pergantian periode, aging days dan refresh. Data beberapa endpoint harus satu request generation. Pertahankan remount entitas yang sudah ada; audit pola halaman lain dengan bukti terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Pada entitas sama, period 30→90 dan respons out-of-order: grafik tetap 90; respons/error/finally 30 tidak mengubah state 90. Uji aging-days, refresh, unmount dan partial failure. Uji browser diperlukan untuk validasi rendered UI.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-TEST-01 — Tes konsistensi ATP dapat lulus walaupun mencatat mismatch

**Prioritas:** P2 · **Status:** open_definition_or_test_gap · **Bukti:** source_review_test_oracle.

**Letak:** [backend/tests/test_iter149_audit.py:116](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/tests/test_iter149_audit.py#L116).



**Tampilan / rantai terkait:** Verification pipeline / ATP oracle · Inventory report → old regression test → green status.

**Penyebab:** test_stock_atp_sum_matches mengumpulkan bad_row/bad_wh dan menulis/print hasil tanpa assert terakhir yang menolak mismatch. Formula lama juga perlu diselaraskan dengan pendingdemandyang didokumentasikan.

**Dampak dan batas interpretasi:** Green test ini hanya membuktikanHTTP/listshape, bukan ATPformula benar. test_iter150 memilikiassert yang lebihbermakna sehingga perbaikannya harus menghindari oracle lama yangsalah.

**Observasi:** {}

```python
 113:     assert r.status_code == 200, r.text
 114:     rows = r.json()
 115:     assert isinstance(rows, list)
 116:     bad_row = []
 117:     bad_wh = []
 118:     for row in rows:
 119:         av = float(row.get('total_available') or 0)
 120:         inc = float(row.get('total_incoming') or 0)
 121:         rsv = float(row.get('total_reserved') or 0)
 122:         atp = float(row.get('total_atp') or 0)
 123:         expected = av + inc - rsv
```

**Prompt perbaikan:**

> Periksa `D4-TEST-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan formulaavailability/ATP bersama timbisnis, buat independentoracle dengan fixture partialreserve/hold/pending/incoming. Tambahkan assertionmismatch dan test-negatif yangmemastikanoracle gagal terhadapmutasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** InjectwrongATP→testFAIL; correctformula→PASS. Uji fixture>100SKU, multiowner, pendingcut, externalincoming dan no-dependencydemoaccount.

**Hubungan dengan catatan lain:** Tidak dipetakan ke ID lama; jangan menganggap bebas dampak ke modul lain.

## D4-DATE-01 — Penjualan dan Home menggunakan bulan/tahun UTC yang berbeda dari periode bisnis WIB

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_force_service.py:27](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L27).



**Tampilan / rantai terkait:** Sales KPI, commission period/history, Home periode default; consumer tanggal serupa perlu ditelusuri · UTC created_at/payment timestamp → period selection → target/commission/report.

**Penyebab:** _in_period memotong tanggal string tanpa konversi timezone. Home _current_month/_today_prefix juga memakai UTC. Transaksi normal pada tujuh jam pertama WIB di awal bulan/tahun dapat masuk periode sebelumnya. Analytics engine memiliki konversi WIB tersendiri, sehingga metrik antarmodul dapat berbeda.

**Dampak dan batas interpretasi:** Timestamp 30Sep18:00UTC adalah 01Oct01:00WIB: filterOctoberFalse, SeptemberTrue. Home defaultmasihSeptember/30Sep. Timestamp 31Dec18:00UTC ditolak dariyear 2027 meski tanggalbisnis 01Jan2027. Belum semua consumer polaUTC ini diuji runtime; jangan menganggap semuanya sudahconfirmed.

- `D4-DATE-01-home-default` — expected `{"month": "2026-10", "day": "2026-10-01"}`; actual `{"month": "2026-09", "day": "2026-09-30"}`; `observed_difference`.
- `D4-DATE-01-month-inclusion` — expected `true`; actual `false`; `observed_difference`.
- `D4-DATE-01-prior-month` — expected `false`; actual `true`; `observed_difference`.
- `D4-DATE-01-year-inclusion` — expected `true`; actual `false`; `observed_difference`.

```python
  24:     """Cocokkan created_at dengan periode: YYYY-MM (bulan), YYYY-Qn (kuartal), YYYY (tahun)."""
  25:     if not period:
  26:         return True
  27:     v = str(value or "")[:10]
  28:     if len(v) < 7:
  29:         return False
  30:     ym, yr = v[:7], v[:4]
  31:     p = str(period).upper()
  32:     if "-Q" in p:
  33:         try:
  34:             py, q = p.split("-Q")
```

**Prompt perbaikan:**

> Periksa `D4-DATE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan timezone bisnis/per-entity dan gunakan helper periode bersama untuk timestamp serta date-only. Buat range UTC dari batas periode WIB. Jangan hanya mengubah bulan default Home sementara filterSO/payment masih memotong stringUTC. Telusuri profitability monthly grouping dan Finance Tower period sebagai related static candidates. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Batas 23:59:59WIB dan 00:00WIB di awalbulan, kuartal dan tahun masuk periodeyangbenar; timestamp Z/+00/+07 serta date-only memiliki aturanjelas. KPI, target, commissionhistory, snapshot dan export pada filter sama harusrekonsiliasi.

**Hubungan dengan catatan lain:** D4-WMS-01, V3-DATE-01, D4-FIN-04

## D4-PLAN-01 — Rencana pembelian mencatat qty yang berbeda dari PR yang dirujuk

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/fulfillment_plan_service.py:133](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L133).



**Tampilan / rantai terkait:** Admin Sales → Rencana pemenuhan → riwayat dan qty sudah direncanakan · SO backorder → partial reorder → PR → keputusan ulang → rencana supply.

**Penyebab:** Helper lama menegaskan ulang PR yang masih terbuka berdasarkan product_id tanpa menambah qty. Planner baru tetap menulis qty permintaan sebagai qty pembelian baru dan _planned menjumlahkan setiap keputusan.

**Dampak dan batas interpretasi:** Kekurangan 100: keputusan awal membuat PR20. Keputusan berikut meminta 80, menunjuk PR20 yang sama, namun mencatat 80; planned_qty menjadi 100 sementara pasokan PR hanya 20. Tidak ada bukti PR kedua lahir dalam kasus sequential ini.

- `D4-PLAN-01-reaffirmed-qty` — expected `{"decision_qty": 20, "referenced_pr_qty": 20}`; actual `{"decision_qty": 80.0, "referenced_pr_qty": 20.0}`; `observed_difference`.
- `D4-PLAN-01-planned-conservation` — expected `20`; actual `100.0`; `observed_difference`.

```python
 130:                          "summary": f"{r['product_name']}: {r['backorder_qty']:g} transfer dari PT lain ({res.get('ref_number') or '-'})"})
 131:     rows = [_row(ln, ln["reorder"]) for ln in plan if ln["reorder"] > EPS]
 132:     if rows:
 133:         res = await fds._reorder_supplier(order, rows, actor, note)
 134:         for r in rows:
 135:             done.append({"mode": "reorder", "product_id": r["product_id"], "qty": r["backorder_qty"],
 136:                          "ref_type": res.get("ref_type"), "ref_id": res.get("ref_id"), "ref_number": res.get("ref_number"),
 137:                          "summary": f"{r['product_name']}: {r['backorder_qty']:g} PO ke supplier ({res.get('ref_number') or '-'})"})
 138:     for ln in plan:
 139:         if ln["wait"] > EPS:
 140:             done.append({"mode": "wait", "product_id": ln["product_id"], "qty": ln["wait"],
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan reaffirmation dari penambahan supply; pakai qty efektif dan per-line reference aktual. Jika perlu tambah 80, lakukan amendment atau PR delta terkontrol. Rekonsiliasikan planned_qty dari supply aktif per referensi unik, bukan penjumlahan narasi histori. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PR20 lalu permintaan 80 tidak boleh memberi kesan supply 100 bila PR tetap 20. Reaffirm 20 berulang tidak meningkatkan planned_qty. Cancel/convert/receive/amend PR harus memperbarui remaining supply; uji multi-SKU saat sebagian SKU sudah punya PR.

**Hubungan dengan catatan lain:** D4-PLAN-03, D4-PLAN-05

## D4-PLAN-02 — Baris produk ganda pada API rencana dapat membuat pembelian melebihi kekurangan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/fulfillment_plan_service.py:76](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L76).



**Tampilan / rantai terkait:** API pemenuhan; PR turunan yang dibuka MD · FulfillmentPlanIn.lines → _validate per baris → supplier PR.

**Penyebab:** Validasi mengecek setiap raw row terhadap shortage yang sama. Tidak ada unique product guard atau akumulasi total lintas baris. Dua row 100 masing-masing lolos pada shortage 100.

**Dampak dan batas interpretasi:** Service asli membuat satu PR berisi 200 untuk demand 100. UI normal mengirim satu baris per produk, tetapi schema dan router publik menerima list dengan duplikasi; qty guard tidak berlaku pada total efektif.

- `D4-PLAN-02-duplicate-product` — expected `100`; actual `200.0`; `observed_difference`.

```python
  73: def _validate(lines_in: List[Dict[str, Any]], opts: Dict[str, Any]) -> List[Dict[str, Any]]:
  74:     by_pid = {ln["product_id"]: ln for ln in opts["lines"]}
  75:     plan = []
  76:     for raw in lines_in or []:
  77:         ln = by_pid.get(raw.get("product_id"))
  78:         if not ln:
  79:             raise FulfillmentError("Barang ini tidak (lagi) punya kekurangan di pesanan — muat ulang.")
  80:         nm = ln["product_name"] or ln["product_id"]
  81:         stock = round(float(raw.get("stock_qty") or 0), 2)
  82:         reorder = round(float(raw.get("reorder_qty") or 0), 2)
  83:         wait = round(float(raw.get("wait_qty") or 0), 2)
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tolak duplikasi product_id atau gabungkan baris sebelum memvalidasi kapasitas/demand. Akumulasikan pula per product + source entity dan validasi finite positive quantities. Jangan memindahkan guard hanya ke UI. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Duplicate product 100+100 ditolak tanpa side effect; duplicate source allocations juga tidak melewati batas. Uji semua endpoint planner dan PR realization; request invalid tidak membuat PR/transfer/reservation.

**Hubungan dengan catatan lain:** D4-PLAN-01

## D4-PLAN-03 — Riwayat mengatakan pemenuhan penuh walaupun sebagian eksekusi gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/fulfillment_plan_service.py:160](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L160).



**Tampilan / rantai terkait:** Admin Sales → Riwayat keputusan / scope · Stock fulfillment → interco failure → persisted decision → UI notification.

**Penyebab:** full dihitung dari seluruh qty permintaan pada plan, setelah _execute menangkap kegagalan yang hanya menyelesaikan sebagian done. Qty yang gagal tetap berkontribusi pada scope full.

**Dampak dan batas interpretasi:** Rencana stock 30 + interco 70 untuk 100: stock 30 berhasil, interco 70 ditolak karena kontrak internal belum tersedia. SO menyimpan parts 30 tetapi scope full dan summary Penuh. Tidak diklaim barang 100 sudah terkirim; kesalahannya pada state/riwayat pemenuhan.

- `D4-PLAN-03-partial-scope` — expected `{"scope": "partial", "actual_qty": 30}`; actual `{"scope": "full", "actual_qty": 30.0}`; `observed_difference`.

```python
 157:             raise
 158:         error = str(exc)
 159:     modes = {p["mode"] for p in done}
 160:     full = all(abs((ln["stock"] + ln["reorder"] + ln["wait"] + sum(x["qty"] for x in ln["interco"]))
 161:                    - ln["backorder_qty"]) <= EPS for ln in plan) and len(plan) == len(opts["lines"])
 162:     decision = {
 163:         "mode": next(iter(modes)) if len(modes) == 1 else "split",
 164:         "scope": "full" if full else "partial",
 165:         "by": actor.get("name", ""), "by_id": actor.get("id", ""), "by_role": actor.get("role", ""),
 166:         "at": now_iso(), "note": (note or "").strip()[:400],
 167:         "summary": ("Penuh" if full else "Sebagian") + " — " + "; ".join(p["summary"] for p in done),
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Hitung execution outcome dari hasil nyata tiap bagian; pisahkan planned coverage dari executed coverage. Simpan per-part succeeded/failed/pending beserta effective qty dan reference. Kegagalan parsial harus dapat dilanjutkan tanpa menjalankan ulang bagian yang sukses. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fixture stock 30/interco 70 fail mencatat partial 30, sisa 70 belum terpenuhi, dan error tetap terlihat. Retry hanya menjalankan sisa. Uji exception infrastruktur, failure sebelum record, dan zero actual stock setelah concurrent consumption.

**Hubungan dengan catatan lain:** D4-PLAN-04, D4-BACKORDER-01

## D4-PLAN-04 — Pesan kegagalan pemenuhan parsial terhapus oleh refresh otomatis

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** javascript_function_counterexample.

**Letak:** [frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx:59](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx#L59).



**Tampilan / rantai terkait:** Dialog Rencana pemenuhan: ErrorNotice · POST partial failure → catch error → load GET → setError empty.

**Penyebab:** submit menaruh pesan error lalu memanggil load; saat GET sukses load menjalankan setError kosong sehingga pesan kegagalan dan informasi bagian yang telah diproses hilang.

**Dampak dan batas interpretasi:** Function asli menghasilkan error transitions kosong → Interco failed; stock 30 already executed → kosong. Operator kehilangan pesan penting sebelum melanjutkan. Bukti ini function-level JavaScript dengan transport terkontrol, bukan uji browser.

- `D4-PLAN-04-error-erased` — expected `"Interco failed; stock30 already executed and persisted"`; actual `""`; `observed_difference`.

```javascript
  56:       };
  57:       const res = await fulfillmentPlanDecide(orderId, body);
  58:       onDecided?.(`${res?.order_number || orderNumber}: ${res?.decision?.summary || "rencana pemenuhan tercatat."}`);
  59:     } catch (e) { setError(apiErrorText(e, "Gagal menjalankan rencana pemenuhan.")); load(); }
  60:     finally { setBusy(false); }
  61:   }
  62: 
  63:   return (
  64:     <div className="modal-overlay" data-testid="fulfill-dialog" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
  65:       <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 920, maxHeight: "92vh", overflowY: "auto" }}>
  66:         <div className="flex flex-wrap items-start justify-between gap-2">
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan load error dari execution error dan pertahankan hasil partial sampai pengguna menutupnya. Refresh data tidak boleh menghapus pesan proses yang belum diakui. Jelaskan bagian sukses, gagal dan tindakan lanjutan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** POST gagal parsial lalu GET sukses tetap menampilkan pesan dan bagian 30 yang sukses. GET gagal harus menampilkan kedua konteks dengan jelas. Lengkapi browser test tanpa mengubah oracle.

**Hubungan dengan catatan lain:** D4-PLAN-03, D4-FE-02

## D4-PLAN-05 — Pasokan masuk yang sama dapat direncanakan penuh untuk beberapa SO

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/fulfillment_plan_service.py:139](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L139).



**Tampilan / rantai terkait:** Rencana tunggu barang datang dan Pending SO coverage · PO incoming → pending SO matching → wait decision → janji pelanggan.

**Penyebab:** pending_so_board mencocokkan incoming penuh secara independen untuk tiap demand. Jalur wait pada planner hanya menambah narasi parts; tidak mencadangkan qty pasokan per PO/SO atau mengurangi remaining supply yang ditawarkan.

**Dampak dan batas interpretasi:** Satu PO100 dianggap tersedia untuk dua SO100; kedua keputusan wait 100 berhasil dan total rencana 200. Bila fitur hanya catatan indikatif, label penuh/covered dan janji harus diperbaiki; jangan menyamakan perkiraan dengan pasokan yang dialokasikan.

- `D4-PLAN-05-wait-supply-conservation` — expected `100`; actual `200.0`; `observed_difference`.

```python
 136:                          "ref_type": res.get("ref_type"), "ref_id": res.get("ref_id"), "ref_number": res.get("ref_number"),
 137:                          "summary": f"{r['product_name']}: {r['backorder_qty']:g} PO ke supplier ({res.get('ref_number') or '-'})"})
 138:     for ln in plan:
 139:         if ln["wait"] > EPS:
 140:             done.append({"mode": "wait", "product_id": ln["product_id"], "qty": ln["wait"],
 141:                          "promise_date": ln["promise_date"],
 142:                          "summary": f"{ln['product_name']}: {ln['wait']:g} tunggu barang datang"
 143:                                     + (f" (janji {str(ln['promise_date'])[:10]})" if ln["promise_date"] else "")})
 144: 
 145: 
 146: async def decide_plan(order_id: str, lines_in: List[Dict[str, Any]], actor: Dict[str, Any],
```

**Prompt perbaikan:**

> Periksa `D4-PLAN-05` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bentuk pegging supply/demand per document line dengan remaining qty, entity, unit dan ETA, atau labelkan sebagai availability forecast non-exclusive. Untuk janji pemenuhan pasti, validasi dan claim supply harus atomik serta reversible. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PO100 dan dua SO100 hanya mengalokasikan 100 total. SO kedua menyisakan shortage 100 atau forecast yang jelas tidak dijamin. Receive/cancel/amend/reorder/transfer harus merekonsiliasi claim tanpa menjanjikan supply dua kali.

**Hubungan dengan catatan lain:** D4-SUPPLY-01, D4-PLAN-01

## D4-GLOBAL-01 — Barang datang 100 yard dilabelkan 100 meter pada katalog stok global

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/sales_stock_service.py:44](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_stock_service.py#L44).



**Tampilan / rantai terkait:** POS desktop/mobile → Datang restock / Datang utk SO · PO document UOM → canonical conversion trail → global stock helper → product card base_unit.

**Penyebab:** apply_global menjumlahkan quantity dan received_qty dokumen secara mentah. Consumer memberi label product.base_unit. quantity_base/uom_trail yang benar dari producer PO tidak dipakai.

**Dampak dan batas interpretasi:** Public POST /purchase-orders menghasilkan quantity 100 yard dan quantity_base91.44 meter. Badge global mengembalikan incoming_restock_qty100, ditampilkan sebagai meter. Konversi producer benar; sumber angka consumer salah.

- `D4-GLOBAL-01-incoming-uom` — expected `91.44`; actual `100.0`; `observed_difference`.

```python
  41:             pid = it.get("product_id")
  42:             if pid not in idset:
  43:                 continue
  44:             open_qty = float(it.get("quantity", it.get("qty", 0)) or 0) - float(it.get("received_qty", 0) or 0)
  45:             if open_qty > 0.01:
  46:                 tgt = inc_so if (bound or it.get("source_so_id")) else inc_rs
  47:                 tgt[pid] = tgt.get(pid, 0.0) + open_qty
  48:     async for d in db.interco_transactions.find({"role": "buyer", "status": {"$in": INCOMING_INTERCO_STATUSES},
  49:                                                  "items.product_id": {"$in": ids}},
  50:                                                 {"_id": 0, "items": 1, "source_order_id": 1}):
  51:         for it in d.get("items") or []:
```

**Prompt perbaikan:**

> Periksa `D4-GLOBAL-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan outstanding dalam satuan dasar dari conversion trail producer dan konversi received quantity dengan unit yang sama. Terapkan ke SO-bound/restock, PO manual/PR/call-off dan interco. Jangan memakai angka fallback 1 untuk unit yang tidak bisa dikonversi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PO100 yard pada SKU meter → incoming 91.44 meter; setelah menerima 40 yard → remaining 54.864 meter sesuai presisi kanonis. Uji kg/gram, roll dengan document factor, landed/cost tidak tercampur qty, dan semua badge mobile/desktop.

**Hubungan dengan catatan lain:** D4-AI-06, D4-SUPPLY-01

## D4-SUPPLY-01 — Sisa PO diterima sebagian hilang dari incoming karena definisi status berbeda

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/roll_service.py:173](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L173).



**Tampilan / rantai terkait:** ATP, Pending SO, global POS incoming dan saran pengadaan · PO receipt → recompute_po_status partial → shared OPEN_PO_STATUSES → incoming supply.

**Penyebab:** Producer recompute_po_status menetapkan partial untuk PO yang baru diterima sebagian. OPEN_PO_STATUSES yang diimpor stock_bucket_service dan sales_stock_service tidak memasukkan partial. Normalisasi status tidak mengikuti state machine kanonis.

**Dampak dan batas interpretasi:** PO100 diterima 90: original recompute menghasilkan partial. Pending supply dan global incoming keduanya 0 padahal tersisa 10. Janji ke customer dan keputusan pembelian ulang dapat salah. Jalur _open_po_incoming juga membaca qty total pada status terbuka lain, perlu uji sisa, bukan sekadar memasukkan partial.

- `D4-SUPPLY-01-open-qty` — expected `10`; actual `0`; `observed_difference`.
- `D4-SUPPLY-01-global-partial` — expected `10`; actual `0.0`; `observed_difference`.

```python
 170: # KN-A11 — SATU definisi "PO masih terbuka / stok dalam perjalanan" untuk papan Stok/ATP,
 171: # Fulfillment Wizard, dan stock_bucket. `waiting_approval` sengaja TIDAK dihitung (belum
 172: # pasti dibeli); `receiving` dihitung karena sisa yang belum diterima memang masih di jalan.
 173: OPEN_PO_STATUSES = ["pending", "created", "approved", "sent", "receiving"]
 174: 
 175: PHYSICAL_STATUS_TO_BUCKET = {
 176:     "available": "available_qty",
 177:     "reserved": "reserved_qty",
 178:     "committed": "committed_qty",
 179:     "picked": "picked_qty",
 180:     "packed": "packed_qty",
```

**Prompt perbaikan:**

> Periksa `D4-SUPPLY-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Satukan definisi status open dengan producer lifecycle; hitung remaining qty dalam unit dasar, bukan ordered qty. Review seluruh importer OPEN_PO_STATUSES dan pembelian/GRN/reorder/forecast/ATP, dengan guard terminal dan tolerance policy. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PO100 received 90 → incoming 10; received 100/completed →0; closed_short/cancelled/rejected →0; receiving legacy tidak menambah seluruh ordered qty. Uji partial receipt, variance amend/close dan qty per roll.

**Hubungan dengan catatan lain:** V3-PO-01, V3-PO-02, D4-GLOBAL-01, D4-PLAN-05

## D4-BACKORDER-01 — Pemenuhan stok bersamaan mereservasi 160 untuk SO yang hanya kurang 100

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/backorder_service.py:82](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/backorder_service.py#L82).



**Tampilan / rantai terkait:** SO detail reserved/backorder, rencana pemenuhan, roll availability dan picking · Two admin stock fills → roll CAS reservations → stale whole SO arrays → allocations push.

**Penyebab:** Roll allocator menjaga stok fisik per roll, tetapi _fill_order tidak mengunci demand/version SO. Dua proses membaca shortage 100 yang sama, masing-masing reserve 80; $push mempertahankan allocations 160 sedangkan $set items/backorders menimpa state dari pembacaan lama 80/20.

**Dampak dan batas interpretasi:** Physical stock 200 memungkinkan dua reserve 80. SO allocations 160, item reserved 80, remaining backorder 20; demand 100 tidak konservatif. Barrier hanya mengatur urutan final write SO, business code dan allocator asli tidak diganti.

- `D4-BACKORDER-01-concurrent-fill` — expected `{"allocated_qty": 100, "item_reserved_qty": 100, "backorder_qty": 0}`; actual `{"allocated_qty": 160.0, "item_reserved_qty": 80.0, "backorder_qty": 20.0}`; `observed_difference`.

```python
  79:     _bo_set.update(stage_fields({**order, **_bo_set}))
  80:     await db.sales_orders.update_one(
  81:         {"id": order["id"]},
  82:         {"$set": _bo_set, "$push": {"allocations": {"$each": new_allocs}}})
  83:     # Auto-commit (4a): order sudah approved/confirmed → roll baru langsung di-commit.
  84:     if new_status in ("approved", "confirmed"):
  85:         from services.roll_service import set_order_rolls_status
  86:         await set_order_rolls_status(order["id"], "committed")
  87:     from dependencies import audit
  88:     await audit(actor_name, "backorder_auto_fulfilled", "sales_order", order["id"], {
  89:         "product_id": product_id, "qty_fulfilled": round(order_got, 2),
```

**Prompt perbaikan:**

> Periksa `D4-BACKORDER-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Claim demand atomik per SO line/version sebelum reserve supply, atau serialisasi operation yang dapat dipulihkan dengan idempotency dan CAS. Kegagalan CAS harus release/compensate allocation yang terlanjur dibuat. Jangan hanya mengganti $set menjadi $inc tanpa demand bound. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Dua request 80 pada shortage 100 tidak pernah menghasilkan reserve total>100; item/allocations/backorder/physical reserved balance sama. Uji dua SKU pada SO sama, auto GR fulfillment vs admin manual, retry, partial failure dan cancel bersamaan.

**Hubungan dengan catatan lain:** D4-PLAN-03, V3-MRES-01

## D4-CAP-01 — SKU yang benar-benar ada ditolak saat membuat PO setelah 1.000 master pertama

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/purchase_orders.py:407](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/purchase_orders.py#L407).



**Tampilan / rantai terkait:** Master Produk / katalog → Pembuatan PO → validasi produk · Expanded dashboard catalog → selected known SKU → PO create capped lookup → false 404.

**Penyebab:** Producer membangun lookup dari first 1000 product docs tanpa filter ID payload. Produk yang ada di luar window dianggap tidak ditemukan; cap 3000 pada dashboard tidak menutup batas 1000 producer.

**Dampak dan batas interpretasi:** Fixture 3003 SKU: PO untuk CAP 0001 berhasil 200; request setara untuk CAP 1002 mendapat 404 meskipun find_one memastikan master ada. Kegagalan ini mencegah procurement SKU sah; bukan hanya tampilan terpotong.

- `D4-CAP-01-purchase-known-sku` — expected `{"CAP0001": {"http_status": 200, "exists": true}, "CAP1002": {"http_status": 200, "exists": true}}`; actual `{"CAP0001": {"http_status": 200, "exists": true}, "CAP1002": {"http_status": 404, "exists": true, "detail": "Produk CAP1002 tidak ditemukan"}}`; `observed_difference`.

```python
 404:                         f"'{supplier_name}' di menu Pemasok terlebih dahulu."))
 405:     
 406:     # Validate products and calculate total
 407:     products = {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
 408:     # FASE F (PS-12) — jangan membelanjakan uang untuk barang yang spesifikasinya
 409:     # belum sah (konsep/labdip/proofing) atau sudah dihentikan.
 410:     from services import rnd_gate
 411:     await rnd_gate.assert_orderable(
 412:         [products[it.product_id] for it in payload.items if it.product_id in products],
 413:         where="Purchase Order")
 414:     raw_items = []
```

**Prompt perbaikan:**

> Periksa `D4-CAP-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Ambil master berdasarkan himpunan ID yang benar-benar diminta, lalu bandingkan missing IDs. Gunakan paginated search untuk UI dan aggregate independen untuk KPI. Review lookup sejenis pada SO/PR/amendment/receiving, bukan mengganti 1000 menjadi angka lebih besar. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PO untuk SKU pertama dan SKU 1003 sama-sama dibuat dengan source FK yang sah; SKU benar-benar tidak ada ditolak. Uji catalog 3003/large, PR→PO, call-off, same-SKU concurrency, grade/UOM/lifecycle guard tetap berlaku.

**Hubungan dengan catatan lain:** D4-DASH-01

## D4-ORDER-01 — Rata-rata pesanan membagi revenue seluruh pesanan dengan hanya 20 pesanan terbaru

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** public_api_to_original_javascript_counterexample.

**Letak:** [frontend/src/features/orders/OrderDashboard.jsx:74](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/orders/OrderDashboard.jsx#L74).



**Tampilan / rantai terkait:** Pesanan → Dasbor: jumlah orders, Rata-rata Pesanan, Top Customers, Status Distribution dan Expiring · Public /dashboard cap 20 → App state data.orders → OrdersView orders prop → OrderDashboard metrics; /sales-orders/stats/summary aggregate semua pesanan.

**Penyebab:** Patch revenue memakai summary.revenue[period].grand_total seluruh pesanan, tetapi denominator recentOrders.length tetap dari window 20. Server sudah menyediakan revenue.count untuk populasi dan status yang sama; consumer mengabaikannya. Top Customers dan status/pending/expiry juga memakai window lokal tanpa label cakupan. Halaman list memakai pagination dan summary server, sehingga list benar tidak membuktikan dasbor benar.

**Dampak dan batas interpretasi:** Fixture 30 SO confirmed 100 pada entitas dan periode sama: original public API memberikan orders 20 dan revenue 3000/count 30. Original JavaScript useMemo memberi totalRevenue 3000 (kontrol PASS), totalOrders 20 dan avg 150 padahal 100. Top Customers untuk customer yang sama hanya 2000 padahal 3000. Ini source-grain mismatch, bukan kesalahan operasi pembagian. Tidak ada klaim bahwa seluruh tabel latest 10 salah; batas 10 pada Recent Orders diberi label jelas.

- `D4-ORDER-01-revenue-control` — expected `3000`; actual `3000`; `pass`.
- `D4-ORDER-01-count` — expected `30`; actual `20`; `observed_difference`.
- `D4-ORDER-01-average` — expected `100`; actual `150`; `observed_difference`.
- `D4-ORDER-01-customer-revenue` — expected `3000`; actual `2000`; `observed_difference`.

```javascript
  71:       totalOrders: recentOrders.length,
  72:       pendingOrders: pendingOrders.length,
  73:       expiringSoon: expiringSoon.length,
  74:       avgOrderValue: recentOrders.length > 0 ? totalRevenue / recentOrders.length : 0,
  75:       topCustomers,
  76:       statusCounts,
  77:       recentOrders: orders.slice(0, 10)
  78:     };
  79:   }, [orders, timeRange, summary]);
  80:   
  81:   const formatCurrency = (amount) => {
```

**Prompt perbaikan:**

> Periksa `D4-ORDER-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan revenue.count sebagai denominator jika rata-rata didefinisikan atas status terpenuhi; definisikan totalOrders terpisah bila mencakup semua status. Hitung Top Customers, distribusi status, pending dan expiry di server dengan scope entity/sales-owner/line/periode yang sama. Label setiap pengecualian periode atau dataset parsial. Jangan memuat seluruh dokumen di browser untuk memperbaiki agregat. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 30 SO confirmed 100 menghasilkan revenue 3000/count 30/avg 100 dan customer revenue 3000. Uji >20 dan >200, mix reserved/cancelled/fulfilled, periode 7/30/90, sales-owner, line scope dan perubahan filter. Bandingkan seluruh widget dengan source query independen; Recent Orders tetap boleh 10 dengan labelnya.

**Hubungan dengan catatan lain:** D4-DASH-01, D4-FE-01

## D4-CASE-01 — Refund store credit menjurnal pengurangan kewajiban dua kali dan menciptakan pendapatan semu

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_gl_counterexample.

**Letak:** [backend/services/finance_case_actions.py:238](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L238).

**Lokasi kode lain dalam rantai:** [backend/services/store_credit_service.py:286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/store_credit_service.py#L286) · [backend/services/gl_service.py:2483](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2483) · [backend/services/finance_case_actions.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L57).

**Tampilan / rantai terkait:** Finance → Pusat Kasus → Refund pelanggan → Saldo kredit toko; buku besar dan laporan laba rugi · Store credit producer → public case create/resolve → sc.adjust(-80) → GL adjustment → cash out 80 → GL cash → resolved.

**Penyebab:** act_refund_store_credit memakai adjust yang ditujukan untuk koreksi/hangus saldo. store_credit_service.adjust sudah memposting Dr2-1450/Cr4-9000, lalu _cash_txn kembali memposting Dr2-1450/CrKas. Dua jurnal masing-masing seimbang, tetapi kedua jurnal untuk satu refund mengurangi kewajiban dua kali.

**Dampak dan batas interpretasi:** Producer adjustment+100 menghasilkan saldo dan kewajiban 100. Public resolve refund 80 sukses 200; ledger pelanggan 20 dan kas keluar 80 benar. Jurnal refund mendebit kewajiban 160, mengkredit Other Income 80, dan saldo kredit GL menjadi-60 padahal ledger 20. Ini normal flow tanpa fault injection. Initial adjustment adalah producer sah; preceding return/CN producer tidak diklaim diuji dalam fixture ini.

- `D4-CASE-01-public-resolution-control` — expected `200`; actual `200`; `pass`.
- `D4-CASE-01-ledger-control` — expected `20`; actual `20.0`; `pass`.
- `D4-CASE-01-liability-debit` — expected `80`; actual `160.0`; `observed_difference`.
- `D4-CASE-01-phantom-income` — expected `0`; actual `80.0`; `observed_difference`.
- `D4-CASE-01-liability-ledger-reconciliation` — expected `20`; actual `-60.0`; `observed_difference`.

```python
 235:     if amount > bal + EPS:
 236:         raise CaseActionError(
 237:             f"Pengembalian {_rp(amount)} melebihi saldo kredit toko {_rp(bal)}")
 238:     entry = await sc.adjust(customer_id=cust, entity_id=ent, amount_signed=-amount,
 239:                             note=f"Dicairkan lewat kasus {case['number']}", actor=actor)
 240:     res = await _cash_txn(
 241:         direction="out", amount=amount, category="refund store credit",
 242:         description=f"Pencairan saldo kredit toko · {case['number']}",
 243:         entity_id=ent, account_id=p.get("account_id", ""),
 244:         cash_type=p.get("cash_type") or "kas_besar", ref_type="finance_case",
 245:         ref_id=case["id"], contra=gl.ACC_STORE_CREDIT, owner_entity_id=ent,
```

**Prompt perbaikan:**

> Periksa `D4-CASE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Sediakan operasi pencairan store credit dengan identitas aksi stabil: klaim saldo, buat satu jurnal DrStoreCredit/CrCash, lalu baris ledger menunjuk jurnal yang sama. Hindari memakai adjust/hangus yang menciptakan pendapatan. Pertahankan append-only ledger, legal entity dan referensi kasus. Audit redemption, reversal, return issue, backfill serta semua caller adjust agar GL dan saldo pelanggan tidak terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Saldo 100, refund 80: cash 80, liability-debit 80, OtherIncome 0, ledger 20=GL20. Public response dan dokumen turunannya lengkap. Uji refund dari credit note asli, partial refund, dua klik, saldo tidak cukup, closed period, GL failure, ledger failure, retry dan reversal; tidak boleh ada journal/ledger yatim atau refund kedua.

**Hubungan dengan catatan lain:** V3-AR-01, D4-CASE-02

## D4-CASE-02 — Penyelesaian kasus keuangan dapat mengulang kas yang sudah tercatat setelah konflik atau kegagalan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_concurrency_and_retry_counterexample.

**Letak:** [backend/services/finance_case_actions.py:206](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L206).

**Lokasi kode lain dalam rantai:** [backend/services/finance_case_service.py:419](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L419) · [backend/services/finance_case_actions.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L57) · [backend/services/finance_case_actions.py:253](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L253) · [backend/services/ar_receipt_service.py:159](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/ar_receipt_service.py#L159) · [backend/services/finance_case_actions.py:461](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L461) · [backend/services/finance_case_actions.py:482](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L482) · [backend/services/gl_service.py:467](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L467).

**Tampilan / rantai terkait:** Finance → Pusat Kasus → Refund uang muka / Pindah buku; Kas & Bank, saldo pelanggan, GL transit · Receipt deposit 100 → public case resolve → cash+GL before balance CAS → conflict/fault → same case retry; own-bank first leg → second-leg failure → retry.

**Penyebab:** finance_case_service.resolve tidak mengklaim action sebelum side effects dan baru menulis status di akhir. _cash_txn selalu membuat UUID baru; idempotensi jurnal per UUID kas tidak melindungi kasus/aksi. Refund mencatat kas sebelum CAS deposit. Pindah buku membuat dua leg berurutan tanpa checkpoint stabil yang dapat dilanjutkan.

**Dampak dan batas interpretasi:** Normal single refund 80 dari receipt deposit 100 benar: saldo 20/kas 80/Dr2-1400 80. Dua resolve yang dijadwalkan setelah sama-sama membaca saldo menghasilkan satu 200/satu 400 tetapi kas keluar 160; deposit CAS tetap 20. Fault sesudah kas+JE sebelum CAS, lalu retry kasus sama, juga kas 160/deposit 20. Pindah buku 80, first leg sukses dan second leg gagal; retry menghasilkan out 160/in80, kasus resolved, saldo transit debit 80. Supplier advance 100 lalu dua refund 80 menghasilkan cash-in160 dan saldo-60 karena unconditional $inc. Penetapan advance 100 gagal saat checkpoint kasus lalu retry menghasilkan saldo 200, sementara GL tetap 100. Refund pada state periode terkunci, tanpa injeksi kegagalan, menulis cash-out 80 posted sebelum GL ditolak; deposit tetap 100 dan kasus open. Supplier fixture dimulai dari original manual advance decision, dan closing memakai explicit closed-state fixture, bukan full vendor-payment/closing producer. Semua ini satu keluarga durability/action identity dan sequencing, bukan setiap subflow diberi ID bug terpisah.

- `D4-CASE-02-normal-refund-control` — expected `{"http": 200, "deposit": 20, "cash": 80, "liability_debit": 80}`; actual `{"http": 200, "deposit": 20.0, "cash": 80.0, "liability_debit": 80.0}`; `pass`.
- `D4-CASE-02-concurrent-cash` — expected `80`; actual `160.0`; `observed_difference`.
- `D4-CASE-02-concurrent-deposit-control` — expected `20`; actual `20.0`; `pass`.
- `D4-CASE-02-concurrent-http-control` — expected `[200, 400]`; actual `[200, 400]`; `pass`.
- `D4-CASE-02-failure-retry-cash` — expected `80`; actual `160.0`; `observed_difference`.
- `D4-CASE-02-failure-retry-deposit-control` — expected `20`; actual `20.0`; `pass`.
- `D4-CASE-02-bank-transfer-retry-total` — expected `{"in": 80, "out": 80}`; actual `{"in": 80.0, "out": 160.0}`; `observed_difference`.
- `D4-CASE-02-bank-transfer-transit` — expected `0`; actual `80.0`; `observed_difference`.
- `D4-CASE-02-supplier-producer-control` — expected `{"http": 200, "advance": 100}`; actual `{"http": 200, "advance": 100.0}`; `pass`.
- `D4-CASE-02-supplier-concurrent-cash` — expected `80`; actual `160.0`; `observed_difference`.
- `D4-CASE-02-supplier-concurrent-balance` — expected `20`; actual `-60.0`; `observed_difference`.
- `D4-CASE-02-supplier-advance-retry-balance` — expected `100`; actual `200.0`; `observed_difference`.
- `D4-CASE-02-supplier-advance-retry-journal-control` — expected `100`; actual `100.0`; `pass`.
- `D4-CASE-02-closed-period-cash` — expected `0`; actual `80.0`; `observed_difference`.
- `D4-CASE-02-closed-period-journal-control` — expected `0`; actual `0`; `pass`.
- `D4-CASE-02-closed-period-deposit-control` — expected `100`; actual `100.0`; `pass`.

```python
 203:     return {"documents": docs, "amount": total}
 204: 
 205: 
 206: async def act_refund_pelanggan(case: Dict[str, Any], p: Dict[str, Any],
 207:                                actor: Dict[str, Any]) -> Dict[str, Any]:
 208:     """Uang muka pelanggan dikembalikan (Dr 2-1400 / Cr Kas-Bank)."""
 209:     from services import ar_receipt_service as ar
 210:     cust = p.get("customer_id") or case.get("customer_id") or ""
 211:     amount = round(float(p.get("amount") or 0), 2)
 212:     dep = await ar.get_deposit_balance(cust)
 213:     if amount > dep + EPS:
```

**Prompt perbaikan:**

> Periksa `D4-CASE-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Terapkan durable operation identity per case+action/version serta atomic claim dengan precondition lifecycle. Klaim dana sebelum kas; simpan leg/checkpoint dan idempotency keys sebelum side effect. Retry melanjutkan leg yang belum selesai dan mengembalikan hasil committed beserta journal reference yang sudah ada, bukan None. Supplier advance mutation juga harus idempotent dan refund memakai balance CAS. Preflight closed period/account/entity sebelum cash atau balance diposting; failed fund/period claim tidak menulis posted cash. Crash recovery/compensation tidak boleh sekadar melepas lock lalu mengulang semua aksi. Audit seluruh executor playbook karena pola status di akhir dipakai bersama; jangan menganggap executor lain terbukti gagal hanya dari source ini. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Normal dan concurrent customer refund tetap satu cash 80/JE80/deposit 20; loser tidak meninggalkan cash. Supplier advance 100/refund 80: saldo 20, cash-in80; retry penetapan advance tidak menambah saldo kedua kali dan saldo=GL100. Semua fault boundary cash insert, JE, balance, case-status dan doc-link diuji. Own-bank transfer 80 setelah failure/retry harus out 80/in80/transit 0. Periode terkunci menolak sebelum cash/balance mutation; unlock sah berjalan normal. Dua request satu case dan dua case berbeda atas dana sama tidak overspend. Dokumen resolusi merujuk seluruh committed legs, reversal append-only, recovery tetap dapat berjalan setelah restart.

**Hubungan dengan catatan lain:** D4-CASE-01, V3-AR-01, V3-BANK-01

## D4-INTERCO-01 — Transfer roll retur dapat selesai memindahkan pemilik tetapi kehilangan jurnal pasangan dan dokumen pemulihan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_controlled_failure_counterexample.

**Letak:** [backend/services/gl_service.py:1333](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L1333).

**Lokasi kode lain dalam rantai:** [backend/services/return_service.py:1126](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_service.py#L1126) · [backend/services/roll_service.py:1519](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L1519) · [backend/routers/transfers.py:476](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/transfers.py#L476).

**Tampilan / rantai terkait:** Retur Jual → Roll released → Pindah kepemilikan; inventory/RFID owner, jurnal antarentitas dan histori transfer · Released return roll A → saga claim → execute_ownership_transfer toB → source JE → destination JE failure → ineffective rollback → retry.

**Penyebab:** return_service.transfer_return_roll_ownership memindahkan owner, lot, RFID owner, movements dan balances sebelum post_intercompany_transfer. Failure rollback mencari reserved_ref yang sudah dibersihkan oleh transfer sehingga owner tidak kembali. warehouse_transfers baru ditulis sesudah kedua JE. Helper GL memakai OR guard: ada salah satu sisi dianggap sudah selesai, tanpa mengisi sisi lain.

**Dampak dan batas interpretasi:** Normal kontrol sukses 200, ownerB dan JE kedua sisi. Fault terkontrol tepat sebelum original destination JE insert: roll/tag/lot sudahB, source JE100 ada, destination tidak ada, transfer doc 0. Parent saga dilepas. Retry helper mengembalikan already_posted dan tetap satu JE; retry API 400 karena pemilik saat ini sudahB. Fixture dimulai dari state released external-sales-return roll dengan original inbound writer dan metadata retur eksplisit; tidak diklaim full SO→retur approval producer atau physical gate telah diuji. Jalur return-origin internal-purchase tetap ditolak sesuai aturan yang sudah ada.

- `D4-INTERCO-01-normal-control` — expected `{"http": 200, "je_posted": true, "owner": "B"}`; actual `{"http": 200, "je_posted": true, "owner": "B"}`; `pass`.
- `D4-INTERCO-01-owner-after-failed-transfer` — expected `"A"`; actual `"B"`; `observed_difference`.
- `D4-INTERCO-01-transfer-history-after-failure` — expected `1`; actual `0`; `observed_difference`.
- `D4-INTERCO-01-rfid-owner-after-failure` — expected `"A"`; actual `"B"`; `observed_difference`.
- `D4-INTERCO-01-journal-pair-after-failure` — expected `["A", "B"]`; actual `["A"]`; `observed_difference`.
- `D4-INTERCO-01-helper-recovery-pair` — expected `2`; actual `1`; `observed_difference`.
- `D4-INTERCO-01-public-recovery` — expected `200`; actual `400`; `observed_difference`.

```python
1330:     # Idempotent guard (cek dua-sisi terpisah)
1331:     src_id = f"{tid}:src"
1332:     dst_id = f"{tid}:dst"
1333:     if await _already_posted("inter_company_transfer", src_id) or \
1334:        await _already_posted("inter_company_transfer", dst_id):
1335:         return {"posted": False, "reason": "already_posted", "total": 0.0}
1336: 
1337:     valuation = await _transfer_items_value_at_cost(transfer, src)
1338:     total = float(valuation["total"])
1339:     if total <= EPS:
1340:         return {"posted": False, "reason": "zero_cost", "total": 0.0,
```

**Prompt perbaikan:**

> Periksa `D4-INTERCO-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist intent transfer dengan operation ID dan cost snapshot sebelum pemindahan. Checkpoint owner/lot/tag/movements/GL tiap sisi; retry harus menyelesaikan missing leg secara idempotent. already_posted harus memeriksa pasangan lengkap dan nilai/ref yang sama, bukan OR existence. Gunakan compensation yang sadar state bila dipilih rollback. Terapkan perbaikan helper shared juga pada transfers.approve dan recovery sesudah crash tanpa memindahkan roll dua kali. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault destination JE, pair-link, transfer-doc insert, return-history write dan balances: hasil dapat dipulihkan sampai owner/lot/tag/ledger kedua PT/history konsisten, atau rollback penuh yang auditable. Satu source JE tidak dianggap selesai. Retry original API harus recover atau menunjukkan operation pending yang dapat dilanjutkan; concurrent request tidak membuat extra movements/JE. Kontrol internal-purchase return tetap menuju Retur Antar-PT.

**Hubungan dengan catatan lain:** D4-INTERCO-02, V3-MASTER-01

## D4-INTERCO-02 — Nilai transfer antarentitas memakai WAC sesudah stok sumber dipindahkan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_cost_snapshot_counterexample.

**Letak:** [backend/services/gl_service.py:1337](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L1337).

**Lokasi kode lain dalam rantai:** [backend/services/return_service.py:1206](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_service.py#L1206) · [backend/routers/transfers.py:435](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/transfers.py#L435) · [backend/services/costing_service.py:45](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/costing_service.py#L45).

**Tampilan / rantai terkait:** Pindah kepemilikan roll retur / Transfer antarentitas at-cost → GL persediaan dan IC-AR/IC-AP · Costed roll A → ownership move toB → source WAC recompute → at-cost JE → stored transfer valuation.

**Penyebab:** _transfer_items_value_at_cost mengambil WAC live entitas sumber. Kedua caller shared menjalankan ownership transfer sebelum memposting helper. Roll yang menjadi objek transfer sudah dikeluarkan dari query source WAC: cost yang dipakai berasal dari sisa barang lain atau fallback master lama. Tidak ada snapshot biaya sebelum perpindahan.

**Dampak dan batas interpretasi:** Normal original public API 200, tanpa fault: satu roll 10m cost 15, master HPP 1; pre-source WAC 15, tetapi sesudah roll pindah source kosong sehingga JE total 10, padahal pre-source at-cost 150. Roll tujuan tetap cost 15/nilai 150. Pada sumber berisi 10m×5 dan 10m×15, pre-source WAC 10 dan target transfer 10m seharusnya 100 menurut kontrak WAC; setelah roll mahal dipindah, JE50 memakai cost roll murah yang tertinggal. Kebijakan WAC versus actual roll-cost harus ditetapkan untuk kasus campuran; kasus sumber satu roll sudah salah pada kedua kebijakan.

- `D4-INTERCO-02-empty_source-valuation` — expected `150.0`; actual `10.0`; `observed_difference`.
- `D4-INTERCO-02-empty_source-http-control` — expected `200`; actual `200`; `pass`.
- `D4-INTERCO-02-empty_source-retained-roll-cost-control` — expected `15`; actual `15.0`; `pass`.
- `D4-INTERCO-02-cheaper_remainder-valuation` — expected `100.0`; actual `50.0`; `observed_difference`.
- `D4-INTERCO-02-cheaper_remainder-http-control` — expected `200`; actual `200`; `pass`.
- `D4-INTERCO-02-cheaper_remainder-retained-roll-cost-control` — expected `15`; actual `15.0`; `pass`.

```python
1334:        await _already_posted("inter_company_transfer", dst_id):
1335:         return {"posted": False, "reason": "already_posted", "total": 0.0}
1336: 
1337:     valuation = await _transfer_items_value_at_cost(transfer, src)
1338:     total = float(valuation["total"])
1339:     if total <= EPS:
1340:         return {"posted": False, "reason": "zero_cost", "total": 0.0,
1341:                 "breakdown": valuation["breakdown"]}
1342: 
1343:     code = transfer.get("code") or tid
1344:     pair_id = f"ict_{tid}"
```

**Prompt perbaikan:**

> Periksa `D4-INTERCO-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan dan simpan immutable valuation sebelum owner/status berubah, dengan quantity/UOM, per-line/per-roll cost dan legal entity source. Pilih kebijakan WAC atau actual roll-cost secara eksplisit dan jaga rekonsiliasi GL terhadap SSOT roll cost; jangan recompute retry dari live remaining source atau cache/fallback. Helper GL mengonsumsi snapshot tervalidasi dan kedua sisi memakai total sama. Audit transfers.approve, return transfer, destination revaluation serta konsolidasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Satu roll 10×15 dengan stale master 1 menghasilkan JE150, ownerB dan subledger 150. Sumber campuran 5/15 mengikuti policy yang terdokumentasi dan kedua entitas tetap rekonsiliasi. Uji source menjadi kosong, source tetap berisi roll biaya berbeda, landed cost, conversion yard/meter, zero-cost nyata versus missing-cost, concurrent cost update, partial transfer, failure/retry tanpa revaluasi ulang.

**Hubungan dengan catatan lain:** D4-INTERCO-01, D4-STOCK-01, D4-STOCK-03

## D4-DOC-01 — Pratinjau Template Dokumen Dasar memanggil endpoint yang tidak tersedia dan mengabaikan jenis template

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_api_to_original_javascript_contract_counterexample.

**Letak:** [frontend/src/hooks/useAppActions.js:616](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/hooks/useAppActions.js#L616).

**Lokasi kode lain dalam rantai:** [frontend/src/features/admin/AdminView.jsx:542](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/admin/AdminView.jsx#L542) · [frontend/src/AppViewRouter.jsx:260](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/AppViewRouter.jsx#L260) · [backend/routers/documents.py:283](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/documents.py#L283).

**Tampilan / rantai terkait:** Pengaturan → Template Dokumen Dasar → Pratinjau pada baris template; iframe live preview · nav doc-templates-basic → AdminView templates → row button → AppViewRouter onPreviewTemplate → useAppActions.previewTemplate → missing POST route.

**Penyebab:** Callback melakukan POST /document-templates/{id}/preview, tetapi aplikasi hanya menyediakan GET /documents/preview/{order_id} beserta CRUD template. Original hook juga mematok document_type invoice walaupun row yang dipilih adalah Surat Jalan. Jalur ini masih terhubung pada activeView doc-templates-basic, sehingga bukan hanya fungsi lama yang tidak pernah dipakai.

**Dampak dan batas interpretasi:** Original public creator membuat template Surat Jalan yang dapat dilihat lewat GET list; satu SO state fixture milikA tersedia. Exact POST dari UI mendapat 404. Original hook dengan original 404 memberi notice Not Found dan tidak mengisi previewHtml. Transport control membuktikan URL yang dipanggil; request body invoice padahal selected row surat_jalan. Existing GET document preview memberi 200 HTML pada fixture sama, sehingga bukan masalah seluruh renderer atau data kosong. DOM tidak diuji; SO fixture bukan full create/fulfill producer.

- `D4-DOC-01-existing-template-control` — expected `{"http": 200, "exists": true}`; actual `{"http": 200, "exists": true}`; `pass`.
- `D4-DOC-01-preview-contract` — expected `200`; actual `404`; `observed_difference`.
- `D4-DOC-01-alternative-renderer-control` — expected `{"http": 200, "html": true}`; actual `{"http": 200, "html": true}`; `pass`.
- `D4-DOC-01-original-route-control` — expected `"http://audit.local/api/document-templates/tmpl_437b60725d91/preview"`; actual `"http://audit.local/api/document-templates/tmpl_437b60725d91/preview"`; `pass`.
- `D4-DOC-01-selected-template-document-type` — expected `"surat_jalan"`; actual `"invoice"`; `observed_difference`.
- `D4-DOC-01-original-preview-html` — expected `true`; actual `false`; `observed_difference`.

```javascript
 613: 
 614:   const previewTemplate = async (templateId, orderId) => {
 615:     try {
 616:       const response = await axios.post(`${API}/document-templates/${templateId}/preview`, { document_type: "invoice", source_id: orderId, actor: user?.name || "Admin" }, { responseType: "text" });
 617:       setPreviewHtml(response.data);
 618:       setNotice("Preview template diperbarui.");
 619:     } catch (error) {
 620:       setNotice(error.response?.data?.detail || "Preview template gagal. Pastikan ada order untuk preview.");
 621:     }
 622:   };
 623: 
```

**Prompt perbaikan:**

> Periksa `D4-DOC-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Satukan kontrak preview berdasarkan source document dan selected template ID/type. UI meneruskan jenis template yang dipilih; server memvalidasi entity, permissions, template effective layer dan kompatibilitas source tanpa membuat generated document/transaksi. Jangan sekadar mengganti endpoint ke GET yang mengabaikan selected ID. Pastikan template dasar dan PDF designer mempunyai batas fitur yang jelas dan dokumen yang benar-benar dicetak memakai format/field yang sama dengan preview. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Admin membuka Template Dokumen Dasar dengan SO yang sah: Pratinjau template Surat Jalan/invoice/jenis lain memberi 200 HTML untuk selected template dan document type yang tepat. Dua template tipe sama harus dapat dipratinjau berbeda sesuai ID, global vs entity override terkontrol, source berbeda entitas ditolak, disabled template ditangani jelas, tanpa generated-doc atau ledger side effect. Uji empty orders, permissions, invalid template/source, error recovery, iframe HTML dan output cetak.

**Hubungan dengan catatan lain:** D4-FE-02

## D4-CASE-03 — Alur dana dipegang karyawan tidak menjaga urutan langkah dan sisa piutang

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_business_state_counterexample.

**Letak:** [backend/services/finance_case_actions.py:310](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L310).

**Lokasi kode lain dalam rantai:** [backend/services/finance_case_service.py:441](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L441) · [backend/services/finance_case_service.py:467](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L467) · [backend/services/finance_case_playbooks.py:113](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_playbooks.py#L113).

**Tampilan / rantai terkait:** Pusat Kasus Keuangan → Transfer ke rekening pribadi karyawan → akui piutang → catat setoran · Case open → action dispatch without transition guard → cash received / employee receivable credit → unconditional resolved.

**Penyebab:** Service memvalidasi action terdaftar pada playbook, tetapi tidak memvalidasi state/step/next_action atau remaining acknowledged receivable. act_setor_dari_karyawan tidak menuntut bukti step 1 berhasil, tidak membatasi amount terhadap sisa piutang, dan tidak mengembalikan hold untuk partial settlement. resolve menutup semua aksi yang tidak memberi hold.

**Dampak dan batas interpretasi:** Original normal step 1 80 lalu step 2 80 lulus: resolved, employee debt 0, cash-in80. Original public step 2 pada case baru juga diterima 200: cash 80, employee receivable-80 tanpa acknowledgment step 1. Setelah step 1 80, setoran 40 memberi receivable 40 tetapi case resolved; setoran 100 memberi receivable-20 tanpa surplus classification. Ini normal requests tanpa fault injection, dan diuji dengan startup indexes asli. SO adalah fixture receivable read-state; original payment/GL executors dipakai, bukan klaim seluruh SO producer sudah diuji.

- `D4-CASE-03-normal-two-step-control` — expected `{"http": [200, 200], "state": "resolved", "debt": 0, "cash_in": 80}`; actual `{"http": [200, 200], "state": "resolved", "debt": -0.0, "cash_in": 80.0}`; `pass`.
- `D4-CASE-03-skip-step-one-cash` — expected `0`; actual `80.0`; `observed_difference`.
- `D4-CASE-03-skip-step-one-debt` — expected `0`; actual `-80.0`; `observed_difference`.
- `D4-CASE-03-partial-remains-open` — expected `"in_progress"`; actual `"resolved"`; `observed_difference`.
- `D4-CASE-03-partial-receivable-control` — expected `40`; actual `40.0`; `pass`.
- `D4-CASE-03-excess-receivable` — expected `0`; actual `-20.0`; `observed_difference`.

```python
 307:             "next_action": "setor_dari_karyawan"}
 308: 
 309: 
 310: async def act_setor_dari_karyawan(case: Dict[str, Any], p: Dict[str, Any],
 311:                                   actor: Dict[str, Any]) -> Dict[str, Any]:
 312:     """Langkah 2: karyawan menyetor → piutang karyawan kembali nol."""
 313:     amount = round(float(p.get("amount") or 0), 2)
 314:     emp = (p.get("employee_name") or (case.get("resolution") or {})
 315:            .get("extra", {}).get("employee_name") or "karyawan")
 316:     res = await _cash_txn(
 317:         direction="in", amount=amount, category="setoran karyawan",
```

**Prompt perbaikan:**

> Periksa `D4-CASE-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan state machine per playbook di backend dengan permitted action, prerequisites, operation version dan remaining amount yang diturunkan dari acknowledged/settled legs. Setoran harus menunjuk acknowledgment/employee yang sah, menjaga legal entity dan source debt. Partial settlement tetap in_progress dengan remaining dan next_action, atau ditolak sebelum efek bila policy tidak membolehkannya. Excess memerlukan keputusan eksplisit dengan akun/ledger surplus yang tepat; jangan mengkredit piutang lebih besar dari yang ada. UI menampilkan step yang sah tetapi server tetap menjadi gate. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Step 2 sebelum acknowledgment ditolak tanpa cash/JE. Holding 80→deposit 80: debt 0 dan resolved. Holding 80→deposit 40: remaining 40, case pending dan dapat menerima 40 berikutnya. Deposit 100 tidak membuat employee receivable negatif; surplus 20 diproses sesuai keputusan terdokumentasi atau request ditolak tanpa side effect. Uji wrong employee/entity/source, repeated step 1, multiple partial settlements, concurrent settlements, rejection/reopen, reversal dan restart recovery; kriteria CASE-02 juga harus terpenuhi.

**Hubungan dengan catatan lain:** D4-CASE-02

## D4-CLOSE-01 — Reopen bulan tidak menandai penutupan tahun yang bergantung padanya sebagai basi

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_api_closing_dependency_counterexample.

**Letak:** [backend/services/closing_service.py:346](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L346).

**Lokasi kode lain dalam rantai:** [backend/services/closing_service.py:398](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L398) · [frontend/src/features/finance/ClosingView.jsx:307](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/ClosingView.jsx#L307).

**Tampilan / rantai terkait:** Keuangan → Tutup Buku → Reopen bulanan; status tahunan dan tombol Tutup Ulang · Manual revenue 100 → month closing 100 → year residual 0 → reopen month → annual snapshot no invalidation → UI hides reclose.

**Penyebab:** reopen_period menganulir jurnal bulan dan memperbarui record bulan, tetapi tidak menginvalidasi penutupan aktif yang mencakupnya. reclose_period memiliki propagasi stale ke parent; reopen tidak. UI menyediakan Tutup Ulang hanya bila closed dan stale, sehingga penutupan tahun tetap tampil final tanpa akses normal ke aksi pemulihannya.

**Dampak dan batas interpretasi:** Original public API: pendapatan 100, close Januari 100 dan tahun residual 0 lulus. Reopen Januari 200 mengembalikan laba belum ditutup 100; tahun tetap closed/staleFalse. Preview tahunan menghitung residual 100, tetapi tombol Tutup Ulang tidak ditawarkan oleh source UI. Persamaan neraca tetap seimbang dan P&L operasional tetap 100; bukan klaim math neraca gagal. Direct API reclose tahunan 200 tersedia sebagai workaround, walau UI tidak menawarkannya. Seluruh producer manual/closing asli; DOM tidak diuji.

- `D4-CLOSE-01-nested-producer-control` — expected `{"month": 100, "year": 0}`; actual `{"month": 100.0, "year": 0.0}`; `pass`.
- `D4-CLOSE-01-before-reopen-control` — expected `0`; actual `0.0`; `pass`.
- `D4-CLOSE-01-parent-stale` — expected `true`; actual `false`; `observed_difference`.
- `D4-CLOSE-01-parent-residual-control` — expected `100`; actual `100.0`; `pass`.
- `D4-CLOSE-01-post-reopen-operating-income-control` — expected `100`; actual `100.0`; `pass`.
- `D4-CLOSE-01-post-reopen-unclosed-income-control` — expected `100`; actual `100.0`; `pass`.
- `D4-CLOSE-01-direct-reclose-workaround-control` — expected `200`; actual `200`; `pass`.

```python
 343:     return safe_doc(rec)
 344: 
 345: 
 346: async def reopen_period(closing_id: str, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
 347:     rec = await db.period_closings.find_one({"id": closing_id}, {"_id": 0})
 348:     if not rec:
 349:         return None
 350:     if rec.get("status") != "closed":
 351:         raise ValueError("Periode ini tidak dalam status tertutup.")
 352:     # INV-ATOMIC-01 — klaim periode (masih closed) sebelum jurnal penutup di-void.
 353:     from services import atomic_claim as _saga
```

**Prompt perbaikan:**

> Periksa `D4-CLOSE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan dependency/invalidation graph penutupan bulanan/tahunan dan terapkan pada reopen, reclose, unlock corrections serta void. Setelah journal penutup anak berubah, parent harus stale/pending dengan alasan dan residual yang dapat direkonsiliasi, atau reopen ditolak sebelum efek bila policy mewajibkan urutan parent dahulu. Tampilkan tindakan pemulihan sesuai status; jangan menandai final hanya karena record closed masih ada. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Close bulan 100 lalu tahun residual 0 → reopen bulan: parent tahun diberi stale dan tersedia reclose, atau aksi ditolak tanpa void sebelum parent ditangani. Setelah pemulihan, residual 100 tertutup satu kali; P&L operasional 100 tetap 100 dan total equity tetap rekonsiliasi. Uji tahun buku non-Desember, beberapa bulan, parent residual bukan 0, reopen/reclose berulang, concurrency, entity dan fault checkpoints.

**Hubungan dengan catatan lain:** D4-CLOSE-02

## D4-CLOSE-02 — Tutup ulang gagal mengadopsi jurnal yang sudah tersimpan sehingga recovery admin tetap gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_closing_fault_and_admin_recovery_counterexample.

**Letak:** [backend/services/closing_service.py:371](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L371).

**Lokasi kode lain dalam rantai:** [backend/services/closing_service.py:404](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L404) · [backend/routers/saga_locks.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L90) · [backend/indexes.py:444](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/indexes.py#L444).

**Tampilan / rantai terkait:** Keuangan → Tutup Buku → Tutup Ulang; Kunci Saga → pemeriksaan efek dan pelepasan admin · Dual-control unlock → backdated correction → reclose → old JE void → new JE durable → lost acknowledgement → parent old ref → admin release → retry unique-index conflict.

**Penyebab:** reclose_period menganulir jurnal lama, membuat jurnal baru dengan source_id closing yang sama, lalu baru memperbarui snapshot dan link parent. Tidak ada checkpoint/adopsi jurnal aktif yang sudah dibuat bila acknowledgment atau parent update gagal. Retry menggunakan parent journal_entry_id lama yang sudah void lalu mencoba insert ulang, bertabrakan dengan unique active source index. Kunci saga memang terlihat dan memblokir replay, tetapi pelepasan yang sah tidak menyediakan resumable recovery.

**Dampak dan batas interpretasi:** Original producer public: close laba 100, unlock dengan pengusul dan penyetuju berbeda, koreksi 20 dan normal reclose 120 lulus. Koreksi berikut 10, fault hanya sesudah original JE130 durably inserted: parent net 120/linkJE 120 void, JE130 aktif dan saga lock tersisa. Immediate retry 409 adalah kontrol guard yang benar. Setelah clock lock di-aging secara eksplisit dan original admin release dengan acknowledgment 200, original reclose retry 500 karena active source unique index, parent tetap link lama. Tidak diklaim journal 130 hilang atau duplicate berhasil dibuat; indeks menjaga jumlah 1 tetapi recovery/link/snapshot gagal.

- `D4-CLOSE-02-normal-reclose-control` — expected `{"net": 120, "stale": false}`; actual `{"net": 120.0, "stale": false}`; `pass`.
- `D4-CLOSE-02-linked-journal-posted` — expected `"posted"`; actual `"void"`; `observed_difference`.
- `D4-CLOSE-02-active-journal-control` — expected `{"count": 1, "total": 130}`; actual `{"count": 1, "total": 130.0}`; `pass`.
- `D4-CLOSE-02-parent-net-income` — expected `130`; actual `120.0`; `observed_difference`.
- `D4-CLOSE-02-immediate-lock-control` — expected `409`; actual `409`; `pass`.
- `D4-CLOSE-02-admin-release-control` — expected `200`; actual `200`; `pass`.
- `D4-CLOSE-02-original-recovery-retry` — expected `200`; actual `500`; `observed_difference`.
- `D4-CLOSE-02-recovery-linked-existing` — expected `"je_6eaaad066784"`; actual `"je_5de1a6405853"`; `observed_difference`.

```python
 368:     return await db.period_closings.find_one({"id": closing_id}, {"_id": 0})
 369: 
 370: 
 371: async def reclose_period(closing_id: str, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
 372:     """F-9b — Tutup Ulang periode yang STALE (angka berubah karena posting backdate):
 373:     void jurnal penutup lama → hitung ulang residual (kecuali JE closing ini sendiri)
 374:     → buat jurnal penutup baru → bersihkan flag stale."""
 375:     rec = await db.period_closings.find_one({"id": closing_id}, {"_id": 0})
 376:     if not rec:
 377:         return None
 378:     if rec.get("status") != "closed":
```

**Prompt perbaikan:**

> Periksa `D4-CLOSE-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist reclose operation/version dan checkpoint intent, old/new journal IDs serta frozen totals sebelum efek. Retry harus mengadopsi JE yang cocok dengan operation/version dan memfinalisasi parent, bukan menganggap unique-index error sebagai sukses atau membuat jurnal baru. Rancang atomic switch/compensation agar status/link/snapshot konsisten, tandai failure yang dapat diperiksa, dan recovery admin menyelesaikan/membatalkan operation secara sadar efek. Pertahankan unique index, fencing dan guard periode; audit close/reopen/unlock auto-close serta concurrent yearly/monthly operations. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Lost acknowledgment sesudah JE insert dan kegagalan parent update dapat direcover lewat fitur asli: tepat satu active JE130, parent menunjuknya/net 130/staleFalse, lock selesai dan histori jelas. Fault sebelum insert tidak membuang journal lama tanpa recovery; retry setelah restart tidak menciptakan extraJE. Uji reopen bersamaan, akun nonaktif, partial unlock, fiscal year, parent invalidation dan laporan/print yang mengikuti snapshot final.

**Hubungan dengan catatan lain:** D4-CLOSE-01, D4-CASE-02

## D4-GL-01 — Jurnal manual yang sudah dibalik masih dapat dianulir dan membentuk pembatalan dua kali

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_mutually_exclusive_cancellation_counterexample.

**Letak:** [backend/services/gl_service.py:755](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L755).

**Lokasi kode lain dalam rantai:** [backend/services/gl_service.py:783](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L783) · [frontend/src/features/finance/GeneralLedger.jsx:369](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/GeneralLedger.jsx#L369).

**Tampilan / rantai terkait:** Keuangan → Buku Besar → Detail Jurnal → Balik Jurnal lalu Anulir Jurnal; Laba-Rugi/Neraca Saldo · Manual expense 100 → reverse journal → net 0 → void original only → standalone reversal → income 100.

**Penyebab:** void_entry memeriksa status non-void dan sumber manual, tetapi mengabaikan reversed_by_entry_id termasuk pending reversal. Filter CAS void juga hanya status non-void. Frontend tetap menampilkan Anulir Jurnal untuk manual/posted walaupun sudah reversed. Membalik dan menganulir asal dapat terjadi berurutan atau beradu tanpa mutually exclusive cancellation state.

**Dampak dan batas interpretasi:** Normal original public manual expense 100 → void memberi laba 0 sebagai kontrol. Manual expense 100 → reverse juga laba 0 sebagai kontrol. Setelah reversal, original public void masih 200: jurnal asal void, pembalik tetapposted. Original income_statement menghasilkan net_income+100, sehingga satu pembatalan berubah menjadi laba semu 100. Ini normal requests tanpa fault injection dan diuji dengan startup indexes. Tidak diklaim semua pembalikan otomatis wajib mengubah dokumen sumber; temuan adalah membatalkan asal dua kali melalui dua aksi GL.

- `D4-GL-01-ordinary-void-control` — expected `{"http": 200, "income": 0}`; actual `{"http": 200, "income": 0}`; `pass`.
- `D4-GL-01-single-reversal-control` — expected `0`; actual `0`; `pass`.
- `D4-GL-01-second-cancellation-rejected` — expected `true`; actual `false`; `observed_difference`.
- `D4-GL-01-post-reversal-void-income` — expected `0`; actual `100.0`; `observed_difference`.

```python
 752:         {"$or": [{"id": entry_id}, {"number": entry_id}]}, {"_id": 0})
 753: 
 754: 
 755: async def void_entry(entry_id: str, actor: Dict[str, Any],
 756:                      can_backdate: bool = True) -> Optional[Dict[str, Any]]:
 757:     je = await db.journal_entries.find_one({"id": entry_id}, {"_id": 0})
 758:     if not je:
 759:         return None
 760:     if je.get("status") == "void":
 761:         raise ValueError("Jurnal sudah di-void.")
 762:     if je.get("source_type") != "manual":
```

**Prompt perbaikan:**

> Periksa `D4-GL-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tentukan satu state machine cancellation: void dan reverse saling eksklusif secara atomik, termasuk reversal pending. Tolak void atas jurnal reversed sebelum efek; bila business policy mengizinkan koreksi pasangan, gunakan aksi terpisah yang memproses pasangan/link/period secara auditable, bukan void asal saja. UI menyembunyikan/menjelaskan aksi tidak sah tetapi backend gate wajib. Review source reversal, backfill dan laporan agar pembalik tetap teridentifikasi. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Manual 100 → reverse: net 0; void asal sesudahnya ditolak 4xx tanpa mengubah jurnal/PL. Manual 100 → void: net 0; reverse asal ditolak. Dua request reverse/void bersamaan hanya satu cancellation menang, tidak pernah menyisakan pembalik tunggal. Uji pending/failed reversal, retry, closed period, partial fault dan drilldown/print/link jurnal.

**Hubungan dengan catatan lain:** D4-CLOSE-02

## D4-GL-02 — Jurnal manual meloloskan NaN/Infinity dan menghilangkan angka transaksi sah dari laporan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_invalid_numeric_and_report_counterexample.

**Letak:** [backend/services/gl_service.py:640](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L640).

**Lokasi kode lain dalam rantai:** [backend/services/gl_service.py:524](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L524) · [backend/schemas_finance.py:53](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_finance.py#L53) · [backend/services/gl_service.py:2974](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2974) · [backend/services/financial_statement_service.py:88](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L88).

**Tampilan / rantai terkait:** Keuangan → Buku Besar/Jurnal manual API → Neraca Saldo, KPI GL dan Laba-Rugi · Valid expense 50 → manual float coercion of JSON stringNaN/Infinity → bypass central validation → non-finite Mongo double → reports omit poisoned account → displayed expense 0.

**Penyebab:** Validator pusat _validate_entry_lines memakai math.isfinite, tetapi create_manual_entry menyisipkan langsung ke journal_entries tanpa melewatinya. Perbandingan negatif/zero/difference terhadap NaN tidak menolak; Infinity-Infinity juga NaN. Schema JournalLineIn menerima coercion string ke float. Response sanitizer mengubah angka tidak finite menjadi null, tanpa membatalkan penulisan.

**Dampak dan batas interpretasi:** Authorized public API dengan JSON valid berupa string NaN dan Infinity masing-masing sukses 200, menyimpan native non-finite double dan mengirim amountsnull. Sebelumnya expense 50 menghasilkan summarydebit 50. Sesudah badentries pada dua akun sama, public GLsummary tetap 200/balancedTrue tetapi totaldebit 0; public P&L opex 0 padahal expense 50 sah tetap ada. Ini invalid-input correctness test, bukan klaim input NaN terjadi dari browser biasa. Hipotesis HTTP 500 karena serialization ditarik: hasil nyata adalah sanitization/masking dan silent omission.

- `D4-GL-02-healthy-summary-control` — expected `{"http": 200, "debit": 50}`; actual `{"http": 200, "debit": 50.0}`; `pass`.
- `D4-GL-02-nan-persisted` — expected `0`; actual `1`; `observed_difference`.
- `D4-GL-02-nan-validation` — expected `true`; actual `false`; `observed_difference`.
- `D4-GL-02-infinity-persisted` — expected `0`; actual `1`; `observed_difference`.
- `D4-GL-02-infinity-validation` — expected `true`; actual `false`; `observed_difference`.
- `D4-GL-02-summary-valid-amount-retained` — expected `50`; actual `0.0`; `observed_difference`.
- `D4-GL-02-income-valid-expense-retained` — expected `50`; actual `0`; `observed_difference`.

```python
 637:                   "updated_at": now_iso()}})
 638: 
 639: 
 640: async def create_manual_entry(payload, actor: Dict[str, Any],
 641:                               entity_id: Optional[str] = None,
 642:                               can_backdate: bool = True) -> Dict[str, Any]:
 643:     raw = [ln.model_dump() if hasattr(ln, "model_dump") else dict(ln) for ln in (payload.lines or [])]
 644:     if len(raw) < 2:
 645:         raise ValueError("Jurnal minimal 2 baris (debit & kredit).")
 646:     codes = [str(l.get("account_code", "")).strip() for l in raw]
 647:     if any(not c for c in codes):
```

**Prompt perbaikan:**

> Periksa `D4-GL-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan validator pusat yang sama untuk seluruh manual/autopost/import producers sebelum side effect, dengan field finite di schema dan validasi aggregate balance sesudah normalisasi. Tolak NaN/Infinity dari angka maupun string 4xx sebelum insert atau perubahan counters material. Jangan mengubah invalid values menjadi 0 sebagai perbaikan. Audit data existing dengan penandaan dan koreksi/reversal yang disetujui; laporan harus menampilkan masalah integritas, bukan silently menghapus akun sah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** NaN/±Infinity pada setiap field debit/credit dan total tidak tersimpan;4xx dengan detail jelas, jurnal/GL tidak berubah. Fixture expense 50 tetap summarydebit 50 dan PLexpense 50 setelah invalid request. Uji numeric strings, overflow 1e309, rounding, huge/negative/zero values, import/manual/autopost, legacy damaged-record quarantine dan safe display tanpa menyatakan balanced jika data rusak.

**Hubungan dengan catatan lain:** D4-GL-01

## D4-EQ-01 — KPI Laba Periode Berjalan pada perubahan ekuitas berubah menjadi nol sesudah tutup buku

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_api_closing_to_frontend_metric_counterexample.

**Letak:** [backend/services/equity_statement_service.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/equity_statement_service.py#L57).

**Lokasi kode lain dalam rantai:** [frontend/src/features/finance/EquityChangesTab.jsx:61](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/EquityChangesTab.jsx#L61) · [backend/services/financial_statement_service.py:62](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L62) · [backend/routers/financial_statements.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/financial_statements.py#L90).

**Tampilan / rantai terkait:** Keuangan → Laporan Keuangan → Perubahan Ekuitas → Laba Periode Berjalan · Operational income 100 → balance current_earnings100 → closing reclass to retained earnings → current_earnings0 → equity API net_income0 → labelled profit KPI.

**Penyebab:** equity_statement mengisi net_income dari perubahan saldo laba yang belum ditutup pada neraca. Itu perubahan komponen equity, bukan laba operasional periode. Jurnal penutup mengubah saldo current_earnings tanpa mengubah laba periode. Frontend memakai net_income dengan label Laba Periode Berjalan tanpa menjelaskan unclosed earnings movement.

**Dampak dan batas interpretasi:** Original public manual revenue 100: equity API sebelum closingnet 100. Original monthly/year closing yang benar memindahkan 100 ke RE; equity API periode sama sesudahnya netincome 0, sedangkan original operating P&L tetap 100. Total pergerakan equity 100 dan saldoakhir 100 benar sebagai kontrol. Source UI mengonsumsi net_income langsung pada KPI; DOM tidak diuji. Temuan source-definition mismatch, bukan roll-forward equity salah atau semua closing gagal.

- `D4-EQ-01-open-period-income-control` — expected `100`; actual `100.0`; `pass`.
- `D4-EQ-01-closed-period-net-income` — expected `100`; actual `0.0`; `observed_difference`.
- `D4-EQ-01-total-equity-movement-control` — expected `100`; actual `100.0`; `pass`.
- `D4-EQ-01-operating-profit-control` — expected `100`; actual `100.0`; `pass`.

```python
  54:         "begin_total": round(begin_total, 2),
  55:         "movement_total": round(end_total - begin_total, 2),
  56:         "end_total": round(end_total, 2),
  57:         "net_income": round(end_ce - begin_ce, 2),
  58:         "generated_at": now_iso(),
  59:     }
```

**Prompt perbaikan:**

> Periksa `D4-EQ-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan period_operating_net_income yang dihitung dari P&L non-closing dalam range/scope yang sama, dengan movement_unclosed_earnings yang diperlukan untuk roll-forward. KPI profit memakai period income; tabel perpindahan RE/current earnings tetap merekonsiliasi, jangan menambahkan laba sekali lagi ke end_total atau movement_total. Dokumentasikan label, beginning balances, fiscal range dan export contract. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Periode profit 100 tetap KPI 100 sebelum/sesudah monthly/year close, reopen/reclose, dan menutup residual; equity movement/end totals tetap 100. Uji opening retained earnings, laba/rugi, periode melintasi beberapa closes, dividen/injeksi modal, comparative/entity, CSV dan source-to-rendered validation. Net income tidak berubah hanya karena laba ditransfer antar komponen equity.

**Hubungan dengan catatan lain:** D4-CLOSE-01

## D4-COA-01 — Mode Semua Entitas pada laporan keuangan menghilangkan akun khusus entitas yang sah

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_producer_multi_entity_dimension_counterexample.

**Letak:** [backend/services/financial_statement_service.py:54](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L54).

**Lokasi kode lain dalam rantai:** [backend/services/financial_statement_service.py:40](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L40) · [backend/services/gl_service.py:507](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L507) · [backend/routers/gl.py:60](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/gl.py#L60) · [backend/services/gl_service.py:651](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L651).

**Tampilan / rantai terkait:** Keuangan → Laporan Keuangan → Semua Entitas; Laba-Rugi dan Neraca · Public entity-specific COA creator → valid manual JE → single-entity effective dimension → all-scope global-only dimension → missing income and unbalanced BS.

**Penyebab:** scope_entity mengembalikan None untuk scope multi-entitas. _accounts_map lalu meminta effective_accounts hanya untuk global template. Producer mendukung akun khusus entitas dengan kode yang tidak ada global; akun sah tersebut hilang dari dimensi multi-entity sehingga debit kas masih dihitung tetapi pendapatan lawannya tidak diklasifikasi. Ini berbeda dari memilih override nama akun yang nondeterministik.

**Dampak dan batas interpretasi:** Original public create akun income 4-7777 hanyaA dan manual DrKas 77/CrIncome 77 sukses 200. Public P&L Juli untukA net 77; mode all berisiA+B, B kosong padaJuli, tetapi net 0. SingleA neraca balancedTrue; all balancedFalse dengan assets 307 tetap benar dan equity 230, selisih 77. Assets 307 berasal dari original lifecycle 100+130+77. Tidak ada konflik override, invalid input atau fault pada skenario ini. Temuan spesifik endpoint Laporan Keuangan entity_id=all, bukan klaim semua fitur Konsolidasi Grup yang memakai helper lain gagal.

- `D4-COA-01-single-entity-income-control` — expected `77`; actual `77.0`; `pass`.
- `D4-COA-01-all-entities-income` — expected `77`; actual `0`; `observed_difference`.
- `D4-COA-01-single-entity-balance-control` — expected `true`; actual `true`; `pass`.
- `D4-COA-01-all-entities-balanced` — expected `true`; actual `false`; `observed_difference`.
- `D4-COA-01-all-entities-assets-control` — expected `307`; actual `307.0`; `pass`.

```python
  51:     """FN-05 — COA efektif entitas laporan (global + override entitas itu, deterministik).
  52:     Laporan multi-entitas memakai dimensi akun global (bukan override acak entitas lain)."""
  53:     from services.gl_service import effective_accounts
  54:     return await effective_accounts(None, scope_entity(scope))
  55: 
  56: 
  57: async def _aggregate(scope: Optional[Dict[str, Any]],
  58:                      date_filter: Optional[Dict[str, str]],
  59:                      include_closing: bool = True) -> Dict[str, Dict[str, float]]:
  60:     """Jumlahkan debit/credit per account_code dari jurnal (non-void, ter-scope).
  61: 
```

**Prompt perbaikan:**

> Periksa `D4-COA-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Resolve account dimension pada grain entity+account sebelum agregasi, lalu roll-up lewat mapping COA grup yang eksplisit. Akun khusus entitas tidak boleh hilang; bila belum dipetakan ke COA grup, tampilkan error/rekonsiliasi yang actionable, bukan silently drop. Jangan memilih override PT pertama secara acak untuk semua PT. Audit P&L/BS/comparative/equity/cashflow, ledger/trial balance dan export dengan resolver yang sesuai scope; pertahankan legal-entity permissions dan policy untuk kode sama dengan klasifikasi berbeda. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Akun khususA income 77 danB kosong: A dan all sama-samaincome 77, allBS balanced dan selisih 0; total all merekonsiliasi partisi legal entity. Uji akun khusus dua PT dengan kode unik, override nama/kategori/type berbeda pada kode sama, global disabled/entity active, unmapped group code, pagination COA besar, comparative, CSV serta entity access. Fitur Konsolidasi Grup yang memakai helper lain harus diuji sebagai kontrol terpisah.

**Hubungan dengan catatan lain:** D4-FIN-01, D4-EQ-01

## D4-PA-01 — Reservasi SO mengambil roll yang sudah diklaim putaway dan meninggalkan lokasi alokasi lama

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/roll_service.py:792](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L792).

**Lokasi kode lain dalam rantai:** [backend/services/putaway_order_service.py:152](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L152) · [backend/services/putaway_order_service.py:200](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L200) · [backend/services/roll_service.py:736](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L736) · [backend/services/roll_service.py:549](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L549) · [backend/routers/sales_orders.py:421](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/sales_orders.py#L421) · [backend/services/sales_order_helpers.py:123](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_order_helpers.py#L123).

**Tampilan / rantai terkait:** Putaway Order → POS/Sales Order → reservasi → sumber pemenuhan gudang · Verified roll → PA claim → public SO whole/partial reservation → PA dispatch/arrival → persisted allocation points to old warehouse.

**Penyebab:** PA mengklaim active_movement tetapi status roll tetap available. Candidate dan CAS reservasi utuh/panjang mengabaikan klaim tersebut. Reservasi parsial mempertahankan status available sambil menambah length_reserved; dispatch PA tidak memeriksa length_reserved. Tidak ada koordinasi atau rebinding alokasi SO setelah roll berpindah.

**Dampak dan batas interpretasi:** Original public PA lalu SO10 mengambil roll 10 yang sama; PA dispatch 409 adalah kontrol yang benar, tetapi konflik proses sudah terjadi. Pada roll 10/SO6, public SO menyimpan reservasi 6 di gudang asal, lalu PA dispatch 200/arrival 200 memindahkan roll ke tujuan. SO tersimpan tetap menunjuk asal. Tanpa fault injection; inbound writer asli, public print/verify/routing/SO/PA dan startup indexes. Tahap approval/picking/shipment SO setelah ini belum diuji lengkap.

- `D4-PA-01-whole-exclusive-claim` — expected `0`; actual `10.0`; `observed_difference`.
- `D4-PA-01-whole-dispatch-guard-control` — expected `409`; actual `409`; `pass`.
- `D4-PA-01-partial-exclusive-claim` — expected `0`; actual `6.0`; `observed_difference`.
- `D4-PA-01-partial-dispatch-blocked` — expected `409`; actual `200`; `observed_difference`.
- `D4-PA-01-partial-source-location-retained` — expected `"PARTIAL-FROM"`; actual `"PARTIAL-TO"`; `observed_difference`.
- `D4-PA-01-rmwhole-exclusive-claim` — expected `0`; actual `10.0`; `observed_difference`.
- `D4-PA-01-rmwhole-quantity-control` — expected `10`; actual `10.0`; `pass`.
- `D4-PA-01-rmwhole-dispatch-guard` — expected `409`; actual `409`; `pass`.
- `D4-PA-01-rmpart-exclusive-claim` — expected `0`; actual `6.0`; `observed_difference`.
- `D4-PA-01-rmpart-quantity-control` — expected `6`; actual `6.0`; `pass`.
- `D4-PA-01-rmpart-dispatch-guard` — expected `409`; actual `200`; `observed_difference`.

```python
 789: }
 790: 
 791: 
 792: async def _available_rolls_for_order(product_id: str, owner_entity_id: str, order_id: str,
 793:                                      customer_id: str = "") -> List[Dict[str, Any]]:
 794:     """Roll available owner-scoped untuk dialokasikan ke `order_id`/`customer_id`.
 795:     Menghormati EARMARK (pegging): roll yang di-earmark untuk demand LAIN dikecualikan;
 796:     roll yang di-earmark untuk order/customer ini tetap masuk (diprioritaskan planner)."""
 797:     rolls = await db.inventory_rolls.find(
 798:         {"product_id": product_id, "owner_entity_id": owner_entity_id, "status": "available",
 799:          "length_remaining": {"$gt": 0}}, {"_id": 0},
```

**Prompt perbaikan:**

> Periksa `D4-PA-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Definisikan kebijakan kompatibilitas reservasi/perpindahan. Bila klaim PA eksklusif, filter candidate dan CAS seluruh jalur reservasi dengan active_movement kosong; dispatch memeriksa reservasi live sebelum efek. Jika bisnis mengizinkan reservasi pada PA bergerak, koordinasikan per roll/demand dan rebind warehouse/task/alokasi secara auditable. Audit qty mode, explicit roll, reallocate, backorder, raw/makloon, release dan cancel PA. ATP/available-for-sale mengikuti kebijakan sama; jangan hanya menyaring UI. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** PA roll 10 lalu SO10/SO6 tidak menghasilkan klaim konflik: ditolak/defer tanpa efek atau lewat koordinasi yang menjaga source/task. Partial reserved tidak ikut bergerak tanpa rebinding. Uji urutan terbalik, race PA/SO, cut, release/cancel, arrival/retry dan qty/explicit-roll public producers. Demand, roll, balance, lokasi dan task tetap rekonsiliasi.

**Hubungan dengan catatan lain:** V3-WMS-02, D4-PA-02, D4-WMS-04

## D4-PA-02 — Putaway kehilangan checkpoint setelah roll berpindah sehingga recovery stok dan tag gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/putaway_order_service.py:232](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L232).

**Lokasi kode lain dalam rantai:** [backend/services/putaway_order_service.py:280](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L280) · [backend/services/putaway_order_service.py:329](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L329) · [backend/services/roll_service.py:233](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L233) · [backend/routers/saga_locks.py:42](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L42) · [backend/routers/putaway_orders.py:74](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/putaway_orders.py#L74).

**Tampilan / rantai terkait:** Putaway Order → Konfirmasi Tiba → BTG/exception; Kunci Saga; stok dan lokasi RFID · Roll location CAS + unset active_movement → tag/movements/balance/parent → failure → admin release → retry/accept cannot adopt landed roll.

**Penyebab:** _land_items memindahkan roll dan menghapus active_movement sebelum tag, mutasi, saldo dan parent difinalisasi. Retry menuntut warehouse asal dan active_movement yang sudah dihapus; tidak ada checkpoint/adopsi efek operation yang sama. Inspector saga tidak memeriksa perubahan existing roll atau PA reference secara memadai.

**Dampak dan batas interpretasi:** Kontrol normal: completed/BTG, roll+tag tujuan, saldo asal 0/tujuan 10 dan dua mutasi. Fault sesudah original roll CAS, sebelum tag update:500; roll tujuan/tag asal, saldo asal transit 10/tujuan 0. Immediate retry 409 lulus. Original admin inspect/release setelah clock aging eksplisit tidak melihat efek. Retry dan accept 200 tetap completed_with_exception; tag asal, mutasi 0, saldo asal 10/tujuan 0. Roll SSOT tidak hilang, tetapi proyeksi/dokumen/tag tertinggal. Manual scan sintetis bukan uji perangkat fisik.

- `D4-PA-02-normal-movement-control` — expected `{"status": "completed", "roll_wh": "NORMAL-TO", "tag_wh": "NORMAL-TO", "from_qty": 0, "to_qty": 10, "movement_count": 2}`; actual `{"status": "completed", "roll_wh": "NORMAL-TO", "tag_wh": "NORMAL-TO", "from_qty": 0.0, "to_qty": 10.0, "movement_count": 2}`; `pass`.
- `D4-PA-02-normal-btg-control` — expected `true`; actual `true`; `pass`.
- `D4-PA-02-fault-control` — expected `500`; actual `500`; `pass`.
- `D4-PA-02-immediate-lock-control` — expected `409`; actual `409`; `pass`.
- `D4-PA-02-inspect-durable-roll-effect` — expected `true`; actual `false`; `observed_difference`.
- `D4-PA-02-retry-parent-finalized` — expected `"completed"`; actual `"completed_with_exception"`; `observed_difference`.
- `D4-PA-02-retry-tag-location` — expected `"RECOVERY-TO"`; actual `"RECOVERY-FROM"`; `observed_difference`.
- `D4-PA-02-retry-audit-pair` — expected `2`; actual `0`; `observed_difference`.
- `D4-PA-02-retry-destination-balance` — expected `10`; actual `0`; `observed_difference`.
- `D4-PA-02-retry-source-balance` — expected `0`; actual `10.0`; `observed_difference`.
- `D4-PA-02-roll-is-at-destination-control` — expected `"RECOVERY-TO"`; actual `"RECOVERY-TO"`; `pass`.

```python
 229:     return await _get(order_id, scope_ids)
 230: 
 231: 
 232: async def _land_items(order: Dict[str, Any], items: List[Dict[str, Any]], actor_name: str,
 233:                       reason: str) -> List[Dict[str, Any]]:
 234:     """Satu jalur posting perpindahan (arrival normal & exception — WM-09): CAS roll milik PA ini,
 235:     pindah gudang, tulis pasangan mutasi out/in, rebuild kedua lokasi. Hasil = item yang benar-benar pindah."""
 236:     from services.roll_service import rebuild_balance
 237:     now = now_iso()
 238:     landed, movements, segs = [], [], set()
 239:     for item in items:
```

**Prompt perbaikan:**

> Periksa `D4-PA-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist operation/version dan checkpoint landed/tagged/audit-posted/balance-rebuilt/parent-finalized per item. Pertahankan token/provenance transisi agar retry mengadopsi efek sah dan melengkapi langkah tersisa. Mutasi out/in memakai unique operation+roll+leg. Inspector admin mencakup roll update, PA number/reference, tag dan invalidation saldo; pelepasan lock bukan penyelesaian efek. Jangan menerima semua roll di tujuan tanpa provenance atau memakai manual edit Mongo sebagai recovery. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault setiap batas roll/tag/mutasi/saldo/parent pulih lewat fitur asli: satu BTG, dua mutasi per roll, parent completed, tag+roll tujuan, asal 0/tujuan 10 dan owned 10. Uji multiroll partial, lost acknowledgment/restart, concurrent/fenced recovery, exception accept/return, stock/ATP/lot. Kontrol normal tetap lulus.

**Hubungan dengan catatan lain:** D4-PA-01, D4-INTERCO-01, D4-CLOSE-02

## D4-PA-03 — Total putaway menjumlahkan meter dan yard lalu memberi satu label satuan

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/putaway_order_service.py:49](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L49).

**Lokasi kode lain dalam rantai:** [backend/services/putaway_order_service.py:166](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L166) · [frontend/src/features/wms/PutawayOrdersPanel.jsx:104](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/PutawayOrdersPanel.jsx#L104) · [frontend/src/features/wms/PutawayOrdersPanel.jsx:144](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/PutawayOrdersPanel.jsx#L144) · [backend/services/roll_service.py:1890](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L1890).

**Tampilan / rantai terkait:** Putaway Order → saran kategori/grade dan ringkasan PA/BTG · Valid product base units → category/owner/grade group → raw qty sum → g.unit / items[0].unit label.

**Penyebab:** Group key tidak memuat unit; qty mentah dijumlahkan dan unit diambil dari roll pertama. create_order menjumlahkan item menjadi total_qty tanpa konversi/breakdown. Frontend memberi label g.unit atau items[0].unit pada total campuran.

**Dampak dan batas interpretasi:** Original inbound/public print/verify: roll 10 meter SKU pertama dan roll 10 yard SKU kedua, woven/gradeA/ownerA. Suggest mengirim satu group 20 meter; public PA total 20 dengan item pertama meter. Harus 19.144 meter (19.14 jika kebijakan dua desimal) atau breakdown 10 meter+10 yard. Per-item benar; producer conversion tidak diklaim rusak. Source consumer diperiksa, DOM belum.

- `D4-PA-03-input-base-units-control` — expected `["meter", "yard"]`; actual `["meter", "yard"]`; `pass`.
- `D4-PA-03-mixed-group-validity` — expected `true`; actual `false`; `observed_difference`.
- `D4-PA-03-document-labelled-total` — expected `19.144`; actual `20.0`; `observed_difference`.

```python
  46:         {"_id": 0}).to_list(200)
  47:     groups: Dict[str, Dict[str, Any]] = {}
  48:     for r in rolls:
  49:         key = f"{r.get('owner_entity_id')}|{r.get('category') or '—'}|{(r.get('grade') or 'A').upper()}"
  50:         g = groups.setdefault(key, {
  51:             "owner_entity_id": r.get("owner_entity_id"), "category": r.get("category") or "",
  52:             "grade": (r.get("grade") or "A").upper(),
  53:             "rolls": [], "qty": 0.0, "unit": r.get("unit", "meter"), "candidates": None})
  54:         g["rolls"].append({k: r.get(k) for k in (
  55:             "id", "roll_no", "sku", "product_name", "category", "grade",
  56:             "length_remaining", "unit", "lot", "rfid_tag_id")})
```

**Prompt perbaikan:**

> Periksa `D4-PA-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Pisahkan total per unit atau konversi ke unit tujuan yang dinyatakan dengan faktor kanonis/precision eksplisit. Unit tak kompatibel kg/meter memakai breakdown dan jumlah roll. Snapshot faktor bila menjadi dokumen historis. Review saran, PA/BTG print, movement summary/export; jangan memakai unit item pertama atau mengganti label saja. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** 10 meter+10 yard tidak tampil 20 meter; gunakan 19.144/19.14 meter dengan precision eksplisit atau breakdown. Reorder item tidak mengubah makna total. Uji kg+meter, multi-SKU, conversion missing, faktor per dokumen, export/print. Per-item dan saldo base-unit tetap benar.

**Hubungan dengan catatan lain:** D4-STOCK-04, D4-GLOBAL-01

## D4-WMS-04 — KPI antrean simpan menghitung roll reserved yang tidak boleh diputaway

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/wms_health_service.py:42](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L42).

**Lokasi kode lain dalam rantai:** [backend/services/putaway_order_service.py:19](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L19) · [backend/services/putaway_order_service.py:113](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L113) · [frontend/src/features/wms/WmsHealthDashboard.jsx:16](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/WmsHealthDashboard.jsx#L16).

**Tampilan / rantai terkait:** Warehouse Health → Antrean Simpan ke Rak; Putaway → Siap Simpan · Verified available → public SO whole reservation → health counts old stage → suggest excludes → PA rejects.

**Penyebab:** putaway_ready hanya memeriksa owner/panjang/journey/routing; suggest/create menegakkan status available dan guard gerak/reservasi. Tidak ada ready/blocked breakdown atau penjelasan beda definisi. Tag_verified adalah bukti identitas, bukan ketersediaan operasional.

**Dampak dan batas interpretasi:** Roll verified tersedia: suggest 1. Original public SO reservasi 10: suggest 0 dan PA create 400, tetapi health tetap putaway_ready1. UI memakai angka pada Antrean Simpan ke Rak. Lifecycle asli; bukan fixture reserved arbitrer. Jika queue fisik memang termasuk reserved, label/kontrak perlu ready 0/blocked 1, bukan menyebut semuanya ready.

- `D4-WMS-04-ready-normal-control` — expected `1`; actual `1`; `pass`.
- `D4-WMS-04-reserved-suggestion-control` — expected `0`; actual `0`; `pass`.
- `D4-WMS-04-reserved-ready-kpi` — expected `0`; actual `1`; `observed_difference`.
- `D4-WMS-04-create-reserved-guard-control` — expected `400`; actual `400`; `pass`.

```python
  39:             rows[r["_id"]]["red_reads_today"] = r["n"]
  40:     async for r in db.inventory_rolls.aggregate([
  41:             {"$match": {"owner_entity_id": {"$in": scope_ids}, "length_remaining": {"$gt": 0},
  42:                         "journey.stage": "tag_verified", "journey.routing": {"$ne": "cross_dock"}}},
  43:             {"$group": {"_id": "$warehouse_id", "n": {"$sum": 1}}}]):
  44:         if r["_id"] in rows:
  45:             rows[r["_id"]]["putaway_ready"] = r["n"]
  46:     async for r in db.putaway_orders.aggregate([
  47:             {"$match": {"status": {"$in": ["open", "in_transit"]},
  48:                         "owner_entity_id": {"$in": scope_ids}}},
  49:             {"$group": {"_id": "$to_warehouse_id", "n": {"$sum": 1}}}]):
```

**Prompt perbaikan:**

> Periksa `D4-WMS-04` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan resolver eligibility yang sama pada health/suggest/create dengan owner/warehouse/current identity/reservasi. Jika termasuk blocked, pisahkan total_pending/ready/blocked_by_reason. Guard CAS server tetap wajib. Cakup QC, routing, active movement dan tag lifecycle. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Reserved tidak menambah actionable ready; health/suggest konsisten. Uji available, partial reserved, quarantine, active PA, pending/retired tag, crossdock, empty, beberapa entitas dan total vs rows. Bila definisi queue berbeda, tampilkan ready 0/blocked 1 beserta alasan.

**Hubungan dengan catatan lain:** D4-PA-01, D4-TAG-01, D4-WMS-01

## D4-RFID-01 — Deduplikasi event RFID melewati recovery keputusan, insiden dan status passage

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/rfid_ingest_service.py:138](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L138).

**Lokasi kode lain dalam rantai:** [backend/services/rfid_ingest_service.py:190](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L190) · [backend/services/rfid_ingest_service.py:194](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L194) · [backend/services/rfid_ingest_service.py:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L151) · [backend/services/rfid_ingest_service.py:214](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L214) · [backend/services/gate_evaluator.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gate_evaluator.py#L129) · [backend/routers/rfid.py:551](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfid.py#L551).

**Tampilan / rantai terkait:** Device Ingest → Gate Monitor/Passage → Alarm/insiden → gate-status API · Raw observation → exit stamp → business read → incident → passage/latch → fault → event dedupe/dwell skips unfinished effects.

**Penyebab:** Observation event_id durable dianggap processed untuk seluruh pipeline tanpa checkpoint read/stamp/incident/passage. Retry event sama dibuang; event baru dapat melewati efek yang belum selesai melalui dwell atau menjadi REPLAY_EXIT akibat stamp yang lebih dahulu durable. Ini berbeda dari cache keputusan basi V3-RFID-01.

**Dampak dan batas interpretasi:** Normal public ingest/replay lulus: satu green MOVEMENT_OUT read, satu duplicate. Fault setelah observation+green stamp sebelum read:500; replay 200/count 0/read 0; event baru menjadi REPLAY_EXIT red. Fault kedua setelah red read sebelum incident: replay dan fresh event dalam dwell tidak memulihkan incident; gate-status passageinfo/latchedFalse padahal red read 1. Stock tidak berubah adalah kontrol desain yang benar. Tidak diklaim lampu/gate fisik atau DOM kiosk diuji.

- `D4-RFID-01-fault-control` — expected `500`; actual `500`; `pass`.
- `D4-RFID-01-original-exit-stamp-control` — expected `"pa_7287e1da23b7"`; actual `"pa_7287e1da23b7"`; `pass`.
- `D4-RFID-01-retry-business-read` — expected `1`; actual `0`; `observed_difference`.
- `D4-RFID-01-retry-decision-count` — expected `1`; actual `0`; `observed_difference`.
- `D4-RFID-01-fresh-event-recovery-verdict` — expected `"MOVEMENT_OUT"`; actual `"REPLAY_EXIT"`; `observed_difference`.
- `D4-RFID-01-stock-unchanged-control` — expected `"in_transit_transfer"`; actual `"in_transit_transfer"`; `pass`.
- `D4-RFID-01-normal-dedupe-control` — expected `{"code": "MOVEMENT_OUT", "reads": 1, "duplicates": 1}`; actual `{"code": "MOVEMENT_OUT", "reads": 1, "duplicates": 1}`; `pass`.
- `D4-RFID-01-red-read-durable-control` — expected `1`; actual `1`; `pass`.
- `D4-RFID-01-red-incident-recovery` — expected `1`; actual `0`; `observed_difference`.
- `D4-RFID-01-red-passage-recovery` — expected `"red"`; actual `"info"`; `observed_difference`.
- `D4-RFID-01-red-latch-recovery` — expected `true`; actual `false`; `observed_difference`.

```python
 135:             "device_id": device["id"], "epc": ev["epc"], "event_id": ev.get("event_id"),
 136:             "captured_at": ev.get("captured_at"), "antenna": ev.get("antenna"), "rssi": ev.get("rssi"),
 137:             "batch_id": batch_id, "source": source, "received_at": now} for ev in evs]
 138:     dup_ids = set()
 139:     if obs:
 140:         try:
 141:             await db.rfid_observations.insert_many(obs, ordered=False)
 142:         except BulkWriteError as bwe:
 143:             dup_ids = {obs[e["index"]]["_id"] for e in bwe.details.get("writeErrors", []) if e.get("code") == 11000}
 144:     fresh = list(dict.fromkeys(o["epc"] for o in obs if o["_id"] not in dup_ids))
 145:     passage = await _passage_for(device, now) if is_gate else None
```

**Prompt perbaikan:**

> Periksa `D4-RFID-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan observation sebagai durable inbox dengan processing state/checkpoint. Per event/decision operation punya read/movement/incident IDs dan passage delta deterministik. Retry melengkapi efek dengan idempotent writes; dwell tidak melewati unfinished operation. Selaraskan exit stamp/read commit melalui transaction/outbox atau resumable sequence dengan provenance. Passage/latch mempertahankan keputusan red durable dan menjelaskan processing/unavailable bila belum final. Pertahankan no-stock-mutation, auth/EPC dan event guards. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault tiap batas observation/stamp/read/incident/passage pulih dari event sama tanpa kehilangan/duplikasi. Green belum final tidak menjadi false replay hanya karena recovery. Red durable menghasilkan satu incident dan red/latched, bukan info. Uji multi-EPC/mixed batch, dwell/new event, restart/reconnect, duplicate/concurrent events, movement change dan acknowledge. Uji perangkat fisik tetap terpisah.

**Hubungan dengan catatan lain:** V3-RFID-01, D4-PA-02, D4-TAG-01

## D4-CC-01 — Recovery cycle count membuat dua laporan dan nomor untuk satu sesi

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/cycle_count_service.py:124](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L124).

**Lokasi kode lain dalam rantai:** [backend/services/cycle_count_service.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L129) · [backend/routers/saga_locks.py:33](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L33) · [backend/routers/rfid.py:650](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfid.py#L650).

**Tampilan / rantai terkait:** Lokasi RFID → Cycle Count → Selesaikan; Kunci Saga; riwayat CC/health · Session/scan → result durable → lost acknowledgment → parent open/locked → admin release → new UUID/number on retry.

**Penyebab:** complete membuat UUID/nomor baru tiap eksekusi, insert result kemudian finalize session/link. Retry tidak mengadopsi existing result; startup indexes tidak menjamin satu result/session. Inspector tidak mencari rfid_cycle_counts.session_id.

**Dampak dan batas interpretasi:** Normal public start/scan/complete: accuracy 100, satu result, replay 400. Fault sesudah original result insert:500/result 1/parent locked. Setelah clock aging eksplisit, public admin inspect tidak melihat efek; release 200/complete 200 membuat result 2 untuk sesi sama dengan nomor baru. Tidak mengubah qty stock adalah desain report-only; temuan tentang histori/idempotensi laporan.

- `D4-CC-01-normal-count-control` — expected `{"accuracy": 100, "results": 1, "retry_http": 400}`; actual `{"accuracy": 100.0, "results": 1, "retry_http": 400}`; `pass`.
- `D4-CC-01-fault-control` — expected `500`; actual `500`; `pass`.
- `D4-CC-01-first-result-persisted-control` — expected `1`; actual `1`; `pass`.
- `D4-CC-01-inspect-count-effect` — expected `true`; actual `false`; `observed_difference`.
- `D4-CC-01-one-session-one-result` — expected `1`; actual `2`; `observed_difference`.

```python
 121:         "extra_items": extra_items[:500],
 122:         "created_at": now, "created_by": actor_name,
 123:     }
 124:     await db.rfid_cycle_counts.insert_one(dict(cc))
 125:     await db.rfid_verify_sessions.update_one({"id": session_id}, _saga.finish_set({
 126:         "status": "completed",
 127:         "result": "simulated" if simulated else ("clean" if not missing and not extra_items and not untagged_n else "with_issues"),
 128:         "missing": [m["epc"] for m in missing], "extra": extra_epcs,
 129:         "completed_at": now, "cycle_count_id": cc["id"]}))
 130:     return safe_doc(cc)
 131: 
```

**Prompt perbaikan:**

> Periksa `D4-CC-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist result ID/nomor operation/session sebelum efek, adopt result cocok saat retry dan finalize parent recoverably. Unique session+revision mengikuti policy recount; recount harus revision/session baru eksplisit. Inspector menampilkan CC durable dan langkah recovery. Rekonsiliasikan data existing secara auditable, jangan menghapus histori sembarangan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Lost acknowledgment atau failed parent update: satu result/nomor dan session completed yang menunjuknya. Uji restart/concurrency/stale lock, recount revision, entity scope, simulated/manual/device evidence dan health/history/export. Stock tidak dimutasi oleh laporan count.

**Hubungan dengan catatan lain:** D4-WMS-02, D4-RFID-01

## D4-TAG-01 — Verifikasi tag lama tetap berlaku setelah tag dihapus atau diganti dengan tag pending

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** original_public_wms_rfid_chain_counterexample.

**Letak:** [backend/services/putaway_order_service.py:132](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L132).

**Lokasi kode lain dalam rantai:** [backend/services/rfid_service.py:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_service.py#L151) · [backend/services/rfid_print_service.py:130](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_print_service.py#L130) · [backend/services/rfid_print_service.py:327](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_print_service.py#L327) · [backend/services/putaway_order_service.py:108](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L108).

**Tampilan / rantai terkait:** RFID → retire/ganti/cetak/verifikasi tag; Putaway → Buat PA · Verified identity → public retire clears roll tag → old journey tag_verified → PA accepts empty or pending_print EPC.

**Penyebab:** Retire menghapus current tag tetapi tidak menginvalidasi evidence identitas lama. PA percaya journey tag_verified dan lookup tag tanpa active/current verification version. Re-encode lewat print job menghasilkan pending_print yang belum dicetak/verifikasi, tetapi journey lama membuatnya siap bergerak.

**Dampak dan batas interpretasi:** Initial identity berasal dari original public print/mark-printed/manual scan/complete. Public retire 200 membuat current tagNone; PA create 200/EPCkosong. Pada roll kedua, retire→new print job memberi pending_print yang belum ack/scan; PA create juga 200. Bukan fixture tagless arbitrer RF-05: producer lifecycle sendiri menciptakan keadaan ini. Client mensyaratkan semua roll bertag; old identity bukan bukti EPC baru.

- `D4-TAG-01-retire-removes-current-tag-control` — expected `null`; actual `null`; `pass`.
- `D4-TAG-01-retired-putaway-rejected` — expected `true`; actual `false`; `observed_difference`.
- `D4-TAG-01-pending-print-control` — expected `"pending_print"`; actual `"pending_print"`; `pass`.
- `D4-TAG-01-new-unverified-identity-rejected` — expected `true`; actual `false`; `observed_difference`.

```python
 129:         if not check["ok"]:
 130:             violations.append(check["reason"])
 131:             continue
 132:         tag = await db.rfid_tags.find_one({"id": r.get("rfid_tag_id")}, {"_id": 0, "epc": 1}) or {}
 133:         items.append({
 134:             "roll_id": r["id"], "roll_no": r.get("roll_no", ""), "epc": tag.get("epc", ""),
 135:             "sku": p.get("sku", ""), "product_name": p.get("name", ""),
 136:             "category": p.get("category", ""), "grade": r.get("grade", ""),
 137:             "product_id": r["product_id"], "lot": r.get("lot", ""),
 138:             "qty": float(r.get("length_remaining") or 0), "unit": r.get("unit", "meter"),
 139:             "status": "pending",
```

**Prompt perbaikan:**

> Periksa `D4-TAG-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Identity readiness harus terikat roll/current live tag ID/EPC/version dan matching verification evidence. Terapkan konsisten pada suggest/create/dispatch/arrival/loading/gate. Retire/re-encode menginvalidasi readiness tanpa memundurkan physical journey secara keliru. Tag harus active, current, linked correctly, EPC kanonis dan verified sesuai policy. Perubahan identity pada active movement ditolak sebelum efek atau lewat workflow retag/manifest update/reverification yang auditable. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Verified→retire menolak PA tanpa claim dan tidak masuk ready. Pending_print baru belum lolos; sesudah ack/verifikasi sah boleh PA. Uji retire saat PAopen/transit, reprint sama, EPCbaru, wrong-link, cut child, tagrevision, race movement dan loading/gate/CC. Override eksplisit tidak menganggap bukti identitas lama sebagai current.

**Hubungan dengan catatan lain:** D4-RFID-01, D4-WMS-04



---

# Temuan validasi sebelumnya yang masih terbuka

17 counterexample runtime dijalankan kembali terhadap commit terbaru; dua catatan statis diperiksa ulang. Rinciannya tidak menyatakan semua kasus W1/W2 gagal: celah berikut dapat muncul pada failure window atau kombinasi data yang lebih luas.

## V3-PROD-01 — Konsumsi bahan dapat berulang setelah movement insert gagal

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/production_service.py:363](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/production_service.py#L363).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** CAS mengurangi roll sebelum journal inventory_movements ditulis. Recovery menghitung konsumsi dari movement; write yang gagal tidak tercatat, sehingga retry mengonsumsi lagi.

**Dampak dan batas interpretasi:** Stok 20→15 saat gagal insert movement; retry 20→10 untuk output 5, sementara movement/reported consumption hanya 5. Tidak ada crash sesudah commit yang diasumsikan: fault terjadi sebelum insert.

- `V3-PROD-01` — expected `"See original invariant and detailed acceptance"`; actual `{"error": "RuntimeError", "before_qty": 20, "after_fault_qty": 15.0, "after_retry_qty": 10.0, "output": 5.0, "reported_consumed": 5.0, "movement_qty": 5.0}`; `observed_difference`.

```python
 360:             if not won:
 361:                 continue  # roll berubah/di-hold bersamaan — dicoba lagi di putaran berikut
 362:             uc = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
 363:             await db.inventory_movements.insert_one({
 364:                 "id": new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
 365:                 "owner_entity_id": owner_entity_id, "movement_type": "production_consume",
 366:                 "quantity": -take, "unit": r.get("unit", "meter"), "lot": r.get("lot", ""),
 367:                 "lot_id": r.get("lot_id", ""), "roll_id": r["id"], "unit_cost": uc,
 368:                 "qty_rolls": 1, "source_document": wo_id, "operation_id": op_id, "timestamp": now_iso(),
 369:             })
 370:             value += take * uc
```

**Prompt perbaikan:**

> Periksa `V3-PROD-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Buat operasi konsumsi per material/roll dengan identity stabil dan state durable sebelum efek, lalu lakukan perubahan fisik dan ledger dalam transaksi atau step idempoten yang dapat direkonsiliasi. Jangan menyelesaikan recovery hanya dari movement yang mungkin belum lahir. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/sesudah tiap write, retry key sama/berbeda dan dua worker: stok 20→15, output 5, movement 5 tepat sekali. Recovery harus bekerja melalui endpoint sah; penghapusan lock di probe hanya kontrol pemulihan lokal.

**Hubungan dengan catatan lain:** GN-06, GN-11, W2-024

## V3-PROD-02 — Reversal dianggap selesai sebelum panjang roll dipulihkan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/production_service.py:389](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/production_service.py#L389).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Movement ditandai reversed sebelum update stok. Kalau update stok gagal, retry mengecualikan movement tersebut dan tidak melakukan restore.

**Dampak dan batas interpretasi:** Roll tersisa 5 dari awal 10; restore gagal sebelum update. Retry restored 0, roll tetap 5 dan movement reversed=true.

- `V3-PROD-02` — expected `"See original invariant and detailed acceptance"`; actual `{"retry_restored": 0.0, "remaining": 5, "movement_reversed": true}`; `observed_difference`.

```python
 386:     async for m in db.inventory_movements.find(
 387:             {"operation_id": op_id, "movement_type": "production_consume", "reversed": {"$ne": True}}, {"_id": 0}):
 388:         mark = await db.inventory_movements.update_one(
 389:             {"id": m["id"], "reversed": {"$ne": True}}, {"$set": {"reversed": True, "reversed_at": now_iso()}})
 390:         if mark.modified_count != 1:
 391:             continue
 392:         qty = -float(m["quantity"])
 393:         await db.inventory_rolls.update_one({"id": m["roll_id"]}, [
 394:             {"$set": {"status": {"$cond": [{"$eq": ["$status", "consumed"]}, "available", "$status"]},
 395:                       "length_remaining": {"$round": [{"$add": ["$length_remaining", qty]}, 2]},
 396:                       "updated_at": now_iso()}}])
```

**Prompt perbaikan:**

> Periksa `V3-PROD-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Claim reversal dengan token/stage dan stable operation ID. Commit restore stock dengan marker yang sama secara atomik, atau simpan progress yang membedakan claimed dari applied; retry memeriksa kontribusi aktual. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Restore operasi 5 selalu menghasilkan roll 10, satu reversal movement dan projection 10, termasuk fault restore dan dua worker; jangan double-increment saat response hilang.

**Hubungan dengan catatan lain:** GN-06, GN-11

## V3-MRES-01 — Dua PR mencadangkan bahan lebih banyak daripada stok

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/material_reservation_service.py:79](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/material_reservation_service.py#L79).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** free_for_commitment dibaca lalu material_reservations diinsert tanpa claim capacity atau unique reservation logical key. Dua PR dapat membaca jumlah bebas sama.

**Dampak dan batas interpretasi:** Dua approved PR masing-masing 700, recipe yield 1 dan stok 1000 menghasilkan active reservation 1400; shortage 0 pada kedua PR. Barrier hanya menyelaraskan read, tetap memanggil helper asli.

- `V3-MRES-01` — expected `"See original invariant and detailed acceptance"`; actual `{"on_hand_available": 1000, "reserved": 1400.0, "shortage": 0.0, "pr_count": 2}`; `observed_difference`.

```python
  76:         if not pid or need <= 0:
  77:             continue
  78:         entity_id = pr.get("entity_id") or ""
  79:         free = await free_for_commitment(pid, entity_id)
  80:         qty = round(min(need, free), 3)
  81:         doc = {"id": new_id("mres"), "product_id": pid, "owner_entity_id": entity_id,
  82:                "ref_type": "purchase_requisition", "ref_id": pr_id, "pr_id": pr_id, "pr_number": pr.get("number"),
  83:                "pr_line_no": line_no, "output_product_id": line["product_id"],
  84:                "target_output_qty": pre.get("target_output_qty"), "recipe": pre.get("recipe"),
  85:                "required_qty": need, "qty": qty, "shortage_qty": round(need - qty, 3),
  86:                "source_ref_id": pr.get("source_ref_id") or "", "status": ACTIVE,
```

**Prompt perbaikan:**

> Periksa `V3-MRES-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Serialisasi commitment pada key product+owner+unit dan dimensi gudang bila relevan. Reservasi harus CAS terhadap ledger kapasitas yang konsisten dengan sales/MKO; unique PR line/version untuk retry; shortage dilaporkan eksplisit. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Parallel 700+700 atas 1000 tidak pernah reserved>1000. Remaining 400 harus shortage/backorder/approval sesuai policy, tidak dianggap tersedia. Uji race dengan SO, issue/cancel/replan dan input UOM berbeda.

**Hubungan dengan catatan lain:** W2-REQ-07, W2-REQ-04

## V3-AR-01 — Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/ar_receipt_service.py:448](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/ar_receipt_service.py#L448).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Receipt mengurangi deposit, mengalokasikan payments ke SO, baru insert receipt. Except mengembalikan deposit tetapi tidak membatalkan alokasi SO. Tidak ada receipt durable untuk resume.

**Dampak dan batas interpretasi:** Saldo deposit 100; fault sebelum insert ar_receipts: SO paid_total100/payments 1, customer deposit 100, receipt count 0. Saldo yang sama bisa dipakai lagi.

- `V3-AR-01` — expected `"See original invariant and detailed acceptance"`; actual `{"error": "RuntimeError('Synthetic receipt insert fault BEFORE write')", "paid_total": 100.0, "payments": 1, "deposit": 100.0, "receipts": 0}`; `observed_difference`.

```python
 445:     receipt_id = new_id("arc")
 446:     number = await next_doc_number("ar_receipts", "number", "AR-", entity_id=entity_id)
 447:     # W2-017 — dana deposit DIRESERVASI (CAS) sebelum alokasi SO; gagal → 409 tanpa efek apa pun.
 448:     await _adjust_deposit(customer["id"], -use_deposit_amount)
 449:     try:
 450:         return await _create_receipt_after_reserve(payload, actor, customer, amount, use_deposit_amount,
 451:                                                    total_funds, method, receipt_date, entity_id,
 452:                                                    receipt_id, number)
 453:     except BaseException:
 454:         if not await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 1}):
 455:             await _adjust_deposit(customer["id"], use_deposit_amount)   # kompensasi reservasi
```

**Prompt perbaikan:**

> Periksa `V3-AR-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist receipt operation sebelum allocations. Setiap alokasi harus terkait stable receipt ID dan dapat resume/compensate tanpa menghapus payment milik operasi lain. Tangani insert/GL/cash/deposit sebagai satu protokol durable. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum receipt insert, setelah SO allocation, sebelum/sesudah GL dan saat rollback. Akhir harus semua effect 100 tepat sekali atau semua batal; tidak ada SO paid tanpa receipt/deposit konsumsi. Uji multi-SO dan pembayaran bersamaan.

**Hubungan dengan catatan lain:** FN-10, W2-017

## V3-BANK-01 — Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/bank_recon_service.py:614](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_recon_service.py#L614).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** CAS membatasi capacity cash transaction, tetapi statement line ditulis berdasarkan ID tanpa claim status/version/capacity yang sama. Dua transaksi berbeda dapat sama-sama mengklaim line bank.

**Dampak dan batas interpretasi:** Statement 100; dua manual_match berbeda 100+100: line allocated 100, cash reconciled 200, kedua cash mencantumkan matched_line_ids BL.

- `V3-BANK-01` — expected `"See original invariant and detailed acceptance"`; actual `{"statement_amount": 100, "statement_allocated": 100.0, "cash_reconciled": 200.0, "linked_cash_count": 2}`; `observed_difference`.

```python
 611:             raise ValueError("Sisa transaksi buku tidak cukup (baru saja dipakai proses lain / alokasi ganda).")
 612:         claimed.append({"txn_id": a["txn_id"], "amount": amt})
 613:     txn_ids = [a["txn_id"] for a in allocations]
 614:     await db.bank_statement_lines.update_one({"id": line["id"]}, {"$set": {
 615:         "status": "matched", "match_kind": match_kind,
 616:         "matched_txn_id": txn_ids[0] if len(txn_ids) == 1 else "",
 617:         "matched_txn_ids": txn_ids, "allocations": allocations,
 618:         "match_type": match_type, "matched_at": now, "matched_by": actor,
 619:         "updated_at": now}})
 620:     for a in allocations:
 621:         t = await db.cash_transactions.find_one({"id": a["txn_id"]}, {"_id": 0})
```

**Prompt perbaikan:**

> Periksa `V3-BANK-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Claim kedua sisi allocation dengan stable match operation dan transaksi/compensation idempoten. Revalidate statement remaining setelah claim; jangan hanya melindungi tiap cash record. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Dua matching paralel atas line 100: satu sukses dan satu conflict atau total allocated 100. Jumlah dari statement links harus sama dengan cash links. Uji split, duplicate payload, unlink/rerun/fault antar-write.

**Hubungan dengan catatan lain:** CX-07, CX-06

## V3-WEIGHT-01 — Split bersamaan menggandakan berat walaupun panjang benar

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/roll_service.py:163](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L163).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** insert_child_roll menghitung berat dari snapshot parent lama dan menulis sisa dengan $set; length CAS terpisah tidak menjaga weight total.

**Dampak dan batas interpretasi:** Parent 10m/3kg dipotong 2m dua kali: parent 6m/2.4kg, dua child masing-masing 0.6kg; total 3.6kg, seharusnya 3kg. Panjang 6+2+2 tetap 10.

- `V3-WEIGHT-01` — expected `"See original invariant and detailed acceptance"`; actual `{"initial_length": 10, "remaining_length": 6.0, "initial_weight": 3, "parent_weight": 2.4, "child_weights": [0.6, 0.6], "total_weight": 3.5999999999999996}`; `observed_difference`.

```python
 160:         s["secondary_measures.kg"] = weight
 161:         parent["secondary_measures"] = {**parent["secondary_measures"], "kg": weight}
 162:     parent["weight_kg"] = weight
 163:     await db.inventory_rolls.update_one({"id": parent.get("id")}, {"$set": s})
 164: 
 165: 
 166: # ── Taksonomi status (KN_15 §3.4) ────────────────────────────────────────────
 167: # Bucket FISIK di gudang (menyusun on_hand)
 168: from services.tolerances import QTY_EPS  # KN-A13 — toleransi bersama
 169: 
 170: # KN-A11 — SATU definisi "PO masih terbuka / stok dalam perjalanan" untuk papan Stok/ATP,
```

**Prompt perbaikan:**

> Periksa `V3-WEIGHT-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Simpan reservasi/split berat dan panjang dalam satu conditional update berdimensi version atau ledger cut dengan snapshot terkini. Tidak boleh menulis derived parent weight dari snapshot lama. Tandai estimated_proportional sebagai estimasi, bukan penimbangan aktual. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Parallel split 2+2: parent 6m/1.8kg dan children 0.6+0.6kg. Uji split QC/retur/cut, decimal rounding dan actual reweigh; conservation kg dan meter diuji terpisah.

**Hubungan dengan catatan lain:** W2-019, WM-01

## V3-PO-01 — Task selisih PO tidak refresh dan kehilangan identitas baris

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/po_variance_task_service.py:51](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/po_variance_task_service.py#L51).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Key task memakai product_id, bukan line_id, dan existing task langsung continue. Received yang berubah tidak memperbarui task/suggested qty. Duplicate product pada PO baru diblokir KN-B15, tetapi dokumen historis masih dapat memiliki dua baris.

**Dampak dan batas interpretasi:** Task awal received 90/short 10; setelah received 95 task tetap 90/10. Fixture legacy dua line MAT dengan shortage 5 dan 100 menghasilkan satu task. Staleness berlaku juga PO satu line biasa.

- `V3-PO-01` — expected `"See original invariant and detailed acceptance"`; actual `{"actual_shortages": [5, 100], "task_count": 1, "task_received": 90.0, "task_short": 10.0, "live_first_received": 95}`; `observed_difference`.

```python
  48:         short = round(ordered - received, 2)
  49:         if received <= 0 or short <= ordered * tol / 100 + 1e-6:
  50:             continue
  51:         key = {"po_id": po_id, "product_id": it.get("product_id"), "status": "open"}
  52:         if await db.po_variance_tasks.find_one(key, {"_id": 1}):
  53:             continue
  54:         task = {
  55:             "id": new_id("pvt"), **key, "entity_id": po.get("entity_id"),
  56:             "po_number": po.get("po_number"), "supplier_name": po.get("supplier_name"),
  57:             "product_name": it.get("product_name") or it.get("name") or "", "unit": it.get("unit", ""),
  58:             "ordered_qty": ordered, "received_qty": received, "short_qty": short, "tolerance_pct": tol,
```

**Prompt perbaikan:**

> Periksa `V3-PO-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Key task harus stable PO line ID/version. Refresh ordered/received/short dan close task bila selesai; keputusan memakai revalidation PO terkini. Migrasi legacy duplicate secara eksplisit, jangan menggabungkan dua harga. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Terima 90 lalu 95: open task received 95/short 5, amendment suggestion 95. Terima 100 menutup obsolete task. Dua legacy line memberi dua task. Race receipt vs decide tidak memakai qty lama.

**Hubungan dengan catatan lain:** W2-REQ-06, FN-02

## V3-MKO-01 — Retry penerimaan maklon menambah output fisik dan nilai stok

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/makloon_order_service.py:1093](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/makloon_order_service.py#L1093).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Progress lots disimpan sesudah seluruh loop output. Output pertama yang sudah dibuat tidak tersimpan dalam progress jika pembuatan kedua gagal. Retry membuat seluruh roll lagi.

**Dampak dan batas interpretasi:** Input 10, dua output 5; fault sebelum create output kedua:1 roll. Retry:3 roll=15; inventory value 180 sedangkan jurnal receipt 120 untuk output 10.

- `V3-MKO-01` — expected `"See original invariant and detailed acceptance"`; actual `{"error": "RuntimeError('Synthetic second output failure BEFORE write')", "rolls_after_fault": 1, "rolls_after_retry": 3, "expected_output": 10, "actual_output": 15.0, "roll_value": 180.0, "journal_value": 120.0}`; `observed_difference`.

```python
1090:     _mko_ref = {"type": "makloon_order", "id": mko_id,
1091:                 "number": f"{order.get('mko_number')} step{seq}"}
1092:     _last = len(rolls_in) - 1
1093:     for _i, r in enumerate(rolls_in if not prog.get("lots") else []):
1094:         _len = round(float(r["length"]), 2)
1095:         _uc = out_uc
1096:         if _i == _last and _len > 0:
1097:             _prior = sum(round(round(float(x["length"]), 2) * out_uc, 2) for x in rolls_in[:_last])
1098:             _uc = round((output_value - _prior) / _len, 6)
1099:         roll = await create_inbound_roll(
1100:             out_pid, r.get("warehouse_id") or out_wh, entity_id, _len,
```

**Prompt perbaikan:**

> Periksa `V3-MKO-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Beri deterministic roll identity per operation+receipt line/index sebelum loop. Persist plan dan state tiap output sebelum/bersama creation; resume harus reconcile actual roll dan movement sebelum membuat lagi. Simpan original warehouse/lot/cost snapshot. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault pada output 1/2/N serta setelah jurnal/status: output total 10 dan dua roll saja, inventory value sama GL120. Uji partial multi-gudang, duplicate lot input, response-lost dan authorized saga recovery.

**Hubungan dengan catatan lain:** CX-13, W2-001, GN-11

## V3-RFID-01 — Read green dari passage lama dipakai kembali pada passage baru

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/rfid_ingest_service.py:149](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L149).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Cache dwell 120 detik mengembalikan verdict read sebelumnya sebelum evaluator dijalankan. Passage window 10 detik; event_id baru 20 detik kemudian membentuk passage baru tetapi tetap memakai verdict lama.

**Dampak dan batas interpretasi:** Event pertama green dan mencatat gate_exit. Sesudah SO cancelled, event UUID baru pada gate sama+20 detik tetapgreen duplicate=true dan passage ID berbeda; evaluator state sekarang red REPLAY_EXIT.

- `V3-RFID-01` — expected `"See original invariant and detailed acceptance"`; actual `{"first": "green", "fresh_event_after_seconds": 20, "second": "green", "duplicate": true, "current_evaluator_result": "red", "current_evaluator_code": "REPLAY_EXIT", "different_passage": true}`; `observed_difference`.

```python
 146:     dwell_cut = (_ts(now) - timedelta(seconds=DWELL_S)).isoformat()
 147:     results, reads = [], []
 148:     for raw in fresh:
 149:         prev = await db.rfid_reads.find_one({"device_id": device["id"], "epc": raw, "timestamp": {"$gte": dwell_cut}},
 150:                                             {"_id": 0}, sort=[("timestamp", -1)])
 151:         if prev:  # tag diam / passage sama — bukan event bisnis baru (tanpa insiden baru)
 152:             await db.rfid_reads.update_one({"id": prev["id"]}, {"$set": {"last_observed_at": now},
 153:                                                                "$inc": {"observation_count": 1}})
 154:             results.append({"epc": raw, "result": prev["result"], "code": prev.get("code"), "reason": prev["reason"],
 155:                             "action": prev.get("action"),
 156:                             "roll_no": prev.get("roll_no"), "sku": prev.get("sku"),
```

**Prompt perbaikan:**

> Periksa `V3-RFID-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bedakan replay event ID dan noisy repeated sensor read dari otorisasi passage baru. Cache tidak boleh melintasi passage atau versi shipment/QC/tag; evaluasi ulang current state untuk event baru yang memulai passage. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Same-gate event berbeda pada+20 detik harus red ketika replay exit/SO cancelled/tag retired/QC hold. Repeated event_id tetap idempoten. Dwell dalam passage tidak menggandakan mutation/incident; worst verdict passage tetap red.

**Hubungan dengan catatan lain:** RF-02, RF-16

## V3-CF-01 — Jurnal campuran kas/nonkas menghasilkan klasifikasi arus kas salah

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/cash_flow_service.py:84](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cash_flow_service.py#L84).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Bila satu jurnal menyentuh kas, semua contra line dimasukkan bucket aktivitas. Aset yang sebagian dibayar kas dan sebagian AP dianggap seluruhnya cash investing serta AP dianggap cash operating.

**Dampak dan batas interpretasi:** Jurnal Dr aset 100/Cr kas 40/Cr AP60 menghasilkan investing−100, operating+60, net−40 dan noncash disclosure kosong. Seharusnya investing−40, operating 0 dan noncash asset 60.

- `V3-CF-01` — expected `"See original invariant and detailed acceptance"`; actual `{"expected_investing": -40, "expected_operating": 0, "expected_noncash_asset": 60, "actual_investing": -100.0, "actual_operating": 60.0, "net_change": -40.0, "noncash": []}`; `observed_difference`.

```python
  81:     noncash: Dict[str, float] = {}
  82:     async for je in db.journal_entries.find(q, {"_id": 0, "lines": 1}):
  83:         lines = [ln for ln in je.get("lines", []) if ln.get("account_code")]
  84:         touches_cash = any(ln["account_code"] in cash for ln in lines)
  85:         for ln in lines:
  86:             code = ln["account_code"]
  87:             if code in cash:
  88:                 continue
  89:             eff = -(float(ln.get("debit", 0) or 0) - float(ln.get("credit", 0) or 0))
  90:             sec = _section(amap.get(code, {}).get("type", ""), code)
  91:             if touches_cash:
```

**Prompt perbaikan:**

> Periksa `V3-CF-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Klasifikasi sumber harus membawa settlement cash portion yang eksplisit. Pecah source/mixed journal secara traceable; jangan memperkirakan aktivitas dari seluruh contra balance. Reconcile total kas dan disclosure noncash terpisah. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fixture asset cash 40+credit 60 harus CFI−40/CFO 0/noncash 60. Tambahkan asset penuh kredit, cash penuh, bank-to-bank, depreciation, sale credit+receipt dan mixed multiple assets/liabilities. Persetujuan policy akuntan diperlukan untuk metode alokasi ambigu.

**Hubungan dengan catatan lain:** FN-04

## V3-DATE-01 — Jurnal date-only pada awal periode hilang dari laporan

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/financial_statement_service.py:31](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L31).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Insert jurnal mempertahankan date yang dikirim, termasuk YYYY-MM-DD. Query start membuat string YYYY-MM-DDT 00:00:00; lexical compare mengeluarkan date-only hari pertama.

**Dampak dan batas interpretasi:** Valid journal beban 10 pada 2026-09-01, laporan 2026-09-01..30: opex 0, seharusnya 10. Nilai tersimpan masih date-only; probe CF lain memakai ISO timestamp agar kesalahan klasifikasi tidak tercampur.

- `V3-DATE-01` — expected `"See original invariant and detailed acceptance"`; actual `{"expected_opex": 10, "actual_opex": 0, "stored_date": "2026-09-01", "filter_start": "2026-09-01T00:00:00"}`; `observed_difference`.

```python
  28: def _day_start(d: Optional[str]) -> Optional[str]:
  29:     if not d:
  30:         return None
  31:     return d if "T" in d else f"{d}T00:00:00"
  32: 
  33: 
  34: def _day_end(d: Optional[str]) -> Optional[str]:
  35:     if not d:
  36:         return None
  37:     return d if "T" in d else f"{d}T23:59:59.999999"
  38: 
```

**Prompt perbaikan:**

> Periksa `V3-DATE-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan representasi tanggal kanonik di seluruh entry/create/autopost/import dan query, dengan timezone bisnis disepakati. Migration preview tanggal lama dan conflict report; hindari mengubah label saja atau memperlebar cutoff tanpa aturan. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Date-only/ISO/tz-offset hari awal dan hari akhir periode masuk tepat sekali. Neraca default, ledger, cash flow, closing, unlock dan konsolidasi memakai cutoff sama. Uji jurnal masa depan tetap tidak masuk hari ini.

**Hubungan dengan catatan lain:** FN-16, W2-021

## V3-WMS-02 — Loading gudang siap ditahan oleh pending cut gudang lain

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/loading_check_service.py:38](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/loading_check_service.py#L38).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Start loading check memanggil guard atas seluruh SO dan API tidak memberi warehouse/shipment subset. SO-wide session mencampurkan readiness shipment yang berbeda.

**Dampak dan batas interpretasi:** Satu tagged committed roll diWH siap; pending cut product lain diWH 2. Guard local WH lulus, start loading check SO409: satu reservasi potong belum dikonfirmasi di gudang lain.

- `V3-WMS-02` — expected `"See original invariant and detailed acceptance"`; actual `{"local_ready_tagged_rolls": 1, "local_cut_guard": "passed", "pending_cuts_other_warehouse": 1, "loading_check_start_error": "409: 1 reservasi potong belum dikonfirmasi (roll induk RL-00010). Potong fisik & konfirmasi dulu."}`; `observed_difference`.

```python
  35:     if existing:
  36:         return safe_doc(existing)
  37:     from services.roll_service import assert_cut_identity_ready
  38:     await assert_cut_identity_ready(order_id)  # WM-02 — potong dikonfirmasi & tag anak terverifikasi
  39:     rolls = await _expected_rolls(order_id)
  40:     if not rolls:
  41:         raise HTTPException(status_code=400, detail="Tidak ada roll ter-alokasi untuk SO ini (pick dulu).")
  42:     tag_ids = [r["rfid_tag_id"] for r in rolls if r.get("rfid_tag_id")]
  43:     tags = {t["id"]: t for t in await db.rfid_tags.find(
  44:         {"id": {"$in": tag_ids}, "status": "active"}, {"_id": 0}).to_list(2000)}
  45:     expected, untagged = [], []
```

**Prompt perbaikan:**

> Periksa `V3-WMS-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Bentuk loading session per shipment/task group+warehouse+manifest version. Expected EPC dan cut guard hanya untuk shipment itu; perubahan manifest mengharuskan check ulang. Parent SO menampilkan agregat progres, bukan satu clean global. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** SO woven/knit/printing tiga gudang: WHwoven dapat check/dispatch/SJ sendiri saat cut WHknit tertunda. Check A tidak membuka B. Shipment parsial dan driver gabungan tetap mempunyai manifest dokumen yang konsisten.

**Hubungan dengan catatan lain:** RF-06, W2-REQ-08

## V3-MASTER-01 — Apply master mengubah produk sebelum snapshot batch durable

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/master_governance_service.py:96](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/master_governance_service.py#L96).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Apply mengubah produk dan last_governance_batch lalu insert dokumen batch before/after. Jika insert gagal, perubahan tidak mempunyai snapshot rollback.

**Dampak dan batas interpretasi:** Stage produk greige→grey dan last_governance_batch terisi; fault sebelum insert batch: durable_batch_count0. Rollback batch yang dijanjikan tidak tersedia.

- `V3-MASTER-01` — expected `"See original invariant and detailed acceptance"`; actual `{"error": "RuntimeError('Synthetic batch journal failure BEFORE write')", "original_stage": "greige", "current_stage": "grey", "batch_reference": "mgb_5a8480b0aa4d", "durable_batch_count": 0}`; `observed_difference`.

```python
  93:                             "before": p["from"], "after": p["to"]})
  94:     batch = {"id": batch_id, "status": "applied", "note": (note or "").strip(), "changes": changes,
  95:              "preview_signature": signature, "applied_by": actor.get("name", ""), "applied_at": now_iso()}
  96:     await db.master_governance_batches.insert_one(dict(batch))
  97:     return safe_doc(batch)
  98: 
  99: 
 100: async def rollback_batch(batch_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
 101:     if len((reason or "").strip()) < 5:
 102:         raise HTTPException(status_code=422, detail="Alasan rollback wajib (min. 5 karakter).")
 103:     b = await db.master_governance_batches.find_one_and_update(
```

**Prompt perbaikan:**

> Periksa `V3-MASTER-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist batch plan/hash/before snapshots dan stage prepared sebelum produk diubah; pakai CAS version tiap produk dan idempoten operation. Progress parsial harus bisa resume/rollback tanpa menimpa edit sesudahnya. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault sebelum/antara product update dan batch insert menghasilkan batch recoverable atau tidak ada perubahan. Uji multi-produk, edits concurrent, dry-run signature stale, rollback conflict dan retry identitas sama.

**Hubungan dengan catatan lain:** W2-REQ-02

## V3-PO-02 — Pilihan amend ke jumlah diterima bertentangan dengan guard PO lama

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/po_amendment_service.py:103](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/po_amendment_service.py#L103).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Task baru menjanjikan amendment qty aktual, tetapi guard lama mengunci quantity setiap baris yang received_qty>0. Ini gap integrasi dua aturan bisnis, bukan alasan untuk menghapus guard seluruh field finansial.

**Dampak dan batas interpretasi:** Ordered 1000/received 960; suggested amendment 960. amend_po menolak 400 qty 1000→960 walaupun tidak kurang dari received dan tujuannya menutup kekurangan.

- `V3-PO-02` — expected `"See original invariant and detailed acceptance"`; actual `{"ordered": 1000, "received": 960, "suggested_amendment": 960, "error": "400: Baris MAT sudah diterima 960 — terkunci dari revisi (qty 1000→960). Barang yang sudah masuk gudang tidak bisa diubah qty/satuan/harga/diskonnya; buat PO baru untuk tambahan, atau retur beli bila ada selisih."}`; `observed_difference`.

```python
 100:     if not old:
 101:         return
 102:     changed = []
 103:     if abs(float(item_in.quantity or 0) - float(old.get("quantity") or 0)) > 0.001:
 104:         changed.append(f"qty {float(old.get('quantity') or 0):g}→{float(item_in.quantity):g}")
 105:     old_unit = str(old.get("unit") or "").strip().lower()
 106:     new_unit = str(item_in.unit or old.get("unit") or "").strip().lower()
 107:     if new_unit != old_unit:
 108:         changed.append(f"satuan {old.get('unit')}→{item_in.unit}")
 109:     new_price = float(item_in.price or 0)
 110:     if new_price > 0 and abs(new_price - float(old.get("price") or 0)) > 0.001:
```

**Prompt perbaikan:**

> Periksa `V3-PO-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Tetapkan flow dedicated receiving-variance amendment atau perbaiki CTA menjadi short-close sesuai policy disepakati. Jika amendment dipilih, target tidak kurang dari received, snapshot/bill/DP dilindungi dan reapproval/credit adjustment eksplisit; jangan rewrite posted GL. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Kasus 1000→960 memiliki jalur selesai yang nyata dan tidak buntu. Received tetap 960; PO version/approval terdokumentasi; vendor bill/AP/DP diperhitungkan terpisah. Jika hanya short-close diperbolehkan, UI tidak menjanjikan amend unsupported.

**Hubungan dengan catatan lain:** W2-REQ-06

## V3-CUT-01 — Gagal membuat child cut menghilangkan stok dan reservasi

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/roll_service.py:614](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L614).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Parent decrement dan pull reservation dilakukan sebelum child insert. Bila insert gagal sebelum write, tidak ada durable cut command yang dapat melanjutkan dan reservation telah hilang.

**Dampak dan batas interpretasi:** Awal 10/reserve 3; fault child insert: parent 7, reserved 0, child 0. Retry confirm_cut404 reservasi tidak ditemukan/sudah dipotong. Stok fisik total data berkurang 3 tanpa child.

- `V3-CUT-01` — expected `"See original invariant and detailed acceptance"`; actual `{"before_length": 10, "after_length": 7.0, "length_reserved": 0, "child_count": 0, "error": "Synthetic cut child insert fault BEFORE write", "retry_error": "404: Reservasi potong tidak ditemukan / sudah dipotong"}`; `observed_difference`.

```python
 611:         "status": rsv.get("status") or "reserved", "reserved_ref": rsv["ref"], "earmarked_for": None,
 612:         "is_remnant": False, "cut": cut, "journey": {"stage": "cut_pending_tag", "updated_at": now_iso()},
 613:         "created_at": now_iso(), "updated_at": now_iso()})
 614:     child = await insert_child_roll(child, parent)
 615:     await db.inventory_movements.insert_one({
 616:         "id": new_id("mov"), "product_id": parent["product_id"], "warehouse_id": parent["warehouse_id"],
 617:         "owner_entity_id": parent.get("owner_entity_id"), "movement_type": "roll_cut",
 618:         "quantity": 0, "unit": parent.get("unit", "meter"), "lot": parent.get("lot", ""),
 619:         "roll_id": child["id"], "parent_roll_id": roll_id, "qty_rolls": 1,
 620:         "source_document": rsv["ref"]["id"], "cut": cut, "timestamp": now_iso()})
 621:     if waste > 0:
```

**Prompt perbaikan:**

> Periksa `V3-CUT-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Persist cut operation dan output identity stabil sebelum mutation; parent/reservation/child/movement/weight/tag lifecycle satu transaksi atau recoverable state machine. Retry mencari cut operation lama, bukan hanya reservation yang sudah dipull. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fault setiap tahap cut 100→70+30 selalu conservation quantity/value/weight+documented waste; retry menghasilkan satu child dan satu movement, tag identity baru harus diverifikasi sebelum loading. Tidak boleh menambah kembali parent bila child sudah ada.

**Hubungan dengan catatan lain:** WM-01, WM-02, W2-REQ-09, GN-11

## V3-MRES-02 — Total cadangan maklon tetap terpotong pada batas query

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/services/material_reservation_service.py:44](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/material_reservation_service.py#L44).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** reserved_by_others memakai 2000, _on_hand_available500 dan apply_to_products5000 untuk total bisnis, bukan daftar berhalaman. Cadangan yang dilewatkan dapat dijanjikan lagi ke sales.

**Dampak dan batas interpretasi:** 2001 active reservation masing-masing 1 menghasilkan reserved_by_others2000. Selisih 1 terukur; batas 500/5000 lain dikonfirmasi statis, belum diuji runtime pada probe ini.

- `V3-MRES-02` — expected `"See original invariant and detailed acceptance"`; actual `{"expected_reserved": 2001, "actual_reserved": 2000.0, "document_count": 2001}`; `observed_difference`.

```python
  41:     q: Dict[str, Any] = {"product_id": product_id, "owner_entity_id": entity_id, "status": ACTIVE}
  42:     if exclude_ref_id:
  43:         q["ref_id"] = {"$ne": exclude_ref_id}
  44:     rows = await db.material_reservations.find(q, {"_id": 0, "qty": 1}).to_list(2000)
  45:     return round(sum(float(r.get("qty") or 0) for r in rows), 3)
  46: 
  47: 
  48: async def free_for_commitment(product_id: str, entity_id: str, exclude_ref_id: str = "",
  49:                               warehouse_id: str = "") -> float:
  50:     return round(max(await _on_hand_available(product_id, entity_id, warehouse_id)
  51:                      - await reserved_by_others(product_id, entity_id, exclude_ref_id), 0.0), 3)
```

**Prompt perbaikan:**

> Periksa `V3-MRES-02` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Gunakan aggregate/kursor penuh untuk seluruh total. Batasi hanya endpoint list berhalaman dengan total terpisah. Harmonisasi owner, product, unit, warehouse dan exclusion ref agar sales dan PR memakai angka sama. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Cap−1/cap/cap+1 pada 2000 reservations,500 balances,5000 catalog reservations serta>10000 roll allocation harus konsisten. Test total/UI/guard commit dan cancellation tidak memakai subset sebagai SSOT.

**Hubungan dengan catatan lain:** GN-12, W2-REQ-07, W2-REQ-04

## V3-PO-03 — Tugas selisih selesai meski amendment belum disetujui dan qty belum berubah

**Prioritas:** P1 · **Status:** confirmed_open · **Bukti:** runtime_counterexample.

**Letak:** [backend/routers/purchase_orders.py:751](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/purchase_orders.py#L751).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Router menyelesaikan seluruh pending_amendment segera sesudah amend_po, sebelum reapproval. Fungsi juga tidak memeriksa apakah perubahan berkaitan dengan shortage line.

**Dampak dan batas interpretasi:** HTTP notes-only amend 200: PO quantity 1000 tetap dan statuswaiting_approval; task shortage received 960 menjadi decided. Persetujuan kuantitas belum terjadi.

- `V3-PO-03` — expected `"See original invariant and detailed acceptance"`; actual `{"http_status": 200, "po_status": "waiting_approval", "po_quantity": 1000, "task_status": "decided", "detail": null}`; `observed_difference`.

```python
 748:     result = await amend_po_service(po_id, payload, actor)
 749:     updated = result["po"]
 750:     from services import po_variance_task_service as _pvt
 751:     await _pvt.close_amendment_tasks(po_id, actor["name"])  # W2-REQ-06
 752:     if result["needs_approval"]:
 753:         from services.notification_service import notify_po_awaiting_approval
 754:         await notify_po_awaiting_approval(updated)
 755:     else:
 756:         await _create_inbound_tasks_for_po(updated)
 757:     return safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))
 758: 
```

**Prompt perbaikan:**

> Periksa `V3-PO-03` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Selesaikan task hanya setelah amendment version/line yang ditautkan approved dan acceptance shortage direvalidasi. Notes-only amendment tidak menutup qty task. Rejection/cancel amendment memulihkan action pending yang benar. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Amend notes saja atau awaiting approval: task pending. Approved qty 960/reconciled policy: task selesai. Rejection tetap memerlukan keputusan. Beberapa task/line/versi tidak tertutup sekaligus oleh perubahan unrelated.

**Hubungan dengan catatan lain:** W2-REQ-06

## V3-DUP-01 — Helper _clean_perms didefinisikan dua kali

**Prioritas:** P3 · **Status:** confirmed_open · **Bukti:** static_quality_observation.

**Letak:** [backend/services/custom_role_service.py:60](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/custom_role_service.py#L60).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** AST seluruh backend menemukan dua definisi top-level identik pada baris 60 dan 67. Definisi kedua menimpa pertama; body kini sama sehingga ini maintainability debt, bukan beda perilaku akses.

**Dampak dan batas interpretasi:** Dua definisi identik pada file yang sama; syntax parser tidak menolaknya.

**Observasi:** Dua definisi identik pada file yang sama; syntax parser tidak menolaknya.

```python
  57:     return out
  58: 
  59: 
  60: def _clean_perms(perms: Any) -> Dict[str, List[str]]:
  61:     try:
  62:         return clean_permissions(perms)
  63:     except ValueError as exc:
  64:         raise HTTPException(status_code=400, detail=str(exc)) from exc
  65: 
  66: 
  67: def _clean_perms(perms: Any) -> Dict[str, List[str]]:
```

**Prompt perbaikan:**

> Periksa `V3-DUP-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Hapus definisi identik dengan satu canonical helper; tambahkan deteksi duplicate top-level definition dalam quality check yang sesuai, tanpa menggandakan business-rule tests. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Satu definisi, custom permission normal/error contract tetap sama. Jangan menjadikan ini P1 atau menghitungnya sebagai bug akses yang sudah terbukti.

**Hubungan dengan catatan lain:** GN-15

## V3-BUILD-01 — Dependency build frontend tidak mempunyai lockfile terlacak

**Prioritas:** P2 · **Status:** confirmed_open · **Bukti:** static_quality_observation.

**Letak:** [frontend/package.json:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/package.json#L151).



**Tampilan / rantai terkait:** Lihat ID terkait dan sumber pada tracker. · Lihat penjelasan dampak operasi di bawah..

**Penyebab:** Repo mendeklarasikan Yarn 1.22.22 tetapi tidak melacak yarn.lock, package-lock.json atau pnpm-lock.yaml. Fresh install harus meresolusikan dependency transitive; dua build tidak mempunyai dependency graph terkunci.

**Dampak dan batas interpretasi:** Install lokal melaporkan No lockfile found; build berhasil dengan warnings memakai dependency graph yang diselesaikan hari audit. Ini risiko reproducibility, bukan bukti frontend gagal build.

**Observasi:** Install lokal melaporkan No lockfile found; build berhasil dengan warnings memakai dependency graph yang diselesaikan hari audit. Ini risiko reproducibility, bukan bukti frontend gagal build.

```json
 148:     "**/tinyglobby/picomatch": "4.0.4",
 149:     "http-proxy-middleware": "2.0.10"
 150:   },
 151:   "packageManager": "yarn@1.22.22+sha512.a6b2f7906b721bba3d67d4aff083df04dad64c399707841b7acf00f6b133b7ac24255f2652fa22ae3534329dc6180534e98d17432037ff6fd140556e2bb3137e"
 152: }
```

**Prompt perbaikan:**

> Periksa `V3-BUILD-01` pada commit `a904d989b622f7da14c4892d03cf6ef0c43f3084` dan telusuri producer, service, projection, API, frontend serta reversal/retry terkait. Commit satu lockfile canonical sesuai packageManager; pipeline harus gagal jika lock tidak ada/berbeda dan memakai frozen/immutable install. Simpan runtime versions dan dependency integrity. Jangan commit node_modules/build/.env. Pertahankan batas entitas dan hak akses. Jangan sekadar membuat tes lama hijau atau mengubah expected agar cocok dengan bug. Catat perubahan, commit, bukti uji dan dampak ke consumer lain; tandai `implemented_pending_validation`, bukan `verified_fixed`.

**Kriteria penerimaan:** Fresh isolated install pada dua runner memakai graph/integrity sama. Build smoke lulus dari lock, lint warning relevan ditinjau; packageManager dan pipeline tidak saling memilih manager berbeda.

**Hubungan dengan catatan lain:** GN-15



---

# Cakupan audit yang benar-benar tercatat

Source dibekukan pada `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Repository bergerak dari `d6da1a3d536228582645abb98aea19f3e491f300` selama sesi, sehingga pengujian utama, 17 counterexample lama, counterexample numerik, GET sweep dan 60 skrip regresi diulang pada kandidat terbaru. Hasil tahap lama dipertahankan sebagai histori. Database uji sintetis lokal digunakan; tidak ada transaksi produksi atau push perubahan aplikasi.

**Coverage perilaku 100% belum tercapai.** Inventaris semua file sudah tersedia, tetapi inventaris, parse, build dan satu baris handler yang dieksekusi bukan bukti bahwa semua kode dan semua flow bisnis sudah benar.

| Lapisan | Hasil pada kandidat terbaru | Batas makna |
|---|---|---|
| Inventaris tracked | 5,824 file; hash per file | File nonkode dan artefak audit juga termasuk; bukan pembacaan semantik seluruh baris |
| Parse source | 1.260 Python + 859 JavaScript = 2.119 file; tanpa parse error | Tidak membuktikan logika atau rendering |
| Inventaris statis | 13.151 fungsi; 1.411 decorated routes; 1.477 literal API calls frontend | Route statis berbeda denominator dari registered API methods; panggilan dinamis belum seluruhnya dipetakan |
| Frontend → registered API → service |1431/1477 literal calls terpetakan; 46 belum |Menggunakan full route prefix dari aplikasi terdaftar dan literal alias yang tidak ambigu; dynamic action/helper tetap unresolved |
| Registered API methods | 1410 | Termasuk kombinasi route/method; bukan jumlah business flow |
| Handler dengan bukti body dieksekusi | 1024 | Guard/error juga dapat memasuki body; tidak otomatis successful authorized flow |
| Mutation methods | 772; body tercatat pada 398; 374 tanpa bukti body | CSV menyimpan setiap route yang masih memerlukan pengujian lifecycle |
| GET sweep | 589/638 dieksekusi; 539 pernah mendapat 200; 49 belum dieksekusi | Angka benar harus dicek dengan oracle; HTTP 200 saja tidak cukup |
| GET exceptions / HTTP >=500 | 0 exceptions; 0 route mencatat status >=500 pada sweep | Hanya fixture sweep ini, bukan jaminan tidak ada error di produksi |
| Full pytest | 1539 pass / 484 fail / 76 skip / 173 error; 2272 testcase records | 484 kegagalan bukan 484 bug; fixture dan test contract perlu adjudikasi |
| Tiga modul tes baru | 14 pass / 3 fail / 5 skip | Ada ketergantungan hardcoded fixture dan fallback PR; bukan seluruh real fulfillment E2E |
| Core replay | 309/310 pass, 15 skrip | Satu fixture RF-05 tanpa tag ditolak oleh aturan wajib tag |
| Wave-2 replay | 82/82 pass, 4 skrip | Kasus retry/failure yang lebih luas tetap mempunyai 17 counterexample lama |
| Extended replay | 414/455 pass, 41 fail, 3 nonzero/timeout, 41 skrip | Seluruh nonpass dipertahankan dalam register, tidak diubah menjadi klaim bug otomatis |
| Counterexample dan kontrol | 209 observasi: 122 selisih numerik/state, 70 kontrol pass, 17 replay fault lama | Beberapa observasi milik satu temuan; bukan 209 bug |
| Backend statement | 50,308/102,029 = 49.31% | Denominator tetap 603 file Python tracked; backend/tests dikecualikan, script test/POC di level atas tetap termasuk |
| Backend branches | 11,898/29,916 = 39.77% | Coverage tercatat dari proses uji dan server lokal; bukan persentase business correctness |
| Backend runtime/startup, denominator terpisah |480 files; statement 50,117/72,221=69.39%; branch 11,846/23,008=51.49% |Same execution record; test/POC/offline files dipisahkan menurut rule dan daftar file eksplisit |
| Frontend build | Compiled successfully | Dependency cache lokal dipakai, ESLint plugin dinonaktifkan; bukan fresh locked install atau lint bersih |
| Frontend numerik | Function/expression asli diekstrak dengan Babel; producer API diuji untuk kasus OrderDashboard dan konversi PO | Tidak ada bukti seluruh navigasi React di browser, visual rendering, export atau printer |
| Perangkat / data produksi | Tidak diuji | RFID reader/gate/printer fisik, reconnect/offline dan rekonsiliasi data produksi tetap perlu uji |

## Register cakupan

`all-file-coverage.csv` mencatat seluruh file dan metode pemeriksaan. Kolom `specific_finding_source_review` berarti source terkait temuan ditelaah, bukan seluruh baris file disertifikasi. `frontend-api-lineage.csv` memperluas mapping hingga service delegation statis; unresolved tetap disebut. `latest/evidence/registered-route-execution.csv` menyimpan seluruh handler dan bukti body execution. `latest/evidence/get-combined-results.json` memuat route GET beserta percobaan dan alasan yang tersisa.

Pemetaan literal memakai route yang benar-benar terdaftar beserta prefix router, bukan hanya path pada decorator. Kolom matching_route dan mapping_basis mencatat ekspansi alias template/literal level modul yang dianalisis dengan Babel, tanpa binding/parameter shadow dan dideklarasikan sebelum caller. Nested alias, helper dinamis dan pilihan action tetap unresolved; tidak dipaksa cocok memakai wildcard. Peta ini hanya kontrak dan delegasi statis hingga tiga tingkat, bukan proof numeric source/flow atau browser success untuk semua caller. ID temuan pada lineage merupakan asosiasi file sumber, bukan verdict bahwa setiap panggilan dalam file itu salah; verdict spesifik mengikuti counterexample dan acceptance. Register binding ada pada latest/evidence/frontend-literal-prefixes.json.

Coverage server di-flush ketika server uji dihentikan dengan tertib. Path Windows dinormalisasi saat merge agar source yang sama tidak dihitung sebagai file berbeda. Laporan hanya memakai source kandidat terbaru. Hasil tahap d6da disimpan terpisah dan tidak dijumlahkan ke persentase kandidat a904.

Denominator 603 juga mengandung top-level test/POC/audit scripts, walaupun direktori backend/tests dikecualikan. Salinan tes di sandbox tidak diatribusikan otomatis ke path file tes asli. Agar pembaca tidak mengira seluruh statement yang belum tercatat berasal dari aplikasi, backend-coverage-by-layer.json memisahkan runtime/startup, offline scripts dan test/POC/audit source dengan rule serta seluruh file list. Persentase runtime yang lebih tinggi memakai denominator berbeda pada bukti yang sama; bukan tambahan coverage atau sertifikasi flow. Semua angka full 603 tetap dipertahankan.

## Yang menghalangi penutupan 100%

1. 374 mutation methods belum mempunyai bukti body execution; handler yang pernah masuk pun belum seluruh state/role/parameter/fault/reversal-nya teruji.
2. 49 GET membutuhkan fixture atau parameter spesifik, termasuk dokumen, foto, sesi dan referensi yang koheren.
3. 657 testcase nonpass perlu fixture deterministik dan adjudikasi lebih jauh; register otomatis belum menjadi verdict manual seluruh kasus.
4. Semua layar membutuhkan validasi angka rendered, filter, paging, export, empty/null/error dan perubahan periode pada role/entity yang sesuai.
5. Jalur RFID dan pencetakan memerlukan perangkat sebenarnya; kebenaran software session tidak membuktikan hasil fisik di gate.

Laporan ini menyimpulkan masalah yang terbukti dan batas uji. Ia tidak memberikan sertifikasi bahwa seluruh code dan semua flow telah selesai diuji.

## Batas verifikasi browser pada sesi ini

Browser helper gagal sebelum navigasi dengan pesan `failed to write kernel assets: The system cannot find the path specified. (os error 3)`. Satu reset dan percobaan ulang memberikan error sama. Frontend/backend lokal sudah disiapkan, tetapi **DOM, screenshot, angka rendered dan navigasi UI tidak terverifikasi**. Ini kegagalan lingkungan alat, bukan temuan bug aplikasi. Bukti dua percobaan tersedia pada `latest/evidence/browser-ui-attempt.json`. Original-JavaScript probes dan API tests tetap berlaku sesuai batasnya; belum menggantikan browser/perangkat fisik.


---

# Rantai bisnis, sumber data dan konsekuensi

Diagram berikut memetakan jalur yang ditelusuri dan titik masalah, bukan klaim seluruh permutasi flow sudah diuji end-to-end.

## Penjualan sampai kas

```text
Customer/term → SO/price → fulfillment decision → reserve/PR → PO atau makloon → receive → RFID/tag → putaway/transit → picking/cut → loading perwarehouse → SJ/dispatch → revenue/COGS/AR → receipt/deposit → bank match → reversal
```

**Catatan terkait:** D4-SALES-01/02/03; D4-FIN-02/03/04; V3-AR-01; V3-BANK-01; V3-CUT-01; V3-WMS-02; V3-RFID-01.

Kesalahan scope target/komisi; reservasi parsial tidak tampak di analitik; loading SO-wide; fault window receipt dan cut. Shipping GL tidak dapat diasumsikan salah hanya dari laporan SO-based.

## MD/R&D ke SKU dan produksi

```text
Role line×sampling → round labdip/proofing/handfeel → result/spec/final ACC → SKU/color/lot → material stage → PR/raw reservation → production issue → output/cost → sale
```

**Catatan terkait:** REQ-01/03/05/08; D4-RND-01; V3-MRES-01/02; V3-PROD-01/02; V3-MKO-01.

SKU MD wajib proses sesuai lini; raw material greige/benang tidak wajib uji sama. Masih perlu keputusan rule hard-gate vs authorized override. Producer menyimpan performer ID tetapi KPI masih nama.

## Pembelian dan selisih roll

```text
PO perroll/perlength → receiving actual lengths → shortage/overage notice → wait/close/amend → supplier bill/payment → return → cost adjustment
```

**Catatan terkait:** V3-PO-01/02/03; D4-STOCK-03; D4-AI-01.

Task variance stale, amendreceivedqty guard dan perubahan notes dapat menutup task. Analytics AP fallback tidak sama dengan bill canonical.

## Intercompany dan stok gabungan

```text
Physicalwarehouse + ownerA/B → aggregate catalog visible to sales → ownership procurement/transfer → entitySO fulfillment → separate ledger → analytics owner grouping
```

**Catatan terkait:** D4-STOCK-01; D4-SALES-03; D4-FIN-01; D4-HR-01.

POV totalstock boleh gabungan sesuai kebutuhan klien; financial/legalownership tidak boleh hilang. Grain row join menyebabkan nilai/velocity duplikasi walau qty correct.

## Reservasi, potong dan transformasi

```text
Whole/partial reserve → pendingcut → physical parent split → child RFID verify → release/pick/ship → WAC/weight/value conservation → snapshot
```

**Catatan terkait:** V3-WEIGHT-01; V3-CUT-01; D4-AI-05/06; D4-DASH-01.

Live availability, canonicalbalance dan historicalfact harus satu definisi. Meter/kg tidak bisa digabung menjadi grandquantity.

## Cycle count dan kesehatan gudang

```text
Read → incident → countopen → assess → approve/journal → device heartbeat → health day/last accuracy
```

**Catatan terkait:** D4-WMS-01/02/03; V3-MASTER-01.

Day boundaryUTC salahWIB; lastopen bukan lastmeasured; rack.levels capacity tidak dibaca. Hardware tetap belumdiuji.

## Keuangan dan pelaporan

```text
GL posting/reversal/close → BS/PL/CF → AR/AP aging → tower/BI/forecast → cost redaction → dashboard
```

**Catatan terkait:** V3-CF-01; V3-DATE-01; D4-CASH-01; D4-FIN-01/02/03/04.

Net cash dapat benar tetapi klasifikasi arus kas salah; default scope Tower tidak konsisten. Estimasi menggunakan WAC terkini berbeda dari realisasi historis. Hipotesis redacted-cost tidak dijadikan temuan UI normal; lihat dokumen 08.

## HR/payroll/sales commission

```text
Employee lifecycle → attendance/overtime → payrollrun → incentive accrual → post/pay → HR analytics
```

**Catatan terkait:** D4-HR-01/02; D4-SALES-03.

Aggregatepayrollreport salah tidak membuktikan posting GL salah. Turnover membutuhkan effective separationevent, bukan updated_at.

## Marketing dan AI analytics

```text
Postmulti-account → aggregatemetrics → channel breakdown → salesfact attribution → unit/date/line scope → daily snapshot → Tanya KN response
```

**Catatan terkait:** D4-MKT-01; D4-AI-01/02/03/04/05/06.

Perchannel actualmeasurements belum tersedia; ETLdelete-before-insert dapat menghapus readmodel. Factmoneyrounding tidakmengonservasi netorder.

## Frontend state dan pengalaman data

```text
Selected entity/period → parallel requests → response generation → table/chart/KPI → tooltip/export/print
```

**Catatan terkait:** D4-FE-01/02; D4-WMS-02.

Respons periode lama dapat menimpa periode baru pada entitas yang sama; App.js meremount saat entitas berubah; chart dipotong menjadi 14 hari; cycle count belum terukur memerlukan status dan penanganan null. Uji browser aktual belum dilakukan.

## Inventaris consumer frontend

1477 literal API calls tersedia pada `frontend-api-lineage.csv`; 21 file terdeteksi memakai komponen chart. Mapping literal dapat melewatkan dynamic router/service call, sehingga label unresolved dipertahankan. Semua 5824 file ada di `all-file-coverage.csv`. Hash atau handler match bukan tanda data metric benar.

- `frontend/src/config/hubTabs.js`: Chart.
- `frontend/src/config/navMeta.js`: Chart.
- `frontend/src/config/navStructure.js`: PieChart.
- `frontend/src/features/designer/DesignScoreTrendChart.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/designer/DesignerKpiTrendChart.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/finance/BiFinanceView.jsx`: BarChart, Chart, ResponsiveContainer.
- `frontend/src/features/finance/BudgetView.jsx`: BarChart, ResponsiveContainer.
- `frontend/src/features/finance/CashFlowForecastView.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/finance/CashFlowTab.jsx`: BarChart, ResponsiveContainer.
- `frontend/src/features/finance/ChartOfAccounts.jsx`: Chart.
- `frontend/src/features/finance/EquityChangesTab.jsx`: BarChart, ResponsiveContainer.
- `frontend/src/features/finance/FinanceTowerParts.jsx`: BarChart, PieChart, ResponsiveContainer.
- `frontend/src/features/finance/ProfitabilityView.jsx`: BarChart, ResponsiveContainer.
- `frontend/src/features/home/SalesHome.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/hr/HrAnalyticsView.jsx`: BarChart, LineChart, PieChart, ResponsiveContainer.
- `frontend/src/features/inventory/StockAnalyticsView.jsx`: BarChart, PieChart, ResponsiveContainer.
- `frontend/src/features/logistics/DispatchDashboard.jsx`: PieChart, ResponsiveContainer.
- `frontend/src/features/manager/ManagerDashboard.jsx`: BarChart, LineChart, PieChart, ResponsiveContainer.
- `frontend/src/features/sales/mobile/MobileSalesHome.jsx`: LineChart, ResponsiveContainer.
- `frontend/src/features/tanya/TanyaChart.jsx`: AreaChart, BarChart, LineChart, PieChart, ResponsiveContainer.
- `frontend/src/features/tanya/TanyaCostChart.jsx`: BarChart, ResponsiveContainer.

## Pemenuhan baru dan metrik pesanan

Catatan PLAN-01/02/03/04/05, GLOBAL-01, SUPPLY-01, BACKORDER-01 dan CAP-01 menghubungkan keputusan pemenuhan, PR/PO, incoming, reservasi demand dan KPI. Rincian contoh rantai dan dampak patch tersedia pada dokumen 12.

D4-ORDER-01 menelusuri original public dashboard window 20 dan summary seluruh order hingga useMemo frontend: revenue sudah benar, count dan denominator rata-rata belum benar. Top Customers, status/pending/expiry masih memakai window lokal; Recent Orders 10 memang berlabel subset. Register 21 file chart ada pada latest/evidence/frontend-chart-register.csv. Numeric non-chart views juga ditelusuri pada API lineage dan temuan. Register statis tidak diberi status seluruh angka rendered telah benar.


---

# Pengujian dan adjudikasi hasil

Kandidat terbaru `a904d989b622f7da14c4892d03cf6ef0c43f3084`: **1539 pass, 484 fail, 76 skip, 173 error**, 2272 testcase records. Pengujian berlangsung pada DB lokal dan assertion asli dipertahankan. Copy tes mengadaptasi path Linux, API localhost, lokasi ROOT dan env database; manifest perubahan tersedia pada evidence. Dua modul dengan side effect saat import—`test_wilayah_extra.py` dan `test_notifications_iter33.py`—dikecualikan dan bukan diberi status pass.

## Seluruh nonpass full pytest

| Petunjuk traceback otomatis | Jumlah |
|---|---|
| `assertion_or_contract_needs_review` | 335 |
| `fixture_credentials_or_auth_contract` | 59 |
| `fixture_or_upstream_precondition_needs_review` | 88 |
| `harness_environment_or_collection` | 15 |
| `async_fixture_loop` | 85 |
| `fixture_login_rate_limit` | 75 |

Klasifikasi di atas adalah petunjuk, bukan pembuktian manual seluruh 657 kasus. Semua testcase dan traceback ada pada `latest/evidence/pytest-triage-register.csv` dan XML. Fixture shared/event-loop Motor, rate limit login, akun/permission lama dan hardcoded data ikut memengaruhi suite. Jangan mengganti expected, memperlemah guard atau menyatakan semua nonpass sebagai bug.

## Tes yang ditambahkan patch terbaru

Tiga modul baru menghasilkan 14 pass/3 fail/5 skip. Tiga failure terkait populasi lot demo: ekspektasi 34 versus aktual 29 dan distribusi BTK 13 versus 8/status karantina. Fixture bukan dataset yang unik terhadap tes itu. Lima skip mempertahankan kekurangan prasyarat. Skenario pemenuhan intercompany dapat memakai fallback PR ketika kontrak harga internal tidak tersedia; status pass pada jalur fallback tidak membuktikan interco purchase→ownership→shipping selesai.

## Replay gelombang sebelumnya

| Kelompok | Skrip | Pemeriksaan | Pass | Fail | Nonzero/timeout |
|---|---|---|---|---|---|
| core | 15 | 310 | 309 | 1 | 0 |
| w2 | 4 | 82 | 82 | 0 | 0 |
| extended | 41 | 455 | 414 | 41 | 3 |

Semua hasil nonpass replay diperinci pada `latest/evidence/replay-nonpass-adjudication.csv`. Bukti awal connection-refused dipertahankan, kemudian tiga skrip diulang dengan pembacaan frontend.env diarahkan ke server suite yang benar; assertion tidak berubah. Core RF-05 masih terblokir oleh fixture tanpa tag. Extended mencakup permission 403, prasyarat return/employee/design yang tidak terbentuk, font OCR tidak tersedia, entitas hardcoded tidak ada, dan timeout. Semua ini dipisahkan dari counterexample yang sudah terbukti.

Kasus COMM-05 mempunyai oracle max(created_at), sedangkan helper kanonis memakai valid_from, created_at, id. Perbedaan tie-break tidak diberi status bug secara otomatis. Follow-up OPS-02 menjalankan scanner tiga kali dan membuktikan level target 1→2→2 sesuai manager→admin; tambahan notifikasi antarlevel memang dirancang. Assertion no-growth seluruh jobs tidak cukup membuktikan duplikasi. Ini kontrol terarah, bukan sertifikasi seluruh scanner bebas race. RF-09 dan flow desain tertentu tetap memerlukan contract/fixture adjudication; tidak dinyatakan tuntas.

## Bukti terarah yang tetap terbuka

17 counterexample fault lama berhasil direproduksi pada source terbaru; temuan ini tidak ditutup oleh W2 82/82. Counterexample baru memakai source asli, expected independen, input terukur dan hasil actual. Race di SO stock fill menjadwalkan dua final-write setelah masing-masing allocator asli berjalan; produksi kode tidak diganti. Function-level JS memakai transport terkontrol agar respons out-of-order dapat diuji, namun masih memerlukan browser test.

Tahap d6da dan baseline 5b7 mempunyai full-suite results sendiri, disimpan sebagai histori. Perbandingan stateful itu bukan eksperimen bersih untuk mengatribusikan seluruh perubahan pass/fail ke patch terbaru. Angka tahap lama tidak dipakai sebagai angka pengujian current commit.


---

# Workflow perbaikan dan validasi

1. Import folder `docs/audit/data-flow-2026-10-05` ke repo. Pertahankan audit W1/W2 sebagai histori; jangan menimpa evidence lama.
2. Baca ringkasan, findings tracker dan dependency phases. Fase 01 durability dikerjakan dahulu agar source stock/finance tidak rusak sebelum projection dibenahi. Scope/commission dan reservasi parsial bernilaiP 1, kerjakan secepat mungkin tanpa melewati uji failure/retry.
3. Agent mengisi `implementation_commit`, `implementation_evidence`, dan status `implemented_pending_validation`. Business-definition findings harus memiliki keputusan definisi eksplisit, bukan asumsi agent.
4. Jalankan fixture independen serta uji regression terkait. Catat unit, owner/legalentity, tanggalbusiness, statusdocument, denominator, price/costbasis, freshness, redaction/nullpolicy.
5. Reviewer menjalankan kembali counterexample original dan jalur terkait, memeriksa diff/source serta angkaAPI/consumer. Baru beri `verified_fixed` bila acceptance terpenuhi; gunakan `partial` jika hanya sebagianwindow tertutup.
6. Closure tidak boleh didasarkan pada kodekomentar, dokumenimplementation, parse/buildpass, endpoint 200 atau test yang tidak mempunyai assertionangka. Sertakan hasilbefore/after.

Evidence dan skriprepro dilampirkan untukaudit, bukan untukdijalankan terhadapproduksi. Bootstraplokal membatasi socket ke loopback dan memakai databasebernamaaudit; janganmenghapusguard saatportingkeCI.


---

# Koreksi dan kontrol terhadap false positive

1. **Entity switch menimpa dashboard:** klaim awal D4-FE-02 ditarik. `App.js` memakai `AppViewRouter key={selectedEntity}` sehingga komponen diremount saat entitas berubah. Probe lama berbagi setters dan melewati lifecycle tersebut. Temuan current D4-FE-02 adalah periode 30→90 dalam komponen yang sama; original load terbukti dapat ditimpa respons 30 yang terlambat. Bukti entity lama bukan bukti bug UI. Dugaan list/summary OrdersView tidak refetch entitas juga tidak dicatat karena remount yang sama.
2. **Katalog 103 SKU masih terpotong:** sudah tidak benar pada a904; kontrol 103 lulus. D4-DASH-01 kini secara spesifik menguji 3003 SKU dan reservasi pada SKU di luar cap 3000. D4-CAP-01 membuktikan lookup PO first 1000 yang berbeda. Batas query bukan otomatis bug tanpa dampak yang terukur.
3. **Perencanaan ulang membuat PR ganda:** kasus sequential justru menggunakan PR20 yang sama. Masalah PLAN-01 adalah planner mencatat 80 dan cumulative 100 ketika referenced PR tetap 20, bukan klaim dua PR baru.
4. **Semua finance melihat HPP Rp 0:** formatter undefined memang memberi nol, tetapi tab profitability normal dibatasi admin/manager. Jalur role finance normal belum terbukti; hipotesis redaction tidak dimasukkan ke tracker. WAC profitability juga sudah memakai entitas per SO, bukan entityNone untuk semua order.
5. **PO yard salah konversi di producer:** producer public PO100 yard memberikan quantity_base91.44 meter dengan benar. Yang salah adalah global incoming consumer memakai quantity 100 dan melabelkannya meter. Perbaiki consumer dan sisa qty, jangan mengganti konversi producer yang benar.
6. **Last cycle count 0%:** data actual adalah accuracy tidak tersedia saat sesi baru masih open dipilih, bukan angka 0 literal. Temuan menguji last measured versus latest open dan null policy.
7. **Marketing harus dibagi 50/50:** sumber hanya reach total post; kontribusi tiap platform tidak diketahui. Equal allocation bukan actual reach. Jika atribusi shared memang diinginkan, metrik harus dinyatakan nonadditive.
8. **Reserved SO berarti revenue GL salah:** temuan membahas label realisasi yang memakai SO reserved. Tidak membuktikan jurnal pengakuan revenue salah. Bedakan orderbook, booking, shipment, invoice dan realized ledger revenue.
9. **Current total discount pasti hilang:** manual header discount yang tidak direkalkulasi terkait dokumen legacy/import. Producer SO current menonaktifkan manual_disc. PPN-inclusive case diuji melalui pricing producer asli dan merupakan sumber net/gross mismatch yang terpisah.
10. **Losing concurrent deposit 400 sendiri membuktikan double-use:** satu 200/satu 400 dapat benar menolak request kedua; oracle 409 yang terlalu spesifik bukan bukti double-use pada receipt replay lama. Follow-up kasus refund D4-CASE-02 berbeda: menghitung cash 160 pada dana/refund 80 sesudah satu request ditolak membuktikan efek parsial. HTTP status harus selalu dibandingkan dengan persisted saldo, cash, JE dan dokumen.
11. **Admin self-approve otomatis bug:** patch menerapkan kebijakan explicit admin override. Evaluasi terhadap keputusan bisnis yang disepakati; jangan menyebut perubahan override sebagai bug hanya karena tes lama mengharapkan SoD mutlak.
12. **Setiap SKU harus labdip/proofing/handfeel:** klarifikasi pengguna membedakan SKU hasil MD dengan greige/benang/bahan. Uji MD mengikuti lini dan kebutuhan sampling; bahan tidak otomatis wajib proses yang sama. Istilah C/H tidak diasumsikan karena belum jelas.
13. **Parse/build/GET 200/100% statement berarti semua flow benar:** tidak valid. Coverage execution dan acceptance flow mempunyai denominator dan bukti yang berbeda; report current mempertahankan seluruh batas ini.


---

# Reproduksi, lingkungan dan asal bukti

Source audit `a904d989b622f7da14c4892d03cf6ef0c43f3084`; hasil current tersedia di `latest/`. Root evidence/repro lama adalah tahap `d6da1a3d536228582645abb98aea19f3e491f300` dan tetap bertanda commit. Jangan menjalankan skrip uji terhadap produksi.

Python runtime 3.12, FastAPI 0.110.1, Motor 3.3.1/PyMongo 4.6.3, pytest 9.1.1, coverage 7.16.2 dan Mongo 8.0.12 digunakan secara lokal. Database fixture memakai nama audit terisolasi; server dan koneksi dibatasi localhost. Tidak ada seed/transaksi yang dijalankan pada database perusahaan. Socket eksternal diblokir pada proses audit.

`latest/repro/` memuat fixture dan counterexample. `wave2_env.py` membuat DB UUID baru; `run_local.py` memerlukan KNHOST_REPO, runtime dengan dependency proyek dan Mongo lokal 27919. Runner portable menyiapkan env dan melakukan path resolution; path adaptasi tidak mengganti business functions. Untuk JavaScript diperlukan Node dan Babel parser dari frontend dependency environment. Package memakai `KNHOST_REPO` agar tidak tergantung nama checkout auditor. Review wrapper terlebih dahulu, pastikan HEAD dan env yang digunakan tercatat, lalu jalankan repro terarah.

OrderDashboard diuji dua tahap: original public `/dashboard` dan `/sales-orders/stats/summary` menghasilkan payload fixture; original useMemo kemudian dijalankan pada payload itu. ManagerDashboard memakai original load, dengan transport terkontrol pada period 30→90. FulfillmentDecisionDialog memakai original submit/load untuk melihat error yang terhapus. Ketiga contoh tidak diklaim sebagai browser navigation atau screenshot verification.

Tes audit asli dalam repository disalin ke sandbox. Adaptasi meliputi lokasi `/app`, API localhost, backend/frontend.env lokal, Windows ROOT derivation dan import mode. Assertion tidak diganti. Log awal yang berhenti akibat port salah disimpan dan tiga skrip diulang setelah memperbaiki pembacaan env. Full-suite fixture stateful dan asynchronous loop errors tetap dicatat.

Build frontend memakai dependency cache yang telah ada; bukan fresh installation dari lockfile. Raw coverage/process/database files tersedia lokal tetapi tidak dimasukkan ke ZIP import. JSON hasil, XML testcase, log, manifest adaptasi dan register route/file ikut paket. Token session sintetis pada log disamarkan dalam salinan paket.

## Batas verifikasi browser pada sesi ini

Browser helper gagal sebelum navigasi dengan pesan `failed to write kernel assets: The system cannot find the path specified. (os error 3)`. Satu reset dan percobaan ulang memberikan error sama. Frontend/backend lokal sudah disiapkan, tetapi **DOM, screenshot, angka rendered dan navigasi UI tidak terverifikasi**. Ini kegagalan lingkungan alat, bukan temuan bug aplikasi. Bukti dua percobaan tersedia pada `latest/evidence/browser-ui-attempt.json`. Original-JavaScript probes dan API tests tetap berlaku sesuai batasnya; belum menggantikan browser/perangkat fisik.


---

# SSOT dan dampak lintas modul

## Kontrak metrik harus mencakup sumber dan grain

Nama dan rumus saja belum cukup. Setiap angka perlu mendefinisikan source document/field, grain, eligible status, entity/owner, sales ownership, line, tanggal bisnis, unit dasar, price/tax/cost basis, denominator, rounding, freshness dan perlakuan null/error. Contohnya revenue 3000 dibagi count 20 secara aritmetika benar tetapi salah populasi. Nilai dan velocity stok dapat terduplikasi jika join owner dihilangkan terlalu awal. Nama performer bukan identity user.

Catatan: D4-ORDER-01, D4-STOCK-01, D4-RND-01, D4-HR-01, D4-SALES-01. UI sales boleh melihat stok gabungan sesuai kebutuhan pengguna; ledger dan kepemilikan tetap per badan usaha.

## Lifecycle PO harus satu sumber kebenaran

PO producer sudah menyimpan unit dokumen dan quantity_base. Consumer incoming harus memakai outstanding base quantity, bukan quantity mentah berlabel base_unit. Producer receipt menetapkan status partial, sementara shared OPEN_PO_STATUSES tidak memasukkan partial. Memperbaiki daftar status saja belum cukup jika consumer kemudian menjumlah seluruh ordered quantity dan mengabaikan received_qty.

Catatan: D4-GLOBAL-01, D4-SUPPLY-01, V3-PO-01/02/03, D4-AI-06. Review ATP, POS desktop/mobile, pending SO, forecast, reorder, GRN variance, return dan amendment pada fixture sama.

## Rencana supply berbeda dari supply yang dieksekusi

Rencana 20+80 bukan supply 100 jika satu PR20 dipakai ulang. Scope full berdasarkan request tidak benar jika interco 70 gagal sesudah stock 30 berhasil. Supply PO100 yang ditawarkan ke dua SO100 membutuhkan pegging eksklusif untuk janji pasti, atau label forecast nonexclusive yang jelas. Riwayat naratif tidak menggantikan reference aktif dan remaining quantity.

Catatan: D4-PLAN-01/02/03/04/05. Bagian sukses perlu operation identity, qty efektif dan reference; bagian gagal harus dapat dilanjutkan tanpa mengulang efek sukses. UI error proses tidak boleh terhapus hanya karena refresh GET berhasil.

## Demand dan stock harus diklaim secara atomik

Allocator dapat menjaga roll dengan CAS tetapi tetap overfulfill satu SO jika dua proses membaca shortage 100 dan masing-masing reserve 80. Demand claim SO/version harus dikoordinasikan dengan supply reservation, persist allocations, cancellation dan compensation. Mengganti satu $set menjadi $inc saja tidak menyelesaikan bound demand atau recovery.

Catatan: D4-BACKORDER-01, V3-MRES-01/02. Uji manual fulfillment versus automatic GR fulfillment dan cancel/retry pada line yang sama.

## Keandalan write memengaruhi seluruh read model

Stock consume, insert movement, child roll, posting GL, deposit/receipt dan publish fact adalah efek terpisah. Marker done/reversed yang mendahului physical restore dapat menutup recovery. Read model ETL delete-before-insert dapat kosong saat insert gagal. Revenue report yang salah source tidak otomatis berarti ledger posting salah; keduanya harus diuji dengan expected yang sesuai.

Catatan: V3-PROD-01/02, V3-MKO-01, V3-AR-01, V3-BANK-01, V3-MASTER-01, V3-CUT-01, D4-AI-03/04. Severity ledger berbeda dari label dashboard, tetapi keduanya perlu sumber dan bukti yang tepat.

## Helper kanonis harus dipakai seluruh consumer

Scope kredit benar pada satu sales KPI belum cukup bila home consumer memanggil tanpa entitas. Canonical bill fallback tidak membenarkan formula AP analytics yang berbeda. Snapshot term SO harus dipakai forecast agar tidak mengikuti term customer yang berubah. Rack→Level→Bin harus dipakai reporting capacity. Lookup master harus berdasarkan requested IDs; menaikkan cap hanya menggeser kegagalan.

Catatan: D4-SALES-02/03, D4-AI-01, D4-FIN-01/02, D4-WMS-03, D4-DASH-01, D4-CAP-01. Duplikasi fungsi _clean_perms tetap dicatat sebagai V3-DUP-01. Finite query cap hanya menjadi bug bila ada bukti kehilangan atau salah angka.

## Waktu dan frontend request generation

UTC adalah format penyimpanan; hari bisnis WIB, separation employee dan last measured accuracy membutuhkan source yang sesuai. App sudah meremount layar saat entity berubah. Race yang terbukti adalah periode berubah dalam komponen yang sama, tanpa guard request generation. Chart 14 hari harus diberi label atau mengikuti pilihan periode; perbaikan angka API tidak menjamin chart benar.

Catatan: D4-DATE-01, V3-DATE-01, D4-WMS-01/02, D4-HR-02, D4-FE-01/02.

## Dampak positif patch dan batas penutupannya

Agregat revenue server sudah benar pada counterexample 30 order; cap katalog 103 berhasil; full core 309/310 dan W2 82/82 lulus. Planner baru menyediakan split pemenuhan dan riwayat keputusan, serta global stock memperbaiki POV lintas entitas. Akan tetapi producer-consumer dan partial execution masih memiliki counterexample khusus. Penutupan perlu before/after pada failure window, scope, UOM dan consumer lain; hasil hijau yang lebih sempit tidak boleh menutup temuan yang lebih luas.


---

# Perubahan kandidat dan histori

Baseline `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` → current `a904d989b622f7da14c4892d03cf6ef0c43f3084`: 799 path berubah. Tahap sesi `d6da1a3d536228582645abb98aea19f3e491f300` → current: 753 path berubah, 49 file backend/frontend code. Banyak path berupa artefak audit UX dan screenshot; jumlah path bukan ukuran kedalaman perbaikan bisnis.

Daftar lengkap tersedia pada `source-delta.csv`. Inventaris current, syntax parse, test suite, counterexample dan route execution memakai commit a904. Dokumen historis d6da disimpan pada `history/stage-d6da1a3`, beserta erratum FE-02; jangan menggabungkan count/status tahap berbeda.

| Patch terlihat | Bukti current | Kesimpulan |
|---|---|---|
| Dashboard master cap 100→3000 |103 SKU lulus;3003 SKU dengan material reserve pada SKU terakhir gagal KPI | Perbaikan parsial; D4-DASH-01 diperbarui, klaim cap 100 ditutup |
| Revenue aggregate server |30 confirmed orders 100 → grand 3000/count 30 | Producer sudah benar; denominator dan customer aggregate UI masih salah |
| Global stock/incoming |Physical combined stock tersedia; PO yard→base producer benar | Incoming consumer kehilangan unit dan partial status |
| Split fulfillment plan |Stock/reorder/interco/wait dapat disusun | Referenced qty, duplicate input, partial scope dan exclusive supply belum konsisten |
| Admin override policy |Explicit bypass/self-approval sesuai policy baru | Tidak otomatis dicatat sebagai SoD bug; requirement tetap perlu disepakati |
| New integration tests |14 pass/3 fail/5 skip | Fallback PR/hardcoded fixture membatasi real-chain proof |


---

# Dampak yang terlihat pada rantai bisnis besar

## Sales demand → keputusan pemenuhan → supply

```text
SO demand100
  → plan stock / interco / supplier PR / wait incoming
  → qty efektif + reference supply + remaining demand
  → reserve stock / PO / makloon
  → receiving aktual dan RFID
  → picking / cut / staging / loading perwarehouse
  → SJ / dispatch / AR-COGS-GL
  → payment / deposit / bank reconciliation / reversal
```

Rantai ini belum aman hanya karena dialog berhasil disimpan. PLAN-01 dapat mencatat 100 supply ketika PR hanya 20; PLAN-03 memberi scope full ketika yang berhasil 30; PLAN-05 menawarkan PO100 bagi demand 200. BACKORDER-01 dapat menulis allocations 160 sementara item menunjukkan reserved 80/backorder 20. Akibatnya masing-masing tampilan dapat terlihat masuk akal, tetapi supply, demand dan state operasional tidak konservatif.

Perbaikan harus mengikat order line, effective quantity, operation/reference identity, supply claim dan state per bagian. Setelah satu bagian berhasil, retry bagian lain tidak boleh reserve atau membeli ulang bagian pertama. Nilai yang belum eksklusif harus ditampilkan sebagai perkiraan, bukan janji pemenuhan pasti.

## Procurement → receiving → incoming badges

```text
PO quantity100 yard
  → producer quantity_base91.44 meter
  → receipt aktual perroll
  → remaining base qty
  → PO partial/completed/closed_short
  → ATP / global incoming / pending SO / reorder / payment variance
```

Public producer benar mengonversi yard ke meter. Consumer global mengambil 100 quantity mentah dan memberi label meter. Pada contoh PO100 diterima 90, producer menjadi partial dan incoming helper menghilangkan sisa 10. Kedua masalah harus diperbaiki bersama: canonical unit, eligible lifecycle dan outstanding quantity. V3-PO variance/amendment tetap perlu ditutup supaya dokumen dan kewajiban pembayaran konsisten dengan penerimaan fisik.

## Inventory ownership → sales aggregate → valuation

Sales memang membutuhkan gabungan tersedia/reserved/coming dari semua entitas, sesuai penjelasan pengguna. Aggregation harus terjadi sesudah grain product+warehouse+owner benar; join yang menghilangkan owner dapat menggandakan nilai/velocity. Pembelian antarentitas dan ledger masih membutuhkan kepemilikan legal, kontrak harga internal serta dokumen yang saling merujuk. Angka global tidak menggantikan transfer ownership.

MD/R&D role lini dan jenis sampling, approval hasil/spec/final, SKU/material stage serta flow makloon tetap mengikuti kebutuhan yang sudah dijelaskan. Barang stok bertag menuju storage; barang untuk SO bertag dapat melalui transit/cross-dock. Semua barang wajib tag. Arti C/H tidak diasumsikan. Requirement historis dicatat dengan verdict lama, bukti current dan bagian yang belum mempunyai runtime acceptance unik.

## Frontend angka → keputusan manajemen

Revenue total benar tidak cukup bila rata-rata memakai 20 baris. Availability benar tidak cukup bila badge incoming memakai unit lain. Grafik periode 90 tidak benar bila data 30 yang terlambat menimpa state atau hanya 14 titik ditampilkan tanpa label. Analitik reserve harus memakai free length/quantity yang sama dengan operasional, dan meter+kg tidak boleh dijumlah menjadi satu quantity.

Validasi setiap metrik harus mengikuti source producer → canonical persisted field → projection/query → API payload → UI expression/render → export. Laporan ini memiliki counterexample terarah pada rantai tersebut, tetapi belum mengklaim semua rendered UI/export telah diuji.


---

# Pekerjaan yang masih diperlukan sebelum coverage penuh

Dokumen ini mempertahankan batas audit, bukan mencatat seluruh item sebagai bug. Tidak ada perubahan status otomatis menjadi verified_fixed dari parse/build/pass parsial.

| Kelompok | Bukti tersedia | Yang masih harus dibuktikan |
|---|---|---|
| Semua code |Hash dan parse seluruh tracked source |Semantic review setiap fungsi; 51,721 statement dan 18,018 branch belum tercatat dieksekusi |
| API mutasi |Register 772 methods |374 belum tercatat body; state-machine success/failure/retry/reversal pada seluruh methods belum lengkap |
| API baca |589 GET dipanggil |49 membutuhkan resource fixture; setiap angka consumer tetap memerlukan oracle |
| W1/W2/REQ |137 ID historis memiliki register |Pass replay lebih sempit daripada acceptance penuh; ID tanpa runtime unik current tetap dinyatakan belum terbukti |
| Browser |Build dan original-JS probes |Seluruh layar/role/entity/filter/paging/export/print/loading/error/null, termasuk angka yang terlihat di DOM |
| Rantai finance |Fault probes dan numeric source review |Seluruh closing/reversal/tax/accrual/reconciliation pada fixture deterministik dan data produksi anonim |
| Rantai WMS/RFID |Software tags/session/loading/cut/count probes |Perangkat gate/reader/printer, offline/reconnect dan operational walkthrough dengan gudang terpisah |
| Tes nonpass |Semua XML/log dan triage register |657 full-suite nonpass belum seluruhnya diberi verdict manual independen |

Register endpoint sudah menyediakan daftar konkret untuk memperluas pengujian. Pengujian lanjutan harus membuat fixture koheren dan oracle independen per lifecycle, bukan mengejar persentase dengan memanggil endpoint kosong atau menutup kegagalan yang tidak dipahami.

## Batas verifikasi browser pada sesi ini

Browser helper gagal sebelum navigasi dengan pesan `failed to write kernel assets: The system cannot find the path specified. (os error 3)`. Satu reset dan percobaan ulang memberikan error sama. Frontend/backend lokal sudah disiapkan, tetapi **DOM, screenshot, angka rendered dan navigasi UI tidak terverifikasi**. Ini kegagalan lingkungan alat, bukan temuan bug aplikasi. Bukti dua percobaan tersedia pada `latest/evidence/browser-ui-attempt.json`. Original-JavaScript probes dan API tests tetap berlaku sesuai batasnya; belum menggantikan browser/perangkat fisik.


---

# Pengujian tambahan: refund, kepemilikan dan valuasi antarentitas

Source `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Sebanyak 41 observasi terarah menghasilkan 23 selisih dan 18 kontrol lulus, tanpa harness error. Observasi ini menjadi **lima** temuan, karena beberapa window dan output berasal dari akar masalah yang sama. Semua angka memakai satuan uang sintetis yang sama; tidak ada transaksi atau database produksi yang dijalankan. Original startup index installer dijalankan: 212 performance indexes dan 25 unique-key installations tercatat, tanpa failure. Unique cash document number serta active journal source indexes diverifikasi ada. Ini bukan klaim seluruh bootstrap/backfill diuji.

| ID / flow | Yang seharusnya | Yang tercatat pada source sekarang | Dampak |
|---|---|---|---|
| CASE-01: kredit 100 dicairkan 80 |Dr kewajiban 80; income 0; saldo GL20=ledger 20 |Dr kewajiban 160; OtherIncome 80; GL-60 versus ledger 20 |Saldo pelanggan terlihat benar, tetapi laba rugi dan neraca salah |
| CASE-02: dua proses refund 80 dari deposit 100 |Satu cash 80 dan saldo 20 |Satu request ditolak, cash 160 sudah tercatat; saldo 20 |CAS melindungi saldo, tidak melindungi cash/GL yang dibuat lebih dulu |
| CASE-02: gagal setelah cash+JE, lalu retry |Lanjutkan aksi yang sama; total cash 80 |Cash 160, saldo 20; kasus akhirnya resolved |Idempotensi journal per cash UUID tidak menjaga idempotensi aksi |
| CASE-02: pindah buku 80, gagal pada leg kedua |Out 80/in80; transit 0 setelah recovery |Out 160/in80; transit debit 80; kasus resolved |Saldo rekening dan kas perusahaan tidak mencerminkan satu transfer |
| CASE-02: supplier advance 100, dua refund 80 |Cash-in80 dan advance 20 |Cash-in160 dan advance-60; kedua request sukses |Saldo supplier tidak diklaim atomik sebelum dipakai |
| CASE-02: penetapan supplier advance 100 gagal saat checkpoint, lalu retry |Saldo dan GL masing-masing 100 |Saldo 200, GL100; retry ditolak setelah balance sudah bertambah |Idempotensi GL saja tidak menjaga saldo supplier |
| CASE-02: refund pada periode terkunci |Tolak sebelum posted cash/balance bergerak |Cash-out 80 posted; GL0; deposit 100; kasus open |Hard lock hanya menjaga jurnal, tetapi cash ledger sudah berubah |
| CASE-03: setoran karyawan sebelum acknowledgment |Tolak tanpa cash/JE |Cash 80 dan employee receivable-80; case resolved |Urutan langkah tidak menjadi backend guard |
| CASE-03: piutang 80, setoran 40 |Sisa 40 masih perlu ditindaklanjuti |Piutang 40, tetapi case resolved |Inbox kasus menghilangkan kewajiban yang belum selesai |
| CASE-03: piutang 80, setoran 100 |Kredit piutang maksimal 80, surplus diputus eksplisit |Piutang karyawan-20 |Nominal tidak dibatasi atau diklasifikasi terhadap sisa yang telah diakui |
| INTERCO-01: destination JE gagal |Operasi pending yang dapat dilanjutkan, atau rollback konsisten |Owner roll/tag sudahB; JE hanyaA; dokumen transfer tidak lahir |Stok, RFID, GL dan histori tidak memiliki keadaan akhir yang koheren |
| INTERCO-01: retry helper/API |Melengkapi destination journal dan histori |Helper already_posted setelah melihat source; API 400 karena owner sudahB |Jalur ulang tidak mencapai pemulihan |
| INTERCO-02: satu roll 10×cost 15, master 1 |Nilai transfer 150 |API 200, journal 10; roll tujuan tetap bernilai 150 |Query biaya terjadi sesudah source kehilangan roll |
| INTERCO-02: source 10×5 +10×15; pindah roll mahal 10 |Pre-source WAC 10: journal 100 menurut kontrak helper |Post-source WAC 5: journal 50 |Biaya yang dipakai justru berasal dari roll yang tertinggal |

## Mengapa pemeriksaan satu layar dapat melewatkan masalah

Refund store credit memberi saldo pelanggan 20 dan cash 80 yang masuk akal. Bahkan kedua jurnal seimbang secara individual. Kesalahan baru terlihat saat seluruh journal delta dibandingkan dengan satu peristiwa refund: pengurangan kewajiban terjadi dua kali, dan income 80 dibuat dari pencairan dana yang bukan pendapatan. Karena itu pengujian balance debit=credit saja belum memadai.

Refund deposit menunjukkan sisi lain: CAS memang menolak penggunaan saldo kedua dan saldo tidak pernah negatif. Namun penolakan terjadi sesudah cash dan JE. Uji harus membuktikan permintaan yang ditolak tidak meninggalkan uang keluar. Pindah buku memperluas dampaknya: retry satu kasus mengulang first leg yang sudah committed karena identitas aksi tidak stabil dan tidak ada checkpoint per leg.

Alur supplier juga diuji: refund tidak memakai CAS sehingga kedua request dapat selesai dan saldo menjadi negatif. Penetapan uang muka memakai source ID journal yang stabil, tetapi increment saldo belum idempotent; setelah checkpoint gagal, retry tidak membuat journal kedua namun sudah menambah saldo sekali lagi. Ini memperlihatkan dua arah ketidaksinkronan berbeda yang berasal dari aksi multiwrite tanpa recovery menyeluruh.

Periode terkunci diuji sebagai kondisi bisnis biasa. Refund tetap menyisipkan cash berstatus posted sebelum helper GL mengecek period lock. Penolakan journal tidak mengembalikan cash atau mengurangi deposit, sehingga tiga sumber menampilkan kejadian yang berbeda. Preflight, pending state dan pemulihan harus diputus secara konsisten untuk seluruh executor, bukan hanya guard di pintu journal.

CASE-03 membahas masalah berbeda: bukan crash/retry, melainkan permitted transition dan conservation pada playbook dua langkah. Normal acknowledgment 80→setoran 80 benar dan menjadi kontrol. Endpoint juga menerima setoran pada case open tanpa acknowledgment, menutup case setelah setoran 40 dari piutang 80, dan mengkredit 100 dari piutang 80. State, sisa dana dan business event harus dibatasi bersama; atomic claim saja belum memperbaiki transisi yang salah.

Transfer ownership merambat dari roll ke lot pemilik tujuan, RFID owner, inventory movement, balance, kedua buku entitas, dokumen transfer dan timeline retur. Source JE yang seimbang belum cukup membuktikan pasangan lengkap. Source existence OR destination existence tidak dapat menjadi syarat selesai. Pengujian juga memeriksa original API retry, bukan hanya memanggil helper dua kali.

## Biaya transfer harus dibekukan sebelum stok sumber berubah

Kasus source satu roll adalah bukti utama tanpa ambiguitas: baik pre-source WAC maupun actual roll cost bernilai 150, tetapi producer journal memberi 10 dari fallback master. Kasus campuran memperlihatkan ketergantungan pada cost barang sisa. Perusahaan perlu menetapkan policy WAC versus actual roll cost untuk barang campuran; audit tidak memilihkan policy tersebut secara diam-diam. Pada setiap policy yang dipilih, kedua GL dan subledger roll harus tetap dapat direkonsiliasi dan retry memakai snapshot biaya yang sama.

## Batas fixture dan kontrol normal

Refund deposit dimulai dari original receipt producer 100 tanpa alokasi sehingga deposit dan cash-in/GL awal terbentuk oleh layanan asli. Store credit dimulai dari original manual adjustment+100 yang diizinkan sistem; fixture ini tidak mengeksekusi seluruh rantai credit note/retur sebelumnya. Return transfer dimulai pada state roll retur external yang sudah released: original inbound writer membuat roll, lot dan movement; metadata lifecycle retur ditambahkan secara eksplisit sebagai fixture. Seluruh transfer dan journal yang diuji sesudah state itu berjalan lewat original public API/services.

Supplier fixture memakai keputusan manual kelebihan bayar yang dibolehkan playbook; original public action membentuk advance 100 dan jurnalnya. Fixture itu tidak mengeksekusi vendor bill/payment sebelumnya. Locked-period fixture membuat explicit period_closings state sesudah original receipt, kemudian memanggil original public refund dan original hard-lock guard; bukan full close/reclose/unlock lifecycle proof.

Normal single deposit refund 80 lulus cash 80/saldo 20/Dr uang muka 80; dugaan akun lawan refund selalu salah ditolak. Normal ownership transfer pada biaya seragam lulus ownerB dan dua-side journal. Fault wrapper hanya mengatur jadwal dua request atau menggagalkan satu boundary sebelum original write; tidak mengganti perhitungan, allocator, GL atau implementasi CAS.

Employee flow dimulai dari explicit SO receivable read-state. Case, payment application dan journal memakai original API/services; bukan whole SO producer proof. Pengujian partial/excess/skipped step tidak memakai fault wrapper. RFID state fixture memakai EPC berbentuk 24 hexadecimal, active tag dan roll link; owner update tetap layanan asli, perangkat fisik tidak digunakan.

Tambahan notification pada replay OPS-02 diperiksa lagi: target overdue case bergerak level 1→2→2 dengan dua ref berbeda dan target manager lalu admin. Ini eskalasi yang dirancang; assertion no-growth seluruh notifikasi terlalu luas untuk menyimpulkan duplikasi. Kontrol ini tidak menyertifikasi semua scanner atau race notification.

ManagerDashboard FE-02 juga diperkuat: respons mock memakai field **total_orders** yang memang dirender UI. State berubah 90→30 ketika respons periode lama selesai terakhir. Hipotesis entity-switch tetap ditarik karena remount; uji ini hanya pergantian periode dalam entitas sama dan bukan browser rendering.

## Lokasi source dan pekerjaan agent

- [D4-CASE-01 — backend/services/finance_case_actions.py:238](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L238); rantai terkait: [backend/services/store_credit_service.py:286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/store_credit_service.py#L286), [backend/services/gl_service.py:2483](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2483), [backend/services/finance_case_actions.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L57)
- [D4-CASE-02 — backend/services/finance_case_actions.py:206](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L206); rantai terkait: [backend/services/finance_case_service.py:419](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L419), [backend/services/finance_case_actions.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L57), [backend/services/finance_case_actions.py:253](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L253), [backend/services/ar_receipt_service.py:159](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/ar_receipt_service.py#L159), [backend/services/finance_case_actions.py:461](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L461), [backend/services/finance_case_actions.py:482](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L482), [backend/services/gl_service.py:467](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L467)
- [D4-INTERCO-01 — backend/services/gl_service.py:1333](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L1333); rantai terkait: [backend/services/return_service.py:1126](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_service.py#L1126), [backend/services/roll_service.py:1519](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L1519), [backend/routers/transfers.py:476](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/transfers.py#L476)
- [D4-INTERCO-02 — backend/services/gl_service.py:1337](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L1337); rantai terkait: [backend/services/return_service.py:1206](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_service.py#L1206), [backend/routers/transfers.py:435](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/transfers.py#L435), [backend/services/costing_service.py:45](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/costing_service.py#L45)
- [D4-CASE-03 — backend/services/finance_case_actions.py:310](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L310); rantai terkait: [backend/services/finance_case_service.py:441](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L441), [backend/services/finance_case_service.py:467](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_service.py#L467), [backend/services/finance_case_playbooks.py:113](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_playbooks.py#L113)

Detail penyebab, kode, expected/actual dan prompt ada pada dokumen 02 dan tracker. Kelima perbaikan masuk **FASE-01** sebelum projection/UI diperbaiki. Jangan membuat retry hanya mengabaikan error atau menghapus side effect tanpa reversal yang auditable. Setelah perbaikan, uji normal/fault/concurrent/retry/reversal dengan invariant cash, balance, liability, income, owner, tag, lot, movements, per-entity GL dan document history bersama-sama.

Bukti: `latest/repro/continuation_finance_probes.py`, `latest/repro/continuation-finance-results.json`, `latest/evidence/continuation-finance-probes.log`. Hasil observasi tidak menjadi klaim coverage 100%.


---

# Kontrak frontend–backend pada pratinjau template dasar

**Temuan D4-DOC-01, prioritas P2.** Source `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Jalur masih tersedia untuk admin melalui Pengaturan → Template Dokumen Dasar, dengan activeView doc-templates-basic. Ini hasil source trace, original public API dan original hook function; browser/iframe DOM belum diuji.

## Flow yang ditemukan

```text
Admin pilih Template Dokumen Dasar
  → AdminView only templates memuat template aktif
  → ada SO pada data.orders[0], tombol Pratinjau tersedia
  → klik baris template, meneruskan templateId + orderId
  → useAppActions.previewTemplate POST /document-templates/<id>/preview
  → route tidak terdaftar, HTTP404
  → catch memberi notice Not Found
  → setPreviewHtml tidak dijalankan, iframe tidak mendapat HTML
```

| Pemeriksaan | Expected | Actual |
|---|---|---|
| Template dari original creator dapat dibaca |200 dan template ditemukan |Lulus |
| Endpoint yang dipanggil tombol |200 HTML untuk selected template/source |404 Not Found |
| Jenis template Surat Jalan yang dipilih |surat_jalan |Callback selalu mengirim invoice |
| Original callback sesudah respons API |HTML pratinjau terisi |Tidak ada HTML; notice error |
| Existing GET /documents/preview/<orderId> untuk Surat Jalan |200 text/html |Lulus pada fixture yang sama |

Template dibuat melalui original public POST; SO berupa fixture read-state eksplisit yang sah dan milik entitasA. Ini tidak menguji seluruh SO→pengiriman atau hasil printer. Control GET yang lulus membatasi kesimpulan: masalah spesifik ada pada kontrak tombol template dasar. Keberhasilan tersebut juga belum membuktikan semua angka/data yang tercetak benar.

## Arah perbaikan

Kontrak harus menerima selected template ID, jenis dokumen dan source yang cocok. Callback harus membawa document_type dari baris template. Server memvalidasi permission, source legal entity, effective global/entity layer dan status template. Mengganti URL ke GET lama saja belum mempertahankan pilihan template, karena GET itu tidak menerima selected template ID.

Pratinjau harus memakai renderer dan data contract yang sama dengan hasil cetak yang nantinya digunakan. Bila perusahaan mempertahankan template dasar dan designer PDF sebagai fitur terpisah, jelaskan output yang diatur masing-masing agar operator tidak mengubah satu format lalu mencetak format lain. Ini perlu pemeriksaan consumer; tidak disimpulkan semua PDF sekarang gagal.

Acceptance lengkap ada pada tracker dan **FASE-05**. Uji dua template tipe sama dengan konten berbeda, Surat Jalan versus invoice, override per entitas, source/template invalid, tanpa SO, hak akses, recovery sesudah error, iframe dan printer/export. Preview tidak boleh membuat dokumen generated atau mengubah transaksi.

## Lokasi dan bukti

[frontend/src/hooks/useAppActions.js:616](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/hooks/useAppActions.js#L616). Rantai tambahan:

- [frontend/src/features/admin/AdminView.jsx:542](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/admin/AdminView.jsx#L542)
- [frontend/src/AppViewRouter.jsx:260](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/AppViewRouter.jsx#L260)
- [backend/routers/documents.py:283](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/documents.py#L283)

`latest/repro/document_preview_probes.py`, `document-preview-api-results.json`, `document_preview_probes.cjs` dan `document-preview-js-results.json` menyimpan fixture, API response, original-function execution serta expected/actual. Script tidak memperbaiki source aplikasi.


---

# Pengujian lanjutan: tutup buku, pembatalan jurnal dan sumber KPI ekuitas

Pada source `a904d989b622f7da14c4892d03cf6ef0c43f3084`, tambahan pengujian menghasilkan **enam temuan** dari 35 observasi: 16 perbedaan dan 19 kontrol lulus. Seluruh pengujian memakai API dan layanan asli, database sintetis lokal terpisah, serta indeks startup asli. Kesimpulan berikut dibatasi oleh fixture dan lifecycle yang dijelaskan; angka uang merupakan satuan sintetis yang konsisten.

## Hasil per flow

| ID | Kasus | Hasil semestinya | Hasil sekarang |
|---|---|---|---|
| CLOSE-01, P2 | Pendapatan 100 → penutupan bulan 100 → tahun residual 0 → reopen bulan | Penutupan tahun diberi tanda perlu diperbarui, atau reopen diblokir sebelum efek sesuai urutan kebijakan | Tahun tetap closed/staleFalse, padahal residual baru 100; tombol Tutup Ulang tidak tersedia menurut kondisi UI |
| CLOSE-02, P1 | Tutup ulang 120 → koreksi 10 → jurnal baru 130 tersimpan → acknowledgment gagal | Catatan dapat dipulihkan untuk menunjuk tepat satu jurnal 130 dan angka 130 | Catatan menunjuk jurnal 120 void, angka 120; setelah fitur pelepasan admin berhasil, retry 500 dan catatan belum pulih |
| GL-01, P1 | Beban 100 → pembalik → net 0 → anulir jurnal asal | Aksi pembatalan kedua ditolak tanpa efek, atau memakai proses koreksi pasangan yang eksplisit | Anulir diterima 200; pembalik tetap aktif dan P&L berubah menjadi laba 100 |
| GL-02, P1 | Beban sah 50 → request angka NaN/Infinity | Input tidak sah ditolak 4xx sebelum insert; laporan tetap memuat 50 | Request 200, native non-finite double tersimpan; response angka menjadi null; KPI GL dan beban P&L menjadi 0 |
| EQ-01, P1 | Laba operasional 100 → tutup buku → Perubahan Ekuitas | KPI laba periode tetap 100; perpindahan ke laba ditahan tidak mengubah laba operasi | net_income KPI berubah 100→0, sedangkan operating P&L100 dan pergerakan ekuitas 100 tetap benar |
| COA-01, P1 | Akun income khususA → jurnal 77 → pilih Semua Entitas | Laba 77 ikut agregat lintas entitas dan neraca tetap seimbang | LaporanA laba 77/balancedTrue, mode all laba 0/balancedFalse; dimensi tidak mencakup akun khusus entitas |

## Reopen bulan dan ketergantungan penutupan tahun

```text
Pendapatan Januari100
  → jurnal penutup Januari100: laba dipindahkan ke laba ditahan
  → penutupan tahunan: residual0 karena Januari sudah ditutup
  → admin Reopen Januari: jurnal bulan menjadi void
  → residual tahun sekarang100
  → record tahun tetap closed, staleFalse
  → UI hanya menawarkan Tutup Ulang jika staleTrue
```

Pemeriksaan tidak menyatakan persamaan neraca rusak: neraca tetap seimbang dan laporan laba rugi operasional tetap 100. Masalah berada pada informasi bahwa tahun telah selesai ditutup dan tindakan lanjutan yang tersedia. Penutupan tahun bergantung pada penutupan bulan; pembatalan bulan harus menginvalidasi hasil tahun. Source sudah mempunyai propagasi stale untuk reclose, tetapi belum menerapkannya pada reopen.

Direct API reclose tahun terbukti berhasil 200 sebagai alternatif pemulihan pada fixture ini. Karena tombolnya bergantung pada stale, keberadaan endpoint tidak membuktikan alur operator sudah mengakomodasi pemulihan. Kebijakan alternatif yang sah adalah mewajibkan pembukaan parent dahulu dan menolak child reopen sebelum efek; kebijakan itu harus dipilih secara eksplisit.

## Tutup ulang dan pemulihan setelah efek tersimpan

Flow normal terlebih dahulu dibuktikan: jurnal pendapatan 100 → close bulan → request unlock → approver berbeda menyetujui → koreksi 20 bertanda backdated_in_unlock → reclose menjadi 120. Semua langkah tersebut memakai original public producer, tanpa memasang state closed/unlock secara manual.

```text
Koreksi berikutnya10, total operasional130
  → klaim saga reclose
  → jurnal lama120 dianulir
  → original insert menyimpan jurnal baru130
  → fault terkontrol: acknowledgment tidak sampai ke caller
  → parent masih menyimpan net120 dan link jurnal120void
  → retry langsung409 karena lock, sesuai guard
  → lock dibuat berumur2jam sebagai fixture waktu
  → admin memeriksa/mengakui efek dan melepas lewat API asli:200
  → retry original mencoba insert source closing yang sama
  → unique active source index menolak; HTTP500
```

Fault wrapper hanya melempar setelah original insert berhasil; perhitungan dan penulisan jurnal tidak diganti. Aging lock hanya mengubah waktu klaim agar menguji jalur admin setelah batas tunggu tanpa menunggu secara nyata. Kunci dan unique index adalah kontrol yang bekerja: tidak ada jurnal kedua yang berhasil dibuat. Kecacatan terletak pada ketiadaan checkpoint/adopsi jurnal yang telah tersimpan, sehingga pelepasan yang sah tetap tidak memulihkan hubungan parent, snapshot dan jurnal.

Prompt perbaikan menuntut identitas operation/version, frozen totals dan checkpoint old/new JE. Recovery harus menyelesaikan parent menggunakan jurnal yang sesuai, atau melakukan compensation yang auditable. Menghapus unique index, mengabaikan exception, atau hanya melepaskan lock bukan penyelesaian.

## Pembalikan dan anulir tidak boleh membatalkan asal dua kali

Kontrol normal menunjukkan manual expense 100→void menghasilkan laba 0; manual expense 100→reverse juga menghasilkan laba 0. Namun reverse→void asal masih diterima. Jurnal pembalik bukan void, sedangkan asal yang sebelumnya mengimbanginya menjadi void; laporan yang benar-benar menghitung semua non-void journal kemudian melaporkan laba 100.

Ini terjadi dengan request biasa, tanpa fault injection. Source UI menyediakan Anulir Jurnal ketika source manual/status non-void, tanpa mempertimbangkan reversed_by_entry_id. Perbaikan harus berada pada gate backend dan CAS bersama; menyembunyikan tombol saja tidak menjaga request bersamaan atau pending reversal. Jika perusahaan membutuhkan koreksi atas pasangan jurnal, sediakan aksi tersendiri dengan aturan tanggal/link/jejak audit yang jelas.

## Input angka tidak sah dapat menyembunyikan transaksi sah

Pengujian menggunakan request oleh admin berizin dengan JSON valid: field float diberi string NaN atau Infinity. Schema melakukan coercion ke float. Create jurnal manual memasukkan langsung ke database dan tidak melewati validator pusat math.isfinite yang sudah dipakai jalur autopost. Perbandingan balance terhadap nilai non-finite tidak menghasilkan penolakan.

API sebenarnya memberi 200 dan angka yang disanitasi menjadi null; **hipotesis serialization 500 tidak dipakai**. Database masih menyimpan non-finite double, sehingga agregat akun tercemar. Setelah transaksi sah 50 pada akun yang sama, GL summary memberi total 0 dan balancedTrue, dan P&L menampilkan beban 0. Jadi keberhasilan response dan indikator balanced tidak mendeteksi hilangnya transaksi sah dari laporan.

Fixture ini menguji ketahanan input API; tidak diklaim bahwa input NaN dapat dilakukan dari formulir browser biasa. Perbaikan harus menolak nilai sebelum penulisan, memakai validator yang sama pada manual/import/autopost, dan mendeteksi data lama yang rusak. Mengubahnya diam-diam menjadi 0 akan mempertahankan kehilangan informasi. Evidence JSON menandai nilai native non-finite dengan objek non_finite agar file bukti tetap JSON yang valid.

## Sumber KPI laba pada perubahan ekuitas

```text
Laba operasi100
  → sebelum close: current_earnings100, equity API net_income100
  → closing: pindah100 ke retained earnings
  → sesudah close: current_earnings0, equity API net_income0
  → EquityChangesTab tetap berlabel Laba Periode Berjalan
  → operating P&L periode sama tetap100
```

Saldo awal, akhir dan total pergerakan ekuitas tetap dapat direkonsiliasi; ketiganya menjadi kontrol dan tidak dicatat sebagai salah. Kesalahan ada pada definisi net_income yang memakai perubahan laba belum ditutup, lalu ditampilkan sebagai laba periode. Perbaikan harus memisahkan laba operasional dalam rentang/scope yang sama dari pergerakan komponen current earnings. Jangan menambahkan laba kembali ke total ekuitas karena perpindahan closing sudah tercakup di komponennya.

## Mode Semua Entitas dan akun khusus entitas

Producer publik mendukung pembuatan akun khusus PT yang belum ada pada template global. Pengujian membuat akun income 4-7777 hanya untukA, kemudian jurnal sah debit kas 77/kredit akun tersebut 77. Laporan satu entitas memakai effective COA A dan menunjukkan laba 77 dengan benar.

```text
Akun khusus entitasA: income4-7777
  → original public manual journal77 tervalidasi dan seimbang
  → P&L entitasA: net77
  → mode Semua Entitas, scope A+B
  → scope_entity(scope multi) mengembalikan None
  → account dimension hanya mengambil template global
  → akun income4-7777 tidak diklasifikasi
  → P&L all net0; BS all assets307/equity230, balancedFalse
```

B tidak mempunyai jurnal Juli pada saat skenario ini berjalan. Kas 307 berasal dari producer sah 100+130+77 yang telah dijelaskan. Tidak ada konflik tipe override pada kode global, input non-finite, atau fault yang menyebabkan selisih 77. LaporanA tetap seimbang sebagai kontrol. Pengujian berikutnya terhadap invalid values berada pada entitasB dan bulanSeptember, sehingga bukan sumber counterexample ini.

Kecacatan spesifik ada pada endpoint Laporan Keuangan dengan entity_id=all. Fitur Konsolidasi Grup mempunyai helper lain; tidak dinyatakan gagal tanpa kontrol tersendiri. Perbaikan harus menyelesaikan dimensi pada grain legal entity+account, kemudian memetakan ke klasifikasi akun grup yang eksplisit. Jangan mengambil override PT pertama secara acak, menghilangkan akun yang belum dipetakan, atau menyamakan kode yang memiliki makna berbeda tanpa kebijakan. Laporan gabungan dan export harus merekonsiliasi partisi per entitas.

## Lokasi kode, bukti dan urutan perbaikan

- [D4-CLOSE-01 — backend/services/closing_service.py:346](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L346); terkait: [backend/services/closing_service.py:398](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L398), [frontend/src/features/finance/ClosingView.jsx:307](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/ClosingView.jsx#L307)
- [D4-CLOSE-02 — backend/services/closing_service.py:371](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L371); terkait: [backend/services/closing_service.py:404](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L404), [backend/routers/saga_locks.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L90), [backend/indexes.py:444](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/indexes.py#L444)
- [D4-GL-01 — backend/services/gl_service.py:755](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L755); terkait: [backend/services/gl_service.py:783](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L783), [frontend/src/features/finance/GeneralLedger.jsx:369](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/GeneralLedger.jsx#L369)
- [D4-GL-02 — backend/services/gl_service.py:640](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L640); terkait: [backend/services/gl_service.py:524](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L524), [backend/schemas_finance.py:53](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_finance.py#L53), [backend/services/gl_service.py:2974](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2974), [backend/services/financial_statement_service.py:88](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L88)
- [D4-EQ-01 — backend/services/equity_statement_service.py:57](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/equity_statement_service.py#L57); terkait: [frontend/src/features/finance/EquityChangesTab.jsx:61](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/finance/EquityChangesTab.jsx#L61), [backend/services/financial_statement_service.py:62](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L62), [backend/routers/financial_statements.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/financial_statements.py#L90)
- [D4-COA-01 — backend/services/financial_statement_service.py:54](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L54); terkait: [backend/services/financial_statement_service.py:40](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L40), [backend/services/gl_service.py:507](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L507), [backend/routers/gl.py:60](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/gl.py#L60), [backend/services/gl_service.py:651](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L651)


Empat perubahan lifecycle/validation CLOSE-01/02 dan GL-01/02 berada pada FASE-01. COA-01 berada pada FASE-03 untuk scope/dimensi, dan EQ-01 pada FASE-04 untuk menjaga definisi metrik dan roll-forward bersama. Dokumen 02, tracker dan prompt fase mencantumkan penyebab, potongan kode, expected/actual, acceptance dan hubungan antar temuan.

Bukti tersedia pada latest/repro/closing_reversal_probes.py, closing-reversal-results.json dan latest/evidence/closing-reversal-probes.log. Browser DOM, seluruh kombinasi fiscal year/role, semua source document dan printer belum diverifikasi. Hasil ini bukan sertifikasi seluruh finance/semua flow atau coverage 100%.


---

# Pengujian lanjutan WMS/RFID: klaim roll, perpindahan, identitas dan recovery

Tujuh temuan tambahan pada source `a904d989b622f7da14c4892d03cf6ef0c43f3084` memperluas pemeriksaan dari angka stok ke hubungan antarproses yang memakai roll yang sama. Empat berprioritas P1 dan tiga P2. Laporan rinci, potongan kode, prompt perbaikan dan acceptance masing-masing tetap tersedia pada dokumen 02 dan tracker; bab ini menjelaskan akibat pada rantai bisnis.

Pengujian memakai original public API untuk print job, pengakuan cetak manual, verifikasi EPC, routing, Putaway Order, pembuatan SO, device ingest, cycle count dan recovery admin. Roll dibuat oleh original inbound writer. Master produk, pelanggan, gudang, aktor dan sesi login adalah fixture sintetis yang sah. Startup indexes asli dipasang: 212 performance dan 25 unique, tanpa kegagalan.

**Batas bukti:** input scan dan pengakuan cetak dibuat sebagai input operator manual pada database localhost. Ini bukan pengujian RFID reader/printer/gate fisik. SO producer dan dokumen alokasinya benar-benar dieksekusi; seluruh approval/picking/cutting/loading/shipping berikutnya belum disertifikasi. Consumer UI ditelusuri dari source, tanpa DOM karena hambatan lingkungan browser yang dijelaskan pada dokumen 13. Clock kunci saga di-aging secara eksplisit untuk menguji recovery tanpa menunggu batas waktu; efek/retry/release memakai fitur asli.

Terdapat **49 observasi: 26 perbedaan state/angka dan 23 kontrol lulus**. Ini bukan 49 bug. Setiap perbedaan dikelompokkan ke akar masalah pada tujuh ID; harness errors 0 dan koneksi eksternal 0.

| Temuan | Seharusnya | Teramati melalui producer/API asli | Dampak dan batas |
|---|---|---|---|
| PA-01: klaim PA lalu SO | Tidak ada klaim yang konflik; perpindahan/reservasi terkoordinasi | SO qty dan explicit-roll menerima 10/6 pada roll yang diklaim PA | Status available saja tidak mencerminkan siapa yang memakai roll |
| PA-01: reservasi parsial 6 pada roll 10 | PA berhenti atau melakukan rebinding alokasi/task yang sah | Dispatch/arrival berhasil; roll tujuan, SO allocation tetap gudang asal | Source pemenuhan dokumen tertinggal dari SSOT roll; fulfillment berikutnya belum diuji penuh |
| PA-02: fault setelah lokasi roll berubah | Recovery melengkapi tag/mutasi/saldo/parent | Roll tujuan, tag asal, mutasi 0, saldo asal 10/tujuan 0; retry/accept tetap exception | Inspector efek kosong; release lock tidak menyelesaikan operasi |
| PA-03: 10 meter + 10 yard |19.144 meter atau breakdown per unit | Saran dan total PA 20 meter | Per-item benar, total/label salah; dua desimal 19.14 boleh bila policy jelas |
| WMS-04: roll sudah reserved | Ready 0 atau queue dengan blocked 1 yang jelas | Suggest 0/create 400, health ready 1 | Dua layar memberi arti kesiapan berbeda untuk stock yang sama |
| RFID-01: observation durable/read gagal | Event yang sama melanjutkan langkah tersisa | Replay count 0/read 0; event baru REPLAY_EXIT | Tidak ada green read awal untuk merekonsiliasi exit stamp |
| RFID-01: red read durable/incident gagal | Recovery membentuk incident dan red passage/latch | Red read 1, incident 0, passage info/latched=False | Salah state pada gate-status API; bukan klaim kondisi lampu fisik |
| CC-01: result durable/parent gagal | Satu result/nomor per session/revision | Admin release+retry menciptakan dua laporan/nomor untuk session sama | Histori count terduplikasi; stock memang tidak diubah oleh laporan |
| TAG-01: retire atau EPC baru pending | Bukti identitas lama tidak mengesahkan current tag | PA menerima current tag=None atau pending_print | Empty/new EPC dapat masuk manifest tanpa verifikasi current identity |

## Kontrol normal dan alur yang sudah bekerja

```text
Original inbound roll10 + lot
  → public create RFID print job: pending_print
  → operator mark-printed: tag active
  → start verify → manual scan EPC → complete: clean/tag_verified
  → routing SIMPAN
  → PA create: klaim active_movement
  → PA dispatch: in_transit_transfer
  → confirm-arrival dengan EPC
  → PA completed dan BTG
  → roll/tag gudang tujuan
  → dua mutasi dan rebuild asal0/tujuan10
```

Alur tersebut lulus sebagai kontrol. Normal device ingest keluar dengan PA aktif juga memberikan MOVEMENT_OUT dan tepat satu read; replay event ID yang sudah lengkap menjadi duplicate tanpa read kedua. Normal count menghasilkan accuracy 100/satu laporan; complete ulang ditolak 400. Original SO mode pilih roll mengisi qty reservasi sesuai 10 atau 6, bukan salah kuantitas. Temuan menguji konflik/recovery/identitas/label di luar kontrol itu.

## Hubungan putaway dengan reservasi penjualan

PA open membiarkan roll available sambil menulis active_movement. SO qty memakai _available_rolls_for_order dan CAS reservasi; SO explicit roll memakai reserve_roll_mode_item/reserve_specific_rolls. Kedua jalur menerima roll itu. Artinya klaim pada satu modul belum menjadi kontrak yang dihormati modul lain.

```text
PA open: roll10 available + active_movement PA
  → SO qty6 / pilih roll exact_cut6
  → parent tetap available, length_reserved6
  → persisted SO allocation: warehouse ASAL, pending_cut
  → PA dispatch hanya memeriksa status + movement + asal
  → PA arrival: parent dipindah ke TUJUAN
  → persisted SO allocation masih ASAL
```

Ini request berurutan biasa, tanpa fault atau race buatan. Reservasi utuh 10 mengubah status reserved, sehingga dispatch 409; guard ini benar tetapi operator menghadapi konflik yang seharusnya dikoordinasikan lebih awal. Reservasi parsial menjaga status available, sehingga dispatch masih 200. Memperbaiki hanya guard dispatch belum menghilangkan offer/claim konflik di sales; memperbaiki hanya daftar candidate juga belum melindungi CAS saat race.

Kebijakan bisnis dapat memilih menunda SO sampai PA selesai, atau membolehkan reservasi sambil mengatur ulang source/task secara eksplisit. Pilihan kedua membutuhkan koordinasi dan audit trail, bukan sekadar menyaring active_movement. Prompt tidak memaksakan bahwa semua perpindahan dengan reservasi selamanya dilarang.

## Recovery perpindahan tidak selesai dengan melepas kunci

Fault ditempatkan sesudah update roll asli sudah tersimpan dan sebelum update tag. _land_items sudah menghapus active_movement dan mengubah warehouse. Parent PA masih in_transit, tag/balance belum mengikuti. Guard kunci langsung menolak retry 409 adalah kontrol yang benar.

Inspector kemudian tidak menemukan efek, karena memeriksa sumber inventory_rolls berdasarkan source_ref/created_at, bukan transition pada existing roll. Setelah release yang sah, confirm retry gagal mengadopsi roll tujuan: syarat CAS masih asal+active_movement. Accept exception memakai jalur yang sama, sehingga mengulang ketidakcocokan tersebut. Hasil final tetap completed_with_exception, tanpa dua mutasi, BTG yang benar atau saldo tujuan.

Perbaikannya memerlukan operation/checkpoint yang menjelaskan roll mana sudah berpindah, dari/ke mana, atas dokumen/version apa, dan langkah mana belum lengkap. Rebuild balance adalah proyeksi dari roll, bukan pengganti penyelesaian manifest, tag dan audit trail. Rebuild manual saja tidak menutup temuan.

## Identitas fisik dan bukti verifikasi harus merujuk tag saat ini

Client menetapkan semua roll harus bertag, termasuk stock dan transit untuk SO. Pengujian TAG-01 tidak memakai barang tanpa tag secara arbitrer: roll awal sudah melalui print/verify asli, lalu public retire membuat tag=None. Journey lama tetap tag_verified. PA memakai stage itu sebagai izin dan menerima EPC kosong.

Pada skenario penggantian, print job baru membuat pending_print; tag tersebut belum diakui tercetak dan belum discan, tetapi PA tetap diterima memakai stage verifikasi lama. Stage perjalanan fisik dan identity readiness perlu dipisahkan agar retag tidak mengubah lokasi/transit dengan keliru. Bukti harus menunjuk current tag ID/EPC/version yang sesuai roll; active tag saja belum membuktikan EPC baru sudah diverifikasi.

## Ketahanan ingest: observation bukan bukti seluruh proses sudah selesai

Pipeline menyimpan raw observation, menentukan keputusan, menulis exit stamp/read, membentuk incident merah, kemudian mengagregasi passage dan latch. Event ID hanya menjaga insert observation. Jika read atau incident gagal, event yang sama dianggap duplicate sehingga tidak melanjutkan efek. EPC baru dalam dwell mengambil cached read dan juga melewati efek insiden/passage yang belum selesai.

```text
GREEN: observation + exit stamp durable
  → read insert gagal
  → event sama: duplicate / no decision
  → event baru: REPLAY_EXIT, bukan recovery original green

RED: observation + red read durable
  → incident creation gagal
  → event sama: duplicate
  → event baru dalam dwell: cached red, tanpa incident/passage posting
  → gate-status passage info, latchedFalse
```

Tidak ada stock mutation oleh ingest; kontrol ini lulus dan harus dipertahankan. Temuan baru adalah ketahanan checkpoint event/decision/incident. V3-RFID-01 yang lebih dahulu dicatat membahas keputusan cache yang menjadi basi saat movement berubah; kedua akar masalah berhubungan tetapi tidak disamakan.

## Metric dan duplikasi yang melanjutkan dampak ke UI

Saran putaway dan PA menyimpan qty per roll yang benar. Namun grain group hanya owner/kategori/grade, sehingga base units dua SKU berbeda dijumlahkan mentah. UI memberi satu label unit pertama. Jangan menyelesaikan dengan mengubah label produk atau memaksa semua data unit sama; tampilkan per-unit breakdown atau konversi sah.

Warehouse Health menghitung old tag_verified pada roll yang sudah direservasi oleh SO, sementara actual suggestion/creation menolaknya. Jika pelanggan membutuhkan antrean fisik termasuk blocked, kontrak harus membedakan pending/ready/blocked dan alasan, bukan menyebut semua ready. Resolver eligibility bersama tetap perlu CAS pada saat aksi.

RFID cycle count memang laporan saja. Lost acknowledgment setelah result insert membuat parent masih open/locked; release dan retry membuat nomor/result baru. Satu scan session bisa tampil sebagai dua kegiatan opname. Unique session+revision serta adoption existing result menjaga recount yang disengaja tetap terpisah dari retry akibat gangguan.

## Kode, bukti dan fase perbaikan

- [D4-PA-01 — backend/services/roll_service.py:792](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L792); terkait: [backend/services/putaway_order_service.py:152](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L152), [backend/services/putaway_order_service.py:200](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L200), [backend/services/roll_service.py:736](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L736), [backend/services/roll_service.py:549](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L549), [backend/routers/sales_orders.py:421](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/sales_orders.py#L421), [backend/services/sales_order_helpers.py:123](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_order_helpers.py#L123)
- [D4-PA-02 — backend/services/putaway_order_service.py:232](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L232); terkait: [backend/services/putaway_order_service.py:280](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L280), [backend/services/putaway_order_service.py:329](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L329), [backend/services/roll_service.py:233](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L233), [backend/routers/saga_locks.py:42](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L42), [backend/routers/putaway_orders.py:74](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/putaway_orders.py#L74)
- [D4-PA-03 — backend/services/putaway_order_service.py:49](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L49); terkait: [backend/services/putaway_order_service.py:166](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L166), [frontend/src/features/wms/PutawayOrdersPanel.jsx:104](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/PutawayOrdersPanel.jsx#L104), [frontend/src/features/wms/PutawayOrdersPanel.jsx:144](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/PutawayOrdersPanel.jsx#L144), [backend/services/roll_service.py:1890](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L1890)
- [D4-WMS-04 — backend/services/wms_health_service.py:42](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L42); terkait: [backend/services/putaway_order_service.py:19](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L19), [backend/services/putaway_order_service.py:113](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L113), [frontend/src/features/wms/WmsHealthDashboard.jsx:16](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/WmsHealthDashboard.jsx#L16)
- [D4-RFID-01 — backend/services/rfid_ingest_service.py:138](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L138); terkait: [backend/services/rfid_ingest_service.py:190](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L190), [backend/services/rfid_ingest_service.py:194](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L194), [backend/services/rfid_ingest_service.py:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L151), [backend/services/rfid_ingest_service.py:214](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L214), [backend/services/gate_evaluator.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gate_evaluator.py#L129), [backend/routers/rfid.py:551](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfid.py#L551)
- [D4-CC-01 — backend/services/cycle_count_service.py:124](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L124); terkait: [backend/services/cycle_count_service.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L129), [backend/routers/saga_locks.py:33](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L33), [backend/routers/rfid.py:650](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfid.py#L650)
- [D4-TAG-01 — backend/services/putaway_order_service.py:132](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L132); terkait: [backend/services/rfid_service.py:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_service.py#L151), [backend/services/rfid_print_service.py:130](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_print_service.py#L130), [backend/services/rfid_print_service.py:327](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_print_service.py#L327), [backend/services/putaway_order_service.py:108](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L108)

FASE-01 menangani PA-02, RFID-01 dan CC-01 karena ketahanan posting/recovery harus stabil sebelum projection diperbaiki. FASE-02 menangani PA-01, PA-03 dan TAG-01 sebagai kontrak roll/perpindahan/identity/unit. WMS-04 berada pada FASE-04; bergantung pada kebijakan dan resolver eligibility yang disepakati di FASE-02.

Bukti: [skrip original-chain](baseline-78/latest/repro/wms_movement_probes.py), [expected/actual dan persisted context](baseline-78/latest/repro/wms-movement-results.json), serta [log eksekusi](baseline-78/latest/evidence/wms-movement-probes.log). Setiap source permalink menuju SHA yang diperiksa. Agent tidak boleh menutup temuan hanya karena endpoint 200, lock berhasil dilepas atau stok pada satu layar terlihat benar.

Bab ini tidak menyatakan coverage 100%. Gate/printer fisik, offline middleware, seluruh state multiwarehouse dan seluruh kombinasi source/role/error tetap memerlukan pengujian sebagaimana register dokumen 13.
