# MN-T3 — Satu form pembayaran, kartu pelanggan, kartu pemasok, dan telusur angka sampai dokumen

| | |
|---|---|
| Gelombang | Modul — menu dan layar |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | PK-05, PK-19, PM-T3, CR-T5 (bagian E juga PK-43; lihat "Asumsi") |
| Menutup temuan | — |
| Keputusan | K-17, K-18, K-34, K-46 |
| Standar | §3.1 (Z1, Z2, Z6), §3.4 (N1–N5), §4 (L1, L3, L4, L7, L8), §5 (D1, D4), §6 |
| Lingkungan uji | B · uji komponen · uji jalan layar di A |

## Tujuan

Menerima pembayaran pelanggan dan membayar pemasok masing-masing memakai **satu form** yang sama dari titik masuk mana
pun, tanpa pindah menu. Satu **kartu pelanggan** dan satu **kartu pemasok** menampilkan seluruh posisi uangnya dan bisa
dibuka dari baris mana pun. Telusur angka → akun → jurnal → dokumen, yang dipasang PK-43 untuk Laba-Rugi dan Neraca,
berlaku di semua laporan keuangan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Form kwitansi pelanggan adalah satu komponen, dipakai di empat tempat: daftar penagihan, gerbang kirim, Meja Finance, HP sales | `frontend/src/features/crm/ARReceiptModal.jsx:39` (`ARReceiptModal`) · `frontend/src/features/crm/CollectionWorklist.jsx:132` (`ARReceiptModal`) · `frontend/src/features/orders/DispatchPaymentGatePanel.jsx:85` (`ARReceiptModal`) · `frontend/src/features/finance/FinanceDesk.jsx:163` (`ARReceiptModal`) · `frontend/src/features/sales/mobile/MobileArReceipt.jsx:15` (`ARReceiptModal`) |
| 2 | Form itu wajib diberi pelanggan dari pemanggil; tidak bisa dibuka tanpa pelanggan, dan tidak punya pilihan rekening | `frontend/src/features/crm/ARReceiptModal.jsx:49` (`method`) |
| 3 | Detail pesanan punya jalur bayar sendiri: panel bayar dan tombol "simulasi pembayaran" yang memanggil pintu lain | `frontend/src/features/finance/payments/SoPaymentPanel.jsx:15` (`SoPaymentPanel`) · `frontend/src/features/orders/OrderDetailPanel.jsx:637` (`simulate-payment-button`) · `frontend/src/hooks/useAppActions.js:480` (`payInvoice`) |
| 4 | Bayar pemasok punya empat form: di detail tagihan, di kontrabon, dari mutasi bank, dan di voucher biaya masuk | `frontend/src/features/purchasing/VendorBillDetailPanel.jsx:56` (`pay`) · `frontend/src/features/purchasing/contrabon/PayModal.jsx:23` (`PayModal`) · `frontend/src/features/finance/bank/ReconContraBonModal.jsx:56` (`pay-from-bank-line`) · `frontend/src/features/purchasing/LandedCostDetailPanel.jsx:45` (`pay`) |
| 5 | Isi permintaannya pun berbeda: bayar tagihan tanpa rekening; bayar kontrabon dengan rekening dan baris mutasi | `backend/schemas_purchasing.py:275` (`VendorBillPaymentCreate`) · `backend/schemas_contrabon.py:56` (`ContraBonPayIn`) |
| 6 | Panel pelanggan 360 hanya diimpor daftar pelanggan CRM; tabnya enam, tanpa jadwal tagihan, kwitansi, titipan, denda, kasus, rekening koran | `frontend/src/features/crm/Customer360Panel.jsx:18` (`HIST_TABS`) · `frontend/src/features/crm/CustomerList.jsx:27` (`Customer360Panel`) · `backend/routers/crm.py:58` (`get_customer_360`) |
| 7 | Panel pemasok 360 hanya diimpor layar Pemasok; memuat PO, tagihan, retur, harga, dokumen, skor — tanpa kontrabon dan pembayaran | `frontend/src/features/purchasing/Supplier360Panel.jsx:33` (`Supplier360Panel`) · `frontend/src/features/purchasing/SuppliersView.jsx:10` (`Supplier360Panel`) · `backend/routers/suppliers.py:367` (`get_supplier_360`) |
| 8 | Di HEAD laporan keuangan tidak punya tautan dari angka dan detail jurnal hanya menampilkan label sumber. PK-43 memasang telusur untuk Laba-Rugi dan Neraca; laporan lain belum | `frontend/src/features/finance/FinancialStatementsView.jsx:79` (`FinancialStatementsView`) · `backend/routers/gl.py:107` (`gl_account_ledger`) · `frontend/src/features/finance/JournalDetailModal.jsx:31` (`sourceMeta`) |
| 9 | Pola tautan antar-layar dan pembuka dokumen sudah ada | `frontend/src/features/finance/FinReportLink.jsx:16` (`FinReportLink`) · `frontend/src/hooks/useAppNavigation.js:72` (`openDocument`) |
| 10 | Kunci idempotensi dari layar dibuat satu hook | `frontend/src/hooks/useIntentKey.js:5` (`useIntentKey`) |

