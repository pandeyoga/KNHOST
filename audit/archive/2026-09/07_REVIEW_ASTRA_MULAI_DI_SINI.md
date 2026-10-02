> Pembaruan: [retur pembelian, refund dan reversal — sembilan skenario beserta prompt](28_AUDIT_RETUR_BELI_DAN_PROMPT.md). [Checklist baseline 96 skenario](29_CHECKLIST_SKENARIO_COVERAGE.md). Total runtime sekarang 59 skenario; belum seluruh flow tercakup.

> Pembaruan GRN/QC: [12 skenario dan dua temuan beserta prompt](26_AUDIT_GRN_FINANCE_QC_DAN_PROMPT.md). [Matriks 35 direktori fitur dan alur lintas modul](27_MATRIKS_CAKUPAN_FLOW.md). Seluruh flow belum dinyatakan tercakup.

> Pembaruan 30 September: [audit produksi, penerimaan dan RFID](24_AUDIT_PRODUKSI_PENERIMAAN_RFID.md), sepuluh skenario tambahan, tiga temuan tambahan dan pendalaman GN-06. [Prompt perbaikan](25_PROMPT_PRODUKSI_PENERIMAAN_RFID.md). Belum seluruh flow teruji.

> Pembaruan putaran 5: [kontrol periode, scope dan inspeksi](22_AUDIT_PERIODE_SCOPE_DAN_INSPEKSI.md), empat cacat baru terkonfirmasi, satu gap kebijakan, sembilan skenario tambahan dan 19 test bawaan lulus. [Prompt perbaikan](23_PROMPT_PERBAIKAN_PERIODE_SCOPE_INSPEKSI.md).

> **Integrasi lanjutan:** [18 — hasil pengujian dengan MongoDB/ASGI](18_HASIL_PENGUJIAN_INTEGRASI.md), [19 — enam detail integrasi](19_TEMUAN_INTEGRASI_LANJUTAN.md), [20 — prompt perbaikan](20_PROMPT_PERBAIKAN_INTEGRASI.md), [21 — cakupan runtime](21_CAKUPAN_RUNTIME_DAN_ENDPOINT.md). Belum full-flow sign-off.

> **Lanjutan 29 September:** [13 temuan tambahan](13_AUDIT_LANJUTAN_FLOW.md), [cakupan yang benar-benar selesai dan sisanya](14_STATUS_CAKUPAN_DAN_SISA.md), serta [prompt perbaikan baru](15_PROMPT_PERBAIKAN_LANJUTAN.md). Belum full-code/full-flow sign-off.

# Review Astra — hasil validasi dan pendalaman KNHOST

