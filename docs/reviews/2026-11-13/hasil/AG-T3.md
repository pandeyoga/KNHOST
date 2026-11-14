# AG-T3 — Asisten: kartu tindakan golongan A dan B lewat pintu aplikasi

- Commit awal: `1204bac` (worktree kerja, basis B)        - Commit akhir: (a) `78bbbd9`, (b) `6407e72`, cek layar `352d8b5`, pop-up `2f0fd32`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke HEAD tujuan: lihat "Penggabungan"
- ID ditangani: — (unit fitur; tidak menutup temuan)
- Keputusan: K-44 (kartu disetujui satu orang = pembuatnya; uang keluar/jurnal/orang kedua = AG-T5), K-45 (Asisten Keuangan
  mati per akun sampai dinyalakan) · Standar: §1, §2.1, §2.4, §3.2, §3.4 (N1–N5), §4 (L1, L3, L4, L8), §5 (D3, D7, D9), §6 ·
  Risiko tinggi — dua serah-terima (`00` §8) · Titik henti **H5**: sakelar per PT `ai.tindakan_uang_masuk` dibiarkan mati
  (bawaan `false`); tidak dinyalakan untuk PT nyata.
- Prasyarat: AG-T2, PK-15, PK-18, PK-21 (semua di basis); PK-19 (`ar_allocation_service`) juga di basis — kartu kwitansi
  mengikuti bentuk endpoint saat ini.

## Cek ulang "Keadaan sekarang" (di `1204bac`; blueprint dibaca di `3132cc4`)

| # | Hasil |
|---|---|
| 1 | Berlaku, bergeser: `_exec_po` memanggil `po_router._create_po_core` langsung `ai_actions.py:251`, `create_notification` `:268`; izin diulang sendiri di `_po_siap` (AG-T1) |
| 2 | Berlaku, bergeser: `_perm_ar_receipt_create` `routers/ar_receipts.py:77`, `resolve_requested_entity` `:89`, `preflight_posting` `ar_receipt_service.py:237`. Sesudah PK-19 target alokasi diperiksa `ar_allocation_service.validate_targets` sebelum efek pertama |
| 3 | Sebagian berubah: `/api/ar-receipts` ber-idempotensi (`idempotency.py:25`, `doc_id` `:84`); **`/api/bank-reconciliation/lines/` sudah ada** (PK-21) — yang belum: `/api/bank-reconciliation/` (sisanya), `/api/finance/posting-failures/`, `/api/customers/…`, `/api/collection-reminders`, `/api/purchase-orders` |
| 4 | Berlaku, bergeser: `mark_reminder` `routers/crm.py:222`, `add_followup` `:243` (`order.update` + `can_collect_customer`); `outcome` `schemas_crm.py:107` |
| 5 | Berlaku, bergeser: `match_line` `routers/bank_reconciliation.py:274`, `allocate_holding` `:413` (`cash.create`) |
| 6 | **Sudah berubah** (PK-18): ulang posting `routers/posting_failures.py:72` membaca registri `services/posting_registry.py` (26 jenis, bukan 5); `SOURCES` `:25` dibentuk dari registri; jawaban `{kind, id, gl_status, journal_entry_id}`; galat jalur ulang non-HTTP → 409 "Posting masih gagal: …" |
| 7 | Berlaku, bergeser: `open_orders` `routers/ar_receipts.py:48` (cakupan PT dari sesi) |
| 8 | Berlaku: tidak ada endpoint lampiran kwitansi/tindak lanjut → `attach_proof` tidak dibuka |
| 9 | Berlaku: `TanyaKnView.jsx:24` (`TABS`, lima tab; enam di layar sempit) |
| 10 | **Sebagian berubah** (PR-T7): `AskKnButton` sudah memakai izin `ai.view` (`AskKnButton.jsx:22`), bukan daftar nama peran; `CONTEXT_TYPES` `ai_chat_service.py:150` (sembilan jenis) tanpa jenis keuangan |
| (temuan) | `SelfApi` (AG-T2) sudah punya mode tulis + `card_id`, tetapi header bernama `X-Ai-Card` dan tanpa pembatas jalur tulis — diganti `X-Asisten-Kartu` + daftar jalur terdaftar |
| (temuan) | Uji CR-T1 `test_CRT1_kontrol_dan_idempotensi_terdaftar` menjaga `/api/customers/{id}` tetap DI LUAR idempotensi — lihat Menyimpang 1 |

## Fitur — mesin kartu golongan A/B (serah-terima a)

- Berlaku di HEAD: belum ada (U1–U17 merah di kode lama: peran uji ber-`ai_finance.create` ditolak "Aksi ['create'] tidak
  berlaku untuk “Asisten Keuangan”" — `bukti/AG-T3/a_merah_kode_lama.log`; `POST /api/ai/tools/prepare_action` di kode lama =
  "Tool tidak dikenal", `GET /api/ai/actions` tidak ada).
