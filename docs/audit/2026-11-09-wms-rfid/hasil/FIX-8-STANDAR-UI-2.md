# FIX-8 — Standar UI Gudang v1 tahap 2 (lencana status · keadaan kosong/memuat/galat/tanpa izin · satu pager & kotak cari · waktu WIB · tanpa id mentah · nomor dokumen · pola detail · tampilan tersimpan)

- **Tanggal:** 10 Nov 2026 (WIB, selesai ±01.45) · **Pelaksana:** Claude Code (implementer paket FIX-8) · **Branch:** worktree
  `worktree-agent-a25cd57f6c540a261` (dasar `main` `c729f4e`; `main` kemudian maju ke `237a97b` = dokumen mockup saja).
- **Status:** `implemented_pending_review` (implementer tidak menetapkan `verified`). Verifikasi tampilan di peramban (360/390 px,
  desktop) diserahkan ke koordinator — paket ini tidak memakai alat peramban.
- **Bahan:** `KN_37` (v1), `hasil/FIX-4-STANDAR-UI.md` (§11 sisa tahap 2), `B4-RISET-STANDAR-UI.md` §3.4/§3.7/§3.9/§3.10/§3.13,
  `B1-UI-MENU-PERAN.md` (UI-08, UI-15, UI-17, UI-25, UI-33), `B1b-SAPUAN-LANJUTAN.md` (UI-49, UI-50, UI-58, UI-60, "pager 3 gaya"),
  `B3b-FORM-INPUT-DAFTAR.md` (INP-15/G-OUT-01, INP-16/G-OUT-02).
- **Standar:** `docs/KN_37_STANDAR_UI_GUDANG.md` diperbarui ke **tahap 2** (§6 anatomi, §6a keadaan daftar, §6b tampilan tersimpan,
  §8 lencana, §8a waktu/id/nomor, §8b pola detail, §9 penjaga, §10 tahap).
- **Commit:** `422c195` (kode, API, penjaga, KN_37, ENTITY_REGISTRY) · `32ad774` (penjaga INV-UI-07/INV-UI-02) · commit laporan ini.

---

## 1. Keputusan yang diterapkan (mandat pemilik lewat koordinator)

| Keputusan (brief) | Penerapan |
|---|---|
| **1. Komponen baku `StatusBadge` + `EmptyState`** | `components/StatusBadge.jsx` (ikon + teks + warna token; 6 nada B4 §3.9) + **kosakata tunggal** `utils/statusVocab.js` (label per ranah dipindah 1:1 — istilah tidak berubah, K-13/KN_32; nada & ikon per kode). `components/EmptyState.jsx` + `listStateKind()` — 5 keadaan: memuat · kosong · saringan kosong · galat · **tanpa izin (403)**. `ResponsiveTable` memakainya otomatis (`error`/`onRetry`/`filtered`/`onReset`). Terpasang di layar WMS-RFID utama (§3) |
| **2. Peleburan pager & kotak cari** | `KNPager` = pembungkus `PaginationBar` (dulu pager 12 px hex lepas `btn-xs`); `PagedRows`/`usePagedRows` ikut. Satu `SearchInput` (ListPageParts) dipinjam `ListControls`, layar Stok, Transfer, Barang Keluar; satu `StatusTabs`. Unduh FIX-4 tetap (36 tombol, kontrak 0 masalah) |
| **3. Tampilan tersimpan (K-B4-12 = YA)** | API `/api/saved-views` + koleksi **`saved_views`** (ENTITY_REGISTRY, USER-SCOPED, index) + `SavedViewsMenu`/`useSavedViews`; saringan + urut + kolom + mode; pribadi, opsional dibagikan **admin** ke peran/PT; bawaan dipulihkan saat daftar dibuka; **cakupan PT/lokasi FIX-1 tidak pernah disimpan** (server menolak 400). Terpasang di Stok › Roll, Transfer, Barang Keluar |
| **4. Waktu WIB · tanpa id mentah · nomor dokumen · pola detail** | formatter tunggal `formatDate`/`formatDateTime`/`formatTime` (WIB) di semua titik WMS-RFID (gudang+HP 24 → 0 temuan statik); cadangan `|| x.id` → label (gudang+HP 61 → 3, sisa = nilai, bukan label); `components/DocNumber.jsx` skema tampilan `[PT] NOMOR` (nomor tersimpan tidak diubah); pola detail per jenis layar (§7 K8-7) + `DetailHeader dangerActions` |
| **5. Guardrail & KN_37** | 4 ratchet baru di `verify_ui_standard.py` (`chip_custom`, `id_fallback`, `date_no_wib`, `empty_false`; baseline = sesudah FIX-8) + cek keras **G-UI-10** (satu pager/kotak cari) + 9 pasangan kontras baru (67/67) + self-test 26 kasus; KN_37 tahap 2 |

