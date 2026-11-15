# AG-T5 — Asisten: kartu tindakan uang keluar dan jurnal, orang kedua, daftar larangan

- Commit awal: `cd5aa59` (worktree kerja, basis B)        - Commit akhir: (a) `31a8d54`, (b) `7747302`, cek layar `df23cb2`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke HEAD tujuan `84744dc`: lihat "Penggabungan"
- ID ditangani: — (unit fitur; tidak menutup temuan)
- Keputusan: K-02 (akun kontrol ditolak pintu jurnal), K-04 (jurnal manual tunduk `kontrol.jurnal_manual.*` pintunya),
  K-17 (bayar hutang = pemegang izin bayar; `ai_finance.pay` juga Finance), K-44 (orang kedua untuk uang keluar dan
  jurnal bisa diatur, bawaan satu orang), K-45 (Asisten Keuangan mati per akun) · Standar: §1 (P1, P2), §2.1, §2.3, §2.4,
  §3.1 (Z2, Z4, Z6), §3.2, §3.4 (N1–N5), §4 (L1, L4), §6 · Risiko tinggi — dua serah-terima (`00` §8).
- Titik henti **H5**: sakelar per PT `ai.tindakan_uang_keluar` dibiarkan MATI (bawaan `false`); tidak dinyalakan untuk PT
  mana pun di kode/seed (hanya di uji database tiruan dan uji lapis A yang mengembalikannya).
- Prasyarat di basis: AG-T3, PK-05, PK-10, PK-12, PK-20, PK-36, KF-T6.

## Cek ulang "Keadaan sekarang" (di `cd5aa59`; blueprint dibaca di `3132cc4`)

| # | Hasil |
|---|---|
| 1 | Berlaku, bergeser: `pay_vendor_bill` `routers/vendor_bills.py:615` (`vendor_bill.pay`), `pay_contra_bon` `routers/contra_bons.py:348` (`contra_bon.pay`), `create_cash_transaction` `routers/cash.py:153` (`cash.create`), `create_journal` `routers/gl.py:189` (`accounting.create`; KF-T6: 202 usulan bila `kontrol.jurnal_manual` dua orang), `reverse_journal` `routers/gl.py:306` (`accounting.void`) |
| 2 | **Sudah tidak berlaku** (PK-12/PK-05): `/api/vendor-bills/`, `/api/contra-bons/`, `/api/cash-transactions`, `/api/gl/` sudah di `IDEMPOTENT_PREFIXES` (`idempotency.py:28–33`) — dibuktikan U15 |
| 3 | Berlaku: `create_manual_entry` menulis `status: "posted"` (`services/gl_service.py:902`); jalur usulan dua orang KF-T6 (`journal_proposal_service`) juga ada |
| 4 | **Sudah tidak berlaku**: `services/dual_control.py` ada (KF-T6) dan dipakai (`butuh_orang_kedua`, `tolak_bila_pelaku_sama`, `periksa`) |
| 5 | Berlaku: `QUEUES` `services/approval_backlog_service.py:41` |
| 6 | Berlaku, bergeser: closing `close` `closing.py:103`, `reopen` `:134`, `reclose` `:186`; `period_unlocks.py:73`; `gl.py:74` (akun); `gl_mappings.py:63`; `gl.py:354/435/484` (sync, saldo awal persediaan, reklas suspense); `crm.py:119/174`; `payment_plans.py:280/294`; `consolidation.py:64` (+ `/api/consolidation/sync-g6` `:126`); `users.py:139`, `access_roles.py:135` (prefix `/api/access`); `config.py:338` (prefix `/api/config`); `ai_assist.py`; `master_governance.py:145` (DELETE purge). **Baru sejak blueprint**: CR-T1 `credit_profiles.py:75/127/138` (pengajuan/putusan profil kredit) — masuk pola L6 (Menyimpang 2) |

## Fitur — serah-terima (a): daftar larangan, tiga tindakan uang, orang kedua

- Berlaku di HEAD: belum ada (uji (a) merah di kode lama: peran uji ber-`ai_finance.pay/approve` ditolak "Aksi ['pay',
  'approve'] tidak berlaku untuk “Asisten Keuangan”", `services.ai_card_rules` tidak ada — `bukti/AG-T5/a_merah_kode_lama.log`).
