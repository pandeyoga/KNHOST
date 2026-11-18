# Konteks untuk chat lokal — Pelatihan Keuangan ERP Kain Nusantara (18 Nov 2026)

Berkas ini ringkasan siap pakai untuk asisten (Claude/Codex) di komputer lokal supaya langsung paham konteks pelatihan
keuangan: tujuan, keputusan pemilik, susunan materi, skenario, data latihan, fitur baru, temuan, dan yang masih menunggu
keputusan. Cara pakai di chat lokal: rujuk berkas ini (`@docs/pelatihan/2026-11-18_keuangan/KONTEKS_CHAT.md`) atau tempel
isinya di awal percakapan. Rincian lengkap selalu ada di berkas yang disebut di tiap bagian — berkas ini hanya peta.

Keadaan per **18 Nov 2026 ±04.00 WIB** · `main` = branch `claude/nifty-carson-jjx3c8` = commit `686befe` (atau sesudahnya).

---

## 1. Inti dalam 10 baris

1. Pelatihan untuk petugas keuangan (akun **Finance**) dan manajer keuangan, tanggal **18 Nov 2026**, di PT **Sukacita
   Textile** (`ent_ksc`, kode dokumen `KSC/…`).
2. Kelas satu hari memakai **deck Flow Krusial** (88 slide) — hanya alur krusial: Piutang, Hutang, Hutang & Piutang per
   Pelanggan/Pemasok, Kas & Bank, Koreksi, Buku besar & tutup bulan. Manual & deck lengkap = rujukan.
3. **Wewenang = IZIN, bukan nama peran.** Peran bisa kustom; tombol tampil bila peran memegang izinnya
   (`docs/blueprint/02_STANDAR.md` §3). Materi ditulis dengan menyebut izin (Modul › aksi).
4. **K-FIN-01** (pemilik, 17 Nov malam): *"finance juga memiliki akses yang sama dengan manager dan jangan dipisah"* →
   peran bawaan Finance memegang SEMUA izin Manajer + lintas PT. Kontrol dua orang tetap per pengguna.
5. **K-SDM-01**: SDM & penggajian dipegang Finance.
6. Fitur baru untuk kelas: **Keuangan › Hutang › Hutang per Pemasok** (bayar beberapa tagihan sekaligus) dan rincian
   **Piutang per Pelanggan** dengan Rekening koran + Janji bayar + Terima pembayaran beberapa SO.
7. Setiap langkah materi sudah dijalankan di layar (Playwright, akun peran) dan dicocokkan dengan buku: **41 skrip lulus**.
8. Uji otomatis pohon akhir: **jest 1.780/1.780**, **tests_mem 2.566 lulus / 0 gagal**, gate tanpa regresi.
9. Malam 18 Nov dini hari dilakukan perburuan cacat (zona waktu, peran kustom, uji adversarial, kegagalan lama) —
   puluhan cacat diperbaiki; sisanya tercatat terbuka / menunggu keputusan pemilik (§9).
10. Laporan lengkap: `docs/pelatihan/2026-11-18_keuangan/LAPORAN_AUDIT.md`.

---

## 2. Berkas penting

