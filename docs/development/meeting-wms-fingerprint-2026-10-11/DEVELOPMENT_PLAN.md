# Development Plan ERP KainNusantara

**Tanggal:** 11 Oktober 2026  
**Cakupan:** 35 kebutuhan IMP-01–IMP-35 dari meeting, internal WMS, dan fingerprint.  
**Tahap dokumen:** rencana implementasi; belum ada pekerjaan yang dinyatakan implemented atau validated.  
**Baseline rujukan:** `f59b8a60d7b7e078888c537ca93c046afae460a9`; agent wajib mengidentifikasi branch/commit aktual pada P00.

## 1. Sasaran dan batas pekerjaan

Sasaran adalah menyelesaikan seluruh kebutuhan yang telah dirapikan, termasuk perilaku UI, kontrak server, migrasi data lama, hubungan antarmodul, dan bukti penerimaan. Paket ini melanjutkan daftar kebutuhan; tidak mengulang audit seluruh kode atau menggantikan backlog temuan gelombang 1–3.

Rencana ini tidak menganggap semua kebutuhan adalah fitur baru. Agent terlebih dahulu memeriksa implementasi pada branch aktual, mempertahankan yang sudah benar, dan memperbaiki gap yang masih berlaku. Perubahan Finance dibatasi pada dampak scope ini: qty komersial, harga, ownership, bahan/WIP, valuation opname, invoice/jurnal yang terkait, dan input attendance untuk payroll.

Keputusan bisnis yang belum final dicatat dalam [DECISIONS.md](DECISIONS.md). P00 dapat selesai dengan keputusan masih terbuka asalkan dampak dan bagian pekerjaan yang menunggu jelas. Struktur data, diagnosis, serta implementasi yang independen boleh dilanjutkan; keputusan klien tidak boleh diganti asumsi atau menjadikan seluruh proyek berhenti.

## 2. Urutan fase dan dependensi

| Fase | Fokus | IMP utama | Mulai setelah | Ukuran |
|---|---|---|---|---|
| [P00](phases/P00.md) | Baseline, keputusan bisnis, dan kontrak antarmodul | Lintas scope | — | M |
| [P01](phases/P01.md) | Master data, lifecycle, dan cakupan lokasi pengguna | IMP-12, IMP-13, IMP-14, IMP-15, IMP-20 | P00 | L |
| [P02](phases/P02.md) | Alamat, putaway, integritas referensi, dan rules WMS | IMP-22, IMP-23, IMP-24, IMP-25 | P01 | XL |
| [P03](phases/P03.md) | Penerimaan OCR dan transfer yang terkait pemenuhan SO | IMP-21, IMP-26, IMP-27 | P02 | XL |
| [P04](phases/P04.md) | Sales, Keep/Pending, roll picker, kuantitas SO, dan grade | IMP-02, IMP-03, IMP-04, IMP-05, IMP-06, IMP-11 | P01, P03 | XL |
| [P05](phases/P05.md) | MD Quality, R&D existing, bahan makloon, dan sumber restock | IMP-16, IMP-17, IMP-18, IMP-19 | P01, P02 | XL |
| [P06](phases/P06.md) | Special Order multi-produk dan jalur desain pelanggan | IMP-07, IMP-08 | P04, P05 | XL |
| [P07](phases/P07.md) | Jenis sampel dan proses Admin Cutting | IMP-09, IMP-10 | P02, P04 | L |
| [P08](phases/P08.md) | Opname, dashboard stok, dan konsistensi meja pengguna | IMP-01, IMP-28, IMP-29 | P01, P02, P03, P04, P05, P06, P07 | XL |
| [P09](phases/P09.md) | Fingerprint langsung, log mentah, perhitungan shift, dan monitoring HR | IMP-30, IMP-31, IMP-32, IMP-33, IMP-34, IMP-35 | P00, P01 | XL; hardware-dependent |
| [P10](phases/P10.md) | Integrasi menyeluruh, migrasi pilot, UAT, dan kesiapan rilis | Lintas scope | P01, P02, P03, P04, P05, P06, P07, P08, P09 | L |

Urutan utama: **P00 → P01 → P02 → P03 → P04 → P06 → P08 → P10**. P05 dapat berjalan setelah P01/P02 dan harus terintegrasi sebelum P06 serta validasi akhir Pending produksi. P07 memerlukan fondasi WMS dan Sales, kemudian masuk validasi P08. P09-A, yakni uji kompatibilitas fingerprint, dimulai setelah P00; P09-B dilaksanakan setelah fondasi lokasi/identitas P01 serta hasil PoC.

