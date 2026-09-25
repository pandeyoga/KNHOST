# PRD — Kain Nusantara ERP (lanjutan dari repo github.com/kakjsbsbs/KN)

## Problem statement (asli, 2026-09-17)
Lanjutkan development repo KN. Fitur dispatch/pengiriman masih sangat basic: tidak ada quick action di dasbor
(hanya list yang harus buat dispatch), belum ada history pengiriman, visualisasi status pengiriman yang sedang
diproses, ketersediaan armada internal, jenis pengiriman (kurir pihak ketiga dll). Pertanyaan: bagaimana fitur
customer ambil sendiri & validasinya? Data pengiriman (alamat kirim) masih bocor/terekspos pada SO yang ambil sendiri.

## Pilihan user
- Bangun semua sekaligus: dasbor dispatch + quick action, visualisasi status, ketersediaan armada, jenis pengiriman
  (internal / kurir pihak ketiga / ambil sendiri), history.
- Ambil sendiri: kode pickup unik + verifikasi identitas pengambil (nama + no. ID), tanpa driver/armada/alamat kirim.
- Kurir pihak ketiga: nama kurir, no. resi, biaya kirim, estimasi tiba.
- Armada: master kendaraan + driver dengan status (tersedia / dalam perjalanan / perawatan), status berubah otomatis.

## Arsitektur (yang disentuh)
- Backend FastAPI: `services/logistics_service.py` (moda self_pickup, kode pickup, handover, dashboard, history, redaksi kode),
  `services/fleet_service.py` (baru — master kendaraan `fleet_vehicles`, status sopir turunan), `routers/logistics.py`
  (endpoint baru), `schemas_logistics.py`, `entity_scope.py` (+fleet_vehicles scoped), `services/so_verify_service.py`
  (anti-bocor alamat pada SO ambil).
- Frontend React: `features/logistics/` → `LogisticsView` (tab Dasbor/Daftar/Riwayat/Armada), `DispatchDashboard`,
  `HistoryPanel`, `FleetPanel`, `PickupHandoverPanel`, `DeliveryCreateModal` (moda otomatis dari metode pemenuhan SO),
  `DeliveryDetailModal` (cabang pickup), `sales_admin/OrderPreviewCard` (sembunyikan alamat untuk SO ambil).
- Frontend TIDAK hot-reload: `setsid nohup bash /app/scripts/rebuild_frontend.sh > /app/.rebuild.out 2>&1 &`.
- Env: backend/.env CORS_ORIGINS harus daftar origin eksplisit (bukan `*`).

## Persona
Admin gudang / manajer (buat & kelola pengiriman, armada), petugas gudang (serah terima pickup), sopir (tugas hari ini),
sales / admin sales (pantau, bagikan kode pickup ke pelanggan).

## Sudah diimplementasikan (2026-09-17)
- Dasbor Pengiriman: KPI (SJ menunggu, menunggu diambil, diproses, di jalan, ETA hari ini, terlambat, terkirim hari ini),
  aksi cepat per SJ (Buat pengiriman / Siapkan pickup), antrean serah terima pickup, alur status (bar), moda (donut),
  ringkasan armada, daftar sedang diproses, baru selesai/gagal.
- Jenis pengiriman: Ekspedisi (kurir, resi, layanan, biaya kirim, ETA) · Armada sendiri (kendaraan master + sopir) ·
  Diambil pelanggan (kode pickup 6 karakter, tanggal ambil).
- Validasi ambil sendiri: SO `fulfillment_method=ambil` wajib moda self_pickup (dan sebaliknya ditolak); tidak ada
  alamat/plat/sopir; tahapan hanya lewat POST pickup-handover (kode cocok + nama pengambil [+ no. ID]); kode salah
  ditolak & dihitung; kode disembunyikan dari peran gudang/sopir (mereka mencocokkan kode yang disebut pengambil).
- Anti-bocor: `shipments/unassigned` & `order_preview` tidak mengirim alamat kirim untuk SO ambil.
- Riwayat: filter tanggal/moda/status/kata kunci, statistik (terkirim, gagal, rata-rata hari, total biaya ekspedisi), CSV.
- Armada: CRUD kendaraan, perawatan ⇄ tersedia, otomatis on_trip saat berangkat & lepas saat tiba/gagal/selesai,
  status sopir turunan dari pengiriman aktif; kendaraan maintenance/on_trip tak bisa dipilih.
- Seed demo: `scripts/seed_dispatch_demo.py`; smoke API: `scripts/smoke_dispatch.sh`.

## Setup ulang 2026-09-18 (repo nakisbdvsb/KN)
- Repo di-overlay ke /app (`.env` dipertahankan; CORS_ORIGINS diisi origin preview eksplisit — wajib, server menolak `*`).
- pip: filter baris `emergentintegrations`/`litellm` (konflik pin; sudah ada di base image). FE: `yarn install --frozen-lockfile` + `bash scripts/rebuild_frontend.sh`.
- Seed: `python seed_realistic.py` → `scripts/seed_dispatch_demo.py` → `backfill_po_payment_due.py` → `seed_endek_showcase.py` → `seed_design_scores_demo.py`.
- Verifikasi: `/api/logistics/dashboard` mengembalikan 5 pengiriman demo; UI Dasbor Pengiriman render (screenshot).
- Temuan kecil: `OrderJourneyPanel` menampilkan "Armada sendiri" untuk moda self_pickup (belum ada cabang pickup) → masuk P1 di bawah.

## Sinkron Permintaan Desain ↔ Design Studio (2026-09-18)
- Permintaan Desain kini memakai master kategori yang SAMA dengan Design Studio (Kategori Pattern + Kategori Design)
  menggantikan `target_type` legacy (tetap diterima API). Modal buat permintaan 3 bagian (sumber · apa · siapa/kapan).
- Desainer: dari detail permintaan → "Buat & buka desain" (`POST /design-requests/{id}/create-design`: desain Studio dibuat
  dengan kode otomatis, brief/kategori/lini ikut, tertaut dua arah `request_id`, permintaan → Dikerjakan) atau "Tautkan
  yang sudah ada" (`/link-design`; hanya desain berjalan & belum tertaut).
- Status permintaan MENGIKUTI siklus hidup desain (`design_studio_service.transition` → `sync_from_design`):
  submit → Menunggu keputusan · request_revision → Minta revisi (+revision_count, alasan) · approve → ACC.
  approve/reject langsung di permintaan yang tertaut Studio ditolak 400 (keputusan + nilai di halaman desain).
- UI: detail 2 kolom (brief, desain tertaut dengan cover/status/nilai, riwayat | fakta, tindakan), stepper status,
  kartu papan menampilkan kategori, pelanggan/SO, kode & status desain, desainer, tenggat. Deep-link `openRnd({view:"rnd-designs", designId})`
  → `RndDesignsView` prop `focus`. Halaman desain menampilkan chip "Dari permintaan …".
- Seed `seed_design_requests()` memakai alur sinkron. Uji: `backend/tests/test_iter319_dsr_studio_sync.py` (9/9), iteration_28.

## Galeri Referensi Brief (2026-09-18)
- `design_requests.references[]` (storage scope `design_requests`): POST/GET/DELETE `/design-requests/{id}/references[/{fid}]`
  (unggah/hapus izin `design_request.create` = pembuat permintaan; hanya gambar; status belum ACC/batal).
- `_propagate_references` menyalin ke desain tertaut sebagai berkas `kind=reference` (penanda `source_reference_id`, idempoten)
  saat create-design / link-design dan saat referensi baru ditambah setelah tertaut.
- UI: `ReferenceGallery.jsx` — pratinjau lokal di modal buat (diunggah setelah permintaan tercipta), galeri + unggah/hapus di
  detail, thumbnail kecil di kartu papan.

## Permintaan Sample R&D — UI baru cermin alur Desainer (2026-09-18)
- Setup ulang dari repo gatadadavaoa/KN (overlay ke /app, .env dipertahankan, CORS eksplisit, seed `seed_realistic.py`).
- Pilihan user: satu papan "Permintaan Sample" + rincian bergaya Studio dengan 3 TAB terpisah Labdip / Handfeel / Proofing;
  pembuat admin/manager/MD/sales; pengerja role MD (custom role & access diperbaiki nanti). Mekanisme server TIDAK diubah.
- Frontend `features/rnd/`: `RndSamplesView` (KPI, tab Papan/Daftar, chip jenis & status, kolom draft→decided,
  `SampleBoardCard`), `SampleFormModal` (FormModal 3 bagian bernomor: dari mana · apa yang disampling · kapan),
  `SampleDetailPanel` (DetailModal framed, kepala + stepper, 2 kolom, aksi kanan), `SampleTypeTabs` (tab per jenis,
  jenis yang belum diminta → tombol tambah via PATCH sample_types), `SampleRoundList` (+prop `onlyType`).
