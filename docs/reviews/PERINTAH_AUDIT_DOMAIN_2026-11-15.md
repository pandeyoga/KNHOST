# Perintah audit domain (R5) — master data, makloon, R&D, retur, QC & MD Quality, pesanan sesudah POS

Ditulis 15 Nov 2026 atas permintaan pemilik. Dikerjakan oleh **reviewer** (sejajar dengan review blueprint di
`PERINTAH_REVIEW_2026-11-15.md`). Audit ini **hanya membaca**: tidak mengubah kode, data, server, atau `main`. Hasilnya
menjadi bahan unit perbaikan sesudah pemilik memilih. Bahasa kerja: Bahasa Indonesia.

## 0. Prompt untuk ditempel di sesi audit

```text
Anda auditor untuk repo KNHOST (Kain Nusantara ERP). Baca docs/reviews/PERINTAH_AUDIT_DOMAIN_2026-11-15.md seluruhnya.
Audit ini hanya membaca: jangan mengubah kode, data nyata, server, atau main. Kerjakan domain berurutan (A dulu) sampai
definisi selesai di §8 terpenuhi: setiap skenario wajib dijalankan sebagai pengguna dengan bukti, setiap form wajib
diinventaris per dropdown, setiap temuan lengkap dan terdaftar di tracker. Periksa sendiri dengan
`python3 scripts/review/periksa_selesai.py audit docs/audit/<tanggal>-domain` — jangan menyatakan selesai sebelum
"HASIL: SELESAI". Akhiri tiap sesi dengan `periksa_selesai.py progres`, satu baris di docs/reviews/LOG_REVIEW.md, commit,
dan push ke cabang review/<tanggal hari ini> (bukan main).
```

## 1. Keluhan pemilik (dasar audit — dikutip dan dirapikan)

1. **Master data, terutama jenis barang**: benang, greige/grey, PFP, PFD, bahan jadi — juga di makloon. Masih sangat
   menjadi perhatian, terutama UI/UX. Di form yang muncul, **aturan stage barang belum ditegakkan** dan **pilihan dropdown
   masih asal**.
2. **Makloon dari awal sampai akhir masih sangat kacau.**
3. **R&D sama** (kacau dari awal sampai akhir).
4. **Retur** — pemilik masih ragu.
5. **Alur pesanan pelanggan sesudah POS**: masalah **alokasi** yang berujung **perubahan tagihan**, **keep/pending lalu
   dibuka lagi**, dan seterusnya. (Tafsiran: alur pesanan penjualan dari checkout POS; bila pemilik juga memaksudkan PO
   ke supplier yang lahir dari pesanan, ikutkan sambungan pesanan → PR/PO.)
6. **Retur, QC, dan MD Quality** masih banyak masalah UI/UX, terutama pengalaman pemakaian — menurut pemilik **lebih
   disebabkan duplikasi atau cacat logika** daripada tampilan semata.

Prinsip audit: keluhan UI/UX diperlakukan sebagai **gejala**. Untuk tiap gejala, telusuri sampai ke sumbernya: dua
implementasi untuk hal yang sama, aturan yang hanya ada di layar (atau tidak ada sama sekali), pilihan yang diambil dari
sumber yang salah, transisi status yang ditawarkan layar tetapi ditolak server (atau sebaliknya).

## 2. Batas dan titik henti

- Hanya membaca. Boleh menjalankan aplikasi lokal dengan data acuan, kueri **hanya-baca** ke database lokal, dan
  Playwright untuk potret layar. Tidak boleh memperbaiki kode, mengubah data nyata, menyentuh VPS, atau push ke `main`.
- Titik henti (`docs/blueprint/00_ATURAN_EKSEKUSI.md` §6): H2 server · H3 data nyata · H4 isi tabel peraturan ·
  H5 sakelar per PT · **H7 logika gerbang RFID** (bila audit menyentuh RFID/handheld, baca `docs/rfid/KEPUTUSAN_GATE_RFID.md`
  dulu dan hanya laporkan) · H8 rahasia.
- Jangan menjalankan dua gate/POC bersamaan. Jangan commit `backend/.env`, `frontend/.env`, `memory/GATE_RECEIPT.*`.

## 3. Bahan yang sudah ada (baca sebelum menulis temuan supaya tidak menggandakan)

