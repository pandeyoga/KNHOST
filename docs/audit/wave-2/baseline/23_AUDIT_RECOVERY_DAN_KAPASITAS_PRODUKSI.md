# Produksi: periode tertutup, retry, konkurensi, cancel dan kapasitas roll

Tanggal2026-10-03; snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Source tidak diubah. Ini tambahan bukti Gelombang2, bukan validasi perbaikan. Gunakan bersama [laporan21](21_AUDIT_PRODUKSI_PAYROLL_BANK.md) dan [prompt terbaru](24_PROMPT_RECOVERY_PRODUKSI.md).

## Metode dan hasil

| Bukti | Checkpoint | Metode |
|---|---:|---|
| [production-recovery-results.json](production-recovery-results.json) | 8 | 1 kontrol,7 pendalaman GN-06. Service close/reopen periode, WO, konsumsi roll dan GL asli pada Mongo berindeks. Periode ditutup melalui service aplikasi; exception GL bukan mock. Satu barrier baca BOM untuk menjadwalkan dua complete WO yang sama. |
| [production-capacity-results.json](production-capacity-results.json) | 5 | 3 kontrol,2 reproduksi W2-024.5.001 input roll sintetis dari template roll asli, nomor unik dan lot opening bersama; complete benar-benar menjalankan mutasi5.000 roll dan movement. Bukan5.001 proses GRN. |

Tambahan13 checkpoint; total239:173 kontrol,34 reproduksi cacat W2,6 observasi kebijakan,26 pendalaman Wave1;24 ID W2. Tidak ada penambahan hitungan untuk replay. Checkpoint bukan flow independen atau persentase coverage. Tidak menjalankan browser, scheduler, mesin produksi atau crash proses. Data nominal kecil sengaja memudahkan rekonsiliasi.

## GN-06: kegagalan GL menghasilkan efek stok yang tidak dapat dipulihkan dengan retry biasa

**Lokasi utama:** [production_service.py:358](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L358), [pembuatan output:404](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L404), [posting GL:413](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L413). Final update WO dilakukan sesudah efek tersebut. [gl_service.py:1574](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L1574) idempotent hanya untuk jurnal berdasarkan WO.

Fixture: output5, bahan A10@10 dan B5@20, biaya bahan200; overhead15; nilai output215. Awal bahan A20/B20. WO dirilis. Periode bulan berjalan menurut waktu aplikasi ditutup dengan `close_period`, kemudian complete dipanggil.

1. **Kontrol C01:** posting overhead benar-benar ditolak `ClosedPeriodError`.
2. **E01/E02:** walau posting ditolak, output5 sudah ada; bahan A tinggal10 dan B15. WO masih released, `produced_roll_ids` kosong dan jurnal overhead0.
3. **E03:** periode dibuka melalui `reopen_period`, complete diulang. Hasil dua roll output total10; WO completed hanya mencatat satu roll dan `produced_qty=5`.
4. **E04:** dua output membawa overhead total30, tetapi GL hanya15. Tidak cukup memeriksa jurnal seimbang: nilai persediaan dan GL sudah berbeda.

**Akar:** efek konsumsi/output terjadi sebelum GL guard; tidak ada operation checkpoint yang merekam output pertama untuk dilanjutkan. Retry mengulang konsumsi dan pembuatan output. Preflight periode sebelum stok dapat membantu kasus ini, tetapi tetap memerlukan recovery untuk kegagalan setelah preflight. Menghapus output pertama secara sembarang juga tidak aman bila telah dipakai proses lain.

## GN-06: dua complete WO yang sama dan pembatalan sesudah kegagalan

**E05/E06:** caller pertama sudah membaca released lalu ditahan pada pengembalian BOM. Caller kedua menyelesaikan WO. Caller pertama dilanjutkan dan tetap menyelesaikan berdasarkan snapshot lama. Terbentuk dua output total10, sementara WO hanya menyimpan satu roll. GL overhead hanya15 karena helper idempotent mengembalikan `None` untuk posting yang sudah ada; writer terakhir mengubah `je_id` menjadi string kosong. Jadi uniknya jurnal tidak mencegah duplikasi stok dan bahkan referensi jurnal hilang dari WO.