- Perubahan perilaku (sebelum → sesudah):
  - **`backend/services/ai_cards.py`** (baru): `CardAction(code, label, cls, risk, write_method, write_path, prepare,
    build_request, result_of, editable)`, `REGISTRY` (7 tindakan tabel spesifikasi; `attach_proof` tidak dibuka →
    "Tindakan ini tidak bisa dilakukan lewat asisten. Lakukan di layarnya."), `prepare`, `decide`, `dismiss`, `fingerprint`,
    `read_fingerprint`, `list_cards`, `write_allowed`, `supersede_pending`/`insert_card`, `tool_result`.
    - `prepare`: tindakan dikenal → tolak "Semua PT" (400) → tolak `entity_id` di argumen (400 "PT diambil dari sesi…") →
      gerbang Asisten Keuangan (`ai_finance.view` + sakelar akun) → golongan B: `ai_finance.create` (403 Z6) → `B` di
      `users.ai_finance.classes` (403 "…belum dinyalakan untuk akun Anda.") → `ai.tindakan_uang_masuk` PT kartu (409
      "…belum dinyalakan untuk {nama PT}.") → `CardAction.prepare` lewat `SelfApi` **baca-saja** (header PT = PT aktif) →
      sidik sha256 atas potret `fingerprint_source` (dibaca lewat GET yang sama) → kartu `pending` lain di percakapan yang
      sama → `superseded` (+`superseded_by`) → sisip (`DuplicateKeyError` indeks `uq_pending_session` → ulang sekali) →
      jejak `ai_card_prepared`. Tidak ada tulisan lain; giliran model berhenti di sini.
    - `decide(approve)` berurutan sesuai spesifikasi: muat (kedaluwarsa diterapkan `ai_actions.load`) · pembuat (403) · status
      (409 "Kartu ini sudah dijalankan." / "…gagal dan tidak bisa diulang." / "…sudah diganti kartu yang lebih baru." /
      "…sudah diabaikan." / "…sudah kedaluwarsa…" / "…sedang diproses.") · PT kartu ∉ akses 403, PT aktif ≠ PT kartu atau
      Semua PT 409 · sakelar golongan B (ulang) · konfirmasi (`medium`/`high`: alasan ≥ 10 huruf; `high`: digit `retype` =
      digit `plan.confirm_text`) · `edits` hanya `editable` (selain itu 400) → `prepare` diulang, `plan` diganti, **sidik tetap
      yang lama** · batas harian `ai.tindakan_maks_per_hari` (kartu `confirmed` pengguna sejak 00.00 WIB; 409) · klaim atomik
      `pending → running` (+ `reason`, `edits`, `decided_by/at`) · baca ulang sidik → beda = `failed`/`stale` (200, pesan
      spesifikasi) · **satu** panggilan tulis `SelfApi(read_only=False, card_id)` dengan `Idempotency-Key` dan
      `X-Asisten-Kartu` = id kartu (putus koneksi/batas waktu → ulang sekali, kunci sama) · 2xx → `confirmed`
      (`result.document`, `result.gl_status` dari jawaban pintu) · ≥ 400 → `failed`/`door` dengan pesan asli; 5xx/galat
      di dalam pintu/kunci sedang diproses → `failed`/`uncertain` · jejak `ai_card_confirmed`/`ai_card_failed`.
  - **`backend/ai_card_context.py`** (baru): middleware ASGI `AiCardMiddleware` (dipasang di `server.py`) menaruh id kartu
    di `ContextVar` **hanya bila** kartu `running` dan milik pengguna sesi (`idempotency._session_user_id`); header lain
    diabaikan. Pembaca `current_card_id()` / `card_field()`.
  - `ai_card_id` ditulis layanan tujuan: `ar_receipt_service` (dokumen kwitansi), `routers/crm.py` (`add_followup`,
    `mark_reminder`), `bank_recon_service._link` (catatan cocok; dicocokkan di layar → field dihapus) dan butir
    `holding_allocated[]`, `routers/posting_failures.py` (jejak `posting_failure_retried` saja).
  - `SelfApi`: header `X-Asisten-Kartu` (dulu `X-Ai-Card`); mode tulis hanya menerima `write_path` tindakan terdaftar
    (403 "Asisten hanya boleh menulis lewat pintu kartu tindakan yang terdaftar." tanpa memanggil aplikasi); `last_status`.
  - Idempotensi: awalan `/api/bank-reconciliation/`, `/api/finance/posting-failures/`, `/api/collection-reminders`,
    `/api/purchase-orders` + pola `^/api/customers/[^/]+/followups/?$` (Menyimpang 1).
  - Indeks: `ai_action_proposals` `(entity_id, status)`; **`uq_pending_session`** unik parsial `(session_id)`
    `{status: "pending", session_id > ""}` di `REQUIRED_UNIQUE_INDEXES` (D7; uji lapis A U13). Kartu lama (`propose_action`)
    kini juga menggantikan kartu menunggu di percakapan yang sama (Menyimpang 3).
  - Endpoint (`routers/ai_assist.py`): `GET /api/ai/actions?box=mine|others|done|failed&page&page_size` →
    `{items, total, page, page_size}` (kartu milik pengguna; kedaluwarsa diterapkan sebelum dihitung; `others` kosong sampai
    AG-T5); `POST /api/ai/actions/{id}/confirm` `{reason, retype, edits}` (kartu baru → `ai_cards.decide`; kartu lama →
    `ai_actions.confirm` seperti AG-T1); `POST /api/ai/actions/{id}/dismiss` `{reason}`. `POST /api/ai/tools/prepare_action`
    `{action, args, user_request, session_id}` (gerbang Asisten Keuangan; jawaban `{proposal_id, …, card}`).
  - Alat model `prepare_action` (`data/ai/tools_kn_tindakan_v1.json`, mode ketat) hanya di mode Keuangan; masuk
    `ACTION_TOOLS` (ditolak "Alat tindakan tidak tersedia pada giliran ini." sesudah alat teks bebas); hasil alat ke penyedia
    hanya baris nominal & total (tanpa nama pihak, K-43). Instruksi keuangan butir 7. `CONTEXT_TYPES` + `journal_entry`,
    `ar_receipt`, `bank_line`, `period`.
  - Tindakan & pintu: `followup_note`, `payment_promise` (tanggal wajib → `outcome=promised`, `next_action_date`),
    `collection_reminder` (golongan A, `low`; pelanggan harus punya pesanan di PT aktif — dibaca `GET /api/sales-orders`);
    `ar_receipt_create` (B, `high`; sidik `open-orders` sisa tiap pesanan + `deposit`; baris "Sisa tagihan {nomor}"; isian
    ubah tanggal/cara bayar/catatan; `account_id` opsional mengikuti endpoint PK-20), `bank_match` (B, `low`; sidik
    `…/candidates` status baris + sisa kandidat), `holding_allocate` (B, `low`; sidik `holding` + `open-orders`),
    `posting_retry` (B, `low`; sidik baris di `GET /api/finance/posting-failures` berhalaman).
