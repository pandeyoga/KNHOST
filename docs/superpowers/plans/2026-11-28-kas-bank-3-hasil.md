# Hasil — Kas & Bank bagian 3: kas kasir (C1), dana tetap kas kecil (C2), opname kas (C3)

Tanggal: 28 Nov 2026 · Cabang: `claude/nifty-carson-jjx3c8` · Garis dasar: `main` `50df890` (F1, Kas & Bank 1–2) +
rancangan/rencana `8009eb1`, `fa711aa` · Pohon kode akhir: `__POHON__`.

- **Rancangan:** `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` (keputusan pemilik C1–C3
  25 Nov; builder check §7.8, delapan jawaban).
- **Rencana:** `docs/superpowers/plans/2026-11-28-kas-bank-3-kasir-dana-tetap-opname.md`, 5 tugas (T2 ∥ T3 dan T4a ∥ T4b
  dikerjakan sejajar — perintah pemilik 28 Nov "ya dengan cepat, subagent lebih dari satu tidak apa-apa").
- **Tangkapan layar (data acuan):** `2026-11-28-kas-bank-3-hasil/tangkapan/` — __TANGKAPAN__

**Status: selesai, belum digabung ke `main`.** Pembaruan VPS tidak mengubah rekening atau saldo yang ada.

## 1. Yang berubah untuk pengguna

| Keadaan dulu | Sekarang |
|---|---|
| Semua rekening tunai berjenis kas kecil (akun 1-1110). Uang tunai dari pelanggan dan dana operasional bercampur, jadi "uang kasir hari ini" dan "sisa kas kecil" tidak bisa dipisah. | Jenis kas ketiga **Kas Kasir** dengan akun sendiri **1-1105 Kas Kasir** (PT mode per rekening: sub-akun `1-1105-NN`). Rekening tunai baru memilih Kas Kasir atau Kas Kecil. **Kwitansi tunai pelanggan** otomatis ke kas kasir bila PT punya satu rekening kasir (lebih dari satu → kasir memilih; tanpa kasir → seperti dulu). Rekening lama tidak diubah; jenis kas terkunci sesudah rekening punya transaksi/akun (pindahkan saldo lewat Pindah Dana). Posisi kas, arus kas, Transaksi Kas, dan pemilih rekening mengenal kas kasir. |
| Kas kecil tanpa dana tetap: saldo tanpa batas, isi ulang diketik bebas sebagai Pindah Dana tanpa kaitan pertanggungjawaban. | Rekening kas kecil bisa diberi **dana tetap** dan **lokasi** (satu kas kecil per lokasi). Kas Kecil › chip **Dana tetap**: posisi per rekening (dana tetap, saldo, panjar yang masih di tangan karyawan, **usulan isi ulang = dana tetap − saldo − sisa panjar**) + rincian dokumen sejak isi ulang terakhir. **Isi ulang** menerbitkan **Pindah Dana** bertanda dari bank/kas besar PT yang sama dengan nominal yang dihitung server dan dikunci; nominal yang berubah sejak dilihat → ditolak berkalimat, lihat ulang. Satu isi ulang terbuka per rekening; kontrol Pindah Dana tetap berlaku. |
| Kas tunai tidak pernah dicocokkan dengan hitungan fisik; tidak ada akun selisih kas; kekurangan karena orang tidak tercatat. | **Opname Kas** (dokumen `OPK-`, tab tersembunyi dibuka dari Rekening & Saldo, Meja Keuangan, Pusat Persetujuan) untuk semua rekening tunai: penghitung mengisi jumlah fisik (pecahan opsional); sistem memotret saldo buku; **selisih 0 → selesai tanpa jurnal**. Selisih ≠ 0 menunggu **orang kedua** (izin setujui kas, bukan penghitung — Admin pun): **selisih kas** (lebih/kurang ↔ **6-9200 Selisih Kas**) atau **piutang karyawan** (kurang saja; karyawan HR PT itu ↔ **1-1290 Piutang Karyawan – Kekurangan Kas**), dibukukan lewat pintu kas tunggal bertanggal hitung. **Tolak** beralasan → hitung ulang. **Batal** opname yang sudah disetujui membalik kas penyesuaiannya (jalur Posting Gagal bila jurnal gagal). Saringan perlakuan "piutang karyawan" = daftar piutang dari opname. Kartu Meja Keuangan **"Opname kas jatuh tempo"** (kasir 1 hari, kas kecil 7, kas besar tunai 7 — Pusat Pengaturan), dihitung sejak fitur aktif dan hanya untuk rekening yang punya kas sesudahnya; pemberitahuan ke penyetuju dan ke penghitung; pratinjau `OPK-` + jejak. |

