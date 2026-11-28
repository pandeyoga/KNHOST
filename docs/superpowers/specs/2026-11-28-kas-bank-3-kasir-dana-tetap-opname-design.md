# Rancangan — Kas & Bank bagian 3: kas kasir (C1), dana tetap kas kecil (C2), opname kas (C3)

Tanggal: 28 Nov 2026 · Status: **keputusan pemilik C1–C3 disetujui 25 Nov** (`docs/keputusan/2026-11-25_DAFTAR_KEPUTUSAN_TERBUKA.md`
§C); builder check selesai 28 Nov (8 jawaban, §7.8). Keputusan builder di §7 dikerjakan tanpa menunggu (perintah pemilik "langsung lanjut kerjakan saja semua"; 28 Nov
"ya dengan cepat, subagent lebih dari satu tidak apa-apa") dan dilaporkan. Dibangun di atas `main` `50df890` (F1, Kas &
Bank 1–2). Recon 28 Nov (pemetaan kode) di ledger SDD.

## 1. Masalah

- **C1:** semua rekening tunai berjenis kas kecil (`1-1110`); uang tunai dari pelanggan dan dana operasional bercampur, jadi
  "uang kasir hari ini" vs "sisa kas kecil" tidak bisa dijawab.
- **C2:** kas kecil tanpa dana tetap: tidak ada batas saldo, isi ulang diketik bebas (Pindah Dana tanpa kaitan LPJ), saldo
  tidak bisa dicek terhadap "dana tetap = tunai + nota".
- **C3:** kas tunai tidak pernah dicocokkan dengan hitungan fisik; tidak ada akun selisih kas; kekurangan karena orang tidak
  tercatat sebagai piutang karyawan.

## 2. Tujuan, bukan tujuan, anti-tujuan

**Tujuan:** jenis kas **Kas Kasir** dengan akunnya sendiri; **dana tetap** per rekening kas kecil dengan **isi ulang**
sebesar pengeluaran yang sudah dipertanggungjawabkan; **opname kas** (hitung fisik) dengan selisih yang disetujui Finance
dan dibukukan ke akun selisih kas atau piutang karyawan; pengingat opname (kasir harian, kas kecil mingguan).

**Bukan tujuan:** C4 (PT mana menerima tunai di lapangan — menunggu pemilik); hitung setoran titipan sales (C12); potong
gaji untuk piutang karyawan (pengisi kasbon K-40 belum dibangun — piutang tercatat, penagihannya di luar bagian ini);
denominasi pecahan wajib (opsional); kas lintas PT.

**Anti-tujuan:** pembaruan VPS yang mengubah jenis rekening lama atau memindah saldo sendiri; selisih opname terbukukan
tanpa orang kedua; saldo per rekening ≠ buku kas rekening (invarian Kas & Bank 1); PT yang tidak memakai fitur baru
berperilaku berbeda dari sekarang.

## 3. Keadaan sekarang (recon 28 Nov)

- Jenis rekening `account_type` bank/cash; `cash_type` kas_besar/kas_kecil (`bank_service.CASH_TYPES`); tunai bawaan kas kecil.
  Akun kas lewat satu pembantu `gl_service.akun_kas` (mode per rekening: sub-akun `{induk}-{NN}`, induk di
  `cash_account_mode.INDUK`); penjaga `verify_akun_kas_satu_pintu` menolak kode kas harfiah.
- Kwitansi tunai (`ar_receipt_service`, cara bayar `needs_account:"kas"`) → `cash_type="kas_kecil"`, rekening tunggal PT.
- Kas kecil = panjar (PD) + LPJ (`cash_advance_service`): cairkan Dr 1-1400/Cr kas; LPJ disetujui Dr beban/Cr 1-1400;
  sisa dikembalikan Dr kas/Cr 1-1400; reimburse Dr 2-1650/Cr kas. Pengeluaran kecil juga lewat kas manual keluar.
- Tidak ada opname kas, akun selisih kas, atau lokasi di rekening. Hub Kas & Bank sudah 6 tab terlihat (batas).
- Pola opname stok (`cycle_count`) dan kontrol dua orang (`dual_control`, `config_catalog_kontrol`) tersedia.

## 4. Pendekatan

- **Kas kasir = `cash_type` ketiga `kas_kasir`** (dipilih) — induk akun baru `1-1105 Kas Kasir`, kunci pemetaan
  `kas_bank.kas_kasir`; semua titik yang mengenal dua jenis kas belajar jenis ketiga. Alternatif "peran rekening" (bidang
  terpisah, akun tetap 1-1110) ditolak: tidak memisah akun buku besar (inti C1).
