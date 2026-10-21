# F-11-layar — Gudang & QC membuka retur pelanggan dari layar (tanpa nilai uang)

- Commit awal: `42321fe` (main) + merge F-11 `claude/charming-wiles-ba3d7a` → `68e4449` · Commit perbaikan:
  `a7c08c3` · Branch: `claude/frosty-stonebraker-6017fe`
- ID ditangani: F-11-layar (celah sisa F-11; lihat "Keterbatasan" di [F-11-F-12](F-11-F-12.md))
- **Keputusan pemilik 2026-10-21 (opsi b, "Terbatas"), diteruskan sesi induk:** detail/timeline/daftar/
  status-counts/meta retur terbuka untuk pemegang `wms.scan` atau `qc.inspect`; daftar dibatasi status
  `approved`/`inspecting`; field uang dibuang dan panel uang di ReturnDetail disembunyikan untuk mereka.
  Opsi (a) `sales_return.view` penuh untuk warehouse/qc **tidak** dipilih → matriks izin tidak diubah.
  Langkah opsional "antrean retur di Meja Operator Gudang" tidak disetujui/ditanyakan → tidak dikerjakan.
- Lingkungan uji: Docker lokal, backend sendiri `kn-wt-f11l-backend` (host `127.0.0.1:8051`) + frontend sendiri
  `kn-wt-f11l-frontend` (`craco start`, host `127.0.0.1:3051`) yang me-mount worktree ini; DB `kn_wt_f11l` =
  klon `kn_wt_f1112` (data acuan sesi F-11/F-12). Akun peran bersandi `scripts.demo_api.DEMO_PASSWORD` cabang ini
  (F-01 belum digabung). `test_database`, `:8001`, `:3000` bersama tidak disentuh.

## F-11-layar — Gudang & QC tidak bisa membuka layar retur
- **Berlaku di HEAD:** ya — direproduksi runtime di `68e4449` (F-11 sudah ada): `warehouse@`/`qc@`
  `GET /sales-returns`, `/{id}`, `/{id}/timeline`, `/status-counts`, `/meta/*` → 403 *Permission ditolak:
  sales_return.view*; tab *Retur Pelanggan* (`hubTabs.js`) hanya admin/sales/manager; menu *Retur* tidak ada untuk
  `qc` (navStructure + katalog modul: `view_resources["returns"]` = order/sales_return/internal_request/
  od_fulfillment, `qc` tak memegang satu pun). Akibatnya aksi F-11 (scan & QC lewat API) tidak bisa dijalankan
  dari layar.
- **Akar masalah:** semua GET retur memakai `require_permission("sales_return", "view")`; tidak ada tampilan
  retur yang aman-uang untuk peran operasional.
