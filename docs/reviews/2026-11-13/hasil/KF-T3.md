# KF-T3 — Layar menampilkan nilai yang dipakai mesin; jadwal diaktifkan penjadwal

- Commit awal: `ccff778` (basis lokal sementara = `2d164c9` + KF-T2) · digabung di atas `0da3656` (sesudah KP-T4, KF-T5)        - Commit akhir: (a) `dbe1633` · (b) `9783875`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KF-04, KF-09, KF-10, KF-11, KP-11 (spesifikasi `docs/blueprint/unit/KF-T3.md`)
- Risiko tinggi → dua serah-terima (`00_ATURAN_EKSEKUSI.md` §8): (a) jalur baru + uji, pemakai lama belum disentuh;
  (b) pengalihan pemakai + pematian yang palsu + layar. Keduanya hijau; SHA belum ada (instruksi: jangan commit) —
  keadaan (a) disimpan utuh sebagai salinan berkas, daftar berkas (b) terpisah (lihat "Pembagian serah-terima").

## Cek ulang "Keadaan sekarang" (spesifikasi ditulis di `dca195b`; dicek di `ccff778`)

| Butir | Hasil di `ccff778` |
|---|---|
| KF-04 PT bukan PKP | Berlaku. `config_service.py:296` (`is_pkp`, dari 254); `config_resolver.py:286` (`value_of`, dari 276), `:291` (`resolve_group`, dari 281) tanpa keterangan penimpaan. Merah dibuktikan U1 |
| `allocation.allow_intercompany` dipaksa mati | Berlaku. `config_service.py:801` (`get_allocation_policy`, dari 539) |
| Master Grade `max_points` menang | Berlaku. `qc_inspection_service.py:105` (`grade_from_points`, sama) |
| KF-09 jadwal | Berlaku. `config_resolver.py:548` (`apply_due_values`, dari 530); `routers/config.py:216`, `:399` (dari 193/371); `scheduler_service.py:79` (`JOBS`) tanpa job; tidak ada pembatalan. Merah U5–U9 |
| KP-11 termin | Berlaku. `routers/sales_orders.py:383` (dari 355) membaca dokumen grup langsung |
| `inventory.default_uom` | Berlaku. `routers/products.py:116` tanpa PT |
| `notif.po_stage_stuck_days` / `notif.low_stock_division` | Berlaku. `notification_service.py:399` / `:195`, `entity_id` kosong |
| `receiving.*` | Berlaku. `receiving_uom_service.py:188/309/390/494` `get_settings()` tanpa PT |
| `uom.*` | Berlaku. `uom_rules_service.py:299` (`load_engine`, dari 303), `:415` (`check_variance`, dari 422); 12 panggilan di `services/` + `routers/` (+1 skrip) |
| `lot.*` saat QC | Berlaku. `qc_inspection_service.py:234` |
| 0 diganti diam-diam | Berlaku. `payment_plan_service.py:78` (`or 1`), `finance_case_service.py:85` (`or 3`) |
| `role_home.*` | **Sudah ditangani PR-T4**: empat kunci `not_used` di `config_catalog_core.py:936` (dari 921) dengan alasan "Diatur per peran di Peran & Hak Akses › Halaman awal" (halaman awal kini sifat peran). Tidak dihidupkan lagi; alasan PR-T4 dipertahankan — lihat Usulan koreksi 1 |
| `tax.efaktur_enabled` | Berlaku. `config_catalog_core.py:48` (dari 45), `config_service.py:302` (dari 256), `tax_center_service.py:174` (dari 161) |
| `contra_bon.qty_tolerance_percent` | Sudah `not_used` (KF-T2), alasan sama dengan tabel (4) |
| `config_health._mentions` | Berlaku. `config_health.py:44` |
| `config_registry.default_of` | Sudah ada (KF-T2) |
| Catatan basis sementara (tidak berlaku di cabang: berkas sudah dihapus di `1dcb06c`) | `frontend/src/features/sales/ReturnAssumptionsPanel.jsx` masih ada di `ccff778` (penghapusan KF-T2 tidak ikut commit sementara) → `test_KFT2_U14…` (tests_mem) dan suite jest KF-T2 U14 merah **di semua keadaan**, dan `audit_config_wiring --strict` keluar 1 (1 editor ganda). Bukan perubahan unit ini; tidak disentuh |

