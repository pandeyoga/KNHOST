# Tracker RFID Chainway

Sumber status: RFID_BACKLOG.json. Ubah JSON lalu render ulang. Kondisi awal belum diimplementasikan/diuji.

| ID | Kebutuhan | Tahap | Status | Commit implementasi / verifikasi | Evidence / issue |
|---|---|---|---|---|---|
| RFID-01 | Identitas perangkat, firmware, SDK dan PoC nyata | RF00 | not_started | — / — | — |
| RFID-02 | Kontrak API ERP dan compatibility seluruh jalur ingest | RF01 | not_started | — / — | — |
| RFID-03 | Aplikasi Android C72 dengan adapter SDK | RF02 | not_started | — / — | — |
| RFID-04 | Workflow C72: verifikasi tag, loading, opname dan alamat | RF02 | not_started | — / — | — |
| RFID-05 | Adapter fixed reader UR300 dan kontrol lokal | RF03 | not_started | — / — | — |
| RFID-06 | Gate passage, arah dan kelengkapan manifest | RF03 | not_started | — / — | — |
| RFID-07 | Outbox offline, deduplikasi dan replay terkontrol | RF01 | not_started | — / — | — |
| RFID-08 | Device health, deployment dan operasi middleware | RF01 | not_started | — / — | — |
| RFID-09 | Identitas operator, scope dan traceability | RF01 | not_started | — / — | — |
| RFID-10 | UAT perangkat nyata dan integrasi seluruh rantai WMS | RF04 | not_started | — / — | — |
| RFID-11 | Profil CP30EN, firmware, koneksi, media dan PoC encoding | RF00 | not_started | — / — | — |
| RFID-12 | Printer connector, routing job, lease dan attempt | RF-P | not_started | — / — | — |
| RFID-13 | Cetak label, tulis EPC dan bukti hasil per item | RF-P | not_started | — / — | — |
| RFID-14 | Gagal cetak, hasil ambigu, reprint dan penggantian tag | RF-P | not_started | — / — | — |
| RFID-15 | Antarmuka printer, template dan jejak operasional per gudang | RF-P | not_started | — / — | — |

## Tahap

| RF | Judul | Status | Dependensi |
|---|---|---|---|
| RF00 | PoC perangkat dan pemetaan SDK | not_started | P00 |
| RF01 | API ERP dan fondasi middleware | not_started | RF00, P01 |
| RF02 | Aplikasi dan workflow C72 | not_started | RF01, P02 |
| RF03 | Adapter gate UR300 dan passage | not_started | RF01, P02, P03 |
| RF-P | Connector CP30EN, print-encode, verifikasi dan recovery | not_started | RF00, RF01, RF02, P02 |
| RF04 | E2E hardware, pilot dan penutupan integrasi | not_started | RF02, RF03, RF-P, P03, P04, P08 |

## Pengujian

| RACC | Skenario | Hasil | Evidence |
|---|---|---|---|
| RACC-01 | Model dan SDK | not_run | — |
| RACC-02 | Read nyata | not_run | — |
| RACC-03 | Identitas dan scope | not_run | — |
| RACC-04 | Kontrak session dan non-session | not_run | — |
| RACC-05 | Trigger dan lifecycle C72 | not_run | — |
| RACC-06 | Verify tag | not_run | — |
| RACC-07 | Loading dan task context | not_run | — |
| RACC-08 | RFID opname | not_run | — |
| RACC-09 | Putaway alamat | not_run | — |
| RACC-10 | Arah dan logical gate | not_run | — |
| RACC-11 | Manifest dan passage | not_run | — |
| RACC-12 | Dwell dan passage baru | not_run | — |
| RACC-13 | Indikator fisik | not_run | — |
| RACC-14 | Offline dan lost ACK | not_run | — |
| RACC-15 | Backlog dan keputusan basi | not_run | — |
| RACC-16 | Health dan versi | not_run | — |
| RACC-17 | Rotation/deployment | not_run | — |
| RACC-18 | Kapasitas batch/concurrency | not_run | — |
| RACC-19 | E2E transfer dan cross-dock | not_run | — |
| RACC-20 | Pilot dan rekonsiliasi | not_run | — |
| RACC-21 | PoC CP30EN | not_run | — |
| RACC-22 | Routing dan concurrent connector | not_run | — |
| RACC-23 | EPC chip dan template | not_run | — |
| RACC-24 | Printed, encoded dan verified | not_run | — |
| RACC-25 | Partial batch dan error | not_run | — |
| RACC-26 | Lost ACK dan crash | not_run | — |
| RACC-27 | Lease expire dan printer offline | not_run | — |
| RACC-28 | Reprint dan retag | not_run | — |
| RACC-29 | UI printer dan dokumen | not_run | — |
| RACC-30 | Recovery setelah ACK server | not_run | — |
