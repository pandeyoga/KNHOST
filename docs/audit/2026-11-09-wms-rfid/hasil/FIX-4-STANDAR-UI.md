# FIX-4 — Standar UI Gudang v1 tahap 1 (token · kelas baku AA · Unduh Excel/CSV · HP gudang · guardrail)

- **Tanggal:** 9 Nov 2026 (WIB, selesai ±18.00) · **Pelaksana:** Claude Code (implementer paket FIX-4) · **Branch:** worktree
  `worktree-agent-a746eaf411a01b164` (dasar `main` `a8275bf` = FIX-1 + FIX-2 + FIX-3a/3b).
- **Keluhan pemilik yang dituju:** "standarisasi UI element mulai dari form, button size, adanya search, filter dll dan
  ukurannya, design UI elementnya, harus ada export Excel"; "masih banyak yang perlu dikonsistenkan".
- **Status:** `implemented_pending_review` (implementer tidak menetapkan `verified`). Verifikasi tampilan (360/390 px,
  desktop) diserahkan ke koordinator — paket ini tidak memakai alat peramban.
- **Dokumen standar:** **`docs/KN_37_STANDAR_UI_GUDANG.md` (baru)** + catatan "digantikan sebagian" di kepala
  `docs/KN_08_UI_UX_STANDARDS.md`. Alasan memilih dokumen baru (bukan menyunting KN_08): KN_08 v1.0 adalah standar seluruh
  aplikasi bergaya bahasa Inggris yang sudah jauh dari kode (Inter, primer navy, radius 6, shadcn wajib, camera-first);
  K-B4-01 memutuskan standar baru **menggantikan bagian yang bertentangan** — dokumen terpisah membuat batas "yang berlaku"
  tegas dan bisa dirujuk guardrail, sementara bagian KN_08 yang masih benar (prinsip, keadaan kosong/galat, anti-pola)
  tetap berlaku tanpa ditulis ulang.

---

## 1. Keputusan yang diterapkan (mandat pemilik lewat koordinator)

| Keputusan | Penerapan |
|---|---|
| **K-B4-01** standar wajib, ditegakkan ratchet | `KN_37` + guardrail `verify_ui_standard.py` (ratchet 7 metrik + 2 cek keras) & `verify_ui_contrast.py` (keras); KN_08 ditandai digantikan sebagian |
| **K-B4-02** skala 12/13/14/16/20/24 (+ kios), min 12 px desktop, HP ≥ 16/14 — **bertahap** | token `--fs-*` + Tailwind `text-fs-*`; **kelas baku** (`components.css`, `purchasing.css`, `mobile.css`) 36 deklarasi < 12 px → 12 px; **aplikasi HP gudang** dibersihkan (kelas `kn-hp-*`); sisanya dibekukan ratchet, tidak dirombak massal |
| **K-B4-03** warna AA lewat token | token `--kn-*`; `primary-button`/`btn-primary`/`nav-button.active` `#007AFF`→`#0058CC`; `danger-button`/`btn-danger` `#FF3B30`→`#B42318`; batas isian `#D6D7DC`→`#8A8A8E`; placeholder & `.text-muted` → `#6B6B73` (rasio §4) |
| **K-B4-04** uji 360 & 390 px | ukuran HP berbasis lebar penuh & `min-height` (tanpa lebar tetap); pengukuran visual = koordinator (§9) |
| **K-B4-06** komponen baru pakai KN_32, layar lama tak diganti istilah | label Unduh/Excel/CSV/saringan memakai istilah yang ada; tidak ada istilah layar lama yang diubah |
| **K-B4-07 + K-B3b-04** Excel (XLSX) + CSV lewat SATU komponen baku memakai Pusat Export, ≤ 50.000 langsung, > → job, ikut saringan & cakupan, semua daftar WMS-RFID, peran gudang diberi akses | `components/ExportMenu.jsx` + `POST /api/export-center/quick`; 31 dari 37 daftar matriks B3b dipasang, 6 dikecualikan beralasan (§3); `warehouse` dapat `data_export` dibatasi daftar putih dataset gudang |
| **K-B4-11** tanda `*` wajib | dipertahankan (`FormSection`), ditulis di KN_37 §5 |
| **K-B4-12** tampilan tersimpan | **di luar paket** (sisa) |
| **K-B1-06** `primary-button` dkk. standar resmi + varian `touch` (≥ 48 px) + larang `!py-*` | pengubah resmi `btn-sm` (≥ 32 px) & `btn-touch` (≥ 48 px) + `btn-primary-cta` (56 px) di `styles/standard.css`; ratchet `btn_force` & `btn_custom` |
| **K-B1-09** huruf minimum | = K-B4-02 |

## 2. Temuan yang ditutup (ID → perubahan → uji)

