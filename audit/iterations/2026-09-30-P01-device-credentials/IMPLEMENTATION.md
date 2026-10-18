# IMPLEMENTATION

Commit sumber diuji: patch di atas `08a9009f18250ea31cecca3ddbe0b7a38561bfe4`, kandidat ter-commit `0076f7ea16ddc93d5b01f480768418464c5c3347`. Diff: [../2026-09-30-P01-scope-batch2/p01_combined.diff](../2026-09-30-P01-scope-batch2/p01_combined.diff) (bagian rfid_*).
ID/fase: RF-12, RF-13 — P01 (hotfix terisolasi, diminta pemilik).

Reproduksi HEAD sebelum patch: `KN_API=http://localhost:8001/api python repro_rf12_rf13.py` → [head_before_patch.txt](head_before_patch.txt) `pass=7 fail=9`. RF-12: `GET /rfid/devices` (role warehouse & admin) dan respons PATCH memuat `api_key`; terbit ulang tanpa regenerate mengembalikan key lama. RF-13: device `enabled=false` + `status=offline` tetap diterima heartbeat (200) & ingest (200), heartbeat mengembalikan `status=online`.

Perubahan dan kontrak lintas caller:
- `rfid_ingest_service`: DB hanya menyimpan `api_key_hash` (SHA-256) + `api_key_hint` (4 char). Key plaintext hanya dikembalikan SEKALI saat terbit/rotasi (`POST /rfid/devices/{id}/api-key`); terbit ulang tanpa `regenerate` → 409 tanpa key. Rotasi langsung membatalkan key lama.
- `authenticate` mencari berdasarkan hash, menolak `enabled=false` (403) → berlaku untuk heartbeat, ingest, device-jobs/pending, device-jobs/ack. `heartbeat`/`ingest` menandai online dengan filter `enabled≠false` (tidak menghidupkan device nonaktif).
- `rfid_service.public_device` = DTO whitelist (list/create/update/seed). Proyeksi `printer-status` & `device-health` mengecualikan `api_key` + `api_key_hash`.
- `update_device`: field `enabled` (lifecycle) terpisah dari `status` (health); nonaktif ⇒ offline; `status=online` ditolak saat nonaktif.
- Migrasi bootstrap idempotent `migrate_plaintext_keys`: key plaintext lama → hash + `key_rotation_required=true` (key pernah terbuka lewat list). Index `rfid_devices.api_key_hash`.
- UI `RfidDevicesView`: key tampil sekali (`rfid-apikey-once-*`, tombol Salin/Sudah disimpan), petunjuk `••••hint`, peringatan wajib rotasi, konfirmasi rotasi, tombol Nonaktifkan/Aktifkan (`rfid-enable-toggle-*`) dengan konfirmasi.

Regression test (command, expected, actual, evidence path):
- `repro_rf12_rf13.py` → 16/16 invariant lulus: [after_patch.txt](after_patch.txt).
- Migrasi legacy (device sintetis plaintext): plaintext hilang, hash ada, rotation_required=true, key lama masih autentik; run kedua 0 (idempotent).
- UI (Playwright, admin, desktop 1920): terbit key → panel sekali tampil; Nonaktifkan → dialog konfirmasi → pill `nonaktif`, status offline, tombol Nyalakan disabled; Aktifkan kembali OK.
- Test lama disesuaikan kontrak baru: `tests/test_iter265_r3r4r5.py` (terbit ulang → 409), `tests/test_iter266_r6_cc_r7.py` (regenerate, cek hash), `scripts/probe_sesi13.py` (ambil key lewat rotasi). `test_iter266` = 9 gagal/22 lulus identik di HEAD dan setelah patch ([legacy_test_iter266_at_head.txt](legacy_test_iter266_at_head.txt)) — ID device hardcode dari seed lama, bukan regresi.

Kontrol yang dipertahankan: hanya admin dapat terbit/rotasi (viewer 403); offline-tapi-enabled bisa reconnect; rotasi tetap membatalkan key lama.
Data historis/migration dry-run: DB sintetis lokal tidak punya key plaintext (0 dokumen). Di produksi migrasi berjalan saat startup; SEMUA device lama ditandai wajib rotasi → middleware perlu key baru (keputusan operasional pemilik).
Batas pengujian: tanpa hardware/middleware nyata; grace policy rotasi (dua key paralel) belum ada — rotasi langsung memutus key lama.
ID siap divalidasi / tertunda: RF-12, RF-13 siap divalidasi setelah SHA commit tercatat.
