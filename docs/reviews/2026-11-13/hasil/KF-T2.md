# KF-T2 — Bereskan kunci pengaturan yang mati, ganda, dan tersembunyi

- Commit awal: `36b056e` (dikerjakan) · digabung di atas `693885f` (sesudah PR-T4, PR-T7)        - Commit akhir: `1dcb06c` (koreksi blueprint `69c7108`)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KF-05, KF-06, KP-13, KP-29 (bagian asumsi retur dan jadwal bayar antar-PT), KP-30 (spesifikasi
  `docs/blueprint/unit/KF-T2.md`)

## Cek ulang "Keadaan sekarang"

Spesifikasi dibaca pada `3132cc4`; dicek ulang pada `36b056e`. Gate `scripts/audit_config_wiring.py` tanpa database di
HEAD: **78 kunci, 7 DEAD, 2 HIDDEN, 2 editor ganda** — sama dengan spesifikasi; `--self-test` FAIL, `--strict` keluar 1.

| Butir | Hasil di `36b056e` |
|---|---|
| 7 kunci "mati" `returns.grade_price_factors.*` | Berlaku. `return_grade_impairment.py:19` (`grade_factors`, gabung `DEFAULT_FACTORS` baris 21); `return_policy_service.py:304` (`return_assumptions`); `audit_config_wiring.py:383` (`if len(leaf) < 3` di `hits`) |
| 2 kunci tanpa layar `interco_payment.*` | Berlaku. `interco_service.py:1284` (`payment_settings`), `:1035` (`allow_netting`) |
| 2 layar menulis lewat jalur lama | Berlaku. `ReturnAssumptionsPanel.jsx:36`, `IntercoPaymentSchedule.jsx:36` (`CutoffForm`); `routers/settings.py:65` (`update_settings`), `:19` (`SETTINGS_SECTIONS`) |
| 11 isian tidak ada di registry | Berlaku. `config_service.py:20` (`returns`), `:25` (`interco_payment`); `return_policy_service.py:294` (`RETURN_ASSUMPTION_DEFAULTS`) |
| `contra_bon.qty_tolerance_percent` aktif tetapi tidak dipakai | Berlaku. `config_catalog_contrabon.py:23`; `contra_bon_service.py:78` (dimuat), `:152` (komentar "tak dipakai lagi") |
| KP-13 `lot.number_format` | Berlaku. `lot_service.py:133`; `config_catalog_ops.py:160`; pembaca hanya `config_simulator.py:315` |
| KP-30 akun bank dua tempat | Berlaku. `bank_recon_service.py:86/91/92`; `gl_mapping_registry.py:40/42` |
| 3 rujukan pemakai salah | Berlaku. `config_catalog_case.py:21,31` (`sla_of`; yang ada `finance_case_service.py:97` `sla_hours_of`); `config_catalog_ai.py:95` (bergeser dari 88; `ask`; yang ada `ai_chat_service.py:157` `chat_events`) |
| KF-06 10 baris cadangan | Berlaku semua; baris bergeser: `config_service.py:309/314` (`compute_tax`), `:679/680` (`compute_order_pricing`), `:788` (`get_allocation_policy`), `ar_aging_service.py:77`, `sales_force_service.py:259/269`, `so_approvals.py:227`, `roll_service.py:1081`, `approval_matrix_service.py:79/202` (dari 69/217). **Ditemukan tambahan:** `roll_service.py:1161` (`_explain_allocation`, cadangan `"fefo"` yang sama) |
| `hr.feature_toggles.pph21` | Tidak berlaku (sesuai spesifikasi); pembaca bergeser ke `hr_payroll_service.py:303`, cadangan `True` = bawaan |
| Catatan baru (tidak di spesifikasi) | `config_health.report()` di HEAD: **4 STALE** — `returns.evidence_required_submit/approve/inspect/settle` (pembaca merangkai kunci `f"returns.evidence_required_{s}"`, jadi berkas pemakai tidak menyebut kuncinya). Sudah STALE juga pada `3132cc4`. U11 (`broken == []`) menuntut ini dibereskan — lihat Menyimpang |
| Unit selesai yang menyentuh kunci ini | KF-T1: `BUKA_SEMENTARA` memuat `returns`, `interco_payment` (dicabut di sini). KF-T6/KP-T3/PK-46/PR-T2/PR-T3: tidak mengubah 16 kunci unit ini |

## KF-05 / KF-06 / KP-13 / KP-29 / KP-30

- Berlaku di HEAD: ya, semua (tabel di atas; bukti merah di bawah).
- Akar masalah: aturan yang dibaca mesin disimpan di tiga tempat berbeda — dokumen `system_settings` (lewat form
  sendiri `PUT /api/settings`), registry Pusat Pengaturan, dan Pemetaan Akun — sehingga satu aturan punya dua editor,
  tanpa riwayat, atau tanpa layar; registry juga memuat kunci yang tidak dibaca, dan cadangan kode menyimpang dari
  bawaan registry.
