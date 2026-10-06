# Gelombang 3 — Laporan Penutupan Implementasi (untuk reviewer independen)

Tanggal: 2026-10-06 · Disusun oleh agent pengembang · Bahasa: Indonesia

> Dokumen ini **bukan** verdict. Status tertinggi yang boleh dipakai agent adalah `implemented_pending_validation`.
> Verdict `verified_fixed / partially_fixed / still_open / needs_business_decision / not_reproduced_on_new_commit`
> hanya ditetapkan reviewer independen. `findings-tracker.json` baseline **tidak ditimpa** (masih `open` untuk 101 ID).

## 1. Identitas kode

| Item | Nilai |
|---|---|
| Commit baseline audit | `a904d98` |
| Actual HEAD sebelum perubahan Gelombang 3 | `f36ae37` |
| HEAD saat laporan disusun | `72cb55e` (`72cb55ee13a03eb0f05bfab3ec5d5b028b25261c`) |
| Commit implementasi | commit otomatis platform di antara `f36ae37` … `72cb55e` (satu commit per langkah) |
| Sumber status per ID | `implementation/FASE-01…05-STATUS.md` (rincian perubahan, file, bukti, batas) |
| Laporan uji agent | `/app/test_reports/iteration_162.json` … `iteration_171.json` |

## 2. Ringkasan

- **101 temuan** (cocok 1:1 dengan `findings-tracker.json`; tidak ada ID hilang/tambahan).
- **101 `implemented_pending_validation`**, 0 `partially_fixed`, 0 `open`, 0 `needs_business_decision` tersisa (semua keputusan bisnis dijawab pemilik, lihat §4).
- Prioritas: **63 P1 · 37 P2 · 1 P3**.

| Fase | Cakupan | Jumlah (P1/P2/P3) | Uji service (DB uji terpisah) | Uji live API | Iterasi testing agent |
|---|---|---|---|---|---|
| 01 | Atomisitas, retry, idempotensi ledger | 23 (20/3/0) | `test_g3_phase01.py` **28/28** | — | 162, 163 |
| 02 | Scope entitas, batas query, satuan, WMS | 23 (22/1/0) | `test_g3_phase02.py` + `test_g3_phase02b.py` **37/37** | `test_g3_phase02_api.py` | 164, 165, 166 |
| 03 | Master data, pembelian, harga, keuangan | 22 (17/5/0) | `test_g3_phase03.py` **22/22** | `test_g3_phase03_live.py`, `03b`, `03c` | 167, 168, 169 |
| 04 | Sumber angka, analitik, parser, KPI | 24 (2/22/0) | `test_g3_phase04.py` **17/17** | `test_g3_phase04_live.py` | 170 |
| 05 | Regresi, duplikasi, validasi penutupan | 9 (2/6/1) | `test_g3_phase05.py` **7/7** | `test_g3_phase05_live.py`, `test_iter149_audit.py::test_stock_atp_sum_matches` | 171 |

Hasil eksekusi ulang saat laporan disusun (HEAD `72cb55e`): service **111/111 lulus**. Live API lulus,
dengan catatan: `test_g3_phase03b_live.py` (7/7) dan `test_g3_phase03c_live.py` (10/10) **memakai satu PO seed yang
dimutasi** (`scripts/seed_test_po_variance.py`) sehingga harus dijalankan **terpisah, masing-masing dengan seed baru**.
Bila dijalankan berurutan pada satu seed, 03b mengubah qty lebih dulu dan 03c gagal karena urutan — bukan regresi.

## 3. Perintah reproduksi

```bash
cd /app/backend
DB_NAME=g3_audit_phase01 python -m pytest tests/test_g3_phase01.py -q -n 0
DB_NAME=g3_audit_phase02 python -m pytest tests/test_g3_phase02.py tests/test_g3_phase02b.py -q -n 0
DB_NAME=g3_audit_phase03 python -m pytest tests/test_g3_phase03.py -q -n 0
DB_NAME=g3_audit_phase04 python -m pytest tests/test_g3_phase04.py -q -n 0
DB_NAME=g3_audit_phase05 python -m pytest tests/test_g3_phase05.py -q -n 0
# live (butuh REACT_APP_BACKEND_URL; jangan jalankan 03b & 03c pada seed yang sama)
export REACT_APP_BACKEND_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
python -m pytest tests/test_g3_phase02_api.py tests/test_g3_phase03_live.py tests/test_g3_phase04_live.py tests/test_g3_phase05_live.py tests/test_iter149_audit.py::test_stock_atp_sum_matches -q -n 0
python ../scripts/seed_test_po_variance.py && python -m pytest tests/test_g3_phase03b_live.py -q -n 0 && python ../scripts/seed_test_po_variance.py --clear
python ../scripts/seed_test_po_variance.py && python -m pytest tests/test_g3_phase03c_live.py -q -n 0 && python ../scripts/seed_test_po_variance.py --clear
```

