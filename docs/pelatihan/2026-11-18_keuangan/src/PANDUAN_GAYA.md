# Panduan gaya — materi Pelatihan Keuangan

Berlaku untuk semua teks yang dibaca peserta: `src/skenario/*.json`, `src/alur_e2e/*.json`, `src/kurikulum.json`, manual, slide.

## 1. Urutan materi (kurikulum)

| Bagian | Isi | Kode |
|---|---|---|
| 0. Pengantar | Tujuan pelatihan, siapa mengerjakan apa, cara membaca manual, akun & data latihan, navigasi, istilah | — |
| 1. Fondasi & konfigurasi | Bagan Akun (COA) → pemetaan akun → profil PT & periode → rekening kas/bank → aturan keuangan & pajak → termin & plafon → hak akses peran → nomor & naskah dokumen → konfigurasi SDM & gaji | K01… |
| 2. Alur ujung ke ujung | Gambaran besar, lalu: Pesanan sampai Uang Masuk (order to cash) · Pengadaan sampai Bayar (procure to pay) · Retur penjualan & pembelian · Karyawan sampai Gaji Dibayar (hire to pay) · Tutup buku & laporan | A1… |
| 3. Praktik Finance per siklus | 3.1 Piutang · 3.2 Hutang · 3.3 Kas & Bank · 3.4 SDM & Gaji · 3.5 Buku Besar & Dokumen | F…, H… |
| 4. Manajer | Laporan keuangan · Tutup buku | F17, F18 |

Fondasi selalu sebelum transaksi: peserta harus tahu dulu akun apa yang akan terisi sebelum mencatat transaksi.

## 2. Bahasa

- **Kalimat pendek, aktif, satu tindakan per kalimat.** "Klik [Simpan]." Bukan rangkaian panjang dengan "lalu… lalu… →".
- **Lakukan** = kalimat perintah: "Pilih rekening BCA Operasional KSC." **Hasil** = apa yang terlihat: "Status berubah menjadi *Lunas*."
- Satu langkah = paling banyak dua tindakan yang berkaitan (mis. isi nominal + klik Simpan). Pecah bila lebih.
- **Istilah tetap** (pakai yang sama di semua bagian): pelanggan, pemasok, pesanan penjualan (SO), pesanan pembelian (PO),
  surat jalan, tagihan pemasok, kwitansi, piutang, hutang, jurnal, akun, rekening, titipan, kontrabon, retur, nota kredit,
  nota debit, proses gaji, slip gaji, setoran pajak. Label tombol & menu ditulis **persis seperti di layar** walau berbahasa
  campuran (mis. tombol "Supplier") — dalam kalimat biasa pakai istilah tetap.
- **Tanpa istilah teknis**: jangan tulis id internal, nama kolom basis data, kunci kartu (`a_dasar:so_lunas`), testid, API,
  nama berkas, atau kode program. Kartu Peserta disebut dengan labelnya: "Kartu Peserta › SO untuk pelunasan".
- **Angka** ditulis "Rp 1.864.800"; contoh angka diberi kata "contoh" bila berbeda per peserta.
- Hindari huruf kapital untuk penekanan (JANGAN, WAJIB); pakai kata "penting:" di depan bila perlu.
- Tanpa singkatan yang belum dijelaskan; singkatan pertama kali ditulis lengkap: "Rekonsiliasi bank (mencocokkan mutasi rekening dengan buku)".

## 3. Bentuk tiap skenario / alur

```json
{"kode":"K01","modul":"1","judul":"Bagan Akun (COA)","bagian":"A",
 "tujuan":"Satu kalimat: apa yang peserta kuasai sesudah skenario ini.",
 "kapan":"Satu–dua kalimat: kapan dipakai di pekerjaan.",
 "konsep":["2–5 butir penjelasan inti sebelum praktik (mengapa, bagaimana sistem bekerja)."],
 "peran":"Finance (akun peserta) · Manajer (pelatih)","menit":20,
 "data_awal":"Data yang dipakai, disebut dengan bahasa biasa.",
 "alur":[{"peran":"Manajer","label":"≤ 6 kata"}],
 "navigasi":[{"menu":"Akuntansi & Pajak › Buku Besar › Bagan Akun","nav_id":"ledger","tab":"chart-of-accounts"}],
 "langkah":[{"no":1,"peran":"Finance","menu":"Akuntansi & Pajak › Buku Besar › Bagan Akun","aksi":"…","isi":"…","hasil":"…","gambar":"uji/hasil/K01/03-xxx.png"}],
 "cek_buku":["Akun 1-1100 Kas Besar / Bank (D) Rp X · 1-1200 Piutang Usaha (K) Rp X — seimbang"],
 "kesalahan_umum":["2–4 butir"],"catatan_pelatih":"…","uji":{"berkas":"uji/…/K01_x.js","peserta_uji":"…"}}
```

Alur ujung ke ujung (`src/alur_e2e/A1.json`) memakai bentuk yang sama, ditambah `"jurnal_per_tahap"`:
`[{"tahap":"Surat jalan dikirim","dokumen":"SJ","jurnal":"5-1000 HPP (D) · 1-1300 Persediaan (K)"}]` dan
`"titik_kontrol":["persetujuan limit kredit oleh Manajer", …]`.

`konsep` wajib diisi untuk Bagian 1 dan 2 (fondasi & alur), opsional untuk praktik.
