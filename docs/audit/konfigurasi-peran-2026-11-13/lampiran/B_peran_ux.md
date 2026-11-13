# Audit B — Peran & Hak Akses, Peran Kustom, Akun & Akses (sisi layar + kelengkapan model)

Tanggal: 2026-11-13 · Kode yang dibaca: `HEAD` = `dca195b` · Cara kerja: **baca saja** (tidak ada berkas repo yang diubah, server dan tes tidak dijalankan). Hitungan dibuat dengan skrip baca-saja di luar repo (lihat Lampiran G).

Tanda bukti: **T** = terbukti dari kode (baris disebut) · **I** = inferensi (masuk akal dari kode, belum dijalankan).
Istilah: *peran acuan* = `base_role` peran kustom · *kustom ber-acuan* = peran kustom yang dibuat lewat "Salin dari peran"/"Duplikat" · *kustom tanpa acuan* = dibuat dari nol.

---

## 1. Ringkasan (10 baris)

1. Peran kustom **bekerja untuk izin API** (1.453 pemeriksaan izin literal, 336 pasangan, semuanya bisa diberikan dari editor), tetapi **tidak untuk segala hal yang masih melekat pada nama peran** — dan layar tidak pernah mengatakan mana yang mana.
2. Kolom **"Salin dari peran"** ternyata juga menetapkan **peran acuan permanen**; acuan itu diam-diam menentukan beranda, meja kerja, peringkat persetujuan, cakupan data "hanya miliknya", penerima notifikasi, tata letak HP, dan 89 gerbang nama peran di server. Tidak bisa dilihat/diubah saat menyunting.
3. **Persetujuan PO, tagihan supplier, dan landed cost** hanya memeriksa login + peringkat peran acuan. Centang "Setujui" di editor tidak berpengaruh; peran kustom tanpa acuan (peringkat 1) tidak akan pernah bisa menyetujui, kustom ber-acuan Manajer tetap bisa walau modulnya "Tidak ada".
4. **Cakupan data sales** ("hanya pelanggan/pesanan miliknya") hanya berlaku bila acuannya `sales`. Peran penjualan yang dibuat dari nol melihat **semua** pelanggan & pesanan badan usahanya; sebaliknya akun ber-peran kustom **hilang dari daftar pilih** sales/sopir/desainer dan dari akrual insentif (kueri `"role": "sales"` literal).
5. Di layar, **52 `roleIs(...)` + ±35 daftar nama peran literal** masih menentukan tombol, sedangkan server memakai izin → peran kustom melihat tombol yang ditolak server, atau tidak melihat tombol padahal berizin (R&D, desain, produksi, tanda tangan, amandemen, katalog).
6. Untuk **peran bawaan**: menaikkan tingkat modul memberi izin API tetapi **menunya tidak muncul**, pratinjau menu di editor justru menampilkannya, dan sebagian perubahan **ditimpa ulang setiap server dinyalakan** (`sync_permission_revocations`).
7. Editor **tidak menjawab "peran ini akhirnya bisa apa"**: tiga tingkat hampir selalu tampil "Kelola penuh · sebagian", beberapa tombol tingkat tidak bisa dipilih, ±22 aksi yang bisa dicentang tidak diperiksa server, satu modul ("Profil POV Sales") tidak punya efek sama sekali.
8. **Akun & Akses**: formulir salah membaca "lintas badan usaha" (daftar statis admin/manajer), tautan karyawan tidak bisa dilepas, pindah akun massal tidak mencabut sesi, dan pemegang `user.update` bisa memberi peran Admin (termasuk ke dirinya).
9. **Bahasa**: pesan 403 mentah ("Permission ditolak: x.y") masih tampil di layar peran/akun sendiri dan di ±244 berkas; ada **dua kamus label** yang berbeda (editor vs pesan galat) untuk 47 nama halaman & 46 nama aksi.
10. **Belum ada** di model: batas nominal per peran, cakupan data per peran, beranda per peran, bandingkan peran, riwayat perubahan di layar, masa berlaku akses, "lihat sebagai peran ini", peran ganda/delegasi. Total **44 temuan: 11 Tinggi · 25 Sedang · 8 Rendah**.

### Jawaban pendek untuk pertanyaan pemilik

| Yang diatur admin di layar peran | Benar-benar mengikuti pengaturan? |
|---|---|
| Izin per aksi (lihat/buat/ubah/setujui…) di API | **Ya** — server membaca matriks tiap permintaan (`dependencies.py:106-116`). |
| Menu peran kustom | **Ya, sebagian besar** — diturunkan dari modul; 10 menu + 8 tab di luar katalog mengikuti acuan saja. |
| Menu peran bawaan | **Tidak bisa ditambah**, hanya bisa berkurang. |
| Tombol di dalam layar | **Campur** — 279 pemakaian `can()` mengikuti izin; ±87 tempat mengikuti nama peran/acuan. |
| Siapa boleh menyetujui (peringkat) | **Tidak** — ikut acuan. |
| Data siapa yang terlihat (milik sendiri vs semua) | **Tidak** — ikut acuan. |
| Beranda & meja kerja | **Tidak** — ikut acuan. |
| Notifikasi | "Giliran Anda" **ya** (berbasis izin); selebihnya ikut nama peran/acuan. |
| Lintas badan usaha | **Ya**, dengan 3 cacat (PR-UX-09, -20, -21). |

---

## 2. Tabel temuan

### 2.1 Tingkat TINGGI

