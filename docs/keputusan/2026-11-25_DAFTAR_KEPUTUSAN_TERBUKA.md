# Daftar keputusan terbuka — 25 Nov 2026

Semua pertanyaan yang menunggu pemilik, masing-masing dengan rekomendasi dan alasannya. Jawab per nomor:
"setuju", "tidak", atau nilai lain. Contoh: "semua setuju kecuali C6 = 2 juta".

Sumber:
- `docs/audit/meja-2026-11-25/` dan `docs/superpowers/specs/2026-11-25-meja-kerja-di-tempat-design.md` (meja);
- `docs/audit/kas-bank-otomasi-2026-11-25/` (tunai, bank, OCR, otomasi);
- `docs/superpowers/plans/2026-11-25-batal-tutup-sisa-pesanan-hasil.md` (sebelum update VPS).

## A. Perombakan Meja

| No | Pertanyaan | Rekomendasi | Alasan |
|---|---|---|---|
| A0 | Setujui rancangan meja (pop-up rincian, kartu tetap 5 baris, tab Pantau, satu nama, konfirmasi aksi besar, huruf ≥ 12 px)? | **Setuju** | Isinya keputusan Bapak 25 Nov; sisanya rincian teknis. |
| A1 | "Perlu Tindakan" di Keuangan diganti nama "Meja Keuangan"? | **Ya** | Semua meja lain bernama "Meja …"; sekarang satu layar punya 4 sebutan. |
| A2 | Pelacak SO tetap ada di tab Pantau semua meja yang boleh melihat pesanan, dan barisnya bisa dibuka? | **Ya** | Setiap peran tetap bisa menjawab "pesanan ini sampai mana", tanpa mengganggu antrean kerja. |
| A3 | Tab Pantau tetap bisa ditindak (bukan hanya dilihat)? | **Ya** | Bila hanya-baca, orang harus pindah menu lagi untuk bertindak. Itu yang mau dihilangkan. |
| A4 | Persetujuan bayar sample tampil di Meja Keuangan **dan** Meja Sample, tidak lagi di meja Manajer? | **Ya** | Kewenangan memutusnya ada di Finance dan Admin Sample. Di meja Manajer hanya membingungkan. |
| A5 | Di Meja Keuangan, pesanan lewat tempo hanya tampil di kartu "Piutang lewat jatuh tempo", tidak diulang di "Uang masuk"? | **Ya** | Sekarang 5 pesanan yang sama tampil di dua kartu. Pop-up-nya tetap menyediakan "Terima pembayaran" dan "Tagih". |
| A6 | Konfirmasi aksi besar (terbit faktur pajak, setujui bayar, lepas ke gudang) dipasang juga di layar asalnya, misalnya layar Pesanan? | **Ya** | Bahayanya sama di mana pun tombolnya. Satu komponen, satu perilaku. |
| A7 | Panel rincian yang dipakai di pop-up ikut diseragamkan hurufnya, sehingga layar Pesanan/Pembelian/R&D juga berubah? | **Ya** | Bila tidak, pop-up meja tetap campur aduk hurufnya. Pekerjaan bertambah, tapi hasilnya seragam di seluruh aplikasi. |
| A8 | Di HP, kartu meja tetap bisa dibuka-tutup (ukuran tetap hanya di desktop)? | **Ya** | Layar HP sempit; kartu kosong setinggi 5 baris akan memaksa gulir panjang. |
| A9 | Pekerjaan berhenti untuk Bapak periksa hanya sesudah gelombang 1 (kerangka); gelombang 2–3 jalan terus dengan tangkapan layar di akhir? | **Ya** | Kerangka adalah dasar semuanya. Sesudah itu isi pop-up per meja bisa jalan tanpa menunggu. |

## B. Lapor Bayar CBD (sudah diputus: tahan sebelum gudang)