## 2. Temuan yang ditutup (ID → perubahan → uji)

| ID | Perubahan | Uji |
|---|---|---|
| **B1b UI-49** (P2) — galat izin disamarkan sebagai kosong | Skor mitra makloon: 403 → "Anda tidak punya akses …" (dulu "Belum ada penerimaan makloon"); pemilih grade di lembar inspeksi, rincian baris SPK, inspeksi roll: `useGrades` + `GradeLoadNote` ("Daftar grade tidak bisa dimuat — Anda tidak punya akses ke Master Grade Mutu …", dulu pilihan kosong diam). Pola sama ditutup di daftar GRN, transfer, roll, PA, tugas keluar, tugas HP, riwayat lintasan, opname RFID (`catch { /* noop */ }`), job cetak, insiden | jest `fix8StandarUi2` (skor mitra 403, catatan grade, lintasan 403, TransferList 403, ResponsiveTable 403); sumber tanpa `.catch(() => setGrades([]))` |
| **B1b UI-50** (P2) — kosong/nol palsu saat memuat | `PaginationBar` "Memuat …" bila `loading && total=0` (Lot & Silsilah); Data Gudang "Memuat lokasi…" + KPI "…" (dulu 0); Monitor Gerbang "Memuat gerbang…"; Retur Antar-PT "Memuat retur antar-PT…"; Analitik Stok; ditambah PA, RFID (lintasan, opname, job cetak, insiden), opname, pendaftaran awal, tugas keluar ("Memuat…" alih-alih "0 tugas"), detail GRN | jest (pager memuat, PA memuat, lintasan memuat, RollsTable memuat) |
| **B1b UI-58** (P3) — nomor dokumen dua skema | `DocNumber`: `KSC/GRN-00023` dan `PA00012` milik KSC sama-sama tampil `[KSC] …`; dipasang di daftar & detail GRN, daftar transfer, tugas keluar (SO), PA. Teks elemen = nomor tersimpan (`/` tak terlihat) — salin/cari/uji teks tidak berubah | jest DocNumber (dua skema, PT tak dikenal → tanpa lencana, bukan id) |
| **B1b UI-60** (P3) — pola detail campur | Satu pola per jenis layar (§7 K8-7). GRN: ikon panah 16 × 16 → kepala baku `DetailHeader` ("Kembali ke daftar Kedatangan"), "Batalkan" jadi `danger-button` di slot **`dangerActions`** (terpisah di ujung, bergaris pemisah), "Jadikan sample uji" `secondary-button`; memuat/403 detail GRN memakai `EmptyState` | jest statik (GrnDetail memakai DetailHeader + dangerActions) |
| **B1b "pager 3 gaya berbeda"** · B4 §3.13 | `KNPager`/`PagedRows`/`usePagedRows` → `PaginationBar`; `ListControls` tanpa `<input>` sendiri | jest (KNPager/PagedRows merender `.kn-pager`), guardrail G-UI-10 (keras) |
| **B4 §3.9 / KN_37 §8** — status chip berbagai gaya | `StatusBadge` menggantikan: `Pill` RFID (33 pemakaian, kini pembungkus), `RollStatusBadge`, `QcStatusBadge`, `TaskBadge` (masuk), `Badge` (keluar), `GrnStatusBadge` + terminal stepper, `transferConstants.StatusBadge` + jenis transfer, PA (dulu hex inline), SPK (daftar, rincian, baris: ditahan/random check/MDQ/warna/handfeel), opname, pendaftaran, lot (status/asal/roll), riwayat grade & HPP roll, inspeksi roll, Data Gudang aktif/nonaktif, roll "tanpa lot"/"cacat", pengiriman (daftar & riwayat), stok OK/Rendah/Habis | jest (StatusBadge, Pill, RollStatusBadge, TransferList), ratchet `chip_custom` gudang 117 → 89 |
| **B1 UI-08** / B1b (HP: "semua pil oranye termasuk Ditolak QC") | Kartu tugas HP = `StatusBadge` ranah `task_hp`: eskalasi bahaya, menunggu/ditolak QC netral (FIX-2), berjalan info, menunggu perhatian | jest mobileShell (lulus), statik |
| **B3b INP-15 / G-OUT-01** (P3) — ≥ 30 titik tanggal tanpa WIB | `fmtTime` RFID (dipakai 23× + antrean periksa D2) → `formatDateTime`; `formatDate` stok, `shortDate*` lot, `localTs` SPK → WIB; `toLocaleString` tanpa zona di LoadingCheck, RollJourney, RollGradePanel ×2, U300PassageList ×2, Eskalasi ×3, ATP, SO tertunda, riwayat beli, HP pindai; `.slice(0,10|16)` atas ISO di Opname ×2, Pendaftaran ×3, Pengecualian terima transfer | jest (formatter WIB: 22.30 UTC → "10 Nov 2026, 05.30 WIB"; fmtTime/shortDateTime/localTs ikut), ratchet `date_no_wib` gudang+HP 24 → 0 |
| **B3b INP-16 / G-OUT-02** · **B1 UI-25** · **B1 UI-17** | ±45 cadangan id mentah → label ("Gudang tanpa nama", "Produk tanpa nama", "PT tanpa nama", "tanpa kode", `entityShortFromCtx`, …): HP gudang (14), Antrean QC, buku mutasi + CSV mutasi, kelompok roll, struktur/okupansi bin, aturan rak, Lokasi Rak, tugas keluar, pick list, transfer, master gudang, lintasan gerbang, antrean printer & verifikasi cetak, sesi U300, lot (gudang/bin/roll), SO tertunda, riwayat beli, pendaftaran (zona/rak), hitung roll, multi-bucket, label antrean offline HP | ratchet `id_fallback` gudang+HP 61 → 3 (sisa: nilai zona/bin perangkat RFID & kunci) |
| **B1 UI-33** — guardrail entity_label merah | `RegistrationDetail.jsx` `{g.owner_entity_id}` → `entityShortFromCtx(...)` | `verify_entity_label`: 2 → 1 pelanggaran (sisa `services/docEntityRegistry.js:14`, bukan layar FIX-8) |
| **B1 UI-15** — hampir tidak ada urut di daftar gudang | Transfer: pilihan "Urut" (terbaru/terlama/nomor/status), ikut tampilan tersimpan & berkas Unduh | jest (tampilan tersimpan mengirim `sort`) |
| **K-B4-12** — tampilan tersimpan | §5 API, §3 layar | pytest `test_fix8_saved_views.py` (19 uji), jest (pulih bawaan, `*`, simpan tanpa kunci cakupan, kolom) |

