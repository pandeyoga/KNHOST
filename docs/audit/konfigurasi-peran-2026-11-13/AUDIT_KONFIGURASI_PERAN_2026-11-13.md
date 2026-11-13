# Audit konfigurasi perusahaan, Pusat Pengaturan, dan peran kustom

Tanggal: 13 Nov 2026 · Kode: `dca195b` · Tidak ada kode aplikasi yang diubah.

Pertanyaan pemilik yang dijawab: *apakah konfigurasi dan peran kustom benar-benar bekerja, lengkap, masuk akal, dan
mudah dipakai?*

## 0. Jawaban singkat

| Pertanyaan | Jawaban | Dasar |
|---|---|---|
| Apakah nilai yang disimpan di Pusat Pengaturan sampai ke mesin? | **Pipanya ya, tetapi tidak semua pemakai membacanya dengan benar.** Dari 310 kunci, 287 diuji tulis di tingkat grup dan 242 di tingkat PT; semuanya terbaca kembali lewat tiga jalur baca, nilai tak sah ditolak. Namun sedikitnya 7 kunci dibaca mesin dari nilai grup walau layar menampilkan nilai PT, 6 kunci aktif tidak menggerakkan apa pun, dan perubahan berjadwal baru dipakai sebagian mesin setelah seseorang membuka layar Pengaturan | Dijalankan (§2.1, KF-09) + dibaca (KF-10, KF-11) |
| Apakah izin "kelola pengaturan" bekerja? | **Tidak.** Pemegang izin itu ditolak di 232 dari 310 pengaturan, dengan pesan yang menyebut izin yang sebenarnya sudah ia miliki. Praktis hanya Admin yang bisa mengubah | Dijalankan (KF-01) |
| Apakah matriks izin ditegakkan server? | **Ya, konsisten** — 16 peran × 786 rute baca dibandingkan dengan matriks, dan 962 rute tulis dipanggil akun tanpa izin (898 ditolak, tak satu pun rute berizin terpakai); penyimpangan hanya terjadi di tempat wewenang ditentukan lewat **nama atau pangkat peran** | Dijalankan (§3.1) |
| Apakah peran kustom bekerja? | **Sebagian.** Membuat, mengubah, menghapus berjalan. Tetapi peran kustom mewarisi akses dari nama peran acuannya terlepas dari tingkat yang diatur, dan peran yang diberi izin tanpa peran acuan tetap ditolak di sejumlah pintu | Dijalankan (PR-01, PR-03) |
| Apakah mencabut semua izin sebuah peran mencabut wewenang menyetujui? | **Tidak.** Peran kustom beracuan Manajer dengan nol izin tetap bisa menyetujui PO Rp250 juta dan tagihan pemasok Rp75 juta | Dijalankan (PR-05) |
| Apakah perubahan izin peran bawaan bertahan? | **Tidak selalu.** Sebagian perubahan ditimpa ulang setiap server dinyalakan | Dijalankan (PR-12) |
| Apakah aman mendelegasikan kelola akun ke peran kustom? | **Tidak.** Peran kustom yang diberi kelola akun bisa menjadikan dirinya Admin dan mereset sandi Admin | Dijalankan (PR-02) |
| Apakah layarnya sendiri bekerja bila dipakai? | **Ya untuk alur utamanya.** Lewat peramban: ubah pengaturan per PT, riwayat, kembalikan ke nilai grup, penolakan nilai tak sah, buat peran, buat akun, masuk sebagai peran baru — 18 dari 21 langkah sesuai harapan; tiga sisanya temuan (KF-01 terlihat di layar, PR-06, PR-16) | Dijalankan (§5a) |
| Apakah setiap layar punya endpoint-nya? | **Ya**, 1.790 panggilan API di layar diperiksa; satu yang tidak punya rute, dan satu rute selalu galat | Statik + dijalankan (§5) |
| Apakah lengkap dan masuk akal? | **Belum.** 72 nilai bisnis masih ditulis mati di kode; penomoran dokumen dan sebagian besar aturan persetujuan tidak bisa diatur; 5 isian master PT tidak dibaca apa pun | Dibaca (§4) |
| Apakah bahasanya mudah? | **Belum merata.** 51 label lebih dari 45 karakter, 63 pengaturan tidak menjelaskan arti nilai 0, 12 label memuat istilah Inggris/teknis; penjaga bahasa repo mencatat 113 teks antarmuka belum berbahasa Indonesia | Dihitung (§2.3) |

Jumlah temuan: Pusat Pengaturan 13 (`KF`), peran dan izin 16 (`PR`), konfigurasi perusahaan 36 (`KP`), ditambah temuan
layar dari dua tinjauan baca di lampiran (`PR-UX` 44 butir; `KF-UX` 28 butir).

## 1. Cara kerja dan batas

