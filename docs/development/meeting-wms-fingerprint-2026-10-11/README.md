# Paket Development Plan — KainNusantara

**Tanggal:** 11 Oktober 2026. **Scope:** 35 kebutuhan meeting/WMS/fingerprint. **Struktur:** 11 fase P00–P10, 16 keputusan, 67 skenario penerimaan. Semua status mulai belum dikerjakan/belum diuji.

## Cara import manual ke repo

Salin seluruh folder paket, termasuk sources, scripts, phases, templates, dan evidence, ke misalnya `docs/development/meeting-wms-fingerprint-2026-10-11/`. Pertahankan struktur relatif agar tautan dapat dibuka. Paket ini berisi dokumen, tracker, dan utility dokumen; tidak mengubah kode aplikasi ketika disalin.

## Urutan baca dan pakai

1. [Development plan utama](DEVELOPMENT_PLAN.md).
2. [Panduan agent](AGENT_GUIDE.md) dan [register keputusan](DECISIONS.md).
3. [Tracker](TRACKER.md) / [BACKLOG.json](BACKLOG.json), lalu [coverage](COVERAGE.md).
4. [Prompt P00](phases/P00.md), kemudian fase lain sesuai dependensi.
5. [Matriks acceptance](ACCEPTANCE_MATRIX.md) dan [template laporan](templates/PHASE_REPORT.md).
6. [Sumber kebutuhan dan bukti historis](sources/README.md).

Setelah agent mengubah BACKLOG.json, jalankan utility berikut dengan Python yang tersedia dari folder paket:

```text
python scripts/render_tracking.py
python scripts/validate_package.py
```

BACKLOG.json adalah sumber status; TRACKER.md hasil render. Utility validasi mengecek konsistensi paket dan status/evidence, bukan menguji ERP atau membuktikan 35 kebutuhan sudah fixed. Source harness WMS dipin ke snapshot audit dan tidak boleh dianggap test kelulusan branch baru.

## Workflow implementasi dan validasi

Agent mengerjakan fase → menyerahkan commit, migrasi, tes dan evidence → status implemented_pending_validation → pengguna/reviewer memvalidasi → validated atau reopened. Pertahankan ID IMP serta DEV-F/DEV-G lama. Jika hardware atau aturan klien belum tersedia, tandai item spesifik dan lanjutkan pekerjaan independen.

Rencana ini tidak menginstruksikan push, pembelian perangkat, pesan ke vendor, atau deployment produksi otomatis. Estimasi kalender ditetapkan setelah baseline P00; ukuran fase merupakan besaran relatif.
