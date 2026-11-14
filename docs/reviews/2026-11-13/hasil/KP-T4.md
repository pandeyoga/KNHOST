# KP-T4 — Satu tabel kebijakan persetujuan untuk semua antrean

- Commit awal: `494a249` (dikerjakan) · digabung di atas `4db17eb` (sesudah PR-T3, PR-T4, PR-T7, KF-T2)        - Commit akhir: (a) `ff73676` · (b) `0c5486e` · perbaikan sesudah gate `884c8d0` · koreksi blueprint `d0c92d3`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-06, KP-07, KP-25, KP-26, PR-05 (bahan PR-UX-02, PR-UX-24) · spesifikasi `docs/blueprint/unit/KP-T4.md`
- Risiko tinggi → dua serah-terima (`00_ATURAN_EKSEKUSI.md` §8): (a) jalur baru + uji, pintu lama belum disentuh;
  (b) pengalihan pintu + pematian jalur lama. SHA (a) `ff73676`, (b) `0c5486e`.

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `494a249`)

| Jangkar spesifikasi | Hasil di `494a249` |
|---|---|
| `approval_backlog_service.py:41` `QUEUES` (38) | Berlaku (38 kunci) |
| A `config_service.py:315` `evaluate_approval`, `role_registry.py:365` | Bergeser ke `config_service.py:572` (KP-T3); `role_satisfies` tetap `:365` |
| B `config_service.py:336` `build_approval_chain` | Bergeser ke `:585`. Hanya dipanggil untuk PO (jenjang tambahan SO/PR tidak pernah dibaca mesin) |
| C `config_divisions.py:83`, `approval_matrix_service.py:196` | `:84` / `:196`. Matriks juga dipakai antrean "Persetujuan Saya" dan papan pesanan khusus |
| D `contra_bon_service.py:988` | `:989`; `rank_of` (peran tak dikenal = 0 → semua lolos) |
| D `interco_service.py:286` | Konstanta di `:53`, dipakai `:290`; nama persis `sales_admin` (bukan +acuan) |
| D `amendment_service.py:729` | `:737`. Admin nama persis + `role_in((need,))`: rentang bawah = Admin ∪ (peran penyetuju + acuannya); peran kustom beracuan Admin hanya di rentang atas (spesifikasi menulis "{…, admin}+acuan") |
| D `rnd_spec_service.py:343`, `makloon_claim_service.py:145` | Berlaku (+ tolak `:224`). `rnd.spec_approval_roles` **juga** dipakai `release_product` dan `special_order_fulfillment.can_release` |
| E `so_approvals.py:204/257`, `sales_orders.py:568/581` | `:203/:257`; `sales_orders.py:595/608` |
| F `cash_advance_service.py:34`, `special_order_service.py:24` | Berlaku. **Beda:** `APPROVAL_THRESHOLD` (Rp10 jt) hanya mengisi field `requires_approval` yang tidak dibaca layar/kode mana pun; pesanan khusus yang diajukan SELALU `pending_approval` dengan tingkat 1 (matriks `levels[0]` tanpa ambang) |
| F `vendor_bills.py:309`, `landed_cost.py:180` | `:310/:372`; `:180` |
| F `marketing_cost_service.py:142` | Berlaku; `role_in` (+acuan, spesifikasi menulis tanpa) |
| F `sample_sale_service.py:41` | **Tidak berlaku** — PR-T2 mengganti daftar dengan izin `sample_order.approve_payment` (pintu sampel kini izin saja) |
| F `crm.py:142` `require_role` | **Tidak berlaku** — PR-T2: izin `credit_override.approve` (`:148`) → mekanisme G |
| G `transfers.py:557` | `:552` |
| PR-05 `purchase_orders.py:809`, `vendor_bills.py:455`, `landed_cost.py:246` | `:819` (+tolak `:938`), `:460` (+`:490`), `:246` (+`:298`) |
| KP-07 `purchase_requisitions.py:188`, `rnd.py:291` | `:188`, `rnd.py:286` (+tolak `:311`, sample `:714`) |
| `t10_setuju_tanpa_izin.py` | Dijalankan di `494a249`: Manajer Kosong menyetujui PO Rp250 jt & tagihan Rp75 jt → 200, 200 |

