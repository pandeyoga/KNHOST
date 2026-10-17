# Laporan Fase L02 — status `in_progress` (2026-10-17, agent E1)

Belum ber-SHA GitHub. Dikerjakan: LN-022 (T01/T02) dan LN-021-T03 sebagian. LN-020, LN-023, LN-021-T01/T02 belum diuji ulang terhadap acceptance; LN-024 menunggu KLX-03.

## Navigasi aktual
- Pesanan → Detail SO → panel Persetujuan (`SoApprovalsPanel`) → "Ajukan harga khusus" / ACC oleh manager.
- Pesanan → Detail SO → Ganti Roll (`POST /api/sales-orders/{id}/items/{pid}/reallocate`, izin inventory.pegging).

## LN-022 — approval harga terikat produk + versi alokasi
- Sebelum: `routers/so_approvals.py` menyimpan `item_index` dan saat ACC menulis harga ke `items[idx]`. Bila baris dihapus/diurutkan ulang, harga tertempel ke produk lain atau hilang; pengajuan lama yang masih pending tetap bisa di-ACC dan menimpa pengajuan baru.
- Sesudah:
  - Entri menyimpan `alloc_sig` = produk + qty + satuan + roll yang benar-benar ter-reserve (whole roll & reservasi potong) pada saat pengajuan.
  - ACC mencari baris lewat `product_id`; bila produk sudah tidak ada → 409; bila `alloc_sig` berbeda (qty diubah lewat override, roll diganti) → 409 "ajukan ulang". Validasi dilakukan SEBELUM klaim atomik (tidak meninggalkan kunci).
  - Pengajuan baru untuk produk yang sama menandai pengajuan pending lama `superseded` (SO dan `price_approvals`), sehingga versi lama tidak dapat menimpa (409 saat ACC). UI: status "Digantikan pengajuan baru".
- SATU pintu (temuan iteration_210): form UI "Ajukan Harga Khusus" (`SpecialPriceRequestForm`: draf → bukti → submit di `/price-approvals`) sebelumnya membuat dokumen lepas yang tidak masuk gerbang SO dan ACC-nya tidak mengubah harga SO. Kini `submit` untuk `scope=order`+`so_id` memanggil `attach_order_price` (entri SO + `alloc_sig` + supersede, klaim atomik); `/price-approvals/{id}/approve|reject` untuk dokumen tertaut SO didelegasikan ke `decide_approval` (SoD tetap dicek); PATCH pengajuan pending tertaut SO → 409. Baris yang di-ACC ber-`price_source=special_approval` (lencana "Harga khusus").
- T03: pengajuan harga tetap hanya untuk status terbuka (draft/reserved/waiting_*) — invoice terposting tidak diedit (perilaku lama dipertahankan).

## LN-021-T03 — detail SO mengikuti alokasi terbaru
- Ganti Roll pada baris mode roll kini memperbarui `items[].roll_lines` (sebelumnya tetap roll lama). Tugas gudang hanya lahir saat confirmed, sedangkan Ganti Roll hanya sebelum confirmed → tidak ada dispatch lama yang tertinggal.

## Bukti
- `backend/tests/test_l02_ln022_special_price.py` 4/4: pengajuan kedua menggantikan pertama (ACC lama 409, harga = 22222); baris P1 dihapus → harga P2 tetap pada P2; qty diubah → ACC lama 409 lalu ajukan ulang OK; Ganti Roll → ACC lama 409.
- `tests/test_iter275_g1_admin_sales_audit.py` tidak bisa jalan (akun lama sales@ tidak ada di data acuan sekarang) — bukan regresi.

## Sesi 2026-10-17 bagian 2 — retest LN-022 + LN-020 + LN-021-T01/T02
### LN-022 (lanjutan, iteration_211)
- SoD juga di `decide_approval` (panel SO): pengaju tidak bisa memutuskan harga khususnya sendiri → 403.
- Klaim SO di keputusan dibungkus try/finally; cek `alloc_sig` dijalankan sesudah klaim.
- DELETE `price_approvals` tertaut SO yang pending → 409. Kartu Pusat Persetujuan tidak menampilkan Ubah/Hapus untuk pengajuan itu.
- Keputusan lewat SO kini menulis `approved_by(_name)` ke dokumen pra; bukti dari form ikut ke `evidence` entri SO.
- Tombol "Ajukan Harga Khusus" di panel SO tersedia untuk Admin Sales.
- Tes: `test_l02_ln022_special_price.py` 5/5, `test_l02_ln022_ln021_extra.py` 4/4, `test_l02_ln022_form_path_retest.py` 6/6.

### LN-020
- T01 — sebelum: `sales_stock_summary` menghitung roll `available` yang sebagian sudah dikunci potong (`length_reserved`) seluruhnya sebagai Bebas (satu panjang terhitung dua kali). Sesudah: bagian `length_reserved` masuk Dikunci, Bebas = sisa. Respons kini membawa `atp_definition` + `atp_horizon_days`; UI `SalesStockSummary` menampilkan "Datang … (belum siap kirim) · Menunggu … · ATP …" dan definisinya (`sales-stock-atp-definition`).
- T02 — sebelum: antrean Keep/Pending hanya untuk izin `order.verify` (Sales tidak punya jalan). Sesudah: `GET /api/sales/keep-pending` menerima `order.view`; peran ber-kunci pemilik (sales) dibatasi ke SO miliknya (`sales_ownership.apply_scope`). Panel `KeepPendingPanel` (prefix `sales-kp`) dipasang di Beranda Sales. Isi pending: produk → SO → dokumen sumber PR/PO/MKO/interco + ETA, tanpa nama pemilik/supplier.
- T03 — sebelum: daftar SO & panel ringkas menjumlah qty semua baris (yard + kg tercampur). Sesudah: `utils/qtyByUnit.js` menampilkan qty per satuan + jumlah roll ("905 yard (9 roll) · 50 kg (2 roll)"); detail (`QtyDual`) dan cetak (kolom roll per baris) sudah benar sebelumnya.
- Belum: "riwayat Sales rotating Tasik/Tamim" — perlu data penugasan nyata untuk diuji.

### LN-021
- T01 — sebelum: `compute_roll_reconcile` opsi turun selalu membuang roll FEFO terakhir; dengan 9×100 + 1×105 dan target 1000 hasilnya bisa 900/9, bukan 905/9. Sesudah: buang roll terpendek yang panjangnya ≥ kelebihan → turun = set utuh terbesar ≤ target (905/9), naik 1005/10; SO turun menyimpan qty 905, 9 roll_lines, `roll_rounding.choice=round_down`.
- T02 — dua SO bersamaan dengan 10 roll yang sama: semua roll hanya dikunci satu SO; SO kalah tidak memegang roll (tanpa perubahan kode, perilaku existing).
- Tes: `backend/tests/test_l02_ln020_ln021.py` 3/3 (fixture produk/roll TEST_ dibuat & dihapus sendiri).

