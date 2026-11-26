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

Tangkapan: folder `2026-11-25-lapor-bayar-cbd-hasil/tangkapan/` (log di `tangkap_lb_log.txt`). ⟨TANGKAPAN⟩

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

Alur tiap tugas: pelaksana → tinjauan tugas (spesifikasi + mutu) → putaran perbaikan bila perlu. Sesudah semua tugas,
tinjauan seluruh cabang (`4e98a42..HEAD`) menemukan 0 Critical, 4 Important, 5 Minor. Semuanya diperbaiki di
`227042a` + `8e2828c`:
- kredit pengganti retur CBD tertolak diam-diam;
- laporan "sedang diproses" yang macet tidak bisa diulang dari layar;
- putusan pada pesanan yang sudah lewat batas bisa langsung gugur;
- uji hidup dan materi latihan masih memakai alur lama.

Pelaksana perbaikan menemukan satu regresi baru: bayar DP tepat 50% memunculkan "kurang bayar". Regresi itu
diperbaiki sebelum gabung (`6a2facf`). Tinjauan ulang: semua butir tertangani, tanpa Critical/Important baru.

## 3. Uji (apa adanya)

- **Backend `tests_mem` penuh** di `6a2facf`: **3011 passed**, 2 skipped, 3 xfailed, **0 failed** (gelombang 2: 2850).
- **Jest penuh** di `6a2facf`: **2107/2108** lulus, **268/270** suite (gelombang 2: 2050/2051, 264/266). Yang gagal
  `odItemCancel` dan `phase4R2`, kendala lingkungan wadah yang sama dengan garis dasar.
- **Uji hidup ber-Mongo** (`tests/test_f10_cbd_dp_dispatch_gate.py`, `test_uat_v3_ui_gaps.py`): 9 lulus, dijalankan di
  salinan DB lewat server terpisah (gelombang perbaikan akhir).
- **MongoDB sungguhan** (bukan tiruan), salinan DB: ⟨MONGO⟩

### 3a. Gate

⟨GATE⟩

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
- **Label status Indonesia** "Sebagian dikirim" (`partially_shipped`) dan "Sebagian disiapkan" (`partially_picked`) dirapikan (R3, sisa gelombang 2).

## 5. Untuk pemilik

1. **Pesanan di VPS yang akan ikut tertahan.**
   - Pesanan CBD/DP/K-27 yang sudah ada dan belum dilepas ke gudang ikut tertahan pada percobaan konfirmasi atau
     keputusan ACC berikutnya. Batas bayarnya dihitung baru dari saat itu.
   - Sejak hari pembaruan, sales tidak bisa lagi mencatat kwitansi transfer atau memakai titipan untuk pesanan itu.
     Sales memakai **Lapor bayar**.
   - Kueri hitung (hanya-baca) ada di pesan serah-terima. Di data acuan hasilnya 0.
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

## 7. Catatan pembaruan VPS

- Indeks baru dibuat otomatis saat backend menyala (`ensure_required_indexes`), termasuk `uq_payment_report` pada
  `ar_receipts` (unik parsial: `payment_report_id` ada dan `status = posted`) dan indeks `payment_reports`.
- DB yang pernah menjalankan `fc05b47` perlu satu kali membuang indeks `uq_payment_report` versi lama (bentuk parsialnya
  berubah). VPS produksi tidak pernah menjalankan `fc05b47`, jadi langkah ini tidak berlaku di sana.
- Bukti bayar disimpan lewat `storage_service` di jalur `payment_reports/` (lokal: `backend/uploads/kn7/payment_reports/`,
  diabaikan git).
- Pengaturan baru memakai bawaan registri. Tidak ada isian yang perlu diubah di Pusat Pengaturan.
