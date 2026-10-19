# Tracker gelombang lanjutan pasca-P05

Dihasilkan dari BACKLOG.json. Ubah status pada BACKLOG, lalu render ulang; jangan mengedit angka manual.

Baseline: `64d81f29577dae4daa86ddc64689dec7243804f2`. Kandidat final: `belum ditetapkan`.

Requirement tervalidasi: **0/56**. Acceptance PASS: **0/230**. Keputusan pending: **23/24**.

Angka di atas adalah kemajuan implementasi/verifikasi gelombang ini. Pemetaan seluruh sumber tidak berarti code coverage 100 persen. Status awal not_started adalah sengaja, karena paket belum mengimplementasikan perubahan.

| Fase | Status | Requirement tervalidasi | Acceptance PASS | Pending terkait | Prompt |
|---|---|---|---|---|---|
| L00 Baseline, penyelarasan keputusan, dan kontrak perubahan | in_progress | 0/3 | 0/6 | — | [Buka](phases/L00.md) |
| L01 Custom role, master data, grade, dan konfigurasi visibilitas | in_progress | 0/6 | 0/23 | DATA-01, DES-04, KLX-01 | [Buka](phases/L01.md) |
| L02 Penjualan, alokasi roll, harga khusus dan konsistensi Finance | not_started | 0/5 | 0/15 | KLX-03 | [Buka](phases/L02.md) |
| L03 Special Order, Designer, uji kain dan rute supplier/makloon | in_progress | 0/5 | 0/27 | — | [Buka](phases/L03.md) |
| L04 Receiving, RFID identity, MD Quality, UOM dan material makloon | in_progress | 0/4 | 0/10 | KLX-01 | [Buka](phases/L04.md) |
| L05 Meja QC dan form inspect tiga sumber | not_started | 0/3 | 0/9 | KLX-02 | [Buka](phases/L05.md) |
| L06 Sampel, Admin Cutting dan penjualan ecer | not_started | 0/3 | 0/9 | — | [Buka](phases/L06.md) |
| L07 Picking, transit, multi-SO dispatch dan perjalanan antar lokasi | not_started | 0/3 | 0/7 | DES-02 | [Buka](phases/L07.md) |
| L08 Menu Retur terpadu, penerimaan, QC dan lineage roll | in_progress | 0/4 | 0/13 | KLR-08, KLR-09 | [Buka](phases/L08.md) |
| L09 Tukar, kompensasi, retur interco dan supplier end-to-end | in_progress | 0/4 | 0/13 | KLR-01, KLR-02, KLR-03, KLR-04, KLR-05, KLR-06, KLR-07, KLR-09, KLR-10, KLR-11 | [Buka](phases/L09.md) |
| L10 Putaway, stock opname, dashboard dan Meja User | not_started | 0/3 | 0/9 | OPS-01 | [Buka](phases/L10.md) |
| L11 Pusat export, join bisnis dan rapor staf | in_progress | 0/4 | 0/12 | DES-03 | [Buka](phases/L11.md) |
| L12 Kesiapan ERP untuk middleware Chainway dan UAT tiga perangkat | not_started | 0/3 | 0/56 | HW-01 | [Buka](phases/L12.md) |
| L13 Absensi langsung perangkat ke ERP | not_started | 0/2 | 0/6 | HR-01, HW-02 | [Buka](phases/L13.md) |
| L14 Integrasi, migrasi, UAT dan penutupan gelombang | not_started | 0/4 | 0/15 | UAT-01 | [Buka](phases/L14.md) |

## Requirement

