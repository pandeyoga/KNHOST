# Laporan Audit — Penyusunan Pelatihan Keuangan (17 Nov 2026)

Setiap skenario pelatihan dijalankan **di layar** (Playwright, akun peran yang sama dengan peserta) lalu dicocokkan **di buku**
(jurnal seimbang, saldo, status). Yang tidak lulus ditelusuri sampai akar masalah, diperbaiki dengan uji terarah, atau
dicatat sebagai keputusan pemilik. Rekap hasil uji per skenario ada di panduan (bagian *Rekap uji jalan*).

Status: **D** = diperbaiki (berkas · uji) · **K** = perlu keputusan pemilik · **C** = catatan untuk pelatih/data.

## 0. Hasil uji akhir (kode final, data dipulihkan bersih)

| Uji | Hasil |
|---|---|
| Pemulihan data acuan dari nol (`restore_local_demo.sh`, kode terbaru) | lulus — 9/9 skenario transaksi demo OK |
| Data latihan (`seed_pelatihan_keuangan_kn.py`) | peserta kelas 01 + peserta peraga 21, 31, 41–43, 61, 66, 72, 81 lulus; peserta baru sesudah aktivitas kelas juga lulus (C-31) |
| **Uji jalan kurikulum lengkap Bagian 0–5** (`uji/jalankan_semua.sh`, berurutan sesuai kurikulum) | **40 skrip · 459/459 langkah lulus di layar + buku · 0 galat 5xx**. Praktik Finance (F, K, H) berurutan di SATU akun peserta kelas (01) seperti di kelas; alur ujung ke ujung A1–A3 di peserta peraga 21, 31, 41–43; Bagian 5: S1 (61) 20/20 · S2 (66) 31/31 · S3 (72) 34/34 · S4 (81) 41/41; potret navigasi 36 layar. Tangkapan layar manual & slide dari putaran ini |
| Bukti setiap klaim di teks materi (V9) | 433 klaim: 346 terbukti uji lama · 47 dibuktikan baru di layar (61/61) · 20 teks dikoreksi · 1 bug diperbaiki · 16 menunggu keputusan pemilik · 3 belum (perilaku kelas / memengaruhi semua pengguna) — §2d |
| Dokumen cetak (`uji/dokumen/`, peserta 01, data bersih) | D1 dokumen penjualan 12/12 · D2 dokumen keuangan 16/16 · D3 naskah/template 9/9 |
| Uji variasi isian & hitungan (`uji/variasi/` V1–V8) | 164 kasus (lihat §2a) |
| Jest penuh (pohon akhir) | 1.717 lulus · 9 gagal = himpunan lama yang sama (phase3P3, roleGateSweep2, phase4R1, fe07ReturnErrors, phase3P8Activation) |
| Backend `tests_mem` penuh (pohon akhir) | 2.503 lulus · 0 gagal |
| Gate `--ci` (pohon akhir) | keluar 1 (merah lama) · dibanding garis dasar `2026-11-17_latih_keuangan2_gate_ci.log`: **tidak ada pelanggaran baru**. Log: `docs/blueprint/garis-dasar-gate/2026-11-17_latih_keuangan3_gate_ci.log` |

## 1. Data acuan & data demo

| # | Temuan | Akar masalah | Status |
|---|---|---|---|
| A-01 | Skrip transaksi demo (`seed_demo_transaksi_kn.py`, dipakai `deploy/setup_demo_lengkap.sh` dan pemulihan data acuan) gagal 5 dari 9 skenario: pembelian, pindah gudang, tiga skenario penjualan | Aturan sesudah skrip ditulis: ambil barang wajib pindai roll (FIX-3b), SPK kedatangan khusus MD Quality (QC 4-point SPK tersendiri), alasan jalur makloon, nilai jasa makloon diisi Pembelian (MP-T4b), pelunasan bersen | D · `backend/scripts/seed_demo_transaksi_kn.py` · dijalankan ulang 9/9 lulus pada pemulihan bersih |
| A-02 | Skrip data acuan P03 gagal: transfer ke Gudang Utama Kanda (sudah nonaktif) | Struktur gudang baru menonaktifkan gudang lama | D · `seed_p03_kn.py` (tujuan Gudang Transit Rancamalang) |
| A-03 | Skrip data acuan P05 gagal: celup langsung dari greige | MP-T1: proses celup wajib berbahan PFD | D · `seed_p05_kn.py` (pre-treatment → celup) |
| A-04 | Akun Sementara 1-9999 bersaldo kredit (KSC −Rp 12 jt) di data demo → daftar periksa tutup buku bulan berjalan merah | Contoh kas bawaan (`bootstrap.py` "Top-up kas kecil", kategori `transfer` satu sisi) dan kas demo "Penjualan karung" (kategori `lain`) tidak punya pasangan akun → otomatis ke Suspense (sesuai rancangan F-8, harus direklasifikasi) | C · peragaan tutup buku memakai bulan kosong; reklasifikasi suspense bisa dijadikan materi |

## 2. Temuan layar & buku selama uji skenario

Diisi dari hasil keempat bagian (Piutang, Kas & Bank, Hutang/Pajak/Gaji, Orientasi/Buku Besar/Manajer).

| # | Skenario | Temuan | Akar masalah | Status |
|---|---|---|---|---|
| B-01 | F01 | Kartu "Selisih bayar perlu diputus" di Beranda Keuangan: tombol menggantung "Memproses…", nilai Rp 0 | `work_desk_service` membaca kunci yang tidak dikirim `pending()` | D · `backend/services/work_desk_service.py` · `tests_mem/test_latih_keuangan_bagian_d.py` |
| B-02 | F16 | Finance (lihat saja) melihat tombol Jurnal Baru, Sinkronkan, Balik/Anulir, tambah/ubah/hapus akun → ditolak 403 saat diklik | Tombol tidak dijaga izin | D · `GeneralLedger.jsx`, `GeneralLedgerTabs.jsx`, `JournalDetailModal.jsx`, `useJournalActions.js`, `ChartOfAccounts.jsx` · `latihBukuBesarIzin.test.js` |
| B-03 | F16 | Simpul jurnal di Jejak Dokumen tanpa nilai | `doc_refs_service` tidak mengisi nilai jurnal | D · `backend/services/doc_refs_service.py` |
| B-04 | F17 | Profitabilitas: "Selisih belum dijelaskan" ≠ 0 bila ada pendapatan denda (4-9300) | Pendapatan lain di Laba-Rugi tidak masuk rekonsiliasi | D · `profitability_service.py` · `test_PK41_laporan.py` |
| B-05 | F18 | Tombol "Reopen" berbahasa Inggris | Label | D · `ClosingView.jsx` |
| B-06 | F01 | Bilah atas Finance menampilkan "Lokasi kerja belum diatur" (tidak relevan untuk keuangan) | Bilah cakupan lokasi tampil untuk semua pemegang `product.view`/`logistics.view` | D · teks peringatan disembunyikan bagi akun tanpa izin gudang (ikon & tooltip tetap) · `LocationScopeBar.jsx`, `App.js` · `fix1Cakupan.test.js` |
| B-07 | F01 | Akun Finance tercatat sebagai karyawan "Manajemen › Manajer" gaji 5 jt (Profil Saya, berpotensi masuk penggajian) | `bootstrap.ROLE_TO_ORG` tidak memetakan `finance`; peran tak terpetakan jatuh ke "Manajer" | D · `bootstrap.py` (Finance → Keuangan & Admin › Akunting, Admin Sales → Staf Admin, peran lain tanpa jabatan) · `test_latih_hr_jabatan.py`. Karyawan yang sudah terbentuk tidak diubah — HR memperbaiki di Karyawan |
| B-08 | F11 | Finance melihat tombol Kirim/Batalkan tagihan supplier → 403 | Tombol tidak dijaga `vendor_bill.update` | D · `VendorBillDetailPanel.jsx`, `VendorBillsView.jsx` · `latihCHutangTombol.test.js` |
| B-09 | F12 | Rincian kontrabon untuk Finance: "hanya bisa memantau… keputusan atas uang ada di Keuangan" (membingungkan) | Teks peran | D · `ContraBonDetailPanel.jsx` (menyebut langkah berikutnya & kapan Finance membayar) |
| B-10 | F15 | Nominal setoran PPh 21 "40.864,5" tersimpan 40,8645 | Input teks dibaca `parseFloat` | D · `PayrollRemittancesView.jsx` (MoneyInput + `parseDecimal`) |
| B-11 | — | Pusat Export › Tagihan Pemasok: kolom Sisa & Status bayar basi sesudah tagihan dibayar | Pembayaran hanya menambah `amount_paid`; `outstanding`/`payment_status` tersimpan tidak diperbarui | D · dihitung ulang di dataset (`export_registry.py`, rumus `bill_financials`) · `test_latih_ekspor_tagihan.py` |
| B-12 | — | Profil pelanggan (CRM) dibuka Finance → 403 warna eksklusif di konsol | Bagian warna dimuat tanpa cek `color.view` | D · `Customer360Panel.jsx` |
| B-13 | F02 | Label "Jurnal Terbit" di Riwayat AR tidak bisa diklik | Kwitansi tidak menyimpan `journal_entry_id` | D · `ar_receipt_service.py` (kwitansi lama diisi saat dibaca) · `test_LATIH_piutang.py` |
| B-14 | F04 | "Pakai titipan" di mode Atur sendiri tidak melunasi SO dan memunculkan "lebih bayar" palsu | Titipan ditambahkan di luar alokasi | D · `ReceivePaymentModal.jsx` · `latihPiutangTitipan.test.js` |
| B-15 | F04 | Pesan lebih bayar hanya menyebut nominal teralokasi (Rp 2.088.077), bukan uang diterima (Rp 2.500.000) | Teks memakai angka alokasi | D · `ReceivePaymentModal.jsx` |
| B-16 | F03 | Selisih atas SO yang belum jatuh tempo ditulis "tagihan yang jatuh tempo" | Teks tidak membedakan jatuh tempo | D · `payment_variance_service.py` |
| B-17 | F05 | Status rencana cicilan tampil "Active" | Label tak diterjemahkan | D · `PaymentPlansView.jsx` |
| B-18 | F06 | Pencarian di Kredit & Plafon tertimpa jawaban lama yang datang belakangan | Tanpa penjaga balapan permintaan | D · `CreditDeskView.jsx` · `latihPiutangKredit.test.js` |
| B-19 | F02 | Satu dialog menampilkan Rp 3.484.012 (pesan server) dan Rp 3.484.013 (layar) untuk tagihan yang sama | Server `rupiah()` membulatkan ala bankir, layar setengah ke atas | D · `core_utils.py` · `test_latih_rupiah_bulat.py` |
| B-20 | F10 | Teks mutasi yang DITEMPEL tercatat bersumber "berkas" | Sumber impor salah | D · `bank_recon_service.py` · `test_pelatihan_kas_bank.py` |
| B-21 | F10 | Ringkasan rekonsiliasi berperiode: sisi buku tidak ikut periode → kartu "Selisih" tak bermakna | Saringan tanggal hanya sisi bank | D · `bank_recon_service.py` |
| B-22 | F10 | "Catat biaya bank", "Catat bunga bank", "Titipkan" langsung menjurnal sekali klik | Tanpa konfirmasi nominal & PT (aturan N5) | D · `ReconLinesTable.jsx` · `pelatihanKasBank.test.js` |
| B-23 | F09 | Setiap nominal diketik Finance memicu cek anggaran → 403 di konsol | Cek anggaran dipanggil tanpa `budget.view` | D · `CashManagementView.jsx` |
| B-24 | F16 | Buku Besar menampilkan sumber "Cash holding" (Inggris) | Label sumber belum ada | D · `glSourceLabels.js` ("Titipan Tunai Sales") |
| B-25 | F07 | LPJ kas kecil yang diketik Finance atas nama karyawan mencatat Finance sebagai pengembali sisa | Bawaan pengembali = pembuat | D · `cash_advance_service.py` (bawaan = pemohon PD) |
| B-26 | F09 | Transaksi Kas kategori "Transfer / Top-up": keluar → beban 6-4000, masuk → Suspense 1-9999 (beban palsu saat setor kas toko ke bank) | Kategori `transfer` tidak terpetakan | D · `gl_service.py` (lewat 1-1150 Kas Transit, sama dengan pindah-buku G-9) · `test_latih_kas_transfer.py` |
| B-27 | F16 | Mencari jurnal dengan nomor kas/kwitansi (KSC/CASH-…) tidak menemukan apa pun | Pencarian tidak membaca `source_label` | D · `gl_service.py` · `test_latih_kas_transfer.py` |
| B-28 | F05 | Rencana & Denda › [Buka pesanan] membuka Daftar Pesanan tanpa panel pesanan bila pesanan itu tidak di halaman 1 (ketahuan saat data lengkap berisi 40 pesanan) | Tautan tanpa nomor SO (juga dari Titipan & Saldo Kredit dan Inbox Persetujuan); sejak M16 panel hanya untuk pesanan yang tampil | D · `OrdersView.jsx` (nomor diambil dari server lalu daftar disaring ke pesanan itu) · `latihTautanPesanan.test.js` |
| B-29 | F01 | (Skrip uji) laba negatif di tab Analisis terbaca positif; kata cari "Latihan NN" ikut memunculkan pelanggan cicilan | Kesalahan skenario, bukan aplikasi | D · `uji/F01_orientasi.js`, `src/skenario/F01.json` (cari "Toko Kain Peserta NN") |

