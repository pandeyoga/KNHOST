# PR-T9 — Perubahan izin peran bawaan bertahan setelah server dinyalakan ulang; satu sumber izin bawaan

| | |
|---|---|
| Gelombang | 2 (tinggi yang murah) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PK-02 |
| Menutup temuan | PR-12, PR-14 (beserta butir layar PR-UX-06, PR-UX-25, PR-UX-26) |
| Keputusan | K-36 (izin kwitansi Sales tetap seperti hari ini), K-47 |
| Standar | §3.2, §3.3 (E3), §4 (L5, L6), §6 |
| Lingkungan uji | B |

## Tujuan

Izin peran bawaan yang diubah Admin tidak lagi kembali sendiri setelah server dinyalakan ulang. Izin bawaan punya satu
sumber (`DEFAULT_PERMISSIONS`) yang isinya sama dengan yang benar-benar berlaku hari ini. "Kembalikan ke bawaan"
mengembalikan semua yang bisa diubah, dan peran kustom yang belum pernah diubah di sebuah modul ikut menerima izin
baru peran dasarnya.

## Keadaan sekarang

| # | Fakta | Jangkar | Bukti |
|---|---|---|---|
| 1 | Setiap proses awal menjalankan tiga daftar tanpa syarat: cabut (`REVOKE`), atur ulang (`RESCOPE`), beri (`GRANT`). Uji: Admin mencabut modul "Uang Masuk, Piutang & Faktur Pajak" dari Sales → `run_bootstrap()` → `ar_receipt: ["create"]` kembali | `backend/bootstrap.py:402` (`sync_permission_revocations`), dipanggil di `backend/bootstrap.py:1648` (`sync_permission_revocations`) | [dijalankan] `docs/audit/konfigurasi-peran-2026-11-13/bukti/t4_peran_bawaan.py` |
| 2 | Dua sumber bertentangan: berkas izin bawaan menulis Sales hanya melihat kwitansi, sedangkan `RESCOPE` dan `GRANT` memberi `ar_receipt.create`. Yang berlaku saat jalan adalah yang kedua | `backend/permissions_config.py:142` (`ar_receipt`); `backend/bootstrap.py:425` (`RESCOPE`); `backend/bootstrap.py:460` (`GRANT`) | [dijalankan] keluaran `t4_peran_bawaan.py`: "sales.ar_receipt sebelum: ['view', 'create']" |
| 3 | Selisih izin bawaan vs izin yang berlaku setelah proses awal pada basis data baru hanya satu pasangan: `sales` × `ar_receipt.create`. Semua 37 butir `GRANT` lain sudah ada di `DEFAULT_PERMISSIONS` | `backend/bootstrap.py:460` (`GRANT`); `backend/permissions_config.py:598` (`design_ownership`) | [dijalankan] tiruan blok baris 411–509 terhadap `DEFAULT_PERMISSIONS` saat menyusun unit ini |
| 4 | `REVOKE` mencabut `approval` dari Finance, lalu `GRANT` memberikannya lagi pada proses awal yang sama; akibatnya dokumen `permission_settings` ditulis ulang pada setiap start | `backend/bootstrap.py:417` (`REVOKE`); `backend/bootstrap.py:463` (`GRANT`); `backend/permissions_config.py:385` (`approval`) | [dijalankan] tiruan yang sama: `changed` selalu benar pada jalan kedua |
| 5 | Penambahan izin bawaan baru sudah berbuku catatan: aksi yang pernah diterapkan dicatat di `defaults_applied`, sehingga pencabutan Admin atas aksi itu tidak dihidupkan lagi | `backend/bootstrap.py:361` (`sync_permission_modules`); `backend/bootstrap.py:378` (`defaults_applied`) | [dibaca] |
| 6 | Penambahan itu hanya berjalan untuk peran bawaan; peran kustom adalah salinan izin peran dasarnya pada saat dibuat | `backend/bootstrap.py:384` (`DEFAULT_PERMISSIONS`); `backend/services/custom_role_service.py:218` (`apply_levels`) | [dibaca] |
| 7 | "Kembalikan ke bawaan" mengembalikan izin dan lintas PT, tidak mengembalikan menu yang disembunyikan | `backend/services/custom_role_service.py:297` (`reset_builtin`); `backend/services/custom_role_service.py:262` (`hidden_views`) | [dibaca] |
| 8 | Tanda "diubah" hanya membandingkan izin, dengan perbandingan daftar yang peka urutan. Pada basis data baru Sales sudah bertanda "diubah" karena butir 2 | `backend/services/custom_role_service.py:129` (`modified`); `frontend/src/features/settings/entities/RoleAccessPanel.jsx:45` (`modified`) | [dibaca] |
| 9 | Tombol "Kembalikan ke bawaan" hanya tampil bila `modified`; teks dialognya "Semua tingkat akses yang Anda ubah pada peran ini dikembalikan ke bawaan sistem…" | `frontend/src/features/settings/entities/RoleEditorDrawer.jsx:276` (`modified`); `frontend/src/features/settings/entities/RoleDangerDialog.jsx:13` (`reset`) | [dibaca] |
| 10 | Basis data baru diisi dengan `DEFAULT_PERMISSIONS` apa adanya | `backend/bootstrap.py:250` (`permission_settings`) | [dibaca] |

