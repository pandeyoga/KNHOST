# PM-T4 — Tunai yang diterima sales dicatat sebagai titipan sampai disetor

| | |
|---|---|
| Gelombang | Modul cara bayar dan rekening |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PM-T3 |
| Menutup temuan | PM-06 |
| Keputusan | K-36 |
| Standar | §1 (kontrak posting; P1–P5, P9, P10), §2 (2.1, 2.2, 2.4), §3.1 (Z1–Z3), §3.2, §3.4 (N1, N2, N4, N5), §4 (L1, L3, L4), §5 (D2, D7, D9), §6 |
| Lingkungan uji | keduanya |

Titik henti **H5**: unit selesai dengan bawaan `kas_langsung` (= perilaku hari ini). Mengubah pengaturan menjadi
`titipan` atau `dilarang` untuk PT nyata adalah keputusan pemilik (tulis pertanyaannya di `STATUS.md`).

## Tujuan

Bila PT memilihnya, uang tunai yang diterima sales di lapangan tidak lagi tercatat sebagai kas kantor. Piutang
pelanggan tetap turun dan pelanggan tetap menerima kwitansi bernomor, tetapi uangnya tercatat sebagai titipan di tangan
sales itu sampai kasir atau Finance menerima setorannya.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| Fakta | Jangkar |
|---|---|
| Sales boleh mencatat kwitansi: izinnya ditambahkan saat server menyala walau daftar izin bawaan hanya `view` (K-36: dipertahankan) | `backend/bootstrap.py:460` (`GRANT`), `backend/permissions_config.py:142` (`ar_receipt`) |
| HP sales memakai form kwitansi yang sama dengan desktop | `frontend/src/features/sales/mobile/MobileArReceipt.jsx:14` (`MobileArReceipt`) |
| Kwitansi tunai langsung menjadi kas kecil PT, siapa pun pencatatnya | `backend/services/ar_receipt_service.py:66` (`CASH_METHODS`), `backend/services/ar_receipt_service.py:71` (`_post_cash_in`) |
| Form memberi tahu "tunai → kas kecil" | `frontend/src/features/crm/ARReceiptModal.jsx:190` (`cashHint`) |
| Akun "Piutang Titipan Karyawan" sudah ada dan terpetakan | `backend/services/gl_service.py:161` (`ACC_PIUTANG_KARYAWAN`), `backend/services/gl_mapping_registry.py:48` (`kas_bank.piutang_karyawan`) |
| Pasangan jurnal yang sama sudah dipakai Kasus Keuangan: Dr piutang karyawan / Cr piutang saat uang diakui dipegang karyawan; kas masuk berakun lawan piutang karyawan saat disetor | `backend/services/finance_case_actions.py:327` (`ACC_PIUTANG_KARYAWAN`), `backend/services/finance_case_actions.py:360` (`contra`) |
| Hub Kas & Bank punya tiga tab | `frontend/src/config/hubTabs.js:159` (`cash-bank`) |
| Jenis dokumen yang jurnalnya bisa gagal didaftar di satu tempat | `backend/routers/posting_failures.py:17` (`SOURCES`) |

## Perubahan

### Data

Koleksi baru `cash_holdings` (awalan id `cth_`, nomor `TTP-` per PT) — satu per kwitansi tunai yang menjadi titipan:

| Field | Arti |
|---|---|
| `entity_id`, `number` | PT dari kwitansi |
| `holder_user_id`, `holder_name` | Pencatat kwitansi = pemegang uang |
| `receipt_id`, `receipt_number`, `customer_id`, `customer_name` | Asal uang |
| `amount`, `deposited_amount` | Diterima; sudah disetor (diubah dengan pembaruan bersyarat) |
| `status` | `dipegang` · `sebagian_disetor` · `disetor` · `batal` |
| `received_at`, `due_at` | Waktu terima; batas setor (`""` bila PT tanpa tenggat) |
| `gl_status`, `gl_error`, `je_id` | Hasil jurnal (P3) |

