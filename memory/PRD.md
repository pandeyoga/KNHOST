# PRD — Kain Nusantara ERP (lanjutan dari repo github.com/kakjsbsbs/KN)

## Sesi W2-P08 (2026-10-04, repo pandeyoga/KNHOST) — Gelombang 2: kebutuhan klien W2-REQ-01..09 selesai implementasi
Permintaan user: "lanjutkan development … selesaikan semua penemuan & perbaikan gelombang 2 … review lagi gelombang 1 dan 2, selesaikan yang tidak butuh keputusan/eksternal info, lalu report."
- REQ-09 pembulatan roll eksplisit + izin `order.exact_cut`; REQ-08 roll tanpa tag diblokir saat dispatch, pengecualian izin `wms.untagged_override` + alasan + audit; REQ-06 tugas keputusan selisih PO (`/api/po-variance-tasks`) + notifikasi MD/Finance; REQ-04 angka grup di papan stok sales; REQ-05 ganti entitas pembeli dari form PO (draft dipertahankan); REQ-07 reservasi bahan makloon (`material_reservations`, `/api/material-reservations`); REQ-02 preview/batch/rollback master (`/api/master-governance/*`, koreksi nama tanpa ubah SKU). REQ-01/03 dari sesi sebelumnya.
- Bukti: docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/ (IMPLEMENTATION.md, regression_p08_fase2_6.py 36/36), test_reports/iteration_142.json (UI).
- Tracker: requirements-tracker 9/9 ready_for_validation; phase P08 ready_for_validation; P09 (validasi gabungan) = tugas auditor.
- Ditunda (keputusan pemilik): standar penamaan, alias warna customer, COMM-04, HR-04, RFID-05 (perangkat), OPS-01 (DB produksi), AUDIT-03 (GitHub Actions).
- Backlog P1: alokasi SO membaca reservasi bahan makloon; UAT 3 gudang → 3 SJ + printer/reader fisik; seed contoh jalur peringatan uji wajib R&D.


## Sesi P21c (2026-10-04) — Tanya KN lebih luas · Keputusan pemilik 5 kasus terakhir
- Tanya KN di detail **retur penjualan** (`ReturnDetail.jsx`), **retur pembelian** (`ReturnDetailPanel.jsx`), **tagihan supplier** (`VendorBillDetailPanel.jsx`), **order makloon** (`MakloonOrderDetailPanel.jsx`) + pertanyaan bawaan per jenis. Backend: `CONTEXT_TYPES` +4, `get_document` + `sales_return`/`purchase_return` (enum tool JSON diperbarui), ringkasan bayar tagihan via `bill_financials`, langkah makloon ringkas (tanpa tarif), milestone retur. Diuji AI nyata (4/4 benar, angka terverifikasi) + `tests/test_tanya_kn_doc_context.py` (4 lulus; sales ditolak tagihan/retur beli; makloon mengikuti izin layar sales).
- Keputusan pemilik (PG04–PG08, `audit/owner-questions-P21.md`): COMM-04 jurnal Beban Pemasaran saat realisasi & dibalik saat batal (implementasi P22); HR-04 tunggu slip resmi konsultan (blocked); RFID-05 ditutup diuji simulasi; OPS-01 divalidasi saat deploy pertama; AUDIT-03 cukup uji lokal pre-commit (bukti sandbox: commit bersecret diblokir). Cakupan: 93 lulus · 3 blocked · 2 partial.
- **Sesi berikut: baca `memory/HANDOFF_P22_NEXT.md`** (prioritas COMM-04).

## Sesi P21b (2026-10-04) — Soal uji fleksibel · Tahap A audit tuntas · Tanya dari Dokumen
**Pesan user:** "Soal Uji Fleksibel … · Lanjutan Audit: DESIGN-04, DOC-03..05, OPS-02..04 + uji layar DOC-06, DESIGN-06, HR-06 · Tanya dari Dokumen: tombol Tanya KN di detail pesanan/pelanggan dengan konteks dokumen".
**Implemented:**
- Eval: `tools/ai_eval/build_questions.py` `ALTERNATIVES` (7 soal: laporan siap-pakai vs metrik/daftar, dibuktikan dari jawaban nyata) → `questions_v1.json` field `alternatives`; `run_eval.py` menilai harapan utama ATAU alternatif, mencatat `matched` (expected/alternative/template), ringkasan `alternative_n`. 7/7 lulus; jawaban salah tetap gagal (`tests/test_ai_eval_judge.py`).
- Tanya dari Dokumen: `AskKnButton` + item "Tulis pertanyaan sendiri…" (`ask-kn-<type>-custom`), pertanyaan bawaan diberi periode; Tanya KN menyimpan konteks dokumen sebagai chip di komposer (`tanya-context-chip`, hapus `tanya-context-clear`, placeholder "Tanya tentang <dok>…") dan menyertakannya ke setiap pertanyaan sampai dihapus/percakapan baru. `get_document` kini memuat paid_total/outstanding/termin/sales/tahap → AI menjawab sisa tagihan; hasil dibungkus `document` agar angka dokumen ikut diverifikasi pemeriksa angka.
- Audit (harness `audit/iterations/2026-10-04-P21-partial-api/repro_p21.py` 40/40, self-clean): DESIGN-04, DOC-03, DOC-04, DOC-05, OPS-02, OPS-03, OPS-04 → tested_pass. UAT iter138/139: DOC-06, DESIGN-06, HR-06, TANYA-DOC lulus. Cakupan: tested_pass 91 · partial 5 (RFID-05, HR-04, COMM-04, OPS-01, AUDIT-03 = butuh pemilik/perangkat).
- FIX: (1) Kunci Saga tidak mendaftar 5 koleksi ber-claim() (goods_receipts, purchase_orders, purchase_requisitions, customers, bank_statement_lines) → kunci menggantung tak terlihat/tak bisa dilepas; + test penjaga `tests/test_saga_lock_registry.py`. (2) Unggahan file rusak (teks ber-ekstensi gambar/PDF) dulu diterima → `storage.validate_upload` cek tanda-tangan isi di 11 jalur (`tests/test_upload_content_check.py`). (3) Notifikasi "Perlu Revisi" desain ditelan dedupe & disiarkan ke semua desainer → ref per transisi, hanya ke pemilik desain. (4) CAS approve/reject PO ikut `version`.
**Backlog:** P1 — perbarui test lama basi (design ID seed lama di test_iter39/40/design_studio_flow, alasan lepas kunci ≥10 karakter di test_iter314/315, kebijakan approval finance di test_iter302); P2 — Tahap C keputusan pemilik (COMM-04, HR-04, RFID-05, OPS-01, AUDIT-03); delegasi approval (fitur belum ada).

## Sesi P21 (2026-10-04) — Tanya KN LIVE dengan kunci OpenAI user + evaluasi model nyata
**Pesan user:** "lanjutkan development dari repo KNHOST … (terhenti di modul AI Analytics: template, status AI chat_enabled=false, has_key=false)". Pilihan: lanjutkan AI Analytics, kunci OpenAI milik user, ikuti PRD/memory.
**Lingkungan:** clone → rsync /app, backend/.env (CORS eksplisit, SESSION_COOKIE_SECURE, KN_DEMO_DATA, SEED_DEMO_ENABLED, OCR_ALLOW_MOCK), pip/yarn, `KN_DISABLE_SCHEDULER=1 seed_realistic`, rebuild FE, restart backend. Integritas 246/2 (baseline). Kunci OpenAI disimpan di DB (`PUT /api/admin/integrations`, uji koneksi OK, 133 model), `ai.enabled=true`, model `gpt-6-sol` (utama) / `gpt-6-luna` (narasi).
**Hasil:**
- Chat nyata (stream OpenAI Responses) berfungsi; prompt caching terbukti (spike §7.2: ~16–24 rb dari ~25 rb token input ter-cache).
- Eval model nyata 120 soal (`tools/ai_eval/reports/model_20261004_123209.json`): tool 94,2% · argumen (setara bisnis) 90,0% (ketat 66,7%) · pemeriksa angka 98,3% · hak akses 15/15 → semua target §9 tercapai.
- Pemeriksa angka (`services/ai_number_check.py`): tidak lagi positif palsu untuk jam ("18:50 WIB"), rentang tanggal ("21–27 Sep"), label/kode hasil ("b1_30", "PO-00011", judul "> 60 hari"), jumlah baris ("12 PO"), angka yang diulang dari pertanyaan ("10 pelanggan"), dan blok ```kn-*```.
- Narasi AI template ditolak (kembali ke ringkasan otomatis) bila angka tidak cocok data (`services/ai_narrative.py`).
- Harness eval: pemakaian dicatat fitur `bi_chat_eval` (masuk anggaran & halaman Biaya "Evaluasi model (admin)", tidak memakan kuota harian pengguna); opsi `--ids`; simpan argumen/galat/unmatched; jawaban yang dirutekan ke template dihitung benar.
- Test lama Tanya KN mengasumsikan tanpa kunci & mematikan `ai.enabled` di akhir → kini memulihkan status AI semula. 110 test Tanya KN lulus; agen uji iterasi 137: backend 6/6, UI 100%.
**Backlog:** P1 — 7 soal eval dengan pilihan tool alternatif yang sah (q047/q053/q057/q074/q076/q091/q093: run_report vs query_metrics/list_records) → tinjau apakah soal menerima >1 tool; P1 — sisa Tahap A audit (DESIGN-04, DOC-03..05, OPS-02..04), UAT DOC-06/DESIGN-06/HR-06, akar reservasi scheduler backorder tanpa rebuild saldo; P2 — harga gpt-6-sol/luna masih "perkiraan"; laporan terjadwal via WhatsApp (bila diminta); Tahap C keputusan pemilik.

## Sesi P20 (2026-10-04) — Tahap A partial API (12/19) + UAT layar lanjutan (7/10 lulus)
**Pesan user:** "lanjutkan … UAT Layar Lanjutan: PROD-06, INV-06, SALE-06, APAR-06, GL-06 dan lima kasus sisanya sampai tuntas · Kasus Partial API: selesaikan 19 kasus partial berbasis API dari Tahap A, mulai dari GRN-05 dan PRET-01". Pilihan: clone repo publik, API dulu lalu UAT, daftar kasus dari repo.
**Hasil:** harness `audit/iterations/2026-10-04-P20-partial-api/repro_p20a..e.py` 69/69 lulus (GRN-05, PRET-01, PROD-02, PROD-05, SALE-05, APAR-02, APAR-05, GL-01, GL-05, HR-01, HR-03, HR-05). UAT iter 134–136: PROD-06, INV-06, SALE-06, APAR-06, GL-06, COMM-06, OPS-06 lulus; DOC-06, DESIGN-06, HR-06 sebagian.
**Perbaikan:** jurnal nota kredit retur jual gagal kini terlihat & bisa diulang; nota kredit 'ar' mengurangi sisa tagihan SO; void kwitansi yang depositnya terpakai ditolak tanpa efek parsial; posting/bayar payroll bersamaan aman (CAS). Rincian: `memory/HANDOFF_P20_2026-10-04.md`.
**Backlog:** P0 — DESIGN-04, DOC-03, DOC-04, DOC-05, OPS-02, OPS-03, OPS-04 (Tahap A sisa); P1 — sisa UAT DOC-06/DESIGN-06/HR-06; akar reservasi scheduler tanpa rebuild saldo; P2 — Tahap C keputusan pemilik (COMM-04, HR-04, RFID-05, OPS-01, AUDIT-03).


## Sesi P19b (2026-10-03) — UAT rantai penerimaan GRN-01 · QC-04 · QC-06 + fitur Tahan/Lepas roll
**Pesan user:** "lanjutkan development dari repo KNHOST … (agen uji P19 berhenti sebelum UAT layar)". Pilihan: clone repo publik → /app, seed demo bawaan, **UAT + bangun fitur yang kurang**.
**Lingkungan:** clone → rsync /app, backend/.env (CORS eksplisit, SESSION_COOKIE_SECURE, KN_DEMO_DATA, SEED_DEMO_ENABLED, OCR_ALLOW_MOCK), pip/yarn, seed_realistic (ulang 1× krn BulkWriteError), rebuild FE. Integritas 246/2 (FAIL 2 = KANDA/SO-00001 seed lama).
**Implemented:**
- FITUR QC-06 Tahan/Lepas roll: `services/roll_hold_service.py`, `POST /api/inventory/rolls/{id}/hold` (wms.update, alasan wajib, available|quarantine → blocked) & `/release` (wms.approve → status semula; juga mencabut tahanan inspeksi warna/handfeel). `process_qc_decision` menolak bila ada roll ditahan. Roll tak-terinspeksi yang diputuskan lewat sampling ditandai `qc_via_sampling`.
- Genealogy Jejak Barang (`roll_timeline_service._qc_events`): asal GRN, inspeksi 4-point, riwayat grade, sampling, keputusan QC, tahan/lepas.
- FE: `inventory/RollHoldControl.jsx` (tab Roll & modal inspeksi roll), badge DITAHAN, header Jejak (PO/lot/hold); QcPlanPanel tombol roll selalu tampil; modal keputusan QC dibuka lagi setelah modal roll ditutup; widget Bantuan disembunyikan saat modal/dialog/popup terbuka.
- BUG QC-04: retur otomatis QC-reject tanpa PPN (hutang PPN tersisa) → kini `po_ppn_rate` dipakai bersama retur manual.
- STATUS "Lunas lewat retur" (2026-10-04): `_po_financials` → `payment_status="settled_by_return"` bila PO belum dibayar tetapi hutangnya habis karena retur (outstanding 0). Retur dibalik → kembali `unpaid`. FE: badge teal "Lunas lewat retur" di daftar PO (billingState), panel ringkas PO (+ catatan `po-compact-settled-by-return`), Supplier 360 (`PO_PAYMENT_LABEL`). Harness kini 29/29.
- CHIP FILTER STATUS BAYAR PO (2026-10-04): `GET /api/purchase-orders?payment=unpaid,partial,paid,settled_by_return` (dipisah koma; PO lama tanpa field = unpaid; nilai tak dikenal diabaikan) + `status-counts` kini mengembalikan `by_payment` (tak terpengaruh chip) dan `by_status` ikut chip. FE `admin/po/POPaymentChips.jsx` (testid `po-payment-filter`, `po-payment-chip-<all|unpaid|partial|paid|settled_by_return>`, `po-payment-chip-count-*`) di atas tab status daftar PO; kartu angka & tab ikut tersaring. Harness 30/30.
**Bukti:** `audit/iterations/2026-10-03-P19-uat-receiving/` (harness 27/27, UAT iter131–133). GRN-01, QC-04, QC-06 → tested_pass.
**Backlog:** P0 Tahap A 19 partial API (HANDOFF_P19 §1); P1 sisa UAT layar PROD-06, INV-06, SALE-06, APAR-06, GL-06, HR-06, COMM-06, DESIGN-06, DOC-06, OPS-06; P2 keputusan pemilik COMM-04, HR-04, RFID-05, OPS-01, AUDIT-03. Catatan: Cycle Count `cc-add-product-select` tak tereproduksi (kode KNSelect/cmdk benar; kemungkinan artefak otomasi).

## Sesi P19 (2026-10-03) — verifikasi + rencana disetujui
**Pesan user:** "buatkan handoffnya saja akan saya lanjutkan di sesi berikutnya".
**Dicek:** GRN-00003 tidak ada lagi di DB (tidak perlu reversal); backend 200. Tidak ada perubahan kode.
**Rencana disetujui:** Tahap A (19 partial API) → Tahap B (13 UAT layar) + perbaiki pilih produk Cycle Count & tombol Bantuan yang menutupi; Tahap C dikumpulkan untuk keputusan pemilik. Detail: `memory/HANDOFF_P19_2026-10-03.md`.


## Sesi P18 (2026-10-03, repo pandeyoga/KNHOST) — menyelesaikan kasus audit "partial"
**Problem statement (user):** "saya ingin anda lanjutkan development dari repo ini https://github.com/pandeyoga/KNHOST … selesaikan 55 sebagian".
**Pilihan user:** balik residu GRN-00003 (lingkungan baru di-seed ulang → tidak ada residu); baca packing list OCR **permanen aktif**; kunci OpenAI user diisi ulang (DB saja); urutan ikut handoff/audit; repo publik.
**Arsitektur yang disentuh:** FastAPI routers (uoms, customers, sales_orders, vendor_bills, cycle_count, purchase_return_service, 6 router IDOR), service baru `customer_merge_service.py`; FE `VendorBillPayments.jsx`, `CustomerMergeSection.jsx`, `CycleCount.jsx`, `useViewDeepLink.js`; alat `audit/tools/set_status.py`.
**Implemented (2026-10-03):** 18 kasus partial → tested_pass (AUTH-01/02/06, MASTER-01..06, COMM-01, PRET-02/03/05/06, APAR-01, INV-03, INV-04, DOC-02). Bug: IDOR baca PT lain (9 endpoint), UOM terpakai bisa diubah, qty retur dipotong diam-diam, SO ke pelanggan merged/nonaktif, ?entity hilang dari URL. Fitur: gabung pelanggan duplikat, batal pembayaran AP, hitung ulang cycle count. Harness p18a..f 60/60, UAT iterasi 129 lulus, integritas 248/0.
**Backlog:** P0 — 19 partial berbasis API (lihat `memory/HANDOFF_P18_2026-10-03.md` §6.1); P1 — 13 UAT layar; P2 — butuh pemilik/perangkat: COMM-04, HR-04, RFID-05, OPS-01, AUDIT-03.
**Next tasks:** lanjut §6 handoff P18.


## Problem statement (asli, 2026-09-17)
Lanjutkan development repo KN. Fitur dispatch/pengiriman masih sangat basic: tidak ada quick action di dasbor
(hanya list yang harus buat dispatch), belum ada history pengiriman, visualisasi status pengiriman yang sedang
diproses, ketersediaan armada internal, jenis pengiriman (kurir pihak ketiga dll). Pertanyaan: bagaimana fitur
customer ambil sendiri & validasinya? Data pengiriman (alamat kirim) masih bocor/terekspos pada SO yang ambil sendiri.

## Pilihan user
- Bangun semua sekaligus: dasbor dispatch + quick action, visualisasi status, ketersediaan armada, jenis pengiriman
  (internal / kurir pihak ketiga / ambil sendiri), history.
- Ambil sendiri: kode pickup unik + verifikasi identitas pengambil (nama + no. ID), tanpa driver/armada/alamat kirim.
- Kurir pihak ketiga: nama kurir, no. resi, biaya kirim, estimasi tiba.
- Armada: master kendaraan + driver dengan status (tersedia / dalam perjalanan / perawatan), status berubah otomatis.

## Arsitektur (yang disentuh)
- Backend FastAPI: `services/logistics_service.py` (moda self_pickup, kode pickup, handover, dashboard, history, redaksi kode),
  `services/fleet_service.py` (baru — master kendaraan `fleet_vehicles`, status sopir turunan), `routers/logistics.py`
  (endpoint baru), `schemas_logistics.py`, `entity_scope.py` (+fleet_vehicles scoped), `services/so_verify_service.py`
  (anti-bocor alamat pada SO ambil).
- Frontend React: `features/logistics/` → `LogisticsView` (tab Dasbor/Daftar/Riwayat/Armada), `DispatchDashboard`,
  `HistoryPanel`, `FleetPanel`, `PickupHandoverPanel`, `DeliveryCreateModal` (moda otomatis dari metode pemenuhan SO),
  `DeliveryDetailModal` (cabang pickup), `sales_admin/OrderPreviewCard` (sembunyikan alamat untuk SO ambil).
- Frontend TIDAK hot-reload: `setsid nohup bash /app/scripts/rebuild_frontend.sh > /app/.rebuild.out 2>&1 &`.
- Env: backend/.env CORS_ORIGINS harus daftar origin eksplisit (bukan `*`).

## Persona
Admin gudang / manajer (buat & kelola pengiriman, armada), petugas gudang (serah terima pickup), sopir (tugas hari ini),
sales / admin sales (pantau, bagikan kode pickup ke pelanggan).

## Sudah diimplementasikan (2026-09-17)
- Dasbor Pengiriman: KPI (SJ menunggu, menunggu diambil, diproses, di jalan, ETA hari ini, terlambat, terkirim hari ini),
  aksi cepat per SJ (Buat pengiriman / Siapkan pickup), antrean serah terima pickup, alur status (bar), moda (donut),
  ringkasan armada, daftar sedang diproses, baru selesai/gagal.
- Jenis pengiriman: Ekspedisi (kurir, resi, layanan, biaya kirim, ETA) · Armada sendiri (kendaraan master + sopir) ·
  Diambil pelanggan (kode pickup 6 karakter, tanggal ambil).
- Validasi ambil sendiri: SO `fulfillment_method=ambil` wajib moda self_pickup (dan sebaliknya ditolak); tidak ada
  alamat/plat/sopir; tahapan hanya lewat POST pickup-handover (kode cocok + nama pengambil [+ no. ID]); kode salah
  ditolak & dihitung; kode disembunyikan dari peran gudang/sopir (mereka mencocokkan kode yang disebut pengambil).
