# WMS: penerimaan bertahap, batas roll, dan pemulihan

Tanggal 2026-10-02. Snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Source aplikasi tidak diubah. Semua fixture sintetis di Mongo lokal; service GRN asli dan indeks aplikasi dipakai. Tidak menguji browser, perangkat, maupun data produksi.

## Hasil dan cakupan

20 checkpoint skenario baru: **15 kontrol, dua reproduksi untuk satu cacat baru W2-013, dan tiga pendalaman GN-11 Gelombang 1**. Checkpoint dalam satu lifecycle saling berkaitan; angka ini bukan 20 business flow independen, bukan persentase line/branch coverage, dan bukan bukti seluruh WMS benar. Total klasifikasi W2 menjadi **99: 69 kontrol, 16 reproduksi cacat W2, enam observasi kebijakan, delapan pendalaman Gelombang 1; 13 ID W2**. Lima belas skenario AR yang belum ditriase tetap di luar total ini.

| ID W2-G | Pemeriksaan | Hasil |
|---|---|---|
| C01 | Dua roll15+25 sebelum close | Hitungan40; PO belum bertambah |
| C02 | PO100, kiriman pertama40 | GRN closed; satu task sisa60 |
| C03 | Kondisi awal task sisa | Counter penerimaan/roll nol, tidak mewarisi GRN aktif |
| C04 | Panggilan ulang pembuat task sisa | Tidak menggandakan task secara berurutan; konkurensi belum diuji |
| C05 | Kiriman kedua60 dibatalkan sebelum close | Roll kiriman kedua dihapus, counter task kembali0; dua roll pertama dan PO40 tetap |
| C06 | Kiriman pengganti: dua line20+40 untuk task sama | Posting dikelompokkan sekali; PO100 dan tidak ada task aktif sisa |
| C07 | Konservasi fisik lintas kiriman dan pembatalan | Lima roll, total100 |
| C08 | Agregasi deklarasi beberapa line | declared_qty_total task kedua60 |
| C09–C10 | DN100yard dengan supplier factor0.9144, hitung45.72+45.72meter | Konversi91.44; close sukses; PO91.44 |
| C11–C12 | Dua line60+60 pada sisa PO100 | Satu blocker over_remaining; close400; PO tetap0 |
| C13 | Supplier UOM tanpa barang supplier yang diwajibkan | Ditolak; fixture kemudian dilengkapi sebelum flow yard diuji |
| C14 |501 roll ditambahkan satu demi satu melalui service hitung | Semua diterima dan counted501 |
| C15 | Retry langsung setelah gangguan di tengah finalisasi | Kunci inbound menahan; GRN closing dan PO0 |
| F01–F02 |501 roll ditutup dan dicoba ulang | Cacat W2-013 di bawah |
| E01–E03 | Gangguan roll kedua, pelepasan kunci, retry | Pendalaman GN-11 di bawah |

## W2-013 — P1 — GRN selesai walaupun finalisasi terpotong setelah500 roll

