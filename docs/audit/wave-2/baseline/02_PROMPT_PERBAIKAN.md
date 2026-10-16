# Prompt develop — Gelombang 2, putaran W2-01

Jalankan setelah membaca README, temuan detail, dan pekerjaan Gelombang 1 yang menyentuh fungsi sama. Jangan mengambil alih perbaikan agent lain. Baca kode terbaru dan reproduksi ulang sebelum mengedit. Jangan menerapkan perubahan data produksi otomatis. Simpan implementasi dan validasi per ID; implementer hanya menandai ready_for_validation, bukan verified_fixed.

## W2-001 — rekonsiliasi jumlah dan nilai

Audit dan perbaiki kontrak receive_step makloon dari actual_output_qty, panjang tiap roll, konversi satuan sampai alokasi WIP dan jurnal persediaan. Reproduksi bukti 10 reported/9,5 measured/material100/jasa20: API saat ini menyelesaikan receipt dengan stok114 versus jurnal120. Pilih basis quantity kanonik sesuai kontrak produk; simpan declared/measured secara terpisah jika toleransi diperlukan. Distribusikan nilai dan residual rounding secara deterministik agar total nilai roll+byproduct sama dengan kapitalisasi GL. Selaraskan validasi UI dan API. Tambahkan uji jumlah sama, lebih/kurang dalam toleransi, batas toleransi, multi-roll, partial, UOM dan byproduct; buktikan tidak menimbulkan posting ganda pada retry. Catat keputusan, file, commit, perintah uji dan hasil aktual dalam evidence; update tracker W2-001 menjadi ready_for_validation setelah lolos.

## W2-002 — validasi lokasi sebelum efek bisnis

Reproduksi POST makloon receive memakai ID gudang yang tidak ada dan buktikan respons sekarang200 beserta roll invalid. Perbaiki validasi effective output warehouse setelah fallback ditentukan tetapi sebelum input dikonsumsi, bill/jurnal/roll ditulis. Gunakan service kebijakan gudang yang sudah ada dan pertahankan gudang shared yang sah. Pastikan semua jalur receive memakai kontrak sama. Uji gudang valid/tidak ada/archived/fallback kosong dan shared sesuai policy; pada penolakan, stok input, order, bill, output, jurnal dan saga lock tidak berubah. Catat evidence dan commit, lalu ready_for_validation untuk W2-002.

## W2-003 — lokasi setiap partial receipt

Reproduksi partial makloon4 di WH dan final6 di WH2 melalui helper, lalu buat test HTTP lengkap create→link→count→reconcile→close untuk kedua kedatangan. Periksa kontrak bisnis apakah multi-gudang diizinkan. Bila diizinkan, pertahankan identitas GRN dan warehouse per roll sampai posting; jika tidak, tolak mismatch secara eksplisit sebelum mutasi. Tangani partial lama tanpa warehouse dengan pembacaan GRN asal dan kebijakan pemulihan yang dapat diaudit. Jangan memperlakukan pemindahan lokasi sebagai receipt baru. Uji gudang sama, berbeda, cancellation, retry, finalisasi bersamaan dan partial lama. Koordinasikan concurrency dengan CX-13 Gelombang1. Catat bukti, commit, keterbatasan dan status ready_for_validation untuk W2-003.
