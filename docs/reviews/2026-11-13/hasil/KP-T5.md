# KP-T5 — Penomoran dokumen bisa diatur per PT, tanpa mengubah satu nomor pun saat dipasang

- Commit awal: `1392969` (dikerjakan) · digabung di atas `640abe4` (sesudah KF-T7, PK-37)        - Commit (a): `4e816a0`        - Commit (b): `eb4e0e1` · cek visual `d1c090f`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-12, KP-35 (spesifikasi `docs/blueprint/unit/KP-T5.md`; keputusan `00` §4.1 — nilai awal = perilaku hari ini; H3 untuk dokumen lama)
- Risiko tinggi → dua serah-terima (`00_ATURAN_EKSEKUSI.md` §8): (a) katalog + pembaca format, titik panggil belum
  disentuh; (b) endpoint, layar, KP-35, dan 11 titik panggil bersama mengirim PT dokumennya. Keadaan (a) disimpan utuh
  (berkas per jalur) untuk integrator; daftar berkas (a) dan (b) di bagian "Pembagian serah-terima".

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `1392969`)

| # | Hasil di `1392969` |
|---|---|
| 1 | Berlaku. `core_utils.py:19` (`next_doc_number`), `doc_type` kini `:61` |
| 2 | Berlaku, bergeser: `core_utils.py:112` (`_max_existing_number`) |
| 3 | Berlaku, bergeser: `indexes.py:580–582` (`uq_entity_doctype`) |
| 4 | Sebagian: **95** pemanggilan (di luar uji/seed/skrip/`core_utils`), **60** awalan berbeda — `CUST-` (`customers.code`, lebar 4, bersama) dipanggil lewat alias `_ndn(...)` di `routers/customers.py:99`, `routers/admin.py:309`, `services/crm_omnichannel_service.py:163` dan tidak ada di daftar spesifikasi. `sales_orders.py:305` → `:332`; `return_service.py:148` tetap |
| 5 | Berlaku. `routers/cash.py:29` |
| 6 | Berlaku, bergeser: `amendment_service.py:905`; `return_service.py:154` |
| 7 | Berlaku. `lot_service.py:133` (def), panggilan `:136` |
| 8 | Berlaku. `makloon_order_service.py:181–182` |
| 9 | Berlaku. `makloon_order_service.py:1407` |
| 10 | Berlaku. `hr_service.py:50` |
| 11 | Berlaku. `special_order_service.py:38` |
| 12 | Berlaku. `routers/invoices.py:46–47` |
| 13 | Sebagian: `hint` (kini `EntityWizard.jsx:376`) sudah diperbaiki KP-T1 ("…nomor dokumen yang bernomor per PT…"); pratinjau empat contoh tetap masih teks tetap (`:386`, ringkasan `:424`) — diperbaiki di unit ini |
| Tambahan | Kelaziman lama yang dipertahankan: titik panggil per PT yang menerima `entity_id = ""` (bukan `None`) masuk cara per PT dengan kode `ENT` (`ENT/SO-…`). Hanya `None`/`"all"` yang jatuh ke deret bersama. Dipertahankan apa adanya supaya tidak satu nomor pun berubah (U2 menguji `""`) |

## KP-12 / KP-35 — format nomor per jenis per PT; tiga deret "baca terakhir + 1"

- Berlaku di HEAD: ya (tabel di atas; merah di bawah).
- Akar masalah: awalan, lebar, dan cara (per PT/bersama) ditulis di tiap titik panggil, jadi bentuk nomor tidak bisa
  diatur dan tidak terlihat di satu tempat; tiga pembuat nomor (`VBM-`, `EMP-`, `SORD-`) membaca nomor terakhir lalu +1
  tanpa reservasi, sehingga dua pemanggil bersamaan mendapat nomor sama.