- `hubTabs`: rnd-samples kini juga untuk `md` & `sales_admin`. `navMeta` judul diperbarui.
- Testing agent iterasi 29: backend 5/5, frontend 100% (papan, filter, buat, tab jenis, kirim, batal, role MD).

## Galeri Bukti Per Tab (2026-09-18)
- `features/rnd/SampleProofGallery.jsx` (kolom per supplier, thumbnail tiap round dgn lencana R<n> & titik hasil, lightbox
  prev/next/Esc) + `ProofImage.jsx` (muat bukti via axios blob agar header Authorization/X-Entity-Id ikut; cache object URL).
- Dipasang di `SampleTypeTabs` setelah tabel perbandingan, hanya untuk jenis yang diminta. Testing agent iterasi 30: 100%.

## Tab per Jenis di hub R&D — Labdip / Handfeel / Proofing (Master) (2026-09-18)
- View baru `rnd-labdip`, `rnd-handfeel`, `rnd-proofing` → `features/rnd/SampleTypeGalleryView.jsx` (+ `SampleTypeCard.jsx`),
  cermin "Desain & Pattern (Master)": KPI, cari + saringan (status/supplier/hasil/skor/ronde/bukti), grid kartu bersampul
  foto bukti, tombol "Sampel <Jenis> Baru" (SampleFormModal `lockType`), klik kartu → rincian dengan tab jenis aktif
  (`initialType`). Dibatalkan disembunyikan kecuali difilter. Terdaftar di hubTabs/navMeta/roles/AppViewRouter.
- Testing agent iterasi 31: frontend 100% (MD + admin, buat dari tab, filter, regresi papan & desain).

### 2026-06 — Peran & Hak Akses (custom role, 3 tingkat per modul)
- Backend: `access_modules.py` (katalog 24 modul: label/deskripsi/resources/nav, `apply_levels`, `nav_for_levels`),
  `services/custom_role_service.py` (buat/ubah/hapus/reset; peran kustom tersimpan di `custom_roles`, matriks izin di
  `permission_settings.matrix`; registry `role_registry.register_custom_roles` disinkron saat start & tiap perubahan),
  router `/api/access/modules|roles` (izin permission.view/update). Admin dikunci; bawaan tidak bisa dihapus/ganti nama.
- Frontend: tab **Peran & Hak Akses** di Badan Usaha & Akses (`RoleAccessPanel`, `RoleEditorDrawer`, `RoleModuleRow`,
  `RoleMenuPreview`): kartu peran + jumlah akun, segmented 3 tingkat per modul, salin dari peran, semua-modul cepat,
  pratinjau menu nyata (buildNavGroups dgn overlay `__preview`), dialog konfirmasi perubahan, peringatan modul sensitif.
- `roles.js`: `registerDynamicRoles` (registry/ROLE_NAV/ROLE_HOME dinamis, ROLE_OPTIONS ikut → formulir akun),
  `roleCanSee` rekursif inherit. `App.js`: poll `/api/roles` + `/auth/me` tiap 60 dtk + event `kn:roles-changed`.
- Testing agent iterasi 32: backend 14/14, frontend 100%.
- Catatan lingkungan: frontend dilayani bundle statis → `bash scripts/rebuild_frontend.sh` setelah ubah src;
  backend/.env butuh CORS_ORIGINS eksplisit (bukan `*`).

### 2026-06 — Notifikasi sinkron dengan Peran & Hak Akses (iterasi 33)
- `services/notification_scope.py`: filter kotak notifikasi = audiens (peran/all/peran acuan/recipient_user) ∧ relevansi
  (link layar tujuan harus boleh dibuka: modul ≥ Lihat). Admin melihat SEMUA notifikasi kecuali yang ditujukan langsung
  (`recipient_user`) ke orang lain — perbaikan dari temuan iterasi 33 (sebelumnya admin hanya audiens admin/all).
- `services/turn_notification_service.py`: penerima "Giliran Anda" digerbang izin dari matriks (peran bawaan + kustom),
  admin/manager dikecualikan kecuali rule menyebutnya. `GET /api/access/roles/{id}` → `turn_alerts`; editor peran
  menampilkan `role-editor-turn-alerts`.
- Setup ulang env baru (2026-06): clone repo pandeyoga/KNHOST; peran kustom `cr_staf_penagihan` + akun penagihan@
  dibuat ulang via API (finance, accounting=view, ar=manage). Pytest `tests/test_notifications_iter33.py` 10/10 lulus.


### 2026-06 — Editor peran: pratinjau notifikasi live, duplikat peran, pindah akun massal
- Backend: `POST /api/access/roles/preview` (turn_alerts & screens dari tingkat yang belum disimpan),
  `POST /api/access/roles/{id}/move-users` (pindah semua akun ke peran lain; admin ditolak). Audit `role_users_moved`.
- Frontend: `RoleNotifPreview` (diff vs tersimpan: "(baru)"/"(hilang)"), tombol `role-card-duplicate-<id>` → editor
  mode duplikat (acuan = peran sumber; hanya modul yang diubah dikirim agar izin parsial tetap setia), panel pindah akun di
  `RoleAccountsList` dengan `RoleDangerDialog` kind "move"; editor tetap terbuka & disegarkan setelah pindah.
- Testing agent iterasi 37: backend 11/11, frontend 100%.

## Design Studio — Nilai hanya saat ACC · HOLD · Label Proofing · Riwayat detail (2026-09-18, repo pandeyoga/KNHOST)
Problem statement: lanjutkan ke Desainer — (1) point hanya di akhir ketika ACC; (2) desain ACC bisa di-HOLD → tidak bisa masuk proofing R&D,
label jelas + filter; label proofing (on progress / finished) + info master produk; navigasi cepat tanggal; (3) history lebih detail.
Pilihan user: hapus semua penilaian kecuali dialog ACC; hold oleh admin/manager (izin `rnd.hold`, dapat diatur di matriks akses);
acuan tanggal ACC & update terakhir (bisa dipilih); riwayat lengkap (diff field, berkas, hold, nilai, proofing & master produk) + filter jenis; seed demo repo.
- Backend: `design_studio_service` — `transition` hanya menyimpan nilai pada `approve` (revisi mengabaikan score), `activate` ditolak saat hold;
  `set_hold`/`release` (field `on_hold`, `hold`, `hold_history`, event `hold`/`release_hold`); `attach_proofing` (batch md_samples/md_specs/products →
  `proofing{state none|in_progress|finished|master, label, detail, samples[], specs[], master_product}`); `log_external` (peristiwa lintas modul).
  `design_gallery_service` — `update_gallery` menulis event `updated` + `changes[{field,label,from,to}]`, `delete_file` → `file_deleted`, unggah colorway ikut timeline,
  filter `on_hold`. `rnd_sample_service` — `_assert_design_not_held` (proofing ditolak saat HOLD) + hook `proofing_requested/finished/decided`.
  `rnd_spec_service` — hook `spec_linked`, `master_product_created`, `master_product_released`. Router: `POST /design-gallery/{id}/lifecycle/hold|release-hold`
  (izin `rnd.hold`), `GET /design-gallery/{id}/history?kind=`; endpoint `/versions/{v}/score` DIHAPUS. `permissions_config`: `rnd.hold` admin+manager (merge otomatis saat restart).
- Frontend: `RndDesignsView` (KPI hold/proofing/master klik-saring, filter `rnd-filter-hold|proofing`, `DateQuickNav`, kartu ber-lencana hold/proofing/master/tanggal),
  `DesignDetailPage` (lencana + banner hold, tab Proofing R&D `ProofingPanel`, tab Riwayat `HistoryPanel` menggantikan TimelinePanel), `LifecycleActions`
  (hold/lepas hold via `canHold`, nilai hanya di dialog ACC, revisi tanpa nilai), `VersionsPanel` tanpa tombol nilai, `DesignBadges`, `SampleFormModal` menandai desain HOLD.
- Seed demo: `scripts/seed_design_hold_proofing_demo.py`. Testing agent iterasi 39: backend 14/14, frontend 100%.


