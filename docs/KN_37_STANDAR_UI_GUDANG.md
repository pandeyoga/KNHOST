# KN_37 — Standar UI Gudang v1

| | |
|---|---|
| Status | **Berlaku** sejak 9 Nov 2026 (paket FIX-4, tahap 1). Keputusan pemilik lewat koordinator: K-B4-01 (wajib, ditegakkan ratchet), K-B4-02, K-B4-03, K-B4-04, K-B4-06, K-B4-07 + K-B3b-04, K-B4-11, K-B1-06, K-B1-09 |
| Menggantikan | bagian `KN_08_UI_UX_STANDARDS.md` yang bertentangan (warna primer, font & skala huruf, radius, shadcn "WAJIB", varian tombol, kontras, adaptasi HP/"camera-first") — lihat catatan di kepala KN_08 |
| Dasar | riset `docs/audit/2026-11-09-wms-rfid/B4-RISET-STANDAR-UI.md` (§3, sumber §4); temuan B1 UI-24/26/27/28/30, B1b UI-52/53, B3b EXP-01…05, FRM-17 |
| Berlaku untuk | layar gudang (`features/wms`, `features/rfid`, `features/inventory`, `features/inspections`), aplikasi HP (`features/mobile`), kios gate, **komponen & kelas baku**, dan **semua kode baru** di mana pun. Layar lama di luar itu mengikuti saat disentuh (ratchet: angka tidak boleh naik) |
| Tidak mengubah | istilah antarmuka (K-13, `KN_32`), definisi "Tersedia" (K-04), kebijakan gate (K-RFID-09/10), "form HP = form desktop" |

Aturan membaca: **WAJIB** = dijaga guardrail; **anjuran** = dinilai reviewer. Angka kontras dihitung skrip
(`scripts/guardrails/verify_ui_contrast.py --table`), bukan dikira.

---

## 1. Prinsip
1. **Cakupan dulu** — setiap daftar/angka gudang mengikuti lokasi kerja + PT pengguna; "semua" dipilih sadar lewat bilah
   "Lokasi: … ▾" (`LocationScopeBar`, FIX-1).
2. **Satu komponen per pola** — tidak ada varian kedua tombol, pager, kotak cari, tombol unduh.
3. **Status = ikon + teks + warna** — tidak pernah warna saja (WCAG 1.4.1).
4. **Pindai dulu, ketik terakhir** — pemindai fisik (C72) utama, kamera cadangan.
5. **Terukur & ditegakkan** — setiap aturan punya angka dan penjaga (§9).

## 2. Token (`frontend/src/styles/tokens.css`, Tailwind `theme.extend`)

### 2a. Huruf — WAJIB (G-UI-01)
| Token CSS | Kelas Tailwind | px / line-height | Peran |
|---|---|---|---|
| `--fs-12` | `text-fs-12` | 12 / 16 | label isian, kepala kolom, chip, lencana, metadata |
| `--fs-13` | `text-fs-13` | 13 / 18 | isi tabel & isian desktop |
| `--fs-14` | `text-fs-14` | 14 / 20 | teks badan; **HP: teks pendukung** (`kn-hp-support`) |
| `--fs-16` | `text-fs-16` | 16 / 24 | **HP: info keputusan** (nomor roll/dokumen, lokasi, jumlah, status — `kn-hp-info`, `kn-hp-title`), isian HP |
| `--fs-20` | `text-fs-20` | 20 / 28 | judul halaman desktop, judul hasil pindai HP |
| `--fs-24` | `text-fs-24` | 24 / 32 | angka KPI, progres HP |
| `--fs-kiosk-40/64` | `text-fs-kiosk-40/64` | 40, 64 | kios gate |

* **Minimum 12 px di mana pun.** HP: keputusan ≥ 16 px, pendukung ≥ 14 px; 12 px hanya metadata dan label tab bawah
  (setara M3 *label*). `text-[Npx]` baru dilarang — pakai kelas di atas.
* Huruf: **Manrope** (badan) & **Outfit** (angka/judul) — yang dipakai kode (`index.css`), bukan Inter.
* Angka `tabular-nums`, rata kanan di tabel, format Indonesia (`formatQty`).
* Pemetaan migrasi: 8,5–11,5 → 12 · 12–13,5 → 13 · 14–15 → 14 · 16–18 → 16 · 19–22 → 20 · 24–26 → 24.