Barrier hanya mengendalikan urutan eksekusi; helper stok/GL tetap asli. Ini bukti interleaving yang mungkin terjadi, bukan pengukuran frekuensi race di produksi. Belum mencakup dua WO berbeda yang berebut roll sama.

**E07:** pada WO lain, complete gagal karena periode tertutup setelah output dibuat. `cancel_work_order` mengizinkan released→cancelled. Output5 masih ada, bahan sudah berkurang, overhead GL0. Guard berdasarkan status saja tidak mendeteksi efek parsial. Cancel harus menolak atau menjalankan kompensasi yang tervalidasi, dengan pemeriksaan pemakaian output dan movement/jurnal terdahulu.

Temuan ini memperkuat GN-06; tidak membuat tiket baru untuk setiap gejala. Tracker Wave1 tidak diubah karena sedang ditangani agent lain.

## W2-024 — P1: WO completed meskipun konsumsi bahan terpotong pada5.000 roll

**Lokasi:** [production_service.py:319](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L319) mengambil maksimal5.000 roll; [354](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L354) mengembalikan consumed_qty tanpa memastikan remaining need nol; [389](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L389) menerima jumlah aktual itu, lalu [405](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L405) membuat output sebanyak planned_qty.

**Reproduksi:** BOM satu bahan, rasio1:1, overhead0. Ada5.001 roll bahan masing-masing1 meter @10. Planned output5.001. Preflight agregasi membaca available5.001 dan sufficient=true. Complete kemudian hanya mengonsumsi5.000 roll, tetapi berstatus completed dengan output5.001; `consumed[0].qty=5000`, biaya bahan50.000. Satu roll input1 meter tetap available. Agregasi movement independen memastikan tepat5.000 konsumsi, total−5.000, sehingga bukan sekadar tampilan counter yang salah.

**Akar:** query ketersediaan mencakup seluruh stok, tetapi query eksekusi dibatasi. Tidak ada postcondition actual consumed=required sebelum output. Sistem menciptakan output berdasarkan rencana walau input yang diterapkan kurang. Jangan menyimpulkan bahwa ini hanya masalah laporan seperti W2-021: di sini mutasi bisnis dan yield yang salah benar-benar terjadi. Karena itu W2-024 mempunyai tiket tersendiri, terkait GN-06 untuk atomicity/recovery.

**Dampak:** konsumsi bahan kurang, yield terlihat berlebih dan unit cost output dihitung dari biaya input yang kurang. Batas kasus adalah satu WO yang memerlukan lebih dari5.000 roll untuk satu komponen; tidak semua WO besar terkena. Distribusi ukuran roll menentukan kapan batas tercapai.

**Perbaikan:** iterasi kandidat konsumsi tanpa batas diam-diam, reservasi/CAS kuantitas aktual, lalu verifikasi invariant sebelum finalisasi output. Bila jumlah tidak cukup karena race atau limit, tidak boleh menandai selesai; efek yang terlanjur terjadi harus bisa dilanjutkan/dikompensasi deterministik. Jangan sekadar menaikkan konstanta atau menambah raise setelah5.000 mutasi tanpa recovery.

## Cakupan setelah putaran ini

PROD-02 kini memiliki bukti failure GL nyata, reopen/retry dan drift nilai. PROD-04 bertambah bukti shortage eksekusi akibat kapasitas. Masih belum seluruh produksi tercover: dua WO berebut bahan, yield/waste/byproduct, unit campuran, full UI, physical execution, crash setiap write dan seluruh permission. Semua cacat yang dilaporkan tetap open pada snapshot ini; belum ada validasi kandidat fix.