| ID | T/I | Temuan | Bukti (berkas:baris) | Akibat nyata untuk peran kustom | Usulan |
|---|---|---|---|---|---|
| PR-UX-01 | T | **"Salin dari peran" = menetapkan peran acuan permanen, tanpa diberi tahu.** Satu dropdown melakukan dua hal: menyalin hak akses *dan* mengisi `base_role`. Setelah dipilih dropdown kembali kosong; satu-satunya jejak adalah kalimat kecil "Menu dasar mengikuti peran acuan" (hanya saat membuat). Saat menyunting, acuan tidak ditampilkan dan tidak bisa diganti (`RolePatch` tak punya `base_role`). Tidak ada pilihan "tanpa acuan" setelah terlanjur memilih. | `RoleEditorDrawer.jsx:38, 89-95, 179-183, 255`; `routers/access_roles.py:24-31`; `role_registry.py:259-275` | Admin mengira "menyalin sekali". Kenyataannya acuan terus hidup: beranda, peringkat, cakupan data, notifikasi, tombol `roleIs`, 89 `role_in` server. Dua peran dengan centang identik berperilaku berbeda hanya karena acuannya beda. | Pisahkan jadi dua kontrol: **"Peran dasar"** (wajib dibaca, dengan daftar apa saja yang ikut) dan **"Salin hak akses dari…"**. Tampilkan peran dasar di kepala editor; izinkan menggantinya dengan konfirmasi dampak. |
| PR-UX-02 | T | **Peringkat persetujuan melekat pada acuan dan tidak tampil di editor.** `rank` peran kustom = peringkat acuan, tanpa acuan = 1. Persetujuan/penolakan **PO, tagihan supplier, landed cost** hanya `current_user` + `role_satisfies` — tidak ada pemeriksaan izin sama sekali. SO & PR: izin **dan** peringkat. | `role_registry.py:264, 365-372`; `routers/purchase_orders.py:798-812, 920-933`; `routers/vendor_bills.py:443-455, 470-485`; `routers/landed_cost.py:238-247, 291-300`; `routers/sales_orders_extra.py:446-461`; `services/purchase_requisition_service.py:330-332` | (a) "Kepala Pembelian" dibuat dari nol + Pembelian "Kelola penuh (Setujui)" → tetap ditolak: *"Approval PO butuh role minimal 'manager'. Role Anda: 'cr_kepala_pembelian'"*. (b) Kustom ber-acuan Manajer dengan Pembelian "Tidak ada" → tetap bisa menyetujui PO/tagihan lewat API. (c) Aksi `purchase_order.approve/reject`, `landed_cost.approve/reject`, `vendor_bill.reject` di editor = sakelar tanpa efek. | Tambahkan pemeriksaan izin `*.approve` pada 6 endpoint itu; jadikan **"Tingkat persetujuan"** isian per peran di editor (Pelaksana / Penyelia / Manajer) + tampilkan di kartu peran. |
| PR-UX-03 | T | **Cakupan data "hanya miliknya" hanya untuk acuan `sales`** (35 dari 89 `role_in` adalah cakupan data). Pemilik pesanan (`sales_id`) juga hanya diisi bila acuan `sales`. | `services/customer_service.py:398-405, 408-423`; `services/sales_ownership.py:44-49`; `routers/sales_orders.py:671`; `routers/customers.py:102`; `routers/crm.py:126, 135, 358, 413`; `routers/logistics.py:37` (sopir) | "Sales Junior" dibuat **dari nol** dengan Penjualan + Pelanggan → melihat **semua pelanggan dan pesanan** badan usahanya, dan pesanan buatannya tanpa `sales_id` (tidak masuk komisi/"Performa Saya"). Sebaliknya "Supervisor Sales" ber-acuan `sales` **tidak bisa** diperluas melihat tim. | Jadikan **cakupan data** pilihan per peran di editor: *Milik sendiri · Tim · Semua di badan usaha*. Sementara itu: saat membuat peran dengan modul Pelanggan/Pesanan tanpa acuan `sales`, tampilkan peringatan "peran ini melihat semua pelanggan". |
| PR-UX-04 | T | **Akun ber-peran kustom hilang dari daftar pilih & hitungan** yang mencari `users.role` persis `"sales"`, `"driver"`, `"designer"`. | `routers/crm.py:48, 73, 372, 427`; `routers/customers.py:109`; `routers/products.py:240`; `routers/admin.py:225, 429`; `services/sales_force_service.py:456`; `services/gl_service.py:2908-2913`; `services/product_exclusivity.py:138`; `services/logistics_service.py:714-716`; `services/design_request_service.py:148`; `services/inspection_service.py:689, 705` | Akun "Sales Senior" (acuan `sales`): tidak muncul di pilihan Sales penanggung jawab, "Pindah Sales" menolak (*Salesperson tujuan tidak valid*), tidak bisa diberi target/insentif, tidak masuk papan peringkat, **tidak ikut akrual insentif ke jurnal**. Sopir/desainer/petugas inspeksi ber-peran kustom tidak bisa ditugaskan. | Ganti kueri menjadi "peran atau peran acuannya" (pembantu `role_ids_like("sales")`), atau lebih baik berbasis izin (`order.create` + cakupan milik sendiri). |
| PR-UX-05 | T | **Peran bawaan: menaikkan modul tidak memunculkan menu, tetapi pratinjau menampilkannya.** Menu peran bawaan = rancangan tertulis (`roles:` + `ROLE_NAV`), izin hanya bisa *menyembunyikan*. Pratinjau editor memakai `inherit: role.base_role` (kosong untuk peran bawaan) → menghitung menu seolah peran kustom tanpa acuan. | `config/roles.js:372-374, 385-396`; `config/navigationConfig.js:138-150`; `RoleEditorDrawer.jsx:258`; `RoleMenuPreview.jsx:28-49`; uji `config/__tests__/navAccess.test.js:104-119` (hanya membandingkan peran kustom) | Admin memberi Finance modul "SDM: Lihat saja" → pratinjau menampilkan menu SDM, simpan sukses, **menu tidak pernah muncul** di akun Finance (API-nya terbuka). Pratinjau peran bawaan juga tidak menampilkan Beranda/Meja Saya/Tanya KN yang nyatanya ada. Kesan pemilik: "pengaturan peran tidak jalan". | Pratinjau peran bawaan harus memakai id peran itu sendiri. Putuskan satu aturan: menu peran bawaan juga boleh **bertambah** dari modul, atau editor mengunci tingkat "naik" pada peran bawaan dengan saran "duplikat jadi peran kustom". |
| PR-UX-06 | T | **Perubahan pada peran bawaan ditimpa setiap server dinyalakan.** `sync_permission_revocations` berjalan tanpa syarat: REVOKE (mis. `sales` × PO/PR/tagihan/RFQ; `md`/`warehouse_admin` × persetujuan), RESCOPE (mis. `warehouse.order = [view, deliver]`, `sales.tax_invoice = [view]`), GRANT (±37 pasangan peran×halaman, mis. `sales.ar_receipt.create`, `manager.design_request.release_hold`, `repair_order`, `od_pricing`). | `bootstrap.py:402-511, 1647-1648` | Admin mencabut kwitansi dari Sales (modul Uang Masuk → "Tidak ada") → setelah restart `ar_receipt: [create]` kembali. Admin memberi Gudang "Konfirmasi pesanan" → hilang setelah restart. Tidak ada tanda di layar. Peran kustom **tidak** terkena (jadi lebih tahan lama daripada peran bawaan). | Jalankan blok itu **sekali** (catat di `defaults_applied` seperti `sync_permission_modules`), jangan tiap start. Di editor peran bawaan beri catatan bila ada aksi yang "dikunci sistem". |
| PR-UX-07 | T (kode; perlu uji API) | **Jalur naik hak lewat akun.** (a) `POST/PATCH /users` menerima peran apa pun termasuk `admin` tanpa memeriksa pelaku → pemegang `user.update` bisa menjadikan dirinya Admin. (b) `POST /access/roles/{rid}/move-users` hanya butuh `permission.update`, tanpa cek "peran sendiri" → bisa memindahkan dirinya + rekan ke peran lebih tinggi. (c) `rid = admin` tidak ditolak dan tanpa cek admin terakhir → semua Admin bisa terdemosi sekaligus. | `routers/users.py:121-157`; `services/user_admin_service.py:218-228, 287-293`; `routers/access_roles.py:51-56, 87-93`; `services/custom_role_service.py:348-360` | Peran kustom dengan modul "Pengaturan, Pengguna & Hak Akses" (bahkan hanya `user.update` lewat aksi rinci) = Admin secara praktik. Peringatan modul hanya menyebut "bisa mengubah hak akses orang lain". | Hanya Admin boleh memberi/mencabut peran Admin; tolak mengubah peran sendiri; `move-users` wajib `user.update`, tolak asal `admin`, dan pakai jalur `update_user` (cabut sesi + audit per akun). |
| PR-UX-08 | T | **Tombol mengikuti nama peran, server mengikuti izin — dua arah.** 52 `roleIs(...)` di 36 berkas + ±20 `[...].includes(role)` + 15 `role === "..."`. `roleIs` mengenali acuan; daftar literal tidak. | Lihat Lampiran B (25 contoh berkas:baris, dengan pasangan servernya) | **Melihat tombol yang ditolak**: kustom ber-acuan MD dengan R&D "Lihat saja" tetap melihat Nilai/Putuskan/Batalkan sample. **Tidak melihat tombol padahal berizin**: kustom tanpa acuan dengan R&D/Desain/Produksi "Kelola penuh" tidak punya tombol kerja sama sekali; tombol tanda tangan & usul amandemen hilang untuk semua peran kustom. | Ganti semua gerbang tombol dengan `can(perms, modul, aksi)` yang sama dengan `require_permission` endpoint-nya. Sisakan `roleIs` hanya untuk tata letak. Tambah penjaga lint: `roleIs`/`includes(role)` dilarang di gerbang aksi. |
| PR-UX-09 | T | **Formulir akun salah membaca "lintas badan usaha".** `CROSS_ROLES` dihitung sekali dari daftar statis (admin, manager); peran kustom selalu `crossEntity: false` walau server mengirim `cross_entity`. | `config/roles.js:147, 427`; `entityApi.js:106-108`; `AccountFormDrawer.jsx:49, 121, 211-215, 301`; server: `user_admin_service.py:145-151, 295-307`; `entity_context_service.py:110-117` | (a) Lintas-PT **dimatikan** untuk Manajer → formulir tetap berkata "otomatis melihat SEMUA", pemilih PT disembunyikan, `allowed_entity_ids` tidak dikirim → daftar lama (semua PT saat akun dibuat) tetap dipakai: **tidak bisa dipersempit dari layar**. (b) Lintas-PT **dinyalakan** untuk peran kustom → formulir berkata "terkunci di badan usahanya" dan menawarkan centang PT yang diabaikan server. | Baca `cross_entity` dari `/api/roles` (sudah dikirim, `role_registry.py:388`). Saat lintas-PT dimatikan pada sebuah peran, tampilkan daftar akun terdampak + minta admin meninjau penugasan PT tiap akun. |
| PR-UX-10 | T (ketiadaan) | **Sebelum menyimpan, admin tidak bisa tahu "peran ini akhirnya bisa apa".** Yang ada: hitungan tingkat, pratinjau *nama menu*, notifikasi giliran, daftar modul berubah. Yang tidak ada: daftar aksi dalam kalimat ("bisa menyetujui retur, tidak bisa menghapus pelanggan"), beranda, peringkat persetujuan, cakupan data, hal yang diwarisi acuan, ketergantungan antar-modul, dan cara mencoba ("lihat sebagai"). | `RoleEditorDrawer.jsx:226-263, 310-351`; `RoleMenuPreview.jsx:74-76`; `services/custom_role_service.py:331-345` (pratinjau server hanya `turn_alerts`, `screens`, `levels`) | Admin menyimpan lalu menguji dengan login akun contoh — persis keraguan pemilik. | Tambahkan panel **"Ringkasan peran"**: Beranda · Tingkat persetujuan · Data yang terlihat · Badan usaha · "Bisa:" / "Tidak bisa:" per modul (kalimat) · "Diwarisi dari peran dasar (tidak bisa diatur di sini)". Tambah tombol **"Lihat sebagai peran ini"** (sesi baca-saja). |
| PR-UX-11 | T | **"Tidak ada"/"Lihat saja" tidak menutup fitur yang digerbang nama peran** bagi kustom ber-acuan. Gerbang `require_role`/`role_in` lolos lewat acuan tanpa melihat matriks. | `dependencies.py:93-98`; `routers/home.py:56-69` (dasbor manajer); `routers/costing.py:16-27` (WAC/HPP semua produk); `routers/crm.py:70-72, 140-142, 327, 370, 425` (pindah sales, putuskan kredit, target, insentif); `routers/incentive_rates.py:45-98`; `routers/lots.py:97-99`; `routers/supplier_contracts.py:76-78`; `routers/config.py:59` (48 setelan `roles=[manager]`); `routers/master_governance.py:144-148` + `services/master_usage_service.py:68-70` (hapus permanen master: `product.view` + acuan admin/md) | "Manajer Toko" diduplikat dari Manajer lalu Keuangan/Laporan/Pelanggan dijadikan "Tidak ada": editor menampilkan 0 akses, tetapi akun itu tetap bisa membaca HPP & margin, dasbor manajer, memindah pelanggan antar-sales, memutus kredit, mengubah 48 setelan. Kustom tanpa acuan dengan modul yang sama "Kelola penuh" justru **ditolak** di tempat yang sama. | Ubah 38 endpoint "nama peran saja" menjadi izin (usulan nama: `customer.reassign`, `customer.credit_decide`, `sales_target.manage`, `costing.view`, `home.manager`). Sampai itu selesai, tampilkan di editor daftar "Fitur yang ikut peran dasar". |

### 2.2 Tingkat SEDANG