### 2b. Spasi & radius
Spasi `2 · 4 · 8 · 12 · 16 · 24 · 32 · 48` (`--sp-0-5 … --sp-12`). Radius `8` (lencana/chip persegi) · `10` (tombol,
isian: `--r-md`) · `14` (kartu, modal: `--r-lg`, `--radius` shadcn kini 14 px) · `18` (sheet HP) · `999` (pil).

### 2c. Warna semantik — WAJIB (G-UI-02 ratchet, G-UI-03 keras)
| Peran | Token | Nilai | Rasio (lawan) |
|---|---|---|---|
| Teks utama | `--kn-text` | `#1C1C1E` | 17,01:1 (putih) |
| Teks sekunder = **minimum warna teks** | `--kn-text-2` | `#6B6B73` | 5,28:1 putih · 4,85:1 `#F4F5F8` · 4,73:1 netral |
| Netral / draf | `--kn-neutral` / `--kn-neutral-soft` | `#3C3C43` / `#F2F2F5` | 9,79:1 |
| **Aksi** (isian tombol utama, tautan, fokus) | `--kn-action` · `--kn-action-hover` · `--kn-action-soft` | `#0058CC` · `#004AAD` · `#E6F0FF` | putih di aksi 6,43:1 · hover 8,13:1 · aksi di soft 5,59:1 |
| Berhasil | `--kn-success-text` · `-solid` · `-soft` | `#126E2C` · `#1B7F4B` · `#E6F6EC` | 6,38 · putih di solid 5,02 · 5,70:1 |
| Perhatian | `--kn-warning-text` · `-soft` · `-kiosk` | `#8C4A00` · `#FFF4E5` · `#FFD60A` | 6,79 · 6,24 · teks gelap di kuning kios 12,05:1 |
| **Bahaya** (tombol hapus/tolak) | `--kn-danger` · `-hover` · `-text` · `-soft` | `#B42318` · `#93190F` · `#A8221A` · `#FDECEC` | putih 6,57 · 8,80 · 7,22 · 6,32:1 |
| Khusus (lot, sampel — kategori) | `--kn-special-text` · `-soft` | `#6B219A` · `#F3E8FA` | 9,09 · 7,68:1 |
| Batas isian | `--kn-field-border` | `#8A8A8E` | 3,44:1 (non-teks, 1.4.11) |
| Pemisah dekoratif | `--kn-divider` | `#E5E5EA` | bukan penanda komponen |
| Fokus | `--kn-focus` | `#0058CC`, garis 2 px, offset 2 px | 6,43:1 |

* Diganti (gagal AA): isian tombol `#007AFF` (4,02:1) dan `#FF3B30` (3,55:1), hover bahaya `#E73229` (4,30:1), teks
  `#8E8E93` (3,26:1) / `#9A9BA3` (2,77:1), batas isian `#D6D7DC` (1,44:1). `#007AFF` tetap boleh untuk dekorasi tanpa teks.
* Kelas Tailwind: `text-kn-text-2`, `bg-kn-action`, `bg-kn-success-soft`, `border-kn-field-border`, `text-kn-danger-text` …
* Hex baru di JS/JSX dilarang (himpunan hex aplikasi dibekukan, §9). Warna kategori tidak memakai hijau/kuning/merah.

## 3. Ukuran & densitas — WAJIB
| | Desktop "ringkas" | HP "nyaman" (C72) |
|---|---|---|
| Tombol & isian | 36 px bawaan (`--control-h`), 32 px kecil (`btn-sm`) | **≥ 48 px** (`btn-touch`, `kn-input-touch`), teks 16 px |
| Aksi utama | satu per halaman/dialog | **56 px** lebar penuh (`btn-touch btn-primary-cta`) |
| Target minimum | 24 × 24 px (WCAG 2.5.8) | **48 × 48 px**, jarak ≥ 8 px (ikon app bar: tampak 40, area sentuh 48 via `::after`) |
| Chip | 28 px | `kn-chip-touch` ≥ 48 px area sentuh |
| Lebar uji | — | **360 dan 390 px** (K-B4-04); teks reflow di 320 px; tabel boleh bergulir di wadahnya |