| Cara | Cakupan | Bukti |
|---|---|---|
| **Aplikasi utuh dijalankan** di database tiruan dalam memori (seluruh `server.app`, proses awal, seed), lalu endpoint dipanggil lewat HTTP di dalam proses | Pusat Pengaturan (310 kunci), peran × rute baca (16 × 786), 3 akun × rute tulis (962), uji kenaikan hak, uji persetujuan | `bukti/t1_config.py`, `t2_roles.py`, `t3_escalation.py`, `t3b_eskalasi_akun.py`, `t9_tulis_tanpa_izin.py`, `t10_setuju_tanpa_izin.py` |
| **Inventaris statik** dengan pengurai sintaks | 1.749 endpoint dan jenis gerbangnya; 336 pasangan izin yang dipakai kode vs 381 di matriks; 1.790 panggilan API layar vs rute | `bukti/inv_endpoints.py`, `fe_be_routes.py` |
| **Uji jalan layar** di peramban tanpa kepala, terhadap aplikasi utuh di port nyata | 21 langkah di Pusat Pengaturan dan Peran & Hak Akses; sapuan buka-layar | `bukti/serve_mem.py`, `ui_pengaturan_peran.js`, `ui_sapuan_layar.js`, `bukti/layar/` |
| **Gate statik repo** | `bash scripts/gate.sh --quick` | `docs/blueprint/03_LINGKUNGAN_UJI.md` §4 |
| **Membaca kode** (tiga tinjauan) | Bahasa dan pengelompokan pengaturan; layar peran dan gerbang peran di layar; konfigurasi perusahaan lain | `lampiran/A_*.md`, `B_*.md`, `C_*.md` |

Yang **tidak** dilakukan: menguji indeks unik dan permintaan bersamaan; memeriksa data nyata. Layar dibuka di peramban
hanya untuk Pusat Pengaturan, Peran & Hak Akses, dan sapuan buka-layar (§5a); penilaian layar lain di lampiran tetap dari
membaca kode. Rute tulis diuji **gerbangnya** (siapa yang ditolak), dengan isi permintaan buatan dari skema; **hasil kerja** tiap
rute tulis hanya diuji untuk pengaturan, peran, akun, persetujuan PO dan tagihan pemasok, dan tiga temuan keuangan di §5.
25 dari 962 rute tulis tidak tercapai gerbangnya (`LAMPIRAN_DAFTAR.md` §I.3). Database tiruan hanya berisi seed awal (4 akun, 3 PT), jadi rute yang butuh dokumen dijawab 404
dan dianggap "lolos gerbang".

Tanda di tabel temuan: **[dijalankan]** dibuktikan dengan uji jalan; **[statik]** dari inventaris terprogram;
**[dibaca]** dari membaca kode.

## 2. Pusat Pengaturan

### 2.1 Yang terbukti bekerja

Registry memuat 310 kunci di 23 kelompok: 306 aktif, 4 ditandai tidak dipakai. 247 kunci berlapis grup → PT, 50 hanya
grup, 13 berlapis sampai pelanggan atau barang.

| Uji | Hasil |
|---|---|
| Tulis di tingkat grup lewat `PUT /api/config/values`, lalu baca lewat API, lewat pembaca baru (`config_resolver.value_of`), dan lewat pembaca lama (`get_effective_settings` / dokumen `system_settings`) | 287 dari 287 cocok di ketiga jalur |
| Tulis di tingkat PT; PT lain harus tetap | 242 dari 242 benar di pembaca baru; 240 di pembaca lama (dua sisanya = KF-04) |
| Cabut lapisan PT → kembali ke nilai grup | 242 dari 242 |
| Nilai tak sah (di luar batas, pilihan tak dikenal, tipe salah) | 264 dari 264 ditolak 400 |
| Kunci berisiko tinggi tanpa alasan | 97 dari 97 ditolak |
| Kunci "tidak dipakai" menolak ditulis | 4 dari 4 |
| Kembalikan ke bawaan | 306 dari 306 |
| Kode yang disebut sebagai pemakai kunci memang memuat kunci itu | 301 dari 306 (lima sisanya memakai nama kunci yang dirakit atau dibaca layar) |

19 kunci bertipe tabel/daftar hanya diuji simpan-ulang. Yang dibuktikan di sini adalah **pipa** dari layar sampai
pembaca; bahwa setiap pemakai lalu berperilaku sesuai nilainya tidak diuji satu per satu.

### 2.2 Temuan

