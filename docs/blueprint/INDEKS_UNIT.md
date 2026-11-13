# Indeks unit kerja

Daftar induk semua unit blueprint, **dalam urutan pengerjaan**. Spesifikasi tiap unit ada di `unit/<ID>.md`. Papan
status yang diubah agen ada di `STATUS.md`; berkas ini tidak diubah saat eksekusi kecuali ada unit baru atau pecahan.

Kolom "Henti" merujuk titik henti di `00_ATURAN_EKSEKUSI.md` §6. Unit ber-"Henti" mulai dengan status `tahan`.
Kolom "Asal" menunjuk dokumen rancangan yang menjelaskan alasannya (`R` = `docs/finance/rencana-2026-11-13/`,
`A` = `docs/audit/konfigurasi-peran-2026-11-13/`).

Jalur: **F** fondasi keuangan · **P** peran dan izin · **K** pengaturan · **U** konfigurasi perusahaan · **M** menu ·
modul: **I** insentif · **G** penggajian · **C** piutang/kredit · **B** pembayaran · **X** pajak · **S** asisten.
Jalur P, K, U, M tidak bergantung pada pola posting, sehingga bisa berjalan selagi H1 menunggu reviewer.

## Gelombang 0 — persiapan

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 1 | PK-01 | Garis dasar gate dan pendaftaran temuan ke tracker | F | — | — | rendah | — | R/02 |
| 2 | PK-02 | Kerangka uji database tiruan + tes regresi dari bukti audit | F | PK-01 | — | rendah | — | R/02 |
| 3 | PK-03 | Cek data nyata (dijalankan pemilik) | F | — | — | rendah | H3 | R/02 |
| 4 | PK-04 | Cadangan lebih sering dan uji pulih | F | — | DB-03 | sedang | H2 | R/02 |

## Gelombang 1 — dua temuan kritis

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 5 | PK-05 | Bayar hutang pemasok lewat satu pintu yang aman | F | PK-02 | SL-01, SL-02, SL-12, GL-03, UX-10 | tinggi | H1 sesudahnya | R/02 |
| 6 | PK-06 | Jurnal kembar antar-PT yang utuh dan bisa diulang | F | PK-02 | IC-01, IC-08 | tinggi | H1 sesudahnya | R/02 |

## Gelombang 2 — tinggi yang murah

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 7 | PR-T1 | Tutup jalan menaikkan hak sendiri | P | PK-02 | PR-02, PR-13 | sedang | — | A |
| 7b | PR-T9 | Perubahan izin peran bawaan bertahan setelah server dinyalakan ulang; satu sumber izin bawaan | P | PK-02 | PR-12, PR-14 | sedang | — | A |
| 8 | KF-T1 | Izin kelola dan lihat pengaturan benar-benar berfungsi | K | PK-02 | KF-01, KF-02, KF-03 | sedang | — | A |
| 9 | PK-47 | Cacat kecil dari uji sapuan endpoint | F | PK-02 | KP-17, MB-01, MB-02, PR-10, PR-15 | rendah | — | A |
| 10 | PK-07 | Setoran karyawan pada kasus keuangan terbukukan dua kali | F | PK-02 | FX-01 | rendah | — | R/02 |
| 11 | PK-08 | Denda keterlambatan dihitung dan dijurnal dengan benar | F | PK-02 | FX-02, FX-03, FX-04 | sedang | — | R/02 |
| 12 | PK-09 | Entitas tidak boleh datang dari isi permintaan | F | PK-02 | IC-05, IC-11, SL-07, FX-08, FX-17, FY-15 | sedang | — | R/02 |
| 13 | PK-10 | Jurnal manual lewat validator pusat; satu penanda pembalik | F | PK-02 | GL-01, GL-07 | sedang | — | R/02 |
| 14 | PK-11 | Periode yang belum berakhir tidak bisa ditutup | F | PK-02 | GL-04 | rendah | — | R/02 |
| 15 | PK-12 | Kunci idempotensi dan penahan klik ganda di semua form uang | F | PK-02 | UX-01, UX-02, GL-08, FY-18 | sedang | — | R/02 |
| 16 | PK-13 | Konfirmasi untuk aksi uang sekali klik | F | PK-02 | UX-03, FY-17 | rendah | — | R/02 |
| 17 | PK-14 | Indeks unik wajib ada | F | PK-02 | GL-09, IC-12, FX-19 | sedang | H6 bila data kembar | R/02 |
| 18 | PK-15 | Alokasi titipan bank dan biaya bank | F | PK-02 | SL-03, SL-04 | sedang | — | R/02 |
| 19 | PK-16 | Laporan menyebut PT-nya; mode gabungan diberi label | F | PK-02 | UX-06, UX-07, UX-14, RC-01, RP-02, RP-04 | rendah | — | R/02 |
| 20 | PK-17 | Nominal keuangan hanya untuk yang berizin | F | PK-02 | IA-01, IA-02, IA-03, IA-09 | sedang | — | R/02 |
| 21 | PK-45 | Penjaga cepat: plafon, faktur pajak, gaji | F | PK-02 | CR-01, TX-01, TX-02, TX-03, TX-04, PY-05, PY-10 | sedang | — | R/02 |
| 22 | PK-46 | Tabel tarif PPh 21 dari pengaturan bertanggal berlaku | F | PK-02 | PY-03, KP-36 | sedang | H4 untuk memuat tabel dari pemilik | R/02 |

