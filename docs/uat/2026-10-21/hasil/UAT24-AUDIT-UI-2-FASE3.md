# UAT 24 Okt — Audit UI tahap 2 · Fase 3 (penggabungan layar duplikat & tata letak)

- Commit (branch `main`): `8bbd1fe` (P1 fondasi) · `2435ad8` (P2 Pengaturan & master) · `fe81929` (P3 penjualan,
  persetujuan, beranda & sampel) · `effc833` (P4 keuangan, pajak & dokumen) · `bdf405a` (P5 rantai pasok) ·
  `bdfcb4e` (P6 R&D, desain & SDM) · `2286728` (P7 aplikasi HP) · `24b2597` (P8 aktivasi alias & menu, katalog
  akses) · `c5eff81` (guardrail lintas paket) · `5599264` & `e7d21bc` (perbaikan hasil crawl HP). Baseline fase 3: `b2c092e`.
- Dasar: keputusan pemilik 26 Okt atas audit UI tahap 2 ([UAT24-AUDIT-UI-2.md](UAT24-AUDIT-UI-2.md) §Keputusan) —
  semua rekomendasi duplikasi disetujui (layar duplikat → tautan/alias ke layar utama, layar lama tidak dihapus),
  **form input di HP tidak diringkas** (isian sama lengkap dengan desktop), urutan tata letak L-04 → L-03 →
  L-01 & L-05 → L-09 → sisanya, papan Beranda "PO Custom" & "Barang ditahan QC" menjadi tautan,
  Labdip/Handfeel/Proofing satu layar Sample R&D (galeri tetap), istilah UI tidak diubah (K-13).
- Rencana: [`audit-ui-2/rencana-fase3.md`](audit-ui-2/rencana-fase3.md). Laporan per paket (status per butir, berkas,
  cara cek, uji, perubahan perilaku): [`audit-ui-2/fase3/`](audit-ui-2/fase3/) (`P1.md` … `P8.md`, `P4_L03A/B.md`,
  `COORD_TODO.md`).

## Yang dikerjakan (ringkas per paket)

| Paket | Butir | Hasil utama |
|---|---|---|
| P1 | fondasi | registri alias + preset (`viewAliases.js`, `useViewPreset`, `useAppNav`), PageTabs/FilterChips/ResponsiveTable/LinkCard/EntityRequiredNotice/DesktopOnlyNotice/FormSection, FormModal/DetailModal layar penuh di HP, papan mode tautan, `approvalDecisions`, App.js dipecah, guardrail ratchet |
| P2 | P16-K1, D-01…D-04, D-21, D-29, Koreksi Harga | menu Pengaturan per kelompok (12 menu + 10 layar `settings-cfg-*`), Template Dokumen, Kategori Beban, Komisi & Insentif, Aturan Persetujuan, Satuan & Konversi, Perangkat; DesktopOnlyNotice semua layar Pengaturan |
| P3 | D-05, D-06, D-07, D-14, D-17, D-24a, L-04 | satu form pelanggan lengkap (CRM/POS/Checkout/Admin/HP), papan PO Custom & QC = tautan, Matriks divisi jadi tab Pusat Persetujuan, PT harga ikut header, satu kontrol status Pesanan, Meja Cutting → tautan; beranda/SO/sampel layak 390 px |
| P4 | D-10…D-14, D-20, L-03/L-07/L-08 | satu ringkasan laba-rugi, Profitabilitas satu layar margin, kelompok umur seragam, satu rekap PPN; pop-up keuangan → FormModal/DetailModal |
| P5 | D-15, D-16, D-18, D-19, D-22, D-23, D-25, D-28, L-03/L-04 | Stock Opname + Sapu RFID, satu daftar transfer, satu pop-up PO, satu tombol pengiriman, Kinerja Mitra Makloon, Barang ditahan QC → SPK Inspeksi; form pembelian/gudang/makloon → FormModal |
| P6 | D-08, D-09, D-24b/c, L-03/L-04 | Sample R&D satu layar (chip jenis, galeri tetap), satu galeri desain, satu rapor KPI desainer, form ubah spesifikasi lengkap |
| P7 | L-09, D-26, D-27, HP D-05/06/07/28 | satu kerangka 4 aplikasi HP (app bar, lonceng, ≤ 5 tab, tab Lainnya), satu pintu "Tampilan desktop", form HP = form desktop lengkap |
| P8 | aktivasi | 14 alias aktif, tab lama dicabut dari hub (rute lama tetap), label menu, katalog akses peran kustom, gerbang per bagian memakai id lama (`hidden_views` tetap dipatuhi) |