## Backlog
- P2 (Akses): ganti `window.confirm` hapus/reset peran dengan modal in-app — SELESAI 2026-06 (`RoleDangerDialog`).
- P2 (Akses): daftar akun pemakai peran di editor — SELESAI 2026-06 (`RoleAccountsList`, `accounts[]` di GET /api/access/roles/{id}).
- P2 (Akses): router tuple peran hardcoded mengenal peran kustom — SELESAI 2026-06 (`role_registry.role_in` di design_requests, internal_requests, rnd, rnd_org, dan `dependencies.require_role`; frontend `roleIs` di rnd/design/designer views; deep-link `?view=` untuk peran `cr_*` menunggu registrasi peran kustom). Testing agent iterasi 35–36: backend 100%, frontend 100%.
- P2 (RND): revoke object URL cache galeri bukti (LRU) untuk sesi panjang; kolom galeri responsif di layar sempit.
- P1 (RND): sticky footer/ringkasan aksi di rincian sample; skeleton KPI saat memuat (kilat 0 ~200ms).
- P1 (RND): testid per-supplier di `SampleSendModal` (`sample-send-supplier-<id>`); galeri foto bukti per tab jenis.
- P1 (RND): perbaikan custom role & access — SELESAI 2026-06 (lihat bagian Peran & Hak Akses).
- P1: notifikasi WA otomatis kode pickup ke pelanggan saat pengiriman pickup dibuat (sekarang tombol WA manual).
- P1: kadaluarsa kode pickup / regenerasi kode oleh admin; batas percobaan kode salah → kunci sementara.
- P1: tampilkan badge moda & kode pickup di Perjalanan Pesanan (OrderJourneyPanel) dan Meja Admin Gudang.
- P2: biaya kirim ekspedisi → jurnal beban pengiriman (GL) / tagihan ke pelanggan.
- P2: jadwal kendaraan (kalender), riwayat perawatan, KM.
- P2: peta posisi live untuk semua pengiriman aktif di dasbor.

---
## SESI 2026-09-18 — Lanjutan repo github.com/makkansbdb/KN: Desainer & R&D

### Problem statement (asli)
Desainer: (a) Ringkasan diperbaiki — tiap ronde revisi tampil ke bawah (judul ronde → foto dikirim → komentar revisi → ronde berikutnya…); tab "Ronde & Nilai" dihapus, nilai di akhir saat ACC. (b) Tab Final: tanpa varian warna — hanya mockup + file desain asli yang bisa diunduh. (c) Galeri Desain → showcase desain ACC saja (tanpa tambah), detail: foto, file asli, mockup, info desain & pattern, produk pemakai + status R&D; filter diperbanyak. (d) Rapikan pop-up.
R&D: (e) Interface labdip/handfeel/proofing seperti desainer: detail ronde, komentar sampai ACC, history, tanggal terima. (f) Spesifikasi produk dikonsolidasikan ke tab sample (input saat create). (g) Rapikan pop-up. (h) Nama & warna supplier diisi saat sampling ACC (bukan awal), sinkron ke master terkait. (i) UX master data yang lahir dari R&D dibuat jelas (varian / induk).
Pilihan user: clone ulang repo; Desainer dulu lalu R&D; nilai tetap satu kali di dialog ACC (tanpa duplikasi); dialog "Pilih pemenang" wajib isi warna supplier + otomatis buat/tautkan master data dengan preview.

### Implementasi (2026-09-18)
- Backend: `design_studio_service.final_requirement` → mockup≥1 + source≥1 (colorway tidak wajib); kind `source` (file bebas ≤50MB) di `add_file` & `upload_kind_file`; `GET files/{fid}?download=1` → attachment.
- Backend R&D: `SampleInput.spec` (spec dibuat & ditautkan saat create sample); `SampleDecideBody` + `supplier_color_name/code`, `approve_spec`, `product_sku/name`; `decide_sample` sinkron warna supplier ke `color_library.supplier_variants` (+factory_name), ACC spesifikasi → produk lahir; `master_data_of()` di GET sample.
- Frontend Desainer: `RoundsTimeline.jsx` (Ringkasan linimasa), tab versions dihapus, `FinalPanel`/`FilesPanel` (mockup + source), dialog ACC tanpa jumlah warna, `DesignImage.jsx` (gambar via axios blob).
- Frontend Galeri: `DesignGalleryView.jsx` showcase + 7 filter, `DesignShowcaseModal.jsx`.
- Frontend R&D: `SampleRoundList.jsx` linimasa per supplier×jenis (dikirim/tenggat/diterima, bukti, catatan, keputusan penilai), `DecideModal.jsx` 3 langkah + preview master data, `SampleMasterDataPanel.jsx`, `SampleFormModal.jsx` bagian 3 spesifikasi, tab hub "Spesifikasi Produk" dihapus.
- Env: `CORS_ORIGINS` di backend/.env wajib daftar origin (bukan '*'); frontend bundle statis → `bash scripts/rebuild_frontend.sh`.
- Uji: testing agent iterasi 40 — backend 8/8, frontend semua alur lolos.

### Backlog / P1–P2
- P1: audit pop-up lain di R&D (RoundActionModal, SampleSendModal, SampleFinishModal, IssueMaterialModal) untuk konsistensi font/spacing.
- P1: seed sample "assessed" ber-warna target agar field warna supplier langsung terlihat di demo.
- P2: hapus kode/komponen colorway yang tak lagi dipakai (ColorwaysPanel, VersionsPanel) bila sudah dipastikan tak dirujuk.
- P2: GET /api/color-library/{id} (saat ini hanya list) untuk layar detail warna versi supplier.

### 2026-09-19 — Pop-up R&D seragam + Riwayat warna supplier
- Refactor 5 pop-up R&D ke shell `FormModal` + `RndField` (Field/Hint/Footer): font 13.5px judul / 11px subjudul / 10.5px label / 11.5px isi, jarak `gap-3` seragam.
- Pustaka Warna: badge "N versi supplier" pada kartu → `SupplierColorVariantsModal` (supplier, nama & kode warna supplier, sampel asal dengan deep-link, tanggal ACC).

### 2026-09-19b — Pustaka Warna: sub-tab Warna Internal / Warna Supplier + keterkaitan
- Sub-tab terpisah; tab Warna Supplier = tabel versi warna per supplier (label supplier jelas), cari nama/kode warna supplier, filter supplier & "sudah/belum jadi produk".
- Modal keterkaitan 3 kolom: Warna internal ↔ Versi supplier ↔ Master produk (+ daftar sample R&D) — backend `color_links` & `list_supplier_variants` di color_service.

### 2026-09-19c — Spesifikasi WAJIB menyatu (1 sample = 1 spesifikasi)
- Koreksi user: tab Spesifikasi dihapus tetapi logikanya wajib & menyatu di form Labdip/Handfeel/Proofing (bukan opsional).
- Form 4 langkah (Acuan → Spesifikasi WAJIB adaptif per jenis → Brief → Kapan); server menolak sample tanpa spesifikasi; validasi per jenis.
- Panel Spesifikasi di rincian (ringkasan, ubah sebelum ACC, "Lengkapi spesifikasi" untuk data lama); ringkas spesifikasi di kartu.
- 2026-09-19d: dropdown "Acuan spesifikasi" dihapus (membingungkan); form 3 langkah; pesanan pelanggan dipindah ke langkah Brief. Anti-duplikasi spesifikasi lewat multi-jenis dalam satu permintaan / "Tambah jenis".

### 2026-09-19e — Dua warna (internal + supplier) visible di semua menu
- Denormalisasi warna internal, versi warna supplier (dilabeli supplier), dan supplier pemenang R&D ke master produk; disinkronkan saat ACC sampling / ACC spesifikasi (+ backfill).
- `ProductColorChip` dipakai di pemilih produk, PO (opsi & baris item, difilter supplier PO), RFQ, katalog (header & kartu varian), detail produk, panel master data R&D.

### 2026-09-19f — Special Order Fase 1
- Menu "Pesanan Khusus" di PENJUALAN (bawah Kasir & Portal). Intake terstruktur 4 langkah (pelanggan & tipe permintaan printing/labdip/handfeel; referensi; spesifikasi ringkas/lengkap; jumlah-harga-tenggat) + unggah referensi pelanggan.
- Routing otomatis saat disetujui: printing → Permintaan Desain (+referensi); labdip/handfeel → Spesifikasi + Permintaan Sample R&D (tertaut special_order_id, exclusive_customer_id). Rincian OD: lini masa fase + rantai dokumen (OD ↔ Desain ↔ Sample ↔ SKU ↔ PR/PO ↔ SO).
- Backlog Fase 2: ACC pelanggan atas sample, harga final (kontrak + margin), eksklusivitas SKU ditegakkan di Kasir/SO, PR/PO ke supplier pemenang, hapus "Buat SKU" ad hoc, proofing otomatis saat desain ACC, kartu ringkas di Meja Admin Sales.

