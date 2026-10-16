# Laporan Fase L04 — status `in_progress`

Belum ada SHA GitHub untuk sesi ini, jadi semua requirement maksimal `in_progress` dan acceptance tetap `not_run` (lihat DEFINITION_OF_DONE). Hasil uji lokal dicatat di `actual_result` pada BACKLOG.

## Ringkasan per requirement

| Req | Status | Isi |
|---|---|---|
| LN-040 | diverifikasi lokal (OCR nyata) + celah idempotensi ditutup | Alur GRN OCR → draf per roll → koreksi → hitung → tutup. |
| LN-041 | diverifikasi lokal | Tidak ada perubahan kode. Pemilihan roll MDQ dan keputusan manusia sudah ada sejak P05. |
| LN-042 | T01/T02 (sesi lalu) + **T03 (sesi ini)** | Reprint label: EPC sama, qty dari saldo ERP, histori cetak. |
| LN-043 | buku bahan baru + bug issue parsial diperbaiki | T01–T03 lulus lokal; pembatas retur per roll utuh dicatat. |

## LN-041 — verifikasi (tanpa perubahan kode)
- **Navigasi:** `?view=inspections` → SPK penerimaan PO → baris roll → isi warna/handfeel (bagian MD Quality) → potong MDQ (opsional) → lepas atau tolak tahanan dengan alasan.
- **T01:** Satu SPK berisi 3 roll dari 3 LOT. MDQ menguji 2 roll dari LOT berbeda.
  - Hanya 2 roll itu yang punya hasil uji dan mutasi `mdq_cut`.
  - Roll ke-3 utuh.
  - `length_initial` (qty bruto receiving) ketiga roll tidak berubah.
- **T02:** Hasil warna `beda_shade` membuat baris ditahan (kebijakan bawaan `tahan`). MDQ lalu melepas tahanan dengan alasan.
  - `color_result` tetap `beda_shade`.
  - Keputusan tercatat terpisah di `md_quality_decision` (action, oleh, peran, waktu) dan di audit `inspection_hold_released`.
  - Role tanpa izin ditolak.
- **Tes:** `backend/tests/test_l04_ln041_mdq_select.py` 2/2.

## LN-042-T03 — reprint label

**Sebelum:**
- Antrean printer (`create_print_job`) sudah memakai ulang tag hidup (EPC sama) dan qty dari `length_remaining`.
- Tidak ada histori cetak per roll.
- Cetak ulang dari browser tidak tercatat.
- Lookup RFID tidak memberi tahu bahwa teks label sudah basi.

**Sesudah:**
- **Koleksi baru** `roll_label_prints` (append-only; scope `owner_entity_id`). Isinya per cetak: `{roll_id, roll_no, epc, qty, unit, kind, channel (print_queue|browser), print_seq, reprint, job_id, by, at}`.
  - Untuk jalur antrean, tidak ada duplikat per (job, roll).
- **`on_printed` (antrean printer / perangkat):** mencatat histori untuk setiap item job. Item job baru membawa flag `reprint`.
- **Endpoint baru:**
  - `POST /api/rfid/rolls/{roll_id}/label-prints` (izin `wms.scan`): mencatat cetak browser; qty diambil dari saldo ERP saat cetak.
  - `GET /api/rfid/rolls/{roll_id}/print-history` (izin `wms.view`): mengembalikan histori, qty terkini, `last_printed_qty`, `label_outdated`.
- **`GET /api/rfid/lookup`:** kini menyertakan `label {prints_count, last_printed_qty, label_outdated, current_qty, epc}`. Saldo tetap dibaca dari ERP; RFID hanya identitas.
- **FE:**
  - RFID Tags → "cetak ulang label" sekarang mencatat histori. Pesannya menampilkan "cetak ke-N · qty terkini · EPC tetap", dan lookup memakai `record=false` supaya cetak tidak dicatat sebagai pindai.
  - `RollLabelActions` (popup browser) ikut mencatat histori.
- **Efek lintas modul:** tidak ada roll, tag, atau mutasi stok baru. Hanya data histori.

