# P18 — Kasus klien "celup": 20 roll Esmica Blue dimakloon jadi hitam, datang sebagai barang baru

- Asal: pertanyaan klien (4 Nov 2026) — stok 20 roll Esmica Blue dikirim ke mitra celup, kembali sebagai warna hitam
  (SKU baru). Perintah pemilik: **"ya kerjakan"** untuk 4 perbaikan di bawah.
- Commit (branch `main`): `b8a6357`. Baseline: `a8a3f6f`. Status: **implemented_pending_review**.
- Berlaku di HEAD (dicek di kode `a8a3f6f`): **ya** —
  1. issue bahan MKO hanya "berdasarkan jumlah" (sistem memilih roll FEFO, roll bisa dibelah), tidak bisa memilih /
     memindai roll tertentu;
  2. hasil langkah terakhir MKO langsung `available` — tanpa karantina QC, tanpa SPK, tanpa tahap journey
     (tidak masuk antrean tag/putaway);
  3. gate OUT untuk roll `subcon` (dikirim ke mitra makloon) dan roll `wip` (dikirim ke Perbaikan) selalu MERAH
     `NO_DOCUMENT` walau dokumennya sah;
  4. satuan roll hasil/sisa jatuh diam-diam ke `"meter"` bila langkah/produk tidak punya satuan.

## Yang dikerjakan
| # | Perbaikan | Inti |
|---|---|---|
| 1 | Issue per roll (pilih / pindai) | Pop-up Issue punya **"Cara memilih bahan"**: *Berdasarkan jumlah* (bawaan, perilaku lama) / *Pilih roll (centang / pindai)* — daftar roll gudang sumber + EPC, kotak pindai/tempel nomor roll atau EPC (banyak kode sekaligus), total terpilih + peringatan bila ≠ rencana (estimasi hasil diskalakan). Server memvalidasi ulang setiap roll (salah produk/gudang/pemilik/habis → 400; karantina/ditahan/dipesan/dipindah/perbaikan → 409, pesan menyebut nomor roll), semua-atau-tidak-sama-sekali (CAS per roll). Endpoint baru `GET /makloon-orders/{id}/steps/{seq}/issue-rolls`; `POST …/issue` menerima `roll_ids` / `roll_codes` (untuk HP/handheld). |
| 2 | Hasil makloon = barang PO | Langkah **terakhir** (tak ada langkah kain sesudahnya): roll hasil & sisa lahir **karantina** selama `purchasing.qc_on_receipt` aktif (kunci yang sama dengan PO), tugas QC di antrean QC (nomor MKO + nama mitra), **SPK "Inspeksi Hasil Makloon"** otomatis yang memutus karantina (izin sama dengan SPK penerimaan PO), tahap journey `received_transit` (gudang transit) / `stored` (gudang simpan) → antrean tag/verifikasi/putaway, tag RFID otomatis bila `receiving.auto_rfid_on_scan` aktif. Backorder & Pesanan Khusus dipenuhi **setelah QC lulus**. Roll ditolak = "barang rusak" + Klaim Selisih ke mitra (retur supplier/Nota Debit ditolak untuk hasil makloon). Langkah tengah tidak berubah. Aturan bersama diekstrak dari jalur PO (`inbound_qc_common`), bukan disalin. |
| 3 | Gate kenal makloon & perbaikan | `gate_doc_movements`: OUT hijau untuk langkah MKO berstatus *issued* ("… langkah N → nama mitra") dan RPR *Dikirim*; MKO dibatalkan → merah **`DOC_CANCELLED`** (kode baru); langkah/RPR tak aktif → `NOT_RELEASED` dengan alasan jelas; gudang lain → `WRONG_WAREHOUSE`; keluar ulang → `REPLAY_EXIT`. IN hijau untuk roll yang kembali dari perbaikan dan bahan MKO batal ke gudang asal; gudang lain → `WRONG_DESTINATION`. |
| 4 | Penjaga satuan | Produk tanpa satuan dasar di jalur makloon (roll hasil, roll sisa, PO bahan otomatis `buy_process`) → **400 "Satuan dasar produk <SKU> belum diisi di master produk — lengkapi dulu."** sebelum ada efek apa pun (dulu diam-diam "meter", sehingga roll ber-yard bisa tercatat sebagai meter). |

Perbaikan ikutan: tugas QC tanpa PO kini me-rebuild saldo **pemilik sebenarnya** (dulu entitas bawaan); roll sisa
langkah ber-id deterministik (retry tidak menggandakan).

