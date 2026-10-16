# Audit lintas flow: QC, sales, proyeksi stok, AR

Review 2026-10-03, snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Seluruh data sintetis di Mongo lokal, indeks aplikasi diinisialisasi, outbound socket dibatasi. Source aplikasi tidak diubah. Hasil ini audit snapshot, bukan validasi fix atau sign-off produksi.

## Ringkasan yang dapat dibuktikan

Tambahan yang masuk register: **56 checkpoint** =41 checkpoint baru (QC14, sales19, projection8) +15 checkpoint AR terdahulu yang kini direview dan direplay. Replay AR bukan15 kasus baru lagi. Hasil tambahan:48 kontrol, tujuh reproduksi cacat untuk enam ID baru W2-014–019, dan satu pendalaman GN-13. Total paket kini155 checkpoint:117 kontrol,23 reproduksi cacat W2,6 observasi kebijakan,9 pendalaman Wave1;19 ID temuan W2.

Checkpoint dalam satu lifecycle dapat saling bergantung.155 bukan jumlah flow independen, bukan persentase coverage, dan bukan berarti seluruh flow kritis lulus. Lihat [matriks cakupan terpadu](18_MATRIKS_FLOW_KRITIS.md) untuk sisa pekerjaan.

| Rangkaian | Bukti aktual | Batas |
|---|---|---|
| GRN → QC → retur supplier → approval |11 kontrol, dua reproduksi W2-014, satu W2-019 | Full accept, campuran accept/damage, validasi input, return panjang dan return pembelian kg. Belum seluruh catch-weight, partial QC, concurrency inspector, atau supplier RMA. |
| SO → verifikasi → confirm → pick → dispatch8+12 → delivered → retur5 → store credit → reversal |19 kontrol HTTP, saldo roll diperiksa tiap tahap | Satu produk/gudang, default non-PPN dan kebijakan approval, qty20. Belum invoice export, split tender POS, pajak, multi-warehouse, pembayaran tunai retur, hardware loading. |
| Available → hold/release → WIP/complete → rebuild bersamaan |7 kontrol, satu reproduksi GN-13 | Barrier mengatur urutan tulis; seluruh query/efek tetap nyata. Bukan pengukuran frekuensi race. |
| AR receipt → kas/GL → deposit allocation → void |11 kontrol, empat cacat W2-015–018 | Legacy SO shipped sintetis; GL asli. Bukan bukti opening-to-closing seluruh perusahaan. |

## W2-014 — P1 — Kuantitas dasar QC dipakai sebagai kuantitas satuan pembelian pada retur