- **Dana tetap = bidang di rekening kas kecil + dokumen isi ulang** yang menerbitkan Pindah Dana berjumlah terkunci
  (dipilih). Alternatif "jurnal isi ulang sendiri" ditolak: kas harus lewat pintu kas & Pindah Dana yang sudah ditinjau.
- **Opname = dokumen `cash_counts`** dengan selisih → kas masuk/keluar lewat `create_cash` berlawan akun selisih/piutang
  (dipilih), supaya buku kas rekening dan sub-akun bergerak bersama (invarian Kas & Bank 1).

## 5. Rancangan

### 5.1 C1 — Kas Kasir

- Akun bawaan baru `1-1105 Kas Kasir` (aset, `is_cash`), kunci pemetaan `kas_bank.kas_kasir` (bawaan 1-1105); induk
  sub-akun per rekening `kas_kasir → 1-1105`; `akun_kas` mode lama → 1-1105 (dengan pemetaan PT). Label "Kas kasir".
- Rekening baru tunai memilih jenis: **Kas Kasir** atau **Kas Kecil** (bank → kas besar seperti sekarang). Rekening lama
  **tidak diubah**; jenis kas tidak bisa diubah sesudah rekening punya transaksi kas (pindahkan saldo lewat Pindah Dana).
- Kwitansi tunai dari pelanggan: rekening bawaan = **kas kasir tunggal PT** bila ada; bila PT tidak punya rekening kas
  kasir → perilaku sekarang (kas kecil tunggal). Setoran titipan sales dan kas masuk manual memilih rekening seperti
  sekarang.
- Semua pembaca kas (`report_basis.kode_kas`, posisi kas, arus kas) ikut membaca kas kasir; penjaga statis ikut menjaga
  `1-1105`. Antar-PT tetap hanya kas besar/bank.

### 5.2 C2 — Dana tetap kas kecil

- Rekening kas kecil punya **dana tetap** (nominal ≥ 0; 0 = tidak memakai dana tetap) dan **lokasi** opsional (lokasi kerja
  yang sudah ada; satu rekening kas kecil per lokasi). Ubah dana tetap/lokasi lewat ubah rekening (pola persetujuan
  perubahan rekening yang ada).
- **Posisi dana tetap** per rekening: dana tetap, saldo buku, uang muka (panjar) yang dicairkan dari rekening ini dan belum
  di-LPJ, dan **usulan isi ulang = dana tetap − saldo buku − panjar belum LPJ** (= pengeluaran yang sudah
  dipertanggungjawabkan sejak isi ulang terakhir; ≤ 0 → tidak perlu isi ulang). Rincian: daftar dokumen sejak isi ulang
  terakhir (LPJ disetujui, kas keluar manual, reimburse dibayar, kas masuk pengembalian).
- **Isi ulang** (`POST` dari posisi dana tetap; izin `cash.create`): pilih rekening sumber (bank/kas besar PT sama) →
  menerbitkan **Pindah Dana** sekali jalan ke rekening kas kecil dengan nominal = usulan (terkunci, dihitung ulang server),
  bertanda `isi_ulang_kas_kecil` + potret rincian; kontrol `kontrol.pindah_dana` berlaku seperti Pindah Dana lain. Satu
  isi ulang menunggu per rekening.

### 5.3 C3 — Opname kas

- Dokumen **Opname Kas** (`cash_counts`, nomor `OPK-` per PT) untuk rekening tunai (kasir, kecil, kas besar tunai):
  penghitung (izin `cash.create`) mengisi **jumlah fisik** (rincian pecahan opsional) dan catatan; sistem memotret **saldo
  buku** saat dihitung; **selisih = fisik − buku**.
- Selisih 0 → `selesai` tanpa jurnal. Selisih ≠ 0 → `menunggu_persetujuan`; **Finance** (izin `cash.approve`, bukan
  penghitung — kontrol `kontrol.selisih_kas` bawaan 2 orang, juga untuk Admin) memilih: **selisih kas** (lebih → Dr kas /
  Cr `6-9200 Selisih Kas`; kurang → Dr `6-9200` / Cr kas) atau **piutang karyawan** (kurang saja; pilih karyawan → Dr
  `1-1290 Piutang Karyawan – Kekurangan Kas` / Cr kas). Dibukukan lewat `create_cash` (ref `cash_count`, akun lawan
  eksplisit). Tolak (alasan) → penghitung menghitung ulang (opname baru).
- **Pengingat:** kartu Meja Keuangan "Opname kas jatuh tempo" per rekening tunai yang opname terakhirnya lebih lama dari
  `kas.opname_kasir_hari` (bawaan 1) / `kas.opname_kas_kecil_hari` (bawaan 7) / kas besar tunai (bawaan 7,
  `kas.opname_kas_besar_hari`); rekening tanpa transaksi kas tidak diingatkan.