| No | Pertanyaan | Rekomendasi | Alasan |
|---|---|---|---|
| B1 | Invoice (Faktur Komersial) dan kode bayar pesanan CBD/DP tersedia **sejak pesanan disetujui**, berstatus "Belum dibayar"? | **Ya** | Sekarang invoice dan kode bayar baru ada setelah dilepas ke gudang. Dengan tahan sebelum gudang, pelanggan tidak bisa menerima invoice berkode sebelum membayar. |
| B2 | Batas waktu bayar pesanan CBD yang sudah disetujui: lewat batas → kedaluwarsa otomatis, stok dilepas, uang yang sempat masuk jadi titipan? | **Ya, bawaan 3 hari** (bisa diubah per PT), sales diingatkan H-1 | Sekarang pesanan yang sudah disetujui tidak pernah kedaluwarsa, jadi stok bisa terkunci selamanya. |
| B3 | Untuk pembayaran **transfer** CBD, sales tidak lagi mencatat kwitansi langsung, cukup "Lapor bayar" (foto bukti)? | **Ya** | Jurnal hanya terbit untuk uang yang sudah dicek Finance. Itu tujuan fitur ini. |
| B4 | Isi Lapor bayar: foto/PDF bukti (wajib), nominal, tanggal transfer, rekening tujuan; Finance bisa Terima atau Tolak dengan alasan? | **Ya** | Cukup untuk dicocokkan dengan mutasi bank, tanpa form panjang. |
| B5 | Berlaku juga untuk termin DP (mis. DP 50%) pada bagian DP-nya? | **Ya** | Risikonya sama; satu alur lebih mudah dilatih. |
| B6 | Pengecualian "lepas tanpa bayar" (Finance/Manager/Admin, alasan wajib) tetap ada? | **Ya** | Untuk pelanggan tepercaya atau keadaan darurat; sudah ada jejak alasannya. |
| B7 | Sales tetap boleh memilih rekening tujuan dari rekening penerimaan PT (bukan dikunci ke satu rekening bawaan)? | **Ya, tetap boleh memilih** | Pelanggan beda bank, jadi transfer sesama bank lebih cepat dan murah. Daftar rekeningnya tetap diatur Finance. Rekening PT lain tidak pernah muncul. |

## C. Tunai & kas kecil

| No | Pertanyaan | Rekomendasi | Alasan |
|---|---|---|---|
| C1 | Pisahkan **kas kasir** (tunai dari pelanggan) dari **kas kecil** (dana operasional), masing-masing dengan akun sendiri? | **Ya** | Sekarang satu akun, sehingga tidak bisa dijawab "uang kasir hari ini berapa" vs "sisa kas kecil berapa". |
| C2 | Kas kecil memakai **dana tetap** per PT/lokasi, diisi ulang sebesar LPJ yang disetujui? | **Ya** | Saldo selalu bisa dicek (dana tetap = tunai + nota). Isi ulang jadi satu dokumen, tidak diketik manual. |
| C3 | **Opname kas**: kasir harian, kas kecil mingguan; selisih disetujui Finance, dibukukan ke akun selisih kas; kekurangan karena orang menjadi piutang karyawan? | **Ya** | Sekarang kas tunai tidak pernah dicocokkan sama sekali. |
| C4 | Sales **dilarang** mencatat penerimaan tunai di PT yang memang tidak menerima tunai di lapangan; PT yang menerima tunai memakai "titipan sampai disetor"? | **Ya** — sebutkan PT mana yang menerima tunai | Sekarang kwitansi tunai sales langsung menaikkan kas, padahal uangnya masih di tangan sales. Ini mengubah pengaturan PT nyata, jadi menunggu Bapak. |
| C5 | Kategori **"Pembelian"** dan **"Gaji"** dihapus dari kas manual? Barang lewat PO/tagihan, gaji lewat penggajian. | **Ya** | "Pembelian" langsung menaikkan Persediaan tanpa barang; "Gaji" membebankan gaji dua kali. |
| C6 | Kas keluar manual **di atas nominal tertentu** butuh persetujuan orang kedua? | **Ya, di atas Rp 1.000.000** (Bapak bisa ganti) | Jalur kas manual sekarang tanpa kontrol sama sekali, padahal risikonya terbesar. |
| C7 | Uang muka karyawan (PD): maksimal **1 PD terbuka** per orang dan LPJ wajib dalam **7 hari**? | **Ya** | Sekarang uang muka bisa menggantung tanpa peringatan. |
| C8 | Pisahkan akun uang muka pemasok dari uang muka karyawan (sekarang satu akun 1-1400)? | **Ya** | Saldo akun tidak bisa dicocokkan ke satu daftar. |