Indeks: `receipt_id` unik; `(entity_id, holder_user_id, status)`.

Koleksi baru `cash_deposits` (awalan id `cdp_`, nomor `STR-` per PT) — setoran: `entity_id`, `holder_user_id`,
`holder_name`, `amount`, `allocations[] {holding_id, amount}`, `note`, `status` (`diajukan` · `diterima` · `ditolak` ·
`dibatalkan`), `bank_account_id`, `received_by(_id)`, `received_at`, `cash_txn_id`, `gl_status`. Indeks
`(entity_id, status, created_at)`.

`ar_receipts` — field baru `cash_holding_id`. Kedua koleksi didaftarkan sebagai koleksi ber-PT di `entity_scope`.

### Server

**Kapan kwitansi menjadi titipan.** Di `create_receipt`, setelah langkah PERIKSA PM-T3: bila cara bayar
ber-`needs_account: kas`, ada uang baru, dan pencatat **tidak** memegang izin `cash.create` (bukan pemegang kas), baca
`pembayaran.sales_terima_tunai` PT kwitansi:

| Nilai | Perilaku |
|---|---|
| `kas_langsung` | Seperti hari ini: kas masuk ke rekening kas |
| `titipan` | Periksa batas (di bawah). Alokasi ke pesanan berjalan lewat fungsi alokasi tunggal (PK-19) seperti biasa. **Tidak ada** transaksi kas. Dibuat `cash_holdings` dan jurnal titipan |
| `dilarang` | 403 |

Pemegang `cash.create` (kasir, Finance) selalu `kas_langsung`.

Jurnal — dua-duanya lewat `gl_service`, akun dari pemetaan (P9), arah mengikuti pasangan yang sudah dipakai Kasus Keuangan:

| Peristiwa | Debit | Kredit | Kunci jurnal |
|---|---|---|---|
| Kwitansi tunai menjadi titipan | `kas_bank.piutang_karyawan` sebesar `amount` | Sama dengan sisi kredit jurnal kas kwitansi biasa (piutang untuk bagian yang sudah diakui, uang muka pelanggan untuk sisanya) — dihitung fungsi yang sama | `source_type: cash_holding`, `source_id` = id titipan |
| Setoran diterima | Kas/bank rekening yang dipilih penerima (transaksi kas lewat pembuat tunggal PK-20) | `kas_bank.piutang_karyawan` (akun lawan transaksi kas) | Kunci transaksi kas; `ref_type: cash_deposit` |

Fungsi baru `gl_service.post_cash_holding(holding)` dan pembaliknya; `cash_holding` dan `cash_deposit` masuk `SOURCES`
panel posting gagal dengan jalur ulang.

Menerima setoran mengikuti urutan `02` §1: PERIKSA (izin, PT, status `diajukan`, periode terbuka, rekening milik PT
dan aktif, penerima ≠ pemegang) → NIAT (setoran ditandai sedang diterima dengan id tetap) → EFEK (`deposited_amount`
tiap titipan naik dengan syarat tidak melewati `amount`) → JURNAL (kas tahan-gagal) → SELESAI (`diterima`).

| Endpoint | Izin | Isi | Jawaban / catatan |
|---|---|---|---|
| `POST /api/ar-receipts` | tetap | tetap | Tambah `cash_holding` bila menjadi titipan |
| `GET /api/cash-holdings?status=&holder_user_id=&overdue=` | `cash_holding.view` | — | Berhalaman, per PT. Tanpa `cash_holding.approve`, hanya titipan milik sendiri |
| `GET /api/cash-holdings/me/summary` | login (milik sendiri, Z3) | — | `{held_total, count, oldest_due_at, limit}` |
| `POST /api/cash-deposits` | `cash_holding.create` | `{amount, holding_ids?, note}` | Setoran `diajukan`; tanpa `holding_ids`, dialokasikan ke titipan tertua lebih dulu |
| `POST /api/cash-deposits/{id}/receive` | `cash_holding.approve` | `{bank_account_id}` | Setoran `diterima` + transaksi kas |
| `POST /api/cash-deposits/{id}/reject` · `/cancel` | `cash_holding.approve` · penyetor sendiri | `{reason}` | `ditolak` · `dibatalkan`; titipan tidak berubah |

