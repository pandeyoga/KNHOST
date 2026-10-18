# Register keputusan dan kebutuhan pending

Keputusan yang belum dijawab tetap dicatat. Jangan mengisi jawaban atas nama owner/client. Semua item di sini pending pada awal paket, dengan jenis yang berbeda: kebijakan client, data, review desain, operasional, hardware, HR atau validasi owner. Tidak semuanya pertanyaan client baru.

Teks pertanyaan client lengkap dengan konteks tersedia pada [dokumen pertanyaan client](sources/09_Pertanyaan_Client_Retur_dan_Pendukung.md). Pertanyaan belum dikirim. Untuk menjawab, gunakan templates/DECISION_RECORD.md lalu isi answer, answer_ref, confirmed_by dan status resolved di BACKLOG.

Usulan desain dapat dikembangkan sebagai prototype untuk direview; belum menjadi kebijakan bisnis. Pending hanya memblok hasil akhir requirement terkait, tidak semua pekerjaan. Keputusan yang sudah jelas tidak ditanyakan ulang.

## KLR-01 — Cutloss: bagian kain yang diterima kembali oleh customer

Jenis: client_policy. Status: **pending**. Requirement: LN-092.

Contoh: satu roll 120 yard diperiksa QC. Yard ke-46 sampai ke-60 cacat, yaitu 15 yard; yard ke-1–45 baik (45 yard), dan yard ke-61–120 baik (60 yard).

- Dalam kasus ini, apakah customer menerima hanya yard 61–120 sebanyak 60 yard dan memperoleh pengembalian nilai setara 60 yard; atau menerima dua potong baik, yaitu 1–45 dan 61–120 sebanyak 105 yard, dan memperoleh pengembalian nilai setara 15 yard?
- Apakah ada cara lain atau keputusan berbeda per kasus? Jika customer menerima dua potong, apakah bentuk dua potong itu harus disetujui customer terlebih dahulu?
- Untuk pilihan pertama, 45 yard yang masih baik ikut tertahan di perusahaan. Apakah itu memang yang dimaksud cutloss?

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-02 — Cutloss: dasar perhitungan nilai kompensasi

Jenis: client_policy. Status: **pending**. Requirement: LN-092.

Setelah bagian yang dikembalikan dan qty kompensasi disepakati, nilai uangnya masih perlu dipastikan. Angka kompensasi tidak otomatis berarti seluruhnya dibayar tunai, karena pengurangan tagihan lebih dahulu serta pilihan refund/saldo sudah disepakati.

- Apakah nilai kompensasi dihitung dari qty yang disetujui dikalikan harga transaksi awal setelah diskon/harga khusus, atau menggunakan nilai lain yang disepakati?
- Mohon satu contoh angka lengkap dari kasus 120 yard tadi: harga awal, qty yang dikompensasi dan nilai akhir. Jika berbeda karena jenis cacat/kondisi, mohon jelaskan dasar kesepakatannya.

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-03 — Tukar barang: jumlah pengganti mengikuti roll atau yard/kg?

Jenis: client_policy. Status: **pending**. Requirement: LN-090.

Warna dan grade pengganti tetap sama sesuai keputusan yang sudah diberikan. Namun panjang/berat setiap roll tidak selalu sama.

- Jika dua roll yang disetujui untuk ditukar totalnya 195 yard, kewajiban penggantinya dua roll atau 195 yard?
- Patokan qty tersebut berasal dari qty yang dahulu dikirim, qty yang benar-benar kembali, atau qty yang disetujui setelah pemeriksaan? Mohon contoh bila qty pengiriman awal dan qty yang kembali berbeda.

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-04 — Tukar barang: perlakuan qty pengganti yang lebih atau kurang

Jenis: client_policy. Status: **pending**. Requirement: LN-090.

Contoh sementara: kewajiban pengganti sudah ditetapkan 195 yard. Roll pengganti yang tersedia tidak selalu tepat 195 yard.

- Jika roll pengganti total 205 yard, apakah tambahan 10 yard dibayar customer, dibebaskan, atau diputus per kasus?
- Jika pengganti total 190 yard, apakah kekurangan lima yard harus dikirim kemudian, diselesaikan menjadi nilai yang dapat direfund/menjadi saldo, atau ditutup dengan kesepakatan tertentu?

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-05 — Tukar barang: harga yang dipakai untuk menilai selisih