## 3. Layar WMS-RFID yang diubah (tampilan)

| Layar | StatusBadge | EmptyState / memuat | WIB | id mentah | DocNumber | Tampilan tersimpan |
|---|---|---|---|---|---|---|
| Stok › Roll (`InventoryStockView`, `RollsTable`) | ✓ | ✓ (memuat/kosong/saringan/galat) | ✓ (mutasi) | ✓ | — | ✓ saringan + mode + 7 kolom |
| Stok › Kelompok roll · Saldo · Mutasi | ✓ | — | ✓ | ✓ | — | (mode Kelompok) |
| Transfer (`TransferManagement`, `TransferList`, detail) | ✓ | ✓ | ✓ (pengecualian terima) | ✓ | ✓ | ✓ saringan + urut + 3 kolom |
| Barang Keluar (`OutboundScanInterface`) | ✓ | ✓ | — | ✓ | ✓ (SO) | ✓ status, gudang, jenis |
| Kedatangan GRN (daftar, detail, stepper) | ✓ | ✓ | — | — | ✓ | — |
| Tugas barang masuk (mode lama) | ✓ | — | — | — | — | — |
| Perintah Simpan ke Rak | ✓ | ✓ | — | — | ✓ | — |
| Antrean QC · SPK inspeksi (daftar, rincian, baris, pemilih grade) · Inspeksi roll | ✓ | ✓ (403 grade) | ✓ (localTs) | ✓ | — | — |
| Opname · Pendaftaran awal | ✓ | ✓ | ✓ | ✓ (UI-33) | — | — |
| Lot & Silsilah (daftar, rincian, aksi, silsilah) | ✓ | ✓ (pager) | ✓ | ✓ | — | — |
| Data Gudang · Lokasi Rak · struktur bin | ✓ | ✓ (KPI "…") | — | ✓ | — | — |
| RFID: tag, lokasi, perangkat, monitor gerbang, lintasan, U300, opname RFID, cetak & verifikasi, keamanan, antrean printer | ✓ (`Pill`) | ✓ | ✓ (`fmtTime`) | ✓ | — | — |
| HP gudang (Masuk/Keluar/Sample/Pindai/Belum Tag) | ✓ | ✓ (403/galat) | ✓ | ✓ | — | — |
| Pengiriman (daftar, riwayat) · Eskalasi · Retur antar-PT · Analitik/ATP/SO tertunda | ✓ | ✓ | ✓ | ✓ | — | — |

## 4. Perubahan perilaku untuk pengguna