Pembatalan kwitansi ber-titipan: bila `deposited_amount == 0` → titipan `batal` + jurnal pembalik; selain itu 409.
Awalan `/api/cash-deposits` masuk `IDEMPOTENT_PREFIXES`. Invarian baru INV-TTP-01 di `verify_data_integrity.py`: per
PT, Σ (`amount` − `deposited_amount`) titipan non-batal = Σ debit jurnal `cash_holding` − Σ kredit akun piutang
karyawan dari kas ber-`ref_type: cash_deposit` (D2).

Galat:

| Keadaan | Kode | Pesan |
|---|---|---|
| PT melarang | 403 | "PT ini tidak mengizinkan sales menerima tunai. Minta pelanggan transfer atau bayar ke kasir." |
| Melewati batas titipan | 409 | "Titipan tunai Anda Rp {dipegang} sudah mencapai batas Rp {batas}. Setor dulu sebelum menerima tunai lagi." |
| Setoran melebihi titipan yang dipegang | 400 | "Setoran melebihi tunai yang Anda pegang (Rp {dipegang})." |
| Penerima = pemegang | 403 | "Setoran tidak bisa diterima oleh pemegang titipannya sendiri." |
| Setoran sudah diputus | 409 | "Setoran ini sudah diterima, ditolak, atau dibatalkan." |
| Batal kwitansi yang titipannya sudah disetor | 409 | "Titipan kwitansi ini sudah disetor. Batalkan penerimaan setorannya dulu." |

### Pengaturan

Group `uang-masuk`, scopes `("global", "entity")`, permission `("cash", "configure")`, consumers
`services/ar_receipt_service.py:create_receipt`. Awalan `pembayaran.` menyimpang dari `02` §2.1 (domain yang ada adalah
`payment`) karena `01_KEPUTUSAN.md` K-36 menyebut nama kunci ini.

| Field | `pembayaran.sales_terima_tunai` | `pembayaran.titipan_batas_nominal` | `pembayaran.titipan_tenggat_setor_hari` |
|---|---|---|---|
| type · default | `enum` `kas_langsung` · `titipan` · `dilarang`; bawaan `kas_langsung` | `money` · 0 (min 0, max 1.000.000.000, Rp) | `int` · 0 (min 0, max 30, hari) |
| label | "Tunai yang diterima sales dicatat sebagai" | "Batas tunai yang boleh dipegang satu sales" | "Tunai harus disetor dalam (hari)" |
| help | "'Kas langsung' = seperti sekarang. 'Titipan' = uang dianggap masih di tangan sales sampai disetor. 'Dilarang' = sales tidak bisa mencatat tunai." | "Jumlah titipan belum disetor per orang. 0 = tanpa batas." | "Titipan lebih lama dari ini bertanda lewat tenggat. 0 = tanpa tenggat." |
| impact | "'Titipan' membuat kas kantor tidak bertambah sampai setoran diterima." | "Sales yang mencapai batas tidak bisa menerima tunai lagi sebelum menyetor." | "Hanya menandai; tidak menolak apa pun." |
| example | "Titipan · sales terima Rp 300.000 → kas tetap, titipan Rp 300.000" | "Rp 5.000.000 · sudah pegang Rp 4,8 jt, terima Rp 300 rb → ditolak" | "1 · diterima Senin, belum disetor Rabu → lewat tenggat" |
| risk / requires_reason | `high` / ya | `medium` / tidak | `low` / tidak |

### Izin dan peran

Sumber daya baru `cash_holding`, modul akses `finance_ops`; id menu `cash-bank`, `cash-holdings`.

