# CR-T3 — Satu mesin gerbang kredit di empat titik periksa, status "Tahan kredit", dan izin kredit yang terbatas

- Commit awal: `53b419b` (worktree kerja, basis B)        - Commit akhir: (a) `2ac8e6c`, (b) `945da6e`, cek layar `eaba57f`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke worktree tujuan pada HEAD **`41c0b60`** (uji & penjaga dijalankan di `fc95d36` `[CR-T4]`; `4580bd9`/`41c0b60` sesudahnya hanya dokumen/STATUS) — lihat "Penggabungan"
- ID ditangani: CR-02, CR-04, CR-05 (spesifikasi `docs/blueprint/unit/CR-T3.md`; keputusan K-14, K-27, K-28, K-29, K-31)
- Standar: `02` §2 (2.1–2.4), §3.1 (Z1, Z2, Z4, Z6), §3.2, §3.4 (N1, N2, N4, N5), §4 (L1, L4, L6), §5 (D3, D7, D8, D9), §6
- Risiko tinggi → dua serah-terima (`00` §8): **(a)** mesin baru `services/credit_gate.py` + sembilan kunci + izin kredit
  (field, `use_override`, izin `credit_override.view/create`, jenjang & kontrol dua orang) di samping jalur lama; **(b)**
  empat titik periksa terpasang, `credit_gate_rejections`, "Tahan kredit", tahan-kirim tunai, pratinjau & pembungkus
  dialihkan, `evaluate_credit_gate`/`check_credit_for_order` dihapus, layar.
