# Kas & Bank bagian 1 — Rencana Implementasi (akun per rekening, Pindah Dana, pindah saldo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tiap rekening punya sub-akun buku besar (aktif per PT lewat pindah saldo yang disetujui), dokumen Pindah Dana
menggantikan dua kas manual lepas, dan kategori Transfer/Top-up ditutup untuk kas manual baru.

**Architecture:** Satu pembantu akun kas `akun_kas(...)` di `gl_service` dipakai semua jurnal yang menyentuh kas; penanda
mode per PT di `system_settings`; layanan baru `fund_transfer_service.py` (Pindah Dana) dan `cash_account_cutover_service.py`
(pindah saldo per PT). Uang hanya lewat `cash_ledger.create_cash` dan jalur posting yang ada.

**Tech Stack:** FastAPI + Motor/MongoDB, React 19 + Jest.

**Spec:** `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` (keputusan builder §7 butir 1–8).
Inventaris kode: `/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/kasbank_inventaris.md`.

## Global Constraints

- Bahasa Indonesia untuk teks layar, galat, komentar baru, commit. Wewenang = izin; nilai bisnis = pengaturan.
- Pembaruan VPS tidak menulis data nyata: tidak ada migrasi saat menyala yang membuat akun, mengubah rekening, atau
  menjurnal. Mode per rekening hanya menyala lewat persetujuan pindah saldo per PT.
- Kode sub-akun `{induk}-{NN}` (`1-1100-01`, `1-1110-01`), akun khusus PT, `is_cash: True`, `bank_account_id`.
- Satu pintu kas `cash_ledger.create_cash`; satu pembantu akun kas `gl_service.akun_kas(entity_id, account_id, cash_type)`;
  penjaga statis menolak `"1-1100"`/`"1-1110"` di baris jurnal di luar pembantu (pola `scripts/guardrails/verify_cash_single_door.py`).
- Pindah Dana: koleksi `fund_transfers`, nomor `PDN-`, satu PT, izin `cash.create` (buat/terima), `cash.delete` (batal),
  `cash.approve` (setujui); kontrol `kontrol.pindah_dana` bawaan min 1 orang.
- Pindah saldo: izin `accounting.manage` (siapkan) + orang kedua (setujui, `tolak_bila_pelaku_sama`); angka dihitung ulang
  saat setuju + sidik; tanggal = hari persetujuan; ditolak bila ada posting kas gagal/tertunda di PT itu.
- Uji: `python -m pytest backend/tests_mem/<file> -n 0 -q -p no:cacheprovider`; jest `CI=true yarn test --watchAll=false <file>`.
- Jangan sentuh `deploy/`, `.env`, `memory/GATE_RECEIPT.*`, `frontend/yarn.lock`. Commit diakhiri
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` dan `Claude-Session: https://claude.ai/code/session_01WetgRZMZjzXfrP6Zn8k4UK`.

## Review Focus

1. **PT belum aktif** → semua jurnal kas persis seperti sekarang (uji regresi kas, kwitansi, gaji, antar-PT, refund). (Task 1–2)
2. **Kas dicatat di antara Siapkan dan Setujui** → ikut terhitung saat setuju; sidik lama ditolak. (Task 3)
3. **Batal kas lama sesudah PT aktif** → pembalik ke sub-akun; saldo sub-akun = buku kas rekening. (Task 2)
4. **Pindah Dana dalam perjalanan yang dibatalkan sebelum diterima** → kas keluar & biaya dibalik, 1-1150 nol. (Task 4)
5. **Rekening bersaldo negatif / rekening tanpa kas** → jurnal pindah saldo dibalik sisinya / baris nol dilewati. (Task 3)

---

### Task 1: Pembantu akun kas, mode per PT, sub-akun rekening

**Files:** `backend/services/gl_service.py` (`akun_kas`, `_cash_account`), `backend/services/cash_ledger.py`
(`periksa_rekening`), `backend/services/bank_service.py` (`create_account`, `_post_opening`, `cash_position`),
`backend/schemas_finance.py`, `backend/services/report_basis.py` (`kode_kas`), `backend/services/cash_flow_service.py`,
`finance_tower_service.py`, `cashflow_forecast_service.py`, `backend/routers/gl.py` (pemilih refund, tolak jurnal manual
ke sub-akun); baru `backend/services/cash_account_mode.py`; uji `backend/tests_mem/test_KB1_1_akun_rekening.py`.

**Interfaces (produces):**
- `cash_account_mode.aktif(entity_id) -> bool`, `aktif_sejak(entity_id) -> str`, `nyalakan(entity_id, by) -> None`
  (penanda `system_settings {scope:"__kas_per_rekening__"}` kunci = entity_id, tulis sekali).
- `async def buat_subakun(rekening: dict, *, kode: str = "") -> str` — kode `{induk}-{NN}` berikutnya di PT (atau `kode`
  akun PT yang sudah ada, divalidasi: postable, PT sama, belum dipakai rekening lain); tulis `bank_accounts.gl_account_code`;
  akun `is_cash`, `bank_account_id`.
