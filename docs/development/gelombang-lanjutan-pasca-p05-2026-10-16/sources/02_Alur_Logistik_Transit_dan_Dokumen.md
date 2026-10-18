# Alur Pengumpulan Gudang, Transit dan Pengiriman

**ERP Kain Nussantara — Produksi IT PT Kubus Teknologi Indonesia**  
**16 Oktober 2026 · Usulan untuk ditinjau berdasarkan jawaban pemilik, belum implementasi**

## Pernyataan yang menjadi dasar

Anda menjelaskan satu lokasi bisa memiliki banyak gudang; picking list dipakai mengumpulkan barang dari gudang sumber; SJ diterbitkan di gudang transit setelah validasi handheld; satu dispatch/armada dapat membawa beberapa SO. Tujuan pertama bisa Jakarta transit, lalu Jakarta menerbitkan SJ baru ketika mengirim ke customer. Perjalanan fisik juga dapat terkait transfer maupun pembelian antar-entitas.

Pola pengambilan→area konsolidasi→pengiriman, penggabungan beberapa SO dalam satu load, serta hub dengan load lanjutan mempunyai padanan pada dokumentasi enterprise. Penerapan berikut adalah sintesis untuk KN, bukan aturan universal nama/nomor dokumen. [Dynamics 365: beberapa SO dalam satu load](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/confirm-and-transfer), [Dynamics 365: hub consolidation](https://learn.microsoft.com/en-us/dynamics365/supply-chain/transportation/plan-loads-hub-consolidation).

## 1. Istilah yang dipakai

| Istilah | Arti untuk project ini | Contoh |
|---|---|---|
| Lokasi | Site/tempat operasional yang menaungi beberapa gudang | Rancamalang; Jakarta |
| Gudang | Unit pengelolaan stok fisik dalam lokasi | Gudang Woven; Gudang Knitting; Gudang Transit |
| Picking list | Perintah pengambilan roll dari alamat simpan | Ambil roll X dari gudang Woven/rak tertentu untuk SO-01 |
| Transfer/konsolidasi internal | Perpindahan fisik barang antar unit gudang tanpa penjualan customer | Woven Rancamalang→Transit Rancamalang |
| SJ | Dokumen isi barang aktual pada satu keberangkatan yang terkait SO/transfer/transaksi asal | SJ transit Rancamalang→Jakarta; SJ Jakarta→customer |
| Dispatch/perjalanan | Satu keberangkatan kendaraan pada rute/segmen tertentu | Kendaraan T, Rancamalang→Jakarta, tanggal tertentu |
| Dispatch Notes/manifest | Daftar seluruh muatan dan referensi SJ/dokumen pada perjalanan | SO-01, SO-02, SO-03 di kendaraan T |
| Segmen perjalanan | Satu tahap asal→tujuan; keberangkatan berikutnya punya identitas sendiri | Segmen 1 ke Jakarta; segmen 2 ke customer |

Picking list adalah sumber instruksi pekerjaan; bukti scan/pengambilan adalah hasil pelaksanaan. Barang yang masih di gudang sumber tidak boleh dipindah ke transit pada data hanya karena picking list dicetak.

## 2. Matriks dokumen dan dampaknya

| Dokumen/kejadian | Lingkup yang direkomendasikan | Dampak stok | Dampak pada SO/customer |
|---|---|---|---|
| Picking list | Gudang sumber + pekerjaan pengambilan + kaitan SO/roll | Belum mengurangi stok terjual; catat pick/staging sesuai realisasi | Menunjukkan pekerjaan persiapan |
| Serah terima gudang sumber→transit | Asal/tujuan aktual + roll yang diserahkan | Berpindah lokasi simpan, owner dan komitmen tetap jika tidak ada transaksi owner | Belum serah terima customer |
| SJ transfer/transit | SO kebutuhan dan/atau transfer asal; satu tujuan/entitas penerbit per dokumen | Stok dalam perjalanan menuju lokasi internal | Belum dianggap customer menerima barang |
| Manifest/Dispatch Notes | Semua muatan pada satu perjalanan kendaraan | Tidak menambah mutasi stok kedua di luar dokumen asal | Menggabungkan perjalanan, bukan menggabungkan piutang beberapa SO |
| Penerimaan Jakarta | SJ transfer/roll aktual | Roll benar-benar diterima di transit Jakarta; selisih tercatat | Sisa kebutuhan/komitmen SO tetap ditelusuri |
| SJ Jakarta→customer | SO + pengiriman aktual dari Jakarta | Pengeluaran fisik customer pada kejadian yang benar | Pemenuhan SO mengikuti transaksi customer, tidak diulang karena transit |
| POD/tanda terima customer | Pengiriman customer dan penerima aktual | Mengakhiri perjalanan/status sesuai prosedur | Membedakan berangkat dari customer sudah menerima |

**SJ per SO perlu diperjelas sebagai per SO per keberangkatan aktual.** SO yang dikirim dua kali tidak dipaksa memakai satu nomor dokumen untuk dua kejadian. Satu SO berisi banyak artikel dapat dicantumkan dalam satu SJ konsolidasi pada keberangkatan yang sama. Jika legal entity, tujuan atau kejadian berangkat berbeda, dokumen dipisahkan dan referensinya dipertahankan. Format nomor serta istilah SJ Transfer/SJ Customer masih usulan penamaan, bukan ketentuan hukum yang dinyatakan dari riset ini.

Rencana perjalanan boleh disiapkan sebelum pick selesai. Manifest final/SJ final berisi realisasi setelah scan; mencetak draft rencana tidak sama dengan mengesahkan keberangkatan atau mengakui penjualan.

## 3. Contoh tiga SO dari beberapa gudang Rancamalang

Contoh berikut ilustrasi, bukan data ERP: SO-01 berisi woven dan printing; SO-02 berisi knitting; SO-03 berisi woven. Semua milik satu entitas penjual dan dijadwalkan ke transit Jakarta menggunakan satu armada. Contoh lintas entitas dijelaskan terpisah.

| Langkah | Aktor/menu kerja yang diusulkan | Input | Sistem memproses | Output |
|---|---|---|---|---|
| 1. Finalisasi | Admin Sales, detail SO/pemenuhan | SO, artikel, qty/roll, harga final, tujuan customer, kebutuhan QC | Memastikan roll layak dan kepemilikan sudah benar; harga/approval sesuai alokasi | SO dan daftar roll final yang siap dipersiapkan |
| 2. Rencanakan konsolidasi | Admin Gudang/Logistik | Gudang sumber, transit tujuan, SO/roll, rute Rancamalang→Jakarta | Membuat hubungan pekerjaan asal dengan rencana perjalanan; belum dispatch customer | Rencana konsolidasi dan perjalanan |
| 3. Picking list | Gudang sumber, pekerjaan picking | Picking list per sumber/pekerjaan | Menunjukkan alamat simpan, kode roll, qty, tujuan transit dan SO terkait | Dokumen instruksi pengambilan |
| 4. Ambil roll | Petugas yang diberi akses | Scan roll sumber dan konfirmasi pengambilan | Memeriksa cocok/tidaknya roll; mencegah ambil roll SO lain | Bukti roll diambil; daftar selisih bila ada |
| 5. Terima di transit | Petugas Transit Rancamalang | Scan serah terima dari gudang sumber | Memindahkan keberadaan fisik ke transit secara tercatat, menjaga owner/reservasi | Stok fisik transit yang siap dikonsolidasi |
| 6. Selesaikan QC bila diminta | Meja QC | Permintaan dan roll alokasi SO | Memeriksa hasil/cakupan; roll pengganti tidak memakai hasil roll lama | Status mutu yang dapat ditelusuri |
| 7. Validasi muatan | Petugas loading dengan C72 | Daftar semua roll perjalanan dan scan fisik | Menampilkan missing/extra/salah SO/roll ganda; menandai hasil basi jika alokasi/qty berubah | Muatan tervalidasi atau exception untuk ditindaklanjuti |
| 8. Sahkan dokumen | Transit Rancamalang/Logistik | Muatan aktual yang sudah sesuai, kendaraan, sopir, tujuan internal | Membentuk dokumen SJ transit per SO/kelompok yang sah dan manifest seluruh perjalanan | SJ-T-01, SJ-T-02, SJ-T-03, manifest D-01 |
| 9. Berangkat | Logistik/gate | Dokumen final dan scan keberangkatan | Mencatat dalam perjalanan internal; tidak memanggil customer dispatch sebagai pengganti transfer | Jejak Rancamalang→Jakarta |

Yang dikumpulkan adalah barang aktual, bukan hanya lembar picking list. Scan di transit harus dibandingkan dengan daftar roll yang direncanakan untuk perjalanan itu; membandingkan masing-masing SO saja belum memastikan seluruh isi kendaraan benar.

Jika Gudang Transit adalah record gudang berbeda dari gudang Woven/Knitting, perpindahan antar-gudang harus tercatat, meskipun alamat lokasinya sama. Tidak boleh memalsukan `warehouse_id` agar cetakan SJ seolah diterbitkan dari transit. Bila transit merupakan area dalam gudang yang sama, gunakan perpindahan alamat internal yang sesuai model WMS. Ini pilihan representasi mengikuti master lokasi/gudang aktual, bukan menyamakan Lokasi dengan Gudang.

## 4. Penerimaan dan pengiriman lanjutan di Jakarta

1. **Antrean penerimaan Jakarta** menampilkan dokumen perjalanan/SJ transit asal, jumlah roll dan referensi SO.
2. Petugas memindai barang yang turun. Sistem membandingkan dengan roll yang benar-benar diberangkatkan, bukan seluruh qty SO yang mungkin belum dikirim.
3. Roll yang cocok diterima di gudang transit Jakarta; stok fisik asal berkurang dan tujuan bertambah sesuai satu mutasi yang sah. Roll tetap dialokasikan pada SO jika kebutuhan itu masih berlaku.
4. Kekurangan, kerusakan atau salah roll dicatat per roll. Roll yang belum tiba tetap dapat ditelusuri; receiving tidak boleh dipaksa penuh agar dokumen terlihat selesai.
5. Untuk keberangkatan ke customer, petugas merencanakan perjalanan lanjutan dari Jakarta. Kendaraan dan pengelompokan SO dapat berbeda dari perjalanan Rancamalang→Jakarta.
6. Validasi muatan fisik lagi di Jakarta. Bukti scan keberangkatan Rancamalang tidak otomatis membuktikan muatan Jakarta masih sama.
7. Terbit **SJ baru Jakarta→customer**, dengan referensi SO dan dokumen transit/roll asal. Manifest baru berisi hanya muatan perjalanan lanjutan tersebut.
8. Catat keberangkatan customer dan selanjutnya POD. Penerimaan internal di Jakarta tidak pernah dijadikan POD customer.

Rantai referensi contoh: **SO-01 → picking sumber → transfer/konsolidasi transit → SJ-T-01 / D-01 → receiving Jakarta → SJ-C-01 / D-02 → POD customer**. ID roll yang sama menautkan setiap tahapan; roll tidak dibuat ulang hanya karena berpindah gudang.

## 5. Kepemilikan barang dan pembelian antar-entitas

Ada tiga dimensi yang harus selalu dapat dibedakan: **di mana fisik barang**, **siapa owner**, dan **SO siapa yang akan dipenuhi**.

- **Satu entitas, beda gudang/lokasi:** transfer fisik menjaga owner. Perpindahan itu sendiri bukan penjualan customer.
- **Beda entitas:** transaksi jual beli internal menyelesaikan pergantian owner dan pencatatan pasangan dokumen entitas penjual/pembeli. Pembayaran dapat menyusul sesuai ketentuan yang telah disepakati.
- **Armada shared:** manifest operasional dapat mengangkut beberapa entitas bila diizinkan, tetapi dokumen penerbit, owner roll, AP/AR internal dan customer tidak disatukan. Hak akses tiap pihak tetap diterapkan.

Satu perjalanan tidak wajib satu transaksi. Sebaliknya, satu transaksi/SO bisa melewati lebih dari satu perjalanan. Jika satu pergerakan fisik sudah digunakan untuk menyerahkan transaksi internal, jangan membuat perpindahan stok kedua untuk roll yang sama hanya karena menambah referensi transfer. Saat serah owner mana yang dipakai harus mengikuti transaksi internal yang sah, tanpa menebak transfer fisik berarti owner otomatis berubah.

Fondasi existing sudah menolak transfer terkait SO bila owner berbeda dan mengingatkan agar membuat transaksi antar-PT. Ini harus dipertahankan ketika membangun konsolidasi perjalanan. [E25: backend/services/transfer_receipt_service.py:73](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/transfer_receipt_service.py#L73).

## 6. Kekurangan dan keputusan kasus

Sesuai jawaban nomor 9, sistem memberikan fakta dan aksi bagi petugas berhak: tunggu sisa barang, kirim pengganti, kembalikan barang, atau sepakati transaksi hanya sebesar roll yang ada disertai amandemen SO bila diperlukan. Tidak ada pemotongan sisa qty otomatis berdasarkan toleransi baru.

Pisahkan penyelesaian **fisik transfer**, **kebutuhan customer**, dan **nilai komersial**. Contoh: SO diamandemen menjadi delapan roll tidak berarti dua roll hilang di perjalanan boleh langsung dihapus tanpa jejak. Jika hanya delapan roll yang dikirim, SJ/manifest menyebut delapan; dua roll lain tidak dicetak seolah ikut kendaraan.

## 7. Apa yang sudah ada dan apa yang harus diselaraskan

| Kemampuan sekarang | Bukti | Kesimpulan untuk skenario Anda |
|---|---|---|
| Pengambilan, SJ per tugas/product/gudang | [E21: backend/services/shipment_service.py:94](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/shipment_service.py#L94) | Fondasi ada; penggabungan multi-produk SO di transit belum sama dengan bentuk sekarang |
| Logistik, kendaraan, sopir dan kumpulan SJ | [E20: backend/services/logistics_service.py:144](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/logistics_service.py#L144) | Fondasi ada; guard satu pesanan secara eksplisit memblokir satu pengiriman banyak SO |
| Final Loading Check fisik | [E23: backend/services/loading_check_service.py:158](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/loading_check_service.py#L158); [E24: backend/services/loading_check_service.py:195](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/loading_check_service.py#L195) | Fondasi ada; scope SO/gudang perlu diperluas/diorkestrasi untuk manifest perjalanan tanpa melemahkan cek roll |
| Transfer terkait SO dan receiving per roll | [E25: backend/services/transfer_receipt_service.py:73](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/transfer_receipt_service.py#L73); [E26: backend/services/transfer_receipt_service.py:236](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/transfer_receipt_service.py#L236) | Dapat dipakai untuk transit internal, tidak membebaskan dari transaksi antar-entitas |
| Dispatch penjualan mengubah status SO dan memanggil GL | [E22: backend/services/shipment_service.py:132](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/shipment_service.py#L132) | Tidak aman secara makna proses bila dipakai begitu saja untuk transit internal |

Uji fungsi asli terisolasi membuktikan tiga SJ dengan tiga SO ditolak `create_delivery`; beberapa SJ satu SO melewati guard yang diuji. Uji berhenti sebelum pembuatan dokumen/DB. Ini bukti batas fungsi sekarang, bukan uji armada fisik.

## 8. Batas usulan

Yang jelas dari pemilik: beda lokasi/gudang, konsolidasi transit, handheld, multi-SO per armada, transit Jakarta dan SJ baru, serta penerapan pada transfer/internal purchase. Rincian penamaan SJ transit, satu dokumen per SO×keberangkatan, dan parent manifest lintas dokumen adalah rancangan yang direkomendasikan untuk ditinjau. Tidak ditetapkan kebijakan pajak atau momen pengakuan pendapatan baru; yang harus dijaga adalah perjalanan internal tidak keliru memicu pengakuan customer atau nilai ganda.
