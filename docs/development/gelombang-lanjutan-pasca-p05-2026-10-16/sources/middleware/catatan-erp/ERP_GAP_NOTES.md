# Catatan Penyelarasan ERP - Pendamping Terpisah

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia  
**Tanggal:** 13 Oktober 2026  
**Snapshot source yang diperiksa:** f59b8a60d7b7e078888c537ca93c046afae460a9  
**Lokasi snapshot lokal:** work/KNHOST-guide-2026-10-07  
**Metode:** inspeksi source integrasi RFID; bukan pemeriksaan deployment terbaru atau uji perangkat nyata.

## Aturan penggunaan

Dokumen ini hanya untuk tim ERP/integrasi. Manual middleware memperlakukan kontrak target lengkap sebagai tersedia sesuai arahan pemilik project. Dokumen ini tidak dimasukkan PDF manual dan tidak mengarahkan tim pengembangan membuat fallback API atau mengubah arsitektur reader menjadi PC gateway.

Sebelum implementasi ERP, bandingkan lagi commit aktif terhadap target contract karena repo mungkin telah berubah setelah snapshot tersebut. Status semua butir di sini adalah perlu sinkronisasi pada commit aktif; tidak dianggap regresi baru yang sudah direproduksi pada production.

## Pemetaan yang perlu diselaraskan

| ID | Basis source snapshot | Kondisi yang terlihat | Target dan dampak |
|---|---|---|---|
| ERP-MW-01 | backend/routers/rfid.py:550; backend/services/rfid_ingest_service.py:118 | /api/rfid/ingest tersedia dengan key; belum berupa envelope v2/context/mode/ACK per event yang ditetapkan paket. | API-02: preserve raw/captured/antenna/RSSI/event ID; ACK durable individual dan pending processing; task/gate scope. |
| ERP-MW-02 | backend/routers/rfid.py:551; backend/services/rfid_ingest_service.py:296 | Branch session mengambil daftar EPC lalu masuk shared scan_session; metadata event_id/captured_at/antenna/RSSI tidak diteruskan seperti branch ingest umum. MAX_EVENTS berada di normalizer branch umum. | Samakan validasi/limits/dedup/evidence pada kedua jalur; jangan menghapus event metadata ketika task context dipakai. |
| ERP-MW-03 | backend/services/rfid_ingest_service.py:103,131 | Passage memakai processing time/window dan direction device. captured_at disimpan sebagai metadata; tidak menjadi pembeda replay historical vs live. | API-01/04/05: logical_gate/antenna/sensor/direction profile, stable local passage, mode live/backfill, explicit close/completeness dan time validity. Backlog tidak menghasilkan izin live sekarang. |
| ERP-MW-04 | backend/routers/rfid.py:361,378; backend/services/rfid_ingest_service.py:241 | Gate status dan acknowledgement tersedia pada user routes, latch/TTL telah ada. | Device-scoped API-04 untuk agent; API-05 final decision; API-06 user ack latch ID dan passage yang tepat. Jangan memberi reader credential admin sebagai workaround. |
| ERP-MW-05 | backend/routers/rfid.py:539,561; backend/services/rfid_ingest_service.py:57,74 | Key hashing/auth dan heartbeat tersedia; heartbeat menandai online. | API-01 config/profile/version/policies serta API-03 radio/printer/transport/queue/build/clock telemetry; online tidak dianggap radio atau printer healthy. |
| ERP-MW-06 | backend/routers/rfid.py:476,495,637; backend/services/rfid_print_service.py:299,327 | Print verify/cycle count dan shared session sudah ada, tetapi generic task/context/expected paging/progress/completion v2 belum ditemukan di router ini. | API-07..13: wrap business services yang sah, permissions dan user-device-task binding; jangan duplikasi stock/opname/dispatch service. |
| ERP-MW-07 | backend/routers/rfid.py:412; WMS hierarchy/putaway services | Daftar lokasi RFID tersedia. Endpoint resolver task-scoped persis target API-20 belum ada pada router RFID snapshot. | Resolve stable bin ID, hierarchy lemari/rak, location version, rule eligibility; completion revalidate scope/status/capacity. Crosscheck WMS existing sebelum membuat service baru. |
| ERP-MW-08 | backend/routers/rfid.py:568; backend/services/rfid_ingest_service.py:319 | GET pending melakukan mutasi lease; same device dapat claim ulang dengan attempt_id baru dan increment attempt. | API-14 POST claim idempoten; stable attempt, API-15 state query, API-16 renew; repoll tidak mengubah attempt yang sedang aktif. |
| ERP-MW-09 | backend/routers/rfid.py:576; backend/services/rfid_ingest_service.py:343 | ACK header job dengan attempt; belum memuat durable physical start intent dan hasil setiap item. | API-17/18: start barrier, payload digest/revision, printed/encoded/unknown per item, partial summary, output started tidak otomatis direassign karena lease expired. |
| ERP-MW-10 | backend/services/rfid_ingest_service.py:354,365,372; backend/services/rfid_print_service.py:204 | Status printed disimpan sebelum on_printed; replay job printed dengan attempt yang sama return lebih awal. Kegagalan di efek lanjutan perlu recovery terpisah. | Durable result + unfinished effect ledger/reconciliation; replay melengkapi tag/journey tanpa physical print lagi. Verifikasi dengan fault injection pada commit aktif. |
| ERP-MW-11 | backend/services/rfid_print_service.py:47,130,204 | Payload ZPL RFID dan pending tag DB ada; on_printed mengaktifkan tag/journey. Itu bukan bukti chip ditulis atau tag terpasang pada roll yang benar. | Capability/media/template profile CP30EN, per-item evidence, verify C72; unsupported status = unknown. DB encoding tetap identitas, physical encoding bukti lain. |
| ERP-MW-12 | backend/services/rfid_print_service.py:216; backend/routers/rfid.py:466 | Manual mark-printed tersedia; schema job ACK tidak menyediakan structured uncertain/reconciliation plan persis target. | API-19 authorized reconciliation dengan item/attempt/revision/evidence/reason; reprint text, retag dan transport replay terpisah; old physical chip dan active movement guarded. |

