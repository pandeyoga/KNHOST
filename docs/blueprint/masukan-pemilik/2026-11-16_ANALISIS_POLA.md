# Analisis pola — 43 masukan pemilik 16 Nov 2026 (M1–M43)

Sumber: `2026-11-16_UI_MEJA_DAN_MENU.md` (masukan + 40 foto). Permintaan pemilik: "coba dari semua ini analisis dulu,
saya rasa ada pattern yang jelas". Angka di bawah dihitung dari kode `frontend/src` di `HEAD` (16 Nov).

## Kesimpulan
43 masukan itu bukan 43 masalah; sebagian besar adalah **10 pola** yang berulang di banyak layar. Akar bersamanya:
**tiap layar merakit tata letaknya sendiri, dan tiap unit kerja menambah lapisan (kartu, bilah penjelasan, tab, chip,
alat admin) tanpa ada yang mengurangi.** Standar UI yang ada (`02_STANDAR.md`, penjaga `verify_ui_standard`) memeriksa
butir kecil — warna hex, ukuran huruf, jenis lencana — dan sifatnya "jangan bertambah", bukan "pakai templat ini".
Tidak ada templat halaman yang wajib, sehingga 871 berkas JSX di 41 folder fitur tumbuh dengan bentuk masing-masing.

Bukti cepat:
| Ukuran | Jumlah berkas |
|---|---|
| Kepala bagian buatan sendiri (`section-head`) vs kepala halaman bersama (`PageHeader`) | 204 vs 24 |
| Saringan berbentuk chip/tab (`FilterChips` 44, `StatusTabs` 12, chip buatan ±29) | ±85 |
| Bilah penjelasan (`notice-bar`) | 171 |
| Kartu angka; yang bisa diklik | 24; ±10 |
| Popup rincian `DetailModal` / formulir `FormModal` | 45 / 185 |
| Rincian berkepala baku `DetailHeader` | 4 |

Kabar baiknya: beberapa pola sudah punya **satu komponen bersama**, jadi perbaikannya sekali untuk semua layar —
semua meja memakai `DeskQueueCard` (6 berkas; buka/tutup ada di komponen itu), pemilih lokasi satu `LocationScopeBar`,
kartu pihak satu `PartyCardHost`.

## Pola

| # | Pola | Masukan | Akar (kode) | Aturan yang diusulkan |
|---|---|---|---|---|
| P1 | **Tiap layar punya tata letak sendiri** — tidak konsisten antar tab/menu, boros ruang, kepala bertumpuk | M1, M4, M16, M23, M26, M29, M36, M40 | Tidak ada templat halaman wajib; `section-head` 204 vs `PageHeader` 24 | **Empat templat**: Daftar, Rincian, Meja, Formulir. Kepala satu baris (judul · cari · saringan · satu aksi utama). Kartu meja tetap terbuka, kiri-kanan sama tinggi, kartu besar satu baris penuh. |
| P2 | **Saringan berbentuk deretan tombol/chip/tab** | M17, M24, M25, M37 | `FilterChips`/`StatusTabs`/chip buatan ±85 berkas | **Satu bilah saring**: cari + dropdown (status, lini, jenis, gudang) + urut + jumlah hasil. Tanpa deret chip/tab status. |
| P3 | **Kartu angka pajangan** — tidak relevan atau tidak bisa diklik | M8, M32 (+ Retur, Lokasi Rak, Antar-PT, SPK Inspeksi) | 24 berkas berkartu angka, ±10 yang bisa diklik | Kartu angka **hanya** bila relevan untuk peran dan **selalu bisa diklik** ke daftar tersaring; selain itu dihapus. |
| P4 | **Penjelasan panjang & alat teknis di layar kerja** | M9, M20, M22, M23, M36, M42 (+ Buku Bahan) | 171 bilah penjelasan; alat admin di katalog (`MasterGovernancePanel`, `MasterCleanupPanel`) dan Jejak Dokumen (`TraceBackfill`) | Layar kerja untuk bekerja: penjelasan → ikon "?"/teks kecil satu baris; **alat admin data → Pengaturan › Data master** (tertutup selain pemegang izin). Panduan awal dihapus. |
| P5 | **Lapisan saling menimpa** — popup melayang, pesan tersembunyi, dua tombol kembali | M18, M34 (+ dua "Kembali", sudah diperbaiki) | Kartu pihak melayang di atas tabel; pesan hasil "Buat Nota Denda" ditulis di halaman di belakang popup | Rincian = **halaman atau panel samping tetap**, bukan kartu melayang; pesan hasil selalu di lapisan yang sedang aktif; tombol yang tidak bisa dipakai nonaktif + alasan. |
| P6 | **Konteks PT & lokasi tidak menyaring turunannya** | M7, M25, M33, M37 | Pemilih lokasi menampilkan area **dan** tiap gudang tanpa saring PT; Bagan Akun punya pemilih PT sendiri (berwarna lain) | PT dipilih **sekali** di bilah atas; lokasi = **area** (gudang di bawahnya); semua pilihan turunan (gudang, lingkup, stok POS) mengikuti PT + area. |
| P7 | **Isian tidak tersaring konteks, dobel, atau seharusnya dihitung sistem** | M10, M11, M12, M13, M27, M28 | Induk produk tidak disaring tahap; spesifikasi mengulang induk & warna; Nama BOM bebas; "HPP" di katalog = `harga_pokok` manual | Pilihan **disaring menurut konteks** (tahap, satuan induk); **satu fakta satu isian**; yang bisa diturunkan sistem tidak ditanya (nama BOM, HPP hitungan); opsional tanpa nilai bawaan. |
| P8 | **Alur & status tidak terbaca** | M14, M15, M16 (panel), teks Riwayat "Step 1: issue…", "Shipped" | Lini masa = deret lencana; rantai dokumen terpisah; teks riwayat dari server bercampur Inggris | **Satu komponen lini masa vertikal**: tahap · waktu · pelaku · dokumen · aksi di tahap berjalan; dipakai Pesanan Khusus, SO, PO, SPK makloon, Retur. Teks riwayat Bahasa Indonesia. |
| P10 | **Pengaturan bertele-tele** — satu kartu besar per pengaturan, paragraf wajib, jendela bergulir mendatar | M43 (semua menu Pengaturan), M37 | `SettingCard.jsx` mewajibkan "Artinya / Kalau diubah / Contoh / Bisa dibedakan / Detail teknis" per kunci; penjaga `verify_config_text` mewajibkan teks itu ada; hak akses di jendela lebar | **Pengaturan berbentuk daftar padat**: satu baris per pengaturan (nama · nilai berlaku · asal: bawaan/PT · ubah langsung di baris); penjelasan di ikon "?" (teksnya tetap disimpan registri, tidak dipajang); satu Simpan per bagian. Hak akses = **halaman matriks** modul × tingkat tanpa gulir mendatar. Penjaga teks tetap memeriksa isi registri, bukan memaksa tampil. |
| P9 | **Data keputusan tidak ada di tempat kerja** | M5, M6, M19, M21, M31, M42 | Meja MD tanpa SPK makloon/PO bahan; POS tanpa limit kredit; daftar tanpa kolom tengah; Jejak Dokumen tanpa daftar | Tiap layar menampilkan data yang dibutuhkan **untuk keputusan perannya** (limit & terpakai di POS, riwayat harga pelanggan, isi meja lengkap per peran, daftar dokumen terbaru). |

