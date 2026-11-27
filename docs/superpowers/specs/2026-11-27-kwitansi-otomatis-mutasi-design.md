# Rancangan — F1 Kwitansi otomatis dari mutasi bank

Tanggal: 27 Nov 2026 · Status: **keputusan pemilik F1 disetujui; builder check selesai (27 Nov, 4 pertanyaan → keputusan builder 10–14)** (`docs/keputusan/2026-11-25_DAFTAR_KEPUTUSAN_TERBUKA.md`
§F1: *"Otomatis penuh untuk yang cocok sempurna, sisanya kartu"*; urutan G1: sesudah Lapor Bayar). Keputusan builder di
§7 dikerjakan tanpa menunggu (perintah pemilik "langsung lanjut kerjakan saja semua") dan dilaporkan untuk diperiksa.
Inventaris kode: dibuat 27 Nov (ringkasan di §2; rujukan baris di rencana).

## 1. Masalah

- Finance mengetik kwitansi **satu per transfer** pelanggan (±2–4 menit per transfer: ketik + cocokkan), padahal mutasi
  bank yang diimpor sudah memuat kode bayar pesanan di berita transfer dan nominalnya.
- Mutasi berkode bayar sudah dikenali saat impor (`pay_code_hits`), tetapi **tidak pernah melahirkan kwitansi sendiri**:
  - pencocokan otomatis hanya menautkan kwitansi yang **sudah ada**;
  - pencocokan otomatis tidak berjalan saat impor (tombol "Cocokkan otomatis" terpisah);
  - tombol "Catat sebagai kwitansi" di layar Rekonsiliasi menjalankan **dua permintaan terpisah dari browser** (buat
    kwitansi, lalu tautkan). Bila yang kedua gagal, kwitansi ada tetapi mutasinya belum tertaut.
- Pesanan CBD/DP yang ditahan sebelum gudang (Lapor Bayar) menunggu Finance mencatat bayar walau uangnya sudah terlihat
  di mutasi.

## 2. Keadaan sekarang (ringkas)

- **Impor mutasi** (`bank_recon_service.import_lines` / `import_raw`, Kas & Bank › Rekonsiliasi): baris
  `bank_statement_lines` per rekening, ber-PT, arah `in`/`out`, berita, ref, tanggal; `pay_code_hits` diisi dari
  `payment_code_service.find_in_text` (kode milik PT baris yang sama). Duplikat dilewati.
- **Pencocokan** (`auto_match`, `_link`): skor kode bayar + nominal sama → tautan otomatis ke kwitansi yang sudah ada.
  Tautan menandai kwitansi `bank_verified` dan memanggil `buka_tahan_bayar` → `pay_hold_service.clear_if_paid`
  (pesanan tertahan dilepas bila Admin Sales sudah "Periksa & lepas").
- **Kwitansi** (`ar_receipt_service.create_receipt`): satu pintu uang masuk (kas + jurnal + alokasi + selisih bayar).
  Pagar B3 `pagar_lapor_bayar` menolak alokasi ke pesanan tertahan oleh pengguna tanpa `payment_report.decide`.
- **Lapor Bayar**: laporan `menunggu` di Meja Keuangan; Terima = `create_receipt` dengan `payment_report_id`
  (indeks unik parsial `uq_payment_report`: satu kwitansi per laporan).
- **Tidak ada**: operasi server "kwitansi dari mutasi" yang atomik; antrean mutasi di Meja Keuangan; pengaturan F1.

## 3. Tujuan dan bukan tujuan

**Tujuan:**
- Mutasi masuk berkode bayar yang **cocok sempurna** dengan tagihan pesanannya menjadi **kwitansi terverifikasi bank
  secara otomatis saat mutasi diimpor**, tanpa klik Finance. Pesanan tertahan dilepas ke gudang dengan jalur yang sama
  dengan Lapor Bayar.
- Mutasi berkode yang **tidak sempurna** menjadi **kartu di Meja Keuangan** dengan alasan yang jelas dan satu tombol
  "Catat kwitansi" yang atomik (kwitansi + tautan mutasi dalam satu permintaan server).
