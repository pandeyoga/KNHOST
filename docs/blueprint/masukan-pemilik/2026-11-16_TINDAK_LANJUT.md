# Tindak lanjut masukan pemilik 16 Nov 2026 (M1–M43 + pengamatan)

Pemilik: "permintaan saya tadi tidak hanya soal ui ux, sudahkah anda perbaiki?" → "sekalian anda telusuri permasalahan
yang ada, saya juga minta soal master data hpp soal bom juga dan masih banyak lagi jadi jangan sampai terlewat".

Daftar ini **satu-satunya** papan kerja masukan 16 Nov. Tiap butir: akar (dari penelusuran kode di `HEAD`), perbaikan,
status. Status: **selesai** (kode + uji, sudah di-commit) · **dikerjakan** · **antre** (gelombang pola UI) ·
**tanya** (butuh jawaban pemilik). Sumber masukan: `2026-11-16_UI_MEJA_DAN_MENU.md`; pola: `../04_POLA_UI.md`.

## A. Bug, izin, dan logika (bukan tata letak)

| # | Masukan | Akar | Perbaikan | Status |
|---|---|---|---|---|
| M41 | Admin tidak punya akses Pusat Export | Garis dasar migrasi izin (`defaults_applied`) dulu dibuat dari **seluruh** izin bawaan kode, bukan dari matriks tersimpan → modul yang datang bersamaan (`data_export`) ditandai "sudah diterapkan" tanpa pernah masuk matriks; semua peran kehilangan modul itu | Garis dasar = pasangan yang sudah ada di matriks; Admin (peran terkunci) dipulihkan tiap start (`ensure_locked_role_defaults`, tercatat di jejak audit); skrip diagnosa `backend/scripts/diagnosa_izin_bawaan_hilang.py` untuk peran lain (baca saja) | selesai |
| M34 | "Buat Nota Denda" tidak terjadi apa-apa | Pesan hasil ditulis ke halaman di belakang pop-up; tombol aktif walau tidak ada denda | Pesan di dalam pop-up; tombol nonaktif + alasan bila tidak ada estimasi denda baru | selesai |
| M33 | Pilih PT, lokasi tidak tersaring | `/location-scope` tidak membaca PT aktif; pilihan = semua gudang | Pilihan hanya gudang bersama + gudang khusus PT aktif; dimuat ulang saat PT diganti | selesai |
| M7 | Lokasi = area, POS ikut area | Pilihan menampilkan area **dan** tiap gudang; POS punya pilihan lokasi sendiri | Pilihan = area (gudang tanpa area tetap muncul; per gedung hanya untuk petugas berpagar); POS memakai area dari bilah atas | selesai |
| M16 | Panel kanan Pesanan bertentangan dengan baris | Panel jatuh ke daftar dasbor sesudah ganti tab/cari/halaman → menceritakan pesanan lain (batal) tanpa tanda pesanan mana | Panel hanya untuk pesanan yang tampil & tersorot; nomor + pelanggan di kepala panel; panel tetap (sticky) | selesai |
| M39 | Rincian gaji tidak sejajar; PPh 21 "Rp 0 0,00%" | Rincian satu sel 5 kolom dibagi 3; tarif tampil tanpa label walau pajak 0 | Rincian sejajar kolom (Pendapatan · Potongan · Tanggungan); pajak 0 → "—"; ada pajak → "TER {kategori} {tarif}" | selesai |
| M38 | Rekonsiliasi: "bisa cocokkan otomatis padahal saya tidak upload berkas" (pemilik 17 Nov: maksudnya temuan) | (1) Tombol aktif walau belum ada mutasi; (2) data acuan/demo membuat mutasi bank contoh dari catatan kas sendiri (`seed_bank_statement`), tanpa tanda asal — jadi tampak seperti mutasi sungguhan padahal tidak pernah diunggah | Tombol nonaktif + alasan bila tidak ada mutasi; asal tiap baris dicatat (`import_source`: berkas/tempel/contoh, pengunggah, nama berkas); layar menulis "Impor terakhir: {berkas} oleh {nama}" atau "n baris data contoh — bukan unggahan Anda"; Cocokkan otomatis atas mutasi yang tidak pernah diunggah minta konfirmasi dulu | selesai |
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
| M27 | BOM: nama bebas, kenapa perlu nama? | Nama wajib bebas; tidak ada versi/utama; Rute Produk mengambil BOM aktif sembarang | Isian nama dihapus; kode sistem "BOM {SKU} v{n}"; versi per produk; satu BOM utama ("Jadikan utama", BOM pertama otomatis utama, menonaktifkan utama → versi aktif terbaru naik); usulan Rute Produk & pilihan perintah kerja memakai BOM utama; BOM lama diberi versi + kode saat start (nama lama tetap tampil) | selesai |
| M28 | Master produk simpan HPP? | Katalog menampilkan `harga_pokok` manual berlabel "HPP" | Tab Informasi produk: "HPP (rata-rata stok)" dari biaya roll hidup (per varian & induk, "dari n {satuan} berbiaya"); `harga_pokok` berganti label "HPP perkiraan (cadangan)"; angka biaya hanya untuk pemegang izin HPP | selesai |
| M30 | Eskalasi Gudang relevan? | Eskalasi manual; menu terpisah mengulang meja | Kartu "Perlu keputusan — eskalasi gudang" di Meja Saya Manajer/Gudang/Admin (izin putus gudang), tugas dieskalasi keluar dari antrean kerja petugas; menu dihapus, layar keputusan dibuka dari kartu | selesai |
| M5 | Meja MD belum lengkap | Tidak ada SPK makloon, PO bahan; PR salah nama field | Kartu baru: SPK makloon berjalan (mitra · tahap), SPK makloon menunggu faktur mitra, PO bahan berjalan; PR kini juga yang disetujui belum direalisasi, judul/pemasok/pengaju/nilai dari field yang benar; baris membuka Order Makloon tersorot | selesai |
| M6 | POS: limit kredit total & terpakai | Bilah pelanggan tanpa angka kredit | Chip di bilah pelanggan POS: Plafon · terpakai (eksposur) · sisa, merah bila lewat plafon; tetap tampil walau gerbang kredit PT dimatikan | selesai |
| M19 | Pelanggan: plafon, sales PJ "—" | Pop-up dari data dasbor mentah; sales PJ hanya dari `assigned_sales_id` | Pop-up Pelanggan: plafon + terpakai dari status kredit; sales PJ jatuh ke PIC tim sales (server & pop-up). Pop-up melayang (M18) menyusul di gelombang tata letak | selesai |
| M21 | Riwayat harga beli pelanggan | Riwayat hanya harga yang diatur | Bagian "Pernah dibeli" di Riwayat Harga: tanggal, SO, qty, harga (coret harga normal bila lebih murah), asal harga (harga khusus/pelanggan/PT/umum/kontrak pesanan khusus); pesanan batal & sample tidak dihitung | selesai |
| M42 | Jejak Dokumen: tampilkan daftar | Cari minimal 2 huruf; alat admin di layar utama | Tanpa kata cari = daftar dokumen terbaru lintas jenis (diurut tanggal); paragraf penjelasan pindah ke tooltip; alat admin pindah ke kaki halaman (terlipat, pemegang izin) | selesai |

