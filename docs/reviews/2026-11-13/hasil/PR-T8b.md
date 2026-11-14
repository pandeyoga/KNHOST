# PR-T8b — 14 rute merah penjaga matriks izin: putusan login-saja dan gerbang izin pertama

- Commit awal: `2121202`        - Commit akhir: `66c1de3` (kode + uji; laporan, tracker, papan kerja di commit berikutnya)        - Branch: `claude/wizardly-fermi-q8jeii` (dibuat dari ujung `claude/nifty-carson-jjx3c8` = `2121202`)
- ID ditangani: T8-01 … T8-09 (temuan baru laporan [PR-T8](PR-T8.md), "Hasil jalan pada HEAD"); standar `02_STANDAR.md`
  §3.1 Z1, Z3, Z6; penjaga INV-PERM-02 (`backend/tests_mem/sapuan_izin.py`, gate `--full` baris `guard:matriks_izin`)
- Unit: lanjutan PR-T8 (pemecahan `00_ATURAN_EKSEKUSI.md` §8, akhiran `b`) atas arahan pemilik sesi 14 Nov: A → `LOGIN_ONLY`,
  B → pindahkan gerbang sesi + izin ke baris pertama handler tanpa mengubah aturan bisnis.

## Cek ulang di `2121202`

Sapuan cepat di HEAD diulang (`bukti/PR-T8b/sapuan_cepat_HEAD_2121202.txt`): **20 baris yang sama** dengan laporan PR-T8
(M0 6, M1 14; 1.773 rute, 7.892 permintaan, 62 dtk, keluar 1).

| Temuan | Rute | Jangkar di `2121202` | Berlaku |
|---|---|---|---|
| T8-01 | `GET /api/dashboard` | `routers/dashboard.py:41` — `current_user`, isi per bagian disaring `has_permission(…,"view")` (PR-T3 S1) | ya — perilaku benar, putusan belum tertulis |
| T8-02 | `GET /api/approval-policies/can-decide/me` | `routers/approval_policies.py:102` — `current_user` → `aps.can_decide` (tanpa izin: `allowed:false`, kalimat Z6); docstring modul `:12` sudah menyebut Z3 "milik sendiri" | ya — idem |
| T8-03 | `GET /api/interco/prices/access` | `routers/interco_prices.py:34` — dua bendera `has_permission` pemanggil | ya — idem |
| T8-04 | `GET /api/hr/payslips/{slip_id}`, `…/pdf` | `routers/hr_payroll.py:233`, `:244` — `_can_view_slip` `:259` (karyawan tertaut atau `hr.view`) sesudah slip dimuat | ya — idem |
| T8-05 | `POST /api/hr/leave-requests/{leave_id}/cancel` | `routers/hr_leave.py:181` — pengaju, atau `hr.manage_attendance` sesudah pengajuan dimuat | ya — idem |
| T8-06 | `POST /api/ap-payments/{intent_id}/resume`, `/cancel` | `routers/ap_payments.py:63`, `:75` — `_guard_intent` (`guard_doc`) **sebelum** `require_permission(_RES[intent.kind],"pay")` | ya — tanpa sesi 404 |
| T8-07 | `POST …/registration/sessions/{sid}/approve`, `/return`; `PATCH`/`DELETE …/lines/{line_id}` | `routers/initial_registration.py:299`, `:269`, `:191`, `:202` — `_session` (`guard_doc`) sebelum izin (`_line_actor` dari status sesi; `approve` dari `finance_step_required`; `return` dari `count_approval`) | ya — tanpa sesi 404 |
| T8-08 | `POST /api/special-orders/{order_id}/fulfillment/{item_key}/cancel` | `routers/special_orders.py:817` — `current_user` → `_od_or_404` → `ful._can(user,"cancel")` | ya — tanpa izin 404 |
| T8-09 | `POST /api/config/values/cancel-scheduled` | `routers/config.py:432` — `current_user` → baris jadwal dimuat → `_may_edit(entry)` | ya — tanpa izin 404 |

## Kelompok A — T8-01 … T8-05: putusan "cukup login" ditulis (Z3)

- Berlaku di HEAD: ya (tabel di atas). Perilaku sudah sesuai Z3; yang kurang hanya catatan putusannya, sehingga penjaga
  menilai "kosong lolos di luar `LOGIN_ONLY`" = M1.
