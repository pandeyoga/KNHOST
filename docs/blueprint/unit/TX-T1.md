# TX-T1 — Pengaturan pajak bertanggal berlaku, potret pajak di dokumen, dan data pajak pelanggan

| | |
|---|---|
| Gelombang | Modul faktur pajak |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PK-40 |
| Menutup temuan | TX-06 |
| Keputusan | K-33 |
| Standar | §2 (2.1, 2.2, 2.4), §3.1 (Z1, Z2, Z6), §3.2, §4 (L1, L5, L6), §5 (D1, D3, D5), §6 |
| Lingkungan uji | B |

Hal peraturan di unit ini bertanda **(konfirmasi konsultan pajak)**. Unit hanya memindahkan angka yang sudah tertulis
di kode menjadi pengaturan dengan nilai yang sama; ia tidak menetapkan tarif, faktor, atau kode baru (H4).

## Tujuan

Tarif PPN, faktor DPP nilai lain, cara pembulatan, dan kode transaksi bawaan menjadi pengaturan per PT yang bisa
dijadwalkan berlaku mulai tanggal tertentu, dan tiap pesanan serta faktur menyimpan potret aturan yang dipakainya —
mengubah tarif untuk bulan depan tidak mengubah dokumen bulan ini. Data pajak pelanggan punya tempat yang layak.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| Fakta | Jangkar |
|---|---|
| PPN dihitung dari pengaturan **saat ini** (dokumen `system_settings` gabungan), tanpa tanggal dokumen | `backend/services/config_service.py:266` (`compute_tax`), `backend/services/config_service.py:272` (`get_effective_settings`) |
| Faktor DPP nilai lain 11/12 ditulis mati — di empat tempat | `backend/services/config_service.py:285` (`dpp_factor`), `backend/services/interco_tax_service.py:70` (`tax_dpp_nilai_lain`), `backend/services/interco_service.py:232` (`dpp_nilai_lain`), `backend/services/config_simulator.py:49` (`factor`) |
| Pembulatan dua desimal di tingkat pesanan, ditulis mati | `backend/services/config_service.py:293` (`ppn`) |
| PT non-PKP memaksa tarif 0 dari master badan usaha | `backend/services/config_service.py:255` (`ppn_rate`) |
| Resolver pengaturan **sudah** mendukung nilai berjadwal dan pembacaan pada tanggal tertentu, tetapi `compute_tax` tidak memakainya | `backend/services/config_resolver.py:318` (`set_value`), `backend/services/config_resolver.py:245` (`resolve`) |
| Tiga kunci pajak terdaftar: tarif, sakelar DPP nilai lain, mode harga | `backend/config_catalog_core.py:17` (`tax.ppn_rate`), `backend/config_catalog_core.py:26` (`tax.dpp_nilai_lain`) |
| Daftar kode transaksi dan bawaannya (04 bila DPP nilai lain, selain itu 01) ditulis mati | `backend/services/tax_invoice_service.py:17` (`KODE_TRANSAKSI_VALID`), `backend/services/tax_invoice_service.py:140` (`kode`) |
| Pesanan menyimpan tarif, mode, dan bendera DPP nilai lain, tetapi bukan faktor maupun cara bulat; hitung ulang saat override memakai pengaturan hari itu | `backend/routers/sales_orders.py:609` (`dpp_nilai_lain`), `backend/services/so_override_service.py:15` (`compute_order_pricing`) |
| Data pajak pelanggan hanya `npwp` teks bebas; potret faktur hanya memuat NPWP dan alamat utama | `backend/schemas.py:106` (`npwp`), `backend/services/tax_invoice_service.py:88` (`customer_npwp`) |
| `tax_override: "non_ppn"` diterima dari isi permintaan (PK-45 menambah izin dan alasan); checkout tidak punya isiannya | `backend/routers/sales_orders.py:308` (`tax_override`), `backend/services/config_service.py:460` (`non_ppn`) |

## Perubahan

### Data

`sales_orders` dan `tax_invoices` — field baru `tax_snapshot` (D3; tidak pernah dihitung ulang):
`{ppn_rate, dpp_nilai_lain, dpp_pembilang, dpp_penyebut, ppn_mode, pembulatan_tingkat, pembulatan_satuan, is_pkp,
berlaku_pada}`. Dokumen lama tanpa potret dianggap berpotret dari field yang ada (`ppn_rate`, `ppn_mode`,
`dpp_nilai_lain`) dengan faktor 11/12, dokumen, dua desimal — tanpa migrasi.

