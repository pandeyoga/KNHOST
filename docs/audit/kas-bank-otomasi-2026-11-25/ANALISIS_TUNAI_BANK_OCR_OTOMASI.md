# Analisis meja keuangan — tunai vs kas kecil, rekening ↔ bagan akun, jurnal otomatis dari OCR, detail barang, otomasi kerja berulang

**HEAD:** `db0a20f` (25 Nov 2026) · **Sifat:** hanya membaca kode dan dokumen. Aplikasi, tes, dan database tidak dijalankan;
tidak ada berkas repo yang diubah. Semua "skenario" di bawah adalah bacaan kode, bukan hasil uji jalan.

**Cara membaca.** Path `backend/...` dan `frontend/src/...` relatif ke akar repo. Temuan audit 13 Nov
(`docs/finance/AUDIT_KEUANGAN_2026-11-13.md`, dibaca di `cd6963a`) yang relevan dicek ulang di HEAD; statusnya ditulis
"masih berlaku", "sudah diperbaiki (unit …)", atau "sebagian". Keputusan pemilik dirujuk dengan nomor K-xx dari
`docs/blueprint/01_KEPUTUSAN.md`. Pertanyaan terbuka dari pelatihan 18 Nov memakai penomoran sendiri yang **bertabrakan**
dengan K-51…K-82 blueprint (mis. "K-55 pelatihan" ≠ K-55 blueprint) — ditulis "K-55 (pelatihan)".

---

## 0. Ringkasan

1. **Tunai dan kas kecil tercampur di satu akun.** Sistem hanya mengenal dua "jenis kas": `kas_kecil` → akun 1-1110 dan
   `kas_besar` → 1-1100 (`backend/services/cash_ledger.py:25,69-70`, `backend/services/gl_service.py:237-238`). Setiap
   rekening ber-`account_type: cash` otomatis `kas_kecil` (`backend/services/bank_service.py:22-27`) dan form rekening
   tidak menawarkan pilihan lain (`frontend/src/features/finance/BankAccountForm.jsx:40-99,147-148`). Jadi **"Kas Toko"
   (tunai dari pelanggan) dan dana kas kecil (pencairan PD, sisa LPJ, bayar reimburse) duduk di akun yang sama 1-1110**.
   Tidak ada konsep imprest (dana tetap + isi ulang), tidak ada batas saldo, tidak ada opname kas, tidak ada akun selisih
   kas. "Isi ulang kas kecil" hanya kategori teks "Transfer / Top-up" pada kas manual.
2. **Rekening tidak punya akun buku besar sendiri.** Semua rekening bank satu PT → satu kode (1-1100 atau hasil
   Pemetaan Akun per PT); semua rekening tunai → 1-1110. Saldo per rekening hanya ada di buku kas
   (`cash_transactions` + saldo awal), bukan di buku besar. Pemindahan antar rekening sendiri **tidak punya dokumen**:
   pilihannya dua kas manual terpisah berkategori "transfer" (lewat 1-1150) atau aksi "pindah-buku" di Kasus Keuangan.
   Antar-PT sudah punya jalur resmi (pinjaman, pelunasan, tagihan antar-PT) dengan kas kembar + jurnal kembar. Biaya
   transfer tidak tertangani di jalur mana pun.
3. **OCR sudah ada, tetapi hanya untuk surat jalan pemasok di Barang Masuk** (OpenAI Responses API + skema JSON ketat,
   `backend/services/ocr_openai_client.py:52-108`). Tidak ada OCR nota/struk/faktur/rekening koran PDF, tidak ada usulan
   akun, dan validasi akun hanya "ada · aktif · bukan induk · bukan akun kontrol". Pemilihan akun kas manual memakai
   pencocokan **substring kata kategori** yang ditulis mati (`gl_service.py:204-221`) — kategori "Pembelian" langsung
   mendebit Persediaan 1-1300 (akun kontrol) tanpa roll.
4. **Detail barang:** item barang hanya bisa dilihat di layar dokumennya sendiri (Pesanan → `OrderDetailPanel`, Tagihan
   Pemasok → `VendorBillDetailPanel`, PO di kartu pemasok). Layar Piutang, Penagihan, Kwitansi, Kontrabon, Hutang per
   Pemasok, Faktur Keluaran, dan Perlu Tindakan **tidak** membuka rincian barang di tempat; nomor dokumen membuka Jejak
   Dokumen (graf relasi tanpa baris barang) atau pindah layar, dan beberapa nomor tidak bisa diklik sama sekali.
5. **Otomasi:** jurnal berulang/templat, tagihan biaya tanpa PO, kwitansi otomatis dari mutasi bank, aturan biaya bank
   otomatis, bayar massal lintas pemasok, isi ulang kas kecil, opname kas, dan pengiriman pengingat ke pelanggan **belum
   ada**. Yang sudah ada dan bisa dipakai ulang: pencocokan bank otomatis (tiga pita + aturan belajar), kode bayar,
   usulan jurnal dua-orang (`journal_proposals`), kartu tindakan asisten, penyusutan sekali klik per periode, draf faktur
   pajak otomatis, denda otomatis, jurnal antar-PT otomatis, penjadwal.

---

## 1. Pembayaran tunai vs petty cash (kas kecil) — prioritas pemilik

### 1.1 Apa yang ada: akun, rekening, dan dua mesin

| Unsur | Isi di HEAD | Bukti |
|---|---|---|
| Akun kas di bagan akun bawaan | 1-1100 "Kas Besar / Bank", 1-1110 "Kas Kecil", 1-1150 "Kas & Bank Transit", 1-1280 "Piutang Titipan Karyawan", 1-1400 "Uang Muka & Biaya Dibayar Dimuka", 2-1650 "Hutang Reimburse", 2-1950 "Titipan Dana Belum Teridentifikasi" | `backend/services/gl_service.py:61-63,68,75,97,103` |
| Jenis kas | Hanya `kas_kecil` (1-1110) dan `kas_besar` (1-1100). Jenis rekening `cash` → `kas_kecil`, `bank` → `kas_besar` | `backend/services/bank_service.py:18-27`; `backend/services/cash_ledger.py:25,69-70` |
| Akun dari jenis kas | `_cash_account`: kas_kecil → 1-1110, lainnya → 1-1100; Pemetaan Akun (`kas_bank.kas_kecil`, `kas_bank.kas_besar`) bisa mengganti kode **per PT**, bukan per rekening | `gl_service.py:237-238`; `backend/services/gl_mapping_registry.py:48-53`; `backend/services/gl_mapping_service.py:51-70` |
| Satu pembuat kas | Semua kas lahir lewat `create_cash`: periksa nominal, PT, rekening milik PT & aktif, periode → sisip id tetap → jurnal tahan-gagal | `backend/services/cash_ledger.py:147-240` (PK-20) |
| Rekening per PT (data acuan) | "BCA Operasional {PT}" (bank) dan "Kas Toko {PT}" (cash → 1-1110) | `backend/scripts/seed_demo_lengkap_kn.py:285-286`; `docs/pelatihan/2026-11-18_keuangan/KONTEKS_CHAT.md:165` |
| Mesin "Kas Kecil" (menu) | Bukan dana kas kecil, melainkan **Pengajuan Dana (PD) + Pertanggungjawaban (LPJ) + Hutang reimburse** | `backend/services/cash_advance_service.py:1-21`; `frontend/src/config/hubTabs.js:176-178` |
| Mesin "Titipan Sales" | Tunai yang diterima sales dicatat sebagai titipan sampai disetor (PM-T4) | `backend/services/cash_holding_service.py:1-21` |

Data rekening nyata per PT tidak bisa dibaca (database tidak dijalankan); daftar di atas dari skrip data acuan.

### 1.2 Peta setiap alur tunai

Kolom "Jurnal" memakai akun bawaan (sebelum Pemetaan Akun per PT). "Kas" = akun rekening yang dipilih: 1-1110 bila
rekening tunai, 1-1100 bila rekening bank.

