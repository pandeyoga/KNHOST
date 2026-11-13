# PR-T1 — Tutup jalan menaikkan hak sendiri lewat kelola akun dan kelola peran

- Commit awal: sesudah `[PK-06]`        - Commit akhir: lihat `git log --grep "\[PR-T1\]"`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PR-02, PR-13

## Cek ulang "Keadaan sekarang"

| # | Hasil |
|---|---|
| `PATCH /api/users/{id sendiri}` → admin | Berlaku. `update_user` hanya memeriksa peran dikenal |
| `POST /api/users` `role: admin` | Berlaku |
| Reset sandi Admin | Berlaku |
| Peran baru beracuan Manajer | Berlaku. `create_custom` menyalin izin acuan tanpa pembanding |
| `PATCH /api/access/roles/manager` | Berlaku |
| `PATCH` peran sendiri | Sudah 403 — dipertahankan |
| Pindah massal akun Admin | Berlaku. `move_users` tanpa penjaga admin terakhir |

Bukti merah: berkas uji dijalankan terhadap kode lama — **16 dari 17 gagal** dalam satu putaran. U13 dan U14 ikut gagal
karena efek berantai (U1 di kode lama berhasil menjadikan akun HR Admin dan mencabut sesinya); dijalankan **sendiri-sendiri**
di kode lama, U12, U13, U14 lulus — sesuai spesifikasi ("merah kecuali U12–U14").

## Perubahan

| Berkas | Isi |
|---|---|
| `backend/services/access_guard.py` (baru) | `manageable_roles`, `assert_can_manage_account`, `excess`, `assert_can_shape_role`, `can_manage_role` (untuk layar). Admin dikecualikan dari semua pemeriksaan |
| `backend/routers/users.py` | Penjaga di buat, ubah, nonaktifkan, aktifkan, reset sandi, cabut sesi; `can_manage` per baris di `GET /api/users`; `GET /api/users/manageable-roles` (peran yang boleh diberikan pelaku — untuk form akun) |
| `backend/routers/access_roles.py` | Buat/ubah/kembalikan bawaan/hapus peran → `assert_can_shape_role` dengan izin **hasil** dihitung sebelum menyimpan; `assignable_roles` di `RolePatch` (hanya Admin, selain itu 403); pindah massal → `assert_can_manage_account` asal & tujuan; `can_manage` per baris + `can_edit_assignable` di `GET /api/access/roles` |
| `backend/services/custom_role_service.py` | `current_permissions`, `projected_permissions` (urutan sama dengan simpan: acuan/izin sekarang + tingkat, izin rinci menimpa); simpan `permission_settings.assignable_roles.{rid}` (id dikenal, bukan `admin` → selain itu 400); `_role_view` + `assignable_roles`, `assignable_roles_labels`; hapus peran ikut membuang kuncinya; `move_users`: asal `admin` → 400, akun pelaku tidak ikut, sesi akun yang dipindah dicabut |
| `frontend/.../RoleEditorDrawer.jsx` | Bagian **Boleh mengelola akun dengan peran** (tampil bila peran memegang `user.create`/`user.update`; hanya Admin yang bisa mencentang); peran ber-`can_manage: false` tampil hanya-baca + petunjuk; tombol hapus/kembalikan bawaan mati |
| `frontend/.../AccountList.jsx` | Ubah/reset/cabut sesi/nonaktifkan/aktifkan mati bila `can_manage` salah, petunjuk "Peran Anda tidak diberi wewenang mengelola akun/peran ini." |
| `frontend/.../RoleAccessPanel.jsx` | Petunjuk yang sama di kartu peran; meneruskan `can_edit_assignable` ke editor |
| `frontend/.../AccountFormDrawer.jsx` | Pilihan peran hanya yang boleh dikelola pelaku (peran akun yang sedang diubah tetap tampil) |
| `frontend/.../entityApi.js` | `accessRolesFull`, `manageableRoles` |
| `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md` | Field `permission_settings.assignable_roles`; `services/access_guard.py` |

## Uji penerimaan

`backend/tests_mem/test_PRT1_eskalasi.py`, peran HR = tanpa acuan, tingkat `{"admin": "manage"}`.

