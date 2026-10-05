# Audit KNHOST — Gelombang 2

## Pembaruan 2026-10-03 — jawaban kebutuhan klien

[Memo 12 poin](25_MEMO_JAWABAN_KEBUTUHAN_KLIEN.md) · [bug dan register kebutuhan](26_TAMBAHAN_KLIEN_DAN_W2_025.md) · [prompt enam fase](27_PROMPT_TINDAK_LANJUT_KEBUTUHAN_KLIEN.md) · [tracker kebutuhan](client-requirements-tracker.json).

**Total 242 checkpoint: 174 kontrol, 36 reproduksi cacat W2, 26 pendalaman Wave1, 6 observasi kebijakan; 25 ID W2.** W2-025 membuktikan pembatasan lini daftar R&D tidak berlaku pada detail/patch sample. Empat probe penjelasan roll/lot/lini tidak menambah hitungan. Sembilan W2-REQ memisahkan kebutuhan fitur/SOP dari bug. Sampling mengikuti lini untuk SKU hasil MD; bahan standar dapat dibuat langsung. Ini penelusuran snapshot, bukan validasi deployment/fix atau pernyataan seluruh flow sudah tercover. Subtotal di bawah merupakan histori.


## Pembaruan 2026-10-03 — recovery dan kapasitas produksi

[Laporan detail](23_AUDIT_RECOVERY_DAN_KAPASITAS_PRODUKSI.md) · [prompt fase perbaikan](24_PROMPT_RECOVERY_PRODUKSI.md) · [matriks](18_MATRIKS_FLOW_KRITIS.md).

**Total239 checkpoint:173 kontrol,34 reproduksi cacat W2,6 observasi kebijakan,26 pendalaman Wave1;24 ID W2.** Tambahan13. W2-024: WO menghasilkan5.001 setelah hanya mengonsumsi5.000 roll bahan. GN-06 diperdalam dengan kegagalan GL akibat periode tertutup asli, reopen/retry menghasilkan dua output, concurrent completion menghapus je_id, dan cancel meninggalkan stok output. Semua source/flow belum tercover; tidak ada validasi fix atau perubahan source aplikasi. Subtotal di bawah adalah histori.


## Pembaruan 2026-10-03 — produksi, payroll dan rekening

[Laporan dan lokasi kode](21_AUDIT_PRODUKSI_PAYROLL_BANK.md) · [prompt empat fase](22_PROMPT_PRODUKSI_PAYROLL_BANK.md) · [matriks](18_MATRIKS_FLOW_KRITIS.md).

**Total226 checkpoint:169 kontrol,32 reproduksi cacat W2,6 observasi kebijakan,19 pendalaman Wave1;23 ID W2.** Tambahan30 pada produksi, payroll dan bank. W2-022: payroll paid tanpa buku kas. W2-023: akun beban diterima sebagai payout. W2-021 diperluas ke limit5.000 transaksi bank. GN-06 terbukti fault/retry mengonsumsi bahan dua kali dan mengikuti BOM terbaru; FN-08 terbukti runtime opening rekening tanpa GL. Bukti lama tidak ditimpa, source aplikasi/Wave1 tracker tidak diubah. Belum seluruh flow tercover; bukan validasi fix. Payroll tanpa BPJS/PPh hanya fixture pencatatan, bukan validasi perpajakan. Angka berikutnya merupakan subtotal historis.


## Pembaruan 2026-10-03 — refund, multi-PO, uang muka dan laporan besar

[Laporan detail dan lokasi kode](19_AUDIT_REFUND_ADVANCE_MULTI_PO_GL.md) · [prompt empat fase](20_PROMPT_REFUND_LAPORAN_DAN_PENDALAMAN.md) · [matriks cakupan](18_MATRIKS_FLOW_KRITIS.md).

**Total196 checkpoint:149 kontrol,28 reproduksi cacat W2,6 observasi kebijakan,13 pendalaman Wave1;21 ID W2.** Tambahan41 checkpoint pada lima harness; replay fixture sales tidak dihitung ulang. W2-020: refund final walau buku kas gagal, retry tidak memperbaiki. W2-021: neraca saldo/buku besar terpotong pada50.000 jurnal dan laba rugi pada100.000. CX-04/CX-05/FN-09 diperdalam tanpa tiket duplikat. Multi-PO dan close/reopen dataset kecil menambah kontrol positif.

Belum semua kode/flow tercover. Bukti ini bukan validasi fix: snapshot tetap sama. POS cashier/tender, seluruh posting subledger, multi-entitas, modul pendukung, browser dan hardware masih mempunyai batas yang dicatat dalam matriks. Angka pada bagian lama merupakan subtotal historis.


## Pembaruan 2026-10-03 — audit lintas flow