Jenis: client_policy. Status: **pending**. Requirement: LN-090.

Pertanyaan ini berlaku bila kelebihan/kekurangan qty pengganti memang dinilai uang. Bukan menanyakan ulang aturan harga SO normal.

- Selisih qty memakai harga transaksi asal setelah diskon/harga khusus, harga yang berlaku saat penggantian, atau harga khusus yang disepakati kembali?
- Jika harga saat ini berbeda dari harga awal, apakah qty yang sekadar mengganti kewajiban lama tetap menggunakan nilai lama, dan hanya selisihnya yang dinilai? Mohon contoh supaya tagihan tidak dihitung dua kali.

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-06 — Discount tanpa barang kembali: bagaimana syarat pemeriksaannya?

Jenis: client_policy. Status: **pending**. Requirement: LN-092.

Penjelasan sebelumnya menyebut discount untuk kain cacat yang tetap dipakai customer. Aturan terbaru menyebut keputusan kompensasi final sesudah QC inspect dan QC retur dilakukan di Rancamalang. Untuk barang yang tidak kembali, cara memenuhi syarat ini belum jelas.

- Apakah discount tanpa pengembalian barang merupakan pengecualian pemeriksaan fisik di Rancamalang dan boleh diputus berdasarkan foto/video serta bukti lain?
- Atau tetap perlu barang/bagian contoh dikirim ke Rancamalang untuk diperiksa? Jika demikian, bagian apa yang dikirim sementara sisanya tetap digunakan customer?

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-07 — Discount: nilai potongan berlaku untuk bagian mana?

Jenis: client_policy. Status: **pending**. Requirement: LN-092.

Barang tetap pada customer, sehingga tidak ada stok retur masuk untuk keseluruhan barang itu. Besarnya koreksi nilai belum dijelaskan.

- Discount ditentukan sebagai persentase, nominal rupiah, atau nilai per yard/kg?
- Potongan berlaku hanya pada qty yang cacat, satu roll, atau seluruh item/tagihan yang disepakati? Mohon satu contoh qty, harga awal dan nilai discount akhir.

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-08 — Syarat klaim bila hangtag hilang atau kain sudah dipotong customer

Jenis: client_policy. Status: **pending**. Requirement: LN-083.

Catatan sebelumnya menyebut kondisi ini kebanyakan ditolak, tetapi bisa berakhir cutloss/discount. Belum ada aturan yang membedakan kasusnya.

- Bagaimana perlakuan untuk: hangtag hilang tetapi roll masih utuh; hangtag ada tetapi kain sudah dipotong; dan hangtag hilang sekaligus kain sudah dipotong?
- Untuk masing-masing kondisi, apakah ditolak, tetap dapat diperiksa, atau hanya diperbolehkan penyelesaian tertentu? Bukti pengganti apa yang dapat dipakai jika hangtag hilang?

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-09 — Batas 21 hari: pengajuan harus masuk kapan?

Jenis: client_policy. Status: **pending**. Requirement: LN-083, LN-093.

Tanggal awal sudah jelas: customer dari SJ penjualan terkait; supplier dari penerimaan gudang asal, per receiving. Yang perlu dipastikan adalah kejadian apa yang harus masih berada dalam 21 hari.

- Jika customer mengajukan pada hari ke-20 tetapi barang baru diterima di Jakarta atau Rancamalang pada hari ke-24, apakah klaim tetap dalam batas waktu?
- Untuk supplier, apakah batas 21 hari berlaku sampai pengajuan klaim dikirim, sampai barang diberangkatkan, atau sampai barang diterima supplier? Perjalanan Jakarta–Rancamalang tidak boleh menimbulkan asumsi tanggal yang berbeda.

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-10 — Pengurangan tagihan: hanya SO asal atau termasuk tagihan lain?

Jenis: client_policy. Status: **pending**. Requirement: LN-091.

Sudah disepakati nilai retur mengurangi tagihan terlebih dahulu; kelebihannya boleh direfund atau menjadi saldo. Belum ditentukan cakupan tagihan yang dikurangi.