- Izin & pengaturan: `ai_finance.create` ("Siapkan dan setujui tindakan") di empat tempat — `permissions_config.AGT3_DEFAULT_PAIRS`
  (admin, manager, finance) · `access_modules` (`ACTION_LABEL`; sumber daya `ai_finance` sudah di modul `assistant`) · pemeriksa
  `ai_cards._sakelar_b` (prepare & decide) · uji (Tanpa Acuan tanpa izin → 403 golongan B; Manajer Kosong → 403). Sakelar akun
  `users.ai_finance.classes` lewat `PATCH /api/users/{id}` oleh pemegang `ai.configure` (`["B"]` atau `[]`; isian yang tidak
  dikirim dipertahankan); layar akun mendapat sakelar "Boleh menyetujui kartu uang masuk". Pengaturan `ai.tindakan_uang_masuk`
  (bool, bawaan mati, global+PT, `high` + alasan, `ai.configure`) dan `ai.tindakan_maks_per_hari` (int 0–1000 kartu, bawaan 0
  = tanpa batas, `low`, `ai.configure`) di kelompok `asisten-analitik`, sub-judul `tanya-kn-tindakan`.
- Status: implemented_pending_review

## Pengalihan jalur lama (serah-terima b)

- `ai_actions._exec_po`: tiap PO lewat `POST /api/purchase-orders` (`SelfApi` mode tulis, sesi & header PT kartu, isi tanpa
  `entity_id`, kunci `<id kartu>:<urutan>`); hasil sebagian AG-T1 tetap (nomor PO disimpan sebelum PO berikutnya; galat pintu =
  `failed` + yang sudah jadi). Pemanggilan `_create_po_core` dicabut (uji statik). `LEGACY_WRITE_PATHS` = `POST
  /api/purchase-orders`. `confirm(…, request)` meneruskan sesi permintaan.
- Pengingat ke sales (`collection_followup`, `customer_followup`) tetap `create_notification` — **satu-satunya pengecualian**
  (tidak ada endpoint layarnya; dicatat di kode).
