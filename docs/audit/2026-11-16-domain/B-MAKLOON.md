# B — Makloon (SPK) — audit §8

HEAD: `91a3ec0`. Backend hidup + data acuan (3 SPK makloon seed: tenun/rajut/celup). Skenario via API/data; alur E2E multi-langkah (issue→terima→QC→HPP) yang butuh membuat & menjalankan SPK baru ditandai `terhambat` (butuh rangkaian mutasi besar) dengan bukti struktural dari SPK seed.

## Peta sumber kebenaran: langkah & stage makloon

```
grep -rnE 'post.*makloon-orders|realize-makloon' frontend/src/features/purchasing
grep -nE '_resolve_stage|from_stage|to_stage|process_stages|stage_by_process_type' backend/services/makloon_order_service.py backend/services/master_registry.py
grep -n 'STAGE_OPTS|stageOpts' frontend/src/features/purchasing/RecipeFormModal.jsx frontend/src/features/purchasing/makloon/MakloonStepEditor.jsx
```

Penulis/sumber (berkas:baris HEAD):
- SPK dibuat: `backend/services/makloon_order_service.py:1` (create) dari dua pintu FE `frontend/src/features/purchasing/makloon/MakloonWizard.jsx:307` dan `frontend/src/features/purchasing/MakloonOrderCreateModal.jsx:192`.
- Stage langkah: `backend/services/makloon_order_service.py:56` (`_resolve_stage`) baca master `backend/services/master_registry.py:199` (`stage_by_process_type`).
- Terima/issue: `backend/services/makloon_order_service.py:697` (issue_step) & `backend/services/makloon_order_service.py:1019` (receive_step).
- Sumber stage FE tak konsisten: `frontend/src/features/purchasing/RecipeFormModal.jsx:12` (`STAGE_OPTS` hardcode) vs master di modal order.
Bukti runtime: ke-3 SPK seed menyimpan `from_stage`/`to_stage` KOSONG (`bukti/B-S1-S8.txt`) → tak ada batas stage untuk ditegakkan.

## Pintu ganda

| Pekerjaan | Pintu sekarang | Seharusnya |
|---|---|---|
| Buat SPK makloon | Wizard (`MakloonWizard.jsx:307`, dari PR) vs Modal (`MakloonOrderCreateModal.jsx:192`, dari resep) — keduanya POST `/makloon-orders` | satu wizard dua-mode |
| Sumber stage langkah | master `process_stages` (modal/step) vs `STAGE_OPTS` hardcode (`RecipeFormModal.jsx:12`) | satu sumber dari server |
| Validasi transisi stage | tak ada (step simpan from/to kosong) | satu validator (resolve_transition) |

## Matriks skenario

| Skenario | Status | Bukti/alasan |
|---|---|---|
| B-S1 | terhambat | greige→PFD→celup→finished E2E: butuh buat+jalankan SPK multi-langkah (issue/terima/QC); SPK seed tak berjalan. Bukti struktural: `bukti/B-S1-S8.txt` (from/to_stage kosong) |
| B-S2 | terhambat | greige→PFP→screen→printing→finished E2E: idem |
| B-S3 | terhambat | benang→tenun/rajut→greige E2E: idem (SPK tenun/rajut seed ada tapi belum dijalankan) |
| B-S4 | terhambat | terima sebagian + susut>batas: butuh receive_step dgn qty sebagian (mutasi berantai) |
| B-S5 | terhambat | hasil ditolak QC→kembali/klaim mitra: butuh QC hasil makloon (data QC 0) |
| B-S6 | terhambat | batal di tengah saat bahan di mitra: butuh issue lalu cancel |
| B-S7 | lulus | bukti/B-S7.txt — dua pintu aktif + sumber stage tak konsisten (master vs STAGE_OPTS hardcode) |
| B-S8 | terhambat | tagihan jasa/HPP ke roll+jurnal: SPK seed tarif=0, `makloon_material_ledger`=0, jurnal makloon=0 (`bukti/B-S1-S8.txt`); butuh jalankan sampai selesai |
| B-S9 | terhambat | repair/rework: butuh SPK selesai lalu repair order |
| B-S10 | terhambat | antar-PT: butuh SPK bahan milik PT lain |

## Inventaris form & dropdown

