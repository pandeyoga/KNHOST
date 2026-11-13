# PR-T1 — Tutup jalan menaikkan hak sendiri lewat kelola akun dan kelola peran

| | |
|---|---|
| Gelombang | 2 (tinggi yang murah) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PK-02 |
| Menutup temuan | PR-02, PR-13 |
| Keputusan | K-50 |
| Standar | §3.3 (E1–E4), §3.1 (Z6), §6 |
| Lingkungan uji | B |

## Tujuan

Peran yang diberi wewenang mengelola akun atau peran (mis. "Admin HR") tidak lagi bisa menjadikan dirinya Admin,
membuat akun Admin, mereset sandi Admin, atau merakit peran yang lebih berkuasa dari dirinya. Admin tetap bisa semuanya.

## Keadaan sekarang

Semua butir `[dijalankan]` lewat `docs/audit/konfigurasi-peran-2026-11-13/bukti/t3_escalation.py` dan
`t3b_eskalasi_akun.py` pada `dca195b`, dengan peran kustom tanpa peran acuan yang modul "Pengaturan, Pengguna & Hak
Akses"-nya "Kelola penuh":

| Aksi oleh peran kustom itu | Hasil sekarang | Jangkar |
|---|---|---|
| `PATCH /api/users/{id sendiri}` isi `{"data": {"role": "admin"}}` | 200; akun menjadi admin | `backend/routers/users.py:134` (`update_user`) → `backend/services/user_admin_service.py:278` (`update_user`): hanya `assert_valid_role` |
| `POST /api/users` dengan `role: "admin"` | 200; akun admin baru | `backend/routers/users.py:121` (`create_user`) → `backend/services/user_admin_service.py:218` (`create_user`) |
| `POST /api/users/{id admin}/reset-password` | 200; sandi admin diganti, sesinya dicabut | `backend/routers/users.py:183` (`reset_password`) |
| `POST /api/access/roles` dengan `base_role: "manager"` | 200; peran baru mewarisi seluruh izin Manajer | `backend/routers/access_roles.py:78` (`create_role`) → `backend/services/custom_role_service.py:201` (`create_custom`) |
| `PATCH /api/access/roles/manager` | 200; izin peran Manajer berubah | `backend/routers/access_roles.py:87` (`patch_role`) |
| `PATCH /api/access/roles/{peran sendiri}` | 403 — sudah dijaga | `backend/routers/access_roles.py:91` |
| `POST /api/access/roles/admin/move-users` isi `{"to_role": "sales"}` (oleh Admin) | 200; akun Admin aktif dari 1 menjadi 0 — `bukti/t4_peran_bawaan.py` | `backend/services/custom_role_service.py:348` (`move_users`): tanpa penjaga admin terakhir |

Yang sudah ada dan dipertahankan: larangan mengubah peran sendiri; penjaga "admin terakhir"
(`backend/services/user_admin_service.py:156`, `assert_not_last_admin`); peran `admin` terkunci
(`backend/services/custom_role_service.py:21`, `LOCKED_ROLES`).

Pada matriks bawaan hanya `admin` yang memegang `user.create/update/delete` dan `permission.update`, jadi celah ini
terbuka saat Admin mendelegasikan modul tersebut ke peran lain — tepat kegunaan peran kustom.

## Perubahan

### Data

`permission_settings` (dokumen `id: "default"`) mendapat satu field:

| Field | Tipe | Arti |
|---|---|---|
| `assignable_roles` | objek `{<id peran pengelola>: [<id peran>, …]}` | Peran mana saja yang akunnya boleh dikelola pemegang peran pengelola. Tidak ada kuncinya = tidak boleh mengelola akun peran apa pun. `admin` tidak disimpan: selalu boleh semua |

Tanpa migrasi: bawaan kosong berarti hanya Admin yang bisa mengelola akun — sama dengan matriks bawaan hari ini.

### Server

Berkas baru `backend/services/access_guard.py`:

| Fungsi | Perilaku |
|---|---|
| `async def manageable_roles(actor: dict) -> Optional[set]` | `None` bila `actor["role"] == "admin"` (semua); selain itu himpunan dari `assignable_roles[actor.role]` |
| `async def assert_can_manage_account(actor, *, target_user: Optional[dict] = None, new_role: Optional[str] = None)` | Menolak 403 bila peran akun sasaran (bila ada) atau `new_role` (bila ada) di luar `manageable_roles`. Mengubah akun sendiri diperlakukan sama (peran sendiri harus ada di daftar) |
| `def excess(target_perms: dict, actor_perms: dict) -> list[tuple[str, str]]` | Pasangan (sumber daya, aksi) yang ada di sasaran dan tidak ada di pelaku |
| `async def assert_can_shape_role(actor, *, current_perms: Optional[dict], new_perms: dict, new_cross_entity: Optional[bool])` | Admin: lolos. Selain itu menolak 403 bila `excess(current_perms, izin_pelaku)` atau `excess(new_perms, izin_pelaku)` tidak kosong, atau `new_cross_entity` benar padahal peran pelaku tidak lintas PT |

