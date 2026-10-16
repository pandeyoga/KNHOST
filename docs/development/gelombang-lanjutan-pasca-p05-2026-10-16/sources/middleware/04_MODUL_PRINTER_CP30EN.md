# 4. Modul Printer CP30EN - Connector, Encoding dan Recovery

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia  
**Artefak serah terima:** paket service connector, source, adapter/SDK profile, media/template profile, runbook dan evidence printer nyata.

## 4.1 Tujuan dan topologi

Connector mengambil job ERP, mengendalikan CP30EN, mencatat hasil fisik per label dan menghubungkannya ke verifikasi C72. Connector tidak membuat EPC/roll/stock baru sendiri.

```text
ERP print API <--HTTPS--> Connector + local ledger <--transport--> CP30EN
CP30EN label -> ditempel ke roll -> C72 verification -> ERP
```

Service dapat berjalan pada host Windows/Linux yang sesuai SDK dan menjangkau printer, atau server yang mempunyai rute yang sah. Runtime dipilih dari commissioning profile. Reader Android tetap berdiri sendiri dan tidak bergantung host printer. Reuse perangkat Android untuk print transport hanya diterima bila runtime/protokol terbukti, bukan karena dua perangkat merek sama.

## 4.2 Hardware dan SDK profile

Catat CP30EN label/serial/firmware/modul RFID, resolution, interface, media dimension/pitch/inlay, ribbon jika digunakan, command language, readback/status/error support dan print-job correlation yang benar-benar tersedia. Profil media yang diubah memerlukan kalibrasi serta test label.

Interface internal PrinterAdapter: connect(profile), capabilities(), queryReadiness(), sendItem(payload), queryOutcome(handle), stopAcceptingNewWork(), disconnect(). Outcome/status query dapat unavailable sesuai capability dan harus ditangani sebagai unknown, bukan dianggap sukses. Nama ini bukan method SDK resmi.

Print connector tidak menjalankan perintah RFID dari asumsi seluruh emulator ZPL kompatibel. Payload/profile yang disahkan diterapkan pada firmware aktual; EPC chip dibandingkan dengan expected ERP/C72. Template font, barcode, ukuran dan satuan diuji pada resolusi unit.

## 4.3 Komponen service

| Komponen | Tanggung jawab |
|---|---|
| PrinterIdentity | Registry device, key, physical printer dan warehouse binding. |
| ClaimScheduler | Claim pekerjaan yang sesuai capability dan capacity. |
| LeaseManager | Stable attempt, renew, expiry dan result reconciliation. |
| JobSnapshotValidator | Revision/payload digest/source snapshot. |
| PrinterAdapter | SDK/protokol, readiness, send dan outcome. |
| OutputLedger | Durable print intent/sent/outcome per job-item-attempt. |
| ResultReporter | Idempotent result/ACK serta recovery server. |
| ReconciliationQueue | Hasil ambigu, operator resolution dan evidence. |
| HealthReporter | Printer state terpisah dari HTTP connector health. |

Host dapat mengelola beberapa printer hanya dengan worker/identity/ledger terisolasi per printer. Satu key tidak digunakan untuk mengklaim seluruh printer/gudang. Satu active output worker per physical binding menjadi default desain.

## 4.4 Flow job dan claim

1. ERP membuat job dari roll serta EPC identity yang sah, dengan item ID/revision/payload digest dan target warehouse.
2. Connector memeriksa capability/readiness lalu claim pekerjaan melalui printer API.
3. Claim menghasilkan job/item snapshot dan lease dengan attempt_id, server time dan expires_at. Poll berikutnya tidak mengganti ID attempt yang masih aktif.
4. Snapshot serta ledger claim disimpan durable. Connector memeriksa config/lease/revision sebelum memulai item.
5. Connector mencatat print intent dan mengirim start acknowledgement yang idempoten ke ERP sebelum perintah fisik.
6. Setelah start accepted untuk lease/context sah, adapter mengirim item. Penyerahan ke transport hanya menghasilkan SENT, bukan CONFIRMED.
7. Adapter/status/readback/operational evidence menentukan outcome item. Hasil dikirim idempoten ke ERP.
8. ERP mengagregasi outcome serta lifecycle identitas; verifikasi C72 adalah flow berikutnya yang terpisah.