## B. Tata letak (pola `04_POLA_UI.md`, per gelombang)

| # | Masukan | Status |
|---|---|---|
| M1, M4 | Meja tetap terbuka, sama tinggi, cari/saring/urut/paginasi per kartu; Keep & Pending satu baris | selesai (pilot `008aa68`) |
| M23 | Retur kacau | selesai (pilot) |
| M24 | Chip saringan → dropdown | selesai: komponen bersama `FilterSelect` (dropdown berhitungan) dipakai di semua daftar — lini, Retur, Pengaturan, Pesanan, Pesanan Khusus, R&D, permintaan desain, transfer, 13 layar keuangan & pembelian, 11 layar lain, SPK Inspeksi, Barang Masuk/Keluar/Cutting, PO/PR/Tagihan/Order Makloon/Retur Supplier. Pengalih bagian/mode (kartu 360, metode opname, mode alokasi bayar, tampilan roll) sengaja tetap |
| M43 | Semua menu Pengaturan | selesai: Ketegasan & semua kelompok (pilot `008aa68`); Hak akses per peran = matriks tanpa gulir mendatar, Peran & Hak Akses satu bilah, Aturan Persetujuan & Kontrol dua orang = daftar padat ubah-di-baris (`df4edf6`) |
| M3 | Tanya KN layar penuh, riwayat bisa disembunyikan | selesai: satu bidang kerja setinggi layar (tanpa kartu-kartu), panel laporan & riwayat bisa disembunyikan (diingat per peramban), strip aturan jadi baris tipis |
| M8, M32 | Kartu angka relevan & bisa diklik (Portal, Beranda Keuangan) | selesai: beranda tanpa "Jml Tersedia"/"Gudang" (M8); Beranda Keuangan — semua kartu menuju laporan/daftar terkait (M32, `02c6c4e`); Rekonsiliasi Bank — kartu hitungan = saringan |
| M14, M15 | Lini masa vertikal Pesanan Khusus | selesai: satu lini masa vertikal (✓/●/○, tanggal & pelaku, "berjalan sejak … (n hari)", dokumen tahap dilebur dari Rantai dokumen, aksi hanya di tahap berjalan, tahap selesai dilipat bila > 3) |
| M17 | Tab status Pesanan → dropdown | selesai: dropdown "Tahap" (jumlah · nilai) di bilah daftar; kepala kartu ganda dihapus |
| M18 | Pop-up melayang (Pelanggan) | selesai: rincian = panel tetap di kanan, konten diberi ruang (tidak menutupi tabel) |
| M20 | Produk & Harga: alat admin dipindah | selesai (`657605f`): katalog bersih (kepala satu baris, satu bilah: cari · tahap · lini · status · saringan lain · jumlah · Alat data master ▾ · Tambah produk); alat tata kelola/perbaikan/sumber restock pindah ke halaman admin tersendiri (pemegang izin) |
| M22 | Rincian produk | selesai (`657605f`): kepala rincian = nama · SKU · status · aksi; kartu kosong dihapus (spek satu baris); label manusiawi; peringatan desain satu baris + tautan; Hapus permanen di menu Lainnya (nonaktif + alasan bila dipakai) |
| M26 | Barang Masuk/Keluar/Cutting satu pola | selesai (`ba42d6d`): Barang Masuk / Keluar / Cutting satu pola (kepala satu baris + ?, bilah Cari → Status ▾ → Jenis ▾ → Gudang ▾ → jumlah → aksi; panel rincian hanya saat baris dipilih; satu tombol buat) |
| M29 | Lokasi Rak | selesai (`ba42d6d`): kepala satu baris + ?, kartu angka membuka tabnya, antrean putaway jadi tabel berkolom |
| M35 | Tombol buat di banyak tempat | selesai untuk Antar-PT (satu tombol per tab di bilah daftar, `02c6c4e`), Transfer, Pesanan Khusus; layar Pembelian di gelombang agen |
| M36, M37 | Bagan Akun & Antar-PT boros; pemilih PT dobel berwarna lain | selesai (`02c6c4e`): kepala satu baris, satu bilah daftar, kartu angka = saringan; lingkup Bagan Akun ikut PT di bilah atas (Template Global = satu opsi dropdown), chip ungu dihapus |
| M40 | Lembar Insentif boros | selesai (`02c6c4e`): kepala satu baris + ?, satu bilah (cari · periode · status dropdown · jumlah · Buat lembar), tabel padat |

## C. Pertanyaan untuk pemilik
1. ~~M38~~ — dijawab 17 Nov: temuan (bisa mencocokkan tanpa mengunggah berkas) → diperbaiki.
