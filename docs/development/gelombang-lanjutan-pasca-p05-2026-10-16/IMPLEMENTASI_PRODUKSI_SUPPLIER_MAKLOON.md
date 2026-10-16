# Implementasi rute produksi supplier dan makloon

ERP Kain Nussantara · Produksi IT PT Kubus Teknologi Indonesia  
Revisi paket 1.2 · 16 Oktober 2026 · Requirement LN-033 dan LN-143

## Mandat dan batas validasi

Owner telah meminta kekurangan integrasi supplier/makloon ditambahkan untuk diimplementasikan. Dokumen ini adalah spesifikasi target, bukan keterangan bahwa fitur telah tersedia atau pengujian ERP telah lulus. Baseline pemeriksaan kode adalah commit `64d81f29577dae4daa86ddc64689dec7243804f2`; L00 tetap harus membandingkan HEAD aktual sebelum edit.

Perubahan ini menghubungkan kemampuan existing. Jangan membangun mesin produksi kedua, mengubah seluruh R&D menjadi pesanan produksi, atau menyamakan persetujuan desain, pengujian kain, pelepasan master dan realisasi pengadaan. Topik pending lama tidak dijawab oleh addendum ini.

## Bukti kondisi baseline

| Bagian | Temuan kode dan dampak |
|---|---|
| `backend/services/rnd_spec_service.py`, `release_product`, sekitar 394–433 | Melepas lifecycle produk setelah guard; tidak membuat PO/MKO. Label frontend berbunyi rilis ke produksi/boleh dijual. |
| `backend/services/special_order_phase2.py`, `auto_procure`, sekitar 281–378 | Membuat PR tanpa fulfillment_mode sehingga default purchase, lalu convert_to_po ke supplier pemenang; menyimpan linked_po_id. Tidak memiliki percabangan realisasi MKO. |
| File yang sama, sekitar 263–271 | Kegagalan pengadaan disimpan sebagai procurement_error setelah harga terkunci. UI harus membedakan harga sah dan pengadaan gagal. |
| File yang sama, sekitar 295–308 | Exception saat release_product memiliki fallback update lifecycle langsung. Guard pengujian/spesifikasi tidak boleh dilewati melalui jalur pengadaan baru maupun lama. |
| `backend/routers/special_orders.py`, create-pr, sekitar 708–767 | Jalur manual PR Pesanan Khusus juga tidak mengisi fulfillment_mode. Mematikan auto_po saja belum menyelesaikan integrasi. |
| `backend/schemas.py`, PurchaseRequisitionItem, sekitar 939–947 | fulfillment_mode default purchase. |
| `backend/services/pr_sourcing_service.py`, realize_to_makloon, sekitar 670–719 | Sudah memiliki realisasi PR makloon, hubungan order, validasi produk hasil dan transfer reservasi bahan. Reuse fondasi ini. |
| `backend/services/restock_source_service.py`, check_lines, sekitar 43–73 | Baseline menolak purchase untuk master makloon, dan both tanpa alasan. Selaraskan LN-013: sumber master adalah default yang dapat diubah sesuai wewenang, bukan larangan mutlak. |
| `frontend/src/features/sales/SpecialOrderShippingPanel.jsx`, sekitar 14 | Panel mensyaratkan linked_po_id; harus melayani MKO tanpa membuat PO fiktif. |
| `backend/services/qc_service.py`, sekitar 405–418 | Kelanjutan Pesanan Khusus mencari find_one berdasarkan product_id dan status. Korelasi tersebut tidak cukup saat beberapa pesanan memakai SKU sama. |

Nomor baris merupakan petunjuk snapshot. Agent wajib mencatat fungsi, route dan baris aktual pada laporan implementasi. Pemeriksaan kode ini tidak mengklaim bahwa semua jalur manual alternatif mustahil; yang harus diperbaiki ialah integrasi yang eksplisit dan dapat ditelusuri.

## Alur bisnis target

### R&D internal tanpa Pesanan Khusus