## D. Rekening bank ↔ bagan akun & pindah dana

| No | Pertanyaan | Rekomendasi | Alasan |
|---|---|---|---|
| D1 | **Satu akun buku besar per rekening** (sub-akun di bawah Kas & Bank)? | **Ya** | Saldo per rekening masuk buku besar, dan selisih buku besar vs rekening tidak bisa muncul lagi. |
| D2 | Dokumen **"Pindah Dana"** satu form: rekening asal, tujuan, nominal, biaya transfer, tanggal? | **Ya** | Sekarang dicatat sebagai dua kas manual lepas; satu sisi lupa = saldo salah tanpa ketahuan. |
| D3 | Setor tunai ke bank dan isi kas kecil **wajib** lewat Pindah Dana; kategori "Transfer/Top-up" di kas manual ditutup? | **Ya** | Satu jalan, satu jejak. |
| D4 | Pemindahan saldo lama ke akun per rekening: satu jurnal reklasifikasi per PT, disiapkan sistem, disetujui Finance? | **Ya** | Menyentuh data nyata, jadi perlu persetujuan. Cara ini tidak mengubah transaksi lama. |
| D5 | Uang antar-PT selain pinjaman/pelunasan (setoran modal, dividen) dibuatkan dokumen sendiri? | **Tunda** — cukup tambahkan biaya transfer ke jalur antar-PT yang ada | Jarang terjadi; jalur resmi antar-PT sudah ada. |

## E. Jurnal otomatis dari foto nota (OCR)

| No | Pertanyaan | Rekomendasi | Alasan |
|---|---|---|---|
| E1 | Dokumen pertama yang dibaca: **nota LPJ kas kecil**? | **Ya** | Paling sering, dan sudah ada persetujuan, kategori, dan lampirannya. |
| E2 | AI hanya **membaca angka**; akun dipilih sistem dari daftar tertutup, lalu ditandai yang mencurigakan? | **Ya** | AI tidak pernah menentukan akun, jadi salah akun bisa dicegah. |
| E3 | Hasil OCR selalu **disetujui manusia** (tidak langsung terposting)? | **Ya** | Versi pertama; bisa dilonggarkan setelah ketepatannya terbukti. |
| E4 | Memakai penyedia OCR yang sama dengan surat jalan pemasok, padahal foto nota memuat nama/NPWP pihak luar? | **Ya**, dengan sakelar per PT (bawaan mati) | Penyedianya sudah teruji di sistem; sakelar membuat tiap PT memilih sendiri. |
| E5 | Anggaran OCR per bulan per PT, dan ambang ketepatan sebelum dinyalakan? | **Rp 500.000/bulan per PT**, ketepatan ≥ 95% pada sampel uji (Bapak bisa ganti) | Biaya terkendali; tidak dinyalakan sebelum terbukti akurat. |
| E6 | PPN di nota kas kecil (PT PKP) di versi pertama? | **Dibebankan penuh + ditandai** | Pengkreditan pajak masukan dari nota kecil butuh keputusan pajak tersendiri (Coretax masih ditahan). |
| E7 | Masa simpan foto nota? | **10 tahun** | Sesuai kewajiban simpan dokumen pajak (UU KUP). |

## F. Otomasi pekerjaan berulang

