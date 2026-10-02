> Pembaruan: [retur pembelian, refund dan reversal — sembilan skenario beserta prompt](28_AUDIT_RETUR_BELI_DAN_PROMPT.md). [Checklist baseline 96 skenario](29_CHECKLIST_SKENARIO_COVERAGE.md). Total runtime sekarang 59 skenario; belum seluruh flow tercakup.

> Pembaruan GRN/QC: [12 skenario dan dua temuan beserta prompt](26_AUDIT_GRN_FINANCE_QC_DAN_PROMPT.md). [Matriks 35 direktori fitur dan alur lintas modul](27_MATRIKS_CAKUPAN_FLOW.md). Seluruh flow belum dinyatakan tercakup.

> Pembaruan 30 September: [audit produksi, penerimaan dan RFID](24_AUDIT_PRODUKSI_PENERIMAAN_RFID.md), sepuluh skenario tambahan, tiga temuan tambahan dan pendalaman GN-06. [Prompt perbaikan](25_PROMPT_PRODUKSI_PENERIMAAN_RFID.md). Belum seluruh flow teruji.

> Pembaruan putaran 5: [kontrol periode, scope dan inspeksi](22_AUDIT_PERIODE_SCOPE_DAN_INSPEKSI.md), empat cacat baru terkonfirmasi, satu gap kebijakan, sembilan skenario tambahan dan 19 test bawaan lulus. [Prompt perbaikan](23_PROMPT_PERBAIKAN_PERIODE_SCOPE_INSPEKSI.md).

> **Integrasi lanjutan:** [18 — hasil pengujian dengan MongoDB/ASGI](18_HASIL_PENGUJIAN_INTEGRASI.md), [19 — enam detail integrasi](19_TEMUAN_INTEGRASI_LANJUTAN.md), [20 — prompt perbaikan](20_PROMPT_PERBAIKAN_INTEGRASI.md), [21 — cakupan runtime](21_CAKUPAN_RUNTIME_DAN_ENDPOINT.md). Belum full-flow sign-off.

> **Lanjutan 29 September:** [13 temuan tambahan](13_AUDIT_LANJUTAN_FLOW.md), [cakupan yang benar-benar selesai dan sisanya](14_STATUS_CAKUPAN_DAN_SISA.md), serta [prompt perbaikan baru](15_PROMPT_PERBAIKAN_LANJUTAN.md). Belum full-code/full-flow sign-off.

> **Review lanjutan 29 September 2026:** baca [hasil validasi Astra](07_REVIEW_ASTRA_MULAI_DI_SINI.md) dan [koreksi per temuan](08_VALIDASI_65_TEMUAN.md) sebelum memakai laporan/prompt awal ini. Sebagian klaim telah dipersempit atau dikoreksi.

# Audit KNHOST — mulai di sini

Repo [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST), snapshot [d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467](https://github.com/pandeyoga/KNHOST/commit/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467), diperiksa 28 September 2026.

**Keputusan audit: RFID/gate belum layak sebagai kontrol utama izin fisik; WMS belum layak dinyatakan aman untuk operasi enterprise; Finance belum layak dijadikan angka final yang diasumsikan akurat tanpa perbaikan dan rekonsiliasi.** Fitur dasarnya cukup luas, tetapi beberapa invariant stok, perjalanan, scope dan financial lifecycle belum dijaga. Penilaian ini atas kode, bukan klaim seluruh transaksi produksi sudah salah.

**65 temuan terkurasi: 47 P1, 16 P2, 2 P3.** P1 adalah blocker proses terkait, P2 cacat/kontrol operasional penting, P3 maintainability. Jumlah tersebut tidak mencakup semua enhancement enterprise atau setiap warning lint. Tidak ada P0 tanpa bukti dampak produksi.

## Dokumen yang disediakan

| Dokumen | Isi |
|---|---|
| [01 — Temuan kode](01_TEMUAN_AUDIT_KNHOST.md) | 65 temuan, file/baris dan cuplikan kode, akar masalah, skenario, dampak, arah fix serta acceptance criteria |
| [02 — Analisis fitur dan enterprise](02_RFID_WMS_FINANCE_FIT_GAP.md) | RFID/WMS, SSOT, UI/UX, bisnis proses tekstil/gate D/H, Finance dan pembanding resmi |
| [03 — Prompt agent developer](03_PROMPT_PERBAIKAN_AGENT.md) | Prompt pembuka, 16 batch dan 65 prompt individual siap salin |
| [04 — Cakupan dan verifikasi](04_CAKUPAN_DAN_VERIFIKASI.md) | Modul lain, kedalaman review, hasil/skip guardrail dan bukti yang diperlukan untuk go-live |
| [05 — Register berkas dan endpoint](05_REGISTER_BERKAS_DAN_ENDPOINT.md) | Inventaris seluruh sumber, kelompok frontend dan decorator endpoint; label kedalaman |
| [06 — Bukti pemeriksaan](06_BUKTI_REPRODUKSI_DAN_PEMERIKSAAN.md) | Output 18 fixture, syntax/lint dan batas interpretasinya |

## Yang harus diperbaiki lebih dahulu

1. Identitas/movement RFID: format EPC database berbeda dari chip; gate OUT/IN bisa green tanpa manifest/source/destination valid (RF-01/02/03). UI stale atau mixed passage dapat memberikan isyarat lolos yang salah (UX-01).
2. Integritas roll/WMS: stale overwrite setelah split, identitas anak dibuat sebelum physical cut, empty scan tiba dianggap semua roll, transit masih tersedia, dan movement tidak diklaim tunggal (WM-01–05).
3. Akurasi Finance: landed cost dapat teralokasi ganda parent–child; WAC mencampur unit; cashflow mengklasifikasikan jurnal nonkas sebagai operasi/investasi; COA lintas entitas dapat mengubah kategori; lifecycle kas/AR/period lock tidak konsisten (FN-01/03/04/05/07–10).
4. Scope dan recovery: replay middleware, websocket tracking, akses per-ID/device credential, stock mutation tanpa CAS dan rollback snapshot lama (GN-01–07, RF-08/12/13).
5. Proses lain: production consume, internal request conversion, CRM/POS entity scope, leave oversubscription, payroll TER/lembur dan marketing partial metrics (GN-06/08/09/10; HR-01–03; MK-01).

## Bukti dan batas yang perlu diketahui

18 skenario fungsi asli dengan mock menunjukkan 16 cacat/gap dan 2 kontrol pembanding. Parse 821 berkas frontend dan seluruh Python terinventarisasi tidak menemukan syntax error; ini tidak menutup bug bisnis. Guardrail bawaan belum seluruhnya lulus: ada violation, dependency error dan bagian DB/runtime skip.

Audit ini mencakup peta modul/flow dan inventaris source; kedalaman behavioral test tidak seragam. Tidak semua endpoint dijalankan, tidak ada rekonsiliasi data produksi, full build/browser session atau hardware commissioning. Dokumen 04 dan 05 menjelaskan tepatnya. Temuan statis/race wajib dibuktikan dengan integration test sebelum ditutup.

Mulai dari batch integritas dan scope, lalu valuation/lifecycle Finance, kemudian workflow RFID/WMS dan UX. Gunakan prompt per tiket; review hasil fix pada branch terbaru. Pilot hanya setelah blocker flow pilot tertutup dan bukti integration/reconciliation tersedia; rollout enterprise memerlukan commissioning serta pengujian skala dan kegagalan.