- Anti-bocor: `shipments/unassigned` & `order_preview` tidak mengirim alamat kirim untuk SO ambil.
- Riwayat: filter tanggal/moda/status/kata kunci, statistik (terkirim, gagal, rata-rata hari, total biaya ekspedisi), CSV.
- Armada: CRUD kendaraan, perawatan ⇄ tersedia, otomatis on_trip saat berangkat & lepas saat tiba/gagal/selesai,
  status sopir turunan dari pengiriman aktif; kendaraan maintenance/on_trip tak bisa dipilih.
- Seed demo: `scripts/seed_dispatch_demo.py`; smoke API: `scripts/smoke_dispatch.sh`.

## Setup ulang 2026-09-18 (repo nakisbdvsb/KN)
- Repo di-overlay ke /app (`.env` dipertahankan; CORS_ORIGINS diisi origin preview eksplisit — wajib, server menolak `*`).
- pip: filter baris `emergentintegrations`/`litellm` (konflik pin; sudah ada di base image). FE: `yarn install --frozen-lockfile` + `bash scripts/rebuild_frontend.sh`.
- Seed: `python seed_realistic.py` → `scripts/seed_dispatch_demo.py` → `backfill_po_payment_due.py` → `seed_endek_showcase.py` → `seed_design_scores_demo.py`.
- Verifikasi: `/api/logistics/dashboard` mengembalikan 5 pengiriman demo; UI Dasbor Pengiriman render (screenshot).
- Temuan kecil: `OrderJourneyPanel` menampilkan "Armada sendiri" untuk moda self_pickup (belum ada cabang pickup) → masuk P1 di bawah.

## Sinkron Permintaan Desain ↔ Design Studio (2026-09-18)
- Permintaan Desain kini memakai master kategori yang SAMA dengan Design Studio (Kategori Pattern + Kategori Design)
  menggantikan `target_type` legacy (tetap diterima API). Modal buat permintaan 3 bagian (sumber · apa · siapa/kapan).
- Desainer: dari detail permintaan → "Buat & buka desain" (`POST /design-requests/{id}/create-design`: desain Studio dibuat
  dengan kode otomatis, brief/kategori/lini ikut, tertaut dua arah `request_id`, permintaan → Dikerjakan) atau "Tautkan
  yang sudah ada" (`/link-design`; hanya desain berjalan & belum tertaut).
- Status permintaan MENGIKUTI siklus hidup desain (`design_studio_service.transition` → `sync_from_design`):
  submit → Menunggu keputusan · request_revision → Minta revisi (+revision_count, alasan) · approve → ACC.
  approve/reject langsung di permintaan yang tertaut Studio ditolak 400 (keputusan + nilai di halaman desain).
- UI: detail 2 kolom (brief, desain tertaut dengan cover/status/nilai, riwayat | fakta, tindakan), stepper status,
  kartu papan menampilkan kategori, pelanggan/SO, kode & status desain, desainer, tenggat. Deep-link `openRnd({view:"rnd-designs", designId})`
  → `RndDesignsView` prop `focus`. Halaman desain menampilkan chip "Dari permintaan …".
- Seed `seed_design_requests()` memakai alur sinkron. Uji: `backend/tests/test_iter319_dsr_studio_sync.py` (9/9), iteration_28.

## Galeri Referensi Brief (2026-09-18)
- `design_requests.references[]` (storage scope `design_requests`): POST/GET/DELETE `/design-requests/{id}/references[/{fid}]`
  (unggah/hapus izin `design_request.create` = pembuat permintaan; hanya gambar; status belum ACC/batal).
- `_propagate_references` menyalin ke desain tertaut sebagai berkas `kind=reference` (penanda `source_reference_id`, idempoten)
  saat create-design / link-design dan saat referensi baru ditambah setelah tertaut.
- UI: `ReferenceGallery.jsx` — pratinjau lokal di modal buat (diunggah setelah permintaan tercipta), galeri + unggah/hapus di
  detail, thumbnail kecil di kartu papan.

## Permintaan Sample R&D — UI baru cermin alur Desainer (2026-09-18)
- Setup ulang dari repo gatadadavaoa/KN (overlay ke /app, .env dipertahankan, CORS eksplisit, seed `seed_realistic.py`).
- Pilihan user: satu papan "Permintaan Sample" + rincian bergaya Studio dengan 3 TAB terpisah Labdip / Handfeel / Proofing;
  pembuat admin/manager/MD/sales; pengerja role MD (custom role & access diperbaiki nanti). Mekanisme server TIDAK diubah.
- Frontend `features/rnd/`: `RndSamplesView` (KPI, tab Papan/Daftar, chip jenis & status, kolom draft→decided,
  `SampleBoardCard`), `SampleFormModal` (FormModal 3 bagian bernomor: dari mana · apa yang disampling · kapan),
  `SampleDetailPanel` (DetailModal framed, kepala + stepper, 2 kolom, aksi kanan), `SampleTypeTabs` (tab per jenis,
  jenis yang belum diminta → tombol tambah via PATCH sample_types), `SampleRoundList` (+prop `onlyType`).
- `hubTabs`: rnd-samples kini juga untuk `md` & `sales_admin`. `navMeta` judul diperbarui.
- Testing agent iterasi 29: backend 5/5, frontend 100% (papan, filter, buat, tab jenis, kirim, batal, role MD).

## Galeri Bukti Per Tab (2026-09-18)
- `features/rnd/SampleProofGallery.jsx` (kolom per supplier, thumbnail tiap round dgn lencana R<n> & titik hasil, lightbox
  prev/next/Esc) + `ProofImage.jsx` (muat bukti via axios blob agar header Authorization/X-Entity-Id ikut; cache object URL).
- Dipasang di `SampleTypeTabs` setelah tabel perbandingan, hanya untuk jenis yang diminta. Testing agent iterasi 30: 100%.

## Tab per Jenis di hub R&D — Labdip / Handfeel / Proofing (Master) (2026-09-18)
- View baru `rnd-labdip`, `rnd-handfeel`, `rnd-proofing` → `features/rnd/SampleTypeGalleryView.jsx` (+ `SampleTypeCard.jsx`),
  cermin "Desain & Pattern (Master)": KPI, cari + saringan (status/supplier/hasil/skor/ronde/bukti), grid kartu bersampul
  foto bukti, tombol "Sampel <Jenis> Baru" (SampleFormModal `lockType`), klik kartu → rincian dengan tab jenis aktif
  (`initialType`). Dibatalkan disembunyikan kecuali difilter. Terdaftar di hubTabs/navMeta/roles/AppViewRouter.
- Testing agent iterasi 31: frontend 100% (MD + admin, buat dari tab, filter, regresi papan & desain).

### 2026-06 — Peran & Hak Akses (custom role, 3 tingkat per modul)
- Backend: `access_modules.py` (katalog 24 modul: label/deskripsi/resources/nav, `apply_levels`, `nav_for_levels`),
  `services/custom_role_service.py` (buat/ubah/hapus/reset; peran kustom tersimpan di `custom_roles`, matriks izin di
  `permission_settings.matrix`; registry `role_registry.register_custom_roles` disinkron saat start & tiap perubahan),
  router `/api/access/modules|roles` (izin permission.view/update). Admin dikunci; bawaan tidak bisa dihapus/ganti nama.
- Frontend: tab **Peran & Hak Akses** di Badan Usaha & Akses (`RoleAccessPanel`, `RoleEditorDrawer`, `RoleModuleRow`,
  `RoleMenuPreview`): kartu peran + jumlah akun, segmented 3 tingkat per modul, salin dari peran, semua-modul cepat,
  pratinjau menu nyata (buildNavGroups dgn overlay `__preview`), dialog konfirmasi perubahan, peringatan modul sensitif.
- `roles.js`: `registerDynamicRoles` (registry/ROLE_NAV/ROLE_HOME dinamis, ROLE_OPTIONS ikut → formulir akun),
  `roleCanSee` rekursif inherit. `App.js`: poll `/api/roles` + `/auth/me` tiap 60 dtk + event `kn:roles-changed`.
- Testing agent iterasi 32: backend 14/14, frontend 100%.
- Catatan lingkungan: frontend dilayani bundle statis → `bash scripts/rebuild_frontend.sh` setelah ubah src;
  backend/.env butuh CORS_ORIGINS eksplisit (bukan `*`).

### 2026-06 — Notifikasi sinkron dengan Peran & Hak Akses (iterasi 33)
- `services/notification_scope.py`: filter kotak notifikasi = audiens (peran/all/peran acuan/recipient_user) ∧ relevansi
  (link layar tujuan harus boleh dibuka: modul ≥ Lihat). Admin melihat SEMUA notifikasi kecuali yang ditujukan langsung
  (`recipient_user`) ke orang lain — perbaikan dari temuan iterasi 33 (sebelumnya admin hanya audiens admin/all).
- `services/turn_notification_service.py`: penerima "Giliran Anda" digerbang izin dari matriks (peran bawaan + kustom),
  admin/manager dikecualikan kecuali rule menyebutnya. `GET /api/access/roles/{id}` → `turn_alerts`; editor peran
  menampilkan `role-editor-turn-alerts`.
- Setup ulang env baru (2026-06): clone repo pandeyoga/KNHOST; peran kustom `cr_staf_penagihan` + akun penagihan@
  dibuat ulang via API (finance, accounting=view, ar=manage). Pytest `tests/test_notifications_iter33.py` 10/10 lulus.


### 2026-06 — Editor peran: pratinjau notifikasi live, duplikat peran, pindah akun massal
- Backend: `POST /api/access/roles/preview` (turn_alerts & screens dari tingkat yang belum disimpan),
  `POST /api/access/roles/{id}/move-users` (pindah semua akun ke peran lain; admin ditolak). Audit `role_users_moved`.
- Frontend: `RoleNotifPreview` (diff vs tersimpan: "(baru)"/"(hilang)"), tombol `role-card-duplicate-<id>` → editor
  mode duplikat (acuan = peran sumber; hanya modul yang diubah dikirim agar izin parsial tetap setia), panel pindah akun di
  `RoleAccountsList` dengan `RoleDangerDialog` kind "move"; editor tetap terbuka & disegarkan setelah pindah.
- Testing agent iterasi 37: backend 11/11, frontend 100%.

## Design Studio — Nilai hanya saat ACC · HOLD · Label Proofing · Riwayat detail (2026-09-18, repo pandeyoga/KNHOST)
Problem statement: lanjutkan ke Desainer — (1) point hanya di akhir ketika ACC; (2) desain ACC bisa di-HOLD → tidak bisa masuk proofing R&D,
label jelas + filter; label proofing (on progress / finished) + info master produk; navigasi cepat tanggal; (3) history lebih detail.
Pilihan user: hapus semua penilaian kecuali dialog ACC; hold oleh admin/manager (izin `rnd.hold`, dapat diatur di matriks akses);
acuan tanggal ACC & update terakhir (bisa dipilih); riwayat lengkap (diff field, berkas, hold, nilai, proofing & master produk) + filter jenis; seed demo repo.
- Backend: `design_studio_service` — `transition` hanya menyimpan nilai pada `approve` (revisi mengabaikan score), `activate` ditolak saat hold;
  `set_hold`/`release` (field `on_hold`, `hold`, `hold_history`, event `hold`/`release_hold`); `attach_proofing` (batch md_samples/md_specs/products →
  `proofing{state none|in_progress|finished|master, label, detail, samples[], specs[], master_product}`); `log_external` (peristiwa lintas modul).
  `design_gallery_service` — `update_gallery` menulis event `updated` + `changes[{field,label,from,to}]`, `delete_file` → `file_deleted`, unggah colorway ikut timeline,
  filter `on_hold`. `rnd_sample_service` — `_assert_design_not_held` (proofing ditolak saat HOLD) + hook `proofing_requested/finished/decided`.
  `rnd_spec_service` — hook `spec_linked`, `master_product_created`, `master_product_released`. Router: `POST /design-gallery/{id}/lifecycle/hold|release-hold`
  (izin `rnd.hold`), `GET /design-gallery/{id}/history?kind=`; endpoint `/versions/{v}/score` DIHAPUS. `permissions_config`: `rnd.hold` admin+manager (merge otomatis saat restart).
- Frontend: `RndDesignsView` (KPI hold/proofing/master klik-saring, filter `rnd-filter-hold|proofing`, `DateQuickNav`, kartu ber-lencana hold/proofing/master/tanggal),
  `DesignDetailPage` (lencana + banner hold, tab Proofing R&D `ProofingPanel`, tab Riwayat `HistoryPanel` menggantikan TimelinePanel), `LifecycleActions`
  (hold/lepas hold via `canHold`, nilai hanya di dialog ACC, revisi tanpa nilai), `VersionsPanel` tanpa tombol nilai, `DesignBadges`, `SampleFormModal` menandai desain HOLD.
- Seed demo: `scripts/seed_design_hold_proofing_demo.py`. Testing agent iterasi 39: backend 14/14, frontend 100%.



## Sesi P17 (2026-10-03) — lanjutan handoff P16 (repo pandeyoga/KNHOST)
- Permintaan user: "lanjutkan development dari repo ini ... lanjutkan ada handoff dokumen dari sesi sebelumnya". Pilihan: arsip boleh dibuka baca saja; faktur tetap per pesanan; kerjakan 9 kasus planned.
- Selesai: arsip baca saja (API + pemilih entitas + pita), uji GRN-04/06, PROD-04/06, COMM-04/05, DESIGN-02/05, OPS-03; bug diperbaiki: koreksi akrual insentif, 3 balapan harga pelanggan, acuan QC per supplier.
- Backlog P0: GRN-06 UI penuh, PROD-06 UAT layar. P1: biaya kampanye → GL, impor produk/stok awal. P2: perbarui tes lama yang basi.
- P17b: integritas 248/0 (seed KANDA/SO-00001), tes basi diperbarui (f1a 16/16, e1e2 74/74), OCR SUNGGUHAN aktif (kunci OpenAI user, gpt-6-sol) & GRN-06 UI lulus end-to-end (iterasi 128). Sisa: balik residu uji KSC/GRN-00003; backlog P0 sekarang PROD-06 UAT layar.

## Backlog
- P2 (Akses): ganti `window.confirm` hapus/reset peran dengan modal in-app — SELESAI 2026-06 (`RoleDangerDialog`).
- P2 (Akses): daftar akun pemakai peran di editor — SELESAI 2026-06 (`RoleAccountsList`, `accounts[]` di GET /api/access/roles/{id}).
- P2 (Akses): router tuple peran hardcoded mengenal peran kustom — SELESAI 2026-06 (`role_registry.role_in` di design_requests, internal_requests, rnd, rnd_org, dan `dependencies.require_role`; frontend `roleIs` di rnd/design/designer views; deep-link `?view=` untuk peran `cr_*` menunggu registrasi peran kustom). Testing agent iterasi 35–36: backend 100%, frontend 100%.
- P2 (RND): revoke object URL cache galeri bukti (LRU) untuk sesi panjang; kolom galeri responsif di layar sempit.
- P1 (RND): sticky footer/ringkasan aksi di rincian sample; skeleton KPI saat memuat (kilat 0 ~200ms).
- P1 (RND): testid per-supplier di `SampleSendModal` (`sample-send-supplier-<id>`); galeri foto bukti per tab jenis.
- P1 (RND): perbaikan custom role & access — SELESAI 2026-06 (lihat bagian Peran & Hak Akses).
- P1: notifikasi WA otomatis kode pickup ke pelanggan saat pengiriman pickup dibuat (sekarang tombol WA manual).
- P1: kadaluarsa kode pickup / regenerasi kode oleh admin; batas percobaan kode salah → kunci sementara.
- P1: tampilkan badge moda & kode pickup di Perjalanan Pesanan (OrderJourneyPanel) dan Meja Admin Gudang.
- P2: biaya kirim ekspedisi → jurnal beban pengiriman (GL) / tagihan ke pelanggan.
- P2: jadwal kendaraan (kalender), riwayat perawatan, KM.
- P2: peta posisi live untuk semua pengiriman aktif di dasbor.

---
## SESI 2026-09-18 — Lanjutan repo github.com/makkansbdb/KN: Desainer & R&D

### Problem statement (asli)
Desainer: (a) Ringkasan diperbaiki — tiap ronde revisi tampil ke bawah (judul ronde → foto dikirim → komentar revisi → ronde berikutnya…); tab "Ronde & Nilai" dihapus, nilai di akhir saat ACC. (b) Tab Final: tanpa varian warna — hanya mockup + file desain asli yang bisa diunduh. (c) Galeri Desain → showcase desain ACC saja (tanpa tambah), detail: foto, file asli, mockup, info desain & pattern, produk pemakai + status R&D; filter diperbanyak. (d) Rapikan pop-up.
R&D: (e) Interface labdip/handfeel/proofing seperti desainer: detail ronde, komentar sampai ACC, history, tanggal terima. (f) Spesifikasi produk dikonsolidasikan ke tab sample (input saat create). (g) Rapikan pop-up. (h) Nama & warna supplier diisi saat sampling ACC (bukan awal), sinkron ke master terkait. (i) UX master data yang lahir dari R&D dibuat jelas (varian / induk).
Pilihan user: clone ulang repo; Desainer dulu lalu R&D; nilai tetap satu kali di dialog ACC (tanpa duplikasi); dialog "Pilih pemenang" wajib isi warna supplier + otomatis buat/tautkan master data dengan preview.

### Implementasi (2026-09-18)
- Backend: `design_studio_service.final_requirement` → mockup≥1 + source≥1 (colorway tidak wajib); kind `source` (file bebas ≤50MB) di `add_file` & `upload_kind_file`; `GET files/{fid}?download=1` → attachment.
- Backend R&D: `SampleInput.spec` (spec dibuat & ditautkan saat create sample); `SampleDecideBody` + `supplier_color_name/code`, `approve_spec`, `product_sku/name`; `decide_sample` sinkron warna supplier ke `color_library.supplier_variants` (+factory_name), ACC spesifikasi → produk lahir; `master_data_of()` di GET sample.
- Frontend Desainer: `RoundsTimeline.jsx` (Ringkasan linimasa), tab versions dihapus, `FinalPanel`/`FilesPanel` (mockup + source), dialog ACC tanpa jumlah warna, `DesignImage.jsx` (gambar via axios blob).
- Frontend Galeri: `DesignGalleryView.jsx` showcase + 7 filter, `DesignShowcaseModal.jsx`.
- Frontend R&D: `SampleRoundList.jsx` linimasa per supplier×jenis (dikirim/tenggat/diterima, bukti, catatan, keputusan penilai), `DecideModal.jsx` 3 langkah + preview master data, `SampleMasterDataPanel.jsx`, `SampleFormModal.jsx` bagian 3 spesifikasi, tab hub "Spesifikasi Produk" dihapus.
- Env: `CORS_ORIGINS` di backend/.env wajib daftar origin (bukan '*'); frontend bundle statis → `bash scripts/rebuild_frontend.sh`.
- Uji: testing agent iterasi 40 — backend 8/8, frontend semua alur lolos.

### Backlog / P1–P2
- P1: audit pop-up lain di R&D (RoundActionModal, SampleSendModal, SampleFinishModal, IssueMaterialModal) untuk konsistensi font/spacing.
- P1: seed sample "assessed" ber-warna target agar field warna supplier langsung terlihat di demo.
- P2: hapus kode/komponen colorway yang tak lagi dipakai (ColorwaysPanel, VersionsPanel) bila sudah dipastikan tak dirujuk.
- P2: GET /api/color-library/{id} (saat ini hanya list) untuk layar detail warna versi supplier.

### 2026-09-19 — Pop-up R&D seragam + Riwayat warna supplier
- Refactor 5 pop-up R&D ke shell `FormModal` + `RndField` (Field/Hint/Footer): font 13.5px judul / 11px subjudul / 10.5px label / 11.5px isi, jarak `gap-3` seragam.
- Pustaka Warna: badge "N versi supplier" pada kartu → `SupplierColorVariantsModal` (supplier, nama & kode warna supplier, sampel asal dengan deep-link, tanggal ACC).

### 2026-09-19b — Pustaka Warna: sub-tab Warna Internal / Warna Supplier + keterkaitan
- Sub-tab terpisah; tab Warna Supplier = tabel versi warna per supplier (label supplier jelas), cari nama/kode warna supplier, filter supplier & "sudah/belum jadi produk".
- Modal keterkaitan 3 kolom: Warna internal ↔ Versi supplier ↔ Master produk (+ daftar sample R&D) — backend `color_links` & `list_supplier_variants` di color_service.

### 2026-09-19c — Spesifikasi WAJIB menyatu (1 sample = 1 spesifikasi)
- Koreksi user: tab Spesifikasi dihapus tetapi logikanya wajib & menyatu di form Labdip/Handfeel/Proofing (bukan opsional).
- Form 4 langkah (Acuan → Spesifikasi WAJIB adaptif per jenis → Brief → Kapan); server menolak sample tanpa spesifikasi; validasi per jenis.
- Panel Spesifikasi di rincian (ringkasan, ubah sebelum ACC, "Lengkapi spesifikasi" untuk data lama); ringkas spesifikasi di kartu.
- 2026-09-19d: dropdown "Acuan spesifikasi" dihapus (membingungkan); form 3 langkah; pesanan pelanggan dipindah ke langkah Brief. Anti-duplikasi spesifikasi lewat multi-jenis dalam satu permintaan / "Tambah jenis".