1. **Lencana status** di layar gudang/RFID/HP kini satu rupa: ikon + teks + warna lembut AA. Warna mengikuti arti, bukan
   layar: menunggu = jingga tua, berjalan = biru, selesai = hijau, ditolak/gagal = merah, draf/dibatalkan = abu (dengan ikon
   larangan), kategori (dipesan, antar-PT, sampel) = ungu. Beberapa warna berubah (mis. "Dibatalkan" transfer/GRN abu — dulu
   sebagian merah; GRN "Ditutup" hijau). **Label tidak berubah.**
2. **Saat memuat** layar menulis "Memuat …" (KPI Data Gudang "…") — tidak lagi "0", "Belum ada …", "Tidak ada …" sesaat.
3. **Tidak berhak** (403) kini tertulis "Anda tidak punya akses ke … — ini bukan daftar kosong" (skor mitra makloon untuk
   Finance; petugas gudang di pemilih grade inspeksi melihat catatan alasan, bukan pilihan kosong). Galat lain: kalimat galat
   + "Coba lagi"; saringan tanpa hasil: "Tidak ada … yang cocok" + **Reset saringan**.
4. **Tanggal/jam** gudang/RFID/HP: "10 Nov 2026 05.30 WIB" (dulu zona perangkat, sebagian tanpa tahun/"WIB", sebagian ISO
   UTC yang terpotong) — kolom waktu RFID sedikit lebih lebar.
5. **Id mentah** tidak lagi tampil: teks "Gudang tanpa nama"/"Produk tanpa nama"/"tanpa kode"/nama PT.
6. **Nomor dokumen** di GRN, transfer, tugas keluar, PA: lencana kecil kode PT + nomor (`[KSC] PA00012`).
7. **Detail GRN**: bilah "← Kembali ke daftar Kedatangan" (dulu ikon kecil), "Batalkan" tombol merah terpisah di ujung kanan.
8. **Pager** semua tabel sisi-klien (juga layar non-gudang yang memakai `KNPager`/`PagedRows`: SDM, keuangan, harga, dsb.)
   kini bergaya `PaginationBar`: "Menampilkan 1–25 dari N", Sebelumnya/Berikutnya (+ halaman pertama/terakhir bila > 2 halaman).
9. **Kotak cari** Stok, Transfer, Barang Keluar memakai kotak baku (ikon, tombol hapus berlabel).
10. **Baru: "Tampilan: … ▾"** di Stok › Roll, Transfer, Barang Keluar — simpan kombinasi saringan/urut/kolom, jadikan bawaan
    (dipulihkan saat membuka daftar), admin bisa membagikan ke peran/PT. **Transfer** punya pilihan **Urut**; tabel **Roll**
    punya pilihan **Kolom**. Pilihan lokasi kerja & PT tetap dari bilah "Lokasi: … ▾"/pemilih PT, tidak ikut tampilan.

## 5. API & data baru

* `GET /api/saved-views?list_key=` · `POST /api/saved-views` · `PUT|DELETE /api/saved-views/{id}` (`routers/saved_views.py`,
  `services/saved_view_service.py`). Model `extra="forbid"`; izin = izin lihat daftar (`product.view` / `transfer.view` /
  `wms.view`); audit `saved_view.create|update|delete`.
* Koleksi **`saved_views`** — terdaftar di `ENTITY_REGISTRY.md` (tabel cepat + bagian rinci), `entity_scope.USER_SCOPED_COLLECTIONS`,
  index `(list_key, owner_user_id)` & `id` (`indexes.py`), pagar tulis "Semua Entitas" (S) `entity_write_guard.GROUP_LEVEL_EXACT`.
* Whitelist isi per daftar (`LISTS`): kunci cakupan (`entity_id`, `owner_entity_id`, `location_view`, `site_id`, `scope`, …) → 400
  dengan pesan; kunci tak dikenal → 400; nilai ≤ 200 huruf, daftar ≤ 50, isi ≤ 4 KB; ≤ 30 tampilan per pengguna per daftar.
* Berbagi: hanya `admin`; peran harus terdaftar (`role_registry`); PT tujuan ⊆ PT yang dibaca admin itu; penerima = peran cocok
  DAN PT yang ia baca beririsan; tampilan bersama hanya diubah/dihapus admin; tampilan pribadi orang lain → 404.

## 6. Keputusan implementer (di luar keputusan koordinator) + alasan

- **K8-1 — Satu sumber kosakata = `utils/statusVocab.js`.** Label 13 ranah gudang/RFID dipindah 1:1 dari peta di berkas fitur;
  berkas lama mengekspor ulang bentuk lamanya (`ROLL_STATUS_META`, `PA_STATUS` [nada, label], `STATUS` GRN, `INS_STATUS_LABEL`,
  `JOB_STATUS`, `STATUS_LABEL` pengiriman/pendaftaran) supaya pemakai lain & uji tidak pecah. Peta umum `DOC_STATUS_LABEL` tetap
  cadangan. Alasan: satu tempat untuk label + nada + ikon tanpa mengganti istilah (K-13).