- Uji Tanya KN lama `test_AGT1_kartu.py` 19/19 hijau (U1 memaksa `_create_po_core` gagal pada panggilan ke-2 — kini lewat
  endpoint, hasil sama).
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_AGT3_kartu_tindakan.py` (25 uji, serah-terima a), `test_AGT3_pengalihan.py` (4, b), lapis A
`backend/tests/test_bp_AGT3_kartu_bersamaan.py` (U5, U13 — ditulis), jest `frontend/src/features/__tests__/agt3KartuTindakan.test.js`
(14). Merah kode lama: `bukti/AG-T3/a_merah_kode_lama.log` (25/25 galat persiapan), `a_jest_merah_kode_lama.log` (modul tidak ada),
`b_merah_kode_a.log` (b1, b4 merah di keadaan (a)).

| ID | Lapis | Merah di kode lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | ya (persiapan: izin `ai_finance.create` tidak dikenal; alat tidak ada) | Lulus — `pending`, B/`high`; `plan.rows[0]` "Sisa tagihan SO-…" 8.000.000 → 3.000.000; `confirm_text` "5000000"; kwitansi 0; sidik 64 huruf; `editable` tanggal/cara bayar/catatan |
| U2 | B | ya (idem) | Lulus — tanpa alasan 400 "Tulis alasan singkat (minimal 10 huruf)."; `retype` "500000" 400 "Ketik ulang nominal persis seperti di kartu."; tetap `pending` |
| U3 | B | ya (idem) | Lulus — 200 `confirmed`; satu kwitansi 5.000.000 ber-`ai_card_id`; `result.document.number` = nomor kwitansi; `result.gl_status` = `gl_status` kwitansi; pesanan terbayar 5.000.000; satu baris `idempotency_keys` (kunci id kartu, `/api/ar-receipts`); jejak `ai_card_confirmed` |
| U4 | B | ya (idem) | Lulus — 409 "Kartu ini sudah dijalankan."; kwitansi tetap 1 |
| U5 | A | — | **Ditulis, belum dijalankan** (`test_bp_AGT3_kartu_bersamaan.py`: [200, 409], kwitansi +1, satu `idempotency_keys`) |
| U6 | B | ya (idem) | Lulus — 409 "…kedaluwarsa…"; `expired`; tanpa kwitansi baru |
| U7 | B | ya (idem) | Lulus — kwitansi layar 2.000.000 sesudah kartu → 200 `failed`/`stale` pesan spesifikasi; kwitansi kartu 0 |
| U8 | B | ya (idem) | Lulus — pelanggan D (PT lain) 400 "…tagihan terbuka … PT aktif."; `entity_id: ent_kanda` di argumen 400; kartu tidak bertambah |
| U9 | B | ya (idem) | Lulus — `fin` (KSC saja) dengan `X-Entity-Id: ent_kanda` 403 (penjaga PT); `fin2` (KSC + Kanda) 409 "Kartu ini disiapkan untuk …"; keduanya tetap `pending` |
| U10 | B | ya (idem) | Lulus — `classes: []` → 403 pesan akun; dikembalikan (isian `enabled` dipertahankan) dan PT KSC dimatikan → 409 pesan PT; Kanda (bawaan mati) 409; KSC menyala lagi tidak mengubah Kanda; kartu disiapkan lalu sakelar akun dimatikan → setujui 403, tetap `pending` |
| U11 | B | ya (idem) | Lulus — akun tanpa `ar_receipt.create`: 200 `failed`/`door`, `error` = detail 403 endpoint (diadu dengan `POST /api/ar-receipts` langsung), `status_code` 403; kwitansi 0; jejak `ai_card_failed` |
| U12 | B | ya (idem) | Lulus — kartu ke-2 di `session_id` sama → kartu ke-1 `superseded` (`superseded_by`); setujui 409 "…diganti kartu yang lebih baru."; satu `pending` per percakapan; kartu lama `propose_action` di percakapan itu ikut menggantikan |
| U13 | A | — | **Ditulis, belum dijalankan** (indeks `uq_pending_session` unik; sisipan kedua `DuplicateKeyError`; kartu `superseded`/tanpa percakapan tidak ikut) |
| U14 | B | ya (idem) | Lulus — naskah `get_document` → `prepare_action` dijawab "Alat tindakan tidak tersedia pada giliran ini."; kartu 0; daftar alat di `.calls` memuat `prepare_action` dan tidak memuat alat menyetujui. U14b: percakapan tanpa teks bebas → kartu `pending` ber-`request` & `session_id`; hasil alat ke penyedia tanpa nama pelanggan |
| U15 | B | ya (idem) | Lulus — tanpa tanggal 400 "Tanggal janji bayar wajib diisi."; dengan tanggal → setujui tanpa alasan 200 `confirmed`; satu `collection_followups` `promised` ber-`ai_card_id`; idempotensi pola `/followups` (bukan `/api/customers/{id}`) |
| U16 | B | ya (idem) | Lulus — kwitansi `gl_status: failed` (fixture), jalur ulang dipaksa gagal → `failed`/`door`, pesan "Posting masih gagal: …"; setujui lagi 409 "Kartu ini gagal dan tidak bisa diulang." |
| U17 | B | ya (idem) | Lulus — `POST /api/ar-receipts` dengan `X-Asisten-Kartu: aiact_palsu` dan dengan id kartu `pending` → kwitansi tanpa `ai_card_id` |
| U18 | layar | ya (modul `TanyaActions` tidak ada) | Uji komponen 14/14: saringan "Menunggu saya · Menunggu orang lain · Selesai · Gagal", kolom "Tindakan · PT · Nominal · Dibuat · Berlaku sampai · Status", pilih baris → kartu → setujui: pop-up "Jalankan Catat kwitansi piutang sebesar Rp 5.000.000 untuk Sukacita?" ("Ya, jalankan"/"Batal") → "Berhasil — Kwitansi Pelanggan AR-…" + "Jurnal: terposting". **Uji jalan peramban belum dilakukan** |
| (+) A lain | B | ya | Lulus — tindak lanjut (`no_response`) & tanda sudah diingatkan lewat pintu layar ber-`ai_card_id`; pelanggan PT lain 404 |
| (+) B lain | B | ya | Lulus — ulang jurnal berhasil (`gl_status` posted, jejak audit ber-`ai_card_id`, kartu baru untuk dokumen yang sudah terposting 404); cocokkan mutasi (catatan cocok ber-`ai_card_id`; cocok ulang di layar tanpa field); alokasi titipan 10.000.000 − 4.000.000 = 6.000.000 dan sisa tagihan 8.000.000 → 4.000.000, `gl_status` posted, butir ber-`ai_card_id` |
| (+) pintu/izin/batas/daftar/isian | B | ya | Lulus — `SelfApi` mode tulis menolak jalur tak terdaftar tanpa memanggil aplikasi; Tanpa Acuan tanpa `ai_finance.create` 403 golongan B, golongan A 200; Manajer Kosong 403; batas harian 1 untuk KSC → kartu ke-2 409 "Batas tindakan asisten hari ini sudah tercapai (1).", Kanda (0) tidak ikut; daftar per kotak (milik sendiri, `others` kosong, saringan tak dikenal 400); abaikan + abaikan lagi 409; isian `amount` ditolak 400, `notes` dipakai (kwitansi bercatatan, `args_initial` tetap) |
| (b) b1–b4 | B | b1, b4 ya (keadaan a); b2, b3 tidak (awalan lahir di a; perilaku AG-T1 tetap) | Lulus — 2 PO lewat endpoint (PT dari header), kunci `<id>:0`, `<id>:1` di `/api/purchase-orders`; kirim ulang kunci sama = jawaban pertama (1 PO); PO ke-2 ditolak → `failed` + 1 PO; statik: tanpa `_create_po_core`, `create_notification` hanya di `_exec_reminders` |

Fixture vs alur: pelanggan, pesanan (+ jurnal pendapatan), rekening, mutasi bank & transaksi kas, kwitansi gagal jurnal,
geser `expires_at`, catatan bersisipan perintah = FIXTURE; peran, sakelar akun, pengaturan, kartu, persetujuan, kwitansi layar,
titipan, percakapan = ALUR API. U16/ulang berhasil memaksa jalur ulang lewat `monkeypatch` registri.

Angka (hitungan tangan di docstring uji): U1 8.000.000 − 5.000.000 = 3.000.000; U7 sisa 8.000.000 → 6.000.000 (kwitansi layar
2.000.000) ≠ potret → `stale`; titipan 10.000.000 − 4.000.000 = 6.000.000.

## Uji lama yang disesuaikan (angka, bukan harapan dilonggarkan)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` | `+ AGT3_KUNCI` (= 2) di U04 | dua kunci baru berizin `ai.configure` |
| `tests_mem/test_PRT9_izin_bawaan.py` | `TAMBAHAN_SESUDAH` + `AGT3_DEFAULT_PAIRS` | izin bawaan baru `ai_finance.create` |
| `tests_mem/test_PK14_indeks_wajib.py`, `tests/test_bp_PK14_indeks_wajib.py` (lapis A) | `+ AGT3_INDEKS` (= 1); 22 → 23 | indeks wajib baru `uq_pending_session` |
| `configKeyIndex.json`, `access_builtin_fixture.json` | dibangkitkan ulang | kunci & izin baru (`test_fe03_access_catalog --noconftest` 6/6) |

## Berkas berubah

