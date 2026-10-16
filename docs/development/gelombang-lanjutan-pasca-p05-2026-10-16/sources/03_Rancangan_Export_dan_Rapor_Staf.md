# Rancangan Export Lanjutan dan Rapor Staf

**ERP Kain Nussantara — Produksi IT PT Kubus Teknologi Indonesia**  
**16 Oktober 2026 · Usulan untuk ditinjau, belum implementasi**

## 1. Kebutuhan yang sudah jelas

User memilih data bisnis yang dibutuhkan, periode tanggal sendiri, filter lengkap, kondisi AND/OR, kolom yang ditampilkan, preview dan hasil unduhan. Penggabungan dilakukan pada data yang mempunyai hubungan bermakna. Contoh yang diminta: penjualan customer A oleh Sales A; artikel A oleh Sales A/B/C; rapor Designer A berisi daftar desain, skor, revisi dan ringkasannya. Rapor Sales juga diperlukan.

“Nilai desain” adalah **skor desain**. Bukan nominal desain atau penjualan kain. Memisahkan arti revisi artwork dan proofing bukan kewajiban membuat file/sheet berbeda. Pemilik tidak diminta memilih nama collection atau merangkai join teknis.

Pola dataset utama + field terkait + preview mempunyai padanan di [NetSuite Dataset Builder](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_1544122173.html). Dokumentasi Oracle juga menjelaskan risiko baris berlipat pada join one-to-many dan agregasi sebelum linking. [Dataset Linking](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_162627392718.html). Rancangan berikut adalah sintesis untuk KN; bukan klaim seluruh fitur NetSuite harus ditiru.

## 2. Satu pusat dengan cara cepat dan cara lanjutan

**Nama menu usulan:** Laporan & Ekspor. Di daftar modul tetap dapat tersedia tombol Ekspor yang membawa filter aktif ke pusat ini.

Urutan penggunaan:

1. **Pilih data utama.** Contoh Rincian Item SO, Pengiriman Aktual, Pembayaran Customer, Stok per Roll, Desain & Versi, Permintaan/Putaran Proofing atau Rapor Staf. Sistem menjelaskan “satu baris mewakili apa”.
2. **Pilih relasi yang relevan.** Contoh item SO→customer→Sales transaksi→artikel/warna. Pilihan memakai nama bisnis dan hanya menawarkan hubungan yang benar-benar tersedia.
3. **Pilih dan urutkan kolom.** Ada pencarian, nama tampilan, tipe data, satuan dan definisi. Field yang tidak berhak dilihat tidak dimunculkan di daftar pemilihan.
4. **Pilih tanggal acuan dan rentang.** Contoh tanggal SO, berangkat, terima uang, upload desain atau ACC. Preset September dan custom tanggal sama-sama tersedia. Zona waktu operasional ditampilkan.
5. **Atur filter/grup.** Contoh customer=A DAN artikel=A DAN (Sales=A ATAU B ATAU C). Kondisi yang tidak relevan untuk dataset tidak ditawarkan sebagai filter palsu.
6. **Pilih hasil detail atau ringkasan.** Ringkasan per Sales/customer/artikel/periode dengan ukuran yang sah. Qty yard/kg tidak dijumlah campur.
7. **Preview.** Menampilkan contoh baris, jumlah seluruh hasil, arti satu baris, filter, tanggal acuan, cakupan akses dan catatan data tidak lengkap. Total ringkasan harus memakai seluruh hasil filter, bukan hanya baris preview.
8. **Unduh/simpan definisi.** CSV untuk tabel datar; XLSX untuk tabel dan ringkasan yang berguna dalam satu workbook. File besar diproses bertahap/asinkron dengan status dan jumlah hasil; tidak diam-diam berhenti di limit layar.

Rancangan awal sebaiknya menyediakan template siap pakai di bawah agar user langsung dapat bekerja, lalu mode lanjutan untuk mengatur kolom/relasi. Ini usulan UX, bukan mengharuskan user menulis query.

## 3. Join yang berguna

