# KP-T2 — Kesiapan PT yang lengkap, langkah "Lengkapi PT", dan pemeriksaan sebelum arsip

| | |
|---|---|
| Gelombang | Jalur konfigurasi perusahaan (U) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KP-T1 |
| Menutup temuan | KP-10, KP-22, KP-24 |
| Keputusan | Jawaban pemilik butir 3 dan 4 |
| Standar | §3.1 (Z1, Z2, Z6), §3.4 (N1), §4 (L1, L2, L3, L5, L6), §5 (D1, D4), §6 |
| Lingkungan uji | B |

## Tujuan

Daftar kesiapan PT memeriksa semua hal yang membuat transaksi pertama dan tutup buku bisa berjalan, dan tiap barisnya
mengantar ke layar yang benar. PT yang baru dibuat langsung dituntun melengkapi sisanya. PT tidak lagi bisa diarsipkan
tanpa sengaja selagi masih punya hutang, saldo kas, uang muka, atau karyawan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Daftar kesiapan berisi 8 butir: pengguna, gudang, rekening bank, harga jual, saldo awal, kop & logo, pajak, tahun fiskal | `backend/services/entity_readiness_service.py:49` (`items`) |
| 2 | Baris gudang mengantar ke `view: "admin"`, yang sekarang adalah layar "Integrasi & Audit"; master gudang ada di `md-warehouses` | `backend/services/entity_readiness_service.py:64` (`warehouses`); `frontend/src/AppViewRouter.jsx:139` (`AdminView`); `frontend/src/AppViewRouter.jsx:174` (`md-warehouses`) |
| 3 | "Rekening bank" menghitung semua `bank_accounts` milik PT **dan** milik `"all"`, tanpa membedakan rekening bank dan akun kas | `backend/services/entity_readiness_service.py:41` (`bank_accounts`) |
| 4 | Teks petunjuk menyebut menu yang sudah tidak ada: "Master Data → Gudang", "Pengaturan → Template PDF", dan menyuruh "ubah status PKP-nya" | `backend/services/entity_readiness_service.py:63` (`how_to`); `backend/services/entity_readiness_service.py:95` (`how_to`); `backend/services/entity_readiness_service.py:105` (`how_to`) |
| 5 | Tidak ada butir untuk pemetaan akun, periode buku, penanda tangan, akun kas, alamat, pengguna keuangan, termin bawaan | `backend/services/entity_readiness_service.py:35` (`readiness`) |
| 6 | Saat PT dibuat: dokumen PT disimpan **dulu**, baru bagan akun dipastikan dan penanda lapisan pengaturan dibuat. Bila langkah bagan akun gagal, PT sudah tersimpan tanpa penanda dan tanpa cara mengulang | `backend/services/entity_provisioning_service.py:161` (`provision_entity`); `backend/services/entity_provisioning_service.py:165` (`seed_default_coa`) |
| 7 | Setelah wizard selesai, layar hanya menampilkan pesan dan membuka detail PT; tidak ada tuntunan mengisi rekening, kas, gudang, kop, akun | `frontend/src/features/settings/entities/EntitiesAccessView.jsx:187` (`onCreated`) |
| 8 | Pemeriksaan "dokumen terbuka" sebelum arsip hanya membaca 17 koleksi; uang muka, SPK makloon, permintaan pembelian, pesanan khusus, dan penerimaan barang tidak termasuk | `backend/services/entity_lifecycle_service.py:50` (`DOC_SOURCES`); `backend/services/entity_lifecycle_service.py:216` (`_open_documents`) |
| 9 | "Piutang belum lunas" dijumlah dari **semua** `sales_orders` PT tanpa menyaring status (pesanan batal ikut terhitung); hutang pemasok, saldo kas/bank, dan karyawan tidak diperiksa | `backend/services/entity_lifecycle_service.py:230` (`_open_balances`) |
| 10 | Pembacaan dokumen terbuka dipotong diam-diam pada 2.000 baris per koleksi | `backend/services/entity_lifecycle_service.py:220` (`to_list`) |

