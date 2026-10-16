# Audit lanjutan KNHOST — data frontend dan rantai bisnis

**Kesimpulan: sistem belum dapat dinyatakan seluruh data dan flow-nya benar.** Sebanyak 19 temuan validasi sebelumnya masih terbuka; audit ini menambah 30 catatan yang membedakan counterexample, kompatibilitas legacy, gap definisi metrik dan kelemahan oracle tes. Daftar tidak menyamakan seluruh kegagalan pytest dengan bug.

**Commit diperiksa:** `d6da1a3d536228582645abb98aea19f3e491f300`. **Pembanding:** `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`. Tanggal audit 2026-10-05. Semua bukti dibuat memakai source candidate asli, database lokal sintetis dan fixture terpisah. Perubahan aplikasi tidak diimplementasikan atau dipush dalam audit ini.

Prioritas utama: failurewindow stock/production/receipt yang tetap terbuka; komisi lintas entitas; grainowner pada valuasi/velocity; partialreservation yang diabaikananalitik; forecastAR/termin; netrevenue diskon; target/scope; dan summarypagination. Chart bisa menghitung formula dengan benar tetapi mengambil cakupan, unit, status atau sumber yang salah.

**Cakupan 100% perilaku belum tercapai.** Inventaris seluruh 5.114 file dan parse 2.104 file code tersedia; 588 dari 637 GET dieksekusi, sementara 49 memerlukan fixture atau parameter khusus. Full pytest dan replay dijalankan, tetapi ada error fixture, skip, branch belum teruji dan belum ada browser/perangkat RFID/printer E2E. Jangan memakai laporan ini sebagai sertifikasi seluruh flow benar. Rincian coverage ada pada dokumen04 dan CSV per file.

## Cara membaca paket

| Berkas | Isi |
|---|---|
| `02-TEMUAN-DATA-FRONTEND.md` | Temuan baru: letakkode, source, expected/actual, dampak, prompt dan acceptance |
| `03-TEMUAN-LAMA-MASIH-TERBUKA.md` | 19catatan lama yang belumtertutup |
| `04-CAKUPAN-DAN-BUKTI.md` | Angka coverage nyata dan batas pengujian |
| `05-RANTAI-MODUL-DAN-METRIK.md` | Hubungan antarmodul dan source-flow |
| `06-TRIAGE-PENGUJIAN.md` | Diferensial pytest dan penjelasan kegagalan |
| `07-WORKFLOW-AGENT.md` / `prompts/` | Urutan fase dan aturan bukti closure |
| `findings-tracker.json` | Tracker 49 catatan; agent melengkapi bukti implementasi |
| `wave-1-2-revalidation-register.json` | SemuaIDhistoris, verdictlama dan bukti replayterbaru dibedakan |
| `frontend-api-lineage.csv` | Mapping consumerliteral kehandler, sumbercollectionlangsung, unresolvedexplicit |
| `all-file-coverage.csv` | Semua file/hash/metode pemeriksaan; tidak disamaratakan manualreview |
| `evidence/`, `repro/`, `test-logs/` | Output asli dan skrip pembanding, termasukhasilnonpass |

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
| D4-DASH-01 | P1 | Ringkasan dashboard kehilangan reservasi makloon di luar100SKU pertama |
| D4-HR-01 | P1 | Payroll gabungan memakai satu run pada KPI dan menimpa run lain pada trend |
| D4-HR-02 | P2 | Turnover menggunakan waktu edit data sebagai waktu karyawan keluar |
| D4-WMS-01 | P2 | RFID RED hari ini pada Warehouse Health memakai hari UTC |
| D4-WMS-02 | P2 | Cycle count terbaru yang belum selesai menghapus angka akurasi terakhir |
| D4-WMS-03 | P1 | Utilisasi gudang mengabaikan struktur Rack→Level→Bin yang didukung master |
| D4-MKT-01 | P2 | Reach agregat post disajikan ulang sebagai reach tiap platform dan akun |
| D4-RND-01 | P2 | KPI R&D menggabungkan orang berbeda yang mempunyai nama sama |
| D4-FE-01 | P2 | Grafik velocity Manager selalu memotong menjadi14hari |
| D4-FE-02 | P1 | Respons lama dapat menimpa dashboard setelah pengguna beralih entitas |
| D4-TEST-01 | P2 | Tes konsistensi ATP dapat lulus walaupun mencatat mismatch |
| D4-DATE-01 | P2 | Penjualan dan Home menggunakan bulan/tahun UTC yang berbeda dari periode bisnis WIB |
