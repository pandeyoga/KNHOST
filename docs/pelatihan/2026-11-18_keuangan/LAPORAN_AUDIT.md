# Laporan Audit — Penyusunan Pelatihan Keuangan (17 Nov 2026)

Setiap skenario pelatihan dijalankan **di layar** (Playwright, akun peran yang sama dengan peserta) lalu dicocokkan **di buku**
(jurnal seimbang, saldo, status). Yang tidak lulus ditelusuri sampai akar masalah, diperbaiki dengan uji terarah, atau
dicatat sebagai keputusan pemilik. Rekap hasil uji per skenario ada di panduan (bagian *Rekap uji jalan*).

Status: **D** = diperbaiki (berkas · uji) · **K** = perlu keputusan pemilik · **C** = catatan untuk pelatih/data.

## 0. Hasil uji akhir (pohon akhir, data acuan dipulihkan dari nol)

| Uji | Hasil |
|---|---|
| Pemulihan data acuan dari nol (`restore_local_demo.sh`, kode terbaru) | lulus — 9/9 skenario transaksi demo OK |
| Data latihan (`seed_pelatihan_keuangan_kn.py`) | peserta kelas 01 + peserta peraga 21, 31, 41–45 lulus; peserta baru sesudah aktivitas kelas kini juga lulus (perbaikan pemilihan roll, C-31) |
| **Uji jalan kurikulum lengkap** (`uji/jalankan_semua.sh`, berurutan sesuai kurikulum) | **36 skrip · 333/333 langkah lulus di layar + buku · 0 galat 5xx · 31 menit**. Praktik Finance (F, K, H) berurutan di SATU akun peserta kelas (01) seperti di kelas; alur ujung ke ujung A1–A3 di peserta peraga 21, 31, 41–43; potret navigasi 36 layar. Tangkapan layar manual & slide dari putaran ini |
| Galat konsol peramban (putaran akhir) | 0 dari aplikasi sesudah perbaikan C-29/C-30 (sisa: gangguan jaringan sandbox ke CDN, bukan aplikasi; 2× 400 memang disengaja oleh uji penolakan) |
| Dokumen cetak (`uji/dokumen/`, peserta 01, data bersih) | D1 dokumen penjualan 12/12 · **D2 dokumen keuangan 16/16** (sisa "Kas in" hilang pada data bersih) · D3 naskah/template 9/9 |
| Uji variasi isian & hitungan (`uji/variasi/` V1–V8) | 164 kasus (lihat §2a) — tidak diulang; perubahan sesudahnya tidak menyentuh isian yang diuji |
| Jest penuh (pohon akhir) | 1.688 lulus · 9 gagal = himpunan lama yang sama (phase3P3, roleGateSweep2, phase4R1, fe07ReturnErrors, phase3P8Activation) |
| Backend `tests_mem` penuh | 2.489 lulus · 0 gagal |
| Gate `--ci` | lihat baris penutup (dijalankan sekali pada pohon akhir sesudah bagian 5) |

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
| D-16 | — | Insiden uji: skrip `verify_concurrency.py` (dikira statis) memulihkan 21 koleksi Mongo bersama ±25 detik → data pengembangan tidak konsisten | C · verifikasi akhir dimulai dari data yang dipulihkan bersih; jangan jalankan skrip `guardrails/verify_concurrency.py` saat ada uji lain |

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
| K-SDM-01 | **Dicatat (keputusan pemilik 17 Nov 2026: "SDM/HR itu dipegang finance juga").** Finance menyiapkan data karyawan, kehadiran, aturan & masukan gaji, menghitung dan memposting proses gaji, membayar, dan menyetor. Manajer mengesahkan masukan, perubahan gaji, dan proses gaji, serta membatalkan (anulir) proses. Hapus karyawan, struktur organisasi, dan pengaturan SDM umum tetap Manajer/Admin. Mohon konfirmasi pembagian ini. |
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
| K-43 | Finance tidak punya tab Koreksi & Amandemen / daftar nota kredit-debit untuk akhir bulan, tetapi punya izin mengajukan amandemen. Beri akses lihat? Izin ajukan disengaja? |
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