Isi tiga daftar di butir 1 (untuk dipindahkan, lihat "Server"): `REVOKE` — `sales` × `purchase_order`,
`purchase_requisition`, `vendor_bill`, `landed_cost`, `input_tax`, `rfq`; `md`, `finance`, `warehouse_admin` ×
`approval`. `RESCOPE` — `sales.price_approval = [view, create, update]`, `sales.tax_invoice = [view]`,
`sales.ar_receipt = [view, create]`, `sales.payment_plan = [view]`, `warehouse.order = [view, deliver]`,
`admin.approval = [view]`, `manager.approval = [view]`. `GRANT` — 37 pasangan peran × sumber daya (89 aksi).

## Perubahan

### Data

`permission_settings` (dokumen `id: "default"`):

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `migrations_applied` | daftar teks | tidak (tidak ada = belum pernah dicatat) | Id butir migrasi izin sekali-jalan yang sudah dijalankan. Butir yang id-nya ada di sini tidak dijalankan lagi |
| `defaults_applied` | objek (sudah ada) | — | Tidak berubah bentuk. Pada jalan pertama unit ini ditambah seluruh pasangan `GRANT` lama (lihat langkah garis dasar) |

`custom_roles`:

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `pending_defaults` | objek `{<sumber daya>: [<aksi>, …]}` | tidak | Izin baru peran dasar yang **belum** diikuti peran kustom ini karena modulnya sudah pernah diubah |

Tanpa indeks baru. Tanpa migrasi data selain langkah garis dasar di bawah, yang tidak mengubah `matrix`.

### Server

**1. Satu sumber izin bawaan — `backend/permissions_config.py`**

- `DEFAULT_PERMISSIONS["sales"]["ar_receipt"]` menjadi `["view", "create"]`; komentar di atasnya diganti dengan
  "Sales mencatat kwitansi dari HP (keputusan Sesi 16, K-36); `void` dan keputusan selisih tetap Finance".
- Tidak ada perubahan lain pada berkas ini. Setelah itu `DEFAULT_PERMISSIONS` = izin yang berlaku hari ini (butir 3).

**2. Migrasi sekali-jalan — `backend/bootstrap.py`**

Konstanta modul baru `PERMISSION_MIGRATIONS: List[Dict[str, Any]]`. Tiap butir:
`{"id": str, "kind": "revoke" | "rescope", "role": str, "resource": str, "actions": List[str]}` (`actions` hanya untuk
`rescope`). Isi awal = 15 butir dari daftar lama, dengan id tetap berbentuk `<kind>:<role>:<resource>`:

| Jenis | Butir |
|---|---|
| `revoke` (8) | `sales` × 6 sumber daya di atas; `md:approval`; `warehouse_admin:approval` |
| `rescope` (7) | `sales:price_approval`, `sales:tax_invoice`, `sales:ar_receipt`, `sales:payment_plan`, `warehouse:order`, `admin:approval`, `manager:approval` |

`revoke:finance:approval` **tidak** dipindahkan (bertentangan dengan izin bawaan Finance, butir 4). Daftar `GRANT`
dihapus seluruhnya: semua pasangannya kini ada di `DEFAULT_PERMISSIONS` dan ditangani `sync_permission_modules`.

Fungsi baru `async def ensure_permission_ledger() -> None`, dipanggil di `run_bootstrap` **tepat sebelum**
`sync_permission_modules` (urutannya penting: tanpa ini `sync_permission_modules` menambahkan `ar_receipt.create`
sekali lagi ke Sales yang izinnya sudah dicabut Admin):