## Jalur peran, pengaturan, konfigurasi perusahaan, menu (boleh berjalan sejajar dengan gelombang 3–7)

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 23 | PR-T2 | Wewenang dari izin, bukan nama peran acuan | P | PR-T1, PR-T9 | PR-01, PR-03 | tinggi | — | A |
| 24 | PR-T3 | Endpoint yang hanya butuh login: dipilah dan dijaga | P | PR-T2 | PR-04 | sedang | — | A |
| 25 | KF-T6 | Kontrol dua orang yang bisa diatur per PT | K | KF-T1 | KP-05, GL-06 | tinggi | — | A |
| 26 | KP-T3 | Aturan Persetujuan: buang pilihan palsu, tampilkan jenjang efektif | U | KF-T1 | KP-03, KP-04, KP-08 | sedang | — | A |
| 27 | KP-T4 | Satu tabel kebijakan persetujuan untuk semua antrean | U | KF-T6, KP-T3, PR-T2 | KP-06, KP-07, KP-25, KP-26, PR-05 | tinggi | — | A |
| 28 | PR-T4 | Sifat peran yang bisa diatur: cakupan data, beranda, penerima notifikasi | P | PR-T2 | PR-06 | tinggi | — | A |
| 29 | PR-T5 | Katalog izin dirapikan; modul akses dipecah | P | PR-T2 | PR-07, PR-08 | sedang | — | A |
| 30 | PR-T6 | Layar Peran & Hak Akses dan Akun & Akses | P | PR-T4, PR-T5 | PR-09, PR-UX | sedang | — | A |
| 31 | PR-T7 | Layar memakai izin, bukan nama peran | P | PR-T2 | PR-11, PR-16 | sedang | — | A |
| 32 | PR-T8 | Penjaga matriks izin berjalan (peran × endpoint) | P | PR-T3 | — | rendah | — | A |
| 33 | KF-T2 | Kunci pengaturan mati, ganda, dan tersembunyi | K | KF-T1 | KF-05, KF-06, KP-13, KP-29, KP-30 | sedang | — | A |
| 34 | KF-T3 | Layar menampilkan nilai yang dipakai mesin; jadwal diaktifkan penjadwal | K | KF-T1 | KF-04, KF-09, KF-10, KF-11, KP-11 | tinggi | — | A |
| 35 | KF-T4 | Bahasa, pengelompokan, dan editor Pusat Pengaturan | K | KF-T2 | KF-12, KF-13, KF-UX | sedang | — | A |
| 36 | KF-T5 | Pengaturan per pelanggan dan per barang punya layar | K | KF-T1 | KF-07 | sedang | — | A |
| 37 | KF-T7 | Nilai bisnis yang ditulis mati menjadi pengaturan | K | KF-T2 | KP-27, KP-28, CR-03 | sedang | — | A |
| 38 | KF-T8 | Penjaga pengaturan: uji putaran semua kunci menjadi gate | K | KF-T2 | KF-08 | rendah | — | A |
| 39 | KP-T1 | Profil PT yang jujur dan bisa diubah | U | KF-T1 | KP-01, KP-02, KP-23 | sedang | — | A |
| 40 | KP-T2 | Kesiapan PT, wizard lanjutan, dan arsip PT | U | KP-T1 | KP-10, KP-22, KP-24 | sedang | — | A |
| 41 | KP-T5 | Penomoran dokumen per PT | U | KP-T1 | KP-12, KP-35 | tinggi | H3 untuk dokumen lama | A |
| 42 | KP-T6 | Dokumen dan cetak per PT | U | KP-T1 | KP-18, KP-19, KP-34 | sedang | — | A |
| 43 | KP-T7 | Pengingat dan penjadwal yang bisa diatur | U | KF-T1 | KP-09, KP-20, KP-21 | sedang | — | A |
| 44 | KP-T8 | Rahasia dan perangkat | U | KF-T1 | KP-14, KP-15, KP-16, KP-31, KP-32 | sedang | — | A |
| 45 | MN-T1 | Menu keuangan dan SDM: pindah dan kelompokkan | M | PR-T5 | UX-17, IA-06, IA-15 | sedang | — | R/01 |
| 46 | KP-T9 | Susunan hub Pengaturan | M | MN-T1, KF-T4 | KP-33 | sedang | — | A |

