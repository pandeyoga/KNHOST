# Cakupan dan pemetaan sumber

Semua ID sumber yang tercantum dipetakan ke requirement aktif. Ini ukuran traceability kebutuhan, bukan ukuran line/function/branch code coverage atau jaminan semua bug ditemukan.

Register historis dipertahankan untuk konteks; keputusan owner terbaru menang. Daftar acceptance lama tidak disalin sebagai PASS. L00 wajib menentukan apakah skenario lama dipakai ulang, diuji ulang, diganti oleh keputusan baru atau masih pending, dengan alasan per ID.

| Kelompok sumber | Jumlah ID terpetakan |
|---|---|
| HIST | 126 |
| LATEST | 17 |
| RETURN | 13 |
| OLD_IMP | 35 |
| OLD_ACC | 67 |
| ERP_MW | 12 |
| MW_UAT | 48 |
| RACC | 30 |
| RFID_REQ | 15 |
| RFID_STAGE | 6 |
| PRODUCTION_ROUTE | 1 |
| ROLE_RND | 1 |

## HIST

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| AK-01 | Nama staf diwakili role dan penugasan | LN-010 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| AK-02 | UI pengaturan role empat tingkat | LN-010 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| AK-03 | Hak aktivitas dan cakupan data | LN-010 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| AK-04 | Konfigurasi POS mengikuti role dinamis | LN-012 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| AK-05 | Grade tidak terlihat oleh Sales, termasuk trial | LN-012 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| AK-06 | Satu ACC dari kelompok PIC cukup | LN-010 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| AK-07 | Arti klik ACC PIC | LN-010 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-01 | Jenis kain berbeda dari tahap barang | LN-011 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-02 | Greige tidak dijual; PFD/PFP dapat dijual | LN-012 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-03 | Dataset bahan dan supplier dari client | LN-011 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-04 | Nama dan kode warna mempunyai acuan jelas | LN-011 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-05 | Tambah, ubah dan nonaktifkan master secara jelas | LN-011 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-06 | R&D wajib mengikuti asal SKU dan lini | LN-011 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-07 | Pengujian existing product tanpa SKU duplikat | LN-011, LN-032 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-08 | Detail dan filter master lengkap | LN-011 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-09 | Sumber restock per artikel | LN-013 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-10 | Greige committed berbeda dari sudah dikeluarkan | LN-043, LN-020 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| MD-11 | Grade dapat dikelola tanpa perubahan program | LN-012 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-01 | Request custom melalui Pesanan Khusus | LN-030 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-02 | Lebih dari satu produk dalam Special Order | LN-030 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-03 | Custom warna dari induk produk existing | LN-030 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-04 | Pakai desain approved yang belum menjadi produk | LN-030 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-05 | Perlakuan desain berstatus HOLD | LN-030 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-06 | Empat skenario memakai sumber berbeda pada flow yang sama | LN-030 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-07 | Label asal desain internal atau Special Order | LN-030 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-08 | Paper disetujui sebelum proofing kain | LN-031 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-09 | Customer memutuskan, Sales mencatat | LN-031 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-10 | Reproofing mengulang hasil dari artwork yang sama | LN-032 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-11 | Harga design yang dimaksud adalah harga kain | LN-022 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SO-12 | Harga custom mengikuti induk produk | LN-022 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-01 | Sales melihat ketersediaan gabungan entitas | LN-020 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-02 | Keep berarti SO belum diverifikasi | LN-020 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-03 | Pending ditampilkan per produk dan sumber pemenuhan | LN-020 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-04 | Sales melihat warna; Admin Sales mengalokasikan detail | LN-012 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-05 | Roll picker untuk Admin Sales | LN-021 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-06 | SO menampilkan satuan dan rincian roll | LN-020 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-07 | Pemenuhan roll utuh tidak selalu sama dengan yard pesanan | LN-021 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-08 | Qty receiving mengikuti fisik per roll | LN-023, LN-040 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-09 | Harga dapat berbeda antar grade | LN-022 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-10 | Rekomendasi grade berdasarkan kebutuhan customer | LN-012 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-11 | Tasik dan Tamim berada dalam entitas Kanda | LN-020 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SL-12 | Satuan transaksi umum yard atau kg | LN-020, LN-042 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-01 | Tiga jenis sampel | LN-060 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-02 | Batas sampel standar | LN-060 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-03 | Batas hanger | LN-060 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-04 | Resep potong catalogue yang terbaru | LN-060 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-05 | Operator mengganti warna tambahan catalogue | LN-060 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-06 | Hasil produksi catalogue dan cakupan warna | LN-060 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-07 | Setelah cutting kembali ke Admin Cutting | LN-061 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-08 | Ecer berbayar berbeda dari sampel | LN-062 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-09 | Kemampuan sample per lokasi | LN-061 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| SM-10 | Catalogue ketika warna tersebar antar lokasi | LN-061 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-01 | Identitas unik setiap roll dan potongan | LN-082 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-02 | Nomor potongan mengadopsi induk RTN | LN-082 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-03 | Qty dan grade dapat berubah saat retur | LN-082, LN-091 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-04 | Retur tidak dikirim lagi ke customer asal | LN-082 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-05 | Toggle pengecualian larangan retur | LN-082 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-06 | Batas klaim customer 21 hari dari SJ | LN-083 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-07 | Tanggal awal batas supplier masih ambigu | LN-083 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-08 | Klaim customer tidak gugur karena supplier kedaluwarsa | LN-083 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-09 | Hangtag hilang atau barang sudah cutting | LN-083 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-10 | Approval regional via WA adalah keadaan saat ini | LN-081 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-11 | ACC teknis berbeda dari penyelesaian komersial | LN-081 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-12 | Cutloss mengembalikan bagian kain yang dipotong | LN-092 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-13 | Discount dapat tanpa barang kembali | LN-092 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-14 | Tukar tetap artikel yang sama | LN-090 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-15 | Warna dan grade pengganti belum final | LN-090 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-16 | Refund atau saldo customer | LN-091 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-17 | Tujuan kain setelah QC | LN-093, LN-100 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-18 | BS dibuang dengan pencatatan fisik | LN-093 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RT-19 | Nilai retur, turun grade dan kerugian | LN-091 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-01 | MD Quality berbeda dari QC cacat/grade | LN-041 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-02 | Potongan MD Quality 0,25 yard selebar kain | LN-042 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-03 | Frekuensi dan pemakaian potongan MD Quality | LN-041 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-04 | Receiving diukur sebelum potongan MD Quality | LN-042 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-05 | Master pembanding dan keputusan tidak sesuai | LN-041 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-06 | Panjang inspect selalu yard | LN-051 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-07 | Pemakaian kg akibat pemotongan panjang | LN-042 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-08 | QC sebelum kirim sesuai kebutuhan | LN-050 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-09 | Daftar customer dan standar QC sebelum kirim | LN-050 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-10 | Pemetaan kolom form inspect | LN-051 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-11 | Kode cacat, interval dan rumus skor | LN-052 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| QC-12 | Ambang grade dan riwayat grade lama | LN-052, LN-012 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-01 | Hierarki fisik mempunyai lemari dan rak terpisah | LN-100 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-02 | Stok dapat ditelusuri pada semua tingkat alamat | LN-102 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-03 | Putaway tetap dapat diakses | LN-100 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-04 | Putaway berbeda dari transfer antar gudang | LN-100 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-05 | Bandung ke Jakarta dahulu, kemudian customer | LN-072 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-06 | Gudang shared, dedicated dan transit | LN-100 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-07 | Aturan lemari/rak dan parameter pembatas | LN-100 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-08 | Perubahan struktur menjaga barang dan tugas aktif | LN-100 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-09 | Visibilitas admin gudang per lokasi | LN-010 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-10 | OCR membaca qty setiap roll | LN-040 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-11 | LOT pabrik dan LOT internal mempunyai jejak | LN-014, LN-040 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-12 | Semua barang ditag, termasuk transit | LN-042, LN-120 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-13 | Satu SO beberapa gudang dan SJ untuk driver | LN-071 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-14 | Transfer parsial, selisih dan pembatalan | LN-072 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-15 | Stock opname memiliki aturan pelaksanaan | LN-101 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| WM-16 | Reprint label tidak menggandakan identitas fisik | LN-042 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| IC-01 | Pemenuhan SO melalui pembelian antar entitas | LN-020, LN-061, LN-093 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| IC-02 | Workspace MD tidak mengaburkan entitas dokumen | LN-013 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| IC-03 | Barang/kepemilikan diproses sebelum pembayaran | LN-072 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| IC-04 | Pembayaran penuh per transaksi tanpa netting | LN-024, LN-093 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| IC-05 | Cutoff pembayaran antar entitas | LN-024 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RP-01 | Meja User membuka detail proses terkait | LN-102 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RP-02 | Satu menu export dengan pilihan dataset | LN-110 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RP-03 | Filter, kolom pilihan, preview dan AND/OR | LN-110 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RP-04 | Join data dengan granularitas yang benar | LN-111 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RP-05 | Definisi data penjualan dan periode | LN-111, LN-023 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RP-06 | Nilai dan revisi designer | LN-112 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RP-07 | Hak export sama ketatnya dengan layar | LN-113 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RF-01 | Tiga perangkat masuk lingkup RFID | LN-120 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RF-02 | Middleware dibuat sendiri dengan tiga modul | LN-120 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RF-03 | Reader berjalan pada Android perangkat | LN-121 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RF-04 | Handheld menjalankan tugas gudang | LN-121 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RF-05 | Printer memproses job label dan tag | LN-122 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RF-06 | Kontrak diasumsikan tersedia hanya untuk dokumen middleware | LN-120 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RF-07 | Pemetaan kontrak aktual dan uji perangkat | LN-120, LN-142 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| RF-08 | Hasil reader tidak otomatis berarti barang keluar | LN-121 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| HR-01 | Absensi langsung tanpa laptop harian | LN-130 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| HR-02 | Model dan firmware absensi belum final | LN-130 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| HR-03 | Pisahkan log punch dari hasil attendance | LN-130 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| HR-04 | Aturan shift, telat, lembur dan koreksi | LN-131 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| DG-01 | Format identitas project yang profesional | LN-001 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| DG-02 | Perbaikan bertahap dengan bukti | LN-142 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |
| DG-03 | Acuan fase 5 dan batas snapshot | LN-001 | Kejelasan historis bukan status implementasi; terapkan keputusan terbaru jika ada overlay. |

