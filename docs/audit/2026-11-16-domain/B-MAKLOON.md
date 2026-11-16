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
| B-S1 | terhambat | langkah 1 (greige→PFD) dijalankan sampai terima — bukti/runtime/B-S1-S4-S6.txt; langkah 2 celup + HPP akhir belum dijalankan (sesi habis), tarif jasa terbaca 0 |
| B-S2 | terhambat | greige→PFP→screen→printing→finished E2E: idem |
| B-S3 | terhambat | benang→tenun/rajut→greige E2E: idem (SPK tenun/rajut seed ada tapi belum dijalankan) |
| B-S4 | gagal | bukti/runtime/B-S1-S4-S6.txt — kirim 200 kg, terima 100 kg: langkah langsung `received`, sisa 100 kg ditolak 409, seluruh Rp10.880.000 dibebankan ke 100 kg (HPP 2×), saran klaim 2× nilai kurang (MK-05) |
| B-S5 | terhambat | hasil ditolak QC→kembali/klaim mitra: butuh QC hasil makloon (data QC 0) |
| B-S6 | gagal | bukti/runtime/B-S1-S4-S6.txt — batal SPK saat 50 kg di mitra → 200 `cancelled`, langkah tetap `issued`, roll `subcon`, WIP Rp2.720.000 menggantung sampai `return-material` dijalankan manual (MK-06) |
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

### MK-05 — Terima hasil kurang langsung menutup langkah; nilai bahan penuh dibebankan ke hasil dan saran klaim dihitung dua kali
- Keparahan: Tinggi
- Jenis akar: cacat logika
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/services/makloon_order_service.py:1358` (`unit_value=out_uc` = HPP hasil sesudah dibebani) · `backend/services/makloon_order_service.py:1026` (terima kedua ditolak) · `bukti/runtime/B-S1-S4-S6.txt`
- Reproduksi: SPK greige→PFD 200 kg (Rp10.880.000) → `issue` → `receive` 100 kg tanpa tanda parsial. Hasil: langkah `received`, HPP 108.800/kg (bahan 54.400/kg), klaim terbuka `amount_suggested` Rp10.880.000 untuk kekurangan 100 kg; `receive` sisa → 409.
- Dampak: HPP hasil menggelembung 2×; nilai klaim yang disarankan ke mitra = seluruh bahan, bukan nilai yang hilang (Rp5.440.000); 100 kg di mitra hilang dari sistem.
- Arah perbaikan: Hitung nilai kurang dengan HPP bahan sebelum pembebanan; saat hasil < toleransi tanya dulu "sisa masih di mitra?" sebelum menutup langkah.
- Keputusan pemilik: Susut di atas toleransi: tahan penutupan langkah sampai klaim diputus?
- Sudah ada: —

### MK-06 — SPK makloon bisa dibatalkan saat bahan masih di mitra tanpa menarik bahan
- Keparahan: Tinggi
- Jenis akar: status
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/services/makloon_order_service.py:1583` (`cancel_order`) · `backend/routers/makloon_orders.py:321` · `bukti/runtime/B-S1-S4-S6.txt`
- Reproduksi: SPK 50 kg → `issue` → `POST /makloon-orders/{id}/cancel`. Hasil: 200, SPK `cancelled`, langkah tetap `issued`, 3 roll `subcon`, saldo 1-1350 Rp2.720.000. `return-material` masih bisa dijalankan sesudahnya (jurnal balik) tetapi tidak diwajibkan.
- Dampak: Bahan dan nilai WIP menggantung di SPK yang sudah batal; tidak ada antrean yang menagih penarikan.
- Arah perbaikan: Tolak batal selama ada bahan di mitra, atau jadikan batal = tarik bahan dalam satu aksi.
- Keputusan pemilik: —
- Sudah ada: —
