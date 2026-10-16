# Acceptance API dan Middleware Chainway

30 skenario RACC-01–RACC-30 termasuk CP30EN. Semua awal not_run; source inspection bukan bukti hardware sudah lulus.

## RACC-01 — Model dan SDK

**Kebutuhan:** RFID-01

**Hasil yang wajib dibuktikan:** Label UR300, model resmi, firmware, OS dan SDK diverifikasi; C72 varian aktual dicatat; runtime tidak ditebak.

## RACC-02 — Read nyata

**Kebutuhan:** RFID-01, RFID-03, RFID-05

**Hasil yang wajib dibuktikan:** EPC dari tag fisik muncul di callback SDK C72 dan fixed reader; simulator/paste EPC dilabeli terpisah.

## RACC-03 — Identitas dan scope

**Kebutuhan:** RFID-02, RFID-09

**Hasil yang wajib dibuktikan:** Key device valid/invalid/disabled, role operator, wrong warehouse, wrong task dan closed session memberi hasil sesuai otorisasi.

## RACC-04 — Kontrak session dan non-session

**Kebutuhan:** RFID-02, RFID-07

**Hasil yang wajib dibuktikan:** Event_id/captured_at/antenna/RSSI, batas batch, retry, processed=False recovery dan response diuji pada kedua jalur. Jangan menganggap session route setara tanpa tes.

## RACC-05 — Trigger dan lifecycle C72

**Kebutuhan:** RFID-03

**Hasil yang wajib dibuktikan:** Start/stop/suspend/resume/reboot tidak meninggalkan reader aktif atau membuang event/outbox; SDK terpasang cocok dengan module.

## RACC-06 — Verify tag

**Kebutuhan:** RFID-04

**Hasil yang wajib dibuktikan:** Expected vs actual EPC membedakan match/missing/extra; completion tidak memalsukan printing/encoding dan stok tidak bertambah dari scan.

## RACC-07 — Loading dan task context

**Kebutuhan:** RFID-04, RFID-09

**Hasil yang wajib dibuktikan:** Roll hanya memenuhi manifest/task aktif yang dipilih; scan C72 berpindah task tidak masuk sesi lama atau mengonsumsi stok dua kali.

## RACC-08 — RFID opname

**Kebutuhan:** RFID-04, RFID-10

**Hasil yang wajib dibuktikan:** Found/missing/extra/untagged dibanding expected physical scope; laporan RFID tidak otomatis menjadi adjustment qty/jurnal.

## RACC-09 — Putaway alamat

**Kebutuhan:** RFID-04

**Hasil yang wajib dibuktikan:** Bin dibaca/dipilih melalui resolver sah; EPC/RSSI tidak dianggap alamat rak; hold/transit/rules tetap diperiksa ERP.

## RACC-10 — Arah dan logical gate

**Kebutuhan:** RFID-05, RFID-06

**Hasil yang wajib dibuktikan:** Gate in/out, reader multi-port dan sensor/antena diperiksa; satu EPC tidak menjadi bukti arah; mapping lokasi terjaga.

## RACC-11 — Manifest dan passage

**Kebutuhan:** RFID-06

**Hasil yang wajib dibuktikan:** Known-valid, unknown, extra, missing, wrong owner/location, blocked quality dan inactive movement ditangani; partial reads tidak otomatis green final.

## RACC-12 — Dwell dan passage baru

**Kebutuhan:** RFID-06, RFID-07

**Hasil yang wajib dibuktikan:** Tag diam tidak memunculkan bisnis berulang; keluar-masuk atau passage baru dievaluasi kembali; retry transport tetap memakai event_id asli.

## RACC-13 — Indikator fisik

**Kebutuhan:** RFID-05, RFID-06

**Hasil yang wajib dibuktikan:** Lampu/alarm yang didukung mengikuti verdict passage aktual; red tidak ditutupi green tag lain; acknowledgement memerlukan peran sah.

## RACC-14 — Offline dan lost ACK

**Kebutuhan:** RFID-07

**Hasil yang wajib dibuktikan:** Queue bertahan saat jaringan/ERP mati dan proses restart; resend tidak menggandakan effects; kegagalan parsial tidak di-ACK sukses seluruhnya.

## RACC-15 — Backlog dan keputusan basi

**Kebutuhan:** RFID-06, RFID-07

**Hasil yang wajib dibuktikan:** Historical replay hanya direkonsiliasi sesuai kontrak; tidak mengaktifkan lampu hijau atau menganggap shipment lama sebagai izin lewat sekarang.

## RACC-16 — Health dan versi

**Kebutuhan:** RFID-08

**Hasil yang wajib dibuktikan:** Heartbeat sukses tetapi reader gagal/upload gagal ditampilkan berbeda; queue age/version/config tercatat tanpa secret.

## RACC-17 — Rotation/deployment

**Kebutuhan:** RFID-08, RFID-09

**Hasil yang wajib dibuktikan:** Key lama invalid setelah rotation yang sah; service/APK update dan rollback mempertahankan queue serta binding peran/gudang.

