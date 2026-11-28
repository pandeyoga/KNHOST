# Kas & Bank bagian 3 — kas kasir, dana tetap kas kecil, opname kas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jenis kas ketiga Kas Kasir (akun sendiri), dana tetap per rekening kas kecil dengan isi ulang terkunci, dan opname
kas dengan selisih yang disetujui orang kedua.

**Architecture:** T1 fondasi (akun, jenis kas, pengaturan, bidang rekening) lebih dulu; lalu T2 (C1 alur + C2 dana tetap)
dan T3 (C3 opname) **sejajar di worktree terpisah** (perintah pemilik 28 Nov: subagent lebih dari satu boleh), digabung
pengendali; T4 layar (dua agen sejajar, worktree); T5 uji/gate/tangkapan/laporan.

**Tech Stack:** FastAPI, Motor/MongoDB (uji mongomock `backend/tests_mem`), React (craco/jest).

**Spec:** `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md`.

## Global Constraints

- Bahasa Indonesia untuk teks layar, galat, komentar baru, commit. Wewenang = izin; nilai bisnis = pengaturan.
- Tanpa migrasi saat menyala yang menulis data; rekening lama tidak dikonversi; PT yang tidak memakai fitur baru berperilaku
  persis seperti sekarang.
- Akun bawaan baru: `1-1105 Kas Kasir` (aset, is_cash), `1-1290 Piutang Karyawan – Kekurangan Kas` (aset),
  `6-9200 Selisih Kas` (beban). `cash_type` baru `kas_kasir` → induk `1-1105`, kunci pemetaan `kas_bank.kas_kasir`.
- Satu pintu kas `cash_ledger.create_cash`; satu pembantu akun kas `gl_service.akun_kas`; penjaga
  `verify_akun_kas_satu_pintu` juga menjaga `1-1105`.
- Kontrol `kontrol.selisih_kas` bawaan "2" (masuk bawaan `kontrol.admin_tetap_dua_orang`); pengaturan
  `kas.opname_kasir_hari` 1, `kas.opname_kas_kecil_hari` 7, `kas.opname_kas_besar_hari` 7.
- Opname: koleksi `cash_counts`, nomor `OPK-` per PT, status `selesai|menunggu_persetujuan|disetujui|ditolak`.
- Uji: `python -m pytest backend/tests_mem/<file> -n 0 -q -p no:cacheprovider`; jest `CI=true yarn test --watchAll=false <file>`.
- Jangan sentuh `deploy/`, `.env`, `memory/GATE_RECEIPT.*`, `frontend/yarn.lock`; `ENTITY_REGISTRY.md`/`CODEBASE_MAP.md`
  hanya di T5. Commit diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` dan
  `Claude-Session: https://claude.ai/code/session_01WetgRZMZjzXfrP6Zn8k4UK`.

## Review Focus

1. **PT tanpa rekening kas kasir** → kwitansi tunai persis seperti sekarang (kas kecil tunggal). (T2)
2. **Isi ulang dihitung ulang server** saat dibuat; dua isi ulang bersamaan untuk satu rekening → satu Pindah Dana. (T2)
3. **Opname saat ada kas tercatat di sela hitung dan putus** → saldo buku dipotret saat dihitung; jurnal selisih memakai
   selisih yang disetujui, bukan dihitung ulang diam-diam. (T3)
4. **Setujui selisih ganda/bersamaan** → satu kas penyesuaian. (T3)
5. **PT dalam mode akun per rekening** (Kas & Bank 1) → kas kasir/penyesuaian opname ke sub-akun rekening; saldo sub-akun
   = buku kas rekening. (T1–T3)

---

### Task 1: Fondasi — akun, jenis kas kasir, pengaturan, bidang rekening

**Files:** `backend/services/gl_service.py` (bagan bawaan + konstanta `ACC_KAS_KASIR`, `ACC_PIUTANG_KURANG_KAS`,
`ACC_SELISIH_KAS`; `akun_kas` mode lama untuk kas_kasir), `backend/services/gl_mapping_registry.py` (`kas_bank.kas_kasir`,
`kas_bank.selisih_kas`, `kas_bank.piutang_kurang_kas`), `backend/services/bank_service.py` (`CASH_TYPES` + kas_kasir,
`account_cash_type`, bidang `dana_tetap` ≥ 0 dan `location_id` opsional di rekening kas kecil, jenis kas terkunci bila
rekening punya kas), `backend/schemas_finance.py`, `backend/services/cash_ledger.py` (label "Kas kasir", `cash_type_for`,
`jenis_kas_akun`), `backend/services/cash_account_mode.py` (`INDUK` kas_kasir → 1-1105), `backend/services/report_basis.py`
(`kode_kas` ikut kas_kasir), `scripts/guardrails/verify_akun_kas_satu_pintu.py` (+1-1105), `backend/config_catalog_kontrol.py`
(`selisih_kas`), katalog pengaturan kas (`kas.opname_*_hari`), `configKeyIndex.json`; uji `backend/tests_mem/test_KB3_1_fondasi.py`.

