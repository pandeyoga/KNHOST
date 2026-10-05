# Gelombang 2, putaran W2-02 — klaim makloon dan pembayaran AP

Snapshot tetap `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Putaran ini melanjutkan PROD-05 dan APAR-01; bukan memvalidasi perbaikan Gelombang 1. Kode aplikasi tidak diubah. Bukti: [hasil runtime](claim-payment-results.json), [harness](repro/wave2_claim_payment.py), [prompt perbaikan](05_PROMPT_KLAIM_DAN_PEMBAYARAN.md).

**11 skenario baru: delapan kontrol sesuai ekspektasi dan tiga reproduksi cacat untuk dua temuan baru.** Dua reproduksi concurrency adalah dua urutan dari satu akar masalah W2-005; jangan dihitung sebagai dua bug terpisah. Jumlah kumulatif Gelombang 2: 20 skenario unik, 14 kontrol, enam reproduksi cacat, lima ID temuan. Pengulangan harness untuk verifikasi tidak ditambahkan ke jumlah tersebut.

Fixture: order draft sintetis, bahan 10 meter bernilai100.000, issue melalui service asli, penerimaan8 meter dengan jasa100.000. Selisih hasil membuka klaim. Vendor bill dan jurnal jasa dibuat oleh penerimaan asli, bukan disisipkan langsung. Pengujian pembayaran/pembatalan memakai ASGI HTTP dengan user berizin; proposal/persetujuan klaim memakai service asli. Satu kontrol vendor bill umum memakai bill fixture dan posting GL asli. Tidak ada transfer uang nyata.

## W2-004 — pembatalan tagihan jasa makloon sukses tanpa membalik utang GL

**P1 · Terbukti runtime HTTP + Mongo · W2-B-F01.**

### Letak kode

- [vendor_bills.py:581 — cancel_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/vendor_bills.py#L581): mengizinkan bill posted yang belum dibayar; tidak membedakan asal makloon.
- [vendor_bills.py:602 — panggilan reversal](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/vendor_bills.py#L602): tidak menjadikan hasil reversal kosong sebagai penghalang perubahan status.
- [gl_service.py:1652 — reverse_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L1652): mencari jurnal `source_type="vendor_bill"`; jika tidak ada, mengembalikan None.
- [gl_service.py:1425 — post_subcon_service](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L1425): tagihan jasa makloon memakai `source_type="subcon_service"`.
- [gl_service.py:1615 — pengecualian posting generik](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L1615): secara eksplisit tidak membuat jurnal vendor_bill kedua untuk makloon, sehingga reversal generik memang tidak akan menemukan jurnal tipe tersebut.

### Reproduksi dan hasil

1. Issue dan receive order makloon sampai lahir tagihan jasa100.000 serta jurnal subcon_service.
2. Belum ada pembayaran.
3. POST `/api/vendor-bills/{bill_id}/cancel` dengan alasan pembatalan.
4. Respons200; status bill `cancelled`; saldo kredit akun utang2-1100 tetap100.000; tidak ada jurnal pembalik.

Tagihan cancelled dikeluarkan dari query ringkasan AP di [vendor_bills.py:61](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/vendor_bills.py#L61). Ini penelusuran source lanjutan, bukan assertion endpoint summary pada harness. Akibatnya status/subledger dan GL dapat bertentangan: dokumen dianggap batal, kewajiban pada GL tetap ada.

Kontrol yang membatasi temuan: bill jasa yang dibayar normal100.000 membuat GL AP nol; cancel setelah dibayar ditolak400. Vendor bill **umum** yang diposting sebagai vendor_bill lalu dibatalkan menghasilkan jurnal pembalik dan net AP nol. Jadi temuan bukan klaim bahwa seluruh pembatalan vendor bill rusak.

### Mengapa perbaikannya lintas flow

Jasa makloon sudah diserap ke WIP dan output ketika penerimaan selesai. Mengganti filter reversal agar menemukan subcon_service saja belum cukup: membalik Dr WIP/Cr AP sesudah WIP sudah dikapitalisasi bisa membuat sisi biaya tidak benar. Kontrak pembatalan harus memutuskan apakah tagihan turunan boleh dibatalkan dari layar generik atau harus melalui koreksi/reversal makloon yang mempertimbangkan output, penjualan/konsumsi lanjut, pajak bila ada, dan klaim terkait.

Pilihan aman secara desain adalah menolak pembatalan generik bill turunan dan mengarahkan ke koreksi sumber, atau menyediakan orkestrasi koreksi sumber yang benar-benar menjaga nilai persediaan/WIP/AP. Pilih sesuai aturan bisnis; jangan menjadikan jurnal sumber yang tidak ditemukan sebagai sukses diam-diam. UI detail juga menampilkan tombol Batalkan untuk status posted tanpa pemeriksaan bill_type pada [VendorBillDetailPanel.jsx:200](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/purchasing/VendorBillDetailPanel.jsx#L200); ini pemeriksaan source UI, belum browser UAT.

### Kriteria penerimaan

- Normal supplier bill masih dapat dibatalkan dengan pembalik yang benar.
- Bill turunan makloon mengikuti kontrak koreksi sumber; tidak boleh cancelled dengan utang GL tertinggal.
- Verifikasi AP, WIP, nilai output, klaim, dan dokumen sumber setelah setiap langkah, retry serta kegagalan posting.
- Uji jasa murni versus jasa yang diserap output, bill dibayar sebagian, pajak fixture, output sudah dikonsumsi/dijual, periode tertutup.
- Jangan memperbaiki data historis dengan penghapusan jurnal atau perubahan nilai tanpa bukti dan persetujuan atas rencana migrasi konkret.

## W2-005 — pembayaran dan potong bon memakai snapshot berbeda sehingga overpayment lolos

**P1 · Terbukti runtime dengan dua interleaving terkontrol · W2-B-F02/F03.**

### Letak kode

- [vendor_bills.py:469](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/vendor_bills.py#L469): `grand_total` disalin dari snapshot awal bill.
- [vendor_bills.py:512](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/vendor_bills.py#L512): guard atomik membandingkan amount_paid terkini + applied dengan **angka grand_total dari snapshot**, bukan nilai dokumen terkini.
- [makloon_claim_service.py:165](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_claim_service.py#L165): batas potongan dihitung dari grand dan paid yang baru dibaca tetapi tidak dikunci.
- [makloon_claim_service.py:170](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_claim_service.py#L170): posting jurnal klaim disusul update bill hanya berdasarkan id, tanpa syarat versi/saldo paid.

### Dua urutan yang terbukti

| Urutan | Perubahan yang terjadi | Hasil akhir |
|---|---|---|
| F02 | Payment membaca tagihan100.000 → klaim40.000 disetujui, grand jadi60.000 → payment80.000 dilanjutkan memakai batas lama | HTTP200, grand60.000, paid80.000, kas keluar80.000 |
| F03 | Klaim memeriksa bill belum dibayar100.000 → payment80.000 selesai → klaim40.000 dilanjutkan tanpa pemeriksaan ulang saldo | HTTP200 untuk payment, klaim approved, grand60.000, paid80.000 |

Keduanya menghasilkan net kredit AP **−20.000** (saldo debit20.000). Bill tetap `posted`, meskipun paid melebihi grand. Kelebihan tidak diperlakukan sebagai keputusan uang muka supplier pada alur ini: pembayaran sebelumnya menilai nominal80.000 sebagai kurang dari snapshot100.000. `bill_financials` memakai `max(grand-paid, 0)` di [vendor_bill_service.py:155](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/vendor_bill_service.py#L155), sehingga tampilan outstanding yang menggunakannya dapat menyembunyikan selisih negatif. Bagian tampilan ini adalah penelusuran source, belum UI UAT.

### Mengapa kontrol yang sudah ada belum cukup

Delapan kontrol menunjukkan jalur serial umumnya berjalan: potong40.000 lalu bayar60.000 melunasi AP; bayar80.000 dulu lalu ajukan potong40.000 secara serial ditolak karena sisa20.000. Dua pembayaran80.000 yang membaca tagihan100.000 bersamaan menghasilkan satu200 dan satu409, dengan kas total80.000. Jadi guard pembayaran efektif untuk **dua pembayaran saat grand_total tetap**. Ia tidak menyatukan perubahan denominator/tagihan oleh writer klaim.

Barrier harness hanya menjeda penjadwalan di await tertentu, lalu memanggil fungsi asli. Tidak mengubah angka, hasil assessment, query Mongo, ataupun jurnal. F02 menjeda hasil assess_bill asli; F03 menjeda sebelum post_makloon_claim asli. Ini reproduksi interleaving tertentu, bukan load test atau bukti semua urutan concurrency.

### Perbaikan yang diperlukan

Semua penulis nilai/saldo bill—pembayaran, klaim, potongan, cancellation dan koreksi—harus memakai kontrak concurrency bersama. Membandingkan `$amount_paid + applied` dengan `$grand_total` terkini menutup arah F02, tetapi **tidak menutup F03** jika writer klaim masih menulis tanpa guard. Klaim harus memastikan grand baru tidak lebih kecil dari paid terkini atau secara eksplisit membuat supplier credit/advance dengan journal dan keputusan sah; jangan diam-diam membiarkan paid>grand.

Guard perubahan bill juga harus dikoordinasikan dengan jurnal dan kas sebagai operasi yang dapat dipulihkan. Menambahkan CAS setelah jurnal klaim sudah ditulis dapat meninggalkan jurnal tanpa perubahan bill ketika CAS kalah. Tentukan urutan claim/reserve, operation ID, commit/compensation, dan retry yang menjaga invariant seluruh dokumen, bukan sekadar menambah satu if.

### Kriteria penerimaan

- F02 dan F03 masing-masing berakhir dengan conflict aman atau hasil bisnis konsisten; tidak ada kas/jurnal yatim.
- Kontrol dua pembayaran biasa tetap satu200/satu409 untuk dua pembayaran80.000 pada tagihan100.000.
- Klaim normal40.000 kemudian bayar60.000 tetap berhasil; retry klaim tidak menggandakan efek.
- Uji pembayaran parsial/penuh versus klaim, cancel versus payment, klaim versus klaim, kegagalan GL dan retry setelah respons hilang.
- Rekonsiliasi grand/paid, daftar pembayaran, kas, saldo GL AP dan advance. Semua keputusan overpayment harus memiliki sumber dan jejak eksplisit.

## Hubungan dengan Gelombang 1

CX-13 meneliti race pada penerimaan output makloon; W2-005 meneliti race **sesudah receipt**, antara potongan tagihan dan pembayaran. FN-07 membahas cash manual/void; W2-004 membahas pembatalan bill turunan dengan tipe jurnal sumber berbeda. Tidak mengubah atau menutup tiket lama. Koordinasikan pengembangan dengan P03/P11 Gelombang 1 karena area source bertumpang tindih.

## Batas coverage

Belum mencakup full HTTP create order/GRN/approval klaim, reversal pembayaran, semua pajak/UOM, seluruh laporan konsolidasi, scheduler/lifespan, indeks deployment lengkap atau browser UI. Hasil ini memperluas coverage PROD-05/APAR-01 tetapi keduanya tetap parsial. Temuan adalah konsistensi perangkat lunak pada fixture sintetis, bukan penetapan kebijakan akuntansi/pajak perusahaan.