- Perubahan perilaku (sebelum → sesudah):
  - **`backend/services/ai_card_rules.py`** (baru): `FORBIDDEN` 13 baris (kode, pola, metode `None` = semua metode tulis /
    `"*"` = semua metode / `"DELETE"`, alasan) persis tabel spesifikasi (L6 diperluas, Menyimpang 2); `forbidden_rule`,
    `forbidden_reason`, `check_write_paths` (penegakan 2), `ACTION_HINTS` + `reason_for_action` (penegakan 3).
  - **Penegakan 1** `SelfApi.call` mode tulis: larangan diperiksa PALING AWAL (sebelum aturan jalur `/api/ai`, `/api/auth`
    dan daftar pintu terdaftar) → 403 alasan baris, aplikasi tidak dipanggil. (a): hanya `card_class="C"`; (b): semua tulisan.
  - **Penegakan 2**: `ai_cards` memanggil `check_write_paths` saat dimuat (REGISTRY + draf PO lama): terlarang atau tanpa
    idempotensi → `RuntimeError` (pemuatan gagal).
  - **Penegakan 3**: `prepare` untuk kode tak terdaftar → alasan baris yang cocok (isian `path`/`method`, atau kata pada kode:
    `period_close` → L1, `user_delete` → L9, `credit_limit_raise` → L6), selain itu pesan baku AG-T3.
  - **Tiga tindakan golongan C** di `REGISTRY` (`high`, alasan ≥ 10 huruf + ketik ulang nominal):
    `vendor_bill_pay` (`POST /api/vendor-bills/{bill_id}/pay`; baris "Sisa hutang {nomor}"; nominal > sisa → 400 karena kartu
    tidak memutus selisih bayar; sidik `GET /api/vendor-bills/{id}` `status` + `financials`), `contra_bon_pay`
    (`POST /api/contra-bons/{cb_id}/pay`; "Sisa kontrabon {nomor}"; sidik `status` + `totals`), `cash_manual`
    (`POST /api/cash-transactions`; arah keluar/masuk, "Saldo {rekening}"; sidik rekening `is_active/entity_id/cash_type` dari
    `GET /api/bank-accounts`). Rekening sumber bayar dibaca dari `GET /api/ap-payments/accounts` (rekening aktif PT dokumen =
    PT kartu); rekening kas manual dari `GET /api/bank-accounts` (PT aktif). Izin pintu (`door`) dicatat per tindakan.
  - **Sakelar golongan C** (`_sakelar_c`, di `prepare` dan `decide`): `ai_finance.pay` (403 Z6 `MSG_IZIN_C_PAY`) → `C` di
    `users.ai_finance.classes` (403 "Tindakan uang keluar dan jurnal lewat asisten belum dinyalakan untuk akun Anda.") →
    `ai.tindakan_uang_keluar` PT kartu (409 "…untuk {nama PT}.").
  - **Orang kedua** di `decide` (sesudah konfirmasi & batas harian, sebelum klaim): `butuh_orang_kedua("asisten_uang_keluar",
    PT, plan.amount)`; tidak butuh → klaim & dijalankan (potret `second_required {needed: false}`, `first_by` = pembuat);
    butuh → atomik `pending → awaiting_second` + `first_by/first_at` + `second_required {needed, basis}` (D3) + `expires_at`
    dihitung ulang dari saat itu; notifikasi `ai_card_second` satu per penerima (pemegang `ai_finance.approve`, bertugas di PT
    kartu, golongan `C` menyala, bukan pembuat; alamat per orang lewat `notification_audience`). Tidak ada tulisan ke pintu.
  - **`POST /api/ai/actions/{id}/second`** `{decision: approve|reject, reason}` (`routers/ai_assist.py` → `ai_cards.second`):
    `require_permission(ai_finance.approve)` (pesan Z6) → `C` di akun → kartu → PT kartu ∉ akses 403 / ≠ PT aktif 409 →
    status (kedaluwarsa 409 "…kedaluwarsa…", lainnya 409 "Kartu ini tidak sedang menunggu orang kedua.") → sakelar PT (409) →
    `tolak_bila_pelaku_sama(…, pengaju=[first_by.id])` (pesan baku KF-T6) → izin PINTU orang kedua (403 `denied`, kartu tetap
    menunggu) → tolak (alasan ≥ 10 huruf wajib → `dismissed` + `second_by/second_at/second_reason`) | setujui (klaim atomik
    `awaiting_second → running` bersyarat `expires_at > sekarang`, sidik dibaca ulang dengan sesi orang kedua, SATU tulisan
    `SelfApi.from_request`-setara sesi orang kedua, `Idempotency-Key` = id kartu). Langkah 7–9 AG-T3 dipisah ke `_jalankan`.
  - `ai_card_context`: kartu `running` diakui bila `executor_id` = pengguna sesi (pembuat atau orang kedua; kartu lama tanpa
    field: pembuatnya) → dokumen hasil orang kedua tetap ber-`ai_card_id`.
  - `ai_card_id` ditulis: `ap_payment_service` (niat bayar, kas, `vendor_bills.payments[]`, `contra_bons.payments[]`),
    `routers/cash.py` (kas manual).
  - Kedaluwarsa `awaiting_second` (`ai_actions._segarkan`, daftar kotak). Pembuat boleh menarik kartu `awaiting_second`
    (`dismiss`, Menyimpang 6).
  - `GET /api/ai/actions?box=others` = kartu `awaiting_second` di PT aktif (semua bagi yang boleh menjadi orang kedua; milik
    sendiri bagi pembuat); kotak Selesai/Gagal juga memuat kartu yang dijalankan pengguna sebagai orang kedua.
    `GET /api/ai/actions/{id}`: orang kedua (izin `ai_finance.approve`, PT kartu dalam akses) bisa membuka kartu orang lain yang
    menunggu / yang ia putus; kartu C dihias `second_preview`, `is_maker`, `can_second`, `second_block` (alasan tertulis).
  - Alat model `prepare_action`: tiga kode + isian baru (`tools_kn_tindakan_v1.json`); instruksi keuangan butir 7.