| ID | Perubahan | Uji |
|---|---|---|
| **B3b EXP-01** (P2) — tidak ada XLSX di daftar WMS-RFID | Tombol baku **"Unduh ▾"** (`ExportMenu`): **Excel (.xlsx) bawaan + CSV**, lewat mesin Pusat Export. Endpoint baru `POST /api/export-center/quick` (izin `data_export.export`): spesifikasi = dataset + saringan + **cari** + **cakupan daftar** (`entity_scope` `active`/`all`/**`work`** = cakupan pekerjaan fisik FIX-1; `location_view`; header `X-Location-Scope`). ≤ **50.000** baris → berkas langsung (`X-Export-Rows`, nama berkas WIB), lebih → **job latar** (202) + notifikasi `export_ready` "Unduhan siap". XLSX berlembar **Ringkasan** (dataset, saringan & cari, **Lokasi**, PT, pengguna, waktu, jumlah). Mode "Semua Entitas" boleh (POST hanya-baca, allowlist `entity_write_guard`). | `test_fix4_ekspor.py` (15), jest `fix4StandarUi` (14) |
| **B3b EXP-02** (P2) — ±45 daftar tanpa ekspor; penjaga hanya melihat `<PaginationBar>` | 31 layar daftar WMS-RFID kini ber-Unduh (tabel §3); `PaginationBar` menerima `exportSpec`; guardrail baru menghitung **pager tanpa Excel** (ratchet) + daftar keras **`WMS_LISTS`** (matriks B3b) wajib Unduh/pengecualian beralasan + **kontrak Unduh↔registry** (dataset/kolom saringan/urut/tanggal/cari harus ada) | `verify_ui_standard.py` (+ self-test 20 kasus) |
| **B3b EXP-03** (P2) — CSV Logistik koma, tanpa BOM, baris tampil saja | `LogisticsView` & `HistoryPanel`: CSV buatan sendiri **dihapus**, diganti `ExportMenu` (Excel + CSV dialek Indonesia `;`/BOM/desimal koma, **semua hasil saringan**, tanggal & moda ikut) | jest (sumber tanpa `new Blob([[head.join(",")…`), backend `test_csv_semicolon_bom_decimal_comma` |
| **B3b EXP-04** (P3) — id/kode mentah di berkas | Kolom **saringan** baru `C(..., default=False)` (id gudang/produk/mitra/bin/…) — ikut filter, **tidak** ikut kolom bawaan berkas; status tetap dilabeli Indonesia (mesin lama) | `test_filter_only_columns_not_in_default_file` |
| **B3b EXP-05** (P3) — dataset WMS-RFID baru belum ada | Dataset baru (`services/export_registry_wms.py`): **Perintah Simpan ke Rak (PA), Perbaikan, Job cetak label, Insiden RFID, Perangkat RFID, Lintasan gerbang, Opname RFID**; dataset lama dilengkapi kolom layar (GRN: mitra/No. SJ/gudang/dibuat; tugas gudang: SO/pelanggan/roll/dibuat; saldo: stok fisik/roll; opname: nama/mode/gudang; tag/pembacaan RFID; pengiriman; retur beli; LOT) + **jalur cari = endpoint daftarnya** (`search_fields`, nama produk/gudang/PT diselesaikan ke id) | `test_datasets_listed_for_admin_and_operator`, `test_every_list_dataset_exports_with_search_and_sort` (24 dataset) |
| **B3b K-B3b-04** — peran gudang & ekspor | `DEFAULT_PERMISSIONS["warehouse"]["data_export"] = ["view","export"]` (diterapkan `sync_permission_modules` sekali); mesin export membatasi peran `warehouse` ke **daftar putih 21 dataset gudang** (bukan penjualan/keuangan/Riwayat Nilai Roll); menu Pusat Export untuk `warehouse` (mengambil job besar). Pagar lokasi petugas berpagar **selalu** berlaku — juga untuk koleksi di luar `WAREHOUSE_FIELDS` (`location_fields`: LOT, pembacaan/insiden/perangkat/lintasan/opname RFID) dan lewat dokumen lain (`location_clause`: SPK→tugas, pengiriman→surat jalan) | `TestWarehouseRole` (5) |
| **B1 UI-30** (P2) — ekspor tidak merata; CSV logistik beda format | = EXP-01/02/03 | — |
| **B1 UI-26 / B1b UI-53** (P2) — huruf < 12 px / HP 75–90 % < 14 px | Kelas baku: **36 deklarasi CSS < 12 px → 12 px** (`components.css` 28, `purchasing.css` 3, `mobile.css` 1 + 4 diganti eksplisit) — `status-pill`, kepala tabel, `field-label`, `kicker`, kartu metrik, kartu `ResponsiveTable`, dll. HP gudang (Masuk/Keluar/Sample/Pindai/Belum Tag/Daftar Awal/Lainnya): judul & info keputusan **16 px**, pendukung **14 px**, label & tab HP 14 px; `text-xs` 0 | jest (statis), census §5 |
| **B1 UI-24 / B1b UI-52** (P2) — target sentuh HP < 44/48 px | Tombol aksi HP `btn-touch` (≥ 48 px) / `btn-primary-cta` (56 px: Terima, Ambil, Pindai, Potong, Simpan & lanjut); isian `kn-input-touch` (≥ 48 px; isian pindai utama 56 px); chip PT `kn-chip-touch`; lonceng/ikon app bar tampak 40 px dengan area sentuh **48 × 48**; tab bawah ≥ 56 px; `PageTabs`, bilah "Lokasi", label di dalam `.m-shell` ≥ 48 px / 14 px; tombol pop-up HP 44 → 48 px | jest (statis), census `hp_touch` 47 → 13 (HP gudang 35 → 1) |
| **B1 UI-27** (P3) — hex lepas | HP gudang: **96 → 26** literal hex (berkas gudang HP: 70 → 0); himpunan hex berbeda aplikasi **dibekukan** (703) — warna baru wajib token | ratchet `hex` + `ui_hex_set.json` |
| **B1 UI-28 / B3b FRM-17** (P2) — tombol gaya sendiri, `!py-*` | Kelas resmi + pengubah `btn-sm`/`btn-touch`; pager baku pakai `kn-pager-btn` (dulu 7 tombol hex lepas); ratchet `btn_custom` & `btn_force` | ratchet |
| **B4 §2.2** — 7 pasangan kontras gagal | `primary-button` 4,02 → **6,43:1**, `danger-button` 3,55 → **6,57:1** (hover 4,30 → 8,80), `btn-primary`/`btn-danger`/`nav-button.active` idem, placeholder 2,77 → **5,28:1**, `.text-muted` 3,26 → **5,28:1**, batas isian 1,44 → **3,44:1** | `verify_ui_contrast.py`: **merah di `main`** (8 kelas baku gagal), **hijau 58/58** sesudah |

## 3. Layar daftar WMS-RFID & tombol Unduh (matriks B3b lampiran B)

Cakupan: **W** = `scope="work"` (lokasi tampilan + semua PT ditugaskan, = daftar FIX-1) · **A** = PT aktif · **L** = + saringan
tampilan lokasi. "Saringan" = yang ikut ke berkas; "tak ikut" → butir server **nonaktif dengan alasan** (`unsupported`).

| Layar (berkas) | Dataset | Cakupan | Saringan & cari yang ikut | Catatan |
|---|---|---|---|---|
| Kedatangan (GRN) `wms/grn/GoodsReceiptsView` | goods_receipts | W | chip status, cari (no. GRN/SJ/mitra) | — |
| Tugas barang masuk (mode lama) `wms/InboundScanInterface` | wms_tasks | W | alur masuk PO + status | — |
| Antrean QC kedatangan `wms/QCInspection` | wms_tasks | A+L | `qc_pending`, cari | — |
| SPK inspeksi `inspections/InspectionsView` (pager) | inspections | A | jenis, status, lini, cari | "ditahan" → `unsupported` (CSV kolom-layar tetap) |
| Antrean penempatan rak `wms/LocationPutawayView` | inventory_rolls | A | gudang, belum ber-bin, sisa > 0, status fisik | — |
| Perintah simpan ke rak `wms/PutawayOrdersPanel` | putaway_orders | W | aktif (≠ draf/batal), gudang asal ATAU tujuan | dataset baru |
| Draf PA `wms/PutawayDraftsPanel` | putaway_orders | W | draf, gudang | — |
| Master gudang `wms/warehouses/WarehouseMasterView` | warehouses | — | cari | chip "Boleh dipakai" (dihitung per PT) → `unsupported`; "Semua" bisa |
| Transfer `wms/TransferManagement` | warehouse_transfers | W | status, jenis, lini, cari (kode/peminta/SO/produk/gudang/PT) | — |
| Sesi opname `inventory/CycleCount` | cycle_count_sessions | W | bukan pendaftaran | — |
| Sesi pendaftaran `inventory/registration/InitialRegistration` | cycle_count_sessions | W | mode pendaftaran | — |
| Stok › Saldo `wms/InventoryStockView` | inventory_balances | A+L | gudang, cari (produk/SKU/gudang/PT) | `BalancesTable` = anak layar ini |
| Stok › Roll (pager) | inventory_rolls | A+L | gudang, lini, cari (roll/lot/…/produk) | cek MDQ/4-point → `unsupported` |
| Stok › Mutasi (pager) | inventory_movements | A | gudang, jenis, cari | — |
| Perbaikan `wms/repair/RepairOrdersView` | repair_orders | A | status, cari | dataset baru |
| Lot `inventory/lots/LotsView` (pager) | inventory_lots | A | asal, status, tahap, gudang, cari | — |
| Tugas barang keluar `wms/OutboundScanInterface` | wms_tasks | W | alur keluar, status, gudang, jenis (SO/sample + syarat terima cutting), cari | — |
| Cutting `wms/CuttingOpsView` | wms_tasks | W | sample_cut terbuka, gudang, cari | tahap paket (dihitung layar) → `unsupported` kecuali "Semua" |
| Pesanan sample `samples/SampleOrdersView` | sales_orders | A | jenis sample, status, cari | bukan layar peran gudang |
| Pengiriman `logistics/LogisticsView` | logistics_deliveries | W | status, tanggal dibuat, cari | CSV koma lama dihapus (EXP-03) |
| Riwayat pengiriman `logistics/HistoryPanel` | logistics_deliveries | W | status akhir, moda, tanggal terkirim, cari | idem; basis tanggal = terkirim (layar: selesai/terkirim/diubah) |
| Retur jual `sales/SalesReturns` (pager) | sales_returns | A | status, tipe, cari | lini → `unsupported` |
| Retur beli `purchasing/PurchaseReturns` (pager) | purchase_returns | A | status, lini, cari | — |
| Retur antar-PT `finance/interco/IntercoReturnsPanel` | interco_returns | A | — | hanya bila `interco_finance.view` (`requires`) |
| Order makloon `purchasing/MakloonOrdersView` | makloon_orders | A | status, lini, cari | — |
| Eskalasi gudang `manager/EscalationManagement` | wms_tasks | W | status eskalasi | — |
| Tag aktif & belum ber-tag `rfid/RfidTagsView` | rfid_tags · inventory_rolls | A | gudang, cari; belum ber-tag = tanpa tag, sisa > 0, status fisik | — |
| Job cetak `rfid/RfidPrintVerifyPanel` | rfid_print_jobs | A | gudang | dataset baru |
| Insiden `rfid/RfidSecurityPanel` | rfid_incidents | lokasi | status, gudang | dataset baru |
| Lokasi tag `rfid/RfidLocationsView` | rfid_tags | A | gudang, cari | — |
| Riwayat opname RFID `rfid/CycleCountPanel` | rfid_cycle_counts | PT semua (RF-08) + lokasi | gudang | dataset baru |
| Perangkat `rfid/RfidDevicesView` | rfid_devices | lokasi | gudang | dataset baru |
| Riwayat lintasan `rfid/GatePassageHistory` | rfid_passages | lokasi | gerbang/gudang | dataset baru |
| **Dikecualikan beralasan** (guardrail `WMS_LIST_EXEMPT`) | | | | |
| Meja Cutting `samples/CuttingDesk` | — | | | 3 antrean turunan dari tugas yang sama → unduh di Cutting |
| Antrean potong `wms/PendingCutsPanel` | — | | | gabungan turunan, bukan satu koleksi |
| Armada `logistics/FleetPanel` | — | | | master kendaraan ganda menunggu K-B3b-05 |
| Aktivitas gate `rfid/RfidGateMonitorView` · Antrean periksa D2 `rfid/GateReviewQueue` · Lintasan U300 `rfid/U300PassageList` | — | | | **berkas PREP-H** (tidak disentuh); antrean D2 butuh keputusan cakupan (hak lihat per dokumen sumber) |

Aplikasi HP (daftar tugas/belum tag) **tidak** diberi Unduh — keputusan implementer §6 (K-I3).

## 4. Kontras (dihitung `verify_ui_contrast.py --table`, rumus WCAG, rasio tidak dibulatkan)
Kelas baku sebelum (`main a8275bf`) → sesudah: `.primary-button` 4,02 → **6,43** · `.primary-button:hover` 5,38 → **8,13** ·
`.danger-button` 3,55 → **6,57** · `.danger-button:hover` 4,30 → **8,80** · `.btn-primary` 4,02 → **6,43** · `.btn-danger`
3,55 → **6,57** · `.nav-button.active` 4,02 → **6,43** · `.field::placeholder` 2,77 → **5,28** · `.text-muted` 3,26 → **5,28** ·
`.field` (batas) 1,44 → **3,44** (syarat 3:1) · semua 23 pasangan token `--kn-*` lolos (tabel KN_37 §2c) · 23 lencana
`.status-*` (latar rgba dikomposit di atas putih) 4,74–9,55:1 lolos. **Total 58/58 lolos; di `main` 8 kelas baku gagal.**

## 5. Sensus sebelum / sesudah

Skrip: `verify_ui_standard.py --census --ref a8275bf` vs pohon kerja (metrik per berkas, komentar dibuang, termasuk CSS
untuk huruf) dan `scripts/audit/b1_style_census.py` (metrik B1, JS/JSX saja).

| Metrik | Sebelum (`main`) | Sesudah | Catatan |
|---|---:|---:|---|
| Huruf < 12 px — seluruh `src` (JS + CSS) | 6.987 | 6.937 | ratchet; kelas baku CSS **101 → 65** (`components.css` 28 → 0, `purchasing.css` 4 → 0, `mobile.css` 4 → 0; sisa `catalog`/`tanya`/`fase0`/`layout`/`config` = luar cakupan) |
| … HP gudang (`features/mobile`) | 15 | 8 | 4 berkas HP gudang + menu akun: 7 → **0** (sisa di aplikasi HP Ops/Persetujuan/peran) |
| Huruf < 14 px di HP (`text-xs`, 12–13 px) | 53 | 15 | HP gudang: 38 → **0** |
| Target sentuh HP tanpa tanda ≥ 48 px | 47 | 13 | HP gudang: 35 → **1** (pemilih berkelas dinamis di menu akun — kini `kn-chip-touch`, diukur statik konservatif) |
| Literal hex JS/JSX | 16.906 | 16.810 | HP: 96 → 26 (HP gudang 70 → 0); hex **berbeda** 703 → 703 (dibekukan) |
| `<button>` bergaya Tailwind sendiri | 795 | 784 | HP gudang 7 → 2 |
| Tombol baku dipaksa `!py/!h/!text` | 577 | 577 | dibekukan (ratchet), tidak dirombak |
| `PaginationBar` tanpa Excel | 18 | 12 | sisa: 10 daftar non-gudang (PO, pelanggan, GL, …) + 2 antrean printer |
| Daftar WMS-RFID (matriks B3b) ber-Unduh | **0 / 37** | **31 / 37** | + 6 dikecualikan beralasan |
| Ekspor XLSX di daftar WMS-RFID (B3b B.6) | 0 | 31 layar · 36 tombol | kontrak Unduh↔registry 36 tombol, 0 masalah |
| B1 census: huruf arbitrer (JS) / < 12 px | 8.989 / 6.819 | 8.952 / 6.805 | area gudang < 12: 1.270 → 1.263 |
| B1 census: tombol baku / Tailwind sendiri | 1.774 / 802 | 1.777 / 791 | |

Catatan jujur: angka seluruh aplikasi turun sedikit karena K-B4-02 memutuskan **bertahap** (komponen & kelas baku + HP
gudang + layar baru), bukan bongkar massal; dampak visual terbesar ada di **kelas baku** yang dipakai ribuan elemen
(pil status, kepala tabel, label isian, kartu metrik, pager, tombol utama/bahaya, batas isian) — tidak terlihat di
hitungan per-berkas JS. Target 360/390 px & persentase teks < 12 px per layar perlu diukur di peramban (§9).

## 6. Perubahan perilaku untuk pengguna
1. **Warna:** tombol utama/aktif menu sedikit lebih gelap (`#0058CC`), tombol bahaya merah tua (`#B42318`), batas isian
   lebih tegas (abu `#8A8A8E`), placeholder & teks pucat lebih gelap.
2. **Huruf:** pil status, kepala kolom tabel, label isian, kicker, kartu metrik, pager kini 12 px (dulu 10–11,5 px) —
   tabel padat sedikit lebih lebar. Radius bawaan shadcn 16 → 14 px.
3. **Unduh:** 31 daftar gudang/RFID punya tombol **"Unduh ▾" → Excel / CSV** yang mengikuti saringan, kotak cari, PT dan
   bilah "Lokasi". Unduhan > 50.000 baris diproses di latar → notifikasi "Unduhan siap" → Pusat Export › Pekerjaan.
   Saringan yang belum bisa diikuti berkas server membuat butir Excel **nonaktif dengan alasan**.
4. **Pengiriman:** tombol "CSV" (koma, halaman ini saja) diganti "Unduh ▾" — berkas kini semua hasil saringan, `;`.
5. **Peran Petugas Gudang** kini bisa mengunduh daftar gudang dan membuka **Pusat Export** (hanya dataset gudang).
6. **HP gudang:** tombol & isian lebih besar (48–56 px), teks kartu tugas 16/14 px, chip PT, ikon app bar & tab bawah
   lebih mudah disentuh; tata letak & alur tidak berubah.
7. PaginationBar memakai gaya baku (12 px, tombol ≥ 28 px); testid lama dipertahankan.

## 7. Keputusan implementer (di luar keputusan koordinator) + alasan
- **K-I1 — Dokumen baru `KN_37`** + catatan di KN_08 (alasan di kepala laporan).
- **K-I2 — "Langsung" = endpoint sinkron `/export-center/quick`** (berkas di respons) dan job Pusat Export yang sudah ada
  untuk > 50.000 (202 + notifikasi). Alasan: satu klik tanpa polling untuk kasus umum; mesin, izin, snapshot & lembar
  Ringkasan sama dengan Pusat Export (bukan mesin kedua). Berkas langsung tidak dicatat sebagai job (jejak = audit
  `export.quick` berisi dataset, kolom, baris, PT, lokasi, saringan).
- **K-I3 — Unduh tidak dipasang di aplikasi HP** (daftar tugas/belum tag): unduh berkas di HP lapangan tidak bernilai
  operasional; data yang sama diunduh dari layar desktop.
- **K-I4 — Ekspor server selalu "semua hasil saringan"**; pilihan "Halaman ini / Semua" tetap ada pada butir CSV untuk
  daftar yang sudah punya CSV kolom-layar (INV-UI-07). Alasan: model server, halaman = artefak tampilan.
- **K-I5 — Jalur cari ditetapkan registry dataset (= endpoint daftar), bukan klien**; saringan yang tidak bisa dinyatakan
  → `unsupported` (butir nonaktif + alasan), bukan mengunduh data lebih luas dari layar. Daftar layar yang mencari di
  peramban (Transfer, Tugas keluar, Lokasi tag, …) kini mencari di server atas kolom yang sama — hasil bisa sedikit lebih
  luas/lebih sempit pada pencarian bebas (dicatat).
- **K-I6 — Peran `warehouse` = daftar putih 21 dataset**, bukan "kelompok Gudang" — kelompok Gudang memuat Riwayat Nilai Roll
  (nilai HPP tak bertanda `cost`).
- **K-I7 — CSV dialek Indonesia hanya untuk tombol daftar**; CSV Pusat Export klasik tetap koma (perilaku lama, sisa).
- **K-I8 — `rfid_v2_reviews` (antrean periksa D2) tidak dipetakan**: hak lihat per kasus diperiksa per dokumen sumber
  (`_case_access`) — tidak bisa dinyatakan sebagai kueri tanpa keputusan cakupan; berkasnya juga milik PREP-H.
- **K-I9 — Label tab bawah HP 12 px** (setara M3 label) — pengecualian tertulis dari "pendukung ≥ 14 px".
- **K-I10 — Ikon app bar HP tampak 40 px, area sentuh 48 px** lewat `::after` (bilah tidak bertambah tinggi).

## 8. Hasil uji & perbandingan regresi

**Lingkungan:** stack sementara `kn-tmp-fix4-mongo` (salinan `kn_test_trial_2026-11-08` → `test_database`, dipulihkan ulang
sebelum tiap putaran) + `kn-tmp-fix4-be` (kode dasar di `/app_base` = `main a8275bf`, kode FIX-4 di `/app`) + node
`kn-tmp-fix4-fe` (volume `kn-dev_fe_node_modules` **hanya-baca**). Stack bersama `kn-uji-*`/`kn-dev-*` tidak disentuh.

| Putaran | Hasil |
|---|---|
| Backend relevan (16 berkas: Pusat Export L11/AUD-EXP, akses fe03, peran, retur, printer, UAT24/26, FIX-1 cakupan, transfer guard + `test_fix4_ekspor`) — **dasar `main`** | **147 lulus · 24 gagal** |
| idem — **FIX-4** | **162 lulus · 9 gagal** (lihat putaran akhir di bawah) |
| Gagal **hanya** di FIX-4 | **0** |
| Gagal di keduanya (utang lama, identik) | `test_l11_export_center::test_ln113_t01_sales_cannot_inject_hidden_fields`, `test_l11_finance_staff_templates::test_coverage_no_unmapped`, `test_lanjutan_sched_returns_interco::test_ln100_t02_shared_woven_node`, `test_return_per_roll::test_supplier_izin_decide_rolls_dan_validasi`, `test_role_editor_iter38` ×2, `test_transfer_status_guard` ×3 |
| Sembuh di FIX-4 | 14 uji FIX-4 (merah di dasar: endpoint `/quick` belum ada) + `test_fe03_access_catalog::test_katalog_selaras_menu_frontend` (merah di dasar karena salinan frontend dasar di kontainer tidak lengkap — artefak lingkungan, bukan klaim perbaikan) |
| `tests/test_fix4_ekspor.py` — dasar | **14/14 GAGAL** (bukti merah) |
| `tests/test_fix4_ekspor.py` — FIX-4 (versi akhir 15 uji) | **15/15 lulus** |
| Jest `fix4StandarUi.test.js` — dasar | **suite GAGAL** (`utils/exportSpec` belum ada) |
| Jest `fix4StandarUi.test.js` — FIX-4 | **14/14 lulus** |
| Jest PENUH — dasar | 82 suite · **581/582** (gagal: `serverAccessReach` manajer → logistics, dari FIX-1/UI-47) |
| Jest PENUH — FIX-4 | 83 suite · 594/596 pada putaran penuh; 2 gagal = `serverAccessReach` manajer (= dasar) + `roleReach` warehouse (jangkauan baru `export-center` belum tercatat) → `ROLE_REACH_ADDITIONS.warehouse` diperbarui, dua suite diulang: 44/45 (hanya manajer = dasar) ⇒ **595/596** |
| Jest terarah sesudah perbaikan Esc (fix4, prepF printer, fix1, mobileShell, fix3a, fix3b) | 6 suite · 55/55 |
| ESLint berkas FE yang diubah (42) | **0 error**, 38 peringatan — semuanya "Unused eslint-disable directive" yang sudah ada |
| `verify_ui_contrast.py` pada CSS `main` (`KN_UI_SRC`) | **MERAH** (8 kelas baku + token belum ada) → FIX-4 **58/58 hijau** |

**Putaran akhir FIX-4** (sesudah semua perubahan): lihat §8a.

### 8a. Putaran akhir
Sesudah perubahan terakhir (kolom `created_at` retur antar-PT, uji ke-15, Esc menu Unduh), DB dipulihkan ulang, kode FIX-4:
**163 lulus · 9 gagal** (172 node; +1 uji FIX-4) — daftar 9 gagal **identik** dengan putaran FIX-4 sebelumnya dan semuanya
juga gagal di dasar; **0 gagal baru**.

## 9. Guardrail

Baru: **`scripts/guardrails/verify_ui_standard.py`** (+ `--self-test` 20 kasus, `--census [--ref]`, `--update`) dan
**`scripts/guardrails/verify_ui_contrast.py`** (+ `--self-test`, `--table`). Baseline (angka sekarang = batas atas):

| Baseline (`scripts/guardrails/baselines/`) | Total | Berkas |
|---|---:|---:|
| `ui_font_lt12.json` (G-UI-01) | 6.937 | 765 |
| `ui_hp_font_lt14.json` (G-UI-01 HP) | 15 | 3 |
| `ui_hex.json` (G-UI-02) | 16.810 | 825 |
| `ui_hex_set.json` (hex berbeda, G-UI-02) | 703 nilai | — |
| `ui_btn_custom.json` (G-UI-04) | 784 | 349 |
| `ui_btn_force.json` (K-B1-06) | 577 | 164 |
| `ui_hp_touch.json` (G-UI-05) | 13 | 4 |
| `ui_list_no_excel.json` (G-UI-07) | 12 | 11 |
| Keras: `WMS_LISTS` (31 + 6 beralasan), kontrak Unduh↔registry (36 tombol), kontras 58 pasangan | — | — |

Guardrail lama, `main` vs FIX-4 (host, `PYTHONUTF8=1`, `verify_state_machine` tidak dijalankan): kode keluar identik di
semua penjaga lama; hitungan berubah hanya karena berkas baru ikut dipindai (`auth_coverage` 28 = 28 pelanggaran, cek
1.725 → 1.726 karena endpoint baru tercakup; `qty_dual` 28 = 28; `error_notice` 275 → 276 cek; `list_export` 19 → 21 cek;
`role_label`/`uom_vocab` 1.185 → 1.188 berkas). `escape_layers` sempat merah (menu Unduh memasang pendengar Esc sendiri) →
diperbaiki memakai `useEscapeClose` (hijau). `no_secrets` 8 temuan = berkas `test_reports/` yang sama (tidak ada di arsip
dasar yang saya pindai; FIX-3b mencatat 8 = 8). Penjaga runtime (`concurrency`, `cross_entity`, …) tidak bisa jalan di host
(modul DB tidak terpasang) — sama di kedua sisi.

## 10. Berkas berisiko bentrok
- **FIX-5 (performa WMS)** mengubah daftar WMS-RFID (halaman server): saya **hanya menambah** satu `import ExportMenu` +
  satu elemen `<ExportMenu …>`/`exportSpec` per layar di 31 berkas (`features/wms/*`, `features/rfid/*` non-PREP-H,
  `features/inventory/*`, `features/logistics/*`, `InspectionsView`, `SalesReturns`, `PurchaseReturns`, `MakloonOrdersView`,
  `IntercoReturnsPanel`, `EscalationManagement`, `SampleOrdersView`). Bila FIX-5 menambah parameter halaman/saringan,
  saringan yang sama perlu diteruskan ke `filters`/`search` tombol (kontrak dijaga G-UI-07b).
- **PREP-H** — `RfidGateMonitorView`, `GateLiveVerdict`, `GateReviewQueue`, `U300Operations`, `U300PassageList`
  **tidak disentuh** (dikecualikan di guardrail dengan alasan).
- Gaya global: `styles/components.css`, `purchasing.css`, `mobile.css`, `tokens.css`, `index.css` (`--radius`),
  `tailwind.config.js`, `App.css` (+ `standard.css`). Paket lain yang menyunting kelas tombol/isian/pil akan bentrok tekstual.
- `MobileWarehouseApp.jsx`, `MobileTaskActions.jsx`, `MobileRegistration.jsx` (kelas saja; FIX-3a/3b baru menyentuhnya).
- `permissions_config.py`, `entity_write_guard.py` (1 baris allowlist), `navStructure.js` (peran Pusat Export),
  fixture `access_builtin_fixture.json`, `roleReach.test.js`.
- `services/export_engine.py`, `export_registry*.py`, `routers/export_center.py`.

## 11. Sisa (tidak dikerjakan / butuh keputusan)
1. **Verifikasi visual 360 & 390 px dan desktop** (K-B4-04, G-UI-09) — koordinator; ukur juga lebar CSS C72.
2. **Unduh di berkas PREP-H** (aktivitas gate `rfid_reads` — dataset siap; lintasan V2) sesudah PREP-H digabung;
   **antrean periksa D2** butuh keputusan cakupan dataset (hak lihat per dokumen sumber).
3. Armada (master kendaraan ganda, K-B3b-05); antrean printer (`PrinterQueuePanel`, 2 pager — sumber `/rfid/printers/queue`
   turunan, belum dataset); 10 daftar berhalaman non-gudang (PO, pelanggan, GL, pesanan, tagihan, pemasok, akun,
   persetujuan, desain, papan PO) masih CSV saja — ratchet mencegah bertambah.
4. Tahap 2 standar: `StatusBadge`/`TaskTypeBadge`, `EmptyState`, peleburan `KNPager`/`PagedRows`/`ListControls`,
   migrasi 12 px di layar gudang saat disentuh (1.257 pemakaian < 12 px di area gudang dibekukan), `!py-*` (577) dibekukan.
5. Tampilan tersimpan (K-B4-12) — di luar paket.
6. CSV Pusat Export klasik masih koma (pakai dialek `id` bila disetujui); `roll_cost_history` (nilai roll) tidak bertanda
   `cost` → Admin Gudang (sudah punya `data_export` sebelum paket ini) bisa mengunduh nilai roll — **temuan untuk reviewer**
   (bukan diubah di sini karena mengubah akses peran lain).
7. Pencarian bebas daftar yang dulu mencari di peramban kini dicari server pada kolom yang sama (K-I5) — perlu dicek
   pemilik bila hasil terasa berbeda.
8. `Riwayat pengiriman`: basis tanggal berkas = tanggal terkirim; layar memakai selesai/terkirim/diubah (selisih kecil
   untuk status "selesai").

---

## Ringkasan untuk koordinator
- **Keputusan diterapkan:** K-B4-01 (KN_37 wajib + ratchet; KN_08 ditandai digantikan sebagian), K-B4-02 bertahap (kelas
  baku + HP gudang), K-B4-03 (warna AA lewat token `--kn-*`), K-B4-04 (ukuran HP berbasis lebar penuh; ukur visual oleh
  Anda), K-B4-06, **K-B4-07 + K-B3b-04** (tombol baku `ExportMenu` → `POST /export-center/quick`: XLSX bawaan + CSV,
  ≤ 50.000 langsung / lebih → job + notifikasi, ikut saringan + cari + PT + lokasi; peran gudang = daftar putih 21
  dataset), K-B4-11 (`*` tetap), K-B1-06 (`btn-sm`/`btn-touch`/`btn-primary-cta`, larangan `!py-*` lewat ratchet), K-B1-09.
  K-B4-12 di luar paket.
- **Sensus sebelum → sesudah:** daftar WMS-RFID ber-Unduh **0/37 → 31/37** (+6 beralasan); kontras kelas baku **8 gagal →
  58/58 lolos** (tombol utama 4,02 → 6,43:1, bahaya 3,55 → 6,57:1, batas isian 1,44 → 3,44:1, placeholder 2,77 → 5,28:1);
  CSS kelas baku huruf < 12 px **101 → 65** (`components/purchasing/mobile.css` → 0); HP gudang: huruf < 14 px **38 → 0**,
  target sentuh tanpa tanda ≥ 48 px **35 → 1**, hex **70 → 0**; hex berbeda aplikasi dibekukan 703; pager tanpa Excel 18 → 12.
- **Layar diubah:** 31 layar daftar (tabel §3; hanya tambah tombol/kelas baku), `PaginationBar` (gaya baku + `exportSpec`),
  aplikasi HP gudang (Masuk/Keluar/Sample/Pindai/Belum Tag/Daftar Awal/Lainnya, banner offline), Pengiriman (CSV koma
  dihapus), kelas baku global (tombol, isian, pil, tabel, label).
- **Guardrail baru + baseline:** `verify_ui_standard.py` (ratchet `font_lt12` 6.937 · `hp_font_lt14` 15 · `hex` 16.810 +
  himpunan 703 · `btn_custom` 784 · `btn_force` 577 · `hp_touch` 13 · `list_no_excel` 12; keras: `WMS_LISTS`, kontrak
  Unduh↔registry 36 tombol) dan `verify_ui_contrast.py` (keras, 58 pasangan).
- **Uji:** backend relevan dasar 147/171 vs FIX-4 163/172 (putaran akhir) — **0 gagal baru** (9 gagal identik di dasar);
  `test_fix4_ekspor` dasar 14/14 merah → 15/15 hijau; Jest penuh 595/596 (= dasar: `serverAccessReach` manajer, FIX-1);
  Jest FIX-4 14/14 (dasar: suite merah); ESLint 0 error; guardrail lama identik (escape_layers diperbaiki).
- **Berkas berisiko bentrok:** 31 layar daftar (bentrok tekstual kecil dengan FIX-5), CSS global/tokens/tailwind,
  HP gudang (`MobileWarehouseApp`/`MobileTaskActions`/`MobileRegistration`), mesin & registry Pusat Export, izin/nav peran
  gudang. Berkas PREP-H tidak disentuh.
- **Sisa:** verifikasi visual 360/390 px; Unduh di berkas PREP-H & antrean D2 (keputusan cakupan); armada, antrean printer,
  10 daftar non-gudang; tahap 2 (StatusBadge, EmptyState, peleburan pager/cari, migrasi 12 px); CSV Pusat Export klasik;
  temuan `roll_cost_history` tanpa tanda `cost` (Admin Gudang).
