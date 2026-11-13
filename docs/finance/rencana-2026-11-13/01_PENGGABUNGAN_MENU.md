# Usulan — Penggabungan menu keuangan dan SDM

Status: usulan untuk diputuskan pemilik (K-46). Belum ada kode. Menu dibaca dari
`frontend/src/config/navStructure.js`, `hubTabs.js`, `roles.js`, dan `features/crm/CrmView.jsx` di `9834947`; aplikasi
tidak dijalankan.

## 0. Ringkasan

- **Sekarang:** pekerjaan keuangan tersebar di **18 entri menu dalam 4 grup** (Keuangan, Akuntansi & Pajak, Kas & Aset,
  dan Hutang Pemasok di Pembelian), ditambah 4 sub-tab keuangan yang tersembunyi di dalam CRM dan satu layar di
  Pengaturan. SDM punya 4 entri.
- **Usulan:** **10 entri dalam 2 grup** untuk keuangan, dan SDM tetap 4 entri tetapi menyerap tiga tempat insentif yang
  sekarang tersebar. Tidak ada fitur yang dihapus; yang berubah adalah tempatnya.
- **Prinsip:** menu disusun menurut **pekerjaan** ("menagih", "membayar", "menutup buku"), bukan menurut jenis dokumen.
  Satu pekerjaan = satu entri; langkah-langkahnya menjadi tab.
- **Tiga tahap:** tahap 1 hanya memindah dan mengelompokkan (konfigurasi, risiko rendah, bisa kapan saja); tahap 2
  menyatukan layar yang isinya tumpang-tindih; tahap 3 menyatukan form dan kartu (bergantung pada paket fondasi).

## 1. Keadaan sekarang

| Grup | Entri (tab di dalamnya) | Jumlah entri |
|---|---|---|
| Keuangan | Dasbor Keuangan (Posisi & Kontrol · BI Keuangan) · Kas & Bank (Rekening & Saldo · Transaksi Kas · Rekonsiliasi Bank) · Piutang · Uang Muka Pelanggan · Rencana Bayar · Kasus Keuangan · Saldo Kredit | 7 |
| Akuntansi & Pajak | Pajak (Faktur Keluaran · Faktur Masukan · PPN & PPh) · Buku Besar (Jurnal & Buku Besar · Bagan Akun) · Laporan (5 tab) · Tutup Buku · Buka Periode · Posting Gagal · Antar Entitas | 7 |
| Kas & Aset | Kas Kecil (Pengajuan Dana · Pertanggungjawaban · Hutang Reimburse) · Kendaraan · Aset Tetap | 3 |
| Pembelian | Hutang Pemasok (Tagihan Supplier · Kontrabon · Landed Cost) | 1 |
| **Jumlah** | | **18** |

Di luar itu, yang sebenarnya pekerjaan keuangan atau penggajian tetapi berada di tempat lain:

| Tempat sekarang | Layar |
|---|---|
| Penjualan › Pelanggan › CRM & Pelanggan › sub-tab **Penagihan** | Daftar kerja penagihan dan kwitansi |
| … › sub-tab **Persetujuan Kredit** | Keputusan izin kredit |
| … › sub-tab **Kinerja Sales** dan **Skema (Arsip)** | Hitung dan akrual insentif; skema lama |
| Pengaturan › Penjualan › **Komisi & Insentif** | Tarif insentif |
| Meja Finance (beranda peran) | Antrean uang masuk dan faktur pajak |
| SDM › KPI | Hub berisi satu tab |
| Analitik › BI SDM | — |

Masalah yang ditimbulkan susunan ini (dari laporan audit §7): piutang berada di tiga tempat; menerima pembayaran
pelanggan memerlukan pindah menu; tutup buku tersebar di tiga entri tanpa tautan; ada lima dasbor dan tiga antrean
dengan angka "sama" yang berbeda; CRM punya tab tingkat ketiga yang tidak terlihat dari sidebar.

## 2. Susunan yang diusulkan

### Grup **Keuangan** — uang harian