- Akar masalah: PR-T3 mengisi `LOGIN_ONLY` dari inventaris statik, yang menggolongkan rute-rute ini "berizin" (ada
  `has_permission` di badan handler) atau tidak menemukannya; PR-T8 tidak mengubah `backend/` di luar `tests_mem/` (U14).
- Perubahan perilaku: **tidak ada**. `backend/login_only_endpoints.py` + 6 entri beralasan (54 → 60):

| Rute | Kategori | Alasan (komentar di berkas) |
|---|---|---|
| `GET /api/dashboard` | `rujukan` | Isi disaring izin per bagian di handler (PR-T3 S1), kuerinya tidak jalan tanpa izin — pola yang sama dengan `GET /api/entities` (S2) |
| `GET /api/approval-policies/can-decide/me` | `milik_sendiri` | Menilai pemanggil sendiri (jalur `/me`); nominal dari pemanggil; tidak memuat data dokumen |
| `GET /api/interco/prices/access` | `sesi` | Dua bendera izin pemanggil (`interco_price.view`/`.set`) untuk menampilkan tombol |
| `GET /api/hr/payslips/{slip_id}`, `…/pdf` | `milik_sendiri` | Slip karyawan yang tertaut ke akun, atau `hr.view`; selain itu 403 |
| `POST /api/hr/leave-requests/{leave_id}/cancel` | `milik_sendiri` | Pengaju membatalkan cutinya; selain pengaju wajib `hr.manage_attendance` |

- `backend/tests_mem/test_PRT3_login_saja.py` U13: angka `53 + 1` → `53 + 1 + 6`; `GET /api/dashboard` **dipindah** dari
  daftar "tidak boleh tercatat" ke pernyataan `== "rujukan"` (berdampingan dengan `GET /api/entities`). Lihat
  "Menyimpang" 1 — harapan PR-T3 ini berubah karena putusan baru, bukan supaya hijau.

## Kelompok B — T8-06 … T8-09: gerbang sesi + izin sebelum dokumen dimuat (Z1)

- Berlaku di HEAD: ya. Tanpa sesi → 404 pada 6 rute (oracle keberadaan id tanpa login: id yang ada → 401, id yang tidak
  ada → 404); bersesi tanpa izin → 404 pada 8 rute.
- Akar masalah: izin persisnya baru bisa dipilih sesudah dokumen dimuat (jenis niat bayar, status sesi pendaftaran,
  pengaturan PT, kunci baris jadwal), sehingga handler memuat dokumen lebih dulu — dan 404-nya mendahului 401/403.
- Perubahan perilaku (sebelum → sesudah), aturan bisnis tetap:

| Rute | Gerbang pertama (baru) | Pemeriksaan sesudah dokumen dimuat |
|---|---|---|
| `ap-payments/{id}/resume`, `/cancel` (`ap_payments.py:79`, `:92`) | `require_any_permission([vendor_bill.pay, contra_bon.pay])` — "Anda belum punya akses untuk membayar tagihan supplier atau kontrabon. Minta Admin menambahkan akses 'Hutang Supplier & Kontrabon'." | **tetap** `require_permission(_RES[intent.kind], "pay")`; kini dengan kalimat Z6 per jenis |
| `registration/…/lines/{line_id}` PATCH/DELETE (`initial_registration.py:207`, `:219`) | `require_any_permission([inventory.cycle_count, inventory.approve_count])` — "…mengubah baris pendaftaran stok awal…'Stok & Persediaan'." | **tetap** `_line_actor` (menunggu persetujuan → `approve_count`, selain itu `cycle_count`); kalimat Z6 |
| `registration/…/return` (`:287`) | `require_any_permission([approve_count, approve_value])` — "…mengembalikan sesi pendaftaran stok awal…" | **tetap**: hitungan sudah disetujui → salah satu dari keduanya; belum → `approve_count`; kalimat Z6 |
| `registration/…/approve` (`:321`) | `require_any_permission([approve_count, approve_value])` — "…menyetujui pendaftaran stok awal…" | **tetap**: langkah Finance aktif (`registration.finance_approval`) → `approve_value` + `assert_finance_ready`; selain itu `approve_count`; kalimat Z6 |
| `special-orders/…/fulfillment/{key}/cancel` (`special_orders.py:822`) | `require_permission("od_fulfillment","cancel")` — "…membatalkan dokumen pengadaan item pesanan khusus…'Pesanan Penjualan'." (pola S8 PR-T3) | Pemeriksaan `ful._can(user,"cancel")` sesudah dokumen **dihapus** — izin yang sama (`has_permission` `od_fulfillment.cancel`) kini di baris pertama |
| `config/values/cancel-scheduled` (`config.py:452`) | `_require_some_edit` (`config.py:77`): sesi + `_may_edit` atas **setidaknya satu** kunci registri — "Anda belum punya akses untuk mengubah pengaturan atau membatalkan jadwal perubahannya. Minta Admin menambahkan akses 'Pusat Pengaturan'." | **tetap** `_may_edit(entry)` kunci baris jadwal + `_assert_scope_write` |

