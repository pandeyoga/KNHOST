# PM-T1 — Satu daftar induk cara bayar, dan rekening yang punya atas nama, peruntukan, dan bawaan per PT

| | |
|---|---|
| Gelombang | Modul cara bayar dan rekening |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | KF-T1 |
| Menutup temuan | PM-03, PM-05 |
| Keputusan | K-34, K-35 |
| Standar | §2.3, §3.1 (Z1–Z3, Z4, Z6), §3.2, §3.4 (N1, N2, N4, N5), §4 (L1, L2, L4, L7), §5 (D1, D7, D8, D9), §6 |
| Lingkungan uji | keduanya (B; A untuk indeks unik) |

## Tujuan

Setiap layar yang menanyakan "dibayar lewat apa" menawarkan daftar yang sama, dikelola di satu master dan bisa
dimatikan per PT. Rekening bank menyimpan atas nama, peruntukan, cara bayar yang dilayani, dan mana yang bawaan untuk
menerima uang pelanggan — bahan untuk instruksi bayar (PM-T2) dan kwitansi ber-rekening (PM-T3).

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

Kosakata cara bayar yang hidup sekarang, per tempat:

| Tempat | Nilai yang dipakai | Jangkar |
|---|---|---|
| Kwitansi pelanggan (desktop dan HP) | `transfer` · `cash` · `giro` · `qris` | `frontend/src/features/crm/ARReceiptModal.jsx:28` (`METHODS`) |
| Server kwitansi | teks bebas, bawaan `transfer`; tunai dikenali dari `cash` · `tunai` · `kontan` | `backend/services/ar_receipt_service.py:439` (`method`), `backend/services/ar_receipt_service.py:44` (`CASH_METHODS`) |
| Bayar tagihan pemasok | `transfer` · `tunai` · `giro` | `frontend/src/features/purchasing/VendorBillDetailPanel.jsx:190` (`tunai`) |
| Bayar voucher biaya masuk | `transfer` · `tunai` · `giro` | `frontend/src/features/purchasing/LandedCostDetailPanel.jsx:171` (`tunai`) |
| Bayar kontrabon | `transfer` · `giro` · `cash` | `frontend/src/features/purchasing/contrabon/contraBonApi.js:34` (`transfer`) |
| Pencairan uang muka karyawan | `tunai` · `transfer` | `frontend/src/features/pettycash/CashAdvanceForm.jsx:146` (`tunai`) |
| Keputusan selisih bayar (pengembalian) | `transfer` · `cash` | `frontend/src/features/finance/payments/PaymentVarianceDialog.jsx:37` (`transfer`), `backend/config_catalog_payment.py:222` (`payment.variance_refund_method`) |
| Pelunasan antar-PT | `transfer` · `cash` | `frontend/src/features/finance/interco/intercoApi.js:63` (`transfer`) |
| Bayar denda (jurnal) | `tunai` · `cash` → kas kecil; lainnya kas besar | `backend/services/gl_service.py:2040` (`cash_acc`) |
| Keputusan selisih bayar (server) | `cash` · `tunai` · `kontan` | `backend/services/payment_variance_service.py:588` (`tunai`) |

Bukan cara bayar, tetapi sering tertukar (kosakata **termin**, tidak diubah unit ini): profil bayar pelanggan
`tunai` · `tempo` · `dp` · `bertahap` · `kontan` (`frontend/src/features/crm/crmUtils.jsx:58` (`PAYMENT_METHODS`);
`backend/schemas_crm.py:22` (`allowed_methods`)) dan jenis termin `cash` · `credit` · `dp` · `installment`
(`backend/services/config_service.py:149` (`DEFAULT_PAYMENT_TERMS`)).

Rekening:

| Fakta | Jangkar |
|---|---|
| Master rekening hanya punya nama, jenis, bank, nomor, PT, saldo awal, catatan | `backend/schemas_finance.py:9` (`BankAccountCreate`) |
| Rekening dibuat dengan `is_active: True`, tetapi pencari "rekening satu-satunya" menyaring field `status` yang tidak pernah diisi — rekening nonaktif ikut terhitung | `backend/services/bank_service.py:177` (`is_active`), `backend/services/bank_service.py:55` (`status`) |
| Membuat dan mengubah rekening cukup izin `cash.create`, langsung berlaku | `backend/routers/bank.py:49` (`create_bank_account`), `backend/routers/bank.py:68` (`patch_bank_account`) |
| Master berlapis global → PT sudah ada dan dipakai termin | `backend/services/entity_master_service.py:59` (`MASTERS`), `backend/services/entity_master_service.py:228` (`WRITE_PERMISSION`) |
| Membaca baris efektif master butuh `settings.view` — Sales tidak memegangnya | `backend/routers/entity_masters.py:46` (`list_master_effective`) |

