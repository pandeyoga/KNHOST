# Rancangan — Kas & Bank bagian 1: akun buku besar per rekening, Pindah Dana, pindah saldo lama

Tanggal: 27 Nov 2026 · Status: **keputusan pemilik D1–D4 disetujui** (`docs/keputusan/2026-11-25_DAFTAR_KEPUTUSAN_TERBUKA.md`
§D; D5 ditunda). Keputusan builder di §7 dikerjakan tanpa menunggu (perintah pemilik "langsung lanjut kerjakan saja
semua", 27 Nov "ya percepat") dan dilaporkan. Inventaris kode: scratchpad `kasbank_inventaris.md` (27 Nov, HEAD `cd5ca87`).

Paket Kas & Bank dipecah: **bagian 1 (rancangan ini): D1–D4**. Bagian 2: C5 + C6 (kategori kas manual, persetujuan orang
kedua). Bagian 3: C1–C3 (kas kasir vs kas kecil, dana tetap, opname). Bagian 4: C7–C8 (aturan PD, akun uang muka
pemasok). C4 menunggu jawaban pemilik (PT mana yang menerima tunai).

## 1. Masalah

- **Semua rekening bank satu PT memakai satu akun buku besar** (`1-1100 Kas Besar / Bank`; kas kecil `1-1110`). Jurnal
  kas memilih akun dari jenis kas (`gl_service._cash_account`), bukan dari rekening. Akibatnya saldo per rekening tidak
  ada di buku besar, dan selisih buku besar vs rekening koran tidak bisa ditunjuk ke rekening mana.
- **Pindah dana antar rekening** (bank → bank, setor tunai ke bank, isi kas kecil) dicatat sebagai **dua kas manual
  lepas** berkategori "Transfer/Top-up" lewat akun transit `1-1150`. Satu sisi lupa dicatat = saldo salah tanpa ketahuan;
  biaya transfer tidak tercatat.

## 2. Tujuan dan bukan tujuan

**Tujuan:**
- Tiap rekening (bank, kas besar, kas kecil) punya **sub-akun buku besar sendiri**; kas berikutnya pada rekening itu
  dijurnal ke sub-akunnya. Laporan posisi kas, arus kas, menara keuangan membaca sub-akun ini.
- Dokumen **Pindah Dana**: satu form (rekening asal, tujuan, nominal, biaya transfer, tanggal kirim/terima) → kas keluar
  dan masuk berpasangan + biaya, satu nomor, satu pembatalan.
- **Setor tunai ke bank dan isi kas kecil wajib lewat Pindah Dana**; kategori "Transfer/Top-up" di kas manual ditutup
  untuk transaksi baru.
- **Alat pindah saldo lama per PT** (D4): sistem menyiapkan jurnal reklasifikasi saldo `1-1100`/`1-1110` ke sub-akun per
  rekening, Finance menyetujui (orang kedua), baru sesudah itu PT memakai akun per rekening.

**Bukan tujuan:** antar-PT (D5 ditunda; jalur antar-PT yang ada tetap), kas kasir vs kas kecil (C1), dana tetap (C2),
opname (C3), persetujuan kas manual (C6), aturan kategori Pembelian/Gaji (C5), multi mata uang.

**Anti-tujuan:** pembaruan VPS yang mengubah data nyata sendiri (akun, rekening, jurnal) tanpa tindakan Finance;
saldo per rekening yang tidak sama dengan saldo buku kas rekening itu; kas lama yang berubah akun.

## 3. Keadaan sekarang (ringkas)

- Pintu kas tunggal `cash_ledger.create_cash` (`periksa_rekening` → id tetap → `gl.post_cash_durable`); dokumen kas
  menyimpan `account_code` dari jenis kas, tetapi jurnal tidak membacanya.
- Rekening `bank_accounts`: `cash_type` (`kas_kecil`/`kas_besar`), PT, saldo awal (jurnal saldo awal `_post_opening`).
- Bagan akun: kode bebas (tanpa pola wajib), akun khusus PT (`entity_id`), unik per (kode, PT); `report_basis.kode_kas`
  mengenal akun bertanda `is_cash`; `cash_flow_service.CASH_CODES` dll. masih konstanta `1-1100`/`1-1110`.
- Usulan jurnal dua orang (`journal_proposals`, KF-T6) dan kontrol dua orang per aksi (`dual_control`) sudah ada.

## 4. Pendekatan

| Pendekatan | Isi | Untung / rugi |
|---|---|---|
| **A. Mode per PT, dinyalakan oleh alat pindah saldo (dipilih)** | Sub-akun dibuat otomatis; PT tetap memakai akun lama sampai Finance menjalankan pindah saldo PT itu (pratinjau → usulan jurnal → disetujui); persetujuan sekaligus menyalakan mode per rekening PT itu | Pembaruan VPS tidak mengubah data nyata; saldo pindah dalam satu jurnal yang diperiksa; tiap PT pindah saat siap. Dua mode hidup berdampingan sementara |
| B. Langsung per rekening sejak pembaruan | Semua kas baru langsung ke sub-akun; saldo lama dipindah belakangan | Saldo buku besar terbelah (lama di 1-1100, baru di sub-akun) sampai pindah saldo dijalankan; laporan per rekening salah di masa antara |
| C. Migrasi skrip saat deploy | Skrip membuat akun + jurnal untuk semua PT | Menulis data nyata tanpa persetujuan — dilarang (STOP & ASK) |

## 5. Rancangan

### 5.1 Sub-akun per rekening (D1)

- Rekening mendapat field **`gl_account_code`**. Saat rekening dibuat (atau saat pindah saldo PT disiapkan untuk rekening
  lama), sistem membuat **akun khusus PT** di bagan akun:
  - kode = `{induk}-{NN}`: induk `1-1100` untuk `kas_besar`/bank, `1-1110` untuk `kas_kecil`; `NN` = nomor urut dua
    digit berikutnya yang kosong di PT itu (`1-1100-01`, `1-1100-02`, …);
  - nama = nama rekening (mis. "BCA Operasional KSC"); `parent_code` = induk; `is_postable` true; **`is_cash` true**;
    `bank_account_id` = rekening.
- Kode sub-akun tidak diubah walau nama rekening berubah (nama akun ikut nama rekening).
- **Mode per PT** (`system_settings` penanda `kas_per_rekening.{entity_id}` = waktu aktif): bila aktif,
  `gl._cash_account(txn)` memakai `gl_account_code` rekening kas itu; bila tidak, jenis kas seperti sekarang.
  `periksa_rekening` mengisi `account_code` dokumen kas sesuai mode. Satu fungsi, satu tempat.
- **Pembaca saldo kas** (`cash_flow_service.CASH_CODES`, `bank_service.cash_position`, `finance_tower_service`,
  `cashflow_forecast_service`, pemilih akun refund `routers/gl.py` `startswith("1-11")`) memakai **kumpulan akun kas
  dinamis**: akun bertanda `is_cash` + induk `1-1100`/`1-1110` (satu pembantu `report_basis.kode_kas`).
- **Jurnal manual** ke sub-akun rekening **ditolak** (akun kas per rekening hanya diisi lewat kas/Pindah Dana), supaya
  saldo sub-akun = buku kas rekening (penjaga seperti akun kontrol buku pembantu).
- Kas lama tidak berubah akun; pembalik kas lama memakai jurnal asalnya (perilaku yang ada).

### 5.2 Pindah Dana (D2, D3)

- Koleksi **`fund_transfers`**, nomor **`PDN-`** (bukan `PD-` milik Pengajuan Dana), ber-PT; satu PT saja (lintas-PT tetap
  lewat antar-PT).
- Isian: rekening asal, rekening tujuan (beda, PT sama, keduanya aktif), nominal > 0, biaya transfer (≥ 0, dibebankan ke
  rekening asal), tanggal kirim, tanggal terima (opsional, ≥ tanggal kirim), catatan.
- **Sekali jalan** (tanggal terima kosong atau = tanggal kirim): kas keluar asal + kas masuk tujuan (keduanya lewat
  `create_cash`, `ref_type="fund_transfer"`, `seq` berbeda) → jurnal Dr tujuan / Cr asal; biaya: kas keluar asal ketiga →
  Dr beban bank (`kas_bank.beban_bank`) / Cr asal.
- **Dalam perjalanan** (tanggal terima > tanggal kirim): saat dibuat hanya kas keluar asal → Dr `1-1150` / Cr asal (+ biaya);
  status `dalam_perjalanan`; aksi **Terima** (tanggal terima) → kas masuk tujuan → Dr tujuan / Cr `1-1150`; status
  `selesai`. Pindah Dana yang masih dalam perjalanan tampil di butir tutup buku ("dana dalam perjalanan ≠ 0").
- **Batal**: satu aksi beralasan membalik semua kas dokumen itu (pembalik kas yang ada); ditolak bila salah satu kasnya
  sudah tercocok mutasi bank (lepas dulu di Rekonsiliasi).
- **Kontrol**: aksi baru `kontrol.pindah_dana` di Pusat Pengaturan (min orang + batas nominal, bawaan **1 orang**, bisa
  dinaikkan per PT); bila butuh orang kedua → dokumen `menunggu_persetujuan`, kas belum terbit sampai disetujui orang lain.
- **Izin**: buat/terima = `cash.create`; batal = `cash.delete`; setujui = `cash.approve` (yang sudah ada).
- **Rekonsiliasi**: kas Pindah Dana adalah kas biasa per rekening, jadi mutasi bank sisi asal dan tujuan tercocok seperti
  kas lain (tanpa perubahan mesin pencocokan).
- **D3**: kategori "Transfer/Top-up" ditutup untuk kas manual **baru**: server menolak (`create_cash_transaction` dan
  kartu Asisten `_prep_cash_manual`) dengan pesan "Pakai Pindah Dana untuk setor tunai, isi kas kecil, dan pindah antar
  rekening."; layar menghapus pilihan itu dan menampilkan tautan ke Pindah Dana. Kata kunci jurnal lama tetap (pembalik
  kas lama memakainya). Setoran titipan tunai sales (`cash_deposits`) tidak berubah.

