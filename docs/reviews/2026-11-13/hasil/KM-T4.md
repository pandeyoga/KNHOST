# KM-T4 — Sambungkan Lembar Insentif ke gaji dan buku besar; matikan komisi otomatis per PT

- Commit awal: `5410979` (worktree kerja, basis B)        - Commit akhir: (a) `b77dce8`, (b) `fee66fe`, cek layar & lapis A `d458cd5`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KM-07, PY-06 (spesifikasi `docs/blueprint/unit/KM-T4.md`; keputusan K-13, K-22, K-26)
- Risiko tinggi → dua serah-terima (`00` §8): **(a)** jalur baru (sakelar `sheet`, pembaca `commission_mode`, komponen
  `INSENTIF`, pengesahan bertahap + masukan gaji + jurnal lembar, Posting Gagal, pelunasan hutang di jurnal gaji, tanda
  bayar, tagihan antar-PT, INV-KM-4/5, endpoint kesiapan) — komisi otomatis belum disentuh; **(b)** pematian jalur lama per
  mode (`_commission_for` menghormati `off`/`sheet`, akrual manual memakai `sales_roster`, `incentive_unit` dicabut) +
  layar + lapis A U16 + uji layar.
- Salinan keadaan (a): `scratchpad/KM-T4_a_state/` (`FILES.txt` 25 berkas, `BASIS.txt` = `5410979`; berkas uji (a) memuat
  tiga tanda `xfail(strict)` menunggu (b)); (a) yang digabung ke HEAD tujuan: `scratchpad/KM-T4_a_merged/`.
