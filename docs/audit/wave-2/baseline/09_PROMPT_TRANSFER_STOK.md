# Prompt develop — W2-008, W2-009 dan perluasan W2-006

Baca [temuan lengkap](08_TEMUAN_TRANSFER_STOK.md), hasil runtime dan pekerjaan Gelombang1 pada core roll, scope dan transfer. Reproduksi pada commit kerja. Pertahankan bukti historis, simpan hasil perbaikan pada iterasi baru. Implementer menandai ready_for_validation; validator independen menilai fixed atau reopened.

## W2-008 — roll pilihan manual dari owner lain

Reproduksi user A di gudang shared dengan produk stok A20 dan B10. POST transfer intra milik A memakai roll_ids B menghasilkan200; dokumen item ownerA tetapi roll reserved milikB. Perbaiki validasi efektif per roll dan per request: product, source warehouse, owner, status, panjang, hak actor, dan kebijakan gudang. Pastikan tidak ada efek parsial saat salah satu roll tidak cocok. Gunakan guard DB saat update supaya state yang berubah setelah precheck tidak lolos. Uji auto dan eksplisit, mixed owners, shared/dedicated, retry, cancel dan konkurensi. Verifikasi transfer intra tidak menjalankan kepemilikan lintas PT; intercompany menggunakan dokumen dan jurnal khusus. Catat bukti dan commit, lalu ready_for_validation untuk W2-008.

## W2-009 — projection usang pada reservasi eksplisit

Reproduksi roll A10 dan balance available10/reserved0. POST transfer dengan roll_ids berhasil dan roll menjadi reserved tetapi balance tetap available10/reserved0. Bandingkan auto reserve stok20 qty10 yang benar menghasilkan available10/reserved10. Perbaiki cabang roll_ids agar projection segmen yang berubah diperbarui dan failure/retry tidak meninggalkan status roll, dokumen atau balance berbeda. Jangan menganggap pembaruan saat cancel cukup. Uji ATP yang membaca projection, urutan create→approve→dispatch→receive/reject/cancel, dan kegagalan setelah reservasi roll ke-n. Koordinasikan dengan perbaikan GN-13 tanpa menutup tiket itu otomatis. Catat bukti dan commit, lalu ready_for_validation untuk W2-009.

## Perluasan W2-006 — fallback owner transfer otomatis

Reproduksi user hanyaA, stok produk hanya B10 pada gudang shared, create transfer tanpa owner/roll_ids; hasil sekarang dokumen entityA dengan item ownerB. Terapkan kontrak owner berizin yang sama pada semua pemanggil resolve_stock_owner, termasuk cycle count dan transfer. Jika auto owner tidak dapat dipilih secara sah, tolak dengan penjelasan tanpa reservasi B. Uji fallback, explicit payload, entitas multiakses dan opsi intercompany yang benar. Tambahkan bukti W2-T-F03 pada W2-006; jangan menaikkan jumlah temuan unik.
