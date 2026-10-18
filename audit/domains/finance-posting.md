# Domain finance-posting

Status otoritatif: [tracker.json](../tracker.json). Tabel ini indeks ID statis, bukan salinan status.

| ID | Prioritas | Fase | Temuan |
|---|---|---|---|
| [AX-02](../findings/AX-02.md) | P1 | [P03](../phases/P03.md) | Task dispatch dianggap selesai sebelum surat jalan tersimpan |
| [CX-01](../findings/CX-01.md) | P1 | [P03](../phases/P03.md) | Penebusan store credit dapat melampaui nominal permintaan dan saldo |
| [CX-03](../findings/CX-03.md) | P1 | [P03](../phases/P03.md) | Gagal posting store credit meninggalkan AR terbayar tetapi kredit belum terpotong |
| [CX-04](../findings/CX-04.md) | P1 | [P03](../phases/P03.md) | Retry pencairan uang muka membuat transaksi kas keluar kedua |
| [CX-05](../findings/CX-05.md) | P1 | [P03](../phases/P03.md) | Uang muka yang telah selesai dapat dipertanggungjawabkan penuh lagi |
| [CX-06](../findings/CX-06.md) | P1 | [P03](../phases/P03.md) | Manual bank matching menerima arah dan rekening yang tidak cocok |
| [CX-07](../findings/CX-07.md) | P1 | [P03](../phases/P03.md) | Split bank reconciliation menghitung target yang sama lebih dari kapasitasnya |
| [CX-08](../findings/CX-08.md) | P1 | [P03](../phases/P03.md) | Reschedule cicilan mengubah arti referensi pembayaran historis |
| [FN-07](../findings/FN-07.md) | P1 | [P03](../phases/P03.md) | Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal |
| [FN-08](../findings/FN-08.md) | P1 | [P03](../phases/P03.md) | Opening balance rekening dan perubahan rekening tidak tersambung GL |
| [FN-10](../findings/FN-10.md) | P1 | [P03](../phases/P03.md) | Pembayaran AR dapat sukses walau jurnal kas gagal |
| [FN-12](../findings/FN-12.md) | P1 | [P03](../phases/P03.md) | Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan |
| [FN-15](../findings/FN-15.md) | P2 | [P03](../phases/P03.md) | Helper autopost tidak menegakkan invariant jurnal di pintu insert |
| [IX-14](../findings/IX-14.md) | P1 | [P03](../phases/P03.md) | GRN dinyatakan closed walau jurnal penerimaan gagal |
| [IX-17](../findings/IX-17.md) | P1 | [P03](../phases/P03.md) | Retur menjadi approved dan mengubah stok/AP sebelum jurnal ditolak |