## Pembagian serah-terima

**(a) jalur baru, pemakai lama belum disentuh** — keadaan disimpan di
`/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/kft3_a_state/` (salinan tiap berkas +
`a_tracked.patch` + `DAFTAR_BERKAS_A.txt`).

| Berkas | Isi |
|---|---|
| `backend/services/config_overrides.py` (baru) | `PENIMPA` (3 butir: `pt_bukan_pkp`, `wajib_transfer_antar_pt`, `master_grade_mutu`), `penimpa(key, ctx, nilai)`; kunci tanpa penimpa = nol kueri |
| `backend/services/config_resolver.py` | `resolve()`: penimpa sesudah pemenang (bukan simulasi) → `value`, `stored_value`, `overridden_by`, lapisan `override` pemenang di `explain`; `LAYER_ORDER`/`LAYER_LABEL` + `override`; `resolve_group` meneruskan `stored_value`/`overridden_by`; `scheduled` + `id`/`scope_type`/`scope_id`; `_stored_rows` & `apply_due_values` melewati `cancelled_at` (penanda diisi bersyarat, sekali); `ensure_due_applied` + cache `_JATUH_TEMPO`; `job_config_apply_due`; `scheduled_row`/`cancel_scheduled` (`ScheduleError`); `history` → `cancelled`; `policy_settings` memanggil `ensure_due_applied`; `set_value`/`clear_layer` `prev_value` = nilai tersimpan; komentar INV-CFG-03 |
| `backend/services/config_service.py` | `get_global_settings` memanggil `ensure_due_applied` (blok `KF-T3`) |
| `backend/services/scheduler_service.py` | Job `config_apply_due` "Aktifkan Pengaturan Terjadwal" (5 menit, `settings-config`) |
| `backend/routers/config.py`, `backend/schemas_config.py` | `POST /api/config/values/cancel-scheduled` (`ConfigCancelScheduledIn`): 404 → 403 (`_may_edit` + `_assert_scope_write`) → 409/409/400; jejak audit `config_schedule_cancelled` |
| `backend/tests_mem/test_KFT3_nilai_dipakai.py` (baru), `conftest.py` (cache `_JATUH_TEMPO`) | U1–U9 (+U7b) |
| `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md` | field `config_values.cancelled_*`; peta dibangkitkan |

**(b) pengalihan + pematian yang palsu + layar** — daftar berkas di
`/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/kft3_b_files.txt` (40 berkas kode/uji/dokumen + laporan ini + 15 berkas bukti).