**Bukti:** `backend/tests/smoke_comm04_ln042t03.py` ALL PASS; `backend/tests/test_comm04_ln042t03_regression.py` (testing agent iteration_189).

## Di luar L04 — COMM-04 (prioritas handoff P22/P23, keputusan PG04)
- **Akun baru** CoA `6-4700 Beban Pemasaran & Promosi`, lewat seed CoA dan konstanta `ACC_BEBAN_PEMASARAN`. Akun beban lain boleh dipilih lewat `expense_account_code`.
- **Koleksi** `mkt_campaign_costs` (SCOPED, nomor `MCC-`).
- **Catat biaya:** `POST /api/marketing/campaigns/{cid}/costs` (izin `accounting.create`).
  - Membuat kas keluar (`ref_type mkt_campaign_cost`) dengan jurnal Dr Beban Pemasaran / Cr Kas Besar atau Kas Kecil.
  - Bila jurnal gagal, ada kompensasi: kas dibatalkan dan biaya dihapus.
  - Header `Idempotency-Key` didukung.
- **Batalkan biaya:** `POST .../costs/{id}/void` (izin `accounting.void`, alasan ≥5).
  - Memakai klaim atomik (`atomic_claim`, terdaftar di Kunci Saga).
  - Jurnal pembalik dibuat di periode berjalan, tepat sekali; kas ikut dibatalkan.
  - Kas yang sudah direkonsiliasi bank ditolak.
- **Anggaran vs realisasi:** `GET .../costs` (budget, realized, remaining, over_budget). Daftar kampanye menampilkan `cost_realized` dan `budget_remaining`. Anggaran tidak dijurnal.
- **FE:** tombol "Biaya" di kartu kampanye (`?view=mkt-campaigns`) membuka `CampaignCostsModal`.

## LN-040 — receiving aktual + OCR per roll (sesi 2)

**Sebelum:**
- Alur GRN sudah ada: OCR SJ + packing list → `expected_rolls` (dengan `doc_status`) → koreksi review → hitung fisik → selisih → tutup.
- Tetapi `POST /goods-receipts/{id}/lines/{n}/rolls` tanpa `expected_seq` yang dikirim ulang (HP putus sinyal) bisa membuat roll dobel.

**Sesudah:**
- `/api/goods-receipts/` ditambahkan ke `IDEMPOTENT_PREFIXES`.
- FE `GrnCountPanel` memakai `useIntentKey`: satu niat = satu kunci. Kirim ulang isi yang sama memakai kunci yang sama. Kunci diganti setelah sukses atau setelah server menjawab 4xx.

**Bukti:** `backend/tests/test_l04_ln040_real_ocr.py`, dengan OCR NYATA (OpenAI). Kunci disimpan di `backend/.env` `OPENAI_API_KEY`, tidak di repo.
- Gambar SJ sintetis: 10 roll; roll #7 sengaja dicoret.
- OCR membaca 9 roll dengan benar, menandai #7 `missing`, dan memberi peringatan "1 roll ragu".

## LN-043 — buku bahan makloon (sesi 2)

**Sebelum:**
- Cadangan (`material_reservations`), issue, batal (bahan tetap di mitra), retur per roll, dan susut per roll sudah ada.
- Tetapi tidak ada satu tampilan yang menjelaskan forecast / cadangan / dikirim / di mitra / terpakai / kembali / susut.
- Bug: cek "dicadangkan order lain" memakai qty rencana, bukan qty dokumen yang benar-benar dikirim. Akibatnya issue parsial ditolak 409 walau bahan cukup.

**Sesudah:**
- **Service baru (hanya-baca)** `services/makloon_material_ledger.py`. Endpoint: `GET /api/makloon-orders/{id}/material-ledger` (izin `makloon_order.view`, dibatasi entitas).
  - Rekonsiliasi per langkah: dikirim = di mitra + kembali + susut + terpakai.
- **Panel FE** `MakloonMaterialLedger` di detail MKO (`mko-material-ledger`): menampilkan angka per kategori, status Seimbang, stok sekarang, penjelasan, dan hasil aktual vs estimasi.
- **Perbaikan** `issue_step`: cek stok sumber dan cadangan pihak lain dipindah ke SESUDAH konversi dokumen.