| Kebutuhan | Satu baris detail | Data terkait yang masuk akal | Ringkasan yang berguna |
|---|---|---|---|
| Penjualan Customer A oleh Sales A | Item SO/transaksi dengan atribusi Sales yang jelas | SO, customer, tim Sales, artikel, warna, kategori, satuan | Periode, artikel, warna, nilai pesanan, qty per satuan |
| Artikel A dijual Sales A/B/C | Item artikel dan bagian kontribusi Sales | Artikel→item SO→SO→customer/tim Sales | Per Sales/customer/warna; jumlah SO unik; qty/roll dan nilai |
| Pemenuhan SO | Item/roll pengiriman aktual, sesuai pilihan | SO→pengiriman→roll→gudang→dokumen transit yang terkait | Qty dipesan vs terkirim, status parsial, lead time |
| Nilai tagihan dan uang customer | Dokumen tagihan atau penerimaan pembayaran | Customer→dokumen final→alokasi pembayaran yang sah | Tagihan, dibayar, saldo piutang dengan tanggal/acuan yang jelas |
| Kinerja designer | Desain atau aktivitas versi desain, dipilih jelas | Desain→versi→penilaian→penugasan→permintaan→OD bila terkait | Skor, desain dikerjakan, ACC, revisi, ketepatan waktu bila datanya tersedia |
| Jejak Special Order | Satu OD/desain atau satu item OD sesuai struktur nyata | OD→desain→proofing→produksi→SO terkait | Round artwork dan round proofing pada kolom berbeda; durasi tiap tahap |

Contoh yang tidak berguna: mencocokkan setiap revisi artwork Designer A dengan setiap proofing kain di periode yang sama hanya karena orang atau tanggal sama. Hubungan harus melalui referensi permintaan/desain/OD yang sah. Jika memang OD yang sama, metrik artwork dan proofing dapat berdampingan setelah masing-masing dihitung pada lingkup yang tepat.

**Tanggal dipilih user, tetapi tidak sembarang disamakan.** Data yang tidak punya tanggal relevan tidak diberi filter periode palsu. Master produk dapat difilter tanggal dibuat/diubah; stok saldo saat ini harus berlabel posisi saat ini. Memilih September tidak otomatis menghasilkan stok historis September jika sumber snapshot/mutasi belum mendukung rekonstruksi.

## 4. Contoh laporan Customer A + Sales A

Contoh parameter: dataset Rincian Item SO; tanggal SO 1–30 September; customer A; Sales A; status transaksi yang disertakan ditampilkan; entitas sesuai hak akses. Contoh periode adalah ilustrasi.

Kolom standar: nomor/tanggal SO, entitas penjual, customer, Sales transaksi/tim, persentase kontribusi, artikel, warna, kategori, qty, satuan, jumlah roll, harga satuan final, diskon, nilai bersih item, pajak bila dipilih, status pemenuhan dan referensi pengiriman.

Untuk detail roll, user memilih relasi “Roll Pemenuhan”. Baris kemudian berarti satu roll pengiriman/alokasi; jumlah item atau total SO tidak boleh otomatis dijumlah kembali pada setiap roll. Preview perlu menjelaskan perubahan arti baris ketika relasi ini ditambahkan.

Ringkasan: jumlah SO unik, jumlah customer unik, qty yard, qty kg, jumlah roll unik sesuai status yang dipilih, nilai pesanan bersih, serta kontribusi Sales. Pajak dan uang dibayar ditampilkan sebagai ukuran terpisah bila memang diminta.