| ID | T/I | Temuan | Bukti | Akibat nyata untuk peran kustom | Usulan |
|---|---|---|---|---|---|
| PR-UX-12 | T | **Tiga tingkat menyesatkan.** Apa pun selain "hanya Lihat" dibaca "Kelola penuh" + tanda kecil "sebagian". Pada peran bawaan utama 9–17 modul berstatus "Kelola penuh · sebagian" (Sales 12 dari 14, Manajer 17 dari 28; rincian Lampiran A.5). Kartu peran menghitung "N kelola" termasuk yang sebagian. Mengeklik "Kelola penuh" pada modul "sebagian" **membuka semua aksi**; baris tidak ditandai "diubah" (pembanding hanya tingkat), dialog konfirmasi hanya berkata "aksi rinci berubah" tanpa menyebut aksinya. | `access_modules.py:221-232`; `roleAccessUtil.js:5-15`; `RoleAccessPanel.jsx:13-14, 41-43`; `RoleModuleRow.jsx:13, 35-39, 52`; `RoleEditorDrawer.jsx:330-335` | Admin yang "merapikan" tingkat (Lihat saja → Kelola penuh lagi) tanpa sadar memberi Setujui/Hapus/Bayar. | Empat keadaan: **Tidak ada · Lihat saja · Sebagian (n/m aksi) · Semua aksi**. Konfirmasi menyebut aksi yang ditambah/dicabut per halaman ("+Setujui, +Hapus"). |
| PR-UX-13 | T | **Tombol tingkat yang tidak bisa dipilih.** "Pusat Persetujuan": "Kelola penuh" langsung kembali ke "Lihat saja" (satu-satunya aksi = lihat). "Visibilitas Atribut Stok" & "Profil POV Sales": "Lihat saja" = "Tidak ada" (tak punya aksi `view`). Pada "Lihat saja", halaman tanpa aksi lihat ikut dicabut diam-diam: Harga Pesanan Khusus, Periode & Tutup Buku, Amandemen Keuangan. | `access_modules.py:184-199, 249-253`; `permissions_config.py` (`approval: [view]`, `field_visibility`, `sales_pov`, `od_pricing`, `period`, `finance_amendment`) | Tombol terasa "rusak"; "Semua modul: Lihat saja" membuat grade/LOT/asal tersembunyi untuk peran itu tanpa penjelasan. | Sembunyikan tingkat yang tak berlaku per modul; untuk modul sakelar pakai dua pilihan (Mati/Nyala) dengan kalimat akibatnya. |
| PR-UX-14 | T | **Modul "Profil POV Sales Komersial" tidak punya efek.** Deskripsinya menjanjikan "GRADE SELALU disembunyikan walau izin visibilitas grade dicentang"; tidak ada satu pun pembaca `sales_pov` di backend maupun frontend, dan `hidden_for` sengaja mengabaikannya. | `access_modules.py:196-199, 328`; `services/field_visibility.py:44-52`; grep `sales_pov`: 0 pemakai di luar definisi | Admin yang mengandalkannya untuk menyembunyikan grade dari peran penjualan kustom keliru: bila "Lihat grade" dicentang, grade tampil. | Hapus modulnya, atau hidupkan kembali aturannya. Jangan biarkan janji keamanan yang tidak ditegakkan. |
| PR-UX-15 | T | **Peran dari nol tidak bisa melihat grade/LOT/asal** kecuali admin tahu menyalakan modul "Visibilitas Atribut Stok" — yang berada di grup **Penjualan** dan hanya menerima "Kelola penuh". Semua peran bawaan (kecuali Sales) punya izin ini secara bawaan. | `access_modules.py:192-195`; `permissions_config.py` (`field_visibility` di 12 peran); `services/field_visibility.py:44-52` | "Staf Gudang" kustom: kolom grade/LOT kosong, tab "Lot & Silsilah" tersembunyi; terlihat seperti data hilang. | Pindahkan ke grup "Gudang/Umum", ganti jadi tiga centang berbahasa biasa, dan nyalakan bawaan saat modul Stok/Gudang dinyalakan. |
| PR-UX-16 | T (6 aksi) / I (sisanya) | **Aksi yang bisa dicentang tetapi tidak diperiksa server.** 46 pasangan tidak ditemukan dalam pemeriksaan literal; setelah mengeluarkan yang diperiksa dinamis, tersisa ±22. Terbukti: `purchase_order.approve/reject`, `landed_cost.approve/reject`, `vendor_bill.reject` (peringkat saja), `reports.view/export` (0 pemeriksa — endpoint laporan memakai `order.view`/`product.view`/`warehouse.view`), `marketing.approve` (nama peran), `sales_pov.commercial`. | Lampiran D; `routers/reporting.py:31, 90, 141, 187, 221, 290`; `services/marketing_service.py:208` | Modul "Laporan & Analitik" praktis hanya sakelar menu: dinyalakan tanpa modul Pesanan → layar 403; dimatikan → laporan tetap bisa dibaca lewat API bila punya `order.view`. | Bersihkan daftar aksi (hapus yang mati) atau pasang pemeriksanya; tambahkan uji "setiap aksi di katalog punya ≥1 pemeriksa". |
| PR-UX-17 | T | **"Sembunyikan menu" bisa menutup satu grup penuh tanpa sengaja.** Di "Menu, tab & aktivitas" → "Menu lain", id grup bersama tampil sebagai centang biasa: "Pengaturan" (`settings-hub`, ada di 16 modul), "Penjualan" (5), "Akuntansi & Pajak" (5), "Keuangan" (4), "Pembelian" (4), "Gudang & Logistik" (3). `hidden_views` satu daftar per peran (bukan per modul). Tidak ada kalimat bahwa menyembunyikan ≠ mencabut izin. | `RoleNavTree.jsx:20-34, 41`; `config/roles.js:362-368`; `navigationConfig.js:148`; `custom_role_service.py:256-263` | Mencabut centang "Pengaturan" di modul Pesanan Penjualan menyembunyikan **seluruh grup Pengaturan** untuk peran itu; centang yang sama berubah di 15 modul lain. Konfirmasi hanya berkata "Pengaturan → disembunyikan". | Jangan tampilkan id grup sebagai centang; tampilkan hanya menu/tab milik modul itu. Tambah catatan: "Menyembunyikan hanya merapikan menu; izin tetap berlaku." |
| PR-UX-18 | T | **Menu di luar katalog modul** → hanya ikut acuan: **Beranda, Meja Saya, Tanya KN, 5 meja peran, Profil Saya** (menu) dan **Impor/Ekspor & Status pelanggan, Harga Internal Antar-PT, Hutang Reimburse, Label Alasan Amandemen, Komisi & Insentif, Penerimaan & OCR, Aturan & Template Bank** (tab). `hidden_views` menolak id di luar katalog. | Lampiran C.2; `access_modules.py:389-390`; `custom_role_service.py:257-261`; `navStructure.js:64-148`; `hubTabs.js:36, 47, 167, 252, 254, 261, 272` | Kustom tanpa acuan tidak akan pernah punya Beranda, Meja Saya, atau Tanya KN. Kustom ber-acuan selalu mendapatkannya dan **tidak bisa** disembunyikan. | Masukkan ke katalog (modul "Umum": Beranda, Meja kerja, Tanya KN) dan tab-tab itu ke modul domainnya. |
| PR-UX-19 | T | **Beranda & meja kerja tidak bisa dipilih.** Tanpa acuan → mendarat di "Profil Saya". Ber-acuan → beranda acuan, walau izin mejanya dicabut: Meja Finance butuh `payment_variance.decide`, Meja Admin Sales butuh `order.confirm`. `/desks/me` untuk peran tanpa meja membalas *"Peran 'cr_xxx' memakai meja khususnya sendiri"* (id teknis). Setelan "Halaman awal peran …" (`role_home.*`, 4 peran) tidak dibaca frontend. | `role_registry.py:259-267, 375-377`; `config/roles.js:431-432`; `navMeta.js:212-240`; `routers/work_desks.py:96-99, 232-248, 254-264`; `config_catalog_core.py:915-927` (0 pemakai di `frontend/src`) | "Staf Penagihan" diduplikat dari Finance tanpa wewenang selisih bayar → setiap login mendarat di layar yang menolak. | Tambah isian **"Halaman awal"** per peran di editor (pilihan = layar yang boleh dibuka); hapus/aktifkan setelan `role_home.*`. |
| PR-UX-20 | T (logika) | **Perubahan lintas-PT peran kustom bisa tidak tersimpan.** "Bawaan" peran kustom dihitung dari nilai **asli** acuan, sedangkan nilai efektif dari nilai acuan **yang sudah diubah**. Bila keduanya beda, memilih nilai yang sama dengan "bawaan" disimpan sebagai "ikut bawaan" → efektifnya tetap mengikuti acuan. Label "Bawaan: mati (mengikuti peran acuan)" juga salah. | `role_registry.py:283-289` vs `298-306`; `custom_role_service.py:122-123, 264-268`; `RoleEditorDrawer.jsx:244-248` | Lintas-PT Finance dinyalakan → "Kasir" (acuan Finance) ikut menyala; admin mematikannya untuk Kasir, layar berkata "disimpan", **Kasir tetap melihat semua PT**. | `cross_entity_default` peran kustom harus = nilai efektif acuan; atau selalu simpan nilai eksplisit untuk peran kustom. |
| PR-UX-21 | T (3 tempat) / I (umum) | **Anggapan "admin/manajer = lintas PT" masih tertanam** setelah lintas-PT dibuat bisa diatur. | `services/customer_service.py:411-413` (lolos sebelum cek entitas); `routers/internal_requests.py:33, 43` (daftar statis sendiri); `routers/bank.py:31, 112`, `routers/cash.py:48` (rekening tingkat grup) | Manajer/kustom ber-acuan Manajer yang lintas-PT-nya dimatikan masih bisa membuka pelanggan PT lain dan rekening tingkat grup. | Ganti dengan `ctx.is_cross_entity` di semua tempat; tambah uji untuk "manajer non-lintas". |
| PR-UX-22 | T | **Notifikasi: hanya "giliran Anda" yang berbasis izin.** ±96 penyebutan `recipient_role` + 10 perulangan `for role in ("manager", …)` beralamat nama peran; pembaca menerima alamat peran sendiri, `all`, dan acuan. Pratinjau editor hanya menampilkan notifikasi giliran. Kustom ber-acuan Manajer tidak ikut pengecualian "pengawas" (nama literal) → menerima semua giliran pelaksana. | `services/notification_scope.py:19-27, 39-57`; `services/turn_notification_service.py:66-77`; `custom_role_service.py:153-162`; `RoleNotifPreview.jsx` | Kustom tanpa acuan: tidak menerima peringatan stok, persetujuan menunggu, pengingat retur, dsb. Kustom ber-acuan Manajer: kebanjiran "Siapkan barang", "Kirim pesanan". | Alamatkan semua notifikasi lewat izin (`notification_audience.roles_with_permission` sudah ada); pratinjau tampilkan semua jenis. |
| PR-UX-23 | T | **Pusat Pengaturan tidak mengikuti izin yang diberikan.** Dari 310 setelan: 251 memakai izin bawaan `settings.manage` dan semuanya `owner_role = admin` → **235 hanya bisa diubah `role == "admin"`** walau "Pengaturan Sistem: Kelola" dicentang; pesan tolaknya *"…(butuh izin settings.manage)"* padahal izin itu dimiliki. 48 setelan ber-`roles=[manager]` bisa diubah kustom ber-acuan Manajer tanpa izin apa pun. Batas baca hanya untuk acuan MD; peran lain (termasuk kustom tanpa modul) membaca semua setelan & riwayat lewat API. | `routers/config.py:45-73, 93-106`; `config_registry.py:163, 226`; hitungan Lampiran A.4 | "Admin Kantor" kustom dengan modul Pengaturan "Kelola penuh": tombol Simpan mati di hampir semua kartu, pesan galat menyuruh meminta izin yang sudah dimiliki. | Hapus `owner_role` (atau jadikan izin `settings.manage_core`); perbaiki pesan; batasi baca dengan `settings.view`/modul domain. |
| PR-UX-24 | T | **Penyetuju di pengaturan = pilihan tetap, peran kustom tidak bisa dipilih.** Aturan Persetujuan: "Tanpa / Manajer / Admin / **Owner**" — "Owner" bukan peran; nilai tak dikenal jatuh ke peringkat Manajer, jadi "Owner" = Manajer. Setelan penyetuju (amandemen, denda, selisih bayar, kasus, kontrabon, antar-PT) hanya Manager/Admin. Daftar peran di setelan (`ai.enabled_roles`, `rnd.sample_decision_roles`, `rnd.spec_approval_roles`, `makloon.claim_approval_roles`, matriks divisi) dicocokkan nama persis. | `features/settings/approvalRulesConstants.js:13-18`; `role_registry.py:355-362`; Lampiran A.4; `services/approval_matrix_service.py:243-248`; `services/rnd_spec_service.py:343`; `SampleDetailPanel.jsx:143, 147` | Pemilik yang memilih "Owner" untuk nilai terbesar mengira hanya dirinya; nyatanya semua Manajer lolos. Peran kustom hanya bisa jadi penyetuju bila acuannya Manajer. | Isi pilihan dari daftar peran (termasuk kustom) + tampilkan "siapa saja yang lolos"; hapus "Owner" atau jadikan peran sungguhan. |
| PR-UX-25 | T | **Peran kustom tidak ikut pembaruan izin.** Migrasi izin baru hanya berjalan untuk peran bawaan; peran kustom = salinan saat dibuat. Tetapi perilaku nama peran tetap "hidup" mengikuti acuan — dua aturan berbeda dalam satu peran, tidak dijelaskan. | `bootstrap.py:361-399` (hanya `DEFAULT_PERMISSIONS.items()`); `custom_role_service.py:217-221` | Fitur baru (mis. Perbaikan roll, Pesanan Khusus) otomatis terbuka untuk Sales, tetapi 403 untuk "Sales Senior" hasil duplikat; tidak ada penanda "tertinggal dari peran dasar". | Di editor tampilkan "Beda dengan peran dasar: +3 / −5 aksi" dan tombol "Samakan halaman baru dengan peran dasar". |
| PR-UX-26 | T | **"Kembalikan ke bawaan" tidak lengkap.** Mengembalikan izin & lintas-PT, **tidak** menu yang disembunyikan. Tombolnya hanya muncul bila izin berbeda; lencana "diubah dari bawaan" tidak menghitung menu tersembunyi/lintas-PT. Dialog berkata "Semua tingkat akses … dikembalikan". | `custom_role_service.py:129, 297-306`; `RoleEditorDrawer.jsx:276-280`; `RoleDangerDialog.jsx:10-14` | Menu yang pernah disembunyikan tetap hilang setelah "kembalikan"; admin tidak punya jalan pintas. | Reset juga `hidden_views`; hitung `modified` dari ketiganya; sebutkan apa saja yang dikembalikan. |
| PR-UX-27 | T | **Pesan 403 mentah masih tampil.** Penerjemah `apiErrorText` ada, tetapi (a) layar Peran/Akun memakai `errText` sendiri dan `ErrorNotice` tidak menerjemahkan string → *"Permission ditolak: permission.view"* tampil apa adanya (mis. Manajer membuka tab "Peran & Hak Akses" — tab tidak digerbang izin); (b) 244 berkas menampilkan `response.data.detail` tanpa penerjemah (53 pembelian, 51 penjualan, 15 gudang); (c) pesan server lain: *"Role Anda tidak memiliki izin untuk aksi ini"*, *"Approval PO butuh role minimal 'manager'. Role Anda: 'cr_xxx'"*. | `dependencies.py:98, 116, 137-139`; `entityApi.js:16-24`; `components/ErrorNotice.jsx:27`; `EntitiesAccessView.jsx:28-38, 159-165`; `utils/apiError.js:66-107`; `purchase_orders.py:810-812` | Pengguna peran kustom paling sering terkena (izinnya paling sering berbeda dari tombol) dan melihat kode teknis + id peran `cr_…`. | Lihat §6 (teks pengganti). Kirim galat terstruktur dari server (`code`, `module`, `action`, `message`) dan terjemahkan di satu pencegat axios. |
| PR-UX-28 | T | **Dua kamus label.** Editor memakai `access_modules.RESOURCE_LABEL/ACTION_LABEL`; pesan 403 & jejak audit memakai `config/auditLabels.js`. Berbeda untuk **47 halaman** dan **46 aksi** (contoh: "Peran & Hak Akses" vs "Matriks Izin"; "Kirim tanpa lunas" vs "Lepas Sebelum Lunas"; "Lepas aset" vs "Hapus Buku"; "Rilis" vs "Lepaskan"). 19 aksi & 3 halaman tidak ada di kamus frontend. | `access_modules.py:275-330`; `frontend/src/config/auditLabels.js`; Lampiran E | Pengguna melapor "tidak punya izin *Lepas Sebelum Lunas*"; admin mencari di editor dan tidak menemukannya (di sana bernama "Kirim tanpa lunas"). | Satu sumber label (server), dikirim lewat `/api/access/modules`, dipakai juga oleh penerjemah galat & jejak audit. |
| PR-UX-29 | T | **Label hilang / jargon di editor.** Tampil mentah: halaman `marketing`; aksi `close`, `count`, `review` (Kedatangan Barang) dan `set` (Harga Internal). Jargon: "Pegging", "Dispatch", "Generate", "Void", "Override / edit SO", "Hold / tahan", "Random check", "Scan", "Kelola BOM", "(WMS)", "(GRN)", "(PIN)", "(SOS)", "RFQ", "Landed Cost", "PD / LPJ". | `access_modules.py:275-330`; `RoleAdvancedPanel.jsx:25, 50` | Admin non-teknis tidak tahu arti sakelar; salah centang. | Lihat §6. |
| PR-UX-30 | T | **Hanya satu modul bertanda "sensitif".** Aksi berisiko lain tanpa peringatan: buka periode, tanggal mundur, void jurnal, bayar tagihan/kontrabon, cairkan dana, bebaskan denda, kelola gaji, lihat data pribadi, kirim tanpa lunas, hapus master (±39 aksi menurut penggolongan saya). Tombol "Semua modul: Kelola penuh" memberi semuanya dalam satu klik. | `access_modules.py:200-210`; `RoleEditorDrawer.jsx:186-192, 337-341`; `RoleModuleRow.jsx:21-26` | Peran kustom mudah menjadi terlalu kuat tanpa disadari. | Tandai aksi berisiko per aksi (ikon + alasan), ringkas di konfirmasi: "Peran ini bisa: membuka periode, membayar supplier…". |
| PR-UX-31 | T | **Tautan akun ↔ karyawan tidak bisa dilepas atau diganti bersih.** Memilih "Tidak ditautkan"/karyawan lain hanya mengubah `users.employee_id`; `hr_employees.user_id` karyawan lama tidak dibersihkan, sedangkan daftar akun membaca tautan dari sisi HR. | `user_admin_service.py:295-308, 344-347, 184-201`; `AccountFormDrawer.jsx:232-238`; `routers/users.py:94-96` | Setelah "dilepas" akun tetap tampil tertaut; karyawan lama tak pernah muncul lagi di "karyawan tanpa akun"; dua karyawan bisa menunjuk satu akun. | Saat tautan berubah, kosongkan `user_id` karyawan lama dalam langkah yang sama; tampilkan konfirmasi. |
| PR-UX-32 | T | **Formulir akun minim konteks peran.** Peran bawaan terpilih = **Sales**; pilihan hanya "nama — 1 badan usaha…" (teks statis); tidak ada ringkasan hak peran, tidak ada tautan "lihat hak peran ini", tidak ada penanda peran kustom/acuan. | `AccountFormDrawer.jsx:29, 205-216`; `config/roles.js:403-413` | Admin memberi peran kustom tanpa tahu isinya; akun baru bisa tak sengaja jadi Sales. | Tanpa pilihan bawaan; tampilkan ringkasan peran (lihat PR-UX-10) di bawah dropdown + tautan ke editor. |
| PR-UX-33 | T | **Sandi.** Skema API memberi bawaan `demo12345` bila sandi kosong dan layanan tidak memeriksa panjang saat membuat (layar memeriksa ≥8). Reset = admin mengetik sandi baru; tidak ada "wajib ganti saat masuk pertama", tidak ada masa berlaku. | `schemas.py:170`; `user_admin_service.py:249, 383-395`; `AccountList.jsx:146-173` | Akun (termasuk ber-peran kustom kuat) bisa lahir dengan sandi yang diketahui umum lewat API/impor. | Wajibkan sandi di server (hapus bawaan), tambah tanda `must_change_password`, opsi tautan setel-sendiri. |
| PR-UX-34 | T | **Pindah akun massal berbeda aturan dari ubah satu akun.** Tidak mencabut sesi, tidak menghitung ulang penugasan PT untuk peran tujuan, tidak memeriksa admin terakhir, satu baris audit. Di klien, beranda tidak diarahkan ulang saat peran berubah di tengah sesi (hanya saat `user.id` berubah). | `custom_role_service.py:348-360`; `user_admin_service.py:287-315`; `hooks/useSessionSync.js:104-114` | Pengguna yang sedang bekerja tiba-tiba berganti menu (≤60 dtk) dan tertinggal di layar yang kini menolak. | Lewatkan tiap akun ke `update_user`; arahkan ke beranda baru saat `user.role` berubah. |
| PR-UX-35 | T | **Editor bisa dibuka dan diubah oleh pemegang "Lihat saja".** Kartu peran selalu bisa diklik; editor tidak punya mode baca; widget "Pindahkan semua akun" tampil (`canMove = !locked`). | `RoleAccessPanel.jsx:53, 119-136`; `RoleEditorDrawer.jsx:28-31, 251` | Peran kustom dengan `permission.view` mengubah banyak hal lalu ditolak saat simpan dengan pesan mentah. | Teruskan `canManage` ke editor → mode baca-saja. |
| PR-UX-36 | T | **Riwayat perubahan peran tidak ada di layar peran.** Tercatat di jejak audit umum (hanya Admin), sebagai JSON; aksi `custom_role_created`, `custom_role_deleted`, `role_users_moved` belum punya label manusia. Tidak ada "pulihkan versi" atau pembanding. | `routers/access_roles.py:55, 82-83, 95-96, 104, 112`; `config/auditLabels.js:112` (hanya 2 aksi) | Tidak bisa menjawab "siapa mengubah peran ini, kapan, dari apa ke apa". | Tab "Riwayat" di editor (tanggal · pelaku · ringkasan beda · jumlah akun terdampak) + tombol pulihkan. |

