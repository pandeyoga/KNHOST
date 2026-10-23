# Analisis Temuan & Rencana Perbaikan — Permintaan Pemilik 23 Okt 2026

> Status dokumen: **ANALISIS SAJA — belum ada kode yang diubah untuk temuan di sini.**
> * Basis kode: `main` @ `f6d5aaa`.
> * Data acuan: DB UAT `kn_uat_23okt` (port 8062/3062).
> * Setiap klaim memakai bukti `berkas:baris`, fungsi, atau data UAT yang dicek langsung, bukan ingatan. Klaim penting
>   dari penelusuran paralel dicek ulang di kode sebelum ditulis.
> * Penanda **Riwayat** pada temuan berarti hal itu **pernah diminta**, tetapi masih salah atau belum ada (indikasi
>   konteks hilang).

## 0. Cara membaca & aturan anti-konteks-hilang

1. Satu temuan = satu ID (`P1`…`P17`, sub-butir `P4.3` dst.). ID ini dipakai di commit, catatan J-berikutnya, dan
   nama uji otomatis (`test_uat23_p4_*` / `p4*.test.js`) supaya jejaknya bisa dicari.
2. Setiap ID punya **Kriteria terima** yang bisa diuji. Temuan boleh ditulis "selesai" hanya bila:
   * (a) uji otomatis untuk kriteria itu hijau;
   * (b) sudah dicek di UI UAT dengan akun peran yang relevan;
   * (c) buktinya (perintah uji + tangkapan layar/teks) ditulis di `hasil/`.
3. Keputusan pemilik yang masih terbuka ditandai **[KEPUTUSAN]** (daftar lengkap di §4) dan tidak diimplementasikan
   dengan tebakan.
4. Bila implementasi menyimpang dari rencana ini, rencana diperbarui dulu, bukan diam-diam.

---

## 1. Ringkasan

| ID | Topik | Keadaan sekarang | Akar masalah utama | Prio |
|---|---|---|---|---|
| P1 | Produk eksklusif & galeri desain | Ada 3 mekanisme eksklusif terpisah (per sales, per pelanggan di SKU, per pelanggan di warna). Galeri desain **tanpa** pemilik/label; rantai desain ↔ SKU putus (0 produk ber-`design_id`). Riwayat: J8 (18 Agt) "BELUM" | Eksklusivitas ditempel di SKU, bukan di desain; tidak ada model kepemilikan desain | Tinggi |
| P2 | Harga OD & nego | Harga = biaya kontrak × margin. Sales boleh kunci harga dengan margin bebas. Kunci langsung memicu PR/PO. Biaya/margin terlihat sales. **Riwayat: SO-12 (15 Okt) harga = Grade A induk — tidak pernah diterapkan** | Arah pemilik hilang di pemetaan; kunci harga = pengadaan | Tinggi |
| P3 | Surat perintah kerja R&D ke supplier | Tidak ada dokumen cetak sampel. Berkas final desain tidak wajib PNG siap cetak. Pantone tidak wajib | Dokumen keluar R&D tidak dimodelkan | Sedang |
| P4 | R&D uji ulang vs produk baru | Satu form untuk semua tujuan. Labdip 1 warna. Warna wajib dari Pustaka. Supplier uji ulang = semua supplier. **Bug pemilih kain dasar (terbukti, layar galat)** | Model per jenis uji, bukan per tujuan; arah data warna terbalik | Tinggi |
| P5 | Galat "Kombinasi ini sudah memiliki SKU…" | Form hanya menawarkan nilai sumbu yang SUDAH ada; keenam warna LINEN OAT sudah SKU produksi → buntu | Varian baru tidak bisa lahir dari R&D; pesan tanpa jalan keluar | Tinggi |
| P6 | Desain/pattern/kategori di master produk | `design_id` hanya dari spesifikasi R&D. Tidak tampil di form, POS, maupun Export | Relasi desain → produk tidak dipakai di luar R&D | Sedang |
| P7 | Menu Perbaikan (repair & celup ulang) | Tidak ada. Hanya "Rework Lot" tanpa biaya/dokumen kirim | Belum pernah dibangun | Sedang |
| P8 | POS sadar lokasi + pelanggan wajib | Pilih pelanggan **opsional**, daftar dari dasbor (batas 100, tidak sesuai sales). Tidak ada pilihan lokasi; stok = total global | "Pilih pelanggan" dibuat opsional, bukan gerbang; lokasi tidak disambung ke penjualan | Tinggi |
| P9 | Model lokasi (site → gudang ber-peran), PO ke lokasi | PO ke gudang (termasuk nonaktif). Peran transit tidak dipakai logika mana pun. Gudang GRN diabaikan. Putaway manual & lintas lokasi. Alokasi berdasar kota pelanggan. "FEFO" = FIFO. Bug gudang bawaan reorder | Model lokasi sudah jadi data, tetapi tidak disambung ke alur | Tinggi |
| P10 | Transfer antar-PT sadar gudang bersama | Gudang bersama sudah "ganti pemilik" (tanpa kirim). Gudang dedicated tidak punya jalur kirim fisik. Roll pilihan hilang (`preferred_roll_ids`). Sumber = tujuan | Keputusan "ganti pemilik vs kirim" tidak dibuat per roll | Sedang |
| P11 | Penanda roll MDQ / 4-point + sampling | Tidak ada flag datar di roll. SPK 4-point **wajib semua roll**. SPK MD boleh sebagian, tetapi roll yang tidak dicek lolos tanpa tanda | Status pemeriksaan tersebar; sampling tidak dimodelkan | Tinggi |
| P12 | Sorotan POS bisa dinyalakan/dimatikan | Terlaris dari seluruh riwayat, tanpa saring visibilitas. Tidak ada produk unggulan/push. Tidak ada pengaturan | Belum dibangun | Rendah |
| P13 | Keep & Pending untuk sales (SO miliknya) | **Sudah ada** di Beranda Sales desktop & HP, dibatasi SO milik sales | Perlu bukti UI & komunikasi, bukan kode baru | Rendah |
| P14 | Sales hanya melihat pelanggannya | Pemilih pelanggan untuk pesanan (`for_order`) mengembalikan **semua** pelanggan PT | Pengecualian `b9135ff` menambal data pelanggan tanpa sales | Tinggi |
| P15 | Gabung beberapa PR → 1 PO + rekomendasi | 1 PR → 1 PO saja. OD multi-item → N PO. Bug `kind`/`type` | Tautan PO↔PR skalar; fitur belum ada | Sedang |
| P16 | UI GRN, Pusat/Jejak Dokumen, Pengaturan | GRN tanpa kartu & grid HP rusak. Jejak tanpa unduh per dokumen. **Bug PDF GRN baca koleksi PO**. Pengaturan 20 tab, 4 lapis, konsep dobel, label seksi dobel | Layar tanpa wadah design-system; registry PDF tertinggal | Sedang |
| P17 | Pratinjau foto tanpa unduh | Tidak ada komponen bersama. Lampiran retur `attachment` (selalu unduh). 10 titik tanpa pratinjau. Token di URL `?auth=` | Header entitas + `Content-Disposition` | Sedang |

---

## 2. Pola akar masalah lintas temuan (kenapa "sudah disebut tetapi masih salah")

Penelusuran riwayat (memo 7 Okt, Daftar Perbaikan 11 Okt IMP-xx, register 126 pernyataan 15 Okt, `ANALISIS_FLOW_DIVISI`
18 Agt, catatan trial 22 Okt) menunjukkan lima pola:

| Pola | Contoh terbukti | Akibat |
|---|---|---|
| **A. Keputusan pemilik hilang di pemetaan** register → paket kerja (LN/IMP) | SO-12 harga OD = harga Grade A induk (P2); J8 desain → item eksklusif (P1) | Fitur dibangun dengan rumus/arah lama |
| **B. Aturan dilonggarkan untuk menambal data** | `for_order` membuka semua pelanggan karena data UAT punya pelanggan tanpa sales (P14, commit `b9135ff`) | Aturan pemilik bocor tanpa keputusan |
| **C. Data/model dibuat, tetapi tidak disambungkan ke alur** | Lokasi & peran gudang (P9), `design_id` produk (P1/P6), `preferred_roll_ids` interco (P10), skema `roll_ids` SPK 4-point (P11) | Fitur "ada" di DB/skema, tidak terasa di layar |
| **D. "Selesai" diklaim tanpa uji di UI dengan akun peran** | Semua IMP/LN masih `implemented_pending_validation`; tracker L "Requirement tervalidasi 0/56" | Pemilik menemukan sendiri saat UAT |
| **E. Regresi tanda tangan komponen** | `BaseFabricPicker` → `onChange(tpl)` vs `SampleSpecFields (id, name)` (P4.8) | Form galat tanpa terdeteksi uji |

**Pencegahan (berlaku untuk seluruh implementasi rencana ini):**
1. Setiap ID P-x dikaitkan ke sumber permintaan (memo/register/catatan) di kepala bagiannya. Keputusan [KEPUTUSAN]
   yang dijawab pemilik dicatat **verbatim** di §4 dokumen ini, dan register tidak lagi menjadi satu-satunya sumber.
2. Tidak ada pelonggaran aturan untuk menambal data. Data yang salah diperbaiki dengan skrip data + antrean "perlu
   ditetapkan".
3. Definisi selesai = uji otomatis + **cek UI dengan akun peran** + bukti di `hasil/`. Status tertinggi implementer
   tetap `implemented_pending_review`.
4. Komponen bersama yang diubah tanda tangannya: grep semua pemakainya dan tambah uji Jest per pemakai.

---

## 3. Urutan fase & ketergantungan

| Fase | Isi | Kenapa urutan ini | Bergantung pada |
|---|---|---|---|
| **F0 — cepat & pasti** | P4.8 bug kain dasar · P14 (hapus `for_order` + antrean pelanggan tanpa sales + data UAT) · P13 bukti UI · P15 bug `kind/type` · `restock_service._default_warehouse` · gudang nonaktif tidak bisa dipilih | Bug nyata & aturan pemilik yang bocor; risiko kecil | [KEPUTUSAN] P14-K1/K2 |
| **F1 — lokasi** | P9.1–P9.3 (data lokasi/peran, PO ke lokasi, GRN) · P8 (pilih lokasi + pelanggan wajib di POS) · P9.5 lingkup lokasi | Fondasi untuk P8/P9.4/P10/P15 | P9-K1..K4, P8-K* |
| **F2 — alur barang** | P9.4 routing otomatis cross-dock/putaway · P9.6 alokasi lokasi+FIFO · P10 transfer antar-PT · P11 penanda roll & sampling | Memakai lokasi F1 | F1 |
| **F3 — R&D & desain** | P4 (dua pintu, rantai tahap, labdip multi-warna, Pustaka = keluaran) · P5 · P3 (surat perintah, PNG, Pantone) · P1 (kepemilikan desain, klaim) · P6 (desain di produk, POS, export) | Satu rantai data desain → warna → SKU | P1-K*, P4-K*; P6 bergantung P1.2 |
| **F4 — komersial** | P2 (SO-12 + nego + pisah kunci/pengadaan) · P15 gabung PR→PO | P15 memakai lokasi tujuan F1; P2 memakai rantai OD | P2-K*, F1 |
| **F5 — layar** | P16 (GRN CSS, unduh dokumen, Pengaturan) · P17 pratinjau foto · P12 sorotan POS · P7 menu Perbaikan | Bisa paralel sesudah F0; P7 memakai lokasi F1 & roll flag F2 | P7-K*, P12-K* |

Setiap fase:
* ditutup dengan uji backend (pytest di `kn-uji-backend`), Jest, cek UI di UAT (akun peran), dan laporan
  `hasil/<FASE>.md`;
* setelah itu baris tracker diperbarui (`implemented_pending_review`) dan di-push.

---

## 4. Daftar keputusan pemilik yang dibutuhkan

| ID | Pertanyaan | Usulan bawaan |
|---|---|---|
| P1-K1 | Siapa memutus klaim desain; pembeli lama boleh repeat? | Manajer; pembeli lama boleh repeat sampai stok habis |
| P1-K2 | Arti HOLD | Tetap "ditahan dari proofing" + penanda "Belum diproduksi" |
| P1-K3 | Desain OD jadi customer label sejak kapan | Sejak OD disetujui |
| P2-K1 | Sales boleh kunci harga OD? | Tidak — Admin Sales |
| P2-K2 | Ambang nego otomatis disetujui? | Tidak ada (semua ke Manajer) |
| P2-K3 | Lantai nego | Harga kontrak |
| P2-K4 | SO-12: Grade A induk apa adanya / + biaya custom; bila di bawah biaya? | Grade A induk; peringatan rugi ke Manajer |
| P4-K1 | Uji ulang tanpa kontrak boleh pakai supplier "pernah PO"? | Boleh, dengan label |
| P4-K2 | Batas warna per labdip; warna ACC langsung jadi SKU? | 10; SKU lahir saat spesifikasi per warna di-ACC |
| P7-K1 | Biaya perbaikan dikapitalisasi / dibebankan | Dikapitalisasi |
| P7-K2 | Celup ulang boleh ganti SKU? | Boleh (roll anak SKU baru) |
| P9-K1 | Soreang/Jakarta: gudang transit terpisah? | Gudang tunggal merangkap transit+storage |
| P9-K2 | Area inspeksi terpisah? | Tidak — status di transit |
| P9-K3 | Luruskan stage roll lama | Ya, otomatis |
| P9-K4 | Stok lokasi lain: otomatis transfer / Admin Sales memutus | Admin Sales memutus |
| P8-K1 | Wajib pelanggan + lokasi untuk semua peran POS atau hanya sales | Semua peran yang membuat pesanan |
| P8-K2 | Satuan lokasi = site (bukan gudang) | Site |
| P12-K1 | Arti "rekomendasi" | (b) per pelanggan dari desain/kategori yang pernah dibeli |
| P14-K1 | 3 pelanggan KSC tanpa sales ditetapkan ke siapa | (pemilik) |
| P14-K2 | Pelanggan "Umum/Walk-in" untuk semua sales? | Ya, satu per PT |
| P16-K1 | Setujui susunan baru menu Pengaturan (7 kelompok) | Disajikan dulu sebagai mock |

