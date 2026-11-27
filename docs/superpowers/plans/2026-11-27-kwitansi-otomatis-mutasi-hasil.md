# Hasil — F1 Kwitansi otomatis dari mutasi bank

Tanggal: 27 Nov 2026 · Cabang: `claude/nifty-carson-jjx3c8` · Garis dasar: `a6fb7f8` (Lapor Bayar, sudah di `main`) ·
Pohon kode akhir F1: `c76ba9a` (+ catatan latihan `96958a0`).

- **Rancangan:** `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` (keputusan pemilik F1 "otomatis
  penuh untuk yang cocok sempurna, sisanya kartu"; keputusan builder §7 butir 1–14).
- **Rencana:** `docs/superpowers/plans/2026-11-27-kwitansi-otomatis-mutasi.md`, 7 tugas.

**Status: selesai, belum digabung ke `main`.** Tanpa tangkapan layar di tahap ini (perintah pemilik 27 Nov "ya percepat":
tangkapan dibuat di akhir Paket Kas & Bank bagian 1).

## 1. Yang berubah untuk pengguna

| Keadaan dulu | Sekarang |
|---|---|
| Finance mengetik kwitansi satu per transfer, lalu mencocokkannya dengan mutasi. | Saat **mutasi bank diimpor**, mutasi masuk yang **memuat kode bayar pesanan dan cocok sempurna** (PT, rekening, pesanan hidup, nominal = yang harus dibayar, selisih < Rp 1) **langsung menjadi kwitansi terverifikasi bank**, tanpa klik. Bilah hasil impor menyebut "… kwitansi otomatis, … perlu dicek". |
| Pesanan CBD/DP tertahan menunggu Finance mencatat bayar walau uangnya sudah di rekening. | Kwitansi otomatis itu membuka tahan bayar; pesanan **lepas ke gudang sendiri** bila Admin Sales sudah "Periksa & lepas" (aturan Lapor Bayar). Sales pemilik pesanan tertahan diberi tahu "Pembayaran … masuk lewat mutasi bank". |
| Laporan bayar sales tetap menunggu walau uangnya sudah masuk. | Bila ada **laporan bayar menunggu** dengan nominal & rekening sama, **laporan itu yang diterima otomatis** (satu kwitansi, tidak ganda). Bila sudah ada kwitansi yang dicatat Finance dengan nominal tepat, mutasi **ditautkan ke kwitansi itu**. |
| Mutasi berkode yang tidak cocok hanya terlihat di layar Rekonsiliasi. | Menjadi **kartu "Mutasi berkode perlu dicek"** di Meja Keuangan (kelompok "Uang masuk perlu dicatat") dengan **alasan berkalimat**: nominal beda, dua kode, rekening beda, pesanan batal/lunas, laporan bayar beda, periode ditutup, mungkin impor ganda, dll. Pop-up: alasan + rincian pesanan + laporan bayar menunggu (Terima dengan mutasi ini / Tolak) + **Catat kwitansi** (satu permintaan: kwitansi + tautan mutasi sekaligus). |
| "Catat sebagai kwitansi" di Rekonsiliasi = dua permintaan dari browser (kwitansi bisa tercatat tanpa tautan). | Satu operasi server atomik. Nominal kwitansi dari mutasi **wajib sama** dengan nominal mutasi (selisih ke tagihan diputus lewat alokasi/keputusan selisih). |
| — | **Batalkan kwitansi dari mutasi**: satu aksi beralasan (di baris Rekonsiliasi dan di rincian kwitansi) melepas tautan + membatalkan kwitansi; mutasi itu tidak diproses otomatis lagi. Peringatan bila pesanan sudah dilepas ke gudang (barang tidak ikut tertahan). |

**Pengaman:**
- Hanya mutasi yang **diimpor sesudah F1 aktif** yang diproses; riwayat mutasi lama di VPS tidak disentuh (tidak ada
  kwitansi mundur tanggal massal).
- Satu kwitansi per mutasi dijamin indeks unik basis data (`uq_bank_line_receipt`).
- Mutasi yang pernah ditautkan mesin tidak diproses otomatis lagi, lewat jalan pelepasan apa pun.
- Mutasi serupa (rekening, tanggal, nominal, kode sama) dengan yang sudah diproses → kartu "Mungkin impor ganda".
- **Sakelar per PT** di Pusat Pengaturan: `bank.kwitansi_otomatis_mutasi` (bawaan **nyala**, sesuai keputusan F1). Mati →
  mutasi berkode tetap menjadi kartu.

## 2. Tugas → commit

| Tugas | Commit |
|---|---|
| T1 Fondasi: pengaturan, waktu aktif, sumber kwitansi, indeks unik, pengecualian pagar B3 | `28e3f56` |
| T2 Penilai mutasi (cocok sempurna / kartu beralasan) | `b914036` |
| T3 Pelaksana jalur A/B/C, proses impor, pemberitahuan | `a3b3374` |
| T4 Endpoint impor/cocokkan otomatis, kwitansi dari mutasi, batal | `ae4750f`, `57fa487` |
| T5 Antrean Meja Keuangan | `921f3b7` |
| T6 Layar | `cd5ca87` |
| Gelombang perbaikan akhir | `16613bd`, `9f5f155`, `c76ba9a`, `96958a0` |

Alur: tugas jalur uang (T1–T5) pelaksana → tinjauan tugas → perbaikan bila perlu; T6 (layar) tanpa tinjauan tugas
(perintah pemilik); tinjauan seluruh cabang → satu gelombang perbaikan (5 Important + gate + 11 butir lain) → tinjauan
ulang: 17/17 tertangani, tanpa temuan baru berat.

Temuan nyata yang tertangkap tinjauan sebelum gabung:
- jalur "kwitansi sudah ada" mustahil terjadi karena urutan pemeriksaan (diperbaiki T2);
- nominal yang salah ketik bisa diam-diam mengubah keputusan selisih bayar (T4, kini selalu ditolak);
- impor ganda yang lolos penyaring bisa melahirkan kwitansi kedua (kartu "Mungkin impor ganda");
- penanda waktu aktif tertulis ulang tiap backend menyala;
- rute batal tidak dikenali penjaga keamanan gate.

## 3. Uji (apa adanya)

- **Backend `tests_mem` penuh** di `cd5ca87`: 3104 lulus, 2 gagal (`test_KFT1_izin_pengaturan`: hitungan kunci pengaturan
  belum ditambah kunci F1) → diperbaiki di gelombang akhir. **Di pohon akhir:** ⟨SUITE⟩
- **Jest penuh** di `cd5ca87`: 2133/2134, 269/271 suite (`odItemCancel`, `phase4R2` = kendala lingkungan, sama dengan garis
  dasar). **Di pohon akhir:** ⟨JEST⟩
- **Uji F1 baru:** 115 uji backend (F1-1…5) + 24 uji jest (`f1KwitansiMutasi`) + uji di berkas terkait.
- **MongoDB sungguhan:** uji balapan `test_bp_PMT3_cocok_bersamaan` (U17) lulus di salinan DB (backend terpisah :8031,
  salinan dibuang); indeks `uq_bank_line_receipt` ada; penanda `__migrations__` tetap satu dokumen sesudah beberapa kali
  backend menyala.

### 3a. Gate

| Mode | FAIL (garis dasar) | Lebih merah | Pelanggaran baru (per pelanggaran) |
|---|---|---|---|
| `--quick` (pohon akhir) | 10 (16) | 0 | 0 |
| `--ci` (`cd5ca87`) | 36 (43) | 2 POC bawaan (sama dengan Lapor Bayar) | 1 → `auth_coverage` rute batal; **diperbaiki** di gelombang akhir (penjaga 27 → 26, rute itu hilang) |

## 4. Keputusan pelaksanaan (periksa)

Keputusan builder rancangan §7 butir 1–14, ditambah ketetapan pengendali selama eksekusi:

1. **R1** Uji field asing di kwitansi: 200 tanpa field tersimpan atau 422; yang dilarang hanya field tersimpan.
2. **R2** Bila penjaga antrean persetujuan menuntut, rute kwitansi-dari-mutasi didaftarkan ke antrean `mutasi_berkode` (ternyata tidak perlu).
3. **R3** Kwitansi terbuka dicari **sebelum** pemeriksaan nominal; tautan ke kwitansi yang ada harus tepat sampai sen.
4. **R4** Dua kwitansi terbuka bernominal sama → yang tertua ditautkan.
5. **R5/R7** Catatan kecil tinjauan dibawa ke tugas berikutnya pada modul yang sama (teks "sudah lunas" menyebut kwitansi terbuka, kas lama tanpa rekening, teks periode pendek, pemulihan, notifikasi sales tidak ganda).
6. **R6** Laporan bayar yang diterima otomatis: kas = nominal & tanggal **mutasi**; alokasi = yang lebih kecil antara harapan dan nominal mutasi (DP berpecahan diselesaikan aturan pembulatan).
7. **R8** Finance bawaan **memegang** izin batal kwitansi (K-FIN-01) — kalimat rancangan dikoreksi; tombol batal dikenali dari sumber kwitansi, bukan jenis cocok.
8. **R9** Nominal kwitansi dari mutasi yang berbeda ≥ Rp 1 dari mutasi **selalu ditolak** (juga bila ada keputusan selisih).
9. **R10** Perintah pemilik "ya percepat": layar tanpa tinjauan per tugas, tangkapan di akhir paket, uji/gate/tinjauan sejajar.
10. **R11** Kartu "Mungkin impor ganda" (rekening, tanggal, nominal, kode sama dengan mutasi yang sudah diproses). Akibat: transfer kembar sungguhan di hari yang sama dicatat manual.
11. **R12** Aksi batal juga di rincian kwitansi bersumber mutasi.

## 5. Untuk pemilik

1. **Sakelar F1 bawaan nyala untuk semua PT** (keputusan F1). Bila ada PT yang ingin mulai dengan kartu saja dulu, matikan
   `bank.kwitansi_otomatis_mutasi` untuk PT itu di Pusat Pengaturan sebelum impor pertama.
2. **Sejak pembaruan, hanya mutasi yang diimpor sesudahnya yang diproses.** Riwayat mutasi lama tetap di Rekonsiliasi.
3. **Transfer kembar di hari yang sama** (pelanggan sungguh membayar dua kali nominal sama) menjadi kartu "Mungkin impor
   ganda" dan dicatat manual (R11).
4. Pertanyaan terbuka sebelumnya masih menunggu: H5, C4, izin "tetapkan sales" Admin Sales, tombol kelebihan jadi titipan,
   larangan melapor-dan-menerima sendiri.

## 6. Catatan kecil yang ditunda (tidak memblokir)

- Mode "Semua PT": Tolak laporan bayar yang tidak disebut kartu → 403 (pindah ke PT laporan dulu).
- Teks galat yang bertentangan bila klaim ulang dan tautan ulang sama-sama gagal (uang tidak terdampak).
- Dua mutasi kembar yang diproses bersamaan oleh dua impor sejajar bisa lolos cek kembar (jendela sempit).
- Kwitansi manual yang dicatat bersamaan dengan kwitansi otomatis untuk pesanan DP (balapan sempit; terlihat di kartu/selisih).
- F1 berjalan di dalam permintaan impor & "Cocokkan otomatis" — impor rekening sangat besar akan terasa lebih lama.
- Status kode bayar `lunas`/`batal` masih belum ditulis siapa pun (F1 tidak bergantung padanya).

## 7. Catatan pembaruan VPS

- Indeks `uq_bank_line_receipt` dibuat otomatis saat backend menyala.
- Penanda "F1 aktif sejak" ditulis sekali saat backend pertama menyala dengan F1; mutasi yang diimpor sebelum itu tidak
  diproses.
- Pengaturan baru memakai bawaan registri; tidak ada isian yang perlu diubah.
