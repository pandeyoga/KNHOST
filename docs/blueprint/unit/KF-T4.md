# KF-T4 — Pusat Pengaturan berbahasa awam, berkelompok rapi, dan bereditor yang layak

| | |
|---|---|
| Gelombang | Jalur pengaturan (K) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KF-T2 |
| Menutup temuan | KF-12, KF-13, KF-UX (28 butir; pembagiannya di "Di luar lingkup") |
| Keputusan | — |
| Standar | §2.1, §4 (L1, L2, L5, L6, L7), §6 |
| Lingkungan uji | B; uji jalan layar di A |

## Tujuan

Pemilik usaha bisa membaca setiap kartu pengaturan tanpa bertanya ke pengembang, menemukannya di kelompok yang masuk
akal, dan mengubah daftar atau tabel tanpa mengetik kode. Tombol pengembali berarti persis seperti labelnya, dan "Coba
dulu" memberi jawaban yang sama dengan mesin.

## Keadaan sekarang

Hitungan registry `[dijalankan]` (modul `config_registry` dimuat pada `3132cc4`: 310 kunci, 23 kelompok); butir lain
`[dibaca]`. "Lampiran A" = `docs/audit/konfigurasi-peran-2026-11-13/lampiran/A_pengaturan_ux.md`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | 23 kelompok tanpa sub-judul (terbesar 40, 27, 26, 25 kunci), dipetakan ke 10 layar `settings-cfg-*`; dua layar memuat 85 dan 69 kunci | `backend/config_registry.py:60` (`GROUPS`); `frontend/src/features/settings/config/configGroupViews.js:24` (`CONFIG_GROUP_VIEWS`) |
| 2 | Pendaftaran kunci hanya mewajibkan label, penjelasan, dan dampak terisi. 51 label lebih dari 45 karakter (terpanjang 72); 24 kunci angka tanpa satuan; 91 kunci angka aktif boleh bernilai 0 dan pada 75 di antaranya penjelasan tidak memuat angka 0; tidak ada dua label sama | `backend/config_registry.py:204` (`label`) |
| 3 | Penjaga bahasa repo tidak memeriksa teks registry: polanya mengenali kunci kamus berkutip (`"label": "…"`), sedangkan katalog menulis argumen `label="…"` | `scripts/audit_i18n_id.py:385` (`RE_PY_TEKS`) |
| 4 | Tautan langsung menebak kelompok dari awalan kunci; daftar id kelompok disalin tangan dari registry | `frontend/src/features/settings/config/configDeepLink.js:35` (`LEGACY_DEEPLINK`); `frontend/src/features/settings/config/configDeepLink.js:79` (`CONFIG_GROUP_IDS`) |
| 5 | Tombol "Default" tampil setiap kali nilai bukan milik PT yang dipilih. Ia mengirim cakupan aktif, dan server menulis nilai bawaan registry **pada lapisan itu** dengan alasan otomatis "Kembalikan ke default sistem", tanpa konfirmasi | `frontend/src/features/settings/config/SettingCard.jsx:190` (`onReset`); `frontend/src/features/settings/config/SettingsHub.jsx:232` (`onReset`); `backend/routers/config.py:299` (`reset_value`) |
| 6 | Mencabut lapisan PT sudah ada ("Kembalikan ke global"), tetapi hanya ditawarkan bila PT punya nilai sendiri dan tidak memeriksa kewajiban alasan | `frontend/src/features/settings/config/SettingsHub.jsx:240` (`onClearEntity`); `backend/routers/config.py:322` (`clear_value_layer`); `backend/services/config_resolver.py:408` (`clear_layer`) |
| 7 | "Coba dulu" QC memberi A/B/C dari dua batas, sedangkan mesin memakai grade aktif di Master Grade Mutu dan membagi rentang A–B menjadi A1, A2, B. "Coba dulu" pajak memperlakukan `tax.efaktur_enabled` sebagai status PKP, sedangkan mesin memakai status PKP master PT | `backend/services/config_simulator.py:220` (`_qc_grade`); `backend/services/qc_inspection_service.py:105` (`grade_from_points`); `backend/services/qc_inspection_service.py:23` (`grade_thresholds`); `backend/services/config_simulator.py:39` (`_tax`); `backend/services/config_service.py:266` (`compute_tax`) |
| 8 | Data kartu tidak memuat `value_format` dan `permission`, sehingga editor "satu pola per baris" tidak pernah terpilih | `backend/services/config_resolver.py:281` (`resolve_group`); `frontend/src/features/settings/config/SettingEditor.jsx:142` (`LinesField`) |
| 9 | 14 kunci bertipe daftar diketik dalam satu kotak berkoma; server hanya memeriksa bentuk daftar; mesin membuang butir tak sah diam-diam | `frontend/src/features/settings/config/SettingEditor.jsx:65` (`ListField`); `backend/config_registry.py:342` (`_coerce_type`); `backend/services/ar_aging_service.py:52` (`edges`); `backend/services/config_service.py:509` (`_sanitize_alloc`) |
| 10 | `approval.extra_levels` disunting sebagai JSON. Bentuk tersimpannya `{jenis dokumen: [{min_amount, role, label}]}` dan hanya dibaca untuk `purchase_order` | `frontend/src/features/settings/config/SettingTableEditor.jsx:221` (`JsonTable`); `backend/config_catalog_core.py:342` (`approval.extra_levels`); `backend/services/config_service.py:336` (`build_approval_chain`) |
| 11 | Tanggal, kamus multi-baris, kode syarat bayar, satuan, dan departemen diketik di kotak teks satu baris. `receiving.mode` bisa diubah dari kartu dan dari panel khusus yang berdialog konfirmasi dan beralasan | `frontend/src/features/settings/config/SettingEditor.jsx:149` (`cfg-input-wide`); `frontend/src/features/wms/grn/GrnModePanel.jsx:35` (`askReason`) |
| 12 | Pada cakupan Global nilai yang tampil tetap dihitung untuk PT aktif; draf kartu tidak dikosongkan saat cakupan berganti; Simpan aktif sebelum alasan wajib diisi | `frontend/src/features/settings/config/SettingsHub.jsx:112` (`ctx`); `frontend/src/features/settings/config/SettingCard.jsx:25` (`draft`); `frontend/src/features/settings/config/SettingCard.jsx:178` (`submit`) |
| 13 | Istilah teknis tampil: "Default sistem", "Global (pengaturan lama)", "Entitas"; "Semua entitas (Global)", "Pilih entitas…"; "Status wiring"; "append-only"; "Hanya admin yang boleh mengubah setting ini"; "diatur di Pusat Pengaturan". Nama peran di registry peran "Manajer" (Lampiran A mengandaikan "Manager") | `backend/services/config_resolver.py:45` (`LAYER_LABEL`); `frontend/src/features/settings/config/configApi.js:163` (`SCOPE_LABEL`); `frontend/src/features/settings/config/SettingsScopeBar.jsx:75` (`entityOpts`); `frontend/src/features/settings/config/ConfigDrawers.jsx:135` (`wiring_status`); `frontend/src/features/settings/config/SettingsHub.jsx:425` (`cfg-history-tab`); `frontend/src/features/settings/config/SettingCard.jsx:238` (`notUsed`); `frontend/src/features/settings/config/ConfigRedirectCard.jsx:45` (`cfg-redirect-title`); `backend/role_registry.py:60` (`ROLES`) |
| 14 | Contoh tersembunyi di balik "Contoh & detail teknis"; kartu menyebut lapisan "Pelanggan tertentu" walau layarnya belum ada; kartu hanya-grup beralasan "menyangkut tampilan aplikasi" | `frontend/src/features/settings/config/SettingCard.jsx:123` (`showMore`); `frontend/src/features/settings/config/SettingCard.jsx:132` (`SCOPE_LABEL`); `frontend/src/features/settings/config/SettingCard.jsx:100` (`globalOnly`) |
| 15 | Pencarian tidak mencakup contoh dan padanan kata; riwayat hanya bisa disaring per kunci dan cakupan dan nilainya tampil mentah; pesan galat simpan memakai kunci teknis dan kata "level" | `backend/config_registry.py:291` (`search`); `backend/routers/config.py:351` (`read_history`); `frontend/src/features/settings/config/configApi.js:141` (`shortVal`); `backend/config_registry.py:398` (`_bounded`); `backend/services/config_resolver.py:318` (`set_value`) |