| ID | Tingkat | Temuan | Bukti | Akibat |
|---|---|---|---|---|
| KF-01 [dijalankan] | Tinggi | Izin `settings.manage` tidak berpengaruh. Peran kustom yang memegangnya ditolak 403 di tingkat grup maupun PT; `can_edit` bernilai salah untuk 232 dari 232 kunci yang dijaga izin itu. Pesannya: "… tidak bisa Anda ubah (butuh izin settings.manage)" | `backend/routers/config.py:45-68` (`_may_edit`: semua 310 kunci ber-`owner_role` "admin", dan cabang terakhir menolak siapa pun selain admin) | Mengatur perusahaan tidak bisa didelegasikan; tombol izin di layar peran menyesatkan |
| KF-02 [dijalankan] | Tinggi | 48 pengaturan bisa diubah siapa pun yang peran acuannya Manajer — termasuk peran kustom dengan semua modul "Tidak ada" | `backend/routers/config.py:59` (`role_in(role, entry.roles)`); daftar di `LAMPIRAN_DAFTAR.md` §G | Wewenang mengubah aturan gudang, lot, satuan, dan lain-lain tidak terlihat dan tidak bisa dicabut di layar peran |
| KF-03 [dijalankan] | Sedang | Semua pengguna yang login — termasuk Sopir — bisa membaca seluruh 310 pengaturan, nilai efektif, dan riwayat perubahannya | `backend/routers/config.py:159-222, 350-365` (hanya `current_user`; satu-satunya batas untuk peran MD di `READ_LIMITS`) | Ambang persetujuan, aturan komisi, dan aturan pencocokan bank terbuka untuk semua |
| KF-04 [dijalankan] | Sedang | Untuk PT non-PKP, layar menampilkan tarif PPN dan status e-faktur lapisan PT, padahal mesin memaksa tarif 0 dan e-faktur mati | `backend/services/config_service.py:247-256`; uji T1 pada `ent_kanda` | Layar menampilkan nilai yang tidak dipakai. Kasus sejenis: 22 pasangan "dua tempat" di `lampiran/C_…` Lampiran B |
| KF-05 [statik] | Sedang | 7 kunci dilaporkan "mati" oleh gate (`returns.grade_price_factors.*`) — koreksi: wadahnya **dibaca** mesin (`backend/services/return_grade_impairment.py:21`), tetapi belum punya entri registry sehingga gate salah menilainya; 2 kunci dibaca kode tanpa layar (`interco_payment.allow_netting`, `…require_full_payment`), 2 layar di luar Pusat Pengaturan menulis lewat jalur lama tanpa riwayat (`ReturnAssumptionsPanel.jsx`, `IntercoPaymentSchedule.jsx`). Satu kunci aktif berlabel "(Lama) … TIDAK DIPAKAI LAGI" | `scripts/audit_config_wiring.py` (gate INV-CFG merah); `contra_bon.qty_tolerance_percent` | Dua sumber kebenaran; perubahan tanpa jejak |
| KF-06 [statik] | Rendah | 11 kunci punya nilai cadangan di kode yang berbeda dari bawaan registry; 3 rujukan pemakai menunjuk fungsi yang tidak ada | `LAMPIRAN_DAFTAR.md` §H; `case.sla_hours`, `case.sla_hours_high`, `ai.route_threshold_pct` | Bila dokumen pengaturan tidak lengkap, mesin memakai nilai yang tidak tampil di layar |
| KF-07 [dibaca] | Sedang | 13 kunci menawarkan lapisan pelanggan/barang, tetapi layar hanya menyediakan pilihan Grup dan PT | `frontend/src/features/settings/config/SettingsScopeBar.jsx:68-74` | Aturan per pelanggan (mis. denda) hanya bisa diisi lewat API |
| KF-08 [statik] | Rendah | Penjaga pengaturan milik repo hanya memeriksa 78 kunci lama, bukan 310 kunci registry | Keluaran `audit_config_wiring.py`: "Total kunci terdeklarasi: 78" | Kunci baru bisa mati tanpa ketahuan |
| KF-09 [dijalankan] | Tinggi | Perubahan **berjadwal** ("berlaku sejak" di masa depan) tidak diaktifkan oleh penjadwal. Pembaca baru memakainya tepat waktu, tetapi pembaca lama baru melihatnya setelah seseorang membuka layar Pengaturan atau Kesehatan Pengaturan. Uji: `ar.grace_days` dijadwalkan 0 → 5; tiga detik setelah jatuh tempo pembaca baru = 5, pembaca lama = 0; setelah layar dibuka, pembaca lama = 5 | `backend/services/config_resolver.py:530` (`apply_due_values`), dipanggil hanya dari `backend/routers/config.py:193` dan `:371`; `bukti/t5_jadwal_pengaturan.py` | Dua bagian mesin memakai nilai berbeda untuk aturan yang sama sampai ada yang membuka layar; jadwal juga tidak bisa dibatalkan |
| KF-10 [dibaca] | Tinggi | Sedikitnya 7 kunci menampilkan nilai khusus PT, tetapi pemakainya membaca nilai grup: `finance.default_payment_term_code`, `inventory.default_uom`, dua kunci `notif.*`, tiga kunci `receiving.*` di jalur pindai lama. Dua kunci diam-diam mengubah nilai 0 menjadi 1 atau 3 | `backend/routers/sales_orders.py:353-356`; rincian 12 kasus di `lampiran/A_pengaturan_ux.md` bagian 6 | Mengatur per PT tampak berhasil tetapi tidak berakibat |
| KF-11 [dibaca] | Tinggi | Enam kunci berstatus aktif tidak menggerakkan mesin: empat `role_home.*` (halaman awal tiap peran — tidak ada pembacanya), `tax.efaktur_enabled` (hanya dibaca layar ringkasan pajak dan simulator), `contra_bon.qty_tolerance_percent`. Pemeriksa kesehatan meloloskannya karena hanya mencocokkan kata | `backend/services/config_service.py:124`; `backend/services/tax_center_service.py:161`; `backend/services/config_health.py:45-52` | Tombol yang bisa diubah tanpa akibat |
| KF-12 [dibaca] | Sedang | Tombol "Default" pada cakupan PT menulis nilai bawaan **sebagai nilai khusus PT** (bukan kembali mengikuti grup), tanpa konfirmasi, dan melewati kewajiban alasan. Fitur "coba dulu" untuk QC dan pajak memakai rumus yang berbeda dari mesin | `lampiran/A_pengaturan_ux.md` bagian 4 dan temuan terkait | PT terlepas dari nilai grup tanpa disadari |
| KF-13 [dibaca] | Sedang | Editor untuk kunci rumit belum layak untuk orang awam: `approval.extra_levels` berupa JSON mentah; 14 daftar diketik berkoma tanpa pemeriksaan isi; `value_format` tidak dikirim ke kartu sehingga `receiving.client_po_patterns` kemungkinan tidak bisa disimpan | `lampiran/A_pengaturan_ux.md` bagian 5 | Salah ketik tersimpan atau perubahan gagal tanpa penjelasan |

