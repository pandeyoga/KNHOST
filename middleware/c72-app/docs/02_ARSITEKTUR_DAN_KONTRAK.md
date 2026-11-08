# 02 — Arsitektur & kontrak API handheld (`/api/handheld`, versi 1.0)

## 1. Lapisan aplikasi
```
UI (Activity, programatik)  ──►  core (Java murni, diuji di host)  ──►  ApiClient ──► ERP /api/handheld/*
        │                         ScanController ─► C72HardwareAdapter ◄── ChainwayC72Adapter (SDK) | SimulatedHardware
        │                         DocMatcher · Snapshot · RegistrationForm · WriteFlow · LocateMeter · BenchRunner
        └── App: utas io (HTTP/SQLite) · radio (SDK) · sync (antrean berkala)   Store ◄── SqliteStore | MemoryStore
```
- **C72HardwareAdapter** (spesifikasi Kubus 02 §2.2) memisahkan SDK dari logika: `initialize(profile)`, `beginInventory`,
  `stopInventory`, `capabilities`, `writeEpc`, `readSingle`, `startLocate/stopLocate`, `openBarcode/startBarcode`,
  `battery`, `release`. Hanya `ChainwayC72Adapter` yang mengimpor `com.rscja.*`. Callback SDK hanya menyalin ke
  `ReadAggregator` (tanpa I/O, tanpa kunci kontrol → tidak deadlock saat `stopInventory`).
- **Satu pemilik radio** (`ScanController`): pemicu ganda tidak membuka sesi kedua; tulis/cari/diagnostik memegang radio
  eksklusif (`acquire`). Panggilan SDK di utas `radio`, HTTP di `io`/`sync` — UI thread tidak memblok.
- **Lapisan tugas = adaptor API** (`ApiClient`, `TaskKind`, `Snapshot`): aplikasi hanya mengenal kode jenis tugas dan
  bentuk snapshot. Bila model tugas ERP berubah (audit UI paralel), cukup server `handheld_tasks.py` + `ApiClient`.

## 2. State & penyimpanan
UNPROVISIONED → READY (device key) → AUTHENTICATED (sesi ERP + sesi operator) → per dokumen: snapshot → SCANNING →
draf tahan-mati → antrean → ACK/konflik → (selesaikan). Tabel SQLite `kn-c72-v1.db` (WAL):

| Tabel | Isi |
|---|---|
| `outbox` | kiriman persist-before-send: `id` = ID idempotensi klien, `body` tidak pernah diubah, status `pending/done/conflict/rejected/blocked/archived`, `attempts`, `next_due`, `user_id` + `op_session` pemilik |
| `snapshots` | daftar yang diharapkan per dokumen (cache baca, semua halaman digabung) |
| `doc_codes` | status lokal per EPC/label per dokumen: `queued`, `acked`, `conflict` (+ pesan), `extra` |
| `epc_pool` | cadangan EPC Daftar Awal per sesi: `free → taken → used` (EPC yang gagal ditulis tidak dipakai ulang) |
| `reg_lines` | baris Daftar Awal yang ditangkap di HP (form + foto) + hasil ERP |
| `kv`, `audit`, `bench` | setelan/sesi/draf pindai, jejak lokal (≤ 5000), hasil uji meja |

Kredensial (device key, token sesi) terenkripsi AES-GCM (Android Keystore); sandi tidak disimpan; backup dimatikan.
Logout/ganti operator/update/reboot **tidak** menghapus antrean (HH-08). Migrasi skema berikutnya wajib menyalin.

## 3. Sinkron (`SyncEngine`)
- Hanya item milik operator yang login (`user_id`) yang dikirim; server juga menolak `OPERATOR_MISMATCH`.
- Urutan per dokumen dijaga (Selesaikan tidak menyalip batch dokumen yang sama); dokumen lain tidak tertahan.
- **HTTP 200 = hasil final** (`status: accepted | conflict | rejected`) → tidak diulang. Galat sementara (jaringan, 5xx,
  429/`Retry-After`, `REQUEST_IN_PROGRESS`, `SAGA_IN_PROGRESS`) → ulang dengan **ID & isi sama**, backoff 2 dtk ×2 …
  maks profil (5 mnt) ±20 %. 401 → login ulang (antrean utuh). `DEVICE_*` → provisioning. `IDEMPOTENCY_CONFLICT` →
  ditahan untuk peninjauan ber-PIN.

## 4. Kontrak HTTP
Identitas: **`X-Device-Key`** (perangkat; hash SHA-256 di `rfid_devices`, `type=handheld`) dan **`Authorization: Bearer`**
(sesi ERP operator). Endpoint kerja WAJIB keduanya. Galat: `{"detail": {"code","message","retryable","details"}}`.
Mutasi idempoten: `client_batch_id` / `client_request_id` di badan (atau header `Idempotency-Key`), 8–80 karakter.

