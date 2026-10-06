# Pekerjaan yang masih diperlukan sebelum coverage penuh

Dokumen ini mempertahankan batas audit, bukan mencatat seluruh item sebagai bug. Tidak ada perubahan status otomatis menjadi verified_fixed dari parse/build/pass parsial.

| Kelompok | Bukti tersedia | Yang masih harus dibuktikan |
|---|---|---|
| Semua code |Hash dan parse seluruh tracked source |Semantic review setiap fungsi; 51,721 statement dan 18,018 branch belum tercatat dieksekusi |
| API mutasi |Register 772 methods |374 belum tercatat body; state-machine success/failure/retry/reversal pada seluruh methods belum lengkap |
| API baca |589 GET dipanggil |49 membutuhkan resource fixture; setiap angka consumer tetap memerlukan oracle |
| W1/W2/REQ |137 ID historis memiliki register |Pass replay lebih sempit daripada acceptance penuh; ID tanpa runtime unik current tetap dinyatakan belum terbukti |
| Browser |Build dan original-JS probes |Seluruh layar/role/entity/filter/paging/export/print/loading/error/null, termasuk angka yang terlihat di DOM |
| Rantai finance |Fault probes dan numeric source review |Seluruh closing/reversal/tax/accrual/reconciliation pada fixture deterministik dan data produksi anonim |
| Rantai WMS/RFID |Software tags/session/loading/cut/count probes |Perangkat gate/reader/printer, offline/reconnect dan operational walkthrough dengan gudang terpisah |
| Tes nonpass |Semua XML/log dan triage register |657 full-suite nonpass belum seluruhnya diberi verdict manual independen |

Register endpoint sudah menyediakan daftar konkret untuk memperluas pengujian. Pengujian lanjutan harus membuat fixture koheren dan oracle independen per lifecycle, bukan mengejar persentase dengan memanggil endpoint kosong atau menutup kegagalan yang tidak dipahami.

## Batas verifikasi browser pada sesi ini

Browser helper gagal sebelum navigasi dengan pesan `failed to write kernel assets: The system cannot find the path specified. (os error 3)`. Satu reset dan percobaan ulang memberikan error sama. Frontend/backend lokal sudah disiapkan, tetapi **DOM, screenshot, angka rendered dan navigasi UI tidak terverifikasi**. Ini kegagalan lingkungan alat, bukan temuan bug aplikasi. Bukti dua percobaan tersedia pada `latest/evidence/browser-ui-attempt.json`. Original-JavaScript probes dan API tests tetap berlaku sesuai batasnya; belum menggantikan browser/perangkat fisik.
