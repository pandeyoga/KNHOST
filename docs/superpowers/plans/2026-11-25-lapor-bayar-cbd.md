# Lapor Bayar CBD & DP — Rencana Kerja

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pesanan yang wajib bayar dulu (CBD, bagian DP) berhenti di tahap "Bayar dicek Finance" sebelum gudang. Sales melapor bayar dengan bukti, lalu Finance menerima atau menolak. Bila diterima, kwitansi dan jurnal terbit otomatis dan pesanan lepas ke gudang sendiri.

**Architecture:**
- Penanda `pay_hold` pada pesanan `approved` dengan sub-status `menunggu_bayar`, bukan status baru.
- Titik periksa baru di `confirm_core` memakai hitungan `dispatch_payment_gate.evaluate` yang sudah ada.
- Koleksi baru `payment_reports` dengan lampiran (`storage_service`).
- "Terima" memanggil `ar_receipt_service.create_receipt` (satu pintu kas), lalu jalur lepas otomatis.
- UI disisipkan ke panel gerbang bayar di rincian pesanan, Perjalanan, Meja Keuangan, Meja Admin Sales, dan HP.

**Tech Stack:** FastAPI + MongoDB (`backend/`, uji `backend/tests_mem` mongomock), React 18 + Tailwind token (`frontend/src`, Jest + RTL).

**Spec:** `docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` (keputusan pemilik B1–B7; keputusan builder §7). Inventaris kode: `.superpowers/sdd/lapor-bayar-inv/inventaris.md` (dianalisis di `a5199a4`).

## Global Constraints

- Bahasa Indonesia untuk UI, komentar, dan commit. LF.
- Wewenang dari **izin**, bukan nama peran. Nilai aturan dari **pengaturan** (`nilai(...)` + katalog), bukan konstanta.
- Izin baru: `payment_report.create` dan `payment_report.decide`.
  - Bawaan `create`: sales, sales_admin, finance, admin, manager.
  - Bawaan `decide`: finance, admin, manager.
  - Didaftarkan di `backend/access_modules.py` + `backend/permissions_config.py` dengan label, dan diperiksa literal `require_permission(request, "payment_report", "<aksi>")`.
- Pengaturan baru `sales.batas_bayar_hari`: durasi hari, bawaan **3**, min 1, maks 30, per grup/PT. Katalognya di `backend/config_catalog_nilai.py`, di samping `sales.reservation_days`.
- "Wajib bayar dulu" dan jumlahnya **hanya** dari `dispatch_payment_gate.evaluate` (termin `dp_percent`, `type: cash` + `finance.tahan_kirim_tunai`, `pay_before_ship`, sample dikecualikan, `finance.dispatch_payment_gate=off` mematikan, dasar `finance.tahan_kirim_dasar_bayar`). Tidak ada hitungan kedua.
- Kas hanya lewat `create_receipt`. Tidak ada `cash_transactions` atau jurnal baru di luar pintu itu (`verify_cash_single_door`, `verify_posting_coverage`).
- Semua tulis uang/keputusan memakai CAS/klaim atomik pada status laporan (`verify_atomic_claim`) dan kunci idempotensi:
  - awalan `/api/payment-reports` masuk `IDEMPOTENT_PREFIXES` server dan `MONEY_PREFIXES` penjaga;
  - layar mengirim lewat `moneyPost` + `useIntentKey`.
- Rute keputusan bernama `terima` / `tolak`. Kata `reject|approve|verify|decide` tidak dipakai di path. Rute didaftarkan di `scripts/guardrails/verify_approval_queues.py` sebagai pintu ber-antrean Meja Keuangan `lapor_bayar`.
- Riwayat status laporan memakai `services/status_history.entry`.
- Notifikasi lewat `notification_service.create_addressed` (per izin/orang). Tidak memakai siaran `all`.
- Cara bayar dari daftar induk (`payment_method_service` / `usePaymentMethods`), tidak memakai literal.
- Rekening tujuan hanya dari `bank-accounts/receiving` PT pesanan. Rekening PT lain → 400.
- Pop-up hanya `DetailModal` / `FormModal` / `askConfirm` / `askReason`. Huruf `text-fs-*`, minimal 12 px. Berkas baru nol px/hex.
- Unduh lampiran lewat blob axios (`useBlobUrl`). Tidak memakai token di URL.
- Jangan ubah `deploy/`, `.env`, `memory/GATE_RECEIPT.*`, `frontend/yarn.lock`. Data nyata = STOP & ASK.
- Uji hemat: uji terarah per tugas; suite penuh + gate sekali di Tugas 9.