| Entri | Tab | Berasal dari |
|---|---|---|
| **Beranda Keuangan** | Perlu Tindakan · Posisi · Analisis | Meja Finance (antrean) + Posisi & Kontrol + BI Keuangan. Lencana jumlah posting gagal dan kartu yang menunggu persetujuan tampil di sini |
| **Piutang** | Saldo & Umur · Penagihan & Penerimaan · Rencana & Denda · Titipan & Saldo Kredit · Kredit & Plafon · Kasus | Piutang + sub-tab Penagihan (CRM) + Rencana Bayar + Uang Muka Pelanggan + Saldo Kredit + sub-tab Persetujuan Kredit (CRM) + Kasus Keuangan |
| **Hutang** | Tagihan · Kontrabon · Pembayaran | Hutang Pemasok (dari grup Pembelian); tab Pembayaran baru (jadwal dan bayar massal, lihat `06` §5) |
| **Kas & Bank** | Rekening & Saldo · Transaksi Kas · Rekonsiliasi · Kas Kecil | Kas & Bank + Kas Kecil (tiga layarnya menjadi satu tab dengan saringan tahap: diajukan → dicairkan → dipertanggungjawabkan → selesai) |
| **Antar-PT** | (tab di dalam layarnya tetap) | Antar Entitas |

### Grup **Akuntansi & Pajak** — pembukuan

| Entri | Tab | Berasal dari |
|---|---|---|
| **Buku Besar** | Jurnal · Bagan Akun | tetap |
| **Tutup Buku** | Daftar Periksa & Tutup · Buka Periode · Posting Gagal | Tiga entri menjadi satu; daftar periksa memuat juga rekonsiliasi persediaan, akun sementara, dan selisih saldo antar-PT yang sekarang tersembunyi di tab Buku Besar |
| **Laporan** | Laba-Rugi, Neraca & Arus Kas · Profitabilitas · Proyeksi Kas · Anggaran · Konsolidasi | tetap |
| **Pajak** | Faktur Keluaran · Faktur Masukan · PPN & PPh | tetap |
| **Aset Tetap** | — | dari Kas & Aset |

Yang pindah keluar dari keuangan:

| Layar | Ke | Alasan |
|---|---|---|
| Landed Cost | Pembelian › Pesanan Pembelian (tab) | Pembebanan biaya ke barang PO, bukan hutang |
| Kendaraan | Gudang & Logistik | Catatan operasional armada |

Grup "Kas & Aset" hilang karena ketiga isinya sudah punya tempat.

### Grup **SDM**

| Entri | Tab | Berasal dari |
|---|---|---|
| Karyawan | Karyawan · Struktur Organisasi | tetap |
| Kehadiran | Presensi · Cuti & Izin · Lembur · Lacak Lapangan | tetap |
| **Penggajian** | Proses Gaji · Komponen & Masukan · Setoran & Pajak | Payroll Run + Slip Gaji (slip menjadi isi detail proses) + rekap PPh 21 dari Pusat Pajak; lihat `09` §3.8 |
| **Kinerja & Insentif** | Capaian · Lembar Insentif · Target & Aturan · KPI Karyawan | Baru (Meja Insentif, `05`) + sub-tab Kinerja Sales dan Skema dari CRM + Komisi & Insentif dari Pengaturan + hub KPI |

### Yang berubah di tempat lain

| Tempat | Sebelum | Sesudah |
|---|---|---|
| CRM & Pelanggan | 7 sub-tab | 3: Pelanggan · Prospek · Interaksi |
| Pembelian | Punya Hutang Pemasok | Tautan dari detail PO ke tagihannya; hub pindah ke Keuangan |
| Tanya KN | Satu mode | + mode Keuangan dan tab Tindakan (`08` §6) — tanpa entri menu baru |
| Pusat Persetujuan | — | Tetap satu tempat untuk memutus; izin kredit, pengajuan plafon, lembar insentif, kartu asisten ikut muncul di sini |

### Hitungan

