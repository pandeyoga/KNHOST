# Laporan Fase P03 — Penerimaan OCR dan transfer yang terkait pemenuhan SO

## Identitas

- Branch dan commit baseline: `main` @ `3ed96fd` (akhir P02).
- Commit implementasi: commit "Save to GitHub" berikutnya di atas `3ed96fd` (hash ditetapkan saat push).
- Pelaksana: agent developer. Reviewer/validator: belum ditetapkan.
- Tanggal & lingkungan uji: 2026-10-11, container preview, data acuan VPS (`setup_demo_lengkap.sh` langkah 3–5e) + `seed_p03_kn.py` (5f).
- IMP: IMP-21, IMP-26, IMP-27 + sisa P02 (IMP-24: cek ulang rules tujuan saat terima, rules untuk transfer antar badan usaha). DEV-G03/G05.
- Status: **implemented_pending_validation**. P02 tetap menunggu validasi (pilihan pemilik).

## Perubahan perilaku

| IMP | Sebelum | Sesudah |
|---|---|---|
| Sisa P02 (IMP-24) | Rules tujuan hanya dicek saat transfer dibuat; transfer antar-PT tanpa evaluator. | Saat terima, tiap roll dievaluasi ulang (`warehouse_violations`). Ditolak → roll tetap di perjalanan + exception `rule_violation`; supervisor (warehouse_admin/manager/admin) dengan alasan ≥5 → masuk sebagai **hold** (hanya ke area QC). Approve antar-PT: gudang tempat roll berada wajib boleh dipakai pemilik BARU + lolos rules → selain itu 409 `INTERCO_DEST_RULES` kecuali pengecualian supervisor beralasan (tercatat `rule_exception`). |
| IMP-26 | Transfer tidak tahu SO; roll berkomitmen SO tidak bisa dipindah (harus dilepas dulu). | `POST /api/transfers` menerima `sales_order_id`; roll reserved untuk SO itu ditandai `transfer_ref {id, so_id}` (CAS) **tanpa reservasi kedua** — `reserved_ref` tetap SO di semua tahap (reserved → in_transit_transfer → reserved di tujuan). Roll di transfer aktif lain → 409; SO entitas lain → 400 (wajib transaksi antar-PT). Saat diterima, alokasi SO & tugas outbound (belum mulai) pindah ke gudang tujuan; SO **tidak** berubah status (tiba ≠ terkirim ke pelanggan; SJ pelanggan tetap dokumen SO). Batal transfer → roll kembali ke komitmen SO di gudang asal. |
| IMP-27 | `dispatched → completed` menerima semua roll sekaligus. | `/status completed` ditolak 409 `TRANSFER_RECEIPT_REQUIRED` bila masih ada roll di jalan. `POST /api/transfers/{id}/receive` per roll (id/nomor roll/tag), kondisi baik/rusak (rusak wajib keterangan), opsi bin/staging tujuan (lewat `place_roll` P02). CAS per roll → retry "already", tanpa mutasi ganda. Status baru `partially_received`; `completed` otomatis (basis `actual_receipt`) saat tak ada roll di jalan. Exception: roll salah (tidak masuk stok), hilang (PIC+alasan), rusak, aturan. Supervisor: kembalikan ke asal / tutup catatan (hilang & aturan tidak bisa ditutup catatan). Batal ditolak bila sudah diterima sebagian. Batch divalidasi dulu sebelum ada roll mendarat. |
| IMP-21 | Packing list → `expected_rolls` dengan panjang; koreksi review menimpa seluruh daftar. | Tiap roll menyimpan bukti dokumen `doc_length/doc_length_text/doc_weight_kg/doc_status (ok/unclear/missing)`; koreksi menandai `corrected` + penanda waktu/oleh, snapshot `ocr_expected_rolls`. `pl_check` per baris: jumlah roll & subtotal dokumen vs SJ, jumlah ragu/koreksi; ketidakcocokan/ragu → GRN "ragu" (tidak auto-post; memang tidak pernah auto-post). SJ hanya total → `basis=total_only`, tidak ada panjang rata-rata; layar meminta ukur tiap roll. Expected roll tidak membuat stok/tag (hanya roll terukur yang membuat roll). |

## File dan consumer