- `async def akun_kas(entity_id: str, account_id: str, cash_type: str) -> str` — mode aktif & rekening ber-`gl_account_code`
  → kode itu; selain itu → akun jenis kas lama (dengan pemetaan PT seperti `_cash_account` hari ini).
- `bank_service.create_account`: rekening baru di PT aktif → `buat_subakun` + saldo awal ke sub-akun.
- `report_basis.kode_kas(entity_id)` → kumpulan akun kas (is_cash + induk) dipakai semua pembaca saldo kas.

- [ ] **Step 1 (uji gagal):** PT tidak aktif → jurnal kas masuk/keluar, saldo awal, posisi kas identik dengan sebelum;
  `nyalakan` → kas baru ke sub-akun, `periksa_rekening` mengisi `account_code` sub-akun; `buat_subakun` urut 01, 02 per PT
  dan per induk; kode akun PT yang sudah ada bisa dipakai; jurnal manual ke sub-akun → 400 berkalimat; posisi kas & arus kas
  menjumlah sub-akun.
- [ ] **Step 2–4:** RED → implementasi → GREEN + `test_PK20_*`, `test_PMT3_*`, `test_KFT2_*`, uji arus kas/menara keuangan
  yang ada.
- [ ] **Step 5: Commit** `feat(kas-bank): akun buku besar per rekening — pembantu akun kas, mode per PT, sub-akun`

### Task 2: Semua jurnal kas lewat pembantu + pembalik kas lama + penjaga statis

**Files:** jalur yang menulis akun kas sendiri (inventaris §1 & builder check): `interco_loan_service.py`,
`interco_charge_service.py`, `fixed_asset_transfer_service.py`, `interco_service.py`, `hr_payroll_pay.py`,
`return_service.py`, `return_roll_settlement_service.py`, `gl_service.py` (penjualan tunai, pembalik kas `post_cash_void` &
pembalik terpadu); baru `scripts/guardrails/verify_akun_kas_satu_pintu.py` (+ swa-uji, daftarkan di `scripts/gate.sh`);
uji `backend/tests_mem/test_KB1_2_jalur_kas.py`.

**Interfaces:** Consumes `akun_kas`. Produces: tidak ada `"1-1100"`/`"1-1110"` harfiah di baris jurnal di luar
`gl_service.akun_kas`/bagan akun bawaan (penjaga merah bila ada; daftar pengecualian eksplisit berkomentar).

- [ ] **Step 1 (uji gagal):** per jalur (pinjaman antar-PT, beban antar-PT, pindah aset, gaji jalur lama, refund retur,
  penjualan tunai) — PT aktif → baris kas ke sub-akun rekening dokumen; PT tidak aktif → akun lama (regresi). Batal kas
  yang dicatat sebelum PT aktif, sesudah aktif → baris kas pembalik ke sub-akun rekening itu; saldo sub-akun = buku kas
  rekening (`bank_service.account_ledger`). Penjaga statis: swa-uji merah pada kode harfiah, hijau pada repo.
- [ ] **Step 2–4:** RED → implementasi → GREEN + suite antar-PT, gaji, retur, kas terkait.
- [ ] **Step 5: Commit** `feat(kas-bank): semua jurnal kas lewat satu pembantu akun kas + penjaga`

### Task 3: Alat pindah saldo per PT (pratinjau, siapkan, setujui)

**Files:** baru `backend/services/cash_account_cutover_service.py`, `backend/routers/cash_account_cutover.py` (daftar di
`server.py`), indeks/koleksi `cash_account_cutovers`, `posting_registry.py` (sumber jurnal `pindah_saldo_kas`), butir
`entity_scope`; uji `backend/tests_mem/test_KB1_3_pindah_saldo.py`.

**Interfaces (produces):**
- `async def pratinjau(entity_id: str) -> dict` → `{rekening: [{id, nama, cash_type, akun_tujuan, akun_tujuan_baru: bool,
  saldo_buku, asal: [{akun, jumlah}]}], kas_tanpa_rekening: {tunggal: [...], tetap: jumlah}, posting_gagal: int,
  baris_jurnal: [...], sidik: str}` (tanpa tulisan; asal dari baris jurnal per kas rekening + saldo awal).
- `async def siapkan(entity_id, pilihan_akun: dict, actor) -> dict` (409 bila posting gagal > 0 atau PT sudah aktif atau usulan
  menunggu; buat sub-akun; simpan usulan `menunggu`).
- `async def setujui(usulan_id, sidik: str, actor) -> dict` (orang kedua; hitung ulang; sidik beda → 409 "Angka berubah,
  muat ulang"; jurnal `pindah_saldo_kas` bertanggal hari ini + `account_id` kas tanpa rekening tunggal + `nyalakan`, satu
  langkah berklaim) dan `tolak(usulan_id, alasan, actor)`.
- Rute: `GET /api/kas-per-rekening/{entity_id}/pratinjau`, `POST …/siapkan`, `POST /api/kas-per-rekening/usulan/{id}/setujui|tolak`,
  `GET /api/kas-per-rekening/usulan`.