| Form | Field | Sumber pilihan | Saringan yang ada | Ditegakkan server? | Masalah |
|---|---|---|---|---|---|
| MakloonWizard.jsx | mode (355) | `MODE_OPTS` | — | ya | — |
| MakloonWizard.jsx | gudang sumber (371) | `whOpts` | aktif? | ya | tak per PT |
| MakloonWizard.jsx | gudang tujuan (375) | `whOpts` | aktif? | ya | tak per PT |
| MakloonWizard.jsx | supplier bahan (379) | `supOpts` | — | ya | tak per aktif/PT |
| MakloonOrderCreateModal.jsx | mode (220) | `MODE_OPTS` | — | ya | — |
| MakloonOrderCreateModal.jsx | recipe (221) | `recipeOpts` | — | ya | — |
| MakloonOrderCreateModal.jsx | supplier (230) | `supOpts` | — | ya | tak per PT |
| MakloonOrderCreateModal.jsx | material-unit (260) | satuan | — | ya | — |
| MakloonOrderCreateModal.jsx | stage (262) | `stageOpts` (master) | tak per bahan masuk | sebagian | beda sumber dgn RecipeFormModal |
| MakloonOrderCreateModal.jsx | flow pick (281) | `FLOW_PICK_OPTIONS` | — | ya | — |
| MakloonOrderCreateModal.jsx | gudang sumber (297) | `whOpts` | — | ya | tak per PT |
| MakloonStepEditor.jsx | stage (182) | `stageOpts` hardcode | TIDAK per bahan masuk | tidak (step simpan kosong) | MK-02/MS-04 |
| MakloonStepEditor.jsx | flow pick (230) | `FLOW_PICK_OPTIONS` | — | ya | — |
| MakloonStepEditor.jsx | basis tarif (298) | konstan basis | — | ya | — |
| MakloonStepEditor.jsx | aux basis (404) | `AUX_BASIS_OPTIONS` | — | ya | — |
| MkoStepModals.jsx | issue gudang (98) | `opts` | — | ya | — |
| MkoStepModals.jsx | issue mode (102) | `ISSUE_MODES` | — | ya | — |
| MkoStepModals.jsx | issue uom (119) | `uomOpts` | — | ya | — |
| MkoStepModals.jsx | terima gudang (200) | `whOpts` | — | ya | — |
| MkoStepModals.jsx | terima uom (213) | `uomOpts` | — | ya | — |
| MkoStepModals.jsx | roll grade (230) | grade | — | ya | — |
| RecipeFormModal.jsx | process-type (100) | `PROC_OPTS` hardcode | — | ya | sumber proses hardcode |
| RecipeFormModal.jsx | input-stage (109) | `STAGE_OPTS` hardcode | — | ya | beda sumber dgn master (MS-03) |
| RecipeFormModal.jsx | output-stage (116) | `STAGE_OPTS` hardcode | — | ya | idem |
| RecipeFormModal.jsx | tariff-unit (139) | `TARIFF_UNITS` | — | ya | — |
| MakloonOrderDetailPanel.jsx | (ikuti anak) | memakai MkoStepModals/StepEditor | — | — | tak ada dropdown sendiri |

## Temuan

### MK-01 — dua pintu aktif pembuatan SPK makloon
- Keparahan: Sedang
- Jenis akar: pintu ganda
- Tingkat bukti: terbukti runtime
- Bukti: `frontend/src/features/purchasing/makloon/MakloonWizard.jsx:307` & `frontend/src/features/purchasing/MakloonOrderCreateModal.jsx:192`; `bukti/B-S7.txt`.
- Reproduksi: buat SPK dari Wizard (via PR) & dari Modal (via resep); `bukti/B-S7.txt`.
- Dampak: dua UX/prasyarat beda ke endpoint sama; mudah salah pintu, aturan beda.
- Arah perbaikan: satu wizard dua-mode; matikan pintu lama.
- Keputusan pemilik: satukan dua pintu makloon?
- Sudah ada: —

### MK-02 — langkah makloon tak menegakkan stage bahan masuk (from/to kosong)
- Keparahan: Tinggi
- Jenis akar: aturan tidak ditegakkan / cacat logika
- Tingkat bukti: terbukti runtime
- Bukti: `backend/services/makloon_order_service.py:1019` (receive_step tak adu stage); ke-3 SPK seed simpan `from_stage`/`to_stage` kosong (`bukti/B-S1-S8.txt`); dropdown `frontend/src/features/purchasing/makloon/MakloonStepEditor.jsx:182` tak disaring.
- Reproduksi: lihat langkah SPK seed `bukti/B-S1-S8.txt` (from/to kosong); langkah printing bisa menerima bahan non-PFP.
- Dampak: bahan salah-tahap bisa diproses; transisi stage nominal.
- Arah perbaikan: simpan & validasi from/to_stage per langkah via validator transisi tunggal; saring dropdown per bahan masuk.
- Keputusan pemilik: dari mana sumber transisi stage (master vs kode)?
- Sudah ada: MS-02, MS-04.

### MK-03 — SPK langkah bisa in_process tanpa mitra
- Keparahan: Sedang
- Jenis akar: status (keputusan pemilik 3b)
- Tingkat bukti: terbukti runtime
- Bukti: `backend/services/makloon_order_service.py:291` (needs_vendor peringatan); SPK seed `in_process` dengan mitra kosong (`bukti/B-S1-S8.txt`).
- Reproduksi: `bukti/B-S1-S8.txt` menunjukkan mitra '-' pada langkah in_process.
- Dampak: SPK macet di issue/catat jasa kemudian; blokir muncul belakangan.
- Arah perbaikan: status "menunggu mitra" eksplisit + blok tindakan lanjutan, atau wajibkan mitra.
- Keputusan pemilik: tetap izinkan SPK tanpa mitra (3b)?
- Sudah ada: —

### MK-04 — sumber stage/proses resep hardcode di frontend (beda dari master)
- Keparahan: Sedang
- Jenis akar: duplikasi
- Tingkat bukti: terbukti runtime (grep)
- Bukti: `frontend/src/features/purchasing/RecipeFormModal.jsx:12` (`STAGE_OPTS` hardcode) & `recipe-process-type` (`PROC_OPTS`) vs modal order baca master `process_stages`; `bukti/B-S7.txt`.
- Reproduksi: bandingkan dropdown stage di RecipeFormModal (hardcode) vs MakloonOrderCreateModal (master).
- Dampak: tahapan baru di master tak muncul di form resep; data resep bisa menyimpang.
- Arah perbaikan: resep baca stage/proses dari server (satu sumber).
- Keputusan pemilik: —
- Sudah ada: MS-03.