P03 memakai kontrak reservasi dan baris SO yang dipetakan pada P00. P04 tidak harus selesai lebih dahulu untuk membangun transfer terkait SO; hindari ketergantungan melingkar dengan menetapkan kontrak bersama dan menggunakan layanan reservasi existing. Perubahan UI Pending P04 dapat diterapkan terhadap layanan existing, tetapi verifikasi lengkap jalur produksi dilakukan setelah P05.

Pengerjaan bersamaan pada repo harus menggunakan branch/PR dan batas file/kontrak yang jelas; penggabungan tetap mengikuti dependensi di atas. Ini adalah pilihan pelaksanaan tim pengguna, bukan instruksi menjalankan agent paralel dari percakapan ini.

## 3. Besaran pekerjaan dan penetapan jadwal

M = satu kajian/fondasi terfokus; L = perubahan domain dengan beberapa consumer; XL = perubahan lintas status, dokumen, atau migrasi yang memerlukan uji rantai. Ukuran ini bersifat relatif, bukan estimasi hari/jam atau jaminan waktu pengerjaan AI.

Pada P00, developer mengisi estimasi berdasarkan gap aktual, kualitas tes existing, kesiapan data, keputusan klien, kapasitas pengembang, dan unit fingerprint. Pecah fase XL menjadi work package yang dapat direview, tanpa menutup IMP sebelum seluruh perilakunya terpenuhi. Tanggal komitmen belum ditentukan karena baseline terbaru serta perangkat nyata belum diverifikasi oleh paket ini.

## 4. Kontrak bersama dan sumber kebenaran

| Area | Kontrak yang harus dijaga |
|---|---|
| Identitas barang | Induk/varian/spec version tetap mempunyai ID; alias supplier/customer merupakan mapping, bukan pengganti identitas internal. |
| Roll fisik | Identitas roll, qty/satuan, status, owner, warehouse dan bin berasal dari record serta event stok yang sah. Proyeksi stok mengikuti layanan otoritatif existing. |
| Lokasi | Site > warehouse > zone > rack/lemari > level/rak > bin. Istilah dapat disesuaikan; ID dan hubungan tidak berubah karena rename. |
| Owner dan lokasi | Perpindahan gudang tidak otomatis memindahkan kepemilikan. Site access, warehouse usability, dan stock owner adalah dimensi berbeda. |
| Komitmen | Satu roll/qty tidak mendanai dua demand. Transfer terkait SO mempertahankan relasi demand tanpa reservation ganda. |
| Qty dan unit | Ordered, allocated, physically received, shipped, remaining serta rollcount terpisah. Penjumlahan lintas dimensi memerlukan konversi sah. |
| Keep/Pending | Keep terkait verifikasi; Pending terkait kebutuhan pemenuhan. Keduanya dapat bersamaan. Definisi angka/timing mengikuti DEC-01. |
| Incoming/ATP | Pipeline tidak dianggap fisik di rak. Pasokan tidak dialokasikan ke demand melebihi kapasitasnya; eligible ATP mempertimbangkan komitmen, kualitas, owner, dan jalur fulfillment. |
| Rules | Satu evaluator untuk saran dan mutasi semua entry path; server revalidasi state, scope, owner, barang, kapasitas, dan kebijakan pengecualian. |
| R&D/OD | Request/round/spec/OD line mempunyai relasi stabil. Uji tambahan tidak membuat SKU baru jika identitas tidak berubah. |
| Absensi | Raw punch adalah bukti asal; attendance shift merupakan hasil derivasi. Perangkat melakukan verifikasi fingerprint; ERP tidak memerlukan template biometrik untuk pencatatan kehadiran. |
| Ringkasan UI | Query total dan detail menggunakan filter/scope/status/unit yang sama; total seluruh data tidak berasal dari page yang sedang terlihat. |

P00 menghasilkan kamus metrik yang mencatat nama, formula, sumber, status yang dimasukkan/dikecualikan, unit, scope, timing, dan contoh. Hindari membuat tabel counter stok lemari/rak atau kalkulasi frontend tersendiri yang berjalan terpisah dari proyeksi server.

