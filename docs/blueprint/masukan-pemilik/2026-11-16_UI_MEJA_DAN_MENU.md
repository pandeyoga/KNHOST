# Masukan pemilik 16 Nov 2026 — tampilan meja, menu samping, Tanya KN, POS, Pesanan Khusus, Pesanan, Pelanggan, Produk, Retur, Kualitas, Gudang

Status: **DITAMPUNG** — pemilik: "tampung dulu masih banyak foto yang harus saya upload". Belum dikerjakan; dijadikan
unit sesudah semua foto masuk. Foto: `2026-11-16_ui-meja/`.

## Masukan (kata pemilik, dirapikan)

| # | Layar | Masukan | Foto |
|---|---|---|---|
| M1 | Semua meja (Meja Saya, Meja Admin Sales, Meja MD, Meja Gudang, Meja Sample, …) | Kartu **tetap terbuka** — tanpa tombol buka/tutup (expand/minimize). Kolom **kiri dan kanan sama** (lebar & tinggi seragam). **Tiap kartu** punya **paginasi, cari, saring, urut** sendiri. | 01, 04, 05 |
| M2 | Menu samping | Menu yang punya sub-menu (mis. MEJA PERAN, PENJUALAN) **ditebalkan dan warnanya lebih gelap**. | 02 |
| M3 | Tanya KN (AI) | Tampilan **penuh**, bukan kartu-kartu. **Riwayat chat bisa disembunyikan.** | 03 |
| M4 | Meja Admin Sales | Kartu yang butuh ruang lebih besar (mis. **Keep & Pending**) **satu baris penuh**, tidak berdampingan dengan kartu lain (Aturan Grade Pelanggan). | 04 |
| M5 | Meja MD | Isi **belum lengkap**: tidak ada **makloon** (SPK makloon), **PO lain** (PO bahan), dsb. | 05 |

### Kiriman 2 — POS/Portal Penjualan, pilihan lokasi, Pesanan Khusus

| # | Layar | Masukan | Foto |
|---|---|---|---|
| M6 | POS › bilah Pelanggan | Tampilkan **limit kredit total dan terpakai** pelanggan terpilih. | 06 |
| M7 | Pilihan lokasi (kepala aplikasi) dan POS | Lokasi = **area**, bukan per gudang: mis. "Rancamalang" mewakili 5 gudangnya; daftar menampilkan areanya saja, bukan tiap gudang. **Saringan barang POS** ("Hanya yang ada di {lokasi}") harus mengikuti area itu — dicek. | 06, 07 |
| M8 | Portal Penjualan (kartu angka atas) | Sebagian kartu tidak relevan (mis. **Jml tersedia** gudang, Gudang) — ganti dengan yang relevan atau hapus bila tidak ada. | 08 |
| M9 | Portal Penjualan | **Panduan awal** (Buat UOM pertama, Buat pengguna baru, …) **dihilangkan**. | 07 |
| M10 | Pesanan Khusus Baru › Induk produk | Pilihan induk produk **tidak tersaring** — greige/benang masih muncul. Hanya induk yang sesuai (kain jadi/tahap yang relevan untuk sumber desain). | 09 |
| M11 | Pesanan Khusus Baru › Satuan | Satuan hanya yang **relevan untuk kain**, atau **mengikuti induk**. | 09 |
| M12 | Pesanan Khusus Baru › Target harga | **Opsional**, tanpa nilai bawaan (nilai bawaan membingungkan). | 09 |
| M13 | Pesanan Khusus Baru › Spesifikasi produk lengkap | Ada **"Induk produk basis"** lagi — **dobel** dengan bagian 2 "Item & sumber desain"; **warna** juga diisi dua kali. Satukan. | 09 |
| M14 | Rincian Pesanan Khusus › Lini masa | Lini masa (deretan 13 lencana tahap) **sulit dimengerti** → **lini masa ke bawah** sesuai urutan, dengan **aksi per tahap**. Pemilik minta analisis. | 10 |

#### Analisis lini masa Pesanan Khusus (permintaan pemilik — M14)
Keadaan sekarang (foto 10): 13 lencana tahap berderet mendatar dan terbungkus jadi dua baris (Draf → … → Produksi →
Siap → Dikirim → Selesai); di bawahnya terpisah "Rantai dokumen" (Permintaan desain, Sample R&D, SKU produk, PR/PO→SO).
Masalah:
1. **Tidak menjawab "sekarang menunggu apa, siapa, sejak kapan"** — lencana hanya tanda centang; tidak ada tanggal,
   pelaku, atau lama menunggu per tahap.
