# Status unit kerja

Papan kerja agen pelaksana. Aturan mengubahnya: `00_ATURAN_EKSEKUSI.md` §5. Urutan = urutan pengerjaan (`INDEKS_UNIT.md`).

| # | ID | Judul | Prasyarat | Status | Commit | Laporan | Catatan |
|---|---|---|---|---|---|---|---|
| 1 | PK-01 | Garis dasar gate dan pendaftaran temuan ke tracker | — | selesai | `fce265c` | [PK-01](../reviews/2026-11-13/hasil/PK-01.md) |  |
| 2 | PK-02 | Kerangka uji database tiruan + tes regresi dari bukti audit | PK-01 | selesai | `ebfd17d` | [PK-02](../reviews/2026-11-13/hasil/PK-02.md) |  |
| 3 | PK-03 | Cek data nyata (dijalankan pemilik) | — | tahan |  |  | Titik henti H3 |
| 4 | PK-04 | Cadangan lebih sering dan uji pulih | — | tahan |  |  | Titik henti H2 |
| 5 | PK-05 | Bayar hutang pemasok lewat satu pintu yang aman | PK-02 | selesai | `212b21c` | [PK-05](../reviews/2026-11-13/hasil/PK-05.md) | H1 dilewati atas arahan pemilik 13 Nov; pola perlu ditinjau reviewer |
| 6 | PK-06 | Jurnal kembar antar-PT yang utuh dan bisa diulang | PK-02 | selesai | `dfec457` | [PK-06](../reviews/2026-11-13/hasil/PK-06.md) | H1 dilewati atas arahan pemilik 13 Nov; pola perlu ditinjau reviewer |
| 7 | PR-T1 | Tutup jalan menaikkan hak sendiri | PK-02 | selesai | `26203dd` | [PR-T1](../reviews/2026-11-13/hasil/PR-T1.md) |  |
| 7b | PR-T9 | Perubahan izin peran bawaan bertahan setelah server dinyalakan ulang; satu sumber izin bawaan | PK-02 | selesai | `41fb474` | [PR-T9](../reviews/2026-11-13/hasil/PR-T9.md) |  |
| 8 | KF-T1 | Izin kelola dan lihat pengaturan benar-benar berfungsi | PK-02 | selesai | `4c4cd52` | [KF-T1](../reviews/2026-11-13/hasil/KF-T1.md) |  |
| 9 | PK-47 | Cacat kecil dari uji sapuan endpoint | PK-02 | selesai | `ac1195a` | [PK-47](../reviews/2026-11-13/hasil/PK-47.md) |  |
| 10 | PK-07 | Setoran karyawan pada kasus keuangan terbukukan dua kali | PK-02 | selesai | `5ded672` | [PK-07](../reviews/2026-11-13/hasil/PK-07.md) | U8 (POC G-9) berhenti sebelum butir setoran: data acuan tanpa rekening impor mutasi |
| 11 | PK-08 | Denda keterlambatan dihitung dan dijurnal dengan benar | PK-02 | selesai | `0b41a2b` | [PK-08](../reviews/2026-11-13/hasil/PK-08.md) |  |
| 12 | PK-09 | Entitas tidak boleh datang dari isi permintaan | PK-02 | selesai | `bdd8e40` | [PK-09](../reviews/2026-11-13/hasil/PK-09.md) |  |
| 13 | PK-10 | Jurnal manual lewat validator pusat; satu penanda pembalik | PK-02 | selesai | `8774bd1` | [PK-10](../reviews/2026-11-13/hasil/PK-10.md) |  |
| 14 | PK-11 | Periode yang belum berakhir tidak bisa ditutup | PK-02 | selesai | `cb6b470` | [PK-11](../reviews/2026-11-13/hasil/PK-11.md) |  |
| 15 | PK-12 | Kunci idempotensi dan penahan klik ganda di semua form uang | PK-02 | selesai | `b5f3011` | [PK-12](../reviews/2026-11-13/hasil/PK-12.md) |  |
| 16 | PK-13 | Konfirmasi untuk aksi uang sekali klik | PK-02 | selesai | `0ac34c1` | [PK-13](../reviews/2026-11-13/hasil/PK-13.md) |  |
| 17 | PK-14 | Indeks unik wajib ada | PK-02 | selesai | `a42f3ef` | [PK-14](../reviews/2026-11-13/hasil/PK-14.md) | Titik henti H6 bila data kembar |
| 18 | PK-15 | Alokasi titipan bank dan biaya bank | PK-02 | selesai | `30e3f28` | [PK-15](../reviews/2026-11-13/hasil/PK-15.md) |  |
| 19 | PK-16 | Laporan menyebut PT-nya; mode gabungan diberi label | PK-02 | dikerjakan |  |  |  |
| 20 | PK-17 | Nominal keuangan hanya untuk yang berizin | PK-02 | siap |  |  |  |
| 21 | PK-45 | Penjaga cepat: plafon, faktur pajak, gaji | PK-02 | siap |  |  |  |
| 22 | PK-46 | Tabel tarif PPh 21 dari pengaturan bertanggal berlaku | PK-02 | siap |  |  | Titik henti H4 untuk memuat tabel dari pemilik |
| 23 | PR-T2 | Wewenang dari izin, bukan nama peran acuan | PR-T1, PR-T9 | siap |  |  |  |
| 24 | PR-T3 | Endpoint yang hanya butuh login: dipilah dan dijaga | PR-T2 | menunggu |  |  |  |
| 25 | KF-T6 | Kontrol dua orang yang bisa diatur per PT | KF-T1 | siap |  |  |  |
| 26 | KP-T3 | Aturan Persetujuan: buang pilihan palsu, tampilkan jenjang efektif | KF-T1 | siap |  |  |  |
| 27 | KP-T4 | Satu tabel kebijakan persetujuan untuk semua antrean | KF-T6, KP-T3, PR-T2 | menunggu |  |  |  |
| 28 | PR-T4 | Sifat peran yang bisa diatur: cakupan data, beranda, penerima notifikasi | PR-T2 | menunggu |  |  |  |
| 29 | PR-T5 | Katalog izin dirapikan; modul akses dipecah | PR-T2 | menunggu |  |  |  |
| 30 | PR-T6 | Layar Peran & Hak Akses dan Akun & Akses | PR-T4, PR-T5 | menunggu |  |  |  |
| 31 | PR-T7 | Layar memakai izin, bukan nama peran | PR-T2 | menunggu |  |  |  |
| 32 | PR-T8 | Penjaga matriks izin berjalan (peran × endpoint) | PR-T3 | menunggu |  |  |  |
| 33 | KF-T2 | Kunci pengaturan mati, ganda, dan tersembunyi | KF-T1 | siap |  |  |  |
| 34 | KF-T3 | Layar menampilkan nilai yang dipakai mesin; jadwal diaktifkan penjadwal | KF-T1 | siap |  |  |  |
| 35 | KF-T4 | Bahasa, pengelompokan, dan editor Pusat Pengaturan | KF-T2 | menunggu |  |  |  |
| 36 | KF-T5 | Pengaturan per pelanggan dan per barang punya layar | KF-T1 | siap |  |  |  |
| 37 | KF-T7 | Nilai bisnis yang ditulis mati menjadi pengaturan | KF-T2 | menunggu |  |  |  |
| 38 | KF-T8 | Penjaga pengaturan: uji putaran semua kunci menjadi gate | KF-T2 | menunggu |  |  |  |
| 39 | KP-T1 | Profil PT yang jujur dan bisa diubah | KF-T1 | siap |  |  |  |
| 40 | KP-T2 | Kesiapan PT, wizard lanjutan, dan arsip PT | KP-T1 | menunggu |  |  |  |
| 41 | KP-T5 | Penomoran dokumen per PT | KP-T1 | menunggu |  |  | Titik henti H3 untuk dokumen lama |
| 42 | KP-T6 | Dokumen dan cetak per PT | KP-T1 | menunggu |  |  |  |
| 43 | KP-T7 | Pengingat dan penjadwal yang bisa diatur | KF-T1 | siap |  |  |  |
| 44 | KP-T8 | Rahasia dan perangkat | KF-T1 | siap |  |  |  |
| 45 | MN-T1 | Menu keuangan dan SDM: pindah dan kelompokkan | PR-T5 | menunggu |  |  |  |
| 46 | KP-T9 | Susunan hub Pengaturan | MN-T1, KF-T4 | menunggu |  |  |  |
| 47 | PK-18 | Penanda gagal dan panel untuk semua jenis dokumen | PK-05, PK-06 tervalidasi | menunggu |  |  |  |
| 48 | PK-19 | Kwitansi, deposit, selisih bayar: satu fungsi alokasi | PK-18 | menunggu |  |  |  |
| 49 | PK-20 | Kas dibuat lewat satu pembuat | PK-18 | menunggu |  |  |  |
| 50 | PK-21 | Rekonsiliasi bank satu mekanisme | PK-15 | siap |  |  |  |
| 51 | PK-22 | Penggajian: tanggal buku, hitung ulang, batal, setoran kewajiban | PK-18 | menunggu |  |  |  |
| 52 | PK-23 | Aset tetap | PK-06, PK-18 | menunggu |  |  |  |
| 53 | PK-24 | Kas kecil dan pertanggungjawaban | PK-18 | menunggu |  |  |  |
| 54 | PK-25 | Kasus keuangan: periksa dulu, efek kemudian | PK-09, PK-19 | menunggu |  |  |  |
| 55 | PK-26 | Landed cost untuk roll yang sudah terjual | PK-18 | menunggu |  |  |  |
| 56 | PK-27 | Biaya roll pada scrap, retur, dan HPP | PK-18 | menunggu |  |  |  |
| 57 | PK-28 | GR/IR: varians, umur, kliring | PK-18 | menunggu |  |  |  |
| 58 | PK-29 | Rekonsiliasi persediaan per PT; true-up dibatasi | PK-27 | menunggu |  |  |  |
| 59 | PK-30 | Antar-PT: panjang aktual, jalur lama, harga dan PPN | PK-06 | siap |  |  |  |
| 60 | PK-31 | Eliminasi per periode; rantai A→B→C; retur setelah lunas | PK-30 | menunggu |  |  |  |
| 61 | PK-32 | Nota kredit satu mesin | PK-19 | menunggu |  |  |  |
| 62 | PK-33 | Hijaukan penjaga atomisitas | PK-19, PK-20 | menunggu |  |  |  |
| 63 | PK-34 | Replica set satu anggota, transaksi di jalur uang, pustaka database | gelombang 3 tervalidasi (PK-18 … PK-25; dengan sendirinya PK-05, PK-06) | tahan |  |  | Titik henti H2 |
| 64 | PK-35 | Uang sebagai bilangan bulat; validator; penomoran jurnal | PK-34 | tahan |  |  | Titik henti H2, H3 |
| 65 | PK-36 | Akun kontrol tertutup dari jurnal manual | PK-10 | siap |  |  |  |
| 66 | PK-37 | Tanggal buku WIB dan kunci periode untuk dokumen | PK-11 | siap |  |  |  |
| 67 | PK-38 | Satu batas wewenang; izin bayar terpisah; ganti termin | KF-T6, PR-T2 | menunggu |  |  |  |
| 68 | PK-39 | Anggaran | PK-18 | menunggu |  |  |  |
| 69 | PK-40 | Pajak: keunikan, masa pajak, basis | PK-14 | siap |  |  |  |
| 70 | PK-41 | Laporan pendukung | PK-19 | menunggu |  |  |  |
| 71 | PK-42 | Layar: perbaikan cepat per berkas | PK-12 | siap |  |  |  |
| 72 | PK-43 | Layar: struktural | PK-06, PK-19 | menunggu |  |  |  |
| 73 | PK-44 | Jejak dokumen dan relasi dokumen | MN-T1 | menunggu |  |  |  |
| 74 | PM-T1 | Induk cara bayar dan rekening ber-peruntukan | KF-T1 | siap |  |  |  |
| 75 | CR-T1 | Profil kredit per pelanggan per PT | PK-45, KF-T6, KF-T7 | menunggu |  |  |  |
| 76 | KM-T1 | Data insentif: omzet terkirim, pencairan, harga acuan, target | PK-19 | menunggu |  |  |  |
| 77 | KM-T2 | Layar Capaian (cari dan jumlahkan) | KM-T1, PK-41 | menunggu |  |  |  |
| 78 | AG-T1 | Asisten: rapikan kartu tindakan yang ada | PK-02 | siap |  |  |  |
| 79 | AG-T2 | Asisten: baca keuangan lewat pintu aplikasi | AG-T1, PK-09, PK-16, PK-17, PR-T3 | menunggu |  |  |  |
| 80 | PY-T1 | Komponen gaji per PT, antrean masukan, jenis proses gaji | PK-22 | menunggu |  |  |  |
| 81 | PY-T2 | Riwayat kompensasi dan penugasan PT | PY-T1 | menunggu |  |  |  |
| 82 | PY-T3 | Aturan hitung gaji dari pengaturan | PY-T1 | menunggu |  |  |  |
| 83 | PY-T4 | Bayar gaji dan setor kewajiban | PY-T1, PM-T1 | menunggu |  |  |  |
| 84 | KM-T3 | Lembar Insentif (dokumen keputusan) | KM-T2, KF-T6 | menunggu |  |  |  |
| 85 | KM-T4 | Lembar Insentif masuk gaji dan buku besar | KM-T3, PY-T1 | menunggu |  |  | Titik henti H5 |
| 86 | KM-T5 | Kartu "Capaian & Insentif Saya"; layar lama dipindah | KM-T4, MN-T1 | menunggu |  |  |  |
| 87 | PY-T5 | Swalayan karyawan: slip setelah dibayar | PY-T1 | menunggu |  |  |  |
| 88 | CR-T2 | Jadwal tagihan dan saldo piutang tersimpan | PK-19, PK-41 | menunggu |  |  |  |
| 89 | CR-T3 | Gerbang kredit di empat titik; izin kredit | CR-T1, CR-T2, PK-38 | menunggu |  |  | Titik henti H5 |
| 90 | CR-T4 | Denda berlapis PT → pelanggan | PK-08, CR-T2 | menunggu |  |  |  |
| 91 | CR-T5 | Daftar kerja kredit dan rekening koran pelanggan | CR-T2 | menunggu |  |  |  |
| 92 | PM-T2 | Cara bayar dan rekening tujuan di pesanan; instruksi bayar | PM-T1 | menunggu |  |  |  |
| 93 | PM-T3 | Kwitansi ber-rekening; terverifikasi bank | PK-19, PK-20, PK-21, PM-T2 | menunggu |  |  |  |
| 94 | PM-T4 | Titipan tunai sales dan setoran | PM-T3 | menunggu |  |  | Titik henti H5 |
| 95 | PM-T5 | Virtual account / QRIS | PM-T3 | tahan |  |  | Titik henti H8 (K-35) |
| 96 | TX-T1 | Pengaturan pajak bertanggal berlaku dan data pajak pelanggan | PK-40 | menunggu |  |  |  |
| 97 | TX-T2 | Pemicu faktur pajak dan daur hidupnya | TX-T1, PK-32 | menunggu |  |  | Titik henti H5 |
| 98 | TX-T3 | Ekspor Coretax, PPh 23, bukti potong | TX-T2 | tahan |  |  | Titik henti H8 (K-08) |
| 99 | AG-T3 | Asisten: kartu tindakan golongan A dan B | AG-T2, PK-15, PK-18, PK-21 | menunggu |  |  | Titik henti H5 |
| 100 | AG-T4 | Asisten: paket tutup buku dan ringkasan pagi | AG-T2, PK-18 | menunggu |  |  |  |
| 101 | AG-T5 | Asisten: kartu tindakan uang keluar dan jurnal | AG-T3, PK-05, PK-10, PK-12, PK-20, PK-36, KF-T6 | menunggu |  |  | Titik henti H5 |
| 102 | MN-T2 | Penyatuan layar keuangan | MN-T1, PK-18, PK-24, PK-43, PY-T1 | menunggu |  |  |  |
| 103 | MN-T3 | Satu form pembayaran, kartu pelanggan, kartu pemasok | PK-05, PK-19, PK-43, PM-T3, CR-T5 | menunggu |  |  |  |

