# Laporan Fase P04 — Sales, Keep/Pending, roll picker, kuantitas SO, dan grade

## Identitas

- Branch dan commit baseline: `main` @ `24fdbeb` (hasil P03), preview di-seed ulang mengikuti `deploy/setup_demo_lengkap.sh`
- Commit implementasi: P04 di atas `6485da9` (commit "Save to GitHub" berikutnya)
- Commit yang diuji: preview 2026-10-11 (iteration_178)
- Pelaksana: agent development · validator: pemilik (belum)
- IMP: IMP-02, IMP-03, IMP-04, IMP-05, IMP-06, IMP-11 · ditambah penuntasan ACC-16 (P03 kaki pelanggan Jakarta)
- Status: implemented_pending_validation

## Penuntasan P03 — kirim dari Jakarta (ACC-16)

Diuji end-to-end di preview (iteration_178): KANDA/SO-00003 → KANDA/TRF-00001 (SRG-01 Soreang → GU-KANDA Jakarta) diterima 10 roll → tugas Soreang batal, tugas Jakarta lahir → 10 scan-pick di Jakarta → loading check di-override manajer (roll demo tanpa RFID) → dispatch → **KANDA/SJ-00002** dari Jakarta berisi 10 nomor roll RL (bukan id internal) → SO `shipped` → mark-delivered → `done`. Tidak ditemukan bug. Catatan: uji faktur = qty kirim dilewati (endpoint faktur bukan publik di skrip uji).

## Perubahan perilaku

| Area | Sebelum | Sesudah |
|---|---|---|
| Keep (IMP-02) | Tidak ada daftar Keep; "Keep" tidak terdefinisi | Daftar Keep = SO belum diverifikasi Admin Sales, umur hari, tanda "lewat batas" bila melewati `sales.keep_max_age_days` (Pusat Pengaturan, global/entitas, 0 = tanpa batas). Tidak membatalkan, tidak menahan/melepas stok. |
| Pending (IMP-03) | Backorder hanya per SO | Daftar per produk × satuan (tidak menjumlah satuan berbeda) → SO terkait → dokumen pemenuhan nyata dari keputusan Admin Sales (transfer PT lain / PR→PO / tunggu). PR tanpa PO ditulis "PR belum menjadi PO"; ETA kosong tampil "belum diketahui". |
| Dalam Perjalanan | — | Roll berkomitmen SO yang masih di transfer tampil di tab sendiri, tidak dihitung Pending (DEC-01). |
| SO unik | — | Hitungan SO unik Keep ∪ Pending; SO yang keduanya dihitung sekali (`counts.both`). |
| Ringkasan stok Sales (IMP-04) | Hanya total | `GET /api/sales/stock-summary`: baris Reguler (non-BS) dan BS terpisah; fisik / dikunci / bebas / ditahan / transit / datang / ATP tidak dicampur; stok PT lain hanya angka "grup" berlabel keputusan Admin Sales; tanpa LOT/pemilik. Tampil di quick view Kasir. |
| Ganti Roll (IMP-05) | Hanya roll available milik entitas | `GET /api/sales-orders/{id}/items/{pid}/roll-candidates`: semua roll fisik produk dengan kelayakan + alasan (dikunci SO lain + nomornya, milik PT lain, karantina/ditahan/transit, sedang dipicking, BS terpisah, grade tidak diterima pelanggan). Modal Ganti Roll menampilkan grade, rekomendasi, dan daftar "Roll tidak layak". Server merevalidasi grade saat reallocate (409). |
| Grade (IMP-11) | Tidak ada aturan pelanggan | Form "Aturan Grade Pelanggan" di Meja Admin Sales (grade diterima, prioritas, terima BS, catatan, riwayat 30 perubahan). Rekomendasi hanya muncul bila aturan ada, disertai alasan; Admin Sales tetap memutuskan. Harga jual sudah tidak bergantung grade (pricelist/kontrak tidak membaca grade) — tidak diubah. |
| Qty roll utuh (IMP-06) | Mesin W2-REQ-09: qty baris = total roll final | Dipertahankan sesuai DEC-13 (tagihan = qty roll aktual dikirim). Tidak ada perubahan kode. |

