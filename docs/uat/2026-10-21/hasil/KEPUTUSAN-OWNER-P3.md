# Keputusan owner 2026-10-21 (putaran 3) — antrean retur di meja Gudang, unduh foto bukti, F-09 di produksi

- Commit awal: `c8b4f3f`        - Commit akhir: lihat tracker        - Branch: `main`
- ID ditangani: lanjutan F-11-layar (antrean & foto), lanjutan F-09 (data lama di produksi)
- Jawaban owner atas pertanyaan di tracker:
  1. Antrean "retur menunggu terima/QC" di meja Gudang → **perlu**.
  2. Gudang/QC boleh mengunduh foto bukti keluhan → **ya**.
  3. Harga khusus ditolak untuk produk yang kemudian dihapus dari pesanan → owner minta **penjelasan flow** dulu
     (lihat bagian akhir; keputusan masih ditunggu).
  4. Skrip perbaikan F-09 dijalankan di produksi → **ya**.

## 1. Antrean "Retur menunggu terima / QC" di meja Gudang
- Perubahan perilaku (sebelum → sesudah): Gudang hanya tahu ada retur dari notifikasi giliran → Meja Operator
  Gudang (`/desks/me`, juga ikut di Meja Admin karena admin memuat antrean gudang) dan Meja Admin Gudang
  (`/warehouse-admin/desk`) punya antrean **Retur menunggu terima / QC**: retur `approved`/`inspecting` (himpunan
  sama dengan daftar retur Gudang/QC F-11-layar), terlama di atas, tiap baris menyebut langkah berikutnya:
  *Menunggu scan terima · x/y roll diterima* (tombol Terima) → *N roll dalam perjalanan … scan tiba* → *Barang sudah
  di gudang — menunggu QC* → *Sedang diperiksa QC*; `inspected` keluar dari antrean. Tanpa nilai uang (nilai 0,
  jenis hitungan "Retur"). Langkah "menunggu QC" memakai gerbang yang SAMA dengan QC (`assert_ready_for_qc`).
- Baris dibuka di layar Retur Pelanggan lewat menu **Retur** (`returns-hub`) dengan fokus ke dokumennya — menu
  Penjualan (`sales-orders`) tidak dimiliki Gudang/QC.
- Berkas: `backend/services/return_journey_service.py` (`receipt_progress`), `backend/services/role_desk_service.py`
  (`return_receipt_qc_queue`), `backend/services/work_desk_service.py`, `frontend/src/features/sales_admin/workDeskApi.js`.

## 2. Gudang/QC mengunduh foto bukti keluhan
- Perubahan perilaku: `GET /sales-returns/{id}/attachments/{att}/download` dulu hanya `sales_return.view` → kini juga
  operator F-11-layar (`wms.scan`/`qc.inspect`) **untuk lampiran foto/video** selama retur di tahap kerja mereka
  (approved/inspecting/inspected); lampiran lain (mis. PDF surat) tetap 403 bagi mereka. Endpoint kini juga memeriksa
  akses badan usaha seperti detail retur (dulu tidak). Layar detail menautkan foto/video untuk Gudang/QC; Sales/
  Finance tidak berubah.
- Berkas: `backend/routers/sales_returns.py`, `backend/services/return_operator_view.py`,
  `frontend/src/features/sales/ReturnDetail.jsx`.

## 3. Perbaikan data F-09 di produksi
- Tidak ada akses ke server produksi dari sesi ini; perbaikan dipasang sebagai **migrasi startup sekali jalan**
  `bootstrap.apply_f09_superseded_rejections_2026_10_21` (penanda `migrations.f09_superseded_rejections_2026_10_21`)
  — jalan otomatis sekali saat backend produksi di-deploy/restart; isinya sama dengan
  `scripts/repair_f09_superseded_rejections.py --apply` (penolakan yang SUDAH diajukan ulang → `superseded`,
  keputusan lama tetap tersimpan, penolakan tanpa pengajuan ulang tetap memblokir, SO tidak dinaikkan otomatis).
  Hasil (daftar nomor SO) tercatat di dokumen penanda & log backend `[F-09]`. Gagal → dicatat, startup tidak gagal.
- Alternatif manual (bila ingin melihat dulu): `docker compose exec backend python scripts/repair_f09_superseded_rejections.py`
  (dry-run) lalu `--apply`.
- Berkas: `backend/bootstrap.py`.

