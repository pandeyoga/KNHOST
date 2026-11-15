# MN-T3 — Satu form pembayaran, kartu pelanggan, kartu pemasok, dan telusur angka sampai dokumen

- Commit awal: `8dee8c6` (worktree kerja, basis B)        - Commit akhir: (a) `351d1f9`, (b) `0f49f18`, cek layar `c4dad6a` · `2bb1a76` · `5737da3`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke worktree tujuan pada HEAD **`dd172d4`** (`KM-T3 selesai`). Catatan: `dd172d4` tidak memuat
  commit `8dee8c6` secara hash, tetapi memuat isinya (`d08d664` = CR-T5 yang dipasang ulang integrator; `git diff
  8dee8c6 d08d664 -- backend frontend scripts` kosong) ditambah `1315ce6` (cek layar CR-T5) dan KM-T3 — lihat "Penggabungan".
- ID ditangani: — (unit fitur; keputusan K-17, K-18, K-34, K-46; spesifikasi `docs/blueprint/unit/MN-T3.md`)
- Risiko **tinggi** → dua serah-terima (`00` §8): **(a)** form baru, kartu, bacaan server, telusur laporan — pemanggil
  lama belum dialihkan (berkas lama `crm/ARReceiptModal.jsx` hanya mengekspor ulang); **(b)** pengalihan tiap titik masuk,
  penghapusan form bayar lama, U6/U7. Keadaan (a) disimpan di `$S/MN-T3_a_state/` (basis `8dee8c6`, 36 berkas) dan (a)
  tergabung ke `dd172d4` di `$S/MN-T3_a_merged/` (36 berkas; `test_MNT3_kartu_pintu.py` 11/11 dan jest `mnt3SatuForm` +
  `crt5MejaKredit` 30/30 di T).

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`; diperiksa di `8dee8c6`)

| # | Hasil di basis B |
|---|---|
| 1 | **Berlaku, bergeser** — `crm/ARReceiptModal.jsx:52`; dipakai **enam** tempat: `CollectionWorklist.jsx:144`, `DispatchPaymentGatePanel.jsx:85`, `FinanceDesk.jsx:238`, `MobileArReceipt.jsx:15`, + `ARAgingView.jsx:369` (PK-43) dan `BankReconciliationView.jsx:353` (PM-T3) |
| 2 | **Sebagian** — pelanggan tetap wajib (memuat `open-orders?customer_id`); pilihan rekening **sudah ada** sejak PM-T3 (`ReceiptPaymentFields`). Kunci idempotensi memakai state sendiri, bukan `useIntentKey` |
| 3 | **Tidak berlaku** — PK-19 mencabut tombol simulasi bayar, `onPay`, `payInvoice` (endpoint 410); `SoPaymentPanel.jsx:17` hanya jadwal & denda, tanpa tombol bayar. Pencarian `simulate-payment\|payInvoice` di `frontend/src`: 0 |
| 4 | **Berlaku, bergeser** — `VendorBillDetailPanel.jsx:102` (`doPay`), `contrabon/PayModal.jsx:27`, `bank/ReconContraBonModal.jsx:46` (`pay`), `LandedCostDetailPanel.jsx:101` (`doPay` → `/landed-costs/{id}/pay`, pintu lain di luar PK-05) |
| 5 | **Tidak berlaku** — PK-05 menambah `bank_account_id` ke `VendorBillPaymentCreate` (`schemas_purchasing.py:275`); isi kedua pintu kini sama `{amount, method, paid_at, bank_account_id, notes}` (kontrabon + `bank_line_id`) |
| 6 | **Bergeser** — `Customer360Panel.jsx:25` `HIST_TABS` 5 + tab Kredit/Tagihan/Rekening Koran/Riwayat Perubahan (CR-T1, CR-T5); diimpor `CustomerList.jsx:27` **dan** `CreditDeskView.jsx:35`; `crm.py:67`. Tanpa kwitansi, titipan, kasus; denda di tab Tagihan |
| 7 | **Berlaku** — `Supplier360Panel.jsx:33`, `SuppliersView.jsx:10`, `suppliers.py:367`; tanpa kontrabon & pembayaran; tagihan tampil tanpa cek izin tagihan |
| 8 | **Sebagian** — PK-43 sudah memasang telusur Laba-Rugi/Neraca (`FinancialStatementsView.jsx:99` `drill`) dan `source_doc`; Neraca Saldo hanya pindah tab tanpa tanggal (`GeneralLedgerTabs.jsx:63`); Arus Kas, Perubahan Ekuitas, Anggaran, Konsolidasi tanpa tautan (berlaku) |
| 9 | **Berlaku** — `FinReportLink.jsx:16`, `useAppNavigation.js:95` (`openDocument`) |
| 10 | **Berlaku** — `useIntentKey.js:5` |
| Server | `GET /api/penalties?customer_id` **sudah ada** (CR-T5) dan `GET /api/contra-bons?supplier_id` **sudah ada** → tidak berlaku; baru: `GET /api/vendor-bills?supplier_id`, `GET /api/finance-cases?customer_id` |

## Perubahan

### Server (hanya bacaan; tanpa endpoint tulis, koleksi, field, izin, atau pengaturan baru)

| Berkas | Isi |
|---|---|
| `backend/services/party_card.py` (baru) | Tabel bagian kartu → izin (`CUSTOMER_SECTIONS`, `SUPPLIER_SECTIONS`); `customer_card` (+ `sections_allowed`, nominal kredit/piutang, kwitansi, riwayat, tindak lanjut = `null` tanpa izinnya, K-18); `supplier_card` (+ `payables` per PT, `bills`, `payments` = `vendor_bills.payments[]` tidak batal, `contra_bons` = `contra_bon_service.list_contra_bons`, `landed_costs`, `sections_allowed`; tagihan/PO/retur/biaya masuk `null` tanpa izin sumbernya; daftar dokumen gabungan disaring per izin) |
| `backend/services/vendor_bill_service.py` | `open_payables(scope_q)` — SATU pembaca tagihan berhutang terbuka (D1), dipakai ringkasan Hutang › Tagihan dan kartu pemasok |
| `backend/routers/vendor_bills.py` | ringkasan hutang memakai `open_payables` (perilaku sama); `GET /vendor-bills?supplier_id` |
| `backend/routers/crm.py`, `routers/suppliers.py` | `…/360` lewat `party_card` (PT dari sesi `resolve_scope_ids`) |
| `backend/routers/finance_cases.py`, `services/finance_case_service.py` | `customer_id` |
| `backend/services/work_desk_service.py` | baris "Hutang supplier jatuh tempo" membawa `supplier_id` (tombol Bayar → kartu pemasok) |

### Layar

| Berkas | Isi |
|---|---|
| `features/finance/payments/ReceivePaymentModal.jsx` (baru) | Form A (tanda tangan spesifikasi + kompatibel `preset`, `offline`, `testId`, `onError`): langkah Pilih pelanggan, banner PT, isian spesifikasi, "Simpan kwitansi", konfirmasi persis, Semua PT mati + petunjuk, `useIntentKey`, klik ganda ditahan, `bankLineId` → kas kwitansi ditautkan ke mutasi; `receiptBody` (isi permintaan) |
| `features/finance/payments/PaySupplierModal.jsx` (baru) | Form B: Pemasok/Dokumen/Sisa hutang hanya-baca, isian spesifikasi, rekening aktif PT dokumen, niat menggantung (PK-05), konfirmasi persis, `bankLineId` (kontrabon → `pay-from-bank-line`; tagihan → `pay` lalu tautkan mutasi); `payBody` |
| `features/finance/cards/partyCards.jsx` (baru), `context/AppNavContext.jsx`, `AppViewRouter.jsx` | `openCustomerCard/openSupplierCard/closeCard`; `PartyCardHost` (DetailModal `lg`); `CustomerCardLink`/`SupplierCardLink` (teks biasa tanpa izin lihat); `DocPill` (ikon+teks+warna); `SectionState` (memuat/galat/kosong) |
| `features/crm/Customer360Panel.jsx`, `CustomerCardSections.jsx` (baru), `CustomerBillingTab.jsx` (`show`) | Kartu pelanggan: kepala 4 angka, "Terima pembayaran", enam bagian chip menurut `sections_allowed`; varian halaman CRM + "Kredit", "Riwayat Perubahan" |
| `features/purchasing/Supplier360Panel.jsx`, `SuppliersView.jsx`, `SupplierPriceList.jsx` | Kartu pemasok: kepala 3 angka (Semua PT per PT), enam bagian, Bayar per baris; daftar produk hanya dimuat pemegang `supplier.update` |
| `features/finance/traceLedger.jsx` (baru), `GeneralLedgerTabs.jsx`, `GeneralLedger.jsx`, `CashFlowTab.jsx`, `EquityChangesTab.jsx`, `BudgetView.jsx`, `BudgetParts.jsx`, `GroupConsolidationView.jsx`, `FinancialStatementsView.jsx` | Telusur bagian E + Semua PT/PT lain → petunjuk |
| (b) `FinanceDesk.jsx`, `sales_admin/DeskQueueCard.jsx` (`_titleNode`), `ARAgingView.jsx`, `ARAgingDetail.jsx`, `crm/CollectionWorklist.jsx`, `payments/SoPaymentPanel.jsx`, `orders/DispatchPaymentGatePanel.jsx`, `orders/OrderDetailPanel.jsx`, `admin/po/PODetailPanel.jsx`, `BankReconciliationView.jsx`, `bank/ReconLinesTable.jsx`, `bank/ReconPayablePicker.jsx` (baru), `purchasing/VendorBillDetailPanel.jsx`, `VendorBillsView.jsx`, `contrabon/ContraBonDetailPanel.jsx`, `ContraBonListTable.jsx`, `ContraBonsView.jsx`, `CashManagementView.jsx`, `sales/mobile/MobileArReceipt.jsx` | Pengalihan titik masuk (tabel di bawah) |
| (b) dihapus | `crm/ARReceiptModal.jsx`, `purchasing/contrabon/PayModal.jsx`, `finance/bank/ReconContraBonModal.jsx`, panel isian bayar di `VendorBillDetailPanel.jsx` |
| Penjaga | `scripts/guardrails/verify_error_notice.py`: `Customer360Panel.jsx` keluar dari `MODAL_BASELINE` (diminta penjaga — baseline basi; mengencang) |
| Dokumen | `ENTITY_REGISTRY.md` (bagian MN-T3, tanpa koleksi/field baru), `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_16_END_TO_END_PROCESS_FLOWS.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (W §9.31; T §9.32 sesudah §9.31 KM-T3), `CODEBASE_MAP.md` (dibangkitkan) |
| Uji | `tests_mem/test_MNT3_kartu_pintu.py` (11), `tests_mem/test_MNT3_U7_satu_pintu_layar.py` (3), jest `features/__tests__/mnt3SatuForm.test.js` (34), berkas bersama `payments/__tests__/fixtures/mnt3_isi_form.json`; disesuaikan (perilaku yang sengaja berubah): `crt5MejaKredit` (d) (bagian kartu), `pmt3KwitansiRekening` (label "Catat sebagai kwitansi" + mutasi tanpa kode bayar), `phase4R2` (form baru), impor/mock `ARReceiptModal` → `ReceivePaymentModal` di `pmt1CaraBayar`, `pmt3KwitansiRekening`, `pmt4TitipanSales`, `phase4R1`, `mnt2LayarKeuangan`, `pk17NominalBerizin` |