## 2a. Uji variasi isian & kebenaran hitungan (sesudah 142 langkah lulus)

Setiap isian yang diketik peserta diuji dengan variasi wajar di layar, lalu hasilnya dicocokkan dengan buku. Tabel lengkap:
`src/variasi_piutang_kas.json` (86 kasus) dan `src/variasi_hutang_pajak_gaji.json` (71 baris / 78 kasus), skrip `uji/variasi/`.
Lampiran A di panduan memuat tabel yang sama.

| # | Layar | Temuan | Akar masalah | Status |
|---|---|---|---|---|
| V-01 | Semua kotak nominal (±106 layar) | "3.374.123" terketik jadi Rp 3; "1.000.000,50" di kotak alokasi jadi Rp 50; tempelan "Rp …" ditolak diam-diam; "3374122,5" terbaca 0 | Pembaca angka kotak nominal hanya mengenal satu gaya | D · `components/MoneyInput.jsx` + `utils/parseMoney.js` (gaya Indonesia, Inggris, "Rp", spasi, ",-") · `parseMoney.test.js`, `moneyInput.test.js` |
| V-02 | Kotak nominal | Pratinjau membulatkan sen (Rp 40.865 untuk 40.864,50) — beda dengan nilai tersimpan | Format tanpa desimal | D · `MoneyInput.jsx` · `latihKlikGandaPratinjau.test.js` |
| V-03 | Terima pembayaran | Mengetik sebelum form selesai memuat bercampur dengan isian otomatis ("50.000" → "832.500"); nominal minus tanpa pesan | Isian otomatis menimpa ketikan | D · `ReceivePaymentModal.jsx` (`amountTouched`, pesan "Nominal tidak boleh minus.") · `latihVariasiTerimaBayar.test.js` |
| V-04 | Dialog konfirmasi | Klik ganda [Simpan kwitansi] menutup dialog konfirmasi (tidak ada kwitansi ganda, peserta harus klik lagi) | Klik ke-2 jatuh di latar dialog baru | D · `utils/overlayDismiss.js` · `latihKlikGandaPratinjau.test.js` |
| V-05 | Kas Kecil · LPJ | Baris LPJ bernominal minus atau tanpa nominal dibuang diam-diam; LPJ melebihi PD menampilkan [Bayar] (ditolak server) menggantikan [Buka] | Validasi & label tombol | D · `SettlementForm.jsx`, `PettyCashView.jsx` · `latihVariasiKasKecil.test.js` |
| V-06 | Rekonsiliasi (tempel) | "3240090.00" terbaca ×100 tanpa peringatan; "1,500,000.00" ditolak; pemisah TAB/";"/spasi ganda ditolak; tanpa baris judul "0 baris" tanpa alasan | Pembaca mutasi | D · `bank_statement_parser.py`, `ReconImportPanel.jsx` (alasan tiap baris dilewati) · `test_latih_variasi_piutang_kas.py` |
| V-07 | Bayar tagihan supplier | Nominal "1764800,5"/"1 864 800" salah baca; lebih bayar Rp 100 diam-diam jadi uang muka pemasok; kurang bayar ≤ Rp 5.000 ditutup otomatis tanpa pemberitahuan; sen dibulatkan | Form & pesan | D · `PaySupplierModal.jsx`, pesan server dalam rupiah · `bayarPemasokVariasi.test.js`, `test_latih_variasi_hutang.py` |
| V-08 | Gaji (akrual insentif) | **Beban Insentif Oktober kurang ±Rp 17,6 jt**, Hutang Insentif 2-1500 bersaldo debit: akrual hanya memakai komisi proses gaji TERAKHIR | `posting_registry.py` | D · menjumlah semua proses terposting di bulan itu · `test_latih_variasi_gaji.py` |
| V-09 | Bayar tagihan bertanggal maju | Pembatalan pembayaran bertanggal maju dibalik dengan tanggal hari ini → bank & hutang November menggelembung | Tanggal jurnal pembalik | D · `vendor_bills.py` (tanggal = tanggal bayar asal) |
| V-10 | Laporan | Rentang tanggal terbalik → semua Rp 0 tanpa pesan | Validasi rentang | D · pemilih tanggal dibatasi (3 tab) + server 400 berbahasa Indonesia |
| V-11 | Sample berbayar · Setoran · Antrean gaji | Persetujuan sample tanpa info uang diterima; setoran tanpa sen; antrean bayar gaji 20 baris (gaji peserta di halaman 2) | Tampilan | D · `SampleOrdersView`, layar setoran, antrean 50 baris |

Hitungan yang dicocokkan dengan rumus sendiri (semua cocok): sisa SO sesudah bayar sebagian · saldo titipan pelanggan · saldo Kas Toko
· uang muka PD bersih · ringkasan rekonsiliasi · kolom umur piutang · denda (taksiran → nota → jurnal 4-9300) · pembayaran tagihan
bertahap (Rp 500.000 + Rp 1.364.800 dengan klik ganda = satu pembayaran) · kontrabon (Rp 1.287.600 − potongan Rp 12.600 = Rp 1.275.000)
· faktur pajak (DPP × 11/12 × 12% = PPN Keluaran jurnal pengiriman) · PPh 21 susulan · neraca saldo, Laba-Rugi, Neraca, Arus Kas
(hari ini, Oktober, satu hari).

## 2b. Dokumen cetak & pengaturan naskah

22 dokumen/jalur cetak diperiksa (`src/dokumen_cetak.json`, skrip `uji/dokumen/`, gambar halaman `uji/hasil/D1–D3/`): isi dicocokkan
dengan transaksi (nomor, tanggal, identitas PT, baris barang, DPP, PPN, total, terbilang), format diperiksa, pengaturan naskah diuji.

