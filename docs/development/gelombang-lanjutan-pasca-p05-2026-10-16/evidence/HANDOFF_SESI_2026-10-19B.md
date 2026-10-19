# Handoff sesi 2026-10-19 (lanjutan, implementasi keputusan owner)

Dikerjakan & di-push ke main (commit 746c970, 8dab383, 99805d1, 40b51f9, c90dff1):
1. LN-083 KLR-08/09 — checklist hangtag/potong/bukti pengganti (peringatan, Finance catat keputusan saat settle); batas customer pada tanggal pengajuan; supplier sampai klaim dikirim (`claim_window_check`).
2. LN-092 KLR-01/02/06/07 — cutloss (qty cacat yard, konversi kg otomatis, harga transaksi neto), diskon nominal per item boleh dari foto/video; izin baru `sales_return.record_cutloss`, `sales_return.decide_compensation`.
3. LN-090 KLR-03/04/05 — pesanan pengganti nyata (SO biasa, harga asal sekali pakai, saldo retur → selisih ditagih / sisa saldo).
4. LN-091 KLR-10/11 — nego: customer pilih refund/saldo; penanggung 3 jenis ongkir per kasus (dicatat, tanpa posting otomatis).
5. LN-093 KLR-09 — catatan (tanpa perubahan alur tambahan).
6. LN-014/040 KLX-01 — LOT pabrik + LOT KN (input bebas); LOT KN baru per penerimaan/SJ.
7. LN-052 KLX-02 — grade/poin/kode cacat diisi QC; status aturan `manual_user_input`.
8. LN-024 KLX-03 — cutoff/tanggal bayar/acuan per PT pembayar.
9. LN-101 OPS-01 — diverifikasi tidak ada ambang nilai kerugian.

Testing agent: iteration_klr_klx_ops_1 — backend 40/40, UI lulus.
Masih pending (owner minta penjelasan): DATA-01, DES-02, DES-03, DES-04, HW-01, HW-02, HR-01, UAT-01. Duplikasi D1–D8 belum disetujui (tidak diubah).
Belum: grade sama pada alokasi roll pengganti; posting otomatis ongkir; pemecahan fisik roll cutloss di stok.
