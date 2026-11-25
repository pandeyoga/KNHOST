# Audit Notifikasi — pemicu, penerima, jalur baca, dan pusat notifikasi

Tanggal: 25 Nov 2026 · Kode: `1ecbbed` · Data: basis data demo lokal (`test_database`, 105 notifikasi, 17 akun)
Lampiran: [A — inventaris 90 jenis pemicu](LAMPIRAN_A_INVENTARIS_PEMICU.md) ·
[B — matriks akun × jenis yang terlihat](LAMPIRAN_B_MATRIKS_AKUN.md) · tangkapan layar di `tangkapan/`

Penanda bukti: **[API]** dibuktikan lewat API pada data demo · **[KODE]** dibuktikan dari kode (berkas:baris) ·
**[SIM]** simulasi baca-saja · **[DUGAAN]** belum dibuktikan. Tidak ada berkas kode yang diubah oleh audit ini.

---

## 1. Ringkasan untuk pemilik

1. **Ada 90 jenis notifikasi** dari ±110 titik pemicu. Siaran "ke semua orang" sudah dibersihkan (0 jenis), tetapi
   **52 jenis masih dialamatkan ke nama peran** (38 satu dokumen per peran + 14 per orang berdasar peran), hanya **13
   jenis** yang dialamatkan lewat **izin** seperti standar proyek (`02_STANDAR.md` §3.1).
2. **Pemutus yang sebenarnya sering tidak diberi tahu.** Contoh paling jelas: lonceng **Finance** di data demo berisi 13
   pesan — 9 stok menipis, 1 pesanan, 3 giliran — dan **tidak satu pun urusan keuangan**. Kasus keuangan, draf denda,
   persetujuan PO/harga khusus, kontrabon telat, piutang/hutang jatuh tempo dialamatkan ke "manager".
3. **Beberapa pesan persetujuan tidak pernah sampai sama sekali** karena penyaring duplikat: permintaan internal
   antar-PT hanya sampai ke admin (Manajer dan Admin Sales terlewat), override harga tidak sampai ke Finance.
4. **Sembilan jenis menautkan ke layar yang tidak ada**; empat di antaranya (eskalasi tugas ambil gudang, klaim GRN,
   permintaan warna, saran aturan bank) karena itu **disembunyikan dari penerimanya** dan hanya terlihat admin.
5. **Ada kebocoran ke orang yang tidak berhak**: pesan opname yang ditujukan ke satu sales ikut tampil di 13 akun lain
   (berisi nomor pesanan + nama pelanggan); pengingat piutang H-3 dan status kiriman tersiar ke semua sales, padahal
   sales hanya boleh melihat pelanggannya sendiri.
6. **Lonceng desktop tidak memuat ulang sendiri.** Notifikasi baru (termasuk **sirine alarm gate MERAH**) baru muncul di
   desktop setelah pengguna melakukan sesuatu; hanya tampilan HP yang memeriksa tiap 60 detik.
7. **Sekitar 24 dari 44 antrean persetujuan tidak memberi tahu penyetujunya** saat dokumen masuk (cuti, lembur, gaji,
   uang muka, kontrabon, jurnal manual, transfer, opname, R&D, antar-PT, dll.), dan sebagian besar keputusan **tidak
   memberi tahu pengajunya**. Sopir dan desainer tidak punya satu pun pemicu.
8. **Pusat notifikasi hanya berupa panel lonceng kecil** (20 pesan per muat): tanpa halaman penuh, tanpa pengelompokan
   di desktop, tanpa preferensi pengguna, tanpa arsip; label jenis hanya ada untuk ±30 dari 90 jenis.

---

## 2. Cara kerjanya sekarang