Uji service memakai database `g3_audit_*` yang dikosongkan per tes (guard: modul di-skip bila `DB_NAME` bukan `g3_audit*`).

## 4. Keputusan bisnis (dijawab pemilik, 2026-10-06)

| Fase | ID | Keputusan |
|---|---|---|
| 01 | D4-CASE-03 | Kelebihan setoran karyawan → kredit toko pelanggan; tanpa pelanggan ditolak |
| 01 | D4-INTERCO-02 | Nilai transfer = biaya aktual roll yang dipindah (snapshot) |
| 01 | D4-OD-LOCK-01 | Retry juga melanjutkan pembuatan PO otomatis |
| 01 | V3-AR-01 | Kwitansi gagal dihapus dan diarsipkan (`ar_receipt_failures`) |
| 02 | D4-RET-POLICY-01 | Asal tak terlacak → kebijakan retur penjualan + tanda "asal tidak diketahui" |
| 02 | V3-WMS-02 | Sesi cek muat per pengiriman (SO + gudang) |
| 02 | D4-PLAN-05 | Pasokan masuk hanya informasi, dibagi FIFO (SO tertua dulu) |
| 02 | D4-PA-01 | Reservasi dan putaway saling mengunci |
| 03 | V3-CF-01 | Hanya porsi tunai masuk arus kas; sisa nonkas |
| 03 | V3-PO-02 | Qty boleh diamandemen ke qty diterima; **selalu** persetujuan ulang |
| 03 | D4-FIN-04 | Realisasi = barang terkirim; nilai pesanan = estimasi terpisah |
| 03 | D4-CASH-01 | Kolom tetap "jenis kas"; data lama diisi otomatis sekali |
| 03 | D4-DATE-01 | Semua periode WIB |
| 04 | D4-STOCK-03 | Nilai persediaan = biaya penuh (dasar + landed, dirinci) |
| 04 | D4-AI-02 | Pelanggan baru = pembelian pertama di lini terpilih |
| 04 | D4-HR-02 | Turnover dari tanggal keluar resmi; data lama tanpa tanggal tidak dihitung, ditandai |
| 04 | D4-MKT-01 | Reach per platform/akun = atribusi bersama, tidak dapat dijumlah |
| 04 | D4-KPI-WEIGHT-01 | Bobot 0 sah dan tidak dihitung |
| 05 | D4-TEST-01 | ATP = tersedia + incoming(horizon) − permintaan tertunda |
| 05 | D4-ORDER-01 | Rata-rata = revenue terpenuhi ÷ jumlah pesanan terpenuhi periode sama |
| 05 | D4-FE-01 | Grafik velocity mengikuti periode terpilih |

Default agent (bukan keputusan pemilik, mohon ditinjau): tanggal tanpa zona = tanggal WIB (timestamp naif = UTC);
skor KPI 0–150 untuk jalur otomatis & manual; akurasi cycle count hanya dari hitungan selesai non-void;
payroll dari run `posted/paying/paid`.

## 5. Daftar per temuan

Kolom **Catatan uji** hanya diisi bila bukti lebih lemah dari uji service/fault-injection biasa.
Rincian perubahan & file per ID ada di `FASE-0x-STATUS.md`.