| Berkas | Isi |
|---|---|
| `services/config_service.py` | `default_payment_term_code(entity_id)` (KP-11) |
| `routers/sales_orders.py` | termin bawaan = `default_payment_term_code(entity_id)` PT pesanan (pembacaan dokumen grup dibuang) |
| `routers/products.py` | `inventory.default_uom` per PT aktif pembuat (`entity_ctx`), cadangan `default_of` |
| `services/notification_service.py` | `notif.po_stage_stuck_days` per PT tiap PO, disimpan sementara per PT selama satu putaran |
| `services/receiving_uom_service.py` | `get_settings(task.entity_id)` di `convert_doc_qty`, `uom_options`, `preview`, `preflight_scan`; `load_engine(task.entity_id)` di `convert_doc_qty` |
| `services/uom_rules_service.py` | `load_engine(entity_id="")`, `check_variance(…, entity_id="")` |
| `makloon_order_service.py` (2), `contract_service.py` (2), `blanket_po_service.py`, `purchase_requisition_service.py` (`_enrich_items(…, entity_id)`), `routers/purchase_orders.py` | `load_engine(<PT dokumen>)` |
| `services/qc_inspection_service.py` | `lots.get_settings(roll.owner_entity_id)` |
| `services/payment_plan_service.py`, `services/finance_case_service.py` | 0/kosong → `default_of(key)` |
| `services/tax_center_service.py` | `efaktur_enabled = is_pkp` |
| `services/config_health.py` | `_mentions(ref, key)` ketat (lihat Menyimpang 1) |
| `config_catalog_core.py`, `_payment.py`, `_case.py` | `notif.low_stock_division` `scopes=("global",)`; `min=1` + help "Paling kecil Rp 1."; `tax.efaktur_enabled` `not_used`; `consumers` termin & tahap PO |
| `config_catalog_{ai,bank,case,contrabon,core,documents,finance,interco,ops,rnd}.py` | 89 rujukan pemakai diarahkan ke pembaca nyata (`bukti/KF-T3/rujukan_pemakai_diperbaiki.log`) |
| `routers/inbound_scan_label.py` | `_tolerance_pct` membaca kunci utuh `receiving.label_variance_tolerance_percent` (sama dengan `receiving_cfg`; supaya ada pembaca yang badannya menyebut kunci) |
| Layar: `features/settings/config/SettingCard.jsx`, `SettingsHub.jsx`, `ConfigDrawers.jsx`, `configApi.js`, `styles/config.css` | lencana **Ditimpa** + catatan + **Buka sumbernya**; editor mengubah nilai tersimpan; baris jadwal per butir (nilai · mulai WIB · Global/nama PT) + **Batalkan jadwal** (`askReason`, alasan wajib kunci berisiko tinggi, "Jadwal dibatalkan."); `configApi.cancelScheduled`; riwayat "dibatalkan"; jejak lapisan "ditentukan oleh: <penimpa>" |
| Uji: `tests_mem/test_KFT3_pengalihan.py` (baru), `tests_mem/test_KFT1_izin_pengaturan.py` (`KFT3_TIDAK_DIPAKAI = 1`), `conftest.py` (cache `_TREES`), `tests/test_bp_KFT3_nilai_dipakai.py` (baru, lapis A), `features/settings/config/__tests__/kft3SettingCard.test.js` (baru) | |
| `memory/PRD.md`, `CODEBASE_MAP.md` | baris KF-T3; peta dibangkitkan (`scripts/gen_codebase_map.py`) |

Membatalkan (b): kembalikan berkas daftar (b) ke salinan (a); (a) tidak mengubah pemakai lama.

## KF-04 / KF-09 / KF-10 / KF-11 / KP-11

- Berlaku di HEAD: ya (tabel cek ulang; merah U1–U16).
- Akar masalah: resolver mengembalikan nilai lapisan tanpa tahu aturan lain yang menang; jadwal hanya disalin ke
  penyimpanan lama saat layar dibuka; sejumlah pembaca lama membaca dokumen grup tanpa PT; pemeriksa kesehatan cukup
  menemukan nama daun.
- Perubahan perilaku (sebelum → sesudah):
  - `GET /api/config/effective` / `explain` / `value_of`: `tax.ppn_rate` PT bukan PKP 12 → **0** (`stored_value` 12,
    `overridden_by.id = pt_bukan_pkp`); `allocation.allow_intercompany` selama wajib transfer aktif True → **False**;
    `qc.grade_thresholds.a_max/b_max` = `max_points` Master Grade bila diisi. `source_layer` tetap lapisan nilai tersimpan.
  - Jadwal jatuh tempo terbaca pembaca lama tanpa membuka layar; job 5 menit; jadwal bisa dibatalkan (riwayat tetap).
  - Pesanan tanpa termin memakai termin PT pesanan; produk baru tanpa satuan memakai satuan PT aktif pembuat; ambang tahap
    PO macet per PT; kebijakan penerimaan/konversi satuan/lot QC per PT dokumen (PT yang belum menyimpan nilai khusus:
    tidak berubah).
  - `notif.low_stock_division` lapisan PT → 400; `payment.plan_tolerance_rupiah`/`case.holding_case_after_days` 0 → 400;
    `tax.efaktur_enabled` simpan → 400 berisi alasan; Pusat Pajak `efaktur_enabled` = status PKP (hasil sama dengan dulu
    untuk data bawaan).
  - Kesehatan Konfigurasi: tidak ada rujukan basi (364 OK / 19 tidak dipakai).
