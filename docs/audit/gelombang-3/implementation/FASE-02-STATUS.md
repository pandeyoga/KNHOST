# Gelombang 3 · Fase 02 — status implementasi (2026-10-06, BARU DIMULAI)

Status tertinggi yang dipakai agent: `implemented_pending_validation`.

| ID | Validasi temuan | Status | Perubahan | Bukti uji |
|---|---|---|---|---|
| D4-ICLOAN-01 | VALID: GET detail mengecek entitas, tetapi disburse/repay/cancel tidak | implemented_pending_validation | `routers/interco_loans.py`: `_guard_loan` (lingkup entitas sisi dokumen yang diminta) dipanggil di detail, cair, bayar, dan batal sebelum service dijalankan | lihat iteration_164 |
| D4-RFQ-02 | VALID: compare dan seluruh mutasi tanpa `assert_entity_access` | implemented_pending_validation | `routers/rfq.py`: compare, send, quote, award, dan cancel kini memeriksa lingkup entitas seperti detail | lihat iteration_164 |
| D4-CAP-01 | VALID: `products.find({}).to_list(1000)`, sehingga SKU ke-1.001 dianggap tidak ada | implemented_pending_validation | `routers/purchase_orders.py`: hanya produk yang dipesan diambil (`$in`, tanpa batas) | lihat iteration_164 |
| D4-DASH-01 | VALID: master `to_list(3000)` dan saldo `to_list(5000)` memotong KPI | implemented_pending_validation | `routers/dashboard.py`: tanpa batas jumlah. **Risiko performa** di katalog sangat besar; agregasi server-side belum dibuat | lihat iteration_164 |
| 19 ID lain Fase 02 | belum ditelaah | open | — | — |

Bukti: `backend/tests/test_g3_phase02.py` (service) + `test_g3_phase02_api.py` (API). iteration_164: 20 uji Fase 02 lulus (5 service + 15 API), regresi Fase 01 28 lulus.
Uji API memakai pengguna ber-lingkup entitas tunggal (ent_ksc) terhadap dokumen ent_kanda. Hasilnya 404 tanpa perubahan data; admin tetap bisa.

Sisa Fase 02 (open): V3-MRES-01, V3-WEIGHT-01, V3-RFID-01, V3-WMS-02, V3-MRES-02, D4-STOCK-01, D4-AI-05, D4-AI-06, D4-WMS-03,
D4-PLAN-05, D4-GLOBAL-01, D4-SUPPLY-01, D4-PA-01, D4-PA-03, D4-TAG-01, D4-RFQ-01, D4-ALERT-WMS-01, D4-PRICE-SCOPE-01, D4-RET-POLICY-01.
