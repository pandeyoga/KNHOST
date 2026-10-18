# 5. Kontrak API Target Middleware

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia  
**Versi contract:** 2.0 / schema_version=2  
**Status penggunaan:** AVAILABLE CONTRACT untuk development middleware.

## 5.1 Aturan contract dan autentikasi

Semua path menggunakan base URL lingkungan integrasi yang diprovisioning. Tim pengembangan memakai OpenAPI JSON dalam paket sebagai acuan field/type bersama. Domain contoh bukan alamat deployment aktual. Contract tersedia menjadi asumsi development; pekerjaan penyelarasan ERP dicatat dalam dokumen ERP terpisah.

Device endpoints memakai X-Device-Key. User endpoints memakai autentikasi ERP. Binding task memakai keduanya: identitas perangkat plus user berizin. Idempotency-Key wajib untuk mutasi task/printer/ack yang dinyatakan pada endpoint; key dipersist sebelum request. Retry key dengan body berbeda menghasilkan IDEMPOTENCY_CONFLICT.

ID adalah opaque string, bukan nomor yang dihasilkan dari panjang/urutan list. Semua timestamp ISO 8601 UTC. config_version/task_version/job_revision mengacu version server. Warehouse/owner berasal dari binding registry dan resource scope server; body bebas tidak memperluas izin.

### Identitas user dan entity context

C72 memakai POST /api/auth/login dengan email/password, lalu menyimpan token session ERP sebagai credential opaque dalam penyimpanan yang dilindungi OS. Token dikirim sebagai Authorization: Bearer pada user endpoints. GET /api/auth/me memberikan user, permissions dan entity_context; POST /api/auth/logout mengakhiri session. Token bukan JWT dan tidak diparse untuk menetapkan izin. Bila expired, minta login ulang; credential password tidak disimpan untuk login otomatis. Outbox evidence tetap tersimpan ketika session berakhir.

X-Entity-Id, bila dipakai ERP, hanya memilih entity context yang user berhak akses; bukan override owner atau warehouse scope. Device key tetap terpisah dan tidak digunakan untuk user approvals. Reader/printer tidak menyimpan username/password operator demi terus berjalan. User reconcile/ack dijalankan melalui session supervisor yang berwenang.

## 5.2 Daftar endpoint acuan

| ID | Method/path | Identitas | Fungsi |
|---|---|---|---|
| API-01 | GET /api/rfid/v2/device/config | Device | Config/profile/binding/limits yang berlaku. |
| API-02 | POST /api/rfid/v2/events | Device | Batch observations dengan ACK individual. |
| API-03 | POST /api/rfid/v2/device/telemetry | Device | Radio/printer/network/queue/build health. |
| API-04 | GET /api/rfid/v2/device/gate-state | Device | Logical gate state, latch dan config untuk reader. |
| API-05 | POST /api/rfid/v2/passages/{local_passage_id}/close | Device + idempotency | Akhir passage dan final verdict. |
| API-06 | POST /api/rfid/v2/passages/{local_passage_id}/acknowledge | User + idempotency | Acknowledge alarm beralasan. |
| API-07 | GET /api/rfid/v2/tasks | User | Daftar pekerjaan yang dapat diakses. |
| API-08 | POST /api/rfid/v2/tasks | User + idempotency | Buat task dari sumber bisnis yang sah. |
| API-09 | GET /api/rfid/v2/tasks/{task_id} | User | Header/snapshot task dan version. |
| API-10 | GET /api/rfid/v2/tasks/{task_id}/expected | User | Expected rows ber-cursor. |
| API-11 | GET /api/rfid/v2/tasks/{task_id}/progress | User | Hasil authoritative scan/task. |
| API-12 | POST /api/rfid/v2/task-contexts | User + device + idempotency | Binding operator-device-task dan expiry. |
| API-13 | POST /api/rfid/v2/tasks/{task_id}/complete | User + idempotency | Review/completion bisnis sesuai kind/version. |
| API-14 | POST /api/rfid/v2/printer/jobs/claim | Device + idempotency | Claim job dengan stable attempt/lease. |
| API-15 | GET /api/rfid/v2/printer/jobs/{job_id}/attempts/{attempt_id} | Device | State/result/recovery attempt. |
| API-16 | POST /api/rfid/v2/printer/jobs/{job_id}/attempts/{attempt_id}/renew | Device + idempotency | Extend lease tanpa mengganti attempt. |
| API-17 | POST /api/rfid/v2/printer/jobs/{job_id}/attempts/{attempt_id}/start | Device + idempotency | Durable start sebelum output fisik. |
| API-18 | POST /api/rfid/v2/printer/jobs/{job_id}/attempts/{attempt_id}/results | Device + idempotency | Hasil dan evidence per item. |
| API-19 | POST /api/rfid/v2/printer/jobs/{job_id}/reconcile | User + idempotency | Resolution output ambigu/reprint plan berizin. |
| API-20 | GET /api/rfid/v2/locations/resolve | User | Resolve barcode/ID bin dalam scope task dan hierarchy resmi. |