### 2.3 Mutu teks dan pengelompokan

Dihitung dari isi registry (306 kunci aktif):

| Ukuran | Jumlah |
|---|---|
| Label lebih dari 45 karakter | 51 |
| Kunci angka tanpa satuan | 22 |
| Kunci yang boleh bernilai 0 tetapi penjelasannya tidak menyebut arti 0 | 63 |
| Label memuat istilah Inggris/teknis ("default", "override", "mode", "SLA", "3-way match") | 12 |
| Kelompok berisi lebih dari 25 kunci | 3 (Stok, Satuan & Alokasi 38; R&D & Desain 27; Penerimaan Barang 26) |

Tinjauan baca atas seluruh 310 kunci (`lampiran/A_pengaturan_ux.md`, 28 temuan `KF-UX`) mengusulkan teks pengganti untuk
208 kunci, mencatat 33 konsep yang memakai lebih dari satu istilah, dan mengusulkan 13 kelompok bersub-judul sebagai
pengganti 23 kelompok sekarang (dua layar saat ini memuat 85 dan 69 kunci).

## 3. Peran dan izin

### 3.1 Yang terbukti bekerja

- Dari 1.749 endpoint, 1.566 dijaga izin, 17 dijaga izin lewat cabang, 38 dijaga nama peran, 107 hanya butuh login,
  21 tanpa sesi (perangkat, login, verifikasi publik).
- 16 peran (12 bawaan + 4 peran kustom uji) dijalankan terhadap 786 rute baca. Untuk rute berizin, jawaban server sesuai
  matriks; tidak ditemukan rute berizin yang terbuka bagi peran tanpa izinnya.
- 962 rute tulis dipanggil oleh akun berperan kustom tanpa acuan dan tanpa satu izin pun: 898 ditolak (401/403), 25
  tidak teruji, 2 galat server, 37 melewati gerbang. Dari 37 itu: 17 memang milik sendiri atau validasi tanpa tulis
  (absen, notifikasi, lokasi kerja); 10 hanya mendahulukan validasi atau pencarian dokumen sebelum gerbang izin (gerbangnya
  ada menurut inventaris statik; empat di antaranya dibaca langsung); 2 diperiksa per kunci pengaturan (T3); 8 adalah persetujuan yang diperiksa lewat pangkat
  peran (PR-05). Tidak ditemukan rute tulis berizin yang bisa dipakai akun tanpa izin (`LAMPIRAN_DAFTAR.md` §I).
- Membuat, mengubah, menghapus peran kustom dan mengubah peran sendiri (ditolak) berjalan seperti dirancang.
- 79 dari 80 sumber daya izin masuk tepat satu modul akses.

### 3.2 Temuan