| # | Dokumen | Temuan | Status |
|---|---|---|---|
| P-01 | Surat Jalan, Daftar Kemasan, Surat Pengambilan | Setiap roll tercetak DUA kali (1 roll 117,79 yd → "2 roll 235,58 yd"); nomor roll = id internal; "Dibuat Oleh" = id pengguna; tanggal SJ = tanggal cetak | D · `pdf_resolvers.py` |
| P-02 | Faktur, rekening koran | Nominal bersen tercetak dibulatkan sementara terbilang menyebut angka lain | D · nominal & terbilang bersen ("… lima puluh sen") |
| P-03 | Tagihan Supplier | DPP Rp 0, Ref PO = id internal, tanpa baris barang/jatuh tempo/sisa | D |
| P-04 | Faktur Komersial | Tanpa jatuh tempo, sudah dibayar, sisa, rincian per surat jalan/cicilan | D |
| P-05 | Semua | Footer berisi "&"/kutip tercetak "&amp;"; judul Inggris (Official Receipt, Vendor Bill, Sales Quotation); "Rp" terpotong | D · `pdf_engine.py` · `test_LATIH_dokumen_cetak.py` |
| P-06 | Slip gaji | Selalu berkop "Kain Nusantara" (bukan nama PT) | D · `routers/hr_payroll.py` · `test_latih_slip_kop.py` |
| P-07 | Bukti Kas Keluar/Masuk | Judul "Payment/Received Voucher", pilihan "Petty Cash", angka Rp 3.268.673 ≠ terbilang "…672" | D · `utils/docPrint.js` · `latihBuktiKas.test.js` |
| P-08 | Pengaturan naskah (Desainer PDF) | Ubah judul, teks penutup bertoken, footer → tercetak; aturan khusus PT hanya di PT itu; token salah ditolak dengan pesan jelas; Finance 403 saat menyimpan; dikembalikan → cetakan identik | Lulus |
| P-09 | Keterangan jurnal kas "Kas in/out" (Inggris) — ikut tercetak di rekening koran | D · `gl_service.py` → "Kas masuk/keluar" (jurnal baru; jurnal lama tetap), teks skenario & uji diperbarui |
| P-11 | Faktur Komersial pesanan LUNAS | Kolom jatuh tempo tercetak "Lunas" (tidak ada tagihan terbuka) — rancangan; uji disesuaikan | Lulus |
| P-12 | Bukti Kas | "Rp" terpisah dari angka di kolom sempit | D · `utils/docPrint.js` (angka tidak dipotong baris) |
| P-10 | Surat Jalan | Satu SJ per pesanan, bukan per pengiriman — pengiriman bertahap tercetak gabungan | C (rancangan) |

Akibat saat deploy: dokumen yang SUDAH ditandatangani elektronik dan isinya berubah karena perbaikan di atas akan tercetak
"belum ditandatangani (versi baru)" — perlu ditandatangani ulang bila dipakai.

## 2c. Penyusunan ulang materi (17 Nov sore): fondasi, alur ujung ke ujung, retur, SDM

Masukan pemilik: materi terasa tidak berurutan, belum ada konfigurasi, bahasa kurang rapi; fondasi dulu (mulai dari Bagan
Akun), SDM dipegang Finance, dan alur ujung ke ujung (pesanan sampai uang masuk, pengadaan sampai bayar, retur) harus
dijelaskan dan diuji sebagai pengguna. Materi disusun ulang menjadi 5 bagian (`src/kurikulum.json`, `src/PANDUAN_GAYA.md`)
dan setiap materi baru dijalankan di layar dengan akun peran, lalu jurnalnya dicocokkan.

| # | Materi | Temuan | Akar masalah | Status |
|---|---|---|---|---|
| C-01 | K01 | Ikon hapus di Bagan Akun per PT juga tampil untuk akun Template Global → akun template bukan-baku bisa terhapus dari **semua PT**, tanpa konfirmasi | Ikon tidak membedakan akun khusus PT dan akun template | D · `ChartOfAccounts.jsx` (hanya akun khusus PT, selalu konfirmasi) · `latihK01HapusAkun.test.js` |
| C-02 | K03 | Manajer tanpa izin audit membuka Riwayat PT → "Belum ada perubahan tercatat" (sebenarnya 403) | Galat akses dibaca sebagai daftar kosong | D · `EntityDetailDrawer.jsx` · `latihK03RiwayatPt.test.js` |
| C-03 | K04 | Petunjuk di form rekening menunjuk "Pengaturan › Keuangan & Pajak › Cara Bayar" (tidak ada di sana) | Teks lama | D · `BankAccountForm.jsx` (Perusahaan (PT) › Master per PT › Cara Bayar) |
| C-04 | H01 | **Tambah Karyawan gagal 500** ("Tidak bisa menghubungi server") sesudah akun pengguna baru + server dinyalakan ulang | Pengisi karyawan dari akun (proses awal) memberi kode "jumlah karyawan + 1" di luar deret resmi → deret tertinggal → bentrok indeks unik | D · `hr_service.next_employee_code` (lewati kode terpakai), `bootstrap.py` (pakai deret resmi) · `test_KSDM01_finance_sdm.py`, `test_latih_hr_jabatan.py` |
| C-05 | H02 | Masukan gaji "8.000.000,00" tersimpan **Rp 800.000.000** | Isian teks biasa | D · `PayComponentsView.jsx` (MoneyInput, opsi `allowNegative`) · `pyt1KomponenMasukan.test.js` |
| C-06 | H04 | Bayar gaji: tanggal bawaan hari ini walau sebelum tanggal jurnal → ditolak server | Tanpa cek di layar | D · `PayrollPayPanel.jsx` (tombol mati + alasan) · `pyt4BayarGaji.test.js` |
| C-07 | H04 | Slip gaji PDF menulis "Periode: 2026-10" | Kode masa tidak diformat | D · `hr_payroll_pdf.py` ("Oktober 2026") · `test_KSDM01_slip_masa.py` |
| C-08 | H01 | Layar Karyawan memanggil `/users` (403 untuk Finance) di setiap muat | Tanpa cek izin | D · `EmployeesView.jsx` · `ksdm01KaryawanFinance.test.js` |
| C-09 | A1 | Kasir: sesudah Manajer menyetujui izin kredit, tombol tetap "Kredit Tertahan" | Cek kredit tidak dimuat ulang | D · `CheckoutDrawer.jsx`, `CreditGateBox.jsx`, `CheckoutStep3.jsx`, `CreditOverrideRequest.jsx` ([Periksa ulang kredit]) · `a1AlurPesanan.test.js` |
| C-10 | A1 | Meja Admin Sales: sesudah [Periksa & lepas], Pelacak SO & Keep & Pending basi | Kartu tidak dimuat ulang | D · `SalesAdminDesk.jsx`, `SoTrackerCard.jsx`, `KeepPendingPanel.jsx` · `a1AlurPesanan.test.js` |
| C-11 | A1 | Barang Keluar: jawaban cari roll yang terlambat mengisi roll lama lagi → [Kirim Pengambilan] bisa ditekan dua kali | Tanpa penjaga balapan permintaan | D · `OutboundScanInterface.jsx` · `a1AlurPesanan.test.js` |
| C-12 | A1 | Gudang melihat isian & tombol [Override] pemeriksaan muat → 403 | Tombol tidak dijaga `wms.approve` | D · `LoadingCheckPanel.jsx` · `latihA1Gudang.test.js` |
| C-13 | A1 | Rincian pesanan: "Belum ada pengiriman tercatat" selama surat jalan masih dimuat | Tanpa status memuat | D · `OrderDetailPanel.jsx` ("Memuat pengiriman…") |
| C-14 | A2 | PR → PO: rencana roll hilang (tugas gudang tanpa "rencana 75 roll", tombol "Buat 75 roll" tidak ada) | Rencana tidak ikut disalin ke PO | D · `pr_sourcing_service.py` · `test_A2_pr_rencana_roll.py` |
| C-15 | A2 | Setiap tagihan pemasok & PO manual tercatat "dibuat Admin" | Nama pembuat dari isian layar (bawaan skema "Admin") | D · `vendor_bills.py`, `purchase_orders.py` (akun yang masuk); Riwayat tagihan berbahasa Indonesia |
| C-16 | A2 | Pembuat PO melihat "🔒 —" di antrean persetujuan; status mentah (Converted, Assigned, scheduled_payment, vendor_bill) di Jejak Dokumen | Label | D · `PurchaseApprovalView.jsx`, `docStatus.js`, `DocRefsPanel.jsx` · `a2PengadaanSampaiBayar.test.js` |
| C-17 | A2 | Keterangan jurnal "Goods Receipt …" dan "Vendor Bill …" | Bahasa campuran | D · `gl_service.py` ("Penerimaan barang …", "Tagihan pemasok …"); jurnal lama tidak diubah |
| C-18 | A2 | MD Quality membuka layar SPK penerimaan → 403 tanda tangan elektronik | Izin `esign.view` tidak ada | D · `permissions_config.py` (`A2_DEFAULT_PAIRS`) · `test_PRT9_izin_bawaan.py` |
| C-19 | A3 | **Kontrabon memotong nota debit sebesar DPP saja** (Rp 1.160.000 bukan Rp 1.287.600) → PPN barang yang sudah dikembalikan tetap dibayar ke pemasok, akun hutang tersisa debit | Memakai `total_amount` (DPP), bukan `grand_total` | D · `contra_bon_service.py` · `test_A3_nota_debit_kontrabon.py` |
| C-20 | A3 | [Maks] / [Pakai Saldo] membulatkan ke rupiah → saldo kredit berakhir ,50 ditolak | Pembulatan di layar | D · `StoreCreditModals.jsx` · `a3PakaiSaldoSen.test.js` |
| C-21 | A3 | Tukar barang per roll: panel "Pesanan pengganti" tidak tampil → SO pengganti tidak bisa dibuat | Syarat tampil hanya untuk retur per baris | D · `ReturnReplacementPanel.jsx` · `a3TukarPerRoll.test.js` |
| C-22 | F07 | Keterangan jurnal LPJ "Pertanggungjawaban petty cash …" | Bahasa campuran | D · `gl_service.py` ("Pertanggungjawaban kas kecil …") |
| C-23 | F18 | Peringatan tutup buku "Penggajian periode ini sudah diposting: Penggajian belum diposting: …" (bertentangan) | Nama butir (pernyataan) digabung dengan pesan masalahnya | D · `ClosingChecklistPanel.jsx` (rincian masalah saja) · `pk43AlurLayar.test.js` |
| C-24 | F16 | Rincian jurnal non-kas (mis. Pendapatan Kirim, nota kredit saldo) menampilkan [Bukti Kas Keluar] & [Bukti Kas Masuk] | Arah kas kosong dianggap "keduanya" | D · `JournalDetailModal.jsx` (hanya jurnal dengan akun 1-11xx) · `latihBuktiKasTombol.test.js` |
| C-25 | F05 | Kartu "Rencana aktif" ikut tersaring kotak cari (nomor nota → 0) sedangkan kartu denda tidak | Kartu rencana dihitung dari daftar tersaring | D · `PaymentPlansView.jsx` (kartu = seluruh PT) · `latihRencanaKpi.test.js` |
| C-26 | F12 | Nominal kartu kontrabon terbelah ("Rp 1.287.60" + "0"); penerimaan barang "tugas 945058 · completed" | `break-words`; id & status mentah | D · `ContraBonParts.jsx` · `latihKontrabonTampil.test.js` |
| C-27 | F04 | Teks lama: kelebihan bayar ≤ Rp 5.000 "masuk toleransi, titipan tidak terbentuk". Uji klaim V9 membuktikan kelebihan kecil tetap diputus otomatis sebagai pembulatan TETAPI tetap masuk titipan (2-1400) | Teks salah | D · teks F04 dikoreksi (V9); aturan nominal transfer latihan (kelebihan ≥ Rp 10.000) dipertahankan agar contoh titipan jelas |
| C-28 | — | Label Kartu Peserta berbeda antara manual dan cetakan skrip data latihan | Dua sumber | D · satu daftar (`bangun.py` = `seed_pelatihan_keuangan_kn.py`), dicek saat membangun |
| C-29 | A3 | QC membuka SPK inspeksi retur → 403 tanda tangan elektronik (putaran akhir) | Izin `esign.view` tidak ada untuk QC | D · `permissions_config.py` (`A2_DEFAULT_PAIRS` + qc) · `test_PRT9_izin_bawaan.py`; diulang di layar (peserta 45) tanpa 403 |
| C-30 | A3 | Sales membuka panel karantina retur → 403 daftar supplier di setiap muat | Panggilan `/suppliers` tanpa cek izin | D · `ReturnQuarantinePanel.jsx` (hanya bila `supplier.view`) · `latihA3Karantina.test.js` |
| C-31 | — | Menyiapkan peserta baru sesudah ada aktivitas kelas gagal: SO ditolak "Qty roll … melebihi panjang bebas" | Skrip data memilih roll yang sebagian panjangnya sudah dipesan | D · `seed_demo_transaksi_kn.py` (roll dengan pesanan sebagian dilewati); peserta 45 tersiapkan lengkap |
| C-32 | — | Gate: layar Karyawan memutuskan dari nama peran (`admin`) dan memanggil `/users` untuk Finance | Perubahan K-SDM-01 | D · `EmployeesView.jsx` (`can(perms,'user','view')`), `audit_sales_roles_ux.py` (pagar dicatat) · `verify_role_gate_ui` 0 pelanggaran |

