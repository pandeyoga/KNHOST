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


## Sesi 2026-10-17 bagian 3 — LN-022-T03 koreksi setelah terbit (penjaga kredit ganda)
- Sebelum: nota kredit/debit tidak mengubah item pesanan, sehingga amandemen kedua dengan harga target yang sama dihitung lagi dari harga ASAL → nota kredit kedua (kredit ganda). Dua usulan pending pada baris yang sama juga bisa sama-sama di-ACC.
- Sesudah (`services/amendment_service.py`):
  - `_note_baseline`: untuk dokumen terbit (`note_only`), pembanding = item asal + perubahan nota yang sudah diterapkan. Usulan ulang ke nilai yang sama → 400 "sudah dikoreksi oleh nota sebelumnya"; koreksi lanjutan (0,9 → 0,8) hanya mengkredit selisihnya.
  - Usulan baru pada produk/field yang masih punya amandemen nota pending → 400.
  - `decide(approve)` untuk nota memeriksa nilai "dari" masih sama dengan nilai efektif terkini (`_assert_note_still_valid`) SEBELUM klaim status.
  - Retest iteration_214 → diperbaiki: (a) satu amandemen nota pending per pesanan (harga, diskon baris, diskon pesanan saling memengaruhi → tidak over-credit); (b) usulan nota bersamaan: hanya yang paling awal bertahan (`_yield_to_earlier_note`); (c) Nota Kredit sesudah Nota Debit yang belum ditagih di-offset ke DN (`open_amount`, `offsets`, status DN `offset_by_credit_note`), hanya sisa yang memotong piutang/jurnal.

## Sesi 2026-10-17 bagian 4 — LN-023 (implemented_pending_validation)
- T01 — sebelum: aging piutang menjumlah seluruh sisa SO terbuka (termasuk confirmed belum dikirim) sebagai "Total Piutang", sedangkan GL hanya mengakui 1-1200 per surat jalan. Sesudah: `ar_aging_service` memecah tiap "belum lunas" menjadi `ar_ledger` (pendapatan diakui − pembayaran, = saldo 1-1200 pesanan) dan `exposure` (belum dikirim/diakui), per pesanan/pelanggan/total + `definitions`. UI `ARAgingView`: KPI "Total Belum Lunas", strip `ar-ledger-exposure` (`ar-ledger-total`, `ar-exposure-total`), kolom detail `ar-detail-split-<order>`. Mesin kredit (limit) tetap memakai belum lunas penuh (perilaku lama, disengaja).
- T02 — sebelum: short-close PO hanya mengubah status. Sesudah: `services/po_close_settlement_service.py` menyimpan `close_settlement` sekali saat tutup-kurang (nilai order/terima/dibatalkan, ditagih, dibayar, `unbilled_received`, `over_billed`, `over_paid`, `balanced`, `follow_ups`) + notifikasi Finance. API `GET /api/purchase-orders/{id}/close-settlement`. UI panel `po-close-settlement` di detail PO. Tanpa jurnal/ubah receiving.
- T03 — retry: close kedua 400 tanpa efek; `close_settlement` ditulis sekali; dialog kwitansi AR desktop kini mengirim `Idempotency-Key` (middleware yang sudah ada) — kunci baru setelah respons gagal.

- Tes: `test_l02_ln022_t03_amendment_note.py` + `_extended.py` + `_edge.py` 24/24 (termasuk `test_repeat_same_price_correction_does_not_double_credit`, `test_second_correction_credits_only_increment`), regresi LN-022 special price + form path lulus.

- T01 lanjutan (sesi 2026-10-18): pecahan ledger/eksposur juga di `compute_customer_credit` (`ar_ledger`, `exposure`), KPI sales/manager/admin home, Sales Force KPI, Customer 360, Order Journey (`journey-ar-split`), HP: beranda sales & detail pelanggan (`m-customer-ar-split`). Label "Piutang Belum Lunas"/"Piutang terbuka" → "Belum Lunas" + sub "Piutang ledger · eksposur". Header rincian aging: `normal-case` + total ledger/eksposur.

- Validasi (sesi 2026-10-18, repo di-clone ulang): iteration_216 — backend 11/12, frontend 100% (semua permukaan menampilkan pecahan, angka cocok dengan API). Bug: journey pesanan cancelled/expired masih menampilkan sisa & eksposur. Perbaikan `order_journey_service.journey()`: sisa = 0 bila dibatalkan; langkah "Dibayar" berbunyi "Pesanan dibatalkan — tidak ada tagihan". iteration_217 — 15/15 lulus.
- Catatan terbuka: (a) pesanan `waiting_approval` ikut dihitung eksposur (perlu konfirmasi bisnis); (b) KPI sales hanya dari `customers.assigned_sales_id` (data demo sebagian tanpa assigned_sales_id); (c) kolom TOTAL daftar SO = DPP, sedangkan journey/AR = termasuk PPN.