| ID | P | Fase | Judul ringkas | Status agent | Catatan uji |
|---|---|---|---|---|---|
| V3-PROD-01 | P1 | 01 | Konsumsi bahan berulang setelah insert movement gagal | implemented_pending_validation | |
| V3-PROD-02 | P1 | 01 | Reversal selesai sebelum panjang roll dipulihkan | implemented_pending_validation | |
| V3-AR-01 | P1 | 01 | Receipt gagal tetapi SO terbayar & deposit utuh | implemented_pending_validation | |
| V3-BANK-01 | P1 | 01 | Satu baris bank ke dua transaksi kas | implemented_pending_validation | |
| V3-MKO-01 | P1 | 01 | Retry penerimaan maklon menambah output | implemented_pending_validation | |
| V3-MASTER-01 | P2 | 01 | Apply master sebelum snapshot batch durable | implemented_pending_validation | |
| V3-CUT-01 | P1 | 01 | Gagal child cut menghilangkan stok/reservasi | implemented_pending_validation | |
| D4-GL-01 | P1 | 01 | Jurnal yang sudah dibalik masih dapat dianulir | implemented_pending_validation | |
| D4-GL-02 | P1 | 01 | Jurnal manual meloloskan NaN/Infinity | implemented_pending_validation | |
| D4-ASSET-01 | P1 | 01 | Klaim periode penyusutan tanpa resume | implemented_pending_validation | |
| D4-ASSET-02 | P1 | 01 | Penyusutan dua periode paralel saling menimpa | implemented_pending_validation | |
| D4-CLOSE-01 | P2 | 01 | Reopen bulan tidak menandai penutupan tahun basi | implemented_pending_validation | |
| D4-CLOSE-02 | P1 | 01 | Tutup ulang gagal mengadopsi jurnal tersimpan | implemented_pending_validation | |
| D4-CC-01 | P2 | 01 | Recovery cycle count membuat dua laporan | implemented_pending_validation | |
| D4-BACKORDER-01 | P1 | 01 | Pemenuhan paralel mereservasi berlebih | implemented_pending_validation | |
| D4-OD-LOCK-01 | P1 | 01 | Harga OD terkunci setelah sinkron SKU gagal | implemented_pending_validation | belum ada uji otomatis khusus resume PO otomatis |
| D4-CASE-01 | P1 | 01 | Refund store credit menjurnal dua kali | implemented_pending_validation | |
| D4-CASE-02 | P1 | 01 | Penyelesaian kasus mengulang kas | implemented_pending_validation | |
| D4-CASE-03 | P1 | 01 | Dana dipegang karyawan tanpa urutan/sisa | implemented_pending_validation | |
| D4-INTERCO-01 | P1 | 01 | Transfer retur memindah pemilik tanpa dokumen | implemented_pending_validation | |
| D4-INTERCO-02 | P1 | 01 | Transfer antarentitas memakai WAC sesudah pindah | implemented_pending_validation | |
| D4-PA-02 | P1 | 01 | Putaway kehilangan checkpoint setelah roll pindah | implemented_pending_validation | |
| D4-RFID-01 | P1 | 01 | Dedup event RFID melewati recovery | implemented_pending_validation | |
| V3-MRES-01 | P1 | 02 | Dua PR mencadangkan bahan melebihi stok | implemented_pending_validation | |
| V3-MRES-02 | P1 | 02 | Total cadangan maklon terpotong batas query | implemented_pending_validation | |
| V3-WEIGHT-01 | P1 | 02 | Split bersamaan menggandakan berat | implemented_pending_validation | |
| V3-RFID-01 | P1 | 02 | Read green passage lama dipakai ulang | implemented_pending_validation | tes lama mereplikasi logika, bukan memanggil service |
| V3-WMS-02 | P1 | 02 | Loading ditahan pending cut gudang lain | implemented_pending_validation | |
| D4-STOCK-01 | P1 | 02 | Stok terhitung dua kali bila pemilik berbagi SKU | implemented_pending_validation | |
| D4-AI-05 | P1 | 02 | Live analytics mengabaikan reserved di roll available | implemented_pending_validation | |
| D4-AI-06 | P1 | 02 | Total qty lintas produk menjumlah meter + kg | implemented_pending_validation | |
| D4-DASH-01 | P1 | 02 | Batas katalog 3.000 SKU | implemented_pending_validation | risiko performa katalog sangat besar |
| D4-WMS-03 | P1 | 02 | Utilisasi mengabaikan Rack→Level→Bin | implemented_pending_validation | |
| D4-PLAN-05 | P1 | 02 | Pasokan sama direncanakan penuh untuk beberapa SO | implemented_pending_validation | |
| D4-GLOBAL-01 | P1 | 02 | 100 yard dilabelkan 100 meter | implemented_pending_validation | |
| D4-SUPPLY-01 | P1 | 02 | Sisa PO partial hilang dari incoming | implemented_pending_validation | |
| D4-CAP-01 | P1 | 02 | SKU ditolak setelah 1.000 master | implemented_pending_validation | |
| D4-PA-01 | P1 | 02 | Reservasi mengambil roll yang diklaim putaway | implemented_pending_validation | |
| D4-PA-03 | P2 | 02 | Total putaway menjumlah meter + yard | implemented_pending_validation | tes lama mereplikasi logika, bukan memanggil service |
| D4-TAG-01 | P1 | 02 | Verifikasi tag lama tetap berlaku | implemented_pending_validation | data lama tanpa `verified_tag_id` memakai fallback |
| D4-ICLOAN-01 | P1 | 02 | Finance mengubah pinjaman entitas lain | implemented_pending_validation | |
| D4-RFQ-01 | P1 | 02 | Award RFQ membuat PO untuk item tak tersedia | implemented_pending_validation | |
| D4-RFQ-02 | P1 | 02 | Perbandingan/pembatalan RFQ lintas entitas | implemented_pending_validation | |
| D4-ALERT-WMS-01 | P1 | 02 | Notifikasi WMS mencampur dua entitas | implemented_pending_validation | |
| D4-PRICE-SCOPE-01 | P1 | 02 | Scope harga khusus berbeda antar-handler | implemented_pending_validation | |
| D4-RET-POLICY-01 | P1 | 02 | Deadline retur berubah karena PO entitas lain | implemented_pending_validation | `needs_admin_review` hanya tampil di daftar peringatan |
| V3-PO-01 | P2 | 03 | Task selisih PO tidak refresh, kehilangan identitas baris | implemented_pending_validation | |
| V3-CF-01 | P1 | 03 | Jurnal campuran kas/nonkas salah klasifikasi | implemented_pending_validation | |
| V3-DATE-01 | P1 | 03 | Jurnal date-only awal periode hilang | implemented_pending_validation | |
| V3-PO-02 | P2 | 03 | Amend ke qty diterima bertentangan dengan guard | implemented_pending_validation | |
| V3-PO-03 | P1 | 03 | Tugas selisih selesai sebelum amendment disetujui | implemented_pending_validation | |
| D4-FIN-01 | P1 | 03 | Control Tower menggabungkan AR semua entitas | implemented_pending_validation | |
| D4-SALES-01 | P1 | 03 | Target penjualan tidak ikut scope entitas | implemented_pending_validation | |
| D4-SALES-02 | P1 | 03 | Sales Home lintas entitas | implemented_pending_validation | |
| D4-SALES-03 | P1 | 03 | Komisi per-SKU memasukkan SO entitas lain | implemented_pending_validation | |
| D4-FIN-02 | P1 | 03 | Forecast kas beda basis AR/termin | implemented_pending_validation | termin 0 eksplisit kini 0 hari di ±21 konsumen |
| D4-FIN-03 | P1 | 03 | Revenue profitabilitas memasukkan PPN | implemented_pending_validation | |
| D4-FIN-04 | P2 | 03 | Realisasi memakai pesanan reserved & WAC | implemented_pending_validation | |
| D4-AI-01 | P1 | 03 | Analytics AP mengabaikan fallback bill | implemented_pending_validation | |
| D4-CASH-01 | P1 | 03 | Saldo awal kas kecil berpindah ke kas besar | implemented_pending_validation | backfill mengubah klasifikasi rekening tipe cash |
| D4-COA-01 | P1 | 03 | Mode Semua Entitas menghilangkan akun khusus | implemented_pending_validation | |
| D4-PLAN-01 | P1 | 03 | Rencana mencatat qty berbeda dari PR | implemented_pending_validation | |
| D4-PLAN-02 | P1 | 03 | Produk ganda membuat pembelian berlebih | implemented_pending_validation | |
| D4-PLAN-03 | P1 | 03 | Riwayat "penuh" walau eksekusi sebagian gagal | implemented_pending_validation | |
| D4-DATE-01 | P2 | 03 | Penjualan & Home memakai bulan UTC | implemented_pending_validation | |
| D4-COMM-BOUNDS-01 | P1 | 03 | Patch master komersial melewati batas angka | implemented_pending_validation | |
| D4-BUD-EDIT-01 | P1 | 03 | Edit anggaran melewati keunikan & batas tahun | implemented_pending_validation | |
| D4-UOM-BF-01 | P2 | 03 | Backfill jumlah roll dari ID mentah | implemented_pending_validation | |
| D4-STOCK-02 | P2 | 04 | Filter kategori tidak berlaku di aging | implemented_pending_validation | |
| D4-STOCK-03 | P2 | 04 | Nilai persediaan mengabaikan landed cost | implemented_pending_validation | |
| D4-STOCK-04 | P2 | 04 | Tanggal roll tanpa timezone menjatuhkan laporan | implemented_pending_validation | |
| D4-AI-02 | P2 | 04 | Pelanggan baru mengabaikan scope lini | implemented_pending_validation | |
| D4-AI-03 | P2 | 04 | Refresh fact menghapus data sebelum pengganti | implemented_pending_validation | |
| D4-AI-04 | P2 | 04 | Pembulatan alokasi tim tidak konservatif | implemented_pending_validation | |
| D4-HR-01 | P1 | 04 | Payroll gabungan memakai satu run | implemented_pending_validation | |
| D4-HR-02 | P2 | 04 | Turnover memakai waktu edit | implemented_pending_validation | data lama tanpa tanggal keluar tidak di-backfill |
| D4-WMS-01 | P2 | 04 | RED hari ini memakai hari UTC | implemented_pending_validation | |
| D4-WMS-02 | P2 | 04 | Cycle count belum selesai menghapus akurasi | implemented_pending_validation | |
| D4-WMS-04 | P2 | 04 | Antrean simpan menghitung roll reserved | implemented_pending_validation | |
| D4-MKT-01 | P2 | 04 | Reach post disajikan per platform/akun | implemented_pending_validation | |
| D4-RND-01 | P2 | 04 | KPI R&D menggabungkan nama sama | implemented_pending_validation | data lama tanpa user_id tetap kunci nama |
| D4-EQ-01 | P1 | 04 | Laba periode berjalan nol setelah tutup buku | implemented_pending_validation | |
| D4-SIM-01 | P2 | 04 | Simulator lolos saat barang belum diterima | implemented_pending_validation | |
| D4-BANK-01 | P2 | 04 | Tanggal mustahil masuk rekonsiliasi | implemented_pending_validation | |
| D4-BANK-02 | P2 | 04 | MT940 tidak membaca RC/RD | implemented_pending_validation | |
| D4-RET-CHAIN-01 | P2 | 04 | Rantai retur menjumlah satuan berbeda | implemented_pending_validation | belum ada unit test; telaah kode + iteration_170 |
| D4-ALERT-DATE-01 | P2 | 04 | Jatuh tempo hari ini disebut terlambat | implemented_pending_validation | |
| D4-ALERT-AMT-01 | P2 | 04 | Peringatan utang menampilkan nominal penuh | implemented_pending_validation | |
| D4-KPI-WEIGHT-01 | P2 | 04 | Bobot KPI nol menjadi satu | implemented_pending_validation | |
| D4-KPI-PERIOD-01 | P2 | 04 | Periode KPI bukan bulan kalender diterima | implemented_pending_validation | |
| D4-KPI-SCORE-01 | P2 | 04 | Skor otomatis KPI dapat negatif | implemented_pending_validation | |
| D4-BUD-THRESHOLD-01 | P2 | 04 | Ambang 0% menjadi 85% | implemented_pending_validation | |
| V3-DUP-01 | P3 | 05 | `_clean_perms` didefinisikan dua kali | implemented_pending_validation | |
| V3-BUILD-01 | P2 | 05 | Tidak ada lockfile frontend terlacak | implemented_pending_validation | workflow CI belum pernah dijalankan di runner GitHub |
| D4-FE-01 | P2 | 05 | Grafik velocity dipotong 14 hari | implemented_pending_validation | |
| D4-FE-02 | P1 | 05 | Respons periode lama menimpa grafik | implemented_pending_validation | |
| D4-TEST-01 | P2 | 05 | Tes ATP lulus walau ada mismatch | implemented_pending_validation | |
| D4-PLAN-04 | P2 | 05 | Pesan gagal parsial terhapus refresh | implemented_pending_validation | telaah kode saja (tanpa uji browser); server belum mengirim `processed` |
| D4-ORDER-01 | P1 | 05 | Rata-rata pesanan dibagi 20 pesanan terbaru | implemented_pending_validation | |
| D4-DOC-01 | P2 | 05 | Pratinjau template memanggil endpoint tak ada | implemented_pending_validation | |
| D4-CB-01 | P2 | 05 | Pemeriksa kontrabon hanya 2.000 dokumen | implemented_pending_validation | |