**Temuan baru (langkah 3, "daftar peran yang belum ada di tabel unit ini") → baris bawaan:**
1. `POST /api/sales-orders/{id}/approve` (`sales_orders_extra.py:461`, `role_satisfies(required_approval_role)`) — pintu kedua
   persetujuan nilai SO.
2. Entri `nilai` penanda validasi (`so_lifecycle_service.submit_core`): dibuat dengan peran `manager` walau aturan SO tidak
   menuntut persetujuan → sub-jenis `sales_order.validasi` (≥ Manajer).
3. `rnd.spec_approval_roles` untuk rilis produk (`release_product`, `can_release`) → sub-jenis `rnd_spec.rilis` (daftar persis).
4. Pencairan pinjaman antar-PT (`interco_loan_service._approval_gate`) memakai kunci `antar_entitas.*` dengan peta peringkat
   pribadi `{manager 1, admin 2}` → jenis `interco_loan` (`queue_key` kosong: bukan antrean; INV-APPR-01 G menerima
   kosong ber-`note`).
5. PR: matriks juga menjaga persetujuan PR di bawah ambang (setuju draf langsung) → aturan "rentang terendah" di `can_decide`.
6. Di luar antrean (tidak diubah, usulan): `finance_case_service._assert_authority` (`role_in`); batas nominal hapus sisa
   `payment.variance_writeoff_max_amount` dengan pengecualian nama `admin` (→ PK-38).

## KP-06 / KP-07 / KP-25 / KP-26 / PR-05

- Berlaku di HEAD: ya (tabel di atas; `t10` 200/200; uji merah di bawah).
- Akar masalah: siapa yang memutus tersebar di tujuh mekanisme (peringkat `approval_rules`, jenjang tambahan, matriks
  divisi nama persis, kunci registry per modul, entri SO ditulis mati, rantai/ambang di kode, izin saja); tiga pintu
  (PO, tagihan pemasok, voucher biaya masuk) hanya memeriksa peringkat tanpa izin; satu keputusan dinilai dua daftar.
- Perubahan perilaku (sebelum → sesudah):
  - Semua pintu bertanya `approval_policy_service.can_decide(doc_kind, PT, nilai, aktor, jenjang)`: boleh = izin setujui jenis
    itu **dan** (`any_holder` atau peran ∈ `roles` rentang yang memuat nilai). Tanpa peringkat, tanpa peran acuan.
  - PR-05: PO / tagihan pemasok (+kampanye) / voucher biaya masuk kini butuh izin `approve|reject` → Manajer Kosong **403**
    "Anda belum punya akses untuk menyetujui Pesanan Pembelian. Minta Admin menambahkan akses 'Pembelian & Pengadaan'."
    (dulu 200); pesan 403 tidak lagi memuat id peran.
  - Pesan batas: "Pesanan Pembelian senilai Rp150.000.000 pada jenjang 1 diputus oleh Admin, Manajer atau … Peran Anda
    belum tercantum di Aturan Persetujuan." (satu pesan, dari tabel — PR tidak lagi dua pesan matriks + peringkat).
  - KP-07: ACC desain/PR/ACC sample/rilis produk satu baris per jenis (`rnd_spec` = matriks ∩ daftar; jalur internal sample →
    ACC spesifikasi kini memakai baris yang sama).
  - KP-25: `APPROVAL_THRESHOLD` dihapus; field tampilan `requires_approval`/`approval_threshold` pesanan khusus dari tabel.
    Pesanan khusus yang diajukan pada nilai yang menurut tabel tidak butuh persetujuan → **disetujui otomatis**
    (`approved_automatically`, jejak `approval_matrix_log`). Bawaan: jenjang 1 selalu berlaku = perilaku hari ini.
  - KP-26: uang muka — jenjang & status dari tabel (`level_status`: 1 `pending_atasan`, 2 `pending_pimpinan`, 3
    `pending_finance`); jenjang tanpa baris dilewati; daftar & pengecualian nama admin di kode dicabut.
  - `evaluate_approval` / `build_approval_chain` = pembungkus `required_levels` (`required_role` = nilai kompatibel
    `legacy_role` untuk tampilan/notifikasi). Rantai baru menyimpan `roles`, `rule_id`, `policy_kind` (D3).
  - Pintu "izin saja" (24 pintu setuju + tolak opname, putus susut makloon, transisi nilai desain; lewat batas kredit lewat `assert_can_decide`)
    memanggil `guard_door` → baris bawaan "Semua pemegang akses" (tidak ada keputusan berubah; bila Admin membatasi peran,
    pintu ikut).
  - `POST/PATCH/DELETE /api/approval-rules` → **410** "Aturan Persetujuan kini diatur per jenis dokumen di Pengaturan ›
    Persetujuan › Aturan Persetujuan …"; GET tetap (riwayat, Master per PT). 17 kunci → `not_used` (U14).
  - Layar Aturan Persetujuan baru (lihat "Layar"); layar PO/tagihan/voucher/uang muka/pesanan khusus menanyakan
    `GET /api/approval-policies/can-decide/me` (bukan `roleSatisfies`/`roleIs` di layar).
