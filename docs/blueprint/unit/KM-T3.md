# KM-T3 — Bangun Lembar Insentif: dokumen keputusan dengan nominal diketik dan angka dasar dipotret

| | |
|---|---|
| Gelombang | Modul — Meja Insentif |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | KM-T2, KF-T6 |
| Menutup temuan | KM-05 |
| Keputusan | K-25 (K-19 … K-24 lewat versi definisi yang dipotret) |
| Standar | §2.3, §3.1 (Z1, Z2, Z4, Z6), §3.2, §3.4 (N1, N2, N4, N5), §4 (L1–L4, L7, L8), §5 (D3, D4, D5, D7, D9), §6 |
| Lingkungan uji | keduanya (B untuk alur; A untuk nomor unik dan dua pengesahan bersamaan) |

## Tujuan

Keputusan insentif punya dokumennya: satu lembar per PT per periode bayar, berisi baris per sales dan komponen. Nominal
**diketik orang**; angka dasar (target, omzet, pencairan, kualitas harga) dipotret saat baris dibuat dan tidak berubah
setelah lembar disahkan, walau data sumbernya berubah. Unit ini belum menjurnal dan belum menyentuh gaji (KM-T4).

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

- Insentif hari ini satu angka hasil mesin, dihitung ulang tiap diminta dan tidak disimpan:
  `backend/routers/crm.py:294` (`get_commission`) → `backend/services/sales_force_service.py:189`
  (`compute_commission`). Tidak ada tempat mengetik nominal, mencatat alasan, atau mengesahkan.
- Angka akrual juga dihitung saat tombol ditekan, jadi berubah mengikuti data: `backend/services/gl_service.py:2913`
  (`compute_commission`), dipicu `backend/routers/crm.py:321` (`post_incentive_gl`).
- Skema lama menyimpan `status: "draft"` yang tidak pernah berpindah: `backend/routers/crm.py:444` (`status`).
- Angka sumber bisa berubah mundur: batal kwitansi menulis ulang riwayat bayar pesanan,
  `backend/services/ar_receipt_service.py:739` (`paid_total`) (ditutup PK-19); retur dan serah-terima pelanggan
  mengubah hasil hitung periode lalu.
- Antrean Pusat Persetujuan didaftarkan sebagai baris (kode, label, view, koleksi, saringan):
  `backend/services/approval_backlog_service.py:159` (`hr_payroll`); dibaca layar lewat
  `backend/routers/so_approvals.py:442` (`approvals_backlog`).
- Nomor dokumen per PT dibuat `next_doc_number`: `backend/services/hr_payroll_service.py:378` (`next_doc_number`);
  nomor wajib-unik terdaftar di `backend/indexes.py:366` (`UNIQUE_DOC_NUMBER_FIELDS`).
- Kunci idempotensi hanya berlaku untuk awalan terdaftar: `backend/idempotency.py:21` (`IDEMPOTENT_PREFIXES`).

Yang dipakai dari unit lain: pengumpul angka per sales (`incentive_achievement`, KM-T2), `incentive_components`,
`current_definition`, endpoint rekonsiliasi (KM-T1), `butuh_orang_kedua` dan `tolak_bila_pelaku_sama` (KF-T6).

## Perubahan

### Data

Koleksi baru `incentive_sheets` (per PT; masuk `SCOPED_COLLECTIONS`, `ENTITY_REGISTRY.md`, `scripts/verify_contract.py`).

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `id`, `number`, `entity_id` | teks | ya | `isheet_…`; nomor `INS-` per PT; PT dari konteks pengguna (N1) |
| `pay_period` | `YYYY-MM` | ya | Bulan penggajian yang akan memuat lembar ini |
| `title` | teks | tidak | Mis. "Insentif Oktober + Triwulan III" |
| `status` | teks | ya | `draft` · `submitted` · `approved` · `paid` · `cancelled` |
| `lines[]` | daftar | ya | Lihat tabel baris |
| `active_keys[]` | daftar teks | ya | `<sales_id>|<component_id>|<basis_period>` tiap baris bukan penyesuaian; dikosongkan saat `cancelled` |
| `totals` | `{lines, amount}` | ya | Banyak baris dan Σ nominal (rupiah bulat) |
| `prepared_by`, `submitted_by`, `approved_by` | `{id, name}` | sesuai status | Pelaku; `submitted_by.id` = pengaju untuk kontrol dua orang |
| `submitted_at`, `approved_at`, `created_at`, `updated_at` | waktu | sesuai status | — |
| `history[]` | daftar | ya | `{action, by_id, by_name, at, reason, from_status, to_status}`; hanya-tambah |

