# Catatan audit yang telah direproduksi

ERP Kain Nussantara · PT Kubus Teknologi Indonesia

Tanggal: 19 Oktober 2026. Acuan kode: `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`.

**Status: audit masih berjalan. Dokumen ini bukan persetujuan penutupan plan atau pernyataan seluruh flow telah lulus.** Pengujian memakai salinan bersih main dan database lokal terisolasi, tanpa patch middleware versi 0.5. Kode aplikasi belum diperbaiki dalam audit ini.

## AUD-RND-01 — ACC labdip dapat meluluskan siklus yang handfeel-nya ditolak

Prioritas: tinggi. Lokasi: `backend/services/rnd_revalidation_service.py`, fungsi `decide`.

Validasi lulus memakai `any(r.result == acc)` untuk seluruh round supplier, tanpa memisahkan jenis uji. Setelah itu keputusan justru mengambil `rounds[-1]` sebagai round sumber. Pengujian langsung terhadap service dan MongoDB memakai siklus berisi labdip dan handfeel: labdip `acc`, handfeel `tolak` (nilai enum resmi). Sistem menyimpan hasil `pass`, status `decided`, dengan referensi round handfeel yang ditolak. Jalur `decide_sample` langsung meneruskan revalidation ke fungsi ini sebelum pemeriksaan kelengkapan jenis uji yang dipakai jalur sample biasa.

Dampak: riwayat kelayakan supplier menyatakan lulus dengan referensi pemeriksaan yang tidak mendukung keputusan tersebut. Layar kelayakan dan pemenuhan Special Order menggunakan hasil ini.

Perbaikan yang perlu dikembangkan: tentukan round final per jenis uji yang benar-benar menjadi dasar keputusan, validasi hasilnya serta jenis uji yang diwajibkan, dan simpan referensi yang sama. Jangan mengubah aturan bahwa kegagalan uji ulang tidak otomatis membatalkan produksi existing. Tambahkan pengujian beberapa jenis uji dengan hasil berbeda, round revisi, dan pengajuan keputusan bersamaan. Reproduksi awal memakai istilah `reject`; bukti terkini telah diperbaiki memakai `tolak` serta jenis uji berbeda agar sesuai model data aplikasi.

Bukti: `evidence/deep-checks.json`, AUD-RND-01. Ini reproduksi service; pembuktian jalur UI untuk seluruh kombinasi round masih diperlukan.

## AUD-RND-02 — Versi artwork yang tidak ada diterima sebagai referensi proofing ulang

Prioritas: sedang. Lokasi: `backend/services/rnd_revalidation_service.py`, fungsi `existing_artwork`.

Kode mengecek status desain secara umum, lalu menerima angka `design_version` dari permintaan tanpa membuktikan versi tersebut ada dan telah disetujui. Desain versi 2 dalam pengujian dapat direferensikan sebagai versi 999.

Dampak: traceability proofing ke artwork tidak dapat dipercaya. Nomor versi pada hasil uji bisa menunjuk artefak yang tidak pernah ada.

Perbaikan: validasi versi terhadap sumber versi desain yang sebenarnya, termasuk status persetujuannya. Pertahankan dukungan versi historis hanya bila versi tersebut memang tersedia dan memenuhi kebijakan. Uji versi tidak ada, versi belum ACC, HOLD, dan versi historis sah.

Bukti: `evidence/deep-checks.json`, AUD-RND-02.

## AUD-EXP-01 — Ekspor berkelompok selesai tetapi unduhan ditolak

Prioritas: tinggi. Lokasi: layanan export engine dan route download export-center.

Reproduksi melalui HTTP aplikasi lengkap: admin membuat export dataset `sales_finance`, kolom `sales_name` dan `grand_total`, `group_by: [sales_name]`, format CSV. Pekerjaan menjadi `done`; unduhan menghasilkan HTTP 403 `ACCESS_CHANGED` untuk kolom `_rows`.

Kolom hitungan hasil grouping ditambahkan engine, tetapi pemeriksaan izin saat download mencoba menyelesaikannya sebagai kolom dataset biasa. Akibatnya pengguna sah tidak dapat mengambil hasil.

Perbaikan: metadata kolom hasil agregasi harus membawa asal dan aturan izinnya. Validasi ulang izin tetap diperlukan; jangan menghapus pemeriksaan keamanan download. Uji grouping CSV/XLSX, kolom agregasi, perubahan izin setelah job selesai, dan export tanpa grouping.