- **Titik henti H5 dipatuhi:** sakelar dibangun dengan bawaan `accrue_then_settle` (perilaku hari ini); tidak ada nilai
  sakelar PT yang diubah di kode, seed, atau data. Pertanyaan pemilik di "Titik henti".

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`, diperiksa di `5410979`)

| Butir spesifikasi | Hasil di basis B |
|---|---|
| Akun insentif `gl_service.py:184` (`ACC_BEBAN_INSENTIF` 6-5000), `:185` (`ACC_HUTANG_INSENTIF` 2-1500); akrual `_balanced_pair` `:2919` | Berlaku — `:184`, `:185`; akrual `post_incentive_accrual` `:3495`, `_balanced_pair` `:3528`. Akun dipetakan lewat `gl_mapping_service.remap_lines` (`penjualan.beban_insentif` / `penjualan.hutang_insentif`) |
| Gaji memuat komisi mesin tanpa membaca mode `hr_payroll_service.py:245`; mode hanya disalin `:358` | Berlaku, bergeser — `_commission_for` `:318`; mode disalin `cfg.get("payroll_commission_mode", …)` `:649`, `:745` |
| Jurnal gaji dua cabang (`accrue_then_settle` → Dr hutang; lain → Dr beban) `gl_service.py:3078` — PY-06 | Berlaku, bergeser — `payroll_journal_lines` `:3704` (PY-T1 memindah jurnal ke komponen; cabang sama) |
| Pilihan terdaftar `config_catalog_ops.py:545`; bawaan `hr_service.py:46` | Berlaku, bergeser — `:761` (tiga pilihan, `scopes` global+PT, tanpa `requires_reason`); `hr_service.py:46` tetap |
| KM-07 akrual memakai peran persis `sales` `gl_service.py:2909`; gaji memakai peran acuan `hr_payroll_service.py:250` | **Sebagian bergeser** — PR-T4 sudah mengganti keduanya ke kategori kerja: akrual `roles_in_category("sales")` di seluruh grup `:3518`, gaji `category_of(role)` `:323`. Sisa KM-07: daftar akrual = semua akun sales grup, bukan sales PT itu → diganti `sales_roster` |
| `incentive_unit` disimpan `routers/incentive_rates.py:23`, mesin memakai `base_qty` `sales_force_service.py:361`; kunci `config_catalog_core.py:274` | Berlaku, bergeser — `:23` (+ isi bawaan dari pengaturan `:65`), `base_qty` `:365`, kunci `:386` |
| Satu akun → satu karyawan → satu PT `routers/hr.py:256`, `:305` | Berlaku (lembar membaca `hr_employees.user_id`, karyawan `status: active`) |
| Antar-PT non-dagang: `ACC_IC_AR` `:157`, `ACC_IC_AP` `:167`; `twin_je` `interco_money_service.py:108`; `twin_cash` `:70`; `non_trade_outstanding` `:146`; `sync_non_trade_elimination` `:163` | Berlaku, bergeser — `:157`/`:167`; `twin_je` `:116`, `twin_cash` `:76`, `non_trade_outstanding` `:154`, `sync_non_trade_elimination` `:171`. Pembantu jurnal kembar PK-06 = `services/twin_journal.py` (`preflight_twin`, `post_twin`) — dipakai unit ini |
| Dipakai dari unit lain: `enqueue_input`, `cancel_input`, komponen ber-`bucket` (PY-T1); `post_durable`, `posting_registry` (PK-18); `journal_date` (PK-22); `sales_roster` (KM-T1) | Ada semua (`hr_pay_inputs.py`, `hr_pay_components.py`, `gl_service.post_durable`, `posting_registry.KINDS`, `periodic_posting.journal_date`, `incentive_targets.sales_roster`) |
| (tambahan) `interco.view` / `interco.settle` dipakai pinjaman `routers/interco_loans.py:103` | Berlaku — `:105`. Tidak ada izin baru |
| (tambahan) Bootstrap menyalin karyawan seed per akun; uji memakai PT `ent_kanda`/`ent_ksc` | Karyawan seed di dua PT dinonaktifkan di fixture supaya jurnal gaji uji hanya memuat karyawan uji (lihat "Menyimpang" 5) |

## KM-07 — daftar sales akrual dan satuan insentif tidak cocok dengan mesin gaji

- Berlaku di HEAD: sebagian (akrual manual memakai semua akun berkategori sales di grup; `incentive_unit` diterima, disimpan,
  dan diisi dari pengaturan, padahal mesin mengalikan tarif dengan satuan dasar).
- Perubahan perilaku: akrual manual (`gl_service.post_incentive_accrual` tanpa `total`) menjumlah komisi daftar
  `incentive_targets.sales_roster(PT, "month", periode)` — daftar yang sama dengan Meja Insentif. `POST /api/incentive-rates`
  tidak lagi menerima `incentive_unit` (isian diabaikan), `GET`/`POST`/`PATCH` tidak mengirimnya (dokumen lama dibiarkan);
  `commission.incentive_unit` `status="not_used"` dengan alasan spesifikasi; layar tarif tanpa kolom & isian "Satuan" (tarif
  tampil "/satuan dasar"); dua pengecualian basi `config_fallback_allow.json` dihapus.

## PY-06 — nilai `off` berarti "beban saat gaji"; komisi otomatis tidak bisa dimatikan per PT

- Berlaku di HEAD: ya (`off` hanya mengubah cabang jurnal; mesin komisi tetap dipanggil `_commission_for`).
- Perubahan perilaku:
  - **Sakelar** `hr.payroll_commission_mode` (spesifikasi "Pengaturan"): pilihan + `sheet` "Dari Lembar Insentif yang
    disahkan", label/bantuan/dampak/contoh spesifikasi, `risk high`, `requires_reason True`, izin `hr.manage_payroll`,
    `consumers` `services/hr_payroll_service.py:commission_mode`. **Satu pembaca** `hr_payroll_service.commission_mode(PT)`
    (resolver global → PT; cadangan = bawaan registry) dipakai `_commission_for`, `_build_slips`/`create_run` (mode proses),
    `incentive_payroll.mode_pt` (pengesahan lembar, kesiapan, INV-KM-4).
  - `_commission_for` → 0 untuk `off` dan `sheet` (mesin tidak dipanggil). `POST /api/sales/incentive/post-gl` sudah 409
    untuk semua mode ≠ `accrue_then_settle` (PK-22) — berlaku untuk `off`/`sheet`.
  - **Pengesahan di PT bermode `sheet`** (`incentive_sheet_service.approve_sheet` → `services/incentive_payroll.py`):
    PERIKSA sesudah kontrol dua orang & Aturan Persetujuan (KM-T3): tiap sales tertaut karyawan aktif (400 pesan spesifikasi),
    komponen `INSENTIF` aktif di PT induk tiap karyawan (400), `journal_date = periodic_posting.journal_date(PT lembar, bulan
    terakhir periode dasar paling akhir)`, `preflight_posting` (409 pesan spesifikasi) → NIAT `submitted → approving`
    bersyarat `rev` (+ `journal_date`, pelaku, koreksi, jatah kerja 2 menit) → EFEK `enqueue_input` per baris bernominal
    (PT induk karyawan, label "{komponen} — {periode dasar}", `source_ref.charge_entity_id` = PT lembar) → JURNAL
    `post_durable(..., gl_service.post_incentive_sheet)` (Dr 6-5000 / Cr 2-1500 sebesar T; T < 0 dibalik; T = 0
    `not_required`) → SELESAI `approved`. Jurnal gagal → `approved` + `gl_status: failed`, Posting Gagal jenis
    `incentive_sheet` (ulang = masukan idempoten + jurnal sekali). Lembar `approving` yang jatahnya habis diteruskan Sahkan
    berikutnya; jatah masih berjalan → 409 "Lembar {nomor} sedang diproses. Muat ulang." PT lain: lembar = keputusan saja
    (`payroll_linked: false`, `gl_status: "not_required"`).
  - **Gaji**: komponen isi awal `INSENTIF` (pendapatan, masukan, kena pajak, kolom `commission`, proses reguler & susulan,
    `system`). Baris slip dari masukan lembar membawa `charge_entity_id`. `gl_service.payroll_journal_lines` memecah kolom
    komisi (`hr_pay_components.commission_parts`): baris lembar PT proses → Dr 2-1500 apa pun mode proses (bebannya sudah
    diakui saat lembar disahkan; negatif = kredit); baris lembar PT lain → Dr 1-1250 per PT tertagih (memo = nomor tagihan);
    sisanya (komisi mesin/masukan manual) cabang lama. Resep posting `posting_registry.post_payroll` mengakru hanya komisi
    non-lembar (tidak ada beban ganda). Sesudah proses `posted`: `incentive_payroll.tandai_dibayar` (baris lembar →
    `paid_run_id`/`paid_run_number`; semua baris bernominal terbayar → `paid`, pembaruan bersyarat `rev`); anulir proses →
    `lepas_dibayar` (lembar kembali `approved`; masukan dilepas PY-T1). Masukan yang datang sesudah proses reguler
    diposting menunggu proses susulan (perilaku PY-T1, tidak diubah).
  - **Sales di PT lain (K-26)** — `services/interco_charge_service.py`, koleksi `interco_charges` (`ICC-`): PERIKSA posting gaji
    PT penagih memeriksa pasangan PT aktif, periode & akun buku PT tertagih (`preflight_twin`); NIAT tagihan `pending` per
    (proses, PT tertagih), id turunan + indeks unik wajib `uq_charge_run_to`; sesudah jurnal gaji terbit → `open` + jurnal PT
    tertagih lewat `twin_journal.post_twin` (`interco_incentive_charge`, kunci = id tagihan): Dr 2-1500 / Cr 2-1250; saldo
    ikut `non_trade_outstanding` (+ `charge_outstanding`) dan eliminasi `sync_non_trade_elimination`. Pelunasan
    `POST /api/interco/charges/{id}/settle` (`interco.settle`, pelaku bertugas di PT tertagih): PERIKSA periode & rekening Bank
    kedua PT + `preflight_twin` → klaim `settle_status: settling` bersyarat sisa → `twin_cash` (keluar PT tertagih, masuk PT
    penagih) → `post_twin` (PT tertagih Dr 2-1250 / Cr kas; PT penagih Dr kas / Cr 1-1250) → sisa turun; 0 → `settled`.
    `GET /api/interco/charges[/{id}]` (`interco.view`). Anulir gaji PT penagih: tagihan yang sudah dilunasi → 409 pesan
    spesifikasi; selain itu jurnal PT tertagih dibalik (`reverse_document` lewat `post_durable`, `void_gl_status`) dan tagihan
    `cancelled`; batal proses (belum diposting) → tagihan `pending` `cancelled`. Posting Gagal jenis `interco_incentive_charge`.
  - **Invarian** di `scripts/verify_data_integrity.py` lapisan insentif: `INV-KM-4` (`incentive_payroll.cek_hutang_insentif`)
    dan `INV-KM-5` (`interco_charge_service.rekonsiliasi`), dengan bukti-merah di uji.
  - **Kesiapan** `GET /api/incentive/switch-readiness` (`incentive.configure`): `{mode, mode_label, checks, ready}` — empat
    butir spesifikasi. Hanya baca.
- Fixture disiapkan langsung vs proses dijalankan: karyawan, tarif & pesanan komisi mesin, periode tertutup, akun nonaktif
  disisipkan; sakelar lewat `config_resolver.set_value` (beralasan); lembar, gaji (buat/ajukan/sahkan/posting/anulir),
  Posting Gagal, pelunasan, pengaturan lewat HTTP.
- Status: implemented_pending_review

## Berkas

| Berkas | Isi |
|---|---|
| `backend/services/incentive_payroll.py` (baru) | PERIKSA/NIAT/EFEK/JURNAL/SELESAI pengesahan bertautan gaji, lanjutkan, ulang jurnal, tanda bayar/lepas, info layar, kesiapan, INV-KM-4 |
| `backend/services/interco_charge_service.py` (baru), `backend/routers/interco_charges.py` (baru), `backend/server.py` | Tagihan insentif antar-PT: rencana, periksa, niat, terbit, pelunasan, anulir, ulang, daftar, INV-KM-5 |
| `backend/services/incentive_sheet_service.py` | `approve_sheet` bercabang menurut sakelar; status `approving`; pesan "sedang diproses" |
| `backend/services/hr_payroll_service.py` | `commission_mode`, `_commission_for` (b), mode proses dari pembaca tunggal, kait posting/anulir/batal |
| `backend/services/gl_service.py` | `post_incentive_sheet`; `payroll_journal_lines` memecah komisi (lembar PT sendiri / PT lain / lainnya), negatif; akrual manual memakai `sales_roster` (b) |
| `backend/services/hr_pay_components.py` | komponen `INSENTIF`; `input_line` membawa `charge_entity_id` & rujukan lembar; `commission_parts` |
| `backend/services/posting_registry.py` | jenis `incentive_sheet`, `interco_incentive_charge`; akrual saat posting tanpa baris lembar |
| `backend/services/interco_money_service.py` | `non_trade_outstanding` + tagihan |
| `backend/routers/incentive.py` | `GET /switch-readiness`; `payroll` pada rincian lembar |
| `backend/routers/incentive_rates.py`, `backend/config_catalog_core.py` (b) | `incentive_unit` dicabut dari API; kunci `not_used` |
| `backend/config_catalog_ops.py` | kunci sakelar (spesifikasi) |
| `backend/indexes.py`, `backend/entity_scope.py`, `backend/doc_number_kinds.py`, `scripts/verify_contract.py` | indeks kerja + `uq_id` + unik wajib `uq_charge_run_to` + unik `number`; SCOPED; jenis nomor `icc`; koleksi kanonik |
| `scripts/verify_data_integrity.py` | INV-KM-4, INV-KM-5 |
| `scripts/guardrails/config_fallback_allow.json` | tiga pengecualian basi dihapus (kode yang dirujuknya diganti pembaca tunggal / dicabut) |
| `frontend/src/features/incentive/IncentiveSheetDetail.jsx` | bilah Jurnal + Lihat jurnal, "Dibayar lewat …", pita, konfirmasi Sahkan bergaji, "Lanjutkan pengesahan" |
| `frontend/src/features/incentive/IncentiveSetupView.jsx` | kartu Kesiapan beralih |
| `frontend/src/features/finance/interco/IntercoChargesPanel.jsx` (baru), `IntercoView.jsx` | daftar tagihan + pop-up Catat pelunasan (tab Pinjaman Antar-PT); fokus `interco_charge` |
| `frontend/src/features/crm/IncentiveRatesEditor.jsx`, `features/settings/masters/masterFieldsConfig.js` (b) | tanpa Satuan |
| `frontend/src/features/finance/glSourceLabels.js` | label sumber jurnal baru |
| Dibangkitkan | `CODEBASE_MAP.md`, `frontend/src/features/settings/config/configKeyIndex.json` |
| Uji baru | `backend/tests_mem/test_KMT4_insentif_gaji.py` (19), `backend/tests/test_bp_KMT4_sahkan_bersamaan_mongo.py` (lapis A U16, ditulis), `frontend/src/features/__tests__/kmt4LembarGaji.test.js` (6) |
| Dokumen | `ENTITY_REGISTRY.md` (baris ringkas + §KM-T4), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.32 |

## Uji penerimaan

"Merah lama" = berkas uji dijalankan di B dengan dua layanan baru disingkirkan (`bukti/KM-T4/merah_kode_lama.txt`,
`merah_kode_lama_sebab.txt`): fixture gagal 16× `pilihan 'sheet' tidak dikenal` (fitur belum ada), U15 gagal pada pilihan.
Uji (b) dijalankan juga di kode (a) (`bukti/KM-T4/b_merah_di_kode_a.txt`): U2 mesin dipanggil 2×, U7 `off` masih 500.000, uji
satuan `status` masih `active`. Jest: `bukti/KM-T4/jest_merah_kode_lama.txt` (`Cannot find module …IntercoChargesPanel`).

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah | lulus — jurnal `incentive_sheet` 2026-10-31 Dr 6-5000 / Cr 2-1500 8.500.000, `gl_status` `posted`, tiga masukan `approved` 2026-11 berlabel spesifikasi, `charge_entity_id` = `ent_kanda` |
| U2 | B | merah (a: mesin dipanggil) | lulus — pratinjau proses reguler (jalur `_build_slips`, slip proses yang dibuat diperiksa lagi di U3): mesin 0 kali dipanggil; Andi 2 baris insentif, komisi 5.000.000, bruto 10.000.000, PPh 21 200.000 (2 % lewat `ter_rate`), bersih 9.800.000; Budi 8.500.000 / 127.500 (1,5 %) / 8.372.500 |
| U3 | B | merah | lulus — Dr 6-1000 10.000.000; Dr 2-1500 8.500.000; Cr 2-1600 18.172.500; Cr 2-1800 327.500; 0 jurnal `incentive_accrual`; saldo 2-1500 0; L1 `paid`, tiap baris `paid_run_id` + nomor |
| U4 | B | merah | lulus — sebelum: saldo 8.500.000 = Σ baris 8.500.000; sesudah: 0 = 0; penjaga `layer_incentive_invariants` PASS INV-KM-4; bukti-merah (baris ditandai dibayar tanpa jurnal gaji) → FAIL |
| U5 | B | merah | lulus dengan angka terkoreksi (lihat "Uji spesifikasi keliru") — jurnal L2 Dr 2-1500 / Cr 6-5000 500.000; slip Andi komisi −500.000, bruto 4.500.000, **PPh 21 −200.000, bersih 4.700.000**; jurnal gaji memuat Cr 2-1500 500.000; saldo 2-1500 0 |
| U6 | B | merah | lulus — `approved`, `payroll_linked` salah, `not_required`, 0 jurnal, 0 masukan |
| U7 | B | merah (a: `off` masih 500.000) | lulus — `ent_ksc` bawaan: komisi 500.000; `off`: 0 |
| U8 | B | merah | lulus — 400 pesan spesifikasi ("Eko belum tertaut …"); tetap `submitted`; 0 masukan, 0 jurnal; + komponen `INSENTIF` nonaktif → 400 "Komponen gaji Insentif belum aktif di …" |
| U9 | B | merah | lulus — 6-5000 nonaktif: `approved`, `failed` (galat menyebut 6-5000), tiga masukan, 0 jurnal; tampil di Posting Gagal; ulang → 1 jurnal, tetap tiga masukan; ulang kedua 404 |
| U10 | B | merah | lulus — 409 "Periode Oktober 2026 sudah ditutup, …"; tetap `submitted`; 0 masukan |
| U11 | B | merah | lulus — masukan kembali `approved`; L1 `approved` tanpa `paid_run_id`; saldo 2-1500 kredit 8.500.000 |
| U12 | B | merah | lulus — jurnal `ent_kanda` Dr 6-5000 / Cr 2-1500 2.000.000; masukan `ent_ksc`; jurnal gaji `ent_ksc` Dr 6-1000 10.000.000 + Dr 1-1250 2.000.000 = Cr 2-1600 11.912.500 + Cr 2-1800 87.500 (tanpa 2-1500); jurnal `ent_kanda` Dr 2-1500 / Cr 2-1250 2.000.000; satu tagihan `open` 2.000.000 (memo baris 1-1250 = nomornya); Δ saldo 2-1500 `ent_kanda` 0; saldo non-dagang + eliminasi; **tambahan**: anulir → jurnal tertagih dibalik, tagihan `cancelled`, eliminasi hilang, lembar `approved`; proses baru → tagihan baru |
| U13 | B | merah | lulus — kas keluar `ent_kanda` / masuk `ent_ksc` 2.000.000; saldo 1-1250 & 2-1250 0; `settled`; INV-KM-5 PASS; anulir sesudah lunas 409 pesan spesifikasi; lunas lagi 409; bukti-merah (sisa diubah tanpa jurnal) → FAIL |
| U14 | B | merah | lulus — 409; 0 jurnal `incentive_accrual` |
| U15 | B | merah | lulus — atribut kunci spesifikasi; putaran `t1_config` (`test_KFT8_putaran_pengaturan.putaran`) 0 kegagalan; tanpa alasan 400; peran Tanpa Acuan `settings.view/manage` tanpa `hr.manage_payroll` 403 |
| U16 | A | — | **ditulis, belum teruji** di MongoDB asli — `backend/tests/test_bp_KMT4_sahkan_bersamaan_mongo.py` (3 putaran [200, 409], 1 jurnal, 1 masukan; indeks wajib). Pengganti lapis B: `asyncio.gather` dua Sahkan → [200, 409], 1 jurnal, 1 masukan; NIAT `approving` berjatah habis diteruskan Sahkan berikutnya tanpa dobel |
| U17 | layar | merah (komponen belum ada) | jest pengganti `kmt4LembarGaji` 6/6: konfirmasi Sahkan menyebut beban, tanggal jurnal, 3 baris, bulan gaji; lembar dibayar → "Dibayarkan", "Dibayar lewat KANDA/PAY-00007", "Lihat jurnal" membuka Buku Besar; pita PT belum dialihkan. **Belum diuji jalan** di peramban |
| (b) satuan | B | merah (a) | lulus — kunci `not_used` + alasan; `POST` dengan `incentive_unit` → tidak tersimpan, tidak dikirim; `GET` tanpa `incentive_unit` |
| (kesiapan) | B | merah | lulus — mode & label; empat butir; saldo hutang `ent_kanda` "Rp 12.500.000" (8,5 + 3 + 0,4 + 0,6 jt belum dibayar); tautan karyawan "Eko"; Manajer Kosong 403 |

### Contoh angka U1 → U3 (lembar → jurnal → slip → saldo 2-1500; hitung tangan)

| Langkah | Dokumen / jurnal | 2-1500 `ent_kanda` (kredit) |
|---|---|---|
| L1 disahkan 5 Nov 2026 | Andi BLN 2.000.000 + Andi TW 3.000.000 + Budi BLN 3.500.000 = T 8.500.000 → jurnal `incentive_sheet` bertanggal 31 Okt 2026 (bulan terakhir periode dasar: Okt 2026 vs Triwulan III = Sep 2026): Dr 6-5000 8.500.000 / Cr 2-1500 8.500.000; tiga masukan gaji 2026-11 | 8.500.000 |
| Slip Nov 2026 | Andi: 5.000.000 + 2.000.000 + 3.000.000 = 10.000.000 × TER A 2 % = 200.000 → bersih 9.800.000. Budi: 5.000.000 + 3.500.000 = 8.500.000 × 1,5 % = 127.500 → 8.372.500. Komisi mesin (1.000 m × 500 = 500.000) tidak dimuat | — |
| Posting gaji (jurnal 30 Nov 2026) | Dr 6-1000 10.000.000 + Dr 2-1500 8.500.000 = 18.500.000 = Cr 2-1600 18.172.500 + Cr 2-1800 327.500 | 8.500.000 − 8.500.000 = **0** |
| INV-KM-4 | sebelum posting 8.500.000 = Σ baris belum dibayar 8.500.000; sesudah 0 = 0 | |

Log: `bukti/KM-T4/tests_mem_KMT4_a_hijau.txt` (15 lulus + 3 xfail menunggu b), `tests_mem_KMT4_b_hijau.txt` (19 lulus),
`b_merah_di_kode_a.txt`, `merah_kode_lama*.txt`, `jest_merah_kode_lama.txt`, `jest_ringkas.txt`, `tests_mem_ringkas.txt`,
`penjaga_sebelum_sesudah.txt`, `gabung_T_2bb1a76.txt`, `gabung_daftar_berkas.txt`.

## Uji spesifikasi keliru (usulan koreksi, `00` §4)

**U5** — Desember adalah masa pajak terakhir (`_is_final_tax_period`: PPh 21 dihitung ulang setahun, pasal 17), bukan TER.
Hitung tangan Andi: bruto setahun 10.000.000 (Nov) + 4.500.000 (Des) = 14.500.000; biaya jabatan min(5 % × 14.500.000 =
725.000; 500.000 × 2 bulan = 1.000.000) = 725.000; neto 13.775.000 < PTKP TK0 54.000.000 → PKP 0 → PPh setahun 0; sudah dipotong
200.000 → PPh 21 Desember **−200.000** (lebih potong dikembalikan lewat slip, perilaku HR-01), bersih **4.700.000**. Jurnal gaji
Desember: Dr 6-1000 10.000.000 + Dr 2-1800 327.500 = Cr 2-1500 500.000 + Cr 2-1600 9.827.500. Teks pengganti kolom "Hasil" U5:
"Jurnal L2: Dr 2-1500 500.000 / Cr 6-5000 500.000. Slip Andi: `commission` −500.000, `gross` 4.500.000, `pph21` −200.000
(Desember = hitung ulang setahun: PKP 0, potongan November 200.000 dikembalikan), `net` 4.700.000. Jurnal gaji memuat Cr 2-1500
500.000; saldo 2-1500 kembali 0". (Alternatif bila ingin `pph21` 0: periode bayar L2 2027-01 — tetapi bukan masa terakhir.)

## Uji lama yang disesuaikan (angka/contoh, bukan harapan dilonggarkan)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_PK14_indeks_wajib.py`, `tests/test_bp_PK14_indeks_wajib.py` (lapis A, ditulis) | `KMT4_INDEKS = 1`; 37 → 38 | indeks unik wajib `interco_charges.uq_charge_run_to` |
| `tests_mem/test_KPT5a_setara.py` | `AWALAN_SESUDAH_KPT5` + `ICC-` | deret nomor baru per PT |
| `tests_mem/test_KPT5b_pengaturan.py` (U14, daftar lengkap) | jenis nomor `… + 1` | jenis `icc` tampil di tabel Penomoran Dokumen |
| `tests_mem/test_KFT1_izin_pengaturan.py` (U02) | `KMT4_TIDAK_DIPAKAI = 1` (dikurangkan) | `commission.incentive_unit` `not_used` → tidak bisa diubah pemegang `settings.manage`; katalog (U04) tetap |
| `tests_mem/test_KFT4_registry.py` (U2 potret) | `BERUBAH_SESUDAH` + `commission.incentive_unit {status}`; `PILIHAN_TAMBAH_SESUDAH` `hr.payroll_commission_mode` + `sheet` | spesifikasi menambah pilihan dan menandai kunci tidak dipakai |

