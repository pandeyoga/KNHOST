# PR-T8 — Penjaga matriks izin berjalan (peran × endpoint)

- Commit awal: `b8bd0a2` (dikerjakan) · digabung di atas `13b84dd` (sesudah PK-21, KP-T7, KF-T4)        - Commit akhir: `303e709`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: — (infrastruktur; menjaga agar PR-01, PR-03, PR-04 tidak kembali) — K-47; standar `02` §3.1 Z1/Z3,
  §3.2 butir 4, §6

## Cek ulang "Keadaan sekarang" (di `b8bd0a2`)

| # | Hasil |
|---|---|
| 1 | Berlaku. `t2_roles.py:28` (`specs`), `:52` (`gets`). Rute GET hidup kini **800** (bukan 786); seluruh rute `/api` **1.773** |
| 2 | Berlaku (`t2_analyze.py:19` `klass`). Hasil di HEAD lewat penjaga baru: tidak ada rute GET yang menolak pemegang semua izin (M2 = 0) dan **tidak ada lagi rute yang terbuka lewat peran dasar** (M3 = 0, M4 = 0) — 23 rute audit sudah ditutup PR-T2/PR-T3 |
| 3 | Berlaku (`t9_tulis_tanpa_izin.py:54` `contoh`, `:212` `sesi_akhir`). Di HEAD 973 rute tulis; dengan pembuat isi yang diperbaiki (lihat Menyimpang 2) **0 rute tak teruji** (jalan pertama dengan `contoh` T9 apa adanya: 30 rute 422) |
| 4 | Berlaku (`inv_endpoints.py:54` `helper_prims`); penjaga baru tidak memakai inventaris statik |
| 5 | Berlaku (`t2_analyze.py:20` `TOLAK_GERBANG`). Penjaga baru tidak menilai dari teks; teks hanya dipakai membaca izin yang diminta |
| 6 | Berlaku. `run_gate` kini `scripts/gate.sh:141`; blok `--full` bergeser ke `:877` (spesifikasi: `:865`) |
| 7 | Berlaku. `verify_auth_coverage` 28 pelanggaran (daftar sama dengan PR-T3/PR-T5) |
| 8 | Berlaku. `backend/login_only_endpoints.py` (54 entri: 53 PR-T3 + `GET /api/access/labels` PR-T5); `backend/tests_mem/conftest.py` |

## INV-PERM-02 — penjaga matriks izin berjalan

- Berlaku di HEAD: fitur baru — skrip sapuan hanya ada di arsip audit dan tidak dipanggil gate mana pun (butir 6).
- Akar masalah: wewenang dijaga dengan membaca kode (inventaris statik), yang keliru menilai pembantu bernama sama dan
  rute login-saja; tidak ada uji jalan yang memerah bila endpoint baru lolos tanpa izin atau terbuka karena peran dasar.
- Perubahan perilaku: **tidak ada** pada aplikasi (U14). Yang baru adalah alat uji di `backend/tests_mem/` + satu baris
  gate.
- Fixture disiapkan langsung vs proses bisnis: peran uji lewat `POST /api/access/roles`, akun lewat `POST /api/users`,
  sesi lewat `POST /api/auth/login` (alur). Satu-satunya fixture sisip: sesi Admin pembuat (sandi seed tiruan acak —
  pola `conftest.sesi`). Rute sementara uji U2–U7 didaftarkan langsung ke `server.app` (fixture) dan dicabut sesudahnya.

### Berkas berubah

