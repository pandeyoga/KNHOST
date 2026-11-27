# Hasil — Kas & Bank bagian 1: akun buku besar per rekening, Pindah Dana, pindah saldo

Tanggal: 27 Nov 2026 · Cabang: `claude/nifty-carson-jjx3c8` · Garis dasar: `b41e21f` (F1, menunggu izin gabung) ·
Pohon kode akhir: `ed51714`.

- **Rancangan:** `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` (keputusan pemilik D1–D4;
  builder check §7–8).
- **Rencana:** `docs/superpowers/plans/2026-11-27-kas-bank-1-rekening-pindah-dana.md`, 7 tugas.
- **Tangkapan layar (F1 + Kas & Bank 1, data acuan):** `2026-11-27-kas-bank-1-hasil/tangkapan/` — 33 potret PT KSC (F1: impor mutasi → kwitansi otomatis + kartu Meja Keuangan + pesanan CBD lepas; Kas & Bank: penanda → pratinjau → siapkan → setujui orang kedua + "Angka berubah" → sesudah aktif; Pindah Dana dua tahap, kontrol dua orang, pratinjau PDN, batal; kas manual tanpa Transfer/Top-up). Skrip `tangkap_kb1.js` + `siapkan_kb1.py`, log angka API `tangkap_kb1_log.txt`: di setiap langkah saldo sub-akun tiap rekening = buku kas rekening itu; akun lama 1-1100/1-1110 jadi Rp 0 untuk bagian yang dipindah.

**Status: selesai, belum digabung ke `main`.** Pembaruan VPS **tidak menulis data nyata**: tidak ada akun, rekening, atau
jurnal yang dibuat/diubah saat backend menyala. Setiap PT tetap memakai akun lama (1-1100 / 1-1110) **sampai Finance
menjalankan pindah saldo untuk PT itu dan orang kedua menyetujuinya.**

## 1. Yang berubah untuk pengguna

| Keadaan dulu | Sekarang |
|---|---|
| Semua rekening bank satu PT berbagi satu akun buku besar 1-1100 (kas kecil 1-1110); saldo per rekening tidak ada di buku besar. | Setiap rekening punya **sub-akun sendiri** (`1-1100-01`, `1-1100-02`, kas kecil `1-1110-01` …, atau akun bagan PT yang dipilih Finance) — **sesudah PT itu dinyalakan lewat pindah saldo**. Kartu rekening di Rekening & Saldo menampilkan "Akun buku besar …"; PT yang belum dinyalakan diberi penanda "PT belum memakai akun per rekening". |
| Tidak ada alat untuk memindah saldo lama. | **Kas & Bank › Akun per rekening** (pemegang izin Akuntansi kelola): pratinjau per rekening — saldo buku kas, dari akun mana saldo dipindah, jurnal yang akan dibuat, kas lama tanpa rekening. **Siapkan** (satu orang) → **Setujui** (orang kedua; Admin pun tidak boleh menyetujui usulannya sendiri). Saat disetujui angka **dihitung ulang**; bila berubah sejak dilihat → "Angka berubah, muat ulang". Jurnal pindah saldo bertanggal hari persetujuan. Ditolak selama ada posting kas gagal/tertunda atau gaji jalur lama yang belum berkas kasnya (daftarnya tampil di layar). Rekening yang berselisih dengan buku kasnya wajib dicentang "sudah diperiksa". |
| Pindah dana antar rekening = dua kas manual lepas berkategori "Transfer/Top-up"; satu sisi bisa lupa; biaya transfer tidak tercatat. | **Kas & Bank › Pindah Dana**: satu form (rekening asal & tujuan satu PT, nominal, biaya transfer, tanggal kirim/terima) → nomor `PDN-…`, kas keluar dan masuk berpasangan + biaya, satu pembatalan. Tanggal terima lebih lambat → "Dalam perjalanan" (akun transit 1-1150) lalu **Terima**. Kontrol dua orang per PT di Pusat Pengaturan (bawaan satu orang). Nomor PDN bisa diklik (pratinjau + jejak). Belum diterima pada tutup buku → butir "Dana dalam perjalanan". |
| Kas manual bisa berkategori Transfer/Top-up. | Kategori itu **ditutup untuk kas manual baru** (layar dan server, juga kartu Asisten): "Pakai Pindah Dana untuk setor tunai, isi kas kecil, dan pindah antar rekening." Kas lama berkategori itu tetap bisa dibatalkan/diposting ulang. |
| Semua jurnal kas menulis 1-1100/1-1110 sendiri-sendiri. | **Satu pembantu akun kas** untuk semua jurnal kas (kas, kwitansi, antar-PT, gaji jalur lama, refund retur, aset, Pindah Dana) + **penjaga** di gate yang menolak kode kas tertulis langsung. Di PT yang belum dinyalakan semua jurnal **persis seperti dulu** (diuji per jalur terhadap rekaman jurnal kode lama). |