### Titik masuk sesudah (b)

| Titik masuk | Form A "Terima pembayaran" | Form B "Bayar" |
|---|---|---|
| Beranda Keuangan › Perlu Tindakan | baris "Uang masuk perlu dicatat" (pelanggan + pesanan); nama pelanggan → kartu | baris "Hutang jatuh tempo" (PO) → kartu pemasok (lihat Menyimpang) |
| Piutang › Saldo & Umur | tombol per baris (kolom Aksi menempel kanan) + rincian "Terima pembayaran"; nama → kartu | — |
| Piutang › Penagihan & Penerimaan | ikon per baris; nama → kartu | — |
| Kartu pelanggan / kartu pemasok | kepala kartu | baris tagihan/kontrabon bersisa |
| Detail pesanan | panel bayar `sop-receive`; nama pelanggan → kartu | — |
| Gerbang kirim | "Terima pembayaran (Rp …)" | — |
| Kas & Bank › Rekonsiliasi | "Catat sebagai kwitansi" (mutasi masuk belum cocok; aturan PM-T3 kwitansi menunggu dipertahankan) | "Bayar pemasok" → pilih kontrabon/tagihan → form B |
| Hutang › Tagihan / Kontrabon | — | detail tagihan, tombol cepat daftar, detail kontrabon; nama pemasok → kartu |
| Detail PO | — | nama pemasok → kartu |
| Kas & Bank › Transaksi Kas | — | tautan "Membayar tagihan pemasok? Pakai form Bayar pemasok" → Hutang › Tagihan |
| HP sales | `MobileArReceipt` (antrean luring tetap) | — |