R&D → pengujian relevan sesuai lini → persetujuan spesifikasi/final → rilis master. Tidak otomatis membuat kebutuhan pembelian atau makloon tanpa permintaan pengadaan yang sah. Ketika kebutuhan restock/produksi kemudian dibuat, gunakan sumber default master dan mekanisme PR existing. Revalidation SKU existing mempertahankan identitas SKU.

### Pesanan Khusus

1. Request per item mencatat sumber induk/artwork/referensi customer, qty dan unit yang diminta.
2. Designer dan PIC menjalankan flow existing. Paper tetap checklist round untuk jalur yang relevan. Label Special Order/redesign tetap tersedia.
3. Pengujian kain mengikuti lini: proofing printing atau labdip/handfeel sesuai aturan; ACC customer dicatat Sales. Revisi tidak menghilangkan histori.
4. Setelah syarat uji, spesifikasi, master dan persetujuan yang relevan sah, tampilkan sumber pemenuhan per item. Default berasal dari master. User berwenang dapat memilih supplier atau makloon; perubahan dan alasan tercatat. Jika data master belum lengkap, tampilkan kebutuhan melengkapi data, jangan diam-diam memilih purchase.
5. Harga jual mengikuti Grade A/induk atau PIC Special Order sesuai keputusan existing; Special Price tetap proses terpisah. Validasi prasyarat pengadaan/approval existing, termasuk harga bila diwajibkan, sebelum realisasi. Mengunci harga tidak boleh dianggap pengadaan berhasil.
6. Supplier: PR purchase → PO barang jadi → penerimaan actual per roll → kualitas yang berlaku → stok eligible untuk alokasi.
7. Makloon: PR makloon → MKO dengan produk hasil, partner, bahan, tahap dan estimasi → reservasi bahan → pengeluaran bahan sah → proses partner → penerimaan hasil actual → kualitas yang berlaku → stok eligible untuk alokasi.
8. Kedua jalur menghubungkan hasil ke item kebutuhan yang benar, lalu SO pemenuhan → alokasi → picking → validasi transit → SJ/dispatch → pengiriman customer mengikuti L07. Jangan membuat SO kedua jika linked SO sudah ada.

MKO = order makloon. PO bahan pendukung yang memang diperlukan tetap boleh mengikuti mekanisme existing; larang PO barang jadi palsu yang dibuat hanya agar integrasi makloon bisa lewat.

Rilis master tidak mengurangi greige. Reservasi mengurangi ketersediaan untuk kebutuhan lain sesuai kontrak L04, bukan saldo fisik. Pengeluaran fisik hanya melalui issue yang sah. Output forecast tidak boleh menjadi stok atau menggantikan receiving actual.

## Navigasi, input, proses dan output

Nama berikut adalah navigasi target; agent wajib menemukan dan melaporkan route aktual, bukan mengasumsikannya sudah ada.

| Langkah | Layar dan input | Proses/output |
|---|---|---|
| Lihat kesiapan | Pesanan Khusus → Detail → item | Uji, persetujuan, SKU, harga dan kebutuhan tersisa terlihat terpisah. Alasan belum dapat direalisasi harus jelas. |
| Pilih pemenuhan | Detail item → Pemenuhan produksi | Jalur default, jalur dipilih, sumber default, partner/supplier dan alasan perubahan; pilih per item, bukan satu dropdown global untuk semua produk. |
| Supplier | Tinjau/buka PR dan PO | Qty/unit/produk/supplier/entitas/harga pengadaan diverifikasi; tampilkan nomor dan tautan dokumen yang dihasilkan. |
| Makloon | Tinjau/buka realisasi PR dan MKO | Data bahan, ketersediaan, reservasi, partner, tahap, yield estimasi dan produk hasil berasal dari modul existing. Data belum lengkap membuka form existing untuk dilengkapi; jangan mengarang recipe atau qty bahan. |
| Pantau | Detail → daftar pengadaan per item | Tampilkan semua PR/PO/MKO, qty direncanakan, diterima, eligible, dialokasikan dan terkirim dengan unit. Tidak cukup menampilkan satu linked_po_id. |
| Terima | Receiving supplier atau hasil makloon | Nomor dokumen asal dan line menjadi referensi; actual per roll, identitas/tag, owner, lokasi dan kualitas ditangani L04/L05. |
| Kirim | SO pemenuhan/WMS | Panel mendukung kedua jenis sumber. Semua syarat alokasi dan pengiriman existing tetap berlaku; tidak memerlukan PO untuk hasil MKO. |