Sumber angka yang sudah ada dan dipakai ulang: piutang terbuka per PT —
`backend/services/ar_aging_service.py:177` (`aging_report`); sisa tagihan pemasok —
`backend/services/vendor_bill_service.py:200` (`bill_financials`); saldo rekening —
`backend/services/bank_service.py:76` (`_balance`); pemetaan akun per PT —
`backend/services/gl_mapping_service.py:95` (`list_mappings`); periode tertutup —
`backend/services/closing_service.py:521` (`status_for_date`); termin efektif —
`backend/services/entity_master_service.py:559` (`resolve_row`); matriks izin —
`backend/dependencies.py:101` (`permission_matrix`).

Yang sudah benar dan dipertahankan: arsip bukan hapus, pratinjau dampak, paksa dengan alasan, kunci-tulis di satu
titik — `backend/services/entity_lifecycle_service.py:315` (`archive_entity`).

## Perubahan

### Data

`business_entities` mendapat satu field:

| Field | Tipe | Arti |
|---|---|---|
| `provisioning` | objek `{coa: bool, config_layer: bool, group_partners: bool, at: iso}` | Langkah penyiapan awal yang sudah berhasil. PT lama tanpa field ini dihitung dari data (lihat butir `provisioning` di bawah) |

Tanpa koleksi dan indeks baru. Tanpa migrasi.

### Server

**Daftar kesiapan** — `backend/services/entity_readiness_service.py` (`readiness`) mengembalikan 16 butir berurutan
seperti urutan mengisi. Bentuk tiap butir tetap `{key, label, ready, count, detail, how_to, view}`; ditambah `tab`
(opsional, nama tab tujuan di layar itu). Bentuk ringkasan (`ready`, `total`, `percent`, `is_ready`) tidak berubah.

| # | `key` | Label | Siap bila (dihitung dari data) | `view` · `tab` |
|---|---|---|---|---|
| 1 | `provisioning` | Penyiapan awal | `gl_accounts` dengan `entity_id` kosong > 0 **dan** ada `system_settings` ber-`scope` = id PT | — (tombol "Ulangi penyiapan") |
| 2 | `address` | Alamat lengkap | `address`, `city`, dan `province` PT tidak kosong | `entities-access` · `entities` |
| 3 | `tax` | Status pajak & NPWP | `default_tax_mode` terisi dan (NPWP terisi atau non-PKP) — aturan hari ini | `entities-access` · `entities` |
| 4 | `doc_prefix` | Kode dokumen | `doc_prefix` cocok `[A-Z0-9]{2,10}` | `entities-access` · `entities` |
| 5 | `users` | Pengguna | `users` aktif dengan `home_entity_id` = id PT > 0 — aturan hari ini | `entities-access` · `accounts` |
| 6 | `finance_user` | Pengguna keuangan | Ada pengguna aktif yang boleh bekerja di PT ini (`home_entity_id` = id, atau id ∈ `allowed_entity_ids`, atau perannya lintas PT) **dan** perannya memegang izin `cash.create` menurut `permission_matrix()` | `entities-access` · `accounts` |
| 7 | `warehouses` | Gudang yang boleh dipakai | `_usable_warehouses` > 0 — aturan hari ini | `md-warehouses` |
| 8 | `bank_account` | Rekening bank | `bank_accounts` `{entity_id: id, account_type: "bank", is_active ≠ false}` > 0 | `bank-accounts` |
| 9 | `cash_account` | Akun kas | `bank_accounts` `{entity_id: id, account_type: "cash", is_active ≠ false}` > 0 | `bank-accounts` |
| 10 | `gl_mappings` | Pemetaan akun | Pada `list_mappings(id)["rows"]`, jumlah baris ber-`required` benar dengan `status` ≠ `"ok"` = 0. `count` = jumlah yang belum beres | `gl-account-mappings` |
| 11 | `period` | Periode buku hari ini terbuka | `status_for_date(<hari ini WIB>, id)["closed"]` salah | `closing` |
| 12 | `payment_term` | Termin pembayaran bawaan | Nilai efektif `finance.default_payment_term_code` untuk PT ini ditemukan `resolve_row("payment-terms", kode, id)` | `entity-masters` |
| 13 | `prices` | Harga jual | Aturan hari ini (harga khusus PT atau harga umum ada) | `pricelist` |
| 14 | `opening_balance` | Saldo awal | Aturan hari ini (ada jurnal bersumber "opening") | `general-ledger` |
| 15 | `branding` | Kop surat & logo | `document_branding` PT punya `logo_b64` atau `header_image_b64`, atau `logo_url` PT terisi | `pdf-templates` |
| 16 | `signers` | Penanda tangan | `document_branding.signatures` PT memuat ≥ 1 baris ber-`name` | `pdf-templates` |

