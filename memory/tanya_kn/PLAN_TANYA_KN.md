# Rencana Kerja — Asisten Analitik "Tanya KN"

Sumber spesifikasi: `memory/tanya_kn/Rencana_Prompt_Asisten_Analitik_KN.md` (+ `system_prompt_kn_analitik_v1.md`,
`katalog_semantik_v1.md`, `tools_kn_analitik_v1.json`, `templates_laporan_v1.json`). Aturan: satu fase per sesi.

## Status fase

| Fase | Isi | Status |
|---|---|---|
| F0 | Helper waktu WIB, format tanggal per field, indeks, perbaikan 5 celah hak akses laporan lama, konfigurasi keputusan klien | **SELESAI (2026-09-27)** |
| F1 | Tabel fakta `fact_sales_lines` + katalog `cat-v1` sebagai data + mesin `query_metrics`/`analyze_change` + test angka | **SELESAI (2026-09-27)** |
| F2 | Tool server (6 tool) + orkestrator OpenAI Responses + prompt caching + pemeriksa angka + log biaya/kuota + rem anggaran + peran | **SELESAI tanpa kunci (2026-09-27)** — sisa: spike cache §7.2 & uji model nyata setelah kunci; streaming token SELESAI 2026-09-27 (kata demi kata; jalur OpenAI stream=True belum diuji dengan kunci) |
| F3 | Panel `?view=tanya-kn`, blok kn-*, galeri, riwayat sesi (cari/buka/lanjut/hapus), markdown, unduh Excel (per tabel & per jawaban), 👍/👎+komentar | **SELESAI (2026-09-27)** |
| F4 | 34 template resep + narasi (otomatis / luna / sol) + laporan terjadwal in-app + template pribadi | **SELESAI (2026-09-27)** — WhatsApp sengaja belum (pilihan user) |
| F5 | Snapshot harian stok/piutang, cache hasil, prewarm (mati bawaan), routing template, set evaluasi 120 | **SELESAI (2026-09-27)** — eval mode `model` nyata 2026-10-04: tool 94,2% · argumen 90,0% · angka 98,3% · hak akses 100% |
| LIVE | Kunci OpenAI user (DB), ai.enabled=true, gpt-6-sol/luna, spike cache §7.2 terbukti | **SELESAI (2026-10-04)** |

## Verifikasi rujukan berkas:baris (baseline dokumen `7b4d2cb`)
Semua rujukan cocok; pergeseran kecil: `require_permission` di `dependencies.py:100` (bukan 94 — baris 94 `has_permission`),
`entity_ctx` di `entity_scope.py:325`, `resolve_list_scope` di `:454`. Kelima celah §3 butir 5 terbukti ada lalu diperbaiki.

## F0 — yang dikerjakan
- `services/analytics_time.py`: 15 preset → batas UTC dari tengah malam WIB; `previous_period` (satuan kalender penuh →
  satuan sebelumnya; "sampai hari ini" → hari yang sama satuan sebelumnya, 31 Mar → 1–28/29 Feb; rolling → panjang sama),
  `same_period_last_year`; minggu mulai Senin. `DATE_FIELDS` (F0.2): batas ISO tanpa mikrodetik juga benar untuk field `YYYY-MM-DD`.
- Indeks (F0.3): `sales_orders` {entity_id,created_at} {sales_id,created_at} {created_by,created_at} {items.product_id} {updated_at};
  `shipments`/`credit_notes` {entity_id,created_at}; `journal_entries` {entity_id,lines.account_code,date}; indeks fakta.
- Celah (F0.4): `/reports/summary` kini `sales_ownership.apply_scope`; `/sales/kpi` & `/sales/commission` wajib izin
  `order.view` + entitas harus dalam penugasan (tanpa entity_id → entitas aktif; `all` hanya untuk yang boleh gabungan);
  `/finance/profitability` → `strip_cost_fields` (ditambah `cogs_base`, `cogs_landed` ke `COST_FIELDS`) & HPP memakai
  `base_quantity`; `/invoices` disaring entitas.
- Konfigurasi (F0.5) grup baru "Asisten Analitik (Tanya KN)": `ai.sales_definition` (net_order), `ai.sales_attribution`
  (team_split), `ai.margin_roles` [admin, manager], `ai.stock_value_roles` [admin, manager, finance] → `services/analytics_config.py`.

## F1 — yang dikerjakan
- `services/analytics_facts.py`: baris fakta per baris SO × anggota sales (rumus di docstring), `rebuild(from)`,
  `sync()` inkremental via watermark `updated_at`, `ensure_fresh()` dipanggil sebelum kueri penjualan (fakta tak pernah
  tertinggal > 60 dtk; peringatan "Data penjualan hingga HH:MM WIB"). Job scheduler `ai_fact_sync` (5 menit) &
  `ai_fact_nightly` (02.00 WIB, 90 hari).
