# Koordinasi dengan Gelombang 1

Paket tidak mengganti `docs/audit/tracker.json`, instruksi maupun perubahan Wave1. Tracker aktif W2 menyimpan related_wave1; wave1-extensions.json mencatat seluruh26 checkpoint pendalaman. Periksa tracker Wave1 repo aktual, bukan menganggap snapshot audit adalah status terbaru.

| Fase | Koordinasi utama |
|---|---|
|P01/P02|WM-07/08, FN-14 (opname); WM-04/GN-13 (transfer/proyeksi); GN-11 (recovery GRN); WM-02 (split)|
|P03|CX-13 makloon, FN-07 bill/pembayaran|
|P04|GN-06 completion/fault/retry/cancel produksi|
|P05|FN-10/GN-11 posting/pemulihan, CX-04/CX-05 uang muka|
|P06|FN-09 koreksi periode tertutup; FN-08 opening rekening|
|P07/P08|RF-16 event/incident, missing-tag/loading dan guard gate dari Wave1; gunakan ID kanonik pada tracker Wave1, bukan nomor baris matriks semata|

Jika kode sudah diperbaiki, tautkan commit dan tambahkan acceptance baru; jangan membuat patch tandingan. Jika belum ada tracker Wave1 dalam repo, rekonstruksi rujukan dari laporan W2 yang sudah memuat bukti baru lalu tandai dependensi belum diverifikasi. Jangan menciptakan status fixed untuk Wave1. Perbaikan lintas fase harus dicatat dalam satu pemilik perubahan dan semua ID terdampak.