| Berkas | Isi |
|---|---|
| `Presentasi_Flow_Krusial_Keuangan.pptx` | **Deck kelas hari ini** (88 slide) — dibangun dari `src/krusial.json` + `src/ppt/buat_ppt_krusial.js` |
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara_Ringkas.pdf` | Manual cetak 160 hlm (tanpa tangkapan layar per langkah) |
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara.pdf` / `.html` | Manual lengkap 417 hlm (tangkapan layar tiap langkah) |
| `Presentasi_Pelatihan_Keuangan_ERP_Kain_Nusantara.pptx` | Deck lengkap 790 slide (semua bagian) |
| `LEMBAR_LATIHAN.md` | Lembar centang peserta per langkah |
| `LAPORAN_AUDIT.md` | §0 hasil uji · §2–§2f temuan (D = diperbaiki, C = catatan) · §3 keputusan pemilik (K-xx) · §4 catatan pelatih |
| `README.md` | Susunan materi, berkas, data latihan, cara membangun & menguji |
| `src/kurikulum.json` | Urutan Bagian 0–5 + tabel peran |
| `src/krusial.json` | Isi deck Flow Krusial: alur, langkah terpilih, tabel izin, rutinitas, catatan akses |
| `src/skenario/*.json` (F, K, H), `src/alur_e2e/*.json` (A, S) | Sumber materi per skenario: konsep, alur, navigasi, langkah (aksi · isian · hasil · gambar), jurnal per tahap, titik kontrol, cek buku, kesalahan umum, catatan pelatih |
| `src/variasi_klaim_materi.json` | Bukti setiap klaim teks materi (V9) |
| `uji/*.js`, `uji/konfigurasi/`, `uji/sdm/`, `uji/e2e/`, `uji/situasi/`, `uji/variasi/` | Skrip uji jalan Playwright per materi |
| `uji/hasil/<KODE>/hasil.json` | Hasil uji per langkah (+ PNG, tidak di-commit) |
| `uji/jalankan_semua.sh` | Menjalankan semua materi berurutan sesuai kurikulum |

Semua path di atas relatif terhadap `docs/pelatihan/2026-11-18_keuangan/`.

---

## 3. Susunan materi (kurikulum lengkap)

| Bagian | Isi | Kode |
|---|---|---|
| 0 Pengantar | Orientasi Finance: Beranda Keuangan, bilah atas, Profil Saya, Tanya KN | F01 |
| 1 Fondasi & Konfigurasi | Bagan akun → pemetaan akun → profil PT & periode → rekening → aturan keuangan & pajak → termin & plafon → hak akses & persetujuan → nomor & naskah dokumen → konfigurasi SDM | K01–K09 |
| 2 Alur ujung ke ujung (peraga pelatih) | Order to cash · Procure to pay · Retur (penjualan, pembelian, tukar) · Hire to pay · Jurnal sampai laporan & tutup buku | A1–A5 |
| 3 Praktik Finance per siklus | 3.1 Piutang (F02–F06, F13, F14) · 3.2 Hutang (F11, F12) · 3.3 Kas & Bank (F07–F10) · 3.4 SDM & Gaji (H01–H04, F15) · 3.5 Buku Besar (F16) | |
| 4 Manajer | Laporan keuangan · tutup buku | F17, F18 |
| 5 Situasi khusus & koreksi | Amandemen penjualan & pembelian, kirim sebagian, uang muka, batal, koreksi, per pihak | S1–S5 |

### Daftar skenario (kode · judul · pelaku · langkah · peserta uji)