**Pengaman:**
- Jurnal manual ke sub-akun rekening ditolak; pembalikan manual jurnal kas rekening & saldo awal rekening ditolak
  (dibalik lewat batal dokumen kas / ubah saldo awal) — supaya saldo sub-akun selalu = buku kas rekening.
- Batal kas lama sesudah PT dinyalakan → pembaliknya ke sub-akun rekening (saldonya sudah dipindah ke sana).
- Jalur tanpa dokumen kas (penjualan tunai tanpa surat jalan, hasil jual aset, ongkir retur dari akun kas lama) di PT yang
  sudah dinyalakan tetap ke akun lama dengan tanda "belum tertaut" (R6/R7).
- Akun rekening tidak bisa dihapus/dinonaktifkan/dibuat tidak-postable; akun tujuan pemetaan kas tidak boleh dipilih
  menjadi akun rekening.
- Persetujuan pindah saldo dan Pindah Dana tampil di Pusat Persetujuan.

## 2. Tugas → commit

| Tugas | Commit |
|---|---|
| T1 Pembantu akun kas, mode per PT, sub-akun rekening | `663d0b2`, `2607943` |
| T2 Semua jurnal kas lewat satu pembantu + pembalik kas lama + penjaga | `cda89c9`, `53521d3` |
| T3 Alat pindah saldo per PT | `6eefaf8`, `a81f65f`, `e345cea` |
| T4 Pindah Dana (server) | `e2020bc`, `479d0af` |
| T5 Tutup kategori Transfer/Top-up | `0be3d11` |
| T6 Layar | `1cb2b63` |
| Gelombang perbaikan akhir | `223e73a`, `b370cc1` |
| Temuan tangkapan layar (alasan tombol terpotong, tanggal mentah) | `ed51714` |

Alur: T1–T5 (jalur uang) pelaksana → tinjauan tugas → perbaikan → tinjauan ulang; T6 (layar) tanpa tinjauan tugas
(perintah pemilik "ya percepat"); tinjauan seluruh cabang → satu gelombang perbaikan → tinjauan ulang: semua temuan (2 Important + 8 kecil) tertangani, tanpa temuan berat baru.

Temuan nyata yang tertangkap tinjauan sebelum gabung:
- akun tujuan pemetaan kas bisa dipilih jadi akun rekening (jurnal kas lama ikut masuk ke rekening) — T1;
- ringkasan konsolidasi masih membaca kas dari dua akun lama saja — T1;
- pembalikan manual jurnal kas rekening tidak ditolak — T1;
- kas yang dibatalkan persis saat PT dinyalakan tidak ikut dipindah (sub-akun ≠ buku kas) — T3, dibuktikan uji;
- Batal Pindah Dana yang bersamaan dengan Terima/Setujui meninggalkan kas tujuan hidup ("uang tercipta") — T4, dibuktikan uji;
- layar Akun per rekening menampilkan selisih palsu sesudah PT dinyalakan; Tolak meninggalkan akun pilihan bertanda
  rekening — tinjauan akhir.

## 3. Uji (apa adanya)

- **Backend `tests_mem` penuh** di `b370cc1`: 3236 lulus, 2 dilewati, 3 xfail, **0 gagal** (EXIT 0, 1228 dtk).
- **Jest penuh** di `b370cc1`: 2173/2174 uji, 270/272 suite — `odItemCancel`, `phase4R2` (kendala lingkungan, sama dengan garis dasar). `ed51714` (layar saja): uji jest terkait 18 suite lulus (64 + 230 uji).
- **Uji baru:** `test_KB1_1`…`test_KB1_6` (backend) + `kb1KasBank.test.js` (jest). Setiap jalur uang diuji di PT belum
  aktif (rekaman jurnal kode lama) dan PT aktif (sub-akun).