## LATEST

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| N01 | Special Order existing ACC tetap proofing; label tujuan bisa difilter | LN-030, LN-032 | jelas |
| N02 | Harga grade alokasi A dan pengajuan ulang harga khusus | LN-022 | jelas |
| N03A | Form MD Quality dari receiving dan bebas memilih roll uji | LN-041 | jelas |
| N03B | Identitas/tag sebelum potong; penerimaan bruto terpisah saldo setelah uji | LN-042 | usulan_untuk_ditinjau |
| N04 | QC SO seluruh/sampling; toggle checkout default tidak; Meja QC | LN-050 | jelas |
| N05 | Form inspect artikel/customer/jenis kain/dua warna/roll/tanggal dan tiga sumber | LN-051 | jelas |
| N06A | Interval 15 yard sepuluh kolom; legenda berarti Keterangan | LN-051 | jelas |
| N06B | Kamus cacat dan formula nilai akhir sampai grade | LN-052 | menunggu_data_client |
| N07 | Dual naming LOT supplier/KN dan aturan pemetaan | LN-014, LN-040 | menunggu_klarifikasi_client |
| N08A | Lokasi banyak gudang; konsolidasi transit; multi-SO satu perjalanan; transit Jakarta | LN-070, LN-072 | jelas |
| N08B | SJ per SO per keberangkatan; manifest armada; dokumen internal bukan customer dispatch | LN-071 | usulan_untuk_ditinjau |
| N09 | Selisih diselesaikan per kasus; amandemen SO bila qty transaksi berubah | LN-021, LN-072 | jelas |
| N10 | Tanggal cutoff, dasar tanggal dan jadwal pembayaran interco | LN-024 | menunggu_klarifikasi_client |
| N11A | Export seluruh data bisnis sesuai akses, filter tanggal, kolom dan preview | LN-110, LN-113 | jelas |
| N11B | Nilai desain adalah skor desain | LN-112 | jelas |
| N11C | Join relevan dan rapor staf designer/Sales lengkap beserta ringkasan | LN-111, LN-112 | jelas |
| N11D | Template rapor, detail/ringkasan dan hubungan antardata yang direkomendasikan | LN-112 | usulan_untuk_ditinjau |