- Perubahan perilaku (sebelum → sesudah):
  - **Katalog** `backend/doc_number_kinds.py`: 65 jenis + nomor turunan `inv` (66 entri): `kind`, label, kelompok
    (Penjualan, Pembelian, Keuangan, Gudang, Antar-PT, R&D, SDM, Master), koleksi, field, **awalan identitas** (= kunci
    deret hari ini, tidak pernah berubah), bawaan `{prefix, width, date_token, reset, scope}` = bentuk hari ini, `clock`
    (`wib`; `lot` = `utc`), `locked` (`sup`, `mak`, `cust`, `cc`, `btg`, `pa`, `pj`, `inv`), `derived` (`inv`),
    `entity_field` (`rtn` = `owner_entity_id`), `lookup(collection, field, prefix, scheme, kind_hint)` (mengenali
    `LOT-2611-`, `SORD-261113-`, `INV-…-`; `CN-` di `credit_notes.number` dipilah oleh `scheme`).
  - **Tabel** `doc_number_formats` (hanya yang diubah; indeks unik wajib `uq_kind_entity` (kind, entity_id) di
    `indexes.REQUIRED_UNIQUE_INDEXES`, D7). Pembaca `services/doc_numbering_service.effective_format`: baris PT → baris
    grup `all` → katalog; `scope` hanya dari grup/katalog.
  - **`core_utils.next_doc_number`** tetap satu-satunya pembuat nomor; tanda tangan + `*, kind="", at=None`. Jenis
    dikenali → `plan()` (format, cara, kunci deret lama, pola semai) → semai sekali → `$inc` → rakit. Tidak dikenal /
    turunan → jalur lama apa adanya (`_legacy_next_doc_number`, + log). Cara: per PT bila `scope = per_pt` dan PT ≠
    `None`/`"all"`; titik panggil `scheme="shared"` tetap bersama selama grup belum memilih cara. Sisipan tanggal
    `YY/YYYY/YYMM/YYYYMM/YYMMDD` (WIB; lot UTC; sisipan yang sudah dirakit titik panggil lot dipakai selama sisipannya
    bawaan). Mulai lagi dari 1: kunci deret + bagian periode (tahun / tahun-bulan / tanggal), deret periode baru disemai
    dari nomor tertinggi ber-awalan-dan-periode sama. Semai per PT kini juga memperhitungkan jenis lain yang memakai
    kunci per PT yang sama bila jenis itu juga per PT (mis. nota debit penjualan + nota debit retur beli), dan awalan
    identitas bila awalan tercetak diubah; deret bersama yang **dipilih grup** disemai dari nomor tertinggi gabungan.
  - **Tanpa baris format** (keadaan saat dipasang): setiap nomor identik dengan sebelumnya — U2 membuktikan untuk
    **289 kombinasi** (98 titik panggil × PT `None`/`"all"`/`""`/`ent_ksc`/`ent_kanda`) × 3 keadaan data, termasuk isi
    `number_sequences` sesudahnya.
  - **API** `routers/doc_numbering.py` (baca `settings.view`, ubah `settings.manage`, pesan Z6; PT lewat
    `resolve_requested_entity`): `GET /api/doc-numbering?entity_id=` → `{entity_id, groups, rows:[{kind, label, group,
    format, default, source ("bawaan"|"grup"|"pt"), source_label, scope_source, next_preview, samples, last_no, locked,
    locked_note, version}]}`; `POST /preview` → `{samples (3), last_no, warnings, format}` tanpa menulis apa pun (`code`
    = kode PT yang belum dibuat, untuk wizard); `PUT /{kind}` (alasan, `expected_version`); `DELETE /{kind}?entity_id=&reason=`.
    Baris grup hanya bagi orang yang **ditugaskan di semua PT aktif** (penugasan, bukan nama peran). Validasi + pesan
    persis spesifikasi; tambahan "Sisipan tanggal atau pengulangan tidak dikenal." untuk nilai di luar daftar. Peringatan
    "Sudah ada {n} dokumen…" dan "Deret baru melanjutkan dari nomor tertinggi {tiap PT / gabungan} yang sudah ada.".
    Jejak `audit_logs` (`doc_number_format_saved` / `_cleared`, sebelum/sesudah, alasan).
  - **KP-35**: `_next_service_bill_no(entity_id)` → `kind="vbm"`; `next_employee_code(entity_id)` → `kind="emp"`;
    `generate_special_order_number(on_date, entity_id)` → `kind="sord"` (`at` = tanggal nomor, WIB). Bentuk sama, deret
    atomik, semai pertama dari nomor tertinggi yang ada. Pemanggil mengirim PT dokumennya.
  - **11 deret bersama** (`sret`, `cn_retur`, `rtn`, `pret`, `dn_retur_beli`, `vb`, `fpm`, `pr`, `rfq`, `lcv`, `wo`):
    pembantu menerima `entity_id` (+`kind=`), 15 pemanggil mengirim PT dokumennya (N1; faktur masukan antar-PT = PT
    pembeli; roll retur = PT pemilik roll). Selama `scope` bawaan hasilnya tidak berubah (U2 diulang penuh). Penyemai
    `bootstrap.py`/`seed_realistic.py` tidak disentuh (tanpa PT → bersama, sama).
  - `entity_provisioning_service.provision_entity`: `number_preview` = `preview("so", PT baru)` (cadangan teks lama bila
    galat).
  - `lot.number_format` (tetap tidak dipakai): alasan ditambah "Diatur di Pengaturan › Dokumen & Cetak › Penomoran Dokumen."
