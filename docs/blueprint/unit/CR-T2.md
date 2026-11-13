# CR-T2 — Jadwal tagihan sebagai satu sumber jatuh tempo, dan saldo piutang tersimpan per pelanggan per PT

| | |
|---|---|
| Gelombang | Modul piutang dan kredit |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | PK-19, PK-41 |
| Menutup temuan | CR-06, CR-09 |
| Keputusan | K-16, K-31 |
| Standar | §1 (P3), §3.1 (Z1), §3.4 (N1–N3), §4 (L4, L6, L8), §5 (D1, D2, D4, D5, D6, D7, D8, D9), §6 |
| Lingkungan uji | keduanya |

## Tujuan

Setiap pesanan yang menimbulkan piutang punya baris tagihan bertanggal jatuh tempo di satu tempat (`payment_plans`), dan
umur piutang, kendali kredit, denda, serta proyeksi kas membaca tempat yang sama. Saldo piutang per pelanggan per PT
disimpan, bisa dibangun ulang, dan dijaga dua invarian, sehingga layar tidak lagi menghitung ulang dari 2.000 pesanan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`. PK-41 (prasyarat) sudah mengubah rumus umur piutang; cek ulang baris di `HEAD`.

| Fakta | Jangkar |
|---|---|
| Jatuh tempo seluruh sisa pesanan = surat jalan **pertama** + hari termin (temuan RP-03) | `backend/services/customer_service.py:169` (`due_context`), `backend/services/customer_service.py:200` (`order_due`) |
| Hitungan kredit membaca paling banyak 2.000 pesanan tiap dibuka dan tidak menyimpan hasilnya | `backend/services/customer_service.py:216` (`compute_customer_credit`) |
| Pesanan bertermin tunai dilewati seluruhnya oleh hitungan kredit dan umur piutang | `backend/services/customer_service.py:234` (`NON_AR_METHODS`), `backend/services/ar_aging_service.py:131` (`_eligible_outstanding`) |
| Denda untuk pesanan tanpa rencana memakai jatuh tempo lain: tanggal pesanan + termin profil | `backend/services/penalty_service.py:253` (`term_days`) |
| Taksiran denda di umur piutang dibulatkan ke bulan penuh; nota denda dihitung harian | `backend/services/ar_aging_service.py:76` (`_denda_estimate`), `backend/services/penalty_service.py:104` (`compute_amount`) |
| `payment_plans` hanya ada bila dibuat orang; mode `dp_installment` · `milestone` · `net` · `custom`; satu rencana aktif per pesanan dijaga kode, bukan indeks | `backend/services/payment_plan_service.py:45` (`MODES`), `backend/services/payment_plan_service.py:246` (`get_active`) |
| INV-PAY-01 menuntut Σ baris rencana = nilai dokumen | `backend/services/payment_plan_service.py:27` (`INV-PAY-01`), `scripts/verify_data_integrity.py:3013` (`INV-PAY-01`) |
| Baris rencana dikenali dengan `seq`; `line_id` hanya ada pada baris hasil pecah | `backend/services/payment_plan_service.py:535` (`line_id`) |
| Pembayaran dialirkan ke baris secara berurutan dari `sales_orders.payments[]`, dipanggil ulang tiap kwitansi | `backend/services/payment_plan_service.py:426` (`recompute_paid`), `backend/services/ar_receipt_service.py:605` (`recompute_for_doc`) |
| Piutang buku besar lahir **per dokumen surat jalan**: Dr akun piutang sebesar porsi nilai pesanan, untuk termin apa pun termasuk tunai | `backend/services/gl_service.py:1092` (`post_shipment_revenue`), `backend/services/gl_service.py:1124` (`ACC_PIUTANG`) |
| Satu keberangkatan bisa terdiri dari beberapa dokumen `shipments` bernomor surat jalan sama; jurnal diposting sesudah dokumen ditulis | `backend/services/shipment_service.py:98` (`shipment_no`), `backend/services/shipment_service.py:149` (`post_order_revenue_and_cogs`) |
| "Piutang ledger" dan "eksposur" sudah dipecah per pesanan dari jurnal | `backend/services/ar_aging_service.py:153` (`recognized_by_order`), `backend/services/ar_aging_service.py:172` (`split_outstanding`) |
| Pembaca jatuh tempo lain: proyeksi kas, pengingat H-x, alat asisten | `backend/services/cashflow_forecast_service.py:80` (`due_context`), `backend/services/alert_ops_service.py:287` (`orders_due_soon`), `backend/services/ai_tools.py:71` (`due_context`) |
| Titipan pelanggan disimpan di `customers.deposit_balance` dan tidak mengurangi hitungan kredit | `backend/services/customer_service.py:273` (`deposit_balance`) |

## Perubahan

### Data

`payment_plans` diperluas (tidak ada koleksi kedua, D1). Satu jadwal hidup per pesanan.

| Field baru | Di | Tipe | Arti |
|---|---|---|---|
| `origin` | jadwal | `term` · `manual` | `term` = lahir otomatis dari termin; `manual` = rencana cicilan buatan orang (yang ada sekarang) |
| `term_code`, `term_type`, `net_days`, `dp_percent` | jadwal | potret | Termin pesanan saat jadwal lahir (lapisan PT menang) |
| `billed_total` | jadwal | angka | Σ `lines[].amount` |
| `recognized_total` | jadwal | angka | Σ debit akun piutang pada jurnal pengakuan penjualan pesanan itu (cara `recognized_by_order`) |
| `line_id` | baris | string `ppl_…` | Identitas tetap; diisi untuk **semua** baris (baris lama diisi skrip) |
| `kind` | baris | tambah nilai `shipment` | Baris yang lahir dari surat jalan |
| `source_type`, `source_id` | baris | `shipment` + nomor surat jalan · `order` + id pesanan · `manual` | Asal baris; kunci idempotensi |
| `shipment_ids` | baris | daftar id | Dokumen `shipments` yang dicakup |
| `billed_at` | baris | ISO | Saat baris lahir (untuk laporan "per tanggal") |

`MODES` mendapat `term` berlabel "Mengikuti termin". Indeks: `(doc_type, doc_id)` unik parsial `status != "void"`
(H6 bila data kembar sudah ada); `lines.line_id`.

Kapan baris lahir (K-16):

| Termin pesanan | Peristiwa | Baris |
|---|---|---|
| `dp_percent == 0` (tempo, juga tunai) | Tiap **nomor** surat jalan selesai dijurnal | `kind: shipment`; `amount` = Σ debit akun piutang jurnal `shipment_revenue` semua dokumen bernomor itu; `due_date` = tanggal surat jalan (WIB) + `net_days` |
| `dp_percent > 0` (DP, bayar-dulu) | Pesanan dikonfirmasi (`confirm_core` berhasil) | `kind: dp`; `amount` = nilai pesanan × `dp_percent` ÷ 100; `due_date` = tanggal konfirmasi; label "Sebelum kirim" |
| sama, `dp_percent < 100` | Tiap nomor surat jalan dijurnal | `kind: shipment`; `amount` = nilai piutang surat jalan × (100 − `dp_percent`) ÷ 100, sisa pembulatan ke surat jalan penutup |
| Cicilan | Rencana dibuat orang (`create_plan`) | `origin: manual`; jadwal `term` di-void "diganti rencana baru"; pembuatan otomatis berhenti untuk pesanan itu |

Pesanan sample dan pesanan berstatus mati tidak diberi jadwal; pembatalan pesanan sebelum kirim meng-void jadwalnya.
Baris `shipment` ditambahkan dengan pembaruan bersyarat `lines.source_id ≠ nomor` sehingga pemanggilan ulang tidak
menggandakan. INV-PAY-01 untuk `origin: term` menjadi: Σ baris = `billed_total` ≤ nilai dokumen + toleransi, dan sama
dengan nilai dokumen bila pesanan sudah terkirim seluruhnya.

Koleksi baru `customer_balances` (awalan id `cbl_`), satu dokumen per (pelanggan, PT); indeks `(customer_id, entity_id)` unik.

| Field | Arti (rumus dari dokumen) |
|---|---|
| `ar_delivered` | Piutang atas barang terkirim belum lunas = Σ per pesanan hidup `min(sisa, max(0, recognized_total − terbayar))` |
| `open_orders_amount` | Pesanan belum dikirim = Σ per pesanan hidup `sisa − bagian terkirim di atas` |
| `overdue_amount`, `oldest_due_date`, `overdue_as_of` | Σ sisa baris ber-`due_date` < hari ini (WIB); tanggal jatuh tempo tertua yang belum lunas; tanggal hitung |
| `giro_outstanding` | Giro diterima belum cair. 0 sampai PM-T3 mengisi (kwitansi giro belum terverifikasi bank) |
| `deposit_balance`, `store_credit_balance` | Titipan dan saldo kredit belum dipakai (cermin `customers.deposit_balance` dan buku saldo kredit) |
| `penalty_outstanding` | Σ nota denda terbit − terbayar |
| `last_payment_at`, `last_payment_amount` | Kwitansi non-void terakhir |
| `rebuilt_at`, `updated_at` | Jejak |

Yang memperbarui (selalu dengan **hitung ulang penuh** satu pasangan, bukan selisih):

| Peristiwa | Pemanggil `refresh(customer_id, entity_id)` |
|---|---|
| Alokasi, pembatalan kwitansi, pemakaian titipan | Fungsi alokasi tunggal hasil PK-19, sesudah langkah efek |
| Surat jalan dijurnal; pesanan dikonfirmasi, diubah nilainya, dibatalkan | `billing_schedule_service` (di bawah) |
| Nota kredit terbit; nota denda terbit, dibayar, dibebaskan | Pembuat nota kredit (PK-32) dan `penalty_service` |
| Pergantian hari (lewat tempo berubah tanpa dokumen) | Job harian 00.10 WIB + pembaca yang menemukan `overdue_as_of` < hari ini |

Kegagalan `refresh` tidak membatalkan dokumen pemicunya; pasangan itu ditandai `stale: true` dan dibetulkan job harian.
Skrip baru `scripts/build_billing_schedule.py` (idempoten, `--dry-run`) membangun jadwal `term` untuk pesanan hidup yang
sudah ada dari surat jalan dan jurnalnya, mengisi `line_id` baris lama, lalu memanggil pembangun ulang saldo (H3).

### Server

Berkas baru `backend/services/billing_schedule_service.py`:

| Fungsi | Perilaku |
|---|---|
| `async def on_order_confirmed(order_id: str) -> Optional[dict]` | Membuat jadwal `term` + baris `dp` bila termin ber-DP |
| `async def on_shipment_posted(order_id: str, shipment_no: str) -> Optional[dict]` | Menambah baris `shipment` (idempoten), memanggil `recompute_paid`, lalu `refresh` |
| `async def on_order_changed(order_id: str) -> Optional[dict]` | Menyesuaikan baris `dp` yang belum dibayar ke nilai pesanan baru; void bila pesanan batal |
| `async def open_lines(*, entity_ids: list, customer_ids: Optional[list] = None, as_of: Optional[str] = None) -> list` | **Satu-satunya** pembaca jatuh tempo. Tiap baris: `plan_id, line_id, order_id, order_number, customer_id, entity_id, kind, amount, paid_amount, outstanding, due_date, days_late`. Dengan `as_of`: hanya baris ber-`billed_at` ≤ tanggal itu dan pembayaran bertanggal ≤ tanggal itu (RP-05) |

Berkas baru `backend/services/customer_balance_service.py`: `compute(customer_id, entity_id, today=None)` (murni dari
dokumen), `refresh(...)`, `get(...)` (menyegarkan bila basi), `rebuild_all(entity_id=None)`, `job_refresh_overdue()`.

| Endpoint | Izin | Jawaban |
|---|---|---|
| `GET /api/customers/{id}/billing-schedule?entity_id=` | `payment_plan.view` + `can_access_customer` | Baris tagihan pelanggan (terbuka dulu), berhalaman |
| `GET /api/customers/{id}/balance?entity_id=` | salah satu: `payment_plan.view`, `credit_profile.view` + `can_view_credit` | Dokumen `customer_balances` + `days_overdue` (dihitung saat baca) |
| `POST /api/ar/balances/rebuild` | `accounting.manage` | `{pairs, changed, seconds}`; PT dari `resolve_requested_entity` |

Pembaca yang dialihkan (serah-terima b):

| Pembaca | Sesudah |
|---|---|
| `ar_aging_service.aging_report`, `customer_aging_detail`, `orders_due_soon` | Kelompok umur per **baris** dari `open_lines`; nilai pesanan yang belum ditagih masuk kolom tersendiri |
| `customer_service.compute_customer_credit`, `collection_worklist` | `ar_outstanding`, `ar_ledger`, `exposure`, `overdue_amount`, `max_overdue_days`, `deposit_balance` dari `customer_balance_service.get`; bentuk jawaban tetap. Baris ber-`term_type: cash` tanpa DP **tetap dilewati** untuk status kredit (perilaku hari ini; CR-T3 yang mengubahnya) |
| `penalty_service` | Unit ini hanya menyediakan `open_lines`; pengalihan denda di CR-T4 |
| `cashflow_forecast_service.cashflow_forecast`, `ai_tools` | Uang masuk diproyeksikan pada `due_date` baris |
| `customer_service.due_context`, `order_due`, `_term_days` | Dihapus setelah pencarian membuktikan tanpa pemanggil (D8) |

Galat: `GET` pelanggan di luar cakupan → 403 "Pelanggan ini di luar cakupan Anda."; `entity_id` di luar penugasan → 403.

### Pengaturan

Tidak ada. K-16 dipakai tanpa kunci; komposisi eksposur (K-31, `ar.eksposur_*`) didaftarkan CR-T3 yang membacanya.

### Izin dan peran

Tidak ada pasangan izin baru.

### Layar

Keuangan › Piutang (`ARAgingView.jsx`): kolom kelompok umur tetap; tambah kolom **Belum dikirim** (dari
`open_orders_amount`) di kanan "Total"; catatan kaki "Umur dihitung per tagihan (surat jalan atau baris rencana), bukan
per pesanan." Rincian pelanggan (`ARAgingDetail.jsx`) menampilkan baris tagihan: "Pesanan", "Tagihan", "Jatuh tempo",
"Nilai", "Dibayar", "Sisa", "Telat (hari)"; tiap baris bisa membuka pesanan dan jurnal surat jalannya (L8). Keadaan
memuat, galat, dan kosong ("Tidak ada tagihan terbuka.") dibedakan.

## Uji penerimaan

Fixture **F1** (kasus RP-03, disisipkan ke database): PT `ent_kanda` (non-PKP, tanpa PPN); pelanggan P; pesanan S1
100 yard × Rp 10.000 = Rp 1.000.000, termin NET30 (30 hari), dikonfirmasi 25 Agu 2026; surat jalan SJ-1 berisi 40 yard
bertanggal 1 Sep 2026 dengan jurnal `shipment_revenue` Dr piutang Rp 400.000.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | F1 | `on_shipment_posted(S1, "SJ-1")` | Jadwal `origin: term` dengan 1 baris `shipment` Rp 400.000, `due_date` 2026-10-01 (1 Sep + 30 hari) |
| U2 | B | U1 | Panggil sekali lagi | Tetap 1 baris; `billed_total` 400.000 |
| U3 | B | U1 | `GET /api/ar/aging?as_of=2026-11-15` | Pelanggan P: kelompok 31–60 hari = 400.000 (15 Nov − 1 Okt = 45 hari); "Belum dikirim" = 600.000; total piutang 400.000, bukan 1.000.000 |
| U4 | B | U1 | `GET …/{P}/balance?entity_id=ent_kanda` pada 15 Nov 2026 | `ar_delivered` 400.000; `open_orders_amount` 600.000 (1.000.000 − 400.000); `overdue_amount` 400.000; `oldest_due_date` 2026-10-01 |
| U5 | B | U1 + SJ-2 berisi 60 yard, 10 Sep 2026, jurnal Rp 600.000 | `on_shipment_posted(S1, "SJ-2")` | Baris kedua Rp 600.000 jatuh tempo 2026-10-10; Σ baris 1.000.000 = nilai pesanan; `open_orders_amount` 0 |
| U6 | B | U5 | Kwitansi Rp 500.000 bertanggal 5 Okt 2026 lewat `POST /api/ar-receipts` | Baris 1 lunas (400.000), baris 2 terbayar 100.000 sisa 500.000; `ar_delivered` 500.000; per 15 Nov `overdue_amount` 500.000, `oldest_due_date` 2026-10-10; `last_payment_amount` 500.000 |
| U7 | B | Pesanan S2 Rp 2.000.000 termin DP50 (`dp_percent` 50, `net_days` 14), dikonfirmasi 3 Nov 2026 | `on_order_confirmed(S2)`; lalu surat jalan senilai Rp 800.000 bertanggal 6 Nov | Baris `dp` Rp 1.000.000 jatuh tempo 2026-11-03; baris `shipment` Rp 400.000 (800.000 × 50 %) jatuh tempo 2026-11-20 |
| U8 | B | F1 tanpa U1; rencana cicilan dibuat lewat `POST` rencana bayar | `on_shipment_posted(S1, "SJ-1")` | Jadwal `term` tidak ada/void; rencana `manual` tidak bertambah baris; umur piutang membaca baris rencana |
| U9 | B | U1 + kwitansi Rp 400.000 bertanggal 5 Nov 2026 | `GET /api/ar/aging?as_of=2026-10-31` dijalankan sesudahnya; lalu `as_of=2026-11-15` | 400.000 di kelompok 1–30 hari (31 Okt − 1 Okt = 30); lalu 0 |
| U10 | B | U1; tanggal uji 20 Okt 2026 | `GET /api/customers/{P}/credit-status` | `overdue_amount` 400.000 dan `max_overdue_days` 19 → `blocked` (19 > 14); sebelum unit ini angka telatnya 1.000.000 |
| U11 | B | U1; pelanggan Q di `ent_ksc` dengan saldo fixture Rp 250.000 | Baca saldo Q sebelum dan sesudah U1–U6; baca saldo (P, `ent_ksc`) | Saldo Q tidak berubah; saldo P di `ent_ksc` semuanya 0 — PT lain tidak ikut berubah |
| U12 | B | U4 | Ubah `customer_balances.ar_delivered` langsung menjadi 1; jalankan INV-BAL-01; `POST /api/ar/balances/rebuild`; jalankan lagi | Merah menyebut pelanggan P; lalu `changed == 1`; lalu hijau |
| U13 | B | U1 | Jalankan INV-BAL-02; sisipkan jurnal manual Dr akun piutang Rp 50.000 di `ent_kanda`; jalankan lagi | Hijau (Σ `ar_delivered` 400.000 = saldo akun piutang 400.000); lalu selisih 50.000 dilaporkan dengan sebab "jurnal tanpa pesanan" |
| U14 | B | peran uji baku | **Tanpa Acuan** + `payment_plan.view`: `GET …/billing-schedule`; **Manajer Kosong**; **Sopir** | 200; 403; 403 |
| U15 | B | U1 | Proyeksi arus kas dengan tanggal uji 20 Sep 2026 | Uang masuk Rp 400.000 pada minggu yang memuat 1 Okt 2026; Rp 600.000 tidak diproyeksikan |
| U16 | B | F1; pesanan dibatalkan sebelum SJ-1 | `on_order_changed(S1)` | Jadwal `void`; semua angka saldo P 0 |
| U17 | A | F1 dengan dua nomor surat jalan | Dua `on_shipment_posted` bersamaan | Dua baris, tanpa kembar; satu jadwal hidup (indeks unik menolak yang kedua) |
| U18 | layar (uji jalan) | Data acuan + U1 lewat alur gudang nyata | Buka Keuangan › Piutang › pelanggan P | Kolom "Belum dikirim" terisi; rincian menampilkan baris tagihan dan tautan ke jurnal |

## Langkah kerja

**Serah-terima (a) — jalur baru, jalur lama belum disentuh.**

1. `backend/tests_mem/test_CRT2_jadwal_saldo.py`: U1, U2, U4–U8, U11–U14, U16 terhadap fungsi baru; merah.
2. Field dan indeks; `billing_schedule_service`; kait di `confirm_core` dan sesudah jurnal surat jalan (kegagalan kait
   ditulis ke `shipments.billing_status: failed` dan didaftarkan di `routers/posting_failures.py` `SOURCES`).
3. `customer_balances`, `customer_balance_service`, job harian, endpoint baca dan bangun ulang.
4. INV-PAY-01 disesuaikan; INV-BAL-01 dan INV-BAL-02 ditambahkan sebagai lapisan baru `verify_data_integrity.py`.
5. Skrip `build_billing_schedule.py`; dijalankan pada data acuan; laporan memuat selisih lama vs baru per pelanggan.

**Serah-terima (b) — alihkan pembaca, matikan jalur lama.**

6. U3, U9, U10, U15 ditulis terhadap endpoint lama; merah.
7. Alihkan pembaca menurut tabel; hapus `due_context`, `order_due`, `_term_days`; layar.
8. U17 di lingkungan A; U18; gate penuh; laporan memuat contoh angka F1: dokumen → jurnal → saldo tersimpan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`payment_plans` field baru; `customer_balances`), `CODEBASE_MAP.md` (dua layanan dan satu skrip
baru), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("baris tagihan", "jadwal tagihan", "belum dikirim").

## Di luar lingkup

- Komposisi eksposur, gerbang, tunai ikut dihitung kredit → CR-T3. Denda dari jadwal → CR-T4.
- Kartu pelanggan, rekening koran, daftar kerja → CR-T5. Kode bayar per baris tagihan → PM-T2. Giro belum cair → PM-T3.
- Saldo hutang tersimpan per pemasok (`06` §5): belum ada unitnya.

## Asumsi dan risiko

- `ASUMSI:` pesanan bertermin tunai tanpa DP ikut diberi baris tagihan per surat jalan (`net_days` 0). Rancangan hanya
  menyebut "non-tunai", tetapi jurnal surat jalan mendebit akun piutang untuk termin apa pun, sehingga tanpa baris ini
  INV-BAL-02 tidak mungkin hijau.
- `ASUMSI:` nilai baris `shipment` diambil dari jurnal, bukan dihitung ulang dari harga, supaya selalu sama dengan buku
  besar. Surat jalan yang jurnalnya gagal belum punya baris sampai jurnalnya diulang.
- `ASUMSI:` selisih INV-BAL-02 yang dianggap terjelaskan memakai daftar sebab hasil PK-41 (jurnal tanpa pesanan, kasus
  keuangan, jalur lama per pesanan). Sebab lain = merah.
- `RISIKO:` jumlah pelanggan terblokir berubah saat pembaca dialihkan (umumnya berkurang, karena bagian belum dikirim
  tidak lagi dianggap telat). Laporan serah-terima (a) memuat daftar pelanggan yang statusnya akan berubah; pemilik
  melihatnya sebelum (b) dipasang ke PT nyata (H3). Membatalkan (b): kembalikan pembaca ke fungsi lama — jadwal dan
  saldo tersimpan tidak dibaca jalur lama, jadi aman dibiarkan.
