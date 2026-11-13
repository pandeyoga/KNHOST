# Rancangan — Piutang lanjut: plafon, blokir, persetujuan, denda (dan catatan untuk hutang)

Status: rancangan untuk diputuskan pemilik. Belum ada kode. Kode dibaca di `9834947`; butir bertanda ✔ dicek langsung
pada berkas:baris yang disebut.

## 0. Ringkasan

- **Sebagian besar bahannya sudah ada**, tetapi tidak membentuk satu kendali: ada plafon per pelanggan, blokir karena
  telat, izin kredit dari manajer, nota denda dengan pembebasan, tahan kirim untuk bayar-dulu. Yang membuatnya belum
  bisa diandalkan ada lima: plafon bisa diubah sales sendiri; pemeriksaan hanya saat pesanan lahir; ambang telat
  ditulis mati di kode; ada tiga cara berbeda menentukan jatuh tempo; dan aturan denda per pelanggan tidak punya layar.
- **Usulan:** satu **profil kredit** per pelanggan per PT, satu **jadwal tagihan** sebagai satu-satunya sumber jatuh
  tempo, satu **mesin gerbang** yang dipanggil di beberapa titik (bukan hanya saat pesanan dibuat), **saldo piutang
  tersimpan** per pelanggan per PT, dan denda yang aturannya berlapis (PT → pelanggan → rencana) dengan pembebasan
  tercatat.
- **Urutan penting:** rumus umur piutang yang sekarang memblokir kredit adalah temuan RP-03. Memperketat blokir di atas
  rumus yang salah akan memblokir pelanggan yang tidak telat. PK-41 (RP-03) dan PK-08 (denda) harus selesai dulu.

## 1. Keadaan sekarang

| Aturan yang diminta | Sudah ada? | Di mana | Lubangnya |
|---|---|---|---|
| Nilai hutang pelanggan | Ada, dihitung saat dibuka, **tidak disimpan** | `compute_customer_credit`, `backend/services/customer_service.py:208-275` | Paling banyak 2.000 pesanan dibaca; deposit tidak mengurangi; tidak ada gabungan lintas PT |
| Plafon kredit | Ada: `customers.credit_limit`, 0 = tanpa batas | Diperiksa hanya saat pesanan dibuat ✔ `backend/routers/sales_orders.py:363-375` | Sales punya izin ubah pelanggan dan `PATCH` menerima `credit_limit` serta `status` ✔ `backend/permissions_config.py:116`, `backend/routers/customers.py:171-178`. Finance hanya bisa melihat. Tanpa riwayat, tanpa persetujuan |
| Telat → tidak bisa pesan | Sebagian: blokir bila telat **> 14 hari**; 1–14 hari hanya peringatan | Gerbang yang sama | `OVERDUE_BLOCK_DAYS = 14` dan `WARNING_RATIO = 0.8` ditulis mati ✔ `customer_service.py:14-15` (dan disalin di `ar_aging_service.py:34-35`) |
| Lewat plafon → ditolak kecuali disetujui | Ada: 409 `CREDIT_BLOCKED`; izin kredit diajukan sales, diputus manajer ✔ `routers/crm.py:91-156` | Sama | Izin tanpa masa berlaku; nominal 0 = tak terbatas ✔ `customer_service.py:523-530`; daftar dan keputusan tanpa penjaga entitas; penyetuju "manager" ditulis mati; percobaan pesanan yang ditolak tidak tercatat |
| Telat → denda | Ada sebagai dokumen `penalties` (draf → terbit → bayar / bebas / ubah) | `backend/services/penalty_service.py` | Proses harian hanya memindai pesanan yang punya rencana bayar; lainnya lewat tombol manual; bawaan `draft` (tidak tertagih sampai diterbitkan orang); FX-02, FX-03, FX-04 |
| Denda bisa berbeda per PT / pelanggan | Mesinnya ya, layarnya tidak | Lapisan global → PT → pelanggan (`ar.denda_rate_pct_per_month`, `ar.grace_days`, `payment.penalty_mode/base/cap_pct`) | Pusat Pengaturan hanya menawarkan Global / Badan usaha; lapisan pelanggan dan override per rencana tanpa layar |
| Denda pelanggan dihapus | Ada per nota (alasan wajib, peran penyetuju) | `penalty_service.py:400-428` | "Pelanggan ini bebas denda" hanya lewat `penalty_mode=off` lapisan pelanggan — tanpa layar, tanpa alasan, tanpa masa berlaku |
| Termin per pelanggan | Master termin per PT; `customers.payment_profile` | Tidak ditegakkan | Layar checkout menawarkan semua termin; server tidak mengadu dengan profil ✔ `routers/sales_orders.py:353-360` |
| Tahan kirim bayar-dulu / DP | Ada di semua jalur kirim | `backend/services/dispatch_payment_gate.py` | Hanya berlaku bila `dp_percent > 0`; FX-16 |
| Pengingat | Notifikasi internal H-3/H-1/H/H+1 dan tindak lanjut manual | `alert_ops_service.py`, `routers/crm.py:186-236` | Tidak ada pengingat ke pelanggan, surat tagih, atau rekening koran pelanggan |

