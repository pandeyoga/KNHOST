# KN_32 — GLOSARIUM & KEBIJAKAN BAHASA ANTARMUKA

**Berlaku sejak:** 2026-07-29 · **Status:** ditegakkan oleh gate (bukan imbauan)
**Keputusan pemilik:** seluruh antarmuka memakai **Bahasa Indonesia**.

---

## 1. Masalah yang diselesaikan

Aplikasi ini dipakai bersama tim gudang, sales, dan keuangan yang bekerja dalam
Bahasa Indonesia. Sebelum sesi ini, "sudah Bahasa Indonesia" hanyalah **klaim prosa**:

* satu berkas diterjemahkan, berkas berikutnya kembali berbahasa Inggris;
* tidak ada satu pun alat yang bisa **GAGAL** ketika label Inggris masuk lagi;
* sebagian teks yang dilihat pengguna ternyata lahir di **backend**
  (`routers/onboarding.py`, judul dokumen cetak, pesan penjadwal) — bagian ini
  tidak pernah ikut diperiksa.

Akibat nyata di lapangan: operator gudang melihat `Available`, `Picked`,
`Quarantine`, `Putaway` — dan keraguan di gudang berujung salah kirim.

## 2. Bentuk penegakan (executable guardrail)

| Alat | Peran |
|---|---|
| `scripts/audit_i18n_id.py --strict` | **MEMERAH** bila ada istilah Inggris pada teks yang dilihat pengguna (FE **dan** BE) |
| `scripts/audit_i18n_id.py --self-test` | **bukti-merah**: 12 skenario membuktikan audit benar-benar bisa memerah, dan tidak salah-lapor pada `data-testid` / `className` / kunci objek / URL |
| `scripts/fix_i18n_id.py --apply` | codemod: menerjemahkan **hanya rentang teks pengguna** memakai pemindai yang sama |
| `scripts/fix_i18n_id.py --self-test` | **bukti-merah**: 11 skenario membuktikan codemod TIDAK menyentuh kunci objek, nilai status backend, `data-testid`, `className`, atau jalur impor |
| `scripts/i18n_table_id.py` | tabel terjemahan tingkat-frasa (data, bisa di-review seperti daftar kata) |

Ketiganya masuk `scripts/gate.sh` (blok STATIK) sehingga `bash scripts/gate.sh`
memerah bila ada regresi bahasa.

### 2.1 Yang dipindai (dan yang TIDAK)

**Dipindai** — hanya yang benar-benar tampil:

* teks JSX antar-tag `>Tersedia<`
* teks di **sekitar interpolasi** `>Onboarding — {peran}<` · `>{n}× pesanan<`
  (celah nyata yang pernah meloloskan 60+ label)
* potongan **template literal** `` sub={`${n} pesanan`} ``
* nilai prop teks: `label` · `title` · `placeholder` · `sub` · `description` · dst.
* di **backend**: nilai kunci `label` · `description` · `title` · `message` · `detail` · `note`

**Tidak dipindai** (supaya nol temuan palsu): `data-testid`, `className`, kunci
objek, nama field API, jalur impor, URL, komentar, dan berkas uji/POC/seed.

## 3. Kata yang WAJIB diterjemahkan (kamus)

134 istilah. Cetak lengkap: `python scripts/audit_i18n_id.py --list`. Contoh inti:

| Inggris | Indonesia | | Inggris | Indonesia |
|---|---|---|---|---|
| Available | Tersedia | | Pending | Menunggu |
| Reserved | Dipesan | | Approved | Disetujui |
| Committed | Dialokasikan | | Rejected | Ditolak |
| Picked | Sudah Diambil | | Cancelled | Dibatalkan |
| Packed | Sudah Dikemas | | Overdue | Lewat Jatuh Tempo |
| Quarantine | Karantina | | Outstanding | Belum Lunas |
| Blocked | Diblokir | | Inbound | Barang Masuk |
| Damaged | Rusak | | Outbound | Barang Keluar |
| Sold | Terjual | | Receiving | Penerimaan |
| Putaway | Penempatan Rak | | Picking | Pengambilan |
| In-Transit | Dalam Perjalanan | | Packing | Pengemasan |
| Draft | Draf | | Dispatch | Pengiriman |
| Order | Pesanan | | On Hand | Stok Fisik |
| Customer | Pelanggan | | Ledger | Mutasi |
| Invoice | Faktur | | Void | Anulir |
| Approval | Persetujuan | | Reversal | Pembalikan |
| Warehouse | Gudang | | Refund | Pengembalian Dana |
| Work Order | Perintah Kerja | | Cycle Count | Stock Opname |

## 4. Kata yang SENGAJA dibiarkan (43 istilah)

Menerjemahkan istilah berikut **memperburuk** kejelasan, bukan memperbaikinya.

### 4.1 Singkatan dokumen yang dipakai lisan sehari-hari
`PO` · `SO` · `PR` · `GR` · `RFQ` · `SKU` · `UOM` · `QC` · `WMS` · `CRM` · `POS` · `HPP` · `RFID`

### 4.2 Istilah tekstil / bahasa kerja industri
`Lot` · `Roll` · `Grade` · `Makloon` · `Finishing` · `Batch` · `Stock Opname` ·
`Landed Cost` · `Supplier` · `Item`

### 4.3 Kata yang memang Bahasa Indonesia / serapan baku
`Total` · `Status` · `Detail` · `Info` · `Transfer` · `Filter` · `Reset` ·
`Bank` · `Debit` · `Target` · `Email` · `Password` · `Scan` · `No.` · `Log` · `CSV`

### 4.4 Dua keputusan yang perlu penjelasan
| Kata | Alasan tetap Inggris |
|---|---|
| **Sales** | dalam praktik Indonesia berarti **orang/tim penjualan** ("tim sales", "kunjungan sales"). Menerjemahkan jadi "Penjualan" mengubah maknanya dari *orang* menjadi *proses*. |
| **Stage** | **enum domain tekstil** (`yarn → grey → finished`) yang divalidasi server (`domain_registry`, aturan transisi). Layar sengaja menyebut nama enumnya supaya cocok dengan pesan penolakan server. |
| **Unit** | sah dalam Bahasa Indonesia (unit organisasi/kerja). Untuk **satuan ukur** dipakai kata "Satuan". |

### 4.5 Istilah keuangan yang sudah jadi nama akun/laporan
`Store Credit` · `Petty Cash` · `Cash Advance` · `AR/AP Aging` · `Weighted Average Cost` ·
`Backorder` — menerjemahkannya memutus kaitan layar dengan nama akun GL & laporan
yang dipakai tim keuangan.

## 5. Izin khusus per-kalimat (`IZIN_KHUSUS`)

Beberapa kalimat **sengaja** memuat kata Inggris karena kata itu adalah **nilai
sistem**, bukan kalimat untuk dibaca. Contoh paling jelas: nama peran RBAC.

> "Hanya `manager/admin` yang dapat menyetujui."

Kalau layar menulis "manajer" sementara nilai di server `manager`, pengguna
mencari "manajer" di matriks izin dan tidak menemukannya. Karena itu setiap
pengecualian **wajib mencantumkan alasan** di `IZIN_KHUSUS` — daftarnya sengaja
pendek agar tidak berubah menjadi tempat sampah.

## 6. Cara menambah istilah baru

```bash
# 1) lihat apa yang masih Inggris
python scripts/audit_i18n_id.py

# 2) tambahkan pasangan istilah ke KAMUS (scripts/audit_i18n_id.py)
#    atau kalimat utuh ke TABEL (scripts/i18n_table_id.py)

# 3) terapkan + buktikan
python scripts/fix_i18n_id.py --apply
python scripts/audit_i18n_id.py --strict     # harus 0 temuan
python scripts/fix_i18n_id.py --self-test    # codemod tetap aman
bash scripts/rebuild_frontend.sh             # preview = bundel statis, WAJIB rebuild
```

## 7. Catatan operasional

* **Tidak ada hot-reload frontend** (lihat `memory/PREVIEW_STABLE_MODE.md`).
  Setiap perubahan `frontend/src` wajib `bash scripts/rebuild_frontend.sh`.
* Codemod **tidak** menyentuh `data-testid`, jadi seluruh skrip uji tetap jalan.
  Satu kasus khusus diperbaiki manual: `LoginScreen` dulu memakai satu nilai
  untuk label DAN testid (`demo-login-${role}`), kini dipisah `key` vs `label`.
* Angka acuan sesi ini: **757 penggantian** di **±230 berkas** (FE + BE),
  audit akhir **0 temuan**.

## 8. Istilah cakupan PT di laporan & form uang (PK-16 · K-15)

Laporan keuangan, form uang, dan berkas unduhan selalu menyebut PT yang angkanya ditampilkan
(`frontend/src/components/EntityScopeBanner.jsx`, field `scope_meta` di jawaban server). Kalimatnya baku —
jangan diganti sinonim di layar lain, supaya pengguna mengenali keadaan yang sama di semua laporan.

| Istilah | Arti | Dipakai di |
|---|---|---|
| **Penjumlahan semua PT** | Mode "Semua PT": angka laporan = jumlah buku tiap PT dalam cakupan pengguna, **bukan** angka grup. Selalu diikuti nama pendek PT-nya dalam kurung. | banner laporan mode gabungan; baris `Cakupan:` di unduhan CSV/XLSX |
| **belum dieliminasi** | Transaksi antar-PT (jual/beli, pinjaman, pelunasan antar-PT) masih ikut terhitung di kedua sisi; angka grup yang sudah dieliminasi hanya ada di **Konsolidasi Grup** (Akuntansi & Pajak › Laporan). Kalimat lengkap: "transaksi antar-PT **belum** dieliminasi". | banner laporan mode gabungan; label `scope_meta.label` |
| **Angka untuk {PT}** | Laporan satu PT; nama lengkap PT (bukan id, bukan singkatan). | banner laporan satu PT |
| **Dicatat di buku {PT}** | Form uang menyimpan ke buku PT di kepala aplikasi (bukan pilihan lokal di form). | form "Catat Transaksi Kas", form jurnal manual |
| **gabungan** | Penanda mode "Semua PT" pada **nama berkas** unduhan (`laba-rugi_gabungan_…csv`); satu PT memakai nama pendeknya (`laba-rugi_KSC_…csv`). | nama berkas CSV/XLSX laporan |

Mode gabungan memakai mesin konsolidasi (angka sudah dieliminasi) baru menyusul di PK-31; saat itu kalimat
"belum dieliminasi" diganti.

## 9. Istilah baku dari unit blueprint (PK-17)

Istilah yang lahir di unit `docs/blueprint/unit/<ID>.md`. Satu istilah untuk satu hal; teks layar dan pesan server
memakai kalimat persis di kolom "Teks".