- **K8-2 — Aturan nada** (B4 §3.9): "dibatalkan" = netral + ikon larangan (bukan merah — tidak perlu tindakan); "ditolak/gagal/
  rusak" = bahaya; FIX-2 tetap: tugas HP menunggu/ditolak QC = netral.
- **K8-3 — Pembungkus lama dipertahankan** (`Pill`, `RollStatusBadge`, `QcStatusBadge`, `TaskBadge`, `Badge`, `GrnStatusBadge`,
  `LotStatusPill`) dan merender `StatusBadge` — tidak mengganti ratusan pemakaian sekaligus; ratchet `chip_custom` menghitung
  `<Pill>`/`status-pill` mentah sebagai pola lama (tidak boleh bertambah).
- **K8-4 — Galat MUAT daftar** tampil di badan daftar (`EmptyState` galat/tanpa izin + Coba lagi); galat AKSI tetap bilah
  `ErrorNotice` (keputusan P5). Beberapa layar tetap juga menampilkan bilah galat lama di atas (tidak dihapus).
- **K8-5 — `KNPager` tetap tersembunyi bila hanya satu halaman** (perilaku lama); tombol pertama/terakhir hanya bila > 2 halaman.
- **K8-6 — Skema nomor = tampilan saja** (UI-58 "chip PT di samping nomor"): kode PT dari awalan nomor atau `entity_id`/
  `work_entity_id` dokumen lewat konteks login; PT tak dikenal → tanpa lencana. Teks elemen = nomor tersimpan.
- **K8-7 — Pola detail per jenis layar** (B4 §3.7 + UI-60): dokumen **kerja bertahap** (GRN, opname, pendaftaran, perbaikan,
  retur, makloon) = halaman detail sebaris dengan `DetailHeader` baku (kerja pindai/hitung panjang tidak cocok di pop-up; GRN di
  wilayah FIX-6); **rincian baca/aksi ringkas** (transfer, SPK, lot, pengiriman) = `DetailModal`; **rincian roll** = pop-up/panel
  roll. Dicatat di KN_37 §8b.
- **K8-8 — Tampilan tersimpan:** 3 daftar utama (Roll, Transfer, Barang Keluar). "Urut" hanya Transfer (di atas transfer yang sudah
  dimuat — sama dengan saringan Jenis & cari layar itu); urut server daftar Roll = wilayah halaman server/performa (FIX-7), tidak
  disentuh. "Kolom" disimpan sebagai kunci kolom **yang disembunyikan**. Admin = peran `admin`. Bawaan pribadi menang atas bawaan
  bersama. Saringan gudang dari tampilan bersama yang bukan gudang pengguna diabaikan saat dipasang.
- **K8-9 — Baseline ratchet LAMA (font, hex, tombol, …) TIDAK dikencangkan** walau turun (font_lt12 6.937 → 6.915, hex 16.810 →
  16.732, btn_custom 784 → 781) — FIX-6/FIX-7 paralel menyentuh berkas yang sama; mengencangkan sekarang bisa membuat gabungan
  mereka merah. Koordinator menjalankan `--update` sesudah semua digabung. Baseline 4 metrik BARU = kondisi sesudah FIX-8.
- **K8-10 — `usePagedList` tidak diubah** (wilayah FIX-7); 403 dikenali dari teks server "Permission ditolak: …".
- **K8-11 — G-OUT-02 di `verify_ui_standard.py`** (metrik `id_fallback`, semua objek), bukan memperluas `verify_entity_label.py`
  (khusus nama PT) — satu infrastruktur ratchet per berkas.
- **K8-12 — `verify_list_export.py`:** berkas `__tests__/` tidak dipindai (uji memasang komponen, bukan layar daftar); `KNPager`
  masuk `DIBOLEHKAN` beralasan (pembungkus pager sisi-klien; Unduh dipasang di layar pemakai).
- **K8-13 — Lencana kategori (jenis transfer, sampel, mode kirim, asal lot)** memakai `StatusBadge tone=… icon="tag"`;
  `TaskTypeBadge` khusus (B4) belum dibuat.

## 7. Hasil uji & perbandingan regresi

**Lingkungan:** node `kn-tmp-fix8-fe` (`node:20`, salinan `frontend/src`, volume `kn-dev_fe_node_modules` **hanya-baca**);
stack `kn-tmp-fix8-mongo` (salinan `kn_test_trial_2026-11-08` → `test_database`, **dipulihkan ulang sebelum tiap putaran**) +
`kn-tmp-fix8-be` (kode FIX-8 di `/app`, kode `main` di `/app_base`). Stack bersama `kn-uji-*`/`kn-dev-*` tidak disentuh. Semua
`kn-tmp-fix8-*` dihapus sesudahnya. Catatan: Docker Desktop sempat macet ±15 menit di tengah pengerjaan (perintah `docker` tak
menjawab, lalu mesin dimulai ulang — bukan oleh paket ini); kontainer node dihidupkan lagi dan seluruh putaran Jest diulang.