---

## 5. Rincian per temuan

## P1 — Produk eksklusif & galeri desain

### Permintaan pemilik
1. Jelaskan mekanisme produk eksklusif pelanggan saat ini.
2. Galeri desain berisi **desain internal** dan **desain eksklusif pelanggan**. Desain eksklusif datang dari pesanan
   khusus (OD) dan **tidak boleh dijual ke pelanggan lain**.
3. Pesanan khusus bisa **memakai desain KN yang sudah ada** tetapi belum diproduksi / di-hold.
4. Daftar label desain beserta definisinya.
5. Pelanggan bisa **mengklaim** desain menjadi miliknya (*customer label*) vs **white label** (bebas dijual).
   Keputusan manual oleh manajemen, tetapi sistem menyediakan data: siapa saja pembeli desain itu, berapa kali order,
   berapa qty.
6. Galeri menampilkan info desain, filter milik pelanggan / bukan, dan label white/customer.

### Mekanisme sekarang (bukti)
Ada **tiga** mekanisme eksklusif yang berdiri sendiri-sendiri. **Tidak satu pun berada di tingkat desain.**

| # | Mekanisme | Field | Di-set oleh | Ditegakkan di | Catatan |
|---|---|---|---|---|---|
| a | Eksklusif per **sales** (PS-20 "PO sendiri") | `products.exclusivity = "sales_tertentu"` + `owner_sales_ids` | Master produk / induk (`rnd_spec_service.approve_spec` mewarisi dari induk) | `services/product_exclusivity.py` (filter daftar untuk peran sales) + `routers/sales_orders.py:200` `pexcl.assert_can_order` | Membatasi **sales**, bukan pelanggan |
| b | Eksklusif per **pelanggan** hasil OD | `products.exclusive_customer_id/name`, `catalog_scope="customer"`, `special_order_id/number` | `special_order_link.ensure_exclusive` (dipanggil `link_for_spec` saat spesifikasi OD di-ACC, `repair_pr_lines`, `routers/special_orders.py:1122`); `rnd_spec_service._product_draft` membawa `spec.exclusive_customer_id` | **Hanya** saat SO disimpan: `routers/sales_orders.py:203` → `special_order_phase2.assert_customer_allowed` (`special_order_phase2.py:758`, galat 400 "EKSKLUSIF untuk pelanggan …") | POS **tetap menampilkan** SKU itu ke semua pelanggan, hanya diberi lencana "Eksklusif: …" (`features/pos/PosProductCard.jsx:31,87`). Penolakan baru terjadi di akhir checkout |
| c | **Warna** milik pelanggan | `color_library.exclusive_customer_id` | Manual (admin/manager, `routers/color_library.py:167`) atau otomatis saat labdip OD diputus (`rnd_sample_service.py:1325` → `color_lock_service.auto_mark_owner`) | `color_lock_service.assert_can_use` saat spesifikasi/varian memakai warna itu | Ada alur "permintaan pakai" (`use_requests`) |

**Galeri desain** (`design_gallery`; `services/design_gallery_service.py`, `services/design_studio_service.py`):
* Tidak ada field pemilik pelanggan. Yang ada: `origin` (`internal` / `special_order` / `redesign` —
  `design_studio_service.py:50` `ORIGIN_LABEL`), `status` (`STATUS_LABEL`, baris 27), `on_hold`
  (`set_hold`, baris 489: "selama hold, desain tidak bisa dipakai proofing R&D / diaktifkan").
* Desain asal OD hanya tertaut **tidak langsung**: `design_gallery.request_id` → `design_requests.special_order_id`.
* Relasi desain → SKU hanya lewat `products.design_id`, yang diisi **satu-satunya** oleh `rnd_spec_service._product_draft`
  (baris 118) saat spesifikasi R&D ber-desain di-ACC. Data UAT: **0 produk** ber-`design_id`. Field
  `recommended_product_ids` di galeri adalah "peruntukan" yang diisi manual, bukan SKU yang lahir dari desain.
* Akibatnya **tidak bisa dihitung** "desain X dibeli siapa, berapa order, berapa qty": rantai desain → SKU → baris SO
  tidak punya data.
* Data UAT: 4 desain; `BDI-ABS-AO-001` (origin `special_order`, status `final_submitted`) dari OD Butik Bali Indah.
  Produk eksklusif pelanggan: 1 (`TEST`, dari SORD-261023-0003).

**OD memakai desain yang sudah ada — sudah ada sebagian.** Item OD bisa memilih "artwork ACC existing"
(`features/sales/CreateSpecialOrderForm.jsx:17,47`: `ARTWORK_OK = approved/final_submitted/active` dan **bukan HOLD**).
Server `special_order_items.assert_artwork_usable` menolak desain HOLD/belum ACC, lalu OD langsung proofing
(`special_order_routing.py:144–147`). Desain **HOLD justru dikecualikan**, bertolak belakang dengan butir 3.

### Riwayat — pernah diminta, tidak pernah ditutup
* `ANALISIS_FLOW_DIVISI.md:102` (18 Agt, dari berkas pemilik "ERP per divisi") **J8**: "MD Jakarta assign designer →
  hasil desain … → jadi item yang bisa di-order sales itu sendiri" — status **❌ BELUM**: "potongannya ada … tetapi
  tidak tersambung". Tidak ada commit yang menutup J8.
* Register 15 Okt SO-04/SO-07 (label/eksklusif OD): SO-07 "keseragaman label belum selesai".
* Istilah **white label / customer label** belum pernah tercatat di repo. Ini permintaan baru, atau dulu disampaikan
  lisan dan hilang saat pencatatan.

### Akar masalah
1. **Eksklusivitas ditempel di SKU, bukan di desain.** Bila desain milik pelanggan dipakai SKU lain (kain dasar lain,
   colorway lain), SKU baru itu **tidak** eksklusif. Tidak ada satu sumber kebenaran "desain ini milik siapa".
2. **Arti "HOLD" di kode berbeda dengan maksud pemilik.** Di kode HOLD = "ditahan, jangan diproofing". Bagi pemilik,
   desain yang di-hold = stok desain KN yang belum diproduksi dan boleh ditawarkan ke pelanggan.
3. **Rantai desain → SKU → penjualan tidak tercatat** (`design_id` hanya dari jalur spesifikasi), sehingga data
   pendukung keputusan klaim tidak bisa disediakan.
4. Penegakan eksklusif pelanggan **terlambat** (saat simpan SO), bukan saat produk dipilih di katalog/POS.

### Label desain — definisi sekarang & usulan
| Kelompok | Label (kode) | Arti | Sudah ada? |
|---|---|---|---|
| Status alur kerja | Draf (`draft`) | Desainer masih menggambar | Ya |
| | Diajukan (`pending_approval`) | Ronde dikirim untuk dinilai | Ya |
| | Dalam Review (`in_review`) | Sedang dinilai | Ya |
| | Perlu Revisi (`revision`) | Dikembalikan dengan catatan | Ya |
| | ACC — Menunggu Berkas Final (`approved`) | Disetujui, berkas final belum lengkap | Ya |
| | Final Diserahkan (`final_submitted`) | Mockup + berkas asli sudah diunggah | Ya |
| | Aktif / Produksi (`active`) | Dipakai produksi | Ya |
| | Diarsipkan (`archived`/`retired`) | Tidak dipakai | Ya |
| Asal | Desain internal / Pesanan Khusus / Redesign (`origin`) | Dari mana desain lahir | Ya |
| Penanda | HOLD (`on_hold`) | Ditahan — tidak boleh proofing/aktif | Ya (arti perlu diputuskan, [KEPUTUSAN] P1-K2) |
| Proofing | Belum proofing / Proofing berjalan / Proofing selesai / Sudah jadi master produk | Turunan dari sampel R&D | Ya (`PROOFING_STATE_LABEL`) |
| **Kepemilikan (BARU)** | **White label** (`white`) | Bebas dijual ke siapa saja | **Belum** |
| | **Customer label** (`customer` + `owner_customer_id`) | Milik satu pelanggan; semua SKU ber-desain ini hanya untuk pelanggan itu | **Belum** |
| | **Klaim menunggu keputusan** (`claim_pending`) | Pelanggan mengajukan klaim; tetap white sampai diputus | **Belum** |
| **Produksi (BARU, turunan)** | Belum diproduksi / Sudah diproduksi | Ada tidaknya SKU rilis ber-`design_id` ini | **Belum** |

### Rencana perbaikan
* **P1.1 Model kepemilikan di desain (SSOT).** Tambah di `design_gallery`:
  * `ownership: "white" | "customer"`, `owner_customer_id/name`;
  * `ownership_source` (`special_order` / `claim` / `manual`), `ownership_history[]`;
  * `claims[]` (`customer_id`, `by`, `at`, status `pending/approved/rejected`, `decided_by`, `reason`).

  Aturan:
  * Desain `origin=special_order` otomatis `customer` milik pemesan (hook di `design_studio_service` saat desain dari
    permintaan OD dibuat/di-ACC).
  * Desain internal: `white` (bawaan, sekaligus migrasi data lama).

  Layanan baru `design_ownership_service.py`: `claim()`, `decide_claim()` (peran: [KEPUTUSAN] P1-K1),
  `release_to_white()`, `usage(design_id)`.
* **P1.2 Rantai desain → SKU.** Tulis `products.design_id/design_code` di **semua** jalur kelahiran SKU ber-desain:
  * spesifikasi R&D (sudah ada);
  * realisasi item OD dengan `source_design_id`;
  * form master produk (P6).

  Migrasi: isi dari `md_specs.design_id` dan dari `special_orders.items.source_design_id` → `linked_product_id`.
* **P1.3 Penegakan eksklusif dari desain.**
  * Perluas `special_order_phase2.assert_customer_allowed`: produk ber-`design_id` yang desainnya `customer` milik
    pelanggan lain ditolak.
  * **Saring katalog/POS**: SKU eksklusif pelanggan lain **tidak tampil** bila pelanggan aktif sudah dipilih (P8), dan
    tampil "terkunci" bila belum dipilih.
  * Penolakan di server tetap (SO, OD, harga khusus, keranjang).
* **P1.4 Data pendukung klaim.** Endpoint `GET /design-gallery/{id}/usage` mengembalikan:
  * pelanggan pembeli (dari `sales_orders.items` dengan `product_id` ∈ SKU ber-`design_id`);
  * jumlah SO, total qty per satuan, SO terakhir, nilai.

  Dipakai di dialog keputusan klaim.
* **P1.5 Galeri.**
  * Lencana **White label / Customer label (nama) / Klaim menunggu** dan **Diproduksi / Belum**.
  * Filter `ownership`, `owner_customer_id`, `produced`.
  * Panel "Pemakaian" (P1.4).
* **P1.6 OD memakai desain KN existing.**
  * Pilihan artwork di OD menampilkan desain `white` yang **belum diproduksi**, plus desain HOLD bila
    [KEPUTUSAN] P1-K2 = boleh.
  * Saat OD disetujui, desain beralih ke `claim_pending`/`customer` sesuai keputusan.

### [KEPUTUSAN]
* **P1-K1** — Siapa yang memutus klaim desain (Manajer? Admin? PIC Designer)? Apakah pembeli lama SKU itu masih
  boleh repeat order setelah klaim disetujui?
* **P1-K2** — Pilih salah satu arti HOLD:
  * (a) HOLD tetap "ditahan dari proofing", ditambah penanda "Belum diproduksi" untuk desain siap tawar;
  * (b) HOLD = "cadangan desain KN, boleh ditawarkan ke pelanggan OD".

  Usulan: **(a)**, karena HOLD sekarang juga dipakai menahan desain bermasalah.
* **P1-K3** — Desain dari OD menjadi customer label **sejak OD disetujui** atau **sejak OD selesai/dibayar**?

### Kriteria terima
1. Desain asal OD tampil berlabel "Customer label · <pelanggan>" di galeri; filter "Milik pelanggan" menampilkannya.
2. Untuk pelanggan lain:
   * SO/POS dengan SKU ber-desain itu ditolak di server (uji API);
   * SKU itu tidak muncul di katalog POS saat pelanggan lain aktif (uji UI).
3. Panel Pemakaian desain menampilkan pembeli, jumlah SO, dan qty yang cocok dengan data SO (uji API dengan data buatan).
4. Klaim diputus Manajer: label berubah, riwayat tercatat, dan sales pengaju mendapat notifikasi.
5. OD bisa memilih desain white label yang belum diproduksi.

---

## P2 — Harga pesanan khusus: tampil ke sales + nego lewat mekanisme harga khusus

### Permintaan pemilik
Harga final OD **ditunjukkan ke sales**. Sales masih bisa **mengajukan harga nego** dengan mekanisme yang **sama dengan
harga khusus**. Semua ini terjadi **sebelum produksi / PO**.

### Mekanisme sekarang (bukti)
**Harga khusus SO biasa**:
* Pengajuan: `POST /sales-orders/{id}/request-special-price` (`routers/so_approvals.py:114–156`) atau dari checkout
  (`so_special_price_service.attach_checkout_requests`). Alasan wajib.
* SO harus berstatus `reserved/waiting_approval/waiting_stock/draft` (`OPEN_STATES`).
* Pengajuan menulis `price_approvals` + `sales_orders.pending_approvals[]` dengan `required_role="manager"`
  (`attach_order_price`).
* Diputus Manajer (`decide_approval`, cek SoD):
  * ACC → harga baris diganti (`price_source="special_approval"`) dan total dihitung ulang (`_apply_decision`);
  * Tolak → sales ajukan harga lain / **lanjut harga normal** (`so_release_service.continue_normal_price`) / batalkan.

  Ini keputusan pemilik E10 (22 Okt).

