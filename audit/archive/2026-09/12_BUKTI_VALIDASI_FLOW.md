# Bukti validasi lintas-flow — review Astra

Snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Dijalankan lokal pada review 28–29 September 2026. Clock di fixture sengaja tetap, tidak mewakili timestamp transaksi produksi.

## Apa yang benar-benar diuji

Badan fungsi diambil dari AST source snapshot, kemudian dieksekusi dengan dependensi terbatas. Model database mendukung projection, sort, query operator yang dipakai, conditional updates, dan perubahan field bertingkat. Operator yang tidak didukung menimbulkan error. Fungsi claim/finish/release yang dipakai berasal dari source, dengan database model yang sama. Barrier async mengatur urutan race secara deterministik; fault injection menolak insert shipment di titik tertentu.

Jumlah skenario: **22**. Semua assertion lulus. Jumlah ini mencakup kontrol positif dan koreksi temuan, **bukan jumlah bug independen**. Dua kontrol membuktikan bahwa implementasi dapat benar untuk jalur sequential split dan PA aktif ke gudang salah. Tidak ada aplikasi produksi atau perangkat pembaca yang diakses.

## Hasil per skenario

| Uji | Jenis | Hasil yang teramati | Makna dan batas |
|---|---|---|---|
| V2-01 | defect | `{"raw_result": "red", "stored_format_result": "info"}` | RF-01 survives full encode/ZPL/ingest chain in dependency model. |
| V2-02 | defect | `{"result": "green", "reason": "Keluar untuk putaway PA-1."}` | PA branch precedes QC block and ignores cancelled PA status. |
| V2-03 | defect | `{"before": "offline", "after": "online"}` | Actual UI Matikan uses offline; heartbeat silently turns it online. |
| V2-04 | defect | `{"untagged": 1, "result": "clean", "dispatch_allowed": true}` | RF-05: subset verification reaches dispatch guard as clean. |
| V2-05 | defect | `{"session_status": "completed", "roll_journey": {"stage": "tag_verified", "updated_at": "2026-09-28T12:00:00Z", "verify_session_id": "S"}, "cycle_count_reports": 0}` | RF-10: wrong completion endpoint consumes a cycle count as print verify and changes roll journey. |
| V2-06 | defect | `{"accepted_requests": 2, "stored": ["A"]}` | RF-10: concurrent union/read/set loses one accepted EPC. |
| V2-07 | defect | `{"start_qty": 100, "end_qty": 140.0, "lengths": [70.0, 40.0, 30.0]}` | WM-01 deterministic interleaving executes original stale normalization after CAS. |
| V2-08 | defect | `{"shipment_roll": "roll_9", "child_tag": null, "child_status": "in_transit_sales"}` | Dispatch can create untagged child after any loading verification; identity checked before dispatch no longer equals shipped identity. |
| V2-09 | defect | `{"pa_status": "open", "roll_status": "quarantine"}` | PA creation verifies tag journey/storage category but accepts QC quarantine. |
| V2-10 | defect | `{"scanned": [], "arrived_count": 1, "warehouse": "W2"}` | WM-03 empty list equals unrestricted arrival; original bulk function executed. |
| V2-11 | defect | `{"roll_owner": "B", "roll_qty": 70, "roll_warehouse": "W2", "movement_owner": "A", "movement_qty": 100}` | PA parent claim does not revalidate roll owner/source/status/quantity; stale document can move newer state. |
| V2-12 | defect | `{"warehouse": "W2", "bin": "BIN-W1", "acquired": {"via": "transfer", "ref_id": "TR", "date": "2026-09-28T12:00:00Z"}, "po_cost_selector_matches": false}` | Warehouse receipt overwrites procurement provenance and retains source bin. Late landed-cost PO selection misses transferred roll. |
| V2-13 | defect | `{"picked_roll": "NEW", "shipped_roll": "OLD"}` | Picked identity is not dispatch selection; dispatch uses qty/FEFO despite scan_log/roll_id. |
| V2-14 | defect | `{"task_status": "dispatched", "has_lock": false, "shipments": 0, "roll_statuses": ["in_transit_sales", "in_transit_sales"]}` | Failure after finish_set before shipment insert leaves dispatched task/transit rolls without shipment; no saga lock exposes recovery. |
| V2-15 | defect | `{"task_shipped_qty": 30.0, "shipment_sum": 60.0}` | Two requests with same pre-read task can both claim sequentially; partial status remains allowed, stale shipped_qty overwrites progress. |
| V2-16 | correction | `{"surplus_qty": 10.0, "unit_cost": 100.0}` | FN-14 zero-cost is conditional: surplus inherits product.harga_pokok=100, not always zero. Missing variance GL remains separate defect. |
| V2-17 | defect | `{"requested_owner": "A", "reserved_owner": "B", "rebuild_calls": 0}` | Explicit roll transfer path omits owner filter and returns before balance rebuild; original service executed. |
| V2-18 | defect | `{"job_owner": "A", "viewer_scope": ["A"], "visible_rolls": ["A-ROLL", "B-ROLL"]}` | Authorized multi-owner job creation stamps first owner; later A-only caller receives B-owned roll through get_print_job. |
| V2-19 | defect | `{"actual_immediate_parent": "CHILD", "stored_parent": "ROOT", "root": "ROOT"}` | Copied child carries its existing parent_roll_id; setdefault preserves grandparent for a new second-generation cut. |
| V2-20 | defect | `{"parent_first": 130, "child_first": 100}` | FN-01 is order-dependent: same voucher allocations produce total stock-cost uplift 130 or 100; not universally double in every order. |
| V2-C1 | control | `{"start_qty": 100, "end_qty": 100.0}` | Sequential split with fresh parent snapshots conserves quantity; V2-07 requires specified concurrency interleaving. |
| V2-C2 | control | `{"result": "red", "reason": "SALAH GUDANG — PA-1 menuju ?, bukan gudang ini."}` | Active PA IN branch does reject wrong destination; RF-03 concerns transit fallback, not every IN decision. |