- Titik henti: **H5** (titik periksa lain, masa berlaku izin, tahan-kirim tunai untuk PT nyata — pertanyaan di bawah),
  **H3** (skrip pembanding & migrasi profil kredit CR-T1 tidak dijalankan ke data mana pun), **H7** (`dispatch_guard`
  disentuh hanya SEBELUM pemeriksaan muat/RFID; logika gerbang RFID tidak diubah).

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`; diperiksa di `53b419b`)

| Fakta spesifikasi | Hasil di basis B |
|---|---|
| Gerbang hanya saat pesanan dibuat dan pratinjau checkout (`sales_orders.py:363`, `crm.py:176`) | Berlaku, bergeser — `routers/sales_orders.py:426`, `routers/crm.py:225` (`evaluate_credit_gate`) |
| Terblokir → 409 `CREDIT_BLOCKED` (`:372`) | Berlaku, bergeser `:436` |
| Alasan kalimat bebas (`customer_service.py:298`) | Berlaku, bergeser `:247` (`reasons = []`, `check_credit_for_order` `:236`) |
| Izin: terbaru menang, nominal 0 = tak terbatas, tanpa masa berlaku, sekali pakai (`:523`, `sales_orders.py:703`) | Sebagian — PK-45 sudah menolak pengajuan bernominal 0 (`crm.py:131`); pembaca lama masih menerima izin lama bernominal 0 (`customer_service.py:476–483`); konsumsi `consumed` `sales_orders.py:785` |
| Pengajuan izin `order.create`; memutus nama peran (`crm.py:93`, `:142`) | Sebagian — pengajuan `order.create` berlaku (`crm.py:120`); memutus SUDAH berizin `credit_override.approve` + Aturan Persetujuan KP-T4 + kontrol dua orang KF-T6 `lewat_batas_kredit` (`crm.py:175–193`) |
| Jalur kedua per pesanan: `credit_overrides` + entri `kredit` + `credit_hold: true` (`so_approvals.py:231/262`) | Berlaku, bergeser `:233`, `:264`; keputusan entri `kredit` menulis izin `consumed` + `credit_hold: false` `:372` |
| Entri menunggu tak bisa dilepas; sub-status "Menunggu approval kredit" (`so_lifecycle_service.py:62`, `so_status.py:48`) | Berlaku (`confirm_core` `:62`, `so_status.py:48/146`) |
| Termin dari permintaan hanya dicek keberadaannya (`sales_orders.py:353`, `so_override_service.py:87`) | Berlaku, bergeser — `sales_orders.py:415`, `so_override_service._header` (PK-38 menambah cek termin lebih longgar = `order.release_unpaid`) |
| Override ubah jumlah/baris/termin tanpa cek kredit (`so_override_service.py:306`) | Berlaku, bergeser `apply` `:384` |
| Tahan-kirim hanya termin ber-DP; CASH lolos (`dispatch_payment_gate.py:66`, `config_service.py:150`) | Berlaku, bergeser — `applies` `:121`, `CASH` `:162` |
| Pagar kirim satu pintu (`loading_check_service.py:304`) | Berlaku `:304` (`dispatch_guard`; dipanggil Barang Keluar, maju tahap WMS, cek keberangkatan trip) |
| Pengecualian kirim `order.release_unpaid` (`sales_orders_extra.py:979`, `permissions_config.py:693`) | Berlaku, bergeser `:992`, `:702` |
| Checkout `creditBlocked`; kartu pelanggan pop-up "Ajukan Override Kredit" (`CheckoutDrawer.jsx:189`, `Customer360Panel.jsx:322`) | Berlaku, bergeser `:207`, `OverrideModal` `:336` |

Prasyarat ada di B: CR-T1 (`credit_profile_service.effective`, cadangan `data_lama`), CR-T2 (`customer_balance_service.get`,
`giro_outstanding` sudah terisi karena PM-T3 ada), PK-38, KP-T4 (`approval_policy_service.can_decide`, jenis
`credit_override`), KF-T6 (`dual_control`). PM-T4 tidak menyentuh berkas unit ini.

## Serah-terima (a) — mesin baru di samping jalur lama

| Berkas | Isi |
|---|---|
| `backend/services/credit_gate.py` (baru) | `evaluate(customer_id, entity_id, checkpoint, order_id, order_amount, term_code, actor, order, today[, saldo])` — urutan spesifikasi: titik mati → `{lolos, checked: false}`; eksposur sen bulat dari `customer_balance_service.get` + `credit_profile_service.effective` PT itu saja; tujuh kode alasan + pesan persis; izin kredit (lingkup pesanan, sudah dipakai pesanan ini, lingkup pelanggan bersisa — hangus paling cepat dulu); K-27 bayar-penuh-dulu hanya di `pesanan_dibuat`; `raw_result` (sebelum izin/K-27). Pesanan yang SUDAH ada: bagiannya di saldo = `this_order` (aturan `customer_balance_service.compute` per pesanan). `use_override` (pembaruan bersyarat sisa + `valid_until` + belum dipakai pesanan ini; idempoten), `release_use`, `hold`, `release`, `recheck_order`, `recheck_holds` (tertua dulu, penjaga masuk-ulang `contextvars`), `gate_checkpoint`, `guard_held`, `after_order_changed`, `term_change_allowed`, `record_rejection`. Tahan-kirim tunai menyala → bagian terkirim pesanan tunai + telatnya ikut |
| `backend/services/credit_override_service.py` (baru) | `create` (nominal > 0 PK-45, lingkup, alasan master wajib, "Lainnya" wajib catatan, potret D3, pemberitahuan pemegang `credit_override.approve` PT itu), `decide` (Aturan Persetujuan `credit_override` → `tolak_bila_pelaku_sama("lewat_batas_kredit")` → tulis bersyarat `pending`; setuju: `valid_until` = putus + `ar.izin_kredit_masa_berlaku_hari`, `remaining_amount`, penolakan terbuka → `dilanjutkan`, pesanan yang ditahan diperiksa ulang; sudah diputus → 409 pesan spesifikasi; pemberitahuan pengaju), `masa_berlaku`, `tampil`, `reasons` |
| `backend/config_catalog_kredit.py` (baru) + `config_registry.py` | sembilan kunci (tabel "Pengaturan"; grup `uang-masuk` → "Pembayaran pelanggan", delapan `ar.*` di sub-judul "Peringatan & blokir kredit" (3 → 11), `finance.tahan_kirim_tunai` di "Syarat bayar"); risiko tinggi + alasan, izin `credit_profile.approve`, pemakai nyata per kunci |
| `config_catalog_kontrol.py` | aksi KF-T6 `lewat_batas_kredit` berlabel **"Izin kredit"**, titik pasang `credit_override_service.py:decide` (lihat Menyimpang 1) |
| `services/amendment_service.py` | benih alasan `cr_riwayat_baik`, `cr_jaminan`, `cr_lain` (applies_to `credit_override`) |
| `permissions_config.py` (`CRT3_DEFAULT_PAIRS`), `access_modules.py` | `credit_override.view` (Admin, Manajer, Sales, Admin Sales, Finance, MD, Admin Sample = pemegang `customer.view`), `.create` (Admin, Manajer, Sales, Admin Sales = pemegang `order.create`); label sumber daya "Izin Kredit" + label tiga aksi; nav modul "Pengawasan Tim Sales & Kredit" + `customers-crm`, `keuangan`, `ar-aging`, `credit-overrides` |
| `routers/crm.py` | `POST /customers/{id}/credit-override` (`credit_override.create`; `scope`, `order_id`, `reason_code`, PT = `resolve_requested_entity` / PT pesanan), `GET /credit-override-reasons`, `GET /credit-overrides` (`credit_override.view`; saringan `scope`, `valid`, `customer_id`; cakupan PT + pelanggan), `GET …/{id}`, `POST …/{id}/decision` lewat layanan |
| `schemas_crm.py`, `idempotency.py` | isian baru; `/api/credit-overrides` + pola `/api/customers/{id}/credit-override` (N4) |
| Layar (a) | pop-up baku `CreditOverrideModal.jsx` (Lingkup, Nominal, Alasan master, Catatan; `moneyPost` + `useIntentKey`), `creditOverrideUi.js`; kartu pelanggan memakainya (tombol "Ajukan izin kredit" bagi `credit_override.create`, riwayat "Izin Kredit" ber-lingkup/sisa/berlaku/jejak pakai); `CreditOverrideRequest.jsx` (checkout & HP) membuka pop-up; Pusat Persetujuan kategori kredit dari `credit_override.view` |
| Uji (a) | `tests_mem/test_CRT3_gerbang.py` (U1–U3, U11–U13 langsung, titik mati, plafon kedaluwarsa, giro, **pembanding 20 kombinasi**), `tests_mem/test_CRT3_izin.py` (U4–U6, U6b, lingkup pesanan, U15, izin bawaan setara, U16 × 9, kunci sesuai spesifikasi, pemakaian bersamaan lapis B, izin lama nominal 0), `tests_mem/pembantu_crt3.py` (fixture G1) |

Merah di kode lama: **48/48** (`bukti/CR-T3/a_merah_kode_lama.txt`, sebab `a_merah_sebab.txt`: `ImportError credit_gate`,
kunci tidak ada di registry, aksi `view` tidak berlaku untuk sumber daya izin kredit, `reason_code` tidak dikenal).
Tes pembanding di (a): gerbang lama dipanggil langsung dan sama dengan tabel beku di 20 kombinasi; (b) menghapus gerbang
lama, tabel beku tetap. Keadaan (a): `$S/CR-T3_a_state/` (basis `53b419b`, 30 berkas) dan `$S/CR-T3_a_merged/` (HEAD
`c3fa3f8`; bentrok di `permissions_config.py`, `test_KFT1_izin_pengaturan.py`, `test_PRT9_izin_bawaan.py` — semua tambahan
berdampingan, keduanya dipertahankan). `tests_mem` (a) di basis: **2102 lulus / 2 dilewati / 2 xfail** (= 2045 + 48 + 9
putaran KF-T8 untuk kunci baru); di (a) tergabung `c3fa3f8`: **2158 lulus / 2 dilewati / 2 xfail** (HEAD `c3fa3f8` = 2101, diturunkan); jest 1018 (sama dengan HEAD — (a) tanpa uji jest baru). Jest (a): 995 lulus (= basis).

## Serah-terima (b) — titik periksa dipasang, jalur lama dimatikan

| Titik / bagian | Tempat | Perilaku |
|---|---|---|
| `pesanan_dibuat` | `routers/sales_orders.create_order` (menggantikan `evaluate_credit_gate`) | `tahan` → 409 `CREDIT_BLOCKED` (`reasons` = `{code, message}`, `rejection_id`) + satu `credit_gate_rejections`; `tolak` → 400 `TERM_NOT_ALLOWED`; lolos berkat izin → `use_override` SEBELUM reservasi (kalah balapan → 409; gagal sesudahnya → `release_use`); pesanan menyimpan `credit_gate_at_order`, `pay_before_ship`, `credit_override_id`, `credit_override_used`; pesanan sample tidak dinilai (tetap) |
| `pesanan_diubah` | `so_override_service.apply` (sesudah tersimpan) + `_header` (termin di luar daftar → 400 sebelum simpan); `amendment_service._apply` (sesudah hitung ulang / nota debit) | hanya bila nilai tagihan naik atau `net_days` termin baru lebih besar; perubahan tetap berlaku; gagal → `hold(...)` |
| `lepas_gudang` | `so_lifecycle_service.confirm_core`, sebelum transisi | "Tahan kredit" → 409 walau titik mati; titik menyala & gagal → `hold(...)` lalu 409 |
| `surat_jalan` | `loading_check_service.dispatch_guard`, sesudah gerbang bayar, sebelum pemeriksaan muat/RFID | sama |
| Tahan kredit | `so_status` | sub-status `tahan_kredit` "Tahan kredit" mendahului alasan lain selama pesanan belum selesai/terkirim penuh (cermin `utils/soStatus.js`) |
| Pelepasan | `customer_balance_service.refresh` (pembayaran, nota, pesanan → `recheck_holds`), `credit_override_service.decide`, `POST /api/sales-orders/{id}/credit-recheck` (`order.update`) | lolos/peringatan (izin dipakai bila perlu) → `credit_hold: false`, info pindah ke `credit_hold_history` (satu baris per tahanan) |
| Tahan-kirim tunai | `dispatch_payment_gate.evaluate` | persen wajib bayar 100 bila `pay_before_ship`, atau termin `type: cash` dan `finance.tahan_kirim_tunai` menyala untuk PT pesanan |
| Pratinjau | `GET /api/customers/{id}/credit-status?amount=&term_code=&entity_id=` | field lama dipertahankan (`level` dari hasil mentah, `blocked` dari hasil akhir, `reasons` = pesan), + `gate` |
| Pembungkus | `POST /api/sales-orders/{id}/request-credit-approval` (`credit_override.create`) | izin lingkup pesanan lewat `credit_override_service.create` (+ `has_so_entry`); entri `kredit` tetap ditulis; keputusan entri → `credit_override_service.decide` (wewenang sudah dinilai entri) |
| Penolakan | `GET /api/credit-gate-rejections` (berhalaman), `GET …/{id}` (+ `payload_snapshot`) | `credit_override.view` per cakupan; pembuat pesanan sendiri selalu melihat penolakannya |
| D8 | `customer_service` | `evaluate_credit_gate`, `check_credit_for_order` dihapus (pencarian: tanpa pemanggil; uji lama dialihkan) |
| Data | `indexes.py`, `entity_scope.py`, `scripts/verify_contract.py`, `approval_backlog_service.py`, `export_registry_more.py` | `credit_gate_rejections` (`cgr_`, indeks `(entity_id, status, created_at)` + `uq_id`, SCOPED, kontrak); antrean ringkas menghitung izin lingkup pesanan tanpa entri pesanan; ekspor "Izin Kredit" (`credit_override.view`, kolom lingkup/sisa/berlaku/alasan) |
| Skrip | `scripts/crt3_beda_gerbang_kredit.py` (baru) | daftar pelanggan yang hasilnya berbeda (lama vs baru), selalu baca-saja (H3) |
| Layar (b) | `CreditGateBox.jsx` (baru), `CheckoutStep3.jsx`, `CheckoutDrawer.jsx`, `MobileCustomerBar.jsx`, `OrderCreditHold.jsx` (baru) + `OrderDetailPanel.jsx`, `CreditOverridesPanel.jsx`, `SoStatusBadges.jsx`, `utils/soStatus.js`, `CustomerCreditTab.jsx`, `CreditProfileRequestModal.jsx`, `hooks/useAppActions.js` | lihat "Cek layar" |
| Uji (b) | `tests_mem/test_CRT3_pemasangan.py` (15), `tests_mem/test_CRT3_beda_gerbang.py` (1), `tests/test_bp_CRT3_izin_bersamaan.py` (lapis A U17, ditulis), jest `features/__tests__/crt3GerbangKredit.test.js` (6) | |

Merah di kode (a) (`bukti/CR-T3/b_merah_kode_a.txt`, `b_merah_daftar.txt`): **14 merah, 2 hijau** — U8 hijau
(spesifikasi: kunci bawaan = perilaku hari ini) dan "tunai ditahan ikut piutang & telat" (fitur mesin (a)); yang lain
merah karena `gate` tidak ada di pratinjau, `reasons` masih kalimat, `credit_override_used` tidak ada, izin kedaluwarsa
tetap dipakai gerbang lama, tidak ada tahanan, termin tidak diperiksa, gerbang bayar tidak menahan tunai, skrip pembanding
butuh `saldo`. Jest (b) merah di kode lama: komponen `CreditGateBox`/`OrderCreditHold` tidak ada.

## Uji penerimaan

Fixture G1 (`pembantu_crt3.g1`, SISIP): pelanggan P plafon khusus Rp 10.000.000; pesanan terkirim Rp 6.000.000 (jurnal surat
jalan Dr 1-1200), pesanan belum dikirim Rp 2.000.000 (uji HTTP: pesanan S lewat `POST /api/sales-orders` 100 m × Rp 20.000,
PT non-PKP), titipan Rp 500.000 → eksposur 7.500.000.

| ID | Lapis | Merah di kode lama (sebab) | Hasil kode baru |
|---|---|---|---|
| U1 | B | ya (modul tidak ada; HTTP: `gate` tidak ada) | Lulus — `peringatan`, `MENDEKATI_PLAFON` "Eksposur sudah 95 % dari plafon." (9.500.000 ≥ 8.000.000); HTTP 200, `credit_warning`, potret `credit_gate_at_order` 9.500.000 |
| U2 | B | ya | Lulus — `tahan` `LEWAT_PLAFON` "Eksposur Rp 10.500.000 melewati plafon Rp 10.000.000."; HTTP 409 `CREDIT_BLOCKED` + `rejection_id`; tidak ada pesanan; satu `credit_gate_rejections` amount 3.000.000, eksposur 10.500.000, `payload_snapshot`; daftar & rincian untuk pembuatnya |
| U3 | B | ya | Lulus — P (titipan tidak dihitung) 10.500.000 → `tahan`; Q `ent_ksc` 10.000.000 → `peringatan`, tanpa `LEWAT_PLAFON` |
| U4 | B | ya | Lulus — izin pelanggan Rp 3.000.000, `valid_until` = putus + 3 hari; pesanan Rp 3.000.000 HTTP 200, `credit_override_id`; `remaining_amount` 0; `used_by` 1 baris (+ nomor pesanan); pesanan kedua 409 |
| U5 | B | ya (gerbang lama mengabaikan masa berlaku) | Lulus — 409 `CREDIT_BLOCKED`; izin tetap bersisa 3.000.000; panel: `expired`, saringan `valid=1` kosong |
| U6 | B | ya | Lulus — nominal 0 → 400 "Nominal izin wajib lebih dari 0."; `kontrol.lewat_batas_kredit.min_orang` = 2 → pengaju-pemutus 403 "Izin kredit harus diputuskan orang lain…", manajer lain 200, putus ulang 409 "Izin kredit ini sudah diputus atau kedaluwarsa." |
| U6b (tambahan) | B | ya | Lulus — lingkup pesanan tanpa pesanan 400; alasan kosong 400; "Lainnya" tanpa catatan 400; pilihan alasan dari master |
| U7 | B | ya | Lulus — override 100 → 250 m (Rp 5.000.000), `ar.periksa_kredit_pesanan_diubah` = ya: nilai tersimpan, `credit_hold: true`, `LEWAT_PLAFON` (6 + 5 − 0,5 = 10,5 jt), checkpoint `pesanan_diubah`, sub-status pertama `tahan_kredit` = "Tahan kredit" |
| U8 | B | tidak (diharapkan: bawaan = hari ini) | Lulus — `credit_hold: false` |
| U9 | B | ya | Lulus — `confirm` 409 "Pesanan … ditahan kredit — Eksposur Rp 10.500.000 melewati … Ajukan izin kredit atau catat pembayaran dulu."; status tidak berubah; "Periksa ulang kredit" → masih tahan |
| U10 | B | ya | Lulus — kwitansi Rp 1.000.000 (`POST /api/ar-receipts`) → 9,5 jt ≤ plafon → dilepas sendiri; `credit_hold_history` 1 baris; `confirm` lalu 200 |
| U11 | B | ya | Lulus — `tahan` `BLOKIR_MANUAL` "Pelanggan diblokir manual: Cek ditolak bank."; izin Rp 5.000.000 tidak terpakai |
| U12 | B | ya | Lulus — langsung: `tolak` `TERMIN_TIDAK_DIIZINKAN` "Termin Kredit NET 30 Hari tidak diizinkan untuk pelanggan ini. Termin yang diizinkan: Tunai / POS, Kredit NET 14 Hari."; HTTP NET30 400 `TERM_NOT_ALLOWED`, NET14 200; ganti termin lewat override ke luar daftar (titik menyala) 400 tanpa simpan |
| U13 | B | ya | Lulus — CBD: mentah `tahan` `TELAT` "Ada tagihan telat 20 hari (batas 14 hari) senilai Rp 6.000.000." → `lolos`, `pay_before_ship`; HTTP 200; `dispatch_guard` 409 "Tertahan pembayaran: termin CBD…"; NET30 409 `TELAT` |
| U14 | B | ya | Lulus — CASH Rp 1.000.000 belum dibayar: `ent_kanda` (kunci ya) 409 "…kurang Rp 1.000.000…", `ent_ksc` lolos; kunci dicabut → lolos |
| U15 | B | ya (`view` tidak berlaku untuk sumber daya) | Lulus — Tanpa Acuan + `credit_override.approve` 200; Manajer Kosong 403; Sopir 403; Tanpa Acuan `view` lihat 200, `create` ajukan 200; Sopir ajukan 403 |
| U16 | B | ya (kunci tidak ada) | Lulus — putaran `t1_config` (KF-T8 `putaran`) sembilan kunci + registri sesuai tabel |
| U17 | A | — | **ditulis, belum dijalankan** (`backend/tests/test_bp_CRT3_izin_bersamaan.py`, 5 putaran dua `use_override` bersamaan → satu True, sisa 0). Padanan lapis B `test_CRT3_dua_pesanan_bersamaan_satu_izin` lulus (database tiruan: tidak membuktikan perilaku bersamaan MongoDB asli — `00` §9) |
| U18 | layar | jest merah (komponen tidak ada) | jest `crt3GerbangKredit` 6/6: empat baris eksposur + plafon + sisa + alasan + "Ajukan izin kredit"; pop-up mengirim lingkup/nominal/alasan dengan kunci idempotensi; panel izin: Lingkup, Sisa, Berlaku sampai, Alasan, konfirmasi pelanggan + PT + nominal; detail pesanan Tahan kredit + Periksa ulang. **Belum diuji jalan** di peramban |
| pembanding | B | (a): gerbang lama = tabel | Lulus — 20 kombinasi, hasil `pesanan_dibuat` kunci bawaan setara gerbang lama (blocked ↔ tahan/tolak, warning ↔ peringatan, ok ↔ lolos) |
| tambahan | B | ya | titik mati (empat), plafon kedaluwarsa (keterangan), giro belum cair (+3 jt, sakelar), izin lingkup pesanan hanya pesanannya, izin bawaan setara, izin lama nominal 0 = kedaluwarsa, tunai ditahan ikut piutang & telat, titik lepas gudang + izin pesanan melepas & dipakai, titik surat jalan + tahanan bertahan walau titik dimatikan, pembungkus `request-credit-approval`, jalur lama dihapus, skrip pembanding baca-saja |

### Hitung tangan

- U1: 6.000.000 + 2.000.000 − 500.000 + 2.000.000 = 9.500.000; 80 % × 10.000.000 = 8.000.000 ≤ 9.500.000 → peringatan;
  9.500.000 ≤ 10.000.000 dan tanpa pesanan ini 7.500.000 < 10.000.000 → bukan tahan; 9.500.000 / 10.000.000 = 95 %.
- U2: + 3.000.000 = 10.500.000 > 10.000.000 → tahan. U3: P tanpa titipan 8.000.000 + 2.500.000 = 10.500.000 > 10.000.000;
  Q 7.500.000 + 2.500.000 = 10.000.000 (tidak > ; tanpa pesanan 7.500.000 < plafon) → peringatan.
- U7: S 2.000.000 → 5.000.000 (bagian `open_orders`): 6.000.000 + 5.000.000 − 500.000 = 10.500.000 > 10.000.000 → tahan.
  U10: kwitansi 1.000.000 → terkirim 5.000.000: 5.000.000 + 5.000.000 − 500.000 = 9.500.000; tanpa S 4.500.000 → tidak tahan
  → peringatan (95 %) → dilepas.
- U13: telat 20 > 14 → tahan; CBD = `type: cash`/DP 100 % → lolos `pay_before_ship`; gerbang bayar 100 % × 1.000.000 belum
  dibayar → kurang 1.000.000.
- U14: CASH `dp_percent` 0 → bawaan tidak menahan; kunci menyala → 100 % × 1.000.000, dibayar 0 → kurang 1.000.000.
- Tidak ada jurnal di unit ini (gerbang hanya membaca saldo dan menulis status pesanan/izin).

## Uji lama yang disesuaikan (perilaku sengaja berubah — tidak dilonggarkan)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` | `CRT3_KUNCI = 9` di U04 | sembilan kunci berizin `credit_profile.approve` |
| `tests_mem/test_KFT4_registry.py` | `CRT3_PEMBAYARAN_PELANGGAN = 9` | kunci baru di kelompok "Pembayaran pelanggan" |
| `tests_mem/test_PRT9_izin_bawaan.py` | `TAMBAHAN_SESUDAH` + `CRT3_DEFAULT_PAIRS` | izin bawaan baru |
| `tests_mem/test_KFT6_tabel_c.py` | label aksi `lewat_batas_kredit` "Izin kredit" | label spesifikasi |
| `tests_mem/test_KFT7_nilai_tertulis.py` U4, `tests/test_decisions_d4.py` (lapis A) | `check_credit_for_order` → `credit_gate.evaluate` | fungsi lama dihapus (D8); harapan sama (peringatan/lolos; tanpa telat) |
| jest `prt7TombolIzin`, `phase4R5` | izin uji + `credit_override.view` | daftar izin kredit kini dijaga `credit_override.view` |
| jest `crt1ProfilKredit` | baris termin yang diizinkan tidak lagi "belum dipakai"; termin bawaan tetap | termin kini ditegakkan saat pesanan dibuat |
| `frontend/src/config/__tests__/fixtures/view_main_permission.json` | `credit-overrides` → `credit_override.view` | endpoint utama tab berizin baru (uji MN-T1 U04) |
| fixture akses `access_builtin_fixture.json`, `configKeyIndex.json`, `memory/INVENTARIS_MULTI_KOLEKSI_2026-09.md` | dibangkitkan ulang | izin bawaan / kunci / inventaris berubah (124 → 123 baris: `create_order` tidak lagi menulis `credit_overrides` langsung, pembungkus menulis lewat layanan) |

