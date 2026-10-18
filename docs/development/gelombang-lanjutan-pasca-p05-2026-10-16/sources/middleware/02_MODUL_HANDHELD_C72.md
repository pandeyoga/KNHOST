# 2. Modul Handheld C72 - Spesifikasi Pembuatan

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia  
**Artefak serah terima:** APK release bertanda versi, source Android, SDK profile, konfigurasi dan hasil UAT.

## 2.1 Tujuan dan ruang lingkup

Aplikasi custom berjalan langsung pada C72. SDK Chainway mengendalikan hardware; aplikasi menyediakan pekerjaan operator dan evidence scan ke ERP. Scope: print verification, loading check, RFID cycle count, scan identitas roll untuk tugas alamat, pencarian tag jika SDK mendukung, serta diagnostics/outbox. Perhitungan stock, harga, receipt dan shipment tetap di ERP.

Pencarian tag memakai kualitas sinyal sebagai bantuan relatif. UI tidak menampilkan estimasi posisi rak atau jarak presisi tanpa sistem pengukuran yang telah divalidasi. RFID goods tetap memakai tag; barcode/QR membantu memilih dokumen/bin atau identitas yang diizinkan, bukan fallback otomatis untuk barang wajib RFID.

## 2.2 Stack dan interface adapter

DISARANKAN Android Kotlin dengan interop Java SDK vendor. UI native atau shell yang mereuse halaman ERP dapat dipilih; akses hardware tetap melalui adapter native. Database lokal durable diperlukan, misalnya Room/SQLite sesuai stack yang dikunci. UI thread tidak melakukan loop radio atau HTTP blocking.

Interface internal C72HardwareAdapter: initialize(profile), beginInventory(callback), stopInventory(), readCapabilities(), release(), serta barcodeTrigger/searchTarget jika terbukti didukung. Nama ini bukan method SDK resmi. Tim pengembangan menyerahkan mapping interface-ke-method SDK, dependency/JNI ABI, permission, callback threading dan error codes berdasarkan unit aktual.

SDK dimiliki satu controller; start/stop diserialisasi untuk mencegah dua layar membuka radio sekaligus. Callback vendor segera diubah ke event lokal durable, kemudian diperbarui ke UI melalui stream yang dibatasi agar laju RF tidak membekukan layar.

## 2.3 Komponen aplikasi

| Komponen | Fungsi |
|---|---|
| OperatorSession | Login, expiry, login ulang dan logout sesuai session ERP; tidak mengasumsikan JWT/refresh token. |
| TaskRepository | Daftar pekerjaan dan expected snapshot server. |
| TaskContextManager | Bind device-user-task dan context version. |
| ScanController | Trigger, radio state, context latch dan stop boundary. |
| C72HardwareAdapter | Adapter SDK aktual, barcode dan capability. |
| EvidenceRepository | Observasi asli dan relasi context immutable. |
| UploadCoordinator | Batch/outbox/retry dan event acknowledgement. |
| ScanResultPresenter | Expected/matched/missing/extra dan qty dari ERP. |
| DiagnosticsScreen | Health, queue, version dan export berizin. |

## 2.4 Layar dan navigasi

| Layar | Input utama | Output/tindakan |
|---|---|---|
| Provisioning | QR/config bootstrap yang disahkan dan device key. | Device binding/config tersimpan; tidak membuka akses global. |
| Login operator | Credential melalui mekanisme ERP. | Identitas user serta peran/scope dari server. |
| Daftar pekerjaan | Filter jenis/lokasi/dokumen, sesuai grant. | Task ID, status, expected rollcount, qty/unit dan PIC. |
| Detail pekerjaan | Task yang dipilih. | Dokumen/expected snapshot, tombol mulai scan. |
| Scan pekerjaan | Trigger perangkat/aksi start-stop. | Unique EPC, per-roll detail, matched/missing/extra dan sync state. |
| Review hasil | Hasil server dan pending local evidence. | Lengkapi/koreksi melalui SOP; submit completion. |
| Cari tag | Target EPC/roll yang diizinkan. | Indikator relatif bila SDK mendukung. |
| Outbox/diagnostics | Filter status/umur/error. | Retry transport, quarantine review dan export berizin. |

Qty yard/meter/kg berasal dari detail roll/expected server. Angka tagcount selalu berlabel jumlah tag/roll; tidak disebut sebagai panjang kain. Missing di UI berarti belum terbaca dalam task, bukan bukti otomatis kehilangan stock.

## 2.5 State aplikasi