Dipasang di:

| Endpoint | Pemeriksaan tambahan |
|---|---|
| `POST /api/users` | `assert_can_manage_account(actor, new_role=payload.role)` |
| `PATCH /api/users/{id}` | `assert_can_manage_account(actor, target_user=sebelum, new_role=data.get("role"))` |
| `DELETE /api/users/{id}`, `POST …/reactivate`, `…/reset-password`, `…/revoke-sessions` | `assert_can_manage_account(actor, target_user=sasaran)` |
| `POST /api/access/roles` | Hitung izin hasil (izin peran acuan + tingkat/izin rinci) **sebelum** menyimpan → `assert_can_shape_role(actor, current_perms=None, new_perms=hasil, new_cross_entity=…)` |
| `PATCH /api/access/roles/{rid}` | `assert_can_shape_role(actor, current_perms=izin rid sekarang, new_perms=hasil, …)`; field `assignable_roles` hanya diterima bila pelaku `admin`, selain itu 403 |
| `POST /api/access/roles/{rid}/reset`, `DELETE …/{rid}` | `assert_can_shape_role` dengan izin `rid` sekarang sebagai `current_perms` dan (untuk reset) izin bawaan sebagai `new_perms` |
| `POST /api/access/roles/{rid}/move-users` | `assert_can_manage_account` untuk peran asal dan peran tujuan. Tambahan untuk semua pelaku termasuk Admin: bila `rid == "admin"` → 400 "Akun Admin tidak bisa dipindahkan massal. Ubah satu per satu di Akun & Akses."; akun pelaku sendiri tidak ikut dipindah; sesi akun yang dipindah dicabut (sama seperti ubah satu akun) |

Tambahan pada model dan jawaban:

- `RolePatch` (`backend/routers/access_roles.py:24`) mendapat `assignable_roles: Optional[List[str]]`; tiap id harus
  peran yang dikenal dan bukan `admin`.
- `_role_view` (`backend/services/custom_role_service.py:104`) menambah `assignable_roles` (daftar id) dan
  `assignable_roles_labels`.
- `GET /api/users` dan `GET /api/access/roles` menambah per baris `can_manage: bool` untuk pelaku, supaya layar bisa
  mematikan tombol.

Teks galat (403):

| Keadaan | Pesan |
|---|---|
| Peran sasaran di luar daftar | "Anda belum diberi wewenang mengelola akun berperan {label peran}. Minta Admin menambahkannya di Peran & Hak Akses." |
| Memberi peran Admin | "Peran Admin hanya bisa diberikan oleh Admin." |
| Izin hasil melebihi izin pelaku | "Peran ini akan memiliki akses yang Anda sendiri tidak punya ({n} akses, mis. {nama modul}). Minta Admin yang mengaturnya." |
| Mengubah peran yang lebih luas | "Peran {label} memiliki akses lebih luas dari peran Anda, jadi hanya bisa diubah Admin." |
| Lintas PT | "Akses ke semua PT hanya bisa diberikan oleh peran yang juga memilikinya." |

`{nama modul}` diambil dari `access_modules.MODULE_CATALOG` (label modul pemilik sumber daya), bukan `x.y`.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan izin baru.

### Layar

`frontend/src/features/settings/entities/RoleEditorDrawer.jsx`: bila peran yang disunting memegang `user.create` atau
`user.update`, tampilkan satu bagian di bawah daftar modul:

- Judul: **Boleh mengelola akun dengan peran**
- Keterangan: "Pemegang peran ini hanya bisa membuat, mengubah, dan mereset sandi akun yang perannya dicentang di sini.
  Kosong = tidak bisa mengelola akun siapa pun."
- Isi: daftar centang semua peran selain Admin (label dari registry peran).
- Hanya bisa diubah Admin; untuk pelaku lain tampil hanya-baca.

`AccountList.jsx` dan `RoleAccessPanel.jsx`: tombol ubah/reset/hapus mati bila `can_manage` salah, dengan petunjuk
"Peran Anda tidak diberi wewenang mengelola akun/peran ini."

`AccountFormDrawer.jsx`: pilihan peran hanya memuat peran yang boleh dikelola pelaku.

## Uji penerimaan

