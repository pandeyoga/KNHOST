# Reproduksi W2-01 hingga W2-05

## Tambahan memo klien — 2026-10-03

`wave2_rnd_line_scope.py` menghasilkan `../rnd-line-scope-results.json`: tiga checkpoint API/indexed Mongo, satu kontrol daftar dan dua reproduksi cacat detail/patch W2-025. Akun fixture mempunyai permission R&D tetapi hanya lini woven. Assertion mengharapkan bug historis; validasi fix harus memakai ekspektasi penolakan dan hasil kandidat terpisah.

`client_requirements_probes.py` menghasilkan `../client-requirements-probes.json`: empat observasi penjelasan urutan roll, helper lini dan patch lot. Tidak dihitung sebagai checkpoint audit tambahan; tidak menguji konversi yard/browser atau full lifecycle lot.

Catatan koreksi histori: AR kini sudah ditriase dan termasuk hitungan terbaru; status AR tertunda pada paragraf lama di bawah sudah tidak berlaku. Gunakan coverage-summary.json sebagai jumlah terkini.


Uji WMS UOM: jalankan `python wave2_wms_uom.py` dengan KNHOST_REPO dan Mongo lokal yang sama. Menghasilkan `../wms-uom-results.json`,16 kontrol pada service konversi asli. Tidak menjalankan UI atau full penerimaan stok. `wave2_ar.py` dan `../ar-results.json` adalah pekerjaan Finance yang sudah menjalankan15 skenario tetapi belum ditriase/lapor final setelah pengguna meminta pindah domain; jangan memasukkannya ke hitungan temuan final.

Review W2-05: `python validate_w2_rfid.py` menggunakan database sintetis baru, bootstrap indeks aplikasi, gudang dedicated/shared dengan field benar, serta service roll/tag/device asli. Hasil sepuluh probe ada di `../validation/W2-05-review/results.json`. Untuk replay harness awal tanpa menimpa bukti, set `RFID_AUDIT_OUTPUT` ke path hasil baru lalu jalankan `wave2_rfid.py`; bukti replay disimpan di `../validation/W2-05-review/replay-original-results.json`. Raw hasil awal mempertahankan klasifikasi historis; koreksi F02–F07 menjadi observasi kebijakan ada di `../validation/W2-05-review/classification.json`. Baca `../12_VALIDASI_ULANG_W2_05.md` sebelum memakai prompt implementasi.

Tambahan W2-05: `python wave2_rfid.py` dengan `KNHOST_REPO` menunjuk checkout snapshot dan Mongo sintetis lokal yang sama, menghasilkan `../rfid-results.json` secara default. 24 skenario berisi label historis sepuluh kontrol, sembilan defect, dan lima perluasan Gelombang 1; review kemudian mengoreksi enam dari sembilan label defect menjadi observasi kebijakan. Dua scheduling barrier membungkus pemanggilan Motor pada service insiden asli untuk memaksa urutan baca/tulis yang berlomba; seluruh route dan fungsi bisnis tetap asli. Tidak menyalakan perangkat fisik atau browser. Setelah memperbaiki bug, ubah assertion yang tadinya mengharapkan bug, dan simpan hasil iterasi baru tanpa menimpa JSON historis.

Tambahan W2-04: `python wave2_transfer.py` dengan KNHOST_REPO dan Mongo lokal, menghasilkan `../transfer-results.json`. Sembilan skenario API untuk transfer otomatis dan pilihan roll manual. User fixture hanya berwenang pada A; W1/W2/W3 adalah gudang shared sintetis. Jangan menjalankan pada database pengguna.

Tambahan W2-03: `python wave2_count.py` menghasilkan `../count-results.json`. Sepuluh skenario API, termasuk kontrol explicit ownerB ditolak dan satu barrier pada session loader untuk race reject/approve. Semua fungsi bisnis tetap asli; fixture hanya data sintetis. Assertion yang mencari bug akan gagal setelah bug diperbaiki, sehingga validasi perbaikan harus memakai expected behavior yang benar serta disimpan sebagai iterasi baru.

Tambahan W2-02: jalankan `python wave2_claim_payment.py` dengan KNHOST_REPO dan Mongo lokal yang sama. Hasilnya `../claim-payment-results.json`, terpisah dari putaran pertama. 11 skenario; F02/F03 dan C07 menggunakan barrier penjadwalan yang membungkus fungsi asli dan dikembalikan dalam finally. Tidak memalsukan hasil assessment/GL. Perintah dan protokol database sintetis di bawah tetap berlaku. Buat salinan hasil historis sebelum menjalankan validasi perbaikan.

Snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Harness memakai Python, dependency backend yang kompatibel, MongoDB lokal port27919 dan database baru `knhost_audit_<uuid>`. Tidak memakai database produksi, .env proyek, login demo remote atau perangkat eksternal. MongoDB8.0.12 dan Python3.12 digunakan saat audit. Daftar dependency historis dilampirkan sebagai referensi lingkungan, bukan lockfile deployment.