| Istilah | Teks | Arti | Unit · tempat |
|---|---|---|---|
| Nilai disembunyikan | "Nilai disembunyikan" + petunjuk "Peran Anda tidak punya akses lihat modul dokumen ini." | Nominal dokumen yang modul sumbernya tidak boleh dilihat peran pembaca. Server mengirim `amount: null`, `amount_hidden: true`; nomor, jenis, status, dan tanggal tetap tampil, tombol buka dan cetak simpul itu mati. Kartu ringkasan yang nilainya disembunyikan menulis "—" | PK-17 · Jejak Dokumen (graf, pencarian, cetak), Referensi Dokumen, Kontrabon, kartu saldo Antar-PT ("Saldo antar-PT hanya untuk peran berizin keuangan antar-PT.") |
| Kelola rekening kas & bank | "Kelola rekening kas & bank" | Izin `cash.configure` (modul "Kas, Bank & Kasus Keuangan"): membuat dan mengubah rekening kas/bank. Terpisah dari mencatat transaksi kas (`cash.create`). Pesan 403: "Anda belum punya akses untuk mengelola rekening kas dan bank. Minta Admin menambahkan akses 'Kas, Bank & Kasus Keuangan'." | PK-17 · Peran & Hak Akses (label aksi), Kas & Bank › Rekening |
| Cara bayar | Label isian "Cara bayar" (kwitansi, bayar tagihan, kontrabon, biaya masuk, uang muka, pengembalian, pelunasan antar-PT) · master "Cara Bayar" (Pengaturan › Keuangan & Pajak › Master per Badan Usaha) · pesan "Cara bayar tidak dikenal: {kata}." / "Cara bayar {nama} tidak aktif untuk PT ini." / "Cara bayar {nama} tidak dipakai untuk penerimaan." / "… untuk pembayaran keluar." | **Dibayar lewat apa**: Transfer bank, Tunai, Giro / cek, QRIS, Titipan / saldo kredit, … — satu daftar untuk semua layar, bisa dimatikan per PT. **Bukan** syarat bayar (termin: tunai/kredit/DP/bertahap = KAPAN dibayar) dan bukan profil bayar pelanggan. Jangan memakai "metode" untuk teks baru | PM-T1 · semua form pembayaran |
| Atas nama | "Atas nama" (isian rekening) · "a.n. {nama}" (kartu rekening) | Nama pemilik rekening seperti tercetak di buku tabungan/rekening koran; wajib bila rekening tampil di dokumen pelanggan | PM-T1 · Kas & Bank › Rekening & Saldo |
| Peruntukan rekening | Bagian "Dipakai untuk" · centang "Penerimaan pelanggan" · "Pembayaran pemasok" · "Gaji" · "Operasional" | Untuk apa rekening boleh ditawarkan; rekening yang tidak dicentang "Penerimaan pelanggan" tidak muncul di daftar rekening penerima pelanggan. Pakai "peruntukan"/"dipakai untuk", bukan "purpose" | PM-T1 · Kas & Bank › Rekening & Saldo |
| Bawaan penerimaan | Bagian "Jadikan bawaan penerimaan untuk" · lencana "Bawaan: {cara bayar}" | Rekening yang dipilih otomatis untuk menerima uang pelanggan lewat satu cara bayar di satu PT; satu cara bayar hanya punya satu rekening bawaan per PT | PM-T1 · Kas & Bank › Rekening & Saldo |
| Tampilkan di dokumen pelanggan | Sakelar "Tampilkan di dokumen pelanggan" · alasan mati "Isi atas nama dan nomor rekening lebih dulu." / "Hanya rekening bank yang bisa tampil di dokumen pelanggan." · pesan 400 "Rekening yang tampil di dokumen wajib punya atas nama dan nomor rekening." | Rekening bank yang boleh dicetak di instruksi bayar / kwitansi (dipakai PM-T2, PM-T3) | PM-T1 · Kas & Bank › Rekening & Saldo |
| Perubahan menunggu persetujuan | Bagian "Perubahan menunggu persetujuan" · lencana "{n} menunggu" · pemberitahuan "Perubahan disimpan sebagai pengajuan dan berlaku setelah disetujui orang lain." · tombol "Setujui" / "Tolak" · "Anda yang mengajukan — rekan lain yang memutus." · pesan 409 "Perubahan rekening ini sudah diputus atau datanya sudah berubah. Ajukan ulang." | Perubahan nomor, bank, atas nama, peruntukan, cara bayar, bawaan, tampil di dokumen, aktif/nonaktif, atau rekening baru yang belum berlaku karena aturan "Ubah rekening kas/bank" PT itu = "Harus dua orang". Izin "Setujui" pada modul "Kas, Bank & Kasus Keuangan" | PM-T1 · Kas & Bank › Rekening & Saldo |
| Rekening tujuan | Isian "Rekening tujuan" (checkout, Edit / Override SO) · pilihan "{bank} {nomor} a.n. {atas nama}" · "Satu-satunya rekening penerimaan PT ini untuk cara bayar ini." · kosong "Belum ada rekening penerimaan untuk cara bayar ini — minta Finance mengaturnya di Kas & Bank." · baris detail pesanan "Rekening tujuan" · pesan 400 "Rekening tujuan bukan milik PT pesanan ini." / "Rekening ini tidak bisa menerima pembayaran pelanggan lewat {cara bayar}." · cara bayar wajib "Pilih cara bayar untuk pesanan ini." | Rekening PT pesanan yang harus dituju pelanggan saat membayar; diambil dari rekening ber-peruntukan "Penerimaan pelanggan" yang melayani cara bayar itu (terisi dari bawaan penerimaan). Pesanan menyimpan potretnya — dokumen lama tetap menyebut rekening saat itu. Jangan memakai "rekening penerima"/"akun bank" di teks baru | PM-T2 · Checkout, detail pesanan, override SO |
| Kode bayar | "Kode bayar: {kode}" (detail pesanan) · baris "Berita/kode   : {kode}" (instruksi bayar) · pengaturan "Awalan kode bayar" | Kode pendek `{awalan}-{5 karakter}` (mis. KN-7F3K2; tanpa 0, 1, I, O) yang ditulis pelanggan di berita transfer, unik lintas PT; dipakai mencocokkan mutasi bank (PM-T3). Lahir saat pesanan bayar-dulu dikonfirmasi, atau per baris tagihan | PM-T2 · detail pesanan, Konfirmasi Pesanan, Faktur |
| Instruksi bayar | Kotak "Instruksi Pembayaran" (Konfirmasi Pesanan & Faktur, kartu detail pesanan) · lima baris "Pembayaran untuk pesanan …" / "Jumlah        : Rp …" / "Jatuh tempo   : …" (atau "sebelum barang dikirim") / "Transfer ke   : …" / "Berita/kode   : …" · tombol "Salin instruksi bayar" · pemberitahuan "Instruksi bayar disalin." · kosong "Instruksi bayar tersedia setelah pesanan dikonfirmasi." / "…setelah barang dikirim." · bagian template "Instruksi pembayaran (rekening tujuan & kode bayar)" | Petunjuk ke rekening mana dan dengan kode apa pelanggan membayar, satu blok per tagihan berkode yang belum lunas; dicetak hanya bila cara bayar ber-rekening bank dan rekening tujuan ditandai "Tampilkan di dokumen pelanggan". Teks yang disalin = teks di dokumen = teks WhatsApp | PM-T2 · detail pesanan, dokumen cetak |
| Rekening penerima | Isian "Rekening penerima" (form kwitansi desktop & HP) · pilihan "{nama rekening} · {bank} {nomor} a.n. {atas nama}" · "Satu-satunya rekening penerimaan PT ini untuk cara bayar ini." · kolom "Rekening" (Riwayat Pembayaran) · baris cetak "Rekening" · pesan 400 "Rekening penerima bukan milik PT kwitansi ini." / "Rekening ini tidak bisa menerima pembayaran pelanggan lewat {cara bayar}." | Rekening PT kwitansi tempat uang pelanggan BENAR-BENAR masuk (bisa berbeda dari rekening tujuan pesanan). Terisi dari rekening tujuan pesanan yang dialokasi, lalu bawaan PT; kwitansi menyimpan potretnya. Untuk pesanan (ke mana pelanggan harus membayar) tetap "Rekening tujuan" | PM-T3 · form kwitansi, Riwayat Pembayaran, cetakan kwitansi |
| No. referensi | Isian "No. referensi" (bertanda "*" bila wajib) · kolom "No. referensi" · pengaturan "Wajibkan nomor referensi di kwitansi" · pesan 400 "Nomor referensi wajib diisi untuk {cara bayar}." · alasan tombol mati "Isi nomor referensi (wajib untuk {cara bayar})." | Nomor transaksi di bukti transfer/giro/QRIS pelanggan; dulu diketik di kolom catatan. Wajib hanya bila cara bayar butuh referensi DAN pengaturan PT menyala | PM-T3 · form kwitansi, Riwayat Pembayaran |
| Tidak sesuai instruksi | Peringatan "Tidak sesuai instruksi bayar pesanan {nomor} ({rekening instruksi})" · isian wajib "Catatan alasan" · lencana "Tidak sesuai instruksi" (Riwayat Pembayaran) · pesan 400 "Rekening penerima berbeda dari instruksi bayar pesanan. Isi catatan alasannya." | Uang diterima di rekening lain dari rekening tujuan salah satu pesanan yang dialokasi; boleh disimpan dengan catatan alasan (minimal 5 huruf) | PM-T3 · form kwitansi, Riwayat Pembayaran |
| Tercatat | Lencana status "Tercatat" (Riwayat Pembayaran) · pilihan pengaturan "Tercatat (cukup ada kwitansi)" | Kwitansi non-tunai yang dicatat berdasarkan bukti pelanggan dan BELUM dicocokkan dengan mutasi bank di rekening yang sama | PM-T3 · Riwayat Pembayaran, pengaturan tahan kirim |
| Terverifikasi bank | Lencana status "Terverifikasi bank" · saringan "Belum terverifikasi lebih dari {N} hari" · pengaturan "Kwitansi wajar belum terverifikasi (hari)", "Bayar-dulu boleh dikirim setelah pembayaran" ("Terverifikasi bank (cocok dengan mutasi)") · pesan 409 "Kwitansi sudah terverifikasi bank. Lepaskan pencocokan mutasinya dulu." | Kas kwitansi sudah cocok PENUH dengan mutasi bank di rekening penerima yang sama (diisi Rekonsiliasi Bank; hilang lagi bila pencocokannya dilepas). Kwitansi tunai tidak pernah menunggu status ini (lencana "Tunai") | PM-T3 · Riwayat Pembayaran, Rekonsiliasi Bank, pagar kirim |
| Kode bayar (mutasi) | Lencana "Kode bayar {kode}" di baris mutasi · tombol "Catat kwitansi dari mutasi ini" · alasan skor "Kode bayar {kode} cocok dengan pesanan {nomor}" / "Kode bayar cocok, nominal berbeda {Rp}" | Kode bayar pesanan yang ditemukan di berita transfer mutasi; nominal sama → dicocokkan otomatis, nominal berbeda → hanya usulan. Bila pesanan belum punya kwitansi, form kwitansi dibuka terisi dari mutasi | PM-T3 · Rekonsiliasi Bank |
| Kontrol dua orang | "Kontrol dua orang" (tab Pengaturan › Persetujuan) · pilihan "Cukup satu orang" / "Harus dua orang" · kolom "Dua orang di atas (Rp)" · sumber "Aturan PT ini" / "Mengikuti semua PT" / "Aturan semua PT" / "Bawaan" | Aturan "pengaju tidak boleh memutuskan dokumennya sendiri", per aksi dan per PT. "Harus dua orang" = keputusan wajib oleh orang selain pengajunya; di atas batas nominal selalu dua orang. Pesan 403: "{Aksi} harus diputuskan orang lain: Anda yang mengajukannya. Minta rekan yang berwenang. Admin dapat mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang." Jangan memakai "SoD", "segregation of duties", "dual control" di layar | KF-T6 · Pengaturan › Persetujuan › Kontrol dua orang, semua titik setuju/putus |
| Jenjang | "Jenjang 1 · Persetujuan", "Jenjang 2 · Direksi" · kolom "Jenjang", "Mulai dari (Rp)", "Sampai di bawah (Rp)", "Yang boleh menyetujui", "Siapa saja yang lolos" · lencana "Aturan grup" / "Aturan khusus PT ini" / "Aturan bawaan (belum disimpan)" · pilihan "Semua pemegang akses" · tombol "Ubah", "Buat aturan khusus PT ini", "Kembali ke aturan grup", "Coba nilai" | Urutan keputusan satu dokumen; tiap jenjang punya rentang nominal (batas atas eksklusif: "sampai di bawah") dan daftar peran yang boleh memutus. Yang lolos = peran tercantum DAN memegang izin setujui modulnya. Pesan 403: "Anda belum punya akses untuk menyetujui {jenis}. Minta Admin menambahkan akses '{modul}'." atau "{Jenis} senilai {Rp} pada jenjang {n} diputus oleh {peran}. Peran Anda belum tercantum di Aturan Persetujuan." Jangan memakai "tier", "level", "approver", "role", "threshold" di layar | KP-T4 · Pengaturan › Persetujuan › Aturan Persetujuan, semua pintu setuju/putus |
| Menunggu orang kedua | "Menunggu orang kedua" · "{n} jurnal manual menunggu orang kedua" · "Menunggu orang kedua — diajukan {nama}" | Pengajuan (jurnal manual, buka kembali tutup buku) sudah tercatat tetapi belum dijalankan; orang lain yang berwenang yang menjalankannya | KF-T6 · Buku Besar › Jurnal, Tutup Buku |
| PT induk (konsolidasi) | "PT induk (konsolidasi)" (sakelar di wizard & detail PT) · keterangan "PT induk tidak ikut dijumlahkan sebagai baris di laporan konsolidasi dan tidak muncul di pilihan PT pada tutup buku." | PT pemegang saham grup (`is_group`). Laporan konsolidasi menjumlahkan PT anggota, bukan PT induk; PT induk juga tidak ditawarkan di pemilih PT Tutup Buku, Buka Periode, Suspense, Eliminasi. Jangan memakai "holding" atau "parent" untuk teks baru | KP-T1 · Pengaturan › Perusahaan (PT) › Profil PT |
| Persen kepemilikan | "Persen kepemilikan (%)" · keterangan "Dipakai Konsolidasi Grup: bagian non-pengendali = laba dan ekuitas PT ini × (100 % − persen ini)." · kepala kolom Konsolidasi Grup "Kepemilikan {n} %" | Persen saham grup atas PT ini (> 0 sampai 100, bawaan 100; K-10). Mati bila PT induk. Sejak PK-31 dipakai laporan Konsolidasi Grup (bagian non-pengendali). Jangan memakai "ownership" | KP-T1 · Pengaturan › Perusahaan (PT) › Profil PT; PK-31 · Konsolidasi Grup |
| Bagian non-pengendali | Baris "Bagian non-pengendali" · kolom "Laba bersih {tahun}" / "Ekuitas per {tanggal}" | Bagian laba dan ekuitas PT anggota yang BUKAN milik grup: laba & ekuitas buku PT × (100 % − persen kepemilikan). Tidak tampil bila semua PT 100 %. Jangan memakai "NCI", "minority interest" | PK-31 · Keuangan › Laporan › Konsolidasi Grup |
| Bagian pemilik induk | Baris "Bagian pemilik induk" | Laba & ekuitas konsolidasi dikurangi bagian non-pengendali (eliminasi antar-PT seluruhnya ditanggung pemilik induk) | PK-31 · Konsolidasi Grup |
| Eliminasi per bulan · Beku | Judul "Eliminasi otomatis antar-PT per bulan" · lencana "Beku" (gembok) · lencana "Bulan berjalan" · peringatan "Eliminasi bulan {bulan} berbeda dari hitung ulang karena ada jurnal mundur. Periksa sebelum memakai laporan ini." | Eliminasi transaksi antar-PT dihitung per bulan dari data bertanggal. "Beku" = bulan sudah ditutup di PT penjual dan pembeli; angkanya tidak dihitung ulang. "Bulan berjalan" = dihitung sampai tanggal laporan | PK-31 · Konsolidasi Grup › Eliminasi |
| Pengembalian dana (antar-PT) | Kolom "Pengembalian dana" · "Harus dikembalikan ke {PT}" (sisi penjual) · "Akan diterima dari {PT}" (sisi pembeli) · tombol & dialog "Catat Pengembalian Dana" · konfirmasi "Pengembalian dana Rp {nominal} dari {PT penjual} kepada {PT pembeli} akan dicatat dan dijurnal di kedua PT." · lencana "Pengembalian Dana" di daftar Settlement · pesan "Transaksi {nomor} tidak punya sisa pengembalian dana." / "Nilai pengembalian dana {rupiah} melebihi sisa pengembalian dana transaksi {nomor} ({rupiah})." / "Pilih PT yang mengembalikan dana dan PT penerima yang berbeda." / 403 "Anda belum punya akses untuk mencatat pengembalian dana atas nama PT ini. Minta Admin menambahkan akses 'Transaksi Antar Badan Usaha'." | Retur atas transaksi antar-PT yang sudah (sebagian) lunas: kelebihan bayar = utang PT penjual kepada PT pembeli; dilunasi lewat kas/bank (bukan saling hapus); tidak termasuk "Sisa". Spesifikasi PK-31 menulis "utang refund"/"Catat Refund" — di layar ditulis "pengembalian dana" (KAMUS `audit_i18n_id.py`: refund → Pengembalian Dana; `02` §4 L1). Nama teknis tetap `refund_*`, `/api/interco/refunds` | PK-31 · Antar-PT › Saldo Antar-PT, Settlement |
| Ubah status PKP | Tombol "Ubah status PKP" · pop-up "Ubah Status PKP" ("Status baru", "Berlaku mulai", "NPWP", "Alasan", panel "Dampak") · "Akan menjadi {status} mulai {tanggal}" + "Batalkan jadwal" | Tindakan bertanggal berlaku dan beralasan untuk mengubah status PKP PT (PKP = memungut PPN, Non-PKP = tanpa PPN). Tanggal hari ini/lampau langsung berlaku; tanggal mendatang dijadwalkan. Dokumen yang sudah ada tidak dihitung ulang. Status PKP tidak diubah lewat "Simpan Perubahan" profil | KP-T1 · detail PT, bagian Pajak |
| Tahun buku & mata uang | "Tahun buku: {bulan awal}–{bulan akhir}" · "Mata uang pembukuan: {label}" · sumber "mengikuti pengaturan grup" / "khusus PT ini" · wizard "Tahun buku berakhir pada bulan" | Nilai yang dipakai laporan dan tutup buku tahunan (kunci Pusat Pengaturan, lapisan PT). Pakai "tahun buku", bukan "tahun fiskal"/"awal tahun fiskal", dan "mata uang pembukuan", bukan "mata uang" saja | KP-T1 · detail PT & wizard Tambah Badan Usaha |
| Nama di kop surat | "Nama di kop surat" (Profil PT) · keterangan "Kosongkan untuk memakai nama legal." | Nama dagang yang dicetak di kop dokumen bila berbeda dari nama legal (`print_name`). Nama legal tetap dipakai faktur pajak dan dokumen hukum. Jangan memakai "print name"/"nama cetak" | KP-T6 · Pengaturan › Perusahaan (PT) › Profil PT |
| Slogan | "Slogan" (Profil PT) · tercetak miring di bawah nama pada kop | Kalimat pendek di bawah nama PT pada kop surat (`tagline`). Jangan memakai "tagline" di teks layar | KP-T6 · Pengaturan › Perusahaan (PT) › Profil PT |
| Identitas di kop | Blok "Identitas di kop" (hanya-baca) · "Diambil dari Profil PT." · tombol "Ubah di Profil PT" · kotak kuning "Kop PT ini masih memakai teks lama" (kolom "Yang tercetak sekarang" / "Di Profil PT"; tombol "Pakai data Profil PT" / "Salin teks kop ke Profil PT") | Nama, alamat, NPWP, telepon, email, slogan, dan situs yang tercetak di kop dokumen PT — satu sumber Profil PT. Teks kop lama (dari layar perancang dulu) tetap tercetak sampai pemilik memilih salah satu tombol | KP-T6 · Pengaturan › Dokumen & Notifikasi › Template Dokumen › Desainer PDF |
| Berlaku untuk (template dokumen) | Pemilih "Berlaku untuk": "Semua PT" / "Hanya {PT}" · tanda "khusus PT ini" · tombol "Kembali ke aturan semua PT" · keterangan "Diatur untuk semua PT." | Lapisan aturan cetak yang disunting. Untuk satu PT hanya teks pembuka, teks penutup, teks footer, tempat & tanggal sebelum tanda tangan, tempat, slot tanda tangan, dan tanda air; tata letak, huruf, warna, dan kolom tetap satu untuk semua PT. Jangan memakai "override"/"scope" | KP-T6 · Pengaturan › Dokumen & Notifikasi › Template Dokumen › Desainer PDF |
| Lengkapi PT / Kesiapan PT | Langkah "Lengkapi PT" (langkah 5 wizard, bagian Kesiapan detail PT, tab "Kesiapan PT") · "{siap} dari {total} hal sudah siap" · tombol "Lengkapi" · "Ulangi penyiapan" · "Langkah ini bisa dilanjutkan kapan saja dari tab Kesiapan." | Daftar hal yang membuat PT siap bertransaksi dan tutup buku (16 butir, dihitung server). "Lengkapi" mengganti PT aktif ke PT itu lalu membuka layar pengisiannya. "Penyiapan awal" = bagan akun bersama + lapisan pengaturan PT; "Ulangi penyiapan" menjalankannya lagi dengan aman. Jangan memakai "readiness", "onboarding", atau "provisioning" | KP-T2 · Pengaturan › Perusahaan (PT) › Kesiapan PT |
| Pengguna keuangan | Butir kesiapan "Pengguna keuangan" · "Belum ada pengguna yang bisa mencatat kas untuk PT ini" | Pengguna aktif yang boleh bekerja di PT itu dan perannya punya akses mencatat Kas & Bank (dibaca dari izin peran, bukan nama peran) | KP-T2 · tab Kesiapan |
| Sebelum mengarsipkan | Daftar centang "Sebelum mengarsipkan" di pop-up arsip PT (pengguna, dokumen terbuka, saldo yang masih hidup, karyawan terdaftar, tutup buku) | Hal yang sama dengan yang diperiksa server sebelum PT diarsipkan; baris yang belum beres menyebut jumlah dan contohnya. Arsip bukan hapus | KP-T2 · Badan Usaha › Arsipkan |
| Batas retur umum | "Batas retur umum" (judul bagian) · baris hanya-baca "Batas retur umum: pelanggan {n} hari sejak surat jalan · pemasok {m} hari sejak barang diterima." | Batas hari retur yang berlaku bila kebijakan retur per kategori/pelanggan tidak menimpanya: pelanggan dihitung dari tanggal surat jalan, pemasok dari tanggal barang diterima gudang; plus pengingat ke pemasok, potong tagihan pesanan asal, dan harga per grade. Diatur di Pusat Pengaturan (kunci `returns.*`), bukan form sendiri. Jangan memakai "asumsi retur" di layar | KF-T2 · Penjualan › Retur › Kebijakan Retur |
| Aturan jadwal bayar | "Aturan jadwal bayar" (judul bagian) · "Tanggal tutup tagihan antar-PT" · "Tanggal bayar antar-PT" · "Tanggal acuan jadwal bayar antar-PT" · "Izinkan saling hapus hutang antar-PT" | Aturan yang menentukan periode dan tanggal bayar tiap transaksi antar-PT, pengingatnya, serta boleh-tidaknya saling hapus dan pelunasan sebagian — untuk semua PT atau satu PT pembayar. Pakai "saling hapus", bukan "netting", dan "tanggal tutup", bukan "cutoff", untuk teks baru | KF-T2 · Keuangan › Antar-PT › Jadwal Bayar |
| Aturan khusus | "Aturan khusus pelanggan ini" / "Aturan khusus barang ini" (judul bagian) · "Mengikuti aturan PT: {nilai}" · "Khusus pelanggan ini: {nilai} (aturan PT: {nilai})" · tombol "Atur khusus" / "Kembali ikut aturan PT" · "Bisa dibedakan per pelanggan — {n} pelanggan diatur khusus" | Nilai aturan Pusat Pengaturan yang berlaku hanya untuk satu pelanggan atau satu barang dan menang atas aturan PT-nya (mis. masa tenggang denda, toleransi selisih bayar, batas susut potong). Kosong = mengikuti aturan PT. Pakai "aturan khusus", bukan "override"/"lapisan pelanggan"; "barang" untuk teks baru (menu tetap "Produk") | KF-T5 · Penjualan › Pelanggan & CRM › detail pelanggan; Produk & Harga › Master Produk › ubah barang; kartu Pusat Pengaturan |
| Status rekonsiliasi transaksi kas | Lencana "Terekonsiliasi" · "Sebagian {rupiah}" (keterangan "Sudah dicocokkan {rupiah} dari {rupiah}") · "Belum" · tautan "Cocokkan di Rekonsiliasi Bank" · pesan 410 "Tanda rekonsiliasi manual sudah tidak dipakai. Cocokkan transaksi dengan mutasi bank di Keuangan › Rekonsiliasi Bank." · pesan 409 "Mutasi bank ini baru saja dilepas atau diubah proses lain. Muat ulang." | Seberapa jauh transaksi kas sudah dicocokkan dengan mutasi rekening koran: penuh, sebagian (angka yang sudah dicocokkan), atau belum sama sekali. Hanya lahir dari pencocokan di Rekonsiliasi Bank — tidak ada lagi tombol "Tandai". Pakai "Sebagian", bukan "parsial" | PK-21 · Keuangan › Kas & Bank › Rekening & Saldo (buku rekening), Rekonsiliasi Bank |
| Penerima & ambang pengingat | Kolom "Penerima" (mis. "Manajer", "Pemegang izin Tagihan Supplier — Bayar") dan "Ambang" (mis. "7 hari · 40 peringatan") + tautan "Ubah" di Penjadwal & Notifikasi · tabel "Penerima tiap pengingat" (kolom "Pengingat", "Cara menentukan": "Peran yang dipilih" / "Semua pemegang izin", "Peran", "Izin") | Siapa yang menerima tiap pengingat terjadwal dan batas kapan pengingat dikirim, untuk PT aktif (tabel PT menggantikan tabel grup). "Semua pemegang izin" = setiap akun aktif yang perannya memegang izin itu dan bertugas di PT dokumen. Pakai "ambang" (bukan "threshold") | KP-T7 · Pengaturan › Dokumen & Notifikasi › Pengingat Otomatis |
| Akun kontrol | Lencana "Akun kontrol" + petunjuk "Hanya berubah lewat dokumen {buku pembantu}" (Bagan Akun) · keterangan "Akun piutang, hutang, persediaan, dan antar-PT tidak ada di daftar ini karena saldonya dijaga dokumen. Koreksi lewat dokumennya." (Jurnal Manual Baru) · pesan 422 "Akun {kode} · {nama akun} adalah akun kontrol {buku pembantu} dan tidak menerima jurnal manual. Koreksi lewat {dokumen pengganti}." dan "Jurnal {nomor} berasal dari {sumber} dan menyentuh akun kontrol {buku pembantu}. Batalkan atau koreksi dokumen sumbernya; pembalikan manual ditolak." · pengaturan "Jurnal manual ke akun kontrol" (Tolak / Izinkan) | Akun buku besar yang saldonya dimiliki buku pembantu — piutang usaha, hutang usaha, persediaan, antar-PT — menurut Pemetaan Akun PT itu (termasuk akun lama di riwayat pemetaan). Hanya berubah lewat dokumennya; jurnal manual, reklasifikasi suspense, dan pembalikan manual jurnal otomatis ke akun itu ditolak kecuali pengaturan PT "Izinkan". Jangan memakai "control account" atau "akun rekonsiliasi" di layar | PK-36 · Jurnal & Buku Besar (Jurnal Manual Baru, Suspense, rincian jurnal), Bagan Akun, Pengaturan › Keuangan & Pajak |
| Jadwal teknis | "Jadwal teknis — tidak diubah dari layar." · "tiap [n] menit" / "tiap [n] jam" | Job penjadwal gerbang RFID yang selangnya dikunci (titik henti RFID); job lain diatur dalam satuan bawaannya (menit atau jam) | KP-T7 · Penjadwal & Notifikasi |
| Permintaan Internal (dari keranjang) | Tombol "Buat Permintaan Internal ({jumlah} {satuan})" di keranjang · berhasil "Permintaan Internal {nomor} dibuat — menunggu Admin Sales." · gagal "Permintaan gagal dibuat: {pesan}" | Stok PT sendiri kurang dan tersedia di PT lain: kasir mengajukan Permintaan Internal; Admin Sales menjadikannya transaksi antar-PT berharga kontrak. Menggantikan "Minta Transfer dari {PT}" (jalur transfer harga pokok, ditutup — 410 "Transfer antar-PT lewat jalur ini sudah ditutup. …"). Jangan memakai "transfer inter-company" di layar | PK-30 · Kasir (keranjang/checkout) |
| Panjang roll aktual (antar-PT) | Pengaturan "Bila panjang roll beda dari pesanan antar-PT" (pilihan "Dokumen menyesuaikan panjang roll yang dikirim" / "Tolak bila panjang roll tidak sama dengan pesanan") · rincian "Disesuaikan ke panjang roll aktual: {dari} → {ke} {satuan}, nilai {rupiah} → {rupiah}." · jurnal "Jurnal Penyesuaian Panjang Roll" · panel Posting Gagal "Penyesuaian Panjang Antar-PT" | Roll antar-PT dikirim utuh; jumlah & nilai dokumen kembar mengikuti panjang roll yang benar-benar pindah | PK-30 · Pengaturan › Pajak & pembukuan › Jual-beli antar-PT, rincian transaksi Antar-PT |
| Harga/PPN di luar kontrak | Label aksi "Ubah harga/PPN di luar kontrak" (izin `interco.override_terms`, modul "Transaksi Antar Badan Usaha") · isian "Alasan mengubah harga/PPN" · rincian "Harga/PPN di luar kontrak oleh {nama}: {alasan}" · "PT pembeli bukan PKP: PPN masukan {rupiah} tidak dapat dikreditkan." | Harga baris, mode harga, atau mode PPN yang berbeda dari kontrak internal & pengaturan PT penjual. Pesan 403: "Anda belum punya akses untuk mengubah harga atau PPN antar-PT di luar kontrak. Minta Admin menambahkan akses 'Transaksi Antar Badan Usaha'." Jangan memakai "override" di layar | PK-30 · form Transaksi Antar-PT Baru, rincian |
| Plafon (kredit) | "Plafon kredit" · "Plafon bawaan pelanggan baru" (Pengaturan) · pilihan "Ikut plafon bawaan PT" / "Plafon khusus pelanggan ini" / "Tanpa batas" · "Berlaku sampai" · "Plafon khusus berakhir {tanggal} — sekarang memakai bawaan PT" · lencana "ikut PT" / "khusus" | Batas piutang seorang pelanggan di SATU PT yang dipakai pemeriksaan kredit (status awas/diblokir). "Ikut PT" = plafon bawaan PT (0 = tanpa batas); "khusus" = angka pelanggan ini; "Tanpa batas" pilihan tersendiri, bukan angka 0. Pakai "plafon", bukan "limit"/"credit limit" untuk teks baru | CR-T1 · kartu pelanggan › Kredit, ringkasan kredit, Pengaturan › Pembayaran pelanggan |
| Profil kredit | Tab "Kredit" (kartu pelanggan) · judul "Profil kredit yang berlaku" · "Profil kredit di PT" · baris "Termin yang diizinkan", "Termin bawaan", "Tahan pesanan bila telat lebih dari", "Status kredit" ("Normal" / "Diblokir manual"), "Alasan blokir" · "belum dipakai saat pesanan dibuat" (termin) · memuat "Memuat profil kredit…" | Nilai kredit seorang pelanggan per PT: plafon, berlaku sampai, termin, hari telat yang menahan pesanan, dan blokir manual. Hanya berubah lewat pengajuan perubahan kredit. Pakai "profil kredit", bukan "credit profile"/"setelan kredit" | CR-T1 · kartu pelanggan › Kredit |
| Pengajuan perubahan kredit | Tombol "Ajukan perubahan" · "Ajukan & setujui" · pop-up "Ajukan perubahan kredit" (isian "Alasan pengajuan", "Lampiran (tautan)") · blok "Menunggu keputusan" · tombol "Setujui" / "Tolak" / "Batalkan pengajuan" · "Riwayat perubahan kredit" (kosong: "Belum ada perubahan kredit.") · antrean "Pengajuan perubahan kredit" (Kredit & Plafon) · nomor `{PT}/PKR-NNNNN` · pesan 409 "Masih ada pengajuan perubahan kredit yang menunggu keputusan untuk pelanggan ini." / "Pengajuan ini sudah diputus." / "Profil kredit sudah berubah sejak pengajuan dibuat. Buat pengajuan baru." · 400 "Isian tidak sah: {isian} — {sebab}." / "Alasan pengajuan wajib diisi (minimal 5 huruf)." · 410 "Plafon dan blokir kredit diubah lewat pengajuan perubahan kredit." | Dokumen usulan perubahan profil kredit (nilai lama → baru + alasan) yang diputus pemegang akses memutus pengajuan kredit (bawaan Admin & Manajer; Sales mengajukan saja). Satu pengajuan terbuka per pelanggan per PT; aturan "Ubah profil kredit pelanggan" di Kontrol dua orang menentukan boleh-tidaknya pengaju memutus sendiri | CR-T1 · kartu pelanggan › Kredit, Keuangan › Piutang › Kredit & Plafon |
| Perlakuan (alokasi biaya masuk) | Kolom "Perlakuan" (tabel alokasi voucher biaya masuk) berisi "Persediaan" · "Di makloon" · "Sudah keluar" · baris ringkas "Menambah nilai persediaan", "Menambah nilai barang di makloon", "Dibebankan ke HPP" / "Dicatat sebagai biaya masuk pembelian" · kalimat "Roll yang sudah terkirim ke pelanggan tidak menambah nilai persediaan; bagiannya langsung menjadi beban." · pengaturan "Biaya masuk untuk barang yang sudah terjual" | Ke mana bagian biaya angkut/bea satu roll dibukukan saat voucher disetujui: roll di gudang menambah nilai persediaan, roll di mitra makloon menambah nilai barang di makloon, roll yang sudah terkirim/diretur ke pemasok/dikirim antar-PT langsung menjadi beban (HPP, atau akun biaya masuk pembelian sesuai pengaturan PT). Bukan "treatment"/"HPP baru" | PK-26 · Pembelian › Hutang Pemasok › Landed Cost (HPP), Pengaturan › Aturan Pembelian & Makloon |
| Nilai buku roll | Baris "Nilai buku roll" dan "Selisih terhadap nota" (rincian retur beli yang disetujui) · keterangan "Selisih ini belum masuk jurnal karena akun \"Selisih nilai retur beli\" belum diatur di Pemetaan Akun." · kebutuhan akun "Selisih nilai retur beli" (Pemetaan Akun) | Nilai persediaan roll yang benar-benar keluar = panjang diretur × biaya roll (termasuk biaya masuk). Persediaan dikurangi sebesar nilai ini, bukan sebesar nota debit; beda keduanya (tanpa PPN) masuk akun selisih bila sudah dipetakan untuk PT. Bukan "HPP retur"/"book value" | PK-27 · Pembelian › Retur Beli, Pengaturan › Keuangan & Pajak › Pemetaan Akun |
| Roll berbiaya 0 | Bagian "Roll berbiaya 0" di tab rekonsiliasi persediaan · daftar "Masih di gudang" (Roll, Barang, PT, Sisa, Status) dan "Sudah terkirim" (Surat Jalan, Pesanan, Roll, Panjang, Tanggal) · "Memuat roll berbiaya 0…" · "Tidak ada roll berbiaya 0." | Roll tanpa biaya: di gudang tidak menambah nilai persediaan; yang terkirim keluar dengan HPP 0 (laba kotor terlihat lebih tinggi). Alat menemukan data biaya yang perlu dikoreksi; roll yang sudah dihapus-buku (scrap) tidak termasuk karena memang bernilai 0 | PK-27 · Keuangan › Jurnal & Buku Besar › Rekonsiliasi Persediaan |
| True-up persediaan | Tombol "Posting Saldo Awal" (tab rekonsiliasi persediaan) · dialog "GL Persediaan {PT} akan disamakan dengan nilai fisik roll ({rupiah}), dengan lawan akun Ekuitas Saldo Awal. Jurnalnya nyata dan masuk buku besar." · petunjuk mati "Pilih satu PT untuk memposting saldo awal." · pesan "True-up persediaan hanya untuk pengisian saldo awal. PT {nama} sudah punya transaksi persediaan; …" · pengaturan "True-up persediaan hanya untuk saldo awal" | Jurnal yang menyamakan saldo buku besar persediaan SATU PT dengan nilai roll, berlawan akun Ekuitas Saldo Awal. Hanya untuk pengisian saldo awal (K-06); selisih sesudah PT bertransaksi ditelusuri lewat "Jelaskan selisih" lalu dikoreksi di dokumennya. Bukan "penyesuaian stok" (itu stock opname) | PK-29 · Keuangan › Jurnal & Buku Besar › Rekonsiliasi Persediaan |
| Saldo awal persediaan | Jurnal bersumber "Saldo Awal Persediaan" · "True-up terakhir" · baris rekonsiliasi "Sinkron" / "Tidak sinkron" · banner "{n} PT belum sinkron: {nama PT}. Total selisih mutlak {rupiah}." | Nilai persediaan yang dibukukan saat PT mulai memakai aplikasi (impor stok awal). "Masa saldo awal" = PT belum punya jurnal persediaan selain jurnal saldo awal itu sendiri. "Sinkron" dinilai per PT: PT A lebih dan PT B kurang dengan jumlah sama tetap dua PT belum sinkron | PK-29 · Keuangan › Jurnal & Buku Besar › Rekonsiliasi Persediaan |