- Data: `approval_policies` (+ indeks `(doc_kind, entity_id, level, sort)`, `uq_id`, SCOPED dengan baris `all`, kanonik
  `verify_contract`). **Tanpa baris tersimpan** → baris bawaan dihitung dari sumber lama dengan nilai efektif PT (sumber
  `bawaan`), sehingga pemasangan kode tanpa migrasi tidak mengubah keputusan siapa pun (dibuktikan U2 dua kali).
  Migrasi `scripts/migrate_kpt4_kebijakan_persetujuan.py` (bawaan hanya-lapor, `--apply` menulis; argumen asing → keluar 2
  sebelum menyentuh database) — **hanya dijalankan di lingkungan B** (`bukti/KP-T4/skrip_migrasi_lingkungan_b.log`: 58
  baris, 48 jenis, peran kustom beracuan Manajer diberi `purchase_order|vendor_bill|landed_cost.approve|reject`; jalan
  kedua 0 tulis). Tidak dijalankan (juga mode lapor) terhadap database `backend/.env` (H3).
- Izin (K-47): `DEFAULT_PERMISSIONS["finance"]["vendor_bill"] = ["approve", "reject"]` (tanpa `view`; Finance dulu menyetujui
  tagihan kampanye lewat nama peran; baris `vendor_bill` biasa tetap ≥ Manajer). PR-T9 `TAMBAHAN_SESUDAH` disesuaikan;
  fixture `access_builtin_fixture.json` dibangkitkan ulang (`tests/fe03_access_fixture.py`), `test_fe03_access_catalog` 6/6.
- Commit: —
- Status: implemented_pending_review (draf; menunggu commit & gate)

## Pembagian serah-terima

**(a) model, pembaca, uji setara — pintu lama belum disentuh** (16 berkas; salinan utuh `<scratch>/kpt4_a_state/`; diuji di
salinan HEAD + keadaan (a): `tests_mem` 369/2/3).

| Berkas | Isi |
|---|---|
| `backend/approval_kinds.py` (baru) | Katalog jenis dokumen: 38 antrean + sub-jenis (label, kelompok, `queue_key`, izin setujui/tolak, field nominal, `level_status`) |
| `backend/services/approval_policy_service.py` (baru) | `default_rows_for`/`build_default_rows`, `rows_for`, `required_levels`, `can_decide`/`assert_can_decide`, `who_can_decide`, `policy_view`, `check_view`, peringatan (celah, tumpang-tindih, lebih longgar dari grup, peran tanpa izin) |
| `backend/routers/approval_policies.py` (baru) + `server.py` | `GET /kinds`, `GET ?entity_id=&doc_kind=`, `GET /check` (izin `settings.view`, pesan Z6, PT lewat `resolve_requested_entity`) |
| `indexes.py`, `entity_scope.py`, `scripts/verify_contract.py` | koleksi `approval_policies` |
| `scripts/guardrails/verify_approval_queues.py` | INV-APPR-01 aturan G + 3 kasus bukti-merah |
| `scripts/migrate_kpt4_kebijakan_persetujuan.py` (baru) | lapor / `--apply` (rencana: baris per jenis × PT, izin butir 4, peringatan, nilai 17 kunci) |
| `frontend/src/features/settings/ApprovalPoliciesView.jsx`, `approvalPolicyHelpers.js` (baru); `ApprovalRulesSettings.jsx` | layar hanya-baca di atas isi KP-T3 |
| `backend/tests_mem/test_KPT4a_setara.py`, `frontend/src/features/__tests__/kpt4ApprovalPolicies.test.js` (baru) | U1–U3, endpoint baca, skrip; uji komponen |
| `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md` | koleksi baru; peta dibangkitkan |