### 5.4 Layar

- Rekening & Saldo: jenis kas di form rekening baru (Kas Kasir / Kas Kecil); kartu rekening menampilkan jenis, dana tetap,
  lokasi; aksi **Opname** per rekening tunai; aksi **Isi ulang** di rekening kas kecil berdana tetap.
- Kas Kecil: chip **Dana tetap** (posisi per rekening + Isi ulang + riwayat).
- Opname: tab tersembunyi **Opname Kas** (dibuka dari Rekening & Saldo, Meja Keuangan, Pusat Persetujuan): daftar,
  form hitung, putuskan selisih; pratinjau `OPK-`.

## 6. Aturan bersama

Wewenang = izin (`cash.create`, `cash.approve`, `cash.configure`); nilai = pengaturan (`kas.*`, `kontrol.selisih_kas`);
satu pintu kas `create_cash`; satu pembantu akun kas `akun_kas`; tanpa migrasi data saat menyala.

## 7. Keputusan builder (periksa)

1. `kas_kasir` jenis kas ketiga, induk `1-1105`; rekening lama tidak dikonversi.
2. Kwitansi tunai ke kas kasir tunggal PT bila ada, selain itu perilaku lama.
3. Dana tetap & lokasi = bidang rekening kas kecil; usulan isi ulang = dana tetap − saldo − panjar belum LPJ; isi ulang =
   Pindah Dana terkunci.
4. Akun baru: `1-1105 Kas Kasir`, `1-1290 Piutang Karyawan – Kekurangan Kas` (terpisah dari 1-1280 titipan yang sudah
   penuh makna), `6-9200 Selisih Kas` (pendapatan/beban lain-lain; satu akun dua arah).
5. Selisih opname selalu butuh orang kedua (`kontrol.selisih_kas` bawaan "2", masuk bawaan admin-tetap-dua-orang).
6. Kekurangan karena orang menjadi piutang karyawan yang tercatat; penagihan/potong gaji di luar bagian ini.
7. Hub Kas & Bank tetap 6 tab: Opname tab tersembunyi; Dana tetap chip di Kas Kecil.
8. **Builder check 28 Nov — delapan jawaban (keputusan builder):**
   1. *Panjar per rekening* dibaca dari dokumen kas pencairan panjar (`cash_transactions` ref panjar, `account_id` = rekening
      ini) yang panjarnya belum di-LPJ — tanpa bidang baru, tanpa isi-ulang data; pencairan lama tanpa rekening tidak dihitung
      ke rekening mana pun (disebut di rincian).
   2. *Opname berlaku untuk semua rekening `account_type=cash`* (kas kasir, kas kecil, kas besar tunai bila ada);
      `kas.opname_kas_besar_hari` untuk yang terakhir. Rekening bank tidak diopname.
   3. *Selisih dipotret saat dihitung dan dibukukan apa adanya* (transaksi sesudahnya menggeser fisik dan buku sama besar);
      tanggal kas penyesuaian = tanggal hitung; periode tertutup saat disetujui → 409 berkalimat. Kas tidak diblok.
   4. *Isi ulang = Pindah Dana itu sendiri* (bertanda `isi_ulang_kas_kecil`), nominal dibekukan saat dibuat; satu isi ulang
      terbuka per rekening = Pindah Dana bertanda yang masih menunggu/dalam perjalanan; lepas saat Pindah Dana selesai/batal.
   5. *PT dengan lebih dari satu rekening kas kasir* → tidak ada bawaan, kasir memilih rekening (perilaku "pilih rekening"
      yang ada). Lokasi opsional berlaku untuk rekening kas kasir dan kas kecil.
   6. *Karyawan* dipilih dari master karyawan HR yang ada; piutang = akun 1-1290 dengan karyawan di rujukan jurnal & dokumen
      kas (tanpa buku pembantu baru); daftar piutang dari opname berperlakuan piutang karyawan.
   7. Kode akun baru tidak bertabrakan dengan bagan bawaan; dipakai lewat konstanta/kunci pemetaan.
   8. *Pengingat opname dihitung sejak fitur aktif* (penanda waktu aktif sekali tulis, pola F1) dan hanya untuk rekening yang
      punya transaksi kas sesudah itu — tidak ada rekening yang langsung "terlambat" pada hari pembaruan.

## 8. Untuk pemilik

- Akun `1-1105`, `1-1290`, `6-9200` — setuju atau penomoran akuntan sendiri?
- Rekening kasir di PT nyata dibuat Finance di layar (dan saldo dipindah lewat Pindah Dana) — kapan, sesudah Bapak setuju.
