# Hasil — Lapor Bayar CBD & DP (tahan sebelum gudang)

Tanggal: 26 Nov 2026 · Cabang: `claude/nifty-carson-jjx3c8` · Garis dasar: `4e98a42` (meja gelombang 1+2, sudah di
`main`) · Pohon kode akhir: `6a2facf`.

- **Rancangan:** `docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` (keputusan pemilik B1–B7).
- **Rencana:** `docs/superpowers/plans/2026-11-25-lapor-bayar-cbd.md`, 9 tugas.

**Status: selesai, belum digabung ke `main`.** Penggabungan ke `main` menunggu izin pemilik.

## 1. Yang berubah untuk pengguna

| Keadaan dulu | Sekarang |
|---|---|
| Pesanan CBD dan bagian DP pesanan DP bisa dilepas ke gudang tanpa uang; gerbang bayar baru ada di surat jalan, jadi gudang sudah mengambil barang. | Pesanan yang wajib bayar dulu **berhenti di tahap "Bayar dicek Finance"**, di antara "Disetujui" dan "Dilepas ke gudang". Belum ada tugas gudang. Tahap ini tampil di rincian pesanan, Perjalanan, Pelacak SO, Meja Keuangan, Meja Admin Sales, dan HP sales. |
| Sales mencatat kwitansi transfer sendiri; kas dan jurnal langsung terbit sebelum bukti dicek. | Sales menekan **"Lapor bayar"** di rincian pesanan: nominal, tanggal, rekening tujuan, nomor referensi, dan **foto/PDF bukti** (wajib). Laporan masuk antrean **"Lapor bayar menunggu dicek"** di Meja Keuangan. |
| — | Finance membuka pop-up laporan (bukti + rincian pesanan) lalu **Terima** atau **Tolak (dengan alasan)** di tempat. **Terima** menerbitkan kwitansi, kas, dan jurnal lewat jalur kwitansi yang sama dengan Uang Masuk; bila bagian wajib sudah lunas, pesanan **lepas sendiri ke gudang** (Admin Sales tidak perlu menekan lagi). **Tolak** memberi tahu sales beserta alasannya; sales boleh lapor ulang. |
| Pelanggan CBD baru bisa menerima Faktur Komersial berkode bayar sesudah pesanan dikonfirmasi. | **Kode bayar dan Faktur Komersial tersedia sejak pesanan disetujui** bila pesanan wajib bayar dulu. Cetakannya berstatus **"Belum dibayar"** sampai bagian wajib lunas. |
| Pesanan yang sudah disetujui tidak pernah kedaluwarsa; stoknya bisa terkunci tanpa batas. | **Batas bayar** per PT (pengaturan `sales.batas_bayar_hari`, bawaan **3 hari**). Pengingat H-1 ke sales dan Admin Sales (`pay_due_soon`). Lewat batas tanpa laporan menunggu → pesanan gugur, stok dilepas, uang muka yang sudah masuk menjadi titipan pelanggan. **Laporan yang masih menunggu dicek tidak membuat pesanan gugur**; Finance diberi tahu. Sesudah Finance memutus laporan pada pesanan yang sudah lewat batas, batasnya diperpanjang (pengaturan `sales.tenggang_sesudah_putusan_jam`, bawaan **24 jam**). |
| Bayar DP tepat 50% pada pesanan DP50 dicatat sebelum gudang memunculkan "kurang bayar". | Bayar tepat sebesar bagian wajib (DP/CBD) **tidak** dianggap kurang bayar. Bayar kurang dari bagian wajib tetap memunculkan keputusan selisih seperti biasa. |

**Wewenang (izin baru `payment_report`, bukan nama peran):**
- `create` (Lapor bayar): bawaan sales, sales_admin, finance, admin, manager.
- `decide` (Terima/Tolak): bawaan finance, admin, manager.

**Yang tidak berubah:**
- Gerbang surat jalan tetap sebagai pagar kedua, dengan hitungan yang sama.
- "Kirim tanpa lunas" (B6) oleh Finance/Manager/Admin tetap ada. Kini ia juga membuka tahan gudang.
- Pesanan non-CBD/DP dan pesanan sample tidak terkena.
- Pesanan Khusus (OD) tidak ditahan di gudang dan tetap dijaga gerbang surat jalan.

