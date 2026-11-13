# TX-T2 — Pemicu faktur pajak yang bisa diatur, draf otomatis, status "diganti", dokumen pajak retur, dan pencocokan PPN

| | |
|---|---|
| Gelombang | Modul faktur pajak |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | TX-T1, PK-32 |
| Menutup temuan | TX-05 |
| Keputusan | K-32 |
| Standar | §2 (2.1, 2.2, 2.4), §3.1 (Z1, Z2), §3.4 (N1, N2, N4, N5), §4 (L1, L4, L8), §5 (D1, D2, D3, D7, D8), §6 |
| Lingkungan uji | keduanya |

Titik henti **H5**: unit selesai dengan bawaan `pesanan` (= perilaku hari ini). Mengubah pemicu untuk PT nyata adalah
keputusan pemilik **setelah** konsultan pajak mengonfirmasi butir bertanda **(konfirmasi konsultan pajak)**; tulis
pertanyaannya di `STATUS.md`.

## Tujuan

PT bisa memilih kapan faktur pajak lahir. Bila memilih "per surat jalan", draf faktur muncul sendiri tiap barang
keluar dan Finance tinggal memeriksa lalu menerbitkan. Faktur yang diganti keluar dari rekap dengan status yang jelas,
retur ber-PPN menghasilkan dokumen pajak retur, dan selisih antara faktur dan akun PPN keluaran selalu bisa dijelaskan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`. PK-45 (TX-01…04) dan PK-40 (keunikan, masa pajak) sudah mengubah berkas yang
sama; cek ulang di `HEAD`.

| Fakta | Jangkar |
|---|---|
| Faktur diterbitkan manual, satu untuk seluruh pesanan, sejak pesanan terkonfirmasi | `backend/routers/tax_invoices.py:51` (`issue_for_order`), `backend/services/tax_invoice_service.py:134` (`issue_tax_invoice`), `backend/services/tax_invoice_service.py:15` (`ELIGIBLE_ORDER_STATUSES`) |
| Satu faktur hidup per pesanan dijaga dengan cek-lalu-sisip. PK-40 menggantinya dengan field `active_key` (`so:{order_id}` · `ic:{…}`) ber-indeks unik `uq_fkt_active`, dicabut saat faktur diganti atau batal | `backend/services/tax_invoice_service.py:142` (`existing`) |
| Status yang ada: `normal` · `pengganti` · `batal`; faktur asli yang diganti hanya diberi `replaced_by_id` | `backend/services/tax_invoice_service.py:153` (`status`), `backend/services/tax_invoice_service.py:221` (`replaced_by_id`) |
| Membatalkan faktur pengganti mengosongkan `replaced_by_id` faktur asalnya | `backend/services/tax_invoice_service.py:244` (`replaces_id`) |
| Rekap PPN keluaran = Σ faktur berstatus bukan `batal` (PK-45 mengecualikan yang sudah diganti) | `backend/services/input_tax_service.py:125` (`out_q`) |
| Jurnal PPN keluaran lahir **per dokumen surat jalan**, porsi dari PPN pesanan | `backend/services/gl_service.py:1129` (`ACC_PPN_OUT`), `backend/services/gl_mapping_registry.py:54` (`penjualan.ppn_keluaran`) |
| Surat jalan ditulis lalu jurnalnya diposting di `dispatch_task` | `backend/services/shipment_service.py:149` (`post_order_revenue_and_cogs`) |
| Retur menghitung PPN dari rasio pesanan asal; tidak membuat dokumen pajak | `backend/services/return_service.py:259` (`order_ppn`) |
| Kunci amandemen pesanan bergantung pada adanya faktur | `backend/services/amendment_service.py:277` (`tax_invoices`) |
| Faktur antar-PT memakai koleksi yang sama dengan `source_type: "interco"` dan punya layar ganti sendiri | `backend/services/tax_invoice_service.py:189` (`interco`) |
| Layar Faktur Keluaran menyaring tiga status | `frontend/src/features/finance/TaxInvoices.jsx:29` (`STATUS_LABEL`) |

## Perubahan

### Data

`tax_invoices` — status menjadi `draf` · `normal` · `pengganti` · `diganti` · `batal`; field baru:

| Field | Tipe | Arti |
|---|---|---|
| `doc_kind` | `faktur` · `retur` | Bawaan `faktur`. `retur` = dokumen pajak retur **(nama dan bentuk resminya: konfirmasi konsultan pajak)** |
| `trigger` | `pesanan` · `surat_jalan` · `retur` | Asal dokumen |
| `active_key` (dari PK-40) | string | Kosakata diperluas: `so:{order_id}` (tetap) · `sj:{order_id}:{nomor surat jalan}` · `retur:{id nota kredit}`. Dimiliki dokumen hidup (`draf`, `normal`, `pengganti`); dicabut saat `diganti` atau `batal` — aturan PK-40 |
| `shipment_no`, `shipment_ids`, `credit_note_id`, `ref_tax_invoice_id` | — | Rujukan sumber dan faktur asal (untuk retur) |
| `status_before_replaced` | string | Status faktur asal sebelum menjadi `diganti`; dipakai saat penggantinya dibatalkan |
| `drafted_at`, `issued_at`, `issued_by`, `discard_reason` | — | Jejak daur hidup |

Indeks: tidak ada yang baru. `uq_fkt_active` (PK-40) kini juga menjaga satu dokumen hidup per surat jalan dan per
nota kredit, dan mencegah satu pesanan punya faktur per pesanan sekaligus draf per surat jalan lewat pemeriksaan di
`draft_for_shipment` dan `issue_tax_invoice`.

Skrip baru `scripts/migrate_tax_invoice_status.py` (`--dry-run`, `--undo`, idempoten; H3): mengisi `doc_kind` dan
`trigger` dokumen lama, dan mengubah faktur ber-`replaced_by_id` terisi menjadi `diganti` (dengan
`status_before_replaced`). Faktur antar-PT (`source_type: interco`) tidak disentuh.

### Server

`tax_invoice_service` — fungsi baru dan yang berubah:

| Fungsi | Perilaku |
|---|---|
| `async def draft_for_shipment(order_id: str, shipment_no: str) -> Optional[dict]` | Hanya bila pemicu PT = `surat_jalan`, pesanan ber-PPN di PT PKP, dan pesanan belum punya faktur hidup ber-`trigger: pesanan`. Idempoten lewat `active_key`. Angka dari **jurnal** surat jalan itu: `ppn_amount` = Σ kredit akun PPN keluaran; harga jual = Σ kredit pendapatan; `dpp` = harga jual × pembilang ÷ penyebut potret pesanan; baris barang = isi surat jalan |
| `async def issue_draft(fkt_id, actor, *, faktur_date=None, nsfp=None, kode_transaksi=None) -> dict` | `draf` → `normal`. Ditolak bila `data_incomplete` terisi; masa pajak diperiksa `tax_center_service.assert_masa_terbuka(entity_id, tanggal, aksi=…)` hasil PK-40 |
| `async def discard_draft(fkt_id, reason, actor) -> dict` | `draf` → `batal`, alasan wajib; sumbernya masuk daftar "tanpa faktur" di pencocokan |
| `replace_tax_invoice` | Faktur asal → `diganti` + `status_before_replaced`; pengganti berstatus `pengganti`. Membatalkan pengganti mengembalikan status asal |
| `async def draft_for_credit_note(credit_note: dict) -> Optional[dict]` | Dipanggil `credit_note_service.settle` (PK-32) untuk nota ber-PPN atas pesanan yang punya faktur terbit: draf `doc_kind: retur`, `ppn_amount` = PPN yang dibalik jurnal nota itu, `ref_tax_invoice_id` = faktur surat jalan terkait, atau faktur hidup terbaru pesanan itu **(kapan wajib dibuat: konfirmasi konsultan pajak)** |
| `input_tax_service.vat_summary` (saringan `saringan_keluaran_aktif` hasil PK-45 diganti) | Keluaran = Σ PPN `faktur` berstatus `normal`/`pengganti` − Σ PPN `retur` berstatus `normal`. `draf`, `diganti`, `batal` tidak dihitung |
| `async def output_reconciliation(entity_id: str, period: str) -> dict` | `{faktur_ppn, retur_ppn, gl_ppn, difference, causes: {surat_jalan_tanpa_faktur[], faktur_tanpa_jurnal[], retur_tanpa_dokumen[]}, unexplained}`; `gl_ppn` = kredit − debit akun `penjualan.ppn_keluaran` pada masa itu |

Kait: `dispatch_task`, sesudah jurnal surat jalan berhasil, memanggil `draft_for_shipment`; kegagalannya tidak
membatalkan surat jalan dan dipulihkan job harian baru `job_tax_draft_backfill` (memindai surat jalan berjurnal tanpa
dokumen pajak pada PT berpemicu `surat_jalan`). Kunci amandemen (`amendment_service.is_issued`) hanya menghitung faktur
`normal` dan `pengganti`.

| Endpoint | Izin | Isi | Jawaban / galat |
|---|---|---|---|
| `GET /api/tax-invoices?status=&doc_kind=` | `tax_invoice.view` | — | Mengenal status dan jenis baru |
| `POST /api/tax-invoices/{id}/issue` | `tax_invoice.create` | `{faktur_date?, nsfp?, kode_transaksi?}` | Faktur `normal`. 409 "Lengkapi data pajak pelanggan dulu: {daftar}."; 409 pesan masa pajak terkunci dari PK-40; 409 "Dokumen ini bukan draf." |
| `POST /api/tax-invoices/{id}/discard` | `tax_invoice.cancel` | `{reason}` | Draf `batal`; tanpa alasan → 400 "Alasan membuang draf wajib diisi." |
| `POST /api/tax-invoices/drafts/rebuild` | `tax_invoice.create` | `{period}` | `{created, skipped}`; idempoten |
| `GET /api/tax/output-reconciliation?period=&entity_id=` | `tax_invoice.view` | — | Hasil `output_reconciliation`; "Semua PT" → 400 "Pilih satu PT." |
| `POST /api/sales-orders/{id}/tax-invoice` (ada) | tetap | tetap | Bila pemicu PT bukan `pesanan` → 409 "PT ini menerbitkan faktur per surat jalan. Terbitkan dari antrean draf." |

Semua aksi ber-id mengadu PT dokumen dengan `guard_doc` (hasil PK-45); awalan `/api/tax-invoices` masuk
`IDEMPOTENT_PREFIXES`. Invarian baru INV-TAX-OUT-01 di `verify_data_integrity.py`: untuk tiap PT PKP dan tiap masa
yang punya faktur atau jurnal PPN keluaran, `unexplained == 0`; sebab yang terjelaskan dicetak sebagai peringatan.

### Pengaturan

| Field | `tax.pemicu_faktur` |
|---|---|
| group · type | `pajak` · `enum` `pesanan` · `surat_jalan` · `uang_muka` |
| default | `pesanan` |
| scopes | `("global", "entity")` |
| label | "Faktur pajak dibuat saat" |
| help | "'Per pesanan' = diterbitkan orang untuk seluruh pesanan, seperti sekarang. 'Per surat jalan' = draf muncul sendiri tiap barang keluar." |
| impact | "Mengubah kapan dan berapa banyak faktur per pesanan. Pesanan yang sudah berfaktur per pesanan tidak diberi draf per surat jalan." |
| example | "Per surat jalan · pesanan dikirim dua kali → dua draf faktur" |
| risk / requires_reason | `high` / ya |
| permission | `("accounting", "manage")` |
| consumers | `services/tax_invoice_service.py:draft_for_shipment`, `services/tax_invoice_service.py:issue_tax_invoice` |

Nilai `uang_muka` terdaftar (K-32) tetapi **ditolak saat disimpan**: jurnal PPN hari ini baru lahir saat surat jalan,
jadi faktur atas uang muka menuntut jurnal baru yang arah dan akunnya belum ditetapkan (H4) **(konfirmasi konsultan
pajak)**. Pesan: "Pemicu 'uang muka' belum bisa dipakai: menunggu ketetapan jurnal PPN atas uang muka."

### Izin dan peran

Tidak ada pasangan baru (`tax_invoice.view/create/update/replace/cancel` yang ada).

### Layar

**Akuntansi & Pajak › Pajak › Faktur Keluaran** (`TaxInvoices.jsx`):

- Chip saringan: "Semua", **Draf**, "Normal", "Pengganti", **Diganti**, "Batal", dan sakelar jenis "Faktur" · **Dokumen
  retur**. Kolom baru "Sumber" (nomor pesanan atau surat jalan, bisa dibuka — L8).
- Baris draf: tombol **Terbitkan** (pop-up "Tanggal faktur", "Kode transaksi", "NSFP (boleh menyusul)"; konfirmasi
  menyebut PT dan PPN) dan **Buang draf** (alasan wajib). Lencana "Data pajak belum lengkap" membuka kartu pelanggan.
- Panel **Pencocokan PPN keluaran** per masa: "PPN di faktur", "PPN di dokumen retur", "PPN di buku besar", "Selisih",
  lalu daftar "Surat jalan tanpa faktur", "Faktur tanpa jurnal", "Retur tanpa dokumen pajak"; baris "Belum terjelaskan"
  berwarna peringatan bila bukan 0.
- Detail pesanan: tombol terbit faktur manual disembunyikan bila pemicu PT `surat_jalan`, diganti tautan "Lihat draf
  faktur ({n})". Keadaan kosong antrean draf: "Tidak ada draf faktur."

## Uji penerimaan

Fixture **T1** (`ent_ksc`, tarif efektif 11 %): pesanan S1 harga jual Rp 10.000.000, PPN 1.100.000, total 11.100.000;
surat jalan SJ-1 (40 %) berjurnal pendapatan 4.000.000 + PPN keluaran 440.000; SJ-2 (60 %) berjurnal 6.000.000 +
660.000. Pelanggan berdata pajak lengkap kecuali disebut.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | T1, pemicu bawaan | `draft_for_shipment(S1, "SJ-1")`; lalu terbit manual per pesanan | Tidak ada draf; faktur `normal` PPN 1.100.000 — sama dengan hari ini |
| U2 | B | T1; `tax.pemicu_faktur` = `surat_jalan` pada `ent_ksc` | `draft_for_shipment(S1, "SJ-1")` | Satu `draf`: PPN 440.000, harga jual 4.000.000, `dpp` 3.666.666,67 (4.000.000 × 11 ÷ 12), `active_key` `sj:S1:SJ-1`; rekap masa itu keluaran 0 |
| U3 | B | U2 | Panggil lagi; lalu `POST …/{id}/issue` | Tetap satu draf; lalu `normal`; rekap keluaran 440.000 |
| U4 | B | U3 | `draft_for_shipment(S1, "SJ-2")` + terbitkan | PPN 660.000; Σ dua faktur 1.100.000 = PPN pesanan |
| U5 | B | U3 (SJ-2 berjurnal, drafnya belum terbit) | `GET /api/tax/output-reconciliation` masa itu | `faktur_ppn` 440.000; `gl_ppn` 1.100.000; `difference` 660.000 seluruhnya di `surat_jalan_tanpa_faktur` (SJ-2); `unexplained` 0; INV-TAX-OUT-01 hijau |
| U6 | B | U3 | Sisipkan jurnal manual kredit akun PPN keluaran Rp 50.000 pada masa itu | `unexplained` 50.000; INV-TAX-OUT-01 merah menyebut PT dan masa |
| U7 | B | U3 | Ganti faktur SJ-1; baca rekap; batalkan penggantinya | Asal `diganti`, pengganti `pengganti` PPN 440.000; rekap tetap 440.000 (bukan 880.000); setelah batal, asal kembali `normal` |
| U8 | B | U2 dengan pelanggan tanpa NPWP dan NIK | `issue`; lengkapi data; `issue` lagi | 409 "Lengkapi data pajak pelanggan dulu: identitas pajak."; 200 |
| U9 | B | U3; nota kredit atas SJ-1: harga jual 1.000.000 + PPN 110.000 (jurnal membalik PPN 110.000) | `draft_for_credit_note`; terbitkan; baca rekap | Draf `doc_kind: retur` PPN 110.000 ber-`ref_tax_invoice_id` faktur SJ-1; rekap keluaran 330.000 (440.000 − 110.000) |
| U10 | B | U2 | `POST /api/sales-orders/{S1}/tax-invoice` | 409 "PT ini menerbitkan faktur per surat jalan…" |
| U11 | B | — | Simpan `tax.pemicu_faktur` = `uang_muka` | 400 dengan pesan "belum bisa dipakai"; nilai tersimpan tidak berubah |
| U12 | B | U2; pesanan serupa di PT PKP ketiga (pemicu bawaan) dan pesanan di `ent_kanda` (non-PKP) | `draft_for_shipment` untuk keduanya | Tidak ada draf di keduanya — PT lain tidak berubah; non-PKP tidak pernah diberi draf |
| U13 | B | U2; masa pajak bulan itu ditandai dilaporkan (PK-40) | `issue` dengan tanggal faktur di masa itu | 409 "Masa pajak … sudah ditandai dilaporkan…"; dokumen tetap `draf` |
| U14 | B | peran uji baku; satu draf | **Tanpa Acuan** + `tax_invoice.create`: `issue`; **Manajer Kosong**; **Sopir**; pengguna PT lain berizin sama | 200; 403; 403; 403 atau 404 |
| U15 | B | fixture: faktur lama ber-`replaced_by_id` | Fungsi migrasi dua kali | Faktur itu `diganti` ber-`status_before_replaced: normal`, tanpa `active_key`; putaran kedua tanpa perubahan; rekap sebelum = sesudah |
| U16 | B | — | Putaran `t1_config.py` untuk `tax.pemicu_faktur` | Lulus untuk `pesanan` dan `surat_jalan`; lapisan PT hanya mengubah PT itu |
| U17 | A | U2 | Dua `draft_for_shipment` bersamaan untuk SJ-1 | Satu draf (indeks unik menolak yang kedua tanpa galat ke pemanggil) |
| U18 | layar (uji jalan) | Data acuan, pemicu `surat_jalan` pada satu PT uji | Kirim sebagian pesanan lewat alur gudang; Finance membuka Faktur Keluaran | Draf muncul dengan sumber surat jalan; setelah diterbitkan panel pencocokan menunjukkan selisih terjelaskan |

## Langkah kerja

**Serah-terima (a) — jalur baru; perilaku terbit dan rekap lama belum disentuh.**

1. `backend/tests_mem/test_TXT2_pemicu_faktur.py`: U1–U6, U8–U14, U16; merah kecuali U1.
2. Field, status `draf`, kosakata `active_key` baru; `tax.pemicu_faktur`.
3. `draft_for_shipment`, `issue_draft`, `discard_draft`, `draft_for_credit_note`, endpoint.
4. `output_reconciliation` + INV-TAX-OUT-01 (peringatan dulu).

**Serah-terima (b) — alihkan dan matikan jalur lama.**

5. U7, U15 ditulis; merah.
6. `replace_tax_invoice` memakai `diganti`; `vat_summary` memakai himpunan status baru; skrip migrasi; kait di
   `dispatch_task` + job harian; kunci amandemen.
7. Layar; INV-TAX-OUT-01 menjadi wajib hijau; U17 di lingkungan A; U18; gate penuh; laporan memuat contoh angka T1
   (surat jalan → jurnal → faktur → rekap) dan daftar pertanyaan konsultan pajak + H5.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`tax_invoices`: status, field, indeks), `CODEBASE_MAP.md` (skrip migrasi, job baru),
`memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("draf faktur", "diganti", "dokumen pajak retur").