### Alias aktif (layar lama → layar utama)
`my-approvals` → Pusat Persetujuan tab Matriks divisi · `cs-design-gallery` → Desain & Pattern mode Galeri (ACC) ·
`costing` → Profitabilitas tab katalog · `interco-transfers` → Operasi Gudang tab Transfer jenis antar-PT ·
`rnd-labdip`/`rnd-handfeel`/`rnd-proofing` → Sample R&D mode Galeri + chip jenis · `doc-templates-basic` →
Template Dokumen tab dasar · `uom-conversions` → Satuan & Konversi · `cs-rfid-devices` → Perangkat tab RFID ·
`settings-hub` → Master Grade Mutu (legacy). Deep link, notifikasi & akses peran lama tetap berfungsi.

## Perubahan perilaku yang perlu diketahui saat UAT
- **Menu Pengaturan** kini satu grup sidebar berisi 7 kelompok: Perusahaan & Akun · Persetujuan · Kebijakan per
  Domain (Penjualan, Gudang & Mutu, Pembelian & Produksi, Keuangan & Pajak, SDM, R&D) · Master Data · Dokumen &
  Cetak · Notifikasi & Penjadwal · Integrasi & Sistem. Kebijakan Retur ada di Pengaturan › Penjualan; Koreksi Harga
  di Produk & Harga; Perangkat (mesin absen + RFID) dan "Semua pengaturan" di Integrasi & Sistem.
- **Papan Beranda** PO Custom & Barang ditahan QC tidak lagi punya tombol Setujui/Lepas — klik membuka dokumennya
  (PO Custom → rincian pesanan khusus; QC → SPK Inspeksi dengan saringan "Hanya yang DITAHAN").
- **Persetujuan Saya** kini tab "Matriks divisi" di Pusat Persetujuan; tab Amandemen menjadi kartu tautan ke Koreksi
  & Amandemen.
- **Sample R&D**: menu Labdip/Handfeel/Proofing membuka satu layar dengan chip jenis; mode Galeri sama dengan galeri
  lama.
- **Aplikasi HP**: tombol desktop & keluar pindah ke tab **Lainnya**; tab Notifikasi diganti lonceng di app bar;
  Gudang: "Belum Tag" menjadi segmen di tab Pindai. Form pelanggan, permintaan internal & permintaan desain di HP
  sekarang lengkap seperti desktop (layar penuh, satu kolom).
- **Layar pengaturan/akuntansi/konsolidasi di HP** menampilkan banner "paling nyaman di desktop" (layar tetap bisa
  dipakai).
- **Profitabilitas**: tab Realisasi hanya untuk peran berizin akuntansi. Kontrak pemasok: "Isi massal harga
  internal" kini tautan ke Harga Internal Antar-PT (saringan Harga Internal di Kontrak tetap).

## Bukti uji
- **Jest** penuh `--maxWorkers=1` (P8, setelah semua paket): **63 suite / 437 uji lulus**. Uji baru: `phase3*`
  (P3, P4, P5, P6, P8, Settings), `mobileShell`, `serverAccessReach` (jangkauan menu dengan izin dari server).
- **ESLint** 0 error di semua berkas yang berubah; pyflakes backend 0 baru.
- **Guardrail**: `check_nav_map`, `audit_config_wiring`, `verify_access_catalog_nav`, `verify_desk_targets`,
  `verify_home_kpi`, `verify_view_aliases`, `verify_page_tabs`, `verify_custom_modals`, `verify_detail_modal`,
  `verify_modal_dismiss`, `verify_escape_layers`, `verify_uom_vocab`, `verify_error_notice`,
  `verify_blocking_dialogs`, `verify_entity_label`, `verify_role_label` **PASS**. Ratchet turun: pop-up buatan
  sendiri 155 berkas / 173 pola → **112 / 123**; tab buatan sendiri 22 / 51 → **16 / 31**. Tiga guardrail yang
  merah sebelum fase 3 kini hijau (`verify_error_notice` 4 → 0, `verify_blocking_dialogs` 3 → 0,
  `verify_entity_label` 7 → 0). `verify_approval_queues` **tetap merah 15** (sama dengan sebelum fase 3; backend).
