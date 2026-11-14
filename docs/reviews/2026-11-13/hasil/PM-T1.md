# PM-T1 — Satu daftar induk cara bayar, dan rekening yang punya atas nama, peruntukan, dan bawaan per PT

- Commit awal: `c38fc92` (dikerjakan) · digabung di atas PK-42 `5e747b2`        - Commit: `fd606e5` · cek visual `27f0853`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PM-03, PM-05
- Keputusan: K-34, K-35 · Standar: `02` §2.3, §3.1 (Z1–Z3, Z4, Z6), §3.2, §3.4 (N1, N2, N4, N5), §4 (L1, L2, L4, L7),
  §5 (D1, D7, D8, D9), §6 · Risiko sedang (satu serah-terima)
- Prasyarat: KF-T1 (izin pengaturan), KF-T6 (`services/dual_control.py`, keluarga `kontrol.*`) — keduanya ada di HEAD

## Cek ulang "Keadaan sekarang" (di `c38fc92`; blueprint dibaca di `3132cc4`)

| Butir | Hasil |
|---|---|
| Kwitansi `METHODS` | Berlaku: `ARReceiptModal.jsx:28` (`transfer · cash · giro · qris`); juga `["cash","tunai","kontan"].includes(method)` di `:190` |
| Server kwitansi teks bebas, `CASH_METHODS` | Berlaku, bergeser: `method` di `ar_receipt_service.py:441` (bukan 439); `CASH_METHODS` `:44`. Juga dipakai `routers/invoices.py:134` dan `bootstrap.backfill_ar_cash_postings` lewat `_cash_routing` |
| Bayar tagihan pemasok `transfer · tunai · giro` | Berlaku, bergeser ke `VendorBillDetailPanel.jsx:243` (bukan 190). Server: satu pintu `ap_payment_service.pay_payable` (PK-05) untuk tagihan DAN kontrabon |
| Voucher biaya masuk | Berlaku: `LandedCostDetailPanel.jsx:171`; server `routers/landed_cost.py:pay_landed_cost` |
| Kontrabon `transfer · giro · cash` | Berlaku: `contraBonApi.js:34` (`METHOD_OPTIONS`), dipakai `PayModal.jsx` dan `PaymentScheduleModal.jsx`; jadwal bayar `contra_bon_service.schedule` juga menyimpan cara bayar |
| Uang muka `tunai · transfer` | Berlaku, bergeser ke `CashAdvanceForm.jsx:151` (bukan 146); server `cash_advance_service.VALID_PAYMENT` `:30` (cara bayar dipilih saat pengajuan, bukan saat pencairan) |
| Selisih bayar (pengembalian) `transfer · cash` | Berlaku: `PaymentVarianceDialog.jsx:37`; kunci `payment.variance_refund_method` bergeser ke `config_catalog_payment.py:236` (bukan 222) |
| Pelunasan antar-PT `transfer · cash` | Berlaku: `intercoApi.js:63` (`SETTLEMENT_METHODS`); server `interco_service.create_settlement` + daftar `meta()["settlement_methods"]` (tidak dibaca layar) |
| Bayar denda (jurnal) `tunai · cash` → kas kecil | **Bergeser/berubah:** `gl_service.py:2218` `post_penalty_payment` kini USANG (PK-08: tidak dipanggil; bayar denda lewat `penalty_service.pay` → jenis kas dari rekening). Himpunan tetap diganti `is_cash`; cara bayar di `penalty_service.pay` kini dinormalkan |
| Selisih bayar (server) `cash · tunai · kontan` | Berlaku, bergeser: `payment_variance_service.py:616` (`_refund`) **dan** `:995` (pembalikan refund) — dua tempat |
| Kosakata termin (tidak diubah) | Berlaku: `crmUtils.jsx:58`, `schemas_crm.py:22`, `config_service.py:160` (bukan 149). Ditemukan dua tempat termin lain: `customer_service.NON_AR_METHODS`, `cashflow_forecast_service.NON_AR_METHODS`, dan pilihan jenis syarat bayar `masterFieldsConfig.js` — semua jadi pengecualian beralasan penjaga |
| `BankAccountCreate` tujuh field | Berlaku: `schemas_finance.py:9` |
| `is_active` vs `status` di `sole_account_id` | Berlaku: `bank_service.py:179` (`is_active: True`), `:57` (`status` disaring) — U5 merah |
| Buat/ubah rekening cukup `cash.create` | **Tidak berlaku lagi:** PK-17 sudah mengganti menjadi `cash.configure` (`routers/bank.py:53`, `:72`), dipegang Admin, Manajer, **Finance** |
| Master berlapis `MASTERS`, `WRITE_PERMISSION` | Berlaku, bergeser: `entity_master_service.py:57`, `:228` |
| Baris efektif master butuh `settings.view` | Berlaku: `routers/entity_masters.py:47` |
| (tambahan) `effective_rows`/`resolve_row` tanpa `include_inactive` | Baris khusus PT yang **nonaktif** disaring lebih dulu, sehingga baris global ber-kode sama menang lagi — "Buat khusus PT → nonaktif" tidak mematikan apa pun bila dibaca dengan bawaan. `payment_method_service` membaca dengan `include_inactive=True` lalu menyaring sendiri (U2 hijau). Master lain (syarat bayar, lini, …) tidak disentuh — lihat "Yang perlu direview" |