### 2026-09-19g — Special Order Fase 2 (ACC pelanggan · harga final · eksklusivitas · proofing otomatis)
- Backend `services/special_order_phase2.py`: `customer_decide` (acc/revisi/tolak + catatan, tanggal, kontak; revisi → sample R&D baru otomatis dgn spesifikasi diwarisi, OD kembali Sampling; tolak → cancelled), bukti (`customer-decision/evidence`), `pricing_preview` (kontrak supplier pemenang + margin default 30% dari `system_settings{scope:special_order}.default_margin_pct`), `lock_price` (sales/sales_admin/manager/admin, wajib ACC pelanggan; harga & eksklusivitas ditulis ke master produk), `unlock_price` (admin + alasan, ditolak bila PR/SO sudah lahir), `assert_customer_allowed` (SO/POS ke pelanggan lain/walk-in → 400), `on_design_approved` (desain OD printing ACC → sample proofing + notifikasi MD).
- `special_order_routing`: fase baru `pricing`; `_phase` memakai sample terakhir (revisi) & kunci harga; `chain_of` → `review` + `pricing`. `approve_special_order` tak lagi membuat SKU ad hoc untuk OD terstruktur; PR/konversi SO OD terstruktur ditolak sebelum harga dikunci; PR memakai product_id & harga kontrak pemenang.
- `rnd_spec_service`: `exclusive_customer_id` diwariskan ke produk; `decide_sample` menstempel eksklusif pelanggan ke produk.
- Frontend: `SpecialOrderCustomerApprovalPanel.jsx`, `SpecialOrderPricingPanel.jsx` (di rincian OD setelah disetujui), badge "Eksklusif: <pelanggan>" di POS (`PosProductCard`), katalog (`VariantCard`), rantai OD.
- Testing agent iterasi 46: backend 9/9, frontend lolos. Catatan: relock setelah unlock membaca ulang harga kontrak sample pemenang terbaru (disengaja).

### Backlog Fase 3 OD
- P0: PR/PO otomatis ke supplier pemenang (pakai kontrak) + tracking produksi → konversi SO dengan harga final (tombol sudah digerbang kunci harga).
- P1: kartu ringkas OD di Meja Admin Sales; notifikasi WA ke pelanggan saat sample siap ACC.
- P1: routing OD printing mengisi Kategori Pattern/Design otomatis (sekarang desainer harus melengkapi via "Ubah" sebelum "Buat & buka desain").
- P2: pengaturan default margin OD di Pusat Pengaturan (sekarang hanya via DB `system_settings`).

### 2026-09-19h — Special Order Fase 3 (PR/PO otomatis · SO harga final · kategori desain otomatis)
- `lock_price` {margin_pct, warehouse_id, auto_po} → `auto_procure`: rilis SKU eksklusif ke produksi → PR (source special_order, "Sistem (OD)") → approve → PO ke supplier pemenang (harga kontrak pemenang; kontrak diikat ke product_id di `decide_sample`; jaminan harga di `auto_procure`), tenggat = expected_delivery OD, gudang default aktif pertama entitas → OD in_production. `POST /special-orders/{id}/procure` untuk ulang. PO completed (`recompute_po_status`) → OD ready. Supplier grup ditolak oleh aturan antar-entitas (pesan jelas).
- `convert-to-so` (in_production/ready + harga terkunci): SO memakai `pricing.product_id` & harga final terkunci (`special_order_price`, `cost_price`, `margin_pct` di baris SO) via `source_special_order_id` di `create_order`.
- OD printing: `pattern_category_code`/`design_category_code` di form intake (opsional) + fallback kategori pertama aktif → DSR siap "Buat & buka desain".
- `POST /special-orders/{id}/submit` (draft → pending_approval; OD dengan submit_for_approval selalu masuk persetujuan tanpa ambang). UI: tombol "Ajukan persetujuan", pilih gudang & toggle PR/PO otomatis di panel harga, chip PO, "Buat PR/PO sekarang".
- Testing agent iterasi 47 (17/18 → bug kontrak diperbaiki) & 48 (retest).

### 2026-09-19i — Special Order Fase 4 (pengiriman otomatis · kartu OD di Meja Admin Sales)
- lock-price (auto_po) → SO OD lahir otomatis (harga final). PO OD diterima gudang (`recompute_po_status` completed; atau setelah QC accept di `qc_service`) → `on_goods_received`: stok direservasi ke SO (backorder), SO confirmed otomatis, tugas Surat Jalan (outbound) lahir. `dispatch_task` → SJ terbit → OD shipped (`on_shipment_dispatched`); SO mark-delivered / logistik delivered → OD done (`on_delivered`). Kegagalan (mis. karantina QC) tercatat di `shipping_error`; tombol/endpoint `prepare-shipment` untuk mengulang. Panel `SpecialOrderShippingPanel` di rincian OD; `chain_of` → outbound_tasks & shipments.
- Meja Admin Sales: antrean `od_acc_pelanggan`, `od_kunci_harga`, `od_siap_kirim` (`work_desk_service` + `special_order_phase2.desk_rows`); ROW_TARGET special_order → deep-link `SpecialOrders` (`focusDoc`) langsung membuka rincian.
- Testing agent iterasi 49: backend 14/14, frontend lolos.
### Backlog OD
- P1: notifikasi WA ke pelanggan (sample siap ACC, barang siap kirim). P2: pengaturan margin OD di Pusat Pengaturan. P2: pengiriman fisik (pick/dispatch) tetap manual gudang — by design.

### 2026-09-19j — Modul Marketing & Sosial Media (baru)
- Backend `services/marketing_service.py` + `routers/marketing.py`: kampanye (`mkt_campaigns`), post (`mkt_posts`) dgn alur idea→draft→review→approved(manager/admin)→scheduled(publish_at+PIC)→published(+url), lampiran (storage), performa manual (metrics + history), bahan konten (desain galeri ACC/produk/OD), analitik per bulan/platform/kampanye, job scheduler `content_reminder` (15 mnt) → notifikasi PIC in-app/WA. Resource izin `marketing` (admin/manager penuh; designer/sales/sales_admin view/create/update). Modul akses "Marketing & Sosial Media".
- Frontend `features/marketing/`: ContentCalendar (bulan/daftar, filter, klik sel → buat), PostFormModal, PostDetailModal (aksi alur, lampiran, performa, riwayat), Campaigns, MarketingAnalytics. Menu standalone "Marketing & Sosmed" (hub marketing-hub: Kalender Konten · Kampanye · Performa).
- Testing agent iterasi 50: backend 30/30, frontend lolos. Tanpa AI & tanpa API sosmed (sesuai pilihan user).
### Backlog Marketing
- P1: template konten & duplikasi post; tampilan minggu; ekspor kalender PDF. P2: posting otomatis via Meta/TikTok API; AI caption (jika diinginkan); UTM link builder & pelacakan prospek ke CRM.

### 2026-09-19k — Marketing lanjutan: Akun Sosmed per PT · Dashboard · Ekspor PDF · Multi-entitas
- `services/marketing_ext.py`: master `mkt_accounts` (per badan usaha, banyak akun; validasi dup & kepemilikan PT/platform saat dipakai di post → snapshot `post.accounts`), `dashboard()` (KPI bulan ini vs lalu, tren 6 bulan, per platform/akun/PT, top, 7 hari ke depan, terlambat, tingkat tepat waktu ≤60 mnt), `calendar_pdf_html()` → weasyprint (A4 landscape, kop PT/Grup, grid, daftar rinci caption ≤120, ringkasan kampanye).
- Multi-entitas: posts/accounts/dashboard/PDF menerima `entity_id=all|ent_x` (resolve_list_scope); tiap respons post membawa `entity_name`; buat konten/akun selalu ke PT aktif (ditampilkan di form). UI mengikuti pemilih PT di header: badge PT di kalender/daftar/rincian saat "Semua".
- Tab hub: Kalender Konten (tombol Ekspor PDF) · Dashboard & Performa · Kampanye · Akun Sosmed. Testing agent iterasi 51 (16/16 + UI) & 52 (retest badge PT lolos).

### 2026-09-21 — Perapian UI Pesanan Khusus
- `SpecialOrderInfoPanels.jsx` ditulis ulang: panel Rincian item custom / Info pelanggan / Riwayat status memakai gaya seragam panel Fase 2–4 (section-card !p-3, kicker label, sel grid), label Bahasa Indonesia, tidak ada konten menempel tepi kartu; grid `items-start`. Popup Tolak → FormModal standar; label "Reject" → "Tolak"; kolom tabel "Expected Del." → "Perkiraan kirim". Testing agent iterasi 53: lolos (tanpa overflow).

---

## Sesi 2026-09-21 — Perbaikan fokus input form R&D (repo github.com/pandeyoga/KNHOST)

### Problem statement (asli)
"saya ingin anda lanjutkan development dari repo ini https://github.com/pandeyoga/KNHOST — perbaiki beberapa form di menu RND,
ketika saya buat labdip, proofing, dan handfeel ketika saya ingin isi form itu hanya setiap satu charakter saya harus klik kolom
form kembali sepertinya ada bug front end." Pilihan user: clone branch main; periksa & perbaiki semua form RND dengan pola sama.