### 5.3 Alat pindah saldo per PT (D1 aktif + D4)

Layar **Kas & Bank › Akun per rekening** (pemegang `accounting.manage`), per PT:
1. **Pratinjau** (tanpa tulisan): daftar rekening PT (jenis kas, sub-akun yang akan dibuat/sudah ada, saldo buku kas
   rekening per tanggal pindah), saldo buku besar `1-1100`/`1-1110` PT itu, **selisih belum tertaut** (kas lama tanpa
   rekening, `unlinked_transactions`), dan jurnal yang akan dibuat (Dr sub-akun per rekening / Cr akun lama sebesar saldo
   buku kas rekening; rekening bersaldo negatif dibalik sisinya). Selisih belum tertaut **tetap di akun lama** dan
   disebut terang-terangan ("selisih Rp … tetap di 1-1100 sampai ditautkan").
2. **Siapkan**: tanggal pindah (bawaan hari ini; periode harus terbuka) → sub-akun dibuat (idempoten) + **usulan jurnal**
   bertanda `pindah_saldo_kas_per_rekening` untuk PT itu (pola `journal_proposals`).
3. **Setujui** (orang kedua, aturan usulan jurnal yang ada): jurnal terposting **dan** mode per rekening PT itu menyala dalam
   satu langkah berklaim; sesudahnya kas baru PT itu masuk sub-akun. Tolak → tidak ada yang berubah selain sub-akun kosong.
