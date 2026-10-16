# Tracker Implementasi dan Validasi

Sumber status: BACKLOG.json. File ini dihasilkan scripts/render_tracking.py; ubah JSON lalu render ulang.

Semua status awal belum dikerjakan. implemented_pending_validation berbeda dari validated.

## Fase

| Fase | Judul | Status | Dependensi | Bukti |
|---|---|---|---|---|
| P00 | Baseline, keputusan bisnis, dan kontrak antarmodul | in_progress | — | evidence/P00/report.md; evidence/P00/wms-probes-head-96f73fa.json; evidence/P00/wms-probes-baseline-f59b8a6.json; evidence/P00/dry-run-bin-simulasi.json |
| P01 | Master data, lifecycle, dan cakupan lokasi pengguna | implemented_pending_validation | P00 | evidence/P01/report.md; /app/test_reports/iteration_173.json |
| P02 | Alamat, putaway, integritas referensi, dan rules WMS | implemented_pending_validation | P01 | evidence/P02/report.md; /app/test_reports/iteration_174.json; /app/test_reports/iteration_175.json |
| P03 | Penerimaan OCR dan transfer yang terkait pemenuhan SO | implemented_pending_validation | P02 | evidence/P03/report.md; /app/test_reports/iteration_176.json; backend/tests/test_p03_transfer_receipt.py |
| P04 | Sales, Keep/Pending, roll picker, kuantitas SO, dan grade | implemented_pending_validation | P01, P03 | evidence/P04/report.md; /app/test_reports/iteration_178.json; backend/tests/test_p03_p04_e2e.py |
| P05 | MD Quality, R&D existing, bahan makloon, dan sumber restock | implemented_pending_validation | P01, P02 | evidence/P05/report.md; /app/test_reports/iteration_179.json; /app/test_reports/iteration_182.json; backend/tests/test_p05_acceptance_acc31_33_34.py |
| P06 | Special Order multi-produk dan jalur desain pelanggan | not_started | P04, P05 | — |
| P07 | Jenis sampel dan proses Admin Cutting | not_started | P02, P04 | — |
| P08 | Opname, dashboard stok, dan konsistensi meja pengguna | not_started | P01, P02, P03, P04, P05, P06, P07 | — |
| P09 | Fingerprint langsung, log mentah, perhitungan shift, dan monitoring HR | not_started | P00, P01 | — |
| P10 | Integrasi menyeluruh, migrasi pilot, UAT, dan kesiapan rilis | not_started | P01, P02, P03, P04, P05, P06, P07, P08, P09 | — |

## Kebutuhan

