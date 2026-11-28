# Kas & Bank bagian 4 — batas uang muka karyawan & tenggat LPJ, akun uang muka pemasok terpisah — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PD baru tertahan selama pemegangnya masih memegang PD terbuka (bawaan 1), tiap PD cair bertenggat LPJ (bawaan 7
hari) yang terlihat dan diingatkan; uang muka pemasok punya akun sendiri `1-1410` yang dinyalakan per PT lewat pindah saldo
disetujui orang kedua.

**Architecture:** T1 fondasi (akun, kunci pemetaan, akun kontrol, pengaturan, pembantu akun uang muka pemasok + semua jalur
pemasok dialihkan ke pembantu — tanpa perubahan perilaku sebelum PT pindah); lalu T2 (C7, PD) dan T3 (C8, pindah saldo &
pencocokan) **sejajar di worktree terpisah**, digabung pengendali; T4 layar (dua agen sejajar); T5 uji/gate/tangkapan/laporan.

**Tech Stack:** FastAPI, Motor/MongoDB (uji mongomock `backend/tests_mem`), React (craco/jest).

**Spec:** `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` (§7 keputusan builder, §7.9 jawaban builder check).

## Global Constraints

- Bahasa Indonesia untuk teks layar, galat, komentar baru, commit. Wewenang = izin; nilai bisnis = pengaturan.
- Tanpa migrasi saat menyala yang menulis data (penanda aktif sekali tulis dikecualikan); PD & uang muka lama tidak diubah;
  PT yang belum pindah membukukan uang muka pemasok persis seperti sekarang (1-1400).
- Akun bawaan baru `1-1410 Uang Muka Pemasok` (aset, induk 1-1000), kunci pemetaan `hutang.uang_muka_pemasok` (bawaan
  1-1410), akun kontrol PK-36 dengan buku pembantu `uang_muka_pemasok` (dokumen pengganti: Kasus Keuangan / Kontrabon).
  1-1400 tetap uang muka karyawan (`kas_bank.uang_muka_karyawan`) + biaya dibayar dimuka.
- Pengaturan: `kas.pd_terbuka_maks` bawaan **1** (0 = tanpa batas), `kas.lpj_tenggat_hari` bawaan **7** (1–90), kontrol
  `kontrol.pindah_uang_muka_pemasok` bawaan **"2"** (masuk bawaan `kontrol.admin_tetap_dua_orang`).
- Kalimat 409 ajukan PD: "Anda masih memegang uang muka PD-… (Rp …, LPJ jatuh tempo …). Selesaikan LPJ-nya dulu sebelum
  mengajukan uang muka baru." (pemegang karyawan: "… {nama} masih memegang …").
- Jurnal lewat `gl_service`; kas lewat `cash_ledger.create_cash`; urutan PERIKSA → KLAIM → EFEK → SELESAI.
- Uji: `python -m pytest backend/tests_mem/<file> -n 0 -q -p no:cacheprovider`; jest `CI=true yarn test --watchAll=false <file>`.
- Jangan sentuh `deploy/`, `.env`, `memory/GATE_RECEIPT.*`, `frontend/yarn.lock`, `.superpowers/` (jangan di-commit);
  `ENTITY_REGISTRY.md`/`CODEBASE_MAP.md` hanya di T5. Commit diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  dan `Claude-Session: https://claude.ai/code/session_01WetgRZMZjzXfrP6Zn8k4UK`.

## Review Focus

1. **Finance mengetik PD untuk dua karyawan berbeda** → masing-masing boleh punya satu PD terbuka; batas per pemegang, bukan
   per pembuat. (T2)
2. **PD cair sebelum pembaruan** → tenggat dari tanggal fitur aktif + N; tidak ada yang lewat tenggat di hari pembaruan. (T2)
3. **Dua ajukan bersamaan oleh pemegang yang sama** → satu lolos, satu 409 (kunci per pemegang, bukan periksa-lalu-tulis). (T2)
4. **Kontrabon berpotongan uang muka belum dibayar saat PT mau pindah** → siapkan ditahan berkalimat; sesudah dibayar,
   pindah menghitung potongan terjurnal → 1-1410 tidak pernah negatif. (T3)
5. **PT belum pindah** → semua jurnal jalur pemasok identik dengan sebelum (1-1400), termasuk potongan kontrabon dan refund
   kasus. (T1)

---

### Task 1: Fondasi — akun 1-1410, akun kontrol, pengaturan, pembantu akun uang muka pemasok

