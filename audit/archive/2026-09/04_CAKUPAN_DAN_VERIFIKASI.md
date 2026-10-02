# Cakupan, metode, dan batas verifikasi

Snapshot [d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467](https://github.com/pandeyoga/KNHOST/commit/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467) diambil 28 September 2026. Laporan menilai kode snapshot, bukan kondisi server produksi saat ini.

## Ukuran dan register

- 1,857 berkas Python/JS/JSX/TS/TSX terinventarisasi di repo (termasuk scripts/tests), 1,205 pada backend/services, backend/routers dan frontend/src.
- 1,353 decorator endpoint pada backend/routers. Ini bukan hitungan unique mounted API: prefix router, alias dan kondisi registrasi belum digabungkan.
- 36 folder kelompok fitur frontend terinventarisasi; daftar berkas dan endpoint lengkap ada dalam [register](05_REGISTER_BERKAS_DAN_ENDPOINT.md).
- 54 berkas muncul sebagai bukti langsung pada 65 temuan. Jumlah ini bukan seluruh berkas yang dibaca, dan bukan berarti setiap fungsi pada berkas tersebut sudah diuji.

## Kedalaman yang sebenarnya

Audit menggabungkan inventaris seluruh sumber, parse syntax, lint terpilih, pencarian jalur mutation/scope/index, pembacaan flow berisiko dan hubungan router–service–UI, reproduksi fungsi asli terpilih, serta pembanding vendor/standar primer. Laporan audit lama pada repo dipakai sebagai petunjuk, bukan dianggap bukti bahwa bug sudah ditutup.

Tidak ada klaim bahwa seluruh lebih dari seribu endpoint telah dipanggil, setiap baris telah direview secara manual, atau seluruh menu sudah dicoba pengguna. Peta modul/flow dan register sumber hanya membuktikan cakupan inventaris; permintaan pemeriksaan mendalam seluruh kode/flow belum selesai. Status terperinci diperbarui dalam [14 — cakupan lanjutan](14_STATUS_CAKUPAN_DAN_SISA.md). Tidak adanya temuan baru bukan sertifikasi bebas bug.

## Peta modul/flow

| Modul/flow | Hasil terkait | Kedalaman dan batas |
|---|---|---|
| RFID, printer, gate, count, loading | RF-01–17; UX-01/02 | Telusur service/router/layar, sesi, expected/read/verify, lifecycle perangkat, simulasi dan dokumen gate. Reproduksi utama; hardware belum diuji. |
| WMS, roll, reservation, picking, putaway, opname | WM-01–09; GN-05/06/07/13 | Flow mutation roll, conservation quantity, movement, scope, ATP, count approval, ledger/projection dan recovery ditelusuri. Race dianalisis; belum stress test Mongo. |
| Finance/GL/AP/AR/cash/bank/assets/report/closing | FN-01–16; GN-03/12; HR-01/02 | Posting/lifecycle, COA, cashflow, valuation, periode dan matching ditelusuri dengan fixture terpilih. Belum rekonsiliasi buku produksi atau sertifikasi pajak. |
| Sales, SO, shipments, returns, credit/pricing | RF-04/06; FN-10/11; GN-07 | Relasi SO–manifest–dispatch–receipt–COGS dan return/consume diperiksa pada flow terkait. Varian diskon/tax/credit dan kanal penuh perlu integration fixture. |
| Purchase/PO/receiving/QC/landed cost/makloon | FN-01/02/03; WM-02/03/04; guardrail | Relasi receipt, UOM, split, cost dan PA diperiksa; guardrail mengungkap dua handler belum ditinjau. Seluruh varian makloon belum dieksekusi. |
| Manufacturing/BOM/work order | GN-06 | Consume/complete, frozen plan, status dan multi-material failure ditelusuri. Perencanaan kapasitas/yield/mesin tidak diuji di pabrik. |
| R&D/samples/design | GN-04/05 | Permission objek dan material issue/GL rollback ditelusuri; catalog/design gallery tercakup inventaris dan syntax. |
| Internal request/intercompany/consolidation | GN-08; FN-05 | Convert pasangan dokumen dan scope/COA ditinjau. Eliminasi multientity, transfer price dan konsolidasi penuh perlu fixture terpisah. |
| CRM/omnichannel/customer | GN-09 | Lead read/update/customer reference dan ownership ditelusuri. Integrasi channel eksternal/webhook delivery belum diuji. |
| POS | GN-10 | Product scope, roll stock selection/substitution dan izin dibaca. Tidak menjalankan terminal atau settlement pembayaran. |
| HR/attendance/leave/payroll/tracking | HR-01/02/03; GN-02 | Tax/overtime/leave lifecycle dan websocket tracking dibaca. Formula overtime direproduksi. Jadwal shift, biometrik, semua analytics belum diuji end-to-end. |
| Marketing | MK-01 | Partial update metrics ditelusuri; statistik/channel dan rendering tercakup inventaris/syntax. |
| Auth/entity/device/security | GN-01/02/03/04/09/10; RF-08/09/12/13 | Middleware replay, session, per-ID guards dan device auth ditelusuri. Bukan penetration test penuh atau verifikasi credential masih aktif. |
| Inventory rebuild/admin/recovery/audit | GN-11/12/13/14/15 | Locks, read/set snapshot, caps, audit data dan duplikasi helper dibaca. Keberadaan index dan data divergence deployed belum diverifikasi. |
| Dashboard/reports/settings/master data/integrations/notifications/onboarding/utilities | GN-16; UX-03; lint, syntax, inventaris | Audience laporan AI dan digest ditelusuri setelah guardrail; false positive label MobileMdApp ditolak lewat pembacaan source. Tidak semua callback/integrasi dan layar memiliki behavioral test; register membedakan kedalamannya. |

## Pemeriksaan yang dijalankan

- Parse AST Python pada seluruh berkas Python terinventarisasi: 0 syntax error. Parse tidak menjalankan import/dependency.
- Parse Babel frontend: 821 berkas, 0 syntax error. Ini bukan build, lint React atau browser runtime.
- Pyflakes 4.0.0: 551 berkas backend, 444 warning; tidak ditemukan UndefinedName. Sebagian berkas test pada root backend ikut dalam hitungan; warning unused import/redefinition bukan otomatis bug bisnis.
- Reproduksi terisolasi: 18 skenario fungsi AST asli dengan mock dependency; 16 menunjukkan perilaku cacat/gap, 2 kontrol pembanding. Semua ekspektasi fixture yang disusun berhasil diamati. Hasil ini bukan 18 integration tests Mongo.
- Pemeriksaan bawaan repo: percobaan menjalankan 34 script guardrail; hasil/skip/error dijelaskan di bawah. Exit nol yang berisi SKIP bukan bukti pemeriksaan runtime lulus.
- Tidak menjalankan full frontend build, pytest suite penuh, browser UX session, reader/printer commissioning, atau buku produksi. Dependensi/backend/Mongo yang diperlukan belum tersedia; mencoba runtime guardrail tidak menghasilkan validasi layanan deployed.

## Pemeriksaan bawaan dan status aktual

Beberapa script memiliki auto-install dependency atau membutuhkan backend/Mongo. Dua percobaan tidak menghasilkan log terselesaikan dalam sesi audit; keduanya ditandai tidak terverifikasi. Log yang selesai diperiksa isinya, bukan hanya exit code. Warning advisor statis dan skip DB dipisahkan dari hasil behavioral.

| Script | Status isi log | Cuplikan akhir nonrahasia |
|---|---|---|
| verify_aging_fields.py | Selesai dengan bagian SKIP; bukan lulus penuh | Gate error (dianggap SKIP): No module named 'motor' |
| verify_approval_queues.py | Selesai dengan bagian SKIP; bukan lulus penuh | Gate error (dianggap SKIP): No module named 'motor' |
| verify_atomic_claim.py | Perlu tinjau: ada kegagalan/violation/advisory | ✗ backend/routers/inbound_scan_label.py /inbound/rolls/{roll_id}/scan: dicatat 'cas' tetapi find_one_and_update induk tidak berprasyarat status. / ✗ BELUM DITINJAU = 2 > baseline 0. Endpoint multi-koleksi BARU wajib memakai atomic_claim.claim()/CAS dan dicatat di REVIEWED: goods_receipts.py POST /goods-receipts/{grn_id}/start-count; makloon_orders.py POST /makloon-orders/{mko_id}/steps/{seq}/partial-receipts/{grn_id}/cancel / → Perbaiki sesuai INVARIANT INV-ATOMIC-01 (detail: |
| verify_auth_coverage.py | Error/dependency; tidak lulus | return codecs.charmap_decode(input,self.errors,decoding_table)[0] / ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ / UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 2611: character maps to &lt;undefined> |
| verify_blocking_dialogs.py | Log selesai; hasil statis terbatas pada aturan script | dialog peramban ditemukan: 0 di 0 berkas (alert/confirm/prompt) · pengecualian terdaftar: 0 / == INV-UI-06 — dialog bawaan peramban (alert/confirm/prompt) dilarang == / [PASS] 1 cek lolos, 0 pelanggaran. |
| verify_codebase_map.py | Log selesai; hasil statis terbatas pada aturan script | == INV-DOC-01 — CODEBASE_MAP.md selaras kode (selisih ≤10%) == / [PASS] 5 cek lolos, 0 pelanggaran. |
| verify_concurrency.py | Error/dependency; tidak lulus | File "C:\Users\abc\Documents\Codex\2026-09-28\sya\work\KNHOST\scripts\guardrails\verify_concurrency.py", line 29, in &lt;module> / import requests / ModuleNotFoundError: No module named 'requests' |
| verify_cross_entity.py | Tidak terverifikasi: belum ada log selesai | Dependency/runtime diperlukan |
| verify_derived_fields.py | Log selesai; hasil statis terbatas pada aturan script | == INV-UI-04 — Field turunan dibaca dari sumbernya sendiri (bukan dari respons daftar) == / [PASS] 3 cek lolos, 0 pelanggaran. |
| verify_detail_modal.py | Log selesai; hasil statis terbatas pada aturan script | panel rincian diperiksa: 26 → pop-up 21 · berdampingan (2 kolom) 5 · INLINE (pelanggaran) 0 · pengecualian terdaftar: 0 / == INV-UI-08 — panel rincian wajib pop-up (bukan diselipkan di bawah daftar) == / [PASS] 26 cek lolos, 0 pelanggaran. |
| verify_doc_origin.py | Selesai dengan bagian SKIP; bukan lulus penuh | [SKIP] MONGO_URL tidak tersedia — hanya pemeriksaan statik. / == INV-ORIG-01 — Asal dokumen PO dari SATU definisi (pr_id · sales dirunut, tidak diketik · refs dua arah) == / [PASS] 6 cek lolos, 0 pelanggaran. |
| verify_entity_label.py | Perlu tinjau: ada kegagalan/violation/advisory | → Perbaiki dengan `entityShort/entityFull/entityShortById/entityFullById/entityOptions` dari `utils/entityLabel.js`. |
| verify_error_notice.py | Log selesai; hasil statis terbatas pada aturan script | utang teknis (baseline aturan C): 12 modal lama belum punya bilah error sendiri — lihat MODAL_BASELINE. / == INV-UI-03 — Kegagalan backend harus terlihat di layar (anti error senyap) == / [PASS] 276 cek lolos, 0 pelanggaran. |
| verify_escape_layers.py | Log selesai; hasil statis terbatas pada aturan script | berkas diperiksa: 814 · memakai useEscapeClose: 28 / == INV-UI-10 — Esc menutup lapisan TERATAS saja (satu tumpukan, bukan pendengar sendiri) == / [PASS] 814 cek lolos, 0 pelanggaran. |
| verify_home_kpi.py | Error/dependency; tidak lulus | import httpx  # noqa: E402 / ^^^^^^^^^^^^ / ModuleNotFoundError: No module named 'httpx' |
| verify_line_scope.py | Selesai dengan bagian SKIP; bukan lulus penuh | [SKIP] MONGO_URL tidak tersedia — hanya pemeriksaan statik. / == INV-LINE-01/02 — Pagar lini produk (kode dikenal · turunan jujur · snapshot lengkap · lini vs fisika kain) == / [PASS] 31 cek lolos, 0 pelanggaran. |
| verify_list_export.py | Error/dependency; tidak lulus | func(path, *args, follow_symlinks=False) / ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ / PermissionError: [WinError 5] Access is denied: 'C:\\Users\\abc\\AppData\\Local\\Temp\\tmplxy3ichf' |
| verify_master_stages.py | Selesai dengan bagian SKIP; bukan lulus penuh | [SKIP] MONGO_URL tidak tersedia — hanya pemeriksaan statik. / == INV-DOMAIN-06 — Master tahapan proses vs registry domain (tahap terpakai · process_type · stage · transisi · mitra · aliran kain) == / [PASS] 4 cek lolos, 0 pelanggaran. |
| verify_modal_dismiss.py | Log selesai; hasil statis terbatas pada aturan script | == INV-UI-01 — Backdrop modal & dropdown ber-portal (anti auto-close) == / [PASS] 24 cek lolos, 0 pelanggaran. |
| verify_nonfinancial_sweep.py | Tidak terverifikasi: belum ada log selesai | Dependency/runtime diperlukan |
| verify_notification_audience.py | Perlu tinjau: ada kegagalan/violation/advisory | - backend\services\ai_schedules.py:91: K2 `recipient_user` dikirim tanpa `recipient_role=""` — bawaan parameternya "all", jadi pesannya tetap tersiar. Tulis recipient_role="" secara eksplisit. / Peristiwa ber-pemilik: ar_due_soon, inspection_assigned, internal_request_decided, low_stock, order_approval, order_split, po_stage_stuck, reservation_expiring, special_order_approval |
| verify_numeric_bounds.py | Selesai dengan bagian SKIP; bukan lulus penuh | ================================================================ / Numeric-bounds aman untuk cakupan teruji (INV-NUM-01 tertutup). |
| verify_picker_portal.py | Log selesai; hasil statis terbatas pada aturan script | berkas diperiksa: 242 · komponen pemilih (pemicu+pop-up): 7 → components\MakloonSelect.jsx, components\PantoneFinder.jsx, components\ProductSelect.jsx, features\purchasing\contracts\ContractFormModal.jsx, features\purchasing\makloon\MakloonWizard.jsx, features\purchasing\MakloonOrderCreateModal.jsx, features\purchasing\RecipeFormModal.jsx / == INV-UI-09 — pemilih (pemicu+pop-up) wajib ber-portal · pop-up bukan anak &lt;label> == / [PASS] 242 cek lolos, 0 pelanggaran. |
| verify_po_board.py | Selesai dengan bagian SKIP; bukan lulus penuh | [SKIP] MONGO_URL tidak tersedia — hanya pemeriksaan statik. / == INV-STAGE-01 — Papan PO per lini (tahap dari master · `inspect` turunan · tanda tahap ber-jejak) == / [PASS] 7 cek lolos, 0 pelanggaran. |
| verify_qty_dual.py | Error/dependency; tidak lulus | func(path, *args, follow_symlinks=False) / ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ / PermissionError: [WinError 5] Access is denied: 'C:\\Users\\abc\\AppData\\Local\\Temp\\tmps8qabb3o' |
| verify_ref_unlink.py | Error/dependency; tidak lulus | File "C:\Users\abc\Documents\Codex\2026-09-28\sya\work\KNHOST\backend\core_utils.py", line 4, in &lt;module> / from pydantic import BeforeValidator / ModuleNotFoundError: No module named 'pydantic' |
| verify_rfid_tag_unique.py | Selesai dengan bagian SKIP; bukan lulus penuh | (Mongo tak terjangkau — lapisan DATA dilewati) / == INV-RFID-01 — satu tag RFID untuk satu roll aktif; potongan tidak mewarisi tag induk == / [PASS] 1 cek lolos, 0 pelanggaran. |
| verify_role_label.py | Error/dependency; tidak lulus | return codecs.charmap_decode(input,self.errors,decoding_table)[0] / ~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ / UnicodeDecodeError: 'charmap' codec can't decode byte 0x9d in position 13804: character maps to &lt;undefined> |
| verify_roll_identity.py | Selesai dengan bagian SKIP; bukan lulus penuh | ✓ 0 pelanggaran — satu nama (`roll_no`), satu pengalokasi, satu nomor per roll. |
| verify_sample_types.py | Selesai dengan bagian SKIP; bukan lulus penuh | [SKIP] MONGO_URL tidak tersedia — hanya pemeriksaan statik. / == INV-SAMPLE-01 — Master jenis sampling vs dokumen sample (jenis terpakai · satu sumber · round ber-jenis · hasil ukur dari master · wajib desain · urutan jadi→kirim · nomor unik) == / [PASS] 3 cek lolos, 0 pelanggaran. |
| verify_state_machine.py | Error/dependency; tidak lulus | File "C:\Users\abc\Documents\Codex\2026-09-28\sya\work\KNHOST\scripts\guardrails\verify_state_machine.py", line 37, in &lt;module> / import requests / ModuleNotFoundError: No module named 'requests' |
| verify_status_history.py | Log selesai; hasil statis terbatas pada aturan script | == INV-HIST-01 — `status_history` hanya boleh punya SATU bentuk == / [PASS] 7 cek lolos, 0 pelanggaran. |
| verify_to_list_bound.py | Perlu tinjau: ada kegagalan/violation/advisory | ✗ backend/services/gl_service.py to_list(50000) ada di ALLOWLIST tetapi tidak lagi di kode — hapus entrinya (ratchet). / ✗ backend/services/gl_service.py to_list(100000) ada di ALLOWLIST tetapi tidak lagi di kode — hapus entrinya (ratchet). / → Perbaiki sesuai INVARIANT INV-PERF-01 (detail: memory/INVARIANTS.md). |
| verify_uom_vocab.py | Selesai dengan bagian SKIP; bukan lulus penuh | Mongo tak terjangkau (No module named 'dotenv') — lapis DATA dilewati. / == INV-UOM-02 — kosakata satuan dokumen ⊆ master `uoms` (kode/nama/alias) == / [PASS] 814 cek lolos, 0 pelanggaran. |

INV-ATOMIC-01 secara eksplisit melaporkan 2 violation pada 108 check: handler inbound scan delete yang terdaftar CAS tidak ditemukan status CAS yang disyaratkan; serta dua handler belum ditinjau (goods receipt start-count dan makloon partial receipt cancel), dengan baseline unreviewed nol. Ini bukti gate repo belum seluruhnya hijau, tetapi advisory ini harus ditelusuri sebelum dijadikan klaim korupsi data. RFID tag uniqueness dan roll identity statis lolos, sedangkan bagian DB/index skip; index live masih belum terbukti.

Tinjau hasil guardrail sesuai platform: verify_to_list_bound mengeluarkan 21 violation, tetapi pencocokan allowlist memakai path slash yang tidak cocok dengan backslash Windows sehingga beberapa cap ditandai sekaligus sebagai tidak ada dan tidak diizinkan. Cap pada source tetap ada dan GN-12 menilai correctness-nya secara independen; angka 21 bukan 21 bug baru. verify_entity_label menandai MobileMdApp karena user.name berada satu baris dengan label entitas yang sebenarnya memakai helper: false positive ditolak. Raw entity_id pada panel OCR benar dan masuk UX-03. verify_blocking_dialogs melaporkan 0 berkas, jadi PASS-nya tidak membuktikan frontend bebas dialog blocking. verify_notification_audience mengungkap caller yang benar-benar masih memakai default all; GN-16 menelusuri filter aktual dan digest.

## Yang diperlukan untuk keputusan go-live

1. Mongo integration fixtures dua entitas, role terbatas, UOM meter/yard, partial roll/partial shipment, dan data di atas cap query.
2. Concurrency barriers, failure injection setiap tahap write, retry/restart, compensating action, serta invariant jumlah/nilai dan source dedup.
3. Reconciliation inventory layer→GL, cash account→GL, AR/AP→GL, landed voucher allocation, acquisition/depreciation register, locked period dan independent cashflow fixture.
4. Browser per persona operator/picker/finance/manager: selected entity, handheld focus, error/offline/retry, accessibility, pagination/filter dan action permissions.
5. Printer write/readback dan commissioning lane D/H dengan known-good/wrong-destination/unknown/duplicate/stray tag, passage mixed verdict, reader/network outage dan rack proximity.
6. Review pajak/payroll oleh pemilik kebijakan dengan effective date dan perhitungan independen. Audit code bukan pengesahan seluruh kepatuhan pajak.

Setiap item harus menghasilkan bukti hasil nyata. File test yang ada, dokumen “audit complete”, komentar SSOT dan dashboard seimbang tidak menggantikannya.