### 9.1 Modul akses & aksi pengganti nama peran (PR-T2)

Wewenang yang dulu ditentukan nama peran kini izin yang tampil di **Peran & Hak Akses** (`backend/access_modules.py`).
Label modul/sumber daya/aksi di bawah adalah teks layar editor peran; pesan 403 dipetakan pusat di PR-T6.

| Modul (grup) | Sumber daya — label | Aksi baru (label) |
|---|---|---|
| **Pengawasan Tim Sales & Kredit** (Penjualan) | `sales_force` — "Tim Sales: Target, Insentif & Penugasan"; `credit_override` — "Izin Kredit" | `sales_force.post` "Catat akrual ke buku besar", `sales_force.assign` "Pindahkan pelanggan ke sales lain" |
| **HPP & Margin Produk** (Alat, sensitif) | `costing` — "HPP & Margin Produk" | `view` — juga menentukan kolom biaya/HPP di jawaban server |
| **Beranda Manajer** (Alat) | `manager_home` — "Beranda Manajer" | `view` |
| **Kebersihan Data & Alat Sistem** (Organisasi, sensitif) | `system_tools` — "Kebersihan Data & Alat Sistem" | `configure` "Jalankan & kembalikan pembersihan, lepas kunci proses" |
| **Perangkat RFID & Handheld** (Gudang, sensitif) | `rfid_device` — "Perangkat RFID & Handheld" | `configure` "Daftarkan & atur perangkat", `revoke` "Cabut akses perangkat" |
| **Asisten Tanya KN** (Alat) | `ai` — "Asisten Tanya KN"; `ai_template` — "Templat Laporan Tanya KN" | `view_margin` "Lihat margin & laba kotor", `view_stock_value` "Lihat nilai persediaan", `ai.manage` "Lihat pemakaian & atur aturan asisten", `ai.configure` "Pengaturan teknis asisten & buka riwayat pengguna lain"; satu aksi per templat (label = judul templat) |

