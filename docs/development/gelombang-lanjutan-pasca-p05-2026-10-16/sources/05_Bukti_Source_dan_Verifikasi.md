# Bukti Source dan Batas Pemeriksaan

**Main:** `64d81f29577dae4daa86ddc64689dec7243804f2` · pemeriksaan 16 Oktober 2026.

Tautan memakai commit tetap agar nomor baris tidak bergeser mengikuti main. Snapshot lokal tidak diubah.

| ID | Pokok bukti | Source |
|---|---|---|
| E01 | ACC desain memicu proofing terkait Special Order | [E01: backend/services/special_order_phase2.py:504](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/special_order_phase2.py#L504) |
| E02 | Keputusan pelanggan dan pembuatan ulang sample | [E02: backend/services/special_order_phase2.py:81](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/special_order_phase2.py#L81) |
| E03 | Hold/release desain | [E03: backend/services/design_studio_service.py:469](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/design_studio_service.py#L469) |
| E04 | Field intake Special Order sekarang | [E04: frontend/src/features/sales/CreateSpecialOrderForm.jsx:31](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/frontend/src/features/sales/CreateSpecialOrderForm.jsx#L31) |
| E05 | Harga Special Order sekarang dari biaya sample dan margin | [E05: backend/services/special_order_phase2.py:190](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/special_order_phase2.py#L190) |
| E06 | Pengajuan harga khusus per SO dan batas statusnya | [E06: backend/routers/so_approvals.py:89](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/routers/so_approvals.py#L89) |
| E07 | Override harga mengajukan amandemen harga | [E07: backend/services/so_override_service.py:316](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/so_override_service.py#L316) |
| E08 | Identitas dan saldo roll dibentuk saat receiving | [E08: backend/services/receiving_roll_service.py:68](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/receiving_roll_service.py#L68) |
| E09 | Penerimaan masuk antrean inspeksi bila qc_pending | [E09: backend/services/inbound_complete_service.py:569](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inbound_complete_service.py#L569) |
| E10 | Payload EPC dipisahkan dari qty teks cetak | [E10: backend/services/rfid_print_service.py:47](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rfid_print_service.py#L47) |
| E11 | Pembacaan EPC mencari roll di database | [E11: backend/services/rfid_ingest_service.py:179](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rfid_ingest_service.py#L179) |
| E12 | Tahap perjalanan tag dan putaway | [E12: backend/services/rfid_print_service.py:21](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rfid_print_service.py#L21) |
| E13 | MD Quality berbeda dari QC pada hasil per baris | [E13: backend/services/inspection_service.py:718](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L718) |
| E14 | Perhitungan poin dan penetapan grade sekarang | [E14: backend/services/qc_inspection_service.py:42](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/qc_inspection_service.py#L42) |
| E15 | Jenis inspeksi dan pemisahan MD Quality | [E15: backend/services/inspection_service.py:48](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L48) |
| E16 | Random check memilih stok available secara acak | [E16: backend/services/inspection_service.py:892](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L892) |
| E17 | Form inspect mengirim agregat count per bobot poin | [E17: frontend/src/features/inspections/InspectLineModal.jsx:81](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/frontend/src/features/inspections/InspectLineModal.jsx#L81) |
| E18 | LOT internal dan LOT supplier mempunyai field berbeda | [E18: backend/services/lot_service.py:165](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/lot_service.py#L165) |
| E19 | Perubahan metadata LOT yang diizinkan | [E19: backend/services/lot_service.py:530](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/lot_service.py#L530) |
| E20 | Pengiriman logistik sekarang dibatasi satu SO/entitas | [E20: backend/services/logistics_service.py:144](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/logistics_service.py#L144) |
| E21 | SJ sekarang terbentuk per tugas/product/gudang | [E21: backend/services/shipment_service.py:94](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/shipment_service.py#L94) |
| E22 | Dispatch memperbarui SO dan memanggil posting GL | [E22: backend/services/shipment_service.py:132](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/shipment_service.py#L132) |
| E23 | Manifest pemeriksaan per SO dan gudang | [E23: backend/services/loading_check_service.py:158](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/loading_check_service.py#L158) |
| E24 | Pagar dispatch dan perubahan roll/qty setelah scan | [E24: backend/services/loading_check_service.py:195](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/loading_check_service.py#L195) |
| E25 | Transfer fisik tidak menggantikan jual beli antar entitas | [E25: backend/services/transfer_receipt_service.py:73](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/transfer_receipt_service.py#L73) |
| E26 | Penerimaan transfer aktual per roll | [E26: backend/services/transfer_receipt_service.py:236](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/transfer_receipt_service.py#L236) |
| E27 | Definisi metrik pesanan, pengiriman/jurnal dan uang berbeda | [E27: backend/services/analytics_catalog.py:67](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/analytics_catalog.py#L67) |
| E28 | Atribusi Sales memakai tim/split dan beberapa fallback | [E28: backend/services/analytics_facts.py:41](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/analytics_facts.py#L41) |
| E29 | Ekspor Excel hasil analitik sudah tersedia | [E29: backend/routers/ai_analytics.py:222](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/routers/ai_analytics.py#L222) |
| E30 | Pilihan periode KPI designer sekarang | [E30: backend/services/rnd_kpi_service.py:79](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_service.py#L79) |
| E31 | Statistik Design Studio: skor versi, revisi, atribusi pembuat | [E31: backend/services/rnd_kpi_service.py:256](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_service.py#L256) |
| E32 | PDF rapor sekarang hanya menampilkan 12 round terbaru | [E32: backend/services/rnd_kpi_export.py:442](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/rnd_kpi_export.py#L442) |
| E33 | Resolver konversi satuan produk | [E33: backend/services/uom_service.py:389](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/uom_service.py#L389) |
| E34 | Sumber daftar roll inspeksi penerimaan/retur | [E34: backend/services/inspection_service.py:521](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L521) |
| E35 | Pilihan hasil warna dan handfeel sekarang | [E35: backend/services/inspection_service.py:91](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/services/inspection_service.py#L91) |
| E36 | Export KPI dan rapor designer yang sudah ada | [E36: backend/routers/rnd.py:750](https://github.com/pandeyoga/KNHOST/blob/64d81f29577dae4daa86ddc64689dec7243804f2/backend/routers/rnd.py#L750) |

## Verifikasi terfokus

Lima pemeriksaan lulus pada fungsi asli yang diekstrak dari source dengan batas dependency in-memory: payload RFID tetap identitas saat qty teks berubah; guard multi-SO menolak tiga SO; beberapa SJ satu SO melewati guard yang diuji; permintaan harga khusus SO confirmed ditolak; perhitungan poin existing berbentuk bobot×jumlah.

Hasil: [VERIFIKASI_TERFOKUS.json](VERIFIKASI_TERFOKUS.json). Ini tidak menjalankan transaksi ERP, database, printer, C72 atau UR300. Rumus inspect client dan keseluruhan alur operasional belum divalidasi lewat perangkat.

## Perubahan baseline

Baseline laporan 15 Oktober: `6be5af70db5b0dedba6f1ce17b0a2f40f23ee046`. Main terbaru saat pengambilan: commit di atas. Di antara service/backend dan feature frontend yang dibandingkan, diff menyangkut makloon_order_service, pr_sourcing_service, MakloonOrderDetailPanel dan MakloonReturnMaterial. Bukti laporan ini tetap dibaca pada snapshot terbaru; tidak mengasumsikan laporan lama otomatis menggambarkan seluruh main terbaru.

## Arti status

Jelas berarti maksud kebutuhan telah dipahami, bukan fitur telah selesai. Ada fondasi berarti fungsi terkait tersedia, bukan seluruh skenario sudah terpenuhi. Usulan berarti desain hasil analisis yang perlu ditinjau sebelum menjadi development plan. Belum ada bukti berarti penelusuran terarah belum membuktikannya; tidak dinyatakan sebagai audit 100% seluruh repository.