## 2d. Bagian 5 — situasi khusus & amandemen, dan bukti setiap klaim teks (17 Nov malam)

Masukan pemilik: "cek juga amandemen dll … end to end flownya dengan berbagai macam situasi … pastikan semua yang anda tulis
di skenario training, anda harus coba juga lulus sebagai user". Empat situasi baru dijalankan di layar dengan akun peran yang
benar (materi S1–S4, Bagian 5), dan setiap klaim di teks materi dicari buktinya (V9).

| Materi | Isi yang diuji | Hasil |
|---|---|---|
| S1 Amandemen & koreksi penjualan | amandemen SO belum terbit (hitung ulang, persetujuan Manajer, ditolak), hapus baris lewat Override, SO ber-uang muka terkunci, nota kredit (turun harga sesudah terkirim + faktur) & nota debit (naik harga) → pelunasan, Jejak Dokumen & umur piutang | 20/20 |
| S2 Amandemen & situasi khusus pengadaan | amandemen PO (versi, persetujuan ulang, batal), terima sebagian → tagih sebagian → tutup sisa (GR/IR 0), tagihan selisih harga (persetujuan orang lain), lebih tagih ditahan & dikoreksi | 31/31 |
| S3 Situasi khusus pesanan sampai uang masuk | kirim bertahap 2 SJ, uang muka 50%, batal SO ber-uang muka → titipan → pengembalian dana, satu transfer untuk beberapa SO, potongan biaya bank di bawah & di atas toleransi | 34/34 |
| S4 Koreksi & pembatalan | batal bayar tagihan → bayar ulang, batal kwitansi, anulir gaji yang sudah diposting → hitung ulang, balik jurnal + reklasifikasi akun sementara, kas salah kategori yang sudah dicocokkan | 41/41 |
| V9 Bukti setiap klaim teks | 433 klaim (konsep, cek buku, kesalahan umum, titik kontrol, catatan pelatih) F/K/H/A: 346 terbukti uji lama, 47 dibuktikan baru di layar (61/61), 20 teks dikoreksi, 1 bug, 16 menunggu keputusan pemilik, 3 belum (perilaku kelas / memengaruhi semua pengguna) — `src/variasi_klaim_materi.json` | 61/61 |

| # | Materi | Temuan | Status |
|---|---|---|---|
| D-01 | S1 | Layar amandemen menulis kode mentah ("manager", "MANAGER", "debit_note") | D · `amendmentApi.js` (approverLabel, resultDocLabel), `AmendmentImpactCard/ProposeModal/DetailPanel.jsx` · `latihS1Amandemen.test.js` |
| D-02 | S1 | Rincian pesanan: "Belum ada Faktur Pajak" + tombol terbit selama daftar masih dimuat | D · `OrderDetailPanel.jsx` |
| D-03 | S2 | Amandemen PO sesudah penerimaan sebagian: PO kembali "Menunggu barang", "Belum Ditagih" basi, tugas karantina ditimpa, **lahir tugas gudang sebesar qty penuh** | D · `routers/purchase_orders.py` · `test_latih_s2_amandemen_po.py` |
| D-04 | S2 | Baris PO yang sudah diterima terkunci total → aturan V3-PO-02 (turunkan qty tepat ke qty diterima) buntu di layar | D · `POAmendModal.jsx` ([Tutup sisa], [Urungkan]) |
| D-05 | S2 | Tagihan lebih tagih ditolak tetapi meninggalkan draf tersembunyi yang menahan nomor faktur → tagihan koreksi ditolak 409; pesan/riwayat keliru; layar mengabaikan ambang Rp 50.000 | D · `vendor_bills.py`, `vendor_bill_service.py`, `VendorBillCreateModal.jsx` · `latihS2TagihanAmbang.test.js` |
| D-06 | S2 | Pembuat tagihan melihat [Setujui] → 403 (kontrol dua orang); draf batal tampil "Sisa" merah; amandemen tercatat "oleh Admin" | D · `VendorBillsView.jsx`, `po_amendment_service.py` |
| D-07 | S2 | Penerimaan berat: pecah baris roll tidak menghitung ulang berat → "Aktual lebih besar 80%", penerimaan terblokir | D · `GRCatchWeightModal.jsx` |
| D-08 | S3 | **Batal SO ber-uang muka: uang muka tertinggal di pesanan mati** (2-1400 tetap memegangnya, tidak bisa dikembalikan/dipakai) | D · `ar_receipt_service.py`, `ar_allocation_service.py`, `sales_orders_extra.py`, `inventory_service.py` (juga pesanan kedaluwarsa), `CancelOrderDialog.jsx` · `test_latih_s3_batal_uang_muka.py`, `latihS3BatalUangMuka.test.js` |
| D-09 | S3 | Bayar tepat uang muka dinilai "Kurang bayar" dan wajib diputus; form Terima pembayaran terisi seluruh sisa SO, bukan uang muka yang ditagih | D · `payment_variance_service.py`, `ar_receipts.py`, `ReceivePaymentModal.jsx` · `latihS3UangMukaForm.test.js` |
| D-10 | S3 | Penyelesaian Kasus yang memindahkan uang tanpa isian rekening → ditolak bila PT punya >1 rekening (pasti terjadi di kelas karena rekening latihan K04) | D · `finance_case_playbooks.py`, `CasePlaybookWizard.jsx` · `latihS3KasusRekening.test.js` |
| D-11 | S4 | [Anulir Jurnal] tanpa alasan (melanggar N5) | D · `JournalDetailModal.jsx`, `useJournalActions.js`, `routers/gl.py`, `gl_service.py` · `test_latih_s4_koreksi.py`, `latihS4Koreksi.test.js` |
| D-12 | S4 | Reklasifikasi akun sementara selalu bertanggal hari ini → saldo Oktober yang dibersihkan awal November tetap menahan tutup buku Oktober | D · `SuspensePanel.jsx`, `schemas_finance.py`, `gl.py`, `gl_service.py` |
| D-13 | S4 | Pesan & riwayat batal bayar mentah ("payment_void", "via transfer (kas_kecil)"); kwitansi dianulir masih "Kurang Bayar · perlu diputus"; kas bayar gaji "Anulir lewat dokumen lain" | D · `VendorBillsView.jsx`, `VendorBillPayments.jsx`, `ap_payment_service.py`, `ARReceiptsHistory.jsx`, `CashManagementView.jsx` |
| D-14 | V9 | Finance melihat ikon pengingat & janji bayar di Penagihan → 403 | D · `CollectionWorklist.jsx` · `latihV9TindakLanjutIzin.test.js` |
| D-15 | V9 | 20 klaim teks keliru (mis. contoh jurnal F04/F18 tidak seimbang, kelebihan ≤ Rp 5.000 tetap jadi titipan, toleransi 3-way match ±5%/Rp 50.000, transfer kas lewat 1-1150, Buka Periode vs Buka Kembali) | D · teks 11 materi dikoreksi |
| D-16 | — | Insiden uji: skrip `verify_concurrency.py` (dikira statis) memulihkan 21 koleksi Mongo bersama ±25 detik → data pengembangan tidak konsisten | C · verifikasi akhir dimulai dari data yang dipulihkan bersih; jangan jalankan skrip `guardrails/verify_concurrency.py` saat ada uji lain. Pelajaran kedua: memulihkan potret dengan `mongorestore --drop` hanya mengganti koleksi yang ADA di arsip — koleksi baru dari uji sebelumnya (mis. mutasi bank) tertinggal dan bentrok dengan nomor peserta yang sama (S4 peserta 76/77 → impor mutasi "sudah pernah masuk"). Untuk VPS & uji ulang: kosongkan basis data dulu, atau pakai nomor peserta yang belum pernah dipakai |

## 2e. Hutang & piutang per pihak (S5) dan Finance setara Manajer (K-FIN-01) — 17/18 Nov malam