**Rumus yang sekarang memblokir** (dibaca dari kode):

- Sisa pesanan = nilai pesanan − Σ pembayaran. Pesanan bertermin tunai dilewati seluruhnya.
- Jatuh tempo = tanggal surat jalan **pertama** + hari termin, untuk **seluruh** sisa pesanan (RP-03).
- Blokir bila: piutang ≥ plafon, atau telat terlama > 14 hari, atau status pelanggan `blocked`, atau piutang + pesanan
  baru > plafon.

## 2. Temuan tambahan (di luar 139 temuan audit)

| ID | Tingkat | Temuan | Bukti | Ditutup oleh |
|---|---|---|---|---|
| CR-01 ✔ (dijalankan 13 Nov: plafon 5 juta → 900 juta, terblokir → aktif, jawaban 200) | Tinggi | Sales bisa menaikkan plafon dan membuka blokir pelanggannya sendiri; Finance tidak bisa mengubah keduanya | `permissions_config.py:116, 358`; `routers/customers.py:171-183` | PK-45 (cepat: keluarkan dua field dari `PATCH` umum), CR-T1 |
| CR-02 | Tinggi | Pemeriksaan kredit hanya saat pesanan lahir. Tambah baris, tambah jumlah, ganti termin, amandemen, setujui, lepas ke gudang, dan kirim tidak memeriksa ulang | `routers/sales_orders.py:363-375` satu-satunya pemanggil gerbang; `services/so_override_service.py` | CR-T3 |
| CR-03 ✔ | Sedang | Ambang telat (14 hari) dan ambang peringatan (80 %) ditulis mati di dua berkas | `customer_service.py:14-15`; `ar_aging_service.py:34-35` | CR-T1 |
| CR-04 ✔ | Sedang | Izin kredit: tanpa masa berlaku; nominal 0 berarti tak terbatas; daftar dan keputusan tidak diadu dengan entitas; satu peran penyetuju untuk semua nominal | `customer_service.py:523-530`; `routers/crm.py:118-156` | PK-45 (penjaga entitas), CR-T3 |
| CR-05 | Tinggi (perlu uji jalan) | Termin bebas dipilih sales untuk pelanggan mana pun; pesanan bertermin tunai keluar dari hitungan piutang, dan tahan-kirim hanya untuk yang ber-DP — barang bisa keluar tanpa bayar dan tanpa jejak di kendali kredit | `routers/sales_orders.py:353-360`; `customer_service.py:16-17, 224-236`; `dispatch_payment_gate.py:66` | CR-T2, CR-T3 |
| CR-06 | Sedang | Tiga definisi jatuh tempo: kendali kredit (surat jalan pertama + termin pesanan), denda tanpa rencana (tanggal pesanan + termin profil), taksiran denda di umur piutang (bulan penuh, sedangkan nota dihitung harian). Rencana cicilan yang disepakati tidak dibaca kendali kredit | `customer_service.py:169-205`; `penalty_service.py:104-109, 252-253`; `ar_aging_service.py:76-82` | CR-T2 |
| CR-07 | Sedang | Denda otomatis hanya untuk pesanan ber-rencana; aturan per pelanggan dan per rencana tidak punya layar | `penalty_service.py:584-596`; `features/settings/config/SettingsScopeBar.jsx:68-74` | CR-T4 |
| CR-08 | Sedang | Tidak ada riwayat plafon, catatan pesanan yang ditolak, maupun rekening koran pelanggan | Pencarian di kode tidak menemukan | CR-T1, CR-T5 |
| CR-09 | Sedang | Saldo piutang dihitung ulang tiap dibuka dari paling banyak 2.000 pesanan | `customer_service.py:216` | CR-T2 |