| Berkas | Isi |
|---|---|
| `backend/tests_mem/sapuan_izin.py` (baru) | Penjaga: proses awal tiruan (`boot_app`), pembuat peran/akun, penyapu, pembuat isi dari OpenAPI (inti `contoh` T9 dipindah ke kelas `PembuatIsi`), penilai murni `nilai()` M0–M8, `--penuh`, `--awalan`, `--keluaran`, `--harapan`, `--uji-diri` (23 kasus bukti-merah tanpa aplikasi) |
| `backend/tests_mem/sapuan_izin_harapan.json` (baru) | Daftar pengecualian beralasan (isi di bawah) |
| `backend/tests_mem/test_PRT8_sapuan_izin.py` (baru) | U2–U10 + bentuk berkas harapan + `--uji-diri` lewat baris perintah (10 uji, ±21 dtk) |
| `backend/tests_mem/README.md` | Bagian "Penjaga matriks izin berjalan": perintah, lama jalan terukur, bagian berkas harapan, **aturan endpoint baru** (6 butir spesifikasi) |
| `scripts/gate.sh` | Blok `--full`: `guard:matriks_izin SELF-TEST` + `guard:matriks_izin (INV-PERM-02, peran × endpoint)`; `skip_gate` "mongomock-motor belum terpasang (backend/tests_mem/requirements.txt)" bila `python -c "import mongomock_motor"` gagal. Tingkat `--quick`, bawaan, `--ci` tidak berubah |
| `scripts/guardrails/verify_auth_coverage.py` | `PUBLIC_ALLOWLIST` + `"GET /api/"` (tanda hidup API di `server.py`, jalur absolut; pemindai statik hanya membaca `routers/*.py`, hasilnya tetap 28) |
| `docs/blueprint/03_LINGKUNGAN_UJI.md` §3, `docs/KN_00_AGENT_QUICK_START.md`, `CODEBASE_MAP.md` | Baris skrip + lama jalan; daftar gate `--full`; peta dihasilkan ulang generator (berkas `tests_mem` tidak dipetakan generator — hanya baris komit/urutan berubah) |

Tidak berubah: semua berkas `backend/` di luar `backend/tests_mem/` (termasuk `login_only_endpoints.py`), `frontend/`,
`middleware/`, `rfid*`/`handheld`, `docs/blueprint/STATUS.md`, `TRACKER.md`, berkas unit.

### Cara kerja ringkas

- Rute: semua `server.app.routes` berawalan `/api/` (tanpa `HEAD`/`OPTIONS`, tanpa `/api/auth/logout*`).
  Akun berurutan paling lemah dulu: `tanpa_token` → `kosong` (Tanpa Acuan Kosong) → `sopir` → `mgr0` (Manajer Kosong) →
  [--penuh: 11 "{peran} Kosong" lagi] → `penuh` (Tanpa Acuan Penuh, tiap modul pada tingkat tertinggi di
  `levels_available`; GET saja) → [--penuh: 13 akun peran bawaan; GET saja].
- Kelas jawaban sesuai spesifikasi. Izin yang diminta: header `X-Permission-Denied` (belum ada — PR-T6) atau teks lama
  digabung **jejak pemeriksa inti** (Menyimpang 1). Pada HEAD, dari 1.691 penolakan akun `kosong`: 1.555 terbaca dari teks,
  63 hanya dari jejak, 35 tanpa izin terbaca (kalimat Z6 dari pemeriksa yang membaca matriks sendiri, mis. `config._allowed`).
- Keluaran `--keluaran`: `hasil[akun]["METODE jalur"] = [kode, kelas, izin_diminta]`, plus `pesan`, `akun`, `sesi_akhir`,
  `jumlah`, `pelanggaran`.

## Hasil jalan pada HEAD — 20 baris, 14 rute: temuan baru (tidak dimasukkan ke daftar)

Mode cepat dan mode penuh memberi **20 baris yang sama** (M0 6, M1 14); tidak ada M2–M8. Sesuai langkah kerja 3, baris
M1 yang bukan milik unit PK-17/KF-T1/KP-T4/PR-T4 **tidak** dimasukkan ke berkas harapan — penjaga tetap MERAH sampai
dibereskan. `STATUS.md` "Menunggu pemilik" tidak diubah (aturan sesi); usulan baris ada di "Yang perlu direview".

**A. Perilaku benar, putusan login-saja belum tertulis** (perbaikan = satu baris `LOGIN_ONLY`, keputusan Z3):

