# IMPLEMENTATION — P14 coverage, UAT, rekonsiliasi & sign-off (putaran 1)

- Tanggal: 2026-10-02. Basis kode: `8fcb9dc9588cf14d9eeb534be38168a1c50f23d3` (HEAD publik) + patch P14 di pohon kerja; SHA kandidat diisi setelah commit platform.
- Lingkungan: preview Emergent, Mongo lokal `test_database` (seed sintetis `seed_realistic.py`, `KN_DEMO_DATA=true`), backend uvicorn, frontend bundle statis.
- Status fase: **belum sign-off**. Putaran ini menambah cakupan & bukti; keputusan akhir menunggu validator independen dan pemilik proses (lihat [SIGNOFF.md](SIGNOFF.md)).

## Perubahan aplikasi

1. **Riwayat Perubahan per sumber daya** — `GET /api/audit-logs/resource?entity_type=&entity_id=` (izin `audit.view`, scope entitas sama dengan daftar audit). Tiap baris membawa `diff`, `integrity` (`ok` / `mismatch` / `unsigned`) hasil hitung ulang `content_hash` GN-14, `layer_entity_id` (override PT vs template global), nama badan usaha. Indeks baru `audit_logs(entity_type, entity_id, timestamp)`.
2. **UI** — komponen `frontend/src/components/AuditHistoryPanel.jsx`; tab "Riwayat Perubahan" di modal detail Bagan Akun (`coa-detail-<kode>`) dan di Pelanggan 360 (`customer-360-tab-changes`). Tab hanya tampil bila pengguna memegang `audit.view`.
3. **Gaji pokok/PII karyawan** (keputusan pemilik: catat field berubah, nilai disamarkan) — `audit(..., masked_fields=[...])`; `PATCH /hr/employees/{id}` mengirim field PII yang benar-benar berubah. Diff: `{field, from:"[REDACTED]", to:"[REDACTED]", masked:true}`; nilai tidak disimpan.
4. **Pemindai secret otomatis** — `.github/workflows/secret-scan.yml` (push & PR) dan `scripts/install_hooks.sh` menjalankan `verify_no_secrets.py` sebagai langkah pre-commit yang **memblokir**.

## Regression lintas fase

`cd backend && python ../audit/iterations/2026-10-02-P14-coverage-uat/run_p14.py` menjalankan ulang 24 harness P01–P14 pada pohon kerja yang sama → [regression_matrix.json](regression_matrix.json), keluaran per skrip di `runs/`.

- Seluruh 24 harness hijau; `repro_p14_history.py` 19/19 ([runs/p14.txt](runs/p14.txt)).
- `p01_s1` hanya lulus via URL HTTPS publik: harness memakai cookie sesi `Secure` (SESSION_COOKIE_SECURE=true) yang tidak dikirim httpx lewat `http://localhost` → artefak lingkungan, bukan regresi (`API_OVERRIDE`).
- `p01_s2` RF-09: harness lama memanggil `scan_verify` (kontrak pra-RF-10/P08 yang kini hanya `print_verify`) → 404. Invariant diadaptasi ke kontrak endpoint (`scan_session` kind `cycle_count`) di p14 dan lulus, termasuk RF-08 (user A-saja ditolak). Dicatat sebagai `drift_excluded`, bukan dihapus.

## Coverage

[coverage.json](../../coverage.json) diperbarui oleh skrip (pemetaan kasus → harness ada di `MAP` run_p14.py, batas cakupan pada `notes`):

| Status | Jumlah |
|---|---|
| tested_pass | 22 |
| partial | 44 |
| planned | 31 |
| blocked | 2 (RFID-06 perangkat fisik, OPS-05 backup/restore) |

Total 99 = 96 baseline + 3 kasus baru (AUDIT-01..03). `tested_pass` berarti skenario dieksekusi invariant yang lulus di DB sintetis — bukan kesiapan produksi. UAT browser: [UAT.md](UAT.md).

## Validasi paket

`python audit/tools/validate.py` → hanya 5 "Broken local link" **pra-ada** di `archive/2026-09/` yang menunjuk `*.log`/`*.lock` (diabaikan `.gitignore`, tidak pernah ada di repo). Tidak diubah (arsip = bukti baseline). Perlu keputusan: commit berkas log tersebut atau koreksi tautan.

## Batas

- Tidak ada pembayaran, perangkat fisik, deploy, atau data produksi yang disentuh. Data uji `TEST_P14*` dibersihkan.
- Riwayat git publik masih memuat token lama (P13) — tugas pemilik.
- Hanya akun GL & pelanggan yang punya tab riwayat; entitas lain dapat memakai `AuditHistoryPanel` yang sama.