**Harga OD**:
* Rumus: harga kontrak supplier pemenang × (1 + margin%), bawaan 30% (`special_order_phase2.pricing_preview` /
  `item_price_lines`).
* **Kunci harga** `routers/special_orders.py:617–623` boleh dilakukan **sales**, sales_admin, manager, admin, dengan
  margin bebas 0–500% **tanpa persetujuan**.
* Kunci harga **langsung memicu pengadaan**: `lock_price` → `auto_procure` → `realize_all` (PR + PO), `auto_po`
  bawaan true. SO dibuat otomatis bila pengadaan lengkap (`routers/special_orders.py:633–638`).
* **Biaya kontrak, supplier, nomor kontrak, dan margin terlihat sales**: `GET /special-orders/{id}/pricing` hanya butuh
  `order.view`, dan ditampilkan di `SpecialOrderPricingPanel.jsx`. Baris SO hasil OD juga menyimpan `cost_price` dan
  `margin_pct`.
* SO hasil OD lahir dengan `price_source="special_order"` dan **tidak** melewati gerbang harga khusus. Sales secara
  teknis bisa mengajukan harga khusus dari detail SO, tetapi saat itu **PO sudah lahir**.
* `_special_price_target` mencocokkan baris lewat `product_id` pertama (`so_approvals.py:103–111`), jadi ambigu bila
  dua item OD ber-SKU sama.

### Riwayat — KONTEKS HILANG (terbukti)
Pemilik sudah memberi arah harga OD pada 15 Okt. Register pernyataan
`docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/sources/REGISTER_PERNYATAAN_126_HISTORIS.json`,
**SO-12** (`discussion_state: resolved_direction`): *"Harga Pesanan Khusus dari induk menggunakan harga Grade A; bila
tidak ada induk, PIC Special Order menentukan harga."* Kolom `current_support` sudah menulis: "Pricing preview OD saat
ini berbasis biaya sample dan margin; kesesuaian … perlu diselaraskan."

Arah ini **tidak pernah diterapkan**: `special_order_phase2.item_price_lines` masih menghitung `cost × (1 + margin)`
(baris 8–41), dan grep "Grade A/induk" di modul itu = nihil. SO-12 dipetakan ke LN-022, lalu tenggelam.

### Akar masalah
0. **Arah harga pemilik (SO-12) hilang di pemetaan** register → LN, sehingga rumus lama (biaya × margin) bertahan.
1. **Kunci harga dan pengadaan menjadi satu aksi**, sehingga tidak ada jendela nego sebelum PO.
2. Mekanisme harga khusus terikat ke **SO**, padahal sebelum kunci harga OD belum punya SO.
3. Tidak ada pemisahan "harga final" (untuk sales) dan "biaya/margin" (untuk Admin Sales/Manajer).

### Rencana perbaikan
* **P2.0 Harga dasar sesuai SO-12.**
  * Item OD yang punya induk → harga dasar = **harga jual Grade A induk** (varian Grade A induk; harga pelanggan/entitas
    mengikuti urutan `customer_price_service` yang sudah ada).
  * Tanpa induk → harga **diisi PIC Special Order** (izin baru `special_order.set_price` lewat manajemen akses).
  * Biaya kontrak × margin tetap ditampilkan **hanya** sebagai pembanding untuk Admin Sales/Manajer (cek laba), bukan
    penentu harga. [KEPUTUSAN] P2-K4.
* **P2.1 Pisahkan kunci harga dan pengadaan.**
  * `lock_price`: peran Admin Sales/Manajer/Admin ([KEPUTUSAN] P2-K1); `auto_po` bawaan **false**.
  * Setelah dikunci, SO **selalu** lahir (`waiting_stock`, backorder diizinkan), sehingga mekanisme harga khusus SO
    langsung bisa dipakai.
* **P2.2 Sales melihat "Harga final" dan tombol "Ajukan harga nego"** di panel OD.
  * Tombol memanggil `request-special-price` atas SO tertaut.
  * Target baris lewat `special_order_item_id` (perbaiki `_special_price_target`/`attach_order_price` agar tidak hanya
    `product_id`).
  * Lantai nego = harga kontrak ([KEPUTUSAN] P2-K3).
* **P2.3 Kait setelah keputusan** di `_apply_decision`. Bila SO berasal dari OD:
  * tulis `special_orders.pricing.items[i].final_unit_price/negotiated_price/special_price_id` dan total;
  * sinkronkan harga SKU eksklusif;
  * **jangan** auto-rilis ke gudang (barang belum ada).
* **P2.4 Gerbang pengadaan**: `auto_procure`/`realize` ditolak selama ada nego `pending`/`rejected` yang belum dijawab,
  dengan pesan "Nego harga belum diputus Manajer". Tombol "Realisasi pengadaan" aktif setelah beres.
* **P2.5 Visibilitas biaya**: izin baru `special_order.view_cost` (Admin Sales, Manajer, Admin, MD). Untuk peran lain
  diredaksi di API (detail OD, `/pricing`, baris SO): `cost_price`, `margin_pct`, `supplier_*`, `contract_number`.

### [KEPUTUSAN]
* **P2-K1** — Apakah sales masih boleh mengunci harga, atau hanya Admin Sales?
* **P2-K2** — Perlu ambang diskon kecil yang otomatis disetujui?
* **P2-K3** — Lantai nego = harga kontrak, atau kontrak + margin minimum (berapa %)?
* **P2-K4** — Konfirmasi ulang SO-12: harga OD ber-induk = harga Grade A induk **apa adanya**, atau Grade A + selisih
  biaya custom (mis. biaya screen/printing)? Bila harga Grade A induk **di bawah** biaya kontrak, apa yang terjadi?

### Kriteria terima
0. Item OD ber-induk → harga usulan = harga Grade A induk. Item tanpa induk → hanya PIC Special Order yang bisa
   mengisi harga (uji API + UI).
1. Admin Sales mengunci harga → SO lahir, **belum** ada PR/PO.
2. Sales (API & UI) melihat harga final tetapi **tidak** biaya, margin, supplier, atau kontrak.
3. Sales mengajukan nego → muncul di Pusat Persetujuan Manajer. Pengaju tidak bisa memutus sendiri.
4. ACC → baris SO, `pricing.items` OD, dan harga SKU berubah; pengadaan bisa direalisasi dan harga PO tetap harga
   kontrak.
5. Tolak → "lanjut harga normal" → harga OD tetap, pengadaan bisa jalan.
6. Selama nego pending, realisasi pengadaan ditolak.
7. OD dua item ber-SKU sama → nego menarget baris yang benar.

---

## P3 — Surat perintah kerja R&D ke supplier (proofing / labdip / handfeel)

### Permintaan pemilik
* MD bisa **mencetak surat perintah** (work order) ke supplier untuk tiap permintaan R&D.
* **Proofing** wajib membawa gambar pattern yang dicetak. Berkas final desainer wajib menyertakan **PNG desain ACC**.
* **Labdip** wajib membawa warna + kodenya; **kode Pantone harus jelas**.

### Mekanisme sekarang (bukti)
* Pengiriman ke supplier = `SampleSendModal` → `sendSample` (membuka ronde per supplier × jenis). **Tidak ada dokumen
  cetak**: `services/pdf_resolvers.py` tidak punya resolver untuk `md_samples` (dicek; yang ada SO/PO/GRN/SJ/dll.).
* Syarat berkas final desain: `design_studio_service.final_requirement` (baris 291) = minimal 1 `mockup` + 1 `source`.
  Tidak ada syarat format: `source` bisa PSD/AI/CDR yang tidak bisa dicetak di surat atau dibuka supplier.
  `FILE_KINDS` = artwork, reference, mockup, colorway, source, ai_illustration.
* Proofing wajib merujuk desain lewat kebijakan `require_design_for_proofing` (`rnd_sample_service.py:445`).
  Yang dicek hanya ada/tidaknya desain dan HOLD (`_assert_design_not_held`, baris 337). **Status ACC dan kelengkapan
  berkas final tidak dicek** di jalur sampel; pemilih di form hanya memberi label "(ACC)".
* Warna labdip = `color_target` dari Pustaka Warna (`specs._color_snapshot`): `code` (kode KN), `name`, `hex`, `system`.
  Kode Pantone hanya ada bila warna itu ber-`system` Pantone. Tidak ada field "kode Pantone" terpisah yang wajib.

### Akar masalah
Dokumen keluar R&D tidak pernah dimodelkan. Syarat berkas final dibuat untuk arsip desainer, bukan untuk eksekusi
supplier.

### Rencana perbaikan
* **P3.1 Resolver PDF `md_sample_work_order`** (`pdf_resolvers.py` + templat), satu surat per supplier peserta.
  * Kepala: nomor sampel, tanggal, target selesai, supplier, PIC MD.
  * Per jenis:
    * **Proofing**: gambar PNG desain ACC (versi ACC), kode desain, ukuran repeat, jumlah warna/screen, kain dasar;
    * **Labdip**: kotak warna (hex), kode KN, **kode Pantone (wajib)**, nama warna versi pelanggan bila OD, kain dasar;
    * **Handfeel**: konstruksi (EPI/PPI, benang, gramasi, lebar), referensi swatch.
  * Kaki: catatan, tanda tangan.
* **P3.2 Tombol "Cetak surat perintah"** di `SampleDetailPanel` (per supplier, setelah "Kirim ke supplier"), dan di Jejak
  Dokumen (P16).
* **P3.3 Berkas final desain** — `final_requirement` ditambah `print_png_required: 1`: minimal satu berkas jenis baru
  `print_png` (PNG, ≥ resolusi minimum terkonfigurasi), dan `submit_final` ditolak tanpa berkas ini. Migrasi: desain
  `final_submitted` lama diberi peringatan "PNG cetak belum ada", tidak ditolak mundur.
* **P3.4 Proofing hanya dari desain ACC berkas lengkap** — validasi server di `create_sample` dan `send` (bukan hanya
  label di UI).
* **P3.5 Pantone wajib untuk labdip.**
  * `color_target.pantone_code` wajib diisi saat labdip dikirim ke supplier.
  * Sumber nilainya: warna OD pelanggan / input MD, divalidasi format `NN-NNNN TCX/TPX` atau kode C.
  * Lihat juga P4.4: warna target labdip tidak lagi dari Pustaka.

### Kriteria terima
1. Sampel proofing → PDF surat perintah memuat PNG desain ACC dan kode desain. Desain tanpa PNG tidak bisa
   `submit_final` (uji API).
2. Sampel labdip tanpa Pantone tidak bisa dikirim ke supplier (uji API + UI). PDF memuat kotak warna + Pantone.
3. Cetak dari detail sampel dan dari Jejak Dokumen menghasilkan PDF yang sama.

---

## P4 — R&D: pisahkan "uji ulang" dan "produk baru"

### Permintaan pemilik
1. **Uji ulang** dipisah dari **produk baru**: tab baru "R&D produk baru"; tab yang ada tetap untuk uji ulang.
2. Urutan produk baru: **handfeel → labdip (dari hasil handfeel ACC) → produk baru**.
3. Labdip bisa menguji **banyak warna sekaligus** (mis. 5), sehingga lahir **banyak varian**.
4. Printing memakai kain woven/knit **yang sudah ada** (sudah lolos handfeel/labdip). Printing di produk multi-warna
   membawa **seri warna**-nya.
5. Perbaikan form:
   * supplier uji ulang = hanya supplier yang **punya kontrak** untuk produk itu;
   * labdip multi-warna memilih **artikel** (bukan SKU);
   * warna target **bukan** dari Pustaka Warna — Pustaka **lahir** dari labdip ACC, dan Pustaka menampilkan SKU yang
     memakai tiap warna;
   * "Desain / pattern (opsional)" dibuang dari labdip (hanya tampil untuk labdip+proofing);
   * "Untuk pesanan pelanggan (opsional)" dibuang kecuali OD.
6. Aksi per tahap harus masuk akal, mis. kenapa ada "kirim sampel" setelah pemenang dipilih?
7. Perbaiki logika **kain dasar** di spesifikasi produk target.

### Mekanisme sekarang (bukti)
| Butir | Sekarang | Bukti |
|---|---|---|
| 1 | Satu form untuk dua mode: "Pengembangan baru (spesifikasi baru)" / "Uji tambahan SKU existing". Tab hub R&D: Permintaan Sample · Labdip · Handfeel · Proofing · Laporan, dibagi per **jenis**, bukan per tujuan | `features/rnd/SampleFormModal.jsx` (pemilih mode), `config/hubTabs.js:92–104` |
| 2 | Jenis sampling dipilih bebas (multi-centang). Tidak ada rantai "labdip berasal dari handfeel ACC"; tidak ada field sampel induk | `rnd_sample_service.create_sample` (`sample_types` list); grep `parent_sample/source_sample` = kosong |
| 3 | Satu sampel = **satu** `color_target` | `rnd_sample_service.py:437,474` |
| 4 | Kain dasar = **induk** (template) mana pun dari master data, tanpa syarat lolos handfeel/labdip. Seri warna kain dasar tidak dibawa ke proofing | `components/BaseFabricPicker.jsx` (daftar semua induk), `services/base_fabric.py` (hanya `template_id/name/sku_prefix`) |
| 5a | Supplier uji ulang = **semua** supplier + makloon aktif (tanpa kontrak) | `rnd_revalidation_service.lookup_partners` (baris 329) |
| 5b | Mode uji ulang memilih **SKU** existing | `features/rnd/ExistingSkuSection.jsx` |
| 5c | Labdip: "Warna target dari **Pustaka Warna** *" (wajib). Saat sampel diputus, nama/kode warna supplier ditambahkan ke warna Pustaka yang sudah ada (`supplier_variants`). Pustaka = INPUT | `SampleSpecFields.jsx:87`, `SpecFormModal.jsx:251`, `rnd_sample_service.py:1260–1290` |
| 5d | Di blok labdip, pemilih "Desain / pattern" **selalu tampil** (opsional) | `SampleSpecFields.jsx:100–104` |
| 5e | "Untuk pesanan pelanggan (opsional)" menampilkan **200 SO mana pun** | `SampleFormModal.jsx:67,204–208` |
| 6 | Tombol: "Kirim ke supplier" (status draft/sent/in_progress/assessed), "Pilih pemenang", "Sample jadi" (aktif begitu ada ronde ACC, **sebelum** pemenang dipilih), lalu "Kirim sample" (ke pelanggan/sales/supplier/arsip) setelah "Sample jadi" | `SampleDetailPanel.jsx:130,318–345` |
| 7 | **BUG**: di form sampel, `BaseFabricPicker` memanggil `onChange(tpl)` (satu objek), tetapi `SampleSpecFields` menangkapnya sebagai `(id, name)`. Akibatnya `base_fabric_template_id` berisi **objek** dan `base_fabric_name` kosong. Tombol pemilih lalu me-render objek (`valueName \|\| value`), sehingga React gagal render. Bila lolos, server menerima objek dan `base_fabric.snapshot` menolak "Kain dasar tidak ditemukan". Form spesifikasi (`SpecFormModal.jsx:184–185`) memakai tanda tangan yang benar. **Dibuktikan 23 Okt** dengan uji Jest sementara (komponen asli, katalog di-mock): memilih kain dasar → galat render *"Objects are not valid as a React child (found: object with keys {id, name, …})"*; isi state `base_fabric_template_id` = objek, `base_fabric_name` = "" | `BaseFabricPicker.jsx:21`, `SampleSpecFields.jsx:107–108` |