- Kwitansi otomatis **bisa dibatalkan** dengan satu aksi berjejak; mutasi itu tidak diproses otomatis lagi.

**Bukan tujuan:**
- Mutasi **tanpa** kode bayar (cocok nama/nominal saja) — tetap lewat layar Rekonsiliasi seperti sekarang.
- Menjalankan seluruh pencocokan otomatis (tiga pita, semua jenis kas) saat impor — hanya mutasi berkode yang diproses.
- Tarikan mutasi langsung dari bank/VA (G3 ditunda).
- Status kode bayar `lunas`/`batal` (belum ada penulisnya; tidak diperlukan F1 — lihat §8).
- Aturan bank F3 (biaya admin, bunga), jurnal berulang F2.

**Anti-tujuan (gagal walau "jalan"):**
- Kwitansi otomatis yang salah pesanan, salah PT, salah rekening, atau ganda untuk satu mutasi.
- Kwitansi otomatis yang membuat kasus selisih bayar baru yang harus diputus Finance (kalau perlu keputusan, ia kartu).
- Laporan bayar sales tertinggal `menunggu` padahal uangnya sudah dicatat dari mutasi.

## 4. Pendekatan

| Pendekatan | Isi | Untung / rugi |
|---|---|---|
| **A. Mesin server saat impor (dipilih)** | Sesudah impor (dan saat "Cocokkan otomatis" ditekan), server memeriksa tiap mutasi masuk berkode; cocok sempurna → kwitansi + tautan atomik; selain itu → kartu | Langsung saat uang terlihat; satu jalur kwitansi yang sudah ada; tanpa job baru. Mutasi hanya datang lewat impor, jadi momen ini lengkap |
| B. Job penjadwal berkala | Sapuan mutasi berkode tiap N menit | Terlambat sampai sapuan berikut; satu job lagi; tidak menambah cakupan karena mutasi tetap datang lewat impor |
| C. Kartu Asisten (Tanya KN, AG-T3) | Kartu `ar_receipt_create` disiapkan Asisten | Terikat sesi obrolan & bawaan mati; bukan antrean kerja rutin |

Builder memilih **A** (pemilik menyerahkan cara; keputusan F1 hanya menetapkan hasil).

## 5. Rancangan

### 5.1 Kapan berjalan

- **Saat impor** (`POST /api/bank-reconciliation/import` dan `/import-file`): sesudah baris tersimpan, mesin F1 memproses
  baris **baru** dari batch itu yang masuk (`direction = in`), `unmatched`, dan punya kode bayar.
- **Saat "Cocokkan otomatis"** ditekan: mesin F1 juga memproses baris berkode yang masih `unmatched` di rekening itu yang
  belum pernah diproses atau yang statusnya kartu (keadaan pesanan bisa sudah berubah). Baris yang kwitansi otomatisnya
  pernah dibatalkan (§5.6) **tidak** diproses lagi.
- **Hanya mutasi yang diimpor sesudah F1 aktif.** Saat backend pertama kali menyala dengan F1, waktu aktifnya dicatat
  sekali (penanda sistem). Baris yang diimpor sebelum itu **tidak** diproses (bukan otomatis, bukan kartu) — riwayat lama
  di VPS tetap di layar Rekonsiliasi seperti sekarang. Ini mencegah kwitansi mundur tanggal massal pada data nyata saat
  "Cocokkan otomatis" pertama kali ditekan sesudah pembaruan.
- **Baris yang pernah ditautkan mesin tidak pernah diproses otomatis lagi**, lewat jalan apa pun tautannya dilepas
  (aksi §5.6, "Lepas" di Rekonsiliasi, pembatalan kwitansi biasa). Penandanya ditulis saat mesin menautkan dan tidak
  dihapus oleh pelepasan. Baris berstatus kartu boleh dinilai ulang.
- Urutan dalam satu batch: tanggal mutasi naik, lalu urutan baris berkas — dua transfer berkode sama diproses berurutan
  (yang kedua melihat sisa tagihan sesudah yang pertama).
- Mesin hanya berjalan bila pengaturan PT baris itu menyala (§5.7). Bila mati: tidak ada kwitansi otomatis; baris berkode
  tetap menjadi kartu (mesin tetap menilai, hanya tidak bertindak), supaya Finance tetap terbantu.