- Jika SO asal retur sudah lunas, tetapi customer masih berutang pada SO lain di entitas yang sama, apakah nilai retur harus digunakan melunasi tagihan lain itu terlebih dahulu?
- Atau pengurangan wajib hanya untuk tagihan SO asal, sehingga customer boleh memilih refund/saldo walaupun mempunyai tagihan lain?

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLR-11 — Siapa menanggung ongkir retur, perjalanan QC dan penggantian?

Jenis: client_policy. Status: **pending**. Requirement: LN-091.

Barang dapat diterima di Jakarta, lalu dikirim ke Rancamalang untuk QC; pengganti kemudian dikirim ke customer. Ini dapat melibatkan beberapa perjalanan.

- Siapa menanggung biaya pengembalian dari customer, perjalanan Jakarta–Rancamalang untuk QC, dan pengiriman pengganti?
- Apakah perlakuannya berbeda bila klaim diterima atau ditolak? Jika melibatkan Sukacita dan CST, apakah ada ketentuan pembagian biaya internal atau diputus per kasus?

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLX-01 — Kode LOT supplier dan LOT internal KN

Jenis: client_policy. Status: **pending**. Requirement: LN-014, LN-040.

Ada kemungkinan SJ pabrik menulis LOT 234 sementara KN menyebut kelompok yang sama LOT A. Ini masih perlu konfirmasi client.

- Apakah memang ada dua kode untuk kelompok yang sama, atau LOT A hanya contoh dan cukup memakai kode pabrik?
- Jika LOT pabrik yang sama datang pada SJ berikutnya untuk artikel/warna yang sama, apakah nama LOT KN tetap sama atau baru?
- Jika KN mempunyai nama sendiri, bagaimana urutan penamaannya dan kapan mulai dari awal lagi? Mohon contoh praktik yang dipakai.

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLX-02 — Kode cacat dan cara menghitung hasil inspect

Jenis: client_policy. Status: **pending**. Requirement: LN-052.

Form inspect sudah disepakati satu baris per roll dan posisi cacat per 15 yard. Kode cacat, hitungan nilai akhir dan ambang grade belum lengkap.

- Mohon daftar kode cacat beserta arti, bobot poin dan cara mencatat jumlah kejadiannya pada tiap interval.
- Mohon satu contoh roll yang sudah selesai diperiksa: panjang inspect, temuan per interval, langkah perhitungan angka hasil akhir, kemudian alasan masuk Grade A/A1/B atau grade aktif lainnya.
- Apakah penentuan grade hanya memakai jumlah poin atau juga panjang/lebar kain? Jika ada kriteria tambahan, mohon ditunjukkan pada contoh tersebut.

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## KLX-03 — Cutoff dan jadwal pembayaran pembelian antar-entitas

Jenis: client_policy. Status: **pending**. Requirement: LN-024.

Barang/transaksi antar-entitas berlangsung lebih dahulu dan pembayaran dijadwalkan akhir bulan. Pembayaran penuh per transaksi tanpa netting sudah disepakati.

- Tanggal cutoff dan tanggal pembayaran sebenarnya kapan?
- Transaksi masuk periode pembayaran berdasarkan tanggal invoice, penerimaan barang, atau acuan lain?
- Transaksi setelah cutoff dibayar periode berikutnya atau ada ketentuan lain? Mohon contoh dua transaksi di sekitar cutoff.

Dampak: Finalisasi perilaku cabang terkait; pekerjaan independen dapat berjalan.

## DATA-01 — Dataset master bahan, supplier dan warna

Jenis: client_data. Status: **pending**. Requirement: LN-011.

Sediakan dataset greige/PFD/PFP/benang, supplier code/name/color dan mapping yang disetujui; jangan mengisi data produksi dari contoh.

- File/data apa yang disahkan sebagai acuan migrasi? Siapa memeriksa mapping dan duplikasi?

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

## DES-01 — Urutan tag dan pemotongan MD Quality

Jenis: design_review. Status: **resolved**. Requirement: LN-042.

Usulan: receiving bruto → identitas/tag → potongan MDQ tercatat → saldo bersih/reprint teks. Qty SSOT ERP, EPC identitas.

