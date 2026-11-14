# PR-T7 — Tombol dan panggilan data di layar mengikuti izin, bukan nama peran

| | |
|---|---|
| Gelombang | Jalur peran (sejajar dengan gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PR-T2 |
| Menutup temuan | PR-11, PR-16 (beserta butir layar PR-UX-08; ikut: PR-UX-41, PR-UX-42) |
| Keputusan | K-47 |
| Standar | §3.1 (Z2), §4 (L5), §6 |
| Lingkungan uji | keduanya (B untuk penjaga dan uji komponen; A untuk uji jalan layar) |

## Tujuan

Tombol yang tampil adalah tombol yang diizinkan server, untuk peran bawaan maupun peran kustom: peran kustom tanpa
peran dasar yang diberi izin melihat tombol kerjanya, dan peran berdasar Manajer yang izinnya dicabut tidak lagi
melihat tombol yang akan ditolak. Kerangka aplikasi tidak lagi memanggil endpoint yang pasti ditolak untuk peran
yang sedang masuk. Penjaga otomatis mencegah gerbang nama peran baru muncul di layar.

## Keadaan sekarang

| # | Fakta | Jangkar | Bukti |
|---|---|---|---|
| 1 | Layar memakai izin di 282 tempat (`can(`), tetapi masih memakai `roleIs(` di 52 tempat pada 36 berkas, ditambah daftar nama peran tertulis dan perbandingan `role ===` | `frontend/src/config/roles.js:156` (`roleIs`); `frontend/src/config/roles.js:445` (`can`) | [statik] hitungan pada HEAD; contoh di lampiran B Lampiran B |
| 2 | `roleIs` mengenali peran dasar; daftar tertulis dan `===` tidak pernah cocok untuk peran kustom | `frontend/src/config/roles.js:156` (`roleIs`); `frontend/src/features/production/ProductionParts.jsx:12` (`prodPerms`) | [dibaca] |
| 3 | Penjaga yang ada hanya memeriksa layar uang, pajak, dan alur pesanan, dan hanya mengenal enam id peran | `scripts/guardrails/verify_role_label.py:57` (`ROLE_IDS`); `scripts/guardrails/verify_role_label.py:66` (`AUTHORITY_ENDPOINTS`) | [dibaca] |
| 4 | `canCurrent` menjawab "boleh" selama konteks izin belum dimuat; konteks baru terisi setelah `GET /api/auth/me` karena jawaban login tidak membawa `view_resources` | `frontend/src/config/roles.js:451` (`canCurrent`); `frontend/src/config/roles.js:354` (`setAccessContext`) | [dibaca] |
| 5 | Peran kustom "Staf Penagihan Uji" (tanpa peran dasar; Uang Masuk "Kelola penuh", Pelanggan dan Pusat Persetujuan "Lihat saja") saat masuk memicu 403 berulang tanpa pesan pada `GET /api/finance/posting-failures/count` dan `GET /api/sales/keep-pending`, dan 404 pada `GET /api/hr/employees/me` | `frontend/src/components/CoreWidgets.jsx:8` (`usePostingFailureCount`); `frontend/src/features/sales_admin/KeepPendingPanel.jsx:30` (`load`); `frontend/src/features/hr/EmployeeSelfService.jsx:153` (`load`) | [dijalankan] `docs/audit/konfigurasi-peran-2026-11-13/bukti/ui_pengaturan_peran.js` butir C2 (hasil di `bukti/layar/hasil_ui_pengaturan_peran.json`); temuan PR-16 |
| 6 | Pusat Persetujuan memanggil semua kategori tanpa melihat izin; untuk peran yang sama enam kategori dijawab 403 dan layar menampilkan "Daftar ini belum lengkap…" | `frontend/src/features/approvals/approvalInboxData.js:50` (`grab`) | [dijalankan] skrip yang sama, butir C3 |
| 7 | Pratinjau menu di editor peran sama dengan menu yang tampil setelah masuk (9 layar) untuk peran kustom itu | `frontend/src/features/settings/entities/RoleMenuPreview.jsx:28` (`RoleMenuPreview`) | [dijalankan] skrip yang sama, butir B1b dan C1 — perilaku ini dipertahankan |
| 8 | Tombol "Tanya KN" memakai daftar peran tertulis di empat tempat | `frontend/src/components/AskKnButton.jsx:4` (`AI_ROLES`); `frontend/src/App.js:310` (`onAskKn`); `frontend/src/features/mobile/MobileOpsApp.jsx:138` (`AI_ROLES`) | [dibaca] |
| 9 | Aplikasi HP dipilih dengan `roleIs`; peran tanpa peran dasar selalu mendapat aplikasi umum | `frontend/src/features/mobile/MobileAppSwitch.jsx:48` (`salesMobileRole`) | [dibaca] |

## Perubahan

### Data

Tidak ada.

### Server

Hanya tambahan bendera kemampuan pada jawaban yang sudah ada, untuk tombol yang wewenangnya bukan satu izin polos:

| Jawaban | Field baru | Dihitung dari |
|---|---|---|
| `GET /api/rnd/samples/{sample_id}` | `caps: {"pick_winner": bool, "approve_spec": bool}` | Aturan yang sama dengan pemeriksa server saat itu (`backend/services/rnd_spec_service.py:336`, `_assert_role`) — layar tidak lagi menghitung sendiri dari daftar peran di pengaturan |
| `POST /api/auth/login` | `view_resources`, `hidden_views`, dan daftar peran (bentuk `GET /api/roles`) — koreksi: `GET /api/auth/me` tidak punya field `view_actions` | Sama dengan `GET /api/auth/me`, supaya konteks izin sudah lengkap sebelum layar pertama digambar (PR-UX-41) |

Tidak ada endpoint baru dan tidak ada izin yang berubah.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan baru. Semua izin yang dirujuk tabel di bawah sudah ada atau lahir di PR-T2.

### Layar

**1. Konteks izin** — `frontend/src/config/roles.js`: `canCurrent(modul, aksi)` menjawab **tidak** bila konteks belum
dimuat dan peran bukan Admin (hari ini: boleh). `setAccessContext` menerima konteks dari jawaban login.

**2. Panggilan data di kerangka aplikasi.** Aturan: komponen yang dimuat di semua layar (sidebar, lencana, panel
beranda, pemuat awal) hanya memanggil endpoint bila `can(...)` untuk izin endpoint itu benar; bila tidak, ia tidak
memanggil dan tidak menggambar apa pun.

| Pemanggil | Endpoint | Izin endpoint | Penjaga di layar |
|---|---|---|---|
| `frontend/src/components/CoreWidgets.jsx:8` (`usePostingFailureCount`) | `GET /api/finance/posting-failures/count` | `accounting.view` | `canCurrent("accounting", "view")` dengan arti baru butir 1 |
| `frontend/src/features/sales_admin/KeepPendingPanel.jsx:30` (`load`) | `GET /api/sales/keep-pending` | salah satu dari `order.verify`, `order.view` | panel tidak dimuat dan tidak memanggil bila keduanya tidak dipegang |
| `frontend/src/features/hr/EmployeeSelfService.jsx:153` (`load`) | `GET /api/hr/employees/me` | login (milik sendiri) | tidak memanggil bila akun tidak punya `employee_id`; tampil "Akun ini belum ditautkan ke data karyawan. Minta Admin menautkannya di Akun & Akses." |
| `frontend/src/features/approvals/approvalInboxData.js:50` (`grab`) | daftar tiap kategori persetujuan | izin lihat tiap kategori | hanya kategori yang izin lihatnya dipegang yang dipanggil; kategori lain tidak dihitung "belum lengkap" |

**3. Tabel penggantian — 25 contoh lampiran B.** "Bendera server" = field boolean pada jawaban API.

| # | Jangkar | Gerbang sekarang | Pengganti |
|---|---|---|---|
| 1 | `frontend/src/features/rnd/SampleDetailPanel.jsx:87` (`canSubmit`) | `roleIs` enam daftar | Kirim `can(perms, "rnd", "submit")` · Nilai `rnd.assess` atau aksi per jenis uji · Putuskan `rnd.decide` atau aksi per jenis uji · PIC `rnd.pic_decide` · Override `rnd.manage` · Ubah `rnd.create` |
| 2 | `frontend/src/features/rnd/SampleDetailPanel.jsx:143` (`mayPickWinner`); `frontend/src/features/rnd/SampleDetailPanel.jsx:147` (`mayApproveSpec`) | daftar peran dari pengaturan, dicocokkan nama | Bendera server `caps.pick_winner`, `caps.approve_spec` |
| 3 | `frontend/src/features/design/DesignRequestDetailPanel.jsx:72` (`canDecide`) | `roleIs` | Putuskan `design_request.decide` · Tugaskan `design_request.assign` · Kerjakan `design_request.deliver` · Rujukan `design_request.create` |
| 4 | `frontend/src/features/design/DesignRequestsView.jsx:132` (`canCreate`) | `roleIs` | Buat `design_request.create` · Laporan `design_request.report` |
| 5 | `frontend/src/features/rnd/RndDesignsView.jsx:75` (`canAssess`); `frontend/src/features/rnd/design/DesignDetailPage.jsx:48` (`canAssess`) | `roleIs(admin, manager)` | `rnd.assess` |
| 6 | `frontend/src/features/production/ProductionParts.jsx:12` (`prodPerms`); `frontend/src/features/production/ProductionView.jsx:20` (`prodPerms`) | daftar tertulis | `prodPerms(perms)`: `production.manage_bom`, `.create`, `.release`, `.complete`, `.cancel` |
| 7 | `frontend/src/features/documents/DocumentCenter.jsx:48` (`canSign`); `frontend/src/features/documents/DocumentActionsBar.jsx:45` (`canSign`) | `ESIGN_ROLES`, `WA_MANAGE_ROLES` | Tanda tangan `esign.sign` · Kelola pengiriman `document_delivery.manage` |
| 8 | `frontend/src/features/finance/amendments/AmendmentTrailPanel.jsx:35` (`canPropose`) | `PROPOSER_ROLES` | `finance_amendment.propose` |
| 9 | `frontend/src/features/catalog/CatalogWorkspace.jsx:44` (`canPurge`) | `["admin", "md"]` | `product.retire` (PR-T2) |
| 10 | `frontend/src/features/admin/po/PODetailPanel.jsx:91` (`canApprove`); `frontend/src/features/admin/po/POCompactPanel.jsx:33` (`canApprove`); `frontend/src/features/purchasing/PurchaseApprovalView.jsx:84` (`roleSatisfies`) | `roleSatisfies` | Dikerjakan KP-T4 (jawaban `can_decide` server); unit ini menghapus sisa `roleSatisfies` bila KP-T4 sudah selesai |
| 11 | `frontend/src/features/purchasing/VendorBillsView.jsx:68` (`canApproveDoc`); `frontend/src/features/purchasing/LandedCostView.jsx:50` (`canApproveDoc`) | `roleSatisfies` | Sama dengan #10 |
| 12 | `frontend/src/features/crm/CrmView.jsx:19` (`isManager`) | `roleIs(admin, manager)` | Tab "Skema (Arsip)" `sales_force.view` · tab "Persetujuan Kredit" `credit_override.approve` |
| 13 | `frontend/src/features/crm/Customer360Panel.jsx:36` (`isManager`) | `roleIs` | "Pindah Sales" `sales_force.assign` |
| 14 | `frontend/src/features/crm/SalesForceDashboard.jsx:16` (`isManager`) | `roleIs` | "Set Target" `sales_force.update` · papan peringkat `sales_force.view` |
| 15 | `frontend/src/features/marketing/PostDetailModal.jsx:29` (`isApprover`) | `roleIs(admin, manager)` | `marketing.approve` |
| 16 | `frontend/src/features/marketing/Campaigns.jsx:33` (`canApproveBill`); `frontend/src/features/marketing/TemplatePicker.jsx:16` (`created_by_id`) | daftar tertulis | Setujui tagihan kampanye: dikerjakan KP-T4 · hapus templat orang lain `marketing.delete` |
| 17 | `frontend/src/features/samples/SampleOrdersView.jsx:71` (`canPay`) | izin + `roleIs` | `sample_order.approve_payment` saja |
| 18 | `frontend/src/features/pettycash/CashAdvanceDetail.jsx:40` (`stageOk`) | `roleIs` atas peran tahap | Dikerjakan KP-T4 (tahap persetujuan kas kecil) |
| 19 | `frontend/src/features/sales/SalesPortal.jsx:319` (`allowRollPick`) | `user.role === "sales"` | kategori kerja peran = `sales` dari `GET /api/roles` (PR-T4); sebelum PR-T4 selesai: `roleIs(role, ["sales"])` |
| 20 | `frontend/src/features/wms/grn/GoodsReceiptsView.jsx:42` (`showLegacy`); `frontend/src/features/wms/grn/GoodsReceiptsView.jsx:88` (`SETTINGS_ROLES`); `frontend/src/features/settings/ReceivingOcrSettings.jsx:19` (`roles`) | daftar tertulis | Bagian penerimaan lama `wms.create` · pintasan pengaturan `goods_receipt.configure` · tiap tab memakai izin endpoint datanya |
| 21 | layar inspeksi yang membaca `can_release_hold` dan `can_create` | bendera server dari nama peran | Benderanya diperbaiki PR-T2; layar tidak berubah |
| 22 | `frontend/src/features/finance/ClosingView.jsx:47` (`isAdmin`) | `role === "admin"` | `accounting.reopen` (PR-T2) |
| 22b | `frontend/src/features/settings/config/SettingsHub.jsx:380` (`isAdmin`) | `role === "admin"` | Dikerjakan KF-T1 (`can_edit` per kunci dari server) |
| 23 | `frontend/src/components/AskKnButton.jsx:20` (`AI_ROLES`); `frontend/src/App.js:310` (`onAskKn`); `frontend/src/features/mobile/MobileOpsApp.jsx:214` (`AI_ROLES`) | daftar tertulis | `ai.view` (PR-T2) |
| 24 | `frontend/src/features/mobile/MobileAppSwitch.jsx:48` (`salesMobileRole`); `frontend/src/features/sales/mobile/MobileOrders.jsx:42` (`isAdmin`) | `roleIs` memilih aplikasi HP | Tata letak, bukan wewenang: dipilih dari halaman awal dan kategori kerja peran (PR-T4): kategori `sales` atau halaman awal `sales-admin-desk` → aplikasi HP sales; halaman awal `md-desk` → aplikasi MD; kategori `sopir` → aplikasi pengemudi; kategori `gudang` atau halaman awal `warehouse-admin-desk` → aplikasi gudang; selain itu aplikasi umum |
| 25 | `frontend/src/features/settings/entities/AccountFormDrawer.jsx:49` (`CROSS_ROLES`) | daftar tertulis | Dikerjakan PR-T6 |

**4. Aturan untuk sisanya** (semua `roleIs(`, `[…].includes(role)`, `X_ROLES.includes(…role)`, `role === "…"` di
`frontend/src` di luar `config/`):

| Jenis pemakaian | Aturan |
|---|---|
| Menyalakan tombol, tab, atau bagian yang memanggil endpoint | `can(perms, sumber daya, aksi)` dengan pasangan yang **sama persis** dengan `require_permission` endpoint yang dipanggil tombol itu; bila endpoint memakai "salah satu dari", layar memakai `||` atas pasangan yang sama |
| Wewenang yang bergantung dokumen (jenjang persetujuan, pemilik, status) | Bendera boolean dari server pada jawaban dokumen; layar tidak menghitung ulang |
| Memilih tata letak (aplikasi HP, susunan beranda) | Dari sifat peran (`home_view`, `kategori_kerja` di `GET /api/roles`), bukan id peran |
| Tur panduan dan daftar periksa pengenalan per peran (`frontend/src/data/tourDefinitions.js`) | Tetap berdasar id peran, dengan peran kustom memakai tur peran dasarnya (materi, bukan wewenang) |
| `role === "admin"` untuk menampilkan alat khusus Admin | `can(...)` atas izin alat itu (`system_tools.configure`, `rfid_device.configure`, `ai.configure`, …) |
| Label, ikon, atau teks sapaan | Boleh tetap |

Tiap penggantian dicatat di laporan sebagai baris "berkas:baris · gerbang lama · izin baru · endpoint yang dijaga".

**5. Penjaga** — skrip baru `scripts/guardrails/verify_role_gate_ui.py` (INV-ROLE-02), mengikuti pola
`scripts/guardrails/verify_role_label.py` dan pembantu `scripts/guardrails/_ratchet.py`:

- Menghitung per berkas di `frontend/src` (tanpa `__tests__`, tanpa komentar): `roleIs(`, `roleSatisfies(`,
  `roleRank(`, `.includes(` yang argumennya berakhiran `role`, dan `role ===`/`role !==` terhadap literal id peran
  (13 id peran bawaan dibaca dari `backend/role_registry.py`).
- Dikecualikan: `config/roles.js`, `config/navMeta.js`, `config/navStructure.js`, `config/hubTabs.js`,
  `config/navigationConfig.js`, `components/LoginScreen.jsx`, `data/tourDefinitions.js`, dan baris berpenanda
  `// tata-letak:` diikuti alasan.
- Ratchet: garis dasar `scripts/guardrails/baselines/role_gate_ui.json` ditulis saat penjaga dibuat (`--init`), lalu
  jumlah per berkas hanya boleh turun; berkas baru dengan jumlah > 0 = merah. Pada akhir unit garis dasar hanya
  memuat baris milik unit lain yang belum selesai (#10, #11, #16, #18, #22b, #25), masing-masing dengan catatan unit
  pemegangnya.
- `--self-test`: menyisipkan `roleIs(role, ["manager"])` dan `["admin"].includes(user.role)` ke salinan berkas dan
  harus memerah; baris ber-`// tata-letak:` tidak memerah.
- Dipasang di `scripts/gate.sh` (bagian statik) sebagai `guard:role_gate_ui (INV-ROLE-02, tombol dari izin)`.
- `verify_role_label.py`: `ROLE_IDS` dibaca dari registry (13 peran), bukan enam yang ditulis.

## Uji penerimaan

Persiapan bersama: peran uji baku `02` §6. "Staf Penagihan Uji" = peran kustom tanpa peran dasar, `levels: {"ar":
"manage", "customer": "view", "approval": "view"}` (peran yang dipakai `ui_pengaturan_peran.js`).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `python scripts/guardrails/verify_role_gate_ui.py` dan `--self-test` | Keluar 0; self-test: 2 sisipan tertangkap, 1 baris tata letak lolos |
| U2 | B | — | Hitung `roleIs(` di `frontend/src` di luar berkas yang dikecualikan | Hanya baris berpenanda `// tata-letak:`; garis dasar hanya memuat baris milik KP-T4, KF-T1, PR-T6 yang belum selesai |
| U3 | B | — | `POST /api/auth/login` sebagai akun "Staf Penagihan Uji" | Jawaban memuat `view_resources`, `hidden_views` (sama dengan `GET /api/auth/me`; field `view_actions` tidak ada di kode — koreksi), dan daftar peran yang memuat peran itu |
| U4 | B | sample dengan `rnd.sample_decision_roles` = `["manager"]` | `GET /api/rnd/samples/{id}` oleh manajer seed, oleh "Tanpa Acuan" + `rnd.view` + `rnd.decide`, dan oleh Sopir | `caps.pick_winner`: benar · sama dengan jawaban pemeriksa server untuk peran itu · 403 |
| U5 | komponen | konteks izin belum dimuat, peran bukan Admin | `canCurrent("accounting", "view")` | `false`; dengan peran Admin `true` |
| U6 | komponen | izin `{production: ["view", "create"]}` | `prodPerms(perms)` | `createWo` benar; `manageBom`, `release`, `complete`, `cancel` salah |
| U7 | komponen | `CrmView` dengan izin `{customer: ["view"], credit_override: ["approve"]}` dan peran kustom tanpa peran dasar | gambar tab | Tab "Persetujuan Kredit" ada; tab "Skema (Arsip)" tidak ada |
| U8 | komponen | `CrmView` dengan peran kustom berdasar Manajer dan izin `{customer: ["view"]}` | gambar tab | Kedua tab tidak ada (sebelum unit: keduanya ada) |
| U9 | komponen | `AskKnButton` dengan izin `{ai: ["view"]}` dan peran kustom; lalu tanpa `ai` dan peran `manager` | gambar | tampil · tidak tampil |
| U10 | layar (uji jalan) | lingkungan A; jalankan `ui_pengaturan_peran.js` | butir C2 | "OK": tidak ada 403 dari `/api/finance/posting-failures/count` maupun `/api/sales/keep-pending`; tidak ada 404 dari `/api/hr/employees/me` |
| U11 | layar (uji jalan) | skrip yang sama | butir C3 "approval-inbox" | Tidak ada panggilan yang dijawab 403; tidak ada peringatan "Daftar ini belum lengkap" |
| U12 | layar (uji jalan) | skrip yang sama | butir B1b dan C1 | Pratinjau menu tetap 9 layar dan sama dengan menu setelah masuk |
| U13 | layar (uji jalan) | "Tanpa Acuan" + modul Produksi "Semua aksi" | Buka layar Produksi | Tombol Buat WO, Rilis, Selesai, Batal, Kelola BOM tampil dan tiap aksi dijawab bukan 403 |
| U14 | layar (uji jalan) | Manajer bawaan, sebelum dan sesudah unit | Buka CRM, Permintaan Desain, Sample, Produksi, Pusat Dokumen, Tutup Buku; catat tombol aksi yang tampil | Daftar tombol sama (tidak ada tombol Manajer yang hilang) |
| U15 | layar (uji jalan) | 13 peran bawaan; sapuan `ui_sapuan_layar.js` sebelum dan sesudah unit | Bandingkan daftar panggilan API yang dijawab 403 per peran | Tidak ada 403 baru; 403 dari kerangka aplikasi hilang |

## Langkah kerja

1. Penjaga `verify_role_gate_ui.py` + `--init` garis dasar; catat jumlah awal per berkas di laporan. U1 merah pada
   self-test sampai penjaga jadi.
2. Uji komponen U5–U9 (merah), lalu `canCurrent`, konteks dari login (U3, U5).
3. Tabel 2 (kerangka). U10, U11 di lingkungan A.
4. Tabel 3 per fitur (R&D, desain, produksi, dokumen, CRM, marketing, sample, gudang, asisten, HP); bendera server
   U4. Jalankan penjaga dengan `--update` setelah tiap fitur.
5. Sisa `roleIs`, daftar tertulis, dan `===` menurut tabel 4.
6. U12–U15; `scripts/gate.sh --quick`; `yarn test --watchAll=false`; laporan memuat tabel penggantian lengkap.

## Dokumen ikut berubah

`CODEBASE_MAP.md` (penjaga baru); `docs/KN_08_UI_UX_STANDARDS.md` (aturan "tombol dari izin, panggilan kerangka
dijaga izin"); `docs/audit/konfigurasi-peran-2026-11-13/bukti/layar/` tidak diubah — hasil uji jalan baru disimpan di
laporan unit.

## Di luar lingkup

- Tombol persetujuan PO, tagihan pemasok, voucher biaya masuk, tagihan kampanye, dan tahap kas kecil → KP-T4.
- Tombol simpan di Pusat Pengaturan → KF-T1. Formulir akun dan editor peran → PR-T6.
- Daftar `roles:` pada menu dan tab (`config/navStructure.js`, `config/hubTabs.js`) → tetap rancangan menu peran
  bawaan; tambahan menu dari izin diatur PR-T6.
- Peran tanpa peran dasar mendarat di "Profil Saya" → halaman awal menjadi sifat peran di PR-T4.
- Menerjemahkan pesan galat mentah di 244 berkas → teks manusia sudah datang dari server sejak PR-T6.

## Asumsi dan risiko

- `ASUMSI:` pasangan izin tiap tombol di tabel 3 diambil dari gerbang endpoint yang disebut lampiran B; pelaksana
  mencocokkannya lagi dengan `require_permission` endpoint pada HEAD dan memakai yang di kode bila berbeda.
- `ASUMSI:` `GET /api/sales/keep-pending` dipanggil dari panel yang dimuat pada halaman awal sementara sebelum peran
  kustom terdaftar; dengan konteks izin lengkap sejak login dan penjaga di panel, panggilan itu hilang. Bila U10
  masih merah, cari pemanggilnya dengan jejak jaringan peramban dan jaga dengan aturan tabel 2.
- `ASUMSI:` akun yang tidak tertaut karyawan tidak punya `employee_id` pada data sesi.
- `RISIKO:` tombol hilang bagi peran bawaan karena pasangan izin di layar lebih sempit dari daftar peran lama.
  Penangkal: U14 dan U15. Membatalkan: kembalikan commit per fitur; garis dasar penjaga dinaikkan kembali hanya untuk
  berkas itu dengan catatan.
