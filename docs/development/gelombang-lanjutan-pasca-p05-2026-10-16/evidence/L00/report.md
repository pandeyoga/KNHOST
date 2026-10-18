# Laporan Fase L00 — Baseline, penyelarasan keputusan, dan kontrak perubahan

ERP Kain Nussantara · PT Kubus Teknologi Indonesia · 2026-10-16

## Identitas

- Repo: `https://github.com/pandeyoga/KNHOST` branch `main`.
- HEAD yang di-clone: `64d81f29577dae4daa86ddc64689dec7243804f2`. Ini sama dengan baseline paket, jadi delta terhadap snapshot = 0 commit dan tidak ada diff yang perlu dibaca ulang.
- Workspace: preview Emergent (`/app`). Riwayat git workspace berbeda dengan GitHub. SHA implementasi baru tersedia setelah "Save to GitHub". Karena itu status requirement L00 masih `in_progress`, belum `implemented_pending_validation`, sampai SHA penuh dicatat (validator mewajibkan full SHA).
- Pelaksana: agent development (E1). Reviewer dan owner: belum ada.
- Lingkungan uji:
  - Data acuan memakai `bash scripts/restore_local_demo.sh`, yaitu urutan `deploy/setup_demo_lengkap.sh` sampai `seed_p05_kn.py`, dengan `KN_DEMO_DATA="true"` dan `CORS_ORIGINS` eksplisit.
  - Semua seed exit 0. Fondasi `uoms`, `gl_accounts`, `expense_categories` sudah ada.
- Pekerjaan lokal pengguna tidak di-reset. Paket hanya ditambahkan ke `docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/`, tanpa menimpa source atau tracker lama.

## LN-001 — Rekonsiliasi fase lama

Sumber: `docs/development/meeting-wms-fingerprint-2026-10-11/BACKLOG.json`. Tercatat 35 requirement: 22 `implemented_pending_validation` dan 13 `not_started`. Tercatat 67 ACC: 21 pass dan 46 not_run. Tidak ada fase lama yang tervalidasi.

| Fase lama | Status sumber | Disposisi pada gelombang L |
|---|---|---|
| P00 | in_progress (ACC-00 not_run) | **Diganti** oleh L00 (laporan ini). |
| P01 | impl_pending_validation; ACC-01..05 pass | ACC-01 (tahap jual) **diuji ulang** di L01, karena keputusan baru membolehkan PFD/PFP dijual, sedangkan greige tidak. ACC-02/03/04 **dipertahankan sebagai bukti lama** dan diuji ulang di L01 bila master berubah. ACC-05 **diuji ulang** di LN-010-T03 (scope lokasi). |
| P02 | ACC-06/08/10/12/13 pass; 07/09/11 not_run | Pass **dipertahankan**, perlu impact assessment di L10. ACC-07/09/11 **dipindah** ke L10 (LN-100). |
| P03 | ACC-14/15/18/19 pass; 16/17/20 not_run | Pass **dipertahankan**, dicek ulang di L04/L07. ACC-16/17/20 **dipindah** ke L07 (LN-070..072). |
| P04 | ACC-21..28 not_run | **Diganti** oleh L02 (LN-020..022). Aturan grade pelanggan berubah dari allowlist ke minimum rank (LN-012). |
| P05 | ACC-29..35 pass | ACC-35 (jalur restock) **gagal terhadap keputusan baru**: P05 memakai hard block, sedangkan keputusan baru = default/rekomendasi. Diganti LN-013-T01. ACC-29..34 **dipertahankan**, perlu retest L04 karena retur bahan berubah (lihat di bawah). |
| P06 | not_started | → L03. |
| P07 | not_started | → L06. |
| P08 | not_started | → L10. |
| P09 | not_started | → L13 (butuh perangkat nyata, HW-02/HR-01). |
| P10 | not_started | → L14. |

### Empat open issue P05 — reproduksi dan tindakan

