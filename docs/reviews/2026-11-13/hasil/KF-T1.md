# KF-T1 — Izin kelola dan lihat pengaturan benar-benar berfungsi

- Commit awal: `82e20b7` (sesudah PR-T9)        - Commit akhir: lihat `git log --grep "\[KF-T1\]"`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KF-01, KF-02, KF-03

## Cek ulang "Keadaan sekarang"

| Fakta | Hasil di HEAD awal |
|---|---|
| Pemegang `settings.manage` (peran kustom) tidak bisa menyimpan | Berlaku — `_may_edit` cabang `owner_role` menolak semua selain Admin |
| Peran kustom beracuan Manajer tanpa izin menyimpan kunci ber-`roles=("manager",)` | Berlaku — 48 kunci (`lot` 8, `receiving` 1, `makloon` 7 ber-`settings.manage`; `rnd` 27 + `approval` 5 ber-`rnd.manage`) |
| Sopir membaca `/api/config/effective` | Berlaku — hanya `current_user`; satu-satunya batas baca `READ_LIMITS["md"]` |
| `GET /api/settings`, `/api/settings/effective` | Berlaku — hanya login, dokumen utuh |
| Catatan baru | Kelompok `tampilan` memuat juga `pos.*` (6) dan `role_home.*` (4), bukan hanya `ui.*` (lihat Menyimpang) |

Bukti merah: `backend/tests_mem/test_KFT1_izin_pengaturan.py` di kode lama — **12 dari 14 gagal**; U6 dan U10 lulus
(memang perilaku yang dipertahankan). **U3 merah di kode lama** (spesifikasi memperkirakan hijau): di kode lama pemegang
`settings.manage` sudah ditolak oleh `owner_role` sebelum aturan lapisan sempat diperiksa
("…tidak bisa Anda ubah (butuh izin settings.manage)").

## Perubahan

| Berkas | Isi |
|---|---|
| `backend/config_registry.py` | `E(...)`: parameter `roles` dan `owner_role` dihapus (memanggil dengan `roles=` → `TypeError`); `sensitif_baca` (eksplisit → kelompok → bawaan `True`); kelompok `tampilan` `sensitif_baca: False`; komentar kepala |
| `backend/config_catalog_ops.py` | 16 kunci: `lot.*` → `inventory.configure`, `receiving.supplier_dn_mode` → `goods_receipt.configure`, `makloon.*` → `makloon.configure`; `_MANAGER_TOO` dihapus |
| `backend/config_catalog_rnd.py`, `config_catalog_approval_matrix.py` | `roles=` dicabut dari 27 + 5 kunci (izin `rnd.manage` tetap) |
| `backend/config_catalog_core.py` | 12 kunci `sensitif_baca=False`; `role_home.*` `sensitif_baca=True` |
| `backend/services/config_resolver.py` | `owner_role` dicabut dari field `resolve_group` |
| `backend/permissions_config.py` | `inventory.configure`, `goods_receipt.configure`, `makloon.configure` untuk `admin` dan `manager` |
| `backend/bootstrap.py` | `migrate_kft1_settings_permissions` (sesudah sinkron izin; penanda `kft1_izin_pengaturan`): peran kustom beracuan Manajer + 4 aksi (tanpa `view`); aksi itu dibuang dari `pending_defaults` PR-T9 |
| `backend/routers/config.py` | `_may_edit` (Admin atau izin kunci), `_may_read`, `_readable_groups`, pesan U/B1/B2 dengan nama modul; `READ_LIMITS`/`_read_limit`/`_visible` dihapus; semua endpoint baca dijaga; `caps.settings_view`; `read_scope` = label kelompok terbaca |
| `backend/routers/settings.py` | `GET /api/settings` → `settings.view` (B1); `GET /api/settings/effective` tanpa `settings.view` → `saring_bagi_pembaca` |
| `backend/services/config_service.py` | `saring_bagi_pembaca`, `BUKA_SEMENTARA = ("scope", "tax.is_pkp", "returns", "interco_payment")` |
| `backend/access_modules.py` | `VIEW_RESOURCE_OVERRIDES` 11 layar pengaturan; modul Stok & Persediaan memuat `settings-hub`, `settings-warehouse`, `settings-cfg-warehouse` (lihat Menyimpang) |
| `frontend/.../SettingsHub.jsx` | 403 dari registry/effective → keadaan kosong berpesan (`cfg-denied`), tanpa "Coba lagi" |
| `frontend/.../SettingsScopeBar.jsx` | "Anda hanya melihat pengaturan **{read_scope}** — yaitu aturan yang termasuk wewenang peran Anda. Yang bisa Anda ubah di daftar ini: n dari m pengaturan."; kalimat "melihat semua aturan" hanya untuk `settings.view` tanpa `settings.manage` |
| `frontend/src/config/__tests__/fixtures/access_builtin_fixture.json` | Ditulis ulang oleh `backend/tests/fe03_access_fixture.py` (aksi `configure` + `view_resources` baru) |
| `backend/tests/test_uat26_d3_decisions.py` | `test_k11_md_reads_only_rnd_settings_groups` memakai fungsi baru (`_may_read`, `_readable_groups`); MD tetap 32 kunci |
| `backend/tests_mem/test_PRT9_izin_bawaan.py` | U1 mengecualikan tiga aksi `configure` yang sengaja ditambah unit ini (berkas "sebelum" tetap foto kode sebelum PR-T9) |
| `ENTITY_REGISTRY.md`, `memory/PRD.md` | Penanda `kft1_izin_pengaturan`; aturan baca dan ubah pengaturan |