## RACC-18 — Kapasitas batch/concurrency

**Kebutuhan:** RFID-02, RFID-07

**Hasil yang wajib dibuktikan:** Batch > limit dipotong client sesuai kontrak, bukan hilang; dua retry dan concurrent sessions tidak mencampur task atau duplikasi record.

## RACC-19 — E2E transfer dan cross-dock

**Kebutuhan:** RFID-10

**Hasil yang wajib dibuktikan:** Stock vs transit routing, actual receipt, tag verification, movement gate dan shipment/SJ konsisten; same-owner/intercompany tidak tercampur.

## RACC-20 — Pilot dan rekonsiliasi

**Kebutuhan:** RFID-10

**Hasil yang wajib dibuktikan:** Unit nyata CP30EN + C72 + UR300 yang tervalidasi menjalani siklus kerja representatif; physical print/encode, EPC/session/passage/qty/owner/dokumen dan recovery cocok pada commit/build tercatat.

## RACC-21 — PoC CP30EN

**Kebutuhan:** RFID-11

**Hasil yang wajib dibuktikan:** Varian/firmware/modul RFID/resolusi/interface/media/SDK aktual tercatat. Payload ERP dicetak dan ditulis pada chip yang benar; C72 membaca EPC tepat. Support keluarga CP30 tidak dianggap bukti seluruh varian.

## RACC-22 — Routing dan concurrent connector

**Kebutuhan:** RFID-12, RFID-09

**Hasil yang wajib dibuktikan:** Job hanya ditarik printer/warehouse/capability yang sesuai; dua connector/heartbeat/polling tidak mengganti attempt aktif atau mencetak job yang sama bersamaan. Lease renewal/reclaim dapat dibedakan.

## RACC-23 — EPC chip dan template

**Kebutuhan:** RFID-13, RFID-15

**Hasil yang wajib dibuktikan:** Label memuat roll/SKU/LOT/qty/unit yang sah; resolusi/ukuran/teks/barcode terbaca. EPC 24 hex chip sama dengan ERP, tidak terpotong atau menulis tag tetangga. QR-only tidak diakui sebagai RFID.

## RACC-24 — Printed, encoded dan verified

**Kebutuhan:** RFID-13, RFID-04

**Hasil yang wajib dibuktikan:** Job sent belum dinyatakan verified. Bukti output/encoding printer serta C72 match/missing/extra tercatat; aktifnya identitas database tidak dianggap verifikasi chip/penempelan fisik.

## RACC-25 — Partial batch dan error

**Kebutuhan:** RFID-12, RFID-13, RFID-14

**Hasil yang wajib dibuktikan:** Batch 10 label dengan 7 sukses dan 3 error/paper out/jam/encode failure. Hanya item yang terbukti berhasil diakui; item gagal/ambigu memiliki status dan PIC. Blank/VOID label ditangani sesuai kemampuan unit/SOP.

## RACC-26 — Lost ACK dan crash

**Kebutuhan:** RFID-14, RFID-07

**Hasil yang wajib dibuktikan:** Putus koneksi/crash sesudah printer menerima/menyelesaikan output tetapi sebelum ACK ERP. Ledger/local/printer/C72 reconciliation membuktikan hasil; ACK diulang tanpa blind reprint atau duplicate physical EPC.

## RACC-27 — Lease expire dan printer offline

**Kebutuhan:** RFID-12, RFID-14

**Hasil yang wajib dibuktikan:** Attempt melebihi TTL, printer kehilangan koneksi, lalu job ditawarkan lagi. Reclaim/renew mempertahankan bukti dan tidak membuat dua printer menghasilkan tag sama; uncertain outcome harus diselesaikan dahulu.

## RACC-28 — Reprint dan retag

**Kebutuhan:** RFID-14, RFID-09

**Hasil yang wajib dibuktikan:** Bedakan retry output belum pasti, label teks rusak dan tag rusak/hilang. Otorisasi/alasan/tag lama/history terjaga; satu roll satu active identity; movement aktif tidak di-bypass; stock dan journey tidak berubah keliru.

## RACC-29 — UI printer dan dokumen

**Kebutuhan:** RFID-15, RFID-08

**Hasil yang wajib dibuktikan:** Antrean/status item/PIC/printer health/attempt/preview/error/C72 proof dapat dibuka. Label internal dan SJ dari gudang pengirim memakai media/perangkat dan sumber data sesuai; CP30EN tidak diasumsikan mencetak semua format dokumen.

## RACC-30 — Recovery setelah ACK server

**Kebutuhan:** RFID-12, RFID-14, RFID-10

**Hasil yang wajib dibuktikan:** Simulasikan job printed durable lalu efek tag/journey on_printed gagal. Retry/recovery melengkapi efek yang belum selesai tanpa mencetak ulang, mengaktifkan tag salah atau menggandakan audit/stock; ledger ERP dan fisik dapat direkonsiliasi.