**(b) pengalihan + pematian jalur lama** (daftar lengkap `<scratch>/kpt4_b_files.txt`, 100 butir relatif (a)):

| Langkah | Berkas |
|---|---|
| 5 migrasi tulis + izin | skrip (a); `permissions_config.py` (blok KP-T4 Finance) |
| 6 PR-05 | `routers/purchase_orders.py` (`_po_policy_level`, `_assert_po_policy`), `routers/vendor_bills.py`, `services/marketing_cost_service.py` (`BILL_APPROVER_ROLES` dihapus), `routers/landed_cost.py` |
| 7 A+B, E | `services/config_service.py` (pembungkus), `routers/so_approvals.py` (`so_entry_kind`), `routers/sales_orders_extra.py`, `routers/approval_rules.py` (410) |
| 8 C | `services/approval_matrix_service.py` (`STAGE_KIND`, `levels_for`/`evaluate`/`guard` dari tabel, mode/cakupan pensiun), `config_divisions.py` (`levels` dihapus), `services/approval_backlog_service.py`, `services/purchase_requisition_service.py`, `services/rnd_spec_service.py`, `services/special_order_fulfillment.py`, `services/special_order_service.py` (`APPROVAL_THRESHOLD` dihapus), `routers/special_orders.py` (setujui otomatis), `bootstrap.py` (benih contoh) |
| 9 F | `services/cash_advance_service.py` (`APPROVAL_STAGES` dihapus), `routers/crm.py` |
| 10 D + kunci | `services/amendment_service.py` (`approval_amount`, `policy_snapshot` dari tabel), `interco_service.py`, `interco_loan_service.py`, `contra_bon_service.py`, `payment_variance_service.py`, `makloon_claim_service.py`, `contract_service.py`; 8 `config_catalog_*.py` (17 kunci `not_used`) |
| 10 G | 22 router, 25 panggilan `guard_door` (pintu "izin saja") |
| 11 tulis + layar | `approval_policies.py` (PUT, DELETE, `can-decide/me`, peran di `/kinds`), `approval_policy_service.py` (`replace_rows`, `delete_pt_rows`, `chain_for`, `guard_door`, konstanta `BAWAAN_*`); layar `ApprovalRulesSettings.jsx` (penuh), `ApprovalPolicyEditor.jsx`, `hooks/useCanDecide.js`, `PurchaseApprovalView`, `VendorBillsView`/`DetailPanel`, `LandedCostView`/`DetailPanel`, `CashAdvanceDetail`, `SpecialOrderDetail`, `DivisionsView` (tautan), `ContraBonDetailPanel` (teks); `ApprovalEffectiveTiers.jsx`, `ApprovalRuleForm.jsx` **dihapus** |
| uji & dokumen | `test_KPT4b_pengalihan.py`, `tests/test_bp_KPT4_dua_penyetuju.py` (baru); disesuaikan: `test_KPT3_aturan_persetujuan.py`, `test_KFT1_izin_pengaturan.py` (`KPT4_TIDAK_DIPAKAI = 10`), `test_PRT9_izin_bawaan.py`, lapis A `test_iter273/274`, `test_uat_v3_ui_gaps3.py`, POC `test_g1/g3/g7/fase_d_makloon/core_e8`; jest `kpt3ApprovalTiers`, `phase3Settings`, `pk13MoneyConfirm`; `memory/PRD.md`, `KN_32` (jenjang), `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md` |

## Uji penerimaan