### 2.3 Tingkat RENDAH

| ID | T/I | Temuan | Bukti | Akibat | Usulan |
|---|---|---|---|---|---|
| PR-UX-37 | T | Membuat peran dengan menu tersembunyi = dua panggilan (POST lalu PATCH). Bila yang kedua gagal, peran sudah jadi; mencoba lagi ditolak "nama sudah dipakai". | `RoleEditorDrawer.jsx:113-116` | Peran setengah jadi. | Terima `hidden_views` di `POST /roles`. |
| PR-UX-38 | T | Pratinjau menu tidak memakai pengecualian server (`Lot & Silsilah` butuh visibilitas LOT; `Pengiriman` butuh izin logistik), dan beberapa tab dijanjikan modul tetapi induknya milik modul lain (BI Keuangan di modul Laporan; Impor Dataset di modul Produk). | `RoleMenuPreview.jsx:8-12`; `access_modules.py:368-374`; Lampiran C.3 | Pratinjau sedikit berbeda dari kenyataan. | Kirim `view_resources` dari server ke pratinjau; rapikan `nav` modul. |
| PR-UX-39 | T | Layar terkubur: Pengaturan › Perusahaan & Akun › Badan Usaha & Akses › tab ke-3 "Peran & Hak Akses"; judul halaman tidak menyebut peran. | `hubTabs.js:238-242`; `EntitiesAccessView.jsx:28-38`; `navMeta.js:175` | Sulit ditemukan. | Menu sendiri "Pengguna & Peran" (tab: Akun · Peran · Cek Peran). |
| PR-UX-40 | T | "Bisa dihapus" dihitung dari akun **aktif** saja, server menghitung semua akun. | `custom_role_service.py:55-60, 128, 313-320` | Tombol hapus aktif lalu ditolak 409. | Samakan hitungan; tampilkan "n aktif · m nonaktif". |
| PR-UX-41 | I | Awal sesi: respons login tidak membawa `view_resources`; sebelum `/auth/me` selesai `canCurrent()` mengembalikan "boleh" dan peran kustom belum terdaftar (beranda sementara = beranda Sales). | `routers/auth.py:141-145, 162-172`; `config/roles.js:354-358, 451-453`; `navigationConfig.js:225-227`; `useSessionSync.js:86-95` | Kilas menu/tombol yang salah sesaat. | Sertakan `_my_nav` + daftar peran di respons login. |
| PR-UX-42 | T | Tata letak HP, tur panduan, dan tombol "Tanya KN" memakai acuan/nama literal. | `MobileAppSwitch.jsx:48-53`; `data/tourDefinitions.js:39`; `components/AskKnButton.jsx:4, 20`; `App.js:310` | Kustom tanpa acuan selalu mendapat aplikasi HP umum, tanpa tur dan tanpa tombol Tanya KN. | Turunkan dari izin/modul. |
| PR-UX-43 | T | "Lihat saja" memuat beberapa aksi tulis: 32 endpoint tulis hanya menuntut `*.view` — kebanyakan pratinjau/simulasi; yang benar-benar menulis: catat pindai roll, buat permintaan pakai warna, cetak label lot, ubah divisi orang (+acuan manajer), hapus permanen master (+acuan admin/md). | Lampiran F | "Lihat saja" tidak sepenuhnya baca-saja. | Naikkan ke aksi tulis yang sesuai. |
| PR-UX-44 | T | Istilah tidak seragam: "peran acuan" / "template" / "Salin dari peran" / "Duplikat" / "acuan:"; server masih menulis "Role", "role berubah" (alasan cabut sesi yang tampil ke admin), dan pesan validasi menyebut id teknis. | `RoleEditorDrawer.jsx:146, 179-181`; `RoleAccessPanel.jsx:47`; `custom_role_service.py:207-209`; `user_admin_service.py:165, 222, 311`; `role_registry.py:414-418` | Membingungkan. | Satu istilah: **"Peran dasar"**; ganti "Role" → "Peran". |

