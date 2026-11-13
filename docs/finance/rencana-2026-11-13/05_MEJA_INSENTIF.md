# Rancangan — Meja Insentif

Status: rancangan untuk diputuskan pemilik. Belum ada kode. Kode dibaca di `9834947`; butir bertanda ✔ dicek langsung
pada berkas:baris yang disebut, sisanya dari pembacaan kode yang belum diuji jalan.

## 0. Ringkasan

- **Yang diminta:** insentif diputuskan manusia kasus per kasus, tetapi angkanya selalu berasal dari tiga hal — capaian
  target omzet, capaian target pencairan, dan kualitas harga jual. Sistem harus memudahkan **mencari dan menjumlahkan**
  angka itu per sales, per periode (bulan, triwulan, tahun), per PT; lalu hasil keputusan bisa terdiri dari beberapa
  komponen dalam satu penggajian.
- **Keadaan sekarang kebalikannya:** komisi dihitung otomatis menjadi satu angka per sales per bulan dan langsung masuk
  slip gaji; tidak ada tempat mengetik nominal, tidak ada komponen ganda, dan tidak ada dokumen keputusan (§1).
- **Usulan:** modul tersendiri bernama **Meja Insentif** dengan tiga bagian — *Capaian* (mencari dan menjumlah, hanya
  baca), *Lembar Insentif* (dokumen keputusan: nominal diketik manusia, angka dasarnya dipotret), *Target & Aturan*
  (per PT). Lembar yang disahkan menjadi **masukan komponen gaji**; penggajian hanya membayarkan.
- **Letak:** bukan di dalam Penggajian dan bukan di CRM. Alasannya di §3.
- **Tidak ada hitung otomatis yang mengikat.** Sistem boleh menampilkan "angka bantu" bila PT menginginkannya, tetapi
  nominal yang berlaku selalu yang diketik dan disahkan orang.

## 1. Keadaan sekarang

| Hal | Di kode | Akibat untuk permintaan ini |
|---|---|---|
| Mesin komisi | `compute_commission()` memilih strategi per PT: `per_sku` (bawaan) atau `achievement_tiered` (arsip) ✔ `backend/services/sales_force_service.py:189-198` | Otomatis; bukan keputusan manusia |
| Hasil | Dihitung ulang tiap layar dibuka; tidak disimpan | Tidak ada jejak "berapa dan mengapa" |
| Ke slip gaji | `_commission_for()` memanggil mesin saat slip dibuat; hasilnya **satu** field `commission`; bila mesin galat, nilainya 0 tanpa peringatan ✔ `backend/services/hr_payroll_service.py:245-257, 298-312` | Tidak bisa dua komponen; tidak bisa diketik |
| Ke buku besar | Akrual manual (Dr 6-5000 / Cr 2-1500) dan posting gaji menghitung dari dua sumber berbeda (FY-08) | Hutang insentif bisa menggantung |
| Target | `sales_targets` disimpan dengan kunci (sales, periode) **tanpa PT**; entitas dipaksa PT asal sales ✔ `backend/routers/crm.py:368-402` | Sales yang menjual di dua PT tidak bisa punya target per PT |
| Target triwulan/tahun | Dihitung sebagai jumlah target bulanan; pilihan "Kuartal/Tahunan" di layar tetap menyimpan satu bulan | Target triwulan yang berdiri sendiri tidak ada |
| Diskon | Pesanan baru selalu `discount_percent: 0` ("potongan hanya via Harga Khusus") ✔ `backend/routers/sales_orders.py:290`; mesin hanya membaca diskon baris | Faktor "harga murah → komisi kecil" praktis tidak bekerja |
| Pencairan | Σ semua `payments[]` pesanan ✔ `sales_force_service.py:109-113`, termasuk hapus sisa dan nota kredit | Angka pencairan memuat yang bukan uang masuk |
| Layar | CRM › Kinerja Sales, CRM › Skema (Arsip), Pengaturan › Penjualan › Komisi & Insentif, kolom "Komisi" di Penggajian, Beranda Sales | Rantainya tersebar di empat menu |

### Data yang tersedia