## Cek layar

Dari kode (integrator memotret 1280/1024/390 px; kartu ±1018 px di 1280, ±760 px di 1024; pop-up `xl` ±990 px).

| # | Butir | Rincian lembar (pop-up) | Kartu Kesiapan (Target & Aturan) | Tagihan insentif antar-PT (Antar-PT › Pinjaman) | Tarif komisi |
|---|---|---|---|---|---|
| 1 | Tabel lebih lebar dari kartu | Tabel tetap 8 kolom KM-T3; "Dibayar lewat …" baris kecil di sel Nominal (`text-fs-12`, bisa patah) | Tanpa tabel (daftar butir) | 7 kolom: Nomor ±104 · Dari PT ±70 · Kepada PT ±70 · Nominal ±64 · Sisa ±64 (tanpa "Rp", judul "Nominal (Rp)" dua baris `head-wrap`) · Status ±95 · Aksi ±125 = ±592 + bantalan 7 × 24 = ±760 di 1024 (nominal ≤ 9 digit); lebih → `overflow-x-auto`, kolom Aksi `col-sticky-end` | Satu kolom lebih sedikit (sebelumnya akhiran "/yard" di sel Tarif → "/satuan dasar") |
| 2 | `section-card` tanpa bantalan | Bilah baru di `section-body` yang ada | `section-head` + `section-body`/`section-pad` | `section-card` + `section-head` + `section-body`; memuat/kosong `section-pad` | tidak berubah |
| 3 | Kepala kartu dijejali | Bilah Jurnal & pita di baris sendiri di bawah tombol | Kepala = ikon + judul; tautan Pusat Pengaturan di bilah sendiri | Kepala = judul; cari, saringan status, hitungan di bilah sendiri | — |
| 4 | Tombol mati hanya tooltip | "Lanjutkan pengesahan" mati → alasan tertulis (`alasanLembar`, kini juga untuk status Sedang disahkan) | Tidak ada tombol alih (H5) | Tanpa izin / bukan PT tertagih → tombol tidak tampil dan alasan tertulis di sel Aksi ("Butuh akses Catat pelunasan antar-PT." / "Dicatat oleh {PT}.") | — |
| 5 | Status hanya warna+teks | Lencana Jurnal PK-18 (`status-done`/`status-rejected`/`status-pending` + ikon); "Sedang disahkan" `status-pending` + Clock | Lencana Siap (`status-done` + CheckCircle2) / Belum (`status-pending` + AlertTriangle) + teks butir | Menunggu jurnal gaji `status-pending` Clock · Belum lunas `status-shipped` Wallet · Lunas `status-done` CheckCircle2 · Dibatalkan `status-cancelled` XCircle (kelas yang ada) | — |
| 6 | Daftar tanpa cari | — | — | Kotak "Cari nomor tagihan atau gaji", saringan status, "n dari m tagihan", `KNPager` | — |
| 7 | Teks bertentangan dengan izin | Teks menyebut akses Sahkan lembar insentif | Kartu hanya untuk pemegang `incentive.configure` | Alasan menyebut akses Catat pelunasan antar-PT | — |
| 8 | Kosong ganda / angka 0 / grafik | Pita satu kalimat; bilah Jurnal hanya untuk lembar bertautan gaji | Satu kalimat per keadaan ("Pilih satu PT …", memuat, galat) | Satu kalimat kosong; tanpa grafik | — |