## Perubahan

### Data

Tidak ada koleksi atau field baru.

### Server

Tidak ada endpoint tulis baru: kedua form memanggil pintu yang sudah disatukan PK-19 (terima) dan PK-05 (bayar),
dengan rekening menurut PM-T3. Perubahan hanya pada **bacaan** yang ada:

| Endpoint (sudah ada) | Izin | Perubahan |
|---|---|---|
| `GET /api/customers/{customer_id}/360` | tetap `customer.view` + aturan kepemilikan | Bertambah `sections_allowed` (daftar bagian kartu yang izinnya dipegang pemanggil); angka kredit dan piutang yang sudah ada di jawaban dikosongkan bila izinnya tidak dipegang (K-18) |
| `GET /api/suppliers/{supplier_id}/360` | tetap `supplier.view` | Bertambah `payables`, `contra_bons`, `payments`, `landed_costs`, dan `sections_allowed`; tiap bagian keuangan — termasuk `bills` yang sudah ada — bernilai `null` bila izin sumbernya tidak dipegang |
| `GET /api/penalties`, `GET /api/finance-cases` | tetap | Parameter opsional baru `customer_id` |
| `GET /api/vendor-bills`, `GET /api/contra-bons` | tetap | Parameter opsional baru `supplier_id` |

Aturan bersama: PT dari sesi (`02` §3.4 N1); mode Semua PT mengembalikan angka per PT dengan label PT, tanpa dijumlah
lintas PT (N3); bagian diisi dengan memanggil fungsi layanan yang dipakai layar sumbernya, bukan kueri baru (D1).

| Bagian kartu | Sumber | Izin bagian |
|---|---|---|
| Kepala kartu pelanggan (eksposur, plafon, lewat jatuh tempo) | `GET /api/customers/{id}/balance` (CR-T2) dan profil kredit (CR-T1) | `payment_plan.view` atau `credit_profile.view` |
| Tagihan & Jadwal | `GET /api/customers/{id}/billing-schedule` (CR-T2) | `payment_plan.view` |
| Pembayaran | `GET /api/ar-receipts?customer_id`, `GET /api/ar-receipts/deposit`, `GET /api/store-credit/ledger` | `ar_receipt.view` |
| Denda & Kasus | `GET /api/penalties?customer_id`, `GET /api/finance-cases?customer_id` | `penalty.view` · `finance_case.view` |
| Tindak Lanjut | bagian tindak lanjut `…/360` | `order.view` |
| Rekening Koran | `GET /api/customers/{id}/statement` (CR-T5) | `credit_profile.view` atau `ar_receipt.view` |
| Kepala kartu pemasok dan bagian Tagihan · Kontrabon · Pembayaran | `…/suppliers/{id}/360` (`payables`, `bills`, `contra_bons`, `payments`) | `vendor_bill.view` · `contra_bon.view` |
| Retur · PO & Biaya Masuk | `…/suppliers/{id}/360` (`returns`, PO, `landed_costs`) | `purchase_return.view` · `purchase_order.view` · `landed_cost.view` |