### Akar masalah
`features/rnd/SampleSpecFields.jsx` mendefinisikan komponen pembungkus `L` DI DALAM fungsi render → tiap keystroke induk re-render,
referensi komponen baru → React unmount/remount `<input>` → fokus hilang. Pola sama di `features/rnd/design/FinalPanel.jsx` (`Row`).

### Yang dikerjakan
- `L` (SampleSpecFields) dan `Row` (FinalPanel) dipindah ke module scope. Berdampak ke form Labdip/Handfeel/Proofing
  (`sample-form-modal` dari `rnd-samples` & galeri `rnd-labdip|handfeel|proofing`) serta `SampleSpecPanel`.
- Audit pola yang sama di seluruh `frontend/src`: sisa kasus (LocationFields `L`, DocRefsPanel/ReallocateRollsModal `Row`,
  CoreWidgets `FavStar`, PdfEditorTabs `Diff`, DomainRegistryParts) TIDAK membungkus input → tidak menimbulkan bug fokus; dibiarkan.
- Lingkungan: backend/.env CORS_ORIGINS eksplisit + SESSION_COOKIE_SECURE; seed_realistic dijalankan; bundle frontend di-rebuild.
- Uji: testing agent iteration_54 — 21/21 field mempertahankan fokus saat mengetik kontinu di semua titik masuk.

### Catatan
- `sample-spec-sku` sengaja meng-uppercase ketikan (perilaku lama, bukan bug).
- Frontend statis: setelah ubah src → `setsid nohup bash /app/scripts/rebuild_frontend.sh > /app/.rebuild.out 2>&1 &` (±8 mnt).

---
## Sesi 2026-09-21 — Verifikasi & perbaikan audit kode (PDF Bagian I & II, 92 temuan)
**Problem statement:** clone repo abagayafaja/KN, verifikasi 92 temuan audit (KN-A01..A13, B01..B35, C01..C10, D01..D26), laporkan validitas, perbaiki. Pilihan user: semua 92 temuan; laporan ringkas di chat; indeks unik dibuat (fail-safe log).

**Hasil verifikasi:** 84 VALID (diperbaiki 71), 5 VALID-DITUNDA (butuh desain UoM/arsitektur), 3 PARSIAL/keputusan desain (B26, C08 sebagian, D08), 2 laporan observasi tanpa perbaikan kode (C09 to_list, C10 except-pass), 0 TIDAK VALID.

**Perbaikan utama:**
- `entity_scope.guard_doc()` — penjaga entitas satu baris untuk jalur tulis: gl void, cash void, vendor_bills (submit/approve/reject/pay/cancel), cycle_count semua aksi, purchase_returns seluruh siklus + list scope, sample_orders (ketat), ar_receipts, hr_payroll, interco (`_guard_party`), fixed_assets, landed_cost, bank PATCH, cash_advances (ketat).
- Mesin status: escalate inbound/outbound berprasyarat status (C01/C02), resolve wajib `escalated`; PO approve CAS + larang penyetuju sama dua tingkat (B04/D05); PO terminal tidak dihidupkan lagi saat penerimaan (D01); `_post_bill` prasyarat status (B05); special order CAS (B10); SO approve blok bila ada approval ditolak (D02); kontrabon settle_bills cek status + `$expr` (D03).
- Atomik: claim saga pada kontrabon pay (B01), settle_return (B02), realize PR→PO (B03), store credit redeem (B06), deposit CAS (B08), allocations `$push` (B07).
- Indeks unik nomor dokumen 22 kolom + `(source_type,source_id)` jurnal aktif (A12/B09); 13 generator "max+1" → `next_doc_number(scheme="shared")` (A12/D15).
- Konstanta bersama: `OPEN_PO_STATUSES`, `PHYSICAL_ROLL_STATUSES` (A11/C05/D10), `GREEN_OUT` RFID (C03), `role_rank` → registry (C04), `services/tolerances.py` (A13/B28).
- Nilai: HPP GR pakai harga neto (A09), short-pick pertahankan diskon header (A10), nota kredit harga neto (B23), retur beli rata-rata berbobot (B24), PPN retur beli dicatat & dibalik, `returned_amount` termasuk PPN (B20/B21), on_order_qty (B14), goods_back rebuild gudang asal (B13), landed cost ke roll pecahan (B17), RFID tag ikut transfer (B19), void kuitansi netralkan baris realokasi (B25), opname tolak bila stok bergerak (B11), PO tolak produk kembar (B15).
- Meja peran & status: driver queue filter delivered (C08), designer/warehouse desk status nyata (D06/D07), so_status backorder fulfilled (D14), peringatan reservasi waiting_stock (D13).
- Frontend: faktor UoM dari master server + blokir satuan tak dikenal (C06), peringatan minimum potong di keranjang (C07), keranjang direset saat ganti PT (D20), jurnal tolak baris debit&kredit (D22), RollPicker reload saat ganti gudang (D23).
- Uji: `tests/test_kn_audit_2026_09_21.py` (+ `_extended.py` dari testing agent) masuk `gate.sh` default; uji lama /sample-requests dinonaktifkan (A08).

**Ditunda (backlog P1):** B12 (opname hanya potong bucket available), B16 (rebuild_balance abaikan unit roll), B18 (length_initial agregat), B22/B27 (konversi satuan retur & create_roll), B26 (WAC abaikan roll berbiaya nol — keputusan desain), D04, D08, D11, D12, D16, D17, D18, D19, D21, D24, D25, D26, C09, C10.
**Gate merah pre-existing (bukan dari sesi ini):** verify_entity_scoping (categories.py design_gallery), audit_entity_isolation (data_hygiene_log), POC E-3 (POST /customers wajib PIC).

### Sesi 2026-09-21 (lanjutan) — sisa audit
- **Konversi satuan (B12/B16/B22/B27):** `roll_service.to_base_qty()`; `create_inbound_roll` menghormati `unit` (yard→meter); `rebuild_balance` mengonversi roll ber-unit lain; opname susut memotong bucket hold/quarantine/blocked/damaged/wip lalu reserved/committed dengan log (bukan diam); retur jual dinormalkan ke satuan dasar (`_normalize_return_items_to_base`), batas retur & harga CN per satuan dasar (`base_quantity`). B18 dicek ulang: jalur scan-label & GR sudah konsisten satuan dasar (tidak perlu perubahan).
- **Frontend D17–D19, D21, D24–D26:** `useEffectivePrices` kanal galat + retry, checkout diblokir bila harga kontrak gagal; kartu omzet dari agregat server `stats/summary.revenue` (grand_total); `computeOrderPreview(items, disc, settings, {cfgSection, taxOverride})` satu cermin server — PO buat/ubah menghormati `purchasing.allow_*_discount` & tax_mode; `kgPerBaseUnit` cabang basis berat; header `X-Total-Count/X-Truncated` + banner terpotong di Stok, join produk tak lagi dipangkas 1.000; antrean luring menyimpan `entity_id` saat direkam & memakainya saat sinkron.
- **Gate lama:** categories.py motif ter-scope; `data_hygiene_log` SCOPED (+inherit global); POC E-3 pakai `assigned_sales_id`; entri REVIEWED /sample-requests basi dihapus dari verify_atomic_claim.
- **C10:** 74 titik `except: pass` → `logger.warning("[fungsi] efek samping gagal diabaikan: %s")` di 43 berkas.
- **Temuan baru (pre-existing, belum diperbaiki):** `bash scripts/gate.sh --ci` masih menunjukkan ±28 gate/POC merah lama yang tidak terkait sesi ini (POC E-5/E-7/E-8/F-6/L/U/P/D/S/I drift, guard uom_vocab 4 layar opsi satuan hardcode, atomic_claim 16 endpoint belum ditinjau, auth_coverage residu gate, i18n 37 label, escape_layers, role_label, warehouse_scope self-test, validate_compliance 3 item, approval_queues 2 pintu + turn_marks). Butuh sesi khusus per gate.