Bukti: `evidence/deep-checks.json`, AUD-EXP-01, job ulang `exj_d68af4d2f7e4` (reproduksi pertama `exj_7ef2c0322a97`).

## AUD-SO-01 — Proses lama dapat melepas kunci realisasi milik proses baru

Prioritas: tinggi. Lokasi: `backend/services/special_order_fulfillment.py`, `_claim` dan `_release`.

Kunci operasi memiliki masa berlaku 120 detik. Setelah kunci A kedaluwarsa, B dapat mengambilnya. Namun `_release` tidak mengecek identitas pemegang kunci: ketika A selesai terlambat, A menghapus kunci B.

Reproduksi menggunakan MongoDB aktual: claim A → timestamp A dibuat kedaluwarsa untuk simulasi waktu → claim B → release A. Kunci B hilang. Ini membuktikan cacat kepemilikan kunci; penggandaan PO/MKO sebagai akibat lanjut belum direproduksi.

Perbaikan: gunakan token unik pemegang kunci, release bersyarat token, perpanjangan lease bila diperlukan, dan validasi ulang state setelah kunci diperoleh. Idempotensi dokumen tetap harus ditegakkan terpisah dari lease.

Bukti: `evidence/fault-checks.json`, AUD-SO-01; harness `work/audit_fault_checks.py`.

## AUD-WMS-01 — Stok opname berubah sebelum jurnal berhasil; retry tidak memulihkan bagian yang tertinggal

Prioritas: tinggi. Lokasi: `backend/services/stock_count_roll_service.py`, `apply_scan`.

Urutan saat ini: ubah saldo roll → insert pergerakan → posting jurnal → rebuild saldo agregat. Pengujian menyuntikkan kegagalan sementara pada panggilan jurnal setelah perubahan stok benar-benar tersimpan di MongoDB.

Hasil: stok 100 menjadi 90 dan satu pergerakan tersimpan. Saat scan yang sama dicoba ulang, sistem mengembalikan `recount` karena saldo sudah berbeda, sehingga operasi ulang ini tidak memperbaiki jurnal yang tertinggal. Kegagalan sengaja disimulasikan, bukan bukti database produksi sedang bermasalah.

Dampak: stok fisik/roll, saldo agregat, dan nilai persediaan di jurnal dapat berbeda setelah gangguan. Menghitung ulang menjadi 90 berisiko menghilangkan konteks selisih 10 yang belum diposting.

Perbaikan: sediakan proses transaksi atau catatan operasi bertahap yang tahan restart dan idempoten. Retry harus membedakan perubahan miliknya sendiri dari perubahan transaksi lain. Pastikan jurnal, movement, saldo roll, dan saldo agregat dapat direkonsiliasi satu kali. Uji gangguan pada setiap batas penulisan serta dua pengguna bersamaan.

Bukti: `evidence/fault-checks.json`, AUD-WMS-01.

## AUD-MKL-01 — Excel rekap klaim makloon gagal saat memiliki baris mitra

Prioritas: tinggi. Lokasi: `backend/routers/supplier_contracts.py:237`, `makloon_claim_recap_xlsx`; sumber `backend/services/makloon_recap_service.py`.

Route Excel membaca `loss_claim_receivable` dan `loss_claim_deducted`, sedangkan service menyediakan `loss_claim` dan `loss_deducted`. Tes route menghasilkan HTTP 500; log aplikasi menunjukkan `KeyError: loss_claim_receivable`.

Ada cacat berikutnya pada baris yang sama: ekspresi daftar kolom ditutup sebelum `+ p[deducted_total]`, sehingga kode mencoba menambahkan angka ke sebuah list. Setelah ketidaksesuaian nama field diperbaiki, ekspresi ini juga harus dibetulkan; jumlah dua nilai seharusnya dihitung sebagai satu sel terakhir.

Perbaikan: samakan kontrak data antara JSON recap dan Excel, perbaiki ekspresi total, lalu uji workbook berisi klaim piutang, potongan tagihan, keduanya, dan tanpa data. Cocokkan angka setiap baris dan total Excel dengan JSON dan dokumen sumber. Jangan hanya menguji respons saat rekap kosong.

Bukti: `evidence/seeded-run/test_l01_fabric_xlsx_color.log` serta `evidence/server-seeded.log`.