`sales_orders` — `tax_override_by` (melengkapi `tax_override_reason` hasil PK-45). Baris pesanan — `ppn_amount` (hanya saat pembulatan per baris).

`customers.tax_profile` (objek baru; `customers.npwp` tetap pemilik nomor NPWP):

| Field | Tipe | Arti |
|---|---|---|
| `id_type` | `npwp` · `nik` · `""` | Identitas yang dipakai di faktur |
| `nik` | string angka | Bila `id_type: nik` |
| `tax_name`, `tax_address` | string | Nama dan alamat menurut dokumen pajak; kosong = nama pelanggan dan alamat utama |
| `is_pkp` | `true` · `false` · `null` | Status PKP pelanggan; `null` = belum diisi |
| `kode_transaksi` | string | Kode transaksi bawaan pelanggan ini; kosong = ikut PT |
| `always_tax_invoice` | bool | Pelanggan selalu meminta faktur pajak |

`tax_invoices` — tambah `customer_tax` (potret `id_type`, nomor identitas, `tax_name`, `tax_address`, `is_pkp`) dan
`data_incomplete` (daftar: `identitas_pajak`, `alamat_pajak`). `products` — `tax_treatment` (`kena` · `dibebaskan` ·
`tidak_dipungut`, bawaan `kena`) dan `tax_item_code`: disimpan dan ditampilkan bertanda "belum dipakai mesin"; lihat
"Di luar lingkup".

### Server

Berkas baru `backend/services/tax_config_service.py`:

| Fungsi | Perilaku |
|---|---|
| `async def tax_settings(entity_id: str, at: Optional[datetime] = None) -> dict` | Membaca tujuh kunci di bawah + `tax.ppn_rate`, `tax.dpp_nilai_lain`, `tax.ppn_mode` lewat `config_resolver.resolve(key, {"entity_id"}, at=at)`; PT non-PKP (master badan usaha) memaksa tarif 0. Hasilnya berbentuk `tax_snapshot` + `sources` |
| `def round_money(value: float, satuan: str) -> float` | **Satu** fungsi bulat pajak (D5): `dua_desimal` atau `rupiah_penuh` |
| `def default_kode(snapshot: dict, customer: dict, settings: dict) -> str` | Urutan: `customers.tax_profile.kode_transaksi` → bawaan PT menurut DPP nilai lain |

`compute_tax(subtotal, entity_id, mode_override=None, *, at=None, snapshot=None)`:
`snapshot` diberikan → dihitung **dari potret** (untuk hitung ulang dokumen yang sudah ada); selain itu dari
`tax_settings(entity_id, at)`. Rumus tetap: tarif efektif = tarif × pembilang ÷ penyebut bila DPP nilai lain;
`dpp` = harga jual × pembilang ÷ penyebut; hasil dibulatkan `round_money`. `compute_order_pricing` meneruskan `at` dan
`snapshot`, dan saat `pembulatan_tingkat == "baris"` menghitung PPN tiap baris lalu menjumlahkannya.

| Pemanggil | Perubahan |
|---|---|
| `create_order` dan pembuat dokumen pembelian | `at` = tanggal dokumen; menyimpan `tax_snapshot` |
| `so_override_service`, amandemen, retur (hitung ulang dokumen lama) | `snapshot` = potret dokumen itu |
| `interco_tax_service`, `interco_service`, `config_simulator` | Faktor dari `tax_settings` |
| `tax_invoice_service.issue_tax_invoice`, `replace_tax_invoice`, `set_nsfp` | Kode bawaan dari `default_kode`; kode sah = `tax.kode_transaksi_diizinkan`; potret `tax_snapshot` dan `customer_tax` ikut disimpan; `data_incomplete` diisi (penerbitan **tidak** ditolak di unit ini) |
| `PATCH /api/customers/{id}` | Menerima `tax_profile` (izin `customer.update`, seperti `npwp` hari ini) dengan validasi di bawah |
| `create_order` | Aturan PK-45 tetap (`tax_override: "non_ppn"` menuntut izin `order.tax_override` dan `tax_override_reason` ≥ 10 huruf); unit ini menambah `tax_override_by` dan potret pajak ber-`is_pkp: false` |

Galat:

| Keadaan | Kode | Pesan |
|---|---|---|
| Kode transaksi di luar daftar PT | 400 | "Kode transaksi {kode} tidak dipakai PT ini." |
| NIK/NPWP berisi selain angka dan tanda baca | 400 | "{NIK/NPWP} hanya boleh berisi angka." |
| `id_type: nik` tanpa `nik` | 400 | "NIK wajib diisi bila identitas pajak memakai NIK." |
| Pesanan tanpa PPN tanpa izin | 403 | "Anda belum punya akses untuk membuat pesanan tanpa PPN. Minta Admin menambahkan akses 'Pesanan Penjualan'." |
| Pesanan tanpa PPN tanpa alasan | 400 | "Alasan pesanan tanpa PPN wajib diisi (minimal 10 huruf)." (pesan PK-45) |

Jumlah digit NPWP (15 atau 16) dan NIK (16) **tidak** menolak simpan; yang menyimpang hanya diberi peringatan di jawaban
(`tax_data_warnings`) **(konfirmasi konsultan pajak)**.

### Pengaturan

Semua: group `pajak-pembukuan` (sub-judul `pajak`), scopes `("global", "entity")`, risk `high`, `requires_reason` ya, permission
`("accounting", "manage")`, consumers `services/tax_config_service.py:tax_settings`. Perubahan bisa dijadwalkan dengan
"berlaku sejak" yang sudah ada di Pusat Pengaturan.

| key | type · default | label | help → impact → example |
|---|---|---|---|
| `tax.dpp_nilai_lain_pembilang` | `int` · 11 (min 1, max 1000) | "Faktor DPP nilai lain — pembilang" | Bagian atas pecahan DPP nilai lain. → Mengubah DPP dan PPN semua dokumen baru. → "11 dari 11/12" **(konfirmasi konsultan pajak)** |
| `tax.dpp_nilai_lain_penyebut` | `int` · 12 (min 1, max 1000) | "Faktor DPP nilai lain — penyebut" | Bagian bawah pecahan. → sama. → "Harga Rp 12.000.000 × 11/12 = DPP Rp 11.000.000" |
| `tax.pembulatan_tingkat` | `enum` `dokumen` · `baris`; bawaan `dokumen` | "PPN dibulatkan per" | Per dokumen = dihitung dari total; per baris = dihitung tiap baris lalu dijumlah. → Bisa menggeser PPN beberapa rupiah. → "Dua baris Rp 100.005: per baris Rp 22.002, per dokumen Rp 22.001 (rupiah penuh)" |
| `tax.pembulatan_satuan` | `enum` `dua_desimal` · `rupiah_penuh`; bawaan `dua_desimal` | "PPN dibulatkan ke" | → Mengubah angka PPN dan total dokumen baru. → "Rp 135.802,37 menjadi Rp 135.802" |
| `tax.kode_transaksi_diizinkan` | `list` · `["01","02","03","04","06","07","08","09"]` | "Kode transaksi faktur yang dipakai" | Pilihan kode saat menerbitkan faktur. → Kode di luar daftar ditolak. → "Hapus 07 → faktur berkode 07 ditolak" **(konfirmasi konsultan pajak)** |
| `tax.kode_transaksi_bawaan` | `enum` (pilihan = kode `tax.kode_transaksi_diizinkan` bawaan) · `"01"` | "Kode transaksi bawaan" | Dipakai bila pelanggan tidak punya kode sendiri dan PT tidak memakai DPP nilai lain. → Mengisi otomatis kode faktur baru. → "01" |
| `tax.kode_transaksi_bawaan_dpp_nilai_lain` | `enum` (pilihan sama) · `"04"` | "Kode transaksi bawaan saat DPP nilai lain" | Dipakai bila pesanan memakai DPP nilai lain. → sama. → "04" **(konfirmasi konsultan pajak)** |

### Izin dan peran

Tidak ada pasangan baru. Pesanan tanpa PPN memakai `order.tax_override` (bawaan admin, manager; modul `penjualan`) yang
dibuat PK-45. Bila PK-45 belum selesai saat unit ini dikerjakan, buat izin dan field `tax_override_reason` persis
seperti itu di empat tempat (§3.2) dan catat di laporan.

### Layar