## Perubahan

### Data

**Cara bayar = master berlapis baru** `payment-methods` di `MASTERS` (koleksi `payment_methods`, awalan id `pmeth`,
kunci `code`). Dipilih master berlapis, bukan konstanta atau kunci pengaturan, karena daftar ini harus bisa dimatikan
per PT dengan mekanisme "Buat khusus PT" yang sudah ada.

| Field | Tipe | Arti |
|---|---|---|
| `code`, `name` | string | Kode kanonik huruf kecil; nama untuk layar |
| `needs_account` | `bank` · `kas` · `tidak` | Jenis rekening yang wajib dipilih |
| `needs_reference`, `needs_due_date` | bool | Butuh nomor referensi; butuh tanggal jatuh tempo (giro). Ditegakkan PM-T3 |
| `is_new_money` | bool | `false` untuk pemakaian titipan |
| `directions` | daftar `masuk` · `keluar` | Dipakai di penerimaan, pembayaran, atau keduanya |
| `aliases` | daftar string | Kata lama yang dipetakan ke kode ini |
| `sort`, `active`, `notes` | — | Seperti master lain |

Benih (baris global `entity_id: "all"`):

| `code` | `name` | `needs_account` | Referensi | Arah | Aktif | `aliases` |
|---|---|---|---|---|---|---|
| `transfer` | Transfer bank | `bank` | ya | masuk, keluar | ya | — |
| `cash` | Tunai | `kas` | tidak | masuk, keluar | ya | `tunai`, `kontan` |
| `giro` | Giro / cek | `bank` | ya + jatuh tempo | masuk, keluar | ya | `cek` |
| `qris` | QRIS | `bank` | ya | masuk | ya | — |
| `va` | Virtual account | `bank` | ya | masuk | tidak (PM-T5) | — |
| `edc` | Kartu / EDC | `bank` | ya | masuk | tidak | `kartu` |
| `deposit` | Titipan / saldo kredit | `tidak` | tidak | masuk | ya; `is_new_money: false` | `titipan` |

Dokumen lama tidak ditulis ulang; nilainya dibaca lewat `normalize`.

**`bank_accounts`** — field baru:

| Field | Tipe | Aturan dan nilai untuk rekening yang sudah ada |
|---|---|---|
| `holder_name` | string | Atas nama. Awal `""` |
| `purposes` | daftar: `penerimaan_pelanggan` · `pembayaran_pemasok` · `gaji` · `operasional` | Awal keempatnya (sama dengan hari ini: rekening boleh dipakai apa saja) |
| `payment_method_codes` | daftar kode cara bayar | Awal: rekening bank `["transfer", "giro", "qris"]`; kas `["cash"]` |
| `default_receiving_methods` | daftar kode | Rekening ini bawaan penerimaan PT-nya untuk cara bayar itu. Awal: `["transfer"]` atau `["cash"]` **hanya** bila ia satu-satunya rekening aktif PT untuk jenisnya; selain itu `[]` |
| `show_on_documents` | bool | Awal `false`. `true` menuntut `holder_name` dan `account_number` terisi dan jenis `bank` |

Indeks: `(entity_id, default_receiving_methods)` unik parsial `{"default_receiving_methods.0": {"$exists": true}}` — satu
bawaan per (PT, cara bayar). Pengisian awal dijalankan fungsi idempoten saat server menyala (pola `backfill_cash_type`).

Koleksi baru `bank_account_changes` (awalan id `bac_`): `entity_id`, `account_id` (`""` untuk rekening baru), `action`
(`buat` · `ubah`), `changes[] {field, from, to}`, `payload`, `reason`, `status` (`menunggu` · `diterapkan` · `ditolak`),
`requested_by(_id)`, `decided_by(_id)`, `created_at`, `decided_at`. Indeks `(entity_id, status, created_at)`.

### Server

Berkas baru `backend/services/payment_method_service.py`:

| Fungsi | Perilaku |
|---|---|
| `def normalize(value: str) -> str` | Kode kanonik dari kode atau alias (huruf besar-kecil diabaikan); tak dikenal → `ValueError` |
| `async def get(entity_id: str, code: str) -> dict` | Baris efektif PT itu (`resolve_row`); nonaktif → `None` |
| `async def active_for(entity_id: str, direction: str) -> list` | Daftar aktif menurut arah, terurut `sort` |
| `async def is_cash(entity_id: str, code: str) -> bool` | `needs_account == "kas"`; pengganti semua himpunan `{"cash", "tunai", "kontan"}` |

Pemakaian: setiap endpoint yang menerima cara bayar (kwitansi, bayar tagihan pemasok, kontrabon, voucher biaya masuk,
pencairan uang muka, bayar denda, keputusan selisih bayar, pelunasan antar-PT) memanggil `normalize` lalu `get`
sebelum menulis apa pun, dan menyimpan kode kanonik. Empat himpunan dan cabang di tabel "Keadaan sekarang" bagian server
diganti `is_cash`. Pilihan `payment.variance_refund_method` tetap dua nilai yang ada.

| Endpoint | Izin | Isi / jawaban |
|---|---|---|
| `GET /api/payment-methods?direction=&entity_id=` | login saja (data rujukan tanpa nominal, Z3) | `[{code, name, needs_account, needs_reference, needs_due_date}]` aktif untuk PT itu |
| `GET /api/bank-accounts/receiving?entity_id=&method=` | salah satu: `order.create`, `ar_receipt.create`, `cash.view` | Rekening aktif PT itu yang ber-`purposes` memuat `penerimaan_pelanggan` dan melayani `method`: `[{id, name, bank_name, account_number, holder_name, is_default}]` — tanpa saldo |
| `POST /api/bank-accounts`, `PATCH /api/bank-accounts/{id}` | `cash.create` (tetap) | Menerima field baru. Bila perubahan menyentuh field peka dan `butuh_orang_kedua("ubah_rekening", entity_id, 0)`: tidak diterapkan, jawaban 202 `{change}` berstatus `menunggu`. Selain itu diterapkan dan dicatat `diterapkan` |
| `GET /api/bank-account-changes?status=` | `cash.view` | Daftar berhalaman per PT |
| `POST /api/bank-account-changes/{id}/decision` | `cash.approve` | `{decision: "approve"\|"reject", note}`; `tolak_bila_pelaku_sama("ubah_rekening", …)`; menerapkan perubahan dengan syarat nilai `from` masih sama |
| `POST/PATCH /api/entity-masters/payment-methods…` | `cash.configure` (lewat `WRITE_PERMISSION`) | Seperti master lain |

Field peka: `account_number`, `bank_name`, `holder_name`, `purposes`, `payment_method_codes`,
`default_receiving_methods`, `show_on_documents`, `is_active`, dan pembuatan rekening. Menjadikan satu rekening bawaan
mencabut tanda bawaan cara bayar itu dari rekening lain PT yang sama dalam operasi yang sama.

`sole_account_id` menyaring `{"is_active": {"$ne": False}}`. PT selalu lewat `resolve_requested_entity`; rekening
ber-id diadu dengan `guard_doc`. Awalan `/api/bank-accounts` dan `/api/bank-account-changes` masuk `IDEMPOTENT_PREFIXES`.

Galat:

| Keadaan | Kode | Pesan |
|---|---|---|
| Cara bayar tak dikenal | 400 | "Cara bayar tidak dikenal: {nilai}." |
| Cara bayar nonaktif di PT itu | 400 | "Cara bayar {nama} tidak aktif untuk PT ini." |
| `show_on_documents` tanpa atas nama/nomor | 400 | "Rekening yang tampil di dokumen wajib punya atas nama dan nomor rekening." |
| Kode cara bayar di rekening tidak dikenal, atau bawaan untuk cara bayar yang tidak dilayani | 400 | "Rekening ini tidak melayani cara bayar {nama}." |
| Perubahan sudah diputus / nilai sudah berubah | 409 | "Perubahan rekening ini sudah diputus atau datanya sudah berubah. Ajukan ulang." |