| | Sebelum | Sesudah |
|---|---|---|
| Entri menu keuangan | 18 dalam 4 grup | 10 dalam 2 grup |
| Entri menu SDM | 4 | 4 (satu di antaranya menyerap tiga tempat lain) |
| Sub-tab keuangan/insentif tersembunyi di CRM dan Pengaturan | 5 | 0 |
| Dasbor keuangan | 5 | 1 (+ kartu ringkas di beranda tiap peran yang menaut ke sini) |
| Antrean kerja keuangan | 3 | 1 |

## 3. Penyatuan di tingkat layar (tahap 2 dan 3)

Mengurangi entri menu saja belum mengurangi klik. Yang benar-benar menyederhanakan pekerjaan:

| # | Disatukan | Dari | Bergantung pada |
|---|---|---|---|
| 1 | **Satu form pembayaran** untuk terima dari pelanggan dan satu untuk bayar supplier, dipanggil dari mana pun (Beranda Keuangan, Piutang, detail pesanan, HP; Hutang, kontrabon, mutasi bank) | Lima sumber `payments[]`, empat jalur bayar supplier dengan form berbeda | PK-05, PK-19, PM-T3 |
| 2 | **Kartu pelanggan** — satu panel berisi eksposur, plafon, jadwal tagihan, kwitansi, titipan, denda, kasus, tindak lanjut, rekening koran. Dibuka dari baris mana pun di Piutang dan dari CRM (komponen yang sama) | Lima menu yang sekarang harus dibuka bergantian | CR-T2, CR-T5 |
| 3 | **Kartu supplier** — saldo, tagihan, kontrabon, pembayaran, retur, landed cost terkait | Tiga tab + layar retur | PK-41 |
| 4 | **Titipan & Saldo Kredit** satu layar | Uang Muka Pelanggan + Saldo Kredit | Duplikasi no. 3 di laporan audit (dua saldo kredit pelanggan) |
| 5 | **Kas Kecil** satu layar bertahap | Pengajuan Dana + Pertanggungjawaban + Hutang Reimburse | PK-24 |
| 6 | **Tutup Buku** satu layar berurutan dengan daftar periksa | Tutup Buku + Buka Periode + Posting Gagal + rekonsiliasi persediaan + akun sementara | PK-18, PK-43 |
| 7 | **Beranda Keuangan** | Meja Finance + dua dasbor + kartu keuangan di beranda admin/manajer | PK-16, PK-17 |
| 8 | **Slip di dalam proses gaji** | Tab Slip Gaji yang menduplikasi tabel di detail proses | PY-T1 |
| 9 | **Telusur dari angka ke dokumen** di semua laporan | Sekarang laporan → akun → jurnal → dokumen tidak tersambung | PK-43 |

Butir 1, 2, dan 9 yang paling mengurangi salah-orang: pengguna tidak lagi memilih "menu mana", hanya "pelanggan mana"
atau "angka mana".

## 4. Siapa melihat apa

Entri dan tab tampil menurut izin, bukan menurut grup. Usulan bawaan (final setelah K-09 dan K-17):

| Peran | Keuangan | Akuntansi & Pajak | SDM |
|---|---|---|---|
| Pemilik / Admin | Semua | Semua | Semua |
| Manajer | Semua | Semua | Semua kecuali yang dibatasi pemilik |
| Finance | Beranda · Piutang (semua tab; Kredit & Plafon tanpa hak memutus) · Kas & Bank · Antar-PT (lihat) · **Hutang dan cairkan kas kecil bila K-17 = Finance** | Pajak (faktur keluaran) · **Buku Besar dan Rekonsiliasi bila K-09 = ya** | Setoran & Pajak (bayar gaji dan setor, bila K-41) |
| Sales | Piutang › Penagihan (hanya pelanggannya) · Kasus (melapor) · Kas Kecil (pengajuan sendiri) | — | Kartu "Capaian & Insentif Saya" di beranda |
| Gudang | Hutang › Kontrabon (terima dokumen, tanpa nominal — K-18) · Antar-PT (barang) | — | — |
| Karyawan mana pun | Kas Kecil: pengajuan dan pertanggungjawaban miliknya, lewat Meja Saya | — | Profil Saya |