## 3. Rancangan

### 3.1 Profil kredit — satu per pelanggan per PT

Dipisah dari data pelanggan biasa, supaya izin mengubahnya berbeda dari izin mengubah alamat.

| Field | Arti | Bawaan |
|---|---|---|
| Plafon | Batas eksposur (rupiah). Kosong = ikut bawaan PT; "tanpa batas" adalah pilihan eksplisit, bukan angka 0 | Dari pengaturan PT |
| Berlaku sampai | Tanggal kaji ulang plafon; setelah lewat, plafon kembali ke bawaan PT dan muncul di daftar kerja | Kosong |
| Termin yang diizinkan | Daftar termin yang boleh dipilih untuk pelanggan ini; satu di antaranya bawaan | Tunai saja, sampai diisi |
| Hari tenggang | Hari setelah jatuh tempo sebelum dianggap telat | Dari PT |
| Hari blokir | Telat lebih dari ini → pesanan baru ditahan | Dari PT |
| Aturan denda | Ikut PT / khusus (tarif, dasar, batas atas) / **bebas denda** (alasan + berlaku sampai) | Ikut PT |
| Status kredit | Normal · Awas · Tahan (otomatis) · **Blokir manual** (alasan; hanya dilepas orang) | Normal |
| Kelompok kredit (opsional) | Beberapa pelanggan — bisa lintas PT — berbagi satu plafon bersama | Kosong |

- **Perubahan profil adalah dokumen**, bukan suntingan: "Pengajuan perubahan kredit" (nilai lama → baru, alasan,
  lampiran) → diputus pemegang wewenang menurut jenjang nominal → tercatat sebagai riwayat. Sales boleh mengajukan,
  tidak boleh memutuskan.
- Pengaturan bawaan per PT (plafon bawaan, tenggang, hari blokir, ambang peringatan, aturan denda, titik periksa) ada di
  Pusat Pengaturan. Layar profil pelanggan menampilkan nilai efektif beserta asalnya ("ikut PT" / "khusus").

### 3.2 Jadwal tagihan — satu sumber jatuh tempo

Setiap pesanan non-tunai punya satu atau lebih **baris tagihan**: jumlah, tanggal jatuh tempo, status.

| Jenis pesanan | Baris tagihan lahir saat | Jatuh tempo |
|---|---|---|
| Tempo biasa | Tiap surat jalan diposting | Tanggal surat jalan + hari termin, senilai barang di surat jalan itu |
| DP / bayar-dulu | Pesanan dikonfirmasi | Sebelum kirim, senilai persen DP |
| Cicilan (rencana bayar) | Rencana disetujui | Per baris rencana |