## Menunggu pemilik

Diisi agen saat sebuah unit masuk `tahan`: satu kalimat pertanyaan, pilihan yang tersedia, usulan.

| Unit | Pertanyaan | Pilihan | Usulan |
|---|---|---|---|
| PK-05, PK-06 (H1) | Pola posting (periksa tanpa tulis → niat → efek idempoten → jurnal tahan-gagal; jurnal kembar `preflight_twin`/`post_twin`) disetujui sebagai acuan unit gelombang 3? | Setujui · minta ubah | Dilanjutkan atas arahan pemilik 13 Nov ("kerjakan sesuai rekomendasi, catat"); reviewer diminta meninjau `hasil/PK-05.md` dan `hasil/PK-06.md` |

## Catatan sesi

Diisi agen di akhir tiap sesi: tanggal, unit yang selesai, unit yang tertahan dan mengapa.

**Sesi 13–14 Nov 2026** (berjalan)

- Cabang kerja: `claude/nifty-carson-jjx3c8` (satu-satunya cabang yang boleh didorong sesi ini), bukan `bp/integrasi`
  dan `bp/<ID>`. Tanda `dikerjakan` dan `selesai` ditulis dalam satu commit unit karena hanya satu agen yang bekerja.
- Lingkungan A setara: MongoDB 7 asli di Docker + backend di host (rincian di laporan PK-01).
- Arahan pemilik 13 Nov (sebelum pergi): "kerjakan berurutan sampai selesai; bila ada pertanyaan kerjakan sesuai
  rekomendasi namun catat". Dipakai untuk titik henti yang bersifat tinjauan (H1) dan pertanyaan aturan bisnis
  (`00` §4.1). **Tidak** dipakai untuk H2 (jalur produksi), H3 (data nyata), H4 (isi tabel peraturan, akun/arah jurnal
  yang tidak disebut unit), H8 (rahasia): unit itu tetap `tahan`.