- Data: tanpa migrasi. Field penanda `config_values.cancelled_at`, `cancelled_by`, `cancelled_by_id`, `cancel_reason`.
  Lapisan PT `notif.low_stock_division` yang sudah tersimpan tidak dihapus (resolver mengabaikannya). Kueri pencarinya
  (lingkungan A, hanya baca):
  `db.config_values.find({key: "notif.low_stock_division", scope_type: "entity"})` dan
  `db.system_settings.find({scope: /^ent_/, "notif.low_stock_division": {$exists: true}})`. Nilai 0 yang tersimpan
  sebelum `min=1` (akan dilaporkan INV-CFG-05): `db.config_values.find({key: {$in: ["payment.plan_tolerance_rupiah",
  "case.holding_case_after_days"]}, value: {$lt: 1}})`.
- Commit: belum (instruksi).
- Pengujian: tabel di bawah.
- Bukti UI: belum diuji jalan di peramban (U17) — pengganti: uji komponen jest 6/6.
- Fixture disiapkan langsung vs proses bisnis: sisip langsung = U6 (baris jadwal jatuh tempo yang belum diterapkan),
  U10c (dua PO bertahap berjalan), U13/U13b (dokumen tugas penerimaan di memori), U13c (roll di memori, pembaca lot
  ditiru); lewat API = U1–U5, U7–U9, U10, U10b, U12, U14–U15 (penyimpanan nilai lapisan PT/grup, Master Grade, jadwal).
- Dampak pada modul terkait: simulator `tax`/`qc_grade` kini memakai nilai penimpa (sama dengan mesin); simulator `tax`
  masih membaca `tax.efaktur_enabled` sebagai PKP (rumus simulator = KF-T4); kartu tautan Pusat Pajak masih menautkan
  "Terbitkan e-Faktur" ke kartunya (spesifikasi: layar tidak berubah bentuk; kartunya kini menulis "tidak dipakai" +
  alasan).
- Keterbatasan / belum teruji: U17 belum diuji jalan di peramban.
- Status: implemented_pending_review.

## Uji penerimaan

Merah: (a) dijalankan pada kode `ccff778` utuh (pohon `git archive HEAD`): 10/10 gagal. Berkas (b) pada keadaan (a)
(pemakai lama): 12 gagal, 2 lulus (U1c = jalur (a); U15b = perilaku dipertahankan); berkas (b) pada `ccff778`: 13 gagal,
1 lulus (U15b).

| ID | Lapis | Merah di kode lama (sebab) | Hasil kode baru |
|---|---|---|---|
| U1 | B | ya — `value` 12 (KF-04) | Lulus — 0 / `stored_value` 12.0 / `pt_bukan_pkp`; `value_of` = `get_effective_settings` = 0 |
| U1c (tambahan) | B | ya | Lulus — tulis 13 lapisan `ent_kanda`: resolver = pembaca lama = 0, `stored_value` 13, riwayat 12 → 13 |
| U2 | B | ya — `overridden_by` tidak ada | Lulus — 12.0, `None` |
| U3 | B | ya — `value` True | Lulus — awal False ditimpa; sesudah PT `ent_ksc` True tanpa penimpa = `get_allocation_policy`; `ent_kanda` False |
| U4 | B | ya — 20 | Lulus — 18; lapisan terakhir `override` satu-satunya pemenang |
| U5 | B | ya — pembaca lama tertinggal (KF-09) | Lulus — nilai baru di kedua pembaca tanpa endpoint |
| U6 | B | ya — job tidak ada | Lulus — job 5 menit, `applied == 1`, dokumen grup memuat nilai; ulang 0 |
| U7 (+U7b) | B | ya — `scheduled` tanpa `id`; 404 | Lulus — 200 + `cancelled_at`; `[]`; 409 "Jadwal ini sudah dibatalkan."; riwayat `cancelled`; 404 / 400 "Alasan pembatalan wajib diisi." |
| U8 | B | ya — 404 | Lulus — 409 "Perubahan ini sudah berlaku…", baris identik |
| U9 | B | ya — 404 | Lulus — Sopir 403, `cancelled_at` tidak ada |
| U10 | B | ya — fungsi tidak ada | Lulus — NET7 / NET30; tidak ada `system_settings.find_one` di sekitar termin |
| U10b, U10c (tambahan) | B | ya — `meter`; ambang kosong | Lulus — produk `ent_ksc` yard / `ent_kanda` meter; PO `ent_ksc` (ambang 3) diberitakan, `ent_kanda` (7) tidak |
| U11 | A | — | **Lulus** di lingkungan A (`tests/test_bp_KFT3_nilai_dipakai.py`, bersama pelengkap U1/U6/U7; backend `69cc4e3`) |
| U12 (+U12b) | B | ya — `entity_id` tidak dikenal | Lulus — `ent_ksc` warn, `ent_kanda` block; pemanggil tanpa PT tinggal 3 yang tanpa dokumen |
| U13 (+U13b, U13c) | B | ya — `ent_ksc` ditolak; mode "off" diabaikan; lot `""` | Lulus — `ent_ksc` lolos ditandai lebih, `ent_kanda` ditolak; mode per PT; lot PT pemilik |
| U14 (+U14b) | B | ya — 200 | Lulus — 400 ×3 (lapisan tidak didukung; minimum 1; minimum 1); pembaca 0 → bawaan registry |
| U15 (+U15b) | B | ya — `tax.efaktur_enabled` aktif | Lulus — enam kunci `not_used` (role_home = alasan PR-T4); 400 berisi alasan; Pusat Pajak e-Faktur = PKP (U15b lulus juga di kode lama: perilaku dipertahankan) |
| U16 | B | ya — tiruan `role_home.admin` OK | Lulus — `STALE`; `MISSING`; rujukan nyata OK; `broken == []` |
| U17 | layar | ya — 5/6 uji komponen merah | Uji komponen 6/6 lulus. **Belum diuji jalan di peramban** |

