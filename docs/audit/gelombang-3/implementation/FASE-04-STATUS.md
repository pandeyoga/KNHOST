# Gelombang 3 · Fase 04 — Status implementasi (2026-10-06)

Status agent paling jauh `implemented_pending_validation`. Uji: `cd /app/backend && DB_NAME=g3_audit_phase04 python -m pytest tests/test_g3_phase04.py -q -n 0` (17 tes) + regresi Fase 01–03 (87 tes).

Keputusan user (2026-10-06, semua opsi a): nilai persediaan = biaya penuh (dasar + landed, dirinci); pelanggan baru = pertama di lini terpilih; turnover memakai tanggal keluar resmi — data lama tanpa tanggal TIDAK dihitung dan ditandai; reach per platform/akun = atribusi bersama, tidak dapat dijumlah; bobot KPI 0 sah (tidak dihitung). Default agent: tanggal tanpa zona = tanggal WIB (timestamp naif = UTC), skor KPI 0–150 otomatis & manual, akurasi cycle count dari hitungan selesai, payroll dari run posted/paying/paid.

| ID | Status | Ringkasan |
|---|---|---|
| D4-STOCK-02 | implemented_pending_validation | whitelist produk kategori diterapkan sebelum roll/balance/movement → aging = baris |
| D4-STOCK-03 | implemented_pending_validation | nilai = `unit_cost` penuh; `value_base/value_landed`, `total_base_value/total_landed_value`, `cost_basis=full_landed` |
| D4-STOCK-04 | implemented_pending_validation | `_parse_ts` selalu aware (date-only = WIB, naif = UTC, invalid = None); umur = hari kalender WIB |
| D4-AI-02 | implemented_pending_validation | `_src_fact_new` memakai `sc.line_q` sebelum grouping first-purchase |
| D4-AI-03 | implemented_pending_validation | upsert deterministik per `_id` lalu pensiunkan baris basi; rebuild penuh per `build_gen`, hapus generasi lama hanya setelah sukses; `last_error` di state |
| D4-AI-04 | implemented_pending_validation | `_alloc` largest-remainder dalam sen untuk net/gross/PPN/HPP per baris lalu per anggota sales |
| D4-HR-01 | implemented_pending_validation | semua run posted/paying/paid per periode dijumlah (multi-PT); `runs`, `unposted_runs`; tren = agregator sama |
| D4-HR-02 | implemented_pending_validation | field `separation_date` (+`separation_history` saat rehire); diisi saat nonaktif (input HR / `end_date` / hari ini WIB); turnover dari tanggal itu; `missing_separation_date` ditampilkan; input "Tanggal Keluar (resmi)" di form karyawan |
| D4-WMS-01 | implemented_pending_validation | RED hari ini = rentang WIB → UTC |
| D4-WMS-02 | implemented_pending_validation | `last_cc` = hitungan terukur non-void/rejected; `latest_cc_status` terpisah; UI N/A + "hitung baru: berjalan" |
| D4-MKT-01 | implemented_pending_validation | `breakdown_basis=shared_post_attribution`, `breakdown_additive=false`; label UI |
| D4-RND-01 | implemented_pending_validation | kunci `u:<user_id>` (legacy `n:<nama>` ditandai `legacy_name_only`), `name_ambiguous`; tren per kunci |
| D4-EQ-01 | implemented_pending_validation | `net_income`/`period_operating_net_income` dari P&L non-penutup; `movement_unclosed_earnings` terpisah |
| D4-WMS-04 | implemented_pending_validation | `putaway_block_reason` bersama (health & suggest); `putaway_pending/ready/blocked/blocked_by_reason` |
| D4-SIM-01 | implemented_pending_validation | simulator memanggil `evaluate_match`; diterima 0/tagih>0 → block |
| D4-BANK-01 | implemented_pending_validation | `strict_iso_date` di parser + `import_lines` (semua jalur), `line_errors` per baris |
| D4-BANK-02 | implemented_pending_validation | marker `R?[CD]` + funds code; RC=keluar, RD=masuk, flag `reversal`; tanggal valuta invalid → error |
| D4-RET-CHAIN-01 | implemented_pending_validation | kelompok (pemilik, satuan) + `held_groups` terstruktur |
| D4-ALERT-DATE-01 | implemented_pending_validation | jatuh tempo = tanggal kalender WIB, selisih hari kalender |
| D4-ALERT-AMT-01 | implemented_pending_validation | saldo dari `bill_financials` (SSOT AP); lunas dilewati; body "sisa X dari Y" |
| D4-KPI-WEIGHT-01 | implemented_pending_validation | 0 tetap 0, None=1, negatif ditolak; rata-rata (BE/FE) mengabaikan bobot 0; semua 0 → None ("—") |
| D4-KPI-PERIOD-01 | implemented_pending_validation | validator `YYYY-(01..12)` create/update; metrik kosong ditolak saat update; periode lama invalid dipisah (`invalid_periods`) |
| D4-KPI-SCORE-01 | implemented_pending_validation | skor otomatis dibatasi 0–150; nilai tak hingga → 0 |
| D4-BUD-THRESHOLD-01 | implemented_pending_validation | ambang 0 dipakai apa adanya; hanya None → 85 |

Tambahan: ekspor Excel profitabilitas `GET /api/finance/profitability/export.xlsx` (sheet Per Pelanggan, Per Produk, Keterangan; HPP/marjin hanya untuk admin/manager), tombol `prof-export-xlsx`.

Batas: return chain hanya diuji lewat telaah kode + testing agent (belum ada unit test fixture linked-roll). Data lama `hr_employees` nonaktif tanpa `end_date` tidak di-backfill (sesuai keputusan).
