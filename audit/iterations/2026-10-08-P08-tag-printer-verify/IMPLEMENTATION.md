# IMPLEMENTATION

Commit sumber diuji: patch di atas `cc74485` (HEAD repo saat sesi; memuat iterasi 2026-10-07). SHA kandidat diisi setelah commit platform.
ID/fase: P08 — IX-12, RF-01, RF-07, RF-10, RF-11, RF-14, RF-15, UX-02.

Reproduksi HEAD: `git worktree add .head_wt HEAD && cp backend/.env .head_wt/backend/ && cp frontend/.env .head_wt/frontend/ && cd .head_wt/backend && python ../audit/iterations/2026-10-08-P08-tag-printer-verify/repro_p08.py` → [head_before_patch.txt](head_before_patch.txt) `pass=4 fail=24` (EPC chip ≠ DB, ZPL injeksi, journey tag_printed saat queued, lease tidak ada, sesi lintas kind, tag aktif tanpa roll, href ZPL tanpa entitas).

## Perubahan

- RF-01: `services/epc.py` = satu kontrak — 24 hex uppercase tanpa pemisah (EPC-96 internal "E2…", bukan GS1). `generate_epc` kanonik; encode custom dinormalisasi; ingest/scan/lookup/pick/sample-sale memakai `normalize_reads`/`try_canonical`. Migrasi startup `migrate_epc_canonical` (tag, read, sesi, job) — benturan dilaporkan & tidak dimigrasi; indeks unik parsial `uniq_live_epc` (status active|pending_print) hanya dibuat bila bersih.
- RF-11: `services/zpl_text.zpl_field` — teks label lewat `^FH_` hex-escape (^ ~ _ / Unicode → `_XX`), kontrol/newline dibuang, `^CI28`. `^RFW` memakai `canonical_epc` (ValueError, tidak dipotong); encode EPC invalid → 400.
- RF-10: sesi wajib `kind` (backfill `print_verify` untuk sesi lama). `scan_session` = `$addToSet $each` berprasyarat kind + open + tanpa `saga_lock`; complete membaca snapshot SESUDAH klaim (scan terlambat 400). Endpoint print hanya `print_verify|cycle_count`; loading check hanya lewat `/outbound/loading-check/{id}/scan`. Sesi tak dikenal → 404.
- RF-07: setiap scan membawa `source` (manual|simulated; device hanya lewat `/rfid/ingest` + `session_id`) + pelaku/device di `scan_log`. Sesi berisi simulasi → hasil `simulated`: loading check tidak membuka dispatch, verify cetak tidak mengubah job/journey/identitas, cycle count ditandai `simulated`. Tombol UI berlabel "Simulasi (tidak sah)".
- RF-14: tag dari print job lahir `pending_print`; aktif + journey `tag_printed` baru saat `mark_printed`/ack printer (`on_printed`, only_from — reprint roll stored tidak mundur). Verifikasi job queued ditolak; `verified_with_issues` dapat diulang (revisi). Gagal di item ke-n → tag baru item sebelumnya dicabut.
- RF-15: pull printer = lease atomik per job (`lease{device_id, attempt_id, expires_at}` TTL 300 dtk, kapabilitas rfid/qr). Ack wajib printer pemilik + attempt aktif; gate/printer lain/attempt lama/lease kedaluwarsa ditolak; replay attempt sama idempoten.
- IX-12: kompensasi attach gagal = retire tag DULU lalu hapus roll (crash di antara → roll + tag retired, bukan tag aktif yatim); `retire_orphan_tags` di startup menyapu sisa. Counter tugas tidak disentuh.
- UX-02: Unduh ZPL lewat apiClient (`responseType: blob`, membawa X-Entity-Id terpilih) → object URL dicabut.

## Regression

- `repro_p08.py` → [after_patch.txt](after_patch.txt) `pass=43 fail=0`.
- Ulang: `repro_p07.py` 18/18, `repro_p07b.py` 16/16 (pemanggil scan disesuaikan ke `scan_session(kind=loading_check)` — invariant RF-10).
- pytest lama `test_iter263_*`, `test_fase_sl_*` merah karena fixture/seed (site Rancamalang, user md@, task id tetap) — bukan dari patch ini.

## Batas

- RF-07: scan `manual` (EPC diketik/ditempel) tetap sah tetapi tercatat pelaku; kebijakan "wajib device" per gudang belum ada (keputusan operasional).
- RF-15: hasil per-label/write-readback dari printer belum disimpan (ack per job).
- RF-01: data produksi dengan benturan EPC kanonik butuh keputusan manual (dilaporkan di log startup).
- Middleware printer lama yang ack tanpa `attempt_id` kini ditolak 400 — perlu update middleware.