## AUD-EXP-02 — Ekspor dapat menggandakan baris saat sumber berubah, walaupun jumlah baris cocok

Prioritas: tinggi. Lokasi: `backend/services/export_engine.py`, `fetch` dan `write_file`.

Ekspor membaca beberapa batch melalui query terpisah dengan skip/limit. Tidak ada snapshot yang membekukan himpunan sumber. Reproduksi memakai engine sebenarnya dan MongoDB terisolasi: sumber awal ID 1,2,3,4; setelah batch pertama membaca 1,2, transaksi lain menghapus 4 dan menambahkan 0. Batch kedua menghasilkan 2,3. File berisi 1,2,2,3; jumlah baris tetap empat dan cocok dengan count sumber, tetapi ID 2 ganda. Ini simulasi penulisan bersamaan, bukan duplikasi yang disisipkan langsung ke file.

Perbaikan: definisikan konsistensi ekspor pada satu titik waktu dan gunakan strategi snapshot/materialisasi yang sesuai. Keyset pagination dapat mengurangi pergeseran, tetapi sendirian tidak menjamin nilai dan keanggotaan data tetap sama. Verifikasi juga ringkasan dan join berasal dari versi data yang konsisten. Uji insert, delete, perubahan field filter, perubahan sort dan perubahan nilai selama ekspor.

Bukti: `evidence/export-consistency.json`, AUD-EXP-02, dan `evidence/concurrent-export.csv`.

## AUD-MKL-02 — Rincian rekap klaim dipotong diam-diam sehingga tidak sama dengan total

Prioritas: sedang. Lokasi: `backend/services/makloon_recap_service.py`, pengembalian `rows[:1000]`.

Service menjumlahkan semua kejadian yang dibaca tetapi hanya mengembalikan 1.000 rincian. Route Excel memakai daftar yang sama. Dengan 1.001 kejadian masing-masing bernilai 10, ringkasan menunjukkan 10.010 sementara rincian hanya berjumlah 10.000. Tidak ada penanda bahwa rincian terpotong.

Perbaikan: untuk export lengkap, iterasi semua rincian dengan pembagian sheet/file bila diperlukan. Untuk preview layar, tampilkan pagination dan total yang jelas. Uji rekonsiliasi rincian dengan ringkasan pada lebih dari 1.000 kejadian serta lebih dari 5.000 order.

Bukti: `evidence/export-consistency.json`, AUD-MKL-02. Pengujian ini memakai satu order dengan banyak kejadian untuk mengisolasi batas rincian; batas order 5.000 belum diuji runtime.

## AUD-MIG-01 — Migrasi menyatakan matched tetapi melewatkan fulfillment kosong

Prioritas: sedang. Lokasi: `scripts/migrate_l03_ln033_fulfillment.py`, `main`, cabang apply.

Seleksi awal melewati order hanya jika `od.get('fulfillment')` bernilai truthy, sehingga `{}` masih dianggap kandidat. Namun update mensyaratkan field `fulfillment` tidak ada. Untuk order dengan `{}`, tidak ada dokumen yang cocok; hasil update tidak diperiksa. Relasi item di PO tetap ditulis, sementara relasi baru di Special Order tidak terbentuk.

Reproduksi dengan dua order legacy identik, satu tanpa field dan satu dengan objek kosong: laporan menyatakan dua matched, tetapi hanya order tanpa field mendapat `fulfillment.main`. Ini cacat apply, bukan masalah dependensi Python pada wrapper tes migrasi.

Perbaikan: bedakan klasifikasi kandidat dari jumlah yang benar-benar berhasil ditulis. Tangani field kosong secara eksplisit dengan guard concurrency, jangan menimpa fulfillment yang sudah dibuat proses lain. Tulis hasil konflik/gagal pada laporan. Uji absent, `{}`, null, state aktif, dan perubahan bersamaan.

Bukti: `evidence/migration-checks.json`, AUD-MIG-01.

## AUD-MIG-02 — Rollback menghapus perubahan operasional setelah migrasi

Prioritas: tinggi. Lokasi: `scripts/migrate_l03_ln033_fulfillment.py`, cabang rollback.

Rollback menghapus seluruh `fulfillment.<item>` bila masih memiliki penanda `migrated`. Tidak ada pemeriksaan versi, perubahan isi, atau dokumen lanjutan. Layanan perubahan route tidak membersihkan penanda migrated, sehingga penanda tersebut sendiri tidak membuktikan state masih sama dengan hasil migrasi.

