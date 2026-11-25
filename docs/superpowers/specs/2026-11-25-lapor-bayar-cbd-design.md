# Rancangan — Lapor Bayar CBD & DP (tahan sebelum gudang)

Tanggal: 25 Nov 2026 · Status: **keputusan pemilik B1–B7 disetujui** (`docs/keputusan/2026-11-25_DAFTAR_KEPUTUSAN_TERBUKA.md` §B,
"ya semuanya setuju"); bentuk UI dari pemilik: *"dibuat simpel … jangan dibuat tampilan baru yang rumit, sisipkan saja di
setiap step fase alur pembelian … diantara disetujui admin sales dan step berikutnya"*; titik tahan: *"tahan sebelum
gudang"*. Keputusan builder di §7 dikerjakan tanpa menunggu (perintah pemilik "langsung lanjut kerjakan saja semua") dan
dilaporkan untuk diperiksa. Inventaris kode: `.superpowers/sdd/…/inventaris` (salinan dari scratchpad
`lapor_bayar_inventaris.md`), dianalisis di `a5199a4`.

## 1. Masalah

- Pesanan CBD (bayar sebelum kirim) dan bagian DP pesanan termin DP **bisa dilepas ke gudang tanpa uang**. Gerbang bayar
  hari ini hanya di surat jalan (`dispatch_payment_gate.guard` dari `loading_check_service.dispatch_guard`), jadi gudang
  sudah mengambil dan menyiapkan barang.
- Sales mencatat kwitansi transfer langsung (`POST /ar-receipts`, izin `ar_receipt.create`). Kwitansi itu langsung
  `posted`: kas dan jurnal terbit sebelum ada yang mencocokkan bukti transfer.
- Pelanggan CBD tidak bisa menerima invoice berkode bayar sebelum membayar. Kode bayar dan Faktur Komersial baru lahir
  saat pesanan dikonfirmasi (dilepas ke gudang).
- Pesanan yang sudah disetujui tidak pernah kedaluwarsa, jadi stoknya bisa terkunci tanpa batas. Penyapu hanya mengurus
  status `reserved` dan `waiting_approval`.

## 2. Tujuan dan bukan tujuan

**Tujuan:**
- Pesanan yang wajib bayar dulu berhenti di tahap **"Bayar dicek Finance"**, di antara "Disetujui" dan "Dilepas ke
  gudang".
- Sales melaporkan bayar (foto/PDF), lalu Finance menerima atau menolak.
- Bila diterima, kwitansi dan jurnal terbit otomatis, dan pesanan lepas ke gudang sendiri.
- Tidak ada layar baru.

**Bukan tujuan:**
- Rekonsiliasi mutasi bank otomatis (F1 "kwitansi otomatis dari mutasi").
- Paket Kas & Bank.
- Alur tunai lapangan (C4 belum dijawab).
- Perubahan matriks izin bawaan di luar izin baru fitur ini.

## 3. Siapa kena, kapan

"Wajib bayar dulu" memakai satu hitungan, yaitu `dispatch_payment_gate.evaluate` yang sudah ada:
- termin `dp_percent > 0` (CBD 100%, DP50 50%, dst.);
- termin `type: cash`, bila `finance.tahan_kirim_tunai`;
- `order.pay_before_ship` (keputusan kredit K-27);
- pesanan sample tetap dikecualikan;
- `finance.dispatch_payment_gate = off` mematikan tahan ini juga.

Jumlah wajib dan uang yang dihitung tetap mengikuti `finance.tahan_kirim_dasar_bayar` (`tercatat` / `terverifikasi`),
supaya gerbang gudang dan gerbang surat jalan tidak pernah berbeda pendapat.

## 4. Alur

```
Dipesan → Disetujui ──(wajib bayar dulu?)── tidak ─────────────────────────────→ Dilepas ke gudang → …
                          │ ya
                          ▼
                 Bayar dicek Finance
       (invoice + kode bayar sudah ada · batas bayar berjalan)
                          │
     sales "Lapor bayar" (bukti + nominal + tanggal + rekening)
                          │
          Finance  Terima ───→ kwitansi + jurnal → cukup? → lepas otomatis ke gudang
                   Tolak (alasan) → sales diberi tahu, boleh lapor ulang
     lewat batas tanpa laporan menunggu → kedaluwarsa, stok dilepas, uang masuk → titipan
     Finance/Manager/Admin "lepas tanpa bayar" (alasan) → lepas ke gudang (B6, jalur yang sudah ada)
```

