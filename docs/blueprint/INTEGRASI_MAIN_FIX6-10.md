# Rencana integrasi: `main` (FIX-6…FIX-10) ke cabang blueprint — 15 Nov 2026, belum dikerjakan

`main` di GitHub = `bfb3d0c`: 33 commit FIX-6…FIX-10 (audit WMS-RFID 9–10 Nov, keputusan pemilik 10 Nov) dari `cd6963a`.
Cabang blueprint `claude/nifty-carson-jjx3c8` = `cd6963a` + 309 commit. Keduanya bercabang dari `cd6963a`; uji gabung
(`git merge-tree`) = **22 berkas bentrok**. Penggabungan dicoba lalu **dibatalkan** (`git merge --abort`) karena 6 berkas
backend berisi dua implementasi untuk alur keuangan/stok yang sama — digabung mekanis berisiko jurnal ganda dan pintu kedua.

Cara menggabung (sekali, di cabang blueprint, dengan commit gabungan supaya `main` nanti bisa maju tanpa konflik):
`git fetch origin main && git merge --no-ff origin/main`, selesaikan bentrok menurut tabel di bawah, uji menurut
`03_LINGKUNGAN_UJI.md` §6. Bacaan wajib: `docs/finance/AUDIT_KEUANGAN_2026-11-13.md` (jurnal/retur), laporan PK-27, PK-28,
PK-32, KF-T6, KP-T4, PR-T2 di `docs/reviews/2026-11-13/hasil/`, laporan FIX-6…FIX-10 di `main`, dan
`docs/rfid/KEPUTUSAN_GATE_RFID.md` (H7) untuk berkas RFID.

## Bentrok semantis (butuh keputusan rancangan + uji "satu transaksi = satu jurnal")

| Berkas | Blueprint (cabang ini) | FIX (main) | Risiko bila digabung mekanis | Arah penyelesaian yang diusulkan |
|---|---|---|---|---|
| `services/purchase_return_service.py` (+ `gl_service.py`) | PK-28: dasar jurnal retur (`ap_basis`: GR/IR vs hutang) ditentukan sekali, posting lewat registri tahan-gagal; KP-T5: Nota Debit bernomor per PT | FIX-6 (D2): pilihan per kasus tolak QC (ganti barang / potong tagihan), tabel transisi dokumen, `post_purchase_return_grir` (Dr GR-IR / Cr Persediaan) lewat `purchase_return_remedy.apply_on_approve` | **Jurnal ganda** untuk retur sebelum ditagih (PK-28 dan FIX-6 sama-sama mendebit GR-IR) | Satu pintu posting = jalur PK-28; semantik FIX-6 (ganti barang tanpa Nota Debit, potong tagihan) masuk sebagai `ap_basis`/hasil di jalur itu; `post_purchase_return_grir` tidak dipanggil terpisah; tabel transisi FIX-6 dipakai untuk status; Nota Debit per PT (KP-T5) tetap |
| `services/return_roll_settlement_service.py` | PK-32: nota kredit lewat satu mesin `issue_settlement_note` | FIX-6 (D5): balik karantina roll yang tidak kembali ke stok + pembuatan nota kredit langsung (cara lama) | **Pintu kedua** nota kredit | Pakai pembalikan karantina FIX-6 + mesin nota PK-32; buang pembuatan nota langsung |
| `services/return_service.py` | PK-27: scrap retur menolkan biaya roll + riwayat biaya; batal scrap memulihkan | FIX-10: status roll lewat `roll_state.transition` (CAS + riwayat status) | Salah satu hilang: biaya tidak dinolkan atau status tanpa CAS | `roll_state.transition` dengan `extra_set` berisi kolom biaya PK-27; catatan riwayat biaya tetap |
| `services/inspection_service.py` | PR-T2/PR-T7: wewenang dari izin, `role_in` dihapus | FIX-10 menambah lagi `from role_registry import role_in` (+ `inspection_state`) | Cek **nama peran** kembali (melanggar `02_STANDAR.md` §3) | Pakai `inspection_state`; ganti pemakaian `role_in` dengan izin yang setara |
| `services/makloon_order_service.py` | PK-18: `_post_step_gl` per langkah makloon | FIX-9: `consume_for_issue(..., actor_name)` kunci cadangan per roll | Jurnal langkah hilang bila sisi FIX dipilih | Keduanya: pemanggilan FIX-9 + `_post_step_gl` |
| `routers/cycle_count.py` | KF-T6/KP-T4: `submitted_by_id` (kontrol dua orang), `guard_door` di tolak | FIX-10: `cycle_count_state.transition` | Kontrol dua orang/kebijakan persetujuan hilang | Transisi FIX-10 dengan `submitted_by_id` di `set_fields` + `guard_door` tetap |

## Bentrok mekanis (gabungkan keduanya)

`backend/indexes.py` (indeks AG-T1/AG-T4/PK-20 + `saved_views` FIX-8), `backend/routers/dashboard.py` (WAC sekaligus FIX-7 +
pagar izin pesanan + `segs`), `gl_service.py` (fungsi `landed_cost_lines` PK-26 + tanda tangan `post_landed_cost`
bawaan PK-26; `post_purchase_return_grir` mengikuti keputusan baris pertama tabel atas), `ENTITY_REGISTRY.md`,
`docs/reviews/TRACKER.md`, `scripts/gate.sh` (gate kedua sisi), `scripts/guardrails/verify_atomic_claim.py` (daftar
`REVIEWED` kedua sisi + pembantu CAS FIX-10), `frontend/src/styles/standard.css`, `LocationScopeBar.jsx`,
`approvalInboxData.js`, `IntercoReturnsPanel.jsx`, `IntercoView.jsx`, `InspectLineModal.jsx`, `RfidGateMonitorView.jsx`
(tampilan saja — logika gerbang tidak diubah, H7). Dibangkitkan ulang: `CODEBASE_MAP.md`,
`frontend/src/config/__tests__/fixtures/access_builtin_fixture.json`.

## Sesudah menggabung

- Penjaga yang wajib bersih: `verify_posting_coverage` (sumber jurnal FIX-6 terdaftar atau dilebur), `verify_atomic_claim`,
  `verify_roll_status_writer` (INV-ROLL-02, FIX-10), `verify_role_gate_ui`, `verify_cash_single_door`,
  `bandingkan_pelanggaran_gate.py` terhadap `garis-dasar-gate/2026-11-15_gate_ci.log`.
- Uji baru: retur beli tolak QC (ganti barang, potong tagihan sebelum/sesudah tagihan) → tepat satu jurnal; penyelesaian
  retur per roll → tepat satu nota kredit; scrap/batal scrap → biaya & status roll benar.
- `tests_mem` dan jest penuh sekali pada pohon akhir; uji lama FIX (backend/tests) yang disebut laporan FIX-10.
- Skrip data produksi FIX-6/FIX-7 (`PANDUAN-SKRIP-DATA-PRODUKSI.md` di `main`) dicek ulang terhadap skema blueprint
  sebelum dijalankan pada data yang sudah memakai kode blueprint.