**Pengaman:** dua isi ulang bersamaan → satu Pindah Dana; dua Setujui bersamaan → satu kas penyesuaian + satu jurnal; dua
Batal bersamaan → satu pembalik; penghitung tidak bisa menolak atau menyetujui selisih opnamenya sendiri; kiriman ulang
berkunci sama kembali ke dokumen yang sama; membuat rekening kas sejenis kedua tidak menggeser saldo rekening lama; kunci proses opname terlihat di Kunci Saga, kunci isi ulang lepas sendiri sesudah
5 menit bila server mati di tengah proses.

## 2. Tugas → commit

| Tugas | Commit |
|---|---|
| T1 Fondasi: jenis kas kasir, akun baru, pengaturan, kontrol `selisih_kas` | `fbe979c`, `de7b714` |
| T2 Kwitansi tunai ke kasir, dana tetap & isi ulang (server) | `3a0a0b3`, `15924ff` (gabung `32374c3`, `9a8725c`) |
| T3 Opname kas (server), antrean, Meja, pemberitahuan | `fefd3a3`, `94803ce` (gabung `3e3d60c`) |
| T4a Layar rekening berjenis kas & dana tetap | `28c628f` (gabung `9bf6ed7`) |
| T4b Layar Opname Kas | `53bb922` (gabung `4b7c043`) |
| Gelombang perbaikan akhir (server A, layar B, gate) | `758904c`, `42150ee`, `f93f08c`, `81e695f` (gabung `7b2715d`, `6cf2a7d`) |
| T5 Uji MongoDB sungguhan | `79fa3b5` |
| T5 Temuan tangkapan: kas lama tanpa rekening (server) | `c8283e0`, `0c498fc` (gabung `ebe337f`) |
| T5 Temuan tangkapan: kalimat tunai, alasan Isi ulang, Jejak (layar) | `aba200f` (gabung `83cd2d9`) |

Alur: T1–T3 (jalur uang) ditinjau per tugas; T4 (layar) tanpa tinjauan tugas (perintah pemilik "ya percepat"); tinjauan
seluruh cabang → satu gelombang perbaikan (dua agen sejajar) → tinjauan ulang: semua tertangani, tanpa temuan berat baru.

Temuan nyata yang tertangkap sebelum gabung:
- pemilih akun bayar ongkir retur menawarkan 1-1105 ke semua PT dan membukukannya tanpa dokumen kas (saldo akun ≠ buku kas
  kasir) — T1, ditutup;
- penghitung berizin setujui bisa **menolak opname sendiri** lalu menghitung ulang sampai sama dengan buku, sehingga selisih
  tak pernah diputus orang kedua — T3, ditutup (dan tombol Tolak ikut disembunyikan untuk penghitung di tinjauan akhir);
- bawaan penerimaan tunai yang tersimpan (kas kecil) mengalahkan kasir tunggal → kwitansi tunai tetap masuk kas kecil — T2,
  ditutup (R4);
- "panjar belum LPJ" dihitung per dokumen, bukan sisa uang di tangan karyawan → isi ulang bisa mengisi uang yang belum
  kembali dan kas melebihi dana tetap — T2, ditutup (R3);
- kas penyesuaian opname tidak bisa dibalik di mana pun (Transaksi Kas menolak, opname tidak punya Batal) — tinjauan akhir,
  ditutup dengan **Batal** di dokumen opname;
- **rekening kas kecil kedua menggeser saldo kas kecil lama** (tangkapan, data acuan KSC): kas lama tanpa rekening
  (bersih Rp 7.750.000) dihitung ke rekening TUNGGAL jenisnya; begitu kas kecil kedua dibuat (fitur lokasi), saldo Kas Toko
  KSC turun 33.150.000 → 25.400.000 sementara buku besar tetap. Opname memotret saldo tergeser (hitungan jujur tampil
  "lebih Rp 7.750.000" → bila disetujui terbukukan dua kali) dan **isi ulang akan mengisi lebih Rp 7,75 juta**. Ditutup
  (R7): kas lama itu ditetapkan ke rekening yang sudah ada saat rekening sejenis kedua lahir; keadaan ambigu yang sudah
  terlanjur → opname & isi ulang ditolak berkalimat;
