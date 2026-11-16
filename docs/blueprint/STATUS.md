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
| 19 | PK-16 | Laporan menyebut PT-nya; mode gabungan diberi label | PK-02 | selesai | `b735229` | [PK-16](../reviews/2026-11-13/hasil/PK-16.md) |  |
| 20 | PK-17 | Nominal keuangan hanya untuk yang berizin | PK-02 | selesai | `376bd21` | [PK-17](../reviews/2026-11-13/hasil/PK-17.md) |  |
| 21 | PK-45 | Penjaga cepat: plafon, faktur pajak, gaji | PK-02 | selesai | `8d952cb` | [PK-45](../reviews/2026-11-13/hasil/PK-45.md) |  |
| 22 | PK-46 | Tabel tarif PPh 21 dari pengaturan bertanggal berlaku | PK-02 | tahan | `c38ab35` | [PK-46](../reviews/2026-11-13/hasil/PK-46.md) | Titik henti H4: menunggu berkas pph21_terverifikasi.json (langkah 1–4 selesai) |
| 23 | PR-T2 | Wewenang dari izin, bukan nama peran acuan | PR-T1, PR-T9 | selesai | `45a9d73` · `653e87e` | [PR-T2](../reviews/2026-11-13/hasil/PR-T2.md) |  |
| 24 | PR-T3 | Endpoint yang hanya butuh login: dipilah dan dijaga | PR-T2 | selesai | `36b056e` | [PR-T3](../reviews/2026-11-13/hasil/PR-T3.md) |  |
| 25 | KF-T6 | Kontrol dua orang yang bisa diatur per PT | KF-T1 | selesai | `a053a94` · `4844181` | [KF-T6](../reviews/2026-11-13/hasil/KF-T6.md) | H3: migrasi sakelar lama berjalan saat proses awal — tinjau sebelum data nyata |
| 26 | KP-T3 | Aturan Persetujuan: buang pilihan palsu, tampilkan jenjang efektif | KF-T1 | selesai | `3224848` | [KP-T3](../reviews/2026-11-13/hasil/KP-T3.md) | H3: --apply skrip migrasi menunggu pemilik |
| 27 | KP-T4 | Satu tabel kebijakan persetujuan untuk semua antrean | KF-T6, KP-T3, PR-T2 | selesai | `ff73676` · `0c5486e` | [KP-T4](../reviews/2026-11-13/hasil/KP-T4.md) | H3: --apply migrate_kpt4_kebijakan_persetujuan wajib saat pemasangan di data nyata |
| 28 | PR-T4 | Sifat peran yang bisa diatur: cakupan data, beranda, penerima notifikasi | PR-T2 | selesai | `6d7dacf` · `39cdd4b` | [PR-T4](../reviews/2026-11-13/hasil/PR-T4.md) | H3: migrasi prt4:sifat-peran & prt4:izin-kpi-sales berjalan saat proses awal |
| 29 | PR-T5 | Katalog izin dirapikan; modul akses dipecah | PR-T2 | selesai | `b8bd0a2` | [PR-T5](../reviews/2026-11-13/hasil/PR-T5.md) | Keputusan pemilik: API Ringkasan kini 403 bagi Sales/Gudang/MD/Admin Gudang/Admin Sample (layar sudah tersembunyi). H3: migrasi prt5:katalog saat proses awal |
| 30 | PR-T6 | Layar Peran & Hak Akses dan Akun & Akses | PR-T4, PR-T5 | selesai | `1392969` | [PR-T6](../reviews/2026-11-13/hasil/PR-T6.md) |  |
| 31 | PR-T7 | Layar memakai izin, bukan nama peran | PR-T2 | selesai | `2d164c9` | [PR-T7](../reviews/2026-11-13/hasil/PR-T7.md) |  |
| 32 | PR-T8 | Penjaga matriks izin berjalan (peran × endpoint) | PR-T3 | selesai | `303e709` | [PR-T8](../reviews/2026-11-13/hasil/PR-T8.md) | guard:matriks_izin (--full) MERAH 20 baris pada 14 rute — dibereskan PR-T8b (`435b470`): sapuan cepat & --penuh HIJAU |
| 32b | PR-T8b | Rute merah penjaga matriks izin: putusan login-saja dan gerbang izin sebelum dokumen dimuat (T8-01…T8-09) | PR-T8 | selesai | `435b470` | [PR-T8b](../reviews/2026-11-13/hasil/PR-T8b.md) |  |
| 33 | KF-T2 | Kunci pengaturan mati, ganda, dan tersembunyi | KF-T1 | selesai | `1dcb06c` | [KF-T2](../reviews/2026-11-13/hasil/KF-T2.md) | H3: --apply migrate_kft2_akun_bank sebelum dipasang di data nyata |
| 34 | KF-T3 | Layar menampilkan nilai yang dipakai mesin; jadwal diaktifkan penjadwal | KF-T1 | selesai | `dbe1633` · `9783875` | [KF-T3](../reviews/2026-11-13/hasil/KF-T3.md) |  |
| 35 | KF-T4 | Bahasa, pengelompokan, dan editor Pusat Pengaturan | KF-T2 | selesai | `13b84dd` | [KF-T4](../reviews/2026-11-13/hasil/KF-T4.md) |  |
| 36 | KF-T5 | Pengaturan per pelanggan dan per barang punya layar | KF-T1 | selesai | `0da3656` | [KF-T5](../reviews/2026-11-13/hasil/KF-T5.md) |  |
| 37 | KF-T7 | Nilai bisnis yang ditulis mati menjadi pengaturan | KF-T2 | selesai | `885daca` | [KF-T7](../reviews/2026-11-13/hasil/KF-T7.md) | H3: migrasi margin pesanan khusus saat proses awal |
| 38 | KF-T8 | Penjaga pengaturan: uji putaran semua kunci menjadi gate | KF-T2 | selesai | `e13e29b` | [KF-T8](../reviews/2026-11-13/hasil/KF-T8.md) |  |
| 39 | KP-T1 | Profil PT yang jujur dan bisa diubah | KF-T1 | selesai | `69cc4e3` | [KP-T1](../reviews/2026-11-13/hasil/KP-T1.md) | H3: --apply migrate_kpt1_profil_pt di data nyata |
| 40 | KP-T2 | Kesiapan PT, wizard lanjutan, dan arsip PT | KP-T1 | selesai | `aea3cec` | [KP-T2](../reviews/2026-11-13/hasil/KP-T2.md) |  |
| 41 | KP-T5 | Penomoran dokumen per PT | KP-T1 | selesai | `4e816a0` · `eb4e0e1` | [KP-T5](../reviews/2026-11-13/hasil/KP-T5.md) | Titik henti H3 untuk dokumen lama |
| 42 | KP-T6 | Dokumen dan cetak per PT | KP-T1 | selesai | `1ebbdaa` | [KP-T6](../reviews/2026-11-13/hasil/KP-T6.md) |  |
| 43 | KP-T7 | Pengingat dan penjadwal yang bisa diatur | KF-T1 | selesai | `0a91095` | [KP-T7](../reviews/2026-11-13/hasil/KP-T7.md) |  |
| 44 | KP-T8 | Rahasia dan perangkat | KF-T1 | selesai | `a742da9` | [KP-T8](../reviews/2026-11-13/hasil/KP-T8.md) |  |
| 45 | MN-T1 | Menu keuangan dan SDM: pindah dan kelompokkan | PR-T5 | selesai | `5e94a1d` | [MN-T1](../reviews/2026-11-13/hasil/MN-T1.md) |  |
| 46 | KP-T9 | Susunan hub Pengaturan | MN-T1, KF-T4 | selesai | `b95bd0d` | [KP-T9](../reviews/2026-11-13/hasil/KP-T9.md) |  |
| 47 | PK-18 | Penanda gagal dan panel untuk semua jenis dokumen | PK-05, PK-06 tervalidasi | selesai | a48a0a9 | [PK-18](../reviews/2026-11-13/hasil/PK-18.md) | Prasyarat "PK-05, PK-06 tervalidasi" dilepas atas keputusan pemilik 14 Nov (H1; lihat Menunggu pemilik) |
| 48 | PK-19 | Kwitansi, deposit, selisih bayar: satu fungsi alokasi | PK-18 | selesai | 1204bac | [PK-19](../reviews/2026-11-13/hasil/PK-19.md) |  |
| 49 | PK-20 | Kas dibuat lewat satu pembuat | PK-18 | selesai | 7f9a527 | [PK-20](../reviews/2026-11-13/hasil/PK-20.md) |  |
| 50 | PK-21 | Rekonsiliasi bank satu mekanisme | PK-15 | selesai | `3c459d9` | [PK-21](../reviews/2026-11-13/hasil/PK-21.md) |  |
| 51 | PK-22 | Penggajian: tanggal buku, hitung ulang, batal, setoran kewajiban | PK-18 | selesai | 8c8d5ab | [PK-22](../reviews/2026-11-13/hasil/PK-22.md) |  |
| 52 | PK-23 | Aset tetap | PK-06, PK-18 | selesai | 5a635ec | [PK-23](../reviews/2026-11-13/hasil/PK-23.md) | H4: akun lawan perolehan hutang/saldo awal belum diatur pemilik |
| 53 | PK-24 | Kas kecil dan pertanggungjawaban | PK-18 | selesai | edce0af | [PK-24](../reviews/2026-11-13/hasil/PK-24.md) |  |
| 54 | PK-25 | Kasus keuangan: periksa dulu, efek kemudian | PK-09, PK-19 | selesai | 06fe1b7 | [PK-25](../reviews/2026-11-13/hasil/PK-25.md) |  |
| 55 | PK-26 | Landed cost untuk roll yang sudah terjual | PK-18 | selesai | 550c400 | [PK-26](../reviews/2026-11-13/hasil/PK-26.md) |  |
| 56 | PK-27 | Biaya roll pada scrap, retur, dan HPP | PK-18 | selesai | 9d29e77 | [PK-27](../reviews/2026-11-13/hasil/PK-27.md) | H4: akun selisih retur beli belum diatur pemilik |
| 57 | PK-28 | GR/IR: varians, umur, kliring | PK-18 | selesai | 3267c09 | [PK-28](../reviews/2026-11-13/hasil/PK-28.md) | H4: akun Selisih harga pembelian belum diatur pemilik (kliring GR/IR menunggu) |
| 58 | PK-29 | Rekonsiliasi persediaan per PT; true-up dibatasi | PK-27 | selesai | 9871d7f | [PK-29](../reviews/2026-11-13/hasil/PK-29.md) | H3: true-up data nyata = skrip --apply (keputusan pemilik) |
| 59 | PK-30 | Antar-PT: panjang aktual, jalur lama, harga dan PPN | PK-06 | selesai | `a4b7c8d` · `a0ae755` | [PK-30](../reviews/2026-11-13/hasil/PK-30.md) | H4 PPN masukan pembeli non-PKP → Menunggu pemilik |
| 60 | PK-31 | Eliminasi per periode; rantai A→B→C; retur setelah lunas | PK-30 | selesai | dae12fc | [PK-31](../reviews/2026-11-13/hasil/PK-31.md) |  |
| 61 | PK-32 | Nota kredit satu mesin | PK-19 | selesai | 7c13605 | [PK-32](../reviews/2026-11-13/hasil/PK-32.md) | H3: migrasi nota debit lama (migrasi_pk32_nota_debit_menunggu.py) di data nyata |
| 62 | PK-33 | Hijaukan penjaga atomisitas | PK-19, PK-20 | selesai | 6943fb7 | [PK-33](../reviews/2026-11-13/hasil/PK-33.md) |  |
| 63 | PK-34 | Replica set satu anggota, transaksi di jalur uang, pustaka database | gelombang 3 tervalidasi (PK-18 … PK-25; dengan sendirinya PK-05, PK-06) | tahan |  |  | Titik henti H2 |
| 64 | PK-35 | Uang sebagai bilangan bulat; validator; penomoran jurnal | PK-34 | tahan |  |  | Titik henti H2, H3 |
| 65 | PK-36 | Akun kontrol tertutup dari jurnal manual | PK-10 | selesai | `16b50fe` | [PK-36](../reviews/2026-11-13/hasil/PK-36.md) |  |
| 66 | PK-37 | Tanggal buku WIB dan kunci periode untuk dokumen | PK-11 | selesai | `689ca70` · `a323bb0` | [PK-37](../reviews/2026-11-13/hasil/PK-37.md) | H3: --terapkan pk37_tanggal_buku_lama di data nyata |
| 67 | PK-38 | Satu batas wewenang; izin bayar terpisah; ganti termin | KF-T6, PR-T2 | selesai | `eef7bb9` | [PK-38](../reviews/2026-11-13/hasil/PK-38.md) |  |
| 68 | PK-39 | Anggaran | PK-18 | selesai | d5c466d | [PK-39](../reviews/2026-11-13/hasil/PK-39.md) |  |
| 69 | PK-40 | Pajak: keunikan, masa pajak, basis | PK-14 | selesai | `a78f552` | [PK-40](../reviews/2026-11-13/hasil/PK-40.md) |  |
| 70 | PK-41 | Laporan pendukung | PK-19 | selesai | 6093baa | [PK-41](../reviews/2026-11-13/hasil/PK-41.md) |  |
| 71 | PK-42 | Layar: perbaikan cepat per berkas | PK-12 | selesai | `5e747b2` | [PK-42](../reviews/2026-11-13/hasil/PK-42.md) |  |
| 72 | PK-43 | Layar: struktural | PK-06, PK-19 | selesai | d07186e | [PK-43](../reviews/2026-11-13/hasil/PK-43.md) | Dikerjakan paralel (worktree terpisah), 15 Nov |
| 73 | PK-44 | Jejak dokumen dan relasi dokumen | MN-T1 | selesai | `5ef71e8` | [PK-44](../reviews/2026-11-13/hasil/PK-44.md) |  |
| 74 | PM-T1 | Induk cara bayar dan rekening ber-peruntukan | KF-T1 | selesai | `fd606e5` | [PM-T1](../reviews/2026-11-13/hasil/PM-T1.md) |  |
| 75 | CR-T1 | Profil kredit per pelanggan per PT | PK-45, KF-T6, KF-T7 | selesai | 281374f | [CR-T1](../reviews/2026-11-13/hasil/CR-T1.md) |  |
| 76 | KM-T1 | Data insentif: omzet terkirim, pencairan, harga acuan, target | PK-19 | selesai | b9753a3 | [KM-T1](../reviews/2026-11-13/hasil/KM-T1.md) | H3: migrasi target lama (migrate_sales_targets_km_t1.py) & isi harga acuan pesanan lama di data nyata; H6: kunci target kembar |
| 77 | KM-T2 | Layar Capaian (cari dan jumlahkan) | KM-T1, PK-41 | selesai | 4b219c4 | [KM-T2](../reviews/2026-11-13/hasil/KM-T2.md) | Pembanding H5 (dasar omzet, sumber harga acuan) tetap bawaan; kinerja periode panjang belum diukur |
| 78 | AG-T1 | Asisten: rapikan kartu tindakan yang ada | PK-02 | selesai | 3e1a42c | [AG-T1](../reviews/2026-11-13/hasil/AG-T1.md) |  |
| 79 | AG-T2 | Asisten: baca keuangan lewat pintu aplikasi | AG-T1, PK-09, PK-16, PK-17, PR-T3 | selesai | 4ffc907 | [AG-T2](../reviews/2026-11-13/hasil/AG-T2.md) |  |
| 80 | PY-T1 | Komponen gaji per PT, antrean masukan, jenis proses gaji | PK-22 | selesai | 64143aa | [PY-T1](../reviews/2026-11-13/hasil/PY-T1.md) | H4: tarif PPh 21 tabel bawaan PK-46 belum diverifikasi; H3/H6: migrasi proses gaji lama (migrasi_pyt1_proses_gaji.py --apply) |
| 81 | PY-T2 | Riwayat kompensasi dan penugasan PT | PY-T1 | selesai | 82ef1bb | [PY-T2](../reviews/2026-11-13/hasil/PY-T2.md) | H3: migrasi riwayat kompensasi (migrate_hr_compensation_py_t2.py --apply) di data nyata; regresi lembur/komisi slip reguler (ditemukan PY-T3) diperbaiki PY-T3 (a) — proses gaji yang dihitung dengan PY-T2 dihitung ulang/susulan (H3) |
| 82 | PY-T3 | Aturan hitung gaji dari pengaturan | PY-T1 | selesai | 649b7dc | [PY-T3](../reviews/2026-11-13/hasil/PY-T3.md) | K-39: lembur absensi tanpa pengajuan tidak dibayar (dampak data acuan ent_ksc Nov Rp 200.505,80); H4 hari libur diisi pemilik; H3 migrasi_pyt3_aturan_gaji.py --apply; memperbaiki regresi lembur/komisi PY-T2 |
| 83 | PY-T4 | Bayar gaji dan setor kewajiban | PY-T1, PM-T1 | selesai | efc1cc6 | [PY-T4](../reviews/2026-11-13/hasil/PY-T4.md) | Konfirmasi pemilik: peran kustom payroll.* tanpa hr.* tidak lagi melihat menu SDM; bug lama daftar bulan WIB diperbaiki |
| 84 | KM-T3 | Lembar Insentif (dokumen keputusan) | KM-T2, KF-T6 | selesai | 5410979 | [KM-T3](../reviews/2026-11-13/hasil/KM-T3.md) | Nomor LIN- (INS- dipakai Inspeksi); tab Skema (Arsip) disembunyikan — dinilai pemilik/reviewer |
| 85 | KM-T4 | Lembar Insentif masuk gaji dan buku besar | KM-T3, PY-T1 | selesai | d458cd5 | [KM-T4](../reviews/2026-11-13/hasil/KM-T4.md) | H5: sakelar hr.payroll_commission_mode tetap bawaan di semua PT (Menunggu pemilik); usulan koreksi uji U5 (PPh 21 Desember); cek layar: tabel tagihan antar-PT 5 kolom |
| 86 | KM-T5 | Kartu "Capaian & Insentif Saya"; layar lama dipindah | KM-T4, MN-T1 | selesai | 7183e4f | [KM-T5](../reviews/2026-11-13/hasil/KM-T5.md) | Gate 7183e4f 12/39; U15/U16 lulus uji jalan; tinjau: peran kustom sales_force tanpa incentive kehilangan menu tarif/jenjang lama; usulan koreksi U7 |
| 87 | PY-T5 | Swalayan karyawan: slip setelah dibayar | PY-T1 | selesai | b014a38 | [PY-T5](../reviews/2026-11-13/hasil/PY-T5.md) | Perilaku berubah: slip baru terlihat karyawan sesudah dibayar (hr.slip_swalayan_sejak) |
| 88 | CR-T2 | Jadwal tagihan dan saldo piutang tersimpan | PK-19, PK-41 | selesai | 76a337d | [CR-T2](../reviews/2026-11-13/hasil/CR-T2.md) | H3: build_billing_schedule.py --apply di data nyata (dry-run data acuan: 0 pelanggan berubah status kredit) |
| 89 | CR-T3 | Gerbang kredit di empat titik; izin kredit | CR-T1, CR-T2, PK-38 | selesai | eaba57f | [CR-T3](../reviews/2026-11-13/hasil/CR-T3.md) | H5: titik periksa gerbang kredit, masa berlaku izin, tahan-kirim tunai tetap bawaan (perilaku lama); H3: migrasi profil kredit CR-T1 (cadangan data_lama tetap); data acuan 0 pelanggan berubah |
| 90 | CR-T4 | Denda berlapis PT → pelanggan | PK-08, CR-T2 | selesai | fc95d36 | [CR-T4](../reviews/2026-11-13/hasil/CR-T4.md) | H3: migrate_penalty_customer_layer.py di data nyata (0 baris di data acuan); H4 nilai denda tetap bawaan registry |
| 91 | CR-T5 | Daftar kerja kredit dan rekening koran pelanggan | CR-T2 | selesai | 1315ce6 | [CR-T5](../reviews/2026-11-13/hasil/CR-T5.md) | Rekening koran: pemetaan jurnal retur/selisih/kasus/saldo kredit/titipan belum diuji dengan data; kinerja ringkasan belum diukur |
| 92 | PM-T2 | Cara bayar dan rekening tujuan di pesanan; instruksi bayar | PM-T1 | selesai | 73314a8 | [PM-T2](../reviews/2026-11-13/hasil/PM-T2.md) |  |
| 93 | PM-T3 | Kwitansi ber-rekening; terverifikasi bank | PK-19, PK-20, PK-21, PM-T2 | selesai | a2c1e19 | [PM-T3](../reviews/2026-11-13/hasil/PM-T3.md) | H3: isi rekening kas kwitansi lama (backfill_receipt_accounts.py --terapkan) di data nyata sebelum (b) dipakai PT berekening ganda |
| 94 | PM-T4 | Titipan tunai sales dan setoran | PM-T3 | selesai | 38c715f | [PM-T4](../reviews/2026-11-13/hasil/PM-T4.md) | H5: mode tunai sales per PT tetap kas_langsung — PT, batas, tenggat titipan diputuskan pemilik (Menunggu pemilik) |
| 95 | PM-T5 | Virtual account / QRIS | PM-T3 | tahan |  |  | Titik henti H8 (K-35) |
| 96 | TX-T1 | Pengaturan pajak bertanggal berlaku dan data pajak pelanggan | PK-40 | selesai | 9707664 | [TX-T1](../reviews/2026-11-13/hasil/TX-T1.md) |  |
| 97 | TX-T2 | Pemicu faktur pajak dan daur hidupnya | TX-T1, PK-32 | selesai | 15d3258 | [TX-T2](../reviews/2026-11-13/hasil/TX-T2.md) | H5: pemicu faktur tetap pesanan di semua PT (pertanyaan konsultan pajak di Menunggu pemilik); H3: migrate_tax_invoice_status.py di data nyata |
| 98 | TX-T3 | Ekspor Coretax, PPh 23, bukti potong | TX-T2 | tahan |  |  | Titik henti H8 (K-08) |
| 99 | AG-T3 | Asisten: kartu tindakan golongan A dan B | AG-T2, PK-15, PK-18, PK-21 | selesai | 78bbbd9 | [AG-T3](../reviews/2026-11-13/hasil/AG-T3.md) | H5: sakelar per PT ai.tindakan_uang_masuk bawaan mati — dinyalakan pemilik per PT |
| 100 | AG-T4 | Asisten: paket tutup buku dan ringkasan pagi | AG-T2, PK-18 | selesai | f94f6bc | [AG-T4](../reviews/2026-11-13/hasil/AG-T4.md) |  |
| 101 | AG-T5 | Asisten: kartu tindakan uang keluar dan jurnal | AG-T3, PK-05, PK-10, PK-12, PK-20, PK-36, KF-T6 | selesai | df23cb2 | [AG-T5](../reviews/2026-11-13/hasil/AG-T5.md) | H5: sakelar per PT ai.tindakan_uang_keluar bawaan mati — dinyalakan pemilik per PT |
| 102 | MN-T2 | Penyatuan layar keuangan | MN-T1, PK-18, PK-24, PK-43, PY-T1 | selesai | b7837de | [MN-T2](../reviews/2026-11-13/hasil/MN-T2.md) | Keputusan menu: Finance tidak lagi melihat rekonsiliasi persediaan & akun sementara (kini di Tutup Buku) |
| 103 | MN-T3 | Satu form pembayaran, kartu pelanggan, kartu pemasok | PK-05, PK-19, PK-43, PM-T3, CR-T5 | selesai | 5737da3 | [MN-T3](../reviews/2026-11-13/hasil/MN-T3.md) | Gate 5737da3 quick 12 / ci 39 (= garis dasar); uji jalan integrator: 3 cacat layar diperbaiki (Saldo & Umur 1024, label PT kartu pemasok, kartu metrik 390) |
| 104 | MP-T1 | Rute Produk: satu tempat untuk jalan beli/buat barang; tahap ditegakkan dari Master Tahapan Proses | — | dikerjakan |  |  | K-57, K-65, K-70, K-71, K-73; pembuat rute awal di data nyata = H3 |
| 105 | MP-T2 | Satu wizard SPK makloon yang membaca rute; semua pilihan tersaring tahap | MP-T1 | menunggu |  |  | K-57, K-59, K-61 |
| 106 | MP-T3 | R&D tersambung ke mitra makloon: putusan melahirkan rute dan kontrak yang benar | MP-T1 | menunggu |  |  | K-65, K-68, K-70, K-72 |
| 107 | MP-T4 | Mekanisme makloon: paket kerja, mitra ke mitra, hasil akhir, tarif borongan/per proses | MP-T2 | menunggu |  |  | K-62…K-69; akun jurnal baru = H4, sakelar per PT = H5 |
| 108 | MP-T5 | Gudang greige/PFD/PFP: peruntukan pengeluaran, surat jalan wajib packing list, akses MD | — | siap |  |  | K-74…K-77 (permintaan klien) |

