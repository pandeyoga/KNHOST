# BE-AUD — Temuan backend paket 2026-10-19 (AUD-xx), dikerjakan sesuai urutan paket

- Commit awal: `12efcc1`        - Commit akhir: `7279557`        - Branch: `main`
- ID ditangani: AUD-RND-01, AUD-RND-02, AUD-EXP-01, AUD-SO-01, AUD-WMS-01, AUD-MKL-01, AUD-EXP-02,
  AUD-MKL-02, AUD-MIG-01, AUD-MIG-02, AUD-RET-01 (AUD-RND-03 sudah di [KEPUTUSAN](KEPUTUSAN-2026-10-21.md))
- Arahan owner 2026-10-21: "temuan backend AUD sesuai paket" — urutan & arahan perbaikan mengikuti
  `TEMUAN_TERVERIFIKASI.md`; tidak ada aturan bisnis/kewenangan/toleransi baru.
- Metode bukti untuk setiap temuan: tes regresi baru dijalankan pada kode lama (berkas yang diperbaiki dikembalikan ke
  versi induk commit perbaikannya, `<commit>^`) → MERAH, lalu pada kode baru → HIJAU. Untuk tes lewat API, reload backend diverifikasi sebelum tes dijalankan (lihat
  "Hambatan lingkungan" — watcher reload sempat mati).
- Semua tes tingkat layanan memakai event loop bersama `tests/_shared_loop.py` (pola repo) — lulus saat dijalankan
  bersama modul tes lain dalam dua urutan (70/70 dan 50/50).

Jalankan semua tes AUD (di container backend):

```bash
cd /app/backend && python -m pytest tests/test_aud_rnd_0102.py tests/test_aud_exp_01.py tests/test_aud_so_01.py tests/test_aud_wms_01.py tests/test_aud_mkl_0102.py tests/test_aud_exp_02.py tests/test_aud_mig_0102.py tests/test_aud_ret_01.py -p no:randomly -n 0 -q
```

## AUD-RND-01 — ACC labdip dapat meluluskan siklus yang handfeel-nya ditolak
- Berlaku di HEAD: ya — jalur kode deterministik (`decide` memeriksa "ada round ACC di mana pun" + round terakhir).
- Akar masalah: dasar keputusan bukan round FINAL per jenis uji.
- Perubahan perilaku: "lulus" hanya bila setiap jenis uji siklus punya round final (round_no terbesar) dengan hasil
  `acc`; jenis yang belum dinilai/ditolak disebut di pesan 400. Keputusan menyimpan `basis_rounds` (round final per
  jenis); `round_id` = round final terbaru. "Gagal" tetap boleh dicatat.
- Berkas: `backend/services/rnd_revalidation_service.py`; fixture tes LN-034 t01 disesuaikan (versi artwork ber-ACC).
- Commit: `c56a988`.
- Pengujian: `tests/test_aud_rnd_0102.py` (4 tes RND-01 + konkurensi keputusan) — kode lama: **4 gagal**, 1 lulus (uji keputusan bersamaan — penjaga regresi); kode baru: 5/5.
- Fixture: round penilaian disiapkan langsung (seperti tes LN-034); siklus dibuat lewat API.
- Status: implemented_pending_review

## AUD-RND-02 — Versi artwork yang tidak ada diterima sebagai referensi proofing ulang
- Berlaku di HEAD: ya — jalur kode deterministik.
- Perubahan perilaku: versi artwork wajib ada di riwayat versi desain dan sudah ACC (penanda `acc` versi atau
  `approved_version`); desain lama tanpa penanda ACC per versi hanya menerima versi yang sedang berlaku. Versi
  historis yang sah tetap diterima.
- Berkas/commit: `rnd_revalidation_service.approved_version_of` · `c56a988`.
- Pengujian: `test_versi_artwork_tidak_ada_atau_belum_acc_ditolak_historis_sah_diterima` (versi 999 → 400 "tidak ada",
  versi belum ACC → 400, versi 1 historis ACC → 201).
- Status: implemented_pending_review