| # | Issue | Reproduksi pada baseline | Tindakan L00 | Bukti |
|---|---|---|---|---|
| 1 | Uji ulang SKU paralel tidak atomik | `prepare_revalidation` hanya `find_one` lalu `insert_one`, sehingga dua request paralel bisa lolos (race TOCTOU). | Ditambah unique multikey index `uniq_open_revalidation` pada `md_samples.open_reval_keys` (`<product_id>:<jenis>`), partial bila field ada. Index dibuat saat bootstrap dan backfill open sample lama. Key dicabut saat `cancel`/`decided`. Insert ganda menghasilkan `DuplicateKeyError`, lalu 400. | `backend/tests/test_l00_p05_open_issues.py::TestRevalidationRace`: 6 request paralel menghasilkan tepat 1 sukses. Sesudah batal, uji baru bisa dibuat. |
| 2 | Opsi "ACC spesifikasi" tampil untuk uji ulang | `DecideModal.jsx` memakai `sample.spec` tanpa memeriksa `purpose`. Server mengabaikannya, tapi UI menyesatkan. | Untuk `purpose=revalidation`, `spec=null`: blok "Master produk" disembunyikan dan dampak menampilkan `decide-revalidation-sku` ("SKU & spesifikasi tidak berubah"). | Build FE; verifikasi UI oleh reviewer. |
| 3 | Retur bahan makloon hanya per langkah utuh | `return_cancelled_material` memindah semua roll `issue_ref` dan membalik seluruh WIP. | API baru `GET /api/makloon-orders/{id}/steps/{seq}/partner-rolls`. `POST …/return-material {reason, roll_ids?}` bisa memilih sebagian roll. WIP dibalik **pro-rata qty yang kembali**, retur terakhir menghabiskan sisa nilai. Idempotency jurnal per himpunan roll. Update roll bersyarat `bucket_ref.id`, jadi roll yang sama tidak bisa kembali dua kali (409). Langkah tetap `issued/awaiting_return` sampai semua roll kembali. Riwayat `material_returns` tercatat. UI memakai checklist roll (`mko-return-roll-<id>`, `mko-return-summary-<seq>`, `mko-return-history-<seq>`). | `TestPartialMaterialReturn`: retur 1 roll, stok +q, WIP = nilai×(1−q/30), ulang 409. Retur sisa: `returned`, WIP 0, ulang 409. Regression P05 ACC-34 tetap lulus (retur penuh pertama memakai source id lama). |
| 3b | **Susut/hilang di mitra** | Belum ada perlakuan. | **Tidak diimplementasikan, menunggu keputusan.** Akun beban, klaim ke mitra, atau potong tagihan jasa adalah keputusan Finance/owner. Roll yang tidak kembali tetap tercatat di mitra (WIP tetap), tidak dihapus diam-diam. Dicatat sebagai temuan keputusan baru **L00-F01** (lihat di bawah), terkait LN-043. | — |
| 4 | Detail MKO tidak bisa dibuka dari HP | View `makloon-orders` tidak termasuk workspace responsif. MobileOpsApp dan MobileMdApp tidak punya pintu masuk. | `makloon-orders` ditambahkan ke `responsiveWorkspace` (App.js). Tombol `mobile-open-makloon-orders` ada di tab Produk MobileOpsApp (admin/manager/md). Entri `m-md-full-makloon-orders` ada di MobileMdApp › Lainnya. | Verifikasi UI 390px oleh reviewer. |

Temuan testing agent iteration_183, sudah diperbaiki:
- Dua retur sebagian paralel pada MKO yang sama pernah menimpa riwayat dan membalik WIP berlebih (read-modify-replace tanpa kunci). Sekarang retur memakai `atomic_claim.claim("makloon_orders", …)`. Dokumen dibaca ulang sesudah klaim, sehingga pemanggil kedua mendapat 409 `SAGA_IN_PROGRESS` dan tidak menulis state basi. Roll yang diabaikan dicatat di `ignored_roll_ids`. Bukti: `backend/tests/test_l00_edge_cases.py` 5/5, dijalankan 3× berturut-turut.
- Entri HP Order Makloon sekarang hanya tampil bila akun punya izin `makloon_order.view`. Peran `md` bawaan tidak punya izin ini, jadi pemberiannya mengikuti custom role (L01), bukan hardcode.
- Banner retur menampilkan sisa nilai di mitra. Riwayat retur per kejadian tetap tampil setelah langkah ditutup.
- Data acuan dipulihkan ulang setelah uji race. Rekonsiliasi GL vs subledger dan WIP lulus kembali.

Regression developer pada workspace:
- `test_p05_restock_material_revalidation.py`: 12/12
- `test_p05_acceptance_acc31_33_34.py`: 17/17
- `test_p05_imp16_md_quality_qc.py`: 16 pass, 1 skip env
- `test_l00_p05_open_issues.py`: 5/5
- `test_l00_edge_cases.py` (testing agent): 5/5

Catatan uji: kedua file P05 sebelumnya saling bergantung bila dijalankan dalam satu sesi pytest (sample uji ulang file pertama baru dibersihkan di akhir sesi). Ini temuan tes, bukan bug produk. Jalankan per file.

## LN-002 — Kontrak perubahan aktif

Prioritas sumber: jawaban owner terbaru → keputusan 16 Okt → register historis → plan lama. Keputusan yang dipakai ada di `KEPUTUSAN_AKTIF_RINGKAS.md`. Keputusan owner di chat 2026-10-16 untuk sesi ini (`evidence/L00/owner_decisions_2026-10-16.md`) menggantikan aturan P05/P04 berikut:

| Kontrak | Kondisi baseline (kode) | Kontrak berlaku | Fase |
|---|---|---|---|
| Sumber restock | `restock_source_service.check_lines` **menolak** jalur yang berbeda dari mode (hard block) | Hanya default/rekomendasi. Jalur lain boleh dengan alasan tercatat. Jangan hard block. | L01 LN-013 |
| Grade pelanggan | `customer_grade_rules.allowed_grades` (allowlist, menolak grade lebih tinggi) | Minimum rank. Grade lebih tinggi diterima, lebih rendah ditolak. | L01 LN-012 / L02 |
| Master grade | `domain_registry.GRADES` di-hardcode (A, A1, A2, B, B1, C, BS) | Master grade dapat ditambah, diaktifkan, dan dinonaktifkan dengan rank. Aktif awal A, A1, B, BS. A2, B1, C historis (roll baseline memakai A, A1, B, B1, BS, C). **Semua form pemilih grade** membaca master aktif. | L01 LN-012 |
| Visibilitas grade/LOT/asal | `/api/products` untuk `sales.kanda` mengirim `grade` dan `batch_lot_rolls` | Konfigurasi visibilitas atribut per role (custom role). Default Sales: grade, LOT, dan asal tersembunyi di katalog, detail, facet, API, dan export, termasuk saat trial. | L01 prioritas |
| Hak akses | Per modul 3 tingkat (`access_modules.LEVELS`) + matriks izin | Modul → Menu → Submenu/Tab → Aktivitas, dengan scope entitas/lokasi dan field. Enforcement UI/API/deep link/export. Preview sebagai role. | L01 LN-010/015 |
| Roll/EPC, qty, owner vs posisi, material makloon, finance, device | Lihat tabel kontrak di DEVELOPMENT_PLAN. | Dipakai apa adanya. Snapshot di bawah menjadi angka pembanding. | semua |

Pending tidak diaktifkan: KLR-01..11, KLX-01..03, DATA-01, DES-01..04, OPS-01, HW-01/02, HR-01, UAT-01 tetap `pending`. LN-002-T02 terpenuhi secara desain: tidak ada formula cutloss atau rumus grade inspect baru di perubahan L00.

### Temuan keputusan baru (belum diputuskan)

- **L00-F01** — Bahan makloon susut atau hilang di mitra setelah MKO batal: perlakuan nilai (beban susut, klaim mitra, atau potong tagihan jasa) dan siapa yang berwenang. Sampai diputuskan, roll tetap tercatat di mitra. Terkait LN-043.

## LN-003 — Fixture, angka pembanding, dan dry-run migrasi

`python scripts/l00_baseline_snapshot.py --out <path>` bersifat **read-only** dan tidak menulis DB. Output: `evidence/L00/baseline_snapshot.json`.

- Stok per owner × gudang × satuan × status (roll terbuka), komitmen material aktif, AR per entitas (SO, grand total, terbayar, belum bayar, parsial), AP vendor bill.
- Dry-run integritas pada data acuan:
  - 46.493 roll, **0** roll yatim (produk/gudang/owner hilang)
  - **0** EPC aktif ganda, **0** roll_no ganda per owner, **0** qty negatif
  - **0** selisih `inventory_balances` vs Σ roll (available+reserved)
  - **0** jurnal tidak seimbang
- Master: grade di roll {A, A1, B, B1, BS, C}, sehingga migrasi grade dinamis wajib mempertahankan B1 dan C sebagai historis. Stage {yarn, grey, pfd, pfp, finished, remnant, byproduct}. Custom role 0. Restock mapping 3 template (CONTOH). Aturan grade pelanggan 0, jadi migrasi allowlist ke minimum tidak punya data produksi di preview.
- Fixture sintetis yang sudah tersedia lewat seed: Kanda/Sukacita/CST (`ent_kanda`, `ent_ksc`, `ent_7487424c3f95`), gudang Jakarta/Soreang/Rancamalang, shared warehouse, transfer lintas entitas, SO sebagian dibayar, PR→MKO bahan terkunci. Fixture yang **belum** ada dan dibuat di fase terkait: Tasik/Tamim, user custom role (L01), sampel catalogue (L06).
- Rencana migrasi per fase: backup `mongodump` sebelum `--apply`, dry-run dengan skrip ini sebelum dan sesudah, rollback dengan restore dump. Tidak ada perubahan data produksi di L00. Satu-satunya perubahan skema L00 adalah index `uniq_open_revalidation` dan backfill field `open_reval_keys` pada sample uji ulang terbuka. Rollback: `dropIndex` + `$unset`.

## Status yang diusulkan

- LN-001, LN-002, LN-003: `in_progress`, implementasi dan bukti developer lengkap. Naik ke `implemented_pending_validation` setelah SHA GitHub dicatat.
- Acceptance L00: `not_run` sampai reviewer terpisah memeriksa (validator mewajibkan reviewer nyata untuk `pass`). Hasil aktual developer tercatat di atas.

## Estimasi lanjutan (setelah L00)

L01 adalah fase terbesar berikutnya: editor hak akses 4 tingkat, master grade, visibilitas atribut per role, dan restock default. Urutan kerja: kebocoran grade/LOT ke Sales (prioritas owner) → master grade + semua form grade → aturan grade pelanggan minimum → restock default → editor hak akses 4 tingkat dan enforcement.