**Interfaces (produces):** konstanta di atas; `bank_service.account_cash_type(acc) ∈ {kas_besar, kas_kecil, kas_kasir}`;
`await gl_service.akun_kas(eid, account_id, "kas_kasir")` → `1-1105` (mode lama, dengan pemetaan PT) atau sub-akun rekening;
rekening `dana_tetap: float`, `location_id: str`; pengaturan dibaca lewat helper config yang ada.

- [ ] **Step 1 (uji gagal):** rekening baru tunai `cash_type="kas_kasir"` → saldo awal & kas ke 1-1105 (PT mode lama) / ke
  sub-akun `1-1105-NN` (PT aktif); ubah `cash_type` rekening yang sudah punya kas → 400 berkalimat; `dana_tetap` negatif →
  422/400; `kode_kas` memuat 1-1105; penjaga menolak `"1-1105"` harfiah di baris jurnal (swa-uji); regresi: rekening
  kas_kecil/kas_besar & semua jurnal kas tidak berubah (rekam dari HEAD); kunci pengaturan baru terdaftar (KFT1/4/6).
- [ ] **Step 2–4:** RED → implementasi → GREEN + KB1_*, KB2_*, kas/bank terkait.
- [ ] **Step 5: Commit** `feat(kas-bank): fondasi kas kasir, akun selisih kas & piutang kekurangan kas, dana tetap rekening`

### Task 2: C1 alur kas kasir + C2 dana tetap & isi ulang (sejajar dengan T3, worktree)

**Files:** `backend/services/ar_receipt_service.py` (tunai → kas kasir tunggal PT bila ada, selain itu perilaku lama),
`backend/services/interco_money_service.py` (kas kasir ditolak seperti kas kecil), baru
`backend/services/petty_float_service.py` (`posisi(account_id)`, `isi_ulang(account_id, sumber_account_id, actor)`),
rute (berkas router baru `backend/routers/petty_float.py`: `GET /api/kas-kecil/dana-tetap?entity_id=`,
`GET /api/kas-kecil/dana-tetap/{account_id}`, `POST /api/kas-kecil/dana-tetap/{account_id}/isi-ulang`),
`backend/services/fund_transfer_service.py` (terima tanda `isi_ulang_kas_kecil` + potret rincian, nominal terkunci);
uji `backend/tests_mem/test_KB3_2_kasir_dana_tetap.py`.

**Interfaces:** posisi = `{account_id, dana_tetap, saldo_buku, panjar_belum_lpj, usulan_isi_ulang, rincian:[…],
isi_ulang_menunggu?}`; usulan = dana_tetap − saldo_buku − panjar_belum_lpj (≤ 0 → 0); isi ulang → Pindah Dana sekali jalan
(sumber bank/kas besar PT sama) bertanda `jenis: "isi_ulang_kas_kecil"`, nominal = usulan server.

- [ ] **Step 1 (uji gagal):** kwitansi tunai PT berkas kasir → rekening kasir; PT tanpa kasir → kas kecil (regresi);
  antar-PT kas kasir → 400; posisi: dana tetap 2.000.000, panjar dicairkan 500.000 belum LPJ, LPJ disetujui 300.000, kas
  keluar manual 200.000 → usulan 500.000; isi ulang → Pindah Dana 500.000 bertanda; nominal dari klien diabaikan/ditolak;
  isi ulang kedua saat yang pertama menunggu → 409; dua isi ulang bersamaan → satu Pindah Dana; dana tetap 0 → isi ulang
  400; PT aktif mode per rekening → saldo sub-akun = buku kas.
- [ ] **Step 2–4:** RED → implementasi → GREEN + KB1_4, kas kecil (`cash_advance`), AR receipt, F1 terkait.
- [ ] **Step 5: Commit** `feat(kas-bank): kwitansi tunai ke kas kasir, dana tetap kas kecil dan isi ulang terkunci`