- kalimat kwitansi tunai masih "masuk Kas Kecil" padahal masuk Kas Kasir; alasan tombol Isi ulang terpotong; Jejak dari
  pratinjau tidak menutup pratinjau — tangkapan, ditutup;
- layar bersama (pemilih rekening, Transaksi Kas) belum mengenal kas kasir; penyetuju rekening baru tidak melihat jenis kas;
  daftar piutang karyawan tak bisa dibuka; nominal isi ulang bisa bergeser antara konfirmasi dan posting — tinjauan akhir,
  ditutup.

## 3. Uji (apa adanya)

- **Backend `tests_mem` penuh** pada kode server akhir (`0c498fc`, sama dengan pohon akhir untuk `backend/`): 3367 lulus,
  2 dilewati, 3 xfail, **0 gagal**. Sebelumnya: `6cf2a7d` 3352 lulus · `4b7c043` 3342 lulus, 0 gagal.
- **Jest penuh** di `6cf2a7d`: 2259/2260 uji, 273/275 suite — `odItemCancel`, `phase4R2` (kendala lingkungan, sama dengan
  garis dasar).
- **Uji baru:** `test_KB3_1_fondasi`, `test_KB3_2_kasir_dana_tetap`, `test_KB3_3_opname`, `test_KB3_4_layar_server`
  (68 lulus di pohon gabungan), `test_KB3_5_kas_lama_rekening` (15: penetapan lewat semua jalur, pembukuan & pembatalan tidak
  berubah di mode lama dan mode akun per rekening, keadaan ambigu → 409, server menyala tidak menulis) + `kb3DanaTetap.test.js`, `kb3Opname.test.js` (jest).
- **MongoDB sungguhan** (`backend/tests/test_bp_KB3_bersamaan.py`, salinan data acuan + backend terpisah :8033, salinan
  dibuang; tiap kasus 3 kali): (1) dua isi ulang bersamaan → selalu satu 200 + satu 409, satu Pindah Dana bertanda
  Rp 1.500.000 (dana tetap 2 juta − saldo 500 ribu) selesai; (2) dua Setujui opname selisih −Rp 20.000 bersamaan → satu 200 +
  satu 409, satu kas + satu jurnal; (3) dua Batal bersamaan → satu 200 + satu 409, satu kas dibatalkan + satu jurnal
  pembalik. 3/3 lulus.

### 3a. Gate

| Mode | FAIL (garis dasar) | Lebih merah | Pelanggaran baru (per pelanggaran) |
|---|---|---|---|
| `--ci` (`4b7c043`) | 37 (43) | — | 3 (antrean opname tanpa pasangan hitung-ulang Beranda; sapuan peran Sales/Admin Sales ke Kas Kecil) → **ditutup** di `81e695f` |
| `--quick` (pohon akhir __POHON__, data acuan) | __GATE__ | | |

## 4. Keputusan pelaksanaan (periksa)

Keputusan builder rancangan §7 (1–8, termasuk delapan jawaban builder check §7.8), ditambah ketetapan selama eksekusi:

1. **R3 — panjar dana tetap = sisa di tangan karyawan** (dicairkan − belanja LPJ disetujui − sisa dikembalikan), bukan
   "panjar tanpa LPJ disetujui".
2. **R4 — kas kasir tunggal selalu menang** sebagai rekening penerimaan tunai (keputusan pemilik C1: tunai pelanggan ke
   kasir); beberapa kasir → bawaan tersimpan di antara rekening kasir, selain itu kasir memilih. Akibat: bawaan tunai yang
   tersimpan di kas kecil tidak berlaku lagi sesudah PT punya kasir.
3. **Opname yang sudah disetujui bisa dibatalkan** dari dokumen opname (alasan wajib, kontrol `selisih_kas` berlaku, pola
   Pindah Dana): kas penyesuaian dibalik; jurnal gagal → Posting Gagal.
4. **Jenis kas terkunci lebih awal** di PT mode per rekening: rekening yang sudah punya sub-akun ikut terkunci walau belum
   ada kas (pesan menyuruh nonaktifkan & buat rekening baru).
5. **Satu kas kecil per lokasi ditegakkan di layanan**, tanpa indeks unik (larangan migrasi); dua pembuatan bersamaan di
   lokasi sama bisa lolos keduanya. Kas kasir boleh banyak per lokasi.