Data UAT: Pustaka Warna 109 entri (kode KN, hex, sistem, keluarga). 283 produk aktif: **0** ber-`color_ref`, **0**
`color_code` yang cocok dengan Pustaka; warna produk = teks bebas. Kontrak per produk ada di `supplier_contracts.product_id`:
714 `internal`, 8 `makloon`, **1** `purchase`.

### Akar masalah
1. Model R&D dibangun per **jenis uji**, bukan per **tujuan** (produk baru vs uji ulang). Urutan bisnis tidak dimodelkan.
2. **Arah data warna terbalik**: Pustaka diperlakukan sebagai daftar warna yang harus sudah ada, padahal warna baru
   justru lahir dari labdip. Produk lama juga tidak tertaut ke Pustaka (0 `color_ref`), sehingga "SKU yang memakai warna
   ini" selalu kosong.
3. Form generik menampilkan semua field ke semua jenis, termasuk field yang tidak relevan.
4. Bug tanda tangan `onChange` kain dasar (regresi saat `BaseFabricPicker` diubah memberi objek).
5. Tombol aksi disusun per status teknis, bukan per tahap bisnis. "Kirim sample" (ke pelanggan) dan "Kirim ke supplier"
   memakai kata yang sama.

### Rencana perbaikan
* **P4.1 Dua pintu R&D.**
  * Tab baru **"R&D Produk Baru"** berisi alur bertahap: Handfeel → Labdip → Spesifikasi/SKU.
  * Tab lama menjadi **"Uji Ulang"**: mode `revalidation` saja, pilih artikel/SKU existing, supplier berkontrak.
  * Field `purpose` sudah ada (`new_development`/`revalidation`), tinggal dipakai sebagai pemisah daftar & form.
* **P4.2 Rantai tahap.** `md_samples.parent_sample_id` + `stage` (`handfeel`/`labdip`/`proofing`).
  * Labdip produk baru **wajib** merujuk handfeel yang ACC (konstruksi diwarisi).
  * Printing (proofing) merujuk **artikel kain dasar yang sudah lolos** (handfeel/labdip ACC atau SKU produksi) dan
    membawa seri warnanya.
  * Server menolak urutan yang dilompati; pemilik dapat mematikan lewat kebijakan R&D.
* **P4.3 Labdip multi-warna.** `color_targets[]` (≤ N, bawaan 10).
  * Satu ronde per supplier × warna; ACC per warna.
  * Pemenang diputus per warna; setiap warna ACC melahirkan **satu varian** (sumbu warna baru di induk).
  * Pilihan dasarnya **artikel** (induk), bukan SKU.
* **P4.4 Pustaka Warna = keluaran labdip.**
  * Input labdip = warna target "bebas": nama, hex, **Pantone (wajib, P3.5)**, foto swatch.
  * Saat warna di-ACC, sistem **membuat** entri Pustaka (kode KN otomatis) atau menautkannya ke entri yang ada bila
    Pantone sama (dicek, tidak diam-diam).
  * Pustaka menampilkan "SKU yang memakai warna ini" dari `products.color_ref`.
  * Migrasi: tautkan produk lama ke Pustaka lewat pencocokan nama/kode yang **ditinjau manusia** (laporan kandidat,
    bukan otomatis).
* **P4.5 Form bersih per jenis.**
  * Labdip saja → tanpa desain.
  * Labdip + proofing → dengan desain.
  * "Untuk pesanan pelanggan" hanya muncul bila sampel lahir dari OD (terisi otomatis, tidak dipilih manual dari semua SO).
* **P4.6 Supplier uji ulang = berkontrak.** `lookup_partners(product_id)` menyaring `supplier_contracts`
  (`partner_id`, `product_id` = produk / induknya, jenis `purchase`/`makloon`), ditambah penanda "pernah PO" sebagai
  pilihan kedua — [KEPUTUSAN] P4-K1, karena data UAT hanya punya 1 kontrak `purchase`.
* **P4.7 Aksi per tahap.** Urutan tombol: Kirim ke supplier → Setor & nilai ronde → Pilih pemenang → **Terima sampel
  fisik** (sebelumnya "Sample jadi", aktif **setelah** pemenang) → **Kirim ke pelanggan** (hanya OD) / **Arsipkan**
  (non-OD). Tombol yang tidak berlaku disembunyikan dengan petunjuk.
* **P4.8 Perbaiki kain dasar.**
  * `SampleSpecFields` memakai `onChange(tpl)` yang benar; uji Jest menyertainya.
  * Kain dasar untuk printing dibatasi ke induk woven/knit yang lolos (P4.2).

### [KEPUTUSAN]
* **P4-K1** — Bila produk belum punya kontrak supplier, apakah uji ulang boleh memilih supplier "pernah PO", atau harus
  membuat kontrak dulu?
* **P4-K2** — Batas jumlah warna per labdip (usul 10). Apakah satu warna ACC langsung melahirkan SKU (lifecycle
  "disetujui", belum dijual), atau menunggu spesifikasi per warna?

### Kriteria terima
1. Tab "R&D Produk Baru" dan "Uji Ulang" terpisah; masing-masing hanya menampilkan sampel dengan `purpose` itu.
2. Labdip produk baru tanpa handfeel ACC ditolak server. Dengan handfeel ACC, konstruksi terwarisi.
3. Labdip 5 warna → 5 ronde per supplier. ACC 3 warna → 3 varian + 3 entri Pustaka baru dengan Pantone.
4. Supplier uji ulang hanya yang berkontrak untuk produk itu (uji API).
5. Memilih kain dasar di form sampel tidak membuat layar galat dan tersimpan benar (uji Jest + UI).
6. "Terima sampel fisik" tidak bisa ditekan sebelum pemenang dipilih; "Kirim ke pelanggan" hanya ada pada sampel OD.

---

## P5 — Galat "Kombinasi ini sudah memiliki SKU yang dirilis/terhubung R&D. Pilih kombinasi baru."

### Yang terjadi di tangkapan layar
Form spesifikasi produk baru: **Induk = LINEN OAT**, Asal Impor, Warna **3**, Grade A, Kode Customer *Tidak ada*,
Lot *Tidak ada*.

* Pilihan tiap sumbu **hanya** nilai yang sudah ada di induk (`SpecVariantFields.jsx:28–41`: opsi dari `tpl.axes`).
* Data UAT LINEN OAT: sumbu warna = `2XXX, 3XXX, 4XXX, 5XXX, ABUX, BWXX`, dan **keenam** varian
  `KNWVN0031-I-{2,3,4,5,ABU,BW}XXX-XA-XX-XX` sudah ada dengan lifecycle **produksi**.
* Aturan `SpecVariantFields.jsx:38–40`: kombinasi yang sudah punya SKU dengan `spec_id`, **atau** lifecycle `produksi`,
  **atau tanpa lifecycle**, dianggap tidak sah. Server menegakkan hal yang sama di `rnd_spec_service.approve_spec`
  ("SKU ini sudah dirilis atau memiliki spesifikasi").

**Jadi untuk LINEN OAT tidak ada satu pun kombinasi yang bisa dipilih.** Pesan menyuruh "pilih kombinasi baru", padahal
form tidak menyediakan cara membuat kombinasi baru.

### Penilaian
Aturan dasarnya **benar**: spesifikasi produk baru tidak boleh menimpa SKU yang sudah dijual. Yang **salah** ada tiga:
1. Form tidak bisa menambah **nilai sumbu baru** (mis. warna baru hasil labdip). Varian baru hanya bisa lahir bila
   induk diedit dulu di Master Katalog. Ini memutus alur P4.3/P4.4.
2. Pesan buntu: tidak menawarkan "SKU ini sudah ada → **Uji ulang SKU ini**" atau "**Tambah warna baru** ke induk".
3. Pilihan mode "Induk baru saat persetujuan" tersembunyi di daftar yang sama, sehingga pengguna tidak tahu bedanya.

### Rencana perbaikan
* **P5.1** Pada pemilih kombinasi, nilai yang sudah jadi SKU ditandai "sudah ada (SKU …)" dan **tidak bisa dipilih**
  (bukan galat setelah dipilih). Tambah tombol **"Warna baru dari labdip"** yang mengambil warna ACC (P4.4); sumbu baru
  dibuat saat spesifikasi di-ACC.
* **P5.2** Bila semua kombinasi sudah ada, tampilkan dua jalan keluar: **Uji ulang SKU ini** (beralih ke tab Uji Ulang
  dengan SKU terisi) atau **Tambah nilai sumbu** (untuk peran pengelola katalog).
* **P5.3** Server: `approve_spec` menerima `new_axis_values` (sumbu → kode/label baru), divalidasi unik, lalu menambah
  opsi ke induk secara atomik bersama kelahiran SKU.

### Kriteria terima
1. LINEN OAT: keenam warna lama tampil "sudah ada". Warna baru dari labdip ACC bisa dipilih, lalu SKU
   `KNWVN0031-I-<kode baru>-XA-XX-XX` lahir saat ACC (uji API).
2. Tidak ada lagi pesan buntu; selalu ada tombol jalan keluar (uji Jest).

---

## P6 — Master produk: kode desain, pattern, kategori desain sebagai tag

### Permintaan pemilik
Master produk punya **kode desain, pattern, kategori desain** sebagai tag. Ketiganya bisa difilter di POS dan ikut
**Pusat Export**, supaya terlihat berapa banyak satu kode desain dibeli dan diulang (repeat order).

### Mekanisme sekarang (bukti)
* Field produk yang ada: `motif` (teks, bawaan "Polos" — `schemas.py:210,251,275`), `design_id/design_version` (hanya
  dari spesifikasi R&D — `rnd_spec_service._product_draft:118`). **Data UAT: 0 produk ber-`design_id`.**
* Desain punya `code`, `category_code/name` (kategori **pattern**), `design_category_code/name` (kategori **design**),
  `tags` (`design_gallery_service.create_gallery`). Tidak ada yang tersalin ke produk.
* POS: pencarian HP mencakup `motif` (`MobilePOS.jsx:37`); filter katalog "Warna / motif" teks bebas
  (`CatalogFilters.jsx:25`). Tidak ada filter desain/pattern/kategori.
* Pusat Export: `PRODUCT_JOIN` (`export_registry.py:27–30`) = sku, nama, kategori, warna, grade, tahap, jenis kain.
  Join produk di baris penjualan (`export_registry.py:67–69`) = warna, grade, jenis kain. **Tidak ada kolom desain.**

### Akar masalah
Relasi desain → produk hanya dibangun untuk jalur R&D baru. Produk lama dan produk dari jalur lain tidak punya
referensi desain, sehingga POS dan export tidak punya data untuk difilter.

### Rencana perbaikan
* **P6.1 Field produk** (denormalisasi dari desain):
  * `design_id`, `design_code`, `pattern_category_code/name`, `design_category_code/name`, `design_tags[]`;
  * diisi lewat pemilih **desain** di form master produk/induk (bukan ketik bebas), dari P1.2, dan lewat sinkron saat
    desain diubah;
  * `motif` tetap ada (teks bebas lama), diberi label "Motif (catatan)".
* **P6.2 Migrasi**: laporan kandidat pencocokan produk ↔ desain (nama/motif/kode) untuk **ditinjau MD**, bukan tebakan
  otomatis.
* **P6.3 POS & katalog**: facet "Kode desain", "Kategori pattern", "Kategori design" di `FacetRail` (desktop) dan
  filter HP; pencarian ikut mencakup kode desain.
* **P6.4 Pusat Export**:
  * kolom desain di `PRODUCT_JOIN` dan join produk baris penjualan;
  * dataset baru **"Penjualan per desain"**: kode desain → jumlah pelanggan, jumlah SO, qty, nilai, **repeat** (pelanggan
    dengan ≥ 2 SO), SO pertama/terakhir. Sama sumbernya dengan panel Pemakaian P1.4.

### Kriteria terima
1. Produk bisa diberi desain dari pemilih; kode/kategori tersalin dan ikut berubah bila desain diubah.
2. POS bisa difilter per kode desain/kategori (uji UI desktop & HP).
3. Export "Penjualan per desain" cocok dengan data SO buatan (uji API), termasuk hitungan repeat.

---

## P7 — Menu baru "Perbaikan" (repair & celup ulang) dengan biaya, memilih roll yang ada