### Sesi 2026-09-21 (sesi 3) — D11, D16, gate merah
- **D11 ATP tunggal:** `services/atp_policy.py` (ATP = available + incoming≤14 hari − backorder aktif; ETA kosong = dalam horizon) dipakai `roll_service.rebuild_balance` (+`pending_demand_qty`), `fulfillment_service` supply (+`pending_demand`), `stock_bucket_service.atp_detail`.
- **D16 3-way tunggal:** `services/three_way_policy.py` (qty% & harga% dari `purchasing.bill_*_tolerance_percent`, rupiah dari `contra_bon.value_tolerance_rupiah`) dipakai vendor bill (`evaluate_match` + `value_tol`) & kontrabon (`policy`, `evaluate_bill_exceptions` harga memakai price_tol). `contra_bon.qty_tolerance_percent` ditandai tidak dipakai.
- **Gate merah 32 → 18:** HIJAU: uom_vocab (+self-test; 4 layar pemilih satuan dari master), atomic_claim (+self-test; 16 endpoint ditinjau — CAS/$inc baru di inbound_scan_label, special_orders approve/lock_price, rnd decide_sample), approval_queues, validate_compliance (prefix router), escape_layers, role_label, warehouse_scope self-test, modal_dismiss, create_modal (+self-test; bendera busy bukan form), POC F-6, POC I.
- **Masih merah (pre-existing, butuh sesi khusus):** 13 POC drift (E-5, E-7, E-8 G1/G2-G3, Cek Kenyataan Peran, F-6.7, Sesi 2026-06, L, U, P-0, P, D, S), audit_sales_roles_ux (panel 403 /md/desk, /warehouse-admin/desk, budget-keys, makloon claims), INV-GATE-01 anti-residu & auth_coverage (POC meninggalkan audit_logs/notifications/PR), ux_audit --strict (5 berkas: ProductRelations, DeliveryTable, Campaigns, MarketingAnalytics, +1), audit_i18n_id (37 label di 19 berkas).

### Sesi 2026-09-22 — restore repo & lanjutan seed/POC E-9
- **Restore lingkungan:** clone `github.com/makkajabsh/KN` → /app; pip/yarn install; `backend/.env` diisi `CORS_ORIGINS` eksplisit + `SESSION_COOKIE_SECURE` (T-02); backend restart (bootstrap fondasi); `seed_realistic.py` dijalankan 2× (idempoten, nol `[warn]`); frontend dibangun ulang (`scripts/rebuild_frontend.sh`, bundle statis).
- **Dua langkah seed yang dulu dilewati** kini terbukti lolos pada seed pertama & kedua: settlement antar-PT memakai `method: "transfer"` (F-08 netting butuh piutang balik) — label ringkasan seed diperbaiki; desain R&D `submit_design` → `approve_design` (F-6.7) termasuk cabang "pakai ulang".
- **POC E-9 (`backend/test_core_rantai_retur_poc.py`):** 44/44 PASS; cleanup kini juga menghapus `turn_marks` (doc_id POC) & `roll_cost_history` (roll POC) → `ukur_residu_poc.py --only e-9` = nol residu.
- **Smoke test agent:** login, /api/, interco settlements (transfer·posted), design-gallery (approved), interco transactions, login UI → semua hijau (`test_reports/iteration_smoke_restore.json`).
- **Berikutnya (dari backlog):** 13 POC drift merah pre-existing, INV-GATE-01/auth_coverage residu POC lain, audit_sales_roles_ux, ux_audit --strict, audit_i18n_id.


### Sesi 2026-09-24 — residu POC NOL + Marketing P1 (template · duplikasi · tampilan minggu)
**Problem statement:** lanjutkan repo github.com/pandeyoga/KNHOST dari titik henti `prune_orphan_turn_marks()`. Pilihan user: (a) selesaikan helper, residu POC G7, `gate.sh --full` hijau; (b) lanjut fitur berikutnya dari PRD.
- **Lingkungan:** clone → /app (.env dipertahankan; `backend/.env` + CORS_ORIGINS eksplisit & SESSION_COOKIE_SECURE). pip: `emergentintegrations` dipasang terpisah (konflik litellm di requirements). `seed_realistic.py` + `seed_e9_chain_demo.py`.
- **Residu POC → nol di semua 38 POC gate** (`scripts/ukur_residu_poc.py`): `poc_stock_guard.py` + `snapshot_new_ids()/purge_new_ids()/with_journal_cleanup()` (sidik `_id` audit_logs/notifications SEBELUM login, sapu sesudah). Dipasang di G-0, G-1, G-2, G-3, G-4, G-7, G-8, G-9, F, F-1, F US3/11/12, D (blok `__main__`) + fixture G-6/G-6b (juga `roll_cost_history`). `prune_orphan_turn_marks` sudah terpasang di 7 POC.
- **Gate:** `bash scripts/gate.sh --full` → **HIJAU** (129 PASS, 0 FAIL). Default gate hijau setelah fitur marketing.
- **Marketing P1:** `POST /api/marketing/posts/{pid}/duplicate {publish_at}` (salinan status Ide, `duplicated_from`, kampanye/akun hanya bila entitas sama); koleksi `mkt_templates` per badan usaha (`GET/POST /api/marketing/templates`, `POST …/{tid}/use` used_count, `DELETE …/{tid}` pembuat/admin/manager). FE: mode **Minggu** di Kalender Konten (`WeekGrid.jsx`), `TemplatePicker.jsx` di form konten baru, `DuplicatePostModal.jsx` + tombol "Simpan sebagai template" di rincian.
- **Uji:** testing agent iteration_59 — backend 15/15 (`backend/tests/test_iter58_marketing_templates_duplicate.py`), frontend 100%.
- **Catatan build:** `scripts/rebuild_frontend.sh` (nice+ionice) mati diam-diam di pod ini; build langsung berhasil ±40 dtk: `cd /app/frontend && GENERATE_SOURCEMAP=false CI=false DISABLE_ESLINT_PLUGIN=true yarn build`.
- **Backlog:** Marketing P2 (posting otomatis Meta/TikTok, AI caption, UTM builder → CRM); OD P1 notifikasi WA pelanggan; EPIC 7 multi-currency (ditunda).

### Sesi 2026-09-24 (lanjutan) — T-04 N+1 (2 PERBAIKI) + geser jadwal konten
- **Impor produk** (`routers/admin.py import_products`): validasi semua baris dulu, lalu satu `find({sku: {$in}})` → peta; SKU kembar dalam file diperlakukan created→updated (dry-run juga). Dry-run 2000 baris < 1 dtk.
- **Laporan stok mati** (`routers/reporting.py stock_aging`): mutasi terakhir per (produk,gudang) lewat satu agregasi `$group $max timestamp`; produk hanya yang ada di saldo. Output lama vs baru IDENTIK (threshold 0/30 × semua/ent_ksc/ent_kanda). Urutan kini benar untuk days=0.
- `memory/TRIASE_NPLUS1_2026-09.md` dibuat ulang: PERBAIKI = 0 (232 TIDAK TAHU tersisa).
- **Geser jadwal konten:** `POST /api/marketing/posts/{pid}/reschedule` (format YYYY-MM-DDTHH:MM, riwayat "jadwal digeser", audit `mkt_post_reschedule`, published ditolak); seret-lepas kartu di tampilan Minggu (`WeekGrid.jsx`), jam tayang tetap.
- Uji: testing agent iteration_60 — backend 15/15, frontend 100%; gate default hijau.

### Sesi 2026-09-24 (lanjutan 2) — audit Pustaka Warna
- Alur nyata terbukti: labdip KN-BLU-01 → ACC Palembang Silk House "Navy 07/NV-07" → produk KTN-NVY-PSH-01 (color_ref + supplier_colors + rnd_supplier) → tab Warna Supplier & modal keterkaitan (data demo kini ada).
- Diperbaiki: PATCH nama kosong → 400 (dulu menghapus nama); status selain active/inactive → 400 (dulu warna "hilang" dari semua filter); tombol UI mengikuti izin `color.*` (MD create+update kini terlihat); `list_supplier_variants` batch `_products_of_colors` (tanpa N+1).
- Uji: testing agent iteration_61 — backend 53/53, frontend 100%. Uji lama `tests/test_color_links.py` & `test_iter44_two_color.py` memakai id basi DB lama (bukan regresi).

### Sesi 2026-09-24 (lanjutan 3) — tab "Warna Pelanggan" di Pustaka Warna
- Permintaan user: tab warna customer terpisah; warna produk eksklusif pelanggan dipisah dari pustaka internal. Label UI "Warna Pelanggan" (gate i18n: customer → Pelanggan).
- Aturan pemisahan (turunan, tanpa mutasi data): warna = warna pelanggan bila `color_library.exclusive_customer_id` terisi (milik pelanggan, diatur di form Tambah/Edit) ATAU hanya dipakai produk ber-`exclusive_customer_id` (tak ada produk umum; pemakaian lewat `color_ref.id` atau `color_code`). Warna yang juga dipakai produk umum tetap di Internal + tampil di grup pelanggan berlabel "juga dipakai N produk umum".
- Backend: `color_service.color_usage/is_customer_color/list_customer_colors`, `GET /api/color-library?scope=internal|customer` (+ `is_customer_color` per baris), `GET /api/color-library/customer-colors` (per pelanggan yang terlihat di badan usaha aktif). FE: `CustomerColorsTab.jsx`, KPI Warna Pelanggan, field "Milik pelanggan (eksklusif)" di form, lencana di PantoneFinder.
- Data demo: `scripts/seed_customer_colors_demo.py` (idempoten) — KN-SJT-01 milik Toko Kain Sejahtera; produk eksklusif Butik Bali Indah SGK-BLI-TSK-01 (KN-GRN-03) & SGK-BLI-UNG-01 (KN-PUR-01) lewat alur labdip → ACC.
- Uji: iteration_62 backend 11/11, frontend 100%.

