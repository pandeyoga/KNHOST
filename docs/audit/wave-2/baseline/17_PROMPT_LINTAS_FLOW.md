# Prompt implementasi lintas flow

Baca 16_AUDIT_LINTAS_FLOW_QC_SALES_STOK_AR.md dan evidence yang ditautkan. Source audit `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`; kerjakan di branch kandidat terbaru, koordinasikan perbaikan Wave1. Jangan mengubah bukti historis. Isi commit dan hasil uji aktual, lalu status ready_for_validation; hanya validasi terpisah boleh menetapkan verified_fixed.

## Fase1 — W2-014, kontrak UOM QC ke retur supplier

Reproduksi QC PO3kg @10.000, roll10meter/3kg dari GRN asli: reject10meter menghasilkan dokumen10kg/100.000 dan returned_amount PO100.000, seharusnya3kg/30.000 untuk seluruh receipt. Perbaiki qc_service._create_qc_return dan caller dengan qty/unit eksplisit serta harga dalam basis tepat. Pertahankan data berat aktual dan snapshot konversi untuk partial reject; jangan gunakan fallback1:1. Selaraskan label dan input QCInspection dengan satuan nyata. Regression: meter/meter, meter/kg, yard/meter, partial/multi-roll, conversion missing, pembulatan residual, approval dan reversal; rekonsiliasi roll, qty PO, nilai dokumen, AP/GL. Kontrol qc-flow-results harus tetap sesuai pada flow normal. Simpan evidence baru untuk W2-014.

## Fase2 — W2-017 dan W2-016, atomicity sumber dana deposit

Perbaiki create_receipt dan void_receipt sebagai satu kontrak dana. W2-017: dua pemakaian80.000 atas deposit100.000 dapat memberi total pembayaran160.000 walau caller kedua409. W2-016: void receipt150.000 yang deposit100.000-nya sudah terpakai membalik pembayaran/kas sebelum gagal409. Reserve/claim dana dan prasyarat pembalikan sebelum efek pada SO/kas/receipt; status final harus mensyaratkan semua efek selesai. Gunakan operasi durable/idempoten dengan pemulihan yang terukur; CAS deposit saja belum cukup karena sudah ada. Uji create-vs-create, create-vs-void, saldo negatif, dana terpakai, multi-order, crash tiap efek, retry dan rollback. Hasil penolakan harus tidak meninggalkan payment/receipt posted tanpa dana atau sumber receipt posted dengan efek sudah dibalik. Koordinasikan GN-11 tanpa menggandakan tiketnya; W2-016/017 tetap acceptance cases berbeda.

## Fase3 — W2-018, perubahan payments SO yang aman saat bersamaan

Reproduksi void40.000 yang dijeda sebelum `$set payments`, lalu pembayaran baru60.000. Saat ini dua respons200 tetapi paid_total0/kas60.000. Hilangkan penimpaan array snapshot lama; gunakan operasi terarah dan concurrency control ketika merekonsiliasi paid_total/payment_status. Jangan menghapus kontrol realokasi negatif. Uji dua void, void+create, multi-receipt satu SO, alokasi lintasSO, retry, serta failure setelah mutation. Pembayaran lain harus tetap tersimpan dan jumlah sama dengan receipt sah; dapatkan bukti end-to-end API, bukan hanya unit helper.

## Fase4 — W2-015, posting nonkas dan pembalikannya

Pisahkan posting GL transaksi pembayaran dari keberadaan cash_transaction. Receipt amount0/use_deposit100.000 harus menghasilkan debit kewajiban deposit/kredit piutang100.000 tepat sekali, tanpa membuat kas fiktif. Uji murni kas, murni deposit, campuran, multi-order, void, closed period, posting failure, retry dan backfill. Pastikan recovery dari fase2/3 tidak menghasilkan jurnal dobel atau jurnal tanpa receipt sah. FN-10 Wave1 menyangkut exception GL yang ditelan: koordinasikan desain, tetapi jangan anggap perbaikannya otomatis menutup jalur amount0.

## Fase5 — GN-13, proyeksi stok mengikuti revision yang benar

Pendalaman baru memakai hold_stock asli: rebuild lama membaca available10, hold4 menulis6/4, rebuild lama lalu menimpa10/0. Terapkan revision/watermark atau mekanisme konsistensi per segmen yang menjamin proyeksi lama tidak menggantikan hasil baru. Pertahankan roll sebagai SSOT dan aturan ownership/UOM. Uji rebuild terbalik urutannya saat hold, reserve, QC, transfer, split dan cancellation; source roll, balance, ATP dan lot aggregate harus konsisten. Failure konversi harus terlihat, bukan dicampur1:1. Evidence projection-results kini membuktikan bagian race GN-13 runtime; simpan validasi pada tiket Wave1 GN-13 tanpa mengubahnya menjadi temuan W2 baru.

## Uji lintas fase sebelum menyerahkan validasi

Jalankan kembali lifecycle sales-flow: stok100 → order20 → verifikasi → pick → dispatch8+12 → delivered → retur5 → store credit50.000 → reversal. Pastikan guards tetap aktif, stok tidak bertambah/ganda pada retry, credit note tidak dobel, pembayaran/deposit dan jurnal net konsisten. Perluas ke refund tunai/pajak/multi-produk; harness audit ini belum menutup variasi tersebut. Laporkan apa yang benar-benar dijalankan dan apa yang masih belum tersedia.

## Fase6 — W2-019, konservasi catch-weight saat split

Reproduksi W2-Q-F03: roll10meter/3kg dipisah QC accept6 dan damaged4; dua roll masing-masing menyimpan3kg, total6kg. Perbaiki qc_service._consume_quarantine dan kontrak insert_child_roll dengan ukuran tambahan yang konservatif dan provenance. Jangan mengasumsikan estimasi berat sebagai timbang aktual. Pilih pengukuran ulang atau estimasi proporsional berlabel sesuai keputusan bisnis; total/residual tidak boleh menggandakan berat. Periksa caller reservasi, dispatch parsial, transfer dan pindah bucket; uji masing-masing sebelum menyatakan semuanya fixed. Pertahankan kontrol full accept3kg dan panjang6+4=10. W2-014 membutuhkan basis nilai pembelian yang benar juga: koordinasikan kedua perubahan tanpa mencampur jumlah fisik dengan jumlah harga.