### Mekanisme sekarang (bukti)
* **Tidak ada menu/dokumen perbaikan.**
* Yang ada: `lot_service.rework_lot` (`POST /lots/{id}/rework`, baris 483–523). Membentuk lot anak `source="rework"`
  dengan `process_type`, memindah roll ke lot anak, dan menandai lot induk `rework`.
  * **Tanpa biaya**, tanpa dokumen kirim ke mitra, tanpa penerimaan kembali, tanpa susut.
  * Layar: `features/inventory/lots/LotActionModals.jsx` (aksi di detail lot).
* SPK makloon (`makloon_order_service`) sudah mendukung bahan dari **stok** (`material_source="stock"`), langkah proses
  dari master tahap, **kontrak tarif per mitra** (`contract_service.resolve_active`), susut, dan penerimaan hasil. Tetapi
  dirancang untuk produksi (greige → jadi), bukan perbaikan roll jadi.

### Akar masalah
Fitur belum pernah dibangun. Bahan bakunya ada (rework lot, makloon, kontrak tarif), tetapi tidak dirangkai untuk
kasus "roll jadi yang cacat/warna meleset → diperbaiki / dicelup ulang → kembali ke stok".

### Rencana perbaikan
* **P7.1 Dokumen `repair_orders`** (nomor `RPR-…`):
  * jenis: `perbaikan` (repair cacat) / `celup_ulang` (re-dye, wajib warna tujuan/dye lot baru) / `finishing_ulang`;
  * mitra: internal / makloon (kontrak opsional);
  * baris = **roll yang dipilih** (pemilih roll dengan filter grade/cacat/lokasi; roll dari retur atau karantina boleh);
  * biaya: tarif kontrak atau manual (per yard/kg/roll/lumpsum) + biaya lain (ongkos kirim).
* **P7.2 Alur status**: Draf → Dikirim (roll `in_repair`, keluar dari ATP, SJ ke mitra bila eksternal) → Diterima
  kembali (qty hasil per roll, susut, grade baru, dye lot baru → roll anak/roll sama) → Selesai.
* **P7.3 Akuntansi** [KEPUTUSAN] P7-K1:
  * (a) biaya **dikapitalisasi** ke nilai persediaan roll hasil (HPP naik), atau
  * (b) dibebankan (beban perbaikan).

  Tagihan mitra memakai Vendor Bill yang ada.
* **P7.4 Menu**: "Perbaikan" di hub Gudang/MD; masuk Jejak Dokumen (P16) dan Pusat Export.
* **P7.5 Tautan**: dari retur (roll cutloss/grade turun), dari SPK QC (roll ditolak), dan dari detail roll → "Kirim ke
  perbaikan".

### [KEPUTUSAN]
* **P7-K1** — Biaya perbaikan dikapitalisasi ke roll atau dibebankan?
* **P7-K2** — Hasil celup ulang: tetap SKU yang sama (warna sama, dye lot baru) atau boleh berubah SKU (warna lain)?

### Kriteria terima
1. Buat perbaikan dari 3 roll → roll keluar dari ATP; terima kembali dengan susut 2% dan grade baru → stok & nilai
   sesuai keputusan K1 (uji API + jurnal).
2. Celup ulang mencatat dye lot baru; jejak roll menampilkan riwayat perbaikan.

---

## P8 — POS/Beranda sadar lokasi + pelanggan wajib dipilih di awal

### Permintaan pemilik
1. Di POS/Beranda pengguna **memilih lokasi gudang** dulu (mis. Jakarta). Katalog menonjolkan stok di lokasi itu.
2. Masuk katalog **wajib** memilih pelanggan **dan** lokasi. Ada opsi pelanggan baru.
3. Cek ulang permintaan lama "sales di POS bisa pilih pelanggan" ("sepertinya belum diimplementasikan").
4. Info stok ditampilkan untuk lokasi pengguna. Pemilihan roll: **lokasi dulu, lalu FIFO** (bukan FEFO — kain tidak
   kedaluwarsa).

### Mekanisme sekarang (bukti)
**Pilih pelanggan — ada, tetapi opsional dan bolong** (riwayat F1b desktop; E2 HP 22 Okt, commit `9b80100`):
* Desktop: bilah `pos-customer-bar` di atas katalog (`features/sales/SalesPortal.jsx:121–159`), harga ikut pelanggan
  (`useEffectivePrices`). "Pelanggan Baru" hanya ada di **checkout** (`pos/CheckoutDrawer.jsx:281–292`). Status kredit
  tidak tampil di bilah desktop.
* HP: `MobileCustomerBar.jsx` di atas katalog & keranjang (dengan chip kredit). "Buat Pesanan Baru" di Beranda HP
  (`MobileSalesHome.jsx:76`) **tidak** meminta pelanggan.
* Daftar pelanggan diambil dari `GET /dashboard`, yang **memotong di 100** (`routers/dashboard.py:53`) dan hanya
  bercakupan **entitas** (bukan milik sales, lihat P14).
* Pilihan hilang setelah muat ulang. Strip Terlaris HP tanpa harga pelanggan (`MobileCatalog.jsx:73`); FBT memakai
  harga umum (`PosFBT.jsx:39`).

**Lokasi — tidak ada sama sekali**:
* Tidak ada pemilih lokasi/gudang di POS, katalog, maupun Beranda. `components/ProductQuickView.jsx:22` menulis
  terang-terangan "Inventory POS = TOTAL GLOBAL saja (tanpa breakdown per gudang/lot/entitas)".
* Angka stok katalog = `sales_stock_service.apply_global` (Σ semua PT & gudang), tanpa rincian per gudang. Rincian per
  gudang hanya di `GET /products/{id}/stock-breakdown` dan menu HP "Stok & ATP".
* Pilih roll di Quick View diurutkan "FEFO" yang sebenarnya FIFO `created_at` (P9.9), tanpa memperhatikan lokasi.

### Akar masalah
1. Permintaan "pilih pelanggan" diterapkan sebagai **pilihan opsional** di atas katalog, bukan **gerbang masuk**.
   Sumber daftarnya juga salah (dasbor, batas 100, tidak sesuai kepemilikan sales).
2. Model lokasi (P9) tidak pernah disambungkan ke sisi penjualan; POS sengaja dirancang "total global".

### Rencana perbaikan
* **P8.1 Gerbang "Mulai jualan"** (desktop & HP, termasuk tombol "Buat Pesanan Baru"):
  * langkah 1: **Lokasi** (bawaan = lokasi akun / terakhir dipakai; daftar lokasi aktif);
  * langkah 2: **Pelanggan**: pencarian server `GET /customers?q=` dengan cakupan P14 (milik sendiri) + **"Pelanggan
    baru"** (`CreateCustomerModal` / `MobileCustomerForm`, langsung terpilih).

  Pilihan disimpan per sesi (`sessionStorage`) dan bisa diganti dari bilah atas. Kebijakan
  `pos.require_customer_first` / `pos.require_location_first` ([KEPUTUSAN] P8-K1 untuk peran non-sales).
* **P8.2 Stok per lokasi.**
  * `apply_global` menambah `by_site` dan `site_available_qty`; `/dashboard` dan `/products` menerima `site_id`.
  * Kartu produk menampilkan **"Di Jakarta: 120 yd"** (menonjol) + "Lokasi lain: 300 yd" (abu-abu).
  * Facet "Tersedia di lokasi ini". Quick View: rincian per gudang di lokasi itu.
* **P8.3 Pilih roll**: urutan **lokasi terpilih → FIFO** (`received_date`); roll lokasi lain diberi label
  "perlu transfer".
* **P8.4 SO membawa `fulfillment_site_id`** = lokasi terpilih → alokasi P9.6, PR/PO reorder ke lokasi itu (P9.2).
* **P8.5** Teruskan harga pelanggan ke Terlaris & FBT. Chip kredit di bilah desktop.

### [KEPUTUSAN]
* **P8-K1** — Wajib pelanggan + lokasi berlaku untuk semua peran yang membuka POS (sales, Admin Sales/kasir,
  manajer), atau hanya sales?
* **P8-K2** — Satuan lokasi = **site** (Jakarta/Rancamalang/Soreang), bukan gudang? (Usulan: site.)

### Kriteria terima
1. Membuka katalog tanpa lokasi & pelanggan → layar gerbang. Setelah dipilih, bilah atas menampilkan keduanya (uji UI
   desktop & HP).
2. Pelanggan ke-150 milik sales bisa dicari. Pelanggan baru dibuat dari gerbang dan langsung terpilih.
3. Lokasi Jakarta: kartu menampilkan stok WH-JKT sama dengan `stock-breakdown`. Pilih roll mendahulukan roll Jakarta
   lalu FIFO.
4. SO yang tersimpan membawa `fulfillment_site_id`.

---

## P9 — Model lokasi: Lokasi (site) → banyak gudang ber-peran; PO dikirim ke LOKASI

### Permintaan pemilik
* Admin Sales dan gudang **sadar lokasi**.
* Lokasi = area berisi beberapa gudang, masing-masing punya **peran** (transit, inspeksi, penyimpanan, …).
* **PO dikirim ke lokasi**, bukan ke gudang. Barang masuk lewat **gudang transit** untuk dihitung dan diberi label.
  Bila **tidak ada SO** yang menunggu, barang dipindah (**putaway**) ke gudang penyimpanan.
* Logika sekarang dinilai "kacau": analisis.

### Data UAT (`kn_uat_23okt`, dicek langsung)
| Lokasi (site) | Gudang | Peran | Berbagi | Stok roll (pemilik) |
|---|---|---|---|---|
| Rancamalang (Bandung) | RCM-TRANSIT | transit, central_inbound, staging | shared (semua PT) | 0 |
| | RCM-WOVEN | storage | shared | 10.009 (CST) |
| | RCM-KNITTING | storage | shared | 10.387 (CST) |
| | RCM-PRINTING | storage | shared | 51 (CST) |
| | RCM-RETUR | return, storage | shared | 20 Kanda · 24 CST · 27 KSC |
| Soreang (Bandung) | SRG-01 | storage | dedicated Kanda | 2.902 (Kanda) |
| Jakarta | WH-JKT | storage | dedicated KSC | 23.151 + **4 roll ber-stage `received_transit`** (KSC) |
| — (tanpa lokasi, **nonaktif**) | WH-BDG, WH-SBY, GU-CST, GU-KSC, GU-KANDA | — | — | 0 |

PO UAT: 2 (keduanya ke WH-JKT). Putaway Order: 0. Transfer antar gudang/PT: 0. Akun berlokasi: hanya 3 akun peran
`warehouse` (Jakarta / Soreang / Rancamalang). Akun sales/Admin Sales **tidak** punya lokasi.

### Mekanisme sekarang (bukti) & kekacauan yang ditemukan
1. **Tujuan PO = gudang** (`schemas_purchasing.py:61–65` `warehouse_id` wajib).
   * Form PO "Gudang *" (`features/admin/po/POCreateForm.jsx:236–244`) memuat `GET /warehouses` **termasuk nonaktif**
     (`routers/warehouses.py:155–174` bawaan `include_inactive=True`).
   * `warehouse_scope_service.assert_usable` **tidak** menolak gudang nonaktif. Gudang lama tanpa lokasi masih bisa
     dipilih.
   * Konsep "kirim ke lokasi" **tidak ada** (grep `ship_to_site|destination_site|receiving_site` = nihil).
2. **Gudang tujuan diturunkan berbeda-beda** di tiap jalur:
   * PR→PO: gudang PR/pilihan (`pr_sourcing_service.py:393–396`);
   * OD: `special_order_phase2.default_warehouse_id` (dedicated dulu, lalu urut kode, **tanpa melihat peran**);
   * Reorder SO: `restock_service._default_warehouse` (baris 265–275) — **BUG**: mencari `warehouses.entity_id`, field
     yang tidak ada di gudang (yang ada `entity_ids`). Akibatnya selalu jatuh ke `find_one({})` = gudang pertama, yang
     bisa nonaktif (urutan data UAT: WH-JKT lalu **WH-BDG nonaktif**).
3. **Transit hanya label.** Roll yang diterima selalu diberi `journey.stage="received_transit"`
   (`inbound_complete_service.py:408,419`) **apa pun peran gudangnya**. Buktinya 4 roll `received_transit` di WH-JKT
   (storage). Peran `transit/central_inbound/staging` **tidak dipakai logika mana pun**; yang dipakai hanya `storage`
   (`putaway_order_service.py:62`) dan `return` (`return_journey_service.py`).
4. **Gudang di GRN diabaikan** untuk baris PO: `GrnCreateWizard` menyimpan `grn.warehouse_id`, tetapi `_post_task`
   memanggil `complete_task` dengan gudang **tugas/PO** (`goods_receipt_close_service.py:276–285`). Pilihan di layar
   tidak berpengaruh, yang menyesatkan pengguna.
5. **Label & putaway.**
   * Tahap `received_transit → tag_printed → tag_verified → putaway/cross_dock` (`rfid_print_service.py:21–30`).
   * Putaway Order hanya menerima roll ber-tag RFID aktif (`putaway_order_service.py:98–116,157`). Gudang yang hanya
     memakai label QR **tidak bisa** membuat PA.
   * PA dibuat **manual**; saran tujuan mencari gudang storage di **semua lokasi** (lokasi sama hanya diurutkan duluan),
     dan `create_order` mengizinkan PA lintas lokasi.
6. **"Ada SO menunggu → langsung ke SO, kalau tidak → simpan" belum ada.**
   * Routing saat terima selalu `"store"`; cross-dock hanya manual (`rfid_print_service.set_routing`, tanpa cek SO).
   * Backorder dipenuhi otomatis (`backorder_service.auto_fulfill_backorders`) dari stok entitas di **mana saja**,
     bukan memprioritaskan roll yang baru datang.