## Warna Pelanggan lanjutan (2026-09-24, repo mkaksjbd/KN)
Problem: lanjutkan 4 fitur — Warna di Profil Pelanggan · Kunci Warna Eksklusif (diblokir, butuh persetujuan manajer) ·
Kartu Warna PDF (swatch, kode, versi supplier + logo/nama badan usaha) · Penanda Warna Otomatis saat labdip ACC.
- Backend: `services/color_lock_service.py` (assert_can_use, permintaan izin di `color_library.use_requests[]`, approve/reject/revoke,
  notifikasi manajer & pemohon, auto_mark_owner), `services/color_card_pdf.py` (WeasyPrint + branding badan usaha aktif),
  endpoint baru di `routers/color_library.py`; kunci dipasang di `product_variant_service.save_product` (semua jalur produk),
  `rnd_spec_service` (buat/ubah spesifikasi) & `rnd_sample_service.decide_sample`. Izin baru `color.approve` (admin+manager).
- Penanda otomatis: sample ber-`exclusive_customer_id` diputus → warna sistem KN belum bertuan & tak dipakai produk umum/pelanggan lain
  menjadi milik pelanggan (`exclusive_source.kind=auto`). Ini juga menutup catatan lama "Pantone ikut pindah" — hanya warna KN yang ditandai.
- Frontend: CustomerColorsTab (lencana Terkunci/Otomatis, tombol Kartu Warna PDF, minta izin pakai, daftar izin), ColorUseRequestModal,
  ColorUseRequestsPanel, CRM `CustomerColorsSection` di Customer 360.
- Seed: `scripts/seed_customer_colors_demo.py` kini + warna baru KN-BLI-EMS-01 Emas Pura (SGK-BLI-EMS-01) → ditandai otomatis.
- Gate: pintu approve/reject izin warna didaftarkan di DOOR_EXEMPT (antrean = panel Warna Pelanggan + notifikasi), belum masuk KPI Pusat Persetujuan.
- Uji: backend 18/18, frontend ~90% (role sales tidak punya menu Pustaka Warna — desain peran lama).

### Backlog
- P1: antrean izin warna masuk Pusat Persetujuan/KPI beranda (butuh koleksi sendiri ber-entity_id).
- P1: tombol "Minta izin" langsung dari pesan tolak di form Produk/Spesifikasi.
- P2: akses sales ke tab Warna Pelanggan (read + minta izin) bila diinginkan.

## GRN + OCR Surat Jalan — Fase 0 selesai (2026-09-24)
Spesifikasi: `memory/grn_ocr/Prompt_Implementasi_GRN_OCR_SJ.md` (+ `prompt_sj_v2.txt`, `schema_sj_v2.json`). Aturan: satu fase per sesi.
Keputusan user: Fase 0 dulu · kunci OpenAI menyusul (Fase 4) · keputusan klien §7 = bawaan dokumen · foto contoh SJ diunggah saat Fase 4.
- 0.1 `advance` menolak tugas inbound (409 USE_RECEIVING_FLOW); tombol "Lanjutkan Tahap" nonaktif untuk inbound.
- 0.2 `receiving.*` di scan label dibaca lewat `value_of`.
- 0.3 Kunci baru `receiving.line_qty_tolerance_pct` (2%) → complete() + uom-options → GRCatchWeightModal.
- 0.4 Grade SSOT (`domain_registry.require_grade`): A+→A, C→BS, tak dikenal 400; semua dropdown grade via useDomainEnums.
- 0.5 Mobile: qty kosong, Terima juga untuk waiting_goods.
- 0.6 Override over-receipt/selisih konversi hanya pemegang `wms.approve`, alasan tercatat; UI askReason.
- 0.7 lookup kode supplier hanya aktif; indeks unik `uq_supplier_sku`; skrip `scripts/check_supplier_item_duplicates.py`.
- 0.8 KN-B15 juga di PR→PO & amandemen (`services/po_line_guard.py`).
- 0.9 Kamera mode manual mengisi Roll ID.
- Uji: `backend/tests/test_grn_phase0.py` 14/14; gate penuh HIJAU.
## GRN Fase 1 selesai (refactor tanpa perubahan perilaku)
- `services/inbound_complete_service.complete_task(task_id, payload, actor, *, ctx, via_grn)`; router `complete` = pembungkus tipis.
- `services/receiving_roll_service.py`: `create_label_roll` (label), `create_counted_roll` (hitung manual), + (Fase 2) `resolve_label_input`, `undo_receiving_roll`.
- Uji: `tests/test_inbound_complete_characterization.py` (golden dari kode LAMA) + phase0 + wms_advance → 16/16 (iteration_65).

## GRN Fase 2 selesai — backend GRN tanpa OCR (2026-06)
- Koleksi `goods_receipts` (nomor `{KODE}/GRN-NNNNN`, `uq_number`, `uq_active_key` unik parsial, indeks §4.3), `supplier_dn_profiles`; keduanya di `SCOPED_COLLECTIONS`; doc type `goods_receipt` di doc_refs.
- Modul izin `goods_receipt` (view/create/count/review/close/approve) sesuai §4.7; grup `warehouse_ops`.
- Konfigurasi baru: `receiving.mode` (legacy|grn, bawaan legacy), `receiving.blind_count` (bawaan true).
- Router `routers/goods_receipts.py` → layanan `services/goods_receipt_service.py` (buat, berkas, kepala SJ, baris, targets, start-count, scan-label/roll hitung/undo) + `services/goods_receipt_close_service.py` (rekonsiliasi §4.4, resolve, close §4.5, `ensure_remainder_task`, reject, cancel).
- Posting HANYA lewat `complete_task(..., via_grn=grn)` (boleh status `receiving`) / `receive_step` (makloon).
- Mode `grn`: scan-receive/scan-label/complete lama → 409 `GRN_MODE` (tugas setengah jalan ditandai `legacy_in_flight`); tugas milik GRN aktif → 409 `GRN_MANAGED`.
- Uji: `tests/test_grn_phase2.py` 6/6 (golden setara jalur lama, hitung buta, DN_DUPLICATE, pemblokir+resolve, tepat satu tugas sisa, batal bersih, mode grn, isolasi entitas). Total GRN 22/22.
- Temuan: `_create_inbound_tasks_for_po` menganggap tugas `qc_pending` "masih ada" (dan menimpa expected_qty-nya) → tidak dipakai untuk sisa; diganti `ensure_remainder_task`.
- Catatan uji lama: `tests/test_fase_sl_*.py` memakai id tugas seed LAMA tertulis mati (`wms_e2e3d9059660`) → 404 di DB seed baru (bukan regresi; dengan id seed sekarang 18/18 lulus).
## GRN Fase 3 selesai — frontend Kedatangan Barang (2026-06)
- Layar `?view=goods-receipts` (menu Gudang & Logistik → Kedatangan Barang): daftar per status + cari, wizard 2 langkah (mitra+PO/MKO+gudang → foto SJ multi-halaman, diperkecil 2048px JPEG 0,85, peringatan foto kecil), detail dengan stepper, tab Surat jalan (foto zoom/putar + kepala SJ + tabel baris + target), Hitung (scan label / roll manual / undo, hitung buta), Rekonsiliasi (tabel SJ vs hitung vs sisa PO, penyelesaian selisih via askReason, Tutup Penerimaan terkunci bila ada pemblokir, hasil posting & tugas sisa).
- Tab "Selisih Supplier": ringkasan per mitra dari GRN ditutup (`GET /goods-receipts/supplier-variance`).
- Tombol PO "Terima Barang di Gudang" → wizard GRN terisi supplier+PO+gudang; "Barang Masuk (lama)" tetap ada.
- Panel tugas lama: banner "Bagian dari GRN …" + baca-saja saat dihitung; setelah tutup "Diterima lewat Kedatangan Barang · SJ …".
- Endpoint baru: `GET /goods-receipts/partners`, `/{id}/rolls`, `/supplier-variance`.
- Uji: iteration_67 (backend 28/28 + UI dasar), iteration_68 (alur hitung→rekon→tutup→selisih, hitung buta, banner). Perbaikan: isian kepala SJ tidak lagi tertimpa/409 setelah "Isi manual".
- Data demo: KSC/GRN-00003 ditutup (100 yd PO-00014, klaim supplier) + tugas sisa 150 yd.