## Menunggu pemilik

Diisi agen saat sebuah unit masuk `tahan`: satu kalimat pertanyaan, pilihan yang tersedia, usulan.

| Unit | Pertanyaan | Pilihan | Usulan |
|---|---|---|---|
| TX-T2 (H5, konsultan pajak) | Sebelum PT memakai pemicu faktur **per surat jalan**: (1) nama, bentuk, penomoran dokumen pajak retur dan kapan wajib (setiap nota kredit ber-PPN? hanya pembeli PKP?); (2) tanggal faktur per surat jalan = tanggal penyerahan atau tanggal terbit; (3) jurnal PPN atas uang muka (akun & arah) sebelum pilihan "Per uang muka" dibuka; (4) koreksi harga cukup dokumen retur atau wajib faktur pengganti; (5) kode transaksi dokumen retur. Semua PT tetap `pesanan` (perilaku lama) | Tetap `pesanan` · aktifkan `surat_jalan` per PT sesudah jawaban | Tetap bawaan sampai butir 1–2 dijawab (`hasil/TX-T2.md`) |
| PM-T4 (H5) | PT mana yang sales-nya boleh menerima tunai sebagai **titipan** (pengaturan `pembayaran.sales_terima_tunai`), berapa batas titipan per sales dan tenggat setor (hari)? Semua PT tetap `kas_langsung` (perilaku lama). Juga: insentif (KM-T1) kini menghitung titipan seperti uang masuk — boleh, atau hanya sesudah disetor? | `kas_langsung` · `titipan` · `dilarang`; batas; tenggat | `titipan` untuk PT yang sales-nya menagih tunai di lapangan, batas ± Rp 5 jt, tenggat 1–2 hari, dinyalakan per PT sesudah angka dicocokkan manual (`hasil/PM-T4.md`) |
| KM-T4 (H5) | PT mana yang insentif sales-nya dialihkan dari komisi otomatis ke **Lembar Insentif** (pengaturan `hr.payroll_commission_mode` = `sheet` per PT, beralasan), dan mulai periode bayar kapan? Semua PT tetap "Komisi otomatis: dicadangkan, dilunasi lewat gaji" (perilaku lama). Kartu Kesiapan di data acuan: Sukacita, Kanda Fabric, Cipta Sandang — empat butir Siap (data acuan belum punya lembar/akrual, jadi belum bermakna untuk data nyata). Juga: usulan koreksi uji U5 (PPh 21 Desember = masa pajak terakhir) di laporan | Tetap komisi otomatis · `sheet` per PT · `off` | Satu PT dulu, sesudah Capaian & Lembar dicocokkan dengan rekap manual minimal satu periode dan semua butir Kesiapan Siap; periode bayar = bulan pertama sesudah akrual komisi otomatis lunas lewat gaji (`hasil/KM-T4.md`) |
| Pelanggaran baru yang lolos gate (ditemukan 15 Nov) | Gate dinilai per status, sehingga pelanggaran baru di gate yang sudah merah lolos selama eksekusi. Dibandingkan dengan garis dasar 13 Nov (`scripts/blueprint/bandingkan_pelanggaran_gate.py`): `guard:approval_queues` +7 (pintu keputusan tanpa antrean: `cash-deposits/{id}/reject`, `hr/compensation` & `hr/assignments` approve/reject, `hr/payroll/inputs/{id}/approve`, status `waiting_approval` di `fact_sales_lines`); `guard:numeric_bounds` +2 (`PayInputCreate.amount`, `RemittanceInput.amount` menerima negatif); `guard:ref_unlink` +2 (`incentive_facts.py` nama koleksi dinamis, `interco_tax_service.py` hapus tanpa sapu tautan); `audit_entity_isolation` +1 router tanpa pagar PT; `audit_sales_roles_ux` +12 layar memanggil endpoint yang tidak diizinkan perannya (mis. Piutang → `/bank-accounts` untuk Sales); POC E-7 +6 pemeriksaan merah (perlu dipilah: regresi atau POC basi); `guard:qty_dual` +1 (data) | Satu unit pembersihan sebelum fitur baru · biarkan | Satu unit pembersihan sebelum fitur baru; sesudahnya garis dasar per pelanggaran diperbarui (`docs/blueprint/garis-dasar-gate/`) |
| PY-T2 / PY-T3 (H3) | Proses gaji reguler yang dihitung dengan kode PY-T2 sebelum PY-T3 tidak memuat lembur dan komisi (regresi, diperbaiki PY-T3 (a)). Di data nyata belum ada (cabang belum dipasang) — bila cabang dipasang bertahap, proses draf dihitung ulang, proses diposting/dibayar butuh susulan | Hitung ulang draf · proses susulan · tidak berlaku | Pasang PY-T2 dan PY-T3 bersamaan (`hasil/PY-T2.md`, `hasil/PY-T3.md`) |
| PK-46 (H4) | Berkas tarif PPh 21 terverifikasi (`docs/blueprint/data/pph21_terverifikasi.json`: TER A/B/C, kategori per status PTKP, PTKP, pasal 17, biaya jabatan, ≥ 5 titik uji per kategori, sumber + pemverifikasi + tanggal berlaku) sudah ada? Mekanisme selesai (`hasil/PK-46.md`); slip tetap memakai angka lama sampai berkas dimuat | Serahkan berkas · tunda | Serahkan berkas yang disalin dari lampiran peraturan dan diverifikasi orang pajak; agen menjalankan `scripts/muat_pph21_terverifikasi.py --dry-run` + U12–U13 di database tiruan; `--apply` di data nyata menunggu persetujuan (H3) |
| PK-30 (H4) | Transaksi antar-PT ke pembeli **bukan PKP** yang ber-PPN: PPN masukan pembeli dijurnal sebagai apa? Sementara jurnal tetap seperti lama (Dr 1-1500 PPN Masukan) dan rincian menampilkan tanda peringatan (`tax_warning`) | Tetap PPN masukan · tambah ke nilai persediaan · beban | Putuskan bersama konsultan pajak; perubahan cukup di rencana jurnal `interco_service` (lihat `hasil/PK-30.md` "Menunggu pemilik"). Selisih panjang: roll pendek menurunkan tagihan tanpa membuat ulang sisa pesanan; kenaikan nilai tidak mengulang ambang persetujuan — mengikuti spesifikasi, mohon dikonfirmasi |
| PK-28 (H4) | Akun **Selisih harga pembelian** (`pembelian.selisih_harga`) per PT belum dipilih — bawaan sengaja kosong (isi pemetaan akun = keputusan pemilik). Akibatnya selisih harga faktur vs PO tetap di GR/IR, kliring GR/IR belum bisa dilakukan, dan kesiapan PT "Pemetaan akun" belum beres di setiap PT | Pilih akun (mis. akun beban/varians pembelian) · tunda | Pemilik/akuntan memilih akun di Pengaturan › Keuangan & Pajak › Pemetaan Akun untuk tiap PT; tidak ada kode yang perlu diubah (`hasil/PK-28.md`) |
| PK-27 (H4) | Akun **Selisih nilai retur beli** (`retur.selisih_retur_beli`) per PT belum dipilih — bawaan sengaja kosong. Selisih nilai nota debit vs nilai buku roll yang diretur belum punya akun; kesiapan PT "Pemetaan akun" belum beres sampai diisi | Pilih akun · tunda | Pemilik/akuntan memilih akun di Pengaturan › Keuangan & Pajak › Pemetaan Akun untuk tiap PT (`hasil/PK-27.md`) |
| PK-23 (H4) | Akun lawan perolehan aset **secara hutang** (`aset.sumber_hutang`) dan **saldo awal aset lama** (`aset.sumber_saldo_awal`) per PT belum dipilih (usulan pelaksana 2-1100 / 3-2900); juga: apakah perolehan secara hutang wajib lewat faktur pemasok? Sampai diisi, dua pilihan sumber dana itu mati di form Tambah Aset | Pilih akun · wajib faktur? · tunda | Pemilik/akuntan memilih akun di Pengaturan › Keuangan & Pajak › Pemetaan Akun (`hasil/PK-23.md`) |
| PK-05, PK-06 (H1) — **diputuskan 14 Nov** | Pola posting (periksa tanpa tulis → niat → efek idempoten → jurnal tahan-gagal; jurnal kembar `preflight_twin`/`post_twin`) disetujui sebagai acuan unit gelombang 3? | Setujui · minta ubah | **Pemilik menyetujui (14 Nov, di sesi): PK-18 dan rantainya dimulai sebelum PK-05/PK-06 `tervalidasi`**; reviewer tetap memvalidasi `hasil/PK-05.md`, `hasil/PK-06.md` — bila pola ditolak, unit gelombang 3 disesuaikan |