Tombol `btn-sm` + `whitespace-nowrap`; konfirmasi pelunasan menyebut nominal & kedua PT (N5); kirim lewat `moneyPost` +
`useIntentKey` (N4); tanggal bayar `KNDatePicker` (bukan `type="date"`); rupiah `formatCurrency` (spasi tak-patah, "-Rp" tidak
patah); tanggal jurnal `formatDate` WIB; label sumber jurnal baru di `glSourceLabels.js` (tanpa kode mentah). Slip gaji
menampilkan label baris komponen apa adanya ("Insentif Bulanan — Okt 2026"). Belum diuji jalan di peramban.

## Menyimpang dari blueprint

1. **Status tagihan `pending` dan `cancelled`** di samping `open`/`settled`: tagihan dibuat sebagai niat sebelum jurnal gaji
   (nomornya menjadi memo baris 1-1250 jurnal gaji, dibaca INV-KM-5), dan ditutup saat proses dibatalkan/dianulir.
2. **Baris lembar di jurnal gaji tidak bergantung mode proses**: Dr 2-1500 (PT sama) / Dr 1-1250 (PT lain) juga di proses
   bermode lain — supaya lembar yang sudah berjurnal tetap "dilunasi lewat gaji seperti biasa" bila PT dikembalikan ke
   `accrue_then_settle` (spesifikasi "Membatalkan"), tanpa beban ganda.
