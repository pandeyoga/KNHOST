# Matriks Penerimaan dan Regresi

67 skenario ACC-00–ACC-66. Status awal: not_run. Ini rencana pengujian, bukan hasil kelulusan.

Fixture angka/shift hanya contoh uji; parameter produksi mengikuti keputusan bisnis. Setiap hasil mencatat commit, lingkungan, expected/actual dan evidence dalam BACKLOG.json.

## P00 — Baseline, keputusan bisnis, dan kontrak antarmodul

### ACC-00 — Baseline target

**Kebutuhan:** ALL

- **Persiapan:** Checkout target pengembangan dan snapshot audit.
- **Tindakan:** Catat commit dan jalankan diagnosis/reproduksi relevan.
- **Hasil yang wajib:** Beda versi, perbaikan existing, baseline failure, dan blocker tercatat; tidak ada status fixed hanya berdasarkan komentar.

## P01 — Master data, lifecycle, dan cakupan lokasi pengguna

### ACC-01 — Tahap dan kelayakan jual

**Kebutuhan:** IMP-12

- **Persiapan:** Greige, PFD, PFP, Finished pada woven/knit/printing.
- **Tindakan:** Cari dari seluruh selector Sales lalu dari MD/pembelian/gudang.
- **Hasil yang wajib:** Bahan tidak muncul bagi Sales; tetap terlihat sesuai izin operasional; bahan SKU tidak dipaksa melewati R&D MD.

### ACC-02 — Alias supplier/color

**Kebutuhan:** IMP-13

- **Persiapan:** Dua supplier memakai kode/nama warna berbeda untuk satu SKU internal.
- **Tindakan:** Impor mapping, buat PO dan terima item dari keduanya.
- **Hasil yang wajib:** Relasi tepat tanpa SKU ganda; kode internal/supplier/customer tidak saling ditimpa; mapping ambigu meminta review.

### ACC-03 — Lifecycle master

**Kebutuhan:** IMP-14

- **Persiapan:** Produk/warna/supplier alias telah dipakai stok dan transaksi.
- **Tindakan:** Rename, nonaktifkan, dan coba hapus referensi terpakai.
- **Hasil yang wajib:** ID serta histori tetap; penghapusan yang memutus relasi ditolak; pengguna mengetahui dependensi.

### ACC-04 — Filter master

**Kebutuhan:** IMP-15

- **Persiapan:** Data lintas tahap/jenis/supplier/status.
- **Tindakan:** Gabungkan filter, paginasi, reset, dan buka detail.
- **Hasil yang wajib:** Jumlah hasil dan detail sesuai filter; nilai registry konsisten; state filter tidak hilang tanpa tindakan pengguna.

### ACC-05 — Scope lokasi

**Kebutuhan:** IMP-20

- **Persiapan:** Operator Bandung, Jakarta, dan supervisor; owner entitas sama.
- **Tindakan:** Baca/mutasi detail lewat UI dan API, termasuk notifikasi/ekspor.
- **Hasil yang wajib:** Operator hanya scope penugasan; supervisor mengikuti grant; same-entity tidak menjadi bypass lokasi.

## P02 — Alamat, putaway, integritas referensi, dan rules WMS

### ACC-06 — Resolver modern/legacy

**Kebutuhan:** IMP-22, IMP-23

- **Persiapan:** Bin legacy rack.bins dan modern rack.levels[].bins.
- **Tindakan:** Buat alamat lewat editor, scan penerimaan, dan putaway manual.
- **Hasil yang wajib:** Seluruh consumer menemukan alamat yang sama pada gudang yang benar; DEV-F01 tidak berulang.

### ACC-07 — Menu dan putaway

**Kebutuhan:** IMP-22

- **Persiapan:** Role standar/custom, desktop/mobile, roll available dan QC hold.
- **Tindakan:** Buka antrean, scan alamat, tempatkan roll.
- **Hasil yang wajib:** Menu benar; qty/owner tidak berubah saat putaway; barang terhambat punya alasan; hold tidak terlewati.

