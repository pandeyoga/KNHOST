# Laporan Fase L04 — dimulai (status `in_progress`)

Hanya **LN-042-T01/T02** (potong uji MD Quality) yang sudah diimplementasikan; requirement L04 lainnya belum. Rincian ada di `evidence/HANDOFF_SESI_2026-10-16.md` §4.

## Implementasi
- Service: `backend/services/mdq_cut_service.py`
- Endpoint: `POST /api/inspections/{id}/lines/{line}/mdq-cut` (izin `md_quality.inspect`)
- UI: `frontend/src/features/inspections/MdqCutBox.jsx`

## Bukti
- `backend/tests/test_l04_mdq_cut.py` 4/4
- `backend/tests/test_l04_mdq_cut_edge.py` 6/6
- Laporan testing agent iteration_188 (UI MDQ: 150 → 149,75 yard, `length_initial` tetap 150)

## Belum dikerjakan
- **LN-040:** receiving aktual + OCR per roll
- **LN-041:** pemilihan roll MDQ sudah ada sejak P05; masih perlu diverifikasi terhadap T01/T02
- **LN-042-T03:** reprint label (EPC sama, qty terkini)
- **LN-043:** komitmen greige, issue, hasil fisik vs forecast yield, sisa bahan
- **Butuh keputusan DES-01:** aturan kg↔yard (`kg_per_yard_validated`)