### 5.2 "Cocok sempurna" (semua harus benar)

Untuk satu baris mutasi:
1. Masuk (`in`), `unmatched`, belum pernah ditautkan, PT baris = PT tertentu (bukan "all").
2. **Tepat satu kode bayar** terbaca di berita/ref, dan kode itu milik PT baris yang sama (sudah dijamin
   `pay_code_hits`). Dua kode atau lebih → kartu.
3. Pesanan kode itu hidup (bukan batal/kedaluwarsa/ditutup) dan menerima kwitansi (`validate_targets`).
4. **Nominal mutasi = nominal harapan** dengan selisih **< Rp 1** (transfer selalu rupiah bulat; tagihan DP bisa
   berpecahan, mis. Rp 173.437,5 dibayar Rp 173.438 atau Rp 173.437). Nominal harapan, menurut keadaan pesanan:
   - pesanan wajib bayar sebelum gudang → `pay_hold_service.sisa_wajib_sebelum_gudang` (R19);
   - kode milik baris jadwal tagihan (cicilan/DP sesudah konfirmasi) → sisa baris jadwal itu;
   - selain itu → sisa tagihan pesanan (`sisa_tagihan`).
   Mutasi boleh cocok dengan **salah satu** harapan yang berlaku (mis. pesanan tidak tertahan dengan kode tingkat
   pesanan: sisa tagihan).
5. **Penilaian selisih bayar** (`payment_variance_service.pre_assess`) untuk kwitansi itu **tidak** meminta keputusan
   (selisih pembulatan < Rp 1 selesai sendiri oleh aturan pembulatan yang sudah ada).
6. **Rekening mutasi** menerima cara bayar transfer, dan **sama dengan rekening instruksi bayar pesanan** bila pesanan
   punya rekening instruksi (beda rekening butuh alasan → kartu).
7. **Periode buku** tanggal mutasi masih terbuka.
8. **Laporan bayar** pesanan itu: tidak ada yang `menunggu`/`memproses`, **atau** tepat satu yang `menunggu` dengan
   nominal sama (selisih < Rp 1) dan rekening sama → laporan itu yang diterima (§5.3 jalur B). Selain itu → kartu.
9. **Tidak ada kwitansi terbuka** (belum terverifikasi) untuk pesanan itu dengan nominal sama — bila ada, mutasi
   **ditautkan ke kwitansi itu** (jalur A), bukan membuat kwitansi baru.
10. Bila butir 8 **dan** 9 sama-sama menemukan calon (ada kwitansi terbuka bernominal sama **dan** laporan menunggu
    bernominal sama) → **kartu** "Kwitansi {no} dan laporan {LB} sama-sama menunggu — putuskan", karena keduanya mungkin
    uang yang sama.
11. Laporan menunggu yang cocok tetapi **tanpa lampiran bukti** tetap boleh diterima lewat jalur B: mutasi bank adalah
    buktinya (pengecualian R9 hanya untuk penerimaan yang membawa baris mutasi).

### 5.3 Tindakan otomatis (satu operasi server per baris)

Baris diklaim lebih dulu (kunci berprasyarat pada baris, pola `atomic_claim`/`match_lock` yang ada), lalu salah satu:
- **Jalur A — kwitansi sudah ada:** tautkan mutasi ke kas kwitansi itu (`_link`, `match_type = auto`). Sama dengan pita
  otomatis yang sudah ada; bedanya kini berjalan saat impor.
- **Jalur B — laporan bayar menunggu yang cocok:** Terima laporan itu (`payment_report_service.terima`, satu pintu
  kwitansi), lalu tautkan mutasi ke kas kwitansinya. Laporan berstatus `diterima` dengan catatan "diterima otomatis dari
  mutasi bank {tanggal} · {rekening}".
