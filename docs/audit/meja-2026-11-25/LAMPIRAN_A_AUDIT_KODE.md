# Audit kode layar "Meja" — UX padat, detail tak terbuka, kerja harus pindah layar

- Repo: `/home/user/KNHOST`, HEAD `db0a20f` (25 Nov 2026), pohon kerja bersih. Audit baca saja: kode tidak diubah dan aplikasi tidak dijalankan.
  Satu foto acuan dipakai untuk mencocokkan bentuk layar: `docs/blueprint/masukan-pemilik/2026-11-16_pilot-pola/sesudah_meja-admin-sales-1366.png`.
- Ukuran yang dipakai: `docs/blueprint/04_POLA_UI.md` (pola Meja §2.B, ukuran §3, larangan §4), `docs/blueprint/02_STANDAR.md` §4 (L2 istilah
  "PT", L4 layar uang) dan skala huruf KN_37 (12/13/14/16/20/24 px, minimum 12 px; token `text-fs-*` di `frontend/tailwind.config.js:12-20`).
- Keluhan pemilik dipetakan ke nomor: **K1** padat/bertumpuk · **K2** klik baris tidak membuka rincian padahal teks terpotong · **K3** kerja di tempat
  (inline/pop-up) tanpa pindah layar · **K4** isi kurang lengkap · **K5** huruf tidak konsisten, tebal/besar di tempat yang salah · **K6** duplikasi.

Isi: §0 cakupan · §1 kerangka bersama (dipakai semua meja) · §2 per meja (A–K) · §3 lintas meja: konsistensi komponen, 10 masalah
terbesar, pola pop-up yang bisa dipakai ulang · §4 keputusan pemilik yang dibutuhkan.

---

## 0. Cakupan — daftar layar "Meja"

| # | Layar (judul yang tampil) | Komponen | Endpoint | Siapa yang melihat |
|---|---|---|---|---|
| A | **Meja Admin Sales** | `features/sales_admin/SalesAdminDesk.jsx` | `GET /api/sales-admin/desk` (`order.confirm`, `routers/work_desks.py:97-102`) + `/desks/so-tracker` + `/sales/keep-pending` + `/customers` | `sales_admin` (ROLE_NAV `config/roles.js:205`), admin lewat grup "Meja Peran" (`config/navStructure.js:143-152`) |
| B | **Meja Saya** (judul kartu dari server: Meja Admin / Meja Manajer / Meja Sales / Meja Operator Gudang / Meja Desainer / Meja Pengemudi, `backend/services/role_desk_service.py:35-36`) | `features/desks/RoleDesk.jsx` (`desk="me"`) | `GET /api/desks/me` (login saja; jenis meja dari kategori peran, antrean disaring izin, `work_desks.py:255-267`, `role_desk_service.py:18-31,308-330`) | admin, manager, sales, warehouse, designer, driver (`navStructure.js:87-94`); dicabut dari sales_admin & warehouse_admin (`roles.js:238-240,350`) |
| C | **Meja MD** | `RoleDesk.jsx` (`desk="md"`) | `GET /api/md/desk` (`design_request.view`, `work_desks.py:215-220`) | `md` (`roles.js:318`), admin |
| D | **Meja Gudang** / "Meja Admin Gudang" | `RoleDesk.jsx` (`desk="warehouse_admin"`) + `features/home/ReturnDeskSummaryCard.jsx` | `GET /api/warehouse-admin/desk` (`wms.view`, `work_desks.py:223-228`) + `/return-dispositions/summary` | `warehouse_admin` (`roles.js:342`), admin |
| E | **Keuangan › Beranda Keuangan › Perlu Tindakan** (dulu "Meja Finance") | `features/finance/FinanceDesk.jsx` | `GET /api/finance/desk` (`payment_variance.decide`, `work_desks.py:234-249`) + `/home/finance` + `/finance/posting-failures` | finance (beranda peran, `config/navMeta.js:257`), admin/manager (tab hub `config/hubTabs.js:261-264`); tiap kelompok berpagar izin `PERLU_TINDAKAN` (`FinanceDesk.jsx:42-68`) |
| F | **Meja Sample** / "Meja Admin Sample" | `features/samples/SampleAdminDesk.jsx` | `GET /api/sample-orders/desk` (`sample_order.view`, `backend/routers/sample_orders.py:151-185`) | `sample_admin` (`roles.js:356`), admin |
| G | **Meja Cutting** (tab di Pesanan Sample) | `features/samples/CuttingDesk.jsx` dalam `SampleOrdersView.jsx:47,166-174` | `GET /api/cutting/desk` (`sample_order.view`; terima = `sample_order.cutting_receive`, `routers/cutting.py:47-55`) | menu Pesanan Sample: admin, sales, manager (`navStructure.js:169`), sample_admin, finance (`roles.js:279,357`) |
| H | **HP Admin Sales › tab "Meja"** | `features/sales/mobile/MobileSalesApp.jsx:71-74` → `MobileSalesAdminDesk.jsx` | sama dengan A | peran berberanda `sales-admin-desk` (`features/mobile/mobileLayout.js:32`) |
| I | **HP MD › tab "Meja"** | `MobileMdApp.jsx:24-29,128-133` → `MobileMdViews.jsx:35-95` (`MobileMdDesk`) | sama dengan C | `md` |
| J | *Kredit & Plafon · Daftar Kerja Kredit* (meja kredit, pembanding) | `features/finance/CreditDeskView.jsx` + `creditDeskParts.jsx` | `GET /api/credit-desk` (+`/summary`) | `credit_profile.view` |
| K | Kartu **"Meja retur internal"** (disisipkan di atas meja D dan E) | `ReturnDeskSummaryCard.jsx` | `/return-dispositions/summary` | semua yang membuka admin-home, manager-home, finance-desk, warehouse-admin-desk (`AppViewRouter.jsx:254-256`) |

Disebut "Meja" tetapi bukan layar meja (hanya didaftar, tidak dibedah): grup sidebar **"Meja Peran"** (admin, `navStructure.js:143-152`);
tombol HP **"Meja QC · SPK inspeksi & random check scan"** yang membuka layar desktop Inspeksi (`features/mobile/MobileOpsApp.jsx:199`);
**"Meja Insentif"** hanya ada di komentar (`hubTabs.js:230-240`, menunya "Kinerja & Insentif"); ringkasan HP Admin Sample yang membaca
antrean meja F (`features/mobile/MobileRoleSummary.jsx:40-75`, tombol "Buka Meja Admin Sample"). Daftar kerja lain yang mirip meja tapi tidak berjudul
"Meja": *Penagihan & Penerimaan · Daftar Kerja Penagihan* (`features/crm/CollectionWorklist.jsx`).

**Jumlah meja yang dibedah: 11 (A–K).**

---

## 1. Kerangka bersama (dipakai hampir semua meja desktop)

### 1.1 Kepala aplikasi — tiga kali judul sebelum isi
- `TopBar` (`components/CoreWidgets.jsx:335-355`): breadcrumb "BERANDA › {jejak menu} › {PT}" (10,5 px tebal huruf besar, `styles/layout.css:339`)
  + `h1.page-title` 17 px Outfit 700 (`layout.css:341`) dari `PAGE_META` (`config/navMeta.js:23-30`). Ada tombol muat ulang global
  (`CoreWidgets.jsx:368-370`).
- Setiap meja lalu menggambar **kepala sendiri** di `section-head`: ikon + `kicker` (12 px 700 huruf besar biru, `styles/components.css:293`) + `h2`
  (14 px Outfit 700, `components.css:289`) + tombol muat ulang sendiri. Akibatnya judul meja muncul 3–4 kali (lihat tiap meja).

### 1.2 `DeskQueueCard` — kartu antrean bersama (`features/sales_admin/DeskQueueCard.jsx`)
Dipakai A, B, C, D, E, F (tidak dipakai G, H, I). Susunan satu kartu (dari atas):
1. Kepala (`:69-99`): ikon 32 px · `h3` judul antrean **14 px tebal** (`:75`) · lencana jumlah 12 px tebal (`:76-80`) · lencana "tertua n hari" 12 px tebal
   (`:81-87`) · `hint` satu baris terpotong (`:89-91`) · di kanan label nilai **huruf besar 12 px semibold** (mis. "TOTAL (TERMASUK PPN)") + total 13 px tebal (`:93-98`).