- **Kartu dan form pelanggan** (`CustomerFormModal.jsx`): bagian "Data pajak" — "Identitas pajak" [NPWP · NIK], "NPWP"
  atau "NIK", "Nama di faktur pajak", "Alamat di faktur pajak", "Status PKP pelanggan" [Belum diisi · PKP · Bukan PKP],
  "Kode transaksi bawaan" (pilihan dari daftar PT + "Ikut PT"), sakelar "Selalu minta faktur pajak". Peringatan bentuk
  tampil di bawah isian tanpa menghalangi simpan.
- **Checkout**: pemegang `order.tax_override` di PT PKP melihat sakelar "Pesanan tanpa PPN" + isian wajib "Alasan tanpa
  PPN"; ringkasan harga langsung menghitung ulang. Pelanggan ber-`always_tax_invoice` mencentang "Minta faktur pajak".
- **Faktur Keluaran** (`TaxInvoices.jsx`): pilihan kode transaksi dari `tax.kode_transaksi_diizinkan`; rincian faktur
  menampilkan "Aturan pajak saat terbit" (tarif, faktor, pembulatan, tanggal berlaku) dan lencana "Data pajak belum
  lengkap" bila `data_incomplete` terisi.
- **Detail pesanan**: baris "Aturan pajak" dari `tax_snapshot`; pesanan tanpa PPN menulis alasan dan pembuatnya.
- **Form produk**: "Perlakuan PPN" dan "Kode barang pajak" bertanda "belum dipakai mesin" (L5).

## Uji penerimaan

Persiapan: `ent_ksc` PKP dengan kunci bawaan (tarif 12, DPP nilai lain ya, harga belum termasuk PPN); `ent_kanda`
non-PKP. Tarif efektif bawaan = 12 × 11 ÷ 12 = 11 %.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | Pesanan `ent_ksc` bersubtotal Rp 12.000.000 | `dpp` 11.000.000; `ppn_amount` 1.320.000; `grand_total` 13.320.000; `tax_snapshot` = tarif 12, 11/12, `dokumen`, `dua_desimal` — sama dengan sebelum unit ini |
| U2 | B | `tax.ppn_rate` = 13 dijadwalkan berlaku 2027-01-01 pada `ent_ksc` | Pesanan hari ini; `compute_tax(12000000, "ent_ksc", at=2027-01-15)` | Pesanan tetap PPN 1.320.000; hitungan 2027 = 1.430.000 (12.000.000 × 13 % × 11 ÷ 12) |
| U3 | B | U1 lalu `tax.ppn_rate` diubah menjadi 13 berlaku sekarang | Override menambah jumlah pesanan U1 menjadi subtotal Rp 24.000.000; terbitkan faktur | PPN 2.640.000 (potret 12 % × 11/12), bukan 2.860.000; faktur memuat potret yang sama |
| U4 | B | `tax.dpp_nilai_lain_pembilang` = 12 pada `ent_ksc` | Pesanan subtotal Rp 12.000.000 di `ent_ksc`; hitungan yang sama untuk PT ketiga | `ent_ksc`: `dpp` 12.000.000, PPN 1.440.000; PT ketiga tetap `dpp` 11.000.000, PPN 1.320.000 — PT lain tidak berubah |
| U5 | B | `tax.pembulatan_satuan` = `rupiah_penuh` | Pesanan subtotal Rp 1.234.567 | PPN 135.802 (dari 135.802,37); `dpp` 1.131.686 (dari 1.131.686,42); total 1.370.369 |
| U6 | B | U5 + `tax.pembulatan_tingkat` = `baris` | Pesanan dua baris masing-masing Rp 100.005; ulangi dengan `dokumen` | Per baris: 11.001 + 11.001 = 22.002 (tiap baris 11.000,55); per dokumen: 22.001 (22.001,10) |
| U7 | B | Pesanan ber-DPP nilai lain | Terbitkan faktur tanpa kode; setel `tax.kode_transaksi_bawaan_dpp_nilai_lain` = `"01"`, terbitkan untuk pesanan lain; pelanggan ber-`kode_transaksi: "02"`, terbitkan | `"04"`; `"01"`; `"02"` |
| U8 | B | `tax.kode_transaksi_diizinkan` tanpa `"07"` pada `ent_ksc` | Terbitkan faktur dengan kode `"07"` | 400 "Kode transaksi 07 tidak dipakai PT ini." |
| U9 | B | — | `PATCH` pelanggan `tax_profile: {id_type: "nik", nik: "12ab"}`; lalu `{id_type: "nik"}`; lalu NIK 16 angka | 400; 400; 200 dan faktur baru memuat `customer_tax.id_type == "nik"` |
| U10 | B | Pelanggan tanpa NPWP dan tanpa NIK | Terbitkan faktur | 200 seperti hari ini; `data_incomplete` memuat `identitas_pajak` |
| U11 | B | — | `sls`: pesanan `tax_override: "non_ppn"`; `mgr` tanpa alasan; `mgr` dengan alasan "Kawasan berikat" | 403; 400; 200 dengan PPN 0 dan `tax_override_reason` tersimpan |
| U12 | B | peran uji baku | **Tanpa Acuan** + `order.create` + `order.tax_override`: pesanan tanpa PPN beralasan; **Manajer Kosong**; **Sopir** | 200; 403; 403 |
| U13 | B | — | Pesanan di `ent_kanda` (non-PKP) | PPN 0; `tax_snapshot.is_pkp == false`, apa pun nilai kunci tarif |
| U14 | B | Transaksi antar-PT berharga Rp 12.000.000, penjual memakai DPP nilai lain | Hitung DPP faktur transaksi antar-PT yang dibuat sebelum U4 dan transaksi baru sesudah U4 | 11.000.000; 12.000.000; transaksi lama tetap 11.000.000 (faktor dibaca dari tempat yang sama, dipotret di transaksi) |
| U15 | B | — | Putaran `t1_config.py` untuk tujuh kunci; pembilang 0 | Lulus; 400 |
| U16 | layar (uji jalan) | Data acuan | Admin menjadwalkan tarif di Pusat Pengaturan › Pajak; Finance membuka rincian faktur lama | Jadwal tampil sebagai "berlaku sejak"; faktur lama menulis aturan saat terbit, tidak berubah |