## PM-03 — Enam kosakata metode bayar yang berbeda

- Berlaku di HEAD: ya (U1–U4 merah; penjaga baru merah 27 pelanggaran di kode HEAD — `bukti/PM-T1/verify_payment_vocab_merah_kode_HEAD.log`).
- Akar masalah: tiap layar dan tiap layanan menulis daftarnya sendiri; tidak ada master, jadi tidak ada yang bisa
  dimatikan per PT, dan kata yang sama tersimpan dua bentuk (`tunai`/`cash`).
- Perubahan perilaku (sebelum → sesudah):
  - Master berlapis baru `payment-methods` (koleksi `payment_methods`, awalan `pmeth`, kunci `code`; izin tulis
    `cash.configure`), benih 7 baris global persis tabel spesifikasi (`services/payment_method_service.BENIH`,
    `ensure_seed` saat server menyala: hanya menambah baris global yang belum ada). Isian master diperiksa server
    (kode huruf kecil, rekening `bank|kas|tidak`, arah `masuk|keluar`, alias huruf kecil) → 400 berkalimat.
  - `services/payment_method_service.py`: `normalize` (kode/alias → kanonik, tak dikenal → `ValueError`), `get`
    (baris efektif PT, nonaktif → `None`; baris khusus PT menang walau nonaktif), `active_for`, `is_cash`
    (`needs_account == "kas"`; kata yang bukan cara bayar mis. `writeoff` → False), plus `wajib`/`kode_400` (galat
    berkalimat) dan kamus kata lama yang dimuat ulang sesudah master diubah.
  - `GET /api/payment-methods?direction=&entity_id=` (login saja, `LOGIN_ONLY` "rujukan"): `[{code, name,
    needs_account, needs_reference, needs_due_date}]` aktif untuk PT itu; PT di luar penugasan → 403.
  - Pintu yang menerima cara bayar menormalkan lalu memeriksa sebelum menulis apa pun dan menyimpan kode kanonik:
    kwitansi (`ar_receipt_service.create_receipt`, arah masuk), bayar tagihan pemasok & kontrabon (satu pintu
    `ap_payment_service.pay_payable`, keluar), jadwal bayar kontrabon (`contra_bon_service.schedule`), voucher biaya
    masuk (`landed_cost.pay_landed_cost`), uang muka (`cash_advance_service` buat & ubah), bayar denda
    (`penalty_service.pay`, masuk), pengembalian selisih bayar (`payment_variance_service.decide_receipt` kind refund),
    pelunasan antar-PT (`interco_service.create_settlement`, kecuali `netting`). Dulu `"bitcoin"` tersimpan apa adanya;
    kini 400 "Cara bayar tidak dikenal: bitcoin." tanpa dokumen; QRIS yang dimatikan khusus PT → 400 "Cara bayar QRIS
    tidak aktif untuk PT ini."; arah salah (mis. QRIS untuk uang muka) → 400 "Cara bayar QRIS tidak dipakai untuk
    pembayaran keluar.".
  - Empat himpunan tunai + cabang `gl_service` diganti `is_cash` (`ar_receipt_service._cash_routing` kini asinkron —
    tiga pemanggil ikut; `payment_variance_service` dua tempat; `gl_service.post_penalty_payment`).
  - Layar: `frontend/src/config/paymentMethods.js` (`usePaymentMethods(arah, PT)`, cache per arah × PT, cadangan = benih
    aktif bila daftar gagal dimuat, `canonicalMethod` untuk nilai lama). Delapan layar dialihkan: kwitansi desktop/HP
    (tanpa titipan — titipan lewat kotak deposit), bayar tagihan, voucher biaya masuk, bayar & jadwal kontrabon, uang
    muka (+ label di detail), pengembalian selisih bayar (label menyebut Kas Kecil/Kas Besar), pelunasan antar-PT.
    Label isian "Metode" → "Cara bayar" (KN_32). `payment.variance_refund_method` tetap dua nilai.
  - Penjaga `scripts/guardrails/verify_payment_vocab.py` (INV-PAY-VOCAB-01, `--self-test` 18 kasus dua arah),
    didaftarkan di kolam statik `scripts/gate.sh`; repo hijau 0 pelanggaran.