2. Bilah saring `TableFilterBar` (`:121-128`, `components/TableFilter.jsx:36-60`): cari + Status ▾ (hanya bila >1 status) + Urut ▾ (selalu, walau 1 baris).
3. Baris 5 per halaman (`:129-137`), pager (`:140`), catatan "Menampilkan n tertua dari count — … buka layar daftarnya" (`:142-146`, **tanpa tautan**).
4. Satu baris (`QueueRow`, `:152-204`), grid `sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)_auto_auto]` (`:164`):
   nomor **13 px tebal biru** (`:167`) + judul **13 px semibold** (`:169`) | lencana status 12 px semibold + revisi + keterangan 12 px (`:173-184`) / baris
   "menunggu n hari · masuk tgl" (`:185-191`) | nilai 13 px semibold (`:193-196`) | tombol `btn-secondary btn-xs` (`:197-201`; `.btn-xs` ditandai "usang: pakai
   .btn-sm" di `styles/purchasing.css:38`).

Temuan pada komponen ini (berlaku ke semua meja pemakainya):
- **K2 — baris tidak bisa diklik.** `div` baris hanya punya `hover:bg-kn-neutral-soft` (`:164`) dan nomor berwarna aksi (`:167`) — tampak seperti tautan,
  tetapi tidak ada `onClick`. Satu-satunya pemicu adalah tombol di kolom kanan (`:197-201`), yang `title`-nya berisi **hint antrean**, bukan rincian baris (`:199`).
- **K2 — pemotongan tanpa jalan melihat utuh:** judul baris `truncate` **tanpa `title`** (`:169`); keterangan `truncate` hanya dengan `title` (hover; tidak
  berlaku di layar sentuh) (`:183`); baris waktu `truncate whitespace-nowrap` dengan `title="Umur baris ini"` (bukan isinya) (`:185-186`). Dengan kartu dua kolom
  (`xl:grid-cols-2`) lebar kolom dokumen ±150 px dan kolom keterangan ±220 px — di foto pilot hampir semua keterangan terpotong ("Medan · Ayu Per…", "masuk ±…").
- **K6 — angka berulang di kepala kartu:** antrean `value_kind="count"` menulis jumlah di lencana (`:79`) **dan** "n dokumen" di kolom nilai (`:63-65`). Keduanya
  bahkan bisa berbeda: lencana = `queue.count` (seluruh antrean), teks kanan = `rows.length` (maks. 200 baris dikirim, `ROW_LIMIT` di
  `backend/services/work_desk_service.py:37`).
- **K1 — kartu kosong setinggi tetangganya:** `h-full` + isi `flex-1` (`:68,116-120`) membuat kartu "Antrean ini bersih" ikut setinggi kartu sebelahnya yang
  berisi 5 baris (terlihat di foto pilot: 9 kartu kosong besar di Meja Admin Sales).
- **K5 — lima titik tebal dalam satu baris** (nomor 700, judul 600, lencana 600, umur 600, nilai 600) dan judul kartu (14 px 700) setara `h2` halaman (14 px 700):
  tidak ada hierarki.
- Pengurutan "Nilai terbesar" tetap ditawarkan untuk antrean jumlah yang kolom nilainya kosong (`:22-26`, `:155-159`).
- "menunggu n hari · masuk ± tgl" memakai `age_days` apa adanya. Untuk antrean jatuh tempo `age_days` = **hari keterlambatan**, bukan lama menunggu, dan tanpa
  `at` sehingga tanggal masuk ditebak (`work_desk_service.py:284-288,551-552`; `DeskQueueCard.jsx:188-190`).

### 1.3 `SoTrackerCard` — tabel "Pelacak SO aktif" (`features/sales_admin/SoTrackerCard.jsx`)
Dipakai A, B (bila `order.view`), C, D, E, F. Kepala h2 + 2 lencana 10,5 px + **paragraf penjelasan tetap** (`:60`) + bilah saring (`:62`) + tabel `min-w-[760px]`
11,5 px, kepala kolom 10,5 px, lencana diam **9 px** (`:105`), "oleh {peran}" 10 px (`:102`). Baris `hover` tetapi tidak bisa diklik (`:88`); baris yang bukan
wewenang meja hanya bertulisan "Menunggu {peran}" — **tidak ada cara membuka SO-nya sama sekali** (`:111-113`). Pelanggan · sales `max-w-[200px] truncate`
tanpa `title` (`:91`). API membawa `age_days`, `entity_id` tidak dikirim (`backend/services/so_tracker_service.py:114-124`). Warna hex mentah (24 kali).

### 1.4 Kartu angka lokal `Metric`
Tiga salinan identik: `RoleDesk.jsx:172-182`, `SalesAdminDesk.jsx:203-215`, `SampleAdminDesk.jsx:101-108` (+ versi lain di `SampleOrdersView.jsx:314-319`).
Label 10 px tebal huruf besar, nilai 15 px tebal — padahal kelas `.metric-card` yang dipakainya menetapkan label 12 px / nilai 20 px (`components.css:219-220`)
dan bersifat **`cursor: pointer` + terangkat saat hover** (`components.css:207,211`). Kartu angka meja berupa `div` tanpa `onClick`: **tampak bisa diklik,
tidak terjadi apa-apa** (melanggar `04_POLA_UI.md:24-25,92`). Komponen baku `MetricRow` yang menerima `onClick/active` (`components/ListPageParts.jsx:78-90`)
tidak dipakai meja mana pun.

### 1.5 Navigasi dari baris
`workDeskApi.js:241-244` menuliskan filosofi: *"Meja kerja bukan tempat mengerjakan SEGALA hal; ia tempat MENEMUKAN pekerjaan lalu melompat ke layar yang
memang menanganinya."* Peta tujuan per jenis dokumen: `ROW_TARGET` (`:245-252`), `FINANCE_QUEUE_TARGET` (`:255-271`), `ROLE_DESK_TARGET` (`:274-295`),
`rowLink` (`:319-343`). `openDocument` menyimpan asal sehingga layar tujuan punya "← Kembali ke …" (`hooks/useAppNavigation.js:95-117,120-127`), tetapi
saat kembali meja **dimuat ulang dari nol**: cari/saring/halaman tiap kartu (state lokal `useTableFilter`/`usePagedRows`) dan posisi gulir hilang.
Tipe yang tidak dikenal jatuh ke daftar Pesanan (`ROW_TARGET.sales_order`, `:328,332`).

### 1.6 Data yang dibawa server per baris
`_row` (`work_desk_service.py:106-116`): `ref_type, ref_id, number, title, subtitle, value, age_days, badge, action, action_kind, at` + `extra` disebar ke baris.
**Tidak ada `entity_id`/nama PT** — di mode "Semua PT" tidak satu baris pun menyebut PT-nya. `generated_at` (waktu susun) dikirim tetapi tidak pernah ditampilkan.

---

## 2. Per meja

### A. Meja Admin Sales (desktop)

**Berkas:** `features/sales_admin/SalesAdminDesk.jsx` (+ `DeskQueueCard`, `SoTrackerCard`, `KeepPendingPanel.jsx`, `CustomerGradeRulesCard.jsx`,
`VerifyOrderDialog.jsx`, `FulfillmentDecisionDialog.jsx`, `OrderPreviewCard.jsx`) · backend `work_desk_service.sales_admin_desk` (`:169-411`).

**Urutan blok di halaman (K1)** — sebelum kartu antrean pertama ada empat blok:
1. Kartu kepala (`:98-139`): kicker "Admin Sales" + h2 "Meja Admin Sales" + muat ulang · paragraf alur 4 baris 11,5 px (`:111-116`) · 3 kartu angka (`:118-126`)
   · kotak "Bukan wewenang meja ini — ada di Meja Finance" (`:128-138`).
2. `SoTrackerCard` (`:142-148`) — tabel semua SO aktif, 5 baris + pager.
3. `KeepPendingPanel` satu baris penuh (`:151-152`) — 3 chip tab + cari + paragraf penjelasan + **seluruh** daftar tanpa paginasi (`KeepPendingPanel.jsx:68-125`).
4. `CustomerGradeRulesCard` (`:153`) — **form data master** (pilih pelanggan, grade minimum, prioritas, BS, catatan, Simpan) di tengah layar kerja, memuat
   seluruh `/customers` setiap meja dibuka (`CustomerGradeRulesCard.jsx:20-24`). Melanggar `04_POLA_UI.md:95`.
5. Grid antrean (`:169-174`) — 13 kartu (+1 bila ada OD siap kirim), semuanya tampil termasuk yang kosong, urutan server.
Halaman ±3.146 px pada 1366 px (`masukan-pemilik/2026-11-16_PILOT_POLA.md` tabel §1).

**Antrean** (`work_desk_service.py`; semua kartu memakai baris §1.2):

| id · judul | Keterangan (hint) | Baris menampilkan | Aksi tombol | Data API yang tidak tampil |
|---|---|---|---|---|
| `perlu_verifikasi` · Perlu diperiksa & dilepas ke gudang (`:189-200`) | periksa kelengkapan lalu lepas | SO · pelanggan \| status + "kota · sales · keadaan" \| total | **Periksa & lepas → pop-up `VerifyOrderDialog`** (data pesanan + daftar periksa, `SalesAdminDesk.jsx:74,178-187`) | `booking_until` (batas cadangan, `:199`) |
| `siap_dikonfirmasi` · Ditahan — siap dilepas (`:204-212`) | ditahan Admin Sales | SO · pelanggan \| "Ditahan {oleh} · keadaan" | **Lepas ke gudang → langsung dieksekusi tanpa konfirmasi** (`SalesAdminDesk.jsx:58-66,76`) | — |
| `menunggu_manajer` · Menunggu keputusan manajer (`:217-227`) | pantau | SO · pelanggan \| teks tetap "Sudah diperiksa · dilepas otomatis sesudah ACC" | Lihat → daftar Pesanan | `booking_until` |
| `siap_cetak_dokumen` · Siap cetak Surat Jalan / Invoice (`:231-242`) | | SO · pelanggan \| status + kota · sales | **"Cetak" → hanya pindah ke daftar Pesanan** (label menjanjikan cetak) | — |
| `perlu_dipenuhi` · Perlu dipenuhi (kurang stok) (`:257-273`) | pilih satu: PT lain/reorder/tahan | SO · pelanggan \| 2 baris barang pertama "X kurang n yard" \| qty | **Putuskan pemenuhan → pop-up `FulfillmentDecisionDialog`** (`:75,189-198`) | `extra.lines` lengkap (hanya `[:2]` masuk keterangan, `:264`) |
| `jatuh_tempo` · Jatuh tempo & pengingat (`:279-290`) | "Pencatatan uangnya di Meja Finance" (nama usang) | SO · pelanggan \| "lewat n hari" \| sisa | Follow-up → daftar Pesanan | `at` tidak ada → "masuk ±" tebakan; umur = hari telat |
| `pelanggan_tanpa_sales` (`:300-306`) | | kode · nama \| kota \| **"1"** per baris (qty bernilai 1, label "Pelanggan") | Tetapkan sales → Pelanggan & CRM | — |
| `retur` · Retur menunggu proses dokumen (`:315-324`) | | SRET · pelanggan \| "atas SO · n baris" \| nilai klaim | Proses → Retur | `return_type` |
| `retur_tukar` (`:333-340`) | | SRET · pelanggan \| atas SO | Buat pengganti → Retur | — |
| `permintaan_internal` (`:348-358`) | | PIN · **alasan dipotong server 70 huruf** (`:352`) | Tindak → Permintaan Internal | `items`, `requested_by_name` |
| `od_acc_pelanggan`, `od_kunci_harga`, `od_siap_kirim` (`:366-392`) | | OD · pelanggan \| jenis · sample / harga kontrak→final | Catat ACC / Kunci harga / Siapkan → Pesanan Khusus | — |
| `harga_ditolak` (`:397-404`) | | SO · pelanggan \| "Sales {nama}" | Lihat → Pesanan | `booking_until` |

**Klik baris:** tidak ada (§1.2). **Aksi di tempat:** 3 dari 14 (verify, fulfill, release). Pelacak SO di meja ini juga memetakan 3 aksinya ke pop-up yang
sama (`:142-148`) — contoh baik. Sisanya pindah layar.
Pesan hasil aksi tampil sebagai `notice-bar` **di puncak halaman** (`:88-92`) — bila aksi dilakukan dari kartu di bawah lipatan, pesannya tidak terlihat
(`04_POLA_UI.md:26,93`).

**Pemotongan:** keterangan antrean (`DeskQueueCard.jsx:183`), judul (`:169`), alasan PIN 70 huruf di server; `KeepPendingPanel` tidak memotong (baris membungkus).

**Tipografi:** kepala & kartu angka memakai px mentah (10 / 10,5 / 11,5 / 12 / 15 px, 11 hex warna di `SalesAdminDesk.jsx`); kartu antrean memakai token `fs-*`;
`SoTrackerCard` 9–11,5 px; `KeepPendingPanel` 10–12 px + chip 11,5 px semibold; `CustomerGradeRulesCard` 11–11,5 px. Lima skala berbeda dalam satu layar.
Label huruf besar "TOTAL (TERMASUK PPN)" diulang di setiap kartu uang.

**Duplikasi (K6):**
- Nama meja: sidebar "Meja Admin Sales" (`navStructure.js:106`) → breadcrumb "MEJA ADMIN SALES" (`breadcrumbFor`) → judul "Meja Admin Sales · Antrean
  Alur Pesanan" (`navMeta.js:23`) → kicker "ADMIN SALES" + h2 "Meja Admin Sales" (`SalesAdminDesk.jsx:102-103`). Admin melihat "Meja Peran › Meja Admin Sales".
- **SO yang sama tampil tiga kali dengan tombol yang sama:** Pelacak SO (aksi "Periksa & lepas", `so_tracker_service.py:49-53`), Keep ("SO belum
  diverifikasi", `KeepPendingPanel.jsx:100-101`), dan antrean `perlu_verifikasi`. Foto pilot: SO-0005/0006/0008/0009 ada di ketiganya. Tab "Pending" Keep &
  Pending ≈ antrean `perlu_dipenuhi`; "Ditahan" ≈ aksi "Lepas ke gudang" di Pelacak.
- Empat tombol muat ulang (TopBar, kepala meja `:105`, Pelacak `SoTrackerCard.jsx:56`, Keep `KeepPendingPanel.jsx:64`).
- "Umur Tertua" (kartu angka) = maksimum lencana "tertua" per kartu; "Perlu Ditindak" = jumlah lencana kartu.
- **"Nilai Antrean"** menjumlah semua antrean non-qty (`:82-83`): total SO + sisa piutang jatuh tempo + nilai retur + OD — angka campuran tanpa arti.
- Teks usang "Meja Finance" (menu itu sudah jadi tab "Perlu Tindakan"): `SalesAdminDesk.jsx:132`, `work_desk_service.py:283`.

**Selisih vs `04_POLA_UI`:** paragraf penjelasan tetap (§1.4/§4) di kepala, Pelacak, Keep; kartu angka tanpa klik (§1.5); alat master data di layar kerja (§4);
Keep & Pending tanpa paginasi dan saringan berupa chip tab (§1.2, §2.B); pesan hasil di lapisan yang tak terlihat (§1.6); kosong berteks "badan usaha"
(`:165`, istilah baku "PT", `02_STANDAR.md` L2); layar bernilai uang tanpa banner PT (L4).

---

### B. Meja Saya (dan judul varian per peran)

**Berkas:** `features/desks/RoleDesk.jsx` (`desk="me"`, `:28-32`), `features/desks/deskText.js` · backend `role_desk_service.py`.

**Kepala (K1/K6):** kicker "Kerja saya" + h2 = judul dari server **"Meja Manajer"/"Meja Admin"/"Meja Sales"/"Meja Operator Gudang"/"Meja Desainer"/"Meja
Pengemudi"** (`RoleDesk.jsx:112-113`, `role_desk_service.py:35-36,329`), sedangkan sidebar, breadcrumb dan judul halaman berkata "Meja Saya · Giliran &
Antrean Peran" (`navMeta.js:27`) — dua nama untuk satu layar. Di bawahnya: paragraf penjelasan (`:119`), 3 kartu angka (`:120-124`), kotak merah "Paling lama
menunggu" + 2 tombol (`:125-140`), kotak "Bukan wewenang meja ini" (`:141-146`, Meja Saya tidak mengirim `not_my_desk` sehingga kosong), `SoTrackerCard`
(`:150`, hanya bila `order.view` — dibaca dari `localStorage` `kn_user`, `:35-40`), lalu grid antrean (`:160-165`).

**Antrean per jenis meja** (semua: aksi = **navigasi**; tidak ada satu pun aksi di tempat):

| id · judul | Siapa | Baris menampilkan | Aksi → tujuan | Catatan data |
|---|---|---|---|---|
| `giliran_saya` · Giliran saya (`role_desk_service.py:44-80`) | semua | nomor = potongan judul notifikasi · judul = **judul notifikasi utuh** "Giliran Anda — {tugas}: {nomor}" · keterangan = isi notifikasi "pihak · Rp · tahap: …" · lencana = tahap | Buka → `resolveView(row.link)` (`RoleDesk.jsx:80-84`) | **nomor diulang di judul; "tahap" diulang (lencana + keterangan); nilai rupiah terselip di teks** (`turn_notification_service.py:162,166`) |
| `eskalasi_keputusan` · Perlu keputusan — eskalasi gudang (`:287-305`) | manager, warehouse, admin (`wms.approve`) | nomor · pihak \| "Barang masuk/keluar · **alasan [:80]** · gudang" | Putuskan → layar Eskalasi | alasan dipotong server |
| `so_acc`, `po_acc`, `retur_acc`, `harga_khusus` (`:94-130`) | manager, admin | SO/PO/retur: nomor · pihak \| **status mentah + sales** (`_so_rows` `:85`, dirapikan `deskText.js:30-31`) — status juga di lencana; PO & retur **tanpa keterangan**; harga khusus: "harga normal → diminta/unit (−x%) · pengaju · “alasan”" | Putuskan → Pesanan / Pembelian / Retur / Persetujuan Harga | alasan harga khusus (informasi kunci untuk memutus) hanya di keterangan terpotong |
| `so_menunggu`, `so_konfirmasi`, `so_ditolak`, `sampel_saya` (`:133-146`) | sales | SO · pelanggan \| status + sales | Lihat → Pesanan | — |
| `tugas_wms`, `po_terima`, `sampel_potong`, `retur_terima_qc` (`:155-226`) | warehouse, admin | tugas · pihak \| arus · qty · gudang · tertahan bayar | Kerjakan / Terima / Potong / Buka → layar gudang | `po_terima` tanpa keterangan |
| `desain_saya`, `desain_bebas` (`:229-240`) | designer | DSR · pelanggan **atau brief[:60]** \| `target_type` mentah | Kerjakan / Ambil → Permintaan Desain | brief dipotong server 60 |
| `kiriman` (`:243-263`) | driver | SJ · pelanggan \| alamat/kota | Antar → Logistik | — |

**Klik baris:** tidak ada. **Pemotongan:** §1.2 + `RoleDesk.jsx:133` (dokumen tertua, `truncate` tanpa `title`) + potongan server di atas.
**Tipografi:** px mentah 10–15 px, 17 hex di `RoleDesk.jsx`; kotak "Paling lama menunggu" label 10,5 px tebal merah huruf besar + teks 12,5 px semibold.
**Duplikasi:** umur tertua tampil 3 kali (kartu angka `:123`, kotak merah `:131`, lencana tiap kartu); jumlah dokumen 2 kali (kartu angka + lencana kartu); kepala
3 nama berbeda (Meja Saya / Kerja saya / Meja Manajer).
**Selisih vs pola:** kartu angka tanpa klik, paragraf penjelasan, kotak "Paling lama menunggu" adalah bilah tambahan (§1.4), istilah "badan usaha" (`:156`).
Komentar menu mengklaim persetujuan "diputus di Meja" (`roles.js:333,344`) padahal semua aksi RoleDesk pindah layar.

---

### C. Meja MD

**Berkas:** `RoleDesk.jsx` (`desk="md"`, `:20-23`) · backend `work_desk_service.md_desk` (`:729-907`). Kepala: kicker "MD / Merchandiser" + h2 "Meja MD"
(server tidak mengirim `title`), paragraf penjelasan 2 baris berisi 5 istilah tebal (`:22`). Judul halaman "Meja MD · Desain, Sample & Bahan" (`navMeta.js:26`).

| id · judul | Baris menampilkan | Aksi → tujuan | Data tidak tampil / terpotong |
|---|---|---|---|
| `desain` · Permintaan desain (`:741-752`) | DSR · pelanggan/SO/"Internal · Motif" \| status ("belum ditugaskan"…) + revisi + **brief[:80]** | Buka → Permintaan Desain (`ROLE_DESK_TARGET`, `workDeskApi.js:275`) | brief utuh, desainer, tenggat (tidak dikirim) |
| `sample` · Sample & labdip (`:770-781`) | nomor · judul \| status + "n putaran · target tgl" | Buka → R&D Sample | `cost_total` dikirim sebagai nilai tapi kartu bertipe jumlah → tidak tampil |
| `od_pemenuhan` (`:802-806`) | OD · pelanggan \| "item: pilih jalur/realisasi" **[:110]** \| lencana "n item belum diadakan" | Buka → Pesanan Khusus | daftar item utuh |
| `pr` · Permintaan pembelian bahan (`:816-826`) | PR · alasan/judul \| qty · gudang · pemasok · butuh tgl · pembuat \| estimasi | Buka → PR | — |
| `makloon_jalan` (`:838-847`) | MKO · hasil akhir \| mitra · tahap \| biaya jasa rencana | Buka → Order Makloon | — |
| `makloon_faktur` (`:855-867`) | MKO · mitra \| no tagihan · langkah · `stage_code` **[:110]** (kode tahap mentah kemungkinan lolos `deskText.js:22-27`) | Buka → Order Makloon | — |
| `po_bahan` (`:874-886`) | PO · pemasok \| "dari PR · tiba tgl" \| total | Buka → Pembelian | — |
| `acuan` · SPK inspeksi tanpa acuan sample (`:895-902`) | SPK · pemasok/pelanggan \| jenis · ref · produk | Buka → Inspeksi | — |

**Klik baris:** tidak ada; semua tombol "Buka" (8 antrean, satu kata aksi yang sama) → pindah ke 6 menu berbeda. Padahal tiap jenis sudah punya panel rincian
dengan aksi (lihat §3.3). **Isi (K4):** tidak ada tenggat/desainer pada DSR, tidak ada pemasok/harga di baris sample; status DSR/sample/PO dicampur di kolom
lencana dengan kosa kata server. **Duplikasi:** sama dengan B (kartu angka, kotak tertua, lencana). **Selisih vs pola:** sama dengan B.

---

### D. Meja Gudang / Meja Admin Gudang

**Berkas:** `RoleDesk.jsx` (`desk="warehouse_admin"`, `:24-27`) + `ReturnDeskSummaryCard` disisipkan **di atas** meja oleh router (`AppViewRouter.jsx:254-256`)
· backend `work_desk_service.warehouse_admin_desk` (`:974-1117`).

**Nama tidak konsisten:** menu "Meja Gudang" (`navStructure.js:125`), judul "Meja Admin Gudang · Operasi Gudang & Logistik" (`navMeta.js:29`), kepala
"ADMIN GUDANG / Meja Admin Gudang" (`RoleDesk.jsx:25`).

| id · judul | Baris menampilkan | Aksi → tujuan | Catatan |
|---|---|---|---|
| `sj_belum_diangkut` (`:999-1009`) | SJ · pelanggan \| "SO · produk" **[:80]** \| qty | Buat pengiriman → Logistik dengan form buat terisi (`RoleDesk.jsx:64-69`) | navigasi + formulir di layar lain |
| `outbound` (`:1018-1032`) | nomor SO · **produk** sebagai judul \| gudang · pelanggan · diambil x/y · tertahan bayar \| qty | Buka WMS → Barang Keluar | `payment_blocked` hanya sebagai lencana |
| `retur_terima_qc` (`role_desk_service.py:210-226`) | SRET · pelanggan \| langkah ("n roll dalam perjalanan…") | Terima / Scan tiba / Buka → Retur | — |
| `inbound` · PO menunggu penerimaan (`:1041-1051`) | PO · pemasok \| "diterima x/y · n baris · ETA" \| total | Terima barang → Barang Masuk | — |
| `qc_pesanan` (`:1062-1071`) | SO · pelanggan \| mode QC | Buat SPK QC → **daftar Inspeksi tanpa fokus** (`workDeskApi.js:321`: `focus_id ""`, `number ""`) — konteks hilang total | hint 3 kalimat cara membuat SPK |
| `spk` (`:1076-1083`) | SPK · pihak \| jenis · ref · produk | Tugaskan → Inspeksi | — |
| `persetujuan_gudang` (`:1096-1099`) | opname/transfer | **Setujui → pindah ke Operasi Gudang** (tab cycle/transfer) | keputusan yang sebetulnya cocok untuk pop-up |
| `logistik` (`:1104-1112`) | nomor · pelanggan \| SJ · moda · sopir · plat · ETA · alasan gagal **[:110]** | Buka → Logistik (rincian pengiriman terbuka di sana) | — |

**`ReturnDeskSummaryCard` (K):** judul "Meja retur internal" `text-sm` semibold, tiga angka **`text-2xl` (24 px) semibold** — angka terbesar di halaman,
lebih besar dari judul halaman 17 px — tidak bisa diklik satu-satu, tombol hitam khusus `bg-[#1D1D1F]` (`ReturnDeskSummaryCard.jsx:20,30,38`), `mb-4`
sendiri. Menambah satu blok lagi sebelum meja.
**Klik baris / pemotongan / tipografi / duplikasi / selisih:** sama dengan B.

---

### E. Keuangan › Beranda Keuangan › Perlu Tindakan (dulu Meja Finance)

**Berkas:** `features/finance/FinanceDesk.jsx`; tiga sumber digabung menjadi kelompok (`susunKelompok`, `:85-118`).

**Kepala (K6):** "Perlu Tindakan" tampil **4 kali**: breadcrumb "… › Beranda Keuangan › Perlu Tindakan", judul "Perlu Tindakan · Pekerjaan Uang yang Menunggu"
(`navMeta.js:25`), tab hub "Perlu Tindakan" (`hubTabs.js:262`), h2 "Perlu Tindakan" (`FinanceDesk.jsx:215`). PT tampil 2 kali (breadcrumb + `EntityScopeBanner`
`:210`). Paragraf penjelasan tetap (`:224-226`). Di atasnya bisa muncul `ReturnDeskSummaryCard` (`AppViewRouter.jsx:254`).

**Yang baik:** satu-satunya meja yang memakai token huruf (`text-fs-*`, `kn-*`), **menyembunyikan kelompok kosong** dan **mengurutkan kelompok paling mendesak dulu**
(`:156-170`, `deskQueueOrder.compareFilledQueues`). Nama pelanggan menjadi tautan kartu pelanggan pop-up (`CustomerCardLink`, `:158-159`).

| Kelompok (`PERLU_TINDAKAN` `:42-68`) | Sumber | Aksi baris |
|---|---|---|
| Uang masuk perlu dicatat | `uang_masuk` + `bayar_sebelum_kirim` (`work_desk_service.py:471-507`) | **Terima pembayaran → pop-up `ReceivePaymentModal`** (`:187-190,257-265`) |
| Selisih bayar perlu diputus | `selisih_bayar` (`:516-526`, `action_kind="decide_variance"`) | Putuskan → **pindah** ke Rencana & Denda (action_kind tidak ditangani FE, `:185-195`) |
| Faktur pajak perlu terbit | `siap_faktur_pajak` (`:439-448`) | **Terbitkan → langsung menerbitkan Faktur Pajak, tanpa pratinjau/konfirmasi** (`:174-183,186`) |
| Nota kredit perlu ditinjau | `nota_batal_item` (`:637-647`) | Tinjau → daftar Pesanan tersaring nomor SO |
| Hutang jatuh tempo | `hutang_jatuh_tempo` (`:591-594`) + papan `vendor_bill` | Bayar → **kartu pemasok pop-up** (`:161-162,191`); baris papan "Buka" → pindah |
| Kontrabon menunggu | papan `contra_bon_*` | Buka → pindah |
| Posting gagal | `/finance/posting-failures` | Buka → Posting Gagal |
| Denda perlu diterbitkan | `denda_draft` (`:534-543`, `action_kind="issue_penalty"`) | Terbitkan → **pindah** (tidak ditangani FE) |
| Piutang lewat jatuh tempo | `jatuh_tempo` (`:546-555`) | Tagih → Piutang fokus pelanggan |
| Sample berbayar menunggu ACC bayar | `sample_acc_bayar` (`:655-663`) | Tinjau → Pesanan Sample |
| Retur selesai QC — putuskan nilai | `retur_putus_nilai` (`:670-677`) | Putuskan → Retur |

**Data tidak tampil / salah tampil (K4):** baris papan tanpa lencana status (`badge: ""`, `:73`) dan tanpa `at`; baris posting gagal selalu "menunggu < 1 hari"
(`age_days: 0`, `:80`); semua kelompok berlabel nilai "Nilai" (`:115`); antrean `uang_muka_belum_kirim` **dihitung server** (berat: satu panggilan GL per pesanan,
`work_desk_service.py:596-631`) tetapi **tidak dipakai** FE (`FinanceDesk.jsx:17`); `totals.ap_overdue/advance_liability` tidak dipakai. Baris "Piutang lewat
tempo": lencana "Lewat tempo" + keterangan "lewat n hari" + "menunggu n hari" = **angka yang sama 3 kali**.
`SoTrackerCard` (semua SO aktif) ditempel di bawah kelompok (`:253-255`) — tabel penjualan di beranda keuangan.
**Selisih vs pola:** kelompok kosong disembunyikan (bertentangan dengan `04_POLA_UI.md:54` "kartu kosong tetap tampil" — tetapi justru menjawab K1);
paragraf penjelasan; pesan hasil di puncak halaman (`:205-209`).

---

### F. Meja Sample / Meja Admin Sample

**Berkas:** `features/samples/SampleAdminDesk.jsx` · backend `routers/sample_orders.py:136-185`.
**Nama:** menu "Meja Sample" (`navStructure.js:134`), judul "Meja Admin Sample · Antrean Pesanan Sample" (`navMeta.js:30`), kepala "ADMIN SAMPLE / Meja Admin
Sample" (`:69-70`), kotak "Bukan wewenang… → Meja Finance" (usang, `sample_orders.py:184`).

| id · judul | Baris | Aksi | Data tidak tampil |
|---|---|---|---|
| `bayar_sampel` · Sample berbayar — menunggu persetujuan pembayaran | SOS · pelanggan \| status + "**GRATIS/BERBAYAR** · 3 barang pertama · dipotong x/y" \| total | **Setujui Bayar → langsung disetujui** (`:36-45`) | `sales_name`, `fulfillment_method`, jumlah item (`sample_orders.py:147`); `at` tidak dikirim |
| `siap_gudang` · Siap diteruskan ke gudang | sama | **Teruskan ke Gudang → langsung** (`:46`) | sama |
| `di_gudang`, `kirim_ambil`, `selesai` (7 hari) | sama | Pantau / Lihat → Pesanan Sample (baris terpilih) | sama |

**Risiko:** di daftar Pesanan Sample, "Setujui Pembayaran" **memeriksa uang yang sudah masuk dan meminta konfirmasi bila kurang** (`SampleOrdersView.jsx:141-153`,
pelatihan 18 Nov V6). Tombol yang sama di meja **melewati pemeriksaan itu**.
**Isi:** 2 dari 5 kartu adalah pantauan (`kirim_ambil`, `selesai`), bukan pekerjaan. "Perlu Ditindak" hanya menghitung 2 antrean (`:56`) — arti berbeda dengan meja lain
yang menjumlah semua. Keterangan berhuruf besar "GRATIS/BERBAYAR" (`sample_orders.py:143`).
**Tipografi / duplikasi / selisih:** sama dengan A (Metric salinan ketiga, toast buatan sendiri `:64`, paragraf `:74`, SoTracker `:90`).

---

### G. Meja Cutting (tab di Pesanan Sample)

**Berkas:** `features/samples/CuttingDesk.jsx` di `SampleOrdersView.jsx:166-174` · backend `services/cutting_service.py:13-16,80-125`.
**Tidak memakai `DeskQueueCard`/`TableFilterBar`:** kartu buatan sendiri (`:88-131`) dengan judul **11 px tebal huruf besar** (`:91`), jumlah 10 px; tanpa cari,
saring, urut, paginasi (semua tugas terbuka sampai 500 dirender); kosong berteks "Kosong." (bukan teks baku).

| Bagian (`QUEUES`) | Baris | Aksi |
|---|---|---|
| Menunggu pembelian internal | "SO · produk" + lencana jenis + umur tunggu \| qty · gudang · roll · "stok milik PT lain" | — |
| Menunggu dipotong gudang | **ringkasan teks** "n baris dari m pesanan: SO-1, SO-2 …" (maks. 8) + `LinkCard` ke Operasi Gudang › Cutting (`:141-164`) | pindah layar |
| Hasil potong — menunggu diterima | sama + **dropdown lokasi tujuan + "Terima hasil potong" di baris** (`:114-124`); tombol biru penuh "Terima semua potongan SO (n baris)" disisip di tengah daftar (`:97-102`) | **di tempat** |
| Diterima — siap kirim/ambil | sama + "diterima oleh …" | — |

**Data tidak tampil:** `customer_name`, `sku`, `cut_at`, `status` dikirim (`cutting_service.py` baris bucket) tetapi tidak ditampilkan — operator tidak tahu
potongan untuk pelanggan siapa. Tidak ada pemotongan teks (baris membungkus). Paragraf penjelasan (`:77`). Tombol "+ Buat Sample Katalog" tetap tampil di tab
ini (`SampleOrdersView.jsx:155-165`). Muat ulang otomatis tiap 60 detik (`:48-52`).

---

### H. HP Admin Sales › tab "Meja"

**Berkas:** `features/sales/mobile/MobileSalesAdminDesk.jsx` (endpoint sama dengan A).
- Kartu antrean **bisa dibuka-tutup** (`:49,65-78`) — dilarang `04_POLA_UI.md:91` (pola HP memang belum diaudit, `PILOT_POLA.md` §3). Tanpa cari/saring/urut;
  "Lihat semua n baris" (`:87-91`).
- Baris: nomor 12 px tebal + lencana status **9,5 px** + umur 9,5 px; judul 12,5 px semibold `truncate`; keterangan 10,5 px `truncate` (`:30-38`) — **tidak ada
  cara melihat teks utuh di HP** (tidak ada hover). Baris tidak bisa disentuh; hanya tombol.
- Aksi: verify/fulfill memakai **dialog yang sama dengan desktop** (`:193-204`); lainnya ke sub-layar HP (retur, permintaan internal, OD) atau tab Pesanan
  (`:131-137`) — pola HP lebih "di tempat" daripada desktop.
- Kepala: tab "Meja" + h2 "Meja Admin Sales" + kartu angka (label 9,5 px, nilai 13 px), paragraf alur (`:177-179`), Keep & Pending (`:180`), kotak "Meja Finance"
  usang (`:183`). Tanpa Pelacak SO dan tanpa form grade (isi berbeda dari desktop).

### I. HP MD › tab "Meja"

**Berkas:** `MobileMdViews.jsx:35-95` (`MobileMdDesk`).
- Kartu bisa dibuka-tutup (`:64-66`), **semua baris** dirender (maks. 200 per antrean), tanpa cari/paginasi.
- **Baris bisa disentuh** (seluruh baris = tombol, `:78`) dan membuka rincian **di dalam aplikasi HP**: DSR → tab Desain (`DesignDetail` `:109+`), sample →
  tab Sample (`SampleDetail` dengan `RoundAssess`/`SampleDecide` `:209-320`), PR → sub-layar PR; jenis lain → tampilan desktop penuh (`mdRowTarget` `:97-103`).
  Ini **satu-satunya meja yang baris-nya membuka rincian**.
- Kartu angka 20 px tebal (`:56-58`) vs 13 px di HP Admin Sales — beda antar aplikasi HP; ikon kartu hanya untuk 3 dari 8 antrean (`:33`); nilai per baris tidak
  ditampilkan sama sekali.

### J. Kredit & Plafon · Daftar Kerja Kredit (pembanding)

**Berkas:** `features/finance/CreditDeskView.jsx`, `creditDeskParts.jsx`. Bentuk berbeda dari pola Meja: satu antrean tampil sekaligus lewat dropdown (6 antrean,
`:207-208`), cari, paginasi server `PaginationBar` + unduh CSV (`:217-223`). **Hampir semua aksi di tempat:** Setujui/Tolak lewat `ConfirmModal` dengan alasan
(`:255-262`), janji bayar `PromiseModal`, bebaskan denda, terbitkan denda dengan `askConfirm` (`:147-156`), salin naskah pengingat, periksa ulang kredit; baris
jatuh tempo bisa **dibentangkan** untuk melihat tagihannya (`creditDeskParts.jsx:171-202`). Token huruf konsisten (`text-fs-12/13`). Kekurangan: "Buka kartu
pelanggan" **mengganti seluruh layar** dengan `Customer360Panel` (`:172-178`) alih-alih pop-up kartu pelanggan bersama.

### K. Kartu "Meja retur internal"
Lihat D. Kartu ini muncul juga di Beranda Admin/Manajer dan di atas Perlu Tindakan Keuangan (`AppViewRouter.jsx:254`).

---

## 3. Lintas meja

### 3.1 Komponen bersama & konsistensinya

| Unsur | A Admin Sales | B/C/D RoleDesk | E Keuangan | F Sample | G Cutting | H HP AS | I HP MD |
|---|---|---|---|---|---|---|---|
| Kartu antrean | `DeskQueueCard` | `DeskQueueCard` | `DeskQueueCard` | `DeskQueueCard` | buatan sendiri | buatan sendiri, buka-tutup | buatan sendiri, buka-tutup |
| Cari/saring/urut per kartu | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Paginasi 5 | ✓ | ✓ | ✓ | ✓ | ✗ | "Lihat semua" | ✗ |
| Kartu kosong | tampil, setinggi tetangga | tampil | **disembunyikan** | tampil | "Kosong." | tampil tertutup | tampil tertutup |
| Urutan kartu | server | server (+fokus) | **paling mendesak dulu** | server | server | server | server |
| Teks mentah dirapikan (`humanizeQueueRows`) | ✗ | ✓ (`RoleDesk.jsx:91`) | ✗ | ✗ | – | ✗ | ✗ |
| Kartu angka | `Metric` lokal (tanpa klik) | `Metric` lokal | tidak ada | `Metric` lokal | tidak ada | inline | inline 20 px |
| Klik baris | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **✓ rincian** |
| Aksi di tempat | 3 jenis | 0 | 3 jenis | 2 jenis (tanpa konfirmasi) | terima potong | 3 jenis | dari rincian |
| Huruf | px mentah + token | px mentah + token | **token** | px mentah + token | px mentah | px mentah 9,5–13 | px mentah 9,5–20 |
| Cangkang pop-up | `modal-overlay` buatan (`VerifyOrderDialog.jsx:64`, `FulfillmentDecisionDialog.jsx:102`) | – | `FormModal` | – | – | sama dengan A | – |
| Pesan hasil | `notice-bar` di puncak | – | `notice-bar` di puncak | div buatan di puncak | `ErrorNotice` dipakai untuk pesan sukses transfer (`CuttingDesk.jsx:58`) | `notice-bar` | – |

Kode siap pakai yang menganggur: `splitDeskQueues` (pisah kartu berisi/kosong, urut mendesak) tidak dipanggil di mana pun (`deskQueueOrder.js:31-38`;
komponen `DeskEmptyQueues` yang dirujuk komentarnya tidak ada).

### 3.2 Sepuluh masalah paling berdampak

1. **Klik baris tidak membuka apa pun (K2).** Baris berhover dan bernomor warna tautan, tetapi tanpa `onClick` (`DeskQueueCard.jsx:163-169`); di Pelacak SO baris
   yang bukan wewenang meja tidak bisa dibuka sama sekali (`SoTrackerCard.jsx:88,111-113`). Kartu angka ber-`cursor: pointer` dan terangkat saat hover tanpa aksi
   (`components.css:207,211`; `RoleDesk.jsx:172-182`). Hanya HP MD yang baris-nya membuka rincian (`MobileMdViews.jsx:78`).
2. **Meja dirancang sebagai papan lompat, bukan tempat kerja (K3).** Filosofi tertulis `workDeskApi.js:241-244`; RoleDesk (Meja Saya, MD, Gudang — 3 meja,
   ±25 jenis antrean) **tidak punya satu pun aksi di tempat** (`RoleDesk.jsx:62-86`). Server sudah mengirim `action_kind` `decide_variance` dan `issue_penalty`
   tetapi FE meneruskannya ke navigasi (`FinanceDesk.jsx:185-195`). "Setujui" opname/transfer, "Putuskan" SO/PO/retur/harga khusus, "Tugaskan" SPK — semuanya
   pindah menu; saat kembali, cari/saring/halaman kartu hilang (§1.5). "Buat SPK QC" mendarat di daftar Inspeksi tanpa dokumen terpilih (`workDeskApi.js:321`).
3. **Halaman bertumpuk sebelum pekerjaan (K1).** Meja Admin Sales: kepala+paragraf+3 angka+kotak wewenang, Pelacak SO, Keep & Pending tanpa paginasi, form
   grade pelanggan — baru kemudian 13–14 kartu antrean termasuk yang kosong (`SalesAdminDesk.jsx:98-174`; ±3.146 px). RoleDesk: `ReturnDeskSummaryCard` +
   kepala + paragraf + 3 angka + kotak tertua + kotak wewenang + Pelacak SO (`AppViewRouter.jsx:254-256`, `RoleDesk.jsx:108-150`). Satu kartu antrean berisi 1 baris
   tetap memikul 5 lapis kepala/bilah (`DeskQueueCard.jsx:69-146`); kartu kosong setinggi tetangga (`:68`).
4. **Pekerjaan yang sama ditampilkan 2–3 kali (K6).** SO belum diperiksa muncul di Pelacak SO ("Periksa & lepas"), Keep, dan antrean `perlu_verifikasi`
   (`so_tracker_service.py:49-53`, `KeepPendingPanel.jsx:100-125`, `work_desk_service.py:189-200`); Pending ≈ `perlu_dipenuhi`; sample berbayar ada di meja F dan E
   (`sample_orders.py:161-175`, `work_desk_service.py:655-663`). Di dalam baris: nomor + "tahap" ganda di Giliran saya (`role_desk_service.py:74-77`,
   `turn_notification_service.py:162,166`), status ganda di `_so_rows` (`role_desk_service.py:85-87`), "lewat n hari" tiga kali di jatuh tempo, jumlah ganda di
   kepala kartu jumlah (`DeskQueueCard.jsx:63-65,76-80`).
5. **Judul berulang dan nama tidak seragam (K6).** "Meja Admin Sales" 3–4 kali (sidebar, breadcrumb, judul `navMeta.js:23`, kepala `SalesAdminDesk.jsx:102-103`);
   "Perlu Tindakan" 4 kali (breadcrumb, `navMeta.js:25`, `hubTabs.js:262`, `FinanceDesk.jsx:215`). Satu layar, beberapa nama: Meja Gudang/Meja Admin Gudang,
   Meja Sample/Meja Admin Sample, Meja Saya/Meja Manajer. Nama usang "Meja Finance" di `SalesAdminDesk.jsx:132`, `MobileSalesAdminDesk.jsx:183`,
   `work_desk_service.py:283`, `sample_orders.py:184`. Empat tombol muat ulang di Meja Admin Sales.
6. **Teks terpotong tanpa jalan melihat utuh (K2).** Judul baris tanpa `title` (`DeskQueueCard.jsx:169`); keterangan hanya bertooltip hover (`:183`, tidak bekerja di
   HP); HP memotong tanpa apa pun (`MobileSalesAdminDesk.jsx:36-37`); Pelacak SO `max-w-[200px] truncate` (`SoTrackerCard.jsx:91`). Server ikut memotong:
   alasan PIN 70 (`work_desk_service.py:352`), brief DSR 80/60 (`:747`, `role_desk_service.py:235`), item OD 110 (`:799`), tagihan makloon 110 (`:863`),
   pengiriman 110 (`:958`), SJ 80 (`:1004`), alasan eskalasi 80 (`role_desk_service.py:299`), barang kurang hanya 2 baris (`:264`), item sample 3 (`sample_orders.py:140`).
7. **Huruf tiga sistem, tebal di mana-mana (K5).** Token `fs-*` (DeskQueueCard, FinanceDesk, CreditDesk) bercampur px mentah 9–15 px (RoleDesk 10–15 px, SoTracker
   9–11,5 px, KeepPending 10–12 px, Cutting 10–12 px, HP 9,5–20 px; hitungan per berkas di Lampiran) dan kelas CSS `.metric-card` (12/20 px) yang ditimpa salinan lokal
   (10/15 px). Judul kartu 14 px tebal = h2 halaman; dalam satu baris lima unsur tebal/semibold; label huruf besar "TOTAL (TERMASUK PPN)" di tiap kartu; angka
   terbesar halaman adalah kartu retur internal 24 px (`ReturnDeskSummaryCard.jsx:20`) dan angka 20 px HP MD — sedang judul halaman 17 px. Teks < 12 px
   melanggar `04_POLA_UI.md:82`.
8. **Kartu angka tidak berguna dan tidak bisa diklik (§1.5).** Tiga salinan `Metric` (`RoleDesk.jsx:172`, `SalesAdminDesk.jsx:203`, `SampleAdminDesk.jsx:101`);
   isinya mengulang lencana kartu; "Nilai Antrean" menjumlah rupiah yang berlainan arti (`SalesAdminDesk.jsx:82-83`); "Perlu Ditindak" berarti beda di tiap
   meja (semua antrean vs 2 antrean, `SampleAdminDesk.jsx:56`; antrean pantauan ikut dihitung di Admin Sales).
9. **Aksi berakibat besar tanpa pratinjau/konfirmasi, dan berbeda dari layar daftarnya.** Terbitkan Faktur Pajak sekali klik (`FinanceDesk.jsx:174-186`);
   Setujui Bayar sample tanpa cek uang masuk yang di daftar Pesanan Sample wajib dikonfirmasi (`SampleAdminDesk.jsx:36-45` vs `SampleOrdersView.jsx:141-153`);
   Lepas ke gudang & Teruskan ke gudang langsung. Bandingkan Meja Kredit: terbitkan denda lewat `askConfirm` (`CreditDeskView.jsx:147-156`).
10. **Isi kurang dan sebagian menyesatkan (K4).** Tidak ada PT per baris di mode Semua PT (`_row` tanpa `entity_id`, `work_desk_service.py:106-116`); batas cadangan
    `booking_until` tidak tampil (`:199,226,403`); semua baris kurang stok tidak tampil (`:268`); pelanggan & SKU di Meja Cutting tidak tampil; sales & cara
    kirim sample tidak tampil (`sample_orders.py:147`); "masuk ±" ditebak bila `at` kosong (jatuh tempo, uang masuk, sample, papan hutang); posting gagal selalu
    "< 1 hari" (`FinanceDesk.jsx:80`); tombol "Cetak" hanya pindah ke daftar Pesanan (`work_desk_service.py:241-242`); catatan "buka layar daftarnya" tanpa tautan
    (`DeskQueueCard.jsx:142-146`); waktu susun `generated_at` tidak pernah tampil; antrean uang muka dihitung tetapi dibuang (`work_desk_service.py:596-631`).

### 3.3 Pola rincian/aksi di tempat yang sudah ada dan bisa dipakai ulang

**Cangkang:**
- `components/DetailModal.jsx` — pop-up rincian baku (Esc, latar `overlayDismiss` INV-UI-01, kunci gulir, layar penuh ≤ 640 px); 45 pemakai. Varian `framed`
  dipakai kartu pelanggan/pemasok dan Permintaan Desain.
- `components/FormModal.jsx` — pop-up aksi/isian baku (187 pemakai; galat di dalam pop-up).
- `components/DetailPopup.jsx` + `features/orders/OrderDetailPanel.jsx` — rincian SO **lengkap dengan tombol siklus** (setujui, konfirmasi, batal, dokumen,
  faktur) dalam pop-up (`features/orders/OrdersView.jsx:257-275`); `SOCompactPanel.jsx` untuk ringkasan.
- `components/DetailDrawer.jsx` + `App.js:350,372` — panel tetap di kanan (konten diberi ruang `xl:pr-[404px]`): bentuk yang dipilih untuk M18 ("bukan kartu
  melayang") — alternatif bila pemilik tidak mau pop-up menutupi daftar.

**Aksi per jenis antrean (komponen yang sudah ada → antrean meja yang bisa memakainya):**

| Komponen yang ada | Untuk antrean |
|---|---|
| `features/approvals/ApprovalDecisionModal.jsx` — "keputusan di tempat": rincian + Setujui/Tolak + catatan untuk SO, PO, harga khusus, retur jual/beli, opname, amandemen, kredit (`:1-12,27-36`) | Meja Saya manajer/admin `so_acc`, `po_acc`, `retur_acc`, `harga_khusus`; Meja Gudang `persetujuan_gudang` (opname) |
| `features/approvals/MyApprovalDecisionModal.jsx` (`FormModal`) — ACC desain, PR, klaim makloon | Meja MD `pr`, `desain` (ACC) |
| `VerifyOrderDialog` + `OrderPreviewCard`, `FulfillmentDecisionDialog` (sudah dipakai A, H, `SOCompactPanel`) | Pelacak SO di semua meja; Meja Saya sales |
| `ReceivePaymentModal` (`FormModal`) | E (sudah), CollectionWorklist (sudah) — juga `bayar_sebelum_kirim`, sample berbayar |
| `partyCards.jsx` `openCustomerCard/openSupplierCard`, `CustomerCardLink` (pop-up kartu pelanggan/pemasok, dipasang sekali di router) | nama pelanggan/pemasok di semua baris meja (kini hanya E) |
| `design/DesignRequestDetailPanel` dalam `DetailModal framed` (`DesignRequestsView.jsx:390-397`) | MD `desain`, desainer `desain_saya/desain_bebas` |
| `rnd/SampleDetailPanel` (`sampleId`), `rnd/DecideModal`, `RoundActionModal` | MD `sample` |
| `purchasing/PurchaseRequisitionDetailPanel`, `MakloonOrderDetailPanel` (`mkoId`), `admin/po/PODetailPanel` (prop `inModal`) | MD `pr`, `makloon_*`, `po_bahan`; Gudang `inbound`; Keuangan hutang |
| `inspections/InspectionDetailPanel`, `logistics/DeliveryDetailModal` (`id`), `wms/transfer/TransferDetailModal`, `sales/ReturnDetail`, `sales/SpecialOrderDetail` | Gudang `spk`/`acuan`/`logistik`/`persetujuan_gudang` (transfer); retur; OD |
| Panel rincian+aksi Pesanan Sample (`SampleOrdersView.jsx:217-300`: setujui bayar dengan cek uang, teruskan, batal, riwayat) — perlu diekstrak jadi komponen | Meja Sample semua antrean; Keuangan `sample_bayar` |
| Pola Meja Kredit: `ConfirmModal` beralasan, `PromiseModal`, baris dibentangkan (`creditDeskParts.jsx:171-202`), `askConfirm` sebelum terbit | Keuangan denda, selisih bayar, piutang lewat tempo; Admin Sales jatuh tempo |
| HP MD `DesignDetail`/`SampleDetail` di dalam tab (`MobileMdViews.jsx:109-320`) | pola HP untuk meja HP lain |

Arah yang konsisten dengan kode yang ada: satu **registri pratinjau per `ref_type`** (jenis → panel rincian di atas) yang dipanggil `DeskQueueCard` saat **baris diklik**
(rincian utuh, teks tak terpotong) dan saat **tombol aksi diklik** (panel yang sama dengan aksinya), dengan "Buka layar penuh" sebagai tautan sekunder — pola
yang sudah ditulis `ApprovalDecisionModal.jsx:3-7`.

---

## 4. Keputusan pemilik yang dibutuhkan sebelum perbaikan (STOP & ASK)

1. **Pop-up vs panel tetap.** `04_POLA_UI.md:26` ("Rincian = halaman/panel tetap") dan `:93` (larangan "popup melayang yang menutupi daftar", asal M18) bertabrakan
   dengan K3. Pilih: `DetailModal` (pop-up berlatar, Esc) atau panel kanan tetap ala `DetailDrawer` (daftar tetap terlihat).
2. **Kartu kosong.** `04_POLA_UI.md:54` mewajibkan kartu kosong tetap tampil; Keuangan sudah menyembunyikannya dan K1 meminta layar tidak padat. Usulan: kartu kosong
   dilipat menjadi satu baris "Bersih: …" (`splitDeskQueues` sudah ada).
3. **Pelacak SO, Keep & Pending, Aturan Grade di meja.** Tetap di meja (dengan duplikasi di atas), dipindah ke tab/menu sendiri, atau digabung ke antrean?
4. **Satu nama per meja** (menu = breadcrumb = judul; kepala di dalam layar dihapus) dan pengganti "Meja Finance" di teks.
5. **Aksi sekali klik** (terbit faktur pajak, setujui bayar sample, lepas/teruskan ke gudang): wajib pratinjau + konfirmasi?
6. **Skala huruf meja**: §3 menyebut label kolom 11 px sekaligus minimum 12 px, dan token `fs-*` tidak punya 11 px — perlu satu angka.

---

## Lampiran — ukuran huruf mentah dan warna hex per berkas (`grep text-[Npx]`, hex `#RRGGBB`, token `text-fs-*`)

| Berkas | px mentah | hex | token fs |
|---|---|---|---|
| `features/desks/RoleDesk.jsx` | 10, 10,5×2, 11, 11,5×2, 12×2, 12,5, 15 | 17 | 0 |
| `features/sales_admin/SalesAdminDesk.jsx` | 10, 10,5, 11,5×2, 12×2, 15 | 11 | 0 |
| `features/sales_admin/DeskQueueCard.jsx` | – | 0 | 17 |
| `features/sales_admin/SoTrackerCard.jsx` | **9**, 10, 10,5×6, 11×4, 11,5×4 | 24 | 0 |
| `features/sales_admin/KeepPendingPanel.jsx` | 10×2, 11×6, 11,5×3, 12×3 | 28 | 0 |
| `features/sales_admin/CustomerGradeRulesCard.jsx` | 11×3, 11,5, 12 | 8 | 0 |
| `features/finance/FinanceDesk.jsx` | – | 0 | 4 |
| `features/samples/SampleAdminDesk.jsx` | 10, 10,5, 11,5×2, 12×2, 15 | 12 | 0 |
| `features/samples/CuttingDesk.jsx` | 10×4, 11×5, 11,5×5, 12×2 | 25 | 0 |
| `features/samples/SampleOrdersView.jsx` | 10×6, 10,5×2, 11×4, 11,5×2, 12×4, 13, 15, 16 | 41 | 0 |
| `features/sales/mobile/MobileSalesAdminDesk.jsx` | **9,5×4**, 10, 10,5×4, 11×2, 11,5×3, 12×3, 12,5, 13×2 | 15 | 0 |
| `features/sales/mobile/MobileMdViews.jsx` | 9,5, 10×2, 10,5×8, 11×17, 11,5×3, 12×16, 12,5×7, 13, 15×2, 20×2 | 41 | 0 |
| `features/home/ReturnDeskSummaryCard.jsx` | 11×3 (+ `text-2xl` 24 px, `text-sm`) | 9 | 0 |
| `features/finance/CreditDeskView.jsx` / `creditDeskParts.jsx` | – | 0 | 3 / 15 |
