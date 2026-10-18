# Domain security-scope

Status otoritatif: [tracker.json](../tracker.json). Tabel ini indeks ID statis, bukan salinan status.

| ID | Prioritas | Fase | Temuan |
|---|---|---|---|
| [AX-04](../findings/AX-04.md) | P1 | [P01](../phases/P01.md) | Transfer roll eksplisit melewati owner filter dan rebuild balance |
| [AX-06](../findings/AX-06.md) | P1 | [P01](../phases/P01.md) | Print job multi-owner membocorkan item melalui owner header pertama |
| [CX-02](../findings/CX-02.md) | P1 | [P01](../phases/P01.md) | Store credit dapat dialokasikan ke pelanggan atau badan usaha yang berbeda |
| [CX-10](../findings/CX-10.md) | P1 | [P01](../phases/P01.md) | E-sign tidak terikat pada versi dokumen yang ditampilkan |
| [GN-01](../findings/GN-01.md) | P1 | [P01](../phases/P01.md) | Idempotency tidak terikat user cookie, entitas dan payload |
| [GN-02](../findings/GN-02.md) | P1 | [P01](../phases/P01.md) | WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope |
| [GN-03](../findings/GN-03.md) | P1 | [P01](../phases/P01.md) | Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen |
| [GN-04](../findings/GN-04.md) | P1 | [P01](../phases/P01.md) | R&D dapat mengambil bahan dari roll badan usaha lain |
| [GN-09](../findings/GN-09.md) | P1 | [P01](../phases/P01.md) | CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID |
| [GN-10](../findings/GN-10.md) | P2 | [P01](../phases/P01.md) | Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global |
| [GN-16](../findings/GN-16.md) | P1 | [P01](../phases/P01.md) | Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas |
| [IX-05](../findings/IX-05.md) | P1 | [P01](../phases/P01.md) | Metadata e-sign lintas badan usaha dapat dibaca lewat HTTP |
| [IX-06](../findings/IX-06.md) | P2 | [P01](../phases/P01.md) | Edit payroll settings dari entitas A mengubah konfigurasi efektif B |
| [IX-07](../findings/IX-07.md) | P1 | [P01](../phases/P01.md) | Pengaturan Finance entitas lain dapat diubah melalui scope |
| [IX-10](../findings/IX-10.md) | P1 | [P01](../phases/P01.md) | Baca dan keputusan buka periode tidak memeriksa penugasan entitas |
| [RF-08](../findings/RF-08.md) | P1 | [P01](../phases/P01.md) | Sesi dan histori Cycle Count RFID tidak terisolasi entitas |
| [RF-09](../findings/RF-09.md) | P2 | [P01](../phases/P01.md) | Cycle count lintas entitas dibuat tetapi tidak dapat dipindai |
| [RF-12](../findings/RF-12.md) | P1 | [P01](../phases/P01.md) | Daftar device membocorkan API key hardware |
| [RF-13](../findings/RF-13.md) | P1 | [P01](../phases/P01.md) | Device dinonaktifkan masih diterima autentikasi |
