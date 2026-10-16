> Pembaruan batas IX-13: [I7-C05 pada laporan 26](26_AUDIT_GRN_FINANCE_QC_DAN_PROMPT.md) membuktikan guard over_remaining default menahan penutupan fixture cm sebelum PO/GL berubah. Kesalahan counter tetap valid; dampak downstream tidak boleh diasumsikan selalu terjadi.

# Audit flow produksi, penerimaan dan lifecycle RFID

Tanggal 30 September 2026; baseline `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Repository aplikasi tidak diubah.

**Hasil tambahan: tiga temuan IX-11–IX-13 dan elaborasi GN-06 dengan bukti kegagalan/retry nyata.** Sepuluh skenario dijalankan: enam reproduksi perilaku cacat dan empat kontrol yang bekerja. Semua memakai fungsi asli dan MongoDB lokal. Penolakan posting berasal dari penjaga periode GL asli, bukan stub atau exception yang disuntikkan.

[Harness](integration_repro/integration_round6.py) · [Hasil JSON](integration_repro/integration_round6.json) · [Log](integration_repro/integration_round6.log) · [Prompt perbaikan](25_PROMPT_PRODUKSI_PENERIMAAN_RFID.md)

## Bukti per skenario

| ID | Flow dan hasil |
|---|---|
| I6-P01 | Posting ditolak: bahan 100→90; output 10 terbentuk; WO released; jurnal nol |
| I6-P02 | Retry setelah periode fixture dibuka: bahan 80; output total 20; WO hanya mencatat satu roll; jurnal overhead 20 |
| I6-C01 | Retry sesudah WO completed tidak mengubah snapshot lagi; kontrol ini tidak memperbaiki duplikasi sebelumnya |
| I6-P03 | Roll held QC tetap dikonsumsi 10 dan WO completed |
| I6-C04 | Putaway menolak hold dengan 400 sebelum lookup bin |
| I6-P04 | Plan awal kebutuhan 10 berubah menjadi konsumsi 20 setelah BOM aktif diubah |
| I6-C02 | Bahan tidak cukup ditolak sebelum efek stok/output/jurnal |
| I6-C03 | Pembatalan penerimaan normal menonaktifkan tag |
| I6-R01 | Gagal attach ke tugas yang sudah selesai menghasilkan 409 tetapi satu tag aktif menjadi yatim |
| I6-W01 | 100 cm dicatat sebagai 100 meter pada tugas; converter kanonik menghasilkan 1 meter |

## Metode dan batas bukti

Master, bahan pembukaan dan kondisi periode dibuat sebagai fixture. BOM dan WO dibuat/rilis melalui service asli; output, movement, lot, biaya dan jurnal melalui implementasi asli. Pembukaan fixture periode untuk menguji retry dilakukan langsung pada database lokal, bukan workflow unlock dua orang; workflow tersebut sudah diuji terpisah pada laporan 22.

Test kali ini memanggil service langsung, bukan HTTP/browser. Ini membuktikan perilaku fungsi bisnis dan persistensinya; validitas seluruh kombinasi fixture melalui UI belum dibuktikan. Seluruh hasil adalah data sintetis, bukan angka kerugian aktual. Full lifespan, worker, replica-set transaction dan seluruh indeks deployment tidak dijalankan. Tidak ada perangkat RFID, printer, PLC atau bank nyata yang dihubungi.

## GN-06/E1 — P1 — Produksi yang gagal posting dapat diproses ulang dan menggandakan hasil

**Lokasi:** [backend/services/production_service.py:358](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L358) · [backend/services/production_service.py:410](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L410) · [backend/services/gl_service.py:1574](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L1574) · [frontend/src/features/production/ProductionWO.jsx:262](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/production/ProductionWO.jsx#L262)

**Reproduksi:** I6-P01/P02. Bahan awal 100 meter dengan biaya 10 per meter; WO merencanakan output 10 dengan kebutuhan bahan 1:1 dan overhead 2 per unit. Periode tanggal posting dibuat tertutup. complete_work_order benar-benar mencapai ClosedPeriodError dari GL, tanpa exception tiruan: bahan tersisa 90, output sudah 10, WO masih released, produced_roll_ids kosong dan tidak ada jurnal. Sesudah fixture penutupan dibuka, retry menghasilkan bahan tersisa 80, dua roll output total 20, tetapi WO mencatat satu output roll dan hanya satu jurnal overhead sebesar 20.

**Akar kesalahan:** Urutan mutasi adalah konsumsi bahan → buat output → post GL → tandai WO completed. Tidak ada checkpoint atau idempotency key untuk efek stok sebelum GL. Guard status completed hanya melindungi pengulangan setelah sukses penuh; ia tidak mengenali efek percobaan gagal. Ini elaborasi temuan GN-06, bukan akar cacat baru yang dihitung lagi.

**Dampak dan batasnya:** Nilai material+output berubah dari 1.000 menjadi 1.020 ketika GL gagal, lalu 1.040 setelah retry, sementara total debit jurnal overhead hanya 20. Selisih perubahan nilai subledger terhadap posting adalah 20 pada fixture ini. Saldo pembukaan tidak diposting ke GL; ini uji delta, bukan rekonsiliasi trial balance perusahaan. UI membaca produced_qty dan produced_roll_ids dari WO, sehingga ringkasannya dapat menyembunyikan output percobaan pertama. Penelusuran UI bersifat statis, belum browser UAT.

**Perbaikan:** Gunakan operasi produksi yang dapat dilanjutkan dengan claim, version, effect key per konsumsi/output/posting, dan checkpoint persisten. Validasi periode sebelum efek stok, tetapi jangan mengandalkan precheck saja karena periode dapat berubah di tengah proses. Pilih transaksi atau saga dengan recovery terukur sesuai deployment. Jangan menyarankan user mengulang tanpa mengecek efek parsial. Rekonsiliasi output berdasarkan provenance WO, movement dan journal sebelum koreksi data historis.

**Kriteria selesai:** Dengan periode tertutup, hasil harus tidak berubah atau berada pada keadaan recovery yang eksplisit dan tidak dapat digandakan. Retry setelah hambatan dilepas menghasilkan tepat satu output 10, konsumsi 10, overhead 20 dan hubungan WO lengkap. Uji crash sesudah setiap tahap, dua complete bersamaan, cancel vs complete, retry sesudah sukses, serta rekonsiliasi delta nilai. Pertahankan penolakan stok tidak cukup.

## IX-11 — P1 — Produksi mengonsumsi roll yang masih ditahan QC

**Lokasi:** [backend/services/production_service.py:166](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L166) · [backend/services/production_service.py:301](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L301) · [backend/services/qc_inspection_service.py:146](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/qc_inspection_service.py#L146) · [backend/services/location_service.py:159](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/location_service.py#L159)

**Reproduksi:** I6-P03 dan kontrol I6-C04. Roll available dibuat melalui layanan stok; inspect_roll kemudian memberi hold karena warna berbeda dan kebijakan tahan. Putaway menolak dengan pesan DITAHAN. complete_work_order tetap mengonsumsi 10 meter dari roll yang sama, membuat output dan menyelesaikan WO. Flag hold pada bahan masih true, tidak ada pelepasan oleh manajer.

**Akar kesalahan:** Precheck _available_qty dan pemilihan FEFO _consume_material hanya menyaring owner, gudang, status available dan panjang positif. inspection.hold.held tidak ikut menentukan kelayakan konsumsi. QC hold terpisah dari status stok; karena itu pemeriksaan status available saja tidak cukup.

**Dampak dan batasnya:** Barang yang diblokir dari putaway dapat berubah menjadi barang jadi melalui jalur produksi. Identitas/provenance output terbentuk, tetapi tidak terdapat langkah otorisasi penggunaan bahan tertahan pada jalur yang diuji. Bila bisnis memang mengizinkan penggunaan khusus untuk rework, izin tersebut perlu dinyatakan dan dicatat; jangan membolehkan seluruh produksi secara implisit. Test tidak mencakup seluruh mekanisme hold, reservasi atau perpindahan stok lainnya.

**Perbaikan:** Tetapkan kelayakan roll untuk proses produksi dalam kontrak bersama yang mempertimbangkan hold, reservasi, owner dan lokasi. Terapkan pada perhitungan tersedia dan claim konsumsi atomik, bukan hanya UI. Jika ada jalur rework/override, wajibkan hak, alasan, cakupan kuantitas, referensi inspeksi dan jejak keputusan.

**Kriteria selesai:** Roll held ditolak sebelum perubahan stok maupun output. Setelah release resmi yang sah, produksi dapat berjalan. Jika hold datang setelah precheck, claim tetap menolak atau berkonflik tanpa efek parsial. Uji kombinasi roll held/non-held, stock shortage setelah pengecualian hold, serta penyelesaian sebagian dan retry.

## IX-12 — P2 — Kompensasi gagal menempelkan roll ke tugas meninggalkan tag RFID aktif tanpa roll

**Lokasi:** [backend/services/receiving_roll_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_roll_service.py#L78) · [backend/services/receiving_roll_service.py:115](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_roll_service.py#L115) · [backend/services/receiving_roll_service.py:356](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_roll_service.py#L356) · [backend/services/receiving_roll_service.py:364](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_roll_service.py#L364)

**Reproduksi:** I6-R01 dan kontrol I6-C03. Dengan auto_rfid_on_scan default aktif, scanner memegang snapshot tugas waiting_goods; database sudah completed sebelum create_counted_roll dilanjutkan. Roll dan tag dibuat oleh fungsi asli. attach_roll_to_task gagal conditional update dan mengembalikan 409, lalu roll dihapus. Database menyisakan satu rfid_tags berstatus active yang menunjuk roll tidak ada. Sebaliknya undo_receiving_roll normal benar-benar menandai tag retired.

**Akar kesalahan:** Cabang kompensasi attach_roll_to_task hanya delete inventory_rolls. Ia tidak memakai retire_roll_tag yang tersedia dan sudah dipanggil jalur undo normal. Efek tambahan saat pembuatan roll tidak termasuk dalam kontrak pembatalan kegagalan attach.

**Dampak dan batasnya:** Registri tag menyatakan identitas aktif tanpa objek fisik tersimpan; EPC tersebut tetap dianggap terpakai pada pengecekan encoding. Bukti ini tidak menyatakan gate memberi green atau barang benar-benar lolos. Skenario menggunakan snapshot lama yang disiapkan secara deterministik; bukan pengukuran frekuensi race di produksi. Tidak ada tag fisik yang ditulis.

**Perbaikan:** Satukan kompensasi kelahiran roll beserta tag, claim supplier dan seluruh referensi yang benar-benar telah dibuat. Jangan memakai undo yang mengurangi counter apabila attach belum pernah berhasil. Gunakan operation/effect ID dan audit alasan untuk membedakan abort sebelum attach dari pembatalan penerimaan yang sudah attached.

**Kriteria selesai:** Gagal attach menghasilkan 409, tidak menambah counter tugas dan tidak meninggalkan tag aktif tanpa roll. Uji auto-tag aktif/nonaktif, kegagalan setelah tag lahir, retry cleanup, serta crash di antara delete roll dan retire tag. Pembatalan normal tetap menurunkan counter tepat sekali dan menonaktifkan tag.

## IX-13 — P1 — Konversi hitung manual penerimaan menyimpang dari mesin UOM utama

**Lokasi:** [backend/services/receiving_roll_service.py:21](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_roll_service.py#L21) · [backend/services/receiving_roll_service.py:248](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_roll_service.py#L248) · [backend/services/receiving_roll_service.py:267](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_roll_service.py#L267) · [backend/services/uom_service.py:178](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/uom_service.py#L178) · [backend/services/goods_receipt_service.py:793](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/goods_receipt_service.py#L793)

**Reproduksi:** I6-W01. Produk memakai base_unit cm dan tugas penerimaan memakai meter, expected_qty=100. create_counted_roll menerima length=100, menyimpan roll 100 cm, tetapi menambah received_qty tugas sebesar 100 meter dan memindahkan tugas ke qc_check. uom_service.convert untuk input sama, memakai faktor kanonik yang benar-benar dimuat, menghasilkan 1 meter.

**Akar kesalahan:** receiving_roll_service mempertahankan tabel _LEN_FACTOR lokal hanya untuk meter/m/yard/yd. Satuan lain mendapat fallback 1.0. create_counted_roll memakai helper lokal tersebut, bukan layanan UOM kanonik yang sudah mendukung cm dan faktor master. Ini duplikasi SSOT konversi, berbeda lokasi dari temuan WAC dan rebuild balance terdahulu.

**Dampak dan batasnya:** Kuantitas yang dicatat pada roll dan tugas tidak sebanding. Status kecukupan penerimaan dapat tercapai terlalu dini. Test menunjukkan transisi tugas dan counter; penutupan GRN, received_qty PO dan pencatatan AP/GL setelahnya belum dieksekusi untuk fixture cm ini, sehingga dampak nilai downstream belum dinyatakan terbukti. Kombinasi unit dibuat sebagai fixture service, bukan lewat wizard pembuatan PO.

**Perbaikan:** Gunakan converter UOM kanonik dengan kontrak unit yang eksplisit dari input, base produk hingga unit tugas. Hilangkan fallback identitas untuk unit tak dikenal. Pisahkan penanganan berat/catch-weight dari panjang dan gunakan hasil pengukuran yang sesuai; jangan mengasumsikan kg selalu dapat diperkirakan dari panjang.

**Kriteria selesai:** 100 cm → 1 meter, meter↔yard, inch, alias master dan konversi variable menghasilkan kuantitas konsisten. Unit tidak dikenal harus ditolak sebelum roll/tag/counter dibuat. Jalankan end-to-end GRN → PO receipt → valuation untuk kombinasi yang sah, beserta batas rounding, timbang tanpa panjang dan retry. Test UOM unit yang lulus tidak cukup jika caller memakai formula lain.

## Validasi lanjutan temuan GN-06: BOM tidak dibekukan

I6-P04 memakai create_bom → create_work_order → release_work_order → update_bom → complete_work_order. Kebutuhan awal 10 berubah menjadi konsumsi 20 ketika qty_per_unit BOM diubah dari 1 menjadi 2 setelah WO dirilis. Ini meningkatkan bukti bagian BOM GN-06 dari penelusuran source menjadi eksekusi database asli. Tidak ada persetujuan ulang atas perubahan resep pada skenario tersebut. Bagian dua complete bersamaan dalam GN-06 masih memerlukan uji concurrency khusus; jangan menganggap seluruh bagiannya otomatis selesai divalidasi.

## Implikasi lintas flow dan UI

Pola utama adalah pemeriksaan hanya pada sebagian jalur: guard periode menjaga jurnal namun berjalan setelah efek stok; guard hold menjaga putaway namun tidak produksi; undo normal menonaktifkan tag namun kompensasi attach tidak; converter pusat benar namun penerimaan memakai duplikat formula. Perbaikan harus mengikuti efek bisnis dari awal sampai reversal/recovery, bukan hanya menambah validasi tombol.

Pada UI produksi, ringkasan output berasal dari WO, bukan pencarian seluruh output berdasarkan provenance. Setelah partial failure, operator memerlukan status pemulihan dan daftar efek yang sudah terjadi, termasuk link roll/movement/journal serta tindakan lanjut yang aman. Jangan mengubah kegagalan menjadi pesan sukses atau mengaktifkan retry generik tanpa idempotensi.

## Koreksi deduplikasi laporan sebelumnya

IX-02 (pembatalan cuti menghapus absensi izin lain) ternyata sudah disebut dalam skenario HR-03 laporan awal. Bukti MongoDB IX-02 tetap valid dan prompt perbaikannya tetap berguna, tetapi **tidak dihitung sebagai akar cacat baru**. Laporan 19 kini dilabeli enam detail integrasi: lima tambahan dan satu pendalaman HR-03. Demikian juga kegagalan/retry produksi pada laporan ini memperdalam GN-06, bukan menambah hitungan bug unik. Jumlah skenario, temuan dan akar masalah harus dibaca terpisah.

## Cakupan saat ini

Paket putaran 4–6 kini mencakup **38 skenario terarah** (19 + 9 + 10), ditambah **19 test bawaan lulus** dan probe autentikasi 1.353 endpoint. Trace pada laporan 21 tetap snapshot putaran 4; angka trace tidak diubah hanya karena ada skenario tambahan.

Belum seluruh kode dan flow tercakup. Alur GRN lengkap, dampak downstream variasi unit ke PO/AP/GL, konkurensi produksi, recovery setelah process kill, UI browser seluruh fitur, rekonsiliasi dataset acuan dan perangkat RFID fisik masih terbuka. Daftar ini bukan alasan menandai flow lainnya telah lulus. Penilaian enterprise pada laporan 10 tetap berlaku; belum ada uji vendor/hardware baru pada putaran ini.