### Jawaban pemilik 15 Nov 2026 — dicatat, **belum dikerjakan**

Nomor mengikuti daftar keputusan yang dijelaskan integrator di sesi 15 Nov. Tidak ada kode, pengaturan, atau data yang
diubah karena jawaban ini; tiap butir dikerjakan sesudah pemilik memberi aba-aba.

| No | Butir | Jawaban pemilik | Tindak lanjut (belum dikerjakan) |
|---|---|---|---|
| 1 | KM-T4 — beralih ke Lembar Insentif | Belum diputuskan; pemilik meminta penjelasan cara komisi yang berlaku sekarang dulu | Penjelasan diberikan di sesi; keputusan PT & bulan menyusul |
| 2 | PM-T4 — titipan tunai sales | Saat ini sales tidak menerima tunai; fitur dicadangkan (tetap ada). Mekanisme titipan disetujui; batas dan tenggat harus bisa dikonfigurasi | Batas (`pembayaran.titipan_batas_nominal`) dan tenggat (`pembayaran.titipan_tenggat_setor_hari`) sudah pengaturan per PT; mode PT tidak diubah |
| 3 | CR-T3 — titik periksa kredit | Pesanan biasa: cukup saat pesanan dibuat (POS). Pesanan custom: minta pendapat integrator | Analisis integrator di sesi: pada Pesanan Khusus, pemeriksaan kredit baru berjalan saat SO lahir ketika harga dikunci; bila tertahan, kunci harga tetap berhasil (gagal hanya tercatat "SO otomatis gagal") dan PO otomatis ke pemasok bisa sudah terbit. Usulan unit baru: periksa kredit sebelum pengadaan, tahan pengadaan sampai izin kredit/DP — menunggu konfirmasi |
| 4 | AG-T3, AG-T5 — asisten tindakan uang masuk & keluar | Nyalakan di semua PT, semua golongan | Sakelar `ai.tindakan_uang_masuk`, `ai.tindakan_uang_keluar` per PT; akun yang dinyalakan (K-45) dan aturan orang kedua uang keluar perlu dipastikan saat dikerjakan |
| 5 | PK-28 — akun Selisih harga pembelian | Setuju | Akuntan memilih akun per PT di Pemetaan Akun |
| 6 | PK-27 — akun Selisih retur beli | Setuju | Akuntan memilih akun per PT di Pemetaan Akun |
| 7 | PK-23 — akun aset dibeli secara hutang & saldo awal | Setuju usulan: 2-1100 dan 3-2900; pembelian aset secara hutang wajib lewat faktur pemasok | Isi pemetaan per PT + aturan wajib faktur |
| 8 | PK-30 — PPN antar-PT ke pembeli non-PKP | Setuju usulan: (b) ditambahkan ke nilai persediaan untuk barang dagang; dua perilaku selisih panjang roll dikonfirmasi | Ubah rencana jurnal `interco_service` |
| 9 | PK-46 — berkas tarif PPh 21 | Belum ada berkas | Tetap `tahan` |
| 10 | TX-T2 — faktur per surat jalan | Setuju usulan: tetap per pesanan sampai konsultan menjawab butir 1–2 | — |
| 11 | Pemasangan ke data nyata (skrip H3) | Setuju urutan: cadangan → mode coba → tinjau → jalankan | Jadwal & pelaksana belum ditentukan |
| 12 | PK-04 — cadangan & uji pulih | Setuju | Butuh jendela waktu server produksi |
| 13 | PK-34, PK-35 — replica set, transaksi, nominal bulat | Setuju | Butuh validasi gelombang 3 oleh reviewer + jendela waktu |
| 14–15 | PM-T5 VA/QRIS, TX-T3 Coretax | Nanti | Tetap `tahan` |
| 16 | PY-T5 — slip terlihat sesudah dibayar | Ok | — |
| 17 | PY-T4 — menu SDM untuk peran payroll tanpa izin SDM | Ok | — |
| 18 | MN-T3 — nominal tersembunyi di kartu bagi peran tanpa izin | Ok | — |
| 19 | MN-T3 — uang muka pemasok lewat Kasus Keuangan | Ya, digabung ke angka "Uang muka ke pemasok" di kartu pemasok | Perubahan kode kecil di `party_card.py` |
| 20 | KM-T5 — peran kustom `sales_force` tanpa `incentive` | Ok | Bila ada peran begitu di data nyata: tambah `incentive.view` |
| 21 | KM-T3 — nomor `LIN-` | Ok | — |