- Berkas berubah: lihat "Pembagian serah-terima".
- Commit: (a) `4e816a0`, (b) `eb4e0e1`, perbaikan tampilan sesudah cek visual `d1c090f`.
- Pengujian: tabel "Uji penerimaan" di bawah; bukti di `docs/reviews/2026-11-13/hasil/bukti/KP-T5/`.
- Bukti UI: dipotret di lingkungan A pada 1280 dan 1024 px (data acuan) — lihat "Cek layar". Uji komponen jest
  (`kpt5PenomoranDokumen.test.js`, 9 tes sesudah cek visual).
- Fixture disiapkan langsung vs proses bisnis: penghitung `number_sequences` dan dokumen lama disisipkan langsung
  (fixture); format disimpan lewat API (alur); PT baru U15 lewat `POST /api/entities` (alur).
- Dampak pada modul terkait: semua pembuat nomor dokumen (satu kueri tambahan ber-indeks ke `doc_number_formats` per
  nomor); wizard PT; tab baru di Pengaturan › Dokumen & Cetak; modul akses Pusat Pengaturan (+ `settings-documents`,
  `settings-doc-numbering`).
- Keterbatasan / yang belum diuji: U12 lulus di lingkungan A (3 uji). U16: layar dipotret dan dirapikan; menyimpan lewat
  pop-up di peramban belum diklik (alur simpan diuji API dan jest).
- Status: implemented_pending_review

## Pembagian serah-terima

**(a) — katalog dan pembaca; titik panggil tidak disentuh.** Keadaan utuh disimpan per jalur di luar repo (salinan
kerja integrator, `kpt5_a_state/`). Berkas (10): `backend/doc_number_kinds.py` (baru), `backend/services/doc_numbering_service.py`
(baru: `effective_format`, `plan`, `seed_number`, `render`), `backend/core_utils.py`, `backend/indexes.py`,
`backend/tests_mem/test_KPT5a_setara.py` (baru), `backend/tests_mem/test_PK14_indeks_wajib.py` (8 → 9 indeks wajib),
`scripts/verify_contract.py`, `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md`, bukti `a_merah_head.txt`, `a_hijau.txt`.
Hasil (a): `tests_mem` 652 lulus / 2 / 3 xfail (HEAD 638/2/3); penjaga statik sama dengan HEAD.