| Pasangan | Arti di layar | Peran bawaan |
|---|---|---|
| `cash_holding.view` | Melihat titipan tunai (milik sendiri; semua bila juga memegang `approve`) | admin, manager, finance, sales, sales_admin |
| `cash_holding.create` | Mengajukan setoran | admin, manager, sales |
| `cash_holding.approve` | Menerima atau menolak setoran | admin, manager, finance |

### Layar

- **Form kwitansi** (`ARReceiptModal.jsx`): teks bantu tunai mengikuti pengaturan — `titipan`: "Uang tunai ini dicatat
  sebagai titipan di tangan Anda sampai disetor ke kasir atau bank."; `dilarang`: pilihan "Tunai" tidak ditawarkan.
- **HP sales**: kartu "Titipan Saya" (total dipegang, jumlah kwitansi, batas, tenggat terdekat) dengan tombol **Setor**
  → pop-up "Jumlah disetor" (terisi total), "Catatan" → pemberitahuan "Setoran diajukan. Serahkan uangnya ke kasir."
- **Keuangan › Kas & Bank › tab baru "Titipan Sales"** (view `cash-holdings`; hub menjadi empat tab): bagian "Setoran
  menunggu diterima" (penyetor, jumlah, umur) dengan tombol **Terima setoran** (pop-up memilih "Masuk ke rekening";
  konfirmasi menyebut nominal, PT, rekening, dan nama penyetor) dan **Tolak**; bagian "Titipan belum disetor" per
  orang dengan saringan "Lewat tenggat". Kosong: "Tidak ada titipan tunai." Tombol mati dengan petunjuk di "Semua PT".

## Uji penerimaan

Persiapan: `sls` (tanpa `cash.create`), `fin` berperan finance (dibuat fixture), pelanggan P dengan tagihan terkirim
bersisa Rp 1.000.000 di `ent_kanda` dan pelanggan Q serupa di `ent_ksc`; rekening kas **K** di `ent_kanda`.
`pembayaran.sales_terima_tunai` = `titipan` pada `ent_kanda` saja, kecuali disebut.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `sls`: kwitansi tunai Rp 300.000 untuk P | 200; **tidak ada** `cash_transactions` baru; satu `cash_holdings` Rp 300.000 `dipegang`; jurnal Dr piutang karyawan 300.000 / Cr piutang 300.000; sisa tagihan 700.000 |
| U2 | B | — | `sls`: kwitansi tunai Rp 300.000 untuk Q (`ent_ksc`, bawaan) | Kas masuk Rp 300.000 seperti hari ini; tidak ada titipan — PT lain tidak berubah |
| U3 | B | — | `fin` (pemegang `cash.create`): kwitansi tunai Rp 300.000 untuk P | Kas masuk ke rekening K; tidak ada titipan |
| U4 | B | U1 | `sls`: `POST /api/cash-deposits` `{amount: 300000}`; `fin`: `receive` ke K | `diajukan` → `diterima`; kas masuk 300.000 ber-`account_id` K; jurnal Dr kas / Cr piutang karyawan 300.000; titipan `disetor`; saldo piutang karyawan dari modul ini 0 |
| U5 | B | Dua kwitansi titipan: Rp 300.000 lalu Rp 200.000 | Setor Rp 350.000, diterima | Titipan pertama `disetor` (300.000); kedua `sebagian_disetor` (50.000, sisa 150.000); `me/summary.held_total` 150.000 |
| U6 | B | U1 | Setor Rp 400.000 | 400 "Setoran melebihi tunai yang Anda pegang (Rp 300.000)." |
| U7 | B | Akun berperan kustom dengan `ar_receipt.create`, `cash_holding.create`, `cash_holding.approve` tetapi tanpa `cash.create` mencatat tunai Rp 100.000 lalu mengajukan setoran | Akun yang sama: `receive` setorannya sendiri | 403 "…pemegang titipannya sendiri."; setoran tetap `diajukan` |
| U8 | B | `pembayaran.titipan_batas_nominal` = 400.000; U1 | `sls`: kwitansi tunai Rp 150.000 | 409 (300.000 + 150.000 = 450.000 > 400.000); tidak ada kwitansi |
| U9 | B | `pembayaran.titipan_tenggat_setor_hari` = 1; titipan ber-`received_at` dua hari lalu | `GET /api/cash-holdings?overdue=true` | Memuat titipan itu |
| U10 | B | pengaturan `dilarang` pada `ent_kanda` | `sls`: kwitansi tunai; lalu kwitansi `transfer` | 403; 200 |
| U11 | B | U1; lalu fixture kedua seperti U4 | Batalkan kwitansi U1; batalkan kwitansi yang titipannya sudah disetor | Titipan `batal`, jurnal pembalik, sisa tagihan 1.000.000; 409 |
| U12 | B | U1 | Periode tertutup lalu `receive`; periode dibuka, jurnal kas dipaksa gagal, lalu diulang dari panel posting gagal | 409 tanpa perubahan; `gl_status: failed`; setelah diulang satu kas dan satu jurnal, `deposited_amount` 300.000 (tidak ganda) |
| U13 | B | U1, U5 | INV-TTP-01 | Hijau; setelah `deposited_amount` diubah langsung di database → merah menyebut PT |
| U14 | B | peran uji baku; setoran `diajukan` | **Tanpa Acuan** + `cash_holding.approve`: `receive`; **Manajer Kosong**; **Sopir**; `sls`: `GET /api/cash-holdings` | 200; 403; 403; `sls` hanya melihat titipannya sendiri |
| U15 | B | — | Putaran `t1_config.py` untuk tiga kunci | Lulus |
| U16 | A | U1 | Dua `receive` bersamaan untuk setoran yang sama | Satu 200, satu 409; satu transaksi kas |
| U17 | layar (uji jalan) | Data acuan, pengaturan `titipan` | `sls` di HP mencatat tunai lalu menyetor; `fin` menerima di tab Titipan Sales | Teks bantu titipan tampil; kartu "Titipan Saya" berubah; setelah diterima saldo rekening kas naik |