## Rencana berikutnya — disetujui pemilik 15 Nov 2026, **belum dikerjakan**

Urutan yang disetujui: jangan menambah fitur dulu. Bahan dan angka pendukung: `EVALUASI_EKSEKUSI_2026-11-15.md`.
Uji dan gate mengikuti `03_LINGKUNGAN_UJI.md` §6 (uji hemat, gate per pelanggaran).

| Urutan | Pekerjaan | Isi | Titik henti / syarat |
|---|---|---|---|
| R0 | Gabungkan `main` (FIX-6…FIX-10, `bfb3d0c`) ke cabang blueprint — **diimplementasikan 15 Nov; 8 keputusan disetujui pemilik, `main` dimajukan ke cabang ini (fast-forward); 4 cabang lama boleh dihapus (penghapusan dari sesi ditolak GitHub 403 — dihapus pemilik)** | Commit gabungan `0f0ff4e` di cabang ini; `main` tidak disentuh. 22 bentrok + 2 duplikasi yang tergabung otomatis (qty tertagih retur beli dikurangi dua kali; registri pengaturan/izin) diselesaikan: satu pintu jurnal retur beli (PK-28) dengan pilihan tolak QC FIX-6, satu mesin nota kredit (PK-32), status roll lewat `roll_state` dengan biaya PK-27, kontrol dua orang opname tetap. Uji baru `tests_mem/test_R0_integrasi_fix6.py` (bukti-merah), lapis A FIX-6…10 dan blueprint terkait lulus (kecuali 2 uji indeks FIX-7 yang bergantung data acuan), gate `--ci` merah 39 → 38 dengan 1 pelanggaran baru (berasal dari FIX-7, masuk R4). Rincian: `INTEGRASI_MAIN_FIX6-10.md` | Tinjauan sebelum `main` dimajukan; skrip data produksi FIX-6/FIX-7 dicek ulang dulu (H3) |
| R1 | Cadangan & uji pulih (PK-04) | Cadangan tiap 6 jam, akhir bulan disimpan lebih lama, perintah uji pulih | H2: jendela waktu server produksi dari pemilik |
| R2 | Cek data nyata (PK-03) | Pemeriksaan hanya-baca pada salinan database produksi: masalah mana yang sudah terjadi di data, berapa banyak | H3: dijalankan/diizinkan pemilik; hasilnya menentukan prioritas R3–R5 |
| R3 | Perapian uji & gate | Pilah 16 POC merah (perbarui/arsipkan); pilah ±403 uji lama `backend/tests/` (masuk gate atau arsip); perbaiki 35 suite jest yang tidak termuat; perbaiki 2 skrip seed data acuan; pilah tuduhan palsu penjaga (mis. `auth_coverage`); target gate `--ci` hijau atau merah hanya untuk temuan tercatat yang disetujui pemilik | — |
| R4 | Bereskan pelanggaran baru dari eksekusi | Daftar di "Menunggu pemilik" (baris "Pelanggaran baru yang lolos gate") dan `EVALUASI_EKSEKUSI_2026-11-15.md` §4; temuan R0 (`INTEGRASI_MAIN_FIX6-10.md` §3 dan §5: dua sistem lencana status, wewenang tampilan bersama dari nama peran `admin`, panel mati Finance di Penerimaan); sesudahnya perbarui garis dasar `garis-dasar-gate/` | — |
| R5 | Audit domain (hanya membaca) — **dikerjakan reviewer, sejajar R7; perintah: `docs/reviews/PERINTAH_AUDIT_DOMAIN_2026-11-15.md`** | Fokus pemilik 15 Nov, urut: (A) master data & jenis barang — benang, greige, PFP, PFD, bahan jadi: aturan stage belum ditegakkan di form, dropdown asal, juga di makloon; (B) makloon dari awal sampai akhir; (C) R&D dari awal sampai akhir; (D) retur jual & beli; (E) QC & MD Quality; (F) pesanan pelanggan sesudah POS — alokasi, perubahan tagihan, keep/pending lalu dibuka lagi. Keluhan UI/UX diperlakukan sebagai gejala: dicari akar duplikasi, cacat logika, aturan tidak ditegakkan. Temuan ber-ID baru (`MS-`, `MK-`, `RD-`, `RT-`, `QM-`, `SO-`) masuk tracker berstatus `open`; pemilik memilih yang diperbaiki, lalu dibuat unit blueprint dengan aturan R6. Sisa cakupan (pembelian umum, RFID cetak & handheld, desain/marketing) menyusul. Peta cakupan per domain di `main` 15 Nov: belum disentuh penjualan 28 %, produk/produksi/R&D 39 %, pembelian & makloon 32 % | Hanya membaca; RFID/handheld: H7 (`docs/rfid/KEPUTUSAN_GATE_RFID.md`); data nyata H3 |
| R6 | Aturan anti-duplikasi tertulis | Setiap fitur baru wajib menyebut pintu yang dipakai ulang dan jalur lama yang dimatikan; jalur lama dihapus di unit yang sama atau serah-terima (b) bertanggal | Usulan integrator — tulis di `02_STANDAR.md` sesudah disetujui |
| R7 | Validasi reviewer | 348 temuan `implemented_pending_review` divalidasi reviewer (Codex), mulai unit keuangan risiko tinggi; PK-34 menunggu gelombang 3 `tervalidasi` | Hanya reviewer yang menetapkan `verified`/`reopened` |
| R8 | Staging, uji pakai, pemasangan bertahap | Lingkungan staging berisi salinan data produksi; skrip H3 mode coba → tinjau → jalankan (Jawaban pemilik no. 11); uji pakai staf per peran; rencana mundur; komunikasi perubahan perilaku (slip sesudah dibayar, lembur wajib pengajuan, gerbang kredit, menu pindah, form bayar disatukan) | Sesudah R1; H2/H3 |
| R9 | Ringkasan per modul untuk manusia | Satu halaman per modul: apa yang dilakukan, pintunya di mana, aturannya di mana | — |
| — | Unit baru: kredit Pesanan Khusus | Periksa kredit sebelum pengadaan/produksi; tahan sampai izin kredit atau DP (persen DP = pengaturan); opsional periksa ulang di surat jalan (`EVALUASI_EKSEKUSI_2026-11-15.md` §7) | Menunggu konfirmasi pemilik |