### Task 3: C3 opname kas (sejajar dengan T2, worktree)

**Files:** baru `backend/services/cash_count_service.py`, `backend/routers/cash_counts.py` (`GET/POST /api/cash-counts`,
`GET /api/cash-counts/{id}`, `POST /api/cash-counts/{id}/approve|reject`), `backend/indexes.py` (nomor `OPK-` unik per
PT), `entity_scope`, `approval_kinds.py` + `approval_backlog_service.py` QUEUES + `verify_approval_queues` DOOR_QUEUE
(view `cash-counts`), `routers/saga_locks.py` LOCKED_COLLECTIONS (bila klaim dipakai), `work_desk_service.py` (antrean
Meja Keuangan `opname_kas_jatuh_tempo`), `notification_service.py` (selisih menunggu → pemegang `cash.approve`; diputus →
penghitung); uji `backend/tests_mem/test_KB3_3_opname.py`.

**Interfaces:** `buat(payload{account_id, jumlah_fisik, pecahan?, catatan}, actor)` → potret `saldo_buku` + `selisih`;
`setujui(id, {perlakuan: "selisih_kas"|"piutang_karyawan", karyawan_id?}, actor)` → `create_cash(ref_type="cash_count",
ref_id=id, contra_account_code=ACC_SELISIH_KAS|ACC_PIUTANG_KURANG_KAS)` arah sesuai tanda selisih; `tolak(id, alasan, actor)`.

- [ ] **Step 1 (uji gagal):** selisih 0 → `selesai`, nol kas; fisik lebih 50.000 → menunggu → setujui orang lain →
  kas masuk 50.000 Dr kas/Cr 6-9200; kurang 30.000 + piutang karyawan (karyawan wajib) → Dr 1-1290/Cr kas; lebih + piutang
  karyawan → 400; penghitung menyetujui sendiri → 403 (juga Admin); setujui ganda bersamaan → satu kas; kas dicatat di sela
  hitung & putus → kas penyesuaian = selisih yang dipotret; tolak beralasan → `ditolak`, nol kas; rekening bank (bukan
  tunai) → 400; antrean meja: rekening kasir tanpa opname > 1 hari & punya kas → muncul; kas kecil 7 hari; rekening tanpa
  kas → tidak; PT aktif per rekening → sub-akun = buku kas.
- [ ] **Step 2–4:** RED → implementasi → GREEN + antrean persetujuan, meja, notifikasi, KB1/KB2 terkait.
- [ ] **Step 5: Commit** `feat(kas-bank): opname kas dengan selisih disetujui orang kedua`

### Task 4: Layar (dua agen sejajar, worktree; tanpa tinjauan per tugas — R10)

- **4a** Rekening & Kas Kecil: form rekening baru pilih jenis kas (Kas Kasir / Kas Kecil untuk tunai), jenis terkunci bila
  ada kas, dana tetap & lokasi di rekening kas kecil; kartu rekening menampilkan jenis/dana tetap/lokasi + aksi "Isi ulang";
  chip **Dana tetap** di Kas Kecil (posisi per rekening, rincian, Isi ulang pop-up pilih rekening sumber, riwayat Pindah Dana
  isi ulang); uji `frontend/src/features/__tests__/kb3DanaTetap.test.js`.
- **4b** Opname: tab tersembunyi **Opname Kas** (`cash-counts`, alias Rekening & Saldo) — daftar, form hitung (jumlah fisik,
  pecahan opsional), putuskan selisih (perlakuan, karyawan); aksi "Opname" di kartu rekening tunai; kartu Meja Keuangan
  "Opname kas jatuh tempo"; pratinjau `OPK-`; notifDocTarget; uji `frontend/src/features/__tests__/kb3Opname.test.js`.
- [ ] jest RED → implementasi → GREEN + suite terkait → commit per agen.

### Task 5: Uji penuh, gate, MongoDB asli, tangkapan, laporan

- [ ] Suite penuh + gate `--ci` sejajar tinjauan seluruh cabang; satu gelombang perbaikan; gate `--quick` di pohon akhir.
- [ ] MongoDB asli `backend/tests/test_bp_KB3_bersamaan.py`: dua isi ulang bersamaan → satu Pindah Dana; dua setujui
  selisih bersamaan → satu kas.
- [ ] Tangkapan di data acuan; laporan `docs/superpowers/plans/2026-11-28-kas-bank-3-hasil.md`; `CODEBASE_MAP.md`,
  `ENTITY_REGISTRY.md`, catatan serah-terima.
