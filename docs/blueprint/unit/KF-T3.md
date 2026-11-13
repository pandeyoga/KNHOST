# KF-T3 — Layar menampilkan nilai yang dipakai mesin; jadwal diaktifkan penjadwal

| | |
|---|---|
| Gelombang | Jalur pengaturan (sejajar gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | tinggi — dua serah-terima (`00` §8) |
| Prasyarat | KF-T1 |
| Menutup temuan | KF-04, KF-09, KF-10, KF-11, KP-11 |
| Keputusan | — (aturan bawaan `00` §4.1) |
| Standar | §2.2, §2.4, §4 (L5, L6), §5 (D8) |
| Lingkungan uji | keduanya (alur pesanan U11 di A) |

## Tujuan

Angka di kartu pengaturan selalu sama dengan yang dipakai mesin: bila aturan lain menimpanya, kartu menyebut siapa;
nilai khusus PT benar-benar dipakai transaksi PT itu; perubahan berjadwal berlaku tepat waktu di semua bagian mesin dan
bisa dibatalkan; dan enam pengaturan yang tidak menggerakkan apa pun tidak lagi tampil aktif.

## Keadaan sekarang

| Temuan | Fakta | Jangkar |
|---|---|---|
| KF-04 `[dijalankan]` (`bukti/t1_config.py`, PT `ent_kanda`) | PT bukan PKP: pembaca lama memaksa tarif PPN 0, sedangkan `value_of` dan `GET /api/config/effective` mengembalikan nilai lapisan PT | `backend/services/config_service.py:254` (`is_pkp`); `backend/services/config_resolver.py:276` (`value_of`); `backend/services/config_resolver.py:281` (`resolve_group`) tidak memuat keterangan penimpaan |
| Penimpaan sejenis `[dibaca]` | `allocation.allow_intercompany` dipaksa mati selama `inventory.intercompany_transfer_required` aktif (keduanya aktif secara bawaan) | `backend/services/config_service.py:539` (`intercompany_transfer_required`) |
| | Batas poin grade: `max_points` di Master Grade Mutu menang atas `qc.grade_thresholds.a_max` / `b_max` | `backend/services/qc_inspection_service.py:105` (`grade_from_points`) |
| KF-09 `[dijalankan]` (`bukti/t5_jadwal_pengaturan.py`) | Nilai berjadwal hanya disalin ke penyimpanan lama oleh `apply_due_values`, yang dipanggil dari dua endpoint layar saja; pembaca lama tertinggal sampai layar dibuka. Tidak ada cara membatalkan jadwal | `backend/services/config_resolver.py:530` (`apply_due_values`); `backend/routers/config.py:193` (`apply_due_values`), `backend/routers/config.py:371` (`apply_due_values`); daftar job `backend/services/scheduler_service.py:79` (`JOBS`) tidak memuatnya |
| KF-10 / KP-11 `[dibaca]` | Kunci berlapis PT yang pemakainya membaca nilai grup — rincian di tabel "Perubahan › Server" | `backend/routers/sales_orders.py:355` (`default_payment_term_code`) dan jangkar di tabel itu |
| KF-10 `[dibaca]` | Nilai 0 diganti diam-diam: `payment.plan_tolerance_rupiah` 0 → 1, `case.holding_case_after_days` 0 → 3, padahal registry mengizinkan 0 | `backend/services/payment_plan_service.py:78` (`plan_tolerance_rupiah`); `backend/services/finance_case_service.py:85` (`holding_case_after_days`) |
| KF-11 `[dibaca]` | `role_home.*` (4 kunci) tidak punya pembaca; berkas yang didaftarkan sebagai pemakai tidak memuat `role_home` | `backend/config_catalog_core.py:921` (`role_home`); `backend/services/config_service.py:124` (`role_home`) hanya bawaan |
| | `tax.efaktur_enabled` tidak dibaca saat menghitung PPN maupun menerbitkan faktur; hanya dipaksa mati untuk PT bukan PKP dan diteruskan ke tampilan Pusat Pajak | `backend/config_catalog_core.py:45` (`tax.efaktur_enabled`); `backend/services/config_service.py:256` (`efaktur_enabled`); `backend/services/tax_center_service.py:161` (`efaktur_enabled`) |
| | Pemeriksa kesehatan meloloskan kunci di atas karena cukup menemukan nama daun (`'admin'`) di berkas mana pun yang didaftarkan | `backend/services/config_health.py:44` (`_mentions`) |

## Perubahan

### Data

`config_values` — tiga field penanda baru pada baris berjadwal yang dibatalkan (bukan field nilai; INV-CFG-03 diperluas:
penanda yang boleh diisi sekali = `applied_at`, `cancelled_at`):

| Field | Tipe | Arti |
|---|---|---|
| `cancelled_at` | teks ISO | Saat jadwal dibatalkan. Ada = baris diabaikan resolver dan `apply_due_values` |
| `cancelled_by`, `cancelled_by_id` | teks | Pembatal |
| `cancel_reason` | teks | Alasan |

Tanpa migrasi. Lapisan PT yang sudah tersimpan untuk kunci yang lapisannya dicabut tidak dihapus; resolver sudah
mengabaikan lapisan di luar `scopes`. Laporan unit memuat kueri pencarinya (`config_values` ber-`scope_type: "entity"`
untuk kunci tersebut).

### Server

**(1) Penimpaan terdaftar** — berkas baru `backend/services/config_overrides.py`:

| Fungsi | Perilaku |
|---|---|
| `PENIMPA: list[dict]` | Tiap butir: `id`, `keys`, `label`, `link` (`{"view": …, "key": …}`), dan fungsi `async cek(key, ctx, nilai) -> Optional[Any]` |
| `async def penimpa(key, ctx, nilai) -> Optional[dict]` | Butir pertama yang `cek`-nya mengembalikan nilai → `{"id", "label", "value", "link"}`; tidak ada → `None` |

| `id` | Kunci | Berlaku bila | Nilai dipakai | `label` |
|---|---|---|---|---|
| `pt_bukan_pkp` | `tax.ppn_rate` | `ctx.entity_id` terisi dan `business_entities.default_tax_mode != "ppn"` | 0.0 | "Status pajak PT ini: bukan PKP" (`link.view = "entities-access"`) |
| `wajib_transfer_antar_pt` | `allocation.allow_intercompany` | `value_of("inventory.intercompany_transfer_required", ctx)` benar | `False` | "Pengaturan “Wajib transfer sebelum menjual stok PT lain” sedang aktif" (`link.key`) |
| `master_grade_mutu` | `qc.grade_thresholds.a_max`, `qc.grade_thresholds.b_max` | Grade aktif `A` / `B` di `domain_registry.GRADES` punya `max_points` | `max_points` grade itu | "Batas poin di Master Grade Mutu" (`link.view = "grade-master"`) |

`config_resolver.resolve()`: sesudah pemenang lapisan ditentukan dan bila bukan simulasi, panggil `penimpa`. Bila ada:
`value` = nilai penimpa; tambah `stored_value` (nilai lapisan pemenang) dan `overridden_by`; `explain` mendapat lapisan
terakhir `{"layer": "override", "label": "Ditimpa aturan lain", "note": <label>}` sebagai pemenang; `LAYER_ORDER`
ditambah `"override"`. `resolve_group()` meneruskan `stored_value` dan `overridden_by` (atau `null`) pada tiap butir —
inilah isi baru jawaban `GET /api/config/effective` dan `GET /api/config/explain`. `get_effective_settings` dan
`get_allocation_policy` tetap menegakkan aturannya; uji memastikan keduanya sama dengan `value_of`.

**(2) Jadwal**:

| Tempat | Perubahan |
|---|---|
| `config_resolver.ensure_due_applied()` — baru | Menyimpan di memori proses waktu jatuh tempo terdekat dari baris `applied_at == ""` tanpa `cancelled_at`; bila sekarang ≥ waktu itu → `apply_due_values()` lalu hitung ulang. `set_value` berjadwal dan pembatalan memperbarui cache. Tanpa baris tertunda biayanya nol kueri |
| `config_service.get_global_settings()`, `config_resolver.policy_settings()` | Baris pertama memanggil `ensure_due_applied()` — semua pembaca lama lewat dua fungsi ini |
| `scheduler_service.JOBS` | Job baru `{"id": "config_apply_due", "label": "Aktifkan Pengaturan Terjadwal", "kind": "interval", "interval_minutes": 5, "fn": <pemanggil apply_due_values>, "link": "settings-config"}`, deskripsi: "Menerapkan perubahan pengaturan yang tanggal berlakunya sudah tiba." |
| `_stored_rows`, `apply_due_values`, `history` | Baris ber-`cancelled_at` tidak dihitung; di riwayat tampil dengan `cancelled: true` |
| `resolve()["scheduled"]` | Tiap butir ditambah `id`, `scope_type`, `scope_id` |

`POST /api/config/values/cancel-scheduled` · izin: `_may_edit` kunci itu + `_assert_scope_write` lapisannya · isi
`{"id": "<id baris config_values>", "reason": "…"}` · jawaban: baris yang dibatalkan.

| Kode | Keadaan | Pesan |
|---|---|---|
| 404 | Baris tidak ada | "Jadwal perubahan tidak ditemukan." |
| 409 | `applied_at` terisi atau `effective_from` sudah lewat | "Perubahan ini sudah berlaku, jadi tidak bisa dibatalkan. Simpan nilai baru bila ingin mengubahnya." |
| 409 | Sudah dibatalkan | "Jadwal ini sudah dibatalkan." |
| 400 | Kunci berisiko tinggi tanpa alasan | "Alasan pembatalan wajib diisi." |
| 403 | Tidak berwenang | pesan U unit KF-T1 |

**(3) KF-10 — nilai khusus PT harus dipakai** (serah-terima b):

| Kunci | Pemakai sekarang | Perbaikan |
|---|---|---|
| `finance.default_payment_term_code` (KP-11) | `backend/routers/sales_orders.py:355` (`default_payment_term_code`) membaca dokumen grup langsung | Fungsi baru `config_service.default_payment_term_code(entity_id)` = `value_of(key, {"entity_id": entity_id})`; pesanan memakainya dengan PT pesanan |
| `inventory.default_uom` | `backend/routers/products.py:116` (`default_uom`) tanpa PT | `value_of(key, {"entity_id": <PT aktif pembuat dari entity_ctx>})` |
| `notif.po_stage_stuck_days` | `backend/services/notification_service.py:399` (`po_stage_stuck_days`) dengan `entity_id` kosong | Dibaca per PT tiap PO (`po["entity_id"]`), disimpan sementara per PT selama satu putaran job |
| `notif.low_stock_division` | `backend/services/notification_service.py:195` (`low_stock_division`) dengan `entity_id` kosong; pindai stok tidak per PT | **Cabut lapisan PT**: `scopes=("global",)` |
| `receiving.block_over_remaining`, `receiving.supplier_uom_input_mode`, `receiving.require_supplier_item_for_supplier_uom` | `backend/services/receiving_uom_service.py:188` (`convert_doc_qty`), `backend/services/receiving_uom_service.py:309` (`uom_options`), `backend/services/receiving_uom_service.py:390` (`preview`), `backend/services/receiving_uom_service.py:494` (`preflight_scan`) memanggil `get_settings()` tanpa PT | `get_settings(task.get("entity_id") or "")` di keempatnya |
| `uom.warn_pct`, `uom.block_pct`, `uom.allow_override`, `uom.precision`, `uom.require_trail` | `backend/services/uom_rules_service.py:303` (`load_engine`), `backend/services/uom_rules_service.py:422` (`check_variance`) | Parameter baru `entity_id: str = ""` pada `load_engine` dan `check_variance`, diteruskan ke `get_settings(entity_id)`; 12 pemanggil (`grep -rn "load_engine(\|check_variance("`) mengirim PT dokumennya; pemanggil tanpa dokumen tetap nilai grup |
| `lot.*` saat inspeksi QC | `backend/services/qc_inspection_service.py:234` (`lot_settings`) | `lots.get_settings(roll.get("owner_entity_id") or "")` |
| `payment.plan_tolerance_rupiah` | `backend/services/payment_plan_service.py:78` (`plan_policy`): 0 → 1 | Registry `min=1`; `help` ditambah "Paling kecil Rp 1."; pembaca: `float(v) if v else default_of(key)` |
| `case.holding_case_after_days` | `backend/services/finance_case_service.py:85` (`policy`): 0 → 3 | Registry `min=1`; pembaca seperti di atas |

Bila `config_registry.default_of` belum ada (lahir di KF-T2), tambahkan di sini: `require(key)["default"]`.

**(4) KF-11 — kunci aktif yang tidak menggerakkan mesin**:

| Kunci | Keputusan | `not_used_reason` |
|---|---|---|
| `role_home.admin`, `role_home.manager`, `role_home.sales`, `role_home.warehouse` | Tandai `not_used` | "Halaman awal tiap peran ditetapkan sistem per peran; pengaturannya akan tersedia di Peran & Hak Akses." |
| `tax.efaktur_enabled` | Tandai `not_used`; `tax_center_service` mengirim `efaktur_enabled = is_pkp` | "Penerbitan faktur pajak mengikuti status PKP di profil PT." |
| `contra_bon.qty_tolerance_percent` | Pastikan `not_used` (dikerjakan KF-T2; kerjakan di sini bila belum) | "Toleransi jumlah kontrabon mengikuti pengaturan 'Toleransi jumlah tagihan pemasok'." |

`config_health._mentions` → `_mentions(ref, key)`: (a) bila rujukan berbentuk `berkas.py:fungsi`, fungsi itu harus ada
(tidak ada → `MISSING`) dan hanya badan fungsi itu yang dipindai (`ast`); (b) cocok = kunci utuh muncul, **atau** segmen
induk dan daun sama-sama muncul; daun saja tidak cukup. Kunci yang memerah setelah pengetatan diselesaikan satu per satu:
rujukan diperbaiki bila pembacanya nyata, atau kunci ditandai `not_used`; daftarnya masuk laporan.

### Pengaturan

Tidak ada kunci baru. Perubahan entri: `notif.low_stock_division` `scopes=("global",)`; `min=1` pada dua kunci di
tabel (3); enam kunci `not_used` di tabel (4).

### Izin dan peran

Tidak ada.

### Layar

`frontend/src/features/settings/config/SettingCard.jsx`:

- Bila `item.overridden_by` ada: baris nilai menampilkan `item.value` dengan lencana **Ditimpa**, dan di bawahnya
  "Ditimpa oleh: {overridden_by.label}. Nilai yang tersimpan ({stored_value}) tidak dipakai." dengan tautan
  **Buka sumbernya** (`openConfig` untuk `link.key`, pindah layar untuk `link.view`). Tombol ubah tetap ada.
- Baris jadwal: "Terjadwal: {nilai} mulai {tanggal WIB} · {Global | nama PT}" + tombol **Batalkan jadwal** (tampil bila
  `can_edit`). Konfirmasi: "Batalkan perubahan terjadwal ini? Nilai yang berlaku sekarang tidak berubah." dengan isian
  alasan (wajib untuk kunci berisiko tinggi). Berhasil: "Jadwal dibatalkan."
- `configApi.cancelScheduled(body)` baru.

`frontend/src/features/finance/TaxCenterView.jsx`: tidak berubah bentuk; nilai "e-Faktur" kini mengikuti status PKP.

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | `ent_kanda` bukan PKP (seed) | `GET /api/config/effective?q=tax.ppn_rate&entity_id=ent_kanda`; `value_of`; `get_effective_settings("ent_kanda")` | `value == 0`, `stored_value == 12.0`, `overridden_by.id == "pt_bukan_pkp"`; `value_of` = 0 = `tax.ppn_rate` pembaca lama |
| U2 | B | — | Sama untuk `ent_ksc` | `value == 12.0`, `overridden_by is None` |
| U3 | B | — | `GET /api/config/effective?q=allocation.allow_intercompany&entity_id=ent_ksc`; lalu Admin menyimpan `inventory.intercompany_transfer_required=false` lapisan PT `ent_ksc` (dengan alasan); baca lagi untuk `ent_ksc` dan `ent_kanda` | Awal: `value False`, ditimpa `wajib_transfer_antar_pt`. Sesudah: `ent_ksc` `True` tanpa penimpa dan `get_allocation_policy("ent_ksc")["allow_intercompany"] is True`; `ent_kanda` tetap `False` |
| U4 | B | Grade `A` di master ber-`max_points` 18 | `value_of("qc.grade_thresholds.a_max")`; `GET /api/config/explain?key=…` | 18; lapisan terakhir `override` menjadi pemenang |
| U5 | B | — | Jadwalkan `ar.grace_days` +5 berlaku 2 detik lagi; tunggu 3 detik; baca `get_effective_settings(None)["ar"]["grace_days"]` tanpa memanggil endpoint mana pun | Sama dengan `value_of("ar.grace_days")` (nilai baru) — `t5_jadwal_pengaturan.py` baris "3 detik kemudian" menampilkan angka yang sama di kedua pembaca |
| U6 | B | — | `scheduler_service.JOB_MAP["config_apply_due"]`; jalankan `fn` dengan satu baris tertunda yang jatuh tempo | Job ada, `interval_minutes == 5`; jawaban `applied == 1`; dokumen `system_settings` memuat nilai baru |
| U7 | B | Jadwalkan `ar.grace_days` berlaku 1 jam lagi | `POST /api/config/values/cancel-scheduled`; `resolve("ar.grace_days")["scheduled"]`; ulangi `POST` | 200 dengan `cancelled_at` terisi; `[]`; 409 "Jadwal ini sudah dibatalkan." |
| U8 | B | Baris yang sudah berlaku | `POST …/cancel-scheduled` | 409 "Perubahan ini sudah berlaku…"; baris tidak berubah |
| U9 | B | Sopir (`02` §6) | `POST …/cancel-scheduled` untuk baris U7 baru | 403; `cancelled_at` tidak ada |
| U10 | B | Admin: `finance.default_payment_term_code="NET7"` lapisan PT `ent_ksc` | `default_payment_term_code("ent_ksc")`, `("ent_kanda")`; cari `system_settings.find_one` di `routers/sales_orders.py` sekitar termin | `"NET7"`; `"NET30"`; pembacaan langsung dokumen grup tidak ada lagi |
| U11 | A | Seperti U10, data acuan | Buat pesanan tanpa `payment_term_code` di tiap PT | Pesanan `ent_ksc` bertermin NET7, PT lain NET30 |
| U12 | B | Admin: `uom.block_pct=50` lapisan PT `ent_ksc` (grup 5) | `check_variance(100, 110, entity_id="ent_ksc")`; `…entity_id="ent_kanda"` | `level != "block"`; `level == "block"` (selisih 10 % ≥ 5 %) |
| U13 | B | Admin: `receiving.block_over_remaining=false` lapisan PT `ent_ksc`; dua tugas penerimaan fixture (sisa 10) di `ent_ksc` dan `ent_kanda` | `preflight_scan` dengan jumlah 12 pada masing-masing | `ent_ksc` tidak ditolak karena melebihi sisa; `ent_kanda` ditolak |
| U14 | B | — | Admin `PUT` `notif.low_stock_division` lapisan PT; `PUT` `payment.plan_tolerance_rupiah=0`; `PUT` `case.holding_case_after_days=0` | Tiga-tiganya 400 (lapisan tidak didukung; minimum 1; minimum 1) |
| U15 | B | — | Status enam kunci tabel (4); Admin `PUT` `role_home.admin` | Semua `not_used`; 400 dengan alasan dari tabel |
| U16 | B | Entri tiruan: kunci `role_home.admin`, `consumers=("permissions_config.py",)`; entri tiruan dengan `consumers=("services/config_service.py:tidak_ada",)` | `config_health.check_entry` | `STALE`; `MISSING`. `config_health.report()["broken"] == []` pada registry nyata |
| U17 | layar (uji jalan) | Login Admin, PT `ent_kanda` | Pengaturan › Keuangan & Pajak › kartu tarif PPN; jadwalkan lalu batalkan satu perubahan | Kartu menampilkan 0 dengan "Ditimpa oleh: Status pajak PT ini: bukan PKP…"; baris jadwal menyebut cakupan; setelah dibatalkan baris hilang dan Riwayat menandainya dibatalkan |

## Langkah kerja

**(a) Jalur baru, pemakai lama belum disentuh:**

1. `backend/tests_mem/test_KFT3_nilai_dipakai.py`: U1–U9 merah.
2. `config_overrides.py` + sambungan di `resolve`/`resolve_group` (U1–U4).
3. `ensure_due_applied`, job penjadwal, pembatalan jadwal (U5–U9). Gate; catat SHA.

**(b) Pengalihan pemakai dan pematian yang palsu:**

4. Tabel (3) baris demi baris, tiap baris dengan ujinya (U10–U14).
5. Tabel (4) dan pengetatan `config_health` (U15, U16); bereskan kunci yang memerah.
6. Layar (U17); `t1_config.py` dijalankan ulang — dua penyimpangan `ent_kanda` kini berbentuk "resolver = pembaca lama =
   0, `stored_value` = nilai tulis". Gate; laporan dengan SHA (a) dan (b).

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (field `config_values.cancelled_*`); `CODEBASE_MAP.md` (`services/config_overrides.py`);
`memory/PRD.md` (penimpaan terdaftar, pembatalan jadwal); komentar INV-CFG-03 di `config_resolver.py`.

## Di luar lingkup

- Penimpaan per dokumen yang sudah dijelaskan teks kartu (denda per rencana pembayaran, susut per kontrak makloon,
  `approval.extra_levels`) dan simulator yang rumusnya berbeda dari mesin → KF-T4.
- Tombol "Default" di cakupan PT, nilai yang tampil saat cakupan Global dipilih → KF-T4 (KF-12).
- Isian form Pelanggan yang menimpa `allocation.lot_mode` / `allocation.dye_lot_strict` → KF-T5.
- Halaman awal peran yang bisa diatur → PR-T4. Mengubah status PKP PT → KP-T1. Penerima dan ambang pengingat per PT → KP-T7.
- Menjadikan pemeriksa kesehatan sebagai gate → KF-T8.

## Asumsi dan risiko

- `ASUMSI:` `tax.efaktur_enabled` tidak dihidupkan sebagai sakelar tersendiri karena status PKP sudah menjadi sumbernya
  (K-08); tidak ada hitungan pajak yang berubah.
- `ASUMSI:` satuan dasar bawaan produk baru mengikuti PT aktif pembuatnya.
- `ASUMSI:` satu proses server (keadaan sekarang). Dengan beberapa proses, cache `ensure_due_applied` proses lain baru
  segar saat job lima menit berjalan.
- `RISIKO:` meneruskan PT ke mesin konversi satuan mengubah hasil bagi PT yang sudah menyimpan nilai khusus (yang selama
  ini diabaikan). Laporan memuat daftar kunci berlapis PT di data acuan sebelum (b). Membatalkan (b): kembalikan
  pemanggil ke tanpa `entity_id`; (a) tidak terpengaruh.
- `RISIKO:` `value_of("tax.ppn_rate")` kini 0 untuk PT bukan PKP; pemakai yang mengandalkan nilai mentah harus memakai
  `resolve()["stored_value"]`. Pencarian pemakai kunci itu dicatat di laporan.