## AUD-EXP-01 — Ekspor berkelompok selesai tetapi unduhan ditolak 403
- Berlaku di HEAD: ya — direproduksi runtime (CSV & XLSX grouping → 403 ACCESS_CHANGED `_rows`).
- Akar masalah: pemeriksaan ulang hak saat unduh memperlakukan kolom turunan engine `_rows` sebagai kolom dataset.
- Perubahan perilaku: kolom turunan engine didaftarkan asalnya (`DERIVED_COLUMNS`); pemeriksaan ulang hak kolom
  dataset & badan usaha saat unduh TETAP berlaku (hak kolom pengelompokan dicabut → 403 dengan `fields=["grade"]`).
- Berkas/commit: `services/export_engine.py`, `routers/export_center.py` · `db25c74`.
- Pengujian: `tests/test_aud_exp_01.py` (2) — kode lama (router `db25c74^`): **2 gagal**; kode baru: 2/2.
- Status: implemented_pending_review

## AUD-SO-01 — Proses lama dapat melepas kunci realisasi milik proses baru
- Berlaku di HEAD: ya — kode (kelas ketahanan).
- Perubahan perilaku: kunci realisasi OD membawa token; `release`/`renew` hanya untuk pemilik token; realisasi
  memvalidasi ulang state sesudah klaim dan memperbarui lease sebelum membuat dokumen — proses yang lease-nya diambil
  alih berhenti (FulfillmentConflict) sebelum menulis.
- Berkas/commit: `services/special_order_fulfillment.py` · `193c048`.
- Pengujian: `tests/test_aud_so_01.py` (skenario reviewer pada MongoDB aktual) — kode lama: **1 gagal**; kode baru: 1/1.
- Status: implemented_pending_review

## AUD-WMS-01 — Stok opname berubah sebelum jurnal berhasil; retry tidak memulihkan
- Berlaku di HEAD: ya — kode (kelas ketahanan).
- Akar masalah: urutan roll → movement → jurnal → saldo tanpa catatan operasi; retry menilai perubahan miliknya
  sendiri sebagai perubahan pihak lain (`recount`).
- Perubahan perilaku: tiap baris koreksi (scan & roll hilang) menulis catatan operasi bertahap
  `roll_count.ops.<kunci>` (token, lease, snapshot roll, syarat CAS, perubahan, rencana movement & jurnal) SEBELUM
  roll diubah; roll diubah lewat CAS sekaligus diberi penanda `count_op` = token. Retry: roll bertoken sendiri →
  lanjutkan movement (sekali per ref), jurnal (idempoten per source_id), rebuild saldo, tandai selesai; roll tanpa
  token → CAS yang sama dicoba (gagal = transaksi lain → `recount`). Lease (120 dtk; dilepas saat error) mencegah dua
  pemroses melanjutkan baris yang sama. Roll "ditemukan" memakai id deterministik per (sesi, baris) → retry tidak
  membuat roll kedua.
- Berkas/commit: `services/stock_count_roll_service.py` · `6974dd9` (+ tes `7279557`).
- Pengujian: `tests/test_aud_wms_01.py` (13): gangguan di movement / jurnal / rebuild saldo, sebelum CAS, sesudah
  tandai selesai, proses mati dengan lease aktif → ditunda lalu diambil alih, transaksi lain sesudah gangguan (selisih
  10 tetap diposting, roll 85 tidak ditimpa), transaksi lain sebelum finalisasi → recount, dua pemroses bersamaan,
  salah alamat + qty, roll hilang, roll ditemukan, finalisasi bersamaan lewat API.
  Kode lama: **10 gagal**, 3 lulus (penjaga regresi). Kode baru: 13/13. Regresi opname: `test_l10_ln101_roll_count`
  4/4, `test_l10_ops01_t1` 8/8.
- Keterbatasan: `create_inbound_roll` (roll_service, tidak diubah) masih punya celah sempit antara insert roll dan
  insert movement-nya sendiri; retry roll ditemukan mengembalikan roll yang sama tetapi tidak menambal movement awal
  bila proses mati tepat di celah itu.
- Status: implemented_pending_review