Set environment `KNHOST_REPO` ke checkout snapshot, lalu jalankan `python wave2_makloon.py` dari folder ini. Pastikan MongoDB lokal sudah berjalan dengan bind127.0.0.1. Hasil ditulis ke `../makloon-results.json`; salin hasil historis ke direktori iterasi baru sebelum menjalankan validasi perbaikan agar bukti lama tidak ditimpa.

Skrip membutuhkan seluruh import backend `server`, tetapi tidak menjalankan lifespan/startup scheduler. Mongo menggunakan database sintetis berbeda setiap run. Fixture order dibuat langsung; issue/receive/posting memakai fungsi asli. F01/F02 melalui API dengan sesi lokal sintetis. F03 melalui helper `_post_mko`, bukan seluruh lifecycle GRN HTTP. Assertion cacat saat kode sudah benar akan gagal: itu sinyal untuk memperbarui regression test dengan expected behavior benar, bukan mempertahankan bug. Seed tidak memakai data bisnis pengguna. Data sintetis tidak dihapus otomatis supaya bisa diperiksa.


## GRN receiving — 2026-10-02

Jalankan `wave2_grn_partial.py`, `wave2_grn_capacity.py`, dan `wave2_grn_recovery.py` dengan KNHOST_REPO dan Mongo lokal sesuai setup di atas. Masing-masing membuat database sintetis baru dan memakai indeks aplikasi. Capacity melakukan501 panggilan hitung asli. Recovery memasang satu fault AutoReconnect sebelum update roll kedua lalu memulihkan hook; pelepasan lock memakai helper aplikasi, bukan pengujian otorisasi admin. Hasil tersimpan pada grn-partial-results.json, grn-capacity-results.json, grn-recovery-results.json. Reproducer mengassert perilaku cacat historis; keberhasilan menjalankannya bukan bukti bug diperbaiki. Untuk validasi fix simpan hasil kandidat terpisah dengan ekspektasi bisnis yang benar.


## Lintas flow — 2026-10-03

`wave2_qc_flow.py` (14 checkpoint), `wave2_sales_flow.py` (19), `wave2_projection.py` (8), `wave2_ar.py` (15, review bukti terdahulu) memakai setup KNHOST_REPO/Mongo yang sama. AR sebelumnya pending kini sudah direplay dan ditriase di laporan16. Bukti AR awal tersimpan di validation/AR-review/original-results.json. Projection memasang barrier pada tulis rebuild lama dan memanggil hold_stock asli; semua operasi DB tetap asli. Sales memakai fixture master dan opening roll lalu API sepanjang lifecycle. QC memakai GRN asli, API QC, kemudian service approval supplier return. Tidak menjalankan scheduler/lifespan/browser/perangkat. Jalankan dengan PYTHONIOENCODING=utf-8 di Windows. Simpan setiap validasi kandidat pada folder baru; jangan menganggap reproducer yang mengharapkan cacat sebagai regression test perbaikan.

## Refund, advance, multi-PO dan GL — 2026-10-03

Jalankan `wave2_advance.py` (8), `wave2_multi_po.py` (8), `wave2_cash_refund.py` (8), `wave2_gl_close.py` (10), `wave2_gl_capacity.py` (7) dengan setup yang sama. Capacity menanam100.001 jurnal sintetis, bukan menjalankan100.001 posting bisnis. Refund mengulang19 kontrol sales sebagai fixture (tidak dihitung ulang), lalu menyetel klasifikasi cash; bukan pengujian tender awal. Fault cash-ledger sebelum write dan barrier baca advance dipulihkan di finally. GL close memakai service asli dengan dataset manual, bukan seluruh subledger atau permission HTTP. Seluruh lima run selesai; hasil parsial tidak dimasukkan total. Kegagalan awal harness refund hanya salah nama expected status (`refunded` vs enum asli `refund_settled`), diperbaiki lalu seluruh harness direplay. Source aplikasi tidak berubah.

## Produksi, payroll dan bank — 2026-10-03

Jalankan `wave2_production_flow.py` (11), `wave2_payroll_flow.py` (11), `wave2_bank_flow.py` (8) dengan setup yang sama. Produksi menyisipkan exception sebelum bahan kedua, lalu memulihkan helper dan mengulang completion. Payroll memakai services asli dan pay via ASGI, feature toggles BPJS/PPh dimatikan untuk fixture aritmetika; tidak memvalidasi tarif/pajak. Bank memakai master asli tetapi cash transactions seeded untuk oracle/capacity. Semua tiga run selesai; replay payroll API menggantikan run service dan tidak menambah hitungan. Simpan validasi kandidat di folder baru agar bukti snapshot lama tidak tertimpa.

## Recovery dan kapasitas produksi — 2026-10-03

`wave2_production_recovery.py` (8 checkpoint) memakai close/reopen periode asli untuk menolak posting GL; satu barrier get_bom menjadwalkan same-WO stale completion. `wave2_production_capacity.py` (5) menanam5001 input roll dari template service lalu menjalankan complete asli termasuk5000 mutasi dan movement. Keduanya selesai pada snapshot yang sama, tanpa browser/hardware/crash proses. Setup KNHOST_REPO/Mongo mengikuti petunjuk di atas; simpan validasi kandidat terpisah. Assertion cacat historis bukan acceptance fix.