### ACC-08 — Status fisik

**Kebutuhan:** IMP-22, IMP-24

- **Persiapan:** Roll available, in-transit, consumed, QC/hold.
- **Tindakan:** Kirim aksi penempatan langsung selain memilih lewat UI.
- **Hasil yang wajib:** In-transit/offsite/consumed ditolak; QC mengikuti area/SOP; state invalid tidak lolos dari endpoint langsung.

### ACC-09 — Padanan Lemari/Rak

**Kebutuhan:** IMP-23

- **Persiapan:** Satu site, dua gudang, zona, lemari dengan dua rak/bin.
- **Tindakan:** Buat tree, label, scan, dan buka alamat roll.
- **Hasil yang wajib:** Hubungan wadah-anak serta ID konsisten; Rack/Level dapat dipakai jika maknanya setara; tidak ada hierarki paralel.

### ACC-10 — Hapus atau pindah struktur

**Kebutuhan:** IMP-25

- **Persiapan:** Bin berisi roll 100 meter dan tugas aktif.
- **Tindakan:** Hapus/pindah node, rename, dan simulasikan alamat legacy invalid.
- **Hasil yang wajib:** Hapus tak sah ditolak atau migrasi sah berjejak; rename menjaga ID; orphan terlihat dan masuk total fisik.

### ACC-11 — Shared/dedicated

**Kebutuhan:** IMP-24

- **Persiapan:** Roll owner A dan dedicated B serta shared yang mengizinkan A/B.
- **Tindakan:** Buat PA, transfer, scan receipt dan putaway ke tujuan.
- **Hasil yang wajib:** Dedicated menolak A di seluruh jalur; shared menerima sesuai grant, tanpa mengubah owner diam-diam.

### ACC-12 — Rules gabungan

**Kebutuhan:** IMP-24

- **Persiapan:** Aturan woven AND grade A, child mempersempit parent.
- **Tindakan:** Coba woven-BS, nonwoven-A, dan woven-A pada semua entry path.
- **Hasil yang wajib:** Hanya kombinasi sah diterima; child tidak membuka larangan parent; saran dan aksi akhir konsisten.

### ACC-13 — Kapasitas dan balapan aksi

**Kebutuhan:** IMP-24

- **Persiapan:** Kapasitas berdimensi yang sudah diputuskan; dua penempatan serentak.
- **Tindakan:** Tempatkan hingga batas dan melebihi batas, ubah kapasitas antara saran dan simpan.
- **Hasil yang wajib:** Hard-block atau warning mengikuti kebijakan; aksi akhir revalidasi; jumlah isi fisik tidak dihitung hanya owner/filter aktif.

## P03 — Penerimaan OCR dan transfer yang terkait pemenuhan SO

### ACC-14 — OCR per roll

**Kebutuhan:** IMP-21

- **Persiapan:** SJ contoh: 10 roll dengan ukuran tidak sama dan total diketahui.
- **Tindakan:** OCR, review kelompok, koreksi satu roll, dan validasi aktual.
- **Hasil yang wajib:** Rollcount/subtotal tepat; nilai dokumen dan aktual tetap terpisah; hasil ragu tidak diposting otomatis.

### ACC-15 — SJ hanya total

**Kebutuhan:** IMP-21

- **Persiapan:** SJ memuat total qty/rollcount tanpa ukuran masing-masing.
- **Tindakan:** Jalankan OCR dan review.
- **Hasil yang wajib:** Tidak dibuat panjang rata-rata fiktif; field per-roll yang tidak diketahui meminta input/review sesuai SOP.

### ACC-16 — Bandung-Jakarta-customer

**Kebutuhan:** IMP-26