**Di luar pola (bug/izin, diperbaiki tersendiri):** M34 nota denda (pesan di belakang popup), M41 Admin tanpa akses Pusat
Export (kode memberi izin → cek data peran), M16 panel SO bertentangan dengan status baris (cek), M38 rekonsiliasi (maksud
perlu dikonfirmasi), M39 rincian gaji tidak sejajar, M2 gaya grup menu, M3 Tanya KN layar penuh.

## Usulan cara mengerjakan
Bukan 42 perbaikan satu per satu, tetapi:
1. **Tetapkan standar tata letak** (tambahan `02_STANDAR.md` bagian UI): empat templat halaman + enam komponen bersama —
   `PageHeader` satu baris, `FilterBar` (dropdown), `KpiCard` berklik, `DeskCard` tetap, `Timeline` vertikal,
   `DetailPage`/panel samping — plus pemeriksa otomatis yang menolak pola lama di berkas yang disentuh.
2. **Perbaiki bug & izin dulu** (cepat, berdampak langsung): M34, M41, M33, M16, M10.
3. **Migrasi per gelombang layar**, yang paling sering dipakai dulu: (a) semua meja (satu komponen) + menu samping;
   (b) Produk & Harga + rincian produk; (c) Pesanan + Pesanan Khusus (lini masa); (d) POS + Pelanggan + Harga per
   Pelanggan; (e) Operasi Gudang (Masuk/Keluar/Cutting satu pola) + Lokasi Rak + Eskalasi → kartu meja; (f) Retur,
   Kualitas; (g) Keuangan (Beranda, Piutang, Antar-PT, Bagan Akun, Penggajian, Insentif); (h) **Pengaturan** (semua
   menu: satu pola daftar padat + matriks hak akses — P10); (i) Tanya KN, Jejak Dokumen, Pusat Export.
4. Tiap gelombang: tangkapan layar sebelum/sesudah di 1366/1024/HP dan dicek pemilik sebelum gelombang berikutnya.

## Perlu keputusan pemilik sebelum mulai
- Urutan gelombang di atas setuju, atau ada layar yang harus didahulukan?
- P3: kartu angka apa yang relevan per layar — saya usulkan per gelombang, pemilik memilih.
- M5: isi lengkap Meja MD (usul: permintaan desain, sample, SPK makloon berjalan & menunggu faktur, PR/PO bahan, pesanan
  khusus).
- M38: maksud "cocokkan otomatis tanpa input file".
- M27/M28: BOM per produk + versi (hapus nama bebas) dan HPP produk = hitungan stok — setuju?
