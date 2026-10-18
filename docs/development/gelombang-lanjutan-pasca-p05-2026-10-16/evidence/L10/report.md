# L10 — Evidence report

## Sesi 2026-10-18 — LN-100 + LN-102 (in_progress: implementasi sebagian, belum diuji testing agent)

Navigasi aktual: Gudang → Lokasi Gudang & Penempatan Rak (`?view=wms-locations`) → tab **Stok per Alamat** (`lp-tab-stock`, panel `stock-tree-panel`, filter pemilik `stock-tree-owner`, node `st-node-<id>`, alamat `st-address-<binId>`); tab Struktur Lokasi (simpan → dialog alasan migrasi bila perlu).

### Route/API
| Method · path | Izin | Hasil | Error |
|---|---|---|---|
| GET `/api/warehouses/{id}/stock-tree?owner=` | `warehouse.view` + lingkup lokasi kerja | pohon Gudang → Zona → Lemari → Rak → Bin (+ Belum ditempatkan / Alamat yatim / Dalam perjalanan), per satuan: available, reserved, qc_hold, wip, in_transit, total; `by_owner`; `definitions` | 403 owner di luar akses, 404 |
| GET `/api/warehouse-sites/{site}/stock-tree?owner=` | sama | Lokasi → gudang-gudangnya (total lokasi = jumlah gudang) | 404 |
| PUT `/api/warehouses/{id}/structure` | existing + `migration_reason` | bin berisi roll/tugas yang pindah induk, atau kapasitas roll di bawah isi → 409 `LOCATION_MIGRATION_REASON` (daftar perubahan); dengan alasan ≥5 → tersimpan + catatan `location_migrations` (from/to path, roll, tugas) | 409 |

### Sebelum → sesudah
- Sebelum: okupansi hanya per bin; istilah "Lemari/Rak" + "Tingkat" menyatukan lemari dan rak; pindah bin berisi stok antar tingkat diam-diam mengubah alamat; kapasitas boleh diturunkan di bawah isi.
- Sesudah: istilah UI Lokasi → Gudang → Zona → **Lemari** (rack) → **Rak** (level) → Bin; stok per tingkat dari saldo roll (SSOT), induk = jumlah anak, satuan dipisah, QC/ditahan & roll diklaim perpindahan tidak dihitung tersedia; owner hanya filter/rincian (bukan node). Migrasi struktur eksplisit & tercatat; roll tetap di bin yang sama (ID bin tetap).
- Tanpa perubahan schema roll; koleksi baru `location_migrations`.

### Uji
- `backend/tests/test_l10_ln100_ln102_stock_tree.py` 3/3 (T01 induk=anak + owner/satuan + QC hold; T03 migrasi + kapasitas; akses). Jurnal tidak bertambah (LN-102-T03 dasar).
- Regresi: `test_p02_wms_putaway` 13/14 dan `test_p02_retest` 4/6 — kegagalan yang sama juga terjadi pada kode sebelum perubahan ini (bergantung data seed aturan bin), bukan regresi sesi ini.

### Belum
- LN-100-T02 (gudang shared, node woven-only) memakai aturan existing `rules.fabric_types`; belum diuji ulang dengan skenario CST/Sukacita.
- LN-102-T02 (kartu antrean Meja User → dokumen) memakai mekanisme existing `RoleDesk`; belum diverifikasi terhadap acceptance.
- Editor struktur belum punya aksi "pindah bin" di UI (guard tetap aktif di API). Testing agent belum dijalankan.


## Sesi 2026-10-18 (lanjutan) — uji LN-100/LN-102 + perbaikan + LN-101 (iteration_224)

### Perbaikan
- `_migration_changes`: bin yang sudah kelebihan isi dari data lama (W-OVER-01) tidak lagi memaksa alasan migrasi bila kapasitasnya tidak diubah.
- Meja Saya (LN-102-T02): antrean "Giliran saya" di-dedupe per dokumen (notifikasi berulang menggandakan count); tautan baris giliran memakai `row.link`; desk `me` memakai peta tujuan per jenis dokumen (tugas gudang → Barang Keluar, harga khusus → Persetujuan, retur beli, desain; PO "Terima" → Barang Masuk); baris tugas gudang menampilkan nomor SO + produk, bukan id mentah.