## Uji penerimaan

Merah kode lama: tests_mem — berkas uji yang sama dengan berkas server dikembalikan ke `8dee8c6`
(`bukti/MN-T3/a_tests_mem_merah_kode_lama.txt`); jest — suite gagal dimuat "Cannot find module
'../finance/payments/ReceivePaymentModal'" (`a_jest_merah_kode_lama.txt`); U6 juga dijalankan pada keadaan (a)
(`b_U6_merah_keadaan_a.txt`); U7 pada `frontend/src` `8dee8c6` (`b_U7_merah_kode_lama.txt`).

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | komponen | merah (modul belum ada) | lulus — tanpa `customerId`: langkah "Pelanggan", isian lain belum tampil, simpan mati; pilih → isian tampil. Dengan `preselectOrderId`: "Atur sendiri", alokasi so1 = 8.000.000, tanda "dibuka" |
| U2 | komponen | merah | lulus — dua klik cepat → satu konfirmasi "Catat penerimaan Rp 5.000.000 dari Toko C ke BCA Operasional · … untuk Sukacita?" ("Ya, simpan"); tepat satu `POST /ar-receipts` ber-`Idempotency-Key`; isi = berkas bersama |
| U3 | B | lulus (pintu PK-19/PM-T3 sudah ada — uji kontrak isi form) | lulus — 1 kwitansi; sisa 3.000.000; rekening kas = rekening form; contoh angka di bawah |
| U4 | B (+ komponen U4b) | lulus (pintu PK-05 sudah ada); U4b merah | lulus — tagihan 7.000.000: 1 kas keluar rekening form, `paid`; kontrabon 4.000.000: 1 kas, tagihannya `paid`. U4b: konfirmasi "Bayar Rp 7.000.000 ke Pemasok S dari … untuk Sukacita?", satu POST ber-kunci, isi = berkas bersama |
| U5 | komponen | merah | lulus — form A dan form B: tombol mati + "Pilih satu PT untuk mencatat pembayaran.", tanpa POST |
| U6 | komponen | merah — keadaan (a) 13/13 peran (mis. "Bayar" tagihan tampil untuk peran tanpa `vendor_bill.pay`; tombol baris Piutang belum ada) | lulus — 13 peran × 8 titik masuk (Saldo & Umur, Penagihan, detail pesanan, gerbang kirim, Rekonsiliasi masuk/keluar, detail tagihan, + kartu pelanggan U15) tampil ⇔ izin; Rekonsiliasi: pemberi `onRecordReceipt` = `ar_receipt.create` (statik); kartu pemasok Bayar ⇔ izin bayar |
| U7 | statik | merah — kwitansi: 1 berkas tetapi `crm/ARReceiptModal.jsx`; bayar pemasok: 3 berkas; simulasi: 0 (sudah PK-19) | lulus — `ReceivePaymentModal.jsx`; `PaySupplierModal.jsx`; 0 |
| U8 | B | merah (`KeyError: sections_allowed`) | lulus — 200, profil terisi, `sections_allowed == []`, `credit`/`payments`/`order_history` `null`, tidak ada nominal piutang/plafon bukan nol di mana pun di jawaban. + U8b (tambahan): Admin semua bagian |
| U9 | B | **lulus** (aturan kepemilikan sudah berlaku) | lulus — sales lain 403; pemilik 200 |
| U10 | B | **lulus** (penjaga PT sudah berlaku) | lulus — akun `ent_kanda` 403, tanpa angka C; `ar-receipts?customer_id` = [] |
| U11 | B | **lulus** (saringan sudah ada) | lulus — 1 kwitansi 1.000.000; denda hanya C. + X1 (tambahan): `finance-cases?customer_id` — merah lama (semua kasus), lulus |
| U12 | B | merah (`KeyError: payables`) | lulus — `payables.outstanding` 8.000.000 (7 + 3 − 2 jt), `payments` = [2.000.000] |
| U13 | B | merah | lulus — lima bagian keuangan `null`, `sections_allowed == ["lainnya"]`, tanpa dokumen tagihan |
| U14 | B | merah (saringan diabaikan: 4 baris) | lulus — 2 baris; pemasok lain 0 |
| U15 | komponen | merah | lulus — 13 peran: chip bagian = tabel izin (cermin `party_card.py`), kepala kartu & "Terima pembayaran" ⇔ izin, membuka tiap bagian tidak memanggil GET tanpa izin |
| U16 | komponen | merah | lulus — Neraca Saldo per 2026-02-28 → `{tab: "ledger", code: "1-1100", end: "2026-02-28"}` (Semua PT → petunjuk); Anggaran → `start` 01-01 / `end` 12-31 tahun anggaran; Konsolidasi PT lain → "Pindah ke Kanda untuk menelusuri angka ini.", laba bersih tidak bisa diklik |
| U17 | penjaga | — | page_tabs 1 = 1 (INV-UI-14 lulus, kartu bukan tab tingkat ketiga), create_modal 5 = 5, i18n 102 = 102, `roleReach.test.js` lulus |
| U18 | layar (uji jalan) | — | **belum diuji jalan** (pelaksana) → diuji jalan integrator, tiga cacat diperbaiki (lihat Gate › Integrator) |