## RETURN

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| R-01 | Pertanyaan cutloss harus memakai contoh roll 120 yard, cacat yard 46–60: apakah customer menerima 61–120 (60 yard) dan nilai dikembalikan setara 60 yard, atau menerima dua potong 1–45 dan 61–120 (105 yard) dengan nilai dikembalikan setara 15 yard. | LN-092 | menunggu_klarifikasi_client |
| R-02 | Sales yang membuat Sales Retur memilih barang/roll mana dari transaksi sumber yang diretur. | LN-080 | dijawab_pemilik |
| R-03 | Tidak menerima Barang Sisa sebagai layanan pengajuan tersendiri. Garansi adalah masa klaim 21 hari sesudah barang dikirim. | LN-080, LN-083 | dijawab_pemilik |
| R-04 | Perbedaan qty yard pada tukar sangat mungkin; patokan pengganti dan penyelesaian selisih perlu diklarifikasi ke client. | LN-090 | menunggu_klarifikasi_client |
| R-05 | Dasar nilai serta tagihan/refund/saldo atas selisih tukar harus ditanyakan ke client. | LN-090, LN-091 | menunggu_klarifikasi_client |
| R-06 | Perubahan warna dan grade pengganti tidak diperbolehkan. | LN-090 | dijawab_pemilik |
| R-07 | Barang pengganti mengikuti permintaan QC pada SO awal. Pengganti menunggu barang retur diterima dan selesai QC. | LN-090, LN-050 | dijawab_pemilik |
| R-08 | Customer boleh memilih refund atau saldo. Bila masih ada tagihan, nilai mengurangi tagihan terlebih dahulu; kelebihannya direfund atau menjadi saldo. | LN-091 | dijawab_pemilik |
| R-09 | Foto boleh dilengkapi kemudian. Kewajiban foto mengikuti konfigurasi kebijakan. | LN-080 | dijawab_pemilik |
| R-10 | CST wajib menerima retur internal bila Sukacita memutuskan mengembalikan ke CST. Sebelumnya Sukacita dapat memilih menyimpan sebagai stok milik Sukacita. | LN-093 | dijawab_pemilik |
| R-11 | QC retur saat ini hanya di Rancamalang. Retur dari Jakarta dapat diterima di Jakarta, dikirim ke Rancamalang dan ditempatkan pada area transit menunggu QC. Gudang shared dibagi kategori, bukan per entitas. Owner dapat menjadi CST setelah retur internal walau fisik tetap di area shared. | LN-081, LN-093, LN-100 | dijawab_pemilik |
| R-12 | CST boleh memilih simpan atau retur supplier. Bila masa retur supplier lewat, disimpan sebagai stok. | LN-093 | dijawab_pemilik |
| R-13 | Persetujuan melalui WA berlangsung di luar ERP; gunakan bukti keputusan. Keputusan tukar/kompensasi final sesudah QC inspect. | LN-081, LN-092 | dijawab_pemilik |

