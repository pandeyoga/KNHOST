# Uji fungsional WMS — konversi satuan dan kuantitas

1 Oktober 2026; snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Sesuai arahan pengguna, pengujian beralih dari Finance ke domain WMS untuk memeriksa apakah pekerjaan dapat dilanjutkan. **16 kontrol lulus**, tanpa temuan baru pada kasus yang diuji. Tidak ada error Daybreak pada hasil alat yang terlihat oleh agent. Ini bukan diagnosis penyebab pesan aplikasi, dan tidak membuktikan Finance adalah pemicu maupun menjamin pesan tersebut tidak muncul lagi.

## Metode

Fungsi aplikasi asli `uom_service` dan `uom_rules_service`, dengan master satuan dan aturan default pada MongoDB lokal sintetis terpisah. Network eksternal diblokir oleh harness. Hasil yang diharapkan ditetapkan eksplisit di [skrip](repro/wave2_wms_uom.py), observasi ada di [wms-uom-results.json](wms-uom-results.json). Tidak memodifikasi source aplikasi, menjalankan browser, atau memposting penerimaan stok lengkap.

| Skenario | Kasus | Hasil sesuai ekspektasi |
|---|---|---|
| W2-U-C01 | 10 yard → meter | 9,14 dengan presisi2 |
| W2-U-C02 | 100 cm → meter | 1 |
| W2-U-C03 | 10 inch → meter | 0,25 dengan presisi2 |
| W2-U-C04 | 2 roll, faktor50 meter/roll | 100 meter |
| W2-U-C05 | 100 meter → roll, faktor50 | 2 roll |
| W2-U-C06 | 3 kg, GSM200, lebar1,5m | 10 meter |
| W2-U-C07 | 10 meter, spesifikasi sama | 3 kg |
| W2-U-C08 | Alias uppercase YRD → MTR | 10 → 9,14 |
| W2-U-C09 | 3 dozen → piece | 36 |
| W2-U-C10 | 100 yard → meter → yard | Kembali100 |
| W2-U-C11 | Berat per base unit yard | 0,27432 kg |
| W2-U-C12 | Roll tanpa faktor konversi | Ditolak dengan UomRuleError |
| W2-U-C13 | Selisih aktual1%, warn2/block5 | ok |
| W2-U-C14 | Selisih aktual2% | warn |
| W2-U-C15 | Selisih aktual5% | block |
| W2-U-C16 | Jejak konversi2 roll →100 meter | qty, faktor50, sumber product_override konsisten |

## Cakupan dan batas

Ini kontrol mesin satuan, bukan kelulusan seluruh WMS. Belum menguji seluruh master kustom, panel per dokumen, perubahan aturan historis, data penerimaan multi-roll, bin/putaway, atau propagation hasil konversi ke setiap flow. IX-13 Gelombang1 mengenai caller penerimaan manual tetap terpisah: core engine yang benar tidak membuktikan seluruh pemanggil memakainya dengan benar.

Setelah16 kontrol baru ini, cakupan yang sudah diklasifikasikan Gelombang2 menjadi **79 skenario:54 kontrol,14 reproduksi cacat W2,6 observasi kebijakan,5 pendalaman Gelombang1; 12 ID temuan**. Replay review W2-05 tidak dihitung ulang.

Pengujian AR yang sempat berjalan sebelum perpindahan domain selesai dan menyimpan15 hasil di `ar-results.json`; bukti itu dipertahankan tetapi **belum masuk total79 dan belum diberi ID temuan baru**, karena review serta laporan Finance ditunda ketika pengguna mengalihkan fokus ke domain lain. Tidak ada klaim bahwa temuan Finance sudah final.