---

## 3. Alur layar pengelola peran — langkah demi langkah

Letak: Pengaturan › Perusahaan & Akun › **Badan Usaha & Akses** → tab **Peran & Hak Akses** (`EntitiesAccessView.jsx`, `RoleAccessPanel.jsx`, `RoleEditorDrawer.jsx`).

| Langkah | Yang terjadi di kode | Yang membingungkan / tidak diberi tahu | Temuan |
|---|---|---|---|
| Buka tab | `GET /access/roles` + `/access/modules`; kartu per peran: jumlah akun, "n kelola · n lihat · n tidak ada", "Semua PT", "acuan: X". | "n kelola" memasukkan yang sebagian. Tab tampil untuk siapa pun yang bisa membuka layar; tanpa `permission.view` muncul galat mentah. | 12, 27 |
| **Buat Peran Baru** | Editor kosong: nama, keterangan, semua modul "Tidak ada", `base_role = ""`. | Tidak ada penjelasan beda "dari nol" vs "dari peran lain" (dari nol = tanpa beranda, peringkat 1, tanpa cakupan milik-sendiri, tanpa grade/LOT). | 01, 03, 15, 19 |
| **Pilih peran acuan** ("Salin dari peran") | Menyalin semua izin + mengisi `base_role` + (bila belum disentuh) lintas-PT. Dropdown kembali kosong. | Tidak dikatakan bahwa acuan permanen dan menentukan banyak hal. Memilih lagi menimpa seluruh centang. Tak bisa kembali "tanpa acuan". Admin tidak bisa jadi acuan (benar, tetapi tak dijelaskan). | 01 |
| **Duplikat** (ikon salin di kartu) | Sama seperti di atas; nama "X (salinan)"; acuan = X (atau acuan X bila X kustom). | Judul "Duplikat Peran" — tidak menyebut bahwa salinan terikat ke peran dasar. | 01, 25 |
| **Atur tingkat per modul** | 31 modul, 8 grup; tombol Tidak ada / Lihat saja / Kelola penuh → menulis ulang izin semua halaman modul. | "Kelola penuh · sebagian"; tombol yang tak bisa dipilih; naik diam-diam ke semua aksi; hanya 1 modul bertanda sensitif. | 12, 13, 30 |
| **Izin rinci** ("Menu, tab & aktivitas") | Per halaman: daftar aksi (381 sakelar total). Aksi apa pun menyalakan "Lihat". | Nama aksi campur jargon/mentah; ±22 sakelar tanpa efek; tidak ada penjelasan per aksi. | 16, 29 |
| **Sembunyikan menu** | Centang per tab; disimpan di `hidden_views` (satu daftar per peran). | Id grup tampil sebagai centang; tak dikatakan "hanya menyembunyikan". Menu di luar katalog tak bisa disembunyikan. | 17, 18 |
| **Lintas badan usaha** | Kotak centang "Akses semua badan usaha (lintas PT)". | Bisa tidak tersimpan (acuan sudah diubah); mematikan tidak mempersempit akun lama; formulir akun tidak ikut. | 20, 09, 21 |
| **Pratinjau** | "Pratinjau menu (N layar)" + "Notifikasi giliran". | Hanya nama menu; salah untuk peran bawaan; tidak menandai menu warisan acuan; tidak ada beranda/peringkat/cakupan data. | 05, 10, 38 |
| **Simpan** | Dialog "Periksa sebelum menyimpan": modul yang berubah, menu, lintas-PT, peringatan modul sensitif; cek versi (konflik antar-admin). Berlaku ≤60 dtk. | Tidak menyebut aksi yang ditambah/dicabut; tidak menyebut hal yang tidak berubah karena ikut acuan. | 12, 10 |
| **Pindahkan akun** | Di editor: "Pindahkan semua akun ke peran lain" → `move-users`. | Semua-atau-tidak; tanpa cabut sesi; tanpa pratinjau beda hak; tampil juga untuk yang tak berwenang. | 34, 35, 07 |
| **Hapus** | Hanya peran kustom tanpa akun; server menolak bila masih dipakai (termasuk akun nonaktif). | Tombol aktif padahal masih ada akun nonaktif. Peran kustom yang jadi acuan peran lain: tidak masalah (acuan selalu peran bawaan). | 40 |
| **Kembalikan ke bawaan** | Hanya peran bawaan yang izinnya berubah. | Menu tersembunyi tidak ikut; tombol tak muncul bila hanya menu/lintas-PT yang diubah; sebagian "bawaan" memang ditimpa ulang saat restart. | 26, 06 |

---

## 4. Hal yang melekat pada nama/acuan peran dan TIDAK bisa diatur dari layar peran

| Hal | Sumber di kode | Kustom **tanpa** acuan | Kustom **ber-acuan** | Bisa diatur di editor? |
|---|---|---|---|---|
| Beranda | `role_registry.py:259-267`; `roles.js:431` | Profil Saya | Beranda acuan (walau izinnya dicabut) | Tidak |
| Meja kerja | `work_desks.py:254-264`; `role_desk_service.py:12, 232-246` | Tidak ada ("Meja Saya" tak tampil; API 404) | Meja acuan; `/desks/me` tanpa cek izin modul | Tidak |
| Peringkat persetujuan | `role_registry.py:264, 351-372` (13 pemakaian `role_satisfies`) | 1 — tak bisa menyetujui apa pun yang menuntut peringkat | = acuan, walau modul "Tidak ada" | Tidak (tidak ditampilkan) |
| Cakupan data "hanya miliknya" | 35 `role_in` (Lampiran C.1) | Melihat semua (dalam badan usahanya) | Sales/sopir/desainer: selalu milik sendiri | Tidak |
| Kolom biaya/HPP | `core_utils.py:368` `COST_SAFE_ROLES`; `export_engine.py:50`; `sales_returns.py:708, 853` | Tidak pernah melihat HPP | Hanya acuan admin/manajer | Tidak |
| Wewenang ber-nama peran | 37 `role_in` + 52 `require_role` + ±10 literal | Ditolak semua | Lolos semua milik acuan | Tidak |
| Penerima notifikasi | `notification_scope.py:19-27` | Hanya "giliran", `all`, pribadi | + semua alamat acuan | Tidak (pratinjau hanya giliran) |
| Penyetuju di setelan | enum Manager/Admin (Lampiran A.4) | Tidak bisa | Hanya bila acuan Manajer | Tidak |
| Ubah setelan | `config.py:45-68` | 59 setelan ber-izin domain saja | + 48 setelan bila acuan Manajer | Sebagian |
| Baca Pusat Pengaturan | `config.py:93-106` | Semua (tanpa batas) | Dibatasi hanya bila acuan MD | Tidak |
| Tata letak HP, tur, Tanya KN | `MobileAppSwitch.jsx:48-53`; `tourDefinitions.js:39`; `AskKnButton.jsx:20` | Aplikasi umum; tanpa tur/Tanya KN | Ikut acuan (Tanya KN: tombol tidak, menu ya) | Tidak |
| Daftar pilih orang | PR-UX-04 | Tidak pernah muncul | Tidak pernah muncul (nama persis) | Tidak |
| Lintas badan usaha | `role_registry.py:283-311` | Mati | Ikut nilai efektif acuan | Ya (dengan cacat 09/20/21) |
| Peran Admin sebagai acuan | `custom_role_service.py:208-209` | — | Ditolak | — |