## Perubahan

### Data

Tidak ada. Pada kunci mana pun tidak boleh berubah: `key`, `type`, `default`, `min`, `max`, `scopes`,
`options[].value`, `consumers`, `permission`, `status`, dan bentuk nilai tersimpan.

### Server

| Bagian | Kontrak |
|---|---|
| `config_registry.GROUPS` | 13 kelompok (tabel (c)); tiap kelompok mendapat `sections: [{id, label, advanced}]`. `advanced: True` = bagian "Lanjutan (teknis)" yang tertutup secara bawaan |
| `GROUP_ALIASES: Dict[str, Tuple[str, str]]` | id kelompok lama → (id kelompok baru, id sub-judul tujuan atau `""`). Dipakai `by_group`, `GET /api/config/effective?group=`, dan layar |
| `E(...)` argumen baru; semua `E(...)` di `config_catalog_*.py` diperbarui | `section: str` (wajib; terdaftar pada kelompoknya) · `items: str = ""` untuk tipe `list`: `options` \| `roles` \| `int_asc` \| `text` · `ordered: bool = False` · `ref: str = ""` untuk tipe `text`: `payment_term` \| `uom` \| `department` · `edit_at: Optional[dict]` (`{view, preset}`; kartu tanpa editor). `ROW_SHAPES` + `grouped_list` (objek `{nilai kolom pertama: [baris]}` disunting sebagai baris datar); `VALUE_FORMATS` + `date` (kosong atau `YYYY-MM-DD` sah), `multiline` |
| `themes_for(key) -> List[str]` | Tema lintas kelompok dari pola kunci: `persetujuan` = `approv\|dual_control\|require_so_validation\|require_verification_before_confirm\|decision_roles\|treatment_roles\|direksi` (35 kunci); `pengingat` = `remind\|sla_\|_sla\|stuck\|escalat\|holding_max_age\|holding_case_after\|unbilled_gr_age\|wait_(warn\|late)\|keep_max_age\|drift_alert` (18); `toleransi` = `toleran` (15) |
| `coerce` | Sesudah tipe: `options` → tiap butir ada di `options[].value`; `roles` → tiap butir id peran yang dikenal `role_registry` (termasuk peran kustom); `int_asc` → bilangan bulat > 0 dan menaik; `text` → tidak kosong. Semua daftar: tanpa butir kembar. `allocation.priority_order`: `owner` butir pertama. `grouped_list`: kolom pertama ada di pilihannya; kolom peran id peran yang dikenal; `min_amount` ≥ 0. Pesan galat simpan memakai `label`, bukan `key`: "'{label}' paling kecil {min}{satuan}.", "'{label}' paling besar {max}{satuan}.", "'{label}': butir '{butir}' tidak dikenal. Pilihan: {daftar label}.", "'{label}' tidak bisa dibedakan per {nama lapisan}." |
| `search(term)` | Mencari juga di `example`, label sub-judul, dan padanan dua arah `SEARCH_SYNONYMS`: pemasok/supplier/vendor · cicilan/angsuran · DP/uang muka · terlambat/telat · roll/gulungan · utang/hutang · PT/entitas/badan usaha · pesanan/SO/order · syarat bayar/termin/term |
| `config_resolver.resolve_group` | Tiap butir menambah `section`, `themes`, `value_format`, `items`, `ordered`, `ref`, `ref_options`, `edit_at`, `permission`, `permission_label` (label modul akses pemilik izin, dari `access_modules`), `never_changed` (benar bila tidak ada baris `config_values` untuk kunci itu dan nilai efektif = `default`). `ref_options` dari fungsi baru `config_resolver.ref_options(ref, entity_id)`: `payment_term` → baris efektif master Syarat Bayar (kode · nama); `uom` → koleksi `uoms`; `department` → nama unit organisasi yang dipakai `notification_audience._users_in_division`. Saat simpan, nilai ber-`ref` harus ada di daftar itu (atau kosong bila `default` kosong) |
| `config_resolver.LAYER_LABEL` | `code_default` "Bawaan sistem" · `legacy_global`, `global` "Aturan grup" · `legacy_entity`, `entity` "Khusus PT" · `customer` "Khusus pelanggan" · `supplier` "Khusus pemasok" · `product` "Khusus produk" · `document` "Khusus dokumen" · `hypothetical` "Coba dulu (belum disimpan)" |
| `GET /api/config/effective` | `group` menerima id lama. Parameter baru `scope=global`: nilai dihitung **tanpa** lapisan PT, dan tiap butir memuat `entity_overrides: [{entity_id, entity_label, value}]` untuk PT yang boleh dilihat pengguna dan punya nilai sendiri |
| `POST /api/config/values/reset` dan `/values/clear` | `reset` tetap menulis nilai bawaan pada lapisan yang disebut; `clear` tetap mencabut lapisan. Keduanya: kunci `requires_reason` tanpa alasan → 400 "'{label}' berisiko tinggi — alasan wajib diisi." (tidak ada lagi alasan otomatis). Alasan bawaan kunci lain: "Dikembalikan ke nilai bawaan sistem" / "Kembali mengikuti nilai grup" |
| `POST /api/config/simulate` | `config_simulator.run(sim_id, values, sample, facts)`; `facts = {"is_pkp": …}` dari master PT pada `ctx.entity_id` (tanpa PT: benar). `_tax` memanggil fungsi murni baru `config_service.ppn_breakdown(subtotal, rate, mode, is_pkp, use_nl) -> dict` yang juga dipakai `compute_tax`; `tax.efaktur_enabled` keluar dari `needs`. `_qc_grade` memanggil fungsi murni baru `qc_inspection_service.thresholds_from(a_max, b_max, a1_max=None, a2_max=None) -> dict` (dipakai juga `grade_thresholds`) lalu `grade_from_points` |
| `GET /api/config/history` | Parameter baru `group`, `changed_by`, `date_from`, `date_to`, `offset`; jawaban `{rows, total}`, `total` = jumlah sebelum dipotong halaman |

