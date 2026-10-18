# Laporan Fase P02 — Alamat, putaway, integritas referensi, dan rules WMS

## Identitas

- Branch/commit implementasi: `main` @ `765b099` (di atas `e43e7d2`).
- Pelaksana: agent developer. Reviewer/validator: belum ditetapkan.
- Tanggal & lingkungan uji: 2026-10-11, container preview, DB data acuan (import master + stok awal, `seed_demo_lengkap_kn`, `seed_demo_transaksi_kn`, `seed_demo_harga_internal_kn`, `seed_simulasi_bin_kn`, `seed_p01_kn`, `seed_p02_kn`).
- IMP: IMP-22, IMP-23, IMP-24, IMP-25. Status: **implemented_pending_validation**.

## Keputusan bisnis (DEC-10, dikonfirmasi pemilik 2026-10-11)

| Topik | Keputusan |
|---|---|
| Satuan kapasitas | Jumlah roll per bin (`capacity_rolls`). Field lama `capacity` (meter) hanya informasi. |
| Melebihi kapasitas | Ditolak keras (409 `BIN_CAPACITY_FULL`), kecuali supervisor gudang (warehouse_admin, manager, admin) memberi pengecualian ber-alasan ≥5 huruf, tercatat di mutasi `putaway.capacity_override` + audit. |
| Kapasitas kosong | Tanpa batas; utilisasi "belum diatur" (tidak ada angka fiktif). |
| QC/hold | Roll quarantine/hold/blocked/damaged atau `inspection.hold.held` hanya ke node berfungsi `qc` (diwarisi zona→lemari→tingkat→bin). In-transit/offsite/consumed selalu ditolak. |
| Campur SKU/lot | Boleh, kecuali node diberi aturan `single_sku` / `single_lot` (diwarisi). |
| Saran bin | SKU+lot sama → SKU sama → bin kosong → lainnya; hanya bin yang lolos evaluator. |
| Hak ubah struktur | warehouse_admin, manager, admin (peran kustom mengikuti peran acuan). |
| Istilah | Lokasi › Gudang › Zona › Lemari/Rak › Tingkat › Bin — "Lemari/Rak" dan "Tingkat" adalah label tampilan node `rack`/`level` yang sama. |

## Perubahan perilaku

| IMP | Server | UI |
|---|---|---|
| IMP-22 | Satu resolver `placement_rules.resolve_bin` (id/kode, format lama `rack.bins` & baru `rack.levels[].bins`) dipakai putaway manual, scan penerimaan, evaluasi & saran. Satu jalur tulis `location_service.place_roll` (evaluasi → kunci bin → evaluasi ulang → CAS status+bin lama → mutasi). Endpoint baru `GET /api/inventory/putaway/suggest`, `GET /api/inventory/putaway/evaluate`. | Tab Putaway: alasan terhambat per roll, "Saran bin" (chip), pemeriksaan bin sebelum simpan, pengecualian kapasitas untuk supervisor. Scan penerimaan: daftar bin dari kedua format + kotak pengecualian. |
| IMP-23 | `flatten_bins` membawa path lengkap, fungsi, kapasitas roll, aturan efektif; ID node dipertahankan saat ganti nama/pindah. Skrip `migrate_p02_lokasi.py` (dry-run bawaan, `--apply`) mengubah rak lama ke Tingkat ber-id tetap `<rack_id>_lv1`, ID bin tidak berubah, rerun tidak menggandakan. | Editor struktur memakai label Zona/Lemari/Rak/Tingkat/Bin; judul menampilkan hierarki lengkap + lokasi/gudang aktif. |
| IMP-24 | Evaluator `evaluate_pure` (tanpa I/O) sama untuk saran & aksi akhir: status fisik, gudang roll, owner shared/dedicated, rules gudang + node AND (kategori, grade, jenis kain), fungsi QC, 1 SKU/1 lot, kapasitas roll (isi dihitung semua owner). Kunci per bin (`bin_locks`, TTL 15 dtk) untuk balapan. PA: `create_order`, `suggest` dan pendaratan (`_land_items`) memakai `warehouse_violations` (DEV-F05). Transfer: setiap roll yang dipesan dicek terhadap rules gudang tujuan (DEV-G04). `check_storage_rules` sekarang AND (DEV-G02); mode gudang baru `combined` + `fabric_types`. | Panel aturan per node (fungsi area, kategori, grade, jenis kain, 1 SKU, 1 lot). Profil gudang: mode "Gabungan". |
| IMP-25 | Simpan struktur menolak hapus bin yang masih berisi roll fisik / tugas aktif (409 `LOCATION_IN_USE`), ID ganda, kode bin ganda/kosong. Okupansi per satuan (`occupied_by_unit`), `orphan` & `unassigned` per satuan, `capacity_rolls_total`. `GET /api/warehouses/{id}/orphans`, `POST /api/inventory/rolls/{id}/fix-location` (alasan wajib, `location_corrections`). | KPI Alamat Yatim + tab koreksi; KPI terisi per satuan (label meter tetap dihapus — DEV-F03). |