Tangkapan: folder `2026-11-25-lapor-bayar-cbd-hasil/tangkapan/` (log di `tangkap_lb_log.txt`). Dibuat di data acuan lokal
(bukan data nyata): `siapkan_lb.py` membuat pesanan CBD dan DP50 lewat API lalu Admin Sales "Periksa & lepas";
`tangkap_lb.js` menjalankan alurnya di layar.
- `01`–`03`: sales desktop — pesanan CBD berhenti di "Bayar dicek Finance" (daftar, rincian, panel tahap bayar
  dengan batas bayar "sisa 3 hari", Perjalanan).
- `04`–`05`: dialog Lapor bayar (nominal = kekurangan, rekening instruksi pesanan, bukti) → laporan "Menunggu dicek".
- `06`–`07`: HP sales — pesanan DP50 (wajib Rp 173.438 = 50%) dan dialog Lapor bayar di HP.
- `08`–`11`: Meja Keuangan — pop-up laporan (bukti + rincian pesanan) → Terima → konfirmasi "Kwitansi Rp 1.318.125 ke
  rekening BCA Operasional KSC akan diterbitkan…" → kwitansi KSC/AR-00003 terbit, **pesanan langsung `confirmed`**
  (tahan dibuka, lunas, tugas gudang lahir).
- `12`–`14`: Tolak dengan alasan → notifikasi sales "Lapor bayar ditolak" beserta alasannya (dan "Lapor bayar diterima"
  untuk CBD).
- `15`–`16`: Perjalanan CBD sesudah Terima: "Dikonfirmasi (otomatis sesudah kwitansi KSC/AR-00003)", tahap kini
  "Disiapkan gudang".
- `17`: Pelacak SO Admin Sales — DP50 "Menunggu bayar — Finance".
- `18`: Faktur Komersial DP50 yang masih tertahan: cap dan status **"Belum dibayar"**.

## 2. Tugas → commit

| Tugas | Commit |
|---|---|
| T1 Fondasi: izin, pengaturan batas bayar, koleksi laporan | `5752fba`, `ab9ba42` |
| T2 Tahan sebelum gudang + kode bayar sejak disetujui | `86d95a7`, `e2cf884` |
| T3 API lapor bayar + lampiran | `55812ae`, `76cbe03` |
| T4 Terima/Tolak + pagar kwitansi transfer (B3) | `5c1c406`, `fc05b47`, `f923dc2` |
| T5 Batas bayar + pengingat | `967cbec`, `82c6bbf` |
| T6 Server layar: Perjalanan, pelacak, meja | `50081a0`, `c1d80ad` |
| T7 Rincian pesanan: lapor, bukti, terima/tolak, invoice sejak disetujui | `446038e` |
| T8 Meja Keuangan, Admin Sales, HP, notifikasi | `b808c2b`, `8c78473` |
| T9a Pola UI `04_POLA_UI.md` §2.E, peta kode, catatan materi pelatihan | `b5f0537` |
| Perbaikan tinjauan akhir | `227042a`, `8e2828c`, `6a2facf` |
| T9b Temuan tangkapan (R21) | `56306b6` |
| T9b Skrip tangkapan, cek MongoDB, laporan | `648bd66`, `4f23df2` + commit laporan akhir |

Alur tiap tugas: pelaksana → tinjauan tugas (spesifikasi + mutu) → putaran perbaikan bila perlu. Sesudah semua tugas,
tinjauan seluruh cabang (`4e98a42..HEAD`) menemukan 0 Critical, 4 Important, 5 Minor. Semuanya diperbaiki di
`227042a` + `8e2828c`:
- kredit pengganti retur CBD tertolak diam-diam;
- laporan "sedang diproses" yang macet tidak bisa diulang dari layar;
- putusan pada pesanan yang sudah lewat batas bisa langsung gugur;
- uji hidup dan materi latihan masih memakai alur lama.

Pelaksana perbaikan menemukan satu regresi baru: bayar DP tepat 50% memunculkan "kurang bayar". Regresi itu
diperbaiki sebelum gabung (`6a2facf`). Tinjauan ulang: semua butir tertangani, tanpa Critical/Important baru.