UNPROVISIONED -> READY -> AUTHENTICATED -> TASK_BOUND -> SCANNING -> REVIEW -> COMPLETION_PENDING -> COMPLETED. SUSPENDED, SYNC_PENDING, AUTH_REQUIRED dan ERROR merupakan state kerja tambahan dengan context yang tetap dapat ditelusuri.

Trigger down memulai inventory hanya jika task/context valid. Trigger up/stop menutup window scan lokal. Double trigger tidak menciptakan sesi radio kedua. Pindah task harus menghentikan radio, menyimpan semua evidence, menutup context lokal, lalu bind task baru; outbox task lama tetap memakai ID lama.

Logout menghentikan operasi user dan tidak menghapus evidence pending. Relogin tidak memindahkan kepemilikan scan lama ke user baru. Completion tidak dibuat dari hitungan lokal saja: seluruh event yang dimaksud harus di-ACK atau direkonsiliasi ERP, kemudian user meminta hasil final dengan idempotency key.

## 2.6 Flow A - Verifikasi hasil cetak CP30EN

1. Operator memilih print job yang ditawarkan ERP; detail memuat roll, EPC expected, status item dan gudang.
2. ERP memberi session/context verifikasi; aplikasi menyimpan snapshot/version.
3. Operator memeriksa label terpasang pada roll yang tepat, lalu membaca dengan C72.
4. Callback SDK membentuk event_id/captured_at/context dan menyimpan evidence sebelum upload.
5. Event dikirim ke kontrak batch; UI menunjukkan provisional lokal terpisah dari hasil server.
6. ERP memberi matched/missing/extra, per-roll detail dan exception. Aplikasi tidak mengaktifkan tag sendiri.
7. Operator review dan complete melalui endpoint task berotorisasi. Hasil final serta bukti tag-roll disimpan ERP.
8. Missing/extra/encode mismatch dikirim ke proses printer exception atau koreksi penempelan, bukan dipaksa clean.

Input: print_job/session/task. Output: verified evidence atau with_issues yang dapat ditindaklanjuti. Teks label yang terlihat benar belum membuktikan chip benar. Pembacaan kumpulan label di meja tidak membuktikan penempelan pada roll.

## 2.7 Flow B - Loading check

Operator memilih task SO/shipment/gudang yang sah. Expected mengacu alokasi fisik serta manifest versi server. Scan actual dibandingkan dengan manifest: EPC asing/roll bukan anggota menjadi extra; roll belum terbaca menjadi missing. Informasi yard/unit/qty aktual dibaca dari ERP.

User review dan complete menghasilkan status loading yang sesuai; shipment/dispatch dijalankan oleh flow ERP yang berwenang. Perubahan manifest saat scan membuat task revision conflict; aplikasi menghentikan completion, refresh/reconcile, dan menjaga evidence versi lama. App tidak membuat override untagged/missing hanya karena operator menekan selesai.

## 2.8 Flow C - RFID opname

Task menentukan lokasi/gudang/bin scope dan owner yang diizinkan. ERP menyediakan expected physical tagged rolls serta informasi untagged. C72 sweep menyetor bukti; hasil server menunjukkan found/missing/extra/untagged. User complete menghasilkan laporan opname RFID.

Hasil itu tidak otomatis mengubah length/qty atau jurnal. Koreksi lokasi, penyesuaian qty dan approval mengikuti modul stock opname. UI mempertahankan distinction read recall/tag coverage/selisih; scan 100% tag tidak diklaim sebagai pengukuran ukuran kain.

## 2.9 Flow D - Identitas dan putaway

Operator memilih tugas, membaca roll/tag, membaca atau memilih alamat bin, dan meninjau target dari server. Aplikasi meminta mutasi bisnis pada tugas yang sesuai; ERP memeriksa owner, lokasi, status fisik, QC, rules dan kapasitas.

Evidence scan dan permintaan mutasi berhubungan melalui correlation/context ID tetapi merupakan operasi terpisah. Retry scan tidak memindahkan barang kedua kali. Nomor bin berasal dari registry alamat ERP; RSSI tidak mengisi bin_id.

## 2.10 Persistence, offline dan concurrency

Tabel lokal: device_config, operator_session_ref, task_snapshot, scan_context, observations, outbox_events, diagnostic_events. Unique event ID dan payload digest mencegah pengiriman berubah saat retry. Expected snapshot adalah cache read-only, bukan replika stock master yang ditulis mandiri.