6. **Pengingat opname** berjalan per selang waktu (kasir dihitung kemarin 17.00 → jatuh tempo hari ini 17.00); opname
   menunggu dihitung sudah diopname, ditolak tidak.
7. **Karyawan piutang** = karyawan HR PT yang sama; pemilih menyaring karyawan keluar; status tidak diperiksa ulang saat
   disetujui.
8. **Sales/Admin Sales tanpa izin lihat kas** tidak lagi diarahkan ke Kas Kecil › Dana tetap (pagar layar sesuai izin).
9. **R7 — kas lama tanpa rekening ditetapkan saat rekening sejenis kedua lahir** (buat langsung, lewat persetujuan dua
   orang, aktifkan kembali, ubah jenis kas): hanya bidang rekening + jejak penetapan + jejak audit; tanpa jurnal, nominal,
   tanggal, atau kode akun berubah; jawaban API memuat kalimat "N kas lama tanpa rekening (bersih Rp …) ditetapkan ke …".
   Tidak dijalankan saat server menyala. Keadaan ambigu yang sudah ada (≥ 2 rekening sejenis + kas tanpa rekening) →
   opname & isi ulang jenis itu ditolak: "Saldo buku rekening … belum pasti … Minta admin menetapkan rekening kas lama
   itu dulu." Kas batal tidak disentuh.
10. **R9 — PT mode akun per rekening:** kas lama dari sebelum akun per rekening menyala TIDAK ditetapkan (pembatalannya
   akan pindah ke sub-akun rekening); yang lain ditetapkan; sisanya ditahan penjaga di atas (lihat §5).
11. Panjar lama tanpa rekening yang ikut ditetapkan kini dihitung sebagai panjar rekening itu → usulan isi ulang turun sebesar
   sisa panjar itu (benar: uangnya keluar dari kas itu).
12. Diparkir (tinjauan akhir, R6, tidak memblokir): status "batal tertunda/gagal jurnal" belum tampil di layar opname;
   kalimat cadangan Batal di layar beda dengan server; tombol "Batal" vs kalimat "Batalkan opname"; daftar/ekspor piutang
   karyawan ikut memuat opname yang dibatalkan; cek kontrol per baris yang sudah disetujui; teks selang pengingat di
   server.

## 5. Untuk pemilik

1. **Kode akun baru** `1-1105 Kas Kasir`, `1-1290 Piutang Karyawan – Kekurangan Kas`, `6-9200 Selisih Kas` — setuju, atau
   penomoran akuntan sendiri? (Bisa diganti lewat Pemetaan Akun per PT.)
2. **Rekening kasir di PT nyata** dibuat Finance di layar, lalu saldo tunai pelanggan dipindah lewat Pindah Dana — kapan,
   sesudah Bapak setuju. Sampai itu, semua PT berperilaku seperti sekarang.
3. **Refund retur tunai dari rekening kasir di PT mode lama ditolak** berkalimat (pemilih akun refund sengaja tidak
   menawarkan 1-1105 agar PT lain tidak melihat pilihan baru). PT mode per rekening tidak terpengaruh. Perlu dibuka?
4. **Daftar piutang karyawan** saat ini ikut memuat opname yang sudah dibatalkan, jadi jumlah di daftar bisa lebih besar
   dari yang masih terutang — dirapikan di tindak lanjut (butir 4.9).
5. **Kas lama tanpa rekening di VPS** (kueri `cek_kas3_vps.js` butir 6): PT yang SUDAH punya dua rekening sejenis dan kas
   lama tanpa rekening tidak bisa opname/isi ulang jenis itu sampai kas lama ditetapkan — belum ada layar untuk itu; mau
   ditetapkan ke rekening mana (per PT) perlu keputusan Bapak. Hal yang sama untuk PT yang kelak memakai akun per rekening
   (kas lama dari sebelum nyala) — penetapannya butuh jurnal pindah akun. Juga: bila rekening tunggal dinonaktifkan lalu
   rekening baru sejenis dibuat, rekening baru menyerap kas lama (aturan lama, tidak diubah).
6. **Selisih opname selalu butuh orang kedua**, termasuk Admin. Di PT dengan satu pemegang izin setujui kas, opname berselisih
   menunggu sampai ada orang kedua.

## 6. Catatan kecil yang ditunda (tidak memblokir)

- Bentuk jawaban ringkasan kas tidak seragam; blok periksa ganda di perubahan rekening; jawaban ubah rekening menampilkan
  bawaan tersimpan, bukan yang berlaku; rekening baru lewat persetujuan dua orang tidak dicek ulang saat disetujui.