| ID | Lapis | Hasil |
|---|---|---|
| U1 | B | Lulus — 403 "Peran Admin hanya bisa diberikan oleh Admin."; peran HR tetap |
| U2 | B | Lulus — 403; jumlah akun admin tetap |
| U3 | B | Lulus — 403; `password_hash` Admin tetap; sesi Admin tetap |
| U4 | B | Lulus — 403 "…belum diberi wewenang mengelola akun berperan Sales…" |
| U5 | B | Lulus — Admin mengisi daftar `["sales","warehouse"]` (200, label ikut); HR membuat akun sales 200 |
| U5b | B | Tambahan — `can_manage`: baris Admin `false`, baris sales `true`; peran Manajer/Admin/peran sendiri `false` bagi HR, Manajer `true` bagi Admin |
| U6 | B | Lulus — 403; `sls` tetap sales |
| U7 | B | Lulus — 200 |
| U8 | B | Lulus — HR 403 (peran sendiri); Admin memasukkan `admin` → 400; daftar tetap |
| U9 | B | Lulus — 403 "…akses yang Anda sendiri tidak punya…"; tidak ada `cr_x` |
| U10 | B | Lulus — 403 "Peran Manajer memiliki akses lebih luas…"; matriks Manajer tetap |
| U11 | B | Lulus — izin hasil `{"hr": "view"}` tidak ⊆ izin HR (dihitung dari jawaban API) → 403; arah sebaliknya (`{"admin": "view"}`) 200 |
| U12 | B | Lulus — sebagai Admin: ubah peran akun ke Admin, buat Admin, reset sandi Admin (akun kedua), peran beracuan Manajer, ubah Manajer → semua 200; keadaan dikembalikan |
| U13 | B | Lulus — 403 "Anda tidak bisa mengubah hak akses peran Anda sendiri…" |
| U14 | B | Lulus — hapus Admin terakhir 409; tetap `active` |
| U16 | B | Lulus — 400 "Akun Admin tidak bisa dipindahkan massal…"; Admin aktif tetap |
| U17 | B | Lulus — 2 akun gudang → sales; sesi keduanya 0 |
| U15 | layar (uji jalan) | **Lulus** di lingkungan A, login akun berperan "Admin HR Uji" (daftar kelola Sales + Gudang): tombol Ubah/reset mati di baris Admin, Manajer, Finance, dll. dengan petunjuk; hidup di Sales dan Gudang; pilihan peran di form = "Sales (lapangan)" dan "Gudang (WMS)". Tangkapan: `bukti/PR-T1/U15_daftar_akun.png`, `U15_form_peran.png` |

`backend/tests_mem` seluruhnya: 82 lulus, 9 diharapkan gagal (milik unit lain).

Skrip audit dijalankan ulang di kode baru (`docs/audit/konfigurasi-peran-2026-11-13/bukti/`):

| Skrip · baris | Sekarang |
|---|---|
| `t3_escalation.py` (d2) | 403 "Peran Manajer memiliki akses lebih luas…" |
| `t3_escalation.py` (d3) | 422 — skrip mengirim `{"role": "admin"}` tanpa pembungkus `data` (galat bentuk di skrip, sama seperti saat audit); bentuk yang benar diuji `t3b` (d3) |
| `t3_escalation.py` (d4) | 403 "Peran Admin hanya bisa diberikan oleh Admin." |
| `t3b_eskalasi_akun.py` (d3), (d5), (d7) | 403, 403, 403 |
| `t4_peran_bawaan.py` (b) | 400; Admin aktif 1 → 1 |

## Gate

- `gate.sh --quick`: 16 merah = garis dasar 16 (`bandingkan_gate.py`: lebih merah 0).
- `gate.sh --ci`: 43 merah = garis dasar 43 (lebih merah 0, menjadi hijau 0).

## Menyimpang dari blueprint

- **Endpoint tambahan** `GET /api/users/manageable-roles` (izin `user.view`): form akun perlu daftar peran yang boleh
  diberikan, dan pemegang modul akun belum tentu boleh membaca `GET /api/access/roles` (`permission.view`).
- **`can_edit_assignable`** di jawaban `GET /api/access/roles`: layar tidak memeriksa nama peran sendiri (02_STANDAR §3);
  server yang memutuskan siapa boleh mencentang daftar.
- **U5b** (tambahan) menguji `can_manage` di kedua daftar.
- **Tombol cabut sesi dan aktifkan** di daftar akun ikut mati (spesifikasi menyebut ubah/reset/hapus) karena server
  juga menolaknya.

## Asumsi (dari spesifikasi)

`ASUMSI:` tidak ada peran selain Admin yang memegang `user.create`/`user.update`/`permission.update` di data nyata.
Kueri pencari (dijalankan di data acuan lingkungan A: hasil `[]`):

```js
const m = (db.permission_settings.findOne({id: "default"}) || {}).matrix || {};
Object.entries(m).filter(([r, p]) => r !== "admin" && (((p.user || []).some(a => ["create", "update"].includes(a)))
  || (p.permission || []).includes("update"))).map(([r]) => r)
```

Bila di produksi ada hasilnya, pemegang peran itu tidak bisa mengelola akun sampai Admin mengisi "Boleh mengelola akun
dengan peran".

## Yang perlu direview

- Pembanding "lebih luas" memakai pasangan (sumber daya, aksi) persis; izin lingkup (mis. `scope_all`) ikut dihitung
  sebagai aksi biasa.
- Peran yang `cross_entity`-nya sudah benar tidak dicek ulang saat diubah tanpa menyentuh `cross_entity` (hanya nilai
  baru `true` yang diperiksa — sesuai spesifikasi).

Status: implemented_pending_review.