| # | Alur | Siapa (izin bawaan) | Layar | Jurnal | Dihitung / disetor / direkonsiliasi |
|---|---|---|---|---|---|
| A1 | **Kwitansi tunai oleh pemegang `cash.create`** (Finance/Manajer/Admin) | `ar_receipt.create` + `cash.create` (`backend/permissions_config.py:388,396`; Finance = Manajer sejak K-FIN-01, commit `790464b`) | Piutang › Penagihan & Penerimaan / Perlu Tindakan → `ReceivePaymentModal` | Dr Kas (rekening tunai → 1-1110) / Cr 1-1200 Piutang untuk bagian yang sudah dikirim, Cr 2-1400 untuk uang muka & kelebihan (`gl_service.py:3344-3386, 3465-3480`) | Rekening tunai = rekening penerima cara bayar "cash" (`needs_account: "kas"`, `backend/services/payment_method_service.py:31-33`; `backend/services/ar_receipt_service.py:98-137`). **Tidak ada hitung fisik, tidak ada rekonsiliasi** (kwitansi tunai tidak pernah masuk daftar "terverifikasi bank", `ar_receipt_service.py:968-985`) |
| A2 | **Kwitansi tunai oleh sales, mode `kas_langsung` (bawaan)** | Sales: `ar_receipt.create` tanpa `cash.create` (`permissions_config.py:145`) | HP sales / `ReceivePaymentModal` | Sama dengan A1 — kas rekening "Kas Toko" langsung naik padahal uang masih di saku sales | `pembayaran.sales_terima_tunai` bawaan `kas_langsung` (`backend/config_catalog_payment.py:147-159`; `cash_holding_service.py:95-106`). Pemilik menjawab "saat ini sales tidak menerima tunai" (`docs/blueprint/STATUS.md`, Jawaban pemilik no. 2) tetapi sistem tetap mengizinkan |
| A3 | **Titipan tunai sales (PM-T4)** bila PT memilih `titipan` | Sales `cash_holding.create`; penerima setoran `cash_holding.approve` = Admin/Manajer/Finance, bukan pemegang titipan (`permissions_config.py:1009-1013`; `cash_holding_service.py:351-352`) | HP: kartu "Titipan Saya" + Setor (`frontend/src/features/sales/mobile/MobileCashHoldingCard.jsx:1-9`); Keuangan › Kas & Bank › Titipan Sales (`frontend/src/features/finance/cashholding/CashHoldingsView.jsx:1-12`) | Kwitansi: Dr 1-1280 / Cr 1-1200 atau 2-1400 (`gl_service.py:3389-3415`). Setoran diterima: Dr Kas/Bank / Cr 1-1280 (`cash_holding_service.py:401-409`) | Batas per orang & tenggat setor bawaan 0 = tanpa batas (`config_catalog_payment.py:161-179`); tenggat **hanya menandai** (`cash_holding_service.py:116-121`). Penerima menerima nominal setoran **apa adanya** — tidak ada isian "jumlah dihitung", tidak ada selisih kurang/lebih (`terima_setoran` hanya menerima `account_id`, `cash_holding_service.py:343-409`). Tanggal kas = saat diterima (`:404`) |
| A4 | **Uang pelanggan di rekening pribadi karyawan** | `finance_case.resolve` | Piutang › Kasus (playbook) | Dr 1-1280 / Cr 1-1200, lalu setoran Dr Kas / Cr 1-1280 (`backend/services/finance_case_playbooks.py:101-115`; `backend/services/finance_case_actions.py:830`) | Memakai akun 1-1280 yang sama dengan A3 (risiko tercatat di `docs/blueprint/unit/PM-T4.md` "Asumsi dan risiko") |
| A5 | **Penjualan tunai di POS** | Kasir/Sales membuat pesanan | POS › `CheckoutDrawer` | Tidak ada kas di POS: pesanan menyimpan cara bayar + rekening tujuan (`frontend/src/features/pos/CheckoutDrawer.jsx:49-51,239-240`); uangnya dicatat kemudian lewat A1/A2 | Pesanan tunai yang sudah dikirim tetapi belum berkwitansi muncul di Perlu Tindakan sebagai `cash_unrecorded` (`backend/services/work_desk_service.py:454-470`). Pesanan bertermin tunai **tanpa surat jalan** dikeluarkan dari daftar tagihan terbuka dan alokasi (`ar_receipt_service.py:470-478`; `backend/services/ar_allocation_service.py:113-121`) — lihat celah C10 |
| A6 | **Jalur lama: pesanan tunai tanpa surat jalan** | Sistem | — | `post_sales_order`: **Dr 1-1100** / Cr Pendapatan + PPN, tanpa transaksi kas dan tanpa rekening (`gl_service.py:1562-1606`, `:1581-1582`) | Tidak masuk saldo rekening mana pun. Hanya terpicu untuk pesanan "terkirim" tanpa surat jalan (`gl_service.py:1180-1200`); sejak K-75 semua barang keluar wajib surat jalan, jadi kemungkinan tinggal data lama — **perlu dicek di data (H3)** |
| B1 | **Bayar tagihan pemasok / kontrabon tunai** | `vendor_bill.pay` / `contra_bon.pay` (Finance, Manajer — `permissions_config.py:833`) | Hutang › Tagihan, Kontrabon, Hutang per Pemasok → `PaySupplierModal` | Dr 2-1100 / Cr Kas; kelebihan bayar Dr **1-1400** (`gl_service.py:3289-3322`) | Rekening sumber = rekening aktif mana pun milik PT dokumen, **tanpa cek peruntukan "pembayaran pemasok"** dan tanpa cek cara bayar ↔ jenis rekening (`backend/services/ap_payment_service.py:90-110`) |
| B2 | **Biaya operasional tunai (kas manual)** | `cash.create` (Finance/Manajer/Admin) | Kas & Bank › Transaksi Kas (`frontend/src/features/purchasing/CashManagementView.jsx`) | Lawan akun dari **kata kategori**: operasional → 6-4000, pembelian → **1-1300 Persediaan**, gaji → 6-1000, transfer → 1-1150 (`gl_service.py:204-214, 3313-3318`) | Tanpa persetujuan, tanpa batas nominal, tanpa lampiran; hanya cek anggaran (`backend/routers/cash.py:186-196`) |
| B3 | **Pengajuan Dana (PD) → pencairan** | Buat: `cash_advance.create` (Sales, Admin Sales, Finance…; `permissions_config.py:147,406`); setuju: jenjang Aturan Persetujuan (bawaan Atasan → Pimpinan → Keuangan, `backend/services/approval_policy_service.py:127-128`); cairkan: `cash_advance.disburse` Admin/Manajer/Finance (`permissions_config.py:833-834,955-956`) | Kas & Bank › Kas Kecil (`frontend/src/features/pettycash/PettyCashView.jsx`) | Dr 1-1400 / Cr Kas; bawaan rekening **kas kecil** (`cash_advance_service.py:325-377`, `:329`) | Kontrol dua orang `kontrol.cairkan_uang_muka` (bawaan 1 orang, K-17; `cash_advance_service.py:331-337`). **Tidak ada** batas PD terbuka per karyawan, tenggat LPJ, atau larangan PD baru sebelum LPJ lama selesai |
| B4 | **LPJ (pertanggungjawaban)** | Buat/ajukan: pemohon; setujui: `cash_settlement.approve` + Aturan Persetujuan (`backend/routers/cash_advances.py:220-226`) | Kas Kecil › Pertanggungjawaban (`SettlementDetail.jsx:219`) | Dr beban per kategori (peta kategori → akun per PT) / Cr 1-1400; kelebihan Cr 2-1650 (`cash_advance_service.py:706-710, 737-790`) | Lampiran ada tetapi wajib hanya bila `finance.lpj_wajib_lampiran` dinyalakan (bawaan mati, `cash_advance_service.py:407-408,588-589`). Tanpa pemasok, tanpa PPN per nota (`backend/schemas_cash_advance.py:72-76`; dikecualikan PK-24) |
| B5 | **Pengembalian sisa uang muka** | `cash_settlement.pay` | Rincian LPJ | Dr Kas / Cr 1-1400 (`cash_advance_service.py:894-965`) | Bawaan rekening kas kecil |
| B6 | **Bayar reimburse (LPJ > uang muka)** | `cash_settlement.pay` | Kas Kecil › Hutang reimburse | Dr 2-1650 / Cr Kas (`cash_advance_service.py:840-890`) | — |
| C1 | **Uang masuk tak dikenal di bank** | `cash.create` | Rekonsiliasi › Titipan | Dr Bank / Cr 2-1950; dialokasikan: Dr 2-1950 / Cr 1-1200 (`backend/services/bank_recon_service.py:1524,1588-1596`) | Dipindai otomatis tiap hari menjadi Kasus bila menganggur (`backend/services/scheduler_service.py:168-171`) |
| C2 | **Pindah dana kas ↔ bank (setor tunai ke bank, isi kas kecil)** | `cash.create` | Transaksi Kas, kategori "Transfer / Top-up" (`CashManagementView.jsx:44-51`), dua kali | Keluar: Dr 1-1150 / Cr Kas asal; masuk: Dr Kas tujuan / Cr 1-1150 (`gl_service.py:211-216`) | Dua transaksi lepas, tidak saling menaut, tanpa cek pasangan — lihat §2.3 |