`backend/tests_mem` seluruhnya (`bukti/KF-T3/tests_mem_seluruh_sebelum_a_ab.log`): `ccff778` **414 lulus / 1 gagal / 2
dilewati / 3 xfail** → (a) **424 / 1 / 2 / 3** → (a)+(b) **438 / 1 / 2 / 3**. Satu gagal di ketiga keadaan =
`test_KFT2_U14…` (berkas `ReturnAssumptionsPanel.jsx` di basis sementara; instruksi menyebut HEAD 415 lulus — selisih
satu itu). Uji KF-T3: 24 (B) + 6 (jest) baru.

Jest (folder sendiri): `kft3SettingCard` 6/6 (kode lama 1/6 — uji kendali "tidak ditimpa"); `settingCardBertanggal` 2/2.
Seluruh suite: lama 36 suite gagal dimuat / 66 lulus / 479 uji (1 gagal) → baru 36 / 67 / 485 (1 gagal sama: KF-T2 U14
pelengkap). Suite gagal dimuat identik (`@radix-ui`/`cmdk` tidak termuat — kendala lingkungan). ESLint berkas layar yang
diubah: 0 galat, 5 peringatan identik dengan kode lama.

`t1_config.py` diulang (`bukti/KF-T3/t1_config_sebelum_sesudah.log`, 383 kunci, galat 0): penyimpangan `ent_kanda`
`tax.ppn_rate` kini berbentuk **resolver = API = pembaca lama = 0** (skrip menandai "salah" karena membandingkan dengan
nilai tulis; `stored_value` = nilai tulis dibuktikan U1c); `tax.efaktur_enabled` kini `not_used` (ditolak). Baru tampak:
`allocation.allow_intercompany` — resolver = mesin (`get_allocation_policy`, False selama wajib transfer aktif), sedangkan
"pembaca lama" skrip membaca dokumen mentah yang tidak pernah dipakai mesin apa adanya; dulu kesamaan semu. Dua kunci PPh
21 bertanggal (PK-46, tidak diproyeksikan) sama seperti sebelumnya.

## Bukti

`bukti/KF-T3/`: `tests_mem_KFT3_a_merah_kode_HEAD.log`, `tests_mem_KFT3_b_merah_keadaan_a.log`,
`tests_mem_KFT3_b_merah_kode_HEAD.log`,
`tests_mem_KFT3_hijau_kode_baru.log`, `tests_mem_seluruh_sebelum_a_ab.log`, `penjaga_statik_sebelum_a_sesudah.log`,
`config_health_sebelum_sesudah.log`, `audit_config_wiring{,_strict,_selftest}_sebelum_sesudah.log`,
`rujukan_pemakai_diperbaiki.log`, `t1_config_sebelum_sesudah.log`, `jest_KFT3_merah_kode_lama.log`,
`jest_KFT3_hijau_kode_baru.log`, `jest_seluruh_sebelum_sesudah.log`.