## AUD-MKL-01 — Excel rekap klaim makloon gagal saat memiliki baris mitra
- Berlaku di HEAD: **sebagian** — KeyError `loss_claim_receivable` masih ada; bagian 2 ("list ditutup sebelum
  `+ p[deducted_total]`") tidak ada di HEAD maupun baseline `63c38bd` (penjumlahan sudah di dalam list sebagai sel
  terakhir) — sama dengan catatan [validasi](VALIDASI_TEMUAN.md).
- Perubahan perilaku: kolom Excel memakai kontrak data JSON rekap (`loss_claim`, `loss_deducted`); baris TOTAL
  diisi lengkap (dulu sebagian kosong).
- Berkas/commit: `routers/supplier_contracts.py` · `ae4e1b3`.
- Pengujian: `tests/test_aud_mkl_0102.py` — workbook untuk mitra piutang saja, potongan tagihan saja, keduanya +
  selisih + menunggu, dan tanpa data; tiap sel ringkasan & TOTAL dicocokkan dengan JSON, angka dicocokkan dengan
  dokumen sumber (fixture), tiap baris rincian dicocokkan dengan JSON, nomor tagihan dipotong terbaca.
  Kode lama: **7 gagal**, 1 lulus. Kode baru: 8/8.
- Status: implemented_pending_review

## AUD-MKL-02 — Rincian rekap klaim dipotong 1.000 baris, berbeda dari total
- Berlaku di HEAD: ya — jalur kode deterministik (+ batas 5.000 order dari observasi paket).
- Perubahan perilaku: order dibaca lewat cursor (tanpa batas 5.000); ringkasan & rincian dari himpunan utuh yang
  sama. JSON: `rows_total`, `rows_offset`, `rows_limit` (halaman ≤ 1.000; tidak sah → 400). Layar: halaman 200
  rincian dengan "a–b dari N" + Sebelumnya/Berikutnya + catatan "Excel memuat semua rincian". Excel: SEMUA rincian
  (dibagi per 100.000 baris per sheet bila perlu) + baris info jumlah rincian di sheet ringkasan.
- Berkas/commit: `services/makloon_recap_service.py`, `routers/supplier_contracts.py`,
  `features/purchasing/makloon/MakloonClaimRecapView.jsx` · `ae4e1b3`.
- Pengujian: 1.001 kejadian @10 → ringkasan 10.010 = jumlah halaman 1 (1.000) + halaman 2 (1) = jumlah rincian Excel
  (1.001 baris); 5.001 order → total 5.001 & 5.001 baris Excel. Jest `mkl02RecapPaging.test.js` (rentang, offset,
  tombol berikutnya nonaktif di akhir).
- Status: implemented_pending_review

## AUD-EXP-02 — Ekspor dapat menggandakan baris saat sumber berubah
- Berlaku di HEAD: ya — kode (kelas ketahanan).
- Definisi konsistensi yang dipakai: tanpa replica set (keputusan T-01) MongoDB tidak punya snapshot read; export =
  hasil SATU agregasi atas sumber yang dimaterialisasi ke koleksi sementara `export_snap_<job>` (satu versi per
  dokumen sumber + baris unwind — dedup per `_id` sumber). File ditulis lewat SATU cursor terurut atas snapshot statis
  itu (tidak ada skip/limit berulang ke sumber hidup). Ringkasan per staf (LN-112) dan nilai join dibaca dari snapshot
  yang sama/sekali untuk seluruh file. Sheet Ringkasan mencatat "Data per <waktu snapshot>". Snapshot dibuang sesudah
  selesai/gagal; snapshot yatim disapu saat export berikutnya. Preview tetap membaca data hidup.
- Berkas/commit: `services/export_engine.py` · `1e275ca`.
- Pengujian: `tests/test_aud_exp_02.py` (8) dengan engine sebenarnya atas koleksi uji terisolasi; perubahan sumber
  disuntikkan DI ANTARA batch: insert+hapus (skenario reviewer), ubah field filter, ubah nilai, ubah field urut, ubah
  nilai join, ringkasan = rincian, unwind tetap terpisah, snapshot dibuang saat sukses & gagal.
  Kode lama: **7 gagal** (mis. file `1,2,2,3` — ID 2 ganda, sama dengan reproduksi reviewer), 1 lulus. Kode baru: 8/8.