| Bahan | Isi | Kegunaan |
|---|---|---|
| `docs/reviews/TRACKER.md` | semua temuan ber-ID | **cek dulu**: temuan yang sama → rujuk ID lama, jangan ID baru |
| `docs/audit/2026-11-09-wms-rfid/` (B1–B4, `hasil/FIX-1…10`) | audit gudang & RFID: alur masuk, opname, transisi status, alur keluar, potong, sampel non-SO, SO ambil-kirim, skema stok, form & daftar, standar UI | jangan mengulang; fokus pada yang belum dicakup |
| `docs/finance/AUDIT_KEUANGAN_2026-11-13.md` | jurnal, piutang/hutang, retur ↔ jurnal, persediaan | efek uang dari temuan Anda dirujuk ke sini |
| `docs/audit/konfigurasi-peran-2026-11-13/` | pengaturan, peran, izin | izin/pengaturan |
| `docs/blueprint/STATUS.md`, `INDEKS_UNIT.md`, `unit/*.md` | unit yang sudah selesai (mis. PK-27/PK-28/PK-32 retur, PK-18 jurnal makloon, FIX-6 retur & tolak QC, FIX-9 kunci makloon, PK-30 roll antar-PT) | perilaku yang sudah diperbaiki — nilai ulang hanya bila ada bukti cacat |
| `docs/blueprint/EVALUASI_EKSEKUSI_2026-11-15.md` §6–§9 | peta cakupan, celah kredit Pesanan Khusus, temuan di luar unit | titik awal |
| `docs/KN_15_INVENTORY_OWNERSHIP_LOT.md`, `KN_16_END_TO_END_PROCESS_FLOWS.md`, `KN_18_TEXTILE_FOUNDATION_PROBLEM_STATEMENT.md`, `KN_19_PLAN_FASE_A_FONDASI_DOMAIN.md`, `KN_22_PLAN_FASE_B_UOM.md`, `KN_23_PLAN_FASE_C_LOT.md`, `KN_24_PLAN_FASE_D_MAKLOON.md`, `KN_31_PLAN_FASE_F_RND_DESIGN.md` | rancangan domain asli (stage, UoM, lot, makloon, R&D) | **bandingkan rancangan vs kode** |
| `ANALISIS_DOMAIN_SALES.md`, `ANALISIS_FLOW_DIVISI.md`, `ANALISIS_FLOW_RETUR_BERANTAI.md`, `RENCANA_EKSEKUSI_MD_ERP.md` | analisis lama (sebelum Nov; bisa basi) | latar; cek ulang di `HEAD` |
| `docs/KN_08_UI_UX_STANDARDS.md`, `docs/UX_USABILITY_STANDARD.md`, `docs/KN_37_STANDAR_UI_GUDANG.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`, `docs/blueprint/02_STANDAR.md` | standar layar, istilah, izin bukan nama peran, pengaturan bukan konstanta | ukuran untuk temuan UI/UX |

## 4. Domain, pertanyaan, dan titik awal kode

### A. Master data & jenis barang (stage) — prioritas tertinggi

Sumber kebenaran yang dirancang: `backend/domain_registry.py` — `STAGES` (keadaan kain: `yarn` benang · `grey` greige ·
`pfd` · `pfp` · `finished` bahan jadi · `remnant` · `byproduct`), `STAGE_TRANSITIONS`, `PROCESS_TYPES`, tujuan pakai
(`dye` → PFD, `print` → PFP); master `process_stages` (FASE T, bisa ditambah pemilik) dijaga
`scripts/guardrails/verify_master_stages.py` (INV-DOMAIN-06). Satuan per jenis: `uom_rules_service.py`, `uom_service.py`,
`variant_axes.py`.