| Kode | Judul | Pelaku | Lgkh | Peserta |
|---|---|---|---|---|
| F01 | Orientasi Finance | Finance | 12 | 01 |
| K01 | Bagan Akun (COA) | Finance · Manajer (pelatih) | 9 | 01 |
| K02 | Pemetaan Akun — dokumen mana masuk ke akun mana | Finance · Finance pelatih | 11 | 01 |
| K03 | Profil PT, tahun buku & periode | Manajer (pelatih) · Finance | 7 | 01 |
| K04 | Rekening kas & bank dengan saldo awal | Finance · Pelatih | 6 | 01 |
| K05 | Aturan Keuangan & Pajak — baca, ubah, kembalikan | Admin (pelatih) · Finance | 11 | 01 |
| K06 | Termin & plafon kredit pelanggan, termin pemasok | Finance · Manajer | 12 | 01 |
| K07 | Hak akses peran & aturan persetujuan | Admin (pelatih) · Finance | 9 | 01 |
| K08 | Nomor & naskah dokumen, Desainer PDF | Admin (pelatih) · Finance | 7 | 01 |
| K09 | Konfigurasi SDM & Gaji | Finance | 7 | 01 |
| A1 | Pesanan sampai Uang Masuk (order to cash) | Sales · Manajer · Admin Sales · Gudang · Finance | 30 | 21 |
| A2 | Pengadaan sampai Bayar (procure to pay) | Gudang · Manajer · Admin · Kepala Gudang · MD Quality · Finance | 30 | 31 |
| A3 | Retur penjualan & pembelian (Nota Kredit · Nota Debit), tukar barang | banyak peran · Finance | 33 | 41 · 42 · 47 |
| A4 | Karyawan sampai Gaji Dibayar | Finance · Manajer | 6 | 01 |
| A5 | Jurnal sampai Laporan & Tutup Buku (ringkasan) | Finance · Manajer | — | — |
| F02 | Terima pelunasan penuh lewat transfer | Finance | 10 | 04 |
| F03 | Pembayaran sebagian & Saldo & Umur piutang | Finance | 8 | 01 |
| F04 | Lebih bayar → titipan → dipakai tagihan berikutnya | Finance + Pelatih | 13 | 01 |
| F05 | Rencana pembayaran (cicilan) & denda | Finance | 16 | 04 |
| F06 | Kredit & Plafon — antrean kredit, kartu pelanggan | Finance | 8 | 01 |
| F07 | Kas Kecil — uang muka, LPJ, terima sisa | Finance · Manajer | 11 | 01 |
| F08 | Titipan Sales — setoran tunai sales | Finance · Sales | 6 | 01 |
| F09 | Rekening & Saldo, Transaksi Kas | Finance | 7 | 04 |
| F10 | Rekonsiliasi bank — impor mutasi, cocokkan, biaya bank | Finance | 9 | 04 |
| F11 | Bayar tagihan pemasok & baca GR/IR | Finance | 6 | 01 |
| F12 | Kontrabon (tukar faktur) sampai dibayar | Finance + Manajer + Admin | 10 | 01 |
| F13 | Faktur pajak keluaran — terbitkan, isi NSFP | Finance | 5 | 01 |
| F14 | Pesanan sample berbayar | Finance | 5 | 01 |
| H01 | Data karyawan baru | Finance | 6 | 01 |
| H02 | Masukan gaji & lembur | Finance · Manajer | 4 | 01 |
| H03 | Proses gaji (siapkan, sahkan, posting) | Finance · Manajer | 6 | 01 |
| H04 | Bayar gaji & slip | Finance | 6 | 01 |
| F15 | Bayar gaji & setor PPh 21 | Finance | 6 | 01 |
| F16 | Buku Besar & Jejak Dokumen | Finance | 9 | 01 |
| F17 | Laporan keuangan (LR, Neraca, Arus Kas, Profitabilitas) | Manajer | 6 | 01 |
| F18 | Tutup buku — daftar periksa, tutup, buka periode | Manajer · Admin | 10 | 01 |
| S1 | Amandemen & koreksi penjualan (nota kredit/debit) | Sales · Admin Sales · Manajer · Finance | 24 | 61 |
| S2 | Amandemen & situasi khusus pengadaan | Manajer · Admin · Gudang · Finance | 35 | 66 |
| S3 | Kirim sebagian · uang muka · batal · biaya bank | Sales · Admin Sales · Gudang · Manajer · Finance | 36 | 72 |
| S4 | Koreksi & pembatalan: kas, hutang, piutang, gaji, jurnal | Finance · Manajer | 41 | 76 |
| S5 | Hutang & Piutang per Pihak | Finance · Manajer (janji bayar) | 20 | 91 |

Kolom "Peserta" = nomor peserta pada putaran uji terakhir (angka contoh di materi berasal dari putaran itu).

---

## 4. Deck Flow Krusial (kelas hari ini)

Sumber `src/krusial.json`. Urutan: judul · agenda · **Wewenang = izin** (catatan akses + tabel aksi → izin) · peta alur
uang · cara menuju layar · 6 alur · rutinitas harian · tanya jawab.