### Contoh angka (`00` §9) — kwitansi 5.000.000 → kas → jurnal → sisa piutang

C3: pesanan terkirim 8.000.000 (jurnal surat jalan Dr 1-1200 8.000.000 / Cr 4-1000 8.000.000). Isi form A 5.000.000
"tertua dulu" → kwitansi → kas masuk `KSC/CASH-00006` 5.000.000 di rekening yang dipilih → jurnal `KSC/JE-00008`
**Dr 1-1100 Kas Besar / Bank 5.000.000 / Cr 1-1200 Piutang 5.000.000** → sisa piutang pesanan 8.000.000 − 5.000.000 =
**3.000.000** (= saldo 1-1200 pesanan itu 8.000.000 − 5.000.000). Unit tidak mengubah arah/akun jurnal (pintu PK-19).

## Penyimpangan dari blueprint

1. **Panel samping → pop-up rincian baku `DetailModal` (`lg`, 896 px)**: lapisan `fixed inset-0` buatan sendiri di
   berkas baru ditolak INV-UI-11; DetailModal sudah membawa Esc, klik latar, kunci gulir, layar penuh di HP. Tetap bukan
   tab hub (ASUMSI unit terpenuhi).
2. Halaman Pelanggan CRM & meja Kredit & Plafon memakai komponen yang sama (varian "page") dengan dua bagian tambahan
   yang sudah ada — "Kredit" (CR-T1) dan "Riwayat Perubahan" — supaya fungsi lama tidak hilang; kartu (pop-up) tetap enam.
