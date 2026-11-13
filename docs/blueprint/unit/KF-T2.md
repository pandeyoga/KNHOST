# KF-T2 — Bereskan kunci pengaturan yang mati, ganda, dan tersembunyi

| | |
|---|---|
| Gelombang | Jalur pengaturan (sejajar gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KF-T1 |
| Menutup temuan | KF-05, KF-06, KP-13, KP-29, KP-30 |
| Keputusan | — |
| Standar | §2.1, §2.2, §2.4, §1 (P9), §4 (L5), §5 (D8) |
| Lingkungan uji | B; gate `config_wiring` di A atau di luar Docker dengan tautan `/app` |

## Tujuan

Setiap aturan yang dibaca mesin punya tepat satu tempat mengubah — Pusat Pengaturan — dengan riwayat; pengaturan yang
tidak dipakai tidak lagi tampil seolah berfungsi; dan bila dokumen pengaturan tidak lengkap, mesin memakai nilai bawaan
yang sama dengan yang tampil di layar. Gate `config_wiring` menjadi hijau.

## Keadaan sekarang

Semua `[dibaca]`; angka gate dari menjalankan `scripts/audit_config_wiring.py` tanpa database pada `3132cc4`:
78 kunci, 7 DEAD, 2 HIDDEN, 2 editor ganda.

| Temuan | Fakta | Jangkar |
|---|---|---|
| 7 kunci "mati" `returns.grade_price_factors.A … BS` | Wadahnya **dibaca** mesin; gate menilainya mati karena tidak ada entri registry yang mencakupnya dan nama daunnya kurang dari tiga huruf | `backend/services/return_grade_impairment.py:21` (`grade_factors`); `backend/services/return_policy_service.py:303` (`return_assumptions`); `scripts/audit_config_wiring.py:369` (`hits`) |
| 2 kunci tanpa layar `interco_payment.allow_netting`, `interco_payment.require_full_payment` | Dibaca saat pelunasan antar-PT; layar selalu menulis `false`/`true` | `backend/services/interco_service.py:1171` (`payment_settings`); `backend/services/interco_service.py:996` (`allow_netting`) |
| 2 layar menulis lewat jalur lama | `PUT /api/settings` menimpa `system_settings` langsung, tanpa baris `config_values` (tanpa riwayat, alasan, jadwal) | `frontend/src/features/sales/ReturnAssumptionsPanel.jsx:36` (`ReturnAssumptionsPanel`); `frontend/src/features/finance/interco/IntercoPaymentSchedule.jsx:36` (`CutoffForm`); `backend/routers/settings.py:50` (`update_settings`), `backend/routers/settings.py:19` (`SETTINGS_SECTIONS`) |
| 11 isian asumsi retur dan jadwal bayar antar-PT tidak ada di registry | Bawaannya hanya di kode | `backend/services/config_service.py:20` (`customer_window_days`), `backend/services/config_service.py:25` (`interco_payment`); `backend/services/return_policy_service.py:294` (`RETURN_ASSUMPTION_DEFAULTS`) |
| `contra_bon.qty_tolerance_percent` aktif tetapi tidak dipakai | Toleransi kontrabon diambil dari `purchasing.bill_qty_tolerance_percent` | `backend/config_catalog_contrabon.py:23` (`contra_bon.qty_tolerance_percent`); `backend/services/contra_bon_service.py:152` (`qty_tolerance_percent`) |
| KP-13: `lot.number_format` tidak dibaca saat membuat nomor lot | Nomor selalu `LOT-YYMM-####`; satu-satunya pembaca kunci adalah simulator | `backend/services/lot_service.py:133` (`next_lot_number`); `backend/config_catalog_ops.py:158` (`lot.number_format`); `backend/services/config_simulator.py:315` (`lot.number_format`) |
| KP-30: akun biaya bank, titipan dana, dan bunga bank diatur di dua tempat | Rekonsiliasi bank membaca tiga kunci registry; Pemetaan Akun punya `kas_bank.beban_bank` dan `kas_bank.titipan_dana` dengan kode bawaan yang sama | `backend/services/bank_recon_service.py:86` (`holding_account_code`), `backend/services/bank_recon_service.py:91` (`charge_account_code`), `backend/services/bank_recon_service.py:92` (`interest_account_code`); `backend/services/gl_mapping_registry.py:40` (`kas_bank.beban_bank`), `backend/services/gl_mapping_registry.py:42` (`kas_bank.titipan_dana`) |
| 3 rujukan pemakai menunjuk fungsi yang tidak ada | `finance_case_service.py:sla_of` (yang ada `sla_hours_of`); `ai_chat_service.py:ask` (yang ada `chat_events`) | `backend/config_catalog_case.py:21` (`sla_of`), `backend/services/finance_case_service.py:97` (`sla_hours_of`); `backend/config_catalog_ai.py:88` (`ai_chat_service.py:ask`), `backend/services/ai_chat_service.py:162` (`route_threshold_pct`) |

KF-06 — nilai cadangan di kode berbeda dari bawaan registry (dicek ulang per baris):

| Kunci | Bawaan registry | Cadangan kode | Jangkar |
|---|---|---|---|
| `tax.ppn_rate` | 12.0 | 0 | `backend/services/config_service.py:274` (`compute_tax`) |
| `tax.dpp_nilai_lain` | True | False | `backend/services/config_service.py:279` (`compute_tax`) |
| `sales.allow_item_discount`, `sales.allow_order_discount` | False | True | `backend/services/config_service.py:430` (`compute_order_pricing`) |
| `inventory.intercompany_transfer_required` | True | False | `backend/services/config_service.py:539` (`get_allocation_policy`) |
| `ar.denda_rate_pct_per_month` | 2.0 | 0 | `backend/services/ar_aging_service.py:77` (`_denda_estimate`) |
| `commission.discount_threshold` | 10.0 | 0 | `backend/services/sales_force_service.py:259` (`discount_threshold`) |
| `commission.discount_factor` | 0.5 | 1.0 | `backend/services/sales_force_service.py:269` (`discount_factor`) |
| `sales.require_so_validation` | False | True | `backend/services/so_approvals.py:227` (`require_validation_default`) |
| `allocation.lot_selection` | fifo | fefo | `backend/services/roll_service.py:1081` (`_build_allocation_plan`) |
| `approval.po_custom_direksi_min` | 50000000 | 0.0 | `backend/services/approval_matrix_service.py:69` (`direksi_min`), `backend/services/approval_matrix_service.py:217` (`evaluate`) |
| `hr.feature_toggles.pph21` | True | — | **Tidak berlaku.** Pembaca sakelar ada di `backend/services/hr_payroll_service.py:279` (`_pph21_on`) dengan cadangan `True`; baris 292 yang disebut `LAMPIRAN_DAFTAR.md` §H membaca nominal `pph21` pada slip, bukan pengaturan |

## Perubahan

### Data

Tidak ada koleksi baru. Tidak ada migrasi untuk 11 kunci baru: `legacy_target` memetakan `returns.x` dan
`interco_payment.x` ke jalur yang sama di dokumen `system_settings` yang dipakai hari ini, sehingga nilai lama terbaca
sebagai lapisan "pengaturan lama".

KP-30 — skrip `scripts/migrate_kft2_akun_bank.py` (disiapkan dan diuji di data acuan; menjalankannya di data nyata =
titik henti H3): untuk lapisan grup dan tiap PT, bila nilai efektif `bank.charge_account_code`,
`bank.holding_account_code`, atau `bank.interest_account_code` berbeda dari kode Pemetaan Akun yang berlaku untuk lapisan
itu, panggil `gl_mapping_service.set_mapping(<kunci pemetaan>, <entity_id atau None>, <kode>, "Pindahan dari Pusat
Pengaturan (KF-T2)", aktor sistem)`. Mode bawaan `--dry-run` mencetak selisih; `--apply` menulis; jalan kedua tanpa
perubahan.

### Server

| Tempat | Perubahan |
|---|---|
| `return_policy_service.return_assumptions(entity_id)` | Membaca lima kunci `returns.*` lewat `config_resolver.value_of(key, {"entity_id": entity_id})`; bentuk jawaban tetap |
| `return_grade_impairment.grade_factors` | Tidak lagi menggabung `DEFAULT_FACTORS`; memakai nilai `returns.grade_price_factors` apa adanya (bawaannya sudah lengkap) |
| `interco_service.payment_settings(entity_id)` | Membaca enam kunci `interco_payment.*` lewat `value_of`; `cutoff_day`/`payment_day` bernilai 0 dan `basis` "" dikembalikan sebagai `None` (arti hari ini) |
| `PUT /api/settings` | Dimatikan: 410 "Pengaturan kini disimpan lewat Pusat Pengaturan." tanpa menulis apa pun. Sebelum itu semua pemanggil di `backend/`, `scripts/`, `frontend/src` dicari dan dialihkan ke `PUT /api/config/values` (diketahui: `backend/tests/test_p13_audit.py`, `scripts/audit/b3b_api_probe.py`). `GET` tetap |
| `config_service.saring_bagi_pembaca` (lahir di KF-T1) | `returns` dan `interco_payment` dicabut dari `BUKA_SEMENTARA`; keterbacaannya kini dari `sensitif_baca=False` pada kunci |
| `config_registry.default_of(key) -> Any` — baru | `require(key)["default"]`; dipakai sebagai satu-satunya cadangan |
| 10 baris cadangan di tabel KF-06 | Literal diganti `default_of("<kunci>")`. Di `compute_order_pricing` kuncinya `f"{cfg_section}.allow_item_discount"` / `…allow_order_discount` (bagian `purchasing` berbawaan `True`, `sales` `False`) |
| `bank_recon_service` (pembaca kebijakan) | `holding_acc` = `await gl_mapping_service.account_for("kas_bank.titipan_dana", entity_id)`; `charge_acc` = `account_for("kas_bank.beban_bank", entity_id)`; `interest_acc` = `account_for("kas_bank.pendapatan_bunga", entity_id)` |
| `gl_mapping_registry` | Entri baru `kas_bank.pendapatan_bunga`, kode bawaan `4-9000` (sama dengan bawaan `bank.interest_account_code` hari ini), label "Pendapatan bunga / jasa giro", pemakai "Rekonsiliasi bank" |
| `consumers` tiga kunci | `case.sla_hours`, `case.sla_hours_high` → `services/finance_case_service.py:sla_hours_of`; `ai.route_threshold_pct` → `services/ai_chat_service.py:chat_events` |
| `contra_bon_service` | `contra_bon.qty_tolerance_percent` dicabut dari daftar kunci yang dimuat |

### Pengaturan

Kunci baru (semua `scopes=("global", "entity")`, `sensitif_baca=False`, `risk="medium"` kecuali disebut):

| key | group | type | default | min · max · unit | permission | label | help | consumers |
|---|---|---|---|---|---|---|---|---|
| `returns.customer_window_days` | `retur` | `duration` | 21 | 1 · 365 · hari | `("sales_return", "policy")` | Batas retur pelanggan sejak surat jalan (hari) | Pelanggan boleh mengajukan retur sampai sekian hari sesudah tanggal surat jalan. Kebijakan retur per kategori atau pelanggan boleh menimpa angka ini. | `services/return_policy_service.py:return_assumptions` |
| `returns.supplier_window_days` | `retur` | `duration` | 21 | 1 · 365 · hari | sama | Batas retur ke pemasok sejak barang diterima (hari) | Klaim ke pemasok harus dikirim sebelum sekian hari sejak roll diterima gudang. | sama |
| `returns.supplier_reminder_days` | `retur` | `duration` | 3 | 0 · 60 · hari | sama | Ingatkan sebelum batas retur pemasok habis (hari) | Pengingat dikirim sekian hari sebelum batas. 0 = tanpa pengingat. | `services/return_disposition_service.py:job_supplier_deadline_reminder` |
| `returns.bill_first` | `retur` | `bool` | True | — | sama | Potong tagihan pesanan asal lebih dulu | Nilai retur dipakai mengurangi tagihan pesanan asal; sisanya baru dikembalikan atau menjadi saldo. | `services/return_service.py`, `services/return_roll_settlement_service.py` |
| `returns.grade_price_factors` | `retur` | `table` (`row_shape="map"`) | `{"A": 100, "A1": 95, "A2": 90, "B": 70, "B1": 60, "C": 40, "BS": 10}` | — | sama | Harga per grade (% dari harga produk) | Dasar menghitung kerugian saat barang retur turun grade: selisih persen grade lama dan baru dikali harga daftar. | `services/return_grade_impairment.py:grade_factors` |
| `interco_payment.allow_netting` | `antar-entitas` | `bool` | False | — | `("entity", "update")` | Izinkan saling hapus hutang antar-PT | Bila tidak, tiap transaksi antar-PT dibayar penuh lewat transfer atau kas. | `services/interco_service.py:create_settlement` |
| `interco_payment.require_full_payment` | `antar-entitas` | `bool` | True | — | sama | Pembayaran antar-PT harus penuh per transaksi | Bila ya, pelunasan sebagian ditolak. | sama |
| `interco_payment.cutoff_day` | `antar-entitas` | `int` | 0 | 0 · 31 · tanggal | sama | Tanggal tutup tagihan antar-PT | Transaksi sampai tanggal ini masuk jadwal bayar bulan itu. 0 = belum diatur (jadwal dan pengingat tidak berjalan). | `services/interco_service.py:payment_schedule` |
| `interco_payment.payment_day` | `antar-entitas` | `int` | 0 | 0 · 31 · tanggal | sama | Tanggal bayar antar-PT | 0 = akhir bulan. | sama |
| `interco_payment.basis` | `antar-entitas` | `enum` ("" Belum diatur · `receipt` Tanggal barang diterima · `invoice` Tanggal invoice · `document` Tanggal dokumen) | "" | — | sama | Tanggal acuan jadwal bayar antar-PT | Tanggal mana yang dibandingkan dengan tanggal tutup. | sama |
| `interco_payment.reminder_days` | `antar-entitas` | `duration` | 3 | 0 · 30 · hari | sama | Ingatkan sebelum tanggal bayar antar-PT (hari) | 0 = tanpa pengingat. | `services/interco_service.py:job_interco_payment_reminder` |

`impact` dan `example` ditulis pelaksana mengikuti `02` §2.1 (contoh memakai angka bawaan di atas). `requires_reason`
tidak diwajibkan (perilaku hari ini). Ini sekaligus menutup butir #55 Lampiran A audit.

Kunci yang ditandai `status="not_used"` (L5) beserta `not_used_reason`:

| Kunci | Alasan yang tampil |
|---|---|
| `contra_bon.qty_tolerance_percent` | "Toleransi jumlah kontrabon mengikuti pengaturan 'Toleransi jumlah tagihan pemasok'." Label dikembalikan tanpa awalan "(Lama)" |
| `lot.number_format` | "Nomor lot saat ini selalu berbentuk KODE-PT/LOT-TTBB-urutan. Format yang bisa diatur menyusul bersama penomoran dokumen." `simulate` dikosongkan |
| `bank.holding_account_code`, `bank.charge_account_code`, `bank.interest_account_code` | "Akun ini diatur di Pengaturan › Keuangan & Pajak › Pemetaan Akun." |

### Izin dan peran

Tidak ada pasangan baru. Menyimpan asumsi retur tetap butuh `sales_return.policy`; jadwal bayar antar-PT tetap
`entity.update` — sama dengan syarat `PUT /api/settings` hari ini.

### Layar

- Penjualan › Retur › Kebijakan Retur (`frontend/src/features/sales/ReturnPoliciesView.jsx`): panel
  `ReturnAssumptionsPanel` diganti daftar kartu dari mesin Pusat Pengaturan (`useSettingsBrowser` + `SettingsBrowser`,
  pola `frontend/src/features/crm/IncentiveRatesEditor.jsx`) dengan `groupIds: ["retur"]` dan `includeKeys` lima kunci
  `returns.*` di atas. Judul bagian: **Batas retur umum**. Bila pelaku tidak boleh membaca Pusat Pengaturan (403), bagian
  itu diganti satu baris hanya-baca dari `GET /api/settings/effective`: "Batas retur umum: pelanggan {n} hari sejak surat
  jalan · pemasok {m} hari sejak barang diterima." Berkas `ReturnAssumptionsPanel.jsx` dihapus.
- Keuangan › Antar-PT › Jadwal Bayar (`IntercoPaymentSchedule.jsx`): `CutoffForm` diganti kartu yang sama dengan
  `groupIds: ["antar-entitas"]`, `includeKeys: ["interco_payment."]`. Judul bagian: **Aturan jadwal bayar**. Tampil hanya
  bagi yang lolos baca; tombol simpan mengikuti `can_edit`.
- Kartu kunci `not_used` sudah menampilkan alasannya (perilaku yang ada).

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | statik | — | `python scripts/audit_config_wiring.py --strict` dan `--self-test` | Keluar 0; DEAD 0, HIDDEN 0, ORPHAN_UI 0, editor ganda 0; self-test PASS |
| U2 | B | — | Impor registry | 11 kunci baru ada dengan bawaan seperti tabel; 5 kunci di tabel kedua berstatus `not_used` |
| U3 | B | — | Admin `PUT /api/config/values` `returns.customer_window_days=30` lapisan PT `ent_ksc` | `return_assumptions("ent_ksc")["customer_window_days"] == 30`; `return_assumptions("ent_kanda")` tetap 21; `GET /api/config/history?key=…` 1 baris |
| U4 | B | Sisipkan `returns.customer_window_days: 14` ke `system_settings{scope: "global"}` (nilai jalur lama) | `return_assumptions("")`; `GET /api/config/effective?q=returns.customer_window_days` | 14; `source_layer == "legacy_global"` |
| U5 | B | — | Admin simpan `returns.grade_price_factors` dengan `B: 50` | `grade_factors("")["B"] == 50.0`; `compute(100000, 80000, 100, 50, 2)["amount"] == 100000.0` (selisih 50 % × 100.000 = 50.000 per satuan, di bawah nilai buku 80.000, × 2) |
| U6 | B | — | Admin simpan `interco_payment.allow_netting=true` lapisan PT `ent_ksc` | `payment_settings("ent_ksc")["allow_netting"] is True`; `payment_settings("ent_kanda")["allow_netting"] is False` |
| U7 | B | — | Bawaan tanpa tulisan apa pun: `payment_settings("")` | `cutoff_day is None`, `payment_day is None`, `basis is None`, `reminder_days == 3`, `require_full_payment is True` |
| U8 | B | — | Admin `PUT /api/settings` `{"scope": "global", "returns": {"customer_window_days": 5}}` | 410; `system_settings` global tidak berubah |
| U9 | B | — | Admin `PUT /api/config/values` untuk tiap 5 kunci `not_used` | 400 dengan teks alasan dari tabel |
| U10 | B | Dokumen global tanpa bagian terkait | `compute_order_pricing([{"price": 100, "quantity": 1, "discount_percent": 10}], settings={"sales": {}, "tax": {}})`; `require_validation_default({})`; `_denda_estimate(1000000, 30, {})` | `items_discount_total == 0.0`; `False`; `20000.0` (2 % × 1 bulan × 1.000.000) |
| U11 | B | — | `config_health.report()` | `broken == []`; tiga kunci di baris "rujukan pemakai" berstatus OK dan nama fungsinya ada di berkas (dicek dengan `ast`) |
| U12 | B | Akun `6-8100` ada; Admin memetakan `kas_bank.beban_bank` → `6-8100` untuk `ent_ksc` | Baca kebijakan rekonsiliasi bank untuk `ent_ksc` dan `ent_kanda` | `charge_acc` = `6-8100` dan `6-8000` |
| U13 | B | Sisipkan baris `config_values` `bank.charge_account_code = "6-8100"` lapisan PT `ent_ksc` (keadaan lama) | `migrate_kft2_akun_bank.py --dry-run`, `--apply`, `--apply` | Dry-run mencetak 1 selisih; sesudah apply `account_for("kas_bank.beban_bank", "ent_ksc") == "6-8100"`; jalan kedua 0 perubahan |
| U14 | statik | — | Cari `axios.put(` ke `/settings` di `frontend/src` | 0 hasil |
| U15 | layar (uji jalan) | Login Admin | Kebijakan Retur → ubah "Batas retur pelanggan…" menjadi 30 → Pengaturan › Semua pengaturan › Riwayat Perubahan | Baris riwayat tampil dengan nama pengubah dan nilai 21 → 30 |

## Langkah kerja

1. `backend/tests_mem/test_KFT2_kunci_pengaturan.py`: U2–U13 merah.
2. Daftarkan 11 kunci; alihkan tiga pembaca ke resolver; U3–U7 hijau.
3. Alihkan dua layar; matikan `PUT /api/settings` setelah pencarian pemanggil bersih (U8, U14).
4. Tandai 5 kunci `not_used`; alihkan pembaca akun bank; skrip migrasi (U9, U12, U13).
5. `default_of` dan 10 cadangan; perbaiki 3 `consumers` (U10, U11).
6. Gate `config_wiring` (U1), `gate.sh --quick`; laporan memuat keluaran gate sebelum dan sesudah.

## Dokumen ikut berubah

`memory/PRD.md` (asumsi retur dan jadwal bayar antar-PT kini di Pusat Pengaturan); `CODEBASE_MAP.md` (hapus
`ReturnAssumptionsPanel.jsx`, tambah `scripts/migrate_kft2_akun_bank.py`); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`
bila "Batas retur umum" belum ada.

## Di luar lingkup

- Nomor lot yang benar-benar mengikuti format → KP-T5. WhatsApp dokumen di Pusat Dokumen (bagian KP-29) → KP-T8.
  Tautan dari hub Pengaturan ke rekening, kas, dan gudang → KP-T9.
- Cadangan `RETURN_ASSUMPTION_DEFAULTS`, `DEFAULT_FACTORS`, dan konstanta kebijakan makloon (Lampiran A #53, #54, #56)
  → KF-T7. Pemeriksa otomatis nilai cadangan → KF-T8.
- `role_home.*` dan `tax.efaktur_enabled` → KF-T3. Teks dan pengelompokan kartu → KF-T4.

## Asumsi dan risiko

- `ASUMSI:` pemegang wewenang mengubah jadwal bayar antar-PT tetap pemegang `entity.update`, seperti hari ini.
- `ASUMSI:` kode akun `4-9000` untuk bunga bank dipertahankan sebagai bawaan entri pemetaan baru; unit ini tidak
  mengubah akun mana pun yang dipakai jurnal selama skrip migrasi dijalankan sebelum pembaca dialihkan di data nyata.
- `RISIKO:` di instalasi yang nilai tiga kunci akun banknya pernah diubah, pembaca baru memakai kode Pemetaan Akun bila
  skrip migrasi belum dijalankan. Laporan unit wajib memuat keluaran `--dry-run` pada data acuan dan menandai langkah
  `--apply` di data nyata sebagai H3. Membatalkan: kembalikan tiga baris pembaca di `bank_recon_service.py`.
- `RISIKO:` `allocation.lot_selection` — cadangan `fefo` adalah nama lama `fifo`; uji yang ada untuk urutan roll harus
  tetap hijau sesudah cadangan diganti.