## 5. Rancangan

### 5.1 Tahan sebelum gudang (server)

- **Penanda, bukan status baru.**
  - Pesanan tetap `approved` dengan `pay_hold = {since, due_at, required, basis}`.
  - Sub-status `menunggu_bayar` mengikuti preseden `credit_hold` / `tahan_kredit` di `so_status.derive_stage_substatus`.
  - Mesin status, `STATUS_LABEL`, penyapu yang lain, dan penjaga `verify_state_machine` tidak berubah.
- **Titik periksa ditambahkan di `confirm_core`**, sesudah `credit_gate.gate_checkpoint(LEPAS_GUDANG)`. Bila wajib bayar
  dulu dan `evaluate(...).blocked` serta belum ada `dispatch_payment_release`, pesanan tidak dikonfirmasi.
  - **Jalur anggun untuk "Periksa & lepas" Admin Sales.** `try_release` tidak 409. Ia mengembalikan dan menulis
    `release.waiting = "bayar"`, dan pesanan pindah ke tahap "Bayar dicek Finance".
  - **Jalur rute lama `POST /confirm` dan pemanggil lain.** Galat 409 dengan pesan pemandu: "Menunggu pembayaran
    dicek Finance — lapor bayar di rincian pesanan."
- **Lepas otomatis.** Sesudah Finance menerima laporan dan uang cukup, jalur yang sama dengan `auto_release` dipanggil
  lagi. Tanda `release.requested` dari "Periksa & lepas" tetap berlaku, jadi Admin Sales tidak perlu menekan lagi.
- **Gerbang surat jalan tetap** sebagai pagar kedua. Hitungannya sama, jadi tidak ada perubahan perilaku untuk pesanan
  yang sudah lewat gudang.
- **Lepas tanpa bayar (B6).** `POST .../dispatch-payment-release` yang sudah ada kini juga membuka tahan gudang dan memicu
  lepas otomatis. Izin, alasan, dan jejaknya tetap.

### 5.2 Invoice dan kode bayar sejak disetujui (B1)

- **Saat tahan bayar dimulai**, yaitu pada kali pertama pesanan yang wajib bayar dulu mencapai `approved` lewat
  `submit_core` (otomatis) atau keputusan ACC:
  - `payment_code_service.ensure_for_order` dipanggil.
  - `pay_hold` ditulis.
  - `ensure_for_order` sendiri tetap idempoten. `confirm_core` tetap memanggilnya untuk pesanan lain.
- **Faktur Komersial dan Konfirmasi berinstruksi bayar boleh dicetak sejak `approved`**, bila pesanan wajib bayar dulu.
  - Daftar status di `OrderDetailPanel` ditambah, begitu juga `orderPrintDocs`.
  - Perjalanan `commercial_invoice.available` menjadi benar sejak tahan bayar.
  - Cetakan memuat cap "Belum dibayar" sampai lunas bagian wajib. Isi cap memakai status pembayaran yang sudah ada;
    templat baru tidak diperlukan.
  - Pesanan non-CBD tidak berubah (keputusan F-08 lama: tersedia sejak dikirim).
- **Termin DP.** Kode tingkat pesanan yang sama dipakai untuk bagian DP. Jadwal tagihan tetap lahir di `confirm_core`.

### 5.3 Batas waktu bayar (B2)

- **Pengaturan baru** `sales.batas_bayar_hari`: durasi, bawaan 3, min 1, maks 30, per grup/PT, dibaca lewat
  `nilai(...)`. Katalognya ditaruh di `config_catalog_nilai.py`, di samping `sales.reservation_days`.