Tangkapan layar (T9b) menemukan tiga galat tampilan kecil, diperbaiki dengan uji di `56306b6` (R21):
- baris lapor bayar di Meja Keuangan berlencana **"Menunggu manajer"** (kata milik antrean ACC harga) → kini
  "Menunggu dicek";
- petunjuk panel tertahan menyuruh "Catat pembayaran di Uang Masuk" (yang ditolak server untuk sales) → sebelum gudang
  kini menunjuk Lapor bayar; teks lama tetap untuk gerbang surat jalan;
- Perjalanan "Ditagih" berbunyi "terbit saat barang dikirim" padahal faktur sudah tersedia sejak disetujui → "sudah
  bisa dicetak (bayar sebelum gudang)".

## 3. Uji (apa adanya)

- **Backend `tests_mem` penuh** di `6a2facf`: **3011 passed**, 2 skipped, 3 xfailed, **0 failed** (gelombang 2: 2850).
- **Jest penuh** di `6a2facf`: **2107/2108** lulus, **268/270** suite (gelombang 2: 2050/2051, 264/266). Yang gagal
  `odItemCancel` dan `phase4R2`, kendala lingkungan wadah yang sama dengan garis dasar.
- **Uji hidup ber-Mongo** (`tests/test_f10_cbd_dp_dispatch_gate.py`, `test_uat_v3_ui_gaps.py`): 9 lulus, dijalankan di
  salinan DB lewat server terpisah (gelombang perbaikan akhir).
- **MongoDB sungguhan** (mongo 7, bukan tiruan), salinan DB `lb9_test` lalu dibuang (`cek_mongo_nyata.py`, log
  `cek_mongo_nyata_log.txt`):
  - indeks wajib: 0 selisih; `uq_payment_report` unik parsial (`payment_report_id` ada, `status = posted`). Uji mongosh:
    kwitansi posted ganda untuk satu laporan ditolak (11000); sesudah kwitansi dibatalkan boleh terbit lagi;
  - penyapu batas bayar: DP50 yang lewat batas → `expired`, cadangan roll dilepas; CBD yang belum lewat tetap;
  - klaim berprasyarat `pay_hold.due_at` (bertitik) dengan nilai basi ditolak 409;
  - pengingat H-1: 6 notifikasi untuk DP50 (batas 2 jam lagi), termasuk sales pemilik; 0 untuk CBD (batas 5 hari lagi).
- **Sesudah R21** (perbaikan tampilan dari tangkapan, `56306b6`): uji terarah LB3–LB6 + semua uji Perjalanan
  (136 lulus), jest 11 suite terkait (129 lulus). Suite penuh dan gate `--quick` diulang pada pohon akhir
  (`56306b6`):
  - `tests_mem`: **3012 passed**, 2 skipped, 3 xfailed, **0 failed**;
  - jest: 2108/2110, 267/270 suite. Gagal: `odItemCancel`, `phase4R2` (lingkungan, sama dengan garis dasar) dan
    `tzTanggalBawaan` — uji ini mensyaratkan proses ber-zona UTC; dijalankan sendiri lulus 3/3 (juga dengan `TZ=UTC`),
    dan lulus di jalankan penuh pertama. Kerapuhan urutan/lingkungan uji, tidak terkait berkas R21;
  - gate `--quick`: 10 FAIL (garis dasar 16), 0 lebih merah, tidak ada pelanggaran baru.

### 3a. Gate

Dijalankan sekali di `6a2facf`, dinilai dengan kedua pembanding.

| Mode | FAIL (garis dasar) | Lebih merah | Menjadi hijau | Pelanggaran baru |
|---|---|---|---|---|
| `--quick` | 10 (16) | 0 | 4 | 0 |
| `--ci` | 36 (43) | 2 | 7 | 1 (lihat bawah) |

- Dua yang lebih merah di `--ci` (`POC Cek Kenyataan Peran`, `POC FASE N`) adalah POC bawaan yang sudah FAIL sejak
  gate 23 Nov; pembanding terhadap gate akhir gelombang 2 tidak memasukkan keduanya sebagai pelanggaran baru.