```
PEMICU (aksi pengguna di endpoint / job penjadwal)
  ├─ create_notification(recipient_role=… | recipient_user=…)     services/notification_service.py:65
  │     bawaan recipient_role="all"; penyaring duplikat unread/day/ever (baris 18-22, 90-101)
  ├─ create_addressed(permission | roles | division | also_users)   services/notification_service.py:25
  │     → penerima dari matriks izin + pagar PT, SATU dokumen per orang       services/notification_audience.py
  └─ reminder_policy.notify (pengingat terjadwal, penerima bisa diatur per PT) services/reminder_policy.py
          ▼
  koleksi notifications (tidak pernah dihapus)
          ├─► WhatsApp  wa_alert_service (≥ warning; peran persis; tanpa pagar PT)   — belum aktif di demo
          ├─► Web Push  web_push_service (HP berlangganan)                          — belum aktif di demo
          └─► BACA  GET /api/notifications · /unread-count · POST /{id}/read · /read-all
                 penyaring = (peran ∈ audiens ∨ untuk saya) ∧ (tautan boleh dibuka) ∧ PT     services/notification_scope.py
                 status baca per orang (read_by)                                     services/notification_read.py
                 ▼
     Lonceng desktop (20 per halaman, dimuat ulang hanya saat ada aksi)   components/NotificationCenter.jsx
     Lonceng HP (dimuat ulang tiap 60 detik + saat push masuk)            features/sales/mobile/MobileNotifSheet.jsx
```

Penjadwal (`services/scheduler_service.py`): pindai kejadian tiap 4 jam (stok menipis, reservasi, pesanan menunggu),
eskalasi tiap 2 jam (belum dibaca > 8 jam → atasan), giliran tiap 5 menit, pengingat antrean persetujuan harian 07.00
WIB (ke "manager"). Pengaturan: 19 kunci `notif.*` di Pusat Pengaturan (penerima pengingat, rantai eskalasi, peran
penerima WA, nomor PIC). **Tidak ada preferensi per pengguna.**

## 3. Siapa melihat apa (data demo)

Diambil lewat API yang sama dengan lonceng, per akun (rincian per jenis di Lampiran B):

| Akun (peran) | Lencana | Isi lonceng |
|---|---|---|
| admin | 21 (26 bila semua PT) | stok menipis 9, kasus keuangan 3, amandemen 4, denda 3, PO 3, restock 3, pesanan 1, pendingan 1, antar-PT 1 |
| manajer (3 akun) | 23 (26) | sama dengan admin tanpa PO PT Kanda & antar-PT, + giliran 3 |
| **finance** | 13 | stok menipis 9, pesanan 1, giliran 3 — **nol urusan keuangan** |
| gudang (2 akun) | 11 / 10 | giliran 10 (+ 1 SPK inspeksi) |
| admin sales | 1 (2) | giliran 2, antar-PT Kanda 1 |
| sales (4 akun), desainer, sopir, MD, admin gudang, admin sample | 0 | — |

Yang sudah benar: sopir/desainer/sales tidak melihat persetujuan PO maupun stok; akun satu PT ditolak (403) untuk PT
lain; status baca per orang bekerja; orang lain tidak bisa menandai notifikasi milik orang lain (404). [API]

---

## 4. Temuan

### KRITIS

**N-01. Penyaring duplikat membuang penerima kedua dan ketiga** [KODE]
Pemicu yang mengirim ke beberapa peran dalam satu putaran memakai jenis + `ref` yang sama dengan penyaring bawaan
"belum dibaca"; dokumen pertama membuat kiriman berikutnya dilewati (`notification_service.py:18`).
* `internal_request_submitted` (`internal_request_service.py:257-265`): loop admin → manager → sales_admin → **hanya
  admin menerima**; Admin Sales, pemilik antreannya, tidak pernah diberi tahu.
* Override harga (`amendment_service.py:724-725`, loop manager → admin → finance): **Finance tidak pernah menerima**.
* Klaim makloon (`makloon_claim_service.py:85-95, 139-147`): hanya peran pertama dari Aturan Persetujuan.

**N-02. Tautan bukan id layar → pesan tersembunyi dari penerimanya, atau membuka layar kosong** [KODE]
Penyaring baca hanya meloloskan pesan yang tautannya layar yang boleh dibuka penerima (`notification_scope.py:50-56`).
Tautan yang bukan id layar tidak pernah cocok:
* `outbound_escalation` (`routers/outbound_picking.py:357`, tautan `outbound` — tidak ada layar itu), `grn_claim`,
  `color_use_request`, `bank_rule_suggested` → **hanya admin yang melihat**. Contoh: gudang mengeskalasi tugas ambil,
  Manajer dan Admin Gudang tidak menerima apa pun.
