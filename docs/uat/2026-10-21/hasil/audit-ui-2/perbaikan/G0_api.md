# G0 — API bersama baru (audit UI tahap 2)

Status: **siap dipakai** (aditif; pemanggil lama tidak berubah kecuali yang dicatat di §5). Uji: `frontend/src/utils/__tests__/g0SharedApi.test.js`.
Semua impor relatif terhadap `frontend/src` (alias `@/` juga bisa).

## 1. Formatter — `utils/formatters.js` (G0-14 · P-06)

| Fungsi | Tanda tangan | Contoh |
|---|---|---|
| `formatPct` | `formatPct(v, digits = 1, { trim = false } = {})` — `v` SUDAH dalam persen (bukan rasio 0–1) | `formatPct(32.4)` → `"32,4%"` · `formatPct(0.75, 2)` → `"0,75%"` · `formatPct(12)` → `"12,0%"` · `formatPct(12, 1, { trim: true })` → `"12%"` · `null`/tak sah → `"—"` |
| `formatPeriod` | `formatPeriod(v, { short = false } = {})` — terima `"YYYY-MM"` atau `"YYYY-MM-DD…"` | `formatPeriod("2026-10")` → `"Oktober 2026"` · `{ short: true }` → `"Okt 2026"` · kosong → `"—"` · format lain dikembalikan apa adanya |
| `formatCompactIDR` | `formatCompactIDR(v, { rp = false, digits = 1 } = {})` — satuan rb · jt · M · T, tanpa ".0" | `150000000` → `"150 jt"` · `1400000000` → `"1,4 M"` · `999960000` → `"1 M"` · `12500` → `"12,5 rb"` · `950` → `"950"` · `-2500000` → `"-2,5 jt"` · `{ rp: true }` → `"Rp 1,4 M"` · `0` → `"0"` · `null` → `"—"` |
| `formatDecimal` | `formatDecimal(v, max = 2, min = 0)` — pengganti `toFixed` | `1234.5` → `"1.234,5"` · `(0.756, 2)` → `"0,76"` · `(3, 2, 2)` → `"3,00"` · `null` → `"—"` |

Yang SUDAH ada (tidak berubah): `formatDate`, `formatDateTime` (WIB), `formatQty`, `formatCurrency`, `todayWib`, `wibDate`, `formatStamp`.
Catatan: `compactIDR`/`fmtPct` lokal di `features/finance/financeShared.jsx` & `BiFinanceView.jsx` milik G1 — ganti ke fungsi di atas bila mau.

## 2. Label status — `utils/docStatus.js` (G0-15 · P-02)

- `docStatusLabel(status, extra?)` — **tanda tangan diperluas (aditif)**:
  - Pencarian kini kebal huruf besar/spasi/strip: `"CANCELLED"` → `"Dibatalkan"`, `"Waiting Approval"` → `"Menunggu persetujuan"`, `"qc-pending"` → `"Menunggu QC"`.
  - `extra` (opsional) = peta lokal layar yang didahulukan: `docStatusLabel(r.status, STATUS_MAP)` → label lokal bila ada, lalu peta bersama, lalu rapikan generik (`"some_code"` → `"Some code"`, perilaku lama).
- Kode baru di `DOC_STATUS_LABEL`: waiting_goods "Menunggu barang", receiving "Sedang diterima", qc_check "Cek QC", qc_pending "Menunggu QC", qc_rejected "Ditolak QC", put_away/putaway "Disimpan ke rak", escalated "Dieskalasi", created "Dibuat", confirmed "Dikonfirmasi", waiting_stock "Menunggu stok", siap_disahkan "Siap disahkan", posted "Terposting", staging "Disiapkan", picked "Diambil", packed "Dikemas", committed "Terikat", expired "Kedaluwarsa", partial "Sebagian", submitted "Diajukan", verified "Diverifikasi", dispatched "Dikirim", open "Terbuka", active "Aktif", inactive "Nonaktif", paid "Lunas", unpaid "Belum lunas", partially_paid "Sebagian dibayar", overdue "Lewat jatuh tempo", void/voided "Dianulir", failed "Gagal", released "Dilepas", on_hold "Ditahan", processing "Diproses", ready "Siap", archived "Diarsipkan", reversed "Dibalik", disputed "Disengketakan", scheduled "Dijadwalkan", waiting "Menunggu", new "Baru". (Kode lama tetap.)
- Baru: `hasDocStatusLabel(status)` → `true` bila ada label Indonesia di peta bersama (untuk memutuskan perlu peta lokal atau tidak).