Masukan pemilik: "finance juga memiliki akses yang sama dengan manager dan jangan dipisah" · "ui interface di finance yang
viewnya per orang atau suplier di klik muncul semua hutang atau piutangnya dan bisa aksi bayar juga … aksinya lengkap mulai
dari bayar dll, tapi cek dulu sudah ada atau belum".

**Yang sudah ada dan dipakai ulang:** Piutang per Pelanggan (`ARAgingView` + rincian `ARAgingDetail`: per SO/SJ + umur,
Jadwal Tagihan, Nota Denda, [Terima pembayaran] untuk beberapa SO + titipan), rekening koran pelanggan (layar + PDF), tindak
lanjut penagihan, kartu pemasok (`Supplier360Panel`), form bayar tagihan PK-05, kontrabon. **Yang belum ada:** daftar hutang
per pemasok dan bayar beberapa tagihan sekaligus — dibangun.

| Materi | Isi yang diuji | Hasil |
|---|---|---|
| S5 Hutang & piutang per pihak | Hutang per Pemasok (umur, potongan, cari/saring/urut, CSV) → rincian → bayar 2 tagihan sekaligus (1 konfirmasi, 2 kas + 2 jurnal, kunci idempoten per tagihan, tagihan berkontrabon ditolak) → Piutang per Pelanggan → rekening koran + PDF → janji bayar → terima pembayaran 2 SO | 20/20 (peserta 91, 92) |
| V10 Finance setara Manajer | Meja Manajer, Pusat Persetujuan, izin kredit, kontrabon (diajukan Manajer, disetujui Finance), Jurnal Baru → Balik, Tutup Buku, sahkan masukan & proses gaji, Pengaturan Keuangan & Pajak | 8/8 |

| # | Materi | Temuan | Status |
|---|---|---|---|
| D-17 | S5 | Tidak ada daftar hutang per pemasok dan bayar banyak tagihan | D · `services/ap_party_service.py`, `GET /api/vendor-bills/payables/by-supplier[/{id}]`, `features/finance/ap/` (`APBySupplierView`, `APSupplierDetail`, `PayManyBillsModal`), tab Keuangan › Hutang › Hutang per Pemasok · `test_S5_hutang_per_pemasok.py`, `latihS5PerPihak.test.js` |
| D-18 | S5 | Rincian Piutang per Pelanggan belum memuat rekening koran dan janji bayar | D · `ARAgingDetail.jsx` ([Rekening koran], [Janji bayar] per SO menurut izin) |
| D-19 | S5 | Kartu pemasok: kontrabon "Dijadwalkan bayar" tanpa tombol Bayar (status `scheduled` vs `scheduled_payment`) | D · `Supplier360Panel.jsx`, `ap_payment_service.cb_payable_statuses()` |
| D-20 | S5 | Rekening koran › Cetak PDF: nama pelanggan bertanda "·" → berkas tersimpan "download" tanpa .pdf | D · `CustomerStatementTab.jsx` (`namaBerkas`) |
| D-21 | K-FIN-01 | Finance dipisah dari Manajer (izin, lintas PT, Meja Saya, Aturan Persetujuan, gerbang nama peran) | D · `permissions_config.py` (blok `KFIN01_*`), `role_registry.py` (`SETARA_PERAN`, lintas PT), `approval_policy_service.py`, `bootstrap.migrate_kfin01_approval_policies`, `grade_service.py`, `routers/home.py`, `roles.js`, `AmendmentDetailPanel.jsx` · `test_KFIN01_finance_setara_manajer.py`, `kfin01FinanceSetaraManajer.test.js`, V10 |
| D-22 | S3 | **Pukul 00.00–07.00 WIB, membayar tepat uang muka dinilai "Kurang bayar"**: hari jatuh tempo dihitung dengan tanggal UTC, jadwal tagihan dengan tanggal buku WIB (ditemukan uji S3-L3 pukul 00.37 WIB) | D · `payment_variance_service._hari_buku` (tanggal buku WIB; jatuh tempo termin juga dari tanggal buku pesanan) · `test_latih_s3_batal_uang_muka.py` |
| D-23 | materi | 11 skrip & 20 teks materi menyatakan "Finance tidak melihat tombol …" | D · skrip mencatat tombol yang kini tampil (`r.kfin`, catatan "K-FIN-01: …"), teks F01, F06, F07, F12, F15, F16, H01–H04, K01, K03, K05–K07, K09, A3, A4, S1, S2, S4 disesuaikan; kurikulum: peran Finance, S5 di Bagian 5 |
| D-24 | F10 | **Pukul 00.00–07.00 WIB, rekonsiliasi bank menilai transaksi kas hari ini "Tanggal beda 1 hari"** (cap waktu UTC dipotong 10 huruf) → skor turun 60 → 55 | D · `bank_recon_service._d` (tanggal buku WIB) · `test_rekon_tanggal_wib.py` |
| C-33 | — | **Celah verifikasi: jam 00.00–07.00 WIB.** Putaran uji sebelumnya selalu siang/sore WIB (tanggal UTC = tanggal WIB), jadi bug yang bergantung jam tidak tertangkap; putaran 18 Nov 00.40 WIB menemukan D-22, D-24, dan skrip F05/F17/F01 yang menghitung "hari ini" dengan UTC (diperbaiki). Pola serupa (`now_iso()[:10]` / `datetime.now(timezone.utc).date()` sebagai "hari ini") masih ada di 37 tempat: services/wa_alert_service.py (2) services/rnd_kpi_export.py (2) services/return_service.py (2) services/payment_variance_service.py (2) services/payment_plan_service.py (2) services/finance_case_scan.py (2) services/work_desk_service.py (1) services/special_order_phase2.py (1) services/so_override_service.py (1) services/scheduler_service.py (1) services/rfid_service.py (1) services/purchase_requisition_service.py (1) services/pr_sourcing_service.py (1) services/pos_recommendation_service.py (1) services/notification_service.py (1) services/marketing_cost_service.py (1) services/internal_request_service.py (1) services/interco_price_service.py (1) services/inspection_service.py (1) services/gl_service.py (1) services/financial_statement_service.py (1) services/escalation_service.py (1) services/digest_service.py (1) services/design_request_service.py (1) services/customer_feedback_service.py (1) services/contract_service.py (1) services/contra_bon_reminder.py (1) services/color_service.py (1) services/bank_recon_service.py (1) routers/purchase_requisitions.py (1) routers/master_governance.py (1). Perlu ditinjau satu per satu dan satu putaran uji khusus pukul 00.00–07.00 WIB sesudah pelatihan. | C |
| D-25 | ulasan S5 | **Uang muka ke pemasok dibaca lintas PT**: dobel di mode Semua PT, tampil di baris PT lain, dan form kontrabon PT lain menawarkan (serta menjurnal) uang muka milik PT Sukacita; kartu pemasok ikut bocor | D · `ap_party_service._credits`, `contra_bon_service.available_credits` · `test_review_s5_uang_muka_per_pt.py` |
| D-26 | ulasan K-FIN-01 | **Aturan Persetujuan "Manajer saja" yang disimpan Admin diam-diam ditambah Finance** (bertentangan dengan janji "ubahan Admin bertahan"); migrasi K-FIN-01 tidak memuat peran kustom ber-dasar Finance | D · `approval_policy_service._row(setara=False)`, `bootstrap.migrate_kfin01_approval_policies` · `test_review_kfin01_aturan_admin.py` |
| D-27 | ulasan S5 | Nomor/status kontrabon bocor ke pemegang `vendor_bill.view` tanpa `contra_bon.view`; "Pilih semua" ikut mencentang tagihan yang tersembunyi saringan (bisa membayar tagihan yang tidak tampil); pesan "tidak ada yang terbayar" di bilah hijau | D · `ap_party_service.supplier_detail`, `APSupplierDetail.jsx`, `PayManyBillsModal.jsx` · `test_review_s5_izin_kontrabon.py`, `reviewS5PerPihak.test.js` |
| D-28 | zona waktu | **23 tempat "hari ini" memakai jam UTC** (berlaku 00.00–07.00 WIB): jatuh tempo rencana bayar/cicilan/termin, baris terlambat, neraca tanpa tanggal, Menara Keuangan MTD/YTD, omzet PPh final per masa, tanggal cetak Faktur Pajak, harga PT/pelanggan & aturan harga khusus (bergeser 7 jam), "berlaku sejak" pengaturan terjadwal (7 jam terlambat), masa kontrak, siklus kontrabon, jatuh tempo PO, jadwal bayar antar-PT, umur titipan bank, penanda retur, biaya kampanye, tanggal bawaan Neraca Saldo & Refund antar-PT, tanggal tagihan di Hutang per Pemasok | D · 26 berkas (commit "Tanggal buku WIB") · `test_tz_dini_hari_wib.py` (20, semua merah di kode lama), `tzTanggalBawaan.test.js` |
| D-29 | S4 | Rincian jurnal manual yang sudah dibalik masih menampilkan [Anulir Jurnal] (server menolak sesudah diklik) | D · `JournalDetailModal.jsx` · `latihS4AnulirSudahDibalik.test.js` |
| C-34 | — | Masih UTC tetapi hanya tampilan/notifikasi (belum diubah): kunci dedupe notifikasi harian, penghitung eskalasi/WA/RFID/ringkasan, lencana hutang jatuh tempo di Meja, saringan PO terlambat, tanggal QC, cetakan gudang lama, nama berkas ekspor. Daftar rinci di laporan agen zona waktu | C |

## 2f. Perburuan cacat 18 Nov dini hari (00.40–07.00 WIB)

Permintaan pemilik: "lakukan apa yang anda bisa lakukan cari kesalahan sebisa mungkin dari semua konteks ini flow dan lain lain".
Pengakuan: pengecekan sebelumnya membuktikan bahwa langkah yang ditulis berjalan (459/459), tetapi tidak MEMBURU kesalahan —
jam 00.00–07.00 WIB, peran kustom, mode lintas PT, klik ganda, dan dua pengguna bersamaan belum pernah diuji, dan materi
ditulis berorientasi nama peran ("Finance tidak bisa …") padahal wewenang = izin (02_STANDAR §3). Malam ini enam alur
perburuan berjalan paralel: zona waktu, ulasan kode malam ini, peran kustom, uji jalan adversarial, kegagalan jest lama,
merah lama di gate.