3. **U2 diuji lewat pratinjau** proses reguler (jalur hitung yang sama) dan slip proses yang dibuat diperiksa di U3; data komisi
   mesin dicabut sesudah U2/U7 supaya serah-terima (a) bisa hijau tanpa menunggu (b).
4. **Kesiapan butir 4** memeriksa proses gaji `draft`/`pending_approval`/`approved` (belum diposting), bukan hanya draf:
   proses yang disahkan tetapi belum diposting juga akan membayar komisi otomatis.
5. **Fixture U12**: sales lintas PT bernama "Dodi" (akun ditugaskan di `ent_kanda` & `ent_ksc`, karyawan `ent_ksc`), karena
   Andi U1 sudah karyawan `ent_kanda` (satu akun = satu karyawan). Karyawan seed kedua PT dinonaktifkan di fixture. Saldo
   2-1500 `ent_kanda` di U12 diperiksa sebagai selisih (0), bukan saldo mutlak (uji sebelumnya meninggalkan saldo).
6. **`pay_on_invoice`** dibiarkan (spesifikasi ASUMSI); akrual manual 409 untuk semua mode ≠ `accrue_then_settle` (PK-22).
7. **Butir Posting Gagal `interco_incentive_charge`** tercakup PT tertagih (`entity_field` `to_entity_id`); kegagalan sisi
   penerima pelunasan (PT penagih) tampil di panel PT tertagih.

