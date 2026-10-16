# Update VPS · Data Demo Lengkap (di atas master produk asli)

Untuk demo/simulasi tanpa perlu mengisi master apa pun. Master produk ASLI hasil migrasi (Excel) tetap utuh;
skrip ini hanya MENAMBAH data pendukung + transaksi contoh. Aman dijalankan ulang (yang sudah ada dilewati).

## Langkah di terminal VPS

1. Di Emergent: tekan **Save to GitHub** (agar kode terbaru ada di GitHub).
2. Masuk ke VPS:
   ```bash
   ssh root@187.77.116.148
   ```
3. Tarik kode terbaru & jalankan skrip demo (satu perintah):
   ```bash
   cd /opt/kainnusantara && git fetch origin main && git reset --hard origin/main && bash deploy/setup_demo_lengkap.sh
   ```
   Jangan pakai `git pull` (riwayat GitHub ditulis ulang oleh Save to GitHub). `deploy/.env` tidak tersentuh.
4. Tunggu sampai muncul `SELESAI — data demo lengkap siap.` (±5–15 menit, sebagian besar untuk build).
5. Buka `https://kainnusantara.cloud` dan login dengan salah satu akun di bawah.

Opsi: `SKIP_UPDATE=1 bash deploy/setup_demo_lengkap.sh` (kode sudah terbaru, lewati build) ·
`SKIP_BACKUP=1` (lewati backup — tidak disarankan).

## Yang dikerjakan skrip (`deploy/setup_demo_lengkap.sh`)

| Langkah | Isi |
|---|---|
| 1 | Backup database (`deploy/backups/…archive.gz`) — titik kembali bila ingin membatalkan |
| 2 | `deploy/update.sh` — tarik kode, build, restart (data tidak dihapus) |
| 3 | Bila master asli belum ada: impor Excel master produk (268 SKU) + stok awal |
| 4 | `scripts/seed_demo_lengkap_kn.py` — master pendukung, gudang, akun, produk & stok semua tahap |
| 5 | `scripts/seed_demo_transaksi_kn.py` — transaksi berjalan lewat endpoint resmi (jurnal & saldo asli) |
| 6 | Pemeriksaan akhir: ringkasan jumlah data + GL Persediaan vs subledger harus SELARAS |

### Struktur gudang
| Lokasi | Gudang | Pemakaian |
|---|---|---|
| Bandung · Rancamalang | Gudang Transit · Gudang Woven · Gudang Knitting · Gudang Printing | bersama (semua entitas) |
| Bandung · Rancamalang | Gudang Retur — hanya grade B / BS / C | bersama (semua entitas) |
| Bandung · Soreang | Gudang Kanda (satu gudang, barang campur) | khusus Kanda |
| Jakarta | Gudang Sukacita (satu gudang, barang campur) | khusus Sukacita |

Stok awal yang sebelumnya ada di "Gudang Utama <entitas>" / gudang bawaan dipindah otomatis ke struktur ini
(Sukacita → Jakarta, Kanda → Soreang, Cipta Sandang → Rancamalang sesuai lini), lalu gudang lama dinonaktifkan.
Gudang yang sudah dipakai transaksi tidak disentuh.

### Master & stok
- Warna (library + nama warna dari master produk), lini produk, tahapan proses, jenis sampel, alasan keluhan, galeri motif.
- 5 supplier (benang, grey, kain jadi, kimia) · 4 makloon (tenun, rajut, celup/pre-treatment, printing) + kontrak tarif.
- 7 customer di 3 entitas (plafon kredit + PIC sales) · rekening bank & kas tiap entitas · target sales bulan berjalan.
- Produk & stok semua tahap bahan: benang (woven/knit) → grey → PFD / PFP → kain jadi (master asli), plus sisa/perca
  dan hasil samping; roll grade B/BS/C di Gudang Retur.

### Transaksi contoh
- Pembelian: PR → disetujui → PO → diterima di Gudang Transit → inspeksi QC → tagihan supplier → dibayar 50%;
  pindah gudang Transit → Woven; PO diterima sebagian (60%); PO menunggu persetujuan.
- Penjualan: SO lunas, terkirim bayar sebagian, terkirim belum bayar, sudah dipick, terkonfirmasi,
  menunggu persetujuan manajer (melebihi plafon kredit).
- Makloon: tenun (bahan di mitra), rajut (selesai diterima), pre-treatment → celup (langkah 1 berjalan),
  printing (SPK dibuat, bahan dicadangkan).
- Kas kecil masuk/keluar di 3 entitas.
- Roll demo belum bertag RFID, jadi pengiriman memakai "pengecualian berizin" Final Loading Check (tercatat di audit).

## Akun demo (sandi semua: `demo1234`)

| Peran | Email (`@kainnusantara.id`) |
|---|---|
| Direktur / MD | `md@` |
| Manajer | `manager@` |
| Keuangan | `finance@` |
| Admin Sales | `salesadmin@` (Sukacita) · `salesadmin.kanda@` · `salesadmin.cst@` |
| Sales | `sales@`, `sales2@` (Sukacita) · `sales.kanda@` · `sales.cst@` |
| Gudang | `warehouse@` (Jakarta) · `warehouse.soreang@` (Soreang) · `warehouse.rancamalang@` (Rancamalang) |
| Admin Gudang | `whadmin@` |
| Desainer | `designer@` |
| Admin Sampel | `sampleadmin@` |
| Sopir | `driver@` |

`admin@kainnusantara.id` TIDAK diubah — tetap memakai `ADMIN_PASSWORD` di `deploy/.env`.
Sandi `demo1234` mudah ditebak: setelah demo selesai, ganti sandi atau nonaktifkan akun di Admin → Pengguna.

## Membatalkan / mengulang
```bash
cd /opt/kainnusantara && ls deploy/backups/          # cari backup dari langkah 1
bash deploy/backup.sh restore deploy/backups/<nama-berkas>.archive.gz
```
Bila satu skenario transaksi gagal, skrip berhenti dengan pesan `GAGAL — …`; skenario yang sudah berhasil
tidak diulang saat skrip dijalankan lagi.