- Keterbatasan: perubahan sumber yang terjadi SELAMA satu pass agregasi materialisasi tidak dibekukan (tanpa snapshot
  read); jaminannya: tiap dokumen sumber muncul paling banyak satu kali dalam satu versi. Koleksi sementara memakai
  ruang disk sebesar hasil export selama job berjalan.
- Status: implemented_pending_review

## AUD-MIG-01 — Apply migrasi menyatakan matched tetapi melewatkan fulfillment kosong
- Berlaku di HEAD: ya — jalur kode deterministik.
- Perubahan perilaku: kandidat = fulfillment tidak ada / `null` / `{}`; update dijaga syarat "masih kosong" dan
  hasilnya diperiksa. Laporan memisahkan `matched` (klasifikasi), `applied` (benar-benar tertulis) dan `conflicts`
  (diisi proses lain di antara baca & tulis / PO sudah tertaut item lain — tidak ditimpa). Tautan PO hanya ditulis bila
  OD tertulis. Opsi baru `--only=<id,...>`.
- Berkas/commit: `scripts/migrate_l03_ln033_fulfillment.py` · `8d6df8f`.
- Pengujian: `tests/test_aud_mig_0102.py` (in-process terhadap DATABASE TERISOLASI `kn_test_mig_<tag>` — data demo
  tidak disentuh): absent / `{}` / null → semua tertulis; state aktif tidak disentuh; perubahan bersamaan → konflik,
  tidak ditimpa; PO sudah tertaut item lain → konflik; `--only`.
- Status: implemented_pending_review

## AUD-MIG-02 — Rollback menghapus perubahan operasional setelah migrasi
- Berlaku di HEAD: ya — jalur kode deterministik.
- Perubahan perilaku: apply menyimpan salinan persis hasil migrasi (`fulfillment_migration.<key>`); rollback =
  update bersyarat kesamaan subdokumen (atomik) — hanya state yang belum berubah yang dihapus, tautan PO dipulihkan.
  State yang sudah dipakai operasional (versi/route/dokumen/riwayat berubah) TIDAK dihapus: dicatat
  `rollback_conflict` di `special_order_reconciliation` (sekali per item). Migrasi versi lama tanpa salinan: hanya
  bentuk murni hasil migrasi (versi 1, route purchase, 1 dokumen, tanpa field tambahan) yang dibatalkan. Rollback
  ulang aman; apply ulang sesudah rollback berjalan.
- Pengujian (berkas sama): rollback state murni; rollback sesudah route makloon v2 + MKO + riwayat (skenario
  reviewer) dan sesudah dokumen PO baru → tidak dihapus + konflik; rollback ulang & apply ulang; migrasi versi lama.
  Kode lama (MIG-01+02): **10 gagal**. Kode baru: 10/10. Dry-run nyata di data acuan: 0 kandidat
  (`test_l03_ln033_fulfillment::test_t10` lulus).
- Status: implemented_pending_review

## AUD-RET-01 — Pembuangan BS gagal di tengah proses dan retry tidak memulihkan
- Berlaku di HEAD: ya — kode (kelas ketahanan). Tidak bersinggungan dengan berkas yang sedang diubah sesi F-11/F-12
  (`return_disposition_service.py` tidak disentuh cabang lain).
- Perubahan perilaku: qty & nilai write-off per roll dikunci saat klaim (`disposition.supplier.plan`, CAS qty); langkah
  per roll idempoten (jurnal per roll, roll bersyarat `disposal_key`, movement sekali, rebuild saldo). Gangguan
  sesudah sebagian tersimpan → klaim ditandai `failed` (tahap `supplier_dispose_failed`), jejak TIDAK dihapus; retry
  keputusan "buang" yang sama melanjutkan sisa langkah (alasan & foto bukti dari keputusan awal). Gangguan sebelum ada
  yang tersimpan → klaim dilepas seperti dulu (keputusan bebas lagi). Klaim "processing" lebih tua dari 10 menit
  (proses mati) dapat diambil alih. Panel disposisi retur: label "Buang BS terhenti — lanjutkan", penyebab, tombol
  "Lanjutkan buang BS".
