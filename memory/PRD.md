# ERP Kain Nusantara (KNHOST) — PRD ringkas
Repo: github.com/pandeyoga/KNHOST (main). Stack: FastAPI + MongoDB + React (bundle statis, rebuild `bash scripts/rebuild_frontend.sh`).
Paket plan: docs/development/gelombang-lanjutan-pasca-p05-2026-10-16 (BACKLOG.json = SSOT, validator `scripts/validate_package.py`).

## Original problem statement (2026-10-19C)
"saya ingin anda lanjutkan development dari repo ini https://github.com/pandeyoga/KNHOST sebelumnya development berhenti ketika testing dan ditengah development, cek commit dan cek plan serta infomasi keputusan yang baru saya putuskan, lalu kerjakan fase perfase, di setiap akhir fasenya commit dan push ke github" (push via scripts/push_github.sh, token sekali pakai).

## Architecture
FastAPI routers/services, MongoDB `test_database`, React feature folders, static FE bundle. Personas: admin, manager, sales, sales_admin, md, warehouse, finance, driver.

## Implemented
- 2026-10-19 (sesi B): 15 keputusan owner KLR-01..11, KLX-01..03, OPS-01 (lihat evidence/HANDOFF_SESI_2026-10-19B.md).
- 2026-10-19 (sesi C): Fase 1 LN-090 grade sama untuk pengganti; Fase 2 LN-033 T08 batal PO/MKO per item OD; Fase 3 LN-012-T04 greige selalu tersembunyi & PFD/PFP dijual, LN-102-T02 kartu Meja Saya; Fase 4 perbaikan hasil uji (realisasi ulang setelah batal, batal SO pengganti kembalikan saldo). Detail: evidence/HANDOFF_SESI_2026-10-19C.md.

## Backlog
- P0: keputusan pending DATA-01, DES-02..04, HW-01/02, HR-01, UAT-01.
- P1: pemecahan fisik roll cutloss & posting ongkir retur (butuh keputusan); duplikasi D1–D8 (butuh persetujuan); tes TestKeepPending basi; filter stage di /api/products.
- P2: review & validasi terpisah (status validated butuh reviewer + owner).
