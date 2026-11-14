# Perapian Meja Finance — penyajian antrean & tombol Bantuan

- Commit awal: `cd6963a`        - Commit akhir: lihat `git log` branch        - Branch: `claude/gifted-cori-1trg95`
- Permintaan langsung pemilik (14 Nov 2026), **bukan** temuan bertracker — `docs/reviews/TRACKER.md` tidak diubah.
- Lingkup: **penyajian saja**. Isi & hitungan antrean (`backend/services/work_desk_service.finance_desk`,
  `GET /api/finance/desk`) dan papan keputusan (`/api/home/finance`) **tidak disentuh**; tidak ada berkas backend berubah.
- Acuan: `docs/KN_37_STANDAR_UI_GUDANG.md` (token `kn-*`, kelas tombol baku, status = ikon + teks + warna) ·
  `docs/KN_08_UI_UX_STANDARDS.md` (progressive disclosure, keadaan kosong).

## Ringkasan angka (terukur Playwright, `alat/potret_meja_finance.js`)

| Skenario | Lebar | Tinggi halaman sebelum → sesudah | Kartu antrean besar | Papan kontrabon kosong | Tombol Bantuan menutupi isi saat halaman dibuka |
|---|---|---|---|---|---|
| Data acuan (1 berisi) | 1280 | 1503 → **933** px | 11 → **1** + 1 baris lipatan | 127 → **36** px | kepala kartu "Uang masuk" (NILAI) → **tidak ada** (di topbar) |
| Data acuan | 390 | 2757 → **1405** px | 11 → **1** + 1 baris | 168 → **50** px | teks Pelacak SO → teks Pelacak SO (tetap mengapung ≤ 768 px, keputusan pemilik) |
| Rekayasa A (3 berisi) | 1280 | 2170 → **1547** px | 11 → **3** | 127 → **36** px | "Rp 70.000.000" kartu Uang masuk → **tidak ada** |
| Rekayasa A | 390 | 4233 → **3112** px | 11 → **3** | 168 → **50** px | teks Pelacak SO → teks Pelacak SO |
| Rekayasa B (semua kosong) | 1280 | 1384 → **800** px (muat 1 layar) | 11 → **0** + "Semua 11 antrean bersih" | 127 → **36** px | kepala kartu "Uang masuk" → **tidak ada** |
| Rekayasa B | 390 | 2596 → **1067** px | 11 → **0** | 168 → **50** px | teks Pelacak SO → teks Pelacak SO |

Saat digulir ke **paling bawah**: 0 elemen tertutup di semua skenario, sebelum maupun sesudah (ruang aman
`#main-content { padding-bottom: 104px }` bekerja). Rekayasa = jawaban `/api/finance/desk` dicegat Playwright
(`alat/buat_data_rekayasa.py`), DB tidak disentuh; data acuan = `restore_local_demo.sh --seed-only`.

## #1 — Kartu kosong mendominasi; antrean yang perlu ditindak tenggelam
- Berlaku di HEAD: **ya** — `FinanceDesk` merender semua antrean sebagai kartu sama besar dalam urutan server; data acuan:
  11 kartu, 10 bernilai 0 (HEAD mengirim **11** antrean, bukan 13 seperti di laporan; kemungkinan hitungan pelapor
  ikut papan/kartu lain).
- Perubahan (sebelum → sesudah):
  - Antrean **ber-isi** tampil dulu, urut **umur tertua → nilai rupiah → jumlah dokumen**, seri terakhir mengikuti urutan
    server (`features/sales_admin/deskQueueOrder.js`, fungsi murni). Nilai yard/jumlah dokumen tidak dibandingkan
    dengan rupiah.
  - Antrean **kosong** dilipat jadi satu baris `DeskEmptyQueues`: "N antrean kosong — tidak ada yang perlu ditindak" +
    daftar nama (dipotong 1 baris desktop / 2 baris HP, nama lengkap di `title`) + tombol baku `ghost-button btn-sm`
    **Tampilkan/Sembunyikan** (`aria-expanded`, `aria-controls`). Dibuka: daftar 2 kolom (xl) — ikon centang + nama +
    petunjuk + angka 0. Semua kosong → "Semua 11 antrean bersih". Tidak ada antrean yang hilang dari layar.
- Status = ikon (CheckCircle2) + teks ("antrean kosong", angka 0) + warna (`kn-success-*`).

## #2 — Papan "Kontrabon menunggu persetujuan (0)" memakan ruang besar
- Berlaku di HEAD: **ya** — papan utama selalu digambar (regresi B5) sebagai kotak ±127 px walau kosong.
- Perubahan: prop opsional `compactEmpty` (`WaitingBoardsStrip` → `WaitingQueueBoard`), dipakai hanya Meja Finance:
  papan **terbaca & kosong** = satu baris (ikon centang + "Tidak ada kontrabon yang menunggu persetujuan" + `link-button`
  "Buka Kontrabon →"), 36 px. Papan berisi & keadaan **gagal dibaca** tetap kotak penuh + **Coba lagi** (B5: kegagalan
  tidak boleh tampil sebagai kabar baik — ada tesnya). testid lama (`…-empty`, `…-goto`) dipertahankan.

