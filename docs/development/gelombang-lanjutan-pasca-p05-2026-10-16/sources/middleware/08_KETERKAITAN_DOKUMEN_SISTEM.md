# 8. Keterkaitan dengan Dokumentasi Sistem

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia

## 8.1 Pemetaan blueprint sebelumnya

| Referensi sistem | Implementasi dalam spesifikasi middleware |
|---|---|
| IMP-01 / meja pengguna | Task/detail/progress dan exception monitoring; ringkasan sama scope/source dengan rincian. |
| IMP-05, IMP-06 / alokasi dan qty roll | C72 loading memakai roll/manifest actual serta qty/unit server. |
| IMP-20 / scope lokasi | User/device/task context terikat site/warehouse, bukan grant global karena owner sama. |
| IMP-21 / OCR penerimaan | ERP menetapkan actual roll/qty; label menerima snapshot sah setelah review. |
| IMP-22, IMP-23 / putaway dan hierarchy | C72 scan bin memakai registry/resolver, bukan inferensi RSSI. |
| IMP-24, IMP-25 / rules/reference | Mutasi alamat tetap menjalankan rules/owner/status/capacity server; ID node stabil. |
| IMP-26, IMP-27 / transfer | Gate mengacu movement; actual receipt tidak berasal dari raw scan saja. |
| IMP-28, IMP-29 / opname/dashboard | Evidence RFID, qty adjustment dan hierarchy metrics tetap dipisahkan dan direkonsiliasi. |
| RFID-01, RFID-11 / hardware PoC | Profile SDK/firmware/model/media pada commissioning ketiga modul. |
| RFID-02, RFID-07, RFID-08, RFID-09 | Contract, outbox, health dan identity shared architecture. |
| RFID-03, RFID-04 | Modul handheld C72 dan HH-01 sampai HH-12. |
| RFID-05, RFID-06 | Agent reader Android on-device dan RD-01 sampai RD-12. |
| RFID-12 sampai RFID-15 | Connector CP30EN dan PR-01 sampai PR-12. |
| RFID-10 / RF04 / P10 | Integrasi INT-01 sampai INT-12 serta UAT perangkat nyata. |

## 8.2 Arahan terbaru yang menjadi acuan

Spesifikasi ini menjadi acuan pengembangan dan integrasi middleware. Reader Android menggunakan APK langsung pada unit tanpa laptop/PC runtime; itu menjadi acuan yang lebih spesifik daripada pilihan host umum pada dokumen awal.

Kontrak target ERP diperlakukan tersedia untuk tim pengembangan middleware. Catatan implementasi ERP berada dalam dokumen terpisah, sehingga modul tidak membuat fallback schema untuk menghindari pekerjaan penyelarasan server.

## 8.3 Referensi teknis primer

- [Chainway C72: lingkungan Android dan SDK](https://www.chainway.net/Products/Info/42).
- [Chainway U300: profil fixed reader Android](https://www.chainway.net/Products/Info/146).
- [Chainway U300: SDK/manual](https://www.chainway.net/support/Info/36).
- [Chainway CP30: dukungan SDK printer](https://www.chainway.net/support/Info/30).
- [Android: foreground service types](https://tim pengembangan.android.com/develop/background-work/services/fgs/service-types).
- [Android: restrictions pada startup service](https://tim pengembangan.android.com/develop/background-work/services/fgs/restrictions-bg-start).

Referensi hardware menunjukkan keluarga produk dan lingkungan; unit aktual tetap mempunyai release profile. Pada Android, pemilihan foreground service type/permission dan startup mengikuti OS serta target SDK yang digunakan. Kebijakan autostart/power OEM diuji saat commissioning; foreground service tidak dijadikan alasan menjanjikan pemulihan setelah semua jenis force-stop.

Referensi ini tidak menetapkan SDK method names atau nomor pin yang belum diverifikasi. Interface internal dalam buku merupakan desain project yang tim pengembangan petakan ke SDK nyata. Semua angka contoh payload/domain bersifat contoh, sedangkan parameter operasional disediakan config project.

## 8.4 Pemetaan acceptance blueprint RFID sebelumnya

| Acceptance lama | Kriteria/skenario paket ini |
|---|---|
| RACC-01 | HH-02, RD-02, PR-01 |
| RACC-02 | HH-02, RD-03 |
| RACC-03 | HH-01, PR-02 |
| RACC-04 | HH-03, HH-09 |
| RACC-05 | HH-02, HH-08 |
| RACC-06 | HH-04, INT-01 |
| RACC-07 | HH-05, HH-10, INT-02 |
| RACC-08 | HH-06, INT-04 |
| RACC-09 | HH-07 |
| RACC-10 | RD-03, INT-05 |
| RACC-11 | RD-04, RD-06, RD-08 |
| RACC-12 | RD-04, RD-05 |
| RACC-13 | RD-06, RD-07 |
| RACC-14 | HH-09, RD-05, INT-06 |
| RACC-15 | RD-09, INT-06 |
| RACC-16 | RD-11, PR-11 |
| RACC-17 | HH-08, RD-10, INT-09, INT-10 |
| RACC-18 | HH-09, RD-05, PR-02 |
| RACC-19 | INT-03 |
| RACC-20 | INT-01, INT-02, INT-03, INT-04 |
| RACC-21 | PR-01 |
| RACC-22 | PR-02, PR-03 |
| RACC-23 | PR-01, PR-11 |
| RACC-24 | PR-05, HH-04, INT-01 |
| RACC-25 | PR-06, INT-08 |
| RACC-26 | PR-07, PR-08, INT-07 |
| RACC-27 | PR-03, PR-08 |
| RACC-28 | PR-09, INT-12 |
| RACC-29 | PR-11 |
| RACC-30 | PR-10, INT-11 |

Pemetaan menyelaraskan cakupan, bukan menyatakan tes lama otomatis lulus. Requirement lama tetap ditelusuri saat UAT dan arahan reader on-device menjadi baseline operasi terbaru.