| IMP | Kebutuhan | Fase utama | Status | Commit implementasi / verifikasi | Bukti / issue |
|---|---|---|---|---|---|
| IMP-01 | Setiap antrean membuka detail pekerjaan yang relevan | P08 | not_started | — / — | — |
| IMP-02 | Tampilan khusus Keep dengan definisi yang konsisten | P04 | implemented_pending_validation | — / — | — |
| IMP-03 | Pending dimulai dari kebutuhan produk, lalu dokumen pemenuhannya | P04 | implemented_pending_validation | — / — | — |
| IMP-04 | Pisahkan tampilan komersial Sales dari detail alokasi internal | P04 | implemented_pending_validation | — / — | — |
| IMP-05 | Roll picker untuk seluruh alokasi dan perubahan pemenuhan | P04 | implemented_pending_validation | — / — | — |
| IMP-06 | Qty, satuan, dan rincian roll jelas sepanjang alur SO | P04 | implemented_pending_validation | — / — | — |
| IMP-07 | Special Order dari artikel existing atau desain pelanggan | P06 | not_started | — / — | — |
| IMP-08 | Special Order berisi beberapa produk dengan progres per baris | P06 | not_started | — / — | — |
| IMP-09 | Tiga jenis sampel tampil jelas bagi Sales | P07 | not_started | — / — | — |
| IMP-10 | Tambahkan serah terima dan proses Admin Cutting setelah pemotongan | P07 | not_started | — / — | — |
| IMP-11 | Samakan harga non-BS dan berikan rekomendasi grade yang dapat dijelaskan | P04 | implemented_pending_validation | — / — | — |
| IMP-12 | Rapikan klasifikasi tahap bahan dan kelayakan tampil di Sales | P01 | implemented_pending_validation | — / — | — |
| IMP-13 | Pemetaan supplier, barang supplier, dan warna supplier lengkap | P01 | implemented_pending_validation | — / — | — |
| IMP-14 | Perjelas tambah, edit, nonaktif, dan hapus master | P01 | implemented_pending_validation | — / — | — |
| IMP-15 | Filter master produk/varian lengkap dan dapat digabung | P01 | implemented_pending_validation | — / — | — |
| IMP-16 | Bedakan MD Quality dengan QC beserta dampak prosesnya | P05 | implemented_pending_validation | — / — | — |
| IMP-17 | Uji tambahan SKU existing tanpa membuat master duplikat | P05 | implemented_pending_validation | — / — | — |
| IMP-18 | Tampilkan kebutuhan bahan makloon, reservasi, issue, dan WIP secara jelas | P05 | implemented_pending_validation | — / — | — |
| IMP-19 | Tetapkan sumber restock per artikel dan arahkan backorder sesuai master | P05 | implemented_pending_validation | — / — | — |
| IMP-20 | Batasi pekerjaan gudang menurut lokasi penugasan pengguna | P01 | implemented_pending_validation | — / — | — |
| IMP-21 | OCR SJ/packing list mengisi kandidat roll secara kelompok | P03 | implemented_pending_validation | — / — | — |
| IMP-22 | Pulihkan pengalaman putaway dan satukan jalur scan/alamat | P02 | implemented_pending_validation | — / — | — |
| IMP-23 | Hierarki fisik konsisten dari lokasi sampai posisi penyimpanan | P02 | implemented_pending_validation | — / — | — |
| IMP-24 | Rules gudang dan sublokasi berlaku konsisten di seluruh jalur | P02 | implemented_pending_validation | — / — | — |
| IMP-25 | Lindungi stok dan tugas saat struktur lokasi diubah | P02 | implemented_pending_validation | — / — | — |
| IMP-26 | Transfer antar gudang untuk memenuhi SO menjaga komitmen barang | P03 | implemented_pending_validation | — / — | — |
| IMP-27 | Terima transfer berdasarkan roll aktual, termasuk parsial dan selisih | P03 | implemented_pending_validation | — / — | — |
| IMP-28 | Stock opname menyatukan qty, identitas roll, alamat, dan RFID | P08 | not_started | — / — | — |
| IMP-29 | Dashboard stok berjenjang dengan subtotal satuan dan status yang benar | P08 | not_started | — / — | — |
| IMP-30 | Mesin mengirim absensi langsung ke penerima di server ERP | P09 | not_started | — / — | — |
| IMP-31 | Registrasi perangkat dan pemetaan ID pegawai terkontrol | P09 | not_started | — / — | — |
| IMP-32 | Pisahkan log punch mentah dari hasil perhitungan kehadiran | P09 | not_started | — / — | — |
| IMP-33 | Tahan putus koneksi dan cegah pencatatan ganda | P09 | not_started | — / — | — |
| IMP-34 | Antarmuka HR memantau sinkronisasi dan exception | P09 | not_started | — / — | — |
| IMP-35 | Tetapkan kompatibilitas hardware melalui uji perangkat nyata | P09 | not_started | — / — | — |

## Keputusan