- **`pay_hold.due_at`** = waktu tahan dimulai + N hari.
- **Penyapu `expire_old_reservations`** juga memproses pesanan `approved` ber-`pay_hold` yang `due_at`-nya lewat.
  Langkahnya sama persis dengan kedaluwarsa cadangan: klaim atomik, lepas roll, `expired`, balik jurnal, uang muka ke
  titipan (`uang_muka_pesanan_batal_ke_titipan`, sudah ada), dan notifikasi Finance `titipan_pesanan_batal`.
  - **Pengecualian:** pesanan dengan laporan bayar berstatus `menunggu` **tidak** dikedaluwarsakan. Uang pelanggan
    mungkin sudah masuk; yang terlambat adalah pengecekan Finance. Finance diberi tahu "laporan bayar menunggu melewati
    batas".
- **Pengingat H-1** ke sales pemilik dan pemegang `order.confirm` memakai mekanisme `generate_system_notifications`.
  - Jenis baru: `pay_due_soon`, dengan ambang yang sama dengan `notif.reservation_expiry_warn_hours`.
  - Pengingat lama `reservation_expiring` tidak lagi menyebut status `approved` / `waiting_stock`, yang memang tidak
    pernah kedaluwarsa (merapikan ketidakselarasan yang ditemukan inventaris).

### 5.4 Lapor bayar (B3, B4, B5, B7)

**Data.** Koleksi baru `payment_reports`. Ber-PT, jadi masuk peta cakupan entitas.

| Isian | Keterangan |
|---|---|
| `id`, `number` | Nomor `LB-…` dari penomoran baku |
| `order_id`, `order_number`, `customer_id`, `entity_id` | |
| `amount`, `transfer_date`, `account_id` | Rekening penerimaan PT pesanan, dari `bank-accounts/receiving` (B7; PT lain → 400) |
| `method` | Dari daftar induk cara bayar non-tunai |
| `reference_no` | Opsional |
| `note` | |
| `attachments[]` | `storage_service`, pola evidence SO; wajib ≥ 1 sebelum laporan bisa diputus |
| `status` | `menunggu` → `diterima` / `ditolak` |
| `reported_by`, `reported_at` | |
| `decided_by`, `decided_at`, `reason` | |
| `receipt_id` | Diisi saat diterima |
| `status_history` | Lewat `services/status_history.entry` |

**Izin baru** `payment_report`:
- `create`: bawaan sales, sales_admin, finance, admin, manager.
- `decide`: bawaan finance, admin, manager.
- `view`: mengikuti `order.view` pada pesanan.

Didaftarkan di `access_modules`, `permissions_config`, dan labelnya. Wewenang dari izin, bukan nama peran.

**Rute.** Semua di bawah `/api/payment-reports`, idempoten, dan masuk `MONEY_PREFIXES`.

| Rute | Kegunaan |
|---|---|
| `POST /api/sales-orders/{id}/payment-reports` | Buat laporan. Pesanan harus ber-`pay_hold` aktif, atau bagian DP/CBD masih kurang. Nominal > 0. |
| `POST /api/payment-reports/{id}/attachments`, `GET …/attachments/{att}` | Unggah dan unduh bukti. Unduh lewat blob, tanpa token di URL. |
| `POST /api/payment-reports/{id}/terima` | Terima |
| `POST /api/payment-reports/{id}/tolak` | Tolak |
| `GET /api/sales-orders/{id}/payment-reports` | Daftar laporan satu pesanan |

Nama `terima`/`tolak` dipakai dengan sengaja (bukan `reject`). Rute keputusan didaftarkan di `verify_approval_queues`
sebagai pintu dengan antrean Meja Keuangan `lapor_bayar`.

**Terima.**
- CAS dari `menunggu` ke `diterima`.
- Memanggil `ar_receipt_service.create_receipt`, satu pintu kas, dengan isian:
  - `customer_id`, `amount`, `method`;
  - `account_id` dari laporan;
  - `receipt_date = transfer_date`;
  - `reference_no`;
  - `proof_url` = tautan lampiran laporan;
  - alokasi ke pesanan itu.