## Kueri pencari (diminta spesifikasi; baca saja)

- Izin lama bernominal 0 yang belum dipakai (kini dianggap kedaluwarsa):
  `db.credit_overrides.find({status:"approved", $or:[{amount:0},{amount:null}], consumed:{$ne:true}}, {id:1, customer_name:1, entity_id:1, decided_at:1})`
- Pelanggan yang hasil gerbangnya berbeda (K-29 per PT, K-31 titipan/giro): `python scripts/crt3_beda_gerbang_kredit.py`
  (baca-saja; di container: `docker compose -f docker-compose.dev.yml exec backend python /app/scripts/crt3_beda_gerbang_kredit.py`).
  **Belum dijalankan ke data acuan** — lingkungan A milik integrator; di uji B: pelanggan dua PT (plafon KSC 10 jt, piutang
  6 jt di KSC + 6 jt di KANDA) berubah `blocked → lolos` di kedua PT.
- Pesanan yang kini ditahan: `db.sales_orders.find({credit_hold:true}, {number:1, customer_name:1, credit_hold_info:1})`.

## Cek layar

Belum dipotret (integrator memotret 1280/1024/390 px). Daftar periksa dari kode:

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati beralasan | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong / angka 0 |
|---|---|---|---|---|---|---|---|---|
| Checkout › Tinjau (kotak kredit `CreditGateBox`) | daftar baris label–angka (bukan tabel), membungkus di 390 px | kotak `p-2.5` berbingkai | lencana hasil sendirian di bilah atas | "Kredit Tertahan"/"Termin Tidak Diizinkan" pada tombol Buat + kalimat "Pesanan belum bisa dibuat: kredit tertahan." di kotak | `status-pill` + ikon: Kredit aman `status-done`, Peringatan `status-pending`, Kredit tertahan/Termin ditolak `status-rejected`; alasan berikon | — | tanpa `credit_override.create`: "Izin kredit diajukan pemegang akses mengajukan izin kredit…" (bukan tombol mati) | komponen tidak dihitung ditulis "tidak dihitung"; plafon 0 = "Tanpa batas"; titik mati = satu kalimat |
| Checkout › Termin | — | — | — | — | — | — | "Hanya termin yang diizinkan untuk pelanggan ini." | daftar kosong = "Default" (tetap) |
| HP › bilah pelanggan | — | tetap | tetap | "Checkout terkunci sampai izin kredit disetujui (pesanan bayar penuh sebelum kirim tetap boleh)." | lencana HP tetap (ikon+teks) | tetap | tetap | — |
| Pop-up "Ajukan izin kredit" (`FormModal md` + `FormSection`) | — | baku | judul + subjudul pelanggan · PT | tidak dimatikan; kekurangan "Lengkapi: …" di kaki | — | — | — | nominal awal = nilai pesanan |
| Detail pesanan › kartu kredit (`OrderCreditHold`, `section-card section-pad`) | — | `section-pad` | lencana "Tahan kredit" + "sejak … · saat …" satu bilah; tombol di bilah sendiri | tanpa `order.update`: "Periksa ulang dilakukan pemegang akses mengubah pesanan." | `status-pill status-rejected` + perisai | — | — | kartu tidak tampil bila tidak ditahan, tanpa izin dipakai, dan bukan bayar-dulu |
| Keuangan › Piutang › Kredit & Plafon › **Izin Kredit** | 9 kolom `data-table head-wrap` di `table-wrap overflow-x-auto`, kolom "Keputusan" `col-sticky-end`; **perlu dinilai di 1024 px** | `section-head` + `section-body` | judul + ikon saja | — | `status-pill` + ikon (Menunggu/Disetujui/Ditolak/Dibatalkan/Kedaluwarsa) via `docStatusLabel` | kotak cari + pager (tetap) + tab status | tanpa approve: "Menunggu pemutus izin kredit"; tanpa `view`: satu kalimat, tidak memanggil server | satu kosong per tab |
| Kartu pelanggan › Kontrol Kredit + riwayat "Izin Kredit" | baris riwayat (bukan tabel) | tetap | tetap | — | `status-pill` status-done/rejected/pending | — | tombol "Ajukan izin kredit" bagi `credit_override.create`, selain itu kalimat | — |
| Sub-status pesanan (`SubStatusChips`) | — | — | — | — | "Tahan kredit" = `status-pill status-rejected` + ikon | — | — | — |