- **Jalur C — kwitansi baru:** `create_receipt` dengan isian dari mutasi:
  - pelanggan & pesanan = dari kode; PT = PT baris; rekening = rekening mutasi; tanggal = tanggal mutasi;
  - cara bayar = transfer; nomor referensi = ref mutasi, atau kode bayar bila ref kosong;
  - alokasi = `[{order_id, amount: harapan}]` (pembulatan < Rp 1 ikut aturan selisih pembulatan);
  - catatan "Kwitansi otomatis dari mutasi bank {tanggal} · {rekening} · {kode}";
  - penanda sumber `source = "mutasi_bank"` + `bank_line_id`;
  lalu tautkan mutasi ke kas kwitansi itu (`match_type = auto_receipt`).

Sesudah tautan: kwitansi `bank_verified` (jalur `_link` yang ada) → `buka_tahan_bayar` → pesanan tertahan lepas ke
gudang bila Admin Sales sudah "Periksa & lepas" (R4 Lapor Bayar, tidak berubah).

**Atomik & tidak ganda:**
- Satu kwitansi per baris mutasi: **indeks unik parsial** `ar_receipts.bank_line_id` (status `posted`), pola
  `uq_payment_report`.
- Pemulihan: bila proses terputus sesudah kwitansi terbuat tetapi sebelum tautan, pemanggilan ulang menemukan kwitansi
  ber-`bank_line_id` itu dan hanya menautkan (pola Terima Lapor Bayar).
- Impor/tombol bersamaan: klaim baris mencegah dua proses pada satu baris.

**Pelaku:** pelaku sistem bernama **"Sistem (mutasi bank)"**; pengimpor dicatat sebagai pemicu di jejak audit.
**Pagar B3**: pelaku sistem tidak memegang izin; pengecualian **eksplisit menurut sumber** `mutasi_bank` (uang sudah
terbukti di rekening — tepat yang dicegah B3 bila belum terbukti). Pengecualian ini tidak berlaku untuk pengguna.

**Efek samping yang sama dengan kwitansi biasa:** kirim kwitansi WhatsApp bila ada aturan aktif (sekarang hanya di
router; mesin F1 memanggilnya juga, galat diabaikan dan dicatat); saldo pelanggan disegarkan.

### 5.4 Kartu (tidak sempurna)

- Baris berkode yang tidak lolos §5.2 diberi penanda **kartu** beserta **alasan berkalimat**, contoh:
  - "Nominal mutasi Rp 1.500.000 ≠ tagihan Rp 1.318.125 (lebih Rp 181.875)";
  - "Dua kode bayar di berita transfer: KN-7F3K2, KN-9QW2X";
  - "Rekening mutasi BCA KSC ≠ rekening instruksi pesanan Mandiri KSC";
  - "Pesanan KSC/SO-00041 sudah batal/lunas";
  - "Laporan bayar KSC/LB-00007 menunggu dengan nominal berbeda";
  - "Periode Okt 2026 sudah ditutup";
  - "Kwitansi otomatis mati untuk PT ini".
- **Meja Keuangan**, kelompok "Uang masuk perlu dicatat", antrean baru **"Mutasi berkode perlu dicek"**:
  - baris = mutasi (tanggal, rekening, nominal, kode → pesanan & pelanggan, alasan);
  - pemegang `ar_receipt.create` dan `cash.create`;
  - pop-up baris: alasan + rincian pesanan (pratinjau pesanan yang sudah ada) + tombol **"Catat kwitansi"** yang membuka
    form terima pembayaran terisi dari mutasi (nominal, tanggal, rekening, referensi, pesanan) dan menyimpannya lewat
    **operasi server atomik baru** "kwitansi dari mutasi" (§5.5). Tombol "Buka Rekonsiliasi" untuk pilihan lain
    (titipkan, abaikan, cocok manual).
- Layar Rekonsiliasi: baris berkode menampilkan alasan kartunya; tombol "Catat sebagai kwitansi" memakai operasi
  atomik yang sama (dua permintaan browser lama dihapus).

### 5.5 Operasi "kwitansi dari mutasi" (manual, atomik)