Server (baru): `backend/ai_card_context.py`, `backend/services/ai_cards.py`, `backend/data/ai/tools_kn_tindakan_v1.json`.
Server (ubah): `server.py` (middleware), `idempotency.py`, `indexes.py`, `config_catalog_ai.py`, `permissions_config.py`,
`access_modules.py`, `routers/ai_assist.py`, `routers/ai_analytics.py` (`prepare_action`), `routers/users.py` (`classes`),
`routers/crm.py`, `routers/posting_failures.py`, `services/ai_self_api.py`, `services/ai_chat_service.py`, `services/ai_actions.py`
(kartu menggantikan; (b) draf PO lewat endpoint), `services/ar_receipt_service.py`, `services/bank_recon_service.py`,
`data/ai/system_prompt_kn_keuangan_v1.md`. Layar: `features/tanya/TanyaActions.jsx` (baru), `TanyaActionCard.jsx`,
`TanyaKnView.jsx`, `tanyaApi.js`, `tanya.css`, `components/AskKnButton.jsx`, `features/finance/JournalDetailModal.jsx`,
`ARAgingDetail.jsx`, `ClosingView.jsx`, `bank/ReconLinesTable.jsx`, `features/settings/entities/AccountFormDrawer.jsx`,
`configKeyIndex.json`, fixture akses. Uji: dua `tests_mem/test_AGT3_*`, `tests/test_bp_AGT3_kartu_bersamaan.py`, jest
`agt3KartuTindakan.test.js`, empat uji lama di atas. Dokumen: `ENTITY_REGISTRY.md` (field kartu, `ai_card_id` di tiga koleksi,
`users.ai_finance.classes`, indeks), `CODEBASE_MAP.md` (generator), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`
§9.8 ("kartu tindakan", tab Tindakan, tindakan uang masuk, "Tanya soal layar ini").

## Menyimpang dari blueprint

1. **Idempotensi tindak lanjut lewat pola, bukan awalan `/api/customers/`.** Uji CR-T1 menjaga `/api/customers/{id}` tetap di
   luar idempotensi; awalan luas memerahkannya dan memperluas risiko yang disebut spesifikasi. Dipakai pola
   `^/api/customers/[^/]+/followups/?$` (pintu satu-satunya kartu yang berawalan `/api/customers/`). Usulan teks pengganti
   kalimat "Awalan yang ditambahkan…": "Awalan yang ditambahkan ke `IDEMPOTENT_PREFIXES`: `/api/bank-reconciliation/`,
   `/api/finance/posting-failures/`, `/api/collection-reminders`, `/api/purchase-orders`; pola `IDEMPOTENT_PATTERNS`:
   `^/api/customers/[^/]+/followups/?$`."
2. **Gerbang `prepare_action`** = gerbang Asisten Keuangan (`ai_finance.view` + sakelar akun `enabled`) untuk SEMUA golongan;
   golongan A tidak menuntut `ai_finance.create`/`classes`/sakelar PT (sesuai "golongan A tidak menuntut sakelar tambahan").
   Persetujuan kartu menuntut `ai.view` + pembuat (+ sakelar golongan B).
3. **Kartu lama ikut "satu kartu menunggu per percakapan".** Indeks `uq_pending_session` berlaku untuk satu koleksi, jadi
   `ai_actions.propose_action` (draf PO/pengingat) kini memanggil `ai_cards.insert_card` — kartu menunggu sebelumnya di
   percakapan yang sama `superseded` (tanpa itu kartu lama kedua di percakapan yang sama gagal 500 di MongoDB asli). Disentuh
   di (a) karena indeksnya lahir di (a).
4. **Isian tambahan** di luar tabel Data: `fingerprint_snapshot` (potret yang disidik, D3), `superseded_by`, `plan.meta`,
   `plan.rows[].kind` (money/text/date untuk format layar), `result.document.label`.
5. **Sidik tidak diganti saat isian diubah**: `prepare` diulang untuk `plan`, tetapi pembanding langkah 7 tetap sidik saat
   disiapkan (perubahan data antara disiapkan dan disetujui tetap terdeteksi walau pengguna mengubah catatan).
6. **Alat `prepare_action` di berkas skema sendiri** (`tools_kn_tindakan_v1.json`) — uji AG-T2 U15 mengunci 22 alat keuangan
   dua arah. Daftar alat mode Keuangan = umum + keuangan + tindakan.
7. **"Tanya soal layar ini"**: tombol berlabel itu di rincian jurnal (bilah bawah pop-up), rincian piutang pelanggan (kepala
   rincian — bukan kolom baru di tabel Piutang supaya tabel tidak melebar), dan Tutup Buku; di baris mutasi bank berlabel
   "Tanya asisten" (sel aksi sudah berisi lima tombol). Jenis konteks keuangan dibuka di mode Keuangan bila chat menyala;
   saran pembukanya pertanyaan untuk jenis itu.
8. **Daftar tab Tindakan di panel utama** (enam kolom tidak muat di panel samping 320 px); panel samping menampilkan keterangan
   singkat. Enam tab samping di layar lebar dibungkus dua baris (tidak ada tab tersembunyi di gulir datar).
9. **Tombol setujui dimatikan sebelum alasan/ketik ulang lengkap** dengan alasan tertulis di sampingnya (server tetap menolak
   400 bila dikirim).
10. **`edits` kartu golongan A** tidak dibuka (spesifikasi hanya menyebut isian kwitansi).
11. **`MSG_PROSES_MATI`** untuk kartu baru: "Proses berhenti sebelum selesai. Periksa dokumennya sebelum meminta kartu baru."
    (`error_code` `uncertain`); kalimat PO AG-T1 tetap untuk draf PO.

## Asumsi

- Spesifikasi: golongan A tanpa sakelar baru; batas harian bawaan 0; alasan ≥ 10 huruf = validasi isian (konstanta
  `REASON_MIN`, dihitung dari panjang teks yang dipangkas); kartu baru di percakapan yang sama menggantikan.
- Pelanggan kartu golongan A harus punya pesanan di PT aktif (dibaca `GET /api/sales-orders` berizin `order.view`), karena
  pintu tindak lanjut tidak mengadu PT pelanggan; nama pelanggan di rencana dari pesanan terbarunya.
- Kartu kwitansi wajib minimal satu alokasi; sisa nominal di atas Σ alokasi menjadi deposit (baris "Deposit pelanggan").
- `reason_code` titipan kosong = "Pengirim akhirnya teridentifikasi" (kode yang sama dengan layar) dan tampil di rencana.
- Batas teknis (konstanta): halaman daftar 20/100, pembacaan sidik berhalaman ≤ 10 halaman, kandidat pencocokan 100.

## Cek layar (KN_37 + KN_08 + UX_USABILITY) — dari kode; integrator memotret 1280/1024/390

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati beralasan | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/angka 0 |
|---|---|---|---|---|---|---|---|---|
| Kartu tindakan (percakapan & tab) | Tabel Rencana 3 kolom `data-table head-wrap`, `table-layout: fixed`, label 44 %, `overflow-wrap: anywhere` | `.tanya-action` berbantalan `--sp-4` | Kepala = judul + pil saja; PT/berlaku, ringkasan, rencana, isian, bilah tombol masing-masing baris sendiri | "Setujui dan jalankan" mati dengan kalimat tertulis: "Pilih satu PT untuk menyetujui kartu." · "Pindah ke {PT} untuk menyetujui." · "Tulis alasan (minimal 10 huruf) [dan ketik ulang nominal] untuk menyetujui." · "Ketik ulang nominal persis…"; mati juga selama memproses | `status-pill` ikon + teks + token warna: Menunggu · Sedang diproses · Berhasil · Gagal · Diabaikan · Kedaluwarsa · Diganti (`docStatusLabel`) | — (satu kartu) | Teks izin dari server (Z6); tidak ada "bukan wewenang" | Rupiah utuh `kpiValueParts` ("Rp" boleh turun, angka tidak dipatah); nilai kosong "—"; "Jurnal dibuat sistem saat disimpan." hanya bila ada jurnal |
| Tanya KN › Tindakan | Tabel 6 kolom `head-wrap`, `table-layout: fixed`, sel `overflow-wrap`; ≤ 600 px menjadi kartu bertumpuk berlabel (tanpa gulir datar) | `section-card section-pad` | Saringan `FilterChips` di bilah sendiri, jumlah "{n} kartu" di baris sendiri | Pager "Sebelumnya/Berikutnya" mati di ujung dengan "Halaman i dari n" tertulis | Kolom Status = pil ikon + teks | Saringan 4 kotak + halaman 20 + jumlah total | — | Memuat "Memuat kartu…" · galat "Kartu tindakan tidak bisa dimuat. Coba lagi." + tombol · kosong "Belum ada kartu tindakan." — dibedakan, tidak ganda; nominal 0 = "—" |
| Tab samping Tanya KN | Enam tab, dua baris di panel 320 px | — | — | — | — | — | — | — |
| Rincian jurnal / rincian piutang / Tutup Buku / baris mutasi bank | Tidak menambah kolom; tombol di bilah yang sudah `flex-wrap` | Tidak berubah | Rincian piutang: tombol di baris kedua kepala (bersama "Buat Nota Denda"), bukan baris judul | Tidak ada tombol mati baru (tombol tidak tampil tanpa izin `ai_finance.view`) | — | — | Tampil menurut `can` (`ai.view` + `ai_finance.view`), bukan nama peran | — |
| Akun & Akses › sakelar "Boleh menyetujui kartu uang masuk" | — | Di dalam `form-subsection` Asisten keuangan | — | Mati tanpa `ai.configure` dengan kalimat hanya-baca yang sudah ada | Teks Menyala/Mati | — | Menyebut akses 'Siapkan dan setujui tindakan' + pengaturan PT | — |
| Huruf & warna | 12–13 px token (`--fs-12/13`), warna token `kn-*`, tombol `primary-button`/`secondary-button btn-sm` `white-space: nowrap`; tanpa hex baru di JSX | | | | | | | |

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di `0562d29` (= `d07186e` +
STATUS) — satu gate untuk AG-T3 (+ cek layar `352d8b5`) dan PK-43:

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 15 FAIL | 16 | 2: ganti nama `guard:page_tabs` (MN-T1, merah garis dasar yang sama) · **`guard:detail_modal` (INV-UI-08)** | 2 (`config_wiring` + uji-diri) |
| `--ci` | 42 FAIL | 43 | 2 (sama) | 2 |

`guard:detail_modal` merah baru milik **AG-T3**: `features/tanya/TanyaActions.jsx` menyelipkan kartu yang dipilih di bawah
daftar. Diperbaiki di **`2f0fd32`** (kartu dibungkus `DetailModal`, uji komponen U18 memastikan kartu di dalam pop-up);
`verify_detail_modal.py` di pohon sesudah perbaikan: **30 cek lolos, 0 pelanggaran** (sebelumnya 1 pelanggaran) — dipastikan
lagi pada gate berikutnya. Tanpa merah itu hasilnya 14 / 41 (= lari bersih sebelumnya).

Kuitansi: `bukti/AG-T3/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Lapis A, uji jalan U18, dan cek layar (integrator, lingkungan A, HEAD `3998cb4` → `352d8b5`)