Baris (`lines[]`):

| Field | Arti |
|---|---|
| `id` | `iline_…`, tetap seumur baris |
| `sales_id`, `sales_name`, `employee_id` | Akun sales; karyawan tertaut (`hr_employees.user_id`), boleh kosong sampai KM-T4 |
| `component_id`, `component_code`, `component_name` | Dari `incentive_components` PT itu (harus aktif) |
| `basis_period_type`, `basis_period`, `basis_label` | Periode dasar, mis. `month` · `2026-10` · "Okt 2026"; `quarter` · `2026-Q3` · "Triwulan III 2026" |
| `snapshot` | Potret: `taken_at`, `definition_version`, `definition` (empat nilai), `target_sales`, `omzet`, `retur`, `omzet_bersih`, `pct_omzet`, `target_collection`, `uang_masuk`, `pct_pencairan`, `realisasi_harga_pct`, `porsi_bawah_acuan_pct`, `margin_pct`, `catatan_data`, `fingerprint` (SHA-256 dari daftar terurut `doc_id:amount` semua dokumen omzet, retur, dan uang masuk), `source_counts` |
| `amount` | Nominal rupiah bulat, **diketik**. Negatif hanya pada baris penyesuaian. Kosong selagi draf boleh |
| `note` | Wajib untuk baris penyesuaian |
| `is_adjustment`, `adjusts` | Baris penyesuaian dan rujukannya `{sheet_id, sheet_number, line_id}` ke baris lembar `approved`/`paid` untuk sales yang sama |
| `amount_prepared`, `approver_note` | Terisi bila pemutus mengoreksi nominal saat mengesahkan |

Indeks: unik `number` (ditambahkan ke `UNIQUE_DOC_NUMBER_FIELDS`); unik (`entity_id`, `active_keys`) supaya satu
(sales, komponen, periode dasar) tidak diputus dua kali di dua lembar; (`entity_id`, `pay_period`, `status`). Field
`gl_status` baru ditulis KM-T4. Tidak ada rumus: server tidak pernah mengisi `amount`.

Transisi status:

| Dari → ke | Aksi | Izin | Syarat |
|---|---|---|---|
| — → `draft` | Buat | `incentive.prepare` | PT tunggal |
| `draft` → `draft` | Tambah, ubah, hapus baris; segarkan angka dasar | `incentive.prepare` | — |
| `draft` → `submitted` | Ajukan | `incentive.prepare` | ≥ 1 baris; semua `amount` terisi; catatan penyesuaian terisi |
| `submitted` → `approved` | Sahkan (boleh mengoreksi nominal dengan catatan) | `incentive.approve` | `tolak_bila_pelaku_sama("lembar_insentif", lembar, aktor, entity_id, nominal=totals.amount, pengaju=[submitted_by.id])` |
| `submitted` → `draft` | Kembalikan | `incentive.approve` | Alasan ≥ 5 huruf |
| `draft` → `cancelled` | Batalkan | `incentive.prepare` | Alasan ≥ 5 huruf |
| `approved` → `paid` | — | — | Ditulis KM-T4 saat proses gaji yang memuatnya diposting |

Semua transisi memakai pembaruan bersyarat status lama. Lembar `approved`, `paid`, dan `cancelled` tidak bisa diubah;
koreksinya baris penyesuaian di lembar lain.

### Server

Berkas baru `backend/services/incentive_sheet_service.py`; endpoint di `routers/incentive.py`. Awalan `/api/incentive/`
ditambahkan ke `IDEMPOTENT_PREFIXES` (N4). PT lembar = PT dokumen, diadu dengan cakupan pengguna (`guard_doc`).

