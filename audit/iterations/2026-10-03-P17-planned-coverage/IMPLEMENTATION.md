# P17 — 9 kasus planned + keputusan pemilik "arsip baca saja"

Permintaan: lanjutkan dari handoff P16 (urutan GRN-04, GRN-06, PROD-04, PROD-06, COMM-04, COMM-05, DESIGN-02, DESIGN-05, OPS-03).
Keputusan user sesi ini: dokumen badan usaha terarsip **boleh dibuka baca saja**; faktur **tetap per pesanan**.
Lingkungan: clone GitHub `main` (b68ae87) → /app, `.restore_env.sh`, seed realistis. Kode diuji = commit `b991f4c`.

## Harness (self-clean, `cd /app/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/<f>.py`)
| Harness | Kasus | Hasil | Temuan & perbaikan |
|---|---|---|---|
| `repro_p17a.py` | GRN-04 | 10/10 | Tanpa perubahan kode (multi-baris, 2 baris SJ ke 1 tugas, tepat 1 tugas sisa, idempoten). |
| `repro_p17b.py` | GRN-06 (API) | 8/8 | Tanpa perubahan kode (timbang netto, not_on_dn memblokir, override butuh hak + audit). OCR & packing list: `tests/test_grn_phase4_read.py`, `tests/test_grn_phase6.py` (-n0). Tes phase6 diselaraskan dengan KN-E22 (stub roll belum diukur tidak dikirim ke penghitung buta). |
| `repro_p17c.py` | PROD-04, PROD-06 | 13/13 | Tanpa perubahan kode (shortage tanpa efek parsial; recovery sesudah worker mati: 409 SAGA_IN_PROGRESS → lepas kunci admin → konsumsi tepat sekali). |
| `repro_p17d.py` | COMM-04 | 3/7 → 7/7 | **BUG**: akrual insentif beku setelah posting pertama; komisi turun/naik (pembayaran batal/susulan) tidak terkoreksi, saldo 2-1500 tersisa saat payroll. Kini jurnal koreksi `incentive_accrual_adj` (kunci deterministik `{ent}:{periode}@{saldo}`), status = saldo bersih (`services/gl_service.py`, `routers/crm.py`). |
| `repro_p17e.py` | COMM-05 | 5/7 → 7/7 (+race) | **3 BUG** harga pelanggan: (1) PATCH record yang sudah dihapus tertulis diam-diam; (2) hapus ganda bersamaan = 2 efek/audit; (3) dua penetapan bersamaan dengan tanggal mulai sama saling menutup → tidak ada harga berlaku. Kini update bersyarat status + record lebih baru tidak ditutup yang lebih lama (`services/customer_price_service.py`, `routers/customer_prices.py`). |
| `repro_p17f.py` | DESIGN-02 | 6/6 | **BUG**: acuan QC = sample decided terbaru produk walau dimenangkan supplier lain. Kini sample milik supplier barang didahulukan, round & supplier acuan disimpan (`services/inspection_service.py::_baseline_for`). |
| `repro_p17g.py` | DESIGN-05 | 6/6 | Tanpa perubahan kode (bahan sample ⇄ roll ⇄ jurnal 6-7000/1-1300 ⇄ cost_total). |
| `repro_p17h.py` | OPS-03 | 6/6 | Tanpa perubahan kode (impor pelanggan: dry-run, terputus lalu dilanjutkan, ulang idempoten). |
| `repro_p17i.py` | Keputusan pemilik | 7/7 | **Fitur**: entitas terarsip bisa DIBACA (GET) oleh admin/manager & pengguna yang pernah ditugaskan; tulis tetap 403/409. `/auth/me` memuat `archived_entities`; pemilih entitas punya bagian "Terarsip — baca saja" + pita `archived-readonly-banner`. |

Regresi P16: 74/74. Agen uji iterasi 127: backend 6/6, frontend 100% (`uat_iteration_127.json`). Integritas: PASS 246 | FAIL 2 (KANDA/SO-00001 backorder seed, lama).

## Sisa
- GRN-06 UI penuh (OCR/packing list/override lewat layar) hanya smoke; PROD-06 UAT operator layar; COMM-04 biaya kampanye belum punya posting GL; OPS-03 impor produk/stok awal.
- `tests/test_f1a_pricelist.py::TestSOIntegration` 2 gagal — juga gagal di kode GitHub asli (bukan regresi P17).
- `test_core_e1e2_poc.py` 6 gagal karena payload uji lama (validasi telepon 422, short_name) — sudah ada sebelum P17; residu entitas "PT Tabrakan" yang ditinggalkannya sudah dibersihkan.
