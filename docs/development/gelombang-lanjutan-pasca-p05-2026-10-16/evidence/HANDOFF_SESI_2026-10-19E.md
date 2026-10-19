# Handoff sesi 2026-10-19E — GL-01 Pemetaan Akun, ongkir retur, pemecahan roll cutloss

Lanjutan sesi D. Semua fase A–F selesai dan di-push per fase (scripts/push_github.sh).

## Jawaban owner (dicatat apa adanya, sesi E)
| ID | Jawaban owner | Implementasi |
|---|---|---|
| CUT-02 | bisa dikonfigurasi, default MD | setting `returns.cutloss_treatment_roles` (bawaan md, md_quality; admin & manager selalu boleh) |
| CUT-03 | BS bukan ROLL, KG atau yard menyesuaikan | potongan BS dicatat dalam satuan dasar roll (kg/yard), nilai = HPP per satuan × qty |
| CUT-04 | setelah QC | pecah hanya saat retur berstatus `inspected` |
| CUT-05 | SJ baru dengan referensi SJ & SO original | `POST /sales-returns/{id}/cutloss/{ctl}/return-shipment` → `shipments.kind=cutloss_return`, `ref_order_number`, `ref_shipment_no` |
| GL-02 | pakai yang sudah ada | `retur.ongkir_perusahaan` → 6-4500 |
| GL-03 | ketika awal pengiriman | jurnal saat biaya logistik disimpan |
| GL-04 | dipilih Finance, semua tipe pembayaran | `pay_account_code` (kas/bank 1-11xx atau kewajiban 2-1xxx), izin `sales_return.post_logistics` |
| GL-05 | ambil sendiri / armada KN (gratis atau customer bayar + nominal) / pihak ketiga (ditanggung KN atau customer bayar sendiri) | `mode` pickup/own_fleet/third_party × `bearer`; armada KN dibayar customer → Dr Piutang / Cr Pendapatan penggantian ongkir |
| GL-06 | bisa dikonfigurasi | setting `returns.logistics_vat_enabled` (bawaan mati) |
| GL-07 | dipilih saat mengirim | `charged_entity_id` per jenis biaya |
| GL-08 | Finance, tanpa persetujuan kedua, hanya jurnal baru | izin `gl_mapping.update` admin+finance, manager lihat |
| ACC-KP-01 | Sales boleh lihat saja | tes lama diubah ke 200; kode tetap (scope pesanan milik sales) |

## Fase
- A: `services/gl_mapping_registry.py`, `gl_mapping_service.py`, `routers/gl_mappings.py`; `_insert_entry` meng-remap baris (sumber manual/reversal/closing tidak). Tanpa pemetaan → jurnal identik.
- B: UI `?view=gl-account-mappings` (FE ikut ter-push di commit Fase A).
- C: pembaca saldo memakai `known_codes(key)` (akun lama + baru): suspense, piutang denda, uang muka pelanggan, selisih bayar, persediaan (rekonsiliasi), AR aging. Trial balance seimbang per PT; verify_data_integrity 11 FAIL = baseline data restore (tidak ada FAIL GL baru).
- D: `services/return_logistics_service.py`, `GET/PUT /sales-returns/{id}/logistics`, jurnal balik saat ubah/tolak retur. UI `ReturnLogisticsPanel` + `LogisticsCostRow`.
- E: `services/return_cutloss_split_service.py`, endpoint split-preview/split/return-shipment; UI `CutlossSplitPanel` + posisi cacat & pilihan BS/Dibuang di form cutloss.
- F: tes `test_gl01_account_mapping.py`, `test_gl01_return_logistics_journal.py`, `test_cut01_cutloss_split.py`; testing agent iteration_244 100%. Temuan teknis diperbaiki: `GET /api/products?stage=`, kartu tugas gudang Meja Saya (judul & qty 0).

## Asumsi (ditandai)
- Piutang ongkir customer hanya dijurnal; belum ada dokumen tagihan terpisah.
- SJ potongan baik langsung berstatus dikirim (roll keluar stok, Dr HPP / Cr Persediaan); belum lewat dispatch armada/ekspedisi.
- `consolidation_service` & `interco_margin` masih membaca kode akun tetap.

## Masih terbuka
D1–D8, DATA-01, DES-02..04, HW-01/02, HR-01, UAT-01, VAL-01 (lihat HANDOFF_SESI_2026-10-19D.md).