1. Baca `permission_settings`. Tidak ada dokumen, atau `migrations_applied` sudah ada → selesai.
2. **Garis dasar**: tulis `migrations_applied` = semua id di `PERMISSION_MIGRATIONS` saat itu. Bila
   `defaults_applied` sudah ada, gabungkan ke `defaults_applied[peran][sumber daya]` setiap aksi dari konstanta baru
   `_LEGACY_GRANTS` (salinan isi `GRANT` lama, hanya dipakai langkah ini); bila belum ada, biarkan —
   `sync_permission_modules` membuatnya seperti sekarang. `matrix` tidak disentuh. Alasannya: blok lama sudah berjalan
   pada setiap start sebelumnya, jadi semua butirnya sudah pernah diterapkan.

`async def sync_permission_revocations() -> None` (nama dan tempat panggil dipertahankan):

1. Baca `permission_settings`. Tidak ada dokumen → selesai.
2. Untuk tiap butir yang id-nya belum ada di `migrations_applied`, terapkan pada `matrix` (`revoke`: hapus sumber
   daya dari peran; `rescope`: ganti daftar aksi bila sumber daya ada pada peran), lalu `$addToSet` id.
3. Tulis ke basis data hanya bila ada yang berubah (tidak ada tulisan pada start biasa).

Aturan untuk butir baru di masa depan: tambahkan butir ber-id baru di akhir daftar; jangan mengubah butir lama.

**3. Peran kustom mengikuti izin baru peran dasarnya — `sync_permission_modules`**

Setelah sebuah aksi bawaan baru `(sumber daya, aksi)` diterapkan ke peran bawaan `R` (cabang `todo` yang sudah ada),
untuk setiap dokumen `custom_roles` dengan `base_role == R`:

- `M` = modul di `access_modules.MODULE_CATALOG` yang memuat sumber daya itu.
- **Ikut** bila izin peran kustom pada semua sumber daya `M` (sebelum penambahan) sama persis, sebagai himpunan,
  dengan izin `R` pada `M` sebelum penambahan, dan himpunan itu tidak kosong → aksi ditambahkan ke
  `matrix[peran kustom][sumber daya]`; `custom_roles.levels` dihitung ulang dengan `levels_of`.
- **Tidak ikut** selain itu (modul sudah diubah Admin, modul kosong, atau sumber daya tidak masuk modul mana pun) →
  aksi dicatat di `custom_roles.pending_defaults`.

Peran dasar hanya dibaca satu tingkat (`base_role` peran kustom), sama seperti `role_registry.role_in`.

**4. "Kembalikan ke bawaan" lengkap — `backend/services/custom_role_service.py`**

- `reset_builtin(rid)`: selain izin dan lintas PT, juga `$unset` `hidden_views.<rid>`; memanggil `load_hidden_views()`
  sebelum membangun jawaban.
- `_role_view`: `modified` = benar bila salah satu berbeda dari bawaan: izin (dibandingkan per sumber daya sebagai
  himpunan; daftar kosong = tidak ada), menu tersembunyi (tidak kosong), lintas PT (`cross_entity_overridden`).
  Field baru `modified_parts`: daftar dari `"izin"`, `"menu"`, `"lintas_pt"`.
- `_role_view` untuk peran kustom: field baru `pending_from_base` (isi `pending_defaults`, bawaan `{}`) dan
  `pending_from_base_count` (jumlah aksi).

**5. Endpoint baru**

| Metode + path | Izin | Isi permintaan | Jawaban | Galat |
|---|---|---|---|---|
| `POST /api/access/roles/{rid}/follow-base` | `permission.update`; pelaku tidak boleh mengikutkan perannya sendiri kecuali Admin; bila `backend/services/access_guard.py` (lahir di PR-T1) sudah ada, panggil `assert_can_shape_role` dengan izin hasil | `{"resources": [<sumber daya>, …]}` atau `{}` = semua yang tertunda | Bentuk `get_role` setelah aksi tertunda ditambahkan dan dihapus dari `pending_defaults` | 400 "Hanya peran kustom yang punya peran dasar yang bisa mengikuti izin baru." · 400 "Tidak ada izin baru dari peran dasar untuk diikuti." · 403 "Anda tidak bisa mengubah hak akses peran Anda sendiri — minta Admin melakukannya." · 404 "Peran tidak ditemukan." |

Jejak audit: aksi `role_followed_base`, sumber daya `custom_role`, isi `{label, added: {<sumber daya>: [aksi]}}`.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan izin baru. Satu perubahan nilai bawaan: `sales` × `ar_receipt` = `view`, `create` — sama dengan
yang berlaku hari ini (K-36).

### Layar

Pengaturan › Perusahaan & Akun › Badan Usaha & Akses › tab Peran & Hak Akses.

- `frontend/src/features/settings/entities/RoleDangerDialog.jsx`, jenis `reset` — isi: "Izin, menu yang
  disembunyikan, dan akses lintas PT peran ini dikembalikan ke bawaan sistem. Akun yang memakainya langsung mengikuti."