- **Backend** (setelah restart; pembanding = kontainer baseline `8bbd1fe` ke DB yang sama `kn_test_trial`):
  uji akses & keputusan (`test_l01_custom_role`, `test_ln015_*`, `test_fe03_access_catalog`,
  `test_phase3_p2_settings_groups`, `test_uat26_d3_decisions`, `test_gl01_account_mapping`) lulus; 19 berkas uji
  yang menyentuh modul berubah: **24 gagal identik di baseline**, 202 lulus (baseline 200 — selisih = uji baru);
  POC inti: `role_access` 41/43, `e8_roles` 56/64, `f6_approval_coverage` 37/38, `e4_master_layers` 55/56,
  `approval_reminder` 26/26 — **setiap kegagalan identik di baseline** (data penugasan PT akun uji, hitungan antrean
  SO, setelan penerimaan OCR hanya global, penjaga antrean).
- **API**: Admin Sales & Admin Gudang kembali mendapat grup Pengaturan (`view_resources["settings-hub"]`) —
  Kebijakan Retur & Master Grade Mutu tampil (temuan P7, diperbaiki P8).

## Verifikasi crawl sesudah fase 3
Crawler yang sama dengan audit tahap 2 (Edge headless; aksi tulis diblokir, hanya membuka/menelusuri) ke stack uji
(DB `kn_test_trial`), sesudah semua commit fase 3.

- **Desktop 1440 px — 127 layar** (semua layar yang komponennya tersentuh fase 3, 10 layar `settings-cfg-*`,
  "Semua pengaturan", dan 14 alias): **1.690 keadaan** (halaman, tab, detail, pop-up, pop-up bertingkat, menu).
  **0 galat JavaScript, 0 halaman melebar, 0 halaman kosong.** Respons ≥ 400: 403 di Beranda/Pusat Persetujuan
  untuk peran non-manajer (sudah ada di crawl sebelum fase 3) dan 404 berkas unggahan (gambar desain, lampiran
  sample, foto pengiriman, bukti keputusan pelanggan) yang memang tidak ada di penyimpanan DB uji — bukan kode.
- **Alias** — setiap `?view=<id lama>` mendarat di layar utama dengan preset yang benar (dicek tangkapan): Persetujuan
  Saya → Pusat Persetujuan tab Matriks divisi; Galeri desain → Desain & Pattern tab Galeri status ACC;
  `costing` → Margin Katalog & HPP; Transfer antar-PT → Operasi Gudang tab Transfer chip "Antar PT"; Labdip/
  Handfeel/Proofing → R&D Produk Baru tab Galeri chip jenis; Template dasar, Satuan, Perangkat RFID, `settings-hub`,
  dan 3 alias lama (approvals, finance, purchase-orders) — semuanya tanpa galat.
- **HP 390 px — 45 layar desktop** (kelas B yang dibuka dari aplikasi HP + kelas C Pengaturan/akuntansi):
  **755 keadaan, 0 galat JavaScript.** Dua layar melebar beberapa piksel — **Perangkat** (455 px, baris mesin absen)
  dan **rincian Order Makloon** (397 px) — karena grid tanpa kolom eksplisit di bawah `lg`; diperbaiki
  (`5599264`, kolom `minmax(0,1fr)`), diukur ulang & di-crawl ulang: lebar 390 = viewport, 0 penanda.
