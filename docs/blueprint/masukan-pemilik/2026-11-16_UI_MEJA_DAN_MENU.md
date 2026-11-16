# Masukan pemilik 16 Nov 2026 — tampilan meja, menu samping, Tanya KN, POS, Pesanan Khusus, Pesanan, Pelanggan, Produk

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

## Catatan pengamatan (Claude, dari foto yang sama — belum dikonfirmasi pemilik)
- Meja Admin Sales › Siap cetak SJ/Invoice: status di bawah nama pelanggan tertulis "Shipped" (kode mentah berbahasa
  Inggris) — seharusnya label Indonesia.
- Meja MD › Sample & labdip: nilai "Rp 0" tidak bermakna untuk sample.
- Meja Saya › Giliran saya: dokumen menunggu 40 hari dengan lencana "Info" — perlu dicek apakah memang tugas.

## Bahan rancangan (diisi saat dijadikan unit)
- Daftar meja dan kartunya, pola kartu tunggal (paginasi/cari/saring/urut per kartu), aturan lebar kartu (penuh vs
  dua kolom), isi Meja MD (makloon, PO bahan, PR, sample), gaya grup menu samping, tata letak Tanya KN.