Offline capture hanya untuk task/context yang server izinkan melalui policy. Tunjukkan data belum sinkron; completion bisnis tetap menunggu acceptance/otorisasi server. Expired context atau task canceled saat reconnect menjadi exception yang direview, bukan dipindahkan otomatis ke sesi baru.

Upload tidak menahan trigger/UI. Queue cap serta local write failure menunjukkan error nyata; event tidak dihitung uploaded jika belum durable. Repeated RF observations dibedakan dari unique EPC matched count. Source manual/simulated/device tetap dipertahankan.

## 2.11 Lifecycle dan deployment

Reader dihentikan/dilepas pada boundary yang benar saat task selesai, user logout atau app dihentikan. Pending data bertahan setelah proses mati/reboot/update. Scheduling retry dan foreground operation mengikuti OS/target SDK yang diuji; manifest/permission tidak disalin dari contoh yang berbeda generasi.

Distribusi APK mengikuti metode internal yang disahkan. Release mencatat package ID, signing identity, app/build/SDK/firmware matrix dan local DB schema version. Update tidak menghapus outbox; rollback memakai migration compatibility atau recovery yang dibuktikan.

## 2.12 Kriteria penerimaan modul

| ID | Kriteria yang wajib dibuktikan |
|---|---|
| HH-01 | Provisioning dan login terikat device/user/site yang benar. |
| HH-02 | Trigger/lifecycle SDK stabil pada unit nyata dan layar tidak freeze. |
| HH-03 | Setiap task mempertahankan context, version dan expected scope. |
| HH-04 | Print verify membuktikan EPC dan hubungan tag-roll dengan C72. |
| HH-05 | Loading membedakan matched/missing/extra dan manifest berubah. |
| HH-06 | Opname tidak auto-post qty/jurnal; unit dan metrik tetap jelas. |
| HH-07 | Putaway memakai bin/rules server dan mutasi idempoten. |
| HH-08 | Offline/logout/reboot/update menjaga evidence dan tidak menukar user/task. |
| HH-09 | Retry/partial ACK/quarantine tidak menggandakan effect. |
| HH-10 | Completion memakai approval/context/version server, bukan counter lokal. |
| HH-11 | Pencarian tag menunjukkan bantuan relatif sesuai capability. |
| HH-12 | APK, source, mapping SDK, runbook dan hasil hardware diserahkan. |


## 2.13 Urutan integrasi per layar

| Step / layar | Input | Proses dan output |
|---|---|---|
| 1. Provisioning | Base URL, key, profile unit | API-01 mengambil config/binding; verifikasi profile supported, simpan version. |
| 2. Login | Email/password operator | AUTH-01/02 memberi session, user, permissions/entity context; tampilkan hanya scope yang sah. |
| 3. Pekerjaan | Kind, warehouse, source ref | API-07 list atau API-08 create dari dokumen sah; task ID/version dan expected totals tersedia. |
| 4. Detail | Task ID/version | API-09/10 mengambil header dan seluruh expected pages; cache snapshot pin version. |
| 5. Mulai scan | Task/version dan device key | API-12 memberi context user-device-task; SDK start hanya setelah context valid. |
| 6. Trigger | Callback EPC/time/metadata | Persist event/context -> API-02 -> durable per-event ACK; UI provisional terpisah dari server. |
| 7. Review | Task/version/cursor | API-11 memberi matched/missing/extra/pending dan qty/unit; row totals mengikuti summary authoritative. |
| 8. Putaway | Code bin dan selected roll IDs | API-20 resolve hierarchy/eligibility; simpan bin/location version untuk review. |
| 9. Selesai | Context/version, allowed action/data | API-13 memvalidasi dan commit sesuai kind; hasil completed/with_issues/downstream refs ditampilkan. |
| 10. Logout | Session aktif | AUTH-03; stop user operation; outbox/context lama tetap untuk evidence. |

Print verify memakai source_type print_job. Loading memakai manifest/task shipment yang sudah dialokasikan; bukan SO qty global yang belum dipilih roll. Cycle count memakai count plan scope. Putaway memakai pekerjaan receipt/putaway sah. Tag search memakai plan/target yang berizin. Nama source_type dan allowed_actions disediakan registry business task ERP; app tidak mengonversi seluruh jenis menjadi satu scan bebas.

Pada setiap langkah, error 401 meminta login ulang, 403 menghentikan work di luar scope, 409 meminta review versi/context, dan transport timeout hanya retry dengan ID yang sama. Data provisional diberi label belum tersinkron/menunggu proses; tidak dicampur dengan metrik final.