Gerbang pertama = gabungan izin yang **mungkin** diminta pemeriksaan kedua, jadi tidak ada pemegang izin sah yang kini
ditolak lebih awal; yang berubah hanya urutan jawaban bagi yang tidak berizin (401/403 sebelum 404).

- Berkas berubah: `backend/routers/ap_payments.py`, `backend/routers/initial_registration.py`,
  `backend/routers/special_orders.py`, `backend/routers/config.py`;
  `scripts/guardrails/verify_permission_checked.py` (INV-PERM-01: `od_fulfillment.cancel` dicabut dari daftar DINAMIS —
  penjaga sendiri yang memintanya: "sudah punya pemeriksa literal … hapus dari DINAMIS"; 580 → 579 cek, tetap 0 pelanggaran).

## Berkas berubah (seluruhnya)

| Berkas | Isi |
|---|---|
| `backend/routers/ap_payments.py` | Gerbang pertama resume/cancel + kalimat Z6 per jenis |
| `backend/routers/initial_registration.py` | Gerbang pertama approve/return/PATCH/DELETE baris + kalimat Z6 pemeriksaan kedua |
| `backend/routers/special_orders.py` | `fulfillment_cancel`: `require_permission("od_fulfillment","cancel")` di baris pertama |
| `backend/routers/config.py` | `_require_some_edit` + `_SCHEDULE_DENIED`; dipakai `cancel_scheduled_value` |
| `backend/login_only_endpoints.py` | 6 entri beralasan + docstring (jumlah 60) |
| `backend/tests_mem/test_PRT8b_gerbang_pertama.py` (baru) | U1–U9 (tabel uji di bawah) |
| `backend/tests_mem/test_PRT3_login_saja.py` | U13: jumlah 60; dasbor = `rujukan` |
| `backend/tests_mem/README.md` | Baris berkas uji baru di tabel "Isi" |
| `scripts/guardrails/verify_permission_checked.py` | DINAMIS `od_fulfillment`: `("view","override_default")` |
| `docs/reviews/2026-11-13/hasil/PR-T8b.md`, `bukti/PR-T8b/*`, `docs/reviews/TRACKER.md`, `docs/blueprint/STATUS.md` | Laporan, bukti, tracker (T8-01…T8-09), papan kerja (baris 32b) |

Tidak berubah: `backend/tests_mem/sapuan_izin.py`, `sapuan_izin_harapan.json` (tidak ada baris dikecualikan), `frontend/`,
`middleware/`, `rfid*`/`handheld`, `deploy/`, `backend/pytest.ini`.

## Uji penerimaan

Bukti merah: berkas uji final dijalankan di salinan `git worktree` `2121202` (kode lama apa adanya) —
**9 gagal / 7 lulus** (`bukti/PR-T8b/tests_mem_PRT8b_merah_salinan_2121202.txt`; jalan pertama di salinan kerja sebelum
router diubah: sama, `tests_mem_PRT8b_merah_kode_lama.log` dengan isi `AssertionError`). Hijau:
`tests_mem_PRT8b_hijau_kode_baru.log` (U1–U9 + seluruh `test_PRT3_login_saja.py`: 29 lulus).

| ID | Lapis | Isi | Merah di lama | Hasil baru |
|---|---|---|---|---|
| U1 | B | Tanpa sesi → 401, 8 rute B (isi sah) | **ya, 6/8** (404 "Pembayaran / Sesi pendaftaran tidak ditemukan"); OD-cancel & cancel-scheduled sudah 401 (`current_user` dulu) | Lulus 8/8 |
| U2 | B | Bersesi tanpa izin (Tanpa Acuan Kosong, Manajer Kosong, Sopir) → 403, kalimat Z6 tanpa `x.y`, 8 rute | **ya** (404 "… tidak ditemukan" mendahului 403; daftar di `tests_mem_PRT8b_merah_kode_lama.log`) | Lulus |
| U3 | B | Pemegang izin paling sempit gerbang pertama (15 pasangan rute × izin, 8 peran uji) → tetap 404 (dokumen tidak ada) | lulus (dulu juga 404) | Lulus |
| U4 | B | Niat bayar faktur (sisip, `done`): `contra_bon.pay` → 403; `vendor_bill.pay` → 409 (resume & cancel) | lulus (aturan lama) | Lulus |
| U5 | B | Sesi pendaftaran `pending_approval` (sisip): `cycle_count` PATCH/DELETE baris → 403; `approve_count` DELETE → bukan 401/403; `approve_value` return → 403; `approve_count` approve (langkah Finance bawaan aktif) → 403; `approve_value` approve → 400 "Langkah 1 belum" | lulus (aturan lama) | Lulus |
| U6 | B | Jadwal `ar.grace_days` (Admin, `PUT /config/values`): `inventory.configure` saja → 403 kalimat per kunci, jadwal tidak batal; Admin → 200 | lulus (aturan lama) | Lulus |
| U7 | B | Batal pemenuhan OD: `od_fulfillment.choose_route+realize` dan `order.view+update` → 403 | **ya** (404 "Special order tidak ditemukan") | Lulus |
| U8 | B | 6 rute A ada di `server.app.routes` dan tercatat `LOGIN_ONLY` dengan kategorinya | **ya** (`('GET','/api/dashboard')` → `None`) | Lulus |
| U9 | B | Perilaku rute A tetap: dasbor 200 bagian kosong; `prices/access` dua bendera `false`; `can-decide/me` `allowed:false` kode `izin` kalimat Z6; slip/pdf/batal cuti: kosong 404, tanpa sesi 401 | lulus | Lulus |

### Penjaga matriks izin (`sapuan_izin.py`, lingkungan B)

| Jalan | Sebelum (`2121202`) | Sesudah |
|---|---|---|
| Mode cepat | keluar 1 — 20 pelanggaran (M0 6, M1 14); tanpa_token lolos 8, kosong lolos 81 | **keluar 0 — HIJAU, 0 pelanggaran**; tanpa_token lolos 2, kosong lolos 73; 1.773 rute, 7.892 permintaan, 64 dtk (`bukti/PR-T8b/sapuan_cepat_sesudah.txt`) |
| Mode penuh (`--penuh`, README: wajib untuk unit yang mengubah gerbang endpoint) | laporan PR-T8: 20 baris yang sama (M0 6, M1 14) | **keluar 0 — HIJAU, 0 pelanggaran**; 37.795 permintaan, 353 dtk; 13 peran bawaan tanpa M4/M5, 12 peran "{peran} Kosong" tanpa M3/M4; `users` 4 + 28, `custom_roles` 0 + 14 (`bukti/PR-T8b/sapuan_penuh_sesudah.txt`) |

### `backend/tests_mem`

| Salinan | Hasil (`cd backend && python -m pytest tests_mem -q`, dua pekerja `pytest.ini`) |
|---|---|
| `2121202` (git worktree, mesin yang sama) | 577 lulus / 2 dilewati / 3 xfail, 135 dtk |
| Sesudah (`66c1de3`) | **593 lulus** / 2 dilewati / 3 xfail, 130 dtk — +16 uji baru (U1 ×8, U2–U9); tidak ada yang berubah merah |

Jalan antara (sebelum perbaikan penjaga INV-PERM-01): 1 gagal `test_PRT5_U12_penjaga_izin_diperiksa` — penjaga meminta
`od_fulfillment.cancel` dicabut dari DINAMIS karena kini punya pemeriksa literal; diperbaiki, lalu suite diulang dari awal.
Bukti: `bukti/PR-T8b/tests_mem_sebelum_sesudah.txt`.

## Penjaga statik dan gate

| Penjaga / gate | Sebelum (`2121202`) | Sesudah |
|---|---|---|
| `gate.sh --quick --no-parallel` (lingkungan B, mesin yang sama) | PASS 43 · FAIL 18 · SKIP 4 | **identik baris per baris** (diff receipt tanpa waktu kosong) — 0 lebih merah, 0 menjadi hijau |
| Jumlah pelanggaran di dalam gate yang merah (auth 28, i18n, create_modal, page_tabs, to_list, entity_label, numeric_bounds HARD 3 / SOFT 5, …) | — | sama persis; satu-satunya selisih INV-PERM-01 `580 → 579` cek, 0 pelanggaran (satu entri DINAMIS berkurang; pasangannya tetap dicek, kini literal) |
| `verify_auth_coverage` | 28 pelanggaran (1.751 cek) | 28 (1.751) |
| `verify_permission_checked` + `--self-test` | PASS 580 | PASS 579; self-test LULUS |
| `verify_codebase_map` (INV-DOC-01) | — | PASS (tidak ada fungsi/berkas inti baru) |
| `sapuan_izin.py` cepat / `--penuh` | keluar 1 (20) | keluar 0 / keluar 0 |

Bukti: `bukti/PR-T8b/gate_quick_sebelum.txt`, `gate_quick_sesudah_selisih.txt`. `memory/GATE_RECEIPT.*` hasil jalan ini
dikembalikan (tidak di-commit, `00` §3). Gate bawaan/`--ci`/`--full` (butuh lingkungan A) tidak dijalankan.

## Fixture disiapkan langsung vs proses bisnis

- Peran uji lewat `POST /api/access/roles` (fixture baku `peran_tanpa_acuan`, `peran_manajer_kosong`), akun + sesi lewat
  fixture `akun`/`sesi` (sisip, pola PK-02). Jadwal pengaturan lewat `PUT /api/config/values` (alur).
- Disisipkan langsung (bentuk minimal yang dibaca handler): satu niat bayar `ap_payment_intents` berstatus `done` (U4),
  satu sesi `cycle_count_sessions` `mode=registration` `pending_approval` (U5). Tidak ada data nyata disentuh (H3).

## Dampak pada modul terkait

- Layar: tidak ada berkas `frontend/` berubah. Bagi yang tidak berizin, layar kini menerima 403 berkalimat Z6 alih-alih
  404 (apakah tombolnya sudah disembunyikan `can(...)` di tiap layar tidak diperiksa di unit ini).
- Pesan 403 teknis lama `Permission ditolak: vendor_bill.pay` / `inventory.approve_*` / `inventory.cycle_count` /
  `od_fulfillment.cancel (…)` di rute-rute ini diganti kalimat Z6 (pencarian di `backend/tests*` dan `frontend/src`: tidak
  ada yang bergantung pada teks lama). Penjaga sapuan tetap membaca izinnya lewat jejak pemeriksa inti.
- Biaya: rute ap-payments dan sesi pendaftaran kini memanggil `current_user` dua kali (gerbang pertama + pemeriksaan
  kedua) — satu baca sesi tambahan per permintaan; batal pemenuhan OD dan batal jadwal tetap sekali.

## Menyimpang dari arahan / blueprint

1. **Harapan PR-T3 U13 diubah dua hal** (bukan hanya angka): `GET /api/dashboard` tercantum di daftar "rute yang diberi izin /
   disaring unit ini tidak boleh tercatat sebagai login-saja sah". Putusan kelompok A menjadikannya `rujukan`, maka
   barisnya dipindah ke pernyataan `LOGIN_ONLY[dasbor] == "rujukan"` (bersama `GET /api/entities`, pola yang sama: isi
   disaring izin di handler). Kalimat komentar disesuaikan menjadi "diberi izin".
2. **`config/values/cancel-scheduled` tidak memakai `require_any_permission`**: wewenang ubah pengaturan di router ini
   adalah `_may_edit` (Admin selalu boleh + izin `entry.permission`, KF-T1). Gerbang pertama memakai predikat yang sama
   atas seluruh registri (`_require_some_edit`), supaya aturan Admin tidak bergeser. Akibatnya penjaga sapuan membaca
   penolakan ini lewat kalimat Z6 saja (tanpa `x.y`), seperti 35 penolakan pemeriksa-matriks-sendiri lain yang dicatat PR-T8.
3. **Kalimat Z6 juga untuk pemeriksaan kedua** (ap-payments per jenis, `_line_actor`, return, approve): arahan menyebut
   pesan Z6 untuk gerbang yang dipindah; pemeriksaan kedua di handler yang sama ikut diubah supaya satu rute tidak memberi
   dua gaya pesan. Izin yang diperiksa tidak berubah.
4. **`scripts/guardrails/verify_permission_checked.py`**: satu entri DINAMIS dicabut atas permintaan penjaga itu sendiri
   (lihat Kelompok B). Ini mengetatkan, bukan melonggarkan: pasangan itu kini wajib punya pemeriksa literal.

## Asumsi

- Kategori kelompok A mengikuti usulan laporan PR-T8 dan arahan sesi; `can-decide/me` = `milik_sendiri` (jalur `/me`,
  sesuai docstring `approval_policies.py:12`), `prices/access` = `sesi`.
- `initial_registration.py` (API opname awal gedung, PREP-B) bukan logika gerbang RFID (`gate_evaluator`,
  `rfid_ingest_service`, `rfid_service`) maupun `middleware/`; hanya urutan pemeriksaan izin dan teks pesan yang diubah.
  Rute HP/handheld lain di berkas itu tidak disentuh (H7).

## Keterbatasan / yang belum diuji

- Lapis A (MongoDB asli) tidak dijalankan untuk unit ini; semua uji di lingkungan B (mongomock). Tidak ada butir
  "bersamaan/indeks" di unit ini.
- Kelompok A sengaja tidak diubah: slip gaji dan batal cuti masih memuat dokumen sebelum menilai pemilik/izin, sehingga
  pengguna **bersesi** tanpa hak masih bisa membedakan id ada (403) dan tidak ada (404). Tanpa sesi tetap 401. Bila
  reviewer menilai ini perlu ditutup, obatnya pola gerbang pertama yang sama (perlu putusan: pemilik slip tanpa izin apa pun
  harus tetap lolos).
- Layar belum diuji jalan di peramban (tidak ada berkas layar berubah).

## Hambatan lingkungan

- `python -m pytest backend/tests_mem -q` **dari root repo** mengumpulkan 0 uji (exit 5) — di kode lama maupun baru
  (`backend/pytest.ini` memasang `-n 2`; pekerja xdist tidak menemukan jalur). Suite dijalankan dari `backend/`
  (`python -m pytest tests_mem -q`); README `tests_mem` menyebut `-n 0` dari root (tidak dicoba di sesi ini).
- Skrip gate memakai jalur `/app/...`: dibuat tautan `/app` → salinan yang diuji (`03_LINGKUNGAN_UJI.md` §1); kini
  menunjuk ke repo.
- Lingkungan A (Docker + MongoDB) tidak tersedia di sesi ini: `gate.sh --quick` dijalankan di lingkungan B (venv Python
  3.11 + mongomock, `/app` → salinan kerja), sebelum dan sesudah di mesin yang sama. Angka FAIL berbeda dari angka
  lingkungan A di laporan PR-T8 (14) karena lingkungan, bukan karena unit ini — pembanding yang sah adalah kolom
  "sebelum" di mesin yang sama.

## Titik henti

- H7: `middleware/`, `rfid*`, `handheld*`, gerbang RFID tidak disentuh. H3: tidak ada data nyata; sapuan dan uji hanya di
  database tiruan.

## Yang perlu direview

- Kategori enam entri `LOGIN_ONLY` (terutama dasbor = `rujukan`) dan perubahan harapan PR-T3 U13 (Menyimpang 1).
- Gerbang `config/values/cancel-scheduled` lewat `_may_edit` atas seluruh registri, bukan `require_any_permission`
  (Menyimpang 2).
- Keterbatasan slip gaji / batal cuti (oracle id untuk pengguna bersesi).

Status: implemented_pending_review
