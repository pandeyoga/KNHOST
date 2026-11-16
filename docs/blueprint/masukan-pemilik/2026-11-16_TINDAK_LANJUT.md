# Tindak lanjut masukan pemilik 16 Nov 2026 (M1–M43 + pengamatan)

Pemilik: "permintaan saya tadi tidak hanya soal ui ux, sudahkah anda perbaiki?" → "sekalian anda telusuri permasalahan
yang ada, saya juga minta soal master data hpp soal bom juga dan masih banyak lagi jadi jangan sampai terlewat".

Daftar ini **satu-satunya** papan kerja masukan 16 Nov. Tiap butir: akar (dari penelusuran kode di `HEAD`), perbaikan,
status. Status: **selesai** (kode + uji, sudah di-commit) · **dikerjakan** · **antre** (gelombang pola UI) ·
**tanya** (butuh jawaban pemilik). Sumber masukan: `2026-11-16_UI_MEJA_DAN_MENU.md`; pola: `../04_POLA_UI.md`.

## A. Bug, izin, dan logika (bukan tata letak)

| # | Masukan | Akar | Perbaikan | Status |
|---|---|---|---|---|
| M41 | Admin tidak punya akses Pusat Export | Garis dasar migrasi izin (`defaults_applied`) dulu dibuat dari **seluruh** izin bawaan kode, bukan dari matriks tersimpan → modul yang datang bersamaan (`data_export`) ditandai "sudah diterapkan" tanpa pernah masuk matriks; semua peran kehilangan modul itu | Garis dasar = pasangan yang sudah ada di matriks; Admin (peran terkunci) dipulihkan tiap start (`ensure_locked_role_defaults`, tercatat di jejak audit); skrip diagnosa `scripts/diagnosa_izin_bawaan_hilang.py` untuk peran lain (baca saja) | selesai |
| M34 | "Buat Nota Denda" tidak terjadi apa-apa | Pesan hasil ditulis ke halaman di belakang pop-up; tombol aktif walau tidak ada denda | Pesan di dalam pop-up; tombol nonaktif + alasan bila tidak ada estimasi denda baru | selesai |
| M33 | Pilih PT, lokasi tidak tersaring | `/location-scope` tidak membaca PT aktif; pilihan = semua gudang | Pilihan hanya gudang bersama + gudang khusus PT aktif; dimuat ulang saat PT diganti | selesai |
| M7 | Lokasi = area, POS ikut area | Pilihan menampilkan area **dan** tiap gudang; POS punya pilihan lokasi sendiri | Pilihan = area (gudang tanpa area tetap muncul; per gedung hanya untuk petugas berpagar); POS memakai area dari bilah atas | selesai |
| M16 | Panel kanan Pesanan bertentangan dengan baris | Panel jatuh ke daftar dasbor sesudah ganti tab/cari/halaman → menceritakan pesanan lain (batal) tanpa tanda pesanan mana | Panel hanya untuk pesanan yang tampil & tersorot; nomor + pelanggan di kepala panel; panel tetap (sticky) | selesai |
| M39 | Rincian gaji tidak sejajar; PPh 21 "Rp 0 0,00%" | Rincian satu sel 5 kolom dibagi 3; tarif tampil tanpa label walau pajak 0 | Rincian sejajar kolom (Pendapatan · Potongan · Tanggungan); pajak 0 → "—"; ada pajak → "TER {kategori} {tarif}" | selesai |
| M38 | Rekonsiliasi "cocokkan otomatis tanpa input file" | Tombol aktif walau belum ada mutasi; mencocokkan 0 baris lalu pesan sukses. Data demo membuat mutasi dari catatan kas sendiri (melingkar). Tidak ada tarik mutasi otomatis | Tombol nonaktif + alasan "Impor mutasi bank dulu". **Tanya:** apakah maksudnya ingin mutasi bank masuk otomatis (fitur baru: koneksi bank/API)? | selesai (temuan) · tanya (fitur) |
| O1 | Meja Admin Sales: "Shipped" mentah | Subtitle = kode tahap berbahasa Inggris | Subtitle = kota · sales; kode lain yang bocor (jenis permintaan, jenis target desain, "revision", "sent") diberi label | selesai |
| O2 | Meja MD Sample: "Rp 0" | Nilai biaya sample jarang diisi | Antrean jumlah (bukan rupiah) | selesai |
| O3 | Meja Saya: giliran 40 hari berlencana "Info" | Lencana = tingkat notifikasi; giliran lama tidak ditutup bila dokumen pindah ke status tanpa giliran atau dokumen lama | Lencana = tahap; baris yang dokumennya sudah pindah tahap tidak tampil; giliran lama ditutup | selesai |
| M31 | Baris kartu meja: tengah kosong | Server tidak mengirim waktu masuk | Semua baris meja membawa `at` ("masuk {tanggal}"); baris berkolom (pilot) | selesai |
| M9 | Panduan awal dihilangkan | Panel onboarding di beranda | Dihapus | selesai |
| M2 | Menu ber-sub-menu tebal & gelap | Kepala grup abu-abu 11 px | Kepala grup tebal, warna teks utama | selesai |
| M25 | Chip gudang bergulir | Deret chip di Stok Gudang | Dropdown "Semua gudang" | selesai |
| M10 | Induk produk Pesanan Khusus tidak tersaring | Daftar induk tanpa saringan tahap | Hanya induk tahap kain jadi | selesai |
| M11 | Satuan relevan / ikut induk | Semua satuan | Satuan mengikuti satuan dasar induk (dimensi sama) | selesai |
| M12 | Target harga opsional tanpa bawaan | Kosong dipaksa 0 di form, skema, server | Label "(opsional)", kosong tanpa bawaan; kosong disimpan 0 = belum ada target dan tampil "—" (bukan "Rp 0") | selesai |
| M13 | Induk & warna diisi dua kali | Langkah 4 mengulang induk & warna item | Langkah 4 tanpa induk & warna; sample revisi memakai warna item (cadangan spesifikasi OD lama) | selesai |
| M27 | BOM: nama bebas, kenapa perlu nama? | Nama wajib bebas; tidak ada versi/utama; Rute Produk mengambil BOM aktif sembarang | Nama dibuat sistem "BOM {SKU} v{n}"; versi per produk; satu BOM utama; rute & perintah kerja memakai BOM utama | dikerjakan |
| M28 | Master produk simpan HPP? | Katalog menampilkan `harga_pokok` manual berlabel "HPP" | Tampilkan HPP hitungan (rata-rata stok + sumber); `harga_pokok` = "HPP perkiraan (cadangan)" | dikerjakan |
| M30 | Eskalasi Gudang relevan? | Eskalasi manual; menu terpisah mengulang meja | Kartu "Perlu keputusan" di meja pemegang izin putus gudang; menu dihapus | dikerjakan |
| M5 | Meja MD belum lengkap | Tidak ada SPK makloon, PO bahan; PR salah nama field | Tambah kartu SPK makloon berjalan, menunggu faktur mitra, PO bahan; perbaiki PR | dikerjakan |
| M6 | POS: limit kredit total & terpakai | Bilah pelanggan tanpa angka kredit | Plafon · terpakai · sisa dari status kredit pelanggan | dikerjakan |
| M19 | Pelanggan: plafon, sales PJ "—" | Pop-up dari data dasbor mentah; sales PJ hanya dari `assigned_sales_id` | Plafon & terpakai di pop-up; sales PJ jatuh ke PIC tim sales | dikerjakan |
| M21 | Riwayat harga beli pelanggan | Riwayat hanya harga yang diatur | "Pernah dibeli": tanggal, SO, qty, harga, asal harga (khusus/langganan/PT) | dikerjakan |
| M42 | Jejak Dokumen: tampilkan daftar | Cari minimal 2 huruf; alat admin di layar utama | Daftar dokumen terbaru saat kosong; alat admin dipindah | dikerjakan |