- **Persiapan:** SO Jakarta dan roll same-owner di Bandung.
- **Tindakan:** Komitmen SO, transfer, dispatch, receipt Jakarta, staging lalu kirim customer.
- **Hasil yang wajib:** Komitmen terjaga tiap tahap; owner/LOT/tag/dasar biaya tetap; SJ transfer dan customer terpisah; arrival belum shipment customer.

### ACC-17 — Reservasi dan concurrency

**Kebutuhan:** IMP-26

- **Persiapan:** Satu roll dibutuhkan SO-A dan SO-B; transfer SO-A berjalan.
- **Tindakan:** Coba alokasi lain/transfer ulang, retry create/dispatch.
- **Hasil yang wajib:** Satu komitmen sah; demand lain tidak mengambil barang yang sudah committed; tidak ada reservation atau stock movement ganda.

### ACC-18 — Receipt parsial

**Kebutuhan:** IMP-27

- **Persiapan:** Transfer 10 roll; baru 7 diterima.
- **Tindakan:** Receipt 7, retry, lalu receipt sisa.
- **Hasil yang wajib:** Hanya 7 menjadi fisik tujuan; 3 tetap transit/exception; retry tidak menambah stok; penutupan mengikuti actual dan SOP.

### ACC-19 — Exception transfer

**Kebutuhan:** IMP-27

- **Persiapan:** Roll salah, rusak, hilang, serta gagal simpan di tengah batch.
- **Tindakan:** Submit receipt/exception dan lakukan recovery.
- **Hasil yang wajib:** Exception ber-PIC/bukti; roll salah tidak masuk stok sebagai roll expected; posting parsial/recovery dapat direkonsiliasi.

### ACC-20 — Aturan tujuan dan ownership

**Kebutuhan:** IMP-24, IMP-26, IMP-27

- **Persiapan:** Tujuan woven-only/dedicated berubah ketika barang transit; owner berbeda.
- **Tindakan:** Terima transfer dan coba fulfillment tanpa dokumen internal yang diperlukan.
- **Hasil yang wajib:** Rules dievaluasi ulang; exception terkontrol; transfer fisik tidak menggantikan transaksi jual-beli internal.

## P04 — Sales, Keep/Pending, roll picker, kuantitas SO, dan grade

### ACC-21 — Keep dan Pending bersamaan

**Kebutuhan:** IMP-02, IMP-03

- **Persiapan:** SO belum diverifikasi dan sebagian line kekurangan barang.
- **Tindakan:** Buka dua daftar, verify, terima supply parsial, kemudian batal line.
- **Hasil yang wajib:** Dua dimensi tidak dipaksakan jadi satu; total SO unik tidak ganda; shortage/status berubah menurut kebijakan sah.

### ACC-22 — Referensi supply Pending

**Kebutuhan:** IMP-03

- **Persiapan:** PR belum PO, PO parsial, MKO, dan transfer terkait demand.
- **Tindakan:** Buka product-level Pending lalu drill-down dokumen.
- **Hasil yang wajib:** Tidak ada nomor PO fiktif; qty supply tidak dipakai untuk beberapa demand melebihi kapasitasnya; ETA unknown tampil unknown.

### ACC-23 — Sales projection

**Kebutuhan:** IMP-04

- **Persiapan:** Varian warna dengan LOT/grade/origin/owner internal.
- **Tindakan:** Cari/buka/catalog/detail/SO/mobile dan respons data untuk peran Sales.
- **Hasil yang wajib:** Sales melihat artikel/warna dan ukuran yang diizinkan; atribut internal tersembunyi tetap tersedia bagi Admin Sales yang berwenang.

### ACC-24 — Stok global dan ATP

**Kebutuhan:** IMP-04

- **Persiapan:** Dua owner, reserved, QC hold, transit, incoming PO dengan beberapa demand.
- **Tindakan:** Bandingkan ringkasan Sales dengan roll/supply serta Admin Sales.
- **Hasil yang wajib:** Fisik/free/incoming/ATP tidak tercampur atau double-count; stok owner lain tidak langsung dianggap owned/sellable tanpa eligibility.