**Files:** `backend/services/gl_service.py` (bagan bawaan `1-1410`, konstanta `ACC_UANG_MUKA_PEMASOK`, pembantu
`akun_uang_muka_pemasok`; potongan kontrabon `supplier_advance` ≈2450-2466 memakai pembantu), baru
`backend/services/supplier_advance_mode.py` (`aktif(eid) -> bool`, `aktif_sejak(eid) -> str`, `nyalakan(eid, oleh) -> str`
sekali tulis per PT, pola `cash_account_mode`), `backend/services/gl_mapping_registry.py` (`hutang.uang_muka_pemasok`,
`control=` ledger `uang_muka_pemasok`), `backend/services/ap_payment_service.py` (≈160-190 lebih bayar `ap_advance`),
`backend/services/payment_variance_service.py` (≈1288,1347,1391), `backend/services/finance_case_actions.py` (lebih bayar
≈1057-1083, refund ≈1089-1103, dry-run ≈575-594), `gl_service._cash_out_contra` cabang `ap_advance` (≈3644), katalog
pengaturan (`kas.pd_terbuka_maks`, `kas.lpj_tenggat_hari` di `config_catalog_finance.py` dekat `finance.lpj_wajib_lampiran`;
`kontrol.pindah_uang_muka_pemasok` di `config_catalog_kontrol.py`), `configKeyIndex.json` (bangkitkan), baru
`scripts/guardrails/verify_akun_uang_muka_pemasok.py` (pola `verify_akun_kas_satu_pintu`: tolak `ACC_UANG_MUKA` / "1-1400"
harfiah di modul & fungsi jalur pemasok; swa-uji); uji `backend/tests_mem/test_KB4_1_fondasi.py`.

**Interfaces (produces):** `ACC_UANG_MUKA_PEMASOK = "1-1410"`; `await gl_service.akun_uang_muka_pemasok(entity_id) -> str`
(PT belum pindah → `ACC_UANG_MUKA`; pindah → akun pemetaan PT `hutang.uang_muka_pemasok`); `supplier_advance_mode.aktif/
aktif_sejak/nyalakan`; pengaturan dibaca lewat `config_resolver.value_of` dengan konteks PT (pola
`cash_advance_service._nilai_pengaturan`).

- [ ] **Step 1 (uji gagal):** PT belum pindah: lebih bayar tagihan (`ap_advance`), selisih bayar, kasus lebih bayar &
  refund, potongan kontrabon → semua baris jurnal 1-1400 identik dengan rekaman HEAD; PT dinyalakan lewat
  `supplier_advance_mode.nyalakan` (uji langsung) → jalur yang sama memakai 1-1410; uang muka karyawan (PD cair, LPJ,
  kembalikan sisa) tetap 1-1400 di kedua PT; jurnal manual ke 1-1410 ditolak (akun kontrol) dengan kalimat dokumen pengganti;
  `nyalakan` kedua kali tidak menggeser `aktif_sejak`; pengaturan & kontrol baru terdaftar (KFT1/KFT4/KFT6); penjaga menolak
  `"1-1400"` harfiah di jalur pemasok (swa-uji merah).
- [ ] **Step 2–4:** RED → implementasi → GREEN + uji terkait (`test_g3_variance_poc`, `test_g9_case_poc`,
  `test_g7_contrabon_poc` bila jalan di mongomock, `tests_mem/test_review_s5_uang_muka_per_pt.py`, `test_PK24_kas_kecil.py`,
  KFT1/4/6, KB1–KB3).
- [ ] **Step 5: Commit** `feat(kas-bank): fondasi akun uang muka pemasok, pengaturan batas & tenggat uang muka karyawan`

### Task 2: C7 — pemegang PD, batas PD terbuka, Batalkan PD, tenggat LPJ (sejajar dengan T3, worktree)

**Files:** `backend/services/cash_advance_service.py`, `backend/schemas_cash_advance.py`, `backend/routers/cash_advances.py`
(baru `POST /api/cash-advances/{id}/cancel {alasan}`; `GET /api/cash-advances/karyawan?entity_id=&q=` izin
`cash_advance.create`; daftar/rincian membawa `pemegang`, `lpj_jatuh_tempo`, `tenggat_status`, `bisa_ajukan`/`alasan_ajukan`),
`backend/services/work_desk_service.py` (antrean `lpj_uang_muka_lewat_tenggat`), `backend/services/notification_service.py`
(`notify_lpj_tenggat(pd, jenis: "h-1"|"lewat")`, dedupe per PD per jenis), penjadwal (pola Lapor Bayar LB-T5: cari
`batas_bayar`/pengingat di `backend/services/` dan `server.py`), penanda aktif `kb4_lpj_tenggat_aktif_sejak` (pola
`cash_count_service.ensure_aktif_sejak`, panggil di startup), kunci per pemegang (pola `petty_float_service._kunci`, koleksi
`cash_advance_locks`); uji `backend/tests_mem/test_KB4_2_pd.py`.