### Peran kustom × alur keuangan (5 peran UJI-KUSTOM, 28 pintu API, 7 skenario layar)

Server memutus menurut izin di semua 28 pintu yang diuji (tidak ada yang meloloskan tanpa izin). Cacatnya di layar dan
sisa gerbang nama peran:

| # | Temuan | Status |
|---|---|---|
| A-03 | [Setujui kontrabon] tampil bagi pemegang `contra_bon.approve` yang tidak tercantum di Aturan Persetujuan → 403 | D · `ContraBonDetailPanel.jsx` (can-decide) · `agAKontrabonSetujuKustom.test.js` |
| A-05/06/07 | Pemegang lihat-saja melihat [Tutup Buku], tombol tulis Rekonsiliasi, [Kasus baru]/[Pindai] → 403; Kasus kosong bila `/customers` 403 | D · `ClosingView`, `BankReconciliationView`, `ReconLinesTable`, `ReconHoldingPanel`, `FinanceCasesView` · `agAKeuanganLihatSaja.test.js` |
| A-08 | [Pratinjau]/[Unduh PDF]/[Kirim WA] tampil tanpa izin dokumen → "Gagal mengunduh PDF"; Dokumen Terkait bilah merah 403 (juga md, sample_admin, md_quality, qc bawaan) | D · `DocumentActionsBar`, `DocRefsPanel` · `agADokumenIzin.test.js` |
| A-11 | Selisih bayar menulis id peran mentah ("WAJIB MANAGER"); hapus sisa/refund ditawarkan ke peran yang ditolak Aturan Persetujuan | D · `PaymentVarianceDialog` · `agASelisihBayarWewenang.test.js` |
| A-01/02 | **Bebaskan/ubah denda dan selesaikan kasus di atas ambang masih diputus NAMA PERAN** (`payment.penalty_waive_approver_role`, `role_in`): dua peran berizin identik berperilaku beda; pesannya memuat id "manager" | Pesan diperbaiki (label peran); gerbang TERBUKA — usul jenis Aturan Persetujuan baru (`penalty_waive`, `finance_case_above_cap`) + migrasi pengaturan; tidak dipasang malam ini (berisiko menjelang kelas, bukan alur krusial) · xfail ketat KU-01 |
| A-04 | Pesan "diputus oleh …" mencantumkan peran yang tidak memegang izin setujui | Terbuka · usul saring `who` dengan indeks izin peran (`approval_policy_service.py:448`) |
| A-09 | Peran dengan izin "terima pembayaran" saja tidak punya layar untuk menerima uang (Saldo & Umur butuh `accounting.view`/`penalty.issue`; Penagihan & Penerimaan butuh modul Pesanan) | Terbuka · keputusan pemilik |
| A-10 | Tab tampil per MODUL padahal endpoint butuh sumber daya tertentu (Beranda Keuangan, Rencana & Denda, Faktur Keluaran/Masukan) → 403 | Terbuka · usul `VIEW_RESOURCE_OVERRIDES` per tab |
| A-12 | K-FIN-01: peran kustom ber-dasar Finance otomatis lintas PT dan lolos gerbang "manager" | Terbuka · keputusan pemilik (K-53) |
| A-13…16 | PO tidak termuat di Tagihan tanpa `purchase_order.view`; approve kontrabon memetakan semua galat ke 403; pesan 403 Saldo & Umur menyebut modul yang sudah dipegang; "Rincian & bayar" bagi lihat-saja | Terbuka (rendah) |

Data uji: pengguna `uji.kustom1–5@` dinonaktifkan; peran UJI-KUSTOM dibiarkan (dipakai jejak audit) — hapus R4 "Manajer
Tanpa Setuju" bila mengganggu pesan Aturan Persetujuan.

### Sembilan kegagalan jest "lama" (dulu dilaporkan sebagai "himpunan lama yang sama")

Kelima suite tidak bisa dimuat sampai 16 Nov (`@radix-ui/primitive/is-development` hilang), sehingga perubahan KP-T4, PR-T5,
CR-T1, MN-T3 (14–15 Nov) tidak pernah diuji ulang. Tujuh uji usang (diperbarui mengikuti keputusan unit itu, plus kasus baru);
dua menyembunyikan bug nyata:

| # | Temuan | Status |
|---|---|---|
| E-T1 | **Desainer PDF digerbang nama peran "admin"**: Manajer/Finance pemegang `pdf_template.manage` tidak bisa membuka desainer, padahal server menerima simpanannya dan "Lengkapi PT" mengarahkan ke sana (alur buntu); lihat-saja melihat tombol simpan → 403 | D · `DocTemplatesView.jsx` (gerbang izin) · `phase3P8Activation` D-01 (merah di kode lama). Akibat: Manajer & Finance kini melihat Desainer PDF — bila harus khusus Admin, cabut izinnya di Peran & Hak Akses (K-54) |
| E-T2 | Penolakan aksi selain lihat berbunyi "tidak punya akses ke modul ini" padahal pengguna sedang di modul itu | D · `utils/apiError.js` · `fe07ReturnErrors` (merah di kode lama) |
| E-T3 | Awalan galat Retur berbahasa Inggris ("Gagal reject/approve/settle/submit") | D · `SalesReturns.jsx`. Sisa serupa di `CycleCount.jsx`, `PurchaseApprovalView.jsx`, `useAppActions.js` — terbuka |
| E-T5 | `useCanDecideMap` memakai jawaban lama sesaat sesudah status dokumen berubah (tombol jenjang 2 tampil sesaat; server tetap menolak) | Terbuka (rendah) |

Jest penuh sesudahnya: **1.778/1.778 lulus, 0 gagal**.

## 3. Perlu keputusan pemilik

