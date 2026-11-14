# PR-T6 — Layar Peran & Hak Akses dan Akun & Akses menjawab "peran ini akhirnya bisa apa"

- Commit awal: `0a91095` (dikerjakan) · digabung di atas `aea3cec` (sesudah KF-T4, PR-T8, PK-36, KP-T2)        - Commit akhir: `1392969`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PR-09 (beserta butir layar PR-UX-01, 02, 05, 09, 10, 17, 20, 21, 27, 29, 31 … 36; ikut: PR-UX-37, 40, 44 —
  tidak punya baris sendiri di TRACKER) — K-47, K-50, K-51 (tampilan batas persetujuan)

## Cek ulang "Keadaan sekarang" (di `0a91095`)

| # | Hasil |
|---|---|
| 1 | Berlaku, bergeser: `RoleEditorDrawer.jsx:124` (`copyFrom` menetapkan `baseRole` + `cross` untuk peran baru); `routers/access_roles.py:31` (`RolePatch` tanpa `base_role`) |
| 2 | Berlaku. `RoleMenuPreview.jsx:28`; `roles.js:395` (`roleCanSee`) — peran bawaan tidak punya jalur menambah menu |
| 3 | Berlaku, bergeser: `custom_role_service.py:706` (`preview_role` → `turn_alerts`, `screens`, `levels`) |
| 4 | Berlaku. `AccountFormDrawer.jsx:49`; `roles.js:147`; `user_admin_service.py:145` (yang terakhir sudah himpunan hidup `CROSS_ENTITY_ROLES`) |
| 5 | Berlaku. `role_registry.py:283`, `:292`; bergeser `custom_role_service.py:579` (`None if want == cross_entity_default`) — dibuktikan U9 merah |
| 6 | Berlaku, bergeser: `customer_service.py:415` (+ `can_view_credit` `:450`, pola sama — dicatat PR-T4 sebagai milik PR-T6); `bank.py:35` (+ `_guard_cash_doc` `:116`, pasangan buka-satu dokumen); `cash.py:48` |
| 7 | Berlaku, bergeser: `dependencies.py:116`, `:139` |
| 8 | Berlaku. `entityApi.js:16`; `apiError.js:76` |
| 9 | Berlaku. `EntitiesAccessView.jsx:28` |
| 10 | Berlaku, bergeser: `RoleAccessPanel.jsx:19`; `RoleEditorDrawer.jsx:325` (`canMove={!readOnly}` — `readOnly` hanya peran terkunci / PR-T1) |
| 11 | Berlaku. `RoleNavTree.jsx:20` |
| 12 | Sebagian: `marketing` SUDAH berlabel ("Pemasaran", PR-T5) — diganti "Marketing & Sosial Media"; aksi `close`/`count`/`review`/`set` sudah berlabel PR-T5 ("Tutup"/"Hitung"/"Tinjau"/"Atur") — diganti label tabel 8. Bergeser: `RESOURCE_LABEL` `:446`, `ACTION_LABEL` `:483` |
| 13 | Berlaku. `user_admin_service.py:344` — dibuktikan U11 merah |
| 14 | Berlaku, bergeser: `AccountFormDrawer.jsx:29`; `schemas.py:176`; `user_admin_service.py:249` |
| 15 | Berlaku, bergeser: `custom_role_service.py:723`; `useSessionSync.js:113` |
| 16 | Berlaku, bergeser: `access_roles.py:140`; `auditLabels.js:88` (`custom_role_created`, `custom_role_deleted`, `role_users_moved` tak berlabel) |
| 17 | Berlaku, bergeser: `custom_role_service.py:164`, `:686` |

"Sepuluh tempat lain" (butir Server 5): di `0a91095` ada **sembilan** — `services/special_order_fulfillment.py:219`,
`services/rnd_revalidation_service.py:234`, `services/sales_order_helpers.py:105`, `routers/sales_returns.py:379`,
`routers/special_orders.py:706` dan `:824`, `routers/outbound_picking.py:638`, `routers/rnd.py:127` dan `:713`
(+ dua di `dependencies.py`). Sapuan U2 membuktikan tidak ada sisa (lihat di bawah).