Penjaga baru `scripts/guardrails/verify_config_text.py` (INV-CFG-TXT; blok statik `scripts/gate.sh`; `--self-test` satu
kasus merah per aturan) memeriksa semua teks kunci dan kelompok. Hasil wajib **0 pelanggaran**, bukan garis dasar:

| Aturan | Isi |
|---|---|
| T1, T2 | Label ≤ 45 karakter; tidak ada dua label sama (tanpa membedakan huruf besar) |
| T3 | Tanpa kata terlarang `02` §4 L1: `scope`, `override`, `threshold`, `fallback`, `payload`, `posting`/`diposting`; tanpa id teknis (`ent_…`, `cr_…`, pola `kata.kata` yang merupakan kunci registry atau izin, pola `kata_kata`); tanpa kode HTTP `(4xx)`; tanpa kode keputusan (`DEC-`, `LN-`, `AS-`, `KLX-`, `P18`, `M-3`) |
| T4 | Kunci bertipe `int`, `pct`, `money`, `decimal`, `duration` wajib ber-`unit`. Pengecualian tunggal bercatatan: `commission.discount_threshold` (satuannya mengikuti `commission.discount_threshold_type`) |
| T5 | Kunci angka aktif yang `min`-nya kosong atau ≤ 0: `help` memuat angka 0 yang berdiri sendiri (pola `(?<![\d.,])0(?![\d.,])`) |
| T6 | Tanpa kata yang diganti tabel (b): `entitas`, `badan usaha`, `supplier`, `vendor`, `customer`, `approval`, `approver`, `pengusul`, `manager`, `role`, `default`, `payroll`, `qty`, `invoice`, `refund`, `round`, `ronde`, `sampel`, `setting`, `wiring`; pada label juga `ambang`, `SJ`, `GRN`. Dikecualikan: frasa yang persis sama dengan label menu di `hubTabs.js`/`navStructure.js` |
| T7 | `section` tiap kunci terdaftar; sub-judul yang tidak `advanced` berisi paling banyak 14 kunci |

### Pengaturan

Tidak ada kunci baru.

**(a) Teks pengganti.** Daftar kerja = bagian "Lampiran A — Teks pengganti per kunci": 208 baris (166 mengganti label;
42 "label tetap"). Per kelompok lama: Uang Masuk 9 · Harga 11 · Persetujuan 10 · Pajak 2 · Dasar Keuangan 4 · Pembelian
4 · Penerimaan 21 · Stok 34 · Kualitas 11 · Lot 5 · Makloon 2 · SDM 5 · Tampilan 7 · Koreksi 7 · Dokumen 3 · R&D 24 · Bank
1 · Kasus 5 · Kontrabon 7 · Antar-PT 6 · Notifikasi 2 · Asisten 21 · Retur 7. Hasilnya 0 label > 45 karakter, 0 kembar.

| # | Aturan penerapan |
|---|---|
| 1 | Kolom "Usulan": "Label" → `label`; "Penjelasan" → `help`; "Dampak" → `impact`; "Contoh" → `example`; "Opsi" → `options[].label` sesuai urutan; "Satuan"/"Isi satuan" → `unit`. Bagian yang tidak disebut tidak diubah |
| 2 | Tabel (b) menang atas teks Lampiran A: "supplier" ditulis "pemasok", "manager" ditulis "Manajer", "badan usaha"/"entitas" ditulis "PT". Nama layar yang dikutip ditulis persis seperti di menu |
| 3 | Lima pola umum di akhir Lampiran A berlaku untuk **semua** kunci: contoh memakai label pilihan; tanpa kode HTTP dan nama isian; "payroll" → "penggajian", "field" → "isian"; persen gaya Indonesia ("1%"); kode keputusan dihapus dari sumbernya. 102 kunci di luar Lampiran A hanya disentuh sejauh diperlukan T3–T6 |
| 4 | Arti 0 (T5): baca fungsi di `consumers`, lalu tulis akibat nyata nilai 0 ("Isi 0 bila …" atau "0 = …"). `min` tidak diubah |
| 5 | Satuan (T4): `sales.keep_max_age_days`, `ai.chat_retention_days`, `ai.anomaly_cover_days` hari · `commission.discount_factor` × komisi · `receiving.min_photo_short_side_px`, `receiving.ocr_image_max_side` piksel · `receiving.ocr_max_output_tokens`, `ai.max_output_tokens` token · `receiving.ocr_max_pages` halaman · `receiving.ocr_monthly_budget_usd`, `ai.monthly_budget_usd` USD · `receiving.ocr_budget_warn_pct`, `cutting.waste_limit_pct`, `ai.route_threshold_pct`, `ai.anomaly_drop_pct` % · `ai.max_tool_rounds` kali · `ai.result_rows_to_model` baris · `ai.daily_question_limit` pertanyaan/hari · `ai.template_cache_minutes` menit · `rnd.design_code_seq_digits` digit · `rnd.design_acc_min_score` poin · `rnd.kpi_penalty_rework`, `rnd.kpi_penalty_overdue` poin per 1%. Diganti: `qc.grade_thresholds.*` "poin/100 yd²" → "poin"; `rnd.max_rounds` "round" → "kali" |
| 6 | Catatan Lampiran A yang bukan teks: pindah kelompok → (c); ganti editor → "Layar"; ubah status atau arti (`tax.efaktur_enabled`, `role_home.*`, `contra_bon.qty_tolerance_percent`) mengikuti hasil KF-T2/KF-T3 — teks ditulis untuk status yang berlaku saat unit dikerjakan; pilihan yang artinya kembar (`allocation.lot_selection` FEFO, `lot.alias_mode`) **tidak dihapus**, labelnya ditulis "… (sama dengan {pilihan lain})". Kalimat yang menjanjikan lapisan pelanggan atau produk dihapus sampai layar KF-T5 ada |

