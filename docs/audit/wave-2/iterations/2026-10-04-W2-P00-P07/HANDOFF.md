# Handoff untuk auditor — Wave 2, iterasi 2026-10-04 (P00–P07)

- **Repository/branch/SHA kandidat:** `pandeyoga/KNHOST` `main`. Basis `8934e12`. Perubahan aplikasi belum di-commit ke `main`; SHA kandidat = hasil `KN_COMMIT_MSG="Wave2 P00-P07" bash scripts/git_sync_check.sh --fix` (lalu Save to GitHub). Validasi wajib pada SHA tersebut, bukan pada snapshot audit `ea874d3b`.
- **Fase/ID siap divalidasi:** P00–P07, seluruh 25 ID W2-001…W2-025 = `ready_for_validation` (tracker aktif `tracker.json`).
- **Fase/ID terbuka:** P08 (W2-REQ-01…09) `not_started` — kebutuhan bisnis/SOP yang perlu keputusan pemilik (lihat di bawah). P09 menunggu auditor.
- **Perubahan Wave1 terkait (tidak diubah statusnya):** AX-04 (dasar W2-008/009), GN-06 (W2-024), GN-12 (W2-021 laporan keuangan), P20 APAR-02 (W2-016), CX-13 (makloon receive), FN-10/GN-11 (pola recovery W2-015/020).
- **Lokasi implementasi/regression:** `iterations/2026-10-04-W2-P00-P07/` — `IMPLEMENTATION.md` (tabel akar masalah per ID), `regression_w2.py` (25/25), `regression_w2_http.py` (6/6), `test_w2_targeted.py` (8/8, agen uji), `replay_obs/` (replay baseline di salinan `iterations/2026-10-04-W2-replay/`).
- **Schema/index/config:** indeks unik parsial `rfid_incidents.dedupe_key` (otomatis). Field baru tercantum di IMPLEMENTATION.md. Tidak ada migrasi data yang dijalankan; data historis terdampak perlu dry-run + persetujuan Finance.
- **Lingkungan & perintah:** backend lokal (supervisor), Mongo `test_database` seed demo; replay memakai mongod sintetis port 27919. `python scripts/verify_data_integrity.py` = PASS 246 · FAIL 2 (KANDA/SO-00001 seed lama, sama dengan baseline P21).
- **Belum divalidasi:** browser UAT selain tombol batal tagihan makloon; hardware RFID; GRN HTTP end-to-end multi-gudang (W2-003); replay `wave2_qc_flow`, `wave2_cash_refund`, `wave2_ar` terblokir fixture lama (bukan regresi patch — lihat `replay_obs/*.fixture_blocked.txt`).
- **tools/check_package.py:** PASS.

## P08 — kebutuhan klien (belum dikerjakan; butuh keputusan)
| ID | Yang perlu diputuskan/disediakan sebelum implementasi |
|---|---|
| REQ-01 | Apakah perlu field `performed_by` terpisah dari `recorded_by` di sampling & hak per jenis uji. |
| REQ-02 | Kamus nama/stage/warna/lot disepakati + rencana migrasi legacy (preview & laporan konflik). |
| REQ-03 | Daftar uji wajib per spesifikasi/lini sebagai hard gate rilis SKU hasil MD. |
| REQ-04 | Angka utama POV sales (available/reserved/incoming grup tanpa owner). |
| REQ-05 | Meja kerja PO lintas entitas dgn buyer eksplisit. |
| REQ-06 | Alur tindak lanjut selisih PO (tunggu/revisi/short-close) + penanggung jawab MD/Finance. |
| REQ-07 | Reservasi bahan saat rencana/create MKO (resep/yield). |
| REQ-08 | Kewajiban tag store & cross-dock; UAT multi-gudang (tautkan RFID-03). |
| REQ-09 | Aturan pemilihan/pemotongan roll (FEFO vs kombinasi) dan persetujuan pembulatan. |