* Lima jenis lain membuka layar kosong saat diklik (`ocr_budget`, `color_use_decided`, `interco_price_request`,
  `ai_followup`, `interco_receipt_auto_fulfilled`).

### TINGGI

**N-03. Alamat "manager" melewatkan pemutus yang sebenarnya — terutama Finance** [API + KODE]
19 titik menulis `recipient_role="manager"` langsung di kode. Finance memegang izin `finance_case.resolve`,
`penalty.waive`, `contra_bon.approve`, `price_approval.approve`, `purchase_order.approve`, tetapi tidak menerima:
`finance_case` (kasus baru), `penalty_draft`, `contra_bon_overdue`, `price_approval_pending`, `po_approval`, serta
pengingat `ar_overdue`, `ap_due`, `depreciation_due`, `budget_alert` (bawaan `reminder_policy.py:56-62`).
`approval_backlog` harian mengirim **satu** ringkasan 44 antrean (termasuk cuti, gaji, jurnal) hanya ke manager.
`rnd_sla_overdue` ke manager, bukan MD; `production_stalled`/`ops_stalled` ke gudang tanpa Admin Gudang.

**N-04. Kebocoran ke orang yang tidak berhak** [KODE + SIM]
* Pesan opname yang memangkas reservasi (`notification_service.py:465-484`) hanya mengisi `recipient_user`;
  `recipient_role` jatuh ke bawaan `"all"`, sehingga penyaring OR menjadikannya siaran: dokumen untuk satu sales lolos ke
  **13 akun** (sales lain, gudang, finance, MD) — berisi nomor pesanan dan nama pelanggan.
* `ar_due_soon` salinan tim (`alert_ops_service.py:330`) memakai izin `ar_receipt.create` yang **dipegang sales**: setiap
  sales menerima piutang H-3/H/H+1 pelanggan rekannya.
* `logistics_delivered` / `logistics_failed` (`logistics_service.py:736`, peran sales & sales_admin): semua sales
  menerima status kiriman pelanggan orang lain.

**N-05. Pagar PT tidak seragam (empat aturan berbeda)** [API + KODE]
Lonceng: peran lintas-PT membaca semua PT; kiriman per orang: daftar PT tersimpan di akun; push: daftar tersimpan; WA:
tanpa pagar. Contoh demo: manager.printing (ditugaskan KSC + Printing) **melihat 3 notifikasi PT Kanda**, tetapi tidak
termasuk penerima kiriman per orang PT Kanda. Enam jenis tanpa `entity_id` padahal dokumennya ber-PT (mis. `ar_overdue`:
umur piutang semua PT ke semua manajer).

**N-06. Lonceng desktop tidak memuat ulang sendiri** [KODE]
Hanya HP yang memeriksa tiap 60 detik (`features/mobile/MobileShell.jsx:33-46`). Desktop memuat ulang saat login, ganti
PT, atau sesudah aksi (`hooks/useAppActions.js:756-802`). Sirine alarm gate MERAH dibunyikan dari pemuatan lonceng
(`utils/sirenAlarm.js:49`), jadi **di desktop sirine tidak berbunyi sampai pengguna melakukan sesuatu** (kecuali layar
Monitor Gate sedang terbuka).

**N-07. Alarm berulang hanya berbunyi sekali seumur hidup** [KODE]
Siaran ke peran menyimpan status baca di `read_by`, sehingga `read` global tidak pernah benar dan penyaring "belum
dibaca" bekerja seperti "pernah": printer macet kedua kali di gudang yang sama (`printer_stuck_watch.py:62`), gangguan
reader RFID kedua (`rfid_v2_health.py:86`) tidak memberi tahu lagi.

### SEDANG

* **N-08. Notifikasi "menunggu keputusan" tetap menyala sesudah diputus** [API + KODE] — hanya PO, amandemen, makloon,
  giliran, dan tagihan kampanye yang ditutup. `finance_case`, `price_approval_pending`, `special_order_approval`,
  `order_approval`, `restock_request`, `credit_override_requested`, dll. tidak. Demo: KSC/CASE-00002 sudah selesai tetapi
  notifikasinya masih belum dibaca dan akan dieskalasi ke admin.