**Interfaces:** `pemegang = {jenis: "pengguna"|"karyawan", id, nama}` (bawaan pembuat; karyawan = `hr_employees` PT dokumen,
aktif); `kunci_pemegang(pd) -> str` (`"u:"+id` / `"k:"+id`); `pd_terbuka(kunci, *, kecuali_id, hanya_dipegang: bool) ->
list`; `lpj_jatuh_tempo` disimpan saat cair = tanggal buku cair + `kas.lpj_tenggat_hari` (PT dokumen); PD cair tanpa potret →
`max(tanggal cair, aktif_sejak) + N`; `tenggat(pd) -> {jatuh_tempo, status: "aman"|"jatuh_tempo_besok"|"lewat"|"terpenuhi",
hari_lewat}`; `jatuh_tempo_lpj(entity_ids) -> list` untuk meja. Status baru PD `cancelled`.

- [ ] **Step 1 (uji gagal):**
  - ajukan PD kedua oleh pemegang yang sama (PD pertama dalam persetujuan / disetujui / cair / `settled` sisa open) → 409
    kalimat Global Constraints; draf kedua boleh disimpan; PD pertama batal/ditolak/tuntas → ajukan lolos;
  - Finance membuat PD untuk karyawan A dan karyawan B → keduanya lolos; untuk A dua kali → 409 menyebut nama A;
  - `kas.pd_terbuka_maks` = 2 untuk PT → dua lolos, ketiga 409; 0 → tanpa batas;
  - cairkan: pemegang memegang PD lain yang cair & belum tuntas → 409; PD lain hanya disetujui → cair lolos (tidak saling kunci);
  - dua ajukan bersamaan pemegang sama (asyncio.gather) → satu 200, satu 409;
  - Batalkan PD draf/dalam persetujuan/disetujui (pembuat atau `cash_advance.reject`, alasan ≥ 5 huruf) → `cancelled`,
    jejak; PD cair → 409; orang lain tanpa izin → 403;
  - cair → `lpj_jatuh_tempo` = tanggal cair + 7; ubah pengaturan sesudahnya tidak menggeser; PD cair sebelum penanda aktif →
    jatuh tempo = aktif_sejak + 7 (tidak lewat di hari aktif); LPJ diajukan → `terpenuhi`; LPJ ditolak → kembali dihitung;
  - antrean meja `lpj_uang_muka_lewat_tenggat`: PD lewat tenggat muncul (hari lewat, pemegang, PT, nominal); terpenuhi → hilang;
  - pemberitahuan H-1 dan lewat ke pembuat PD, sekali per PD per jenis (jalankan penjadwal dua kali → satu);
  - regresi: alur PD → LPJ → kembalikan sisa → reimburse tidak berubah (PK24).
- [ ] **Step 2–4:** RED → implementasi → GREEN + PK24, kas kecil, petty_float (KB3_2), meja keuangan, notifikasi, antrean.
- [ ] **Step 5: Commit** `feat(kas-bank): batas uang muka karyawan per pemegang, Batalkan PD, tenggat LPJ & pengingat`

### Task 3: C8 — pindah saldo uang muka pemasok per PT & pencocokan uang muka (sejajar dengan T2, worktree)

**Files:** baru `backend/services/supplier_advance_service.py` (`subledger(entity_id) -> {baris:[{supplier_id, nama, dari_kas,
dipotong_terjurnal, dari_kasus, refund_kasus, sisa}], total, advance_balance_info}` — §7.9.1; `penahan(entity_id) -> list` —
§7.9.2), baru `backend/services/supplier_advance_cutover_service.py` + `backend/routers/supplier_advance_cutover.py` (pola
`cash_account_cutover_service` / `routers/cash_account_cutover.py`: `GET /api/uang-muka-pemasok/pindah/{entity_id}/pratinjau`,
`POST …/{entity_id}/siapkan`, `POST /api/uang-muka-pemasok/pindah/{id}/setujui`, `…/tolak`; izin `accounting.manage`;
kontrol `kontrol.pindah_uang_muka_pemasok`; koleksi `supplier_advance_cutovers`, sidik, klaim, `LOCKED_COLLECTIONS`),
jurnal reklas `gl_service.post_pindah_uang_muka_pemasok(...)` (Dr akun pemetaan PT / Cr 1-1400; 0 → tanpa jurnal) lalu
`supplier_advance_mode.nyalakan`, baru `GET /api/uang-muka/terbuka?entity_id=` (karyawan: PD terbuka per pemegang + saldo
1-1400; pemasok: `subledger` + saldo akun pemasok PT; selisih + keterangan), `backend/services/closing_checklist.py` (butir
`uang_muka_cocok`, peringatan, pola `dana_dalam_perjalanan`), pendaftaran (`indexes.py`, `entity_scope`, `doc_number_kinds`
bila bernomor, `saga_locks`); uji `backend/tests_mem/test_KB4_3_pindah_uang_muka_pemasok.py`.