| Endpoint | Izin | Isi permintaan | Jawaban |
|---|---|---|---|
| `GET /api/incentive/sheets` | `incentive.view` | `pay_period?`, `status?`, `page`, `page_size` | `{items, total}` tanpa `lines[].snapshot` |
| `POST /api/incentive/sheets` | `incentive.prepare` | `{pay_period, title?, lines?: [{sales_id, component_id, basis_period_type, basis_period}]}` | Lembar `draft`; tiap baris dipotret |
| `GET /api/incentive/sheets/{id}` | `incentive.view` | — | Lembar + `drift[]` per baris: `{line_id, field, snapshot, current, diff}` untuk `omzet_bersih`, `uang_masuk`, `realisasi_harga_pct` yang kini berbeda dari potret |
| `POST …/{id}/lines` | `incentive.prepare` | `{sales_id, component_id, basis_period_type, basis_period, amount?, note?, is_adjustment?, adjusts?}` | Lembar terbaru |
| `PATCH …/{id}/lines/{line_id}` | `incentive.prepare` | `{amount?, note?}` | Lembar terbaru |
| `DELETE …/{id}/lines/{line_id}` | `incentive.prepare` | — | Lembar terbaru |
| `POST …/{id}/refresh` | `incentive.prepare` | — | Potret semua baris diambil ulang; `{changed: [line_id]}` |
| `POST …/{id}/submit` | `incentive.prepare` | — | Lembar `submitted` |
| `POST …/{id}/approve` | `incentive.approve` | `{corrections?: [{line_id, amount, note}]}` | Lembar `approved` |
| `POST …/{id}/return`, `…/{id}/cancel` | `incentive.approve`, `incentive.prepare` | `{reason}` | Lembar `draft`, `cancelled` |
| `GET …/{id}/export` | `incentive.view` | — | `.xlsx`: lembar "Lembar" (kolom layar) dan "Potret" (seluruh angka potret per baris) |
| `GET /api/incentive/sheets/adjustable-lines` | `incentive.prepare` | `sales_id` | Baris lembar `approved`/`paid` sales itu |

Potret diambil dengan memanggil pengumpul KM-T2 untuk (sales, jenis periode, periode dasar) dan `current_definition`;
hasilnya disalin apa adanya. `margin_pct` disimpan di potret tetapi hanya dikirim ke pemegang `incentive.view_margin`.
Antrean baru di `approval_backlog_service`: (`incentive_sheet`, "Lembar insentif menunggu pengesahan",
`incentive-sheets`, `incentive_sheets`, `{"status": "submitted"}`).

| Keadaan | Kode | Pesan |
|---|---|---|
| Mengubah lembar yang bukan draf | 409 | "Lembar {nomor} berstatus {label status}, jadi tidak bisa diubah." |
| Baris kembar (di lembar ini atau lembar lain yang masih berlaku) | 409 | "{sales} · {komponen} · {periode dasar} sudah ada di lembar {nomor}." |
| Ajukan dengan nominal kosong | 400 | "Isi nominal semua baris sebelum mengajukan." |
| Nominal negatif pada baris biasa | 400 | "Nominal negatif hanya untuk baris penyesuaian." |
| Penyesuaian tanpa rujukan sah atau tanpa catatan | 400 | "Baris penyesuaian harus merujuk baris lembar yang sudah disahkan dan diberi catatan." |
| Koreksi pemutus tanpa catatan | 400 | "Beri catatan untuk setiap nominal yang dikoreksi." |
| Komponen nonaktif atau milik PT lain | 400 | "Komponen ini tidak aktif di PT yang sedang dibuka." |
| Pengaju mengesahkan sendiri saat wajib dua orang | 403 | Pesan `dual_control` |
| Tanpa izin | 403 | Bentuk Z6, nama modul "Kinerja & Insentif" |

### Pengaturan

Aksi `lembar_insentif` ditambahkan ke `KONTROL_AKSI` di `config_catalog_kontrol.py` (lahir di KF-T6): label "Pengesahan
lembar insentif", punya nominal. Lahir dua kunci menurut `02` §2.3: `kontrol.lembar_insentif.min_orang` (bawaan "1",
K-25) dan `kontrol.lembar_insentif.batas_nominal` (bawaan 0); `consumers`: `incentive_sheet_service.py:approve_sheet`.

### Izin dan peran

| Izin | Label aksi | Peran bawaan |
|---|---|---|
| `incentive.prepare` | "Siapkan lembar insentif" | admin, manager, sales_admin, finance |
| `incentive.approve` | "Sahkan lembar insentif" | admin, manager |

Modul akses `incentive`: `nav` ditambah `incentive-sheets`. Sales tanpa izin `incentive.*` tidak bisa membuka lembar;
kartu miliknya dibangun KM-T5.

### Layar

Hub `hr-kpi-hub`, tab baru **Lembar Insentif** (view `incentive-sheets`) di antara Capaian dan Target & Aturan. Komponen
baru `frontend/src/features/incentive/IncentiveSheetsView.jsx` dan `frontend/src/features/incentive/IncentiveSheetDetail.jsx`.