3. `sections_allowed` memuat juga kunci `ringkasan` (kepala kartu); enam bagian lainnya sesuai spesifikasi.
4. **Perlu Tindakan › Hutang jatuh tempo** berisi **PO** (bukan tagihan/kontrabon) dan tagihan menunggu ACC (belum
   bisa dibayar): tombol "Bayar" baris PO membuka **kartu pemasok** (tagihan PO itu dibayar dari sana dengan form B);
   server menambah `supplier_id` ke baris (bacaan).
5. **Konsolidasi**: matriks hanya memuat pos kelompok (Pendapatan, HPP, …), tidak ada baris berkode akun. Angka per PT
   pada pos rincian membuka Laporan Keuangan PT itu (tahun / tanggal sama), dari sana akun → buku besar → dokumen
   (PK-43); PT lain → petunjuk pindah PT. Total/laba tidak bisa diklik.
6. **Neraca Saldo** mendapat isian "Per tanggal" (`as_of` endpoint lama) — perlu untuk preset `end` U16.
7. **Selisih bayar pemasok**: dialog selisih yang ada hanya punya takaran untuk pelanggan; tidak ada endpoint takar
   selisih pemasok (endpoint baru di luar lingkup). Bayar sebagian = sisa tetap hutang (perilaku PK-05).
8. **Rekonsiliasi keluar**: selain kontrabon, tagihan pemasok terposting bersisa juga bisa dipilih; tagihan dari mutasi
   = `pay` lalu tautan mutasi (dua panggilan; bila tautan gagal, pembayaran tetap tercatat dan pesannya tampil).
9. **Rekonsiliasi masuk**: "Catat sebagai kwitansi" tampil di tiap mutasi masuk belum cocok, **kecuali** semua kode bayar
   mutasi itu sudah punya kwitansi menunggu (aturan PM-T3 dipertahankan — cocokkan saja).
10. U3 memakai pelanggan **C3** berbentuk sama (agar U11 tetap menghitung 1 kwitansi C) dengan jurnal surat jalan
    (supaya kwitansi mengkredit piutang, bukan uang muka 2-1400).
11. Bayar voucher biaya masuk barang tetap form sendiri (`/landed-costs/{id}/pay` bukan pintu PK-05 — di luar lingkup).

## Asumsi

- "Jatuh tempo 7 hari" = nama angka kepala kartu pemasok (definisi tampilan dari spesifikasi, termasuk yang sudah lewat
  jatuh tempo), bukan aturan bisnis — tidak dijadikan pengaturan.
- "Uang muka ke pemasok" = sisa uang muka yang bisa dipotong di kontrabon (`contra_bon_service.available_credits`, per PT).
- Kepala kartu pelanggan: Eksposur & Plafon dari `GET /customers/{id}/exposure` (angka mesin, kotak CR-T5), Lewat jatuh
  tempo & Titipan + saldo kredit dari `GET /customers/{id}/balance` (CR-T2). Semua PT → PT pemilik data pelanggan, berlabel.
- Bagian "Riwayat Lain" dan "Tindak Lanjut" = izin `order.view`.

## Cek layar (dari kode; integrator memotret 1280/1024/390)