## Penggabungan

Dikerjakan di basis lokal `ccff778`; digabung di atas `0da3656` (sesudah KP-T4 dan KF-T5). (a) tergabung otomatis
(`routers/config.py`, `config_resolver.py`, `config_service.py`, `ENTITY_REGISTRY.md`); `tests_mem` (a) **450 → 460**.
Konflik di (b):

| Berkas | Sebab | Penyelesaian |
|---|---|---|
| `config_catalog_contrabon|finance|interco|rnd.py` | KF-T3 mengarahkan `consumers` kunci persetujuan ke pembaca lama (`contra_bon_service.policy`, `amendment_service.policy_snapshot`, `interco_service._assert_may_release`, `rnd_gate.policy`); KP-T4 sudah memindah kunci itu ke Aturan Persetujuan (`not_used`, pemakai `approval_policy_service.default_rows_for`) | Bentuk KP-T4; `config_health` tetap 0 rusak (pembaca bawaan menyebut kuncinya utuh) |
| `test_KFT1_izin_pengaturan.py` | `KPT4_TIDAK_DIPAKAI` dan `KFT3_TIDAK_DIPAKAI` | Keduanya dikurangkan di U02, alasan tertulis |
| `test_KFT3_pengalihan.py` U14 | KF-T5 mengganti pesan lapisan tak sah menjadi "“{label}” tidak bisa dibedakan per PT." | Harapan uji mengikuti pesan baru |

