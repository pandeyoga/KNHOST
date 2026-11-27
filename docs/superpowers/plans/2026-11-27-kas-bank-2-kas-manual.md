# Kas & Bank bagian 2 — kas manual tanpa Pembelian/Gaji, kas keluar besar butuh orang kedua — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kas manual baru tidak bisa berkategori Pembelian/Gaji (C5), dan kas keluar manual di atas batas PT (bawaan
Rp 1.000.000) menjadi pengajuan `PKK-` yang baru terbit sebagai kas + jurnal sesudah orang kedua menyetujui (C6).

**Architecture:** C5 = satu pembantu di `cash_ledger` yang membaca akun lawan jurnal (`gl_service.cash_contra_account`)
dan dipanggil di pintu manual (rute + kartu Asisten), seperti Transfer/Top-up di Kas & Bank 1 Tugas 5. C6 = aksi kontrol
`kas_keluar_manual` + koleksi `cash_out_requests` + layanan pengajuan berpola Pindah Dana (`menunggu_persetujuan` → klaim →
`create_cash`) + rute manual yang menjawab 202; layar dan antrean di Tugas 4.

**Tech Stack:** FastAPI, Motor/MongoDB (uji: mongomock `backend/tests_mem`), React (craco/jest).

**Spec:** `docs/superpowers/specs/2026-11-27-kas-bank-2-kas-manual-design.md` (C5/C6 disetujui pemilik; §7 keputusan builder,
§7.8 jawaban builder check).

## Global Constraints

- Bahasa Indonesia untuk teks layar, galat, komentar baru, commit. Wewenang = izin; nilai bisnis = pengaturan.
- Tanpa migrasi saat menyala yang menulis data; tanpa izin baru (`cash.create` ajukan, `cash.approve` setujui/tolak,
  `cash.delete` batal oleh selain pengaju).
- Satu pintu kas `cash_ledger.create_cash`; penolakan C5/C6 hanya di pintu manual (`routers/cash.py create_cash_transaction`,
  `ai_cards._prep_cash_manual`), **tidak** di `create_cash` (bayar tagihan "pembelian", "Pembayaran Gaji" tetap jalan).
- Pesan C5 persis: "Kategori Pembelian dan Gaji tidak lagi dipakai di kas manual: pembelian barang lewat PO/tagihan pemasok, gaji lewat Proses Gaji. Belanja kecil kebutuhan kantor pakai kategori Operasional."
- Kontrol: aksi `kas_keluar_manual`, kelompok C, bagian Buku besar, `min_orang` bawaan "1", `batas_nominal` bawaan 1000000,
  "di atas" = nominal > batas; masuk bawaan `kontrol.admin_tetap_dua_orang`.
- Pengajuan: koleksi `cash_out_requests`, nomor `PKK-` per PT, status `menunggu_persetujuan|disetujui|ditolak|dibatalkan`;
  kas terbit `ref_type="manual"`, `ref_id=<id pengajuan>`, tanggal kas = tanggal diajukan.
- Uji: `python -m pytest backend/tests_mem/<file> -n 0 -q -p no:cacheprovider`; jest `CI=true yarn test --watchAll=false <file>`.
- Jangan sentuh `deploy/`, `.env`, `memory/GATE_RECEIPT.*`, `frontend/yarn.lock`. Commit diakhiri
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` dan `Claude-Session: https://claude.ai/code/session_01WetgRZMZjzXfrP6Zn8k4UK`.

## Review Focus

1. **Kiriman ulang Idempotency-Key yang sama** (sebelum dan sesudah disetujui) → pengajuan yang sama (202), tidak pernah
   pengajuan kedua atau kas langsung. (Task 2)
2. **Dua Setujui bersamaan / Setujui × Batal bersamaan** → satu kas, atau batal utuh tanpa kas. (Task 2; MongoDB asli Task 5)
3. **Periode tertutup atau anggaran terlampaui saat disetujui** → persetujuan ditolak berkalimat, pengajuan tetap menunggu,
   tidak ada kas. (Task 2)
4. **Pengajuan menunggu tidak terhitung** di saldo kas, buku kas rekening, ringkasan Transaksi Kas. (Task 2)
5. **Kas masuk manual di atas batas & kas keluar = batas** → langsung terjurnal seperti sekarang. (Task 2)

---

### Task 1: C5 — kategori Pembelian/Gaji ditutup di kas manual