### 1.3 Status temuan audit 13 Nov yang menyangkut kas (dicek di HEAD)

| Temuan | Status di HEAD | Bukti HEAD |
|---|---|---|
| SL-07 kas manual menerima `ref_type`, entitas, rekening dari klien | **Sudah diperbaiki** (PK-09, PK-20) | `backend/routers/cash.py:171-181` |
| SL-11 kas tanpa rekening | **Sudah diperbaiki untuk kas baru** (PK-20); kas lama tanpa rekening tetap dijelaskan sebagai "belum tertaut" | `cash_ledger.py:95-121`; `bank_service.py:197-221` |
| UX-01 / UX-02 klik ganda kas | **Sudah diperbaiki** (PK-12): kunci idempotensi = id kas | `routers/cash.py:200` |
| FX-04 bayar denda langsung Dr Kas | **Sudah diperbaiki** (PK-08): fungsi lama ditandai usang | `gl_service.py:2483-2490` |
| FY-03 perolehan aset Cr kas tanpa transaksi kas | **Sudah diperbaiki** (PK-23) | `backend/services/fixed_asset_service.py:401` (lewat `create_cash`) |
| IC-08 settlement antar-PT tanpa transaksi kas | **Sudah diperbaiki** (PK-06, `twin_cash`) | `backend/services/interco_money_service.py:76-112`; `backend/services/interco_service.py:1382,1569` |
| SL-09 sisa uang muka tanpa alur kembali | **Sudah diperbaiki** (PK-24) | `cash_advance_service.py:894` |
| FY-13 peta kategori LPJ abai lapisan PT | **Sudah diperbaiki** (PK-24) | `cash_advance_service.py:140-144` |
| FY-14 LPJ tanpa bukti/vendor/PPN | **Sebagian**: lampiran + kunci isi; vendor & PPN tidak | `cash_advance_service.py:407-427`; `docs/blueprint/unit/PK-24.md` "Di luar lingkup" |
| "Tiga wadah uang dipegang orang" (1-1400, 1-1280, 2-1650) | **Masih berlaku**; bahkan 1-1400 juga menampung uang muka **pemasok** | `gl_service.py:3304-3306` (ap_advance → 1-1400); `gl_mapping_registry.py:63-64`; `docs/blueprint/unit/PK-24.md` "Di luar lingkup" |
| "Tiga peta beban tunai" (kategori LPJ, kata kunci kas manual, akun kampanye); "gaji" bertabrakan dengan penggajian | **Masih berlaku** | `gl_service.py:204-221` vs `cash_advance_service.py:75-85` |
| RP-06 akun kas di Arus Kas ditulis mati | **Masih berlaku** | `backend/services/cash_flow_service.py:33` |

### 1.4 Tumpang-tindih dan celah

Tingkat: **Tinggi** = buku bisa salah atau uang bisa tidak terlacak pada kondisi wajar · **Sedang** = kontrol/kejelasan ·
**Rendah** = kerapian.

| ID | Tingkat | Temuan | Bukti | Akibat |
|---|---|---|---|---|
| C1 | Tinggi | **Kas toko dan kas kecil satu akun.** Rekening tunai selalu `kas_kecil` → 1-1110; form rekening tidak punya pilihan jenis kas; layar Transaksi Kas menamai pilihannya "Kas Kecil (tunai)" vs "Kas Besar / Bank (transfer)" | `bank_service.py:22-27`; `BankAccountForm.jsx:147-148`; `CashManagementView.jsx:331-332` | Uang pelanggan tunai, dana operasional kecil, pencairan PD, sisa LPJ, refund retur tunai bercampur di satu saldo. Tidak bisa dijawab "berapa uang kasir hari ini" vs "berapa dana kas kecil" kecuali PT membuat dua rekening tunai — itu pun di buku besar tetap satu akun |
| C2 | Tinggi | **Sales bisa mencatat tunai sebagai kas langsung.** Bawaan `kas_langsung`; pemilik bilang sales tidak menerima tunai, tetapi tidak ada PT yang disetel `dilarang` atau `titipan` | `config_catalog_payment.py:147-159`; `cash_holding_service.py:95-106`; `STATUS.md` Jawaban pemilik no. 2 | Saldo "Kas Toko" naik sementara uang di tangan sales — kas fisik tidak cocok dengan buku tanpa ada yang tahu siapa memegangnya |
| C3 | Tinggi | **Tidak ada opname kas dan tidak ada akun selisih kas.** Tidak ada dokumen hitung kas, pecahan, berita acara, atau jurnal kurang/lebih kas; daftar periksa tutup buku tidak memeriksa kas tunai | `grep` "opname kas/hitung kas/cash count" kosong; bagan akun tanpa akun selisih kas (`gl_service.py:57-150`); `backend/services/closing_checklist.py:99-163` (butir: suspense, posting gagal, neraca saldo, stok, mutasi bank) | Rekening tunai **tidak pernah direkonsiliasi**: rekonsiliasi hanya untuk mutasi bank yang diimpor |
| C4 | Tinggi | **Tidak ada imprest / isi ulang / batas kas kecil.** "Top-up" hanya kategori teks; tidak ada saldo tetap, batas, usulan isi ulang dari LPJ yang disetujui, atau penolakan saldo negatif | `CashManagementView.jsx:44-51`; `cash_ledger.py:147-240` (tidak ada cek saldo cukup) | Kas kecil bisa minus di buku; isi ulang yang dicatat sebelah (hanya "masuk") meninggalkan saldo di 1-1150. Data acuan sendiri berisi "Top-up kas kecil" masuk tanpa pasangan keluar (`backend/bootstrap.py:1417-1426`) |
| C5 | Tinggi | **Kas manual "Pembelian" mendebit Persediaan 1-1300** (akun kontrol) tanpa roll; "Gaji" mendebit 6-1000 padahal penggajian sudah membebankan gaji dan membayar Hutang Gaji; "Setoran Modal" arah keluar jatuh ke beban 6-4000; "Operasional"/"Lain-lain" arah masuk jatuh ke Suspense 1-9999 | `gl_service.py:204-221, 3313-3318, 3481-3492`; penjaga akun kontrol hanya untuk jurnal manual (`gl_service.py:607-611`) | Persediaan buku besar ≠ buku roll; beban gaji dobel; Suspense memblokir tutup buku (`closing_checklist.py:99-105`) |
| C6 | Tinggi | **Jurnal manual bebas memakai akun kas.** Kas/bank bukan akun kontrol | `gl_mapping_registry.py:30-35` (hanya piutang, hutang, persediaan, antar-PT); `gl_service.py:842-870` | Saldo buku besar kas ≠ Σ saldo rekening tanpa jejak di rekening mana pun. Layar sendiri mengakuinya: "Sisa selisih … berasal dari jurnal kas manual" (`frontend/src/features/finance/BankAccountsView.jsx:139-143`) |
| C7 | Sedang | **Tiga arti "uang dipegang orang" dan empat arti "titipan".** 1-1400 = uang muka karyawan **dan** uang muka pemasok **dan** biaya dibayar dimuka; 1-1280 = titipan tunai sales **dan** kasus rekening pribadi karyawan; "titipan" = titipan pelanggan 2-1400, titipan dana bank 2-1950, titipan tunai sales 1-1280, cara bayar "deposit" beralias "titipan" | `gl_service.py:3304-3311`; `gl_mapping_registry.py:63-67`; `payment_method_service.py:45-47`; `docs/blueprint/unit/PM-T4.md` risiko | Saldo akun tidak bisa dicocokkan dengan satu daftar; staf salah pilih menu |
| C8 | Sedang | **Kas manual tanpa persetujuan, batas, atau lampiran.** Satu orang `cash.create` bisa mengeluarkan nominal berapa pun; keluarga `kontrol.*` tidak punya aksi kas manual (hanya kartu asisten `asisten_uang_keluar`) | `routers/cash.py:153-224`; `backend/config_catalog_kontrol.py:101-144` | Pengeluaran tunai terbesar risikonya justru jalur tanpa kontrol |
| C9 | Sedang | **PD tanpa batas terbuka per karyawan dan tanpa tenggat LPJ** | `cash_advance_service.py:164-212, 325-351` | Uang muka lama menggantung di 1-1400 tanpa peringatan |
| C10 | Sedang (perlu uji jalan) | Pesanan bertermin tunai **sebelum ada surat jalan** tidak bisa menerima kwitansi (dikeluarkan dari daftar terbuka dan ditolak alokasi). Bila PT menyalakan `finance.tahan_kirim_tunai` (bayar dulu), urutan "bayar dulu baru kirim" bisa macet atau dipaksa lewat titipan | `ar_receipt_service.py:470-478`; `ar_allocation_service.py:113-121`; `backend/services/dispatch_payment_gate.py:50-56` | Kasir menerima uang di loket tetapi tidak bisa membukukannya ke pesanannya |
| C11 | Sedang | Bayar pemasok dari rekening mana pun milik PT: tidak memeriksa peruntukan "pembayaran pemasok" (PM-T1) maupun "cara bayar transfer dari rekening tunai" | `ap_payment_service.py:90-110` vs peruntukan yang hanya dipakai penerimaan (`backend/services/bank_account_change_service.py:294-300`) dan gaji (`backend/services/hr_payroll_pay.py:89`) | Rencana `07` §A3.9 (rekening sumber ber-peruntukan) belum utuh |
| C12 | Sedang | Setoran titipan diterima sebesar nominal ajuan; selisih hitung hanya bisa "Tolak" lalu ajukan ulang | `cash_holding_service.py:343-409` | Kekurangan setoran tidak tercatat sebagai piutang karyawan/selisih |
| C13 | Rendah | Pemilih akun kas untuk refund retur menawarkan semua kode `1-11xx` termasuk 1-1150 Transit; rekening ditentukan dari jenis kas kode itu, jurnal memakai kode itu | `backend/routers/gl.py:58-70`; `backend/services/return_service.py:1748,1819-1821` | Refund bisa mengkredit Transit sementara buku rekening bank turun |
| C14 | Rendah | Daftar Transaksi Kas tidak menampilkan rekening, tidak menaut ke dokumen sumber maupun jurnal | `CashManagementView.jsx:395-425` | Menelusuri kas harus lewat Jejak Dokumen |