Telusur memakai kontrak PK-43 apa adanya: `source_doc` pada `GET /api/gl/journal/{entry_id}`, `start` pada buku besar
akun, `start` dan `end` pada daftar jurnal. Unit ini tidak menambah endpoint telusur.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan izin baru. Tombol di layar memakai `can(perms, …)`: terima pembayaran `ar_receipt.create`; bayar
pemasok memakai izin bayar hasil PK-05 (di HEAD `vendor_bill.pay` dan `contra_bon.pay`).

### Layar

**A. Form "Terima pembayaran pelanggan"** — komponen yang diperluas: `ARReceiptModal`, dipindah menjadi
`frontend/src/features/finance/payments/ReceivePaymentModal.jsx` (berkas baru; berkas lama mengekspor ulang sampai
serah-terima b). Tanda tangan: `{ customerId?, customerName?, preselectOrderId?, bankLineId?, amountHint?, onClose,
onDone }`. Tanpa `customerId` form dibuka dengan langkah "Pilih pelanggan".

- Isian: "Pelanggan" · "Nominal diterima" · "Tanggal terima" · "Cara bayar" · "Rekening penerima" · "Pakai titipan" ·
  "Alokasi ke tagihan" (pilihan "Tertua dulu" · "Atur sendiri") · "Catatan". Banner "PT: {nama PT}".
- Tombol "Simpan kwitansi". Konfirmasi: "Catat penerimaan Rp {nominal} dari {pelanggan} ke {rekening} untuk {nama
  PT}?" dengan "Ya, simpan" dan "Batal". Mode Semua PT: tombol mati, petunjuk "Pilih satu PT untuk mencatat
  pembayaran."
- Kunci idempotensi dari `useIntentKey`; tombol mati selama menyimpan. Galat server tampil di dalam pop-up.

| Titik masuk | Tempat tombol "Terima pembayaran" | Isi awal |
|---|---|---|
| Beranda Keuangan › Perlu Tindakan | baris "Uang masuk perlu dicatat" | pelanggan, pesanan |
| Piutang › Saldo & Umur | baris pelanggan | pelanggan |
| Piutang › Penagihan & Penerimaan | baris daftar kerja | pelanggan |
| Kartu pelanggan | kepala kartu | pelanggan |
| Detail pesanan | panel bayar (menggantikan tombol simulasi pembayaran) | pelanggan, pesanan |
| Gerbang kirim | panel gerbang | pelanggan, pesanan |
| Kas & Bank › Rekonsiliasi | baris mutasi masuk belum cocok: "Catat sebagai kwitansi" | nominal, tanggal, rekening, `bankLineId` |
| HP sales | layar terima pembayaran | pelanggan |

**B. Form "Bayar pemasok"** — berkas baru `frontend/src/features/finance/payments/PaySupplierModal.jsx`, diturunkan
dari `contrabon/PayModal.jsx` (yang isiannya paling lengkap). Tanda tangan: `{ target: { type: "vendor_bill" |
"contra_bon", id }, bankLineId?, onClose, onPaid }`.

- Isian: "Pemasok" dan "Dokumen" (hanya-baca) · "Sisa hutang" (hanya-baca) · "Nominal dibayar" · "Tanggal bayar" ·
  "Cara bayar" · "Rekening sumber" · "Catatan". Selisih bayar memakai dialog selisih yang ada.
- Tombol "Bayar". Konfirmasi: "Bayar Rp {nominal} ke {pemasok} dari {rekening} untuk {nama PT}?" dengan "Ya, bayar"
  dan "Batal". Aturan PT, idempotensi, dan galat sama dengan form A.

