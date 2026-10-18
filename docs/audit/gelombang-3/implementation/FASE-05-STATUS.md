# Gelombang 3 · Fase 05 — Status implementasi (2026-10-06)

Status agent paling jauh `implemented_pending_validation`. Uji: `cd /app/backend && DB_NAME=g3_audit_phase05 python -m pytest tests/test_g3_phase05.py -q -n 0` (7 tes) + regresi Fase 01–04 (104 tes) + `tests/test_iter149_audit.py -k atp` (live).

Keputusan user (2026-10-06, semua a): ATP = tersedia + incoming(horizon) − permintaan tertunda; rata-rata pesanan = revenue status terpenuhi ÷ jumlah pesanan terpenuhi periode sama; grafik velocity mengikuti periode terpilih.

| ID | Status | Ringkasan |
|---|---|---|
| V3-DUP-01 | implemented_pending_validation | satu `_clean_perms`; tes AST `test_no_duplicate_top_level_defs` memindai seluruh backend (di luar tests) |
| V3-BUILD-01 | implemented_pending_validation | `frontend/yarn.lock` tidak lagi di-.gitignore (akan ter-commit); workflow `.github/workflows/frontend-lockfile.yml`: corepack yarn 1.22.22, gagal bila lock hilang/ada lock manager lain, `yarn install --frozen-lockfile`, build smoke |
| D4-FE-01 | implemented_pending_validation | `slice(-14)` dihapus; data dipakai hanya bila `period_days === period`; judul menampilkan rentang tanggal |
| D4-FE-02 | implemented_pending_validation | generation guard + AbortController di `load` (setter data/error/loading), abort saat unmount; satu generation untuk 6 endpoint |
| D4-TEST-01 | implemented_pending_validation | oracle bersama `tests/atp_oracle.py`; tes live kini ASSERT + uji negatif mutasi; fixture 105 SKU × 2 owner (hold, reserve, pending, PO dalam/luar horizon) dibandingkan expected independen; status board kini mengekspos `pending_demand` per entitas & gudang; batas `to_list(2000/20000)` di supply index dihapus |
| D4-PLAN-04 | implemented_pending_validation | `execError` terpisah dari `error` muat; refresh tidak menghapusnya; panel "Proses pemenuhan belum tuntas" + tombol "Saya mengerti"; daftar bagian yang sudah diproses ditampilkan bila server mengirim `processed` |
| D4-ORDER-01 | implemented_pending_validation | `/sales-orders/stats/summary` menambah `periods[7d/30d/90d]` (orders, by_status, fulfilled_count, revenue, avg_order_value, top_customers) + `pending_count`; scope entitas/sales-owner/lini sama; batas 200 untuk reservasi dihapus; expiring hanya yang belum lewat; UI memakai agregat server + label cakupan |
| D4-DOC-01 | implemented_pending_validation | `POST /api/document-templates/{id}/preview` {source_id}: jenis dokumen dari template terpilih, template nonaktif 409, document_type tak cocok 400, template override PT lain 400, pagar entitas sumber, tanpa generated_documents/jurnal; UI tidak lagi mematok invoice |
| D4-CB-01 | implemented_pending_validation | `_live_contra_bons` membaca seluruh cursor; `stats()` melapor `scanned/live_total/complete`; gate `verify_data_integrity` FAIL bila cakupan tidak lengkap; fixture 2.102 dokumen dengan duplikat awal/tengah/akhir terdeteksi, cancelled dikecualikan |

Batas: workflow CI belum dijalankan di runner GitHub (hanya ditambahkan); `processed` partial dari endpoint decide belum dikirim server (pesan gagal tetap bertahan).
