# Keputusan yang dibutuhkan dari pemilik

Satu daftar untuk semua dokumen rencana. K-01 … K-18 sama dengan §10 laporan audit (nomor tidak berubah); K-19 … K-46
baru dari perencanaan ini.

Cara menjawab yang paling ringkas: **"setuju semua usulan, kecuali K-xx: …"**. Jawaban dicatat di kolom terakhir (tanggal
+ isi), dan paket yang tertahan boleh dimulai. Kolom "Menahan" menyebut pekerjaan yang tidak boleh jalan sebelum dijawab.

Urutan menjawab yang disarankan: kelompok A (membuka paket fondasi terbanyak), lalu kelompok sesuai modul yang ingin
dibangun lebih dulu.

## A. Fondasi (dari laporan audit)

| No | Pertanyaan | Usulan | Menahan | Jawaban |
|---|---|---|---|---|
| K-01 | Arsitektur database: tetap MongoDB + replica set satu node + perkeras; atau PostgreSQL lebih awal? | Tetap MongoDB, urutan di laporan audit §9.3 | PK-34, PK-35 | |
| K-02 | Akun kontrol (piutang, hutang, persediaan, antar-PT) ditutup dari jurnal manual? | Ya, koreksi lewat dokumennya | PK-36; asisten menulis jurnal | |
| K-03 | Periode tertutup ikut mengunci dokumen, pembayaran, dan mutasi stok — atau hanya jurnal? | Ikut mengunci | PK-37 (butir kunci dokumen) | |
| K-04 | "Wajib dua orang" untuk buka periode dan jurnal manual berlaku juga bagi admin? | Ya, tanpa pengecualian | PK-38 | |
| K-05 | Landed cost setelah barang terjual: porsi terjual ke HPP periode berjalan atau ke akun varians? | HPP periode berjalan | PK-26 | |
| K-06 | True-up persediaan dibatasi untuk saldo awal saja? | Ya | PK-29 (butir true-up) | |
| K-07 | Antar-PT, roll lebih panjang dari pesanan: dokumen menyesuaikan panjang aktual, atau transfer ditolak? | Dokumen menyesuaikan | PK-30 (IC-02) | |
| K-08 | PT mana yang PKP; ekspor Coretax dan PPh 23 + bukti potong masuk lingkup? | — (fakta dari pemilik) | PK-40 (ekspor), TX-T3 | |
| K-09 | Peran Finance mendapat menu Hutang, Rekonsiliasi Bank, Buku Besar? | Rekonsiliasi ya; Hutang mengikuti K-17; Buku Besar hanya lihat | PK-44, MN-T1 | |
| K-10 | Semua PT 100 % satu pemilik, atau perlu persentase kepemilikan di konsolidasi? | — (fakta dari pemilik) | PK-31 | |
| K-11 | Satu batas wewenang dan pembuat ≠ penyetuju untuk semua pengurang piutang tanpa kas (hapus sisa, kasus, nota kredit)? | Ya | PK-38 | |
| K-12 | Anggaran: cukup memperingatkan atau memblokir; dokumen apa saja yang dicakup? | Memperingatkan; mencakup PO, faktur non-PO, kas, LPJ | PK-39 (FY-12) | |
| K-13 | Tanggal jurnal periodik (penyusutan, gaji, insentif): akhir periode atau hari posting? | Akhir periode | PK-22 (FY-02) | |
| K-14 | Nota debit kenaikan harga: aturan tagihnya? Ganti termin ke yang lebih longgar butuh izin setara pelepasan? | Tagih sebagai baris tagihan baru; ganti termin = perlu izin | PK-32 (FX-15), PK-38 | |
| K-15 | Laporan mode "Semua Entitas": memakai konsolidasi (dengan eliminasi) atau tetap penjumlahan berlabel? | Berlabel dulu (PK-16), konsolidasi setelah PK-31 | Hanya versi konsolidasi | |
| K-16 | Umur piutang dihitung per surat jalan, per baris rencana, atau per pesanan? | Per surat jalan; per baris rencana untuk cicilan; DP sebelum kirim (`06` §3.2) | PK-41 (RP-03), CR-T2 | |
| K-17 | Siapa yang membayar hutang dan mencairkan uang muka: Finance atau Manajer/Admin? | Finance membayar, Manajer menyetujui | PK-24 (IA-05), PK-44 | |
| K-18 | Peran non-keuangan boleh melihat nominal dokumen keuangan di Jejak Dokumen? | Tidak | PK-17 (IA-01) | |