- `frontend/src/features/settings/entities/RoleEditorDrawer.jsx` — pesan berhasil: "Peran “{label}” dikembalikan ke
  bawaan: izin, menu, dan akses lintas PT." Tombol **Kembalikan ke bawaan** tampil bila `role.modified` (kini
  mencakup tiga hal).
- Editor peran kustom yang `pending_from_base_count > 0`, di atas daftar modul: catatan "Peran dasar {label peran
  dasar} mendapat {n} izin baru yang belum diikuti peran ini." dengan tombol **Ikuti peran dasar**. Konfirmasi:
  judul "Ikuti izin baru peran dasar?", isi daftar "{label sumber daya}: {label aksi}, …" (label dari
  `/api/access/modules`), tombol **Ya, ikuti** dan **Batal**. Hanya untuk pemegang `permission.update`.
- `frontend/src/features/settings/entities/entityApi.js` — fungsi baru `followBaseAccessRole(id, resources)`.

## Uji penerimaan

Persiapan bersama: berkas `backend/tests_mem/data/matriks_bawaan_sebelum_PRT9.json` dibuat pada langkah kerja 1,
**sebelum** kode diubah, dari jawaban `GET /api/access/roles` (izin tiap peran bawaan). `adm` = admin seed. Peran uji
baku menurut `02` §6. "Nyalakan ulang" = `await bootstrap.run_bootstrap()`.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | basis data baru | `GET /api/access/roles` | Untuk 13 peran bawaan, izin per sumber daya (sebagai himpunan) sama dengan berkas "sebelum" — tidak ada peran yang izin efektifnya berubah |
| U2 | B | basis data baru | `GET /api/access/roles/sales` | `permissions.ar_receipt` = `["view", "create"]`; `modified` = salah; `modified_parts` = `[]` |
| U3 | B | — | `adm`: `PATCH /api/access/roles/sales` `{"levels": {"ar": "none"}}` → nyalakan ulang → `GET /api/access/roles/sales` | `ar_receipt` tidak ada di `permissions` (sebelum unit: `["create"]`) |
| U4 | B | — | `adm`: `PATCH /api/access/roles/warehouse` dengan `permissions` = izin sekarang, `order` ditambah `confirm` → nyalakan ulang | `order` Gudang tetap memuat `confirm` |
| U5 | B | — | `adm`: `PATCH /api/access/roles/finance` `{"levels": {"approval": "none"}}` → nyalakan ulang | `approval` tetap tidak ada pada Finance |
| U6 | B | basis data baru, catat `permission_settings.updated_at` | Nyalakan ulang dua kali tanpa perubahan | `updated_at` tidak berubah; `migrations_applied` berisi 15 id |
| U7 | B | tambahkan lewat tambalan uji satu butir `{"id": "revoke:sales:vehicle_log", "kind": "revoke", "role": "sales", "resource": "vehicle_log"}` | Nyalakan ulang; lalu `adm` memberi kembali `vehicle_log: ["view"]` ke Sales; nyalakan ulang lagi | Setelah start pertama Sales tanpa `vehicle_log`; setelah start kedua `vehicle_log` = `["view"]`; id butir ada di `migrations_applied` tepat sekali |
| U8 | B | `adm` membuat peran kustom "Sales Senior" (`base_role: "sales"`, tanpa perubahan); tambalan uji menambah `update` ke `DEFAULT_PERMISSIONS["sales"]["vehicle_log"]` | Nyalakan ulang | Sales dan "Sales Senior" sama-sama memuat `vehicle_log.update`; `pending_from_base_count` = 0 |
| U9 | B | seperti U8, tetapi peran kustom "Sales Sempit" dibuat dengan `levels: {"logistics": "view"}` | Nyalakan ulang | "Sales Sempit" tidak memuat `vehicle_log.update`; `pending_from_base` = `{"vehicle_log": ["update"]}` |
| U10 | B | setelah U9 | `adm`: `POST /api/access/roles/{Sales Sempit}/follow-base` `{}` | 200; `vehicle_log` memuat `update`; `pending_from_base_count` = 0; panggilan kedua → 400 "Tidak ada izin baru…" |
| U11 | B | "Manajer Kosong"; tambalan uji menambah `update` ke `DEFAULT_PERMISSIONS["manager"]["uom"]` | Nyalakan ulang | Manajer memuat `uom.update`; "Manajer Kosong" tetap tanpa izin `uom`; tertunda tercatat |
| U12 | B | — | `adm`: `PATCH /api/access/roles/finance` `{"hidden_views": ["finance-cases"]}` → `GET` → `POST /api/access/roles/finance/reset` → `GET` | Sebelum reset: `modified` benar, `modified_parts` = `["menu"]`. Sesudah: `hidden_views` = `[]`, `modified` salah |
| U13 | B | setelah U3 | `adm`: `POST /api/access/roles/sales/reset` → nyalakan ulang | `ar_receipt` = `["view", "create"]`; `modified` salah |
| U14 | B | "Tanpa Acuan" hanya dengan `permission.view`; "Sopir" | Masing-masing `POST /api/access/roles/{Sales Sempit}/follow-base` | 403 dan 403 |
| U15 | B | tiruan instalasi lama (fixture sisip): hapus `migrations_applied`; set `defaults_applied.sales.ar_receipt` = `["view"]`; hapus `matrix.sales.ar_receipt` | Nyalakan ulang | `ar_receipt` Sales tetap tidak ada (garis dasar tidak menjalankan butir lama dan tidak menambah `create`); `defaults_applied.sales.ar_receipt` memuat `create`; `migrations_applied` berisi 15 id |
| U16 | layar (uji jalan) | Login Admin setelah U12 persiapan | Buka editor Finance → **Kembalikan ke bawaan** | Dialog memuat teks baru; setelah ya, menu "Kasus Keuangan" tampil lagi pada pratinjau |

