# Checklist UAT dan keputusan operasional

Setiap baris memerlukan kandidat SHA, role, entity/line, input, expected, actual, evidence dan status. Belum diuji secara menyeluruh oleh paket ini.

|Poin klien|Acceptance tugas pengguna|
|---|---|
|1|Wiwi/Tita dengan akun terpisah: histori jelas, lini woven tidak dapat mengolah printing; input atas nama pelaksana lain dapat dibedakan bila SOP membutuhkannya.|
|2/12|Benang/grey/PFD/PFP/finished tidak bercampur; master lama bermasalah muncul di daftar koreksi, bukan otomatis digabung.|
|3|Bahan dapat dibuat langsung; SKU MD tidak rilis sebelum uji wajib sesuai lini ACC; retry pembentukan SKU tidak menduplikasi.|
|4|Sales melihat total grup tanpa owner; SO A memakai stok B lewat proses internal yang sah; reserved/incoming tidak dihitung ganda.|
|5|MD memilih buyer yang benar tanpa kehilangan konteks SO/PR; lini dan izin tetap dibatasi.|
|6|10roll datang960 dari1000: MD mengetahui selisih, memilih tunggu/revisi/tutup; dokumen dan pembayaran direkonsiliasi.|
|7|Dua kebutuhan produksi tidak sama-sama menjanjikan greige yang sama; reserve berbeda dari issue fisik; cancel/replan terukur.|
|8|Supplier lot dikoreksi dengan internal lot stabil; label, roll dan genealogy dapat ditelusuri.|
|9|Roll/yard tampil konsisten,9×100+105 diuji dua urutan, delta dan pilihan potong/pembulatan jelas.|
|10|Tiga gudang menyerahkan barang yang benar kepada driver; SJ sesuai shipment aktual, partial dan cetak ulang tidak mengaku seluruh SO terkirim.|
|11|Store dan cross-dock sama-sama tag/QC sesuai aturan, tidak ada putaway ganda; tag/reader/printer gagal menghasilkan tindakan yang jelas.|

Keputusan terbuka: standar nama perusahaan, alias kode warna customer jika diperlukan, pihak pembeli per kebutuhan, kapan komitmen rencana mengunci bahan, kebijakan toleransi/penutupan PO, izin potong roll, konsolidasi SJ serta printer. Catat pilihan, alasan, pemilik keputusan dan tanggal. Jangan mengubah pertanyaan ini menjadi asumsi terselubung. Arti C/H tidak diperlukan untuk menguji kebutuhan yang telah diklarifikasi.

Finance: rekonsiliasi AR/AP/deposit/kas/stok/WIP/GL menggunakan dataset yang disetujui. Akurasi BPJS/PPh/pajak membutuhkan aturan dan data acuan tersendiri. Hardware: reader/tag nyata, arah lewat, printer, offline/reconnect, alarm serta SOP operator. Browser: pemilihan entity/line, scan focus, error/retry, jumlah/unit dan cetak dokumen. Kelulusan backend tidak menggantikan hasil ini.