## Catatan sesi

Diisi agen di akhir tiap sesi: tanggal, unit yang selesai, unit yang tertahan dan mengapa.

**Sesi 13–14 Nov 2026**

- Cabang kerja: `claude/nifty-carson-jjx3c8` (satu-satunya cabang yang boleh didorong sesi ini), bukan `bp/integrasi`
  dan `bp/<ID>`. Tanda `dikerjakan` dan `selesai` ditulis dalam satu commit unit karena hanya satu agen yang bekerja.
- Lingkungan A setara: MongoDB 7 asli di Docker + backend di host (rincian di laporan PK-01).
- Arahan pemilik 13 Nov (sebelum pergi): "kerjakan berurutan sampai selesai; bila ada pertanyaan kerjakan sesuai
  rekomendasi namun catat". Dipakai untuk titik henti yang bersifat tinjauan (H1) dan pertanyaan aturan bisnis
  (`00` §4.1). **Tidak** dipakai untuk H2 (jalur produksi), H3 (data nyata), H4 (isi tabel peraturan, akun/arah jurnal
  yang tidak disebut unit), H8 (rahasia): unit itu tetap `tahan`.

**Sesi 14–15 Nov 2026** (lanjutan, berakhir 15 Nov)

- Kerja paralel atas persetujuan pemilik 14 Nov ("bisakah pisah agar dikerjakan lebih cepat" · "agen gabung sendiri"):
  pelaksana bekerja di worktree terpisah (basis B → W), menggabung sendiri ke HEAD terbaru (T); integrator memasang di
  cabang (unit risiko tinggi: commit (a) lalu (b)), menjalankan lingkungan A (lapis A, uji jalan layar), gate, menutup unit.