AUTH-01: POST /api/auth/login; AUTH-02: GET /api/auth/me; AUTH-03: POST /api/auth/logout. Ketiganya mendukung session user, terpisah dari 20 endpoint RFID.

Provisioning device/key dilakukan melalui registry ERP oleh administrator. App menggunakan key yang diprovisioning, bukan membuat akun admin atau menduplikasi registry. API bisnis di belakang generic task memastikan receipt/dispatch/alamat/opname tetap menjalankan rule ERP.

## 5.3 Device config dan profile

Config response mempunyai device_id/device_type/site_id/warehouse_id, enabled, config_version, server_time, hardware_profile_id, hardware_profile, limits, policies dan logical_gates untuk reader.

limits memuat max_events, max_body_bytes dan max_queue_bytes. policies memuat heartbeat/telemetry interval, backoff, capture offline, gate validity, passage boundary dan print lease. Setiap field memiliki unit eksplisit. Nilai production ditentukan commissioning; contoh angka dalam fixture hanya contoh transport.

hardware_profile adalah parameter SDK/media terverifikasi, bukan kode executable dari server. logical_gates memetakan gate ID/direction/antena/sensor ke scope yang dipercayai. Config yang unsupported dinyatakan CONFIG_UNSUPPORTED; agent tidak memakai fallback parameter yang belum disahkan.

## 5.4 Observations dan ACK individual

Request batch terdiri schema_version, batch_id, mode, config_version, context dan events. mode=live atau backfill. context.kind adalah inventory, print_verify, loading_check, cycle_count, putaway, tag_search atau gate. Sesi operator memakai task_context_id; gate memakai logical_gate_id/local_passage_id.

Setiap event berisi event_id, raw_epc, captured_at, time_quality, dan metadata antenna/rssi yang nullable. epc kanonik dapat diisi jika raw value valid; raw asing/rusak tidak hilang. RSSI unit diketahui profile; jika dBm tidak terkonfirmasi, rssi_dbm null dan raw_rssi dapat dicatat.

```json
{
  "schema_version": 2,
  "batch_id": "batch-example-001",
  "mode": "live",
  "config_version": "cfg-example-01",
  "context": {
    "kind": "print_verify",
    "task_context_id": "ctx-example-01"
  },
  "events": [{
    "event_id": "event-example-001",
    "raw_epc": "E20034120123456789ABCDEF",
    "epc": "E20034120123456789ABCDEF",
    "captured_at": "2026-10-13T02:00:00Z",
    "time_quality": "synced",
    "antenna": null,
    "rssi_dbm": null
  }]
}
```

Response event_acks berisi event_id, status, durable, processing_status dan error nullable. accepted/duplicate dengan durable=true menutup record transport. processing pending tetap terlihat pada task dan dipulihkan ERP; completion tidak menganggap pending sebagai hasil final. rejected/quarantined/retry ditangani per event; event yang sudah di-ACK tidak ikut resend.

Envelope malformed, unsupported schema atau limit berlebih ditolak sebelum processing. Batch valid dengan sebagian event bermasalah menghasilkan ACK individual; jangan menghapus seluruh batch hanya dari HTTP 200. Server menyimpan dedup device/event ID dan membedakan observation dari business effect.

## 5.5 Task context dan completion

Task header mempunyai task_id/kind/source_ref/site/warehouse/status/version, expected_count, expected_qty_by_unit, allowed_actions dan progress link. Expected rows memakai cursor; total tidak dihitung dari satu page. Row memuat roll_id/roll_no/EPC serta qty/unit dan atribut yang diizinkan.

Task creation menunjuk source_type/source_id/warehouse dan kind. ERP memvalidasi dokumen sumber. Binding context menunjuk task_id/version dan dipasangkan dengan device key/user session; response memberi context ID, expiry, offline_capture_allowed dan authoritative snapshot version.

Untuk putaway, GET /api/rfid/v2/locations/resolve memakai task_id dan code dari barcode/QR alamat. Respons node_id/bin_id beserta hierarchy path site > warehouse > zone > cabinet > shelf/bin, rules_summary dan eligible. Nama display mengikuti istilah ERP; lemari adalah node fisik berbeda dari rak. eligible pada lookup membantu UI, sedangkan completion tetap memvalidasi ulang status/capacity/rules/version pada saat commit. Code yang tidak dikenal tidak dibuat menjadi lokasi baru oleh handheld.