**(b) — pengaturan, layar, pengalihan deret lama.** Berkas tambahan/berubah: `backend/routers/doc_numbering.py` (baru),
`backend/server.py`, `backend/services/doc_numbering_service.py` (list/preview/save/clear), `backend/doc_number_kinds.py`
(`entity_field`), KP-35: `services/makloon_order_service.py`, `services/hr_service.py`, `routers/hr.py`,
`services/special_order_service.py`, `routers/special_orders.py`; 11 deret bersama: `services/return_service.py`,
`services/purchase_return_service.py`, `services/vendor_bill_service.py`, `services/input_tax_service.py`,
`services/purchase_requisition_service.py`, `services/rfq_service.py`, `services/landed_cost_service.py`,
`services/production_service.py`, `services/qc_service.py`, `services/interco_tax_service.py`,
`services/marketing_cost_service.py`, `services/return_roll_settlement_service.py`, `routers/landed_cost.py`,
`routers/rfq.py`, `routers/input_tax.py`, `routers/vendor_bills.py`; `services/entity_provisioning_service.py`,
`config_catalog_ops.py`, `access_modules.py`; uji `tests_mem/test_KPT5b_pengaturan.py` (baru),
`tests_mem/test_KPT5a_setara.py` (U1/U2 diulang atas titik panggil baru), `tests_mem/test_KFT2_kunci_pengaturan.py`
(teks alasan `lot.number_format`), `tests/test_bp_KPT5_bersamaan.py` (baru, lapis A); layar
`frontend/src/features/settings/docnumbering/DocNumberingView.jsx` (baru), `features/settings/entities/docNumberPreview.js`
(baru), `EntityWizard.jsx`, `entityApi.js`, `appViewImports.js`, `AppViewRouter.jsx`, `config/hubTabs.js`, `config/navMeta.js`,
uji jest `features/__tests__/kpt5PenomoranDokumen.test.js` (baru), `features/__tests__/kpt1ProfilPt.test.js`,
`config/__tests__/navAccess.test.js`, `config/__tests__/roleReach.test.js`, fixture `access_nav_fixture.json`,
`access_builtin_fixture.json` (dari `tests/fe03_access_fixture.py`); dokumen `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md`,
`docs/KN_13_NAVIGATION_MAP.md`, `memory/PRD.md`; bukti `b_merah_head.txt`, `uji_mutasi.txt`.

## Uji penerimaan

Merah lama: (a) di keadaan HEAD (berkas baru dipindah sementara); (b) di pohon `git archive HEAD` + berkas uji disalin.