| Method & path | Identitas | Fungsi |
|---|---|---|
| `GET /device/config?app_version=` | perangkat | binding (gudang, site, cakupan), `profile` + `profile_version`, `kinds`, `limits`, `server_time` |
| `POST /session/start` `{app_version}` | keduanya | ikat operator↔perangkat; menutup sesi operator lama perangkat (ganti operator) |
| `POST /session/end` `{operator_session_id, reason}` | keduanya | tutup sesi operator |
| `GET /me` | keduanya | pengguna, gudang efektif (perangkat ∩ lokasi kerja), jenis tugas + izin |
| `GET /tasks/summary` | keduanya | jumlah dokumen terbuka per jenis |
| `GET /tasks?kind=&q=&limit=` | keduanya + izin jenis | daftar dokumen |
| `GET /tasks/{kind}/{doc_id}/expected?offset=&limit=&start=` | keduanya + izin | yang diharapkan (≤ 5000 baris/halaman); `start=true` membuka sesi cek muat/opname/verifikasi |
| `POST /batches` | keduanya + izin | satu pindai massal satu dokumen (lihat §5) |
| `POST /tasks/{kind}/{doc_id}/complete` `{client_request_id, session_id}` | keduanya + izin | selesaikan sesi (cek muat, opname, verifikasi cetak) |
| `POST /tasks/cutting/{task_id}/cut` `{client_request_id, epc\|roll_id, actual_length, reason}` | keduanya + `wms.scan` | potong sampel |
| `GET /lookup?code=` · `GET /untagged?warehouse_id=` | keduanya + `wms.view` | cari roll (EPC/no. roll/ID) · roll belum bertag |
| `POST /tag-writes` `{client_request_id, code}` | keduanya + `wms.scan` | niat tulis + EPC baru (tag lama tetap berlaku) |
| `POST /tag-writes/{id}/confirm` `{client_request_id, verified_epc, tid, rssi, attempts}` | keduanya + `wms.scan` | baca ulang cocok → retire tag lama, aktifkan tag baru |
| `POST /tag-writes/{id}/fail` `{reason}` | keduanya + `wms.scan` | tutup niat (EPC tidak dipakai) |
| `GET /registration/catalog` | keduanya + `inventory.cycle_count` | katalog produk aktif bersatuan dasar (cache offline) |
| `POST /registration/{sid}/epc-pool` `{count≤200}` | keduanya + idem | cadangan EPC sistem untuk perangkat ini (diisi sampai `count`) |
| `POST /registration/{sid}/label-decode` · `/racks/{rack_id}` · `/lines/mark-written` | keduanya + idem | urai label supplier · rak selesai · tandai tertulis |
| `GET/POST /devices`, `POST /devices/{id}/rotate-key\|revoke\|enable`, `PUT /devices/{id}/profile`, `GET /devices/{id}/activity` | pengguna (admin; cabut: admin/admin gudang; baca: `wms.view`) | registri perangkat & jejak siapa-perangkat-apa |

Izin jenis tugas = izin endpoint web asal: `putaway_in`/`outbound_*` → `wms.update`; `transfer_in` → `transfer.update`;
`cutting`/`cycle_count`/`print_verify` → `wms.scan`; `registration` → `inventory.cycle_count`.

`doc_id`: PA id · transfer id · `<order_id>~<warehouse_id>` (cek muat) · warehouse id (opname) · print job id · task id
(potong) · sesi pendaftaran id.

**Snapshot** (`expected`): `version` = sidik STRUKTUR (anggota + dokumen terbuka/tertutup + sesi), bukan progres;
`rows[] {roll_id, roll_no, epc, state: pending|done|exception|returned, sku, product_name, qty, unit, lot, bin_code}`,
`untagged[]`, `counts`, `qty_by_unit`, `closed`, `needs_start`, `session_id`, `labels_allowed`, `registration{}`/`task{}`.