Token `kn-*`/`text-fs-*` di kode baru (tanpa hex baru), tombol `btn-sm` + `whitespace-nowrap`, tanpa `type="date"`.
`audit_create_modal` 6 → 5 (pop-up buatan sendiri `OverrideModal` diganti `FormModal`), `audit_i18n_id` 103 → 102.

## Menyimpang dari blueprint

1. **Aksi kontrol dua orang**: spesifikasi menambah aksi `izin_kredit`; KF-T6 sudah punya aksi yang sama persis
   (`lewat_batas_kredit`, kelompok C, awal "1", bernominal, titik keputusan izin kredit). Menambah aksi kedua = dua kunci
   untuk satu kontrol (L5) dan nilai tersimpan `kontrol.lewat_batas_kredit.*` hilang. Aksi lama dipakai, labelnya diganti
   **"Izin kredit"**. U6 memakai `kontrol.lewat_batas_kredit.min_orang`. Usulan koreksi teks unit: "Aksi `izin_kredit`
   ditambahkan ke `KONTROL_AKSI`…" → "Aksi `lewat_batas_kredit` (KF-T6) dilabeli ulang "Izin kredit"…"; U6 "lalu
   `kontrol.lewat_batas_kredit.min_orang` = 2 …"; tabel endpoint `tolak_bila_pelaku_sama("lewat_batas_kredit", …)`.