### ACC-25 — Edit alokasi roll

**Kebutuhan:** IMP-05

- **Persiapan:** Alokasi existing, picking aktif dan roll tak layak.
- **Tindakan:** Ganti pilihan, retry, dan pilih roll committed pesanan lain.
- **Hasil yang wajib:** Reservasi lama/barunya konsisten; tugas aktif diperiksa; pilihan tak layak ditolak; jumlah berasal dari roll actual.

### ACC-26 — Yard dan roll utuh

**Kebutuhan:** IMP-06

- **Persiapan:** 9 roll x 100 yard dan 1 roll x 105 yard; order 1.000 yard.
- **Tindakan:** Tinjau pilihan 10 roll/1.005 atau 9 roll/905 dengan keputusan komersial yang sah.
- **Hasil yang wajib:** Selisih terlihat; qty/order/allocation/shipment/invoice sesuai keputusan; tidak otomatis menyatakan semua qty 1.000.

### ACC-27 — Detail qty sebelum/sesudah alokasi

**Kebutuhan:** IMP-06

- **Persiapan:** Order yard/meter/kg/roll; ada line belum allocated dan partially shipped.
- **Tindakan:** Buka list/detail/picking/SJ serta rinci roll.
- **Hasil yang wajib:** Ordered/allocated/shipped/remaining jelas; unknown roll bukan nol aktual; unit berbeda tidak dijumlah sebagai satu qty.

### ACC-28 — Harga dan rekomendasi grade

**Kebutuhan:** IMP-11

- **Persiapan:** Grade A/B/non-BS, BS, customer standards, kontrak harga berbeda.
- **Tindakan:** Bandingkan harga kondisi sama dan rekomendasi alokasi.
- **Hasil yang wajib:** Non-BS sama untuk kondisi sama; kontrak/entity terms tetap sah; rekomendasi menjelaskan alasan; BS sesuai keputusan; HPP tidak disamakan.

## P05 — MD Quality, R&D existing, bahan makloon, dan sumber restock

### ACC-29 — MD Quality dan QC

**Kebutuhan:** IMP-16

- **Persiapan:** Arrival hold, retur, random check dan quality request.
- **Tindakan:** Jalankan proses serta hasil/approval masing-masing.
- **Hasil yang wajib:** PIC/objek/status jelas; stok tidak release karena nama menu berubah; fungsi baru mengikuti keputusan, bukan asumsi.

### ACC-30 — Labdip dan Handfeel existing

**Kebutuhan:** IMP-17

- **Persiapan:** SKU aktif dengan Labdip selesai.
- **Tindakan:** Buat Handfeel tambahan, approve, dan coba ulang.
- **Hasil yang wajib:** SKU tetap sama; ronde/pelaksana/approval terlacak; retry tidak membuat master/hasil duplikat; arah Handfeel ke Labdip juga valid.

### ACC-31 — Perubahan identitas dan hak MD

**Kebutuhan:** IMP-17

- **Persiapan:** MD woven/printing/knitting; uji mengubah warna/konstruksi.
- **Tindakan:** Coba request di luar grant dan approve revisi aktif.
- **Hasil yang wajib:** Hak lini/jenis uji mengikuti penugasan; perubahan identitas menggunakan jalur resmi; histori existing tidak ditimpa.

### ACC-32 — Reservasi dan issue 1:1

**Kebutuhan:** IMP-18

- **Persiapan:** Bahan 1.000 yard, kebutuhan 600 pada fixture resep 1:1.
- **Tindakan:** Reserve 600 lalu issue 600; ulangi setiap aksi.
- **Hasil yang wajib:** Setelah reserve available 400; setelah issue fisik gudang 400 dan WIP terlacak; tidak double-decrement atau double-post biaya.

### ACC-33 — Yield dan bahan kurang

**Kebutuhan:** IMP-18