---

## 5. Kesesuaian menu ↔ izin (`access_modules.py`)

- **Sumber daya izin di luar modul: 0.** Semua 79 sumber daya di `DEFAULT_PERMISSIONS`/`EXTRA_ACTIONS` masuk salah satu dari 31 modul. (T)
- **"Kelola penuh" lengkap terhadap endpoint:** dari 336 pasangan izin literal di backend, tidak ada aksi yang berada di luar daftar "Kelola penuh". Satu-satunya anomali: `("gl", "view")` di `routers/supplier_contracts.py:207` — sumber daya `gl` tidak ada (tak berbahaya, bagian dari pilihan "salah satu dari"). 56 pemeriksaan lain bersifat dinamis (nama aksi dari variabel) dan tidak bisa dipastikan otomatis. (T/I)
- **Menu di luar modul:** 10 id menu + 8 tab (Lampiran C.2) → PR-UX-18. (T)
- **Id modul yang bukan menu/tab:** 8, tujuh di antaranya alias terdaftar; `product-templates` ditangani khusus di kode. Tidak ada id mati. (T)
- **"Lihat saja" yang memuat tulis:** 32 endpoint (Lampiran F) → PR-UX-43. (T)
- **Aksi tanpa pemeriksa:** ±22 (Lampiran D) → PR-UX-16.
- **Gerbang di luar matriks** (tidak terjangkau tingkat mana pun): 52 `require_role`, 89 `role_in`, 13 `role_satisfies`, ±10 perbandingan literal → PR-UX-02, -03, -11.
- **Modul tanpa menu:** "Visibilitas Atribut Stok", "Profil POV Sales" (sakelar murni).

---

## 6. Akun & Akses — yang hilang atau berisiko

| Topik | Keadaan sekarang | Risiko / kekurangan | Temuan |
|---|---|---|---|
| Membuat akun | Nama, email, sandi ≥8 (di layar), peran, tautan karyawan, badan usaha utama, PT tambahan, lini produk, lokasi gudang. | Peran bawaan "Sales"; sandi bawaan `demo12345` di API; tanpa ringkasan hak peran. | 32, 33 |
| Memberi/mengganti peran | Validasi terhadap daftar peran; mengganti peran **mencabut sesi** dan diperingatkan sebelumnya (baik). | Siapa pun ber-`user.update` bisa memberi Admin; tidak ada pembanding "hak lama vs baru". | 07, 10 |
| Peran diganti saat pengguna login | Satu akun: sesi dicabut (pekerjaan belum tersimpan hilang; pengguna tidak diberi alasan). Massal: tidak dicabut, menu berubah ≤60 dtk. | Dua perilaku berbeda. | 34 |
| Izin peran diubah saat pengguna login | Server langsung; layar ≤60 dtk (`useSessionSync.js:55-85`). | Baik; disebut di editor. | — |
| Badan usaha | Utama wajib (dari HR bila tertaut); tambahan eksplisit untuk peran non-lintas. Akun tanpa badan usaha jatuh diam-diam ke `ent_ksc` lewat API (`user_admin_service.py:138`). | Formulir salah soal lintas-PT; mematikan lintas-PT tidak mempersempit. | 09, 20, 21 |
| Tautan akun ↔ karyawan | Satu karyawan = satu akun; badan usaha ikut HR; peringatan bila tidak tertaut. | Tidak bisa dilepas/diganti bersih. | 31 |
| Nonaktifkan | Soft; sesi dicabut; admin terakhir dijaga. | Tidak ada tanggal berakhir otomatis; tidak ada pengingat akun lama tak dipakai. | §8 |
| Reset sandi | Admin mengetik sandi baru; sesi dicabut; diaudit. | Tanpa wajib ganti; admin tahu sandi pengguna. | 33 |
| Peran dihapus saat masih dipakai | Ditolak server (409, menyebut jumlah akun). | Tombol hapus bisa aktif padahal ada akun nonaktif. | 40 |
| "Cek Peran" | Menilai kecocokan peran vs jejak kegiatan; terapkan usulan lewat `update_user`. | Baik; belum menjelaskan peran kustom/acuan. | — |

---

## 7. Bahasa — yang tampil ke pengguna dan usulan teks pengganti

**Yang sudah baik:** label tingkat ("Tidak ada · Lihat saja · Kelola penuh"), nama 31 modul, sebagian besar nama aksi sudah berbahasa Indonesia; id teknis seperti `manage_payroll`, `release_unpaid` **tidak** tampil mentah (berlabel "Kelola payroll", "Kirim tanpa lunas …").

**Yang tampil mentah:** halaman `marketing`; aksi `close`, `count`, `review`, `set`; pesan 403 (PR-UX-27); id peran `cr_…` dan kata "Role" di pesan server.

| Tempat | Sekarang | Usulan |
|---|---|---|
| Dropdown editor | "Salin dari peran: pilih peran acuan…" | Dua kontrol: **"Peran dasar"** — "Menentukan halaman awal, tingkat persetujuan, dan data siapa yang terlihat. Tidak bisa diganti sembarangan." · **"Salin hak akses dari…"** — "Hanya menyalin centang; boleh diubah setelahnya." |
| Tingkat | "Kelola penuh · sebagian" | "Sebagian (7 dari 13 aksi)" |
| Tingkat | "Kelola penuh" | "Semua aksi" (+ "termasuk setujui & hapus" bila ada) |
| Tombol | "Menu, tab & aktivitas" | "Atur rinci" |
| Catatan pratinjau | "Menu = pintu. Tombol di dalam layar mengikuti tingkat akses…" | "Daftar ini hanya menu. Lihat **Ringkasan peran** untuk apa yang bisa dilakukan." |
| Modul | "Operasi Gudang (WMS)" | "Operasi Gudang" |
| Modul | "Riset & Sample (R&D)" | "Pengembangan Produk & Sample" |
| Modul | "Kas Kecil (PD / LPJ)" | "Kas Kecil (pengajuan dana & pertanggungjawaban)" |
| Modul | "Visibilitas Atribut Stok (grade · LOT · asal)" | "Boleh melihat grade, nomor lot & asal barang" |
| Modul | "Profil POV Sales Komersial" | Hapus (tidak berefek) |
| Halaman | `marketing` | "Marketing & Sosial Media" |
| Aksi | `close` / `count` / `review` | "Tutup penerimaan" / "Hitung fisik" / "Periksa hasil hitung" |
| Aksi | `set` | "Tetapkan harga internal" |
| Aksi | "Pegging" | "Kaitkan stok ke pesanan" |
| Aksi | "Dispatch" | "Berangkatkan kiriman" |
| Aksi | "Generate" | "Buat label" |
| Aksi | "Void" | "Batalkan (void)" |
| Aksi | "Override / edit SO" | "Ubah pesanan yang sudah terkunci" |
| Aksi | "Hold / tahan" · "Random check" · "Scan" | "Tahan" · "Cek acak" · "Pindai" |
| Aksi | "Kelola BOM" | "Kelola resep produksi" |
| 403 izin (`dependencies.py:116`) | "Permission ditolak: order.approve" | "Anda belum punya izin **Setujui** di **Pesanan Penjualan**. Minta Admin menyalakannya di Pengaturan › Peran & Hak Akses." |
| 403 salah satu (`:137-139`) | "Permission ditolak: butuh salah satu dari a.b / c.d" | "Layar ini butuh salah satu izin: … (sebut label)." |
| 403 nama peran (`:98`) | "Role Anda tidak memiliki izin untuk aksi ini" | "Tindakan ini hanya untuk **Manajer** (atau peran dengan dasar Manajer). Peran Anda: {label peran}." |
| 403 peringkat (`purchase_orders.py:810-812`) | "Approval PO butuh role minimal 'manager'. Role Anda: 'cr_xxx'." | "PO ini harus disetujui setingkat **Manajer**. Peran Anda ({label}) belum sampai tingkat itu." |
| Meja (`work_desks.py:264`) | "Peran 'cr_xxx' memakai meja khususnya sendiri." | "Peran Anda belum punya meja kerja. Buka menu yang tersedia di samping." |
| Setelan (`config.py:73`) | "'X' tidak bisa Anda ubah (butuh izin settings.manage)" | "Pengaturan 'X' hanya bisa diubah Admin." |
| Formulir akun | "Peran ini terkunci di badan usahanya…" | Ikuti nilai nyata peran: "Peran ini melihat **semua** badan usaha aktif" / "…hanya badan usaha yang dicentang di bawah". |
| Kilas simpan akun | "1 sesi dicabut (role berubah) — dia perlu masuk lagi." | "…(peran berubah)…" |
| Aturan Persetujuan | pilihan "Owner" | Hapus, atau jelaskan "= Manajer ke atas". |

---

## 8. Kelengkapan model — yang dibutuhkan pemilik tetapi belum ada

| Kebutuhan | Ada? | Catatan dari kode | Usulan singkat |
|---|---|---|---|
| Batas nominal persetujuan **per peran** | Tidak | Hanya aturan nilai → peran (3 pilihan) + peringkat; batas per orang ada untuk sebagian kasus keuangan (`finance_case_service.py:414`, `payment_variance_service.py:629`). | Isian "Boleh menyetujui s.d. Rp …" per jenis dokumen di editor. |
| Tingkat persetujuan per peran | Tidak (ikut acuan) | PR-UX-02 | Isian per peran. |
| Cakupan data per peran | Tidak (ikut acuan) | PR-UX-03 | Milik sendiri / tim / semua. |
| Beranda per peran | Tidak | PR-UX-19; setelan `role_home.*` mati | Isian "Halaman awal". |
| Salin peran | **Ya** | "Duplikat" & "Salin dari peran" | Perjelas (PR-UX-01). |
| Bandingkan dua peran | Tidak | 0 kode | Tampilan berdampingan + beda dengan peran dasar. |
| Riwayat perubahan peran | Sebagian | Hanya jejak audit umum | PR-UX-36. |
| Masa berlaku akses (akun/peran sementara) | Tidak | 0 kode | Tanggal berakhir akun + peran sementara. |
| "Lihat sebagai peran ini" | Tidak | 0 kode | Sesi baca-saja sebagai peran X. |
| Peran ganda / tambahan izin per orang | Tidak | Satu akun = satu `role`; yang per-akun hanya PT, lini, lokasi | Izin tambahan per akun dengan masa berlaku. |
| Delegasi / pengganti saat cuti | Tidak | Tidak ditemukan | Pengganti persetujuan bertanggal. |
| Pemisahan tugas (SoD) antar-izin | Sebagian | SoD pembuat≠penyetuju ada per dokumen; tidak ada peringatan kombinasi izin berbahaya di editor | Aturan "kombinasi terlarang" + peringatan saat simpan. |
| Peran berbeda per badan usaha | Tidak | Peran global; PT hanya daftar akses | Opsional. |
| Penerima notifikasi per peran | Sebagian | "Giliran" berbasis izin; lainnya nama peran | PR-UX-22. |
| Ekspor / cetak matriks peran | Tidak di layar peran | — | Unduh XLSX "siapa bisa apa". |
| Uji otomatis "aksi punya pemeriksa" | Tidak | PR-UX-16 | Gate baru. |
| Peringatan akun tak terpakai / peran tanpa akun | Sebagian | "Terakhir masuk" tampil; tanpa pengingat | Laporan berkala. |
| Wajib ganti sandi / 2 langkah | Tidak | PR-UX-33 | Tambah. |

