# Prompt implementasi dan validasi kebutuhan klien

Gunakan per fase, pada branch kandidat yang memuat perbaikan terbaru. Basis audit lama: `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Baca memo25 dan register26 terlebih dahulu. Jangan mengulang implementasi yang sudah diselesaikan agent Gelombang1; petakan commit dan test yang relevan. Prioritas berikut mengurutkan dependensi, bukan meminta seluruh fase digabung menjadi satu perubahan.

## Kontrak untuk setiap fase

> Bandingkan snapshot audit dengan kode sekarang. Konfirmasi bug/gap masih berlaku sebelum mengubah kode. Jangan menimpa bukti historis. Gunakan database sintetis, tanpa data produksi. Catat commit, file, perubahan perilaku, test dan batas validasi. Update tracker dari open ke in_progress lalu ready_for_validation; jangan menandai verified_fixed hanya karena implementasi selesai. Pisahkan kebutuhan fitur, keputusan SOP dan cacat. Jangan mengubah Wave1 tracker tanpa koordinasi. Buat acceptance test atas kontrak bisnis, bukan test yang sekadar meniru implementasi.

## Fase 1 — pagar akses MD dan kontrak sampling

> Perbaiki W2-025 dengan guard dokumen yang konsisten atas entity, line dan permission aksi. Replay reproducer pada salinan hasil untuk membuktikan perilaku lama, lalu buat regression yang menuntut penolakan akses printing oleh woven-only, mempertahankan akses woven dan multi-line sah. Periksa jalur turunan tanpa menganggap semua endpoint pasti cacat. Kebijakan dokumen/assignment tanpa lini harus eksplisit.
>
> Selanjutnya validasi W2-REQ-03: SKU hasil MD mengikuti uji wajib menurut lini/spesifikasi (woven/knit labdip+handfeel; printing proofing dan handfeel bila diwajibkan), bahan standar tidak wajib melalui R&D. Default pilihan jenis sampling bukan bukti gate sudah benar. Uji missing/rejected/ACC setiap jenis wajib, perubahan spesifikasi setelah ACC, approve_spec langsung, sample decide, release, kegagalan pembentukan SKU dan retry. Tutup bypass jika terbukti. Jangan memaksa semua SKU menjalani tiga uji atau membuat master ganda saat retry. Laporkan penerapan performed_by/recorded_by dan custom permission per jenis sampling sesuai kebutuhan nyata W2-REQ-01.

## Fase 2 — master item, warna, tahap dan lot

> Kerjakan W2-REQ-02 setelah menyusun kamus data untuk persetujuan pemilik master. Jangan mengarang standar penamaan perusahaan. Bedakan SKU/template, stage, fabric_type, line_code, warna internal, supplier color, lot internal dan supplier lot. Pertahankan SKU serta referensi histori saat koreksi nama/nonaktif. Raw material boleh dibuat langsung dengan permission dan lifecycle yang sesuai; output MD tetap mengikuti fase1.
>
> Sediakan preview migrasi legacy, daftar duplikasi/konflik dan rollback sebelum perubahan massal. Jangan melakukan rename lot internal untuk menggantikan lot supplier. Uji koreksi supplier lot, split/merge genealogy, label dan referensi roll/dokumen. Bila alias warna customer diperlukan, definisikan kontraknya terlebih dahulu; jangan menyamakan eksklusivitas customer dengan alias kode.

## Fase 3 — rencana kebutuhan dan reservasi material makloon

> Kerjakan W2-REQ-07. Telusuri SO→PR sourcing→MKO→issue→receive dan integrasikan reservasi material pada titik komitmen rencana yang eksplisit. Hitung input menurut resep, yield dan satuan; 600 output tidak selalu600 greige. Reservasi mengurangi ketersediaan untuk komitmen baru, tetapi tidak mengurangi fisik/menjurnal issue sebelum barang benar-benar diserahkan. Issue mengonsumsi reservasi yang sama; cancel/replan mengubah atau melepasnya.
>
> Uji dua SO bersamaan, shortage parsial, perubahan resep/qty, pembatalan, retry setelah fault, multi-step, owner dan warehouse berbeda. Rekonsiliasi available/reserved/subcon/output dan nilai persediaan/WIP. Cocokkan dengan perbaikan makloon/produksi Wave1 serta W2-001 dan W2-024; jangan memperbaiki double-consumption dengan menyembunyikan selisih saldo.

## Fase 4 — penerimaan aktual, keputusan MD dan keuangan PO

> Kerjakan W2-REQ-06. Pertahankan panjang aktual setiap roll. Gunakan kasus PO10×100, diterima10roll total960: (a) tunggu40; (b) revisi kesepakatan960; (c) short-close sisa. Sediakan tugas/notifikasi untuk MD penanggung jawab, alasan dan jejak approval. Gunakan amendment yang ada dan aturan statusnya; jangan menjanjikan amend setelah closed_short bila belum didukung.
>
> Uji masing-masing kasus tanpa pembayaran, dengan DP, dengan invoice/pembayaran parsial, retur dan reversal. Tunjukkan tabel sebelum/sesudah untuk qty order/received, total PO, nilai terima, tagihan, pembayaran, saldo utang/DP dan jurnal. Jangan otomatis mengubah semua nilai menjadi960 karena hasil terima960: basis harga/kontrak dan persetujuan selisih harus jelas. Verifikasi idempotensi retry dan periode tertutup. Bandingkan bug Finance yang sudah ditangani Wave1/2 sebelum membuat tiket tambahan.

## Fase 5 — POV sales dan meja kerja MD lintas entitas

> Kerjakan W2-REQ-04/05. Manfaatkan global_total yang sudah ada untuk POV sales available/reserved/incoming grup tanpa bocoran owner/biaya. Bedakan total grup dengan jumlah yang sudah dapat dijanjikan setelah interco. Pertahankan scope akun dan definisi ATP, jangan menjumlahkan proyeksi/incoming yang sama dua kali.
>
> MD dapat melihat kebutuhan lintas entitas yang diizinkan dan memilih badan usaha pembeli secara eksplisit per transaksi. Jangan membuang konteks entity dari backend atau membuat PO di entitas yang salah untuk menghindari switch UI. Uji SO A membutuhkan stok B, interco parsial/cancel/retry, incoming belum diterima, role sales tanpa detail owner, serta MD woven yang tidak boleh mengolah printing.

## Fase 6 — roll, cross-dock, multi-gudang dan SJ

> Kerjakan W2-REQ-08/09 dengan mendahulukan koreksi RFID-03 yang sudah ada. Semua roll wajib tag, baik untuk stock/store maupun SO/cross-dock. Uji autoencode gagal, cetak gagal, tag belum diverifikasi, salah tag, routing berubah, dispatch manual/exception dan retry. Cross-dock tidak boleh melewati GRN/QC/owner maupun menghasilkan putaway ganda. Jelaskan jalur pengecualian yang masih diizinkan beserta otorisasi dan jejaknya.
>
> Uji SO tiga produk dari tiga gudang sampai driver: picking terpisah, muatan aktual, shipment, SJ per shipment/warehouse, kekurangan salah satu gudang, pengiriman parsial, POD dan cetak ulang. Ringkasan SO tidak boleh dipakai sebagai bukti seluruh barang sudah berangkat. Dokumentasikan pilihan SOP konsolidasi dan lokasi printer; verifikasi hardware terpisah dengan operator.
>
> Untuk panjang/roll, uji9×100+1×105 dalam dua urutan, satuan yard dan meter, pembulatan naik/turun, pilihan potong bila diizinkan, backorder, harga dan qty invoice. Jangan hard-code round_down905: prefix urutan dapat900. Sampaikan total/delta dan persetujuan pengguna sebelum finalisasi.

## Paket bukti untuk validasi kembali

Setiap fase menyerahkan commit kandidat, daftar ID terkait, ringkasan perubahan, test input/expected/actual, bukti data/jurnal yang relevan dan batas yang belum diuji. UI memerlukan bukti tugas pengguna; RFID fisik memerlukan hasil perangkat. Pada tracker simpan `implementation_commits`, `implementation_evidence`, `validation_commit`, `validation_evidence` dan history. Auditor kemudian menetapkan verified_fixed/reopened/partially_fixed berdasarkan bukti, bukan klaim agent implementasi.