Aksi baru pada sumber daya lama: `rnd.manage_org` "Kelola divisi R&D", `rnd.report` "Laporan penilaian desainer & papan
SLA", `rnd.extend_rounds` "Buka ronde di atas batas", `goods_receipt.configure` "Ganti mode penerimaan",
`warehouse.configure` "Ubah struktur & profil gudang", `accounting.reopen` "Buka kembali periode & tembus blokir akun
sementara", `inspection.release` "Lepas / tolak tahanan barang", `product.retire` "Nonaktifkan / hapus permanen master",
`sales_return.treat_cutloss` "Pilih potongan cacat: masuk BS atau dibuang", `od_pricing.unlock` "Buka kunci harga final".
Pengaturan yang digantikan izin ini berstatus "tidak dipakai" dengan alasan "Diatur di Peran & Hak Akses › …"
(`ai.enabled_roles`, `ai.margin_roles`, `ai.stock_value_roles`, `returns.cutloss_treatment_roles`).

**Tingkat akses & modul organisasi (PR-T5).** Satu kamus label (`GET /api/access/labels`, sumber `access_modules.py`)
dipakai editor peran, pesan penolakan, dan jejak audit; perbaikan kata per label di PR-T6.

| Istilah | Teks layar | Arti |
|---|---|---|
| Tingkat akses | **Tidak ada** · **Lihat saja** · **Semua aksi** (dulu "Kelola penuh") | Hanya tingkat yang berlaku untuk modul itu yang ditawarkan. Modul tanpa aksi lihat = sakelar **Mati** · **Nyala** (mis. "Melihat grade, nomor lot & asal barang", "Perangkat RFID & Handheld"); modul yang satu-satunya aksinya lihat tidak punya "Semua aksi" (mis. "Pusat Persetujuan", "Beranda Manajer", "HPP & Margin Produk", "Laporan & Analitik"). Pesan 400: "Tingkat “{tingkat}” tidak berlaku untuk modul “{modul}”." |
| Sebagian | Lencana **"Sebagian ({n} dari {m} aksi)"** di kanan nama modul; tidak ada tombol tingkat yang menyala | Peran memegang sebagian aksi modul (diatur di **"Atur rinci"**, PR-T6; dulu "Menu, tab & aktivitas"). Kartu peran: "{n} semua aksi · {n} sebagian · {n} lihat · {n} tidak ada" |
| Tidak termasuk pada Lihat saja | "Tidak termasuk pada Lihat saja: {halaman}." | Halaman yang tidak punya aksi lihat ikut tercabut pada "Lihat saja" (mis. Periode & Tutup Buku, Amandemen Keuangan, Harga Pesanan Khusus) |
| Aksi berisiko | Ikon peringatan + petunjuk "Peran ini bisa {akibat}." · dialog simpan: "Perhatian — peran ini akan bisa: {akibat}; {akibat}." | Daftar `SENSITIVE_ACTIONS` (membuka periode, membayar pemasok, mengelola akun orang lain, …); hanya peringatan, izin tidak berubah |
| Modul organisasi | **Akun Pengguna** · **Peran & Hak Akses** · **Data PT** (KP-T9; dulu "Badan Usaha (PT)") · **Pusat Pengaturan** · **Penjadwal & Notifikasi Otomatis** | Pengganti modul gabungan "Pengaturan, Pengguna & Hak Akses": memberi "kelola akun" tidak lagi ikut memberi ubah peran, kelola PT, ubah pengaturan, dan penjadwal. Pesan 403 menyebut modul pemilik izinnya, mis. "Minta Admin menambahkan akses 'Pusat Pengaturan'." |

### 9.2 Sifat peran (PR-T4)

Empat hal yang dulu melekat pada nama peran dasar kini isian **Sifat peran** di editor Peran & Hak Akses
(`RoleTraitsPanel.jsx`; disimpan `permission_settings.role_traits`). Isian yang tidak diubah Admin tampil
"Mengikuti {peran dasar}" atau "Mengikuti bawaan sistem".

| Istilah | Teks layar | Arti |
|---|---|---|
| Cakupan data | Label isian **"Data yang terlihat"** · pilihan "Milik sendiri" / "Milik sendiri dan timnya" / "Semua di PT yang boleh dibuka" · keterangan "Berlaku untuk pelanggan, pesanan, pengajuan harga, prospek, pengiriman, dan permintaan desain." | Dokumen ber-pemilik siapa yang terlihat dan bisa diubah pemegang peran, di dalam PT yang boleh dibuka. "Timnya" = akun yang karyawannya berada di unit organisasi yang dikepalai karyawan pelaku. Pesan 403 bila diberi lebih luas: "Anda tidak bisa memberi cakupan data lebih luas dari cakupan peran Anda sendiri." Jangan memakai "scope" / "row-level" di layar |
| Halaman awal | Label **"Halaman awal"** · keterangan "Layar pertama setelah masuk." · pilihan yang izinnya belum dimiliki: "{layar} · Butuh akses yang belum dimiliki peran ini" | Layar pertama setelah masuk. Bila izin layar tersimpan dicabut, akun mendarat di Profil Saya. Pesan 400: "Halaman awal “{layar}” butuh akses yang belum dimiliki peran ini." |
| Kategori kerja | Label **"Kategori kerja"** · pilihan "Tidak ada" / "Sales" / "Sopir" / "Desainer" / "Petugas gudang" / "Pengawas" · kalimat akibat di bawah isian | Jenis pekerjaan pemegang peran: menentukan siapa yang muncul di daftar pilih sales/sopir/desainer, ikut papan peringkat, komisi dan akrual insentif, dibatasi lokasi kerja, dan jenis Meja Saya. Peran tanpa kategori: "Peran Anda belum punya meja kerja. Buka menu yang tersedia di samping." |
| Ikut menerima notifikasi | Label **"Ikut menerima notifikasi untuk"** · keterangan "Notifikasi giliran tetap mengikuti izin." | Notifikasi yang dialamatkan ke peran bawaan yang dicentang ikut sampai ke pemegang peran ini |
| KPI & komisi sales lain | Label aksi "Lihat KPI & komisi sales lain" (modul Pesanan Penjualan) | Izin `order.view_sales_kpi`: memilih sales lain di dasbor Tim Sales. Tanpa izin ini (dan untuk peran bercakupan "milik sendiri") permintaan KPI sales lain menampilkan KPI dirinya |

### 9.3 Bahasa kartu Pengaturan (KF-T4)

Satu istilah untuk teks registry Pengaturan (label, penjelasan, dampak, contoh, pilihan) dan layar `settings-cfg-*` /
"Semua pengaturan". Ditegakkan penjaga `scripts/guardrails/verify_config_text.py` (INV-CFG-TXT, aturan T1–T7, 0
pelanggaran): label ≤ 45 huruf, tanpa label kembar, tanpa kata teknis/id/kode HTTP/kode keputusan, kunci angka
bersatuan, arti angka 0 ditulis, dan kata di kolom "Menggantikan" tidak dipakai (label juga tanpa "ambang", "SJ", "GRN";
frasa yang persis label menu dikecualikan). Singkatan PO, QC, HPP, RFID tetap.

| Dipakai | Menggantikan |
|---|---|
| **PT**; "grup" = semua PT; "Semua PT" · **antar-PT** · **pelanggan** · **pemasok** ("mitra makloon" khusus makloon) · "PO kita" | entitas, badan usaha, perusahaan (badan hukum) · antar entitas · customer, pembeli, toko · supplier, vendor · klien |
| **persetujuan / disetujui** · **penyetuju** · **pengaju** | ACC (kecuali nama status tercetak di layar R&D), approval, disahkan · approver · pengusul |
| **Manajer** · **Admin (Direksi)** saat pertama disebut, lalu "Admin" · **peran** · **bawaan** | manager · Direksi, pemilik, owner · role · default |
| **toleransi** (selisih yang dimaafkan) · **batas** (angka tertinggi/terendah) · "**mulai** (nilai)" untuk persetujuan | ambang |
| **Biarkan / Beri peringatan / Tolak** (atau **Tahan** untuk barang); **ditolak** = aksi dibatalkan, **ditahan** = menunggu keputusan · **aktif / mati** | enam susunan kata lama; blokir, blok keras, block · hidup, nyala, OFF, nonaktif |
| **pesanan** · **PO**, **permintaan pembelian** · **jumlah** | SO, order, Sales Order · Purchase Order, PR, Purchase Requisition · qty |
| **tagihan** · **Faktur Pajak** (hanya pajak) · **kwitansi** · **surat jalan** (ditulis lengkap) · **penerimaan barang** | invoice, bill, faktur (bukan pajak) · SJ · GRN, GR, Barang Masuk (kecuali nama menu) |
| **syarat bayar**; "tempo" = lama kredit · **koreksi dokumen** · **pengembalian dana** · **saldo pelanggan** (nama akun Store Credit tetap, §4.5) · **biaya pokok (HPP)** | term, termin · amandemen · refund · deposit · WAC |
| **peringatan** (muncul saat itu) · **pengingat** (kiriman terjadwal) · "dalam … hari" · **dinaikkan ke atasan** · **tingkat** | warn · jendela, rentang, horizon · eskalasi · jenjang, level |
| **putaran** · **sample** · **departemen** (SDM; "divisi" hanya matriks R&D) · **penggajian / slip gaji** · **stok** / "persediaan" (nilai di pembukuan) · "**dicatat di pembukuan**" · **produk** (master) / **barang** (fisik) | round, ronde · sampel · payroll · jurnal, GL, Dr/Cr, posting · SKU, artikel (di label) |
| **Pengaturan** (menu), **pengaturan** (satu kartu), "Semua pengaturan" · "**Berlaku untuk**" | Pusat Pengaturan, setting, konfigurasi, setelan · cakupan, level, lapisan |

Teks layar baku:

| Istilah | Teks | Arti |
|---|---|---|
| Berlaku untuk | "Semua PT (aturan grup)" / "Satu PT" + "Pilih PT…" · pita "Anda sedang mengubah aturan grup — berlaku untuk semua PT yang tidak punya nilai sendiri." / "Anda sedang mengubah nilai khusus {PT}. PT lain tidak terpengaruh." / "Pilih PT dulu supaya perubahan tersimpan pada PT yang benar." | Lapisan yang diubah. Pada aturan grup kartu menampilkan nilai grup dan "PT dengan nilai sendiri: {PT} = {nilai}" |
| Asal nilai | lencana "Bawaan sistem" · "Aturan grup" · "Khusus {nama PT}" · "Mengikuti nilai grup" | Dari mana nilai yang berlaku datang |
| Ikuti nilai grup | tombol "Ikuti nilai grup" · dialog "'{label}' untuk {PT} kembali mengikuti nilai grup ({nilai grup}). Nilai khusus {PT} ({nilai sekarang}) dicabut." | Mencabut nilai khusus PT (`POST /api/config/values/clear`); alasan bawaan "Kembali mengikuti nilai grup" |
| Pakai nilai bawaan sistem | "Pakai nilai bawaan sistem" (aturan grup) / "Pakai nilai bawaan sistem untuk PT ini" · dialog menyebut nilai bawaan dan akibatnya | Menulis nilai bawaan pada lapisan itu (`/values/reset`); untuk PT, PT itu tidak lagi mengikuti grup. Alasan bawaan "Dikembalikan ke nilai bawaan sistem". Kunci berisiko tinggi tanpa alasan → "'{label}' berisiko tinggi — alasan wajib diisi." Jangan menulis "Default" |
| Lanjutan (teknis) | blok tertutup "Lanjutan (teknis): {sub-judul}" · tombol kartu "Detail teknis" | Sub-judul `advanced` (model & anggaran AI, baca surat jalan otomatis, RFID & proses macet) dan kunci/berkas pemakai |
| Kesehatan Pengaturan | tab "Kesehatan Pengaturan" · kolom "Tersambung ke sistem?" | Pengganti "Kesehatan Konfigurasi", "Status wiring" |
### 9.3 Peran dasar, ringkasan peran, dan pesan penolakan (PR-T6)

| Istilah | Teks layar | Arti |
|---|---|---|
| Peran dasar | Isian **"Peran dasar"** (hanya peran kustom; pilihan "Tanpa peran dasar" + peran bawaan selain Admin) · keterangan "Menentukan nilai awal halaman awal, data yang terlihat, kategori kerja, dan menu warisan. Tidak menyalin hak akses." · konfirmasi "Ganti peran dasar ke {peran}?" | Sumber nilai awal sifat peran dan menu warisan; bisa diganti kapan saja tanpa mengubah izin. Lintas PT tidak ikut berganti. Pengganti istilah lama **"peran acuan"** / **"template"**. Pesan 400: "Peran dasar hanya bisa diatur pada peran kustom." · "Peran Admin tidak bisa dijadikan peran dasar." · "Peran dasar tidak dikenal." |
| Salin hak akses dari… | Isian **"Salin hak akses dari…"** · keterangan "Hanya menyalin centang; boleh diubah setelahnya." | Menyalin centang izin peran lain ke peran yang sedang disunting; tidak mengubah peran dasar maupun lintas PT |
| Ringkasan peran | Panel **"Ringkasan peran"** di editor: "Halaman awal: …" · "Data yang terlihat: …" · "Kategori kerja: …" · "PT: semua PT aktif" / "PT: hanya yang ditugaskan per akun" · "Batas persetujuan: {jenis dokumen} — {jenjang}, sampai Rp … / tanpa batas" atau "Mengikuti tingkat {peran}; diatur di Aturan Persetujuan." · "**{modul}** — {halaman}: bisa {aksi}; tidak bisa {aksi}." · "Perhatian — peran ini bisa: …" · "Mengikuti peran dasar: …" | Jawaban "peran ini akhirnya bisa apa" sebelum disimpan (`POST /api/access/roles/preview` → `summary`; `GET /api/access/roles/{id}/summary`). Formulir akun menampilkan versi pendeknya + tautan **"Lihat hak peran ini"** |
| Mode baca | Judul **"Lihat Hak Akses · {peran}"** · tombol **"Tutup"** | Pemegang `permission.view` tanpa `permission.update`: semua isian mati, tanpa simpan, hapus, kembalikan, dan pindah akun |
| Riwayat peran | Tab **"Riwayat"** di editor: Waktu (WIB) · Oleh · Perubahan · Akun terdampak; kosong "Belum ada perubahan tercatat." | Dari jejak audit (`role_access_updated`, `role_access_reset`, `custom_role_created` "Peran dibuat", `custom_role_deleted` "Peran dihapus", `role_users_moved` "Akun dipindahkan ke peran lain") |
| Tinjau penugasan PT | Dialog **"Tinjau penugasan PT"** + tombol **"Buka Akun & Akses"** | Sesudah lintas PT sebuah peran dimatikan: akun peran itu yang masih ditugaskan ke lebih dari satu PT. Penugasan tidak diubah otomatis |
| Pesan penolakan (Z6) | "Anda belum punya akses untuk {melihat/membuat/mengubah/menghapus/menyetujui/menolak/mencatat ke buku besar/membayar/membatalkan/mengekspor/mengatur/melepas} {halaman}. Minta Admin menambahkan akses '{modul}'." · aksi lain: "… untuk melakukan “{aksi}” pada {halaman}. …" · beberapa izin: "Anda belum punya akses ke layar ini. Minta Admin menambahkan salah satu akses: '{modul}', '{modul}'." | Pengganti "Permission ditolak: x.y" (`dependencies.denied_message`). Kode izin hanya di header `X-Permission-Denied` untuk alat uji |
| Peran berubah | Pemberitahuan "Peran Anda berubah menjadi {peran}." · alasan cabut sesi "peran berubah" (dulu "role berubah") | Peran akun diganti di tengah sesi → layar pindah ke halaman awal peran baru |

Label kamus server yang diganti (lampiran B §7): halaman `marketing` "Marketing & Sosial Media" (dulu "Pemasaran"),
`goods_receipt` "Kedatangan Barang" (dulu "… (GRN)"), `internal_request` "Permintaan Internal Antar PT" (dulu "… (PIN)"),
`sample_order` "Pesanan Sample" (dulu "… (SOS)"), `rfq` "Permintaan Penawaran Harga" (dulu "RFQ / Penawaran"),
`landed_cost` "Biaya Masuk Barang" (dulu "Landed Cost"), `wms` "Operasi Gudang" (dulu "… (WMS)"); aksi `close` "Tutup
penerimaan", `count` "Hitung fisik", `review` "Periksa hasil hitung", `set` "Tetapkan harga internal", `pegging` "Kaitkan
stok ke pesanan", `dispatch` "Berangkatkan kiriman", `generate` "Buat label", `void` "Batalkan (void)", `override` "Ubah
pesanan yang sudah terkunci", `hold` "Tahan", `random_check` "Cek acak", `scan` "Pindai", `manage_bom` "Kelola resep
produksi", `manage_payroll` "Kelola gaji", `release` "Lepas / rilis"; modul `warehouse_ops` "Operasi Gudang", `rnd`
"Pengembangan Produk & Sample", `petty_cash` "Kas Kecil (pengajuan dana & pertanggungjawaban)". Teks tombol editor
"Menu, tab & aktivitas" → **"Atur rinci"**.

### 9.4 Menu keuangan & SDM (MN-T1)

