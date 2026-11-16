# Ringkasan untuk pemilik — review batch B1 (16 Nov 2026)

Yang diperiksa: 17 perbaikan keuangan berkeparahan Kritis/Tinggi (bayar hutang pemasok, titipan & biaya bank, nominal
untuk yang berizin, alokasi pembayaran piutang, konsolidasi antar-PT, batas hapus piutang) pada kode `main` `91a3ec0`.
Tiap butir dibaca kodenya, uji pelaksana dijalankan ulang, dan dicoba dibantah dengan uji tambahan reviewer.
Tidak ada kode, server, atau data nyata yang diubah. Layar tidak dipotret (sesuai pilihan sesi ini).

## Hasil

| Putusan | Jumlah | Butir |
|---|---|---|
| Benar (verified) | 10 | GL-03, SL-03, SL-04, SL-05, SL-06, FX-05, FX-06, FX-07, IC-03, IC-04 |
| Dibuka lagi (reopened) | 4 | SL-01, IA-01, IA-03, IC-07 |
| Menunggu keputusan Anda | 3 | SL-02, IA-02, FX-10 |

## Yang harus diperbaiki dulu (sebelum dipasang ke VPS)

1. **SL-01 (Kritis)** — pembayaran kontrabon bisa dibatalkan dari layar faktur satu per satu: kas 14 jt batal dan
   jurnalnya dibalik, tetapi hanya satu faktur (9 jt) yang terbuka lagi dan kontrabon tetap "lunas". Buku besar dan
   daftar hutang berselisih.
2. **IC-07** — retur antar-PT kedua bisa disetujui melebihi nilai transaksi, sehingga kewajiban "pengembalian dana"
   (11 jt) melebihi uang yang pernah diterima (10 jt).
3. **IA-03** — akun gudang melihat nominal kontrabon dan nama pemasok di papan Meja Finance, padahal di layar Kontrabon
   nominalnya sengaja disembunyikan dari gudang.
4. **IA-01** — nominal Nota Kredit/Debit masih terbaca di pencarian Jejak Dokumen oleh peran tanpa izin keuangan.

## Yang aman dipasang (dari batch ini)

Bayar faktur pemasok satu pintu (periksa periode dulu, jurnal tahan-gagal), alokasi titipan bank dan biaya/bunga bank,
kwitansi/deposit/hapus sisa lewat satu fungsi alokasi (termasuk batal kwitansi), eliminasi konsolidasi per periode dan
rantai A→B→C. Uji balapan di MongoDB asli (7 uji) lulus.

## Skrip migrasi yang terkait batch ini (belum dijalankan; keputusan Anda)

1. `scripts/apply_pk17_role_cleanup.py --apply` — mencabut izin lama gudang atas tagihan pemasok di matriks tersimpan.
   Tanpa ini, perbaikan IA-02 tidak berlaku di data yang sudah ada.
2. `scripts/migrasi_pk31_eliminasi_per_periode.py --apply` — memindahkan entri eliminasi lama ke entri per bulan.
   Jalankan mode baca-saja dulu dan periksa "dampak laba-rugi" per tahun sebelum `--apply`.

## Keputusan yang ditunggu dari Anda

1. **B1-K1 (SL-02)** — Haruskah server menolak pembayaran hutang yang datang tanpa kunci anti-ganda? Layar selalu
   mengirimnya; pemanggil lain (integrasi/skrip) masih bisa menggandakan kas keluar.
2. **B1-K2 (IA-02)** — Kapan skrip pembersih izin gudang dijalankan, dan bolehkah Finance melihat laporan margin
   antar-PT?
3. **B1-K3 (FX-10)** — Batas hapus piutang tanpa kas (Rp 1.000.000) berlaku per keputusan. Satu orang bisa menghapus
   2 × Rp 600.000 pada pesanan yang sama. Haruskah batasnya kumulatif (per pesanan, per pelanggan, atau per orang per
   periode)?

## Temuan baru (di luar 17 butir)

RV-01, RV-02, RV-03 — lihat [`TEMUAN_BARU_B1.md`](TEMUAN_BARU_B1.md). RV-03 baru dugaan dari membaca kode.

## Yang belum dikerjakan

- Batch B2–B8 (223 butir) belum direview.
- Skenario audit domain C, D, E masih "terhambat" (data uji R&D, retur, QC belum dibuat) — tidak disentuh sesi ini.
- Sisi layar batch B1 (menu peran, tombol) tidak diperiksa.