## 3. Pembersih kode internal — `utils/cleanText.js` (G0-15 · P-02)

`stripInternalCodes(text)` (tanda tangan sama) kini juga membuang keluarga kode keputusan/invarian/spesifikasi:
`KLX-03`, `KLR-05` (KL?-nn), `P7-K1`, `KN-D16`, `INV-IC-02` (INV-XXX-nn, termasuk `INV-IC-02/INV-IC-03`), `KN_17 §5.2` (KN_nn §…),
`G-6` (hanya di dalam kurung `(G-6)` atau sebelum `:`/`·`/`—`).
- Kurung yang isinya hanya kode + kata pengantar ("keputusan pemilik", "lihat", "invarian") dibuang seluruhnya; kurung yang punya isi lain hanya dibuang kodenya.
- Contoh: `"diputus sistem (KLR-05)"` → `"diputus sistem"` · `"Menunggu KLX-03"` → `"Menunggu"` · `"Dibayar per PT pembayar, KLX-03."` → `"Dibayar per PT pembayar."` · `"(keputusan pemilik P7-K1)"` → dibuang · `"Auto G-6: Eliminasi"` → `"Auto Eliminasi"` (kata "Auto"/"AUTO" & "Balanced" tetap — terjemahkan di layar) · `"(berlaku 30 hari, KLR-05)"` → `"(berlaku 30 hari)"`.
- TIDAK menyentuh kode warna/produk (`KN-BLU-01`) maupun nomor dokumen (`KSC/INV-00012`).

## 4. Pesan galat izin — `utils/apiError.js` (G0-03 · P-07)

- `apiErrorText(e)` (tanda tangan sama): teks server `"Permission ditolak: <modul>.<aksi>[ — keterangan | (keterangan)]"` kini diterjemahkan:
  - `approval.view` → `"Anda tidak punya akses ke Persetujuan."`
  - `sales_return.reject` → `"Anda tidak punya izin “Tolak” di Retur Penjualan."`
  - `wms.untagged_override — roll tanpa tag …` → `"Anda tidak punya izin “Izinkan Roll Tanpa Tag” di WMS / Gudang. Roll tanpa tag …"`
  - `butuh salah satu dari a.view / b.view / c.view` → `"Anda tidak punya akses ke A, B, atau C."`
  - Berlaku juga bila `e` berupa string atau `Error.message` berisi teks itu. Kode izin hanya ke `console.debug` saat dev.
  - 403 dengan kalimat biasa (mis. `"Akses gudang tujuan ditolak."`) **tetap apa adanya**; 403 tanpa isi → `"Anda tidak punya izin untuk tindakan ini."` (lama).
- Baru: `permissionDeniedText(detail)` → kalimat Indonesia, atau `""` bila `detail` bukan penolakan izin.
- Baru: `isForbiddenError(e)` → `true` bila status 403 atau detail "Permission ditolak: …". Pakai untuk membedakan **"tidak punya akses"** dari **daftar kosong** (P-07):
  ```js
  import apiErrorText, { isForbiddenError } from "@/utils/apiError";
  try { … } catch (e) { if (isForbiddenError(e)) setDenied(apiErrorText(e)); else setError(apiErrorText(e)); }
  ```
- Label modul/aksi diambil dari `config/auditLabels` (`MODULE_LABEL`/`ACTION_LABEL`, kini mencakup semua modul & aksi `require_permission` di backend).

## 5. Label aksi audit — `config/auditLabels.js` (G0-16)

- `auditActionLabel(key)` — **perilaku fallback berubah**: tidak lagi humanize Inggris. Urutan: peta tetap → pola `<sumber daya>_<kata kerja>` (mis. `reservation_expired` → "Reservasi kedaluwarsa", `bank_line_ignored` → "Baris mutasi bank diabaikan") → `"Aksi lain"`. `login` kini "Masuk" (dulu "Masuk (login)").
- Baru: `auditActionInfo(key)` → `{ label, known, code }`; `isKnownAuditAction(key)`. Untuk G5-01: tampilkan `label`, taruh `code` di `title` (tooltip) hanya bila perlu/`!known`.
- `MODULE_LABEL` + `ACTION_LABEL` diperluas (data_export, od_pricing, od_fulfillment, md_quality, qc, sample_order, special_order, …; aksi set_price, decide_rolls, untagged_override, override, release_hold, …). `moduleLabel`/`actionLabel` tidak berubah perilaku.

