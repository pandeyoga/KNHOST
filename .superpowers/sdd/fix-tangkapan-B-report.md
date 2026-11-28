# Perbaikan tangkapan B (layar) — laporan

Dasar 77d160c (worktree awalnya di 50df890 yang lebih lama; di-reset ke 77d160c).

1. Kalimat tunai kwitansi — `ReceivePaymentModal.jsx`: fungsi baru `kalimatTunai`; rekening terpilih → "<Cara bayar> → masuk <nama> (<Kas Kasir|Kas Kecil|Kas Besar>)." (label dari `judulJenisKas`), belum terpilih → "… → masuk rekening tunai PT yang dipilih.". `ReceiptPaymentFields.jsx` kini mengirim `accountName` dan `cashType` lewat `onState`. Non-tunai tidak diubah.
2. Alasan isi ulang — `DanaTetapView.jsx`: span alasan `whitespace-normal break-words text-left` (pola BarisAksi).
3. Jejak — `DocPreviewModal.jsx`: Jejak memanggil `openTrace` lalu `onClose`. Satu-satunya pemasang `DocPreviewModal` adalah `DocPreviewHost`; tidak ada pemanggil yang mengandalkan pratinjau tetap terbuka.

Uji: pmt4TitipanSales (+uji kasir/kas kecil/belum terpilih), mejaG2DocPreview (onClose pada Jejak), kb3DanaTetap (kelas pembungkus). Jest terarah: 10 suite / 123 uji lulus, ditambah 17 suite / 182 uji (lb8MejaHp, tanggalBawaanWib, mejaKonfirmasiPajak, mejaDeskFrame, latihV9, mejaG2*, crt5MejaKredit) lulus. eslint 0 galat (4 peringatan lama). Tidak ada `scripts/verify_*` untuk layar frontend (hanya API/data), tidak dijalankan.