`backend/tests_mem/test_KPT4a_setara.py` (a), `test_KPT4b_pengalihan.py` (b); merah = kode `494a249` dan keadaan (a)
(`bukti/KP-T4/tests_mem_KPT4_merah_HEAD_dan_a.log`), hijau = (a)+(b) (`tests_mem_KPT4_hijau.log`).

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | B | ya (modul tidak ada) | Lulus — 58 baris bawaan; 38/38 antrean; PO J1 ≥ Rp100.000.000 (≥ Manajer, tanpa Finance), J2 ≥ Rp500.000.000 "Direksi" {Admin} |
| U2 | B | ya | Lulus — **14.670 kombinasi, 0 selisih** (48 jenis × 15 id peran × 10 nilai × 2 PT × jenjang yang ada) di baris tersimpan + **7.170 kombinasi, 0 selisih** di sumber `bawaan`; uji mutasi (kampanye tanpa peran acuan) → 20 selisih (penguji membedakan) |
| U3 | B | ya | Lulus — 20 pasangan, jumlah & label jenjang sama |
| U4 | B | ya (200) | Lulus — 403 `batas`, tanpa id peran / kata "role" |
| U5 | B | ya | Lulus — `ent_ksc` 200 (`pending`), `ent_kanda` 403 |
| U6 | B | ya (200 ×3) | Lulus — 403 `izin` ×3 |
| U7 | B | ya (skrip tidak ada) | Lulus — laporan memberi `purchase_order.approve|reject`; PO Rp150 jt `ent_kanda` 200 |
| U8 | B | ya | Lulus — `ent_kanda` 200 `approved`; `ent_ksc` 403 (persiapan tambahan: lihat Menyimpang) |
| U9 | B | ya | Lulus — langsung `approved` |
| U10 | B | ya | Lulus dengan harapan terkoreksi (Menyimpang #1) |
| U11 | B | ya (404) | Lulus — 400 alasan; 400 peran; 400 rentang; 400 nominal; 409 versi basi |
| U12 | B | tidak (perilaku lama tetap) | Lulus — 200 (J1, tetap menunggu J2) lalu 200 `pending` |
| U13 | B | ya | Lulus — 403 satu pesan dari tabel → 200 `approved` |
| U14 | B | ya | Lulus — 17 kunci `not_used`, alasan menyebut Aturan Persetujuan |
| U15 | A | — | **Lulus** di lingkungan A (MongoDB 7 asli, backend `884c8d0`, data acuan sesudah gate): dua manajer menyetujui PO yang sama bersamaan → satu menang (`backend/tests/test_bp_KPT4_dua_penyetuju.py`) |
| U16 | layar | ya (komponen tidak ada) | Uji komponen 8/8 (`kpt4ApprovalPolicies.test.js`: kartu Uang Muka PT Kanda tiga jenjang, lencana, Coba nilai, galat/coba lagi, Ubah/Buat khusus/Kembali ke grup, baca-saja). **Belum diuji jalan di peramban** |
| tambahan | B | ya | pintu "izin saja" (transfer) ikut tabel lalu kembali ke grup; `can-decide/me` untuk tombol |

`t10_setuju_tanpa_izin.py` (bukti audit, dijalankan apa adanya): `494a249` 200/200 → sesudah **403/403** (pesan izin Z6).

`backend/tests_mem` seluruhnya: **HEAD 364 lulus / 2 dilewati / 3 xfail → (a) 369 / 2 / 3 → (a)+(b) 382 / 2 / 3** di
salinan kerja. Sesudah digabung: HEAD `4db17eb` **415** → (a) `ff73676` **420** → (b) `0c5486e` **433** lulus / 2 / 3.
Jest sesudah digabung (`src/config`, `src/features`, `src/hooks`, `src/components`): 468/468 uji lulus; 34 suite gagal
dimuat karena `@radix-ui/primitive/is-development` (kendala lingkungan). Lapis A lain yang menyentuh persetujuan/izin
(KP-T3, iter273, KF-T6, PR-T3, PR-T4, PR-T7, KF-T2) dijalankan ulang di lingkungan A: lulus.

## Penggabungan

Unit dikerjakan di atas `494a249`; sementara itu PR-T3, PR-T4, PR-T7, KF-T2 dan perbaikan susulan KF-T6/KP-T3 masuk.
Penggabungan tiga arah per berkas (basis `494a249` untuk (a), keadaan (a) untuk (b)). Penyesuaian yang perlu:

| Tempat | Sebab | Penyelesaian |
|---|---|---|
| `approval_kinds.py` + `test_KPT4a_setara.py` U1 | Antrean `journal_proposal` lahir di perbaikan susulan KF-T6 (`8b5fdea`), sesudah KP-T4 dirancang; INV-APPR-01 aturan G menuntut tiap antrean punya jenis | Jenis baru `journal_proposal` (izin `accounting.create`, nominal `total_debit`, mekanisme G); U1 38 → 39 antrean, alasan tertulis |
| `contra_bon_service.CFG_KEYS`, `config_catalog_contrabon.py` | KF-T2 membuang `qty_tolerance_percent`; KP-T4 membuang tiga kunci persetujuan | Keduanya dibuang; alasan `not_used` masing-masing tetap |
| `approval_matrix_service.py` | KF-T2 mengganti cadangan `po_custom_direksi_min` dengan `default_of`; KP-T4 memindah ambang Direksi ke baris tabel | Bentuk KP-T4 (baris bawaan membaca kunci lewat resolver → bawaan registry 50 jt); uji KF-T2 U10b disesuaikan ke `evaluate` asinkron, harapannya tetap |
| `rnd_spec_service.py` | PR-T7 menambah `role_allowed` (bendera `caps` di rincian sample); KP-T4 mengganti `_assert_role` dengan `can_decide` | Satu pembantu `_decision` dipakai keduanya, jadi tombol dan pemeriksa server tetap sepakat; uji PR-T7 U4/U4b menyiapkan aturan lewat `PUT /api/approval-policies/rnd_sample` (kunci lama 400 `not_used`) |
| `routers/period_unlocks.py` | Impor PR-T3 + KP-T4 | Keduanya |
| `ApprovalRulesSettings.jsx`, `ApprovalEffectiveTiers.jsx` | KP-T4 menulis ulang layar dan menghapus komponen KP-T3; cabang punya perbaikan warna `1da3bde` di versi lama | Versi KP-T4 dipakai; komponen lama dihapus |
| `test_KFT1_izin_pengaturan.py`, `test_PRT9_izin_bawaan.py` | Angka/izin dari PR-T4, KF-T2, KP-T4 | Konstanta dijumlahkan (kunci yang dimatikan tidak tumpang tindih); `TAMBAHAN_SESUDAH` digabung |

Garis dasar `verify_role_gate_ui` dikencangkan sesudah (b): **25 → 19 gerbang, 19 → 16 berkas** (`CashAdvanceDetail`,
`LandedCostView`, `VendorBillsView` 0; `PurchaseApprovalView` 4 → 2). Hitungan penjaga statik berhitung lain sama
dengan sebelum unit, kecuali `audit_i18n_id` 112 → 111 (turun).

Jest: HEAD 35 suite gagal muat (cmdk/radix) / 63 lulus / 442 uji → baru 35 / 64 / 445; daftar suite gagal muat identik.
`phase3Settings` (gagal muat di lokal) dijalankan dengan tiruan `KNSelect` hanya di folder uji: 13/13.

## Contoh angka (nominal; tidak ada jurnal yang berubah)

| Dokumen | Nilai | Baris yang dipakai | Hasil |
|---|---|---|---|
| PO `ent_ksc` (benih) | Rp150.000.000 | J1 [100 jt, ∞) ≥ Manajer; J2 [500 jt, ∞) tidak memuat | 1 jenjang; Manajer boleh, Tanpa Acuan (berizin) 403 batas |
| PO | Rp600.000.000 | J1 + J2 "Direksi" {Admin} | 2 jenjang (U12) |
| PO deviasi harga | Rp50.000.000 | `purchase_order` tanpa jenjang → paksa `purchase_order.deviasi_harga` J1 ≥ Manajer | 1 jenjang |
| Kontrabon `ent_kanda` (uji U2: ambang 10 jt, peran Admin) | Rp9.999.999 / Rp10.000.000 | [0, 10 jt) ≥ Admin; [10 jt, ∞) ≥ Admin | Manajer 403 di keduanya |
| Amandemen (ambang Admin 50 jt) | dampak 30 jt, akumulasi 60 jt | `approval_amount` = 60 jt → rentang [50 jt, ∞) {Admin + acuannya} | Manajer 403 |

## Layar

Pengaturan › Persetujuan › Aturan Persetujuan (menggantikan isi KP-T3): pemilih PT ("Semua PT (aturan grup)" + PT), kelompok
Penjualan/Pembelian/Keuangan/Gudang/R&D/SDM, kartu per jenis (lencana Aturan grup / Aturan khusus PT ini / Aturan bawaan
(belum disimpan); kolom Jenjang · Mulai dari (Rp) · Sampai di bawah (Rp) · Yang boleh menyetujui · Siapa saja yang lolos;
tanda "{peran}: belum punya akses {modul}"; peringatan kuning), tombol Ubah / Buat aturan khusus PT ini / Kembali ke aturan
grup / Coba nilai, keterangan + tautan Kontrol Dua Orang. Pop-up baku `FormModal` (alasan wajib, versi). Tab Divisi:
tautan ke Aturan Persetujuan; kunci "Persetujuan & Ambang" yang pindah tampil "tidak dipakai" beralasan.

## Penjaga statik (sebelum → sesudah, dari salinan; MongoDB sengaja tak terjangkau)

`verify_auth_coverage` 28 → 28 pelanggaran (cek 1740 → 1745; 5 rute baru lolos) · `verify_access_catalog_nav` 0 → 0 ·
`verify_money_idempotency` lulus · `verify_custom_modals` lulus · `verify_ui_standard` 26 → 23 (daftar lengkap; tiga
pelanggaran berkas KP-T3 yang dihapus hilang, tidak ada yang baru) · `verify_error_notice` lulus (283 → 282 cek) ·
`verify_approval_queues` 5 → 5 (226 → 312 cek; pelanggaran sama: `gl.py` usulan jurnal, `initial_registration.py`) +
bukti-merah aturan G · `verify_codebase_map` lulus · `verify_page_tabs` 1 → 1 · `verify_knselect_contract` 0 → 0 ·
`audit_i18n_id --strict` 113 → 112 · `audit_create_modal` 2 → 2 · `audit_config_wiring` "9 kunci bermasalah + 2 editor
ganda" → sama · `config_health` OK 359 / NOT_USED 9 / STALE 4 → 342 / 26 / 4 (17 kunci `not_used`).
Log: `bukti/KP-T4/penjaga_statik.log`.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), sesudah `restore_demo` (data acuan; tiga skrip seed yang sama seperti
garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`0c5486e`) | `--quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| 1 (`0c5486e`) | `--ci` | 42 FAIL | 43 | **1** | 2 |
| 2 (`884c8d0`) | `--quick` | 14 FAIL | 16 | 0 | 2 |
| 2 (`884c8d0`) | `--ci` | 41 FAIL | 43 | 0 | 2 |

Yang lebih merah di jalan 1: **POC FASE E-8 G1** — memeriksa Finance tanpa izin `vendor_bill` sama sekali, padahal unit
ini sengaja memberi Finance `vendor_bill.approve|reject` (K-47, pengganti gerbang nama peran tagihan vendor kampanye;
jenis yang boleh diputus ditentukan Aturan Persetujuan, bawaan hanya `vendor_bill.kampanye`). Harapan POC disesuaikan
dengan alasan tertulis; yang dijaga E8.2 tetap (tanpa buat/ubah/bayar sisi hutang, tanpa `contra_bon`/`landed_cost`).
`884c8d0`, POC 65/65.

## Menyimpang dari blueprint

1. **U10 keliru** (usulan koreksi blueprint, berkas unit tidak diubah): di `494a249` pesanan khusus yang diajukan selalu
   `pending_approval` (tingkat 1 tanpa ambang); `APPROVAL_THRESHOLD` hanya mengisi field yang tidak dibaca. Baris bawaan
   tabel lengkap KP-T4 baris 12 seharusnya "J1 · ≥ 0 · {manager, admin}". Harapan yang benar: "Rp10.000.000 dan
   Rp10.000.000,01 diajukan → `pending_approval`, `pending_approval` (sama dengan hari ini); sesudah PUT J1 mulai 20 jt:
   Rp15 jt → disetujui otomatis (`confirmed`), Rp25 jt → `pending_approval`". Uji memakai harapan ini.
2. **U8 persiapan**: Finance bawaan tidak memegang `cash_advance.approve` → uji menambahkan izin itu lewat matriks
   (fixture). Usulan: tulis "Finance diberi izin setujui uang muka" di persiapan U8.
3. **U2**: "semua peran bawaan + 3 peran uji" = 15 id (Sopir = `driver`, peran bawaan).
4. Sub-jenis tambahan: `sales_order.validasi`, `rnd_spec.rilis`, `interco_loan`, `payment_variance.hapus_sisa` (temuan
   baru di atas). Total 48 jenis.
5. `can_decide` "rentang terendah": nilai yang pada suatu jenjang tidak butuh persetujuan tetap dijaga penyetuju rentang
   terendah jenjang itu (persetujuan lebih awal, mis. PR draf) — setara matriks lama; jenjang tanpa penyetuju sama sekali →
   403 "belum punya penyetuju" (atau potret `roles` dokumen bila ada); jenis tanpa penyetuju sama sekali → cukup izin.
6. Sumber `bawaan` (baris dihitung bila tabel kosong) — tidak disebut spesifikasi; dipakai supaya kode bisa dipasang tanpa
   migrasi tanpa mengubah keputusan. Konsekuensi: 17 kunci beku (tulis ditolak `not_used`) tetapi nilai terakhirnya
   masih membentuk baris bawaan sampai migrasi.
7. Layar keputusan: pada daftar/detail PO, tagihan, voucher tombol yang tidak boleh **disembunyikan** dengan petunjuk dari
   server (dulu juga disembunyikan); uang muka: tombol mati + petunjuk; pesanan khusus: petunjuk.
8. Pintu "izin saja": hanya pintu setuju yang dijangkar spesifikasi (+ tolak opname, putus susut makloon, transisi nilai
   desain, kredit). Pintu tolak jenis G lainnya belum bertanya tabel (bawaan semua pemegang izin → tidak ada keputusan
   berubah; bila Admin membatasi peran jenis G, pintu tolaknya belum ikut) — usulan lanjutan.
9. `DELETE /api/approval-policies/{doc_kind}` menerima `reason` sebagai parameter kueri.
10. Status salah pada setuju/tolak pesanan khusus kini 409 "Pesanan khusus ini tidak sedang menunggu persetujuan." (dulu
    403 bercampur pesan nama peran).
11. `contra_bon` `policy_snapshot.approval_role|high_value_role` kini label peran dari tabel (dulu id).
12. `PUT /supplier-contracts/policy` dengan `claim_approval_roles` → 400 berpesan (layar tidak mengirimnya).
13. Mode/cakupan matriks (`off`/`warn`/`new_only`) pensiun: penegakan selalu dari tabel; PT yang memakainya dihitung tanpa
    irisan matriks saat membentuk baris (ASUMSI spesifikasi), dilaporkan skrip.
14. Uji/POC lama yang menguji perilaku yang sengaja diubah disesuaikan (daftar di tabel (b)); sesudah gate juga POC E-8
    (`884c8d0`, izin putus tagihan Finance).

## Asumsi / keraguan / titik henti

- H3: migrasi tidak dijalankan pada data mana pun selain database tiruan. Bila (b) dipasang di data nyata **tanpa**
  `--apply`, keputusan tetap sama (sumber `bawaan`) **kecuali** peran kustom yang dulu lolos peringkat PO/tagihan/voucher
  tanpa memegang izinnya (mis. beracuan Manajer tanpa modul Pembelian) — mereka baru mendapat izin lewat skrip (butir 4).
  Pemilik perlu menjalankan skrip saat pemasangan.
- `replace_rows` memakai pemeriksaan versi + `update_many` bersyarat; dua PUT bersamaan pada lapisan yang belum punya baris
  bisa sama-sama menulis (tidak diuji di MongoDB asli).
- Dokumen lama yang menunggu di jenjang yang kemudian dihapus Admin (mis. uang muka `pending_pimpinan` sesudah J2 dibuang)
  → 403 "belum punya penyetuju" sampai aturan diisi lagi.
- Admin menyetujui semua jenjang PO/pesanan khusus sekaligus (`approval_matrix_service.is_admin`, nama peran) tetap seperti
  sebelum unit ini (bukan kode baru; di luar lingkup).
- Masih membaca nilai lama untuk tampilan: `config_simulator` "Uji rantai persetujuan" (`approval.extra_levels`),
  `rnd_gate.policy` (daftar R&D), `/approval-rules/effective` — usulan dirapikan.
- Penggabungan: PR-T7 (`roleIs` → izin) kemungkinan menyentuh `CashAdvanceDetail.jsx` (di sini `roleIs` sudah dicabut),
  `VendorBillsView`/`LandedCostView`/`PurchaseApprovalView` (`roleSatisfies` dicabut). PR-T4: `role_registry.py`, `roles.js`,
  `access_modules.py` tidak disentuh; `permissions_config.py` satu blok KP-T4; `bootstrap.py` satu blok (benih contoh).

## Hambatan lingkungan

- Layar belum diuji jalan di peramban (U16 hanya uji komponen). U15 dan gate dijalankan saat penggabungan.
- Jest lokal: 35 suite gagal muat karena `cmdk`/radix (sama dengan HEAD).

## Yang perlu direview

- Semantik `can_decide` (rentang terendah, jenjang kosong, potret), sumber `bawaan`, dan koreksi U10.
- Daftar 48 jenis & baris bawaannya (`approval_policy_service.default_rows_for`) terhadap tabel lengkap spesifikasi.

Status: implemented_pending_review.