## Gelombang 3 — pola posting (menunggu H1)

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 47 | PK-18 | Penanda gagal dan panel untuk semua jenis dokumen | F | PK-05, PK-06 tervalidasi | GL-02, GL-12, IV-04, UX-04 | tinggi | — | R/02 |
| 48 | PK-19 | Kwitansi, deposit, selisih bayar: satu fungsi alokasi | F | PK-18 | SL-05, SL-06, SL-08, SL-14, FX-05, FX-06, FX-07, IA-07 | tinggi | — | R/02 |
| 49 | PK-20 | Kas dibuat lewat satu pembuat | F | PK-18 | SL-11 | tinggi | — | R/02 |
| 50 | PK-21 | Rekonsiliasi bank satu mekanisme | F | PK-15 | SL-10 | sedang | — | R/02 |
| 51 | PK-22 | Penggajian: tanggal buku, hitung ulang, batal, setoran kewajiban | F | PK-18 | FY-02, FY-06, FY-07, FY-08, FY-09 | tinggi | — | R/02 |
| 52 | PK-23 | Aset tetap | F | PK-06, PK-18 | FY-01, FY-03, FY-04, FY-05, FY-20 | tinggi | — | R/02 |
| 53 | PK-24 | Kas kecil dan pertanggungjawaban | F | PK-18 | SL-09, FY-13, FY-14, FY-19, IA-05 | sedang | — | R/02 |
| 54 | PK-25 | Kasus keuangan: periksa dulu, efek kemudian | F | PK-09, PK-19 | FX-09, FX-11, FX-18 | sedang | — | R/02 |

## Gelombang 4 — nilai persediaan dan antar-PT

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 55 | PK-26 | Landed cost untuk roll yang sudah terjual | F | PK-18 | IV-01, IV-10 | tinggi | — | R/02 |
| 56 | PK-27 | Biaya roll pada scrap, retur, dan HPP | F | PK-18 | IV-02, IV-06, IV-07, IV-08 | tinggi | — | R/02 |
| 57 | PK-28 | GR/IR: varians, umur, kliring | F | PK-18 | IV-03 | tinggi | — | R/02 |
| 58 | PK-29 | Rekonsiliasi persediaan per PT; true-up dibatasi | F | PK-27 | IV-05, IV-09, GL-13 | sedang | — | R/02 |
| 59 | PK-30 | Antar-PT: panjang aktual, jalur lama, harga dan PPN | F | PK-06 | IC-02, IC-09, IC-10 | tinggi | — | R/02 |
| 60 | PK-31 | Eliminasi per periode; rantai A→B→C; retur setelah lunas | F | PK-30 | IC-03, IC-04, IC-07, RP-10 | tinggi | — | R/02 |
| 61 | PK-32 | Nota kredit satu mesin | F | PK-19 | FX-12, FX-13, FX-14, FX-15 | tinggi | — | R/02 |