## Cara membaca bukti tanpa melebihkan kesimpulan

1. V2-07 membuktikan interleaving yang menghasilkan 140 dari 100 pada badan fungsi; tidak mengukur frekuensi race di deployment nyata. V2-C1 membuktikan sequential normal tetap 100.
2. V2-11 memakai PA dengan snapshot lama dan roll yang telah berubah. Ini menguji tidak adanya precondition saat arrival; bukan simulasi lengkap semua proses yang menghasilkan perubahan owner tersebut.
3. V2-13 menyediakan dua roll committed SO sama, picked_qty 50, scan_log dan roll_id memilih NEW. Dispatch 50 memilih OLD berdasarkan urutan roll, bukan bukti pick. Tidak memakai scan quantity yang bertentangan untuk membangun kesimpulan ini.
4. V2-15 menjalankan dua invocation dengan task snapshot yang sama, seperti dua request telah membaca sebelum claim. Keduanya memperoleh claim bergantian. Ini tidak mengandalkan dua lock aktif bersamaan.
5. V2-17 memanggil service transfer secara langsung dengan owner A dan roll B. Telaah router menunjukkan owner hasil resolve diteruskan bersama roll_ids tanpa mencocokkan owner setiap roll; syarat realistisnya gudang sumber bersama dan owner A sah tersedia/terpilih.
6. V2-18 dimulai dengan creator yang sah melihat A+B, lalu caller A saja membaca job. Ini bukan eskalasi saat create; kebocoran muncul karena stamping owner parent tidak mencerminkan semua item.
7. V2-19 memodelkan child input yang menyalin parent, seperti _split_roll; parent_roll_id lama dipertahankan setdefault. Root benar tidak berarti direct parent benar.
8. V2-16 adalah counterexample yang membatalkan klaim surplus selalu zero-cost. Tidak membuktikan harga fallback selalu tepat bagi kebijakan akuntansi bisnis.
9. Reproduksi audit awal memakai fake database yang lebih sederhana. Jangan menganggap hasil lama mencakup projection, operator query dan interleaving Mongo sebenarnya. Review baru memperkuat kasus paling kritis; bukan mengubah semua reproduksi lama menjadi integration test.

## Belum diverifikasi

Mongo transaction/session/read concern, unique index yang benar-benar terpasang di deployment, autentikasi HTTP dan middleware pada server berjalan, visual/touch/focus/performance UI, queue middleware Kotlin, kemampuan printer melaksanakan ZPL, antena/tag/tunnel, koneksi terputus nyata, data historis serta saldo GL produksi. Tidak ditemukan runtime MongoDB/docker untuk menjalankan integration test lokal pada sesi ini.

Tidak ada klaim “seluruh test suite lulus”. Pemeriksaan syntax dan lint sebelumnya bukan bukti financial correctness. Beberapa guardrail awal tidak selesai karena bootstrap dependency; jangan memasukkan sebagai PASS. Rincian audit awal tetap tersedia pada dokumen 04 dan 06.

## Paket reproduksi untuk developer

Gunakan source snapshot yang sama, lalu jalankan harness dengan Python standar. Harness mengambil fungsi dari repo, tidak berisi credential. File pendamping tersedia di folder `review_repro/`. Baca README untuk penempatan clone. Setelah patch, ubah ekspektasi defect menjadi perilaku benar dan tambah integration test MongoDB replica set, API authorization, serta fault injection persistence; jangan sekadar membuat assertion lama tetap lulus.