- **Persiapan:** Artikel butuh jenis greige tertentu dengan yield/unit berbeda; stock bahan kurang.
- **Tindakan:** Rencanakan makloon, hitung kebutuhan dan incoming.
- **Hasil yang wajib:** Tidak memilih bahan yang salah karena nama mirip; kebutuhan mengikuti resep; konversi unknown tidak ditebak; shortage terlihat sebelum janji produksi.

### ACC-34 — Pembatalan/partial produksi

**Kebutuhan:** IMP-18, IMP-19

- **Persiapan:** Reservasi, issue parsial, hasil parsial, waste, dan cancellation.
- **Tindakan:** Proses kejadian dan retry; cek Pending serta saldo/WIP/cost.
- **Hasil yang wajib:** Hanya unissued commitment dilepas sesuai state; issued material tidak muncul kembali otomatis sebagai gudang; biaya/qty/remaining dapat direkonsiliasi.

### ACC-35 — Jalur restock

**Kebutuhan:** IMP-19

- **Persiapan:** Artikel supplier-only, makloon-only, both, dan mapping belum diketahui.
- **Tindakan:** Buat PR/PO/MKO melalui UI dan API.
- **Hasil yang wajib:** Jalur yang tidak sah ditolak; both memakai pilihan beralasan; unknown meminta mapping; stok siap/pengadaan internal sah tetap dapat memenuhi demand.

## P06 — Special Order multi-produk dan jalur desain pelanggan

### ACC-36 — Desain pelanggan dan artikel existing

**Kebutuhan:** IMP-07

- **Persiapan:** Artikel existing, customer design ready dan design needs adjustment.
- **Tindakan:** Buat OD, simpan versi, review dan teruskan.
- **Hasil yang wajib:** Ready melalui ACC sah ke proofing; needs adjustment ke Desainer; tidak auto-ACC dan tidak menimpa SKU asal.

### ACC-37 — OD dua produk

**Kebutuhan:** IMP-08

- **Persiapan:** Dua produk dengan desain/uji/qty/progres berbeda.
- **Tindakan:** Approve satu, cancel/revise lainnya, lanjut supply dan SO.
- **Hasil yang wajib:** Status tiap line serta header tepat; chain SKU/R&D/PR/MKO/SO per line; satu selesai tidak menutup seluruh OD.

### ACC-38 — OD legacy dan retry

**Kebutuhan:** IMP-07, IMP-08

- **Persiapan:** OD single-product lama sudah memiliki dokumen turunan.
- **Tindakan:** Migrasikan/adaptasi, baca melalui consumer dan retry create turunan.
- **Hasil yang wajib:** ID/link historis tetap; satu line stabil; tidak menduplikasi SKU/PR/SO atau membuat ACC historis palsu.

## P07 — Jenis sampel dan proses Admin Cutting

### ACC-39 — Tipe sampel

**Kebutuhan:** IMP-09

- **Persiapan:** Hanger/Katalog/Cutting dengan skema harga berbeda.
- **Tindakan:** Buat dari Sales dan baca sampai tugas gudang.
- **Hasil yang wajib:** Jenis fisik konsisten, tidak bercampur dengan pricing scheme/R&D tests; batas/biaya mengikuti keputusan.

### ACC-40 — Handoff Admin Cutting

**Kebutuhan:** IMP-10

- **Persiapan:** Tugas potong dengan hasil aktual dan sisa roll.
- **Tindakan:** Selesai potong, serah terima, finishing, kemudian kirim.
- **Hasil yang wajib:** Ada antrean/PIC/bukti; belum terkirim saat selesai potong; handoff tidak menjadi receipt stok baru.

### ACC-41 — Retry, cancel, dan sampel legacy

**Kebutuhan:** IMP-09, IMP-10

