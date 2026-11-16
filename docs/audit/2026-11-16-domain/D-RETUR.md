# D — Retur (jual & beli) — audit §8

HEAD: `91a3ec0`. Data acuan: 0 `sales_returns`, 0 `purchase_returns` → alur retur E2E `terhambat`; RT-01 terbukti tingkat kode.

## Peta sumber kebenaran: status & penyelesaian retur

```
grep -rnE 'TRANSITIONS|assert_transition|FAMILY_STATE' backend/services/return_state.py backend/services/sales_return_transition.py backend/services/return_roll_settlement_service.py
grep -rnE 'SUPPLIER_STATES|TRANSITIONS' backend/services/purchase_return_state.py backend/services/purchase_return_doc_state.py
```
Penulis: `backend/services/return_state.py` (tabel transisi tunggal) · `backend/services/sales_return_transition.py:38` (assert_transition) · `backend/services/return_roll_settlement_service.py:31` (FAMILY_STATE→return_state) · `backend/services/purchase_return_state.py:27` (RMA supplier) · `backend/services/purchase_return_doc_state.py:28` (status dokumen).

## Pintu ganda

| Pekerjaan | Pintu | Seharusnya |
|---|---|---|
| Status retur jual | satu tabel `return_state.TRANSITIONS` (SAH) | — (bukan duplikat) |
| Penyelesaian retur | roll_settlement / compensation / replacement / cutloss_split | satu pintu penyelesaian (perlu verifikasi data) |

## Matriks skenario

| Skenario | Status | Bukti/alasan |
|---|---|---|
| D-S1 | terhambat | retur jual per roll E2E: 0 sales_returns di seed |
| D-S2 | terhambat | scrap/batal scrap: butuh retur |
| D-S3 | terhambat | klaim ke supplier berantai: butuh retur jual+beli |
| D-S4 | terhambat | retur sebagian/cut-loss: butuh retur |
| D-S5 | terhambat | penggantian/kompensasi/nego: butuh retur |
| D-S6 | terhambat | retur beli sebelum/sesudah tagih + reverse: butuh retur beli |
| D-S7 | terhambat | retur antar-PT: butuh retur |
| D-S8 | terhambat | retur ditolak/batal: butuh retur |

## Inventaris form & dropdown

| Form | Field | Sumber pilihan | Saringan | Ditegakkan server? | Masalah |
|---|---|---|---|---|---|
| CreateReturnForm.jsx | order-select (194) | SO terkirim | — | ya | — |
| CreateReturnForm.jsx | type-select (220) | jenis retur | — | ya | — |
| CreateReturnForm.jsx | condition (312) | `CONDITION_OPTIONS` | — | ya | — |
| CreateReturnForm.jsx | reason (332) | `reasons` | — | ya | — |
| ReturnDispositionPanel.jsx | (ikuti anak) | aksi disposisi | per status | ya | tak ada dropdown sendiri |
| ReturnRollClaims.jsx | condition (71) | `CONDITION_OPTIONS` | — | ya | — |
| PurchaseReturns.jsx | supplier (377) | `suppliers` | — | ya | tak per aktif/PT |
| PurchaseReturns.jsx | po-select (381) | PO supplier | per supplier | ya | — |
| PurchaseReturns.jsx | warehouse (385) | `warehouses` | — | ya | tak per PT |
| PurchaseReturns.jsx | product (401) | `products` | — | ya | — |
| PurchaseReturns.jsx | reason (409) | `REASONS` | — | ya | — |
| PurchaseReturns.jsx | basis (414) | opsi basis | — | ya | — |

## Temuan

### RT-01 — pembagian state retur SAH (bukan duplikat)
- Keparahan: Rendah
- Jenis akar: status
- Tingkat bukti: dugaan (baca kode)
- Bukti: `backend/services/sales_return_transition.py:38` (satu tabel `return_state`); `backend/services/purchase_return_state.py:27` vs `backend/services/purchase_return_doc_state.py:28` (dua sumbu).
- Reproduksi: baca kode; uji runtime butuh retur (0 di seed).
- Dampak: — (menutup kecurigaan duplikasi).
- Arah perbaikan: —.
- Keputusan pemilik: —.
- Sudah ada: —.

### RT-02 — banyak sub-service penyelesaian retur (risiko uang/stok ganda)
- Keparahan: Rendah
- Jenis akar: duplikasi (dugaan)
- Tingkat bukti: dugaan (baca kode)
- Bukti: `backend/services/return_roll_settlement_service.py:31` + `backend/services/return_compensation_service.py` + `backend/services/return_replacement_service.py`.
- Reproduksi: butuh retur per-roll melewati penyelesaian (0 di seed) — uji runtime yang dibutuhkan untuk membuktikan/menggugurkan.
- Dampak: potensi kompensasi/stok ganda bila >1 pintu menyelesaikan satu retur.
- Arah perbaikan: satu pintu penyelesaian + satu status.
- Keputusan pemilik: —.
- Sudah ada: —.