## 6. Batas pengujian & risiko yang diketahui

1. **MongoDB standalone (tanpa replica set)** — tidak ada transaksi multi-dokumen. Fase 01 memakai write-ahead marker, id deterministik dan klaim CAS; exception tertutup, *crash proses* di antara dua write dipulihkan pada retry berikutnya (tidak ada sweeper latar belakang).
2. Movement `pending` (Fase 01) dapat terlihat oleh laporan selama beberapa milidetik.
3. Live test 03b/03c berbagi satu PO seed yang dimutasi (§2).
4. Beberapa tes lama Fase 02 (D4-PA-03, V3-RFID-01) mereplikasi logika, bukan memanggil service.
5. Item dengan catatan di §5 belum memiliki bukti setara uji service/fault-injection.
6. Performa: penghapusan batas query (`to_list(N)`) di D4-DASH-01, D4-CAP-01, V3-MRES-02, D4-CB-01, supply index ATP belum diuji beban pada data sangat besar.

## 7. Migrasi & dampak data historis

- Field baru tanpa migrasi wajib: `op_marks`, `pending`/`wal`, `pending_cut_ops`, `match_lock`, `effects_done`, `deposit_credited`, `applied_periods`, `depreciation_claims`, `pricing.sku_synced`, `unit_cost_snapshot`, `last_pa_landed`, `processed` (RFID), `held_amount/settled_amount`, `weight_split_children`, `loading_checks.<gudang>`, `journey.verified_tag_id`, `cash_type/cash_type_source`, `separation_date/separation_history`, `build_gen` (fact sales), `pending_demand` (status board).
- **Backfill otomatis sekali**: `bank_accounts.cash_type` saat startup (hanya yang kosong; sumber dicatat di `cash_type_source`). Dampak: rekening tipe `cash` tanpa transaksi kas kecil kini dihitung kas kecil.
- Perubahan perilaku pada konsumen: termin 0 eksplisit = 0 hari (sebelumnya 30); profitabilitas `totals` kini realisasi (estimasi di `estimate`); `/sales-orders/stats/summary` menambah `periods` & `pending_count`.
- Data lama tetap jalur lama: movement tanpa `wal`, aset tanpa `applied_periods`, kwitansi tanpa `effects_done`, karyawan nonaktif tanpa tanggal keluar, ronde R&D tanpa `performed_by_user_id`.
- Kwitansi gagal (V3-AR-01) dihapus dari `ar_receipts` (nomor terlewat) dan diarsipkan di `ar_receipt_failures`.
- Rollback: memakai fitur rollback checkpoint platform; tidak ada migrasi skema yang perlu dibalik selain field tambahan di atas.

## 8. Permintaan validasi independen

Validasi ID: **seluruh 101 ID pada §5**. Repo/branch: workspace `/app`, commit `72cb55e` (actual HEAD sebelum perubahan `f36ae37`, baseline `a904d98`). PR: tidak ada.
Periksa perubahan source, jalankan counterexample baseline (`evidence/`, `repro/`) pada HEAD tercatat, dan telusuri flow
hingga consumer/report/UI. Bukti agent: `docs/audit/gelombang-3/implementation/FASE-0x-STATUS.md`,
`backend/tests/test_g3_phase0*.py`, `/app/test_reports/iteration_162…171.json`. Jangan menyimpulkan fixed dari checklist
agent atau satu tes positif saja. Berikan verdict per ID: verified_fixed / partially_fixed / still_open /
needs_business_decision / not_reproduced_on_new_commit, lengkap dengan sebab dan bukti. Prioritaskan item bercatatan di §5
dan default agent di §4.