- Status: implemented_pending_review

## PM-05 — Master rekening tanpa peruntukan dan bawaan; saringan aktif memakai field yang salah

- Berlaku di HEAD: ya (U5–U11 merah).
- Akar masalah: `bank_accounts` hanya menyimpan identitas; "rekening satu-satunya" menyaring `status` yang tidak pernah
  diisi; perubahan rekening langsung berlaku tanpa jejak terpisah.
- Perubahan perilaku (sebelum → sesudah):
  - Field baru `holder_name`, `purposes`, `payment_method_codes`, `default_receiving_methods`, `show_on_documents`
    (skema `BankAccountCreate`/`BankAccountUpdate` + `reason` opsional). Diperiksa server: peruntukan dari empat nilai;
    cara bayar harus cocok jenis rekening (bank ↔ ber-rekening bank, kas ↔ tunai; titipan tidak); bawaan ⊆ yang dilayani
    → 400 "Rekening ini tidak melayani cara bayar {nama}."; `show_on_documents` menuntut atas nama + nomor + jenis bank →
    400 "Rekening yang tampil di dokumen wajib punya atas nama dan nomor rekening.".
  - Satu bawaan per (PT, cara bayar): menulis bawaan mencabut tanda yang sama dari rekening lain PT itu dalam operasi
    yang sama; indeks unik wajib `bank_accounts.uq_default_receiving` (`(entity_id, default_receiving_methods)`, parsial
    `{"default_receiving_methods.0": {"$exists": true}}`, `REQUIRED_UNIQUE_INDEXES`); benturan dua permintaan bersamaan
    → `DuplicateKeyError` → cabut + tulis diulang (≤ 3×, `bank_service._tulis_bawaan`).
  - `sole_account_id` menyaring `{"is_active": {"$ne": False}}` (+ `status` lama tetap).
  - Rekening lama TANPA field baru dibaca dengan nilai awal spesifikasi (`bank_service.bidang_efektif`/`rekening_pt`):
    empat peruntukan, cara bayar menurut jenis, bawaan `["transfer"]`/`["cash"]` hanya untuk rekening aktif satu-satunya
    di PT untuk jenisnya. Setiap tulis rekening sebuah PT menyimpan nilai itu lebih dulu untuk rekening PT tersebut
    (`isi_awal_bidang_rekening(tulis=True, entity_id=PT)`); seluruh database lewat skrip
    `scripts/blueprint/pmt1_isi_rekening.py` (bawaan **lapor**, `--terapkan` menulis; data nyata = H3, tidak dijalankan).
  - `GET /api/bank-accounts/receiving?entity_id=&method=` (salah satu `order.create`, `ar_receipt.create`, `cash.view`;
    PT lewat `resolve_requested_entity`): `[{id, name, bank_name, account_number, holder_name, is_default}]`, tanpa saldo.
  - `POST/PATCH /api/bank-accounts` (`cash.configure`, tetap): bila perubahan menyentuh field peka (nomor, bank, atas nama,
    peruntukan, cara bayar, bawaan, tampil di dokumen, aktif) atau membuat rekening, dan `butuh_orang_kedua
    ("ubah_rekening", PT, 0)` → tidak diterapkan, 202 `{change}` berstatus `menunggu`; selain itu diterapkan dan
    dicatat `diterapkan` (semua perubahan, bukan hanya field peka — riwayat di satu tempat). Koleksi baru
    `bank_account_changes` (`bac_`, SCOPED, indeks `(entity_id, status, created_at)`).
  - `GET /api/bank-account-changes?status=&page=&page_size=` (`cash.view`, per PT, berhalaman; baris menunggu membawa
    `blocked_reason` bila pembaca = pengaju dan aturan dua orang) dan `POST /api/bank-account-changes/{id}/decision`
    (`cash.approve`; `tolak_bila_pelaku_sama("ubah_rekening", …)`; setujui = terapkan hanya bila nilai `from` masih sama,
    dengan syarat nilai lama di filter tulis; tolak = alasan wajib; sudah diputus / data berubah → 409).
  - Aksi kontrol ke-37 `ubah_rekening` ("Ubah rekening kas/bank", kelompok C, awal "1", tanpa nominal, bagian Buku
    besar) → satu kunci `kontrol.ubah_rekening.min_orang`. Izin baru `cash.approve` (Admin, Manajer; blok
    `PMT1_DEFAULT_PAIRS`, tersalin lewat `sync_permission_modules`). Awalan `/api/bank-accounts`,
    `/api/bank-account-changes` masuk `IDEMPOTENT_PREFIXES` dan `MONEY_PREFIXES` penjaga.
  - Layar Rekening & Saldo: form `BankAccountForm` (buat & ubah — dulu tidak ada form ubah) dengan Atas nama, Dipakai
    untuk, Cara bayar yang dilayani, Jadikan bawaan penerimaan untuk, Tampilkan di dokumen pelanggan, Catatan untuk
    penyetuju; tombol "Ubah rekening" di rincian rekening (`cash.configure`); kartu menulis "a.n. …" dan lencana
    "Bawaan: …"; 202 → pemberitahuan "Perubahan disimpan sebagai pengajuan dan berlaku setelah disetujui orang lain.";
    bagian `BankAccountChangesPanel` "Perubahan menunggu persetujuan" (Setujui/Tolak untuk `cash.approve`, konfirmasi
    menyebut rekening, PT, lama → baru; Tolak minta alasan). Pengaturan › Keuangan & Pajak › Master per Badan Usaha
    menampilkan master "Cara Bayar" (kolom & isian di `masterFieldsConfig.js`).
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_PMT1_cara_bayar.py` (18 uji: U1–U13 + 5 tambahan). Merah di kode HEAD: 17/17 (uji skrip ditulis
sesudahnya, skripnya baru) — `bukti/PM-T1/tests_mem_PMT1_merah_kode_HEAD.log`.

| ID | Lapis | Merah di kode lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | ya (404 rute tidak ada) | Lulus — `sls`: `transfer, cash, giro, qris, deposit`; arah keluar `transfer, cash, giro` |
| U2 | B | ya ("Master 'payment-methods' tidak dikenal") | Lulus — baris khusus `ent_kanda` qris nonaktif: Kanda tanpa qris, KSC tetap |
| U3 | B | ya (tersimpan `tunai`; `bitcoin` 200) | Lulus — `tunai`/`kontan` tersimpan `cash` (kwitansi + pembayaran pesanan); `bitcoin` 400 pesan persis, tanpa kwitansi |
| U4 | B | ya (200, kwitansi `qris` di Kanda) | Lulus — 400 "Cara bayar QRIS tidak aktif untuk PT ini.", tanpa kwitansi |
| U5 | B | ya (`""`) | Lulus — id rekening aktif |
| U6 | B | ya (200, rekening lahir) | Lulus — 400 pesan atas nama, jumlah rekening tetap |
| U7 | B | ya (405 rute penerima tidak ada) | Lulus — B bawaan, A tidak, tepat satu; bawaan giro yang tidak dilayani → 400 |
| U8 | B | ya (405) | Lulus — rekening Kanda tidak tampil untuk `sls`; `entity_id=ent_kanda` 403; tanpa saldo |
| U9 | B | ya (kunci `kontrol.ubah_rekening.min_orang` tidak ada) | Lulus — 202 (`changes` = nomor lama → baru), nomor tetap; `mgr` memutus 403; `adm` 200, nomor berubah; ulang 409; daftar `diterapkan` memuatnya |
| U10 | B | ya (rekening Kanda tidak ada — U8) | Lulus — PT lain langsung + satu catatan `diterapkan` (aksi ubah); ganti nama langsung |
| U11 | B | ya (fungsi tidak ada) | Lulus — bank: 4 peruntukan, `transfer, giro, qris`, bawaan `["transfer"]`; dua kas `["cash"]`, bawaan `[]`; putaran kedua 0 perubahan, dokumen identik |
| U12 | B | ya (400 "Aksi ['approve'] tidak berlaku untuk Kas & Bank") | Lulus — Tanpa Acuan + `cash.approve` putus 200; + `cash.configure` tambah master 200; Manajer Kosong & Sopir 403/403 (+ rekening penerima 403) |
| U13 | B | ya (penjaga tidak ada) | Lulus — `--self-test` 18/18; repo 0 pelanggaran (kode HEAD: 27, `bukti/…/verify_payment_vocab_merah_kode_HEAD.log`) |
| U14 | A | — | **Lulus** di lingkungan A (MongoDB 7 asli; bersama uji PK-14 lapis A: 11 lulus): `backend/tests/test_bp_PMT1_bawaan_bersamaan.py` (indeks terpasang + lima putaran dua PATCH bersamaan; data acuan PT dipulihkan) |
| U15 | layar | ya (komponen tidak ada) | Uji komponen jest `pmt1CaraBayar.test.js` 6/6 (kwitansi tanpa QRIS bila dimatikan, form rekening, 202, panel perubahan). **Uji jalan peramban belum dilakukan** |
| tambahan | B | ya | Bayar hutang `bitcoin` → `ApPaymentError` 400 tanpa niat; uang muka `tunai` → `cash`, `qris` 400 arah; `normalize`/`is_cash`; master menolak isian tak sah; skrip isi awal lapor bawaan → `--terapkan` → ulang 0 |

`backend/tests_mem` seluruhnya: HEAD **782 lulus / 2 dilewati / 2 xfail** → sesudah **800 lulus / 2 dilewati / 2 xfail**
(+18 uji baru; uji lama yang menghitung kunci/izin/indeks disesuaikan di bawah) — `bukti/PM-T1/tests_mem_sebelum_HEAD.log`,
`tests_mem_sesudah.log`.

## Uji yang disesuaikan (perilaku sengaja berubah — angka, bukan harapan dilonggarkan)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` | `+ PMT1_KUNCI` (= 1) di U02 dan U04 | kunci baru `kontrol.ubah_rekening.min_orang` berizin `settings.manage` |
| `tests_mem/test_KFT6_kontrol.py` | `N_AKSI` 36 → 37, `N_KUNCI` 59 → 60 | aksi ke-37 tanpa nominal |
| `tests_mem/test_PRT9_izin_bawaan.py` | `TAMBAHAN_SESUDAH` + `PMT1_DEFAULT_PAIRS` | `cash.approve` bawaan Admin & Manajer |
| `tests_mem/test_PRT3_login_saja.py` | `LOGIN_ONLY` 54 → 55 | `GET /api/payment-methods` data rujukan |
| `tests_mem/test_PK14_indeks_wajib.py`, `tests/test_bp_PK14_indeks_wajib.py` | indeks wajib 14 → 15 | `uq_default_receiving` |
| `tests_mem/conftest.py` | `CACHE_PROSES` + `payment_method_service._KAMUS` | cache proses dipulihkan per modul |
| `frontend/src/config/__tests__/fixtures/access_builtin_fixture.json` | dibangkitkan ulang (`cash` + `approve` untuk admin & manager) | `tests/test_fe03_access_catalog.py` 6/6 |
| `frontend/src/features/settings/config/configKeyIndex.json` | dibangkitkan ulang (`gen_config_key_index.py`) | kunci kontrol baru |

