# MP-T5 — Gudang greige/PFD/PFP: peruntukan, surat jalan wajib packing list, akses MD

- Commit awal: `d746702`        - Commit akhir: `3ba2cad` (5c) · `01a6585` (5a/5b)        - Branch: `claude/nifty-carson-jjx3c8`
- Spesifikasi `docs/blueprint/unit/MP-T5.md` (pecahan 5a/5b/5c); keputusan K-74, K-75, K-76, K-77
- MP-T5a, MP-T5b, MP-T5c selesai. K-76 (greige/PFD/PFP satu gudang, satu admin) = pengaturan data gudang & penugasan
  admin, bukan kode — dilakukan pemilik/admin di data nyata.

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

## MP-T5a — Surat jalan kirim bahan makloon berisi daftar roll (K-75)

### Perubahan
- Koleksi baru `makloon_shipments` (per PT): satu surat jalan per pengiriman langkah SPK — nomor `SJM-` (jenis penomoran
  `msj`, per PT), dari (gudang, atau **mitra** bila diteruskan MP-T4a), ke mitra, barang, daftar roll (no roll, lot,
  panjang, grade), total roll & kuantitas, peruntukan. Dibuat otomatis oleh `issue_step` sesudah jurnal kirim
  (idempoten per SPK × langkah); `forward_step` menandai asal "mitra".
- Dokumen cetak `makloon_sj` "Surat Jalan Kirim Bahan Makloon" (`resolve_makloon_sj`): baris per roll, total, "Dikirim
  dari", "Peruntukan", tanda tangan penerima/pengirim.
- `GET /api/makloon-orders/{id}/shipments`; rincian SPK menampilkan "Surat jalan {nomor} · {n} roll · {qty}" per langkah
  dengan tombol cetak/kirim/tanda tangan dokumen yang sudah ada (`DocumentActionsBar`).
- SJ Transfer: bila transfer menyimpan roll per barang, dicetak per roll (Roll, Lot, Jumlah); total roll = jumlah baris.
- SJ penjualan sudah memuat daftar roll sebelum unit ini (tidak diubah). Nota Retur Beli tidak diubah (dicatat).

## MP-T5b — Peruntukan pengeluaran bahan (K-74)

### Perubahan
- SPK makloon menyimpan `purpose` {kind: pelanggan (customer_id → nama) · toko (nama toko) · stok}. Wajib bila tahap bahan ada
  di pengaturan baru `makloon.peruntukan_wajib_tahap` (bawaan greige/PFD/PFP): "Peruntukan wajib diisi untuk bahan …: pilih
  untuk pelanggan, untuk toko, atau stok." SPK dari PR tidak wajib (peruntukan mengikuti PR).
- Peruntukan tercetak di surat jalan kirim bahan. Wizard: isian "Peruntukan bahan" (+ pelanggan / nama toko).
- Seed data acuan (`seed_demo_transaksi_kn.py`) diberi peruntukan "stok" pada dua SPK berbahan greige/PFP.

### Uji penerimaan (`backend/tests/test_bp_MPT5_sj_peruntukan.py`, lapis A)
Merah sebelum kode: SPK greige tanpa peruntukan 200; tidak ada surat jalan.

| ID | Hasil |
|---|---|
| U1 | lulus — SPK greige tanpa peruntukan 400 "Peruntukan wajib …"; "Untuk toko AB" 200 dan tersimpan |
| U2 | lulus — kirim 4 roll → SJ `KSC/SJM-…` dari gudang ke mitra pre-treatment, 4 roll, 200 yd, peruntukan stok; teruskan 190 yd → SJ kedua dari **mitra** pre-treatment ke mitra printing, 2 roll; cetak: 4 baris, "Total Roll 4", "Peruntukan: Stok" |

Uji lama disesuaikan (perilaku sengaja diubah): fixture `test_bp_MPT4a_teruskan.py` dan `test_MPT2_spk_dari_rute.py`
diberi peruntukan "stok"; `test_KFT1_izin_pengaturan.py` (`MPT5B_KUNCI`); `test_KPT5a_setara.py` (`SJM-`) dan
`test_KPT5b_pengaturan.py` (+1 jenis `msj`). Uji terarah: makloon `tests_mem` (5 berkas) 106 lulus; KFT1/KFT8/KMT3 553
lulus; KPT5a/b 30 lulus; lapis A MP-T4a + MP-T5 5 lulus. `verify_config_text` 0 pelanggaran; `verify_ui_standard` tanpa
temuan untuk berkas unit ini.

### Cek layar
- PDF `bukti/MP-T5/sj_kirim_bahan_makloon_contoh.pdf` (KSC/SJM-00008): 2 roll × 95 yd, total 190 yd, "Dikirim dari … (mitra,
  diteruskan langsung)", "Peruntukan Stok".
- Rincian SPK KSC/MKO-00036: dua baris surat jalan (200 yd dari gudang; 190 yd dari mitra) dengan tombol dokumen
  (`1280-07-sj-rincian.png`); wizard: pilihan peruntukan + isian nama toko (`1280-08-wizard-peruntukan.png`).

### Asumsi
- ASUMSI: satu surat jalan per pengiriman langkah (bukan per truk); pengiriman ulang langkah yang sama tidak terjadi.
- ASUMSI: peruntukan dicatat di SPK (pengeluaran gudang greige ke mitra); transfer antar-gudang belum meminta peruntukan.
