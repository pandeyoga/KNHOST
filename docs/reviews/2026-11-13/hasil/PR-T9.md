# PR-T9 — Perubahan izin peran bawaan bertahan setelah server dinyalakan ulang; satu sumber izin bawaan

- Commit awal: `9668b07` (sesudah PR-T1)        - Commit akhir: lihat `git log --grep "\[PR-T9\]"`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PR-12, PR-14 (beserta butir layar PR-UX-06, PR-UX-25, PR-UX-26)

## Cek ulang "Keadaan sekarang"

| # | Hasil |
|---|---|
| 1 | Berlaku. `sync_permission_revocations` menjalankan REVOKE/RESCOPE/GRANT tanpa syarat pada setiap start |
| 2 | Berlaku. `permissions_config.py` Sales `ar_receipt: ["view"]`; RESCOPE/GRANT memberi `create` |
| 3 | Berlaku. Selisih bawaan vs efektif di basis data baru hanya `sales.ar_receipt.create` (dibuktikan U1: berkas "sebelum" sama dengan izin efektif sesudah unit) |
| 4 | Berlaku. Pada kode lama `permission_settings.updated_at` berubah setiap start (U6 merah: `…26.351457` → `…26.552664`) |
| 5–10 | Berlaku pada baris yang disebut |

Berkas "sebelum": `backend/tests_mem/data/matriks_bawaan_sebelum_PRT9.json`, dibuat dari `GET /api/access/roles` di
basis data tiruan baru pada kode **sebelum** unit ini (13 peran bawaan; Sales sudah bertanda "diubah" — butir 8).

Bukti merah: `backend/tests_mem/test_PRT9_izin_bawaan.py` di kode lama — **14 dari 15 gagal**; U1 lulus (memang
harus sama sebelum dan sesudah).

## Perubahan

| Berkas | Isi |
|---|---|
| `backend/permissions_config.py` | Sales `ar_receipt` = `view, create` (K-36) dengan komentar baru; satu-satunya perubahan nilai |
| `backend/bootstrap.py` | `PERMISSION_MIGRATIONS` (8 `revoke` + 7 `rescope`, id `<kind>:<role>:<resource>`; `revoke:finance:approval` tidak dipindahkan); `_LEGACY_GRANTS` (salinan GRANT lama, hanya untuk garis dasar); `ensure_permission_ledger` (dipanggil tepat sebelum `sync_permission_modules`); `sync_permission_revocations` hanya menjalankan butir yang belum tercatat dan tidak menulis pada start biasa; `sync_permission_modules` meneruskan aksi bawaan baru ke peran kustom turunan (`_follow_base_defaults`: ikut bila modulnya belum diubah, selain itu `pending_defaults`) |
| `backend/services/custom_role_service.py` | `_same_perms` (per sumber daya sebagai himpunan), `_modified_parts` (`izin`/`menu`/`lintas_pt`), `modified` dari tiga bagian; `pending_from_base`, `pending_from_base_count`; `reset_builtin` ikut membuang `hidden_views.<rid>`; `follow_base(rid, resources, dry_run)` |
| `backend/routers/access_roles.py` | `POST /api/access/roles/{rid}/follow-base` (izin `permission.update`; peran sendiri 403; `assert_can_shape_role` PR-T1 dengan izin hasil; jejak audit `role_followed_base`) |
| `frontend/.../RoleDangerDialog.jsx` | Teks reset baru; jenis `follow` ("Ikuti izin baru peran dasar?", **Ya, ikuti** / **Batal**) |
| `frontend/.../RoleEditorDrawer.jsx` | Pesan berhasil reset baru; catatan "Peran dasar {label} mendapat {n} izin baru…" + tombol **Ikuti peran dasar** (hanya pemegang `permission.update`); konfirmasi memuat "{label sumber daya}: {label aksi}, …" |
| `frontend/.../RoleAccessPanel.jsx`, `entityApi.js` | `canFollow`; `followBaseAccessRole(id, resources)` |
| `ENTITY_REGISTRY.md`, `memory/PRD.md` | `permission_settings.migrations_applied` (+ `defaults_applied` dijelaskan), `custom_roles.pending_defaults`; satu kalimat PRD |

## Uji penerimaan