- **MongoDB sungguhan** (`backend/tests/test_bp_KB1_bersamaan.py`, salinan data acuan + backend terpisah :8031, salinan dibuang): (1) Terima × Batal Pindah Dana bersamaan, 5 dokumen — tiap dokumen utuh selesai **atau** utuh batal, 1-1150 bersih nol, tidak pernah campuran; (2) dua Setujui Pindah Dana bersamaan → satu set kas; (3) dua Setujui pindah saldo bersamaan → satu jurnal pindah saldo, mode menyala sekali, sub-akun tiap rekening = buku kasnya. 3/3 lulus.
- **Waktu pratinjau** pindah saldo: ±0,03 dtk pada data ukuran demo, ±1,0 dtk pada 10× (database tiruan tanpa indeks;
  MongoDB asli memakai dua indeks baru `cash_transactions.journal_entry_id` / `parent_journal`).

### 3a. Gate

| Mode | FAIL (garis dasar) | Lebih merah | Pelanggaran baru (per pelanggaran) |
|---|---|---|---|
| `--ci` (`1cb2b63`) | 36 (43) | 2 POC bawaan (sama dengan F1 & Lapor Bayar) | **0** |
| `--quick` (pohon akhir `ed51714`, data acuan) | 10 (16) | 0 | **0** |

## 4. Keputusan pelaksanaan (periksa)

Keputusan builder rancangan §7, ditambah ketetapan pengendali selama eksekusi:

1. **R1** Semua kode kas 1-1100/1-1110 yang tertulis langsung di baris jurnal diganti pembantu (bukan hanya daftar builder check); pengecualian penjaga eksplisit beralasan.
2. **R2** Jenis kas diturunkan dari dokumen kas/rekening, bukan dari kode akun.
3. **R3** Pembalikan manual jurnal yang menyentuh akun rekening ditolak; batal lewat dokumen kas.
4. **R4** Jurnal yang PT bukunya berbeda dengan PT rekening tetap ke akun lama (jarang).
5. **R5** Pemilih akun refund tetap daftar akun templat; refund ke rekening memakai sub-akun lewat pembantu. *Kalimat rancangan §5.1 "kumpulan akun kas dinamis" untuk pemilih refund dikoreksi.*
6. **R6** Penjualan tunai tanpa surat jalan (dan hasil jual aset) di PT aktif → akun lama + "belum tertaut", **bukan** sub-akun rekening tunggal: anti-tujuan "saldo per rekening = buku kas rekening" lebih kuat. *Kalimat rancangan §5.1 dikoreksi.* Akibat: hasil penjualan tunai tanpa SJ menumpuk di akun lama sampai paket C1 (kas kasir) memberinya dokumen kas.
7. **R7** Ongkir retur dari akun kas lama di PT aktif juga bertanda "belum tertaut".
8. **R8** Pindah saldo ditolak selama ada gaji jalur lama tanpa dokumen kas; pratinjau memindah persis baris yang nanti dialihkan pembalik.
9. **R9** Admin tidak boleh menyetujui pindah saldo yang ia siapkan sendiri (bawaan `kontrol.admin_tetap_dua_orang`, tetap pengaturan).
10. **R10** Selisih rekening ≠ 0 tidak menghalangi, tetapi wajib dicentang "sudah diperiksa".
11. **R11** Jurnal saldo awal rekening tidak bisa dibalik manual di PT aktif.
12. **R12** Tugas kecil T5 dijalankan sejajar dengan tinjauan T4 (tetap satu pelaksana aktif).
13. **R13** Kategori kas manual apa pun yang memuat "transfer" ditolak — hari ini kategori seperti itu sudah dijurnal ke akun transit (salah).
14. **R14** Satu butir kecil tinjauan akhir diparkir: daftar usulan pindah saldo lintas PT di mode "Semua PT".
15. **R15** Pindah Dana sekali jalan menjurnal kedua kakinya lewat akun transit 1-1150 (keluar asal → 1-1150, 1-1150 → masuk tujuan); efek bersih = Dr tujuan / Cr asal dan 1-1150 nol per dokumen. *Kalimat rancangan §5.2 "Dr tujuan / Cr asal" dibaca sebagai efek bersih.*
16. **R16** Dua temuan layar dari tangkapan (alasan tombol mati terpotong di layar 1440 px; tanggal mentah di pop-up kartu Meja dan riwayat pratinjau PDN) diperbaiki sebelum tangkapan akhir.
- Diterima apa adanya: Admin boleh menyetujui Pindah Dana sendiri bila kontrol dua orang dinyalakan (perilaku kontrol
  baku; pindah dana rutin, berbeda dengan pindah saldo); batas nominal kontrol = nominal pindah tanpa biaya; nominal
  negatif ditolak skema (422).

## 5. Untuk pemilik

