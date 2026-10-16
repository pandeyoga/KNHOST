# Laporan Fase P05 — MD Quality, R&D existing, bahan makloon, dan sumber restock

## Identitas

- Branch dan commit baseline: `main` @ `ad51444` (berisi checkpoint P05 parsial `9fd6d29`), preview di-seed ulang mengikuti `deploy/setup_demo_lengkap.sh` (lokal: `scripts/restore_local_demo.sh`)
- Commit implementasi: P05 di atas `ad51444` (commit "Save to GitHub" berikutnya)
- Commit yang diuji: preview 2026-10-12 (iteration_179) · penutupan 2026-10-14 (iteration_182)
- Pelaksana: agent development · validator: pemilik (belum)
- IMP: IMP-17, IMP-18, IMP-19 (implemented_pending_validation) · IMP-16 waiting_decision (DEC-06)
- Status fase: implemented_pending_validation (2026-10-14: DEC-13 diputuskan, ACC-29..35 lulus)

## Perubahan perilaku

| Area | Sebelum | Sesudah |
|---|---|---|
| Sumber restock (IMP-19) | Tidak ada; PR/PO/MKO bebas jalur | `product_templates.restock_source {mode supplier/makloon/both, note, lead_time_days}` + riwayat 30 perubahan, dikelola MD (izin product.update) di Master Produk › "Sumber restock artikel". Artikel lama TIDAK di-default (tampil "belum diatur"). Server (`restock_source_service.check_lines`) memvalidasi PR, PO manual, dan Order Makloon barang jadi: jalur yang bertentangan ditolak; "both" wajib alasan (`route_reason`, tersimpan di `restock_route`); "belum diatur" mengikuti `purchasing.restock_source_unknown` (warn/block; data acuan = block). Bahan baku (benang/grey/PFD) tidak dibatasi. Reorder dari SO memilih makloon otomatis untuk artikel makloon-only. |
| Bahan makloon (IMP-18) | Bahan Order Makloon langsung baru dicadangkan lewat PR | Order Makloon `process_only` mengunci bahan saat dibuat (`material_reservations` per MKO, idempoten, kunci per produk×entitas); kekurangan dicatat `shortage_qty` (tidak ditebak). Tanpa resep/yield wajib `manual_material_reason` (`material_basis` = manual). Issue memakai cadangan; issue < cadangan menyisakan cadangan aktif (bukan hilang), batal MKO melepas sisa. Pending Admin Sales menampilkan MKO, bahan dikunci/kurang/dikirim ke mitra. |
| Uji tambahan SKU existing (IMP-17) | Setiap permintaan sample wajib membuat spesifikasi baru (berpotensi SKU baru) | `POST /api/rnd/samples {product_id, sample_types}` → `purpose: revalidation`: SKU aktif dipakai apa adanya, tidak ada spec/SKU baru, lifecycle produk tidak diubah, lini SKU diperiksa terhadap hak lini akun. Retry saat uji sejenis untuk SKU yang sama masih terbuka ditolak (menyebut nomor sample). Proofing & SKU non-aktif ditolak. Keputusan pemenang tidak meng-ACC spesifikasi/membuat produk; hasil dicatat ke `products.rnd_test_history`. UI: form sample mode "Uji tambahan SKU existing" (pilih SKU + histori ronde/pelaksana), badge di kartu & detail. |
| MD Quality vs QC (IMP-16, 2026-10-13) | Satu petugas mengisi warna/handfeel + 4-point; tahanan hanya dilepas manajer | Peran baru `md_quality` & `qc` (hak juga melekat ke MD). Baris inspeksi diisi per bagian (`part`): MD Quality = warna/handfeel (boleh saat draf, grade tidak berubah, tahanan → MD Quality lepas/tolak; manajer cadangan), QC = 4-point/ukur (hasil MD Quality tidak ditimpa). Random check stok (`POST /api/inspections/random-check`): N roll Tersedia acak ditahan (`blocked`), SPK `random_check` hanya QC; ditutup → roll lulus dilepas, roll baris `tolak`/SPK ditolak tetap ditahan, grade dari 4-point; tidak bisa dibuka ulang. Uji: iteration_180 (BE 16/17, 1 skip env). |
| Sisa cadangan MKO (IMP-18) | Issue < cadangan: sisa tetap aktif walau MKO selesai | MKO berstatus `completed` → sisa `material_reservations` aktif dilepas otomatis + catatan timeline. |
| Batal MKO sesudah issue (DEC-13, 2026-10-14) | Batal langsung memindah roll subcon → available + jurnal balik WIP, padahal bahan masih di mitra | Batal hanya melepas cadangan yang belum dikirim. Langkah yang sudah di-issue tetap `issued` + `awaiting_return`, order `material_at_partner`, WIP 1-1350 tetap. Retur dicatat manual: `POST /api/makloon-orders/{id}/steps/{seq}/return-material {reason ≥5}` (izin makloon_order.cancel) → roll available + `subcon_issue_reversal` (1×, ulang 409), langkah `returned`. Terima hasil pada order batal → 409. UI: `mko-await-return-<seq>` → `mko-return-open/reason/submit-<seq>`, `mko-step-returned-<seq>`. |
| Kebutuhan bahan dari resep (ACC-33, 2026-10-14) | Prefill makloon: `round()` dulu lalu `ceil` → 100 kemeja butuh 168,42 m (hanya 99,997 kemeja) | Dibulatkan ke ATAS dari nilai mentah → 168,43 m. |