- `services/analytics_catalog.py`: 30 metrik & 19 dimensi Katalog §B–C sebagai data (sumber, agregasi, satuan, definisi,
  izin modul, syarat margin/nilai stok).
- `services/analytics_engine.py`: validasi (≤6 metrik, ≤3 dimensi, dimensi didukung) → hak akses (entitas, sales-sendiri
  via atribusi, lini, margin, nilai stok, izin modul → `denied`) → agregasi Mongo (`maxTimeMS` 10 dtk) → turunan
  (avg_order_value, gross_margin_pct, target_achievement_pct), pembanding, `_delta`, `_delta_pct`, `_share`, total dari
  seluruh data, qty otomatis dipisah per satuan, nama tampilan di-join setelah agregasi, maks 200 baris kembali / 5.000
  disimpan di `ai_results` (TTL 30 hari). `analyze_change`: kontribusi + baris "Lainnya" → Σ = perubahan total.
- Endpoint (`routers/ai_analytics.py`): `GET /api/ai/catalog`, `POST /api/ai/query`, `POST /api/ai/analyze-change`,
  `GET /api/ai/results/{id}` (pemilik/admin), `GET /api/ai/facts/status`, `POST /api/ai/facts/rebuild?from=` (admin, audit).

## Keputusan yang saya ambil sendiri (mohon dikonfirmasi)
1. Bawaan keputusan klien §7 = usulan dokumen (net_order, team_split, margin admin/manager, nilai stok + finance).
2. Peran asisten sementara = daftar bawaan `ai.enabled_roles` (konstanta di router; jadi konfigurasi di F2).
3. Sales dibatasi menurut **atribusi fakta** (sales_team/sales_id/pembuat/pemilik pelanggan), piutang/uang masuk/retur
   menurut pelanggan yang dipegangnya.
4. `ap_outstanding` = grand_total − amount_paid tagihan supplier yang belum lunas; jatuh tempo memakai `due_date`, bila
   kosong `bill_date`.
5. Metrik posisi (piutang, hutang, stok) dengan `time_grain` → satu baris posisi saat ini + peringatan (snapshot harian = F5).
6. `new_customers` hanya mendukung dimensi entity/sales_person/customer/customer_city/customer_segment/date.
7. Pembanding + `time_grain` → pembanding hanya di total (baris tren tidak dipasangkan) + peringatan.

## Hal yang belum yakin
- `payment_status`/`order_status` untuk piutang dan pembayaran parsial vendor bill mengikuti field yang ada di seed.
- Nama model `gpt-6-sol`/`gpt-6-luna` dan fitur `prompt_cache_breakpoint` harus dibuktikan lewat spike §7.2 di akun OpenAI klien.

## Test
- `tests/test_tanya_kn_f0_time.py` (6), `tests/test_tanya_kn_f0_access.py` (4), `tests/test_tanya_kn_f1_engine.py` (12) → 22/22 lulus.

## F2 sisa–F5 — yang dikerjakan (2026-09-27)
- Mode uji: `ai.model_main` berawalan `mock` + `ai.enabled` → chat tanpa OpenAI (template terdekat).
- Routing: `ai_templates.route` = min(rasio karakter, Jaccard kata) ≥ `ai.route_threshold_pct` (90) → dijawab template tanpa model.
- Narasi: `services/ai_narrative.py` — otomatis dari angka server; AI (`ai.model_fast` luna / `ai.model_main` sol) via `POST /api/ai/narrative` bila AI aktif & anggaran ada.
- Biaya: `services/ai_cost.py` (harga perkiraan, `cost_usd` di `ai_usage_log`), `ai.monthly_budget_usd` 100, `GET /api/ai/usage`; `ai.enabled_roles`.
- Cache: `ai_result_cache` (TTL; `ai.template_cache_minutes` 5, periode tertutup 24 jam).
- Jadwal: `services/ai_schedules.py`, koleksi `ai_schedules`/`ai_schedule_runs`, job `ai_schedule_dispatch` (5 mnt, CAS next_run_at), notifikasi in-app link `tanya-kn`.
- Snapshot: `services/analytics_snapshots.py` → `fact_stock_daily`/`fact_ar_daily` (job 23.55), mesin memakai snapshot untuk periode yang sudah lewat.
- Pemeliharaan: job `ai_maintenance` (retensi `ai.chat_retention_days` 180), `ai_prewarm` (06.55, `ai.prewarm_enabled` mati).
- Eval: `backend/tools/ai_eval/` — `build_questions.py` → `questions_v1.json` (120), `run_eval.py --mode engine|model`.
- Test: `tests/test_tanya_kn_f4_f5.py` (7) + f2_f3 (6) → lulus (iteration_75).

## F6 — Jawaban bertahap + Halaman Biaya AI (2026-09-27)
- SSE delta kata demi kata, `delta_reset`, `done.text`; tab Biaya + `GET /api/ai/usage/daily`; seed contoh `scripts/seed_ai_usage_demo.py`. Uji iteration_76.
