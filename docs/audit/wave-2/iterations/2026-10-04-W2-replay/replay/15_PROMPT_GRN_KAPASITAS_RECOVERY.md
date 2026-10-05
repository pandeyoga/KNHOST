# Prompt perbaikan WMS — koordinasi Wave2 dan Wave1

Gunakan source kandidat terbaru milik agent develop; bukti audit di snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Jangan menimpa perbaikan agent lain. Status siap validasi memerlukan commit dan hasil aktual; validator terpisah menentukan verified_fixed.

## Fase A — W2-013: kelengkapan finalisasi receipt

Perbaiki pemotongan roll pada backend/services/inbound_complete_service.py:110–125 dan kontrak penutupan goods_receipt_close_service.py:276–404. Baca 14_UJI_GRN_PARSIAL_KAPASITAS_RECOVERY.md dan jalankan repro/wave2_grn_capacity.py sebelum perubahan. Saat ini501 roll masing-masing1meter dihitung dan diterima, namun close berstatus closed dengan hanya500 quarantine/movement/received_qty PO dan satu receiving; retry409. Hilangkan silent total cap500 menggunakan iterator atau batch berkelanjutan dengan manifest stabil. Jangan sekadar mengganti500 menjadi angka lebih besar. Periksa cap2000 pada refresh_counted dan konsistensi daftar yang ditampilkan, tanpa menyatakan bug tambahan sebelum bukti.

Pastikan closed/done mensyaratkan seluruh roll dan efek yang diwajibkan selesai. Jika batas bisnis diperlukan, tolak eksplisit sebelum perubahan stok dan sediakan feedback UI yang jelas. Uji499/500/501, beberapa batch, beberapa line/task, receipt parsial, pembatalan, dan retry; jumlah counted, roll final, movement serta received_qty harus konsisten, dan tidak ada receiving tertinggal setelah close. Pertahankan kontrol normal pada wave2_grn_partial.py. Simpan evidence baru terpisah; jangan menimpa JSON audit. Isi implementation_commits dan implementation_evidence W2-013, lalu ready_for_validation. Temuan bukan fixed hanya karena reproducer cacat menjadi gagal: tulis regression tests yang mengharapkan perilaku benar.

## Fase B — koordinasikan dengan pemilik GN-11, jangan buat tiket duplikat

Elaborasi recovery inbound_complete menggunakan bukti repro/wave2_grn_recovery.py. Dua roll4+6 dengan kegagalan sebelum update roll kedua meninggalkan quarantine4/receiving6 dan PO0. Retry ditahan lock sebagaimana mestinya. Setelah helper pelepasan lock dipakai dan retry berjalan, GRN closed tetapi PO6, quarantine_qty6 untuk fisik10, qty_rolls1 untuk dua roll, dan task sisa4 palsu.

Audit checkpoint seluruh efek dalam complete_task. Tetapkan manifest receipt yang tetap lintas retry, idempotency key per efek, serta resume/reconcile yang membedakan selesai/belum/hasil ambigu. Jangan memakai roll berstatus receiving sebagai satu-satunya rekonstruksi receipt yang sudah sebagian diposting. UI pemulihan harus menunjukkan progress/error dan aksi yang benar; pelepasan lock tidak boleh memberi ilusi bahwa seluruh efek aman diulang. Selaraskan dengan perbaikan GN-11 yang sudah berlangsung dan W2-013; pertahankan pengunci serialisasi.

Uji gangguan sebelum/sesudah tiap transisi roll, movement, update PO, rebuild proyeksi, counter QC, dan status akhir. Uji retry berulang termasuk setelah sebagian efek selesai. Sesudah pemulihan, dua roll10 harus konsisten dengan PO10/QC10 tanpa task sisa palsu, movement ganda atau duplikasi receipt. Uji mekanisme admin lewat API berotorisasi sebagai tambahan; harness audit sebelumnya hanya memanggil helper release. Tempatkan bukti di paket validasi GN-11 dan rujuk bukti Wave2 ini; jangan mengubah status tracker Wave1 secara otomatis dari pekerjaan Wave2.