| DEC | Topik | Status | Sumber keputusan / alasan |
|---|---|---|---|
| DEC-01 | Keep/Pending | confirmed | Pemilik via chat 2026-10-11 (P04) |
| DEC-02 | Special Order | open | — |
| DEC-03 | Sampel dan Admin Cutting | open | — |
| DEC-04 | Grade dan BS | open | Pemilik via chat 2026-10-11 (P04) — sebagian |
| DEC-05 | Dataset dan lifecycle master | confirmed | Pemilik via chat 2026-10-11 (P01) |
| DEC-06 | MD Quality / QC / R&D existing | confirmed | Pemilik via chat 2026-10-12/13 |
| DEC-07 | Resep dan restock | proposed | Tercatat sebagai keputusan pemilik 2026-10-11 di kode sesi sebelumnya (restock_source_service.py, seed_p05_kn.py) — mohon dikonfirmasi ulang |
| DEC-08 | OCR penerimaan | open | — |
| DEC-09 | Hak lokasi dan cakupan data | confirmed | Pemilik via chat 2026-10-11 (P01) |
| DEC-10 | Rules dan kapasitas WMS | confirmed | Pemilik via chat 2026-10-11 (P02) |
| DEC-11 | Transfer terkait SO | open | — |
| DEC-12 | Opname | open | — |
| DEC-13 | Dampak komersial dan Finance | open | Pemilik via chat 2026-10-11 (P04) — sebagian |
| DEC-14 | Hardware fingerprint | open | — |
| DEC-15 | Perhitungan absensi | open | — |
| DEC-16 | Pilot dan operasi | open | — |

## Pengujian

