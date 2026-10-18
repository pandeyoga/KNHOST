# Panduan Paket Middleware RFID

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia  
**Nomor dokumen:** KNI-RFID-MW-SPEC-001  
**Versi:** 1.0  
**Tanggal:** 13 Oktober 2026  
**Status:** spesifikasi development dan acuan review teknis.

## Tujuan

Menjadi acuan tim pengembangan untuk membangun aplikasi handheld C72, agent reader UR300 Android dan connector printer CP30EN. Paket menjelaskan arsitektur, flow operasional, input/output, contract, local state, recovery, commissioning dan bukti penerimaan.

Seluruh kontrak target dalam manual diperlakukan tersedia sesuai arahan pemilik project. Ini adalah baseline rancangan integrasi, bukan pernyataan bahwa semua endpoint telah deployed. Perbedaan snapshot ERP dicatat hanya dalam catatan-erp/ERP_GAP_NOTES.md, terpisah dari manual middleware.

## Isi dan urutan baca

1. 01_ARSITEKTUR_BERSAMA.md: batas SSOT, tiga runtime, outbox, identity dan config.
2. 02_MODUL_HANDHELD_C72.md: layar, task, SDK Android, print verify, loading, opname, putaway dan tag search.
3. 03_MODUL_READER_ANDROID_UR300.md: reader agent on-device tanpa PC harian, passage, decision, latch dan offline.
4. 04_MODUL_PRINTER_CP30EN.md: claim, intent, output, encoding, partial, unknown dan reconciliation.
5. 05_KONTRAK_API_TARGET.md dan kontrak/OPENAPI_RFID_V2.json: path, auth, schema dan error.
6. 06_PERSIAPAN_COMMISSIONING.md: kebutuhan unit/SDK, runtime, instalasi, profile dan runbook.
7. 07_UAT_DAN_SERAH_TERIMA.md: 36 acceptance criteria modul dan 12 skenario integrasi.
8. 08_KETERKAITAN_DOKUMEN_SISTEM.md: keterkaitan rencana ERP/RFID terdahulu dan sumber vendor.

PDF memuat delapan bab spesifikasi middleware. Catatan ERP dan raw OpenAPI sengaja disediakan sebagai berkas pendamping terpisah. File uat/UAT_TRACKER.csv dapat diisi tim pengembangan/QA dan di-review berdasarkan evidence, bukan diubah menjadi pass hanya karena aplikasi berhasil dibangun.

## Kontrol dokumen

| Peran/fungsi | Tanggung jawab |
|---|---|
| Pemilik project ERP Kain Nussantara | Keputusan scope bisnis dan penerimaan kebutuhan. |
| Tim produksi IT PT Kubus Teknologi Indonesia | Implementasi, review teknis dan kontrol versi. |
| Tim ERP | Konsistensi contract, SSOT, izin dan business effects. |
| Tim Android | APK C72 dan reader beserta lifecycle/SDK mapping. |
| Tim printer connector | Service, physical output ledger dan recovery CP30EN. |
| QA dan operasi gudang | UAT aktual, commissioning, SOP dan evidence. |

Versi 1.0 menetapkan reader native Android tanpa PC runtime, tiga modul terpisah, contract target lengkap, printer per-item outcome dan catatan ERP terpisah. Nama personal penyetuju, tanda tangan dan tanggal UAT diisi saat pelaksanaan. Perubahan contract memerlukan revisi OpenAPI, dokumen, fixture, client/server compatibility dan UAT terkait secara bersamaan.

## Batas serah terima paket ini

Paket berisi dokumentasi, contract dan template pengujian. Tidak berisi implementasi APK/connector, SDK vendor yang dilisensikan, credential produksi, atau hasil uji perangkat nyata. Semua outcome UAT awal adalah not_run. Tidak ada perubahan source ERP atau deployment dalam pembuatan paket ini.