Completion memakai task_context_id, task_version serta action_data yang ditetapkan task. Putaway dapat memuat destination_bin_id. Completion response menjelaskan status/result, pending_processing, downstream refs dan eligibility; with_issues pada loading tidak diperlakukan clean untuk dispatch.

Server menolak stale/canceled context, pending evidence yang belum selesai, version conflict dan izin yang tidak cocok. Retry Idempotency-Key mengembalikan hasil yang sama, bukan membuat dokumen bisnis kedua.

## 5.6 Gate close, decision dan latch

Close request memakai logical_gate_id, config_version, mode, closing_captured_at dan boundary_reason. Event passage memakai local ID yang sama. ERP mengikat expected manifest/context sesuai instalasi; app tidak mengklaim expected bebas sebagai sumber izin.

Decision response: decision_id, local_passage_id, logical_gate_id, mode, final, verdict, completion_basis, config_version, created_at, expires_at, allow_live_signal, latched, reason_code/action dan count summaries.

Agent hanya menerapkan indikator live bila seluruh syarat sesuai: final=true, mode=live, current passage/gate/version, validity belum habis dan allow_live_signal=true. green adalah verdict yang sah, bukan hasil HTTP success atau beberapa EPC dikenal. UNKNOWN/REVIEW untuk arah/data/completeness tidak pasti mengikuti policy server.

Gate-state device-scoped memuat latch serta authoritative passage/decision terbaru. Supervisor acknowledge memakai auth user dan note; response menghapus latch yang dimaksud tanpa mengubah raw evidence. Device polling kemudian menyesuaikan state; acknowledgement tidak menciptakan decision green baru.

Polling setelah close final=false menggunakan logical_gate_id dan local_passage_id pada API-04 sehingga hasil passage tidak tertukar dengan passage baru. Latch tetap mencerminkan gate saat ini. Keputusan historis hanya evidence; agent tetap mencocokkan active passage sebelum signal.

## 5.7 Printer lease, intent dan hasil

Claim memakai capabilities/requested_max_jobs dan menerima jobs yang sah. Job mempunyai job_id/revision/kind/warehouse/owner context, items, payload profile serta lease. Item ID/EPC/payload digest stabil; server mengevaluasi snapshot roll. Lease mempunyai attempt_id/device_id/claimed_at/expires_at.

Renew mengubah expiry untuk attempt yang sama. Start menunjuk item_ids dan job_revision; server menyimpan intent/started state sebelum response accepted. Connector tidak melakukan hardware send sebelum start diterima. Lease expired dengan output started/uncertain tidak di-reassign otomatis; state query/reconciliation menentukan langkah berikutnya.

Results berisi result_event_id, item_id, payload_sha256, print_status, encode_status dan evidence. result_event_id tetap untuk kiriman ulang evidence yang sama. UNKNOWN -> resolved membutuhkan evidence baru/approval sesuai sumber; result terdahulu tetap berjejak. confirmed tidak otomatis diubah mundur oleh duplicate lama.

Native result yang tidak tersedia dilaporkan unknown. Job partial memuat item status masing-masing dan aggregate needs_review. Job printed/identity active berbeda dari verified tag-roll; ERP menyiapkan task C72 berikutnya jika policy terpenuhi.

User reconcile memakai job/attempt/item, note, action dan evidence_ref; ERP menghasilkan disposition yang sah. Connector tidak membuat reprint/retag sendiri dari timeout. Result retry juga menyelesaikan unfinished server effects tanpa physical resend.

## 5.8 Error dan tindakan client

| HTTP/code | Tindakan client |
|---|---|
| 400 SCHEMA_INVALID / CONFIG_UNSUPPORTED | Stop request yang sama; quarantine/diagnostics dan perbaiki contract/config. |
| 401 DEVICE_KEY_INVALID / USER_AUTH_EXPIRED | Reprovision/login ulang sesuai identitas; jangan loop tanpa batas. |
| 403 SCOPE_DENIED / DEVICE_DISABLED | Stop new work; tampilkan lifecycle/scope error. |
| 404 RESOURCE_NOT_FOUND | Review resource/context; tidak membuat ID pengganti sendiri. |
| 409 VERSION_CONFLICT / CONTEXT_CLOSED | Stop business completion; refresh/reconcile dengan evidence lama tetap. |
| 409 IDEMPOTENCY_CONFLICT / LEASE_CONFLICT | Jangan mengganti key untuk memaksa berhasil; query/reconcile. |
| 413 BATCH_TOO_LARGE | Pecah batch sebelum resend; rejected envelope belum diproses. |
| 429 RATE_LIMITED | Ikuti Retry-After/backoff, pertahankan ID. |
| 5xx / network timeout | Retry transport dengan identity sama; printer physical resend tetap memakai reconciliation. |