Penjaga baru `scripts/guardrails/verify_payment_vocab.py` (pola `scripts/guardrails/verify_uom_vocab.py`, punya
`--self-test`, didaftarkan di `scripts/gate.sh`): merah bila ada berkas layar yang menulis pilihan cara bayar sendiri
(`value: "transfer" | "cash" | "tunai" | "giro" | "qris" | "kontan"` dalam daftar pilihan) di luar berkas baru
`frontend/src/config/paymentMethods.js`, atau berkas server yang menulis himpunan kata itu di luar
`payment_method_service`. Daftar pengecualian tertulis di penjaga: kosakata termin (tiga tempat di atas), kategori kas
"Transfer / Top-up", dan jenis pengembalian retur.

### Pengaturan

Tidak ada kunci baru di luar keluarga kontrol: aksi `ubah_rekening` ditambahkan unit ini ke `KONTROL_AKSI` (katalog
kontrol hasil KF-T6) — label "Ubah rekening kas/bank", kelompok C, awal "1", tanpa nominal.

### Izin dan peran

| Pasangan | Arti di layar | Peran bawaan | Modul · menu |
|---|---|---|---|
| `cash.approve` | Menyetujui perubahan rekening | admin, manager | `finance_ops` · `bank-accounts` |
| `cash.configure` | Mengelola daftar cara bayar | admin, manager | `finance_ops` · `settings-finance` |

### Layar

- **Keuangan › Kas & Bank › Rekening & Saldo** (`BankAccountsView.jsx`): form rekening mendapat isian "Atas nama",
  "Dipakai untuk" (centang: Penerimaan pelanggan · Pembayaran pemasok · Gaji · Operasional), "Cara bayar yang dilayani"
  (centang dari master), "Jadikan bawaan penerimaan untuk" (centang, hanya dari yang dilayani), sakelar "Tampilkan di
  dokumen pelanggan". Kartu rekening menulis atas nama dan lencana "Bawaan: {cara bayar}". Saat perubahan butuh orang
  kedua: pemberitahuan "Perubahan disimpan sebagai pengajuan dan berlaku setelah disetujui orang lain."; bagian
  "Perubahan menunggu persetujuan" dengan tombol **Setujui** / **Tolak** (`cash.approve`); konfirmasi menyebut nama
  rekening, PT, dan nilai lama → baru (N5).
- **Pengaturan › Keuangan & Pajak**: master "Cara Bayar" tampil di daftar master berlapis yang ada.
- Semua layar di tabel kosakata mengambil pilihan dari `usePaymentMethods(arah)` (hook baru di
  `frontend/src/config/paymentMethods.js`) dan mengirim kode kanonik; label mengikuti `name` master.

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | benih | `sls`: `GET /api/payment-methods?direction=masuk` di `ent_ksc` | 200; kode `transfer, cash, giro, qris, deposit` (tanpa `va`, `edc`) |
| U2 | B | `adm` membuat baris khusus `ent_kanda` untuk `qris` dengan `active: false` | `GET` yang sama untuk `ent_kanda` lalu `ent_ksc` | `ent_kanda` tanpa `qris`; `ent_ksc` tetap memuatnya — PT lain tidak berubah |
| U3 | B | pelanggan dengan tagihan terbuka | Kwitansi `method: "tunai"`; `"kontan"`; `"bitcoin"` | Dua pertama tersimpan `cash`; ketiga 400 "Cara bayar tidak dikenal: bitcoin." tanpa kwitansi |
| U4 | B | U2 | Kwitansi `method: "qris"` di `ent_kanda` | 400 "Cara bayar QRIS tidak aktif untuk PT ini." |
| U5 | B | PT dengan dua rekening bank, satu ber-`is_active: false` | `sole_account_id(PT, "kas_besar")` | Id rekening yang aktif (sebelum unit ini `""`) |
| U6 | B | — | `POST /api/bank-accounts` dengan `show_on_documents: true` tanpa `holder_name` | 400 dengan pesan atas nama; tidak ada rekening baru |
| U7 | B | Rekening A dan B di `ent_ksc`, keduanya melayani `transfer`; A bawaan `transfer` | `PATCH` B `default_receiving_methods: ["transfer"]`; `GET …/receiving?method=transfer` | B `is_default: true`, A `false`; tepat satu bawaan |
| U8 | B | Rekening milik `ent_kanda` | `sls` (hanya `ent_ksc`): `GET …/receiving?entity_id=ent_ksc&method=transfer`; lalu `entity_id=ent_kanda` | Daftar tidak memuat rekening `ent_kanda`; permintaan kedua 403 |
| U9 | B | `kontrol.ubah_rekening.min_orang` = 2 pada `ent_ksc` | `mgr`: `PATCH` nomor rekening A; `mgr` memutus; `adm` menyetujui | 202 dan nomor belum berubah; 403; 200 dan nomor berubah |
| U10 | B | seperti U9 | `mgr`: `PATCH` rekening `ent_kanda` (nomor); `mgr`: `PATCH` `name` rekening A | 200 langsung berlaku + satu catatan `diterapkan`; 200 langsung (bukan field peka) |
| U11 | B | fixture rekening lama tanpa field baru: satu bank tunggal, dua kas | Jalankan pengisian awal dua kali | Bank: empat peruntukan, tiga cara bayar, bawaan `["transfer"]`; dua kas: bawaan `[]`; putaran kedua tanpa perubahan |
| U12 | B | peran uji baku | **Tanpa Acuan** + `cash.approve`: putus perubahan; + `cash.configure`: tambah baris master; **Manajer Kosong** dan **Sopir**: keduanya | 200; 200; 403; 403 |
| U13 | B | — | `verify_payment_vocab.py --self-test`; lalu penjaga pada repo | Contoh pelanggar memerah; repo hijau |
| U14 | A | Rekening A dan B | Dua `PATCH` bersamaan menjadikan masing-masing bawaan `transfer` | Tepat satu rekening bawaan; tidak ada galat 500 |
| U15 | layar (uji jalan) | U2 | Buka form kwitansi, bayar tagihan pemasok, dan kontrabon di `ent_kanda` dan `ent_ksc` | Pilihan dan label sama di ketiga form; QRIS tidak ada di `ent_kanda` |