[Laporan dan lokasi kode](16_AUDIT_LINTAS_FLOW_QC_SALES_STOK_AR.md) · [prompt enam fase](17_PROMPT_LINTAS_FLOW.md) · [matriks96 kasus luas dan sisa kritis](18_MATRIKS_FLOW_KRITIS.md).

**Total klasifikasi terbaru155 checkpoint:117 kontrol,23 reproduksi cacat W2,6 observasi kebijakan,9 pendalaman Wave1;19 ID W2.** Tambahan56 terdiri dari41 checkpoint baru pada QC/sales/projection dan15 AR yang dahulu tertunda, kini direview dan direplay. Replay tidak dihitung dua kali. Status pending AR pada bagian lama sudah digantikan review ini.

Enam temuan baru: unit/nilai retur QC salah (W2-014), pure deposit tanpa reklasifikasi GL (015), void sumber deposit parsial (016), pemakaian deposit bersamaan meninggalkan payment tanpa dana (017), void menghapus payment baru (018), split QC menggandakan berat (019). GN-13 kini terbukti runtime lewat hold/rebuild, tanpa ID duplikat.19 kontrol sales menelusuri order hingga delivery, retur store credit dan reversal.

Semua source/flow kritis **belum** tercover.155 bukan155 business flow independen atau persentase coverage. Sisa dan batas kini dipetakan pada satu matriks, termasuk full Finance close, POS/refund tunai, multi-PO/gudang, concurrency/recovery menyeluruh, modul pendukung, browser dan hardware. Source aplikasi/trackers Wave1 tidak diubah. Angka di bawah adalah subtotal historis.

## Pembaruan 2026-10-02 — GRN parsial, kapasitas dan recovery

[Hasil detail](14_UJI_GRN_PARSIAL_KAPASITAS_RECOVERY.md) · [prompt perbaikan](15_PROMPT_GRN_KAPASITAS_RECOVERY.md).

20 checkpoint tambahan:15 kontrol, dua reproduksi cacat W2-013, tiga pendalaman GN-11. W2-013:501roll dihitung tetapi hanya500 difinalkan, GRN tetap closed. Pendalaman GN-11: setelah kegagalan roll kedua dan pelepasan lock, retry menghasilkan stok10 tetapi PO/QC6 dan task sisa4 palsu. Tidak menggandakan ID GN-11 atau mengubah tracker Gelombang1.

**Total klasifikasi terbaru:99 checkpoint skenario (69 kontrol,16 reproduksi cacat W2,6 observasi kebijakan,8 pendalaman Gelombang1),13 ID W2.** Ini bukan99 flow independen atau persentase coverage kode.15 skenario AR belum ditriase dan tetap tidak dihitung. Angka di bagian terdahulu adalah subtotal historis. GRN-04 bertambah bukti, tetap parsial; browser/hardware dan keseluruhan aplikasi belum tercover.

Gelombang 2 mencari cacat pada flow yang belum tercover dalam Gelombang 1. Tidak mengubah tracker, status, maupun prompt Gelombang 1. Pengguna menyatakan belum ada perbaikan kode Gelombang 1; pekerjaan ini bukan validasi perbaikannya.

## Uji terbaru — WMS konversi satuan

[16 kontrol fungsional WMS](13_UJI_WMS_UOM.md) semuanya sesuai ekspektasi, memakai service asli dan Mongo sintetis. [Hasil](wms-uom-results.json). Tidak ada error Daybreak dari alat yang terlihat; ini bukan bukti Finance menyebabkan pesan tersebut. Total yang sudah diklasifikasikan kini **79 skenario:54 kontrol,14 reproduksi cacat W2,6 observasi kebijakan,5 pendalaman Gelombang1;12 ID tracker**. Angka pada review terdahulu adalah subtotal historis. Bukti AR yang selesai sebelum pengalihan domain tersimpan di `ar-results.json`, belum ditriase/lapor final dan tidak masuk total79.

## Review terbaru — koreksi W2-05

[Validasi ulang putaran terakhir](12_VALIDASI_ULANG_W2_05.md) mengonfirmasi tiga temuan dengan koreksi penting: W2-010 (P1) dipersempit ke histori reads karena incidents dan device infra memang SHARED; W2-011 tetap valid, prioritas P2; W2-012 valid dan terbukti lewat HTTP serta konkurensi tanpa barrier. Enam observasi akses pada laporan awal tidak lagi dihitung sebagai pelanggaran terkonfirmasi. 24 skenario awal direplay dengan hasil sama, ditambah10 probe review; pengulangan tidak menambah coverage.

[Laporan RFID yang dikoreksi](10_TEMUAN_RFID_GATE_DAN_INSIDEN.md) · [prompt revisi](11_PROMPT_RFID_GATE_DAN_INSIDEN.md) · [bukti review](validation/W2-05-review/results.json) · [klasifikasi terbaru](validation/W2-05-review/classification.json). JSON runtime awal tetap disimpan sebagai histori; interpretasi terbaru mengungguli label defect lama.

