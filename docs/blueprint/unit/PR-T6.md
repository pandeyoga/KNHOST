# PR-T6 — Benahi layar Peran & Hak Akses dan Akun & Akses supaya menjawab "peran ini akhirnya bisa apa"

| | |
|---|---|
| Gelombang | Jalur peran (sejajar dengan gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PR-T4, PR-T5 |
| Menutup temuan | PR-09 dan temuan layar PR-UX (PR-UX-01, 02, 05, 09, 10, 17, 20, 21, 27, 29, 31 … 36; ikut karena murah: PR-UX-37, 40, 44) |
| Keputusan | K-47, K-50, K-51 (tampilan batas persetujuan) |
| Standar | §3.1 (Z6), §3.3, §4 (L1, L2, L5, L6, L7), §6 |
| Lingkungan uji | keduanya (B untuk server; A untuk uji jalan layar) |

## Tujuan

Admin bisa membaca, sebelum menyimpan, apa yang bisa dan tidak bisa dilakukan sebuah peran: halaman awalnya, data
siapa yang terlihat, batas persetujuannya, dan aksi per modul dalam kalimat. "Peran dasar" dan "salin hak akses"
menjadi dua hal yang terpisah dan terlihat. Pratinjau menu benar untuk peran bawaan. Formulir akun tidak lagi salah
soal lintas PT. Penolakan akses tampil sebagai kalimat yang menyebut akses apa yang harus diminta.

## Keadaan sekarang

| # | Fakta | Jangkar | Bukti |
|---|---|---|---|
| 1 | Satu daftar pilih "Salin dari peran" menyalin izin sekaligus menetapkan peran dasar; saat menyunting peran dasar tidak tampil dan tidak bisa diganti | `frontend/src/features/settings/entities/RoleEditorDrawer.jsx:89` (`copyFrom`); `backend/routers/access_roles.py:24` (`RolePatch`) | [dibaca] |
| 2 | Pratinjau menu memakai peran dasar sebagai pewaris; untuk peran bawaan nilainya kosong, sehingga dihitung seperti peran kustom tanpa dasar. Menu peran bawaan sendiri hanya bisa berkurang, tidak bertambah | `frontend/src/features/settings/entities/RoleMenuPreview.jsx:28` (`RoleMenuPreview`); `frontend/src/config/roles.js:385` (`roleCanSee`) | [dibaca] |
| 3 | Pratinjau server hanya mengembalikan notifikasi giliran, daftar layar, dan tingkat | `backend/services/custom_role_service.py:331` (`preview_role`) | [dibaca] |
| 4 | Formulir akun menentukan "lintas PT" dari daftar tertulis (admin, manager), bukan dari nilai peran di server | `frontend/src/features/settings/entities/AccountFormDrawer.jsx:49` (`CROSS_ROLES`); `frontend/src/config/roles.js:147` (`CROSS_ENTITY_ROLES`); `backend/services/user_admin_service.py:145` (`CROSS_ENTITY_ROLES`) | [dibaca] |
| 5 | "Bawaan" lintas PT peran kustom dihitung dari nilai asli peran dasar, nilai efektifnya dari nilai peran dasar yang sudah diubah; nilai yang sama dengan "bawaan" disimpan sebagai "ikut bawaan" | `backend/role_registry.py:283` (`cross_entity_default`); `backend/role_registry.py:292` (`apply_cross_entity`); `backend/services/custom_role_service.py:264` (`cross_entity`) | [dibaca] |
| 6 | Tiga tempat masih menganggap `admin`/`manager` selalu lintas PT | `backend/services/customer_service.py:407` (`can_access_customer`); `backend/routers/bank.py:31` (`role_in`); `backend/routers/cash.py:48` (`role_in`) | [dibaca] |
| 7 | Pesan penolakan memuat kode izin: "Permission ditolak: goods_receipt.view" | `backend/dependencies.py:112` (`require_permission`); `backend/dependencies.py:119` (`require_any_permission`) | [dijalankan] `docs/audit/konfigurasi-peran-2026-11-13/bukti/t2_roles.py` (kolom pesan), temuan PR-09 |
| 8 | Layar peran dan akun memakai pengurai galat sendiri yang tidak menerjemahkan pesan itu; penerjemah pusat ada tetapi tidak dipakai di sini | `frontend/src/features/settings/entities/entityApi.js:16` (`errText`); `frontend/src/utils/apiError.js:76` (`permissionDeniedText`) | [dibaca] |
| 9 | Tab "Peran & Hak Akses" dan "Cek Peran" tampil tanpa memeriksa izin | `frontend/src/features/settings/entities/EntitiesAccessView.jsx:28` (`TABS`) | [dibaca] |
| 10 | Kartu peran selalu bisa diklik dan editor tidak punya mode baca; widget pindah akun tampil untuk siapa pun | `frontend/src/features/settings/entities/RoleAccessPanel.jsx:16` (`onOpen`); `frontend/src/features/settings/entities/RoleEditorDrawer.jsx:251` (`canMove`) | [dibaca] |
| 11 | "Menu lain" di editor menampilkan id grup bersama (mis. Pengaturan) sebagai centang biasa; satu centang menyembunyikan seluruh grup | `frontend/src/features/settings/entities/RoleNavTree.jsx:20` (`navTree`) | [dibaca] |
| 12 | Halaman `marketing` tidak punya label; beberapa aksi berlabel jargon ("Pegging", "Dispatch", "Generate") | `backend/access_modules.py:275` (`RESOURCE_LABEL`); `backend/access_modules.py:305` (`ACTION_LABEL`) | [dibaca] |
| 13 | Mengganti atau melepas tautan karyawan hanya mengubah sisi akun; `user_id` karyawan lama tidak dibersihkan | `backend/services/user_admin_service.py:344` (`employee_id`) | [dibaca] |
| 14 | Formulir akun memilih Sales sebagai peran bawaan; skema API memberi sandi bawaan bila kosong | `frontend/src/features/settings/entities/AccountFormDrawer.jsx:29` (`role`); `backend/schemas.py:170` (`password`); `backend/services/user_admin_service.py:249` (`hash_password`) | [dibaca] |
| 15 | Pindah akun massal menulis `role` langsung tanpa menghitung ulang penugasan PT; layar tidak mengarahkan ulang saat peran berubah di tengah sesi | `backend/services/custom_role_service.py:348` (`move_users`); `frontend/src/hooks/useSessionSync.js:104` (`lastUserIdRef`) | [dibaca] |
| 16 | Riwayat perubahan peran hanya ada di jejak audit umum; tiga dari lima aksinya belum berlabel | `backend/routers/access_roles.py:95` (`role_access_updated`); `frontend/src/config/auditLabels.js:112` (`role_access_updated`) | [dibaca] |
| 17 | "Bisa dihapus" dihitung dari akun aktif, sedangkan penghapusan menolak bila ada akun apa pun | `backend/services/custom_role_service.py:128` (`deletable`); `backend/services/custom_role_service.py:313` (`count_documents`) | [dibaca] |

## Perubahan

### Data

- `audit_logs`: baris `role_access_updated`, `role_access_reset`, `custom_role_created`, `custom_role_deleted` kini
  ditulis dengan `before` dan `after` berisi `{permissions, hidden_views, cross_entity, traits, base_role}` (parameter
  `before` yang sudah ada di `backend/dependencies.py:166`, `audit`). Tanpa koleksi atau field baru.
- Tanpa migrasi.

### Server

**1. Peran dasar terpisah dari salin hak akses**

- `RolePatch` mendapat `base_role: Optional[str]`. Hanya untuk peran kustom; nilai `""` = tanpa peran dasar; harus
  peran bawaan selain Admin. Mengganti peran dasar **tidak** mengubah izin; yang ikut berubah hanya sifat yang belum
  diisi sendiri (PR-T4) dan menu warisan. Galat: 400 "Peran dasar hanya bisa diatur pada peran kustom." · 400 "Peran
  Admin tidak bisa dijadikan peran dasar." · 400 "Peran dasar tidak dikenal."
- `RoleCreate` dan `RolePatch` menerima `hidden_views` pada pembuatan (satu panggilan, PR-UX-37).
- Pesan lama "Peran acuan (template) tidak dikenal." dan "Peran Admin tidak bisa dijadikan template." diganti dua
  pesan di atas. Semua teks server memakai "peran dasar"; alasan cabut sesi "role berubah" menjadi "peran berubah".

**2. Ringkasan peran**

| Metode + path | Izin | Isi permintaan | Jawaban |
|---|---|---|---|
| `GET /api/access/roles/{rid}/summary` (baru) | `permission.view`, atau `user.view` (untuk formulir akun) | — | objek `summary` di bawah |
| `POST /api/access/roles/preview` (sudah ada) | `permission.view` | ditambah `base_role`, `traits`, `cross_entity` | jawaban lama + `summary` + `nav_added` (lihat 3) |

```text
summary = {
  "home":        {"view": str, "label": str},
  "data_scope":  {"value": str, "label": str},
  "kategori":    {"value": str, "label": str},
  "cross_entity": bool,
  "approvals":   [{"label": str, "level": str, "max_amount": number|null}] | {"follows_rank_of": str},
  "modules":     [{"id": str, "label": str, "level": str, "held": int, "total": int,
                   "pages": [{"label": str, "can": [str], "cannot": [str]}]}],
  "risky":       [str],
  "follows_base": [str]
}
```

- `approvals`: bila koleksi `approval_policies` (KP-T4) ada, satu baris per jenis dokumen dan jenjang yang
  mencantumkan peran ini pada lapisan grup, dengan batas atas rentangnya (`null` = tanpa batas). Bila belum ada:
  `{"follows_rank_of": <label peran yang peringkatnya dipakai>}`.
- `pages[].can` / `cannot`: label aksi (kamus server) yang dipegang / tidak dipegang pada halaman itu.
- `risky`: kalimat dari `SENSITIVE_ACTIONS` (PR-T5) untuk aksi yang dipegang.
- `follows_base`: kalimat untuk tiap sifat yang masih mengikuti peran dasar, mis. "Halaman awal mengikuti Sales".

**3. Menu peran bawaan boleh bertambah**

`role_registry.public_list()` mengirim untuk peran bawaan `nav: {"add": […], "remove": []}` dengan `add` = menu yang
dibuka izin sekarang dikurangi menu yang dibuka izin bawaan peran itu
(`nav_allowed_for_perms(matriks sekarang) − nav_allowed_for_perms(DEFAULT_PERMISSIONS[peran])`). Pada pemasangan
`add` kosong untuk semua peran, jadi tidak ada menu yang berubah. Jawaban pratinjau memuat `nav_added` yang dihitung
dengan cara yang sama dari izin yang sedang disunting.

**4. Lintas PT**

- `cross_entity_default(rid)` untuk peran kustom = nilai **efektif** peran dasarnya. `update_role` selalu menyimpan
  nilai eksplisit untuk peran kustom (tidak pernah "ikut bawaan").
- Saat `cross_entity` sebuah peran berubah dari ya ke tidak, jawaban `PATCH` memuat
  `accounts_to_review: [{id, name, allowed_entities: [label PT]}]` (akun peran itu yang penugasannya lebih dari satu
  PT). Tidak ada penugasan yang diubah otomatis.
- Tiga tempat di butir 6 memakai himpunan `CROSS_ENTITY_ROLES` yang hidup (`backend/role_registry.py:280`), bukan
  daftar `("admin", "manager")`.

**5. Pesan penolakan (Z6)**

Fungsi baru `denied_message(pairs: List[Tuple[str, str]]) -> str` di `backend/dependencies.py`, dipakai
`require_permission`, `require_any_permission`, dan sepuluh tempat lain yang menulis "Permission ditolak: …" sendiri
(mis. `backend/routers/special_orders.py:792`).

| Keadaan | Teks |
|---|---|
| Satu izin | "Anda belum punya akses untuk {frasa aksi} {label halaman}. Minta Admin menambahkan akses '{label modul}'." |
| Salah satu dari beberapa | "Anda belum punya akses ke layar ini. Minta Admin menambahkan salah satu akses: '{label modul}', '{label modul}'." |

Frasa aksi: `view` "melihat" · `create` "membuat" · `update` "mengubah" · `delete` "menghapus" · `approve`
"menyetujui" · `reject` "menolak" · `post` "mencatat ke buku besar" · `pay` "membayar" · `void` "membatalkan" ·
`export` "mengekspor" · `configure` "mengatur" · `release` "melepas"; aksi lain: "melakukan “{label aksi}” pada".
Label dari kamus server (PR-T5). Jawaban 403 menambah header `X-Permission-Denied: <sumber daya>.<aksi>[,…]` untuk
alat uji; isi `detail` tetap teks.

**6. Akun**

- `UserCreate.password` tanpa nilai bawaan; `create_user` menolak sandi kurang dari 8 karakter: 400 "Kata sandi
  minimal 8 karakter." Tidak ada lagi sandi cadangan di layanan.
- `update_user`: bila `employee_id` berubah atau dikosongkan, `hr_employees.user_id` semua karyawan lain yang menunjuk
  akun itu dikosongkan dalam langkah yang sama.
- `move_users`: tiap akun dipindah lewat `user_admin_service.update_user(id, {"role": tujuan})` (penugasan PT dihitung
  ulang, sesi dicabut); `move_role_users` di router menulis satu baris audit `user_updated` per akun di samping baris
  `role_users_moved`; penjaga PR-T1 tetap.
- `_role_view`: `deletable` = peran kustom tanpa akun apa pun; field baru `users_inactive`.

**7. Riwayat peran**

| Metode + path | Izin | Jawaban |
|---|---|---|
| `GET /api/access/roles/{rid}/history?limit=50` (baru) | `permission.view` | `{"items": [{"at", "actor", "action", "action_label", "added": [str], "removed": [str], "other": [str], "users": int}]}` — `added`/`removed` = "{label halaman}: {label aksi}" dari selisih `before`/`after`; `other` = kalimat perubahan sifat, menu, lintas PT, peran dasar |

**8. Label (kamus server `backend/access_modules.py`)**

| Kunci | Sekarang | Menjadi |
|---|---|---|
| halaman `marketing` | (tidak ada) | Marketing & Sosial Media |
| halaman `goods_receipt` | Kedatangan Barang (GRN) | Kedatangan Barang |
| halaman `internal_request` | Permintaan Internal (PIN) | Permintaan Internal Antar PT |
| halaman `sample_order` | Pesanan Sample (SOS) | Pesanan Sample |
| halaman `rfq` | RFQ / Penawaran | Permintaan Penawaran Harga |
| halaman `landed_cost` | Landed Cost | Biaya Masuk Barang |
| halaman `wms` | Operasi Gudang (WMS) | Operasi Gudang |
| aksi `close` · `count` · `review` · `set` | (tidak ada) | Tutup penerimaan · Hitung fisik · Periksa hasil hitung · Tetapkan harga internal |
| aksi `pegging` | Pegging | Kaitkan stok ke pesanan |
| aksi `dispatch` | Dispatch | Berangkatkan kiriman |
| aksi `generate` | Generate | Buat label |
| aksi `void` | Void | Batalkan (void) |
| aksi `override` | Override / edit SO | Ubah pesanan yang sudah terkunci |
| aksi `hold` · `random_check` · `scan` | Hold / tahan · Random check · Scan | Tahan · Cek acak · Pindai |
| aksi `manage_bom` · `manage_payroll` | Kelola BOM · Kelola payroll | Kelola resep produksi · Kelola gaji |
| aksi `release` | Rilis | Lepas / rilis |
| modul `warehouse_ops` | Operasi Gudang (WMS) | Operasi Gudang |
| modul `rnd` | Riset & Sample (R&D) | Pengembangan Produk & Sample |
| modul `petty_cash` | Kas Kecil (PD / LPJ) | Kas Kecil (pengajuan dana & pertanggungjawaban) |

Label jejak audit baru di `frontend/src/config/auditLabels.js`: `custom_role_created` "Peran dibuat" ·
`custom_role_deleted` "Peran dihapus" · `role_users_moved` "Akun dipindahkan ke peran lain".

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan baru.

### Layar

Tempat: Pengaturan › Perusahaan & Akun › Badan Usaha & Akses › tab **Peran & Hak Akses** dan **Akun & Akses**.

**Editor peran** (`RoleEditorDrawer.jsx` dan komponennya)

- Dua kontrol menggantikan "Salin dari peran":
  - **Peran dasar** (hanya peran kustom; pilihan "Tanpa peran dasar" + peran bawaan selain Admin). Keterangan:
    "Menentukan nilai awal halaman awal, data yang terlihat, kategori kerja, dan menu warisan. Tidak menyalin hak
    akses." Tampil juga saat menyunting. Mengganti nilainya memunculkan konfirmasi "Ganti peran dasar ke {label}?"
    berisi daftar `follows_base` sebelum dan sesudah.
  - **Salin hak akses dari…** Keterangan: "Hanya menyalin centang; boleh diubah setelahnya."
- Judul saat menduplikat: "Duplikat Peran · {label} (peran dasar: {label})".
- Tombol "Menu, tab & aktivitas" menjadi **Atur rinci**.
- Panel kanan **Ringkasan peran** (menggantikan kotak "Ringkasan"), diisi dari `summary` pratinjau, diperbarui
  ±500 ms setelah perubahan terakhir:
  - "Halaman awal: {label}" · "Data yang terlihat: {label}" · "Kategori kerja: {label}" · "PT: semua PT aktif" atau
    "PT: hanya yang ditugaskan per akun".
  - "Batas persetujuan:" daftar "{jenis dokumen} — {jenjang}, sampai Rp {angka berpemisah ribuan}" atau "tanpa
    batas"; bila `follows_rank_of`: "Mengikuti tingkat {label}; diatur di Aturan Persetujuan."
  - Per modul yang tidak "Tidak ada": "**{modul}** — {halaman}: bisa {aksi, aksi}; tidak bisa {aksi, aksi}."
  - "Perhatian — peran ini bisa: {kalimat}; {kalimat}." bila `risky` tidak kosong.
  - "Mengikuti peran dasar: {kalimat}; {kalimat}." bila `follows_base` tidak kosong.
  - Memuat: kerangka abu-abu. Galat: "Ringkasan tidak bisa dimuat." dengan tombol **Coba lagi**. Kosong: "Belum ada
    modul yang dinyalakan."
- Pratinjau menu: untuk peran bawaan pewarisnya id peran itu sendiri ditambah `nav_added`; menu tambahan diberi tanda
  "baru". Catatan di bawahnya menjadi "Daftar ini hanya menu. Lihat Ringkasan peran untuk apa yang bisa dilakukan."
- "Menu & tab yang tampil": id yang merupakan grup sidebar atau hub tidak ditampilkan sebagai centang; hanya menu
  dan tab milik modul itu. Catatan baru: "Menyembunyikan hanya merapikan menu; izin tetap berlaku."
- Kotak lintas PT: "Bawaan: {aktif|mati}" memakai `cross_entity_default` baru. Setelah menyimpan dengan
  `accounts_to_review` tidak kosong: dialog "Tinjau penugasan PT" berisi daftar akun dan tombol **Buka Akun & Akses**.
- Mode baca: bila pelaku tidak memegang `permission.update`, judul "Lihat Hak Akses · {label}", semua isian mati,
  tanpa tombol simpan, hapus, kembalikan, dan pindah akun.
- Tab baru **Riwayat** di editor (peran yang sudah ada): kolom Waktu (WIB) · Oleh · Perubahan · Akun terdampak. Kosong:
  "Belum ada perubahan tercatat."
- Tombol hapus: petunjuk "Masih dipakai {n} akun ({m} nonaktif) — pindahkan akunnya dulu."

**Akun & Akses** (`AccountFormDrawer.jsx`, `AccountList.jsx`, `EntitiesAccessView.jsx`)

- Peran: tanpa pilihan awal pada akun baru ("Pilih peran…"; wajib). Pilihan menampilkan label peran dan, untuk peran
  kustom, "· peran dasar {label}". Di bawahnya ringkasan dari `summary`: halaman awal, data yang terlihat, PT, dan
  jumlah modul per tingkat; tautan **Lihat hak peran ini** (membuka editor mode baca).
- Kalimat lintas PT mengikuti nilai peran dari `GET /api/roles`: "Peran ini membuka semua PT aktif." atau "Peran ini
  hanya membuka PT yang dicentang di bawah." `allowed_entity_ids` dikirim setiap kali peran tidak lintas PT.
- Melepas atau mengganti tautan karyawan meminta konfirmasi: "Lepas tautan ke {nama karyawan}?"
- Tab "Peran & Hak Akses" dan "Cek Peran" hanya tampil bagi pemegang `permission.view`; "Akun & Akses" bagi pemegang
  `user.view`.
- `entityApi.js` `errText` meneruskan ke `apiErrorText`, sehingga semua galat di kedua tab lewat penerjemah pusat.
- `useSessionSync.js`: bila `user.role` berubah di tengah sesi, layar diarahkan ke halaman awal peran baru dengan
  pemberitahuan "Peran Anda berubah menjadi {label}."

## Uji penerimaan

Persiapan bersama: peran uji baku `02` §6; `adm` = admin seed.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | "Tanpa Acuan" tanpa izin apa pun | `GET /api/goods-receipts` | 403; `detail` = "Anda belum punya akses untuk melihat Kedatangan Barang. Minta Admin menambahkan akses 'Operasi Gudang'."; tidak memuat titik-kode `goods_receipt.view`; header `X-Permission-Denied: goods_receipt.view` |
| U2 | B | — | Sapu semua rute GET oleh Sopir | Tidak ada `detail` 403 yang cocok pola `[a-z_]+\.[a-z_]+` atau memuat "Permission", "Role", `cr_` |
| U3 | B | "Tanpa Acuan" + `permission.view` | `GET /api/access/roles/sales/summary` oleh Tanpa Acuan, Manajer Kosong, Sopir | 200 · 403 · 403; `data_scope.value` = `milik_sendiri`; `home.view` = `sales-home` |
| U4 | B | — | `adm`: `POST /api/access/roles/preview` `{"role_id": "sales", "levels": {"hr": "view"}}` | `summary.modules` memuat modul `hr` ber-`level` `view`; `nav_added` memuat `hrd` |
| U5 | B | basis data baru | `GET /api/roles` | Untuk 13 peran bawaan `nav.add` = `[]` |
| U6 | B | — | `adm`: `PATCH /api/access/roles/finance` `{"levels": {"hr": "view"}}` → `GET /api/roles` | `nav.add` Finance memuat `hrd` dan `hr-people` |
| U7 | B | peran kustom "K" berdasar `finance` | `adm`: `PATCH …/{K}` `{"base_role": "sales"}` → `GET` | `base_role` = `sales`; `permissions` tidak berubah; `traits.data_scope` = `milik_sendiri` (mengikuti dasar baru) |
| U8 | B | — | `adm`: `PATCH /api/access/roles/manager` `{"base_role": "sales"}`; `PATCH …/{K}` `{"base_role": "admin"}` | 400 "Peran dasar hanya bisa diatur pada peran kustom." · 400 "Peran Admin tidak bisa dijadikan peran dasar." |
| U9 | B | `adm` menyalakan lintas PT pada Finance; peran kustom "Kasir" berdasar `finance` | `adm`: `PATCH …/{Kasir}` `{"cross_entity": false}` → `GET /api/access/roles/{Kasir}` | `cross_entity` = salah (sebelum unit: tetap benar) |
| U10 | B | Manajer dimatikan lintas PT-nya; pelanggan di PT yang tidak ditugaskan ke manajer seed | `GET /api/customers/{id}/360` oleh manajer seed | 403 (sebelum unit: 200) |
| U11 | B | akun X tertaut karyawan E1 | `adm`: `PATCH /api/users/{X}` `{"data": {"employee_id": "<E2>"}}`; lalu `{"data": {"employee_id": ""}}` | Setelah langkah 1: `hr_employees.E1.user_id` kosong, `E2.user_id` = X. Setelah langkah 2: `E2.user_id` kosong |
| U12 | B | — | `adm`: `POST /api/users` tanpa `password`; dengan `password: "1234567"` | 422 atau 400 · 400 "Kata sandi minimal 8 karakter."; tidak ada akun terbuat |
| U13 | B | 2 akun berperan Gudang dengan penugasan PT kedua; satu sesi masing-masing | `adm`: `POST /api/access/roles/warehouse/move-users` `{"to_role": "sales"}` | 200; `allowed_entity_ids` kedua akun dihitung ulang menurut aturan peran tujuan; sesi terhapus; 2 baris audit `user_updated` |
| U14 | B | `adm` mengubah Sales dua kali (cabut `order.cancel`, lalu beri kembali) | `GET /api/access/roles/sales/history` | 2 butir; butir lama `removed` = ["Pesanan Penjualan (SO): Batalkan"], butir baru `added` berisi yang sama |
| U15 | B | peran kustom dengan satu akun nonaktif | `GET /api/access/roles/{peran}` | `deletable` = salah; `users_inactive` = 1 |
| U16 | B | — | `adm`: `POST /api/access/roles` dengan `hidden_views: ["finance-cases"]` | 200 dalam satu panggilan; `hidden_views` tersimpan |
| U17 | B | berkas kode jawaban Manajer untuk `/api/customers`, `/api/bank-accounts`, `/api/cash-transactions`, `/api/access/roles` (403), `/api/users`, dibuat sebelum kode diubah | Ulangi oleh manajer seed (lintas PT bawaan) | Kode sama |
| U18 | layar (uji jalan) | Login Admin | Buat peran baru → pilih Peran dasar "Sales" → Salin hak akses dari "Admin Sales" → lihat Ringkasan peran → simpan | Dua kontrol terpisah; ringkasan memuat "Data yang terlihat: Milik sendiri" dan kalimat "bisa … tidak bisa …" per modul; tangkapan layar di laporan |
| U19 | layar (uji jalan) | Login sebagai peran kustom ber-`permission.view` saja | Buka tab Peran & Hak Akses → klik kartu | Editor mode baca tanpa tombol simpan; tab Riwayat terbuka |

## Langkah kerja

1. `backend/tests_mem/test_PRT6_layar_peran.py` (U1–U17). Merah: semua kecuali U17.
2. `denied_message` + header; sepuluh tempat manual. Hijau: U1, U2. Uji lama yang mencocokkan teks "Permission
   ditolak" diperbarui ke header.
3. `summary`, pratinjau, `nav.add` peran bawaan. Hijau: U3–U6.
4. `base_role` di `RolePatch`, lintas PT, tiga tempat butir 6. Hijau: U7–U10, U17.
5. Akun: sandi, tautan karyawan, pindah massal, `deletable`, riwayat, `hidden_views` saat buat. Hijau: U11–U16.
6. Label tabel 8 + label audit.
7. Layar editor dan akun; U18, U19 di lingkungan A.
8. Gate penuh, `scripts/audit_i18n_id.py`, `verify_role_label.py`, `verify_error_notice.py`; laporan.

## Dokumen ikut berubah

`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("peran dasar", label yang diganti); `CODEBASE_MAP.md`; `memory/PRD.md`.

## Di luar lingkup

- Isian sifat peran (cakupan data, halaman awal, kategori kerja, notifikasi) → sudah di PR-T4; unit ini hanya
  meringkasnya.
- Batas persetujuan per peran dan pesan penolakan persetujuan ("Approval PO butuh role minimal…") → KP-T4.
- Pesan Pusat Pengaturan ("…butuh izin settings.manage") → KF-T1. Pesan Meja Saya → PR-T4.
- Tombol di layar lain yang masih memakai nama peran → PR-T7.
- Letak layar di menu (PR-UX-39) → KP-T9. Kilas menu saat awal sesi (PR-UX-41) dan tata letak HP (PR-UX-42) → PR-T7.
- Wajib ganti sandi saat masuk pertama, masa berlaku sandi, "lihat sebagai peran ini", bandingkan dua peran, pulihkan
  versi peran, masa berlaku akses, peran ganda (lampiran B §8): tidak ada unit yang memegangnya.

## Asumsi dan risiko

- `ASUMSI:` peran dasar tetap ada sebagai sumber nilai awal sifat dan menu warisan; karena itu ia dibuat bisa diganti,
  bukan dihapus.
- `ASUMSI:` menu peran bawaan boleh bertambah hanya sebesar selisih terhadap izin bawaannya; ini satu-satunya aturan
  yang tidak mengubah menu siapa pun saat dipasang.
- `ASUMSI:` mematikan lintas PT tidak mempersempit penugasan akun secara otomatis; Admin meninjau daftarnya.
- `ASUMSI:` teks label di tabel 8 mengikuti usulan lampiran B §7; label lain tidak diubah.
- `RISIKO:` alat atau uji yang mencocokkan teks "Permission ditolak" berhenti bekerja. Penangkal: header
  `X-Permission-Denied`; penerjemah lama di layar tetap dipertahankan. Membatalkan: kembalikan `denied_message` ke
  teks lama.
- `RISIKO:` akun yang dibuat lewat impor tanpa sandi kini ditolak. Itu disengaja; pesan galatnya menyebut sebabnya.
