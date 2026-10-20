# Validasi ulang pada main terbaru 8dab383 — 20 Oktober 2026

Acauan terbaru: `8dab383f764df80737bfe02f887422b3fd72aa70`. Snapshot: `work/KNHOST-frontend-audit-2026-10-20`. Addendum ini menentukan status terkini; laporan sebelumnya menguraikan akar masalah pada 63c38bd.

## Hasil paling penting: Special Order multiitem terbukti melalui API aktual

FE-SR-04 berhasil direproduksi pada backend main terbaru di port 8020 dengan database audit `kn_frontend_audit_20261020`.

1. **POST create Special Order: 200.** Payload dua item: Artikel A 100 yard dan Artikel B 200 yard. Keduanya tersimpan sebagai item berbeda oleh endpoint asli.
2. Fixture sample terminal/ACC pelanggan disiapkan dalam database audit, untuk memfokuskan tes pada harga/konversi. Produk A dan B adalah produk khusus tes dengan stok nol.
3. **GET pricing: 200.** Dengan biaya A=10, B=30 dan margin 30%, respons memilih **B 100 yard**, harga 39 dan total **3.900**. Jika kedua item dihitung dengan margin yang sama, total seharusnya 1.300 + 7.800 = **9.100** sebelum pajak.
4. **POST lock-price (auto_po=false): 200.** Harga yang salah diterima dan dikunci oleh aplikasi.
5. **POST convert-to-so: 200.** Aplikasi benar-benar membuat SO `KSC/SO-00039`, status `waiting_stock`, dengan **satu baris B 100 yard**. Artikel A hilang, dan qty B juga salah. Subtotal 3.900; grand total 4.329 mengikuti PPN fixture. Artinya guard tidak mencegah kondisi ini dan bukan sekadar ekspresi AST yang salah.
6. Fixture milik tes dibersihkan: dua produk, dua sample, satu Special Order, dan satu SO. Tidak membuat pembayaran atau menguji pengiriman fisik. Jejak audit dan nomor counter tes tetap menjadi bukti di database audit.

Bukti lengkap: `multi-item-http-latest-evidence.json`; harness: `verify-multi-item-http-latest.py`. Level bukti sekarang **HTTP terverifikasi pada main terbaru**. R&D hingga ACC, pengadaan, receiving, pengiriman dan AR belum dijalankan sebagai satu rantai dalam tes ini.

## Status enam temuan pada main terbaru

| ID | Status terbaru | Dasar validasi |
|---|---|---|
| FE-SR-04 | **Masih ada, HTTP terverifikasi** | API create → pricing → lock → convert benar-benar menghasilkan satu baris B100 dari A100+B200. |
| FE-SR-01 | **Masih ada, callback aktual diuji ulang** | Handler `SalesReturns.jsx:163` masih menelan error; cabang detail kini baris 218, error daftar baris 312. `ReturnSettleModal.jsx:65` masih menutup dialog. Harness terbaru menghasilkan `modal_closed=true` saat API disimulasikan menolak. Penambahan tombol buang draf tidak memperbaiki propagasi error ini. |
| FE-SR-02 | **Masih ada, callback aktual diuji ulang** | `CreateReturnForm.jsx:59` belum memiliki cancellation/sequence check. Respons A yang terlambat tetap menimpa produk ketika SO-B terpilih. Penambahan initialOrderId/kamera tidak mengubah handler ini. |
| FE-SR-03 | **Masih ada, penelusuran gate/permission** | SpecialOrders, SpecialOrderDetail dan SalesReturns tetap memakai array literal role pada titik yang dilaporkan. Pagar `canSeeGrade` yang baru ditambahkan adalah perbaikan visibility tersendiri; tidak menyelesaikan ketersediaan tombol aktivitas bagi custom role. |
| FE-SR-05 | **Masih ada, source/kontrak tidak berubah** | QCInspection tetap menjumlah angka mentah serta melabel input dan angka sebagai meter; tidak ada perubahan konversi/unit pada jalur tersebut. |
| FE-SR-06 | **Masih ada pada pemilih desktop umum** | SalesReturns tetap mengambil nonpaged sales-orders yang dibatasi 200 lalu menyaring lokal. MobileSalesNative kini dapat memberikan initialOrderId dari pesanan yang sudah diketahui; ini membantu jalur mobile tersebut tetapi tidak membuat pemilih umum dapat mencari semua SO eligible. |

## Bukti dan inventaris terbaru

- `callback-evidence-latest.json`: fungsi aktual dari source terbaru, bukan salinan implementasi tes.
- `control-inventory-latest.json`: **161 berkas, 918 elemen** dalam inventaris statis. Angka ini tidak berarti 918 elemen sudah diklik/lulus.
- `multi-item-http-latest-evidence.json`: request/response create, pricing, lock-price dan convert; tidak menyimpan token login.

Pemeriksa utama menangani browser. Hambatan browser localhost/sandbox harus dilaporkan sebagai batas lingkungan, bukan bug aplikasi. Review ini tidak mengklaim seluruh tombol atau semua flow main terbaru telah lulus.
