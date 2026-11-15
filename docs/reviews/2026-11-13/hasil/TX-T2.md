# TX-T2 — Pemicu faktur pajak yang bisa diatur, draf otomatis, status "diganti", dokumen pajak retur, dan pencocokan PPN

- Commit awal: `cd5aa59` (worktree kerja, HEAD terlepas = basis B)        - Commit akhir: (a) `38b5c9b`, (b) `84744dc`, cek layar `15d3258`
- Branch: `claude/nifty-carson-jjx3c8`        - Digabung pelaksana ke HEAD tujuan `5f193df` (lihat "Penggabungan")
- ID ditangani: TX-05 (spesifikasi `docs/blueprint/unit/TX-T2.md`; keputusan K-32; standar `02_STANDAR.md` §2.1/2.2/2.4,
  §3.1 Z1/Z2, §3.4 N1/N2/N4/N5, §4 L1/L4/L8, §5 D1/D2/D3/D7/D8, §6)
- Risiko tinggi → dua serah-terima (`00` §8). **(a)** jalur baru (pengaturan, draf, terbit/buang, dokumen retur, bangun
  ulang, pencocokan, INV-TAX-OUT-01 sebagai peringatan) — penerbitan & penggantian per pesanan lama tidak berubah.
  **(b)** status `diganti`, rekap himpunan status baru, kait `dispatch_task` + `credit_note_service.settle`, job harian,
  kunci amandemen, skrip migrasi, layar, INV-TAX-OUT-01 wajib hijau.
- **Titik henti H5**: unit selesai dengan bawaan `pesanan` (= perilaku hari ini). Tidak ada PT nyata yang diubah pemicunya
  di kode/seed; uji memakai lapisan PT di database tiruan. Pertanyaan konsultan pajak di bagian "Menunggu pemilik".
- **H4**: tidak ada tarif/faktor/akun baru. Angka draf diambil dari jurnal yang sudah ada (akun pemetaan PT), faktor DPP
  dari potret pajak pesanan (TX-T1). Pilihan `uang_muka` ditolak saat disimpan (jurnal PPN atas uang muka belum ditetapkan).
- **H3**: skrip `scripts/migrate_tax_invoice_status.py` hanya disiapkan dan diuji di database tiruan.

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca pada `3132cc4`; dicek di `cd5aa59`)

| Fakta | Hasil di `cd5aa59` |
|---|---|
| Faktur diterbitkan manual, satu untuk seluruh pesanan | Berlaku, bergeser — `routers/tax_invoices.py:56` (`issue_for_order`), `services/tax_invoice_service.py:235` (`issue_tax_invoice`), `:17` (`ELIGIBLE_ORDER_STATUSES`) |
| Satu faktur hidup per pesanan: `active_key` + `uq_fkt_active` (PK-40) | Berlaku — `tax_invoice_service.py:61` (`kunci_aktif_keluaran`), jalan cepat `:245` |
| Status `normal`·`pengganti`·`batal`; asal yang diganti hanya diberi `replaced_by_id` | Berlaku — `:260`, `:353` (klaim `replaced_by_id`) |
| Batal pengganti mengosongkan `replaced_by_id` asal | Berlaku — `cancel_tax_invoice` `:405–:426` |
| Rekap keluaran = faktur bukan batal & belum diganti (PK-45) | Berlaku — `input_tax_service.py:194` (`saringan_keluaran_aktif`, `tax_invoice_service.py:42`) |
| Jurnal PPN keluaran per surat jalan | Berlaku — `gl_service.py:172` (`ACC_PPN_OUT`), `:1484` (`post_shipment_revenue`); `gl_mapping_registry.py:73` |
| Surat jalan ditulis lalu jurnal di `dispatch_task` | Berlaku, bergeser — `shipment_service.py:154` (`post_durable` → `post_order_revenue_and_cogs`) |
| Retur menghitung PPN dari rasio pesanan, tanpa dokumen pajak | Berlaku, bergeser — `return_service.py:346` (`order_ppn`); nota retur kini lewat mesin PK-32 `credit_note_service.issue/settle` |
| Kunci amandemen bergantung pada adanya faktur | Berlaku — `amendment_service.py:293` (`status $nin batal/cancelled`) |
| Faktur antar-PT di koleksi sama (`source_type: interco`) | Berlaku — `tax_invoice_service.py:323`; asal antar-PT yang diganti tetap `normal` + `replaced_by_id` (`interco_tax_service.py:334`) |
| Layar menyaring tiga status | Berlaku — `TaxInvoices.jsx:31` (`FILTERS`; TX-T1 sudah: 8 kolom, status di bawah nomor) |

## TX-05 — faktur hanya per pesanan, faktur asal yang diganti tidak berstatus jelas, retur tanpa dokumen pajak, selisih PPN tidak terjelaskan

- Berlaku di HEAD: ya (bukti merah `bukti/TX-T2/a_merah_kode_lama.txt`: kunci `tax.pemicu_faktur` tidak ada di registry,
  `draft_for_shipment` tidak ada; `bukti/TX-T2/b_merah_di_kode_a.txt`: asal tanpa `status_before_replaced`, rekap masih
  `$nin`, tanpa kait/job/skrip).