**Interfaces:** pratinjau = `{entity_id, baris, total, saldo_1_1400, penahan:[{jenis, nomor, kalimat}], bisa_siapkan,
alasan}`; siapkan → dokumen `{status: "menunggu", total, sidik, baris}`; setujui (orang kedua) → hitung ulang, sidik beda →
409; jurnal + `nyalakan`; tolak beralasan.

- [ ] **Step 1 (uji gagal):**
  - sub-ledger: lebih bayar 3.000.000 (kas `ap_advance`) − potongan kontrabon terbayar 1.000.000 + kasus lebih bayar 500.000
    − refund kasus 200.000 → sisa 2.300.000 untuk pemasok itu di PT itu; `advance_balance` beda → hanya keterangan;
  - kontrabon berpotongan uang muka belum dibayar → siapkan 409 berkalimat menyebut nomor kontrabon; jurnal uang muka
    pemasok gagal/tertunda → 409; baris pemasok negatif → 409 "periksa kasus";
  - siapkan → setujui oleh orang yang sama → 403 (Admin juga); orang kedua → jurnal Dr 1-1410 / Cr 1-1400 2.300.000,
    penanda PT menyala; sesudahnya potongan kontrabon baru & refund kasus → 1-1410; 1-1410 = sub-ledger;
  - data berubah antara siapkan & setujui → 409; total 0 → setujui tanpa jurnal, penanda menyala; setujui ganda bersamaan →
    satu jurnal; PT lain tidak tersentuh;
  - uang muka terbuka: karyawan = PD terbuka (cair − LPJ terjurnal + sisa belum kembali) vs saldo 1-1400; pemasok vs 1-1410
    (PT pindah) / digabung dengan catatan (PT belum); butir tutup buku `uang_muka_cocok` peringatan (tidak menahan).
- [ ] **Step 2–4:** RED → implementasi → GREEN + KB1_3 (pindah saldo kas), kontrabon, kasus, variance, tutup buku.
- [ ] **Step 5: Commit** `feat(kas-bank): pindah saldo uang muka pemasok per PT dan daftar uang muka terbuka`

### Task 4: Layar (dua agen sejajar, worktree; tanpa tinjauan per tugas)

- **4a** PD: form PD — **Pemegang uang** (bawaan "Saya sendiri"; pemegang izin buat boleh pilih karyawan HR PT itu), tombol
  Ajukan mati + `alasan_ajukan` server; aksi **Batalkan PD** (alasan) di rincian/daftar; lencana tenggat ("LPJ jatuh tempo
  5 Des" · "Lewat 3 hari") di daftar PD & Kas Kecil; kartu Meja Keuangan "LPJ uang muka lewat tenggat"; target pemberitahuan
  ke rincian PD; uji `frontend/src/features/__tests__/kb4Pd.test.js`.
- **4b** Uang muka: **Uang muka terbuka** (chip di Kas Kecil — karyawan & pemasok, saldo akun vs daftar, selisih + keterangan)
  dan **Pindah saldo uang muka pemasok** (letak & komponen mengikuti layar pindah saldo Kas & Bank 1; pratinjau, penahan
  berkalimat, Siapkan/Setujui/Tolak, tombol mati beralasan); butir tutup buku tampil; uji
  `frontend/src/features/__tests__/kb4UangMuka.test.js`.
- [ ] jest RED → implementasi → GREEN + suite terkait → commit per agen; fixture akses dibangkitkan ulang bila izin layar berubah.

### Task 5: Uji penuh, gate, MongoDB asli, tangkapan, laporan

- [ ] Suite penuh + gate `--ci` sejajar tinjauan seluruh cabang; satu gelombang perbaikan; gate `--quick` di pohon akhir.
- [ ] MongoDB asli `backend/tests/test_bp_KB4_bersamaan.py`: dua ajukan PD bersamaan pemegang sama → satu lolos; dua setujui
  pindah saldo bersamaan → satu jurnal.
- [ ] Tangkapan di data acuan; laporan `docs/superpowers/plans/2026-11-28-kas-bank-4-hasil.md` (+ kueri VPS baca-saja: PD
  terbuka per pemegang, PD cair tanpa LPJ, sub-ledger uang muka pemasok per PT & penahan); `CODEBASE_MAP.md`,
  `ENTITY_REGISTRY.md`, catatan serah-terima.