| ID | Lapis | Uji | Merah di kode lama | Hijau di kode baru |
|---|---|---|---|---|
| U1 | B | `test_KPT5a_setara.py::test_KPT5_U1_…` — pengurai sintaks atas semua pemanggilan (98 sesudah b): dikenali `lookup`, lebar & cara bawaan = titik panggil, awalan berbeda **63** (59 spesifikasi + `CUST-` + 3 KP-35; di (a): 60) | merah (`doc_number_kinds` tidak ada) | hijau |
| U2 | B | `…::test_KPT5_U2_setara_semua_titik_panggil_tiga_keadaan` (289 kombinasi × penghitung 41 / dokumen lama tanpa deret / kosong; nomor + isi `number_sequences` vs salinan fungsi lama) dan `…::test_KPT5_U2_contoh_hitung_tangan_dan_cakupan_jenis` (`KSC/SO-00042`, `SRET-00042`, `KSC/LOT-<YYMM>-0042`, `CC00042`; 62 jenis lewat fungsi lama + 3 KP-35 = 65) | contoh/cakupan merah (katalog tidak ada); setara = lama vs lama | hijau; uji mutasi (bukti `uji_mutasi.txt`) menunjukkan uji menangkap lebar, cara, pola semai, sisipan lot |
| U3 | B | `…::test_KPT5_U3_semai_dari_nomor_tertinggi` — `KSC/SO-00007` → `KSC/SO-00008` | hijau (perilaku lama yang dipertahankan) | hijau |
| U4 | B | `test_KPT5b_pengaturan.py::test_KPT5_U4_…` — `KANDA/SP-000013`, `KSC/SO-00031`; GET sumber "Khusus PT ini"; DELETE → `KANDA/SO-00014` | merah (404) | hijau |
| U5 | B | `…::test_KPT5_U5_mulai_lagi_tiap_tahun` (jam dibekukan) — `KSC/SO-2026-00001` lalu `KSC/SO-2027-00001`; penghitung lama 30 tidak berubah | merah (404) | hijau |
| U6 | B | `…::test_KPT5_U6_…` — 400 "Agar nomor tidak kembar, pengulangan tahunan harus disertai sisipan tahun." (+ harian) | merah (404) | hijau |
| U7 | B | `…::test_KPT5_U7_…` — 400 "Format ini sama dengan Nota kredit, sehingga nomornya bisa kembar. Bedakan awalannya."; `CNR-` boleh | merah (404) | hijau |
| U8 | B | `…::test_KPT5_U8_…` — `KSC/SRET-00041`, `KANDA/SRET-00042`, nomor lama tetap; peringatan "tiap PT" di pratinjau dan simpan | merah (404) | hijau |
| U9 | B | `…::test_KPT5_U9_jenis_terkunci` — 400 "Format nomor Kode pemasok tidak bisa diubah dari layar."; 8 jenis terkunci | merah (404) | hijau |
| U10 | B | `…::test_KPT5_U10_…` — 400 "Pilihan per PT atau bersama diatur untuk seluruh grup." | merah (404) | hijau |
| U11 | B | `…::test_KPT5_U11_…` — `VBM-00010`, `EMP-00121`, `SORD-<hari ini WIB>-0004` | merah (tanda tangan lama tanpa PT — nilainya sama dengan lama) | hijau |
| KP-35 | B | `…::test_KPT5_KP35_dua_puluh_panggilan_bersamaan_tidak_kembar` — 20 panggilan sebelum dokumen tersimpan → 20 nomor berbeda | **merah: 20 × `EMP-00121`** (kembar) | hijau |
| KP-35 | B | `…::test_KPT5_KP35_setara_generator_lama` — data rapi kosong / 1 / 7 dokumen: nomor pertama = generator lama | hijau (oracle) | hijau |
| U12 | A | `backend/tests/test_bp_KPT5_bersamaan.py` — 20 `POST /api/hr/employees` bersamaan → `EMP-` berurutan tanpa kembar; 20 `_next_service_bill_no` bersamaan di MongoDB asli; indeks unik terpasang | — | **lulus** di lingkungan A (MongoDB 7 asli, 3 uji, 14 Nov) |
| U13 | B | `…::test_KPT5_U13_…` — dua pratinjau sama (`KSC/SO-000042…44`), `last_no` tetap 41, tidak ada penghitung baru | merah (404) | hijau |
| U14 | B | `…::test_KPT5_U14_izin` — Sopir 403/403; Tanpa Acuan `settings.view` 200 (66 baris)/403; peran satu PT: grup 403, PT sendiri 200, PT lain 403 | merah (404) | hijau |
| U15 | B | `…::test_KPT5_U15_…` — `provisioning.number_preview = "UJI/SO-00001"`; pratinjau wizard ikut format grup (`BARU/SO-000001`) | merah (404 pada langkah format grup) | hijau |
| U16 | layar | Uji jalan | — | **dipotret** 1280/1024 px, tiga cacat tampilan diperbaiki (`d1c090f`, lihat "Cek layar"); uji komponen jest 9 tes hijau (tabel, pop-up, pratinjau, Deret hanya grup, Kembalikan, tanpa izin, memuat/galat, wizard) |
| tambahan | B | validasi alasan/awalan/lebar/versi 409/404; jejak audit; daftar 66 baris + "Contoh nomor berikutnya" = nomor yang benar-benar terbit; indeks unik terdaftar; tanpa baris format saat dipasang; bagian periode | merah (404 / modul tidak ada) | hijau |

`tests_mem` (venv 3.11, `-n 0`): HEAD **638 lulus / 2 dilewati / 3 xfail** → (a) **652 / 2 / 3** → (b) **668 / 2 / 3**
(akhir, sesudah semua perubahan; `b_hijau.txt`).

Jest (folder salinan; `@radix-ui`/`cmdk` tak termuat = kendala lingkungan, sama di HEAD): HEAD 78 suite lulus / 35 gagal
dimuat, 563 tes lulus → baru **79 / 35, 571 tes lulus** (+8 `kpt5PenomoranDokumen`; suite yang gagal dimuat sama persis
dengan HEAD); suite terkait (kpt5, kpt1, kpt2, prt6, navAccess, roleReach, serverAccessReach, kft6) lulus. `fe03_access_fixture.py` + `tests/test_fe03_access_catalog.py
--noconftest`: 6 lulus.