## Gelombang 5 — infrastruktur

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 62 | PK-33 | Hijaukan penjaga atomisitas | F | PK-19, PK-20 | DB-01 | sedang | — | R/02 |
| 63 | PK-34 | Replica set satu anggota, transaksi di jalur uang, pustaka database | F | gelombang 3 tervalidasi (PK-18 … PK-25; dengan sendirinya PK-05, PK-06) | DB-04 | tinggi | H2 | R/02 |
| 64 | PK-35 | Uang sebagai bilangan bulat; validator; penomoran jurnal | F | PK-34 | DB-02, IV-11, GL-11 | tinggi | H2, H3 | R/02 |

## Gelombang 6 — kontrol

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 65 | PK-36 | Akun kontrol tertutup dari jurnal manual | F | PK-10 | IC-06, GL-10 | sedang | — | R/02 |
| 66 | PK-37 | Tanggal buku WIB dan kunci periode untuk dokumen | F | PK-11 | GL-05 | tinggi | — | R/02 |
| 67 | PK-38 | Satu batas wewenang; izin bayar terpisah; ganti termin | F | KF-T6, PR-T2 | FX-10, FX-16, IA-08, IA-12 | sedang | — | R/02 |
| 68 | PK-39 | Anggaran | F | PK-18 | FY-10, FY-11, FY-12 | sedang | — | R/02 |
| 69 | PK-40 | Pajak: keunikan, masa pajak, basis | F | PK-14 | SL-13, FY-16 | sedang | — | R/02 |

## Gelombang 7 — laporan dan layar

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 70 | PK-41 | Laporan pendukung | F | PK-19 | RP-01, RP-03, RP-05, RP-06, RP-07, RP-08, RP-09, RP-11, RP-12 | tinggi | — | R/02 |
| 71 | PK-42 | Layar: perbaikan cepat per berkas | F | PK-12 | UX-05, UX-09, UX-11, UX-12, UX-18 | rendah | — | R/02 |
| 72 | PK-43 | Layar: struktural | F | PK-06, PK-19 | UX-08, UX-13, UX-15, UX-16 | sedang | — | R/02 |
| 73 | PK-44 | Jejak dokumen dan relasi dokumen | F | MN-T1 | IA-04, IA-10, IA-11, IA-13, IA-14 | sedang | — | R/02 |

## Modul