**Files:** `backend/services/cash_ledger.py` (pembantu + pesan), `backend/routers/cash.py` (`create_cash_transaction`),
`backend/services/ai_cards.py` (`_prep_cash_manual`); uji `backend/tests_mem/test_KB2_1_kategori.py`; perbarui uji lama
yang mengirim kas manual baru berkategori pembelian/gaji lewat rute (mis. `test_PK39_pemeriksaan.py` U11b → kategori
lain berakun sama tidak diperlukan; pakai "operasional" dan sesuaikan asersi).

**Interfaces:** Produces `cash_ledger.kategori_kas_manual_ditutup(category: str) -> bool` dan
`cash_ledger.PESAN_KATEGORI_PEMBELIAN_GAJI_DITUTUP: str`. Ditutup bila `gl_service.cash_contra_account({"ref_type": "manual",
"direction": "out", "category": category})` ∈ {akun persediaan `1-1300`, beban gaji `6-1000`} (pakai konstanta gl_service,
bukan string baru) — dinilai dengan tabel kata kunci KELUAR untuk kedua arah (spesifikasi §7.8 butir 2).

- [ ] **Step 1 (uji gagal):** rute POST kas manual kategori `pembelian`, `Pembelian`, `Beli kain`, `bahan bakar`, `gaji`,
  `Gaji / Upah`, `payroll` (arah keluar dan masuk) → 400 dengan pesan C5 persis; `operasional`, `lain`, `modal`, `sewa` → 200;
  kartu Asisten `cash_manual` berkategori pembelian → ditolak dengan pesan sama; `create_cash` langsung dengan
  `ref_type="vendor_bill"`, kategori "pembelian" → tetap jalan; kas lama berkategori pembelian (dibuat lewat
  `create_cash(ref_type="manual")`) → bisa dibatalkan lewat rute void.
- [ ] **Step 2–4:** RED → implementasi → GREEN + uji kas/Asisten/anggaran terkait (`test_KB1_5_tutup_transfer.py`, `AGT5*`,
  `test_PK39*`).
- [ ] **Step 5: Commit** `feat(kas-bank): kas manual baru tidak lagi berkategori Pembelian/Gaji`

### Task 2: C6 — pengajuan kas keluar manual di atas batas (server)

**Files:** baru `backend/services/cash_out_request_service.py`, `backend/routers/cash_out_requests.py` (daftar di
`server.py`); ubah `backend/routers/cash.py` (cabang 202), `backend/config_catalog_kontrol.py` (aksi + `_TITIK` + bawaan
batas & admin-tetap), `backend/indexes.py` (nomor unik per PT, kunci idempoten unik parsial per PT), `entity_scope`
butir koleksi baru, `ENTITY_REGISTRY.md`; uji `backend/tests_mem/test_KB2_2_pengajuan.py`.

**Interfaces (produces):**
- `async def ajukan(payload: dict, actor: dict, entity_id: str, idem_key: str) -> dict` (pengajuan; idempoten per PT+kunci).
- `async def setujui(request_id: str, actor: dict) -> dict`, `async def tolak(request_id: str, alasan: str, actor: dict) -> dict`,
  `async def batal(request_id: str, actor: dict) -> dict`, `async def daftar(entity_ids, status=None, …) -> dict`,
  `async def rincian(request_id: str) -> dict`.
- Rute: `POST /api/cash-transactions` → 202 `{"request": {...}}` bila arah keluar dan `dual_control.butuh_orang_kedua(
  "kas_keluar_manual", eid, amount)`; `GET /api/cash-out-requests`, `GET /api/cash-out-requests/{id}`,
  `POST /api/cash-out-requests/{id}/approve|reject|cancel`.
- Dokumen: `{id, number, entity_id, status, cash_type, direction:"out", amount, category, description, account_id,
  txn_date, idempotency_key, pengaju{ id, name }, created_at, jejak[], cash_id?, terbit_error?, alasan_tolak?}`.

- [ ] **Step 1 (uji gagal):** keluar 1.000.000 → 200 kas langsung; keluar 1.000.001 → 202 pengajuan `PKK-`, nol kas, nol
  jurnal, saldo kas & buku kas rekening & ringkasan tidak berubah; masuk 5.000.000 → 200; `min_orang` "2" → keluar 10.000 →
  202; batas PT diubah 5.000.000 → keluar 2.000.000 → 200; kunci idempoten sama dikirim ulang (menunggu & sesudah
  disetujui) → pengajuan sama; setujui oleh pengaju → 403 kalimat orang kedua; admin penyiap → 403 (bawaan admin-tetap);
  setujui orang lain → kas `ref_type` manual `ref_id`=id pengajuan, tanggal = tanggal diajukan, status `disetujui`,
  `cash_id`; setujui ganda → satu kas; setujui × batal (urutan sela, pola Pindah Dana T4 U13) → utuh salah satu; periode
  tertutup saat disetujui → 409 berkalimat, tetap menunggu, nol kas; anggaran mode blokir terlampaui saat disetujui → 409
  berkalimat; tolak tanpa alasan → 400, dengan alasan → `ditolak`; batal oleh pengaju → `dibatalkan`; batal sesudah
  disetujui → 409; pengajuan dari PT lain tidak terlihat/terputus (`entity_scope`).