2. **Cadangan `data_lama` CR-T1 TIDAK dihapus** (langkah 5): penanda migrasi `crt1_profil_kredit` belum dipasang di data
   nyata (H3). Menghapus cadangan sebelum `migrate_credit_profiles.py --terapkan` membuka blokir & plafon pelanggan lama
   tanpa jejak; cadangan mati sendiri begitu skrip dijalankan. Docstring modul diperbarui.
3. **Pembungkus `request-credit-approval` tidak lagi menyetel `credit_hold: true`**: tanda tunggal "Tahan kredit" hanya dari
   gerbang (spesifikasi "Data"); entri `kredit` menunggu sudah menahan `confirm_core`. `reason_code` kosong → "Lainnya"
   + catatan (panel pesanan lama tidak mengirim kode alasan). Keputusan entri `kredit` memutus izinnya lewat layanan yang
   sama (wewenang sudah dinilai jenis `sales_order.kredit`); izin yang sudah diputus di panel tidak diputus ulang.
4. **`credit_override.view` juga untuk MD dan Admin Sample**: keduanya memegang `customer.view` hari ini (tabel spesifikasi
   hanya menyebut lima peran) — supaya setara akses.
5. **Tab Kredit & Plafon**: endpoint utamanya kini `credit_override.view`, jadi tab juga dibuka modul pemegang sumber daya
   itu (nav `sales_force` + `credit-overrides`, aturan MN-T1); pembaca pelanggan tetap membuka tab (panel profil kredit
   CR-T1); tanpa `credit_override.view` panel izin menulis satu kalimat dan tidak memanggil server.
