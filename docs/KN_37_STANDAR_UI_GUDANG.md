# KN_37 — Standar UI Gudang v1

| | |
|---|---|
| Status | **Berlaku** sejak 9 Nov 2026 (paket FIX-4, tahap 1); **tahap 2 berlaku 10 Nov 2026 (paket FIX-8)**: lencana status, keadaan kosong/memuat/galat/tanpa izin, satu pager & kotak cari, waktu WIB, tanpa id mentah, nomor dokumen satu skema tampilan, pola detail, tampilan tersimpan. Keputusan pemilik lewat koordinator: K-B4-01 (wajib, ditegakkan ratchet), K-B4-02, K-B4-03, K-B4-04, K-B4-06, K-B4-07 + K-B3b-04, K-B4-11, **K-B4-12 (tampilan tersimpan = YA)**, K-B1-06, K-B1-09 |
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
Anatomi: judul (`PageHeader`) → **cakupan** (bilah "Lokasi: … ▾") → ringkasan ≤ 4 angka → cari (`SearchBox`/
`SearchInput`) → saringan (`FilterChips`) → urut → **Tampilan: … ▾** (`SavedViewsMenu`, §6b) → **Unduh ▾** →
tabel/kartu (keadaan: `EmptyState`, §6a) → pager (`PaginationBar`).

**Satu komponen per pola (G-UI-10, keras, FIX-8):** satu pager = `PaginationBar` (`KNPager`, `PagedRows`,
`usePagedRows` hanya pembungkusnya — dulu 3 gaya); satu kotak cari = `ListPageParts.SearchInput` (`SearchBox` =
kotak itu + saringan di sebelahnya; `ListControls` meminjamnya); satu tab status = `ListPageParts.StatusTabs`.

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

### 6a. Keadaan daftar — WAJIB (B4 §3.10, B1b UI-49/UI-50; ratchet `empty_false`)
Satu komponen `components/EmptyState.jsx` + `listStateKind({loading, error, count, filtered})`; `ResponsiveTable`
menerima `error`/`onRetry`/`filtered`/`onReset`/`what` dan memakainya otomatis.

| Keadaan | Tampil | Dilarang |
|---|---|---|
| **memuat** | ikon berputar + "Memuat …" (angka KPI "…") | "0", "Belum ada …", "Tidak ada …" sebelum data datang |
| **kosong** | ikon + "Belum ada …" + satu aksi utama (opsional) | — |
| **saringan kosong** | "Tidak ada … yang cocok dengan saringan" + **Reset saringan** | teks kosong biasa |
| **galat** | kalimat `apiErrorText` + **Coba lagi** | galat ditelan (`.catch(() => setX([]))`) |
| **tanpa izin (403)** | "Anda tidak punya akses ke …" + "ini bukan daftar kosong — minta admin" | tampil sebagai kosong |

Pemilih yang daftar opsinya bisa 403 (mis. grade dari Master Grade untuk peran gudang) memakai `useGrades` +
`GradeLoadNote` (catatan di dekat pemilih), bukan daftar opsi kosong diam-diam.

### 6b. Tampilan tersimpan — K-B4-12 (FIX-8)
`components/SavedViewsMenu.jsx` + `hooks/useSavedViews.js` → API `/api/saved-views` (koleksi `saved_views`,
ENTITY_REGISTRY). Satu tampilan = **saringan + urut + kolom (disembunyikan) + mode** sebuah daftar.
* Pribadi per pengguna; **admin** boleh membagikan ke peran dan/atau PT (+ "bawaan untuk penerima").
* Saat daftar dibuka: bawaan pribadi → bawaan bersama dipasang sekali; `*` di tombol = layar berbeda dari tampilan aktif;
  "Tampilan standar" = tanpa saringan.
* **Cakupan tidak pernah ikut** (PT aktif, lokasi kerja, site — server menolak kuncinya 400); nilai saringan di luar
  daftar pilihan pengguna diabaikan saat dipasang. Izin = izin lihat daftarnya.
* Terpasang di: Operasi Gudang › Stok › **Roll** (gudang, lini, status cek, hanya di-peg, Kelompok/Daftar, 7 kolom
  opsional), **Transfer** (jenis, status, lini, urut: terbaru/terlama/nomor/status, 3 kolom opsional), **Barang Keluar**
  (status, gudang, jenis SO/Sample). Daftar lain menambah kunci di `saved_view_service.LISTS` + satu `useSavedViews`.