- Perubahan perilaku (sebelum → sesudah):
  - **11 kunci baru** di registry (tabel spesifikasi; `scopes` global+PT, `sensitif_baca=False`, `risk="medium"`):
    `returns.customer_window_days|supplier_window_days|supplier_reminder_days|bill_first|grade_price_factors`
    (`config_catalog_ops.py`, izin `sales_return.policy`) dan
    `interco_payment.allow_netting|require_full_payment|cutoff_day|payment_day|basis|reminder_days`
    (`config_catalog_interco.py`, izin `entity.update`). Jalur simpan = jalur dokumen lama, jadi nilai lama terbaca
    sebagai lapisan "Global (pengaturan lama)" tanpa migrasi (U4).
  - `return_assumptions(entity_id)` dan `interco_service.payment_settings(entity_id)` membaca kunci itu lewat
    `config_resolver.value_of` (lapisan PT berlaku; bentuk jawaban tetap; `cutoff_day`/`payment_day` 0 dan `basis` ""
    → `None`). `grade_factors` memakai tabel apa adanya (tanpa `DEFAULT_FACTORS`).
  - `PUT /api/settings` → **410** "Pengaturan kini disimpan lewat Pusat Pengaturan." tanpa menulis (izin lama
    `entity.update`/`sales_return.policy` tetap diperiksa lebih dulu). `GET` tetap.
  - `GET /api/settings/effective` tanpa `settings.view`: bagian `returns`/`interco_payment` kini dibuka per kunci
    (`sensitif_baca=False`), bukan lewat `BUKA_SEMENTARA` (`returns.evidence_required_*` dan kunci retur lain yang
    sensitif tidak lagi ikut terkirim ke pembaca biasa).
  - **5 kunci `not_used`** dengan alasan tabel spesifikasi: `contra_bon.qty_tolerance_percent` (label tanpa "(Lama)";
    dicabut dari `contra_bon_service.CFG_KEYS`), `lot.number_format` (`simulate` dikosongkan; juga dicabut dari kartu
    tautan di Stok › Lot), `bank.holding|charge|interest_account_code`. Simpan → 400 berisi alasannya (U9).
  - Rekonsiliasi bank (`bank_recon_service.load_cfg`): `holding_acc` = `account_for("kas_bank.titipan_dana")`,
    `charge_acc` = `account_for("kas_bank.beban_bank")`, `interest_acc` = `account_for("kas_bank.pendapatan_bunga")` per
    PT. Entri Pemetaan Akun baru `kas_bank.pendapatan_bunga` (bawaan `4-9000`, `remap=False` — lihat Menyimpang).
  - `config_registry.default_of(key)` baru; 10 baris tabel KF-06 (+1 tambahan `_explain_allocation`) memakai bawaan
    registry sebagai cadangan: PPN 12 % + DPP nilai lain, diskon penjualan mati (pembelian hidup), wajib transfer
    antar-PT, denda 2 %/bulan, ambang komisi 10 / faktor 0,5, validasi SO tidak wajib, lot FIFO, ambang Direksi PO
    Custom Rp50 jt.
  - `consumers` `case.sla_hours`, `case.sla_hours_high` → `finance_case_service.py:sla_hours_of`;
    `ai.route_threshold_pct` → `ai_chat_service.py:chat_events`.
  - Layar: Penjualan › Retur › Kebijakan Retur — bagian **Batas retur umum** = kartu Pusat Pengaturan dikunci ke lima
    kunci `returns.*` (`ReturnGeneralLimits.jsx`); tanpa akses baca (403 atau tidak satu pun kunci terbaca) → satu baris
    hanya-baca "Batas retur umum: pelanggan {n} hari sejak surat jalan · pemasok {m} hari sejak barang diterima.".
    `ReturnAssumptionsPanel.jsx` dihapus. Keuangan › Antar-PT › Jadwal Bayar — `CutoffForm` diganti bagian **Aturan
    jadwal bayar** (kartu `interco_payment.*`), hanya tampil bagi yang lolos baca, tombol simpan mengikuti `can_edit`;
    jadwal dimuat ulang sesudah simpan; kalimat status mengikuti aturan yang dipakai mesin (dulu "netting
    dinonaktifkan" ditulis tetap).
- Data: tidak ada koleksi/field baru. Skrip `scripts/migrate_kft2_akun_bank.py` (bawaan = `--dry-run`, hanya cetak;
  `--apply` menulis lewat `gl_mapping_service.set_mapping`, alasan "Pindahan dari Pusat Pengaturan (KF-T2)"; argumen
  tak dikenal/bertentangan → keluar 2 sebelum menyentuh basis data). **Tidak dijalankan terhadap basis data mana pun di
  luar database tiruan** (instruksi + H3); keluaran di lingkungan B: `bukti/KF-T2/skrip_migrasi_lingkungan_b.log`.
- Berkas berubah:

| Berkas | Isi |
|---|---|
| `backend/config_registry.py` | `default_of(key)` (salinan bawaan registry) |
| `backend/config_catalog_ops.py` | 5 kunci `returns.*` (blok `KF-T2` di akhir); `lot.number_format` → `not_used`, tanpa `simulate` |
| `backend/config_catalog_interco.py` | 6 kunci `interco_payment.*` (blok `KF-T2` di akhir) |
| `backend/config_catalog_contrabon.py`, `config_catalog_bank.py` | 4 kunci → `not_used` + alasan; label kontrabon tanpa "(Lama)" |
| `backend/config_catalog_case.py`, `config_catalog_ai.py` | `consumers` tiga kunci |
| `backend/services/return_policy_service.py`, `return_grade_impairment.py`, `interco_service.py` | Pembaca lewat resolver; teks petunjuk jadwal |
| `backend/services/return_evidence_service.py` | `KUNCI_BUKTI` — empat kunci ditulis utuh (U11) |
| `backend/services/bank_recon_service.py`, `gl_mapping_registry.py` | Akun bank dari Pemetaan Akun; entri `kas_bank.pendapatan_bunga` |
| `backend/services/contra_bon_service.py` | Kunci `not_used` dicabut dari `CFG_KEYS` |
| `backend/services/config_service.py` | `BUKA_SEMENTARA` tanpa `returns`/`interco_payment`; `_reg_default`; 5 cadangan; `DEFAULT_GLOBAL_SETTINGS` (tanpa `returns.grade_price_factors`; "belum diatur" antar-PT = 0/"") |
| `backend/services/ar_aging_service.py`, `sales_force_service.py`, `so_approvals.py`, `roll_service.py`, `approval_matrix_service.py` | Cadangan = `default_of` (baris ber-komentar `KF-T2`) |
| `backend/routers/settings.py` | `PUT /api/settings` → 410; `SETTINGS_SECTIONS`/`SECTION_PERMISSION` dan impor tak terpakai dibuang |
| `backend/access_modules.py` | `VIEW_RESOURCE_OVERRIDES["settings-cfg-finance"] = ["settings", "entity"]` (satu baris sesudah baris KF-T6) |
| `scripts/migrate_kft2_akun_bank.py` | Baru — skrip pindahan (lapor / `--apply`) |
| `scripts/audit/b3b_api_probe.py` | Uji "PUT /settings lama" dialihkan ke `PUT /api/config/values` (`inventory.min_cut_qty` −5) |
| `frontend/src/features/sales/ReturnGeneralLimits.jsx` | Baru — bagian Batas retur umum |
| `frontend/src/features/sales/ReturnPoliciesView.jsx`, `AppViewRouter.jsx` | Pasang bagian baru; teruskan `selectedEntity`/`entities` |
| `frontend/src/features/sales/ReturnAssumptionsPanel.jsx` | Dihapus |
| `frontend/src/features/finance/interco/IntercoPaymentSchedule.jsx`, `IntercoView.jsx` | Aturan jadwal bayar dari Pusat Pengaturan; kalimat status dari konfigurasi |
| `frontend/src/features/inventory/lots/LotsView.jsx` | "Format nomor lot" dicabut dari kartu tautan pengaturan |
| `frontend/src/config/__tests__/fixtures/access_builtin_fixture.json` | Ditulis ulang `backend/tests/fe03_access_fixture.py` (+`entity` di `settings-cfg-finance`) |
| `backend/tests_mem/test_KFT2_kunci_pengaturan.py`, `test_KFT2_migrasi_akun_bank.py` | Baru — U2–U14 (+U10b, U13b) |
| `backend/tests_mem/test_KFT1_izin_pengaturan.py` | `KFT2_KUNCI = 11` (U04 katalog), `KFT2_TIDAK_DIPAKAI = 4` (U02) dengan alasan |
| `backend/tests/test_bp_KFT2_kunci_pengaturan.py` | Baru — pelengkap lapis A (lulus di MongoDB asli) |
| `backend/tests/test_p13_audit.py`, `test_lanjutan_sched_returns_interco.py`, `test_audit_bagian_iii.py`, `test_role01_matrix_defaults.py` | Pemanggil `PUT /api/settings` dialihkan ke `PUT /api/config/values` / harapan 410 (komentar `KF-T2`) |
| `frontend/src/features/__tests__/kft2KunciPengaturan.test.js` | Baru — uji komponen dua layar + U14 |
| `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`, `CODEBASE_MAP.md` | Baris KF-T2; istilah "Batas retur umum", "Aturan jadwal bayar"; peta dibangkitkan ulang |

- Commit: `1dcb06c`; koreksi blueprint terpisah `69c7108` (usulan 1, 2, 3, 5, 6, 7 di bawah; usulan 4 tidak diterapkan —
  itu perubahan aturan pindahan, bukan salah uji, jadi tetap tercatat sebagai penyimpangan untuk diputuskan peninjau).
- Pengujian: lihat tabel uji di bawah.
- Bukti UI: belum diuji jalan di peramban (U15).
- Fixture disiapkan langsung vs proses bisnis dijalankan: fixture sisip langsung = U4 (`returns.customer_window_days: 14`
  di dokumen grup) dan U13 (baris `config_values` `bank.charge_account_code` lapisan `ent_ksc`); lewat API = U3, U5,
  U6, U8, U9, U12 (akun 6-8100 dan pemetaan), U13b (pemetaan Kanda).
- Dampak pada modul terkait: rekonsiliasi bank memakai Pemetaan Akun per PT (di data bawaan akunnya sama: 2-1950,
  6-8000, 4-9000); `verify_data_integrity.py` INV-BNK-03 kini menjumlah akun titipan pemetaan (sama dengan jurnal);
  kartu `returns.*` dan `interco_payment.*` juga tampil di Pengaturan › Penjualan / Keuangan & Pajak dan "Semua
  pengaturan" (mesin yang sama, bukan editor kedua).
- Keterbatasan / yang belum diuji: U15 (uji jalan peramban).
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_KFT2_kunci_pengaturan.py` + `test_KFT2_migrasi_akun_bank.py` (lingkungan B). Merah = kedua berkas
uji dijalankan di salinan `git archive 36b056e` (kode lama utuh, skrip belum ada): **14 gagal, 1 lulus (U7)**
(`bukti/KF-T2/tests_mem_KFT2_merah_kode_lama.log`). Hijau di kode baru: 15/15 (+14 uji KF-T1).

| ID | Lapis | Merah di lama (sebab) | Hasil |
|---|---|---|---|
| U1 | statik | ya — 9 kunci bermasalah + 2 editor ganda; `--strict` 1; `--self-test` FAIL | Lulus — 71 kunci: OK 70, NOT_USED 1, DEAD/HIDDEN/ORPHAN_UI 0, editor ganda 0; `--strict` 0; `--self-test` PASS (`bukti/KF-T2/audit_config_wiring_*`) |
| U2 | B | ya (kunci belum terdaftar) | Lulus — 11 kunci (grup, tipe, bawaan, min/max/satuan, izin, lapisan, `sensitif_baca`, risiko, label ≤ 45); `row_shape` map; pilihan `basis`; 5 `not_used` + alasan persis; label kontrabon tanpa "(Lama)"; `simulate` lot kosong |
| U3 | B | ya (404 tidak ada di registry) | Lulus — `ent_ksc` 30, `ent_kanda` 21, riwayat 1 baris |
| U4 | B | ya (kunci tidak tampil di `/config/effective`) | Lulus — 14; `source_layer == "legacy_global"` |
| U5 | B | ya (404) | Lulus — `grade_factors("")["B"] == 50.0`; `compute(…)["amount"] == 100000.0` |
| U6 | B | ya (404) | Lulus — `ent_ksc` True, `ent_kanda` False |
| U7 | B | **tidak** (perilaku dipertahankan) | Lulus — `None`/`None`/`None`/3/True |
| U8 | B | ya (200, dokumen grup tertimpa) | Lulus — 410 + pesan; dokumen grup identik |
| U9 | B | ya (200, tersimpan) | Lulus — 5 × 400 berisi alasan tabel |
| U10 | B | ya (`items_discount_total` 10,0; True; 0) | Lulus — 0,0; False; 20.000 |
| U10b (tambahan) | B | ya (PPN 0 tanpa DPP nilai lain; …) | Lulus — 7 baris lain tabel KF-06 + kalimat penjelasan alokasi |
| U11 | B | ya (4 STALE `returns.evidence_required_*`; `sla_of`/`ask` tidak ada) | Lulus — `broken == []`; tiga kunci OK dan fungsinya ada (`ast`) |
| U12 | B | ya (`6-8000` untuk `ent_ksc`) | Lulus — `6-8100` / `6-8000` |
| U13 | B | ya (skrip tidak ada) | Lulus — lapor 1 selisih, tidak menulis; tulis → `account_for(…, "ent_ksc") == "6-8100"` (+ jejak alasan); ulang 0; argumen salah → 2 |
| U13b (tambahan) | B | ya (skrip tidak ada) | Lulus — pemetaan Kanda yang sudah diubah Admin tidak ditimpa kembali ke 6-8000 |
| U14 | statik | ya (2 berkas) | Lulus — 0 hasil (tests_mem + jest) |
| U15 | layar (uji jalan) | — | **Belum diuji jalan** (tanpa peramban/backend di sesi ini). Pengganti: uji komponen `kft2KunciPengaturan.test.js` 5/5 (kode lama: suite gagal dimuat — `ReturnGeneralLimits` belum ada). Riwayat perubahan tercatat dibuktikan U3 (`/config/history`) |

Uji pelengkap lain: `docs/audit/konfigurasi-peran-2026-11-13/bukti/t1_config.py` (standar §2.4.1) di worktree — 11 kunci
baru lulus putaran (tulis grup → terbaca 3 jalur; lapisan PT → hanya PT itu; cabut; nilai tak sah 400; pulihkan); 5 kunci
`not_used` ditolak; seluruh registry: tulis grup 348/348, tulis PT 301/301, `not_used` ditolak 14/14, galat 0
(`bukti/KF-T2/t1_config_16_kunci.log`). Statik lapis A tanpa database (`--noconftest`):
`test_phase3_p2_settings_groups.py` + `test_fe03_access_catalog.py` 8 lulus.

Lapis A (**lulus 5/5** di lingkungan A — MongoDB 7 asli, backend `1dcb06c`, data acuan): `backend/tests/test_bp_KFT2_kunci_pengaturan.py` (registry, 410 tanpa tulis,
lapisan PT `ent_ksc`, entri pemetaan bunga, skrip `--dry-run` tidak menulis + mencetak keluaran untuk laporan). Uji lama
yang disesuaikan (belum dijalankan di A): `test_p13_audit.py::TestSettingsAudit` (jejak audit `config_value_changed`),
`test_lanjutan_sched_returns_interco.py::test_ln024_klx03_config_per_payer_entity`,
`test_audit_bagian_iii.py::TestE45SettingsScope` (410), `test_role01_matrix_defaults.py::test_asumsi_retur_…`.

`backend/tests_mem` seluruhnya: **379 lulus / 2 dilewati / 3 xfail → 394 lulus / 2 dilewati / 3 xfail** (15 uji baru;
`bukti/KF-T2/tests_mem_seluruh_sebelum_sesudah.log`) di salinan kerja. Sesudah digabung di atas PR-T4 + PR-T7:
**400 → 415 lulus** / 2 / 3. Jest (`src/config/__tests__`, `kft2KunciPengaturan`, `prt7TombolIzin`): 120/120.

**Keluaran `--dry-run` di data acuan** (diwajibkan spesifikasi; `bukti/KF-T2/skrip_migrasi_mode_lapor_data_acuan.log`,
sesudah `restore_demo`, hanya baca):

```
== KF-T2 akun rekonsiliasi bank → Pemetaan Akun — mode lapor (lapisan grup + 3 PT) ==
Selisih akun jurnal: 0
(mode lapor; jalankan dengan --apply untuk menulis)
```

Di data acuan tidak ada lapisan yang akun jurnalnya berubah karena pembaca dialihkan ke Pemetaan Akun.

## Penggabungan dengan PR-T4 dan PR-T7

Berkas yang juga berubah di cabang sejak `36b056e`: `access_modules.py`, `sales_force_service.py` (tergabung otomatis),
`test_KFT1_izin_pengaturan.py` (konflik angka: konstanta PR-T4 `PRT4_TIDAK_DIPAKAI` dan KF-T2 `KFT2_TIDAK_DIPAKAI` keduanya
dikurangkan di U02; `KFT2_KUNCI` di U04), glosarium dan `PRD.md` (otomatis). Fixture akses frontend dan
`CODEBASE_MAP.md` dibangkitkan ulang.

Jest (lingkungan lokal; folder uji sendiri): `kft2KunciPengaturan` 5/5 (lama: gagal dimuat). Seluruh suite: lama 35 suite
gagal dimuat / 63 lulus / 442 uji → baru 35 / 64 / 447; daftar suite gagal identik (cmdk/radix tidak termuat).
`phase3Settings` + `decisionsD3` dengan tiruan KNSelect hanya di folder uji: 21/21 lama dan baru. `phase4R3` (LotsView),
`serverAccessReach`, `roleReach`, `phase4R5` lulus.

## Bukti

`bukti/KF-T2/`: `tests_mem_KFT2_merah_kode_lama.log`, `tests_mem_KFT2_hijau_kode_baru.log`,
`tests_mem_seluruh_sebelum_sesudah.log`, `audit_config_wiring_sebelum_sesudah.log`, `…_strict_…`, `…_selftest_…`,
`audit_config_wiring_antara_tabel_di_dua_tempat.log` (keadaan antara, lihat Menyimpang), `config_health_sebelum_sesudah.log`,
`penjaga_statik_sebelum_sesudah.log`, `penjaga_kode_keluar.log`, `t1_config_16_kunci.log`, `jest_KFT2_merah_kode_lama.log`,
`jest_KFT2_hijau_kode_baru.log`, `jest_seluruh_sebelum_sesudah.log`, `skrip_migrasi_lingkungan_b.log`.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `1dcb06c`), sesudah `restore_demo` (data acuan; tiga skrip seed
yang sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Menjadi hijau (keduanya mode): `config_wiring (INV-CFG-01/04, satu sumber kebenaran)` dan `config_wiring SELF-TEST` —
gate wiring dengan database kini bersih.

Penjaga statik dari worktree (tanpa database), sebelum → sesudah: `audit_config_wiring` 9 kunci bermasalah + 2 editor
ganda → bersih, `--strict` 1 → 0, `--self-test` FAIL → PASS; `config_health` 4 STALE → 0; `verify_auth_coverage` 28 → 28
(isi sama); `verify_access_catalog_nav` 0 → 0; `verify_ui_standard` 26 → 26 (isi sama, hex 16842 → 16836);
`verify_custom_modals`, `verify_codebase_map`, `verify_money_idempotency`, `verify_error_notice`,
`verify_knselect_contract`, `verify_modal_dismiss`, `verify_blocking_dialogs` lulus → lulus; `verify_page_tabs` 1 → 1;
`audit_i18n_id --strict` 113 → 112 (temuan "Tanggal invoice" pindah dari layar ke pilihan registry — teks spesifikasi;
"refund" hilang bersama panel lama).

## Menyimpang dari blueprint

- **U1 butuh satu perubahan di luar tabel "Server":** mendaftarkan `returns.grade_price_factors` saja membuat 7 daun
  `returns.grade_price_factors.A … BS` di `DEFAULT_GLOBAL_SETTINGS` menjadi **ORPHAN_UI** (kartu ada, tetapi `hits`
  tidak mencari daun < 3 huruf) — dibuktikan `bukti/KF-T2/audit_config_wiring_antara_tabel_di_dua_tempat.log`. Tabel itu
  dibuang dari `DEFAULT_GLOBAL_SETTINGS["returns"]`; bawaannya kini hanya di registry. Penjaga tidak diubah. Akibat:
  dokumen grup baru tidak lagi dibenih dengan tabel itu (dibaca dari bawaan registry); `GET /api/settings/effective`
  hanya memuat tabel itu bila tersimpan (satu-satunya pembaca layar, panel lama, dihapus).
- **U11 butuh perbaikan di luar daftar "3 rujukan":** 4 STALE `returns.evidence_required_*` (sudah ada pada `3132cc4`).
  Pembacanya ditulis dengan kunci utuh (`return_evidence_service.KUNCI_BUKTI`); `consumers` tidak diubah.
- **Label ≤ 45 huruf (standar §2.1 menang, unit tidak menulis "menyimpang dari standar")** — empat label spesifikasi
  terlalu panjang; "(hari)" dibuang karena satuan "hari" tampil di kartu: "Batas retur pelanggan sejak surat jalan",
  "Batas retur ke pemasok sejak barang diterima", "Ingatkan sebelum batas retur pemasok habis", "Ingatkan sebelum
  tanggal bayar antar-PT". U15 ("Batas retur pelanggan…") tetap cocok.
- **Aturan skrip pindahan akun bank:** spesifikasi membandingkan "nilai efektif kunci lama" dengan "kode Pemetaan Akun".
  Karena `gl_mapping_service.remap_lines` mengalihkan kode bawaan (6-8000 → pemetaan `kas_bank.beban_bank`, 4-9000 →
  `penjualan.pendapatan_lain`), perbandingan harfiah akan **mengembalikan** pemetaan yang sudah diubah Admin bila kunci
  lama masih bawaan, dan memindah `bank.holding_account_code` padahal jurnal titipan tidak pernah memakainya (akun tetap
  2-1950 yang dialihkan pemetaan). Skrip membandingkan **akun jurnal** hari ini vs sesudah pengalihan pembaca (satu
  tingkat `remap`, sama dengan mesin), menghitung lapisan grup lebih dulu, dan hanya melaporkan kunci titipan (tampilan
  ringkasan). U13 tetap terpenuhi; U13b membuktikan kasus yang dilindungi. Ini yang membuat ASUMSI spesifikasi ("tidak
  mengubah akun mana pun yang dipakai jurnal") benar.
- `kas_bank.pendapatan_bunga` `remap=False`: kode bawaannya sama dengan `penjualan.pendapatan_lain` (ber-`remap`), dan
  `REMAP_BY_DEFAULT` mewajibkan kode bawaan unik. Rekonsiliasi memanggilnya eksplisit (`account_for`).
- U13 di modul sendiri (`test_KFT2_migrasi_akun_bank.py`): U12 di modul utama sudah memetakan `kas_bank.beban_bank`
  untuk `ent_ksc`, sehingga "keadaan lama" U13 tidak bisa dibuat di basis data yang sama.
- Tambahan kecil di luar tabel, searah tujuan unit: `roll_service._explain_allocation` (cadangan "fefo" yang sama, U10b);
  `DEFAULT_GLOBAL_SETTINGS["interco_payment"]` "belum diatur" ditulis 0/0/"" (= bawaan registry; arti sama, `payment_settings`
  memetakan ke `None`); kartu tautan Stok › Lot tidak lagi menyebut "Format nomor lot"; kalimat status Jadwal Bayar
  mengikuti konfigurasi (L6); teks petunjuk server "Atur di form di bawah" → "Atur di bagian Aturan jadwal bayar di bawah".
- `VIEW_RESOURCE_OVERRIDES["settings-cfg-finance"]` + `entity`: aturan KF-T1 (U14 `test_KFT1`) — tab kelompok
  "antar-entitas" terbuka bagi pemegang izin pengubah kuncinya. Peran bawaan yang memegang `entity` (Admin, Manajer) sudah
  memegang `settings`, jadi jangkauan menu peran bawaan tidak berubah (fixture akses: satu baris).
- Pemanggil `PUT /api/settings` lebih banyak dari dua yang disebut spesifikasi: juga
  `backend/tests/test_lanjutan_sched_returns_interco.py`, `test_audit_bagian_iii.py`, `test_role01_matrix_defaults.py`
  (dialihkan) dan `tests/archive/test_epic4_incentive_poc.py` (arsip di luar `backend/`/`scripts/`/`frontend/src`; tidak
  diubah, akan menerima 410).
- `CODEBASE_MAP.md` dibangkitkan ulang; generatornya tidak mendaftar berkas layar maupun skrip satu per satu, jadi
  "hapus `ReturnAssumptionsPanel.jsx`, tambah `scripts/migrate_kft2_akun_bank.py`" tidak berbekas di peta (sunting tangan
  dilarang).

## Usulan koreksi blueprint (teks pengganti persis)

1. Tabel "Kunci baru", kolom label — ganti empat label:
   `Batas retur pelanggan sejak surat jalan` · `Batas retur ke pemasok sejak barang diterima` ·
   `Ingatkan sebelum batas retur pemasok habis` · `Ingatkan sebelum tanggal bayar antar-PT`.
2. Tabel "Server", baris baru: "| `config_service.DEFAULT_GLOBAL_SETTINGS` | `returns.grade_price_factors` dibuang (bawaan
   hanya di registry); tanpa ini 7 daun tabel menjadi ORPHAN_UI di gate (daun < 3 huruf tidak dicari pembacanya) |".
3. "Keadaan sekarang", baris baru: "| 4 rujukan pemakai basi `returns.evidence_required_*` | Pembaca merangkai kunci
   (`f\"returns.evidence_required_{s}\"`), jadi `config_health` menilai STALE dan U11 (`broken == []`) merah |
   `backend/services/return_evidence_service.py:15` (`policy`) |"; tabel "Server", baris baru:
   "| `return_evidence_service.policy` | Kunci per tahap ditulis utuh |".
4. Bagian "Data" KP-30, kalimat aturan diganti: "untuk lapisan grup lalu tiap PT, bila **akun jurnal** hari ini (nilai
   efektif `bank.charge_account_code` / `bank.interest_account_code` sesudah pengalihan `remap_lines`) berbeda dari akun
   jurnal sesudah pembaca dialihkan (kode Pemetaan Akun yang berlaku untuk lapisan itu, termasuk rencana lapisan grup,
   sesudah `remap_lines`), panggil `gl_mapping_service.set_mapping(<kunci pemetaan>, <entity_id atau None>, <akun jurnal
   hari ini>, \"Pindahan dari Pusat Pengaturan (KF-T2)\", aktor sistem)`. `bank.holding_account_code` hanya dilaporkan
   (jurnal titipan memakai akun tetap 2-1950 yang sudah dialihkan Pemetaan Akun)."; tabel "Server" baris
   `gl_mapping_registry` ditambah "`remap=False` (kode bawaan sama dengan `penjualan.pendapatan_lain`)".