- Izin & pengaturan: `ai_finance.pay` (admin, manager, finance) dan `ai_finance.approve` (admin, manager) di empat tempat
  (`permissions_config.AGT5_DEFAULT_PAIRS`, `access_modules.ACTION_LABEL` "Tindakan uang keluar" / "Menyetujui sebagai orang
  kedua", pemeriksa `ai_cards._sakelar_c` / router `second`, uji Tanpa Acuan & Manajer Kosong). Sakelar akun `classes` menerima
  `C` (`routers/users.py`). `ai.tindakan_uang_keluar` (bool, mati, global+PT, `high`+alasan, `ai.configure`, consumer
  `services/ai_cards.py:_sakelar_c`). `KONTROL_AKSI` + `asisten_uang_keluar` ("Tindakan uang keluar dan jurnal lewat asisten",
  awal "1", bernominal, bagian Buku besar; titik `ai_cards.py:decide` & `:second`; label Pengaturan pendek "Kartu asisten uang
  keluar: …"; contoh dari spesifikasi) → `kontrol.asisten_uang_keluar.min_orang` / `.batas_nominal`.
- Layar: kartu (`TanyaActionCard.jsx`): "Kartu ini akan menunggu persetujuan orang kedua sebelum dijalankan." di bawah tombol
  bila berlaku; status "Menunggu orang kedua" (ikon + teks + warna); "Menunggu orang kedua · disetujui {pembuat}, {tanggal
  jam} WIB"; panel orang kedua (alasan pembuat, isian Alasan wajib saat menolak, "Setujui dan jalankan" → pop-up "Jalankan
  {label} sebesar Rp {nominal} untuk {PT} atas permintaan {pembuat}?" "Ya, jalankan"/"Batal", "Tolak"), alasan tertulis bila
  tidak bisa memutus, pembuat bisa "Abaikan". Tab Tindakan: kolom "Berlaku sampai" untuk kartu menunggu; `initialBox`. Akun &
  Akses: tiga pilihan "Baca saja · Uang masuk · Uang masuk, uang keluar, dan jurnal".
- Status: implemented_pending_review

## Pengalihan — serah-terima (b): dua tindakan jurnal, antrean, larangan untuk semua tulisan

- `journal_manual` (`POST /api/gl/journal`, izin pintu `accounting.create`): `prepare` menghitung total debit & kredit (sen
  bulat) dan menolak "Jurnal tidak seimbang: debit 100.000 ≠ kredit 90.000."; akun TIDAK dipilih (dari permintaan; nama akun
  hanya untuk tampilan dari `GET /api/gl/accounts` bila terbaca); `confirm_text` = total debit; tanpa sidik (pintu memeriksa
  periode & akun). Pintu menjawab 202 usulan (KF-T6) → kartu `confirmed`, `result.message` "Usulan jurnal menunggu persetujuan
  di layar Jurnal", `result.document` usulan. Akun kontrol → 422 pintu → `failed`/`door` (U13).
- `journal_reverse` (`POST /api/gl/journal/{entry_id}/reverse`, izin pintu `accounting.void`): ketik ulang NOMOR jurnal
  (`retype_kind: "text"`, huruf besar/kecil & spasi diabaikan, pesan "Ketik ulang nomor jurnal persis seperti di kartu."),
  sidik `status/reversed/reversed_by_entry_id/total_debit`, jurnal void / sudah dibalik ditolak saat disiapkan.
- Izin `ai_finance.post` ("Tindakan jurnal", admin & manager) — `_sakelar_c` memilih `pay`/`post` menurut tindakan.
- `ai_card_id` di `journal_entries` (`gl_service._insert_entry` dan `create_manual_entry`) dan `journal_proposals`.
- Antrean `("ai_card_second", "Tindakan asisten menunggu orang kedua", "tanya-kn", "ai_action_proposals", {"status":
  "awaiting_second"})` + `AGING_META` + jenis `approval_kinds.ai_card_second` (INV-APPR-01 G) + pasangan
  `verify_home_kpi.EXPECT` (INV-HOME-01) + `QUEUE_PRESETS` (baris backlog & "terlama" membawa `preset {tab: actions, box:
  others}`); Pusat Persetujuan meneruskan preset → Tanya KN membuka tab Tindakan › Menunggu orang lain (`useViewPreset`).
- `SelfApi`: larangan diperiksa untuk SEMUA panggilan mode tulis (golongan A, B, C, tanpa golongan, draf PO lama). Uji AG-T3,
  AG-T1 tetap hijau.
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_AGT5_kartu_uang_keluar.py` (18 uji, a), `test_AGT5_jurnal_dan_antrean.py` (7 uji, b), lapis A
`backend/tests/test_bp_AGT5_orang_kedua_bersamaan.py` (U9 — ditulis), jest `features/__tests__/agt5KartuUangKeluar.test.js`
(8, a) dan `agt5JurnalDanAntrean.test.js` (3, b).

| ID | Lapis | Merah di kode lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | ya (izin `ai_finance.pay/approve` tidak dikenal) | Lulus — `pending`, C/`high`; "Sisa hutang VB-…" 7.000.000 → 0; `confirm_text` "7000000"; kas 0 |
| U2 | B | ya (idem) | Lulus — `confirmed`; satu kas keluar 7.000.000 ber-`ai_card_id`; tagihan `paid` 7.000.000, `payments[].ai_card_id`, niat bayar ber-`ai_card_id`; jurnal Dr 2-1100 / Cr 1-1100 7.000.000; satu `idempotency_keys` |
| U3 | B | ya (idem) | Lulus — `awaiting_second` (`basis` min_orang, `expires_at` ≥ +23 j); kas 0; notifikasi untuk `mgr`, tidak untuk `fin`/`fin2`. Hitungan antrean → U3 (b) |
| U3 (antrean) | B | ya (keadaan a: baris tidak ada) | Lulus — baris `ai_card_second` persis teks spesifikasi; hitungan +1; preset ikut di baris & daftar terlama; `GET /api/approvals/backlog` |
| U4 | B | ya (idem) | Lulus — 403 "Tindakan uang keluar dan jurnal lewat asisten harus diputuskan orang lain: Anda yang mengajukannya. …"; status tetap |
| U5 | B | ya (idem) | Lulus — 403 Z6 (tanpa kode izin); status tetap |
| U6 | B | ya (idem) | Lulus — `confirmed`; tepat satu kas, `created_by` = orang kedua; `first_by` fin, `second_by` mgr, `second_reason`; ulang → 409 "Kartu ini tidak sedang menunggu orang kedua." |
| U7 | B | ya (idem) | Lulus — 7.000.000 → `awaiting_second` (`basis` batas_nominal); 4.000.000 → `confirmed` |
| U8 | B | ya (idem) | Lulus — kartu 7.000.000 PT Kanda (sakelar Kanda menyala sementara) `confirmed` langsung, kas Kanda ber-`ai_card_id` |
| U9 | A | — | **Ditulis, belum dijalankan** (`test_bp_AGT5_orang_kedua_bersamaan.py`: Finance pembuat, Manajer & Admin bersamaan → [200, 409], satu kas) |
| U10 | B | ya (idem) | Lulus — 409 "…kedaluwarsa…"; `expired`; kas 0 |
| U11 | B | ya (idem) | Lulus — bayar layar 3.000.000 → `failed`/`stale`; satu kas 3.000.000 tanpa `ai_card_id` |
| U12 | B | ya (keadaan a: kode tak dikenal) | Lulus — 400 "Jurnal tidak seimbang: debit 100.000 ≠ kredit 90.000."; seimbang → `pending`, `confirm_text` "100000"; disetujui → satu jurnal manual ber-`ai_card_id`, saldo 1-1100 & 3-1000 +100.000 |
| U13 | B | ya (idem) | Lulus — `failed`/`door`, pesan = 422 PK-36 pintu (diadu langsung), jumlah jurnal tetap |
| U14 | B | ya (modul tidak ada) | Lulus — 13/13 alasan baris, aplikasi tidak dipanggil (a: `card_class="C"`; b: tanpa golongan, A, B) |
| U15 | B | ya (idem) | Lulus — semua `write_path` (+ draf PO) tidak terlarang & ber-idempotensi (tindak lanjut lewat pola AG-T3); `check_write_paths` gagal untuk path terlarang/tanpa idempotensi |
| U16 | B | ya (idem) | Lulus — `period_close` → L1, `user_delete` → L9; kartu 0; `credit_limit_raise` → L6; kode lain pesan baku |
| U17 | B | ya (idem) | Lulus — `get_document` tagihan bercatatan perintah → `prepare_action` "Alat tindakan tidak tersedia pada giliran ini."; kartu 0, kas 0 |
| U18 | B | ya (idem) | Lulus — orang kedua PT Kanda: 403 `MSG_TANPA_AKSES_PT` / 403 penjaga PT; sakelar KSC mati → 409 pesan PT saat disiapkan dan saat orang kedua memutus (kartu tetap menunggu) |
| (+) kontrabon, kas manual | B | ya | Lulus — kontrabon 5.000.000 (2 faktur) lunas, kas & `payments[]` ber-`ai_card_id`; kas manual 250.000 `manual`/`out`; rekening dinonaktifkan sesudah disiapkan → `stale`; rekening PT lain 400 |
| (+) izin/sakelar/tolak/kotak | B | ya | Lulus — tanpa `ai_finance.pay` 403 Z6; Manajer Kosong 403; akun tanpa `C` 403; `classes: ["X"]` 400; lebih dari sisa hutang 400; orang kedua tanpa `vendor_bill.pay` 403 "Anda belum punya akses untuk membayar …", kartu tetap; kotak `others` (mgr & pembuat ya, fin2 tidak); `can_second`/`second_block`; tolak tanpa alasan 400, dengan alasan `dismissed`; kartu `pending` → 409 |
| (+) balik jurnal, izin post | B | ya (keadaan a) | Lulus — ketik ulang "JE-00001" 400, nomor huruf kecil 200; pembalik ber-`ai_card_id`, jurnal asal bertanda; dibalik lagi 409; tanpa `ai_finance.post` 403 Z6, Tanpa Acuan ber-`post` 200, Manajer Kosong 403 |
| Layar | jest | ya (`bukti/AG-T5/a_jest_merah_kode_lama.log` 7/8; `b_jest_merah_keadaan_a.log` 3/3) | Lulus 11/11 (`a_jest_hijau.log`, `b_jest_hijau.log`). **Uji jalan peramban belum dilakukan** (pop-up Pusat Persetujuan → kartu U3: integrator) |

Fixture vs alur: rekening, tagihan pemasok (+ jurnal hutang), kontrabon, geser `expires_at`, catatan bersisipan perintah,
rekening dinonaktifkan = FIXTURE; peran, sakelar akun, pengaturan PT & kontrol dua orang, kartu, persetujuan, orang kedua,
bayar layar, jurnal yang dibalik (dibuat lewat kartu), percakapan = ALUR API.

## Contoh angka (`00` §9) — `bukti/AG-T5/contoh_angka.log`

- **U2** kartu `vendor_bill_pay` VB-AGT5-1 Rp 7.000.000 → kas keluar `KSC/CASH-00005` 7.000.000 (rekening BCA KSC) → jurnal
  `KSC/JE-00006`: **Dr 2-1100 Hutang Usaha 7.000.000 · Cr 1-1100 Kas Besar / Bank 7.000.000** → saldo 2-1100 (normal kredit)
  7.000.000 → 0; sisa hutang tagihan 7.000.000 − 7.000.000 = 0. Hitung tangan: D = K = 7.000.000; hutang berkurang sebesar kas.
- **U12** kartu `journal_manual` → `KSC/JE-00005`: **Dr 1-1100 100.000 · Cr 3-1000 Modal Disetor 100.000**; saldo 1-1100
  100.000.000 → 100.100.000, 3-1000 100.000.000 → 100.100.000 (+100.000 masing-masing menurut saldo normalnya).

## Uji lama yang disesuaikan (angka/contoh, bukan harapan dilonggarkan)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` | `AGT5_KUNCI = 3` (U04), `AGT5_KUNCI_KONTROL = 2` (U02) | tiga kunci baru (`ai.tindakan_uang_keluar` berizin `ai.configure`; dua `kontrol.asisten_uang_keluar.*` berizin `settings.manage`) |
| `tests_mem/test_KFT6_kontrol.py` | `N_AKSI` 39 → 40, `N_KUNCI` 64 → 66, `BERNOMINAL` + `asisten_uang_keluar` | aksi kontrol dua orang baru (spesifikasi) |
| `tests_mem/test_PRT9_izin_bawaan.py` | `TAMBAHAN_SESUDAH` + `AGT5_DEFAULT_PAIRS` | izin bawaan baru `ai_finance.pay/post/approve` |
| `tests_mem/test_KPT4a_setara.py::test_KPT4_U1` | jumlah antrean 39 → 40 | baris antrean baru `ai_card_second` (spesifikasi); jenis `approval_kinds.ai_card_second` ikut tercakup baris bawaan |
| `tests_mem/test_AGT3_kartu_tindakan.py::test_AGT3_pintu_tulis_hanya_jalur_terdaftar` | contoh jalur tak terdaftar `/api/gl/journal`, `/api/cash-transactions` → `/api/cash-advances`, `/api/finance-cases` | kedua jalur itu kini pintu kartu golongan C yang SAH; harapan uji (tak terdaftar → 403 tanpa memanggil aplikasi) tetap |
| `access_builtin_fixture.json`, `configKeyIndex.json`, `CODEBASE_MAP.md` | dibangkitkan ulang | izin & kunci baru, berkas baru (`test_fe03_access_catalog --noconftest` 6/6) |

## Berkas berubah

Server (baru): `backend/services/ai_card_rules.py`. Server (ubah): `services/ai_cards.py`, `services/ai_self_api.py`,
`services/ai_actions.py`, `ai_card_context.py`, `routers/ai_assist.py`, `routers/users.py`, `routers/cash.py`,
`services/ap_payment_service.py`, `permissions_config.py`, `access_modules.py`, `config_catalog_ai.py`,
`config_catalog_kontrol.py`, `data/ai/tools_kn_tindakan_v1.json`, `data/ai/system_prompt_kn_keuangan_v1.md`; (b) +
`services/gl_service.py`, `services/journal_proposal_service.py`, `services/approval_backlog_service.py`,
`approval_kinds.py`, `scripts/guardrails/verify_home_kpi.py` (pasangan EXPECT, statik). Layar: `features/tanya/
TanyaActionCard.jsx`, `TanyaActions.jsx`, `tanyaApi.js`, `tanya.css`, `features/settings/entities/AccountFormDrawer.jsx`; (b)
+ `features/tanya/TanyaKnView.jsx`, `features/approvals/ApprovalInbox.jsx`, `AppViewRouter.jsx`. Uji: dua `tests_mem/
test_AGT5_*`, `tests/test_bp_AGT5_orang_kedua_bersamaan.py`, dua jest `agt5*`, lima uji lama di atas. Dokumen:
`ENTITY_REGISTRY.md` (field kartu, `ai_card_id` di `cash_transactions`, `journal_entries`, niat bayar, `payments[]`,
`users.ai_finance.classes` C), `CODEBASE_MAP.md` (generator), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`
§9.18 di W / §9.20 di T + baris tab Tindakan §9.8.

## Menyimpang dari blueprint

1. **Label `ai.tindakan_uang_keluar`** "Izinkan asisten untuk uang keluar dan jurnal" (spesifikasi: "Izinkan asisten
   menyiapkan uang keluar dan jurnal" = 49 huruf > 45, `02` §2.1 / INV-CFG-TXT). `consumers` = `services/ai_cards.py:_sakelar_c`
   (fungsi yang benar-benar membaca; dipanggil `prepare` dan `decide`), pola AG-T3 `_sakelar_b`.
2. **L6 diperluas ke CR-T1** (`customers/{id}/credit-profile-requests`, `credit-profile-requests/…`): CR-T1 sudah di basis dan
   spesifikasi meminta "menambah profil kredit (CR-T1) … berarti menambah baris di sini"; kategori & alasan sama dengan L6,
   jadi pola baris L6 yang diperluas (tetap 13 baris, U14 tetap 13/13). Usulan teks pengganti kolom pola L6:
   `^/api/(customers/[^/]+/(credit-override|credit-profile-requests)|credit-overrides/|credit-profile-requests/)`.
3. **Metode L11 "semua"** ditulis `"*"` (tipe spesifikasi `str | None`; `None` sudah berarti "semua metode tulis").
4. **Sidik kas manual** dari `GET /api/bank-accounts` (spesifikasi: `/api/bank-accounts/position`, yang hanya berisi saldo
   buku besar, tanpa status rekening). **Rekening sumber bayar** dari `GET /api/ap-payments/accounts` (pintu layar bayar,
   izin bayar yang sama, rekening aktif PT dokumen) — bukan `/api/bank-accounts` (butuh `cash.view` yang tidak dituntut pintu
   bayar). Keduanya tetap "rekening milik PT kartu".
5. **Notifikasi orang kedua** hanya untuk pemegang `ai_finance.approve` yang juga bergolongan `C` (spesifikasi: izin + akses PT
   + bukan pembuat) — yang tanpa `C` tetap ditolak endpoint `second`; hasil U3 sama.
6. **Pembuat boleh menarik kartu `awaiting_second`** ("Abaikan" → `dismissed`): transisi `awaiting_second → dismissed` di
   spesifikasi hanya menyebut penolakan orang kedua; tanpa ini kartu yang keliru menggantung sampai kedaluwarsa.
7. **Kotak "Menunggu orang lain"** juga memuat kartu `awaiting_second` milik pembuat sendiri (tanpa tombol putus; spesifikasi
   hanya menyebut "yang boleh diputus pengguna") — tanpa itu kartu pembuat hilang dari semua kotak. Kotak Selesai/Gagal memuat
   kartu yang dijalankan pengguna sebagai orang kedua.
8. **Hitungan antrean U3** diuji di serah-terima (b) (baris `QUEUES` termasuk (b) menurut "Langkah kerja"); U3 (a) menguji
   sisanya. Jenis `approval_kinds.ai_card_second` ditambahkan karena INV-APPR-01 G menuntut tiap kunci `QUEUES` punya jenis.
9. **Preset Pusat Persetujuan**: baris backlog/terlama `ai_card_second` membawa `preset` (`QUEUE_PRESETS`), diteruskan
   `ApprovalInbox` → `onNavSelect(..., {preset})` → `TanyaKnView` (`useViewPreset`). Baris lain tidak berubah bentuk.
10. **Jejak & isian tambahan**: `executor_id`, `retype_kind`, `second_preview/is_maker/can_second/second_block` (dihias saat
    dibaca, tidak disimpan), audit `ai_card_awaiting_second`, `ai_card_second_approved`, `ai_card_second_rejected`.
11. **`ai_card_id` di jurnal** dipasang di `_insert_entry` (semua jurnal yang lahir di permintaan kartu `running`, termasuk jurnal
    kas bayar hutang) dan `create_manual_entry`; usulan jurnal KF-T6 juga ber-`ai_card_id`.

## Asumsi

- Spesifikasi: orang kedua menjalankan pintu dengan sesinya sendiri (wajib izin pintu); jurnal lewat asisten memakai kunci
  `kontrol.asisten_uang_keluar.*` yang sama; `ai_finance.post`/`approve` bawaan admin & manager, `pay` juga finance (K-17).
- Orang kedua memutus menurut aturan **saat diputus** (`tolak_bila_pelaku_sama` membaca pengaturan terkini); potret saat pembuat
  menyetujui disimpan `second_required` (D3). Bila PT menurunkan aturan ke satu orang sementara kartu menunggu, pembuat tidak
  lagi ditolak di `second` (perilaku pembantu KF-T6, sama dengan amandemen).
- Sakelar PT `ai.tindakan_uang_keluar` diperiksa ulang saat orang kedua menyetujui (H5: mematikan sakelar menahan semua kartu).
- Kartu tidak memutus selisih bayar pemasok (nominal > sisa hutang ditolak saat disiapkan); kas manual boleh arah masuk
  ("setoran") maupun keluar.
- Batas teknis (konstanta): pesan "minimal 10 huruf" alasan menolak = `REASON_MIN` AG-T3; alasan pembalikan ≥ 5 (aturan pintu).

## Cek layar (KN_37 + KN_08 + UX_USABILITY) — dari kode; integrator memotret 1280/1024/390

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati beralasan | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/angka 0 |
|---|---|---|---|---|---|---|---|---|
| Kartu tindakan golongan C (percakapan & pop-up tab Tindakan) | Tabel Rencana 3 kolom yang sama (`head-wrap`, `table-layout: fixed`); tidak ada kolom baru | `.tanya-action` berbantalan; panel orang kedua `.tanya-card-second` (kolom flex, jarak `--sp-2`) | Kepala tetap judul + pil; "Menunggu orang kedua · disetujui …" di baris meta sendiri; alasan pembuat, isian, bilah tombol masing-masing baris sendiri | "Tolak" mati → "Tulis alasan (minimal 10 huruf) untuk menolak." tertulis di sampingnya; "Setujui dan jalankan" pembuat mati → kalimat AG-T3 (+ "nomor jurnal" untuk balik jurnal); tanpa wewenang: tombol tidak tampil, `second_block` tertulis | Pil "Menunggu orang kedua" ikon `UserCheck` + teks + token `kn-warning` (`docStatusLabel`) | — (satu kartu) | Pesan izin dari server (Z6); pembuat: "Kartu ini dijalankan sesudah orang lain yang berwenang menyetujuinya." (tidak menyebut "bukan wewenang") | Rupiah utuh `kpiValueParts`/`formatCurrency`; tanggal "14 Nov 2026, 10.15 WIB"; nilai kosong "—" |
| Tanya KN › Tindakan | Enam kolom tetap; "Berlaku sampai" terisi untuk kartu menunggu | tidak berubah | tidak berubah | tidak berubah | kolom Status = pil | saringan empat kotak + halaman (tetap) | — | keadaan memuat/galat/kosong tidak berubah |
| Pusat Persetujuan | Tidak ada tabel baru — satu chip antrean dari server ("Tindakan asisten menunggu orang kedua" + jumlah) dan baris "menunggu di layar lain" | tidak berubah | tidak berubah | chip mati bila layar bukan wilayah peran (perilaku lama, `title`) | — | — | label dari server | angka 0 tidak tampil (chip hanya bila > 0, perilaku lama) |
| Akun & Akses › Asisten keuangan | — | di dalam `form-subsection` | `legend` "Kartu tindakan yang boleh disetujui" + tiga pilihan radio, bantuan di baris sendiri | `fieldset disabled` tanpa `ai.configure` + kalimat hanya-baca yang sudah ada | teks pilihan | — | menyebut akses 'Siapkan dan setujui tindakan', 'Tindakan uang keluar', 'Tindakan jurnal' + pengaturan PT | — |
| Huruf & warna | token `--fs-12/13`, warna `kn-*`, tombol `primary-button`/`secondary-button btn-sm` `white-space: nowrap`; tanpa hex baru | | | | | | | |

**Uji jalan peramban belum dilakukan** (lingkungan B tanpa backend/peramban).

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`38c715f`** — satu gate
untuk rantai gelombang 4 (PY-T2, TX-T2 (a/b) + cek layar, AG-T5 (a/b) + cek layar, CR-T2 (a/b), PM-T4):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`b62ef45`: 12 / 39) — tidak ada gate baru yang merah. "Tidak dijalankan" tambahan = ganti label
(`guard:atomic_claim SELF-TEST` 10 → 64 kasus, `guard:page_tabs` + uji-dirinya). Kuitansi: `bukti/AG-T5/gate_quick_receipt.md`,
`gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- Rantai gelombang 4 dipasang integrator berurutan di atas `8ac7059`: PY-T2 `5edef21` · `82ef1bb` → TX-T2 (a) `38b5c9b` · (b) `84744dc` · cek layar `15d3258` → AG-T5 (a) `31a8d54` · (b) `7747302` · cek layar `df23cb2` → CR-T2 (a) `2d9709e` · (b) `76a337d` → PM-T4 `38c715f`. Tiap commit diuji `tests_mem` penuh di worktree bantu sebelum dipetik (angka di bawah). Jest penuh di `38c715f`: **995 lulus** (957 + PY-T2 8 + TX-T2 7 + AG-T5 11 + CR-T2 5 + PM-T4 7; 35 suite gagal dimuat `cmdk`/`@radix-ui`, sama). Penjaga statik di `38c715f` = garis dasar kecuali `verify_auth_coverage` 27 → **26** (AG-T5); `verify_atomic_claim` 161/0, `verify_posting_coverage` 138/0, `verify_cash_single_door` 736/0, `verify_role_gate_ui` 31/0, `verify_detail_modal` 30/0. Glosarium KN_32: §9.18 PY-T2 · §9.19 TX-T2 · §9.20 AG-T5 · §9.21 CR-T2 · §9.22 PM-T4 (nomor pelaksana dirapikan integrator). Indeks wajib lapis A: 29 + PY-T2 2 + CR-T2 2 + PM-T4 1 = **34** (`check_required_indexes` 34/34 di data acuan).
- Dipasang di atas TX-T2 (`15d3258`) tanpa bentrok baru (pelaksana sudah menggabung ke `84744dc`; satu-satunya
  perubahan HEAD sesudahnya hanya layar pajak): (a) **`31a8d54`** `tests_mem` **1993/2/2**; (b) **`7747302`**
  **2000/2/2**, 0 gagal. `hitung_penjaga`: auth 27 → **26**, lainnya garis dasar.
- Lingkungan A: lapis A **U9 lulus** (Manajer dan Admin menyetujui sebagai orang kedua bersamaan → satu 200 + satu 409,
  tepat satu kas keluar ber-`ai_card_id`); lapis A AG-T3 (kartu bersamaan) tetap lulus. **H5: `ai.tindakan_uang_keluar`
  tetap mati di kode/seed**; untuk uji jalan dinyalakan sementara di database uji lokal saja.
- Uji jalan **U18** (kartu "Bayar tagihan pemasok" Rp 7.000.000 disiapkan Finance, disetujui pembuat → menunggu orang
  kedua): **cacat ditemukan dan diperbaiki (`df23cb2`)** — Tanya KN › Tindakan di 1280 px: panel utama ±650 px, tabel
  enam kolom `table-layout: fixed` → pil "Menunggu orang kedua" (±170 px, tidak boleh patah) meluber dari kolom ±108 px,
  tabel 727 px, halaman bergeser 40 px. Ambang kartu bertumpuk berlabel dinaikkan 600 → 740 px lebar panel. Sesudahnya
  1280/1024/390: tabel = lebar panel, `overflowX` 0. Pop-up kartu untuk orang kedua (rencana, "Menunggu orang kedua ·
  disetujui {nama}", alasan pembuat, Setujui dan jalankan; Tolak mati dengan alasan tertulis) rapi
  (`bukti/AG-T5/cek_*.png`). Sesuai spesifikasi (baris 96/167) kartu yang menunggu orang kedua tampil di kotak "Menunggu
  orang lain", juga bagi orang kedua. Pilihan golongan ketiga di Akun & Akses (menu pilihan yang sudah ada) dicakup jest,
  tidak dipotret.

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A dipakai integrator). Lapis A U9 ditulis, belum dijalankan.

Yang dijalankan di lingkungan B (W, basis `cd5aa59`):

- `tests_mem`: B **1924 lulus / 2 dilewati / 2 xfail** → (a) **1945 / 2 / 2** → (b) **1951 lulus + 1 merah / 2 / 2** (merah = `test_KPT4a_setara::test_KPT4_U1` hitungan antrean 39, kini 40 karena baris `ai_card_second` — disesuaikan, berkas itu lalu 5/5; uji penuh sesudahnya di T, lihat Penggabungan). Log `bukti/AG-T5/tests_mem_*.log`.
- Jest penuh: B **119 suite lulus · 957 uji** → (a) **120 · 965** → (b) **121 · 968** (35 suite gagal dimuat `cmdk`/`@radix-ui`
  = kendala lingkungan, sama dengan B).
- `hitung_penjaga.sh`: B auth 27 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 5 · entity_label 2
  (lainnya 0/PASS) → (a)/(b) **auth 26** (turun: `GET /api/ai/actions/{pid}` kini memanggil `entity_ctx`), lainnya sama.
  `verify_role_gate_ui` 31/0; `verify_atomic_claim` 160/0 + uji-diri 64/0 (endpoint `…/second` tidak terdeteksi menulis ≥ 2
  koleksi: satu koleksi langsung lewat `ai_cards.second`; notifikasi orang kedua lahir di jalur `…/confirm` dua tingkat
  layanan — pola CAS `pending → awaiting_second` sebelum notifikasi, notifikasi ber-`ref` per penerima);
  `verify_permission_checked` 606 → 608 (a) → 609 (b) /0; `verify_config_fallback` 157/0 (`--entity` 157/0);
  `verify_config_text` 3276 → 3297/0; `verify_posting_coverage` 133/0; `verify_cash_single_door` 728 → 729/0;
  `verify_detail_modal` 30/0; `verify_payment_vocab` 1814 → 1815/0; `verify_access_catalog_nav` 0; `audit_config_wiring
  --strict` hijau; `check_nav_map` PASS.

## Serah-terima

- **(a)** daftar larangan + penegakan 1 (golongan C) / 2 / 3, tiga tindakan uang, izin `pay`/`approve`, sakelar akun `C`,
  `ai.tindakan_uang_keluar`, kontrol `asisten_uang_keluar`, alur & endpoint orang kedua, notifikasi, layar kartu/tab/akun.
  Disimpan di `/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/AG-T5_a_state/` (`files/`,
  `FILES.txt` 33 berkas, `BASIS.txt` = `cd5aa59`) dan tergabung di `…/AG-T5_a_merged/` (`BASIS.txt` = `84744dc`).
- **(b)** dua tindakan jurnal + izin `post`, `ai_card_id` jurnal, baris Pusat Persetujuan (+ jenis, AGING_META, EXPECT KPI,
  preset), larangan untuk semua tulisan `SelfApi`.

## Penggabungan

- HEAD tujuan: **`84744dc`** (selama unit dikerjakan HEAD maju `cd5aa59` → `5f193df` (STATUS + laporan) → `5edef21` (PY-T2)
  → `82ef1bb` (PY-T2, satu berkas layar HR) → `8ac7059`/`38b5c9b`/`84744dc` (STATUS, TX-T2 (a)/(b))). Worktree tujuan `wt22`
  berisi (b) tergabung, belum di-commit. Prosedur per berkas: HEAD = basis → salin W; beda → `git merge-file -p <HEAD> <B>
  <W>`; berkas baru disalin; `CODEBASE_MAP.md`, `configKeyIndex.json` (`--check` selaras), fixture akses dibangkitkan ulang
  (`test_fe03_access_catalog --noconftest` 6/6).
- Digabung tiga arah **tanpa bentrok**: `ENTITY_REGISTRY.md`, `memory/PRD.md` (entri PY-T2/TX-T2 dan AG-T5 berdampingan),
  `configKeyIndex.json` (lalu dibangkitkan ulang).
- **Bentrok** (kedua perilaku dipertahankan): `backend/tests_mem/test_KFT1_izin_pengaturan.py` — konstanta `PYT2_KUNCI`,
  `TXT2_KUNCI` (HEAD) dan `AGT5_KUNCI`, `AGT5_KUNCI_KONTROL` (unit ini) semua dipertahankan; U04 = `… + PMT3_KUNCI +
  PYT2_KUNCI + TXT2_KUNCI + AGT5_KUNCI`, U02 `… + PK24_KUNCI_KONTROL + AGT5_KUNCI_KONTROL`.
  `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` — §9.18 (PY-T2) dan §9.19 (TX-T2) tetap; bagian AG-T5 menjadi **§9.20** (di W
  bernomor §9.18). `CODEBASE_MAP.md` — dibangkitkan ulang terhadap HEAD tujuan.
- Hitungan lain: PR-T9 (`TAMBAHAN_SESUDAH`), indeks wajib PK-14, antrean KP-T4 — HEAD tidak menambah apa pun di sana, jadi tidak
  ada penjumlahan dengan unit lain (KP-T4: 39 + `ai_card_second` = 40).
- Keadaan **(a)** tergabung: `…/AG-T5_a_merged/` (`files/`, `FILES.txt` 33 berkas, `BASIS.txt` = `84744dc`; bentrok yang sama
  diselesaikan dengan cara yang sama). Uji: `tests_mem` penuh (a) tergabung di `5f193df` **1945 / 2 / 2**
  (`bukti/AG-T5/tests_mem_a_tergabung_T.log`); di `84744dc` subset KF-T1, KF-T6, PR-T9, AG-T5 (a), AG-T3, PY-T2, TX-T2, PK-05
  **143 lulus** (`tests_mem_a_tergabung_T_subset.log`).
- Angka di T (`84744dc` + AG-T5 (b)) — HEAD diukur dari salinan `git archive 84744dc`:
  - `tests_mem`: HEAD **1972 / 2 dilewati / 2 xfail** → T **2000 / 2 / 2** (+28: 18 (a) + 7 (b) + 3 putaran pengaturan
    untuk tiga kunci baru); tanpa merah (`bukti/AG-T5/tests_mem_{HEAD,T}_84744dc.log`).
  - Jest penuh: HEAD **121 suite · 972 uji** → T **123 · 983** (+11; 35 suite gagal dimuat `cmdk`/`@radix-ui` sama dengan HEAD).
  - `hitung_penjaga.sh`: HEAD auth 27 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 5 · entity_label 2
    (lainnya 0/PASS) → T sama kecuali **auth 26** (turun).
  - `verify_role_gate_ui` 31/0 = 31/0; `verify_atomic_claim` 160/0 = 160/0 (+ uji-diri 64 hijau); `verify_permission_checked`
    606 → 609/0; `verify_posting_coverage` 133/0; `verify_cash_single_door` 730 → 731/0; `verify_detail_modal` 30/0;
    `verify_payment_vocab` 1818 → 1819/0; `verify_access_catalog_nav` 0; `verify_config_fallback` 158/0 (`--entity` 158/0) dan
    `verify_config_text` 3311/0 di T (di salinan HEAD tidak bisa dijalankan tanpa `MONGO_URL`); `audit_config_wiring --strict`
    hijau dan `check_nav_map` PASS (keduanya lewat salinan berjalur T).
- Seed data uji (`seed_realistic.py` akar repo dan `backend/seed_realistic.py`): unit ini tidak mengubah syarat pembuatan dokumen
  yang di-seed (bayar tagihan, kas manual, jurnal tetap) dan tidak menghapus/mengganti nama fungsi yang dipakai di luar
  (`list_cards` hanya mendapat parameter opsional `ctx`, `_write` parameter opsional `card_class`) — dicek `grep`; keduanya tidak
  perlu diubah.

## Hambatan lingkungan

- Lapis A (U9) dan uji jalan peramban (pop-up Pusat Persetujuan → kartu U3) tidak bisa di lingkungan B.
- `verify_aging_fields` (membaca MongoDB lewat `backend/.env`) sempat terpanggil SEKALI di daftar penjaga saya (baca-saja,
  tanpa keluaran dalam batas waktu) — tidak dijalankan lagi; kandidat field `AGING_META['ai_card_second']` (`first_at`,
  `created_at`, `title`, `user_name`) semuanya ditulis `ai_cards.prepare` / `_await_second`.
- Satu `git stash`/`git stash pop` sesaat di W untuk membandingkan keluaran `verify_auth_coverage` dengan basis (dipulihkan
  utuh, tanpa commit); perbandingan berikutnya memakai `git show <rev>:berkas`.

## Temuan di luar lingkup (tidak diperbaiki)

- `GET /api/contra-bons/{id}` menyembunyikan nilai bagi yang tanpa `vendor_bill.view` (PK-17): orang kedua berizin
  `contra_bon.pay` tetapi tanpa `vendor_bill.view` akan mendapat `stale` pada kartu kontrabon (sidik membaca `totals`).
- Pintu `POST /api/ai/actions/{id}/confirm` sekarang menulis notifikasi (jalur orang kedua) tetapi tidak terlihat oleh pencacah
  `inventaris_multi_koleksi` (penelusuran satu tingkat).

## Yang perlu direview

- Urutan `second` (sakelar PT sebelum pembanding pembuat; izin pintu sesudahnya) dan pemakaian aturan saat diputus.
- `ACTION_HINTS` (kata pada kode tak terdaftar → baris larangan) — pola sengaja luas.
- Pembuat menarik kartu menunggu; kotak "Menunggu orang lain" memuat kartu pembuat.
- U9 di MongoDB asli; uji jalan kartu & Pusat Persetujuan di 1280/1024/390 px.

Status: implemented_pending_review.
