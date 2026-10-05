> Pembaruan putaran 5: [kontrol periode, scope dan inspeksi](22_AUDIT_PERIODE_SCOPE_DAN_INSPEKSI.md), empat cacat baru terkonfirmasi, satu gap kebijakan, sembilan skenario tambahan dan 19 test bawaan lulus. [Prompt perbaikan](23_PROMPT_PERBAIKAN_PERIODE_SCOPE_INSPEKSI.md).

# Pengujian integrasi lanjutan KNHOST

Snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`, diperiksa 29 September 2026.

[Temuan baru](19_TEMUAN_INTEGRASI_LANJUTAN.md) · [Prompt perbaikan](20_PROMPT_PERBAIKAN_INTEGRASI.md) · [Cakupan runtime](21_CAKUPAN_RUNTIME_DAN_ENDPOINT.md) · [Harness dan hasil](integration_repro/README.md)

Pengujian sekarang memakai aplikasi yang benar-benar diimpor, FastAPI/ASGI, Motor dan MongoDB 8.0.12 lokal. Bukti ini lebih kuat daripada model query pada putaran sebelumnya. **Belum seluruh kode dan seluruh flow selesai diuji**, khususnya kombinasi role/state, UI browser, worker, data historis dan perangkat fisik.

## Hasil terukur

- **246 modul service berhasil diimpor.** Tidak ada kegagalan import setelah dependency audit tersedia dan adapter platform diterapkan. Ini bukan eksekusi semua fungsi.
- **1.353 endpoint router diuji tanpa login:** 1.351 menghasilkan 401; dua menghasilkan 200. Dua endpoint tersebut adalah logout serta verifikasi publik e-sign untuk kode tidak dikenal, yang mengembalikan valid=false.
- **User sintetis tanpa permission:** 1.261 respons 403, enam 401, 46 respons 200, 34 respons 404, empat 400, dan satu 503. Logout sengaja dilewati agar sesi uji tidak terhapus. Respons 200/404/400 tidak otomatis menunjukkan bug: beberapa endpoint hanya membutuhkan autentikasi, atau baru memeriksa izin setelah menemukan dokumen. Pengujian ini belum menggantikan seluruh matriks role dan akses objek.
- **19 skenario bisnis terarah:** 16 perilaku cacat teramati, satu gap bersyarat mengenai overlap lembur, dan dua kontrol benar. Lima temuan tambahan dan pendalaman HR-03 dijelaskan pada dokumen 19; sebelas skenario memperkuat temuan lama. IX-02 tidak dihitung ulang sebagai akar cacat baru. Jumlah skenario tidak boleh dijumlahkan sebagai jumlah bug baru.
- **Trace source:** 4.146 baris berbeda pada 195 berkas; 1.680 fungsi mempunyai setidaknya satu baris yang dieksekusi. Banyak router berhenti pada guard. Ini bukan persentase keberhasilan flow atau branch coverage.

## Temuan lama yang kini dibuktikan dengan MongoDB asli

| Skenario | Temuan terdahulu | Hasil |
|---|---|---|
| I4-RF01 | RF-01 | EPC dari ZPL tanpa pemisah ditolak; EPC dalam format tersimpan diterima |
| I4-RF02 | Gate/QC pada RF dan AX | PA cancelled dengan roll quarantine tetap mendapat green pada cabang putaway |
| I4-RF03 | RF-13 | Device offline dapat authenticate dan heartbeat hingga menjadi online |
| I4-RF04 | RF-05 | Dua roll, satu belum bertag; hasil complete tetap clean dan dispatch guard mengizinkan |
| I4-WM01 | WM-01 | Split 30 dan 40 mengubah total panjang 100 menjadi 140 pada interleaving terkontrol |
| I4-FN01 | CX-01 | Request 10 menerapkan pembayaran 150; saldo kredit 100 menjadi −50; posting GL asli menghasilkan satu jurnal |
| I4-FN02 | CX-06 | Mutasi bank OUT pada BANK1 dapat matched ke transaksi kas IN pada BANK2 |
| I4-FN03 | CX-07 | Transaksi kas 100 dialokasikan 60+60 hingga reconciled_amount menjadi 120 |
| I4-HR01 | HR-03 | Dua pengajuan masing-masing 10 hari disetujui atas jatah 12; remaining menjadi −8 |
| I4-HR03 | HR-03 | Tiga hari cuti lintas tahun seluruhnya dibebankan ke tahun mulai; tahun berikutnya mendapat pembebanan nol |

I4-HR07 memperkuat gap bersyarat HR-02: apabila automatic 120 menit dan formal 120 menit merepresentasikan pekerjaan yang sama, payroll menjumlahkan 240 menit. Fixture pada hari yang sama tidak membuktikan bahwa seluruh catatan formal dan otomatis selalu duplikat.

## Kontrol yang benar

I4-C01: kehadiran tepat jadwal pada shift 08–17 menghasilkan work_min=540 dan overtime_min=0.

I4-C02: preview payroll dengan body entity B ditolak 403 untuk user A. Generic body guard bekerja. Kandidat kebocoran dari pembacaan router saja tidak dinaikkan menjadi bug.

## Metode dan batas lingkungan

Database setiap proses memakai nama acak `knhost_audit_*`, baru dan hanya pada `127.0.0.1:27919`. Tidak ada credential atau data produksi yang digunakan. Jaringan keluar proses pengujian dibatasi ke loopback; tidak ada transfer bank, pengiriman OTP nyata atau perintah perangkat.

Fungsi bisnis diimpor utuh dari source. Untuk split, wrapper hanya menahan return setelah Mongo benar-benar menjalankan CAS agar interleaving dapat diulang; query dan update tidak diganti. Store credit menggunakan posting GL asli, dan bank matching menjalankan layanan learning serta penulisan database asli.

Full app lifespan, scheduler dan bootstrap tidak dijalankan. Seluruh indeks deployment belum dipasang. Hasil ini tidak membuktikan crash recovery worker, transaksi replica set atau kesiapan startup produksi Linux. Fixture juga tidak merekonsiliasi saldo pembukaan perusahaan nyata.

Host Windows memerlukan adapter `os.uname()` untuk hostname scheduler. Adapter berada dalam harness; repository tidak diubah. Konfigurasi CORS lokal diisi. Ini tidak membuktikan aplikasi mendukung startup Windows tanpa adapter.

Dependency inti FastAPI 0.110.1, Motor 3.3.1, PyMongo 4.6.3 dan Pydantic 2.13.5 mengikuti source. Versi dependency lain dalam lock audit dapat berbeda dari keseluruhan requirements repository; versi aktual dilampirkan.

MongoDB diunduh sebagai ZIP resmi mengikuti [dokumentasi instalasi ZIP MongoDB](https://www.mongodb.com/docs/v8.0/tutorial/install-mongodb-on-windows-zip/). SHA-256 arsip lokal adalah `d1b4a8ce75f0d474218768facb91f07b7de6d3d8126f3732c90d72978639049a`. Ini hash lokal, bukan klaim pencocokan dengan checksum vendor terpisah.

Dua endpoint export Excel awalnya menghasilkan 500 karena dependency openpyxl belum terpasang. Setelah dipasang dan payload probe diperbaiki, seluruh probe anonim selesai tanpa 500. Kegagalan penyiapan ini tidak dihitung sebagai bug aplikasi.

## Pekerjaan yang masih terbuka

Daftar detail ada pada [14 — cakupan dan sisa](14_STATUS_CAKUPAN_DAN_SISA.md), dengan pembaruan bahwa integrasi Mongo/ASGI sudah tersedia untuk skenario di laporan ini.

Inventaris test bawaan menemukan 268 berkas dengan 2.133 fungsi bernama test; 251 berkas mengimpor HTTP client dan 118 mengimpor DB client. Banyak bergantung pada akun, fixture dan ID tertentu. Angka tersebut bukan jumlah test bawaan yang sudah dijalankan.

Masih diperlukan pengujian seluruh happy path, partial completion, reversal, kegagalan dan konkurensi di workflow lainnya; matriks role dan objek; UAT browser seluruh 36 kelompok fitur; rekonsiliasi dataset acuan; serta RFID/gate secara fisik. Peraturan pajak/payroll terbaru juga memerlukan validasi terpisah. Semua endpoint telah menerima probe autentikasi, tetapi **seluruh perilaku bisnis belum terverifikasi**.