| Titik masuk | Tempat tombol "Bayar" | Isi awal |
|---|---|---|
| Hutang › Tagihan | detail tagihan | tagihan |
| Hutang › Kontrabon | detail kontrabon | kontrabon |
| Kas & Bank › Rekonsiliasi | baris mutasi keluar belum cocok | dokumen pilihan, nominal, tanggal, rekening, `bankLineId` |
| Beranda Keuangan › Perlu Tindakan | baris "Hutang jatuh tempo" | tagihan atau kontrabon |
| Kartu pemasok | baris tagihan atau kontrabon | dokumen itu |
| Kas & Bank › Transaksi Kas | di form kas manual: tautan "Membayar tagihan pemasok? Pakai form Bayar pemasok" | — |

**C. Kartu pelanggan** — komponen yang diperluas: `Customer360Panel`, dibuka sebagai panel samping lewat pembuka
bersama `openCustomerCard(customerId)` di konteks navigasi aplikasi. Kepala: nama, PT, empat angka "Eksposur" ·
"Plafon" · "Lewat jatuh tempo" · "Titipan & saldo kredit", tombol "Terima pembayaran". Bagian (enam): "Tagihan &
Jadwal" · "Pembayaran" · "Denda & Kasus" · "Tindak Lanjut" · "Rekening Koran" · "Riwayat Lain" (pesanan, dokumen,
harga khusus, sample — isi tab lama, sebagai chip). Bagian di luar `sections_allowed` tidak ditampilkan. Titik masuk:
nama pelanggan di tab-tab Piutang, di Beranda Keuangan, di detail pesanan, dan daftar pelanggan CRM (komponen sama).

**D. Kartu pemasok** — komponen yang diperluas: `Supplier360Panel`, pembuka `openSupplierCard(supplierId)`. Kepala:
nama, PT, tiga angka "Saldo hutang" · "Jatuh tempo 7 hari" · "Uang muka ke pemasok". Bagian (enam): "Tagihan" ·
"Kontrabon" · "Pembayaran" · "Retur" · "PO & Biaya Masuk" · "Lainnya" (harga, dokumen, skor). Titik masuk: nama
pemasok di Hutang › Tagihan dan Kontrabon, di detail PO, dan layar Pemasok.

Keduanya: bagian dimuat saat dibuka; memuat "Memuat…"; galat "Bagian ini tidak bisa dimuat. Coba lagi." tanpa
mengosongkan bagian lain; kosong "Belum ada data."; daftar di dalam bagian berhalaman dengan jumlah total.

**E. Telusur di semua laporan** — mekanisme PK-43 (preset `{tab: "ledger", code, start, end, from}`, tombol kembali,
"Buka Dokumen Sumber") diperluas:

| Laporan | Yang bisa diklik | Tujuan |
|---|---|---|
| Buku Besar › Neraca Saldo | baris akun | buku besar akun itu sampai tanggal neraca saldo |
| Laporan › Arus Kas, Perubahan Ekuitas | baris yang membawa kode akun | buku besar akun itu pada rentang laporan |
| Laporan › Anggaran | angka realisasi per akun | buku besar akun itu pada tahun anggaran |
| Laporan › Konsolidasi | angka akun per PT | buku besar akun itu bila PT baris = PT aktif; selain itu petunjuk "Pindah ke {nama PT} untuk menelusuri angka ini." |
| Piutang › Saldo & Umur | nama pelanggan | kartu pelanggan |
| Hutang › Tagihan (ringkasan umur) | nama pemasok | kartu pemasok |

Baris ringkasan (total, laba kotor, laba bersih) dan baris tanpa kode akun tidak bisa diklik. Mode Semua PT: klik
angka meminta "Pilih satu PT untuk menelusuri angka ini."

## Uji penerimaan

