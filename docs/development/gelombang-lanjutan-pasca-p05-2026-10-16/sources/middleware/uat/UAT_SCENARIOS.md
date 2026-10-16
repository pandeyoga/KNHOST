# Skenario UAT

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia

Semua 48 skenario mulai **not_run**. Lengkapi versi server, client build, profile hardware/SDK, actual, evidence, reviewer dan issue. Input di bawah adalah fixture pengujian yang disiapkan QA, bukan data production.

## HH-01

**Input/prasyarat:** Akun gudang A; device terikat A; task warehouse B.

**Langkah:** Provision, login, buka task A; coba pilih task B.

**Expected:** A sesuai izin; B ditolak tanpa memindah scope device.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-02

**Input/prasyarat:** C72 aktual, SDK/firmware tercatat; trigger fisik dan tag known.

**Langkah:** Scan berulang, stop, screen-off/resume; periksa thread/UI.

**Expected:** Satu owner SDK, tidak freeze/double callback; lifecycle state jelas.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-03

**Input/prasyarat:** Dua task/version/operator berbeda.

**Langkah:** Bind task pertama, scan, switch sesuai rule dan bind berikutnya.

**Expected:** Event lama mengacu context pertama; expected dan progress tidak tercampur.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-04

**Input/prasyarat:** Print job tag-roll; satu label salah EPC atau salah pemasangan.

**Langkah:** Baca chip dengan C72; review matched/missing/extra dan roll label.

**Expected:** Correct tag-roll verified; salah atau belum terbaca tetap issue.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-05

**Input/prasyarat:** Manifest 10 roll serta satu tag extra; server revises manifest.

**Langkah:** Scan subset/extra; ubah manifest lalu minta complete.

**Expected:** Matched/missing/extra jelas; stale version conflict tanpa clean dispatch.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-06

**Input/prasyarat:** Count plan dengan qty/unit dan missing/untagged.

**Langkah:** Sweep, repeat tag, review lalu complete count evidence.

**Expected:** Unique tag count benar; bukan auto qty/journal adjustment; discrepancies tersimpan.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-07

**Input/prasyarat:** Putaway task; valid bin serta bin wrong rule/capacity.

**Langkah:** Resolve barcode, scan selected rolls, commit; retry same key.

**Expected:** Valid alamat satu mutasi; invalid ditolak; lokasi bukan hasil RSSI.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-08

**Input/prasyarat:** Pending outbox; authorized offline context.

**Langkah:** Disconnect, scan, logout, reboot/update, login user lain dan reconnect.

**Expected:** Evidence/context asli bertahan; expired context tidak auto complete sebagai user lain.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-09

**Input/prasyarat:** Partial ACK serta response lost untuk batch yang sama.

**Langkah:** Upload; retry unacknowledged records dengan event ID sama.

**Expected:** ACKed event tidak resent; pending/quarantine terlihat; satu business effect per event.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-10

**Input/prasyarat:** Local counter clean, server processing pending/with_issues.

**Langkah:** Review server progress dan tekan complete.

**Expected:** Completion/dispatch mengikuti eligibility/version server; local counter tidak memaksa.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-11

**Input/prasyarat:** Known target EPC dan unknown/non-RFID roll.

**Langkah:** Buka tag search plan, baca RSSI jika SDK mendukung.

**Expected:** Bantuan relatif sesuai capability; tidak mengklaim jarak/bin pasti.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## HH-12

**Input/prasyarat:** Release APK/source/profile/runbook dan evidence.

**Langkah:** Fresh install build tercatat, ulang satu flow hardware dan recovery.

**Expected:** Build reproducible, SDK mapping nyata, artifact dan evidence lengkap.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-01

**Input/prasyarat:** UR300 Android terpasang APK, ERP network; semua PC/laptop dilepas.

**Langkah:** Boot, screen-off, baca tag, upload dan terapkan verdict sah.

**Expected:** Reader bekerja langsung tanpa gateway PC atau handheld penghubung.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-02

**Input/prasyarat:** Actual OS/SDK/ABI/permissions/power policy.

**Langkah:** Init SDK; reboot; process kill dan force-stop dibedakan.

**Expected:** Autostart/recovery yang didukung terbukti; manual recovery exception terdokumentasi.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-03

**Input/prasyarat:** Two logical gates/antenna-sensor mapping dan arah.

**Langkah:** Lewat dua arah/dua scope; periksa event metadata/context.