5. Baris `PUT /api/settings` — "(diketahui: …)" diganti: "(diketahui: `backend/tests/test_p13_audit.py`,
   `backend/tests/test_lanjutan_sched_returns_interco.py`, `backend/tests/test_audit_bagian_iii.py`,
   `backend/tests/test_role01_matrix_defaults.py`, `scripts/audit/b3b_api_probe.py`, dua layar)".
6. Langkah kerja 1: "U2–U13 merah" → "U2–U13 merah kecuali U7 (bawaan yang sama dengan perilaku hari ini)".
7. "Dokumen ikut berubah": "`CODEBASE_MAP.md` (hapus …, tambah …)" → "`CODEBASE_MAP.md` (dibangkitkan ulang
   `scripts/gen_codebase_map.py`)".

## Asumsi / keraguan

- `ASUMSI` spesifikasi dipakai: wewenang jadwal bayar antar-PT = `entity.update`; `4-9000` bawaan entri bunga.
- Teks alasan `contra_bon.qty_tolerance_percent` menyebut "Toleransi jumlah tagihan pemasok" (spesifikasi), sedangkan label
  kunci tujuannya masih "Toleransi qty tagihan supplier" — teks kartu menjadi urusan KF-T4.
- Simulator `lot_number` tetap ada di katalog simulator (`config_simulator.py`); hanya tautannya dari kunci yang dicabut
  (spesifikasi: "`simulate` dikosongkan").