- Backend dinyalakan ulang → `scripts/check_required_indexes.py`: **23 dari 23 indeks wajib beres**,
  `ai_action_proposals.uq_pending_session` terpasang, 0 kelompok kembar (`bukti/AG-T3/cek_indeks_wajib_sesudah_restart.txt`;
  sebelum restart 22/23 karena indeks baru belum dibuat — `cek_indeks_wajib_data_acuan.txt`).
- Lapis A `tests/test_bp_AGT3_kartu_bersamaan.py` (U5, U13) + `tests/test_bp_PK14_indeks_wajib.py`: **11 lulus**
  (`bukti/AG-T3/lapis_A.log`).
- `tests_mem` di HEAD `3998cb4`: **1745 lulus / 2 dilewati / 3 xfail**; jest penuh (dengan perbaikan cek layar): **898 lulus**,
  111 suite lulus, 35 suite gagal dimuat (`cmdk`/`@radix-ui`, sama dengan sebelumnya).
- **U18 (uji jalan peramban, data acuan)**: admin di Sukacita, sakelar Asisten Keuangan + golongan B dinyalakan sementara,
  `ai.tindakan_uang_masuk` = ya untuk `ent_ksc` (H5: hanya di data acuan, dipulihkan `restore_demo` sebelum gate). Kartu
  `ar_receipt_create` Rp 5.000.000 untuk Fashion Bandung Kencana / SO-0004 disiapkan lewat `POST /api/ai/tools/prepare_action`.
  Tanya KN › Tindakan: saringan "Menunggu saya · Menunggu orang lain · Selesai · Gagal", kolom
  `Tindakan · PT · Nominal · Dibuat · Berlaku sampai · Status`, "1 kartu"; buka baris → kartu; tombol setujui mati dengan
  kalimat "Tulis alasan (minimal 10 huruf) dan ketik ulang nominal untuk menyetujui."; isi alasan + "5.000.000" → pop-up
  "Jalankan Catat kwitansi piutang sebesar Rp 5.000.000 untuk Sukacita?" → "Ya, jalankan" → **"Berhasil — Kwitansi Pelanggan
  KSC/AR-00008"**, "Jurnal: terposting". Sesuai teks U18. Potret `bukti/AG-T3/u18_*.png`.
