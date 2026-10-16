# Gelombang 2 — detail temuan makloon

Commit `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Tanggal 30 September 2026. Data sintetis dalam Mongo lokal terisolasi. Bukti angka: [makloon-results.json](makloon-results.json). Fixture menyiapkan order draft dan bahan 10 meter @10, kemudian memanggil `issue_step` asli; create/wizard order tidak diuji. Tidak ada patch pada fungsi bisnis untuk memaksa hasil.

## W2-001 — toleransi jumlah membuat nilai roll berbeda dari jurnal penerimaan

**P1 · Runtime terkonfirmasi melalui API · W2-M-F01.**

Letak: [backend/services/makloon_order_service.py:918](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_order_service.py#L918), [backend/services/makloon_order_service.py:1021](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_order_service.py#L1021), [backend/services/makloon_order_service.py:1029](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_order_service.py#L1029), [backend/services/makloon_order_service.py:1062](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_order_service.py#L1062). UI juga memakai toleransi yang sama: [frontend/src/features/purchasing/MakloonOrderDetailPanel.jsx:455](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/purchasing/MakloonOrderDetailPanel.jsx#L455).

Kode membolehkan `abs(sum_rolls - actual_out) <= 0.5`. Namun unit cost dihitung dari `output_value / actual_out`, sementara roll fisik dibentuk dari masing-masing `r.length`. Jurnal memakai seluruh `wip_total`. Ketiga basis tersebut tidak direkonsiliasi setelah toleransi diterima.

Reproduksi: issue bahan 10 meter bernilai 100; terima output yang dilaporkan 10 meter, jasa 20, satu roll panjang 9,5 meter. `POST /api/makloon-orders/{id}/receive` mengembalikan 200 dan order completed. Nilai per unit 12, nilai roll **114**, tetapi debit persediaan/jurnal receipt **120**. Selisih 6 tidak dialokasikan atau dicatat sebagai selisih nilai. Ini bukan jurnal tidak balance: debit/kredit jurnal dapat seimbang sambil subledger persediaan salah terhadap GL.

Kontrol: jumlah 10 dan roll 10 menghasilkan nilai roll/jurnal sama-sama 120; retry ditolak 409 tanpa perubahan. Panjang 9,49 ditolak 400 sebelum roll/jurnal output lahir. Batas yang bermasalah justru selisih yang dianggap masih diperbolehkan.

Alur terdampak: penerimaan → roll dan balance → HPP ketika roll dijual/diproduksi → rekonsiliasi persediaan versus GL. Dampak ke penjualan belum dieksekusi dalam putaran ini; drift sudah terbukti saat receipt. Inspeksi source UI membuktikan form juga menerima selisih ini, tetapi belum dilakukan browser UAT.

Perbaikan: tetapkan satu basis quantity kanonik untuk costing; bedakan declared quantity dengan measured quantity. Jika toleransi operasional tetap diizinkan, nilai total yang dialokasikan ke roll harus sama dengan nilai kapitalisasi, dengan residual pembulatan terkontrol. Jangan sekadar menyeimbangkan jurnal tanpa memperbaiki subledger. Uji lebih/kurang di dalam toleransi, batas 0,5, multi-roll, konversi UOM, barang sisa, dan partial receipt.

## W2-002 — penerimaan makloon menerima gudang tujuan yang tidak ada

**P1 · Runtime terkonfirmasi melalui API · W2-M-F02.**

Letak: [backend/routers/makloon_orders.py:165](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/makloon_orders.py#L165), [backend/services/makloon_order_service.py:927](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_order_service.py#L927), [backend/services/roll_service.py:1505](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L1505).

Router memeriksa permission dan akses order, tetapi tidak memvalidasi `output_warehouse_id`. Service memilih ID itu dan meneruskannya ke penciptaan roll. Helper roll tidak memastikan keberadaan gudang. Sebagai pembanding kontrak dalam aplikasi sendiri, pembuatan GRN menolak gudang tidak ditemukan di [backend/services/goods_receipt_service.py:155](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/goods_receipt_service.py#L155).

Reproduksi: user entitas A dengan izin receive, order A valid, kirim `output_warehouse_id="NONEXISTENT-WAREHOUSE"`. API memberi 200, order completed, roll 10 meter dan jurnal 120 tercipta. Roll menunjuk gudang yang tidak terdaftar.

Alur terdampak: penerimaan final terlihat sukses tetapi lokasi stok tidak dapat dipetakan ke master gudang. Pengambilan, putaway, stock count dan rekonsiliasi per lokasi berisiko kehilangan visibilitas stok. Bukan bukti akses lintas entitas: pengujian khusus ini membuktikan referensi gudang tidak ada, bukan seluruh kebijakan gudang bersama/ownership.

Perbaikan: validasi gudang efektif setelah seluruh fallback ditentukan, sebelum konsumsi bahan atau child write. Gunakan kebijakan gudang yang berlaku dalam aplikasi untuk keberadaan, status dan izin pemakaian; jangan membuat aturan baru yang memblokir gudang bersama sah. Pusatkan pemeriksaan agar API langsung dan pemanggil internal konsisten. Uji ID tak ada, archived/inactive, fallback kosong, gudang sah dan kebijakan shared.

## W2-003 — penggabungan kiriman parsial kehilangan gudang kedatangan awal

**P1 · Runtime pada helper posting GRN dengan Mongo nyata · W2-M-F03.** Belum diuji melalui seluruh lifecycle HTTP GRN.

Letak: [backend/services/goods_receipt_close_service.py:311](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/goods_receipt_close_service.py#L311), [backend/services/goods_receipt_close_service.py:335](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/goods_receipt_close_service.py#L335), [backend/services/makloon_order_service.py:906](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_order_service.py#L906), [backend/services/makloon_order_service.py:927](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_order_service.py#L927), [backend/services/makloon_order_service.py:1029](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/makloon_order_service.py#L1029).

`_post_mko` menyimpan partial receipt berupa quantity/roll/nomor kedatangan, tetapi tidak menyimpan gudang kedatangan. Saat final receipt, roll parsial digabung dengan roll final dan seluruhnya dibuat memakai satu `out_wh` dari GRN final.

Reproduksi: helper posting menerima kedatangan parsial 4 meter di WH; kedatangan final 6 meter di WH2. Kedua gudang milik entitas fixture yang sama dan terdaftar. Hasil aktual: roll 4 meter **dan** roll 6 meter sama-sama di WH2. Tidak ada operasi transfer eksplisit untuk empat meter pertama. Total quantity dan nilai tetap bisa benar sementara distribusi lokasi salah.

Keberadaan dua gudang adalah fixture yang disengaja. Pembuatan GRN menerima gudang terdaftar dan pencarian open MKO tidak memfilter gudang (`goods_receipt_service.py:145–170`); namun putaran ini tidak menjalankan semua create/link/count/reconcile/close HTTP. Karena itu bukti definitif dibatasi pada kontrak helper posting. Wajib tambahkan end-to-end GRN sebelum menyimpulkan semua konfigurasi deployment terdampak.

Kontrol: penggabungan partial 4 + final 6 pada gudang sama menghasilkan dua roll total 10, nilai 120 dan jurnal 120. Cancel partial yang masih ditahan menghapus entry dan membatalkan GRN fixture; retry 404. Ini tidak membuktikan concurrency cancel-versus-final.

Perbaikan: jika multi-gudang diizinkan, simpan warehouse asal setiap kiriman/roll dan gunakan saat posting; perpindahan sesudah kedatangan harus lewat transfer yang memiliki jejak. Jika bisnis mewajibkan satu gudang per step, tolak mismatch sebelum staging/posting dan tampilkan alasannya. Data partial lama yang belum punya warehouse perlu resolusi dari GRN asal; jangan diam-diam memakai gudang final.

## Batas interpretasi

Tidak mengubah/menggabungkan status Gelombang 1. CX-13 tetap tiket concurrency tersendiri. Tiga ID baru adalah pelanggaran invariant yang berbeda meskipun lokasinya berdekatan. Semua angka adalah fixture teknis, bukan opini tarif pajak atau sign-off laporan keuangan. Full startup/lifespan, semua indeks deployment, UI, crash recovery dan perangkat belum diuji di putaran ini.