## Penjaga statik (sebelum → sesudah)

`hitung_penjaga.sh`: semua hitungan sama dengan HEAD (verify_auth_coverage 28, verify_ui_standard 15, audit_i18n_id 109,
audit_create_modal 6, verify_page_tabs 1, verify_to_list_bound 6, verify_entity_label 2, sisanya 0/PASS; bagian data
verify_approval_queues diabaikan). `verify_role_gate_ui` 0 pelanggaran (31 cek). `verify_config_text` 0 pelanggaran
(2834 cek; tidak ada kunci baru). `audit_config_wiring --strict` (salinan berjalur) hijau. `verify_contract --all`
CONTRACT OK. `verify_codebase_map` PASS (peta dihasilkan ulang). `validate_compliance` 17 PASS / 1 FAIL / 129 WARN = HEAD
(FAIL = `frontend/.env` tidak ada di lingkungan B); `EntityWizard.jsx` tetap 500 baris (pratinjau dipindah ke
`docNumberPreview.js`).

## Penggabungan

Dikerjakan di `1392969`; digabung di atas `640abe4` (sesudah KF-T7 dan PK-37) sebagai (a) `4e816a0` lalu (b)
`eb4e0e1`. tests_mem sesudah gabung: 729 lulus. Sesudahnya PK-40 (`a78f552`) menambah 5 indeks wajib: uji PK-14 lapis B
menjadi 9 + 5, dan uji PK-14 lapis A yang belum menghitung indeks KP-T5 (masih 8) dibetulkan menjadi 14. PK-40 juga
mempertahankan nomor faktur masukan per PT dari KP-T5 (`next_input_number(entity_id)`).

## Cek layar

Dipotret di lingkungan A (`admin@`, data acuan) pada 1280 × 860 dan 1024 × 768 px; di HP 390 px peran admin masuk
aplikasi HP yang tidak memuat layar pengaturan (sesuai rancangan). Acuan: `docs/KN_37_STANDAR_UI_GUDANG.md`.

| Temuan (sebelum `d1c090f`) | Perbaikan |
|---|---|
| Tabel 9 kolom lebih lebar dari kartu: tombol **Ubah** terpotong di tepi kanan (pada Keuangan tinggal ikon pensil) | Judul kolom boleh dua baris (`data-table head-wrap`); kolom aksi lekat di kanan (`col-sticky-end`). 1280 px: tabel muat utuh; 1024 px: tabel bergulir di wadahnya, Ubah tetap tampak (KN_37 §3) |
| Judul kelompok ("Penjualan", "Keuangan") menempel di tepi kartu — `section-card` tanpa bantalan | `section-card section-pad`; judul 14 px + jumlah jenis |
| 66 jenis dalam 8 kelompok = halaman ±5.300 px tanpa cara mencari | Kotak cari (nama jenis atau awalan, tanpa peka huruf); kelompok tanpa hasil hilang; keterangan bila tidak ada yang cocok (uji jest baru) |
| "Bersama semua PT" pecah tiga baris | Kolom Deret dan Sumber tidak memecah baris |

Bukti: `bukti/KP-T5/layar_penomoran_1280_sebelum_ubah_terpotong.png`, `layar_penomoran_1280_sesudah_cari.png`,
`layar_penomoran_1024_sesudah.png`.

Dicoba lalu dibatalkan: lebar kolom tetap (`table-fixed`) agar kolom sejajar antar-kelompok — teks bertabrakan di 1024 px.
Penjaga sesudah perbaikan: `hitung_penjaga` sama, `verify_ui_contrast` 0, `verify_role_gate_ui` 0.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), tiap jalan sesudah `restore_demo` (data acuan; tiga skrip seed yang sama
seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`eef7bb9` — KP-T5, MN-T1, PK-38) | `--quick` | 14 FAIL | 16 | 1 (ganti nama, lihat bawah) | 2 (`config_wiring` + uji-diri, sejak KF-T2) |
| 1 (`eef7bb9`) | `--ci` | 43 FAIL | 43 | **3** | 2 |
| 2 (`3092d92` — + POC `bcce72a`, PK-40 `a78f552`, cek visual `d1c090f`·`f2bf995`·`c38fc92`) | `--quick` | 14 FAIL | 16 | 1 (ganti nama) | 2 |
| 2 (`3092d92`) | `--ci` | 41 FAIL | 43 | 1 (ganti nama) | 2 |

