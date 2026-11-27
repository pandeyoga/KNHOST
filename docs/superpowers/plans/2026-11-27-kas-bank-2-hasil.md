# Hasil — Kas & Bank bagian 2: kas manual tanpa Pembelian/Gaji (C5), kas keluar besar butuh orang kedua (C6)

Tanggal: 27 Nov 2026 · Cabang: `claude/nifty-carson-jjx3c8` · Garis dasar: `31f3f97` (Kas & Bank 1 + rancangan/rencana
bagian 2) · Pohon kode akhir: `82b9f02`.

- **Rancangan:** `docs/superpowers/specs/2026-11-27-kas-bank-2-kas-manual-design.md` (keputusan pemilik C5 & C6 25 Nov;
  builder check §7.8).
- **Rencana:** `docs/superpowers/plans/2026-11-27-kas-bank-2-kas-manual.md`, 5 tugas.
- **Tangkapan layar (data acuan):** `2026-11-27-kas-bank-2-hasil/tangkapan/` — 27 potret PT KSC (finance@ pengaju, manager@ penyetuju): kategori tanpa Pembelian/Gaji + penolakan server; Rp 1.000.000 langsung; Rp 2.500.000 → "Ajukan" → PKK menunggu (nol kas, saldo tetap); Setujui mati untuk pengaju; Pusat Persetujuan → Setujui → kas + jurnal; Tolak beralasan; Batal; kartu Asisten "Diajukan"; pemberitahuan. Skrip `tangkap_kb2.js`, log angka API `tangkap_kb2_log.txt`.

**Status: selesai, belum digabung ke `main`.** Pembaruan VPS tidak menulis data.

## 1. Yang berubah untuk pengguna

| Keadaan dulu | Sekarang |
|---|---|
| Kas manual berkategori "Pembelian" dijurnal ke Persediaan tanpa barang masuk; "Gaji" dijurnal ke beban gaji di luar penggajian (gaji bisa terbeban dua kali). Teks bebas seperti "Beli kain" atau "bahan bakar" juga kena. | Kas manual **baru** (layar, server, kartu Asisten) menolak kategori yang dijurnal ke Persediaan atau beban gaji: "Kategori Pembelian dan Gaji tidak lagi dipakai di kas manual: pembelian barang lewat PO/tagihan pemasok, gaji lewat Proses Gaji. Belanja kecil kebutuhan kantor pakai kategori Operasional." Pilihan Pembelian & Gaji hilang dari form. Kas lama tetap bisa dibatalkan/diposting ulang; bayar tagihan pemasok & Proses Gaji tidak terpengaruh. |
| Kas keluar manual berapa pun langsung terjurnal oleh siapa pun pemegang izin catat kas. | Kas keluar manual **di atas** batas PT (bawaan **Rp 1.000.000**, Pusat Pengaturan › kontrol `kas_keluar_manual`) menjadi **pengajuan `PKK-`**: tidak ada kas atau jurnal sampai **orang kedua** (izin setujui kas) menyetujui — Admin pun tidak boleh menyetujui pengajuannya sendiri. Form menampilkan "Di atas Rp … — akan diajukan…" dan tombol **Ajukan**; bagian **Menunggu persetujuan** di Transaksi Kas (Setujui / Tolak beralasan / Batal), Pusat Persetujuan, pratinjau PKK + jejak, pemberitahuan ke penyetuju dan ke pengaju. Saat disetujui periode, rekening, kategori, dan anggaran diperiksa ulang. Rp 1.000.000 tepat dan kas masuk tetap langsung. |

**Pengaman:** kiriman ulang dengan kunci yang sama selalu kembali ke pengajuan atau kas yang sama, tidak pernah kas keluar
baru di atas batas (termasuk saat berbalapan dengan pembatalan); pengajuan menunggu tidak ikut saldo kas atau buku kas
rekening; persetujuan berklaim (dua Setujui bersamaan → satu kas); kunci proses yang tertinggal karena server mati bisa
dilepas di Kunci Saga.