### LN-101 — opname per roll (implemented, menunggu OPS-01 untuk kebijakan hilang/asing)
Navigasi: Gudang → Operasi Gudang (`?view=operations`) → tab Stock Opname → Buat sesi → panel **Opname per Roll (scan)** (`roll-count-panel`).
| Method · path | Izin | Hasil |
|---|---|---|
| POST `/api/cycle-count/sessions/{id}/roll-scope` {node_id} | inventory.cycle_count | snapshot roll per scope node (zona/lemari/rak/bin), dibekukan; 409 bila sudah ada scan |
| POST `/api/cycle-count/sessions/{id}/roll-scans` {code,bin_id,measured_qty,tag} | inventory.cycle_count | klasifikasi: cocok, salah alamat, qty beda, tag rusak, tak terbaca, roll asing, kode tak dikenal, masuk setelah snapshot; scan ganda → `duplicate:true` (CAS, tidak menambah) |
| GET `/api/cycle-count/sessions/{id}/roll-reconcile` | inventory.cycle_count | + hilang, bergerak setelah snapshot (delta yang sudah diposting) |
| POST `/api/cycle-count/sessions/{id}/roll-finalize` {reason} | inventory.approve_count | terapkan salah alamat (lewat aturan bin yang sama dgn putaway; ditolak → exception) & qty beda (CAS vs saldo saat scan, jurnal `cycle_count_variance` idempoten per roll); roll berubah sesudah scan → `recount`; hilang/asing TIDAK di-adjust (OPS-01) |

Cutoff/delta: selisih = fisik − saldo live saat scan, jadi gerakan yang sudah diposting tidak diulang (LN-101-T02). Counter tanpa ACC → 403; finalisasi ulang → 400; jurnal 1× (LN-101-T03).

### Uji
- `tests/test_l10_ln100_ln102_stock_tree.py` 3/3, `tests/test_l10_ln101_roll_count.py` 3/3, `tests/test_l10_t1_review.py` (testing agent) 12/12.
- Testing agent iteration_224: backend 17/17, UI opname per roll & Stok per Alamat & Meja Saya berjalan. Temuan medium (relokasi melewati aturan bin) dan temuan kecil (label kind, kartu Item Count kosong, tombol finalisasi per izin, kebocoran info roll entitas lain saat scan, label scope) sudah diperbaiki.

### Belum / blocker
- OPS-01 pending: tindak lanjut roll hilang/asing & threshold adjustment.
- KPI "Terisi" di layar lokasi masih menghitung roll belum ditempatkan; urutan satuan per node belum seragam (kosmetik).
- Reviewer terpisah & persetujuan owner belum ada — status maksimal in_progress.


## Sesi 2026-10-18 (3) — KPI "Terisi di Rak" + SOP opname OPS-01 (iteration_225)
Keputusan owner (chat 2026-10-18): hilang → wajib hitung ulang lalu dihapus saat ACC; roll asing gudang sama → dipindah ke tempat ditemukan (gudang lain → transfer); kode tak dikenal → roll baru saat ACC (produk & pemilik ditetapkan penyetuju, lot baru OPN-<sesi>); penyetuju = inventory.approve_count; batas nilai kerugian tambahan: belum ada.
- API baru POST `/api/cycle-count/sessions/{id}/roll-missing-recount`; `roll-finalize` menerima `new_rolls[]` + `zero_cost_reason`.
- Pengaman: roll hilang yang masih dialokasikan/dipesan/dipindah → exception `missing_allocated` (tidak dihapus); qty berubah sejak snapshot → "bergerak setelah snapshot", bukan hilang.
- `GET /api/warehouses/{id}/locations` → `binned_rolls`, `binned_by_unit`; KPI layar "Terisi di Rak".
- Tes: test_l10_ln101_roll_count.py 4/4, test_l10_ops01_t1.py 8/8, test_l10_t1_review.py 12/12.

## Sesi 2026-10-18 (lanjutan): sisa LN-100
- **Editor struktur — aksi "Pindah ke…" per bin** (`lp-bin-<id>-move`): bin dipindah ke tingkat lain dengan ID tetap. Saat disimpan, bin berisi stok/tugas memicu 409 `LOCATION_MIGRATION_REASON` → UI meminta alasan, lalu migrasi tercatat.
- **LN-100-T02**: `test_lanjutan_sched_returns_interco.py::test_ln100_t02_shared_woven_node`. Pada gudang shared Rancamalang Woven dengan node woven-only, roll woven Sukacita & CST diterima tanpa gudang owner fiktif, sedangkan roll knit ditolak ("Jenis kain 'knit' tidak diizinkan … (hanya woven)").
- Masih terbuka: batas nilai kerugian opname (owner: belum ada) dan verifikasi LN-102-T02.