| ID | Tingkat | Temuan | Bukti | Akibat |
|---|---|---|---|---|
| PR-01 [dijalankan] | Tinggi | Peran kustom beracuan Manajer dengan **semua modul "Tidak ada"** tetap mendapat 200 di 23 rute yang bagi Sopir 403: HPP rata-rata (`/costing/wac`), beranda Manajer untuk semua PT, papan peringkat sales, tarif insentif, alat kebersihan data, pemakaian asisten. Ia juga bisa mengubah 48 pengaturan (KF-02) dan memenuhi tuntutan persetujuan "manager". Di rute **tulis** (T9) ia melewati 28 gerbang yang menolak peran tanpa acuan; lima di antaranya langsung berhasil: membuat tarif insentif, memposting insentif ke buku besar, mengubah kebijakan kontrak pemasok, membangkitkan notifikasi, memindai wawasan asisten (semuanya 200) | `backend/role_registry.py:334-340` (`role_in` mengenali peran acuan); `backend/dependencies.py:93-98` (`require_role`); `LAMPIRAN_DAFTAR.md` §E | Tingkat akses di layar peran tidak menggambarkan akses sebenarnya; akses tidak bisa dicabut tanpa mengganti peran acuan |
| PR-02 [dijalankan] | Tinggi | Peran kustom yang diberi modul "Pengaturan, Pengguna & Hak Akses" bisa: menjadikan akunnya sendiri Admin (200), membuat akun Admin (200), mereset sandi Admin (200), mengubah izin peran Manajer (200), membuat peran baru beracuan Manajer (200) | `backend/routers/users.py:121-158, 183-193`; `backend/routers/access_roles.py:78-98`; `bukti/t3b_eskalasi_akun.py` | Kelola akun tidak bisa didelegasikan dengan aman. Bawaan hanya Admin yang memegang izin ini, jadi celah terbuka saat didelegasikan |
| PR-03 [dijalankan] | Tinggi | Izin tidak cukup: peran kustom tanpa peran acuan yang diberi izin tetap ditolak di 38 endpoint ber-`require_role` dan di gerbang nama peran di dalam handler (registri lot, divisi R&D, rapor desainer, papan SLA, asisten analitik) | `LAMPIRAN_DAFTAR.md` §A, §F; `ai.enabled_roles` | Peran baru tidak bisa diberi pekerjaan itu kecuali dijadikan turunan Manajer — yang lalu membuka PR-01 |
| PR-04 [statik + dijalankan] | Sedang | 107 endpoint hanya butuh login; 41 di antaranya menulis. Termasuk papan Meja Finance/Sales/Gudang, target dan skema insentif, seluruh pengaturan (KF-03), dan persetujuan/penolakan PO, tagihan pemasok, voucher biaya masuk | `LAMPIRAN_DAFTAR.md` §B, §C | Sebagian memang milik sendiri (`/me`); sisanya membuka data atau bergantung pada pemeriksaan lain di dalam handler |
| PR-05 [dijalankan] | Tinggi | Wewenang menyetujui PO dan tagihan pemasok ditentukan **peringkat peran acuan** (`role_satisfies`), bukan izin. Uji T10: peran kustom beracuan Manajer dengan **nol izin** menyetujui PO Rp250.000.000 (200, status menjadi disetujui), menolak PO lain (200), dan menyetujui tagihan pemasok Rp75.000.000 yang lalu terposting (200); peran tanpa acuan ditolak (403). Izin `purchase_order.reject`, `vendor_bill.reject`, `landed_cost.approve/reject` ada di matriks tetapi tidak pernah diperiksa | `backend/routers/purchase_orders.py:797-822`; `backend/routers/vendor_bills.py:442-457` | Peran kustom tanpa acuan tidak bisa menyetujui walau diberi izin; peran beracuan Manajer bisa walau izinnya dicabut. Pesan galat mencetak id peran mentah |
| PR-06 [dibaca] | Sedang | Beranda, cakupan data ("hanya miliknya"), peringkat persetujuan, dan penerima notifikasi melekat pada nama/acuan peran dan tidak bisa diatur dari layar peran. Kode memuat 89 pemakaian `role_in(` dan 67 perbandingan `role` langsung di `backend/services` + `backend/routers` | Hitungan terprogram; rincian di `lampiran/B_peran_ux.md` | Peran kustom tanpa acuan mendarat di profil sendiri, tidak punya meja kerja, dan cakupan datanya tidak terdefinisi |
| PR-07 [statik] | Sedang | 41 pasangan izin di matriks tidak pernah diperiksa server: 7 hanya dipakai layar untuk menampilkan tombol, 34 tidak dipakai sama sekali (mis. `period.backdate`, `reports.view`, `tax_invoice.print`) | Hitungan `bukti/inv_endpoints.py` + matriks | Tombol izin yang tidak berakibat apa pun |
| PR-08 [dibaca] | Sedang | Modul akses "Pengaturan, Pengguna & Hak Akses" menyatukan akun, peran, pengaturan, badan usaha, dan penjadwal dalam satu tombol tingkat. Dua modul (`field_visibility`, `sales_profile`) tidak berubah apa pun pada tingkat "Lihat saja" | `backend/access_modules.py:200-212` | Memberi "kelola akun" otomatis memberi "ubah peran" dan "kelola PT" |
| PR-09 [dijalankan] | Rendah | Pesan penolakan menampilkan nama teknis: "Permission ditolak: goods_receipt.view", "Role Anda: 'cr_…'" | `backend/dependencies.py:112`; `backend/routers/purchase_orders.py:812` | Pengguna tidak tahu harus meminta akses apa |
| PR-10 [statik] | Rendah | Satu pilihan izin merujuk sumber daya yang tidak ada (`gl.view`) | `backend/routers/supplier_contracts.py:208` | Pilihan mati |
| PR-12 [dijalankan] | Tinggi | Perubahan Admin atas izin **peran bawaan** ditimpa setiap server dinyalakan. Uji: Admin mencabut modul "Uang Masuk" dari Sales (izin kwitansi hilang) → proses awal aplikasi dijalankan ulang → izin `ar_receipt: [create]` kembali | `backend/bootstrap.py:402` (`sync_permission_revocations`, berisi daftar cabut/atur-ulang/beri yang dijalankan tanpa syarat), dipanggil di `backend/bootstrap.py:1648`; `bukti/t4_peran_bawaan.py` | Inilah yang terasa sebagai "pengaturan peran tidak jalan": perubahan tersimpan, lalu diam-diam batal setelah restart. Peran kustom tidak terkena |
| PR-13 [dijalankan] | Tinggi | Pindah-massal akun bisa mengosongkan Admin. `POST /api/access/roles/admin/move-users` ke peran lain dijawab 200; akun Admin aktif dari 1 menjadi 0, tanpa penjaga "admin terakhir" | `backend/services/custom_role_service.py:348` (`move_users`); `backend/routers/access_roles.py:51`; `bukti/t4_peran_bawaan.py` | Satu salah klik membuat sistem tanpa Admin; pemulihan hanya lewat basis data |
| PR-14 [dijalankan] | Sedang | Matriks izin bawaan punya **dua sumber yang bertentangan**. Contoh: `permissions_config.py` menulis Sales hanya boleh *melihat* kwitansi (dengan catatan keputusan pemisahan tugas), tetapi daftar di proses awal memberi Sales izin *membuat* kwitansi setiap server dinyalakan; yang berlaku saat jalan adalah yang kedua | `backend/permissions_config.py:142`; `backend/bootstrap.py:425, 460`; keluaran `bukti/t4_peran_bawaan.py` ("sales.ar_receipt sebelum: ['view', 'create']") | Membaca `permissions_config.py` saja memberi gambaran izin yang salah; dokumen rencana 13 Nov yang menyebut "Sales tidak berizin mencatat kwitansi" keliru dan sudah dikoreksi |
| PR-15 [dijalankan] | Tinggi | Menyetujui dan menolak PO **tidak memeriksa PT**. Uji T10: akun Finance bawaan yang hanya ditugaskan ke satu PT membuka PO milik PT lain → 404; menyetujui PO yang sama → 200, PO berubah menjadi disetujui atas namanya. Tagihan pemasok dan voucher biaya masuk sudah punya penjaga ini | `backend/routers/purchase_orders.py:797` (`approve_purchase_order`), `backend/routers/purchase_orders.py:920` (`reject_purchase_order`) — tanpa `guard_doc`; pembanding `backend/routers/vendor_bills.py:443` | Siapa pun yang pangkat perannya memenuhi tingkat persetujuan bisa memutus PO PT lain bila tahu id-nya |
| PR-11 [statik] | Sedang | Layar memakai izin di 269 tempat (`can(`), tetapi masih memakai nama peran di 117 tempat (53 `roleIs(` + 64 perbandingan `role`) | Hitungan terprogram; contoh di `lampiran/B_peran_ux.md` | Peran kustom melihat tombol yang ditolak server, atau tidak melihat tombol padahal berizin |