| Angka | Sumber | Bisa diandalkan? | Yang kurang |
|---|---|---|---|
| Omzet per sales, dasar tanggal pesanan | `fact_sales_lines` (per baris × anggota tim; neto tanpa PPN; per PT; tanggal WIB) | Ya | Memuat pesanan yang belum disetujui atau belum dikirim |
| Omzet dasar barang terkirim | `shipments` × harga neto baris pesanan | Sebagian | Surat jalan tidak menyimpan rupiah maupun sales; perlu dibangun |
| Omzet dasar faktur | `invoices` | Tidak | Hanya lahir dari jalur lama "simulasi bayar" (SL-05) |
| Retur / nota kredit | `credit_notes` → pesanan → tim sales | Ya | Nilai per baris produk tidak disimpan; empat pembuat nota kredit (FX-12…15) |
| Pencairan | `ar_receipts` (kas baru, deposit terpakai, alokasi per pesanan) | Ya di tingkat kwitansi | Alokasi per pesanan mencampur kas dan deposit; void **menghapus** baris `payments[]` sehingga angka periode lalu berubah mundur |
| Harga jual neto per baris | `price`, `line_total`, `price_source` di baris pesanan | Ya | — |
| Harga pembanding | `normal_price` hanya ada di baris harga khusus/OD | Sebagian | Baris harga langganan tanpa pembanding; batas bawah tidak dipotret |
| Margin per baris | `unit_cost` = rata-rata saat pesan | Sebagian | Bisa 0 (stok kosong, indent), sehingga margin tampak 100 % |
| Pemilik angka | `sales_team` pada pesanan (maks. 2 orang, ada pembagian) | Ya | Tiga aturan atribusi berbeda dipakai di tiga tempat |

## 2. Temuan tambahan (di luar 139 temuan audit)

| ID | Tingkat | Temuan | Bukti | Ditutup oleh |
|---|---|---|---|---|
| KM-01 ✔ | Tinggi | Faktor diskon mesin komisi praktis mati: diskon baris selalu 0 dan `normal_price` tidak dibaca | `routers/sales_orders.py:290`; `services/sales_force_service.py:251-260` | KM-T1 (harga acuan dipotret), KM-T4 (mesin lama dimatikan) |
| KM-02 ✔ | Tinggi | "Pencairan" menjumlah semua `payments[]` termasuk hapus sisa dan nota kredit | `services/sales_force_service.py:109-113`; `services/payment_variance_service.py:458-466`; `services/return_service.py:352` | PK-19 (jenis baris pembayaran), KM-T1 |
| KM-03 | Sedang | Tiga aturan "milik siapa" hidup bersamaan: KPI (pemilik pelanggan kini), mesin komisi (pemilik atau tim), fakta analitik (tim → sales pesanan → pembuat → pemilik) | `sales_force_service.py:93, 323`; `services/analytics_facts.py:41-60` | KM-T1, keputusan K-21 |
| KM-04 ✔ | Sedang | Target tanpa PT di kuncinya; triwulan/tahun bukan angka tersendiri; layar menawarkan pilihan yang tidak disimpan | `routers/crm.py:368-402`; `features/crm/IncentiveSchemeEditor.jsx:196-205` | KM-T1 |
| KM-05 | Sedang | Tidak ada dokumen keputusan insentif; angka sumber bergerak mundur (void kwitansi menghapus baris, retur, amandemen, serah-terima pelanggan) | `services/ar_receipt_service.py:725-741` | PK-19 (void = baris pembalik bertanggal), KM-T3 |
| KM-06 | Sedang | Serah-terima pelanggan hanya mengubah `assigned_sales_id`, bukan `sales_team`; pesanan baru bisa tetap teratribusi ke sales lama (belum diuji jalan) | `routers/crm.py:79-83`; `services/customer_service.py:83-91` | KM-T1 |
| KM-07 | Rendah | `incentive_unit` disimpan tetapi tidak dipakai; daftar "sales" berbeda antara akrual (`role == "sales"`) dan gaji (`role_in`) | `routers/incentive_rates.py:20-31`; `services/gl_service.py:2909` | KM-T4 |

## 3. Keputusan letak: modul sendiri, tersambung ke penggajian