## 7. Aplikasi HP gudang — WAJIB (G-UI-05, G-UI-01 HP)
* Kelas teks: `kn-hp-title` (16/700), `kn-hp-info` (16), `kn-hp-support` (14), `kn-hp-tag` (14). Dilarang `text-xs` &
  `text-[N<14px]` (ratchet `hp_font_lt14`).
* Semua tombol/isian interaktif: `btn-touch` / `kn-input-touch` / `kn-chip-touch` / `min-h-touch` (ratchet `hp_touch`).
  Komponen bersama di dalam `.m-shell` (label, `PageTabs`, bilah lokasi, `notice-bar`) otomatis 48 px / 14 px.
* Hasil pindai: ikon + judul + teks + warna lembut (`bg-kn-*-soft`); aksi lanjut lebar penuh.

## 8. Status & lencana — WAJIB (G-UI-06, ratchet `chip_custom`; FIX-8)
**Satu komponen `components/StatusBadge.jsx`** — ikon + teks + warna token (tidak pernah warna saja, WCAG 1.4.1):
`<StatusBadge status="quarantine" domain="roll" />` · `<StatusBadge status={s} label={labelLama(s)} />` ·
`<StatusBadge tone="special" icon="tag">Antar PT</StatusBadge>`.
* **Kosakata tunggal `utils/statusVocab.js`**: label per ranah (`roll`, `transfer`, `task_in`, `task_out`, `task_hp`,
  `putaway`, `grn`, `inspection`, `registration`, `cycle_count`, `print_job`, `print_item`, `delivery`) dipindah 1:1 dari
  peta lama (istilah tidak berubah, K-13) + cadangan peta umum `DOC_STATUS_LABEL` (tidak pernah kode mentah); nada & ikon
  per kode. Berkas fitur lama mengekspor ulang dari sini (`ROLL_STATUS_META`, `PA_STATUS`, `INS_STATUS_LABEL`, …).
* 6 nada (B4 §3.9): **berhasil** selesai/tersedia · **info** berjalan/terbuka · **perhatian** menunggu/ditahan/sebagian ·
  **bahaya** ditolak/gagal/rusak · **netral** draf/arsip/dibatalkan · **khusus** kategori (dipesan, makloon, sampel,
  antar-PT). Kelas `kn-badge tone-*` — 6 pasangan dihitung G-UI-03 (5,59–9,79:1).
* Pembungkus lama yang kini merender StatusBadge: `Pill` (RFID), `RollStatusBadge`, `QcStatusBadge`, `TaskBadge`,
  `Badge` (keluar), `GrnStatusBadge`, `transferConstants.StatusBadge`, `LotStatusPill`. `status-pill` mentah & pil
  Tailwind buatan layar = pola usang (ratchet). `TaskTypeBadge` = sisa.
* Saringan ≠ status ≠ tab (`FilterChips` / lencana / `PageTabs`).

### 8a. Waktu, id, nomor dokumen — WAJIB (B3b G-OUT-01/02, B1b UI-58; ratchet `date_no_wib`, `id_fallback`)
* **Waktu = WIB lewat formatter tunggal** `utils/formatters`: `formatDate` ("10 Nov 2026"), `formatDateTime`
  ("10 Nov 2026 05.30 WIB"), `formatTime` ("05.30 WIB"). Dilarang `new Date(x).toLocaleString(` / `toLocale*String("id-ID",
  {day|hour…})` tanpa `timeZone`, dan `x_at.slice(0, 10|16)` atas stempel UTC. Pembantu lama (`fmtTime` RFID,
  `formatDate` stok, `shortDate*` lot, `localTs` SPK) kini memanggil formatter ini.
* **Tanpa id mentah**: label tidak boleh jatuh ke `x.id`/`x.foo_id` (`nama || x.id`); pakai nama/kode atau teks jujur
  ("Gudang tanpa nama", "Produk tanpa nama", `entityShort`/`entityShortFromCtx` untuk PT). Id sebagai NILAI/kunci boleh.
