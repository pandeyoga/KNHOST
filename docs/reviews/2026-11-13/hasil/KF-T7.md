# KF-T7 — Nilai bisnis yang ditulis mati menjadi pengaturan

- Commit awal: `303e709` (dikerjakan) · digabung di atas `890291e` (sesudah PK-36, KP-T2, PR-T6)        - Commit akhir: `885daca` · perbaikan sesudah gate `64ecb19`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-27, KP-28, CR-03 (spesifikasi `docs/blueprint/unit/KF-T7.md`; Lampiran A butir #1–9, #45–54,
  #64–69)
- Risiko sedang → satu serah-terima (langkah 1–8 utuh, belum di-commit per kelompok butir — lihat Menyimpang 1).

## Cek ulang "Keadaan sekarang" (spesifikasi dicek di `3132cc4`; dicek ulang di `303e709`)

| # | Hasil di `303e709` |
|---|---|
| 1, 2 | Berlaku. `ar_aging_service.py:35` (`OVERDUE_BLOCK_DAYS`), dipakai `:97` (`_credit_status`); `customer_service.py:16`, dipakai `:254` (`compute_customer_credit`) |
| 3, 4 | Berlaku. `ar_aging_service.py:34`; `customer_service.py:15` (`WARNING_RATIO`) — **tambahan:** dipakai juga `customer_service.py:297` (`check_credit_for_order`, proyeksi pesanan baru) |
| 5 | Berlaku, bergeser: `routers/sales_orders.py:572` (`expires`); teks job `scheduler_service.py:112` |
| 6 | Berlaku. `customer_service.py:22` (`MAX_GROUP_SALES`); pemakai `apply_group_sales_rule` ← `normalize_sales_team` (`customer_service`, `sales_order_helpers`) ← `routers/customers.py` (buat/ubah), `routers/admin.py` (impor), `routers/sales_orders.py` (buat pesanan) |
| 7 | **Tidak berlaku — ditutup KP-T4.** `special_order_service.py:23` hanya komentar "`APPROVAL_THRESHOLD` … DIHAPUS"; `routers/special_orders.py:288` membaca `approval_policy_service.required_levels("special_order", PT, nilai)` (Aturan Persetujuan per PT, baris tabel kebijakan). Bukti: U7 hijau di kode lama dan baru |
| 8 | Berlaku. `special_order_phase2.py:27` (`DEFAULT_MARGIN_PCT`), `:52` (`default_margin_pct`, membaca `system_settings{scope:"special_order"}` tanpa penulis) |
| 9 | Berlaku. `special_order_phase2.py:280` (`MULTI_ITEM_MIN`); `is_multi_item` dipanggil `special_order_phase2.py` ×2 dan `routers/special_orders.py:1354/1366` |
| 45, 46 | Berlaku. `notification_service.py:16` (`LOW_STOCK_THRESHOLD`); `stock_availability.py:22` (`LOW_STOCK_QTY`) — **tambahan:** dipakai juga `stock_figures.py:285/316` (`stock_state`, `figures_for`) dan label `LOW_STOCK_LABEL`. **Beda:** `stock_availability` tidak memakai titik pesan ulang barang (definisi tunggal "Stok rendah" K-04), hanya angka 100 |
| 47 | Berlaku. `notification_service.py:216` (`soon`). **Tambahan:** jendela 24 jam yang sama di `routers/sales_orders_extra.py:242` (`get_orders_stats`, kartu "Reservasi hampir habis") |
| 48 | Berlaku. `stock_analytics_service.py:39/40` |
| 49 | Berlaku. `roll_service.py:238`, dipakai `:553` (`generate_rolls_from_balances`: stok lama tanpa rincian roll dipecah saat rincian roll dibuat pertama kali — label spesifikasi sesuai) |
| 50 | Berlaku. `supplier_dn_profile_service.py:14/15`; pemakai `active_locale`/`_decide_locale` + `goods_receipt_ocr_service.py:310` |
| 51 | Berlaku. `sample_sale_service.py:38/39`; **tambahan pemakai:** `cutting_service.py:259` (`change_catalogue_soft`), `routers/sample_orders.py:62` (`sample_kinds`); teks galat "kurang dari 3 yard" (`sample_sale_service.py:140`) |
| 52 | Berlaku, bergeser: `qc_inspection_service.py:60/61`; pemakai `inspection_service.py:1083/1218/1250`; **tambahan:** salinan rumus di layar `IntervalDefectGrid.jsx:5` (`IV = 15`, minimum 10) dan `InspectSheetGrid.jsx:16` |
| 53 | Berlaku. `return_grade_impairment.py:15` (`DEFAULT_FACTORS` — sejak KF-T2 hanya didefinisikan, tidak dipakai) |
| 54 | Berlaku. `return_policy_service.py:294` (`RETURN_ASSUMPTION_DEFAULTS`, tertimpa seluruhnya oleh lima kunci registry KF-T2); `return_disposition_service.py:101` (`or 21`), `:470` (`or 3`) |
| 64 | Berlaku, bergeser: `gl_service.py:3378`; pemakai `:3419/3423/3424` (`inventory_reconciliation`), `:3634/3642` (`inventory_drift_explain`) |
| 65 | Berlaku, bergeser: `closing_service.py:40`; pemakai `:290` (`preview`), `:315` (`check_suspense_gate`) |
| 66 | Berlaku, bergeser: `inspection_service.py:123` (pemakai `finish`, `reopen`, `release_hold`, `reject_hold`, `meta`); `putaway_arrival_service.py:37` (`close_remaining`). `gate_review_actions.py:27` **tidak disentuh** (H7) |
| 67 | Berlaku. `routers/auth.py:28/29` (`_register_failure`) |
| 68 | Berlaku. `core_utils.py:12`; `dependencies.py:15` (`session_expiry`), `:57` (perpanjangan); `routers/auth.py:151` (`max_age`); `bootstrap.py:1855` (`ensure_auth_indexes`) |
| 69 | Berlaku. `esign_service.py:20/21` (`create_request`, `verify_and_sign`) |

## KP-27 / KP-28 / CR-03

- Berlaku di HEAD: ya, kecuali butir #7 (ditutup KP-T4 — bukti U7). 19/20 uji penerimaan merah di kode lama.
- Akar masalah: angka kebijakan ditulis sebagai konstanta modul (beberapa dalam dua salinan, satu di layar juga),
  sehingga hanya pengembang yang bisa mengubahnya dan dua salinan bisa berbeda.
- Perubahan perilaku (sebelum → sesudah): **tidak ada perilaku yang berubah saat dipasang** (bawaan = nilai hari ini);
  sesudahnya Admin (izin `settings.manage`) bisa mengubah 26 angka di Pusat Pengaturan, per PT bila kolom `scopes`
  memuat `entity`. Tabel akhir "konstanta → kunci → pemakai":

  | # | Konstanta lama | Kunci (lapisan) | Pemakai (pembaca kunci → penerima nilai) |
  |---|---|---|---|
  | 1–4 | `OVERDUE_BLOCK_DAYS` ×2, `WARNING_RATIO` ×2 | `ar.overdue_block_days`, `ar.credit_warning_pct` (grup, PT) | `customer_service.credit_thresholds` (satu-satunya pembaca, PT pelanggan) → `credit_status` (rumus tunggal) ← `compute_customer_credit`, `check_credit_for_order`, `ar_aging_service._credit_status`/`aging_report`; daftar (`home_service`, `sales_force_service`, umur piutang) membaca sekali per PT |
  | 5 | `timedelta(days=3)` | `sales.reservation_days` (grup, PT) | `inventory_service.reservation_expires_at` ← `routers/sales_orders.py` (buat pesanan); teks job "(menurut pengaturan masa reservasi)" |
  | 6 | `MAX_GROUP_SALES` | `sales.group_sales_max_members` (grup, PT) | `customer_service.group_sales_max` → `normalize_sales_team(..., max_members=)` ← `routers/customers.py`, `routers/admin.py`, `routers/sales_orders.py` (`sales_order_helpers`) |
  | 7 | (`APPROVAL_THRESHOLD`, dihapus KP-T4) | — tidak didaftarkan | Aturan Persetujuan `special_order` per PT (`approval_policy_service.required_levels`) |
  | 8 | `DEFAULT_MARGIN_PCT` + dokumen `system_settings{scope:"special_order"}` | `sales.special_order_margin_pct` (grup, PT) | `special_order_phase2.default_margin_pct(entity_id)` (PT pesanan); migrasi sekali `migrasi_margin_lama` (penanda `__migrations__.kft7_margin_pesanan_khusus`, alasan "Pindahan dari penyimpanan lama", dokumen lama tidak dihapus) |
  | 9 | `MULTI_ITEM_MIN` | `sales.special_order_multi_item_min` (grup) | `special_order_phase2.multi_item_min` → `is_multi_item(od, min_items)` |
  | 45, 46 | `LOW_STOCK_THRESHOLD`, `LOW_STOCK_QTY` | `inventory.low_stock_default_qty` (grup) | `notification_service.generate_system_notifications` (titik pesan ulang barang, bila kosong angka ini); `stock_availability.low_stock_qty` → `is_low_stock(av, batas)`, `low_stock_summary` (`threshold`, label), `stock_figures.figures_for`/rincian stok (`low_stock_qty`, `stock_state`) |
  | 47 | `timedelta(hours=24)` | `notif.reservation_expiry_warn_hours` (grup) | `notification_service.generate_system_notifications`; `routers/sales_orders_extra.get_orders_stats` (`expiring_soon_count` + `expiring_soon_hours` baru) |
  | 48 | `TREND_WINDOW_DAYS`, `TREND_BAND` | `inventory.stock_analytics.trend_window_days`, `…trend_band_pct` (grup, PT) | `stock_analytics_service.trend_rules` → `classify_velocity(trend_days, trend_band)`, `trend_of(.., band)` |
  | 49 | `MAX_AVAILABLE_ROLL_LEN` | `inventory.split_roll_max_length` (grup) | `roll_service.generate_rolls_from_balances` |
  | 50 | `MIN_CONFIRMED`, `LOCALE_SHARE` | `receiving.dn_profile_min_confirmed`, `…min_share_pct` (grup) | `supplier_dn_profile_service.profile_rules` → `active_locale(prof, min_confirmed)`, `_decide_locale(votes, min_share)`, `public(prof, rules)`; `goods_receipt_ocr_service.map_extraction` |
  | 51 | `CATALOGUE_BASE_QTY`, `CATALOGUE_SOFT_QTY` | `sales.sample_catalogue_base_qty`, `…soft_qty` (grup, PT) | `sample_sale_service.catalogue_qty` ← `catalogue_templates_for`, `build_catalogue`, `routers/sample_orders.sample_kinds`; `cutting_service.change_catalogue_soft` menjumlah komponen tersimpan |
  | 52 | `INTERVAL_YARD`, `MIN_INTERVALS` | `qc.inspection_interval_yard`, `qc.inspection_min_points` (grup, PT) | `qc_inspection_service.interval_rules` (PT pemilik roll / PT retur) → `interval_count`, `normalize_interval_defects`; `inspection_service.meta()["policy"]["inspection_points"]` → layar `IntervalDefectGrid`, `InspectSheetGrid` |
  | 53, 54 | `DEFAULT_FACTORS`, `RETURN_ASSUMPTION_DEFAULTS`, `or 21`, `or 3` | `returns.*` (sudah ada sejak KF-T2) | `return_policy_service.return_assumptions` (lima kunci saja); `return_disposition_service._hari` (tidak ada → `default_of`) |
  | 64 | `ROUNDING_TOLERANCE` | `finance.rounding_tolerance_rupiah` (grup, risiko tinggi) | `gl_service.inventory_reconciliation`, `gl_service.inventory_drift_explain` (label "Selisihnya paling banyak Rp … — pembulatan sen") |
  | 65 | `SUSPENSE_OVERRIDE_MIN_LEN` | `periode.suspense_reason_min_chars` (grup) | `closing_service.suspense_reason_min_chars` ← `preview`, `check_suspense_gate` |
  | 66 | `MIN_REASON`, `MIN_CLOSE_REASON` | `qc.hold_reason_min_chars`, `putaway.close_reason_min_chars` (grup) | `inspection_service.min_reason_len` ← `finish`, `reopen`, `release_hold`, `reject_hold`, `meta`; `putaway_arrival_service.close_remaining` |
  | 67 | `MAX_LOGIN_ATTEMPTS`, `LOCKOUT_MINUTES` | `keamanan.maks_salah_sandi`, `keamanan.lama_kunci_menit` (grup, risiko tinggi) | `routers/auth._register_failure` |
  | 68 | `SESSION_TTL_HOURS` | `keamanan.umur_sesi_jam` (grup, risiko tinggi) | `routers/auth.login` (kedaluwarsa + `max_age` kuki + `sessions.ttl_hours`); `bootstrap.ensure_auth_indexes`; `dependencies.session_expiry(hours)`, `session_ttl_hours(session)` (perpanjangan memakai umur sesi itu sendiri) |
  | 69 | `OTP_TTL_MIN`, `MAX_ATTEMPTS` | `esign.otp_ttl_minutes`, `esign.max_attempts` (grup) | `esign_service.create_request`, `esign_service.verify_and_sign` |

  Semua pembaca memakai `services/nilai_pengaturan.py:nilai(key, entity_id)` (baru): `value_of` + galat/kosong →
  `config_registry.default_of` (`02` §2.2). Kelompok baru **"Keamanan akun & sesi"** (`keamanan`, sub-judul "Salah
  sandi & lama sesi") tampil sebagai chip di layar Integrasi & Sistem › AI & Tampilan (`configGroupViews.js`
  `settings-cfg-system: ["sistem", "keamanan"]`). Sub-judul baru: "Peringatan & blokir kredit"
  (Pembayaran pelanggan), "Pesanan khusus & katalog sample" (Penjualan & harga), "Tanda tangan elektronik"
  (Persetujuan, pengingat & dokumen). `verify_config_text`: 428 kunci · 14 kelompok · **0** pelanggaran.
- Data: tidak ada koleksi baru. Satu migrasi sekali jalan (#8, berjalan saat backend menyala, pola KF-T6). Isian baru
  `sessions.ttl_hours` (umur sesi saat dibuat; sesi lama tanpa isian = 24 jam) — `ENTITY_REGISTRY.md` diperbarui.
- Berkas berubah:
  - Pengaturan: `backend/config_catalog_nilai.py` (baru, 26 kunci, blok KF-T7), `backend/config_registry.py` (blok
    KF-T7: kelompok `keamanan` + tiga sub-judul; impor katalog), `backend/services/nilai_pengaturan.py` (baru).
  - Server: `services/customer_service.py`, `ar_aging_service.py`, `home_service.py`, `sales_force_service.py`,
    `sales_order_helpers.py`, `inventory_service.py`, `scheduler_service.py`, `special_order_phase2.py`,
    `notification_service.py`, `stock_availability.py`, `stock_figures.py`, `stock_analytics_service.py`,
    `roll_service.py`, `supplier_dn_profile_service.py`, `goods_receipt_ocr_service.py`, `sample_sale_service.py`,
    `cutting_service.py`, `qc_inspection_service.py`, `inspection_service.py`, `return_grade_impairment.py`,
    `return_policy_service.py`, `return_disposition_service.py`, `gl_service.py`, `closing_service.py`,
    `putaway_arrival_service.py`, `esign_service.py`; `routers/sales_orders.py`, `sales_orders_extra.py`,
    `customers.py`, `admin.py`, `special_orders.py`, `sample_orders.py`, `auth.py`; `core_utils.py`, `dependencies.py`,
    `bootstrap.py`.
  - Layar: `features/inspections/IntervalDefectGrid.jsx`, `InspectSheetGrid.jsx`, `InspectLineModal.jsx`
    (jarak/jumlah titik dari `policy.inspection_points`), `features/orders/OrderDashboard.jsx` ("Berakhir dalam <
    {jam} jam"), `features/settings/config/configGroupViews.js`, `configKeyIndex.json` (dibangkitkan).
  - Uji baru: `backend/tests_mem/test_KFT7_nilai_tertulis.py` (20), `backend/tests/test_bp_KFT7_nilai_tertulis.py`
    (lapis A, ditulis), `frontend/src/features/__tests__/kft7NilaiPengaturan.test.js` (4).
  - Uji lama disesuaikan (perilaku/tanda tangan sengaja diubah, berkomentar `KF-T7`):
    `tests_mem/test_KFT1_izin_pengaturan.py` (`KFT7_KUNCI = 26` di U02/U04), `tests_mem/test_KFT4_registry.py`
    (kelompok ke-14, tema toleransi +1 `finance.rounding_tolerance_rupiah`, Pembayaran pelanggan +2, peta layar),
    `features/__tests__/phase3Settings.test.js` (14 kelompok), lapis A `tests/test_uat26_d2_decisions.py`
    (`trend_of`/`classify_velocity`/`is_low_stock` berparameter), `tests/test_grn_phase5.py`
    (`active_locale`/`_decide_locale` berparameter).
  - Dokumen: `memory/PRD.md`, `ENTITY_REGISTRY.md` (`sessions`), `CODEBASE_MAP.md` (dibangkitkan).
    `KN_32` tidak diubah — label baru tidak memakai istilah yang menggantikan istilah lain ("sample", bukan "sampel").
- Commit: belum (instruksi).
- Pengujian: tabel di bawah.
- Bukti UI: **belum diuji jalan di peramban** — pengganti: uji komponen jest 4/4 (merah 3/4 di kode lama).
- Fixture disiapkan langsung vs proses bisnis: pengaturan selalu lewat API (`PUT /api/config/values`, `values/reset`,
  `values/clear`); masuk lewat `POST /api/auth/login` dengan akun `POST /api/users`. Fixture sisip: pelanggan + pesanan
  + surat jalan (U3–U5), barang + saldo stok (U9), dokumen lama margin (U8), baris Aturan Persetujuan (U7), pesanan
  ber-reservasi (T4). Status kredit, umur piutang, masa reservasi, titik inspeksi, katalog, tren, format surat jalan
  diuji lewat fungsi layanan (bukan HTTP).
- Dampak pada modul terkait: status kredit (kartu pelanggan, Customer 360, beranda sales/manajer, pemeriksaan kredit
  pesanan, umur piutang) kini satu rumus; pesan "Group sales maksimal {n} orang (1 PIC + {n−1} co-sales)."; galat
  katalog/inspeksi menyebut angka yang berlaku; layar inspeksi dan server memakai jarak titik yang sama.
- Keterbatasan / belum teruji: uji jalan peramban; perilaku #49
  (pemecah roll) dan #66 putaway hanya diuji putaran `t1_config` + statik (jalurnya hanya hidup saat roll pertama kali
  dibangkitkan / saat menutup sisa PA).
- Status: implemented_pending_review.

## Uji penerimaan

Merah: kode `303e709` utuh (`git archive`), berkas uji baru disalin: **19/20 gagal** (`bukti/KF-T7/merah_kode_lama.log`,
sebab `merah_kode_lama_sebab.log`: kunci "tidak ada di registry" 404, fungsi pembaca belum ada, konstanta masih ada).
U7 lulus di kode lama — memang bukti "tidak berlaku". Jest baru di kode lama **3/4 gagal** (yang lulus = uji cadangan
perilaku lama).

| ID | Lapis | Merah di kode lama (sebab) | Hasil kode baru |
|---|---|---|---|
| U1 | B | ya — kunci tidak terdaftar | Lulus — 26 kunci, bawaan = kolom "Nilai", `settings.manage`, lapisan & risiko sesuai tabel; `approval.special_order_min_amount` tidak ada (Usulan koreksi 1) |
| U2 | statik | ya — 28 pasangan konstanta/berkas tersisa | Lulus — 0 nama konstanta sebagai kode (tokenize; komentar diabaikan) di berkas jangkar + pemakai; 20 nama khas 0 di seluruh `backend/` (tanpa uji, `gate_review_actions.py` dikecualikan H7); literal `timedelta(days=3)`, "(3 hari)", `timedelta(hours=24)`, `or 21)`, `or 3)` hilang |
| U3 | B | ya — `credit_thresholds` belum ada | Lulus — awal keduanya "warning" (10 ≤ 14); KSC=7 → KSC "blocked", KANDA "warning"; dicabut → "warning" |
| U4 | B | ya — kunci 404 | Lulus — "active" (7 jt < 8 jt) → 60 % "warning" (7 jt ≥ 6 jt) di kartu & umur piutang; pemeriksaan kredit pesanan "warning" → "ok" sesudah dicabut |
| U5 | B | ya | Lulus — 7 → "blocked", 30 → "warning", kedua pembaca sama; keduanya memanggil `credit_thresholds` |
| U6 | B | ya — fungsi pembantu belum ada | Lulus — KSC sekarang + 5 hari, KANDA + 3 hari; deskripsi job "(menurut pengaturan masa reservasi)" |
| U7 | B | **tidak** (sudah ditutup KP-T4) | Lulus — tidak ada `APPROVAL_THRESHOLD`; Aturan Persetujuan KSC mulai 5 jt / KANDA mulai 10 jt → 8 jt: KSC wajib, KANDA tidak; 12 jt: KANDA wajib (Usulan koreksi 2) |
| U8 | B | ya — `migrasi_margin_lama` belum ada | Lulus — tanpa dokumen 30.0; dokumen 999 (tidak sah) → tidak dipindah, penanda tidak dipasang, server tetap jalan; dokumen 25 → migrasi `{"ditulis": 1}` → 25.0 (juga KANDA), alasan "Pindahan dari penyimpanan lama"; jalan kedua 0; dokumen lama tetap; dokumen lama diubah → tetap 25 (tidak dibaca lagi) |
| U9 | B | ya — kunci 404 | Lulus — 60 < 100 diperingatkan; 50 → tidak; titik pesan ulang 80 tetap menang; "Stok rendah" `threshold` = 50 |
| U10 | B | ya — kunci 404 | Lulus — 3 kali salah → percobaan ke-4 (sandi benar) 429; U10b lama kunci 60 menit |
| U11 | B | ya — kunci 404 | Lulus — sesi baru ≈ sekarang + 2 jam, kuki `Max-Age=7200`; sesi sebelum perubahan tetap pada kedaluwarsanya walau dipakai (`/auth/me`) |
| U12 | B | ya — `interval_rules` belum ada | Lulus — KSC 20, KANDA 14; roll 90 yard 10 (minimum) |
| U13 | B | ya — kunci 404 | Lulus — tiga-tiganya 400 "… paling kecil …" |
| U14 | B | ya — kunci 404 | Lulus — 26 kunci: tulis grup → terbaca (`value_of` & `/effective`); PT → hanya PT itu; hanya-grup → lapisan PT 400; nilai tak sah 400; pulih ke bawaan |
| U15 | statik | ya | Lulus — `keamanan` tepat di `settings-cfg-system`; 26 kunci `config_health` OK (pemakai ada & menyebut kuncinya). `audit_config_wiring --strict` hijau (gate) ; uji jest `phase3Settings` (14 kelompok) lulus dengan tiruan KNSelect lokal |
| T1 (tambahan) | B | ya | Lulus — tim 3 orang: KSC=3 diterima (split 100 %), KANDA ditolak "maksimal 2 orang" |
| T2 (tambahan) | B | ya | Lulus — multi-barang 2 ≥ 2 → 3: tidak; katalog KSC 1,5/2 yard, KANDA 1/2 |
| T3 (tambahan) | B | ya | Lulus — pita tren KSC 20 % → "stabil", KANDA tetap 10 %; format surat jalan 5 terkonfirmasi → "unknown" |
| T4 (tambahan) | B | ya | Lulus — toleransi pembulatan 1 → 5; alasan tutup buku 5 → 8; alasan inspeksi di `meta` 15 → 20; reservasi 30 jam lagi: 24 jam → tanpa pemberitahuan, 48 jam → ada |
| Layar | jest | ya — 3/4 | Lulus 4/4 — `intervalCount` server-sama, label "20 interval × 10 yard", cadangan 15/10, kelompok `keamanan` di `settings-cfg-system` |
| Lapis A | A | — | **Lulus** di lingkungan A (backend `885daca`, data acuan): `backend/tests/test_bp_KFT7_nilai_tertulis.py` (kunci & kelompok di backend berjalan + kesehatan OK, sesi `ttl_hours`, katalog/stok rendah bawaan, penanda migrasi) |

`backend/tests_mem` seluruhnya: `303e709` **577 lulus / 2 dilewati / 3 xfail** → sesudah **597 lulus / 2 dilewati /
3 xfail** (+20 uji KF-T7; `bukti/KF-T7/tests_mem_sebelum.log`, `tests_mem_sesudah.log`).

Jest seluruh suite (`bukti/KF-T7/jest_seluruh.log`): lama 35 suite gagal dimuat / 75 lulus / **537** uji lulus → baru
35 / 76 / **541** uji lulus (+4); suite gagal dimuat identik (`@radix-ui`/`cmdk` tidak termuat — kendala lingkungan).
Lapis A yang disesuaikan: bagian murni `test_uat26_d2_decisions.py` 10 lulus / 1 gagal **sama dengan kode lama**
(`test_k05_registry_keys` menuntut kelompok lama `stok-satuan` — basi sejak KF-T4, bukan unit ini);
`test_grn_phase5.py::test_profile_locale_evidence_alias_and_items` mengimpor `/app/backend` (di mesin ini = repo
utama) — badan ujinya dijalankan terhadap kode salinan kerja: lulus.

## Bukti

`docs/reviews/2026-11-13/hasil/bukti/KF-T7/`: `merah_kode_lama.log`, `merah_kode_lama_sebab.log`,
`jest_merah_kode_lama.log`, `jest_seluruh.log`, `tests_mem_sebelum.log`, `tests_mem_sesudah.log`,
`penjaga_statik_sebelum_sesudah.log`, `penjaga_pengaturan.log`, `audit_config_wiring.log`.

## Penggabungan

Digabung di atas `890291e` (sesudah PK-36, KP-T2, PR-T6). Satu konflik di `test_KFT1_izin_pengaturan.py` (PK-36
`PK36_KUNCI` + KF-T7 `KFT7_KUNCI` — keduanya dipertahankan di U04); `dependencies.py`, `special_orders.py`,
`customer_service.py`, `gl_service.py`, `sales_order_helpers.py`, `ENTITY_REGISTRY.md`, `PRD.md` tergabung otomatis;
indeks kunci pengaturan dan `CODEBASE_MAP.md` dibangkitkan ulang. `tests_mem` **638 → 658 lulus** / 2 / 3; jest seluruhnya
555/555 (35 suite gagal dimuat karena `@radix-ui`). Lapis A: `test_bp_KFT7_nilai_tertulis.py` + `test_bp_KFT4_pengaturan_awam.py`
+ `test_uat26_d2_decisions.py` — 19 lulus, 5 dilewati (uji d2 butuh `DB_NAME=d2_audit_*`). Dua harapan lapis A disesuaikan:
daftar kelompok KF-T4 (lapis A) kini memuat `keamanan` (kelompok ke-14), dan `test_k05_registry_keys` memakai id kelompok
`stok` (KF-T4 menerjemahkan `stok-satuan`; uji ini sudah merah sejak KF-T4, dicatat agen).

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), sesudah `restore_demo` (data acuan; tiga skrip seed yang sama seperti garis
dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Jalan gate untuk dua unit yang digabung berturut-turut
(KF-T7 `885daca`, PK-37 `689ca70`·`a323bb0`):

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`a323bb0`) | `--quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| 1 (`a323bb0`) | `--ci` | 42 FAIL | 43 | **1** | 2 |
| 2 (`64ecb19`) | `--quick` | 14 FAIL | 16 | 0 | 2 |
| 2 (`64ecb19`) | `--ci` | 41 FAIL | 43 | 0 | 2 |

Yang lebih merah di jalan 1: **POC FASE E-4 master berlapis** — menuntut semua setelan `receiving.*` berlapis PT, sedangkan
KF-T7 (#50) mendaftarkan `receiving.dn_profile_min_confirmed` dan `receiving.dn_profile_min_share_pct` berlingkup global
sesuai spesifikasi (profil format angka surat jalan milik pemasok lintas PT; pembaca `profile_rules()` tanpa konteks PT).
Pengecualian beralasan `KFT7_GLOBAL_BY_DESIGN` (pola OCR/PPh 21) di `64ecb19`; POC 57/57.

Sebelum penggabungan, penjaga statik di lingkungan B (`hitung_penjaga.sh`): **sama persis** dengan `303e709`
(auth_coverage 28, ui_standard 23, i18n 109, create_modal 6, page_tabs 1, to_list_bound 6, entity_label 2, lainnya 0);
`verify_role_gate_ui` PASS (33 cek, 0); `audit_config_wiring --strict` hijau di HEAD dan sesudah (122 kunci
terdeklarasi, 105 OK, 17 NOT_USED, 0 HIDDEN/ORPHAN/DEAD); `verify_config_text` 0 + self-test hijau;
`gen_config_key_index --check` selaras; `verify_codebase_map` PASS. Tidak ada penjaga baru (spesifikasi tidak meminta).

## Menyimpang dari blueprint

1. **Satu serah-terima, bukan satu commit per kelompok butir** (langkah kerja 3): instruksi tidak meng-commit. Bagian
   per kelompok bisa dipisah saat integrasi menurut tabel "konstanta → kunci → pemakai".
2. **Butir #7 tidak didaftarkan** (`approval.special_order_min_amount`): KP-T4 sudah memindahkan keputusan "kapan
   pesanan khusus wajib disetujui" ke Aturan Persetujuan (baris tabel kebijakan per PT); kunci kedua akan menjadi sumber
   kebenaran ganda (`02` §5 D1). U1 = 26 kunci, U7 diganti uji "tidak berlaku" (Usulan koreksi 1–2).
3. **Kelompok `keamanan`**: label "Keamanan akun & sesi" (huruf kecil mengikuti 13 kelompok KF-T4, spesifikasi
   "Keamanan Akun & Sesi"), `order` 14 (spesifikasi 24 ditulis sebelum KF-T4 merapikan 23 → 13 kelompok), satu sub-judul
   "Salah sandi & lama sesi" (KF-T4 mewajibkan sub-judul).
4. **Sub-judul** (spesifikasi ditulis sebelum `section` wajib): kunci kredit → sub-judul baru "Peringatan & blokir
   kredit"; margin/multi-barang/katalog → baru "Pesanan khusus & katalog sample"; `esign.*` → baru "Tanda tangan
   elektronik" (alias `dokumen` akan menaruhnya di "Rujukan antar dokumen"); `notif.reservation_expiry_warn_hours` →
   "Kapan pengingat dikirim" (tempat kunci waktu pengingat KP-T7; alias `notifikasi` = "Pemberitahuan");
   `sales.reservation_days`/`group_sales_max_members` → "Alur pesanan"; stok → "Laris/lambat & pesan ulang" dan "Kerja
   gudang"; `receiving.dn_profile_*` → "Menghitung & menerima" (kelompok `penerimaan` spesifikasi); `qc.*` → "Inspeksi &
   grade"; pembukuan → "Mata uang & tutup buku". Semua ≤ 14 kunci per sub-judul.
5. **Label disesuaikan penjaga INV-CFG-TXT** (Usulan koreksi 3): tiga label spesifikasi > 45 huruf; "sampel" →
   "sample", "ambang" (dilarang di label) → "Stok dianggap menipis di bawah"; "Kesamaan format minimum (%)" →
   "Kesamaan format surat jalan minimum (%)" (jelas tanpa membaca kunci tetangga).
6. **`stock_availability` tidak memakai titik pesan ulang** (spesifikasi: "Ambang = titik pesan ulang barang, bila kosong
   …" untuk kedua berkas): "Stok rendah" papan stok/dasbor adalah definisi tunggal keputusan pemilik K-04 (satu angka
   untuk semua barang); menambahkan titik pesan ulang di sana mengubah perilaku saat dipasang. Kedua pembaca kini
   memakai SATU kunci; penjelasan kunci menulis keduanya apa adanya.
7. **Umur sesi dicatat di sesi (`ttl_hours`)**: memenuhi "sesi yang sudah ada tidak diubah" juga saat perpanjangan
   otomatis, dan `current_user` (tiap permintaan) tidak membaca pengaturan. Sesi tanpa isian (dibuat sebelum unit ini)
   = bawaan registry 24 jam — nilai yang berlaku saat sesi itu dibuat.
8. **Pemakai tambahan yang tidak disebut spesifikasi** ikut dialihkan supaya U2 dan "satu angka satu pemilik" terpenuhi:
   `check_credit_for_order` (#3–4), `stock_figures` (#46), `routers/sales_orders_extra.get_orders_stats` (#47, + isian
   `expiring_soon_hours` yang dipakai layar Pesanan), `cutting_service`/`routers/sample_orders` (#51), dan salinan
   rumus titik inspeksi di layar (`IntervalDefectGrid`, `InspectSheetGrid` — tanpa ini layar menerima titik yang
   ditolak server bila jaraknya diubah; nilai dikirim `inspection_service.meta()["policy"]["inspection_points"]`).
9. **`returns.supplier_reminder_days` = 0** di ringkasan Beranda PT pemasok (`desk_summary`): dulu `or 3` membaca 0
   sebagai 3; kini 0 = tanpa pengingat, sama dengan job pengingatnya dan penjelasan kuncinya.
10. **Pembaca bersama baru** `services/nilai_pengaturan.py` (galat baca → `default_of`) dan katalog baru
    `config_catalog_nilai.py` — dipilih agar perubahan di berkas bersama (`config_registry.py`, katalog lain) sekecil
    mungkin (dua blok ber-komentar KF-T7) karena unit lain bekerja paralel.

## Usulan koreksi blueprint (teks pengganti persis)

1. Uji U1, sel hasil: ganti "27 kunci tabel ada; bawaannya sama dengan kolom \"Nilai\" di \"Keadaan sekarang\"" dengan
   "26 kunci tabel ada (tanpa `approval.special_order_min_amount`, lihat #7); bawaannya sama dengan kolom \"Nilai\" di
   \"Keadaan sekarang\"". Di tabel "Pengaturan" hapus baris #7 dan tambahkan di bawah tabel: "Butir #7 tidak didaftarkan:
   KP-T4 menghapus `APPROVAL_THRESHOLD`; kapan pesanan khusus wajib disetujui = Aturan Persetujuan jenis `special_order`
   per PT." U14: "untuk 27 kunci" → "untuk 26 kunci".
2. Uji U7: ganti sel persiapan "—" dengan "Aturan Persetujuan pesanan khusus: `ent_ksc` jenjang 1 mulai Rp5.000.000,
   `ent_kanda` mulai Rp10.000.000", langkah dengan "`approval_policy_service.required_levels(\"special_order\", PT,
   nilai)` untuk 8.000.000 di kedua PT dan 12.000.000 di `ent_kanda`; cari `APPROVAL_THRESHOLD` di
   `special_order_service.py` dan `routers/special_orders.py`", hasil dengan "`ent_ksc` wajib, `ent_kanda` tidak; 12 jt
   `ent_kanda` wajib; 0 pemakaian konstanta (tidak berlaku — ditutup KP-T4)". Baris server `special_order_service`,
   `routers/special_orders.py` dihapus.
3. Tabel "Pengaturan", kolom label: `receiving.dn_profile_min_confirmed` "Surat jalan terkonfirmasi sebelum format dipakai
   otomatis" → "Pakai format angka sesudah surat jalan dicek"; `receiving.dn_profile_min_share_pct` "Kesamaan format
   minimum (%)" → "Kesamaan format surat jalan minimum (%)"; `periode.suspense_reason_min_chars` "Panjang minimum
   alasan melewati akun sementara" → "Panjang alasan melewati akun sementara"; `keamanan.maks_salah_sandi` "Salah sandi
   berturut-turut sebelum akun dikunci" → "Salah sandi berturut-turut sebelum dikunci"; `sales.sample_catalogue_base_qty`
   "Isi katalog sampel per warna (yard)" → "Isi katalog sample per warna (yard)"; `inventory.low_stock_default_qty`
   "Ambang stok menipis bila barang belum diatur" → "Stok dianggap menipis di bawah". Kalimat kelompok baru:
   `"label": "Keamanan Akun & Sesi", "order": 24` → `"label": "Keamanan akun & sesi", "order": 14` + `"sections":
   [{"id": "masuk", "label": "Salah sandi & lama sesi"}]`.
4. Baris server `notification_service, stock_availability`: ganti "Ambang = titik pesan ulang barang, bila kosong
   `inventory.low_stock_default_qty`" dengan "Pemberitahuan stok menipis: titik pesan ulang barang, bila kosong
   `inventory.low_stock_default_qty`. \"Stok rendah\" (`stock_availability`, K-04): `inventory.low_stock_default_qty`
   untuk semua barang (definisi K-04 tidak berubah)".

## Asumsi / keraguan

- `ASUMSI` spesifikasi dipakai: kunci keamanan, tanda tangan, stok menipis, profil surat jalan hanya lapisan grup;
  `ar.overdue_block_days` tanpa lapisan pelanggan (profil kredit CR-T1); PT ambang kredit = PT pelanggan.
- PT pemakai lain: masa reservasi & tim sales pesanan = PT pesanan; tim sales pelanggan = PT pelanggan (buat: PT isian /
  PT aktif); margin pesanan khusus = PT pesanan; titik inspeksi = PT pemilik roll (retur: PT retur); katalog = PT pesanan
  sample / PT aktif (`/sample-orders/kinds`); tren = PT saringan Analitik Stok.
- `gl_service.py` disentuh hanya pada toleransi pencocokan persediaan (bukan posting/jurnal) — tidak ada temuan
  `AUDIT_KEUANGAN_2026-11-13.md` yang menyangkut angka ini.
- `putaway_arrival_service.py` (perintah simpan) disentuh hanya pada panjang alasan menutup sisa PA — bukan logika
  gerbang (`gate_evaluator`/`rfid_*`); `gate_review_actions.py` tidak disentuh (H7).
- Sisa di layar (teks, nilai bawaan tetap benar selama angka tidak diubah; usul unit lanjutan): `CartPanel.jsx:161`
  "Reservasi 3 hari", `CatalogueCreateModal.jsx:53` "1 yard tiap warna tersedia + 2 yard satu warna soft", cadangan
  hitung lokal `OrderDashboard.jsx:72` (< 24 jam, hanya bila agregat server tidak ada), judul `navMeta.js`
  "AI & Tampilan · Sistem, AI & tampilan" hanya menyebut kelompok pertama.
- Sisa Lampiran A di luar unit ini (spesifikasi): #56 bawaan kebijakan makloon `contract_service`, #63 selang simpan
  posisi pelacakan.

## Titik henti

- **H3** — migrasi margin (#8) berjalan otomatis sekali saat backend menyala (spesifikasi; pola KF-T6) dan hanya menulis
  bila dokumen lama ada; nilai lama yang tidak sah (di luar 0–500 %) tidak dipindah, dicatat di log peringatan, dan
  penanda tidak dipasang (server tetap menyala). Kueri hanya-baca untuk pemilik sebelum memasang di data nyata (tidak dijalankan):
  `db.system_settings.find_one({scope: "special_order"}, {_id: 0, default_margin_pct: 1, updated_at: 1})`.
- **H7** — antrean gerbang RFID (`gate_review_actions.py:27` `MIN_REASON`) tidak disentuh.