## 4. Tombol — WAJIB (G-UI-04, K-B1-06)
* Kelas resmi: `primary-button` · `secondary-button` · `danger-button` · `ghost-button` · `icon-button` · `link-button`
  (alias lama `btn-primary/btn-secondary/btn-danger` setara). shadcn `<Button>` **tidak** wajib (pemakaian nyata ±0).
* Ukuran hanya lewat pengubah resmi (`styles/standard.css`): **`btn-sm`** (desktop kecil, ≥ 32 px, 12 px) dan
  **`btn-touch`** (HP, ≥ 48 px, 16 px) + `btn-primary-cta` (56 px). `!py-*`, `!h-*`, `!text-*` di atas kelas tombol baku
  **dilarang** (ratchet `btn_force`). `<button>` berkelas Tailwind sendiri dilarang di kode baru (ratchet `btn_custom`).
* Aksi merusak: `danger-button` + `askConfirm`; dijauhkan dari aksi utama di HP.

## 5. Isian & form
* Wadah `FormModal` + `FormSection` (form HP = form desktop). Label di atas isian (`.field-label`, kini 12 px; di HP
  otomatis 14 px), tanpa titik dua; placeholder bukan label. **Tanda wajib tetap `*`** (K-B4-11).
* Isian desktop `.field` (batas `#8A8A8E`, placeholder `#6B6B73`); HP `kn-input-touch` (≥ 48 px; isian pindai utama
  + `min-h-touch-primary` = 56 px). Rujukan ID selalu lewat pemilih (`KNSelect`, `BinSelect`, `RollPicker`, `ProductSelect`).
* Galat di bawah isian, spesifik, ikon + teks; isian pengguna tidak pernah dihapus.

## 6. Halaman daftar & Unduh — WAJIB (G-UI-07, K-B4-07, K-B3b-04)
Anatomi: judul (`PageHeader`) → **cakupan** (bilah "Lokasi: … ▾") → ringkasan ≤ 4 angka → cari (`SearchBox`) → saringan
(`FilterChips`) → **Unduh ▾** → tabel/kartu → pager (`PaginationBar`).

**Satu tombol baku "Unduh ▾" — `components/ExportMenu.jsx`** (di pager: `PaginationBar exportSpec={{…}}`):
* Butir **Excel (.xlsx) — bawaan** dan **CSV (titik-koma)**, keduanya lewat mesin Pusat Export
  (`POST /api/export-center/quick`). Daftar yang sudah punya CSV kolom-layar (`exportConfig`, INV-UI-07) memakai itu
  untuk butir CSV.
* Isi berkas = **saringan + cari + cakupan daftar yang sedang dilihat**: `scope="work"` (daftar pekerjaan fisik FIX-1:
  lokasi tampilan + semua PT ditugaskan), `scope="active"` (PT aktif), `locationView` (layar stok). Jalur cari ditetapkan
  **registry dataset** (= endpoint daftarnya), bukan klien. Izin isi tetap dari modul sumber, visibilitas field & HPP.
* **≤ 50.000 baris → berkas langsung**; lebih → **job latar** Pusat Export + notifikasi "Unduhan siap" (tidak dipotong
  diam-diam). XLSX memuat lembar **Ringkasan** (dataset, saringan & cari, lokasi, PT, pengguna, waktu, jumlah baris).
  CSV daftar: `;`, BOM UTF-8, desimal koma, Ya/Tidak, anti-formula.
* Saringan layar yang belum bisa dinyatakan ke dataset → prop `unsupported="alasan"`: butir server **nonaktif dengan
  alasan tertulis** (tidak pernah mengunduh data yang lebih luas dari layar).
* Peran `warehouse` boleh mengunduh **dataset gudang saja** (daftar putih `export_registry_wms.WAREHOUSE_ROLE_DATASETS`),
  tetap dipagari lokasi tugasnya; menu Pusat Export terbuka untuk mengambil job besar.
* Dataset baru menambah **kolom saringan** `C(..., default=False)` (id gudang/produk) — ikut filter, tidak ikut kolom
  bawaan berkas (EXP-04).