## Langkah kerja

1. `backend/tests_mem/test_TXT1_pengaturan_pajak.py`: U1–U15; merah kecuali bagian angka U1 dan U13 (bawaan = perilaku lama) dan U12 (sudah ditutup PK-45).
2. Tujuh kunci + `tax_config_service`; `compute_tax` dan `compute_order_pricing` menerima `at` dan `snapshot`. U2, U4–U6.
3. Potret di pesanan dan faktur; hitung ulang dokumen lama dari potret; pemanggil antar-PT dan simulator. U3, U14.
4. Kode transaksi dari pengaturan dan pelanggan; data pajak pelanggan; `data_incomplete`. U7–U10.
5. Sakelar pesanan tanpa PPN di checkout; layar lain; U11, U12, U16; `scripts/audit_config_wiring.py`; gate; laporan
   dengan contoh hitung U1, U5, U6.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`tax_snapshot`, `customers.tax_profile`, field produk), `CODEBASE_MAP.md`
(`services/tax_config_service.py`), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("DPP nilai lain",
"kode transaksi", "aturan pajak saat terbit").

## Di luar lingkup

- Kapan faktur lahir, status "diganti", dokumen pajak retur, antrean "lengkapi data pajak" → TX-T2.
- PPN per barang (`tax_treatment` dipakai menghitung) dan harga termasuk PPN per pelanggan: belum ada unitnya —
  keduanya mengubah rumus, perlu konfirmasi konsultan pajak lebih dulu.
- Status PKP satu sumber dan `tax.efaktur_enabled` yang diturunkan darinya (KF-04) → KF-T3. Ekspor Coretax → TX-T3.

## Asumsi dan risiko

- `ASUMSI:` "tabel bertanggal berlaku" di rancangan dipenuhi dengan kemampuan berjadwal resolver yang sudah ada, bukan
  tabel baru. Tanggal sebelum baris pengaturan pertama memakai nilai yang berlaku sekarang.
- `ASUMSI:` faktor disimpan sebagai dua bilangan bulat (11 dan 12), bukan desimal, supaya tidak ada galat pembulatan.
- `ASUMSI:` bentuk NPWP 15/16 digit dan NIK 16 digit hanya menjadi peringatan **(konfirmasi konsultan pajak)**.
- `RISIKO:` dokumen lama tanpa potret dihitung ulang dengan faktor 11/12 walau pengaturan sudah diubah — itu disengaja.
  Membatalkan: `compute_tax` tanpa `at` dan `snapshot` berperilaku persis seperti sebelum unit ini.