Persiapan bersama: pelanggan **C** (`ent_ksc`, milik sales `sls`) bersisa tagihan 8.000.000 pada satu pesanan; pemasok
**S** dengan tagihan terposting 7.000.000 dan 3.000.000, yang kedua sudah dibayar 2.000.000; satu kwitansi C senilai
1.000.000 dengan jurnalnya; satu jurnal manual. Peran uji baku `02` §6.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | komponen | — | Render `ReceivePaymentModal` tanpa `customerId`; lalu dengan `preselectOrderId` | Pertama: langkah "Pilih pelanggan"; kedua: alokasi terisi untuk pesanan itu |
| U2 | komponen | Nominal 5.000.000, rekening dipilih | Klik "Simpan kwitansi" dua kali cepat, setujui konfirmasi | Konfirmasi memuat "Rp 5.000.000", nama pelanggan, rekening, PT; tepat satu `POST /ar-receipts` ber-`Idempotency-Key` |
| U3 | B | — | Kirim isi yang dihasilkan form A (5.000.000, tertua dulu) ke pintu kwitansi | Satu kwitansi; sisa tagihan C = 3.000.000 (8.000.000 − 5.000.000); rekening pada kwitansi = yang dipilih |
| U4 | B | — | Kirim isi form B untuk tagihan 7.000.000, lalu bentuk isi yang sama untuk satu kontrabon | Masing-masing satu kas keluar dengan rekening yang dipilih; tagihan lunas |
| U5 | komponen | Mode Semua PT | Render form A dan form B | Tombol simpan dan bayar mati dengan petunjuknya |
| U6 | komponen | 13 peran bawaan dengan izin dari fixture | Render tiap titik masuk pada dua tabel di atas | Tombol "Terima pembayaran" tampil hanya bagi pemegang `ar_receipt.create`; "Bayar" hanya bagi pemegang izin bayar; tidak ada tombol yang berujung 403 |
| U7 | statik (sesudah b) | — | Cari pemanggil `POST` kwitansi, pintu bayar pemasok, dan `simulate-payment` di `frontend/src` | Satu berkas, satu berkas, nol |
| U8 | B | Tanpa Acuan ber-`customer.view` saja | `GET /api/customers/{C}/360` | 200; profil terisi; `sections_allowed` kosong; tidak ada nominal piutang maupun plafon di jawaban |
| U9 | B | Sales lain (bukan pemilik C) | `…/360` | 403 (aturan kepemilikan yang ada tetap berlaku) |
| U10 | B | Akun ber-PT `ent_kanda` saja | `…/360` untuk C; `GET /api/ar-receipts?customer_id={C}` | Ditolak penjaga PT atau daftar kosong; tidak ada angka C |
| U11 | B | Admin, PT `ent_ksc` | `GET /api/ar-receipts?customer_id={C}`; `GET /api/penalties?customer_id={C}` | 1 kwitansi 1.000.000; daftar denda hanya milik C (pelanggan lain ber-denda tidak ikut) |
| U12 | B | Admin | `GET /api/suppliers/{S}/360` | `payables` saldo 8.000.000 (7.000.000 + 3.000.000 − 2.000.000); `payments` 1 baris 2.000.000 |
| U13 | B | Tanpa Acuan ber-`supplier.view` saja | `…/suppliers/{S}/360` | 200; `payables`, `bills`, `contra_bons`, `payments`, `landed_costs` bernilai `null`; `sections_allowed` tidak memuatnya |
| U14 | B | — | `GET /api/vendor-bills?supplier_id={S}`; lalu pemasok lain | 2 baris; 0 baris |
| U15 | komponen | 13 peran bawaan dengan izin dari fixture | Render kartu pelanggan dan kartu pemasok | Bagian yang tampil = bagian yang izinnya dipegang; tidak ada bagian yang memanggil endpoint tanpa izin |
| U16 | komponen | — | Klik baris akun di Neraca Saldo per 2026-02-28; klik angka realisasi akun di Anggaran 2026; klik angka PT lain di Konsolidasi | Preset `{tab: "ledger", code, end: "2026-02-28"}`; preset `start` 2026-01-01 dan `end` 2026-12-31; petunjuk "Pindah ke … untuk menelusuri angka ini." |
| U17 | penjaga | — | `verify_page_tabs.py`, `audit_create_modal.py` (INV-UI-05), `audit_i18n_id.py`, `roleReach.test.js` | Tidak lebih merah; kartu tidak tercatat sebagai tab tingkat ketiga |
| U18 | layar (uji jalan) | Data acuan; finance lalu manager | Terima pembayaran dari Beranda Keuangan, Piutang, detail pesanan, kartu pelanggan; bayar pemasok dari Hutang, Rekonsiliasi, kartu pemasok; telusuri satu angka Anggaran sampai dokumen sumbernya | Semua selesai tanpa membuka menu lain; laporan memuat tangkapan layar tiap titik masuk |