Berkas baru: `backend/services/{makloon_issue_rolls,makloon_receipt_qc,inbound_qc_common,gate_doc_movements}.py`,
`frontend/src/features/purchasing/makloon/MkoIssueRollPicker.jsx`, uji `backend/tests/test_makloon_celup_rolls.py`,
`frontend/src/features/__tests__/phase5MakloonRolls.test.js`. Diubah: `makloon_order_service`, `stock_bucket_service`,
`gate_evaluator`, `inbound_complete_service`, `qc_service`, `inspection_service`, router makloon/inspeksi/antrean QC,
`schemas_makloon`, katalog config (`purchasing.qc_on_receipt` kini menyebut makloon), `MkoStepModals`,
`MakloonOrderDetailPanel`, `InspectionDetailPanel`, `makloonApi`, `CODEBASE_MAP.md`.

## Perubahan perilaku yang perlu diketahui saat UAT
- **Hasil langkah terakhir SEMUA Order Makloon kini menunggu SPK QC** (selama `purchasing.qc_on_receipt` aktif —
  bawaan). Dulu langsung tersedia untuk dijual. Bila pemilik ingin makloon tanpa QC: matikan kunci itu per badan
  usaha (berlaku juga untuk PO) — atau minta kunci terpisah.
- Pop-up Issue makloon punya pilihan mode; mode lama tetap bawaan. Mode "Pilih roll" mengirim roll **utuh**.
- SPK hasil makloon mengikuti siklus SPK biasa (Draf → ditugaskan → mulai → periksa baris → tutup).
- Gate: roll ke/dari makloon & perbaikan tidak lagi merah "tanpa dokumen" bila dokumennya aktif.
- Jalur makloon menolak produk tanpa satuan dasar (lengkapi master produk).

## Bukti uji
- **Uji baru** `test_makloon_celup_rolls.py` di stack uji resmi (`kn-uji-backend`, DB `kn_test_trial`): **20/20 lulus**
  termasuk uji HTTP (`GET issue-rolls` + `POST issue` kode tak dikenal → 400 tanpa mutasi).
- **Uji HTTP manual alur klien** (stack resmi, akun demo Admin, Sukacita): MKO celup `KSC/MKO-00081`
  (CHIKITA KNIT BEIGE → AUDIA KNIT HITAM, PT Celup Warna Dayeuhkolot) — daftar issue-rolls memuat roll + EPC;
  issue dengan **2 nomor roll + 1 EPC huruf kecil** → `issue_mode=rolls`, qty = Σ roll (76,7 kg), roll `subcon` utuh;
  gate OUT WH-JKT **hijau `MOVEMENT_OUT`** "… langkah 1 → PT Celup Warna Dayeuhkolot" (baca ulang dalam jendela
  dwell = duplikat; `REPLAY_EXIT` teruji di uji layanan); terima → 3 roll **karantina** satuan **kg**, journey
  `stored`; antrean QC bernomor MKO + mitra; SPK `KSC/INS-00143` (Inspeksi Hasil Makloon) → tugaskan, mulai, 3 baris
  diperiksa, tutup "terima" → roll **available**, tugas QC `completed`, MKO `completed`. 15/15 langkah lulus.
  (Percobaan pertama dengan artikel CHIKITA KNIT sebagai hasil ditolak 409 "sumber restock belum diatur" — aturan
  lama yang benar; hasil diganti ke artikel AUDIA KNIT.)
- **Perbandingan A/B** (salinan DB uji yang sama, Mongo & backend sementara terisolasi; A = kode ini, B = HEAD
  `a8a3f6f`; 33 berkas uji makloon/gate/QC/penerimaan):
  * paralel (xdist): A 139 gagal / 203 lulus (+20 uji baru), B 134 / 189. 7 kegagalan hanya-A semuanya di modul
    yang **tidak disentuh** (sampel R&D uji ulang, nomor Pesanan Khusus duplikat saat paralel, pajak antar-PT) dan
    **hilang saat diulang serial**: 5 berkas itu A 12 gagal vs B 13 gagal, tidak ada yang hanya-A.
  * uji gate & QC serial di DB bernama `test_database` (nama yang dikunci `iter117/118`): **B 45/45**; A —
    `iter117_p09` + `iter118_p10` **26/26 lulus**. Catatan: bila berkas uji ber-`_shared_loop` (31 berkas, termasuk uji
    baru) jalan lebih dulu di proses yang sama, `iter117/118` gagal 17 ("attached to a different loop") — **sama di
    HEAD** (dibuktikan dengan `test_aud_exp_02.py` + `iter117/118` di B: 17 gagal). Kelemahan isolasi uji lama, bukan
    kode produk.
  * Merah lama yang identik di A & B (data acuan tidak lengkap / fixture lama): `fase_sl_scan_label`,
    `iter143_makloon_po_variance`, `iter258`, `iter266`, `iter276` (50 error, fixture data), `l00_*`, `l01_*`, `l04`,
    `p05_acceptance` dll.