7. **Lingkup lokasi pengguna** (`services/location_scope.py`):
   * hanya peran `warehouse` (`SCOPED_ROLES`); berlaku ke tugas WMS, pengiriman, roll, mutasi, GRN, transfer;
   * **celah**: `putaway_orders` tidak tercakup, router PA tidak memanggil `assert_warehouse`, daftar GRN membuat filter
     sendiri (`routers/goods_receipts.py:52`), dan gudang tanpa `site_id` tidak pernah masuk lingkup;
   * **Admin Sales & sales sama sekali tidak sadar lokasi**: SO tidak punya lokasi pemenuhan (grep di sales_orders/so_*/
     fulfillment* = nihil).
8. **Alokasi roll SO** (`roll_service._available_rolls_for_order` 894–923, `_wh_rank_factory` 926–932):
   * peringkat gudang = `warehouse.city` vs `WAREHOUSE_PRIORITY` hard-code (Jakarta/Bandung/Surabaya/Denpasar) terhadap
     **kota pelanggan**, bukan lokasi pengguna/SO;
   * semua gudang RCM-* dan SRG-01 ber-kota "Bandung", sehingga satu SO bisa terpecah Soreang + Rancamalang tanpa
     preferensi;
   * roll yang masih `receiving`/transit (belum dilabel) ikut menjadi kandidat.
9. **"FEFO" sebenarnya FIFO**: `lot_selection: "fefo"` diurutkan dari `min(created_at)` roll per lot. Tidak ada
   tanggal kedaluwarsa. Roll potongan/retur mendapat `created_at` baru sehingga dianggap "muda". Pemilik: **lokasi
   dulu, lalu FIFO** — tanpa FEFO.
10. **Konsep ganda**:
    * `warehouse.city` dan `site.city`;
    * dua arti "putaway" (penempatan ke rak `/inventory/putaway` dan Putaway Order antar gedung);
    * peran `qc` dipakai di kode (`QC_ROLES`) tetapi bukan peran sah; peran **inspeksi tidak ada** (QC berjalan di
      tempat sebagai status karantina).

### Akar masalah
Model lokasi (site + peran) **sudah dibuat sebagai data** (FASE lokasi), tetapi **tidak pernah disambungkan** ke
pembelian, penerimaan, alokasi, maupun penjualan. Setiap jalur menebak gudangnya sendiri, sehingga hasilnya terasa
kacau: transit tanpa arti, gudang GRN diabaikan, gudang nonaktif tetap bisa dipilih, dan alokasi berdasar kota pelanggan.

### Rencana perbaikan (bertahap)
* **P9.1 Data & aturan dasar.**
  * Semua gudang aktif wajib ber-lokasi dan ber-peran. Gudang nonaktif disembunyikan dari pemilih, dan
    `assert_usable` menolaknya.
  * Lokasi tanpa gudang transit (Soreang, Jakarta) diberi peran `transit` pada gudang tunggalnya (atau gudang transit
    baru — [KEPUTUSAN] P9-K1).
  * Tambah peran **`inspection`** bila pemilik ingin gudang/area inspeksi terpisah ([KEPUTUSAN] P9-K2).
* **P9.2 PO/PR ke lokasi.**
  * `ship_to_site_id` di PO, PR, dan Amend.
  * Helper `warehouse_profile_service.receiving_warehouse_for_site(site, entity)` memberi gudang aktif berperan
    `central_inbound/transit` yang boleh dipakai entitas itu.
  * `warehouse_id` tetap disimpan sebagai **turunan**, sehingga tugas WMS/GRN tidak berubah bentuk.
  * Dipakai di PO manual, PR→PO, OD, dan Reorder. Bug `restock_service._default_warehouse` ikut diperbaiki.
  * UI: "Lokasi kirim" menggantikan "Gudang"; gudang transit tampil sebagai info.
* **P9.3 Penerimaan.**
  * Gudang GRN diturunkan dari PO (tidak bisa diganti ke lokasi lain).
  * `journey.stage` diisi sesuai peran gudang.
  * Label QR diterima setara RFID untuk syarat putaway (`label_verified`).
* **P9.4 Keputusan routing otomatis** setelah label/hitung (`putaway_order_service.decide_routing`):
  * ada backorder SO/OD entitas itu untuk produk tersebut → **reservasi roll yang baru datang** (`roll_ids`) dan routing
    `cross_dock` → tugas ambil;
  * selain itu → **draf Putaway Order otomatis** ke gudang storage **di lokasi yang sama** (filter lokasi wajib di
    `suggest/create_order`).
* **P9.5 Lingkup lokasi.**
  * Tambah `putaway_orders` ke `WAREHOUSE_FIELDS`, `assert_warehouse` di router PA/GRN, `narrow` di daftar GRN.
  * Akun Admin Sales mendapat `location_site_ids`.
  * SO mendapat `fulfillment_site_id` (bawaan lokasi pengguna/POS — P8).
* **P9.6 Alokasi.**
  * Urutan: **lokasi SO** → lokasi lain (dengan tanda "perlu transfer") → FIFO berdasar `received_date`.
  * Ganti nama `fefo` → `fifo` (alias untuk konfigurasi lama).
  * Keluarkan roll yang masih receiving/transit-belum-label dan roll di gudang `return` (kecuali permintaan grade).
* **P9.7 Satukan istilah.** "Penempatan rak" vs "Putaway antar gudang" diberi nama berbeda di menu. Kota gudang diambil
  dari lokasi.

### [KEPUTUSAN]
* **P9-K1** — Soreang & Jakarta: tambah gudang transit terpisah, atau gudang tunggal merangkap transit+storage?
* **P9-K2** — Perlu gudang/area **inspeksi** terpisah (roll pindah fisik dari transit → inspeksi → storage), atau
  inspeksi cukup status di gudang transit?
* **P9-K3** — Roll yang sudah ada stage `received_transit` di gudang storage (4 roll WH-JKT): diluruskan otomatis
  menjadi "stored"?
* **P9-K4** — Bila stok lokasi SO kurang tetapi ada di lokasi lain: otomatis ambil (transfer antar lokasi), atau
  Admin Sales memutus?

### Kriteria terima
1. PO dibuat dengan "Lokasi kirim = Rancamalang" → tugas penerimaan di RCM-TRANSIT. Gudang nonaktif tidak bisa dipilih
   (uji API).
2. Terima + label: (a) ada backorder → roll baru langsung tereservasi ke SO itu, routing cross-dock, tugas ambil lahir;
   (b) tanpa backorder → draf PA ke storage Rancamalang (bukan Soreang).
3. Alokasi SO berlokasi Jakarta memilih roll WH-JKT lebih dulu, lalu FIFO (uji unit `roll_service`).
4. Akun gudang Soreang tidak melihat PA/GRN Rancamalang.
5. Reorder SO memakai gudang transit lokasi SO (bukan WH-BDG nonaktif).

---

## P10 — Transfer antar-PT sadar gudang bersama

### Permintaan pemilik
Gudang bisa **dipakai bersama** atau **khusus satu PT**. Transfer antar-PT **di dalam gudang bersama** tidak perlu
pengiriman (cukup ganti pemilik).

### Mekanisme sekarang (bukti)
1. Keputusan pemenuhan "ambil dari PT lain" (`fulfillment_decision_service.options` / `_take_from_other_entity`):
   ketersediaan per PT dihitung dari `inventory_balances` **tanpa** lokasi/berbagi
   (`internal_request_service.availability`).
2. `internal_request_service.convert` membuat pasangan dokumen interco (SO/SJ/Invoice internal penjual + PO/Bill
   internal pembeli). **`preferred_roll_ids` dari dialog pilih roll (E5, 22 Okt) hilang di sini**: disimpan di
   permintaan internal (baris 178), tetapi tidak diteruskan ke `convert` (baris 410–420). Ini sesuai catatan E5
   "pemakaian otomatis di Tugas Gudang penjual belum".
3. "Tugas Gudang" diterbitkan **manual** (`routers/interco.py:190–209` → `interco_service.create_warehouse_task`).
   * Roll dipilih FIFO di semua gudang penjual (`reserve_rolls_for_transfer` tanpa `roll_ids`).
   * `warehouse_transfers` lahir dengan **sumber = tujuan = gudang roll pertama** (`interco_service.py:1605–1615`).
4. ACC transfer (`routers/transfers.py:515–605`) → `execute_ownership_transfer` = **ganti pemilik di tempat**, tanpa
   dispatch/SJ. Lalu backorder SO pembeli dipenuhi otomatis. Tidak ada GRN di sisi pembeli.
5. Pagar `transfer_receipt_service.interco_violations` → `placement_rules`: bila gudang **dedicated** milik PT lain,
   ditolak 409 kecuali pengecualian supervisor.

**Kesimpulan**: untuk gudang **bersama** (semua RCM-*), perilaku "ganti pemilik tanpa kirim" **sebenarnya sudah
terjadi**. Yang salah:
* (a) untuk gudang **dedicated** (WH-JKT milik KSC, SRG-01 milik Kanda) **tidak ada jalur perpindahan fisik**; yang ada
  hanya pengecualian, sehingga stok pembeli tertinggal di gudang khusus penjual;
* (b) tugas gudang manual + FIFO mengabaikan roll pilihan;
* (c) dokumen "Surat Jalan Transfer Antar-PT" tetap ditawarkan untuk kasus gudang bersama.

### Akar masalah
Keputusan "ganti pemilik saja vs kirim fisik" tidak pernah dibuat **per roll berdasar gudang**. Semua transfer
interco dipaksa ke satu jalur (ganti pemilik di tempat).

### Rencana perbaikan
* **P10.1** Di `interco_service.create_warehouse_task`, per roll:
  * `placement_rules.is_usable(gudang roll, PT pembeli)` → **mode ganti pemilik**: diterbitkan **otomatis** saat
    konfirmasi, tanpa SJ, dengan jejak "pindah kepemilikan di <gudang>";
  * selain itu → **mode kirim fisik**: `warehouse_transfers` ber-`interco_pair_id`, tujuan = gudang transit di lokasi SO
    (P9), lewat ambil → SJ transfer → terima (`transfer_receipt_service`). Pemilik berganti **saat diterima**.
* **P10.2** Teruskan `preferred_roll_ids`: convert → item interco → `reserve_rolls_for_transfer(roll_ids=…)`.
* **P10.3** Ketersediaan PT lain dihitung per **lokasi** dan diberi tanda "satu gudang bersama (tanpa kirim)" /
  "perlu kirim dari <lokasi>".
* **P10.4** Transfer `inter_entity` lama dari POS (`routers/transfers.py:303–430`, `CheckoutDrawer.jsx:228`) memakai
  aturan yang sama.

### Kriteria terima
1. SO KSC dipenuhi dari stok CST di RCM-WOVEN (bersama) → pemilik roll berganti otomatis, **tanpa** SJ/dispatch. Roll
   yang dipilih di dialog adalah roll yang berpindah.
2. SO KSC dipenuhi dari stok Kanda di SRG-01 (dedicated) → transfer fisik SRG-01 → transit lokasi SO, dengan SJ dan
   penerimaan. Pemilik berganti saat diterima.
3. Ketersediaan PT lain menampilkan lokasi dan mode.

---

## P11 — Penanda roll: sudah dicek MD Quality? sudah diinspeksi (4-point)? + MD Quality boleh sampling

### Permintaan pemilik
Setiap roll menyimpan status **"sudah dicek MD Quality atau belum"** dan **"sudah diinspeksi atau belum"**.
MD Quality boleh mengecek **sebagian** roll (sampling); sekarang sistem memaksa semua.

### Mekanisme sekarang (bukti)
* **Penanda di roll (`inventory_rolls`)**: tidak ada boolean datar. Status hanya bisa diturunkan dari field bersarang:
  * MD Quality: `inspection.md_quality_at/by` (`qc_inspection_service.record_quality`, ±163–170);
  * 4-point: `inspection.inspected_at/by` + poin/grade (`qc_inspection_service.inspect_roll`).

  `qc_service.roll_inspected()` hanya menghitung 4-point. Status MD/4-point **tidak tampil** di daftar maupun detail roll.
* **Alur sesudah GRN** (sejak E9, 22 Okt):
  1. `purchasing.qc_on_receipt=True` → roll `quarantine` + tugas `qc_pending`.
  2. `inspection_service.ensure_for_qc_task` membuat **SPK MD Quality** (`po_receipt`, `md_only=True`) berisi **semua**
     roll kedatangan.
  3. SPK **QC 4-point** dibuat terpisah (`create_qc_4point`). Bila dibuat dari SPK MD, **semua** roll ikut. Tombol UI
     "Buat SPK QC 4-point" hanya mengirim `inspection_id` (`InspectionDetailPanel.jsx:209–211`). Skema sebenarnya
     mendukung subset `roll_ids`, tetapi UI tidak memakainya.
* **Validasi tutup SPK** (`inspection_service.finish`, baris 1209–1218):
  * semua jenis: minimal **satu** baris diperiksa;
  * **QC 4-point: "SPK QC 4-point: periksa SEMUA roll dulu."** ← inilah "dipaksa semua";
  * random check: semua roll.
* **SPK MD Quality sebenarnya sudah boleh sebagian** (cukup ≥ 1 baris). Saat ditutup, `_release_quarantine`
  (baris ±1126–1192) **menerima semua roll yang tidak ditolak, termasuk yang tidak dicek MD**, dengan grade bawaan "A"
  (baris 1167). Roll yang tidak dicek **tidak ditandai** sebagai "lolos tanpa cek MD".
* `qc_via_sampling` (`qc_service.py:356–362`) menandai roll tanpa 4-point sebagai "sampling", sehingga artinya rancu
  untuk alur MD-only.
* `inspection_service` baris ±911: bagian MD juga mengisi `inspected_at` baris, sehingga ringkasan "inspected"
  mencampur MD dan QC.
* **Pengaturan sampling**: hanya per tugas `wms_tasks.qc_plan` (all / sampling pct+min / none; `QcPlanPanel.jsx`) dan
  hanya untuk 4-point. Tidak ada kunci global `qc.sampling_*`; untuk MD tidak ada sama sekali (`config_catalog_core.py`
  grup `qc.*`).