- **`guard:page_tabs`** tercatat "lebih merah" + "tidak dijalankan" karena MN-T1 mengganti namanya (INV-UI-12 →
  INV-UI-12/13/14). Merahnya sama dengan garis dasar: INV-UI-12 pada `features/wms/InventoryStockView.jsx` (berkas lama,
  tidak disentuh unit mana pun hari ini); INV-UI-13 dan INV-UI-14 hijau. Bukan merah baru.
- Jalan 1 `--ci`: **POC F-2** dan **POC E-8 G1** merah karena izin bawaan Finance hutang (K-17, MN-T1/PK-38) — POC masih
  menuntut sisi hutang tertutup. Disesuaikan di `bcce72a` (rincian di laporan MN-T1); jalan 2 keduanya hijau.
- Penjaga statik per hitungan (`hitung_penjaga.sh`, karena gate hanya membandingkan PASS/FAIL) sama dengan sebelum unit.


## Menyimpang dari blueprint

1. **Jumlah awalan dan jenis** (uji penerimaan keliru menghitung). HEAD punya 60 awalan lewat `next_doc_number`, bukan 59:
   `CUST-` dipanggil lewat alias `_ndn`. `CN-` dan `DN-` masing-masing dua jenis (`cn`/`cn_retur`, `dn`/`dn_retur_beli`),
   `MKO-` satu jenis (`mko`, per PT; tanpa PT bersama). Maka: 62 jenis lewat fungsi lama + 3 KP-35 = **65 jenis + `inv`**.
   Usulan koreksi teks (berkas unit tidak diubah di sini):
   - U1 hasil → "Tiap pemanggilan dikenali `lookup`; jumlah awalan berbeda yang dikenali = 60 sebelum langkah 5 (59 daftar
     + `CUST-` lewat alias `_ndn`) dan 63 sesudahnya (+ `VBM-`, `EMP-`, `SORD-`)".
   - U2 hasil → "Hasil = rakitan cara lama dengan angka 42, mis. `KSC/SO-00042`, `SRET-00042`, `KSC/LOT-<YYMM>-0042`,
     `CC00042`; 62 dari 62 jenis yang dibuat `next_doc_number` sama; tiga jenis KP-35 setara generator lamanya".
   - "Data" → "`backend/doc_number_kinds.py` — 65 jenis + `inv` (…`cust` → `customers.code`, lebar 4, bersama, `locked`)".
2. **`cust` dikunci** (tidak disebut spesifikasi) dengan alasan yang sama dengan `sup`/`mak` (kode master dipakai bersama) —
   aturan bawaan §4.1 (paling mudah dibalik).
3. **Bagian periode `bulanan` dengan sisipan `YYMMDD`** = tahun-bulan (spesifikasi: "seluruh sisipan", yang membuat deret
   bulanan diam-diam mulai lagi tiap hari). `tahunan` = tahun, `harian` = tanggal; untuk lot (`YYMM` + bulanan) hasilnya
   sama dengan spesifikasi.
4. **Tanda tangan** `next_doc_number(…, *, kind="", at=None)`: `at` ditambahkan karena pesanan khusus menomori dengan
   tanggal dokumen (penyemai data demo). `lookup` menerima `scheme` dan `kind_hint` (memilah `CN-` dua jenis).
5. **Hub Dokumen & Cetak menjadi dua tab**, bukan tiga (KF-T4 sudah mencabut "Aturan Dokumen"). Tab masuk `nav` modul
   **Pusat Pengaturan** (`settings`), bukan "Pengaturan, Pengguna & Hak Akses" (dipecah PR-T5); grup `settings-documents`
   ikut diberikan ke modul itu (tab Template Dokumen tetap modul Dokumen). `navAccess.test.js` disesuaikan.