Server tidak mereassign pekerjaan berstatus started/uncertain hanya karena lease habis. Renew mempertahankan attempt_id. Claim yang belum mulai dapat dilepas/reassign sesuai policy; started output memerlukan reconciliation sebelum pengulangan fisik.

## 4.5 State ledger

CLAIMED -> INTENT_RECORDED -> START_ACCEPTED -> SENT -> CONFIRMED/FAILED/UNKNOWN -> RESULT_PENDING -> REPORTED. READY_FOR_VERIFY merupakan status proses setelah outcome yang sah, bukan bukti tag telah terpasang dan terbaca oleh C72.

Store lokal mempunyai job_id, job_revision, item_id, attempt_id, printer_id, EPC expected, payload_sha256, intent/start/sent/result timestamps, print_status, encode_status, evidence_source, adapter_handle, last_error dan operator resolution reference. Unique(job_id,item_id,attempt_id) menjaga replay transport/results.

Printer output tidak dapat dijamin tepat sekali hanya dari unique database record. Crash setelah send bisa menyisakan ketidakpastian fisik. State UNKNOWN mempertahankan evidence dan menghentikan blind reprint sampai outcome ditentukan.

## 4.6 Hasil per item dan batch parsial

print_status dan encode_status memakai confirmed/failed/unknown; encode_status=not_applicable hanya untuk jenis label non-RFID yang memang diizinkan. payload sent atau spool accepted tidak dipetakan otomatis ke confirmed.

Batch 10 label dengan 7 confirmed, 2 failed dan 1 unknown menghasilkan agregat partial/needs_review. Item yang gagal/unknown tidak ditutup sukses karena tujuh lainnya selesai. Server memiliki context item/tag yang tepat; connector tidak mengaktifkan seluruh tag dengan ACK header job.

Evidence source: printer_status, printer_readback, c72_scan atau operator_review sesuai kemampuan dan SOP. Jika hardware tidak memberi outcome deterministik, gunakan status unknown dan reconciliation yang disediakan kontrak. C72 proof tidak disebut sebagai native printer readback.

## 4.7 Template dan identitas

Isi label: nomor roll, artikel/SKU, LOT bila relevan, qty/unit sesuai snapshot, EPC display dan barcode yang disetujui. Field internal/customer mengikuti template dan peran; template tidak menampilkan implementasi API/SDK untuk pengguna gudang.

EPC write harus persis nilai kanonik ERP. Tidak ada pemotongan 24 hex atau penggantian ke format lain tanpa kontrak. Byte alignment, memory bank/write command dan media calibration mengikuti SDK/unit terverifikasi, bukan contoh generik yang diasumsikan sama.

Jika roll/qty/template berubah sejak job dibuat, server revision check menentukan validitas. Connector tidak merender ulang dengan data terbaru sambil mempertahankan revision lama. Label QR hanya jenis output terpisah; tidak memenuhi kewajiban RFID. Cetak SJ/logistik memakai flow dokumen/perangkat yang sesuai dan tidak dianggap otomatis menjadi fungsi encoding printer ini.

## 4.8 Gagal cetak dan hasil ambigu

| Kasus | Perilaku yang wajib |
|---|---|
| Offline/paper out sebelum item dikirim | Jangan mulai item; laporkan readiness/error dan queue policy. |
| Encoding failure/VOID jika didukung | Laporkan item failed beserta evidence; label fisik ditangani SOP. |
| Timeout setelah send | UNKNOWN; query outcome/ledger/C72/operator review sebelum resend. |
| Output selesai tetapi result ACK hilang | Kirim result/ACK ulang dengan key/attempt yang sama; jangan resend payload. |
| Lease expired saat print berjalan | Hentikan new work dan reconcile current output; tidak membuka worker kedua. |
| ERP job canceled/revised setelah start | Simpan hasil fisik, laporkan exception dan tangani label sesuai server; tidak menghilangkan bukti. |
| Server menyimpan printed lalu efek lanjutan gagal | Replay result melengkapi unfinished effect idempoten; tidak physical reprint. |
| Update/reboot connector | Restore ledger; SENT/UNKNOWN tidak berubah menjadi READY untuk automatic print. |

## 4.9 Reprint dan re-tag

Retry result transport, cetak ulang teks, dan penggantian chip merupakan operasi berbeda. Masing-masing memperoleh authorization/reason/reference dari ERP. Connector menerima rencana replacement yang sah dan tidak memilih identitas baru sendiri.