## Review Focus

1. **Terima ganda dan balapan.** Dua Finance menekan Terima bersamaan, atau Terima diulang setelah jaringan putus: tepat satu kwitansi. Panggilan kedua → 409 atau putar ulang idempoten. (Tugas 4)
2. **`create_receipt` gagal di tengah** (periode tertutup, rekening nonaktif): laporan tetap `menunggu`, tidak ada kwitansi setengah jadi, dan galatnya tampil di dialog. (Tugas 4)
3. **Pesanan dibatalkan atau kedaluwarsa saat laporan menunggu**:
   - laporan `menunggu` milik pesanan mati tidak bisa diterima (409 pemandu);
   - pesanan dengan laporan `menunggu` tidak dikedaluwarsakan penyapu. (Tugas 4, 5)
4. **Isolasi PT.** Laporan/lampiran pesanan PT lain → 403. Rekening PT lain → 400. Mode "Semua PT" memuat laporan PT dokumen. (Tugas 3)
5. **Pesanan lama dan non-CBD tidak berubah perilaku.**
   - Pesanan NET30 tetap lepas seperti dulu.
   - Pesanan CBD yang sudah `confirmed` sebelum fitur ini tidak tiba-tiba tertahan.
   - `release_unpaid` tetap membuka tahan.
   (Tugas 2)

---

### Task 1: Fondasi — izin, pengaturan, koleksi laporan

**Files:**
- Modify: `backend/access_modules.py`, `backend/permissions_config.py` (izin `payment_report.create|decide` + label + bawaan di atas)
- Modify: `backend/config_catalog_nilai.py` (`sales.batas_bayar_hari`; `consumers` diisi berkas Tugas 5)
- Modify: peta cakupan entitas (`backend/entity_scope.py` `field_for` / daftar koleksi bercakupan — ikuti cara `ar_receipts` didaftarkan)
- Create: `backend/services/payment_report_service.py` (kerangka: konstanta status `MENUNGGU="menunggu"`, `DITERIMA="diterima"`, `DITOLAK="ditolak"`; `next_number(entity_id) -> "LB-…"` memakai penomoran baku dokumen; `tampil(doc)` membuang `_id` dan isian internal)
- Test: `backend/tests_mem/test_LB1_fondasi.py`

**Interfaces:**
- Produces:
  - `payment_report_service.MENUNGGU|DITERIMA|DITOLAK`;
  - `next_number(entity_id: str) -> str`;
  - `tampil(doc: dict) -> dict`;
  - `nilai("sales.batas_bayar_hari", entity_id) -> int`.

- [ ] **Step 1: Uji gagal.**
  - `test_izin_payment_report_terdaftar_dan_bawaan`: sales & sales_admin memegang `create` tetapi tidak `decide`; finance memegang keduanya.
  - `test_batas_bayar_bawaan_3_per_pt`: `nilai(...)` = 3; diubah untuk satu PT → PT lain tetap 3.
  - `test_nomor_LB_berurutan_per_pt`.
- [ ] **Step 2: → FAIL.**
- [ ] **Step 3: Implementasi.**
- [ ] **Step 4: → PASS.** Lalu jalankan `python scripts/guardrails/verify_permission_checked.py` dan `verify_config_*.py` (yang ada). Pemeriksa literal izin baru boleh belum ada di tugas ini hanya bila penjaga mengizinkan daftar `DINAMIS`/menunggu. Bila tidak, pemeriksa pertama didahulukan dari Tugas 3: tambah satu rute baca `GET /api/sales-orders/{id}/payment-reports` di tugas ini.
- [ ] **Step 5: Commit** `feat(pembayaran): fondasi lapor bayar — izin, pengaturan batas bayar, koleksi laporan`.

### Task 2: Tahan sebelum gudang + kode bayar sejak disetujui