- **Aplikasi HP 12 peran** (tiap tab bawah + tiap butir menu Lainnya sebagai titik awal): **170 tampilan HP**
  (designer, finance, md_quality, qc, sample_admin, warehouse 41 · admin, manager, md, sales, sales_admin,
  warehouse_admin 119 · finance ulang 10), **±1.700 keadaan, 0 galat JavaScript, 0 halaman melebar.**
  - Satu regresi P7 ditemukan & diperbaiki: di antrean lintas tahap, "Buka layar lengkap" membawa **Finance** ke layar
    PR yang tidak boleh ia buka ("Permission ditolak"). *Koreksi (fase 4):* Finance BUKAN pemutus PR —
    `/approvals/my-queue` mengirim semua dokumen tertunda ke pemegang `approval.view` (dengan `can_decide`), dan HP
    menampilkan semuanya; fase 4 · R5 menyaring HP ke `can_decide`. Tombol kini hanya tampil bila layar tujuan boleh dibuka peran itu (aturan menu yang
    sama, termasuk izin server); crawl ulang Finance: 0 akses ditolak.
  - Keterbatasan alat: Edge headless putus setelah "Aktifkan notifikasi" + ganti PT di tab Lainnya (admin/manager);
    dicek manual di peramban biasa (normal, tanpa galat), lalu kedua tombol itu dilewati crawler pada putaran ulang.
  - Respons 403 lain yang baru terlihat (bukan dari fase 3 — gerbang tidak berubah): tab **Lot & Silsilah** di Stok &
    ATP terdaftar untuk sales sejak lama padahal server tidak memberi izin lot ("Registri LOT tidak tersedia untuk
    peran Anda"); panggilan latar `/config/health` (sales, Admin Sales di Semua pengaturan baca-saja) & `/makloons`
    (Admin Sales di Lot). Dicatat di Belum dikerjakan.
- Catatan risiko: pola grid serupa (`grid gap-3 lg:grid-cols-[…]` tanpa `grid-cols-1`) masih ada di ±20 layar
  lain; hanya melebar bila isinya punya baris panjang yang tak bisa dipatahkan. Tidak tertangkap crawl ini.

## Belum dikerjakan
> **Fase 4 (26 Okt) mengerjakan sisa di bawah** — lihat [UAT24-AUDIT-UI-2-FASE4.md](UAT24-AUDIT-UI-2-FASE4.md).

- **Form HP yang belum setara desktop** (audit P7, hanya laporan): PR MD (supplier, pemilih artikel, alasan rute →
  sebaiknya `PrCreateModal`), Kwitansi (tanggal, deposit, mode alokasi, selisih bayar → `ARReceiptModal` perlu
  FormModal dulu), Amandemen (diskon tingkat pesanan, lampiran → `AmendmentProposeModal` perlu FormModal dulu).
- **Pop-up buatan sendiri tersisa** (ratchet 112 berkas): a.l. keuangan (`JournalEntryModal`, Rekonsiliasi ×5,
  `TaxInvoices`, `StoreCredit`, `AmendmentProposeModal`, kontrabon ×4, WhatsApp/TTD), rantai pasok
  (`PurchaseRequisitionDetailPanel`, `GrnCreateWizard`, `GrnOcrSampleEditor`, `RollInspectionModal`,
  `MakloonOrderDetailPanel`), R&D (`DesignFormModal`, `CategoryManagerModal`, `SampleProofGallery`).
- **Tata letak sisa (L-01/L-02/L-06/L-07/L-08/L-10)** di luar daftar paket: inventory-lots & QC Hub (L-01),
  RFID gate/tag, analitik stok, eskalasi, perbaikan, akun marketing, template produk (L-02), KPI Operasi Gudang,
  designer-kpi, retur (L-06), RfidTags/StockAnalytics/KpiView/AttendanceView (L-07), bilah alat & KPI
  makloon/logistik/papan stok/designer-kpi/mkt-calendar/hr-leave (L-08), form Induk produk (L-10).
  `InspectionDetailPanel.jsx` 658 baris (> 500 sejak sebelum fase 3).
- **Backend**: `verify_approval_queues` 11 pintu keputusan tanpa antrean + antrean bayangan (nota kredit 8,
  credit override 1, Barang Masuk `review` 1, cetak RFID `verified` 4); `/reports/order-velocity` belum disaring per
  sales (panel kecepatan dibatasi admin/manajer); kegagalan POC/uji lama di atas (data penugasan PT akun uji).
- **Gerbang akses lama yang terlihat di crawl HP**: tab Lot & Silsilah tampil untuk sales tanpa izin lot (sembunyikan
  tab atau beri izin baca lot); antrean HP menampilkan dokumen yang tak bisa diputus peran itu (lihat koreksi di
  atas); panggilan latar `/config/health` & `/makloons` ditolak untuk sales/Admin Sales (diam, layar
  tetap tampil).
- Aplikasi HP MD masih punya tiga baris "Tampilan lengkap" Labdip/Handfeel/Proofing (kini mendarat di layar yang
  sama lewat alias; istilah tidak diubah — K-13).