Perubahan stok, receipt, allocation, consumption, adjustment, dan ingestion harus mempunyai operasi sekali saja atau mekanisme idempotensi serta recovery yang dapat dibuktikan. Pilih transaksi/conditional update/outbox/reconciliation sesuai kemampuan database aktual; jangan mengasumsikan transaksi multi-record tersedia tanpa memeriksa infrastrukturnya.

## 5. Peran dan tanggung jawab

| Fungsi | Tanggung jawab |
|---|---|
| Pemilik proses | Menetapkan keputusan bisnis, scope, PIC, serta hasil UAT. |
| Agent/developer | Reproduksi gap, implementasi lengkap server/UI, migrasi, meaningful tests, dokumentasi, dan evidence. |
| Reviewer teknis | Menilai kontrak, state transition, consumer terdampak, ketahanan retry/concurrency, dan kecocokan perubahan dengan kebutuhan. |
| Validator | Mengecek kembali commit implementasi dan bukti nyata; dapat menggunakan sesi validasi bersama pengguna. |
| Pengguna domain | UAT dengan peran Sales/Admin Sales, MD, Gudang, Cutting, HR, serta Finance yang relevan. |
| Pemilik deployment | Menyetujui pilot/rilis dan menjalankan operasi produksi sesuai kewenangan. |

Nama personal dan pembagian tenaga diisi pengguna; tidak diasumsikan. Review implementasi dan persetujuan bisnis merupakan dua kegiatan berbeda.

## 6. Strategi data lama, migrasi, dan compatibility

| Kelompok | Penanganan yang direncanakan |
|---|---|
| Tahap/alias master | Mapping yang eksplisit, konflik/ambiguity report, ID stabil; jangan merge SKU berdasarkan kemiripan nama. |
| Supplier/color | Cakupan uniqueness dan mapping ke internal; transaksi lama mempertahankan representasi serta relasi yang sah. |
| Assignment lokasi | Review user-site sebelum enforcement; pengguna lama tidak otomatis memperoleh semua lokasi. |
| Struktur alamat | Adapter legacy-modern atau migrasi bertahap; bin referenced tetap terpetakan, invalid masuk orphan queue. |
| Rules/kapasitas | Version/config jelas; dimensi wajib diketahui sebelum utilization atau hard limit baru digunakan. |
| Transfer aktif | State serta demand commitment tetap; receipt historis tanpa bukti tidak diberi scan palsu. |
| Sales/alokasi | Rekonsiliasi qty line/roll/dokumen; invoice yang telah diposting tidak diubah diam-diam. |
| R&D/spec | Histori serta pelaksana/approval yang ada dipertahankan; missing evidence tampil unknown. |
| Makloon | Rekonsiliasi reserved, issued, WIP, hasil/waste dan biaya; tidak menggunakan konversi atau yield fiktif. |
| OD single-product | Diadaptasi menjadi satu line dengan ID stabil dan semua link downstream; consumer lama diuji. |
| Sampel aktif | Mapping sesuai posisi proses/fisik; historical dispatched tidak dibuka ulang otomatis. |
| Opname | Sesi dan adjustment existing tetap berjejak; expected tidak diganti saat count berjalan. |
| HR legacy | Aggregate lama tetap aggregate; tidak membuat raw punch fiktif. Sumber CSV/bridge/native dibedakan. |

Setiap migrasi memiliki preview, mapping, jumlah record, exception, apply/checkpoint, rerun yang aman, dan rekonsiliasi hasil. Percobaan dilakukan pada salinan data representatif. Rollback harus mempertimbangkan event/dokumen baru setelah upgrade; rollback kode saja belum tentu dapat membalik perubahan data dengan aman.

## 7. Pengujian dan bukti penerimaan

[ACCEPTANCE_MATRIX.md](ACCEPTANCE_MATRIX.md) berisi 67 skenario ACC-00–ACC-66. Semua mulai sebagai `not_run`. Itu daftar pengujian yang harus dilakukan, bukan laporan bahwa pengujian telah lulus.

Gunakan tes existing setelah memeriksa ruang lingkup dan lingkungan. Snapshot mempunyai `backend/pytest.ini` dengan xdist dan `frontend/package.json` dengan skrip test/build; branch aktual dapat berbeda. Jangan mengubah konfigurasi tes agar terlihat lulus. Jangan menjalankan tes yang memutasi layanan aktif/produksi tanpa lingkungan uji yang sesuai. Tes unit terisolasi, API+DB, UI, dan E2E dipilih sesuai perubahan; build bukan bukti kebenaran bisnis.