| Pilihan | Untuk | Lawan | Putusan |
|---|---|---|---|
| Di dalam Penggajian | Ujungnya memang slip gaji | Yang memutuskan insentif (pemilik, manajer penjualan) bukan yang menjalankan gaji; datanya dari penjualan dan keuangan; membuka layar gaji berarti membuka data gaji orang lain; triwulanan dan tahunan tidak seirama dengan proses gaji bulanan | Tidak |
| Di dalam CRM (tempat sekarang) | Dekat dengan data penjualan | CRM adalah wilayah kerja sales; keputusan bayaran tidak boleh berada di wilayah yang bisa diubah pihak yang dibayar | Tidak |
| **Modul sendiri, di grup SDM** | Izin sendiri (`incentive.*`); bisa dibuka manajer penjualan tanpa melihat gaji; satu pintu untuk seluruh rantai; hasilnya masukan resmi bagi penggajian | Satu entri menu baru (diimbangi hilangnya tiga tempat lama, lihat `01`) | **Ya** |

Pembagian tanggung jawab:

```text
Penjualan & Keuangan ──angka──▶ MEJA INSENTIF ──lembar disahkan──▶ PENGGAJIAN ──▶ slip, PPh 21, jurnal bayar
(omzet, pencairan, harga)      (cari · jumlahkan ·                (hanya membayarkan;
                                putuskan · potret)                 tidak menghitung insentif)
```

Tunjangan jabatan, makan, hari raya, dan lembur **tidak** masuk Meja Insentif. Itu urusan komponen gaji
([`09_HR_DAN_PAYROLL.md`](09_HR_DAN_PAYROLL.md)). Keduanya bertemu di slip sebagai baris komponen yang berbeda.

## 4. Tiga bagian layar

Satu entri menu "Kinerja & Insentif" dengan tab: **Capaian · Lembar Insentif · Target & Aturan** (+ KPI Karyawan yang
sekarang berdiri sendiri).

### 4.1 Capaian — mencari dan menjumlahkan (hanya baca)

Pengguna memilih **PT** dan **periode** (bulan, triwulan, tahun, atau rentang bebas). Layar menampilkan satu baris per
sales:

| Kelompok | Kolom |
|---|---|
| Omzet | Target · Omzet · % capaian · Retur · Omzet bersih |
| Pencairan | Target · Uang masuk · % capaian · Sisa piutang · Lewat tempo |
| Kualitas harga | Realisasi harga (%) · Rata-rata potongan · Porsi omzet di bawah harga acuan · Margin (%) — margin hanya untuk yang berizin |
| Lain | Pelanggan baru · Jumlah pesanan · Catatan data (mis. "3 baris tanpa harga acuan", "2 baris HPP 0") |

Yang membuat layar ini "meja kerja", bukan laporan:

1. **Telusur sampai dokumen.** Klik angka omzet → daftar surat jalan/pesanan penyusunnya; klik uang masuk → daftar
   kwitansi dan alokasinya. Tiap baris bisa dibuka.
2. **Jumlah pilihan.** Centang sales, pelanggan, atau dokumen mana pun → bilah bawah menampilkan jumlah, rata-rata,
   dan banyaknya. Ini yang dimaksud "mencari dan menjumlahkan": pengguna bebas menyusun sendiri dasar keputusannya.
3. **Saring dan kelompokkan** menurut pelanggan, kategori/lini produk, kanal, sumber harga (umum, PT, langganan,
   khusus), atau anggota tim.
4. **Bandingkan periode** (bulan ini vs bulan lalu vs bulan sama tahun lalu) dan **kumulatif** (tahun berjalan).
5. **Simpan tampilan** dan **ekspor Excel** dengan definisi angka tercetak di lembar pertama.
6. **Tombol "Buat lembar insentif dari tampilan ini".**

Setiap kolom punya keterangan definisi yang sedang berlaku untuk PT itu (lihat §5), supaya dua orang yang membuka
layar yang sama membaca angka yang sama.

### 4.2 Lembar Insentif — dokumen keputusan

Satu lembar = satu PT + satu **periode bayar** (bulan penggajian). Isinya baris per (sales × komponen):

| Kolom baris | Isi | Sumber |
|---|---|---|
| Sales | Nama; tertaut ke karyawan | Master |
| Komponen | Mis. "Insentif Bulanan", "Insentif Triwulan", "Bonus Tahunan", "Insentif Khusus" | Daftar komponen PT |
| Periode dasar | Mis. Okt 2026; Triwulan III 2026 | Dipilih saat baris dibuat |
| Angka dasar | Target, capaian omzet, capaian pencairan, kualitas harga | **Dipotret** dari Capaian saat baris dibuat |
| Angka bantu | Kosong, kecuali PT mengaktifkan rumus bantu (§4.3) | Dihitung, tidak mengikat |
| **Nominal** | Diketik | Manusia |
| Catatan | Wajib bila nominal berbeda dari angka bantu, atau bila baris adalah penyesuaian | Manusia |