- [ ] **Step 1 (uji gagal):** pratinjau = buku kas rekening per akun asal (termasuk saldo awal di akun berbeda dan pemetaan
  PT); siapkan ditolak bila posting kas gagal; kas baru sesudah siapkan ikut terhitung saat setuju; sidik lama → 409; setujui
  oleh penyiap → ditolak; setujui → jurnal seimbang, akun lama PT untuk rekening = 0, sub-akun = buku kas, mode menyala,
  kas tanpa rekening tunggal ber-`account_id`; rekening negatif → sisi dibalik; rekening nol dilewati; setujui ganda → satu jurnal.
- [ ] **Step 2–4:** RED → implementasi → GREEN.
- [ ] **Step 5: Commit** `feat(kas-bank): alat pindah saldo per PT — pratinjau, siapkan, setujui dengan hitung ulang`

### Task 4: Pindah Dana (server)

**Files:** baru `backend/services/fund_transfer_service.py`, `backend/routers/fund_transfers.py`, `cash_ledger.REF_LABEL`
(`fund_transfer`), `posting_registry.py`, `config_catalog_kontrol.py` (aksi `pindah_dana`), `entity_scope.py`, `indexes.py`
(nomor unik), butir tutup buku `closing_checklist.py` (dana dalam perjalanan); uji `backend/tests_mem/test_KB1_4_pindah_dana.py`.

**Interfaces (produces):** `buat(payload, actor)`, `terima(id, tanggal, actor)`, `setujui(id, actor)`, `batal(id, alasan, actor)`,
`daftar(entity_ids, …)`, `rincian(id)`; status `menunggu_persetujuan|dalam_perjalanan|selesai|batal`; rute
`/api/fund-transfers` (GET/POST), `/{id}`, `/{id}/receive|approve|cancel`.

- [ ] **Step 1 (uji gagal):** sekali jalan → kas keluar asal + masuk tujuan + biaya, jurnal Dr tujuan/Cr asal, Dr beban bank/Cr
  asal (akun lewat `akun_kas`, jadi benar di PT aktif maupun tidak); dua tahap via 1-1150 + terima; batal membalik semua kas,
  ditolak bila kas sudah tercocok mutasi; lintas PT / rekening sama / nonaktif / nominal ≤ 0 → 400; kontrol 2 orang → kas
  belum terbit sampai disetujui orang lain; nomor `PDN-` urut per PT; butir tutup buku menghitung dalam perjalanan.
- [ ] **Step 2–4:** RED → implementasi → GREEN + `test_latih_kas_transfer.py`, rekonsiliasi.
- [ ] **Step 5: Commit** `feat(kas-bank): dokumen Pindah Dana — pasangan kas, biaya, dalam perjalanan, batal, kontrol`

### Task 5: Tutup kategori Transfer/Top-up untuk kas manual baru

**Files:** `backend/routers/cash.py` (`create_cash_transaction`), `backend/services/ai_cards.py` (`_prep_cash_manual`);
uji `backend/tests_mem/test_KB1_5_tutup_transfer.py`.

- [ ] Uji gagal: POST kas manual kategori `transfer`/`top-up` (varian huruf) → 400 "Pakai Pindah Dana untuk setor tunai, isi
  kas kecil, dan pindah antar rekening."; kartu Asisten sama; kas lama berkategori itu tetap bisa dibatalkan & diposting ulang.
  RED → implementasi → GREEN → commit `feat(kas-bank): kas manual baru tidak lagi berkategori Transfer/Top-up`.

### Task 6: Layar (tanpa tinjauan per tugas — R10)

**Files:** `frontend/src/features/finance/` (Rekening: kolom "Akun buku besar" + penanda PT belum aktif; tab baru
**Pindah Dana** di hub Kas & Bank `config/hubTabs.js` — daftar, form `FormModal`, Terima/Setujui/Batal, pratinjau dokumen;
layar **Akun per rekening** — pratinjau tabel, Siapkan, daftar usulan + Setujui/Tolak dengan sidik; kas manual — hapus
kategori Transfer/Top-up + tautan Pindah Dana); registri pratinjau dokumen (`fund_transfer`); uji
`frontend/src/features/__tests__/kb1KasBank.test.js`.

- [ ] Uji jest per layar (izin menyembunyikan aksi; satu pop-up; sidik dikirim saat setuju; pesan 409 "Angka berubah"
  ditampilkan + muat ulang) → implementasi → GREEN + suite kas/bank terkait → commit
  `feat(kas-bank): layar Pindah Dana, akun per rekening, kolom akun di rekening`.

### Task 7: Uji penuh, gate, tangkapan (paket), laporan

- [ ] Suite penuh + gate `--quick`/`--ci` sejajar dengan tinjauan seluruh cabang; satu gelombang perbaikan.
- [ ] Tangkapan di data acuan (akhir paket, R10): F1 (impor → kwitansi otomatis, kartu Meja Keuangan) + Kas & Bank 1
  (Pindah Dana, pindah saldo PT demo: pratinjau → siapkan → setujui; rekening dengan akun buku besar).
- [ ] Laporan `docs/superpowers/plans/2026-11-27-kas-bank-1-hasil.md` + `CODEBASE_MAP.md` + `04_POLA_UI.md` bila ada pola baru.