## 6. Perubahan uji yang ikut disesuaikan

- `features/__tests__/fe07ReturnErrors.test.js` (modal tolak retur): harapan `toContain("sales_return.reject")` → `toContain("Retur Penjualan")` + `not.toContain("sales_return.reject")`. Hanya baris itu.

## 7. Perubahan perilaku komponen bersama (SUDAH berlaku — jangan ditambal per layar)

- **KNSelect** (G0-04/05/06) — kontrak prop lama tetap; prop opsional baru `emptyText` (bawaan "Belum ada pilihan") & `unknownLabel(value)`.
  - Opsi bernilai `""` ("Pilih…", "Semua …"): saat nilai kosong TIDAK tampil di daftar (pemicu tetap menampilkan labelnya); saat nilai terisi tampil abu tanpa ✓ (untuk mengosongkan). testid `<id>-option-empty` hanya ada di DOM saat nilai terisi.
  - Sorotan keyboard abu netral (ui/command `data-selected`, ui/select `focus`) — berlaku juga untuk CommandPalette. Terpilih = ✓ + tebal biru. Combobox dibuka tersorot & tergulir di nilai aktif.
  - Menu selebar isi: min selebar pemicu, maks `min(26rem, 100vw-1.5rem)`.
  - Nilai non-kosong yang tak ada di `options` (dan `options` tidak kosong) → pemicu menampilkan "`<nilai>` (tidak ada di daftar)" oranye (`data-kn-unknown="true"`), dev `console.warn`. Saat `options` masih `[]` (memuat) perilaku lama.
- **DetailModal** (G0-07): `framed` kini punya tombol × bulat di pojok kanan atas kartu (di luar area gulir), testid `<testId>-close-x`; `showClose={false}` bila panel sudah punya × sendiri. Isi kartu kini dibungkus satu `div` di dalam elemen `role=dialog`.
- **LocationFields** (G0-08): prop baru `labelStyle` (`"sentence"` bawaan · `"caps"` gaya lama) dan `showErrors` (berikan `true` setelah submit gagal agar galat kelengkapan tampil walau blok alamat belum disentuh). Satu isian Kode pos (ketik 5 angka ⇄ "Pilih dari daftar"); testid `-postal-quick` (mode ketik) dan `-postal` (mode daftar) tetap, `-postal-mode` baru; `-error` kini di bawah isian yang kurang. Akar blok `col-span-full` (aman di grid 1 atau 2 kolom).
- **adminDelete** (G0-11): `adminDelete(resource, id, name?)` — kini `askConfirm` (danger, "Nonaktifkan") lebih dulu; pesan "Pelanggan <nama> dinonaktifkan." Nama dicari dari `data[resource]` bila `name` tidak dikirim.
- **WaitingQueueBoard** (G0-01): tombol aksi `.primary-button` (biru) di semua papan; baris membungkus < 640 px.
- **ProductGallery / MediaLightbox** (G0-18): gambar gagal → teks "Gambar tidak dapat dimuat", tanpa tombol perbesar/lightbox (testid `<id>-broken`, `media-lightbox-error`).
- **PaginationBar** (G0-19): `pageSize` aktif selalu ikut di pilihan "Per halaman".
- **ConfirmModal / askReason** (G0-20): hint `reasonMinLength` abu "Minimal N huruf." sebelum mengetik; kalimat menggurui dihapus.
- **KNDatePicker** (G0-13): popover dijaga di dalam layar, tinggi maks `min(22rem,70dvh)`.
- **App/TopBar** (G0-09/G0-21): pesan sistem awal kosong; bilah HP hanya tampil bila ada pesan; CTA bilah = "Tutup". (G0-12) tombol kembali ke HP satu gaya `.m-back-float`, tersembunyi saat pop-up terbuka.
- **navMeta/hubTabs** (G0-17): "Impor Dataset Klien", "Dasbor Keuangan", "Pajak (PPN & PPh)", tab "Persetujuan Pembelian", "Laporan R&D · SLA Ronde & Tahap Produk".