## OLD_IMP

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| IMP-01 | Setiap antrean membuka detail pekerjaan yang relevan | LN-102 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-02 | Tampilan khusus Keep dengan definisi yang konsisten | LN-020 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-03 | Pending dimulai dari kebutuhan produk, lalu dokumen pemenuhannya | LN-020 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-04 | Pisahkan tampilan komersial Sales dari detail alokasi internal | LN-012, LN-020 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-05 | Roll picker untuk seluruh alokasi dan perubahan pemenuhan | LN-021 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-06 | Qty, satuan, dan rincian roll jelas sepanjang alur SO | LN-020 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-07 | Special Order dari artikel existing atau desain pelanggan | LN-030, LN-031 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-08 | Special Order berisi beberapa produk dengan progres per baris | LN-030 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-09 | Tiga jenis sampel tampil jelas bagi Sales | LN-060 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-10 | Tambahkan serah terima dan proses Admin Cutting setelah pemotongan | LN-061 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-11 | Samakan harga non-BS dan berikan rekomendasi grade yang dapat dijelaskan | LN-022, LN-012 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-12 | Rapikan klasifikasi tahap bahan dan kelayakan tampil di Sales | LN-011, LN-012 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-13 | Pemetaan supplier, barang supplier, dan warna supplier lengkap | LN-011 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-14 | Perjelas tambah, edit, nonaktif, dan hapus master | LN-011 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-15 | Filter master produk/varian lengkap dan dapat digabung | LN-011 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-16 | Bedakan MD Quality dengan QC beserta dampak prosesnya | LN-041, LN-050, LN-051 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-17 | Uji tambahan SKU existing tanpa membuat master duplikat | LN-032, LN-011 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-18 | Tampilkan kebutuhan bahan makloon, reservasi, issue, dan WIP secara jelas | LN-043 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-19 | Tetapkan sumber restock per artikel dan arahkan backorder sesuai master | LN-013 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-20 | Batasi pekerjaan gudang menurut lokasi penugasan pengguna | LN-010 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-21 | OCR SJ/packing list mengisi kandidat roll secara kelompok | LN-040 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-22 | Pulihkan pengalaman putaway dan satukan jalur scan/alamat | LN-100 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-23 | Hierarki fisik konsisten dari lokasi sampai posisi penyimpanan | LN-100 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-24 | Rules gudang dan sublokasi berlaku konsisten di seluruh jalur | LN-100 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-25 | Lindungi stok dan tugas saat struktur lokasi diubah | LN-100 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-26 | Transfer antar gudang untuk memenuhi SO menjaga komitmen barang | LN-072 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-27 | Terima transfer berdasarkan roll aktual, termasuk parsial dan selisih | LN-040, LN-072, LN-023 | Status sumber implemented_pending_validation; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-28 | Stock opname menyatukan qty, identitas roll, alamat, dan RFID | LN-101 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-29 | Dashboard stok berjenjang dengan subtotal satuan dan status yang benar | LN-102 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-30 | Mesin mengirim absensi langsung ke penerima di server ERP | LN-130 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-31 | Registrasi perangkat dan pemetaan ID pegawai terkontrol | LN-130 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-32 | Pisahkan log punch mentah dari hasil perhitungan kehadiran | LN-131 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-33 | Tahan putus koneksi dan cegah pencatatan ganda | LN-130 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-34 | Antarmuka HR memantau sinkronisasi dan exception | LN-130, LN-131 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |
| IMP-35 | Tetapkan kompatibilitas hardware melalui uji perangkat nyata | LN-130 | Status sumber not_started; tidak disalin menjadi status kelulusan gelombang baru. |