`tests_mem` (b) **474 lulus** / 2 / 3 (sebelum KP-T1); jest seluruhnya 479/479. Catatan basis sementara di atas
(`ReturnAssumptionsPanel.jsx`) tidak berlaku di cabang.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `69cc4e3`), sesudah `restore_demo` (data acuan; tiga skrip seed yang
sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Satu jalan gate untuk tiga unit
yang digabung berturut-turut (KF-T5 `0da3656`, KF-T3 `dbe1633`·`9783875`, KP-T1 `69cc4e3`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Hitungan penjaga statik berhitung (`scripts`… `verify_auth_coverage` 28, `verify_ui_standard` 23, `audit_i18n_id` 111,
`audit_create_modal` 6, `verify_page_tabs` 1, `verify_to_list_bound` 6, `verify_entity_label` 2, lainnya 0/PASS) sama
sebelum dan sesudah tiap unit; `verify_role_gate_ui` PASS; `audit_config_wiring --strict` bersih; `config_health` 0 rusak.
Jest (`src/config`, `src/features`, `src/hooks`, `src/components`) di HEAD akhir: 487/487 uji lulus; 34 suite gagal dimuat
karena `@radix-ui/primitive/is-development` (kendala lingkungan).

Penjaga statik dari salinan kerja, sebelum → (a) → sesudah (hitungan identik di ketiga keadaan):
`verify_auth_coverage` 28 → 28 → 28 (1740 → 1741 cek: rute baru berizin lolos); `verify_ui_standard` 23; `audit_i18n_id`
113 (hanya geser baris karena job baru); `audit_create_modal` 6; `verify_page_tabs` 1; `verify_to_list_bound` 6;
`verify_entity_label` 2; `verify_list_export`, `verify_error_notice`, `verify_custom_modals`, `verify_money_idempotency`,
`verify_codebase_map`, `verify_knselect_contract`, `verify_access_catalog_nav`, `verify_modal_dismiss`,
`verify_blocking_dialogs` lulus/0; `verify_role_gate_ui` 39 cek / 0 pelanggaran; `audit_config_wiring` 0 kunci bermasalah
+ 1 editor ganda (basis sementara) — OK 66 → 65, NOT_USED 5 → 6 (`tax.efaktur_enabled`); `--strict` 1 → 1, `--self-test`
keluar sama; `config_health` (aturan baru) 365 OK / 18 → 364 OK / 19 tidak dipakai, 0 rusak (aturan ketat pada registry
lama: 89 rusak — daftar di bukti). `verify_approval_queues` tidak dibandingkan (bergantung isi database).

## Menyimpang dari blueprint

1. **`config_health` (a)**: badan fungsi dipindai **ditambah konstanta modul berisi teks saja** (tuple/list/set/dict teks,
   mis. `CFG_KEYS`, `STAGE_AKSI`, `KUNCI_BUKTI`) yang dirujuk badan itu. Tanpa ini pemuat kebijakan berpola "satu fungsi
   membaca daftar kunci modul" (`finance_case_service.policy`, `bank_recon_service.load_cfg`, `contra_bon_service.policy`,
   `approval_matrix_service.guard`, …) tidak pernah menyebut kuncinya di badannya, sehingga rujukan harus kehilangan nama
   fungsinya (dan `test_KFT2_U11` — yang menuntut fungsi rujukan ada — ikut merah) atau kodenya ditulis ulang. Konstanta
   bersarang/campuran (mis. `DEFAULT_GLOBAL_SETTINGS`) tidak ikut, supaya tidak meloloskan semua kunci. Aturan keluarga
   `kontrol.<aksi>.<x>` (KF-T6, literal aksi) dipertahankan. Uji U16 tetap sesuai spesifikasi.
2. Pengetatan memerahkan **89 kunci** (84 STALE, 5 MISSING) — semuanya punya pembaca nyata; rujukannya diarahkan ke fungsi
   pembaca (tidak ada yang perlu `not_used`), plus 2 kunci yang pembacanya diubah unit ini (termin, tahap PO macet).
   Satu pembaca ditulis dengan kunci utuh (`inbound_scan_label._tolerance_pct`) karena pembantunya merangkai kunci.
3. `resolve()` saat ditimpa: `source_layer`/`source_label` tetap lapisan nilai tersimpan (kartu tetap bisa "Kembalikan ke
   global" untuk nilai milik PT); `set_value`/`clear_layer` mencatat `prev_value` = nilai tersimpan (riwayat "12 → 13",
   bukan "0 → 13"). Kartu mengedit nilai tersimpan (bukan nilai penimpa).
4. `link` penimpa hanya memuat kunci yang relevan (`{"view": …}` atau `{"key": …}`), bukan keduanya.
5. Urutan pemeriksaan pembatalan: 404 → 403 → 409 dibatalkan → 409 sudah berlaku → 400 alasan (403 sebelum 409 supaya
   keadaan baris tidak bocor ke yang tidak berwenang). `applied_at`/`cancelled_at` diisi dengan update bersyarat.
6. Uji tambahan di luar tabel untuk baris tabel (3) tanpa ID (U10b, U10c, U12b, U13b, U13c, U14b, U15b, U1c).

## Usulan koreksi blueprint (teks pengganti persis)

1. Tabel (4), baris `role_home.*`: "| `role_home.admin`, `role_home.manager`, `role_home.sales`, `role_home.warehouse` |
   Sudah `not_used` (PR-T4 — halaman awal kini sifat peran) | "Diatur per peran di Peran & Hak Akses › Halaman awal" |";
   "Keadaan sekarang" KF-11 baris pertama: "`role_home.*` (4 kunci) sudah `not_used` sejak PR-T4"; U15 hasil: "Semua
   `not_used`; 400 dengan alasan kunci itu".
2. "(4)", kalimat `config_health._mentions`: "(a) bila rujukan berbentuk `berkas.py:fungsi`, fungsi itu harus ada (tidak
   ada → `MISSING`) dan hanya badan fungsi itu — ditambah konstanta modul berisi teks saja yang dirujuknya — yang dipindai
   (`ast`); (b) cocok = kunci utuh muncul, **atau** segmen induk dan daun sama-sama muncul sebagai kata utuh; daun saja
   tidak cukup; keluarga `kontrol.<aksi>.<x>` cukup literal aksinya (KF-T6)."
3. U16 persiapan: "Entri tiruan berstatus `active`: kunci `role_home.admin`, …" (entri `not_used` selalu `NOT_USED`).
4. "(1) Penimpaan terdaftar", sesudah kalimat `explain`: "`source_layer`/`source_label` tetap lapisan nilai tersimpan;
   `set_value` mencatat `prev_value` = `stored_value`."
5. Tabel (3) baris `uom.*`: "… 12 pemanggil di `services/`+`routers/` mengirim PT dokumennya; tiga tanpa dokumen tetap nilai
   grup: `uom_rules_service.convert_with_trail`, `makloon_calc_service.estimate_output` (mesin dipinjamkan pemanggil),
   `routers/uom_conversions.check_variance`; `receiving_uom_service.convert_doc_qty` juga `load_engine(task.entity_id)`."