## Menyimpang dari blueprint

- **Pengisian awal tidak dijalankan saat server menyala** (spesifikasi: "fungsi idempoten saat server menyala, pola
  `backfill_cash_type`"). Arahan kerja: tulis data nyata = H3 → skrip ber-mode lapor. Penggantinya memenuhi U11 yang sama:
  fungsi `bank_service.isi_awal_bidang_rekening(tulis, entity_id)` + skrip `scripts/blueprint/pmt1_isi_rekening.py`
  (lapor bawaan), dan aplikasi membaca rekening lama dengan nilai awal yang sama (`bidang_efektif`) sehingga perilaku
  sebelum dan sesudah skrip sama. Tulis rekening sebuah PT menyimpan nilai itu untuk rekening PT tersebut (tindakan
  pengguna, bukan migrasi). Benih master cara bayar (baris global baru di koleksi baru) tetap ditanam saat menyala, sama
  dengan benih syarat bayar.
- **`cash.configure` bukan izin baru**: PK-17 sudah melahirkannya (kelola rekening) untuk Admin, Manajer, **Finance**.
  Mengelola daftar cara bayar memakai izin itu juga (spesifikasi: bawaan Admin & Manajer) — Finance ikut bisa mengubah
  master Cara Bayar. Yang baru hanya `cash.approve` (Admin, Manajer). Endpoint buat/ubah rekening tetap `cash.configure`
  (spesifikasi menulis `cash.create` — sudah bergeser oleh PK-17).
- Arah cara bayar ditegakkan server (spesifikasi tidak menulis galatnya): pesan tambahan "Cara bayar {nama} tidak dipakai
  untuk penerimaan / pembayaran keluar."; uang muka dulu hanya `tunai|transfer`, kini cara bayar keluar aktif mana pun
  (termasuk giro).
- Galat tambahan berkalimat: "Peruntukan rekening tidak dikenal: {x}.", "Keputusan harus setujui atau tolak.", "Alasan
  penolakan wajib diisi." (N5), dan validasi isian master cara bayar (kode, jenis rekening, arah).
- Cara bayar di rekening juga harus cocok jenis rekening (bank ↔ ber-rekening bank, kas ↔ tunai) — memakai pesan
  "Rekening ini tidak melayani cara bayar {nama}.".
- Jadwal bayar kontrabon (`schedule`) ikut dinormalkan (menyimpan cara bayar yang lalu dipakai bayar).
- `GET /api/bank-account-changes` berbentuk `{items, total, page, page_size}` (+ `label_changes`, `blocked_reason`);
  daftar tanpa `payload`.
- Layar menampilkan maksimal 50 pengajuan menunggu dengan keterangan "Menampilkan n dari N" (tanpa pager kedua — KN_37
  satu pager; daftar ini biasanya sangat pendek).

## Asumsi

- Spesifikasi: kode kanonik = nilai terbanyak hari ini (`cash`); rekening lama diberi empat peruntukan dan cara bayar
  menurut jenisnya; nominal kontrol `ubah_rekening` selalu 0; KF-T6 sudah ada → U9 dijalankan (tidak ditunda).
- "Jenis" pada "satu-satunya rekening aktif PT untuk jenisnya" = `account_type` (bank / kas), bukan `cash_type`.
- Perubahan yang tidak menyentuh field peka (nama, catatan, saldo awal) tetap dicatat `diterapkan`.
- Pengaju yang sama boleh menyetujui bila aturan PT = 1 orang (pengajuan lahir saat aturan 2, lalu diturunkan).
- Admin yang mengajukan boleh menyetujui sendiri bila `kontrol.admin_boleh_sendiri` = ya (perilaku KF-T6, dicatat di
  jejak persetujuan).

## Kueri nilai cara bayar yang tersimpan (RISIKO spesifikasi — supaya alias yang kurang terlihat)

Jalankan di MongoDB data nyata (baca saja); nilai di luar `transfer, cash, tunai, kontan, giro, cek, qris, va, edc,
kartu, deposit, titipan` akan DITOLAK pintu baru bila dikirim ulang, dan dibaca `is_cash` = bukan tunai:
```
db.ar_receipts.distinct("method")
db.sales_orders.distinct("payments.method")
db.vendor_bills.distinct("payments.method")
db.contra_bons.distinct("payments.method"); db.contra_bons.distinct("schedule.method")
db.ap_payment_intents.distinct("method")
db.landed_cost_vouchers.distinct("payments.method")
db.cash_advances.distinct("payment_method")
db.penalties.distinct("payments.method")
db.payment_variance_decisions.distinct("effect.refund.method")
db.interco_settlements.distinct("method")
db.cash_transactions.distinct("method")
```
(Riwayat juga memuat kata bukan-cara-bayar yang sah: `writeoff`, `realokasi`, `finance_case`, `kontrabon`,
`kontrabon:deduction`, `netting`, "Transfer Simulasi" — dibaca apa adanya, tidak melewati pintu baru.)

## Cek layar

Belum dipotret (integrator memotret 1280/1024/390 px). Daftar periksa dari kode:

| Layar | (1) tabel ⊂ kartu | (2) bantalan kartu | (3) kepala kartu | (4) tombol mati beralasan | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong / angka 0 |
|---|---|---|---|---|---|---|---|---|
| Rekening & Saldo — bagian "Perubahan menunggu persetujuan" | 4–5 kolom, `data-table head-wrap`, kolom Keputusan `col-sticky-end`, wadah `overflow-x-auto` | `section-head` + `section-body` | judul + satu lencana jumlah (tanpa tombol) | Setujui/Tolak mati untuk pengaju sendiri + teks "Anda yang mengajukan — rekan lain yang memutus." | lencana "{n} menunggu" (jam), "Rekening baru" (plus) = `status-pill` ikon+teks+token | ≤ 50 baris, terbaru dulu, keterangan "Menampilkan n dari N"; tanpa kotak cari (biasanya sedikit) — **perlu dinilai** | tanpa `cash.approve`: "Perubahan ini berlaku setelah disetujui pemegang akses menyetujui perubahan rekening." (tidak ada "bukan wewenang") | 0 menunggu → bagian tidak tampil (satu keadaan kosong: kartu rekening) |
| Rekening & Saldo — kartu rekening | — (kartu) | tetap | tetap | — | lencana "Bawaan: …" ikon centang + teks + `bg-kn-success-soft`; "a.n. …" teks | kotak cari lama (nama/bank/nomor) | — | tetap |
| Rekening & Saldo — rincian (modal) | tabel mutasi lama tidak diubah | tetap | baris tombol "Ubah rekening" + "Cocokkan" di bilah sendiri (bukan kepala) | — | — | — | tombol Ubah hanya bila `cash.configure` | — |
| Form Tambah/Ubah rekening (`FormModal size=lg` + `FormSection` bernomor) | — | baku | — | "Tampilkan di dokumen" mati + alasan tertulis; Jenis mati saat ubah + "Jenis tidak bisa diubah sesudah rekening dibuat."; daftar centang kosong menulis sebabnya | — | — | — | — |
| Kwitansi (desktop & HP), Bayar tagihan, Voucher biaya masuk, Bayar & jadwal kontrabon, Uang muka (form & detail), Pengembalian selisih bayar, Pelunasan antar-PT | hanya sumber pilihan & label "Cara bayar" berubah | — | — | — | — | — | — | — |
| Pengaturan › Keuangan & Pajak › Master per Badan Usaha › Cara Bayar | 7 kolom di `ResponsiveTable stickyActions` (sama dengan master lain) | baku | baku | baku | baku | kotak cari bawaan panel | tombol per izin server (`can`) | baku |

Teks memakai token `kn-*` dan `text-fs-*` (tanpa hex/`text-[Npx]` baru); `verify_ui_standard` 15 = 15, `verify_role_gate_ui`
0 pelanggaran.

## Penggabungan

Dikerjakan di `c38fc92`; digabung di atas PK-42. Bentrok yang diselesaikan: blok izin KP-T8 dan PM-T1 di
`permissions_config.py` (keduanya dipertahankan, masing-masing dengan loop sendiri); `interco_service.meta` (PK-30
`defaults` + PM-T1 `settlement_methods` dari daftar induk); tombol tambah rekening (`EntityGatedButton` PK-42 + reset form
PM-T1); impor `PaymentVarianceDialog` (PK-42 `MoneyInput`/`parseDecimal` + PM-T1 daftar induk); hitungan uji KF-T1
`PMT1_KUNCI`, PRT9, indeks wajib (lapis B `9 + PK40_INDEKS + 1 + PMT1_INDEKS`, lapis A 16). tests_mem 1303; jest 698/698;
`verify_payment_vocab` + uji-diri hijau di HEAD gabungan.

## Cek layar (potret integrator)

Rekening & Saldo (`admin@`, data acuan). Kartu rekening: lencana "Bawaan: Transfer Bank" berikon (PM-T1). Temuan:

| Temuan | Perbaikan |
|---|---|
| 1280 px: lima kartu KPI sebaris terlalu sempit; `break-words` memecah angka di tengah ("Rp 146.625.6" / "88"), tanda minus terpisah | Angka tidak pindah baris; ikon kartu disembunyikan di lebar lg–2xl (`27f0853`); 1600 px ikon tampil lagi |

Bukti: `bukti/PM-T1/layar_rekening_1280_sebelum_angka_terpotong.png`, `layar_rekening_kpi_1280_sesudah.png`,
`layar_rekening_kpi_1600_sesudah.png`. Form rekening dan panel pengajuan perubahan belum dibuka di peramban.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), tiap jalan sesudah `restore_demo` (data acuan; tiga skrip seed yang sama
seperti garis dasar gagal).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`c9cf10f` — KF-T8, KP-T6, KP-T8, PK-30) | `--quick` | 16 FAIL | 16 | 3 (ganti nama + 2 balapan, lihat bawah) | 2 |
| 1 (`c9cf10f`) | `--ci` | 42 FAIL | 43 | 2 (ganti nama + 1 balapan) | 2 |
| 2 (`27f0853` — + perbaikan penjaga `c2cc412`, PK-42 `5e747b2`, PM-T1 `fd606e5`, cek visual) | `--quick` | 14 FAIL | 16 | 1 (ganti nama) | 2 (`config_wiring` + uji-diri) |
| 2 (`27f0853`) | `--ci` | 41 FAIL | 43 | 1 (ganti nama) | 2 |

