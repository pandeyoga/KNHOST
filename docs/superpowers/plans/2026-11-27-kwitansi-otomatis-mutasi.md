# F1 Kwitansi Otomatis dari Mutasi Bank — Rencana Implementasi

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mutasi masuk berkode bayar yang cocok sempurna menjadi kwitansi terverifikasi bank otomatis saat impor; sisanya
menjadi kartu "Mutasi berkode perlu dicek" di Meja Keuangan dengan operasi "kwitansi dari mutasi" yang atomik.

**Architecture:** Satu layanan baru `backend/services/bank_auto_receipt_service.py` (penilai + pelaksana) dipanggil router
rekonsiliasi sesudah impor dan saat "Cocokkan otomatis". Semua uang lewat pintu yang ada (`create_receipt`,
`payment_report_service.terima`, `bank_recon_service._link/_unlink`). Layar: antrean baru Meja Keuangan + panel pop-up,
layar Rekonsiliasi memakai endpoint atomik.

**Tech Stack:** FastAPI + Motor/MongoDB (backend, uji `backend/tests_mem` mongomock), React 19 + Jest (frontend).

**Spec:** `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` (keputusan builder §7 butir 1–14).

## Global Constraints

- Bahasa Indonesia untuk teks layar, pesan galat, komentar baru, pesan commit.
- Wewenang = izin (`require_permission` / `has_permission` / `can(...)`), bukan nama peran.
- Nilai bisnis = pengaturan; satu-satunya pengaturan baru: `bank.kwitansi_otomatis_mutasi` (bool, scopes global+PT,
  bawaan **True**).
- "Cocok sempurna" = `abs(nominal_mutasi − harapan) < 1` (rupiah) — definisi, bukan pengaturan.
- Satu pintu uang: kwitansi hanya lewat `ar_receipt_service.create_receipt` atau `payment_report_service.terima`; tautan
  mutasi hanya lewat `bank_recon_service._link`/`_unlink`. Tidak ada posting jurnal baru.
- Satu kwitansi hidup per baris mutasi: indeks unik parsial `uq_bank_line_receipt` pada `ar_receipts.bank_line_id`
  (`{bank_line_id: {$exists: true}, status: "posted"}`).
- Penanda sumber kwitansi: `source = "mutasi_bank"` + `bank_line_id`; pelaku sistem
  `AKTOR_MUTASI = {"id": "", "name": "Sistem (mutasi bank)", "role": "system", "sistem": "mutasi_bank"}`.
- F1 hanya memproses baris yang diimpor sesudah waktu aktif (`system_settings` `{scope:"__migrations__"}` kunci
  `f1_kwitansi_mutasi_aktif_sejak`, ditulis sekali saat backend menyala).
- Baris yang pernah ditautkan mesin (`f1.pernah_otomatis = True`) tidak pernah diproses otomatis lagi.
- Uji: `cd /home/user/KNHOST && python -m pytest backend/tests_mem/<file> -n 0 -q -p no:cacheprovider`; jest:
  `cd frontend && CI=true yarn test --watchAll=false <file>`. pytest selalu `-n 0`.
- Jangan sentuh `deploy/`, `.env`, `memory/GATE_RECEIPT.*`, `frontend/yarn.lock`; berkas unggahan uji tidak di-commit.
- Akhir pesan commit: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` dan
  `Claude-Session: https://claude.ai/code/session_01WetgRZMZjzXfrP6Zn8k4UK`.

## Review Focus

1. **Impor ulang berkas yang sama** → baris duplikat dilewati; tidak ada kwitansi kedua (indeks + klaim). (Task 3)
2. **Dua mutasi berkode sama dalam satu impor** (pelanggan transfer dua kali) → yang pertama otomatis, yang kedua kartu
   `sudah_lunas`/`nominal_beda`. (Task 3)
3. **DP berpecahan**: harapan Rp 173.437,5; mutasi Rp 173.438 dan Rp 173.437 → keduanya otomatis tanpa kasus selisih
   bayar terbuka. (Task 2 + 3)
4. **Pengaturan mati untuk PT** → tidak ada kwitansi; baris berkode tetap kartu `otomatis_mati`. (Task 2)
5. **Mutasi lama** (dibuat sebelum waktu aktif) dan **baris yang pernah otomatis lalu dilepas lewat "Lepas" biasa** →
   tidak disentuh mesin saat "Cocokkan otomatis". (Task 3 + 4)

---

## Peta berkas