## Asumsi

- `ASUMSI:` (spesifikasi K-26) tagihan memakai 1-1250/2-1250 lewat pemetaan akun yang ada (`antar_pt.piutang_ic`/`utang_ic`);
  tidak ada akun baru (H4).
- `ASUMSI:` (spesifikasi) label baris slip "{komponen} — {periode dasar}"; lembar disahkan sebelum PT dialihkan tidak dijurnal
  surut (pita di layar menyebutnya).
- `ASUMSI:` baris bernominal 0 tidak menjadi masukan gaji dan tidak menghalangi lembar menjadi `paid`.
- `ASUMSI:` tanggal jurnal jurnal tertagih (tagihan) = tanggal jurnal gaji PT penagih; tanggal pelunasan = isian (bawaan hari ini).
- `ASUMSI:` tagihan bernilai negatif (lembar penyesuaian lintas PT tanpa baris positif) membalik arah jurnal; pelunasannya hanya
  untuk sisa positif (belum diuji — kasus jarang).
- `ASUMSI:` "dua bulan terakhir" pencocokan = dua bulan penuh sebelum bulan berjalan (WIB).
- Bila proses mati tepat sesudah jurnal gaji terbit tetapi sebelum tagihan terbit/tanda bayar tertulis, tidak ada jalur ulang
  otomatis; INV-KM-4/INV-KM-5 menandainya (tagihan tetap `pending`).