Koleksi `payment_plans` yang sudah ada diperluas menjadi jadwal tagihan untuk semua pesanan non-tunai; tidak dibuat
koleksi kedua (aturan D1 di `04`). Semua pemakai membaca dari sini: umur piutang (menutup RP-03), kendali kredit, denda,
proyeksi arus kas, pengingat, dan instruksi bayar ([`07`](07_PAJAK_DAN_PEMBAYARAN.md)). Ini keputusan K-16; usulan
saya seperti tabel di atas.

### 3.3 Eksposur dan saldo tersimpan

```text
Eksposur = piutang atas barang terkirim yang belum lunas
         + pesanan terkonfirmasi yang belum dikirim
         + giro diterima yang belum cair
         − titipan / saldo kredit yang belum dipakai   (bila pemilik setuju dikurangkan)
```

Layar selalu menampilkan keempat barisnya, bukan hanya totalnya (K-31).

Saldo disimpan di `customer_balances` per (pelanggan, PT): piutang terbuka, lewat tempo, tanggal jatuh tempo tertua,
pesanan terbuka, giro beredar, titipan, denda terbuka, pembayaran terakhir. Diperbarui oleh fungsi alokasi tunggal
(PK-19), posting surat jalan, dan nota kredit. Karena ini angka turunan, wajib ada pembangun ulang dan invarian harian
"saldo tersimpan = hitung ulang dari dokumen" serta "Σ piutang terkirim per PT = saldo akun piutang" (aturan D2).

### 3.4 Mesin gerbang kredit

Satu fungsi, dipanggil di **titik periksa** yang dipilih per PT:

| Titik periksa | Usulan bawaan |
|---|---|
| Pesanan dibuat | Periksa |
| Pesanan diubah sehingga nilainya naik atau terminnya melonggar (override, amandemen) | Periksa |
| Dilepas ke gudang | Periksa |
| Surat jalan dibuat | Periksa |

Hasil gerbang beserta alasan terstruktur:

| Kondisi | Hasil |
|---|---|
| Eksposur + pesanan ini ≤ plafon, tidak ada yang telat melewati tenggang | Lolos |
| Eksposur ≥ ambang peringatan, atau telat dalam tenggang | Lolos dengan peringatan |
| Eksposur + pesanan ini > plafon | **Tahan — lewat plafon** |
| Telat > hari blokir | **Tahan — telat** |
| Status blokir manual | **Tahan — blokir manual** (tidak bisa dilepas otomatis) |
| Termin yang dipilih tidak ada di daftar termin pelanggan | **Tolak** |
| Plafon kedaluwarsa | Diperlakukan sebagai plafon bawaan PT + masuk daftar kerja |

Catatan atas keputusan pemilik yang sudah ada: per uji coba 22 Okt ("Blokir, kecuali ACC Manajer"), pesanan dari
pelanggan terblokir **ditolak** dan izin diminta sebelum checkout. Rancangan ini mempertahankannya untuk titik "pesanan
dibuat". Yang ditambahkan: (a) percobaan yang ditolak dicatat (siapa, pelanggan, nilai, alasan) supaya terlihat di daftar
kerja; (b) keranjang tersimpan sehingga setelah izin keluar, checkout tidak diulang dari nol; (c) di titik periksa
sesudahnya, pesanan yang sudah ada **ditahan** (status "Tahan kredit"), bukan dibatalkan.

Pesanan tunai / bayar-dulu dari pelanggan yang sedang ditahan (K-27): usulan saya diperbolehkan, dengan barang ditahan
sampai lunas — termin tunai harus ikut tahan-kirim, tidak hanya yang ber-DP (menutup CR-05).

### 3.5 Izin kredit (pelepasan)