Label menu dan tab baru sesudah penggabungan menu (`docs/blueprint/unit/MN-T1.md`; susunan lengkap: KN_13 bagian
"MENU KEUANGAN, AKUNTANSI & PAJAK, DAN SDM"). Istilah baku tetap: **PT** (bukan "Entitas"/"Badan Usaha" di menu
keuangan — "Antar Entitas (Grup)" → **Antar-PT**) dan **pemasok** (bukan "supplier" — "Tagihan Supplier" → **Tagihan**
di bawah menu **Hutang**; label izin server `vendor_bill` tetap "Tagihan Supplier" sampai kamus izin diganti).

| Label baru | Dulu | Tempat |
|---|---|---|
| **Beranda Keuangan** › **Perlu Tindakan** · **Posisi** · **Analisis** | Dasbor Keuangan (Posisi & Kontrol · BI Keuangan) + menu lepas "Meja Finance" | Keuangan |
| **Piutang** › **Saldo & Umur** · **Penagihan & Penerimaan** · **Rencana & Denda** · **Titipan & Saldo Kredit** · **Kredit & Plafon** · **Kasus** | Piutang, sub-tab CRM "Penagihan" & "Persetujuan Kredit", Rencana Bayar, Uang Muka Pelanggan, Saldo Kredit, Kasus Keuangan | Keuangan |
| Chip **Titipan pelanggan** · **Saldo kredit** | menu "Uang Muka Pelanggan" · "Saldo Kredit" | Piutang › Titipan & Saldo Kredit |
| **Hutang** › **Tagihan** · **Kontrabon** | Pembelian › Hutang Pemasok › Tagihan Supplier · Kontrabon (Tukar Faktur) | Keuangan |
| **Kas & Bank** › … · **Rekonsiliasi** · **Kas Kecil** | Rekonsiliasi Bank; Kas & Aset › Kas Kecil | Keuangan |
| Chip **Pengajuan dana** · **Pertanggungjawaban** · **Hutang reimburse** | tab Pengajuan Dana (PD) · Pertanggungjawaban · Hutang Reimburse | Kas & Bank › Kas Kecil |
| **Antar-PT** | Antar Entitas (Grup) | Keuangan |
| **Buku Besar** › **Jurnal** · **Bagan Akun** | Jurnal & Buku Besar · Chart of Accounts | Akuntansi & Pajak |
| **Tutup Buku** › **Daftar Periksa & Tutup** · **Buka Periode** · **Posting Gagal** | tiga entri terpisah | Akuntansi & Pajak |
| **Laporan** › … · **Profitabilitas** · **Proyeksi Kas** · **Anggaran** · **Konsolidasi** | Profitabilitas & Margin · Proyeksi Arus Kas · Anggaran vs Realisasi · Konsolidasi Grup | Akuntansi & Pajak |
| **Pajak** › … · **PPN & PPh** | Pajak (PPN & PPh) | Akuntansi & Pajak |
| **Penggajian** › **Proses Gaji** | Payroll Run | SDM |
| **Kinerja & Insentif** › **Kinerja Sales** · **Target & Aturan** · **Skema (Arsip)** · **KPI Karyawan** | SDM › KPI (KPI Karyawan (manual)); sub-tab CRM "Kinerja Sales" & "Skema (Arsip)"; Pengaturan › Penjualan › Komisi & Insentif | SDM |

Nama lama tetap bisa dicari di palet Ctrl+K ("{nama lama} → kini di {menu} › {tab}", `config/viewAliases.js`).
Jangan memakai "Dashboard", "BI", "Payroll Run", "Chart of Accounts", "Store Credit" pada label menu baru.

### 9.5 Menu Pengaturan sembilan hub & satu istilah "PT" (KP-T9)

Susunan lengkap: KN_13 bagian "MENU PENGATURAN (KP-T9)". Istilah baku **PT** di tiga berkas menu (`navStructure.js`,
`hubTabs.js`, `navMeta.js` — dijaga `scripts/check_nav_map.py` CHECK 6), katalog modul akses, dan pemilih PT; satu-satunya
pengecualian nama hub **"Perusahaan (PT)"**. Teks letak di layar ditulis "Pengaturan › {hub} › {tab}".

| Label baru | Dulu | Tempat |
|---|---|---|
| **Perusahaan (PT)** › **Profil PT** · **Kesiapan PT** · **Master per PT** | Perusahaan & Akun › Badan Usaha & Akses (tab dalam Badan Usaha, Kesiapan) · Master Data › Master per Badan Usaha | Pengaturan |
| **Pengguna & Hak Akses** › **Akun** · **Peran & Hak Akses** · **Cek Peran** | tab dalam Badan Usaha & Akses (Akun & Akses, Peran & Hak Akses, Cek Peran) | Pengaturan |
| **Persetujuan** › … · **Persetujuan R&D** | Divisi & Persetujuan R&D | Pengaturan |
| **Penjualan** › … · **Alasan Koreksi** | Label Alasan Amandemen | Pengaturan |
| **Gudang, Pembelian & Produksi** › … · **Penerimaan Barang** · **Grade Mutu** · **Aturan Pembelian & Makloon** · **R&D & Desain** | Gudang & Mutu (Penerimaan & OCR, Master Grade Mutu) · hub Pembelian & Produksi · hub R&D | Pengaturan |
| **Keuangan & Pajak** › … · **Bank** | Aturan & Template Bank | Pengaturan |
| **SDM** › **Aturan SDM & Penggajian** · **Shift & Lokasi Absen** · **Mesin Absen** | SDM & Penggajian · Shift & Geofence · Integrasi & Sistem › Perangkat (tab dalam Mesin absen) | Pengaturan |
| **Dokumen & Notifikasi** › **Template Dokumen** · **Pengingat Otomatis** · **WhatsApp** · **Penomoran Dokumen** | Dokumen & Cetak · Notifikasi & Penjadwal › Penjadwal & Notifikasi (tab dalam Job/Riwayat, WhatsApp) | Pengaturan |
| **Sistem** › **Integrasi & Audit** · **Perangkat RFID** · **Kamus Aturan Kain** · **Impor Data Awal** · **AI & Tampilan** · **Cari Semua Pengaturan** | Integrasi & Sistem (Perangkat, Semua pengaturan) · Master Data (Registri Domain, Impor Dataset Klien) | Pengaturan |
| **Semua PT** (pemilih PT, mode hanya lihat) · teks cadangan **PT** | "Semua Entitas" · "Badan usaha" | kepala aplikasi |
| **Transaksi Antar-PT** · **Data PT** · sumber daya izin **PT** | "Transaksi Antar Badan Usaha" · "Badan Usaha (PT)" · "Badan Usaha" | katalog modul akses (editor peran, pesan 403) |
| **Harga per PT** · **Transfer Antar-PT** · **Akun Sosmed · per PT** · kicker **Antar-PT** | Harga per Badan Usaha · Transfer Antar-Entitas · … per Badan Usaha · Antar Entitas | menu & judul halaman |

Nama hub/tab lama tetap bisa dicari di palet Ctrl+K: "Badan Usaha & Akses", "Pembelian & Produksi", "Master Data",
"Notifikasi & Penjadwal" (`config/viewAliases.js`, `since: "KP-T9"`). Kata "entitas"/"badan usaha" **di dalam** layar
(selain menu dan pemilih PT) diganti unit pemilik layarnya.

### 9.6 Nama dokumen & panel relasi (PK-44)

Satu dokumen satu nama — di peta Jejak Dokumen (`services/doc_refs_service.py::DOC_TYPES`), bilah aksi dokumen, dan teks
baru. Menu & layar lain yang masih memakai nama lama diganti unit pemilik layarnya (MN-T1 untuk menu).

| Istilah | Teks | Arti · bedakan dari | Unit · tempat |
|---|---|---|---|
| Tagihan Pemasok | "Tagihan Pemasok" | Faktur/tagihan yang diterima dari pemasok dan menjadi hutang usaha (`vendor_bill`). Jangan memakai "Tagihan Supplier", "Vendor Bill", "Faktur Supplier" pada teks baru | PK-44 · Jejak Dokumen, bilah aksi rincian tagihan |
| Kontrabon | "Kontrabon (Tukar Faktur)" | Dokumen tukar faktur: banyak tagihan pemasok satu siklus digabung jadi satu tanda terima dan satu pembayaran. **Bukan** tagihan — jangan menulis "Tagihan … (Kontrabon)" | PK-44 · Jejak Dokumen, Hutang › Kontrabon |
| Uang Muka Pelanggan | "Titipan pelanggan" / "Uang Muka Pelanggan" | Uang PELANGGAN yang diterima lebih dulu (titipan, belum dialokasikan ke tagihan). Bedakan dari Pengajuan Dana (PD) | PK-44 · Piutang › Titipan & Saldo Kredit |
| Pengajuan Dana (PD) · Pertanggungjawaban Dana (LPJ) | "Pengajuan Dana (PD)" · "Pertanggungjawaban Dana (LPJ)" | Kasbon KARYAWAN (uang perusahaan yang dicairkan ke karyawan) dan laporan pemakaiannya. LPJ selalu berinduk PD. Bedakan dari Uang Muka Pelanggan | PK-44 · Jejak Dokumen, Kas & Bank › Kas Kecil |
| Pengembalian sisa (uang muka) | Ringkasan LPJ "Sisa Harus Dikembalikan" (sisa terbuka) · "Sisa Dikembalikan · {nomor kas}" (sudah diterima) · "Sisa Uang Muka" (LPJ belum disetujui) · "Kekurangan Dana" · tombol & pop-up "Terima Pengembalian Sisa {rupiah}" (Jenis kas · Rekening · Tanggal) · konfirmasi "Terima {rupiah} dari {karyawan} ke {rekening} · {PT}?" · pesan "LPJ {nomor} tidak punya sisa uang muka yang belum dikembalikan." | Uang muka KARYAWAN yang tidak terpakai dan dikembalikan ke kas perusahaan sesudah LPJ disetujui (kas masuk, menutup uang muka PD sampai nol). **Bukan** "pengembalian dana" (refund ke pelanggan/antar-PT) dan bukan hutang reimburse (kelebihan pengeluaran yang dibayar ke karyawan) | PK-24 · Kas & Bank › Kas Kecil |
| LPJ terkunci · Perbaiki & Ajukan Lagi | 409 "LPJ {nomor} sudah diajukan, jadi isinya tidak bisa diubah. Minta penyetuju menolaknya bila perlu diperbaiki." · 409 "LPJ {nomor} belum diajukan." · tombol "Perbaiki & Ajukan Lagi" (LPJ ditolak, hanya pembuatnya) · status "Menunggu jurnal" (disetujui, jurnal belum terbit) · 400 "Lampirkan minimal satu bukti pengeluaran sebelum mengajukan LPJ." | Isi & lampiran LPJ hanya bisa diubah selagi draf; LPJ yang ditolak dibuka lagi oleh pembuatnya | PK-24 · Kas Kecil › Pertanggungjawaban |
| Pelunasan Antar-PT | "Pelunasan Antar-PT" | Dokumen pelunasan saldo antar-PT (termasuk saling hapus). Jangan memakai "Settlement Antar-PT (Netting)" pada teks baru | PK-44 · Jejak Dokumen, Antar-PT |
| Dokumen Terkait | Judul panel "Dokumen Terkait" · tombol "Lihat seluruh jejak" · tombol "Buka" · "Tanpa akses lihat" · garis tahapan ("{tahap} · {n}" / "{tahap} · belum") | Satu-satunya panel relasi di rincian dokumen: dokumen asal ("Berasal dari") dan turunan ("Menurunkan"), plus garis tahapan pesanan/PO. "Tanpa akses lihat" = peran tidak memegang izin lihat modul dokumen itu (PK-17) | PK-44 · rincian pesanan, PO, tagihan pemasok, kontrabon, penerimaan barang |
| Cetak Dokumen | Judul panel "Cetak Dokumen · …" | Daftar dokumen cetak turunan (surat pengambilan, daftar kemasan, surat jalan, bukti terima). Bukan panel relasi | PK-44 · rincian pesanan & PO |
| Kembali ke … | Bilah "← Kembali ke {layar asal}" (mis. "Kembali ke Jejak Dokumen", "Kembali ke Dasbor Keuangan") | Muncul sesudah melompat ke dokumen dari Jejak Dokumen, panel Dokumen Terkait, atau kartu angka; membawa kembali ke layar asal (jejak yang sama). Hilang saat memilih menu lain | PK-44 · semua layar tujuan tautan dokumen |
| Dokumen tidak ditemukan | "Dokumen {nomor} tidak ditemukan di PT ini." | Tautan dokumen menunjuk dokumen yang tidak ada atau di luar PT aktif; layar tujuan menulis ini (bukan layar kosong) | PK-44 · layar tujuan tautan dokumen |

### 9.7 Pajak keluaran: aturan pajak per PT dan data pajak pelanggan (TX-T1)

Istilah layar Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak (sub-judul Pajak), form pelanggan (bagian "Data pajak"), checkout, Faktur Keluaran, dan detail pesanan
(`docs/blueprint/unit/TX-T1.md`, K-33). Hal peraturan (faktor, daftar kode) menunggu konfirmasi konsultan pajak.

| Istilah | Teks layar | Arti |
|---|---|---|
| **DPP nilai lain** | "Pakai DPP nilai lain" · "Faktor DPP nilai lain — pembilang / penyebut" · baris rincian "DPP nilai lain (11/12)" | Dasar pengenaan pajak = pecahan × harga jual (bawaan 11/12, sehingga PPN efektif 11 % walau tarif 12 %). Pecahan ditulis dari aturan dokumennya, bukan dari pengaturan hari ini. Jangan menulis "DPP Nilai Lain" berhuruf besar di label baru |
| **kode transaksi** | "Kode transaksi faktur yang dipakai" · "Kode transaksi bawaan" · "Kode transaksi bawaan saat DPP nilai lain" · pilihan "Ikut PT" di data pelanggan · galat "Kode transaksi {kode} tidak dipakai PT ini." | Dua angka di depan nomor seri Faktur Pajak (01, 04, …). Daftar per PT; bawaan faktur = kode pelanggan, lalu bawaan PT menurut DPP nilai lain |
| **aturan pajak saat terbit** | Rincian faktur "Aturan pajak saat terbit" (tarif, DPP nilai lain, pembulatan, harga, "Aturan berlaku pada") · detail pesanan "Aturan pajak: …" · faktur lama "Faktur ini terbit sebelum aturan pajak disimpan bersama faktur: …" | Potret aturan yang dipakai saat dokumen dibuat. Mengubah atau menjadwalkan pengaturan pajak tidak mengubah dokumen yang sudah ada |
| **pembulatan PPN** | "PPN dibulatkan per" [Per dokumen · Per baris] · "PPN dibulatkan ke" [Dua angka di belakang koma · Rupiah penuh] | Per dokumen = dari total; per baris = tiap baris lalu dijumlah |
| **Data pajak** (pelanggan) | "Identitas pajak" [NPWP · NIK] · "Nama di faktur pajak" · "Alamat di faktur pajak" · "Status PKP pelanggan" [Belum diisi · PKP · Bukan PKP] · "Selalu minta faktur pajak" · peringatan "{NPWP/NIK} berisi {n} angka; biasanya … angka." | NPWP tetap disimpan di data pelanggan; nama/alamat kosong = nama toko dan alamat utama. Peringatan bentuk tidak menghalangi simpan |
| **Data pajak belum lengkap** | lencana ikon + "Data pajak belum lengkap" · "Identitas pajak (NPWP/NIK) belum diisi" · "Alamat pajak belum diisi" | Faktur tetap terbit; kekurangan ditandai di faktur |
| **Pesanan tanpa PPN** | sakelar "Pesanan tanpa PPN" + isian wajib "Alasan tanpa PPN" (checkout) · detail pesanan "Pesanan tanpa PPN — dibuat {nama}. Alasan: …" | Hanya pemegang akses pesanan tanpa PPN di PT PKP; alasan minimal 10 huruf |
| **belum dipakai mesin** | lencana di form produk: "Perlakuan PPN" [Kena PPN · Dibebaskan · Tidak dipungut] · "Kode barang pajak" | Disimpan untuk persiapan; PPN per barang belum dihitung (L5) |

### 9.8 Asisten Keuangan di Tanya KN (AG-T2, AG-T3)

Istilah mode Keuangan di Tanya KN, sakelar akun di Pengaturan › Akun & Akses, dan pengaturan penyamaran nama
(`docs/blueprint/unit/AG-T2.md`, K-15, K-43, K-45).