## Titik henti

- **H5 (pertanyaan pemilik — usulan baris STATUS "Menunggu pemilik"):** "KM-T4 — PT mana yang dialihkan ke Lembar Insentif
  (`hr.payroll_commission_mode` = `sheet`), dan mulai periode bayar kapan? Pilihan: per PT di Pusat Pengaturan › Gaji & SDM ›
  Lembur, komisi & kepegawaian (beralasan). Usulan: mulai dari satu PT sesudah Capaian & lembar dicocokkan dengan rekap
  manual minimal satu periode dan kartu Kesiapan semua Siap; periode bayar = bulan pertama sesudah semua akrual komisi otomatis
  dilunasi gaji." Hasil endpoint kesiapan tiap PT di **data acuan belum dijalankan** (lingkungan A dipakai integrator; unit tidak
  memanggil :8001): `GET /api/incentive/switch-readiness` dengan `X-Entity-Id` tiap PT, akun admin data acuan.
- H4: akun hanya 6-5000, 2-1500, 1-1250, 2-1250 + kas Bank (pelunasan, seperti pinjaman antar-PT) lewat pemetaan yang ada.
- H3: tidak ada skrip data; uji hanya di database tiruan; lapis A ditulis.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`d458cd5`**:

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`5737da3`: 12 / 39). Kuitansi: `bukti/KM-T4/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- HEAD cabang maju dari `2bb1a76` (HEAD tujuan pelaksana) ke `5737da3` (cek layar MN-T3: hanya `styles/components.css`, tidak
  disentuh unit ini). (a) dipasang dari `$S/KM-T4_a_merged/` (25 berkas) → **`b77dce8`**: `tests_mem` integrator **2294 lulus /
  2 dilewati / 5 xfail** (3 `xfail(strict)` menunggu (b)), 0 gagal (`bukti/KM-T4/integrator_tests_mem_a.txt`). (b) = 40 berkas
  T disalin di atas (a) → **`fee66fe`**, diperiksa berkas demi berkas sama dengan T (satu-satunya beda pohon:
  `components.css` versi `5737da3`, benar dipertahankan). `tests_mem` 2298 dan jest 1111 dari pelaksana (pohon sama — tidak
  diulang, mode hemat pemilik 15 Nov).
- Lingkungan A (data acuan sesudah `restore_demo`, kode `fee66fe`; `bukti/KM-T4/integrator_lapis_A.txt`):
  - Lapis A **U16** jalan pertama: ketiga putaran dua-Sahkan-bersamaan **lulus** ([200, 409], 1 jurnal, 1 masukan gaji per
    lembar) tetapi pembersihan gagal 422 — `POST /config/values/clear` menerima satu butir (`ConfigValueIn`), uji mengirim
    `{"items": […]}`; lembar uji tertinggal sehingga jalan kedua 409 "sudah ada di lembar". Uji dibetulkan (**`d458cd5`**),
    sisa dibersihkan (3 lembar, 3 jurnal, 3 masukan, 1 komponen, nilai mode PT dicabut), jalan ulang **2 lulus**, sisa 0.
  - PK-14 lapis A **9 lulus** (indeks wajib 38: `uq_charge_run_to`, `uq_source_key` terpasang).
  - `verify_data_integrity --only incentive,interco`: **INV-KM-1…5 PASS**, FAIL 0 (WARN INV-IC lama: belum ada transaksi
    antar-PT di data acuan) — `bukti/KM-T4/integrator_inv_km.txt`.
  - **Kesiapan beralih per PT** (`GET /api/incentive/switch-readiness`, admin, data acuan; `bukti/KM-T4/integrator_kesiapan_per_pt.txt`):
    Sukacita, Kanda Fabric, Cipta Sandang — ketiganya mode "Komisi otomatis: dicadangkan, dilunasi lewat gaji", **empat butir
    Siap** (pencocokan Sep–Okt 2026 cocok, saldo hutang insentif Rp 0, sales lembar tertaut karyawan, tidak ada proses gaji
    belum diposting yang memuat komisi otomatis). Catatan: data acuan belum punya Lembar Insentif maupun akrual komisi, jadi
    "Siap" di sini belum berarti siap di data nyata — sakelar tetap keputusan pemilik (H5).
- Uji jalan **U17** (data contoh di database uji: PT Sukacita mode `sheet`, satu Lembar Insentif 2.500.000 disahkan → jurnal
  terbit; tiga tagihan antar-PT contoh untuk tata letak; skrip `bukti/KM-T4/kmt4_layar_fixture.py`, hanya untuk database uji):
  **satu cacat ditemukan dan diperbaiki (`d458cd5`)** — Antar-PT › Pinjaman › **Tagihan insentif antar-PT** di 1024 px: 7 kolom
  ±767 px dalam kartu 734 px → lencana Status tertutup kolom Aksi yang menempel ("Menung…", "Belum l…"). PT penagih/tertagih
  dan Nominal/Sisa kini masing-masing satu kolom dua baris → 5 kolom = **734 / 990 px** (1024 / 1280), semua lencana utuh; di
  390 px (tampilan penuh) tabel bergulir di dalam kartu, Aksi menempel. Jest `kmt4LembarGaji` + `kmt3LembarInsentif` 13/13.
- Potret tanpa cacat: rincian Lembar Insentif (lencana Disahkan, bilah **Jurnal Terbit · per 30 Nov 2026 · Lihat jurnal**,
  pita "Lembar sudah disahkan — koreksi dibuat sebagai baris penyesuaian…", tabel 8 kolom = pop-up di 1024/1280, bergulir di
  390), kartu **Kesiapan beralih ke Lembar Insentif** di Target & Aturan (mode tertulis, empat butir ikon+teks, tautan Pusat
  Pengaturan, tanpa tombol alih — H5), Komisi Otomatis (`bukti/KM-T4/cek_*.png`).

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A dipakai integrator). Lapis A U16 dan `tests/test_bp_PK14_indeks_wajib.py` (38) ditulis, belum
teruji. Uji jalan U17 belum.

## Penjaga & angka uji (worktree kerja W, basis `5410979`)

| | Sebelum (B) | Sesudah (W) |
|---|---|---|
| `tests_mem` | 2265 lulus / 2 dilewati / 2 xfail | **2284** lulus / 2 / 2 (+19 KM-T4). Jalan penuh: 2283 lulus + 1 merah `test_KFT1 U02` (hitungan kunci berizin `settings.manage`: `commission.incentive_unit` kini tidak dipakai) → konstanta `KMT4_TIDAK_DIPAKAI` ditambahkan, berkas itu 14/14 (terarah, hemat uji) |
| jest penuh | 1071 lulus (35 suite gagal dimuat — `cmdk`/`@radix-ui`) | **1077** lulus (+6 `kmt4LembarGaji`; 35 suite yang sama) |
| `hitung_penjaga.sh` | auth 26 · ui_standard 11 · i18n 102 · create_modal 5 · page_tabs 1 (INV-UI-13 0) · to_list 5 · entity_label 2 · lainnya 0 | **identik** |
| `verify_posting_coverage` · `verify_atomic_claim` (+ uji-diri 64) · `verify_role_gate_ui` | 137/0 · 161/0 · 31/0 | 140/0 · 161/0 · 31/0 |
| `verify_cash_single_door` · `verify_detail_modal` · `verify_config_text` · `verify_payment_vocab` | 751/0 · 31/0 · 3486/0 · 1860/0 | 752/0 · 31/0 · 3486/0 · 1862/0 |
| `verify_config_fallback` (+`--entity`) · `audit_config_wiring --strict` · `check_nav_map` · `verify_access_catalog_nav` | 162/0 (162/0) · hijau · PASS · 0 | 162/0 (162/0) · hijau · PASS · 0 |
| Inventaris multi-koleksi (`inventaris_multi_koleksi.py`) | — | tidak berubah |

## Penggabungan (pelaksana, ke HEAD `2bb1a76` — sesudah MN-T3 `351d1f9`…`2bb1a76`)

Worktree tujuan T di-*detach* ke HEAD cabang; per berkas: sama dengan B → disalin dari W; beda → `git merge-file -p <HEAD> <B>
<W>`; baru → disalin. Berkas unit yang juga diubah HEAD sesudah B hanya empat dokumen:

| Berkas | Keadaan | Keputusan |
|---|---|---|
| `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | bentrok di ujung berkas (MN-T3 menambah §9.32) | keduanya: §9.32 MN-T3 utuh, bagian KM-T4 menjadi **§9.33** (di W tetap §9.32) |
| `ENTITY_REGISTRY.md`, `memory/PRD.md` | tergabung otomatis | diperiksa: tidak ada baris HEAD yang hilang |
| `CODEBASE_MAP.md`, `configKeyIndex.json` | turunan | dibangkitkan ulang di T (`access_modules.py` tidak berubah → fixture akses tidak dibangkitkan) |