## OLD_ACC

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| ACC-00 | Baseline target | LN-001, LN-140, LN-142 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-01 | Tahap dan kelayakan jual | LN-011, LN-012 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-02 | Alias supplier/color | LN-011 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-03 | Lifecycle master | LN-011 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-04 | Filter master | LN-011 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-05 | Scope lokasi | LN-010 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-06 | Resolver modern/legacy | LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-07 | Menu dan putaway | LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-08 | Status fisik | LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-09 | Padanan Lemari/Rak | LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-10 | Hapus atau pindah struktur | LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-11 | Shared/dedicated | LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-12 | Rules gabungan | LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-13 | Kapasitas dan balapan aksi | LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-14 | OCR per roll | LN-040 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-15 | SJ hanya total | LN-040 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-16 | Bandung-Jakarta-customer | LN-072 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-17 | Reservasi dan concurrency | LN-072 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-18 | Receipt parsial | LN-023, LN-040, LN-072 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-19 | Exception transfer | LN-023, LN-040, LN-072 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-20 | Aturan tujuan dan ownership | LN-023, LN-040, LN-072, LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-21 | Keep dan Pending bersamaan | LN-020 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-22 | Referensi supply Pending | LN-020 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-23 | Sales projection | LN-012, LN-020 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-24 | Stok global dan ATP | LN-012, LN-020 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-25 | Edit alokasi roll | LN-021 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-26 | Yard dan roll utuh | LN-020 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-27 | Detail qty sebelum/sesudah alokasi | LN-020 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-28 | Harga dan rekomendasi grade | LN-012, LN-022 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-29 | MD Quality dan QC | LN-041, LN-050, LN-051 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-30 | Labdip dan Handfeel existing | LN-011, LN-032 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-31 | Perubahan identitas dan hak MD | LN-011, LN-032 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-32 | Reservasi dan issue 1:1 | LN-043 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-33 | Yield dan bahan kurang | LN-043 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-34 | Pembatalan/partial produksi | LN-013, LN-043 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-35 | Jalur restock | LN-013 | Uji ulang/dipertahankan/diganti pada L00; hasil historis pass bukan PASS kandidat baru. |
| ACC-36 | Desain pelanggan dan artikel existing | LN-030, LN-031 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-37 | OD dua produk | LN-030 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-38 | OD legacy dan retry | LN-030, LN-031 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-39 | Tipe sampel | LN-060 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-40 | Handoff Admin Cutting | LN-061 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-41 | Retry, cancel, dan sampel legacy | LN-060, LN-061 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-42 | Opname actual roll dan RFID | LN-101 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-43 | Snapshot dan transaksi berjalan | LN-101 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-44 | Posting adjustment dan dampak reservasi | LN-101 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-45 | Mixed unit dan kapasitas | LN-102 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-46 | Rekonsiliasi hierarchy | LN-100, LN-102 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-47 | Shared capacity dan permissions | LN-102 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-48 | Meja seluruh peran | LN-102 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-49 | Hardware PoC | LN-130 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-50 | Native protocol receiver | LN-130 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-51 | Mapping dan registrasi | LN-130 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-52 | Raw event dan koreksi | LN-131 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-53 | Shift overnight | LN-131 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-54 | Missing/multiple punches dan overtime | LN-131 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-55 | Offline dan kiriman ulang | LN-130 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-56 | Out-of-order, drift, dan partial failure | LN-130 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-57 | Monitoring HR | LN-130, LN-131 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-58 | Pilot direct tanpa perantara | LN-130 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-59 | E2E SO dan transfer | LN-020, LN-021, LN-023, LN-040, LN-072 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-60 | E2E backorder supplier/makloon | LN-013, LN-020, LN-040, LN-043, LN-100 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-61 | E2E Special Order dan R&D | LN-011, LN-030, LN-031, LN-032, LN-041, LN-050, LN-051 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-62 | E2E sampel dan WMS | LN-010, LN-060, LN-061, LN-100, LN-101 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-63 | E2E attendance dan payroll review | LN-130, LN-131 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-64 | Migrasi dan rollback | LN-001, LN-140, LN-142 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-65 | Concurrency dan recovery lintas modul | LN-001, LN-140, LN-142 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |
| ACC-66 | UAT dan kesiapan rilis | LN-001, LN-140, LN-142 | Uji ulang/dipertahankan/diganti pada L00; hasil historis not_run bukan PASS kandidat baru. |

## ERP_MW

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| ERP-MW-01 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-121 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-02 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-121 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-03 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-121 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-04 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-121 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-05 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-121 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-06 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-121 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-07 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-121 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-08 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-122 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-09 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-122 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-10 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-122 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-11 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-122 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |
| ERP-MW-12 | Rebase gap kontrak middleware ke ERP aktual | LN-120, LN-122 | Dokumen sumber menggunakan snapshot lama; temuan belum otomatis dianggap masih terjadi. |

