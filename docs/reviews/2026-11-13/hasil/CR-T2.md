# CR-T2 — Jadwal tagihan sebagai satu sumber jatuh tempo, dan saldo piutang tersimpan per pelanggan per PT

- Commit awal: `5f193df` (worktree kerja, basis B)        - Commit akhir: (a) `2d9709e`, (b) `76a337d`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke worktree tujuan pada HEAD **`84744dc`** (`[TX-T2](b)`, sesudah PY-T2 dan TX-T2 (a)); bentrok tekstual diselesaikan, kedua perilaku dipertahankan — lihat "Penggabungan"
- ID ditangani: CR-06, CR-09 (spesifikasi `docs/blueprint/unit/CR-T2.md`; keputusan K-16 "jatuh tempo per surat jalan; per
  baris rencana untuk cicilan; DP sebelum kirim", K-31 hanya dicatat — komposisi eksposur = CR-T3)
- Risiko tinggi → dua serah-terima (`00` §8): **(a)** jalur baru (jadwal tagihan `payment_plans` `origin: term`, saldo
  tersimpan `customer_balances`, kait, endpoint, invarian, skrip) — pembaca lama belum dialihkan; **(b)** pembaca jatuh
  tempo dialihkan ke jadwal (umur piutang, status kredit, daftar tagih, pengingat, proyeksi kas, Tanya KN),
  `customer_service._term_days` dihapus, layar.

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`; diperiksa di `5f193df`)

| Fakta spesifikasi | Hasil di basis B |
|---|---|
| `due_context`/`order_due` — jatuh tempo seluruh sisa = surat jalan pertama (`customer_service.py:169/:200`) | **Tidak berlaku** — dihapus PK-41; jatuh tempo per surat jalan dihitung saat dibaca di `report_basis.baris_tagihan` (`report_basis.py:137`) |
| `compute_customer_credit` membaca ≤ 2.000 pesanan tiap dibuka, tanpa simpan (`:216`) | **Sebagian** — bergeser `:199`; batas 2.000 sudah dicabut PK-41 (kursor), tetapi tetap dihitung ulang dari semua pesanan tiap dibuka, tanpa simpan |
| Pesanan bertermin tunai dilewati (`NON_AR_METHODS` `:234`; `_eligible_outstanding` `ar_aging_service.py:131`) | Berlaku, bergeser — `customer_service.py:19`, `report_basis.pesanan_piutang` `:89`; `_eligible_outstanding` dihapus PK-41 |
| Denda pesanan tanpa rencana: tanggal pesanan + termin profil (`penalty_service.py:253`) | Berlaku, bergeser `:294` (CR-T4) |
| Taksiran denda dibulatkan bulan (`ar_aging_service.py:76`) vs nota denda harian (`penalty_service.py:104`) | Berlaku, bergeser `:79` / `:108` (CR-T4) |
| `payment_plans` hanya buatan orang; `MODES` `:45`; satu rencana aktif "dijaga kode, bukan indeks" (`get_active` `:246`) | Sebagian — `MODES` `:45`, `get_active` `:255`; indeks `uq_plan_active_doc` (status `active`) SUDAH ada sejak PK-14 (`indexes.py:760`); status `closed` belum dijaga |
| INV-PAY-01 (`payment_plan_service.py:27`; `verify_data_integrity.py:3013`) | Berlaku, bergeser — `:27`; `verify_data_integrity.py:3170/:3192` |
| `line_id` hanya pada baris hasil pecah (`:535`) | Berlaku (`reschedule_line`) |
| `recompute_paid` `:426`, dipanggil ulang tiap kwitansi (`ar_receipt_service.py:605`) | Berlaku, bergeser — `:453`; pemanggil kini fungsi alokasi tunggal PK-19 (`ar_allocation_service._segarkan` `:183`, `remove_unborn` `:404`) |
| Piutang lahir per dokumen surat jalan (`gl_service.py:1092/:1124`) | Berlaku, bergeser `:1445` (`post_shipment_revenue`: `source_id` = dokumen surat jalan, `source_label` = nomor, `ref.order_id`, tanggal = `shipment.created_at`) |
| Satu keberangkatan = beberapa dokumen bernomor sama; jurnal sesudah dokumen (`shipment_service.py:98/:149`) | Berlaku, bergeser — `dispatch_order_batch`; `post_durable` sesudah `insert` `:154`; tiap `dispatch_task` menjurnal SEMUA surat jalan pesanan yang belum berjurnal |
| `recognized_by_order` `:153`, `split_outstanding` `:172` | Berlaku, bergeser `:175`, `:196` (dipakai `order_journey_service`) |
| Pembaca jatuh tempo lain: proyeksi kas `:80`, pengingat `alert_ops_service.py:287`, alat asisten `ai_tools.py:71` (`due_context`) | Bergeser — PK-41 mengalihkan ke `baris_tagihan` (`cashflow_forecast_service.py:74`, `ai_tools.py:71`; pengingat lewat `ar_aging_service.orders_due_soon`, `alert_ops_service.py:290`) |
| Titipan `customers.deposit_balance` tidak mengurangi hitungan kredit (`:273`) | Berlaku (CR-T3) |

## Hubungan jadwal tagihan ↔ `baris_tagihan` (satu sumber jatuh tempo)

- **Satu rumus jatuh tempo**: `report_basis.jatuh_tempo(tanggal, hari)` + `report_basis.hari_termin(pelanggan, pesanan,
  peta)` (aturan `_term_days` yang dipindah, D8). Dipakai pembangun jadwal, proyeksi kas (bagian belum dikirim), nota
  debit (`credit_note_service.due_date_of`), denda pesanan tanpa rencana dan selisih bayar (pemanggil lama, hanya impornya).
- **Satu pembangun baris**: `billing_schedule_service.bangun_baris` (tabel K-16) — dipakai kait peristiwa (disimpan),
  skrip `build_billing_schedule.py` (disimpan), dan pembaca untuk pesanan yang belum berjadwal (dibaca, tidak disimpan;
  INV-PAY-05 WARN melaporkannya).
- **Satu pembaca jatuh tempo**: `billing_schedule_service.lines_for_orders` (inti `open_lines`). Sesudah (b),
  `report_basis.baris_tagihan` = baris dari `lines_for_orders` (bentuk baris PK-41 tetap: `sumber`, `jatuh_tempo`,
  `nilai`, `terbayar`, `sisa`, `hari_lewat`, `jurnal_*`) + satu baris "belum dikirim" + bagian `tercatat` per baris.
  Semua pemanggil PK-41 (umur piutang, rincian, pengingat H-x, daftar tagih, proyeksi kas, Tanya KN, Tower) ikut dialihkan
  tanpa mengubah bentuk jawaban.
- Untuk pesanan tempo/tunai tanpa DP dan tanpa rencana, baris jadwal = baris PK-41 (dibuktikan U3 di kode (a): `open_lines`
  dan `baris_tagihan` memberi baris, nilai, jatuh tempo, hari lewat, dan jurnal yang sama). Bedanya hanya pada baris
  yang baru terbaca: uang muka (K-16) dan baris rencana cicilan.

## Serah-terima (a) — jalur baru, pembaca lama belum disentuh

| Berkas | Isi |
|---|---|
| `backend/services/billing_schedule_service.py` (baru) | `bangun_baris` (K-16), `termin_pesanan` (potret termin), `sync_order` (gabung idempoten per `source_type`+`source_id`, tulis-bersyarat `rev`, ≤ 6 ulang), kait `on_order_confirmed`, `on_shipment_posted`, `on_order_changed`, `on_debit_note`, `after_shipment_journal` (galat → `shipments.billing_status: failed`), `retry_shipment_billing`, `lines_for_orders`, `open_lines`, `recognized_sen`; kode bayar per baris lahir (`payment_code_service.ensure_for_line`, PM-T2) |
| `backend/services/customer_balance_service.py` (baru) | `compute` (murni dokumen), `refresh` (hitung ulang penuh; tanpa PT = semua PT pelanggan — bentuk panggilan PM-T3), `refresh_safe`, `get`, `get_many`, `rebuild_all`, `job_refresh_overdue`, `verify_stored` (INV-BAL-01), `reconcile_gl` (INV-BAL-02) |
| `backend/routers/customer_balances.py` (baru) + `server.py` | `GET /api/customers/{id}/billing-schedule`, `GET /api/customers/{id}/balance`, `POST /api/ar/balances/rebuild` |
| `services/payment_plan_service.py` | `MODES` + `term` "Mengikuti termin"; `get_manual`; `get_active` = jadwal hidup apa pun asalnya (rencana orang menang bila kembar); `create_plan` `origin: manual`, `line_id` semua baris, me-void jadwal term, segarkan saldo; `update_plan`/`void_plan`/`reschedule_line` menolak jadwal term; `recompute_paid` tulis-bersyarat `rev` + status `closed` jadwal term hanya bila tertagih penuh dan lunas; `list_plans` tanpa jadwal term; `needs_plan` = rencana orang |
| Kait | `so_lifecycle_service.confirm_core`, `shipment_service.dispatch_task` (sesudah jurnal), `posting_registry` (ulang jurnal surat jalan + jenis baru `shipment_billing` "Jadwal Tagihan Surat Jalan"), `sales_order_helpers.so_transition` (status mati), `credit_note_service._baris_tagihan` (nota debit), `ar_allocation_service._segarkan`/`remove_unborn`, `ar_receipt_service` (simpan & batal kwitansi, deposit), `store_credit_service._append`, `penalty_service` (terbit/bebas/ubah/bayar), job `scheduler_service` "customer_balance_overdue" 00.10 WIB |
| Pembaca lama dijaga tetap | `penalty_service` (akrual hanya rencana orang; CR-T4), `payment_variance_service._order_due_now`, `ar_aging_service` kolom rencana, `routers/payment_plans.py` by-doc → `get_manual` |
| `services/report_basis.py` | `jatuh_tempo` (satu rumus; `baris_tagihan` memakainya — hasil sama), `hari_termin` (pembungkus di (a)) |
| `indexes.py` | wajib `payment_plans.uq_plan_live_doc` (`doc_id`, `doc_type` \| status `active`/`closed`), `customer_balances.uq_customer_entity`; indeks kinerja `lines.line_id`, (`origin`, `status`), (`customer_id`, `status`), (`entity_id`, `overdue_as_of`); `uq_id` `customer_balances` |
| `scripts/verify_data_integrity.py` | INV-PAY-01 aturan jadwal term; INV-PAY-05 (WARN); lapisan baru `balance` INV-BAL-01/02 |
| `scripts/build_billing_schedule.py` (baru) | `--dry-run` (bawaan, baca-saja) + daftar pelanggan yang status kreditnya berubah; `--apply` |
| Uji | `tests_mem/test_CRT2_jadwal_saldo.py` (17), `tests/test_bp_CRT2_jadwal_bersamaan.py` (lapis A U17, ditulis); disesuaikan: `test_PMT2_instruksi_bayar.py` (cabang U11 & kode per baris yang menunggu CR-T2), `test_PK14_indeks_wajib.py` + lapis A `test_bp_PK14_indeks_wajib.py` (+2 indeks: 29 → 31) |
| Dokumen | `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md`, `scripts/verify_contract.py` (`customer_balances`) |

Merah di kode lama: **17/17** (`ImportError: billing_schedule_service`, `get_manual` tidak ada) — `bukti/CR-T2/a_merah_kode_lama.txt`;
hijau 17/17. Keadaan (a): `$S/CR-T2_a_state/` (basis `5f193df`, 30 berkas) dan `$S/CR-T2_a_merged/` (HEAD `5f193df` = basis,
isi sama, tanpa bentrok). `tests_mem` keadaan (a): **1941/2/2** (= 1924 + 17).

## Serah-terima (b) — pembaca dialihkan, jalur lama dimatikan

| Berkas | Perubahan |
|---|---|
| `services/report_basis.py` | `hari_termin` berisi aturan (pindahan `_term_days`); `baris_tagihan` membaca `billing_schedule_service.lines_for_orders` + baris belum dikirim + `tercatat`; `SUMBER_UANG_MUKA`, `SUMBER_RENCANA`; `ringkas_baris`: `ar_ledger` = Σ tercatat, `exposure` = total − tercatat, `tagih` baru; `tercatat_sen` |
| `services/customer_service.py` | `_term_days` **dihapus**; `compute_customer_credit` dari `customer_balance_service.get_many` (tercatat = `ar_delivered − cash_term_amount`, belum dikirim = `open_orders_amount − cash_term_open_amount`, telat = `days_overdue`, titipan dari saldo); `collection_worklist.outstanding` = `tagih` |
| `services/ar_aging_service.py` | `_sum_lines` memakai `tercatat`; docstring |
| `services/cashflow_forecast_service.py`, `credit_note_service.py`, `penalty_service.py`, `payment_variance_service.py`, `scripts/seed_ar_due_soon_demo.py`, `scripts/pk41_status_kredit_berubah.py`, `tests/test_g3_phase03.py` | impor `report_basis.hari_termin` / `jatuh_tempo` (perilaku sama) |
| `services/customer_balance_service.py` | `sidik` dokumen (jaring pengaman penulis yang belum berkait; `get` menyegarkan, INV-BAL-01 melaporkan WARN "basi"); job harian mengambil daftar pasangan dulu |
| `scripts/verify_data_integrity.py` | INV-BAL-01: WARN untuk saldo basi menurut sidik |
| `services/billing_schedule_service.py` | pesanan sample dibaca dari pembangun (tidak pernah disimpan); nota debit membawa nomor & jurnalnya |
| Layar | `ARAgingDetail.jsx` bagian "Jadwal Tagihan" + galat; `ARAgingView.jsx` galat muat rincian; jest `crt2JadwalTagihan.test.js` (5) baru; `pk41LaporanPendukung.test.js` judul kolom "Tagihan" |
| Uji | `tests_mem/test_CRT2_pengalihan.py` (9) |
| Dokumen | `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.18 (di T §9.20), `CODEBASE_MAP.md` |

Pencarian pematian jalur lama (`grep -rn '_term_days\b' backend scripts seed_realistic.py`, di luar `contra_bon_service._term_days`
milik pemasok): tanpa pemanggil (`due_context`/`order_due` sudah dihapus PK-41). Arsip `docs/audit/…/repro/` tidak diubah.

Merah di kode (a) (`bukti/CR-T2/b_merah_kode_a.txt`): **4 merah, 3 hijau** — U7 `b1_30` 0 (seharusnya 1.000.000), U8 `b1_30`
1.000.000 telat 19 (seharusnya 31–60 500.000 + 1–30 500.000, 35), pengingat H+1 uang muka tidak ada, U3 `line_id` belum ada
di baris (angka sama); U9, U10, U15 hijau sejak PK-41 dan tetap hijau. Uji job harian ditambahkan sesudahnya (hijau).

## Uji penerimaan

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah: modul tidak ada | lulus — jadwal `term`, 1 baris `shipment` 400.000 jatuh tempo 2026-10-01, `billed_total` 400.000 |
| U2 | B | merah | lulus — tetap 1 baris, `line_id` sama, satu jadwal hidup |
| U3 | B | (a) setara: merah lama (modul); (b) endpoint: hanya `line_id` belum ada, angka sama | lulus — `open_lines` = `baris_tagihan` (400.000, 2026-10-01, 45 hari, jurnal sama); `GET /api/ar/aging?as_of=2026-11-15`: `b31_60` 400.000, `current` 600.000, total 1.000.000, selisih pencocokan 0 |
| U4 | B | merah | lulus — `ar_delivered` 400.000; `open_orders_amount` 600.000; `overdue_amount` 400.000; `oldest_due_date` 2026-10-01; `days_overdue` 45 |
| U5 | B | merah | lulus — baris kedua 600.000 jatuh tempo 2026-10-10; Σ 1.000.000; `open_orders_amount` 0 |
| U6 | B | merah | lulus — kwitansi lewat `POST /api/ar-receipts` tgl 5 Okt: baris 1 lunas, baris 2 terbayar 100.000 sisa 500.000; `ar_delivered` 500.000; `overdue_amount` 500.000; `oldest_due_date` 2026-10-10; `last_payment_amount` 500.000 (tersimpan oleh fungsi alokasi, tanpa pembaca) |
| U7 | B | merah: `b1_30` 0 | lulus — baris `dp` 1.000.000 jatuh tempo 2026-11-03; `shipment` 400.000 jatuh tempo 2026-11-20; per 20 Nov `b1_30` 1.000.000 (17 hari), `current` 1.000.000, tercatat 800.000 |
| U8 | B | merah: `b1_30` 1.000.000, telat 19 | lulus — jadwal term void "diganti rencana baru", rencana tetap 2 baris; `b31_60` 500.000 (35), `b1_30` 500.000 (5); `max_overdue_days` 35, diblokir |
| U9 | B | lulus (PK-41) | lulus — per 31 Okt `b1_30` 400.000 + `current` 600.000; per 15 Nov `current` 600.000 |
| U10 | B | lulus (PK-41) | lulus — dari saldo tersimpan: `overdue_amount` 400.000, `max_overdue_days` 19 → `blocked`; belum dikirim 600.000 tidak telat |
| U11 | B | merah | lulus — saldo Q (`ent_ksc`, 250.000) tidak berubah; (P, `ent_ksc`) semua 0 |
| U12 | B | merah | lulus — INV-BAL-01 FAIL menyebut "Toko P CR-T2 … ar_delivered"; rebuild `changed` 1; lalu PASS |
| U13 | B | merah | lulus — PASS (400.000 = 400.000); jurnal manual Dr 1-1200 50.000 → WARN selisih 50.000 sebab "jurnal tanpa pesanan"; sumber tak dikenal → FAIL |
| U14 | B | merah | lulus — Tanpa Acuan + `payment_plan.view` 200; Manajer Kosong 403; Sopir 403; PT di luar penugasan 403; pelanggan di luar cakupan 403 "Pelanggan ini di luar cakupan Anda."; saldo: `credit_profile.view` 200, Sopir 403; bangun ulang Sopir 403 |
| U15 | B | lulus (PK-41) | lulus — 400.000 jatuh tempo 2026-10-01 (`per_sj`); 600.000 perkiraan 2026-10-20 (`estimate_not_shipped`) |
| U16 | B | merah | lulus — jadwal void; saldo P 0 |
| U17 | A | — | **ditulis, belum dijalankan** (`backend/tests/test_bp_CRT2_jadwal_bersamaan.py`; dua kait bersamaan × 3 putaran → satu jadwal hidup, dua baris tanpa kembar; sisip jadwal hidup kedua / saldo kedua → DuplicateKeyError) |
| U18 | layar | jest merah 4/4 (`bukti/CR-T2/jest_merah_layar_lama.txt`) | jest `crt2JadwalTagihan` 5/5 hijau. **Belum diuji jalan** di peramban (integrator: data acuan + pesanan DP + pesanan tempo dikirim sebagian lewat alur gudang) |
| tambahan | B | merah | lulus — kait gagal → `billing_status: failed` + panel Posting Gagal jenis `shipment_billing` + ulang → baris lahir; INV-PAY-01 jadwal term (merah bila baris dipotong); pembaca lama (denda, panel rencana, daftar rencana) mengabaikan jadwal mesin di (a); skrip baca-saja → tulis → idempoten + daftar status berubah; pengingat H+1 uang muka & daftar tagih; job harian 00.10 |

### Contoh angka — dokumen → jurnal → buku pembantu (F1, hitung tangan)

- Pesanan S1 Rp 1.000.000 NET30 (`ent_kanda`, non-PKP). Surat jalan SJ-1 1 Sep (40 yard): jurnal `shipment_revenue`
  **Dr 1-1200 400.000 / Cr 4-1000 400.000** → baris jadwal `shipment` 400.000 jatuh tempo 1 Sep + 30 = **1 Okt**. Saldo
  tersimpan per 15 Nov: terkirim belum lunas min(1.000.000 − 0, 400.000 − 0) = **400.000**; belum dikirim 1.000.000 −
  400.000 = **600.000**; lewat tempo 400.000 (1 Okt < 15 Nov, 45 hari). INV-BAL-02: Σ 400.000 = saldo 1-1200 `ent_kanda`
  400.000.
- SJ-2 10 Sep (60 yard): **Dr 1-1200 600.000 / Cr 4-1000 600.000** → baris 600.000 jatuh tempo **10 Okt**; Σ baris
  1.000.000 = nilai pesanan; belum dikirim **0**.
- Kwitansi 500.000 tgl 5 Okt (transfer, alokasi ke S1): jurnal kas **Dr bank 500.000 / Cr 1-1200 500.000**; baris 1
  (jatuh tempo tertua) lunas 400.000, baris 2 terbayar 100.000 sisa **500.000**. Saldo: terkirim belum lunas 1.000.000 −
  500.000 = **500.000** = saldo 1-1200 (400.000 + 600.000 − 500.000); lewat tempo per 15 Nov 500.000, jatuh tempo tertua
  10 Okt.
- DP50 (U7): pesanan 2.000.000 dikonfirmasi 3 Nov → baris uang muka 2.000.000 × 50 % = **1.000.000** jatuh tempo 3 Nov
  (tanpa jurnal — piutang buku besar baru lahir saat kirim). Surat jalan 6 Nov: **Dr 1-1200 800.000 / Cr 4-1000 800.000**
  → baris surat jalan 800.000 × 50 % = **400.000** jatuh tempo 20 Nov. Umur per 20 Nov: 1–30 hari 1.000.000; belum jatuh
  tempo 400.000 + 600.000 (belum ditagih); tercatat 800.000 = saldo 1-1200 → pencocokan tetap 0.

## Uji lama yang menguji perilaku yang sengaja diubah (dilaporkan)

- `test_PMT2_instruksi_bayar.py`: U6 menuntut kode tingkat pesanan tanpa `plan_id`/`line_id` (CR-T2 belum ada) — kini kode
  itu terkait ke baris uang muka jadwal (aturan `ensure_for_line` PM-T2); U11 punya `pytest.fail("CR-T2 sudah ada: lengkapi
  cabang U11 …")` — dilengkapi (satu surat jalan → satu kode 400.000 jatuh tempo 2 Des, instruksi "2 Des 2026"); uji kode
  per baris memakai jadwal hasil kait (fixture rencana kedua kini ditolak indeks `uq_plan_active_doc`).
- `test_PK14_indeks_wajib.py` (+`CRT2_INDEKS = 2`), lapis A `test_bp_PK14_indeks_wajib.py` 29 → 31.
- `pk41LaporanPendukung.test.js`: judul kolom rincian "Surat Jalan" → "Tagihan".
- `tests/test_g3_phase03.py` (lapis A): impor `report_basis.hari_termin` (isi asersi sama).

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`38c715f`** — satu gate
untuk rantai gelombang 4 (PY-T2, TX-T2 (a/b) + cek layar, AG-T5 (a/b) + cek layar, CR-T2 (a/b), PM-T4):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`b62ef45`: 12 / 39) — tidak ada gate baru yang merah. "Tidak dijalankan" tambahan = ganti label
(`guard:atomic_claim SELF-TEST` 10 → 64 kasus, `guard:page_tabs` + uji-dirinya). Kuitansi: `bukti/CR-T2/gate_quick_receipt.md`,
`gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- Rantai gelombang 4 dipasang integrator berurutan di atas `8ac7059`: PY-T2 `5edef21` · `82ef1bb` → TX-T2 (a) `38b5c9b` · (b) `84744dc` · cek layar `15d3258` → AG-T5 (a) `31a8d54` · (b) `7747302` · cek layar `df23cb2` → CR-T2 (a) `2d9709e` · (b) `76a337d` → PM-T4 `38c715f`. Tiap commit diuji `tests_mem` penuh di worktree bantu sebelum dipetik (angka di bawah). Jest penuh di `38c715f`: **995 lulus** (957 + PY-T2 8 + TX-T2 7 + AG-T5 11 + CR-T2 5 + PM-T4 7; 35 suite gagal dimuat `cmdk`/`@radix-ui`, sama). Penjaga statik di `38c715f` = garis dasar kecuali `verify_auth_coverage` 27 → **26** (AG-T5); `verify_atomic_claim` 161/0, `verify_posting_coverage` 138/0, `verify_cash_single_door` 736/0, `verify_role_gate_ui` 31/0, `verify_detail_modal` 30/0. Glosarium KN_32: §9.18 PY-T2 · §9.19 TX-T2 · §9.20 AG-T5 · §9.21 CR-T2 · §9.22 PM-T4 (nomor pelaksana dirapikan integrator). Indeks wajib lapis A: 29 + PY-T2 2 + CR-T2 2 + PM-T4 1 = **34** (`check_required_indexes` 34/34 di data acuan).
- Dipasang di atas AG-T5 (`df23cb2`): (a) **`2d9709e`** dari keadaan (a) tergabung (basis `5f193df`) — bentrok
  `indexes.py`, `shipment_service.py` (kait draf faktur TX-T2 lalu baris jadwal CR-T2), dua uji PK-14 (konstanta
  PY-T2 + CR-T2, lapis A 33) — kedua perilaku dipertahankan; (b) **`76a337d`** dari T pelaksana — bentrok KN_32 (CR-T2 →
  §9.21). `tests_mem`: (a) **2017/2/2**, (b) **2025/2/2**, 0 gagal.
- Lingkungan A (data acuan sesudah `restore_demo`, kode `38c715f`): `check_required_indexes` **34/34**
  (`uq_plan_live_doc`, `customer_balances.uq_customer_entity` terpasang, 0 kembar — H6 tidak terjadi).
  `build_billing_schedule.py` (baca-saja) di data acuan: 8 pesanan hidup · jadwal baru 0 · baris baru 0 · **0 pelanggan
  berubah status kredit** (`bukti/CR-T2/integrator_billing_dry_run.txt`) — data acuan sudah berjadwal lewat kait saat
  disemai. `verify_data_integrity`: INV-PAY-01/02/05 PASS, **INV-BAL-02 PASS** (Σ piutang terkirim = saldo akun piutang, 3
  PT — kekhawatiran pelaksana tidak terjadi), INV-BAL-01 PASS + WARN 2 saldo basi (disegarkan saat dibaca)
  (`integrator_invarian_data_acuan.txt`). Lapis A **U17 lulus** (jadwal bersamaan → satu jadwal); `test_g3_phase03`
  (impor `hari_termin`) lulus. **`--apply` di data nyata = H3, menunggu pemilik.**
- Uji jalan **U18** (Keuangan › Piutang › rincian pelanggan): bagian "Jadwal Tagihan" (Pesanan · Tagihan "Surat jalan
  SJ-…" + tautan jurnal · Jatuh tempo · Nilai · Dibayar · Sisa · Telat berikon) = lebar pop-up di 1280 (1120 px) dan 1024
  (952 px); di 390 px bergulir di dalam kartu; keadaan kosong "Tidak ada tagihan terbuka." untuk pesanan belum dikirim;
  ringkasan "tercatat · belum dikirim" di kepala pop-up (`bukti/CR-T2/cek_*.png`). Tidak ada cacat.
- Catatan: uji lapis A U17 meninggalkan pelanggan uji `Toko BP CR-T2 …` di database uji (dipulihkan `restore_demo`).

Pelaksana (catatan asli):

Belum dijalankan (`gate.sh --quick` / penuh dijalankan integrator di lingkungan A).

## Angka uji

| Rangkaian | Sebelum | Sesudah |
|---|---|---|
| `tests_mem` W | B `5f193df` **1924 lulus / 2 dilewati / 2 xfail** | (a) **1941 lulus / 2 dilewati / 2 xfail** (= 1924 + 17; salinan lengkap B + berkas (a), `bukti/CR-T2/tests_mem_a.txt`); (b) = T (isi sama) |
| `tests_mem` T (`84744dc`, akhir) | HEAD 1972/2/2 (diturunkan) | **1997 lulus / 2 dilewati / 2 xfail** (= 1972 + 25; `bukti/CR-T2/T3_tests_mem.txt`) |
| `tests_mem` T (`8ac7059`) | HEAD 1942/2/2 (diturunkan) | **1967 lulus / 2 dilewati / 2 xfail** (= 1942 + 25; `bukti/CR-T2/T2_tests_mem.txt`) |
| `tests_mem` T (`5f193df`, gabung pertama) | HEAD = B 1924/2/2 | **1949 lulus / 2 dilewati / 2 xfail** (= 1924 + 17 + 8; `bukti/CR-T2/T_tests_mem.txt`); berkas CR-T2 + PM-T2 + CR-T1 sesudah suntingan terakhir 67/67 (`T_crt2_final.txt`) |
| jest T | B **957 lulus** (35 suite gagal dimuat `cmdk`/`@radix-ui`, lingkungan) | gabung pertama **962**; `8ac7059` **970**; akhir `84744dc` **977** (HEAD 972 + 5; 35 suite sama) |

Penjaga statik (`hitung_penjaga.sh`, B → W/T): auth 27 → 27 · ui_standard 13 → 13 · i18n 103 → 103 · create_modal 6 → 6 ·
page_tabs 1 → 1 · to_list 5 → 5 · entity_label 2 → 2 · lainnya PASS/0. `verify_role_gate_ui` 31/0; `verify_config_fallback`
157/0 (+`--entity` 157/0); `verify_payment_vocab` 1817/0; `verify_access_catalog_nav` 0; `verify_posting_coverage` **134/0**
(+1 jenis registri `shipment_billing`; uji-diri hijau); `verify_cash_single_door` 731/0 (uji-diri hijau);
`verify_permission_checked` 606/0; `verify_detail_modal` 30/0; `verify_atomic_claim` 160/0 (+`--self-test` 64 hijau;
inventaris multi-koleksi tetap 123 baris, dibangkitkan ulang tanpa selisih); `audit_config_wiring --strict` hijau;
`check_nav_map` PASS; `verify_codebase_map` PASS (`bukti/CR-T2/penjaga_*.txt`).

## Cek layar (dari kode; foto 1280/1024/390 oleh integrator)

| Layar | Daftar periksa |
|---|---|
| Keuangan › Piutang › rincian pelanggan (`ARAgingDetail`, pop-up `DetailModal`) — bagian baru "Jadwal Tagihan" | (1) tabel 7 kolom (Pesanan, Tagihan, Jatuh tempo, Nilai, Dibayar, Sisa, Telat (hari)) di `table-wrap` + `data-table head-wrap`; tanpa kolom aksi (tautan pesanan/jurnal di sel, `link-button`) → tidak ada tombol terpotong; (2) di dalam `section-body` kartu rincian; (3) kepala bagian = ikon + judul + "N tagihan terbuka" satu baris, saringan di bilah sendiri; (4) tidak ada tombol mati; (5) telat = `status-pill` ikon + angka + warna; belum jatuh tempo = teks "0"/"N lagi"; (6) > 8 baris → kotak cari "Cari pesanan / tagihan…" + saringan "Hanya lewat jatuh tempo" (`filter-chip`, `aria-pressed`); hasil saringan kosong "Tidak ada tagihan yang cocok dengan saringan." beda dengan "Tidak ada tagihan terbuka."; (7) tanpa teks wewenang; (8) bagian belum dikirim tidak ikut jadwal (tidak bertanggal); catatan kaki "Umur dihitung per tagihan: surat jalan, uang muka, atau baris rencana." Rupiah `tabular-nums`, tanggal `formatDate` (WIB) |
| Rincian pelanggan — sub-tabel per pesanan (PK-41) | judul kolom pertama "Tagihan"; baris "Uang muka 50%" dan baris rencana (label rencana) kini muncul; lain tetap |
| Rincian pelanggan — keadaan | memuat (kerangka), **galat** (baru: `notice-bar danger` `role="alert"` ikon + kalimat + "Coba lagi" `secondary-button btn-sm`), kosong ("Tidak ada pesanan terbuka.") dibedakan |
| Keuangan › Piutang (`ARAgingView`) | susunan kolom tetap (PK-41); angka kelompok umur kini memuat uang muka & baris rencana; galat muat rincian diteruskan ke pop-up |

Belum diuji jalan di peramban (U18).

## Menyimpang dari blueprint

1. **Indeks satu jadwal hidup**: MongoDB tidak menerima `$ne` di ekspresi parsial; dipakai `status ∈ {active, closed}` dan
   kunci dibalik (`doc_id`, `doc_type`) sebagai indeks baru `uq_plan_live_doc` supaya tidak berpola kunci sama dengan
   `uq_plan_active_doc` (PK-14, tetap). `lines.line_id` = indeks biasa (bukan unik).
2. **Jadwal term tanpa nomor** (`number: ""`) dan tanpa tautan `refs` — supaya nomor RPB tidak habis untuk tiap pesanan;
   daftar Rencana Pembayaran (`list_plans`) dan panel rencana pesanan (`by-doc`) hanya menampilkan rencana buatan orang.
   Jadwal term tidak bisa diubah/di-void/dijadwal ulang tangan (400 "Jadwal tagihan ini mengikuti termin …").
3. **Kunci idempotensi baris**: `source_type`+`source_id`; uang muka `order` + `dp:<id pesanan>`, jurnal lama per pesanan
   `order` + id pesanan, nota debit `debit_note` + id nota. Nilai baris surat jalan/nota debit selalu disamakan dengan
   dokumennya saat kait diulang (dokumen kedua bernomor surat jalan sama yang jurnalnya terbit belakangan menambah nilai,
   bukan baris kedua); uang muka hanya disesuaikan bila belum dibayar.
4. **Pembaca untuk pesanan yang belum berjadwal**: dibaca dari pembangun yang sama tanpa disimpan (pesanan lama sebelum
   skrip, kait gagal, pesanan sample) — supaya pengalihan (b) tidak mengosongkan umur piutang data lama sebelum skrip
   dijalankan (H3). INV-PAY-05 (WARN) melaporkan pesanan berjurnal tanpa jadwal tersimpan.
5. **Alokasi pembayaran `open_lines`** dihitung saat baca (pembayaran ≤ posisi, tanpa nota tertangguh; dulu yang menunjuk
   baris `plan_line_seq`, lalu jatuh tempo tertua) — satu aturan dengan `baris_tagihan`. `recompute_paid` tetap menulis
   `paid_amount` tersimpan (layar rencana, denda).
6. **`customer_balances` tambahan field**: `cash_term_open_amount` (bagian belum dikirim pesanan tunai — perlu agar status
   kredit (b) tetap melewati pesanan tunai sepenuhnya), `open_orders_count`, `fingerprint` (sidik dokumen), `stale_reason`.
   `overdue_amount`/`oldest_due_date` hanya pesanan berpiutang (bukan tunai tanpa DP), sejalan umur piutang.
7. **`get` juga menyegarkan bila sidik dokumen berubah** (banyak pesanan, waktu ubah/status/terbayar, banyak jurnal
   pengakuan, kwitansi, nota denda) — jaring pengaman untuk penulis yang belum berkait (mis. pesanan baru belum
   dikonfirmasi yang ikut piutang berjalan di pemeriksaan kredit); "basi" dibandingkan `overdue_as_of ≠ hari ini` (bukan `<`).
   INV-BAL-01 membandingkan baris yang sidiknya masih sama (angka diubah langsung = FAIL, U12); baris yang sidiknya sudah
   berbeda dilaporkan WARN "saldo basi" (disegarkan saat dibaca), supaya alur yang membuat pesanan tanpa membaca saldo
   tidak memerahkan gate.
8. **Daftar tagih** (`collection_worklist`) tetap per pesanan dari baris jadwal (`baris_tagihan`), bukan dari saldo
   tersimpan (saldo tidak punya rincian per pesanan); `outstanding` = sisa baris berjatuh tempo (uang muka ikut ditagih).
9. **Titipan di status kredit**: dari saldo tersimpan — cermin `customers.deposit_balance` hanya pada PT pemilik data
   pelanggan; kartu kredit yang disaring PT lain kini menunjukkan 0 (dulu titipan penuh).
10. **Kait refresh tambahan** di luar tabel spesifikasi: simpan/batal kwitansi (pembayaran terakhir, giro), deposit,
    saldo kredit, rencana cicilan baru. `refresh(customer_id)` tanpa PT = semua PT pelanggan (bentuk panggilan PM-T3).
11. **`giro_outstanding` sudah diisi**: kwitansi giro (`payment_method_code`/`method` `giro`/`cek`) tidak batal yang belum
    `bank_verified` (PM-T3 sudah ada di HEAD; spesifikasi menulis 0 sampai PM-T3).
12. **Skrip**: `--dry-run` = bawaan (tanpa bendera pun baca-saja); `--apply` untuk menulis.
13. Glosarium: §9.18 di W; di HEAD tujuan `84744dc` menjadi **§9.20** (§9.18 PY-T2, §9.19 TX-T2).

## Asumsi

- `ASUMSI:` (spesifikasi) pesanan bertermin tunai tanpa DP diberi baris per surat jalan (`net_days` 0); kode bayar per baris
  hanya untuk pesanan berpiutang (pesanan tunai dibayar dengan kode tingkat pesanan PM-T2).
- `ASUMSI:` (spesifikasi) nilai baris surat jalan = Σ debit akun `penjualan.piutang` (pemetaan PT) jurnal `shipment_revenue`
  bernomor itu; surat jalan yang jurnalnya gagal belum punya baris sampai jurnalnya diulang (ulang dari panel memanggil kait).
- `ASUMSI:` (`00` §4.1) uang muka jatuh tempo = tanggal buku `confirmed_at` (cadangan `created_at`); "sudah dikonfirmasi" =
  `confirmed_at` ada atau status di luar draft/reserved/waiting_stock/waiting_approval/approved/mati.
- `ASUMSI:` DP dihitung dari grand total pesanan (tagihan tambahan nota debit punya barisnya sendiri); surat jalan penutup
  (pesanan `shipped`/`done`) = Σ pengakuan − uang muka − baris surat jalan sebelumnya.
- `ASUMSI:` baris rencana `manual` selalu ikut pada posisi `as_of` (rencana menggantikan seluruh jadwal pesanan); baris
  term hanya yang `billed_at` ≤ `as_of`.
- `ASUMSI:` (spesifikasi) sebab terjelaskan INV-BAL-02 = jurnal `manual`/`manual_void` ("jurnal tanpa pesanan") dan
  `finance_case` ("kasus keuangan"); "jalur lama per pesanan" tidak menimbulkan selisih (pengakuan jurnal lama = Σ debit
  piutang pesanan) sehingga tidak dihitung terpisah — selisih lain = FAIL.
- `ASUMSI:` pengakuan piutang `recognized_total`/`ar_delivered` hanya akun piutang (tanpa akun kas jurnal lama tunai) —
  supaya sama dengan saldo akun piutang (INV-BAL-02).

## Yang perlu direview / titik henti

- **RISIKO status kredit (pemilik, sebelum (b) dipasang ke PT nyata — H3)**: daftar pelanggan yang statusnya berubah
  dibuat `python scripts/build_billing_schedule.py --dry-run` (baca-saja; integrator di data acuan:
  `docker compose -f docker-compose.dev.yml exec backend python /app/scripts/build_billing_schedule.py --dry-run`).
  Di uji B: pelanggan DP50 belum bayar uang muka berubah `active → blocked` (telat 17 hari sejak konfirmasi). Pesanan CBD
  (DP 100 %) yang belum dibayar kini telat sejak konfirmasi — kemungkinan sumber perubahan terbesar di data nyata.
- **H3**: `build_billing_schedule.py --apply` pada data nyata = keputusan pemilik. Di data acuan boleh (integrator) —
  menghilangkan WARN INV-PAY-05.
- **H6**: indeks `uq_plan_live_doc` gagal dibuat bila ada pesanan dengan rencana `active` + `closed` sekaligus (kueri pencari
  di `finder`); tidak ada penggabungan data oleh skrip.
- Lapis A belum dijalankan: `test_bp_CRT2_jadwal_bersamaan.py` (U17), `test_bp_PK14_indeks_wajib.py` (31 indeks),
  `test_g3_phase03.py` (impor). INV-BAL-01/02 dan INV-PAY-05 belum dijalankan di data acuan (bisa memerah bila data acuan
  punya jurnal piutang di luar daftar sebab).
- `seed_payment_plans` (dua salinan seed) menghapus SEMUA `payment_plans` sebelum membuat contoh — jadwal term hasil kait
  saat seed ikut terhapus (WARN INV-PAY-05 sampai skrip/kait berikutnya); tidak diubah (perilaku seed lama).
- Denda dari jadwal = CR-T4; komposisi eksposur/titipan = CR-T3 (`get_manual` menjaga perilaku denda & selisih bayar).
- Belum diuji jalan di peramban (U18).

## Penggabungan

- Keadaan (a): `$S/CR-T2_a_state/` (basis `5f193df`, 30 berkas, `tests_mem_a.txt`) dan `$S/CR-T2_a_merged/` (HEAD saat (a)
  selesai = `5f193df` = basis → isi sama, tanpa bentrok).
- (b) mula-mula digabung ke `5f193df` (42 berkas disalin; `tests_mem` T **1949/2/2**, jest **962**). Sebelum melapor HEAD
  bergerak ke **`5edef21`** (`[PY-T2]`) → digabung ulang tiga arah (basis `5f193df`) di worktree tujuan:

| Berkas | Bentrok | Keputusan |
|---|---|---|
| `backend/indexes.py` | tekstual (`ID_INDEX_COLLECTIONS`: PY-T2 `hr_compensation_history`, `hr_employee_assignments` vs CR-T2 `customer_balances`) | keduanya |
| `backend/tests_mem/test_PK14_indeks_wajib.py` | tekstual (`PYT2_INDEKS` vs `CRT2_INDEKS`; rumus jumlah) | keduanya; jumlah `… + PYT1_INDEKS + PYT2_INDEKS + CRT2_INDEKS` |
| `backend/tests/test_bp_PK14_indeks_wajib.py` (lapis A) | tekstual (komentar) + makna (keduanya menulis `== 31`) | kedua komentar; jumlah **29 + 2 (PY-T2) + 2 (CR-T2) = 33** |
| `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | tekstual (dua §9.18) | §9.18 = PY-T2, bagian CR-T2 = **§9.19** |
| `CODEBASE_MAP.md` | tekstual | dibangkitkan ulang (`gen_codebase_map.py`) |
| `ENTITY_REGISTRY.md`, `memory/PRD.md`, `backend/server.py`, `services/scheduler_service.py`, `scripts/verify_data_integrity.py` (lapisan `hr_comp` + `balance`), `scripts/verify_contract.py` | bersih | tiga arah, kedua perilaku ada (diperiksa) |