- Satu pelanggaran baru di `--ci`: POC FASE E-7 "nol residu di SELURUH basis data" — `sys_scheduler_runs 10→11 (+1)`.
  Itu satu catatan putaran penjadwal backend yang kebetulan jatuh di jendela POC 4 detik (cabang ini hanya mengubah
  teks deskripsi job, tidak menambah job). E-7 dijalankan ulang dua kali tersendiri: residu PASS, 7 FAIL = garis
  dasar. **Bukan regresi.**

## 4. Keputusan pelaksanaan (di luar rancangan — periksa)

Dicatat sebagai ketetapan R1–R20 di buku catatan kerja. Yang mengubah perilaku:

- **Lepas otomatis hanya bila Admin Sales sudah "Periksa & lepas"** (R4).
  - Pesanan CBD yang dibayar sebelum diperiksa Admin Sales hanya kehilangan tahannya, lalu menunggu Admin Sales seperti
    biasa. Verifikasi Admin Sales tidak dilompati.
- **Kwitansi Finance langsung juga membuka tahan** (R5). Bukan hanya Terima laporan.
- **Pesanan Khusus (OD) tidak ditahan sebelum gudang** (R6). OD sedang diproduksi, jadi tidak boleh digugurkan
  penyapu. OD tetap dijaga gerbang surat jalan seperti dulu.
- **Terima butuh minimal satu bukti** (R9). Klaim "sedang diproses" atomik; klaim yang macet lebih dari 10 menit boleh
  diambil alih.
- **Aturan isian uang masuk disatukan untuk laporan dan kwitansi** (R10).
  - Nomor referensi wajib bila PT memintanya.
  - Rekening tujuan ≠ rekening instruksi pesanan → pelapor wajib menulis alasan.
  - Giro/cek tidak bisa dilaporkan lewat Lapor bayar.
  - Laporan yang melebihi sisa wajib/sisa tagihan ditolak saat dibuat. Kelebihan nyata dicatat lewat kwitansi manual dan
    keputusan selisih.
  - Satu kwitansi per laporan dijamin indeks unik basis data.
- **Pagar pesanan tertahan diperketat** (R11, R12, R13).
  - Pengguna tanpa izin `payment_report.decide` tidak bisa mengalokasikan uang non-tunai maupun titipan ke pesanan yang
    wajib bayar dulu dan belum ke gudang, termasuk sebelum disetujui dan saat menunggu stok.
  - Satu-satunya pengecualian: uang **tunai** baru, mengikuti pengaturan `pembayaran.sales_terima_tunai`.
  - Akibatnya: sales tidak bisa memakai titipan pelanggan untuk pesanan tertahan; Finance yang melakukannya.
- **Kredit pengganti retur** untuk pesanan CBD dikecualikan dari pagar itu (R18-a).
- **Tenggang sesudah putusan** jadi pengaturan baru `sales.tenggang_sesudah_putusan_jam` (bawaan 24 jam, R18-c). Ia
  juga memperpanjang masa cadangan pesanan yang belum disetujui.
- **Bayar tepat bagian wajib bukan "kurang bayar"** (R19). Penilaian selisih untuk pesanan tertahan mengharapkan sisa
  wajib sebelum gudang, bukan seluruh pesanan. Bawaan nominal form kwitansi mengikutinya.
- **Teks dan lencana dari tangkapan** (R21): lihat §2. Hanya teks/label; tidak ada logika uang yang berubah.
- **Label status Indonesia** "Sebagian dikirim" (`partially_shipped`) dan "Sebagian disiapkan" (`partially_picked`) dirapikan (R3, sisa gelombang 2).

## 5. Untuk pemilik

1. **Pesanan di VPS yang akan ikut tertahan.**
   - Pesanan CBD/DP/K-27 yang sudah ada dan belum dilepas ke gudang ikut tertahan pada percobaan konfirmasi atau
     keputusan ACC berikutnya. Batas bayarnya dihitung baru dari saat itu.
   - Sejak hari pembaruan, sales tidak bisa lagi mencatat kwitansi transfer atau memakai titipan untuk pesanan itu.
     Sales memakai **Lapor bayar**.
   - Kueri hitung (hanya-baca): `2026-11-25-lapor-bayar-cbd-hasil/hitung_vps.js`. Di data acuan hasilnya 0.
