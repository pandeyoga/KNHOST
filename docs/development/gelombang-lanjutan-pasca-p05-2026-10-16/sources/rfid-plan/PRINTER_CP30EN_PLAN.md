# Rencana Printer CP30EN — API, Connector, Encoding dan Verifikasi

**Tanggal:** 12 Oktober 2026. **Pilihan pengguna:** CP30EN. **Scope:** RFID-11–RFID-15, terkait RFID-04 dan RFID-10. **Tahap:** PoC RF00, kontrak RF01, implementasi RF-P, UAT RF04/P10.

## 1. Profil yang diketahui dan yang harus dibuktikan

Nama CP30EN diberikan pengguna dan dipakai dalam rencana. Dokumentasi resmi yang ditemukan berada pada keluarga [CP30](https://www.chainway.net/Products/Info/138); [halaman dukungan](https://www.chainway.net/support/Info/30) menyediakan Windows_ZPL SDK dan ZPL_Linux SDK. Cocokkan label varian/serial, firmware/modul RFID, interface, resolusi, ukuran label, jenis inlay dan ribbon sebelum driver/template diaktifkan. Jangan menafsirkan suffix EN atau kemampuan unit dari nama saja.

Kode saat ini membuat ZPL dengan instruksi RFID serta template berasumsi 203 dpi. Dokumen bahasa [ZPL ^RF](https://docs.zebra.com/us/en/printers/software/zpl-pg/c-zpl-rfid-zpl-rfid-commands/r-zpl-rfid-rf.html) menjelaskan read/write RFID pada implementasi Zebra; sumber ini menjadi referensi bahasa, bukan bukti kompatibilitas seluruh perintah pada CP30EN. PoC harus menguji command dan hasil chip pada firmware CP30EN aktual.

## 2. Tempat menjalankan connector

| Pilihan | Prasyarat | Keterangan |
|---|---|---|
| Service Windows/Linux di lokasi gudang | SDK/koneksi kompatibel dan akses printer lokal. | Menarik job ERP dan menjalankan connector unattended; dapat memakai host existing yang layak, bukan laptop operator yang harus dibuka setiap kali cetak. |
| Service pada server yang dapat menjangkau printer | Rute jaringan privat yang sah dan transport/protokol yang didukung. | Cocok bila printer benar-benar dapat dijangkau server; ERP cloud tidak otomatis dapat mengakses printer di LAN gudang. |
| Reuse host reader/perangkat existing | SDK/protokol serta runtime terbukti cocok. | PoC diperlukan; ketersediaan SDK Windows/Linux tidak membuktikan aplikasi yang sama berjalan pada Android UR300/C72. |

Connector bukan aplikasi yang otomatis diasumsikan dapat dipasang di firmware printer. Pilih satu arsitektur dari bukti jaringan dan SDK; hindari dua connector aktif untuk printer yang sama tanpa koordinasi. Media/koneksi aktual diisi dari unit, bukan dipilih fiktif.

## 3. Alur operasional yang dituju

1. Barang diterima melalui flow gudang yang sah; identitas roll, qty/satuan, LOT, gudang dan owner sudah ditetapkan. Pembuatan label tidak menambah stok lagi.
2. Operator memilih roll dan jenis label. ERP menetapkan/referensikan EPC unik serta print job; satu EPC tidak diterbitkan ulang sebagai identitas roll lain.
3. Operator meninjau template/snapshot sumber, tujuan printer/gudang dan jumlah label. Data yang berubah sejak job dibuat ditinjau sebelum output, bukan dicetak dari informasi yang diam-diam sudah basi.
4. Connector mengklaim job/attempt yang sah, menyimpan ledger lokal, memeriksa readiness dan mengirim perintah yang sudah lolos PoC.
5. CP30EN mencetak informasi label dan menulis EPC ke chip RFID. Jika firmware mendukung hasil encode/readback/error, connector menyimpannya. Payload dikirim belum membuktikan kedua pekerjaan selesai.
6. Hasil per item dicatat: berhasil, gagal, atau belum dapat dipastikan. Job parsial tidak dikonfirmasi berhasil seluruhnya. Label error/VOID/blank ditangani sesuai kemampuan unit dan SOP.
7. Label ditempel ke roll yang tepat; C72 menjalankan sesi print_verify dari ERP dan membandingkan expected vs scanned. Pemeriksaan penempelan menjaga roll-label tidak tertukar, bukan sekadar membaca kumpulan tag yang masih di meja.
8. Setelah bukti yang disyaratkan sah, barang masuk putaway/storage atau tetap transit untuk cross-dock. Loading/gate memakai identitas dan dokumen aktual.

Output utama: label terbaca manusia/barcode, EPC chip sesuai ERP, proof printer/item/attempt, serta verifikasi C72 yang terikat tag dan roll. RFID tag wajib tidak dipenuhi hanya dengan label QR. Cetak SJ/logistik tetap berasal dari dokumen dan lokasi pengiriman menggunakan media/perangkat yang sesuai; CP30EN tidak dianggap printer A4 untuk semua format SJ.

## 4. API printer yang sudah tersedia pada snapshot

| Endpoint | Fungsi dan batas |
|---|---|
| POST /api/rfid/print-jobs | Operator membuat job dari roll; menyimpan EPC/tag/item/warehouse/owner dan ZPL. Ini belum menulis chip printer secara fisik. |
| GET /api/rfid/print-jobs/{job_id}/zpl | Mengambil payload ZPL; keberhasilan download belum membuktikan cetak/encode selesai. |
| GET /api/rfid/device-jobs/pending | Connector printer memakai X-Device-Key untuk claim job sesuai warehouse/capability; menghasilkan lease dan attempt_id. |
| POST /api/rfid/device-jobs/{job_id}/ack | Connector mengakui job printed dengan attempt_id lease yang sah; kontrak existing adalah tingkat job. |
| POST /api/rfid/print-jobs/{job_id}/mark-printed | Jalur pengakuan manual operator; tidak boleh dilaporkan sebagai hasil device otomatis. |
| POST /api/rfid/print-jobs/{job_id}/verify/start | Operator memulai expected scan job. |
| POST /api/rfid/ingest dengan session_id | C72 mengirim bukti scan device ke sesi. |
| POST /api/rfid/verify-sessions/{session_id}/complete | Operator menutup hasil verifikasi sesuai permission dan exception. |

Rujukan: [router RFID](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/routers/rfid.py#L568), [printer ingest/ACK](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/rfid_ingest_service.py#L310), [print job dan journey](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/rfid_print_service.py#L130).

Contoh body ACK existing setelah hasil job benar-benar memenuhi kontrak:

```json
{"attempt_id": "patt-example"}
```

Tidak ada field per-item success/error dalam AckPayload yang ditelusuri. RF01/RF-P harus menetapkan kontrak partial result, uncertain output, failure, lease renewal dan recoverability; field usulan tidak dikirim sambil mengasumsikan server existing memprosesnya. Compatibility dapat memakai job satu item jika sah dan memadai, tetapi kebutuhan bulk harus mempunyai hasil per item yang jelas.

## 5. State database dan bukti fisik

| Dimensi | Makna |
|---|---|
| EPC/tag terdaftar | Identitas ERP dibuat/referensikan; belum membuktikan tag fisik ditulis. |
| Job queued/lease | Pekerjaan tersedia/diklaim; belum output berhasil. |
| Payload sent | Connector menyerahkan data ke transport/printer; hasil bisa belum pasti. |
| Printed/encoded terkonfirmasi | Hasil hardware/operasional telah diketahui sesuai kontrak model; simpan bukti, jangan menyimpulkan dari HTTP download/socket success. |
| Pending_print/active pada tag ERP | Lifecycle identitas. Pada snapshot, on_printed mengaktifkan pending_print setelah ACK; active tidak sama dengan C72 verified. |
| Verified | Pembacaan yang sah sesuai expected dan hubungan tag-roll, dengan penempelan fisik yang benar serta approval/SOP yang berlaku. |

Target state tambahan di atas adalah rancangan kontrak; bukan pernyataan seluruh state sudah ada dalam schema existing. Perluasan harus menjaga history, legacy manual print, serta rule downstream yang membutuhkan verified_tag_id.

## 6. Failure, retry dan hasil belum pasti

| Kasus | Perilaku yang dituju |
|---|---|
| Printer offline sebelum payload dikirim | Job dapat ditunda/dicoba sesuai kebijakan, dengan attempt/queue yang dapat ditelusuri. |
| Data dikirim tetapi hasil timeout/tidak pasti | Masuk reconciliation melalui status printer, ledger, readback/C72 dan operator; jangan langsung kirim ulang semua label. |
| Selesai cetak tetapi ACK ERP hilang | Ulangi ACK atau reconciliation hasil; tidak mencetak ulang output yang sudah jadi. |
| Batch sebagian berhasil | Persist item outcome; jangan ACK seluruh job lalu mengaktifkan seluruh tag sebagai sukses. |
| Paper/ribbon out, jam, encoding error | Simpan error/recovery dan posisi terakhir yang diketahui. VOID/error marker hanya dianggap tersedia bila model membuktikannya. |
| Lease expired ketika masih mencetak | Claim/renew/reassign mengikuti attempt yang terkoordinasi; printer kedua tidak mengambil job dengan output fisik belum diselesaikan. |
| Poll job sama dari printer pemilik lease | Jangan memutar attempt_id atau spool ulang attempt aktif hanya karena polling dilakukan lagi. |
| Job printed tersimpan, efek tag/journey gagal | Recovery melengkapi efek yang belum selesai berdasarkan attempt dan job, tanpa physical reprint. |

Keunikan record serta replay ACK tidak menjamin pencetakan fisik tepat sekali pada semua printer. Jika hardware tidak mempunyai dedup/job-status yang cukup, persistent ledger dan review output ambigu adalah bagian wajib recovery.

Pada kode snapshot, pull dapat mengklaim ulang job milik printer yang sama dan membuat attempt baru; ACK menyimpan printed sebelum memanggil on_printed. Kedua jalur perlu diuji terhadap polling saat print aktif serta kegagalan side effect setelah status durable. Ini risiko kontrak dari penelusuran statis, belum klaim reproduksi runtime atau temuan tervalidasi pada branch terbaru.

## 7. Reprint dan re-tag

- Bedakan penggantian tulisan label dengan penggantian chip/identitas RFID. Cetak stiker teks pengganti tidak otomatis menulis chip baru.
- Jika chip baru dibuat dengan EPC yang sama, tag lama tidak boleh tetap beredar sebagai tag fisik aktif. Penanganan fisik dan sistem harus mengikuti SOP; unique EPC di database tidak mendeteksi dua chip fisik yang diberi nilai sama.
- Jika EPC diganti, gunakan alur retire/replacement berizin dan histori tag-roll; verifikasi tag baru. Guardrail movement aktif dipertahankan.
- Record operator, alasan, referensi job/item/attempt, identitas lama-baru, penanganan tag lama dan bukti C72. TID dapat membantu jika tersedia, tanpa diasumsikan wajib atau mengganti SSOT EPC/roll.
- Reprint tidak membuat receipt/stok baru, mengubah owner, memundurkan journey stored atau mengubah invoice historis. Jumlah/media label dan qty barang adalah dimensi terpisah.

## 8. Antarmuka dan evidence

UI menampilkan queue per printer/gudang, item/roll, preview serta sumber qty/unit, state hardware vs job vs verification, error/ambiguity, attempt, PIC, dan tindakan retry/reconcile/reprint/retag sesuai izin. Health printer tidak disamakan dengan heartbeat service connector.

Evidence minimal: label/model/firmware dan SDK; konfigurasi media/resolusi/koneksi yang dapat direview; payload EPC/template; actual print/encode; C72 expected/actual; item outcome; lease/attempt/ACK; offline/lost ACK/partial failure; tag replacement; UI; rekonsiliasi roll/tag/job/journey. Gunakan RACC-21–RACC-30 serta E2E RF04/P10. Semua skenario awal not_run.
