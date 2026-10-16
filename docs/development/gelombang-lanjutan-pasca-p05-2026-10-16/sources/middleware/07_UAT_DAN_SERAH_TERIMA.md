# 7. Pengujian, Integrasi dan Serah Terima Implementasi

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia

## 7.1 Pembagian tanggung jawab

| Fungsi | Tanggung jawab serah terima |
|---|---|
| Tim C72 | APK/source/SDK mapping, task UI, context/evidence/outbox, lifecycle dan actual C72 tests. |
| Tim reader | APK on-device, boot/service/SDK profile, passage/direction/signals, offline/backfill dan no-PC evidence. |
| Tim printer | Connector/SDK transport, item/attempt/ledger, physical outcome, uncertain recovery dan actual CP30EN tests. |
| Tim ERP | Lingkungan contract target, resource/dataset, auth/registry, expected/dokumen dan monitoring integration. |
| QA | Contract tests, failure/concurrency, UI, real-hardware evidence dan cross-module reconciliation. |
| Project lead/pemilik proses | Parameter pilot, SOP, PIC, UAT dan penetapan scope rilis. |

## 7.2 Test layers

Unit tests memakai adapter fake untuk state/queue/context, bukan bukti unit hardware bekerja. Contract tests memakai schema/fixtures yang sama. Integration tests mengecek API+data+operator scope. Hardware tests menggunakan serial/firmware/build nyata. UAT menggunakan tugas serta kondisi gudang representatif.

Setiap hasil memuat requirement ID, target commit server, client build, hardware/SDK/config profile, langkah, input, expected, actual, pass/fail/not_run, dan evidence. Build berhasil tidak menutup requirement hardware. Seluruh hasil awal dalam paket adalah not_run.

## 7.3 Kriteria modul

HH-01 sampai HH-12, RD-01 sampai RD-12 dan PR-01 sampai PR-12 adalah 36 kriteria utama modul. Skenario RACC-01 sampai RACC-30 dari blueprint hardware sebelumnya tetap relevan; pemetaan disediakan pada dokumen keterkaitan sistem. Reader RD-01 secara khusus menutup arahan no-PC runtime.

## 7.4 Uji integrasi wajib

| ID | Skenario dan hasil yang wajib |
|---|---|
| INT-01 | CP30EN write EPC -> label dipasang -> C72 verify -> ERP tag-roll evidence; database identity saja belum dianggap physical proof. |
| INT-02 | Loading C72 -> ERP manifest/version -> reader live passage -> indikator sesuai dokumen; qty/unit tetap otoritatif. |
| INT-03 | Bandung -> Jakarta transfer -> actual receipt/putaway atau cross-dock; reader tidak menggantikan penerimaan fisik. |
| INT-04 | Opname sweep -> found/missing/extra/untagged -> review/adjustment; tidak ada double qty/jurnal. |
| INT-05 | Satu physical reader memetakan logical gates/direction yang sah; scope, latch dan response tidak tertukar. |
| INT-06 | Network mati/reconnect -> outbox/backfill; tidak ada green lama, task baru palsu atau duplicate effects. |
| INT-07 | Printer selesai output tetapi ACK hilang -> result replay/reconcile; tidak physical reprint otomatis. |
| INT-08 | Partial print/encode -> per-item state -> C72 issues; seluruh batch tidak ditutup sukses. |
| INT-09 | Manifest/config berubah, user logout/context expired/key rotated; stale action ditolak dengan evidence tetap. |
| INT-10 | Reboot/update reader dan C72 serta connector restart; ledger/schema/pending data bertahan tanpa PC reader runtime. |
| INT-11 | Server unfinished effects setelah event/result durable dipulihkan; roll/tag/journey/dokumen tidak terduplikasi. |
| INT-12 | Reprint/retag disetujui -> identitas lama/baru/physical label ditangani -> gate/stock trace tetap konsisten. |

## 7.5 Bukti dan status pekerjaan

Status: not_started -> in_progress -> implemented_pending_validation -> validated; reopened untuk regresi. Waiting hardware/decision digunakan pada bagian yang memang membutuhkan input tersebut. Kontrak target tetap acuan development, sehingga pengembang tidak membuat variasi schema per modul.

Simpan evidence per modul/requirement dan laporan integrasi terpisah. Validator menguji commit/build/profile yang sama. Screenshot UI saja tidak membuktikan SDK read atau print encoding; lampirkan raw callback/status/event/response yang relevan dengan credential direduksi.

## 7.6 Checklist serah terima

1. Source repository, build instructions, dependency lock dan ketentuan SDK vendor.
2. APK C72, APK reader Android, serta service package CP30EN; package/signing/build identity.
3. Hardware/firmware/SDK/ABI/permission/media/config compatibility matrix.
4. Implementasi sesuai OpenAPI dan typed contract test suite.
5. Local schema serta migration/update/rollback evidence; pending data tidak hilang.
6. SOP provisioning, deployment, monitoring, recovery dan exception.
7. Hasil 36 requirement criteria serta 12 integration scenarios, dengan actual hardware evidence.
8. Known limitations/issue yang masih terbuka, dampak, PIC dan disposition scope.

## 7.7 Definition of done

Selesai ketika ketiga modul menjalankan flow yang ditetapkan pada perangkat nyata; reader beroperasi tanpa PC penghubung; contract/state/evidence/scope/recovery lulus; dokumen, unit, owner dan identitas sesuai ERP; seluruh artifact serta runbook diserahkan; UAT ditandatangani fungsi yang berwenang pada versi yang tercatat.

Dokumentasi ini sendiri tidak menyatakan aplikasi telah dibuat atau hardware telah diuji. Penetapan tanggal rilis, nama personal approver dan hasil UAT diisi saat pelaksanaan, bukan dibuat oleh dokumen.