2. **Kelebihan bayar.** Perlukah tombol "Terima + kelebihan jadi titipan" di laporan? Sekarang laporan yang melebihi
   sisa wajib ditolak saat dibuat, dan kelebihan dicatat lewat kwitansi manual + keputusan selisih (R10-b).
3. **Kasus sempit yang ditunda (R7).** Pesanan NET30 + bayar penuh sebelum kirim (K-27) yang dilepas tanpa bayar (B6)
   lalu dikirim bisa menampilkan dua instruksi bayar untuk satu pesanan. Kasus ini jarang. Penyelesaiannya butuh aturan
   status kode bayar (PM-T3).
4. **Empat mata.** Finance memegang `create` dan `decide` sekaligus, jadi satu orang bisa melapor lalu menerima
   laporannya sendiri. Rancangan tidak melarangnya. Perlukah dilarang?
5. **Kamera HP.** Tombol bukti di HP membuka kamera belakang langsung (`capture`). Perlu dicoba di HP sungguhan.
6. **Izin `sales_force.assign`** untuk Admin Sales (pertanyaan gelombang 2) masih menunggu jawaban.

## 6. Catatan kecil yang ditunda (tidak memblokir, R20)

- Tolak yang mengambil alih klaim macet dari pekerja yang ternyata masih hidup lebih dari 10 menit bisa meninggalkan
  laporan ditolak dengan kwitansi terposting. Jendelanya sempit dan terlihat di jejak.
- Penyapu yang sedang berjalan di antara tulis putusan dan perpanjangan batas masih bisa menggugurkan pesanan.
- Teks bantuan hapus sisa "pesanan langsung lunas" tidak tepat untuk pesanan tertahan; tombol jadwal ulang tersembunyi
  untuk pesanan tertahan.
- Beberapa layar memuat dokumen pesanan dan menghitung gerbang dua kali (biaya, bukan galat).
- Kartu "Sebelum masuk gudang" di HP (dan rincian) masih berlencana "Sudah diperiksa · siap dilepas" untuk pesanan yang
  sedang menunggu bayar; tahap bayar tampil benar tepat di bawahnya. Perlu satu baris teks "menunggu bayar".
- Faktur Komersial pesanan DP50 menampilkan total pesanan dan sisa tagihan penuh; bagian DP yang wajib dibayar dulu
  tampil di instruksi bayar dan panel tahap bayar, bukan di faktur.

## 6a. Catatan lingkungan uji lokal (bukan VPS)

- Sesudah gate, master **Cara Bayar** (`payment_methods`) di DB lokal kosong, sehingga daftar "Cara bayar" di dialog
  Lapor bayar sempat kosong ("Belum ada pilihan"). Backend mengisinya lagi setiap menyala (`ensure_seed`), dan
  tidak ada kode aplikasi yang menghapusnya; penyebab di rangkaian gate lokal belum ditelusuri. Di VPS master ini
  terisi sejak backend menyala, jadi tidak berdampak. Layar Lapor bayar menampilkan daftar kosong apa adanya (tidak
  memakai cadangan) — sesuai aturan "daftar induk satu sumber".
- Data acuan sesudah gate berbeda dari data acuan murni (akun `sales2`/`sales3`, pelanggan acuan tertahan kredit).
  Tangkapan akhir dibuat di data acuan murni (`restore_local_demo.sh --seed-only`), lalu DB dipulihkan lagi.

## 7. Catatan pembaruan VPS

- Indeks baru dibuat otomatis saat backend menyala (`ensure_required_indexes`), termasuk `uq_payment_report` pada
  `ar_receipts` (unik parsial: `payment_report_id` ada dan `status = posted`) dan indeks `payment_reports`.
- DB yang pernah menjalankan `fc05b47` perlu satu kali membuang indeks `uq_payment_report` versi lama (bentuk parsialnya
  berubah). VPS produksi tidak pernah menjalankan `fc05b47`, jadi langkah ini tidak berlaku di sana.
- Bukti bayar disimpan lewat `storage_service` di jalur `payment_reports/` (lokal: `backend/uploads/kn7/payment_reports/`,
  diabaikan git).
- Pengaturan baru memakai bawaan registri. Tidak ada isian yang perlu diubah di Pusat Pengaturan.