## Uji penerimaan

| ID | Lapis | Hasil |
|---|---|---|
| U1 | B | Lulus — `settings.manage` menyimpan di lapisan PT; `value_of(…, ent_ksc)` = `False` |
| U2 | B | Lulus — `can_edit` benar pada 232 kunci |
| U3 | B | Lulus — lapisan grup tetap 403 "…hanya dapat diubah peran lintas badan usaha…" |
| U4 | B | Lulus — `settings.view` saja: simpan 403 menyebut 'Pengaturan, Pengguna & Hak Akses' tanpa `settings.manage`; registry 200, 310 kunci |
| U5 | B | Lulus — Manajer Kosong: simpan 403, registry 403; nilai tetap |
| U6 | B | Lulus — Manajer bawaan menyimpan `lot.require_dye_lot` dan `rnd.max_rounds` di lapisan grup (200) |
| U7 | B | Lulus — `inventory.view/configure`: lot 200; makloon 403; registry 8 kunci `lot.*`; `group=pajak` 403 B2 "…pengaturan “Pajak”…" |
| U8 | B | Lulus — migrasi: 4 aksi tanpa `view`; jalan kedua dokumen identik; sesudah Admin mencabut `inventory.configure` tidak kembali |
| U9 | B | Lulus — Sopir: registry, effective, explain, history, simulators, health → 403; lima pertama berpesan B1/B2 |
| U10 | B | Lulus — MD: registry 32; simpan `rnd.max_rounds` lapisan PT 200; explain kunci bank 403 |
| U11 | B | Lulus — Sopir menerima `ui.show_coming_soon`, `tax.ppn_rate`, `tax.is_pkp`, `finance.default_payment_term_code`; tanpa `bank`, `commission`, `approval`, `ar`, `role_home`. Admin: `bank.auto_match_min_score` 85, `commission` ada |
| U12 | B | Lulus — Sopir `GET /api/settings` 403 B1; Manajer 200 |
| U13 | B | Lulus — tidak ada `roles`/`owner_role`; 14 kunci `sensitif_baca` salah; `E(..., roles=…)` → `TypeError` |
| U14 | B | Lulus — 11 layar: `VIEW_RESOURCE_OVERRIDES` = `{settings}` ∪ `permission[0]` kunci kelompoknya (dibaca dari `configGroupViews.js`) |
| U15 | layar | **Belum diuji jalan sampai checkout**: data acuan lingkungan A tidak punya lokasi gudang (`warehouse_sites` = 0), sehingga tombol "Buka katalog" POS terkunci untuk semua akun. Pengganti yang dijalankan di peramban (akun `sales@` dan `admin@`): `GET /api/settings/effective` → Sales menerima `tax` (ppn_rate 12, ppn_mode, dpp_nilai_lain, is_pkp), `finance.default_payment_term_code` NET30, `inventory.min_cut_qty` 0,5, `sales.allow_item/order_discount`, `allocation.roll_pick_sales`, `ui.*`, `purchasing.*` — **semuanya sama persis dengan nilai yang diterima Admin**; bagian `approval`, `ar`, `commission`, `qc`, `role_home` tidak dikirim ke Sales |
| U16 | layar (uji jalan) | **Lulus** — akun berperan `inventory: view, configure`: Pengaturan › Gudang & Mutu › Aturan Gudang & Mutu menampilkan tepat 8 kartu `lot.*`, tombol simpan aktif; pemberitahuan "Anda hanya melihat pengaturan Lot & Ketertelusuran — … Yang bisa Anda ubah di daftar ini: 8 dari 8 pengaturan."; "Semua pengaturan" tidak tampil. Tangkapan: `bukti/KF-T1/U16_aturan_gudang.png` |