## 2. Tugas → commit

| Tugas | Commit |
|---|---|
| T1 C5 kategori ditutup | `77ce3e0` |
| T2 C6 pengajuan (server) | `f9e13eb`, `9d57723` |
| T3 Kartu Asisten & pemberitahuan | `fbc152a` |
| T4 Layar & antrean | `ddb962b` |
| Gelombang perbaikan akhir | `f10fa8c`, `935dc8b`, `ff5c081` |
| Uji Kas & Bank 1 bergantung jam (UTC vs WIB) | `d1c25e7` |
| Temuan tangkapan (status kartu "Diajukan", label pratinjau, tombol Tutup, seed demo menyetujui pengajuan) | `82b9f02` |

Alur: T1–T3 ditinjau per tugas; T4 (layar) tanpa tinjauan tugas (perintah pemilik "ya percepat"); tinjauan seluruh cabang
→ satu gelombang perbaikan → tinjauan ulang: semua tertangani, tanpa temuan berat baru.

Temuan nyata yang tertangkap sebelum gabung:
- **jalan pintas persetujuan orang kedua** lewat kunci kiriman ulang (kas masuk berkunci sama → kas keluar Rp 5 juta langsung
  terjurnal) — T2, dibuktikan uji, ditutup;
- kiriman ulang yang berbalapan dengan pembatalan kas, dan nomor pengajuan yang dipakai sebagai kunci kiriman, masih bisa
  menerbitkan kas keluar di atas batas — tinjauan akhir, ditutup;
- kunci proses pengajuan (juga Pindah Dana & pindah saldo Kas & Bank 1, dan 8 koleksi lain) tidak terlihat di Kunci Saga
  sehingga tak bisa dilepas — tinjauan akhir, ditutup + penjaga diperkuat;
- uji Kas & Bank 1 merah setiap malam sesudah 17:00 UTC (tanggal UTC vs tanggal buku WIB) — uji diperbaiki (produk benar).

## 3. Uji (apa adanya)

- **Backend `tests_mem` penuh** di `d1c25e7`: 3280 lulus, 2 dilewati, 3 xfail, **0 gagal** (EXIT 0, 1248 dtk). `82b9f02` (kartu Asisten, pratinjau, seed demo): uji terarah 55 backend + 49 jest lulus.
- **Jest penuh** di `d1c25e7`: 2196/2197 uji, 271/273 suite — `odItemCancel`, `phase4R2` (kendala lingkungan, sama dengan garis dasar).
- **Uji baru:** `test_KB2_1`…`test_KB2_4` (backend) + `kb2KasManual.test.js` (jest).
- **MongoDB sungguhan** (`backend/tests/test_bp_KB2_bersamaan.py`, salinan data acuan + backend terpisah :8032, salinan dibuang, 3 kali jalan): (1) dua Setujui bersamaan ×3 → selalu satu 200 + satu 409, satu kas + satu jurnal; (2) Setujui × Batal bersamaan ×5 → tidak pernah campuran (disetujui = 1 kas, dibatalkan = 0 kas), kedua urutan menang terjadi; (3) dua kiriman berkunci sama bersamaan → satu pengajuan, nol kas langsung. 3/3 lulus.

### 3a. Gate

| Mode | FAIL (garis dasar) | Lebih merah | Pelanggaran baru (per pelanggaran) |
|---|---|---|---|
| `--ci` (`ddb962b`) | 36 (43) | 2 POC bawaan (sama dengan Kas & Bank 1, F1) | **0** |
| `--quick` (pohon akhir) | ⟨GQ⟩ | ⟨GQ2⟩ | ⟨GQ3⟩ |

## 4. Keputusan pelaksanaan (periksa)

Keputusan builder rancangan §7 (1–8), ditambah ketetapan selama eksekusi:

1. **C5 dihitung dari kata kunci jurnal** (akun lawan Persediaan / beban gaji), hanya isian kategori, kas masuk & keluar.
   Kategori bebas seperti "Operasional – beli ATK" ikut ditolak karena hari ini sudah dijurnal ke Persediaan.
2. **Batas Rp 1.000.000, "di atas" = lebih dari**; batas tidak dinilai ulang saat disetujui; anggaran tidak dicadangkan
   (diperiksa saat diajukan dan saat disetujui — yang menentukan).
3. **Admin pun butuh orang kedua** untuk kas keluar manual di atas batas (bawaan `kontrol.admin_tetap_dua_orang`).
4. **Tanggal kas = tanggal diajukan**; periode tertutup saat disetujui → ditolak berkalimat, pengaju mengajukan ulang.
5. **Kunci kiriman berawalan `pkk_` ditolak** (400) supaya nomor pengajuan tidak bisa dipakai sebagai kunci.
6. **Batal oleh pemegang izin hapus kas memberi tahu pengaju** (dianggap keputusan); batal oleh pengaju sendiri tidak.
7. **Kunci Saga diperluas** ke semua koleksi yang memakai klaim lewat konstanta modul (penjaga OPS-04 kini membaca AST);
   pemeriksaan kunci ikut membaca kas ber-`ref_id`.
8. Diparkir: butir daftar periksa tutup buku untuk pengajuan menunggu (fitur baru di luar rancangan); uji jalur preset di
   jest.

## 5. Untuk pemilik

1. Batas Rp 1.000.000 berlaku sama untuk semua PT sampai diubah per PT di Pusat Pengaturan (kontrol "Kas keluar manual").
2. Admin pun butuh orang kedua (butir 4.3) — setuju? Di PT yang hanya punya satu pemegang izin setujui kas, pengajuan di atas
   batas menunggu sampai ada orang kedua (atau batas dinaikkan).
3. Pengajuan yang masih menunggu belum muncul di daftar periksa tutup buku (butir 4.8).
4. Materi pelatihan Keuangan (situasi S4, variasi V2) memakai kategori Pembelian sebagai contoh salah kategori — perlu
   diganti contohnya pada pembaruan materi berikutnya.

## 6. Catatan kecil yang ditunda (tidak memblokir)

- Id kas tidak memuat PT: kas keluar ≤ batas di PT B yang memakai kunci kiriman PT A mendapat kas PT A kembali / 409 (tanpa
  uang baru) — lama.
- Setujui ulang sesudah crash (kas sudah ada) mengulang cek anggaran/periode terhadap kas itu.
- Penjaga OPS-04 melewati bentuk `claim(collection=…)` bernama-kata-kunci (belum ada pemanggil); kalimat "Sedang diproses …
  Kunci Saga" disalin tiga kali; uji hidup lama `test_iter314` kini 400 (lepas kunci tanpa alasan).
- Uji kecil: urutan kata kunci pertama-menang, kartu Asisten berkategori diizinkan, dua asersi 403/404.

## 7. Catatan pembaruan VPS

- Koleksi & indeks baru (`cash_out_requests`, nomor `PKK-` unik per PT, kunci kiriman unik per PT) dibuat saat backend
  menyala; tidak ada data yang ditulis.
- Pengaturan baru dengan bawaan registri: `kontrol.kas_keluar_manual.min_orang` "1", `kontrol.kas_keluar_manual.batas_nominal`
  1.000.000; `kas_keluar_manual` masuk bawaan `kontrol.admin_tetap_dua_orang` — **bila VPS menyimpan isian sendiri untuk
  daftar itu, bawaan baru tidak berlaku** (kueri Kas & Bank 1 `cek_kas_vps.js` butir 4 menunjukkannya).
- Kunci Saga kini menampilkan kunci lama yang tertinggal di koleksi yang baru terdaftar; Admin bisa menerima pemberitahuan
  untuk kunci lama itu sesudah pembaruan (wajar).