## File dan consumer

- Server: `services/restock_source_service.py`, `routers/restock_sources.py`, `services/purchase_requisition_service.py`, `routers/purchase_orders.py`, `services/makloon_order_service.py`, `services/material_reservation_service.py`, `services/restock_service.py`, `services/fulfillment_decision_service.py`, `services/pr_sourcing_service.py`, `services/sales_p04_service.py`, `services/rnd_sample_service.py` (`prepare_revalidation`, `create_sample`, `decide_sample`), `routers/rnd.py`, `schemas*.py`, `config_catalog_core.py` (`purchasing.restock_source_unknown`).
- UI: `catalog/RestockSourcePanel.jsx`, `CatalogWorkspace.jsx`, `admin/po/POCreateForm.jsx`, `purchasing/PurchaseRequisitions.jsx`, `purchasing/makloon/MakloonWizard.jsx`, `sales_admin/PendingProductRow.jsx`, `rnd/SampleFormModal.jsx`, `rnd/ExistingSkuSection.jsx`, `rnd/SampleBoardCard.jsx`, `rnd/SampleDetailPanel.jsx`.

## Data dan migrasi

- Tidak ada backfill: artikel tanpa mapping tetap "belum diatur" (DEC-07). Seed CONTOH `scripts/seed_p05_kn.py` (langkah 5h setup): RIVERA RIB=makloon, ALICE KNIT=supplier, AUDIA KNIT=both, kebijakan unknown=block, KANDA/SO-00006 → PR → MKO bahan grey 300 kg dikunci.
- Sample lama tanpa `purpose` dibaca sebagai pengembangan baru (perilaku lama).

## Pengujian

| ACC | Hasil | Bukti |
|---|---|---|
| ACC-35 Jalur restock | pass (API + UI panel) | `backend/tests/test_p05_restock_material_revalidation.py` 12/12, iteration_179 |
| ACC-30 Labdip/Handfeel existing | pass (create/retry/histori via API + UI) | sama; keputusan pemenang untuk sample revalidation belum dijalankan end-to-end |
| ACC-32 Reservasi & issue | pass — reserve tidak memindah fisik; issue parsial 60 dari 100: fisik −60, cadangan sisa aktif, WIP = nilai bahan; ulang issue ditolak (1 jurnal, tanpa double-decrement) | `backend/tests/test_p05_acceptance_acc31_33_34.py` |
| ACC-31 Identitas & hak MD | pass — uji tambahan dengan warna target lain tidak mengubah SKU/nama/warna/spec produk; MD di luar grant lini ditolak | sama |
| ACC-33 Yield & bahan kurang | pass — kekurangan tercatat `shortage_qty`, issue melebihi stok ditolak, bahan per ID (kain bernama mirip tidak terpilih), tanpa resep wajib alasan. Resep acuan pemilik (1 kemeja = 1,6 m, yield 95%, 1 roll = 50 m): 100 kemeja → 168,43 m = 3,37 roll; forecast balik 100 pcs; roll→meter per produk; produk tanpa aturan roll → 400 (tidak ditebak) | `test_p05_acceptance_acc31_33_34.py::TestACC33Recipe`, iteration_182 |
| ACC-34 Batal/parsial | pass — hasil parsial menutup MKO, sisa cadangan dilepas, WIP 0; batal sebelum issue melepas cadangan; batal SESUDAH issue: bahan tetap di mitra & WIP tetap, retur manual mengembalikan stok + 1 jurnal balik, retry ditolak (DEC-13) | sama + UI iteration_182 |
| Rekonsiliasi WIP/Finance | pass — saldo 1-1350 tiap entitas = Σ nilai bahan MKO yang masih di mitra; persediaan GL vs subledger selisih 0 di 3 entitas (setelah perbaikan roll transfer internal di jalan) | sama |
| ACC-29 MD Quality & QC | pass | iteration_180/181, `test_p05_imp16_md_quality_qc.py` |

## Perbaikan saat validasi (2026-10-13)

- Issue parsial (qty dokumen < rencana) kini menskalakan estimasi hasil langkah — sebelumnya hasil wajar dibaca "kurang dari estimasi" dan membuka klaim palsu sehingga MKO tertahan Sebagian.
- Rekonsiliasi persediaan GL ikut menghitung roll transfer INTERNAL yang masih di jalan (`in_transit_transfer`) — sebelumnya Kanda terlihat selisih −Rp 7.940.592 (10 roll KANDA/TRF-00002).

## Issue terbuka

- Retur bahan dicatat per langkah utuh (semua roll langkah itu); retur sebagian/susut di mitra belum ada.
- Detail MKO (termasuk retur bahan) hanya di desktop; tampilan HP tidak punya pintu masuk ke detail MKO.
- Uji duplikat revalidation tidak atomik (dua permintaan paralel bersamaan bisa lolos).
- Dialog keputusan pemenang masih menampilkan opsi "ACC spesifikasi" untuk sample revalidation (diabaikan server).