## 5. Batch pindai (`POST /batches`)
```json
{"client_batch_id":"b-2f0…","kind":"putaway_in","doc_id":"pa_…","session_id":null,"snapshot_version":"9c1…",
 "operator_session_id":"hos_…","user_id":"usr_…","device_time":"2026-11-09T01:00:00Z","clock_offset_ms":1200,
 "clock_synced":true,"captured_from":"…","captured_to":"…","simulated":false,
 "reads":[{"epc":"E2…","rssi":-55.5,"count":3,"first_seen":"…","last_seen":"…","tid":null}],
 "labels":["ROLLNO"],"label_reason":"","bin_id":"","lines":[]}
```
Respons (disimpan; kiriman ulang badan sama → `replay: true`; ID sama isi beda → 409 `IDEMPOTENCY_CONFLICT`):
```json
{"status":"accepted","kind":"putaway_in","doc_id":"pa_…","snapshot_stale":false,"current_version":"9c1…",
 "items":[{"ref":"E2…","result":"arrived","conflict":false,"message":"…","roll_id":"…","roll_no":"…"}],
 "summary":{"total":3,"arrived":2,"extra":1,"conflict":0},"doc":{"status":"partially_received","done":2,"pending":2},
 "client_request_id":"b-2f0…","server_time":"…","replay":false}
```
`result` per item: `arrived`/`received`/`matched` · `already` · `extra` (bukan dokumen — diabaikan, tidak jadi
exception "salah kirim") · `conflict` (roll berubah saat offline / aturan gudang menolak) · `needs_rfid` ·
`needs_override` · `exception_recorded` · `saved`/`invalid` (Daftar Awal). Dokumen tertutup → `status: conflict`,
`error.code: DOC_CLOSED`. `simulated: true` hanya untuk sesi bukti (server mencatat `simulated`); tiba/terima/daftar →
`SIMULATION_NOT_ALLOWED`. Server menyimpan bacaan mentah (≤ 2000), `device_time`, `clock_skew_ms`, operator & perangkat.

Daftar Awal: `lines[] {client_line_id, epc, written, captured_at, bin_id, owner_entity_id, product_id | unrecognized+note,
qty, unit, length_from_label, lot, dye_lot, grade, old_roll_no, label_raw}`. Mode sistem: EPC wajib cadangan perangkat
ini untuk sesi ini; `written=true` → `mark_written`. Kirim ulang baris yang sama → `saved` "sudah tersimpan sebelumnya".

## 6. Kode galat utama
| Kode | HTTP | Tindakan aplikasi |
|---|---|---|
| `DEVICE_KEY_REQUIRED` / `DEVICE_KEY_INVALID` / `DEVICE_DISABLED` / `DEVICE_NOT_HANDHELD` | 401/403 | berhenti; provisioning ulang (PIN) |
| (401 tanpa kode) | 401 | login ulang operator; antrean utuh |
| `PERMISSION_DENIED`, `SCOPE_DENIED`, `KIND_UNKNOWN`, `DOC_NOT_FOUND` | 403/404 | tampilkan; tidak diulang |
| `OPERATOR_MISMATCH` | 409 | item milik operator lain — tunggu operator itu |
| `IDEMPOTENCY_CONFLICT` | 409 | tahan, tinjau (PIN) — jangan ganti ID |
| `REQUEST_IN_PROGRESS`, `SAGA_IN_PROGRESS`, `EPC_GENERATION_FAILED` | 409/503 | ulang dengan ID sama |
| `SESSION_REQUIRED`/`SESSION_NOT_FOUND`/`SESSION_MISMATCH`, `COMPLETE_NOT_SUPPORTED`, `PROFILE_INVALID` | 400/404/409 | kontrak — perbaiki aplikasi/konfigurasi |

## 7. Pemetaan kriteria modul Kubus (02 §2.12)
| ID | Status 0.1.0-lab |
|---|---|
| HH-01 provisioning & login terikat device/user/site | dibangun + diuji pytest (binding, ganti operator, cakupan) |
| HH-02 trigger/lifecycle SDK stabil, layar tidak freeze | logika diuji host; **unit nyata belum** (uji meja §3 dok 03) |
| HH-03 context/version/expected scope | snapshot ber-versi + sesi eksplisit; diuji |
| HH-04 print verify EPC & tag-roll | dibangun + diuji pytest |
| HH-05 loading matched/missing/extra | dibangun + diuji; "manifest berubah" → `snapshot_stale` + `SESSION_MISMATCH` |
| HH-06 opname tanpa auto-post | memakai `cycle_count_service` (laporan saja) |
| HH-07 putaway rules server + idempoten | trip `client_trip_id`; aturan/BTG di layanan asal; pemilihan bin per roll **belum** (lihat laporan) |
| HH-08 offline/logout/reboot/update | antrean SQLite + pemilik per item; diuji host (MemoryStore) — SQLite di unit belum |
| HH-09 retry/partial ACK tidak menggandakan | idempotensi server + ID tetap; diuji pytest & host |
| HH-10 completion pakai server | `complete` lewat sesi server; tombol aktif hanya bila antrean dokumen kosong |
| HH-11 cari tag relatif | dibangun (SDK `startLocation` + cadangan RSSI) — belum terbukti |
| HH-12 APK, source, mapping SDK, runbook, hasil hardware | APK debug + source + dokumen ini; hasil hardware **menunggu unit** |