### 2026-09-19e — Dua warna (internal + supplier) visible di semua menu
- Denormalisasi warna internal, versi warna supplier (dilabeli supplier), dan supplier pemenang R&D ke master produk; disinkronkan saat ACC sampling / ACC spesifikasi (+ backfill).
- `ProductColorChip` dipakai di pemilih produk, PO (opsi & baris item, difilter supplier PO), RFQ, katalog (header & kartu varian), detail produk, panel master data R&D.

### 2026-09-19f — Special Order Fase 1
- Menu "Pesanan Khusus" di PENJUALAN (bawah Kasir & Portal). Intake terstruktur 4 langkah (pelanggan & tipe permintaan printing/labdip/handfeel; referensi; spesifikasi ringkas/lengkap; jumlah-harga-tenggat) + unggah referensi pelanggan.
- Routing otomatis saat disetujui: printing → Permintaan Desain (+referensi); labdip/handfeel → Spesifikasi + Permintaan Sample R&D (tertaut special_order_id, exclusive_customer_id). Rincian OD: lini masa fase + rantai dokumen (OD ↔ Desain ↔ Sample ↔ SKU ↔ PR/PO ↔ SO).
- Backlog Fase 2: ACC pelanggan atas sample, harga final (kontrak + margin), eksklusivitas SKU ditegakkan di Kasir/SO, PR/PO ke supplier pemenang, hapus "Buat SKU" ad hoc, proofing otomatis saat desain ACC, kartu ringkas di Meja Admin Sales.

### 2026-09-19g — Special Order Fase 2 (ACC pelanggan · harga final · eksklusivitas · proofing otomatis)
- Backend `services/special_order_phase2.py`: `customer_decide` (acc/revisi/tolak + catatan, tanggal, kontak; revisi → sample R&D baru otomatis dgn spesifikasi diwarisi, OD kembali Sampling; tolak → cancelled), bukti (`customer-decision/evidence`), `pricing_preview` (kontrak supplier pemenang + margin default 30% dari `system_settings{scope:special_order}.default_margin_pct`), `lock_price` (sales/sales_admin/manager/admin, wajib ACC pelanggan; harga & eksklusivitas ditulis ke master produk), `unlock_price` (admin + alasan, ditolak bila PR/SO sudah lahir), `assert_customer_allowed` (SO/POS ke pelanggan lain/walk-in → 400), `on_design_approved` (desain OD printing ACC → sample proofing + notifikasi MD).
- `special_order_routing`: fase baru `pricing`; `_phase` memakai sample terakhir (revisi) & kunci harga; `chain_of` → `review` + `pricing`. `approve_special_order` tak lagi membuat SKU ad hoc untuk OD terstruktur; PR/konversi SO OD terstruktur ditolak sebelum harga dikunci; PR memakai product_id & harga kontrak pemenang.
- `rnd_spec_service`: `exclusive_customer_id` diwariskan ke produk; `decide_sample` menstempel eksklusif pelanggan ke produk.
- Frontend: `SpecialOrderCustomerApprovalPanel.jsx`, `SpecialOrderPricingPanel.jsx` (di rincian OD setelah disetujui), badge "Eksklusif: <pelanggan>" di POS (`PosProductCard`), katalog (`VariantCard`), rantai OD.
- Testing agent iterasi 46: backend 9/9, frontend lolos. Catatan: relock setelah unlock membaca ulang harga kontrak sample pemenang terbaru (disengaja).

### Backlog Fase 3 OD
- P0: PR/PO otomatis ke supplier pemenang (pakai kontrak) + tracking produksi → konversi SO dengan harga final (tombol sudah digerbang kunci harga).
- P1: kartu ringkas OD di Meja Admin Sales; notifikasi WA ke pelanggan saat sample siap ACC.
- P1: routing OD printing mengisi Kategori Pattern/Design otomatis (sekarang desainer harus melengkapi via "Ubah" sebelum "Buat & buka desain").
- P2: pengaturan default margin OD di Pusat Pengaturan (sekarang hanya via DB `system_settings`).

### 2026-09-19h — Special Order Fase 3 (PR/PO otomatis · SO harga final · kategori desain otomatis)
- `lock_price` {margin_pct, warehouse_id, auto_po} → `auto_procure`: rilis SKU eksklusif ke produksi → PR (source special_order, "Sistem (OD)") → approve → PO ke supplier pemenang (harga kontrak pemenang; kontrak diikat ke product_id di `decide_sample`; jaminan harga di `auto_procure`), tenggat = expected_delivery OD, gudang default aktif pertama entitas → OD in_production. `POST /special-orders/{id}/procure` untuk ulang. PO completed (`recompute_po_status`) → OD ready. Supplier grup ditolak oleh aturan antar-entitas (pesan jelas).
- `convert-to-so` (in_production/ready + harga terkunci): SO memakai `pricing.product_id` & harga final terkunci (`special_order_price`, `cost_price`, `margin_pct` di baris SO) via `source_special_order_id` di `create_order`.
- OD printing: `pattern_category_code`/`design_category_code` di form intake (opsional) + fallback kategori pertama aktif → DSR siap "Buat & buka desain".
- `POST /special-orders/{id}/submit` (draft → pending_approval; OD dengan submit_for_approval selalu masuk persetujuan tanpa ambang). UI: tombol "Ajukan persetujuan", pilih gudang & toggle PR/PO otomatis di panel harga, chip PO, "Buat PR/PO sekarang".
- Testing agent iterasi 47 (17/18 → bug kontrak diperbaiki) & 48 (retest).

### 2026-09-19i — Special Order Fase 4 (pengiriman otomatis · kartu OD di Meja Admin Sales)
- lock-price (auto_po) → SO OD lahir otomatis (harga final). PO OD diterima gudang (`recompute_po_status` completed; atau setelah QC accept di `qc_service`) → `on_goods_received`: stok direservasi ke SO (backorder), SO confirmed otomatis, tugas Surat Jalan (outbound) lahir. `dispatch_task` → SJ terbit → OD shipped (`on_shipment_dispatched`); SO mark-delivered / logistik delivered → OD done (`on_delivered`). Kegagalan (mis. karantina QC) tercatat di `shipping_error`; tombol/endpoint `prepare-shipment` untuk mengulang. Panel `SpecialOrderShippingPanel` di rincian OD; `chain_of` → outbound_tasks & shipments.
- Meja Admin Sales: antrean `od_acc_pelanggan`, `od_kunci_harga`, `od_siap_kirim` (`work_desk_service` + `special_order_phase2.desk_rows`); ROW_TARGET special_order → deep-link `SpecialOrders` (`focusDoc`) langsung membuka rincian.
- Testing agent iterasi 49: backend 14/14, frontend lolos.
### Backlog OD
- P1: notifikasi WA ke pelanggan (sample siap ACC, barang siap kirim). P2: pengaturan margin OD di Pusat Pengaturan. P2: pengiriman fisik (pick/dispatch) tetap manual gudang — by design.

### 2026-09-19j — Modul Marketing & Sosial Media (baru)
- Backend `services/marketing_service.py` + `routers/marketing.py`: kampanye (`mkt_campaigns`), post (`mkt_posts`) dgn alur idea→draft→review→approved(manager/admin)→scheduled(publish_at+PIC)→published(+url), lampiran (storage), performa manual (metrics + history), bahan konten (desain galeri ACC/produk/OD), analitik per bulan/platform/kampanye, job scheduler `content_reminder` (15 mnt) → notifikasi PIC in-app/WA. Resource izin `marketing` (admin/manager penuh; designer/sales/sales_admin view/create/update). Modul akses "Marketing & Sosial Media".
- Frontend `features/marketing/`: ContentCalendar (bulan/daftar, filter, klik sel → buat), PostFormModal, PostDetailModal (aksi alur, lampiran, performa, riwayat), Campaigns, MarketingAnalytics. Menu standalone "Marketing & Sosmed" (hub marketing-hub: Kalender Konten · Kampanye · Performa).
- Testing agent iterasi 50: backend 30/30, frontend lolos. Tanpa AI & tanpa API sosmed (sesuai pilihan user).
### Backlog Marketing
- P1: template konten & duplikasi post; tampilan minggu; ekspor kalender PDF. P2: posting otomatis via Meta/TikTok API; AI caption (jika diinginkan); UTM link builder & pelacakan prospek ke CRM.

### 2026-09-19k — Marketing lanjutan: Akun Sosmed per PT · Dashboard · Ekspor PDF · Multi-entitas
- `services/marketing_ext.py`: master `mkt_accounts` (per badan usaha, banyak akun; validasi dup & kepemilikan PT/platform saat dipakai di post → snapshot `post.accounts`), `dashboard()` (KPI bulan ini vs lalu, tren 6 bulan, per platform/akun/PT, top, 7 hari ke depan, terlambat, tingkat tepat waktu ≤60 mnt), `calendar_pdf_html()` → weasyprint (A4 landscape, kop PT/Grup, grid, daftar rinci caption ≤120, ringkasan kampanye).
- Multi-entitas: posts/accounts/dashboard/PDF menerima `entity_id=all|ent_x` (resolve_list_scope); tiap respons post membawa `entity_name`; buat konten/akun selalu ke PT aktif (ditampilkan di form). UI mengikuti pemilih PT di header: badge PT di kalender/daftar/rincian saat "Semua".
- Tab hub: Kalender Konten (tombol Ekspor PDF) · Dashboard & Performa · Kampanye · Akun Sosmed. Testing agent iterasi 51 (16/16 + UI) & 52 (retest badge PT lolos).

### 2026-09-21 — Perapian UI Pesanan Khusus
- `SpecialOrderInfoPanels.jsx` ditulis ulang: panel Rincian item custom / Info pelanggan / Riwayat status memakai gaya seragam panel Fase 2–4 (section-card !p-3, kicker label, sel grid), label Bahasa Indonesia, tidak ada konten menempel tepi kartu; grid `items-start`. Popup Tolak → FormModal standar; label "Reject" → "Tolak"; kolom tabel "Expected Del." → "Perkiraan kirim". Testing agent iterasi 53: lolos (tanpa overflow).

---

## Sesi 2026-09-21 — Perbaikan fokus input form R&D (repo github.com/pandeyoga/KNHOST)

### Problem statement (asli)
"saya ingin anda lanjutkan development dari repo ini https://github.com/pandeyoga/KNHOST — perbaiki beberapa form di menu RND,
ketika saya buat labdip, proofing, dan handfeel ketika saya ingin isi form itu hanya setiap satu charakter saya harus klik kolom
form kembali sepertinya ada bug front end." Pilihan user: clone branch main; periksa & perbaiki semua form RND dengan pola sama.

### Akar masalah
`features/rnd/SampleSpecFields.jsx` mendefinisikan komponen pembungkus `L` DI DALAM fungsi render → tiap keystroke induk re-render,
referensi komponen baru → React unmount/remount `<input>` → fokus hilang. Pola sama di `features/rnd/design/FinalPanel.jsx` (`Row`).

### Yang dikerjakan
- `L` (SampleSpecFields) dan `Row` (FinalPanel) dipindah ke module scope. Berdampak ke form Labdip/Handfeel/Proofing
  (`sample-form-modal` dari `rnd-samples` & galeri `rnd-labdip|handfeel|proofing`) serta `SampleSpecPanel`.
- Audit pola yang sama di seluruh `frontend/src`: sisa kasus (LocationFields `L`, DocRefsPanel/ReallocateRollsModal `Row`,
  CoreWidgets `FavStar`, PdfEditorTabs `Diff`, DomainRegistryParts) TIDAK membungkus input → tidak menimbulkan bug fokus; dibiarkan.
- Lingkungan: backend/.env CORS_ORIGINS eksplisit + SESSION_COOKIE_SECURE; seed_realistic dijalankan; bundle frontend di-rebuild.
- Uji: testing agent iteration_54 — 21/21 field mempertahankan fokus saat mengetik kontinu di semua titik masuk.

### Catatan
- `sample-spec-sku` sengaja meng-uppercase ketikan (perilaku lama, bukan bug).
- Frontend statis: setelah ubah src → `setsid nohup bash /app/scripts/rebuild_frontend.sh > /app/.rebuild.out 2>&1 &` (±8 mnt).

---
## Sesi 2026-09-21 — Verifikasi & perbaikan audit kode (PDF Bagian I & II, 92 temuan)
**Problem statement:** clone repo abagayafaja/KN, verifikasi 92 temuan audit (KN-A01..A13, B01..B35, C01..C10, D01..D26), laporkan validitas, perbaiki. Pilihan user: semua 92 temuan; laporan ringkas di chat; indeks unik dibuat (fail-safe log).

**Hasil verifikasi:** 84 VALID (diperbaiki 71), 5 VALID-DITUNDA (butuh desain UoM/arsitektur), 3 PARSIAL/keputusan desain (B26, C08 sebagian, D08), 2 laporan observasi tanpa perbaikan kode (C09 to_list, C10 except-pass), 0 TIDAK VALID.

**Perbaikan utama:**
- `entity_scope.guard_doc()` — penjaga entitas satu baris untuk jalur tulis: gl void, cash void, vendor_bills (submit/approve/reject/pay/cancel), cycle_count semua aksi, purchase_returns seluruh siklus + list scope, sample_orders (ketat), ar_receipts, hr_payroll, interco (`_guard_party`), fixed_assets, landed_cost, bank PATCH, cash_advances (ketat).
- Mesin status: escalate inbound/outbound berprasyarat status (C01/C02), resolve wajib `escalated`; PO approve CAS + larang penyetuju sama dua tingkat (B04/D05); PO terminal tidak dihidupkan lagi saat penerimaan (D01); `_post_bill` prasyarat status (B05); special order CAS (B10); SO approve blok bila ada approval ditolak (D02); kontrabon settle_bills cek status + `$expr` (D03).
- Atomik: claim saga pada kontrabon pay (B01), settle_return (B02), realize PR→PO (B03), store credit redeem (B06), deposit CAS (B08), allocations `$push` (B07).
- Indeks unik nomor dokumen 22 kolom + `(source_type,source_id)` jurnal aktif (A12/B09); 13 generator "max+1" → `next_doc_number(scheme="shared")` (A12/D15).
- Konstanta bersama: `OPEN_PO_STATUSES`, `PHYSICAL_ROLL_STATUSES` (A11/C05/D10), `GREEN_OUT` RFID (C03), `role_rank` → registry (C04), `services/tolerances.py` (A13/B28).
- Nilai: HPP GR pakai harga neto (A09), short-pick pertahankan diskon header (A10), nota kredit harga neto (B23), retur beli rata-rata berbobot (B24), PPN retur beli dicatat & dibalik, `returned_amount` termasuk PPN (B20/B21), on_order_qty (B14), goods_back rebuild gudang asal (B13), landed cost ke roll pecahan (B17), RFID tag ikut transfer (B19), void kuitansi netralkan baris realokasi (B25), opname tolak bila stok bergerak (B11), PO tolak produk kembar (B15).
- Meja peran & status: driver queue filter delivered (C08), designer/warehouse desk status nyata (D06/D07), so_status backorder fulfilled (D14), peringatan reservasi waiting_stock (D13).
- Frontend: faktor UoM dari master server + blokir satuan tak dikenal (C06), peringatan minimum potong di keranjang (C07), keranjang direset saat ganti PT (D20), jurnal tolak baris debit&kredit (D22), RollPicker reload saat ganti gudang (D23).
- Uji: `tests/test_kn_audit_2026_09_21.py` (+ `_extended.py` dari testing agent) masuk `gate.sh` default; uji lama /sample-requests dinonaktifkan (A08).

**Ditunda (backlog P1):** B12 (opname hanya potong bucket available), B16 (rebuild_balance abaikan unit roll), B18 (length_initial agregat), B22/B27 (konversi satuan retur & create_roll), B26 (WAC abaikan roll berbiaya nol — keputusan desain), D04, D08, D11, D12, D16, D17, D18, D19, D21, D24, D25, D26, C09, C10.
**Gate merah pre-existing (bukan dari sesi ini):** verify_entity_scoping (categories.py design_gallery), audit_entity_isolation (data_hygiene_log), POC E-3 (POST /customers wajib PIC).

### Sesi 2026-09-21 (lanjutan) — sisa audit
- **Konversi satuan (B12/B16/B22/B27):** `roll_service.to_base_qty()`; `create_inbound_roll` menghormati `unit` (yard→meter); `rebuild_balance` mengonversi roll ber-unit lain; opname susut memotong bucket hold/quarantine/blocked/damaged/wip lalu reserved/committed dengan log (bukan diam); retur jual dinormalkan ke satuan dasar (`_normalize_return_items_to_base`), batas retur & harga CN per satuan dasar (`base_quantity`). B18 dicek ulang: jalur scan-label & GR sudah konsisten satuan dasar (tidak perlu perubahan).
- **Frontend D17–D19, D21, D24–D26:** `useEffectivePrices` kanal galat + retry, checkout diblokir bila harga kontrak gagal; kartu omzet dari agregat server `stats/summary.revenue` (grand_total); `computeOrderPreview(items, disc, settings, {cfgSection, taxOverride})` satu cermin server — PO buat/ubah menghormati `purchasing.allow_*_discount` & tax_mode; `kgPerBaseUnit` cabang basis berat; header `X-Total-Count/X-Truncated` + banner terpotong di Stok, join produk tak lagi dipangkas 1.000; antrean luring menyimpan `entity_id` saat direkam & memakainya saat sinkron.
- **Gate lama:** categories.py motif ter-scope; `data_hygiene_log` SCOPED (+inherit global); POC E-3 pakai `assigned_sales_id`; entri REVIEWED /sample-requests basi dihapus dari verify_atomic_claim.
- **C10:** 74 titik `except: pass` → `logger.warning("[fungsi] efek samping gagal diabaikan: %s")` di 43 berkas.
- **Temuan baru (pre-existing, belum diperbaiki):** `bash scripts/gate.sh --ci` masih menunjukkan ±28 gate/POC merah lama yang tidak terkait sesi ini (POC E-5/E-7/E-8/F-6/L/U/P/D/S/I drift, guard uom_vocab 4 layar opsi satuan hardcode, atomic_claim 16 endpoint belum ditinjau, auth_coverage residu gate, i18n 37 label, escape_layers, role_label, warehouse_scope self-test, validate_compliance 3 item, approval_queues 2 pintu + turn_marks). Butuh sesi khusus per gate.

### Sesi 2026-09-21 (sesi 3) — D11, D16, gate merah
- **D11 ATP tunggal:** `services/atp_policy.py` (ATP = available + incoming≤14 hari − backorder aktif; ETA kosong = dalam horizon) dipakai `roll_service.rebuild_balance` (+`pending_demand_qty`), `fulfillment_service` supply (+`pending_demand`), `stock_bucket_service.atp_detail`.
- **D16 3-way tunggal:** `services/three_way_policy.py` (qty% & harga% dari `purchasing.bill_*_tolerance_percent`, rupiah dari `contra_bon.value_tolerance_rupiah`) dipakai vendor bill (`evaluate_match` + `value_tol`) & kontrabon (`policy`, `evaluate_bill_exceptions` harga memakai price_tol). `contra_bon.qty_tolerance_percent` ditandai tidak dipakai.
- **Gate merah 32 → 18:** HIJAU: uom_vocab (+self-test; 4 layar pemilih satuan dari master), atomic_claim (+self-test; 16 endpoint ditinjau — CAS/$inc baru di inbound_scan_label, special_orders approve/lock_price, rnd decide_sample), approval_queues, validate_compliance (prefix router), escape_layers, role_label, warehouse_scope self-test, modal_dismiss, create_modal (+self-test; bendera busy bukan form), POC F-6, POC I.
- **Masih merah (pre-existing, butuh sesi khusus):** 13 POC drift (E-5, E-7, E-8 G1/G2-G3, Cek Kenyataan Peran, F-6.7, Sesi 2026-06, L, U, P-0, P, D, S), audit_sales_roles_ux (panel 403 /md/desk, /warehouse-admin/desk, budget-keys, makloon claims), INV-GATE-01 anti-residu & auth_coverage (POC meninggalkan audit_logs/notifications/PR), ux_audit --strict (5 berkas: ProductRelations, DeliveryTable, Campaigns, MarketingAnalytics, +1), audit_i18n_id (37 label di 19 berkas).

### Sesi 2026-09-22 — restore repo & lanjutan seed/POC E-9
- **Restore lingkungan:** clone `github.com/makkajabsh/KN` → /app; pip/yarn install; `backend/.env` diisi `CORS_ORIGINS` eksplisit + `SESSION_COOKIE_SECURE` (T-02); backend restart (bootstrap fondasi); `seed_realistic.py` dijalankan 2× (idempoten, nol `[warn]`); frontend dibangun ulang (`scripts/rebuild_frontend.sh`, bundle statis).
- **Dua langkah seed yang dulu dilewati** kini terbukti lolos pada seed pertama & kedua: settlement antar-PT memakai `method: "transfer"` (F-08 netting butuh piutang balik) — label ringkasan seed diperbaiki; desain R&D `submit_design` → `approve_design` (F-6.7) termasuk cabang "pakai ulang".
- **POC E-9 (`backend/test_core_rantai_retur_poc.py`):** 44/44 PASS; cleanup kini juga menghapus `turn_marks` (doc_id POC) & `roll_cost_history` (roll POC) → `ukur_residu_poc.py --only e-9` = nol residu.
- **Smoke test agent:** login, /api/, interco settlements (transfer·posted), design-gallery (approved), interco transactions, login UI → semua hijau (`test_reports/iteration_smoke_restore.json`).
- **Berikutnya (dari backlog):** 13 POC drift merah pre-existing, INV-GATE-01/auth_coverage residu POC lain, audit_sales_roles_ux, ux_audit --strict, audit_i18n_id.