| Kunci (contoh) | Sebelum | Sesudah |
|---|---|---|
| `sales.require_so_validation` | "Pesanan wajib disahkan manajer sebelum dikonfirmasi (persetujuan nilai)" (71) | "Pesanan wajib disetujui manajer" (31) |
| `cutting.wait_late_minutes` | "Meja Cutting — batas merah/terlambat (menit) hasil potong belum diterima" (72) | "Meja potong: tanda merah setelah" (32) |
| `receiving.ocr_reasoning_effort` | "Reasoning effort OCR"; pilihan none/low/medium | "Ketelitian AI membaca surat jalan" (33); pilihan Tanpa/Rendah/Sedang |
| `amendment.dual_control` · `approval.matrix_sod` | "Pengusul tidak boleh menyetujui usulannya sendiri" (49) · "Pengaju tidak boleh menyetujui dokumennya sendiri" (49) | "Koreksi: pengaju tak boleh setujui sendiri" (42) · "R&D: pengaju tak boleh setujui sendiri" (38) |
| `inventory.intercompany_transfer_required` | "Wajib transfer sebelum jual stok entitas lain"; contoh "… ditolak (400)" | "Jual stok PT lain wajib lewat transfer" (38) |
| `lot.enforcement_mode` | "Ketegasan pengisian nomor lot"; contoh "block → …" | "Nomor lot wajib diisi saat terima barang?" (41); contoh "Tolak bila kosong → …" |
| `purchasing.require_supplier_master` · `finance.default_payment_term_code` | "PO wajib memilih supplier master"; "supplier_id kosong" · "Term pembayaran default" | "PO wajib pilih pemasok terdaftar" (32) · "Syarat bayar bawaan pesanan baru" (32) |
| `payment.plan_tolerance_rupiah` · `hr.feature_toggles.npwp_required` | contoh "… selisih Rp 1 dengan toleransi Rp 1 → DITOLAK" · dampak tentang komponen slip gaji | contoh "… → diterima; selisih Rp 2 → ditolak" · dampak "Data karyawan baru tidak bisa disimpan tanpa NPWP. Tidak mengubah hitungan gaji." |
| `ai.max_output_tokens` · `saga.stuck_lock_minutes` | "Maks token jawaban" · "Umur kunci saga yang diperingatkan" | "Batas panjang jawaban AI" (24) · "Proses macet: beri tahu admin setelah" (37) |
| `rnd.spec_approval_roles` | "Peran yang boleh meng-ACC spesifikasi & merilis produk" (54) | "Siapa menyetujui spesifikasi & rilis produk" (43) |

**(b) Satu istilah.** Tabel bagian 3 Lampiran A memuat 38 baris konsep; semuanya dipakai, dengan tiga penyesuaian ke
`02` §4 L2 dan registry peran (PT, pemasok, Manajer). Selaras `KN_32`: singkatan PO, QC, HPP, RFID tetap.

| Dipakai | Menggantikan |
|---|---|
| **PT**; "grup" = semua PT; "Semua PT" · **antar-PT** · **pelanggan** · **pemasok** ("mitra makloon" khusus makloon) · "PO kita" | entitas, badan usaha, perusahaan (sebagai badan hukum) · antar entitas · customer, pembeli, toko · supplier, vendor · klien |
| **persetujuan / disetujui** · **penyetuju** · **pengaju** | ACC (kecuali nama status tercetak di layar R&D), approval, disahkan · approver · pengusul |
| **Manajer** · **Admin (Direksi)** saat pertama disebut, lalu "Admin" · **peran** · **bawaan** | manager · Direksi, pemilik, owner · role · default |
| **toleransi** (selisih yang dimaafkan) · **batas** (angka tertinggi/terendah) · "**mulai** (nilai)" untuk persetujuan | ambang |
| Pilihan tiga tingkat **Biarkan / Beri peringatan / Tolak** (atau **Tahan** untuk barang); **ditolak** = aksi dibatalkan, **ditahan** = menunggu keputusan · **aktif / mati** | enam susunan kata lama; blokir, blok keras, block · hidup, nyala, OFF, nonaktif |
| **pesanan** · **PO**, **permintaan pembelian** · **jumlah** | SO, order, Sales Order · Purchase Order, PR, Purchase Requisition · qty |
| **tagihan** · **Faktur Pajak** (hanya pajak) · **kwitansi** (bukti terima uang) · **surat jalan** (ditulis lengkap) · **penerimaan barang** | invoice, bill, faktur (bukan pajak) · SJ · GRN, GR, Barang Masuk |
| **syarat bayar**; "tempo" = lama kredit · **koreksi dokumen** · **pengembalian dana** · **saldo pelanggan** (nama akun Store Credit tetap, `KN_32` §4.5) · **biaya pokok (HPP)** | term, termin · amandemen · refund · deposit · WAC |
| **peringatan** (muncul saat itu) · **pengingat** (kiriman terjadwal) · "dalam … hari" · **dinaikkan ke atasan** · **tingkat** | warn · jendela, rentang, horizon · eskalasi · jenjang, level |
| **putaran** · **sample** · **departemen** (SDM; "divisi" hanya matriks R&D) · **penggajian / slip gaji** · **stok** (barang di gudang; "persediaan" = nilai di pembukuan) · "**dicatat di pembukuan**" · **produk** (master) / **barang** (fisik) | round, ronde · sampel · payroll · jurnal, GL, Dr/Cr, posting · SKU, artikel (di label) |
| **Pengaturan** (menu), **pengaturan** (satu kartu), "Semua pengaturan" (layar cari) · "**Berlaku untuk**" | Pusat Pengaturan, setting, konfigurasi, setelan · cakupan, level, lapisan |

**(c) Kelompok baru.** Penempatan memakai pola kunci; pola yang lebih khusus menang. Kunci yang lahir sesudah `3132cc4`
mengikuti pola awalannya (asumsi retur → `retur-koreksi`·`retur`; `interco_payment.*` → `pajak-pembukuan`·`antar-pt`).

