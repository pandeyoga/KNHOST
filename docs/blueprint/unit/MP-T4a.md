# MP-T4a — Mekanisme makloon tanpa jurnal baru (pecahan MP-T4; jurnal di MP-T4b)

> Dipecah 16 Nov (`00` §8): bagian yang mengubah akun/arah jurnal (K-63 hutang jasa saat faktur dicocokkan, K-64 hasil
> klaim, tarif borongan per SPK) pindah ke **MP-T4b** berstatus `tahan` (H4/H5, pertanyaan di `STATUS.md` "Menunggu
> pemilik"). MP-T4a hanya memakai jurnal yang sudah ada: WIP makloon 1-1350 tetap satu akun, perpindahan antar-mitra hanya
> memindah nilai di buku pembantu SPK.


| | |
|---|---|
| Gelombang | Modul master produk & makloon |
| Jenis | fitur + perbaikan |
| Risiko | tinggi (dua serah-terima; menyentuh jurnal WIP makloon dan hutang jasa) |
| Prasyarat | MP-T2 |
| Menutup temuan | Audit makloon 16 Nov (bahan antara dipaksa ke gudang sendiri; tagihan jasa saat terima; klaim ke pendapatan; validasi klaim saat setuju; tolak klaim menutup SPK; QC tolak tidak tersambung klaim; susut 0 di Buku Bahan; batal SPK saat bahan di mitra; terima sebagian menutup langkah) |
| Keputusan | K-62, K-63, K-64, K-66, K-67, K-68, K-69 |
| Standar | `02` §1 (posting), §2, §3, §6 |
| Lingkungan uji | A (MongoDB asli — penerimaan memakai `array_filters`) + B untuk aturan |

## Tujuan

SPK berlangkah banyak berjalan seperti di lapangan: kain boleh langsung dari mitra ke mitra berikutnya (dicatat MD),
mitra end-to-end cukup melapor hasil akhir, tarif bisa borongan atau per proses, hutang jasa lahir saat faktur mitra
dicocokkan, dan hasil klaim dibukukan sesuai keadaan roll.

## Keadaan sekarang (dijalankan 16 Nov, skenario B-S1…B-S5)

- Hasil langkah antara wajib diterima ke gudang sendiri lewat Kedatangan (`goods_receipt_close_service._post_mko`). 
- Tagihan jasa diposting saat barang diterima (`makloon_order_service.receive_step`).
- Potong bon klaim → Dr 2-1100 / Cr 4-9200 "Pendapatan Klaim Makloon" walau roll masih di stok.
- Validasi klaim baru di tahap setuju; tolak klaim menutup SPK; QC tolak hasil makloon tidak membuat klaim.
- Penerimaan GRN tidak bisa mengisi biaya bahan pembantu nyata dan nomor faktur mitra.

## Perubahan (garis besar; dirinci saat unit dimulai, akun jurnal mengikuti yang sudah ada — akun baru = H4)

- Perpindahan mitra→mitra: dokumen "Teruskan ke mitra berikut" (izin baru `makloon_order.forward`, bawaan MD, K-66),
  memindahkan WIP antar-mitra tanpa lewat gudang; pilihan "kembali ke gudang dulu" tetap ada (K-62).
- Mode langkah "hasil akhir saja" (K-67): langkah antara tidak wajib diterima; jumlah antara opsional.
- Tarif borongan per SPK (satu tarif, satu tagihan) atau per proses (K-68), dari kontrak.
- Hutang jasa saat faktur mitra dicocokkan (K-63) — jurnal akrual saat terima diganti GR/IR jasa; akun mengikuti
  pemetaan yang ada, bila butuh akun baru → H4.
- Klaim (K-64): pengurang biaya roll yang masih di stok; pendapatan bila sudah terjual. Validasi saat diajukan; tolak
  klaim tidak menutup SPK; QC tolak hasil makloon membuka draf klaim.

## Uji penerimaan (dirinci saat unit dimulai)

| ID | Lapis | Langkah | Hasil |
|---|---|---|---|
| U1 | A | SPK 2 langkah, teruskan langsung mitra A → B | WIP pindah A→B, tidak ada roll masuk gudang di antaranya |
| U2 | A | mitra end-to-end lapor hasil akhir saja | langkah antara selesai tanpa penerimaan; HPP = bahan + tarif borongan |
| U3 | A | terima hasil, faktur mitra belum dicocokkan | belum ada hutang jasa; sesudah dicocokkan → hutang |
| U4 | A | klaim potong bon, roll masih di stok | biaya roll turun; tidak ada pendapatan klaim |

## Asumsi dan risiko
RISIKO: mengubah saat lahirnya hutang jasa memengaruhi saldo hutang — dipasang dengan sakelar per PT (H5).
