# Pengujian GRN sampai Finance dan keputusan QC

30 September 2026, snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. [Matriks cakupan lanjutan](27_MATRIKS_CAKUPAN_FLOW.md).

**12 skenario baru dijalankan: delapan kontrol yang bekerja dan empat reproduksi yang mendukung dua temuan P1, IX-14 dan IX-15.** Total paket putaran 4–7 menjadi 50 skenario, terpisah dari 19 test bawaan dan probe autentikasi 1.353 endpoint. Angka ini bukan persentase cakupan bisnis.

[Script reproduksi](integration_repro/integration_round7.py) · [Hasil JSON](integration_repro/integration_round7.json) · [Log](integration_repro/integration_round7.log)

## Lingkup dan cara pengujian

Fixture menyediakan master supplier/warehouse/product serta PO dan task inbound awal. Selanjutnya service asli menjalankan create GRN → manual entry → header surat jalan → add line dengan target PO → start count → create counted roll/tag → finish count → reconcile → close → stok, received_qty PO dan GL. Jadi lifecycle GRN manual benar-benar dijalankan, tetapi proses membuat/menyetujui PO sebelumnya tidak termasuk.

MongoDB lokal memakai indeks unik goods_receipts.active_key dengan partial filter yang sama seperti indexes.py:446. Indeks ini diperlukan untuk menguji surat jalan duplikat; seluruh indeks deployment lain dan app lifespan belum dipasang/dijalankan. Test tidak memakai mock query. Keputusan QC diuji melalui HTTP ASGI asli; langkah GRN memakai service langsung. Akun dan seluruh angka sintetis, tidak ada perubahan aplikasi atau data produksi.

Tanggal surat jalan fixture adalah 2026-09-30. Periode yang dikunci mengikuti tanggal runtime UTC yang benar-benar digunakan posting (terlihat pada log), bukan asumsi tanggal surat jalan atau kalender chat. Tidak ada kesimpulan baru tentang aturan tanggal pengakuan akuntansi dari perbedaan tanggal ini.

## Hasil kontrol dan temuan

| ID | Hasil teramati | Kesimpulan terbatas |
|---|---|---|
| I7-C01 | GRN closed; PO received=10; satu roll quarantine; satu jurnal debit 100 | Jalur normal GRN manual sampai GL bekerja pada fixture satu baris/satu roll |
| I7-C02 | Close ulang 409; snapshot tidak berubah | Tidak menggandakan penerimaan yang sudah sukses |
| I7-C03 | Cancel → cancelled, task waiting_goods, roll dihapus, tag retired, PO received=0, journal=0 | Pembatalan saat counting membersihkan efek fixture |
| I7-C04 | Cancel ulang tidak mengubah snapshot | Pengulangan cancel aman pada fixture |
| I7-C05 | Konversi 100 cm→100 meter menghasilkan over_remaining; close 400 BLOCKERS_OPEN | Dengan kebijakan default, salah unit tertangkap sebelum PO/GL diposting |
| I7-C06 | Versi lama ditolak 409; status tetap counting | CAS menolak perubahan dokumen basi |
| I7-C07 | User konteks B membaca GRN A ditolak 404 | Resource tersembunyi; 404 merupakan penolakan yang sah, bukan kegagalan test akses |
| I7-C08 | Surat jalan sama ditolak 409 DN_DUPLICATE; GRN kalah tetap review | Indeks unik mencegah start count duplikat pada fixture ini |
| I7-F01 | Closed period: GRN closed, line done, PO received=10, jurnal nol | Finalitas GRN tidak menunjukkan kegagalan finansial |
| I7-F02 | Periode dibuka, retry close tetap 409, jurnal nol | Jalur close tidak memulihkan posting yang hilang |
| I7-W01 | HTTP menerima 4/10; task completed, karantina tersisa 6 | QC parsial menutup tugas terlalu dini |
| I7-W02 | HTTP keputusan atas sisa 6 ditolak 400 | Kelanjutan QC tidak tersedia pada endpoint yang sama |