| id · label (jumlah pada `3132cc4`) | Pertanyaan | Sub-judul: pola kunci (jumlah) |
|---|---|---|
| `penjualan` · Penjualan & harga (25) | Siapa boleh menurunkan harga, kapan pesanan boleh jalan, dan bagaimana komisi sales dihitung? | `harga` Harga & diskon: `sales.allow_*_discount`, `sales.sample_payment_tolerance_pct`, `pricelist.*` (6) · `alur-pesanan` Alur pesanan: `sales.keep_max_age_days`, `sales.allow_partial_shipment`, `sales.quotation_enabled`, `sales.require_so_validation`, `sales_admin.*` (5) · `komisi` Komisi sales: `commission.*` (8) · `saran-pos` Saran produk di kasir (POS): `pos.*` (6) |
| `pembayaran-pelanggan` · Pembayaran pelanggan (24) | Kapan pelanggan harus bayar, dan apa akibatnya kalau telat atau bayarnya tidak pas? | `syarat-bayar` Syarat bayar, DP & cicilan: `finance.default_payment_term_code`, `finance.dispatch_payment_gate`, `ar.aging_buckets`, `payment.plan_*`, `payment.default_*` (8) · `denda` Denda telat bayar: `ar.denda_rate_pct_per_month`, `ar.grace_days`, `payment.penalty_*` (8) · `selisih-bayar` Selisih bayar: `payment.variance_*` selain `variance_ap_tolerance_rupiah` (8) |
| `retur-koreksi` · Retur & koreksi dokumen (14) | Bukti apa yang wajib untuk retur, dan koreksi angka mana yang harus disetujui? | `retur` Retur penjualan: `returns.*` (7) · `koreksi` Koreksi dokumen: `amendment.*` (7) |
| `pembelian` · Pembelian, makloon & tagihan pemasok (25) | Apa yang wajib saat memesan ke pemasok atau makloon, dan kapan tagihannya boleh dibayar? | `memesan` Memesan ke pemasok: `purchasing.restock_source_unknown`, `.require_supplier_master`, `.allow_*_discount`, `.price_deviation_approval_percent` (5) · `makloon` Makloon: `makloon.*` (7) · `tagihan` Tagihan pemasok & kontrabon: `contra_bon.*`, `purchasing.bill_*`, `payment.variance_ap_tolerance_rupiah` (13) |
| `penerimaan` · Penerimaan barang & lot (24) | Boleh terima lebih dari PO? Nomor lot wajib? Satuan pemasok dihitung bagaimana? | `menerima` Menghitung & menerima: `receiving.*` selain 17 kunci `baca-sj`, `purchasing.receive_tolerance_percent`, `purchasing.qc_on_receipt` (11) · `nomor-lot` Nomor lot: `lot.*` (8) · `konversi-satuan` Konversi satuan: `uom.*` (5) |
| `kualitas` · Mutu kain (QC) (11) | Berapa poin cacat jadi grade apa, dan kapan roll ditahan? | `inspeksi` Inspeksi & grade: `qc.four_point_enabled`, `qc.grade_thresholds.*`, `qc.grade_from_points` (4) · `tidak-sesuai` Bila tidak sesuai sample: `qc.*_mismatch_action`, `qc.accept_all_with_hold_action` (3) · `jumlah-cek` Berapa roll yang dicek: `qc.*sampling_*` (4) |
| `stok` · Stok, alokasi & potong (31) | Roll mana dipakai lebih dulu, bagaimana sisa potong diperlakukan, dan kapan barang disebut laris atau lambat? | `memilih-stok` Memilih stok untuk pesanan: `allocation.*`, `inventory.intercompany_transfer_required`, `inventory.min_cut_qty`, `stock.atp_horizon_days`, `catalog.sales_hidden_stages` (14) · `potong` Potong & sisa potong: `cutting.*` (5) · `laris-lambat` Laris/lambat & pesan ulang: `inventory.stock_analytics.*`, `inventory.reorder.*` (8) · `kerja-gudang` Kerja gudang: `inventory.default_uom`, `wms.location_scope_enforced`, `registration.finance_approval`, `putaway.auto_draft` (4) |
| `persetujuan` · Persetujuan, pengingat & dokumen (15) | Dokumen bernilai berapa naik ke siapa, siapa diingatkan, dan bagaimana dokumen saling merujuk? | `umum` Persetujuan umum: `approval.extra_levels`, `approval.reminder_min_days` (2) · `rnd` Persetujuan R&D: `approval.matrix_*`, `approval.po_custom_direksi_min` (5) · `pemberitahuan` Pemberitahuan: `notif.*` (2) · `rujukan-dokumen` Rujukan antar dokumen: `docref.*` (6) |
| `pajak-pembukuan` · Pajak, pembukuan & antar-PT (17) | Berapa PPN, kapan buku ditutup, dan bagaimana jual-beli antar-PT dihitung? | `pajak` Pajak: `tax.*` (5) · `tutup-buku` Mata uang & tutup buku: `finance.base_currency`, `finance.fiscal_year_end_month`, `inventory.drift_alert_rupiah`, `periode.*` (5) · `antar-pt` Jual-beli antar-PT: `antar_entitas.*` (7) |
| `bank-kasus` · Bank & uang yang nyangkut (26) | Kapan mutasi bank dicocokkan otomatis, dan berapa lama uang tak jelas boleh menganggur? | `bank` Mencocokkan mutasi bank: `bank.*` (14) · `kasus` Kasus keuangan: `case.*` (12) |
| `sdm` · Gaji & SDM (20) | Berapa iuran BPJS, PPh 21, dan upah lembur? | `bpjs` BPJS: `hr.bpjs.*`, `hr.jkk_classes`, `hr.feature_toggles.bpjs_*` (12) · `pph21` PPh 21: `hr.ter_enabled`, `hr.ptkp_table`, `hr.feature_toggles.pph21`, `hr.feature_toggles.npwp_required` (4) · `lembur` Lembur, komisi & kepegawaian: `hr.overtime.*`, `hr.employment_types`, `hr.payroll_commission_mode` (4) |
| `rnd` · R&D & desain (27) | Kapan barang hasil R&D boleh dijual, siapa memutus sample, dan bagaimana desainer dinilai? | `boleh-dijual` Kapan produk boleh dijual: `rnd.lifecycle_enforcement`, `rnd.new_product_default_lifecycle`, `rnd.variant_axes_*`, `rnd.spec_approval_roles` (5) · `sample` Sample & pemasok pemenang: `rnd.sample_decision_roles`, `rnd.max_rounds`, `rnd.round_sla_days`, `rnd.require_*`, `rnd.labdip_max_colors`, `rnd.sla_escalate_admin_days`, `rnd.auto_contract_on_decide`, `rnd.sample_material_from_stock` (10) · `kode-desain` Kode & nilai desain: `rnd.design_*` (6) · `nilai-desainer` Nilai desainer: `rnd.kpi_*` (6) |
| `sistem` · Sistem, AI & tampilan (lanjutan) (51) | Fitur AI mana yang menyala dan berapa anggarannya, serta apa yang tampil di menu? | `tanya-kn` Tanya KN: arti angka & hak lihat: `ai.sales_*`, `ai.margin_roles`, `ai.stock_value_roles`, `ai.enabled`, `ai.enabled_roles`, `ai.daily_question_limit`, `ai.monthly_budget_usd`, `ai.glossary`, `ai.anomaly_*` (12) · `tanya-kn-teknis` (lanjutan) sisa `ai.*` (11) · `baca-sj` (lanjutan) Baca surat jalan otomatis: `receiving.ocr_*`, `receiving.min_photo_short_side_px`, `receiving.client_po_patterns` (17) · `rfid-proses` (lanjutan) RFID & proses macet: `rfid.*`, `wms.rfid_simulation`, `saga.stuck_lock_minutes` (5) · `menu` Menu & halaman awal: `ui.*`, `role_home.*` (6) |

| Kelompok lama (jumlah) → baru (`GROUP_ALIASES` memakai tujuan pertama) | | |
|---|---|---|
| `uang-masuk` (25) → `pembayaran-pelanggan` 24, `pembelian` 1 | `harga-diskon` (17) → `penjualan` | `persetujuan` (10) → `persetujuan` 7, `penjualan` 2, `pembelian` 1 |
| `pajak` (5) → `pajak-pembukuan`·`pajak` | `keuangan-dasar` (6) → `pajak-pembukuan`·`tutup-buku` 5, `sistem` 1 | `pembelian` (8) → `pembelian` 6, `penerimaan` 2 |
| `penerimaan` (26) → `penerimaan` 9, `sistem` 17 | `stok-satuan` (40) → `stok` 31, `penerimaan` 5, `sistem` 4 | `kualitas` (11) → `kualitas` |
| `lot` (8) → `penerimaan`·`nomor-lot` | `makloon` (7) → `pembelian`·`makloon` | `sdm` (20) → `sdm` |
| `tampilan` (12) → `sistem`·`menu` 6, `penjualan` 6 | `amandemen` (7) → `retur-koreksi`·`koreksi` | `dokumen` (6) → `persetujuan`·`rujukan-dokumen` |
| `rnd` (27) → `rnd` | `bank` (14) → `bank-kasus`·`bank` | `kasus` (12) → `bank-kasus`·`kasus` |
| `kontrabon` (10) → `pembelian`·`tagihan` | `antar-entitas` (7) → `pajak-pembukuan`·`antar-pt` | `notifikasi` (2) → `persetujuan`·`pemberitahuan` |
| `asisten-analitik` (23) → `sistem`·`tanya-kn` | `retur` (7) → `retur-koreksi`·`retur` | |