## Hal yang dapat dipakai kembali

Device registry dan key hashing/auth, scope warehouse, raw observation dedup/reprocessing unfinished, red latch, print queue/lease, print verify, loading-check dan opname merupakan fondasi. Tidak perlu menghapusnya hanya karena contract v2 memakai path berbeda. Adapter server dapat menggunakan existing services setelah semantics, consistency dan recovery diuji.

User auth menggunakan opaque session token, login/logout dan /api/auth/me pada backend/routers/auth.py:86,150,170. Native app memakai Bearer fallback yang didukung; tidak membutuhkan JWT refresh service baru secara otomatis.

## Checklist validator ERP

1. Catat actual commit/environment, inventory route/service/data migration dan hasil diff target.
2. Validasi scope user/device/site/warehouse/owner untuk semua task, printer job dan logical gate.
3. Uji malformed envelope, limit, duplicate/pending event, metadata task, partial ACK dan interrupted processing.
4. Uji live/backfill, passage re-entry, direction, full/subset/per-EPC policy, stale response dan latch acknowledge.
5. Uji stable claim, renew/start barrier, started lease expiry, partial outcomes, lost result ACK dan failure setelah status persisted.
6. Pastikan qty/unit, location rules, stock/journal dan shipment tetap satu sumber business service; scan tidak membuat posting ganda.
7. Jalankan compatibility OpenAPI serta 36 criteria/12 integration scenarios bersama unit aktual.

Catatan ini adalah daftar pekerjaan integrasi dan risiko berdasarkan snapshot; semua UAT tetap not_run sampai ada evidence aktual. Source inspection tidak menggantikan test fisik atau status fix pada commit aktif.