## B. Tata letak (pola `04_POLA_UI.md`, per gelombang)

| # | Masukan | Status |
|---|---|---|
| M1, M4 | Meja tetap terbuka, sama tinggi, cari/saring/urut/paginasi per kartu; Keep & Pending satu baris | selesai (pilot `008aa68`) |
| M23 | Retur kacau | selesai (pilot) |
| M24 | Chip saringan → dropdown | sebagian: lini (semua layar), Retur, Pengaturan; SPK Inspeksi, Barang Masuk/Keluar antre |
| M43 | Semua menu Pengaturan | sebagian: Ketegasan & semua kelompok pengaturan (pilot); Hak akses (matriks tanpa gulir), Aturan Persetujuan, Kontrol dua orang antre |
| M3 | Tanya KN layar penuh, riwayat bisa disembunyikan | antre |
| M8, M32 | Kartu angka relevan & bisa diklik (Portal, Beranda Keuangan) | antre (komponen `MetricRow` sudah mendukung klik) |
| M14, M15 | Lini masa vertikal Pesanan Khusus | antre |
| M17 | Tab status Pesanan → dropdown | antre |
| M18 | Pop-up melayang (Pelanggan) | antre |
| M20 | Produk & Harga: alat admin dipindah | antre |
| M22 | Rincian produk | antre |
| M26 | Barang Masuk/Keluar/Cutting satu pola | antre |
| M29 | Lokasi Rak | antre |
| M35 | Tombol buat di banyak tempat | antre |
| M36, M37 | Bagan Akun & Antar-PT boros; pemilih PT dobel berwarna lain | antre |
| M40 | Lembar Insentif boros | antre |

## C. Pertanyaan untuk pemilik
1. M38 — "cocokkan otomatis tanpa input file": maksudnya (a) temuan tombol (sudah diperbaiki), atau (b) ingin mutasi bank
   masuk sendiri tanpa unggah berkas (perlu koneksi bank — fitur baru)?
