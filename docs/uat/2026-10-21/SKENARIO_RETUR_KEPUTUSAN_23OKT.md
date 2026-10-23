# Skenario UAT — Keputusan Retur: Cutloss · Diskon · Tukar Barang (23 Okt 2026)

Tiga retur **sudah disiapkan sampai titik keputusan** di data UAT (`kn_uat_23okt`, http://localhost:3062).
Penguji tinggal menjalankan keputusannya. Akun = akun demo per peran (sandi sama seperti biasa).

Angka "hasil yang harus terlihat" dan jurnal di bawah adalah **hasil simulasi pada salinan persis database UAT**
dengan kode yang sama (input contoh tercantum). Bila input Anda berbeda, angka mengikuti rumus yang ditulis.

Disiapkan ulang dengan: `python scripts/seed_uat_retur_keputusan_kn.py` (di container backend, sesudah
`seed_uat_retur_kn.py`).

---

## 0. Data siap

Harga transaksi DENIM TENCEL TAUPE = **Rp 25.000/yard** (neto), PPN 11 %; biaya persediaan (WAC) = **Rp 18.000/yard**.

| Kode | Retur | SO asal · pelanggan | Barang diklaim | Bayar SO asal | Status sekarang |
|---|---|---|---|---|---|
| **K1 Cutloss** | **SRET-00005** | KSC/SO-00005 · Toko Kain Sejahtera | roll **RL-36309** · 122,61 yd | **Belum dibayar** (Rp 6.897.540) | *Selesai Inspeksi* — barang di Rancamalang · Gudang Transit, QC: lubang 2 titik (interval 15–30 yd), grade B |
| **K2 Diskon** | **SRET-00006** | KSC/SO-00006 · Moda Surabaya Fashion | 121,59 yd (kain **tetap di pelanggan**) | **Lunas** | *Disetujui* — bukti foto `bukti_k2.png`, tanpa QC fisik |
| **K3 Tukar barang** | **SRET-00007** | KSC/SO-00007 · Konveksi Maju Bersama | roll **RL-36313** · 121,07 yd | **Lunas** | *Selesai Inspeksi* — barang di Rancamalang · Gudang Transit, QC: noda 3 titik, grade B |

## 1. Cara membaca jurnal retur

**Penjualan awal** (sudah terjadi saat Surat Jalan; contoh SO-00007):

| Akun | Debit | Kredit |
|---|---|---|
| 1-1200 Piutang Usaha | 6.839.820 | |
| 4-1000 Pendapatan Penjualan | | 6.162.000 |
| 2-1200 PPN Keluaran | | 677.820 |
| 5-1000 Harga Pokok Penjualan | 4.436.640 | |
| 1-1300 Persediaan Barang | | 4.436.640 |

**Nota Kredit (CN)** membalik penjualan sebesar nilai yang dikompensasi:
Dr 4-1000 Pendapatan (DPP) + Dr 2-1200 PPN Keluaran (rasio PPN SO asal) / Cr **ke mana nilainya**:

| Ke mana nilainya | Akun kredit | Kapan |
|---|---|---|
| Potong sisa tagihan SO asal | 1-1200 Piutang | **selalu lebih dulu** bila SO asal belum lunas (hanya SO asal) |
| Jadi saldo pelanggan | 2-1450 Saldo Kredit Pelanggan | sisa sesudah potong tagihan, bila dipilih "Jadi saldo" / Store Credit / Tukar Barang |
| Refund tunai | 1-1100 Kas/Bank (akun pilihan) + mutasi kas keluar | sisa sesudah potong tagihan, bila dipilih "Refund tunai" / Pengembalian Dana |

**Barang kembali ke stok** (Pengembalian Dana / Store Credit / Tukar Barang): Dr 1-1300 Persediaan / Cr 5-1000 HPP
(qty × WAC). **Nego** (cutloss/diskon) tidak menggerakkan stok lewat CN.

Modal **Selesaikan Retur** kini menampilkan semua ini **sebelum disimpan**: nilai Nota Kredit per baris, DPP, PPN,
"Ke mana nilainya", barang ke stok, dan tombol **Lihat jurnal yang akan terbentuk**.

---

## 2. K1 — Cutloss (SRET-00005): kain cacat dipotong, bagian baik kembali ke pelanggan

| # | Peran (akun) | Navigasi | Input / keputusan | Hasil yang harus terlihat | Jurnal |
|---|---|---|---|---|---|
| 1 | MD Quality (`mdquality@`) | Menu **Retur** › Retur Pelanggan › SRET-00005 [Detail →] › panel **Cutloss & diskon** | Qty cacat **5** yard **atau** posisi cacat **20 – 25**; Potongan cacat **Masuk stok BS**; Roll **RL-36309** (terpilih otomatis); catatan → [Catat qty cacat] | Baris cutloss 5 yd · *Masuk stok BS* + tombol [Pratinjau potongan] | — |
| 2 | MD Quality / MD | baris cutloss › [Pratinjau potongan] → [Proses potongan] | konfirmasi | Bar potongan **20 yd baik · 5 yd BS · 97,61 yd baik**; roll anak **RL-36309-1** (5 yd, grade BS, tersedia); RL-36309 & RL-36309-2 ditahan untuk dikirim balik | Roll masuk gudang: **Dr 1-1300 2.206.980 / Cr 5-1000 2.206.980** (122,61 × 18.000) |
| 3 | MD Quality / MD | baris cutloss › [Buat SJ potongan baik] | — | **KSC/SJ-xxxxx** 117,61 yd ke Toko Kain Sejahtera, merujuk SJ & SO asal | **Dr 5-1000 2.116.980 / Cr 1-1300 2.116.980** (117,61 × 18.000) |
| 4 | Finance (`finance@`) | **Meja Finance** › antrean *Retur selesai QC — putuskan nilai* › SRET-00005 [Putuskan] › panel Cutloss & diskon | baris cutloss terisi otomatis **5 yd × Rp 25.000 = Rp 125.000**; *Catatan keputusan Finance* (wajib) → [Putuskan nilai] | *Diputus Finance: Rp 125.000 · nama* | — |
| 5 | Manajer (`manager@`) | detail retur › [Selesaikan (Pilih Outcome)] › **Nego (Diskon)** | kompensasi bebas (SO-00005 belum lunas → semua pilihan memotong tagihan dulu); bukti keputusan → [Selesaikan (Nego (Diskon))] | Panel nilai: **Nota Kredit Rp 138.750** = DPP 125.000 + PPN 13.750; *Potong sisa tagihan KSC/SO-00005 Rp 138.750*. Sesudah simpan: retur *Nego*, **CN-xxxxx**; sisa tagihan **SO-00005 = Rp 6.758.790** | **Dr 4-1000 125.000 · Dr 2-1200 13.750 / Cr 1-1200 138.750** |

**Netto K1:** Pendapatan −125.000 · PPN Keluaran −13.750 · Piutang −138.750 · Persediaan **+90.000** (5 yd BS) ·
HPP −90.000 (biaya qty cacat dibalik karena pendapatannya ikut dibalik).

Variasi **Dibuang** (langkah 1 pilih *Dibuang*): tambah **Dr 5-9500 Beban potongan cacat dibuang 90.000 / Cr 1-1300
90.000** → persediaan netto 0; biaya 5 yd pindah dari HPP ke beban kerugian.

Urutan: cutloss (1) wajib sebelum Finance (4). Pecah roll & SJ (2–3) boleh sebelum atau sesudah Manajer (5).

## 3. K2 — Diskon dari foto (SRET-00006): kain tetap di pelanggan

| # | Peran (akun) | Navigasi | Input / keputusan | Hasil yang harus terlihat | Jurnal |
|---|---|---|---|---|---|
| 1 | Finance (`finance@`) | Menu **Retur** › Retur Pelanggan › SRET-00006 [Detail →] › panel **Cutloss & diskon** | Qty cacat diskon **20** yd → nominal disarankan 20 × 25.000 = 500.000, ketik nominal kesepakatan **250.000**; centang bukti **bukti_k2.png**; catatan → [Putuskan nilai] | *Diputus Finance: Rp 250.000* | — |
| 2 | Manajer (`manager@`) | panel Cutloss & diskon › pilihan kompensasi **Jadi saldo** → [Selesaikan diskon (tanpa barang kembali)] | — | Retur *Nego*, **CN Rp 277.500** (250.000 + PPN 27.500); saldo Moda Surabaya Fashion **+Rp 277.500**; SPK QC **KSC/INS-00004** otomatis *Ditutup — QC tidak diperlukan* | **Dr 4-1000 250.000 · Dr 2-1200 27.500 / Cr 2-1450 277.500** |

Variasi: **Refund tunai** → Cr 1-1100 Kas/Bank 277.500 + mutasi kas keluar. **"Kurangi piutang SO asal saja"** →
**ditolak** (SO-00006 sudah lunas): pilih Jadi saldo atau Refund.
Saldo dipakai kelak untuk SO lain: Dr 2-1450 / Cr 1-1200.

## 4. K3 — Tukar barang, pengganti LEBIH banyak (SRET-00007)

| # | Peran (akun) | Navigasi | Input / keputusan | Hasil yang harus terlihat | Jurnal |
|---|---|---|---|---|---|
| 1 | Manajer (`manager@`) | Retur › SRET-00007 › [Selesaikan (Pilih Outcome)] › **Tukar Barang** | bukti keputusan → [Selesaikan (Tukar Barang)] | Panel: **CN Rp 3.359.692,50** (121,07 × 25.000 = 3.026.750 + PPN 332.942,50) → *Jadi saldo*; *Tipe retur berubah dari Retur menjadi Penggantian*; roll RL-36313 masuk karantina (grade B) | **Dr 4-1000 3.026.750 · Dr 2-1200 332.942,50 / Cr 2-1450 3.359.692,50**; **Dr 1-1300 2.179.260 / Cr 5-1000 2.179.260** (121,07 × 18.000) |
| 2 | Admin Sales (`salesadmin@`) | **Meja Admin Sales** › *Retur tukar — buat pesanan pengganti* › [Buat pengganti] › panel **Pesanan pengganti** | kewajiban 121,07 yd; isi pengganti **150** yd → [Buat pesanan pengganti] | **SO pengganti KSC/SO-xxxxx**: 150 × 25.000 = 3.750.000 + PPN 412.500 = **4.162.500**; *saldo retur dipakai Rp 3.359.692,50 · ditagih Rp 802.807,50*; grade **A** (= grade saat dijual) | **Dr 2-1450 3.359.692,50 / Cr 1-1200 3.359.692,50** |
| 3 | Admin Sales → Gudang → Admin Gudang | alur kirim biasa: Periksa & lepas → Barang Keluar (150 yd = **potong roll**: konfirmasi potong + tag roll anak) → muat → Surat Jalan → kirim | — | SO pengganti *Terkirim* | saat SJ: **Dr 1-1200 4.162.500 / Cr 4-1000 3.750.000 · Cr 2-1200 412.500**; **Dr 5-1000 / Cr 1-1300** (150 × WAC ≈ 2.700.000) |
| 4 | Finance (`finance@`) | Meja Finance › catat kwitansi pelanggan **Rp 802.807,50** | — | SO pengganti lunas | dibayar **sebelum** SJ: **Dr 1-1100 / Cr 2-1400 Uang Muka Pelanggan**, direklas otomatis Dr 2-1400 / Cr 1-1200 saat SJ; dibayar **sesudah** SJ: Dr 1-1100 / Cr 1-1200 |
| 5 | Manajer | SRET-00007 › panel karantina / *Tujuan barang retur* › simpan sebagai stok grade **B** | — | RL-36313 tersedia grade B; **kerugian turun grade Rp 908.025**; biaya roll 18.000 → 10.500/yd | **Dr 5-9500 908.025 / Cr 1-1300 908.025** = 121,07 × (25.000 × (100 % − 70 %)) |

Netto ke pelanggan: kredit 3.359.692,50 + bayar 802.807,50 = harga 150 yd (4.162.500).

## 5. Ringkasan jurnal

| Skenario | Langkah | Debit | Kredit |
|---|---|---|---|
| K1 | Pecah roll (roll masuk gudang) | 1-1300 2.206.980 | 5-1000 2.206.980 |
| K1 | SJ potongan baik | 5-1000 2.116.980 | 1-1300 2.116.980 |
| K1 | Nota Kredit (Nego) | 4-1000 125.000 · 2-1200 13.750 | 1-1200 138.750 |
| K2 | Nota Kredit (Nego, jadi saldo) | 4-1000 250.000 · 2-1200 27.500 | 2-1450 277.500 |
| K3 | Nota Kredit (Tukar Barang) | 4-1000 3.026.750 · 2-1200 332.942,50 · 1-1300 2.179.260 | 2-1450 3.359.692,50 · 5-1000 2.179.260 |
| K3 | Saldo dipakai SO pengganti | 2-1450 3.359.692,50 | 1-1200 3.359.692,50 |
| K3 | Bayar selisih (sebelum SJ) | 1-1100 802.807,50 | 2-1400 802.807,50 |
| K3 | Lepas karantina grade B | 5-9500 908.025 | 1-1300 908.025 |

## 6. Ditemukan & diperbaiki saat menyiapkan skenario (aktif di UAT)

| ID | Masalah | Perbaikan |
|---|---|---|
| J22 | Modal Selesaikan Retur tanpa nilai rupiah; tukar barang hanya dari tipe pengajuan | Panel nilai + jurnal; pilihan **Tukar Barang** |
| J23 | Roll cutloss yang sudah diterima gudang tetap *delivered* → **Pecah roll tidak pernah bisa** | Roll masuk gudang dulu (Dr Persediaan / Cr HPP), lalu dipecah; boleh juga sesudah Nego |
| J24 | Nego "kurangi piutang SO asal": GL piutang turun tetapi **sisa tagihan SO tidak** (pelanggan tetap ditagih penuh) | Tagihan SO asal ikut dipotong; melebihi sisa tagihan → ditolak dengan arahan |
| J25 | Diskon dari foto: SPK QC retur menggantung *Draf* | SPK ditutup otomatis "QC tidak diperlukan" |
| J26 | Pengganti mencari stok grade hasil QC (B) → "Stok tidak mencukupi" padahal pelanggan membeli A | Grade pengganti = grade saat dijual |
| J27 | Kerugian turun grade A→B tidak pernah tercatat (dibanding B→B) | Dibanding grade saat dijual |
| J28 | MD / MD Quality tidak punya menu Retur → panel cutloss tak terjangkau; kolom roll teks bebas → pecah roll gagal | Menu Retur untuk MD & MD Quality; roll dipilih dari roll klaim |

## 7. Batasan pengecekan

- Dicek di layar: modal Selesaikan (nilai, jurnal, Tukar Barang), panel cutloss untuk MD Quality & MD (roll terpilih
  otomatis), antrean *Retur selesai QC — putuskan nilai* di Meja Finance, form diskon Finance.
- Dijalankan lewat endpoint yang sama dengan tombolnya di **salinan** database (supaya data UAT tetap untuk Anda):
  pecah roll, SJ potongan baik, keputusan Finance, penyelesaian, pesanan pengganti, bayar selisih, lepas karantina.
- Lepas karantina ditolak untuk Admin Sales (butuh `sales_return.approve`) → dilakukan Manajer; panduan S14-13 menulis
  Admin Sales — perlu dicek apakah tombolnya tampil untuk Admin Sales.
- Pemakaian saldo (K3 langkah 2) mengkredit Piutang sebelum penjualan pengganti diakui → piutang pelanggan sementara
  minus sampai SJ terbit (saldo akhir benar).