Ini sekaligus menutup temuan "izin ada, menu tidak" dan "menu ada, tujuan ditolak" (IA-03, IA-06, UX-17).

## 5. Aturan supaya menu tidak membengkak lagi

1. Layar baru masuk sebagai **tab di hub yang sudah ada**. Entri sidebar baru hanya bila pekerjaannya tidak termasuk
   hub mana pun.
2. Satu hub paling banyak **enam tab**. Bila lebih, itu tanda ada dua pekerjaan yang perlu dipisah — atau dua layar yang
   perlu disatukan.
3. **Tidak ada tab tingkat ketiga** (tab di dalam tab di dalam hub). Pengelompokan lebih dalam memakai saringan.
4. **Tidak ada dasbor baru.** Angka baru menjadi kartu di Beranda Keuangan, dan setiap kartu menaut ke layar yang
   menjelaskannya.
5. **Tidak ada antrean baru.** Hal yang butuh tindakan masuk "Perlu Tindakan"; hal yang butuh keputusan masuk Pusat
   Persetujuan.
6. Layar ditempatkan menurut **siapa yang mengerjakan**, bukan modul mana yang membuat datanya.
7. Setiap entri yang dipindah meninggalkan **alias** (mekanisme `hidden` + `aliasOf` di `hubTabs.js` sudah ada), supaya
   tautan lama, jejak dokumen, dan notifikasi tetap membuka layar yang benar.
8. Satu istilah per dokumen (aturan D8 di `04`). Label Inggris yang tersisa diindonesiakan ("Payroll Run", "Chart of
   Accounts").

Aturan 2–5 sebagian sudah dijaga `scripts/guardrails/verify_page_tabs.py` dan `verify_access_catalog_nav.py`; batas enam
tab dan larangan tab tingkat ketiga ditambahkan ke penjaga itu di MN-T1.

## 6. Tahap

| Tahap | Isi | Menyentuh | Prasyarat | Selesai bila |
|---|---|---|---|---|
| MN-T1 Pindah dan kelompokkan | Susunan §2 tanpa mengubah isi layar: grup, entri, tab, alias; menu per peran §4; label | `navStructure.js`, `hubTabs.js`, `roles.js`, `navMeta.js`, peta tujuan jejak dokumen | K-46; K-09/K-17 untuk kolom Finance | Tiap view lama masih terbuka lewat alias; penjaga navigasi hijau; uji jalan per peran: tidak ada entri yang berujung "tidak berwenang" |
| MN-T2 Satukan layar | Butir 4–8 di §3 | Layar terkait | Paket di kolom "Bergantung pada" | Per butir: satu layar menggantikan yang lama, yang lama dihapus |
| MN-T3 Form dan kartu tunggal | Butir 1–3 dan 9 di §3 | Form pembayaran, `Customer360Panel`, laporan | Idem | Menerima pembayaran dan membayar supplier bisa diselesaikan dari satu titik masuk mana pun tanpa pindah menu |

MN-T1 adalah bagian dari PK-44. Ia tidak bergantung pada perbaikan lain dan bisa dikerjakan lebih awal bila pemilik
ingin hasil yang cepat terlihat — dengan catatan bahwa memindah menu tidak memperbaiki angka di dalamnya.

## 7. Risiko

| Risiko | Penanganan |
|---|---|
| Pengguna kehilangan layar yang biasa dibuka | Alias; pencarian menu mengenali nama lama; catatan "pindah ke …" selama satu bulan |
| Peran gudang/sales tiba-tiba melihat grup Keuangan | Grup tampil hanya bila ada minimal satu entri yang diizinkan; isi entri disaring per tab |
| Dokumen navigasi (`KN_13`, `KN_14`, `KN_16`) makin basi | Diperbarui di commit yang sama (IA-15) |
| Tes layar yang bergantung pada `data-testid` menu | Dipertahankan; yang berubah hanya induknya |