## PR-09 — Pesan penolakan memuat kode izin (Z6) dan layar peran/akun tidak menjawab "bisa apa"
- Berlaku di HEAD: ya (butir 1–17 di atas; U1–U16 merah di kode lama).
- Akar masalah: penolakan izin ditulis sebagai kode teknis di 11 tempat; layar peran hanya mengatur centang, tanpa
  ringkasan hasil; "salin dari peran" mencampur dua hal (peran dasar dan izin); lintas PT peran kustom disimpan sebagai
  "ikut bawaan" padahal bawaannya dihitung dari nilai asli peran dasar; tiga titik server memakai daftar nama
  `("admin","manager")`; akun memakai sandi cadangan, tautan karyawan lama tertinggal, pindah massal menulis `role`
  langsung.
- Perubahan perilaku (sebelum → sesudah):
  - **403**: "Permission ditolak: goods_receipt.view" → "Anda belum punya akses untuk melihat Kedatangan Barang. Minta
    Admin menambahkan akses 'Operasi Gudang'." (`dependencies.denied_message`; beberapa izin: "Anda belum punya akses ke
    layar ini. Minta Admin menambahkan salah satu akses: '…', '…'."); header `X-Permission-Denied: <sumber>.<aksi>[,…]`
    (`dependencies.denied`). Penjelas yang berguna dipertahankan tanpa kode (`note`, mis. "Roll tanpa tag wajib
    dicetak/diverifikasi RFID."). Sopir × 802 rute GET: 631 → **0** pesan 403 berkode/“Permission”/“Role”/`cr_`.
  - **Ringkasan peran** `GET /api/access/roles/{rid}/summary` (izin `permission.view` atau `user.view`) dan `summary` +
    `nav_added` di `POST /api/access/roles/preview` (kini menerima `base_role`, `traits`, `cross_entity`) — bentuk persis
    spesifikasi; modul "Tidak ada" tidak dicantumkan; modul membawa juga `partial`. `approvals`: baris `approval_policies`
    lapisan grup yang mencantumkan peran ini (`roles` memuat id peran), atau `{"follows_rank_of": <peran dasar / peran
    itu>}` bila koleksi kosong. Kode di `services/role_insight_service.py` (baru).
  - **Peran dasar**: `PATCH … {"base_role": …}` (hanya peran kustom; "" = tanpa peran dasar; peran bawaan selain
    Admin). Izin tidak berubah; sifat yang belum diisi sendiri + menu warisan ikut peran dasar baru; **lintas PT dipatok**
    (nilai efektif sekarang disimpan bila belum tersimpan). Pesan 400 tiga kalimat spesifikasi; pesan lama "Peran acuan
    (template) …" dan "… dijadikan template." diganti (juga di `POST /api/access/roles` dan pratinjau).
  - **Menu peran bawaan boleh bertambah**: `GET /api/roles` → `nav: {"add": nav_allowed(sekarang) − nav_allowed(bawaan),
    "remove": []}` untuk 13 peran bawaan (`role_registry.apply_builtin_nav`, dipanggil `sync_registry`); kosong saat
    pasang (U5). Layar: `roles.js` `NAV_EXTRA` dibaca `roleCanSee` untuk peran itu sendiri (tidak diwariskan ke peran
    kustom berdasarnya).
  - **Lintas PT**: `cross_entity_default` peran kustom = nilai EFEKTIF peran dasarnya; peran kustom selalu disimpan
    eksplisit; ya → tidak memuat `accounts_to_review: [{id, name, allowed_entities: [label PT]}]` (akun peran itu
    berpenugasan > 1 PT; tidak diubah otomatis). `can_access_customer`, `can_view_credit`, daftar rekening/kas tingkat grup
    (+ penjaga buka-satu rekening `_guard_cash_doc`) memakai `CROSS_ENTITY_ROLES` hidup.
  - **Akun**: `UserCreate.password` wajib (422 bila tidak ada) dan < 8 → 400 "Kata sandi minimal 8 karakter."; tidak ada
    sandi cadangan. Mengganti/melepas `employee_id` mengosongkan `hr_employees.user_id` karyawan lain yang menunjuk akun
    itu. `move_users` → `user_admin_service.update_user(id, {"role": tujuan})` per akun (PT dihitung ulang, sesi dicabut
    "peran berubah"); router menulis `user_updated` per akun + `role_users_moved`; akun yang ditolak dilaporkan di
    `failed`, tidak menggagalkan yang lain. `deletable` = peran kustom tanpa akun apa pun; field `users_inactive`.
    "Role wajib dipilih." → "Peran wajib dipilih."; alasan cabut sesi "role berubah" → "peran berubah".
  - **Riwayat** `GET /api/access/roles/{rid}/history?limit=50` (`permission.view`): `role_access_updated`,
    `role_access_reset`, `custom_role_created`, `custom_role_deleted` (+ `role_followed_base`, `role_users_moved`) kini
    berpotret `before`/`after` = `{permissions, hidden_views, cross_entity, traits, base_role}` (+ `label`, `users`);
    `added`/`removed` = "{halaman}: {aksi}", `other` = kalimat sifat/menu/PT/peran dasar. Baris lama tanpa potret →
    "Rincian perubahan tidak tercatat …".
  - **RoleCreate.hidden_views** — satu panggilan pembuatan (PR-UX-37); editor tidak lagi PATCH kedua.
  - **Label tabel 8** + tiga label jejak audit.
  - **Layar** — editor: "Peran dasar" (keterangan, konfirmasi "Ganti peran dasar ke {peran}?" berisi `follows_base`
    sebelum/sesudah) dan "Salin hak akses dari…" (hanya centang); judul duplikat "(peran dasar: …)"; "Atur rinci"; panel
    **Ringkasan peran** (pratinjau server ±500 ms; kerangka / "Ringkasan tidak bisa dimuat." + Coba lagi / "Belum ada modul
    yang dinyalakan."); pratinjau menu peran bawaan = peran itu + `nav_added`, tanda "baru", catatan "Daftar ini hanya
    menu. …"; "Menu & tab yang tampil" tanpa id grup/hub + catatan; kotak lintas PT "Bawaan: …"; dialog "Tinjau penugasan
    PT" + **Buka Akun & Akses**; **mode baca** (tanpa `permission.update`: "Lihat Hak Akses · {peran}", isian mati, tanpa
    simpan/hapus/kembalikan/pindah, tombol "Tutup"); tab **Riwayat**; petunjuk hapus "Masih dipakai {n} akun ({m}
    nonaktif) — …". Akun & Akses: "Pilih peran…" (wajib), "· peran dasar {peran}", ringkasan peran pendek + **Lihat hak
    peran ini** (pemegang `permission.view`), kalimat lintas PT dari `GET /api/roles`, konfirmasi "Lepas tautan ke
    {karyawan}?"; tab mengikuti izin; `errText` → `apiErrorText`; peran berubah di tengah sesi → halaman awal peran baru +
    "Peran Anda berubah menjadi {peran}.".