Bukti per fase minimal: commit, kebutuhan dan temuan yang disentuh, before/after, kontrak/status berubah, migrasi serta hasilnya, perintah tes berikut exit/result, sample input-output, screenshot UI relevan, issue terbuka, dan batas validasi. Gunakan [template laporan](templates/PHASE_REPORT.md).

Untuk inventory/Finance, bukti harus memperlihatkan rekonsiliasi roll/saldo/komitmen/dokumen/jurnal yang relevan. Untuk hardware, simpan model/firmware, konfigurasi tanpa secret, event mesin nyata, penerimaan ERP, offline/retry, dan kecocokan shift. Bukti simulator dan bukti mesin nyata dilaporkan terpisah.

## 8. Tracker dan proses validasi berulang

[BACKLOG.json](BACKLOG.json) adalah sumber status, commit, issue, keputusan, dan evidence. [TRACKER.md](TRACKER.md) adalah tampilan hasil render, bukan sumber status kedua. Gunakan `scripts/render_tracking.py` setelah mengubah JSON. [COVERAGE.md](COVERAGE.md) memetakan 35 IMP ke fase, keputusan, dan skenario penerimaan.

Alur normal: `not_started → in_progress → implemented_pending_validation → validated`. Gunakan `waiting_decision` atau `waiting_hardware` hanya untuk bagian yang sungguh bergantung input tersebut. Jika validator menemukan regresi, ubah menjadi `reopened` beserta alasan, commit, dan evidence.

`implemented_pending_validation` berarti kode telah ada serta developer menyerahkan bukti; belum menutup kebutuhan. `validated` memerlukan verifikasi pada commit tercatat dan evidence yang mendukung seluruh hasil yang diharapkan. Jika hanya satu consumer/perangkat berhasil, jangan menutup seluruh IMP. Jika bug sudah fixed pada baseline, tetap lampirkan bukti commit/tes sebelum menutupnya.

Validasi akhir P10 memeriksa keseluruhan scope, termasuk pengujian rantai setelah integrasi. P08 dan P09 dapat memakai adapter legacy selama transisi yang dibuktikan; adapter bukan alasan menggandakan sumber kebenaran.

## 9. Pilot dan definisi selesai

Pilot menguji lokasi/perangkat serta peran yang disepakati, dengan data dan dokumen nyata yang boleh digunakan. Sediakan panduan operasional, training singkat, monitoring exception, jalur recovery, dan bukti migrasi. Scope rilis dapat dipisahkan berdasarkan kesiapan, tetapi status keseluruhan tidak menjadi complete bila salah satu dari 35 kebutuhan belum validated.

Selesai berarti seluruh 35 kebutuhan memiliki implementasi serta bukti penerimaan pada target commit; keputusan yang diperlukan telah tercatat; migrasi/reconciliation/UAT lulus; tidak ada bug material terbuka yang melanggar scope. Kompatibilitas fingerprint harus dibuktikan pada unit nyata. Rilis produksi mengikuti otorisasi pemilik sistem setelah hasil konkret tersedia.

## 10. Rincian dan prompt per fase

- [P00 — Baseline, keputusan bisnis, dan kontrak antarmodul](phases/P00.md)
- [P01 — Master data, lifecycle, dan cakupan lokasi pengguna](phases/P01.md)
- [P02 — Alamat, putaway, integritas referensi, dan rules WMS](phases/P02.md)
- [P03 — Penerimaan OCR dan transfer yang terkait pemenuhan SO](phases/P03.md)
- [P04 — Sales, Keep/Pending, roll picker, kuantitas SO, dan grade](phases/P04.md)
- [P05 — MD Quality, R&D existing, bahan makloon, dan sumber restock](phases/P05.md)
- [P06 — Special Order multi-produk dan jalur desain pelanggan](phases/P06.md)
- [P07 — Jenis sampel dan proses Admin Cutting](phases/P07.md)
- [P08 — Opname, dashboard stok, dan konsistensi meja pengguna](phases/P08.md)
- [P09 — Fingerprint langsung, log mentah, perhitungan shift, dan monitoring HR](phases/P09.md)
- [P10 — Integrasi menyeluruh, migrasi pilot, UAT, dan kesiapan rilis](phases/P10.md)

Prompt umum wajib dibaca melalui [AGENT_GUIDE.md](AGENT_GUIDE.md). Semua titik masuk kode pada fase merupakan referensi snapshot, bukan daftar file wajib diubah atau pernyataan bahwa file tersebut satu-satunya consumer.