| Alur | Dasar | Langkah yang ditampilkan |
|---|---|---|
| Piutang — dari pesanan sampai uang masuk | A1 | A1 [8, 19] · F02 [4, 6, 7, 8, 10] · F03 [2, 6, 8] · F04 [4, 7, 11] |
| Hutang — dari pengadaan sampai bayar | A2 | A2 [18] · F11 [2–5] · F12 [3, 5, 10] |
| Hutang & Piutang per Pelanggan dan Pemasok | S5 | semua langkah S5 |
| Kas & Bank — rekonsiliasi harian | F10 | F09 [4] · F10 [2–6, 9] |
| Koreksi yang paling sering | S4 | S4 [3–6] |
| Buku besar & tutup bulan | A5 | F16 [3, 8] · F18 [3, 5] |

### Tabel aksi → izin (dipakai di deck)

| Aksi | Izin (Modul › aksi) |
|---|---|
| Terima pembayaran (kwitansi) | Kwitansi / Uang Masuk (AR) › Buat |
| Batalkan kwitansi | Kwitansi / Uang Masuk (AR) › Batalkan (void) |
| Janji bayar pelanggan | Pesanan Penjualan (SO) › Ubah |
| Bayar tagihan pemasok (satu / beberapa) | Tagihan Supplier › Bayar |
| Setujui tagihan selisih harga | Tagihan Supplier › Setujui |
| Buat · setujui · bayar kontrabon | Kontrabon › Buat · Setujui · Bayar (setujui juga harus tercantum di Aturan Persetujuan) |
| Rekonsiliasi bank, catat biaya bank | Kas & Bank › Buat |
| Jurnal manual · balik · anulir | Akuntansi & Buku Besar › Buat · Batalkan (void) |
| Tutup buku | Akuntansi & Buku Besar › Kelola |
| Buka kembali periode | Akuntansi & Buku Besar › Buka kembali (bawaan khusus Admin) |
| Setujui izin kredit | Izin Kredit › Setujui |

### Rutinitas harian Finance (slide penutup)
- **Pagi**: Beranda Keuangan › Perlu Tindakan (uang masuk perlu dicatat, faktur pajak perlu terbit, selisih bayar).
- **Setiap ada transfer masuk**: Piutang › Penagihan & Penerimaan atau Piutang per Pelanggan → Terima pembayaran → kwitansi.
- **Jadwal bayar pemasok**: Hutang per Pemasok → centang tagihan jatuh tempo → Bayar → konfirmasi.
- **Sore**: Kas & Bank › Rekonsiliasi: impor mutasi, cocokkan, bukukan biaya bank.
- **Akhir bulan**: periksa akun sementara & GR/IR, baca Laba-Rugi & Neraca, tutup buku.

---

## 5. Data latihan & akun

- **Sandi semua akun demo/latihan**: `demo12345`.
- Akun peran: `admin@`, `manager@`, `finance@`, `sales@`, `salesadmin@`, `warehouse@`, `qc@` … `@kainnusantara.id`.
- Akun peserta: `finance.latihNN@kainnusantara.id` (peran Finance, ditugaskan ke PT Sukacita). Sejak K-FIN-01 akun ini
  **lintas PT** dan memegang izin Manajer — peserta diminta tetap di PT Sukacita.
- Data per peserta (lewat endpoint resmi): pelanggan `Latihan NN · Toko Kain Peserta NN`, pemasok
  `Latihan NN · Pemasok Grey Peserta NN`, SO pelunasan & bayar sebagian, cicilan, tagihan pemasok (bayar & kontrabon),
  izin kredit, karyawan baru, dll. Kartu Peserta: `--kartu`.
- Rekening: **BCA Operasional KSC** (bank), **Kas Toko KSC** (kas tunai).
- Menyiapkan peserta (lokal Docker):
  ```bash
  docker compose -f docker-compose.dev.yml exec backend python scripts/seed_pelatihan_keuangan_kn.py --mulai 07 --peserta 07
  ```
  `--hanya a_dasar:akun` / `a_dasar:mitra` / `a_dasar:so_` untuk sebagian; `--nonaktifkan` sesudah pelatihan.
  Peserta yang sudah dipakai **tidak bisa diulang** (dokumennya sudah terpakai) — pakai nomor baru.