**Total terkini: 63 skenario unik; 38 kontrol; 14 reproduksi cacat W2; enam observasi kebijakan; lima pendalaman Gelombang 1; 12 ID tracker W2.** Angka subtotal lama bersifat historis. Ini review keabsahan temuan, bukan verifikasi fix. Source aplikasi tidak berubah; UI browser, middleware dan hardware belum diuji; seluruh kode/flow belum tercover.

## Pembaruan terbaru W2-04

[Transfer gudang dan reservasi roll](08_TEMUAN_TRANSFER_STOK.md) menambahkan W2-008 (roll manual milik B dapat dipakai dokumen A) serta W2-009 (saldo tersedia tidak diperbarui saat roll manual direservasi). Perilaku auto-owner transfer W2-T-F03 dicatat sebagai pendalaman W2-006. [Prompt develop](09_PROMPT_TRANSFER_STOK.md) · [hasil runtime](transfer-results.json).

**Total terkini: 39 skenario unik, 28 kontrol sesuai ekspektasi, 11 reproduksi cacat, sembilan ID temuan.** Angka subtotal dalam bagian putaran sebelumnya adalah histori. INV-02, INV-03, PROD-05 dan APAR-01 masih parsial; seluruh kode/flow belum tercover.

## Pembaruan terbaru W2-03

[Stock opname: ownership dan keputusan](06_TEMUAN_CYCLE_COUNT.md) menambahkan W2-006 (pemilihan owner otomatis di luar scope) dan W2-007 (reject terlambat menimpa approved setelah stok berubah). [Prompt perbaikan](07_PROMPT_CYCLE_COUNT.md) · [Hasil runtime](count-results.json).

**Total terkini: 30 skenario unik, 22 kontrol sesuai ekspektasi, delapan reproduksi cacat, tujuh ID temuan.** Angka pada bagian putaran sebelumnya adalah subtotal historis. INV-03, PROD-05 dan APAR-01 tetap parsial; seluruh kode/flow belum tercover.

## Pembaruan putaran W2-02

[Klaim dan pembayaran AP](04_TEMUAN_KLAIM_DAN_PEMBAYARAN.md) menambahkan W2-004 (cancel bill makloon tidak membalik utang GL) dan W2-005 (race klaim versus payment meloloskan overpayment). [Prompt develop](05_PROMPT_KLAIM_DAN_PEMBAYARAN.md) dan [hasil runtime](claim-payment-results.json) terpisah dari putaran pertama.

Total kini **20 skenario unik: 14 kontrol sesuai ekspektasi dan enam reproduksi cacat untuk lima ID temuan**. Pengulangan run tidak dihitung lagi. Seluruh flow belum tercover. PROD-05 dan APAR-01 masih parsial.

## Putaran W2-01: makloon → stok → biaya → lokasi

Snapshot diuji: `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Sembilan skenario runtime selesai: enam kontrol sesuai ekspektasi dan tiga reproduksi cacat. Dua cacat dibuktikan melalui ASGI HTTP; satu melalui helper posting GRN dengan Mongo nyata. Ini bukan pengujian UI browser atau perangkat fisik, bukan seluruh flow makloon dan bukan seluruh aplikasi.

- [Temuan detail dan akar masalah](01_TEMUAN_MAKLOON.md)
- [Prompt perbaikan terpisah Gelombang 2](02_PROMPT_PERBAIKAN.md)
- [Cakupan dan pekerjaan berikutnya](03_CAKUPAN.md)
- [Tracker Gelombang 2](tracker.json)
- [Hasil runtime](makloon-results.json)
- [Cara reproduksi](repro/README.md)

ID tetap: W2-001 hingga W2-003. Status awal `open`; hasil pengujian yang mereproduksi cacat tidak berarti sudah diperbaiki. Agent develop boleh mengisi commit dan bukti lalu `ready_for_validation`; validator baru menetapkan `verified_fixed` setelah menguji ulang commit kandidat. Bukti historis jangan ditimpa saat validasi perbaikan: simpan hasil baru dalam direktori iterasi terpisah.

Gelombang 1 CX-13 membahas stale snapshot/concurrency pada makloon receive. Tiga temuan ini membahas kontrak jumlah/nilai serta lokasi, bukan menghitung ulang CX-13. Perbaikan mungkin menyentuh fungsi yang sama: koordinasikan dengan fase P11/P02/P04 Gelombang 1 dan jangan menimpa perubahan agent lain. Tidak ada source aplikasi yang diperbaiki dalam putaran ini.

Main memiliki SHA berbeda dari baseline audit lama. Diff spesifik `makloon_order_service.py`, `makloon_orders.py`, dan `stock_bucket_service.py` terhadap baseline lama kosong; temuan tidak dinyatakan sebagai regresi akibat pekerjaan perbaikan Anda. SHA baru tetap dicatat supaya bukti dapat direproduksi.