`backend/tests_mem` seluruhnya: 111 lulus, 9 diharapkan gagal (milik unit lain).

Skrip audit di kode baru (`docs/audit/konfigurasi-peran-2026-11-13/bukti/`):

- `t3_escalation.py`: kunci `settings.manage` tanpa `roles` = 232, kunci ber-`roles` = 0; **(a)** lapisan grup 403 (aturan lapisan),
  **lapisan PT 200**, **`can_edit=true` 232 dari 232**; (b) Manajer bawaan (hanya `settings.view`) 403 dengan pesan baru.
  Skrip berhenti di (c) karena membaca field `roles` yang sengaja dihapus (arsip audit tidak diubah); (c) dan (f1)
  diwakili U5 dan U9.
- `t1_config.py`: 287 dari 287 tulis grup dan 242 dari 242 tulis PT tetap terbaca benar.
- `backend/tests/test_uat26_d3_decisions.py::test_k11_md_reads_only_rnd_settings_groups` dan
  `test_uat26_d3_http.py::test_k11_md_reads_only_rnd_config` (lingkungan A): lulus.
- `backend/tests/test_fe03_access_catalog.py`: 6 lulus (fixture = katalog).
- Jest `serverAccessReach.test.js`, `roleReach.test.js`: lulus dengan fixture baru. `decisionsD3.test.js` dan
  `phase3Settings.test.js` **tidak bisa dimuat di lingkungan ini** ("Cannot find module
  '@radix-ui/primitive/is-development'" dari `cmdk` di salinan `node_modules` lokal) — bukan perubahan unit ini.

## Gate

- `gate.sh --quick`: 16 merah = garis dasar 16 (lebih merah 0).
- `gate.sh --ci`: 43 merah = garis dasar 43 (lebih merah 0, menjadi hijau 0).

## Menyimpang dari blueprint

- **Kelompok `tampilan`** juga memuat `pos.*` (6) dan `role_home.*` (4). Sesuai aturan kelompok, `pos.*` ikut tidak
  sensitif; `role_home.*` diberi `sensitif_baca=True` eksplisit supaya U11 ("tanpa `role_home`") terpenuhi. Jumlah
  kunci tidak sensitif = 20 (14 di daftar spesifikasi + 6 `pos.*`).
- **Modul Stok & Persediaan** kini membuka menu `settings-hub` › `settings-warehouse` › `settings-cfg-warehouse`.
  Tanpa itu peran kustom yang hanya memegang izin Stok (U7/U16) tidak punya jalan menu ke kartu lot yang kini menjadi
  wewenangnya. Akibat sampingan: peran kustom ber-`inventory.view` tanpa izin pengaturan melihat tab itu dengan pesan B1
  (sejalan dengan catatan K-49 di spesifikasi).
- **Kelompok terbaca diurutkan** menurut jumlah kunci terbaca (terbanyak dulu) bagi pembaca terbatas, pengganti
  "kelompok utama peran di depan" dari `READ_LIMITS` (MD tetap membuka R&D lebih dulu).
- **Migrasi** juga membuang keempat aksi dari `custom_roles.pending_defaults` (PR-T9) supaya tombol "Ikuti peran dasar"
  tidak menawarkan aksi yang sudah dimiliki.

## Asumsi (dari spesifikasi)

Tanpa `settings.view`, seseorang hanya membaca kunci yang boleh ia ubah. Peran kustom beracuan Manajer yang sudah ada
diberi empat aksi tanpa `view`. Peran kustom yang hari ini membuka tab pengaturan domain dalam keadaan terkunci kini
melihat pesan B1.

**Peran kustom di data acuan yang terkena** (dijalankan pada data acuan lingkungan A): tidak ada — data acuan tidak memuat peran kustom sama sekali (`custom_roles` = 0 dokumen), jadi migrasi `kft1_izin_pengaturan` tidak mengubah apa pun di sana. Kueri untuk data nyata: `db.custom_roles.find({base_role: "manager"})` (akan menerima 4 aksi) dan peran kustom tanpa `settings.view` yang membuka tab `settings-cfg-*` lewat modul domainnya (akan melihat pesan B1).

## Yang perlu direview

- `RISIKO:` peran kustom beracuan Manajer yang modulnya "Tidak ada" lalu menerima aksi `configure` dari migrasi:
  `level_of` menganggap modul ber-aksi apa pun sebagai terbuka, sehingga menu modul itu bisa ikut tampil walau aksi
  `view` tidak diberikan. Spesifikasi berasumsi menu tidak ikut terbuka.
- `BUKA_SEMENTARA` untuk `returns` dan `interco_payment` dicabut KF-T2.

Status: implemented_pending_review.