### Sesi 2026-09-24 — residu POC NOL + Marketing P1 (template · duplikasi · tampilan minggu)
**Problem statement:** lanjutkan repo github.com/pandeyoga/KNHOST dari titik henti `prune_orphan_turn_marks()`. Pilihan user: (a) selesaikan helper, residu POC G7, `gate.sh --full` hijau; (b) lanjut fitur berikutnya dari PRD.
- **Lingkungan:** clone → /app (.env dipertahankan; `backend/.env` + CORS_ORIGINS eksplisit & SESSION_COOKIE_SECURE). pip: `emergentintegrations` dipasang terpisah (konflik litellm di requirements). `seed_realistic.py` + `seed_e9_chain_demo.py`.
- **Residu POC → nol di semua 38 POC gate** (`scripts/ukur_residu_poc.py`): `poc_stock_guard.py` + `snapshot_new_ids()/purge_new_ids()/with_journal_cleanup()` (sidik `_id` audit_logs/notifications SEBELUM login, sapu sesudah). Dipasang di G-0, G-1, G-2, G-3, G-4, G-7, G-8, G-9, F, F-1, F US3/11/12, D (blok `__main__`) + fixture G-6/G-6b (juga `roll_cost_history`). `prune_orphan_turn_marks` sudah terpasang di 7 POC.
- **Gate:** `bash scripts/gate.sh --full` → **HIJAU** (129 PASS, 0 FAIL). Default gate hijau setelah fitur marketing.
- **Marketing P1:** `POST /api/marketing/posts/{pid}/duplicate {publish_at}` (salinan status Ide, `duplicated_from`, kampanye/akun hanya bila entitas sama); koleksi `mkt_templates` per badan usaha (`GET/POST /api/marketing/templates`, `POST …/{tid}/use` used_count, `DELETE …/{tid}` pembuat/admin/manager). FE: mode **Minggu** di Kalender Konten (`WeekGrid.jsx`), `TemplatePicker.jsx` di form konten baru, `DuplicatePostModal.jsx` + tombol "Simpan sebagai template" di rincian.
- **Uji:** testing agent iteration_59 — backend 15/15 (`backend/tests/test_iter58_marketing_templates_duplicate.py`), frontend 100%.
- **Catatan build:** `scripts/rebuild_frontend.sh` (nice+ionice) mati diam-diam di pod ini; build langsung berhasil ±40 dtk: `cd /app/frontend && GENERATE_SOURCEMAP=false CI=false DISABLE_ESLINT_PLUGIN=true yarn build`.
- **Backlog:** Marketing P2 (posting otomatis Meta/TikTok, AI caption, UTM builder → CRM); OD P1 notifikasi WA pelanggan; EPIC 7 multi-currency (ditunda).

### Sesi 2026-09-24 (lanjutan) — T-04 N+1 (2 PERBAIKI) + geser jadwal konten
- **Impor produk** (`routers/admin.py import_products`): validasi semua baris dulu, lalu satu `find({sku: {$in}})` → peta; SKU kembar dalam file diperlakukan created→updated (dry-run juga). Dry-run 2000 baris < 1 dtk.
- **Laporan stok mati** (`routers/reporting.py stock_aging`): mutasi terakhir per (produk,gudang) lewat satu agregasi `$group $max timestamp`; produk hanya yang ada di saldo. Output lama vs baru IDENTIK (threshold 0/30 × semua/ent_ksc/ent_kanda). Urutan kini benar untuk days=0.
- `memory/TRIASE_NPLUS1_2026-09.md` dibuat ulang: PERBAIKI = 0 (232 TIDAK TAHU tersisa).
- **Geser jadwal konten:** `POST /api/marketing/posts/{pid}/reschedule` (format YYYY-MM-DDTHH:MM, riwayat "jadwal digeser", audit `mkt_post_reschedule`, published ditolak); seret-lepas kartu di tampilan Minggu (`WeekGrid.jsx`), jam tayang tetap.
- Uji: testing agent iteration_60 — backend 15/15, frontend 100%; gate default hijau.

### Sesi 2026-09-24 (lanjutan 2) — audit Pustaka Warna
- Alur nyata terbukti: labdip KN-BLU-01 → ACC Palembang Silk House "Navy 07/NV-07" → produk KTN-NVY-PSH-01 (color_ref + supplier_colors + rnd_supplier) → tab Warna Supplier & modal keterkaitan (data demo kini ada).
- Diperbaiki: PATCH nama kosong → 400 (dulu menghapus nama); status selain active/inactive → 400 (dulu warna "hilang" dari semua filter); tombol UI mengikuti izin `color.*` (MD create+update kini terlihat); `list_supplier_variants` batch `_products_of_colors` (tanpa N+1).
- Uji: testing agent iteration_61 — backend 53/53, frontend 100%. Uji lama `tests/test_color_links.py` & `test_iter44_two_color.py` memakai id basi DB lama (bukan regresi).

### Sesi 2026-09-24 (lanjutan 3) — tab "Warna Pelanggan" di Pustaka Warna
- Permintaan user: tab warna customer terpisah; warna produk eksklusif pelanggan dipisah dari pustaka internal. Label UI "Warna Pelanggan" (gate i18n: customer → Pelanggan).
- Aturan pemisahan (turunan, tanpa mutasi data): warna = warna pelanggan bila `color_library.exclusive_customer_id` terisi (milik pelanggan, diatur di form Tambah/Edit) ATAU hanya dipakai produk ber-`exclusive_customer_id` (tak ada produk umum; pemakaian lewat `color_ref.id` atau `color_code`). Warna yang juga dipakai produk umum tetap di Internal + tampil di grup pelanggan berlabel "juga dipakai N produk umum".
- Backend: `color_service.color_usage/is_customer_color/list_customer_colors`, `GET /api/color-library?scope=internal|customer` (+ `is_customer_color` per baris), `GET /api/color-library/customer-colors` (per pelanggan yang terlihat di badan usaha aktif). FE: `CustomerColorsTab.jsx`, KPI Warna Pelanggan, field "Milik pelanggan (eksklusif)" di form, lencana di PantoneFinder.
- Data demo: `scripts/seed_customer_colors_demo.py` (idempoten) — KN-SJT-01 milik Toko Kain Sejahtera; produk eksklusif Butik Bali Indah SGK-BLI-TSK-01 (KN-GRN-03) & SGK-BLI-UNG-01 (KN-PUR-01) lewat alur labdip → ACC.
- Uji: iteration_62 backend 11/11, frontend 100%.

## Warna Pelanggan lanjutan (2026-09-24, repo mkaksjbd/KN)
Problem: lanjutkan 4 fitur — Warna di Profil Pelanggan · Kunci Warna Eksklusif (diblokir, butuh persetujuan manajer) ·
Kartu Warna PDF (swatch, kode, versi supplier + logo/nama badan usaha) · Penanda Warna Otomatis saat labdip ACC.
- Backend: `services/color_lock_service.py` (assert_can_use, permintaan izin di `color_library.use_requests[]`, approve/reject/revoke,
  notifikasi manajer & pemohon, auto_mark_owner), `services/color_card_pdf.py` (WeasyPrint + branding badan usaha aktif),
  endpoint baru di `routers/color_library.py`; kunci dipasang di `product_variant_service.save_product` (semua jalur produk),
  `rnd_spec_service` (buat/ubah spesifikasi) & `rnd_sample_service.decide_sample`. Izin baru `color.approve` (admin+manager).
- Penanda otomatis: sample ber-`exclusive_customer_id` diputus → warna sistem KN belum bertuan & tak dipakai produk umum/pelanggan lain
  menjadi milik pelanggan (`exclusive_source.kind=auto`). Ini juga menutup catatan lama "Pantone ikut pindah" — hanya warna KN yang ditandai.
- Frontend: CustomerColorsTab (lencana Terkunci/Otomatis, tombol Kartu Warna PDF, minta izin pakai, daftar izin), ColorUseRequestModal,
  ColorUseRequestsPanel, CRM `CustomerColorsSection` di Customer 360.
- Seed: `scripts/seed_customer_colors_demo.py` kini + warna baru KN-BLI-EMS-01 Emas Pura (SGK-BLI-EMS-01) → ditandai otomatis.
- Gate: pintu approve/reject izin warna didaftarkan di DOOR_EXEMPT (antrean = panel Warna Pelanggan + notifikasi), belum masuk KPI Pusat Persetujuan.
- Uji: backend 18/18, frontend ~90% (role sales tidak punya menu Pustaka Warna — desain peran lama).

### Backlog
- P1: antrean izin warna masuk Pusat Persetujuan/KPI beranda (butuh koleksi sendiri ber-entity_id).
- P1: tombol "Minta izin" langsung dari pesan tolak di form Produk/Spesifikasi.
- P2: akses sales ke tab Warna Pelanggan (read + minta izin) bila diinginkan.

## GRN + OCR Surat Jalan — Fase 0 selesai (2026-09-24)
Spesifikasi: `memory/grn_ocr/Prompt_Implementasi_GRN_OCR_SJ.md` (+ `prompt_sj_v2.txt`, `schema_sj_v2.json`). Aturan: satu fase per sesi.
Keputusan user: Fase 0 dulu · kunci OpenAI menyusul (Fase 4) · keputusan klien §7 = bawaan dokumen · foto contoh SJ diunggah saat Fase 4.
- 0.1 `advance` menolak tugas inbound (409 USE_RECEIVING_FLOW); tombol "Lanjutkan Tahap" nonaktif untuk inbound.
- 0.2 `receiving.*` di scan label dibaca lewat `value_of`.
- 0.3 Kunci baru `receiving.line_qty_tolerance_pct` (2%) → complete() + uom-options → GRCatchWeightModal.
- 0.4 Grade SSOT (`domain_registry.require_grade`): A+→A, C→BS, tak dikenal 400; semua dropdown grade via useDomainEnums.
- 0.5 Mobile: qty kosong, Terima juga untuk waiting_goods.
- 0.6 Override over-receipt/selisih konversi hanya pemegang `wms.approve`, alasan tercatat; UI askReason.
- 0.7 lookup kode supplier hanya aktif; indeks unik `uq_supplier_sku`; skrip `scripts/check_supplier_item_duplicates.py`.
- 0.8 KN-B15 juga di PR→PO & amandemen (`services/po_line_guard.py`).
- 0.9 Kamera mode manual mengisi Roll ID.
- Uji: `backend/tests/test_grn_phase0.py` 14/14; gate penuh HIJAU.
## GRN Fase 1 selesai (refactor tanpa perubahan perilaku)
- `services/inbound_complete_service.complete_task(task_id, payload, actor, *, ctx, via_grn)`; router `complete` = pembungkus tipis.
- `services/receiving_roll_service.py`: `create_label_roll` (label), `create_counted_roll` (hitung manual), + (Fase 2) `resolve_label_input`, `undo_receiving_roll`.
- Uji: `tests/test_inbound_complete_characterization.py` (golden dari kode LAMA) + phase0 + wms_advance → 16/16 (iteration_65).

## GRN Fase 2 selesai — backend GRN tanpa OCR (2026-06)
- Koleksi `goods_receipts` (nomor `{KODE}/GRN-NNNNN`, `uq_number`, `uq_active_key` unik parsial, indeks §4.3), `supplier_dn_profiles`; keduanya di `SCOPED_COLLECTIONS`; doc type `goods_receipt` di doc_refs.
- Modul izin `goods_receipt` (view/create/count/review/close/approve) sesuai §4.7; grup `warehouse_ops`.
- Konfigurasi baru: `receiving.mode` (legacy|grn, bawaan legacy), `receiving.blind_count` (bawaan true).
- Router `routers/goods_receipts.py` → layanan `services/goods_receipt_service.py` (buat, berkas, kepala SJ, baris, targets, start-count, scan-label/roll hitung/undo) + `services/goods_receipt_close_service.py` (rekonsiliasi §4.4, resolve, close §4.5, `ensure_remainder_task`, reject, cancel).
- Posting HANYA lewat `complete_task(..., via_grn=grn)` (boleh status `receiving`) / `receive_step` (makloon).
- Mode `grn`: scan-receive/scan-label/complete lama → 409 `GRN_MODE` (tugas setengah jalan ditandai `legacy_in_flight`); tugas milik GRN aktif → 409 `GRN_MANAGED`.
- Uji: `tests/test_grn_phase2.py` 6/6 (golden setara jalur lama, hitung buta, DN_DUPLICATE, pemblokir+resolve, tepat satu tugas sisa, batal bersih, mode grn, isolasi entitas). Total GRN 22/22.
- Temuan: `_create_inbound_tasks_for_po` menganggap tugas `qc_pending` "masih ada" (dan menimpa expected_qty-nya) → tidak dipakai untuk sisa; diganti `ensure_remainder_task`.
- Catatan uji lama: `tests/test_fase_sl_*.py` memakai id tugas seed LAMA tertulis mati (`wms_e2e3d9059660`) → 404 di DB seed baru (bukan regresi; dengan id seed sekarang 18/18 lulus).
## GRN Fase 3 selesai — frontend Kedatangan Barang (2026-06)
- Layar `?view=goods-receipts` (menu Gudang & Logistik → Kedatangan Barang): daftar per status + cari, wizard 2 langkah (mitra+PO/MKO+gudang → foto SJ multi-halaman, diperkecil 2048px JPEG 0,85, peringatan foto kecil), detail dengan stepper, tab Surat jalan (foto zoom/putar + kepala SJ + tabel baris + target), Hitung (scan label / roll manual / undo, hitung buta), Rekonsiliasi (tabel SJ vs hitung vs sisa PO, penyelesaian selisih via askReason, Tutup Penerimaan terkunci bila ada pemblokir, hasil posting & tugas sisa).
- Tab "Selisih Supplier": ringkasan per mitra dari GRN ditutup (`GET /goods-receipts/supplier-variance`).
- Tombol PO "Terima Barang di Gudang" → wizard GRN terisi supplier+PO+gudang; "Barang Masuk (lama)" tetap ada.
- Panel tugas lama: banner "Bagian dari GRN …" + baca-saja saat dihitung; setelah tutup "Diterima lewat Kedatangan Barang · SJ …".
- Endpoint baru: `GET /goods-receipts/partners`, `/{id}/rolls`, `/supplier-variance`.
- Uji: iteration_67 (backend 28/28 + UI dasar), iteration_68 (alur hitung→rekon→tutup→selisih, hitung buta, banner). Perbaikan: isian kepala SJ tidak lagi tertimpa/409 setelah "Isi manual".
- Data demo: KSC/GRN-00003 ditutup (100 yd PO-00014, klaim supplier) + tugas sisa 150 yd.

## GRN Fase 4 selesai — OCR OpenAI (2026-09-25, kode siap; kunci OpenAI belum ada)
- Backend: `services/ocr_openai_client.py` (satu-satunya import `openai`, Responses API + schema strict, store=False, kode galat OCR_*), `ocr_sj_v2.py` (PROMPT/SCHEMA sj-v2), `dn_rules.py` (parser angka, pilih declared, pola PO, cocok baris, cek total), `goods_receipt_ocr_service.py` (klaim CAS draft→reading, pembaca kedua on_doubt, `ai_usage_log` + biaya, rem anggaran + notifikasi ambang, penyapu malas >5 mnt, `pages_from_bytes`). Endpoint `POST /goods-receipts/{id}/read`, `GET /goods-receipts/usage?month=` (hak approve). Detail GRN kini memuat `ocr_enabled`.
- Integrasi: blok `openai` di integrations (`openai_api_key`/`openai_clear_key`, `POST /admin/integrations/openai/test`) + panel UI `OpenAiIntegrationPanel` (Admin → Master Data & Audit → Integrasi AI).
- UI GRN: draf → "Baca otomatis" + "Isi manual saja" (`grn-ocr-read`, `grn-manual-entry`), progres `grn-ocr-progress` (polling saat status reading), kotak hasil `grn-extraction` (gagal `grn-ocr-failed`, peringatan nama supplier/penerima `grn-ocr-warnings`, beda pembaca kedua `grn-ocr-header-diff` + sorotan emas di isian kepala SJ), kolom Tertulis (qty_text) + Qty, status "Angka ragu", baris ragu `grn-line-doubt-<n>` dengan pilihan kandidat/isi lain, beda per baris `grn-line-diff-<n>`. Tab "Biaya OCR" (`grn-view-tab-usage`, admin/manager/warehouse_admin).
- Skrip evaluasi `backend/tools/ocr_eval.py` (env `OCR_GOLDSET_DIR`, laporan akurasi per field, baris salah tak ditandai, biaya/lembar, gerbang §5).
- Mode tiruan: backend/.env `OCR_ALLOW_MOCK="1"` + model `mock-<fixture>` (tests/fixtures/ocr). Demo: `cd /app/backend && python ../scripts/seed_grn_ocr_demo.py` (KSC/PO-00014, angka ragu).
- Uji: GRN total 42/42 (iteration_69). Kegagalan je_debit sesi lalu = DB tercemar; dengan seed segar lulus.
- Bawaan tetap `receiving.ocr_enabled=false`. Untuk LIVE: isi kunci OpenAI, uji koneksi, nyalakan per entitas, pastikan nama model `receiving.ocr_model_*` valid di akun OpenAI.

## GRN Fase 5 makloon + Profil SJ otomatis + validasi manual OCR (2026-09-25)
- VALIDASI MANUAL: hasil OCR = usulan. Kepala SJ (`dn.verified`) & tiap baris OCR (`verified`) wajib dicek manusia sebelum `start-count` (400 NOT_READY, `verification_errors`). PATCH dn → verified + `corrected_fields`; PATCH baris (ubah apa pun / `verified:true`) → verified, koreksi vs `ocr_declared` → `corrected` + `corrected_fields`. UI: `grn-verify-summary`, `grn-dn-pending` + tombol "Konfirmasi kepala SJ", status baris "Belum dicek", tombol `grn-line-verify-<n>` (Sesuai foto), edit penuh `grn-line-edit-<n>` → `grn-line-edit-form-<n>` (kode, deskripsi, PO, qty, satuan, roll, kg, grade, lot, non-stok), label `grn-line-corrected-<n>`.
- FASE 5 MAKLOON: OCR memetakan SJ makloon ke langkah MKO `issued` (nomor MKO → nomor lama/PO di MKO → pola PO klien → satu-satunya MKO). Baris grade BS → `role: byproduct` bila langkah punya produk sisa; selain itu `role: ""` + pertanyaan (pemblokir sampai dipilih, `grn-line-role-<n>`). Barang sisa: satuan sendiri (tanpa konversi), roll hitung boleh tanpa lot (auto `SISA-<MKO>-<seq>`), wajib ada baris output langkah sama. Tutup → `receive_step` dengan qty output = hitung fisik, `actual_byproduct_qty`, `byproduct_lot`, `supplier_dn`, berat per roll (`MakloonReceiveRoll.weight_kg`, `MakloonReceiveIn.supplier_dn`). Tombol MKO `receive-step-grn-<seq>` "Terima lewat Kedatangan (SJ)" → `?view=goods-receipts&mko=&makloon=&wh=` (wizard preset).
- PROFIL SJ: `services/supplier_dn_profile_service.py` belajar saat GRN ditutup (idempoten per GRN) HANYA dari data yang dicek manusia: suara format angka (`locale_votes`, aktif otomatis ≥3 SJ & ≥80% bukti, bisa dikunci admin), nama lain pengirim (hanya varian yang memicu peringatan), pemetaan barang `item_map` (kode/deskripsi → produk, dipakai `match_line` method `profile`), statistik akurasi (baris dikoreksi/total). API `GET/PATCH /goods-receipts/dn-profiles[/{partner_id}]`. UI tab "Profil SJ" (`grn-view-tab-profiles`, `GrnProfilesPanel`). Info profil di hasil baca (`grn-ocr-profile`).
- Perbaikan: `normalize_grade` mengembalikan dict → grade baris manual/OCR kini tersimpan sebagai string.
- Uji: `tests/test_grn_phase5.py` (5) + seluruh GRN 47/47 (iteration_70). Fixture mock `sj_makloon.json`. Demo: `scripts/seed_grn_ocr_demo.py` (KSC/GRN-00004 supplier, KSC/GRN-00005 makloon — sudah ditutup oleh uji UI; MKO-00002 kini received, seed ulang lewat seed_realistic bila perlu).