| # | ID | Judul | Jalur | Prasyarat | Menutup | Risiko | Henti | Asal |
|---|---|---|---|---|---|---|---|---|
| 74 | PM-T1 | Induk cara bayar dan rekening ber-peruntukan | B | KF-T1 | PM-03, PM-05 | sedang | — | R/07 |
| 75 | CR-T1 | Profil kredit per pelanggan per PT | C | PK-45, KF-T6, KF-T7 | — | sedang | — | R/06 |
| 76 | KM-T1 | Data insentif: omzet terkirim, pencairan, harga acuan, target | I | PK-19 | KM-01, KM-02, KM-03, KM-04, KM-06 | tinggi | — | R/05 |
| 77 | KM-T2 | Layar Capaian (cari dan jumlahkan) | I | KM-T1, PK-41 | — | sedang | — | R/05 |
| 78 | AG-T1 | Asisten: rapikan kartu tindakan yang ada | S | PK-02 | AG-01, AG-02, AG-04, AG-05 | sedang | — | R/08 |
| 79 | AG-T2 | Asisten: baca keuangan lewat pintu aplikasi | S | AG-T1, PK-09, PK-16, PK-17, PR-T3 | AG-03, AG-06 | tinggi | — | R/08 |
| 80 | PY-T1 | Komponen gaji per PT, antrean masukan, jenis proses gaji | G | PK-22 | PY-01, PY-02, PY-13, PY-14 | tinggi | — | R/09 |
| 81 | PY-T2 | Riwayat kompensasi dan penugasan PT | G | PY-T1 | PY-09 | sedang | — | R/09 |
| 82 | PY-T3 | Aturan hitung gaji dari pengaturan | G | PY-T1 | PY-04, PY-07, PY-08, PY-12 | tinggi | — | R/09 |
| 83 | PY-T4 | Bayar gaji dan setor kewajiban | G | PY-T1, PM-T1 | PY-11 | sedang | — | R/09 |
| 84 | KM-T3 | Lembar Insentif (dokumen keputusan) | I | KM-T2, KF-T6 | KM-05 | sedang | — | R/05 |
| 85 | KM-T4 | Lembar Insentif masuk gaji dan buku besar | I | KM-T3, PY-T1 | KM-07, PY-06 | tinggi | H5 | R/05 |
| 86 | KM-T5 | Kartu "Capaian & Insentif Saya"; layar lama dipindah | I | KM-T4, MN-T1 | — | rendah | — | R/05 |
| 87 | PY-T5 | Swalayan karyawan: slip setelah dibayar | G | PY-T1 | — | rendah | — | R/09 |
| 88 | CR-T2 | Jadwal tagihan dan saldo piutang tersimpan | C | PK-19, PK-41 | CR-06, CR-09 | tinggi | — | R/06 |
| 89 | CR-T3 | Gerbang kredit di empat titik; izin kredit | C | CR-T1, CR-T2, PK-38 | CR-02, CR-04, CR-05 | tinggi | H5 | R/06 |
| 90 | CR-T4 | Denda berlapis PT → pelanggan | C | PK-08, CR-T2 | CR-07 | sedang | — | R/06 |
| 91 | CR-T5 | Daftar kerja kredit dan rekening koran pelanggan | C | CR-T2 | CR-08 | sedang | — | R/06 |
| 92 | PM-T2 | Cara bayar dan rekening tujuan di pesanan; instruksi bayar | B | PM-T1 | PM-01 | sedang | — | R/07 |
| 93 | PM-T3 | Kwitansi ber-rekening; terverifikasi bank | B | PK-19, PK-20, PK-21, PM-T2 | PM-02, PM-04 | tinggi | — | R/07 |
| 94 | PM-T4 | Titipan tunai sales dan setoran | B | PM-T3 | PM-06 | sedang | H5 | R/07 |
| 95 | PM-T5 | Virtual account / QRIS | B | PM-T3 | — | tinggi | H8 (K-35) | R/07 |
| 96 | TX-T1 | Pengaturan pajak bertanggal berlaku dan data pajak pelanggan | X | PK-40 | TX-06 | sedang | — | R/07 |
| 97 | TX-T2 | Pemicu faktur pajak dan daur hidupnya | X | TX-T1, PK-32 | TX-05 | tinggi | H5 | R/07 |
| 98 | TX-T3 | Ekspor Coretax, PPh 23, bukti potong | X | TX-T2 | — | sedang | H8 (K-08) | R/07 |
| 99 | AG-T3 | Asisten: kartu tindakan golongan A dan B | S | AG-T2, PK-15, PK-18, PK-21 | — | tinggi | H5 | R/08 |
| 100 | AG-T4 | Asisten: paket tutup buku dan ringkasan pagi | S | AG-T2, PK-18 | — | sedang | — | R/08 |
| 101 | AG-T5 | Asisten: kartu tindakan uang keluar dan jurnal | S | AG-T3, PK-05, PK-10, PK-12, PK-20, PK-36, KF-T6 | — | tinggi | H5 | R/08 |
| 102 | MN-T2 | Penyatuan layar keuangan | M | MN-T1, PK-18, PK-24, PK-43, PY-T1 | — | sedang | — | R/01 |
| 103 | MN-T3 | Satu form pembayaran, kartu pelanggan, kartu pemasok | M | PK-05, PK-19, PK-43, PM-T3, CR-T5 | — | tinggi | — | R/01 |

Jumlah: 104 unit.