Butir lama `bank_accounts` dipecah menjadi 8 dan 9; butir lama `fiscal_year` dihapus (tahun buku selalu punya nilai
efektif sejak KP-T1). `readiness_summary` tetap mengembalikan `warehouse_count`.

Teks `detail` saat belum siap dan `how_to` (persis):

| `key` | `detail` belum siap | `how_to` |
|---|---|---|
| `provisioning` | "Penyiapan awal PT belum tuntas" | "Tekan Ulangi penyiapan." |
| `address` | "Alamat, kota, atau provinsi masih kosong" | "Lengkapi alamat di profil PT." |
| `tax` | "PKP tetapi NPWP masih kosong" | "Lengkapi NPWP di profil PT, atau pakai tombol Ubah status PKP." |
| `finance_user` | "Belum ada pengguna yang bisa mencatat kas untuk PT ini" | "Beri seorang pengguna peran yang punya akses Kas & Bank, dan tugaskan ke PT ini." |
| `warehouses` | "Tidak ada gudang yang boleh dipakai PT ini" | "Atur gudang bersama atau khusus di Master Gudang." |
| `bank_account` | "Belum ada rekening bank" | "Tambah rekening di Keuangan › Rekening & Saldo." |
| `cash_account` | "Belum ada akun kas" | "Tambah akun kas di Keuangan › Rekening & Saldo." |
| `gl_mappings` | "{n} pemetaan akun wajib belum beres" | "Lengkapi di Pengaturan › Keuangan & Pajak › Pemetaan Akun." |
| `period` | "Tanggal hari ini berada di periode yang sudah ditutup" | "Periksa Tutup Buku; transaksi bertanggal hari ini akan ditolak." |
| `payment_term` | "Termin bawaan “{kode}” tidak ada di daftar termin PT ini" | "Pilih termin yang ada di Pusat Pengaturan, atau tambahkan terminnya." |
| `branding` | "Dokumen cetak masih memakai kop bawaan" | "Atur di Pengaturan › Dokumen & Cetak › Template Dokumen." |
| `signers` | "Belum ada nama penanda tangan" | "Isi di Pengaturan › Dokumen & Cetak › Template Dokumen." |

**Penyiapan PT yang bisa diulang** — `backend/services/entity_provisioning_service.py`:

1. `provision_entity` mengubah urutan: validasi → `gl_service.seed_default_coa()` (milik bersama, tidak menulis apa pun
   atas nama PT) → simpan dokumen PT dengan `provisioning: {coa: true, config_layer: false, group_partners: false}` →
   `run_provisioning_steps`.
2. `async def run_provisioning_steps(entity_id, actor_name) -> dict` — tiga langkah yang masing-masing aman diulang:
   pastikan bagan akun; buat penanda `system_settings{scope: id}`; `sync_group_entity_suppliers`. Tiap langkah yang
   berhasil ditandai di `provisioning`. Kegagalan satu langkah tidak membatalkan PT dan dilaporkan di jawaban.
3. `POST /api/entities/{id}/provisioning/retry` · izin `entity.update` · tanpa isi · jawaban `{entity_id,
   provisioning, readiness}`. 404 bila PT tidak ada; 409 "PT ini sudah diarsipkan." bila terkunci.

**Pemeriksaan sebelum arsip** — `backend/services/entity_lifecycle_service.py`:

- Daftar baru `ARCHIVE_EXTRA_SOURCES` (koleksi · field nomor · label), dipakai `_open_documents` bersama
  `DOC_SOURCES` tetapi **tidak** dipakai kunci kode dokumen:
  `cash_advances`·`number`·"Uang muka"; `cash_advance_settlements`·`number`·"Pertanggungjawaban uang muka";
  `makloon_orders`·`mko_number`·"SPK makloon"; `purchase_requisitions`·`number`·"Permintaan pembelian";
  `special_orders`·`number`·"Pesanan khusus"; `goods_receipts`·`number`·"Penerimaan barang".
- `_open_documents` menghitung dengan `count_documents({entity_id, status: {$nin: CLOSED_STATUSES}})` dan mengambil
  tiga contoh nomor dengan `limit(3)`; tidak ada lagi `to_list(2000)` (D4).
- `_open_balances` menjadi:

| `key` | Label | Cara hitung | Penghalang bila |
|---|---|---|---|
| `piutang` | Piutang pelanggan belum lunas | `aging_report(entity_id=id)["totals"]["total"]` | > 0,01 |
| `hutang` | Hutang pemasok belum lunas | Σ `bill_financials(b)["outstanding"]` untuk `vendor_bills` `{entity_id: id, status: "posted"}` | > 0,01 |
| `kas_bank` | Saldo kas dan bank | Σ nilai mutlak saldo tiap `bank_accounts` `{entity_id: id}` (saldo awal + masuk − keluar, transaksi tidak batal) | > 0,01 |
| `antar_pt` | Saldo antar-PT | seperti hari ini | > 0,01 |
| `stok` | Roll stok masih dimiliki | seperti hari ini | > 0 |

- `deactivation_impact` menambah `employees` = jumlah `hr_employees` `{entity_id: id, status: {$ne: "resigned"}}` dan
  penghalang "{n} karyawan masih terdaftar di PT ini — pindahkan atau akhiri dulu". Jawaban menambah kunci
  `employees` dan `checks`: daftar `{key, label, ok, detail}` untuk kelima kelompok (pengguna, dokumen, saldo,
  karyawan, periode) supaya layar bisa menampilkan daftar centang yang sama dengan yang diperiksa server.

Cara memaksa (alasan wajib) tidak diubah.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan izin baru. Butir `finance_user` membaca matriks izin, bukan nama peran (Z2).

### Layar

Tempat: Pengaturan › Perusahaan & Akun › Badan Usaha & Akses › tab Badan Usaha dan tab Kesiapan.

- Komponen baru `frontend/src/features/settings/entities/EntityCompletionSteps.jsx`: menampilkan butir kesiapan
  sebagai daftar langkah bernomor. Tiap baris: tanda siap/belum, label, `detail`, `how_to`, dan tombol **Lengkapi**
  (bila `view` ada) yang lebih dulu mengganti PT aktif ke PT ini lalu membuka `view` (dan `tab`). Baris `provisioning`
  yang belum siap bertombol **Ulangi penyiapan**. Judul: **Lengkapi PT**. Ringkasan: "{siap} dari {total} hal sudah
  siap".
- `EntityWizard.jsx`: setelah simpan berhasil, wizard tidak menutup; ia berpindah ke langkah ke-5 **Lengkapi PT**
  yang memuat komponen di atas untuk PT baru, dengan tombol **Selesai** (menutup dan membuka detail) dan kalimat
  "Langkah ini bisa dilanjutkan kapan saja dari tab Kesiapan."
- `EntityDetailDrawer.jsx` (bagian "Kesiapan") dan `EntityReadinessPanel.jsx` memakai komponen yang sama, sehingga
  tautan dan teksnya satu sumber. Judul panel menjadi **Kesiapan PT**.
- `ArchiveEntityDialog.jsx`: menampilkan `checks` sebagai daftar centang berjudul **Sebelum mengarsipkan**; baris
  yang belum beres menyebut jumlah dan contohnya; nominal rupiah berpemisah ribuan. Tombol **Arsipkan** tetap mati
  selama ada penghalang, kecuali dipaksa dengan alasan.