| ID | Rute | Kode | Jangkar | Usulan |
|---|---|---|---|---|
| T8-01 | `GET /api/dashboard` | M1 (200) | `routers/dashboard.py:41` | `rujukan` — isi disaring izin per bagian (PR-T3 S1); terlewat karena inventaris statik menggolongkannya IZIN |
| T8-02 | `GET /api/approval-policies/can-decide/me` | M1 (400 `doc_kind` contoh) | `routers/approval_policies.py:102` | `milik_sendiri` — boleh-tidaknya pemanggil memutus (KP-T4) |
| T8-03 | `GET /api/interco/prices/access` | M1 (200) | `routers/interco_prices.py:34` | `sesi` — dua bendera izin pemanggil sendiri |
| T8-04 | `GET /api/hr/payslips/{slip_id}`, `…/pdf` | M1 (404) | `routers/hr_payroll.py:233`, `:244` | `milik_sendiri` — pemilik slip atau berizin (`_can_view_slip`) sesudah slip dimuat |
| T8-05 | `POST /api/hr/leave-requests/{leave_id}/cancel` | M1 (404) | `routers/hr_leave.py:181` | `milik_sendiri` — pengaju, atau `hr.manage_attendance` sesudah dokumen dimuat |

**B. Gerbang sesudah dokumen dimuat (Z1)** — id contoh dijawab 404 sebelum gerbang:

| ID | Rute | Kode | Jangkar | Catatan |
|---|---|---|---|---|
| T8-06 | `POST /api/ap-payments/{intent_id}/resume`, `…/cancel` | **M0** + M1 (404) | `routers/ap_payments.py:63`, `:75` → `_guard_intent` `:39` → `entity_scope.guard_doc` `:489` | 404 **tanpa sesi** (oracle keberadaan id; id yang ada → `entity_ctx` → 401). Sumber daya izin dipilih dari `intent.kind`. Asal PK-05 |
| T8-07 | `POST /api/registration/sessions/{sid}/approve`, `…/return`; `PATCH`/`DELETE …/lines/{line_id}` | **M0** + M1 (404) | `routers/initial_registration.py:299`, `:269`, `:191`, `:202` → `_session` `:84` → `guard_doc` | Sama dengan T8-06; izin `inventory.approve_value`/`approve_count` dipilih dari pengaturan PT sesi |
| T8-08 | `POST /api/special-orders/{order_id}/fulfillment/{item_key}/cancel` | M1 (404) | `routers/special_orders.py:817` | `current_user` → `_od_or_404` → `_can("cancel")`; sudah dicatat PR-T3 (Asumsi) — obatnya pola S8 PR-T3 (`require_permission("od_fulfillment","cancel")` lebih dulu) |
| T8-09 | `POST /api/config/values/cancel-scheduled` | M1 (404) | `routers/config.py:394` | Izin per kunci dari baris jadwal yang dimuat (KF-T3). Area Pusat Pengaturan — KF-T4 sedang berjalan |

## Berkas harapan (`sapuan_izin_harapan.json`) — isi

| Bagian | Baris | Isi |
|---|---|---|
| `tolak_bukan_izin` | 0 | Tidak ada GET yang menolak akun `penuh` dengan 403 (13 GET ditolak 401: rute perangkat ber-`X-Device-Key`/sesi handheld, H7) |
| `menunggu_unit` | 12 | PR-T4 `GET /api/desks/me`; PK-17 `GET /api/home/sales`, `/home/warehouse`; KF-T1 `GET /api/settings/compute-tax`, `/settings/effective`, `/settings/evaluate-approval`; KP-T4 `POST` approve/reject `landed-costs`, `purchase-orders`, `vendor-bills` (6). Semuanya diserahkan PR-T3 tabel A; keempat unit pemegang sudah `implemented_pending_review` tanpa memutuskan baris ini |
| `tak_teruji` | 0 | — |
| `galat_dikenal` | 1 | `POST /api/push/subscribe` — 503 "Notifikasi push belum dikonfigurasi di server." (lingkungan B tanpa kunci VAPID; jawaban sah) |
| `isi_contoh` | 17 | Validasi sebelum gerbang: `ai/export.xlsx` (`ids`), `ap-payments/accounts`·`pending` (`kind`), `customers/{id}/merge` (alasan), `documents/relations/{doc_type}/…` (`doc_type`), `gl/inventory-drift-explain` (`entity_id` PT tugas); izin per kunci Pusat Pengaturan dengan kunci nyata `tax.ppn_rate`: `config/explain`, `layers`, `simulate`, `PUT values` (nilai = bawaan), `values/clear`, `values/reset`; **H7** (perilaku tidak diubah): `handheld/batches`, `handheld/tasks`, `tasks/{kind}/…/complete`·`expected` (jenis tugas sah), `rfid/v2/passages/{id}/acknowledge` (`device_id`) |