6. **Wewenang baris grup** = ditugaskan di semua PT aktif (bukan `ctx.is_cross_entity` yang memakai nama peran, seperti
   KP-T4) — Z2.
7. **Semai tambahan** (tidak mengubah keadaan bawaan; U2 hijau): (i) awalan identitas ikut disemai bila awalan tercetak
   diubah; (ii) jenis lain yang memakai kunci per PT yang sama ikut disemai bila juga per PT; (iii) deret bersama yang
   dipilih grup disemai dari nomor tertinggi gabungan (sesuai kalimat peringatan "gabungan").
8. **Lot**: titik panggil `lot_service.next_lot_number` tidak diubah; sisipan `LOT-<YYMM>-` yang dirakitnya dikenali
   `lookup` dan dipakai selama sisipannya bawaan; bila grup mengganti sisipan, jam UTC dipakai.
9. **API**: `GET` menjawab `{entity_id, groups, rows}` (daftar di `rows`) + field tambahan (`default`, `source_label`,
   `scope_source`, `samples`, `locked_note`); `POST /preview` menerima `code` (PT belum dibuat) dan isian format opsional;
   `DELETE` mewajibkan alasan, juga untuk baris grup (kembali ke bawaan); pesan tambahan untuk sisipan/pengulangan di luar
   daftar.
10. **Semai KP-35**: generator lama `EMP-`/`VBM-` memakai hitungan dokumen bila nomor teratas bukan berawalan `EMP-`/`VBM-`;
    kini selalu nomor tertinggi berawalan itu (sama untuk data rapi — uji setara; berbeda hanya bila ada kode bukan
    `EMP-` di urutan teratas, dan hitungan lama justru rawan kembar).
11. **Uji lama disesuaikan**: `test_PK14_indeks_wajib.py` 8 → 9 indeks wajib (`doc_number_formats.uq_kind_entity`, D7);
    `test_KFT2_kunci_pengaturan.py` teks alasan `lot.number_format`; `kpt1ProfilPt.test.js` menghitung hanya `POST
    /api/entities` (wizard kini juga meminta pratinjau nomor).

## Asumsi / keraguan / titik henti

- `ASUMSI` (spesifikasi): deret bersama yang ada tetap bawaan; empat nomor RFID dan kode master dikunci; jam sisipan WIB
  (lot UTC); pilihan "per PT atau bersama" untuk seluruh grup.
- `ASUMSI` (unit ini): `cust` dikunci (butir 2); `entity_id = ""` tetap per PT berkode `ENT` seperti hari ini.
- **H3**: menomori ulang dokumen lama / memisah deret bersama yang sudah terbit tidak disediakan. Tidak ada migrasi data.
- **H7**: jenis RFID (`cc`, `btg`, `pa`, `pj`) hanya dicatat di katalog dan dikunci; titik panggil RFID/gerbang tidak disentuh.
- U12 (lapis A) lulus di MongoDB asli; lingkungan B tidak membuktikan keunikan saat bersamaan (uji KP-35 di B hanya
  membuktikan reservasi atomik dalam satu proses). U16: simpan lewat pop-up di peramban belum diklik.
- Biaya: satu kueri ber-indeks ke `doc_number_formats` per nomor; `GET /api/doc-numbering` menghitung contoh untuk 66 jenis
  (deret yang belum ada dihitung dari dokumen yang ada, baca saja).

## Hambatan lingkungan

- Jest: 35 suite gagal dimuat karena `@radix-ui`/`cmdk` tidak termuat lokal (sama di HEAD).
- `validate_compliance`: `frontend/.env` tidak ada (sama di HEAD).

## Yang perlu direview

- U2 setara (oracle = salinan fungsi lama) dan uji mutasi; pilihan "bulanan + YYMMDD = tahun-bulan".
- Wewenang baris grup (penugasan semua PT aktif) vs KP-T4 (`is_cross_entity`).
- Tampilan sesudah cek visual (kotak cari, judul kolom dua baris, kolom aksi lekat) — tambahan di luar spesifikasi layar.