| Berkas | Tanggung jawab |
|---|---|
| `backend/services/bank_auto_receipt_service.py` (baru) | Waktu aktif, penilai baris, pelaksana jalur A/B/C, proses impor/rekening, kwitansi manual dari mutasi, pembatalan |
| `backend/config_catalog_bank.py` | Kunci `bank.kwitansi_otomatis_mutasi` |
| `backend/services/ar_receipt_service.py` | Teruskan `source`/`bank_line_id`; pengecualian B3 untuk `AKTOR_MUTASI` |
| `backend/indexes.py` | `uq_bank_line_receipt` |
| `backend/services/payment_report_service.py` | `terima(..., bank_line=None)`: lampiran tidak wajib bila membawa mutasi; kwitansi bersumber mutasi |
| `backend/services/bank_recon_service.py` | `_unlink` mempertahankan penanda `f1`; `list_lines` membawa `f1` |
| `backend/routers/bank_reconciliation.py` | Kait impor/cocokkan otomatis; `POST /lines/{id}/receipt`; `POST /lines/{id}/void-receipt` |
| `backend/server.py` | Panggil `ensure_aktif_sejak()` saat menyala |
| `backend/services/work_desk_service.py` | Antrean `mutasi_berkode` |
| `backend/services/notification_service.py` | Jenis `bayar_masuk_mutasi`, `ringkasan_mutasi_otomatis` (lewat `create_addressed`) |
| `frontend/src/features/finance/bank/bankLineReceiptApi.js` (baru) | `receiptFromLine`, `voidLineReceipt` |
| `frontend/src/features/desks/BankLineQueuePanel.jsx` (baru) | Pop-up antrean `mutasi_berkode` |
| `frontend/src/features/finance/FinanceDesk.jsx`, `features/desks/deskPanels.js` | Daftarkan antrean + panel |
| `frontend/src/features/finance/payments/ReceivePaymentModal.jsx` | Mode `bankLineId` memakai endpoint atomik |
| `frontend/src/features/finance/BankReconciliationView.jsx`, `bank/ReconLinesTable.jsx`, `bank/ReconImportPanel.jsx` | Alasan kartu, lencana otomatis, batal, jumlah di pesan |
| `frontend/src/components/NotificationCenter.jsx`, `features/notifications/notifDocTarget.js` | Label & tujuan dua jenis notifikasi baru |
| Pratinjau kwitansi (`features/documents/preview/bodies/` berkas kwitansi) | Baris "Lahir dari mutasi bank …" |

---

### Task 1: Fondasi — pengaturan, waktu aktif, isian kwitansi, indeks unik, pengecualian B3

**Files:**
- Create: `backend/services/bank_auto_receipt_service.py` (hanya konstanta + `ensure_aktif_sejak`, `aktif_sejak`, `menyala`)
- Modify: `backend/config_catalog_bank.py`, `backend/services/ar_receipt_service.py`, `backend/indexes.py`,
  `backend/server.py`
- Test: `backend/tests_mem/test_F1_1_fondasi.py`

**Interfaces:**
- Produces:
  - `SUMBER: str = "mutasi_bank"`; `AKTOR_MUTASI: dict` (Global Constraints); `PENANDA_AKTIF = "f1_kwitansi_mutasi_aktif_sejak"`.
  - `async def ensure_aktif_sejak() -> str` — tulis `now_iso()` ke `system_settings {scope:"__migrations__"}` bila
    kunci belum ada; kembalikan nilainya.
  - `async def aktif_sejak() -> str` — baca nilai (kosong bila belum ada).
  - `async def menyala(entity_id: str) -> bool` — `nilai("bank.kwitansi_otomatis_mutasi", entity_id)` (pola pembaca
    pengaturan yang sama dengan `pay_hold_service.due_at`).
  - `create_receipt` menerima `source` dan `bank_line_id` (hanya dari layanan; `ReceiptPayload` di router TIDAK
    menambah field ini) dan menyimpannya di dokumen kwitansi bila ada.
  - `_pagar_lapor_bayar` dilewati bila `payload.get("source") == SUMBER and actor.get("sistem") == SUMBER`.

- [ ] **Step 1: Uji gagal** — `test_F1_1_fondasi.py`:
  - `test_pengaturan_terdaftar_bawaan_nyala`: katalog memuat `bank.kwitansi_otomatis_mutasi`, `type == "bool"`,
    `default is True`, scopes `("global","entity")`; `await menyala("ent_ksc") is True`; sesudah `PUT /api/config/values`
    mematikan untuk `ent_ksc` → `False`, PT lain tetap `True`.
  - `test_waktu_aktif_ditulis_sekali`: `a = await ensure_aktif_sejak(); b = await ensure_aktif_sejak(); assert a == b != ""`.
  - `test_kwitansi_menyimpan_sumber_dan_baris`: `create_receipt({... "source": "mutasi_bank", "bank_line_id": "stmtline_x"}, finance_actor)`
    → dokumen `ar_receipts` punya kedua field; `POST /api/ar-receipts` dengan `source`/`bank_line_id` di badan →
    dokumen TIDAK menyimpannya (field asing diabaikan).
  - `test_indeks_unik_baris_mutasi`: `uq_bank_line_receipt` terdaftar di `REQUIRED_UNIQUE_INDEXES` dengan partial
    `{"bank_line_id": {"$exists": True}, "status": "posted"}`.
  - `test_b3_dikecualikan_hanya_untuk_aktor_mutasi`: pesanan CBD tertahan; `create_receipt` transfer dengan
    `source="mutasi_bank"` oleh `AKTOR_MUTASI` → berhasil; oleh aktor sales (tanpa `payment_report.decide`) dengan
    `source="mutasi_bank"` → 409 `PESAN_PAKAI_LAPOR_BAYAR`; oleh `AKTOR_MUTASI` tanpa `source` → 409.