## Langkah kerja

1. `backend/tests_mem/test_PMT1_cara_bayar.py`: U1–U12; merah.
2. Master + benih + `payment_method_service` + `GET /api/payment-methods`. U1, U2 hijau.
3. `normalize`/`get` di tiap endpoint penerima cara bayar; ganti himpunan tunai. U3, U4 hijau.
4. Field rekening, pengisian awal, indeks, perbaikan `sole_account_id`, daftar rekening penerima. U5–U8, U11 hijau.
5. `bank_account_changes` + kontrol dua orang + dua pasangan izin (§3.2). U9, U10, U12 hijau.
6. `paymentMethods.js`, pengalihan layar, penjaga + gate. U13; U14 di lingkungan A; U15; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`payment_methods`, `bank_account_changes`, field `bank_accounts`), `CODEBASE_MAP.md`
(`services/payment_method_service.py`, penjaga baru), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`
("cara bayar" ≠ "termin"; "atas nama"; "peruntukan").

## Di luar lingkup

- Cara bayar dan rekening tujuan di pesanan, instruksi bayar → PM-T2. Rekening dan referensi wajib di kwitansi → PM-T3.
- Satu akun buku besar per rekening (`07` §A3.2): mengubah bagan akun, belum ada unitnya; kas tetap dua akun.
- Rekening pemasok terdaftar dan persetujuan perubahannya (`07` §A3.9): belum ada unitnya.
- Menyatukan kosakata termin (`tunai/tempo/dp/bertahap/kontan` vs `cash/credit/dp/installment`): belum ada unitnya.

## Asumsi dan risiko

- `ASUMSI:` kode kanonik mengikuti nilai yang paling banyak tersimpan hari ini (`cash`, bukan `tunai`) supaya data lama
  tidak perlu ditulis ulang.
- `ASUMSI:` rekening lama diberi keempat peruntukan dan cara bayar menurut jenisnya, supaya tidak ada yang tiba-tiba
  tidak bisa dipakai; pemilik mempersempitnya lewat layar (`01` §C).
- `ASUMSI:` nominal untuk `butuh_orang_kedua("ubah_rekening", …)` selalu 0 (perubahan rekening tidak bernilai uang).
- `ASUMSI:` KF-T6 bukan prasyarat di indeks. Bila `services/dual_control.py` belum ada, perubahan rekening langsung
  diterapkan dan dicatat `diterapkan` (sama dengan bawaan satu orang); U9 ditunda dan dicatat sebagai sisa pekerjaan.
- `RISIKO:` endpoint lama yang menerima kata tak dikenal kini menolak (400). Kata lama yang sah sudah menjadi alias;
  laporan memuat kueri nilai `method` berbeda yang tersimpan di tiap koleksi supaya alias yang kurang terlihat.
  Membatalkan: kembalikan `normalize` menjadi peneruskan nilai apa adanya.