Hitungan U6: 8 butir `revoke` + 7 butir `rescope` = 15.

Setelah unit selesai, `t4_peran_bawaan.py` baris (a) harus menampilkan `ar_receipt = None` setelah proses awal
dijalankan ulang.

## Langkah kerja

1. Tulis berkas "sebelum" (U1) dari HEAD; tulis `backend/tests_mem/test_PRT9_izin_bawaan.py` untuk U1–U15. Merah: U2
   (`modified`), U3–U6, U7–U15.
2. `permissions_config.py` (satu baris) + `PERMISSION_MIGRATIONS`, `_LEGACY_GRANTS`, `ensure_permission_ledger`, tulis
   ulang `sync_permission_revocations`. Hijau: U1–U7, U13, U15.
3. Cabang peran kustom di `sync_permission_modules` + `pending_defaults` + endpoint `follow-base`. Hijau: U8–U11, U14.
4. `reset_builtin`, `modified`, `modified_parts`. Hijau: U12.
5. Layar; U16.
6. Gate (`bash scripts/gate.sh --quick` dan penuh); laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`permission_settings.migrations_applied`, `custom_roles.pending_defaults`); `memory/PRD.md`
(satu kalimat: izin peran bawaan tidak lagi ditimpa saat start).

## Di luar lingkup

- Menaikkan modul peran bawaan memunculkan menunya, dan pratinjau menu peran bawaan (PR-UX-05) → PR-T6.
- Menampilkan "beda dengan peran dasar" secara menyeluruh untuk peran kustom yang sudah tertinggal sebelum unit ini →
  PR-T6 (panel "Ringkasan peran").
- Pemberian izin baru hasil penggantian gerbang nama peran kepada peran kustom → PR-T2 (migrasinya memakai
  `migrations_applied` dari unit ini).
- Memecah atau mengganti nama modul akses → PR-T5.

## Asumsi dan risiko

- `ASUMSI:` setiap basis data yang ada sudah pernah dinyalakan dengan kode HEAD, sehingga 15 butir lama dan seluruh
  `GRANT` sudah pernah diterapkan; karena itu garis dasar hanya mencatat, tidak menjalankan. Basis data yang dipulihkan
  dari cadangan lebih tua dari Sesi 16 perlu satu kali start dengan kode lama sebelum kode unit ini.
- `ASUMSI:` aturan "ikut bila modulnya belum pernah diubah" adalah tafsir aman atas permintaan "peran kustom ikut
  pembaruan izin"; tidak ada keputusan pemilik yang lebih rinci. Yang tidak ikut otomatis tetap bisa diikutkan dengan
  satu tombol.
- `ASUMSI:` peran dasar peran kustom selalu peran bawaan (layar hanya mengirim peran bawaan sebagai `base_role`).
- `RISIKO:` butir cabut yang masih diperlukan ternyata belum pernah berjalan di sebuah instalasi → izin lama tetap
  hidup. Pencari: bandingkan `matrix` dengan `DEFAULT_PERMISSIONS` lewat tanda `modified` di layar peran.
  Membatalkan: hapus field `migrations_applied` dan kembalikan fungsi lama; `matrix` tidak pernah diubah oleh garis
  dasar.
