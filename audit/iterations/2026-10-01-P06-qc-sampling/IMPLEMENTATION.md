# IMPLEMENTATION

Commit sumber diuji: patch di atas `0076f7ea16ddc93d5b01f480768418464c5c3347` (working tree; SHA kandidat diisi setelah commit platform). Diff: [../2026-10-01-P02-core-roll/session2_combined.diff](../2026-10-01-P02-core-roll/session2_combined.diff).
ID/fase: PG01 (keputusan pemilik opsi C) + IX-15 — P06.

Reproduksi HEAD sebelum patch: [head_before_patch_ix15.txt](head_before_patch_ix15.txt) — keputusan 4 dari 30 m tanpa inspeksi → task `completed`, sisa karantina 26 m (tertutup). PG01: di HEAD tidak ada rencana/cakupan inspeksi sama sekali (keputusan qty langsung).

Perubahan dan kontrak lintas caller:
- `qc_service`: `qc_plan` pada task (`mode` all|sampling, `sample_pct`, `sample_min`, `planned_by/at`, riwayat `qc_plan_history`); `qc_coverage` = roll terinspeksi (4-Point `inspection.inspected_at` atau grade manual `manager_override`) vs wajib (all = semua roll; sampling = max(min, ceil(pct×n))). `set_qc_plan` hanya saat `qc_pending`, validasi mode/pct/min.
- `process_qc_decision` (sebelum claim/mutasi): IX-15 — terima+tolak wajib = seluruh qty karantina; PG01 — cakupan wajib terpenuhi. Hasil menyimpan `qc_coverage` + `decision_applies_to_uninspected` (keputusan sampel berlaku eksplisit untuk sisa lot).
- API: `GET/PUT /inbound/qc/tasks/{task_id}/plan` (wms.view / wms.update + guard entitas).
- UI `QcPlanPanel` di modal Inspeksi QC: pilihan **Cek semua** / **Sampling** (% roll per lot, minimal roll), Simpan rencana, cakupan "Terinspeksi x/y · wajib z", tombol ke inspeksi roll; tombol simpan keputusan nonaktif sampai cakupan terpenuhi dan seluruh qty dialokasikan.

Regression test: `repro_pg01_ix15.py` 13/13 [after_patch.txt](after_patch.txt). UI Playwright admin 1920: panel tampil, mode Sampling memunculkan input + Simpan rencana, cakupan 1/1 terpenuhi.
Kontrol yang dipertahankan: validasi over-allocation, disposisi reject, claim saga `qc_pending`.
Data historis/migration dry-run: task lama tanpa `qc_plan` = Cek semua; task `qc_pending` yang ada kini butuh inspeksi per roll (atau grade manual) sebelum keputusan — perubahan perilaku yang disengaja sesuai PG01.
Batas pengujian: pemilihan roll sampel tidak diacak/ditentukan sistem (inspektur memilih); inspeksi dua inspector bersamaan & retry belum diuji; reopen inspeksi (IX-09) belum ditangani.
ID siap divalidasi / tertunda: IX-15 siap divalidasi setelah SHA tercatat; PG01 terimplementasi.