- Arahan pemilik 14 Nov: setiap layar baru dicek terhadap `KN_37`, `KN_08`, `UX_USABILITY_STANDARD` di 1280/1024/390 px;
  cacat diperbaiki sebelum unit ditutup (commit "Cek layar" per unit; rinciannya di bagian "Integrator" tiap laporan).
- **Hemat uji** (pemilik 15 Nov, "uji berulang tidak efisien"): `tests_mem` integrator hanya untuk keadaan yang belum diuji
  penuh pelaksana (keadaan antara (a), atau bila integrator menyelesaikan bentrok sendiri); pohon (b) yang identik dengan T
  pelaksana (diperiksa berkas demi berkas) memakai angka pelaksana; satu `restore_demo` untuk lapis A + potret; gate
  dijalankan saat lingkungan A menganggur sehingga tidak menambah waktu tunggu. Potret layar dan lapis A tetap wajib.
- Penyimpangan urutan kecil (sengaja, untuk waktu): MN-T3 diluncurkan sebelum CR-T5 resmi ditutup, KM-T5 sebelum KM-T4
  resmi ditutup — basisnya commit unit prasyarat yang sudah lengkap di cabang; gate unit prasyarat tetap dijalankan dan
  hijau setara garis dasar sebelum unit lanjutannya ditutup.