- **Persiapan:** Cutting partially done, request canceled, dokumen lama shipped.
- **Tindakan:** Retry cut/handoff/send dan migrasi state.
- **Hasil yang wajib:** Konsumsi tepat sekali; outstanding ditindaklanjuti; historical shipped tidak dibuka kembali tanpa alasan.

## P08 — Opname, dashboard stok, dan konsistensi meja pengguna

### ACC-42 — Opname actual roll dan RFID

**Kebutuhan:** IMP-28

- **Persiapan:** Expected roll, missing, extra, wrong-bin, serta ukuran berbeda.
- **Tindakan:** Count tree/scan, review, approve dan reconciliate.
- **Hasil yang wajib:** Identitas/jumlah/qty aktual benar; wrong-bin sebagai koreksi alamat; missing/extra tidak otomatis adjustment tanpa review.

### ACC-43 — Snapshot dan transaksi berjalan

**Kebutuhan:** IMP-28

- **Persiapan:** Sesi count dengan perubahan stok setelah snapshot dan scope bin/warehouse overlap.
- **Tindakan:** Submit/approve dan buat scope tumpang tindih.
- **Hasil yang wajib:** Perubahan ditangani sesuai cutoff/recount sah; overlap ditolak; expected tidak diganti diam-diam.

### ACC-44 — Posting adjustment dan dampak reservasi

**Kebutuhan:** IMP-28

- **Persiapan:** Qty variance memengaruhi reserved SO; approval/retry/reversal.
- **Tindakan:** Approve dua kali dan cek roll/saldo/jurnal/notifikasi.
- **Hasil yang wajib:** Adjustment/jurnal sekali; owner/unit/cost benar; demand terdampak ditindaklanjuti; RFID tidak melakukan posting kedua.

### ACC-45 — Mixed unit dan kapasitas

**Kebutuhan:** IMP-29

- **Persiapan:** Bin berisi 100 meter dan 100 kg, kapasitas berdimensi.
- **Tindakan:** Buka occupancy dan utilization pada seluruh tingkat.
- **Hasil yang wajib:** Dua subtotal; tidak 200 meter; persen dihitung pada dimensi sah atau ditampilkan tidak dapat dihitung.

### ACC-46 — Rekonsiliasi hierarchy

**Kebutuhan:** IMP-25, IMP-29

- **Persiapan:** Roll assigned, unassigned, orphan, hold, transit, lebih dari satu halaman.
- **Tindakan:** Drill-down site hingga roll dan bandingkan total.
- **Hasil yang wajib:** Bin sah + unassigned + orphan = fisik scope/unit sama; in-transit tidak dihitung di rak; pagination bukan total.

### ACC-47 — Shared capacity dan permissions

**Kebutuhan:** IMP-29

- **Persiapan:** Shared warehouse dua owner, operator hanya boleh detail owner tertentu.
- **Tindakan:** Filter owner dan cek kapasitas/rincian.
- **Hasil yang wajib:** Kapasitas fisik memperhitungkan seluruh isi; rincian yang tidak berhak tidak bocor; angka scope dijelaskan.

### ACC-48 — Meja seluruh peran

**Kebutuhan:** IMP-01

- **Persiapan:** Antrean Sales/Admin Sales/MD/Gudang/Sampel/Finance, desktop/mobile.
- **Tindakan:** Klik angka/baris, buka detail, kembali dengan filter.
- **Hasil yang wajib:** Ringkasan/rincian memakai scope dan source sama; next action sesuai role; filter dipertahankan; error/empty state dapat dipahami.

## P09 — Fingerprint langsung, log mentah, perhitungan shift, dan monitoring HR

### ACC-49 — Hardware PoC

**Kebutuhan:** IMP-35

- **Persiapan:** Unit time-attendance nyata; model/firmware/protokol dicatat.
- **Tindakan:** Atur custom ERP server dan lakukan punch.
- **Hasil yang wajib:** Data tiba langsung di ERP tanpa PC/gateway lokal; simulator/brosur saja tidak memenuhi bukti.