Pisahkan status rilis produk, kemajuan pengadaan, produksi makloon, penerimaan, kualitas dan fulfillment. Dokumen PO yang baru dibuat cukup berarti pengadaan telah direalisasi, bukan pabrik telah memulai pekerjaan. Status agregat diturunkan dari seluruh item, tidak diubah menjadi ready oleh satu item selesai. Pertahankan kompatibilitas status existing dengan pemetaan terdokumentasi, jangan sekadar mengganti string global.

## Kontrak data dan layanan yang wajib diselesaikan

Nama field berikut konseptual. L00/implementer wajib memetakan ke schema existing atau mencatat migrasi yang diperlukan sebelum coding, tanpa membuat source of truth kedua.

| Konsep | Data minimum dan aturan |
|---|---|
| Identitas kebutuhan | Special Order ID + item ID stabil, produk/SKU hasil, approved spec/test revision, entitas, qty/unit, linked SO + SO line jika sudah terbentuk. |
| Keputusan rute | purchase atau makloon, default master yang digunakan, pilihan final, pelaku/waktu/alasan/version. Identitas supplier pemenang pengujian tidak otomatis menentukan jenis kontrak pengadaan. |
| Realisasi | PR + PR line → PO + PO line atau MKO + output/product line. Satu kebutuhan dapat memiliki beberapa realisasi parsial; simpan jumlah tercakup/tersisa dan pembatalan. |
| Bahan | Referensi reservasi/issue/return/consumption milik layanan material existing. Tidak membuat ledger reservasi lokal khusus OD. |
| Hasil | Receiving document + line + roll IDs dan qty actual, status kualitas, sumber produksi dan entitas pemilik. |
| Alokasi | Hubungan hasil eligible ke SO line melalui layanan alokasi existing; jangan pilih pesanan dengan find_one berdasarkan SKU saja. |
| Retry | Identitas operasi/idempotency untuk kebutuhan dan versi/realisasi yang sama, claim atomik atau mekanisme ekuivalen existing, serta recovery setelah partial failure. |

Perbarui create-pr manual, auto-procure, retry dan UI agar semuanya menggunakan layanan routing yang sama. Validasi input dan hak dilakukan di backend; UI hanya membantu input. Untuk permintaan lama yang tidak membawa rute, resolve secara aman dari relasi/default yang sah, atau kembalikan kebutuhan melengkapi data; jangan menyimpan ulang sebagai purchase tanpa evaluasi.

Sebelum implementasi, hasilkan tabel route/API aktual berisi method/path, permission, request/response, perubahan schema dan error. Lengkapi operasi memilih/mengubah rute, realisasi, baca progress, pembatalan/amandemen, dan callback receipt/QC. Tidak diwajibkan membuat endpoint baru bila operasi existing dapat diperluas dengan kompatibel.

Callback hasil wajib membawa atau menurunkan korelasi dokumen/line yang deterministik. Dokumen legacy yang ambigu harus masuk antrian rekonsiliasi, tidak dipasangkan otomatis berdasarkan SKU. Event duplicate tidak menambah stok, task outbound atau alokasi dua kali. Kegagalan satu operasi menyimpan error dan relasi yang sudah berhasil; retry melanjutkan tanpa membuat ulang dokumen.

## Guard dan dampak antar modul