2. **Aksi terpisah dari tahapnya** — tombol tindakan ada di bagian lain halaman; pengguna harus mencari.
3. **Dua tampilan untuk satu alur** — lini masa (status) dan rantai dokumen (dokumen) menceritakan hal yang sama secara
   terpisah; pengguna harus mencocokkan sendiri (mis. "Sampling berjalan" ↔ "KSC/SMP-00001").
4. **Deretan mendatar terbungkus** — urutan terbaca sulit; tahap yang dilewati/tidak berlaku tidak dibedakan.
Usulan (lini masa ke bawah, satu baris per tahap):
- Kiri: titik status (selesai ✓ / sedang berjalan ● / belum ○ / dilewati —), garis penghubung vertikal.
- Isi tiap tahap: nama tahap · **tanggal & pelaku** (selesai) atau **"menunggu {peran/nama} sejak {tanggal} ({n} hari)"**
  (berjalan) · **dokumen tahap itu** sebagai tautan (Permintaan desain, Sample, SKU, PR/PO, SO, Surat jalan) — rantai
  dokumen dilebur ke sini.
- **Tombol aksi hanya di tahap yang sedang berjalan** (mis. "Putuskan sample", "Konversi ke SO"), sesuai izin pemakai.
- Tahap selesai bisa dilipat ("8 tahap selesai — lihat"); tahap yang tidak berlaku untuk tipe permintaan ini disembunyikan
  atau ditandai "tidak diperlukan".
- HP: bentuk yang sama (memang vertikal) tanpa penyesuaian khusus.

### Kiriman 3 — acuan lini masa, Pesanan, Pelanggan, Produk & Harga

| # | Layar | Masukan | Foto |
|---|---|---|---|
| M15 | Lini masa (Pesanan Khusus dan sejenisnya) | Acuan: lini masa vertikal di sisi kanan (tiap tahap: nama, tanggal, catatan/keterangan tahap, mis. "Proses perbaikan: 29 hari dari tanggal pengajuan"). Pemilik: **"seperti ini, tapi saya ingin lebih bagus"**. Acuan hanya pola tata letak (produk lain), bukan untuk ditiru mereknya. | 11 |
| M16 | Pesanan (daftar SO + panel rincian kanan) | **Cacat UI**: daftar menyisakan ruang kosong besar; panel kanan berupa tumpukan bagian panjang (Ditagih, Dibayar, Tagihan, Progres gudang, Surat jalan, Pelacakan, Faktur pajak, Uang masuk) yang sebagian besar "belum ada". | 12 |
| M17 | Pesanan › tab status | Deretan tab status bernilai (Semua · Dipesan · Backorder · Diproses · Dikirim · Selesai · Dibatalkan) **tidak perlu** — cukup **saringan dropdown**. | 13 |
| M18 | Umum (contoh: Pelanggan) | **Popup muncul sembarangan** — kartu "Rincian {pelanggan}" melayang menutupi tabel. | 14 |
| M19 | Pelanggan | **UI perlu diperbaiki** (tabel tertutup kartu melayang; plafon kredit hanya "Lihat tab Kredit di kartu pelanggan"; sales penanggung jawab "—"). | 14 |
| M20 | Produk & Harga | **"Sangat kacau sekali, hancur"**: alat tata kelola master untuk admin data (preview legacy, `line_code: ∅ → woven`, daftar kandidat duplikat SKU mentah, "Eksekusi 0 perubahan", lembar kerja perbaikan, sumber restock) tampil terbuka di atas katalog; delapan tab; banyak saringan. | 15 |

Catatan Claude untuk M16 (perlu dicek): baris KSC/SO-00001 berstatus "Selesai · Lunas", sedangkan panel kanan menulis
"Ditagih ✗" dan "Dibayar — Pesanan dibatalkan, tidak ada tagihan". Bila panel itu milik SO-00001, isinya bertentangan
dengan status baris; bila milik pesanan lain, panel tidak menunjukkan pesanan mana yang sedang dibuka.

Catatan Claude untuk M20: arah yang masuk akal — halaman Produk & Harga hanya katalog bersih (cari + saringan ringkas +
daftar induk/varian); alat tata kelola data (preview legacy, duplikat, lembar kerja perbaikan, sumber restock) dipindah
ke tempat admin data (mis. Pengaturan › Data master) dan tertutup untuk peran selain pemegang izinnya.