Ekspektasi awal harness untuk penolakan akses adalah 403. Implementasi sengaja mengembalikan 404 untuk menyembunyikan objek, sehingga assertion diperbaiki setelah memeriksa entity_scope. Ini koreksi test, bukan perubahan aplikasi atau temuan bug.

## IX-14 — P1 — GRN dinyatakan closed walau jurnal penerimaan gagal

**Lokasi:** [backend/services/inbound_complete_service.py:486](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/inbound_complete_service.py#L486) · [backend/services/goods_receipt_close_service.py:280](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/goods_receipt_close_service.py#L280) · [backend/services/goods_receipt_close_service.py:390](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/goods_receipt_close_service.py#L390)

**Bukti:** I7-F01/F02: dari draft manual, isi surat jalan/baris, mulai hitung, tambah roll, selesai hitung dan close. Saat periode tanggal posting tertutup, log asli mencatat kegagalan GL. GRN tetap closed, baris posted.status=done, tugas qc_pending, roll quarantine, PO received_qty=10 dan journal_count=0. Setelah fixture periode dibuka, close ulang menghasilkan 409 dan jurnal tetap tidak ada. Pembukaan fixture dilakukan langsung agar mengisolasi pemulihan posting, bukan untuk menguji workflow unlock.

**Akar kesalahan:** complete_task menangkap seluruh exception dari post_goods_receipt, hanya mencatat log, lalu melanjutkan status tugas. _post_task menerima hasil sebagai sukses dan close_grn memberi tanda done/closed. Percobaan ulang pada GRN closed ditolak. Tidak ada pemulihan lewat jalur close yang diuji; pencarian caller post_goods_receipt hanya menemukan jalur penerimaan tersebut. Ini tidak menutup kemungkinan koreksi manual atau tooling operasional lain di luar jalur ini.

**Dampak:** Stok dan PO menyatakan penerimaan terjadi tanpa pasangan Dr Persediaan/Cr GR-IR. Fixture normal yang identik menghasilkan jurnal debit 100; fixture gagal menghasilkan nol. Ini bukti selisih posting penerimaan sintetis, bukan nilai kerugian produksi atau saldo AP invoice. Jangan membuat ulang penerimaan untuk mengganti jurnal: stok sudah ada.

**Perbaikan:** Pisahkan keberhasilan penerimaan fisik dari penyelesaian finansial secara eksplisit. Gunakan durable posting operation/outbox dengan status pending/failed/posted, key idempotensi per task, error yang terlihat dan retry berotoritas. Jika kebijakan mensyaratkan GL atomik, rollback atau recovery harus mencakup stok, PO dan journal. Periode tertutup tidak boleh dibuka diam-diam; retry memakai tanggal/otorisasi koreksi yang sah. Rekonsiliasi GR tanpa journal dari sumber task, nilai roll dan PO sebelum backfill.

**Kriteria selesai:** Uji normal, closed period, kegagalan DB, retry ganda dan crash sesudah journal insert. Hanya satu jurnal muncul, stok/PO tidak bertambah ulang, status finansial tidak menyatakan sukses ketika posting gagal. Sesudah recovery, delta nilai persediaan dan GR-IR sesuai. Pisahkan finalitas fisik dan finansial pada UI serta laporan pengecualian.

### Prompt perbaikan IX-14

```text
Perbaiki IX-14 pada KNHOST.

Bukti: I7-F01/F02: dari draft manual, isi surat jalan/baris, mulai hitung, tambah roll, selesai hitung dan close. Saat periode tanggal posting tertutup, log asli mencatat kegagalan GL. GRN tetap closed, baris posted.status=done, tugas qc_pending, roll quarantine, PO received_qty=10 dan journal_count=0. Setelah fixture periode dibuka, close ulang menghasilkan 409 dan jurnal tetap tidak ada. Pembukaan fixture dilakukan langsung agar mengisolasi pemulihan posting, bukan untuk menguji workflow unlock.

Akar: complete_task menangkap seluruh exception dari post_goods_receipt, hanya mencatat log, lalu melanjutkan status tugas. _post_task menerima hasil sebagai sukses dan close_grn memberi tanda done/closed. Percobaan ulang pada GRN closed ditolak. Tidak ada pemulihan lewat jalur close yang diuji; pencarian caller post_goods_receipt hanya menemukan jalur penerimaan tersebut. Ini tidak menutup kemungkinan koreksi manual atau tooling operasional lain di luar jalur ini.

Tugas: Pisahkan keberhasilan penerimaan fisik dari penyelesaian finansial secara eksplisit. Gunakan durable posting operation/outbox dengan status pending/failed/posted, key idempotensi per task, error yang terlihat dan retry berotoritas. Jika kebijakan mensyaratkan GL atomik, rollback atau recovery harus mencakup stok, PO dan journal. Periode tertutup tidak boleh dibuka diam-diam; retry memakai tanggal/otorisasi koreksi yang sah. Rekonsiliasi GR tanpa journal dari sumber task, nilai roll dan PO sebelum backfill.

Acceptance: Uji normal, closed period, kegagalan DB, retry ganda dan crash sesudah journal insert. Hanya satu jurnal muncul, stok/PO tidak bertambah ulang, status finansial tidak menyatakan sukses ketika posting gagal. Sesudah recovery, delta nilai persediaan dan GR-IR sesuai. Pisahkan finalitas fisik dan finansial pada UI serta laporan pengecualian.

Reproduksi pada database sintetis memakai integration_round7.py. Ubah assertion perilaku cacat menjadi ekspektasi yang benar setelah patch. Pertahankan delapan kontrol yang telah bekerja. Periksa caller, UI, recovery dan rekonsiliasi historis. Sediakan dry-run untuk penemuan data terdampak; jangan koreksi produksi otomatis. Laporkan batas pengujian dan jangan menyatakan seluruh modul lulus hanya karena skenario ini lulus.
```

## IX-15 — P1 — Keputusan QC sebagian menutup tugas dan mengunci sisa karantina

**Lokasi:** [backend/services/qc_service.py:183](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/qc_service.py#L183) · [backend/services/qc_service.py:305](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/qc_service.py#L305) · [backend/routers/inbound_receiving_extra.py:120](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L120)

**Bukti:** I7-W01/W02 memakai HTTP FastAPI/ASGI dengan user sintetis berizin wms.update pada A. Setelah GRN normal selesai, roll 10 meter berada di karantina. POST qc-decision accept_qty=4/reject_qty=0 menghasilkan 200 dan tugas completed, sementara sisa karantina masih 6. POST berikutnya untuk menerima 6 menghasilkan 400 karena tugas bukan qc_pending.

**Akar kesalahan:** Validator hanya memastikan total keputusan tidak melebihi karantina; nilai di bawah total sah. Namun _apply_qc_decision menentukan status selesai dari accepted_qty>0, tanpa memeriksa sisa karantina. Router dan claim berikutnya mewajibkan qc_pending. Karena itu kontrak kuantitas parsial dan transisi terminal tidak cocok.

**Dampak:** Sisa roll masih tercatat sebagai quarantine tetapi tidak dapat diputuskan melalui endpoint QC yang sama. Tugas selesai dapat menyembunyikan pekerjaan inspeksi yang belum selesai. Uji ini tidak membuktikan kehilangan stok, pelepasan sisa karantina atau penghapusan otomatis; yang terbukti adalah kuantitas tersisa dan jalur keputusan berikutnya tertutup.

**Perbaikan:** Tentukan kontrak: jika QC wajib memutuskan seluruh kuantitas, tolak total keputusan yang kurang sebelum mutasi. Jika QC bertahap diperbolehkan, pertahankan qc_pending selama masih ada karantina, akumulasikan hasil/histori secara aman, dan selesaikan hanya ketika seluruh kuantitas memiliki disposisi. Hitung residual dari sumber roll yang konsisten di dalam operasi yang dilindungi claim/version.

**Kriteria selesai:** Uji 4+0 dari 10, kelanjutan 6, kombinasi accept/reject, hanya reject sebagian, rounding, retry dan dua inspector bersamaan. Tidak boleh ada task terminal dengan residual yang belum diputuskan. Kuantitas awal harus sama dengan accepted+rejected+remaining; genealogy dan tag parent/child tetap valid.

### Prompt perbaikan IX-15

```text
Perbaiki IX-15 pada KNHOST.

Bukti: I7-W01/W02 memakai HTTP FastAPI/ASGI dengan user sintetis berizin wms.update pada A. Setelah GRN normal selesai, roll 10 meter berada di karantina. POST qc-decision accept_qty=4/reject_qty=0 menghasilkan 200 dan tugas completed, sementara sisa karantina masih 6. POST berikutnya untuk menerima 6 menghasilkan 400 karena tugas bukan qc_pending.

Akar: Validator hanya memastikan total keputusan tidak melebihi karantina; nilai di bawah total sah. Namun _apply_qc_decision menentukan status selesai dari accepted_qty>0, tanpa memeriksa sisa karantina. Router dan claim berikutnya mewajibkan qc_pending. Karena itu kontrak kuantitas parsial dan transisi terminal tidak cocok.

Tugas: Tentukan kontrak: jika QC wajib memutuskan seluruh kuantitas, tolak total keputusan yang kurang sebelum mutasi. Jika QC bertahap diperbolehkan, pertahankan qc_pending selama masih ada karantina, akumulasikan hasil/histori secara aman, dan selesaikan hanya ketika seluruh kuantitas memiliki disposisi. Hitung residual dari sumber roll yang konsisten di dalam operasi yang dilindungi claim/version.

Acceptance: Uji 4+0 dari 10, kelanjutan 6, kombinasi accept/reject, hanya reject sebagian, rounding, retry dan dua inspector bersamaan. Tidak boleh ada task terminal dengan residual yang belum diputuskan. Kuantitas awal harus sama dengan accepted+rejected+remaining; genealogy dan tag parent/child tetap valid.

Reproduksi pada database sintetis memakai integration_round7.py. Ubah assertion perilaku cacat menjadi ekspektasi yang benar setelah patch. Pertahankan delapan kontrol yang telah bekerja. Periksa caller, UI, recovery dan rekonsiliasi historis. Sediakan dry-run untuk penemuan data terdampak; jangan koreksi produksi otomatis. Laporkan batas pengujian dan jangan menyatakan seluruh modul lulus hanya karena skenario ini lulus.
```

## Koreksi batas dampak IX-13

Bug konversi IX-13 tetap nyata pada counter task, tetapi tidak otomatis berarti setiap GRN akan memposting kuantitas salah. I7-C05 menunjukkan guard over_remaining default menahan penutupan fixture cm sebelum received_qty PO dan jurnal berubah. Efek jika user menyelesaikan discrepancy dengan override, atau kebijakan block_over_remaining dimatikan, belum diuji. Jangan mengubah temuan menjadi klaim bahwa GL pasti salah 100 kali pada semua penerimaan cm.

## Sisa cabang alur ini

Belum diuji penuh: OCR/file upload, multiple PO/line/roll, timbang dan catch-weight, supplier label claim, partial receipt/remainder task, persetujuan discrepancy/override, makloon partial delivery, worker restart, crash recovery, QC full accept/reject supplier return sampai debit note/AP, QC concurrency, browser UI, dan hardware label/RFID. Matriks cakupan mencatat semua kelompok fitur tanpa menandai yang belum diuji sebagai lulus.