- Gagal release_product tidak boleh diteruskan dengan update lifecycle langsung. Bedakan error bisnis dari gangguan teknis; keduanya tidak mengesahkan bypass uji/approval. Override existing hanya sah bila eksplisit, berwenang dan diaudit.
- Sebelum ada realisasi, perubahan rute memperbarui rencana dengan audit. Sesudah PR/PO/MKO aktif, gunakan pembatalan/amandemen existing dan rekonsiliasi kebutuhan. Sesudah issue atau receipt, jangan hapus transaksi untuk mengganti rute.
- Semua aksi mengikuti custom role dan scope entitas/lokasi. Hak memilih sumber berbeda dari hak merilis master, mengunci harga, merealisasi pengadaan atau membatalkan. Tidak hardcode nama staf.
- Hak override default restock tidak mengesampingkan guard kualitas, stock, transaksi, approval, maupun kepemilikan entitas.
- MD Quality tidak disamakan dengan QC inspect. Pengujian receiving yang berlaku tetap dilalui; request QC customer tetap dipertahankan. Addendum tidak menentukan formula inspect yang masih pending.
- Harga beli output supplier, biaya bahan sendiri, biaya jasa makloon dan harga jual customer berbeda. Reuse posting existing dan dokumentasikan kapan AP/AR/inventory/HPP dipengaruhi; rilis master atau perubahan status OD tidak boleh menjadi event akuntansi tambahan.
- Perbedaan qty hasil terhadap forecast memunculkan sisa kebutuhan; tindak lanjut memakai amandemen/penutupan/permintaan tambahan existing. Jangan menciptakan toleransi variance baru yang sebelumnya ditolak owner.
- Warehouse shared tidak mengubah owner. Supply lintas entitas tetap melalui transaksi internal existing; jangan memenuhi SO entitas lain hanya karena stok berada di gudang yang sama.

## Migrasi dan urutan implementasi

1. L00: rebase baseline aktual, inspeksi kontrak dan status lama; inventaris seluruh OD/PR/PO/MKO aktif dan relasinya. Buat fixture supplier, makloon, campuran, partial, legacy dan dua OD SKU sama.
2. L01/L02/L04: selaraskan sumber default, permission, harga, material reservation/issue, UOM dan receiving. Fondasi L04 menjadi dependency validasi penuh L03, tanpa siklus dependency.
3. L03/LN-033: tambah relasi line-level kompatibel, layanan routing tunggal, guard release dan idempotensi; implementasikan UI dan recovery. Uji seluruh acceptance LN-033.
4. L04/L05/L07: konsumsi referensi sumber yang sama pada receiving, kualitas dan pengiriman. Tambahkan regression terkait; jangan menduplikasi tabel/ledger untuk setiap layar.
5. L14/LN-143: jalankan rangkaian dua jalur, mixed/partial, concurrency, Finance dan customer delivery pada kandidat final.

Migrasi harus dry-run dahulu dan melaporkan jumlah matched/ambiguous/unresolved. linked_po_id lama tetap terbaca selama transisi dan dipetakan ke relasi baru hanya bila identitas line terbukti. Jangan otomatis membuat MKO dari label produk makloon pada transaksi historis, membuat ulang stock atau mengulang posting. Simpan mapping dan audit sebelum/sesudah. Rollback harus memulihkan kompatibilitas pembacaan; transaksi fisik/keuangan baru yang sudah berjalan diselesaikan dengan prosedur reversal bisnis yang sah, bukan dihapus.

## Titik selesai dan bukti wajib

LN-033 selesai setelah seluruh 10 skenario terkait pass dan dependency tervalidasi. LN-143 selesai setelah seluruh 8 skenario rangkaian pass pada commit kandidat final. Daftar authoritative ada di BACKLOG.json dan [acceptance matrix](ACCEPTANCE_MATRIX.md).

Bukti harus menunjukkan navigasi aktual, input, dokumen/line yang terbentuk, qty dan unit sebelum/sesudah, reservasi/issue/output actual, status kualitas, alokasi/pengiriman serta rekonsiliasi posting. Sertakan hasil failure/retry dan dua pesanan SKU sama, bukan hanya screenshot dropdown. Review membuktikan jalur lama tetap berjalan.

Status requirement baru tetap not_started dan acceptance not_run. Validasi struktur paket tidak sama dengan pengujian ERP. L03 tidak menutup integrasi pengiriman sebelum L14 memenuhi bukti lengkap. Aturan lama tentang reviewer, owner approval, pending, evidence dan commit tetap berlaku.