- **`guard:page_tabs`** hanya berganti nama sejak MN-T1 (INV-UI-12 → INV-UI-12/13/14); merahnya sama dengan garis dasar
  (INV-UI-12 `wms/InventoryStockView.jsx`, berkas lama).
- Jalan 1: **`guard:role_gate_ui`** dan **`guard:role_label`** merah palsu karena balapan di kolam statik paralel —
  uji-diri `role_gate_ui` menulis probe sementara `features/__poc_role_gate_probe.jsx` ke `src` yang dipindai penjaga lain.
  Bukan dari unit mana pun; diperbaiki di `c2cc412` (uji-diri menghitung probe di memori; pemindaian melewati probe
  penjaga lain). Jalan 2 keduanya hijau.
- Penjaga statik per hitungan (`hitung_penjaga.sh`) tidak naik; PK-42 menurunkan `verify_ui_standard` 15 → 13 dan
  `audit_i18n_id` 109 → 104.

PK-42 dan PM-T1 masuk di jalan 2 (tanpa merah baru).


Dijalankan di salinan kerja (lingkungan B / statik):

| Pemeriksaan | Sebelum (HEAD) | Sesudah |
|---|---|---|
| `tests_mem` | 782 lulus / 2 dilewati / 2 xfail | 800 lulus / 2 dilewati / 2 xfail |
| jest `src/config/__tests__` + `src/features/__tests__` + `src/components` | 613 uji lulus; 35 suite gagal dimuat (34 radix + suite baru tanpa komponen) | 619 lulus; 34 suite gagal dimuat (radix, kendala lingkungan) |
| 6 suite radix yang menyentuh layar ini, dengan tiruan KNSelect | 49/50 (`roleGateSweep2` kasbon 1 gagal) | 49/50 (kegagalan sama); `phase4R1`, `phase4R2`, `decisionsD1`, `auditUi2G5b`, `uatV3S2Cbd` hijau |
| `hitung_penjaga.sh` (16 penjaga) | auth 28 · ui 15 · i18n 109 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya PASS/0 | identik |
| `verify_payment_vocab` (baru) | 27 pelanggaran (kode HEAD) | 0; self-test 18/18 |
| `verify_role_gate_ui` · `verify_config_text` · `verify_permission_checked` · `verify_ui_contrast` | PASS | PASS (581 cek izin; 433 kunci teks) |
| `audit_config_wiring.py --strict` (salinan berjalur) | bersih | bersih |
| `verify_approval_queues` bagian statik (pintu) | 77 pintu, 3 tanpa antrean (registrasi stok awal) | sama |
| `tests/test_fe03_access_catalog.py --noconftest` | — | 6/6 |
| `gen_config_key_index.py --check` | — | selaras |

