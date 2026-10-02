# Domain inventory-core

Status otoritatif: [tracker.json](../tracker.json). Tabel ini indeks ID statis, bukan salinan status.

| ID | Prioritas | Fase | Temuan |
|---|---|---|---|
| [AX-05](../findings/AX-05.md) | P1 | [P02](../phases/P02.md) | Penerimaan transfer menghilangkan asal PO dan membawa bin gudang lama |
| [AX-07](../findings/AX-07.md) | P2 | [P02](../phases/P02.md) | Potongan generasi kedua mencatat kakek sebagai parent langsung |
| [FN-03](../findings/FN-03.md) | P1 | [P02](../phases/P02.md) | WAC menjumlah panjang dan cost lintas unit tanpa konversi |
| [GN-12](../findings/GN-12.md) | P2 | [P02](../phases/P02.md) | Agregasi kritis berhenti pada batas to_list tanpa penanda truncation |
| [GN-13](../findings/GN-13.md) | P2 | [P02](../phases/P02.md) | Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit |
| [GN-15](../findings/GN-15.md) | P3 | [P02](../phases/P02.md) | Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten |
| [IX-13](../findings/IX-13.md) | P1 | [P02](../phases/P02.md) | Konversi hitung manual penerimaan menyimpang dari mesin UOM utama |
| [WM-01](../findings/WM-01.md) | P1 | [P02](../phases/P02.md) | Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil |
| [WM-02](../findings/WM-02.md) | P1 | [P02](../phases/P02.md) | Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik |
