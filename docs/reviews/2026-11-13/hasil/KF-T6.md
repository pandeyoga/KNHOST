# KF-T6 — Kontrol "harus dua orang" yang bisa diatur per PT

- Commit awal: `2965eb5` (dikerjakan) · digabung di atas `783e67e` (sesudah PR-T2)        - Commit akhir: `a053a94` (a) · `4844181` (b)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-05, GL-06
- Risiko tinggi → dua serah-terima (`00_ATURAN_EKSEKUSI.md` §8): (a) jalur baru + uji, titik lama belum disentuh;
  (b) pengalihan 35 aksi + migrasi sakelar + buka kembali/jurnal manual dua orang. SHA (a) `a053a94`, (b) `4844181`.

## Penggabungan dengan PR-T2

Unit dikerjakan di atas `2965eb5`; sementara itu PR-T2 (`45a9d73`, `653e87e`) masuk. Penggabungan tiga arah per berkas
(basis = `2965eb5` untuk (a), keadaan (a) untuk (b)). Konflik dan penyelesaiannya:

| Berkas | Konflik | Penyelesaian |
|---|---|---|
| `backend/routers/closing.py` | PR-T2 mengganti cek nama peran admin di buka kembali dengan izin `accounting.reopen`; KF-T6 menambah jalur dua orang di fungsi yang sama | Keduanya: izin `accounting.reopen` (PR-T2) diperiksa dulu, lalu `_reopen_dua_orang` (KF-T6). Impor digabung |
| `backend/tests_mem/test_KFT1_izin_pengaturan.py` | PR-T2 (229 = 232 − 3) dan PK-46 (`310 + 5`) mengubah angka yang sama | `229 + KFT6_KUNCI − KFT6_TIDAK_DIPAKAI` dan `310 + 5 + KFT6_KUNCI`, alasan tertulis |
| `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | PR-T2 menambah §9.1 tepat di tempat KF-T6 menambah baris tabel §9 | Baris KF-T6 masuk tabel §9; §9.1 PR-T2 tetap di bawahnya |

Berkas lain yang juga disentuh PR-T2 (`access_modules.py`, `bootstrap.py`, `config_registry.py`, `crm.py`,
`price_approvals.py`, `sales_returns.py`, `transfers.py`, `hr_payroll_service.py`, `ENTITY_REGISTRY.md`, `PRD.md`)
tergabung otomatis. Fixture akses frontend dan `CODEBASE_MAP.md` dibangkitkan ulang sesudah tiap tahap. Tidak ada
cek nama peran baru yang tertinggal: satu-satunya rujukan "Admin" tetap `approval_matrix_service.is_admin` (definisi
lama, dipakai di satu tempat `dual_control._is_admin`), sesuai catatan Asumsi.

## Cek ulang "Keadaan sekarang" (dibaca di `2965eb5`; blueprint di `3132cc4`)

| Butir | Hasil |
|---|---|
| Sakelar `approval.matrix_sod` | Berlaku; bergeser `config_catalog_approval_matrix.py:62` (bukan 63). Dibaca `approval_matrix_service.py:196` `sod_blocked` dan `:256` (di dalam `evaluate`) |
| Sakelar `amendment.dual_control` | Berlaku, `config_catalog_finance.py:55`; dibaca `amendment_service.policy_snapshot` + `decide` (`:736`) |
| `admin_override` (`:181`), `is_requester` (`:132`) | Berlaku |
| Tabel A (8 jangkar) | Berlaku di baris yang sama (`rnd.py:291/316/719`, `special_orders.py:1050/1139`, `purchase_requisitions.py:188` (+ `:210` tolak), `purchase_requisition_service.py:336`, `price_approvals.py:382/475`, `so_approvals.py:302`); amandemen bergeser ke `amendment_service.py:736` |
| Tabel B (12) | Berlaku; bergeser: `purchase_orders.py:820` (tingkat berikut `:843`), `vendor_bills.py:464`, `contra_bon_service.py:1015` (kini lewat `admin_override`, bukan pembanding `created_by_id` polos), `interco_return_service.py:435`, `period_unlock_service.py:198`. Lainnya sama baris |
| Tabel C (17 aksi, 19 jangkar) | Berlaku (tanpa pemeriksaan); bergeser: `crm.py:147`, `hr_payroll_service.py:485` (`submit_run` `:469`), `penalty_service.py:445`, `gl_service.py:688` (`posted` baris 742), `gl.py:160`. **Beda dari blueprint:** `sales_returns`/`purchase_returns`/`cuti`/`gaji` dsb. — fungsi layanan retur menerima NAMA, bukan aktor (dipasang di router); `price_approvals.requested_by` berisi **id akun** (bukan `requested_by_id`); `crm.decide_credit_override` memakai `require_role(["manager"])` |
| GL-06 buka kembali (`closing.py:105`) / jurnal manual langsung `posted` | Berlaku |
| Lampiran C.1: klaim makloon tidak lewat `guard` | Benar — masuk tabel C |

## Pembagian serah-terima

**(a) jalur baru, titik lama belum disentuh** — perilaku aplikasi tidak berubah (semua titik lama tetap memakai
`admin_override`/`sod_blocked`/pembanding sendiri).

| Berkas | Isi |
|---|---|
| `backend/config_catalog_kontrol.py` (baru) | `KONTROL_AKSI` (35 aksi: aksi, label, kelompok A/B/C, awal, punya_nominal, bagian layar) → 35 `kontrol.<aksi>.min_orang` + 20 `kontrol.<aksi>.batas_nominal` + `kontrol.admin_boleh_sendiri` + `kontrol.admin_tetap_dua_orang` (57 kunci, grup `persetujuan`, lapisan grup+PT, izin `settings.manage`, risiko tinggi/wajib alasan). Di (a) `consumers` = `services/dual_control.py:butuh_orang_kedua` saja |
| `backend/services/dual_control.py` (baru) | `butuh_orang_kedua`, `pelaku_sama`, `periksa` (tanpa efek), `tolak_bila_pelaku_sama` (403 + jejak `approval_matrix_log` "diputuskan sendiri oleh admin"), `aturan(entity_id)` untuk layar |
| `backend/routers/kontrol.py` (baru) + `server.py` (1 baris) | `GET /api/kontrol/aturan?entity_id=` (izin `settings.view`, pesan Z6) → `rows`, admin, `can_edit` |
| `backend/config_registry.py` | impor katalog (1 baris, blok `KF-T6`) |
| `backend/access_modules.py` | blok `KF-T6`: `settings-dual-control` ke `nav` modul `admin`; `VIEW_RESOURCE_OVERRIDES["settings-dual-control"] = ["settings"]` |
| `frontend/src/features/settings/kontrol/DualControlView.jsx` (baru) | Tab ke-4 Pengaturan › Persetujuan: Berlaku untuk (Semua PT/PT), tabel per kelompok (Jumlah orang · Dua orang di atas (Rp) · Sumber), pengecualian Admin, Tim kecil (alasan wajib), Simpan (alasan wajib, mati sampai ada perubahan), memuat/galat+coba lagi/hanya-baca |
| `frontend/src/{AppViewRouter.jsx, appViewImports.js, config/hubTabs.js, config/navMeta.js}` | tab + rute |
| `frontend/src/features/settings/config/configGroupViews.js`, `cfg/SettingsGroupView.jsx` | `excludeKeys: ["kontrol."]` + tautan di "Persetujuan & Ambang"; deep link `kontrol.*` → tab baru |
| Fixture akses frontend (`access_*_fixture.json`), `navAccess.test.js`, `roleReach.test.js` | dibangkitkan ulang / penambahan jangkauan tercatat (`KFT6_DUAL_CONTROL`) |
| `backend/tests_mem/test_KFT6_kontrol.py`, `test_KFT1_izin_pengaturan.py` (U02/U04: `+ KFT6_KUNCI`) | uji (a) |
| `frontend/src/features/__tests__/kft6DualControl.test.js` | uji layar |

**(b) pengalihan + pematian jalur lama**

| Berkas | Isi |
|---|---|
| `services/approval_matrix_service.py` | `admin_override` & `sod_blocked` **dihapus** (0 pemanggil tersisa, dibuktikan U15 + grep); `evaluate` tidak lagi menilai pemisahan tugas; `guard` memanggil pembantu dengan `STAGE_AKSI` (design_acc→acc_desain, sample_acc→acc_sample, po_custom, purchase_request→permintaan_pembelian; juga saat menolak, seperti dulu); `settings()["sod"]` = alias dari `butuh_orang_kedua`; antrean "Persetujuan Saya" memakai `periksa` (tombol mati + alasan) |
| `config_catalog_approval_matrix.py`, `config_catalog_finance.py` | dua sakelar lama → `not_used` ("Dipindahkan ke Pengaturan › Persetujuan › Kontrol dua orang.") |
| `services/dual_control.py` (bagian akhir) + `bootstrap.py` (2 baris) | `migrasi_sakelar_lama()` sekali jalan (penanda `__migrations__.kft6_kontrol`) |
| `config_catalog_kontrol.py` (`_TITIK`) | titik pasang tiap aksi → `consumers`; `services/config_health.py`: keluarga `kontrol.*` dikenali dari literal nama aksi |
| Tabel A: `amendment_service.py` (`policy_snapshot["dual_control"]` alias + `decide`), `purchase_requisition_service.py`, `price_approvals.py`, `so_approvals.py` | pembantu |
| Tabel B (11 berkas): `purchase_orders.py` (2 aksi), `vendor_bills.py`, `landed_cost.py`, `contra_bon_service.py`, `marketing_cost_service.py`, `interco_return_service.py`, `period_unlock_service.py`, `makloon_loss_service.py`, `return_exception_service.py`, `design_ownership_service.py`, `initial_registration_service.py` | pembanding lama + `admin_override` diganti satu panggilan; semua 403 (dulu sebagian 400) |
| Tabel C: `transfers.py`, `cycle_count.py`, `sales_returns.py`, `purchase_returns.py`, `hr_leave_service.py` (cuti, lembur, `akun_karyawan`), `hr_payroll_service.py`, `cash_advance_service.py` (2), `penalty_service.py`, `payment_variance_service.py` (2) + `routers/payment_variance.py`, `crm.py`, `makloon_orders.py` (+ `makloon_claim_service.py`), `internal_request_service.py`, `design_request_service.py`, `sales_orders_extra.py` | panggilan baru sesudah izin+status; titik pengajuan mulai menyimpan id (`requested_by_id`, `submitted_by_id`, `created_by_id`, `proposed_by_id`) |
| `routers/closing.py` | buka kembali dua orang: 202 + `reopen_request`, pengaju sama 403, orang kedua menjalankan, `reopen_request` dihapus |
| `services/journal_proposal_service.py` (baru), `routers/gl.py`, `services/gl_service.py` (`create_manual_entry(hanya_periksa=, disetujui=)`) | jurnal manual dua orang: 202 usulan, `GET /api/gl/journal-proposals`, `…/approve`, `…/reject` |
| `entity_scope.py`, `indexes.py`, `services/export_registry_more.py`, `scripts/verify_contract.py` | `journal_proposals` SCOPED, indeks (`uq_id`, antrean), dataset Pusat Export, koleksi kanonik |
| `scripts/verify_data_integrity.py` | INV-CLS-02 & INV-AMD-02 membaca potret `kontrol_dua_orang` (setuju-sendiri sah bila aturannya satu orang) |
| `test_g1_amendment_poc.py`, `test_g7_contrabon_poc.py` (lapis A) | kunci/pesan baru |
| Layar: `features/finance/JournalProposalsPanel.jsx` (baru), `GeneralLedger.jsx`, `JournalEntryModal.jsx`, `ClosingView.jsx` | pita + saringan "Menunggu persetujuan" (FilterChips) + Setujui (konfirmasi nominal+PT, `moneyPost`+`useIntentKey`) / Tolak (alasan); 202 ditangani; label "Menunggu orang kedua — diajukan {nama}" |
| Uji: `tests_mem/test_KFT6_pengalihan.py`, `test_KFT6_tabel_c.py`, `tests/test_bp_KFT6_dua_orang_mongo.py`, `features/__tests__/kft6JurnalDuaOrang.test.js`; `test_KFT1` U02 `− KFT6_TIDAK_DIPAKAI` | |
| Dokumen | `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md` (generator), `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` |

Hijau di kedua keadaan. Di salinan kerja (basis `2965eb5`): (a) saja → `tests_mem` 293 lulus / 3 xfail, (a)+(b) → 319 / 3.
Sesudah digabung di atas `783e67e`: HEAD 315 lulus / 2 dilewati / 3 xfail → (a) `a053a94` 325 / 2 / 3 → (b) `4844181`
351 / 2 / 3. Pada (a): `verify_auth_coverage` dan `verify_ui_standard` keluaran identik dengan `783e67e`;
`verify_codebase_map`, `verify_access_catalog_nav` PASS/0.

## Uji penerimaan

| ID | Lapis | Merah di kode lama | Hasil |
|---|---|---|---|
| U1 | B | ya (modul tidak ada) | Lulus — `True`, `False`, `False`; aksi tak dikenal `KeyError` |
| U2 | B | ya (pesan "Pemisahan tugas (SoD)…", ent_ksc tetap 403) | Lulus — 403 pesan dua orang; `ent_ksc` 200, `ent_kanda` 403 |
| U3 | B | ya (6 jt 200) | Lulus — pembantu: 4 jt/5 jt tidak, 6 jt ya; HTTP: 200 / 403 / orang kedua 200 |
| U4 | B | ya (outcome "disetujui sendiri oleh admin (lewati…)", lalu 200) | Lulus — 200 + 1 baris `approval_matrix_log` "diputuskan sendiri oleh admin"; lalu 403 |
| U5 | B | ya (400) | Lulus — 403; daftar dikosongkan → 200 |
| U6 | B | ya (400 "Kontrol ganda") | Lulus — 200 (bawaan satu orang); 403; orang kedua 200 |
| U7 | B | ya (403 kedua = 200) | Lulus — 200; 403; 200 |
| U8 | B | ya (200) | Lulus — 403; 200 |
| U9 | B | ya (fungsi migrasi tidak ada) | Lulus — `ent_kanda` "1", `ent_ksc` "2"; kedua sakelar `not_used`; jalan kedua 0 baris baru |
| U10 | B | ya | Lulus — grup "1"; `policy_snapshot("ent_ksc")["dual_control"] is False` |
| U11 | B | ya (modul tidak ada) | Lulus — 200 (35 butir, satu alasan); semua aksi `ent_ksc` salah; `ent_kanda` `setujui_po` benar; layar sumber "entity" |
| U12 | B | ya (200 langsung) | Lulus — 202 & `closed`; 403; admin kedua 200, `reopened`, `reopen_request` hilang |
| U12 | A | — | Lulus (`tests/test_bp_KFT6_dua_orang_mongo.py::test_U12_buka_kembali_dua_admin`, MongoDB 7 asli, backend `4844181`) |
| U13 | B | ya (200 langsung `posted`) | Lulus — 202, `journal_entries` tetap, saldo tetap; 403; 200 (`created_by` mgr, `approved_by` mgr2), saldo kedua akun +1.000.000; ulang 409 "Usulan jurnal ini sudah diputuskan."; tolak tanpa alasan 400 |
| U13/U14 | A | — | Lulus (`::test_U13_U14_jurnal_manual`, lingkungan yang sama) |
| U14 | B | ya | Lulus — 5 jt langsung `posted`; 15 jt 202 usulan |
| U15 | statik | ya (11 berkas berisi pola lama) | Lulus — 0 pembanding lama di 11 berkas tabel B; 35/35 aksi punya titik pasang |
| U16 | B | ya (404) | Lulus — sopir 403/403 (pesan Z6, tanpa `settings.view`); peran lihat-saja `can_edit=false` |
| U17 | B | ya | Lulus — 57 kunci: tulis grup & PT terbaca, PT lain tetap, "3"/negatif/bukan-daftar/bukan-bool 400, tanpa alasan 400, maksimum 1 T |
| Tabel C (RISIKO) | B | ya (13/13) | Lulus — pengaju = pemutus → 403 saat 2 untuk 13 aksi (transfer, opname, retur jual/beli, lembur, LPJ, bebas denda, selisih kwitansi, lewat batas kredit, klaim makloon, permintaan internal/desain, nilai pesanan); 4 aksi C lain di U3/U7/U8/U12/U13 |
| U18 | layar | ya (komponen tidak ada) | Uji komponen jest 6/6 + 4/4 (jurnal & tutup buku). **Uji jalan peramban belum dilakukan** |

Bukti: `bukti/KF-T6/` — `tests_mem_KFT6_merah_kode_HEAD.log` (36 gagal di kode HEAD), `tests_mem_KFT6_a_merah_kode_HEAD.log`,
`tests_mem_KFT6_b_merah_keadaan_a.log` (26 gagal: titik HEAD + jalur baru), `tests_mem_sebelum_sesudah.log`,
`jest_KFT6.log`, `penjaga_statik.log`, `contoh_jurnal_U13.log`.

`backend/tests_mem` seluruhnya: di salinan kerja **283 lulus + 3 xfail → 319 lulus + 3 xfail** (36 uji baru); sesudah
digabung **315 → 351 lulus** (2 dilewati H4, 3 xfail). Lapis A: `tests/test_bp_KFT6_dua_orang_mongo.py` 2 lulus.

## Contoh jurnal → saldo (U13, `00` §9)

`bukti/KF-T6/contoh_jurnal_U13.log` (database tiruan, PT `ent_ksc`, `kontrol.jurnal_manual.min_orang = 2`):
usulan "Setoran modal" Rp 1.000.000 → 202, 0 jurnal, saldo tetap. Pengusul menyetujui → 403. Orang kedua menyetujui →
jurnal `KSC/JE-00005` `posted`: D 1-1100 Kas Besar / Bank 1.000.000 · K 3-1000 Modal Disetor 1.000.000. Saldo 1-1100
100.000.000 → 101.000.000 (+1.000.000, saldo normal debit); 3-1000 100.000.000 → 101.000.000 (+1.000.000, saldo normal
kredit). Hitung tangan: D = K = 1.000.000; masing-masing akun bertambah sebesar barisnya.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `4844181`), sesudah `restore_demo` (data acuan; tiga skrip
seed yang sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 16 FAIL | 16 | 0 | 0 |
| `gate.sh --ci` | 43 FAIL | 43 | 0 | 0 |

POC lapis A yang diubah unit ini (`test_g1_amendment_poc.py`, `test_g7_contrabon_poc.py`) ikut di `--ci` dan tidak
menambah merah. Penjaga statik di salinan kerja (`bukti/KF-T6/penjaga_statik.log`): tidak ada yang bertambah merah
(verify_auth_coverage 28=28, verify_access_catalog_nav 0, verify_money_idempotency/verify_custom_modals/verify_error_notice
PASS, verify_ui_standard 23=23 baris identik, verify_list_export 0, verify_page_tabs 1=1, verify_to_list_bound 6=6,
audit_i18n_id 113=113, audit_create_modal 6=6, audit_config_wiring sama, config_health STALE 4=4, verify_codebase_map PASS).
Jest sesudah digabung: `src/config/__tests__` + `src/features/__tests__` 384/384 uji lulus; 33 suite gagal dimuat karena
`@radix-ui/primitive/is-development` tidak terpasang di lingkungan lokal (kendala lingkungan, sama di HEAD).

## Menyimpang dari blueprint

- `tolak_bila_pelaku_sama` mendapat argumen kata-kunci tambahan `kecualikan_admin=True`; buka kembali tutup buku
  memakai `False`: titik itu hanya untuk Admin, jadi pengecualian Admin bawaan ("ya") akan membuat aturan dua orang tidak
  pernah berlaku — U12 menuntut 403 untuk Admin yang sama. Fungsi `periksa(...)` (tanpa efek) ditambahkan untuk antrean.
- Penjaga di jalur yang keputusannya terjadi **sesudah uang bergerak** tidak melempar 403: `purchase_requisition_service`
  (persetujuan otomatis pemenuhan pesanan khusus menangkap `ValueError`), `payment_variance_service.decide_receipt`
  (saat kwitansi dibuat) dan `decide_bill` (saat bayar tagihan) melempar `ValueError/VarianceError` berpesan sama;
  pemanggilnya sudah mencatat kegagalan tanpa membatalkan uang. Jalur HTTP keputusan (guard PR, antrean selisih
  kwitansi `routers/payment_variance.py`) tetap 403.
- "Pengaju" yang tidak ada di dokumen: bebas denda = penerbit nota denda (`created_by`); selisih kwitansi = pencatat
  kwitansi; selisih bayar tagihan = pembuat tagihan (`created_by_id`); harga khusus = `requested_by` (berisi id akun);
  gaji = `submitted_by_id` (baru) atau nama; nominal gaji = `totals.net`.
- Pemeriksaan retur jual/beli dipasang di router (layanan hanya menerima nama). Retur beli hanya diperiksa untuk
  draf/menunggu (lanjutan jurnal gagal IX-17 bukan keputusan). Retur jual diperiksa sebelum syarat bukti foto.
- Amandemen: keputusan memakai aturan **saat diputus** (pembantu), bukan potret saat diusulkan; potret keputusan disimpan
  `doc_amendments.kontrol_dua_orang` dan INV-AMD-02 membacanya.
- Migrasi: lapisan PT hanya ditulis bila sakelar PT itu BERBEDA dari grup ("1" atau "2"), supaya PT yang mengikuti grup
  tetap mengikuti grup (tafsir "pada lapisan itu"); hasil U9/U10 sama.
- `kontrol.*` disembunyikan hanya di tab "Persetujuan & Ambang" (tempat kelompoknya), tidak di "Semua pengaturan"
  (komponen di sana hanya mendukung satu tautan pengecualian = komisi); deep link `kontrol.*` mendarat di tab baru.
- Tambahan yang tidak disebut spesifikasi tetapi dibutuhkan: `journal_proposals` didaftarkan SCOPED, indeks, dataset
  Pusat Export (penjaga G-UI-07), `verify_contract`; INV-CLS-02 menerima setuju-sendiri buka periode bila aturannya
  satu orang (potret `period_unlock_requests.kontrol_dua_orang`).
- `test_KFT1_izin_pengaturan.py` U02/U04: angka diubah sebagai konsekuensi kunci baru (`232 + 57 − 1`, `310 + 57`),
  ditulis eksplisit dengan alasan di berkas uji.

## Asumsi

- `ASUMSI` unit: empat titik † dipertahankan lewat `kontrol.admin_tetap_dua_orang`; mode `warn` dipindahkan sebagai "2";
  `pengurang_piutang` satu pasang kunci (batasnya diisi PK-38); buka kembali & jurnal manual pola "ajukan lalu dijalankan".
- "Admin" = definisi lama `approval_matrix_service.is_admin` (nama peran) — dipakai di satu tempat agar PR-T2 cukup
  mengganti satu fungsi. Tidak ada pemeriksaan nama peran baru di kode baru lainnya.
- Aturan lama "Hanya dokumen baru" (`approval.matrix_scope = new_only`) tidak lagi mengecualikan dokumen lama dari
  pengaju ≠ pemutus (pembantu berlaku untuk semua dokumen); masih berlaku untuk matriks peran.
- Perubahan perilaku yang disengaja (keputusan pemilik): buka periode kini bawaan **satu orang** (dulu selalu dua,
  kecuali Admin).

## Keterbatasan / belum teruji

- Uji jalan peramban (U18) belum dilakukan (hanya uji komponen jest).
- `decide_bill` (selisih bayar tagihan saat bayar) tidak punya uji 403-saat-2 (keputusannya di dalam alur bayar).
- Klaim jurnal usulan (`pending → posting`) memakai update bersyarat; balapan dua penyetuju belum teruji di MongoDB asli.
- Migrasi menulis data pengaturan saat proses awal — **tinjau sebelum rilis (H3)**. Membatalkan (b): kembalikan berkas
  (b); (a) tidak mengubah perilaku.

## Yang perlu direview

Bentuk `tolak_bila_pelaku_sama(kecualikan_admin=)`; pilihan "pengaju" pada aksi tabel C tanpa kolom pengaju; penjaga
non-403 di jalur sesudah uang bergerak; INV-CLS-02/INV-AMD-02 yang kini membaca potret aturan.

Status: implemented_pending_review.