### ACC-50 — Native protocol receiver

**Kebutuhan:** IMP-30

- **Persiapan:** Payload nyata beberapa jenis sesuai dokumentasi model.
- **Tindakan:** Kirim event/batch/heartbeat dan payload rusak.
- **Hasil yang wajib:** Parsing/response/ACK sesuai protokol; event durable sebelum success; format tak didukung terdiagnosis tanpa menebak JSON compatibility.

### ACC-51 — Mapping dan registrasi

**Kebutuhan:** IMP-31

- **Persiapan:** Dua device dengan enrollment sama, unmapped user, inactive/unknown device.
- **Tindakan:** Punch lalu resolve/reprocess mapping.
- **Hasil yang wajib:** Employee/entity/site tepat; ambiguity disimpan untuk review; perangkat tidak sah tidak diterima sebagai sumber terotorisasi.

### ACC-52 — Raw event dan koreksi

**Kebutuhan:** IMP-32

- **Persiapan:** Log asli dan koreksi HR.
- **Tindakan:** Hitung attendance, koreksi, lalu reprocess.
- **Hasil yang wajib:** Log asal tetap; keputusan/perhitungan dapat ditelusuri; historical aggregate tanpa raw tidak diberi event fiktif.

### ACC-53 — Shift overnight

**Kebutuhan:** IMP-32

- **Persiapan:** Fixture shift 22:00–06:00 dengan punch lintas tanggal dan toleransi yang disetujui.
- **Tindakan:** Derive attendance dan review HR.
- **Hasil yang wajib:** Masuk/pulang masuk shift yang benar; tidak otomatis menjadi dua hari/alpha; fixture bukan aturan shift produksi.

### ACC-54 — Missing/multiple punches dan overtime

**Kebutuhan:** IMP-32

- **Persiapan:** Punch berulang sah, lupa keluar, libur, overtime belum approved.
- **Tindakan:** Proses lalu lihat exception dan payroll-ready status.
- **Hasil yang wajib:** Hasil mengikuti SOP; kasus tak lengkap masuk review; lembur/payroll tidak disahkan otomatis.

### ACC-55 — Offline dan kiriman ulang

**Kebutuhan:** IMP-33

- **Persiapan:** Mesin offline lalu backlog dan duplicate transport message.
- **Tindakan:** Reconnect, ulangi ACK/retry, proses batch.
- **Hasil yang wajib:** Seluruh event sah pulih; kiriman transport sama tidak ganda; dua punch sah timestamp sama tidak hilang karena dedupe kasar.

### ACC-56 — Out-of-order, drift, dan partial failure

**Kebutuhan:** IMP-33

- **Persiapan:** Jam device salah, backlog terlambat, storage gagal di tengah batch.
- **Tindakan:** Retry/reconcile dengan metadata waktu sumber.
- **Hasil yang wajib:** Pemulihan dapat dibuktikan; waktu asli tetap; exception drift terlihat; success tidak diberikan untuk event yang belum tersimpan.

### ACC-57 — Monitoring HR

**Kebutuhan:** IMP-34

- **Persiapan:** Heartbeat sukses tetapi ingestion gagal; ID belum mapping.
- **Tindakan:** Buka last contact/success, error, resolve dan reprocess.
- **Hasil yang wajib:** Kontak tidak dianggap data berhasil; HR menemukan exception dan dapat menindaklanjuti sesuai izin dengan audit.

### ACC-58 — Pilot direct tanpa perantara

**Kebutuhan:** IMP-30, IMP-35

- **Persiapan:** Unit PoC pada jaringan/lokasi pilot; mode bridge lama tersedia.
- **Tindakan:** Operasikan satu siklus kerja, disconnect/reconnect, bandingkan punch mesin dan ERP.
- **Hasil yang wajib:** Direct path terbukti sepanjang siklus; jumlah dan identitas cocok; bridge tidak diperlukan untuk path pilot; jaringan/protocol limitations tercatat.