- Akar masalah: satu-satunya jalan lahir faktur adalah tombol per pesanan; status asal yang diganti tidak ditulis; tidak
  ada dokumen pajak untuk nota kredit ber-PPN; pembanding buku besar PK-40 hanya angka selisih tanpa penyebab.
- Perubahan perilaku (sebelum → sesudah):
  - **Pengaturan `tax.pemicu_faktur`** (`config_catalog_core.py`, kelompok `pajak-pembukuan`/`pajak`, `global`+`entity`,
    risiko tinggi, wajib alasan, izin `accounting.manage`): `pesanan` (bawaan) · `surat_jalan` · `uang_muka` — yang terakhir
    ditolak `config_resolver.set_value` → `tax_config_service.periksa_pemicu_faktur` (400 "Pemicu 'uang muka' belum bisa
    dipakai: menunggu ketetapan jurnal PPN atas uang muka."). Pemakai: `draft_for_shipment`, `issue_tax_invoice`.
  - **Data `tax_invoices`**: status `draf`·`normal`·`pengganti`·`diganti`·`batal`; `doc_kind` (`faktur`·`retur`), `trigger`
    (`pesanan`·`surat_jalan`·`retur`), `shipment_no`, `shipment_ids`, `credit_note_id`, `ref_tax_invoice_id`,
    `journal_entry_ids` (sumber angka), `status_before_replaced`, `drafted_at`, `issued_at`, `issued_by`,
    `discard_reason`. `kunci_aktif_keluaran`: `so:` · `sj:{pesanan}:{nomor SJ}` · `retur:{nota}` · `ic:`; dimiliki
    `draf`/`normal`/`pengganti`. Tanpa indeks baru (`uq_fkt_active` PK-40 menjaga per SJ dan per nota).
  - **`draft_for_shipment(order_id, shipment_no)`**: hanya PT berpemicu `surat_jalan`, pesanan ber-PPN di PT PKP, belum
    berfaktur per pesanan. Angka dari **jurnal `shipment_revenue`** semua catatan surat jalan bernomor itu (dan pembaliknya):
    PPN = kredit−debit akun `penjualan.ppn_keluaran`, harga jual = kredit−debit `penjualan.pendapatan` (pemetaan PT,
    `known_codes`); `dpp` = harga jual × pembilang ÷ penyebut potret pesanan (dibulatkan `round_money` potret); baris =
    isi surat jalan. Idempoten (draf yang sama disegarkan bila surat jalan satu nomor bertambah baris —
    `dispatch_order_batch`); kalah balapan indeks → dokumen pemegang kunci, tanpa galat. Draf yang dibuang tidak dibuat ulang.
  - **`issue_draft`** (`POST /api/tax-invoices/{id}/issue`, `tax_invoice.create`, `guard_doc`): draf → `normal`; 409 "Dokumen
    ini bukan draf."; data pajak pembeli SAAT INI dihitung ulang → 409 "Lengkapi data pajak pelanggan dulu: {daftar}.";
    kode sah PT (400); masa pajak `assert_masa_terbuka` (409 PK-40); NSFP kembar 409; draf SJ ditolak bila pesanan
    sementara itu berfaktur per pesanan. Tanggal bawaan = tanggal buku jurnal sumbernya.
  - **`discard_draft`** (`POST …/{id}/discard`, `tax_invoice.cancel`): alasan wajib (400 "Alasan membuang draf wajib
    diisi."), draf → `batal` + `discard_reason`, kunci dicabut.
  - **`draft_for_credit_note(credit_note)`**: nota kredit `issued`/`posted` (mesin PK-32) ber-PPN atas pesanan PKP yang
    punya faktur terbit → draf `doc_kind: retur`; PPN = debit−kredit akun PPN keluaran pada jurnal nota
    (`journal_entry_id`), `ref_tax_invoice_id` = faktur SJ yang roll-nya dikembalikan (roll nota/retur ∈ `shipments.rolls`),
    selain itu faktur hidup terbaru pesanan; kode transaksi = kode faktur asal. Tidak membuat jalur nota sendiri.
  - **`rebuild_drafts`** (`POST /api/tax-invoices/drafts/rebuild {period}`, `tax_invoice.create`, PT aktif; "Semua PT" →
    400 "Pilih satu PT."): surat jalan berjurnal masa itu (bila pemicu PT `surat_jalan`) + nota kredit berjurnal masa itu →
    `{created, skipped, reasons}`; idempoten.
  - **`output_reconciliation(entity_id, period)`** (`GET /api/tax/output-reconciliation`, `tax_invoice.view`, satu PT):
    `{faktur_ppn, retur_ppn, gl_ppn, difference, causes: {surat_jalan_tanpa_faktur[], faktur_tanpa_jurnal[],
    retur_tanpa_dokumen[]}, unexplained, unexplained_journals[], accounts}` — lihat "Model pencocokan".
  - **Rekap PPN** (`vat_summary`): (a) draf tidak dihitung, retur dikurangkan (dibutuhkan U2/U9; data lama tidak berubah);
    (b) himpunan status baru: faktur `normal`/`pengganti` (belum diganti) − retur `normal`. Kartu keluaran memuat
    `faktur_ppn`, `retur_ppn`, `retur_count`.
  - **`replace_tax_invoice`** (b): asal → `diganti` + `status_before_replaced`; pengganti faktur SJ menyalin angka &
    rujukan SJ (bukan seluruh pesanan, sudah di (a)); batal pengganti memulihkan status asal. Draf/retur tidak bisa
    diganti (409); draf tidak bisa dibatalkan/diberi NSFP (409 → Buang draf / isi saat terbit).
  - **Kait (b)**: `shipment_service.dispatch_task` sesudah jurnal → `draft_for_shipment` (gagal tidak membatalkan surat
    jalan); `credit_note_service.settle` sesudah `posted` → `draft_for_credit_note`; job harian `tax_draft_backfill`
    (01.40, `scheduler_service.JOBS`) memulihkan surat jalan/nota berjurnal tanpa dokumen pajak apa pun.
  - **Kunci amandemen** (b): hanya faktur `normal`/`pengganti` (bukan draf, `diganti`, dokumen retur).
  - **Meja Finance** (b): antrean "Siap terbitkan Faktur Pajak" tidak memuat pesanan PT berpemicu `surat_jalan` (tombolnya
    akan 409). **`/settings/effective`** bagian `tax` memuat `pemicu_faktur` (detail pesanan).
  - **INV-TAX-OUT-01** (`verify_data_integrity.py`, lapisan `tax`): tiap PT PKP × masa ber-faktur/jurnal PPN →
    `unexplained == 0`; sebab terjelaskan = WARN. (a) WARN, (b) **FAIL** (`INV_TAX_OUT_WAJIB = True`). FKT-3 kini per
    `active_key` (+ pesanan tidak boleh berfaktur per pesanan sekaligus per SJ).
  - **Skrip H3** `scripts/migrate_tax_invoice_status.py` (`--dry-run`, `--undo`, idempoten, catatan `tx_t2_migrasi`):
    `doc_kind`/`trigger` dokumen lama; asal ber-`replaced_by_id` → `diganti`. Antar-PT tidak disentuh.
  - **Layar**: lihat "Cek layar".

### Model pencocokan (satuan sumber)

Jurnal ber-PPN keluaran masa itu dan dokumen pajak terbit masa itu dikelompokkan per satuan: faktur per surat jalan →
(pesanan, nomor SJ); per pesanan → pesanan (jurnal `shipment_revenue`/`sales_order`/`amendment_debit_note` pesanan
yang punya faktur per pesanan terbit, atau di PT berpemicu pesanan); nota kredit (jurnal `sales_return`/
`amendment_credit_note` ↔ nota lewat `journal_entry_id`; pembalik lewat `ref.reverses_entry_id`) → nota; antar-PT
(`interco_transaction`) → pasangan; retur antar-PT (`interco_return`) → retur tanpa dokumen. Sumbangan satuan =
jurnal − dokumen (retur bertanda negatif); > 0 → "surat jalan tanpa faktur", < 0 → "faktur tanpa jurnal" (nota: < 0 →
"retur tanpa dokumen pajak"). Jurnal bersumber lain (manual, penyesuaian) = **belum terjelaskan**. Selisih masa di mode
pesanan (faktur terbit sebelum kirim) = faktur tanpa jurnal di masa terbit + surat jalan tanpa faktur di masa kirim.

### Contoh angka (fixture T1, `ent_ksc`, efektif 11 %) — surat jalan → jurnal → faktur → rekap

| Langkah | Hitungan tangan | Hasil uji |
|---|---|---|
| Pesanan S1 | 100 m × 100.000 = 10.000.000; DPP 10.000.000 × 11/12 = 9.166.666,67; PPN 12 % × DPP = 1.100.000; total 11.100.000 | `compute_order_pricing` sama |
| SJ-1 40 m → jurnal | porsi 0,4: Dr 1-1200 4.440.000 / Cr 4-1000 4.000.000 / Cr 2-1200 440.000 | U2 |
| Draf SJ-1 | PPN = Σ kredit 2-1200 = 440.000; harga jual 4.000.000; DPP 4.000.000 × 11 ÷ 12 = 3.666.666,67; total 4.440.000; rekap masa 0 (draf) | U2 |
| Terbit SJ-1 | rekap keluaran 440.000 | U3 |
| SJ-2 60 m (penutup) → jurnal | 10.000.000 − 4.000.000 = 6.000.000; PPN 1.100.000 − 440.000 = 660.000 | U5 |
| Pencocokan (SJ-2 belum terbit) | buku besar 440.000 + 660.000 = 1.100.000; faktur 440.000; selisih 660.000 = SJ-2 tanpa faktur; belum terjelaskan 0 | U5 |
| + jurnal manual Cr 2-1200 50.000 | buku besar 1.150.000; selisih 710.000; terjelaskan 660.000; belum 50.000 → INV merah menyebut PT & masa | U6 |
| Nota kredit 10 m atas SJ-1 | 1.000.000 + PPN 110.000: Dr 4-1000 1.000.000 / Dr 2-1200 110.000 / Cr 1-1200 1.110.000; dokumen retur PPN 110.000, DPP 916.666,67, rujuk faktur SJ-1; rekap 440.000 − 110.000 = 330.000; buku besar 1.100.000 − 110.000 = 990.000 | U9 |
| Terbit SJ-2 | Σ faktur 440.000 + 660.000 = 1.100.000 = PPN pesanan; selisih 0 | U4 |

- Berkas berubah: lihat tabel serah-terima di bawah.
- Pengujian: tabel "Uji penerimaan". tests_mem W **1924 lulus / 2 dilewati / 2 xfail** (basis) → (a) **1944 / 2 / 2** →
  (b) 1953 + 1 gagal (`test_PK09_entitas.py::test_U11` — fixture berstatus `issued`, lihat Menyimpang 8) → disesuaikan,
  modul itu 19/19; T (HEAD `5f193df`): **1954 / 2 / 2**. jest W 957 → **963**; T **964** (35 suite gagal dimuat
  `cmdk`/`@radix-ui` = kendala lingkungan, sama dengan basis).
- Bukti UI: belum dipotret (integrator, 1280/1024/390 px); uji komponen `txt2FakturDraf.test.js` 7/7.
- Fixture vs proses: pesanan, surat jalan, retur, faktur lama (U15), masa terkunci lewat API kunci; pesanan disisip
  sesudah dihitung `compute_order_pricing`; jurnal surat jalan lewat `post_order_revenue_and_cogs`; nota kredit lewat
  `credit_note_service.issue/settle`; kait surat jalan lewat `dispatch_task` asli (pemindahan roll ditiru); pengaturan,
  terbit, buang, bangun ulang, pencocokan, ganti, batal, PATCH pelanggan, meja Finance lewat API.
- Dampak pada modul terkait: rekap PPN Pusat Pajak (keluaran = faktur − retur); kunci amandemen; meja Finance; detail
  pesanan; nota kredit ber-PPN membuat draf retur (hanya bila pesanan punya faktur terbit di PT PKP).
- Keterbatasan / yang belum diuji: U17 lapis A ditulis, belum dijalankan (MongoDB asli); U18 uji jalan belum
  (integrator); pemindahan roll/gerbang RFID di `dispatch_task` tidak diuji (H7, ditiru).
- Status: implemented_pending_review

## Serah-terima (a) — jalur baru

Salinan: `scratchpad/TX-T2_a_state/` (`files/`, `FILES.txt`, `BASIS.txt` = `cd5aa59`); tergabung di
`scratchpad/TX-T2_a_merged/` (`BASIS.txt` = `5f193df`; semua berkas sama di basis dan HEAD → disalin, `CODEBASE_MAP.md`
dibangkitkan ulang). Uji (a) di T: TX-T2 + KF-T1 + PK-40 + PK-45 70/70 (`bukti/TX-T2/a_tergabung_T_subset.txt`).

| Berkas | Isi |
|---|---|
| `backend/config_catalog_core.py` | kunci `tax.pemicu_faktur` |
| `backend/services/config_resolver.py` | `set_value` memanggil penjaga pemicu |
| `backend/services/tax_config_service.py` | `PEMICU_BELUM_BISA`, `periksa_pemicu_faktur` |
| `backend/services/tax_invoice_service.py` | kosakata/pesan; `saringan_retur_aktif`; `kunci_aktif_keluaran` (sj:/retur:); `issue_tax_invoice` (pemicu, cek per-SJ, `doc_kind`/`trigger`/`issued_*`); `set_nsfp`/`replace`/`cancel` menolak draf, retur tidak diganti, pengganti SJ menyalin angka SJ; `draft_for_shipment`, `draft_for_credit_note`, `issue_draft`, `discard_draft`, `rebuild_drafts`, `output_reconciliation`, `output_reconciliation_periods`; cetak draf/retur |
| `backend/services/input_tax_service.py` | rekap: draf tidak dihitung, retur pengurang |
| `backend/routers/tax_invoices.py`, `backend/schemas.py` | saringan `doc_kind`; `issue`, `discard`, `drafts/rebuild`, `output-reconciliation` |
| `scripts/verify_data_integrity.py` | FKT-3 per `active_key`; INV-TAX-OUT-01 (WARN) |
| `scripts/blueprint/pk40_kunci_faktur.py` | proyeksi field kunci baru |
| `backend/tests_mem/test_TXT2_pemicu_faktur.py` (baru), `test_KFT1_izin_pengaturan.py` (`TXT2_KUNCI = 1`) | uji |
| `frontend/.../configKeyIndex.json`, `CODEBASE_MAP.md` | dibangkitkan |

## Serah-terima (b) — pengalihan

| Berkas | Isi |
|---|---|
| `backend/services/tax_invoice_service.py` | rekap `$in normal/pengganti`; `replace` → `diganti` + pulih; `job_tax_draft_backfill` |
| `backend/services/shipment_service.py` | kait `draft_for_shipment` sesudah jurnal |
| `backend/services/credit_note_service.py` | kait `draft_for_credit_note` sesudah `posted` |
| `backend/services/amendment_service.py` | `is_issued` hanya faktur terbit |
| `backend/services/work_desk_service.py` | antrean faktur per pesanan hanya PT berpemicu pesanan |
| `backend/services/scheduler_service.py` | job `tax_draft_backfill` |
| `backend/services/tax_config_service.py` | `bagian_pajak_layar.pemicu_faktur` |
| `backend/services/input_tax_service.py` | docstring rekap |
| `scripts/verify_data_integrity.py` | `INV_TAX_OUT_WAJIB = True` |
| `scripts/migrate_tax_invoice_status.py` (baru), `scripts/INDEX.md` | H3 |
| `frontend/src/features/finance/TaxInvoices.jsx`, `TaxOutputRecon.jsx` (baru), `features/orders/OrderDetailPanel.jsx` | layar |
| `frontend/src/features/__tests__/txt2FakturDraf.test.js` (baru) | uji komponen |
| `backend/tests/test_bp_TXT2_draf_bersamaan_mongo.py` (baru) | U17 lapis A (ditulis) |
| `backend/tests_mem/test_PK09_entitas.py` | fixture status `issued` → `normal` |
| `ENTITY_REGISTRY.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.19 (pelaksana menulis §9.18; dinomori ulang saat digabung sesudah PY-T2), `CODEBASE_MAP.md` | dokumen |

## Uji penerimaan

Berkas `backend/tests_mem/test_TXT2_pemicu_faktur.py` (29 uji). "Merah lama" (a) = kode `cd5aa59`
(`bukti/TX-T2/a_merah_kode_lama.txt`); (b) = kode (a) (`bukti/TX-T2/b_merah_di_kode_a.txt`).

| ID | Lapis | Merah lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | **hijau** (sengaja: perilaku hari ini) | Lulus — PT PKP ketiga, pemicu bawaan: tanpa draf; terbit per pesanan `normal` PPN 1.100.000, `so:` |
| U2 | B | ya — kunci tidak ada (404) / `draft_for_shipment` tidak ada | Lulus — angka di atas; `sj:{S1}:SJ-1`; rekap 0 |
| U3 | B | ya — fungsi tidak ada (lanjutan) | Lulus — tetap 1 draf; terbit `normal`; rekap 440.000; terbit ulang 409 "Dokumen ini bukan draf." |
| U4 | B | ya (lanjutan) | Lulus — 660.000; Σ 1.100.000; selisih 0 |
| U5 | B | ya (lanjutan) | Lulus — 440.000 / 1.100.000 / 660.000 di SJ-2 / belum 0; INV-TAX-OUT-01 PASS; FKT-3/FKT-5 PASS |
| U6 | B | ya (lanjutan) | Lulus — belum 50.000 + nomor jurnal; INV-TAX-OUT-01 menyebut PT & "November 2026" & "Rp 50.000" — (a) WARN, (b) FAIL |
| U7 | B | ya (kode (a)): tanpa `status_before_replaced` | Lulus — asal `diganti`/`normal`, pengganti 440.000 angka SJ; rekap tetap; batal → asal `normal` + kunci pulih |
| U8 | B | ya (lanjutan) | Lulus — 409 "Lengkapi data pajak pelanggan dulu: identitas pajak."; PATCH NPWP; 200 |
| U9 | B | ya (lanjutan) | Lulus — retur 110.000 rujuk faktur SJ-1; rekap 330.000; buku besar 990.000; belum 0 |
| U10 | B | ya — kunci tidak ada | Lulus — 409 "PT ini menerbitkan faktur per surat jalan. Terbitkan dari antrean draf." |
| U11 | B | ya — 404 kunci tidak ada | Lulus — 400 "…belum bisa dipakai…uang muka…"; nilai tetap `surat_jalan` |
| U12 | B | ya — kunci tidak ada | Lulus — PT ketiga (bawaan) & `ent_kanda` non-PKP (pemicu sengaja `surat_jalan`): tanpa draf |
| U13 | B | ya (lanjutan) | Lulus — kunci masa lalu lewat API: 409 "Masa pajak … sudah ditandai dilaporkan…", tetap draf |
| U14 | B | ya (lanjutan) | Lulus — Manajer Kosong 403, Sopir 403, PT lain 403/404 (tetap draf), Tanpa Acuan + `tax_invoice.create` 200 |
| U15 | B | ya (kode (a)): skrip tidak ada | Lulus — `--dry-run` tidak menulis; asal `diganti` + `status_before_replaced: normal`, tanpa kunci; antar-PT tidak disentuh; rekap sama; putaran 2 "0"; `--undo` kembali |
| U16 | B | ya — kunci tidak ada | Lulus — metadata; lapisan PT hanya PT itu; cabut; tak sah 400; tanpa alasan 400. + putaran KF-T8 `tax.pemicu_faktur` lulus |
| U17 | A | — | **ditulis** `backend/tests/test_bp_TXT2_draf_bersamaan_mongo.py` (belum dijalankan) |
| U18 | layar | — | **belum diuji jalan** (integrator); jest `txt2FakturDraf` 7/7 |
| (a) tambahan | B | ya | buang draf (alasan wajib, tidak dibuat ulang, tampil di pencocokan); bangun ulang idempoten (+400 masa tak sah); saringan `status`/`doc_kind`; "Semua PT" 400; draf/retur tidak lewat batal/ganti/NSFP |
| (b) tambahan | B | ya (kode (a)) | rekap himpunan baru; kait `dispatch_task` (+gagal tidak membatalkan SJ); job pemulih (+tidak membuat ulang yang dibuang); kait `settle` → draf retur 55.000; kunci amandemen; meja Finance; `/settings/effective.pemicu_faktur`; INV wajib |

## Menyimpang dari blueprint

1. Rekap di (a) sudah mengecualikan draf dan mengurangkan retur — U2 dan U9 (lapis (a)) menuntutnya; dokumen lama tidak
   punya draf/retur sehingga angkanya tidak berubah. (b) memasang himpunan status baru.
2. Pengganti faktur per surat jalan menyalin angka SJ sejak (a) (jalur baru); status `diganti` di (b).
3. Draf tidak bisa dibatalkan (`/cancel`), diganti, atau diberi NSFP (409 berpesan); dokumen retur tidak bisa diganti
   (bentuk resmi menunggu konsultan pajak) — tidak disebut spesifikasi, menutup jalan pintas yang merusak `discard_reason`.
4. Urutan uji U9 sebelum U4 supaya angka spesifikasi (330.000) tetap; U7 memakai pesanan sendiri dan menilai "rekap
   tetap R, bukan R + 440.000" karena masa uji memuat faktur lain (hitungan di docstring uji).
5. U17 lapis A memanggil layanan di proses (motor → MongoDB asli) dengan PT uji sendiri, bukan HTTP: tidak ada endpoint
   satu-SJ, dan "bangun ulang" lewat HTTP akan menyentuh surat jalan data acuan PT lain.
6. Kait `dispatch_task` diuji dengan `ship_order_rolls` ditiru (gerbang roll/RFID = H7).
7. Draf memakai nomor FKT saat lahir (draf yang dibuang meninggalkan lompatan nomor internal; NSFP resmi tidak terpengaruh).
8. Uji lama disesuaikan: `test_PK09_entitas.py::test_U11` memakai status `issued` (tidak pernah ditulis layanan faktur)
   → `normal`; maksud uji (cakupan PT) tetap.
9. Di luar daftar "Perubahan" tetapi perlu agar pemanggil tidak menabrak 409: antrean meja Finance, `pemicu_faktur` di
   `/settings/effective`, proyeksi `pk40_kunci_faktur.py`, FKT-3 per `active_key`.

## Asumsi

- Spesifikasi: angka dari jurnal; dokumen retur di `tax_invoices` sebagai draf; pesanan berfaktur per pesanan tidak diberi
  draf SJ; draf dibuang tidak dibuat ulang (juga oleh "bangun ulang" dan job).
- Satu "surat jalan" = semua catatan `shipments` bernomor sama untuk pesanan itu (kirim per gudang berbagi nomor).
- Tanggal faktur bawaan saat terbit = tanggal buku jurnal sumbernya (surat jalan / nota); boleh diubah di pop-up.
- Dokumen retur hanya untuk pesanan yang punya faktur terbit; status yang dihitung rekap hanya `normal`.
- `issue_for_order` (terbit per pesanan) tetap tanpa `guard_doc` pesanan (perilaku lama; di luar lingkup).

## Menunggu pemilik (usulan baris `STATUS.md` — integrator)

- **H5 / konsultan pajak**: (1) nama, bentuk, penomoran dokumen pajak retur, dan kapan wajib (setiap nota kredit ber-PPN?
  hanya pembeli PKP?); (2) tanggal faktur per surat jalan = tanggal penyerahan atau tanggal terbit; (3) jurnal PPN atas
  uang muka (akun & arah) sebelum pilihan "Per uang muka" dibuka; (4) koreksi harga (nota amandemen) cukup dokumen retur
  atau wajib faktur pengganti; (5) kode transaksi dokumen retur. Pilihan: tetap `pesanan` (bawaan) · aktifkan
  `surat_jalan` per PT sesudah jawaban. Usulan: tetap bawaan sampai butir 1–2 dijawab.
- **H3**: menjalankan `scripts/migrate_tax_invoice_status.py` (mulai `--dry-run`) pada data nyata.

## Cek layar

Acuan `docs/KN_37_STANDAR_UI_GUDANG.md` + KN_08/UX. Token `kn-*`, kelas tombol baku; `verify_ui_standard` tetap 13
(per berkas tidak naik; `OrderDetailPanel` tetap 57). Belum dipotret (integrator 1280/1024/390 px).

| Layar | (1) tabel ≤ kartu, aksi lekat | (2) bantalan | (3) kepala | (4) tombol mati | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/angka 0 |
|---|---|---|---|---|---|---|---|---|
| **Faktur Keluaran** (`TaxInvoices.jsx`) | Tetap **8 kolom** (kolom "Pesanan" → "Sumber"; SJ/nota di bawahnya, tidak dipatah), `data-table head-wrap`, Aksi `col-sticky-end` lebar minimum sama; draf: Terbitkan/Buang di kisi 2×2 yang sama | `section-head`/`section-body` | Kepala tetap judul + Muat ulang; chip saringan + sakelar jenis di bilah sendiri | Tidak ada tombol mati baru; aksi yang tidak berlaku tidak dirender (draf: tanpa NSFP/batal/ganti) | `status-pill` Draf (FilePen) / Diganti (History) + lama; lencana data pajak = tombol tautan berisi pil ikon+teks | Kotak cari + nomor SJ/nota ikut dicari; chip Draf memuat jumlah | Tombol dari `can(tax_invoice.create/cancel/…)`; teks atas menjelaskan dua pemicu | "Tidak ada draf faktur." khusus saringan draf; satu keadaan kosong |
| **Pop-up Terbitkan / Buang draf** | — | `FormModal` baku | Judul + nomor | Tombol utama selalu aktif; galat di dalam pop-up (`fkt-modal-error`) | — | — | — | Konfirmasi `moneyMessage`: efek + **Rp PPN** + **nama PT** (N5); alasan buang wajib |
| **Pencocokan PPN keluaran** (`TaxOutputRecon.jsx`, kartu di bawah daftar) | Tabel 4 kolom `head-wrap` di dalam kartu (`overflow-x-auto`) | `section-head`/`section-body` | Judul + Muat ulang; "Bangun ulang draf" di bilah isian (bukan kepala), keterangan di sampingnya | Muat ulang mati di "Semua PT" dengan kalimat petunjuk tertulis; Bangun ulang disembunyikan tanpa izin/"Semua PT" | "Belum terjelaskan" ikon + teks + `bg-kn-warning-soft` bila ≠ 0, netral bila 0; "cocok" ikon + teks hijau | Masa (bulan) + kotak "Cari sumber" ("n dari m") | Tanpa izin `tax_invoice.view` layar tidak terbuka; teks "Semua PT" = hanya baca | `MetricRow` (nol netral); daftar sebab hanya yang berisi; satu kalimat bila cocok |
| **Detail pesanan › Faktur Pajak** (`OrderDetailPanel.jsx`) | Daftar ringkas (bukan tabel) | Kotak lama | Tombol terbit diganti tautan "Lihat draf faktur (n)" (pemicu `surat_jalan`) | — | Label status (tidak lagi kode mentah) + warna token untuk Draf/Diganti; "dokumen retur" & nomor SJ teks netral | — | Tombol terbit tetap `can(tax_invoice.create)` | Kalimat kosong lama |
| **Pengaturan › Keuangan & Pajak › Pajak** | Kartu baku (13 kunci di sub-judul, ≤ 14) | baku | baku | baku | baku | baku | izin `accounting.manage` | `verify_config_text` 0 pelanggaran |

## Penggabungan ke HEAD cabang

Worktree tujuan disetel ke HEAD cabang **`5f193df`** ("STATUS: KM-T2, PY-T2, CR-T2, PM-T4 dikerjakan"). Sejak basis
`cd5aa59` HEAD hanya mengubah STATUS/TRACKER, laporan, `ListPageParts.jsx`, `BankReconciliationView.jsx`,
`FinanceTowerParts.jsx`, dan satu uji lapis A — **tidak ada berkas unit ini yang berubah di HEAD**, jadi 29 berkas (24 ubah +
5 baru; tanpa `backend/.env` dan `hasil/`) disalin apa adanya, **tanpa bentrok**. `CODEBASE_MAP.md` dan
`configKeyIndex.json` dibangkitkan ulang di T; hitungan KF-T1 (`TXT2_KUNCI = 1`) tidak bertemu tambahan unit lain.

| Pemeriksaan di T (`5f193df` + unit) | Hasil |
|---|---|
| tests_mem penuh | **1954 lulus / 2 dilewati / 2 xfail** (`bukti/TX-T2/b_tests_mem_T.txt`; basis HEAD = basis W 1924/2/2 — tidak ada uji `tests_mem` berubah di HEAD). Sesudahnya perbaikan nomor draf (nomor FKT diambil saat sisip): TX-T2 + PK-40 + PK-45 + PK-32 + PK-09 + TX-T1 122/122 |
| jest penuh | **964 lulus** (957 + 7 `txt2FakturDraf`); 35 suite gagal dimuat `cmdk`/`@radix-ui` = basis |
| `hitung_penjaga.sh` | auth 27 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 5 · entity_label 2 (= basis); lainnya 0/PASS |
| `verify_role_gate_ui` | 31/0 |
| `verify_config_fallback` / `--entity` | 157/0 · 157/0 |
| `verify_payment_vocab` | 1815/0 |
| `verify_access_catalog_nav` | 0 temuan |
| `verify_atomic_claim` / `--self-test` | 160/0 · 64 kasus hijau (endpoint baru menulis satu koleksi + `doc_refs` catatan → tidak masuk `REVIEWED`; inventaris multi-koleksi tidak berubah) |
| `verify_posting_coverage` / `verify_cash_single_door` / `verify_permission_checked` / `verify_config_text` / `verify_detail_modal` | 133/0 · 728/0 · 606/0 · 3283/0 · 30/0 |
| `audit_config_wiring --strict` (salinan berjalur T) | hijau |
| `check_nav_map` (salinan berjalur T) | PASS |

Salinan (a) tergabung: `scratchpad/TX-T2_a_merged/` (`BASIS.txt` = `5f193df`).

## Hambatan lingkungan

- 35 suite jest gagal dimuat (`cmdk`/`@radix-ui`), sama dengan basis. Lapis A dan uji jalan tidak dijalankan (larangan
  database `backend/.env` / backend :8001).

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`38c715f`** — satu gate
untuk rantai gelombang 4 (PY-T2, TX-T2 (a/b) + cek layar, AG-T5 (a/b) + cek layar, CR-T2 (a/b), PM-T4):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`b62ef45`: 12 / 39) — tidak ada gate baru yang merah. "Tidak dijalankan" tambahan = ganti label
(`guard:atomic_claim SELF-TEST` 10 → 64 kasus, `guard:page_tabs` + uji-dirinya). Kuitansi: `bukti/TX-T2/gate_quick_receipt.md`,
`gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- Rantai gelombang 4 dipasang integrator berurutan di atas `8ac7059`: PY-T2 `5edef21` · `82ef1bb` → TX-T2 (a) `38b5c9b` · (b) `84744dc` · cek layar `15d3258` → AG-T5 (a) `31a8d54` · (b) `7747302` · cek layar `df23cb2` → CR-T2 (a) `2d9709e` · (b) `76a337d` → PM-T4 `38c715f`. Tiap commit diuji `tests_mem` penuh di worktree bantu sebelum dipetik (angka di bawah). Jest penuh di `38c715f`: **995 lulus** (957 + PY-T2 8 + TX-T2 7 + AG-T5 11 + CR-T2 5 + PM-T4 7; 35 suite gagal dimuat `cmdk`/`@radix-ui`, sama). Penjaga statik di `38c715f` = garis dasar kecuali `verify_auth_coverage` 27 → **26** (AG-T5); `verify_atomic_claim` 161/0, `verify_posting_coverage` 138/0, `verify_cash_single_door` 736/0, `verify_role_gate_ui` 31/0, `verify_detail_modal` 30/0. Glosarium KN_32: §9.18 PY-T2 · §9.19 TX-T2 · §9.20 AG-T5 · §9.21 CR-T2 · §9.22 PM-T4 (nomor pelaksana dirapikan integrator). Indeks wajib lapis A: 29 + PY-T2 2 + CR-T2 2 + PM-T4 1 = **34** (`check_required_indexes` 34/34 di data acuan).
- Dipasang di atas PY-T2 (`82ef1bb`): (a) **`38b5c9b`** — bentrok `test_KFT1_izin_pengaturan.py` (konstanta PY-T2
  dan TX-T2 dipertahankan, hitungan dijumlahkan); (b) **`84744dc`** — bentrok `scheduler_service.py` (job PY-T2
  `hr_compensation_effective` dan TX-T2 `tax_draft_backfill` dipertahankan keduanya) dan KN_32 (TX-T2 → §9.19).
  `tests_mem`: (a) **1962/2/2**, (b) **1972/2/2**, 0 gagal.
- Lingkungan A: lapis A **U17** mula-mula gagal "Event loop is closed" (tiga `asyncio.run` terpisah, klien Motor terikat
  ke loop pertama) → satu loop untuk semua putaran (`15d3258`) → **lulus** (dua `draft_for_shipment` bersamaan → satu
  draf). `verify_data_integrity --only tax`: PASS 6 / FAIL 0 (INV-TAX-OUT-01 hijau). `migrate_tax_invoice_status.py
  --dry-run` di data acuan: 0 faktur perlu diubah. **Data nyata = H3; pemicu tetap `pesanan` di semua PT (H5).**
- Uji jalan **U18** (data contoh di database uji lokal: `ent_ksc` pemicu `surat_jalan`, 4 surat jalan berjurnal → bangun
  ulang = 4 draf, satu diterbitkan): **cacat ditemukan dan diperbaiki (`15d3258`)** — tabel Faktur Keluaran 8 kolom
  = 1069 px: di 1024 px (kartu 732 px) kolom DPP/PPN/total tertutup gulir, di 1280 px kolom total tertutup kolom aksi
  lekat. Kini **5 kolom** (No. faktur · status · NSFP | Sumber | Pembeli | DPP · PPN · Total berlabel | Aksi kisi 3
  kolom, `DocumentActionsBar` ber-`contents`) = 988 / 732 px = lebar kartu; "Surat jalan" boleh turun baris. Pop-up
  Terbitkan draf memakai `KNDatePicker` (dulu isian tanggal peramban: "11/15/2026" format AS) dan panel Pencocokan
  memakai `KNMonthPicker`. Jest TX-T2 diperbarui (judul 5 kolom, NSFP/PPN/Total berlabel) 7/7; `phase4R2` tetap
  gagal dimuat (`DecisionModal` → `cmdk`, garis dasar). Panel Pencocokan PPN keluaran (1024/390), bagian Faktur Pajak di
  detail pesanan ("Lihat draf faktur (n)", label status) rapi (`bukti/TX-T2/cek_*.png`).
- Temuan di luar lingkup (tidak diubah): daftar Pesanan dengan panel detail di 1024 px sempit (kolom "Total (termasuk
  PPN)" terpotong) — perilaku lama layar Pesanan.

Pelaksana (catatan asli):

Belum dijalankan (integrator).

## Yang perlu direview

- Model satuan pencocokan (terutama mode pesanan lintas masa dan antar-PT) dan pilihan tanggal bawaan faktur draf.
- Penyegaran draf saat surat jalan satu nomor bertambah baris (`dispatch_order_batch`).