**Files:**
- Create: `backend/services/pay_hold_service.py`
- Modify:
  - `backend/services/so_lifecycle_service.py` (`submit_core` sesudah mencapai `approved`; `confirm_core` titik periksa sesudah `credit_gate.gate_checkpoint(LEPAS_GUDANG)`);
  - jalur keputusan ACC yang membuat pesanan `approved` (`backend/routers/so_approvals.py`, `backend/routers/sales_orders_extra.py` — cari semua penulis `approved`);
  - `backend/services/so_release_service.py` (`try_release` jalur anggun);
  - `backend/services/dispatch_payment_gate.py` (`release()` memanggil lepas otomatis);
  - `backend/services/so_status.py` (sub-status `menunggu_bayar`).
- Test: `backend/tests_mem/test_LB2_tahan_gudang.py`

**Interfaces:**
- Produces:
  - `pay_hold_service.start(order) -> dict|None`. Bila `evaluate(order).applies and blocked`, menulis `pay_hold={since, due_at, required, basis}` dan memanggil `payment_code_service.ensure_for_order`. Idempoten: tidak menimpa `since`/`due_at`.
  - `pay_hold_service.blocked(order) -> bool`.
  - `pay_hold_service.clear_if_paid(order_id) -> bool`. Bila tidak lagi `blocked`, menghapus penanda lalu memanggil `so_release_service.auto_release`. Mengembalikan apakah lepas terjadi.
- `confirm_core` melempar `HTTPException(409, PESAN_MENUNGGU_BAYAR)` bila `blocked` tanpa `dispatch_payment_release`. Bunyi `PESAN_MENUNGGU_BAYAR` = "Menunggu pembayaran dicek Finance — lapor bayar di rincian pesanan."
- `try_release` menangkap kasus itu: tulis `release.waiting="bayar"`, kembalikan `{released: False, waiting: "bayar"}`. Tidak ada 409 ke "Periksa & lepas".
- `so_status`: sub-status `menunggu_bayar` (label "Menunggu bayar") bila `pay_hold` ada dan status `approved`.

- [ ] **Step 1: Uji gagal.**
  - `test_cbd_disetujui_tertahan_dan_berkode`: pesanan CBD Rp 1.000.000 di-submit (auto-approve). Hasilnya `approved` + `pay_hold.required=1000000` + `payment_codes` ada.
  - `test_periksa_lepas_menunggu_bayar_tanpa_409`: `review_and_release` → `waiting="bayar"`, status tetap `approved`, tidak ada tugas outbound.
  - `test_confirm_lama_409_pemandu`.
  - `test_net30_tidak_tertahan` (Review Focus 5).
  - `test_dp50_tertahan_setengah`: `required = 50%`.
  - `test_gerbang_off_tidak_menahan`.
  - `test_sample_tidak_menahan`.
  - `test_release_unpaid_membuka_tahan_dan_melepas`: `dispatch-payment-release` beralasan → `confirmed`.
  - `test_kwitansi_finance_cukup_melepas`: kwitansi Finance teralokasi penuh lewat `create_receipt` + `clear_if_paid` → `confirmed`.
  - `test_pesanan_confirmed_lama_tidak_tertahan`: pesanan CBD yang sudah `confirmed` tanpa `pay_hold` tetap jalan. Gerbang surat jalan tetap berlaku seperti dulu.
- [ ] **Step 2: → FAIL.**
- [ ] **Step 3: Implementasi.**
- [ ] **Step 4: → PASS.** Uji lama yang menyentuh rilis/konfirmasi (`grep -l "review_and_release\|confirm_core\|try_release\|dispatch_payment" backend/tests_mem/*.py`) tetap hijau.
- [ ] **Step 5: Commit** `feat(pembayaran): pesanan wajib bayar dulu ditahan sebelum gudang; kode bayar sejak disetujui`.

### Task 3: API lapor bayar + lampiran

**Files:**
- Create: `backend/routers/payment_reports.py` (daftarkan di `backend/server.py` seperti router lain)
- Modify: `backend/services/payment_report_service.py` (`create_report`, `add_attachment`, `list_for_order`)
- Modify: `backend/idempotency.py` (`/api/payment-reports`), `scripts/guardrails/verify_money_idempotency.py` (`MONEY_PREFIXES`)
- Test: `backend/tests_mem/test_LB3_lapor.py`