| No | Pertanyaan | Rekomendasi | Alasan |
|---|---|---|---|
| F1 | **Kwitansi otomatis dari mutasi bank** yang kode bayar dan nominalnya cocok sempurna: otomatis penuh atau kartu siap-setuju? | **Otomatis penuh** untuk yang cocok sempurna, sisanya kartu | Penghemat waktu terbesar (tiap transfer pelanggan). Cocok sempurna = risiko salah sangat kecil, dan tetap bisa dibatalkan. |
| F2 | **Jurnal berulang/templat** (sewa, akrual, dsb.) lahir sebagai **draf** tiap akhir bulan, lalu disetujui? | **Draf + setuju** | Jurnal salah yang berulang tiap bulan berbahaya; draf tetap memangkas ketik ulang. |
| F3 | **Aturan bank**: biaya admin, bunga, dan autodebet rutin dibukukan otomatis saat mutasi diimpor? | **Ya**, aturan diusulkan sistem, disetujui Finance, dengan batas nominal per aturan | Baris rutin bulanan per rekening tidak perlu diklik satu per satu. |
| F4 | **Tagihan biaya tanpa PO** (sewa, listrik, jasa, ekspedisi) + tagihan berulang, dibuat Finance, persetujuan dua orang di atas batas? | **Ya** | Sekarang tagihan wajib PO, jadi biaya rutin lari ke kas manual tanpa kontrol. |
| F5 | Urutan otomasi? | **F1 → F2 → E (OCR) → F3 → F4**, lalu bayar hutang massal, tutup bulan satu tombol, pengingat tagihan otomatis | Diurut dari penghematan terbesar dan bahan yang sudah paling siap. |

## G. Urutan kerja keseluruhan

| No | Pertanyaan | Rekomendasi | Alasan |
|---|---|---|---|
| G1 | Urutan? | **Meja gelombang 1 → Meja gelombang 2 (+ detail barang di layar Keuangan) → Lapor Bayar CBD → Kwitansi otomatis dari mutasi (F1) → Paket Kas & Bank (C, D) → Meja gelombang 3 → otomasi lain** | Meja dan Lapor Bayar paling terasa harian. F1 menyempurnakan Lapor Bayar. Kas & Bank butuh keputusan data per PT, jadi dirancang sambil menunggu jawaban C4/D4. |
| G2 | Rancangan perombakan notifikasi (ditunda sebelumnya)? | **Sesudah Lapor Bayar** | Lapor Bayar menambah notifikasi ke Finance; perombakan sekaligus merapikan yang baru. |
| G3 | VA (virtual account) bank? | **Tunda** | Kode bayar di berita transfer + kwitansi otomatis dari mutasi (F1) memberi hasil serupa tanpa biaya Rp 4.000-an per transaksi. Ditinjau lagi bila pencocokan masih banyak manual. |

## H. Sebelum update VPS (fitur tutup sisa & persetujuan pembatalan sudah di `main`)

| No | Pertanyaan | Rekomendasi | Alasan |
|---|---|---|---|
| H1 | Koreksi komisi memakai pengali capaian bulan penutupan (batasan versi pertama)? | **Terima untuk sekarang**; ditinjau ulang sebelum pengali capaian dinyalakan | Pengali capaian masih mati bawaan, jadi belum berpengaruh. |
| H2 | Tidak ada pengisian ulang data lama; bulan sebelum rilis dianggap final dari jurnal akrual/gaji yang berlaku? | **Setuju** | Tidak menulis data nyata; hasilnya sama dengan maksud aturan. |
| H3 | Run gaji **draf** yang dibuat sebelum update dihitung ulang sesudah update? | **Ya** | Saldo potongan baru tercatat saat dihitung. |
| H4 | Perbandingan komisi sebelum/sesudah pada data acuan sebelum update? | **Ya** | Memastikan angka komisi lama tidak berubah tanpa sengaja. |
| H5 | Peran kustom yang harus bisa menyetujui pembatalan diberi izin "setujui pembatalan"? Admin/manager/finance otomatis. | **Ya** — sebutkan perannya | Peran kustom tidak otomatis mendapat izin baru. |