| Berkas | Perubahan |
|---|---|
| `configGroupViews.js` | Tiap kelompok tetap di tepat satu layar: `settings-cfg-approval` [`persetujuan`] · `settings-cfg-sales` [`penjualan`, `retur-koreksi`] (kunci `commission.*` tetap disembunyikan) · `settings-cfg-warehouse` [`penerimaan`, `kualitas`, `stok`] · `settings-cfg-purchasing` [`pembelian`] · `settings-cfg-finance` [`pembayaran-pelanggan`, `pajak-pembukuan`, `bank-kasus`] · `settings-cfg-hr` [`sdm`] · `settings-cfg-rnd` [`rnd`] · `settings-cfg-system` [`sistem`] |
| `viewAliases.js`, `hubTabs.js`, `navMeta.js` | Dua layar kehilangan kelompoknya dan menjadi alias (tab dicabut, rute cadangan `activeView === "<id>"` dipertahankan, id tetap di `access_modules.py`): `settings-cfg-documents` → `settings-cfg-approval` dengan `preset: {section: "rujukan-dokumen"}`; `settings-cfg-notify` → `settings-cfg-approval` dengan `preset: {section: "pemberitahuan"}`. Label tab `settings-cfg-approval` menjadi "Ketegasan, Pengingat & Dokumen", `settings-cfg-system` menjadi "AI & Tampilan"; `PAGE_META` delapan layar ditulis "<label tab> · <label kelompoknya>" |
| `configDeepLink.js` | `LEGACY_DEEPLINK` dan `CONFIG_GROUP_IDS` dihapus; `groupForKey(key)` membaca `configKeyIndex.json` (`{key: [kelompok, sub-judul]}`, ditulis skrip baru `scripts/gen_config_key_index.py`; uji statik menegaskan berkas sama dengan keluaran skrip); `openConfig({group})` menerjemahkan id lama lewat salinan `GROUP_ALIASES` yang diuji sama dengan server. Pemanggil lama tidak diubah. `READ_LIMITS` tetap memakai id `rnd` |

### Izin dan peran

Tidak ada.

### Layar

Tempat: semua layar `settings-cfg-*`, "Semua pengaturan", Komisi & Insentif (satu mesin: `SettingsBrowser`). Tombol
"Default" dihapus (KF-12); tindakan penggantinya berdialog konfirmasi baku dengan isian **Alasan** (wajib bila berisiko tinggi).

| Keadaan | Tombol | Isi dialog | Panggilan |
|---|---|---|---|
| Cakupan PT, PT punya nilai sendiri | **Ikuti nilai grup** | "'{label}' untuk {PT} kembali mengikuti nilai grup ({nilai grup}). Nilai khusus {PT} ({nilai sekarang}) dicabut." | `POST /api/config/values/clear` |
| Cakupan PT, PT mengikuti grup | tidak ada tombol; keterangan "Mengikuti nilai grup" | — | — |
| Cakupan PT, nilai efektif ≠ bawaan (tautan teks di bawah editor) | **Pakai nilai bawaan sistem untuk PT ini** | "Nilai bawaan sistem ({nilai bawaan}) disimpan sebagai nilai khusus {PT}. Sesudah itu {PT} tidak lagi mengikuti perubahan nilai grup." | `POST /api/config/values/reset`, `scope_type: "entity"` |
| Cakupan grup, nilai ≠ bawaan | **Pakai nilai bawaan sistem** | "Nilai grup '{label}' kembali ke bawaan sistem ({nilai bawaan}). Berlaku untuk semua PT yang tidak punya nilai sendiri." | `POST /api/config/values/reset`, `scope_type: "global"` |

| Kunci | Editor baru (KF-13); `SettingEditor.jsx` memilih dari `type` + `items`/`value_format`/`ref`/`row_shape` |
|---|---|
| `approval.extra_levels` (`row_shape: "grouped_list"`) | Tabel baris berkolom **Jenis dokumen** (pilihan; hanya jenis yang punya pembaca: "Pesanan Pembelian (PO)") · **Mulai nilai (Rp)** · **Peran penyetuju** (pilihan peran) · **Nama tingkat**. Baris berjenis dokumen lain yang sudah tersimpan tampil hanya-baca bertanda "belum dipakai" |
| `makloon.claim_approval_roles`, `returns.cutloss_treatment_roles`, `ai.margin_roles`, `ai.stock_value_roles`, `ai.enabled_roles`, `rnd.spec_approval_roles`, `rnd.sample_decision_roles` (`items: "roles"`) | Kotak centang berlabel nama peran |
| `catalog.sales_hidden_stages`, `rnd.variant_axes_optional` (`items: "options"`) | Kotak centang dari `options`. Pilihan sumbu varian = delapan kode `variant_axes.AXIS_CATALOG` berlabel Indonesia |
| `allocation.priority_order`, `rnd.variant_axes_default` (`items: "options"`, `ordered`) | Daftar yang bisa digeser urutannya; `owner` terkunci di urutan pertama |
| `ar.aging_buckets` (`int_asc`) · `hr.employment_types` (`text`) | Deret isian angka dengan pratinjau "kolom 1–30, 31–60, 61–90, di atas 90 hari" · daftar butir teks; keduanya tambah/hapus butir |
| `receiving.client_po_patterns` (`regex`) · `receiving.ocr_price_table` (`json_map`) · `ai.glossary` (`multiline`) · `approval.matrix_effective_from` (`date`) | Kotak multi-baris (yang pertama satu pola per baris) · pemilih tanggal baku |
| `finance.default_payment_term_code` (`ref: "payment_term"`) · `inventory.default_uom`, `commission.incentive_unit` (`ref: "uom"`) · `notif.low_stock_division` (`ref: "department"`) | Daftar pilih dari `ref_options` |
| `tax.pph_items`, `hr.jkk_classes`, `hr.ptkp_table` · semua kunci `money` · `receiving.mode` (`edit_at`) | Tetap · isian berpemisah ribuan dengan batas "paling kecil Rp … · paling besar Rp …" · tanpa editor: nilai + tautan "Ubah di Penerimaan & OCR › Mode Penerimaan" (panel itu membaca `preset.tab`) |