### 1.5 Yang perlu diputuskan pemilik (tunai)

1. **Pisahkan "kas toko/kasir" dari "kas kecil"?** Usulan: jenis rekening tunai dipilih eksplisit (kasir · kas kecil ·
   brankas) dengan akun buku besar sendiri (terkait §2, PM-T1.md:215 "belum ada unitnya").
2. **Kas kecil model imprest?** Dana tetap per PT/lokasi + batas + isi ulang sebesar LPJ yang disetujui (satu dokumen
   pindah-buku), atau tetap model PD/LPJ saja.
3. **Opname kas:** seberapa sering (harian kasir, mingguan kas kecil), siapa menghitung, siapa menyetujui selisih, akun
   selisih kas (beban/pendapatan lain atau piutang karyawan).
4. **`pembayaran.sales_terima_tunai` per PT** (K-36, titik henti H5, sudah di "Menunggu pemilik"): `dilarang` atau
   `titipan` + batas + tenggat. Saran: `dilarang` untuk PT yang memang tidak menerima tunai di lapangan.
5. **Kas manual:** kategori "Pembelian" dan "Gaji" dihapus/dialihkan (barang lewat PO/tagihan, gaji lewat penggajian)?
   Kas manual keluar di atas nominal tertentu butuh orang kedua (aksi baru di `kontrol.*`, pola K-04/K-11)?
6. **PD:** batas PD terbuka per karyawan dan tenggat LPJ (hari).
7. Pisahkan akun uang muka pemasok dari uang muka karyawan (1-1400) — butuh pemetaan akun baru.

---

## 2. Rekening bank ↔ bagan akun (COA) dan transfer antar rekening

### 2.1 Bagaimana rekening tertaut ke akun buku besar

- **Tidak ada field akun di rekening.** Skema rekening: nama, jenis (`bank`/`cash`), `cash_type`, bank, nomor, PT,
  saldo awal, atas nama, peruntukan, cara bayar, bawaan penerimaan, tampil di dokumen — tanpa kode akun
  (`backend/schemas_finance.py:9-26`). Kaitan ke buku besar **diturunkan dari jenis kas**:
  `periksa_rekening` → `cash_type` → `_cash_account` → 1-1100/1-1110 (`cash_ledger.py:95-121`; `gl_service.py:237-238`).
- **Beberapa rekening berbagi satu akun.** Semua rekening bank satu PT memakai satu kode; semua rekening tunai satu kode.
  Pemetaan Akun bisa mengganti kode **per PT** (`gl_mapping_service.py:36-48`), tidak per rekening. Unit PK-20 menulis
  terang: "Akun buku besar per rekening (hari ini hanya 1-1100 dan 1-1110) — tidak diubah"
  (`docs/blueprint/unit/PK-20.md` "Di luar lingkup"); PM-T1: "Satu akun buku besar per rekening (`07` §A3.2) … belum ada
  unitnya" (`docs/blueprint/unit/PM-T1.md:215`). Rancangan pemilik sudah memuatnya: `07_PAJAK_DAN_PEMBAYARAN.md:81`.
- **Saldo per rekening hanya di buku kas**: saldo awal + Σ masuk − Σ keluar transaksi kas tidak batal
  (`bank_service.py:139-177`). Angka utama "Kas & Bank" = saldo buku besar akun kas (`bank_service.py:224-243`); selisih
  terhadap Σ rekening dijelaskan sebagian oleh "transaksi belum tertaut" (`BankAccountsView.jsx:121-143`).
- **Bagan akun per PT:** satu templat global (`entity_id: None`) di-seed `seed_default_coa` (`gl_service.py:245-276`),
  dipanggil saat PT dibuat (`backend/services/entity_provisioning_service.py:212,273-274`). PT bisa menambah akun sendiri
  atau menimpa nama/status (`gl_service.py:347-388`; `backend/routers/gl.py:74-87`, izin `accounting.manage`). Akun
  khusus PT tidak terlihat dari PT lain (`gl_service.py:636-650`) — jadi jurnal tidak bisa memakai akun PT lain.
- **Yang diisi pengguna saat menambah rekening** (`BankAccountForm.jsx:40-99`): nama, jenis (bank/tunai), bank & nomor
  (bank), atas nama, saldo awal, peruntukan, cara bayar dilayani, bawaan penerimaan, tampil di dokumen, alasan (bila
  butuh orang kedua, `kontrol.ubah_rekening`). **Tidak ada pilihan akun buku besar dan tidak ada pilihan jenis kas.**
  Saldo awal langsung dijurnal Dr Kas/Bank / Cr 3-2900 bertanggal hari ini (`bank_service.py:296-325`).

### 2.2 Risiko ketidakcocokan rekening ↔ bagan akun

| ID | Tingkat | Risiko | Bukti |
|---|---|---|---|
| R1 | Tinggi | Laporan kas membaca kode tetap 1-1100/1-1110; bila `kas_bank.kas_besar`/`kas_kecil` dipetakan ke kode lain di sebuah PT, Arus Kas dan angka "Kas & Bank (buku besar)" tidak lagi memuat kas PT itu | `cash_flow_service.py:33`; `bank_service.py:229-238` vs `gl_mapping_service.py:51-70` |
| R2 | Tinggi | Jurnal manual ke akun kas mengubah buku besar tanpa mengubah rekening mana pun (C6) | `gl_mapping_registry.py:30-35` |
| R3 | Sedang | Saldo awal dijurnal menurut `account_type` (`cash` → 1-1110), tetapi mutasi menurut `cash_type`. API menerima `cash_type` eksplisit, dan `backfill_cash_type` mengisi `cash_type` dari mayoritas riwayat → rekening tunai bisa ber-`kas_besar`: saldo awal di 1-1110, mutasinya di 1-1100 | `bank_service.py:30-46, 287-290, 317` |
| R4 | Sedang | Akun yang dibuat staf (mis. "1-1101 Bank BCA") tidak bisa ditautkan ke rekening; jurnal otomatis tidak akan pernah memakainya kecuali lewat Pemetaan Akun per PT (dan itu berlaku untuk **semua** bank PT tersebut) | `schemas_finance.py:9-26`; `gl_mapping_registry.py:48-49` |
| R5 | Rendah | Refund retur memilih kode akun (bukan rekening) dari daftar `1-11xx` (C13) | `routers/gl.py:58-70` |

### 2.3 Transfer antar rekening sendiri

**Satu PT — tidak ada dokumen transfer.** Tiga cara yang ada hari ini:

| Cara | Layar & izin | Jurnal | Biaya transfer | Celah |
|---|---|---|---|---|
| Dua kas manual kategori "Transfer / Top-up" (keluar di rekening A, masuk di rekening B) | Kas & Bank › Transaksi Kas; `cash.create` | Keluar Dr 1-1150 / Cr Kas A; masuk Dr Kas B / Cr 1-1150 (`gl_service.py:211-216`) | Tidak ada; harus kas manual ketiga (kategori bebas) atau "Bukukan biaya" di Rekonsiliasi (`bank_recon_service.py:1321-1345`) | Dua dokumen lepas, dua kunci idempotensi; tidak ada cek pasangan; tidak ada butir tutup buku "1-1150 = 0" (`closing_checklist.py` tidak memuatnya; satu-satunya pemakai 1-1150 = kas manual & kasus). Salah pilih kategori ("Operasional") → beban palsu; satu sisi lupa → saldo 1-1150 menggantung dan saldo satu rekening salah |
| Kasus Keuangan, playbook "Pelanggan salah transfer ke rekening KN yang lain" → aksi `pindah_buku` | Piutang › Kasus; `finance_case.resolve` | 2 kas + 2 jurnal lewat 1-1150, tertaut ke kasus (`finance_case_actions.py:350-374, 803-827`; `finance_case_playbooks.py:89-99`) | Tidak ada | Jalur ini satu-satunya yang menjamin pasangan, tetapi dimaksudkan untuk salah-transfer pelanggan; memakai kasus untuk setoran harian tidak wajar |
| Jurnal manual Dr 1-1100 / Cr 1-1110 | Akuntansi › Jurnal | — | — | Tidak menyentuh rekening (R2) |

Rekonsiliasi bank tidak punya aksi "ini pindah-buku" untuk baris mutasi; baris boleh "Abaikan" dengan catatan opsional
(`bank_recon_service.py:1288-1298`, izin `cash.create`), sehingga transfer keluar bisa hilang dari buku tanpa jejak.

**Antar-PT — ada, lewat dokumen antar-PT (bukan "transfer" polos):**

| Jalur | Layar & izin | Jurnal | Biaya |
|---|---|---|---|
| Pinjaman antar-PT `ICL-` (cairkan, angsur) | Keuangan › Antar-PT; buat `interco.create`, cairkan `interco.approve`, angsur `interco.settle` (`backend/routers/interco_loans.py:51-120`) | Pemberi Dr 1-1250 / Cr Kas; penerima Dr Kas / Cr 2-1250; kas kembar + jurnal kembar (`backend/services/interco_loan_service.py:1-22, 229-284`) | Tidak ada |
| Pelunasan dagang antar-PT (transfer/netting/refund) | Antar-PT › Settlement | Pembayar Dr 2-1250 / Cr Kas; penerima Dr Kas / Cr 1-1250 (`interco_service.py:1746-1779`) | Tidak ada |
| Tagihan insentif antar-PT, bayar pindah aset | Antar-PT | Pola sama (`backend/services/interco_charge_service.py:295-306`; `backend/services/fixed_asset_transfer_service.py:297-301`) | Tidak ada |

Uang antar-PT wajib rekening bank (kas kecil ditolak, `interco_money_service.py:91-96`). Transfer polos ke PT sama
ditolak dengan petunjuk "pakai pindah-buku/mutasi biasa" — yang tidak ada sebagai dokumen (`interco_money_service.py:46-51`).

**Bila orang memakai kas manual untuk uang antar-PT** (pindah PT aktif, catat "transfer" keluar di PT-A lalu "transfer"
masuk di PT-B): PT-A Dr 1-1150, PT-B Cr 1-1150 — dua neraca salah, tidak ada piutang/utang antar-PT, tidak ikut
eliminasi, tidak terlihat di Saldo Antar-PT. Gabungan "Semua PT" kebetulan nol sehingga kesalahannya tersembunyi.

**Keputusan pemilik:** (a) satu akun buku besar per rekening (rancangan `07` §A3.2) atau tetap per jenis; (b) dokumen
"Pindah Dana" satu-form (rekening asal, tujuan, nominal, biaya transfer + akun biaya, tanggal kirim/terima) dengan
pasangan dijamin; (c) apakah setor tunai ke bank dan isi kas kecil wajib lewat dokumen itu (kategori "Transfer / Top-up"
kas manual ditutup); (d) uang antar-PT selain pinjaman/pelunasan (mis. setoran modal, dividen) perlu jenis dokumen sendiri?

---

## 3. Jurnal otomatis / "smart journaling" dari OCR

### 3.1 Yang ada hari ini

| Kemampuan | Ada? | Bukti |
|---|---|---|
| OCR surat jalan pemasok (Barang Masuk) | **Ada.** OpenAI Responses API, skema JSON ketat `sj-v2`, `store=False`, putar otomatis, cek mutu foto, pembaca kedua, log biaya `ai_usage_log`, rem anggaran bulanan, mode tiruan untuk uji | `backend/services/ocr_openai_client.py:52-168`; `backend/services/ocr_sj_v2.py:1-10`; `backend/services/goods_receipt_ocr_service.py:29-100, 438-540`; `backend/routers/goods_receipts.py:53-59,190-193` |
| Sampel uji ketepatan OCR | **Ada** (khusus SJ): kunci jawaban manusia + ambang (`dn_number` 0,98, qty 0,95) | `backend/services/ocr_sample_service.py:1-25`; `backend/routers/ocr_samples.py` |
| OCR nota/struk/faktur pemasok/bukti transfer | **Belum ada.** `extract()` terikat prompt & skema SJ | `ocr_openai_client.py:56-73` |
| Rekening koran | **Parser berkas, bukan OCR**: CSV/TSV, MT940, OFX, XLSX dengan templat per bank; PDF/foto tidak | `backend/services/bank_statement_parser.py:1-20` |
| Unggah berkas ke asisten (Tanya KN) | **Belum ada**; lapisan penyedia hanya teks/alat | `backend/services/ai_provider.py:1-50`; tidak ada `UploadFile` di `routers/ai_*.py` |
| Kartu tindakan asisten: kas manual & jurnal manual | **Ada** (AG-T5). Akun **tidak diusulkan sistem**: diisi dari permintaan pengguna, diperiksa pintu | `backend/services/ai_cards.py:794-835, 870-905` ("Akun TIDAK dipilih di sini", `:862`) |
| Input berkas lewat asisten | **Ditunda**: "menunggu endpoint lampiran" | `docs/blueprint/unit/AG-T5.md:230`; `docs/blueprint/unit/AG-T3.md:248` |
| Peta kategori → akun | Tiga peta terpisah: kata kunci kas manual (ditulis mati), kategori biaya LPJ (master berlapis per PT), akun kampanye | `gl_service.py:204-221`; `cash_advance_service.py:75-85,140-144`; `backend/services/entity_master_service.py:67-74` |
| Pemetaan akun kebutuhan jurnal otomatis | Ada, dengan **cek jenis akun** saat disetel (`allowed_types`) | `gl_mapping_registry.py:37-45`; `gl_mapping_service.py:169-189` |
| Usulan jurnal menunggu orang kedua | Ada (KF-T6) — bisa jadi wadah "draf dari OCR" | `backend/services/journal_proposal_service.py:1-45` |
| Aturan belajar dari kebiasaan | Ada di rekonsiliasi: setelah N pencocokan manual pola sama → aturan **diusulkan**, manusia menyetujui | `bank_recon_service.py:1438-1490` |
| Lampiran bukti | Ada di LPJ, kasus, retur; **tidak** di kas manual, jurnal manual, tagihan pemasok; kwitansi hanya `proof_url` teks | `cash_advance_service.py:640-705`; `backend/routers/ar_receipts.py:44` |
| `posting_registry` | Registri jenis dokumen yang menjurnal untuk panel Posting Gagal & ulang posting — **bukan** templat jurnal | `backend/services/posting_registry.py:1-25` |

### 3.2 Bagaimana akun dipilih dan divalidasi

- **Kas manual:** lawan akun menurut `ref_type`, lalu **substring** kategori (huruf kecil) terhadap daftar kata, lalu
  `contra_account_code` eksplisit — yang **tidak bisa** dikirim layar/API kas manual
  (`gl_service.py:3289-3322, 3481-3496`; `backend/schemas_purchasing.py:220-231`). Kata "bahan" juga cocok untuk "bahan
  bakar" → Persediaan; "beli" cocok untuk "beli ATK" → Persediaan.
- **LPJ:** kategori → akun dari master `expense_categories` (lapisan PT menang), cadangan 6-4900
  (`cash_advance_service.py:140-144, 706-710`). PATCH kategori global hanya memeriksa akun ada dan bukan induk — **tanpa
  cek jenis** (`cash_advance_service.py:127-133`); lapisan PT lewat master berlapis **tanpa validasi apa pun**
  (`entity_master_service.py:418-423`). Jadi kategori biaya bisa diarahkan ke akun kas, piutang, atau persediaan, dan
  jurnal otomatis tidak menolak akun kontrol (`gl_service.py:607-611`, P10).
