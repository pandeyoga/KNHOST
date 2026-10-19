# LN-120-T01 — Parity matrix kontrak RFID v2 vs ERP aktual

Sumber kontrak: `sources/middleware/kontrak/OPENAPI_RFID_V2.json` (v2.0.0, target). ERP aktual: `backend/routers/rfid.py`, `backend/services/rfid_ingest_service.py` @ HEAD `fd0706c`.
Status: **ADA** = setara tersedia · **SEBAGIAN** = fungsi ada, bentuk/kontrak berbeda · **GAP** = belum ada (backlog). Kontrak tidak dianggap ada hanya karena tertulis di manual.

| Op | Kontrak v2 | ERP aktual | Status | Catatan / backlog |
|---|---|---|---|---|
| AUTH_01 | POST /api/auth/login | POST /api/auth/login | ADA | Session user (operator C72). |
| AUTH_02 | GET /api/auth/me | GET /api/auth/me | ADA | permissions, entity, hidden_views. |
| AUTH_03 | POST /api/auth/logout | POST /api/auth/logout | ADA | |
| API_01 | GET /rfid/v2/device/config | GET /api/rfid/devices (user) | SEBAGIAN | Belum ada endpoint config/profile yang dibaca device dengan X-Device-Key. BL-MW-01. |
| API_02 | POST /rfid/v2/events | POST /api/rfid/ingest (X-Device-Key, batch_id) | SEBAGIAN | Batch durable + dedup batch_id ada; belum event_time/live-backfill/direction per event sesuai skema v2. BL-MW-02 (LN-121). |
| API_03 | POST /rfid/v2/device/telemetry | POST /api/rfid/heartbeat | SEBAGIAN | Hanya online/last_seen; telemetry berlapis belum. BL-MW-03. |
| API_04 | GET /rfid/v2/device/gate-state | GET /api/rfid/gate/{device_id}/status (user) | SEBAGIAN | Belum dibaca device sendiri; latch logical gate belum. BL-MW-04 (LN-121). |
| API_05 | POST /rfid/v2/passages/{id}/close | — (passage ditutup implisit di ingest) | GAP | BL-MW-05 (LN-121). |
| API_06 | POST /rfid/v2/passages/{id}/acknowledge | POST /api/rfid/passages/{id}/acknowledge | ADA | Supervisor (user session). |
| API_07 | GET /rfid/v2/tasks | GET /api/wms/tasks (user scope) | SEBAGIAN | Task WMS ada; belum envelope cursor/version v2. BL-MW-07. |
| API_08 | POST /rfid/v2/tasks | dibuat dari dokumen bisnis (receiving/putaway/opname) | SEBAGIAN | Tidak ada pembuatan task generik dari device — sesuai prinsip "dokumen bisnis sah". |
| API_09 | GET /rfid/v2/tasks/{id} | GET /api/wms/tasks/{id} | SEBAGIAN | Tanpa field version. BL-MW-07. |
| API_10 | GET /rfid/v2/tasks/{id}/expected | — | GAP | Expected rows ber-cursor. BL-MW-10 (LN-121). |
| API_11 | GET /rfid/v2/tasks/{id}/progress | GET /api/rfid/cycle-counts/{id} (opname saja) | SEBAGIAN | BL-MW-11. |
| API_12 | POST /rfid/v2/task-contexts | — | GAP | Bind operator/device/task. BL-MW-12 (LN-121). |
| API_13 | POST /rfid/v2/tasks/{id}/complete | POST /api/inbound/tasks/{id}/complete, /rfid/cycle-count/{id}/complete, /rfid/verify-sessions/{id}/complete | SEBAGIAN | Completion sah per jenis tugas; belum satu endpoint v2. |
| API_14 | POST /rfid/v2/printer/jobs/claim | GET /api/rfid/device-jobs/pending (claim lease atomik + attempt_id) | SEBAGIAN | Semantik claim/lease sudah ada (RF-15); bentuk path berbeda. |
| API_15 | GET …/attempts/{attempt_id} | — | GAP | BL-MW-15 (LN-122). |
| API_16 | POST …/attempts/{attempt_id}/renew | — (lease diperbarui saat pull ulang device sama) | SEBAGIAN | BL-MW-16 (LN-122). |
| API_17 | POST …/attempts/{attempt_id}/start | — | GAP | Start barrier. BL-MW-17 (LN-122). |
| API_18 | POST …/attempts/{attempt_id}/results | POST /api/rfid/device-jobs/{job_id}/ack (attempt_id) | SEBAGIAN | Hanya sukses seluruh job; belum outcome per item success/failed/unknown/partial. BL-MW-18 (LN-122). |
| API_19 | POST /rfid/v2/printer/jobs/{id}/reconcile | POST /api/rfid/print-jobs/{id}/verify/start + verify-sessions | SEBAGIAN | Verifikasi EPC ada; reconcile dengan approval user belum. BL-MW-19. |
| API_20 | GET /rfid/v2/locations/resolve | GET /api/rfid/locations | SEBAGIAN | BL-MW-20. |

Ringkasan: 4 ADA · 14 SEBAGIAN · 5 GAP (dari 23 operasi). Seluruh SEBAGIAN/GAP menunggu **HW-01** (unit, SDK, firmware aktual) sebelum bentuk final dikunci — tidak diklaim PASS.

## LN-120-T02 — Identitas tiga perangkat (bukti otomatis)

Setiap device punya kunci sendiri (`POST /api/rfid/devices/{id}/api-key`, hanya admin, disimpan hash). Tidak ada token user bersama yang di-hardcode. Tes `backend/tests/test_ln120_device_identity.py` membuktikan:
- kunci salah/kosong → 401; device nonaktif → 403;
- reader/gate tidak bisa menarik/mengakui job cetak (bukan printer);
- printer tidak bisa mengirim bacaan EPC;
- printer gudang A tidak bisa mengakui job gudang B (403).

MW-INT-01..12: belum dijalankan — butuh middleware + unit nyata (HW-01).