Reproduksi: jalankan apply pada order legacy, lalu simulasikan perubahan operasional ke versi 2 dengan route makloon, riwayat alasan dan referensi MKO baru. Rollback menghapus seluruh state tersebut; MKO tetap ada. Dokumen MKO tidak terhapus, tetapi hubungan dan riwayat pada Special Order hilang.

Perbaikan: simpan snapshot/hash hasil migrasi dan lakukan rollback bersyarat hanya untuk state yang belum berubah. Data yang sudah dipakai operasional harus ditandai konflik untuk rekonsiliasi, bukan dihapus. Uji rollback setelah perubahan route, PR/PO/MKO baru, serta rollback ulang. Reproduksi perubahan pascamigrasi menggunakan fixture database, bukan klik seluruh flow pengadaan.

Bukti: `evidence/migration-checks.json`, AUD-MIG-02.

## AUD-RET-01 — Pembuangan BS gagal di tengah proses dan tidak dapat dilanjutkan lewat retry

Prioritas: tinggi. Lokasi: `backend/services/return_disposition_service.py`, `decide_supplier`, `_dispose`, `_stage`.

Urutan pembuangan: posting jurnal write-off → nolkan saldo roll dan tandai damaged → insert movement → rebuild saldo → tandai keputusan selesai. Pada pengujian, roll BS dimiliki kembali oleh entitas pemasok internal, memiliki metadata bukti foto, dan tahap awal `supplier_pending`. Panggilan `decide_supplier` dijalankan normal dengan gangguan sementara disuntikkan hanya pada insert movement.

Hasil: satu jurnal write-off 1.000 sudah tersimpan; roll 100 yard menjadi nol/damaged; movement tidak ada. Penanganan error menghapus klaim keputusan. Retry melalui `decide_supplier` ditolak karena status damaged membuat tahap dianggap closed. Bagian movement dan rebuild saldo yang tertinggal tidak dipulihkan.

Perbaikan: catat operasi pembuangan yang dapat dilanjutkan setelah gangguan, dengan idempotency key yang sama untuk jurnal, roll, movement, balance dan keputusan. Jangan menghapus jejak operasi ketika sebagian perubahan sudah committed. Retry sah harus melanjutkan pekerjaan yang tertinggal tanpa jurnal atau pengurangan stok ganda. Uji kegagalan di setiap batas penulisan dan disposal beberapa roll dengan kegagalan pada roll berikutnya.

Bukti: `evidence/return-recovery.json`. Ini pengujian service keputusan pembuangan; tidak mengklaim seluruh perjalanan retur inbound atau validasi file foto nyata telah diuji.

## Observasi yang belum ditetapkan sebagai bug bisnis

- Referensi kontrak terminated diterima oleh `_validate_contract_ref`, sedangkan daftar pilihan mengeluarkannya. Reproduksi tercatat sebagai AUD-RND-03 di `deep-checks.json`. Perlu memastikan apakah referensi kontrak historis memang diperbolehkan sebelum menetapkan perubahan perilaku.
- Rekap makloon juga membatasi pembacaan 5.000 order. Dampak batas order masih perlu diuji; pemotongan rincian 1.000 baris sudah dibuktikan pada AUD-MKL-02.
- Audit seluruh requirement dan UAT perangkat belum selesai. Temuan di atas tidak mewakili daftar final.

## Bukti pengujian umum

- Build produksi frontend berhasil; terdapat warning lint dan ukuran bundle. Build memakai cache dependensi yang tersedia, bukan pemasangan ulang lockfile yang sepenuhnya bersih.
- Parsing sintaks 992 berkas Python: tidak ada kesalahan sintaks. Ini bukan pengujian kebenaran logika.
- Batch 69 berkas tes menghasilkan catatan XML: 248 passed, 51 failed, 93 error, 17 skipped. Error collection/setup dan ketergantungan data contoh dicatat terpisah. Angka ini **bukan persentase acceptance yang selesai**; jumlah test case berbeda dari 230 butir acceptance plan.
- Sebagian modul melaporkan test passed tetapi proses Windows berakhir dengan exit abnormal. Status tersebut belum dianggap eksekusi bersih.
- Rincian per test: `evidence/test-cases.json`; hasil per proses: `evidence/seeded-run/suite-results.json`; sintaks: `evidence/syntax-scan.json`.