Jika satu SO ditangani Sales A dan B, tampilkan nilai transaksi penuh dan nilai kontribusi sebagai kolom berbeda. Jangan memberikan masing-masing 100% omzet pada A dan B lalu menjumlahkannya sebagai omzet perusahaan. Sistem existing sudah memiliki konsep `sales_team` dan split; itu layak menjadi sumber yang dipakai konsisten. [E28: backend/services/analytics_facts.py:41](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/analytics_facts.py#L41).

## 5. Contoh rapor Designer A

**Parameter:** user/staf Designer A berdasarkan ID; entitas/lini yang boleh diakses; September/custom tanggal; tujuan Internal/Special Order; status bila dipilih; pilihan tanggal acuan yang jelas. Semua field di bawah adalah rancangan isi, bukan pernyataan semua datanya sudah ada.

| Bagian | Isi yang direkomendasikan | Penjelasan agar tidak salah membaca |
|---|---|---|
| Identitas laporan | Nama staf/ID, periode, tanggal acuan, entitas/lini, waktu unduh | Nama sama tidak menggabungkan dua staf berbeda |
| Daftar desain | Kode, judul, tujuan, jenis baru/redesign, referensi OD/customer bila ada | Desain internal tidak dipaksa mempunyai customer |
| Tanggal | Ditugaskan, mulai, upload versi, ACC, tenggat jika tersedia | Jangan mengarang durasi/SLA bila tanggal dasar belum dicatat |
| Status | Aktif dikerjakan, review, revisi, ACC, hold sesuai status sumber | Status saat ini berbeda dari aktivitas yang terjadi dalam periode |
| Versi | Versi awal/terakhir, jumlah versi yang dikerjakan, penanggung jawab versi | Pekerjaan setelah handover tidak seluruhnya dikreditkan kepada pembuat dokumen pertama |
| Skor | Skor final yang tercatat, skor tiap versi bila dipilih, pemberi/tanggal penilaian | Skala existing 0–2; kosong berbeda dari skor 0 |
| Revisi | Jumlah permintaan revisi pada periode, jumlah versi revisi yang disetor pada periode, catatan alasannya | Permintaan revisi dan hasil revisi selesai adalah dua kejadian berbeda |
| Aktivitas pendukung | Checklist print paper per round jika field telah tersedia, file/bukti dan tanggal | Tidak mengubah checklist menjadi approval tambahan |
| Hubungan proofing | Nomor proofing/round bila memang terkait OD/desain dan dipilih | Bukan ukuran wajib kinerja artwork semua designer |

**Ringkasan yang disarankan:**

- Jumlah desain unik yang dikerjakan dalam periode, desain baru dibuat, desain ACC dan desain belum selesai. Masing-masing definisinya ditampilkan.
- Jumlah versi disetor, permintaan revisi dan versi revisi selesai pada periode.
- Jumlah penilaian valid, jumlah belum dinilai, skor final per desain dan/atau rata-rata skor versi dengan label yang tepat.
- Ketepatan waktu hanya untuk pekerjaan yang punya tenggat dan waktu serah yang sah; tampilkan pembilang/penyebut, bukan sekadar persentase.
- Daftar hold/belum ACC sebagai status posisi tanggal laporan, dipisahkan dari aktivitas yang benar-benar terjadi pada rentang tanggal.

**Contoh lintas periode:** desain dibuat Agustus, revisi disetor September, ACC Oktober. Bila user memilih aktivitas September, desain itu muncul karena revisi September, tetapi ACC Oktober tidak dihitung sebagai ACC September. Skor/keadaan terbaru boleh ditampilkan dalam kolom tersendiri berlabel posisi saat laporan agar tidak tertukar dengan hasil pada periode.

Bentuk unduhan yang praktis: satu XLSX **Rapor Designer A** berisi **Ringkasan**, **Detail Desain**, dan opsional **Riwayat Versi**. Sheet berbeda di sini berguna karena detailnya berbeda tingkat, bukan karena artwork/proofing harus dipisah secara paksa. Jika user hanya memilih detail desain, satu tabel/file cukup. PDF ringkas dapat menjadi tambahan, tetapi tidak menggantikan unduhan seluruh detail.

## 6. Contoh rapor Sales A

Parameter: ID staf, custom periode, tanggal acuan, entitas/lokasi/lini yang diizinkan, customer/artikel dan status. Gunakan atribusi Sales pada transaksi atau snapshot timnya, bukan otomatis pemegang customer saat laporan dijalankan. Existing menyediakan beberapa mode atribusi; pilihan yang dipakai harus terlihat agar hasilnya tidak membingungkan. [E28: backend/services/analytics_facts.py:41](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/analytics_facts.py#L41).

Detail yang disarankan: tanggal/nomor SO, customer, artikel/warna, qty dan satuan, jumlah roll, harga final/approval harga khusus, nilai item, kontribusi Sales, status Keep/Pending/pemenuhan, qty/roll terkirim, tanggal/dokumen pengiriman, tagihan, uang diterima dan saldo yang relevan sesuai sumber dan hak akses. Detail pembayaran tidak ditempel berulang pada setiap item sebagai total yang boleh dijumlah.

Ringkasan yang berguna:

- Jumlah SO unik dan customer aktif.
- Nilai pesanan bersih serta kontribusi Sales, dengan tanggal SO.
- Qty dipesan dan terkirim per satuan, serta roll sesuai definisi status.
- Sisa pemenuhan/Keep/Pending dengan waktu posisi laporan.
- Nilai pengiriman atau pendapatan terakui bila sumber/perizinan tersedia, diberi label berbeda dari nilai pesanan.
- Uang diterima pada periode menurut tanggal penerimaan; piutang berjalan menurut posisi/tanggal yang benar.
- Target vs realisasi hanya bila target dan basis realisasi sudah terkonfigurasi; tidak membuat target atau bobot rapor baru dari asumsi.

**Rapor bukan otomatis nilai akhir staf baru.** Dokumen ini mengusulkan laporan kinerja terukur. Bobot, target dan penilaian komposit tidak dikarang; bila kelak diminta nilai akhir, pakai definisi yang disepakati dan tampilkan komponennya.

## 7. Mencegah angka berlipat

Contoh: satu SO dua item, tiga roll pengiriman dan dua pembayaran. Join bebas dapat menghasilkan banyak kombinasi. Menjumlah total SO Rp10 juta pada tiap kombinasi akan menghasilkan angka palsu walaupun operasi penjumlahannya sendiri benar.

Prinsip pengolahan:

1. Tentukan satu baris: item SO, roll, dokumen pembayaran, desain atau versi. ID sumber tetap dibawa sebagai penanda.
2. Relasi ke customer/artikel biasanya memperkaya satu baris. Relasi ke banyak roll/pembayaran harus mengubah tingkat detail atau diagregasi dahulu pada kunci yang tepat.
3. Total SO, total pembayaran SO dan nilai item tidak disamakan. Bila pembayaran hanya teralokasi pada SO, jangan mengklaim pembayaran per artikel tanpa metode alokasi yang sah.
4. Hitung jumlah SO/customer/desain secara unik. Menjumlah skor bukan otomatis rata-rata; rata-rata harus membawa jumlah penilaian sebagai pembagi.
5. Pisahkan yard/kg dan mata uang. Kurs/konversi hanya dipakai bila ada sumber dan aturan yang sah.
6. Tampilkan draft, batal, belum dinilai dan data lama yang tidak lengkap secara eksplisit. Jangan membuat kosong menjadi angka nol atau menyembunyikan record hanya karena relasi opsional kosong.
7. Preview, ringkasan dan hasil unduh memakai definisi/filter yang sama. Tampilkan waktu data/snapshot bila proses unduh panjang agar perubahan transaksi tidak membuat halaman saling bertentangan.

Model Oracle juga menegaskan join dapat menghasilkan semua kombinasi yang kemudian perlu diagregasi pada tingkat yang benar; pemilihan relasi saja tidak menjamin total aman. [Oracle Dataset Linking](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_162627392718.html).

## 8. Hak akses dan cakupan seluruh data

“Semua data” berarti seluruh dataset bisnis yang dipetakan ke aplikasi dalam cakupan izin user. User dapat memilih seluruh hasil filter, bukan dibatasi halaman pertama. Role yang diberi akses lintas entitas boleh memilih cakupan lintas entitas; role terbatas tidak memperoleh cakupan baru melalui export/template bersama.

Aturan Sales tidak melihat grade/LOT/detail owner tetap berlaku pada preview, file, filter yang ditawarkan dan template. Semua pengaturan kewenangan memakai Custom Role/Access seperti keputusan Anda. Staf/gudang dibatasi lokasi jika memang konfigurasi operasinya demikian. Hak download dapat dicatat terpisah dari hak lihat bila diperlukan oleh konfigurasi, bukan mengubah aturan bisnis yang sudah disepakati.

Simpan definisi laporan: dataset/arti baris, relasi, kolom, filter, basis tanggal, agregasi, unit, pembuat dan versi definisi. Hasil download mencantumkan parameter supaya rapor bisa dicek ulang. Relasi tabel ditentukan implementasi berdasarkan kunci bisnis yang sah; user tidak diberi keharusan memilih tabel teknis tanpa konteks.

## 9. Fondasi kode sekarang

| Area | Yang terbukti ada | Batas terhadap kebutuhan terbaru |
|---|---|---|
| Analitik Sales | Katalog metrik, dimensi customer/produk/Sales, fact transaksi dan export Excel | Tidak otomatis meliputi semua record bisnis dan pilihan field bebas |
| Makna angka | Katalog membedakan penjualan berbasis SO, pendapatan jurnal dan penerimaan uang | Label/rapor baru harus memakai sumber yang tepat, tidak menyamakan ketiganya |
| Designer | Skor versi, revisi dari timeline, agregat dan export KPI/rapor | Periode preset dan atribusi nama pembuat belum cukup untuk semua kasus rapor aktivitas per staf |
| PDF personal | Ringkasan serta riwayat round | Hanya 12 round ditampilkan; bukan export seluruh desain/versi lengkap |

Bukti: [E27: backend/services/analytics_catalog.py:67](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/analytics_catalog.py#L67); [E28: backend/services/analytics_facts.py:41](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/analytics_facts.py#L41); [E29: backend/routers/ai_analytics.py:222](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/routers/ai_analytics.py#L222); [E30: backend/services/rnd_kpi_service.py:79](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_service.py#L79); [E31: backend/services/rnd_kpi_service.py:256](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_service.py#L256); [E32: backend/services/rnd_kpi_export.py:442](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_export.py#L442); [E36: backend/routers/rnd.py:750](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/routers/rnd.py#L750).

Pernyataan “fitur export belum ada” terlalu luas dan tidak sesuai bukti. Yang benar: komponen export/analitik sudah ada, tetapi pusat export dengan seluruh cakupan dan kontrol yang Anda jelaskan perlu diselaraskan dan dilengkapi. Dokumen ini tidak membuktikan semua formula laporan existing telah benar; penelusuran sekarang hanya menentukan fondasi yang dapat digunakan dan batas yang tidak boleh diasumsikan.