- Garis dasar gate sepanjang sesi: `--quick` 12 FAIL / `--ci` 39 FAIL (garis dasar berkas 16/43); "lebih merah" satu =
  ganti nama `guard:page_tabs` oleh MN-T1 (merah garis dasar yang sama). `restore_demo` selalu berakhir "GAGAL:
  seed_demo_transaksi_kn.py seed_p03_kn.py" (garis dasar lingkungan).
- Temuan di luar cakupan unit (dicatat, tidak dikerjakan): `services/handheld_tasks.py` membaca nama PT dari `db.entities`
  (kosong) → handheld "Daftar Awal" menampilkan kode PT mentah (bug sama dengan yang diperbaiki di kartu pemasok MN-T3);
  `SoTrackerCard` masih memakai hex & huruf < 12 px; `penalty_service.waive` memeriksa nama peran; parameter `?today=`
  pada akrual denda; daftar Pesanan sempit di 1024 px saat panel rincian terbuka; Pusat Amandemen di 1024 px; beberapa
  tanggal bawaan memakai zona peramban.
- Butir tinjauan (bukan titik henti; rinciannya di laporan unit): MN-T3 — peran ber-`customer.view`/`supplier.view` tanpa izin
  kredit/bayar tidak lagi melihat nominal di kartu (K-18), uang muka pemasok lewat kasus keuangan belum ikut angka kartu;
  KM-T4 — usulan koreksi uji U5 (PPh 21 Desember); KM-T5 — peran kustom yang hanya memegang `sales_force` tanpa `incentive`
  kehilangan menu tarif/jenjang komisi lama (kini di layar ber-izin `incentive.view`), usulan koreksi uji U7 (persen tanpa
  pembagi = `null`).