Contoh satu lembar untuk gaji November 2026, PT A:

| Sales | Komponen | Periode dasar | Omzet / target | Cair / target | Realisasi harga | Nominal |
|---|---|---|---|---|---|---|
| Andi | Insentif Bulanan | Okt 2026 | 1.000 jt / 800 jt | 700 jt / 750 jt | 86 % | 2.000.000 |
| Andi | Insentif Triwulan | Tw III 2026 | 2.600 jt / 2.400 jt | 2.300 jt / 2.250 jt | 88 % | 3.000.000 |
| Budi | Insentif Bulanan | Okt 2026 | 500 jt / 500 jt | 520 jt / 450 jt | 100 % | 3.500.000 |

Budi menjual separuh omzet Andi tetapi pada harga penuh dan melampaui target pencairan; pemutus melihat ketiga angka
berdampingan dan memberi lebih besar. Sistem tidak menghalangi maupun memaksakan.

Alur dan aturannya:

| Status | Siapa | Yang terjadi |
|---|---|---|
| Draf | Penyiap | Baris ditambah, nominal diisi. "Segarkan angka dasar" masih boleh |
| Diajukan | Penyiap | Angka dasar terkunci; lembar tidak bisa diubah penyiap |
| Disahkan | Pemutus (≠ penyiap) | Nominal boleh dikoreksi pemutus dengan catatan; potret dibekukan; akrual dijurnal (§6); baris menjadi masukan gaji |
| Dibayarkan | Penggajian | Ditandai saat proses gaji yang memuatnya diposting |
| Dikembalikan | Pemutus | Kembali ke draf dengan alasan |

- Lembar yang sudah disahkan **tidak diubah**. Koreksi (retur setelah insentif dibayar, kwitansi dibatalkan, salah
  ketik) dibuat sebagai **baris penyesuaian** di lembar periode berikutnya, merujuk baris asalnya, boleh bernilai
  negatif.
- Lebih dari satu lembar per PT per periode bayar diperbolehkan (mis. lembar susulan), selama belum dibayarkan.
- Layar menandai bila angka di Capaian hari ini sudah berbeda dari potret (mis. ada retur baru), dengan selisihnya —
  sebagai bahan penyesuaian, bukan perubahan otomatis.

### 4.3 Target & Aturan — per PT

| Yang diatur | Isi |
|---|---|
| Target | Per sales, per PT, per jenis periode (bulan / triwulan / tahun), masing-masing angka tersendiri untuk omzet dan pencairan. Bisa disalin dari periode sebelumnya dan diimpor dari Excel |
| Komponen insentif | Daftar per PT: kode, nama, jenis periode dasar, kolom angka yang ditampilkan, kena pajak (ya), aktif |
| Definisi angka | Pilihan per PT untuk dasar omzet, isi pencairan, dan harga acuan (§5). Berversi dan bertanggal berlaku |
| Rumus bantu (opsional) | Per komponen: dasar (omzet / pencairan / omzet tertimbang kualitas harga) × tarif menurut jenjang capaian. Bawaan **mati** |
| Peran | Siapa penyiap, siapa pemutus, siapa boleh melihat margin |

Perubahan definisi tidak mengubah lembar yang sudah disahkan, karena potret menyimpan versi definisinya.

### 4.4 Untuk sales

Kartu "Capaian & Insentif Saya" di Beranda Sales dan Profil Saya: target, capaian berjalan, dan — setelah lembar
disahkan — rincian komponen beserta angka dasarnya. Menggantikan "Komisi MTD" yang sekarang berasal dari mesin otomatis.

## 5. Definisi angka (harus diputuskan; usulan saya di kolom terakhir)

