# Prompt perbaikan produksi, penerimaan dan RFID

Baseline `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Baca [bukti lengkap](24_AUDIT_PRODUKSI_PENERIMAAN_RFID.md). Jangan menjalankan perbaikan data produksi otomatis.

## GN-06/E1 — Produksi yang gagal posting dapat diproses ulang dan menggandakan hasil

```text
Perbaiki GN-06/E1 pada KNHOST.
Lokasi awal: backend/services/production_service.py:358, backend/services/production_service.py:410, backend/services/gl_service.py:1574, frontend/src/features/production/ProductionWO.jsx:262.

Bukti: I6-P01/P02. Bahan awal 100 meter dengan biaya 10 per meter; WO merencanakan output 10 dengan kebutuhan bahan 1:1 dan overhead 2 per unit. Periode tanggal posting dibuat tertutup. complete_work_order benar-benar mencapai ClosedPeriodError dari GL, tanpa exception tiruan: bahan tersisa 90, output sudah 10, WO masih released, produced_roll_ids kosong dan tidak ada jurnal. Sesudah fixture penutupan dibuka, retry menghasilkan bahan tersisa 80, dua roll output total 20, tetapi WO mencatat satu output roll dan hanya satu jurnal overhead sebesar 20.

Masalah: Urutan mutasi adalah konsumsi bahan → buat output → post GL → tandai WO completed. Tidak ada checkpoint atau idempotency key untuk efek stok sebelum GL. Guard status completed hanya melindungi pengulangan setelah sukses penuh; ia tidak mengenali efek percobaan gagal. Ini elaborasi temuan GN-06, bukan akar cacat baru yang dihitung lagi.

Tugas: Gunakan operasi produksi yang dapat dilanjutkan dengan claim, version, effect key per konsumsi/output/posting, dan checkpoint persisten. Validasi periode sebelum efek stok, tetapi jangan mengandalkan precheck saja karena periode dapat berubah di tengah proses. Pilih transaksi atau saga dengan recovery terukur sesuai deployment. Jangan menyarankan user mengulang tanpa mengecek efek parsial. Rekonsiliasi output berdasarkan provenance WO, movement dan journal sebelum koreksi data historis.

Acceptance criteria: Dengan periode tertutup, hasil harus tidak berubah atau berada pada keadaan recovery yang eksplisit dan tidak dapat digandakan. Retry setelah hambatan dilepas menghasilkan tepat satu output 10, konsumsi 10, overhead 20 dan hubungan WO lengkap. Uji crash sesudah setiap tahap, dua complete bersamaan, cancel vs complete, retry sesudah sukses, serta rekonsiliasi delta nilai. Pertahankan penolakan stok tidak cukup.

Jalankan reproduksi pada database sintetis dan ubah assertion menjadi invariant perilaku benar. Periksa caller lain, jalur normal, reversal, retry dan concurrency. Sertakan migration/reconciliation plan untuk data yang mungkin terdampak, dengan dry-run dan audit trail. Laporkan apa yang diuji, hasil serta batas bukti; jangan menyatakan seluruh modul aman berdasarkan satu regression test.
```

## IX-11 — Produksi mengonsumsi roll yang masih ditahan QC

```text
Perbaiki IX-11 pada KNHOST.
Lokasi awal: backend/services/production_service.py:166, backend/services/production_service.py:301, backend/services/qc_inspection_service.py:146, backend/services/location_service.py:159.

Bukti: I6-P03 dan kontrol I6-C04. Roll available dibuat melalui layanan stok; inspect_roll kemudian memberi hold karena warna berbeda dan kebijakan tahan. Putaway menolak dengan pesan DITAHAN. complete_work_order tetap mengonsumsi 10 meter dari roll yang sama, membuat output dan menyelesaikan WO. Flag hold pada bahan masih true, tidak ada pelepasan oleh manajer.

Masalah: Precheck _available_qty dan pemilihan FEFO _consume_material hanya menyaring owner, gudang, status available dan panjang positif. inspection.hold.held tidak ikut menentukan kelayakan konsumsi. QC hold terpisah dari status stok; karena itu pemeriksaan status available saja tidak cukup.

Tugas: Tetapkan kelayakan roll untuk proses produksi dalam kontrak bersama yang mempertimbangkan hold, reservasi, owner dan lokasi. Terapkan pada perhitungan tersedia dan claim konsumsi atomik, bukan hanya UI. Jika ada jalur rework/override, wajibkan hak, alasan, cakupan kuantitas, referensi inspeksi dan jejak keputusan.

Acceptance criteria: Roll held ditolak sebelum perubahan stok maupun output. Setelah release resmi yang sah, produksi dapat berjalan. Jika hold datang setelah precheck, claim tetap menolak atau berkonflik tanpa efek parsial. Uji kombinasi roll held/non-held, stock shortage setelah pengecualian hold, serta penyelesaian sebagian dan retry.

Jalankan reproduksi pada database sintetis dan ubah assertion menjadi invariant perilaku benar. Periksa caller lain, jalur normal, reversal, retry dan concurrency. Sertakan migration/reconciliation plan untuk data yang mungkin terdampak, dengan dry-run dan audit trail. Laporkan apa yang diuji, hasil serta batas bukti; jangan menyatakan seluruh modul aman berdasarkan satu regression test.
```

## IX-12 — Kompensasi gagal menempelkan roll ke tugas meninggalkan tag RFID aktif tanpa roll

```text
Perbaiki IX-12 pada KNHOST.
Lokasi awal: backend/services/receiving_roll_service.py:78, backend/services/receiving_roll_service.py:115, backend/services/receiving_roll_service.py:356, backend/services/receiving_roll_service.py:364.