**Interfaces:**
- Rute:
  - `POST /api/sales-orders/{id}/payment-reports` (izin `payment_report.create`), body `{amount, transfer_date, account_id, method, reference_no?, note?}` → laporan `menunggu`.
  - `POST /api/payment-reports/{id}/attachments` (izin `payment_report.create`, `UploadFile`, `storage_service.validate_upload`, `build_path("payment_reports", ext)`) → `{id: att_…, original_filename, content_type, size, uploaded_by, uploaded_at}`.
  - `GET /api/payment-reports/{id}/attachments/{att}` (izin `order.view` + akses pesanan) → berkas inline.
  - `GET /api/sales-orders/{id}/payment-reports` (izin `order.view`).
- Validasi `create_report`:
  - pesanan hidup, sesuai PT pengguna (`guard_doc`), dan sales hanya untuk pesanan yang boleh dibuka (`sales_ownership.assert_may_open`);
  - `pay_hold` aktif, atau `evaluate().shortfall > 0` → selain itu 409 "Pesanan ini tidak menunggu bayar";
  - `amount > 0`;
  - `account_id` ∈ `bank_account_change_service.daftar_penerima(PT pesanan, method)` → selain itu 400;
  - `method` non-tunai dari daftar induk;
  - laporan `menunggu` lain dengan `amount` dan `transfer_date` sama → 409 "Laporan yang sama masih menunggu dicek".
- Notifikasi `lapor_bayar_masuk` ke `permission=("payment_report","decide")`, PT pesanan, tautan rincian pesanan.

- [ ] **Step 1: Uji gagal.** Satu uji per validasi di atas, plus:
  - lampiran: PDF 200 KB diterima; berkas `.exe` ditolak; > 10 MB ditolak;
  - unduh oleh sales pemilik boleh; sales lain 403; pengguna PT lain 403 (Review Focus 4);
  - notifikasi `lapor_bayar_masuk` hanya ke pemegang `decide` di PT itu.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS** + `verify_money_idempotency.py`, `verify_auth_coverage.py`, `verify_notification_audience.py`, `verify_status_history.py`, `verify_payment_vocab.py`.
- [ ] **Step 5: Commit** `feat(pembayaran): API lapor bayar — laporan, bukti, daftar per pesanan`.

### Task 4: Terima / Tolak + B3 di server

**Files:**
- Modify: `backend/routers/payment_reports.py`, `backend/services/payment_report_service.py` (`terima`, `tolak`)
- Modify: `backend/services/ar_receipt_service.py` (`create_receipt`: tolak sales transfer ke pesanan ber-`pay_hold`)
- Modify: `scripts/guardrails/verify_approval_queues.py` (daftarkan pintu `terima`/`tolak` ke antrean `lapor_bayar`)
- Test: `backend/tests_mem/test_LB4_putus.py`

**Interfaces:**
- `POST /api/payment-reports/{id}/terima` (izin `payment_report.decide`):
  1. CAS `menunggu` → `memproses`.
  2. `create_receipt({customer_id, amount, method, account_id, receipt_date: transfer_date, reference_no, proof_url: "/api/payment-reports/{id}/attachments/{att0}", allocations: [{order_id, amount}], entity_id}, actor)`.
  3. Sukses → `diterima` + `receipt_id` + `status_history`. Gagal → kembali `menunggu`, lalu galat diteruskan (Review Focus 2).
  4. `pay_hold_service.clear_if_paid(order_id)`.
  5. Notifikasi `lapor_bayar_diterima` ke pelapor + sales pemilik (`also_users`).
  - Kembalian `{report, receipt_number, released: bool, waiting_bank: bool}`. `waiting_bank` = dasar `terverifikasi` dan masih `blocked`.
- `POST /api/payment-reports/{id}/tolak` (izin `payment_report.decide`), body `{reason}` (≥ 5 huruf): CAS `menunggu` → `ditolak`; notifikasi `lapor_bayar_ditolak` (alasan) ke pelapor + sales pemilik.
- Pesanan mati (`DEAD_STATUSES`) → `terima` 409 "Pesanan sudah batal/kedaluwarsa — tolak laporan ini" (Review Focus 3). `tolak` tetap boleh.
- `create_receipt` menolak dengan 409 "Pesanan ini menunggu lapor bayar — pakai Lapor bayar" bila tiga syarat terpenuhi:
  - pencatat tanpa `payment_report.decide`;
  - cara bayar bukan tunai;
  - salah satu alokasi menunjuk pesanan ber-`pay_hold`.