Pertanyaan:
1. Untuk **setiap form** yang membuat/mengubah barang atau memakai barang, apakah stage ditegakkan **di server** (bukan
   hanya di layar)? Mulai dari: `features/admin/products/ProductMasterForm.jsx`, `features/catalog/VariantEditor.jsx`,
   `SpecVariantFields.jsx`, `LinkExistingVariant.jsx`, `features/settings/masters/EntityMastersView.jsx`,
   `features/rnd/SpecFormModal.jsx`, `SampleFormModal.jsx`, `ExistingSkuSection.jsx`, `features/purchasing/PoStageModal.jsx`,
   `PoBoardView.jsx`, `RecipeFormModal.jsx`, `features/purchasing/makloon/*` (`MakloonWizard.jsx`, `MakloonStepEditor.jsx`,
   `MkoStepModals.jsx`), `MakloonOrderCreateModal.jsx`, `features/samples/CuttingDesk.jsx`, POS/checkout, form PO, form
   retur. Backend: `master_registry.py`, `product_template_service.py`, `product_variant_service.py`, `entity_master_service.py`,
   `fabric_type_master_service.py`, `rnd_spec_service.py`, `process_recipe_service.py`, `makloon_order_service.py`.
2. **Dropdown "asal"**: untuk tiap dropdown di form-form itu, dari mana pilihannya diambil, dan apakah disaring menurut
   stage, jenis proses, PT, gudang, mitra, dan status aktif? Contoh yang harus dijawab: bisakah benang/greige dijual di
   POS; bisakah langkah makloon "printing" memakai bahan yang belum PFP; apakah pilihan proses mengikuti `from_stage`
   barang masuk; apakah pilihan satuan mengikuti jenis (benang kg vs kain meter/yard); apakah pilihan mitra mengikuti
   `process_types` mitra; apakah grade mengikuti stage.
3. **Satu sumber atau banyak**: daftar stage/label/proses ditulis di berapa tempat (backend + frontend)? Contoh yang sudah
   terlihat: label PFP/PFD ditulis dua cara di `domain_registry.py` (baris ±55–57 "Prepared for Printing/Dyeing" vs ±448–459
   "Pre-treatment untuk printing/celup"). Cari salinan daftar di `.jsx` yang tidak membaca dari server.
4. **Transisi stage**: apakah setiap jalur yang mengubah stage (makloon per langkah, potong, perbaikan, R&D, penerimaan)
   memakai `STAGE_TRANSITIONS`, atau ada jalur yang menulis `stage` langsung?
5. **Data acuan**: berapa produk/roll yang stage-nya tidak cocok dengan satuan, kategori, atau riwayat prosesnya (kueri
   hanya-baca)?

### B. Makloon dari awal sampai akhir

Alur yang harus ditelusuri sebagai pemakai sungguhan (peran pembelian/MD/gudang/finance): kebutuhan (SO / Pesanan Khusus /
stok) → PR → **pembuatan SPK makloon** (ada `MakloonWizard.jsx` dan `MakloonOrderCreateModal.jsx` — dua pintu?) →
rencana langkah (`process_recipe_service`, master `process_stages`) → kirim bahan (`makloon_issue_rolls.py`, kunci cadangan
FIX-9 `makloon_roll_lock.py`) → di mitra (`subcon`) → terima per langkah (`makloon_order_service.receive_step`,
`makloon_receipt_qc.py`, `inbound_qc_common.py`) → QC hasil → susut/hilang (`makloon_loss_service.py`) → klaim
(`makloon_claim_service.py`) → buku bahan (`makloon_material_ledger.py`) → tagihan jasa (`record_service_step`,
`makloon_calc_service.py`) → jurnal per langkah (PK-18) → stok hasil → rekap (`makloon_recap_service.py`) dan skor mitra
(`makloon_service.py`).

Skenario wajib: grey → PFD → celup → bahan jadi; grey → PFP → printing (+ screen); benang → tenun/rajut → grey; terima
sebagian; kirim balik ke mitra; perbaikan (`repair_order_service.py`); batal di tengah; mitra berbeda per langkah; antar-PT.
Pertanyaan: di mana alur buntu atau membingungkan; data apa yang diisi dua kali; status mana yang bisa macet; apakah nilai
(biaya bahan + jasa + susut) sampai ke HPP hasil dengan benar; apakah layar detail (`MakloonOrderDetailPanel.jsx`)
menceritakan keadaan sebenarnya.

### C. R&D (dan desain)