Jika EPC sama ditulis pada chip pengganti, tag lama harus ditangani fisik/sistem sesuai SOP agar dua chip aktif dengan nilai sama tidak beredar. Jika EPC diganti, history tag lama-baru dan roll terjaga; guardrail movement aktif tetap berlaku. Unique EPC database sendiri tidak membuktikan hanya satu chip fisik ada.

Reprint tidak menambah stock, mengubah owner, memundurkan journey stored, atau menulis ulang invoice. Label rusak/hilang dengan outcome yang tidak pasti masuk review. TID dapat dipakai sebagai evidence tambahan bila tersedia; tidak mengganti identitas roll/EPC ERP.

## 4.10 Operasi dan serah terima

Service berjalan otomatis melalui runtime host yang disahkan, dengan satu-instance control, bounded recovery, log rotation, config/key provisioning dan protected diagnostics. Printer health, connector heartbeat, queue age dan last confirmed output ditampilkan terpisah.

Install/runbook mencatat SDK/dependency/runtime, endpoint, physical connection, profile media, device registry/capability, template calibration, first-label test dan recovery. Release/rollback tidak membuang output ledger. Kunci/API secret tidak tercetak pada label atau log.

## 4.11 Kriteria penerimaan modul

| ID | Kriteria yang wajib dibuktikan |
|---|---|
| PR-01 | CP30EN/profile/media/command dan actual EPC chip teruji. |
| PR-02 | Routing warehouse/capability/device worker benar. |
| PR-03 | Claim/renew menjaga stable attempt dan lease scope. |
| PR-04 | Print intent durable serta start diterima sebelum hardware send. |
| PR-05 | Sent, printed, encoded dan C72 verified tidak disamakan. |
| PR-06 | Batch parsial mempertahankan outcome per item. |
| PR-07 | Lost ACK/result retry tidak physical reprint. |
| PR-08 | Timeout/crash/expired lease menghasilkan reconciliation yang benar. |
| PR-09 | Reprint/retag menjaga old-new identity, physical tag dan movement guard. |
| PR-10 | Server unfinished effects dipulihkan tanpa duplicate stock/journey. |
| PR-11 | UI/telemetry/template unit/revision/queue serta SOP jelas. |
| PR-12 | Source/service package/SDK map/runbook dan evidence diserahkan. |


## 4.12 Urutan integrasi connector

| Step | Input | Proses dan output |
|---|---|---|
| 1. Service start | Device key, printer profile, local ledger | API-01 memvalidasi config; restore attempts/pending results; periksa SDK/media/readiness. |
| 2. Claim | Stable request key dan capabilities | API-14 memberi jobs/revision/items/payload/lease; job kosong bukan error. |
| 3. Review work | Job/attempt/profile dan exact payload bytes | Cek digest/revision/routing, record local intent; started/sent lama masuk recovery dahulu. |
| 4. Start barrier | Intent ID, item IDs dan digests | API-17 accepted wajib sebelum hardware send; timeout query API-15, tidak blind send. |
| 5. Physical output | Payload/model/media terverifikasi | SDK mengirim print/encode; simpan status/evidence actual; unsupported outcome unknown. |
| 6. Lease | Attempt yang sama dan revision | API-16 renew sesuai policy; expired started output tidak otomatis claim printer lain. |
| 7. Results | Stable result event ID tiap item | API-18 memberi ACK individual dan aggregate; partial/unknown tetap terbuka. |
| 8. Lost ACK/restart | Durable ledger dan pending result | API-15 state query lalu retry result; printer payload tidak dikirim ulang hanya karena HTTP gagal. |
| 9. Reconcile | Supervisor action/note/evidence/item IDs | API-19 menetapkan disposition/reprint/retag plan yang sah; connector menerima job baru jika ada. |
| 10. Verify | Label terpasang pada roll | C72 mengikuti task print_verify; hasil actual chip/tag-roll tersimpan ERP. |

API-03 melaporkan connector/printer/queue health. Satu worker aktif per printer; pembagian paralel antar printer tetap menggunakan routing dan lease terpisah. Timeout jaringan sebelum send berbeda dari timeout sesudah output mungkin terjadi; state ledger menentukan perlakuannya.
