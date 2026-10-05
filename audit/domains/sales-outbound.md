# Domain sales-outbound

Status otoritatif: [tracker.json](../tracker.json). Tabel ini indeks ID statis, bukan salinan status.

| ID | Prioritas | Fase | Temuan |
|---|---|---|---|
| [AX-01](../findings/AX-01.md) | P1 | [P07](../phases/P07.md) | Roll yang dipindai tidak menjadi identitas yang wajib dikirim |
| [AX-03](../findings/AX-03.md) | P1 | [P07](../phases/P07.md) | Claim bergantian masih membolehkan progres partial shipment ditimpa |
| [CX-11](../findings/CX-11.md) | P1 | [P07](../phases/P07.md) | Retur dua baris produk yang sama memakai harga baris terakhir |
| [CX-12](../findings/CX-12.md) | P1 | [P07](../phases/P07.md) | Pengiriman pertama menutup special order sebelum pengiriman lain selesai |
| [GN-11](../findings/GN-11.md) | P1 | [P07](../phases/P07.md) | Saga release menghapus lock tanpa mengecek efek yang sudah terposting |
| [RF-04](../findings/RF-04.md) | P1 | [P07](../phases/P07.md) | Final Loading Check belum menjadi prasyarat dispatch |
| [RF-05](../findings/RF-05.md) | P1 | [P07](../phases/P07.md) | Loading Check clean walaupun sebagian roll tidak punya tag |
| [RF-06](../findings/RF-06.md) | P1 | [P07](../phases/P07.md) | Hasil loading melekat pada SO, tidak pada versi shipment aktual |
| [WM-06](../findings/WM-06.md) | P1 | [P07](../phases/P07.md) | Scan picking tidak memvalidasi identitas roll dan menerima qty negatif |