### Kiriman 4 — Harga per Pelanggan, rincian produk, Retur, filter, Gudang

| # | Layar | Masukan | Foto |
|---|---|---|---|
| M21 | Produk & Harga › Harga per Pelanggan | Tambahkan **riwayat harga beli pelanggan** per barang (pernah membeli berapa, kapan, dari pesanan mana), termasuk asalnya — mis. **lahir dari harga khusus (special price)**. | 16 |
| M22 | Rincian produk | **UI rincian per produk masih sangat kacau.** | 17 |
| M23 | Retur | **Menu retur kacau.** | 18 |
| M24 | Umum — saringan berbentuk deretan tombol | **Tombol-tombol saringan diganti dropdown** (contoh: Lini Semua/Woven/Knit/Printing di Retur & SPK Inspeksi; 9 chip jenis + 7 chip status di SPK Inspeksi). Sejalan dengan M17 (tab status Pesanan). | 18, 19 |
| M25 | Gudang (saringan gudang) | Deretan chip gudang bergulir mendatar **sangat buruk** — ganti dropdown; sejalan dengan M7 (lokasi = area, gudang di bawahnya). | 20 |

Catatan Claude (dari foto, perlu dicek saat dijadikan unit):
- M21: daftar menampilkan semua barang dengan "belum diatur" dan kolom "Harga PT" kosong — barang yang relevan untuk
  pelanggan itu (pernah dibeli / punya harga khusus) sebaiknya di atas atau jadi saringan bawaan.
- M22: kepala rincian berisi kartu angka yang kosong (Gramasi —, Lebar —, Tersedia 0, Foto 0), label tahap teknis
  ("Finished (Jadi — Dyed/Printed) · Woven (Tenun)"), pesan teknis ("kode desain & kategorinya kosong di POS/export"),
  dan tombol merah "Hapus permanen" beserta teks izin yang panjang di tengah halaman.
- M23: satu layar memuat 3 tab + 4 kartu angka berketerangan panjang + bilah penjelasan bertautan + cari + chip lini +
  2 dropdown + tabel — terlalu banyak lapisan sebelum isi.

### Kiriman 5 — Operasi Gudang, BOM, Lokasi Rak, Eskalasi

| # | Layar | Masukan | Foto |
|---|---|---|---|
| M26 | Operasi Gudang › Barang Masuk / Barang Keluar / Cutting | UI/UX **tidak konsisten** antar tab — padahal bisa satu pola (Barang Masuk: cari + chip status + kosong di tengah; Barang Keluar: chip status + cari + chip jenis + dropdown gudang + daftar kiri/panel kanan). | 21, 22 |
| M27 | BOM Produksi In-House › BOM Baru | **"Nama BOM" diisi bebas — kenapa perlu nama BOM?** (pertanyaan pemilik; jawaban di bawah) | 23 |
| M28 | Master produk | **Apakah master produk menyimpan HPP?** (pertanyaan pemilik; jawaban di bawah) | — |
| M29 | Lokasi Rak | **UI masih sangat buruk.** | 24 |
| M30 | Eskalasi Gudang | **Menu ini untuk apa, relevan?** (pertanyaan pemilik; jawaban di bawah) | 25 |

#### Jawaban pertanyaan pemilik (dari kode di `HEAD`, 16 Nov)

**M27 — Nama BOM.** Nama hanya label bebas: wajib tidak kosong, tanpa aturan unik, tanpa nama bawaan
(`backend/services/production_service.py` `create_bom`). Kuncinya `id`; perintah kerja menaut ke `bom_id` dan menyalin
`bom_name` hanya untuk tampilan. Satu produk boleh punya banyak BOM aktif tanpa versi/utama, dan Rute Produk mengambil
BOM aktif **sembarang** untuk produk itu (`product_route_service.py` — `find_one` tanpa urutan). Jadi nama BOM memang
tidak diperlukan sebagai isian; yang diperlukan adalah **BOM per produk hasil + versi**.
Usulan: hapus isian nama; identitas = produk hasil + nomor versi ("BOM {SKU} v2", dibuat sistem); satu BOM **utama**
per produk (versi lama arsip); Rute Produk dan perintah kerja memakai BOM utama.

