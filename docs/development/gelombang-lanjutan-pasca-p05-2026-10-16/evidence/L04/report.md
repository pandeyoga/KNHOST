# Laporan Fase L04 — status `in_progress`

Belum ada SHA GitHub untuk sesi ini, jadi semua requirement maksimal `in_progress` dan acceptance tetap `not_run` (lihat DEFINITION_OF_DONE). Hasil uji lokal dicatat di `actual_result` pada BACKLOG.

## Ringkasan per requirement

| Req | Status | Isi |
|---|---|---|
| LN-040 | belum | Receiving aktual + OCR per roll. Alur GRN (read OCR → `expected_rolls` → koreksi → hitung → selisih → tutup) sudah ada; belum diverifikasi terhadap T01/T02. Untuk OCR sungguhan, kunci OpenAI perlu diisi lagi di Admin > Integrasi. |
| LN-041 | diverifikasi lokal | Tidak ada perubahan kode. Pemilihan roll MDQ dan keputusan manusia sudah ada sejak P05. |
| LN-042 | T01/T02 (sesi lalu) + **T03 (sesi ini)** | Reprint label: EPC sama, qty dari saldo ERP, histori cetak. |
| LN-043 | belum | Komitmen greige, issue, hasil fisik vs forecast, dan sisa bahan. |

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

## Blocker
- **DES-01:** aturan kg↔yard (LN-042-T02 cabang konversi produk).
- **KLX-01:** LOT supplier vs internal (LN-040).
- **Kunci OpenAI:** dibutuhkan untuk OCR sungguhan (LN-040-T01).