Catatan skala: registry peran disimpan di memori proses dan dimuat ulang saat peran diubah. Dengan satu proses server
(keadaan sekarang) ini aman; bila kelak dijalankan beberapa proses, perubahan peran tidak sampai ke proses lain.

## 4. Konfigurasi perusahaan di luar Pusat Pengaturan

36 temuan (`KP-01` … `KP-36`: 11 tinggi, 19 sedang, 6 rendah) beserta empat lampiran daftar ada di
`lampiran/C_konfigurasi_perusahaan.md`. Seluruhnya dari membaca kode; lima yang paling berakibat saya cek ulang pada
berkas:barisnya (KP-01, KP-02, KP-03, KP-09, KP-14) dan satu terbukti saat dijalankan (KP-17).

| Kelompok | Inti | ID |
|---|---|---|
| Master PT | Lima isian tidak dibaca kode mana pun (skema penomoran, penanggung insentif, awal tahun fiskal, templat bagan akun, induk grup); status PKP tidak bisa diubah setelah PT dibuat; validasi longgar | KP-01, 02, 23 |
| Kesiapan dan arsip PT | Daftar kesiapan hanya 8 butir dan satu tautannya salah; PT baru lahir tanpa rekening, kas, gudang; pemeriksaan sebelum arsip tidak lengkap | KP-10, 22, 24 |
| Persetujuan | Enam mekanisme hidup bersamaan, 38 antrean keputusan, tiga cara menentukan penyetuju; pilihan "Owner" dan "Diskon (%)" tidak berakibat; aturan PT menggantikan seluruh jenjang grup | KP-03, 04, 06, 07, 08, 25, 26 |
| Setuju-sendiri | 2 sakelar (bawaan melarang), 12 larangan ditulis mati, ≥ 14 pintu tanpa pemeriksaan; Admin selalu lolos | KP-05 |
| Penomoran | 59 awalan di 90 titik panggil ditulis mati; 18 jenis dokumen memakai deret bersama tanpa kode PT | KP-12, 13, 35 |
| Dokumen dan cetak | Identitas PT di tiga tempat; teks penutup dan slot tanda tangan tidak per PT; faktur tanpa rekening bank | KP-18, 19, 34 |
| Pengingat | Selang 11 job tidak bisa diubah walau layar menerima; penerima dan ambang hari ditulis mati | KP-09, 20, 21 |
| Rahasia dan perangkat | Token mesin absen dikirim utuh dan disimpan polos; token WhatsApp polos di dua tempat | KP-14, 15, 16, 31, 32 |
| Nilai ditulis mati | 72 nilai bisnis (hari blokir kredit, masa reservasi, ambang pesanan khusus, rantai uang muka, dan lain-lain) | KP-11, 27, 28, 30, 36 |
| Susunan menu | 12 hub / 30 tab; usulan 9 hub | KP-29, 33 |

Yang sudah benar dan tidak perlu dirombak: satu jalur validasi buat/ubah PT; awalan nomor PT terkunci setelah dokumen
pertama; arsip PT dengan pratinjau dampak; master berlapis grup → PT; pemetaan akun per PT yang beralasan dan beriwayat;
kunci asisten terenkripsi.

## 5. Temuan lain dari uji sapuan

