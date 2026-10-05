# Prompt develop — W2-006 dan W2-007

Baca [laporan](06_TEMUAN_CYCLE_COUNT.md), bukti runtime dan pekerjaan P01/P02/P10 Gelombang1 yang mungkin mengubah fungsi sama. Reproduksi pada SHA kerja saat ini. Jangan mengubah status tiket Gelombang1 dari hasil pengujian ini. Simpan bukti implementasi baru per iterasi; jangan menimpa count-results.json historis.

## W2-006 — owner otomatis harus tetap berada dalam scope sah

Reproduksi user hanyaA pada gudang shared dengan produk yang available hanya milikB: create sessionA → add item tanpa owner → expected B10 → actual8 → submit/approve sukses dan B menjadi8. Pertahankan kontrol explicit ownerB ditolak403, foreign session404, dan produk yang mempunyai stokA diproses untukA.

Perbaiki pemilihan owner pada opname sebagai kontrak otorisasi, bukan preferensi stok terbesar. Jangan hanya memvalidasi payload owner: validasi hasil resolver dan item lama juga. Jika ownerA tidak punya available stock, tetap pertahankan targetA atau berikan error yang tepat; jangan fallback keB. Periksa perbedaan available versus fisik untuk reserved/quarantine sesuai kontrak opname, tanpa merusak perbaikan WM-07/WM-08 yang sedang berlangsung.

Uji owner kosong, explicit, penggunaA dan A+B, stok nol, reserved-only, shared warehouse, sesi lama itemB dan perubahan izin sebelum approve. Pada penolakan tidak boleh ada pembacaan expected atau adjustment owner tidak sah. Catat commit, desain, bukti API dan efek Mongo; tandai W2-006 ready_for_validation setelah lulus.

## W2-007 — satu keputusan akhir untuk approve/reject

Reproduksi reject membaca submitted lalu dijeda; approve menerapkan100→90 dan selesai; reject dilanjutkan sehingga200 dan status akhirrejected. Perbaiki reject serta approve agar memakai protokol status/version/lock yang sama. Request kalah harus conflict tanpa metadata penolakan, audit sukses atau perubahan stok tambahan. Jangan mengandalkan disabled button di UI.

Uji kedua interleaving, reject saat lock aktif, double reject, retry, serta failure setelah adjustment. Pastikan status terminal sesuai keputusan yang benar-benar menang dan bukti stoknya. Cancellation setelah approval, jika dibutuhkan, harus operasi reversal tersendiri yang dapat diaudit. Koordinasikan dengan WM-08 dan FN-14 tanpa mengklaim keduanya selesai dari test ini. Simpan commit dan hasil regression, lalu tandai W2-007 ready_for_validation; validator independen menentukan verified_fixed.