### Akar masalah
1. Tidak ada **atribut roll** yang eksplisit. Status pemeriksaan tersebar di SPK dan field bersarang, sehingga pemilik
   tidak bisa melihat atau menyaring "roll mana yang belum dicek".
2. SPK 4-point dirancang "satu kedatangan = semua roll" (pembuatan dan penutupan).
3. Sampling MD tidak dimodelkan, jadi sistem tidak bisa membedakan "dicek dan lolos" dari "lolos tanpa dicek".

### Rencana perbaikan
* **P11.1 Flag datar di roll + backfill + indeks**: `md_quality_checked` (bool, `_at`, `_by`, `_spk`),
  `inspected_4point` (bool, `_at`, `_spk`), `md_quality_via_sampling` ({spk, checked, total}).
  * Ditulis di `record_quality`, `inspect_roll`, dan `_release_quarantine`.
  * Backfill dari `inspection.md_quality_at` dan `inspection.inspected_at`.
* **P11.2 SPK 4-point bisa sebagian**: modal "pilih roll" saat membuat SPK (subset dari SPK MD/kedatangan).
  * `finish` 4-point = semua baris **di SPK itu**; atau ikut rencana sampling `qc.sampling_pct/min` (kunci baru).
  * Roll yang tidak dicek **dikeluarkan dari SPK**, bukan diluluskan.
* **P11.3 Sampling MD**: kunci `qc.md_sampling_pct/min` (bawaan 0 = bebas, minimal 1), dengan indikator
  "x/y roll dicek (wajib n)" di SPK MD.
  * Saat ditutup, roll yang tidak dicek ditandai `md_quality_via_sampling`.
  * Ganti makna `qc_via_sampling` → `four_point_pending`.
* **P11.4 UI**:
  * chip **MDQ ✓ / MDQ sampling / belum** dan **4-pt ✓ / belum** di daftar roll, detail roll, baris SPK, pilih roll SO,
    dan Lokasi Rak;
  * filter stok "belum MDQ" / "belum 4-point".

### Kriteria terima
1. SPK MD dengan 10 roll, 2 dicek → bisa ditutup. 2 roll = `md_quality_checked`, 8 roll = `md_quality_via_sampling`.
   Semua lepas karantina.
2. SPK 4-point untuk 3 dari 10 roll → bisa dibuat dan ditutup setelah 3 roll dicek.
3. Setiap roll menampilkan dua status yang benar. Filter stok berfungsi (uji API + UI).
4. Regresi: uji inspeksi backend & `f14SpkOneDecision` tetap hijau.

---

## P12 — Sorotan POS (Terlaris / Push / Rekomendasi) bisa dinyalakan & dimatikan

### Mekanisme sekarang (bukti)
* **Terlaris**: `PosBestSellers` → `GET /pos/best-sellers` (`routers/pos.py:18–26`) → `pos_recommendation_service`
  (baris 45–72).
  * Urutan: jumlah order, lalu qty, lalu nilai, dari **seluruh riwayat** SO tidak batal (batas 8.000 dokumen) — **tanpa
    jendela waktu**.
  * `_enrich` (baris 25–42) tidak menyaring produk nonaktif / belum boleh dipesan / eksklusif pihak lain; query N+1.
* **Sering dibeli pelanggan ini**: `ReorderStrip` (EPIC5, `SalesPortal.jsx:191`) — muncul bila pelanggan dipilih.
* **FBT** (sering dibeli bersama): hanya di keranjang HP (`MobileCart.jsx:96`).
* **Push/unggulan**: **tidak ada** (grep `is_featured|featured|unggulan|push_product` = nihil).
* **Pengaturan nyala/mati: tidak ada** (tidak ada kunci `pos.*` di `config_catalog_core.py`).

### Rencana perbaikan
* **P12.1 Kunci konfigurasi** (Pusat Pengaturan, per PT): `pos.best_sellers.enabled/window_days/limit`,
  `pos.reorder.enabled`, `pos.fbt.enabled`, `pos.featured.enabled`.
* **P12.2 Terlaris**: jendela waktu (bawaan 90 hari), saring visibilitas (aktif, orderable, eksklusif — P1.3), dan
  hilangkan N+1.
* **P12.3 Produk Push/Unggulan**: field produk `is_featured`, `featured_rank`, `featured_until`, `featured_note` (diatur
  MD/Manajer di master produk), endpoint `/pos/featured`, strip **"Produk Unggulan"** di POS desktop & HP.
* **P12.4 Rekomendasi**: [KEPUTUSAN] P12-K1. Pilihan arti:
  * (a) "Sering dibeli pelanggan ini" (sudah ada);
  * (b) rekomendasi per pelanggan berbasis desain/kategori yang pernah dibeli (memakai P6);
  * (c) daftar manual.

### Kriteria terima
1. Admin mematikan Terlaris → strip hilang di desktop & HP tanpa deploy.
2. Terlaris hanya menghitung N hari terakhir dan tidak pernah menampilkan produk yang tidak boleh dipesan pelanggan
   aktif.
3. Produk unggulan tampil sampai `featured_until`.

---

## P13 — Keep & Pending juga terlihat oleh sales (hanya SO miliknya)

### Temuan: **SUDAH ADA** — perlu dibuktikan di UI, bukan dibangun ulang
* Endpoint `GET /sales/keep-pending` (`routers/sales_p04.py:15–23`): menerima izin `order.view` dan memakai
  `sales_ownership.apply_scope`. Untuk peran **sales**, hasilnya hanya SO yang `created_by` / `sales_id` /
  `sales_team.sales_id` = dirinya (`services/sales_ownership.py`, keputusan pemilik E8.10).
* Panel yang sama (`KeepPendingPanel`) dipasang di:
  * **Beranda Sales desktop** (`features/home/SalesHome.jsx:258`, `testPrefix="sales-kp"`);
  * **Beranda HP sales** (`MobileSalesHome.jsx:204`);
  * Meja Admin Sales (desktop & HP).

  Riwayat: L02 LN-020-T02, `f8eb33d` (Keep & Pending di HP), E7 (cari & filter).

### Dibuktikan di UAT (23 Okt, API `GET /sales/keep-pending`, entitas KSC)
| Akun | Keep | Pending | SO unik |
|---|---|---|---|
| `salesadmin@` (Admin Sales) | 1 (KSC/SO-00008) | 1 | 1 |
| `sales2@` (Bima) | 0 | 0 | 0 |

KSC/SO-00008 (Butik Bali Indah, `waiting_stock`) dibuat oleh akun **admin** (`created_by=user_admin_01`, `sales_name`
"Budi Santoso" = nama admin), dengan `sales_id` **kosong** dan `sales_team` kosong. SO ini **tidak dimiliki sales mana
pun**, sehingga tidak muncul di Keep & Pending sales mana pun. Pembatasan sudah bekerja; yang bermasalah datanya.

### Penyebab pemilik tidak melihatnya
1. Panel ada di **Beranda** sales, bukan di menu Meja Admin Sales.
2. **SO yang dibuat admin/Admin Sales tidak mewarisi sales pelanggan** (pelanggan Butik Bali Indah sendiri juga belum
   punya sales, lihat P14). Akibatnya panel sales kosong dan terlihat seperti fitur belum ada. Ini terhubung dengan
   P14.2: pelanggan wajib punya sales, dan SO yang dibuat atas nama pelanggan mewarisi `sales_team` pelanggan
   (`customer_service` baris ±84 sudah punya fungsi pewarisan — perlu dipastikan dipanggil di semua jalur pembuatan
   SO, termasuk konversi OD).

### Rencana
* **P13.1 Verifikasi UI** dengan `sales2@` di UAT (desktop & HP): tangkapan layar Keep & Pending di Beranda, isi =
  hanya SO milik Bima.
* **P13.2** Bila SO yang dibuat Admin Sales "atas nama" sales tidak membawa `sales_id`, perbaiki di jalur pembuatan.
* **P13.3** Tautan "Keep & Pending" di menu sales (bukan hanya kartu di Beranda), supaya mudah ditemukan.

### Kriteria terima
Akun sales melihat Keep/Pending/Dalam Perjalanan hanya untuk SO miliknya, di desktop dan HP. Bukti tangkapan layar di
`hasil/`.

---

## P14 — Sales hanya melihat pelanggannya sendiri

### Mekanisme sekarang (bukti)
* Aturan baris (row-level) **sudah ada**: `customer_service.scope_query` (±baris 379–382). Untuk peran sales,
  `assigned_sales_id = user.id`. Pelanggan baru buatan sales otomatis milik pembuatnya (`routers/customers.py:96–100`).
* **Tetapi** `routers/customers.py:35–40`: `if for_order and role_in(role, ("sales",))` mengembalikan **SEMUA
  pelanggan entitas** (tanpa data kredit). Pengecualian ini dipakai oleh:
  * form Pesanan Khusus (`CreateSpecialOrderForm.jsx:43`);
  * harga khusus HP (`MobileFieldViews.jsx:16`);
  * POS HP (`MobileSalesNative.jsx:127`);
  * katalog sampel (`CatalogueCreateModal.jsx:25`).

  Komentar di `MobileFieldViews.jsx:14–15` menjelaskan alasannya (cek UI UAT v3 S4): agar pelanggan **tanpa sales**
  (Toko Kain Sejahtera) tetap bisa dipilih.
* **Data UAT**: KSC punya 4 pelanggan, dan **3 tanpa sales** (Toko Kain Sejahtera, Butik Bali Indah, Moda Surabaya
  Fashion). `sales@` (Ayu Marketing) **tidak punya pelanggan sama sekali**.

### Riwayat
* Aturan pemilik: KN_17 "Sales hanya mengelola customer miliknya"; keputusan E8.10 (tertulis di kepala
  `services/sales_ownership.py`).
* Pengecualian `for_order` masuk lewat commit **`b9135ff`** ("checkpoint before testing_agent_full_stack", lingkungan
  Emergent) **tanpa keputusan pemilik yang tercatat**. Cek UI UAT v3 S4 lalu memperluasnya ke form harga khusus HP.
* Pemilih pelanggan HP (`MobileCustomerBar`, E2 22 Okt) mengambil daftar dari `/dashboard`, yang memotong pelanggan
  di **100** (`routers/dashboard.py:53` `to_list(100)`) dan hanya bercakupan entitas, **bukan** milik sales.

### Akar masalah
Celah sengaja `for_order` dibuat untuk menambal **data pelanggan yang belum punya sales**. Akibatnya aturan pemilik
("sales mengurus pelanggannya sendiri", E8.10) bocor di semua pemilih pelanggan untuk pesanan. Ini contoh perbaikan
yang menambal gejala (data) dengan melonggarkan aturan.

### Rencana perbaikan
* **P14.1** Hapus pengecualian `for_order` untuk sales: pemilih pelanggan = `scope_query` (milik sendiri + tim
  `sales_team`).
* **P14.2** Pelanggan tanpa sales:
  * Admin Sales/Manajer **wajib menetapkan** sales;
  * laporan "Pelanggan tanpa sales" di meja Admin Sales;
  * data UAT: tetapkan 3 pelanggan KSC ke sales ([KEPUTUSAN] P14-K1 — ke siapa).
* **P14.3** Sales membuat pelanggan baru dari POS/HP (sudah ada, otomatis miliknya). Pastikan tersedia di titik masuk
  katalog (P8).
* **P14.4** Pelanggan walk-in/umum: [KEPUTUSAN] P14-K2 — apakah ada pelanggan "Umum/Walk-in" yang boleh dipakai semua
  sales?

### Kriteria terima
1. `sales2@` di semua pemilih pelanggan (POS desktop/HP, OD, harga khusus, sampel) hanya melihat pelanggan miliknya
   (uji API untuk tiap pemanggil `for_order`).
2. `sales@` tanpa pelanggan → daftar kosong + tombol "Pelanggan baru".
3. Meja Admin Sales menampilkan antrean "Pelanggan tanpa sales".

---

## P15 — Gabung beberapa PR (supplier sama) menjadi 1 PO + rekomendasi untuk MD

### Permintaan pemilik
Beberapa PR untuk supplier yang sama bisa **digabung menjadi satu PO**, dengan **rekomendasi** yang membantu MD melihat
PR mana yang bisa digabung.

**Riwayat**: permintaan ini **tidak tercatat** di dokumen mana pun sebelumnya (memo 7 Okt, IMP-xx, register 126,
catatan trial). Bila pernah disampaikan, hilangnya terjadi saat pencatatan.

### Mekanisme sekarang (bukti)
* **PR** (`purchase_requisitions`, `purchase_requisition_service.create_requisition`):
  * supplier hanya di **header** (`preferred_supplier_id`);
  * satu `warehouse_id` dan satu `entity_id` per PR;
  * baris punya `fulfillment_mode`, `realized_qty`, `realizations[]`.
* **Realisasi**: `convert-to-po` dan `realize-po` (`routers/purchase_requisitions.py:194,234`) sama-sama memanggil
  `pr_sourcing_service.realize_to_po` (baris 346–579). Hasilnya **satu PR → satu PO** per panggilan. Satu PR bisa
  dipecah ke beberapa PO (`line_nos`), tetapi **beberapa PR tidak pernah bisa ke satu PO**.
* Tautan PO → PR **skalar**: `pr_id/pr_number/source_pr_id`. Baris PO hanya `pr_line_no` tanpa `pr_id`. Konsumen
  `pr_id` skalar: `doc_refs_service`, `po_board_service`, `po_origin_from_pr`, klaim atomik per PR.
* UI `PurchaseRequisitions.jsx` / `PurchaseRequisitionDetailPanel.jsx`: tidak ada multi-pilih atau aksi gabung.
* **OD**: `special_order_fulfillment.realize_all` membuat **satu PR per item** (`ensure_pr`), langsung auto-approve,
  lalu langsung PO. OD 3 item ke supplier yang sama menghasilkan **3 PO**.