## Asumsi

- `ASUMSI` spesifikasi dipakai: e-Faktur tidak dihidupkan sebagai sakelar; satuan bawaan produk baru = PT aktif pembuat
  ("Semua PT" = nilai grup); satu proses server (cache jadwal proses lain segar saat job 5 menit).
- Pembatalan oleh pemegang izin kunci; pada lapisan PT diperiksa penugasan PT (`_assert_scope_write`); alasan wajib bila
  `requires_reason` (= risiko tinggi).
- Daftar kunci berlapis PT di data acuan (RISIKO spesifikasi): **belum diambil dari database** (instruksi: jangan menyentuh
  database `backend/.env`). Pembacaan statik skrip benih: satu-satunya lapisan PT yang ditulis benih = `receiving.mode`
  (`seed_realistic._seed_receiving_mode`), tidak termasuk tabel (3). Kueri untuk lingkungan A:
  `db.config_values.find({scope_type: "entity", cancelled_at: {$exists: false}, key: {$in: ["finance.default_payment_term_code",
  "inventory.default_uom", "notif.po_stage_stuck_days", "receiving.block_over_remaining", "receiving.supplier_uom_input_mode",
  "receiving.require_supplier_item_for_supplier_uom", "uom.warn_pct", "uom.block_pct", "uom.allow_override", "uom.precision",
  "uom.require_trail"]}})` ditambah `key: /^lot\./`, dan `db.system_settings.find({scope: /^ent_/})` (lapisan lama PT).
- Pemakai `value_of("tax.ppn_rate")` mentah (RISIKO): hanya simulator `tax` (`config_simulator.py`) lewat `resolve`; mesin
  pajak memakai `get_effective_settings`. Tidak ada pemakai yang mengandalkan nilai mentah.

## Titik henti

- Tidak ada yang dilewati. Tidak ada skrip migrasi. Job penjadwal tidak dijalankan terhadap database `backend/.env` (U6
  hanya di lingkungan B).

## Persinggungan dengan unit lain

- KP-T4 (berjalan): `config_service.py` — dua blok `KF-T3` (`get_global_settings` baris pertama; fungsi baru
  `default_payment_term_code` sebelum "Kalkulasi pajak"); tidak menyentuh `approval_matrix_service.py`, kebijakan
  persetujuan, maupun `config_catalog_approval_matrix.py`.
- KP-T7 (belum): hanya `notif.po_stage_stuck_days` per PT (tabel (3)) dan job `config_apply_due`; penerima/ambang pengingat
  lain dan pengaturan penjadwal tidak disentuh.
- KF-T2/KF-T6: `consumers` beberapa kunci mereka diarahkan ke pembaca nyata (rujukan saja); aturan `kontrol.*` di
  `config_health` dipertahankan. KF-T4: simulator & teks kartu tidak diubah. KF-T5: penimpaan dari form Pelanggan tidak
  didaftarkan.

## Hambatan lingkungan

- Tanpa peramban dan tanpa backend :8001: U11, pelengkap lapis A, U17 (uji jalan) dan `gate.sh` belum dijalankan.
- `/app` menunjuk repo utama: `audit_config_wiring.py` dan `config_health` dijalankan lewat pemuat yang mengganti jalurnya
  ke salinan kerja (berkas penjaga tidak diubah).
- Satu berkas unggahan uji (`backend/uploads/kn7/design_gallery/e0720b68….png`) muncul sesudah putaran uji/skrip audit di
  salinan kerja dan sudah dihapus (bukan bagian unit).

## Yang perlu direview

- Perluasan pemindaian `config_health` (Menyimpang 1) dan 91 rujukan pemakai baru (`bukti/KF-T3/rujukan_pemakai_diperbaiki.log`).
- `source_layer` tetap lapisan tersimpan saat ditimpa (Menyimpang 3).
- Pesan galat minimum dari registry masih memuat kunci teknis ("'payment.plan_tolerance_rupiah' minimum 1 (diberi 0)") —
  format lama semua kunci, tidak diubah di sini.

Status: implemented_pending_review.