**Expected:** Arah/gate scope tepat; RSSI tidak menjadi direction authority.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-04

**Input/prasyarat:** Tag diam, passage selesai, re-entry tag sama.

**Langkah:** Ulang baca stationary lalu keluar/masuk pada boundary baru.

**Expected:** Noise tidak membuat passage ganda; re-entry memperoleh passage ID baru.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-05

**Input/prasyarat:** Network lost ACK, process death setelah durable local capture.

**Langkah:** Persist event, upload, kill/restart dan resend.

**Expected:** ID/captured/context tetap; tidak kehilangan pending data atau duplicate effects.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-06

**Input/prasyarat:** Fresh live authorized final green; stale/final=false/mismatched response.

**Langkah:** Kirim close setelah ACK barrier; inject tiap response kondisi.

**Expected:** Indikator green hanya final/live/current/valid; semua kondisi lain sesuai review policy.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-07

**Input/prasyarat:** Red latch satu gate serta supervisor ack yang stale.

**Langkah:** Picu red, tampilkan keputusan berikutnya, coba wrong/stale latch ack lalu sah.

**Expected:** Red dominan; stale ack ditolak; sah ack tidak menghasilkan green historis.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-08

**Input/prasyarat:** Manifest/full/subset/per_epc policies; missing/unknown.

**Langkah:** Uji tiap policy dengan tag subset/extra lalu close.

**Expected:** Counts/basis jelas; full missing tidak clean; unread bukan bukti physical absence.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-09

**Input/prasyarat:** Offline passages dan backlog serta server jam/response delayed.

**Langkah:** Capture offline, passage baru, reconnect dan replay backfill.

**Expected:** Historical evidence tersimpan; tidak live green untuk replay/response lama.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-10

**Input/prasyarat:** Outbox hampir penuh, disk error, reboot/update.

**Langkah:** Inject persistence failure lalu restart/update dengan queue pending.

**Expected:** Alarm/stop capture sesuai policy; evidence pending utuh; tidak silently drop.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-11

**Input/prasyarat:** Radio off sementara network online; ERP down sementara radio ready.

**Langkah:** Baca telemetry/dashboard untuk masing-masing kondisi.

**Expected:** Radio/ERP/queue/SDK/lifecycle dipisahkan; online bukan hardware healthy.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## RD-12

**Input/prasyarat:** Signed APK/source/SDK map/config and no-PC runbook.

**Langkah:** Deploy fresh dan ulang reader live/offline/no-PC.

**Expected:** Artifact/profile/evidence perangkat nyata dan SOP exception lengkap.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-01

**Input/prasyarat:** CP30EN aktual dengan media RFID/ribbon/profile/SDK.

**Langkah:** Calibrate, print/encode satu known EPC lalu baca chip C72.

**Expected:** Text/media/EPC exact dan physical outcome terbukti pada profil tersebut.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-02

**Input/prasyarat:** Dua connector/printer warehouses berbeda; job RFID vs QR.

**Langkah:** Claim secara concurrent, capability mismatch dan second worker.

**Expected:** Satu pemilik attempt sesuai scope/capability; salah printer tidak menerima work.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-03

**Input/prasyarat:** Claim active attempt; retry claim dan renew.

**Langkah:** Replay same key, poll state, renew lalu cek attempt/expiry.

**Expected:** Attempt stabil, lease valid; renew tidak menghasilkan physical output baru.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-04

**Input/prasyarat:** Durable intent, ERP start timeout/conflict.

**Langkah:** Record intent, coba start tanpa ACK lalu terima start sah.

**Expected:** Tidak send sebelum accepted; digest/item/revision match dan intent dapat dipulihkan.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-05

**Input/prasyarat:** Spool ACK, physical print/encode status, C72 verification.

**Langkah:** Bandingkan status di tiap tahap termasuk hardware tanpa deterministic status.

**Expected:** Sent tidak confirmed; printed/encoded/verified terpisah; unavailable evidence unknown.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-06

**Input/prasyarat:** 10 items: 7 confirmed, 2 failed, 1 unknown.

**Langkah:** Report result batch dan inspect job/item/tag states.

**Expected:** Partial/needs_review; hanya outcome sah diterapkan; tidak whole-job success.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-07

**Input/prasyarat:** Physical output selesai; result response sengaja hilang.

**Langkah:** Restart connector dan kirim result event yang sama.

**Expected:** Satu output fisik; duplicate result safe; ledger tidak resend printer payload.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-08