- Data nyata yang `system_settings.interco_payment.cutoff_day` bernilai `null` (benih lama) tetap terbaca `None`
  (lapisan lama menang atas bawaan 0); kartu menampilkan isian kosong sampai disimpan.

## Titik henti

- **H3** — `scripts/migrate_kft2_akun_bank.py --apply` di data nyata = keputusan pemilik, dan harus sebelum kode KF-T2
  dipasang di sana (RISIKO spesifikasi). Keluaran `--dry-run` pada data acuan diambil saat penggabungan (lihat Uji
  penerimaan): selisih akun jurnal 0. `--apply` tidak dijalankan di data mana pun selain database tiruan uji.

## Persinggungan dengan unit lain

- KP-T4 (berjalan paralel): `approval_matrix_service.py` (impor `default_of` + dua baris cadangan
  `approval.po_custom_direksi_min`) dan `config_service.py` (helper `_reg_default`, `BUKA_SEMENTARA`,
  `DEFAULT_GLOBAL_SETTINGS`, `compute_tax`, `compute_order_pricing`, `get_allocation_policy`) — semua baris ber-komentar
  `KF-T2`, tidak menyentuh `approval_pool`/`evaluate_approval`/`config_catalog_approval_matrix.py`. Bila KP-T4 memindah
  `po_custom_direksi_min` ke tabel kebijakan, dua cadangan itu ikut pindah.