| Angka | Pilihan | Usulan | Alasan |
|---|---|---|---|
| Omzet (K-19) | Saat pesanan dibuat · saat barang dikirim · saat lunas | **Barang terkirim, tanpa PPN, dikurangi retur** | Sama dengan pendapatan di Laba-Rugi, sehingga bisa dicocokkan; pesanan yang tidak jadi dikirim tidak menaikkan capaian |
| Pencairan (K-20) | Semua baris pembayaran · hanya uang masuk | **Hanya uang yang benar-benar masuk dan sudah dialokasikan ke pesanan**: kas/transfer/QRIS, giro saat cair, deposit dan titipan bank saat dialokasikan. Tidak termasuk hapus sisa, nota kredit, saldo kredit dari retur | Insentif pencairan menghargai uang masuk, bukan penghapusan piutang |
| Pemilik angka (K-21) | Sales pada pesanan · pemilik pelanggan saat ini | **Sales pada pesanan (dengan pembagian tim), dipotret saat pesanan dibuat**; pencairan mengikuti pesanannya | Serah-terima pelanggan tidak memindahkan hasil kerja lama |
| Harga acuan (K-23) | Harga daftar PT · harga umum · harga langganan · batas bawah | **Harga daftar PT pada tanggal pesanan**, dipotret di tiap baris pesanan | Satu pembanding yang sama untuk semua sales di PT itu |
| Kualitas harga | — | Tiga angka berdampingan: *realisasi harga* = Σ nilai neto ÷ Σ (jumlah × harga acuan); *porsi di bawah acuan*; *margin* (dengan tanda bila HPP 0) | Realisasi harga tidak bergantung pada HPP yang kadang 0 |
| Triwulan dan tahun (K-24) | Kalender · tahun buku | **Mengikuti tahun buku PT**; target triwulan dan tahun adalah angka tersendiri | Konsisten dengan laporan keuangan |
| Koreksi setelah dibayar (K-25) | Mengubah lembar lama · baris penyesuaian | **Baris penyesuaian di periode berikut** | Lembar lama adalah bukti keputusan |

Dua pengaman angka (aturan D2 di `04`):

1. **Omzet Meja Insentif harus cocok dengan buku besar.** Untuk tiap PT dan bulan: Σ omzet terkirim semua sales
   (+ penjualan tanpa sales) = mutasi akun pendapatan, di luar antar-PT dan jurnal penutup. Selisih ditampilkan di
   layar dengan daftar penyebabnya dan menjadi invarian di `verify_data_integrity.py`.
2. **Pencairan harus cocok dengan kas.** Σ pencairan + penerimaan yang belum dialokasikan = kas masuk dari pelanggan
   pada periode itu.

Bila dua pengaman ini merah, layar Capaian menampilkan peringatan dan tombol "Buat lembar" meminta konfirmasi.

## 6. Sambungan ke penggajian dan buku besar

| Kejadian | Jurnal (per PT) | Catatan |
|---|---|---|
| Lembar disahkan | Dr Beban Insentif (6-5000) / Cr Hutang Insentif (2-1500), bertanggal akhir periode dasar terbaru di lembar atau tanggal sah — sesuai K-13 | Satu jurnal per lembar; kunci jurnal = id lembar |
| Proses gaji memuat baris | Dr Hutang Insentif (2-1500) sebesar **persis** Σ baris yang dimuat; masuk bruto PPh 21 | Menutup FY-08: satu sumber angka |
| Baris penyesuaian negatif | Kebalikan akrual; mengurangi bruto di gaji periode itu | — |

- Baris yang disahkan ditulis ke koleksi **masukan komponen gaji** (rancangan di `09` §3) dengan kunci unik per baris
  lembar. Proses gaji mengambil masukan berstatus "disahkan, belum dibayar" untuk PT dan periode bayarnya.
- Di slip, tiap baris tampil sendiri dengan nama komponen dan periode dasarnya ("Insentif Triwulan III 2026").
- Mesin komisi otomatis dimatikan untuk PT yang sudah memakai lembar (`hr.payroll_commission_mode = off`, yang
  sekarang belum dihormati kode — PY-06). Tanpa itu insentif terbayar dua kali.
- Insentif dibayar **lewat penggajian**, tidak lewat kas langsung, supaya masuk hitungan PPh 21. Bila pemilik ingin
  dibayar di luar tanggal gajian, itu proses gaji berjenis "susulan" (PY-02), bukan transaksi kas.
- Sales yang menjual untuk dua PT (K-26): lembar tetap per PT. Usulan: PT tempat penjualan terjadi mengakui bebannya;
  pembayaran lewat gaji PT tempat karyawan terdaftar; selisihnya menjadi tagihan antar-PT lewat dokumen antar-PT.
  Butuh keputusan pemilik karena menyangkut pajak dua PT.