- Peserta peraga (agar dokumen peserta kelas tidak terpakai): A1 21 · A2 31 · A3 41/42/47 · S1 61 · S2 66 (akun+pemasok
  saja) · S3 72 (akun, mitra, SO saja) · S4 76 · S5 91.

### Akun buku besar yang sering muncul

| Akun | Nama |
|---|---|
| 1-1100 | Kas Besar / Bank |
| 1-1110 | Kas Kecil |
| 1-1150 | Kas & Bank Transit (dana dalam perjalanan) |
| 1-1200 | Piutang Usaha |
| 1-1270 | Piutang Denda Pelanggan |
| 1-1500 | PPN Masukan |
| 2-1100 | Hutang Usaha |
| 2-1150 | GR/IR (barang diterima belum ditagih) |
| 2-1400 | Uang Muka Pelanggan (titipan / uang muka SO belum dikirim) |
| 2-1450 | Saldo Kredit Pelanggan (saldo retur / store credit) |
| 2-1500 · 2-1600 · 2-1800 | Hutang Insentif Penjualan · Hutang Gaji · Hutang PPh 21 |
| 4-1000 | Pendapatan Penjualan |
| 4-9300 | Pendapatan Denda Keterlambatan |
| 6-8000 | Beban Administrasi Bank |
| 6-9100 | Beban Selisih Pembayaran Pelanggan (selisih ≤ toleransi) |

Jurnal khas: kwitansi Dr 1-1100 / Cr 1-1200 · lebih bayar Cr 2-1400 · bayar tagihan Dr 2-1100 / Cr 1-1100 · biaya bank
Dr 6-8000 / Cr 1-1100 · nota denda Dr 1-1270 / Cr 4-9300 · pakai saldo retur ke SO belum dikirim Dr 2-1450 / Cr 2-1400
(direklas ke 1-1200 saat surat jalan terbit).

---

## 6. Fitur baru (17–18 Nov)

### Keuangan › Hutang › Hutang per Pemasok (`ap-by-supplier`)
- Satu baris per pemasok per PT: jumlah tagihan, 5 kolom umur, sisa hutang, jatuh tempo terdekat, potongan (nota debit +
  uang muka ke pemasok, per PT). Kartu angka = saringan; cari, saring, urut, CSV; Semua PT tidak dijumlah.
- Rincian pemasok: tagihan terbuka bercentang, [Bayar] per tagihan, **[Bayar terpilih]** = satu form + satu konfirmasi,
  tiap tagihan dibayar sendiri (satu kas keluar + satu jurnal per tagihan, kunci idempoten per tagihan, [Ulangi yang
  gagal]). Tagihan yang dipegang kontrabon tidak bisa dicentang ("Bayar lewat kontrabon …").
- Server: `GET /api/vendor-bills/payables/by-supplier[/{supplier_id}]` (`services/ap_party_service.py`).

### Piutang › Saldo & Umur › rincian pelanggan
- Per SO/SJ + umur, Jadwal Tagihan, Nota Denda, **[Terima pembayaran]** (beberapa SO + titipan, "Atur sendiri"),
  **[Rekening koran]** (tampil, Cetak PDF, salin pengingat), **[Janji bayar]** per SO (izin Pesanan › Ubah).

---

## 7. Catatan untuk pelatih (hari H)

- Akun Finance kini melihat tombol Manajer (Setujui, Tutup Buku, Jurnal Baru, Tambah Akun, Batalkan kwitansi) dan pemilih
  PT. Ingatkan: tetap di PT Sukacita, jangan menyetujui dokumen peserta lain, jangan mengubah pengaturan bersama.
