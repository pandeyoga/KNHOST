# Development Plan API dan Middleware RFID Chainway

**Tanggal:** 12 Oktober 2026. **Baseline kode yang dibaca:** `f59b8a60d7b7e078888c537ca93c046afae460a9`; verifikasi ulang branch aktual sebelum implementasi.

## 1. Kesimpulan dan posisi pekerjaan

API RFID di sisi ERP sudah mempunyai fondasi ingest, device authentication, session, gate evaluation dan health. Belum ditemukan aplikasi Android/adaptor Chainway berupa project Gradle, Kotlin/Java, AAR atau APK pada snapshot repo. Ketiadaan itu membatasi bukti dalam repo ini; bukan pernyataan tidak ada aplikasi vendor atau repo lain.

Paket plan sebelumnya berfokus pada 35 kebutuhan ERP/WMS dan fingerprint. Integrasi SDK, aplikasi C72, serta service gate perlu pekerjaan eksplisit dalam addendum ini. Middleware berarti software penerjemah/pengendali perangkat; tidak otomatis berarti PC/laptop tambahan atau produk middleware vendor berbayar.

## 2. Hardware dan lokasi menjalankan middleware

| Perangkat | Arsitektur yang dituju | Hal yang harus dibuktikan |
|---|---|---|
| C72 | Aplikasi Android pada handheld → SDK RFID → persistent queue → HTTPS API ERP. Tidak perlu PC sebagai perantara harian. | Varian OS/module/SDK aktual, trigger/lifecycle, APK, jaringan dan task operator. |
| UR300 yang disebut pengguna | Adapter reader pada unit jika runtime mendukung; jika tidak, host edge lokal dengan SDK yang tepat. ERP tetap menerima lewat API yang sama. | Label/model resmi, OS/SDK, installability, port/antenna, GPIO/trigger dan operasi unattended. |
| CP30EN | Print connector menjangkau printer lewat interface unit yang terverifikasi dan menarik job dari ERP. Lokasi runtime mengikuti SDK serta rute jaringan nyata. | Profil keluarga CP30, firmware/modul RFID, resolusi, media/inlay, command language, hasil encoding dan readback. |
| ERP | Identitas tag/roll, session, manifest/movement, rules, keputusan bisnis, histori dan tampilan pekerjaan. | API/UI serta stok/dokumen memakai sumber yang sama. |