Persiapan bersama (fixture): peran kustom **HR** = tanpa peran acuan, tingkat `{"admin": "manage"}`; akun `hr`
berperan HR; akun `adm` = admin seed; akun `sls` = sales seed. `assignable_roles` kosong kecuali disebut.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `hr`: `PATCH /api/users/{hr}` `{"data": {"role": "admin"}}` | 403 "Peran Admin hanya bisa diberikan oleh Admin."; peran `hr` di database tetap HR |
| U2 | B | — | `hr`: `POST /api/users` dengan `role: "admin"` | 403; jumlah akun admin tetap 1 |
| U3 | B | — | `hr`: `POST /api/users/{adm}/reset-password` | 403; `password_hash` `adm` tidak berubah; sesi `adm` tetap ada |
| U4 | B | — | `hr`: `POST /api/users` dengan `role: "sales"` | 403 (daftar kelola kosong) |
| U5 | B | `adm`: `PATCH /api/access/roles/{HR}` `{"assignable_roles": ["sales", "warehouse"]}` → 200 | `hr`: `POST /api/users` `role: "sales"` | 200; akun terbuat berperan sales |
| U6 | B | seperti U5 | `hr`: `PATCH /api/users/{sls}` `{"data": {"role": "manager"}}` | 403 (manager di luar daftar); peran `sls` tetap sales |
| U7 | B | seperti U5 | `hr`: `POST /api/users/{sls}/reset-password` | 200 |
| U8 | B | — | `hr`: `PATCH /api/access/roles/{HR}` `{"assignable_roles": ["admin"]}` | 403 (hanya Admin mengubah daftar ini; dan `admin` bukan isi yang sah) |
| U9 | B | — | `hr`: `POST /api/access/roles` `{"label": "X", "base_role": "manager"}` | 403 "…akses yang Anda sendiri tidak punya…"; tidak ada peran `cr_x` |
| U10 | B | — | `hr`: `PATCH /api/access/roles/manager` `{"levels": {"accounting": "none"}}` | 403 "Peran Manajer memiliki akses lebih luas…"; izin Manajer tidak berubah |
| U11 | B | — | `hr`: `POST /api/access/roles` `{"label": "Y", "base_role": "", "levels": {"hr": "view"}}` (HR punya `hr.view`? lihat catatan) | Bila izin hasil ⊆ izin HR: 200; bila tidak: 403. Tes menghitung himpunannya dari jawaban `GET /api/access/roles/{HR}` dan menegaskan salah satu sesuai hitungan |
| U12 | B | — | `adm`: ulangi U1–U3, U9, U10 sebagai Admin | Semua 200 (Admin tidak terpengaruh) |
| U13 | B | — | `hr`: `PATCH /api/access/roles/{HR}` `{"levels": {"hr": "manage"}}` | 403 "Anda tidak bisa mengubah hak akses peran Anda sendiri…" (perilaku lama tetap) |
| U14 | B | `adm` menonaktifkan `sls` | `adm`: `DELETE /api/users/{adm}` | 400/409 penjaga "admin terakhir" tetap bekerja |
| U16 | B | — | `adm`: `POST /api/access/roles/admin/move-users` `{"to_role": "sales"}` | 400; jumlah akun Admin aktif tetap 1 |
| U17 | B | `adm` membuat 2 akun berperan `warehouse` dan memberi masing-masing satu sesi | `adm`: `POST /api/access/roles/warehouse/move-users` `{"to_role": "sales"}` | 200; kedua akun berperan sales; sesi keduanya terhapus |
| U15 | layar (uji jalan) | Login sebagai `hr` setelah U5 | Buka Akun & Akses | Tombol ubah pada akun Admin dan Manajer mati dengan petunjuk; pilihan peran di form hanya Sales dan Gudang |

Catatan U11: tingkat `"admin": "manage"` memberi `user`, `permission`, `settings`, `entity`, `scheduler`
(`backend/access_modules.py:200-202`), tidak memberi `hr`; jadi hasil yang diharapkan 403. Tes tetap menghitung dari
jawaban API supaya tidak bergantung pada isi katalog modul.

Setelah unit selesai, `t3_escalation.py` baris (d2)–(d4) dan `t3b_eskalasi_akun.py` baris (d3), (d5), (d7) harus
menampilkan 403, dan `t4_peran_bawaan.py` baris (b) harus menampilkan 400 dengan jumlah Admin tetap.

## Langkah kerja

1. `backend/tests_mem/test_PRT1_eskalasi.py`: U1–U14, U16, U17; semuanya merah kecuali U12–U14.
2. `access_guard.py` + pemasangan di `routers/users.py`.
3. Pemasangan di `routers/access_roles.py` + field `assignable_roles`.
4. `can_manage` di jawaban daftar; layar.
5. Gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (field `permission_settings.assignable_roles`); `CODEBASE_MAP.md` (`services/access_guard.py`).

## Di luar lingkup

- Memecah modul "Pengaturan, Pengguna & Hak Akses" menjadi beberapa modul → PR-T6.
- Mengganti gerbang nama peran dengan izin → PR-T2.
- Riwayat perubahan peran di layar → PR-T7.

## Asumsi dan risiko

- `ASUMSI:` tidak ada peran selain Admin yang saat ini memegang `user.*` atau `permission.update` di data nyata. Bila
  ada, setelah unit ini pemegangnya tidak bisa mengelola akun sampai Admin mengisi "Boleh mengelola akun dengan peran".
  Laporan unit memuat kueri pencarinya: peran pada `permission_settings.matrix` yang memiliki `user.create`/`user.update`/
  `permission.update` selain `admin`.
- `RISIKO:` Admin terkunci keluar — tidak mungkin, karena Admin dikecualikan dari semua pemeriksaan baru. Membatalkan:
  cabut pemanggilan `access_guard` di dua router; field baru tidak dibaca kode lain.