- Kontrol dua orang tetap: pembuat dokumen tidak bisa menyetujui dokumennya sendiri.
- Peragaan yang mengubah pengaturan bersama wajib dikembalikan segera: K02 (pemetaan akun), K05 (aturan), K08 (naskah).
- Tutup buku (F18) diperagakan pada bulan kosong (September 2026), lalu dibuka kembali Admin. Jangan menutup Okt/Nov.
- S5 memakai dokumen yang sama dengan F02/F03/F11/F12 → jalankan di peserta peraga; bagian A mengeluarkan ±Rp 3,15 jt
  dari BCA Operasional KSC per peserta.
- Layar membulatkan rupiah, buku menyimpan sen (mis. tampil Rp 1.000.001, buku Rp 1.000.000,50) — temuan K-07.
- Bila tombol tidak tampil: cek izin peran (Peran & Hak Akses) dan Aturan Persetujuan; bila tampil tapi ditolak:
  baca pesan server (kontrol dua orang, periode tertutup, status dokumen).

---

## 8. Yang diperbaiki 17–18 Nov (commit di `main`)

| Commit | Isi |
|---|---|
| `790464b` | K-FIN-01: Finance = Manajer (izin, lintas PT, Meja, Aturan Persetujuan, gerbang nama peran satu arah) |
| `ac25d81` | Hutang per Pemasok + aksi di rincian piutang (S5) |
| `6d02792`, `74a492c`, `704d7a5` | **Zona waktu**: "hari ini" dari jam UTC salah pukul 00.00–07.00 WIB (bayar uang muka dinilai kurang bayar, rekonsiliasi "beda 1 hari", jatuh tempo cicilan/termin, harga & pengaturan terjadwal terlambat 7 jam, neraca, PPh final, tanggal Faktur Pajak, dll. — 25 tempat) |
| `bd41803` | Ulasan: uang muka pemasok dibaca lintas PT, aturan Admin "Manajer saja" ditambah Finance diam-diam, izin kontrabon, "Pilih semua" mencentang tagihan tersembunyi |
| `41c3b92` | Peran kustom: tombol keuangan mengikuti izin & Aturan Persetujuan (tidak lagi tampil lalu 403) |
| `1f612b7` | 9 kegagalan jest lama: 7 uji usang, 2 bug (Desainer PDF digerbang nama peran; pesan "tidak punya akses ke modul ini" keliru) |
| `a445621`, `d439b80` | Uji adversarial: pembalik kwitansi/kas bertanggal maju, kontrabon ganda saat balapan, pesan balapan berisi kode mentah, Lepas biaya bank tanpa konfirmasi |
| `cfaccf5`, `59c6104` | Tebus saldo retur ke SO belum/sebagian dikirim mengkredit Piutang (kini Uang Muka + reklas); pemeriksa selisih piutang menghitung ganda; tautan dokumen makloon/amandemen hilang; registri entitas |
| `def23db` | Tombol Anulir tidak tampil pada jurnal yang sudah dibalik |
| `4d3fb2b` … `a5db900` | Materi berorientasi izin, S5 masuk kurikulum, uji ulang penuh, manual & deck dibangun ulang |

---

## 9. Menunggu keputusan pemilik (LAPORAN_AUDIT.md §3)

| Kode | Pertanyaan |
|---|---|
| **K-52 / K-53** | Akun Finance (termasuk akun latihan) kini lintas PT + izin Manajer. Biarkan, matikan lintas PT untuk peran Finance, atau buat peran kustom "Finance latihan"? |
| K-51 | Hutang/piutang per pihak: izin janji bayar terlalu luas (`order.update`), janji per pelanggan, bayar banyak = N kas (bank 1 mutasi), rekening koran pemasok PDF, cicilan dari rincian, pemasok hanya-potongan tak tampil, pembulatan sen |
| K-54 | Desainer PDF kini terbuka bagi Manajer & Finance (pemegang `pdf_template.manage`). Bila harus khusus Admin: cabut izinnya |
| K-55 | Kwitansi dengan nomor referensi transfer sama diterima tanpa peringatan — tolak atau peringatkan? |
| K-56 | Koreksi data lama tebus saldo retur yang terlanjur Cr 1-1200 di VPS (data nyata — STOP & ASK) |
| A-01/A-02 (§2f) | Bebaskan denda & kasus di atas ambang masih diputus NAMA PERAN — usul jenis Aturan Persetujuan baru |
| A-09/A-10 | Peran ber-izin "terima pembayaran" saja tidak punya layar; tab tampil per modul padahal endpoint butuh sumber daya tertentu |
| K-07 | Pembulatan sen di layar vs buku |