| ID | Tingkat | Temuan | Bukti |
|---|---|---|---|
| KP-17 [dijalankan] | Sedang | `GET /api/entities/count` selalu galat 500: memakai nama `include_test` yang bukan parameternya | `backend/routers/entities.py:83-95` |
| MB-02 [dijalankan] | Rendah | `POST /api/interco/returns/{id}/approve` dengan id yang tidak ada dijawab galat 500, bukan 404: hasil pencarian yang kosong langsung dibaca isinya, sebelum izin diperiksa | `backend/routers/interco.py:425` (`approve_interco_return`) |
| MB-01 [statik] | Rendah | Layar tugas di HP memanggil `GET /api/products/{id}`, padahal rute itu hanya punya PATCH dan DELETE; galatnya ditelan sehingga data produk selalu kosong | `frontend/src/features/mobile/MobileTaskActions.jsx:79` |

Dari 786 rute baca yang dipanggil sebagai Admin dengan id contoh, hanya satu yang menjawab 500 (KP-17). Dari 962 rute
tulis yang dipanggil akun tanpa izin, satu menjawab 500 (MB-02).

Lingkungan uji yang sama dipakai untuk mereproduksi satu temuan audit keuangan lewat API yang sebenarnya: **FX-01**
(`bukti/t6_fx01_setoran_ganda.py`) — kasus "uang dipegang karyawan" Rp10.000.000, lalu aksi setor Rp10.000.000 →
dua transaksi kas masuk (Rp20.000.000) dan saldo piutang titipan karyawan (1-1280) menjadi −Rp10.000.000. Temuan itu
sebelumnya hanya dibaca dari kode.

Dua temuan dari riset modul (`docs/finance/rencana-2026-11-13/11_TEMUAN_TAMBAHAN.md`) juga dijalankan:

| Temuan | Uji | Hasil |
|---|---|---|
| **TX-01** | `bukti/t7_tx01_faktur_pengganti.py`: terbitkan faktur pajak (PPN Rp110.000), lalu terbitkan pengganti | Rekap PPN keluaran masa itu menjadi Rp220.000 (2 faktur), seharusnya Rp110.000 |
| **CR-01** | `bukti/t8_cr01_plafon_oleh_sales.py`: akun Sales mengubah pelanggannya sendiri | Plafon Rp5.000.000 → Rp900.000.000 dan status terblokir → aktif: 200 |

## 5a. Uji jalan layar (peramban)

Aplikasi utuh dinyalakan di port nyata (`bukti/serve_mem.py`: backend di database tiruan; frontend `craco start` dari
salinan `frontend/`), lalu dijalankan lewat peramban tanpa kepala. Skrip: `bukti/ui_pengaturan_peran.js`; hasil mentah
dan tangkapan layar: `bukti/layar/`.

| # | Langkah lewat layar | Yang terlihat | Dicek ke API | Hasil |
|---|---|---|---|---|
| A1 | Admin membuka Pusat Pengaturan | 23 kelompok, kartu tampil, tidak ada panggilan API yang gagal | registry 310 kunci | Sesuai |
| A2 | Mengubah "boleh kirim sebagian" untuk satu PT (sakelar → alasan → Simpan) | "Ya / Aktif" → "Tidak / Mati", lencana "nilai Sukacita", pemberitahuan "Tersimpan dan langsung berlaku di mesin." | PT itu `false`, PT lain tetap `true` | Sesuai |
| A3 | Muat ulang halaman | Nilai tetap | — | Sesuai |
| A4 | Membuka riwayat kartu | Perubahan dan alasannya tampil | — | Sesuai |
| A5 | "Kembalikan ke global" | Nilai kembali "Ya / Aktif" | PT itu kembali `true` | Sesuai |
| A6 | Mengisi denda 1.007 % (batas 100) | Ditolak; pesannya "'ar.denda_rate_pct_per_month' maksimum 100 (diberi 1007.0)" | Nilai tidak berubah | Sesuai; **pesan memakai kunci teknis** (KF-UX) |
| A7 | Menyimpan pengaturan berisiko tinggi tanpa alasan | Ditolak: "… berisiko tinggi — alasan perubahan WAJIB diisi." | Nilai tidak berubah | Sesuai |
| B1 | Membuat peran "Staf Penagihan Uji" (piutang: Kelola; pelanggan dan Pusat Persetujuan: Lihat) | Ringkasan "28 Tidak ada · 2 Lihat saja · 1 Kelola penuh", layar konfirmasi merinci tiga modul, pratinjau menu 9 layar | Peran tersimpan tanpa peran acuan | Sesuai |
| B2 | Membuat akun dengan peran itu | Akun tersimpan | Peran dan PT asal benar | Sesuai |
| C1 | Masuk sebagai akun itu | Menu = pratinjau di editor (Pusat Persetujuan, Pelanggan, Piutang, Uang Muka Pelanggan, Rencana Bayar, Saldo Kredit, Pajak, Pengaturan › Keuangan & Pajak, Profil Saya) | — | Sesuai. Mendarat di "Profil Saya", bukan meja kerja (PR-06) |
| C2 | Kerangka aplikasi saat masuk | Tidak ada pesan galat | `GET /api/finance/posting-failures/count` 403 dan `GET /api/sales/keep-pending` 403 di **setiap** layar; `GET /api/hr/employees/me` 404 | **Temuan PR-16** |
| C3 | Membuka Piutang dan Pelanggan | Layar terbuka, tanpa panggilan gagal | — | Sesuai |
| C3 | Membuka Pusat Persetujuan | Peringatan jujur: "Daftar ini belum lengkap: 6 kategori tidak bisa ditampilkan untuk peran Anda (…)" | 6 antrean dijawab 403 | Layar menangani dengan benar; editor peran tidak memberi tahu bahwa modul "Pusat Persetujuan" saja tidak membuka antrean apa pun (PR-UX) |
| C3 | Mengetik alamat Pusat Pengaturan, Buku Besar, Badan Usaha & Akses | Dikembalikan ke "Profil Saya" | Tidak ada panggilan | Sesuai |
| D1 | Peran dengan izin "kelola pengaturan" membuka Pusat Pengaturan | 25 dari 25 kartu terkunci, bertuliskan "Hanya admin yang boleh mengubah setting ini." | — | **KF-01 terbukti di layar** (`bukti/layar/D1_pengelola_pengaturan.png`) |