* **N-09. Tombol "Setujui" di lonceng memakai pangkat peran** (`NotificationCenter.jsx:8-13`, `{sales:1, warehouse:1,
  manager:2, admin:3}`), server memakai izin + Aturan Persetujuan. Finance dan semua peran kustom tidak pernah melihat
  tombolnya. Server tetap aman.
* **N-10. Peran kustom**: menerima siaran peran hanya bila berdasar peran bawaan (`notify_like`); peran kustom tanpa acuan
  dengan izin identik Manajer menerima **0**. WA dan kiriman `roles=…` memakai nama peran persis.
* **N-11. Penerima ditetapkan sekali saat notifikasi lahir** — orang baru atau perubahan izin tidak mewarisi pesan yang
  masih tertunda (demo: Admin Gudang, MD, Admin Sample dibuat 1 detik sesudahnya → 0 notifikasi, padahal 10 giliran
  menyebut Admin Gudang). Giliran (`turn`) juga bisa tertutup sebelum tahapnya benar-benar selesai
  (`turn_notification_service.py:157-159`).
* **N-12. Kebisingan & penerima salah sasaran** — `low_stock` memakai izin `purchase_order.create`: 9 produk × 5 orang =
  45 baris per putaran ke admin, finance, manajer; **MD dan Admin Gudang (pembuat PR) tidak menerima**. Kartu eskalasi
  menyebut nama penerima pertama saja ("belum ditindak oleh Hendra Wijaya (Finance)") walau diterima 5 orang.
* **N-13. Notifikasi yatim** — `po_arrival`, `backorder_ready`, `ar_due_soon` dengan pemilik kosong hanya terlihat admin;
  `backorder_ready` KANDA/SO-00001 dikirim ke sales yang tidak bertugas di PT Kanda (tidak pernah terlihat), pembuat
  pesanannya tidak menerima apa-apa.

### RENDAH

* N-14. Konteks PT bawaan menyembunyikan notifikasi non-kritis PT lain bagi pengguna multi-PT (admin 21 vs 26).
* N-15. WA tanpa persetujuan pengguna: ringkasan dikirim ke semua pengguna aktif yang bernomor (termasuk sopir,
  desainer); WA selalu menambahkan admin; audiens WA ≠ audiens lonceng.
* N-16. Langganan push di HP bersama hanya dilepas lewat menu keluar HP; keluar dari tampilan desktop atau sesi
  kedaluwarsa membiarkan perangkat menerima push pengguna lama. [DUGAAN]
* N-17. **`titipan_pesanan_batal_gagal` memakai tingkat `"danger"`** yang tidak dikenal (`ar_receipt_service.py:416`) —
  dianggap "info" oleh eskalasi dan WA. *Ini kesalahan perbaikan 25 Nov (`a30efa0`); seharusnya `"critical"`.*
* N-18. `design_ai_comment` ke semua desainer, bukan pemilik desain; alias tautan `finance` berbeda backend/frontend;
  `od_cancel_credit_note` menaut ke `orders`, bukan Meja Finance; `period_unlock_reclosed` hanya ke admin.

---

## 5. Pemicu yang belum ada

**Penyetuju tidak diberi tahu saat dokumen masuk antrean** (hanya tertangkap ringkasan harian ke manager):
uang muka & pertanggungjawabannya; **seluruh SDM** (cuti, lembur, gaji, lembar insentif); biaya masuk, usulan jurnal,
tagihan pemasok non-kampanye, buka periode, selisih bayar; kontrabon (verifikasi, persetujuan, sengketa); transfer
gudang, opname, barang ditahan inspeksi; spesifikasi & sample R&D, permintaan desain; transaksi & retur antar-PT; susut
makloon, pengecualian retur, verifikasi pesanan, PR.

**Pengaju tidak diberi tahu keputusannya**: harga khusus, PO custom, amandemen, kasus keuangan, PR, cuti, lembur, uang
muka, buka periode, tagihan pemasok, transfer.

**Peran tanpa satu pun pemicu**: sopir (tugas kirim), desainer (permintaan desain masuk/ditugaskan).