**Input/prasyarat:** Crash setelah send; expired lease saat output in progress.

**Langkah:** Restart/poll/reconcile; start second worker setelah expiry.

**Expected:** Started output tidak otomatis reassign/reprint; unknown dipertahankan hingga resolution.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-09

**Input/prasyarat:** Reprint text vs retag; old chip dan movement aktif.

**Langkah:** Ajukan kedua tindakan dengan reason/evidence; uji movement guard.

**Expected:** Trace old/new identity, old chip SOP, authorized plan; qty/owner tidak berubah.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-10

**Input/prasyarat:** Result persisted, failure sebelum tag/journey effect.

**Langkah:** Fault injection ERP lalu replay result.

**Expected:** Unfinished effects dipulihkan tepat; tidak duplicate stock/journey/output.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-11

**Input/prasyarat:** Job qty yard/kg, template revision, queue backlog/status.

**Langkah:** Review UI/telemetry/label dan cancelled/revised job.

**Expected:** Unit/template/context tepat; no silent rerender revision lama; operator SOP jelas.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## PR-12

**Input/prasyarat:** Service package/source/profile/media/runbook.

**Langkah:** Fresh host install, first-label test, reboot/recovery dan rollback.

**Expected:** Build dapat direproduksi; ledger tidak hilang; hardware evidence lengkap.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-01

**Input/prasyarat:** Satu roll actual ERP dan chip kosong.

**Langkah:** Print+encode CP30EN, pasang label, verify C72, cek relation ERP.

**Expected:** EPC/tag-roll/qty/unit konsisten; database identity bukan physical proof.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-02

**Input/prasyarat:** SO manifest loading, source/warehouse valid.

**Langkah:** C72 loading -> server review -> reader passage -> authorized dispatch.

**Expected:** Manifest/version/roll actual tepat; raw scan tidak post shipment sendiri.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-03

**Input/prasyarat:** Transfer Bandung ke Jakarta; planned receipt/putaway/cross-dock.

**Langkah:** Dispatch sumber, gate evidence, actual receipt tujuan, bin/transit dan delivery.

**Expected:** Owner/location/in-transit history konsisten; penerimaan tidak hanya dari tag gate.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-04

**Input/prasyarat:** Inventory plan plus physical discrepancies.

**Langkah:** Sweep C72, review, approved adjustment terpisah, dashboard comparison.

**Expected:** Counts vs qty jelas; satu approved effect dan journal; totals sesuai detail.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-05

**Input/prasyarat:** Satu reader dengan dua logical gates berizin.

**Langkah:** Lintaskan tag/context untuk masing-masing gate dan arah.

**Expected:** Verdict/latch/direction/warehouse tidak tertukar.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-06

**Input/prasyarat:** Offline dengan pending observations dan new live task/passage.

**Langkah:** Reboot/reconnect/drain queue sambil live capture berpolicy.

**Expected:** History backfill utuh; no stale live clearance or task reassignment.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-07

**Input/prasyarat:** Printer output selesai, result ACK lost.

**Langkah:** Retry/restart/query/reconcile hasil.

**Expected:** One physical output, idempotent result recovery; tidak blind resend.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-08

**Input/prasyarat:** Partial print/encode dan mismatched C72 scan.

**Langkah:** Laporkan per-item; verify evidence; gate checks movement.

**Expected:** Issue tetap terbuka dan tidak clean manifest karena header job sukses.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-09

**Input/prasyarat:** Manifest/config revision, session expiry/key rotation.

**Langkah:** Update resource/identity saat scanning/attempt; review stale requests.

**Expected:** New scope/version enforced; evidence asli tetap dan stale complete ditolak.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-10

**Input/prasyarat:** Pending queues/ledgers pada ketiga runtime.

**Langkah:** Rolling update, reboot dan rollback tanpa PC reader.

**Expected:** Migration/recovery tidak kehilangan data atau resend output ambigu.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-11

**Input/prasyarat:** Server event/result durable tetapi effects pending.

**Langkah:** Inject failure setelah persistence, retry/recovery dan audit downstream.

**Expected:** Effect selesai sekali; evidence/result tetap; no duplicate posting/print.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

## INT-12

**Input/prasyarat:** Tag rusak/hilang dengan active movement.

**Langkah:** Authorized reprint/retag, old chip action, verify baru dan gate.

**Expected:** Identity history/movement consistency dan physical duplicates ditangani.

**Status:** not_run. Actual/evidence diisi pada UAT_TRACKER.csv.