| Bagian layar | Isi |
|---|---|
| Daftar kartu | Kartu di bawah sub-judul; bagian `advanced` dalam blok tertutup **Lanjutan (teknis)**; kartu ringkas satu baris (label · nilai · lencana asal · risiko) yang terbuka saat diklik; kunci berstatus tidak dipakai dikumpulkan di bawah |
| Saringan (`FilterChips`) | **Semua** · **Sudah diubah** · **Risiko tinggi** · **Persetujuan** · **Pengingat & batas waktu** · **Toleransi selisih**; di "Semua pengaturan" tiga saringan tema berlaku lintas kelompok |
| Isi kartu | **Contoh** tampil langsung; tombolnya menjadi **Detail teknis** (kunci teknis, berkas pemakai). Baris lapisan: "Bisa dibedakan untuk: Semua PT · Satu PT". Lencana asal "Bawaan sistem", "Aturan grup", "Khusus {nama PT}"; laci "Kenapa nilainya begini?" satu baris per lapisan itu, tanpa nama koleksi |
| Menyimpan | Simpan mati sampai alasan terisi bila wajib. Kunci berisiko tinggi: dialog "Ubah '{label}'? Dari {lama} menjadi {baru} untuk {Semua PT / nama PT}." + kalimat dampak. Draf, alasan, dan jadwal dikosongkan saat cakupan berganti; meninggalkan kelompok dengan draf: "Ada perubahan yang belum disimpan pada {n} pengaturan. Tinggalkan?" |
| Kartu hanya-grup dan kartu terkunci | "Satu nilai untuk seluruh grup — tidak dibedakan per PT."; pada cakupan PT tetap bisa diubah oleh yang berhak dengan catatan "Mengubah di sini berlaku untuk semua PT." Terkunci: "Hanya pemegang akses '{permission_label}' yang boleh mengubah pengaturan ini." |
| Bilah cakupan | "Berlaku untuk" → **Semua PT (aturan grup)** / **Satu PT** + "Pilih PT…". Pita: "Anda sedang mengubah aturan grup — berlaku untuk semua PT yang tidak punya nilai sendiri." / "Anda sedang mengubah nilai khusus {PT}. PT lain tidak terpengaruh." / "Pilih PT dulu supaya perubahan tersimpan pada PT yang benar." (satu peringatan saja). Pada cakupan grup layar meminta `scope=global`; kartu menampilkan nilai grup dan baris "PT dengan nilai sendiri: {PT} = {nilai}" yang bila diklik berpindah ke cakupan PT itu |
| Riwayat, Kesehatan, pengalih | Saringan PT, orang, rentang tanggal, kelompok; nilai diformat seperti di kartu; "Muat berikutnya" dengan jumlah total; laci per kartu punya **Pulihkan nilai ini** (mengisi draf kartu; penyimpanan tetap lewat Simpan); tiap layar kelompok mendapat tautan "Riwayat perubahan kelompok ini". Pembuka: "Semua perubahan pengaturan, terbaru dulu. Nilai lama tidak pernah dihapus." Kesehatan dan kartu pengalih: tab "Kesehatan Pengaturan"; kolom "Kelompok" berisi label; "Status wiring" → "Tersambung ke sistem?"; nama berkas pindah ke Detail teknis. Kartu pengalih: "{judul} diatur di Pengaturan" |

## Uji penerimaan

Persiapan bersama: seed lingkungan B (`ent_ksc` PKP, `ent_kanda` non-PKP), akun admin, potret registry dari langkah 1.
`bukti/t1_config.py` harus tetap lulus sesudah putaran "kembalikan ke bawaan" dan "cabut lapisan PT" mengirim alasan.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B (statik) | — | `python scripts/guardrails/verify_config_text.py` dan `--self-test` | 0 pelanggaran T1–T7; self-test mendeteksi satu kasus merah per aturan |
| U2 | B (statik) | Potret sebelum | Bandingkan `key`, `type`, `default`, `min`, `max`, `scopes`, nilai pilihan, `permission`, `status` semua kunci | Sama persis; jumlah kunci tidak berubah |
| U3 | B | — | `GET /api/config/registry` | `groups` berisi tepat 13 id tabel (c); tiap kunci ber-`section` terdaftar; `ar.grace_days` → `pembayaran-pelanggan`·`denda`; `receiving.ocr_enabled` → `sistem`·`baca-sj`; `payment.variance_ap_tolerance_rupiah` → `pembelian`·`tagihan`; `pos.fbt.enabled` → `penjualan`·`saran-pos` |
| U4 | B | — | `GET /api/config/effective?group=uang-masuk` lalu `?group=dokumen` | 200 dengan butir kelompok `pembayaran-pelanggan`; lalu butir kelompok `persetujuan` |
| U5 | B | `ent_kanda` punya nilai `tax.ppn_mode` | `POST /api/config/values/reset` `{key: "tax.ppn_rate", scope_type: "global"}` tanpa alasan lalu dengan alasan; `POST /api/config/values/clear` `tax.ppn_mode` lapisan `ent_kanda` tanpa alasan lalu dengan alasan | 400 dan nilai tetap; 200 dan nilai 12; 400; 200 |
| U6 | B | Grup `ar.grace_days` = 5; `ent_kanda` = 9 | `POST /api/config/values/clear` `{key, scope_type: "entity", scope_id: "ent_kanda"}`; lalu grup diubah ke 6 | Sesudah cabut: `ent_kanda` 5 dengan `source_layer` `global`; sesudah grup berubah: `ent_kanda` 6 — PT kembali mengikuti grup |
| U7 | B | Lanjutan U6 (grup = 6) | `POST /api/config/values/reset` `{key, scope_type: "entity", scope_id: "ent_kanda"}`; lalu grup diubah ke 7 | `ent_kanda` 0 (bawaan) dengan `source_layer` `entity`, tetap 0 sesudah grup berubah; `ent_ksc` 7 |
| U8 | B | Master Grade Mutu seed: A, A1, A2, B, B1, C, BS aktif tanpa batas poin sendiri | `POST /api/config/simulate` `{key: "qc.grade_thresholds.a_max", overrides: {"qc.grade_thresholds.a_max": 20, "qc.grade_thresholds.b_max": 40}, sample: {points: 25}}`; ulangi dengan 45 dan 18 | "A1"; "BS"; "A". Hitungan: rentang 20–40 dibagi tiga → batas A1 26,67 dan A2 33,33; 45 > 40 → grade aktif terakhir |
| U9 | B | — | `POST /api/config/simulate` pajak, `ctx.entity_id: "ent_ksc"`, `overrides` tarif 12, DPP nilai lain ya, mode `excluded`, `tax.efaktur_enabled: false`, subtotal 10.000.000; ulangi dengan `ent_kanda` | `ent_ksc`: PPN Rp 1.100.000, total Rp 11.100.000 (10.000.000 × 12% × 11/12); `ent_kanda`: tanpa PPN, total Rp 10.000.000; keduanya sama dengan `ppn_breakdown` untuk masukan itu |
| U10 | B | — | `GET /api/config/effective?group=sistem`; `PUT /api/config/values` `receiving.client_po_patterns` dengan dua pola bawaan, lalu dengan `["("]`; `PUT` `ai.margin_roles` = `["admin", "Manager"]` lalu `["admin", "manager"]`; `ar.aging_buckets` = `[30, 20]`, `["a"]`, `[14, 30, 60]`; `allocation.priority_order` = `["lot", "owner"]` | Butir memuat `value_format: "regex"`; 200, 400; 400 (menyebut butir "Manager"), 200; 400, 400, 200; 400 |
| U11 | B | — | `PUT` `approval.extra_levels` = `{"purchase_order": [{"min_amount": 500000000, "role": "admin", "label": "Direksi"}]}`; lalu `role: "owner"` | 200 dan nilai tersimpan berbentuk sama; lalu 400; butir memuat `row_shape: "grouped_list"` dengan empat kolom |
| U12 | B | — | `GET /api/config/registry?q=supplier` dan `?q=pemasok`; `?q=gulungan` dan `?q=roll` | Tiap pasangan mengembalikan himpunan kunci yang sama dan tidak kosong |
| U13 | B | `ent_kanda` punya `tax.ppn_mode` = `included`; grup `excluded` | `GET /api/config/effective?group=pajak-pembukuan&scope=global&entity_id=ent_kanda` | Butir `tax.ppn_mode`: `value` `excluded`; `entity_overrides` memuat `ent_kanda` = `included` |
| U14 | layar (uji komponen, lalu uji jalan sebagai admin) | — | `SettingCard` kunci berisiko tinggi, cakupan Satu PT: nilai warisan, lalu nilai khusus PT; ganti PT saat ada draf. Uji jalan: buka Pengaturan › Gudang & Mutu dan Integrasi & Sistem › AI & Tampilan | Tidak ada tombol "Default"; "Ikuti nilai grup" hanya saat PT punya nilai sendiri; Simpan mati sampai alasan terisi; draf kosong sesudah ganti PT. Uji jalan: sub-judul tampil; "Lanjutan (teknis)" tertutup; daftar peran berupa centang; tidak ada teks "entitas", "wiring", "setting" |