## MW_UAT

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| HH-01 | **Input/prasyarat:** Akun gudang A; device terikat A; task warehouse B. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-02 | **Input/prasyarat:** C72 aktual, SDK/firmware tercatat; trigger fisik dan tag known. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-03 | **Input/prasyarat:** Dua task/version/operator berbeda. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-04 | **Input/prasyarat:** Print job tag-roll; satu label salah EPC atau salah pemasangan. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-05 | **Input/prasyarat:** Manifest 10 roll serta satu tag extra; server revises manifest. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-06 | **Input/prasyarat:** Count plan dengan qty/unit dan missing/untagged. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-07 | **Input/prasyarat:** Putaway task; valid bin serta bin wrong rule/capacity. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-08 | **Input/prasyarat:** Pending outbox; authorized offline context. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-09 | **Input/prasyarat:** Partial ACK serta response lost untuk batch yang sama. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-10 | **Input/prasyarat:** Local counter clean, server processing pending/with_issues. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-11 | **Input/prasyarat:** Known target EPC dan unknown/non-RFID roll. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| HH-12 | **Input/prasyarat:** Release APK/source/profile/runbook dan evidence. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-01 | **Input/prasyarat:** UR300 Android terpasang APK, ERP network; semua PC/laptop dilepas. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-02 | **Input/prasyarat:** Actual OS/SDK/ABI/permissions/power policy. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-03 | **Input/prasyarat:** Two logical gates/antenna-sensor mapping dan arah. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-04 | **Input/prasyarat:** Tag diam, passage selesai, re-entry tag sama. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-05 | **Input/prasyarat:** Network lost ACK, process death setelah durable local capture. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-06 | **Input/prasyarat:** Fresh live authorized final green; stale/final=false/mismatched response. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-07 | **Input/prasyarat:** Red latch satu gate serta supervisor ack yang stale. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-08 | **Input/prasyarat:** Manifest/full/subset/per_epc policies; missing/unknown. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-09 | **Input/prasyarat:** Offline passages dan backlog serta server jam/response delayed. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-10 | **Input/prasyarat:** Outbox hampir penuh, disk error, reboot/update. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-11 | **Input/prasyarat:** Radio off sementara network online; ERP down sementara radio ready. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| RD-12 | **Input/prasyarat:** Signed APK/source/SDK map/config and no-PC runbook. | LN-121 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-01 | **Input/prasyarat:** CP30EN aktual dengan media RFID/ribbon/profile/SDK. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-02 | **Input/prasyarat:** Dua connector/printer warehouses berbeda; job RFID vs QR. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-03 | **Input/prasyarat:** Claim active attempt; retry claim dan renew. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-04 | **Input/prasyarat:** Durable intent, ERP start timeout/conflict. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-05 | **Input/prasyarat:** Spool ACK, physical print/encode status, C72 verification. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-06 | **Input/prasyarat:** 10 items: 7 confirmed, 2 failed, 1 unknown. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-07 | **Input/prasyarat:** Physical output selesai; result response sengaja hilang. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-08 | **Input/prasyarat:** Crash setelah send; expired lease saat output in progress. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-09 | **Input/prasyarat:** Reprint text vs retag; old chip dan movement aktif. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-10 | **Input/prasyarat:** Result persisted, failure sebelum tag/journey effect. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-11 | **Input/prasyarat:** Job qty yard/kg, template revision, queue backlog/status. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| PR-12 | **Input/prasyarat:** Service package/source/profile/media/runbook. | LN-122 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-01 | **Input/prasyarat:** Satu roll actual ERP dan chip kosong. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-02 | **Input/prasyarat:** SO manifest loading, source/warehouse valid. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-03 | **Input/prasyarat:** Transfer Bandung ke Jakarta; planned receipt/putaway/cross-dock. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-04 | **Input/prasyarat:** Inventory plan plus physical discrepancies. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-05 | **Input/prasyarat:** Satu reader dengan dua logical gates berizin. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-06 | **Input/prasyarat:** Offline dengan pending observations dan new live task/passage. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-07 | **Input/prasyarat:** Printer output selesai, result ACK lost. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-08 | **Input/prasyarat:** Partial print/encode dan mismatched C72 scan. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-09 | **Input/prasyarat:** Manifest/config revision, session expiry/key rotation. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-10 | **Input/prasyarat:** Pending queues/ledgers pada ketiga runtime. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-11 | **Input/prasyarat:** Server event/result durable tetapi effects pending. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |
| INT-12 | **Input/prasyarat:** Tag rusak/hilang dengan active movement. | LN-120 | UAT integrasi nyata required pada L12; implementasi adapter tetap workstream middleware. |