- [ ] **Step 2–4:** RED → implementasi → GREEN + uji kas, anggaran, kontrol (KFT1/KFT4/KFT6 hitungan kunci + indeks kunci
  layar), Pindah Dana, KB1_*.
- [ ] **Step 5: Commit** `feat(kas-bank): kas keluar manual di atas batas jadi pengajuan yang disetujui orang kedua`

### Task 3: Kartu Asisten dan pemberitahuan pengajuan

**Files:** `backend/services/ai_cards.py` (`_cash_result` membaca 202), `backend/services/notification_service.py`
(jenis baru: pengajuan masuk → pemegang `cash.approve` PT itu; diputus → pengaju), panggilan dari
`cash_out_request_service`; uji `backend/tests_mem/test_KB2_3_asisten_notifikasi.py`.

**Interfaces:** Consumes Task 2. Produces jenis notifikasi `kas_keluar_diajukan`, `kas_keluar_diputus` (kunci `notifDocTarget`
untuk Tugas 4: dokumen `cash_out_request`).

- [ ] **Step 1 (uji gagal):** kartu `cash_manual` keluar di atas batas → status kartu "Diajukan — menunggu persetujuan kas
  keluar PKK-…" (bukan galat), tanpa kas; di bawah batas → seperti sekarang; ajukan → satu pemberitahuan per pemegang
  `cash.approve` PT itu (bukan pengaju, bukan PT lain); setujui/tolak → pemberitahuan ke pengaju berisi hasil & alasan.
- [ ] **Step 2–4:** RED → implementasi → GREEN + uji Asisten (`AGT*`) & notifikasi terkait.
- [ ] **Step 5: Commit** `feat(kas-bank): kartu Asisten dan pemberitahuan pengajuan kas keluar`

### Task 4: Layar + antrean persetujuan (tanpa tinjauan per tugas — R10)

**Files:** `frontend/src/features/purchasing/CashManagementView.jsx` (CATEGORIES tanpa pembelian/gaji, label lama tetap;
catatan & tombol "Ajukan" bila keluar > batas; bagian "Menunggu persetujuan" dengan Setujui/Tolak/Batal), pratinjau dokumen
`cash_out_request` (registri pratinjau + jejak), `notifDocTarget`; server: jenis persetujuan + baris `QUEUES`
"Kas keluar manual menunggu" + `DOOR_QUEUE` (rute `/approve` dikenali `DOOR_RE`), `guard_door`; uji
`frontend/src/features/__tests__/kb2KasManual.test.js` + perbarui `kb1KasBank.test.js` (CATEGORIES).

- [ ] Uji jest (izin menyembunyikan aksi; Setujui mati untuk pengaju dengan alasan; 202 → toast + baris menunggu; satu
  pop-up; nomor PKK- membuka pratinjau) → implementasi → GREEN + suite kas/antrean terkait; `verify_approval_queues` tanpa
  pelanggaran baru → commit `feat(kas-bank): layar pengajuan kas keluar dan kategori kas manual`.

### Task 5: Uji penuh, gate, MongoDB asli, tangkapan, laporan

- [ ] Suite penuh + gate `--ci` sejajar dengan tinjauan seluruh cabang; satu gelombang perbaikan; gate `--quick` di pohon akhir.
- [ ] Uji MongoDB asli `backend/tests/test_bp_KB2_bersamaan.py` (pola `test_bp_KB1_bersamaan.py`): dua Setujui bersamaan →
  satu kas; Setujui × Batal bersamaan → utuh salah satu.
- [ ] Tangkapan di data acuan: form tanpa Pembelian/Gaji; ajukan di atas batas; menunggu (Setujui mati untuk pengaju);
  orang kedua setujui → kas; tolak beralasan; Pusat Persetujuan.
- [ ] Laporan `docs/superpowers/plans/2026-11-27-kas-bank-2-hasil.md` + `CODEBASE_MAP.md` + materi pelatihan yang memakai
  kategori Pembelian (`docs/pelatihan/2026-11-18_keuangan/uji/situasi/S4_koreksi_pembatalan.js`, `uji/variasi/V2_kas.js`)
  dicatat sebagai tindak lanjut bila tidak diubah.