## Keterbatasan / belum teruji

- U14 dan indeks unik parsial (`$exists` pada `default_receiving_methods.0`) **teruji di MongoDB 7 asli**: server menyala
  dengan indeks wajib terpasang, `test_bp_PMT1_bawaan_bersamaan.py` lulus, PK-14 lapis A menghitung 16 indeks wajib.
- Uji jalan peramban (U15) belum; hanya uji komponen.
- Skrip `pmt1_isi_rekening.py` diuji di lingkungan B (mode lapor tidak menulis; `--terapkan`; ulang 0) — tidak dijalankan
  ke database mana pun (H3).
- Pintu putusan `POST /api/bank-account-changes/{id}/decision` tidak tertangkap pola INV-APPR-01 (nama berakhir
  `decision`, bukan `decide`) dan tidak punya baris antrean Pusat Persetujuan/KPI beranda — pengajuan hanya tampil di
  Rekening & Saldo (spesifikasi tidak meminta antrean; `00` §7.4 melarang antrean baru di luar unit).
- Cache daftar cara bayar di layar per sesi: sesudah master Cara Bayar diubah, layar lain melihat daftar baru setelah
  dimuat ulang.
- Sapuan matriks izin `backend/tests_mem/sapuan_izin.py` mode cepat (lingkungan B): **merah 20 pelanggaran, himpunan
  identik dengan HEAD** (M0 6, M1 14: `ap-payments/{id}/cancel|resume`, `registration/sessions/*`, `dashboard`, dll. —
  tidak ada rute PM-T1). Rute baru lolos penilaian (`GET /api/payment-methods` = LOGIN_ONLY; rute lain menolak "kosong").
  `bukti/PM-T1/sapuan_izin_cepat_HEAD.txt`, `sapuan_izin_cepat_sesudah.txt`. Mode `--penuh` belum dijalankan.