| Istilah | Teks layar | Arti |
|---|---|---|
| **Asisten Keuangan** | pilihan Mode "Umum" · "Keuangan" di kotak tanya · kicker jawaban "Asisten Keuangan" · sakelar akun "Asisten Keuangan" + "Mati = akun ini tidak bisa bertanya soal keuangan lewat Tanya KN." · akses peran "Asisten Keuangan" ("Bertanya soal keuangan lewat Tanya KN") | Mode Tanya KN yang menjawab soal jurnal, laporan keuangan, piutang, hutang, kas, periode, antar-PT, pajak, dan anggaran dengan membaca layar yang sama dengan pengguna. Butuh akses peran **dan** sakelar akun yang dinyalakan pemilik |
| **Menjawab untuk** | banner "Menjawab untuk: {nama PT}" · gabungan "Semua PT — angka gabungan belum dieliminasi" | PT yang angkanya dipakai jawaban (PT aktif di kepala aplikasi). Pada Semua PT angkanya penjumlahan tanpa eliminasi antar-PT (K-15) |
| **Memeriksa angka** | status "Memeriksa angka…" · lencana "Angka diperiksa: semua cocok dengan data" / "Angka tidak bisa dipastikan" · kalimat "Saya tidak bisa memastikan angka untuk pertanyaan ini. Data yang berhasil diambil ada di tabel di bawah." | Jawaban mode Keuangan baru ditampilkan sesudah setiap angkanya cocok dengan data yang diambil; bila tetap tidak cocok, teks diganti kalimat baku dan tabel datanya tetap tampil |
| **Sumber** | bagian "Sumber": "{judul} · {PT} · {periode}", catatan di bawahnya, tombol "Buka di layar" | Data yang dipakai jawaban, disusun server (bukan ditulis asisten); tombol membuka layar laporannya |
| **Samarkan nama pihak** | pengaturan "Samarkan nama pihak yang dikirim ke asisten" | Nama pelanggan, pemasok, dan karyawan diganti kode (mis. "PLG-001") sebelum dikirim ke penyedia model, lalu dikembalikan ke nama asli di layar. Nominal dan nama PT tetap dikirim. Diatur per PT |
| **Paket tutup buku** | kartu "Paket tutup buku" (grup Keuangan tab Laporan) · "Bulan" · tombol "Buat paket" · "Menyusun paket… (i dari 12)" · lembar "Disertakan" / "Tidak disertakan — {alasan}" · "Unduh Excel" (AG-T4) | Satu berkas Excel satu bulan untuk satu PT: laporan utama, umur piutang dan hutang, pencocokan, antar-PT, kas & bank, posting gagal, jurnal manual, status periode — angka sama dengan layarnya. Lembar yang layarnya tidak boleh Anda buka ditulis "Tidak disertakan" |
| **Pencocokan** | lembar "Pencocokan": kolom "Hal" · "Buku besar" · "Buku pembantu" · "Selisih" · "Akun kontrol belum dipetakan" (AG-T4) | Saldo akun kontrol buku besar dibanding total buku pembantunya (umur piutang, umur hutang, nilai roll); selisih dihitung sistem |
| **Ringkasan pagi keuangan** | tombol "Jadwalkan ringkasan pagi keuangan" · isian "Jam kirim (WIB)" · baris jadwal "Ringkasan pagi keuangan · {nama PT}" (AG-T4) | Notifikasi harian satu PT: piutang dan hutang yang jatuh tempo hari itu, uang masuk yang belum cocok dengan bank, posting gagal, dan selisih rekonsiliasi |
| **kartu tindakan** | kepala "Kartu tindakan · {tindakan}" · baris "PT: {nama PT} · berlaku sampai {tanggal, jam} WIB" · tabel "Rencana" ("Hal" · "Sekarang" · "Sesudah") · "Jurnal dibuat sistem saat disimpan." · isian "Alasan" ("Mengapa tindakan ini dilakukan?") dan "Ketik ulang nominal" · tombol "Setujui dan jalankan" / "Abaikan" · pop-up "Jalankan {tindakan} sebesar Rp {nominal} untuk {nama PT}?" ("Ya, jalankan" · "Batal") · hasil "Berhasil — {jenis dokumen} {nomor}", "Jurnal: terposting" / "Jurnal gagal — lihat Posting Gagal", "Gagal: {pesan}", "Kedaluwarsa", "Diganti kartu yang lebih baru", "Diabaikan" · status Menunggu · Sedang diproses · Berhasil · Gagal · Diabaikan · Kedaluwarsa · Diganti (AG-T3) | Rencana tindakan yang disiapkan asisten (tindak lanjut penagihan, janji bayar, tanda sudah diingatkan, kwitansi, pencocokan mutasi bank, alokasi titipan, ulang jurnal gagal). Tidak ada yang tertulis sebelum pengguna menyetujui kartunya; sesudah disetujui, kartu menjalankan tombol layar yang sama dengan izin pengguna, tepat sekali. Kartu baru di percakapan yang sama menggantikan kartu yang belum disetujui |
| **Tindakan** (tab Tanya KN) | tab "Tindakan" · saringan "Menunggu saya" · "Menunggu orang lain" · "Selesai" · "Gagal" · kolom "Tindakan" · "PT" · "Nominal" · "Dibuat" · "Berlaku sampai" · "Status" · "Belum ada kartu tindakan." (AG-T3) | Daftar kartu tindakan milik Anda. "Menunggu orang lain" = kartu uang keluar yang menunggu persetujuan orang kedua di PT aktif (AG-T5) |
| **tindakan uang masuk** | pengaturan "Izinkan asisten mencatat uang masuk" · "Batas kartu disetujui per orang per hari" · sakelar akun "Boleh menyetujui kartu uang masuk" · akses peran "Siapkan dan setujui tindakan" · galat "Tindakan uang masuk lewat asisten belum dinyalakan untuk akun Anda." / "…untuk {nama PT}." (AG-T3) | Kartu golongan uang masuk (kwitansi, pencocokan bank, alokasi titipan, ulang jurnal gagal) butuh tiga hal: akses peran, sakelar akun, dan pengaturan PT yang menyala (bawaan mati) |
| **Tanya soal layar ini** | tombol "Tanya soal layar ini" di rincian jurnal (Buku Besar), rincian piutang pelanggan, Tutup Buku; "Tanya asisten" di baris mutasi Kas & Bank (AG-T3) | Membuka Tanya KN mode Keuangan dengan konteks layar itu; tampil bila akun punya akses Asisten Keuangan |

### 9.9 Sisa GR/IR, selisih harga faktur, dan kliring (PK-28)