Error response memiliki request_id dan error.code/message/retryable; diagnostics mencatat context tanpa secret. Config/role/clock conflicts dibedakan dari hardware unavailable.

## 5.9 Compatibility dan contoh mesin

OpenAPI adalah acuan field/path target dalam paket, bukan source implementasi middleware. Dependency versions serta SDK method mapping berada pada commissioning/release matrix. Additive response field boleh diabaikan client yang mendukung minor revision; required semantics/schema major yang tidak didukung menghasilkan error, bukan silent downgrade.

Kontrak ini sengaja tunggal untuk ketiga tim pengembangan. Perubahan route/field/status harus direvisi di OpenAPI dan spesifikasi secara bersamaan sebelum digabung; APK/connector dan ERP release matrix mencatat pasangan versi yang telah lulus.


## 5.10 Ringkasan schema untuk pembaca

| Kelompok | Field utama | Makna dan aturan |
|---|---|---|
| Quantity | qty, unit | qty string decimal exact; jumlah EPC/roll berbeda dari yard/meter/kg. Jangan menjumlah unit berbeda. |
| DeviceConfig | device_id, scope, config_version, hardware_profile, limits, policies | Server menetapkan binding dan parameter profile; client tidak memperluas scope. |
| Observation | event_id, raw_epc, epc, captured_at, time_quality, antenna, rssi_dbm | Identitas dan raw capture stabil; epc hanya canonical valid, metadata yang tidak tersedia null. |
| EventAck | event_id, status, durable, processing_status, error | Durable transport dan selesai business effects dibedakan. |
| TaskHeader | kind, source_ref, warehouse, task_version, expected_count, expected_qty_by_unit | Count/qty authoritative seluruh task; bukan penjumlahan page pertama. |
| TaskContext | device_id, user_id, task_id, task_version, expires_at | Upload mengacu context asli; logout tidak memindahkan evidence ke user baru. |
| TaskProgress | counts, rows, qty_by_unit, completion_eligible, pending_processing | UI provisional tidak menggantikan hasil final server. |
| GateDecision | passage/gate ID, final, verdict, expires_at, mode, allow_live_signal | HTTP 200/familiar EPC saja tidak berarti izin keluar. |
| PrintJob/Lease | job_revision, item_id, payload_sha256, attempt_id, expires_at | Job dan output identity tetap; lease bukan alasan physical resend. |
| PrintItemResult | result_event_id, print_status, encode_status, evidence | Partial/unknown dilaporkan per item; C72 verify terpisah. |
| LocationResolve | bin_id, location_version, hierarchy, eligible, rules_summary | Alamat berasal registry ERP; rules/capacity divalidasi lagi pada completion. |

OpenAPI JSON menjabarkan required fields, enums, pattern, nullability, auth dan response. Endpoint JSON examples berada pada kontrak/CONTRACT_EXAMPLES.json. Hanya angka contoh transport digunakan; bukan nilai stock aktual atau konfigurasi production.

Passage close juga membawa observed_event_count dan capture_complete. Server membandingkan jumlah event ID unik yang tersimpan serta status processing. last_event_id saja tidak membuktikan seluruh batch terdahulu diterima. Capture error, event gap, pending effect atau clock tidak layak menghasilkan REVIEW/UNKNOWN atau final=false; tidak ada green otomatis. Passage yang sudah berubah menjadi backfill tidak memperoleh clearance live saat koneksi pulih.

Parameter event/body/queue limits ditentukan konfigurasi. Task page limit 1-500 adalah batas transport kontrak; total_count dan summary tetap total seluruh snapshot. Max events per batch mengikuti DeviceConfig, bukan hardcoded 500 dalam aplikasi.


Untuk gate, context membawa direction dan direction_evidence dari fixed profile, sensor sequence, server context atau unknown. Close membawa field yang sama. Server memvalidasi evidence terhadap profile/binding config_version; direction pada body tidak otomatis dipercaya. Konfigurasi bidirectional yang belum menghasilkan direction sah tidak mengizinkan automatic clearance. Count close adalah jumlah event_id observasi unik, bukan jumlah EPC unik.

TaskHeader dapat memuat assigned_user untuk PIC; bila null/tidak ditugaskan UI menampilkan belum ditugaskan. Action completion mengikuti allowed_actions dan task kind dari server. Roll/item/qty tidak dihitung ulang dari jumlah record response pagination.