- Jurnal tetap jurnal kwitansi biasa (uang muka 2-1400 untuk bagian sebelum kirim).
- Lalu memeriksa ulang tahan dan mencoba lepas otomatis.
- Gagal di tengah → laporan kembali ke `menunggu` (pola rollback `create_receipt`).
- Terima **tidak** menandai `bank_verified`; itu tetap hak rekonsiliasi bank. Lihat §7-5.

**Tolak.**
- CAS dari `menunggu` ke `ditolak`, dengan alasan ≥ 5 huruf.
- Tidak ada uang yang bergerak.
- Sales diberi tahu dan boleh lapor ulang.

**Laporan ganda.** Satu pesanan boleh punya beberapa laporan (DP lalu pelunasan, atau setelah ditolak). Laporan baru
dengan nominal dan tanggal sama dengan laporan `menunggu` lain ditolak server dengan 409 dan pesan pemandu.

**B3 di server.** `create_receipt` menolak (409, pesan "Pesanan ini menunggu lapor bayar — pakai Lapor bayar") bila
ketiga syarat ini terpenuhi:
- pencatat tidak punya `payment_report.decide`;
- cara bayar non-tunai;
- alokasinya menyentuh pesanan ber-`pay_hold` aktif.

Tunai tetap mengikuti `pembayaran.sales_terima_tunai`. Kwitansi Finance tetap bebas.

### 5.5 Layar — disisipkan, tanpa layar baru

- **Rincian pesanan** (desktop dan HP). Panel "Bayar sebelum kirim" (`DispatchPaymentGatePanel`) menjadi
  "Bayar sebelum gudang" bila tahan aktif.
  - Ringkasan wajib, tercatat, dan kurang; batas bayar dengan sisa hari.
  - Tombol **"Lapor bayar"**, bagi pemegang `payment_report.create`. Membuka `FormModal`:
    - nominal, bawaan = kurang;
    - tanggal transfer, bawaan hari ini;
    - rekening tujuan (pilihan rekening penerimaan PT);
    - cara bayar;
    - referensi;
    - unggah bukti (wajib).
  - Daftar laporan pesanan: status, bukti (pratinjau gambar/PDF), alasan tolak.
  - Bagi pemegang `payment_report.decide`: **Terima** (pratinjau kwitansi yang akan terbit, lalu konfirmasi) dan
    **Tolak** (`askReason`) di baris laporan itu.
  - Tombol lama "Terima pembayaran" (kwitansi langsung) disembunyikan untuk pencatat yang ditolak server di §5.4.
- **HP sales.** Rincian pesanan HP mendapat panel yang sama (lapor bayar dari HP, foto dari kamera).
  `MobileArReceipt` memberi pesan pemandu bila pesanan terpilih menunggu lapor bayar.
- **Perjalanan pesanan.** Langkah baru `bayar_dicek` ("Bayar dicek Finance") di antara `disetujui` dan `dikonfirmasi`.
  - Dilewati (`_mark_skipped`) bila pesanan tidak wajib bayar dulu.
  - Kunci langkah ditambahkan di `OrderJourneyPanel.jsx` dan `MobileOrderJourney.jsx`.
- **Meja Keuangan.** Antrean baru `lapor_bayar` di kelompok "Uang masuk", berisi laporan `menunggu` (izin
  `payment_report.decide`).
  - Pop-up meja: rincian laporan + bukti + pratinjau pesanan (registri gelombang 2), dengan aksi Terima/Tolak di tempat.
  - Antrean `bayar_sebelum_kirim` yang ada tetap. Baris pesanan yang sudah punya laporan menunggu disembunyikan dari
    situ supaya tidak ganda.
- **Meja Admin Sales.** Keterangan baris `_ket` mengenal "menunggu bayar (dicek Finance)". Pesanan itu tidak tampil
  sebagai "siap dilepas".
- **Pelacak SO.** `next_step` untuk pesanan `approved` ber-tahan = "Menunggu bayar — Finance", berperan finance. Hold
  dihitung juga untuk status pra-gudang.