- Fixture disiapkan langsung vs proses bisnis: karyawan HR (U11), akun Gudang berpenugasan PT kedua + id PT tak aktif
  (U13), pelanggan PT uji (U10, U17), rekening & transaksi kas grup (U17) disisipkan langsung; sisanya lewat API.
- Dampak pada modul terkait: pesan 403 seluruh aplikasi (teks saja; kode, izin, dan urutan pemeriksaan tidak berubah);
  pindah akun massal kini ikut aturan ubah akun (akun yang karyawan HR-nya tanpa PT aktif ditolak per akun).
- Status: implemented_pending_review.

## Berkas berubah

| Berkas | Isi |
|---|---|
| `backend/dependencies.py` | `DENIED_VERB`, `denied_message`, `denied` (+ header); `require_permission`/`require_any_permission` |
| `backend/services/special_order_fulfillment.py`, `rnd_revalidation_service.py`, `sales_order_helpers.py`; `backend/routers/sales_returns.py`, `special_orders.py`, `outbound_picking.py`, `rnd.py` | Sembilan penolakan manual → `denied`/`denied_message` (`special_order_fulfillment.denied_for` supaya pasangan dinamis tetap dinamis bagi INV-PERM-01) |
| `backend/access_modules.py` | Blok `PR-T6` label tabel 8 (sumber daya, aksi, tiga modul) |
| `backend/role_registry.py` | `cross_entity_default` (efektif peran dasar); blok `PR-T6` `nav_added_for`, `apply_builtin_nav`; `public_list` `nav` peran bawaan |
| `backend/services/custom_role_service.py` | `sync_registry` + `apply_builtin_nav`; `users_inactive`/`deletable`; `create_custom` (pesan, `hidden_views`); `update_role` (`base_role`, lintas PT eksplisit, `accounts_to_review`, patok lintas PT); `preview_role` (+ `summary`, `nav_added`); `move_users` lewat `update_user`; blok `PR-T6` (`_save_hidden`, `_clean_hidden`, `_clean_base_change`, `_accounts_to_review`, `projected_scope_after`) |
| `backend/services/role_insight_service.py` (baru) | `role_summary`, `hypothetical_traits`, `snapshot`, `role_history` |
| `backend/routers/access_roles.py` | `RoleCreate.hidden_views`, `RolePatch.base_role`, `RolePreview` (+`traits`, `cross_entity`); `GET …/summary`, `GET …/history`; audit berpotret; `user_updated` per akun saat pindah massal; penjaga cakupan data juga saat ganti peran dasar |
| `backend/services/user_admin_service.py`, `backend/schemas.py` | Sandi wajib ≥ 8; tautan karyawan lama dibersihkan; "Peran wajib dipilih."; "peran berubah" |
| `backend/services/customer_service.py`, `backend/routers/bank.py`, `backend/routers/cash.py` | `CROSS_ENTITY_ROLES` hidup |
| `frontend/src/features/settings/entities/RoleEditorDrawer.jsx` | Editor (di atas); hex 57 → 0, huruf < 12 px 27 → 0 |
| `…/RoleBaseControls.jsx`, `RoleSummaryPanel.jsx`, `RoleHistoryTab.jsx`, `RoleSettingsBoxes.jsx`, `AccountRoleSummary.jsx`, `useRolePreview.js` (baru) | Dua kontrol + dialog (lewat `ConfirmModal`), panel ringkasan, tab Riwayat, kotak lintas PT & kelola akun, ringkasan formulir akun, satu pratinjau berdebounce |
| `…/RoleMenuPreview.jsx`, `RoleNavTree.jsx`, `RoleModuleRow.jsx`, `RoleNotifPreview.jsx`, `RoleTraitsPanel.jsx`, `RoleAccessPanel.jsx`, `RoleDangerDialog.jsx` | Pratinjau menu peran bawaan + "baru"; tanpa id grup/hub; "Atur rinci"; pratinjau bersama; turunan sifat mengikuti peran dasar yang sedang diganti; `canManage`/`onOpenAccounts`; token warna |
| `…/AccountFormDrawer.jsx`, `AccountList.jsx`, `EntitiesAccessView.jsx`, `entityApi.js` | Formulir akun; tab berizin; `errText` → `apiErrorText`; `accessRoleSummary`, `accessRoleHistory`; `CROSS_ROLES` dihapus |
| `frontend/src/config/roles.js`, `auditLabels.js`, `frontend/src/hooks/useSessionSync.js` | `NAV_EXTRA`; tiga label audit; peran berubah di tengah sesi |
| `scripts/guardrails/baselines/role_gate_ui.json` | `--update`: 19 → 18 gerbang (`AccountFormDrawer.jsx` 1 → 0, catatan pemegang PR-T6 hilang) |
| Uji | `backend/tests_mem/test_PRT6_layar_peran.py` (U1–U16 + U18b, U19b), `test_PRT6_sapuan.py` (U17) + `data/kode_sebelum_PRT6.json` (dibuat dari kode `0a91095`, `KN_PRT6_TULIS_SEBELUM=1`); jest `frontend/src/features/__tests__/prt6LayarPeran.test.js` (14); lapis A `backend/tests/test_bp_PRT6_layar_peran.py` (lulus di MongoDB asli) |
| POC disesuaikan | `backend/test_core_e1e2_poc.py` E2.1e/E2.1f: payload ditambah `password` (yang diuji aturan HR, bukan sandi; tanpa itu 422 sebelum aturannya) — tidak ada di daftar gate |
| Dokumen | `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.3 (+ "Atur rinci" di §9.1), `memory/PRD.md`, `CODEBASE_MAP.md` (generator) |

## Uji penerimaan

Merah di kode lama: berkas uji final dijalankan pada salinan `git archive 0a91095` backend
(`bukti/PR-T6/merah_kode_lama.log`) → **18 dari 19 gagal** dengan sebab masalahnya; U17 lulus (memang harus).
Hijau: `bukti/PR-T6/hijau_kode_baru.log` (19 lulus).

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | B | ya ("Permission ditolak: goods_receipt.view") | Lulus — kalimat persis; tanpa titik-kode; header `X-Permission-Denied: goods_receipt.view` |
| U2 | B | ya (631 pesan berkode) | Lulus — Sopir × 802 rute GET: 669 jawaban 403, 0 cocok pola (`bukti/PR-T6/u2_sapuan_sopir_lama_vs_baru.log`) |
| U3 | B | ya (404) | Lulus — 200 · 403 · 403; `milik_sendiri`; `sales-home`; + halaman SO "bisa Lihat …; tidak bisa Kirim tanpa lunas …" |
| U4 | B | ya (`summary` tidak ada) | Lulus — modul `hr` `view`; `nav_added` ∋ `hrd` |
| U5 | B | ya (`nav` = null) | Lulus — 13 peran bawaan `{"add": [], "remove": []}` |
| U6 | B | ya | Lulus — Finance `nav.add` ∋ `hrd`, `hr-people` (dikembalikan sesudahnya) |
| U7 | B | ya (`base_role` tetap `finance`) | Lulus — `sales`; izin sama; `data_scope` `milik_sendiri`; lintas PT tetap |
| U8 | B | ya (200) | Lulus — dua kalimat persis + "Peran dasar tidak dikenal." + POST beracuan Admin |
| U9 | B | ya (tetap benar) | Lulus — salah; + `accounts_to_review` memuat akun 2 PT berlabel nama PT; penugasan tidak diubah |
| U10 | B | ya (200) | Lulus — 403 |
| U11 | B | ya (E1 tetap tertaut) | Lulus — E1 kosong, E2 = X; lalu E2 kosong |
| U12 | B | ya (akun dibuat) | Lulus — 422 · 400 "Kata sandi minimal 8 karakter."; tidak ada akun |
| U13 | B | ya (id PT tak aktif tertinggal, tanpa `user_updated`) | Lulus — PT dihitung ulang, sesi terhapus, satu `user_updated` per akun (3 akun: 2 akun uji + akun seed Gudang, lihat Menyimpang 5), satu `role_users_moved` |
| U14 | B | ya (404) | Lulus — 2 butir; lama `removed` = ["Pesanan Penjualan (SO): Batalkan"]; baru `added` memuatnya |
| U15 | B | ya (`deletable` benar, `users_inactive` tidak ada) | Lulus — salah; 1 |
| U16 | B | ya ([]) | Lulus — satu panggilan, `["finance-cases"]` tersimpan |
| U17 | B | tidak (memang sama) | Lulus — kode + jumlah baris Manajer seed di 6 rute sama dengan `kode_sebelum_PRT6.json` (termasuk rekening & kas tingkat grup, pelanggan PT lain 200) |
| U18 | layar (uji jalan) | — | **Belum diuji jalan** (peramban tidak dijalankan). Padanan: jest `prt6LayarPeran.test.js` "U18 — …" (dua kontrol, salin tidak mengganti peran dasar, ringkasan "Data yang terlihat: Milik sendiri", "… bisa … tidak bisa …") + lapis B `U18b` + lapis A `test_U18_…` (ditulis) |
| U19 | layar (uji jalan) | — | **Belum diuji jalan**. Padanan: jest "U19 — mode baca …" (judul, isian mati, tanpa simpan/hapus/pindah, tab Riwayat) + lapis B `U19b` (daftar/ringkasan/riwayat 200, simpan 403 berkalimat + header) + lapis A `test_U19_…` (ditulis) |

Jest `prt6LayarPeran.test.js`: kode lama **14/14 gagal** (`bukti/PR-T6/jest_prt6_merah_kode_lama.log`; `RoleSummaryPanel`
belum ada sehingga salinan lama diberi tiruan kosong agar berkas termuat) → kode baru **14/14 lulus**. Juga diuji: dialog
ganti peran dasar (sebelum/sesudah, `base_role` dikirim), petunjuk hapus, judul duplikat, galat/kosong ringkasan &
riwayat, dialog Tinjau penugasan PT, "Menu lain" tanpa id grup, `NAV_EXTRA`, formulir akun (tanpa peran awal, wajib,
kalimat lintas PT dari server — Manajer yang lintas PT-nya dimatikan, label "· peran dasar", konfirmasi lepas tautan),
`errText`, tab berizin, peran berubah di tengah sesi, label audit.

`backend/tests_mem`: sebelum **545 lulus / 2 dilewati / 3 xfail** → sesudah **564 lulus / 2 dilewati / 3 xfail** (+19 uji PR-T6; tidak ada uji
lama yang diubah — `test_PRT5_U12` sempat merah di tengah pengerjaan dan dihijaukan lewat kode, lihat Menyimpang 3).
`tests/test_fe03_access_catalog.py --noconftest`: 6 lulus (fixture akses dibangkitkan ulang — tidak berubah).

Jest seluruhnya (folder kerja terpisah; `bukti/PR-T6/jest_ringkasan_lengkap.log`): HEAD 74 suite lulus / 35 gagal dimuat
(`@radix-ui/primitive/is-development` tidak termuat lokal — kendala lingkungan) / 526 uji → sesudah 75 / 35 (suite yang
sama) / **540 uji, semua lulus**. Suite editor peran lama (`prt5EditorPeran`, `prt4SifatPeran`, `roleCrossEntity`) lulus
tanpa perubahan.

## Penjaga statik (sebelum → sesudah)

`hitung_penjaga.sh` (`bukti/PR-T6/penjaga_hitung_*.log`): `verify_auth_coverage` 28 → 28 (1751 → 1753 cek; dua
endpoint baru berizin), **`verify_ui_standard` 23 → 15** (berkas editor peran/akun tidak lagi di atas garis dasar),
`audit_i18n_id` 111 → 111, `audit_create_modal` 6 → 6, `verify_page_tabs` 1 → 1, `verify_to_list_bound` 6 → 6,
`verify_entity_label` 2 → 2, lainnya PASS/0 → sama. Daftar STATIK `gate.sh` (57 perintah, `bukti/PR-T6/statik_*.log`):
hasil sama dengan HEAD; tiga perintah yang merah di salinan HEAD (`config_wiring` + self-test, `ref_unlink` self-test)
merah hanya karena salinan arsip tanpa `backend/.env`. `verify_role_gate_ui` PASS (garis dasar 19 → 18) + self-test;
`verify_permission_checked` 580 cek lolos + self-test; `verify_custom_modals` PASS (dialog baru lewat `ConfirmModal`);
`verify_atomic_claim` "belum ditinjau" 95 → 95 (lihat Menyimpang 8); `audit_config_wiring --strict` (salinan berjalur
`$W`) keluar 0; `verify_codebase_map` PASS; `verify_role_label`/`verify_error_notice` hijau.

## Penggabungan

Digabung di atas `aea3cec`. Satu konflik di glosarium (baris KP-T2 dan PR-T6 — keduanya dipertahankan);
`access_modules.py`, `test_core_e1e2_poc.py` (KP-T2 + PR-T6), `auditLabels.js`, `EntitiesAccessView.jsx`, `entityApi.js`,
`PRD.md` tergabung otomatis; fixture akses (`test_fe03_access_catalog` 6 lulus) dan `CODEBASE_MAP.md` dibangkitkan ulang;
garis dasar `verify_role_gate_ui` dikencangkan (`--update`): 19 → 18 gerbang, 16 → 15 berkas. `tests_mem` **619 → 638
lulus** / 2 / 3; jest seluruhnya 551/551 (35 suite gagal dimuat karena `@radix-ui`). Lapis A `test_bp_PRT6_layar_peran.py`
bersama lapis A PR-T5/PR-T4: 9 lulus.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `1392969`), sesudah `restore_demo` (data acuan; tiga skrip seed yang
sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Satu jalan gate untuk tiga unit
yang digabung berturut-turut (PK-36 `16b50fe`, KP-T2 `aea3cec`, PR-T6 `1392969`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Hitungan penjaga statik berhitung sesudah ketiga unit: `verify_ui_standard` 23 → 15 (PR-T6), lainnya sama;
`verify_role_gate_ui` PASS (garis dasar 19 → 18 gerbang), `verify_permission_checked` 580 PASS, `verify_config_text` PASS,
`audit_config_wiring --strict` bersih, `verify_access_catalog_nav` 0. Jest seluruhnya di HEAD akhir 551/551.

## Menyimpang dari blueprint

1. **Sembilan, bukan sepuluh**, tempat penolakan manual di HEAD (daftar di cek ulang). Penjelas yang berguna dipertahankan
   sebagai kalimat tanpa kode (`denied(..., note=...)`).
2. **Lintas PT dipatok saat peran dasar diganti** (spesifikasi: "yang ikut berubah hanya sifat … dan menu warisan").
   Peringkat (`rank`) peran kustom tetap mengikuti peran dasar (`register_custom_roles`) — sisa pemakai `role_satisfies`/
   `role_in` yang masih ada di kode (di luar unit ini) ikut peran dasar baru; dicatat di "Yang perlu direview".
3. **`special_order_fulfillment.denied_for(aksi)`** — `routers/special_orders.py` memakainya supaya pasangan
   `od_fulfillment.cancel` tetap tercatat dinamis bagi INV-PERM-01 (tuple literal di pesan dihitung penjaga sebagai
   pemeriksa literal dan memerahkan `test_PRT5_U12`).
4. **`can_view_credit` dan `bank._guard_cash_doc`** ikut `CROSS_ENTITY_ROLES` hidup (pola sama dengan tiga tempat butir 6;
   tanpa itu daftar rekening grup dan buka-satu rekening grup bisa berbeda pendapat). Kode jawaban Manajer seed sama (U17).
5. **U13**: `move_users` memindahkan SEMUA akun peran asal kecuali pelaku — di database tiruan termasuk akun seed
   `warehouse@` — jadi baris `user_updated` = 3, bukan 2; uji memeriksa "satu per akun yang dipindah". Fixture memakai id
   PT tak aktif supaya "dihitung ulang" terlihat (Gudang → Sales sama-sama tidak lintas PT).
6. **Pratinjau menerima `base_role: None`** (dulu `""`): `None` = tidak diubah (peran yang disunting) / tanpa peran dasar
   (peran baru). Satu-satunya pemanggil (`RoleNotifPreview`) kini memakai pratinjau bersama editor.
7. **Potret audit `permissions` = daftar "sumber_daya.aksi"** (bukan peta) — penyaring rahasia jejak audit menyamarkan
   kunci yang memuat "pin" (`gl_mapping`).
8. **`_save_hidden`** — tulisan `hidden_views` lewat pembantu (pola `_set_cross_entity`); tanpa itu INV-ATOMIC-01 menghitung
   `POST /api/access/roles` sebagai endpoint multi-koleksi baru (95 → 96), padahal endpoint itu sudah menulis
   `permission_settings` lewat pembantu sejak sebelum unit ini.
9. **Konfirmasi ganti peran dasar hanya untuk peran yang sudah ada** (peran baru: langsung, karena belum ada akun).
10. **Kotak tingkat "Semua modul"** dipisah dari baris kontrol peran dasar; tombolnya kini `secondary-button btn-sm`.
11. `errText` tetap merangkai `message` + `blockers` + `hint` untuk detail berobjek berpenghalang (dialog arsip PT);
    selebihnya `apiErrorText`.

## Asumsi

- `ASUMSI` spesifikasi dipakai apa adanya (peran dasar diganti, bukan dihapus; menu bawaan bertambah hanya sebesar selisih
  izin bawaan; mematikan lintas PT tidak mempersempit penugasan; label tabel 8 dari lampiran B §7).
- "Koleksi `approval_policies` ada" = berisi minimal satu dokumen; baris yang dicantumkan = lapisan grup, aktif,
  `roles` memuat id peran (baris `any_holder` tidak dicantumkan).
- "Akun peran itu" pada `accounts_to_review` = semua akun berperan itu (aktif & nonaktif).

## Hambatan lingkungan

- Peramban/dev server tidak dijalankan → U18, U19 **belum diuji jalan** (tangkapan layar belum ada). Lapis A
  `backend/tests/test_bp_PRT6_layar_peran.py` dijalankan saat penggabungan: lulus.
- Jest: 35 suite gagal dimuat karena `@radix-ui/...` (sama di HEAD).

## Titik henti

- H3: tidak ada migrasi data. Baris audit lama tanpa potret tetap apa adanya (riwayat menulis "Rincian perubahan tidak
  tercatat …").
- H7: tidak ada yang disentuh di `middleware/`/gerbang RFID. `routers/outbound_picking.py` (pemindaian muat, pengecualian
  roll tanpa tag) hanya diganti teks pesan 403-nya; logika tidak berubah.

## Yang perlu direview

- Pindah akun massal kini memakai aturan ubah akun: akun yang karyawan HR-nya tanpa PT aktif → ditolak per akun
  (`failed`), dulu ikut terpindah.
- Teks 403 berubah di seluruh aplikasi; alat yang mencocokkan "Permission ditolak" → header `X-Permission-Denied`.
  Penerjemah layar lama (`apiError.permissionDeniedText`) dipertahankan.
- Peringkat peran kustom ikut peran dasar saat diganti (Menyimpang 2).
- Berkas bersama yang disentuh (blok `PR-T6`): `access_modules.py` (label), `role_registry.py` (dua fungsi + satu baris
  `public_list` + `cross_entity_default`), `roles.js` (`NAV_EXTRA`); `permissions_config.py` tidak disentuh, tidak ada
  izin baru.
- Butir garis dasar `verify_role_gate_ui` yang pernah dicatat untuk PR-T6 — `hr/AiIllustrationPanel.jsx` (berkas yatim;
  aturan servernya `design_gallery_service.py:620`) — **tidak** dikerjakan: tidak ada di spesifikasi PR-T6.

Status: implemented_pending_review.