- Akhir sesi: **semua unit `siap` habis** — 97 `selesai`, 7 `tahan` — PK-03 (H3 cek data nyata), PK-04, PK-34 (H2), PK-35 (H2, H3), PK-46 (H4 berkas PPh 21),
  PM-T5, TX-T3 (H8 kredensial penyedia/Coretax). Tidak ada unit
  `menunggu` yang prasyaratnya terpenuhi.
- Lanjutan 15 Nov (sesudah unit terakhir ditutup): pemilik menjawab 21 butir keputusan (dicatat, belum dikerjakan);
  kebijakan uji hemat dan pembanding gate per pelanggaran disimpan (`03_LINGKUNGAN_UJI.md` §6); pembanding baru menemukan
  pelanggaran yang lolos selama eksekusi (belum dibereskan); peta cakupan audit dibuat; rencana R1–R9 disetujui pemilik.
  Evaluasi biaya, waktu, cakupan, dan celah kredit Pesanan Khusus: `EVALUASI_EKSEKUSI_2026-11-15.md`. Sesi berikutnya =
  review oleh pemilik.

**Sesi 14 Nov 2026 — PR-T8b** (cloud, lingkungan B saja)

- Cabang kerja: `claude/wizardly-fermi-q8jeii`, dibuat dari ujung `claude/nifty-carson-jjx3c8` (`2121202`); dipetik ke
  `claude/nifty-carson-jjx3c8` oleh integrator 15 Nov (`66c1de3` → `435b470`), sebelum cabang dimajukan ke `main`.
- PR-T8b selesai (T8-01…T8-09): `guard:matriks_izin` kini hijau (cepat dan `--penuh`). Lingkungan A tidak tersedia —
  gate bawaan/`--ci`/`--full` belum dijalankan untuk unit ini.
- Integrasi 15 Nov (atas persetujuan pemilik): 4 cabang sesi cloud dipetik ke cabang ini — CR-T4b `?today=` (`018e660`…),
  PR-T8b gerbang izin (`435b470`, `263ed25`), perapian Meja Finance (`5c4bd26`: Bantuan di topbar + urutan kelompok; lipatan
  antrean kosong tidak dipakai karena MN-T2), P23 tanggal bawaan WIB (`7371f9d`, `9ed15a9`; perbaikan form kwitansi lama
  dipindah ke `ReceivePaymentModal`/`PaySupplierModal`). Uji pohon akhir: `tests_mem` 2.332 lulus; jest 1.134 lulus
  (35 suite gagal dimuat = kendala lingkungan tercatat). Belum digabung: 33 commit FIX-6…FIX-10 (audit WMS-RFID 9–10 Nov)
  yang masih di `main` lokal komputer pemilik — `main` di GitHub ditahan sampai commit itu ikut digabung.
- 15 Nov (akhir): pemilik mem-push 33 commit FIX-6…FIX-10 ke `main` (`bfb3d0c`, tanpa force-push). Penggabungan `main` ke
  cabang ini dicoba lalu dibatalkan: 6 berkas backend berisi dua implementasi alur yang sama (risiko jurnal ganda / pintu
  kedua) — dijadikan R0 dengan rencana di `INTEGRASI_MAIN_FIX6-10.md`. Cabang blueprint belum digabung ke `main`.
- 15 Nov (malam): R0 dikerjakan atas pilihan pemilik "Kerjakan sekarang" — `main` digabung ke cabang ini (`0f0ff4e`),
  `main` tidak disentuh. Selain 22 bentrok, uji lapis A FIX-6 menemukan duplikasi yang tergabung otomatis tanpa penanda
  bentrok (qty tertagih retur "potong tagihan" dikurangi PK-28 dan FIX-6 sekaligus) → satu aturan PK-28. Bukti dan
  temuan sampingan: `INTEGRASI_MAIN_FIX6-10.md`.
- 15 Nov (malam, lanjutan): pemilik meninjau ringkasan R0 di sesi ini dan menyetujui 8 keputusan (`INTEGRASI_MAIN_FIX6-10.md`
  §1). Atas izin pemilik: `main` dimajukan ke cabang ini (fast-forward, tanpa force-push) dan cabang lama
  `determined-dijkstra-ohdenb`, `gifted-cori-1trg95`, `sleepy-allen-c6cnpi`, `wizardly-fermi-q8jeii` boleh dihapus (isinya sudah
  tergabung lewat `7371f9d`/`9ed15a9`, `5c4bd26`, CR-T4b, `435b470`/`263ed25`); penghapusan dari sesi ini ditolak GitHub
  (HTTP 403), jadi dihapus pemilik lewat halaman Branches GitHub. Deploy ke VPS tetap oleh pemilik; sebelum
  dipasang di data nyata jalankan dulu skrip migrasi `--apply` yang tercantum di kolom "Titik henti" tabel unit (H3).
- 15 Nov (akhir): perintah review untuk sesi berikutnya ditulis di `docs/reviews/PERINTAH_REVIEW_2026-11-15.md`.
- 15 Nov (akhir): R5 diubah menjadi audit domain oleh reviewer dengan fokus pemilik (master & stage, makloon, R&D, retur,
  QC & MD Quality, pesanan sesudah POS); perintah: `docs/reviews/PERINTAH_AUDIT_DOMAIN_2026-11-15.md`.
- 15 Nov (akhir): pemilik menilai hasil agent review dangkal → kedua perintah diberi tujuan terukur dan definisi selesai
  yang diperiksa mesin (`scripts/review/periksa_selesai.py`): review dibagi batch B0–B8 (9 + 247 butir), tiap butir wajib
  temuan asli, ≥30 baris kode dibaca, pencarian pintu lain, uji + hasil, ≥2 upaya membantah, putusan cocok tracker; audit
  domain wajib 47 skenario dan 30 form (inventaris ≥ jumlah komponen pilihan). Kemajuan dihitung ke
  `docs/reviews/PROGRES_REVIEW.md`, log sesi di `docs/reviews/LOG_REVIEW.md`, reviewer push ke `review/<tanggal>`.