- [ ] **Step 1: Uji gagal.**
  - `test_terima_menerbitkan_kwitansi_uang_muka_dan_melepas`: jurnal Dr Bank / Cr Uang Muka 2-1400 sebesar nominal; pesanan `confirmed`; `released=True`.
  - `test_terima_sebagian_dp_tetap_tertahan_bila_kurang`.
  - `test_terima_dua_kali_satu_kwitansi`: panggilan kedua 409; jumlah kwitansi 1 (Review Focus 1).
  - `test_terima_gagal_kembali_menunggu`: periode tertutup → laporan `menunggu`, kwitansi 0.
  - `test_dasar_terverifikasi_waiting_bank`.
  - `test_tolak_tanpa_uang`.
  - `test_tolak_alasan_pendek_400`.
  - `test_terima_pesanan_mati_409`.
  - `test_sales_kwitansi_transfer_ke_pesanan_tertahan_409`.
  - `test_sales_tunai_dan_finance_transfer_tetap_boleh`.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS** + `verify_atomic_claim.py`, `verify_cash_single_door.py`, `verify_posting_coverage.py`, `verify_approval_queues.py`, `verify_money_idempotency.py`.
- [ ] **Step 5: Commit** `feat(pembayaran): Finance terima/tolak lapor bayar — kwitansi otomatis, lepas otomatis; kwitansi transfer sales ke pesanan tertahan ditolak`.

### Task 5: Batas waktu bayar + pengingat

**Files:**
- Modify: `backend/services/pay_hold_service.py` (`due_at = since + nilai("sales.batas_bayar_hari", PT)` hari)
- Modify: `backend/services/inventory_service.py` (`expire_old_reservations`: tambah pesanan `approved` ber-`pay_hold.due_at <= sekarang` tanpa laporan `menunggu`, langkah kedaluwarsa yang sama)
- Modify: `backend/services/notification_service.py` (`pay_due_soon`; `reservation_expiring` tidak lagi untuk `approved`/`waiting_stock`; laporan menunggu lewat batas → `lapor_bayar_lewat_batas` ke `decide`)
- Modify: `backend/config_catalog_nilai.py` (`consumers` `sales.batas_bayar_hari`)
- Test: `backend/tests_mem/test_LB5_batas.py`

- [ ] **Step 1: Uji gagal.**
  - `test_due_at_mengikuti_pengaturan_pt` (2 hari untuk satu PT).
  - `test_lewat_batas_kedaluwarsa_stok_lepas_uang_ke_titipan`: kwitansi Finance sebagian sebelumnya → titipan pelanggan bertambah; notifikasi `titipan_pesanan_batal`.
  - `test_laporan_menunggu_menahan_kedaluwarsa_dan_memberi_tahu_finance` (Review Focus 3).
  - `test_pengingat_h1_ke_sales_pemilik`.
  - `test_reservation_expiring_tidak_lagi_untuk_approved`.
  - `test_pesanan_tanpa_pay_hold_tidak_tersentuh_penyapu_baru`.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS** + uji lama kedaluwarsa (`grep -l "expire_old_reservations\|reservation_expir" backend/tests_mem/*.py`), `verify_config_*`, `verify_notification_audience.py`.
- [ ] **Step 5: Commit** `feat(pembayaran): batas bayar 3 hari per PT — kedaluwarsa otomatis, pengingat H-1, laporan menunggu tidak dibatalkan`.

### Task 6: Server untuk layar — Perjalanan, pelacak, meja

**Files:**
- Modify: `backend/services/order_journey_service.py` (langkah `bayar_dicek` di antara `disetujui` dan `dikonfirmasi`; dilewati bila tidak wajib bayar dulu; `commercial_invoice.available` benar sejak `pay_hold` untuk pesanan wajib bayar dulu)
- Modify: `backend/services/so_tracker_service.py` (`next_step` pesanan `approved` ber-`pay_hold` = "Menunggu bayar — Finance", peran `finance`; hold dihitung juga untuk status pra-gudang)
- Modify: `backend/services/work_desk_service.py`:
  - Meja Keuangan: antrean `lapor_bayar` (laporan `menunggu`, ref_type `payment_report`, `action_kind="decide_payment_report"`, extra `order_id, order_number, amount, transfer_date, account_label, attachments_count, reported_by_name`);
  - `bayar_sebelum_kirim` tidak memuat pesanan yang punya laporan `menunggu`;
  - Meja Admin Sales `_ket` mengenal "menunggu bayar (dicek Finance)" dan pesanan itu tidak masuk `siap_dikonfirmasi`.