- **Perubahan perilaku (sebelum → sesudah):**

  | Endpoint / layar | Sebelum | Sesudah (pemegang `wms.scan`/`qc.inspect` **tanpa** `sales_return.view` = "operator") |
  |---|---|---|
  | `GET /sales-returns` (biasa & berhalaman) | 403 | 200, hanya status `approved`/`inspecting`; saringan status lain → daftar kosong; field uang dibuang |
  | `GET /sales-returns/status-counts` | 403 | 200, hanya `approved`/`inspecting` (+`all`) — sama dengan daftar |
  | `GET /sales-returns/{id}` | 403 | 200 untuk `approved`/`inspecting`/`inspected`, status lain 403; tanpa estimasi nilai & field uang tersimpan |
  | `GET /sales-returns/{id}/timeline` | 403 | sama seperti detail; jalur `settlement` ("Penyelesaian uang") & `value_basis` tidak dikirim |
  | `GET /sales-returns/meta/evidence-policy`, `/meta/complaint-reasons` | 403 | 200 |
  | `POST …/inspect/start`, `…/inspect/complete` (F-11) | dokumen mentah | operator menerima dokumen tanpa field uang |
  | Pemegang `sales_return.view` (Sales, Finance, Manajer, Admin, MD, MD Quality, Admin Sales) | — | **tidak berubah** |
  | Peran tanpa satu pun izin baca (Desainer, dst.) | 403 | 403 |

  - "Field uang" = nama field yang memuat kata uang (`price`, `amount`, `total`, `value`, `cost`, `refund`,
    `credit`, `writeoff`, `ppn`, `discount`, `compensation`, `payment`, `balance`, `settlement`, `decision`, …)
    dibuang rekursif — mis. `estimated_value`, `unit_price_est`, `line_total_est`, `order_grand_total`,
    `compensation`, `credit_note_*`, `logistics_costs`, `store_credit_*`. Pengecualian non-uang: `point_value`
    & `total_points` (poin cacat 4-point). Detail operator juga tidak menghitung harga dari SO sama sekali.
  - `inspected` ikut terbuka di detail/timeline (tidak di daftar) supaya layar QC tidak patah sesudah
    "Selesaikan Inspeksi" dan hasil QC masih terbaca; ini **lebih sempit** dari opsi (b) yang tidak membatasi
    status detail — lihat "Yang perlu direview".
  - **Frontend:**
    - Tab *Retur Pelanggan* + menu *Retur* untuk `warehouse` & `qc` (`warehouse_admin` ikut lewat pewarisan
      `warehouse`). Katalog modul (`access_modules.py`) Operasi Gudang & QC kini membuka `returns`/`returns-hub`,
      jadi peran kustom mengikuti izin efektif (fixture FE-03 dibangkitkan ulang).
    - `SalesReturns`: untuk operator tanpa kolom *Nilai (CN)*/*Nota Kredit* (juga di CSV), kartu ringkasan
      "Menunggu Terima / QC" & "Sedang QC", saringan status hanya Semua/Disetujui/Inspeksi, tanpa peta retur.
      Tombol *Buat Retur* kini digerbang `sales_return.create` (FE-04).
    - `ReturnDetail`: tanpa kolom Harga/Nilai, estimasi, catatan harga, Tanya KN, bar dokumen (cetak Nota Retur),
      panel Kelayakan/Pengecualian/Kompensasi/Pengganti/Ongkir/Karantina/Rantai/Grade-loss/Disposisi/Nota Kredit
      (semua hanya `sales_return.view`). Tombol mengikuti izin endpoint (FE-04): form scan = `sales_return.update`
      atau `wms.scan`; panel QC = `sales_return.update` atau `qc.inspect`; unggah lampiran & edit keluhan/tonggak
      = `sales_return.update`; unduh lampiran = `sales_return.view` (operator melihat nama berkas saja).
      Tombol keputusan uang (Setujui/Selesaikan/Tolak/Pembalikan) sudah digerbang `sales_return.approve|reject`.
- **Berkas:** `backend/services/return_operator_view.py` (baru), `backend/routers/sales_returns.py`,
  `backend/access_modules.py`, `frontend/src/config/hubTabs.js`, `frontend/src/config/navStructure.js`,
  `frontend/src/config/__tests__/fixtures/access_nav_fixture.json`, `frontend/src/features/sales/ReturnDetail.jsx`,
  `frontend/src/features/sales/SalesReturns.jsx`.
- **Commit:** `a7c08c3`.

## Pengujian
- **Tes backend baru** `backend/tests/test_f11_layar_return_screen_access.py` (4 tes, proses bisnis lewat API:
  Sales ajukan → Manajer setujui; login peran pakai `scripts.demo_api.DEMO_PASSWORD`):
  1. Daftar & hitungan: `warehouse@`/`qc@` 200, hanya `approved`/`inspecting`, retur `pending_approval` tidak
     tampil, `?status=pending_approval` → kosong, berhalaman = biasa, `status-counts` hanya dua status; Finance &
     Sales tetap melihat `pending_approval`; Desainer 403.
  2. Detail/timeline/meta tanpa uang: Finance memutus kompensasi diskon **7.777** (bukti foto ditempel langsung);
     Finance/Sales tetap menerima `estimated_value`/`unit_price_est`/`compensation`; Gudang/QC 200 tanpa satu pun
     kunci uang dari daftar tetap (bukan pola yang sama dengan server) **dan angka 7777 tidak muncul di respons**;
     timeline tanpa jalur `settlement`; meta 200; Desainer 403 di semua.
  3. Di luar tahap: retur `pending_approval` → detail & timeline 403 untuk Gudang/QC, Finance 200.
  4. Alur penuh lewat endpoint layar: Gudang Jakarta lihat daftar/detail → TRM → QC mulai (respons tanpa uang) →
     QC melihat `inspecting` di daftar → SJ ke Rancamalang → Gudang Rancamalang buka detail → TBA → QC selesai →
     detail `inspected` tetap 200, tidak lagi di daftar.
  - **Merah dulu** (router `68e4449`, tes final): **3 gagal, 1 lulus** — `assert 403 == 200` (Gudang/QC ditolak
    `sales_return.view`); tes 3 lulus juga di kode lama (penjaga: di kode lama semua 403). **Sesudah: 4/4 lulus.**
- **Tes frontend baru** `frontend/src/features/__tests__/f11LayarOperatorView.test.js` (5 tes): tab & menu untuk
  warehouse/qc (desainer tidak); detail warehouse/qc tanpa Harga/Nilai/estimasi/11 panel uang, form scan hanya
  warehouse, panel QC ada, tanpa unggah/unduh, tanpa panggilan `/credit-notes`; detail Sales tetap lengkap; daftar
  Gudang tanpa kolom uang & *Buat Retur*, Sales tetap lengkap.
  - **Merah dulu** (4 berkas sumber `68e4449`): **4 gagal, 1 lulus** (penjaga Sales lulus di keduanya — memang
    bukan regresi). **Sesudah: 5/5 lulus.** Seluruh `src/config/__tests__` + `src/features/__tests__`: **60/60
    lulus** (55 lama + 5 baru), termasuk `navAccess`, `permissionGates`, `roleGateSweep*`, `fe07ReturnErrors`.
- **Regresi area retur backend:** 42 berkas `backend/tests/test_*.py` yang menyentuh retur / katalog modul / menu
  (`-n 0`, `--continue-on-collection-errors`), dijalankan bersamaan pada dua container dengan DB klon identik:
  kode baru (`a7c08c3`) **87 gagal · 177 error · 272 lulus · 21 dilewati**; baseline `68e4449` (worktree terpisah)
  **87 gagal · 177 error · 272 lulus · 21 dilewati**. Diff per ID tes: **0 gagal baru, 0 berubah**. Kegagalan
  bersama sudah ada sebelumnya (mis. `test_f0b_entity_scoping` 91, `test_iter275` 49, `test_iter256` 42,
  `test_iter265` 14, `test_iter261` 13). Di antaranya `test_f11_f12_return_receipt_qc` 6 *error* di **kedua** run:
  fixture butuh 2 produk dengan ≥3 roll utuh di KSC/SO-00001, sedangkan retur uji layar SRET-00161 memakai satu
  roll produk kedua (data, bukan kode). Diulang pada klon segar data acuan (`kn_wt_f11l_chk`) dengan kode baru:
  `test_f11_f12_return_receipt_qc` + `test_f11_layar_return_screen_access` + `test_l08_ln081_journey` +
  `test_fe03_access_catalog` → **18/18 lulus**.
- **Lint:** flake8 `--select=E9,F` pada berkas backend berubah — 0 temuan (temuan lama F841 `sales_returns.py:236`
  hilang karena baris itu kini memakai `user, operator`). ESLint pada berkas frontend berubah — 0 error, 2 peringatan
  lama (direktif `eslint-disable` tak terpakai di baris `SalesReturns.jsx` yang tidak diubah). `sales_returns.py`
  944 baris (sudah > 800 sebelum perubahan: 934).
- **Gate quick start** (`seed_reset.sh`, `health_check.py`, `audit_endpoint_sweep.py`, `ux_audit.py`,
  `verify_contract.py`): tidak dijalankan — `seed_reset.sh` me-reset DB lewat jalur Emergent; cakupan perubahan
  diuji lewat tes endpoint & layar di atas.
- **Bukti UI (browser bawaan, frontend `:3051` → backend `:8051`):** retur uji `SRET-00161` (1 roll RL-35761,
  6 yard) dibuat Sales & disetujui Manajer lewat API; **semua langkah berikut lewat layar**:
  1. `warehouse@` (Eko, Jakarta) → menu *Retur* → tab *Retur Pelanggan*: 2 retur `Disetujui`, kartu "Retur untuk
     Gudang/QC", tanpa kolom Nilai/Nota Kredit, tanpa *Buat Retur* ([1](bukti-F-11-layar/1-gudang-daftar-retur.jpg)).
  2. Detail SRET-00161: tanpa Harga/Nilai/panel uang; form scan → *Terima di gudang* · Jakarta · RL-35761 →
     "Scan tercatat SRET-00161/TRM-1" ([2](bukti-F-11-layar/2-gudang-scan-terima-TRM.jpg)); lalu *Kirim* Jakarta →
     Rancamalang · Gudang Transit → `SJ-1` ([3](bukti-F-11-layar/3-gudang-kirim-SJ-ke-rancamalang.jpg)).
  3. `warehouse.rancamalang@` (Gilang) → daftar & detail → *Tiba di gudang tujuan* · Rancamalang Transit → `TBA-1`.
  4. `qc@` (Mulyadi) → sidebar memuat *Retur* → detail: tanpa form scan (tak punya `wms.scan`), tanpa kolom uang,
     tanpa unggah → *Mulai Inspeksi* ("Inspeksi SRET-00161 dimulai.") → P1 = 2 (poin 2, grade A) → *Selesaikan
     Inspeksi* → status *Selesai Inspeksi*, satu-satunya tombol "Kembali ke Daftar Retur"
     ([4](bukti-F-11-layar/4-qc-inspeksi-selesai.jpg)); daftar QC tinggal SRET-00003.
  5. `sales@` (regresi): daftar tetap 4 kartu + kolom Nilai (CN)/Nota Kredit + *Buat Retur*; detail SRET-00161 tetap
     Harga/Nilai + "Estimasi nilai retur Rp 120.000" + panel rantai retur.
  - Semua permintaan API selama langkah 1–4 → 200 (tidak ada 403 dari panel tersembunyi).
- **Fixture disiapkan langsung vs proses bisnis:** proses bisnis lewat API/layar untuk semua langkah, kecuali
  lampiran foto pada tes backend 2 (ditempel ke dokumen; unggah berkas bukan objek uji).

## Dampak pada modul terkait
- **Admin Gudang** (`warehouse_admin`, memegang `wms.scan`/`qc.inspect`, tanpa `sales_return`): ikut melihat tab &
  tampilan operator (pewarisan menu `warehouse`) — sejalan dengan notifikasi giliran `approved` yang sudah
  menujunya ke `returns`.
- **Notifikasi giliran `approved`** (Gudang & Admin Gudang, tautan `returns`) kini membuka layar yang bisa dibaca.
  Peran `qc` tetap tidak menerima notifikasi giliran (syaratnya `inspection.inspect`) — tidak diubah.
- **Efek FE-04 pada pemegang `sales_return.view` tanpa `update`** (Finance, MD Quality): form scan, unggah lampiran,
  dan edit keluhan/tonggak tidak lagi tampil (dulu tampil lalu 403 di server); Finance tidak lagi melihat
  *Buat Retur* (POST butuh `sales_return.create`). MD Quality tidak lagi melihat panel QC retur (tak punya
  `qc.inspect`/`update`, dulu tombolnya 403). Data & panel uang mereka tidak berubah.
- **Peran kustom:** modul *Operasi Gudang* atau *QC* tingkat apa pun kini membuka menu Retur; server tetap menuntut
  `wms.scan`/`qc.inspect` — lihat keterbatasan.

## Keterbatasan / yang belum diuji
- **Lampiran bukti:** operator melihat nama berkas tetapi tidak bisa mengunduh (`…/attachments/{id}/download`
  tetap `sales_return.view`, di luar cakupan keputusan) dan tidak bisa mengunggah. Bila kebijakan bukti badan usaha
  mewajibkan foto di tahap *inspeksi* (`returns.evidence_required_inspect`, data acuan: tidak), QC tidak bisa
  menyelesaikan QC sebelum Sales/Admin mengunggah foto.
- **Baris retur tanpa roll** (gerbang F-12 lewat tonggak *Barang sampai*): menandai tonggak butuh
  `sales_return.update`, jadi Gudang tidak bisa menandainya dari layar; QC retur seperti itu masih menunggu Sales/Admin.
- **Antrean "Retur menunggu terima/QC" di Meja Operator Gudang** (langkah opsional) belum dibuat — menunggu persetujuan.
- **Penyaring uang berbasis nama field:** field uang baru yang namanya tidak memuat kata uang akan lolos ke operator;
  tes memeriksa daftar kunci tetap + angka kompensasi khas.
- **Peran kustom dengan modul Operasi Gudang/QC tingkat "Lihat saja"** (tanpa `wms.scan`/`qc.inspect`) melihat menu
  Retur tetapi daftarnya 403 (bilah merah) — katalog modul tidak bisa membedakan aksi per menu.
- Teks lama: sesudah QC selesai, notifikasi layar tetap "Pilih outcome untuk menyelesaikan" juga untuk QC; respons
  `inspect/start` tidak membawa `roll_nos`, jadi baris qty aktual menampilkan id roll sampai detail dimuat ulang
  (perilaku lama, semua peran).
- Uji browser hanya di badan usaha KSC dengan data acuan; peran `warehouse_admin` & peran kustom tidak diuji di browser.

## Hambatan lingkungan
- Panel browser bawaan sempat tidak menggambar ulang (jendela tidak di depan): screenshot timeout & dropdown Radix
  perlu dibuka ulang; isian angka diisi lewat `form_input`. Tidak memengaruhi hasil.
- Worktree tidak punya `backend/.env`; dibuat lokal (di-ignore git, tanpa rahasia) untuk tes yang membacanya.
- Paket `docs/uat/2026-10-21/` (rencana) belum ada di repo — hanya folder `hasil/` (sama dengan catatan F-11-F-12).

## Yang perlu direview
1. Batas tampilan operator: daftar `approved`/`inspecting`; detail/timeline juga `inspected` (lebih sempit dari opsi b
   yang tidak membatasi status detail; status lain 403).
2. Penyaring uang berbasis kata pada nama field (`backend/services/return_operator_view.py`, `MONEY_TOKENS`/`SAFE_KEYS`).
3. Penambahan `returns`/`returns-hub` ke modul *Operasi Gudang* & *QC* di katalog akses (menu peran kustom).
4. Efek gerbang FE-04 di layar retur untuk pemegang `sales_return.view` tanpa `update`/`create` (Finance, MD Quality).
5. Pertanyaan owner: (a) antrean retur di Meja Operator Gudang? (b) QC boleh mengunduh foto bukti keluhan?

- **Status:** F-11-layar `implemented_pending_review`