| ID | Fase | Kebutuhan | Status | Bukti |
|---|---|---|---|---|
| LN-001 | L00 | Baseline aktual dan rekonsiliasi fase lama | in_progress | evidence/L00/report.md, evidence/L00/baseline_snapshot.json, evidence/L00/owner_decisions_2026-10-16.md |
| LN-002 | L00 | Kontrak perubahan dan keputusan belum final | in_progress | evidence/L00/report.md, evidence/L00/baseline_snapshot.json, evidence/L00/owner_decisions_2026-10-16.md |
| LN-003 | L00 | Fixture, risiko migrasi, dan rencana bukti | in_progress | evidence/L00/report.md, evidence/L00/baseline_snapshot.json, evidence/L00/owner_decisions_2026-10-16.md |
| LN-010 | L01 | Editor hak akses empat tingkat dan enforcement | in_progress | evidence/L01/report.md, evidence/L01/field_leak_scan_sales_before.json, evidence/L01/field_leak_scan_sales_after.json |
| LN-011 | L01 | Stage, jenis kain, supplier/color dan master lifecycle | in_progress | evidence/L01/report.md |
| LN-012 | L01 | Grade dinamis, rank customer dan konfigurasi POS | in_progress | evidence/L01/report.md, evidence/L01/field_leak_scan_sales_before.json, evidence/L01/field_leak_scan_sales_after.json |
| LN-013 | L01 | Default restock dan konteks entitas MD | in_progress | evidence/L01/report.md, evidence/L01/field_leak_scan_sales_before.json, evidence/L01/field_leak_scan_sales_after.json |
| LN-014 | L01 | LOT supplier dan identitas LOT internal | in_progress | evidence/L14/report.md (T3/T4), backend/tests/test_ln014_lot_identity.py, tests/test_ln140_chain_fixes.py |
| LN-020 | L02 | ATP, Keep/Pending dan satuan pada SO | in_progress | evidence/L02/report.md |
| LN-021 | L02 | Roll picker dan perubahan alokasi yang sah | in_progress | evidence/L02/report.md |
| LN-022 | L02 | Harga grade dan pengajuan ulang Special Price | in_progress | evidence/L02/report.md |
| LN-023 | L02 | AR, AP, revisi PO dan dampak finansial | in_progress | evidence/L02/report.md |
| LN-024 | L02 | Utang/piutang interco dan pembayaran per transaksi | in_progress | evidence/L02/report-ln024.md |
| LN-030 | L03 | Sumber desain, multi-produk dan status HOLD | implemented_pending_validation | evidence/L03/report.md, evidence/L03/owner_decisions_2026-10-18.md |
| LN-031 | L03 | Round designer dan persetujuan yang sudah ada | implemented_pending_validation | evidence/L03/report.md |
| LN-032 | L03 | Uji kain sesuai lini dan proofing printing berulang | implemented_pending_validation | evidence/L03/report.md |
| LN-040 | L04 | Receiving aktual dan OCR per roll | in_progress | evidence/L04/report.md |
| LN-041 | L04 | MD Quality memilih roll dan mencatat dua indikator | in_progress | evidence/L04/report.md |
| LN-042 | L04 | Pemotongan 0,25 yard, identitas tag dan konversi kg | in_progress | evidence/L04/report.md |
| LN-043 | L04 | Komitmen greige, issue, hasil fisik dan sisa bahan makloon | in_progress | evidence/L04/report.md |
| LN-050 | L05 | Permintaan QC dan sumber antrean | in_progress | evidence/L05/report.md |
| LN-051 | L05 | Form inspect sesuai kertas tanpa ambigu satuan | in_progress | evidence/L05/report.md |
| LN-052 | L05 | Kamus cacat, perhitungan skor dan grade tervalidasi | in_progress | evidence/L05/report.md |
| LN-060 | L06 | Tiga jenis sampel dan catalogue terurai | in_progress | evidence/L06/report.md |
| LN-061 | L06 | Cutting lintas lokasi/entitas dan Admin Cutting | in_progress | evidence/L06/report.md |
| LN-062 | L06 | Ecer berbayar, sisa roll dan mutasi potong | in_progress | evidence/L06/report.md |
| LN-070 | L07 | Picking multi-gudang dan validasi konsolidasi | in_progress | evidence/L07/report.md |
| LN-071 | L07 | Dokumen per leg dan multi-SO manifest | in_progress | evidence/L07/report.md |
| LN-072 | L07 | Transit Jakarta, receipt aktual dan posting yang tepat | in_progress | evidence/L07/report.md |
| LN-080 | L08 | Form retur dan menu yang jelas | in_progress | evidence/L08/report.md |
| LN-081 | L08 | Pisahkan perjalanan fisik, QC, keputusan dan saldo | in_progress | evidence/L08/report.md |
| LN-082 | L08 | Identitas unik, potongan dan larangan kembali ke customer asal | in_progress | evidence/L08/report.md |
| LN-083 | L08 | Batas waktu, eligibility dan bukti keputusan | in_progress | evidence/L08/report-ln083.md |
| LN-090 | L09 | Tukar barang sampai customer | in_progress | evidence/L09/report.md |
| LN-091 | L09 | Refund/saldo, potong tagihan dan nilai histori | in_progress | evidence/L09/report-ln091-092.md |
| LN-092 | L09 | Cutloss dan discount hanya setelah kebijakan final | in_progress | evidence/L09/report-ln091-092.md |
| LN-093 | L09 | Sukacita → CST → supplier dengan provenance benar | in_progress | evidence/L09/report.md |
| LN-100 | L10 | Alamat fisik dan putaway yang dapat dipakai | in_progress | evidence/L10/report.md |
| LN-101 | L10 | Stock opname fisik, identitas, qty dan rekonsiliasi | in_progress | evidence/L10/report.md |
| LN-102 | L10 | Dashboard stok dan antrean Meja User yang konsisten | in_progress | evidence/L10/report.md |
| LN-110 | L11 | Registry seluruh data bisnis dan builder export | in_progress | evidence/L11/report.md |
| LN-111 | L11 | Join relevan, grain dan Finance analytics | in_progress | evidence/L11/report.md |
| LN-112 | L11 | Rapor Designer dan Sales lengkap | in_progress | evidence/L11/report.md |
| LN-113 | L11 | Keamanan field dan konsistensi pekerjaan export | in_progress | evidence/L11/report.md |
| LN-120 | L12 | Parity kontrak dan pemisahan modul | not_started | belum ada |
| LN-121 | L12 | UR300/C72: durability, context dan keputusan bisnis | not_started | belum ada |
| LN-122 | L12 | CP30EN print/encode/verify dan reprint yang aman | not_started | belum ada |
| LN-130 | L13 | Kontrak direct attendance dan raw log | not_started | belum ada |
| LN-131 | L13 | Attendance turunan, koreksi dan aturan HR | not_started | belum ada |
| LN-140 | L14 | Rantai bisnis dan Finance pada satu kandidat rilis | in_progress | evidence/L14/report.md, backend/test_core_rantai_retur_poc.py (46/46) |
| LN-141 | L14 | Migrasi dan batas cakupan yang terukur | not_started | belum ada |
| LN-142 | L14 | UAT dan definisi selesai | not_started | belum ada |
| LN-033 | L03 | Rute pemenuhan supplier/makloon dari R&D dan Pesanan Khusus | in_progress | evidence/L03/report.md |
| LN-143 | L14 | Validasi produksi Pesanan Khusus hingga penerimaan, Finance dan pengiriman | not_started | belum ada |
| LN-015 | L01 | Detail UI/UX dan otorisasi custom role lintas modul | in_progress | evidence/L01/report.md, evidence/L01/field_leak_scan_sales_before.json, evidence/L01/field_leak_scan_sales_after.json |
| LN-034 | L03 | Revalidasi produk per supplier, kontrak terpisah dan keputusan PIC | in_progress | evidence/L03/report.md |