Modul: `rnd_flow_service.py`, `rnd_gate.py`, `rnd_sample_service.py`, `rnd_spec_service.py`, `rnd_required_tests.py`,
`rnd_revalidation_service.py`, `rnd_sla_service.py`, `rnd_catalog_validation.py`, `rnd_org_service.py`,
`rnd_kpi_service.py`, `design_request_service.py`, `design_studio_service.py`, `design_gallery_service.py`,
`design_ownership_service.py`, router `rnd.py`, `design_*.py`, `sample_orders.py`; Pesanan Khusus → R&D
(`special_order_routing.py`, `special_order_service.py` create-sku); layar `features/rnd/*`, `features/designer/*`.
Pertanyaan: alur permintaan → sample → keputusan pelanggan → spesifikasi → SKU/varian → produksi/makloon; stage sample
dan SKU yang lahir; pintu ganda pembuatan SKU (R&D vs Pesanan Khusus vs master); gerbang (`rnd_gate`) yang ditawarkan
layar tetapi ditolak server; KPI desainer dari data yang benar.

### D. Retur (jual & beli) — pemilik ragu

Ada ±30 modul `return_*`/`purchase_return_*`. Pasangan yang memang dirancang berdampingan (jangan langsung dituduh duplikat,
tetapi periksa apakah pembagiannya benar): `return_state.py` (tabel transisi retur jual) + `sales_return_transition.py`
(penulis FIX-6); `purchase_return_state.py` (status RMA supplier) + `purchase_return_doc_state.py` (status dokumen FIX-6).
Alur: retur dari pelanggan (POS/SO, per roll vs per item, `CreateReturnForm.jsx`) → jemput/scan masuk karantina
(`return_journey_service`, `return_intake_service`, D5) → inspeksi → disposisi (`return_disposition_service`: masuk stok /
scrap / klaim ke supplier / perbaikan) → penyelesaian (refund / kredit / nego; `return_roll_settlement_service`,
`return_settlement_policy`, `return_compensation_service`, `return_replacement_service`, `return_cutloss_split_service`) →
retur berantai ke supplier (`return_chain_service`, `purchase_return_service.create_from_sales_return`) → antar-PT
(`interco_return_service`). Pertanyaan: jalur mana yang menghasilkan uang/stok ganda atau hilang; status yang bisa macet;
pilihan disposisi yang ditawarkan tetapi tidak sah; apa yang harus diisi pengguna dua kali; layar mana yang menyesatkan.
Sesudah R0 (15 Nov) jurnal retur beli sudah satu pintu — lihat `docs/blueprint/INTEGRASI_MAIN_FIX6-10.md`.

### E. QC & MD Quality

Modul: `qc_service.py` (karantina saat penerimaan, tolak/terima), `qc_inspection_service.py` (4-point per roll, grade),
`inspection_service.py` + `inspection_state.py` (SPK inspeksi / PA, gedung inspeksi), `makloon_receipt_qc.py`,
`inbound_qc_common.py`, pemeriksaan retur, grade (`grade_service.py`, `grade_master_service.py`, `return_grade_impairment.py`);
router `inspections.py`, `qc_inspection.py`; layar `features/inspections/*`, `features/wms/QCInspection.jsx`, akun
`mdquality@` dan `qc@`. Sudah terlihat: aturan "QC 4-point dikerjakan di SPK QC 4-point tersendiri" (pesan galat yang membuat
seed gagal) — berapa pintu keputusan QC yang ada untuk satu roll, siapa yang boleh memutuskan apa (izin, bukan nama peran),
dan apakah hasil QC (grade, tolak, retur) sampai ke stok, harga, dan retur beli dengan satu cara.

### F. Pesanan pelanggan sesudah POS — alokasi, perubahan tagihan, keep/pending, buka lagi