## Langkah kerja

**Serah-terima (a) — yang baru, pemanggil lama belum disentuh**

1. Tes U1–U5 dan U8–U16 (merah).
2. Perluasan dua endpoint 360 dan empat parameter saringan.
3. `ReceivePaymentModal` dan `PaySupplierModal`; pembuka kartu bersama; perluasan dua panel 360.
4. Telusur di laporan pada tabel E. Gate; laporan (a) dengan SHA.

**Serah-terima (b) — pengalihan dan penghapusan**

5. Alihkan tiap titik masuk pada dua tabel form (termasuk tombol "Catat Pembayaran" yang dipasang PK-43); tes U6.
6. Hapus form bayar lama di detail tagihan, kontrabon, dan mutasi bank; cabut tombol simulasi pembayaran dan
   `payInvoice` setelah pencarian pemakai (`00` §7 butir 3); tes U7.
7. Penjaga; uji jalan U18. Gate; laporan (b) dengan SHA dan satu contoh angka (`00` §9): kwitansi 5.000.000 → kas →
   jurnal → sisa piutang 3.000.000.

## Dokumen ikut berubah

`CODEBASE_MAP.md` (dua form, pembuka kartu, form yang dihapus); `docs/KN_16_END_TO_END_PROCESS_FLOWS.md` (alur terima
dan bayar); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("kartu pelanggan", "kartu pemasok", "dokumen sumber");
`memory/PRD.md`.

## Di luar lingkup

- Aturan alokasi, titipan, selisih bayar, dan rekening pada kwitansi → PK-19, PM-T3. Pintu bayar hutang → PK-05.
- Jadwal dan bayar massal (tab "Pembayaran" di Hutang): belum ada unitnya; dicatat di laporan.
- Bayar voucher biaya masuk barang dan bayar reimburse lewat form B: hanya bila PK-05 memasukkannya ke pintu yang sama.
- Telusur Laba-Rugi dan Neraca, tombol "Buka Dokumen Sumber", daftar periksa tutup buku → sudah di PK-43.
- Isi profil kredit, jadwal tagihan, rekening koran → CR-T1, CR-T2, CR-T5; unit ini hanya menampilkannya.

## Asumsi dan risiko

- `ASUMSI:` bagian E membutuhkan PK-43 `selesai` walau tidak tercantum sebagai prasyarat di indeks. Bila belum, pecah
  bagian E menjadi `MN-T3b` (`00` §8) dan selesaikan A–D lebih dulu.
- `ASUMSI:` kartu dibuka sebagai panel samping, bukan tab hub, sehingga enam bagiannya tidak melanggar larangan tab
  tingkat ketiga; penjaga INV-UI-14 (MN-T1) hanya memeriksa komponen yang dirender sebagai tab hub.
- `ASUMSI:` kartu tidak punya endpoint gabungan sendiri: ia memakai endpoint 360 yang ada ditambah endpoint per bagian,
  supaya aturan izin tiap bagian tetap satu tempat.
- `ASUMSI:` nama bagian kartu dan urutan isian form ditetapkan di sini; rancangan `01` §3 hanya menyebut isinya.
- `RISIKO:` serah-terima (b) menghapus empat form bayar yang dipakai harian. Tiap penghapusan satu commit; membatalkan
  = mengembalikan commit itu, karena form baru memanggil pintu yang sama.
- `RISIKO:` endpoint 360 pemasok hari ini mengembalikan tagihan tanpa memeriksa izin tagihan; sesudah unit ini peran
  ber-`supplier.view` saja tidak lagi melihat nominalnya. Itu sejalan dengan K-18; dicatat di laporan.
