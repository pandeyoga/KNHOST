# Memo jawaban kebutuhan klien — MD, R&D, master, stok, pembelian dan gudang

Tanggal pemeriksaan:2026-10-03. Basis kode: `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Memo menjawab kondisi **snapshot yang diaudit**, bukan menyatakan konfigurasi deployment atau perbaikan terbaru sudah diverifikasi. Nomor mengikuti12 penjelasan terakhir pengguna; poin7 dan8 memisahkan greige dan lot dari poin7 catatan awal. C/H tidak ditafsirkan sebagai entitas atau gudang tertentu.

Kesepakatan bisnis: SKU hasil pengembangan MD mengikuti sampling sesuai lini; woven/knitting umumnya labdip+handfeel, printing proofing dan handfeel bila diperlukan. Bahan seperti benang/greige boleh dibuat langsung tanpa melewati semua sampling. Seluruh roll barang dalam kedua jalur penerimaan harus bertag RFID; perbedaannya adalah disimpan atau langsung cross-dock.

Status **tersedia** berarti ada jalur implementasi yang ditemukan, bukan semua variasi telah lolos UAT. **Sebagian/gap** berarti sebagian kebutuhan tersedia tetapi belum memenuhi seluruh kontrak klien. Bukti utama adalah penelusuran backend dan frontend; probe runtime terbatas dijelaskan di akhir. Tidak ada perubahan source aplikasi.

## Ringkasan jawaban

| No | Kebutuhan yang dirapikan | Kesimpulan |
|---|---|---|
|1|MD dibagi menurut lini, jenis pekerjaan, izin aksi dan riwayat pelaksana|Sebagian tersedia; ada bug pembatasan lini W2-025. Hak khusus per jenis sampling belum terbukti tersedia.|
|2|Master item/warna/kode konsisten untuk bahan hingga barang jadi|Struktur dasar cukup baik; standar penamaan dan tata kelola belum otomatis terselesaikan.|
|3|Master langsung untuk bahan; SKU hasil MD lahir melalui ACC R&D|Kedua jalur ada. ACC sample, ACC spesifikasi dan release adalah langkah berbeda; enforcement seluruh uji wajib perlu diperkuat/divalidasi.|
|4|Sales melihat stok agregat grup tanpa mengetahui pemilik|Backend menyediakan agregat; layar yang ditelusuri belum sepenuhnya mengikuti POV tunggal yang diminta. Interco tetap proses tersendiri.|
|5|MD bekerja lintas entitas tanpa sering berpindah konteks|Bisa diberi hak beberapa entitas/lini; pembuatan PO standar tetap mengikuti entitas aktif.|
|6|Penerimaan10 roll aktual960 dari pesanan1000, keputusan sisa dan pembayaran|Pengukuran aktual, variance, sisa penerimaan, short-close dan amendment ada; notifikasi MD spesifik serta otomatisasi Finance belum lengkap.|
|7|SO→makloon mengamankan greige sejak keputusan pemenuhan|Sourcing dan issue makloon ada; pada jalur yang ditelusuri keputusan/create order belum mereservasi bahan.|
|8|Lot internal dan lot pabrik jelas, bisa ditelusuri dan dikoreksi|Master lot, nomor internal, supplier lot dan genealogy ada; rename internal bukan aksi patch biasa.|
|9|Pesan berdasarkan panjang atau roll dengan jumlah aktual terlihat|Pilihan roll dan reconcile naik/turun/potong tersedia. Hasil mengikuti urutan roll; tidak otomatis selalu905 untuk pembulatan turun.|
|10|SO multi-produk dipenuhi beberapa gudang hingga driver menerima SJ|Task per gudang, shipment dan SJ per shipment/per gudang tersedia; SOP konsolidasi dan printer perlu ditetapkan.|
|11|Stok rutin disimpan; barang untuk SO langsung transit/cross-dock; semua bertag|Dua routing tersedia. Kewajiban RFID belum boleh dianggap terjamin hanya karena fitur auto-tag/print ada.|
|12|Benang, greige, PFD, PFP adalah tahap bahan yang tidak tercampur|Tahap tersebut tersedia eksplisit dan digunakan proses makloon; bedakan stage, lini, jenis kain dan status lokasi.|

## 1. Pembagian MD dan histori pekerjaan

Sistem mempunyai beberapa lapisan: role/custom role menentukan modul dan aksi; penugasan entitas menentukan badan usaha; `allowed_line_codes` menentukan lini woven/knit/printing; jenis sampling menentukan labdip/proofing/handfeel. Membuat role “MD Printing” saja tidak cukup: entitas, lini, hak create/submit/assess/decide dan kebijakan approver juga harus diatur.

Lini bukan jenis kain fisik: printing bisa memakai kain woven maupun knit. Jenis sampling juga bukan role. Master lini menyediakan usulan sampling, dengan default woven/knit→labdip+handfeel dan printing→proofing. Ini cocok dengan klarifikasi pengguna; tidak perlu memaksa semua SKU menjalani tiga uji.

Riwayat menyimpan pembuat, pelaku submit hasil (`performed_by`), assessor, finisher dan timeline. Karena submit menyimpan **nama akun yang memasukkan hasil**, ini belum otomatis membuktikan orang itu pelaksana fisik labdip. Wiwi dan Tita perlu akun masing-masing; bila satu orang menginput untuk orang lain, perlukan field penanggung jawab/pelaksana terpisah. Modal histori lintas warna menampilkan putaran/mitra/hasil; nama pelaku terdapat pada detail round/catatan, bukan kolom utama modal tersebut.

**Cacat terkonfirmasi:** akun yang hanya diizinkan woven tidak melihat sample printing di daftar, tetapi masih dapat membuka dan mengubah judul sample printing melalui endpoint detail dalam entitas yang sama. W2-025 direproduksi melalui API. Maka pagar lini belum boleh dinyatakan aman untuk pemisahan jobdesk sebelum diperbaiki. Selain itu, assignment lini kosong berarti semua lini dan dokumen tanpa lini tetap terlihat—ini perilaku kompatibilitas yang disengaja, sehingga master lama harus diklasifikasi dahulu.

Hak aksi R&D yang diperiksa berbasis modul (`rnd.submit`, `rnd.assess`, dll.), belum ada bukti aturan “boleh assess labdip tetapi tidak handfeel” per akun pada jalur round. Bila itu diperlukan selain pemisahan lini, catat sebagai kebutuhan tambahan, bukan menganggap filter tab sudah menjadi izin.

Bukti: `role_registry.py:213`; `services/line_scope.py:1–180`; `services/master_registry.py:393`; `routers/rnd.py:80,294,372,384,471,487`; `services/rnd_sample_service.py:858–889`; `frontend/src/features/rnd/LabdipHistoryModal.jsx`; `SampleRoundList.jsx:158`. [Rincian W2-025 dan gap](26_TAMBAHAN_KLIEN_DAN_W2_025.md).

## 2. Struktur master data dan standar penamaan

Struktur yang tersedia sudah memisahkan beberapa hal penting:

| Dimensi | Fungsi | Contoh |
|---|---|---|
|Template/induk produk|Keluarga produk dan atribut varian|Satu keluarga kain dengan beberapa warna/lebar|
|Produk/SKU|Identitas item yang dibeli, dijual atau diproses|SKU greige berbeda dari SKU hasil dyeing|
|`stage`|Tahap barang|yarn, grey, pfd, pfp, finished, remnant, byproduct|
|`fabric_type`|Konstruksi fisik kain|woven, knit|
|`line_code`|Pembagian pekerjaan bisnis|woven, knit, printing|
|Satuan dan spesifikasi|Basis jumlah dan karakteristik teknis|meter/yard/kg, GSM, lebar, yarn count|
|Master warna internal|Identitas warna perusahaan|kode/nama/hex/sistem/family|
|Referensi supplier/customer|Nama/kode versi pihak luar dan pemilik eksklusivitas|kode warna pabrik, warna khusus customer|
|Lot dan roll|Batch dan identitas fisik persediaan|lot internal, supplier lot, nomor roll|

**Penilaian:** struktur dasarnya masuk akal, tetapi belum cukup untuk menyebut master ideal. Ada kompatibilitas field lama seperti warna teks bebas dan lifecycle/lini kosong. Standar penamaan perusahaan belum diberikan; kode tidak bisa menentukan sendiri apakah dua nama merupakan item sama. Perlu kamus istilah, field wajib menurut tahap, aturan duplikasi, master owner dan proses koreksi.

Usulan: SKU stabil sebagai identitas; nama produk dapat diperbaiki tanpa membuat SKU baru untuk sekadar typo. Tahap/proses/warna/lebar menjadi atribut eksplisit, bukan hanya teks nama. Buat SKU terpisah bila barang secara fisik/komersial berbeda atau berubah tahap dan perlu saldo terpisah. Jangan memasukkan nama entitas/gudang ke SKU sekadar untuk memisahkan kepemilikan; pemilik dan lokasi sudah dimensi stok tersendiri. Ini usulan tata kelola, bukan skema penamaan yang sudah berlaku.

Bukti: `schemas.py:210,250`; `domain_registry.py:53–88`; `services/product_template_service.py`; `services/product_variant_service.py`; `services/color_service.py:1–7`; `routers/products.py:93–131`.

## 3. Menambah/nonaktifkan master dan alur R&D sampai SKU

**Tanpa R&D:** route create product tersedia dengan izin `product.create`; SKU diperiksa agar tidak duplikat dan atribut domain/lini divalidasi. Ini jalur yang sesuai untuk bahan standar yang tidak memerlukan pengembangan MD. Lifecycle tetap harus sesuai kebijakan; create master tidak berarti semua item boleh langsung dijual. HPP tidak diisi manual pada create, tetapi berasal dari transaksi/valuasi.

**Penghapusan:** aksi delete produk yang ditelusuri mengubah status menjadi inactive, bukan menghapus fisik. Warna juga dinonaktifkan. Ini membantu mempertahankan referensi histori. Tetap perlu menguji dampaknya pada dokumen terbuka dan memastikan alternatif SKU yang dipakai selanjutnya; jangan mengartikan tombol delete sebagai menghapus semua histori.

**Melalui MD/R&D:**

1. Tetapkan lini, kebutuhan produk/spesifikasi, warna target dan jenis sampling yang diwajibkan menurut lini.
2. Buat permintaan sample; proses round per mitra/jenis; unggah hasil dan ukur; nilai ACC/revisi/tolak. Sample jadi dan dikirim juga memiliki pencatatan tersendiri.
3. Putuskan mitra/pemenang dan harga; sistem dapat membentuk kontrak/item supplier serta menyimpan kode/nama warna supplier.
4. Opsi `approve_spec` pada keputusan sample dapat sekaligus menyetujui spesifikasi dan membuat/menghubungkan SKU. Opsi ini tidak selalu aktif; kesalahan pembentukan master dapat dicatat sebagai `master_error`. Karena itu keputusan sample tidak boleh dianggap jaminan SKU sudah lahir.
5. ACC spesifikasi menghasilkan lifecycle `disetujui`; aksi release terpisah mengubahnya menjadi `produksi`. Penegakan boleh dipesan bergantung kebijakan lifecycle off/warn/block. Data legacy dengan lifecycle kosong dianggap produksi.

**Gap penerapan uji wajib:** pada service keputusan yang dibaca, prasyarat eksplisit adalah terdapat round ACC dari supplier yang dipilih; belum ditemukan pemeriksaan seluruh jenis sampling yang diwajibkan sudah ACC. Approval spesifikasi/release juga perlu dicek sebagai jalur terpisah agar tidak melewati prasyarat tersebut. Ini kandidat gap workflow yang perlu regression lifecycle lengkap, belum temuan runtime tambahan. Kriteria yang dibutuhkan adalah semua uji **yang diwajibkan untuk SKU hasil MD itu**, bukan semua tiga uji untuk semua bahan.

**Warna sebaiknya lahir di mana?** Master warna internal menjadi acuan target sebelum/selama spesifikasi dan sample. Hasil ACC mengikat versi/kode warna supplier ke identitas internal tersebut; jangan mengganti kode internal dengan kode pabrik. Kode/nama supplier memang tersedia melalui `supplier_variants` dan disalin ke master terkait. Warna customer ditangani dengan keterkaitan produk/customer, `exclusive_customer_id` dan izin pemakaian. Itu tidak otomatis sama dengan katalog alias kode warna customer yang berbeda per pelanggan; kebutuhan alias customer seperti itu belum dijelaskan dan dukungan penuh belum dibuktikan. Jangan menyatukan warna hanya karena nama/hex mirip; ACC fisik dan hak penggunaan tetap relevan.

Bukti: `routers/products.py:93,231`; `services/color_service.py:130,244,336`; `services/rnd_sample_service.py:1006–1147`; `services/rnd_spec_service.py:299–422`; `services/rnd_gate.py:1–78`; `frontend/src/features/rnd/DecideModal.jsx:48`.

## 4. POV sales: stok grup, reserved, incoming dan available to order

Sistem mempertahankan stock per produk×gudang×owner. Melihat stok grup tidak memindahkan hak milik. Untuk SO entitas A yang dipenuhi stok B, jalur internal request/interco menyediakan dokumen pembelian/penjualan internal, ship/receive dan jurnal pasangan sebelum alokasi sesuai owner. Fulfillment wizard juga menawarkan draft interco untuk kekurangan stok.

Backend inventory board memiliki `global_total` (available/reserved/incoming/ATP agregat tanpa rincian owner untuk role terbatas), sedangkan `by_entity` dan total utama mengikuti entitas yang diizinkan/aktif. **Layar InventoryStatusBoard yang ditelusuri menampilkan total sendiri serta informasi “tersedia di badan usaha lain”, bukan seluruh angka grup sebagai satu set angka utama.** Jadi dasar datanya ada, tetapi POV yang diminta belum persis sama.

Alternatif saat ini: sales melihat stok sendiri plus indikasi stok entitas lain lalu meminta Admin Sales menentukan interco. Target perubahan: tampilan sales utama berisi stok grup, reserved dan incoming grup, tanpa nama owner; backend tetap menjaga owner, biaya, pajak dan transaksi interco. Bedakan “tersedia di grup” dengan “sudah aman dijanjikan untuk SO ini”. ATP pada modul ini merupakan available+incoming; jangan otomatis menyebutnya jaminan pemenuhan bertanggal atau bahan yang sudah dicadangkan. Semua alokasi harus mencegah stok yang sama dijanjikan dua kali.

Bukti: `services/fulfillment_service.py:45–133,270–361`; `services/fulfillment_wizard_service.py:33–113`; `services/fulfillment_decision_service.py:1–30`; `frontend/src/features/inventory/InventoryStatusBoard.jsx:210–268`.

## 5. MD lintas entitas saat membuat PO

Lini menentukan produk yang ditangani MD; entitas menentukan pihak yang bertransaksi. MD dapat ditugaskan ke beberapa entitas dan beberapa lini, tetapi satu PO tetap harus mempunyai entitas pembeli yang tegas. Route create PO standar mengambil `active_entity_id` dari konteks sesi dan meneruskannya ke core create. Daftar PO mendukung filter scope entitas dan lini.

Dengan jalur standar ini, MD perlu berada pada konteks pembeli yang benar sebelum membuat PO. Tidak tepat menyatakan mode “semua entitas” otomatis memilih badan usaha pembeli berdasarkan lokasi barang. Belum terbukti ada satu meja kerja MD yang sekaligus memilih buyer per transaksi tanpa perpindahan konteks.

Alternatif UI yang disarankan: daftar kerja lintas entitas sesuai hak MD, dengan pilihan “dibeli oleh” yang eksplisit saat membuat/realisasi PO, sumber kebutuhan SO/PR terisi, dan validasi supplier/gudang/kontrak/buku entitas. Ini penyederhanaan antarmuka, bukan menghapus pemisahan pembukuan.

Bukti: `routers/purchase_orders.py:216–270,330`; `services/pr_sourcing_service.py:670–710`; `services/line_scope.py`.

## 6. Pesan10 roll×100 yard, datang10 roll dengan total960 yard

Ini selisih panjang, bukan gramasi/GSM. Sistem penerimaan mendukung panjang aktual per roll, jumlah roll, satuan dokumen dan konversi ke satuan dasar. Panjang aktual tidak seharusnya dipaksa menjadi100 untuk menyesuaikan PO.

| Keputusan bisnis | Dukungan sistem | Yang perlu dijaga |
|---|---|---|
|Sisa40 masih ditunggu|GRN parsial dan remainder task tersedia; pembentukan sisa mempertimbangkan toleransi|PO tetap mencatat pesanan dan received aktual; jangan menganggap toleransi berarti supplier boleh ditagih penuh tanpa persetujuan.|
|Sisa tidak akan dikirim|Short-close PO dengan alasan tersedia; task terbuka dibatalkan setelah guard GRN aktif|Short-close mengubah status, **bukan otomatis mengubah qty/harga/nilai PO**.|
|Kesepakatan pembelian direvisi menjadi960|Amendment dengan histori versi, perhitungan nilai dan evaluasi approval tersedia|Amendment hanya status tertentu; `closed_short` bukan status amendable. Putuskan urutan revisi sebelum short-close.|
|Sudah ada pembayaran/tagihan|Perlu rekonsiliasi utang, DP/kelebihan bayar, tagihan dan koreksi yang terkait|Jangan menganggap mengedit PO otomatis membalik GL atau mengembalikan dana. Validasi end-to-end masih diperlukan.|

Source ringkasan keuangan PO menggunakan grand_total/total_amount dikurangi retur dan pembayaran, sambil menampilkan received_value terpisah. Maka penerimaan960 **tidak otomatis** menjadikan basis outstanding960 jika dokumen tetap1000. Ini alasan penting memisahkan kuantitas fisik, komitmen PO, tagihan dan pembayaran.

Variance disimpan pada task/PO/GRN. Notifikasi kedatangan tersedia untuk manager, warehouse, serta sales terkait order tertentu. Jalur yang diperiksa belum mengirim pemberitahuan khusus “kurang40” kepada MD penanggung jawab dengan tugas memilih tunggu/revisi/tutup. Klaim GRN juga mengirim ke manager. Catat gap penerima dan tindak lanjut, bukan menganggap tidak ada notifikasi sama sekali.

Bukti: `services/receiving_roll_service.py:197–277`; `services/goods_receipt_close_service.py:238–266`; `services/inbound_complete_service.py:312–329,543–550`; `services/alert_ops_service.py:110`; `routers/purchase_orders_extra.py:94–127`; `services/po_amendment_service.py:30,226–344`; `routers/purchase_orders.py:33–73`. Bukti penerimaan parsial terdahulu: [laporan14](14_UJI_GRN_PARSIAL_KAPASITAS_RECOVERY.md).

## 7. SO→makloon: kapan greige diamankan dan berkurang?

Jalur yang ditemukan: kebutuhan SO dapat menjadi PR; baris PR mempunyai mode purchase/makloon; prefill makloon menelusuri resep output→input; realisasi membuat Order Makloon tertaut PR. **Jumlah output600 belum tentu membutuhkan greige600**, karena konversi satuan, yield/loss dan resep harus dihitung.

Create order makloon menyimpan rencana, step dan estimasi. Pada jalur yang ditelusuri tidak ada reservasi bahan saat keputusan fulfillment atau create order. Wizard fulfillment sendiri menjelaskan tidak memotong stok. Saat `issue_step`, bahan available benar-benar dipindah menjadi `subcon`/WIP di vendor dan GL Dr WIP / Cr persediaan. Saat receive, bahan subcon dikonsumsi dan hasil proses dibentuk. Jadi issue bukan penghapusan histori bahan: bahan berpindah kategori/lokasi proses sebelum dikonversi menjadi output.

Untuk contoh rasio1:1: sebelum issue, greige1000 masih dapat terlihat available1000; setelah issue600, available400 dan600 berada di subcon/WIP. **Gap waktu yang dikhawatirkan pengguna memang belum tertutup oleh reservasi material pada jalur ini.** Tidak aman menyatakan keputusan produksi langsung mengunci600.

Alternatif sementara adalah melakukan issue hanya ketika bahan benar-benar diserahkan/dikeluarkan sesuai SOP, dengan koordinasi alokasi material. Jangan memajukan issue palsu sekadar untuk “mengunci” stok. Target fitur: reservasi rencana bahan tertaut kebutuhan/MKO, kemudian issue mengonsumsi reservasi yang sama; cancel/replan melepaskan/mengubahnya. Stok fisik tidak turun saat sekadar merencanakan, tetapi available-to-promise bahan harus memperhitungkan komitmen tersebut.

Bukti: `services/fulfillment_wizard_service.py:1–8`; `services/pr_sourcing_service.py:546,670`; `services/makloon_order_service.py:475–532,604–665,934`. Kecacatan makloon/produksi yang sudah ditemukan tetap berlaku dan bukan dianggap fixed oleh adanya alur ini.

## 8. Sumber kebenaran LOT dan koreksi

Master `inventory_lots` dengan `id` dan `lot_number` adalah identitas batch internal; roll merujuk `lot_id`, sementara `lot` menyimpan nomor yang ditampilkan. Nomor pabrik disimpan sebagai `supplier_lot`; ada pula `dye_lot`, shade, referensi asal dan parent lot untuk genealogy. Lot dan nomor roll bukan hal yang sama.

Supplier lot ditangkap pada penerimaan/scanning/manual. Sistem mempunyai resolve/create lot dan nomor internal otomatis; format dipengaruhi penomoran/entitas. Probe menghasilkan contoh `A/LOT-2610-0003`, bukan aturan bahwa semua lot harus bernama A/B. Label fisik perlu mengacu identitas internal dan tetap menampilkan referensi pabrik sesuai kebutuhan operasi.

Patch lot biasa mengizinkan koreksi supplier lot/dye lot/shade/catatan dan beberapa metadata; **tidak mengizinkan mengganti lot_number internal**. Probe mengonfirmasi supplier lot123 dapat dikoreksi tanpa mengubah nomor internal, sedangkan patch lot_number menjadiA ditolak. Ada split/merge/link genealogy terpisah. Karena itu jangan menjanjikan penggantian bebas123→A sebagai fitur rename. Jika perlu nama pendek/alias, jadikan atribut tambahan yang tidak menghapus nomor pabrik maupun identitas internal.

Perubahan lot master dan sinkronisasi seluruh snapshot dokumen/roll perlu dikaji sebelum koreksi massal; hasil probe hanya memverifikasi patch yang disebut, bukan seluruh histori dan cetak ulang.

Bukti: `services/lot_service.py:147–289,346–364,422,453,548`; `services/receiving_roll_service.py:56–57`; [probe runtime](client-requirements-probes.json).

## 9. Pesan per panjang atau per roll

Mode `purchase_mode=roll` membawa `roll_lines` berupa roll yang dipilih dan take_qty. Helper reservasi membedakan roll utuh dan potongan; rincian alokasi menyimpan panjang roll. Jalur reconcile per panjang menyediakan `round_up`, `round_down`, `exact_whole` bila cocok, `exact_cut`, atau `take_all` dengan sisa backorder. UI menampilkan jumlah roll/total/delta dan memberi pilihan, dengan default exact_whole atau round_up bila tersedia.

Contoh9×100+1×105=1005: pembulatan naik dapat1005/10 roll. Pembulatan turun tidak selalu905: jika roll105 menjadi roll terakhir menurut urutan pemilihan, sembilan roll pertama total900; jika105 masuk sembilan pertama, total905. **Dua urutan tersebut direproduksi pada helper dengan fixture satuan dasar**. Konversi yard/browser tidak termasuk probe itu; prinsip jumlah roll sama, tetapi tampilan yard harus memakai konversi resmi sistem.

Algoritme memakai prefix urutan FEFO yang diimplementasikan, bukan pencarian semua kombinasi agar total paling dekat. Jika pelanggan menghendaki “selalu kombinasi optimum905”, itu kebutuhan berbeda. Jika aturan bisnis melarang memotong roll, opsi exact_cut yang saat ini tersedia perlu dibatasi menurut kebijakan; jangan menganggap opsi tersebut otomatis dilarang hanya karena praktik gudang tidak mau potong.

Bukti: `services/roll_service.py:1701–1740,1749,1835,1884–1960`; `routers/sales_orders.py:310,379`; `frontend/src/components/RollReconcileSheet.jsx:13–92`; [probe](client-requirements-probes.json).

## 10. Tiga produk dari tiga gudang sampai ke driver dan SJ

Alur yang tersedia: SO→alokasi roll menurut gudang/owner→task picking per gudang→scan/konfirmasi jumlah→pemeriksaan loading sesuai kebijakan→dispatch/shipment→dokumen SJ→pengiriman/POD. Picking list untuk pekerjaan internal; SJ untuk pergerakan/penerimaan barang. Satu SO tidak wajib berarti satu shipment atau satu SJ.

Sistem mempunyai SJ per shipment dan SJ berdasarkan SO yang dapat difilter warehouse; tanpa filter tersedia ringkasan beberapa gudang. Karena data/dokumen dapat dibuka dari perangkat gudang yang berizin, **driver tidak harus kembali ke lokasi lain hanya untuk mengambil cetakan**. Namun pencetakan otomatis setelah gate atau pemetaan printer fisik per gudang belum terbukti dari jalur ini. Perlu printer yang bisa dijangkau titik dispatch; tidak harus satu jenis/mesin per gudang sebagai aturan software, tetapi SOP harus memastikan dokumen tersedia sebelum driver berangkat.

Untuk tiga gudang, pilih SOP: setiap gudang melakukan shipment/SJ bagi barang yang benar-benar berangkat dari sana, atau semua picking dikonsolidasikan di staging sebelum pengiriman gabungan. Jangan mencetak ringkasan seluruh SO seolah semua barang sudah dibawa ketika baru satu gudang menyerahkan. “Gate cocok” memverifikasi fisik yang lewat; itu tidak menggantikan keputusan dokumen mana mewakili muatan driver.

Mekanisme dasar multi-gudang ada; lifecycle lengkap tiga gudang, satu driver, konsolidasi, gate dan dokumen final belum diuji dalam putaran memo ini. Known findings delivery/dispatch/printing scope tetap perlu validasi terpisah.

Bukti: `routers/outbound_picking.py:27,412–433`; `services/shipment_service.py`; `routers/outbound_picking_extra.py:29–90,91`; `services/fulfillment_wizard_service.py:66–89`; `services/logistics_service.py:1–7`.

## 11. Semua bertag: jalur stock/store dan jalur pesanan/cross-dock

**Untuk disimpan:** PO→GRN/periksa fisik dan QC→buat/encode tag→cetak dan tempel→verifikasi tag→routing store→putaway ke gudang/lokasi penyimpanan. Penyelesaian setiap tahap mengikuti gate/kebijakan operasional; jangan mengartikan daftar ini sebagai semua status dipindah otomatis oleh satu tombol.

**Untuk SO:** SO→PR/PO tertaut→terima di transit→identifikasi dan QC yang diwajibkan→tag/cetak/tempel/verifikasi→routing cross_dock→alokasi/staging→loading check→dispatch/SJ. Cross-dock menghindari putaway ke rak penyimpanan, bukan menghilangkan GRN, identitas roll, QC, owner, stok maupun dokumen pengiriman.

Implementasi routing store/cross_dock tersedia. Setelah verified, routing cross_dock dapat menjadi cross_dock_ready; tidak selalu otomatis hanya karena PO berasal dari SO. Auto-tag pada receiving bersifat best-effort: kegagalan masih memerlukan tag manual. Jadi requirement “semua barang wajib RFID” perlu pemeriksaan gate yang konsisten; keberadaan auto-tag tidak membuktikan seluruh jalan keluar tertutup bagi roll tanpa tag. Audit lama telah menemukan loading dapat dianggap clean ketika roll wajib belum bertag (RFID-03); jangan membuat tiket duplikat.

Alternatif operasional saat ini: petugas wajib memeriksa/cetak/verifikasi tag sebelum kedua cabang, pilih routing berdasarkan kebutuhan dan pastikan alokasi SO. Target perbaikan: kewajiban tag berlaku end-to-end pada semua jalur dispatch, termasuk manual/exception dengan otorisasi dan jejak yang jelas. RFID hardware belum diuji.

Bukti: `services/receiving_roll_service.py:71–85`; `services/rfid_print_service.py:20–27,252,262–281`; `services/fulfillment_wizard_service.py:83–89`; [matriks RFID-03](18_MATRIKS_FLOW_KRITIS.md).

## 12. Tahap benang→greige→PFD/PFP→barang jadi

Sudah tersedia melalui `stage`: yarn, grey, pfd, pfp, finished, remnant, byproduct. Registry proses membedakan weaving/knitting dari yarn ke grey, pre-treatment ke PFD bila target dye atau PFP bila target print, kemudian dyeing/printing ke finished. Ini mendukung klarifikasi bahwa greige/PFD/PFP adalah tahapan barang, bukan hanya kategori nama.

Agar tidak tercampur: setiap SKU/lot harus memakai stage kanonik; fabric_type dan line_code tetap terpisah. Alur konversi membuat output yang ditautkan ke input/proses dan genealogy, bukan mengganti nama SKU bahan di tempat sementara saldo lama masih ada. Layar/filter dan label perlu menampilkan stage bersama kode/nama agar operator tidak salah mengambil bahan dengan tampilan mirip. Standardisasi data lama menjadi pekerjaan migrasi, bukan sekadar menambah pilihan dropdown.

Bukti: `domain_registry.py:53–88,103–106,437–456`; `schemas.py:210,250`; `services/makloon_order_service.py`; `services/makloon_calc_service.py`; `services/lot_service.py:402–480`.

## Tindak lanjut

Tambahan Gelombang2 berada di [register gap dan bug](26_TAMBAHAN_KLIEN_DAN_W2_025.md) dan [prompt fase](27_PROMPT_TINDAK_LANJUT_KEBUTUHAN_KLIEN.md). Bug W2-025 sudah memiliki reproduksi API. Gap bisnis diberi ID terpisah W2-REQ agar tidak mencampur permintaan fitur dengan cacat yang terbukti. Tidak menaikkan jumlah checkpoint239 untuk probe penjelasan; tiga checkpoint W2-025 menambah total menjadi242. Seluruh penerapan perlu diverifikasi pada commit kandidat dan konfigurasi klien sebelum dinyatakan siap dipakai.
