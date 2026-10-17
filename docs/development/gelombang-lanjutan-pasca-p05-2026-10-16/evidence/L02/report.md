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