`POST /api/bank-reconciliation/lines/{id}/receipt` — isian form terima pembayaran (pelanggan, alokasi, nominal, cara,
referensi, catatan, keputusan selisih bila ada). Server: klaim baris → `create_receipt` (rekening & tanggal dari mutasi,
`source = mutasi_bank`, `bank_line_id`) → tautan. Satu permintaan; bila tautan gagal, kwitansi tidak tertinggal tanpa
tautan (pemulihan seperti §5.3). Izin: `cash.create` + `ar_receipt.create`; pagar B3 berlaku normal untuk pengguna.

**Laporan bayar menunggu pada pesanan tujuan** (supaya uang yang sama tidak tercatat dua kali):
- Permintaan **ditolak (409 pemandu)** selama salah satu pesanan tujuan punya laporan `menunggu`/`memproses`: "Putuskan
  dulu laporan bayar {LB}: Terima bila buktinya mutasi ini, Tolak bila bukan."
- **Kecuali** permintaan menyebut laporan itu (`payment_report_id`): server menerima laporan itu (`terima`, jalur B)
  dan menautkan mutasi ke kwitansinya; nominal laporan harus sama dengan nominal mutasi (selisih < Rp 1), rekening sama.
- Pop-up kartu menampilkan laporan menunggu pesanan itu dengan tombol "Terima laporan ini dengan mutasi ini" dan
  "Tolak" (alasan); keduanya memakai aturan Lapor Bayar yang sudah ada.
- Celah lama di luar mutasi (Finance mencatat kwitansi manual biasa saat laporan menunggu, lalu laporan diterima
  belakangan) **tidak** diubah F1 — dicatat sebagai catatan (§8).

### 5.6 Membatalkan kwitansi otomatis

- Aksi **"Batalkan kwitansi dari mutasi"** di rincian kwitansi bersumber `mutasi_bank` dan di baris Rekonsiliasi:
  alasan wajib; server melepas tautan mutasi (`_unlink`) lalu membatalkan kwitansi (`void_receipt`, aturan yang sama),
  dalam satu permintaan; baris kembali `unmatched` dengan penanda **"kwitansi otomatis dibatalkan"** sehingga mesin tidak
  memprosesnya lagi (tetap bisa dicatat manual lewat kartu/Rekonsiliasi).
- Izin: **aturan batal kwitansi yang sudah ada** (`ar_receipt.void`, bawaan manajer & admin — Finance bawaan tidak
  memegangnya) + `cash.create`. Tidak ada izin baru: membatalkan uang masuk tetap wewenang yang sama dengan kwitansi
  manual. Finance yang melihat kwitansi otomatis keliru meminta manajer (dicatat untuk pemilik).
- **Pesanan sudah dilepas ke gudang** oleh kwitansi itu: pembatalan tetap boleh, dengan peringatan di konfirmasi
  "Pesanan {no} sudah dilepas ke gudang ({status}); membatalkan kwitansi tidak menahan barang — tahan pesanan atau hubungi
  Gudang bila perlu." Sama dengan pembatalan kwitansi manual hari ini (tahan bayar tidak dipasang ulang).
- Kwitansi dari jalur B (laporan diterima): pembatalan mengikuti aturan kwitansi laporan yang sudah ada (laporan tidak
  terkunci).

### 5.7 Pengaturan

- Baru: `bank.kwitansi_otomatis_mutasi` — boolean, cakupan global + PT, **bawaan nyala** (keputusan F1), risiko sedang,
  penjelasan: "Mutasi masuk berkode bayar yang cocok sempurna langsung menjadi kwitansi terverifikasi bank".
- Tidak ada pengaturan toleransi: "cocok sempurna" = selisih < Rp 1 (definisi, karena transfer rupiah bulat). Toleransi
  yang lebih lebar = kartu, bukan otomatis.

### 5.8 Pemberitahuan & jejak

- **Finance** (pemegang `payment_report.decide`, per orang): satu notifikasi **per impor** — "Impor mutasi {rekening}:
  {n} kwitansi otomatis (Rp …), {m} mutasi berkode perlu dicek" (tidak dikirim bila keduanya 0).
- **Sales pemilik pesanan**: hanya bila pesanan itu **sedang tertahan bayar** — "Pembayaran {pesanan} Rp … masuk lewat
  mutasi bank (kwitansi {nomor}); pesanan dilepas ke gudang" (atau "… menunggu Admin Sales" bila belum diperiksa).