## 7. Model data

| Koleksi | Kunci unik | Isi pokok |
|---|---|---|
| `sales_targets` (diubah) | (entitas, sales, jenis periode, periode) | target omzet, target pencairan |
| `incentive_components` | (entitas, kode) | nama, jenis periode dasar, kolom tampil, rumus bantu, aktif |
| `incentive_definitions` | (entitas, berlaku sejak) | dasar omzet, isi pencairan, harga acuan |
| `incentive_sheets` | nomor per entitas | entitas, periode bayar, status, baris[], penyiap, pemutus, riwayat keputusan, `gl_status` |
| baris lembar | (lembar, sales, komponen, periode dasar) | potret angka + versi definisi + sidik sumber, angka bantu, nominal, catatan, rujukan baris yang dikoreksi |
| `fact_shipment_sales` (baru, turunan) | (surat jalan, baris, sales) | nilai neto, harga acuan, biaya, entitas, tanggal WIB; bisa dibangun ulang dari dokumen |
| `fact_collections` (baru, turunan) | (kwitansi, alokasi, sales) | jenis sumber uang, nilai, tanggal; bisa dibangun ulang |
| baris pesanan (ditambah field) | — | `list_price`, `floor_price` dipotret untuk **semua** baris |

Semua angka turunan mengikuti aturan D2: ada cara membangun ulang dan ada invarian.

## 8. Izin

| Izin | Pemegang yang diusulkan | Boleh |
|---|---|---|
| `incentive.view` | Manajer, pemilik, keuangan | Melihat Capaian semua sales di PT-nya |
| `incentive.view_margin` | Pemilik, manajer tertentu | Melihat kolom margin |
| `incentive.prepare` | Admin penjualan atau keuangan | Membuat dan mengajukan lembar |
| `incentive.approve` | Pemilik / manajer (≠ penyiap) | Mengesahkan, mengembalikan |
| `incentive.configure` | Pemilik / admin | Target, komponen, definisi |
| (tanpa izin khusus) | Sales | Hanya kartu miliknya |

## 9. Tahap bangun

| Tahap | Isi | Prasyarat | Selesai bila |
|---|---|---|---|
| KM-T1 Data | Fakta omzet terkirim dan pencairan; potret harga acuan di baris pesanan; target per PT per jenis periode; satu aturan atribusi | PK-19 (jenis baris pembayaran; void sebagai baris pembalik) | Dua invarian §5 hijau di data acuan; target triwulan tersimpan sebagai angka sendiri |
| KM-T2 Capaian | Layar baca: tabel, telusur, jumlah pilihan, saring, banding, ekspor | KM-T1; PK-41 (RP-08) | Angka satu bulan nyata dicocokkan dengan rekap manual yang sekarang dipakai pemilik — **dijalankan berdampingan minimal satu periode** |
| KM-T3 Lembar | Dokumen, potret, alur sah, baris penyesuaian, ekspor. Belum menjurnal | KM-T2 | Lembar disahkan → potret tidak berubah walau data sumber berubah; penyiap tidak bisa mengesahkan sendiri |
| KM-T4 Gaji dan buku besar | Masukan komponen gaji, akrual, pelunasan, mematikan mesin otomatis per PT | KM-T3; PK-22; PY-T1 | Saldo 2-1500 = Σ baris disahkan belum dibayar, per PT; slip menampilkan tiap komponen |
| KM-T5 Sales | Kartu "Capaian & Insentif Saya"; layar lama di CRM dan Pengaturan dipindah atau dihapus | KM-T4 | Tidak ada lagi "Komisi MTD" dari mesin otomatis di PT yang sudah beralih |

KM-T2 berguna sendiri walau tahap berikutnya belum dibangun: pemilik sudah bisa mencari dan menjumlahkan, lalu
memutuskan di luar sistem seperti sekarang.

## 10. Yang sengaja tidak dirancang

- Rumus insentif baku. Pemilik menyatakan tidak ada aturan tetap; rumus bantu disediakan sebagai pilihan, bukan inti.
- Insentif untuk selain sales (admin penjualan, supervisor). Modelnya memungkinkan (baris per karyawan), tetapi angka
  dasarnya perlu definisi tersendiri.
- Sengketa/keberatan sales atas angka. Bisa ditambahkan sebagai catatan per baris di KM-T5 bila diperlukan.
