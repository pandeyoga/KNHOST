# Baseline dan hubungan dengan pekerjaan sebelumnya

Acuan yang benar adalah snapshot `64d81f29577dae4daa86ddc64689dec7243804f2`, bukan copy plan awal yang seluruh statusnya masih kosong. Commit tersebut bertanggal 14 Oktober 2026. Tidak dilakukan klaim pengambilan HEAD remote terbaru untuk penyusunan paket ini.

| Fase lama | Status pada snapshot | Penempatan pekerjaan gelombang baru |
|---|---|---|
| P00 | in_progress | L00: rekonsiliasi baseline/data UAT dan status belum selesai. |
| P01 | implemented_pending_validation | L01/L04/L06: validasi role/master/stage/supplier; koreksi PFD/PFP, grade dan UOM. |
| P02 | implemented_pending_validation | L07/L10: pertahankan struktur/rules/putaway lalu perluas sesuai perjalanan aktual. |
| P03 | implemented_pending_validation | L04/L07: receipt aktual, OCR, transfer, selisih dan konsolidasi. |
| P04 | implemented_pending_validation | L02/L03: alokasi/Keep/Pending/harga; hapus asumsi harga semua non-BS sama. |
| P05 | implemented_pending_validation | L03/L04/L05: revalidation, MDQ dan makloon; review open issue P05 dan sumber restock default. |
| P06 | not_started | L03: Special Order/desain multi-produk, ditambah klarifikasi terbaru. |
| P07 | not_started | L06: sampel/Admin Cutting, ditambah catalogue dan ecer. |
| P08 | not_started | L10: opname/dashboard/Meja User, dengan dampak L05/L11. |
| P09 | not_started | L13: absensi, hardware dan kebijakan HR masih pending. |
| P10 | not_started | L14: integrasi/UAT, mencakup seluruh perluasan dan RFID nyata. |

P05 dinyatakan implementasinya selesai oleh report developer, tetapi validasi owner belum tuntas. Status acceptance lama juga campuran; PASS pada commit lama harus ditinjau dampak dan diuji ulang bila kontraknya berubah.

Empat keterbatasan yang tercantum pada report P05 adalah retur material hanya keseluruhan step, akses retur bahan desktop, potensi race existing-SKU revalidation, dan label “ACC spesifikasi” pada revalidation. L00 memeriksa reproduksi dan L03/L04 menangani yang relevan. Ini catatan baseline, bukan klaim telah dites ulang dalam penyusunan plan.

## Keputusan terbaru yang menggantikan asumsi lama

| Catatan lama | Keputusan yang berlaku untuk rencana ini |
|---|---|
| Greige, PFD dan PFP semuanya tersembunyi dan tidak bisa dijual | Greige tidak untuk customer; PFD/PFP boleh dijual dengan konfigurasi dan daftar yang jelas. |
| Harga semua grade selain BS sama | Harga dapat berbeda antar-grade; Special Order mengacu grade A dan bisa meminta Special Price. |
| Sumber restock menjadi hard block jalur lain | Menjadi default/rekomendasi, bukan larangan mutlak. |
| Cutloss sudah mempunyai arti operasional tertentu | Belum final. Contoh 120 yard harus dijawab client sebelum implementasi cabang final. |
| Pengganti mungkin boleh ganti warna/grade | Pengganti artikel, warna dan grade sama dengan barang yang dijual. |
| Deadline supplier berdasarkan tanggal PO atau satu tanggal gabungan | Awal 21 hari dari penerimaan gudang per receiving. End-event deadline masih pending. |
| QC retur dapat dilakukan pada semua lokasi | Saat ini di Rancamalang; Jakarta dapat menerima lalu mengirim ke area transit QC Rancamalang. |
| Gudang diberi nama per entitas di Rancamalang | Shared warehouse kategori; owner adalah atribut berbeda dari posisi fisik. |
| Supplier return memilih PO produk terakhir | Wajib provenance roll asli sampai receiving/PO dan SO terkait. |
| Manual middleware berarti semua endpoint ERP tersedia | Asumsi itu hanya untuk manual middleware; parity ERP tetap dibuktikan. |

Kode L00–L14 sengaja berbeda dari P00–P10 agar status lama tidak tertimpa. Implementasi yang sudah benar dipakai kembali dan diverifikasi, bukan dibangun ulang. Untuk audit wave 1, 2 dan 3, rujuk tracker audit masing-masing di repo; paket ini tidak menyatakan audit tersebut telah ditutup.

## Aturan prioritas sumber

1. Jawaban owner paling baru pada topik yang sama, termasuk 13 jawaban retur.
2. Keputusan jelas dari pembahasan 16 Oktober.
3. Register historis 126 statement untuk konteks yang belum digantikan.
4. Rencana lama dan dokumen middleware sebagai referensi teknis sesuai batas snapshot.
5. Usulan analisis diberi label usulan; tidak berubah menjadi keputusan bisnis hanya karena ditulis dalam plan.

Contoh: RT-12 historis ditandai jelas, tetapi jawaban R-01 terbaru menempatkan cutloss sebagai pending. Jawaban terbaru yang dipakai. Status `clarity=J` tidak pernah berarti fitur sudah benar atau tes sudah lulus.