## #3 — Tinggi kartu tidak seragam; satu kartu sendirian di baris terakhir
- Berlaku di HEAD: **ya** — `DeskQueueCard` sengaja `self-start` (tinggi masing-masing).
- Perubahan: prop opsional `stretch` + `className` pada `DeskQueueCard` (bawaan = perilaku lama; meja lain tidak
  berubah — ada tesnya). Meja Finance: kartu **terbuka** sebaris sama tinggi; kartu ditutup pengguna kembali
  `self-start`; jumlah kartu ganjil → kartu terakhir `xl:col-span-2` (tidak ada kartu sendirian setengah lebar).
- Konsekuensi yang disengaja: kartu yang barisnya lebih sedikit menyisakan ruang kosong **di dalam** bingkainya
  (rekayasa A: Selisih bayar 3 baris di samping Uang masuk 5 baris + pager).

## #4 — Tombol melayang "Bantuan & Panduan" menutupi angka
- Berlaku di HEAD: **ya**. Ruang aman 104 px hanya menolong di **akhir** halaman; saat halaman dibuka tombol menutupi
  apa pun yang ada di pojok kanan bawah layar (terukur: NILAI kartu Uang masuk; pada rekayasa A "Rp 70.000.000" dan
  pemilih urutan "Tertua dulu"). Catatan serupa sudah muncul di P6, P18, P19.
- Keputusan pemilik (ditanyakan di sesi ini): **pindah ke topbar**. Perubahan **global** (semua layar & peran):
  - Layar **> 768 px**: `TourMenu placement="topbar"` — `icon-button` bola lampu di topbar (antara lonceng dan Sync),
    panel turun dari atas, `aria-expanded`/`aria-haspopup`. Tidak ada elemen `fixed` di atas isi.
  - Layar **≤ 768 px** (tampilan desktop di HP): tetap tombol bulat mengapung (label teks dibuang — memang tak pernah
    tampil di lebar itu), ruang aman bawah tetap.
  - Esc menutup panel lewat `useEscapeClose` (INV-UI-10). Klik di luar: mode mengapung = lapisan `fixed inset-0`
    (lama); mode topbar = pendengar `mousedown` dokumen — lapisan `fixed` tidak bisa dipakai karena topbar
    ber-`backdrop-filter` menjadi wadah elemen `fixed` (terukur: klik di luar tidak menutup panel sebelum diganti).
  - Satu status menu (`showTourMenu`) untuk kedua penempatan (`App.js`), slot baru `helpMenu` di `TopBar`.

## Berkas berubah
- Baru: `features/sales_admin/deskQueueOrder.js`, `features/sales_admin/DeskEmptyQueues.jsx`,
  `features/__tests__/financeDeskTidy.test.js`, `components/__tests__/tourMenuPlacement.test.js`.
- Ubah: `features/finance/FinanceDesk.jsx`, `features/sales_admin/DeskQueueCard.jsx` (opt-in),
  `components/WaitingQueueBoard.jsx` + `WaitingBoardsStrip.jsx` (opt-in), `components/TourMenu.jsx`,
  `components/CoreWidgets.jsx` (slot `helpMenu`), `App.js`, `styles/layout.css` (catatan ruang aman saja),
  `CODEBASE_MAP.md` (3 baris hitungan fitur).
- Token Standar UI pada berkas yang disentuh: `FinanceDesk.jsx` huruf < 12 px 4 → 0, hex 11 → 0; `TourMenu.jsx`
  huruf < 12 px 4 → 0, hex 12 → 0 (tombol mengapung kini `bg-kn-action` 6,43:1, dulu `#007AFF` 4,02:1). Berkas baru 0.

## Pengujian
- Jest baru `financeDeskTidy.test.js` (8): urutan murni; **semua kosong** (tanpa kartu, baris "Semua 11 antrean bersih",
  buka/tutup, 11 butir angka 0, metrik 0); **sebagian berisi** (urutan umur, `stretch`, kartu ganjil merentang,
  angka & baris server tidak berubah, kartu ditutup → `self-start`); 2 berisi tanpa rentang; papan kontrabon ringkas;
  papan berisi & gagal-baca tetap penuh (B5); `DeskQueueCard` tanpa `stretch` = lama. Dijalankan terhadap
  `FinanceDesk.jsx` HEAD: **4 gagal** (perilaku baru), 4 lulus (penjaga regresi) — tesnya menangkap perubahan.