| # | Pertanyaan |
|---|---|
| K-01 | Belum ada layar/endpoint **ganti sandi sendiri**; hanya Admin yang bisa mereset. Perlu ditambahkan? |
| K-02 | Pendapatan 4-9xxx (denda, bunga, klaim) di Laba-Rugi: tetap di Pendapatan atau dipindah ke "Pendapatan lain-lain" di bawah laba kotor? |
| K-03 | Faktur pajak per pesanan bisa terbit tanpa NPWP/NIK pembeli, tetapi draf per surat jalan ditolak. Aturannya disamakan? |
| K-04 | NSFP tanpa pemeriksaan format (label 16 digit; Coretax 17 digit) dan belum ada ekspor e-Faktur. |
| K-05 | Kontrabon bisa dibayar di server sejak *Disetujui*, tetapi layar baru menampilkan tombol bayar sesudah *Dijadwalkan*. Dipertahankan? |
| K-06 | Susulan PPh 21 bisa bersen (Rp 40.864,50). Dibulatkan ke rupiah? |
| K-07 | Total SO bisa berakhiran ,50 sedangkan transfer selalu rupiah bulat → rekonsiliasi bank selisih Rp 0,50. Total SO dibulatkan ke rupiah? |
| K-08 | Lebih bayar hanya bisa dicatat di alokasi *Tertua dulu* (di *Atur sendiri* nominal = jumlah alokasi). Bila pelanggan masih punya tagihan lain, kelebihan otomatis terserap ke tagihan itu dan tidak bisa disimpan sebagai titipan. Perlu pilihan "sisanya jadi titipan" di Atur sendiri? |
| K-09 | Plafon pelanggan baru tampil "tanpa batas" selama usulan plafon belum disetujui. Disengaja? |
| K-10 | Finance boleh menyusun rencana cicilan (kini hanya bisa mengubah) dan mencatat janji bayar di Kredit & Plafon (kini butuh izin ubah pesanan)? |
| K-11 | Alasan bawaan kurang bayar "Dipotong biaya bank" walau kekurangannya besar (mis. 60%). Ganti bawaan? |
| K-12 | Kas masuk kategori "Lain-lain" masuk Akun Sementara (Suspense) — disengaja (harus direklasifikasi) atau perlu akun pendapatan lain-lain? |
| K-13 | Persetujuan PD tahap "Pimpinan" & "Bagian Keuangan" hanya bisa disetujui Admin, bukan Finance. Dipertahankan? |
| K-14 | Pengaturan `pembayaran.sales_terima_tunai = titipan` dinyalakan prep untuk PT Sukacita (F08). Di data nyata ini keputusan pemilik. |
| K-15 | Kas keluar kategori "Setoran Modal" dibukukan ke 6-4000 Beban (penarikan modal/prive seharusnya ke ekuitas); kas keluar "Pembelian" mendebit 1-1300 Persediaan; kas masuk Operasional/Pembelian/Gaji/Lain-lain ke Suspense. Petakan ulang kategori? |
| K-16 | Tanggal maju: kwitansi, pembayaran tagihan, dan jadwal bayar kontrabon boleh bertanggal masa depan/lampau tanpa peringatan. Dibatasi? |
| K-17 | Kas kecil boleh minus; LPJ tanpa foto nota (`finance.lpj_wajib_lampiran` mati) dan uraian kosong diterima. Diperketat? |
| K-18 | Tidak ada batas lebih bayar (mis. salah ketik nol) selain dialog selisih. Perlu batas atau konfirmasi kedua? |
| K-19 | [Buka Kembali] periode tanpa alasan; alasan satu huruf diterima. Wajib alasan bermakna? |
| K-20 | PPh 21 susulan memakai tarif 4,5%; menurut TER A (PP 58/2023) 6% (Rp 36.945 vs Rp 260.577 pada contoh) — butir terbuka K-42/PY-03. |
| K-21 | Cetakan Faktur Pajak bukan format DJP/Coretax; ekspor e-Faktur belum ada; NSFP menerima "ABC-DEF"/"12345". Beri label "salinan internal" + cek 16–17 digit? |
| K-22 | Nomor Tagihan Supplier "VB-00030" dan Permintaan Pembelian "PR-00003" tanpa awalan PT (deret bersama), berbeda dengan KSC/PO- dan KSC/CB-. Diseragamkan per PT? |
| K-23 | Naskah memakai `{{rekening_bank}}` tetapi PT Sukacita belum punya rekening bawaan transfer → kosong. Tetapkan rekening bawaan per PT. |
| K-24 | Tombol cetak lama "Faktur (PPN)"/"Surat Jalan" + editor "Kop & tata letak dasar" hanya memengaruhi jalur lama; tab Desainer PDF hanya Admin walau Manajer punya izin. Pensiunkan jalur lama & buka Desainer untuk Manajer? |
| K-25 | Nota denda dan rekap setoran PPh/BPJS belum punya cetakan. Perlu? |
| K-SDM-01 | **Digantikan K-FIN-01 (17 Nov 2026 malam) untuk pembagian Finance–Manajer.** **Dicatat (keputusan pemilik 17 Nov 2026: "SDM/HR itu dipegang finance juga").** Finance menyiapkan data karyawan, kehadiran, aturan & masukan gaji, menghitung dan memposting proses gaji, membayar, dan menyetor. Manajer mengesahkan masukan, perubahan gaji, dan proses gaji, serta membatalkan (anulir) proses. Hapus karyawan, struktur organisasi, dan pengaturan SDM umum tetap Manajer/Admin. Mohon konfirmasi pembagian ini. |
| K-FIN-01 | **Dicatat (keputusan pemilik 17 Nov 2026 malam, kata-kata asli: "untuk sekarang finance juga memiliki akses yang sama dengan manager dan jangan dipisah").** Peran bawaan Finance memegang SEMUA izin bawaan Manajer (ditambah izinnya sendiri: Pemetaan Akun ubah, Harga Internal antar-PT), lintas PT seperti Manajer, Meja Saya = Meja Manajer, dan ikut tercantum di setiap baris Aturan Persetujuan yang menyebut Manajer (bawaan & tersimpan). Menggantikan pemisahan K-SDM-01: Finance kini juga mengesahkan & menganulir gaji, menghapus karyawan, mengatur struktur organisasi, menyetujui SO/PO/kontrabon/izin kredit, membuat jurnal manual, menutup buku. Kontrol dua orang per PENGGUNA (`kontrol.<aksi>.min_orang`) tidak berubah. Bukti: `backend/tests_mem/test_KFIN01_finance_setara_manajer.py`, `frontend/src/config/__tests__/kfin01FinanceSetaraManajer.test.js`, uji layar `uji/variasi/V10_finance_setara_manajer.js` (8/8). Risiko pemisahan tugas (untuk pemilik): satu akun Finance kini bisa menyiapkan SEKALIGUS mengesahkan proses gaji dan jurnal manual (kontrol dua orang `proses_gaji` & `jurnal_manual` bawaan 1 orang — dapat dinyalakan di Pengaturan › Persetujuan › Kontrol dua orang); masukan gaji tidak punya kontrol dua orang sama sekali; Finance kini lintas PT (bisa dimatikan per peran di Peran & Hak Akses). |
| K-51 | **Hutang & piutang per pihak (S5).** (1) Janji bayar memakai izin ubah pesanan (`order.update`) — terlalu luas; perlu izin penagihan sendiri? (2) Janji bayar dicatat per SO, bukan per pelanggan — perlu janji per pelanggan? (3) Bayar beberapa tagihan = N kas keluar, sedangkan bank menunjukkan satu mutasi (rekonsiliasi pakai cocok-pecah) — tetap begini atau satu kas dengan alokasi? (4) Rekening koran pemasok / rekap hutang PDF belum ada (baru CSV) — perlu? (5) Rencana cicilan tidak dibuat dari rincian piutang — perlu? (6) Pemasok yang hanya punya potongan tanpa tagihan terbuka tidak muncul di daftar. (7) Konfirmasi kwitansi membulatkan rupiah (lihat K-07). |
| K-52 | **K-FIN-01 untuk akun latihan.** Akun `finance.latihNN` kini lintas PT seperti Manajer (kotak PT bisa dibuka; data PT Kanda & Cipta terjangkau) dan memegang izin Manajer (setujui, tutup buku, jurnal manual, bagan akun). Selama kelas peserta diminta tetap di PT Sukacita dan tidak menyetujui/mengubah pengaturan bersama. Sesudah kelas: `--nonaktifkan`. Bila ingin akun latihan tetap terkunci 1 PT, perlu peran kustom "Finance latihan" (berbasis Finance, lintas PT dimatikan) — putuskan sebelum pelatihan berikutnya. |
| K-53 | **Akun Finance kini lintas PT (K-FIN-01) — `allowed_entity_ids` diabaikan untuk semua akun Finance**, termasuk akun latihan yang ditugaskan ke Sukacita saja (terbukti: finance.latih01 membaca dan bisa menulis di semua PT). Bila pembatasan PT harus tetap, Admin mematikan "lintas PT" untuk peran Finance di Peran & Hak Akses (berlaku untuk semua akun Finance) atau memakai peran kustom. Mohon keputusan. |
| K-54 | Sesudah gerbang nama peran Desainer PDF dicabut (E-T1), Manajer dan Finance (pemegang `pdf_template.manage`) membuka Desainer PDF. Bila desainer harus khusus Admin, cabut izin itu dari peran Manajer/Finance di Peran & Hak Akses (bukan memasang lagi gerbang nama peran). |
| K-26 | Akun "Selisih harga pembelian" dan "Selisih nilai retur beli" belum dipetakan: kliring GR/IR ditolak dan Kesiapan PT kurang "Pemetaan akun". Akun mana yang dipakai? |
| K-27 | Finance boleh **membaca** Aturan Keuangan & Pajak (izin `settings.view`)? Manajer tidak bisa mengubah "Kelompok umur piutang" (butuh `settings.manage`) — disengaja? |
| K-28 | Akun yang pernah dipakai di riwayat pemetaan tetap dihitung akun kontrol walau pemetaannya sudah dikembalikan. Disengaja? |
| K-29 | Data PT Sukacita belum lengkap: alamat terverifikasi, kop & logo, penanda tangan (juga kop slip gaji hanya nama PT). |
| K-30 | Finance punya izin kelola Cara Bayar (`cash.configure`) tetapi tidak punya menu ke Perusahaan (PT) › Master per PT. Buka menunya atau cabut izinnya? |
| K-31 | SDM: Finance kini bisa mengubah PTKP, TER, dan BPJS yang berlaku untuk semua PT. Dikunci ke Manajer/Admin? |
| K-32 | SDM: gaji awal karyawan baru berlaku tanpa persetujuan; risiko karyawan fiktif hanya bertumpu pada pengesahan proses gaji oleh Manajer. Wajib persetujuan? Finance juga bisa menyetujui lembur yang ia ajukan sendiri — diblokir? |
| K-33 | SDM: bila aturan dua orang penggajian dinyalakan, Finance yang mengajukan proses tidak bisa memposting/membayarnya. Disengaja? |
| K-34 | Pesanan sampai uang masuk: pendapatan & piutang diakui saat surat jalan terbit dan jatuh tempo dihitung dari tanggal surat jalan. Sesuai kebijakan? [Tandai Diterima (Selesai)] tanpa konfirmasi & bukti terima — perlu? |
| K-35 | Pengadaan: tagihan yang cocok bersih (3-way match) diposting pembuatnya tanpa orang kedua — disengaja? Batas persetujuan PR Rp 50 juta / PO Rp 100 juta benar? Dua tombol PR → PO ("Konversi ke PO", "Realisasi ke PO") — satu saja? MD Quality cukup memeriksa 1 dari 75 roll? |
| K-36 | Pembayaran tidak dicek ke saldo bank (BCA bisa minus). Blokir atau peringatan? |
| K-37 | Finance bisa membatalkan pembayaran tagihan pemasok (izin bayar = izin batal di server). Pembatalan perlu Manajer? |
| K-38 | Retur: refund langsung membukukan pembayaran bank saat Manajer menyimpan, tanpa langkah bayar Finance. Perlu langkah bayar Finance atau orang kedua? |
| K-39 | Retur: Finance tidak bisa membuka "Retur ke Supplier (Nota Debit)" (hanya melihatnya di kontrabon). Beri akses lihat? Nota debit hanya mengurangi tagihan lewat kontrabon — bila tagihan dibayar langsung (F11), nota debit tetap terbuka. |
| K-40 | Retur: barang yang dinilai QC "Rusak" masuk stok bernilai nol dan HPP tidak dibalik. Sesuai kebijakan? |
| K-41 | Nota debit menambah PPN Keluaran di buku tanpa dokumen pajak; faktur pengganti dibentuk dari angka SO asli → rekonsiliasi PPN selisih (contoh Rp 12.577). Perlu faktur pengganti/tambahan? (melengkapi TX-T2 H5 butir 4) |
| K-42 | Sesudah SO ber-uang muka, satu baris tidak bisa dihapus (Override terkunci, amandemen qty 0 ditolak) — hanya batal seluruh SO. Perlu jalur hapus baris? Turun harga SO ber-uang muka yang belum dikirim menjadi nota kredit tertunda tanpa jurnal — sesuai? |
| K-43 | ~~Finance tidak punya tab Koreksi & Amandemen~~ — terjawab K-FIN-01: Finance kini membuka tab yang sama dengan Manajer. |
| K-44 | Amandemen PO yang menaikkan harga di bawah Rp 100 juta langsung berlaku tanpa persetujuan (hanya dicek terhadap daftar harga pemasok). Perlu persetujuan? Tutup sisa PO ada dua jalan ("Tutup sisa" lewat persetujuan Admin vs [Tutup PO (Kurang)] langsung) — mana yang baku? |
| K-45 | PT Sukacita masih memakai penerimaan mode lama (barang kurang wajib eskalasi; sisa PO tanpa tugas). Pindah ke mode Kedatangan (GRN)? Draf tagihan tidak bisa diubah (batal lalu buat baru) — perlu tombol ubah? Penyetuju tagihan selisih harga praktis hanya Admin — siapa seharusnya? |
| K-46 | Uang muka pesanan yang dibatalkan kini menjadi titipan (tidak hangus). Ada aturan uang muka hangus/biaya batal? Batal SO ber-uang muka bisa tanpa Finance — dipertahankan? Pesanan ber-uang muka bisa kedaluwarsa (reservasi 3 hari) — dikecualikan? |
| K-47 | Potongan biaya transfer jatuh ke dua akun: ≤ toleransi otomatis ke 6-9100, > toleransi lewat Kasus ke 6-8000. Disatukan? Finance tidak bisa menyelesaikan kasus biaya bank kecil sendiri — dipertahankan? |
| K-48 | Faktur per pesanan untuk pengiriman bertahap terbit sebesar seluruh SO saat PPN Keluaran di buku baru sebagian. Pakai pemicu per surat jalan, atau tahan faktur sampai terkirim penuh? |
| K-49 | [Anulir Jurnal] manual menandai jurnal anulir tanpa jurnal pembalik — batasi ke jurnal hari itu/periode berjalan, atau cukup [Balik Jurnal]? Gaji yang sudah dibayar tidak bisa dibatalkan sama sekali (juga bila transfer ditolak bank) — perlu jalur batal bayar gaji / potong kelebihan lewat masukan minus? |
| K-50 | Bayar tagihan dari Kas Toko (rekening tunai) diterima dengan cara bayar "Transfer" — kunci cara bayar sesuai rekening? Alasan pembatalan kas & kwitansi hanya terbaca di Jejak Audit Admin — tampilkan ke Finance/Manajer? Masukan gaji untuk masa yang proses regulernya sudah diposting tidak pernah terpakai tanpa peringatan — tolak/peringatkan? |