| Layar | Lebar terhitung | Kolom aksi / tombol | Status | Mati beralasan | Catatan |
|---|---|---|---|---|---|
| Form Terima pembayaran (FormModal `md` 672 → isi ±640) | isian 2 kolom (sm), daftar tagihan baris fleksibel | kaki: total + alasan + Batal/Simpan `btn-sm whitespace-nowrap`, membungkus | lencana selisih `status-pending` + ikon | "Pilih satu PT…", "Pilih pelanggan dulu.", "Isi nominal diterima.", alasan rekening PM-T3 | banner PT di bilah sendiri; tanpa `type="date"` (KNDatePicker); tanpa hex / `text-[Npx]` (berkas baru 0) |
| Form Bayar pemasok (`md` ±640) | 3 kolom hanya-baca + 2 kolom isian | sama | — | "Pilih satu PT…", "Isi nominal dibayar.", "Pilih rekening…"; niat menggantung = bilah Lanjutkan/Batalkan | |
| Kartu pelanggan (DetailModal `lg` 896 → isi 864; halaman CRM 1280: kolom kanan ±686, 1024: ditumpuk ±760) | Tagihan & Jadwal 7 kol ±650 (CR-T5), Rekening Koran 6 kol ±650, Kwitansi 5 kol ±590, Kasus 4 kol ±500 | "Terima pembayaran" di kepala; alasan Semua PT di bilah sendiri di bawah kepala | `DocPill` ikon+teks+warna (`status-shipped/paid/pending/draft/cancelled/rejected`) | ya | 4 angka `MetricRow` (−Rp tidak patah); chip bagian membungkus; memuat/galat "Bagian ini tidak bisa dimuat. Coba lagi."/kosong "Belum ada data."; daftar berhalaman 10 + jumlah total |
| Kartu pemasok (sama) | Tagihan 7 kol ±654–666 (halaman 1280 kolom kanan ±654 → bisa bergulir), Kontrabon 7 kol ±652, Pembayaran 5 kol ±588 | Bayar `btn-sm` di `col-sticky-end` | `DocPill` | Semua PT: bilah alasan di atas tabel | 3 angka `MetricRow`; Semua PT per PT berlabel |
| Piutang › Saldo & Umur | tabel ±860 + Aksi ±150 = ±1010 (1280 muat ±1018; 1024 bergulir, Aksi menempel kanan) | `col-sticky-end` | (lama) | bilah "Pilih satu PT…" di atas tabel | nama pelanggan = tautan kartu |
| Perlu Tindakan | baris fleksibel (DeskQueueCard) | label "Terima pembayaran"/"Bayar" `btn-xs` | (lama) | — | nama pelanggan tautan kartu |
| Detail pesanan › panel bayar | kepala tombol membungkus (`flex-wrap`) | "Terima pembayaran" `btn-sm` | (lama) | alasan di bilah sendiri | |
| Rekonsiliasi | label tombol lebih pendek; pilih dokumen di FormModal `lg` (isi ±864, baris membungkus) | `btn-sm` | lencana "nominal tepat"/"selisih" ikon+teks+warna | alasan PM-T3 tetap | |
| Detail tagihan / daftar tagihan / kontrabon | panel bayar sisipan dihapus (−1 huruf < 12 px, −1 hex) | "Bayar" hanya pemegang izin | (lama) | — | nama pemasok tautan kartu |
| Laporan (Neraca Saldo, Arus Kas, Perubahan Ekuitas, Anggaran, Konsolidasi) | tanpa kolom baru | angka/nama = `link-button` | — | petunjuk telusur di bilah `notice-bar info` | Neraca Saldo + "Per tanggal" (KNDatePicker) |