Bukti: I6-R01 dan kontrol I6-C03. Dengan auto_rfid_on_scan default aktif, scanner memegang snapshot tugas waiting_goods; database sudah completed sebelum create_counted_roll dilanjutkan. Roll dan tag dibuat oleh fungsi asli. attach_roll_to_task gagal conditional update dan mengembalikan 409, lalu roll dihapus. Database menyisakan satu rfid_tags berstatus active yang menunjuk roll tidak ada. Sebaliknya undo_receiving_roll normal benar-benar menandai tag retired.

Masalah: Cabang kompensasi attach_roll_to_task hanya delete inventory_rolls. Ia tidak memakai retire_roll_tag yang tersedia dan sudah dipanggil jalur undo normal. Efek tambahan saat pembuatan roll tidak termasuk dalam kontrak pembatalan kegagalan attach.

Tugas: Satukan kompensasi kelahiran roll beserta tag, claim supplier dan seluruh referensi yang benar-benar telah dibuat. Jangan memakai undo yang mengurangi counter apabila attach belum pernah berhasil. Gunakan operation/effect ID dan audit alasan untuk membedakan abort sebelum attach dari pembatalan penerimaan yang sudah attached.

Acceptance criteria: Gagal attach menghasilkan 409, tidak menambah counter tugas dan tidak meninggalkan tag aktif tanpa roll. Uji auto-tag aktif/nonaktif, kegagalan setelah tag lahir, retry cleanup, serta crash di antara delete roll dan retire tag. Pembatalan normal tetap menurunkan counter tepat sekali dan menonaktifkan tag.

Jalankan reproduksi pada database sintetis dan ubah assertion menjadi invariant perilaku benar. Periksa caller lain, jalur normal, reversal, retry dan concurrency. Sertakan migration/reconciliation plan untuk data yang mungkin terdampak, dengan dry-run dan audit trail. Laporkan apa yang diuji, hasil serta batas bukti; jangan menyatakan seluruh modul aman berdasarkan satu regression test.
```

## IX-13 — Konversi hitung manual penerimaan menyimpang dari mesin UOM utama

```text
Perbaiki IX-13 pada KNHOST.
Lokasi awal: backend/services/receiving_roll_service.py:21, backend/services/receiving_roll_service.py:248, backend/services/receiving_roll_service.py:267, backend/services/uom_service.py:178, backend/services/goods_receipt_service.py:793.

Bukti: I6-W01. Produk memakai base_unit cm dan tugas penerimaan memakai meter, expected_qty=100. create_counted_roll menerima length=100, menyimpan roll 100 cm, tetapi menambah received_qty tugas sebesar 100 meter dan memindahkan tugas ke qc_check. uom_service.convert untuk input sama, memakai faktor kanonik yang benar-benar dimuat, menghasilkan 1 meter.

Masalah: receiving_roll_service mempertahankan tabel _LEN_FACTOR lokal hanya untuk meter/m/yard/yd. Satuan lain mendapat fallback 1.0. create_counted_roll memakai helper lokal tersebut, bukan layanan UOM kanonik yang sudah mendukung cm dan faktor master. Ini duplikasi SSOT konversi, berbeda lokasi dari temuan WAC dan rebuild balance terdahulu.

Tugas: Gunakan converter UOM kanonik dengan kontrak unit yang eksplisit dari input, base produk hingga unit tugas. Hilangkan fallback identitas untuk unit tak dikenal. Pisahkan penanganan berat/catch-weight dari panjang dan gunakan hasil pengukuran yang sesuai; jangan mengasumsikan kg selalu dapat diperkirakan dari panjang.

Acceptance criteria: 100 cm → 1 meter, meter↔yard, inch, alias master dan konversi variable menghasilkan kuantitas konsisten. Unit tidak dikenal harus ditolak sebelum roll/tag/counter dibuat. Jalankan end-to-end GRN → PO receipt → valuation untuk kombinasi yang sah, beserta batas rounding, timbang tanpa panjang dan retry. Test UOM unit yang lulus tidak cukup jika caller memakai formula lain.

Jalankan reproduksi pada database sintetis dan ubah assertion menjadi invariant perilaku benar. Periksa caller lain, jalur normal, reversal, retry dan concurrency. Sertakan migration/reconciliation plan untuk data yang mungkin terdampak, dengan dry-run dan audit trail. Laporkan apa yang diuji, hasil serta batas bukti; jangan menyatakan seluruh modul aman berdasarkan satu regression test.
```

## Tambahan untuk GN-06: versi BOM

```text
Bekukan resep dan overhead yang menjadi dasar WO pada titik persetujuan/rilis sesuai kebijakan bisnis. complete_work_order harus memakai versi tersebut. Perubahan BOM master berikutnya tidak boleh mengubah konsumsi WO yang sudah dirilis tanpa revisi dan persetujuan yang tercatat. Uji kebutuhan 10 tetap 10 setelah BOM master menjadi 20; revisi WO resmi boleh mengubahnya dengan version conflict dan jejak sebelum/sesudah. Gabungkan rancangan ini dengan recovery produksi, jangan membuat snapshot yang tidak dipakai oleh jalur complete.
```