1. **Kapan tiap PT pindah ke akun per rekening?** Disarankan awal bulan, sesudah rekonsiliasi bulan lalu bersih, saat kas
   sepi (jendela balapan beberapa milidetik saat menyala). Menjalankan pindah saldo di PT nyata adalah tindakan Finance di
   layar — **sesudah Bapak setuju** (data nyata = STOP & ASK).
2. **Pola kode sub-akun `1-1100-01`** — setuju, atau ada penomoran akuntan sendiri? Finance bisa memilih akun bagan PT yang
   sudah ada untuk suatu rekening sebelum menyiapkan pindah saldo.
3. **Peran kustom** yang punya Akuntansi tetapi tidak punya Kas & Bank mungkin tidak sampai ke tab Akun per rekening (tab
   tersembunyi, dibuka dari Rekening & Saldo / antrean / Posting Gagal).
4. Kas manual tidak punya kategori biaya bank: biaya transfer dicatat di kolom biaya Pindah Dana atau Rekonsiliasi ›
   Catat biaya bank.
5. Pertanyaan terbuka sebelumnya masih menunggu: H5, C4, izin "tetapkan sales" Admin Sales, tombol kelebihan jadi
   titipan, larangan melapor-dan-menerima sendiri.

## 6. Catatan kecil yang ditunda (tidak memblokir)

Dari tinjauan per tugas dan tinjauan akhir; semua dinilai **boleh tetap** oleh tinjauan akhir:
- Balapan nomor sub-akun bila dua rekening baru dibuat bersamaan di PT aktif (jendela sangat sempit) — usul indeks unik
  `(PT, kode)` untuk akun khusus PT sesudah cek data VPS.
- Label baris sub-akun di laporan multi-PT bisa memakai nama rekening PT lain (total benar).
- Penjaga statis kode kas: pengecualian per lokasi tanpa hitungan; kunci pemetaan selain `kas_bank.*` tidak terlihat.
- Usulan pindah saldo yang prosesnya mati di antara klaim dan menyala, lalu diteruskan, tidak mengulang cek penghalang
  (hanya sesudah crash).
- Dokumen Pindah Dana tanpa kontrol dua orang yang terbitnya terhenti tertinggal "menunggu persetujuan" (terlihat di
  antrean, "Setujui lagi").
- Siapkan pindah saldo yang gagal karena galat selain pembuatan sub-akun meninggalkan akun pilihan bertanda (layar
  memberi jalan keluar); tombol Posting Gagal untuk "dokumen induk" bisa mendarat di panel kosong bila jurnal induknya
  masih tertunda.
- Pratinjau refund per roll belum membaca rekening (posting nyata benar).
- Cacat lama: PT yang memetakan kas besar ke akun khusus PT — jurnal penjualan tunai tidak terbaca di `order_revenue_recognized`.
- Skrip manual `backend/backend_test_epic7b_bank.py` memakai kategori "transfer" (kini 400).
- Utang uji/kerapian: jalur pemulihan rekening baru, uji pembalik dokumen yang kasnya menumpang jurnal induk, logika
  baris posisi kas ganda di dua pembaca, ukuran `gl_service`.
- Daftar usulan pindah saldo lintas PT di mode "Semua PT" (R14, diparkir).

## 7. Catatan pembaruan VPS

- Indeks baru dibuat otomatis saat backend menyala (nomor `PDN-` unik, koleksi `fund_transfers` & `cash_account_cutovers`,
  `cash_transactions.journal_entry_id` / `parent_journal`). Tidak ada data yang ditulis.
- Pengaturan baru memakai bawaan registri: `kontrol.pindah_dana` (1 orang), `kontrol.pindah_saldo_kas` (2 orang), dan
  `pindah_saldo_kas` masuk bawaan `kontrol.admin_tetap_dua_orang`. **Bila VPS menyimpan isian sendiri untuk daftar
  Admin-tetap-dua-orang, bawaan baru itu tidak berlaku** — cek dengan kueri di bawah (butir 4) dan tambahkan lewat Pusat
  Pengaturan bila perlu.
- **Angka posisi kas bisa berubah tampilan** di PT yang punya pemetaan akun kas ke akun khusus PT atau akun bertanda kas:
  pembaca posisi kas kini menjumlah semua akun kas PT (selaras Arus Kas). Jurnal tidak berubah.
- Kueri hanya-baca sebelum pembaruan: `2026-11-27-kas-bank-1-hasil/cek_kas_vps.js` (pemetaan kas, riwayatnya, akun
  bertanda kas, isian Admin-tetap-dua-orang, kas yang postingnya gagal/tertunda per PT). Di data acuan semuanya kosong.