Daftar periksa brief: (1) tabel ≤ kartu atau kolom aksi menempel — ya; (2) `section-card` berbantalan (`section-head`/
`section-body`/`section-pad`) — ya; (3) kepala kartu tidak dijejali (alasan & angka di bilah sendiri) — ya; (4) tombol
mati beralasan tertulis — ya; (5) status ikon+teks+warna — ya (kelas yang ada); (6) daftar panjang berhalaman + jumlah —
ya (pencarian tetap di layar sumber); (7) teks izin — "Anda belum punya akses ke bagian keuangan pelanggan ini." hanya
bila tidak ada bagian; (8) satu teks kosong per bagian, angka 0 netral (`MetricRow`). **Belum diuji jalan.**

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`5737da3`**:

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`5410979`: 12 / 39). Kuitansi: `bukti/MN-T3/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- HEAD cabang tetap `dd172d4` sejak pelaksana menggabung. (a) dipasang dari `$S/MN-T3_a_merged/` → **`351d1f9`**
  (`tests_mem` integrator **2276/2/2**, 0 gagal — sekali, untuk keadaan antara yang belum diuji penuh pelaksana); (b) = pohon
  T disalin di atas (a) → **`0f49f18`**, diperiksa berkas demi berkas sama dengan T (`tests_mem` 2279 dan jest 1105 dari
  pelaksana, pohon sama — tidak diulang, mode hemat pemilik 15 Nov).
- Unit tanpa uji lapis A (U3/U4/U8–U14 lapis B, sisanya komponen/statik); lingkungan A dipakai untuk uji jalan **U18** dan gate.
- Uji jalan U18 (data acuan sesudah `restore_demo`, peramban zona Asia/Jakarta, 1280/1024/390): **tiga cacat ditemukan dan
  diperbaiki**:
  1. **`c4dad6a`** — Piutang › Saldo & Umur di 1024 px: tabel 10 kolom ±1010 px dalam kartu ±762 px, kolom umur tertutup
     gulir dan nama pelanggan terhimpit. Kini tabel `min-w-[700px]`, kolom "Kredit" dilebur ke bawah nama pelanggan
     (`CreditStatusPill`, testid tetap), tombol baris "Terima" (judul & `aria-label` "Terima pembayaran"), kaki tabel
     menyesuaikan → 9 kolom = lebar kartu di 1024 dan 1280.
  2. **`2bb1a76`** — kepala kartu pemasok dan "Hutang per PT" menampilkan kode mentah **"PT ent_ksc"**: `party_card._nama_pt`
     membaca koleksi `entities` (kosong) → kini `business_entities` (`short_name` › `name` › `legal_name`). Uji
     `test_MNT3_kartu_pintu.py` U12 ditambah dua asersi (label ≠ kode PT): kode lama **1 gagal**, kode baru **11 lulus**.
     Sesudah perbaikan kepala kartu: "Kanda Fabric SUP-00001 · Aktif · Jakarta · PT Sukacita · Barang dari badan usaha grup".
  3. **`5737da3`** — 390 px (tampilan penuh): kartu angka `MetricRow` dua sebaris ±175 px memotong "Rp 106.665.3…" di tepi
     kartu. Di ≤640 px ikon hiasan disembunyikan, angka 16 px dan patah di spasi bila perlu; di atas 640 px tidak berubah
     (komponen bersama — semua layar yang memakai `MetricRow` ikut membaik di HP).
- Potret (`bukti/MN-T3/cek_*.png`): form **Terima pembayaran** dari baris Saldo & Umur (1280/1024/390 — banner PT, pelanggan
  terkunci, KNDatePicker, rekening penerimaan terkunci beralasan, alokasi "Tertua dulu/Atur sendiri", kaki total + Batal/Simpan
  kwitansi; `overflowX` 0); form **Bayar pemasok** (1024); **Saldo & Umur** (1280/1024/390, tabel 390 bergulir di dalam kartu,
  Aksi menempel); **kartu pemasok** (1024, kepala sesudah perbaikan 2); **kartu pelanggan** dari nama di Saldo & Umur (1280/1024/390 — kepala nama + lencana segmen/blokir + "Terima pembayaran", empat angka Eksposur/Plafon/Lewat jatuh tempo/Titipan & saldo kredit tidak terpotong, chip bagian, Jadwal tagihan 7 kolom = lebar kartu di 1024; di 390 chip bergulir mendatar (pola baku `FilterChips` ≤640 px) dan tabel bergulir di dalam kartu). Potret kartu pelanggan diambil sesudah gate (data acuan sesudah gate; baca-saja).
- Jest di `5737da3`, 19 suite yang menyentuh Saldo & Umur, form/kartu baru, `MetricRow`, meja kredit: **242 lulus, 0 gagal**;
  3 suite gagal dimuat (`phase3P4Finance`, `phase4R1`, `phase4R2` — `cmdk`/`@radix-ui`, termasuk 35 suite garis dasar).

Pelaksana (catatan asli):

Belum dijalankan (integrator). Angka lingkungan B ada di bagian "Angka uji" (diisi di bawah).

## Angka uji

| | W sebelum (B `8dee8c6`) | W sesudah | T sebelum (HEAD `dd172d4`, angka KM-T3) | T sesudah |
|---|---|---|---|---|
| `tests_mem` | 2245 lulus / 2 dilewati / 2 xfail | **2259** / 2 / 2 (+14 MN-T3) | 2265 / 2 / 2 | **2279** / 2 / 2 (+14) |
| jest penuh | 1064 lulus (35 suite gagal dimuat `cmdk`/`@radix-ui`) | **1097** + 1 merah `pmt3` (diperbaiki; 7 suite terkait 96/96) → 1098 | 1071 (35 suite sama) | **1105** lulus (35 suite sama) |
| `hitung_penjaga.sh` | auth 26 · ui_standard 11 · i18n 102 · create_modal 5 · page_tabs 1 · to_list 5 · entity_label 2 · lain 0 | sama, **ui_standard 9** (−2: panel bayar sisipan `VendorBillDetailPanel` dihapus) | sama dengan W sebelum | sama, **ui_standard 9** |
| `verify_role_gate_ui` · `verify_detail_modal` | 31/0 · 30/0 | 31/0 · 30/0 | 31/0 · 31/0 | 31/0 · 31/0 |
| `verify_cash_single_door` · `verify_posting_coverage` | 748/0 · 137/0 | 749/0 · 137/0 | 749/0 · 137/0 | 750/0 · 137/0 |
| `verify_atomic_claim` (+uji-diri 64) | 161/0 · hijau | 161/0 · hijau | 161/0 · hijau | 161/0 · hijau |
| `verify_payment_vocab` · `verify_config_text` | 1855/0 · — | 1859/0 · 3472/0 | 1858/0 · 3486/0 | 1862/0 · 3486/0 |
| `verify_config_fallback` (+`--entity`) · `audit_config_wiring --strict` · `check_nav_map` | — | 161/0 (161/0) · hijau · — | 162/0 · hijau · PASS | 162/0 (162/0) · hijau · PASS |
| `verify_error_notice` | 0 | 0 (baseline dikencangkan, lihat Perubahan) | 0 | 0 |

Catatan hemat uji: `tests_mem` penuh W dijalankan sekali sesudah (b); sesudahnya hanya `test_MNT3_kartu_pintu.py`
diubah (fixture surat jalan C3 + asersi contoh angka U3) → berkas itu dijalankan ulang 11/11, lalu masuk jalan penuh T.
Jest penuh W: satu merah `pmt3KwitansiRekening` (tombol tampil di mutasi yang kode bayarnya sudah berkwitansi menunggu)
→ aturan PM-T3 dipertahankan di `ReconLinesTable.jsx`; jalan penuh T hijau.

## Penggabungan

- HEAD tujuan **`dd172d4`** (`git -C /home/user/KNHOST rev-parse HEAD`); T = `$S/wt22` detached di `dd172d4` +
  `backend/.env` disalin. `dd172d4` tidak memuat hash `8dee8c6`, tetapi memuat isinya (`d08d664`; selisih kode kosong).
- 69 berkas dari W: **sama dengan B → disalin**; beda → `git merge-file`: `AppViewRouter.jsx`, `ENTITY_REGISTRY.md`,
  `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md` (otomatis, tanpa bentrok); **bentrok 1**: `docs/KN_32_…` — HEAD menambah
  §9.31 KM-T3 di tempat yang sama → keduanya dipertahankan, bagian MN-T3 menjadi **§9.32** (di W tetap §9.31).
  Tiga berkas dihapus (`ARReceiptModal.jsx`, `PayModal.jsx`, `ReconContraBonModal.jsx`) — hanya di pohon kerja.
- Dibangkitkan ulang di T: `CODEBASE_MAP.md`; `configKeyIndex.json` (tidak berubah). `access_modules.py`, katalog
  pengaturan, izin bawaan, indeks: tidak disentuh → fixture akses, `*_KUNCI`, PRT9, indeks wajib tidak berubah.
- Draf laporan + bukti hanya di W.

## Hambatan lingkungan

- 35 suite jest gagal dimuat karena `cmdk`/`@radix-ui` lokal (sama dengan basis).
- `verify_config_text`/`verify_config_fallback` butuh `bcrypt` → dijalankan dengan venv uji.

## Yang perlu direview

- Penyimpangan 1, 4, 5 (bentuk kartu, Hutang jatuh tempo, Konsolidasi) dan 7 (selisih bayar pemasok).
- K-18: peran ber-`customer.view` tanpa izin kredit (md, sample_admin) tidak lagi menerima `credit`/nominal di `…/360`;
  peran ber-`supplier.view` saja (md_quality, qc) tidak lagi melihat nominal tagihan/PO di kartu pemasok (RISIKO unit).
- `suppliers.advance_balance` (uang muka lewat kasus keuangan) tidak ikut angka "Uang muka ke pemasok" — perlu keputusan
  bila harus digabung.
- Titik henti §6: tidak ada yang tersentuh (H3 data nyata, H4 akun/arah jurnal, H5 sakelar PT, H7 middleware, H8 rahasia).

Status: implemented_pending_review
