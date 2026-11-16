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

## Keadaan sekarang
Dicek ulang saat unit dimulai: pintu pengeluaran gudang (surat jalan penjualan, kirim bahan makloon, transfer, retur
beli), mana yang sudah mencetak packing list, dan izin pembelian MD per tahap barang.

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
