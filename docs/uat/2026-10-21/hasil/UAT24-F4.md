# UAT 24 Okt — F4 (komersial: P2 harga Pesanan Khusus · P15 gabung PR → 1 PO)

- Commit: `272575a` · branch `main`.
- Sumber: [`ANALISIS_TEMUAN_UAT_23OKT.md`](../ANALISIS_TEMUAN_UAT_23OKT.md) P2, P15; keputusan pemilik = usulan bawaan §4
  (P2-K1 kunci harga oleh Admin Sales — bukan sales; P2-K2 tanpa ambang nego otomatis, semua ke Manajer; P2-K3 lantai
  nego = harga kontrak; P2-K4 harga Grade A induk apa adanya, di bawah biaya → peringatan rugi ke Manajer).
- **DB UAT `kn_uat_23okt`**: tidak perlu migrasi data; izin baru `od_pricing` terpasang otomatis saat backend start
  (backend & frontend UAT sudah di-restart).

## Perubahan perilaku (sebelum → sesudah)
### P2 — harga Pesanan Khusus (arahan pemilik SO-12 yang dulu hilang)
* Harga = kontrak supplier × (1 + margin) untuk semua item → **dasar harga per item**:
  * item dari **induk produk** → **harga jual Grade A induk** lewat rantai harga yang sudah ada (harga pelanggan → PT →
    global). Acuan: SKU induk yang dipilih bila Grade A; else Grade A sekeluarga berwarna sama; else Grade A sekeluarga
    berharga tertinggi (SKU hasil OD lain tidak dipakai). Satuan dikonversi ke satuan dasar SKU hasil;
  * item **tanpa induk** → harga **diisi PIC Special Order** (izin baru `od_pricing.set_price`, tombol "Simpan harga
    PIC" atau langsung saat kunci). Bila belum diisi, usulan kontrak + margin tampil dan **dikonfirmasi PIC saat
    mengunci** (pengunci tanpa hak itu ditolak).
  * kontrak + margin tinggal **pembanding laba**; harga di bawah kontrak tidak diblokir tetapi Manajer menerima
    notifikasi "Harga … di bawah biaya kontrak".
* Kunci harga: sales/Admin Sales/Manajer/Admin + PR/PO otomatis → **izin `od_pricing.lock`** (bawaan Admin Sales,
  Manajer, Admin), **tanpa pengadaan otomatis** (`auto_po` bawaan mati), dan **SO selalu lahir saat kunci** (backorder;
  SKU eksklusif OD itu dikecualikan dari gerbang "belum dirilis", SKU nonaktif tetap ditolak). Gagal membuat SO → harga
  tetap terkunci, galat tercatat, tombol konversi SO tetap ada.
* Nego: tidak ada jendela sebelum PO → panel OD menampilkan **"Harga nego · SO …"** per baris SO dengan tombol **Ajukan
  harga nego** (mekanisme harga khusus SO yang sama, diputus Manajer di Pusat Persetujuan; pengaju tidak bisa memutus).
  * baris dituju lewat `special_order_item_id` — dua item OD ber-SKU sama tidak lagi tertukar (juga kunci pengajuan
    ulang & penggantian pengajuan lama);
  * **lantai = harga kontrak** per satuan baris; pesan penolakan tidak menyebut angka biaya untuk peran tanpa hak lihat;
  * **ACC** → harga baris SO, rincian harga OD (`negotiated`, total OD) dan harga SKU eksklusif ikut berubah; SO OD tidak
    dilepas otomatis ke gudang (barang belum ada);
  * **Tolak** → "Lanjut harga normal" (harga OD tetap) atau ajukan harga lain.
* **Gerbang pengadaan**: realisasi pengadaan (Realisasi pengadaan, per item di panel Pemenuhan, Buat PR) ditolak selama
  nego **menunggu Manajer** atau **ditolak dan belum dijawab** sales.
* **Biaya tersembunyi**: biaya kontrak, margin, supplier, nomor kontrak, pembanding, tanda rugi dibuang dari semua respons
  `/api/special-orders/*` dan dari baris SO hasil OD untuk peran tanpa `od_pricing.view_cost` (bawaan Admin Sales,
  Manajer, Admin, MD) — satu titik saring (middleware), sama seperti visibilitas grade/LOT.

### P15 — gabung PR → 1 PO
* Satu PR → satu PO → **beberapa PR (badan usaha, lokasi tujuan & supplier sama) → satu PO**; SKU kembar dilebur jadi
  satu baris dengan `pr_allocations[]`; tiap PR mencatat realisasi sebesar bagiannya, berstatus "Jadi PO", tertaut di
  Jejak Dokumen. PR beda lokasi/PT/supplier ditolak dengan pesan jelas; klaim semua PR atomik.
* Daftar PR: centang multi-PR + bilah "Gabung ke 1 PO" + pratinjau baris hasil lebur; panel **"Saran gabung PR → 1 PO"**
  (kelompok per supplier preferensi/supplier layak untuk semua barang × lokasi, est. nilai, rentang tanggal butuh, tanda
  SKU sama). MD melihat saran dengan catatan "teruskan ke Purchasing" (membuat PO tetap hak `purchase_order.create`,
  sama dengan konversi PR tunggal).
* **P15.4 OD**: item satu Pesanan Khusus dengan supplier sama → **satu PO** (harga tiap baris = kontrak pemenang item itu,
  `special_order_item_keys[]`); PO gabungan dibatalkan dari panel Pemenuhan → semua item PO itu kembali "direncanakan";
  batal SATU item OD yang PO-nya dipakai item lain ditolak sebelum apa pun diubah.

## Bukti
* `test_uat24_f4.py` **6 lulus**: 2 PR → 1 PO (SKU kembar 1 baris, alokasi per PR, Jejak Dokumen), PR beda lokasi/PT
  ditolak tanpa kunci tertinggal, saran gabung; P2 — harga Grade A induk lewat rantai harga pelanggan, item tanpa induk
  diisi PIC (sales 403), kunci oleh Admin Sales (sales 403) → SO lahir tanpa PR/PO, sales tidak menerima kunci biaya di
  detail OD/pricing/pemenuhan/SO; nego di bawah kontrak ditolak tanpa angka biaya; nego pending → pengadaan 400 "Nego";
  ACC → baris SO, rincian OD, total OD, harga SKU berubah, lalu pengadaan **1 PO** untuk 2 item supplier sama berharga
  kontrak; tolak → "lanjut harga normal" (harga OD tetap) → nego ulang item kedua (SKU sama dengan item pertama) hanya
  mengubah baris itu.
* Uji fokus OD/PR/harga khusus (10 berkas: F4, FE-01 ×4, iter105, LN-022, F-09, LN-033 ×2) **57 lulus**. Jest `uat24F4`
  3 lulus; Jest penuh **36 suite / 153 uji lulus**; ESLint 0 error.
* **Regresi** 68 berkas uji OD/PR/PO/persetujuan, DB klon identik, baseline `a75e915` vs kode F4: **8 gagal baru, 2 pulih**.
  * 7 uji FE-01 menyandi aturan lama "SO hanya lewat Konversi" → kini SO lahir saat kunci (helper `_so` memakai SO yang
    sudah ada, konversi manual hanya bila belum ada). Uji FE-01 multi-item memakai item tanpa induk supaya tetap menguji
    mekanika harga per item.
  * 1 (`test_trial_22okt_flow` E5) bergantung data, tetapi menyingkap **bug nyata**: pemilih roll di rencana pemenuhan
    menampilkan sisa roll penuh walau sebagian sudah dicadangkan pesanan lain → Admin Sales memilih qty yang ditolak
    "melebihi panjang bebas". Kini daftar memakai **panjang bebas** (roll habis dicadangkan tidak ditampilkan).
  * Pulih: `iter105` konversi PR→PO (data uji diperbaiki), `iter313` cookie login (tidak terkait).
  * 168 gagal / 166 error lain **sudah ada di baseline** (data acuan iter46/47/49, f0b, g1/g2 audit, dsb.).
* UI (DB simulasi `kn_uat_sim`, akun peran):
  * Admin Sales — OD 2 item: "Harga Grade A induk · acuan KNWVN0042-L-0352-XA" Rp 19.000/yd dan item tanpa induk "Usulan
    kontrak + margin" dengan kolom kontrak/pembanding + isian PIC; isi Rp 23.500 → **Kunci harga & buat SO** → SO
    KSC/SO-00014 lahir, "Pengadaan belum direalisasi", tombol **Ajukan harga nego** per baris.
  * Sales (Bima) — tabel tanpa kolom kontrak/supplier, ajukan nego Rp 21.000 → "Menunggu Manajer" + "Nego harga belum
    diputus Manajer — pengadaan menunggu"; entri muncul di antrean Manajer; sesudah ACC: "Harga nego (ACC Manajer) ·
    nego dari Rp 23.500", total OD Rp 8.220.000.
  * MD — panel "Saran gabung PR → 1 PO: PT Benang Sejahtera Abadi → Jakarta · 2 PR · ada SKU sama" dengan catatan
    "Teruskan ke Purchasing"; Admin → **Gabung kelompok ini → Buat 1 PO** → KSC/PO-00003 (baris lebur 350 kg = 150 + 200,
    `pr_allocations` per PR), kedua PR "Jadi PO".
* UAT (sesudah restart): `salesadmin@` memegang `od_pricing` lock/set_price/view_cost, `md@` view_cost, `sales2@` tidak
  ada; daftar OD untuk sales tidak memuat biaya/kontrak/supplier.

## Catatan / batasan
* Nego dibuka selama SO hasil OD masih tahap pesanan. Setelah nego terakhir di-ACC dan tidak ada persetujuan lain,
  SO naik ke "Disetujui" (aturan SO yang sudah ada) sehingga baris lain tidak bisa dinego lagi — sales sebaiknya
  mengajukan semua nego sekaligus.
* Item OD lama yang sudah terkunci (SORD-261023-0003) tidak dihitung ulang.
* Harga Grade A induk diambil saat pratinjau/kunci; perubahan harga master sesudah kunci tidak mengubah OD.