- **Cek layar 1280/1024/390** — cacat yang ditemukan dan diperbaiki di `352d8b5`:
  1. Tab Tindakan di **1024 px**: panel utama hanya ±410 px (panel samping 320 px), tabel enam kolom meluap — pil status keluar
     kartu, judul kolom terpotong, kata dipatah ("kwita nsi", "Sukacit a"). Tata letak bertumpuk kini mengikuti lebar panel
     (`@container (max-width: 600px)`), bukan lebar layar; sel Nominal dibungkus agar "Rp" tidak terpisah dari angka.
  2. Kartu: baris rencana "Tanggal kwitansi" tampil ISO mentah "2026-11-15" → kini "15 Nov 2026" (uji komponen ditambah).
  3. Kartu di HP (390 px): judul SEKARANG/SESUDAH saling menimpa → kolom "Hal" 34 % di kartu sempit.
  4. Rincian piutang (1024 px): kolom Nota Denda terpotong → `data-table head-wrap`; nomor pesanan tidak dipatah; "Buat Nota
     Denda" `btn-sm` sejajar "Tanya soal layar ini".
  Sesudah perbaikan: `overflowX = 0` di 1280/1024/390 untuk daftar dan kartu; Tutup Buku 1024 px (tombol "Tanya soal layar
  ini" di bilah kepala) rapi. Potret `bukti/AG-T3/cek_*.png`.
- Catatan: isian "Cara bayar" di kartu menampilkan kode `transfer` (isian teks bebas mengikuti `method` di `/api/ar-receipts`,
  sedangkan rencana menampilkan label "Transfer") — dibiarkan; PM-T3 sedang mengubah `method` kwitansi.

Yang dijalankan di lingkungan B (W, basis `1204bac`):

- `tests_mem`: B **1676 lulus / 2 dilewati / 3 xfail** (diukur 23.53 WIB) → (b) **1701 lulus + 6 merah / 2 / 3** (diukur
  00.42 WIB). Keenam merah = `test_PK36_akun_kontrol` U5b/U6/U7/U8 dan `test_PK10_jurnal_pembalik` U04/U07 "Tanggal pembalik
  tidak boleh sebelum tanggal jurnal asli." — **merah jam** (00.00–07.00 WIB): kode B tanpa unit ini merah sama (7 merah,
  `bukti/AG-T3/merah_jam_kode_B_PK36_PK10.log`). Uji baru +31 (25 + 4 + 2 putaran KF-T8). Log `tests_mem_*.log`.
- Jest penuh: B **108 suite lulus · 870 uji** → W **109 · 884** (+14; 35 suite gagal dimuat `cmdk`/`@radix-ui` = sama).
  Suite yang memuat layar yang disentuh (`pk42LayarKeuangan`, `pk21Rekonsiliasi…`, `kft6JurnalDuaOrang`, `pk11ClosingNotEnded`,
  `pk36AkunKontrol`, `pk16ScopeBanner`, `prt7TombolIzin`, `agt1`/`agt2`/`agt4`) tetap hijau.
- `hitung_penjaga.sh` sama dengan B (auth 27 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 6 ·
  entity_label 2; lainnya 0/PASS); `verify_role_gate_ui` 31/0; `verify_config_fallback` 154/0 (+`--entity` 154/0);
  `verify_payment_vocab` 1791/0; `verify_permission_checked` 593/0; `verify_posting_coverage` 140/0; `verify_cash_single_door`
  714/0; `verify_config_text` 3213/0; `verify_atomic_claim` keluaran identik dengan B; `verify_access_catalog_nav` 0;
  `verify_codebase_map` 0; `audit_config_wiring --strict` hijau; `check_nav_map` PASS; `gen_config_key_index --check` selaras.

## Serah-terima

- **(a)** mesin kartu, middleware, idempotensi, indeks, tujuh tindakan + `ai_card_id`, izin, dua pengaturan, endpoint daftar,
  alat `prepare_action`, tab Tindakan, kartu, "Tanya soal layar ini", sakelar golongan di layar akun; jalur draf PO lama belum
  disentuh (selain menggantikan kartu menunggu, Menyimpang 3). Keadaan disimpan di
  `/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/AG-T3_a_state/` (`BASIS.txt` = `1204bac`) dan
  tergabung di `…/AG-T3_a_merged/` (lihat Penggabungan).
- **(b)** draf PO lewat `POST /api/purchase-orders`; pengingat ke sales tetap `create_notification` (pengecualian tercatat).