Tanggal: **29 September 2026**. Source baseline: `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Review menggunakan commit yang sama dengan audit sebelumnya agar hasilnya dapat dibandingkan; tidak menyatakan telah menilai perubahan main sesudah commit ini.

## Kesimpulan

Masalah utama bertahan setelah ditelusuri lebih dalam: **identitas roll fisik, bukti scan, otorisasi perpindahan, task/shipment, dan biaya belum selalu menjadi satu transaksi bisnis yang konsisten.** WMS/RFID mempunyai banyak fitur yang relevan untuk tekstil, tetapi snapshot ini belum layak menjadi kontrol release barang otomatis yang diandalkan. Finance juga belum dapat dinyatakan akurat tanpa memperbaiki posting/valuation/reporting dan merekonsiliasi data nyata.

Ini penilaian source dan uji terisolasi, bukan pernyataan bahwa seluruh transaksi produksi salah. Tidak ada perubahan kode aplikasi, deploy, akses credential, ataupun mutasi data produksi.

## Hasil review audit sebelumnya

Seluruh **65 ID** diberi keputusan individual dalam [08 — validasi temuan](08_VALIDASI_65_TEMUAN.md). Distribusi: 48 Valid, 10 Diperjelas, 1 Gap bersyarat, 1 Gap integrasi, 1 Gap desain, 2 Dikoreksi sebagian, 1 Gap kontrol, 1 Gap pemeliharaan. Kategori diperjelas/dikoreksi tidak berarti keseluruhan temuan dibatalkan; detail menjelaskan bagian yang tetap benar.

Koreksi terpenting:

- **FN-14:** surplus opname tidak selalu zero-cost. Fungsi menerima fallback harga_pokok produk; uji baru menghasilkan cost100. Masalah variance GL tetap valid.
- **RF-03:** PA aktif sudah menolak tujuan yang salah; cacat ada pada fallback transit. Kontrol yang benar jangan dihapus.
- **RF-13:** kasus nyata memakai status offline dari tombol Matikan, bukan enum disabled. Heartbeat dapat menghidupkan kembali status itu.
- **RF-17:** extra sudah memengaruhi result with_issues; yang tidak menghukumnya adalah metric accuracy. Status taggable/onsite/allocatable boleh berbeda sesuai tujuan.
- **FN-01:** double landed cost bergantung urutan parent/child; urutan yang berbeda menghasilkan uang berbeda. Ini tetap cacat, dengan trigger yang kini lebih tepat.
- **FN-11/GN-14:** WAC tidak otomatis salah; yang salah ialah basis biaya tak konsisten. Artefak kandidat credential juga tidak membuktikan credential masih aktif.

## Bukti lintas-flow yang lebih kuat

| Kejadian | Hasil uji fungsi asli dalam model dependensi |
|---|---|
| Split30 dan40 bersamaan dari100 | Total akhir140 pada interleaving yang diuji; sequential tetap100 |
| Pick NEW50 dengan OLD50 juga committed | Dispatch memilih OLD, berbeda dari roll pick |
| Dua request partial masing-masing30 | Sum surat jalan60, task shipped_qty tetap30 |
| Insert shipment gagal setelah task selesai | Roll transit, task dispatched, tidak ada shipment dan lock sudah hilang |
| Transfer eksplisit meminta ownerA tetapi ID rollB | RollB ikut reserved dan cabang itu tidak rebuild balance |
| Receipt transfer W1→W2 | BinW1 tetap melekat; acquired PO diganti TR sehingga selector late cost PO melewatkannya |
| Print job campuran A+B | Caller A-only dapat melihat item B karena owner header=A |
| Potong child menjadi grandchild | Parent langsung tersimpan ROOT, bukan CHILD |
| Landed cost100 untuk parent70+child30 | Uplift130 parent-first,100 child-first |

Rincian trigger, letak kode, dampak, perbaikan dan acceptance ada pada [09 — akar masalah dan flow](09_AKAR_MASALAH_DAN_FLOW.md). Delapan AX tidak dijumlahkan begitu saja terhadap65 karena beberapa memperluas temuan lama.

## Dokumen yang sebaiknya dibaca

1. [08 — Validasi 65 temuan](08_VALIDASI_65_TEMUAN.md): keputusan dan koreksi per ID, dengan link source yang dipatok commit.
2. [09 — Akar masalah dan flow](09_AKAR_MASALAH_DAN_FLOW.md): delapan analisis lanjutan dan enam flow yang menghubungkan WMS–RFID–Finance.
3. [10 — Blueprint RFID/WMS enterprise](10_BLUEPRINT_RFID_WMS_ENTERPRISE.md): pembanding Microsoft, Oracle, SAP, Zebra dan GS1; 41 baris capability; kontrak edge, state, UI/UX, commissioning dan batas kelayakan.
4. [11 — Prompt perbaikan tervalidasi](11_PROMPT_PERBAIKAN_TERVALIDASI.md): 13 batch yang mencakup semua65 ID dan temuan lanjutan, beserta acceptance numeric Finance.
5. [12 — Bukti validasi flow](12_BUKTI_VALIDASI_FLOW.md): 22 skenario, termasuk dua kontrol positif dan satu koreksi, metode serta batas pembuktian. [Paket reproduksi](review_repro/README.md) disertakan.

## Prioritas keputusan

Mulai dari scope/credentials dan bukti simulasi; perbaiki operasi roll/pick/shipment serta transfer; selaraskan cost layer dan durable posting; baru aktifkan gate dengan evidence passage dan uji perangkat nyata. Policy RFID wajib/manual harus per flow dan transparan. Wave/slotting/RTLS canggih dapat menyusul jika dibutuhkan volume operasi—bukan syarat menyalin semua fitur vendor.

Untuk rancangan gate D/H, risiko software yang ditemukan tidak dapat diselesaikan oleh tambahan antena/tunnel. Sebaliknya perbaikan software tidak membuktikan coverage radio. Kedua lapisan perlu acceptance terpisah yang bertemu pada satu manifest dan movement operation.

## Batas review

Tidak ada MongoDB integration run, server end-to-end, pengujian visual handheld/kiosk, middleware Kotlin atau commissioning reader/printer pada sesi ini. Uji baru mengeksekusi fungsi source dengan query model, controlled concurrency dan fault injection; hasilnya kuat untuk logika yang diuji tetapi tidak menggantikan persistence/authorization test nyata. Tidak ada akses database produksi untuk menghitung dampak historis atau mengesahkan saldo. Audit awal tetap tersimpan pada dokumen01–06 dan harus dibaca bersama koreksi ini.