## B. Insentif (`05`)

| No | Pertanyaan | Usulan | Menahan | Jawaban |
|---|---|---|---|---|
| K-19 | Omzet untuk insentif diakui saat pesanan dibuat, barang dikirim, atau lunas? Dengan atau tanpa PPN? | Barang terkirim, tanpa PPN, dikurangi retur | KM-T1 | |
| K-20 | "Pencairan" memuat apa? (pemakaian deposit, titipan bank, saldo kredit dari retur, hapus sisa, giro belum cair) | Hanya uang yang benar-benar masuk dan sudah dialokasikan; giro saat cair | KM-T1 | |
| K-21 | Pemilik angka: sales pada pesanan saat transaksi, atau pemilik pelanggan saat ini? | Sales pada pesanan (dengan pembagian tim) | KM-T1 | |
| K-22 | Komisi otomatis per SKU dan "Komisi MTD": dimatikan dan diganti lembar insentif? Beban diakui saat lembar disahkan? | Ya untuk keduanya, per PT saat PT itu beralih | KM-T4, PK-22 (FY-08) | |
| K-23 | Harga pembanding "harga normal": harga daftar PT, harga umum, atau harga langganan? Harga langganan yang disetujui dihitung potongan? | Harga daftar PT pada tanggal pesanan; harga langganan tetap dibandingkan dengannya | KM-T1 | |
| K-24 | "Tiga bulanan" = triwulan kalender, mengikuti tahun buku, atau tiga bulan bergulir? Target triwulan/tahun angka sendiri atau jumlah bulanan? | Mengikuti tahun buku; angka sendiri | KM-T1 | |
| K-25 | Siapa menyiapkan dan siapa memutuskan nominal? Retur atau kwitansi batal setelah insentif dibayar: ditarik kembali? | Penyiap admin penjualan/keuangan; pemutus pemilik/manajer; koreksi sebagai baris penyesuaian periode berikut | KM-T3 | |
| K-26 | Sales yang menjual untuk lebih dari satu PT: siapa membayar, dan ditagihkan antar-PT? | PT penjualan mengakui beban; dibayar lewat gaji PT induk; selisih lewat dokumen antar-PT | KM-T4 | |

Pertanyaan pelengkap yang bisa dijawab saat KM-T2 berjalan: siapa boleh melihat margin; apakah pesanan sample, pelanggan
umum, dan penjualan tanpa sales ikut dihitung; adakah penerima selain sales.

## C. Piutang dan kredit (`06`)

| No | Pertanyaan | Usulan | Menahan | Jawaban |
|---|---|---|---|---|
| K-27 | Telat berapa hari mulai menahan pesanan; boleh berbeda per PT atau pelanggan? Pesanan tunai dari pelanggan yang ditahan: boleh? | Diatur per PT, bisa ditimpa per pelanggan; tunai boleh dengan barang ditahan sampai lunas | CR-T1, CR-T3 | |
| K-28 | Siapa berhak mengubah plafon dan membuka blokir; siapa menyetujui? | Sales dan Finance mengajukan; manajer/pemilik memutus menurut jenjang nominal | CR-T1 | |
| K-29 | Plafon per PT, atau gabungan grup untuk pelanggan yang sama? | Per PT, dengan kelompok kredit opsional lintas PT | CR-T1 | |
| K-30 | Denda otomatis terbit atau selalu usulan? Dasarnya sisa yang sudah dikirim dan jatuh tempo? | Usulan (draf) sebagai bawaan; dasar = sisa baris tagihan yang telat | CR-T4 | |
| K-31 | Eksposur untuk plafon memuat pesanan yang belum dikirim dan giro yang belum cair? Titipan mengurangi? | Ya, ya, ya — ditampilkan terperinci | CR-T2 | |

## D. Pajak dan pembayaran (`07`)