## Data lama dan migrasi

- Resolver membaca kedua format, jadi migrasi struktur bersifat opsional. Dry-run pada data acuan: 90 rak lama di gudang format lama; ID bin tetap.
- Alamat yatim tidak dipindah otomatis; masuk daftar exception dan tetap terhitung fisik.
- `seed_p02_kn.py` (langkah 5e `deploy/setup_demo_lengkap.sh`) mengisi **CONTOH**: Zona Q · Karantina QC (4 bin, 10 roll), Rak W01 Tingkat 1 berkapasitas roll, W-OVER-01 kapasitas 3, Tingkat 2 "1 SKU", Tingkat 3 "grade A". `--hapus` mengembalikan.
- `seed_p01_kn.py`: pemetaan akun juga mengisi akun yang punya daftar site kosong (sebelumnya terlewat).

## Hasil uji

| Skenario | Hasil | Bukti |
|---|---|---|
| ACC-06 Resolver modern/legacy | pass | iteration_174 |
| ACC-07 Menu dan putaway | sebagian (peran kustom & mobile belum) | iteration_174 |
| ACC-08 Status fisik | pass | iteration_174/175 |
| ACC-09 Padanan Lemari/Rak | sebagian (cetak label bin belum) | iteration_174 |
| ACC-10 Hapus/pindah struktur | pass | iteration_174/175 |
| ACC-11 Shared/dedicated | sebagian (evaluator unit; PA end-to-end belum) | iteration_175 |
| ACC-12 Rules gabungan | pass | iteration_175 |
| ACC-13 Kapasitas & balapan | pass | iteration_174/175 |
| ACC-45 Mixed unit & kapasitas | fondasi P02 selesai; dashboard P08 | iteration_174 |

Testing agent: iterasi 174 backend 13/14 (1 dilewati karena data acuan, diperbaiki), UI 100%; iterasi 175 backend 7/7. Gate: DEV-F01–F05 dan DEV-G01/G02/G04 terverifikasi di lingkungan uji; kontrol C01 (hold ditolak ke storage) tetap jalan.

## Issue terbuka

- Transfer: rules tujuan dicek saat transfer dibuat, belum diulang saat diterima (barang sudah tiba).
- Transfer antar badan usaha (inter-company) belum memakai evaluator rules gudang tujuan.
- Peran kustom, tampilan mobile/handheld, dan cetak label bin belum diuji.
- Angka kapasitas & aturan adalah contoh; kapasitas nyata per bin perlu diisi kepala gudang.
- Seed transaksi demo di preview: 2 skenario (pembelian_parsial, penjualan_sukacita) gagal saat dijalankan ulang di atas data yang sudah ada — di luar P02, perlu dicek di VPS.