| Hal | Sekarang | Usulan |
|---|---|---|
| Lingkup | Per pelanggan, sekali pakai | Per pesanan **atau** per pelanggan sampai nominal tertentu |
| Nominal | 0 = tak terbatas | Wajib > 0 |
| Masa berlaku | Tidak ada | Wajib (bawaan dari PT, mis. 3 hari) |
| Penyetuju | Peran "manager" ditulis mati | Jenjang nominal dari aturan persetujuan per PT; pengaju ≠ penyetuju |
| Alasan | Teks bebas | Kode alasan + catatan |
| Jejak | Log audit | Tampil di kartu pelanggan dan di pesanan yang memakainya |
| Pemberitahuan | Tidak ada saat diajukan | Ke penyetuju saat diajukan; ke pengaju saat diputus |

Mengganti termin ke yang lebih longgar memerlukan izin yang sama (FX-16).

### 3.6 Denda keterlambatan

Aturan berlapis; lapisan yang lebih khusus menang:

```text
Global  →  PT  →  Pelanggan (profil kredit)  →  Rencana bayar tertentu
```

| Unsur aturan | Pilihan |
|---|---|
| Mode | Mati · **Usulan** (nota draf, diterbitkan orang) · Otomatis (nota langsung terbit) |
| Tarif | % per bulan, dihitung harian |
| Dasar | Sisa baris tagihan yang telat (bukan seluruh pesanan) |
| Tenggang | Hari |
| Batas atas | % dari pokok |
| Nominal terkecil | Di bawah ini tidak dibuat nota |

- Dihitung dari **jadwal tagihan** untuk semua pesanan non-tunai, bukan hanya yang ber-rencana (menutup CR-07).
- Satu nota per pelanggan per PT per bulan, memuat rincian per baris tagihan; hari telat tidak dihitung dua kali
  lintas bulan (FX-03).
- **Pembebasan** ada dua tingkat, keduanya tercatat: per nota (sudah ada: alasan + penyetuju; setelah PK-08 membalik
  sisa, bukan nominal penuh), dan per pelanggan ("bebas denda" di profil kredit dengan alasan dan masa berlaku, diputus
  lewat pengajuan perubahan kredit).
- Denda yang belum dibayar ikut tampil di kartu pelanggan dan rekening koran, tetapi **tidak** menambah eksposur untuk
  plafon kecuali pemilik memutuskan lain.
- Jurnal dan pembayaran denda mengikuti PK-08 (kunci per kejadian; bayar lewat kas dengan rekening).

Usulan bawaan mode: **Usulan** (K-30). Denda yang terbit otomatis tanpa dilihat orang berisiko merusak hubungan dengan
pelanggan bila ada salah catat pembayaran; setelah angka terbukti benar beberapa bulan, PT bisa beralih ke otomatis.

### 3.7 Kerja harian pengendali kredit

Tab "Kredit & Plafon" di pusat Piutang (lihat [`01`](01_PENGGABUNGAN_MENU.md)) dengan satu daftar kerja:

| Antrean | Isi |
|---|---|
| Menunggu keputusan | Izin kredit dan pengajuan perubahan profil |
| Ditahan | Pesanan berstatus "Tahan kredit" + pesanan yang ditolak saat checkout |
| Jatuh tempo | Baris tagihan H-3 sampai H+N, dikelompokkan per pelanggan |
| Janji bayar | Janji bertanggal dari tindak lanjut; yang lewat naik ke atas |
| Kaji ulang | Plafon yang mendekati atau melewati tanggal berlaku; pelanggan yang sering lewat plafon |
| Denda | Nota draf yang menunggu diterbitkan atau dibebaskan |

**Kartu pelanggan** (perluasan `Customer360Panel` yang sudah ada, bukan layar baru): eksposur beserta rinciannya,
profil kredit dan riwayatnya, jadwal tagihan, kwitansi, titipan dan saldo kredit, denda, kasus, tindak lanjut, dan
**rekening koran** (saldo awal, tagihan, pembayaran, nota kredit, denda, saldo akhir; bisa "per tanggal"; bisa dicetak
dan dikirim ke pelanggan).