Keadaan memuat, galat, kosong: seperti panel kesiapan yang ada (kerangka abu-abu; "Pilih PT untuk melihat daftar
kesiapannya.").

## Uji penerimaan

Persiapan bersama: seed lingkungan B; akun admin; `ent_ksc` dan `ent_kanda`.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `GET /api/entities/ent_ksc/readiness` | `total` = 16; urutan `key` persis seperti tabel; tidak ada `key` `bank_accounts` maupun `fiscal_year` |
| U2 | B | — | Ambil butir `warehouses` | `view` = `"md-warehouses"`; tidak ada butir ber-`view` `"admin"` |
| U3 | B | Hapus semua `bank_accounts` `ent_kanda`; sisipkan satu `{entity_id: "ent_kanda", account_type: "cash"}` | `GET …/ent_kanda/readiness` | `cash_account.ready` benar; `bank_account.ready` salah |
| U4 | B | Sisipkan `bank_accounts` `{entity_id: "all", account_type: "bank"}` saja | `GET …/ent_kanda/readiness` | `bank_account.ready` salah (rekening tingkat grup tidak dihitung) |
| U5 | B | Nonaktifkan satu akun yang dipetakan wajib untuk `ent_kanda` (`gl_accounts.is_active = false`) | `GET …/ent_kanda/readiness` | `gl_mappings.ready` salah; `count` = jumlah baris wajib ber-status bukan `ok` dari `GET /api/gl/account-mappings` untuk PT yang sama |
| U6 | B | Sisipkan `period_closings` `{entity_id: "ent_kanda", status: "closed"}` yang mencakup hari ini | `GET …/ent_kanda/readiness` dan `…/ent_ksc/readiness` | `period.ready` salah untuk `ent_kanda`, benar untuk `ent_ksc` |
| U7 | B | Tulis lapisan PT `finance.default_payment_term_code = "TIDAKADA"` untuk `ent_kanda` | `GET …/ent_kanda/readiness` | `payment_term.ready` salah; `detail` memuat "TIDAKADA"; `ent_ksc` tetap siap |
| U8 | B | Peran **Tanpa Acuan** berizin `cash.create`; satu akun aktif berperan itu dengan `home_entity_id: "ent_kanda"`; tidak ada pengguna lain yang bisa bekerja di `ent_kanda` selain peran lintas PT tanpa `cash.create` | `GET …/ent_kanda/readiness` sebelum dan sesudah akun dibuat | `finance_user.ready` salah → benar |
| U9 | B | `document_branding` `{entity_id: "ent_kanda", signatures: [{label: "Direktur", name: ""}]}` | `GET …/ent_kanda/readiness`; lalu isi `name: "Budi"` | `signers.ready` salah → benar |
| U10 | B | `gl_service.seed_default_coa` dipaksa melempar galat pada panggilan pertama | `POST /api/entities` dengan isi sah | Galat; **tidak ada** dokumen PT baru di `business_entities` |
| U11 | B | PT dibuat normal; lalu `system_settings{scope: id}` dihapus | `GET …/readiness` → `POST …/provisioning/retry` → `GET …/readiness` | `provisioning.ready` salah → jawaban retry `provisioning.config_layer` benar → siap |
| U12 | B | `POST …/provisioning/retry` dua kali berturut | — | Keduanya 200; jumlah `system_settings{scope: id}` = 1; jumlah pemasok "entitas grup" tidak bertambah pada panggilan kedua |
| U13 | B | `ent_kanda`: satu `sales_orders` `{status: "cancelled", grand_total: 1000000, paid_total: 0}` (fixture) | `GET …/ent_kanda/deactivation-impact` | `balances` tidak memuat `piutang` (dulu memuat Rp1.000.000) |
| U14 | B | `ent_kanda`: `vendor_bills` `{status: "posted", grand_total: 500000, amount_paid: 200000}` | `GET …/deactivation-impact` | `balances` memuat `hutang` dengan `amount` 300000 (500.000 − 200.000); `can_archive` salah |
| U15 | B | `ent_kanda`: `bank_accounts` `{account_type: "cash", opening_balance: 250000}` tanpa transaksi | `GET …/deactivation-impact` | `balances` memuat `kas_bank` 250000 |
| U16 | B | `ent_kanda`: satu `cash_advances` `{status: "approved"}` dan satu `hr_employees` `{status: "active"}` | `GET …/deactivation-impact`; lalu `DELETE /api/entities/ent_kanda` tanpa paksa | `open_documents` memuat "Uang muka" `count` 1; `employees` = 1; DELETE → 409 dengan dua penghalang itu |
| U17 | B | seperti U16 | `DELETE /api/entities/ent_kanda?force=true&reason=Tutup%20usaha` sebagai admin | 200; status `archived` (cara memaksa tidak berubah) |
| U18 | layar (uji jalan) | Login admin | Buat PT lewat wizard sampai langkah 5; tekan **Lengkapi** pada baris Gudang | Terbuka Master Gudang dengan PT baru sebagai PT aktif |

## Langkah kerja

1. `backend/tests_mem/test_KPT2_kesiapan_arsip.py`: U1–U17 (merah).
2. Daftar kesiapan 16 butir beserta teksnya.
3. Urutan penyiapan PT, `run_provisioning_steps`, endpoint ulang.
4. `ARCHIVE_EXTRA_SOURCES`, `_open_documents` tanpa potongan, `_open_balances` dari buku pembantu, `employees`,
   `checks`.
5. `EntityCompletionSteps.jsx`; langkah 5 wizard; panel kesiapan; dialog arsip.
6. Gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (field `business_entities.provisioning`); `CODEBASE_MAP.md` (`EntityCompletionSteps.jsx`);
`memory/PRD.md` (langkah "Lengkapi PT").

## Di luar lingkup

- Kesiapan sebagai **gerbang** yang menolak transaksi pertama: tidak ada keputusan pemilik; tidak dibangun.
- Form buat rekening, kas, gudang, dan kop di dalam wizard: langkah "Lengkapi PT" mengantar ke layar yang sudah ada.
- Syarat "hanya admin yang boleh memaksa arsip" masih memakai nama peran → PR-T2.
- Butir kesiapan "penomoran dokumen sudah diatur" → ditambahkan KP-T5 bila tabelnya lahir.
- Nama hub dan tab → KP-T9.

## Asumsi dan risiko

- `ASUMSI:` izin yang menandai "pengguna keuangan" adalah `cash.create` (izin mencatat transaksi kas), karena itu
  izin keuangan paling dasar yang dipegang peran Finance bawaan.
- `ASUMSI:` rekening dan akun kas tingkat grup (`entity_id: "all"`) tidak dihitung sebagai milik PT, sesuai catatan
  kode bahwa kas tingkat grup harus nol setelah migrasi E7.4.
- `ASUMSI:` hutang pemasok yang masih hidup = tagihan berstatus `posted` dengan sisa > 0, sama dengan yang dipakai
  pengingat hutang jatuh tempo.
- `ASUMSI:` pengalih PT aktif bisa dipanggil dari komponen ini lewat fungsi yang sama dengan pemilih PT di kepala
  layar (`frontend/src/hooks/useAppActions.js`); bila tidak, tombol **Lengkapi** membuka layar tujuan dan menampilkan
  petunjuk "Pilih {nama PT} di pemilih PT."
- `RISIKO:` status "terbuka" memakai aturan umum (di luar `CLOSED_STATUSES`), sehingga koleksi tambahan bisa terhitung
  terbuka lebih banyak dari seharusnya (mis. permintaan pembelian yang sudah menjadi PO). Akibatnya hanya arsip yang
  tertahan; admin tetap bisa memaksa dengan alasan. Membatalkan: kosongkan `ARCHIVE_EXTRA_SOURCES`.
- `RISIKO:` PT lama yang sekarang "100% siap" akan turun persentasenya karena butir bertambah. Itu yang dimaksud.
