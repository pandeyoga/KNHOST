# MP-T5 — Gudang greige/PFD/PFP: peruntukan, surat jalan wajib packing list, akses MD

- Commit awal: `d746702`        - Branch: `claude/nifty-carson-jjx3c8`
- Spesifikasi `docs/blueprint/unit/MP-T5.md` (pecahan 5a/5b/5c); keputusan K-74, K-75, K-76, K-77
- **Status: sebagian.** MP-T5c selesai (bagian ini); MP-T5a (surat jalan kirim bahan makloon + daftar roll) dan MP-T5b
  (peruntukan) belum dikerjakan. K-76 (satu gudang, satu admin) = pengaturan data gudang, bukan kode.

## MP-T5c — MD membeli bahan greige/PFD/PFP (K-77)

### Cek ulang
- MD bawaan sudah memegang `purchase_requisition` view/create/update dan `purchase_order.view` (`backend/permissions_config.py`
  peran `md`) — PR tidak dipersempit (MD sudah boleh meminta pembelian apa pun).
- PO butuh `purchase_order.create` (`backend/routers/purchase_orders.py:302`); tab "Pesanan Pembelian (PO)" di hub tidak
  menyertakan MD (`frontend/src/config/hubTabs.js:58`).

### Perubahan
- Izin baru `purchase_order.create_bahan` "Buat PO bahan (greige/PFD/PFP)" — bawaan Admin & MD; modul Pembelian & Pengadaan.
- `POST /api/purchase-orders`: boleh dengan `create` **atau** `create_bahan`; pemegang `create_bahan` saja ditolak 403 bila ada
  baris non-katalog atau bertahap di luar pengaturan `purchasing.material_purchase_stages` ("Akses Anda hanya untuk pembelian
  bahan (Greige …, PFD …, PFP …). MPT5-FINISHED-… bertahap Finished …").
- Pengaturan `purchasing.material_purchase_stages` (daftar tahap; bawaan greige, PFD, PFP; global → PT).
- Layar: tab "Pesanan Pembelian (PO)" untuk MD; pemegang izin terbatas melihat tombol "Buat PO bahan" (bukan menu PO/makloon)
  dan daftar barang di form hanya barang bertahap bahan.

### Uji penerimaan (`backend/tests_mem/test_MPT5c_md_beli_bahan.py`)
Merah sebelum kode: PO MD 403 ("…akses untuk membuat Pesanan Pembelian"), pengaturan tidak ada, aksi tidak dikenal.

| ID | Hasil |
|---|---|
| U1 | lulus — MD PR greige 200 |
| U2 | lulus — MD PO kain jadi 403 "hanya untuk pembelian bahan"; PR kain jadi tetap 200 |
| U3 | lulus — MD PO PFP 200 |
| U4 | lulus — pengaturan hanya greige → PO PFP 403 |
| U5 | lulus — Admin (pemegang `create`) PO kain jadi 200 |
| U6 | lulus — peran Tanpa Acuan (`purchase_order` view+create_bahan) 200; Manajer Kosong 403 |

Uji lama disesuaikan: `test_PRT9_izin_bawaan.py` (tambahan admin/md `create_bahan`), `test_KFT1_izin_pengaturan.py`
(`MPT5_KUNCI = 1` di U02/U04). Registri: KFT1, KFT8 (setelah `consumers` dibetulkan ke `_assert_material_only`), PRT5, PRT9 —
557 + 508 lulus; jest `src/config` 178 lulus. `verify_config_text` 0 pelanggaran.

### Cek layar (`bukti/MP-T5/uji_jalan_md_po_bahan.js`)
MD: tab "Pesanan Pembelian (PO)" tampil (`md-po-halaman.png`); tombol "Buat PO bahan" 1, menu PO lengkap 0; form terbuka tanpa
galat API (`md-po-bahan.png`). Catatan lingkungan: uji jalan pertama gagal karena server dev frontend lama masih berjalan
(pola `pkill` tidak cocok) — sesudah dinyalakan ulang, lulus.

### Asumsi
- ASUMSI: "pembelian" pada K-77 = PO; PR MD tidak diubah.
- ASUMSI: layar menyaring barang dengan tahap benang/greige/PFD/PFP; tahap sebenarnya ditegakkan server dari pengaturan.