Alur: checkout POS (`features/pos/CheckoutDrawer.jsx`, `CheckoutStep3.jsx`) → SO → reservasi/alokasi roll
(`sales_order_helpers.reserve_roll_mode_item`, `material_reservation_service.py`) → keputusan pemenuhan — **empat modul
yang tumpang tindih**: `fulfillment_service.py` (ATP), `fulfillment_decision_service.py` ("satu pintu untuk tiga jalan yang
tersebar di lima layar"), `fulfillment_plan_service.py` (rencana per baris, 2026-10), `fulfillment_wizard_service.py`
(skenario S1–S8) → realokasi (`ReallocateRollsModal.jsx`, `sales_orders_extra` reallocate / release-rolls) → backorder
(`backorder_service.py`) → **Keep/Pending** (`sales_p04_service.py`, keputusan pemilik DEC-01 11 Okt, `sales.keep_max_age_days`)
→ **buka lagi** (release-reservation, reopen) → batal baris (`so_line_cancel_service.py`) → perubahan tagihan (panjang roll
nyata vs pesanan; PK-30 roll dikirim utuh; koreksi/nota kredit PK-32; harga khusus `so_special_price_service.py`;
`ar_allocation_service.py`) → kirim & faktur.
Pertanyaan: apakah tagihan selalu mengikuti alokasi terakhir; apa yang terjadi pada DP/pembayaran bila alokasi berubah
sesudah bayar; apakah keep/pending → buka lagi meninggalkan reservasi atau backorder basi; berapa pintu yang bisa mengubah
alokasi dan apakah semuanya memakai aturan yang sama; layar mana yang menampilkan angka berbeda untuk pesanan yang sama.

## 5. Lensa yang dipakai di setiap domain

1. **Peta sumber kebenaran**: koleksi/field mana yang menjadi kebenaran, kode mana yang menulisnya (cari semua penulis).
2. **Pintu ganda**: dua service/endpoint/layar untuk pekerjaan yang sama; jalur lama yang tidak dimatikan.
3. **Aturan tidak ditegakkan**: aturan hanya di layar, hanya di satu dari beberapa pintu, atau tidak ada.
4. **Pilihan dropdown**: sumber pilihan, saringan (stage, proses, PT, gudang, mitra, aktif, izin), nilai yang mustahil.
5. **Status**: transisi yang ditawarkan layar vs diterima server; status macet tanpa jalan keluar.
6. **Efek uang dan stok**: jurnal, piutang/hutang, HPP, saldo stok — rujuk audit keuangan bila menyentuh jurnal.
7. **Pengalaman pemakai per peran**: jalankan skenario dengan akun peran (sales, salesadmin, manager, md, mdquality, qc,
   warehouse, wh.admin, finance, designer, sampleadmin; sandi `demo12345`), potret 1280 px dan 390 px, catat langkah buntu,
   pesan galat yang tidak menjelaskan, data yang diisi dua kali.
8. **Data acuan**: hitung catatan yang sudah tidak konsisten (kueri hanya-baca), sebagai bukti skala masalah.

## 6. Cara kerja dan lingkungan

```bash
docker compose -f docker-compose.dev.yml up -d
```

```bash
bash scripts/dev_restore_demo.sh
```

Hambatan yang sudah diketahui (bukan temuan baru): rantai seed `seed_demo_transaksi_kn.py` gagal di 5 skenario (QC
4-point wajib SPK terpisah, ambil wajib pindai, blok kredit) dan `seed_p03_kn.py` (gudang tujuan nonaktif) — tetapi
**kegagalan seed itu sendiri bisa menjadi bukti** bahwa alur yang sah terlalu sulit/berubah; catat kaitannya bila relevan.
Akun `manager.printing@` hanya ada di `seed_realistic.py`. Jest: 36 suite gagal dimuat (`cmdk`).

Penjaga yang relevan untuk dibaca keluarannya: `verify_master_stages.py`, `verify_sample_types.py`, `verify_uom_vocab.py`,
`verify_qty_dual.py`, `verify_state_machine.py`, `verify_status_history.py`, `verify_derived_fields.py`,
`verify_knselect_contract.py`, `verify_ui_standard.py`, `verify_role_gate_ui.py`. POC terkait yang merah: lini produk,
tahapan proses, sampling (`backend/test_core_*_poc.py`).

## 7. Keluaran

1. Folder `docs/audit/<tanggal>-domain/`:
   - `00-RINGKASAN.md` — temuan per domain, peta duplikasi (tabel "pekerjaan → pintu-pintu yang ada → yang seharusnya satu"),
     dan **pertanyaan untuk pemilik** (keputusan bisnis yang dibutuhkan, bernomor).
   - Satu berkas per domain (`A-MASTER-STAGE.md`, `B-MAKLOON.md`, `C-RND.md`, `D-RETUR.md`, `E-QC-MDQ.md`,
     `F-PESANAN-SESUDAH-POS.md`), plus `bukti/` (potret, kueri, keluaran skrip).
2. Format tiap temuan: ID, judul, keparahan (Kritis/Tinggi/Sedang/Rendah), domain, **jenis akar** (duplikasi · cacat logika ·
   aturan tidak ditegakkan · pilihan salah · status · UI saja), bukti berkas:baris di `HEAD`, langkah reproduksi di data
   acuan, potret, dampak bagi pengguna dan uang/stok, arah perbaikan (bukan kode), keputusan pemilik yang dibutuhkan, dan
   "sudah ada: <ID>" bila sama dengan temuan lama.
3. Prefiks ID baru (belum dipakai di tracker): `MS-` master & stage · `MK-` makloon · `RD-` R&D · `RT-` retur ·
   `QM-` QC & MD Quality · `SO-` pesanan sesudah POS.
4. Daftarkan setiap temuan di `docs/reviews/TRACKER.md` (bagian baru "Audit domain — <tanggal>") berstatus `open`, kolom
   Fase dikosongkan (diisi saat pemilik memilih dan blueprint membuat unit).
5. Ringkasan singkat untuk pemilik di akhir: 10 masalah terbesar (urut dampak), duplikasi yang harus disatukan lebih dulu,
   dan pertanyaan yang harus dijawab pemilik sebelum perbaikan.

Perbaikan **tidak** dikerjakan di sesi audit. Sesudah pemilik memilih, pelaksana membuat unit blueprint baru (dengan aturan
anti-duplikasi R6: tiap fitur menyebut pintu yang dipakai ulang dan jalur lama yang dimatikan).

## 8. Tujuan dan definisi selesai (wajib, diperiksa mesin)

### Tujuan terukur

1. **Setiap skenario wajib di bawah dijalankan sebagai pengguna sungguhan** (akun peran, data acuan, layar 1280 px dan
   390 px), dengan status `lulus` / `gagal` / `terhambat` dan bukti di `bukti/`.
2. **Setiap form wajib diinventaris per komponen pilihan**: satu baris per dropdown/radio/pencari — dari mana pilihannya,
   saringan apa yang ada, apakah server menegakkan aturan yang sama, dan apa masalahnya. Jumlah baris per form minimal
   sama dengan jumlah komponen pilihan di berkas itu (dihitung pemeriksa; komponen anak ikut diikuti dan dicatat).
3. **Setiap domain punya peta sumber kebenaran**: data mana yang menjadi kebenaran dan **semua** kode yang menulisnya
   (perintah pencarian ditulis), serta peta pintu ganda.
4. **Setiap temuan bisa dikerjakan tanpa bertanya lagi**: akar, bukti `berkas:baris`, langkah reproduksi, dampak, arah
   perbaikan, keputusan pemilik yang dibutuhkan, dan rujukan bila temuan sudah ada.

### Bentuk berkas domain (judul bagian persis, dipakai pemeriksa)

`## Peta sumber kebenaran` (blok perintah pencarian + ≥ 3 `berkas:baris` penulis) · `## Pintu ganda` · `## Matriks skenario`
(tabel `| <ID skenario> | peran | langkah yang dilakukan | lulus/gagal/terhambat | bukti/<berkas> | temuan |`) ·
`## Inventaris form & dropdown` (domain A, B, C, D, E, F yang punya form wajib; tabel
`| Form (nama berkas) | Field | Sumber pilihan | Saringan yang ada | Ditegakkan server? | Masalah |`) · `## Temuan`
(satu `### <ID> — <judul>` per temuan, berisi baris `Keparahan:`, `Jenis akar:`, `Bukti:`, `Reproduksi:`, `Dampak:`,
`Arah perbaikan:`, `Keputusan pemilik:`, `Sudah ada:`). Baris `Berkas dibaca: berkas.py:120-188, …` dicatat di tiap
bagian supaya jumlah baris kode yang dibaca bisa dihitung. `terhambat` wajib menyebut alasannya di kolom langkah.

### Skenario wajib

| ID | Skenario |
|---|---|
| A-S1 | Buat produk baru untuk tiap stage (benang, greige, PFD, PFP, bahan jadi) lewat Master Produk: atribut wajib, satuan, kategori; apakah server menolak kombinasi yang tidak sah |
| A-S2 | Ubah stage/satuan produk yang sudah punya stok atau dokumen |
| A-S3 | Varian dan spesifikasi dari R&D untuk tiap stage (form spesifikasi & editor varian) |
| A-S4 | Jual tiap stage di POS (benang, greige, PFP, PFD, bahan jadi): mana yang boleh, mana ditolak, ditolak oleh server atau hanya layar |
| A-S5 | PO pembelian benang (kg) dan greige (meter/yard): satuan, konversi, harga per satuan |
| A-S6 | Langkah makloon yang tidak cocok stage (printing dengan bahan greige; celup dengan PFP) — lewat layar **dan** lewat API langsung |
| A-S7 | Tambah tahapan proses baru di master tahapan lalu pakai di SPK; nonaktifkan tahapan yang masih dipakai dokumen |
| A-S8 | Label dan istilah stage di semua layar (PFP/PFD, greige/grey, benang/yarn): daftar ketidakkonsistenan |
| A-S9 | Kueri hanya-baca data acuan: produk/roll yang stage, satuan, kategori, atau riwayat prosesnya tidak cocok (jumlah + contoh) |
| B-S1 | Makloon greige → PFD → celup → bahan jadi, satu mitra per langkah, sampai stok hasil & HPP |
| B-S2 | Makloon greige → PFP → screen → printing → bahan jadi |
| B-S3 | Makloon benang → tenun/rajut → greige |
| B-S4 | Terima sebagian; sisa masih di mitra; susut melebihi batas |
| B-S5 | Hasil ditolak QC → kembali ke mitra / klaim ke mitra |
| B-S6 | Batal di tengah saat bahan sudah di mitra |
| B-S7 | SPK dari Pesanan Khusus/SO vs dari stok; SPK dibuat lewat Wizard vs lewat modal buat — apakah dokumennya sama |
| B-S8 | Tagihan jasa per langkah + HPP hasil (bahan + jasa + susut) sampai ke roll, jurnal, dan rekap |
| B-S9 | Perbaikan (repair order) dan pengerjaan ulang |
| B-S10 | Makloon antar-PT (bahan milik PT lain / mitra dipakai beberapa PT) |
| C-S1 | Permintaan desain → sample → keputusan pelanggan → spesifikasi → SKU |
| C-S2 | Pesanan Khusus → R&D → sample → SKU (pintu `create-sku`) — bandingkan dengan C-S1 |
| C-S3 | Sample ditolak, direvisi, divalidasi ulang |
| C-S4 | Gerbang R&D dan uji wajib: yang ditawarkan layar vs yang ditolak server |
| C-S5 | SKU dari R&D masuk produksi/makloon/pembelian (stage dan satuan yang lahir) |
| C-S6 | KPI desainer/R&D dari data acuan dibanding hitungan tangan |
| D-S1 | Retur jual per roll dari SO terkirim → scan masuk karantina → inspeksi → masuk stok → refund |
| D-S2 | Retur jual → scrap → batal scrap |
| D-S3 | Retur jual → klaim ke supplier (berantai) → retur beli |
| D-S4 | Retur jual sebagian roll (potong) / cut-loss split |
| D-S5 | Retur jual dengan penggantian barang / kompensasi / nego |
| D-S6 | Retur beli manual sebelum dan sesudah ditagih; lalu koreksi (reverse) |
| D-S7 | Retur antar-PT |
| D-S8 | Retur ditolak atau dibatalkan sebelum diselesaikan |
| E-S1 | Penerimaan PO ber-QC: terima, tolak sebagian, tolak + retur (ganti barang / potong tagihan) |
| E-S2 | QC 4-point per roll → grade → harga dan stok |
| E-S3 | SPK inspeksi MD Quality (PA ke gedung inspeksi) → hasil → kembali ke stok |
| E-S4 | QC hasil makloon |
| E-S5 | Pemeriksaan retur jual (grade turun, rusak) |
| E-S6 | Siapa boleh memutuskan apa (izin, bukan nama peran) untuk `qc@`, `mdquality@`, `warehouse@`, `manager@` |
| F-S1 | POS checkout → SO → alokasi otomatis → kirim → faktur, panjang roll nyata ≠ pesanan |
| F-S2 | Realokasi roll sesudah DP dibayar: tagihan, DP, piutang |
| F-S3 | Stok kurang → rencana pemenuhan (stok / PT lain / PO / tunggu) lewat keempat modul pemenuhan — hasilnya sama? |
| F-S4 | Keep → lewat batas umur → pending → dibuka lagi: reservasi dan backorder |
| F-S5 | Batal satu baris sesudah alokasi / sesudah bayar |
| F-S6 | Harga khusus / persetujuan harga, lalu alokasi berubah |
| F-S7 | Pesanan → PR/PO supplier (backorder) → barang datang → alokasi otomatis |
| F-S8 | Angka pesanan yang sama di layar berbeda (POS, daftar pesanan, meja admin sales, piutang) — cocok? |

### Form wajib (inventaris per komponen pilihan)

| ID | Berkas | Domain |
|---|---|---|
| A-F1 | `ProductMasterForm.jsx` | master produk |
| A-F2 | `VariantEditor.jsx` | varian |
| A-F3 | `SpecVariantFields.jsx` | varian dari spesifikasi |
| A-F4 | `LinkExistingVariant.jsx` | tautkan varian |
| A-F5 | `EntityMastersView.jsx` | master per PT (ikuti komponen anak) |
| A-F6 | `UomConversionView.jsx` | konversi satuan |
| A-F7 | `PoStageModal.jsx` | tahap PO |
| A-F8 | `CuttingDesk.jsx` | potong |
| B-F1 | `MakloonWizard.jsx` | buat SPK (wizard) |
| B-F2 | `MakloonOrderCreateModal.jsx` | buat SPK (modal) |
| B-F3 | `MakloonStepEditor.jsx` | langkah |
| B-F4 | `MkoStepModals.jsx` | aksi langkah |
| B-F5 | `RecipeFormModal.jsx` | resep proses |
| B-F6 | `MakloonOrderDetailPanel.jsx` | rincian SPK (ikuti komponen anak) |
| C-F1 | `SpecFormModal.jsx` | spesifikasi R&D |
| C-F2 | `SampleFormModal.jsx` | sample |
| C-F3 | `ExistingSkuSection.jsx` | SKU yang ada |
| C-F4 | `SpecDetailPanel.jsx` | rincian spesifikasi (ikuti komponen anak) |
| C-F5 | `DivisionsView.jsx` | divisi desain |
| D-F1 | `CreateReturnForm.jsx` | retur jual |
| D-F2 | `ReturnDispositionPanel.jsx` | disposisi retur (ikuti komponen anak) |
| D-F3 | `ReturnRollClaims.jsx` | klaim per roll |
| D-F4 | `PurchaseReturns.jsx` | retur beli |
| E-F1 | `QCInspection.jsx` | QC penerimaan |
| E-F2 | `InspectLineModal.jsx` | inspeksi per baris |
| E-F3 | `InspectSheetGrid.jsx` | lembar inspeksi |
| F-F1 | `CheckoutDrawer.jsx` | checkout POS |
| F-F2 | `CheckoutStep3.jsx` | langkah 3 checkout (ikuti komponen anak) |
| F-F3 | `ReallocateRollsModal.jsx` | realokasi roll (ikuti komponen anak) |
| F-F4 | `PriceApprovals.jsx` | persetujuan harga |

### Definisi selesai

- **Per domain**: semua skenario domain itu ada di matriks dengan status dan bukti (atau `terhambat` beralasan); semua form
  wajibnya diinventaris sebanyak komponen pilihannya; peta sumber kebenaran dan pintu ganda terisi; setiap temuan lengkap
  dan terdaftar di `TRACKER.md` (bagian baru "Audit domain — <tanggal>", status `open`); tidak ada "TODO/TBD/belum dicek".
- **Seluruh audit**: `python3 scripts/review/periksa_selesai.py audit docs/audit/<tanggal>-domain` mencetak
  **HASIL: SELESAI**, `00-RINGKASAN.md` berisi `## 10 masalah terbesar` (10 butir bernomor ber-ID), `## Peta duplikasi`,
  `## Pertanyaan untuk pemilik` (bernomor).
- **Per sesi**: `periksa_selesai.py progres` dijalankan (menulis `docs/reviews/PROGRES_REVIEW.md`), satu baris di
  `docs/reviews/LOG_REVIEW.md`, commit, push ke cabang `review/<YYYY-MM-DD>`. Bila berhenti sebelum selesai, tulis domain
  dan skenario terakhir yang dikerjakan di log.
- **Bukan bukti**: membaca dokumen tanpa membuka kode/layar; "tampaknya"; skenario yang tidak dijalankan; menyalin temuan
  audit lama tanpa memeriksa ulang di `HEAD`.