- Idempoten per PT: PT yang sudah aktif tidak bisa disiapkan lagi; usulan yang masih menunggu menghalangi usulan kedua.
- Rekening baru di PT yang sudah aktif mendapat sub-akun langsung saat dibuat (saldo awal dijurnal ke sub-akunnya).

### 5.4 Layar

- **Rekening** (Kas & Bank › Rekening): kolom/isian "Akun buku besar" (kode + nama), hanya-baca; penanda "PT belum memakai
  akun per rekening" + tautan ke alat pindah saldo.
- **Pindah Dana** (tab di hub Kas & Bank): daftar (nomor, tanggal, asal → tujuan, nominal, biaya, status), form satu
  pop-up (pola `FormModal`), aksi Terima (dalam perjalanan), Setujui, Batal beralasan; pratinjau dokumen (pola
  `DocPreviewModal`) + Jejak.
- **Kas manual**: kategori Transfer/Top-up hilang; petunjuk "Setor tunai, isi kas kecil, pindah antar rekening → Pindah
  Dana".
- **Akun per rekening**: layar alat §5.3 (pratinjau tabel, tombol Siapkan, status usulan, tautan ke usulan jurnal).

## 6. Aturan bersama

- Wewenang menurut izin; nilai bisnis lewat pengaturan (`kontrol.pindah_dana.*`), bukan konstanta.
- Satu pintu kas (`create_cash`), satu pintu jurnal (usulan jurnal untuk pindah saldo).
- Tidak ada penulisan data nyata saat pembaruan: sub-akun & pindah saldo hanya lewat tindakan Finance di layar.

## 7. Keputusan builder (periksa)

1. **Mode per PT dinyalakan oleh persetujuan pindah saldo** (pendekatan A) — bukan langsung saat pembaruan.
2. **Kode sub-akun `{induk}-{NN}`** (`1-1100-01`, `1-1110-01`), akun khusus PT, `is_cash`. Penomoran akun adalah wewenang
   pemilik/akuntan: kode bisa diganti sebelum pindah saldo disetujui (lihat pertanyaan pemilik).
3. **Jurnal manual ke sub-akun rekening ditolak**; selisih belum tertaut tetap di akun lama.
4. **Nomor Pindah Dana `PDN-`**; dua tahap bila tanggal terima > tanggal kirim (akun transit `1-1150`).
5. **Kontrol `kontrol.pindah_dana` bawaan 1 orang** (perpindahan internal); bisa dinaikkan per PT.
6. **Kategori Transfer/Top-up ditutup untuk kas manual baru di server**; kas lama tidak disentuh.
7. **Izin memakai `cash.create`/`cash.delete`/`cash.approve`/`accounting.manage` yang ada**; tidak ada izin baru.

## 8. Untuk pemilik (tidak menghalangi pembangunan)

- Pola kode sub-akun `1-1100-01` — setuju, atau ada penomoran akuntan sendiri?
- Kapan tiap PT pindah ke akun per rekening (disarankan awal bulan, sesudah rekonsiliasi bulan lalu bersih)? Menjalankan
  pindah saldo di PT nyata adalah tindakan Finance di layar, sesudah Bapak setuju.
