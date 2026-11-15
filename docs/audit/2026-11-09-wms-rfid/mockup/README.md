# Mockup Pusat Tugas Gudang & Penampil Roll (10 Nov 2026)

Rancangan layar **sebelum dibangun**, untuk dinilai pemilik. Bukan kode aplikasi; semua data contoh.

* Berkas: [`pusat-tugas-gudang.html`](pusat-tugas-gudang.html) (HTML mandiri, dibuka langsung di peramban).
* Versi daring (privat milik pemilik): https://claude.ai/artifact/LY7eLs1Fui5nZ562auk5Bg
* Dasar: `docs/KN_37_STANDAR_UI_GUDANG.md` (token & anatomi), riset `../B4-RISET-STANDAR-UI.md` §3.4–3.10,
  keputusan pemilik 10 Nov (`../KEPUTUSAN-KOORDINATOR.md`).

Isi:
1. **Pusat Tugas · desktop** — antrean tugas supervisor lintas jenis & PT dalam lokasi kerja, ringkasan yang bisa
   diklik, lencana jenis tugas (kategori) terpisah dari status, panel rincian, penetapan petugas.
2. **HP C72 · pindai per dokumen** — "Tugas saya" + tombol "Tugas berikutnya", layar tugas scan-first (Belum ·
   Cocok · Di luar dokumen · Masalah), mode RFID baca massal, pengecualian beralasan, selesai dengan selisih
   (kuning, tidak mengunci), sinyal putus (pindaian antre, Selesai menunggu koneksi). Ada panel simulasi.
3. **Penampil roll** — dua angka stok (lokal + Total grup semua PT, rincian per lokasi/PT/status/akan datang),
   Stok Fisik = Tersedia + Dipesan + Lainnya, tampilan tersimpan, hierarki Produk › Warna › Lot › Roll,
   rincian roll dengan pratinjau label 70 × 22 mm.
4. **Butir untuk dinilai** — 9 butir dengan rekomendasi; jawaban disalin pemilik ke chat.

Jawaban pemilik atas butir di bagian 4 dicatat di `../KEPUTUSAN-KOORDINATOR.md` sebelum Pusat Tugas dibangun.
