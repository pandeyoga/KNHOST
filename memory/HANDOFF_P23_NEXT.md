# HANDOFF — P23 (disiapkan 2026-10-04, akhir sesi Wave-2 P00–P07) → sesi berikutnya

> Bahasa user: **Indonesia**. Setup lingkungan: `memory/HANDOFF_P16_2026-10-09.md` §1 (atau `bash .restore_env.sh`; CORS_ORIGINS eksplisit, `KN_DISABLE_SCHEDULER=1`).
> Wajib akhir sesi: `KN_COMMIT_MSG="..." bash scripts/git_sync_check.sh --fix` (agen sesi ini TIDAK menjalankannya — git write), lalu user **Save to GitHub**.

## 0. Status
- Paket Gelombang 2 diimpor ke `docs/audit/wave-2/` (baseline tidak diubah; `tools/check_package.py` PASS).
- **25/25 temuan W2 = ready_for_validation** (tracker `docs/audit/wave-2/tracker.json`); fase P00–P07 ready_for_validation.
- Bukti: `docs/audit/wave-2/iterations/2026-10-04-W2-P00-P07/` (IMPLEMENTATION.md, HANDOFF.md, regression 25/25 + HTTP 6/6, test agen 8/8 `backend/tests/test_w2_targeted.py`).
- Integritas data: PASS 246 · FAIL 2 (seed lama KANDA/SO-00001).
- Alat baru: `docs/audit/wave-2/tools/set_status.py` (implementer hanya boleh sampai ready_for_validation).

## 1. Berikutnya
1. **Auditor**: validasi W2 pada SHA commit sesi ini (`PROMPT_VALIDASI.md`).
2. **P08 kebutuhan klien W2-REQ-01..09** — butuh keputusan pemilik (daftar di HANDOFF iterasi). Tanyakan dulu, jangan menebak kebijakan.
3. **COMM-04** (jurnal Beban Pemasaran kampanye) masih prioritas dari P22 — rencana di `memory/HANDOFF_P22_NEXT.md` §1.
4. Migrasi/rekonsiliasi data historis (dry-run dulu): retur QC unit kg lama, berat ganda roll split lama, payroll paid tanpa buku kas, kwitansi murni deposit tanpa jurnal reklas, refund final tanpa kas, partial makloon tanpa gudang.
5. Adaptasi fixture replay yang terblokir (qc_flow: rencana inspeksi wajib; sales_flow: reservasi saat verifikasi; ar: seed COA).

## 2. Jangan diregresi
Kontrak baru: resolver owner = otorisasi (tanpa fallback B); reject opname CAS; reads RFID ber-scope; guard lini R&D di detail; GRN tidak done bila ada roll `receiving`; retur QC qty satuan PO; split membagi berat; makloon costing = panjang terukur, gudang divalidasi & gudang kiriman sebagian disimpan; tagihan jasa makloon tidak bisa dibatalkan generik; potong bon atomik; deposit direservasi; void receipt CAS; refund tidak final tanpa kas; payroll catat buku kas & akun wajib kas/bank; insiden RFID CAS + dedupe unik.