## Langkah kerja

1. Potret registry; `backend/tests_mem/test_KFT4_*.py` untuk U2–U13 dan penjaga `verify_config_text.py` (merah).
2. `GROUPS`, `sections`, `GROUP_ALIASES`, `section` di semua `E(...)`; `gen_config_key_index.py`; U3, U4 hijau.
3. Teks: Lampiran A, lalu aturan umum, satuan, arti 0, istilah; U1 hijau.
4. `configGroupViews.js`, `configDeepLink.js`, dua alias; perbarui uji lama `test_phase3_p2_settings_groups.py` dan `phase3Settings.test.js`.
5. `reset`/`clear` beralasan; simulator QC dan pajak; validasi isi daftar, `grouped_list`, `ref_options`; U5–U11.
6. Pencarian, riwayat, `scope=global`; U12, U13.
7. Kartu: pengembalian nilai, editor, sub-judul, saringan, lencana, bilah cakupan; lalu riwayat, Kesehatan, pengalih.
8. U14; gate; laporan (jumlah kunci per kelompok; daftar kunci yang teks arti-0-nya ditulis baru). Unit boleh dipecah
   (`00` §8) menjadi **KF-T4a** langkah 1–4, **KF-T4b** langkah 5–6, **KF-T4c** langkah 7–8.

## Dokumen ikut berubah

`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (tabel (b)); `CODEBASE_MAP.md` (penjaga, skrip indeks, `configKeyIndex.json`);
`docs/KN_13_NAVIGATION_MAP.md` (dua tab menjadi alias); `docs/blueprint/02_STANDAR.md` §2.1 (field `section`, `items`, `ref`).

## Di luar lingkup

| KF-UX | Dipegang |
|---|---|
| 04, 08, 09, 10, 11, 12, 15, 17, 19, 20, 21, 22, 23, 24, 25, 27 | Unit ini |
| 13 | Unit ini untuk saringan tema dan kalimat pembeda pada pasangan kunci; penggabungan dua sakelar setuju-sendiri → KF-T6 |
| 14 | Unit ini untuk `receiving.mode` dan nama "Pengaturan"; tiga tab persetujuan dan aturan bank → KP-T3, KP-T9 |
| 16, 18, 26 | Unit ini untuk teks, editor, dan `permission_label`; perilaku yang membuat teks keliru, `role_home.*`, dan pemeriksa kesehatan yang hanya mencocokkan kata → KF-T3; tiga kode akun bank → KF-T2 (KP-30) |
| 01, 02, 03, 05 | KF-T3 (nilai PT tidak dibaca mesin; penimpaan oleh master; kunci aktif tanpa efek; jadwal dan pembatalannya) |
| 06 | KF-T5 (layar lapisan pelanggan dan produk) |
| 07 | KF-T2 (aturan di luar registry, jalur tulis lama) dan KF-T7 (ambang blokir kredit) |
| 28 | KF-T1 (izin) dan KP-T9 (tab tampil menurut modul akses) |
| Lain | Pesan 403 pengaturan → KF-T1; menyamakan bawaan registry `approval.extra_levels` dengan bawaan mesin → KF-T2; simulator baru untuk kunci berisiko tinggi lain tidak dibuat; susunan hub Pengaturan → KP-T9 |

## Asumsi dan risiko

- `ASUMSI:` di mana Lampiran A bagian 3 berbeda dari `02` §4 L2, standar yang dipakai: "PT" dan "pemasok".
- `ASUMSI:` Lampiran B sumber hanya memberi jumlah kunci per sub-judul; tabel (c) adalah pembagian pola awalan yang menghasilkan jumlah itu. Empat penempatan tidak tersurat di sumber: `sales.sample_payment_tolerance_pct` → Harga & diskon; `inventory.min_cut_qty` dan `catalog.sales_hidden_stages` → Memilih stok; `inventory.default_uom` → Kerja gudang.
- `ASUMSI:` pola tema `pengingat` menghasilkan 18 kunci (sumber menyebut 17 tanpa daftar); satuan pada aturan (a)5 yang tidak tertulis di Lampiran A diturunkan dari label dan nama kunci; pilihan departemen untuk `notif.low_stock_division` adalah nama unit organisasi SDM.
- `RISIKO:` nilai daftar tersimpan yang tidak lolos validasi baru (mis. id peran salah ketik) tetap terbaca, tetapi kartunya menolak disimpan ulang sampai diperbaiki. Laporan memuat kueri pencarinya; unit tidak mengubah data.
- `RISIKO:` PT yang dulu menekan "Default" masih terkunci pada nilai bawaan. Kueri: `config_values` dengan `scope_type: "entity"` dan `reason: "Kembalikan ke default sistem"`; pemulihannya keputusan pemilik (H3).
- `RISIKO:` tautan lama ber-id kelompok lama ditangani `GROUP_ALIASES`. Membatalkan unit = mengembalikan `GROUPS` dan `group` di katalog; tidak ada data tersimpan yang memuat id kelompok.