## Langkah kerja

1. `backend/tests_mem/test_PMT4_titipan_sales.py`: U1–U15; merah kecuali U2.
2. Tiga kunci; cabang titipan di `create_receipt`; `cash_holdings`; `post_cash_holding`. U1–U3, U8, U10 hijau.
3. Setoran: ajukan, terima (urutan §1), tolak, batal; `SOURCES`. U4–U7, U12 hijau.
4. Pembatalan kwitansi; INV-TTP-01; izin di empat tempat. U9, U11, U13, U14 hijau.
5. Layar; U16 di lingkungan A; U17; gate; laporan dengan contoh angka U1 → U4 (dokumen → jurnal → saldo) dan pertanyaan H5.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (dua koleksi baru), `CODEBASE_MAP.md`, `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md` (tab
"Titipan Sales"), `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("titipan tunai", "setoran").

## Di luar lingkup

- Izin Sales mencatat kwitansi yang diberikan saat server menyala (temuan PR-14) → PR-T9.
- Tunai non-pelanggan di tangan karyawan (uang muka, kas kecil) → PK-24. Kasus "uang dipegang karyawan" yang sudah
  terjadi tetap lewat Kasus Keuangan.

## Asumsi dan risiko

- `ASUMSI:` "sales" ditentukan dari izin, bukan nama peran: pencatat tunai yang tidak memegang `cash.create`.
- `ASUMSI:` batas dan tenggat bawaan 0 (tidak dipakai) karena rancangan tidak menyebut angka.
- `ASUMSI:` penerima setoran tidak boleh pemegang titipan itu sendiri — sifat serah-terima, bukan kontrol yang diatur.
- `RISIKO:` akun piutang karyawan juga dipakai Kasus Keuangan, sehingga saldo akunnya ≠ jumlah titipan. Invarian
  membandingkan per sumber jurnal, bukan saldo akun. Membatalkan: kembalikan pengaturan ke `kas_langsung`; titipan
  yang masih terbuka diselesaikan lewat setoran biasa.