- Berkas/commit: `services/return_disposition_service.py`, `features/sales/ReturnDispositionPanel.jsx` · `28d53c7`.
- Pengujian: `tests/test_aud_ret_01.py` (9): gangguan di movement (skenario reviewer), perubahan roll, rebuild saldo,
  tandai selesai; jurnal (sebelum ada yang tersimpan → dilepas); dua roll dengan kegagalan pada roll kedua; proses
  mati (lease aktif → tidak diambil alih; kedaluwarsa → dilanjutkan); dua pengguna bersamaan; lanjutkan hanya untuk
  keputusan buang. Kode lama: **6 gagal**, 3 lulus (penjaga regresi). Kode baru: 9/9. Regresi
  `test_ln091t02_ln093_chain` 10/10. Jest `ret01DisposeResume.test.js` 3/3.
- Keterbatasan: roll yang terhenti tampil di panel retur (tahap baru), belum di kotak masuk antar-PT
  (`IntercoReturnInbox` hanya menampilkan roll menunggu keputusan).
- Status: implemented_pending_review

## Guardrail
- INV-ATOMIC-01: endpoint batal item OD (FE-01, `13c64d8`) didaftarkan di REVIEWED (`1dcd37e`) — "belum ditinjau"
  kembali ke 71 = baseline `8dab383`. Penjaga ini sudah MERAH sejak `8dab383` (6 pelanggaran + 71 belum ditinjau +
  self-test 2 gagal) — tidak berubah oleh pekerjaan ini.
- Gate statik `scripts/gate.sh --quick` di HEAD: MERAH — 21 gate gagal. Tiap gate yang gagal dijalankan ulang pada
  HEAD dan pada `12efcc1` (sebelum pekerjaan AUD; di container, baseline sebagai worktree sementara): **tidak ada gate
  yang memburuk**; semua identik dengan baseline kecuali `verify_auth_coverage` yang MEMBAIK 9 → 8 pelanggaran
  (route `recap.xlsx` kini terbaca menegakkan izin lewat `_claim_recap`). Gate default (seed ulang) tidak dijalankan
  karena me-reset database dev yang sedang dipakai untuk UAT.

## Regresi lain yang dijalankan (gagal = sudah gagal di kode lama, dibandingkan dengan stash)
- `test_l11_export_center.py::test_ln113_t01_sales_cannot_inject_hidden_fields` — gagal sejak `c8e3be8`.
- `test_l11_finance_staff_templates.py::test_coverage_no_unmapped`, `test_iter285_feedback_export_hutang.py`
  (1 gagal + 4 error) — identik pada engine lama.
- `test_l01_material_loss.py::TestLossDeductBillAndTolerance` (4) — kondisi data: bahan demo sudah dicadangkan
  order lain (409); berkas ini tidak memanggil rekap.

## Hambatan lingkungan
- Watcher reload uvicorn di container dev sempat mati (`WatchfilesRustInternalError: Cannot allocate memory`) —
  backend berhenti memuat ulang kode. Diketahui karena bukti merah MKL pertama "lulus" di kode lama; container
  backend di-restart dan setiap bukti merah lewat API sesudahnya menunggu server benar-benar memuat kode lama.
- Fixture awal RET-01 memakai `ent_cst` dari bukti reviewer; di data acuan PT CST ber-id `ent_a602991f8094`, sehingga
  nomor jurnal bertabrakan (`CST/JE-…`). Sisa uji (1 `number_sequences`, 1 saldo nol) dihapus; fixture kini mengambil
  id entitas dari `doc_prefix`.
- Sesi lain (F-01) mengubah sandi demo di cabangnya; tes baru di sini memakai sandi demo saat ini — perlu disesuaikan
  saat cabang itu digabung.

## Yang perlu direview
- EXP-02: definisi konsistensi "satu pass materialisasi" (tanpa snapshot read Mongo) — cukupkah untuk kebutuhan audit?
- WMS-01: lease 120 dtk & RET-01: 10 menit untuk mengambil alih operasi dari proses yang mati.
- MIG-02: aturan "bentuk murni" untuk migrasi versi lama tanpa salinan.
- MKL-02: ukuran halaman layar 200 & pembagian sheet 100.000 baris.