## Di luar lingkup

- Faktur atas uang muka dan faktur gabungan bulanan: menunggu ketetapan jurnal dan konsultan pajak; belum ada unitnya.
- Faktur antar-PT (`source_type: interco`) tetap di layar Antar Entitas dan tidak disentuh unit ini.
- Ekspor Coretax, PPh 23, bukti potong → TX-T3. Kunci masa pajak → PK-40. Mesin nota kredit → PK-32.

## Asumsi dan risiko

- `ASUMSI:` angka draf per surat jalan diambil dari jurnal surat jalan, bukan dihitung ulang, supaya Σ faktur selalu
  bisa dicocokkan dengan akun PPN keluaran.
- `ASUMSI:` dokumen pajak retur disimpan di `tax_invoices` dengan `doc_kind: retur` (bukan koleksi baru), dan lahir
  sebagai draf yang diterbitkan orang **(konfirmasi konsultan pajak: bentuk, penomoran, dan kapan wajib)**.
- `ASUMSI:` pesanan yang sudah berfaktur per pesanan tidak diberi draf per surat jalan saat PT berganti pemicu.
- `ASUMSI:` draf yang dibuang tidak dibuat ulang otomatis; sumbernya tetap tampil di "Surat jalan tanpa faktur".
- `RISIKO:` di mode `pesanan`, faktur terbit sebelum barang dikirim sehingga selisih masa wajar terjadi; invarian hanya
  memerah untuk selisih yang tidak terjelaskan. Membatalkan (b): kembalikan `vat_summary` dan `replace_tax_invoice`;
  status `diganti` dipetakan balik oleh skrip yang sama dengan `--undo`.