- **Jurnal manual:** pengguna memilih akun dari daftar akun aktif bukan induk; akun kontrol disembunyikan bila PT menolak
  (`frontend/src/features/finance/JournalEntryModal.jsx:67-75`). Server: seimbang (sen bulat), akun ada/aktif/bukan
  induk, bukan akun kontrol, periode terbuka, PT = PT aktif (`gl_service.py:658-690, 842-905`). **Tidak ada** aturan
  jenis (mis. "beban ke akun aset"), tidak ada peringatan akun kas tanpa rekening, tidak ada lampiran, tidak ada templat.
- **Rekening PT lain:** ditolak di semua pintu kas (`cash_ledger.py:104-108`; `ap_payment_service.py:104-110`;
  `ar_receipt_service.py:50`). Di jurnal, "rekening" tidak ada sebagai akun, jadi pertanyaan itu tidak berlaku — tetapi
  akibatnya jurnal juga tidak tahu rekening mana yang bergerak (R2).

### 3.3 Jalur terkecil "foto nota → usulan jurnal + tanda curiga" (konsep)

Prinsip yang sudah disetujui di rancangan `08` §3: satu pintu, model hanya mengusulkan, kode yang menghitung dan memilih
akun, isi dokumen = data bukan perintah.

1. **Mulai dari LPJ, bukan jurnal bebas.** LPJ sudah punya lampiran, persetujuan, kategori → akun per PT, anggaran, dan
   jurnal tahan-gagal. Tambah tombol "Baca nota" di lampiran LPJ: foto → baris pengeluaran usulan (tanggal, uraian,
   nominal, **kategori**). Akun tetap dari master kategori; tidak ada jurnal baru yang ditulis model.
2. **Generalisasi pembaca OCR:** `extract()` menerima prompt + skema sebagai parameter (hari ini ditulis mati ke SJ,
   `ocr_openai_client.py:56-73`); skema baru `nota-v1` (penjual, NPWP penjual, nama pembeli, nomor & tanggal nota, baris,
   subtotal, PPN, total, cara bayar). Pakai ulang putar otomatis, cek mutu foto, log biaya, rem anggaran, mode tiruan,
   dan sampel uji (`ocr_sample_service.py`) dengan ambang per field.
3. **Usulan kategori/akun oleh kode, bukan model:** urutan (a) aturan pengguna per penjual/kata (pola
   `learn_from_manual`: usulkan aturan setelah N kali dipilih sama, manusia menyetujui); (b) riwayat pilihan penjual itu
   di PT itu; (c) kategori bawaan. Model boleh menyarankan kategori dari daftar tertutup, kode yang memutus.
4. **Tanda curiga (dihitung kode):** Σ baris ≠ total; tanggal di periode tertutup/lain bulan; nota kembar (penjual +
   tanggal + total, atau sidik gambar); nama pembeli ≠ PT LPJ (salah PT); ada PPN padahal dibebankan penuh (PT PKP);
   kategori menunjuk akun bukan beban (aset/kas/kontrol); nominal melebihi sisa uang muka PD atau anggaran (K-12);
   "barang dagang/bahan" di nota kas (seharusnya PO/tagihan); keterbacaan rendah atau angka ditulis tangan.