## RACC

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| RACC-01 | Model dan SDK | LN-120, LN-121, LN-122 | Diturunkan ke UAT HH-02, RD-02, PR-01; hasil sumber tidak disalin sebagai PASS. |
| RACC-02 | Read nyata | LN-120, LN-121 | Diturunkan ke UAT HH-02, RD-03; hasil sumber tidak disalin sebagai PASS. |
| RACC-03 | Identitas dan scope | LN-120, LN-121, LN-122 | Diturunkan ke UAT HH-01, PR-02; hasil sumber tidak disalin sebagai PASS. |
| RACC-04 | Kontrak session dan non-session | LN-120, LN-121 | Diturunkan ke UAT HH-03, HH-09; hasil sumber tidak disalin sebagai PASS. |
| RACC-05 | Trigger dan lifecycle C72 | LN-120, LN-121 | Diturunkan ke UAT HH-02, HH-08; hasil sumber tidak disalin sebagai PASS. |
| RACC-06 | Verify tag | LN-120, LN-121 | Diturunkan ke UAT HH-04, INT-01; hasil sumber tidak disalin sebagai PASS. |
| RACC-07 | Loading dan task context | LN-120, LN-121 | Diturunkan ke UAT HH-05, HH-10, INT-02; hasil sumber tidak disalin sebagai PASS. |
| RACC-08 | RFID opname | LN-120, LN-121 | Diturunkan ke UAT HH-06, INT-04; hasil sumber tidak disalin sebagai PASS. |
| RACC-09 | Putaway alamat | LN-120, LN-121 | Diturunkan ke UAT HH-07; hasil sumber tidak disalin sebagai PASS. |
| RACC-10 | Arah dan logical gate | LN-120, LN-121 | Diturunkan ke UAT RD-03, INT-05; hasil sumber tidak disalin sebagai PASS. |
| RACC-11 | Manifest dan passage | LN-120, LN-121 | Diturunkan ke UAT RD-04, RD-06, RD-08; hasil sumber tidak disalin sebagai PASS. |
| RACC-12 | Dwell dan passage baru | LN-120, LN-121 | Diturunkan ke UAT RD-04, RD-05; hasil sumber tidak disalin sebagai PASS. |
| RACC-13 | Indikator fisik | LN-120, LN-121 | Diturunkan ke UAT RD-06, RD-07; hasil sumber tidak disalin sebagai PASS. |
| RACC-14 | Offline dan lost ACK | LN-120, LN-121 | Diturunkan ke UAT HH-09, RD-05, INT-06; hasil sumber tidak disalin sebagai PASS. |
| RACC-15 | Backlog dan keputusan basi | LN-120, LN-121 | Diturunkan ke UAT RD-09, INT-06; hasil sumber tidak disalin sebagai PASS. |
| RACC-16 | Health dan versi | LN-120, LN-121, LN-122 | Diturunkan ke UAT RD-11, PR-11; hasil sumber tidak disalin sebagai PASS. |
| RACC-17 | Rotation/deployment | LN-120, LN-121 | Diturunkan ke UAT HH-08, RD-10, INT-09, INT-10; hasil sumber tidak disalin sebagai PASS. |
| RACC-18 | Kapasitas batch/concurrency | LN-120, LN-121, LN-122 | Diturunkan ke UAT HH-09, RD-05, PR-02; hasil sumber tidak disalin sebagai PASS. |
| RACC-19 | E2E transfer dan cross-dock | LN-120 | Diturunkan ke UAT INT-03; hasil sumber tidak disalin sebagai PASS. |
| RACC-20 | Pilot dan rekonsiliasi | LN-120 | Diturunkan ke UAT INT-01, INT-02, INT-03, INT-04; hasil sumber tidak disalin sebagai PASS. |
| RACC-21 | PoC CP30EN | LN-120, LN-122 | Diturunkan ke UAT PR-01; hasil sumber tidak disalin sebagai PASS. |
| RACC-22 | Routing dan concurrent connector | LN-120, LN-122 | Diturunkan ke UAT PR-02, PR-03; hasil sumber tidak disalin sebagai PASS. |
| RACC-23 | EPC chip dan template | LN-120, LN-122 | Diturunkan ke UAT PR-01, PR-11; hasil sumber tidak disalin sebagai PASS. |
| RACC-24 | Printed, encoded dan verified | LN-120, LN-121, LN-122 | Diturunkan ke UAT PR-05, HH-04, INT-01; hasil sumber tidak disalin sebagai PASS. |
| RACC-25 | Partial batch dan error | LN-120, LN-122 | Diturunkan ke UAT PR-06, INT-08; hasil sumber tidak disalin sebagai PASS. |
| RACC-26 | Lost ACK dan crash | LN-120, LN-122 | Diturunkan ke UAT PR-07, PR-08, INT-07; hasil sumber tidak disalin sebagai PASS. |
| RACC-27 | Lease expire dan printer offline | LN-120, LN-122 | Diturunkan ke UAT PR-03, PR-08; hasil sumber tidak disalin sebagai PASS. |
| RACC-28 | Reprint dan retag | LN-120, LN-122 | Diturunkan ke UAT PR-09, INT-12; hasil sumber tidak disalin sebagai PASS. |
| RACC-29 | UI printer dan dokumen | LN-120, LN-122 | Diturunkan ke UAT PR-11; hasil sumber tidak disalin sebagai PASS. |
| RACC-30 | Recovery setelah ACK server | LN-120, LN-122 | Diturunkan ke UAT PR-10, INT-11; hasil sumber tidak disalin sebagai PASS. |