| Putaran | Hasil |
|---|---|
| Jest `fix8StandarUi2.test.js` — **dasar `main`** (src main + berkas uji) | **suite GAGAL** (komponen/kosakata belum ada) — bukti merah |
| Jest `fix8StandarUi2.test.js` — FIX-8 | **25/25 lulus** |
| Jest PENUH — dasar `main` | 86 suite: 85 lulus + 1 gagal (suite FIX-8) · **604/604** uji lama lulus |
| Jest PENUH — FIX-8 | **86/86 suite · 629/629** (604 lama + 25 baru) — **0 gagal baru** (putaran akhir: lihat §7a) |
| ESLint 91 berkas FE yang berubah vs `main` | **0 error**, 36 peringatan — semuanya "Unused eslint-disable directive" (pola repo yang sudah ada) |
| pytest set regresi (registry koleksi, katalog akses fe03, FIX-1 cakupan, FIX-4 ekspor, FIX-5 performa, FIX-8) — **dasar** | **82 lulus · 20 gagal** = 19 uji FIX-8 (endpoint belum ada — bukti merah) + `test_registry_ai_collections` |
| idem — **FIX-8** | **101 lulus · 1 gagal** = `test_registry_ai_collections::test_every_ai_collection_is_registered` (sama di dasar: `ai_action_proposals`, `ai_insights` belum terdaftar — bukan FIX-8) |
| Gagal **hanya** di FIX-8 | **0** |
| `python -m entity_write_guard --self-test` (dasar & FIX-8) | HIJAU di keduanya |
| Server FIX-8 | mulai tanpa galat; index `kn_list_key_1__owner_user_id_1`, `kn_id_1` terbuat; uji membersihkan `saved_views` (0 dokumen sisa) |

### 7a. Putaran akhir
Sesudah perubahan terakhir (`docEntityId`, penjaga INV-UI-07) Jest penuh diulang pada kode akhir: **86/86 suite · 629/629 uji lulus**
(sama dengan putaran pertama). ESLint diulang pada 91 berkas yang berubah vs `main`: 0 error. pytest dijalankan pada kode akhir
backend (tidak berubah sesudah `422c195`).

## 8. Guardrail

Baru/diperluas: **`verify_ui_standard.py`** (+ metrik `chip_custom`, `id_fallback`, `date_no_wib`, `empty_false`; cek keras G-UI-10;
`--init-missing`; self-test 20 → 26 kasus HIJAU) · **`verify_ui_contrast.py`** (+ 9 pasangan: 6 nada lencana, nomor dokumen, teks
keadaan kosong, kepala menu tampilan) · **`verify_list_export.py`** (K8-12).

Sensus (`verify_ui_standard.py --census [--ref main]`; "gudang" = `features/wms|rfid|inventory|inspections`, "HP" = `features/mobile`):

| Metrik | `main` total (gudang · HP) | FIX-8 total (gudang · HP) | Baseline baru |
|---|---:|---:|---|
| `chip_custom` (G-UI-06) | 594 (117 · 2) | **560 (89 · 1)** | `ui_chip_custom.json` 560 |
| `id_fallback` (G-OUT-02) | 221 (47 · 14) | **163 (3 · 0)** | `ui_id_fallback.json` 163 |
| `date_no_wib` (G-OUT-01) | 166 (22 · 2) | **139 (0 · 0)** | `ui_date_no_wib.json` 139 |
| `empty_false` (UI-49/50) | 322 (54 · 2) | **308 (42 · 2)** | `ui_empty_false.json` 308 |
| `font_lt12` | 6.935 (gudang 1.257) | 6.915 (1.238) | lama (tidak dikencangkan, K8-9) |
| `hex` / hex berbeda | 16.808 / 703 | 16.732 / 699 | lama |
| `btn_custom` | 784 | 781 | lama |

Sisa di luar gudang ("lain") sebagian besar layar penjualan/keuangan/SDM — dibekukan ratchet. `empty_false` adalah heuristik
statik (syarat `.length === 0` tanpa penjaga memuat + "Belum ada/Tidak ada" berikutnya, atau galat ditelan jadi `[]`); sisa 42 di
gudang kebanyakan bagian rincian sesudah data termuat (bukan kosong palsu) — ratchet mencegah bertambah.