- **Daftar:** saringan "Periode bayar" dan "Status"; kolom "Nomor", "Periode bayar", "Status", "Baris", "Total",
  "Penyiap", "Pemutus"; tombol "Buat lembar" (pop-up baku: "Periode bayar", "Judul (opsional)"). Lencana status: Draf ·
  Diajukan · Disahkan · Dibayarkan · Dibatalkan. Kosong: "Belum ada lembar insentif untuk saringan ini."
- **Dari Capaian:** tombol "Buat lembar insentif dari tampilan ini" (aktif bila ada sales dicentang dan pelaku memegang
  `incentive.prepare`) membuka pop-up "Periode bayar", "Komponen", "Periode dasar", lalu membuat lembar draf berisi satu
  baris per sales yang dicentang. Bila pencocokan angka KM-T1 merah, konfirmasi dulu: "Angka omzet atau pencairan belum
  cocok dengan pembukuan. Tetap buat lembar?"
- **Detail:** kolom "Sales", "Komponen", "Periode dasar", "Omzet / target", "Cair / target", "Realisasi harga",
  "Nominal" (isian uang berpemisah ribuan), "Catatan". Baris bisa dibuka: seluruh angka potret, "Dipotret {tanggal jam}
  WIB · definisi versi {n}", dan bila `drift` ada: "Berubah sejak dipotret: {kolom} {selisih}" (bahan penyesuaian, bukan
  perubahan otomatis). Tombol menurut status dan izin: "Tambah baris", "Tambah penyesuaian", "Segarkan angka dasar",
  "Ajukan", "Sahkan", "Kembalikan", "Batalkan", "Ekspor Excel".
- **Konfirmasi (N5):** Sahkan — "Sahkan lembar {nomor}? {n} baris · total Rp … · {nama PT}. Setelah disahkan, lembar
  tidak bisa diubah; koreksi dibuat sebagai penyesuaian di lembar berikutnya." Kembalikan dan Batalkan meminta alasan.
- Banner PT; "Buat lembar" mati saat "Semua PT" dengan petunjuk "Pilih satu PT dulu."

## Uji penerimaan

Fixture **F3** di `ent_kanda` (non-PKP), fakta sudah dibangun; angka capaian yang dihasilkan KM-T2: Andi Okt 2026 —
target omzet 800 jt, omzet 1.000 jt, target cair 750 jt, uang masuk 700 jt, realisasi harga 86,2 %; Andi Triwulan III —
2.400 jt, 2.600 jt, 2.250 jt, 2.300 jt, 88,0 %; Budi Okt — 500 jt, 500 jt, 450 jt, 520 jt, 100,0 %. Komponen: BLN
"Insentif Bulanan" (bulan), TW "Insentif Triwulan" (triwulan). Akun: `sa` (hanya `incentive.prepare`), `mgr` dan `adm`
(memegang keduanya).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | F3 | `sa`: buat lembar `pay_period` 2026-11 dengan tiga baris (Andi BLN 2026-10, Andi TW 2026-Q3, Budi BLN 2026-10); isi nominal 2.000.000, 3.000.000, 3.500.000 | `draft`; `totals.amount` 8.500.000 (2 + 3 + 3,5 jt); potret Andi BLN: `omzet` 1.000.000.000, `target_sales` 800.000.000, `uang_masuk` 700.000.000, `realisasi_harga_pct` 86,2; `amount` awal kosong (server tidak mengisi) |
| U2 | B | U1 | `sa`: ajukan; lalu `PATCH` nominal satu baris | `submitted`; `PATCH` 409 "Lembar … berstatus Diajukan, jadi tidak bisa diubah." |
| U3 | B | U2; `kontrol.lembar_insentif.min_orang` bawaan | `mgr`: sahkan | 200 `approved`; jumlah `journal_entries` tidak bertambah (unit ini tidak menjurnal) |
| U4 | B | U3; lalu nota kredit retur Rp 50.000.000 atas pesanan Andi bertanggal 25 Okt; bangun fakta | `GET` lembar | Potret tetap `omzet_bersih` 1.000.000.000; `drift` baris Andi BLN: `current` 950.000.000, `diff` −50.000.000 |
| U5 | B | Lembar draf baru berisi Andi BLN 2026-09; retur seperti U4 tetapi di September | `refresh` | `changed` memuat baris itu; potret mengikuti angka terbaru |
| U6 | B | `kontrol.lembar_insentif.min_orang` = "2" untuk `ent_kanda`; lembar diajukan `mgr` | `mgr` sahkan; lalu `adm` sahkan | 403 pesan `dual_control`; lalu 200 |
| U7 | B | Lembar diajukan `sa` | `mgr` sahkan dengan `corrections` Budi 3.000.000 tanpa catatan; lalu dengan catatan | 400; lalu 200: `amount` 3.000.000, `amount_prepared` 3.500.000, `totals.amount` 8.000.000 |
| U8 | B | U3 | `sa`: lembar kedua 2026-11 dengan baris Andi BLN 2026-10 | 409 "Andi · Insentif Bulanan · Okt 2026 sudah ada di lembar {nomor}." |
| U9 | B | U3 | `sa`: lembar 2026-12, baris penyesuaian Andi BLN −500.000 merujuk baris U1, dengan catatan; ulangi tanpa `adjusts`; ulangi baris biasa bernominal −1 | 200; 400; 400 "Nominal negatif hanya untuk baris penyesuaian." |
| U10 | B | Lembar `submitted` | `mgr`: kembalikan dengan alasan "cek Budi"; ulangi dengan alasan "x" | `draft`, `history` bertambah satu berisi alasan; yang kedua 400/422 |
| U11 | B | U3; ubah `insentif.dasar_omzet` `ent_kanda` menjadi `pesanan` | `GET` lembar | `snapshot.definition_version` dan `snapshot.definition.dasar_omzet` (`terkirim`) tidak berubah |
| U12 | B | Peran Tanpa Acuan ber-`incentive.prepare`; Manajer Kosong | Buat lembar; sahkan; Manajer Kosong `GET` daftar | 200; 403; 403 |
| U13 | B | Lembar milik `ent_ksc`; pengguna hanya ditugaskan di `ent_kanda` | `GET`, `submit` | 403 atau 404; status tidak berubah |
| U14 | B | Lembar `submitted` | `GET /api/approvals/backlog` | Antrean `incentive_sheet` berjumlah 1 |
| U15 | B | U3 | `GET …/export`; buka dengan `openpyxl` | Lembar "Lembar" tiga baris, total 8.500.000; lembar "Potret" memuat 1000000000 |
| U16 | A | Lembar `submitted` | Dua `approve` bersamaan; dua `POST` buat lembar bersamaan | Satu 200 dan satu 409; dua nomor berbeda |
| U17 | layar (uji jalan) | F3, login `mgr` | Capaian: centang Andi dan Budi → "Buat lembar insentif dari tampilan ini" → isi nominal → Ajukan → Sahkan | Konfirmasi menyebut "2 baris · total Rp …" dan nama PT; lencana "Disahkan"; isian nominal terkunci |

