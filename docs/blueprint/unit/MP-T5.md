# MP-T5 — Gudang greige/PFD/PFP: peruntukan pengeluaran, surat jalan wajib packing list, akses MD

| | |
|---|---|
| Gelombang | Modul master produk & makloon |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | — |
| Menutup temuan | Permintaan klien 16 Nov |
| Keputusan | K-74, K-75, K-76, K-77 |
| Standar | `02` §2, §3, §4, §6 |
| Lingkungan uji | B + peramban |

## Tujuan

Setiap pengeluaran dari gudang greige/PFD/PFP mencatat peruntukan (pelanggan/toko atau stok) dan jumlah; semua barang
keluar gudang memakai surat jalan yang memuat packing list; MD bisa membeli greige/PFP/PFD.

## Keadaan sekarang (diperiksa 16 Nov, `d746702`)

| Pintu barang keluar | Dokumen cetak | Daftar roll (packing list) |
|---|---|---|
| Kirim pesanan ke pelanggan | `delivery_note` "Surat Jalan Pengiriman" (`backend/services/pdf_resolvers.py:882`) + `packing_list` terpisah (`:845`) | **Sudah** — SJ memuat baris per roll (kode, roll, jumlah) |
| Transfer antar-gudang | `transfer` "Surat Jalan Transfer" (`:660`) | Belum — hanya jumlah roll per barang |
| Kirim bahan ke mitra makloon (issue langkah SPK) | **Tidak ada** — hanya SPK (`:602`) | Belum |
| Retur beli ke pemasok | `purchase_return` "Nota Retur Beli" (`:533`) | Dicek saat unit dimulai |

Peruntukan pengeluaran (pelanggan/toko/stok) belum dicatat di SPK makloon maupun transfer. MD bawaan tidak punya izin
pembelian (`backend/permissions_config.py` peran `md`).

## Pecahan yang disarankan (`00` §8)

- **MP-T5a** — Surat jalan kirim bahan makloon (per pengiriman langkah, daftar roll) + daftar roll di SJ transfer & retur beli.
- **MP-T5b** — Peruntukan wajib pada SPK makloon & transfer yang bahannya greige/PFD/PFP (Pelanggan · Toko · Stok), tampil di
  SPK dan surat jalan.
- **MP-T5c** — Izin baru `purchase_order.create_bahan` "Buat PO bahan (benang/greige/PFD/PFP)" bawaan MD (K-77): PO/PR
  hanya untuk barang bertahap bahan; pemegang `purchase_order.create` tidak terpengaruh.

## Perubahan (garis besar)
- Isian "Peruntukan" (pelanggan/toko · stok) wajib pada pengeluaran bahan tahap greige/PFD/PFP; tampil di surat jalan
  dan laporan pengeluaran.
- Pengeluaran gudang tanpa surat jalan ber-packing list ditolak (daftar pintu dari pemeriksaan di atas).
- K-76 = pengaturan gudang (satu gudang, satu admin) — dikerjakan lewat data gudang, bukan kode.
- K-77: izin pembelian untuk peran MD mencakup greige/PFP/PFD (cek izin bawaan dan penyaring tahap di PR/PO).

## Uji penerimaan (dirinci saat unit dimulai)

| ID | Lapis | Langkah | Hasil |
|---|---|---|---|
| U1 | B | keluarkan greige tanpa peruntukan | 400 |
| U2 | B | keluarkan greige untuk pelanggan X | surat jalan memuat peruntukan + packing list |
| U3 | B | MD membuat PR greige | 200 |