* **Nomor dokumen satu skema TAMPILAN** `components/DocNumber.jsx`: `[PT] NOMOR` untuk dua skema tersimpan (`KSC/PO-00166`
  dan `PRET-00070` milik PT KSC tampil sama). Nomor tersimpan tidak diubah; teks elemen = nomor tersimpan (salin/cari tetap).

### 8b. Pola detail — (B1b UI-60, B4 §3.7; keputusan implementer FIX-8)
| Jenis layar | Pola | Contoh |
|---|---|---|
| Dokumen **kerja bertahap** (pindai/hitung/rekonsiliasi berlangkah, tabel panjang) | **halaman detail sebaris** dengan kepala baku `DetailParts.DetailHeader` ("← Kembali ke daftar …" ≥ 32 px, judul + lencana, aksi kanan; aksi merusak di `dangerActions` — terpisah di ujung) | GRN Kedatangan, Perbaikan, Retur, Order Makloon, Opname, Pendaftaran awal |
| **Rincian dokumen** baca + aksi ringkas | `DetailModal` (layar penuh di HP) | Transfer, SPK inspeksi, Lot, Pengiriman |
| **Rincian roll** dari tabel | panel/pop-up roll (`RollJourneyPopup`, `DetailDrawer`) | Jejak roll |

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
| **G-UI-06** (FIX-8) | lencana buatan sendiri: `status-pill` mentah, `<Pill>`, `<span>` berpil Tailwind (rounded+px+latar+huruf ≤ 12) | `chip_custom` | ratchet | `ui_chip_custom.json` (560; gudang 117 → 93 sebelum baseline) |
| **G-OUT-01** (FIX-8) | tanggal/jam tanpa formatter WIB | `date_no_wib` | ratchet | `ui_date_no_wib.json` (139; gudang+HP 24 → 0) |
| **G-OUT-02** (FIX-8) | cadangan label ke id mentah `… \|\| x.id` | `id_fallback` | ratchet | `ui_id_fallback.json` (163; gudang+HP 61 → 5) |
| **UI-49/50** (FIX-8) | kosong palsu: galat ditelan jadi `[]`, "Belum ada" tanpa penjaga memuat | `empty_false` | ratchet | `ui_empty_false.json` (308) |
| **G-UI-10** (FIX-8) | satu pager (`KNPager`/`usePagedRows` → `PaginationBar`), `ListControls` tanpa `<input>` sendiri | `single_pattern_problems` | **keras** | lolos |

```
PYTHONUTF8=1 python scripts/guardrails/verify_ui_standard.py            # gate
PYTHONUTF8=1 python scripts/guardrails/verify_ui_standard.py --census [--ref <git-ref>]   # sensus sebelum/sesudah
PYTHONUTF8=1 python scripts/guardrails/verify_ui_contrast.py --table    # tabel rasio
```
Ratchet: jumlah per berkas hanya boleh turun; berkas baru = 0; kencangkan dengan `--update`.

## 10. Tahap
* **Tahap 1 (FIX-4, selesai):** token, kelas baku AA, pengubah tombol, pager & Unduh baku, HP gudang (huruf & sentuh),
  31 daftar WMS-RFID ber-Unduh, guardrail + baseline.
* **Tahap 2 (FIX-8, 10 Nov 2026, selesai):** `StatusBadge` + kosakata tunggal, `EmptyState` (5 keadaan) di layar
  WMS-RFID utama, peleburan pager & kotak cari & tab status, waktu WIB, tanpa id mentah, `DocNumber`, pola detail,
  tampilan tersimpan (K-B4-12) di 3 daftar utama, 4 ratchet baru + 1 cek keras, kontras 67/67.
* **Sisa (tahap 3):** `TaskTypeBadge`; `StatusPill` (CoreWidgets, 47 berkas non-gudang, menampilkan kode) → StatusBadge;
  migrasi 12 px di layar gudang (dibekukan ratchet); tampilan tersimpan untuk daftar lain (GRN, PA, tag RFID) + urut
  server roll (paket performa); Unduh di berkas PREP-H; dataset antrean periksa gate V2; CSV Pusat Export klasik ke
  dialek Indonesia; ukur lebar CSS C72 (K-B4-04); `DocNumber` & `DetailHeader dangerActions` di layar retur/makloon/PO.