Semua penjaga statik (kecuali `verify_state_machine`, tidak dijalankan sesuai larangan), `main` vs FIX-8 (host, `PYTHONUTF8=1`):

| Penjaga | `main` | FIX-8 |
|---|---|---|
| `verify_ui_standard` | PASS 4.316 cek | **PASS 5.692 cek** |
| `verify_ui_contrast` | PASS 58/58 | **PASS 67/67** |
| `verify_error_notice` | PASS 276 | PASS 277 |
| `verify_list_export` | PASS 21 | PASS 20 (berkas uji tak dipindai, KNPager beralasan) |
| `verify_entity_label` | MERAH 2 | MERAH **1** (sisa `services/docEntityRegistry.js:14` — sudah ada di `main`) |
| `verify_escape_layers` / `role_label` / `uom_vocab` | PASS | PASS (1.194 → 1.202 berkas) |
| `verify_auth_coverage` | MERAH 28 (1.727 cek) | MERAH 28 (1.731 cek — 4 endpoint baru tercakup) |
| `verify_qty_dual` | MERAH 28 | MERAH 28 |
| `verify_atomic_claim` 6 · `line_scope` 1 · `numeric_bounds` 3 · `page_tabs` 1 · `to_list_bound` 20 | MERAH | identik |
| `verify_no_secrets` | 0* | 8 temuan = berkas `test_reports/pytest/*.xml` yang ada di worktree tetapi tidak ikut arsip `main` yang saya pindai (*FIX-3b/FIX-4 mencatat 8 = 8) |
| `concurrency`, `cross_entity`, `home_kpi`, `nonfinancial_sweep`, `ref_unlink` | tidak jalan di host (modul DB/httpx tidak terpasang) | sama |
| lainnya (24 penjaga) | PASS | PASS (kode keluar identik) |

## 9. Berkas berisiko bentrok

- **FIX-7 (halaman server/performa daftar)** — saya hanya mengubah TAMPILAN di layar daftar yang sama: `wms/InventoryStockView.jsx`
  (kotak cari, `SavedViewsMenu`, prop RollsTable), `wms/inventory/RollsTable.jsx` (kolom opsional, baris keadaan, lencana),
  `wms/inventory/RollGroupView.jsx` (3 label), `wms/TransferManagement.jsx` (kotak cari, urut klien, tampilan), `wms/transfer/TransferList.jsx`,
  `wms/OutboundScanInterface.jsx` (kotak cari, keadaan, tampilan, DocNumber), `wms/PutawayOrdersPanel.jsx`, `wms/grn/GoodsReceiptsView.jsx`,
  RFID `GatePassageHistory`/`RfidSecurityPanel`/`RfidPrintVerifyPanel`/`CycleCountPanel`/`RfidGateMonitorView`; komponen
  `PaginationBar.jsx` (1 baris teks memuat), `KNPager.jsx`, `ResponsiveTable.jsx` (keadaan), `ListControls.jsx`/`ListPageParts.jsx`.
  `usePagedList.js` **tidak** disentuh. Bila FIX-7 memindah urut/saringan Transfer ke server, `sort` tampilan tersimpan cukup
  diteruskan ke parameter server (`sort` sudah dibaca `get_page_params`).
- **FIX-6 (GRN/retur/PO)** — tampilan saja: `wms/grn/GoodsReceiptsView.jsx`, `GrnDetail.jsx` (kepala detail), `GrnBits.jsx`,
  `grnApi.js` (`STATUS` diturunkan dari kosakata), `inspections/*` (lencana, pemilih grade, `inspectionsApi.INS_STATUS_LABEL`),
  `wms/RollInspectionModal.jsx`, `wms/inbound/InboundTaskPanel.jsx`, `finance/interco/IntercoReturnsPanel.jsx` + `IntercoView.jsx`
  (1 prop `loading`), `purchasing/makloon/MakloonPartnerScorePanel.jsx`. Layar retur/PR/makloon **tidak** disentuh.
- **Global**: `styles/standard.css` (ditambah di akhir), `utils/formatters.js` (+`formatTime`), `utils/entityLabel.js`
  (+`entityCodeFromCtx`), `components/DetailParts.jsx` (+`dangerActions`), `components/QcStatusBadge.jsx`; backend
  `server.py` (1 router), `entity_write_guard.py` (1 baris), `entity_scope.py` (1 koleksi), `indexes.py` (`saved_views`);
  `scripts/guardrails/verify_ui_standard.py`, `verify_ui_contrast.py`, `verify_list_export.py`, 4 baseline baru; `ENTITY_REGISTRY.md`,
  `KN_37`.
- Tidak diubah: logika bisnis, rumus stok, cakupan, alur GRN/retur/PO, endpoint daftar lama, `TRACKER.md`, `deploy/*`.