## Pengujian
- Tes backend baru: `backend/tests/test_f11_layar_keputusan_lanjutan.py` (2 — antrean meja Gudang & Admin Gudang
  mengikuti langkah scan → QC → keluar saat `inspected`; unduh foto Gudang/QC 200, PDF 403, di luar tahap 403,
  Sales/Finance tetap, Desainer 403, PT lain ditolak) dan `backend/tests/test_f09_startup_repair.py` (1 — migrasi
  startup: penolakan yang diajukan ulang → `superseded`, keputusan lama tersimpan, tanpa pengajuan ulang tetap
  memblokir, SO tidak dinaikkan, sekali jalan).
  - **Merah dulu** (6 berkas backend versi `c8b4f3f`): **3 gagal** (antrean tidak ada; Gudang 403 saat unduh;
    fungsi migrasi tidak ada). **Sesudah: 3/3 lulus.**
- Tes frontend: `deskReturnQueue.test.js` (2, baru — baris retur meja Gudang → layar Retur Pelanggan di menu Retur);
  `f11LayarOperatorView.test.js` diperbarui (foto tertaut untuk Gudang/QC, PDF tidak; Sales tetap semua).
  Seluruh Jest **65/65 lulus**.
- Regresi backend (backend & DB terpisah dengan data acuan seed baru — semua akun `demo12345`): F-11/F-12,
  F-11-layar, F-09, meja peran (`test_iter313`, `test_ln102_t02`, Meja Admin Gudang `test_iter295`),
  `test_role_in_alignment`, `test_l08_evidence_identity`, `test_ln091t02_ln093_chain`: **60 lulus, 2 dilewati**.
  `test_iter295::test_wh_desk_structure` diperbarui (daftar antrean Meja Admin Gudang bertambah `retur_terima_qc`).
  Di luar daftar: `test_iter295::TestMdDesk` gagal karena data acuan tidak punya permintaan desain (0 dokumen di
  DB uji & `test_database`) dan `TestOutboundToLogisticsBridge` membaca Mongo `localhost` dari `.env` — tidak terkait.
- Lint: flake8 F821/F811/E9 bersih pada berkas berubah; `verify_desk_targets`: 29 target, 0 temuan.

## Penjelasan flow harga khusus (pertanyaan 3) — keputusan masih ditunggu
Ada dua jalur:
1. **Harga khusus pelanggan (standing)** — diajukan dari Pusat Persetujuan Harga (bisa dengan bukti, berlaku sampai
   tanggal tertentu & minimal qty). Setelah disetujui berlaku untuk SO berikutnya pelanggan itu.
2. **Harga khusus satu pesanan** — diajukan dari detail SO selama tahap *Dipesan*: lahir dokumen persetujuan harga
   (lingkup pesanan) + entri persetujuan di SO untuk **produk itu** dan **versi alokasinya** (roll & qty saat itu).
   Manajer memutus (pengaju tidak boleh memutus sendiri). Disetujui → harga baris diganti & total dihitung ulang;
   bila semua entri SO sudah disetujui, SO naik ke *Disetujui* dan roll dikunci. Ditolak → SO tidak bisa disetujui
   sampai diajukan ulang (F-09: pengajuan ulang menggantikan penolakan). Bila alokasi/qty baris berubah sesudah
   diajukan, persetujuan ditolak sistem (perlu diajukan ulang untuk versi baru).

**Celah:** Override SO bisa **menghapus baris**, tetapi entri harga khusus untuk produk itu tidak ikut disentuh.
Entri yang masih menunggu tidak bisa disetujui ("produk sudah tidak ada — tolak lalu ajukan ulang"); bila ditolak,
ia mengunci SO, dan karena produknya sudah tidak ada, tidak bisa diajukan ulang → SO terkunci selamanya.
Usulan: saat baris dihapus, entri harga khusus produk itu (menunggu maupun ditolak) otomatis ditandai **dibatalkan
karena baris dihapus** (dokumen persetujuan harga ikut dibatalkan, riwayat tetap) sehingga tidak lagi memblokir.

## Yang perlu direview
- Isi baris antrean (tanpa uang) & pilihan menaruhnya juga di Meja Admin Gudang.
- Batas unduh operator: hanya `image/*`/`video/*`.
- Migrasi startup F-09 berjalan sekali per database (penanda) — data yang terkunci sesudahnya ditangani alur F-09 biasa.