**Lokasi dan penyebab:** [inbound_complete_service.py:110–125](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/inbound_complete_service.py#L110) mengambil roll receiving dengan `.to_list(500)`, kemudian menghitung final_qty hanya dari hasil terbatas tersebut. Loop [baris335](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/inbound_complete_service.py#L335) memfinalkan daftar itu. PO bertambah dari final_qty di baris442–463. Sementara [goods_receipt_service.py:677](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/goods_receipt_service.py#L677) mengumpulkan sampai2000 roll untuk counted, sehingga501 dapat lolos hitungan dan rekonsiliasi.

[goods_receipt_close_service.py:276–294](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/goods_receipt_close_service.py#L276) tidak memastikan seluruh roll GRN sudah terfinalkan setelah complete_task kembali. Baris389–404 menandai line done lalu GRN closed. Tidak ada pengecekan bahwa jumlah counted sama dengan jumlah yang berhasil diposting.

**Reproduksi penuh F01:** buat PO501meter, satu line DN501meter/501roll. Panggil add_counted_roll asli501 kali, masing-masing1meter. Hitungan tersimpan501roll/501meter. Finish count dan close asli mengembalikan GRN `closed`, tetapi:

- PO `received_qty=500`;
-500 roll `quarantine`, satu roll masih `receiving`;
- hanya500 movement penerimaan;
- task `qc_pending`, sementara declared/counted GRN tetap501.

**F02:** close ulang ditolak409, roll receiving tetap satu. Task sisa tidak tercipta pada fixture ini: selisih1 berada dalam toleransi pemenuhan PO2% pada ensure_remainder_task baris243–247. Toleransi itu bukan akar pemotongan; ia membuat kehilangan finalisasi lebih mudah tidak terlihat.

**Dampak terbukti:** dokumen selesai tidak merepresentasikan seluruh barang yang dihitung; satu roll tidak masuk antrean QC normal, jumlah PO dan movement kurang, dan aksi retry normal tidak menyelesaikannya. Tidak mengklaim stok fisik hilang, hardware gagal, atau sudah menguji proses QC/return terhadap roll tertinggal. Batas2000 pada counted adalah risiko lain dari pola limit, belum direproduksi dan tidak dihitung sebagai temuan tambahan.

**Prioritas P1:** silent partial posting pada dokumen yang telah dianggap selesai.501roll adalah syarat reproduksi, bukan klaim volume harian pengguna.

**Hubungan temuan:** berbeda dari RF-16 (pemotongan batch RFID ingest) dan IX-14/FN-10 (kegagalan posting GL). Ini pemotongan daftar stok saat GRN close. Perbaikan dapat berbagi desain recovery dengan GN-11, tetapi penyebab spesifik limit500 memerlukan acceptance test sendiri.

**Perbaikan:** gunakan iterator/batch yang memproses seluruh roll dengan keanggotaan receipt stabil; batasi ukuran batch internal tanpa membatasi total receipt diam-diam. Pastikan status final hanya setelah setiap efek wajib selesai dan jumlah roll/quantity yang diposting direkonsiliasi dengan manifest hitungan. Bila ada batas bisnis, validasi eksplisit sebelum mutasi dan tampilkan batas pada UI. Batas501 harus tidak pernah berakhir sebagai closed dengan500 selesai.

## GN-11 — pendalaman: pelepasan lock tidak memulihkan checkpoint penerimaan

Sumber historis: `work/KNHOST-audit/docs/audit/findings/GN-11.md`. Tidak dibuat ID baru atau diubah status Wave1; bukti tambahan ditaruh terpisah supaya agent develop dapat menggabungkannya ke fase recovery yang sedang berjalan.

**Metode E01:** dua roll asli4+6meter, PO10, DN10. Test menyisipkan satu `AutoReconnect` tepat sebelum update finalisasi roll kedua; update pertama, movement, serta operasi DB lain tetap asli. Hook dipulihkan sebelum retry. Ini simulasi gangguan deterministik, bukan pengukuran frekuensi gangguan di produksi atau pengujian putus jaringan sungguhan.

Setelah kegagalan, GRN `closing`, PO0, satu roll quarantine4 dan satu receiving6. C15 membuktikan retry langsung ditahan saga lock yang masih ada: pengunci tidak boleh dinyatakan tidak berfungsi.

Kemudian test memanggil `atomic_claim.release('wms_tasks', task_id)`, helper yang dipakai endpoint admin pelepasan lock, lalu close lagi memakai version terbaru. Test ini tidak menguji otorisasi endpoint admin atau menghapus roll/PO secara langsung.

**Hasil E02–E03:** GRN menjadi `closed`; seluruh roll fisik berjumlah10, tetapi PO hanya menerima6; task QC `quarantine_qty=6` untuk roll quarantine berjumlah10; task `qty_rolls=1` padahal ada dua roll. Sistem menciptakan task sisa4 yang sebenarnya telah diterima.

**Akar masalah:** [inbound_complete_service.py:110–125](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/inbound_complete_service.py#L110) membangun ulang unit kerja hanya dari status receiving. Roll4 yang sudah berubah ke quarantine tidak lagi masuk retry. Tidak ada catatan efek per roll/operation yang menghubungkan jumlah original receipt dengan efek PO dan QC yang belum dijalankan. Lock serialisasi mencegah tumpang tindih, tetapi setelah dilepas tidak memulihkan progress.

**Dampak:** retry menghasilkan sumber data yang saling berbeda dan instruksi sisa penerimaan palsu. Ini dasar konkret memperluas GN-11 ke GRN; bukan sekadar dugaan bahwa transaksi multi-koleksi berisiko. Tidak mengklaim telah menguji crash pada setiap tahap, ambiguous write acknowledgement, seluruh posting finansial, atau seluruh recovery admin.

**Perbaikan yang perlu dikoordinasikan:** simpan receipt operation/manifest stabil dan ledger efek yang dapat dilanjutkan; per-roll transition, movement, akumulasi PO, counter QC, dan terminal GRN harus bisa direkonsiliasi. Release lock saja bukan tanda aman untuk memulai posting dari nol. Recovery harus melanjutkan efek yang belum terjadi, menghindari penghitungan ulang yang menggandakan efek lama, serta mengungkap status parsial pada UI.

## Bukti dan batas cakupan

- [13 kontrol flow normal](grn-partial-results.json), [harness](repro/wave2_grn_partial.py).
- [501roll dan penutupan](grn-capacity-results.json), [harness](repro/wave2_grn_capacity.py).
- [Fault injection dan recovery](grn-recovery-results.json), [harness](repro/wave2_grn_recovery.py).
- [Prompt implementasi dan validasi](15_PROMPT_GRN_KAPASITAS_RECOVERY.md).

GRN-04 checklist Wave1 kini memperoleh bukti runtime untuk partial receipt dan beberapa line pada task yang sama. Tetap parsial: beberapa PO/produk/task dalam satu GRN, persetujuan selisih, packing list, OCR, supplier label, catch-weight menyeluruh, concurrency pembuat remainder, 2000+roll, crash pada semua tahap, UI/browser dan perangkat belum ditutup oleh putaran ini. Partial QC lama IX-15 juga belum dinyatakan fixed. Tidak ada klaim readiness enterprise menyeluruh dari kontrol yang lulus ini.