---

## Lampiran A — Hitungan

### A.1 Frontend (`frontend/src`, tanpa `__tests__`)

| Jenis | Jumlah |
|---|---|
| (a) `roleIs(...)` | 52 pemakaian di 36 berkas |
| (a) `[...].includes(role)` / `X_ROLES.includes(role)` atas peran pengguna | ±20 |
| (a) `role === "..."` atas peran pengguna | 15 (12 di antaranya `"admin"`) |
| (a) `roleSatisfies/roleRank` (peringkat) | 6 |
| (a) `roleCanSee` di dalam layar | 4 |
| (a) daftar `roles:` menu/tab | 84 (`navStructure.js`) + ±125 (`hubTabs.js`) |
| (b) `can(perms, modul, aksi)` | 279 pemakaian di 134 berkas |
| (b) `canCurrent(...)` | 22 di 17 berkas |
| (b) akses langsung `permissions.x` | 45 |
| Berkas yang memakai (a) dan (b) sekaligus | 15 |
| `apiErrorText(` (penerjemah galat) | 375 di 187 berkas |
| `response.data.detail` mentah tanpa penerjemah | 244 berkas |

Apa yang terjadi pada peran kustom untuk (a): `roleIs` → **ikut acuan** (`roles.js:156-160`); daftar literal & `===` → **tidak pernah cocok** (kecuali id kustomnya dimasukkan); `roleSatisfies` → peringkat acuan; `roles:` menu → modul katalog + warisan acuan (`roles.js:385-396`).

### A.2 Backend (`backend/routers` + `backend/services`)

| Jenis | Jumlah |
|---|---|
| `require_permission/has_permission/require_any_permission` literal | 1.453 pemakaian, 336 pasangan, 150 berkas; 56 dinamis |
| `require_role(` | 52 (routers) |
| `role_in(` | 43 (routers) + 46 (services) = 89 baris |
| `.get("role")` | 126 (routers) + 164 (services) — termasuk "peran dokumen" (pic, penjual/pembeli, dll.) |
| `role_satisfies(` | 13 |
| Perbandingan literal atas peran pengguna | 63: 28 `== / != "admin"`, 10 perulangan penerima, 8 `in CROSS_ENTITY_ROLES`, 17 daftar nama (±10 nyata tanpa acuan) |
| Kueri `users` dengan `"role": "<nama>"` persis | 13 (+4 `$in`) |
| `recipient_role` | ±96 penyebutan |
| `owner_role` | 310 setelan, semuanya `admin` |

### A.3 `role_in` menurut maksud (89)

| Maksud | Jumlah |
|---|---|
| Wewenang (boleh/tidak melakukan) | 37 |
| Cakupan data (milik sendiri / lokasi / lini) | 35 |
| Tampilan (HPP/biaya, kode ambil, label) | 7 |
| Akses fitur (Tanya KN, penjadwal) | 5 |
| Pusat Pengaturan (ubah/baca) | 2 |
| Notifikasi (penerima) | 2 |
| Cakupan badan usaha | 1 |

### A.4 Pusat Pengaturan (310 setelan)

Izin ubah: `settings.manage` 251 · `rnd.manage` 32 · `hr.manage_payroll` 19 · `uom.update` 5 · `sales_return.policy` 3. `roles=[manager]`: 48. Hanya `role == "admin"`: 235. Setelan berisi peran: `amendment.approver_role`, `payment.penalty_waive_approver_role`, `payment.variance_writeoff_approver_role`, `case.approver_role`, `contra_bon.approval_role`, `contra_bon.high_value_approval_role`, `antar_entitas.approval_role`, `antar_entitas.high_value_approval_role` (enum Manager/Admin); `makloon.claim_approval_roles`, `returns.cutloss_treatment_roles`, `ai.margin_roles`, `ai.stock_value_roles`, `ai.enabled_roles`, `rnd.spec_approval_roles`, `rnd.sample_decision_roles` (daftar id peran); `role_home.admin/manager/sales/warehouse` (tidak dipakai layar).

### A.5 Katalog modul

31 modul · 79 sumber daya · 381 sakelar aksi · 192 id menu/tab. Tingkat peran bawaan (tidak ada / lihat / kelola / di antaranya sebagian): admin 1/1/29/0 · manager 1/2/28/17 · sales 13/4/14/12 · sales_admin 7/9/15/13 · finance 10/10/11/9 · warehouse 16/2/13/11 · md 13/4/14/10 · warehouse_admin 14/4/13/9 · designer 25/2/4/2 · driver 29/0/2/1 · sample_admin 21/6/4/3 · md_quality 20/6/5/3 · qc 21/6/4/2.

---

## Lampiran B — 25 contoh tombol vs server (peran kustom)

Arti kolom akibat: **A** = melihat tombol yang ditolak server · **B** = tidak melihat tombol padahal berizin · **C** = tombol & server sama-sama ikut acuan (tidak bisa diatur dari editor).

| # | Layar (berkas:baris) | Gerbang layar | Gerbang server | Akibat |
|---|---|---|---|---|
| 1 | `features/rnd/SampleDetailPanel.jsx:87-92` | `roleIs` daftar admin/manager/md/warehouse/sales untuk Kirim, Nilai, Putuskan, PIC, Override, Ubah | `rnd.submit / assess / decide / pic_decide / manage / create` (`routers/rnd.py:596, 686, 703, 745, 819, 580`) | **A**: acuan MD + R&D "Lihat saja". **B**: tanpa acuan + R&D "Kelola penuh". |
| 2 | `features/rnd/SampleDetailPanel.jsx:143, 147` | `decideRoles.includes(role)` / `specRoles.includes(role)` (literal) | `services/rnd_spec_service.py:343` (literal) | **C**: peran kustom tak pernah boleh memilih pemenang/ACC spesifikasi kecuali id-nya diketik ke setelan. |
| 3 | `features/design/DesignRequestDetailPanel.jsx:72-75` | `roleIs` admin/manager/md/designer/sales_admin | `design_request.assign / decide / deliver / create` (`routers/design_requests.py:255, 299, 284, 172`) | A dan B seperti #1. |
| 4 | `features/design/DesignRequestsView.jsx:132-133` | `roleIs` (Buat, Laporan) | `design_request.create / report` (`:128, :346`) | A/B. |
| 5 | `features/rnd/RndDesignsView.jsx:75`, `features/rnd/design/DesignDetailPage.jsx:48` | `canAssess = roleIs(admin, manager)` | `rnd.assess` (`routers/design_studio.py:29`) | **B**: MD/kustom ber-izin menilai tidak punya tombol. |
| 6 | `features/production/ProductionParts.jsx:12-20` (+ `ProductionView.jsx:20`) | `arr.includes(role)` literal | `production.manage_bom / create / release / complete / cancel` (`routers/production.py:95-214`) | **B** untuk **semua** peran kustom (bahkan ber-acuan Gudang). |
| 7 | `features/documents/DocumentCenter.jsx:19-20, 48-49`; `DocumentActionsBar.jsx:14, 45` | `ESIGN_ROLES.includes(role)` literal | `esign.sign` (`routers/esign.py:46, 63`) | **B**: tombol tanda tangan hilang untuk semua peran kustom. |
| 8 | `features/finance/amendments/AmendmentTrailPanel.jsx:20, 35` | `PROPOSER_ROLES.includes(role)` (admin, manager, sales) | `finance_amendment.propose` (`routers/amendments.py:46, 78, 92`) | **B**: juga untuk Admin Sales & Finance bawaan. |
| 9 | `features/catalog/CatalogWorkspace.jsx:44` | `["admin","md"].includes(role)` | `product.view` + `role_in(LIFECYCLE_ROLES)` (`master_governance.py:146`, `master_usage_service.py:68-70`) | **B** untuk acuan MD (server boleh, tombol tidak ada); C untuk lainnya. |
| 10 | `features/admin/po/PODetailPanel.jsx:91`; `POCompactPanel.jsx:33`; `features/purchasing/PurchaseApprovalView.jsx:84, 93` | `roleSatisfies(role, required_role)` | login + peringkat (`purchase_orders.py:798-812`) | **C**: izin "Setujui" tak berpengaruh; acuan Manajer selalu bisa. |
| 11 | `features/purchasing/VendorBillsView.jsx:68`; `LandedCostView.jsx:50` | `roleSatisfies` | login + peringkat (`vendor_bills.py:443-455`; `landed_cost.py:238-247`) | **C**. |
| 12 | `features/crm/CrmView.jsx:19, 26-27` | `isManager = roleIs(admin, manager)` → tab Skema, Persetujuan Kredit | `require_role(["manager"])` (`crm.py:140-142`) | **C**: "Pelanggan: Lihat saja" + acuan Manajer tetap memutus kredit. |
| 13 | `features/crm/Customer360Panel.jsx:36, 76` | `isManager` → "Pindah Sales" | `require_role(["manager"])`, target wajib `role: "sales"` (`crm.py:70-73`) | **C** + target ber-peran kustom ditolak. |
| 14 | `features/crm/SalesForceDashboard.jsx:16, 104` | `isManager` → Set Target, papan peringkat | `require_role(["manager"])` (`crm.py:268, 327, 370, 425`) | **C**. |
| 15 | `features/marketing/PostDetailModal.jsx:29` | `canEdit && roleIs(admin, manager)` | `role_in(APPROVE_ROLES)` (`marketing_service.py:208`); aksi `marketing.approve` tak dipakai | **C**: centang "Setujui" di Marketing tanpa efek. |
| 16 | `features/marketing/Campaigns.jsx:33`; `TemplatePicker.jsx:16` | daftar literal | `role_in(BILL_APPROVER_ROLES)` (`marketing_cost_service.py:220`); literal (`routers/marketing.py:384`) | **B** untuk acuan Finance/Manajer (server `role_in` boleh, layar literal tidak). |
| 17 | `features/samples/SampleOrdersView.jsx:71` | `can(approve_payment) && roleIs(finance, sample_admin, manager, admin)` | izin + `role_in` (`sample_orders.py:180-181`) | **C**: izin saja tidak cukup; tanpa acuan tak bisa. |
| 18 | `features/pettycash/CashAdvanceDetail.jsx:40` | `roleIs(role, stageRoles[...])` | `role_in(role, stage["roles"])` (`cash_advance_service.py:247, 269`) | **C**: tahap persetujuan kas kecil per nama peran. |
| 19 | `features/sales/SalesPortal.jsx:319` | `user.role === "sales"` (literal) | `role_in(("sales",))` (`sales_orders.py:396`) | **A**: acuan Sales melihat pemilih roll saat dimatikan, lalu ditolak 400. |
| 20 | `features/wms/grn/GoodsReceiptsView.jsx:23-24, 42, 88`; `features/settings/ReceivingOcrSettings.jsx:19` | daftar literal | `goods_receipt.*` + `role_in(admin, manager)` untuk ganti mode (`goods_receipts.py:116-119`) | **B**: bagian penerimaan lama & pintasan pengaturan tidak tampil untuk peran kustom. (I untuk sisi server bagian lama) |
| 21 | `routers/inspections.py:74, 464` → dipakai layar inspeksi | bendera `can_release_hold` / `can_create` dihitung literal | `role_in(HOLD_RELEASE_ROLES)` (`inspection_service.py:1684, 1725`) | **B**: acuan Manajer boleh di server, bendera layar "tidak". |
| 22 | `features/finance/ClosingView.jsx:47`; `features/settings/config/SettingsHub.jsx:380` | `role === "admin"` | `closing.py:79, 108`; `config.py:57, 66` | **C**: khusus Admin; tidak bisa didelegasikan. |
| 23 | `components/AskKnButton.jsx:4, 20`; `App.js:310`; `features/mobile/MobileOpsApp.jsx:138, 214` | daftar literal 6–7 peran | `role_in(role, ai.enabled_roles)` (`routers/ai_analytics.py:22-23`) | **B**: tombol "Tanya KN" hilang untuk peran kustom walau server mengizinkan (lewat acuan). |
| 24 | `features/mobile/MobileAppSwitch.jsx:48-53`; `features/sales/mobile/MobileOrders.jsx:42` | `roleIs` memilih aplikasi HP | — | **C**: tata letak HP ikut acuan; tanpa acuan = aplikasi umum. |
| 25 | `features/settings/entities/AccountFormDrawer.jsx:49` | `CROSS_ROLES.includes(role)` (statis) | `role in CROSS_ENTITY_ROLES` dinamis (`user_admin_service.py:145`) | PR-UX-09. |