Sesudah isi contoh, ke-17 rute itu menolak `tanpa_token` (401) dan `kosong` (403/401) — gerbangnya teruji, bukan
dikecualikan. Rute `/api/` (tanda hidup) masuk `PUBLIC_ALLOWLIST`.

## Uji penerimaan

Merah di kode lama: (a) berkas uji pada `git archive b8bd0a2` → **gagal dikumpulkan** (`sapuan_izin` belum ada,
`bukti/PR-T8/tests_mem_PRT8_merah_kode_lama.log`); (b) penjaga pada kode **sebelum PR-T2** (`ba0565c`, salinan `git
archive` + berkas baru) → **128 baris: M0 6, M1 22, M2 40, M3 58, M7 2** (`bukti/PR-T8/sapuan_cepat_kode_sebelum_PRT2_ba0565c.log`)
— kelas cacat PR-01/03/04 tertangkap (contoh: `GET /api/ai/catalog` mgr0 200 "juga tertutup bagi Sopir"; penuh 403
"Asisten analitik belum dibuka untuk peran Anda"). Hijau: `bukti/PR-T8/tests_mem_PRT8_hijau_kode_baru.log` (10/10).

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | B | ya (128 baris di `ba0565c`) | **MERAH di HEAD — keluar 1**: ringkasan lima akun; 20 baris = temuan baru T8-01…T8-09 di atas, tidak satu pun dimasukkan daftar (langkah kerja 3). Usulan koreksi bunyi di bawah |
| U2 | B | ya (modul tidak ada) | Lulus — keluar 1; tepat satu baris M0 `GET /api/_uji/tanpa-sesi` `tanpa_token` 200 (ditambah M1 bagi `kosong`, karena rute tanpa penegak juga lolos tanpa izin) |
| U3 | B | ya | Lulus — keluar 1; satu-satunya baris M1; `tanpa_token` 401 |
| U4 | B | ya | Lulus — keluar 1; satu-satunya baris M2 (`penuh` 403); `kosong` 403 berizin `order.view` |
| U5 | B | ya | Lulus — keluar 1; satu-satunya baris M3 `mgr0` 200 bertanda "juga tertutup bagi Sopir" (rute `POST`, supaya akun `penuh` yang hanya GET tidak ikut) |
| U6 | B | ya | Lulus — keluar 1 dengan satu baris M6 (422 bagi keempat akun); dengan `isi_contoh` `{"json": {"kode": "KN-0001"}}` keluar 0 (401·403·403·403) |
| U7 | B | ya | Lulus — keluar 1; satu baris M7 "tolak_bukan_izin: rute tidak ada"; baris tanpa alasan juga ditolak |
| U8 | B | ya | Lulus — `nilai()` atas hasil buatan: dua baris M5 (`sales` lolos tanpa `accounting.view`; `finance` 403 padahal memegangnya — izin dari `DEFAULT_PERMISSIONS`) |
| U9 | B | ya | Lulus — `GET /api/costing/wac`: `kosong` 403 · `penuh` 200 · `mgr0` 403 · `sopir` 403 (label "Tanpa Acuan Penuh", "Manajer Kosong"); berkas `bukti/PR-T8/U9_keluaran_costing.json` |
| U10 | B | ya | Lulus — empat akun bersesi 200 di `GET /api/auth/me`; `users` 4 seed + 4 = 8, `custom_roles` 0 + 3 = 3 (mode cepat; mode penuh 4 + 28 = 32, 0 + 14 = 14). `tanpa_token` tidak bersesi (lihat koreksi) |
| U11 | B | — | Mode penuh: **tidak ada M4 maupun M5** untuk 13 peran bawaan, termasuk Manajer; keluar 1 hanya karena 20 baris U1 yang sama (`bukti/PR-T8/sapuan_penuh_HEAD.log`) |
| U12 | B | ya | Lulus — 10 uji dalam 20,6–21,3 dtk (`-n 0`) |
| U13 | A | — | **Belum dijalankan** (butuh lingkungan A). Blok gate yang sama diuji terpisah di lingkungan B dengan `run_gate`/`skip_gate` asli: tanpa `mongomock-motor` → SELF-TEST PASS, `guard:matriks_izin` **SKIP** dengan alasan; dengan → SELF-TEST PASS, `guard:matriks_izin` **FAIL** (20 temuan, 71 dtk) (`bukti/PR-T8/U13_blok_gate_*.log`). Gate lain tidak dijalankan |
| U14 | B | — | Lulus — `git status`: di `backend/` hanya `tests_mem/` (README, tiga berkas baru) |
| U15 | B | — | Mode cepat: 7.892 permintaan, **67–73 dtk** sendiri (±75 dtk dengan proses awal; 121 dtk saat CPU dibagi dengan `tests_mem` paralel). Mode penuh: 37.795 permintaan, **340–350 dtk** (±6 mnt). Tertulis di README dan `03` §3 |

