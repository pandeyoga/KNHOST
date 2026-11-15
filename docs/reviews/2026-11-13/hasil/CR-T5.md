# CR-T5 — Daftar kerja "Kredit & Plafon", janji bayar, dan rekening koran pelanggan

- Commit awal: `4580bd9` (worktree kerja, basis B)        - Commit akhir: `d08d664` · cek layar `1315ce6`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke worktree tujuan pada HEAD **`efc1cc6`** (`[PY-T4] Cek layar …`; gabung pertama di `b014a38` sesudah
  CR-T3 (a) `2ac8e6c`, (b) `945da6e`, cek layar `eaba57f` dan PY-T5, lalu dipindah ke `efc1cc6` sesudah PY-T4 `61cf7a1`);
  bentrok diselesaikan, perilaku CR-T3, PY-T4 dan CR-T5 dipertahankan — lihat "Penggabungan"
- ID ditangani: CR-08 (spesifikasi `docs/blueprint/unit/CR-T5.md`; keputusan K-31 "eksposur memuat pesanan belum dikirim
  dan giro belum cair; titipan mengurangi", kunci `ar.eksposur_*` milik CR-T3)
- Risiko **sedang** → satu serah-terima (`00` §8 tidak berlaku).

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`; diperiksa di `4580bd9`)

| Fakta spesifikasi | Hasil di basis B |
|---|---|
| "Piutang" satu layar tanpa tab; MN-T1 menyediakan tab "Kredit & Plafon" (`credit-overrides`) berisi panel izin kredit (`navStructure.js:305`, `AppViewRouter.jsx:180`) | **Bergeser** — hub `ar-aging` sudah enam tab (MN-T1, `hubTabs.js:251`); menu `navStructure.js:299`; `ARAgingView` `AppViewRouter.jsx:198`; tab `credit-overrides` merender `CreditOverridesPanel` + `CreditProfileRequestsPanel` (`:207`) — dipakai, langkah "buat hub" tidak perlu |
| Persetujuan izin kredit di CRM tab "Persetujuan Kredit" (`CrmView.jsx:27`) | **Tidak berlaku** — MN-T1 sudah memindah tab itu ke Piutang › Kredit & Plafon; `CrmView` tinggal tiga tab (Pelanggan · Prospek · Interaksi); Pusat Persetujuan menautkan `targetView: "credit-overrides"` (`approvalInboxData.js:142`) |
| Tindak lanjut punya `promised` + `next_action_date`, tanpa nominal & status janji (`schemas_crm.py:85`, `crm.py:214`) | Berlaku, bergeser — `schemas_crm.py:107`, `add_followup` `crm.py:264`. Ditemukan pemanggil lain: kartu asisten "Catat janji bayar" (`ai_cards._prep_promise`, AG-T3) menaruh tanggal janji di `next_action_date` dan nominal hanya di catatan; tiga form lain juga menawarkan "Dijanjikan bayar" (`CollectionWorklist.jsx`, HP `MobileSalesFlows.jsx`, `MobileCollectionTargets.jsx`) |
| Daftar tagih & pengingat dari surat jalan pertama, dialihkan CR-T2 ke baris tagihan (`customer_service.py:450/:542`) | Berlaku, bergeser — `collection_worklist` `:405`, `collection_reminders` `:495`; sudah dari `report_basis.baris_tagihan` (CR-T2 b) |
| Pengingat jatuh tempo internal H-3, H-1, H, H+1 (`alert_ops_service.py:54/:280`) | Bergeser — konstanta `AR_DUE_SOON_OFFSETS` kini pengaturan `notif.ar_due_soon_offsets` (KP-T7); `job_ar_due_soon` `:287` |
| Kartu pelanggan: riwayat, dokumen, harga khusus, sample, penagihan, override, 50 kwitansi; tanpa rekening koran (`customer_service.py:318`, `Customer360Panel.jsx:18`) | Berlaku, bergeser — `customer_360` `:268`, `HIST_TABS` `:20`; tab Kredit (CR-T1) sudah ada |
| Akun piutang dari pemetaan (`gl_mapping_service.py:71`) | Berlaku — `known_codes` `:71` (per PT, PK-29) |
| Mesin PDF dipanggil langsung dengan isi dokumen (`pdf_service.py:12`) | Berlaku, bergeser — `render_html` diimpor `pdf_service.py:18` dari `pdf_engine.py:352` |
| Nota denda draf didaftar per PT & status (`penalty_service.py:502`) | Berlaku, bergeser `:742` (tanpa saringan pelanggan — ditambah `customer_id`) |
| Modul akses `ar` memuat `ar-aging` (`access_modules.py:134`) | Bergeser `:143`; `credit-overrides` ada di `nav` modul `customer` lewat `_MNT1_NAV_ADD` `:308` |

## Perubahan

| Berkas | Isi |
|---|---|
| `backend/services/credit_desk_service.py` (baru) | `queue(name, entity_ids, actor, page, page_size, q)` dan `summary(...)` (jumlah = `total` tiap antrean, satu pembangun); enam pembangun antrean sesuai tabel spesifikasi; cakupan pelanggan `customer_scope` (sifat peran `data_scope`, aturan `scope_query` = `can_access_customer`); janji bayar `promise_fields` (validasi + kalimat persis), `promise_status` / `with_promise_status` (dihitung saat dibaca); `due_lines` (satu pembaca jatuh tempo `billing_schedule_service.open_lines`); `reminder_text` (templat persis + kode bayar & rekening PM-T2 bila ada); `exposure` (kotak Eksposur — lihat "Menyimpang") |
| `backend/services/customer_statement_service.py` (baru) | `customer_of_journal(je)` (satu pemetaan jurnal → pelanggan: pengakuan penjualan lewat pesanan/surat jalan, kas kwitansi, titipan tunai, deposit, nota kredit/debit, retur, keputusan selisih bayar, kasus keuangan, saldo kredit, titipan mutasi bank, denda; jurnal pembalik → jurnal asal), `statement(...)` (baris jurnal akun `penjualan.piutang` PT itu, aturan tanggal & status = `report_basis.saldo_akun_sen`; bagian `penalties` akun `penjualan.piutang_denda`), `statement_document` / `statement_html` (kop & gaya PT, `pdf_engine.render_html`) |
| `backend/routers/credit_desk.py` (baru) + `server.py` | `GET /api/credit-desk`, `/credit-desk/summary` (`credit_profile.view`), `GET /api/customers/{id}/statement` + `.pdf` (`credit_profile.view` atau `ar_receipt.view`, + `document.print`; `format=html`), `/reminder-text` (`order.view` + `can_collect_customer`), `/exposure` (kotak Eksposur; `customer.view` atau `credit_profile.view` + `can_view_credit`). PT lewat `resolve_requested_entity`; "Semua PT" untuk rekening koran/naskah → 400 "Pilih satu PT untuk rekening koran." |
| `backend/schemas_crm.py`, `routers/crm.py` (`add_followup`, +3 baris) | `promise_date`, `promise_amount` (tipe longgar → 400 berkalimat); `promised` tanpa tanggal/nominal/tanggal lampau → 400, tanpa tulisan |
| `backend/services/customer_service.py` (+6 baris) | `customer_360.collection_followups` + `promise_status`/`promise_paid` (tab Penagihan) |
| `backend/services/ai_cards.py` | kartu asisten "Catat janji bayar": aturan janji yang sama (`promise_fields`) diperiksa saat kartu disiapkan; isi kirim + `promise_date`, `promise_amount` (tanpa ini kartu yang disetujui gagal 400 di endpoint) |
| `backend/services/penalty_service.py`, `routers/payment_plans.py` | `GET /api/penalties?customer_id=` (tab Tagihan › Nota denda) |
| `backend/indexes.py` | indeks kinerja `collection_followups (entity_id, outcome, promise_date)` (bukan wajib) |
| `backend/access_modules.py` | `credit-overrides` pindah dari `nav` modul `customer` ke `ar`; `VIEW_RESOURCE_OVERRIDES` = `credit_profile`, `VIEW_ACTION_REQUIREMENTS` = `credit_profile.view` (di T + `credit_override.view`, lihat "Penggabungan") |
| Layar baru | `features/finance/CreditDeskView.jsx` (tab Kredit & Plafon), `features/finance/creditDeskParts.jsx` (tabel enam antrean, kolom CSV), `features/crm/CustomerExposureBox.jsx`, `CustomerStatementTab.jsx`, `CustomerBillingTab.jsx` (+ `CustomerOverrideSection`), `promiseUi.jsx` (lencana, isian, pop-up "Catat janji bayar") |
| Layar diubah | `Customer360Panel.jsx` (kotak Eksposur, tab baru, Penagihan berlencana janji, isian janji di form tindak lanjut, dua kolom mulai `xl`), `CollectionWorklist.jsx`, HP `MobileSalesFlows.jsx`, `MobileCollectionTargets.jsx` (isian janji wajib), `AppViewRouter.jsx`, `appViewImports.js`, `navMeta.js`, `hubTabs.js` (komentar) |
| Uji | `tests_mem/test_CRT5_meja_kredit.py` (17), jest `features/__tests__/crt5MejaKredit.test.js` (10); disesuaikan: `tests_mem/test_AGT3_kartu_tindakan.py` (U15), jest `prt7TombolIzin.test.js` (U7/U8), `view_main_permission.json`, fixture akses (dibangkitkan) |
| Dokumen | `ENTITY_REGISTRY.md` (`collection_followups`), `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (bagian baru: W §9.27, T §9.30), `CODEBASE_MAP.md` (dibangkitkan). `scripts/INDEX.md` tidak berubah (tanpa skrip baru) |

## Uji penerimaan

Merah di kode lama: **17/17** tests_mem (endpoint 404; U5 kode lama menerima janji tanpa tanggal → 200; U6 `KeyError
promise_date`) — `bukti/CR-T5/merah_kode_lama.txt`; jest **suite gagal** "Cannot find module '../crm/CustomerBillingTab'"
(fitur belum ada) — `bukti/CR-T5/jest_merah_layar_lama.txt`. Hijau 17/17 (`W_hijau_CRT5.txt`), jest 10/10.

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah (404) | lulus — Okt: saldo awal 0; 400.000 → 0 → 600.000 → 500.000; saldo akhir 500.000 = Σ jurnal piutang P ≤ 31 Okt (dihitung ulang dari jurnalnya); pengecoh (pelanggan Q, jurnal manual) tidak tampil |
| U2 | B | merah | lulus — Nov: saldo awal 500.000; satu baris kwitansi 500.000; saldo akhir 0 |
| U3 | B | merah | lulus — `ent_ksc` kosong bersaldo 0; konteks "Semua PT" → 400 "Pilih satu PT untuk rekening koran." |
| U4 | B | merah | lulus — `statement.pdf?format=html` memuat "Rekening Koran Pelanggan", nama PT, "Saldo akhir", "500.000" |
| U5 | B | merah (200, catatan lahir) | lulus — tanpa tanggal 400; tanggal lampau 400; tanpa nominal 400; tidak ada catatan; hasil lain tanpa isian janji 200 |
| U6 | B | merah (`KeyError`) | lulus — 8 Nov `menunggu`; 12 Nov `ingkar` di urutan pertama (di atas janji `ditepati` bertanggal lebih awal); kwitansi 9 Nov 500.000 → `ditepati` |
| U7 | B | merah | lulus — 2 baris (`izin_kredit`, `ubah_profil`), `total == 2`, tertua dulu, umur 10 & 5 hari |
| U8 | B | merah | lulus — 1 baris `pesanan_ditahan` dengan pesan alasan entri persetujuan kredit |
| U9 | B | merah | lulus — satu baris P9: 2 tagihan (yang +5 hari tidak ikut), total 400.000, telat terlama 10 |
| U10 | B | merah | lulus — 2 baris: `lewat` (19 Nov) lalu `mendekati` (30 Nov); +40 hari tidak ikut |
| U11 | B | merah | lulus — angka ringkasan = `total` tiap antrean |
| U12 | B | merah | lulus — `X-Entity-Id: ent_ksc` → `menunggu_keputusan` kosong; antrean tak dikenal → 400 "Antrean tidak dikenal." |
| U13 | B | merah | lulus — `sls` hanya melihat baris pelanggan miliknya |
| U14 | B | merah | lulus — Tanpa Acuan + `credit_profile.view` 200 (antrean & ringkasan); Manajer Kosong 403; Sopir 403 |
| U15 | B | merah | lulus — naskah persis templat, dua baris tagihan, total 400.000 |
| X1 (tambahan) | B | merah | lulus — kotak Eksposur: tujuh baris berlabel persis + denda terpisah; baris dihitung = yang dipakai mesin (W: perilaku `compute_customer_credit`; T: kunci `ar.eksposur_*` + angka = `credit_gate.evaluate`) |
| X2 (tambahan) | B | merah | lulus — nota denda draf yang jadwalnya sudah void bertanda `plan_void` (usul CR-T4) |
| U16 | layar | jest merah (suite gagal dimuat, modul belum ada) | jest `crt5MejaKredit` 10/10: enam chip berlabel persis + jumlah; Finance tanpa "Setujui" (kolom Aksi tidak ada); pemutus Setujui/Tolak + alasan tertulis untuk pengaju sendiri; konfirmasi menyebut pelanggan · PT · nominal; kosong/galat + "Coba lagi"; Semua PT hanya-baca; "Buka kartu pelanggan" membuka kartu di tempat; Salin pengingat; tanda jadwal void; kartu pelanggan 8 tab + janji berlencana + isian janji; kotak Eksposur; Rekening Koran (kolom, saldo awal/akhir, Jejak Dokumen). **Belum diuji jalan** di peramban (PDF terunduh & saldo = layar: integrator) |

### Contoh angka (U1, hitung tangan; unit tidak menjurnal)

Jurnal R1 di `ent_kanda` (akun 1-1200): SJ-1 1 Okt **Dr 400.000** → saldo 400.000; kwitansi KW-1 15 Okt (kas
`ref_type: ar_receipt` → kwitansi milik P) **Cr 400.000** → 0; SJ-2 20 Okt **Dr 600.000** → 600.000; nota kredit NK-1 25 Okt
(`ref.order_id` = S1) **Cr 100.000** → 500.000. Saldo akhir Okt 500.000 = 400.000 + 600.000 − 400.000 − 100.000. Nov: saldo
awal 500.000, KW-2 5 Nov **Cr 500.000** → 0. Pengecoh: SJ-Q 10 Okt Dr 250.000 (pesanan pelanggan Q) dan jurnal manual
12 Okt Dr 70.000 (tanpa pelanggan) ada di buku besar 1-1200 PT itu tetapi tidak di rekening koran P.

## Uji lama yang menguji perilaku yang sengaja diubah (dilaporkan)

- `tests_mem/test_AGT3_kartu_tindakan.py` U15: kartu "Catat janji bayar" kini wajib bernominal (400 "Nominal janji bayar
  wajib lebih dari nol.") dan tanggal tetap "2026-12-01" diganti hari ini + 16 (tanggal lampau kini ditolak — tanpa ini uji
  menjadi merah mulai 2 Des 2026); + asersi `promise_date`/`promise_amount` tersimpan.
- jest `prt7TombolIzin.test.js` U7/U8: tab Kredit & Plafon kini dibuka `credit_profile.view` (dulu `customer.view`); `customer.view`
  saja tidak lagi membukanya. Di T + `credit_override.view` (CR-T3).
- `frontend/src/config/__tests__/fixtures/view_main_permission.json` (`credit-overrides`): izin utama `credit_profile.view`,
  endpoint `/api/credit-desk?queue=menunggu_keputusan` (di T: dua izin alternatif dengan `endpoint_per_izin`).

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`1315ce6`** (CR-T5 + cek layar):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`efc1cc6`: 12 / 39). Kuitansi: `bukti/CR-T5/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- HEAD cabang tetap `efc1cc6` sejak pelaksana menggabung; T di-commit apa adanya (`8dee8c6`) lalu dipetik ke atas penutupan
  CR-T3/PY-T5/PY-T4 (`cfe5836`, hanya laporan/STATUS) → **`d08d664`** (pohon kode sama). `tests_mem` di T 2245/2/2 dan jest
  1064 (pelaksana) — tidak diulang integrator (pohon identik; arahan pemilik 15 Nov). Jest CR-T5 10/10 sesudah cek layar.
- Uji jalan **U16** (integrator, data acuan sesudah `restore_demo`): Piutang › **Kredit & Plafon** (enam antrean berjumlah, kotak
  cari, Unduh) — **cacat ditemukan dan diperbaiki (`1315ce6`)**: antrean "Menunggu keputusan" 761 px di kartu ±732 px (1024),
  kolom Ringkasan tertutup kolom Aksi lekat; tautan "Buka kartu pelanggan" yang turun baris rata tengah. Kini lebar minimum
  Aksi 112/120 px (tombol bertumpuk), sel pelanggan 130 px, tautan rata kiri → **732 px**. Kartu pelanggan › **Rekening Koran**
  (Dari/Sampai `KNDatePicker`, Tampilkan, Cetak PDF, Salin pengingat; tabel saldo awal → mutasi → saldo akhir) = 732 px di 1024,
  656 px di 1280; keadaan "Tidak ada mutasi piutang pada periode ini." (`bukti/CR-T5/cek_*.png`). Unduh PDF dan pencocokan saldo
  rekening koran dengan buku besar 1-1200 per pelanggan untuk retur/selisih bayar/kasus/saldo kredit/titipan: data acuan tidak
  memuat dokumen jenis itu — **belum diuji dengan data**; INV-BAL-02 (Σ piutang terkirim = saldo akun piutang) tetap PASS.
- Tombol "Bebaskan" denda memakai `penalty_service.waive` yang masih memeriksa nama peran (warisan, dicatat CR-T4) — di luar
  lingkup.

Pelaksana (catatan asli):

Belum dijalankan (`gate.sh --quick` / penuh dijalankan integrator di lingkungan A).

## Angka uji

| Rangkaian | Sebelum | Sesudah |
|---|---|---|
| `tests_mem` W (B `4580bd9`) | **2126 lulus / 2 dilewati / 2 xfail** (`W_tests_mem_basis.txt`) | **2143 lulus / 2 dilewati / 2 xfail** (= 2126 + 17, 0 gagal; `W_tests_mem_sesudah.txt`). Jalan penuh dimulai sebelum `exposure()` dirapikan ke gerbang kredit dan ringkasan izin kredit + lingkup; berkas CR-T5 dijalankan ulang sesudahnya 17/17 (`W_hijau_CRT5.txt`) |
| `tests_mem` T (`efc1cc6`, gabung terakhir) | HEAD 2228/2/2 (diturunkan: T − 17 uji baru) | **2245 lulus / 2 dilewati / 2 xfail**, 0 gagal (`T_tests_mem.txt`); gabung pertama di `b014a38`: 2228/2/2, 0 gagal |
| jest W | **1034 lulus** (35 suite gagal dimuat `cmdk`/`@radix-ui`, lingkungan) | **1043 lulus** jalan penuh (`W_jest_sesudah.txt`) + 1 uji (pembaca izin kredit saja) ditambah sesudahnya, lulus terarah → **1044** (= 1034 + 10); 35 suite sama |
| jest T | HEAD `efc1cc6` **1054 lulus** (diukur, 35 suite gagal dimuat; `HEAD_jest.txt`) | **1064 lulus** (= 1054 + 10; 35 suite sama; `T_jest.txt`); di `b014a38`: 1044 → 1054 |

Penjaga statik (`hitung_penjaga.sh`, B → W): auth 26 → 26 · ui_standard 11 → 11 · i18n 103 → 103 · create_modal 6 → 6 ·
page_tabs 1 → 1 · to_list 5 → 5 · entity_label 2 → 2 · list_export, error_notice, custom_modals, knselect, access_catalog_nav,
money_idempotency, codebase_map PASS/0 (`W_penjaga_*.txt`). `verify_role_gate_ui` 31/0; `verify_posting_coverage` 138/0;
`verify_cash_single_door` 743/0; `verify_detail_modal` 29/0; `verify_atomic_claim` 161/0; `verify_payment_vocab` 1844/0;
`verify_permission_checked` 615/0; `verify_config_fallback` 159/0 (+`--entity` 159/0); `verify_config_text` 3402/0;
`audit_config_wiring --strict` hijau; `check_nav_map` PASS; `verify_contract --all` OK. Di T (`efc1cc6` + CR-T5) = HEAD tepat sama (`hitung_penjaga.sh` T vs pohon HEAD: tanpa selisih — auth 26 · ui_standard 11 · i18n 102 · create_modal 5 · page_tabs 1 · to_list 5 · entity_label 2 · lainnya PASS/0); `verify_role_gate_ui` 31/0; `verify_posting_coverage` 137/0; `verify_cash_single_door` 748/0; `verify_detail_modal` 30/0; `verify_atomic_claim` 161/0; `verify_payment_vocab` 1855/0; `verify_permission_checked` 617/0; `verify_access_catalog_nav` 0; `verify_config_fallback` 161/0 (+`--entity` 161/0); `verify_config_text` 3472/0; `audit_config_wiring --strict` hijau; `check_nav_map` PASS (`T_penjaga.txt`).

## Cek layar (dari kode; foto 1280/1024/390 oleh integrator)

Lebar hitung: kartu 1280 px ±1018, 1024 px ±760 (dikurangi bantalan `section-body`).

| Layar | Lebar tabel terhitung | (1) aksi | (2) bantalan | (3) kepala | (4) tombol mati | (5) status | (6) cari | (7) teks izin | (8) kosong/0 |
|---|---|---|---|---|---|---|---|---|---|
| Piutang › Kredit & Plafon › Menunggu keputusan | Jenis 120 · Pelanggan 150 · Nominal 110 · Pengaju 110 · Ringkasan 110 · Aksi 150 = **750** ≤ 760 | `col-sticky-end`, `btn-sm` boleh turun baris | `section-card` + `section-body` | chip & cari di badan, bukan kepala | pengaju sendiri / Semua PT: mati + alasan tertulis di bawah tombol / bilah sendiri | Jenis = `status-pill` + ikon (`status-pending`/`status-shipped`) | kotak cari + 6 chip saringan | tanpa izin putus: kolom Aksi tidak tampil (bukan "bukan wewenang") | satu kalimat kosong; chip "0" netral |
| … › Ditahan | Jenis 95 · Pelanggan 160 · Pesanan 105 · Nilai 110 · Alasan(+sejak) 110 · Aksi 150 = **730** | sticky | ya | ya | "Periksa ulang kredit" mati tanpa gerbang (W) + "Pesanan dilepas lewat keputusan izin kredit." tertulis | "Ditahan"/"Ditolak" ikon+teks+warna | ya | — | ya |
| … › Jatuh tempo | Pelanggan 170 · Tagihan 140 · Total 110 · Telat 130 · Aksi 160 = **710** | sticky; "Salin pengingat"/"Catat janji bayar" turun baris di sel | ya | ya | "Catat janji bayar" tanpa `order.update` → alasan tertulis | "Telat N hari" merah / "N hari lagi" jingga, berikon | ya | — | rincian baris dibuka per pelanggan |
| … › Janji bayar | 160 · 100 · 110 · 110 · 100 · 100 = **680** | tanpa aksi selain tautan kartu | ya | ya | — | Menunggu (jam, jingga) · Ditepati (centang, hijau) · Ingkar (segitiga, merah) | ya | — | ya |
| … › Kaji ulang | 160 · 110 · 100 · 110 · 90 = **570** | — | ya | ya | — | Lewat / Mendekati berikon | ya | — | ya |
| … › Denda | Nota 120 · Pelanggan 160 · Nominal 110 · Telat 70 · Catatan 140 · Aksi 150 = **750** | sticky | ya | ya | Semua PT: mati + bilah alasan | tanda jadwal void ikon + teks jingga | ya | tanpa izin: "Dipantau" | ya |
| Kartu pelanggan › kotak Eksposur | `dl` dua kolom di kolom kiri 320 px (≥1280); 1024: ditumpuk penuh | — | `section-head`/`section-body` | judul + nama PT pendek saja | — | "tidak dihitung" teks | — | — | denda terpisah, nol netral |
| Kartu pelanggan › Rekening Koran | Tanggal 84 · Dokumen 130 · Keterangan 132 · Tagihan 96 · Pembayaran 104 · Saldo 104 = **650** (kolom kanan 1280 ±650; 1024 ditumpuk ±728) | Saldo `col-sticky-end` | di dalam tab | bilah Dari/Sampai/tombol sendiri | Cetak/Salin hanya bagi pemegang izin | — | tanggal | — | "Tidak ada mutasi piutang…" satu kalimat; Denda: satu kalimat |
| Kartu pelanggan › Tagihan | 100 · 120 · 90 · 90 · 90 · 90 · 70 = **650** | Telat `col-sticky-end` | ya | ringkasan di bilah judul bagian | — | Telat berikon (`status-rejected`) | (jadwal satu pelanggan) | — | "Tidak ada tagihan terbuka." |

Tanggal lewat `KNDatePicker` (tanpa `type="date"`); nominal `whitespace-nowrap` (saldo/sisa plafon negatif "-Rp …" tidak
patah); warna lewat token `kn-*`; tombol `btn-sm`. Kelas status yang dipakai ADA di `styles/components.css`
(`status-pending`, `status-done`, `status-rejected`, `status-shipped`, `status-draft`). Form HP: isian janji `kn-input-touch`.

## Menyimpang dari blueprint

1. **Endpoint tambahan `GET /api/customers/{id}/exposure`** (tidak di tabel Server): kotak Eksposur membutuhkan angka per
   (pelanggan, PT) yang dipakai mesin; `/360` tidak ber-PT. Di T angkanya dari `credit_gate.evaluate` titik "periksa ulang"
   (satu pemilik angka, D1); di W (tanpa gerbang) rumus `compute_customer_credit`. Baris "Titipan & saldo kredit" = titipan
   pelanggan (yang mengurangi di gerbang); saldo kredit toko tidak mengurangi eksposur dan ditulis di keterangan.
2. **"Override Kredit" → bagian "Izin kredit" di tab Kredit** dirender di kartu pelanggan (`CustomerOverrideSection`), bukan di
   `CustomerCreditTab.jsx` (berkas CR-T1/CR-T3), supaya penggabungan bersih. Tab "Riwayat Perubahan" (izin `audit.view`) tetap
   ada di belakang delapan tab spesifikasi (§7 butir 3).
3. **Unduh** (KN_37 §6): antrean hasil hitung beberapa koleksi tidak punya dataset Pusat Export; `PaginationBar` memakai
   `exportSpec` dengan dataset `credit_overrides` + `unsupported` (butir Excel mati dengan alasan tertulis) dan CSV kolom-layar
   (`exportConfig`). Tidak pernah mengunduh data lebih luas dari layar.
4. **Isian janji di form lain**: `CollectionWorklist`, dua form HP, dan kartu asisten ikut aturan janji (tanpa ini form itu
   gagal 400 sesudah unit ini).
5. **Naskah pengingat**: PM-T2 sudah selesai, jadi baris tagihan berkode bayar aktif menambah " · kode bayar {kode}" dan
   rekening tujuan pesanan yang tampil di dokumen ditulis "Transfer ke: {rekening}" sesudah Total (format tidak disebut
   spesifikasi — kosakata instruksi bayar PM-T2). Tanpa kode/rekening naskah = templat persis (U15).
6. Baris rekening koran memuat isian tambahan `doc_label`, `trace_type`, `je_number`, `reversal` (untuk tautan Jejak Dokumen,
   L8); bagian denda memakai `doc_type` `nota_denda`.

## Asumsi

- `ASUMSI:` (spesifikasi) jendela "Jatuh tempo" = hari ini + 3 hari, "Kaji ulang" = 14 hari, janji 90 hari terakhir,
  penolakan 90 hari — parameter fungsi (`JENDELA_*`), bukan aturan yang menahan sesuatu.
- `ASUMSI:` (spesifikasi) janji dinilai terhadap seluruh kwitansi tidak-batal pelanggan di PT itu, bertanggal catatan s.d.
  tanggal janji (termasuk); tanggal catatan = tanggal buku WIB `created_at`.
- `ASUMSI:` (`00` §4.1) catatan janji lama tanpa `promise_date` tidak masuk antrean "Janji bayar" (tetap di tab Penagihan,
  tanpa lencana); PT janji = PT catatan (PT pemilik data pelanggan, perilaku `add_followup` hari ini).
- `ASUMSI:` "jatuh tempo terdekat" = jatuh tempo ≥ hari ini terdekat (`next_due_date`); juga dikirim `oldest_due_date`.
- `ASUMSI:` "telat terlama" boleh negatif (semua baris belum jatuh tempo → "N hari lagi").
- `ASUMSI:` antrean "Ditahan": pesan alasan = `credit_hold_info.reasons[0]` (CR-T3) → alasan entri persetujuan kredit yang
  menunggu → "Menunggu keputusan izin kredit."; "Periksa ulang kredit" memanggil `POST /api/sales-orders/{id}/credit-recheck`
  (CR-T3) — tanpa gerbang tombol mati beralasan.
- `ASUMSI:` PDF rekening koran memakai gaya dokumen bawaan PT (`__default__` + lapisan PT), nomor = kode pelanggan; tidak ada
  jenis templat PDF baru.

## Yang perlu direview / titik henti

- **H3**: tidak ada skrip data. Catatan janji lama tidak dimigrasi (tanpa nominal); bila pemilik ingin catatan `promised` lama
  masuk antrean, perlu keputusan + skrip (tidak dibuat).
- **H4/H5**: tidak ada nilai aturan, akun, atau templat PDF resmi baru; tidak ada sakelar PT.
- **Kinerja belum diukur**: ringkasan menghitung enam antrean tiap dibuka (jatuh tempo = `open_lines` seluruh pesanan belum
  lunas PT itu); rekening koran membaca semua jurnal piutang PT ≤ tanggal "Sampai" lalu memetakan pelanggannya (dimuat
  sekaligus per koleksi). Di data acuan wajar; di data nyata besar perlu diukur integrator.
- **Pemetaan jurnal → pelanggan** (`customer_of_journal`) diuji untuk surat jalan, kas kwitansi, nota kredit, jurnal manual;
  jenis lain (retur, selisih bayar, kasus keuangan, saldo kredit, titipan bank, deposit, titipan tunai) dipetakan dari kode
  pembuatnya tetapi **belum diuji** dengan dokumen nyata — integrator: bandingkan saldo akhir rekening koran beberapa
  pelanggan data acuan dengan rincian buku besar 1-1200.
- Kotak Eksposur di W (tanpa CR-T3) = perilaku lama; di T = gerbang kredit. Endpoint `/exposure` menjalankan
  `credit_gate.evaluate` (baca-saja) tiap kartu dibuka.
- `penalty_service.waive` masih memeriksa peran penyetuju lewat `role_in` (warisan, dicatat CR-T4) — tombol "Bebaskan" di
  antrean memakai endpoint yang sama.
- Belum diuji jalan di peramban (U16).

## Penggabungan

- T = `$S/wt32` di-reset ke HEAD cabang **`b014a38`** (dibaca saja dari `/home/user/KNHOST`), `backend/.env` disalin. HEAD sudah
  memuat **CR-T3** (gerbang kredit, izin kredit `credit_override.view/create`, `credit_gate_rejections`, `credit_hold_info`,
  `POST …/credit-recheck`, kunci `ar.eksposur_*`) dan PY-T5.
- Berkas yang sama di B dan HEAD → disalin dari W: `server.py`, `routers/payment_plans.py`, `services/ai_cards.py`,
  `services/penalty_service.py`, `tests_mem/test_AGT3_kartu_tindakan.py`, `KN_13`, `AppViewRouter.jsx`, `appViewImports.js`,
  `hubTabs.js`, `navMeta.js`, `CollectionWorklist.jsx`, dua form HP. Berkas baru (11) → disalin.
- `git merge-file` bersih: `access_modules.py`, `indexes.py`, `routers/crm.py`, `schemas_crm.py`, `services/customer_service.py`,
  `prt7TombolIzin.test.js`, `memory/PRD.md`.
- Bentrok + keputusan:
  - `Customer360Panel.jsx` (5 bentrok dengan CR-T3): impor `CreditOverrideModal` (CR-T3) **dan** komponen CR-T5; tab "Izin
    Kredit" (nama CR-T3) pindah ke tab Kredit sebagai bagian "Izin kredit" (spesifikasi CR-T5) — rincian CR-T3 (lingkup, sisa,
    berlaku sampai, alasan baku, pemakaian `used_by`) dipindah ke `CustomerOverrideSection` (`CustomerBillingTab.jsx` di T,
    + `SCOPE_LABEL`); `canAskCredit` (CR-T3) + `canBilling`/`canStatement` (CR-T5); kotak Eksposur CR-T5 membungkus tombol
    "Ajukan izin kredit" CR-T3 (syarat `credit_override.create`, kalimat tanpa izin tetap); `const limit` yang tak terpakai lagi
    dibuang.
  - `access_modules.py` (bersih tekstual, disesuaikan makna): CR-T3 menambah `credit-overrides` ke modul `sales_force`
    (pembaca `credit_override.view`). Syarat tampil tab di T = **salah satu** `credit_profile.view` (antrean) atau
    `credit_override.view` (daftar izin kredit, perilaku CR-T3); `CreditDeskView` tanpa `credit_profile.view` menampilkan
    `CreditOverridesPanel` saja tanpa memanggil antrean. `customer.view` saja tidak lagi membuka tab (CR-T5).
  - `view_main_permission.json`: `credit-overrides` = dua izin alternatif + `endpoint_per_izin`
    (`credit_profile.view` → `/api/credit-desk?queue=menunggu_keputusan`, `credit_override.view` → `/api/credit-overrides`).
  - `prt7TombolIzin.test.js` (T): + kasus `{credit_override: [view]}` → tab tampil.
  - `ENTITY_REGISTRY.md`: baris CR-T3 (`credit_overrides`, `credit_gate_rejections`) + baris `collection_followups` CR-T5.
  - `KN_32`: HEAD sudah §9.27 (CR-T3) dan §9.28 (PY-T5) → bagian CR-T5 menjadi §9.29 (lalu §9.30 di gabung kedua); istilah "eksposur" milik §9.27,
    baris CR-T5 menjadi "kotak Eksposur (kartu pelanggan)" yang merujuk §9.27.
  - `CODEBASE_MAP.md` dibangkitkan ulang; fixture akses (`tests/fe03_access_fixture.py`) dibangkitkan ulang (+ uji
    `test_fe03_access_catalog.py` 6/6); `configKeyIndex.json` dibangkitkan (tanpa selisih — unit tidak menambah kunci).
- Makna CR-T3 yang dipakai CR-T5 di T (kode sama dengan W, dideteksi saat jalan): kotak Eksposur = `credit_gate.evaluate`
  ("periksa ulang", baca-saja) — baris dihitung mengikuti `ar.eksposur_*` PT itu (bawaan ya), angka eksposur = gerbang;
  antrean "Ditahan" memuat `credit_gate_rejections` `terbuka` dan "Periksa ulang kredit" aktif; ringkasan izin kredit
  memakai `reason_label` + lingkup bila ada.
- Hitungan uji lama tidak berubah (tanpa kunci pengaturan, izin, atau indeks wajib baru).
- **Gabung kedua**: HEAD maju ke `61cf7a1` + `efc1cc6` (PY-T4) sebelum laporan. Keadaan T (37 berkas) disimpan
  (`$S/crt5/t_state1/`), T di-reset ke `efc1cc6`, lalu `git merge-file <efc1cc6> <b014a38> <T lama>`: bersih
  `ENTITY_REGISTRY.md`, `access_modules.py`, `KN_13`, `view_main_permission.json`, `hubTabs.js`, `navMeta.js`, `memory/PRD.md`;
  bentrok `KN_32` (PY-T4 mengambil §9.29 → bagian CR-T5 menjadi **§9.30**), `CODEBASE_MAP.md` dan fixture akses
  (dibangkitkan ulang; `test_fe03_access_catalog.py` 6/6; `configKeyIndex.json` tanpa selisih). Semua angka T di atas dari
  `efc1cc6`.