## GRN Fase 6 packing list + nama/warna versi supplier + selisih di tagihan (2026-09-25)
- NAMA & WARNA VERSI SUPPLIER: `dn_rules.match_line` kini: profil → `supplier_sku` → kode warna supplier (unik) → skor nama (vs `supplier_items.supplier_item_name`, nama internal hanya cadangan) 60% + warna (vs `products.supplier_colors` nama/kode, warna internal cadangan) 40%; tanpa warna & nama supplier sama → ambiguous (manusia memilih). `_enrich_supplier_names` menempelkan data ke tugas. `match.via` disimpan; UI `grn-line-mapping-<n>` "SJ: … → KN: … · via …". Tombol `grn-line-catalog-<n>` → `POST /goods-receipts/{id}/lines/{n}/save-catalog` (tawaran simpan ke Katalog Supplier; warna tetap lewat ACC R&D). Sebelumnya: nama supplier TIDAK terpakai (tugas tak membawa supplier_item_name) & warna supplier diabaikan — sudah diperbaiki.
- FASE 6: `receiving.ocr_extract_packing_list=true` → `packing_list` → `line.expected_rolls` (`assign_packing_groups`: lot → item_hint ≥0,6 → tanpa petunjuk satu baris/urutan; tak terpasang = peringatan). Bisa dikoreksi di edit baris (`grn-edit-pl-<n>`, PATCH `expected_rolls`). Hitung: `GrnPackingChecklist` (`grn-pl-list-<n>`, `grn-pl-roll-<n>-<seq>`, `grn-pl-result-…`), roll diukur ber-`expected_seq` (roll PO: `grn_expected_seq`; makloon: `expected_seq`), `roll_check` (konversi m↔yd, beda >max(0,5;1%)), hitung buta: panjang PL disembunyikan sampai diukur. Rekon: `packing_list_mismatch` (bukan pemblokir).
- TAGIHAN: `GET /goods-receipts/doc-variance?po_id=|mko_id=&step_seq=` (izin goods_receipt.view ATAU vendor_bill.view; hanya GRN closed) → rows/summary/claims. UI `GrnDocVariance` di VendorBillDetailPanel (`vb-grn-variance`, PO atau MKO+langkah untuk tagihan jasa makloon) & VendorBillCreateModal (`vb-create-grn-variance`).
- Uji: `tests/test_grn_phase6.py` (10) · total 55 lulus + 2 skip (iteration_71). Demo: KSC/GRN-00007 (SJ-MOCK-PACK, review), KSC/GRN-00004 (angka ragu), VBM-00007 (selisih makloon).

## GRN Fase 7 — beralih penuh per badan usaha (2026-09-25)
- Backend `services/receiving_mode_service.py`: `GET /goods-receipts/mode` (status per entitas: mode, tugas menunggu, sudah mulai di layar lama, legacy_in_flight, kedatangan terbuka/ditutup; izin goods_receipt/purchase_order/makloon_order view) · `PUT /goods-receipts/mode` {entity_id, mode, reason≥5} (goods_receipt.approve + role admin/manager) → `set_value("receiving.mode", scope entity)` + tandai tugas yang sudah dimulai `legacy_in_flight` + audit. Guard baru: `POST /makloon-orders/{id}/receive` → 409 GRN_MODE di entitas mode grn (selain scan-receive/scan-label/complete yang sudah dijaga `guard_legacy_receiving`).
- Frontend: hook `useReceivingMode` (cache + event `kn:receiving-mode-changed`); tab "Mode Penerimaan" (`grn-view-tab-mode`, `GrnModePanel`, kartu per entitas + konfirmasi beralasan). Disembunyikan di mode grn: tab Barang Masuk (hilang bila tak ada tugas in-flight; bila ada jadi "Barang Masuk (sisa lama)"), daftar tugas lama difilter ke in-flight + banner `inbound-grn-mode-banner`, tombol PO "Barang Masuk (lama)", tombol MKO "Terima Hasil", aksi terima di aplikasi gudang (`mw-inbound-grn-<id>`).
- Bawaan semua entitas tetap `legacy` (uji karakterisasi jalur lama memakai ent_ksc). Uji: `tests/test_grn_phase7.py` (3) · total 55 lulus (iteration_72). Membersihkan lapisan entitas: `POST /config/values/clear`.
### Berikutnya: kunci OpenAI + set emas SJ · pilot per entitas lalu nyalakan mode Kedatangan · seed supplier_colors demo · klaim dari tagihan.

## Tanya KN (Asisten Analitik) — F0 + F1 selesai (2026-09-27)
Spesifikasi: `memory/tanya_kn/Rencana_Prompt_Asisten_Analitik_KN.md` (+ Lampiran A–D). Rencana & status fase: `memory/tanya_kn/PLAN_TANYA_KN.md`. Aturan: satu fase per sesi.
- Catatan GRN/OCR: Fase 0–7 spesifikasi GRN sudah selesai semua; sisa hanya kunci OpenAI + set emas SJ + pilot per entitas.
- F0: `services/analytics_time.py` (periode WIB, pembanding, DATE_FIELDS), indeks analitik, 5 celah hak akses ditutup (/reports/summary kepemilikan sales · /sales/kpi & /sales/commission izin+entitas · /finance/profitability strip HPP + base_quantity · /invoices per entitas), grup konfigurasi "Asisten Analitik" (`ai.sales_definition`, `ai.sales_attribution`, `ai.margin_roles`, `ai.stock_value_roles`).
- F1: `fact_sales_lines` (`services/analytics_facts.py`, job `ai_fact_sync` 5 mnt + `ai_fact_nightly` 02.00), katalog `cat-v1` (`services/analytics_catalog.py`, 30 metrik/19 dimensi), mesin `services/analytics_engine.py` (query_metrics, analyze_change, ai_results TTL 30 hari), endpoint `/api/ai/{catalog,query,analyze-change,results/{id},facts/status,facts/rebuild}`.
- Uji: `tests/test_tanya_kn_f0_time.py`, `test_tanya_kn_f0_access.py`, `test_tanya_kn_f1_engine.py`, `test_tanya_kn_supplemental.py` → 65 lulus (iteration_73).
### Berikutnya: F2 (tool server + orkestrator OpenAI Responses + prompt caching + pemeriksa angka + log biaya) — butuh kunci OpenAI & spike cache §7.2 · lalu F3 UI panel "Tanya KN".

## Tanya KN — F2/F3 UI + mode uji + unduh Excel per jawaban (2026-09-27)
- Pilihan user: OpenAI dengan kunci sendiri (MENYUSUL, isi di Admin → integrasi OpenAI) · model `gpt-6-sol` (bawaan `ai.model_main`) · chat dinyalakan admin sendiri (`ai.enabled`, bawaan mati).
- Panel `?view=tanya-kn`: template laporan (grafik+tabel), chat bebas, strip Aturan Angka → Pusat Pengaturan grup "asisten-analitik".
- MODE UJI (MOCKED): `ai.enabled=true` + `ai.model_main` berawalan `mock` (mis. `mock-chat`) → chat menjawab TANPA OpenAI (template terdekat, teks diawali "[MODE UJI …]"), status pill "Mode uji (tiruan)".
- Excel: per tabel `GET /api/ai/results/{id}/export.xlsx` + seluruh jawaban `GET /api/ai/export.xlsx?ids=a,b` (1 sheet per hasil; tombol `tanya-answer-export`). Hasil chat yang tak dirujuk teks tampil di "Data pendukung".
- Uji: `tests/test_tanya_kn_f2_f3.py` (6) + UI (iteration_74) lulus. Status akhir DB: ai.enabled=false, model gpt-6-sol.
### Berikutnya: pasang kunci OpenAI → admin aktifkan → uji chat nyata (gpt-6-sol) bersama owner · riwayat sesi chat di panel · F4 narasi AI untuk template.

## Tanya KN — riwayat, narasi, jadwal, fase F2–F5 selesai tanpa kunci (2026-09-27)
- Riwayat percakapan (tab Riwayat: cari/buka/lanjut/hapus/baru), jawaban markdown, komentar 👎, "Simpan sebagai template saya" (tab Laporan → Template saya).
- Narasi template di atas grafik: otomatis dari angka server; AI luna/sol menyala otomatis setelah kunci + ai.enabled.
- Laporan terjadwal harian/mingguan (notifikasi aplikasi saja, pilihan user), tab Jadwal + riwayat kiriman.
- Anggaran AI USD 100/bulan + log biaya + ai.enabled_roles · cache template 5 mnt · routing pertanyaan≈template · snapshot harian stok & piutang · set evaluasi 120 (`backend/tools/ai_eval`).
- MOCKED: semua jalur OpenAI belum pernah diuji nyata (kunci belum ada); mode uji `mock-chat`.
- Uji: iteration_75 (backend 13/13, UI 100%). Detail: `memory/tanya_kn/PLAN_TANYA_KN.md`.
### Berikutnya: pasang kunci OpenAI → spike cache §7.2 → `run_eval.py --mode model` → pilot owner · laporan terjadwal via WhatsApp (bila diminta) · streaming token.


## Tanya KN — Jawaban Bertahap + Halaman Biaya AI (2026-09-27)
- Streaming: `ai_chat_service.stream_text` kirim `delta` kata demi kata (blok kn-* utuh) untuk jawaban template/mode uji/notice; jalur OpenAI memakai `responses.create(stream=True)` → `response.output_text.delta` diteruskan, `delta_reset` bila ronde berakhir dengan tool call, `done.text` = teks final. Header SSE `Cache-Control: no-cache`, `X-Accel-Buffering: no`. UI `TanyaStreaming` (blok kn-* tampil placeholder sampai selesai), parse SSE inkremental di `askChat`.
- Biaya AI: tab "Biaya" (`?view=tanya-kn&tab=cost`) → `TanyaCostView` (KPI, grafik batang bertumpuk harian per fitur & per pengguna, tabel fitur/pengguna/model, rentang 7/30/90, cakupan Tanya KN/semua fitur AI, metrik USD/panggilan/token) + `TanyaBudgetCard`. API `GET /api/ai/usage/daily` (`services/ai_usage_report.py`), akses = `ai.enabled_roles`.
- Data contoh `scripts/seed_ai_usage_demo.py` (demo:true, dikecualikan dari anggaran; `--clear`).
- Uji: iteration_76 (backend 6/6 baru + 13/13 regresi, UI 100%). `backend/tests/test_tanya_kn_streaming_costpage.py`.
- Belum: jalur streaming OpenAI nyata belum diuji dengan kunci (MOCKED); harga gpt-6-luna masih perkiraan.

## Tanya KN di HP + audit mobile sales (2026-09-28)
- `TanyaKnView` mode ringkas (≤900px, `useIsMobile(900)`): tab horizontal Tanya/Laporan/Riwayat/Jadwal/Biaya, satu kolom; pilih template/sesi/kiriman otomatis kembali ke tab Tanya. CSS HP di akhir `tanya.css`.
- Sales HP: kartu `m-home-ask-kn` + menu Lainnya `mobile-more-tanya`; deep link `?view=tanya-kn` → subhalaman Tanya. Seksi baru "Fitur lainnya · tampilan penuh" (`mobile-full-<view>`: sample-orders, rnd-samples, logistics, finance-cases, cash-advances, vehicle-logs, mkt-calendar, document-center, hr-my-profile) membuka halaman responsif + tombol `mobile-back-to-app` (App.js `mobileVisit`).
- Peran lain di HP (MobileOpsApp): tab `mobile-tab-btn-tanya` untuk peran asisten (menggantikan tab Desktop; tombol desktop pindah ke tab Ringkas).
- Uji: iteration_77 (UI 100%, sales/manager/finance/admin HP + regresi desktop).
- Celah HP tersisa: sub-halaman hub Pesanan, Pelanggan, Produk & Harga, Stok & ATP hanya diwakili layar HP sederhana.

## Hub lengkap di HP sales (2026-09-28)
- `MobileHubMenu.jsx` (Lainnya → "Hub lengkap · setara desktop", `mobile-hub-<view>`): semua tab hub Pesanan, Pelanggan, Produk & Harga, Stok & ATP yang boleh dilihat peran (via `hubTabsForRole`) dibuka tampilan penuh + `mobile-back-to-app`. Setara 1:1 dengan tab desktop sales (4/2/2/2).
- Perbaikan: PaginationBar grup kanan `flex-wrap` (halaman Retur tidak melebar di HP); `.m-main` scroll-padding-bottom agar tombol tidak tertutup tab bar.
- Uji: iteration_78 + iteration_79 (10/10 hub, UI 100%).

## Koreksi cepat HP + menu lipat + pelanggan baru HP (2026-09-28)
- `MobileAmendments.jsx` + `MobileAmendSheet.jsx`: Lainnya → Koreksi & Amandemen (statistik, tab Ajukan/Riwayat) dan tombol "Ajukan koreksi" di detail pesanan (tab Pesanan). Ubah jumlah/harga/diskon → alasan dipilih otomatis (qty_adjustment / price_correction / discount_grant, bisa diganti) → dampak dari `/api/amendments/preview` → "Ajukan koreksi". API amandemen yang ada, tanpa perubahan backend.
- `MoreSection.jsx`: menu Lainnya dikelompokkan (Asisten & laporan, Pesanan & harga, Pelanggan & lapangan, Stok, Hub lengkap, Fitur lainnya), bisa dibuka/tutup, status diingat (`localStorage kn_m_more_open`).
- `MobileCustomerForm.jsx`: tambah pelanggan dari HP (Pelanggan (CRM) → `m-customers-add`, dan checkout keranjang → `mobile-cart-new-customer`); POST /api/customers, sales pembuat otomatis PIC.
- Pesanan Khusus (OD) sudah ada di HP sebelumnya (`m-special-new`).
- Uji: iteration_80 (backend 5/5, UI ~95%; alur "pelanggan baru dari keranjang" belum diuji ujung-ke-ujung).

---
## Sesi 2026-09-28 — Kelengkapan UI HP (mobile web) Sales & Admin Sales
Lingkungan: repo di-clone ulang ke /app (backend FastAPI + frontend CRA). Frontend dilayani bundle statis
(`static_server.js`) oleh program supervisor `expo` lewat script `"expo": "node static_server.js"` di
frontend/package.json. Setelah ubah src: `bash /app/scripts/rebuild_frontend.sh`.
backend/.env ditambah: CORS_ORIGINS, SESSION_COOKIE_SAMESITE, SEED_DEMO_ENABLED. Data demo: `python /app/seed_realistic.py`.

Audit web vs HP → celah yang ditutup:
- Admin Sales di HP dulu jatuh ke MobileOpsApp (inbox generik). Kini memakai MobileSalesApp (mewarisi menu sales)
  dengan tab pertama **Meja** = `MobileSalesAdminDesk` (antrean /sales-admin/desk, Verifikasi, Keputusan Pemenuhan,
  Konfirmasi, baris "Buka" → layar HP pesanan/retur/PIN/OD atau tampilan penuh). Kunjungan Sales disembunyikan (403).
- Pemilih badan usaha di Lainnya (termasuk "Semua" = hanya-lihat + catatan).
- Pesanan: rincian kini memuat perjalanan pesanan (/journey), sisa tagihan, alamat & termin, Catat bayar (kwitansi AR),
  Ajukan retur (pra-isi pesanan); Admin Sales: Verifikasi/Konfirmasi/Keputusan pemenuhan.
- Layar HP baru: Permintaan Internal (PIN: daftar, filter, ajukan multi-baris + isyarat stok, batal, TINDAK: pilih PT
  sumber → jadikan antar-PT / tolak), Status Harga Khusus, Pesanan Sampel (native), Pantau Persetujuan (Admin Sales).
- Beranda HP sales: papan "giliran Anda" (WaitingQueueBoard), KPI Pelanggan Saya & Capaian Target, rincian komisi per SKU,
  tren komisi 6 bulan, Pelanggan Saya & Kredit.
- Tampilan penuh Admin Sales: Meja (desktop), Operasi Gudang, PR, Transaksi Antar-PT, Kebijakan Retur; semua peran: Jejak Dokumen.
- Dialog desktop (Verifikasi/Pemenuhan) tampil sebagai lembar bawah di HP; tabel barang bisa digeser.

Backlog HP berikutnya: layar HP native untuk Pengiriman, Kas Kecil/PD, R&D sample (masih tampilan penuh);
detail pelanggan → riwayat penagihan/follow-up; mode offline untuk aksi Admin Sales.

### Sesi 2026-09-28 (lanjutan) — alur sales lengkap, notifikasi, PWA
- Pelanggan HP: kartu kredit (limit/tersedia/lewat tempo/status blokir), Telepon/WhatsApp, Ubah data (PATCH /customers/{id}),
  Tambah alamat kirim (POST /customers/{id}/addresses + LocationFields), Tindak lanjut penagihan (POST /customers/{id}/followups),
  tab Alamat & Kontak, tombol "Buat pesanan" (pelanggan langsung terpilih di keranjang).
- Pesanan Khusus HP: detail (status, spesifikasi, tahapan, harga final, riwayat), Ajukan draf, keputusan pelanggan ACC/revisi/tolak + foto bukti.
- Retur HP: Ajukan draf (submit) + unggah foto bukti. Pesanan Sampel: batalkan (bila punya izin sample_order.cancel).
- Notifikasi: lonceng HP bisa diketuk (tandai dibaca + buka layar terkait), polling 60 dtk + saat kembali ke aplikasi,
  Web Push PWA: backend routers/push.py + services/web_push_service.py (pywebpush, VAPID_* di backend/.env), audiens = penyaring lonceng;
  service worker menampilkan notifikasi & membuka aplikasi saat diketuk; kartu "Notifikasi HP" di Lainnya (izin kontekstual, uji, matikan).
- PWA: public/manifest.json, ikon 192/512/maskable/apple-touch, meta apple/theme-color, tombol "Pasang aplikasi" (beforeinstallprompt / panduan iOS),
  pintasan ?m=orders|catalog, SW v3 menyimpan data sales terakhir untuk offline baca.

### Sesi 2026-09-28 (lanjutan) — Aplikasi HP MD / Merchandiser
MD dulu jatuh ke MobileOpsApp (inbox generik). Kini `MobileMdApp` (App.js: role md + wantMobile):
- Tab Meja (/md/desk: desain, sample & labdip, PR bahan, SPK tanpa acuan; baris → layar HP terkait / tampilan penuh),
  Desain (daftar+filter, buat & ajukan, tugaskan desainer, ACC / minta revisi, batal, riwayat),
  Sample (daftar+cari+filter, detail supplier & putaran, nilai putaran ACC/revisi/tolak + skor, putuskan pemenang: supplier+alasan+harga/MOQ/lead),
  Produk (cari/kategori, detail + stok per gudang, ubah nama/harga dasar via PATCH /products/{id} bila izin product.update),
  Lainnya (push, pasang PWA, pilih badan usaha, PR bahan: daftar/buat multi-baris/ajukan draf, pantau PO, daftar harga, status harga khusus,
  stok, 15 tampilan penuh: spesifikasi, labdip, handfeel, proofing, laporan R&D, galeri desain, template, kategori, warna, UoM, RFQ, supplier,
  inspeksi, jejak dokumen, profil). Lonceng interaktif + polling + web push sama dengan aplikasi sales.
File: features/sales/mobile/MobileMdApp.jsx, MobileMdViews.jsx.


## Sesi 2026-09-28 — Validasi & perbaikan Audit Kode KNHOST Bagian III
Problem statement: "lanjutkan development dari repo github.com/pandeyoga/KNHOST; validasi dan perbaiki catatan & temuan
(PDF Audit_Kode_KNHOST_BagianIII_2026-09-28) jika memang benar." Pilihan user: perbaiki SEMUA temuan yang terbukti, stack asli.
- Laporan per temuan: `memory/LAPORAN_AUDIT_BAGIAN_III_2026-09-28.md` (penanda kode `KN-Exx`).
- Selesai: E01–E51 (kecuali sebagian E07/E20/E30/E42), temuan lama #12 (sebagian), #17, #18.
- Baru: endpoint `POST /api/goods-receipts/{id}/return-to-reconcile` + tombol `grn-return-to-reconcile`; tombol `grn-ocr-retry`;
  lencana `grn-ocr-mock-badge`; input stok awal `stock-unit-cost-input`/`stock-weight-input`; koleksi `supplier_roll_claims`.
- Env baru backend: `KN_SECRETS_KEY` (Fernet, enkripsi kunci API at-rest), `OCR_ALLOW_MOCK=1`, `CORS_ORIGINS` eksplisit,
  `SESSION_COOKIE_SECURE`. Produksi: set `AI_ALLOW_MOCK=0` dan `OCR_ALLOW_MOCK` kosong.
- Skrip data lama E01: `python scripts/fix_sales_name_e01.py [--apply]`.
- Test: `backend/tests/test_audit_bagian_iii.py` (iteration_85: 24/24 lulus; 1 kasus E03 kini bergantung data karena harga SO demo sudah diamandemen saat uji).