Juga terbuka (rendah/sedang, rinci di §2f): sisa pembalik bertanggal hari ini untuk deposit/titipan tunai, form kwitansi
tanpa peringatan periode tertutup, alokasi lebih dari sisa dipangkas diam-diam, 37 tempat UTC yang hanya tampilan/notifikasi
(C-34), guard numeric_bounds & approval_queues, POC usang.

---

## 10. Menjalankan & membangun ulang (lokal Docker)

```bash
docker compose -f docker-compose.dev.yml up -d
```
Uji jalan semua materi (butuh backend :8001, frontend :3000, Node + Playwright di host; skrip memanggil `python3` untuk
langkah tertentu — set `KN_PY` ke Python yang bisa menjalankan skrip backend):
```bash
KN_PESERTA=01 bash docs/pelatihan/2026-11-18_keuangan/uji/jalankan_semua.sh
```
`KN_HANYA="F02 K0"` = hanya skrip berawalan itu; `KN_PESERTA_S5=93` dst. untuk peserta peraga lain.

Membangun ulang dokumen (dari `docs/pelatihan/2026-11-18_keuangan/`):
```bash
python3 src/bangun.py && python3 src/bangun.py --ringkas
```
```bash
python3 src/ppt/siapkan_data.py && node src/ppt/render_alur.js && node src/ppt/buat_ppt_krusial.js && node src/ppt/buat_ppt.js
```
(`pptxgenjs` lewat `NODE_PATH`; lihat README.)

Uji otomatis: backend `python -m pytest backend/tests_mem -n 0 -q` (wajib `-n 0`); frontend `cd frontend && CI=true yarn test --watchAll=false`.
Gate: `bash scripts/gate.sh --ci` (menghapus & mengisi ulang DB dev; nilai per pelanggaran dengan
`scripts/blueprint/bandingkan_pelanggaran_gate.py` terhadap `docs/blueprint/garis-dasar-gate/2026-11-18_latih_keuangan4_gate_ci.log`).

### VPS (sesudah `main` maju)
```bash
cd /opt/kainnusantara && bash deploy/backup.sh
```
```bash
cd /opt/kainnusantara && bash deploy/update.sh
```
Peserta peraga di VPS (contoh S5):
```bash
cd /opt/kainnusantara && docker compose --env-file deploy/.env -f deploy/docker-compose.yml exec backend python scripts/seed_pelatihan_keuangan_kn.py --mulai 91 --peserta 91
```

---

## 11. Aturan kerja repo yang relevan (ringkas dari AGENTS.md / CLAUDE.md)

- Bahasa kerja Bahasa Indonesia (UI, dokumen, pesan commit). Line ending LF.
- Wewenang dari izin, nilai aturan bisnis dari pengaturan (`docs/blueprint/02_STANDAR.md` §2–§3); data nyata, jalur
  produksi, isi tabel peraturan = STOP & ASK (`docs/blueprint/00_ATURAN_EKSEKUSI.md` §6).
- Jangan ubah `deploy/docker-compose.yml`, `deploy/Dockerfile.*` untuk kebutuhan dev; jangan commit `.env` atau
  `memory/GATE_RECEIPT.*`.
- Sebelum mengubah jurnal/buku pembantu: baca `docs/finance/AUDIT_KEUANGAN_2026-11-13.md`.
- Uji hemat: uji terarah selama bekerja, suite penuh sekali pada pohon akhir, gate sekali per gelombang.