## Hambatan lingkungan

- Suite jest yang memuat `cmdk`/`@radix-ui` gagal dimuat lokal (34 suite, sama di HEAD); enam yang menyentuh layar unit ini
  dijalankan dengan tiruan KNSelect/KNDatePicker (`p13_radix_stub.js`) di kedua kode.
- Saat menghitung garis dasar, `verify_approval_queues.py` sempat dijalankan dengan Python ber-`pymongo` sehingga bagian
  datanya **membaca** database dari `backend/.env` (hanya baca, tidak menulis). Sesudahnya hanya bagian statik (pintu)
  yang dihitung lewat fungsi skripnya.

## Yang perlu direview

- `effective_rows`/`resolve_row` (`entity_master_service`) menyaring baris nonaktif SEBELUM memilih lapisan, sehingga
  "Buat khusus PT lalu nonaktifkan" tidak pernah mematikan baris global di master lain (syarat bayar, lini produk, …).
  PM-T1 hanya menghindarinya untuk cara bayar; perbaikan umumnya butuh unit sendiri.
- Finance memegang `cash.configure` → ikut mengelola master Cara Bayar (lihat Menyimpang).
- Arah cara bayar ditegakkan server; uang muka kini menerima giro.
- Bentuk pengisian awal: dibaca dengan nilai awal + skrip lapor, bukan migrasi saat menyala.
- Indeks wajib baru di `REQUIRED_UNIQUE_INDEXES` (lihat Keterbatasan).