- PR-T4/PR-T7: `access_modules.py` (satu baris baru sesudah baris KF-T6), `AppViewRouter.jsx` (satu baris
  `return-policies`), `IntercoView.jsx` (satu baris), `LotsView.jsx` (satu butir kartu tautan + komentar).
- KF-T3 (`role_home.*`, `tax.efaktur_enabled`) tidak disentuh. KF-T7 (cadangan `RETURN_ASSUMPTION_DEFAULTS`,
  `DEFAULT_FACTORS`) — konstanta dibiarkan; `grade_factors` sudah tidak memakai `DEFAULT_FACTORS`.

## Hambatan lingkungan

- Tanpa peramban dan tanpa backend :8001 di sesi ini: U15, lapis A, dan `gate.sh` belum dijalankan.
- `/app` di mesin ini menunjuk repo utama, bukan worktree: `audit_config_wiring.py` dan `config_health` dijalankan lewat
  pemuat yang mengganti jalurnya ke worktree (berkas penjaga tidak diubah); U11 mengarahkan `config_health.BACKEND` ke
  salinan kerja lewat `monkeypatch`.
- Jest lokal: cmdk/radix tidak termuat; suite lama yang memuat `KNSelect` asli diberi tiruan hanya di folder uji.

## Yang perlu direview