6. **Teks checkout**: "Keranjang disimpan. Setelah izin disetujui, buka lagi dari Pesanan tertunda." tidak dipakai — layar
   "Pesanan tertunda" tidak ada (antrean = CR-T5) dan keranjang tidak disimpan; diganti kalimat yang benar ("Isi keranjang
   tetap di layar ini; setelah izin disetujui, tekan Buat Sales Order lagi."). Isi permintaan tetap tersimpan di
   `credit_gate_rejections.payload_snapshot` untuk CR-T5.
7. **Status penolakan `kedaluwarsa`** belum diisi otomatis (tidak ada job); `terbuka` → `dilanjutkan` saat izin pelanggan
   itu di PT itu disetujui. `tolak` (termin) tidak membuat dokumen penolakan (U12 tidak memintanya; pengguna cukup memilih
   termin lain).
8. **Pratinjau `credit-status`**: `level` dari hasil mentah (sebelum izin/bayar-dulu), `blocked` dari hasil akhir — layar
   lama tetap benar (izin disetujui → "terblokir, tapi ada izin"), dan pelanggan tertahan yang memilih CBD tidak terkunci.
9. **`dispatch_guard` juga dipakai cek kesiapan trip** (`trip_service.trip_check`): saat titik `surat_jalan` menyala,
   pemeriksaan kesiapan pun bisa menahan pesanan (pagar satu pintu, perilaku spesifikasi).
10. Tambahan kecil: `use_override(…, order_number)` (jejak pakai bernomor, bukan id); `credit_override_used` di pesanan
    (layar tanpa id teknis); `evaluate(…, saldo=)` untuk skrip baca-saja; idempotensi `/api/credit-overrides` + pola pengajuan
    (N4); antrean ringkas `credit_override` menghitung izin lingkup pesanan tanpa entri pesanan; ekspor berizin
    `credit_override.view`.

## Asumsi

- `ASUMSI` unit: bawaan = perilaku hari ini (hanya `pesanan_dibuat`; izin tanpa kedaluwarsa; tunai tidak ditahan); K-27 tidak
  untuk blokir manual; benih alasan tiga kode; KP-T4 ADA di HEAD → keputusan memakai `assert_can_decide("credit_override")`
  (bukan sisa pekerjaan).
- `ASUMSI` (`00` §4.1): pesanan bertermin tunai tanpa DP tetap di luar eksposur (perilaku CR-T2) kecuali
  `finance.tahan_kirim_tunai` menyala; saat menyala SEMUA tagihan tunai terkirim yang belum lunas dihitung (sesudah kunci
  menyala, kiriman tunai belum lunas hanya bisa lewat pengecualian berizin).
- `ASUMSI`: pesanan baru dinilai dengan nilai penuhnya (sama dengan gerbang lama, juga untuk termin tunai); pesanan yang sudah
  ada dinilai dengan bagiannya di saldo (`this_order`); izin lingkup pelanggan harus bersisa ≥ sisa tagihan pesanan;
  "eksposur tanpa pesanan ini ≥ plafon" dipertahankan (aturan lama "piutang ≥ plafon").
- `ASUMSI`: `pesanan_diubah` dinilai sesudah override/amandemen tersimpan bila nilai tagihan (termasuk tagihan tambahan
  nota debit) naik atau `net_days` termin baru lebih besar; ganti termin ke luar daftar ditolak sebelum disimpan.
- `ASUMSI`: pemeriksaan ulang pesanan yang ditahan mengabaikan sakelar titik (tahanan harus bisa lepas walau titik
  dimatikan); dipicu tiap `refresh` saldo hari ini.

## Pertanyaan H5 untuk `STATUS.md` (tidak diubah pelaksana — diteruskan integrator)

"CR-T3: titik periksa kredit mana yang dinyalakan untuk PT nyata (bawaan hanya 'pesanan dibuat')? Pilihan: (a) tetap; (b)
+ 'nilai pesanan naik'; (c) keempatnya — usulan rancangan; juga masa berlaku izin (bawaan 0 = tanpa batas; usulan 3 hari)
dan 'Tahan pengiriman pesanan tunai sampai lunas' (bawaan mati). Usulan: (b) + 3 hari dulu di satu PT sesudah daftar
`scripts/crt3_beda_gerbang_kredit.py` dicocokkan pemilik."

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`efc1cc6`** — satu gate
untuk CR-T3 ((a) `2ac8e6c` · (b) `945da6e` · cek layar `eaba57f`), PY-T5 (`b014a38`), PY-T4 (`61cf7a1` · cek layar `efc1cc6`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`fc95d36`: 12 / 39). Kuitansi: `bukti/CR-T3/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- (a) dari keadaan (a) tergabung (basis `c3fa3f8`) digabung tiga arah ke HEAD `41c0b60` tanpa bentrok (`test_KFT4_registry.py`,
  `view_main_permission.json`, KN_32 tergabung bersih) → **`2ac8e6c`**; `tests_mem` (a) **2183/2/2**, 0 gagal (integrator — gabung sendiri). (b) = pohon T pelaksana persis
  (dicek per berkas: 70 berkas sama, tidak ada berkas lebih/kurang) → **`945da6e`**; `tests_mem` T **2199/2/2** dan jest 1040
  (pelaksana) — tidak diulang integrator (arahan pemilik 15 Nov: tanpa uji ganda pada pohon identik).
- Lingkungan A (data acuan sesudah `restore_demo`, kode `945da6e`): lapis A **U17 lulus** (`test_bp_CRT3_izin_bersamaan.py`);
  `scripts/crt3_beda_gerbang_kredit.py` (baca-saja): **6 pasangan pelanggan/PT diperiksa · 0 berbeda** hasil gerbang lama vs
  baru (`bukti/CR-T3/integrator_beda_gerbang_data_acuan.txt`); indeks wajib **36/36**. **H5: semua titik periksa bawaan =
  perilaku hari ini; tidak ada yang dinyalakan.**
- Uji jalan **U18** (integrator; dua izin kredit diajukan lewat API di database uji): **cacat ditemukan dan diperbaiki
  (`eaba57f`)** — tabel Izin Kredit 9 kolom = 1007 px di kartu ±732 px (1024) dan 988 px (1280): kolom Alasan tertutup kolom
  Keputusan lekat, Pemohon/Status di balik gulir. Kini 5 kolom (Pelanggan · lingkup | Nominal · sisa · berlaku sampai |
  Alasan · pemohon | Status ikon+teks | Keputusan lekat) = **732 / 988 px**; jest CR-T3 6/6 tetap hijau
  (`bukti/CR-T3/cek_izin_kredit_*.png`). Kotak kredit checkout dan kartu kredit detail pesanan dicakup jest, tidak dipotret.

Pelaksana (catatan asli):

Belum dijalankan (`gate.sh --quick` / penuh dijalankan integrator di lingkungan A).

## Angka uji

| Rangkaian | Sebelum | Sesudah |
|---|---|---|
| `tests_mem` W | basis `53b419b` **2045 lulus / 2 dilewati / 2 xfail** (`bukti/CR-T3/tests_mem_base_tm.txt`) | (a) **2102 / 2 / 2** (salinan lengkap basis + 30 berkas (a), `tests_mem_a_tree_tm.txt`); (b) **2118 / 2 / 2** (`tests_mem_b_tm.txt`; +48 (a) +9 putaran KF-T8 +16 (b)) |
| `tests_mem` (a) tergabung `c3fa3f8` | HEAD 2101 (diturunkan) | **2158 / 2 / 2** (`tests_mem_am_tm.txt`) |
| `tests_mem` T (`fc95d36`, akhir) | HEAD 2126 (diturunkan = 2199 − 73) | **2199 lulus / 2 dilewati / 2 xfail** (`tests_mem_T.txt`) |
| jest W (3 folder + seluruh `src`) | basis **995 lulus**; 35 suite gagal dimuat (`cmdk`/`@radix-ui`, lingkungan) | (a) **995**; (b) **1001** (+6 `crt3GerbangKredit`); 35 suite sama |
| jest T (`fc95d36`) | HEAD **1034** (35 suite gagal dimuat) | **1040** (35 suite sama) |

Penjaga statik (`hitung_penjaga.sh`, basis → W (b); HEAD `fc95d36` → T): auth 26 → 26 · ui_standard 13 → 13 (HEAD 11 → 11) ·
i18n **103 → 102** · create_modal **6 → 5** · page_tabs 1 → 1 · to_list 5 → 5 · entity_label 2 → 2 · lainnya PASS/0
(`bukti/CR-T3/penjaga_*.txt`, `T_penjaga*.txt`, `HEAD_penjaga.txt`). `verify_role_gate_ui` 31/0 (tidak naik);
`verify_atomic_claim` 161/0 + `--self-test` 64 hijau (inventaris multi-koleksi dibangkitkan ulang: 124 → 123 baris);
`verify_posting_coverage` 138/0; `verify_cash_single_door` 739/0 (T 743/0); `verify_detail_modal` 30/0 (T 29/0 = HEAD);
`verify_payment_vocab` 1834/0 (T 1842/0); `verify_permission_checked` 615/0 (T 617/0); `verify_access_catalog_nav` 0;
`verify_money_idempotency` 19/0; `verify_config_fallback` 160/0 (+`--entity` 160/0); `verify_config_text` 3395/0 (T 3465/0);
`audit_config_wiring --strict` hijau; `check_nav_map` PASS; `verify_codebase_map` PASS; `tests/test_fe03_access_catalog.py
--noconftest` 6/6.

## Penggabungan

- Keadaan (a): `$S/CR-T3_a_state/` (basis `53b419b`, 30 berkas + `FILES.txt` + `BASIS.txt`) dan `$S/CR-T3_a_merged/`
  (HEAD saat (a) selesai = `c3fa3f8`; bentrok `permissions_config.py` (KM-T2 + CR-T3), `test_KFT1_izin_pengaturan.py`
  (`PYT3_KUNCI` + `CRT3_KUNCI`), `test_PRT9_izin_bawaan.py` (KM-T2 + CR-T3) — keduanya dipertahankan; dibangkitkan ulang
  `CODEBASE_MAP.md`, `configKeyIndex.json`, fixture akses).
- (b) digabung ke worktree tujuan pada HEAD **`fc95d36`** (`[CR-T4]`; sebelumnya `b7837de` (MN-T2) — digabung ulang karena
  HEAD bergerak; skrip `$S/crt3_gabung_T.sh`), lalu T dipindah ke **`41c0b60`** (dua commit dokumen/STATUS, tanpa berkas
  bersama — 70 berkas gabungan disalin apa adanya, `CODEBASE_MAP.md` dibangkitkan ulang sama, `configKeyIndex.json`
  selaras). 70 berkas: 35 sama di HEAD dan basis → disalin; 15 baru; 10 tergabung
  bersih (`ENTITY_REGISTRY.md`, `access_modules.py`, `config_registry.py`, `entity_scope.py`, `credit_profile_service.py`
  (CR-T4), `test_KFT4_registry.py` (CR-T4), `view_main_permission.json` (MN-T2), `CreditProfileRequestModal.jsx`,
  `CustomerCreditTab.jsx` (CR-T4), `scripts/verify_contract.py`); bentrok (tambahan berdampingan, KEDUA sisi dipertahankan):

| Berkas | Bentrok | Keputusan |
|---|---|---|
| `backend/permissions_config.py` | blok KM-T2 vs blok CR-T3 di akhir berkas | HEAD + blok CR-T3 |
| `backend/tests_mem/test_KFT1_izin_pengaturan.py` | `PYT3_KUNCI` vs `CRT3_KUNCI`; rumus jumlah U04 | keduanya; `… + PYT3_KUNCI + CRT3_KUNCI` |
| `backend/tests_mem/test_PRT9_izin_bawaan.py` | KM-T2 vs CR-T3 (`TAMBAHAN_SESUDAH`) | keduanya |
| `backend/indexes.py` | `ID_INDEX_COLLECTIONS`: PY-T3 (`hr_holidays`, …) vs CR-T3 `credit_gate_rejections` | keduanya |
| `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | §9.23 KM-T2 … §9.26 CR-T4 vs §9.23 CR-T3 | bagian CR-T3 = **§9.27** |
| `memory/PRD.md`, `scripts/INDEX.md` | butir di tempat yang sama (CR-T4 / PY-T3) | keduanya |
| `CODEBASE_MAP.md`, `configKeyIndex.json`, fixture akses, `memory/INVENTARIS_MULTI_KOLEKSI_2026-09.md` | berkas bangkitan | dibangkitkan ulang di T |

- Draf laporan + bukti hanya di W.

## Yang perlu direview

Menyimpang 1 (aksi kontrol dipakai ulang), 2 (cadangan `data_lama` dipertahankan — H3), 3 (pembungkus tanpa
`credit_hold`), 5 (nav tab Kredit & Plafon), 9 (cek kesiapan trip ikut menahan); kolom panel Izin Kredit di 1024 px; U17
lapis A dan uji jalan U18 belum dijalankan; daftar pelanggan berubah hasil (skrip) di data acuan.

Status: implemented_pending_review.