| ID | Lapis | Hasil |
|---|---|---|
| U1 | B | Lulus — 13 peran bawaan, izin efektif per sumber daya sama dengan berkas "sebelum" |
| U2 | B | Lulus — `ar_receipt` `view, create`; `modified` salah; `modified_parts` `[]` |
| U3 | B | Lulus — sesudah start ulang `ar_receipt` tetap tidak ada (kode lama: `["create"]`) |
| U4 | B | Lulus — `order` Gudang tetap memuat `confirm` (kode lama: `["view","deliver"]`) |
| U5 | B | Lulus — Finance tetap tanpa `approval` |
| U6 | B | Lulus — dua kali start: `updated_at` tetap; `migrations_applied` 15 id unik |
| U7 | B | Lulus — butir uji `revoke:sales:vehicle_log`: start 1 dicabut; Admin memberi `["view"]`; start 2 tetap `["view"]`; id tercatat sekali |
| U8 | B | Lulus — Sales dan "Sales Senior" sama-sama memuat `vehicle_log.update`; tertunda 0 |
| U9 | B | Lulus — "Sales Sempit" tanpa `update`; `pending_from_base` = `{"vehicle_log": ["update"]}` |
| U10 | B | Lulus — `follow-base` 200, `update` masuk, tertunda 0; kedua kali 400 "Tidak ada izin baru…" |
| U11 | B | Lulus — Manajer memuat `uom.update`; "Manajer Kosong" tanpa `uom`; tertunda tercatat |
| U12 | B | Lulus — sebelum reset `modified` benar, `modified_parts` `["menu"]`; sesudah `hidden_views` `[]`, `modified` salah |
| U13 | B | Lulus — reset Sales lalu start: `ar_receipt` `view, create`; `modified` salah |
| U14 | B | Lulus — peran "Tanpa Acuan" (`permission.view` saja) 403; Sopir 403 |
| U15 | B | Lulus — tiruan instalasi lama: `ar_receipt` Sales tetap tidak ada; `defaults_applied.sales.ar_receipt` memuat `create`; `migrations_applied` 15 id |
| U16 | layar (uji jalan) | **Lulus** di lingkungan A (Admin): Finance dengan menu "Kasus Keuangan" disembunyikan → tombol **Kembalikan ke bawaan** tampil (`modified` karena menu); dialog memuat "Izin, menu yang disembunyikan, dan akses lintas PT peran ini dikembalikan ke bawaan sistem…"; sesudah **Ya, kembalikan**, pratinjau menu Finance memuat "Kasus Keuangan" lagi. Tangkapan: `bukti/PR-T9/U16_dialog_kembalikan.png`, `U16_sesudah.png` |

`backend/tests_mem` seluruhnya: 97 lulus, 9 diharapkan gagal (milik unit lain).

**Garis dasar di basis data nyata (lingkungan A, MongoDB 7, data acuan sesudah gate PR-T1, dibuat kode lama):**
backend dinyalakan dengan kode unit ini → `matrix` identik sebelum/sesudah, `updated_at` tidak berubah,
`migrations_applied` dari tidak ada menjadi 15 id. Jadi garis dasar hanya mencatat, tidak mengubah izin siapa pun.

Skrip audit `docs/audit/konfigurasi-peran-2026-11-13/bukti/t4_peran_bawaan.py` baris (a) sekarang: "admin mencabut modul
Uang Masuk dari Sales → 200 | ar_receipt kini: None · setelah proses awal dijalankan ulang (= restart): ar_receipt =
None" (sebelum unit: `['create']`).

## Gate

- `gate.sh --quick`: 16 merah = garis dasar 16 (lebih merah 0).
- `gate.sh --ci`: 43 merah = garis dasar 43 (lebih merah 0, menjadi hijau 0).

## Menyimpang dari blueprint

- **Urutan uji** di berkas berbeda dari urutan nomor (satu basis data per modul): U8/U9 dijalankan sebelum U7, karena
  sesudah U7 izin `vehicle_log` Sales tinggal `["view"]` sehingga "Sales Sempit" (`logistics: view`) menjadi sama
  dengan Sales dan akan ikut — bertentangan dengan maksud U9. Dengan urutan ini tiap uji memakai keadaan yang dimaksud
  spesifikasinya.
- **`follow-base`** menolak peran pelaku sendiri lebih dulu (seperti `PATCH`), lalu penjaga PR-T1 dengan izin hasil.
- **Pratinjau `follow_base(dry_run=True)`** dipakai router untuk menghitung izin hasil sebelum menyimpan.

## Asumsi (dari spesifikasi)

Setiap basis data yang ada sudah pernah dinyalakan dengan kode sebelum unit ini (garis dasar hanya mencatat). Tafsir
"ikut bila modul belum pernah diubah" (modul = katalog `access_modules`, satu tingkat `base_role`). Peran dasar peran
kustom selalu peran bawaan.

## Yang perlu direview

- Butir migrasi baru di masa depan: tambahkan di akhir `PERMISSION_MIGRATIONS` dengan id baru (komentar di kode).
- Peran kustom yang sudah tertinggal dari peran dasarnya **sebelum** unit ini tidak dicatat sebagai tertunda (di luar
  lingkup → PR-T6).

Status: implemented_pending_review.