- **Notifikasi** (`create_addressed`):

  | Jenis | Ke | Isi |
  |---|---|---|
  | `lapor_bayar_masuk` | `payment_report.decide` | Laporan bayar masuk |
  | `lapor_bayar_diterima` | Pelapor + sales pemilik | Laporan diterima |
  | `lapor_bayar_ditolak` | Pelapor + sales pemilik | Alasan tolak |
  | `pay_due_soon` | Sales pemilik + `order.confirm` | Batas bayar H-1 |
  | (pemberitahuan) | Finance | Laporan menunggu melewati batas |

  Label dicantumkan di `NotificationCenter`.

## 6. Uji

- **Backend `tests_mem`:**
  - tahan di `confirm_core`; jalur anggun `try_release`; lepas otomatis sesudah terima;
  - lepas tanpa bayar membuka tahan;
  - kode bayar lahir saat `approved`;
  - penyapu: lewat batas tanpa laporan → kedaluwarsa + titipan; ada laporan `menunggu` → tidak;
  - terima memanggil `create_receipt` (jurnal uang muka benar, kwitansi teralokasi);
  - tolak tidak menggerakkan uang;
  - CAS ganda terima → 409;
  - laporan ganda → 409;
  - `create_receipt` sales transfer ke pesanan ber-tahan → 409, sedangkan tunai dan Finance tetap boleh;
  - isolasi PT (rekening PT lain → 400, laporan PT lain → 403);
  - izin baru.
- **Jest:** panel lapor bayar (validasi, unggah wajib, Terima/Tolak berizin); langkah Perjalanan desktop dan HP; antrean
  Meja Keuangan di tempat; pesan pemandu kwitansi.
- **Penjaga:**
  - `verify_money_idempotency`, `verify_cash_single_door`, `verify_posting_coverage`, `verify_atomic_claim`;
  - `verify_permission_checked`, `verify_approval_queues`, `verify_home_kpi`;
  - `verify_notification_audience`, `verify_status_history`, `verify_payment_vocab`, `verify_config_*`.

  Gate `--quick` + `--ci` sekali di akhir, dinilai per pelanggaran.
- **Tangkapan layar.** Data acuan tidak punya pesanan CBD/DP. Skrip tangkapan membuat satu pesanan CBD dan satu DP50
  lewat API di lingkungan uji. Data nyata tidak disentuh.

## 7. Keputusan builder (diperiksa pemilik, dikerjakan tanpa menunggu)

1. **"Tertahan bayar" = penanda `pay_hold` + sub-status, bukan status baru.** Lebih sedikit yang berubah, dan mengikuti
   preseden tahan kredit.
2. **Pesanan dengan laporan bayar menunggu tidak kedaluwarsa** walau lewat batas. Finance diberi tahu. Ini supaya uang
   pelanggan yang sudah masuk tidak membuat pesanannya batal.
3. **Antrean keputusan di Meja Keuangan, bukan Pusat Persetujuan Manajer.** Ini pekerjaan rutin Finance, bukan ACC.
4. **Satu pesanan boleh banyak laporan** (DP lalu pelunasan, atau lapor ulang sesudah ditolak). Laporan kembar yang masih
   menunggu ditolak server.
5. **Terima ≠ cocok mutasi bank.** Bila suatu PT memakai `finance.tahan_kirim_dasar_bayar = terverifikasi`, pesanan
   baru lepas sesudah rekonsiliasi bank menandai kwitansinya. Layar menulis "Menunggu cocok mutasi bank". Bawaan
   `tercatat` (semua PT hari ini) melepas langsung saat diterima.
6. **Cap "Belum dibayar"** pada Faktur Komersial yang dicetak sebelum lunas bagian wajib.
7. **Izin baru `payment_report.create/decide`** dengan bawaan di §5.4. Sales tetap memegang `ar_receipt.create` untuk
   tunai dan pesanan non-tahan.

## 8. Batasan

- Mengikuti `AGENTS.md`: wewenang dari izin, nilai aturan dari pengaturan, Bahasa Indonesia, LF.
- Jangan ubah `deploy/`. Data nyata = STOP & ASK. Uji hemat.
- Pop-up hanya `DetailModal` / `FormModal`.
- Kas hanya lewat `create_receipt`. Jurnal tidak bertambah jenis.