Hitungan uji lama di HEAD (KF-T1, PRT9, indeks wajib PK-14, jenis nomor KP-T5, potret KF-T4) tidak diubah MN-T3 → angka KM-T4
ditambahkan apa adanya. Serah-terima (a) tergabung: `scratchpad/KM-T4_a_merged/` (25 berkas; dibuat di `c4dad6a`, berkasnya
tidak tersentuh `c4dad6a..2bb1a76` → `BASIS.txt` = `2bb1a76`; uji terarah KM-T4/PK-14/KP-T5/KF-T4 di sana 61 lulus + 3 xfail).

| | HEAD `2bb1a76` (murni) | T (HEAD + KM-T4) |
|---|---|---|
| `tests_mem` | tidak dijalankan penuh (hemat uji) — 2279 (= T − 19) | **2298** lulus / 2 dilewati / 2 xfail |
| jest penuh | 1105 (= T − 6, suite yang sama) | **1111** lulus (35 suite gagal dimuat — `cmdk`/`@radix-ui`, daftar sama dengan B) |
| `hitung_penjaga.sh` | auth 26 · ui_standard 9 · i18n 102 · create_modal 5 · page_tabs 1 (INV-UI-13 0) · to_list 5 · entity_label 2 · lainnya 0 | **identik** |
| `verify_posting_coverage` · `verify_atomic_claim` (+ uji-diri 64) · `verify_role_gate_ui` | 137/0 · 161/0 · 31/0 | 140/0 · 161/0 · 31/0 |
| `verify_cash_single_door` · `verify_detail_modal` · `verify_config_text` · `verify_payment_vocab` | 750/0 · 31/0 · 3486/0 · 1862/0 | 753/0 · 31/0 · 3486/0 · 1866/0 |
| `verify_config_fallback` (+`--entity`) · `verify_access_catalog_nav` · `audit_config_wiring --strict` · `check_nav_map` | 162/0 (162/0) · 0 · hijau · PASS | 162/0 (162/0) · 0 · hijau · PASS |

## Hambatan lingkungan

- Suite jest yang memuat `cmdk`/`@radix-ui` gagal dimuat di lingkungan lokal (kendala lama); uji KM-T4 meniru `KNSelect`/
  `KNDatePicker`.

## Yang perlu direview

- Usulan koreksi U5 (masa pajak Desember).
- Menyimpang 1–2 (status tagihan tambahan; baris lembar di jurnal gaji tidak bergantung mode).
- Lapis A U16, uji jalan U17, dan hasil kesiapan tiap PT di data acuan (H5).