- Tinjau SOP urutan tag, pengukuran, pemakaian dan reprint; boleh pilih urutan operasional lain asalkan identitas dan saldo tetap benar.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

Jawaban tercatat: Disetujui owner 2026-10-16 (chat sesi E1): urutan receiving bruto → identitas/tag → potong MDQ 0,25 yd tercatat sebagai pemakaian → saldo bersih & reprint teks (EPC sama, qty terkini). Qty SSOT ERP, EPC identitas. Roll kg: potong wajib berat aktual, tanpa itu transaksi diblok. Tambahan: susut/hilang bahan di mitra boleh sebagian panjang roll (roll dipecah) seperti retur sebagian.

## DES-02 — Penamaan dan pengelompokan dokumen per leg

Jenis: design_review. Status: **pending**. Requirement: LN-071.

Flow multi-SO/transit sudah diputuskan owner; nama dokumen internal, SJ customer per leg dan manifest merupakan usulan desain implementasi.

- Setujui contoh dokumen Bandung–Jakarta–customer dan tiga SO dalam satu manifest; pastikan internal transit tidak dianggap customer delivery.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

## DES-03 — Format rapor dan metric dictionary

Jenis: design_review. Status: **pending**. Requirement: LN-112.

Kebutuhan detail+ringkasan dan skor desain jelas; layout sheet, attribution dan basis tanggal yang ditawarkan perlu preview untuk review.

- Review contoh rapor Designer dan Sales serta label ordered/shipped/invoiced/revenue/cash; tidak meminta satu angka tunggal untuk arti penjualan berbeda.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

## DES-04 — Konteks multi-entitas workspace MD

Jenis: design_review. Status: **pending**. Requirement: LN-013.

Default restock dan transaksi per entitas jelas; desain antrean lintas entitas perlu menjaga entitas buyer/owner/AP secara eksplisit.

- Review preview flow membuat PO dari antrean gabungan dan memilih entitas dokumen; tidak menggabungkan pembukuan.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

## OPS-01 — SOP pelaksanaan stock opname

Jenis: operational_policy. Status: **resolved 2026-10-18** (keputusan owner via chat; lihat evidence/L10/report.md sesi 3). Requirement: LN-101.

Kebutuhan opname jelas, parameter freeze/cutoff/delta, recount dan otorisasi adjustment harus dicocokkan dengan fitur/SOP yang benar-benar berlaku.

- Setelah cek kode existing, catat kebijakan mana sudah ada dan mana memerlukan keputusan owner; jangan membuat threshold atau freeze global tanpa dasar.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

## HW-01 — Unit, SDK, firmware dan profile RFID aktual

Jenis: hardware_validation. Status: **pending**. Requirement: LN-121, LN-122, LN-120.

UR300, C72 dan CP30EN dipilih. Runtime Android, command encoding, tag/media, network dan profile perlu pembuktian unit nyata.

- Siapkan unit+firmware/SDK resmi, tag/media aktual, profile perangkat dan lokasi pilot untuk commissioning; simulator tidak menggantikannya.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

## HW-02 — Model dan firmware absensi belum dipilih

Jenis: hardware_selection. Status: **pending**. Requirement: LN-130.

Kebutuhan langsung ERP tanpa laptop harian sudah jelas, model dan protokol belum final.

- Konfirmasi unit/model/firmware serta kemampuan push/direct integration dengan bukti vendor dan pengujian perangkat.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

## HR-01 — Aturan attendance dan shift

Jenis: hr_policy. Status: **pending**. Requirement: LN-131.

Raw log dapat dibangun terpisah; shift, overnight, telat, lembur, hari libur dan koreksi belum diberikan.

- Sediakan aturan dan contoh hasil yang disetujui HR; pisahkan attendance dari dampak payroll.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.

## UAT-01 — Lingkungan pilot dan persetujuan akhir

Jenis: owner_validation. Status: **pending**. Requirement: LN-142.

Penutupan perlu kandidat commit, data representatif, role nyata, perangkat dan reviewer/owner.

- Tetapkan pelaksana UAT, environment/data teranonimkan yang sah, hasil yang diterima serta referensi persetujuan final.

Dampak: Validasi akhir requirement yang tergantung item ini; tidak memblok semua fase.