- Kunci jenis kas & satu-kas-kecil-per-lokasi diperiksa lalu ditulis tanpa penjaga atomik.
- Pencairan panjar lama tanpa rekening tidak dihitung ke rekening mana pun (disebut di rincian); posisi dana tetap tak
  konsisten selama isi ulang menunggu; pengembalian lama tanpa rekening bisa tampil dua kali di rincian.
- Meja Keuangan memuat seluruh riwayat kas tiap rekening tunai setiap dimuat; cek kontrol N+1 di daftar opname.
- Opname lama yang masih menunggu (hanya lewat balapan dua pembuatan) bisa disetujui lagi bila opname yang lebih baru
  dibatalkan; jurnal asal yang gagal lalu dibatalkan tampil dua baris di Posting Gagal.
- Tolak sendiri Admin di bawah "admin boleh sendiri" tercatat "approve" di jejak persetujuan.
- Kas lama tanpa rekening (perbaikan tangkapan): penetapan tidak dibatalkan bila pembuatan rekening gagal sesudahnya (saldo
  aman, jejak menyebut rekening yang batal dibuat); pembantu penetapan menambah ±175 baris di `bank_service.py` (layak modul
  sendiri); saringan "kas tanpa rekening" masih ditulis sendiri di `bank_recon_service` dan `ar_receipt_service` (setara);
  kwitansi lama tidak mendapat potret rekening; rekening tunggal dinonaktifkan lalu rekening baru sejenis dibuat → rekening
  baru menyerap kas lama (aturan lama); uji MongoDB sungguhan `backend/tests/test_g3_phase03.py` (memanggil isi jenis kas
  saat menyala) tidak dijalankan ulang.

## 7. Catatan pembaruan VPS

- **Tidak ada rekening atau saldo yang diubah saat pembaruan.** Satu tulisan saat menyala: penanda waktu aktif opname
  (`system_settings.__migrations__.kb3_opname_kas_aktif_sejak`, sekali tulis) — pengingat opname dihitung sejak itu, jadi
  tidak ada rekening yang langsung "terlambat".
- Tiga akun templat baru (1-1105, 1-1290, 6-9200) ditambahkan oleh pengisi bagan akun yang sudah ada saat pertama kali
  dipanggil (hanya menambah yang belum ada).
- Sesudah pembaruan, saat Finance **membuat rekening kas sejenis kedua** (mis. kas kecil per lokasi), kas lama tanpa rekening
  PT itu ditetapkan ke rekening yang sudah ada (hanya bidang rekening + jejak; tanpa jurnal) dan layar/API menyebutnya.
  Kueri butir 6 menunjukkan kas mana yang akan ikut, dan PT yang sudah ambigu (perlu keputusan sebelum opname/isi ulang).
- Koleksi & indeks baru: `cash_counts` (nomor `OPK-` unik per PT, id), kunci isi ulang dana tetap; dibuat saat backend
  menyala.
- Pengaturan baru dengan bawaan registri: `kas.opname_kasir_hari` 1, `kas.opname_kas_kecil_hari` 7,
  `kas.opname_kas_besar_hari` 7, `kontrol.selisih_kas.min_orang` "2"; `selisih_kas` masuk bawaan
  `kontrol.admin_tetap_dua_orang` — **bila VPS menyimpan isian sendiri untuk daftar itu, bawaan baru tidak berlaku** (kueri
  di bawah butir 3).
- Kueri cek data sebelum memakai fitur (baca saja, `cek_kas3_vps.js`): (1) akun PT sendiri yang sudah berkode
  1-1105/1-1290/6-9200 — bila ada, atur Pemetaan Akun `kas_bank.kas_kasir` / `selisih_kas` / `piutang_kurang_kas` PT itu ke
  akun lain dulu; (2) rekening tunai per PT dan jenisnya; (3) rekening tunai per PT; (4)–(5) isian `kontrol.admin_tetap_dua_orang` tanpa `selisih_kas` dan pengaturan opname yang
  tersimpan; (6) kas lama tanpa rekening per PT & jenis + jumlah rekening aktif (baris ambigu ditandai). Di data acuan:
  KSC kas kecil 3 kas (bersih Rp 7.750.000), KSC kas besar 1, KANDA kas kecil 1 — semua masih ikut rekening tunggal.