- [ ] **Step 2:** Jalankan → FAIL (modul/kunci belum ada).
- [ ] **Step 3:** Implementasi:
  - `config_catalog_bank.py`: `E("bank.kwitansi_otomatis_mutasi", type="bool", default=True, scopes=G, risk="medium",`
    label "Kwitansi otomatis dari mutasi bank", help "Mutasi masuk berkode bayar yang cocok sempurna (pesanan, PT,
    rekening, nominal) langsung menjadi kwitansi terverifikasi bank saat mutasi diimpor. Mati = mutasi berkode tetap
    tampil sebagai kartu di Meja Keuangan untuk dicatat manual.", consumers `services/bank_auto_receipt_service.py:menyala`).
  - `indexes.py`: entri `REQUIRED_UNIQUE_INDEXES` `uq_bank_line_receipt` (pola `uq_payment_report`, label "satu kwitansi
    per mutasi bank").
  - `server.py`: di proses awal, sesudah benih cara bayar: `await ensure_aktif_sejak()` dalam try/except log peringatan.
  - `ar_receipt_service.create_receipt` / `_create_receipt_after_reserve`: teruskan & simpan `source`, `bank_line_id`.
- [ ] **Step 4:** Jalankan uji → PASS; juga `test_LB4_putus.py test_PMT3_kwitansi_rekening.py` → PASS.
- [ ] **Step 5: Commit** `feat(pembayaran): fondasi F1 — pengaturan kwitansi otomatis, waktu aktif, sumber kwitansi, indeks satu kwitansi per mutasi`

### Task 2: Penilai baris mutasi (cocok sempurna / kartu + alasan)

**Files:**
- Modify: `backend/services/bank_auto_receipt_service.py`
- Test: `backend/tests_mem/test_F1_2_penilai.py`

**Interfaces:**
- Consumes: Task 1 (`menyala`, `aktif_sejak`, `SUMBER`).
- Produces: `async def nilai_baris(line: dict) -> dict` (tanpa menulis apa pun) →
  `{"keputusan": "A"|"B"|"C"|"kartu"|"lewati", "alasan_kode": str, "alasan": str, "order": dict|None,
    "harapan": float|None, "receipt": dict|None, "report": dict|None}`.
  - `"lewati"` (bukan urusan F1): bukan `in`; bukan `unmatched`; tanpa kode; `created_at < aktif_sejak()`;
    `f1.pernah_otomatis`; `f1.status == "dibatalkan"`.
  - Kode alasan kartu (string tetap, dipakai layar): `pt_tidak_jelas`, `kode_ganda`, `pesanan_mati`, `sudah_lunas`,
    `nominal_beda`, `rekening_beda`, `rekening_tolak_cara`, `periode_tutup`, `laporan_beda`, `laporan_diproses`,
    `laporan_dan_kwitansi`, `selisih_perlu_putusan`, `otomatis_mati`.
  - Harapan (§5.2-4): `pay_hold_service.sisa_wajib_sebelum_gudang(order)`; sisa baris jadwal milik kode baris
    (`payment_plans.lines[]` dengan `pay_code == kode`); `payment_report_service.sisa_tagihan(order)`. Cocok bila
    `abs(amount − h) < 1` untuk salah satu harapan yang berlaku (urutan di atas; yang pertama cocok dipakai).
  - Urutan penilaian: lewati → PT/kode → pesanan → nominal → laporan & kwitansi terbuka (A/B/`laporan_*`) → rekening →
    periode → `pre_assess(customer_id, amount, [{order_id, amount: harapan}], stmt_date, entity_id)["needs_decision"]`
    → `menyala` (bila mati: `kartu`/`otomatis_mati` dengan alasan yang akan menjadi keputusan bila menyala).
  - Teks alasan memakai `core_utils.rupiah`, contoh tepat: `"Nominal mutasi Rp 1.500.000 ≠ tagihan Rp 1.318.125 (lebih Rp 181.875)"`.

- [ ] **Step 1: Uji gagal** — `test_F1_2_penilai.py` (pakai pola pembantu `_rekening`/`_impor` dan pesanan CBD/DP dari
  `test_PMT3_kwitansi_rekening.py` / `test_LB4_putus.py`), satu uji per keputusan:
  - `test_cbd_tertahan_nominal_tepat_C` (harapan = sisa wajib, keputusan `"C"`);
  - `test_dp50_pecahan_dua_arah_C`: harapan 173437.5; mutasi 173438 → `"C"`; mutasi 173437 → `"C"`; mutasi 173436 → kartu `nominal_beda`;
  - `test_kode_baris_cicilan_C` (harapan = sisa baris jadwal);
  - `test_kwitansi_terbuka_sama_A` (kwitansi Finance belum terverifikasi, nominal sama → `"A"`, `receipt` terisi);
  - `test_laporan_menunggu_sama_B` (nominal & rekening sama → `"B"`; laporan tanpa lampiran tetap `"B"`);
  - `test_laporan_beda_kartu`, `test_laporan_memproses_kartu`, `test_laporan_dan_kwitansi_kartu`;
  - `test_dua_kode_kartu`, `test_pesanan_batal_kartu`, `test_sudah_lunas_kartu`, `test_rekening_beda_instruksi_kartu`,
    `test_periode_tutup_kartu`, `test_baris_pt_all_kartu`;
  - `test_pengaturan_mati_kartu_otomatis_mati`;
  - `test_lewati`: arah keluar; tanpa kode; `created_at` sebelum waktu aktif; `f1.pernah_otomatis=True`; status `matched`.
  - Tiap uji kartu memeriksa `alasan_kode` tepat dan `alasan` berisi nomor/nominal yang relevan.
  - `test_penilai_tidak_menulis`: hitungan dokumen `ar_receipts`, `cash_transactions`, `bank_statement_lines` sama sebelum/sesudah.
- [ ] **Step 2:** Jalankan → FAIL.
- [ ] **Step 3:** Implementasi `nilai_baris` dengan urutan di atas; baca kode dari `line["pay_code_hits"]` (isi lewat
  `bank_recon_service.pay_code_hits(line)` bila kosong); pemeriksaan rekening & cara lewat
  `ar_receipt_service.periksa_uang_masuk`-setara tanpa tulisan (pakai fungsi pemeriksa yang ada, tangkap
  `HTTPException` → kode alasan); periode lewat `gl.preflight_posting`-setara tanpa tulisan.
- [ ] **Step 4:** Jalankan → PASS.
- [ ] **Step 5: Commit** `feat(pembayaran): F1 penilai mutasi berkode — cocok sempurna, kartu beralasan`

### Task 3: Pelaksana jalur A/B/C, proses impor & rekening, pemberitahuan

**Files:**
- Modify: `backend/services/bank_auto_receipt_service.py`, `backend/services/payment_report_service.py`,
  `backend/services/bank_recon_service.py` (`_unlink` & `list_lines` saja), `backend/services/notification_service.py`
- Test: `backend/tests_mem/test_F1_3_pelaksana.py`

**Interfaces:**
- Consumes: Task 2 `nilai_baris`.
- Produces:
  - `async def proses_baris(line: dict, pemicu: str) -> dict` → `{"line_id", "hasil": "otomatis"|"kartu"|"lewati",
    "jalur": "A"|"B"|"C"|"", "receipt_id", "receipt_number", "order_id", "order_number", "alasan_kode", "alasan",
    "released": bool}`.
  - `async def proses_impor(import_batch: str, pemicu: str) -> dict` → `{"kwitansi_otomatis": int, "kartu": int,
    "nilai_otomatis": float, "rincian": [hasil proses_baris…]}`; baris batch diurutkan `stmt_date` naik lalu urutan
    sisip; satu notifikasi ringkasan Finance bila `kwitansi_otomatis + kartu > 0`.
  - `async def proses_rekening(bank_account_id: str, entity_ids: list, pemicu: str) -> dict` — bentuk sama; baris
    `unmatched` berkode di rekening itu yang tidak `lewati`.
  - Penanda baris `f1 = {"status": "otomatis"|"kartu"|"dibatalkan", "jalur", "alasan_kode", "alasan", "dinilai_at",
    "receipt_id", "order_id", "report_id", "pernah_otomatis": bool, "dilepas_at": str}`.
  - `payment_report_service.terima(report, order, actor, *, bank_line: dict | None = None)`: bila `bank_line` ada —
    lampiran tidak wajib; kwitansi `isi_kwitansi` ditambah `source=SUMBER`, `bank_line_id`; catatan laporan
    "Diterima otomatis dari mutasi bank {tanggal} · {rekening}" bila `actor.get("sistem") == SUMBER`.
  - Kode alasan tambahan milik pelaksana: `galat` (galat tak terduga saat bertindak → kartu, teks galat berkalimat).
  - Ringkasan Finance hanya dari `proses_impor` (bukan dari `proses_rekening`; tombol menampilkan jumlahnya sendiri).
  - Jenis notifikasi: `bayar_masuk_mutasi` (sales pemilik, hanya pesanan yang tadinya tertahan bayar),
    `ringkasan_mutasi_otomatis` (per orang pemegang `payment_report.decide` di PT baris).

- [ ] **Step 1: Uji gagal** — `test_F1_3_pelaksana.py`:
  - `test_jalur_C_kwitansi_terverifikasi_dan_lepas`: CBD tertahan + "Periksa & lepas" → impor mutasi berkode nominal
    tepat → `proses_impor` → 1 kwitansi `source="mutasi_bank"`, `bank_line_id`, `bank_verified=True`, nomor referensi
    = ref mutasi (atau kode bila ref kosong); baris `matched`, `match_type="auto_receipt"`, `f1.status="otomatis"`,
    `f1.pernah_otomatis=True`; pesanan `confirmed`; `variance.needs_decision` tidak ada/False; notifikasi
    `bayar_masuk_mutasi` ke sales pemilik dan `ringkasan_mutasi_otomatis` ke Finance (satu per orang).
  - `test_jalur_A_menautkan_kwitansi_yang_ada` (tidak ada kwitansi baru; `match_type="auto"`).
  - `test_jalur_B_laporan_diterima_otomatis`: laporan `diterima`, catatan memuat "mutasi bank", satu kwitansi dengan
    `payment_report_id` **dan** `bank_line_id`; juga untuk laporan tanpa lampiran.
  - `test_kartu_menulis_alasan_tanpa_uang`: baris tetap `unmatched`, `f1.status="kartu"`, kode alasan; tidak ada kwitansi/kas.
  - `test_impor_ulang_tidak_ganda` (Review Focus 1): impor berkas sama dua kali + `proses_impor` dua kali → 1 kwitansi.
  - `test_dua_mutasi_kode_sama_satu_batch` (Review Focus 2): yang pertama otomatis, yang kedua kartu.
  - `test_dp_pecahan_tanpa_selisih_terbuka` (Review Focus 3): DP 173437.5, mutasi 173438 → kwitansi; antrean
    `selisih_bayar` Meja Keuangan kosong untuk pelanggan itu.
  - `test_proses_baris_bersamaan_satu_kwitansi`: `asyncio.gather(proses_baris(l), proses_baris(l))` → tepat 1 kwitansi.
  - `test_pemulihan_kwitansi_tanpa_tautan`: kwitansi ber-`bank_line_id` sudah ada, baris belum `matched` →
    `proses_baris` hanya menautkan (jumlah kwitansi tetap 1).
  - `test_lepas_biasa_tidak_diproses_lagi` (Review Focus 5): jalur C lalu `bank_recon_service.unmatch` →
    `f1.pernah_otomatis` masih True, `f1.dilepas_at` terisi → `proses_rekening` → `lewati`, kwitansi tetap 1.
  - `test_mutasi_lama_tidak_disentuh` (Review Focus 5): baris `created_at` sebelum waktu aktif → `proses_rekening` → lewati.
  - `test_galat_tak_terduga_jadi_kartu`: `create_receipt` dipaksa melempar (monkeypatch) → baris `kartu`
    `alasan_kode="galat"`, tidak ada kwitansi setengah jadi, proses baris berikutnya tetap jalan.
- [ ] **Step 2:** Jalankan → FAIL.
- [ ] **Step 3:** Implementasi:
  - Klaim baris memakai CAS `match_lock` yang sama dengan `_link` (pemilik kunci = operasi F1); kunci diserahkan ke
    `_link` atau dilepas pada jalur kartu. Bila `_link` mensyaratkan kunci kosong, tambahkan parameter
    `_link(..., op: str = "")` yang menerima kunci milik pemanggil — satu tempat.
  - Jalur C: `create_receipt(payload, AKTOR_MUTASI)` dengan isian §5.3 spesifikasi; `DuplicateKeyError` pada
    `uq_bank_line_receipt` → ambil kwitansi pemenang, tautkan.
  - Jalur B: `terima(report, order, AKTOR_MUTASI, bank_line=line)` lalu tautkan ke kas kwitansinya.
  - Sesudah tautan: `delivery_service.dispatch_event("ar_receipt", rid, "created", entity_id, AKTOR_MUTASI["name"])`
    dalam try/except (dicatat); audit `bank_auto_receipt` `{line_id, receipt_number, order_number, jalur, pemicu}`.
  - `_unlink`: jangan hapus `f1`; bila `f1.pernah_otomatis` → `$set f1.dilepas_at`.
  - `list_lines`: sertakan `f1` apa adanya.
- [ ] **Step 4:** Jalankan → PASS; jalankan juga `test_LB*.py`, `test_PMT3_*.py`, `test_PK21_*.py`, `test_PK15_*.py`.
- [ ] **Step 5: Commit** `feat(pembayaran): F1 pelaksana — kwitansi/laporan/tautan otomatis dari mutasi berkode, kartu beralasan, ringkasan Finance`

### Task 4: Endpoint — kait impor & cocokkan otomatis, kwitansi dari mutasi (manual), pembatalan

**Files:**
- Modify: `backend/routers/bank_reconciliation.py`, `backend/services/bank_auto_receipt_service.py`
- Test: `backend/tests_mem/test_F1_4_endpoint.py`

**Interfaces:**
- Consumes: Task 3 `proses_impor`, `proses_rekening`, `proses_baris`.
- Produces:
  - Respons `POST /api/bank-reconciliation/import`, `/import-file`, `/auto-match` bertambah `kwitansi_otomatis`,
    `kartu`, `nilai_otomatis` (impor: dari `proses_impor(res["import_batch"], nama_pengimpor)`; auto-match: sesudah
    `auto_match` lama, `proses_rekening`). Galat F1 tidak menggagalkan impor (dicatat; jumlah 0).
  - `async def kwitansi_dari_mutasi(line_id: str, payload: dict, actor: dict, entity_ids: list) -> dict` →
    `{"receipt": dict, "line": dict, "released_order_ids": list}`; rute `POST /api/bank-reconciliation/lines/{line_id}/receipt`
    (izin `cash.create` **dan** `ar_receipt.create`; badan = isian `ReceiptPayload` + `payment_report_id` opsional).
    Rekening = rekening mutasi, tanggal = tanggal mutasi, `source`/`bank_line_id` diisi server; nominal badan harus =
    nominal mutasi (selisih < Rp 1) bila tanpa keputusan selisih; laporan menunggu pada pesanan tujuan → 409
    `"Putuskan dulu laporan bayar {LB}: Terima bila buktinya mutasi ini, Tolak bila bukan."` kecuali
    `payment_report_id` disebut (→ `terima(..., bank_line=line)`; nominal laporan = nominal mutasi, rekening sama).
  - `async def batal_kwitansi_mutasi(line_id: str, reason: str, actor: dict, entity_ids: list) -> dict`; rute
    `POST /api/bank-reconciliation/lines/{line_id}/void-receipt` badan `{reason}` (izin `ar_receipt.void` **dan**
    `cash.create`; alasan ≥ 5 huruf): `_unlink` lalu `void_receipt` (aturan yang ada) lalu `f1.status="dibatalkan"`;
    respons memuat `order_released: bool` + `peringatan` "Pesanan {no} sudah dilepas ke gudang ({status});
    membatalkan kwitansi tidak menahan barang — tahan pesanan atau hubungi Gudang bila perlu." bila pesanan sudah
    `confirmed` atau lebih jauh.
  - Audit: `bank_line_receipt_created`, `bank_line_receipt_voided`.

- [ ] **Step 1: Uji gagal** — `test_F1_4_endpoint.py`:
  - `test_impor_mengembalikan_jumlah_otomatis_dan_kartu` (berkas dua baris: satu sempurna, satu nominal beda).
  - `test_pengaturan_mati_impor_tanpa_kwitansi` (Review Focus 4): `kwitansi_otomatis == 0`, `kartu == 1`.
  - `test_cocokkan_otomatis_memproses_kartu_yang_kini_sempurna`: kartu `nominal_beda` lalu Finance mencatat sebagian
    sehingga sisa = nominal mutasi → `/auto-match` → otomatis.
  - `test_kwitansi_dari_mutasi_atomik`: 1 permintaan → kwitansi + baris `matched`; `create_receipt` sukses tetapi
    `_link` dipaksa gagal → tidak ada kwitansi `posted` tanpa tautan (dibatalkan/rollback) **atau** pemanggilan ulang
    menautkan kwitansi yang sama (pilih satu, uji membuktikannya).
  - `test_kwitansi_dari_mutasi_tolak_selama_laporan_menunggu` (409 dengan nomor LB) dan
    `test_kwitansi_dari_mutasi_dengan_laporan_diterima` (`payment_report_id` → laporan `diterima`, baris `matched`).
  - `test_izin`: sales (tanpa `cash.create`) → 403; finance tanpa `ar_receipt.void` → 403 untuk void-receipt;
    manager → 200.
  - `test_batal_kwitansi_mutasi`: baris `unmatched`, `f1.status="dibatalkan"`, kwitansi `void`; `/auto-match` sesudahnya
    tidak membuat kwitansi baru; pesanan sudah `confirmed` → `peringatan` ada.
  - `test_pt_lain_403` untuk kedua rute baru.
- [ ] **Step 2:** Jalankan → FAIL.
- [ ] **Step 3:** Implementasi rute + fungsi layanan; atomik manual: klaim baris dulu, lalu `create_receipt`, lalu
  `_link`; bila `_link` gagal → `void_receipt` dengan alasan sistem "tautan mutasi gagal" dan galat 409 berkalimat
  (keputusan builder, diuji di Step 1).
- [ ] **Step 4:** Jalankan → PASS; ulang `test_F1_*.py`.
- [ ] **Step 5: Commit** `feat(pembayaran): F1 endpoint — impor & cocokkan otomatis memproses mutasi berkode, kwitansi dari mutasi atomik, batal kwitansi mutasi`

### Task 5: Antrean Meja Keuangan "Mutasi berkode perlu dicek"

**Files:**
- Modify: `backend/services/work_desk_service.py`
- Test: `backend/tests_mem/test_F1_5_meja.py`

**Interfaces:**
- Consumes: penanda `f1` (Task 3).
- Produces: antrean `mutasi_berkode` (label "Mutasi berkode perlu dicek", petunjuk "Mutasi bank berkode bayar yang
  belum bisa menjadi kwitansi otomatis. Baca alasannya, lalu Catat kwitansi dari mutasi atau buka Rekonsiliasi.") di
  `finance_desk`, hanya bila pengguna memegang `cash.create` **dan** `ar_receipt.create`; baris dari
  `bank_statement_lines` ber-PT cakupan dengan `f1.status == "kartu"` dan `status == "unmatched"`:
  `_row(ref_type="bank_statement_line", ref_id=line.id, number=order_number or kode, title=customer_name or
  counterparty, subtitle="{stmt_date} · {nama rekening} · {kode} · {alasan}", value=amount, badge=alasan_kode,
  action="Catat kwitansi", action_kind="receipt_from_line", extra={line_id, order_id, order_number, customer_id,
  bank_account_id, stmt_date, ref, codes, alasan, alasan_kode, report_id})`.

- [ ] **Step 1: Uji gagal** — `test_F1_5_meja.py`: antrean muncul untuk finance; tidak untuk sales_admin; baris kartu
  tampil dengan `badge == "nominal_beda"` dan subtitle berisi alasan; baris `otomatis`/`lewati`/PT lain tidak tampil;
  `verify_approval_queues` tetap hijau (antrean tanpa pintu putusan baru).
- [ ] **Step 2:** FAIL. **Step 3:** Implementasi. **Step 4:** PASS (+ `test_LB6_layar.py`, `test_MEJA_*`).
- [ ] **Step 5: Commit** `feat(pembayaran): F1 antrean Meja Keuangan mutasi berkode perlu dicek`

### Task 6: Layar — Meja Keuangan, form kwitansi dari mutasi, Rekonsiliasi, pratinjau kwitansi, notifikasi

**Files:**
- Create: `frontend/src/features/finance/bank/bankLineReceiptApi.js`, `frontend/src/features/desks/BankLineQueuePanel.jsx`
- Modify: `frontend/src/features/finance/FinanceDesk.jsx`, `frontend/src/features/desks/deskPanels.js`,
  `frontend/src/features/sales_admin/workDeskApi.js` (label lencana alasan),
  `frontend/src/features/finance/payments/ReceivePaymentModal.jsx`,
  `frontend/src/features/finance/BankReconciliationView.jsx`, `frontend/src/features/finance/bank/ReconLinesTable.jsx`,
  `frontend/src/features/finance/bank/ReconImportPanel.jsx`, berkas badan pratinjau kwitansi di
  `frontend/src/features/documents/preview/bodies/`, `frontend/src/components/NotificationCenter.jsx`,
  `frontend/src/features/notifications/notifDocTarget.js`
- Test: `frontend/src/features/__tests__/f1KwitansiMutasi.test.js`

**Interfaces:**
- Consumes: rute Task 4, antrean Task 5.
- Produces:
  - `receiptFromLine(lineId: string, payload: object, idemKey: string) => Promise<{receipt, line, released_order_ids}>`
    (POST `/api/bank-reconciliation/lines/{id}/receipt`, header `Idempotency-Key`);
    `voidLineReceipt(lineId: string, reason: string, idemKey: string) => Promise<{order_released, peringatan}>`.
  - `ReceivePaymentModal` prop `bankLineId`: simpan lewat `receiptFromLine` (satu permintaan; `linkBankLine` lama
    dihapus); prop baru `paymentReportId` diteruskan.
  - Label lencana alasan (kamus `BADGE_LABEL`): `nominal_beda` "Nominal beda", `kode_ganda` "Dua kode",
    `rekening_beda` "Rekening beda", `rekening_tolak_cara` "Rekening tak menerima cara bayar", `pesanan_mati` "Pesanan batal",
    `sudah_lunas` "Sudah lunas", `laporan_beda` "Laporan bayar beda", `laporan_diproses` "Laporan sedang diproses",
    `laporan_dan_kwitansi` "Kwitansi & laporan menunggu", `periode_tutup` "Periode ditutup", `pt_tidak_jelas` "PT tak jelas",
    `selisih_perlu_putusan` "Perlu putusan selisih", `otomatis_mati` "Otomatis mati", `galat` "Gagal otomatis".
  - `NotificationCenter` `TYPE_LABEL.bayar_masuk_mutasi = "Pembayaran masuk (mutasi bank)"`,
    `TYPE_LABEL.ringkasan_mutasi_otomatis = "Kwitansi otomatis dari mutasi"`; `notifDocTarget`: pertama → pesanan,
    kedua → Meja Keuangan.

- [ ] **Step 1: Uji gagal** — `f1KwitansiMutasi.test.js` (pola mock axios `lb8MejaHp.test.js`):
  - Meja Keuangan: kelompok "Uang masuk perlu dicatat" memuat antrean `mutasi_berkode` untuk pengguna ber-`cash.create`
    + `ar_receipt.create`; tersembunyi tanpa `cash.create`; `panelFor(row, {id:"uang_masuk"})` baris `_queue:"mutasi_berkode"`
    → `BankLineQueuePanel`.
  - Panel: menampilkan alasan, pratinjau pesanan (`order_id`), tombol "Catat kwitansi" membuka `ReceivePaymentModal`
    dengan `bankLineId`, nominal/tanggal/rekening/referensi terisi dari baris; bila `extra.report_id` ada: tombol
    "Terima laporan ini dengan mutasi ini" memanggil `receiptFromLine` dengan `payment_report_id`.
  - `ReceivePaymentModal` dengan `bankLineId`: simpan → tepat SATU `axios.post` ke `/lines/{id}/receipt`; tidak ada
    POST `/ar-receipts` maupun `/match`.
  - Rekonsiliasi: baris `f1.status="kartu"` menampilkan alasan (`recon-f1-reason-{id}`); baris `match_type="auto_receipt"`
    berlencana "Kwitansi otomatis" (`recon-f1-auto-{id}`) dan tombol "Batalkan kwitansi" (`recon-f1-void-{id}`) hanya
    untuk pemegang `ar_receipt.void` → konfirmasi beralasan → `voidLineReceipt`; `peringatan` respons ditampilkan.
  - Pesan sukses impor & "Cocokkan otomatis" memuat "{n} kwitansi otomatis" dan "{m} perlu dicek" bila > 0.
  - Pratinjau kwitansi `source="mutasi_bank"` menampilkan "Lahir dari mutasi bank".
  - `TYPE_LABEL` dua jenis baru + `notifDocTarget`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementasi (pola panel = `PayReportQueuePanel`; konfirmasi = `askReason` dengan
  `reasonMinLength: 5`, `testId: "recon-f1-void-reason"`). **Step 4:** PASS + suite terkait
  (`lb8MejaHp`, `lb7RincianPesanan`, `pmt3KwitansiRekening`, `pk15ReconHolding`, `pelatihanKasBank`).
- [ ] **Step 5: Commit** `feat(pembayaran): F1 layar — antrean mutasi berkode, kwitansi dari mutasi atomik, lencana & batal di Rekonsiliasi`

### Task 7: Dokumen, suite penuh, gate, tangkapan, laporan (pengendali)

**Files:**
- Modify: `docs/blueprint/04_POLA_UI.md` (pola "mutasi berkode → kartu"), `CODEBASE_MAP.md`
  (`python3 scripts/gen_codebase_map.py`), materi latihan rekonsiliasi bila skenarionya menyebut "Catat sebagai
  kwitansi" dua langkah (`docs/pelatihan/2026-11-18_keuangan/rekonsiliasi/`) — catatan "berubah sejak F1".
- Create: `docs/superpowers/plans/2026-11-27-kwitansi-otomatis-mutasi-hasil.md` + folder (skrip tangkapan, tangkapan).

- [ ] **Step 1:** Suite penuh `tests_mem` + jest di latar pada pohon akhir; bandingkan dengan Lapor Bayar (3012 / 2108).
- [ ] **Step 2:** Gate `--quick` + `--ci` sekali; dua pembanding; pelanggaran baru = penghalang (residu penjadwal diuji ulang).
- [ ] **Step 3:** Tangkapan di data acuan lokal (bukan data nyata): skrip membuat pesanan CBD tertahan + DP, rekening
  penerimaan, berkas CSV mutasi (satu sempurna, satu nominal beda, satu dua kode), impor lewat layar → pesan jumlah;
  pesanan CBD lepas; Meja Keuangan kartu → Catat kwitansi; Rekonsiliasi lencana + batal (manajer).
- [ ] **Step 4:** Laporan hasil (yang berubah, tugas → commit, uji apa adanya, gate, keputusan pelaksanaan, untuk pemilik).
- [ ] **Step 5: Commit** `docs(pembayaran): hasil F1 kwitansi otomatis dari mutasi`