Dokumentasi resmi [C72](https://chainway.net/Products/Info/42) menyebut Android dan SDK Chainway. Halaman resmi yang ditemukan untuk fixed reader bernama [U300](https://chainway.net/Products/Info/146), menyebut Android 11 serta SDK; ini belum membuktikan UR300 pengguna sama dengan U300. Pencocokan label/firmware adalah gate RF00. Jika unit ternyata cocok dan mendukung pemasangan aplikasi, adapter dapat dijalankan pada reader; kebutuhan kotak edge tambahan tidak otomatis berlaku.

Pengguna menetapkan printer **CP30EN**. [Dukungan resmi keluarga CP30](https://www.chainway.net/support/Info/30) menyediakan Windows_ZPL SDK dan ZPL_Linux SDK. Nama CP30EN dipertahankan; label varian dan kemampuan aktual diuji sebelum memilih driver/protokol. [Rencana printer](PRINTER_CP30EN_PLAN.md) menjelaskan runtime, API, encoding, partial failure dan C72 verification.

## 3. Pembagian tanggung jawab

**Reader/SDK** melakukan RF inventory dan menyediakan EPC/metadata sesuai kemampuan unit. **Middleware** mengendalikan trigger/antena, membentuk event, menyimpan outbox, mengirim API, menerima hasil dan mengendalikan indikator yang didukung. **ERP** memetakan EPC ke roll, memeriksa task/owner/lokasi/dokumen, memberi keputusan, dan menjalankan stok melalui flow bisnis sah.

Pembacaan EPC bukan bukti qty yard/berat, rak, kepemilikan, atau seluruh muatan sudah terbaca. Posisi resmi berasal dari transaksi alamat; RSSI hanya bantuan pembacaan/pencarian relatif. Gate mendeteksi lintasan, sedangkan receipt/dispatch/opname tetap mengikuti dokumen dan otorisasi. Indikator hijau bukan pengganti pembuktian kelengkapan manifest yang disepakati.

## 4. Kebutuhan tambahan

### RFID-01 — Identitas perangkat, firmware, SDK dan PoC nyata

**Tahap utama:** RF00

Catat UR300 sesuai nama pengguna dan cocokkan label/datasheet ke model resmi. C72 juga dicatat OS/module/SDK aktual; dua model bernama sama dapat mempunyai generasi berbeda. Buktikan pembacaan EPC asli dan profil runtime, jaringan, antena, trigger/GPIO jika digunakan.

**Bukti selesai:** PoC kedua unit dengan SDK asli, record model/firmware dan EPC yang benar-benar terbaca; brosur atau simulator tidak cukup.

### RFID-02 — Kontrak API ERP dan compatibility seluruh jalur ingest

**Tahap utama:** RF01

Pertahankan endpoint existing; dokumentasikan API device dan operator terpisah, metadata event, batas batch, scope, status sesi, receipt/response, versioning dan backward compatibility. Pemeriksaan jalur session harus mencakup metadata/idempotensi/limit, bukan mengasumsikan sama dengan ingest umum.

**Bukti selesai:** Contract tests untuk non-session dan session, valid/invalid device, batch, retry, incomplete processing dan legacy payload.

### RFID-03 — Aplikasi Android C72 dengan adapter SDK

**Tahap utama:** RF02

Aplikasi pada C72 mengendalikan radio melalui SDK unit aktual: trigger start/stop, EPC/RSSI jika tersedia, scanner lifecycle, power/profile, dan pencarian target bila SDK mendukung. SDK demo bukan aplikasi produksi. Gunakan shell tugas ringkas; UI ERP dapat direuse dengan bridge terbatas atau UI native sesuai hasil desain.

**Bukti selesai:** APK terpasang pada C72 aktual membaca tag tanpa PC; trigger, suspend/resume, koneksi serta task UI diuji.

### RFID-04 — Workflow C72: verifikasi tag, loading, opname dan alamat

**Tahap utama:** RF02

Operator memilih pekerjaan/sesi yang sah, melihat expected/scanned/missing/extra, lalu review/complete dengan hak operator. Read device dikirim lewat /api/rfid/ingest sebagai bukti device. QR/bin scan untuk putaway memakai alamat dan validator ERP; RFID read sendiri tidak menentukan rak, panjang, berat, atau stock adjustment.

**Bukti selesai:** Input-output task cocok dengan dokumen/roll/alamat; sesi di gudang lain ditolak; pengurangan/penerimaan stok hanya melalui flow bisnis yang sah.

### RFID-05 — Adapter fixed reader UR300 dan kontrol lokal

**Tahap utama:** RF03

Jika unit yang diverifikasi mendukung aplikasi Android terpasang, adapter berjalan di reader. Jika runtime/SDK memerlukan host, jalankan service edge lokal yang sesuai; jangan menjanjikan tanpa host untuk model yang belum terverifikasi. Baca antena, trigger, health dan kendalikan lampu/alarm bila hardware/SDK mendukung.

**Bukti selesai:** Service berjalan unattended setelah boot/restart, pembacaan serta kontrol indikator dibuktikan pada reader dan instalasi nyata.

### RFID-06 — Gate passage, arah dan kelengkapan manifest

**Tahap utama:** RF03

Direction mengikuti konfigurasi gate/logical zone yang dipercaya. Jangan menebak arah dari satu pembacaan EPC/RSSI. Jika reader melayani in/out, petakan port/sensor ke logical gate sesuai PoC. Pisahkan observasi, passage, verdict dan physical handoff; bandingkan konteks dokumen serta expected barang untuk passage tersebut.

**Bukti selesai:** Unknown/wrong warehouse/not in manifest/missing/hold/replay ditangani; pembacaan beberapa EPC valid belum otomatis membuktikan seluruh muatan lengkap.

### RFID-07 — Outbox offline, deduplikasi dan replay terkontrol

**Tahap utama:** RF01

Simpan event sebelum kirim dengan event_id stabil, captured_at, context dan metadata. Retry memakai ID sama; duplicate RF dalam satu passage berbeda dari kiriman ulang transport. Reconnect memproses backlog tanpa memicu lampu hijau untuk lintasan historis. Kontrak replay baru harus disepakati server-client, bukan field yang diam-diam diabaikan.

**Bukti selesai:** Offline, restart, lost ACK, partial failure, stale decision dan backlog tidak menggandakan event bisnis atau memalsukan izin lewat saat ini.

### RFID-08 — Device health, deployment dan operasi middleware

**Tahap utama:** RF01

Catat reader connected, ERP reachable, last contact, last successful upload, SDK/app/firmware version, local queue/errors dan antenna health jika tersedia. Heartbeat tidak membuktikan pembacaan/pengiriman tag berhasil. Siapkan provisioning, key rotation, release APK/service, watchdog dan rollback.

**Bukti selesai:** Kegagalan SDK/jaringan antrean terlihat; restart pulih; perubahan versi/konfigurasi dapat ditelusuri dan tidak membuang outbox.

### RFID-09 — Identitas operator, scope dan traceability

**Tahap utama:** RF01

API key mengidentifikasi perangkat, sedangkan user session mengotorisasi pekerjaan dan completion. Simpan pelaksana, device, site/warehouse, session/movement, EPC/roll, timestamps dan versi client. C72 mobile dapat berpindah tugas/gudang hanya melalui binding yang sah; jangan melepas scope dengan field warehouse bebas.

**Bukti selesai:** Perangkat sah tidak otomatis berwenang semua task; role dan lokasi diuji di server; scan manual/simulated/device tetap dibedakan.

### RFID-10 — UAT perangkat nyata dan integrasi seluruh rantai WMS

**Tahap utama:** RF04

Integrasikan ERP, CP30EN, C72 dan UR300 terhadap printing/encoding, tag verification/loading/transfer/putaway/cross-dock/opname dan gate. Uji dengan roll, tag, dokumen, layout antena, media label dan kondisi operasi representatif. Catat batas daya baca dan SOP checker; tidak mengklaim 100% hanya dari simulator.

**Bukti selesai:** Evidence actual print/encode, raw read, response ERP, indikator gate, chain dokumen, qty/owner/tag/alamat dan recovery diverifikasi pada commit/build yang tercatat.

### RFID-11 — Profil CP30EN, firmware, koneksi, media dan PoC encoding

**Tahap utama:** RF00

Model printer telah dipilih pengguna: CP30EN. Catat label/varian dan hubungannya dengan keluarga CP30 resmi, serial, firmware, modul RFID, resolusi, command language/SDK, interface dan media tag aktual. Validasi ZPL/encoding/readback serta kalibrasi; tidak mengasumsikan semua emulasi ZPL atau suffix EN mempunyai kemampuan yang sama.

**Bukti selesai:** CP30EN nyata menghasilkan label dan EPC chip yang sesuai payload ERP serta dapat dibaca C72. SDK/dokumentasi dan konfigurasi printer/media tercatat; tidak cukup dengan cetak teks EPC.

### RFID-12 — Printer connector, routing job, lease dan attempt

**Tahap utama:** RF-P

Bangun connector ke CP30EN sesuai SDK/protokol dan jaringan aktual. Gunakan antrean ERP per gudang/capability, claim/lease/attempt_id, jurnal lokal per attempt dan item, status perangkat serta hasil yang dapat ditelusuri. Printer tidak diasumsikan dapat menjalankan aplikasi Android atau polling API sendiri.

**Bukti selesai:** Dua connector tidak memproses attempt aktif bersamaan; polling/lease renewal tidak mengganti attempt_id pekerjaan yang sedang dicetak. Routing warehouse/type benar dan connector tidak memakai hak admin untuk job harian.

### RFID-13 — Cetak label, tulis EPC dan bukti hasil per item

**Tahap utama:** RF-P

Pisahkan identitas EPC di database, rendered label, payload sent, hasil print/encode yang terkonfirmasi dan physical read verification. EPC chip tepat sama dengan EPC kanonik ERP; isi label berasal dari snapshot roll yang sah dengan qty/satuan jelas. Dukung hasil parsial dan VOID/error jika firmware menyediakannya.

**Bukti selesai:** Job dengan beberapa item sukses dan satu gagal tidak diakui berhasil seluruhnya. QR-only tidak memenuhi kewajiban RFID. C72 membandingkan expected vs scanned dan bukti tag yang terpasang sebelum downstream flow yang memerlukannya.

### RFID-14 — Gagal cetak, hasil ambigu, reprint dan penggantian tag

**Tahap utama:** RF-P

Tangani paper/ribbon out, jam, encoding error, offline, crash, timeout, expired lease, lost ACK dan server side-effect failure. Hasil fisik yang belum pasti masuk reconciliation, bukan blind reprint. Bedakan label belum jadi, penggantian label tampak dan penggantian tag RFID; tag lama diamankan/dinonaktifkan secara fisik dan sistem sesuai SOP.

**Bukti selesai:** Retry ACK tidak mencetak ulang; timeout tidak mengaktifkan duplicate physical EPC. Re-tag mempertahankan histori dan satu identitas aktif per roll serta memeriksa movement aktif. Reprint tidak menambah stock atau memundurkan journey roll tersimpan.

### RFID-15 — Antarmuka printer, template dan jejak operasional per gudang

**Tahap utama:** RF-P

Sediakan antrean per printer/gudang, preview/jenis label, item status, alasan gagal/ambigu, operator, attempt dan verifikasi C72. Template mengikuti ukuran/resolusi unit, teks, barcode dan qty/unit yang sah. Pisahkan label RFID/QR dari cetak dokumen SJ; tidak mengasumsikan CP30EN adalah printer A4 untuk seluruh dokumen.

**Bukti selesai:** Admin gudang dapat menindak job/exception serta menelusuri roll-tag-job-attempt-verification. Isi template tidak membuat master/stock baru; kebutuhan cetak SJ tetap tersedia dari gudang pengirim melalui printer dokumen yang sesuai.

## 5. Tahap implementasi

| Tahap | Fokus | Kebutuhan utama | Dependensi |
|---|---|---|---|
| [RF00](prompts/RF00.md) | PoC perangkat dan pemetaan SDK | RFID-01, RFID-11 | P00 |
| [RF01](prompts/RF01.md) | API ERP dan fondasi middleware | RFID-02, RFID-07, RFID-08, RFID-09 | RF00, P01 |
| [RF02](prompts/RF02.md) | Aplikasi dan workflow C72 | RFID-03, RFID-04 | RF01, P02 |
| [RF03](prompts/RF03.md) | Adapter gate UR300 dan passage | RFID-05, RFID-06 | RF01, P02, P03 |
| [RF-P](prompts/RF-P.md) | Connector CP30EN, print-encode, verifikasi dan recovery | RFID-12, RFID-13, RFID-14, RFID-15 | RF00, RF01, RF02, P02 |
| [RF04](prompts/RF04.md) | E2E hardware, pilot dan penutupan integrasi | RFID-10 | RF02, RF03, RF-P, P03, P04, P08 |

RF00 dimulai bersama P00 agar SDK/runtime diketahui sejak awal. RF01 sesudah P01; RF02/RF03 menggunakan alamat dan rules P02, sedangkan gate movement lintas gudang membutuhkan P03. RF04 melengkapi UAT P10 setelah flow bisnis serta dashboard/opname yang relevan stabil. Tidak harus menunggu semua domain selesai untuk memulai PoC hardware.

PoC CP30EN ikut RF00; kontrak printer/lease/hasil ikut RF01. Tahap RF-P menyelesaikan connector, encoding, UI dan recovery setelah fondasi serta C72 siap. Driver dan template dapat dipersiapkan lebih awal pada bagian yang independen. RF04 menunggu RF-P; printer merupakan bagian wajib scope perangkat ini.

## 6. Keputusan yang belum final

- Pencocokan label UR300/U300, OS/firmware/SDK dan akses dua unit; pengguna sudah memastikan nama UR300 dan C72, tetapi label serta generasi belum dibaca langsung.
- Jumlah gate, layout antena, arah satu/dua jalur, trigger/sensor, lampu/alarm, barang per passage, serta SOP completeness/exception/offline.
- Binding C72 ke lokasi/gudang/operator dan scope owner yang diizinkan; device key tidak menggantikan hak user.
- Profil CP30EN, firmware, koneksi, media, aturan reprint/retag/penanganan output ambigu serta printer per gudang. Model sudah dipilih; parameter ini tidak diasumsikan dari nama saja.
- Jaringan ERP, rollout/pilot, SLA/latensi operasional yang disepakati, serta izin instalasi aplikasi pada unit.

Client/schema dapat disiapkan selama menunggu keputusan, tetapi perilaku produksi baru tidak boleh diaktifkan dengan aturan fiktif. Jangan menjanjikan scan 100% dari datasheet; bukti pilot harus memakai layout, tag dan roll representatif.

## 7. Evidence dan definition of done

Status normal: not_started → in_progress → implemented_pending_validation → validated. waiting_decision/waiting_hardware/reopened digunakan per item. Catat commit server, build/APK/service, SDK/firmware profile, input/output API, actual EPC, UI, indikator fisik, offline/retry dan rekonsiliasi. Semua acceptance awal not_run.

Selesai ketika CP30EN, C72 dan UR300 nyata berjalan melalui ERP, middleware dan task yang benar; physical print/encode serta raw observations/reads/passage/session/roll/dokumen terhubung; output ambigu direkonsiliasi dan tidak dicetak ulang membabi buta; scope/recovery serta RF04/P10 tervalidasi. Simulator/paste EPC tidak menjadi bukti hardware. Rencana ini belum merupakan implementasi APK/connector, pengujian unit atau sertifikasi deployment terbaru.