* **Bug tambahan**: `_realize_po` (`special_order_fulfillment.py:485`) mencari `r.get("kind")`, padahal
  `pr_sourcing_service._record` (baris 245) menulis `"type"`. Fallback "PO lama dari realisasi PR" tidak pernah cocok,
  sehingga berisiko membuat PO ganda saat diulang.
* Data pembantu sudah ada: `GET /purchase-requisitions/eligible-suppliers` (`by_product`, `common`).

### Kendala penggabungan
* PO hanya punya satu `entity_id`, satu `warehouse_id`, dan mata uang ikut badan usaha. Gabungan wajib sama
  ketiganya. Setelah P9, `warehouse_id` → **site/lokasi tujuan**, sehingga gabungan antar-gudang dalam satu lokasi
  menjadi mungkin.
* **KN-B15**: satu produk = satu baris PO (`po_line_guard`). SKU sama dari PR berbeda harus dilebur ke satu baris
  dengan alokasi per PR.
* PO lintas OD akan merusak `special_order_id` skalar (`mark_ready_if_all_received`, hook QC, `_fix_po_price`).

### Rencana perbaikan
* **P15.1** `realize_many_to_po(pr_refs=[{pr_id, line_nos}], supplier_id, destination, …)`:
  * validasi entitas/tujuan/supplier sama dan semua PR approved;
  * klaim atomik semua PR (lepas semua bila gagal);
  * lebur baris per `product_id` dengan `pr_allocations[]`;
  * header `pr_ids[]/pr_numbers[]`; `pr_id` = PR pertama (kompatibel);
  * `_record` per PR = qty alokasinya; `doc_refs` ke setiap PR.

  `realize_to_po` lama menjadi kasus satu PR.
* **P15.2 Rekomendasi** `GET /purchase-requisitions/merge-suggestions`:
  * kelompok PR approved yang punya baris purchase terbuka per (entitas, lokasi tujuan, supplier);
  * supplier diambil dari `preferred_supplier_id`, atau dari `eligible-suppliers.common` bila kosong;
  * skor: jumlah PR, nilai, rentang `needed_by_date`, hemat biaya kirim/MOQ bila ada.
* **P15.3 UI**:
  * centang multi-PR di daftar (status approved) + aksi **"Gabung ke 1 PO"**;
  * panel **"Saran gabung"** di Meja MD/Purchasing;
  * pratinjau baris hasil lebur sebelum PO dibuat.
* **P15.4 OD**: fase 1 — gabung **dalam satu OD** (item dengan supplier sama → 1 PO); `special_order_item_keys[]` dan
  `mark_ready` membaca array. PR OD lintas OD tidak digabung. Perbaiki bug `kind`/`type`.

### Kriteria terima
1. Dua PR approved (supplier & lokasi sama) → 1 PO; SKU kembar = 1 baris beralokasi. Kedua PR mencatat realisasi ke PO
   itu dan tampil di papan PO & Jejak Dokumen.
2. PR beda entitas/lokasi → ditolak dengan pesan jelas.
3. OD 2 item supplier sama → 1 PO; OD tetap "Siap" setelah PO diterima.
4. Panel saran menampilkan kelompok yang benar (uji API dengan data buatan).

---

## P16 — UI rusak / tidak konsisten

### P16.1 Langkah GRN (Surat jalan · Hitung roll · Rekonsiliasi) "tanpa CSS"
**Temuan**: bukan class yang tidak terdefinisi. Pindai semua `className` di `features/wms/grn/*.jsx` terhadap seluruh
`*.css` + Tailwind = **0 class hilang**. Masalahnya, layar disusun tanpa wadah design-system:
* Detail GRN dirender tanpa kartu (`GoodsReceiptsView.jsx:53` hanya `<div className="p-4 pb-28 lg:p-0">`).
* Panel tanpa latar putih di atas latar halaman abu-abu: `GrnCountPanel.jsx:34` (kartu baris hitung tanpa `bg-white`),
  `GrnReconPanel.jsx:44`, `GrnReviewPanel.jsx:30,117`.
* Tab langkah = pil buatan sendiri (`GrnDetail.jsx:65–69`), bukan `tab-bar/tab-button` standar.
* Tabel `<table>` mentah (`GrnReconPanel.jsx:45`, `GrnReviewPanel.jsx:118`), bukan `.table-wrap` + `.data-table`.
* Input `inputCls` 12px buatan sendiri (`GrnBits.jsx:48`), bukan `.field`. Banyak teks 9,5–11px.
* **Responsif rusak di langkah Hitung**: `GrnCountPanel.jsx:57` `grid-cols-4/5/6` tanpa breakpoint, dan input tanpa
  label (hanya placeholder). Di HP kolom ±50px.

**Rencana**: kartu `section-card` + `section-head` ("Langkah 1/2/3" + judul), `tab-bar` standar, `data-table`, `.field`
berlabel, grid `grid-cols-2 sm:grid-cols-n`.
**Terima**: tiga langkah tampil dalam kartu putih dengan tab standar. Lebar 375px → maks 2 kolom berlabel. Audit
tata letak CDP (tanpa gulir samping/tumpang tindih) lulus di desktop & HP.

Catatan sampingan — class yang benar-benar tidak terdefinisi di tempat lain: `guided-panel`
(`components/GuidedActionPanel.jsx:14`), `sidebar-zone`, `fav-star` (`CoreWidgets.jsx`), `print-area`
(`logistics/ManifestPanel.jsx:23`), `cfg-row-picked` (`settings/config/ImpactPicker.jsx:192`), `tanya-table/chart/gallery`.

### P16.2 Pusat Dokumen / Jejak Dokumen: unduh langsung
* Tab "Daftar Dokumen" (`features/documents/DocumentCenter.jsx`) **sudah** punya Pratinjau & Unduh PDF per baris
  (baris 84–99, 179–182), tetapi hanya untuk jenis di `DOC_REGISTRY` (`pdf_resolvers.py:1056–1085`).
* Tab "Jejak Dokumen" (`documents/trace/DocTraceView.jsx`, `TraceGraph.jsx:22–37`) **tidak punya** unduh per dokumen:
  kartu node hanya "jadikan jangkar" dan "Buka dokumen" (pindah layar). "Cetak Jejak (PDF)" mencetak peta relasinya,
  bukan dokumennya. Node sudah membawa `doc_type/doc_id`.
* **Jenis jejak tanpa PDF**: kontrak supplier, GRN baru (`goods_receipts`), tugas ambil, pengiriman (ada HTML
  `/shipments/{id}/surat-jalan` tetapi tidak terdaftar), amandemen, nota kredit, rencana bayar, denda, selisih bayar,
  transaksi/settlement interco, faktur pajak masukan, spesifikasi & **sampel R&D** (P3), kasus finance, kas, permintaan
  internal, pinjaman interco, permintaan desain, jurnal.
* **BUG**: resolver PDF `goods_receipt` (`pdf_resolvers.py:1075`) membaca koleksi **`purchase_orders`** (bukti terima
  per PO, alur lama), sedangkan jenis jejak `goods_receipt` = koleksi `goods_receipts` (GRN baru). Akibatnya:
  * GRN baru **tidak punya PDF**;
  * tautan "N surat" dari baris goods_receipt di Pusat Dokumen membawa id PO ke jejak GRN, sehingga salah/tidak
    ditemukan.

**Rencana**:
* peta jejak → PDF (`pdf_doc_type` di `_T(...)` `doc_refs_service`);
* tombol Pratinjau/Unduh di kartu node (logika dipindah ke `documents/pdfActions.js`);
* `goods_receipt` lama diganti nama `po_receipt` + resolver GRN baru;
* resolver bertahap untuk nota kredit, rencana bayar, denda, kontrak, sampel R&D (P3.1), perbaikan (P7);
* opsional "Unduh semua (ZIP)".

**Terima**: setiap node yang jenisnya punya resolver bisa dipratinjau/diunduh tanpa pindah layar; node lain tertulis
"belum bisa dicetak". PDF GRN baru bisa diunduh.

### P16.3 Pengaturan berantakan
* **Satu menu, 20 tab + 1 alias** (`config/hubTabs.js:216–243`), navigasi sampai **4 lapis**: Pusat Pengaturan 6 tab
  dalam × 23 kelompok (`config_registry.py:60–125`), Entitas & Akses 5 tab, Master per BU 10 jenis, Penjadwal 3 tab,
  Penerimaan & OCR 4 tab.
* **BUG label seksi dobel**: `rnd-divisions` (`hubTabs.js:242`) ber-seksi "Organisasi & Akses" tetapi letaknya sesudah
  SDM. `HubTabs.jsx:20–25` hanya mengelompokkan tab berurutan, sehingga label seksi muncul dua kali dan `key` React
  dobel.
* **Konsep di banyak tempat**: Persetujuan (4 tempat), Kebijakan Retur (3), Rate Insentif (3), Template dokumen (5),
  Satuan (3), Tahap proses (3).
* **Salah tempat**: seksi "Sistem" mencampur aturan bisnis + integrasi AI/WA/audit. Pusat Pengaturan memuat aksi
  operasional (Kunci Saga, Kebersihan Data, Koreksi Harga). "Master per BU" mencampur kebijakan, master, dan dokumen.
* Halaman sangat panjang: `SettingsHub.jsx` 518 baris, `EntityMastersView.jsx` 519, `AdminView.jsx` 560.

**Rencana (satu konsep = satu rumah)**:
1. Perusahaan & Akun
2. Persetujuan (satu halaman lintas domain)
3. Kebijakan per domain: Penjualan · Gudang & Mutu · Pembelian & Produksi · Keuangan & Pajak · SDM · R&D
4. Master Data (indeks ke master domain)
5. Dokumen & Cetak (satu Template Dokumen)
6. Notifikasi & Penjadwal
7. Integrasi & Sistem (admin)

Koreksi Harga dipindah ke Produk & Harga. Usulan ini disajikan ke pemilik **sebelum** dipindah ([KEPUTUSAN] P16-K1),
karena memindah menu mengubah kebiasaan pengguna.

**Terima**: setiap konsep hanya dicapai dari satu tempat; tidak ada label seksi dobel; uji navigasi
(`access_nav_fixture`) hijau.

### P16.4 Sapuan konsistensi
Jalankan audit tata letak CDP (`audit`) di semua layar utama desktop + HP dengan akun tiap peran. Hasil (gulir samping,
teks terpotong, tumpang tindih, kelas tak terdefinisi) masuk daftar perbaikan F5.

---

## P17 — Semua foto yang diunggah bisa dipratinjau tanpa unduh

### Mekanisme sekarang (bukti)
* **Tidak ada komponen bersama.** Yang mendekati: `useProofBlob` + `ProofImage` (`features/rnd/ProofImage.jsx:18–50`,
  memuat blob lewat axios dengan `X-Entity-Id`), `ProofLightbox` yang tidak diekspor (`SampleProofGallery.jsx:14`), dan
  `DeliveryPhoto` (duplikat logika).
* **Akar teknis**:
  * sesi memakai cookie, tetapi badan usaha ditentukan header `X-Entity-Id` (`entity_scope.py:373`). Tautan `<a href>` /
    `<img src>` polos ke berkas PT lain mendapat **403**;
  * lampiran **retur** dikirim `Content-Disposition: attachment`, sehingga klik selalu **mengunduh**
    (`routers/sales_returns.py:1168`, `services/return_attachment_service.py:46–47`).
* **Tempat foto tidak bisa dipratinjau**:
  1. lampiran retur jual (`ReturnDetail.jsx:310`, chip nama → unduh);
  2. foto per roll retur (`ReturnRollsPanel.jsx:34` "Foto 1" → unduh; dipakai juga retur beli & antar-PT);
  3. foto disposisi BS (`ReturnDispositionPanel.jsx:99–100`);
  4. pemilih foto klaim roll tanpa thumbnail (`ReturnRollClaims.jsx:31–36`);
  5. retur di HP hanya angka "N lampiran" (`MobileMdViews.jsx:334`, `MobileSalesFlows.jsx:433,438`);
  6. bukti persetujuan SO (`SoApprovalsPanel.jsx:164`) — tautan teks dengan **token di URL `?auth=`**
     (**celah keamanan**: token terekam di riwayat/log);
  7. lampiran harga khusus (`PriceApprovalCard.jsx:110–118`, `PriceApprovals.jsx:219–221`) — blob di tab baru, tanpa
     thumbnail;
  8. foto pengiriman (`DeliveryDetailModal.jsx:234`) — thumbnail tidak bisa diperbesar;
  9. thumbnail yang dibuka sebagai URL mentah di tab baru (rawan 403): `SpecialOrderChainPanel.jsx:135`,
     `SpecialOrderCustomerApprovalPanel.jsx:162`, `PostDetailModal.jsx:149`, `SampleRoundList.jsx:148`,
     `FilesPanel.jsx:72`, `RoundsTimeline.jsx:66`; `<img src>` polos di `ReferenceGallery.jsx:35–36`,
     `ColorwaysPanel.jsx:60–61`;
  10. thumbnail referensi OD di HP tidak bisa diklik (`MobileSalesFlows.jsx:400–405`).

### Rencana perbaikan
* **P17.1 Komponen bersama** `components/AttachmentThumb.jsx` + `components/MediaLightbox.jsx`:
  * blob lewat axios (header entitas), gambar/video/PDF;
  * navigasi ←/→, perbesar, tombol **"Unduh asli"** eksplisit;
  * `useProofBlob` dipindah ke `hooks/`. Pasang di titik 1–10.
* **P17.2 Backend**: lampiran retur `inline` untuk `image/*` & `video/*` (`attachment` hanya bila `?download=1`). Hapus
  `?auth=` di persetujuan SO/harga khusus; muat lewat blob.
* **P17.3** Uji Jest komponen + sapuan grep: tidak ada `href` lampiran mentah tersisa.

### Kriteria terima
Setiap foto tampil sebagai thumbnail; klik membuka lightbox di halaman yang sama (desktop & HP, juga di PT non-home)
tanpa unduhan. Unduh hanya lewat tombol. Tidak ada token di URL.
