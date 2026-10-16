# IMPLEMENTATION

Commit sumber diuji: patch di atas `08a9009f18250ea31cecca3ddbe0b7a38561bfe4`, kandidat ter-commit `0076f7ea16ddc93d5b01f480768418464c5c3347`. Diff: [../2026-09-30-P01-scope-batch2/p01_combined.diff](../2026-09-30-P01-scope-batch2/p01_combined.diff).
ID/fase: GN-01, GN-02, GN-03, IX-05, IX-07, IX-10 — P01.

Reproduksi HEAD sebelum patch: `repro_p01_scope.py` via HTTPS preview (cookie Secure) → [head_before_patch.txt](head_before_patch.txt) `pass=5 fail=17` (5 = kontrol positif). Fixture: role sintetis `audit_scope_tester` (cash/esign/entity.update/period.unlock/hr.view) + user hanya ent_ksc (A); target ent_kanda (B). Semua terbukti: ledger & reconcile B 200; signatures B 200 + create request B 200; PUT settings scope=B 200 (nilai B berubah) & scope global 200; list/active period-unlock B 200, approve B → `approved`; GN-01 respons user cookie A di-replay ke user cookie B; payload berbeda di-replay; anonim + key di-replay; GN-02 sales subscribe dapat snapshot, sesi expired diterima.
Catatan insiden fixture: run HEAD menulis `system_settings{scope:global}.finance = {}` (efek bug IX-07); dipulihkan ke `DEFAULT_GLOBAL_SETTINGS.finance`, skrip diubah agar memakai nilai yang sama.

Perubahan dan kontrak lintas caller:
- GN-01 `idempotency.py`: identitas = `user_id` dari sesi sah (cookie `session_token`/Bearer, cek expiry); tanpa sesi sah tidak ada lookup/replay. Kunci = key|method|path|user_id|X-Entity-Id; `payload_hash` (query+body) — beda payload → 409 `IDEMPOTENCY_KEY_REUSED`.
- GN-02 `server.py` + `tracking_service`: expiry sesi dicek di WS; subscribe butuh `hr.view` (sama dgn HTTP Live Map); subscriber menyimpan scope entitas; snapshot & broadcast disaring; tiap ping sesi/izin divalidasi ulang, dicabut → koneksi ditutup. `entity_scope.allowed_entities_for` diekstrak dari `entity_ctx` (satu sumber HTTP/WS).
- GN-03 `routers/bank.py`: ledger & reconcile memuat dokumen lalu `guard_doc` entitas aktif; rekening/transaksi grup lama hanya admin/manager (selaras list).
- IX-05 `routers/esign.py`: `_guard_source` (DOC_REGISTRY → dokumen sumber → guard_doc) pada signatures, request, verify; entitas request = pemilik sumber (mismatch body → 400); list signatures difilter entitas.
- IX-07 `routers/settings.py`: scope entitas di-resolve via `resolve_requested_entity` + kunci-tulis entitas; scope global hanya peran lintas-PT.
- IX-10 `period_unlocks`: list/active memakai `resolve_scope_ids`; approve/reject memuat record dan wajib entitas ∈ penugasan (404).

Regression test: `repro_p01_scope.py` → 22/22 lulus [after_patch.txt](after_patch.txt). `pytest tests/test_sesi14_idempotency.py tests/test_g5_poc.py tests/test_sesi16_ar_receipt.py` → 15 passed.
Kontrol yang dipertahankan: akses entitas sendiri (ledger, reconcile, signatures) tetap 200; replay user sama + payload sama tetap berfungsi; manager tetap menerima snapshot.
Data historis/migration dry-run: tidak ada migrasi data. Kunci idempotensi lama (format lama) tidak lagi cocok → paling buruk 1 eksekusi ulang aksi offline yang sedang antre saat deploy (TTL 7 hari).
Batas pengujian: GN-01 pemulihan durable saat proses mati di tengah (status in_progress tertahan → 409 sampai TTL) BELUM ditangani; GN-02 pencabutan efektif pada ping berikutnya, bukan instan; broadcast manager admin tanpa entitas pada posisi (`entity_id` kosong) tidak terlihat oleh siapa pun (konsisten dgn HTTP); IX-07 perubahan via Pusat Pengaturan (config_resolver) tidak diuji di batch ini.
ID siap divalidasi / tertunda: keenam ID siap divalidasi setelah SHA tercatat; cabang GN-01 durable-recovery tetap terbuka.
