# Rubrik review UI — ERP Kain Nusantara (KNHOST)

Anda me-review tangkapan layar (PNG) + metrik otomatis per layar. Bahasa laporan: **Indonesia**. Tujuan: menemukan halaman/tab/form
yang **kacau, tidak konsisten, rusak, atau duplikat**, dengan bukti yang bisa dicek ulang.

## Standar design system yang SUDAH ADA di kode (acuan "benar")
* Kerangka halaman: `PageHeader` (judul h1 + subjudul + aksi kanan, `components/ListPageParts.jsx`), isi dalam kartu `.section-card`
  (latar putih, border tipis, radius besar) dengan kepala `.section-head` (judul + aksi) dan label kecil `.kicker`.
* Tab standar: `.tab-bar` + `.tab-button` (garis bawah). Pil/segmented buatan sendiri = tidak standar.
* Tabel standar: `.data-table` (12.5px). `<table>` mentah atau grid `grid-cols-[...]` buatan sendiri = tidak standar.
* Tombol: `.primary-button` (biru iOS `--ios-blue`, putih tebal 13px), `.secondary-button` (putih bergaris), `.icon-button`.
  Tombol utama berwarna lain (ungu #6B219A, hitam, hijau, biru #0058CC vs #007AFF) = tidak konsisten.
* Isian: `.field` (13px, tinggi ±34px) + label di atas (`.field-label` atau label 10.5–11px). Placeholder-sebagai-label = buruk.
* Dropdown: `KNSelect` (satu gaya). Tanggal: `KNDatePicker`. Modal: `FormModal`/`DetailModal` (judul, deskripsi, isi, kaki tombol).
* Teks minimum yang layak dibaca ±11px; banyak teks 9–10.5px = terlalu kecil.

## Yang dicari per layar
1. **Rusak / menyesatkan (Tinggi)**: galat, halaman kosong tanpa penjelasan, data mentah/kode internal (mis. `waiting_approval`,
   `undefined`, `NaN`, id teknis), gambar rusak, angka tidak masuk akal, tombol/isian keluar layar di HP, tumpang tindih,
   gulir samping di HP, teks terpotong yang menyembunyikan arti.
2. **Tidak konsisten (Sedang)**: kerangka halaman berbeda dari standar (tanpa judul/kartu), tab buatan sendiri, tabel mentah,
   warna tombol utama lain, dua gaya dropdown dalam satu form, ukuran huruf campur aduk/terlalu kecil, susunan aksi berbeda
   (tombol simpan di kiri vs kanan), label tidak seragam (MAJUSCULE vs biasa), istilah campur Inggris–Indonesia
   (mis. "Sales Orders" vs "Pesanan"), ikon/warna status berbeda untuk status yang sama.
3. **Form (Sedang/Tinggi)**: isian tanpa label, penanda wajib (*) tidak konsisten, urutan isian tidak logis, lebar isian aneh,
   form terlalu panjang tanpa pengelompokan, tombol kaki tidak jelas (dua tombol utama, label tombol ambigu), modal terlalu
   sempit/lebar, isian yang tidak relevan untuk konteks.
4. **Duplikasi (Sedang)**: layar/tab/form yang fungsinya sama atau sangat mirip dengan layar lain (sebut pasangannya), dua
   tombol yang melakukan hal sama di satu halaman, informasi sama ditampilkan dua kali.
5. **Kosmetik (Rendah)**: spasi, perataan, ikon tidak serasi.

## Format keluaran (WAJIB, ringkas, tanpa basa-basi)
Untuk setiap layar:
```
### <id layar> — <judul layar> (<peran>)
- [T|S|R] [rusak|konsisten|form|HP|duplikasi|istilah] <temuan konkret, sebut elemen/teks yang terlihat> (bukti: <nama png>)
```
Maksimal 6 butir per layar, urut dari paling parah. Layar yang baik cukup satu baris: `- OK — <alasan singkat>`.
Di AKHIR laporan buat bagian:
```
## Pola berulang
- <pola> — muncul di: <daftar id layar>
## Kandidat duplikasi
- <layar A> ≈ <layar B> — <kenapa mirip / apa bedanya>
## Contoh baik (acuan)
- <id layar> — <kenapa layak jadi acuan>
```
Jangan menebak isi yang tidak terlihat. Bila PNG tidak bisa dibaca, tulis itu. Jangan mengedit berkas apa pun.