## Penggabungan

- HEAD tujuan: **`8eb091b`** (selama unit dikerjakan HEAD maju `1204bac` → `bcb7b85` → `8abfb72` → `f8d80fc` (PK-29, PK-22) →
  `8eb091b`). Worktree tujuan `wt22` berisi (b) tergabung, belum di-commit. Prosedur: per berkas, HEAD = basis → salin W; beda →
  `git merge-file -p <HEAD> <B> <W>`; berkas baru disalin; `CODEBASE_MAP.md`, `configKeyIndex.json`, fixture akses dibangkitkan
  ulang.
- Digabung tiga arah **tanpa bentrok**: `ENTITY_REGISTRY.md`, `backend/access_modules.py`, `backend/indexes.py`,
  `backend/permissions_config.py`, `backend/routers/crm.py`, `tests_mem/test_PRT9_izin_bawaan.py`,
  `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`, `memory/PRD.md` (perubahan PK-22/PK-29 dan AG-T3 berdampingan).
- **Bentrok** (kedua perilaku dipertahankan): `backend/idempotency.py` — PK-22 menutup daftar dengan `"/api/hr/payroll/"`,
  AG-T3 menambah empat awalan sesudahnya (pola `/followups` di `IDEMPOTENT_PATTERNS` tanpa bentrok);
  `tests_mem/test_KFT1_izin_pengaturan.py` — konstanta `PK29_KUNCI`, `PK22_KUNCI`, `AGT3_KUNCI` semua dipertahankan, U04 =
  `… + PK29_KUNCI + PK22_KUNCI + AGT3_KUNCI`. Hitungan lain: PR-T9 dan indeks wajib PK-14 di HEAD = basis (tidak ada tambahan
  unit lain yang perlu dijumlah); `test_fe03_access_catalog --noconftest` 6/6 di T.
- Keadaan **(a)** tergabung: `…/AG-T3_a_merged/` (`BASIS.txt` = `8eb091b`; digabung dan diuji di `f8d80fc` — `8eb091b` tidak
  menyentuh berkas (a) selain peta kode, yang dibangkitkan ulang terhadap `8eb091b`). `tests_mem` (a) tergabung di `f8d80fc`:
  **1741 lulus / 2 / 3** (`bukti/AG-T3/tests_mem_a_tergabung_T.log`).
- Angka di T (`8eb091b` + AG-T3 (b)): `tests_mem` HEAD **1714 / 2 dilewati / 3 xfail** → T **1745 / 2 / 3** (+31: 25 (a) + 4 (b)
  + 2 putaran KF-T8; tanpa merah — merah jam PK-36/PK-10 tidak muncul pada putaran ini); jest HEAD 110 suite · 884 uji → T
  111 · 898 (+14; 35 suite gagal dimuat `cmdk`/`@radix-ui` sama dengan HEAD); `hitung_penjaga.sh` T = HEAD (auth 27 ·
  ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2, lainnya 0/PASS);
  `verify_role_gate_ui` 31/0; `verify_config_fallback` 154 → 155/0 (`--entity` sama); `verify_payment_vocab` 1791 → 1794/0;
  `verify_access_catalog_nav` 0; `verify_permission_checked` 602 → 603/0; `verify_posting_coverage` 138/0;
  `verify_cash_single_door` 714 → 716/0; `verify_config_text` 3213 → 3227/0; `verify_codebase_map` 0;
  `audit_config_wiring --strict` hijau dan `check_nav_map` PASS (keduanya lewat salinan berjalur T). Bukti
  `bukti/AG-T3/tests_mem_{HEAD,T}_8eb091b.log`, `penjaga_{HEAD,T}.txt`, `penjaga_lain_HEAD_T.txt`, `jest_ringkas.txt`.
- Seed data uji (`seed_realistic.py` akar repo dan `backend/seed_realistic.py`): unit ini tidak mengubah syarat pembuatan
  dokumen yang di-seed dan tidak menghapus/mengganti nama fungsi yang dipakai di luar (`ai_actions.confirm`/`_exec_po` hanya
  mendapat parameter opsional) — keduanya tidak perlu diubah (dicek `grep`).

## Hambatan lingkungan

- Lapis A (U5, U13) dan uji jalan peramban (U18) tidak bisa di lingkungan B — dijalankan integrator di lingkungan A (lihat Gate); mode model penyedia sungguhan = H8.
- Uji PK-36/PK-10 merah jam 00.00–07.00 WIB (bukan akibat unit; lihat Gate).

## Temuan di luar lingkup (tidak diperbaiki)

- `GET /api/ar-receipts/deposit?customer_id` tidak mengadu PT pelanggan (saldo deposit pelanggan PT lain terbaca pemegang
  `ar_receipt.view`); kartu kwitansi hanya memakainya untuk pelanggan yang tagihannya ada di PT aktif.
- `GET /api/collection-worklist` / `collection-reminders` tanpa `entity_id` tidak disaring PT aktif.
- Uji PK-36 U5b–U8 dan PK-10 U04/U07/U14 bergantung jam (tanggal UTC vs WIB): merah antara 00.00 dan 07.00 WIB.
- Aturan alat teks bebas → `propose_action` di **mode umum** (catatan AG-T2) tetap terbuka; `prepare_action` tidak ditawarkan
  di mode umum.

## Yang perlu direview

- Urutan `decide` dan pemetaan galat (`door` vs `uncertain`), ulang sekali hanya pada putus koneksi/batas waktu.
- Pola idempotensi `/followups` (Menyimpang 1) dan kartu lama yang ikut menggantikan (Menyimpang 3).
- Indeks wajib `uq_pending_session`: data lama dengan dua kartu `pending` di percakapan yang sama membuat server menolak mulai
  (mode `enforce`) — periksa dengan `finder` sebelum memasang (H6).
- U5/U13 di MongoDB asli; uji jalan tab Tindakan dan kartu di 1280/1024/390 px.