## RFID_REQ

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| RFID-01 | Identitas perangkat, firmware, SDK dan PoC nyata | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-02 | Kontrak API ERP dan compatibility seluruh jalur ingest | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-03 | Aplikasi Android C72 dengan adapter SDK | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-04 | Workflow C72: verifikasi tag, loading, opname dan alamat | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-05 | Adapter fixed reader UR300 dan kontrol lokal | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-06 | Gate passage, arah dan kelengkapan manifest | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-07 | Outbox offline, deduplikasi dan replay terkontrol | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-08 | Device health, deployment dan operasi middleware | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-09 | Identitas operator, scope dan traceability | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-10 | UAT perangkat nyata dan integrasi seluruh rantai WMS | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-11 | Profil CP30EN, firmware, koneksi, media dan PoC encoding | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-12 | Printer connector, routing job, lease dan attempt | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-13 | Cetak label, tulis EPC dan bukti hasil per item | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-14 | Gagal cetak, hasil ambigu, reprint dan penggantian tag | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |
| RFID-15 | Antarmuka printer, template dan jejak operasional per gudang | LN-120, LN-121, LN-122 | Reconcile kontrak/ERP dan UAT; pembangunan aplikasi perangkat di luar paket ERP ini. |

## RFID_STAGE

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| RF00 | PoC perangkat dan pemetaan SDK | LN-120 | Status workstream terpisah; hanya parity/integrasi dan readiness masuk gelombang ERP. |
| RF01 | API ERP dan fondasi middleware | LN-120 | Status workstream terpisah; hanya parity/integrasi dan readiness masuk gelombang ERP. |
| RF02 | Aplikasi dan workflow C72 | LN-120 | Status workstream terpisah; hanya parity/integrasi dan readiness masuk gelombang ERP. |
| RF03 | Adapter gate UR300 dan passage | LN-120 | Status workstream terpisah; hanya parity/integrasi dan readiness masuk gelombang ERP. |
| RF-P | Connector CP30EN, print-encode, verifikasi dan recovery | LN-120 | Status workstream terpisah; hanya parity/integrasi dan readiness masuk gelombang ERP. |
| RF04 | E2E hardware, pilot dan penutupan integrasi | LN-120 | Status workstream terpisah; hanya parity/integrasi dan readiness masuk gelombang ERP. |

## PRODUCTION_ROUTE

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| PRD-20261016 | Owner menyetujui penambahan rute supplier/makloon ke paket implementasi | LN-033, LN-143 | Persetujuan chat 16 Oktober: tambahkan kekurangan yang telah divalidasi; tidak mengesahkan implementasi selesai. Lihat IMPLEMENTASI_PRODUKSI_SUPPLIER_MAKLOON.md |

## ROLE_RND

| ID | Catatan sumber | Requirement aktif | Disposisi/pengingat |
|---|---|---|---|
| OWNER-20261016 | Hak akses rinci; revalidation gagal menunggu keputusan PIC | LN-015, LN-034 | Keputusan owner pada chat 16 Oktober 2026. Rancangan rinci: CUSTOM_ROLE_DAN_REVALIDASI_RND_REV1_3.md |


## Batas dan catatan penting

- 126 statement mencakup konteks meeting, WMS, fingerprint dan middleware yang telah dirapikan sebelumnya. Statement yang dipetakan boleh menjadi reuse/validasi, tidak harus fitur baru.
- Sisa P06–P10 dan koreksi P01–P05 ditangani menurut BASELINE_DAN_PLAN_LAMA. Status implementasi lama tidak otomatis menjadi status gelombang baru.
- Kontrak middleware dan skenario perangkat dibawa sebagai referensi parity ERP dan UAT. Pembangunan adapter/APK merupakan workstream terpisah.
- Audit wave 1–3 tetap memiliki tracker tersendiri. Review seluruh kode repo tidak diklaim selesai oleh dokumen ini.
- Bukti analisis terdahulu terbatas pada snapshot dan fungsi yang diperiksa; bukan hasil uji rilis baru.