## GRN Fase 4 selesai — OCR OpenAI (2026-09-25, kode siap; kunci OpenAI belum ada)
- Backend: `services/ocr_openai_client.py` (satu-satunya import `openai`, Responses API + schema strict, store=False, kode galat OCR_*), `ocr_sj_v2.py` (PROMPT/SCHEMA sj-v2), `dn_rules.py` (parser angka, pilih declared, pola PO, cocok baris, cek total), `goods_receipt_ocr_service.py` (klaim CAS draft→reading, pembaca kedua on_doubt, `ai_usage_log` + biaya, rem anggaran + notifikasi ambang, penyapu malas >5 mnt, `pages_from_bytes`). Endpoint `POST /goods-receipts/{id}/read`, `GET /goods-receipts/usage?month=` (hak approve). Detail GRN kini memuat `ocr_enabled`.
- Integrasi: blok `openai` di integrations (`openai_api_key`/`openai_clear_key`, `POST /admin/integrations/openai/test`) + panel UI `OpenAiIntegrationPanel` (Admin → Master Data & Audit → Integrasi AI).
- UI GRN: draf → "Baca otomatis" + "Isi manual saja" (`grn-ocr-read`, `grn-manual-entry`), progres `grn-ocr-progress` (polling saat status reading), kotak hasil `grn-extraction` (gagal `grn-ocr-failed`, peringatan nama supplier/penerima `grn-ocr-warnings`, beda pembaca kedua `grn-ocr-header-diff` + sorotan emas di isian kepala SJ), kolom Tertulis (qty_text) + Qty, status "Angka ragu", baris ragu `grn-line-doubt-<n>` dengan pilihan kandidat/isi lain, beda per baris `grn-line-diff-<n>`. Tab "Biaya OCR" (`grn-view-tab-usage`, admin/manager/warehouse_admin).
- Skrip evaluasi `backend/tools/ocr_eval.py` (env `OCR_GOLDSET_DIR`, laporan akurasi per field, baris salah tak ditandai, biaya/lembar, gerbang §5).
- Mode tiruan: backend/.env `OCR_ALLOW_MOCK="1"` + model `mock-<fixture>` (tests/fixtures/ocr). Demo: `cd /app/backend && python ../scripts/seed_grn_ocr_demo.py` (KSC/PO-00014, angka ragu).
- Uji: GRN total 42/42 (iteration_69). Kegagalan je_debit sesi lalu = DB tercemar; dengan seed segar lulus.
- Bawaan tetap `receiving.ocr_enabled=false`. Untuk LIVE: isi kunci OpenAI, uji koneksi, nyalakan per entitas, pastikan nama model `receiving.ocr_model_*` valid di akun OpenAI.

## GRN Fase 5 makloon + Profil SJ otomatis + validasi manual OCR (2026-09-25)
- VALIDASI MANUAL: hasil OCR = usulan. Kepala SJ (`dn.verified`) & tiap baris OCR (`verified`) wajib dicek manusia sebelum `start-count` (400 NOT_READY, `verification_errors`). PATCH dn → verified + `corrected_fields`; PATCH baris (ubah apa pun / `verified:true`) → verified, koreksi vs `ocr_declared` → `corrected` + `corrected_fields`. UI: `grn-verify-summary`, `grn-dn-pending` + tombol "Konfirmasi kepala SJ", status baris "Belum dicek", tombol `grn-line-verify-<n>` (Sesuai foto), edit penuh `grn-line-edit-<n>` → `grn-line-edit-form-<n>` (kode, deskripsi, PO, qty, satuan, roll, kg, grade, lot, non-stok), label `grn-line-corrected-<n>`.
- FASE 5 MAKLOON: OCR memetakan SJ makloon ke langkah MKO `issued` (nomor MKO → nomor lama/PO di MKO → pola PO klien → satu-satunya MKO). Baris grade BS → `role: byproduct` bila langkah punya produk sisa; selain itu `role: ""` + pertanyaan (pemblokir sampai dipilih, `grn-line-role-<n>`). Barang sisa: satuan sendiri (tanpa konversi), roll hitung boleh tanpa lot (auto `SISA-<MKO>-<seq>`), wajib ada baris output langkah sama. Tutup → `receive_step` dengan qty output = hitung fisik, `actual_byproduct_qty`, `byproduct_lot`, `supplier_dn`, berat per roll (`MakloonReceiveRoll.weight_kg`, `MakloonReceiveIn.supplier_dn`). Tombol MKO `receive-step-grn-<seq>` "Terima lewat Kedatangan (SJ)" → `?view=goods-receipts&mko=&makloon=&wh=` (wizard preset).
- PROFIL SJ: `services/supplier_dn_profile_service.py` belajar saat GRN ditutup (idempoten per GRN) HANYA dari data yang dicek manusia: suara format angka (`locale_votes`, aktif otomatis ≥3 SJ & ≥80% bukti, bisa dikunci admin), nama lain pengirim (hanya varian yang memicu peringatan), pemetaan barang `item_map` (kode/deskripsi → produk, dipakai `match_line` method `profile`), statistik akurasi (baris dikoreksi/total). API `GET/PATCH /goods-receipts/dn-profiles[/{partner_id}]`. UI tab "Profil SJ" (`grn-view-tab-profiles`, `GrnProfilesPanel`). Info profil di hasil baca (`grn-ocr-profile`).
- Perbaikan: `normalize_grade` mengembalikan dict → grade baris manual/OCR kini tersimpan sebagai string.
- Uji: `tests/test_grn_phase5.py` (5) + seluruh GRN 47/47 (iteration_70). Fixture mock `sj_makloon.json`. Demo: `scripts/seed_grn_ocr_demo.py` (KSC/GRN-00004 supplier, KSC/GRN-00005 makloon — sudah ditutup oleh uji UI; MKO-00002 kini received, seed ulang lewat seed_realistic bila perlu).

## GRN Fase 6 packing list + nama/warna versi supplier + selisih di tagihan (2026-09-25)
- NAMA & WARNA VERSI SUPPLIER: `dn_rules.match_line` kini: profil → `supplier_sku` → kode warna supplier (unik) → skor nama (vs `supplier_items.supplier_item_name`, nama internal hanya cadangan) 60% + warna (vs `products.supplier_colors` nama/kode, warna internal cadangan) 40%; tanpa warna & nama supplier sama → ambiguous (manusia memilih). `_enrich_supplier_names` menempelkan data ke tugas. `match.via` disimpan; UI `grn-line-mapping-<n>` "SJ: … → KN: … · via …". Tombol `grn-line-catalog-<n>` → `POST /goods-receipts/{id}/lines/{n}/save-catalog` (tawaran simpan ke Katalog Supplier; warna tetap lewat ACC R&D). Sebelumnya: nama supplier TIDAK terpakai (tugas tak membawa supplier_item_name) & warna supplier diabaikan — sudah diperbaiki.
- FASE 6: `receiving.ocr_extract_packing_list=true` → `packing_list` → `line.expected_rolls` (`assign_packing_groups`: lot → item_hint ≥0,6 → tanpa petunjuk satu baris/urutan; tak terpasang = peringatan). Bisa dikoreksi di edit baris (`grn-edit-pl-<n>`, PATCH `expected_rolls`). Hitung: `GrnPackingChecklist` (`grn-pl-list-<n>`, `grn-pl-roll-<n>-<seq>`, `grn-pl-result-…`), roll diukur ber-`expected_seq` (roll PO: `grn_expected_seq`; makloon: `expected_seq`), `roll_check` (konversi m↔yd, beda >max(0,5;1%)), hitung buta: panjang PL disembunyikan sampai diukur. Rekon: `packing_list_mismatch` (bukan pemblokir).
- TAGIHAN: `GET /goods-receipts/doc-variance?po_id=|mko_id=&step_seq=` (izin goods_receipt.view ATAU vendor_bill.view; hanya GRN closed) → rows/summary/claims. UI `GrnDocVariance` di VendorBillDetailPanel (`vb-grn-variance`, PO atau MKO+langkah untuk tagihan jasa makloon) & VendorBillCreateModal (`vb-create-grn-variance`).
- Uji: `tests/test_grn_phase6.py` (10) · total 55 lulus + 2 skip (iteration_71). Demo: KSC/GRN-00007 (SJ-MOCK-PACK, review), KSC/GRN-00004 (angka ragu), VBM-00007 (selisih makloon).
### Berikutnya: kunci OpenAI + set emas SJ → Fase 7 beralih penuh (receiving.mode=grn per entitas, UI lama disembunyikan) · seed supplier_colors demo.