- Modify: `scripts/guardrails/verify_home_kpi.py` hanya bila antrean masuk `approval_backlog_service.QUEUES` (tidak direncanakan; antrean Meja Keuangan saja)
- Test: `backend/tests_mem/test_LB6_layar.py`

- [ ] **Step 1: Uji gagal:**
  - Perjalanan CBD tertahan: `current_step == "bayar_dicek"`, invoice `available`.
  - Perjalanan NET30: `bayar_dicek` dilewati.
  - Pelacak `next_step`.
  - Antrean `lapor_bayar` berisi laporan menunggu PT pengguna saja.
  - Dedupe `bayar_sebelum_kirim`.
  - `_ket` Admin Sales.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS** + `test_MEJA*.py`, uji Perjalanan lama.
- [ ] **Step 5: Commit** `feat(pembayaran): tahap "Bayar dicek Finance" di Perjalanan, pelacak, Meja Keuangan & Admin Sales`.

### Task 7: Layar rincian pesanan — lapor, bukti, terima/tolak, cetak, Perjalanan

**Files:**
- Create:
  - `frontend/src/features/orders/payReport/payReportApi.js` (`listReports(orderId)`, `createReport(orderId, body, key)`, `uploadProof(reportId, file)`, `terima(reportId, key)`, `tolak(reportId, reason, key)` — tulis lewat `moneyPost`);
  - `LaporBayarDialog.jsx` (`FormModal`; nominal bawaan = kurang, tanggal bawaan hari ini, rekening dari `GET /bank-accounts/receiving?entity_id&method`, cara bayar dari `usePaymentMethods("masuk", PT)` tanpa tunai, referensi, catatan, bukti wajib);
  - `PayReportList.jsx` (status, nominal, tanggal, pelapor, bukti via `useBlobUrl`, alasan tolak; tombol Terima/Tolak untuk `payment_report.decide`).
- Modify:
  - `frontend/src/features/orders/DispatchPaymentGatePanel.jsx`: judul "Bayar sebelum gudang" bila tahan aktif; batas bayar + sisa hari; tombol "Lapor bayar"; tombol kwitansi langsung disembunyikan bagi pencatat yang akan ditolak server (tanpa `payment_report.decide` dan pesanan tertahan).
  - `frontend/src/features/orders/OrderDetailPanel.jsx` dan `frontend/src/features/documents/orderPrintDocs.js`: Faktur Komersial dan Konfirmasi tersedia sejak `approved` bila pesanan tertahan bayar.
  - `frontend/src/features/orders/OrderJourneyPanel.jsx`, `frontend/src/features/sales/mobile/MobileOrderJourney.jsx`: langkah `bayar_dicek` "Bayar dicek Finance".
- Test: `frontend/src/features/__tests__/lb7RincianPesanan.test.js`

- [ ] **Step 1: Uji gagal:**
  - Lapor bayar: bukti kosong → tombol kirim mati; kirim → POST laporan lalu unggah, lalu toast "Laporan bayar dikirim ke Finance" dan muat ulang.
  - Terima: pratinjau "Kwitansi Rp … ke rekening … akan diterbitkan" → konfirmasi → POST terima; kembalian `waiting_bank` menampilkan "Menunggu cocok mutasi bank".
  - Tolak: `askReason`; batal → tidak ada POST.
  - Tanpa `payment_report.decide` tidak ada tombol Terima/Tolak.
  - Tombol kwitansi langsung tersembunyi untuk sales pada pesanan tertahan.
  - Faktur Komersial tampil pada pesanan `approved` tertahan.
  - Langkah Perjalanan desktop dan HP.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS** + uji lama berkas yang disentuh (`f10DispatchPaymentGate`, `uatV3S2Cbd`, Perjalanan, OrderDetailPanel), `verify_ui_standard`, `verify_custom_modals`, `verify_money_idempotency`, `verify_payment_vocab`.
- [ ] **Step 5: Commit** `feat(pembayaran): Lapor bayar di rincian pesanan — bukti, terima/tolak Finance, invoice sejak disetujui, tahap di Perjalanan`.

### Task 8: Meja Keuangan, Meja Admin Sales, HP, notifikasi

