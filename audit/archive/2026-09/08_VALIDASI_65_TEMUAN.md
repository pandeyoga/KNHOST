# Review lanjutan Astra — validasi 65 temuan

Tanggal review: 29 September 2026. Snapshot: `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Snapshot sengaja sama dengan audit awal agar validasi dapat dibandingkan; ini **bukan pernyataan bahwa main GitHub terbaru telah diaudit**.

Dokumen ini mengoreksi interpretasi audit Sol. “Valid” berarti jalur kode mendukung cacat yang dijelaskan dengan prasyarat yang disebutkan; bukan berarti cacat sudah terjadi pada database produksi. “Diperjelas” mempersempit klaim atau menjelaskan kontrol yang sudah ada. “Dikoreksi sebagian” menarik bagian klaim yang tidak benar/terlalu kuat. “Gap” memerlukan keputusan desain/policy dan tidak boleh dihitung sebagai bug universal.

Pengujian baru mengeksekusi badan fungsi asli dalam model dependensi terkontrol. Uji itu bukan MongoDB, HTTP end-to-end, hardware, atau browser. Rujukan pengujian: [12 — bukti dan batas verifikasi](12_BUKTI_VALIDASI_FLOW.md). Rincian lama tetap di [01 — audit awal](01_TEMUAN_AUDIT_KNHOST.md); apabila bertentangan, gunakan koreksi di dokumen ini.

## Register keputusan

| ID | Keputusan review | Fokus |
|---|---|---|
| [RF-01](#rf-01) | Valid | Format EPC database berbeda dari EPC yang ditulis ke chip |
| [RF-02](#rf-02) | Valid | Gate OUT menganggap status sebagai izin keluar |
| [RF-03](#rf-03) | Diperjelas | Gate IN menerima transit di gudang mana pun |
| [RF-04](#rf-04) | Gap bersyarat | Final Loading Check belum menjadi prasyarat dispatch |
| [RF-05](#rf-05) | Valid | Loading Check clean walaupun sebagian roll tidak punya tag |
| [RF-06](#rf-06) | Valid | Hasil loading melekat pada SO, tidak pada versi shipment aktual |
| [RF-07](#rf-07) | Valid | Tombol simulasi dapat mengisi bukti verifikasi operasional |
| [RF-08](#rf-08) | Valid | Sesi dan histori Cycle Count RFID tidak terisolasi entitas |
| [RF-09](#rf-09) | Valid | Cycle count lintas entitas dibuat tetapi tidak dapat dipindai |
| [RF-10](#rf-10) | Valid | Mesin sesi bersama tidak memvalidasi jenis sesi dan kehilangan scan konkuren |
| [RF-11](#rf-11) | Valid | Payload ZPL dan custom EPC tidak divalidasi aman |
| [RF-12](#rf-12) | Valid | Daftar device membocorkan API key hardware |
| [RF-13](#rf-13) | Diperjelas | Device dinonaktifkan masih diterima autentikasi |
| [RF-14](#rf-14) | Valid | Lifecycle cetak mengklaim tag tercetak terlalu dini dan retry verifikasi buntu |
| [RF-15](#rf-15) | Valid | Antrean printer tidak memiliki claim dan ack tidak membatasi tipe device |
| [RF-16](#rf-16) | Gap integrasi | Ingest belum mempunyai event identity, passage window dan deduplikasi lintas batch |
| [RF-17](#rf-17) | Diperjelas | Definisi stok fisik RFID berbeda dari SSOT dan metrik count mengabaikan extra |
| [WM-01](#wm-01) | Valid | Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil |
| [WM-02](#wm-02) | Gap desain | Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik |
| [WM-03](#wm-03) | Valid | Konfirmasi tiba dengan scan kosong memindahkan semua roll |
| [WM-04](#wm-04) | Valid | Putaway antar-gudang in-transit tidak mengubah bucket stok roll |
| [WM-05](#wm-05) | Valid | PA dapat berebut roll dan arrival menulis lokasi tanpa prasyarat roll |
| [WM-06](#wm-06) | Valid | Scan picking tidak memvalidasi identitas roll dan menerima qty negatif |
| [WM-07](#wm-07) | Valid | Stock opname per bin memakai expected seluruh gudang dan membolehkan duplikasi |
| [WM-08](#wm-08) | Valid | Adjustment shortage dapat parsial tetapi sesi tetap approved |
| [WM-09](#wm-09) | Valid | Penerimaan exception PA tidak menulis mutasi transfer |
| [FN-01](#fn-01) | Diperjelas | Landed cost menghitung anak split dua kali |
| [FN-02](#fn-02) | Valid | 3-way match lolos overbilling dari baris produk duplikat |
| [FN-03](#fn-03) | Diperjelas | WAC menjumlah panjang dan cost lintas unit tanpa konversi |
| [FN-04](#fn-04) | Valid | Arus kas seimbang tetapi klasifikasi transaksi nonkas salah |
| [FN-05](#fn-05) | Valid | Master akun laporan menggabungkan override entitas dengan last-write-wins |
| [FN-06](#fn-06) | Valid | Jurnal manual menolak akun custom entitas dan mengabaikan override |
| [FN-07](#fn-07) | Diperjelas | Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal |
| [FN-08](#fn-08) | Valid | Opening balance rekening dan perubahan rekening tidak tersambung GL |
| [FN-09](#fn-09) | Valid | Void jurnal manual melewati penguncian periode |
| [FN-10](#fn-10) | Valid | Pembayaran AR dapat sukses walau jurnal kas gagal |
| [FN-11](#fn-11) | Diperjelas | HPP per shipment memakai rata-rata semua roll pesanan |
| [FN-12](#fn-12) | Valid | Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan |
| [FN-13](#fn-13) | Valid | Close periode dapat berjalan dua kali secara bersamaan |
| [FN-14](#fn-14) | Dikoreksi sebagian | Stock opname tidak memposting variance GL dan surplus dibuat tanpa cost |
| [FN-15](#fn-15) | Gap kontrol | Helper autopost tidak menegakkan invariant jurnal di pintu insert |
| [FN-16](#fn-16) | Valid | Neraca default tidak membatasi tanggal meski diberi label hari ini |
| [GN-01](#gn-01) | Valid | Idempotency tidak terikat user cookie, entitas dan payload |
| [GN-02](#gn-02) | Valid | WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope |
| [GN-03](#gn-03) | Valid | Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen |
| [GN-04](#gn-04) | Valid | R&D dapat mengambil bahan dari roll badan usaha lain |
| [GN-05](#gn-05) | Valid | Rollback pengambilan bahan R&D dapat menimpa pemakaian roll lain |
| [GN-06](#gn-06) | Valid | Produksi menyelesaikan WO tanpa claim dan memakai BOM terbaru |
| [GN-07](#gn-07) | Valid | Retur supplier mengurangi roll dengan read-set dan partial return kehilangan identitas fisik |
| [GN-08](#gn-08) | Valid | Konversi permintaan internal dapat melahirkan transaksi antar-PT ganda |
| [GN-09](#gn-09) | Valid | CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID |
| [GN-10](#gn-10) | Valid | Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global |
| [GN-11](#gn-11) | Diperjelas | Saga release menghapus lock tanpa mengecek efek yang sudah terposting |
| [GN-12](#gn-12) | Valid | Agregasi kritis berhenti pada batas to_list tanpa penanda truncation |
| [GN-13](#gn-13) | Valid | Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit |
| [GN-14](#gn-14) | Dikoreksi sebagian | Audit log selalu before=None dan source secrets tersimpan dalam repo publik |
| [GN-15](#gn-15) | Gap pemeliharaan | Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten |
| [HR-01](#hr-01) | Valid | PPh21 memakai TER bahkan pada masa pajak terakhir |
| [HR-02](#hr-02) | Diperjelas | Lembur memakai multiplier flat dan dua sumber menit berpotensi tumpang tindih |
| [HR-03](#hr-03) | Valid | Persetujuan cuti tidak mengecek ulang saldo dan cuti lintas tahun salah pembebanan |
| [MK-01](#mk-01) | Valid | Input metrik marketing parsial mengganti seluruh metrik sebelumnya |
| [UX-01](#ux-01) | Valid | Gate kiosk menampilkan hasil lama sebagai LIVE dan tidak mengagregasi satu passage |
| [UX-02](#ux-02) | Valid | Unduhan ZPL lewat tautan tidak membawa konteks entitas yang dipilih |
| [GN-16](#gn-16) | Diperjelas | Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas |
| [UX-03](#ux-03) | Valid | Panel biaya OCR menampilkan ID entitas mentah |

## Penjelasan per temuan

<a id="rf-01"></a>

### RF-01 — Valid

**Klaim awal:** Format EPC database berbeda dari EPC yang ditulis ke chip.

**Hasil validasi:** Encoding, ZPL, ingest, dan verifikasi tidak memiliki representasi EPC canonical bersama. Raw hex dari payload ZPL tidak ditemukan oleh lookup exact-string. Middleware yang sengaja mengubah format dapat menutupi gejala, tetapi kontrak backend tetap rapuh. Jangan mengubah panjang EPC berdasarkan asumsi 96-bit tanpa memeriksa kapasitas tag dan encoding identifier yang dipilih.

**Dasar pembuktian:** V2-01: encode → ZPL → ingest fungsi asli; raw=red, format tersimpan=info.

**Lokasi kode:** [backend/services/rfid_service.py:43](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L43); [backend/services/rfid_print_service.py:43](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L43); [backend/services/rfid_ingest_service.py:99](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L99).

<a id="rf-02"></a>

### RF-02 — Valid

**Klaim awal:** Gate OUT menganggap status sebagai izin keluar.

**Hasil validasi:** Masalah melampaui daftar status yang terlalu longgar. PA OUT diperiksa sebelum blok quarantine dan tidak mewajibkan PA aktif; roll quarantine dengan PA cancelled memperoleh green. Izin keluar harus berasal dari manifest aktif dan QC release, bukan journey atau bucket stok.

**Dasar pembuktian:** V2-02; diperkuat telaah cabang fallback OUT dan pembanding simulator.

**Lokasi kode:** [backend/services/rfid_ingest_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L78); [backend/services/rfid_service.py:32](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L32).

<a id="rf-03"></a>

### RF-03 — Diperjelas

**Klaim awal:** Gate IN menerima transit di gudang mana pun.

**Hasil validasi:** Jangan membaca judul lama sebagai semua gate IN selalu salah. Cabang PA aktif memang menolak gudang tujuan yang salah. Defek berada pada fallback transit tanpa resolusi dokumen tujuan. Pagar yang sudah benar harus dipertahankan.

**Dasar pembuktian:** V2-C2 menghasilkan red untuk PA aktif ke gudang salah; cabang fallback transit ditelaah dan reproduksi RF-03 lama tetap relevan.

**Lokasi kode:** [backend/services/rfid_ingest_service.py:65](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L65).

<a id="rf-04"></a>

### RF-04 — Gap bersyarat

**Klaim awal:** Final Loading Check belum menjadi prasyarat dispatch.

**Hasil validasi:** Tidak ada loading check berarti dispatch diizinkan. Ini bertentangan dengan target operasi Anda jika RFID wajib, tetapi bukan bug universal untuk gudang yang sah memakai proses manual. Buat policy per warehouse/flow, prasyarat bukti, serta override berotorisasi dengan alasan. Jangan memaksa semua historical order mempunyai RFID.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/loading_check_service.py:104](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L104).

<a id="rf-05"></a>

### RF-05 — Valid

**Klaim awal:** Loading Check clean walaupun sebagian roll tidak punya tag.

**Hasil validasi:** Untagged_count dicatat, tetapi expected hanya berisi tag aktif dan clean hanya membandingkan missing/extra. Satu dari dua roll tanpa tag dapat diabaikan sampai guard dispatch. Label BERSIH harus mengacu pada semua barang fisik dalam shipment.

**Dasar pembuktian:** V2-04: untagged=1, result=clean, dispatch allowed.

**Lokasi kode:** [backend/services/loading_check_service.py:56](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L56); [backend/services/loading_check_service.py:77](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L77).

<a id="rf-06"></a>

### RF-06 — Valid

**Klaim awal:** Hasil loading melekat pada SO, tidak pada versi shipment aktual.

**Hasil validasi:** SO terlalu luas sebagai identitas bukti loading. Partial shipment, perubahan alokasi, potong roll, pindah gudang atau cetak ulang dapat membuat bukti lama tidak berlaku. Dispatch bahkan memilih ulang roll dan dapat menciptakan child baru. Ikat bukti ke shipment_id, manifest_version, roll-version, dan tag-binding-version.

**Dasar pembuktian:** V2-08 dan V2-13, ditambah telaah loading_check pada SO.

**Lokasi kode:** [backend/services/loading_check_service.py:54](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L54); [backend/services/loading_check_service.py:84](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L84); [backend/services/loading_check_service.py:93](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L93).

<a id="rf-07"></a>

### RF-07 — Valid

**Klaim awal:** Tombol simulasi dapat mengisi bukti verifikasi operasional.

**Hasil validasi:** Tombol simulasi pada panel loading memasukkan expected EPC ke endpoint scan operasional. Risiko ada pada asal bukti, bukan larangan simulator untuk pengembangan. Backend wajib menyimpan evidence_origin dan menolak simulated evidence untuk release produksi; menyembunyikan tombol saja tidak cukup.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [frontend/src/features/rfid/CycleCountPanel.jsx:67](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/CycleCountPanel.jsx#L67); [frontend/src/features/rfid/RfidPrintVerifyPanel.jsx:244](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidPrintVerifyPanel.jsx#L244); [frontend/src/features/wms/LoadingCheckPanel.jsx:79](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/wms/LoadingCheckPanel.jsx#L79).

<a id="rf-08"></a>

### RF-08 — Valid

**Klaim awal:** Sesi dan histori Cycle Count RFID tidak terisolasi entitas.

**Hasil validasi:** Scope sesi count yang sedang terbuka dan histori count tidak setara dengan scope inventori pembentuk expected. Warehouse bersama dapat membocorkan count lintas pemilik. Pagar start warehouse dan permission modul tidak menggantikan pemeriksaan pemilik sesi/detail/completion.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/cycle_count_service.py:22](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L22); [backend/services/cycle_count_service.py:53](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L53); [backend/services/cycle_count_service.py:111](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L111).

<a id="rf-09"></a>

### RF-09 — Valid

**Klaim awal:** Cycle count lintas entitas dibuat tetapi tidak dapat dipindai.

**Hasil validasi:** Count multi-owner dibentuk dengan owner_entity_id=None, sementara scan bersama memerlukan owner tersebut berada dalam scope. Gunakan daftar scope immutable pada sesi atau pisahkan sesi per owner. Jangan memperbaiki dengan menganggap None berarti boleh untuk semua.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/cycle_count_service.py:44](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L44); [backend/services/rfid_print_service.py:214](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L214).

<a id="rf-10"></a>

### RF-10 — Valid

**Klaim awal:** Mesin sesi bersama tidak memvalidasi jenis sesi dan kehilangan scan konkuren.

**Hasil validasi:** Dua cacat berbeda: read–union–set menghilangkan scan konkuren; complete_verify menerima kind sesi lain dan dapat menulis tag_verified pada roll dari cycle count. Claim status open tidak menyelesaikan masalah tipe sesi maupun snapshot progress sebelum claim.

**Dasar pembuktian:** V2-05: count selesai tanpa report, journey berubah; V2-06: dua scan diterima tetapi hanya satu tersimpan.

**Lokasi kode:** [backend/services/rfid_print_service.py:219](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L219); [backend/services/rfid_print_service.py:236](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L236).

<a id="rf-11"></a>

### RF-11 — Valid

**Klaim awal:** Payload ZPL dan custom EPC tidak divalidasi aman.

**Hasil validasi:** Data yang masuk ke bahasa printer harus diperlakukan sebagai field, bukan command. Validasi EPC serta escape/encode field ZPL dan batasi ukuran. Reproduksi string hanya menunjukkan payload command dapat terbentuk; tidak membuktikan model printer tertentu menjalankan semua command tersebut.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/rfid_print_service.py:43](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L43); [backend/services/rfid_print_service.py:52](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L52); [backend/services/rfid_service.py:122](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L122).

<a id="rf-12"></a>

### RF-12 — Valid

**Klaim awal:** Daftar device membocorkan API key hardware.

**Hasil validasi:** list_devices mengembalikan API key; menyembunyikan tombol di frontend tidak menghapus secret dari respons. Pisahkan data inventory device, enrollment, dan rotasi secret; tampilkan secret hanya pada penerbitan sesuai izin.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/rfid_service.py:197](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L197); [backend/routers/rfid.py:304](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L304).

<a id="rf-13"></a>

### RF-13 — Diperjelas

**Klaim awal:** Device dinonaktifkan masih diterima autentikasi.

**Hasil validasi:** Fixture lama yang memakai status disabled tidak sesuai enum aplikasi. Jalur nyata UI Matikan mengirim offline; authenticate tetap menerima key dan heartbeat mengubahnya online. Defek tetap valid sebagai kontrak UI/backend. Pisahkan enabled/revoked dari last_seen/health.

**Dasar pembuktian:** V2-03 memakai offline yang benar-benar dikirim UI, lalu authenticate → heartbeat menghasilkan online.

**Lokasi kode:** [backend/services/rfid_ingest_service.py:35](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L35).

<a id="rf-14"></a>

### RF-14 — Valid

**Klaim awal:** Lifecycle cetak mengklaim tag tercetak terlalu dini dan retry verifikasi buntu.

**Hasil validasi:** queued langsung mengubah journey menjadi tag_printed, dan verified_with_issues tidak bisa memulai ulang lewat start_verify. Ada masalah lebih luas: reprint menimpa journey operasional, lalu verification dapat membuat roll tampak siap PA lagi. Status media label harus terpisah dari status perpindahan stok.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/rfid_print_service.py:20](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L20); [backend/services/rfid_print_service.py:189](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L189).

<a id="rf-15"></a>

### RF-15 — Valid

**Klaim awal:** Antrean printer tidak memiliki claim dan ack tidak membatasi tipe device.

**Hasil validasi:** Polling queued jobs tanpa lease memungkinkan pengiriman job yang sama ke beberapa printer. ACK hanya terikat warehouse tidak cukup untuk identitas device/kind/attempt. Exactly-once physical printing tidak bisa dijamin hanya unique DB key; timeout cetak perlu keadaan uncertain dan verifikasi/reprint terkendali.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/rfid_ingest_service.py:144](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L144); [backend/services/rfid_ingest_service.py:153](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L153).

<a id="rf-16"></a>

### RF-16 — Gap integrasi

**Klaim awal:** Ingest belum mempunyai event identity, passage window dan deduplikasi lintas batch.

**Hasil validasi:** Backend yang terlihat menerima daftar EPC, waktu server, dan dedup dalam batch; belum ada kontrak passage/event/replay yang memadai. Middleware Kotlin/reader adapter tidak ditemukan dalam repo ini. Jangan mengklaim edge pasti tidak ada di lapangan, atau wajib menyimpan setiap raw read di DB utama. Minta kontrak edge dan buktikan idempotensi serta evidence lintasan.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/rfid_ingest_service.py:98](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L98); [backend/services/rfid_ingest_service.py:110](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L110).

<a id="rf-17"></a>

### RF-17 — Diperjelas

**Klaim awal:** Definisi stok fisik RFID berbeda dari SSOT dan metrik count mengabaikan extra.

**Hasil validasi:** Metric accuracy=found/expected tidak menghukum extra, tetapi result with_issues memang memperhitungkan extra. Jadi bukan semua hasil count mengabaikan extra. Daftar status taggable, physical-at-site, allocatable, dan countable boleh berbeda secara sah; yang salah adalah semantik tidak eksplisit dan penerapan yang tidak sesuai lokasi fisik.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/rfid_service.py:21](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L21); [backend/services/cycle_count_service.py:80](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L80).

<a id="wm-01"></a>

### WM-01 — Valid

**Klaim awal:** Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil.

**Hasil validasi:** CAS pengurangan parent diikuti normalisasi $set memakai snapshot lama. Dua split 30 dan 40 dapat mengubah total 100 menjadi 140. Jalur sequential dengan snapshot baru tetap 100; jangan menganggap semua split selalu salah. Insert child juga membutuhkan jaminan recovery jika gagal setelah parent berubah.

**Dasar pembuktian:** V2-07 interleaving terkontrol; V2-C1 kontrol sequential.

**Lokasi kode:** [backend/services/roll_service.py:490](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L490); [backend/services/roll_service.py:508](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L508).

<a id="wm-02"></a>

### WM-02 — Gap desain

**Klaim awal:** Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik.

**Hasil validasi:** Reservasi virtual dapat sah dalam WMS, tetapi tidak boleh ditampilkan sebagai physical child yang sudah ada dan membutuhkan tag sebelum pemotongan. Kode memberi nomor roll anak, menghilangkan tag, dan memperlakukannya sebagai stok fisik. Pisahkan reservation segment dari physical roll/cut confirmation; ini penting untuk satu tag per roll pada proyek Anda.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/roll_service.py:490](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L490); [backend/services/roll_service.py:523](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L523).

<a id="wm-03"></a>

### WM-03 — Valid

**Klaim awal:** Konfirmasi tiba dengan scan kosong memindahkan semua roll.

**Hasil validasi:** Daftar scan kosong ditafsirkan sebagai semua item datang. Jika bisnis membutuhkan manual receive, gunakan command/permission terpisah dengan bukti dan alasan, bukan [] yang ambigu. Konfirmasi PA open juga perlu kebijakan jelas jika keberangkatan belum dicatat.

**Dasar pembuktian:** V2-10: [] menghasilkan arrived_count=1 dan warehouse W2.

**Lokasi kode:** [backend/services/putaway_order_service.py:177](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L177); [backend/services/putaway_order_service.py:180](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L180).

<a id="wm-04"></a>

### WM-04 — Valid

**Klaim awal:** Putaway antar-gudang in-transit tidak mengubah bucket stok roll.

**Hasil validasi:** Dispatch PA mengubah journey tetapi tidak mengeluarkan roll dari bucket tersedia di gudang asal. Akibatnya barang yang sedang dibawa masih dapat dipilih order lain. Status movement harus menentukan availability, bukan kosmetik timeline.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/putaway_order_service.py:154](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L154); [backend/services/putaway_order_service.py:160](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L160).

<a id="wm-05"></a>

### WM-05 — Valid

**Klaim awal:** PA dapat berebut roll dan arrival menulis lokasi tanpa prasyarat roll.

**Hasil validasi:** Claim pada dokumen PA tidak melindungi roll dari transaksi lain. Arrival menulis roll berdasarkan id tanpa memastikan owner, asal, status, versi atau kuantitas snapshot. Fixture stale menunjukkan ledger memakai owner A/100 sementara roll aktual B/70 dipindah. Ini uji prasyarat service, bukan bukti bahwa owner selalu berubah melalui UI PA.

**Dasar pembuktian:** V2-11; telaah create/dispatch/arrival dan saga parent.

**Lokasi kode:** [backend/services/putaway_order_service.py:129](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L129); [backend/services/putaway_order_service.py:192](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L192).

<a id="wm-06"></a>

### WM-06 — Valid

**Klaim awal:** Scan picking tidak memvalidasi identitas roll dan menerima qty negatif.

**Hasil validasi:** Endpoint menerima identitas dan actual_qty untuk log task tanpa memverifikasi roll/bin serta qty positif. Ini diperparah dispatch yang tidak menggunakan pilihan fisik scan. Validasi dan reservation/pick claim harus terikat roll nyata serta kuantitas sisa pada versi yang sama.

**Dasar pembuktian:** Telaah route scan_pick; V2-13 membuktikan ketidakcocokan roll pick dan dispatch pada service.

**Lokasi kode:** [backend/routers/outbound_picking.py:82](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L82); [backend/routers/outbound_picking.py:112](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L112); [backend/routers/outbound_picking.py:139](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L139).

<a id="wm-07"></a>

### WM-07 — Valid

**Klaim awal:** Stock opname per bin memakai expected seluruh gudang dan membolehkan duplikasi.

**Hasil validasi:** Scope bin pada dokumen count tidak menjadi scope expected inventory yang sama. Dedup item/dimensi juga diperlukan. RFID count kehadiran tag dan stock opname kuantitas harus dihubungkan dengan aturan, tetapi tidak dianggap pengukuran yang sama: tag tidak mengukur sisa meter.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/routers/cycle_count.py:119](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L119); [backend/routers/cycle_count.py:117](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L117); [backend/routers/cycle_count.py:36](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L36).

<a id="wm-08"></a>

### WM-08 — Valid

**Klaim awal:** Adjustment shortage dapat parsial tetapi sesi tetap approved.

**Hasil validasi:** Adjustment shortage dapat mengembalikan removed lebih kecil dari requested dan hanya memberi warning; caller tetap approve. Roll picked/packed yang diharapkan dalam baseline dapat tidak eligible pada pengurangan. Existing warning/notification terhadap reserved tidak membuat hasil parsial menjadi benar.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/roll_service.py:1602](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L1602); [backend/routers/cycle_count.py:231](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L231).

<a id="wm-09"></a>

### WM-09 — Valid

**Klaim awal:** Penerimaan exception PA tidak menulis mutasi transfer.

**Hasil validasi:** Resolve exception accept mengubah roll/tag/location tetapi tidak menulis mutasi transfer yang setara dengan arrival normal. arrived_count dan status parent perlu dihitung ulang dari item aktual. Koreksi harus lewat movement immutable, bukan menambal dashboard saja.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/putaway_order_service.py:228](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L228).

<a id="fn-01"></a>

### FN-01 — Diperjelas

**Klaim awal:** Landed cost menghitung anak split dua kali.

**Hasil validasi:** Double allocation bergantung urutan. Parent dahulu mempropagasi biaya ke child, lalu alokasi langsung child menambah lagi karena tidak memakai guard voucher yang sama. Child dahulu dapat menghindari propagasi ulang. Jadi input/query order memengaruhi nilai uang; ini tetap cacat determinisme. Transfer yang mengganti acquired.ref_id juga dapat menghilangkan target PO.

**Dasar pembuktian:** V2-20 menjalankan apply_allocation_to_rolls dengan alokasi sama dalam dua urutan: parent70 + child30 untuk biaya100 menghasilkan uplift130 parent-first dan100 child-first; target selector juga ditelaah.

**Lokasi kode:** [backend/services/landed_cost_service.py:62](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/landed_cost_service.py#L62); [backend/services/landed_cost_service.py:159](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/landed_cost_service.py#L159); [backend/services/landed_cost_service.py:173](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/landed_cost_service.py#L173).

<a id="fn-02"></a>

### FN-02 — Valid

**Klaim awal:** 3-way match lolos overbilling dari baris produk duplikat.

**Hasil validasi:** Baris produk berulang dinilai satu per satu terhadap prior billed, bukan akumulasi dokumen berjalan; kapasitas PO juga dapat direbut dua bill berbeda. Perbaiki match menggunakan PO/receipt line identity dan claim kuantitas invoice; melarang duplicate product saja akan merusak PO yang sah memiliki dua baris produk sama.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/vendor_bill_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/vendor_bill_service.py#L78); [backend/services/vendor_bill_service.py:73](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/vendor_bill_service.py#L73); [backend/routers/vendor_bills.py:204](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L204).

<a id="fn-03"></a>

### FN-03 — Diperjelas

**Klaim awal:** WAC menjumlah panjang dan cost lintas unit tanpa konversi.

**Hasil validasi:** Penerimaan normal create_inbound_roll menormalisasi unit dan cost; jangan menuduh seluruh receipt mencampur unit. Jalur initial stock/legacy masih dapat menyimpan unit berbeda, lalu WAC menjumlah raw length dan unit_cost. Bukti harus menggunakan jalur reachable itu. Proyeksi qty yang mengonversi unit dapat berbeda dari valuation yang tidak.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/costing_service.py:70](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/costing_service.py#L70); [backend/services/costing_service.py:74](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/costing_service.py#L74).

<a id="fn-04"></a>

### FN-04 — Valid

**Klaim awal:** Arus kas seimbang tetapi klasifikasi transaksi nonkas salah.

**Hasil validasi:** Kesamaan total perubahan kas tidak membuktikan CFO/CFI/CFF benar. Delta akun nonkas dipakai sebagai arus; depresiasi atau aset dibeli kredit dapat menghasilkan bagian arus yang salah walau saling menutup. Gunakan metode cash-flow yang dinyatakan dan fixture transaksi nonkas, bukan hanya tes total zero.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/cash_flow_service.py:61](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cash_flow_service.py#L61); [backend/services/cash_flow_service.py:75](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cash_flow_service.py#L75).

<a id="fn-05"></a>

### FN-05 — Valid

**Klaim awal:** Master akun laporan menggabungkan override entitas dengan last-write-wins.

**Hasil validasi:** Kode akun sama dapat di-override per entity; create_account memungkinkan metadata/type berbeda. Dictionary global code→account memakai hasil terakhir dan dapat salah mengklasifikasi laporan entity lain. Resolve chart dengan entity dan effective policy sebelum aggregate.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/financial_statement_service.py:41](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L41); [backend/services/financial_statement_service.py:42](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L42).

<a id="fn-06"></a>

### FN-06 — Valid

**Klaim awal:** Jurnal manual menolak akun custom entitas dan mengabaikan override.

**Hasil validasi:** Manual journal menggunakan kumpulan akun global, tidak resolver akun efektif entity. Akun custom sah dapat ditolak atau override tidak digunakan. FN-05 dan FN-06 harus diperbaiki bersama agar input jurnal dan laporan memakai account identity yang sama.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/gl_service.py:567](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L567).

<a id="fn-07"></a>

### FN-07 — Diperjelas

**Klaim awal:** Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal.

**Hasil validasi:** Tidak semua transaksi kas selamanya tanpa jurnal: jalur sumber tertentu atau backfill dapat membuat JE. Defek spesifik ialah create manual tidak menjamin posting langsung/durable dan void kas tidak menjamin pembalikan JE terkait. Hilangkan klaim universal; tetap wajib rekonsiliasi cash subledger dengan GL dan reversal.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/routers/cash.py:108](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L108); [backend/routers/cash.py:156](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L156).

<a id="fn-08"></a>

### FN-08 — Valid

**Klaim awal:** Opening balance rekening dan perubahan rekening tidak tersambung GL.

**Hasil validasi:** Opening balance bank merupakan angka master yang tidak otomatis memiliki pasangan GL; perubahan nilai dapat mengubah ledger bank tanpa jurnal. Bedakan saldo statement bank, saldo subledger, dan saldo buku besar. Opening/import harus berupa transaksi asal yang terkontrol dan dapat ditelusuri.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/bank_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_service.py#L78); [backend/services/bank_service.py:94](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_service.py#L94).

<a id="fn-09"></a>

### FN-09 — Valid

**Klaim awal:** Void jurnal manual melewati penguncian periode.

**Hasil validasi:** Void manual journal tidak memakai pemeriksaan periode yang mengunci posting biasa. Memiliki permission accounting tidak berarti boleh mengubah periode closed. Reversal di periode terbuka atau reopen berotorisasi harus eksplisit.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/gl_service.py:673](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L673); [backend/services/gl_service.py:687](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L687).

<a id="fn-10"></a>

### FN-10 — Valid

**Klaim awal:** Pembayaran AR dapat sukses walau jurnal kas gagal.

**Hasil validasi:** Penerimaan AR dapat tersimpan ketika GL gagal dan exception hanya dicatat. Eventual posting boleh sebagai desain jika ada outbox, status pending/failed yang terlihat, retry idempotent dan rekonsiliasi. Best-effort log saja tidak memberi jaminan itu.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/ar_receipt_service.py:71](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L71); [backend/services/ar_receipt_service.py:106](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L106).

<a id="fn-11"></a>

### FN-11 — Diperjelas

**Klaim awal:** HPP per shipment memakai rata-rata semua roll pesanan.

**Hasil validasi:** Metode average cost tidak otomatis salah menurut akuntansi. Defek ialah harga shipment dihitung dari rata-rata roll order yang berubah, bukan basis biaya konsisten dengan subledger dan roll shipment aktual. Tetapkan specific identification atau WAC dengan cost layer/period policy; jangan mencampur keduanya.

**Dasar pembuktian:** Telaah post_shipment_cogs dan _order_item_unit_cost; V2-13 menunjukkan risiko identitas fisik yang mendahului COGS.

**Lokasi kode:** [backend/services/gl_service.py:992](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L992); [backend/services/gl_service.py:1070](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L1070).

<a id="fn-12"></a>

### FN-12 — Valid

**Klaim awal:** Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan.

**Hasil validasi:** Master aset dapat mengubah nilai/tanggal sebelum depresiasi dan akun aset setelahnya tanpa memperbarui JE perolehan yang sudah terbit. Cegah silent edit sesudah posting atau buat amendment dengan reversal/reclass sesuai periode; jangan mengubah historic JE di belakang layar.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/fixed_asset_service.py:141](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/fixed_asset_service.py#L141).

<a id="fn-13"></a>

### FN-13 — Valid

**Klaim awal:** Close periode dapat berjalan dua kali secara bersamaan.

**Hasil validasi:** Close membaca status terlebih dahulu lalu membuat jurnal penutup/record tanpa exclusive claim yang setara. Reopen mempunyai mekanisme sendiri; temuan ini tidak berarti semua fungsi closing tanpa kontrol. Perlukan unique period key dan serialisasi close versus posting/reopen.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/closing_service.py:253](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/closing_service.py#L253); [backend/services/closing_service.py:270](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/closing_service.py#L270); [backend/services/closing_service.py:312](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/closing_service.py#L312).

<a id="fn-14"></a>

### FN-14 — Dikoreksi sebagian

**Klaim awal:** Stock opname tidak memposting variance GL dan surplus dibuat tanpa cost.

**Hasil validasi:** Klaim surplus selalu tanpa cost ditarik. create_inbound_roll mengambil product.harga_pokok jika cost tidak diberikan; fixture HPP=100 menghasilkan unit_cost=100. Zero hanya jika fallback kosong/nol. Bagian yang tetap valid: adjustment tidak memposting variance GL, dan kebijakan valuation surplus harus dinyatakan serta dibuktikan.

**Dasar pembuktian:** V2-16 mengeksekusi apply_cycle_count_adjustment → create_inbound_roll, surplus 10 dengan unit_cost 100.

**Lokasi kode:** [backend/services/roll_service.py:1602](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L1602); [backend/routers/cycle_count.py:224](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L224).

<a id="fn-15"></a>

### FN-15 — Gap kontrol

**Klaim awal:** Helper autopost tidak menegakkan invariant jurnal di pintu insert.

**Hasil validasi:** Helper insert autopost mengandalkan caller untuk balance, finite amounts, akun valid dan period. Ini kelemahan defense-in-depth, bukan bukti setiap journal yang ada tidak seimbang. Tegakkan invariant di pintu persistence bersama tanpa menonaktifkan pengecekan domain caller.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/gl_service.py:503](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L503); [backend/services/gl_service.py:508](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L508).

<a id="fn-16"></a>

### FN-16 — Valid

**Klaim awal:** Neraca default tidak membatasi tanggal meski diberi label hari ini.

**Hasil validasi:** Router menerima as_of=None dan meneruskannya; service melakukan aggregate tanpa batas tanggal tetapi label default hari ini. Hanya jalur tanpa parameter yang terkena; UI yang selalu mengirim tanggal tidak membuktikan endpoint default benar.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/financial_statement_service.py:174](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L174).

<a id="gn-01"></a>

### GN-01 — Valid

**Klaim awal:** Idempotency tidak terikat user cookie, entitas dan payload.

**Hasil validasi:** Identitas middleware memakai cookie kn_session sedangkan autentikasi menggunakan session_token; active entity/payload tidak mengikat key. Dengan known/reused idempotency key, replay response dapat melintasi principal/scope. Random UUID klien menurunkan kemungkinan kebetulan, bukan menggantikan authorization response.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/idempotency.py:32](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/idempotency.py#L32); [backend/dependencies.py:9](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L9); [backend/idempotency.py:33](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/idempotency.py#L33).

<a id="gn-02"></a>

### GN-02 — Valid

**Klaim awal:** WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope.

**Hasil validasi:** Subscriber WebSocket GPS tidak menerapkan scope pengiriman/role yang setara REST, dan lookup session tidak memeriksa expiry pada jalur itu. Pisahkan otorisasi subscribe dan publish serta filter event per penerima; autentikasi user aktif saja tidak cukup.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/server.py:294](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/server.py#L294); [backend/services/tracking_service.py:61](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/tracking_service.py#L61); [backend/services/tracking_service.py:41](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/tracking_service.py#L41).

<a id="gn-03"></a>

### GN-03 — Valid

**Klaim awal:** Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen.

**Hasil validasi:** Permission bank/cash pada route berdasarkan ID belum membuktikan akun/dokumen milik scope pemanggil. Endpoint rekonsiliasi baru yang memakai scope tidak otomatis memperbaiki jalur lama. Perbaiki seluruh public entry point dan pagari di service boundary.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/routers/bank.py:82](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L82); [backend/routers/bank.py:92](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L92).

<a id="gn-04"></a>

### GN-04 — Valid

**Klaim awal:** R&D dapat mengambil bahan dari roll badan usaha lain.

**Hasil validasi:** Izin terhadap sample request tidak otomatis mengizinkan roll bahan milik entity lain. Issue mengambil roll by ID; pemeriksaan status/qty tidak memeriksa owner yang harus cocok atau intercompany authorization yang sah.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/routers/rnd.py:318](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L318); [backend/services/rnd_sample_service.py:1188](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_sample_service.py#L1188).

<a id="gn-05"></a>

### GN-05 — Valid

**Klaim awal:** Rollback pengambilan bahan R&D dapat menimpa pemakaian roll lain.

**Hasil validasi:** Kompensasi gagal GL mengembalikan quantity snapshot lama dan dapat menimpa konsumsi lain sesudah CAS pertama. Gunakan reversal operasi sendiri dengan versi/fencing; jangan restore seluruh old state tanpa memeriksa peristiwa selanjutnya.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/rnd_sample_service.py:1246](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_sample_service.py#L1246).

<a id="gn-06"></a>

### GN-06 — Valid

**Klaim awal:** Produksi menyelesaikan WO tanpa claim dan memakai BOM terbaru.

**Hasil validasi:** WO completion memakai BOM saat selesai dan tidak mengunci eksekusi sebagai satu operasi. Perubahan BOM atau retry setelah sebagian issue/receipt/GL dapat mengubah hasil atau menggandakan efek. Snapshot BOM/version dan material actual serta durable execution record diperlukan.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/production_service.py:358](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L358); [backend/services/production_service.py:278](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L278); [backend/services/production_service.py:339](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L339).

<a id="gn-07"></a>

### GN-07 — Valid

**Klaim awal:** Retur supplier mengurangi roll dengan read-set dan partial return kehilangan identitas fisik.

**Hasil validasi:** Pengurangan roll retur memakai read–set dan partial return tidak mempertahankan identitas potongan fisik yang keluar. Sama seperti outbound, retur harus memakai physical roll/segment yang terverifikasi serta movement; jangan memperbaiki hanya qty header.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/purchase_return_service.py:621](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L621); [backend/services/purchase_return_service.py:663](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L663).

<a id="gn-08"></a>

### GN-08 — Valid

**Klaim awal:** Konversi permintaan internal dapat melahirkan transaksi antar-PT ganda.

**Hasil validasi:** convert mengecek open dari snapshot lalu membuat interco sebelum menandai converted. create interco menyimpan source_request_id sebagai metadata, tanpa dedup pada jalur yang ditelaah; tidak ditemukan unique source-request enforcement pada pencarian kode. Perlu claim + unique business key, bukan hanya idempotency HTTP.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/internal_request_service.py:415](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/internal_request_service.py#L415); [backend/services/internal_request_service.py:427](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/internal_request_service.py#L427).

<a id="gn-09"></a>

### GN-09 — Valid

**Klaim awal:** CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID.

**Hasil validasi:** CRM guard owner untuk role sales tidak menggantikan entity check pada detail/mutation ID. List tersaring masih dapat dibypass dengan ID pada operasi lain. Uji custom role yang punya permission modul, bukan hanya role sales default.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/routers/crm_omnichannel.py:126](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L126); [backend/services/crm_omnichannel_service.py:148](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/crm_omnichannel_service.py#L148).

<a id="gn-10"></a>

### GN-10 — Valid

**Klaim awal:** Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global.

**Hasil validasi:** Query entity rekomendasi tidak diselesaikan melalui scope resolver; product_summary menjumlah inventory_balances seluruh owner/warehouse tanpa context. Ini membuktikan scope aggregate global. Jika tampilan stok grup memang diinginkan, tetap perlu izin khusus dan label eksplisit, tidak boleh menjadi stok yang dapat dijual entity aktif.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/routers/pos.py:20](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pos.py#L20); [backend/services/pos_recommendation_service.py:15](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/pos_recommendation_service.py#L15); [backend/services/pos_recommendation_service.py:26](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/pos_recommendation_service.py#L26).

<a id="gn-11"></a>

### GN-11 — Diperjelas

**Klaim awal:** Saga release menghapus lock tanpa mengecek efek yang sudah terposting.

**Hasil validasi:** Release lock admin dapat membolehkan retry operasi yang efek parsialnya sudah terjadi. Tidak berarti setiap retry pasti double-post; beberapa domain punya idempotensi tambahan. Pada dispatch bahkan ada titik lock sudah dilepas sebelum shipment dibuat, sehingga daftar stuck-lock tidak cukup untuk recovery.

**Dasar pembuktian:** V2-14; telaah atomic_claim dan endpoint release.

**Lokasi kode:** [backend/routers/saga_locks.py:36](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/saga_locks.py#L36); [backend/services/atomic_claim.py:53](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/atomic_claim.py#L53).

<a id="gn-12"></a>

### GN-12 — Valid

**Klaim awal:** Agregasi kritis berhenti pada batas to_list tanpa penanda truncation.

**Hasil validasi:** Batas to_list pada aggregate bisnis dapat memotong data tanpa continuation/indikator. Temuan tidak berlaku untuk pagination list UI yang memang dibatasi. Perbaiki agregasi stok, biaya, laporan dan expected set; tes di atas batas, bukan sekadar menghapus semua limit.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/roll_service.py:184](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L184); [backend/services/financial_statement_service.py:60](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L60); [backend/services/costing_service.py:60](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/costing_service.py#L60); [backend/routers/cash.py:76](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L76).

<a id="gn-13"></a>

### GN-13 — Valid

**Klaim awal:** Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit.

**Hasil validasi:** Rebuild berbasis snapshot dapat selesai tidak berurutan; writer lebih lambat menimpa proyeksi baru. Fallback konversi unit memakai raw quantity berpotensi salah dimensi. SSOT roll tidak otomatis menjamin cache balance benar; gunakan watermark/version dan gagal eksplisit untuk konversi yang tidak diketahui.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/roll_service.py:184](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L184).

<a id="gn-14"></a>

### GN-14 — Dikoreksi sebagian

**Klaim awal:** Audit log selalu before=None dan source secrets tersimpan dalam repo publik.

**Hasil validasi:** before=None membatasi audit perubahan pada helper umum, tetapi domain tertentu punya cost history sendiri. Artefak kandidat credential di repo tidak membuktikan credential masih aktif. Tidak ada secret yang dipakai untuk mencoba akses. Koreksi judul lama “source secrets” menjadi “artefak berpotensi sensitif; validitas belum terbukti”; lakukan pemeriksaan aman dan rotasi hanya credential nyata yang terekspos.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/dependencies.py:168](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L168).

<a id="gn-15"></a>

### GN-15 — Gap pemeliharaan

**Klaim awal:** Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten.

**Hasil validasi:** Duplikasi helper konkret patut dirapikan, tetapi jumlah status berbeda tidak otomatis pelanggaran SSOT. Taggable, available-to-promise, onsite, blocked dan financial inventory berbeda tujuan. Satukan definisi domain dan policy, bukan memaksa satu array status untuk semua kebutuhan.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/contract_service.py:62](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/contract_service.py#L62); [backend/services/lot_service.py:59](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/lot_service.py#L59); [backend/services/receiving_uom_service.py:63](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L63); [backend/services/uom_rules_service.py:146](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/uom_rules_service.py#L146).

<a id="hr-01"></a>

### HR-01 — Valid

**Klaim awal:** PPh21 memakai TER bahkan pada masa pajak terakhir.

**Hasil validasi:** Perhitungan TER generik tidak menyediakan penyelesaian masa pajak terakhir dengan rekonsiliasi penghasilan tahunan/Pasal 17. Berlaku untuk pegawai/kondisi yang mengikuti mekanisme tersebut, bukan klaim semua jenis penerima penghasilan harus memakai rumus identik. Belum disertifikasi terhadap seluruh tabel tarif dan seluruh status pegawai.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/hr_payroll_service.py:191](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L191); [backend/services/hr_payroll_service.py:192](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L192).

<a id="hr-02"></a>

### HR-02 — Diperjelas

**Klaim awal:** Lembur memakai multiplier flat dan dua sumber menit berpotensi tumpang tindih.

**Hasil validasi:** Flat multiplier tidak memodelkan jam pertama/berikutnya dan jenis hari pada lembur yang tunduk aturan tersebut. Dua sumber menit berpotensi overlap bila merepresentasikan pekerjaan sama; tidak semua konfigurasi pasti double count. Tetapkan source event identity, approval, kalender, eligibility dan payroll policy.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/hr_payroll_service.py:180](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L180); [backend/services/hr_payroll_service.py:156](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L156).

<a id="hr-03"></a>

### HR-03 — Valid

**Klaim awal:** Persetujuan cuti tidak mengecek ulang saldo dan cuti lintas tahun salah pembebanan.

**Hasil validasi:** Persetujuan cuti tidak mengecek saldo terkini sehingga dua pending request yang terpisah tanggal dapat bersama-sama melebihi saldo. Filter tahun berdasarkan date_from juga salah untuk rentang lintas tahun. Overlap tanggal dan saldo cuti adalah dua invariant berbeda.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/hr_leave_service.py:87](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L87); [backend/services/hr_leave_service.py:202](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L202); [backend/services/hr_leave_service.py:96](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L96).

<a id="mk-01"></a>

### MK-01 — Valid

**Klaim awal:** Input metrik marketing parsial mengganti seluruh metrik sebelumnya.

**Hasil validasi:** Update metrics parsial mengganti objek metrics seluruhnya. Jika caller hanya mengirim field baru, field lama hilang. Endpoint harus menyatakan PUT replacement atau PATCH merge; UI yang kadang mengirim seluruh objek tidak melindungi caller parsial lain.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/marketing_service.py:259](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/marketing_service.py#L259).

<a id="ux-01"></a>

### UX-01 — Valid

**Klaim awal:** Gate kiosk menampilkan hasil lama sebagai LIVE dan tidak mengagregasi satu passage.

**Hasil validasi:** Kiosk menggunakan hasil terakhir dan label LIVE meski polling gagal; 25 reads sebelum filter device dapat menyembunyikan lane sibuk. Timestamp yang sudah ditampilkan tetap berguna, tetapi tidak menggantikan state disconnected/stale dan ringkasan per passage. Audit ini membaca komponen; belum pengujian visual pada monitor gudang.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [frontend/src/features/rfid/RfidGateMonitorView.jsx:71](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidGateMonitorView.jsx#L71); [frontend/src/features/rfid/RfidGateMonitorView.jsx:76](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidGateMonitorView.jsx#L76); [frontend/src/features/rfid/RfidGateMonitorView.jsx:121](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidGateMonitorView.jsx#L121).

<a id="ux-02"></a>

### UX-02 — Valid

**Klaim awal:** Unduhan ZPL lewat tautan tidak membawa konteks entitas yang dipilih.

**Hasil validasi:** Tautan browser langsung tidak membawa X-Entity-Id dari interceptor Axios. entity_ctx mengambil header saja, lalu default home; tidak ada fallback cookie active entity pada resolver ini. Saat user memilih entity non-home, download job dapat ditolak walau layar berizin. Perlu authenticated blob request atau mekanisme download yang mempertahankan scope.

**Dasar pembuktian:** Telaah anchor UI → route get_print_job → entity_ctx/resolve_scope_ids; belum browser end-to-end.

**Lokasi kode:** [frontend/src/features/rfid/RfidPrintVerifyPanel.jsx:180](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidPrintVerifyPanel.jsx#L180).

<a id="gn-16"></a>

### GN-16 — Diperjelas

**Klaim awal:** Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas.

**Hasil validasi:** Notifikasi default all tidak berarti semua user lintas entity otomatis melihat semuanya: inbox masih memiliki scope entity dan permission link. Risiko spesifik ialah penerima lain yang memenuhi pagar tersebut dapat melihat report pribadi; digest query tidak punya entity filter. Terapkan audience+scope di setiap channel, bukan menyimpulkan semua channel pasti bocor dengan cara sama.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [backend/services/ai_schedules.py:92](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_schedules.py#L92); [backend/services/notification_service.py:67](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/notification_service.py#L67); [backend/services/notification_scope.py:47](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/notification_scope.py#L47); [backend/services/digest_service.py:119](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/digest_service.py#L119).

<a id="ux-03"></a>

### UX-03 — Valid

**Klaim awal:** Panel biaya OCR menampilkan ID entitas mentah.

**Hasil validasi:** ID entity mentah menambah beban baca panel biaya OCR. Ini perbaikan label ringan, bukan penghalang akurasi ledger. Resolve nama dan tetap sediakan ID untuk dukungan teknis hanya bila diperlukan.

**Dasar pembuktian:** Telaah statis alur kode dan pagar pemanggil; bukan pengujian HTTP.

**Lokasi kode:** [frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx:53](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx#L53).

## Acuan nonkode yang memengaruhi keputusan

Arus kas: transaksi investasi/pendanaan nonkas tidak menjadi arus kas periode itu; ini dasar menguji klasifikasi, bukan hanya kesamaan total. [IFRS — IAS 7](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/).

PPh 21: panduan DJP membedakan TER pada masa selain masa terakhir dan penghitungan masa terakhir. Implementasi harus mencakup rekonsiliasi tersebut; review ini tidak mengesahkan seluruh payroll. [DJP — panduan masa pajak akhir/A1](https://pajak.go.id/sites/default/files/2025-12/Pembuatan%20Bukti%20Pemotongan%20PPh%20Pasal%2021-Tahunan%20A1%20%20%281%29.pdf).

Lembur: lakukan validasi kalender, eligibility, basis upah dan perhitungan jam terhadap aturan yang berlaku bagi pekerja terkait. Acuan HR-02: [PP 35/2021 — sumber resmi BPK](https://peraturan.bpk.go.id/Details/161904/Peraturan). Tidak semua kontrak/kategori pekerja memiliki perlakuan identik.