5. **Langkah kedua (sesudah LPJ jalan):** foto tagihan pemasok tanpa PO → draf tagihan biaya (butuh fitur tagihan non-PO,
   §5 #5), dan foto struk untuk kas manual → **usulan jurnal** di `journal_proposals` (KF-T6) yang tampil di Jurnal untuk
   disetujui, bukan langsung terposting. Kartu asisten AG-T5 bisa memakai jalur yang sama setelah "endpoint lampiran"
   (AG-T5.md:230) ada.
6. **Pagar akun:** satu validator "jenis akun yang boleh" dipakai master kategori biaya (tutup celah
   `entity_master_service.py:418-423`), kas manual, dan usulan OCR — memakai `allowed_types` yang sudah ada di registri
   pemetaan (`gl_mapping_registry.py:37-45`).

**Keputusan yang dibutuhkan:** dokumen pertama (LPJ · kas manual · tagihan non-PO · bukti transfer · rekening koran PDF);
penyedia & privasi (foto nota memuat nama/NPWP pihak luar — K-43 penyamaran, K-45 asisten mati per akun); anggaran OCR
bulanan dan ambang ketepatan sebelum dinyalakan per PT; boleh-tidaknya model memilih kategori atau hanya membaca angka;
perlakuan PPN nota kas kecil di PT PKP (PK-24 mengecualikannya; K-08); apakah usulan dari OCR selalu butuh orang kedua
(K-44 `kontrol.asisten_uang_keluar`); masa simpan foto.

---

## 4. Dokumen keuangan → detail barang

Komponen rincian bersama yang **menampilkan baris barang**: `OrderDetailPanel` (pesanan, `frontend/src/features/orders/
OrderDetailPanel.jsx:330`), `SOCompactPanel` (`frontend/src/features/orders/SOCompactPanel.jsx:23`), `VendorBillDetailPanel`
(qty pesan/terima/tagih, harga PO vs tagihan, `frontend/src/features/purchasing/VendorBillDetailPanel.jsx:169-176`),
`RecordDetailModal` (generik; tabel item **hanya** bila `itemColumns` diisi, `frontend/src/features/documents/
RecordDetailModal.jsx:70`). Jejak Dokumen (`openTrace`) menampilkan graf relasi + nilai + tombol "Buka dokumen", **tanpa
baris barang** (`frontend/src/features/documents/trace/DocTraceView.jsx:212-234`; `backend/services/doc_refs_service.py:
448-460`). Tidak ada layar "faktur penjualan": faktur komersial = PDF dari pesanan; `GET /invoices` hanya data lama
(`backend/routers/invoices.py:14-19`).

| Layar | Klik nomor/baris → | Baris barang? | Gap | Bukti |
|---|---|---|---|---|
| Perlu Tindakan (`FinanceDesk`) | Tombol "Buka" → **pindah layar** (Pesanan, PO, pelanggan, Rencana & Denda, Retur…) | Tidak di tempat; ada di layar tujuan bila tujuannya pesanan/PO/tagihan | Antrean "Uang masuk" membuka **daftar pelanggan**, bukan pesanan; tidak ada pratinjau barang di meja; pulang ke meja tergantung tombol kembali | `frontend/src/features/finance/FinanceDesk.jsx:72-82,186-195`; `frontend/src/features/sales_admin/workDeskApi.js:255-271,319-343` |
| Piutang › Saldo & Umur (rincian pelanggan) | Nomor pesanan = teks; panah membuka **baris tagihan per surat jalan** (nilai, terbayar, sisa) | **Tidak** | Tidak ada tautan ke pesanan maupun barang; Jadwal Tagihan menaut ke Jejak Dokumen | `frontend/src/features/finance/ARAgingDetail.jsx:164-171,315-347,429` |
| Piutang › Penagihan & Penerimaan | Nomor pesanan berwarna tautan tetapi **tidak bisa diklik** | Tidak | Paling sering dipakai saat menagih, justru tanpa rincian | `frontend/src/features/crm/CollectionWorklist.jsx:111-117` |
| Kwitansi (riwayat) | Nomor kwitansi → Jejak Dokumen; nomor pesanan teralokasi = teks | Tidak | — | `frontend/src/features/crm/ARReceiptsHistory.jsx:225,255` |
| Kartu pelanggan › Tagihan / Rekening koran | Nomor → Jejak Dokumen | Tidak | — | `frontend/src/features/crm/CustomerBillingTab.jsx:99,107`; `CustomerStatementTab.jsx:55,60` |
| Titipan & Saldo Kredit | Nomor pesanan → layar Pesanan (fokus) | Ya, di layar tujuan | Pindah layar | `frontend/src/features/finance/CustomerCreditView.jsx:317` |
| Hutang › Tagihan | Baris → `VendorBillDetailPanel` di tempat | **Ya** (lengkap + 3-way match) | — (contoh baik) | `frontend/src/features/purchasing/VendorBillsView.jsx:241,360` |
| Hutang › Hutang per Pemasok | Nomor tagihan/kontrabon → Jejak Dokumen | Tidak (2 lompatan lagi) | Panel rincian pemasok tidak memakai `VendorBillDetailPanel` | `frontend/src/features/finance/ap/APSupplierDetail.jsx:166,209` |
| Hutang › Kontrabon | Baris → `ContraBonDetailPanel`; daftar faktur di dalamnya = teks | Tidak (hanya nomor & nilai faktur) | Tidak bisa membuka faktur/barang dari kontrabon kecuali lewat "Dokumen terkait" | `frontend/src/features/purchasing/contrabon/ContraBonParts.jsx:84`; `ContraBonDetailPanel.jsx:252` |
| Kartu pemasok (Supplier 360) | PO → `RecordDetailModal` **dengan** barang; Tagihan & Retur beli → `RecordDetailModal` **tanpa** kolom item | PO ya; tagihan & retur **tidak** (`itemColumns: []`) | Perbaikan kecil: isi `itemColumns` | `frontend/src/features/purchasing/Supplier360Panel.jsx:100-125,127-142,143-157` |
| Hutang › GR/IR | Nomor → dokumen asalnya | Di layar tujuan | Pindah layar | `frontend/src/features/purchasing/GrIrView.jsx:209` |
| Pajak › Faktur Keluaran | Nomor pesanan → layar Pesanan | Tidak di rincian faktur (hanya DPP/PPN) | Faktur pajak tanpa daftar barang di layar | `frontend/src/features/finance/TaxInvoices.jsx:99,134-137,554-568` |
| Selisih bayar, Denda | Nomor → Jejak Dokumen | Tidak | — | `frontend/src/features/finance/payments/PaymentVarianceQueue.jsx:209,287`; `PenaltyPanel.jsx:148` |
| Transaksi Kas | Tidak ada tautan sama sekali | Tidak | Lihat C14 | `CashManagementView.jsx:395-425` |
| Kas Kecil › PD / LPJ | Rincian dokumen | Ya (baris PD/LPJ) | — | `frontend/src/features/pettycash/CashAdvanceDetail.jsx:132`; `SettlementDetail.jsx:219` |
| Jurnal › rincian | Bilah "Dokumen sumber" → dokumen | Di layar tujuan | — | `frontend/src/features/finance/JournalDetailModal.jsx:11-13,45-49` |

**Saran ringkas:** satu komponen "pratinjau dokumen" (laci samping) yang menerima `{docType, docId}` dan merender baris
barang untuk pesanan, tagihan pemasok, retur, kontrabon (gabungan baris faktur), surat jalan — dipanggil dari semua nomor
di atas sebelum opsi "Buka layar penuh". Bahan sudah ada: `RecordDetailModal` + `VendorBillDetailPanel` + data `items`.
Perbaikan termurah: isi `itemColumns` tagihan & retur di `Supplier360Panel.jsx:141,156`; jadikan nomor pesanan di
`CollectionWorklist.jsx:117` dan `ARAgingDetail.jsx:171` bisa diklik.

---

## 5. Gap otomasi kerja berulang di keuangan

### 5.1 Pekerjaan berulang hari ini: yang sudah otomatis dan celahnya

| Pekerjaan | Di mana | Yang sudah ada | Celah |
|---|---|---|---|
| Jurnal berulang (sewa, asuransi/biaya dibayar dimuka, akrual listrik/internet, alokasi biaya) | Akuntansi › Jurnal (`JournalEntryModal.jsx`) | Validator, tanggal buku, usulan dua orang | **Tidak ada templat, salin jurnal, impor, atau jadwal** (audit §7 "jurnal berulang/templat … tidak ditemukan"; §8 gap "Rendah–sedang") — diketik ulang tiap bulan per PT |
| Penyusutan | Aset Tetap | Satu klik per periode untuk semua aset, idempoten, tanggal akhir periode (`backend/routers/fixed_assets.py:117-119`; `fixed_asset_service.py:551-557`; `backend/services/periodic_posting.py:1-12`); pengingat harian bila belum dijalankan (`scheduler_service.py:107-110`) | Masih harus diklik; tidak ada jalankan otomatis tanggal 1 |
| Gaji, BPJS/PPh 21, insentif | Penggajian | Posting & bayar & setor kewajiban otomatis jurnalnya (PY-T4, PK-22) | — (sudah baik) |
| Mencocokkan mutasi bank | Kas & Bank › Rekonsiliasi | Impor CSV/MT940/OFX/XLSX, cocok otomatis tiga pita + kode bayar + aturan belajar (`bank_recon_service.py:1082-1155, 491-505, 1438-1490`) | Cocok otomatis = tombol terpisah, tidak jalan saat impor (`backend/routers/bank_reconciliation.py:199-248`); tidak ada tarikan mutasi dari bank |
| Biaya adm/bunga/pajak bunga bank | Rekonsiliasi › "Bukukan biaya" | Satu klik per baris (`bank_recon_service.py:1321-1345`) | Aturan hanya menambah skor cocok, **tidak membukukan otomatis** (`bank_recon_service.py:1100-1110`) |
| Mencatat uang masuk pelanggan | Penagihan & Penerimaan / Perlu Tindakan | Satu form untuk banyak pesanan satu pelanggan, alokasi FIFO otomatis (`ar_receipt_service.py:1-22`); kode bayar di instruksi (PM-T2) | Kwitansi diketik **satu per transfer**; mutasi bank berkode bayar tidak membuat kwitansi sendiri — paling jauh jadi titipan lalu dialokasikan manual (`bank_recon_service.py:1524-1600`) |
| Bayar hutang | Hutang per Pemasok | Bayar beberapa tagihan **satu pemasok** (N kas, `frontend/src/features/finance/ap/PayManyBillsModal.jsx`) | Tidak ada jadwal/bayar massal lintas pemasok ("belum ada unitnya", `docs/blueprint/unit/MN-T3.md:208`); tidak ada berkas transfer bank |
| Tagihan biaya rutin (sewa, listrik, ekspedisi, jasa) | Hutang › Tagihan | — | Tagihan pemasok **wajib PO** (`backend/schemas_purchasing.py:263-264`); tanpa PO hanya dari makloon & kampanye (`backend/services/makloon_order_service.py:1117`; `backend/services/marketing_cost_service.py:220`). Akibatnya biaya rutin lewat kas manual (C5) atau PO pura-pura. Anggaran sudah mengantisipasi tagihan non-PO (`backend/services/budget_service.py:840`) |
| Faktur pajak keluaran | Pajak › Faktur Keluaran | Draf otomatis dari pemicu PT + pemulih draf terjadwal (TX-T2; `scheduler_service.py:349`) | Terbitkan & isi NSFP **satu per satu** (`backend/routers/tax_invoices.py:68-152`); ekspor Coretax `tahan` (TX-T3, K-08) |
| Kas kecil: isi ulang & LPJ | Kas Kecil, Transaksi Kas | PD/LPJ berjenjang, kategori → akun | Isi ulang manual dua kali (§2.3); baris LPJ diketik dari nota (C4) |
| Tutup bulan | Tutup Buku | Daftar periksa (`closing_checklist.py`), paket tutup buku & ringkasan pagi asisten (AG-T4), tutup otomatis jendela buka periode | Langkah dijalankan satu-satu (susut, cek gaji, akrual insentif, rekonsiliasi, reklas suspense); daftar periksa tanpa butir kas tunai, transit 1-1150, titipan 1-1280, uang muka 1-1400 |
| Jurnal antar-PT | Antar-PT | Otomatis dua sisi (PK-06) + pengingat settlement/bayar (`scheduler_service.py:178,319`) | — |
| Pengingat & denda | Penjadwal | Pengingat internal H-3…H+1, piutang lewat tempo, usulan nota denda harian (`scheduler_service.py:99-102,158-166`) | Pengingat hanya ke sales internal (`backend/services/alert_ops_service.py:287-330`); ke pelanggan = "Salin pengingat" manual (CR-T5: "pengiriman otomatis menyusul", `docs/finance/rencana-2026-11-13/06_PIUTANG_LANJUT.md:214`) |
| Cek kecocokan buku pembantu ↔ buku besar | Skrip luring | `scripts/verify_data_integrity.py`; pantau selisih persediaan harian (`scheduler_service.py:207`) | Tidak ada pemeriksaan harian piutang/hutang/kas/titipan vs akun kontrol ("tidak dikerjakan", `docs/blueprint/unit/PK-35.md:188`) |

### 5.2 Daftar fitur berperingkat (paling banyak menghapus kerja berulang)

Perkiraan beban kasar untuk 3–5 PT; frekuensi × usaha adalah taksiran pembaca kode, belum diukur di lapangan.

| # | Fitur | Kerja yang hilang (kasar) | Memakai ulang | Risiko & pengaman | Keputusan pemilik | Sudah direncanakan? |
|---|---|---|---|---|---|---|
| 1 | **Kwitansi otomatis dari mutasi bank** — mutasi masuk dengan kode bayar unik + nominal = sisa tagihan → kwitansi "terverifikasi bank" lahir sendiri (atau kartu siap setuju); sisanya titipan dengan usulan pesanan | Harian; tiap transfer pelanggan ±2–4 menit ketik + cocok. Puluhan per hari → jam per minggu | `pay_code_hits` (`bank_recon_service.py:491-505`), alokasi titipan (`:1588`), `create_receipt`, status terverifikasi PM-T3, kartu AG-T3 | Salah alokasi → hanya cocok sempurna yang otomatis; pratinjau harian; jejak "lahir dari mutasi"; bisa dibatalkan seperti kwitansi biasa | Otomatis penuh atau kartu; toleransi nominal; per PT | **Sebagian**: `07` §A3.6 "cocok sempurna boleh otomatis" hanya untuk mencocokkan kwitansi yang sudah ada; membuat kwitansi dari mutasi belum ada unitnya |
| 2 | **Jurnal berulang & templat** — templat baris (akun, nominal tetap/rumus, PT), jadwal bulanan, lahir sebagai usulan jurnal tanggal akhir periode; "Salin jurnal" | Bulanan; 10–30 jurnal/PT diketik ulang | `journal_proposals` (KF-T6), `create_manual_entry` + validator + penjaga akun kontrol, `periodic_posting.journal_date`, `scheduler_service` | Jurnal salah berulang tiap bulan → selalu usulan (draf) + setuju; templat berversi; berhenti otomatis di tanggal akhir | Draf vs auto-post; siapa menyetujui; akun yang boleh di templat | **Tidak** (audit §7/§8 menyebutnya gap; tidak ada unit) |
| 3 | **Smart journaling dari foto nota/faktur** — OCR → baris LPJ / draf tagihan / usulan jurnal dengan kategori-akun usulan dan tanda curiga (§3.3) | Mingguan–harian; tiap nota 1–3 menit ketik + salah ketik | `ocr_openai_client`, `ocr_sample_service`, lampiran LPJ + `storage_service`, master kategori biaya, `journal_proposals`, aturan belajar ala `learn_from_manual`, kartu AG-T5 | Salah baca/akun → model hanya membaca, kode memilih akun dari daftar tertutup; tanda curiga; selalu disetujui manusia; anggaran & ambang ketepatan; privasi K-43 | Lihat §3.3 | **Sebagian**: `08` §4.3 "input dari berkas" dirancang, ditunda (AG-T5.md:230, AG-T3.md:248) |
| 4 | **Aturan bank otomatis membukukan** — baris biaya adm, bunga, pajak bunga, autodebet tetap (PLN/telepon/BPJS) dibukukan sendiri ke akun aturan saat impor | Bulanan per rekening; 3–10 baris × klik + pilih akun | `bank_match_rules` + `learn_from_manual`, `book_charge` (`bank_recon_service.py:1321`), Pemetaan Akun `kas_bank.beban_bank`/`pendapatan_bunga` | Aturan salah → aturan diusulkan sistem, disetujui manusia (sudah polanya); batas nominal per aturan; bisa "Lepas" | Jenis baris yang boleh otomatis; batas nominal | **Tidak** |
| 5 | **Tagihan biaya tanpa PO + tagihan berulang** — tagihan pemasok berakun beban (sewa, listrik, jasa, ekspedisi), opsi jadwal bulanan; dibayar lewat satu pintu bayar hutang | Bulanan; menghapus "PO pura-pura" dan kas manual biaya | `vendor_bills` + persetujuan `tagihan_pemasok`, `ap_payment_service`, anggaran non-PO (`budget_service.py:840`) | Hutang fiktif → persetujuan dua orang yang sudah ada; akun beban dari daftar tertutup; lampiran wajib | Siapa membuat (Finance/peminta); akun boleh; apakah kas manual biaya ditutup | **Sebagian**: K-12 menyebut "faktur non-PO" untuk anggaran; fiturnya belum ada unit |
| 6 | **Jadwal & bayar massal hutang** — pilih tagihan jatuh tempo lintas pemasok → satu persetujuan → N pembayaran + daftar transfer untuk bank | Mingguan; tiap tagihan 1–2 menit | `ap_payment_service` (niat, idempoten), `PayManyBillsModal`, pola daftar transfer gaji PY-T4, `match_group` rekonsiliasi | Bayar ganda/salah rekening → niat per tagihan (sudah), persetujuan `kontrol.bayar_hutang`, rekening pemasok berpersetujuan (`07` §A3.9) | Hari bayar tetap; batas & dua orang | **Tidak** ("belum ada unitnya", MN-T3.md:208) |
| 7 | **Kas kecil imprest + isi ulang otomatis + opname kas** — saldo tetap per rekening tunai; usulan isi ulang = Σ LPJ disetujui sejak isi terakhir → satu dokumen pindah dana; opname berkala dengan akun selisih | Mingguan; menghapus kas manual "Top-up" berpasangan dan rekap LPJ | `pindah_buku` (`finance_case_actions.py:803`), `create_cash`, LPJ, daftar periksa tutup buku | Kas hilang tak terlihat → opname wajib sebelum isi ulang; selisih butuh persetujuan | §1.5 butir 1–3 | **Tidak** |
| 8 | **Dokumen "Pindah Dana" antar rekening sendiri** (dengan biaya transfer) + butir tutup buku "1-1150 = 0" | Harian–mingguan (setor kas toko ke bank) | `act_pindah_buku`, `create_cash`, `book_charge` | Sebelah/ganda → satu dokumen dua kaki idempoten; terlihat di rekonsiliasi | §2.3 keputusan b–c | **Tidak** |
| 9 | **Tutup bulan satu tombol** — jalankan berurutan: susut, cek gaji, akrual insentif, cocok otomatis bank, cek transit/titipan/uang muka/suspense, paket laporan; berhenti di butir merah | Bulanan; ½–1 hari per PT | `closing_checklist.py`, `run_depreciation`, AG-T4 paket tutup buku, `posting_registry` (ulang posting gagal) | Langkah gagal di tengah → tiap langkah idempoten (sudah), ringkasan sebelum tutup, tutup tetap manusia | Urutan & butir wajib | **Sebagian**: daftar periksa (PK-43) & paket (AG-T4) ada; orkestrasi belum |
| 10 | **Pengingat tagihan ke pelanggan otomatis** (WA/email berisi instruksi bayar + kode bayar) & **faktur pajak massal** (terbitkan terpilih, impor rentang NSFP) | Harian (penagihan) & bulanan (pajak) | Naskah pengingat CR-T5, kode bayar PM-T2, saluran WA KP-T8 (`wa_alert_service`), draf faktur TX-T2 | Pesan salah ke pelanggan → hanya tagihan terbuka, jendela kirim, berhenti bila sudah bayar; pajak: periksa sebelum terbit | Saluran & jam kirim; nada pesan; siapa menerbitkan faktur | **Sebagian**: CR-T5 "pengiriman otomatis menyusul"; ekspor Coretax TX-T3 `tahan` (K-08) |
| 11 | **Pemeriksaan harian buku pembantu ↔ akun kontrol** (piutang, hutang, kas per rekening, titipan, transit) dengan notifikasi | Harian; menggantikan cek manual di akhir bulan | `verify_data_integrity.py`, invarian INV-TTP-01 (`cash_holding_service.py:16-19`), penjadwal | Hanya membaca | Penerima notifikasi | **Sebagian**: audit §9.3 langkah 2; PK-35.md:188 "tidak dikerjakan" |

---

## 6. Rujukan rencana yang sudah ada (jangan dibuat ulang)

- Titipan tunai sales PM-T4 (selesai, `38c715f`) — tinggal keputusan H5 per PT (K-36).
- Rekening ber-peruntukan PM-T1, kwitansi ber-rekening PM-T3 (selesai).
- Satu akun buku besar per rekening: rancangan `07` §A3.2 (`07_PAJAK_DAN_PEMBAYARAN.md:81`), **tanpa unit** (PM-T1.md:215).
- Kas satu pembuat PK-20, kas kecil PK-24 (selesai); "tiga wadah uang dipegang orang" dan PPN nota kas kecil sengaja di
  luar lingkup PK-24.
- Asisten AG-T1…T5 (selesai); input berkas ditunda (AG-T5.md:230).
- Bayar massal: tanpa unit (MN-T3.md:208).
- VA/QRIS PM-T5 dan Coretax TX-T3: `tahan` (K-35, K-08).