**Files:**
- Modify:
  - `frontend/src/features/finance/FinanceDesk.jsx`: kelompok `uang_masuk` memuat antrean `lapor_bayar` (izin `payment_report.decide`); aksi `decide_payment_report` di tempat.
  - `frontend/src/features/desks/deskPanels.js` (`queue:lapor_bayar` → panel laporan) + Create `frontend/src/features/desks/PayReportQueuePanel.jsx`: rincian laporan + bukti + pratinjau pesanan dari registri, dengan Terima/Tolak memakai `payReportApi` Tugas 7.
  - `frontend/src/features/sales_admin/SalesAdminDesk.jsx`: keterangan "Menunggu bayar".
  - Rincian pesanan HP (cari komponen rincian pesanan di `frontend/src/features/sales/mobile/`): panel bayar yang sama dengan `LaporBayarDialog`, input berkas `accept="image/*,application/pdf" capture="environment"`.
  - `frontend/src/features/sales/mobile/MobileArReceipt.jsx`: pesan pemandu bila pesanan terpilih tertahan.
  - `frontend/src/components/NotificationCenter.jsx`: label jenis `lapor_bayar_masuk`, `lapor_bayar_diterima`, `lapor_bayar_ditolak`, `lapor_bayar_lewat_batas`, `pay_due_soon`.
- Test: `frontend/src/features/__tests__/lb8MejaHp.test.js`

- [ ] **Step 1: Uji gagal:**
  - Baris `lapor_bayar` di Meja Keuangan membuka pop-up dengan bukti dan pratinjau pesanan, dengan Terima/Tolak di tempat (sukses → toast + muat ulang kartu).
  - Tanpa izin `decide` kartu tidak tampil.
  - Keterangan Admin Sales.
  - Lapor bayar dari HP.
  - Pesan pemandu `MobileArReceipt`.
  - Label notifikasi.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS** + `mejaG2*.test.js`, `meja*.test.js`, uji HP lama.
- [ ] **Step 5: Commit** `feat(pembayaran): lapor bayar di Meja Keuangan (terima/tolak di tempat), Admin Sales, HP sales, notifikasi`.

### Task 9: Uji penuh, gate, tangkapan, laporan

**Files:**
- Create: `docs/superpowers/plans/2026-11-25-lapor-bayar-cbd-hasil.md` + folder `2026-11-25-lapor-bayar-cbd-hasil/` (tangkapan + skrip).
- Modify:
  - `docs/blueprint/04_POLA_UI.md` (pola "tahap bayar di alur pesanan");
  - `CODEBASE_MAP.md` (`python3 scripts/gen_codebase_map.py`);
  - materi pelatihan Keuangan yang menyebut sales mencatat kwitansi transfer CBD (`docs/pelatihan/2026-11-18_keuangan/`): tambah catatan "berubah sejak Lapor Bayar" — teks saja, skrip uji latihan disesuaikan bila langkahnya menyentuh kwitansi CBD.

- [ ] **Step 1:** Suite penuh `backend/tests_mem` + jest di latar pada pohon akhir. Bandingkan dengan gelombang meja 2; kegagalan lingkungan yang sama (`odItemCancel`, `phase4R2`) dicatat apa adanya.
- [ ] **Step 2:** Gate `--quick` + `--ci` sekali. Nilai dengan kedua pembanding (`docs/reviews/2026-11-13/garis-dasar/bandingkan_gate.py`, `scripts/blueprint/bandingkan_pelanggaran_gate.py docs/blueprint/garis-dasar-gate/2026-11-15_gate_ci.log <log>`). Pelanggaran baru = penghalang.
- [ ] **Step 3:** Tangkapan. Skrip membuat pesanan CBD dan DP50 lewat API di lingkungan uji lokal (data acuan; bukan data nyata), lalu memotret:
  - tahap tertahan di rincian dan Perjalanan;
  - dialog Lapor bayar desktop dan HP;
  - Meja Keuangan pop-up lapor bayar → Terima → pesanan lepas;
  - Tolak → notifikasi sales;
  - Faktur Komersial "Belum dibayar".
- [ ] **Step 4:** Laporan hasil: yang berubah untuk pengguna, tugas → commit, uji apa adanya, gate, keputusan pelaksanaan, pertanyaan pemilik.
- [ ] **Step 5: Commit** `docs(pembayaran): hasil Lapor Bayar CBD`.