**Bukti:** `backend/tests/test_l04_ln043_material_ledger.py` 3/3; regresi `test_p05_acceptance_acc31_33_34.py` dan `test_l00_p05_open_issues.py` 22/22.

**Pembatas retur sebagian roll — diselesaikan di sesi 3:**
- `return-material` kini menerima `partial: [{roll_id, qty}]`.
  - Roll dipecah lewat `stock_bucket_service.split_off_from_ref`. Roll anak mendapat nomor sendiri (`split_from_roll_id`), lalu kembali ke gudang. Induk tetap di mitra dengan panjang berkurang.
  - WIP dibalik pro-rata.
  - Validasi: roll yang sama tidak boleh muncul dua kali (400); qty 0 atau melebihi sisa ditolak (400).
- UI `mko-return-partial-<roll>` menampilkan validasi bila angka tidak sah.
- Susut tetap per roll utuh.
- Bukti: `tests/test_session3_partial_return_notif_budget.py`, `tests/test_session3_extended_t1.py`; testing agent iteration_192–193.
- Batasan mobile P05 belum direproduksi pada sesi ini.

## COMM-04 lanjutan — tagihan vendor kampanye tanpa PO (keputusan owner 2026-10-16)

**Alur:** Marketing/Admin mengajukan (`POST /api/marketing/campaigns/{cid}/vendor-bills`; izin `marketing.update`).
- Dokumen tersimpan di `vendor_bills` dengan `bill_type=campaign_expense`, status `pending_approval`, dan belum dijurnal.
- **Persetujuan:** Finance/Manager/Admin menyetujui (`.../approve`). Pembuat tidak boleh menyetujui tagihannya sendiri, kecuali kebijakan admin override.
  - Jalur generik `/vendor-bills/{id}/approve|reject` juga diarahkan ke aturan yang sama.
  - Saat disetujui → `post_vendor_bill` membuat jurnal Dr 6-4700 (+ Dr 1-1500 PPN Masukan) / Cr 2-1100 Hutang Usaha.
- **Pembayaran:** lewat `/vendor-bills/{id}/pay` yang sudah ada (Dr Hutang / Cr Kas). Masuk umur hutang.
- **Tolak:** wajib alasan ≥5 karakter, tanpa jurnal.
- **Realisasi anggaran:** = biaya kas langsung + tagihan yang sudah disetujui (tanpa PPN). Tagihan yang menunggu persetujuan ditampilkan terpisah.
- **Validasi:** vendor dari daftar `GET /api/marketing/vendor-options` (tanpa badan usaha grup; dibatasi entitas); invoice dobel ditolak.

**Bukti:** `backend/tests/test_comm04_campaign_bills.py` 3/3 dan `test_comm04_campaign_bills_edge.py` 4/4.

## Blocker
- **DES-01:** aturan kg↔yard (LN-042-T02 cabang konversi produk).
- **KLX-01:** LOT supplier vs internal (LN-040).
- **Kunci OpenAI:** dibutuhkan untuk OCR sungguhan (LN-040-T01).

## Sesi 4 — penutupan L04 (2026-10-16)
- **DES-01 → resolved:** owner menyetujui urutan SOP: receiving bruto → tag/identitas → potong MDQ tercatat → saldo bersih & reprint (EPC sama).
  - Untuk roll kg, potongan wajib memakai berat aktual; tanpa itu transaksi diblok (LN-042-T02, `test_kg_requires_actual_data`).
- **Susut sebagian roll (keputusan owner):** `material-loss` menerima `partial: [{roll_id, qty}]`.
  - Roll dipecah DI MITRA (`split_off_from_ref(keep_in_bucket=True)`): roll anak tetap berstatus subcon, lalu roll anak itulah yang dicatat susut, mengikuti aturan toleransi dan persetujuan yang sudah ada.
  - Semua masukan divalidasi dulu sebelum ada roll yang dipecah. UI memakai kolom qty yang sama dengan retur.
  - Bukti: `test_session3_partial_return_notif_budget.py::test_partial_loss_splits_child_at_partner`.
- **Mobile P05 (MKO dari HP):** diverifikasi di 390px. Lihat iteration_194.