- `configKeyIndex.json` tidak berubah; `access_modules.py` tidak disentuh (fixture akses tidak perlu). PM-T4 dan KM-T2 belum
  masuk HEAD saat menggabung — berkas bersama yang mungkin bentrok bila masuk lebih dulu: `ar_receipt_service.py` (kait
  saldo di `_adjust_deposit`, akhir simpan & batal kwitansi), `ar_allocation_service.py` (`_segarkan`), `customer_service.py`,
  `indexes.py`, `PRD.md`, `KN_32`.
- Sesudahnya HEAD bergerak ke `8ac7059` (`82ef1bb` warna lencana PY-T2 + STATUS; dua berkas di luar unit ini — T dipindah
  tanpa gabung ulang; `tests_mem` 1967/2/2, jest 970), lalu ke **`84744dc`** (`[TX-T2]` (a) `38b5c9b` + (b)) → digabung ulang
  tiga arah (basis `5f193df`); bentrok yang sama dengan PY-T2 di `indexes.py` dan dua uji PK-14 (TX-T2 tidak menyentuhnya →
  hasil penyelesaian sebelumnya dipakai), ditambah:

| Berkas | Bentrok | Keputusan |
|---|---|---|
| `backend/services/shipment_service.py` | tekstual (sesudah jurnal surat jalan: TX-T2 `draft_for_shipment` vs CR-T2 `after_shipment_journal`) | keduanya: draf faktur TX-T2 lalu baris jadwal CR-T2 (keduanya tahan-gagal, tidak saling bergantung) |
| `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | tekstual (§9.18 PY-T2, §9.19 TX-T2) | bagian CR-T2 = **§9.20** |
| `backend/services/credit_note_service.py`, `services/scheduler_service.py` (job `tax_draft_backfill` + `customer_balance_overdue`), `scripts/verify_data_integrity.py`, `ENTITY_REGISTRY.md`, `memory/PRD.md` | bersih | kedua perilaku ada (diperiksa); `CODEBASE_MAP.md` dibangkitkan ulang |

- Angka di T akhir (`84744dc`): `tests_mem` **1997 lulus / 2 dilewati / 2 xfail** (HEAD = 1997 − 25 = 1972, diturunkan; semua hijau, `bukti/CR-T2/T3_tests_mem.txt`); jest **977 lulus** (HEAD 972 + 5; 35 suite gagal dimuat sama, `T3_jest.txt`); penjaga statik = HEAD `84744dc` (`hitung_penjaga` sama
  persis; `bukti/CR-T2/penjaga_T3*.txt`); penjaga lain sama dengan baris di bawah (`verify_payment_vocab` 1821/0).
- Angka di T (`8ac7059`): `tests_mem` **1967 lulus / 2 dilewati / 2 xfail** (HEAD = 1967 − 25 uji CR-T2 = 1942, diturunkan;
  semua hijau); jest **970 lulus** (35 suite gagal dimuat sama, lingkungan; HEAD = 970 − 5 uji CR-T2 = 965, diturunkan); penjaga statik = HEAD (`hitung_penjaga` sama persis);
  `verify_role_gate_ui` 31/0; `verify_config_fallback` 158/0 (+`--entity` 158/0); `verify_payment_vocab` 1820/0;
  `verify_access_catalog_nav` 0; `verify_posting_coverage` 134/0 (+uji-diri); `verify_cash_single_door` 733/0 (+uji-diri);
  `verify_permission_checked` 606/0; `verify_detail_modal` 30/0; `verify_atomic_claim` 160/0 (+uji-diri 64; inventaris
  123 baris tanpa selisih); `verify_codebase_map` PASS; `audit_config_wiring --strict` hijau; `check_nav_map` PASS
  (`bukti/CR-T2/T2_*.txt`, `penjaga_T2*.txt`). Draf laporan + bukti hanya di W.

Status: implemented_pending_review.
