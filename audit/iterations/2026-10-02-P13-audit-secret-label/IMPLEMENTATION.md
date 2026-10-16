# IMPLEMENTATION

- Commit sumber diuji: patch di atas `5cddfc964ee0b1b84729d13d01a789d31f31bb7d` (P10–P12 sudah termasuk). SHA kandidat diisi setelah commit platform.
- ID/fase: P13, yaitu GN-14 dan UX-03.

## Reproduksi HEAD

Perintah: worktree `5cddfc9` → `cd .head_wt/backend && SKIP_HTTP=1 python <repo>/audit/iterations/2026-10-02-P13-audit-secret-label/repro_p13.py <repo>/.head_wt`. Hasil: [head_before_patch.txt](head_before_patch.txt) `pass=0 fail=7`.

- `audit()` tidak menerima `before`.
- Ada 4 file token sesi yang ter-track: `.tok`, `.tok_admin`, `.tok_mgr`, `memory/.tok_admin`. Pola `.tok*` tidak masuk `.gitignore`.
- Belum ada pemindai secret.
- Panel OCR merender `r.entity_id`.
- Bagian HTTP tidak dijalankan pada baseline, karena server yang berjalan sudah memakai kode patch.

**Pemeriksaan token** (nilai tidak dicetak): keempat file menghasilkan 401 di `/api/auth/me` pada backend preview ini (seed baru). Validitasnya di lingkungan lain (produksi/preview lama) **belum diperiksa** — itu tugas pemilik.

## Perubahan

**GN-14 — `backend/dependencies.py`**

`audit()` kini menerima `before` dan `source`. Baris audit memuat:
- `actor_id` (dari request context)
- `source`
- `before` / `after`
- `diff`: field level atas yang berubah, `{field, from, to}`; untuk after parsial hanya kunci after yang dibandingkan
- `content_hash`: sha256 isi baris, untuk deteksi perubahan

Redaksi otomatis: kunci yang mengandung password, secret, token, api_key, private_key, hash, otp, session, credential, atau pin diganti `[REDACTED]` di before maupun after. Pemanggil lama tetap kompatibel.

**Endpoint keuangan/konfigurasi yang kini mengirim nilai sebelum:**
- PATCH/DELETE akun GL (snapshot akun saat dihapus)
- Void jurnal (status/total)
- PATCH rekening kas/bank (field yang diubah)
- PUT settings (seksi pajak/keuangan/dll.)
- PATCH syarat bayar
- PUT HR settings
- PATCH karyawan (PII tetap dikecualikan)
- Nonaktif karyawan
- PATCH pelanggan (hanya field yang diubah, bukan dokumen penuh)
- HPP stok awal roll

**Secret di repo:**
- Keempat file token dihapus dari pohon kerja.
- `.gitignore` kini menolak `.tok`, `.tok_*`, `**/.tok*`, `*.token`.
- `tests/rnd_flow_check.py` membaca token dari `KN_TEST_TOKEN` / `KN_TEST_TOKEN_FILE` (default `/tmp/kn_test.tok`).
- Guardrail baru `scripts/guardrails/verify_no_secrets.py`:
  - Memindai file ter-track: nama terlarang (`.tok*`, `.env*`, `*.pem`, `*.key`, `credentials.json`) dan pola credential umum (private key, AWS, Stripe live, OpenAI, Google, Emergent, Slack, GitHub, Bearer literal).
  - Hanya mencetak file:baris:jenis, tanpa nilai.
  - Exit 1 bila ada temuan.
  - Hasil sesudah patch: [secret_scan_after.txt](secret_scan_after.txt) `0 temuan`.

**UX-03 — `frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx`**
- Kolom Badan usaha memakai `entityShortById` (EntityScopeContext).
- Fallback: "Badan usaha tidak dikenal" (ID tak ada di daftar) dan "Tanpa badan usaha" (kosong).
- ID teknis tetap ada di atribut `title`. testid `grn-ocr-usage-entity-<model>-<entity>`.

## Regression

- `repro_p13.py /app` → [after_patch.txt](after_patch.txt) `pass=10 fail=0` (in-process + HTTP lokal akun GL + statis).

## Batas / tindakan pemilik

- **Riwayat git publik** masih memuat file token lama. Pembersihan riwayat (git filter-repo/BFG + force-push) dan invalidasi/rotasi sesi di semua lingkungan wajib dilakukan pemilik repo. Agent tidak menulis ulang riwayat publik.
- Pemindai belum dipasang sebagai pre-commit/CI. Perlu keputusan alur CI.
- Rantai hash antar-baris (append-only kuat) belum dibuat; `content_hash` hanya per baris. Skrip uji internal (`backend/test_*_poc.py`) masih menghapus `audit_logs` sintetisnya sendiri.
- Dari ±670 pemanggil `audit()`, hanya jalur keuangan/konfigurasi di atas yang diberi nilai sebelum. Domain dengan riwayat sendiri (jurnal, roll timeline, history dokumen) tidak diubah. Pemanggil lain mendapat redaksi + actor_id/source, tetapi before masih kosong.
- UX-03 diverifikasi statis + render oleh agen uji (lihat test_reports).