## Langkah kerja

1. `backend/tests_mem/test_KMT3_lembar_insentif.py`: U1–U15; merah karena fiturnya belum ada.
2. Koleksi, indeks, nomor `INS-`, izin dan modul akses, aksi kontrol `lembar_insentif`.
3. `incentive_sheet_service.py`: buat, baris, potret, segarkan, lalu transisi status dengan pembaruan bersyarat.
4. Endpoint, pesan galat, antrean Pusat Persetujuan, ekspor.
5. Layar daftar, detail, tombol di Capaian; uji jalan U17; U16 di lingkungan A; gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`incentive_sheets`); `CODEBASE_MAP.md`; `memory/PRD.md`; `docs/KN_13_NAVIGATION_MAP.md`;
`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("lembar insentif", "periode bayar", "periode dasar", "penyesuaian").

## Di luar lingkup

- Jurnal akrual, masukan komponen gaji, status `paid`, mematikan komisi otomatis → KM-T4 (H5).
- Kartu "Capaian & Insentif Saya" untuk sales → KM-T5.
- Rumus bantu dan kolom "Angka bantu" (rancangan `05` §4.3) tidak dibangun: tidak ada angka usulan dari sistem.
- Siapa berwenang menyetujui pada nominal berapa (batas per peran) → KP-T4.

## Asumsi dan risiko

- `ASUMSI:` lembar draf boleh dibatalkan (status `cancelled`) dengan alasan; rancangan tidak menyebutnya, dan penghapusan
  dokumen dilarang.
- `ASUMSI:` baris tanpa karyawan tertaut boleh disahkan di unit ini; KM-T4 yang mewajibkan tautan sebelum masuk gaji.
- `ASUMSI:` satu (sales, komponen, periode dasar) hanya boleh diputus sekali; tambahan berikutnya lewat penyesuaian.
- `RISIKO:` potret besar memperlambat daftar; karena itu daftar tidak mengirim `snapshot`. Membatalkan: cabut tab dan
  endpoint lembar; koleksi `incentive_sheets` tidak dibaca kode lain sebelum KM-T4.
