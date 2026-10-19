# ERP Kain Nusantara (KNHOST) — PRD ringkas
Repo: github.com/pandeyoga/KNHOST (main). Stack: FastAPI + MongoDB + React (bundle statis, rebuild `bash scripts/rebuild_frontend.sh`).
Paket plan: docs/development/gelombang-lanjutan-pasca-p05-2026-10-16 (BACKLOG.json = SSOT, validator `scripts/validate_package.py`).

## 2026-10-19 (sesi lanjutan) — implementasi 15 keputusan owner
- KLR-08/09 batas klaim & checklist hangtag · KLR-01/02/06/07 cutloss & diskon · KLR-03/04/05 pesanan pengganti · KLR-10/11 refund/saldo & ongkir · KLX-01 dua kode LOT · KLX-02 form inspeksi manual · KLX-03 cutoff configurable · OPS-01 tanpa batas kerugian.
- Evidence: evidence/L01, L02, L05, L08, L09, L10 report + HANDOFF_SESI_2026-10-19B.md. Testing: test_reports/iteration_klr_klx_ops_1.json (lulus).

## Backlog
- P0: keputusan pending DATA-01, DES-02..04, HW-01/02, HR-01, UAT-01 (jelaskan ke owner).
- P1: duplikasi D1–D8 (butuh persetujuan); grade sama pada alokasi pengganti; posting ongkir.
- P2: review & validasi terpisah (status validated butuh reviewer + owner).