## 10. Sisa (tidak dikerjakan / butuh keputusan)

1. **Verifikasi visual** (desktop + 360/390 px) lencana, keadaan kosong, menu Tampilan di peramban — koordinator.
2. **UI-50 di luar batas berkas** (bukan layar WMS-RFID): POS `pos/PosStartGate.jsx:44` ("Belum ada pelanggan — buat pelanggan baru"
   saat memuat — **risiko pelanggan ganda**), Produk & Varian `catalog/CatalogWorkspace.jsx:61`, Antar Entitas
   `finance/interco/IntercoPanels.jsx:58`, Meja Admin Sample ("Tidak ada SO aktif"). Polanya tinggal memakai `EmptyState`/`listStateKind`.
3. **UI-58/UI-60 di layar retur/PR/makloon** (wilayah FIX-6): pasang `DocNumber` pada nomor `PRET-`/`SRET-`/`PR-` dan pindahkan
   "Tolak"/"Batalkan Pesanan" ke `DetailHeader dangerActions`.
4. **G-OUT-01 di luar gudang**: `sales/ReturnTimelinePanel.jsx:31`, `purchasing/MakloonPartialReceipts.jsx:7` (dan 139 titik "lain" yang
   dibekukan ratchet); nama sesi opname bawaan UTC di server `cycle_count.py:69`.
5. `StatusPill` (`components/CoreWidgets.jsx`, 47 berkas non-gudang) masih mencetak kode status dengan spasi — kandidat dilebur ke
   `StatusBadge` (perubahan tampilan lintas modul, butuh persetujuan); `TaskTypeBadge` (B4 §3.9).
6. Tampilan tersimpan untuk daftar lain (GRN, PA, tag RFID, opname) dan **urut server** daftar Roll (bersama FIX-7).
7. Migrasi huruf 12 px layar gudang (1.238 pemakaian < 12 px dibekukan), CSV Pusat Export klasik masih koma, lebar CSS C72 (K-B4-04),
   Unduh di berkas PREP-H & antrean periksa gate V2 (sisa FIX-4).
8. Penjaga merah lama yang bukan FIX-8: `test_registry_ai_collections` (`ai_action_proposals`, `ai_insights`), `verify_entity_label`
   `docEntityRegistry.js:14`, `auth_coverage` 28, `qty_dual` 28, dll. (tabel §8).
9. Kencangkan baseline ratchet lama (`--update`) sesudah FIX-6/7/8 digabung (K8-9).

---

### Ringkasan untuk koordinator
FIX-8 selesai di worktree `worktree-agent-a25cd57f6c540a261` (commit `422c195`, `32ad774` + laporan; **belum** di-push/merge, TRACKER
tidak disentuh). Isi: `StatusBadge` + kosakata status tunggal (`utils/statusVocab.js`, istilah tidak berubah), `EmptyState` 5 keadaan
(403 ≠ kosong, memuat ≠ 0), pager/kotak cari/tab status dilebur jadi satu, waktu WIB lewat formatter tunggal, cadangan id mentah
diganti label, `DocNumber` `[PT] NOMOR` (tampilan saja), `DetailHeader dangerActions` (GRN), dan **tampilan tersimpan** (API
`/api/saved-views` + koleksi `saved_views`, terdaftar; cakupan PT/lokasi tidak pernah disimpan; berbagi peran/PT hanya admin) di
Stok › Roll, Transfer, Barang Keluar. Temuan ditutup: B1b UI-49, UI-50 (layar WMS-RFID), UI-58 & UI-60 (layar gudang), pager 3 gaya,
B1 UI-08/15/17/25/33, B3b INP-15/G-OUT-01 & INP-16/G-OUT-02 (gudang+HP), K-B4-12. Uji: Jest FIX-8 25/25 (suite merah di `main`),
Jest penuh 629/629 (main 604/604 + suite FIX-8 gagal), pytest regresi 101 lulus/1 gagal lama (main 82/20: 19 FIX-8 + 1 lama yang
sama) — **0 gagal baru**; ESLint 0 error; `verify_ui_standard` PASS (4 ratchet baru + G-UI-10), `verify_ui_contrast` 67/67,
`verify_entity_label` 2 → 1, penjaga lain kode keluar identik dengan `main`. Perlu tindakan koordinator: verifikasi visual peramban;
perhatikan bentrok tampilan dengan FIX-7 (layar daftar Stok/Transfer/Keluar/PA/RFID, `RollsTable`, `ResponsiveTable`, `KNPager`) dan
FIX-6 (GRN, inspeksi, pemilih grade); `--update` baseline ratchet lama sesudah semua digabung; sisa UI-50 POS/Produk (risiko pelanggan
ganda) di luar batas berkas paket ini.