**M28 — HPP di master produk.** Master produk hanya menyimpan `harga_pokok` — angka manual/peninggalan yang dipakai
sebagai cadangan bila roll lahir tanpa biaya. HPP sebenarnya ada **per roll** (`inventory_rolls.unit_cost`, termasuk
biaya tambahan) dan dihitung saat dibaca sebagai rata-rata tertimbang stok hidup (`costing_service.py`), dikirim API
produk sebagai `hpp` + sumbernya. Masalah: tab Informasi produk di katalog menampilkan `harga_pokok` berlabel "HPP"
(`frontend/src/features/catalog/FamilyInfoTab.jsx`) — **angka berbeda** dari HPP hitungan.
Usulan: layar produk menampilkan HPP hitungan (rata-rata stok + sumber: "dari 23 roll" / "perkiraan"); `harga_pokok`
diganti nama "HPP perkiraan (dipakai bila roll tanpa biaya)" atau dihapus bila semua jalur penerimaan sudah membawa biaya.

**M30 — Eskalasi Gudang.** Eskalasi selalu **manual**: petugas menekan "Eskalasi" di layar scan Barang Masuk/Keluar
dengan alasan (izin `wms.update`) bila tugas tidak bisa diselesaikan apa adanya (mis. qty tidak sesuai); tidak ada
eskalasi otomatis karena umur. Pemegang `wms.approve` memutus: kembalikan ke status sebelumnya atau ubah qty (keluar:
lepas cadangan roll, ubah baris SO, hitung ulang harga). Fungsinya relevan, tetapi **menu terpisahnya tidak**: tugas yang
sama sudah tampil di antrean gudang Meja Saya dan di saringan "Dieskalasi" layar scan.
Usulan: hapus menu Eskalasi Gudang; jadikan kartu "Perlu keputusan" di Meja Gudang/Meja Saya untuk pemegang
`wms.approve` (sejalan M1).

### Kiriman 6 — baris daftar, kartu angka keuangan, entitas ↔ lokasi, nota denda, tombol buat, ruang

| # | Layar | Masukan | Foto |
|---|---|---|---|
| M31 | Daftar baris di kartu meja (contoh: Faktur pajak perlu terbit) | Baris: info di kiri, nilai + tombol di kanan, **tengahnya kosong** → daftar jadi lebar. **Isi bagian tengah** (kolom: pelanggan, PPN, status, umur, dst.). | 26 |
| M32 | Kartu angka (contoh: Beranda Keuangan — marjin, rasio, umur piutang/hutang, terbesar) | Kartu **hanya menampilkan angka** — tidak ada navigasi/fungsi. Kartu harus bisa diklik ke rincian/daftar tersaring (atau dihapus bila tidak berguna; sejalan M8). | 27 |
| M33 | Pilihan PT ↔ pilihan lokasi (kepala aplikasi) | **Pilih entitas (PT) dulu, tetapi lokasi tidak tersaring** — gudang PT lain ikut muncul. Lokasi harus mengikuti PT terpilih (dan berupa area, M7). | 29 |
| M34 | Piutang › popup pelanggan › "Buat Nota Denda" | **Diklik tidak terjadi apa-apa.** Diagnosa (Claude): permintaan berjalan, tetapi pesan hasil ("Tidak ada denda yang layak dibuatkan nota…") ditulis di halaman **di belakang popup** (`ARAgingView.jsx` `flash`), jadi tidak terlihat; tombol juga tampil walau tidak ada tagihan lewat jatuh tempo. Perbaikan: pesan di dalam popup; tombol nonaktif + alasan bila tidak ada yang layak. | 28 |
| M35 | Umum (contoh: Antar-PT) | **Tombol "buat transaksi baru" ada di mana-mana** — satu aksi utama per layar, letak konsisten. | 29 |
| M36 | Umum (contoh: Bagan Akun, Antar-PT) | **Sangat boros ruang**: kepala bertumpuk dua baris (cari + tipe + Tambah + muat ulang turun baris), bilah penjelasan panjang, kartu angka berketerangan panjang, dua deret tab, dropdown "Semua peran" selebar layar, baris cari terpisah. | 29, 30 |

Catatan Claude (foto 28): ringkasan "Belum lunas Rp 6.743.694 (tercatat Rp 0 · belum dikirim Rp 6.743.694)" dan kolom
"Tercatat · Belum dikirim" sulit dipahami orang awam — istilahnya perlu ditinjau bersama M19 (Pelanggan).