| ACC | Fase | Skenario | Hasil | Commit / evidence |
|---|---|---|---|---|
| ACC-00 | P00 | Baseline target | not_run | —; — |
| ACC-01 | P01 | Tahap dan kelayakan jual | pass | c3291a7; evidence/P01/report.md |
| ACC-02 | P01 | Alias supplier/color | pass | c3291a7; evidence/P01/report.md |
| ACC-03 | P01 | Lifecycle master | pass | c3291a7; evidence/P01/report.md |
| ACC-04 | P01 | Filter master | pass | c3291a7; evidence/P01/report.md |
| ACC-05 | P01 | Scope lokasi | pass | c3291a7; evidence/P01/report.md |
| ACC-06 | P02 | Resolver modern/legacy | pass | 765b099; evidence/P02/report.md |
| ACC-07 | P02 | Menu dan putaway | not_run | —; evidence/P02/report.md |
| ACC-08 | P02 | Status fisik | pass | 765b099; evidence/P02/report.md |
| ACC-09 | P02 | Padanan Lemari/Rak | not_run | —; evidence/P02/report.md |
| ACC-10 | P02 | Hapus atau pindah struktur | pass | 765b099; evidence/P02/report.md |
| ACC-11 | P02 | Shared/dedicated | not_run | —; evidence/P02/report.md |
| ACC-12 | P02 | Rules gabungan | pass | 765b099; evidence/P02/report.md |
| ACC-13 | P02 | Kapasitas dan balapan aksi | pass | 765b099; evidence/P02/report.md |
| ACC-14 | P03 | OCR per roll | pass | P03 di atas 3ed96fd; evidence/P03/report.md; /app/test_reports/iteration_176.json |
| ACC-15 | P03 | SJ hanya total | pass | P03 di atas 3ed96fd; evidence/P03/report.md |
| ACC-16 | P03 | Bandung-Jakarta-customer | not_run | —; evidence/P03/report.md; /app/test_reports/iteration_176.json; /app/test_reports/iteration_178.json; backend/tests/test_p03_p04_e2e.py |
| ACC-17 | P03 | Reservasi dan concurrency | not_run | —; evidence/P03/report.md |
| ACC-18 | P03 | Receipt parsial | pass | P03 di atas 3ed96fd; evidence/P03/report.md; /app/test_reports/iteration_176.json |
| ACC-19 | P03 | Exception transfer | pass | P03 di atas 3ed96fd; evidence/P03/report.md; /app/test_reports/iteration_176.json |
| ACC-20 | P03 | Aturan tujuan dan ownership | not_run | —; evidence/P03/report.md; /app/test_reports/iteration_176.json |
| ACC-21 | P04 | Keep dan Pending bersamaan | not_run | —; evidence/P04/report.md; /app/test_reports/iteration_178.json |
| ACC-22 | P04 | Referensi supply Pending | not_run | —; — |
| ACC-23 | P04 | Sales projection | not_run | —; — |
| ACC-24 | P04 | Stok global dan ATP | not_run | —; — |
| ACC-25 | P04 | Edit alokasi roll | not_run | —; — |
| ACC-26 | P04 | Yard dan roll utuh | not_run | —; — |
| ACC-27 | P04 | Detail qty sebelum/sesudah alokasi | not_run | —; — |
| ACC-28 | P04 | Harga dan rekomendasi grade | not_run | —; — |
| ACC-29 | P05 | MD Quality dan QC | pass | preview 2026-10-13; /app/test_reports/iteration_181.json; backend/tests/test_p05_imp16_md_quality_qc.py |
| ACC-30 | P05 | Labdip dan Handfeel existing | pass | P05 di atas ad51444; evidence/P05/report.md; /app/test_reports/iteration_179.json |
| ACC-31 | P05 | Perubahan identitas dan hak MD | pass | preview 2026-10-13; backend/tests/test_p05_acceptance_acc31_33_34.py |
| ACC-32 | P05 | Reservasi dan issue 1:1 | pass | preview 2026-10-13; backend/tests/test_p05_acceptance_acc31_33_34.py |
| ACC-33 | P05 | Yield dan bahan kurang | pass | preview 2026-10-14; /app/test_reports/iteration_182.json; backend/tests/test_p05_acceptance_acc31_33_34.py (resep acuan 1,6 m/kemeja, yield 95%, roll 50 m) |
| ACC-34 | P05 | Pembatalan/partial produksi | pass | preview 2026-10-14; /app/test_reports/iteration_182.json; backend/tests/test_p05_acceptance_acc31_33_34.py (DEC-13: bahan tetap di mitra sampai retur dicatat) |
| ACC-35 | P05 | Jalur restock | pass | P05 di atas ad51444; evidence/P05/report.md; /app/test_reports/iteration_179.json; backend/tests/test_p05_restock_material_revalidation.py |
| ACC-36 | P06 | Desain pelanggan dan artikel existing | not_run | —; — |
| ACC-37 | P06 | OD dua produk | not_run | —; — |
| ACC-38 | P06 | OD legacy dan retry | not_run | —; — |
| ACC-39 | P07 | Tipe sampel | not_run | —; — |
| ACC-40 | P07 | Handoff Admin Cutting | not_run | —; — |
| ACC-41 | P07 | Retry, cancel, dan sampel legacy | not_run | —; — |
| ACC-42 | P08 | Opname actual roll dan RFID | not_run | —; — |
| ACC-43 | P08 | Snapshot dan transaksi berjalan | not_run | —; — |
| ACC-44 | P08 | Posting adjustment dan dampak reservasi | not_run | —; — |
| ACC-45 | P08 | Mixed unit dan kapasitas | not_run | —; evidence/P02/report.md |
| ACC-46 | P08 | Rekonsiliasi hierarchy | not_run | —; — |
| ACC-47 | P08 | Shared capacity dan permissions | not_run | —; — |
| ACC-48 | P08 | Meja seluruh peran | not_run | —; — |
| ACC-49 | P09 | Hardware PoC | not_run | —; — |
| ACC-50 | P09 | Native protocol receiver | not_run | —; — |
| ACC-51 | P09 | Mapping dan registrasi | not_run | —; — |
| ACC-52 | P09 | Raw event dan koreksi | not_run | —; — |
| ACC-53 | P09 | Shift overnight | not_run | —; — |
| ACC-54 | P09 | Missing/multiple punches dan overtime | not_run | —; — |
| ACC-55 | P09 | Offline dan kiriman ulang | not_run | —; — |
| ACC-56 | P09 | Out-of-order, drift, dan partial failure | not_run | —; — |
| ACC-57 | P09 | Monitoring HR | not_run | —; — |
| ACC-58 | P09 | Pilot direct tanpa perantara | not_run | —; — |
| ACC-59 | P10 | E2E SO dan transfer | not_run | —; — |
| ACC-60 | P10 | E2E backorder supplier/makloon | not_run | —; — |
| ACC-61 | P10 | E2E Special Order dan R&D | not_run | —; — |
| ACC-62 | P10 | E2E sampel dan WMS | not_run | —; — |
| ACC-63 | P10 | E2E attendance dan payroll review | not_run | —; — |
| ACC-64 | P10 | Migrasi dan rollback | not_run | —; — |
| ACC-65 | P10 | Concurrency dan recovery lintas modul | not_run | —; — |
| ACC-66 | P10 | UAT dan kesiapan rilis | not_run | —; — |