`backend/tests_mem`: **510 lulus / 2 dilewati / 3 xfail → 520 / 2 / 3** (+10 uji PR-T8; dua pekerja) di salinan kerja.
Sesudah digabung (tanpa konflik; `scripts/gate.sh` otomatis): **567 → 577 lulus** / 2 / 3. Sapuan cepat di HEAD gabungan
(sesudah KF-T4, KP-T7, PK-21 yang menambah endpoint): 1773 rute, 7892 permintaan, 64 dtk — **20 baris yang sama**, tidak ada
temuan baru dari unit yang masuk sesudahnya.
Jest: tidak dijalankan (tidak ada berkas `frontend/` berubah).

## Penjaga statik

| Penjaga | Sebelum | Sesudah |
|---|---|---|
| `hitung_penjaga.sh` (16 penjaga) | `verify_auth_coverage` 28, `verify_ui_standard` 23, `audit_i18n_id` 111, `audit_create_modal` 6, `verify_page_tabs` 1, `verify_to_list_bound` 6, `verify_entity_label` 2, lainnya 0 | **identik** (`bukti/PR-T8/penjaga_hitung_sebelum_sesudah.txt`) |
| `verify_auth_coverage --self-test` | hijau | hijau (8/8) |
| `verify_role_gate_ui` | — | PASS 33 cek |
| `verify_permission_checked` (INV-PERM-01) | — | PASS 580 cek |
| `audit_config_wiring --strict` (salinan berjalur `$W`) | — | keluar 0 |
| `sapuan_izin.py --uji-diri` (baru) | — | 23/23 PASS |

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `303e709`), sesudah `restore_demo` (data acuan; tiga skrip seed yang
sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Satu jalan gate untuk dua unit
yang digabung berturut-turut (KF-T4 `13b84dd`, PR-T8 `303e709`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Baris gate baru KF-T4 (`guard:config_text` + self-test, `config_key_index`) PASS di kedua mode. Baris PR-T8
(`guard:matriks_izin` + self-test) hanya di `--full` (tidak dijalankan); penjaga dijalankan terpisah di lingkungan B pada
`303e709`: self-test HIJAU, sapuan cepat MERAH dengan 20 baris yang sama dengan temuan PR-T8 (`bukti/PR-T8/sapuan_cepat_HEAD_gabungan.txt`).

## Menyimpang dari blueprint

1. **Izin yang diminta = teks lama ∪ jejak pemeriksa inti** (bila header PR-T6 belum ada). Spesifikasi: header, lalu teks.
   Teks hanya menyebut pemeriksaan terakhir: `GET /api/design-gallery` (`rnd.view` lalu `hr.view`) menjawab "Permission
   ditolak: hr.view", sehingga mode penuh sempat memberi **32 baris M5 palsu** (8 peran bawaan pemegang `rnd.view`
   "lolos tanpa memegang hr.view", `bukti/PR-T8/jalan_antara_penuh_sebelum_perbaikan_penilai.log`). Jejak = pembungkus `dependencies.permission_matrix` di proses
   sapuan saja (dipanggil lewat nama global hanya oleh `has_permission`/`require_permission`/`require_any_permission`),
   mencatat pasangan yang diperiksa dan tidak dipegang; kalimat Z6 tanpa `x.y` juga jadi terbaca (63 penolakan). Kode
   aplikasi tidak diubah.
2. **Pembuat isi**: parameter jalur bilangan → `1`, enum → nilai pertama (spesifikasi: `x`; 20 rute `{seq}`/`{page}`/
   `{line_no}` 422); string menghormati `maxLength`; nama `reason`/`alasan`/`note`… → "Uji sapuan izin otomatis"
   (validator ≥ 5 huruf), nama telepon → `081234567890`. `isi_contoh` menerima juga `data` dan `path` (parameter jalur),
   dan hanya menimpa bagian yang disebut. Hasil: 30 rute 422 → 0, tanpa satu pun baris `tak_teruji`.
3. **Rute `PUBLIC_ALLOWLIST` tidak dinilai M3–M5**: `POST /api/auth/login` dikunci sesudah lima percobaan gagal, sehingga
   10 akun "{peran} Kosong" yang datang belakangan mendapat 429 = "lolos" → 10 M4 palsu. Jawaban rute tanpa sesi tidak
   bergantung pada peran.
4. **M7 diperluas**: juga `tolak_bukan_izin` yang tidak lagi 403, `tak_teruji` yang tidak lagi 422, `galat_dikenal` yang tidak
   lagi galat, entri `tolak_bukan_izin` non-GET, bagian/bentuk berkas harapan yang salah. Dengan `--awalan`, M7 hanya
   menilai entri di bawah awalan itu.
5. **M8 diperluas** dengan jumlah `users`/`custom_roles` ≠ seed + buatan sapuan (bunyi U10). **M6** satu baris per rute
   (bukan per akun), dengan jumlah akun lain yang terkena.
6. **Mode penuh**: 12 peran "{peran} Kosong" = `mgr0` (dinilai M3) + 11 lainnya (M4); akun peran bawaan dibuat baru lewat
   API (sandi seed tiruan acak), termasuk Admin.
7. **Gate**: selain satu baris spesifikasi, ditambah `guard:matriks_izin SELF-TEST` di blok yang sama (`--full`, di luar
   cabang `AUTH_READY`) — bukan di daftar statik, karena spesifikasi menetapkan `--quick`/bawaan/`--ci` tidak berubah.
8. **Lapis A** (`backend/tests/test_bp_PRT8_*.py`) tidak ditulis: U13 adalah perintah gate, dan U14 melarang berkas
   `backend/` di luar `tests_mem/`.
9. **`PUBLIC_ALLOWLIST` + `"GET /api/"`** (berkas `scripts/`, bukan `backend/`): rute tanda hidup di `server.py`; tanpa itu
   M0+M1 untuk rute tanpa data.
10. **`LOGIN_ONLY` tidak diubah** walau temuan A (T8-01…T8-05) cukup diobati satu baris tiap rute: itu putusan Z3 dan U14
   melarang perubahan `backend/` di luar `tests_mem/` (juga `test_PRT3_login_saja.py` U13 menghitung 54 entri).

## Usulan koreksi blueprint (teks pengganti persis, `docs/blueprint/unit/PR-T8.md`)

- U1, kolom "Hasil yang diharapkan":
  > Keluar 0 bila tidak ada temuan terbuka; ringkasan memuat lima akun. Pada HEAD unit ini keluar 1 dengan tepat 20 baris (M0 6, M1 14) di 14 rute — temuan baru T8-01…T8-09 di laporan PR-T8, yang menurut langkah kerja 3 tidak dimasukkan ke daftar; tidak ada baris lain
- U10, kolom "Hasil yang diharapkan":
  > Keempat akun bersesi (`kosong`, `penuh`, `mgr0`, `sopir`) 200 di `GET /api/auth/me` (tidak ada M8; `tanpa_token` tidak bersesi); jumlah dokumen `users` dan `custom_roles` = seed + buatan sapuan
- U11, kolom "Hasil yang diharapkan":
  > Tidak ada M4 maupun M5 untuk 13 peran bawaan — termasuk Manajer: tiap rute GET yang izinnya ia pegang tidak dijawab 403 berizin itu. Baris lain sama dengan U1
- Bagian "Kelas jawaban", kalimat izin:
  > Izin yang diminta sebuah penolakan dibaca dari header `X-Permission-Denied` (lahir di PR-T6); bila header tidak ada, dari pola teks lama `Permission ditolak: <sumber daya>.<aksi>` digabung pasangan yang diperiksa `has_permission`/`require_permission`/`require_any_permission` dan tidak dipegang selama permintaan itu (jejak di proses sapuan)
- "Parameter jalur diisi `x`" →
  > Parameter jalur diisi `x`, kecuali skema menuntut bilangan (`1`) atau enum (nilai pertama); `isi_contoh` boleh menyebut `path`
- Tabel "Perintah", kolom lama: `±8 menit` → `±75 detik (terukur 0,009 dtk per permintaan)`; `±39.000 permintaan` /
  `±40 menit` → `37.795 permintaan` / `±6 menit`. "Pemasangan di gate": `scripts/gate.sh:865` → `scripts/gate.sh:877`.
- `ASUMSI` pertama (lama jalan dari sesi audit) → "terukur: mode cepat ±75 detik, mode penuh ±6 menit".

## Asumsi / keraguan

- `ASUMSI` spesifikasi dipakai: 404 = lolos gerbang. Akibatnya pola "muat dokumen dulu, izin kemudian" (temuan B) merah,
  sesuai maksud Z1; pola itu juga ada di enam rute persetujuan KP-T4 yang dicatat `menunggu_unit`.
- `menunggu_unit`: keempat unit pemegang (PK-17, KF-T1, KP-T4, PR-T4) sudah `implemented_pending_review` tanpa
  memutuskan 12 baris itu — perlu ditugaskan ulang (atau putusan reviewer bahwa baris itu `LOGIN_ONLY`).
- 35 penolakan `kosong` tanpa izin terbaca (pemeriksa yang membaca matriks sendiri dan menjawab kalimat Z6): M5 cabang
  "lolos tanpa memegang" tidak menilai rute itu sampai PR-T6 memasang header.
- Akun `penuh` tidak menyapu rute tulis (spesifikasi): rute tulis yang menolak pemegang izin tidak dijaga di sini.
- Unit paralel (KF-T4, KP-T7, PK-21) yang menambah endpoint akan terlihat di sapuan sesudah digabung; jalankan mode
  cepat sesudah penggabungan. Isi contoh `config/*` memakai kunci `tax.ppn_rate` — bila KF-T4 mengubah bentuk isi
  `config/values`, baris `isi_contoh` itu perlu disesuaikan (M6 akan memerah, bukan diam).

## Titik henti

- H7: `handheld`/`rfid` tidak diubah. Dua pola dicatat: jenis tugas (`handheld_core.kind_context`) dan isi mentah
  `rfid/v2/passages/{id}/acknowledge` divalidasi **sebelum** sesi (404 `KIND_UNKNOWN` / 400 `INVALID_JSON` tanpa sesi,
  tanpa data). Ditangani dengan `isi_contoh` beralasan; dengan isi sah keduanya menolak tanpa sesi.
- H3: tidak ada data nyata disentuh; sapuan hanya berjalan di database tiruan (`boot_app` memaksa `MONGO_URL` palsu).

## Hambatan lingkungan

- Lingkungan A (gate, U13) tidak dijalankan — integrator. Waktu U15 diukur di satu proses Python 3.11 dengan CPU dibagi
  agen lain (angka 67–73 dtk = tanpa beban lain; 121 dtk = saat `tests_mem` berjalan bersamaan).

## Yang perlu direview

- Daftar temuan T8-01…T8-09: kelompok A (keputusan `LOGIN_ONLY`) dan B (pindahkan gerbang izin ke pernyataan pertama atau
  putusan pengecualian). Usulan baris `STATUS.md` "Menunggu pemilik": "PR-T8 — 14 rute merah di `guard:matriks_izin`
  (T8-01…T8-09): A = catat di `LOGIN_ONLY` (dashboard, can-decide/me, interco/prices/access, payslip, batal cuti) atau
  beri izin; B = gerbang izin sebelum dokumen dimuat (ap-payments resume/cancel, sesi pendaftaran, batal pemenuhan OD,
  batal jadwal pengaturan). Usulan: A ke LOGIN_ONLY, B ke unit pemilik router."
- Isi `sapuan_izin_harapan.json` (30 baris; tabel di atas) — terutama 12 `menunggu_unit` dan 5 `isi_contoh` H7.
- Jejak pemeriksa inti (Menyimpang 1): pembungkus hanya di proses sapuan; bila reviewer ingin bunyi spesifikasi persis,
  hapus penggabungan di `izin_diminta` — mode penuh akan memberi 32 M5 palsu (`design-gallery`).

Status: implemented_pending_review (penjaga `--full` MERAH pada 20 baris temuan yang diserahkan ke unit pemilik rutenya).