Ringkasnya: alur utama kedua layar **bekerja** dari klik sampai tersimpan, dan pratinjau menu di editor peran cocok dengan
menu yang didapat akun. Yang tidak bekerja adalah yang sudah ditemukan lewat API (KF-01, PR-06) ditambah satu temuan
baru:

| ID | Tingkat | Temuan | Bukti |
|---|---|---|---|
| PR-16 [dijalankan] | Rendah | Kerangka aplikasi memanggil dua endpoint di setiap layar tanpa melihat izin peran, sehingga peran yang tidak memegang izinnya menerima penolakan berulang (senyap, tidak tampil ke pengguna, tetapi memenuhi log dan menutupi penolakan yang sungguhan) | `bukti/ui_pengaturan_peran.js` langkah C2 |

Yang belum diuji lewat layar: layar lain di luar dua bidang ini (lihat sapuan di bawah), tampilan di HP, dan pembaca layar.

## 6. Garis dasar gate statik repo

`bash scripts/gate.sh --quick` pada `dca195b`: 13 gate merah, di antaranya penegak auth, penjaga atomisitas, penjaga
pengaturan, penjaga bahasa. Rinciannya di `docs/blueprint/03_LINGKUNGAN_UJI.md` §4. Artinya penjaga otomatis repo saat
ini tidak bisa dipakai sebagai tanda "aman" sampai dihijaukan; ini pekerjaan unit PK-01 dan unit yang disebut di sana.

## 7. Tindak lanjut

Setiap temuan dipegang tepat satu unit di `docs/blueprint/INDEKS_UNIT.md`:

| Temuan | Unit |
|---|---|
| PR-02, PR-13 | PR-T1 |
| PR-12, PR-14 | PR-T9 |
| KF-01, KF-02, KF-03 | KF-T1 |
| KP-17, MB-01, MB-02, PR-10, PR-15 | PK-47 |
| PR-01, PR-03 | PR-T2 |
| PR-04 | PR-T3 |
| PR-06 | PR-T4 |
| PR-07, PR-08 | PR-T5 |
| PR-09, temuan `PR-UX` | PR-T6 |
| PR-16 | PR-T7 |
| PR-11 | PR-T7 |
| KF-05, KF-06, KP-13, KP-29, KP-30 | KF-T2 |
| KF-04, KF-09, KF-10, KF-11, KP-11 | KF-T3 |
| KF-12, KF-13, temuan `KF-UX` | KF-T4 |
| KF-07 | KF-T5 |
| KP-05 (dan GL-06 dari audit keuangan) | KF-T6 |
| KP-27, KP-28 (dan CR-03) | KF-T7 |
| KF-08 | KF-T8 |
| KP-01, KP-02, KP-23 | KP-T1 |
| KP-10, KP-22, KP-24 | KP-T2 |
| KP-03, KP-04, KP-08 | KP-T3 |
| KP-06, KP-07, KP-25, KP-26, PR-05 | KP-T4 |
| KP-12, KP-35 | KP-T5 |
| KP-18, KP-19, KP-34 | KP-T6 |
| KP-09, KP-20, KP-21 | KP-T7 |
| KP-14, KP-15, KP-16, KP-31, KP-32 | KP-T8 |
| KP-33 | KP-T9 |
| KP-36 | PK-46 |

## 8. Menjalankan ulang bukti

Lihat `docs/blueprint/03_LINGKUNGAN_UJI.md` §3. Ringkasnya:

```bash
cd docs/audit/konfigurasi-peran-2026-11-13/bukti
python inv_endpoints.py /tmp/endpoints.json
python t1_config.py /tmp/t1.json
python t2_roles.py /tmp/t2_roles.json /tmp/endpoints.json && python t2_analyze.py /tmp
python t3_escalation.py && python t3b_eskalasi_akun.py
python t9_tulis_tanpa_izin.py /tmp/t9.json /tmp/endpoints.json && python t9_analyze.py /tmp/t9.json
python t10_setuju_tanpa_izin.py
python fe_be_routes.py /tmp/endpoints.json
```