## File dan consumer

| File | Perubahan | Kebutuhan |
|---|---|---|
| `backend/services/sales_p04_service.py` | baru — keep_pending, aturan grade, kandidat, revalidasi, ringkasan stok | IMP-02..05, 11 |
| `backend/routers/sales_p04.py`, `server.py` | endpoint baru | semua |
| `backend/routers/sales_orders_extra.py` | reallocate: revalidasi grade/BS → 409 | IMP-05, 11 |
| `backend/config_catalog_core.py` | `sales.keep_max_age_days` | IMP-02 |
| `backend/scripts/seed_p04_kn.py`, `deploy/setup_demo_lengkap.sh` (5g) | data CONTOH | — |
| `frontend/src/features/sales_admin/KeepPendingPanel.jsx`, `PendingProductRow.jsx`, `CustomerGradeRulesCard.jsx`, `SalesAdminDesk.jsx`, `sales/mobile/MobileSalesAdminDesk.jsx` | panel & form | IMP-02, 03, 11 |
| `frontend/src/features/orders/ReallocateRollsModal.jsx` | kandidat berkelayakan + rekomendasi | IMP-05, 11 |
| `frontend/src/components/SalesStockSummary.jsx`, `ProductQuickView.jsx` | ringkasan stok Sales | IMP-04 |

## Keputusan bisnis (pemilik via chat 2026-10-11)

- DEC-01 confirmed: Keep ada batas yang dapat dikonfigurasi (disimpan di pengaturan sistem); transit berkomitmen SO = bukan Pending ("dalam perjalanan").
- DEC-04 sebagian: BS tampil sebagai pilihan "BS" terpisah; aturan pelanggan-grade belum ada → form. Matriks harga BS masih open.
- DEC-13 sebagian: tagihan selalu ikut qty roll aktual dikirim. Write-off roll hilang dll. masih open.
- DEC-08 tetap open (tidak diubah sesuai pemilik).

## Migrasi dan rekonsiliasi

Tidak ada migrasi stok/jurnal. Koleksi baru `customer_grade_rules` (kosong). Data contoh `seed_p04_kn.py` (idempoten, flag `migrations.p04_demo`): KANDA/SO-00004 (Keep, umur 5 hari [CONTOH]), KANDA/SO-00005 (Keep + Pending 250), KANDA/SO-00006 (Pending 250, terverifikasi), batas Keep entitas Kanda = 3 hari [CONTOH].

## Hasil pengujian

| ACC/test | Lingkungan | Expected vs actual | Hasil |
|---|---|---|---|
| ACC-16 | preview, iteration_178 | dua kaki Soreang→Jakarta→pelanggan | lulus uji developer |
| ACC-21 | API + UI desktop/390px | Keep/Pending terpisah, SO unik tidak ganda | lulus sebagian (supply parsial & batal baris belum) |
| ACC-23/24 | API stock-summary sebagai sales | tanpa LOT/pemilik; fisik/bebas/ATP terpisah | lulus uji developer |
| ACC-25 | API kandidat + modal | alasan tak layak tampil; 409 grade diuji di service | sebagian |
| ACC-28 | API aturan grade | 422 grade tak sah / prioritas di luar diterima; rekomendasi beralasan | lulus uji developer |
| ACC-22, 26, 27 | — | — | not_run |

Bukti: `/app/test_reports/iteration_178.json`, `backend/tests/test_p03_p04_e2e.py` (backend 19/19 non-skip, UI 100%).

## Issue terbuka

- Pending jalur produksi (MKO) menunggu P05/P10.
- Aturan grade belum berisi data pelanggan nyata.
- Ganti Roll grade 409 belum diuji lewat UI (demo tanpa roll non-A pada produk SO contoh).
- Fase siap dimulai berikutnya: P05 (dependensi P01, P02) atau P07 (P02, P04).