Peran: kumpulan izin "pengendali kredit" untuk Finance (melihat semua, mengajukan perubahan, menerbitkan denda, mencatat
janji bayar); keputusan tetap di manajer/pemilik menurut jenjang (K-28).

## 4. Tahap bangun

| Tahap | Isi | Prasyarat | Selesai bila |
|---|---|---|---|
| CR-T1 Profil dan pengaturan | Profil kredit per pelanggan per PT; pengajuan perubahan ber-persetujuan; ambang dari Pusat Pengaturan; riwayat; izin pengendali kredit | PK-45 | Sales mengirim `credit_limit` lewat `PATCH` pelanggan → diabaikan; perubahan plafon tanpa pengajuan tidak mungkin; ambang PT-A ≠ PT-B berlaku |
| CR-T2 Jadwal tagihan dan saldo | Baris tagihan untuk semua pesanan non-tunai; saldo tersimpan + pembangun ulang + invarian; umur piutang, proyeksi kas, dan kendali kredit membaca dari jadwal | PK-19, PK-41 (RP-03), K-16 | Kasus uji RP-03 (pesan 100, kirim 40) → 40 jatuh tempo, 60 belum; saldo tersimpan = hitung ulang; Σ piutang terkirim = akun piutang |
| CR-T3 Gerbang | Satu mesin di empat titik periksa; status "Tahan kredit"; izin kredit berjenjang, bernominal, bermasa berlaku; catatan penolakan; termin diadu dengan profil; tunai ikut tahan-kirim | CR-T2, PK-38 (FX-16) | Menaikkan jumlah pesanan hingga lewat plafon → ditahan; izin kedaluwarsa tidak bisa dipakai; pengaju tidak bisa menyetujui sendiri; pesanan tunai pelanggan tertahan tidak bisa dikirim sebelum lunas |
| CR-T4 Denda | Aturan berlapis dengan layar di profil pelanggan; perhitungan dari jadwal tagihan; mode per PT; bebas denda per pelanggan | PK-08, CR-T2 | Tarif pelanggan menimpa tarif PT; pelanggan bebas denda tidak menerima nota; pembebasan nota setelah bayar sebagian → piutang denda 0 |
| CR-T5 Daftar kerja dan rekening koran | Tab Kredit & Plafon; janji bayar; rekening koran; pengingat ke pelanggan (naskah siap kirim; pengiriman otomatis menyusul) | CR-T2 | Rekening koran "per 31 Okt" yang dibuka November = saldo akun piutang pelanggan itu per 31 Okt |

CR-T1 bisa dimulai lebih awal karena tidak bergantung pada rumus umur piutang.

## 5. Catatan untuk hutang (supplier)

Pemilik meminta piutang yang "advanced"; untuk hutang cukup dicatat apa yang sepadan dan di paket mana:

| Kebutuhan | Keadaan | Rencana |
|---|---|---|
| Bayar lewat satu pintu yang aman | Empat jalur dengan form berbeda; SL-01 kritis | PK-05 |
| Saldo dan umur hutang per supplier | Daftar dipotong 2.000; "umur" dihitung dari jatuh tempo; tidak memuat landed cost dan nota debit (RP-01, RP-07) | PK-41; saldo tersimpan per supplier per PT dengan invarian yang sama seperti piutang |
| Jadwal bayar | Tidak ada; hanya jatuh tempo per faktur | Tab "Pembayaran" di pusat Hutang: daftar jatuh tempo, pilih banyak faktur → satu pembayaran per supplier (bayar massal) |
| Rekening supplier | Teks di master supplier | Rekening tujuan terdaftar; perubahan rekening lewat persetujuan (pengaman penipuan) — lihat `07` |
| Pemisahan setujui / bayar | Satu manajer bisa semuanya (IA-12) | PK-38 |
| Selisih harga dan GR/IR | Tanpa akun varians (IV-03) | PK-28 |