- Aturan "akun jurnal" skrip pindahan (Menyimpang + usulan koreksi 4), termasuk catatan "akun pemetaan dialihkan lagi oleh
  kebutuhan lain; periksa manual" (rantai `remap` dua tingkat yang tidak bisa dibetulkan dengan menulis kode yang sama).
- Pembuangan `returns.grade_price_factors` dari `DEFAULT_GLOBAL_SETTINGS` sebagai jalan U1 (penjaga tidak diubah).
  Risiko sisa: gate `config_wiring` **dengan database** membaca dokumen pengaturan per PT; bila suatu PT menyimpan tabel
  harga per grade sendiri (proyeksi `PUT /api/config/values` lapisan PT), daun `A … BS` di dokumen itu akan dinilai
  ORPHAN_UI — kelas temuan yang sama dengan daun tabel lain (lihat self-test [7] penjaga); perbaikannya di penjaga
  (KF-T8), bukan di unit ini.
- Bunga bank ber-bawaan 4-9000 tetap dialihkan `remap_lines` ke pemetaan `penjualan.pendapatan_lain` selama pemetaan
  `kas_bank.pendapatan_bunga` masih bawaan (perilaku hari ini dipertahankan); memetakan bunga ke akun lain memutus
  pengalihan itu.

Status: implemented_pending_review.