### Kiriman 7 — Bagan Akun, rekonsiliasi, penggajian, insentif, Pusat Export, Jejak Dokumen

| # | Layar | Masukan | Foto |
|---|---|---|---|
| M37 | Bagan Akun › "Lingkup" (Template Global · Sukacita · Kanda Fabric · Cipta Sandang) | **Warnanya beda sendiri** (ungu), dan **relevankah bila PT sudah dipilih di bilah atas?** — pilihan PT dobel. | 31 |
| M38 | Rekonsiliasi bank | "Rekonsiliasi saya bisa cocokkan otomatis **tanpa input file**." Perlu dikonfirmasi maksudnya: (a) temuan — tombol cocokkan otomatis tersedia walau belum ada mutasi diimpor; atau (b) permintaan — mutasi bank masuk/dicocokkan otomatis tanpa unggah berkas. | — |
| M39 | Penggajian › rincian per karyawan | **UI rincian (breakdown) masih bermasalah**: blok Pendapatan/Potongan/Tanggungan perusahaan tidak sejajar kolom tabel; PPh 21 "Rp 0 0,00%". | 32 |
| M40 | Kinerja & Insentif › Lembar Insentif | **Boros ruang** (kartu berjudul + keterangan + tombol + label saringan + chip status + baris kosong). | 33 |
| M41 | Pusat Export | **"Saya admin tapi tidak punya akses."** Kode memberi peran `admin` izin `data_export` view/export (`backend/permissions_config.py`); dugaan: izin peran yang tersimpan di database (atau akun berperan kustom berlabel Admin) belum memuat "Pusat Export Data" — perlu dicek di data. | 34 |
| M42 | Pusat Dokumen › Jejak Dokumen | **Cari dokumen harus menampilkan daftar** (dokumen terbaru/tersaring), bukan hanya kotak cari. Juga: panel "Alat admin · susun ulang relasi dokumen lama" tampil di layar utama (sejenis M20). | 35 |

### Kiriman 8 — semua menu Pengaturan

| # | Layar | Masukan | Foto |
|---|---|---|---|
| M43 | **Semua menu Pengaturan** (contoh: Peran & Hak Akses, Hak akses per peran, Aturan Persetujuan, Ketegasan/Pengingat & Dokumen, Kontrol dua orang) | **"Masih berantakan, boros, tidak konsisten, UI/UX buruk, bertele-tele — UI/UX sangat buruk sekali."** | 36–40 |

Catatan Claude (dari foto + kode):
- Hak akses per peran: jendela lebar dengan **gulir mendatar**, ringkasan teks panjang di kanan, peringatan panjang.
- Peran & Hak Akses: dua bilah penjelasan panjang, tombol muat ulang sendirian di satu baris.
- Aturan Persetujuan: tiap aturan satu kartu + lencana "Aturan bawaan (belum disimpan)" + "Buat aturan khusus PT ini" +
  isian "Coba nilai" sendiri-sendiri.
- Ketegasan/Pengingat: **satu kartu besar per pengaturan**; dibuka berisi "Artinya", "Kalau diubah", "Contoh", "Bisa
  dibedakan untuk", "Detail teknis", lalu isian + Simpan. Ini bentuk wajib dari komponen `SettingCard.jsx` dan
  dijaga penjaga `verify_config_text` (wajib arti, dampak, contoh) — standar kita sendiri yang membuatnya bertele-tele.
- Kontrol dua orang: tiap baris dropdown + isian Rp dengan gema "Rp 0" di bawahnya + kolom Sumber.

## Catatan pengamatan (Claude, dari foto yang sama — belum dikonfirmasi pemilik)
- Meja Admin Sales › Siap cetak SJ/Invoice: status di bawah nama pelanggan tertulis "Shipped" (kode mentah berbahasa
  Inggris) — seharusnya label Indonesia.
- Meja MD › Sample & labdip: nilai "Rp 0" tidak bermakna untuk sample.
- Meja Saya › Giliran saya: dokumen menunggu 40 hari dengan lencana "Info" — perlu dicek apakah memang tugas.

## Bahan rancangan (diisi saat dijadikan unit)
- Daftar meja dan kartunya, pola kartu tunggal (paginasi/cari/saring/urut per kartu), aturan lebar kartu (penuh vs
  dua kolom), isi Meja MD (makloon, PO bahan, PR, sample), gaya grup menu samping, tata letak Tanya KN.
