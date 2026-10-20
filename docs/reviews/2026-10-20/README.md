# Hasil lanjutan audit main KNHOST

**Pembaruan 20 Oktober 2026 — frontend dan main terbaru:** baca `AUDIT_FRONTEND_2026-10-20.md` dan `PROMPT_PERBAIKAN_FRONTEND_2026-10-20.md`. Acuannya main **8dab383f764df80737bfe02f887422b3fd72aa70**. Terdapat **13 kelompok temuan terkait frontend** setelah duplikasi akar masalah role digabungkan, dengan bukti render/kontrak, reproduksi HTTP, dan empat observasi browser pada form Interco, Data Gudang serta tautan Harga Khusus. Build terbaru berhasil; seluruh klik/role/flow belum diuji. Screenshot disertakan. Laporan backend di bawah tetap memiliki baseline 63c38bd dan tidak otomatis dianggap seluruhnya diperiksa ulang pada 8dab383.

Tanggal: 19 Oktober 2026

Commit yang diperiksa: `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`.

**Belum merupakan laporan penutupan audit.** Perubahan belum dapat dinyatakan seluruhnya sesuai plan atau bebas bug. Pemeriksaan ini menemukan 11 masalah yang telah direproduksi, disertai lokasi kode, dampak, dan arahan pengujian perbaikan. Tidak ada kode produksi yang diubah atau di-push.

Pembaruan terbaru: baca `LANJUTAN_WMS_SPECIAL_ORDER_MIGRASI.md`. Terdapat 27 kasus WMS unik lulus, 18 kasus realisasi Special Order unik lulus, dan pengujian pembagian sheet ekspor lulus. Temuan baru mencakup apply/rollback migrasi dan recovery pembuangan BS. Hasil terbaru melengkapi, bukan menghapus, catatan batch awal di bawah.

## Isi paket

1. `TEMUAN_TERVERIFIKASI.md`: 11 temuan, bukti, serta arahan perbaikan.
2. `MATRIKS_CAKUPAN.md`: inventaris seluruh 56 requirement dan 230 acceptance dengan keterbatasan pemeriksaan yang eksplisit.
3. `evidence/deep-checks.json`: reproduksi R&D dan unduhan grouping export.
4. `evidence/fault-checks.json`: lease realisasi Special Order dan gangguan posting opname.
5. `evidence/export-consistency.json` dan `concurrent-export.csv`: ketidakkonsistenan export saat sumber berubah serta rincian makloon terpotong.
6. `evidence/test-cases.json` dan `seeded-run/`: rincian eksekusi batch tes repository.
7. `evidence/supplement-run.xml` dan `.log`: pengujian ulang setelah akun fixture dan supplier dilengkapi.
8. `evidence/syntax-scan.json`: hasil parsing Python.
9. `evidence/closure-check.json`: hasil validator penutupan paket plan.

## Apa yang sudah dikerjakan

- Build produksi frontend berhasil dengan warning lint dan ukuran bundle. Dependensi menggunakan cache lokal; belum merupakan verifikasi instalasi bersih dari lockfile.
- Sebanyak 992 berkas Python lolos parsing sintaks. Ini tidak membuktikan semua baris sudah dianalisis semantik atau semua cabang telah dijalankan.
- Batch 69 berkas tes: XML mencatat 248 passed, 51 failed, 93 error, 17 skipped. Beberapa proses Windows memiliki exit abnormal meski tes melaporkan pass; dicatat terpisah dalam hasil proses.
- Setelah fixture akun dari skrip demo repository dan supplier tambahan disiapkan, tujuh modul diuji ulang: **41 passed, 5 failed**. Angka ini tidak boleh ditambahkan ke 248 sebagai jumlah kasus unik karena ada pengulangan.
- Lima kegagalan pengulangan: data grade B1 historis tidak tersedia; SKU contoh yang dicari tidak ada; cleanup MDQ memakai event loop berbeda; pengujian partisi mensyaratkan lebih dari 5.000 baris sedangkan dataset hanya 117; inventory export masih berisi collection yang belum dipetakan. Masing-masing harus ditindaklanjuti menurut penyebabnya, bukan semuanya diberi label bug bisnis.
- Login lokal dan perpindahan ke tampilan desktop/entitas berhasil diamati. Navigasi berikutnya terhambat pemuatan localhost di browser. Pengujian UI menyeluruh belum selesai; kondisi tersebut tidak dipakai sebagai bukti bug halaman export.
- Pengujian gangguan memakai database terisolasi dan injeksi gangguan yang dijelaskan di laporan. Tidak menyuntikkan kegagalan ke sistem produksi.

## Hasil penting

| ID | Masalah |
|---|---|
| AUD-RND-01 | Labdip ACC dapat meluluskan siklus dengan handfeel ditolak |
| AUD-RND-02 | Versi artwork yang tidak ada diterima |
| AUD-EXP-01 | Export grouping selesai tetapi unduhan ditolak 403 |
| AUD-SO-01 | Proses lama dapat menghapus kunci realisasi milik proses baru |
| AUD-WMS-01 | Retry opname tidak memulihkan jurnal yang gagal setelah stok berubah |
| AUD-MKL-01 | Excel rekap klaim makloon error karena kontrak field dan ekspresi total |
| AUD-EXP-02 | Export dapat menggandakan baris saat sumber berubah, count tetap cocok |
| AUD-MKL-02 | Rincian klaim makloon dipotong pada 1.000 baris, berbeda dari total |
| AUD-MIG-01 | Apply migrasi melewatkan fulfillment kosong tanpa melaporkan kegagalan tulis |
| AUD-MIG-02 | Rollback menghapus state operasional yang berubah setelah migrasi |
| AUD-RET-01 | Pembuangan BS gagal pada movement, lalu retry tidak memulihkan proses |

## Yang belum ditutup

Matriks terbaru memuat 168 acceptance yang belum divalidasi penuh, enam acceptance yang berkaitan langsung dengan temuan terbukti, tiga berstatus teruji API lokal dengan batas pengujian dijelaskan, serta 53 acceptance bertanda membutuhkan perangkat fisik pada plan. Ini status penutupan yang konservatif, **bukan klaim 168 butir sama sekali belum disentuh**. Tes yang hanya membuktikan sebagian kondisi tidak otomatis meluluskan seluruh acceptance.

Pekerjaan tersisa meliputi rekonstruksi fixture dataset KN yang sesuai, penelusuran UI lengkap per role, pengujian rantai supplier/makloon sampai Finance dan pengiriman, perjalanan retur lintas lokasi/entitas sampai penyelesaian, pemulihan setelah gangguan di batas transaksi lainnya, migrasi dan rollback, parity kontrak middleware pada main bersih, serta UAT perangkat.

Validator closure menghasilkan 317 hambatan metadata. Ini **bukan 317 bug kode**: termasuk keputusan pending, requirement belum validated, serta bukti/commit penutupan yang belum lengkap. Jangan mengubah status menjadi selesai hanya untuk meloloskan validator.

## Cara menggunakan temuan

Tangani masalah per domain dengan reproduksi yang sama, kemudian tambahkan regresi alur terkait. Perbaikan dinyatakan terverifikasi setelah lulus reproduksi negatif, alur normal, pengujian retry/concurrency yang relevan, dan rekonsiliasi data. Untuk masalah bisnis yang belum pasti, seperti penggunaan kontrak terminated sebagai referensi historis, jangan mengubah perilaku sebelum aturan tersebut dipastikan.