## 7. Aplikasi HP gudang — WAJIB (G-UI-05, G-UI-01 HP)
* Kelas teks: `kn-hp-title` (16/700), `kn-hp-info` (16), `kn-hp-support` (14), `kn-hp-tag` (14). Dilarang `text-xs` &
  `text-[N<14px]` (ratchet `hp_font_lt14`).
* Semua tombol/isian interaktif: `btn-touch` / `kn-input-touch` / `kn-chip-touch` / `min-h-touch` (ratchet `hp_touch`).
  Komponen bersama di dalam `.m-shell` (label, `PageTabs`, bilah lokasi, `notice-bar`) otomatis 48 px / 14 px.
* Hasil pindai: ikon + judul + teks + warna lembut (`bg-kn-*-soft`); aksi lanjut lebar penuh.

## 8. Status & lencana
`status-pill` (12 px; semua pasangan teks/latar lolos ≥ 4,5:1 — dihitung G-UI-03). Komponen `StatusBadge` {nada, ikon,
label} & `TaskTypeBadge` = **tahap 2** (B4 §3.9). Saringan ≠ status ≠ tab (`FilterChips` / lencana / `PageTabs`).

## 9. Penjaga & baseline
| ID | Aturan | Penjaga | Mode | Baseline (9 Nov, sesudah FIX-4) |
|---|---|---|---|---|
| G-UI-01 | huruf < 12 px (`text-[Npx]`, `fontSize`, CSS `font-size`) | `verify_ui_standard.py` `font_lt12` | ratchet/berkas | `baselines/ui_font_lt12.json` |
| G-UI-01 HP | huruf < 14 px di `features/mobile` | `hp_font_lt14` | ratchet | `ui_hp_font_lt14.json` |
| G-UI-02 | literal hex di JS/JSX + himpunan hex berbeda tidak bertambah | `hex` + `ui_hex_set.json` | ratchet | `ui_hex.json`, `ui_hex_set.json` |
| G-UI-03 | kontras token & kelas baku | `verify_ui_contrast.py` | **keras** | 58/58 pasangan lolos |
| G-UI-04 | `<button>` Tailwind sendiri | `btn_custom` | ratchet | `ui_btn_custom.json` |
| K-B1-06 | `!py/!h/!text` di kelas tombol baku | `btn_force` | ratchet | `ui_btn_force.json` |
| G-UI-05 | target sentuh HP tanpa tanda ≥ 48 px | `hp_touch` | ratchet | `ui_hp_touch.json` |
| G-UI-07 | `PaginationBar` tanpa `exportSpec` | `list_no_excel` | ratchet | `ui_list_no_excel.json` |
| G-UI-07 keras | layar daftar WMS-RFID (matriks B3b) wajib `ExportMenu`/`exportSpec`; pengecualian beralasan | `WMS_LISTS` / `WMS_LIST_EXEMPT` | **keras** | 31 dipasang + 6 beralasan |
| INV-UI-07 | CSV kolom-layar benar (`;`, BOM, desimal koma) | `verify_list_export.py` | keras | tetap |

```
PYTHONUTF8=1 python scripts/guardrails/verify_ui_standard.py            # gate
PYTHONUTF8=1 python scripts/guardrails/verify_ui_standard.py --census [--ref <git-ref>]   # sensus sebelum/sesudah
PYTHONUTF8=1 python scripts/guardrails/verify_ui_contrast.py --table    # tabel rasio
```
Ratchet: jumlah per berkas hanya boleh turun; berkas baru = 0; kencangkan dengan `--update`.

## 10. Tahap
* **Tahap 1 (FIX-4, selesai):** token, kelas baku AA, pengubah tombol, pager & Unduh baku, HP gudang (huruf & sentuh),
  31 daftar WMS-RFID ber-Unduh, guardrail + baseline.
* **Tahap 2 (sisa):** `StatusBadge`/`TaskTypeBadge`, `EmptyState`, peleburan `KNPager`/`PagedRows`/`ListControls` ke
  satu versi, pemigrasian 12 px di layar gudang yang disentuh, Unduh di berkas PREP-H (sesudah digabung), dataset antrean
  periksa gate V2 (butuh keputusan cakupan), tampilan tersimpan (K-B4-12, di luar paket), CSV Pusat Export klasik ke
  dialek Indonesia, ukur lebar CSS C72 (K-B4-04).
