# Temuan tambahan dari riset perencanaan (48 butir)

Temuan ini muncul saat menelusuri kode untuk merancang modul di `05`–`09`. Mereka **di luar** 139 temuan laporan audit
keuangan dan memakai awalan ID baru supaya tidak bertabrakan: `KM` insentif, `CR` kredit/piutang, `PM` pembayaran, `TX`
pajak, `AG` asisten, `PY` penggajian.

Cara perolehan: kode dibaca di `9834947`; tidak ada yang dijalankan dan tidak ada database. Tanda ✔ berarti berkas:baris
buktinya saya buka dan baca sendiri; tanpa tanda berarti berasal dari pembacaan kode oleh agen riset dan belum saya cek
ulang baris per baris. Semuanya **harus dicek ulang di `HEAD`** sebelum diperbaiki, sama seperti temuan audit.

Rincian tiap temuan (bukti, skenario) ada di dokumen rancangannya; tabel ini indeks dan penugasannya. Tiap temuan
dipegang tepat satu paket atau tahap.

| ID | Tingkat | Ringkas | Rincian | Ditutup oleh |
|---|---|---|---|---|
| KM-01 ✔ | Tinggi | Faktor diskon mesin komisi praktis mati | `05` §2 | KM-T1 |
| KM-02 ✔ | Tinggi | "Pencairan" memuat hapus sisa dan nota kredit | `05` §2 | KM-T1 |
| KM-03 | Sedang | Tiga aturan atribusi sales hidup bersamaan | `05` §2 | KM-T1 |
| KM-04 ✔ | Sedang | Target tanpa PT; triwulan/tahun bukan angka tersendiri | `05` §2 | KM-T1 |
| KM-05 | Sedang | Tanpa dokumen keputusan; angka sumber bergerak mundur | `05` §2 | KM-T3 |
| KM-06 | Sedang | Serah-terima pelanggan tidak memindah tim sales | `05` §2 | KM-T1 |
| KM-07 | Rendah | Field tak terpakai; daftar "sales" tidak seragam | `05` §2 | KM-T4 |
| CR-01 ✔ (dijalankan 13 Nov) | Tinggi | Sales bisa mengubah plafon dan status blokir pelanggannya | `06` §2 | PK-45 |
| CR-02 | Tinggi | Kredit hanya diperiksa saat pesanan lahir | `06` §2 | CR-T3 |
| CR-03 ✔ | Sedang | Ambang telat dan peringatan ditulis mati di dua berkas | `06` §2 | CR-T1 |
| CR-04 ✔ | Sedang | Izin kredit tanpa masa berlaku, nominal 0 = tak terbatas, tanpa penjaga entitas | `06` §2 | CR-T3 |
| CR-05 | Tinggi | Termin bebas dipilih; pesanan tunai lolos dari kendali kredit dan tahan-kirim | `06` §2 | CR-T3 |
| CR-06 | Sedang | Tiga definisi jatuh tempo; rencana cicilan tidak dibaca kendali kredit | `06` §2 | CR-T2 |
| CR-07 | Sedang | Denda otomatis hanya untuk pesanan ber-rencana; aturan per pelanggan tanpa layar | `06` §2 | CR-T4 |
| CR-08 | Sedang | Tanpa riwayat plafon, catatan penolakan, rekening koran pelanggan | `06` §2 | CR-T5 |
| CR-09 | Sedang | Saldo piutang dihitung dari paling banyak 2.000 pesanan | `06` §2 | CR-T2 |
| PM-01 | Tinggi | Pesanan dan dokumen pelanggan tanpa cara bayar, rekening tujuan, instruksi bayar | `07` §A2 | PM-T2 |
| PM-02 ✔ | Tinggi | Kwitansi tidak mencatat rekening; metode teks bebas | `07` §A2 | PM-T3 |
| PM-03 | Sedang | Enam kosakata metode bayar yang berbeda | `07` §A2 | PM-T1 |
| PM-04 | Sedang | Rekonsiliasi tidak dibatasi rekening yang sama | `07` §A2 | PM-T3 |
| PM-05 ✔ | Sedang | Master rekening tanpa peruntukan dan bawaan; saringan aktif memakai field yang salah | `07` §A2 | PM-T1 |
| PM-06 | Sedang | Tunai di tangan sales tanpa alur titipan dan setoran | `07` §A2 | PM-T4 |
| TX-01 ✔ (dijalankan 13 Nov) | Tinggi | Faktur asli tetap terjumlah di rekap PPN setelah diganti: 110.000 menjadi 220.000 | `07` §B2 | PK-45 |
| TX-02 ✔ | Sedang | Kunci amandemen tidak lepas setelah faktur batal | `07` §B2 | PK-45 |
| TX-03 ✔ | Tinggi | Ubah/ganti/batal faktur tanpa penjaga entitas | `07` §B2 | PK-45 |
| TX-04 ✔ | Tinggi | Pesanan non-PPN lewat API tanpa izin khusus | `07` §B2 | PK-45 |
| TX-05 | Sedang | Faktur per pesanan dan manual; tidak terikat surat jalan, uang muka, retur | `07` §B2 | TX-T2 |
| TX-06 | Sedang | Faktor DPP, pembulatan, kode transaksi ditulis mati; tanpa data pajak pelanggan/barang | `07` §B2 | TX-T1 |
| AG-01 ✔ | Sedang | Konfirmasi gagal kembali ke antre; bisa menggandakan PO | `08` §2 | AG-T1 |
| AG-02 | Sedang | Draf tanpa masa berlaku; entitas tidak diperiksa ulang | `08` §2 | AG-T1 |
| AG-03 | Sedang | Aturan cakupan asisten terpisah dari izin router | `08` §2 | AG-T2 |
| AG-04 | Sedang | Pencarian supplier/gudang/sales tanpa saringan entitas | `08` §2 | AG-T1 |
| AG-05 | Rendah | Skema alat menawarkan yang tidak dilayani | `08` §2 | AG-T1 |
| AG-06 | Keputusan | Nama dan nominal dikirim ke penyedia tanpa penyamaran | `08` §2 | AG-T2 |
| PY-01 ✔ | Tinggi | Slip berkolom tetap | `09` §2 | PY-T1 |
| PY-02 ✔ | Tinggi | Satu proses gaji per PT per periode | `09` §2 | PY-T1 |
| PY-03 ✔ | Tinggi | Tabel tarif PPh 21 tampak tidak disalin dari peraturan | `09` §2 | PK-46 |
| PY-04 | Tinggi | Tanpa prorata dan potongan absen | `09` §2 | PY-T3 |
| PY-05 ✔ | Tinggi | Karyawan keluar tidak terhitung masa terakhirnya | `09` §2 | PK-45 |
| PY-06 | Sedang | Mode komisi "mati" tidak dihormati | `09` §2 | KM-T4 |
| PY-07 | Sedang | Pengaturan lembur tidak berpengaruh | `09` §2 | PY-T3 |
| PY-08 | Sedang | Lembur dari absensi otomatis disetujui | `09` §2 | PY-T3 |
| PY-09 | Sedang | Tanpa riwayat gaji dan penugasan PT bertanggal | `09` §2 | PY-T2 |
| PY-10 ✔ | Sedang | Pratinjau gaji menerima entitas mentah | `09` §2 | PK-45 |
| PY-11 | Sedang | Bayar gaji selalu dari satu akun; tanpa daftar transfer | `09` §2 | PY-T4 |
| PY-12 | Sedang | Tanpa saldo awal pajak tahun berjalan | `09` §2 | PY-T3 |
| PY-13 | Rendah | PDF slip berbaris tetap dan berangka mati | `09` §2 | PY-T1 |
| PY-14 | Rendah | Validasi periode; teks layar keliru; label belum diindonesiakan | `09` §2 | PY-T1 |

Jumlah: 15 tinggi, 28 sedang, 4 rendah, 1 keputusan. Delapan belas di antaranya bertanda ✔.

## Batas

- Saat daftar ini disusun tidak ada yang dijalankan. Sesudahnya TX-01 dan CR-01 dibuktikan lewat API
  (`docs/audit/konfigurasi-peran-2026-11-13/bukti/t7_…`, `t8_…`). Sisanya masih dari membaca kode; AG-01 khususnya harus
  dibuktikan dengan tes sebelum diperbaiki.
- PY-03 membandingkan tabel di kode dengan ingatan saya atas lampiran peraturan; yang pasti dari kode hanyalah bentuk
  tabelnya yang janggal. Kebenarannya harus diputuskan orang pajak dengan teks peraturan di tangan.
- Riset pembanding (sistem ERP lain, penyedia pembayaran, produk asisten akuntansi) sebagian hanya dari cuplikan
  penelusuran; yang demikian tidak dijadikan dasar rancangan tanpa ditandai.