---

## 6. Pusat notifikasi — UI/UX

Dinilai dari kode (`components/NotificationCenter.jsx`, `features/sales/mobile/MobileNotifSheet.jsx`,
`hooks/useAppActions.js`) dan tangkapan layar per akun (§6.1).

| # | Temuan | Dampak bagi pengguna |
|---|---|---|
| U-01 | Hanya panel lonceng; **tidak ada halaman Pusat Notifikasi** (riwayat, cari, arsip) | Pesan lama sulit dicari; tidak ada tempat kerja untuk "yang perlu saya tindak" |
| U-02 | Desktop tidak memuat ulang sendiri (N-06) | Lencana dan isi basi; alarm gate tidak berbunyi |
| U-03 | Saring jenis/tingkat hanya atas 20 pesan yang sudah dimuat; jumlah per jenis ikut terpotong | "Stok menipis (9)" padahal di server lebih banyak; filter terlihat bohong |
| U-04 | Label jenis hanya ±30 dari 90; sisanya kode mentah ("penalty draft", "finance case") | Bahasa campur, tidak dimengerti |
| U-05 | Desktop tidak mengelompokkan (hari ini/kemarin, perlu tindakan vs info); HP mengelompokkan → **dua tampilan berbeda perilaku** | Pesan penting tenggelam di antara 45 stok menipis |
| U-06 | Pita alamat menampilkan **nama peran** ("Manajer"/"Umum") | Setelah pengalamatan pindah ke izin, pita ini menyesatkan |
| U-07 | Aksi langsung hanya untuk PO & tagihan kampanye, dan memakai pangkat peran (N-09) | Persetujuan lain harus pindah layar; Finance tak pernah melihat tombol |
| U-08 | Klik = tandai dibaca + pindah layar; tidak ada "tandai belum dibaca", arsip, hapus; pesan tidak pernah dihapus | Kotak menumpuk; tak bisa menyimpan pengingat |
| U-09 | "Semua" (tandai semua dibaca) tanpa konfirmasi, termasuk yang belum dimuat | Pesan penting hilang dari lencana tanpa pernah dilihat |
| U-10 | Tombol "Sirine" di kepala panel untuk semua peran | Kekacauan visual bagi peran non-gudang |
| U-11 | Gagal memuat diperlakukan sebagai kosong → "Tidak ada notifikasi. Sistem dalam kondisi baik." (`useAppActions.js:196`) | Pesan menenangkan palsu saat server bermasalah |
| U-12 | Butir berperan tombol tanpa penanganan Enter/Spasi; tombol bersarang di dalam tombol | Tidak bisa dipakai papan ketik / pembaca layar |
| U-13 | Waktu hanya relatif ("3 hari lalu") | Sulit mencocokkan dengan dokumen/audit |
| U-14 | Tidak ada preferensi pengguna (bisukan jenis non-kritis, kanal WA) | Tidak bisa mengurangi kebisingan sendiri |
| U-15 | Dua tempat "perlu tindakan" dengan angka berbeda: kartu **Menunggu Persetujuan Saya** di beranda Manajer (22, dari antrean persetujuan) dan lencana lonceng (23, dari notifikasi) | Pengguna tidak tahu mana yang harus dikerjakan; angka tidak pernah cocok |
| U-16 | Panel sempit (±360 px); kepala berisi Sirine/Scan/Semua; area saring memakan ±¼ tinggi → hanya ±4 pesan terlihat pada layar 1440×900 | Harus menggulir untuk hal penting |
| U-17 | Teks hitungan membingungkan: "Menampilkan 20 dari 20 notifikasi (dari 23 total)" | Tidak jelas apakah ada yang tersembunyi |

### 6.1 Tangkapan layar

Diambil 25 Nov dari aplikasi lokal dengan data demo (1440×900, skala 2; HP = iPhone 13), folder `tangkapan/`:

| Berkas | Akun | Lencana | Yang terlihat |
|---|---|---|---|
| `panel_admin.png` | admin | 21 | tiga **kasus keuangan berlabel "MANAJER"**, usulan denda; jenis tampil "finance case" (kode mentah) |
| `panel_finance.png` | finance | 13 | giliran cocokkan tagihan PO, pesanan menunggu persetujuan — **tidak ada kasus keuangan** |
| `panel_manager.png`, `desktop_manager.png` | manajer | 23 | giliran retur, kasus keuangan; di belakangnya kartu "Menunggu Persetujuan Saya" berangka 22 (U-15) |
| `panel_warehouse.png` | gudang | 11 | giliran "PO disetujui — siapkan penerimaan barang" |
| `panel_sales.png` | sales | 0 | satu giliran lama yang sudah selesai |
| `hp_sales_notif.png` | sales (HP) | 0 | lembar bawah: saring, ajakan pasang aplikasi untuk push, satu giliran |

MD dan sopir: lonceng kosong (tanpa pemicu untuk perannya).

---

## 7. Arah perbaikan (usulan, urut prioritas)

1. **Satu pintu pengalamatan berbasis izin + PT dokumen.** Semua pemicu lewat `create_addressed(permission=…)` atau
   aturan persetujuan (`approval_policy_service.who_can_decide`), satu dokumen per orang. Bawaan `recipient_role="all"`
   dicabut (gagal tertutup). Penyaring duplikat dihitung per penerima. Menutup N-01, N-03, N-04, N-05, N-10, N-12.
2. **Katalog jenis notifikasi** (seperti `approval_kinds.py`): jenis → label, izin penindak, layar tujuan, tingkat,
   apakah aksi. Penjaga statik memeriksa tautan = layar nyata dan penerima memegang izin layar itu. Label layar dibaca dari
   katalog. Menutup N-02, U-04, N-17/N-18.
3. **Setiap antrean persetujuan: beri tahu saat masuk, tutup saat diputus, beri tahu pengaju.** Satu helper dipakai semua
   antrean di `approval_backlog_service.QUEUES`. Menutup §5 dan N-08.
4. **Lonceng desktop memuat ulang sendiri** (tiap 60 detik saat terlihat, sama dengan HP) dan sirine ikut. Menutup N-06.
5. **Halaman Pusat Notifikasi**: tab "Perlu tindakan" vs "Info", dikelompokkan per hari, saring/cari di server, arsip,
   tandai belum dibaca, preferensi per pengguna (bisukan jenis non-kritis; WA dengan persetujuan), retensi pesan lama.
   Satu komponen untuk desktop dan HP. Menutup U-01…U-14.
6. **Penerima dihitung ulang saat dibaca untuk pesan yang masih menunggu** (atau kirim ulang saat izin berubah), dan
   satu aturan pagar PT untuk lonceng, push, dan WA. Menutup N-05, N-11.

## 8. Dampak ke rencana tutup sisa & persetujuan pembatalan (`docs/superpowers/plans/2026-11-25-batal-tutup-sisa-pesanan.md`)

Rencana itu sudah memakai pengalamatan izin (`create_addressed(permission=("order","approve_cancel"))`) dan memberi tahu
pengaju. Tiga penyesuaian supaya tidak mengulang temuan di atas:
1. Tutup notifikasi "permintaan batal" saat diputus/ditarik/void (`resolve_action`) — N-08.
2. Pastikan tautan `approval-inbox` termasuk layar yang boleh dibuka pemegang `order.approve_cancel`, terutama Finance
   (penyaring relevansi) — N-02; uji: Finance benar-benar melihat notifikasinya lewat `GET /api/notifications`.
3. Tambahkan label jenis baru di lonceng (desktop & HP) — U-04; tingkat memakai nilai yang dikenal (`warning`/`critical`).

## 9. Batas audit

* WA dan push tidak aktif di lingkungan uji (tanpa pengaturan WA, tanpa kunci VAPID, 0 langganan): audiensnya dari kode.
* Sebagian besar pengingat terjadwal belum pernah berjalan di data demo; penerimanya dari kode dan pengaturan bawaan.
* Kepatutan izin bawaan (mis. Finance memegang `purchase_order.create` sehingga menerima stok menipis) adalah keputusan
  pemilik, bukan cacat jalur notifikasi.
* Efek samping uji: 22 baris log masuk dan `last_login_at` 17 akun demo berubah; satu tanda baca uji sudah dikembalikan.