Istilah tab Keuangan › Hutang › GR/IR (Diterima Belum Ditagih), rincian tagihan pemasok, dan rekonsiliasi tutup-kurang PO
(`docs/blueprint/unit/PK-28.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **GR/IR** | Tab "GR/IR (Diterima Belum Ditagih)" · kolom "Sisa GR/IR" · kaki tabel "Total sisa GR/IR" dan "Saldo akun GR/IR di buku besar" | Akun "Barang diterima belum ditagih" (2-1150): naik saat barang PO diterima, turun saat pemasok menagih atau barang diretur sebelum ditagih. Sisa positif = barang sudah diterima, faktur belum datang; sisa negatif = sudah ditagih lebih dari nilai terima. Singkatan dipertahankan (bahasa kerja keuangan), selalu bersama penjelasnya |
| **kliring** (GR/IR) | Tombol "Kliring" · dialog "Kliring sisa GR/IR?" · isian wajib "Alasan" · tindak lanjut tutup-kurang "Sisa GR/IR PO ini tidak akan tertagih — kliring di Keuangan › Hutang › GR/IR." | Memindahkan sisa GR/IR satu PO yang tidak akan tertagih ke akun selisih harga pembelian; menerbitkan jurnal. Hanya untuk PO yang sudah selesai, ditutup-kurang, atau dibatalkan. Bukan pembatalan faktur dan bukan pembayaran |
| **selisih harga pembelian** | Pemetaan Akun "Selisih harga pembelian" · rincian faktur "Selisih harga terhadap PO" · "Selisih ini masih berada di akun GR/IR karena akun "Selisih harga pembelian" belum diatur di Pemetaan Akun." | Neto faktur pemasok dikurangi nilai GR/IR menurut harga neto baris PO (positif = faktur lebih mahal). Akunnya dipilih pemilik; selama belum dipilih, selisih tetap di GR/IR |
| **jurnal tidak terhubung ke PO** | Kaki tabel merah "Rp {nominal} berasal dari jurnal yang tidak terhubung ke PO." | Bagian saldo akun GR/IR yang bukan dari penerimaan/tagihan/retur/kliring sebuah PO (mis. jurnal manual, potongan kontrabon) |

### 9.10 Aset tetap: sumber dana, pindah antar-PT, penyusutan (PK-23)

Istilah form **Tambah Aset Tetap**, daftar aset, dan Posting Gagal (`docs/blueprint/unit/PK-23.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **sumber dana** (perolehan aset) | Isian wajib "Sumber Dana *" tanpa bawaan: "Dibayar dari kas/bank" · "Dibeli secara hutang" · "Saldo awal (aset lama)"; pilihan mati berketerangan "Akun lawannya belum ditetapkan di Pemetaan Akun."; pesan 400 "Pilih sumber dana perolehan aset." · 409 "Sumber dana \"{label}\" belum bisa dipakai karena akun lawannya belum ditetapkan di Pemetaan Akun." · keterangan form "Perolehan dijurnal otomatis: debit akun aset, kredit sesuai sumber dana." | Dari mana harga perolehan aset dibayar; menentukan akun kredit jurnal perolehan (kas: akun kas rekening terpilih + kas keluar di rekening itu; hutang/saldo awal: akun Pemetaan Akun "Lawan perolehan aset yang dibeli secara hutang" / "Lawan aset lama yang dicatat sebagai saldo awal", hidup sesudah pemetaannya disimpan). Bukan "funding" dan bukan "akun kredit" |
| **Sedang Dipindah / Sedang Dilepas** | Status aset "Sedang Dipindah" · "Sedang Dilepas"; pesan 409 "Aset {nomor} sedang diproses. Muat ulang." | Pindah antar-PT atau pelepasan yang sudah diklaim tetapi belum selesai (mis. jurnal salah satu PT belum terbit). Aset tidak bisa diubah, disusutkan, dilepas, atau dipindah lagi sampai selesai; Ulang Posting meneruskannya |
| **sudah dipindahkan** | Status "Pindah PT" · keterangan tombol mati "Aset ini sudah dipindahkan ke {PT}." · pesan 409 "Aset {nomor} sudah dipindahkan ke {PT}, jadi tidak bisa diubah, disusutkan, atau dilepas di sini." | Hak atas aset sudah berpindah ke PT lain; yang aktif adalah aset penggantinya di PT itu |
| **belum berjurnal perolehan** | Pesan 409 "Aset {nomor} belum punya jurnal perolehan. Ulangi posting di Posting Gagal dulu." · alasan lewat penyusutan "belum berjurnal perolehan" · keterangan tombol mati "Jurnal perolehan belum terbit — ulangi di Keuangan › Posting Gagal." | Aset tersimpan tetapi jurnal perolehannya gagal/diproses; tidak disusutkan, dilepas, atau dipindah sampai jurnalnya terbit |
| **Penyusutan Aset / Pelepasan Aset / Pindah Aset Antar-PT / Bayar Pindah Aset** (Posting Gagal) | Jenis di panel Posting Gagal | Entri penyusutan per aset & periode, pelepasan yang macet, sisi pengirim jurnal pindah aset, dan dua sisi jurnal pembayarannya yang belum terbit — Ulang Posting menerbitkan yang kurang tepat sekali |

### 9.11 Penggajian: hitung ulang, batal, anulir, setoran kewajiban (PK-22)

Istilah SDM › Penggajian (`docs/blueprint/unit/PK-22.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **setoran kewajiban** | Tab "Setoran Kewajiban" · tombol "Catat Setoran" · kartu "Kewajiban · Sudah disetor · Sisa" | Pembayaran hutang BPJS dan PPh 21 yang dipotong/ditanggung dari gaji suatu masa ke BPJS atau kas negara. Satu setoran = satu kas keluar (rekening wajib) yang mengurangi hutangnya; tanggal setor = tanggal jurnal. Batasnya sisa kewajiban masa itu |
| **hitung ulang** (penggajian) | Tombol "Hitung Ulang" (draf) · "Dihitung ulang {n}×" | Slip gaji draf dihitung lagi dari data karyawan, lembur, dan komisi terbaru; nomor slip tetap |
| **batalkan** (penggajian) | Tombol "Batalkan" · lencana "Dibatalkan" | Membatalkan penggajian yang belum diposting (draf, diajukan, disahkan) beserta slipnya; tanpa jurnal. Proses baru periode itu boleh dibuat |
| **anulir** (penggajian) | Tombol "Anulir" · lencana "Dianulir" | Membatalkan penggajian yang sudah diposting dengan membalik jurnal gajinya (bertanggal sama dengan jurnal asal). Gaji yang sudah dibayar tidak bisa dianulir (koreksi lewat proses susulan) |
| **tanggal buku** (jurnal periodik) | "Jurnal gaji: … · tanggal buku 31 Okt 2026" · pengaturan "Tanggal jurnal gaji, penyusutan, dan insentif" | Tanggal jurnal gaji, penyusutan, dan akrual insentif: hari terakhir periodenya (bawaan) atau hari jurnal dibuat |

### 9.12 Daftar periksa tutup buku, telusur laporan, pelunasan antar-PT (PK-43)

| Istilah | Teks | Arti · bedakan dari | Unit · tempat |
|---|---|---|---|
| **daftar periksa** (tutup buku) | Panel "Daftar Periksa Sebelum Tutup Buku" · ringkasan "{n} beres · {m} perlu dilihat · {k} harus diselesaikan" · status "Beres" / "Perlu dilihat" / "Harus diselesaikan" / "Tidak terbaca" · tombol "Buka" | Butir pemeriksaan yang angkanya diambil dari sistem sebelum periode ditutup. Hanya "Harus diselesaikan" yang menghalangi (aturan server); "Perlu dilihat" ikut ditulis di konfirmasi Tutup Buku. Bedakan dari Pratinjau (jurnal penutup) | PK-43 · Tutup Buku |
| **saldo awal** (buku besar) | Baris pertama "Saldo awal" bila isian "Dari" diisi · "Saldo awal Rp … · Saldo akhir Rp …" | Saldo akun sebelum tanggal "Dari" (tanda mengikuti saldo normal akun); saldo berjalan berangkat dari sini | PK-43 · Buku Besar |
| **dokumen sumber** (jurnal) | Bilah "Dokumen sumber {jenis} {nomor}" · tombol "Buka Dokumen Sumber" · "{jenis} {nomor} — di luar PT Anda" / "— Anda belum punya akses untuk membukanya" | Dokumen yang melahirkan jurnal otomatis. Jurnal manual, penutup, pembalik, dan reklas penampung tidak punya dokumen sumber | PK-43 · rincian jurnal |
| **Pelunasan Antar-PT** (tombol) | Tombol "Buat Pelunasan" · pop-up "Pelunasan Antar-PT" · isian "Tanggal pelunasan", "Rekening {PT pembayar}" · tombol "Terbitkan Pelunasan" | Satu nama untuk tombol, pop-up, dan pengingat saldo menganggur (dulu "Buat Settlement"/"Settlement Antar-PT") | PK-43 · Antar-PT |

### 9.13 Kasus keuangan: penyelesaian tertunda dan titipan salah transfer (PK-25)

Istilah Keuangan › Kasus Keuangan, Antar Entitas › Pinjaman Antar-PT, dan Posting Gagal (`docs/blueprint/unit/PK-25.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **titipan salah transfer** | Lencana "Titipan salah transfer" di daftar Pinjaman Antar-PT · tautan "Kasus {nomor}: pelanggan membayar ke PT yang salah" · dokumen turunan kasus "Dokumen antar-PT {nomor}" | Dokumen antar-PT yang lahir saat kasus "Pelanggan bayar ke PT yang salah" diselesaikan: PT penerima uang berutang kepada PT pemilik tagihan sebesar uang yang salah masuk. Statusnya langsung "Sudah dicairkan" (uangnya memang sudah di PT penerima), saldonya tampil di Saldo Antar-PT sebagai saldo non-dagang, dan dilunasi lewat tombol "Angsur" seperti pinjaman. Bukan pinjaman yang disengaja |
| **penyelesaian tersimpan, jurnalnya gagal** | Pita rincian kasus "Penyelesaian tersimpan, tetapi jurnalnya gagal: {galat}. Perbaiki penyebabnya lalu ulangi dari Posting Gagal." · keterangan tombol mati "Penyelesaian sebelumnya belum tuntas — lanjutkan dari Posting Gagal." · pesan 409 "Kasus {nomor} punya penyelesaian \"{nama aksi}\" yang belum tuntas. Lanjutkan penyelesaian itu dari Posting Gagal." · jenis Posting Gagal "Kasus Keuangan" | Pelunasan/kas/titipan kasus sudah tercatat, tetapi jurnalnya belum terbit (mis. akun nonaktif). Kasus tetap terbuka; Ulang Posting meneruskan penyelesaian yang sama (tanpa pelunasan kedua) lalu menutup kasusnya. Penyelesaian dengan isi lain ditolak sampai yang tertunda tuntas |

### 9.14 Meja Insentif: omzet terkirim, pencairan, harga acuan (KM-T1)

Istilah SDM › Kinerja & Insentif › Target & Aturan (`docs/blueprint/unit/KM-T1.md`, keputusan K-19 … K-24).

| Istilah | Teks layar | Arti |
|---|---|---|
| **omzet terkirim** | "Omzet vs buku besar" · "Omzet terkirim (semua sales)" · pengaturan "Omzet insentif dihitung saat" | Nilai barang yang sudah dikirim, tanpa PPN, dikurangi retur dan nota kredit koreksi — sama dengan pendapatan penjualan di buku besar pada bulan yang sama. Pesanan yang belum dikirim tidak menaikkan omzet |
| **pencairan** | "Pencairan vs kas masuk" · "Dialokasikan ke pesanan" · "Kas belum dialokasikan" · pengaturan "Yang dihitung sebagai pencairan" | Uang pelanggan yang benar-benar masuk dan sudah dialokasikan ke pesanan (tunai, transfer, QRIS, giro, deposit, titipan bank). Hapus sisa, nota kredit, saldo kredit, dan kasus bukan pencairan pada pilihan bawaan. Kwitansi yang dibatalkan mengurangi pencairan pada bulan batal, bukan bulan asalnya |
| **harga acuan** | Pengaturan "Harga pembanding kualitas harga" (Harga daftar PT · Harga umum · Batas bawah harga) | Harga pembanding untuk menilai apakah sales menjual di bawah harga; dipotret di tiap baris pesanan saat pesanan dibuat |
| **target per PT** | Bagian "Target" · "Jenis periode" (Bulan · Triwulan · Tahun) · "Salin dari periode sebelumnya" | Target omzet dan pencairan per sales di PT yang sedang dibuka. Triwulan dan tahun mengikuti tahun buku PT dan adalah angka tersendiri, tidak dijumlah dari target bulanan |
| **komponen insentif** | Bagian "Komponen insentif" · "Tambah komponen" | Jenis insentif yang dipakai PT (mis. Insentif Bulanan, Insentif Triwulan): kode, periode dasar, dan angka yang ditampilkan. Nominalnya diputuskan di lembar insentif |
| **definisi angka** | Bagian "Definisi angka" · "Berlaku sejak {tanggal} (versi {n})" · "Ubah di Pusat Pengaturan" | Empat pilihan PT yang menentukan arti angka insentif; tiap perubahan dicatat sebagai versi baru |
| **pencocokan angka** | Kartu "Pencocokan angka" · "Cocok" · "Selisih Rp …" · "Penyebab selisih" | Pemeriksaan bulanan: omzet = pendapatan buku besar; pencairan + kas belum dialokasikan = kwitansi = kas masuk |

### 9.15 Nota kredit & nota debit pesanan (PK-32)

Istilah Keuangan › Koreksi & Amandemen, jejak koreksi di rincian pesanan, nota batal item, dan rincian retur
(`docs/blueprint/unit/PK-32.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **status nota** | Lencana "Menunggu Finance" · "Terbit" · "Selesai" · "Batal" (ikon + teks + warna), di samping nomor nota lencana jurnal PK-18 | Menunggu Finance = nota batal item belum ditinjau; Terbit = nota sudah lahir, efeknya (potong tagihan, saldo kredit, jurnal) belum semua tuntas — mis. jurnal gagal, ulang di Posting Gagal; Selesai = semua efek tuntas; Batal = dibatalkan sebelum berefek |
| **tagihan tambahan** | Bagian "Tagihan tambahan" di rincian pesanan (kolom Nota Debit · Keterangan · Nilai · Jatuh tempo) · baris "Tagihan tambahan (nota debit)" dan "Total tagihan" di Ringkasan Harga | Tagihan dari nota debit kenaikan harga/qty pesanan yang sudah terbit (K-14). Total pesanan asal tidak diubah; **total tagihan** = total pesanan + tagihan tambahan, dan sisa tagihan dihitung dari angka ini. Jatuh tempo = tanggal nota + termin pesanan |
| **belum mengurangi pendapatan** | "Rp {nominal} belum mengurangi pendapatan karena barangnya belum dikirim." (nota debit: "belum menambah") | Bagian nota yang barangnya belum dikirim: tidak dijurnal saat nota terbit, melainkan ikut nilai efektif saat surat jalan berikutnya |
| **kelebihan bayar** (nota) | "Kelebihan bayar Rp {nominal} tetap sebagai uang muka pelanggan." | Uang pelanggan di atas nilai pesanan sesudah koreksi; tetap uang muka pelanggan (dikembalikan/dipakai lewat Uang Masuk), bukan saldo kredit |
| **melebihi nilai pesanan** | 409 "Nota kredit {rupiah} akan membuat total nota kredit pesanan {nomor} menjadi {rupiah}, melebihi nilai pesanan {rupiah}. Periksa nota yang sudah terbit." | Total nota kredit (retur + koreksi) satu pesanan tidak boleh melebihi nilai tagihannya |
| **tidak bisa dibatalkan** (nota) | 409 "Nota {nomor} sudah mengurangi tagihan atau sudah dijurnal, jadi tidak bisa dibatalkan." · 400 "Alasan pembatalan nota wajib (minimal 5 huruf)." | Nota hanya bisa dibatalkan sebelum satu efek pun tuntas |

### 9.16 Laporan pendukung: umur piutang per surat jalan, umur hutang, arus kas, profitabilitas (PK-41)

Istilah Keuangan › Piutang, Keuangan › Hutang (Tagihan), Laporan Keuangan › Arus Kas, Profitabilitas, dan Control
Tower (`docs/blueprint/unit/PK-41.md`, keputusan K-16).

| Istilah | Teks layar | Arti |
|---|---|---|
| **piutang tercatat** | "Piutang tercatat (buku besar)" · baris di bawah total Piutang "Piutang tercatat {Rp} · Saldo akun piutang {Rp} · Selisih {Rp}" · kartu Control Tower "tercatat {Rp} · belum dikirim {Rp}" · Modal Kerja "Kas + piutang tercatat − hutang" | Nilai surat jalan yang sudah dijurnal dikurangi pembayaran yang dialokasikan ke surat jalan itu (jatuh tempo tertua dulu). Inilah yang dicocokkan dengan saldo akun piutang; selisihnya biasanya jurnal manual ke akun piutang, nota denda, atau jurnal pendapatan yang gagal |
| **belum dikirim** | Baris rincian pesanan "Belum dikirim" · status umur "Belum dikirim" · "belum dikirim {Rp}" | Bagian nilai pesanan yang barangnya belum keluar lewat surat jalan (dikurangi uang muka yang melebihi nilai terkirim). Belum punya jatuh tempo, tidak pernah telat, dan belum masuk buku besar piutang |
| **belum jatuh tempo** | Kolom pertama umur piutang dan umur hutang "Belum jatuh tempo" · status umur "Belum jatuh tempo" | Tagihan yang jatuh temponya hari ini atau sesudahnya (hari lewat ≤ 0), dihitung per tanggal kalender WIB. Umur piutang: jatuh tempo = tanggal surat jalan + termin; umur hutang: jatuh tempo tagihan, atau tanggal tagihan + termin pemasok bila kosong. Pengganti kata "Lancar" di dua laporan ini |
| **hari lewat jatuh tempo** | Kolom "Hari Lewat" (rincian surat jalan) · kolom "Hari lewat jatuh tempo" (lembar Umur Hutang) · "{n} hari lagi" | Selisih tanggal hari ini (atau tanggal posisi laporan) dengan jatuh tempo; positif = sudah lewat, "n hari lagi" = belum jatuh tempo |
| **saldo awal rekening yang didaftarkan periode ini** | Baris Arus Kas di bawah "Kas Awal Periode" | Saldo awal rekening bank/kas baru yang dicatat dalam periode laporan. Menambah kas awal, bukan arus pendanaan |
| **pencocokan ke Laba-Rugi** | Panel Profitabilitas "Pencocokan ke Laba-Rugi" (lima baris) | Jembatan dari marjin layar Profitabilitas (barang terkirim dikurangi nota kredit) ke laba kotor Laba-Rugi: penghapusan/penyesuaian persediaan dan penjualan antar-PT tidak dihitung di layar Profitabilitas |
| **nota debit belum dipotong** | Kartu pencocokan hutang "− Nota debit belum dipotong {Rp}" | Retur beli yang sudah menurunkan akun hutang tetapi belum mengurangi sisa tagihan mana pun (potongannya baru mengurangi tagihan saat kontrabon yang memuatnya lunas) |

### 9.17 Penggajian: komponen gaji, masukan, jenis proses gaji (PY-T1)

Istilah SDM › Penggajian (`docs/blueprint/unit/PY-T1.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **proses gaji** | Tab "Proses Gaji" · "Jenis proses: Reguler · THR · Susulan" | Satu kali penghitungan gaji satu PT untuk satu periode (dokumen "Penggajian", nomor `PAY-`). Reguler = gaji bulanan semua karyawan (satu per PT per periode); THR = hanya yang punya masukan THR; susulan = masukan yang belum terpakai sesudah proses reguler |
| **komponen gaji** | Tab "Komponen & Masukan" › bagian "Komponen gaji" · tombol "Tambah komponen" | Satu jenis baris di slip gaji (gaji pokok, tunjangan, lembur, komisi, THR, BPJS, PPh 21, bonus, potongan) — daftarnya per PT. Komponen bawaan tidak bisa dihapus atau diganti jenisnya |
| **masukan** (gaji) | Bagian "Masukan" · tombol "Tambah masukan", "Sahkan", "Batalkan" · status "Menunggu disahkan · Disahkan · Terpakai · Dibatalkan" | Nilai satu komponen untuk satu karyawan pada satu periode bayar (mis. bonus Rp 2.000.000), dari isian manual atau modul lain. Ikut dihitung di proses gaji periode itu sesudah disahkan; "Terpakai" = sudah masuk sebuah proses gaji |
| **tanggungan perusahaan** | Jenis komponen · bagian slip "Tanggungan perusahaan (informasi)" | Iuran yang dibayar perusahaan untuk karyawan (BPJS bagian perusahaan); tidak mengurangi gaji bersih |

### 9.18 Penggajian: riwayat kompensasi, penugasan PT, rapel (PY-T2)

Istilah kartu karyawan (SDM › Karyawan › buka karyawan) dan proses gaji (`docs/blueprint/unit/PY-T2.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **riwayat kompensasi** | Bagian "Riwayat Kompensasi" · tombol "Ajukan perubahan", "Sahkan", "Tolak" · lencana "Menunggu disahkan · Berlaku · Akan berlaku · Berakhir · Ditolak" | Daftar gaji pokok dan komponen tetap (tunjangan) karyawan menurut tanggal berlakunya. Perubahan gaji tidak lagi diketik di data karyawan: diajukan sebagai baris baru, berlaku sesudah disahkan. Proses gaji memakai baris yang berlaku pada periodenya |
| **penugasan PT** | Bagian "Penugasan PT" · tombol "Pindahkan ke PT lain" | PT (dan departemen, jabatan) tempat karyawan digaji menurut tanggal berlaku. PT pada hari terakhir bulan yang menggaji sebulan itu, kecuali pengaturan "Gaji berubah di tengah bulan" = prorata |
| **berlaku sejak** | Kolom & isian "Berlaku sejak" | Tanggal pertama nilai baru dipakai. Baris sebelumnya otomatis berakhir sehari sebelumnya |
| **rapel** | Komponen "Rapel" · baris slip "Rapel gaji September 2026" | Kekurangan gaji untuk bulan yang sudah dibayar karena kenaikan yang berlaku mundur. Dibuat otomatis sebagai masukan "Menunggu disahkan" di bulan berjalan; ikut proses gaji sesudah disahkan |
| **prorata** (gaji) | Pengaturan "Gaji berubah di tengah bulan" · baris slip "Gaji Pokok (1–15 Nov)" | Gaji bulan itu dibagi menurut jumlah hari tiap nilai (atau tiap PT) berlaku: nilai × hari ÷ jumlah hari bulan itu |

### 9.19 Faktur pajak: draf faktur, diganti, dokumen pajak retur, pencocokan PPN (TX-T2)

Istilah Akuntansi & Pajak › Pajak › Faktur Keluaran (`docs/blueprint/unit/TX-T2.md`). Nama dan bentuk resmi dokumen retur
menunggu konfirmasi konsultan pajak.

| Istilah | Teks layar | Arti |
|---|---|---|
| **pemicu faktur** | Pengaturan "Faktur pajak dibuat saat" · Per pesanan · Per surat jalan · Per uang muka (belum bisa dipakai) | Kapan faktur pajak lahir di PT itu. Per pesanan = diterbitkan orang untuk seluruh pesanan (bawaan); per surat jalan = draf muncul sendiri tiap barang keluar |
| **draf faktur** | Status "Draf" · tombol "Terbitkan", "Buang draf" · "Lihat draf faktur (n)" · "Tidak ada draf faktur." | Faktur yang disiapkan sistem dari jurnal surat jalan (atau nota kredit) dan belum terbit; tidak dihitung rekap PPN sampai diterbitkan. Draf yang dibuang tidak dibuat ulang otomatis |
| **diganti** | Status "Diganti" | Faktur asal yang sudah punya faktur pengganti; keluar dari rekap PPN. Bila penggantinya dibatalkan, faktur asal kembali ke status semula |
| **dokumen pajak retur** | Sakelar "Dokumen retur" · "Terbitkan Dokumen Pajak Retur" · "Nota … atas …" | Dokumen pajak atas nota kredit ber-PPN (retur/koreksi) yang mengurangi PPN keluaran; menunjuk faktur asalnya |
| **pencocokan PPN keluaran** | Panel "Pencocokan PPN keluaran" · "PPN di faktur", "PPN di dokumen retur", "PPN di buku besar", "Selisih", "Surat jalan tanpa faktur", "Faktur tanpa jurnal", "Retur tanpa dokumen pajak", "Belum terjelaskan" | Perbandingan satu PT satu masa antara dokumen pajak terbit dan akun PPN keluaran di buku besar; "Belum terjelaskan" = PPN di jurnal yang sumbernya tidak dikenal (mis. jurnal manual) dan wajib 0 |

### 9.20 Asisten: kartu uang keluar dan orang kedua (AG-T5)

Istilah Tanya KN › Tindakan untuk kartu golongan uang keluar (`docs/blueprint/unit/AG-T5.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **tindakan uang keluar** | pengaturan "Izinkan asisten untuk uang keluar dan jurnal" · pilihan akun "Uang masuk, uang keluar, dan jurnal" · akses peran "Tindakan uang keluar" · galat "Tindakan uang keluar dan jurnal lewat asisten belum dinyalakan untuk akun Anda." / "…untuk {nama PT}." | Kartu bayar tagihan pemasok, bayar kontrabon, dan kas manual yang disiapkan asisten. Butuh akses peran, pilihan akun, dan pengaturan PT yang menyala (bawaan mati) |
| **orang kedua** (kartu asisten) | status "Menunggu orang kedua" · "Menunggu orang kedua · disetujui {nama}, {tanggal jam} WIB" · "Kartu ini akan menunggu persetujuan orang kedua sebelum dijalankan." · tombol "Setujui dan jalankan" / "Tolak" · akses peran "Menyetujui sebagai orang kedua" | Bila PT mewajibkan dua orang (Pengaturan › Persetujuan › Kontrol dua orang, "Kartu asisten uang keluar"), kartu yang disetujui pembuatnya baru dijalankan sesudah rekan lain yang berwenang menyetujuinya; pembuat tidak bisa menjadi orang kedua |
| **kartu jurnal** (asisten) | tindakan "Catat jurnal manual" · "Balik jurnal" · isian "Ketik ulang nomor jurnal" · akses peran "Tindakan jurnal" · galat "Jurnal tidak seimbang: debit {x} ≠ kredit {y}." · hasil "Usulan jurnal menunggu persetujuan di layar Jurnal" · baris Pusat Persetujuan "Tindakan asisten menunggu orang kedua" | Jurnal manual dan balik jurnal yang disiapkan asisten; akun selalu dari pengguna dan diperiksa pintu jurnal (akun kontrol ditolak). Bila jurnal manual PT itu wajib dua orang, kartu berakhir sebagai usulan yang diputus di layar Jurnal |
| **daftar larangan** (asisten) | galat alat: "Tutup buku dan membukanya kembali hanya dilakukan di layar Tutup Buku." · "Pengguna, peran, dan izin hanya diatur di Pengaturan." · "Asisten tidak menghapus data." dan lainnya | Hal yang tidak pernah bisa dilakukan lewat asisten, apa pun permintaannya; dikerjakan di layarnya masing-masing |

### 9.21 Jadwal tagihan dan saldo piutang pelanggan (CR-T2)

Istilah Keuangan › Piutang (`docs/blueprint/unit/CR-T2.md`, keputusan K-16).

| Istilah | Teks layar | Arti |
|---|---|---|
| **jadwal tagihan** | Rincian pelanggan › bagian "Jadwal Tagihan" | Daftar baris tagihan satu pesanan yang disimpan sistem: lahir otomatis mengikuti termin (tiap surat jalan, uang muka saat pesanan dikonfirmasi, nota debit), atau rencana cicilan yang dibuat orang (rencana itu menggantikan jadwal termin) |
| **baris tagihan** | Kolom "Tagihan": "Surat jalan SJ-…", "Uang muka", "Cicilan 1", "Nota debit …" · kolom "Jatuh tempo", "Nilai", "Dibayar", "Sisa", "Telat (hari)" | Satu tagihan bertanggal jatuh tempo sendiri. Umur piutang, status kredit, pengingat, dan proyeksi kas menghitung telat per baris, bukan per pesanan. Catatan kaki: "Umur dihitung per tagihan: surat jalan, uang muka, atau baris rencana." |
| **belum dikirim** | Baris "Belum dikirim" di rincian pesanan | Bagian nilai pesanan yang belum menjadi baris tagihan (barang belum dikirim). Tidak punya jatuh tempo dan tidak pernah telat |
| **uang muka** (jadwal) | Baris "Uang muka 50%" | Untuk termin ber-DP: persen nilai pesanan yang jatuh tempo pada tanggal pesanan dikonfirmasi (sebelum kirim); baris surat jalan sesudahnya hanya memuat sisanya |
| **saldo piutang pelanggan** | (dibaca kartu kredit pelanggan dan pemeriksaan kredit pesanan) | Ringkasan tersimpan per pelanggan per PT: piutang barang terkirim, pesanan belum dikirim, lewat jatuh tempo, giro belum cair, titipan, saldo kredit, denda terbit. Dihitung ulang penuh dari dokumen tiap ada pembayaran, surat jalan, atau perubahan pesanan, dan setiap pergantian hari |

### 9.22 Titipan tunai sales dan setoran (PM-T4)

Istilah Keuangan › Kas & Bank › Titipan Sales, kartu HP "Titipan Saya", dan form kwitansi (`docs/blueprint/unit/PM-T4.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **titipan tunai** | Tab "Titipan Sales" · kartu HP "Titipan Saya" · lencana "Titipan sales" di Riwayat Pembayaran · teks bantu kwitansi "Uang tunai ini dicatat sebagai titipan di tangan Anda sampai disetor ke kasir atau bank." · status "Dipegang · Sebagian disetor · Disetor · Batal" · penanda "Lewat tenggat" · pengaturan "Tunai yang diterima sales dicatat sebagai", "Batas tunai yang boleh dipegang satu sales", "Tunai harus disetor dalam (hari)" | Uang tunai dari pelanggan yang diterima orang yang bukan pemegang kas (biasanya sales) di PT yang memilih "Titipan". Piutang pelanggan sudah turun dan pelanggan menerima kwitansi bernomor, tetapi uangnya belum masuk kas kantor — tercatat sebagai piutang titipan karyawan sampai setorannya diterima. Bedakan dari "Titipan pelanggan" (uang muka/deposit pelanggan) dan "titipan dana" (mutasi bank belum dikenali) |
| **setoran** (titipan) | Tombol "Setor" · pop-up "Setor titipan tunai" ("Jumlah disetor", "Catatan") · pemberitahuan "Setoran diajukan. Serahkan uangnya ke kasir." · bagian "Setoran menunggu diterima" · tombol "Terima setoran" (pop-up "Masuk ke rekening") dan "Tolak" · status "Diajukan · Diterima · Ditolak · Dibatalkan" · galat "Setoran melebihi tunai yang Anda pegang (Rp …).", "Setoran tidak bisa diterima oleh pemegang titipannya sendiri." | Penyerahan tunai titipan ke kasir/Finance. Diajukan pemegang titipan (dialokasikan ke titipan tertua lebih dulu); diterima orang lain yang berwenang ke rekening kas/bank PT — saat itu kas kantor bertambah dan titipan berkurang. Ditolak/dibatalkan tidak mengubah titipan. Bukan "setoran kewajiban" (BPJS/PPh 21, §9.11) |

### 9.23 Meja Insentif: capaian, omzet bersih, realisasi harga (KM-T2)

Istilah SDM › Kinerja & Insentif › Capaian (`docs/blueprint/unit/KM-T2.md`, keputusan K-19 … K-24). Layar hanya membaca;
nominal insentif diputuskan di lembar insentif.

| Istilah | Teks layar | Arti |
|---|---|---|
| **capaian** | Tab "Capaian" · kolom "% capaian" (kelompok Omzet dan Pencairan) · "Memuat capaian…" · "Capaian gagal dimuat." | Angka dasar insentif per sales di satu PT dan satu periode: target dan hasilnya. % capaian omzet = omzet bersih ÷ target omzet; % capaian pencairan = uang masuk ÷ target pencairan; satu desimal dengan koma ("86,2 %"); target belum diisi tampil "—" |
| **omzet bersih** | Kolom "Omzet bersih" · bilah "Omzet bersih: jumlah Rp … · rata-rata Rp …" · "+Rp … dari {periode}" | Omzet (menurut definisi PT — bawaan: barang terkirim tanpa PPN) dikurangi retur dan nota koreksi dalam periode yang sama |
| **realisasi harga** | Kolom "Realisasi harga" · "Rata-rata potongan" · "Di bawah harga acuan" (kelompok Kualitas harga) | Nilai jual barang terkirim dibagi nilai pada harga acuan PT (bawaan: harga daftar PT), hanya baris yang harga acuannya tercatat. Rata-rata potongan = 100 % − realisasi harga; di bawah harga acuan = porsi nilai jual yang harganya di bawah acuan |
| **uang masuk** (capaian) | Kolom "Uang masuk" · panel "Uang masuk — {sales} — {periode}" | Pencairan menurut definisi PT (bawaan: hanya uang yang benar-benar masuk dan dialokasikan ke pesanan); kwitansi yang dibatalkan mengurangi periode batalnya |
| **sisa piutang** (capaian) | Kolom "Sisa piutang" · "Lewat tempo" | Piutang pelanggan yang kini dipegang sales itu per akhir periode (paling jauh hari ini), dihitung per surat jalan seperti Umur Piutang; lewat tempo = bagian yang sudah lewat jatuh tempo |
| **telusur** | Klik angka Omzet, Retur, atau Uang masuk → panel "{kolom} — {sales} — {periode}" · "Jumlah Rp … dari {n} dokumen" | Daftar dokumen (surat jalan, nota kredit, kwitansi, pesanan) di balik satu angka; jumlahnya sama dengan angka sel. Nomor dokumen membuka dokumennya |
| **jumlah pilihan** | Bilah "{n} baris dipilih · … · rata-rata Rp …" · "{n} dokumen dipilih · jumlah Rp …" | Jumlah dan rata-rata baris yang dicentang, dihitung di layar dari angka yang sedang tampil |
| **catatan data** | Kolom "Catatan data" · "{n} catatan data" di bawah nama | Baris yang tidak ikut dihitung atau belum pasti: tanpa harga acuan, tanpa biaya (tidak ikut margin), kwitansi giro belum dipastikan cair, kasus keuangan yang bukan uang masuk |
| **tampilan tersimpan** | Tombol "Simpan tampilan" · "Tampilan disimpan di peramban ini." | Pilihan jenis periode, pembanding, kumulatif, pengelompokan, kolom, dan cari yang dibuka lagi otomatis — hanya di peramban itu, per pengguna |

### 9.24 Penggajian: aturan hitung — prorata masuk/keluar, hari kerja, potongan, lembur, saldo awal pajak (PY-T3)

Istilah Pengaturan › SDM (Aturan SDM & Penggajian, Kalender Libur), kartu karyawan, dan slip gaji
(`docs/blueprint/unit/PY-T3.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **prorata** (masuk/keluar) | Pengaturan "Gaji karyawan masuk/keluar tengah bulan" · baris slip "Gaji Pokok (16–30 Nov)" · tanda komponen "Diprorata" | Gaji bulan pertama dan terakhir dibayar sebanding hari bekerja: menurut hari kalender (hari ÷ jumlah hari bulan itu) atau hari kerja (hari kerja ÷ hari kerja bulan itu). Hanya komponen bertanda Diprorata yang dibagi. Bawaan: tidak diprorata (sebulan penuh) |
| **hari kerja** | Pengaturan "Hari kerja seminggu" · "Prorata menurut hari kerja" | Senin–Jumat (atau Senin–Sabtu pada pola enam hari) yang bukan hari libur PT. Dipakai prorata, potongan harian, dan jenis hari lembur |
| **kalender libur** | Tab "Kalender Libur" · "Tambah hari libur" · jenis "Nasional · Cuti bersama · Perusahaan" | Daftar hari libur PT yang diisi dari keputusan resmi. Sistem tidak mengisinya sendiri. Lembur pada hari libur memakai pengali hari libur |
| **upah sehari** (potongan) | "Potongan tidak hadir (2 hari)" · "Potongan cuti tanpa gaji (1 hari)" | Σ komponen bertanda Diprorata ÷ hari kerja bulan itu. Hari tidak hadir = hari kerja tanpa absensi dan tanpa cuti disetujui |
| **potongan terlambat** | Pengaturan "Potongan terlambat per menit (Rp)" · baris slip "Potongan terlambat (45 menit)" | Σ menit terlambat di absensi × tarif per menit. Potongan absensi mengurangi beban gaji dan bruto pajak |
| **lembur dari pengajuan** | Pengaturan "Lembur dibayar berdasarkan" · tautan "Lihat dampaknya" | Bawaan: lembur hanya dibayar bila pengajuan lemburnya disetujui. Pilihan absensi juga membayar menit lebih di absensi pada tanggal tanpa pengajuan (di atas "Lembur absensi minimal") |
| **saldo awal pajak** | Bagian kartu karyawan "Saldo awal pajak {tahun}" · "Jumlah masa di luar sistem", "Bruto", "Iuran pensiun", "PPh 21 sudah dipotong" | Penghasilan dan PPh 21 tahun berjalan yang dibayar di luar sistem sebelum penggajian dipakai. Ditambahkan saat pajak setahun dihitung ulang di masa pajak terakhir; terkunci sesudah slip masa terakhir diposting |

### 9.25 Layar keuangan yang disatukan: tahap kas kecil, titipan & saldo kredit, Perlu Tindakan (MN-T2)

Istilah Keuangan › Kas & Bank › Kas Kecil, Piutang › Titipan & Saldo Kredit, Akuntansi & Pajak › Tutup Buku, dan Beranda
Keuangan › Perlu Tindakan (`docs/blueprint/unit/MN-T2.md`).

| Istilah | Teks layar | Arti |
|---|---|---|
| **tahap kas kecil** | Chip & kolom "Tahap": **Diajukan · Dicairkan · Dipertanggungjawabkan · Selesai** (+ "Semua") · kosong "Belum ada pengajuan dana." | Letak satu pengajuan dana (PD) di alurnya, diturunkan dari status PD dan pertanggungjawabannya (LPJ): *Diajukan* = belum dicairkan (draf, menunggu persetujuan, disetujui, ditolak — status rinciannya ditulis di bawah pil); *Dicairkan* = uang sudah keluar, LPJ belum diajukan; *Dipertanggungjawabkan* = LPJ diajukan/disetujui, atau sudah dijurnal tetapi sisa uang muka belum kembali / hutang reimburse belum dibayar; *Selesai* = tidak ada sisa di kedua arah |
| **sisa kembali / hutang reimburse** | Kolom "Pertanggungjawaban": "Sisa kembali Rp …" · "Hutang reimburse Rp …" · tombol baris "Bayar" | Selisih LPJ terhadap uang muka: uang muka lebih besar → karyawan mengembalikan sisa ("Terima sisa" di rincian LPJ); pengeluaran lebih besar → perusahaan berhutang reimburse ke karyawan. Sebelum LPJ dijurnal angkanya perkiraan dari pengeluaran yang diajukan |
| **pertanggungjawabkan** | Tombol "Pertanggungjawabkan" di panel PD yang sudah dicairkan · "Dana sudah dicairkan dan belum dipertanggungjawabkan." | Membuat LPJ untuk PD itu (pop-up form LPJ dengan PD terpilih) |
| **titipan & saldo kredit** | Tab "Titipan & Saldo Kredit" · kolom "Uang muka pesanan belum dikirim" · "Deposit" (keterangan "Satu angka per pelanggan, tanpa PT") · "Saldo kredit" ("Per PT, ada riwayat") · "Jumlah" · "Umur tertua" · saringan "Punya uang muka / Punya deposit / Punya saldo kredit" · kosong "Tidak ada titipan maupun saldo kredit." · petunjuk "Pilih satu PT untuk mengubah saldo." | Uang pelanggan yang dipegang perusahaan, dari dua buku yang tidak digabung: laporan uang muka (uang muka pesanan + deposit kelebihan bayar) dan buku saldo kredit per PT (mis. dari retur). Jumlah = penjumlahan ketiganya. Bedakan dari "titipan tunai" sales (§9.22) |
| **daftar periksa** (tutup buku) | Panel "Daftar Periksa Sebelum Tutup Buku" · tombol "Buka" · seksi lipat "Persediaan vs buku besar" dan "Akun sementara" | Butir yang dicek sebelum menutup periode (§9.12). Butir akun penampung dan persediaan kini membuka seksinya di layar Tutup Buku itu sendiri; Posting Gagal dan Buka Periode adalah tab di hub yang sama |
| **akun sementara** | Seksi "Akun sementara" · "Saldo akun penampung (Suspense 1-9999) harus nol sebelum tutup buku; reklasifikasi di sini." | Akun penampung (Suspense) untuk mutasi yang belum dikenali; dulu tab "Suspense" di Jurnal & Buku Besar |
| **perlu tindakan** | Tab "Perlu Tindakan" · kelompok "Uang masuk perlu dicatat · Selisih bayar perlu diputus · Faktur pajak perlu terbit · Nota kredit perlu ditinjau · Hutang jatuh tempo · Kontrabon menunggu · Posting gagal · Denda perlu diterbitkan · Piutang lewat jatuh tempo · Sample berbayar menunggu ACC bayar · Retur selesai QC — putuskan nilai" · kosong "Tidak ada yang perlu ditindak hari ini." | Satu daftar pekerjaan uang berkelompok. Kelompok hanya tampil bila pengguna berhak atas modul sumbernya dan ada isinya; tiap baris satu tombol ke layar penanganannya |
| **kartu Keuangan** (beranda) | Kartu "Keuangan": "Kas & bank" · "Piutang lewat jatuh tempo" · "Hutang belum dibayar" · tautan "Buka Beranda Keuangan" | Ringkasan tiga angka di Beranda Admin dan Dasbor Manajer, dari sumber yang sama dengan tab Beranda Keuangan › Posisi |

### 9.26 Aturan denda berlapis: PT, pelanggan, rencana (CR-T4)

Istilah kartu pelanggan › Kredit › "Aturan denda", pop-up "Ajukan perubahan kredit", form rencana bayar, dan panel denda
(`docs/blueprint/unit/CR-T4.md`, keputusan K-30).

| Istilah | Teks layar | Arti |
|---|---|---|
| **aturan denda** | Bagian "Aturan denda" (Perlakuan denda · Tarif denda · Dasar hitung · Batas atas · Hari tenggang · Denda paling kecil yang dibuatkan nota) · lencana asal "ikut PT" / "khusus pelanggan" | Aturan yang dipakai usulan denda keterlambatan seorang pelanggan di satu PT. Dibaca berlapis: aturan PT (Pusat Pengaturan) → aturan khusus pelanggan (profil kredit) → aturan khusus rencana bayar (paling khusus) |
| **ikut PT** · **khusus** (aturan denda) | Pilihan "Aturan denda": "Ikut PT · Khusus · Bebas denda" · isian "Tarif denda (% per bulan)", "Dasar hitung" ("Sisa tagihan yang telat" · "Seluruh sisa pesanan"), "Batas atas (% dari dasar)", "Hari tenggang" · keterangan "Kosong = ikut aturan PT." | Khusus = pelanggan ini punya tarif/tenggang/batas sendiri; isian kosong tetap ikut PT. Diubah hanya lewat pengajuan perubahan kredit yang diputus pemegang akses memutus |
| **bebas denda** | Lencana "Bebas denda s.d. {tanggal}" · isian "Alasan", "Berlaku sampai" · galat "Bebas denda wajib beralasan dan punya tanggal berakhir." · kalimat "Bebas denda berakhir {tanggal} — sekarang ikut PT." | Pelanggan tidak dibuatkan usulan denda baru sampai tanggal itu (usulan yang sudah ada tidak diubah). Wajib beralasan dan bertanggal; tidak ada bebas selamanya |
| **aturan denda khusus rencana** | Form rencana bayar › bagian lipat "Aturan denda khusus rencana ini" · keterangan "Kosong = mengikuti aturan pelanggan atau PT." | Tarif/dasar/batas/tenggang untuk satu rencana cicilan; menimpa aturan pelanggan dan PT untuk pesanan itu saja |
| **aturan dari** (nota denda) | Panel denda: "Aturan dari: PT · pelanggan · rencana" | Asal unsur aturan yang dipakai nota itu (tercatat di potret aturan nota) |
| **taksiran denda** | Kolom "Denda" umur piutang, angka *est.* | Denda yang akan lahir bila dibuatkan nota sekarang — rumus dan aturannya sama dengan nota denda (harian, 30 hari = 1 bulan), bukan lagi dibulatkan per bulan penuh |
