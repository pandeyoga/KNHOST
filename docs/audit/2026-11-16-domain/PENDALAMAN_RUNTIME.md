# Audit domain — pendalaman runtime (16 Nov 2026, HEAD `91a3ec0`)

Audit sebelumnya lulus pemeriksa tetapi 40 dari 47 skenario berstatus `terhambat`. Sesi ini menjalankan skenario itu
lewat API di database lokal (`test_database`) dengan data uji berlabel `[UJI-AUDIT-1116]`. Tidak ada kode produksi,
data nyata, server, atau `main` yang diubah. Layar tidak dipotret (pilihan pemilik: berkas:baris + reproduksi API).

## Cakupan sesudah sesi ini

| Domain | Lulus | Gagal (cacat terbukti) | Masih terhambat |
|---|---|---|---|
| A master & stage | 6 | 1 (A-S6) | 2 (A-S3, A-S7) |
| B makloon | 1 | 2 (B-S4, B-S6) | 7 (B-S1 sebagian, B-S2, B-S3, B-S5, B-S8, B-S9, B-S10) |
| C R&D | 0 | 1 (C-S2) | 5 |
| D retur | 3 (D-S2, D-S4, D-S6) | 3 (D-S1, D-S5, D-S8) | 2 (D-S3, D-S7) |
| E QC & MD Quality | 0 | 3 (E-S1, E-S5, E-S6) | 3 (E-S2 sebagian, E-S3, E-S4) |
| F pesanan sesudah POS | 2 (F-S1, F-S2) | 3 (F-S3, F-S5, F-S8) | 3 (F-S4, F-S6, F-S7) |

"Gagal" berarti skenario dijalankan dan sistem berperilaku salah. 22 skenario masih `terhambat`; alasannya ditulis di
matriks tiap domain.

## Temuan baru, urut dampak

1. **SO-03** — batal pesanan ber-DP: uang muka Rp3.163.611 tetap menempel di pesanan batal, deposit pelanggan 0.
2. **SO-02** — pesanan terkirim sebagian tidak bisa dibatalkan, ditutup, atau dialokasi ulang walau stok ada.
3. **RT-05** — retur ditolak/dibalik sesudah barang diterima: roll dicatat di pelanggan padahal ada di gudang.
4. **MK-05** — makloon terima kurang: HPP hasil 2× dan saran klaim 2× nilai yang hilang.
5. **MK-06** — SPK makloon batal saat bahan di mitra: WIP dan roll menggantung.
6. **QM-03** — satu penerimaan PO butuh tiga dokumen; keputusan tolak QC diterima lalu diabaikan.
7. **QM-02** — enam roll dipindai menjadi satu roll 300 yard.
8. **RT-07** — grade berubah tanpa riwayat lewat retur/cutloss; BS masuk stok tersedia dengan HPP penuh.
9. **RD-02** — SKU Pesanan Khusus tanpa GSM/lebar langsung bisa dijual di POS.
10. **QM-04**, **RT-06**, **RT-04**, **RT-03** (Sedang); **RT-08**, **QM-05**, **SO-04** (Rendah).

## Koreksi atas audit sebelumnya

| Klaim lama | Hasil runtime |
|---|---|
| QM-01 "grade satu penulis, ditarik/dugaan" | Keliru. `grade-override` dan SPK 4-point menulis `grade_history`, tetapi retur dan cutloss mengubah grade tanpa riwayat (RT-07). |
| SO-01 "tiga pintu pemenuhan setuju di data contoh" | Sesudah kirim sebagian, rencana pemenuhan = 124,04; wizard dan meja pemenuhan = 260,48. Terbukti berbeda. |
| MK-02 "langkah makloon tidak menyimpan from/to_stage" | Keliru. Tersimpan sebagai `stage_from_stage`/`stage_to_stage` (`backend/services/makloon_order_service.py:434`), hanya tidak diadu dengan bahan masuk: printing dari greige, celup di mitra tanpa proses celup, dan bahan jadi → benang semuanya diterima. |
| RT-02 "risiko uang ganda retur belum terbukti" | Jurnal refund, reverse, scrap, batal scrap, cutloss, dan retur beli seimbang dan tidak ganda pada kasus yang dijalankan. Klaim ganda atas roll yang sama ditolak. Cacat yang ditemukan ada di status dan stok, bukan jurnal ganda. |

## Yang berjalan benar (dijalankan, tidak ada cacat)

- Ambil wajib pindai roll; pintu lama `qc-decision` ditolak 409 dan diarahkan ke SPK.
- Jurnal pendapatan = total SO; HPP terpisah; DP direklas saat kirim.
- Refund retur: pesanan belum lunas memotong piutang, pesanan lunas mengeluarkan kas ber-transaksi kas; reverse
  membatalkan keduanya.
- Kompensasi cutloss dihitung ulang server (isian 99 juta menjadi 375.000).
- 3-way match menolak tagihan pemasok melebihi yang diterima sesudah retur beli.

## Pertanyaan tambahan untuk pemilik

1. DP pesanan yang dibatalkan: otomatis jadi deposit, atau dikembalikan? (SO-03)
2. Sisa backorder pesanan terkirim sebagian: boleh ditutup Admin Sales sendiri? (SO-02)
3. Barang retur yang ditolak sesudah sampai gudang: dikirim balik atau disimpan? (RT-05)
4. Siapa pemutus akhir tolak/retur saat penerimaan: QC atau MD Quality? (QM-03, QM-04)
5. Susut makloon di atas toleransi: langkah ditahan sampai klaim diputus? (MK-05)
6. Stok BS hasil retur dinilai berapa? (RT-07)

## Catatan lingkungan dan data uji

- Data uji yang tertinggal di database lokal: SO KSC/SO-00002…00010, retur SRET-00004…00011, PO KSC/PO-00002…00004,
  SPK makloon CST/MKO-00003…00006, SKU `MTO-261116-0002`, kwitansi KSC/AR-00007…00010. Semua berlabel
  `[UJI-AUDIT-1116]` di catatan/alasan; tidak ada yang dihapus.
- KSC/AR-00010 lahir dari percobaan `method: "deposit"` yang ternyata dicatat sebagai kas masuk Rp1.000.000; itu
  artefak uji, bukan temuan yang sudah diperiksa.
- Skrip reproduksi: `bukti/runtime/skrip/` (butuh backend lokal hidup; `kn.py` + `flow.py` adalah pembantu).
- Skrip data contoh `seed_demo_transaksi_kn.py` gagal karena tiga aturan yang kini wajib: grade harus dipilih
  petugas, ambil wajib pindai roll, dan QC 4-point di SPK tersendiri. Skripnya yang tertinggal, bukan aturannya.