| File | Perubahan | IMP |
|---|---|---|
| `backend/services/transfer_receipt_service.py` (baru) | SO options/rolls, attach roll berkomitmen, receive per roll, exception/resolve, ringkasan dari dokumen roll, rehome alokasi SO, `interco_violations` | 24/26/27 |
| `backend/services/roll_service.py` | `owned_by_transfer`, `transfer_held_rolls`, `held_cas`, `so_still_open`; dispatch & release CAS + komitmen SO dipertahankan | 26/27 |
| `backend/routers/transfers.py` | create `sales_order_id`; approve antar-PT cek rules; guard `completed`; cancel guard; endpoint `so-options`, `so-rolls`, `{id}/receipt`, `{id}/receive`, `{id}/exceptions`, `{id}/exceptions/{exc}/resolve`; detail `dest_rule_check` | 24/26/27 |
| `backend/schemas.py` | `TransferCreate.sales_order_id`, `TransferApprove.rule_exception_reason`, `TransferReceiveIn`, `TransferExceptionIn`, `TransferExceptionResolveIn` | 26/27 |
| `backend/services/dn_rules.py`, `goods_receipt_ocr_service.py`, `goods_receipt_service.py` | bukti dokumen per roll, `pl_summary`, peringatan, `_doubtful`, koreksi tanpa menimpa | 21 |
| `backend/scripts/seed_demo_transaksi_kn.py` | skenario pindah_gudang memakai penerimaan per roll | 27 |
| `backend/scripts/seed_p03_kn.py` (baru), `deploy/setup_demo_lengkap.sh` langkah 5f | data contoh transfer SO Soreang → Jakarta (dikirim) | 26 |
| Frontend `features/wms/transfer/*` | `TransferReceiptPanel`, `ReceiptRollTable`, `ReceiptExceptions`, `TransferSoPicker`; detail menampilkan SO, cek aturan antar-PT + alasan; tombol "Complete Transfer" dihapus; status "Diterima Sebagian" | 24/26/27 |
| Frontend `features/wms/grn/GrnPackingChecklist.jsx`, `GrnLineRow.jsx` | ringkasan dokumen vs SJ, tanda ragu/dikoreksi, petunjuk SJ hanya total | 21 |

## Keputusan bisnis

DEC-08 dan DEC-11 masih **open** — tidak ditebak. Perilaku sementara mengikuti teks "Sambil menunggu": OCR hanya kandidat, tidak membagi total; komitmen roll tidak dilepas agar bisa transfer; penerimaan hanya aktual; exception tidak disembunyikan sebagai completed. Belum diaktifkan: penghapusan (write-off) roll hilang (DEC-13), ambang review OCR per kategori, SOP pembatalan saat transit selain "kembalikan ke asal".

## Migrasi dan rekonsiliasi

- Tidak ada migrasi data. Transfer lama `completed` tetap terbaca; layar menulis "Transfer lama: hanya status 'Selesai' yang tercatat, tanpa bukti penerimaan per roll" (tidak dibuat scan fiktif). Transfer lama `dispatched` tetap di perjalanan dan wajib diterima per roll.
- Link SO tidak di-backfill (tidak ada referensi lama yang dapat dibuktikan).
- Data contoh preview: KANDA/TRF-00001 & TRF-00002 sudah dipakai uji (completed dengan exception), KANDA/TRF-00003 (SO-00005) masih dalam perjalanan untuk dicoba. Di VPS `seed_p03_kn.py` membuat satu transfer contoh.

## Hasil pengujian

| ACC | Lingkungan | Hasil | Evidence |
|---|---|---|---|
| ACC-14 OCR per roll | fungsi (dn_rules/pl_summary), tanpa foto SJ nyata | pass | iteration_176, `backend/tests/test_p03_transfer_receipt.py` |
| ACC-15 SJ hanya total | fungsi | pass | idem |
| ACC-16 Bandung-Jakarta-customer | API+DB | sebagian (kaki pelanggan not_run) | iteration_176 |
| ACC-17 Reservasi & concurrency | desain + retry | not_run (SO-A/SO-B serentak) | — |
| ACC-18 Receipt parsial | API+DB | pass | iteration_176 + uji developer |
| ACC-19 Exception | API+DB | pass (bug validasi rusak diperbaiki) | iteration_176 |
| ACC-20 Aturan tujuan & ownership | API+DB | sebagian (approve antar-PT belum lewat API) | iteration_176 |

## Risiko dan issue terbuka

| Issue | Dampak | IMP/DEC | Tindak lanjut |
|---|---|---|---|
| Roll hilang tidak bisa dihapus dari stok | tetap tercatat dalam perjalanan | DEC-13 | keputusan Finance |
| Roll rusak/ditahan yang terikat SO tetap memegang komitmen | SO kurang barang siap kirim | DEC-11 | Admin Sales ganti roll / batal baris |
| Rehome hanya untuk tugas outbound berstatus `created` | tugas yang sudah dipick tidak dipindah | IMP-26 | SO yang sudah dipick tidak bisa ditautkan (hanya roll `reserved`) |
| UI penerimaan, alur pelanggan dari Jakarta, approve antar-PT belum diuji end-to-end | — | ACC-16/20 | UAT |

## Kesimpulan fase

IMP-21, IMP-26, IMP-27 diimplementasikan dan diuji developer → `implemented_pending_validation`. Sisa P02 (rules saat terima & antar-PT) ditutup di kode. BACKLOG.json diperbarui, TRACKER.md dirender, `validate_package.py` tanpa error. Fase yang siap dimulai: P04 (dependensi P01+P03), P05 (P01+P02).