Contoh awal Anda (`CrmView.jsx:19`) = baris #12: layar dan server sama-sama memakai nama peran, jadi tombol tidak "bohong" — tetapi fiturnya tidak bisa diberikan/dicabut dari layar peran.

---

## Lampiran C — Daftar

### C.1 `role_in` cakupan data (35)

`routers/admin.py:269` · `ai_analytics.py:429` · `crm.py:126, 135, 254, 358, 413` · `crm_omnichannel.py:76, 132, 202` · `customers.py:102` · `design_requests.py:49` · `logistics.py:37` · `price_approvals.py:179, 215` · `sales_orders.py:396, 671` · `sample_orders.py:247` · `warehouses.py:187` · `services/analytics_engine.py:71` · `analytics_facts.py:58` · `customer_service.py:400, 419, 438, 455` · `export_engine.py:61, 222, 228, 232` · `hr_payroll_service.py:250` · `location_scope.py:74` · `logistics_service.py:152` · `product_exclusivity.py:60` · `sales_ownership.py:49` · `stock_figures.py:223`.

### C.2 Menu/tab di luar katalog modul

Menu: `home` (Beranda), `my-desk` (Meja Saya), `tanya-kn`, `sales-admin-desk`, `finance-desk`, `md-desk`, `warehouse-admin-desk`, `sample-admin-desk`, grup `meja-peran`, `cs-bom` (segera hadir); `hr-my-profile` selalu tampil.
Tab: `customers-master`, `internal-prices`, `reimburse-payables`, `amendment-reasons`, `incentive-rates`, `settings-receiving-ocr`, `bank-recon-rules`, `permission-matrix` (alias).

### C.3 Tab yang induknya milik modul lain

`bi-finance` (modul Laporan; induk Dasbor Keuangan/Keuangan) · `client-dataset-import` (modul Produk; induk Master Data/Pengaturan) · `supplier-internal-prices` (modul Antar Badan Usaha; induk Master Pembelian).

### C.4 Perbandingan literal tanpa mengenal acuan (server)

`routers/marketing.py:384` · `routers/inspections.py:74, 464` · `routers/home.py:51` · `services/rnd_spec_service.py:343` · `services/special_order_fulfillment.py:335` · `services/inspection_service.py:689, 713` · `services/ai_chat_service.py:100` · `services/approval_matrix_service.py:248` · `services/ai_templates.py:29, 114` · `services/ai_schedules.py:43, 81`.

---

## Lampiran D — Aksi yang bisa dicentang tetapi tidak ditemukan pemeriksanya

Terbukti tidak diperiksa (T): `purchase_order.approve`, `purchase_order.reject`, `landed_cost.approve`, `landed_cost.reject`, `vendor_bill.reject`, `reports.view`, `reports.export`, `marketing.approve`, `sales_pov.commercial`.
Tidak ditemukan dalam bentuk literal apa pun (I — bisa saja lewat variabel): `esign.manage`, `finance_case.admin`, `interco.update`, `inventory.create`, `md_quality.view`, `order.print`, `tax_invoice.print`, `template.print`, `template.import`, `template.export`, `transfer.complete`, `uom.import`, `uom.export`.
Diperiksa secara dinamis (bukan temuan): `field_visibility.*`, `goods_receipt.*`, `od_fulfillment.*`, `rnd.assess_* / decide_*`, `sales_return.split_cutloss`, `finance_amendment.approve`, `order.approve_price_edit`, `period.backdate`. Hanya dipakai ekspor/notifikasi: `entity.view`, `label.view`, `wms.dispatch`.

## Lampiran E — Contoh beda label (editor ↔ pesan galat/jejak)

Halaman: `permission` "Peran & Hak Akses" ↔ "Matriks Izin" · `approval` "Matriks Persetujuan" ↔ "Persetujuan" · `ar_receipt` "Kwitansi / Uang Masuk (AR)" ↔ "Penerimaan AR" · `interco` "Transaksi Antar PT (barang)" ↔ "Antar-Badan Usaha" · `purchase_order` "Pesanan Pembelian (PO)" ↔ "Purchase Order" · `rnd` "Riset & Sample" ↔ "R&D" · `landed_cost` "Landed Cost" ↔ "Biaya Masuk (landed cost)" · `hr` "SDM / Karyawan" ↔ "SDM (HRD)". (47 total)
Aksi: `release_unpaid` "Kirim tanpa lunas…" ↔ "Lepas Sebelum Lunas" · `dispose` "Lepas aset" ↔ "Hapus Buku" · `release` "Rilis" ↔ "Lepaskan" · `override` "Override / edit SO" ↔ "Kecualikan Aturan" · `pegging` "Pegging" ↔ "Alokasi Stok" · `generate` "Generate" ↔ "Hasilkan" · `invoice` "Buat faktur" ↔ "Tagihkan" · `manage_payroll` "Kelola payroll" ↔ "Kelola Gaji". (46 total)
Tidak ada di kamus frontend: halaman `field_visibility`, `goods_receipt`, `sales_pov`; aksi `approve_price_edit`, `assess_*`, `decide_*` (6), `choose_route`, `close`, `commercial`, `count`, `grade`, `lot`, `origin`, `override_default`, `post_logistics`, `review`, `split_cutloss`, `view_cost`.

## Lampiran F — Endpoint tulis yang hanya menuntut `*.view` (32)

Benar-benar menulis: `POST /rfid/roll-scans` (`rfid.py:225`, `wms.view`) · `POST /color-library/{id}/use-requests` (`color_library.py:82`, `color.view`) · `POST /lots/{id}/label` (`lots.py:185`, `inventory.view`) · `PATCH /products/{id}/media/{mid}` (`product_media.py:89`, `product.view` + kemampuan tambahan) · `PUT /rnd/divisions/members` (`rnd_org.py:59`, `rnd.view` + acuan manajer) · `DELETE /master/{kind}/{mid}/purge` (`master_governance.py:146`, `product.view` + acuan admin/md) · `DELETE /export/templates/{id}` (`export_center.py:363`).
Pratinjau/simulasi (wajar): `config/impact-preview`, `sales-orders/preview-allocation / preview-lots / preview-roll-reconcile`, `sales-returns/cutloss/simulate / discount/simulate`, `supplier-contracts/resolve / tariff-preview`, `uom-conversions/convert / check-variance`, `access/roles/preview`, `bank-reconciliation/preview`, `finance/budget-check`, `document-templates/{id}/preview`, `suppliers/label-pattern/test`, `makloon-orders/estimate`, `payment-plans/preview`, `payment-variances/assess`, `templates/validate-script`, `process-recipes/forecast`, `inbound/tasks/{id}/preview-uom`, `rfid/printers/label-preview`, `export/preview`.

## Lampiran G — Cara mengulang hitungan

Skrip baca-saja (Python, tanpa menulis ke repo; dijalankan dengan `python3 -B`) ada di
`(folder kerja sementara di luar repo)/audit/work/`:
`a1.py` (sumber daya ↔ modul, label hilang, tingkat "Lihat saja") · `a2.py` (tingkat peran bawaan) · `a3.py` + `a11.py` (pasangan izin di backend ↔ aksi katalog) · `a4.py` + `a10.py` (pemakaian nama peran menurut maksud) · `a5.py` (310 setelan Pusat Pengaturan; modul `bcrypt/motor/pymongo` ditiru karena tidak terpasang) · `a6.py` + `a9.py` (id menu/tab ↔ modul) · `a7.py` (endpoint tulis ber-izin lihat / tanpa izin) · `a8.py` (dua kamus label).

Batasan: tidak ada yang dijalankan terhadap server atau basis data; temuan bertanda **I** dan butir "perlu uji API" (PR-UX-07, -11, -20, -21) sebaiknya dikonfirmasi lewat uji peran × endpoint yang sedang Anda jalankan.