- **Jejak**: audit `bank_auto_receipt` (baris, kwitansi, pesanan, jalur A/B/C, pemicu), audit pembatalan; kwitansi
  menyimpan `source`, `bank_line_id`; pratinjau kwitansi menulis "Lahir dari mutasi bank {tanggal} · {rekening} · ref".
- Respons impor & tombol "Cocokkan otomatis" memuat jumlah `kwitansi_otomatis`, `kartu`; layar menampilkannya di
  pesan sukses.

## 6. Batasan & aturan bersama

- Wewenang menurut izin, bukan nama peran; nilai bisnis lewat pengaturan (`docs/blueprint/02_STANDAR.md` §2–§3).
- Satu pintu kwitansi: semua jalur memakai `create_receipt` / `terima` yang sudah ada; tidak ada posting jurnal baru.
- PT: semua pembacaan & penulisan ber-PT; kode bayar hanya dari PT baris.
- Tidak menyentuh data nyata; pengaturan baru memakai bawaan registri.

## 7. Keputusan builder (periksa)

1. **Pendekatan A** (mesin saat impor + saat "Cocokkan otomatis"), bukan job penjadwal.
2. **Cocok sempurna = selisih < Rp 1** terhadap harapan menurut keadaan pesanan (§5.2-4); bukan pengaturan.
3. **Laporan bayar menunggu yang nominal & rekeningnya sama diterima otomatis** (jalur B), supaya tidak ada kwitansi
   ganda dan laporan sales tidak tertinggal; laporan dengan nominal beda → kartu.
4. **Pengecualian pagar B3 menurut sumber `mutasi_bank`** untuk pelaku sistem saja.
5. **Pengaturan per PT, bawaan nyala.** Bila mati, mutasi berkode tetap menjadi kartu.
6. **Hanya mutasi berkode** yang diproses; mutasi tanpa kode tidak berubah perilakunya.
7. **Pembatalan satu aksi** (lepas tautan + batal kwitansi) dan baris tidak diproses otomatis lagi.
8. **Notifikasi sales hanya untuk pesanan yang tertahan bayar**; Finance satu ringkasan per impor.
9. **Tombol "Catat sebagai kwitansi" lama diganti operasi atomik** (dua permintaan browser dihapus).
10. **Hanya mutasi yang diimpor sesudah F1 aktif** diproses (otomatis maupun kartu); riwayat lama tidak disentuh.
11. **Baris yang pernah ditautkan mesin tidak diproses otomatis lagi**, lewat jalan pelepasan apa pun.
12. **Operasi "kwitansi dari mutasi" menolak selama ada laporan bayar menunggu** pada pesanan tujuan, kecuali Finance
    memilih menerima laporan itu bersama mutasinya; kwitansi terbuka + laporan menunggu bernominal sama → kartu.
13. **Laporan tanpa lampiran boleh diterima bila membawa baris mutasi** (mutasi = bukti bank).
14. **Pembatalan memakai izin batal kwitansi yang ada** (manajer/admin); pesanan yang sudah dilepas tidak ditahan ulang,
    hanya diperingatkan.

## 8. Di luar cakupan / catatan

- Status kode bayar `lunas`/`batal` tidak ditulis siapa pun hari ini; F1 tidak bergantung padanya (nominal harapan
  dihitung dari pesanan). Kode pesanan yang sudah lunas → kartu "sudah lunas".
- Kasus R7 Lapor Bayar (dua instruksi bayar NET30 + K-27 + B6) tetap ditunda.
- Mutasi `out` (bayar pemasok) — bukan F1.
- Celah lama Lapor Bayar: kwitansi manual biasa (bukan dari mutasi) untuk pesanan yang laporannya masih menunggu tidak
  menutup laporan itu, sehingga Terima belakangan bisa mencatat uang yang sama dua kali bila nominalnya masih di bawah
  sisa tagihan. Tidak diubah F1; diusulkan sebagai perbaikan kecil terpisah.
- Pembatalan kwitansi (manual maupun otomatis) tidak memasang ulang tahan bayar pada pesanan yang sudah dilepas.