### Backlog (P1/P2)
- P1: keputusan pemilik — tarif PPN antar-PT (#16), satuan lebar varian cm vs m (#15), penyatuan toleransi penerimaan (E20).
- P2: penerimaan parsial per langkah makloon (E07), hash foto asli dari klien (E30), impor pelanggan (#13), data demo SDM (#14),
  sisa laporan (#11), registry scope koleksi ai_* (#19), sinkron dokumen `backorders` saat amandemen qty (E04d).


---
## Sesi 2026-06 (lanjutan repo github.com/pandeyoga/KNHOST) — penyelesaian pengujian fitur Bagian III lanjutan
- Repo di-clone ke /app, dependensi dipasang, DB di-seed (seed_realistic.py + seed_e9_chain_demo.py), bundel FE di-build ulang.
- `.env` backend: CORS_ORIGINS wajib (bukan '*') — diisi URL preview + localhost:3000.
- Test E02/E03/E04c (`tests/test_audit_bagian_iii.py`) kini DINAMIS: cari SO demo E-9 via Mongo, harga di bawah lantai dihitung dari price_guard (floor-1) → 25/25 lulus.
- Diuji & lulus: PPN antar-PT ikut pajak penjualan, terima makloon bertahap (validasi + merge), impor/ekspor pelanggan dengan sales & kode unik, laporan net & WIB, HPP stok awal, hash foto asli GRN, varian lebar cm→m (iteration_87 17/17, iteration_88 FE 3/3; hash foto GRN diverifikasi live).
- Perbaikan: `GET /api/inventory/rolls-without-cost` kini mengembalikan sku, nama produk & qty (sebelumnya kosong di peringatan HPP).
- Suite regresi baru: `backend/tests/test_review_iter86_features.py` (jalankan dengan `-o addopts=''`).

### Backlog
- P1: Seed demo GRN makloon status reconcile agar toggle `grn-mko-partial-toggle` bisa diuji end-to-end di UI.
- P2: Jejak (trail) saat penerimaan makloon terakhir menyerap GRN parsial sebelumnya.
- P2: Samakan bentuk respons /reports/order-velocity (dict) dengan endpoint laporan lain.

### 2026-06 (lanjutan-2)
- Demo terima makloon bertahap: `scripts/seed_makloon_partial_demo.py` (MKO-00002 langkah 1: GRN SJ-DEMO-MKL-P1 30 yd ditahan, GRN SJ-DEMO-MKL-P2 42 yd di rekonsiliasi dengan centang `grn-mko-partial-toggle`).
- Riwayat makloon parsial: `partial_receipts[]` mencatat by_id, `absorbed_by`; langkah mendapat `partial_absorption` + timeline `partial_received`/`partial_absorbed`; UI `MakloonPartialReceipts` di kartu langkah MKO.
- Pengingat HPP go-live: `OpeningCostBanner` di Control Tower admin & Dasbor Manajer → Operasi/Stok (peringatan kini di atas layar Stok). GET rolls-without-cost memakai izin `inventory.view`.
- Audit E04 sisa ditutup: amandemen qty menyinkronkan `sales_orders.backorders[]` + `has_backorder`.
- Test: iteration_89 (BE 100%, FE 4/5 → izin manajer diperbaiki & diverifikasi 200).

### 2026-06 (lanjutan-3)
- Batal terima sebagian: POST /api/makloon-orders/{id}/steps/{seq}/partial-receipts/{grn_id}/cancel {reason ≥5} → entri pindah ke `cancelled_partials`, GRN → cancelled (+`mko_partial_cancelled`), timeline `partial_cancelled`; UI tombol di kartu langkah.
- PDF SPK Makloon: tabel "Riwayat Kiriman Bertahap" (engine PDF kini mendukung `extra_tables`).
- Rantai dokumen: jenis `journal_entry` + tautan TURUNAN (jurnal via source_id, kas via ref_id) di Jejak & panel Relasi (tidak dicetak di kop PDF); kiriman sebagian ↔ penerimaan akhir & tagihan jasa ↔ semua kedatangan kini bertaut.
- Test: iteration_90 BE/FE 100%.
- 2026-06: Klik jurnal di Jejak Dokumen → Buku Besar (general-ledger) langsung membuka detail jurnal itu (focus_type journal_entry; daftar tersaring ke nomornya).
- 2026-06: Jurnal yang dibuka dari Jejak punya tombol "Kembali ke Jejak <nomor>" (from_trace di focusDoc). Cetak Jejak Dokumen: GET /api/documents/trace/{type}/{id}/print (pdf|html, depth) + tombol `trace-print-pdf` — daftar dokumen (★ jangkar), tabel relasi (tersimpan vs otomatis), tanda tangan pencetak & auditor. iteration_91 100%.


---
## Sesi 2026-09-28 — Aktivasi OpenAI (repo github.com/pandeyoga/KNHOST)
**Permintaan:** lanjutkan repo KNHOST, aktifkan API OpenAI untuk fitur yang ada (key milik user), uji OCR dengan 5 foto
SJ/packing list WhatsApp. Model pilihan user: **gpt-6-sol & gpt-6-luna**.

**Dikerjakan**
- Repo dipulihkan ke /app (deps, seed, build FE). `backend/.env`: `OPENAI_API_KEY` (key user), `KN_SECRETS_KEY`,
  `CORS_ORIGINS` eksplisit, `KN_DEMO_DATA`/`SEED_DEMO_ENABLED`.
- Konfigurasi diaktifkan via Pusat Pengaturan (tercatat audit): `ai.enabled=true`, `receiving.ocr_enabled=true`,
  `receiving.ocr_extract_packing_list=true`. Integrasi OpenAI diuji → `verified_at` terisi (sumber kunci: env).
- Model: chat/narasi `gpt-6-sol` (main) & `gpt-6-luna` (fast); OCR utama `gpt-6-sol`, pembaca kedua `gpt-5.6-sol`.
- **Baru — auto-orientasi foto SJ** (`goods_receipt_ocr_service.auto_orient` + `ocr_openai_client.detect_rotation`):
  foto WhatsApp miring 90° (EXIF hilang) diputar tegak sebelum OCR. Kunci baru `receiving.ocr_auto_orient` (default aktif)
  & `receiving.ocr_orient_model` (default `gpt-6-sol`; uji: luna sering tertukar 90°/270°, sol konsisten 3/3).
  Hasil tercatat di `extraction.orientation` + `ai_usage_log` role `orient`. `gpt-6-luna` ditambah ke tabel harga OCR.
- **Baru — upscale foto kecil** (sisi pendek < `receiving.min_photo_short_side_px`, maks 2×) sebelum dikirim.
- **Baru — PO klien tanpa label di baris** (mis. "(3374/SCB/0926)" di keterangan) kini dipindai `client_po_patterns`
  untuk pencocokan PO. `tools/ocr_eval.py` ikut memakai auto-orient & logika PO yang sama.
- Set emas kecil: `/app/tests/fixtures_sj/gold` (sj1, sj4). Hasil eval: nomor SJ 50–100% (sj1 ambigu SRJL), tanggal,
  qty, satuan, roll, po_ref 100%, baris salah tak ditandai 0%. ±US$0,015/lembar.

**Backlog**
- P1: perbanyak set emas (≥20 SJ nyata) untuk gerbang §5 Fase 4; foto sangat pudar (dot-matrix karbon) tetap sulit.
- P2: tampilkan info "foto diputar otomatis" di layar tinjau GRN.


## Sesi 2026-09-28 (lanjutan) — Tips foto, info foto diputar, Sampel Uji OCR, belajar dari koreksi
- **Tips Foto SJ** (`GrnPhotoTips.jsx`) di langkah unggah wizard Kedatangan (6 tips, bisa dilipat, disimpan di localStorage).
- **Info Foto Diputar**: kotak `grn-ocr-rotated` di layar tinjau + foto kiri ikut diputar otomatis (canvas, `grn-photo-auto-rotated`).
- **Sampel Uji OCR** (tab baru di Kedatangan Barang): koleksi `ocr_samples` + `ocr_sample_runs`, router `/api/ocr-samples`,
  layanan `services/ocr_sample_service.py`. Tombol **Jadikan sampel uji** di detail GRN (jawaban = isian yang sudah dicek),
  editor kunci jawaban, uji berjalan di latar (progres), laporan akurasi per field vs target (SJ ≥98%, qty & satuan ≥95%).
  Seed 7 sampel dari foto nyata pemilik: `scripts/seed_ocr_samples.py` (ent_ksc 2, Cipta Sandang 5).
  Uji pertama: nomor SJ 100%, tanggal 100%, qty 89% (SJ-3171 ambil angka roll pertama), satuan 100%, roll 100%, PO baris 50%.
- **Aturan qty total baris** (`dn_rules._row_total`): bila baris merinci panjang per roll + total, pilih angka = jumlah sisanya.
- **Belajar dari koreksi (bukan melatih ulang model)**: `supplier_dn_profiles.corrections[]` (beda baca AI vs final manusia,
  dari GRN ditutup / dijadikan sampel) + `format_notes` (catatan admin di Profil SJ) → dikirim sebagai petunjuk ke AI saat
  membaca SJ mitra yang sama (`hints_for`). Tercatat di `extraction.hints_used`, tampil `grn-ocr-hints`.
  Terbukti: GRN-00007 dikoreksi 495→405 → baca ulang SJ yang sama untuk mitra itu membaca 405.

**Backlog berikutnya**
- P1: kumpulkan ≥20 sampel nyata per badan usaha; koreksi po_ref baris ikut direkam sebagai petunjuk.
- P2: petunjuk tingkat badan usaha (bukan per mitra) untuk sampel tanpa mitra; ekspor laporan uji.


## Sesi 2026-09-28 (lanjutan 2) — Koreksi PO baris jadi petunjuk AI + UI HP
- `goods_receipt_service.update_line`: nilai PO asli AI disimpan di `lines[].ocr_po_ref` saat pertama dikoreksi;
  `corrected_fields` memuat/menghapus `po_ref` sesuai beda. `corrections_from_grn` merekam "Baris N nomor PO";
  `hints_for` menambah panduan PO tanpa label. UI: PO dikoreksi menampilkan "AI: ~~asli~~" + catatan belajar di form edit.
- **UI HP**: Kedatangan Barang kini bisa dibuka di HP (`App.js` responsiveWorkspace + tombol "Kembali ke aplikasi HP");
  pintu masuk di aplikasi HP gudang (kartu `mobile-open-grn` di tab Masuk) & HP admin/manajer (tab Produk
  `mobile-open-grn-ops`). Baris SJ jadi kartu di HP (`GrnLineCard.jsx`), form edit & pilihan angka ragu dipakai bersama
  tabel desktop; wizard & editor sampel jadi bottom-sheet (z-70 di atas tombol melayang); tab/stepper bisa digeser;
  foto ringkas; Profil SJ & Sampel Uji OCR tanpa luapan horizontal di 390px. Diuji iteration_94: 100%.

## Sesi 2026-09-28 (lanjutan di kontainer baru)
- Repo dipulihkan (`.restore_env.sh`): CORS_ORIGINS eksplisit, KN_SECRETS_KEY baru, seed, build FE.
- Kunci OpenAI klien dipasang (integrasi terenkripsi + env OPENAI_API_KEY), uji koneksi lulus; gpt-6-sol/gpt-6-luna/gpt-5.6-sol terbukti tersedia.
- `receiving.ocr_enabled=true` & `ai.enabled=true` (PUT /api/config/values, teraudit). Fakta penjualan dibangun ulang (`POST /api/ai/facts/rebuild`).
- iteration_95: Photo Quality Check backend 6/6 + wizard HP/desktop (buram, terpotong, ambil ulang, dialog kirim) lulus; Tanya KN chat model nyata + template + tab Biaya lulus.

## Tanya KN — dari jawaban ke tindakan, peringatan, konteks halaman, data gudang, perkiraan (2026-09-28)
- Tool baru: `ops_metrics` (supplier_performance, receiving_discrepancy, dispatch_speed, qc_results, makloon_wip — `services/ai_ops_metrics.py`), `forecast` (stock_demand, cashflow, churn_risk — `services/ai_forecast.py`), `propose_action` (draft_po, collection_followup, customer_followup — `services/ai_actions.py`, koleksi `ai_action_proposals`).
- Blok `kn-action` → `TanyaActionCard` (qty bisa diubah, Setujui/Abaikan). API `GET/POST /api/ai/actions/{id}[/confirm|/dismiss]` (`routers/ai_assist.py`). PO dibuat lewat `_create_po_core` dengan hak akses pengguna.
- Peringatan anomali: `services/ai_insights.py`, job `ai_anomaly_scan` 07.00 WIB, koleksi `ai_insights`, notifikasi `ai_insight`; tab `Peringatan` (`TanyaInsights`); `GET /api/ai/insights`, `POST /api/ai/insights/scan`.
- Konteks halaman: `components/AskKnButton.jsx` di Customer360, ProductDetail, PODetailPanel, OrderDetailPanel, GrnDetail → sessionStorage `kn_tanya_pending` → chat `context` → awalan `[Konteks halaman …]`.
- Config: `ai.glossary`, `ai.anomaly_enabled`, `ai.anomaly_drop_pct`, `ai.anomaly_cover_days`. Pemeriksa angka tak lagi menandai "90 hari terakhir".
- Uji: iteration_96 (pytest 24/24 `backend/tests/test_iter96_tanya_kn_actions.py`, regresi Tanya KN 64/64, UI lulus).

## Master produk KN — pengkodean & impor Excel (2026-09-29)
- Kode artikel `KN{KNT|WVN|PRT}{0000}` otomatis saat induk baru tanpa prefix (`product_template_service.next_article_code`).
- Sumbu varian bawaan = urutan segmen SKU: origin (I/L/X) · color (4 kar) · grade (A→XA, B1, C baru) · customer (XX) · lot (XX) — `services/variant_axes.py`, `rnd.variant_axes_default`, `AxisEditor.FALLBACK_AXES`.
- Skrip idempoten `backend/scripts/import_master_produk_kn.py` (+ `--dry-run`) membaca `backend/data/import/TEST_MIGRASI_MASTER_PRODUK.xlsx` → 30 induk, 268 SKU, 325 entity_prices; harga MOCK (yard 18–25 rb, kg 40–45 rb). Panduan VPS: `deploy/IMPORT_MASTER_PRODUK.md`.
- Uji: iteration_97 (14/14 backend, UI lulus).

## VPS sekali jalan (2026-09-29)
- `deploy/setup_vps_ai_import.sh`: simpan OPENAI_API_KEY + KN_SECRETS_KEY di deploy/.env → update.sh → impor Excel master produk → `backend/scripts/vps_enable_ai.py` (kunci terenkripsi, uji koneksi, nyalakan OCR/Tanya KN/peringatan, rebuild fakta, uji chat nyata). docker-compose kini meneruskan KN_SECRETS_KEY & OPENAI_API_KEY. Panduan: `deploy/IMPORT_MASTER_PRODUK.md`.

## 2026-09-29 — Restore repo + perbaikan Daftar Roll (45 ribu roll)
- Repo pandeyoga/KNHOST ditarik ulang ke /app (.env dipertahankan; CORS_ORIGINS eksplisit, SESSION_COOKIE_SECURE, KN_SECRETS_KEY), `.restore_env.sh` (deps, seed_realistic, build FE), impor master produk (268 SKU) + stok awal (45.435 roll MOCK).
- GET /api/inventory/rolls mode array: kini menghormati `?limit` (1–5000, default 5000), `?skip`, `?q` (dulu diabaikan → ~5,9 MB per panggilan; pemindai outbound pakai q+limit=5). Peta produk hanya memuat id/sku/name tanpa batas 1000.
- Layar Daftar Roll (Operasi Gudang → Stok → Roll): default 100 per halaman; PaginationBar mendapat tombol opsional `onFirst`/`onLast` (`rolls-pager-first|last`).
- Uji: iteration_99 lulus (backend & frontend).
## Backlog
- P2: Daftar Roll belum bisa dibuka dari tampilan mobile (shell persona mobile).
- 2026-09-29: `deploy/cek_vps.sh` (pemeriksaan akhir VPS) + dipanggil sebagai langkah 5/5 `setup_vps_ai_import.sh`.
- 2026-09-29: build VPS gagal 'deploy/frontend.yarn.lock not found' (platform tidak mem-push *.lock) → lock kini di deploy/frontend-yarnlock.txt, Dockerfile.frontend menyalinnya secara opsional (COPY …tx[t]).
- 2026-09-29: vps_enable_ai.py & cek_vps.sh tidak wajib sandi admin (sesi admin internal 1 jam, dihapus sesudahnya); setup tidak lagi prompt sandi.
- 2026-09-29: Tanya KN — kotak tanya dipindah ke bawah (sticky, di atas FAB Bantuan), auto-scroll; toast galat chat menyebut HTTP/detail (body teks diurai); nginx-web.conf /api/ai/chat tanpa buffer/gzip 600s; edge.sh nginx host proxy_buffering off. Uji iteration_103 lulus.
- 2026-09-29: Tanya KN redesign gaya Claude (terang, ungu KN): TanyaChatPane (panel tinggi-tetap, pesan bergulir, komposer bulat di dasar, sambutan + 4 contoh, tombol ke-bawah), FAB Bantuan jadi ikon di halaman ini. Uji iteration_104 lulus.

## 2026-09-29 — Lanjutan: repo di-clone ulang + uji UI iter105 + rapikan UI Pesanan Khusus & Produk & Harga
- Restore: rsync repo → /app (.env dipertahankan; CORS_ORIGINS eksplisit, SESSION_COOKIE_SECURE, KN_SECRETS_KEY baru), seed_realistic, impor master produk (268 SKU) + stok awal (45.435 roll MOCK), build FE.
- Uji UI iterasi 105 (PR dua kolom artikel→warna, dual name KN/SUP, filter supplier, papan R&D/desain tanpa kolom selesai, alias supplier di varian) — LULUS (iteration_105.json).
- CSS "hantu" gelombang 3: `.input`, `.field-input`, `.form-select`, `.chip` kini didefinisikan; utility padding (pl-8, px-2, py-1.5 …) di atas `.field/.input/.textarea` kini menang → ikon cari tak lagi menimpa placeholder.
- Produk & Harga: kicker seragam "Produk & Harga", judul "Harga per Badan Usaha"/"Pustaka Warna"; filter harga khusus jadi checkbox; tombol baris "Atur harga/Ubah harga" sekunder di kedua layar harga; katalog selebar tab lain; chip sumbu hero dikelompokkan berlabel & tanpa "Tidak ada"; nama varian "Impor · Warna 10 · Grade A"; form Kategori tidak memanjang; UOM: "Buat Satuan" primer, "Nonaktifkan" garis merah tipis.
- Pesanan Khusus: judul "Pesanan Khusus (OD)", label Indonesia (Dikirim, Draf, Terkonfirmasi di lini masa backend), status dokumen tertaut berlabel, tanggal kirim tanpa jam, kolom angka rata kanan, chip tipe permintaan, modal buat: select tidak terpotong & catatan selebar penuh.
- Catatan: demo SORD-260618-0001 kini berstatus Terkonfirmasi (disetujui saat uji).

## 2026-09-29 — Retur & Makloon seragam gaya Pesanan Khusus + konsolidasi penerimaan barang
- Komponen bersama `components/ListPageParts.jsx` (PageHeader, MetricRow, SearchBox, StatusTabs) dipakai Retur Jual, Retur Beli, Order Makloon, Klaim Makloon: judul ber-ikon + subjudul, kartu KPI, cari + filter lini sebaris, tab status bergaris bawah dengan lencana, tabel data-table (angka rata kanan, nomor monospace, "Detail →"), empty/loading state seragam, label Indonesia (Buat Retur, Draf, Menunggu Persetujuan, Diterima sebagian, Dibatalkan). Retur Beli: kolom Nilai/Nota Debit tak lagi menempel.
- "Kedatangan Barang" (SJ + OCR) = fungsi yang sama dengan Barang Masuk → dihapus dari sidebar, kini tab hub Operasi Gudang "Barang Masuk (SJ & OCR)" (view `goods-receipts` tetap untuk deep link). Tab lama di Operasi WMS dinamai "Scan Terima PO" (mode lama) + banner ke tab baru. Finance melihat Operasi Gudang hanya dengan tab Barang Masuk.
- Uji: iteration_106 (97%; satu temuan role finance → grup Gudang & Logistik kini memuat finance, diverifikasi).

## 2026-09-30 — Mode Surat Jalan Sukacita + rincian seragam + Pembelian seragam
- Sukacita (ent_ksc) kini `receiving.mode = grn` (Surat Jalan & OCR satu pintu); 2 tugas scan lama ditandai sisa lama (tetap bisa diselesaikan). `seed_realistic._seed_receiving_mode` menanam ulang saat reseed.
- `components/DetailParts.jsx` (DetailHeader, Panel, Cell, Timeline) — rincian Pesanan Khusus, Retur Jual, Retur Beli (modal), Order Makloon kini satu gaya kartu. Riwayat retur jual menampilkan Inspeksi & Diselesaikan (dulu "Belum terjadi").
- PR, PO, Tagihan Supplier memakai ListPageParts (judul + subjudul, kartu angka, cari + filter, tab status berlencana, tabel data-table, label Indonesia). PO: tab status baru + backend `GET /api/purchase-orders/status-counts` & param `status` (koma).
- static_server.js: bila folder build hilang saat boot (pod restart), rebuild otomatis di latar + halaman "sedang menyiapkan".
- Uji: iteration_107 — backend 7/7, frontend 100%.

## 2026-09-30 — Mode Surat Jalan & OCR untuk SEMUA badan usaha
- Kanda Fabric (ent_kanda) & Cipta Sandang (ent_15cac172d308) kini `receiving.mode = grn` (Sukacita sudah sebelumnya). Seed `_seed_receiving_mode` kini menanam grn untuk semua badan usaha.
- `receiving_mode_service._entity_status` memakai short_name/legal_name (dulu tampil ID). Teks panel Mode Penerimaan menunjuk ke "Scan Terima PO (sisa lama)".

---
## Sesi 2026-09-30 — Impor paket audit & rencana perbaikan bertahap
- Kode dari github.com/pandeyoga/KNHOST (HEAD ea874d3) disalin ke /app; paket KNHOST_AUDIT_PACKAGE_2026-09-30 diekstrak ke /app/audit (README/WORKFLOW/tracker.json SSOT, 103 record, 15 fase P00–P14, 96 kasus coverage, 1 keputusan policy PG01).
- `python audit/tools/validate.py` → PASS. Environment dipulihkan (.restore_env.sh; seed_realistic dijalankan dengan backend dihentikan agar tidak bentrok bootstrap). Login demo OK.
- Catatan: SHA baseline audit d1fd56e / 3a7c40a TIDAK ada di riwayat repo publik (riwayat ditulis ulang) → setiap ID wajib direbaseline pada HEAD sebelum diperbaiki (P00).
- Aturan kerja: validasi (reproduksi di HEAD) dulu → perbaiki → regression test → status ready_for_validation (bukan verified_fixed) + iterations/<tgl>-<fase>-<slug>/IMPLEMENTATION.md.
- Urutan: P00 → P01 (scope/credential, 19 ID) → P02 → P03 → P04/P06 → P05/P07/P08 → P09–P13 → P14.

## Sesi 2026-09-30 (lanjutan) — P01 Scope Hotfix + Device Key Protection
- Rebaseline di HEAD 08a9009 lalu patch 17 ID P01 (status tracker: in_progress, menunggu SHA commit → ready_for_validation oleh sesi berikut; validator independen yang menandai verified_fixed):
  RF-12/RF-13 (key device di-hash, tampil sekali, rotasi; enabled≠health; UI Devices), GN-01 (idempotency terikat user sesi+entitas+payload), GN-02 (WS tracking: expiry, hr.view, scope entitas), GN-03, IX-05, IX-07, IX-10, AX-04, AX-06, CX-02, GN-04, GN-09, GN-10, GN-16, RF-08, RF-09.
- Tertunda (open): IX-06 (PUT payroll settings global vs entitas — perlu UI pilih lapisan), CX-10 (e-sign binding hash versi).
- Bukti: /app/audit/iterations/2026-09-30-P01-{device-credentials,scope-batch1,scope-batch2}/ (repro sebelum/sesudah + IMPLEMENTATION.md + p01_combined.diff). Testing agent iter108: 63/63 lulus.
- PG01 diputuskan pemilik: opsi C, UI pilihan "Cek semua"/"Sampling" (default cek semua) — dicatat di audit/policy-decisions.json, implementasi di P06.
- Next: isi SHA → ready_for_validation; IX-06 + CX-10; P02 (roll/split/projection); UI PG01 di P06.

## Sesi 2026-10-01 — IX-06, CX-10, P02, PG01/IX-15
- P01 (17 ID) → ready_for_validation (implementasi 522e282, dicek di 0076f7e).
- IX-06: PUT payroll settings pilih lapisan entitas/global lewat config_resolver; /config/values dibatasi penugasan & global hanya peran lintas-PT; UI Pusat Pengaturan menonaktifkan Global bila tidak berwenang.
- CX-10: e-sign terikat hash isi kanonik (hash_version=2, doc_snapshot); PDF versi baru tidak membawa TTD lama; halaman verifikasi menampilkan status versi (current/superseded/legacy_unbound).
- P02: WM-01 (split atomik + retry nomor potongan), AX-07, AX-05, FN-03, IX-13, GN-12, GN-13 dipatch; WM-02 & GN-15 open.
- PG01 + IX-15: rencana QC Cek semua/Sampling + cakupan tercatat + keputusan wajib seluruh qty; UI QcPlanPanel.
- Bukti: audit/iterations/2026-10-01-*; testing agent iter109 100%.
- Next: isi SHA sesi ini → ready_for_validation; WM-02 (reservasi tanpa split fisik); P03 posting kas/AR/bank; sisa P06 (AX-08, WM-03..05, WM-09, IX-09).

## SESI 2026-10-02 — Lanjutan repo pandeyoga/KNHOST: WM-02 + P03 + sisa P06
Permintaan: lanjutkan (a) WM-02 reservasi tanpa potong, (b) fase P03 durable posting, (c) sisa P06 receiving; update tracker/iterations format sama.
Dikerjakan (bukti `audit/iterations/2026-10-02-*`, semua `in_progress` menunggu SHA; item sesi 2026-10-01 → `ready_for_validation` @49b1770):
- WM-02: reservasi PANJANG di roll induk (`length_reservations`), roll anak lahir saat `POST /api/inventory/rolls/{id}/reservations/{rid}/cut`; `GET /api/inventory/pending-cuts`; dispatch auto-cut `at_dispatch`; loading check menolak sebelum potong; tab UI "Antrean Potong" (`lp-tab-cuts`).
- P03: validator jurnal pusat (FN-15), preflight periode, `gl_status` terlihat (kas/kwitansi/retur/GR), repost kwitansi, void kas ber-pembalik, saldo awal rekening berjurnal, aset terkunci setelah kapitalisasi, store credit Σ alokasi + kompensasi, pencairan PD idempoten, 1 LPJ/PD, bank recon validator + kapasitas atomik, seq cicilan immutable, GRN/retur tidak final saat jurnal gagal, surat jalan ditulis sebelum task dispatched.
- P06: PA hanya roll available + klaim per roll (`active_movement`), dispatch → in_transit_transfer, scan kosong = nol tiba, override manual beralasan (izin wms.approve, tombol `pa-confirm-manual-<id>`), mutasi transfer untuk accept exception, reopen inspeksi mengosongkan `inspect_done_at` retur.
Tes: repro 66/66, testing agent iter 110 100%, E8 desk POC 97/97, allocation+reallocate 8 pass, integrity gate 246/0.
Backlog: GN-15; gate PA/loading RFID wajib tag anak (P07/P09); CX-05 akun reimburse kelebihan LPJ (keputusan pemilik); picker roll tampilkan panjang bebas; fase P04/P05/P07.

## SESI 2026-10-03 — Tag roll anak, picker panjang bebas, Panel Posting Gagal, P04 Costing, CX-05
- WM-02 lanjutan: dispatch & loading check 409 bila reservasi potong belum dikonfirmasi / roll anak belum ber-tag+terverifikasi (auto-cut dispatch dihapus); complete_verify RFID mengesahkan identitas anak; picker menampilkan panjang bebas; beli-per-roll sebagian = reservasi panjang; Ganti Roll melepas reservasi potong yang tak dipilih.
- CX-05 (keputusan pemilik): kelebihan LPJ → 2-1650 Hutang Reimburse Karyawan; 1 LPJ per PD.
- Panel Posting Gagal: GET /api/finance/posting-failures + retry; menu Keuangan → Posting Gagal.
- P04: FN-01 landed cost tanpa hitung ganda, FN-02 3-way match akumulasi + tolak baris ganda, FN-11 snapshot biaya roll di surat jalan, IX-16 retur beli satu nilai gross.
- Tes: repro 2026-10-03 20/20, repro 2026-10-02 66/66, testing agent iter 111 100%, integritas 248/0.
- Backlog: FN-02 per PO line ID + klaim atomik tagihan bersamaan; verifikasi identitas manual (label) selain RFID; alur bayar Hutang Reimburse; GN-15; fase P05/P07/P09.

## SESI 2026-10-04 — Verifikasi label, bayar Hutang Reimburse, match per baris PO, lencana Posting Gagal
- WM-02: POST /api/inventory/rolls/{id}/verify-identity (scan label = no. roll) + GET /api/inventory/cut-children-unverified; UI di tab Antrean Potong.
- CX-05: LPJ menyimpan hutang_reimburse; POST /api/cash-advance-settlements/{id}/pay-reimburse (Dr 2-1650 / Cr Kas, idempotent); tombol di detail LPJ.
- FN-02: tagihan supplier per baris PO (po_line_code/line_code), klaim PO saat create/submit → tagihan bersamaan tidak melebihi diterima.
- Lencana: GET /api/finance/posting-failures/count; badge di grup Keuangan & item Posting Gagal.
- Tes: repro 12/12, testing agent iter 112 100%, UI lencana dicek manual, integritas 248/0.

## SESI 2026-10-05 — P05 (COA/laporan/close), koreksi FN-02, label anak, pilih baris PO, Hutang Reimburse
- P05: CX-09 (perimeter eliminasi + laporan baca murni), FN-04 (arus kas per jurnal kas + pengungkapan nonkas), FN-05/FN-06 (resolver COA efektif per entitas di laporan, jurnal manual & autopost), FN-09 (void ikut penjaga periode), FN-13 (kunci close per entitas), FN-16 (as_of default = hari ini), IX-08 (CAS approve/reject → 409). Bukti `audit/iterations/2026-10-05-P05-coa-reports-close/` (HEAD 11/29 → 29/29).
- FN-02 dikoreksi: `items[].line_code` = LINI produk, bukan id baris → kunci baru `line_id`/`po_line_id` (ensure_line_ids), juga di kontrabon.
- Fitur: cetak label roll anak QR + Code128 (jsbarcode) di Antrean Potong; form tagihan menampilkan Baris #n, lini, harga PO, sisa per baris; tab Kas & Petty Cash → Hutang Reimburse (0–7/8–14/15–30/>30 hari, admin/manager).
- Tracker: FN-02 + 8 ID P05 ready_for_validation @6240190; WM-02, CX-05 @1a2c33a. Agen uji iterasi 113: API 10/10, UI struktural.
- Backlog: P07 (9 ID needs_revalidation), approve tagihan per-PO, reversal periode berjalan (kebijakan), review akuntan FN-04.

## SESI 2026-10-06 — P07 (sebagian) + Jurnal Pembalik (kebijakan PG02)
- Jurnal pembalik: POST /api/gl/journal/{id}/reverse {date, reason}; tanggal pilihan user wajib periode terbuka, izin accounting.void, alasan wajib, manual + otomatis, satu pembalik per jurnal; tombol "Balik Jurnal" di detail jurnal Buku Besar. Kebijakan dicatat di audit/policy-decisions.json (PG02).
- P07: WM-06 (validasi roll & qty scan-pick), AX-03 (dispatch baca ulang progres sesudah klaim), AX-01 (kirim roll yang dipindai), RF-05 (roll tanpa tag wajib scan label agar clean), CX-11 (nilai retur FIFO per baris SO). Bukti iterations/2026-10-06-P07-dispatch-identity-reversal (HEAD 4/10 → 18/18). ready_for_validation @1ea1dd8.
- Tertunda: CX-12, GN-11, RF-04, RF-06. Kebijakan terbuka: wajib scan per roll saat pick (saat ini opsional), override loading check berizin, undo pick.

## SESI 2026-10-07/08 — Sisa P07 (CX-12, GN-11, RF-04, RF-06) + P08 Tag, printer & typed verification
- Repo di-clone ulang dari GitHub (restore_env: pip/yarn/mongo/bootstrap/seed/build OK). backend/.env: CORS_ORIGINS eksplisit (URL preview + localhost:3000).
- P07 sisa: iterasi 115 lulus (API 19/19, UI Kunci Saga) → tracker ready_for_validation @cc74485. UI RF-04 dicek: kebijakan gudang `wh-lc-policy-*` tersimpan; LoadingCheckPanel label roll tanpa tag, override (amber), hasil simulasi diblokir.
- P08: RF-01 EPC kanonik 24 hex (services/epc.py, migrasi + indeks unik `uniq_live_epc`); RF-11 ZPL ^FH escape + EPC tanpa potong; RF-10 sesi wajib kind + scan $addToSet atomik, scan terlambat ditolak, 404 sesi tak dikenal; RF-07 scan `source` manual|simulated|device + scan_log, hasil `simulated` tidak membuka dispatch/journey; RF-14 tag `pending_print` → aktif saat cetak diakui, verifikasi bermasalah dapat diulang, rollback tag bila job gagal; RF-15 lease printer (attempt_id, TTL 300 dtk), ack wajib pemilik; IX-12 kompensasi attach (retire tag dulu) + sapu tag yatim; UX-02 unduh ZPL via apiClient blob.
- Bukti: audit/iterations/2026-10-08-P08-tag-printer-verify (HEAD 4/28 → 43/43); agen uji iterasi 116 API 18/18 + UI panel RFID. Tracker 8 ID P08 ready_for_validation.
- Catatan integrasi: middleware printer wajib kirim `attempt_id` saat ack (dari GET /api/rfid/device-jobs/pending); handheld dapat setor sweep ke sesi lewat POST /api/rfid/ingest {epcs, session_id}.
- Backlog: P09 (gate edge contract, evaluator, kiosk — 4 ID), P10 (count/opname), P11, P12, P13; kebijakan terbuka: wajib scan device (bukan manual) per gudang, hasil write-readback per label.

## SESI 2026-10-08 (lanjutan) — P09 Gate + status klaim printer + riwayat scan loading check
- P09: satu evaluator gate `services/gate_evaluator.py` (ingest perangkat, simulator, kiosk) berbasis movement aktif (PA in_transit / transfer dispatched / surat jalan SO memuat roll) dengan kode alasan; keluar ulang = REPLAY_EXIT (RF-02); IN hanya di gudang tujuan movement aktif, transit tanpa dokumen merah (RF-03); ingest events {epc,event_id,...} idempoten, dwell 120 dtk, batas 500 → 413, passage red-dominant (RF-16); `GET /api/rfid/gate/{id}/status` + `POST /api/rfid/passages/{id}/acknowledge`, kiosk `GateLiveVerdict` (TIDAK TERHUBUNG / GATE OFFLINE — TAHAN, alarm terkunci sampai diakui), reads difilter server `read_type=gate` + cursor (UX-01).
- Fitur: badge klaim printer + hitung mundur di panel Cetak & Verifikasi; "Riwayat scan" (sumber/pelaku/perangkat/jumlah/waktu) di LoadingCheckPanel.
- Bukti: audit/iterations/2026-10-08-P09-gate-contract (HEAD 3/22 → 22/22); agen uji iterasi 117 API 18/18 + UI gate; badge klaim & riwayat scan dicek lewat screenshot dengan data sintetis. Tracker 4 ID P09 ready_for_validation.
- Backlog: P10 (count/opname & adjustment), P11, P12, P13, P14; middleware perlu kirim event_id & attempt_id.

## SESI 2026-10-08 (akhir) — P10 Opname + fitur gate/printer
- P10: WM-07 (expected per bin, count key unik, actual ≥0 finite), WM-08 (potong CAS semua bucket fisik, adjustment per baris, approved_with_exceptions), FN-14 (jurnal selisih 5-9500/4-9000, WAC surplus, zero_cost_reason), RF-17 (cycle count RFID metrik coverage/recall/extra). Fitur: saran tindakan satpam per kode gate, peringatan klaim printer (≤60 dtk, ulang >2×), riwayat passage gate + pengakuan alarm. Agen uji iterasi 118 lulus 100%. Tracker 4 ID ready_for_validation.

## SESI 2026-10-02 — P11 Mutasi alternatif & konversi dokumen
- Problem statement (asli): "saya ingin anda lanjutkan development dari repo ini https://github.com/pandeyoga/KNHOST ... sebelumnya development terhenti disini saya ingin anda lanjutkan" → pilihan user: selesaikan P10 lalu lanjutkan yang belum dikerjakan (P11 dan lainnya).
- Repo di-restore ulang dari GitHub (HEAD 5cddfc9; .env dipertahankan, CORS_ORIGINS eksplisit + SESSION_COOKIE_SECURE, seed, build FE).
- GN-06/IX-11 produksi: resep BOM dibekukan di WO, draft wajib dirilis (default teknis), klaim WO + CAS panjang bebas, bahan tertahan QC & panjang dipesan tidak dikonsumsi, kompensasi per operation_id, tahap durable (resume tanpa konsumsi ganda). UI: tombol Selesaikan hanya untuk WO dirilis; galat 409 tampil sebagai teks.
- GN-05: rollback bahan sample R&D `$inc` idempoten (tidak menimpa pemakaian lain).
- GN-07 retur beli: satu jalur konsumsi (owner/produk/status, konversi UoM, CAS), retur sebagian = roll anak returned_supplier beridentitas sendiri, finalisasi diklaim.
- GN-08: convert permintaan internal diklaim + kunci logis source_request_id (retry pakai pasangan lama); reject/cancel ber-CAS.
- CX-13 makloon receive: klaim terikat step issued + snapshot hasil klaim, receive_progress durable, tulisan akhir milik token; input 0 tanpa receipt sah → 409.
- Bukti: audit/iterations/2026-10-02-P11-mutasi-konversi (HEAD 3/15 → 21/21); agen uji iterasi 119 lulus 100% (repro P11 21/21, regresi P10 21/21, HTTP 10/10, UI produksi). Tracker 6 ID ready_for_validation.
- Kebijakan terbuka: override rework bahan tertahan QC (hak/alasan/qty), draft WO wajib rilis, yield/waste aktual produksi, cetak tag RFID untuk roll anak retur.
- Backlog: P12 (payroll, HR, marketing), P13 (audit trail, kandidat secret, label ringan), P14 (coverage/UAT/sign-off); validator independen untuk ID ready_for_validation P05–P11.

## SESI 2026-10-02 (lanjutan) — P12 Payroll, HR & marketing
- Permintaan user: "Fase P12 Payroll: Lanjutkan P12 supaya perhitungan payroll, data HR, dan marketing tercatat benar dan aman"; "Izin Rework QC" DIBATALKAN user ("batalkan izin rework kerjakan faase p12").
- HR-02/IX-04 lembur: satu event per tanggal (pengajuan approved mengesahkan, absensi hanya bila approved), tier PP 35/2021 (hari kerja 1,5×/2×; istirahat/libur 2×/3×/4×, jadwal 5/6 hari), snapshot overtime_events di slip.
- HR-01 PPh21: bruto pajak + premi JKK/JKM/Kes pemberi kerja; masa terakhir (Desember / bulan berhenti) = PPh setahun Pasal 17 − potongan sebelumnya, lebih potong dikembalikan (jurnal mendebit Hutang PPh 21); karyawan berhenti ikut payroll bulan terakhir.
- IX-03 shift malam lintas tengah malam benar (22–06 = 480 mnt, lembur 0).
- IX-01/HR-03 cuti: override 0 bertahan, jatah negatif 400; reservasi pending atomik per tahun, tanggal bertabrakan ditolak, approve cek ulang saldo, cuti lintas tahun dibagi per tahun, cancel hanya menghapus absensi miliknya.
- MK-01 metrik marketing: update per field (tidak menghapus field lain), riwayat menyimpan snapshot penuh.
- Bukti: audit/iterations/2026-10-02-P12-payroll-hr-marketing (HEAD 4/22 → 23/23); agen uji iterasi 120 lulus 100% (API 11/11, UI 5 layar) + perbaikan router entitlement → 400. Tracker 7 ID ready_for_validation.
- Kebijakan terbuka: validasi akuntan fixture PPh21; basis upah lembur (gaji pokok vs + tunjangan tetap); TER pegawai tidak tetap/bonus/THR; kalender libur nasional untuk cuti & lembur; adjustment pasca-posting payroll.
- Backlog: P13 (audit trail, kandidat secret, label ringan), P14 (coverage/UAT/sign-off).

## SESI 2026-10-02 (lanjutan 2) — P13 Audit trail, secret & label
- Permintaan user: "Fase P13 Audit: Lanjutkan P13 untuk memastikan jejak perubahan dan keamanan aplikasi."
- GN-14: audit() kini menyimpan before/after/diff, actor_id, source, content_hash dan meredaksi kunci rahasia; endpoint keuangan/konfigurasi (akun GL, void jurnal, rekening bank, settings, syarat bayar, HR settings/karyawan, pelanggan, HPP stok awal) mengirim nilai sebelum. File token sesi (.tok, .tok_admin, .tok_mgr, memory/.tok_admin) dihapus + .gitignore; guardrail scripts/guardrails/verify_no_secrets.py (0 temuan).
- UX-03: panel biaya OCR menampilkan nama badan usaha (fallback "Badan usaha tidak dikenal").
- Bukti: audit/iterations/2026-10-02-P13-audit-secret-label (HEAD 0/7 → 10/10); agen uji iterasi 121 lulus 100% (API 16/16, UI UX-03). Tracker 2 ID ready_for_validation.
- Tindakan pemilik: bersihkan riwayat git publik dari file token + invalidasi sesi di semua lingkungan; putuskan apakah perubahan gaji (base_salary, kini PII) dicatat before/after di audit; pasang pemindai secret di CI/pre-commit.
- Backlog: P14 (coverage/UAT/sign-off); validator independen untuk ID ready_for_validation P05–P13.

## SESI 2026-10-02 (lanjutan 3) — P14 Coverage/UAT/sign-off + Riwayat Perubahan
- Permintaan user: "Fase P14 Sign-off: Melanjutkan P14 agar cakupan uji dan persetujuan akhir audit lengkap." + "Riwayat Audit Layar: Menambahkan tab riwayat perubahan pada detail akun GL dan pelanggan agar perubahan nilai lama dan baru lebih jelas terlihat."
- Pilihan user: kerjakan keduanya; base_salary dicatat sebagai field berubah dengan nilai [REDACTED]; pemindai secret di pre-commit + GitHub Actions; tab riwayat mengikuti izin audit.view; repo di-clone dari GitHub.
- Setup ulang kontainer: rsync repo → /app, backend/.env (CORS_ORIGINS eksplisit, SESSION_COOKIE_SECURE, KN_DEMO_DATA, SEED_DEMO_ENABLED, OCR_ALLOW_MOCK), seed_realistic, rebuild bundle.
- Baru: GET /api/audit-logs/resource (diff, integrity ok/mismatch/unsigned, lapisan override), AuditHistoryPanel; tab Riwayat Perubahan di detail Bagan Akun (coa-detail-<kode>) & Pelanggan 360; audit(masked_fields) untuk PII karyawan; .github/workflows/secret-scan.yml; hook pre-commit memblokir secret.
- P14: run_p14.py menjalankan ulang 24 harness P01–P14 (semua hijau; drift RF-09 & cookie Secure didokumentasikan) dan memetakan ke coverage.json: 22 tested_pass, 44 partial, 31 planned, 2 blocked (99 kasus = 96 + AUDIT-01..03). UAT.md + SIGNOFF.md (belum dapat ditandatangani; 5 exception menunggu pemilik). Agen uji iterasi 122 lulus 100%.
- Backlog P0: validator independen untuk 101 ID ready_for_validation; UAT pengguna bisnis; dataset acuan O2C/P2P/R2R/payroll. P1: kasus planned (31); akun demo hr.view tanpa view_pii; tab riwayat untuk entitas lain (supplier, produk, rekening bank). P2: tautan arsip *.log/*.lock yang hilang; GN-15 (SSOT helper/status).

## SESI 2026-10-02 (lanjutan 4) — Uji kasus tersisa + Riwayat entitas lain
- Permintaan user: "Uji Kasus Tersisa: Tambahkan uji untuk 31 kasus yang belum diuji, dimulai dari POS, retur supplier, dan alur desain" + "Riwayat Entitas Lain: Tambahkan tab Riwayat Perubahan yang sama di detail supplier, produk, dan rekening bank".
- Baru: tab Riwayat Perubahan di Supplier 360, Master Produk (per varian), Kas & Bank; supplier/produk kini mencatat nilai sebelum (produk hanya field berubah).
- repro_p14b_cases.py: PRET-04 & AUTH-03 lulus; DESIGN-01/03/04 partial; SALE-02 tested_fail (POS tanpa shift/void/split tender); AUTH-05 tested_fail (lost update PUT /permissions). UAT iteration_123: 7 kasus UI partial/pass.
- Coverage: 24 tested_pass, 54 partial, 17 planned, 2 tested_fail, 2 blocked.
- Backlog P0: putuskan & perbaiki AUTH-05 (versi/ETag matriks izin); keputusan fitur POS shift/void/split tender. P1: 17 kasus planned tersisa.



## SESI 2026-10-02 (lanjutan 5) — GN-15 + AUTH-05 (label iterasi "P15")
- Permintaan user: "lanjutkan gn-15 dan yang belum diselesaikan".
- GN-15: resolver kebijakan tunggal `config_resolver.policy_settings` (lot/makloon/receiving/uom), definisi stok fisik analitik diturunkan dari roll_service (kini termasuk wip). repro_gn15 21/21. Tracker: 102 ready_for_validation, 1 duplicate, 0 open.
- AUTH-05: GET/PUT /permissions ber-versi (stale 409, tanpa versi 400), frontend mengirim versi. Coverage AUTH-05 tested_pass.
- Regresi 26 harness hijau (kecuali SALE-02 = gap fitur POS). Agen uji iterasi 124 lulus 100%.
- Sisa: SALE-02 fitur kasir POS (keputusan pemilik), 17 kasus planned, validator independen, pembersihan riwayat git.
- 2026-10-02: SALE-02 (kasir POS) ditandai not_applicable atas keputusan pemilik (PG-SALE02 di audit/policy-decisions.json): semua penjualan lewat Sales Order. validate.py menerima status not_applicable dengan alasan wajib; repro_p14b memverifikasi premisnya (23/23). Coverage: 25 tested_pass, 54 partial, 17 planned, 2 blocked, 1 not_applicable, 0 tested_fail.



## SESI 2026-10-09 — P16 Tutup cakupan (transfer, penjualan → faktur, desain)
- Permintaan user: "lanjutkan uji hingga semua selesai" (lanjutan iterasi yang terhenti sebelum uji dijalankan).
- Setup ulang kontainer dari GitHub (repo belum memuat P16 lama → dikerjakan ulang): rsync → /app, backend/.env (CORS_ORIGINS, SESSION_COOKIE_SECURE, KN_DEMO_DATA, SEED_DEMO_ENABLED, OCR_ALLOW_MOCK), pip (tanpa litellm konflik), seed_realistic, rebuild bundle.
- Perbaikan: (1) /transfers/{id}/status hanya transisi operasional; approve/reject/cancel lewat endpoint khusus (400). (2) transfer antar-PT kini tersimpan (dulu roll bocor tertahan). (3) batal SO ditolak 409 bila Faktur Pajak aktif. (4) jalur lama design-gallery submit/reject/approve diteruskan ke siklus Studio (desainer tak bisa ACC sendiri, nilai wajib).
- Bukti: audit/iterations/2026-10-09-P16-close-coverage (HEAD 24/35 → 43/43); agen uji iterasi 125 lulus 100% (API + UI Manajemen Transfer). Coverage: 30 tested_pass (INV-02, SALE-01, SALE-03, DESIGN-01, DESIGN-03 naik), 49 partial, 17 planned, 2 blocked, 1 not_applicable.
- Sisa: INV-04 rekonsiliasi dua buku saat approve; 17 kasus planned; FAIL integritas seed KANDA/SO-00001; keputusan faktur per surat jalan vs per pesanan.
- 2026-10-09 (git): penyebab perubahan sesi lama tidak terbawa ke GitHub = riwayat git job bercabang dari "Initial commit" (tidak menurunkan GitHub main) → push bukan fast-forward. Riwayat kini ditumpuk di atas GitHub main `aa52c8c` (commit P16 tunggal). WAJIB sebelum Save to GitHub / akhir sesi: `bash scripts/git_sync_check.sh` (pakai `--fix` bila belum commit / bercabang). yarn.lock & .emergent/cron di-.gitignore.
- 2026-10-09 (putaran 2): kasus planned diuji — AUTH-04, GRN-02/03, COMM-03, QC-05 tested_pass; MASTER-01/05, DOC-02 partial. Bug diperbaiki: PO ke supplier nonaktif, harga khusus lingkup pesanan bocor ke SO lain/harga standing, lost update inspeksi bersamaan. Harness repro_p16b–f + run_all_p16.txt (74/74), agen uji iterasi 126 100%. Coverage: 35 tested_pass, 52 partial, 9 planned, 2 blocked, 1 n/a.


## SESI 2026-10-04 — Gelombang 2 (W2) P00–P07
- Permintaan user: "import catatan gelombang kedua ke repo… baca semua yang ada di zip, berikan analisis validasi dan kerjakan" (yang butuh info eksternal dilewati).
- Paket diimpor ke `docs/audit/wave-2/` (baseline utuh, check_package PASS). Rekonsiliasi P00 dengan Wave1: W2-008/009 sudah sebagian ditangani AX-04, W2-024 oleh GN-06, W2-021 (laporan keuangan) oleh GN-12, W2-016 precheck APAR-02 (non-atomik).
- Diperbaiki 25 temuan: scope owner opname/transfer (W2-006/008/009), reject opname CAS (007), scope raw read RFID (010), insiden RFID CAS + dedupe unik (011/012), GRN 501 roll (013), retur QC satuan PO (014), split berat (019), makloon costing/gudang/partial (001/002/003), batal tagihan jasa makloon (004), race potong bon vs bayar (005), produksi tanpa cap 5000 (024), AR deposit reklas/void/CAS/snapshot (015–018), refund tanpa buku kas (020), cap laporan & rekening (021), payroll buku kas & akun kas (022/023), guard lini R&D (025).
- Bukti: `docs/audit/wave-2/iterations/2026-10-04-W2-P00-P07/` — regression 25/25, HTTP 6/6, agen uji iterasi 140 (8/8 + UI). Tracker W2: 25 ready_for_validation. Integritas PASS 246 · FAIL 2 (seed lama).
- 2026-10-04: Keputusan pemilik W2-REQ-01..09 sudah ditetapkan → `docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md` (REQ-03=warn saja, REQ-05=tetap entitas aktif+ganti cepat, REQ-07=reservasi sejak keputusan fulfillment/PR).
- Belum: implementasi P08 W2-REQ-01..09 sesuai DECISIONS.md, COMM-04, migrasi data historis terdampak, commit (`git_sync_check.sh --fix`). Handoff: `memory/HANDOFF_P23_NEXT.md`.


## SESI 2026-10-04 (lanjutan) — Stok Makloon Aman · IA menu · penyeragaman UI · R3
- Permintaan user: "Uji Ulang Pembulatan" (lembar pembulatan roll sales + contoh selisih PO), "Stok Makloon Aman" (alokasi sales menghitung bahan cadangan makloon), analisis menu/tab dobel + perbaiki IA, perbaiki UI semua halaman (pop-up tumpang tindih, kolom tabel, paginasi). Keputusan: cadangan berlaku sejak PR makloon disetujui; perilaku dapat dikonfigurasi, bawaan blokir.
- Backend: `roll_service.makloon_guard` — reservasi `material_reservations` aktif dikurangkan dari stok bebas (SO mode qty & roll, ATP `build_supply_index`). Setting `allocation.makloon_reserve_mode` block|approve (Pusat Pengaturan). Mode approve → 409 MAKLOON_RESERVED_APPROVAL → kirim ulang `confirm_makloon_override` → approval SO tipe `makloon` (manajer), memblokir approve SO sampai diputus. Backorder service tetap menghormati cadangan.
- preview-roll-reconcile: permintaan all_entities dari peran non-lintas-entitas diturunkan ke entitas sendiri (dulu 403 → lembar pembulatan sales gagal).
- IA: grup baru "Akuntansi & Pajak" (dipisah dari Keuangan 12→7+6); "Pusat Cetak" jadi tab di Pusat Dokumen; "Analitik Stok" pindah ke hub Analitik; entri "Segera Hadir" ganda dihapus. Tidak ada view/tab dobel (dicek skrip).
- UI: tumpukan pop-up dinamis (`utils/overlayStack.js`, pop-up terakhir selalu di atas; dropdown Radix di atas semua pop-up), kepala/kaki sticky `.modal-card` menempel tepi kartu, isi pop-up tidak meluber, gaya tabel global seragam (header, padding, perataan angka, tfoot), paginasi 25 baris (`components/PagedRows.jsx`, `hooks/usePagedRows.js`) di 19 tabel daftar + papan Stok Multi-Bucket, tab bar HP satu baris, badge notifikasi HP.
- Tes: pytest R3 `tests/test_iter265_r3r4r5.py` diperbaiki (ID device/SO dinamis, attempt_id ack) → 28 pass 6 skip; regression P08 36/36; agen uji iterasi 143. Data uji: `scripts/seed_test_po_variance.py` (+ --clear).
- Backlog: penyeragaman visual lanjutan per layar (kartu KPI, header halaman) bila ada temuan spesifik; uji roll-mode SO terblokir cadangan makloon lewat UI.


## SESI 2026-10-04 (lanjutan 2) — Audit IA menyeluruh + konsolidasi + label makloon kasir
- Permintaan user: analisis mendalam semua halaman/tab/sub-tab, grouping sesuai domain, TIDAK ADA fitur terhapus, lapor sebelum eksekusi; lalu "eksekusi sesuai rekomendasi"; plus cek konsistensi CSS semua halaman/pop-up/tombol.
- Audit: `scripts/audit_ia.py` (inventaris statis 406→464 tab, endpoint tulis lintas layar) + crawl browser 132 halaman (`docs/audit/ia/crawl_all.json`), laporan `docs/audit/ia/IA_AUDIT_2026-10-04.md` (referensi SAP Fiori Spaces/Pages & Odoo Configuration). Kembar identik: tidak ada; 14 tumpang tindih, 8 sebaran fungsi, 5 salah domain.
- Eksekusi: grup Meja Peran (admin), RFID jadi hub di Gudang, Eskalasi Gudang ke Gudang, Antar Entitas ke Akuntansi & Pajak, Dasbor Keuangan hub (+BI Keuangan), Pengaturan 3 seksi (HubTabs `section`), tab Matriks Izin / Template Dokumen Dasar / Integrasi & Audit, CRM tab Impor/Ekspor & Status, Inbox kategori Kredit Pelanggan (GET /api/credit-overrides/{id}), tautan editor lengkap di Master per BU, penamaan ulang (Pengajuan Harga Khusus, Riwayat Persetujuan PO, Antrean QC Kedatangan, Dokumen Inspeksi (INS), Terima Cepat (mode lama)), tautan Margin→Profitabilitas, Rekap PPN→SPT, Kas Kecil.
- Verifikasi tidak ada yang hilang: diff view menu vs commit 8470015 → hanya 2 placeholder "Segera Hadir" (sudah dari sesi sebelumnya); semua view lama tetap ada + 4 view baru.
- Kasir: `material_reservation_service.apply_to_products` dipakai /api/products & /api/dashboard → `makloon_reserved_qty` + stok bebas dikurangi; label `product-makloon-reserved-<id>`.
- CSS: `scripts/audit_css.py` (536 kelas kustom, 15 tanpa gaya → .pill, .ghost-button, .cfg-impact-result ditambah; sisanya prefix template), baseline tombol/isian global, pita status bilah atas tidak menabrak.
- Agen uji iterasi 145: semua IA lolos; bug label makloon kasir (dashboard) diperbaiki → retest.


## SESI 2026-10-04 (lanjutan 3) — Audit angka/kartu + form tersisa + menu per peran
- Audit angka (agen uji 147/148, pembanding pymongo independen): diperbaiki → Beranda admin/manager & papan peringkat kini ter-scope badan usaha aktif (`routers/home.py _scope_entity`, `crm.py get_leaderboard`), `sales_kpi` memfilter SO per entitas + `compute_customer_credit(entity_id)` (AR = AR Aging 442.999.760,5), saldo kas = saldo awal rekening + masuk − keluar (`cash.py`), Beranda sales: target penagihan vs target penjualan (`_target_sales_for`, `_sales_target`), persen tertagih ×100 (SalesHome/AdminHome/MobileSalesHome), label "Capaian Target Penagihan".
- Bukan bug (terverifikasi): tagihan supplier "dibayar > total" (total_amount = DPP; grand_total incl PPN), ATP negatif = tersedia + masuk − permintaan tertunda.
- Form: lebar semua FormModal kembali sesuai ukuran (regresi CSS global `[role=dialog]` → `:where`), pesan "Pilih provinsi." baru muncul setelah alamat mulai diisi.
- Menu peran: warehouse & sales admin sesuai; akun md@/wh.admin@/sampleadmin@ tidak ada karena bootstrap hanya membuatnya bila KN_DEMO_DATA=true (menunggu keputusan user).

## SESI 2026-10-05 — Keluhan user: Kesehatan Konfigurasi merah + Riwayat Perubahan penuh TEST
- Kesehatan Konfigurasi: 2 setting "BELUM tersambung" sebenarnya tersambung; referensi kode di katalog basi → `config_catalog_ops.py` (receiving.auto_rfid_on_scan → receiving_roll_service) & `config_catalog_ai.py` (ai.route_threshold_pct → ai_chat_service). Health: OK 263 / NOT_USED 2.
- Pembersihan data uji: 18 config_values TEST + audit_logs, 5 retur TEST_R5 beserta roll/mutasi/store credit/jurnal/credit note (balance di-rebuild), lease "TEST Printer RFID" di 3 job cetak. `tests/test_iter265_r3r4r5.py` kini punya fixture pembersih otomatis.
- Pemindaian otomatis: 135 halaman + semua tab (teks NaN/undefined/TEST/error) → bersih; 38 pop-up "Buat/Tambah/Catat" dibuka (lebar, luber, tumpang tindih) → tidak ada masalah tata letak (temuan "select bawaan" = select tersembunyi Radix).
- Stok & ATP: rumus ditampilkan, kolom "tertahan" & "− tertunda" (`total_hold`, `total_pending_demand`) → Tersedia+Incoming−Tertunda = ATP & Tersedia+Dipesan+Tertahan = Stok Fisik (0 selisih di 20 produk).
- Tabel div-grid tanpa jarak kolom (≈60 layar, mis. "PPNPERIODE") → jarak kolom global 12px.


## 2026-10-05 — Skrip Data Demo Lengkap untuk VPS
Permintaan pengguna: "cek sebelumnya saya ada skrip migrasi ke vps berdasarkan master data asli, setelah cek saya ingin anda menambahkan skrip tambahan berupa semua data yang dibutuhkan untuk bisa menjalankan demo dengan seamless tampa harus menambahkan master data, misal pattern, warna, dll, buatkan juga semua akun role, buatkan semua stage bahan yang ada jadi system benar benar bisa di simulasikan, saya minta benar benar lengkap. lalu buatkan skripnya dan buatkan guide update vps saya di terminal vps"
Keputusan pengguna: transaksi contoh di tiap tahap = ya · sandi semua akun demo `demo1234` · 3 entitas (Cipta Sandang, Kanda, Sukacita) · gudang: Rancamalang (Transit, Woven, Knitting, Printing, Retur grade B/BS/C — shared) · Soreang (1 gudang Kanda) · Jakarta (1 gudang Sukacita).
- `backend/scripts/seed_demo_lengkap_kn.py` (master referensi, struktur gudang + pindah stok awal, 17 akun peran, supplier/makloon+kontrak/customer/rekening/target, produk & stok yarn→grey→PFD/PFP + remnant/byproduct + roll retur B/BS/C, true-up GL).
- `backend/scripts/seed_demo_transaksi_kn.py` (9 skenario via endpoint resmi: PR→PO→terima Transit→QC→tagihan→bayar 50%, transfer Transit→Woven, PO parsial, PO/PR menunggu, 7 SO berbagai status + AR, 4 SPK makloon, kas kecil). Idempoten per skenario (`migrations.demo_lengkap_transaksi`).
- `backend/scripts/demo_api.py` (klien ASGI dalam-proses), `deploy/setup_demo_lengkap.sh`, `deploy/DEMO_LENGKAP_VPS.md`; `import_stok_awal_kn.py` kini memilih gudang struktur baru bila ada.
- Diuji di DB simulasi VPS sementara (bootstrap + impor Excel + stok awal → kedua skrip → ulang = dilewati; 17 akun login OK; GL persediaan = subledger; jurnal seimbang). DB preview tidak disentuh; DB simulasi dihapus. Belum dijalankan di VPS nyata; UI belum diuji dengan data demo ini.



## 2026-10-05 — Perbaikan Audit UX A→B→C→D (disetujui pengguna)
Rincian: `memory/CHANGELOG_2026-10-05_ABCD.md`. Diuji testing agent (iteration_151): A/B/C/D lolos; temuan "Produk Terlaris masih per-entitas" & `entity_available_qty` di /api/products sudah diperbaiki (dicek curl). Belum teruji: peran warehouse_admin (akun tidak ada di DB preview).
Backlog: sisa temuan audit `docs/audit/ux-2026-10-05/LAPORAN_AUDIT_UX_2026-10-05.md` (daftar tanpa cari/paginasi di layar lain), setup demo VPS (ditunda pengguna).


## 2026-10-05 — Admin lewati persetujuan + Rencana Pemenuhan Admin Sales (disetujui pengguna: 1.a, 2.ya)
Rincian: `memory/CHANGELOG_2026-10-05_ABCD.md` (E, F). Testing agent iteration_152: endpoint & validasi rencana lolos, admin setujui PO sendiri lolos, manajer tetap diblok. BELUM teruji end-to-end: eksekusi sukses rencana (cadang stok / transfer / PR), checkout mode per roll lintas-entitas, dan situs SoD lain (vendor bill, landed cost, kontrabon, amandemen, buka periode, retur antar-PT).
Ditahan pengguna: sisa temuan audit UX; setup demo VPS.


## 2026-10-05 — Uji nyata pemenuhan (checkout → rencana) + pembersihan
- Lolos nyata: stok sendiri sebagian (KSC, JMP-PLB-001: cadang 50, backorder 90→40), transfer antar-PT (Kanda←Sukacita BTK-MEGA-001 150 → KANDA/IC-00005 + KSC/IC-00005 terkonfirmasi, jurnal kedua PT terbit), PR ke supplier (bertaut SO), keputusan "Sebagian/Penuh" tercatat.
- Temuan: transfer hanya bisa bila ada kontrak harga internal aktif per barang & pasangan PT (demo: hanya BTK-MEGA-001 KSC→Kanda). Bug diperbaiki: permintaan internal (PIN) yatim bila konversi gagal → kini otomatis dibatalkan (`fulfillment_decision_service._take_from_other_entity`).
- Semua data uji dihapus (11 SO, 8 pelanggan TEST_, 6 PR, 5 PIN, 2 transaksi antar-PT, 4 jurnal + pembalikannya, mutasi reservasi, notifikasi, audit). Saldo stok kembali: BTK 310, DNM 300, JMP 210.

