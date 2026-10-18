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