## P10 — Integrasi menyeluruh, migrasi pilot, UAT, dan kesiapan rilis

### ACC-59 — E2E SO dan transfer

**Kebutuhan:** IMP-02, IMP-03, IMP-05, IMP-06, IMP-26, IMP-27

- **Persiapan:** SO Jakarta, stock Bandung, partial transfer/dispatch/customer fulfillment.
- **Tindakan:** Jalankan dari order sampai SJ/invoice sesuai keputusan qty.
- **Hasil yang wajib:** Keep/Pending/commitment/physical shipment dan qty komersial selaras; dua kaki perjalanan serta ownership terdokumentasi.

### ACC-60 — E2E backorder supplier/makloon

**Kebutuhan:** IMP-03, IMP-18, IMP-19, IMP-21, IMP-24

- **Persiapan:** Artikel beda sumber restock, shortage bahan, supply/receipt parsial.
- **Tindakan:** PR/PO atau PR process/MKO lalu actual receipt/fulfillment.
- **Hasil yang wajib:** Routing benar; shortage/remaining turun sesuai kejadian; material/WIP/cost dan qty supply tidak double-count.

### ACC-61 — E2E Special Order dan R&D

**Kebutuhan:** IMP-07, IMP-08, IMP-16, IMP-17

- **Persiapan:** OD multi-produk + customer design + uji existing.
- **Tindakan:** Approval per line, master/spec, supply, SO lalu shipment.
- **Hasil yang wajib:** Tidak ada SKU/dokumen ganda; progres header benar; quality gate dan PIC jelas per line.

### ACC-62 — E2E sampel dan WMS

**Kebutuhan:** IMP-09, IMP-10, IMP-20, IMP-22, IMP-28

- **Persiapan:** Cutting, handoff, transfer/putaway serta opname terkait roll.
- **Tindakan:** Jalankan antarperan/lokasi lalu reconcile.
- **Hasil yang wajib:** Tidak mengurangi stok dua kali; physical location/tag/remaining benar; stock adjustment tetap berapproval.

### ACC-63 — E2E attendance dan payroll review

**Kebutuhan:** IMP-30, IMP-31, IMP-32, IMP-33, IMP-34, IMP-35

- **Persiapan:** Unit nyata, overnight, offline, correction dan approved attendance.
- **Tindakan:** Punch sampai review HR dan consumer payroll yang relevan.
- **Hasil yang wajib:** Log/attendance/payroll input konsisten; tidak ganda; otorisasi dan exception terjaga; hardware tetap harus nyata.

### ACC-64 — Migrasi dan rollback

**Kebutuhan:** ALL

- **Persiapan:** Salinan data representatif, legacy documents dan event baru setelah upgrade.
- **Tindakan:** Dry-run, apply, rerun, rollback/forward-fix rehearsal.
- **Hasil yang wajib:** Tidak ganda/hilang; ID/link/cost historis tetap; transaksi/log baru tidak dibuang saat rollback; mapping ambiguous terlapor.

### ACC-65 — Concurrency dan recovery lintas modul

**Kebutuhan:** ALL

- **Persiapan:** Dua petugas, stale UI, retry dan kegagalan antara roll/projection/document/journal.
- **Tindakan:** Jalankan skenario konflik serta pemulihan.
- **Hasil yang wajib:** Tidak double allocation/receipt/consumption/posting; stale decision ditolak/review; invariant stok dan dokumen kembali konsisten.

### ACC-66 — UAT dan kesiapan rilis

**Kebutuhan:** ALL

- **Persiapan:** Target commit, keputusan tercatat, seluruh evidence.
- **Tindakan:** Review peran/lokasi dan cocokkan 35 tracker items.
- **Hasil yang wajib:** Seluruh requirement punya bukti API/UI/integration relevan; blocker tidak disembunyikan; belum ada bukti tidak ditandai validated.