| No | Pertanyaan | Usulan | Menahan | Jawaban |
|---|---|---|---|---|
| K-32 | Faktur pajak terbit per pesanan, per surat jalan, atau per penerimaan uang muka? | Per surat jalan dan per uang muka — **konfirmasi konsultan pajak** | TX-T2 | |
| K-33 | Adakah pelanggan tanpa NPWP, kode transaksi selain yang sekarang, atau barang/jasa dengan perlakuan PPN berbeda? Boleh ada pesanan non-PPN di PT yang PKP, dan siapa memutuskan? | — (fakta dari pemilik); non-PPN hanya dengan izin khusus | TX-T1 | |
| K-34 | Rekening mana untuk penerimaan pelanggan di tiap PT; berbeda per pelanggan, lokasi, atau jenis pesanan? Cara bayar apa saja yang sah? | — (fakta dari pemilik) | PM-T1 | |
| K-35 | Bersedia memakai virtual account / QRIS dari bank atau penyedia? Nominal unik untuk pesanan bayar-dulu? | Tahap 1 tanpa penyedia (kode bayar + rekening tujuan); VA per pelanggan dipertimbangkan setelahnya | PM-T5 | |
| K-36 | Sales lapangan boleh menerima tunai? Batas dan tenggat setornya? | Tidak, sampai alur titipan dan setoran dibangun | PM-T4 | |

## E. HR dan penggajian (`09`)

| No | Pertanyaan | Usulan | Menahan | Jawaban |
|---|---|---|---|---|
| K-37 | Komponen gaji apa saja per PT (tetap atau per hari hadir), mana yang kena pajak, masuk dasar BPJS dan upah lembur? THR dan insentif triwulan dalam proses bulanan atau terpisah? | Daftar dari pemilik; THR proses terpisah; insentif ikut proses bulanan periode bayarnya | PY-T1 | |
| K-38 | Aturan prorata dan potongan (alpha, telat, cuti tanpa gaji, masuk/keluar tengah bulan); karyawan harian/borongan? | — (aturan dari pemilik) | PY-T3 | |
| K-39 | Lembur wajib pengajuan, atau otomatis dari absensi? Kalender libur dan 6 hari kerja per PT? | Wajib pengajuan | PY-T3 | |
| K-40 | Kasbon/pinjaman karyawan dipotong gaji? | Ya, lewat antrean masukan | PY-T1 | |
| K-41 | Perlu peran HR terpisah? Siapa menghitung, mengesahkan, membayar? Dari rekening mana, perlu berkas unggah bank? | HR menyiapkan; manajer/pemilik mengesahkan; Finance membayar dan menyetor | PY-T4 | |
| K-42 | Siapa memverifikasi tabel tarif PPh 21 (PY-03) sebelum penggajian dipakai untuk gaji nyata? Bila mulai di tengah tahun, bagaimana saldo awal pajak dimasukkan? | Konsultan pajak; isian saldo awal sekali | PK-46, PY-T3 | |

## F. Asisten keuangan (`08`) dan menu (`01`)

| No | Pertanyaan | Usulan | Menahan | Jawaban |
|---|---|---|---|---|
| K-43 | Penyedia model: tetap yang sekarang, pindah, atau lapisan yang bisa berganti? Nama pelanggan/supplier dan nominal boleh dikirim ke penyedia, atau disamarkan? | Lapisan yang bisa berganti; nama disamarkan sebagai bawaan | AG-T2 | |
| K-44 | Tindakan apa yang boleh lewat asisten, batas nominal tanpa penyetuju kedua, siapa penyetuju kedua? | Tahapan di `08` §4.3; golongan C selalu penyetuju kedua | AG-T3, AG-T5 | |
| K-45 | Siapa yang diberi akses asisten keuangan dan anggaran biayanya per bulan? | Bawaan mati per akun; dinyalakan pemilik | AG-T2 | |
| K-46 | Setuju susunan menu baru (10 entri dalam 2 grup untuk keuangan; Hutang pindah ke Keuangan; Kinerja & Insentif di SDM)? | Ya | MN-T1 | |

## Yang bisa berjalan tanpa keputusan apa pun

PK-01, 02, 03, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 23, 25, 27, 28, 33, 42, 43; sebagian besar
PK-16, PK-17, PK-22, PK-24, PK-45; AG-T1; KM-T2 dalam mode "tampilkan ketiga dasar omzet berdampingan" sambil menunggu K-19.