- Di stack resmi `kn-uji-backend` 33 berkas yang sama memberi 147 gagal / 55 error — **tidak bisa dibandingkan**:
  banyak uji mengunci `mongodb://localhost:27017` / `test_database` atau membaca `backend/.env` (localhost,
  `test_database`), sedangkan kontainer memakai `mongo:27017` / `kn_test_trial`. Karena itu dipakai A/B di atas.
- **Jest** `--maxWorkers=1`: `phase5MakloonRolls` + `uatV3NavWarehouseMakloon` **14/14 lulus**. ESLint 6 berkas FE:
  **0 error** (1 peringatan lama `MakloonOrderDetailPanel.jsx:78`, sudah ada di HEAD).
- **Peramban** (`:3063`, Admin · Sukacita): pop-up Issue MKO `KSC/MKO-00082` mode "Pilih roll" — 93 roll + 4
  tertahan, EPC tampil, pindai `RL-04993 RL-05000 RL-TIDAKADA` + Enter → 2 roll tercentang, pesan "tidak ada di gudang
  sumber" untuk kode ketiga, total 50,85 kg + peringatan beda rencana, Enter tidak mengirim form; di 390 px pop-up
  layar penuh, `scrollWidth` = 390. Pop-up ditutup Batal (tidak di-issue). Detail `KSC/MKO-00081` menampilkan
  "QC hasil makloon sudah diputus."
- **Guardrail**: hijau — `custom_modals` 98, `error_notice` 265, `escape_layers` 1148, `uom_vocab` 1149,
  `approval_queues` 300, `home_kpi` 152, `codebase_map`, `modal_dismiss`, `detail_modal`, `picker_portal`,
  `blocking_dialogs`, `knselect_contract`, `rfid_tag_unique`, `roll_identity`, `doc_origin`, `cross_entity`,
  `aging_fields`, `po_board`, `status_history`, `view_aliases`, `role_label`, `page_tabs`, `list_export`, dll.
  Merah lama, hitungan sama dengan baseline fase 4: `atomic_claim` 6, `auth_coverage` 8 (endpoint baru ber-auth),
  `ref_unlink` 3, `to_list_bound` 6, `qty_dual` 5, `numeric_bounds` 3. `line_scope` 17 (baseline 15) — selisihnya
  dokumen retur `TEST_RET-…` sisa putaran uji, bukan makloon. `no_secrets` 10 = `backend/.env`/`frontend/.env` lokal
  (tidak di-commit) + XML laporan uji lama di `test_reports/` — bukan dari perubahan ini. `state_machine` &
  `concurrency` tidak dijalankan (mengubah data).

## Data uji yang ditinggalkan (DB uji `kn_test_trial`)
- `KSC/MKO-00081` (selesai, alur klien lengkap) + SPK `KSC/INS-00143` + perangkat gate `UJI-CELUP gate-out`
  (bukti). `KSC/MKO-00082` (Draf, langkah *Menunggu issue*) — sengaja dibiarkan agar uji HTTP
  `test_makloon_celup_rolls` tidak ter-skip ("tidak ada MKO dengan langkah pending").
- 10 perangkat gate `TEST_iter117_*/TEST_iter118_*` sisa dua putaran uji di stack resmi (pembersihan ujinya gagal
  karena alamat Mongo) **sudah dihapus**. Sisa `TEST_*` lain dari putaran itu (mis. retur `TEST_RET-U23-*`) belum
  dibersihkan.

## Belum dikerjakan / catatan
- Roll hasil makloon belum ada di sistem saat truk mitra lewat gate IN (roll lahir saat penerimaan dicatat) → gate IN
  membaca `UNKNOWN_EPC` bila tag mitra dipindai. Di luar lingkup.
- Retur bahan sebagian dari MKO **aktif** di gate IN mengikuti aturan umum lama (belum ada alurnya).
- Perbaikan **internal** ikut hijau di gate OUT (aturan: RPR *Dikirim* → hijau).
- Stack UAT (`kn-verify-*`, :3062/:8062) belum dinyalakan; uji di atas hanya di stack uji.