- Jest baru `tourMenuPlacement.test.js` (3): topbar = `icon-button` tanpa widget `fixed`, panel `top-full`;
  Esc & klik di luar menutup, klik di dalam tidak; mode mengapung tetap.
- Jest penuh: **87 suite / 615 tes lulus** (`CI=true yarn test --watchAll=false`).
- Penjaga statik: `verify_ui_standard.py` **PASS** dan turun (huruf < 12 px 6935 → 6927, hex 16808 → 16785, hex berbeda
  703 → 702; btn_custom 784 & btn_force 577 tetap) · `verify_ui_contrast` 58/58 · `verify_escape_layers` ·
  `verify_desk_targets` · `verify_role_label` · `verify_error_notice` · `verify_blocking_dialogs` ·
  `verify_modal_dismiss` · `verify_custom_modals` · `verify_codebase_map` — semua PASS.
- **`scripts/guardrails/verify_role_gate_ui.py` tidak ada** di repo (juga tidak di riwayat git) — tidak bisa dijalankan;
  penjaga peran terdekat `verify_role_label.py` (INV-ROLE-01) PASS.
- ESLint berkas berubah: 0 galat (1 peringatan lama `CoreWidgets.jsx:88`, bukan baris yang diubah).
- Peramban (Playwright, finance@, 1280 px): panel Bantuan terbuka di bawah topbar tanpa terpotong, Esc menutup, klik
  di luar menutup, lipatan antrean terbuka (10 butir), tombol "Terbitkan" baris Faktur Pajak bisa diklik
  (`elementFromPoint`), 0 galat halaman.

## Bukti UI (`shots/`)
`sebelum-*` / `sesudah-*` × `acuan` · `A` · `B` × `1280` · `390` (halaman penuh), `*-tampilan-pertama` (viewport saat
dibuka — tempat tombol melayang menutupi isi), `sesudah-1280-bantuan-terbuka`, `sesudah-1280-lipatan-terbuka`.
Potret 390 px = Meja Finance lewat "Tampilan Desktop" (`kn_force_desktop=1`): di HP peran Finance mendarat di aplikasi
HP (MobileOpsApp), bukan layar ini. Notifikasi topbar "Login berhasil…" ditutup sebelum memotret (lihat Keterbatasan).

## Fixture vs proses bisnis
Data acuan dari rantai seed resmi; skenario A/B = respons API dicegat di peramban (penyajian saja, tanpa tulis DB).

## Dampak pada modul terkait
- Tombol Bantuan pindah ke topbar di **semua** layar desktop untuk **semua** peran.
- `DeskQueueCard`, `WaitingQueueBoard`, `WaitingBoardsStrip` dipakai meja lain — perubahan hanya lewat prop opsional;
  Meja Admin Sales, Meja Saya, Operasi Gudang, beranda tidak berubah.

## Keterbatasan / yang belum diuji
- Topbar 1280 px yang padat (pemilih PT + bilah lokasi + peringatan "Lokasi kerja belum diatur") kini memotong judul
  lebih pendek ("Meja Finan…" → "Meja …") karena satu ikon tambahan; breadcrumb tetap ada.
- ≤ 768 px tombol masih mengapung dan pada tampilan pertama menutupi teks tabel Pelacak SO (keputusan pemilik).
- Rantai seed data acuan di lingkungan ini: 3 dari 12 skrip gagal karena aturan aplikasi lebih baru menolak langkah
  seed (`seed_demo_transaksi_kn` — ambil wajib pindai roll, QC 4-point, blok kredit; `seed_p03_kn`; `seed_p05_kn`).
  Bawaan HEAD, bukan akibat perubahan ini; data finance tetap memuat 11 antrean (1 berisi).
- Di luar lingkup, ditemukan: notifikasi topbar "Login berhasil sebagai Finance." melebarkan halaman 1280 px menjadi
  1454 px (gulir horizontal) sampai ditutup.
- Belum diuji di Safari/Firefox; tidak ada uji e2e penuh semua peran untuk posisi tombol Bantuan.

Status: implemented_pending_review

## Hambatan lingkungan
Docker Hub membatasi unduhan (429) → mongo dari `mirror.gcr.io/library/mongo:7`; backend (Python 3.11) & frontend
(`craco start`) dijalankan langsung tanpa container; `/app` = symlink ke repo. Worker sesi sempat dimulai ulang
(layanan dinyalakan ulang, hasil tidak terpengaruh).

## Yang perlu direview
1. Aturan urutan antrean ber-isi (umur → nilai → jumlah) — atau mau urutan nilai dulu?
2. Ruang kosong di dalam kartu yang lebih pendek akibat tinggi seragam.
3. Posisi tombol Bantuan di topbar untuk semua peran; pemendekan judul topbar saat topbar padat.
