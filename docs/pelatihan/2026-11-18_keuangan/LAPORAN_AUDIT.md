# Laporan Audit — Penyusunan Pelatihan Keuangan (17 Nov 2026)

Setiap skenario pelatihan dijalankan **di layar** (Playwright, akun peran yang sama dengan peserta) lalu dicocokkan **di buku**
(jurnal seimbang, saldo, status). Yang tidak lulus ditelusuri sampai akar masalah, diperbaiki dengan uji terarah, atau
dicatat sebagai keputusan pemilik. Rekap hasil uji per skenario ada di panduan (bagian *Rekap uji jalan*).

Status: **D** = diperbaiki (berkas · uji) · **K** = perlu keputusan pemilik · **C** = catatan untuk pelatih/data.

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