## 4. Catatan untuk pelatih

- **Tutup buku (F18) memengaruhi semua pengguna** — diperagakan pelatih pada bulan kosong; jangan menutup November atau
  Oktober (jurnal gaji latihan bertanggal 31 Okt). Jangan menyetujui permintaan Buka Periode selama pelatihan (spanduk merah
  tampil untuk semua pengguna).
- **Penggajian (F15)**: penggajian reguler Oktober diperagakan pelatih; tiap peserta membayar penggajian susulan miliknya
  dan menyetor PPh 21-nya.
- **Kontrabon (F12)**: Finance tidak membuat kontrabon — Manajer membuat & menjadwalkan, Admin menyetujui (kontrol dua orang),
  Finance membayar. Kerjakan F11 sebelum F12.
- Karyawan demo belum punya nomor rekening → Daftar transfer gaji menulis "Tanpa Rekening — Bayar Tunai".
- Akun "Selisih harga pembelian" belum dipetakan → peringatan di tab GR/IR (pemetaan akun = Pengaturan › Keuangan & Pajak).
- Jejak Dokumen: rantai digeser ke kanan untuk melihat simpul kwitansi, kas, dan jurnal.
- **Urutan Piutang wajib F02 → F03 → F04 → F05 → F06.** F04 langkah 7 dijalankan pelatih sesudah semua peserta selesai
  langkah 6 (membuat tagihan berikutnya per peserta; perintah diberikan terpisah). Tagihan berikutnya sengaja tidak dibuat
  sejak awal karena alokasi *Tertua dulu* akan menyerap kelebihan bayar (lihat K-08).
- Denda (F05) bertambah tiap hari: angka di layar peserta berbeda dari contoh di panduan.
- Kas Kecil (F07) langkah persetujuan LPJ dilakukan pelatih sebagai Manajer.
- Rekening BCA & Kas Toko dipakai semua peserta: saldo dan kartu "Selisih" rekonsiliasi tidak akan nol di kelas — peserta
  memeriksa baris miliknya (keterangan "Latihan NN"). Mengimpor mutasi yang sama dua kali di hari yang sama dilewati sebagai
  duplikat. Jangan mengaktifkan usulan aturan pencocokan selama sesi (peserta berikutnya tidak lagi berlatih cocok manual).
- Nominal F09 = Rp 300.000 + NN × Rp 10.000 (peserta 01 = Rp 310.000).
- Antrean Manajer berisi 6 izin kredit latihan (F06) — jangan disetujui sebelum peserta selesai membaca.
- **Mengetik nominal**: "3.374.122,50", "Rp 3.374.123", "3374123" semuanya terbaca benar — minta peserta selalu membaca
  pratinjau di bawah kotak dan kalimat konfirmasi sebelum [Ya, simpan]. Klik tombol simpan SEKALI.
- Bayar tagihan: ketik nominal penuh — kekurangan ≤ Rp 5.000 otomatis menutup tagihan (sekarang diberitahukan di layar).
- Pakai tanggal hari ini (tanggal maju/lampau belum dibatasi, K-16). Bila daftar tetap abu-abu, tekan muat ulang.
- Setujui sample berbayar hanya sesudah uangnya tampil lunas.
- Rekonsiliasi tempel: nominal berkoma dibungkus tanda kutip, atau salin langsung dari Excel.

### Tambahan sesudah penyusunan ulang (bagian 1, 2, 3.4)

- **Fondasi (bagian 1) mengubah pengaturan bersama — kembalikan segera sesudah peragaan:** K02 langkah 8–11 (pemetaan
  Beban administrasi bank khusus Sukacita → kembali ke global; hanya akun beban, jangan akun kontrol), K05 langkah 6–10
  (kelompok umur piutang → "Ikuti nilai grup"), K08 langkah 3–4 dan 7 (naskah kwitansi khusus Sukacita → "Kembali ke aturan
  semua PT"). K07 tidak disimpan ([Buang & tutup]). K01 langkah 7–9: Manajer menambah lalu menghapus akun 6-4950.
  K04: sesudah kelas, nolkan saldo awal dan nonaktifkan "Rekening Latihan NN".
- **Alur ujung ke ujung (bagian 2) diperagakan pelatih** dengan akun tiap peran (sandi semua `demo12345`) pada peserta
  peraga tersendiri, bukan dokumen latihan peserta kelas. Pakai dua jendela browser (mis. Sales & Manajer).
  - A1: pakai pelanggan peraga yang segar (skrip mengatur plafon sendiri); jangan menyetujui izin kredit F06 Rp 50 juta
    lebih dulu. Pengiriman selalu perlu override Manajer (roll latihan tanpa tag RFID). Cocok mutasi bank skor 75 tanpa
    kode bayar → cocokkan manual; dengan kode KN-… di berita transfer → otomatis.
  - A2: satu rantai membayar Rp 116.550.000 dari BCA Operasional KSC (sisa ±Rp 620 juta) → paling banyak 4 rantai; sisanya
    diperagakan bersama. "PPN 12%" di tagihan = 11% DPP (12% × 11/12). "Roll langsung ke gedung simpan" hanya penempatan
    rak; pemeriksaan MD Quality tetap.
  - A3: peringatan oranye "Asal barang tidak terlacak…" di form retur boleh diabaikan. "Nilai" di daftar retur pemasok =
    DPP, bukan total nota debit. Pengiriman SO pengganti mengikuti A1.
- **SDM (3.4):** masa gaji latihan = proses **susulan Oktober 2026** per peserta (cerita: karyawan masuk 1 Oktober, terlewat
  proses reguler → Rapel Rp 8.000.000). Proses susulan menyerap SEMUA masukan yang sudah disahkan dan belum terpakai:
  sahkan masukan satu peserta, minta peserta itu langsung [Hitung gaji], baru peserta berikutnya. Sesudah pelatihan Manajer
  menandai karyawan "Latihan NN · Andi Pratama" keluar (lembur 16 Nov akan masuk proses reguler November).
- Penggajian kini dibuka di tab Proses Gaji; setoran PPh 21 (F15) di tab **Setoran & Pajak**.

### Tambahan Bagian 5 (situasi khusus & koreksi)

- Bagian 5 diperagakan pelatih dengan akun peran pada peserta peraga tersendiri (uji: 61 S1, 66 S2, 71 S3, 76 S4); satu
  putaran ±5–7 menit per situasi dan selalu memakai peserta baru.
- S1: "Finance meninjau nota kredit" hanya untuk nota dari batal item pesanan khusus; nota kredit amandemen terbit saat
  Manajer setuju. Celah tampilan kecil: di umur piutang nota kredit tampak "terbayar"; daftar faktur pajak baru segar
  sesudah SO dibuka ulang.
- S2: PO Rp 101,5 juta hanya untuk memunculkan persetujuan ulang, lalu langsung dibatalkan; eskalasi gudang muncul di Meja
  Saya Manajer; selisih harga Rp 500.000 di GR/IR jangan dikliring di kelas (akun selisih belum dipetakan, K-26).
- S3: satu Override RFID cukup untuk dua surat jalan; saat menyelesaikan kasus pengembalian dana pilih BCA Operasional KSC;
  layar Kasus memuat daftar pelanggan lengkap — tunggu selesai sebelum [Kasus baru].
- S4: jurnal pembalik dicari dengan nomor jurnal asli ("Pembalik KSC/JE-…: alasan"); saldo akun sementara memuat data contoh
  Rp 2.000.000 — peserta mereklasifikasi nominalnya sendiri; koreksi gaji susulan pakai komponen "Insentif".

### Tambahan 18 Nov (K-FIN-01 & S5)

- Akun Finance kini setara Manajer (K-FIN-01): tombol Setujui, Tutup Buku, Jurnal Baru, Tambah Akun, Batalkan kwitansi, dan
  pemilih PT tampil untuk peserta. Ingatkan di awal kelas: tetap di PT Sukacita, jangan menyetujui dokumen peserta lain,
  jangan mengubah pengaturan bersama. Kontrol dua orang tetap: pembuat tidak bisa menyetujui dokumennya sendiri (K-52).
- Materi yang dulu menulis "Finance tidak melihat tombol …" kini menulis bahwa tombol itu tampil; langkah persetujuan di
  latihan tetap diperagakan Manajer sebagai orang kedua.
- S5 memakai dokumen yang sama dengan F02/F03/F11/F12 — jalankan di peserta peraga (uji: 91). Bagian A mengeluarkan
  Rp 3,15 jt per peserta dari BCA Operasional KSC.
- Deck kelas satu hari: `Presentasi_Flow_Krusial_Keuangan.pptx` (Piutang · Hutang · per pihak · Kas & Bank · Koreksi ·
  Buku besar & tutup bulan). Manual & deck lengkap tetap sebagai rujukan.