**Kode:** [qc_service.py:23](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/qc_service.py#L23) membaca panjang roll dan baris185 menghitung total karantina dari length_remaining. `_create_qc_return` [baris106–140](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/qc_service.py#L106) mengalikan qty itu dengan harga PO, tetapi mengisi unit dokumen menggunakan `task.unit`. Tidak ada konversi dari base product ke unit harga PO. Caller di baris269 meneruskan reject_qty mentah.

**W2-Q-C10/F01/F02, flow penuh:** produk meter dengan gramasi200 dan lebar1.5; PO3kg @10.000/kg. GRN menghitung satu roll10meter dengan berat aktual3kg. Close benar-benar mencatat PO received_qty3kg dan roll quarantine10meter. Reject seluruh10meter melalui endpoint QC menghasilkan retur **quantity10, unit kg, total100.000**; yang sebanding dengan seluruh pembelian adalah3kg senilai30.000. Approval retur aktual lalu mencatat `PO.returned_amount=100.000`.

**Kontrol pembanding C08/C09:** PO dan roll sama-sama meter, retur10meter @10 menghasilkan100 dan approval tidak mengurangi stok dua kali. Kesalahan muncul pada perpindahan unit antara QC dan dokumen pembelian; bukan seluruh retur supplier gagal.

**SSOT dan UI:** QC menggunakan ukuran dasar roll, tetapi builder retur memperlakukan angka itu sebagai satuan transaksi PO. Frontend `QCInspection.jsx:185/211` bahkan menuliskan label `m` secara tetap; ini bukti source UI, bukan browser UAT. Untuk produk berbasis yard/kg, label perlu mengikuti kontrak unit yang disepakati. Jangan memperbaiki nominal saja sambil membiarkan qty/unit salah.

**Dampak terbukti:** retur dan subledger PO terlalu besar70.000 dalam fixture. Tidak mengklaim bank benar-benar membayar, semua akun GL telah direkonsiliasi, atau seluruh jenis unit gagal.

**Perbaikan:** bawa qty_base/unit_base, actual weight dan qty_purchase/unit_purchase secara eksplisit. Untuk reject sebagian, tentukan alokasi berat/nilai sesuai pengukuran dan snapshot konversi receipt/PO; jangan memakai faktor master terbaru tanpa jejak. Qty untuk menggerakkan roll berbeda dari basis harga retur. Uji meter/meter, meter/kg, yard/meter, partial dan multi-roll.

## GN-13 — risiko statis kini terbukti melalui hold dan rebuild nyata

Tidak dibuat ID baru atau diubah tracker Wave1. [roll_service.py:186](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L186) mengambil snapshot roll; [baris248](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L248) menulis balance tanpa revision guard.

W2-P-E01: rebuild A membaca available10, dijeda tepat sebelum tulis projection. `hold_stock` asli memindahkan4 ke hold dan rebuild B menulis available6/hold4/ATP6. A dilanjutkan: roll tetap available6+hold4, tetapi balance menjadi available10/hold0/ATP10. Rebuild baru memperbaikinya (C07). Dengan demikian yang salah adalah proyeksi setelah interleaving, bukan roll fisik diubah kembali.

Barrier hanya menunda pemanggilan asli update_one milik task A; tidak mengganti hasil query atau nilai yang ditulis. Belum dibuktikan bahwa allocator berbasis roll bisa oversell sebagai akibatnya. Dampak terkonfirmasi adalah saldo/ATP menampilkan4 lebih banyak sampai proyeksi dihitung lagi. Bagian fallback UOM GN-13 tidak diuji pada putaran ini.

## W2-015 — P1 — Pembayaran murni deposit tidak memposting reklasifikasi GL

**Kode:** [ar_receipt_service.py:71–75](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/ar_receipt_service.py#L71) langsung return jika kas baru nol. Posting GL receipt tergantung jalur kas tersebut; create receipt kemudian mengubah deposit di baris511.

**F01:** top-up100.000 melalui API, kemudian lunasi SO100.000 memakai deposit100.000 dan kas baru0. Response200, deposit0, SO paid100.000, tetapi delta GL kosong. Secara rekonsiliasi internal, pelunasan harus mengurangi kewajiban deposit dan piutang dengan nilai sama; jalur campuran C07 membuktikan engine memang melakukan itu ketika ada kas baru20.000+deposit80.000: kas+20.000, debit uang muka80.000, kredit piutang100.000.

Tidak menciptakan kas baru untuk pembayaran deposit adalah benar. Cacatnya adalah hilangnya posting nonkas. Berbeda dari FN-10 yang menelan exception GL: pada kasus ini posting dilewati tanpa exception. Scheduler/backfill tidak dijalankan dan tidak diklaim pasti memperbaikinya; receipt sudah terlihat final sebelum rekonsiliasi GL benar.

**Perbaikan:** pisahkan posting transaksi bisnis dari pencatatan kas; receipt kas0 tetap memiliki jurnal reklasifikasi yang idempoten dan dapat direversal. Jangan membuat kas fiktif sebagai jalan pintas.

## W2-016 — P1 — Void sumber deposit ditolak setelah pembayaran dan kas sudah dibalik

**Kode:** [ar_receipt_service.py:571–649](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/ar_receipt_service.py#L571). Menghapus payment SO dan void kas/GL lebih dulu; koreksi deposit baru terjadi di baris640–643, sebelum status receipt ditulis void.

**F02:** receipt150.000 dialokasikan50.000 ke SO1, sisanya deposit100.000. Receipt kedua memakai seluruh deposit untuk SO2. Void receipt pertama mengembalikan409 karena deposit sudah terpakai. Namun SO1 sudah kembali unpaid, kas150.000 sudah void dan GL pembalik sudah terjadi; receipt pertama masih posted dengan lock. SO2 tetap paid100.000.

Penolakan karena dana telah dipakai masuk akal; efek parsial sebelum penolakan adalah cacat. Ini terjadi berurutan, tanpa fault injection atau concurrency. GN-11 relevan untuk recovery umum, tetapi kasus ini mempunyai prasyarat bisnis spesifik yang seharusnya diperiksa dan dikunci sebelum efek pembatalan.

**Perbaikan:** validasi dependensi deposit dan reserve hak pembalikan secara atomik sebelum membalik efek. Jika ada kebijakan unwind receipt turunan, buat proses eksplisit dengan jejak dan hak yang sesuai. Kegagalan tidak boleh meninggalkan receipt posted tetapi kas/allocations sudah dibalik.

## W2-017 — P1 — CAS deposit terlambat: pembayaran sudah diterapkan ketika saldo tidak cukup

**Kode:** [ar_receipt_service.py:374](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/ar_receipt_service.py#L374) snapshot saldo; baris419/439 menerapkan pembayaran; baris474 memasukkan receipt posted; baris511 baru mengurangi deposit. `_adjust_deposit` baris117–129 memiliki CAS yang benar mencegah saldo negatif, tetapi CAS tidak mencakup efek sebelumnya.

**F03:** deposit100.000, dua SO masing-masing80.000. Caller A membaca saldo lalu dijeda. Caller B selesai membayar80.000. A dilanjutkan dan berakhir409, tetapi kedua SO sudah paid80.000; total pembayaran160.000, deposit tersisa20.000, kedua receipt pemakaian berstatus posted. C10 membuktikan pemakaian berurutan tanpa snapshot lama menolak pembayaran kedua sebelum memutasi SO.

Barrier hanya mengatur snapshot pembacaan deposit, semua operasi bisnis dan Mongo tetap asli. Ini bukan klaim uang eksternal berpindah atau frekuensi race tertentu.

**Perbaikan:** klaim/reserve dana deposit sebelum alokasi SO dan penerbitan receipt final; buat kompensasi/resume yang mengikat seluruh efek pada operation ID. Jangan hanya menambah CAS saldo karena CAS tersebut sudah ada. Uji saldo cukup/tidak cukup, transaksi berbeda pada pelanggan sama dan failure setelah dana direserve.

## W2-018 — P1 — Void menimpa pembayaran lain yang baru masuk

**Kode:** [ar_receipt_service.py:592–610](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/ar_receipt_service.py#L592) menghitung payments dari snapshot lama lalu `$set` seluruh array tanpa revision predicate. Pengunci ada di receipt yang di-void, bukan di SO yang menerima pembayaran lain.

**F04:** SO100.000 sudah dibayar40.000. Void40.000 dijeda sebelum menyimpan array pembayaran hasil filter. Pembayaran baru60.000 selesai. Void dilanjutkan; kedua response200, receipt60.000 tetap posted dan kas aktif60.000, tetapi SO payments kosong/paid_total0/unpaid. Net efek GL sesuai adanya pembayaran baru tidak menjadi sumber yang dibaca ulang oleh array payment. C11 urutan serial void dulu lalu pembayaran60.000 menghasilkan paid_total60.000.

**Perbaikan:** operasi penghapusan terarah berdasarkan receipt ID dan perhitungan saldo dengan concurrency control SO; jangan menulis ulang daftar dari snapshot lama. Pertahankan aturan realokasi negatif dan pastikan paid_total/payment_status dihitung dari versi yang sama. Uji void-vs-create, dua void, realokasi, retry dan kegagalan setelah mutasi.

## Bukti yang harus dibaca bersama

- [QC14 checkpoint](qc-flow-results.json), [harness](repro/wave2_qc_flow.py).
- [Sales19 checkpoint dan respons API](sales-flow-results.json), [harness](repro/wave2_sales_flow.py).
- [Projection8 checkpoint](projection-results.json), [harness](repro/wave2_projection.py).
- [AR15 checkpoint hasil replay](ar-results.json), [bukti awal yang dipertahankan](validation/AR-review/original-results.json), [harness](repro/wave2_ar.py).
- [Prompt fase implementasi](17_PROMPT_LINTAS_FLOW.md).

Reproducer mengassert perilaku cacat untuk membuktikan keberadaannya; untuk verifikasi fix, acceptance tests harus mengharapkan perilaku bisnis yang benar. Respons200 saja bukan bukti lulus: kontrol sales juga memeriksa stok; kontrol AR memeriksa pembayaran, kas, deposit dan GL sesuai lingkup masing-masing. Seluruh laporan keuangan, pajak, seluruh FIFO/WAC, UI, perangkat fisik dan scheduler belum mendapat sign-off.

## W2-019 — P2 — Pemisahan roll saat QC menggandakan berat tersimpan

**Kode:** [qc_service.py:58–74](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/qc_service.py#L58) mengurangi length pada parent lalu menyalin `dict(roll)` ke child. Field `weight_kg` dan `secondary_measures.kg` tidak dibagi/dikosongkan untuk pengukuran ulang. [roll_service.py:93–115](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L93) memberi identitas child baru tetapi tidak menyelesaikan kontrak berat.

**W2-Q-F03:** penerimaan asli PO3kg menghasilkan satu roll10meter/3kg. QC menerima6meter dan menolak4meter menjadi damaged. Panjang tetap10, tetapi dua roll masing-masing membawa weight_kg3 dan secondary_measures.kg3, sehingga jumlah tersimpan6kg. C11 pembanding full accept tanpa split mempertahankan3kg. Yang bertambah adalah data berat, bukan berat fisik barang.

**Dampak:** panjang lolos rekonsiliasi sementara ukuran kedua salah; data untuk timbang, laporan atau penanganan barang berbasis berat tidak bisa dipercaya setelah split ini. Belum diuji efek moneternya atau semua caller helper split; tidak mengklaim seluruh split telah direproduksi. Berbeda dari WM-02 yang membahas kapan child fisik lahir pada reservasi, dan W2-014 yang mencampur unit harga retur.

**Perbaikan:** tetapkan kontrak konservasi ukuran tambahan saat split. Jika berat aktual potongan belum diukur, tandai belum diukur; bila estimasi proporsional diizinkan, beri provenance estimasi dan alokasikan residual agar total tetap3kg. Jangan menyalin hasil timbang parent sebagai hasil timbang setiap child. Audit seluruh caller insert_child_roll dan ukuran turunan/label yang memakai field ini, dengan tests per flow sebelum menyatakan cakupan menyeluruh.
