# Addendum verifikasi frontend — main 20 Oktober 2026

Baseline terbaru: **`8dab383f764df80737bfe02f887422b3fd72aa70`**.  
Dibandingkan dengan baseline audit sebelumnya `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`.

**Hasil: tujuh temuan frontend WMS/Finance sebelumnya masih terbukti pada sumber terbaru; belum ada yang dapat ditutup.** Ini merupakan verifikasi terhadap commit baru, bukan sekadar meneruskan status laporan lama.

## Metode

1. Memeriksa diff dan identitas Git blob untuk sumber frontend dan kontrak backend terkait tiap temuan.
2. Memeriksa perubahan pemanggil `IntercoView`, router layar, konfigurasi izin, serta perilaku role acuan.
3. Menjalankan ulang **18 kasus render/formatter** dengan JSX yang dibaca langsung menggunakan `git show` pada SHA terbaru. State dikontrol dan efek jaringan tidak dieksekusi; bukti ini bukan klik browser maupun transaksi bisnis lengkap.

Bukti tersedia dalam `render-results-8dab.json`. `latest-8dab.json` memuat status, referensi terbaru, serta identitas blob lama/baru per berkas. `revalidate_latest.py` hanya membaca Git dan menulis artefak audit. Kode aplikasi, checkout, dan database tidak diubah.

## Status setiap temuan

| ID | Status terbaru | Referensi terbaru yang diverifikasi | Bukti |
|---|---|---|---|
| **FE-WF-01 — pilihan Interco tidak bekerja** | **Masih terbuka, P1** | `KNSelect.jsx:149`, `:189`; `IntercoCreateModal.jsx:109,112,115,118,137`; `IntercoPanels.jsx:32`; `IntercoSettlementModal.jsx:107,111,115` | Kesembilan kontrol dan komponen tidak berubah. Eksekusi callback pilihan buyer/payee pada sumber terbaru kembali menghasilkan `stateUpdates=[]`. |
| **FE-WF-02 — tombol persetujuan transfer hanya untuk literal manager** | **Masih terbuka, P2** | `wms/transfer/TransferDetailModal.jsx:219`; `backend/routers/transfers.py:523,633` | Detail dan permission API tidak berubah. Render manager menampilkan Setujui; admin dan custom manager berizin tidak. |
| **FE-WF-03 — Finance tidak mendapat tombol keputusan selisih pembayaran** | **Masih terbuka, P2** | `finance/payments/PaymentVarianceQueue.jsx:53,54,215,217`; `backend/permissions_config.py:377`; `backend/routers/payment_variance.py:144,170` | Default Finance masih memiliki `payment_variance.decide`; cabang render belum mengikutinya. Finance/custom Finance tetap tidak menampilkan tombol. |
| **FE-WF-04 — kontrol role kustom WMS/Store Credit tidak ekuivalen** | **Masih terbuka, P2** | `wms/LocationPutawayView.jsx:18,37,141,150`; `wms/transfer/TransferReceiptPanel.jsx:13,25,86,103`; `finance/StoreCreditView.jsx:37,202,244`; `backend/role_registry.py:293,298,299` | Berkas kontrol tidak berubah. Role standar warehouse admin/manager mendapat kontrol; role kustom berizin ekuivalen tidak. Backend tetap mendukung role acuan. Cabang exception transfer tetap dibuktikan statis, bukan transaksi browser. |
| **FE-WF-05 — error awal penerimaan menjadi loading tanpa akhir** | **Masih terbuka, P2** | `wms/transfer/TransferReceiptPanel.jsx:31,55,101` | Berkas tidak berubah. Render `data=null` dengan error terisi tetap menampilkan loading tanpa pesan error. |
| **FE-WF-06 — Neraca belum diketahui ditampilkan Seimbang** | **Masih terbuka, P2** | `finance/FinancialStatementsParts.jsx:113,122`; `finance/FinancialStatementsView.jsx:294` | Kedua berkas tidak berubah. `balanced=undefined/null` kembali menghasilkan teks Seimbang. |
| **FE-WF-07 — tooltip defisit kas ditampilkan positif** | **Masih terbuka, P2** | `finance/CashFlowForecastView.jsx:38,70,75` | Berkas tidak berubah. Formatter sumber terbaru mengubah saldo -100 menjadi Rp100. |

Seluruh path frontend pada tabel relatif terhadap `frontend/src/features/`, kecuali `KNSelect.jsx` yang berada di `frontend/src/components/` dan path backend yang ditulis lengkap. File JSON memberikan path lengkap relatif repo untuk setiap lokasi.

## Dampak perubahan main terhadap interpretasi

- **IntercoView memang berubah**, terutama penempatan tab retur ke menu retur terpadu. Jalur transaksi dan settlement asal masih ada. Tombol settlement kini berada pada `IntercoView.jsx:212` dan preset penerima pada `:315`; penerima tetap kosong ketika dibuka dari tombol utama. Karena callback penerima masih salah, pembaruan tab retur tidak menyelesaikan FE-WF-01.
- **Konfigurasi izin berubah**, tetapi penambahannya mengenai pencatatan cutloss/kompensasi retur serta perubahan istilah. Hak Finance `payment_variance.decide` di baris 377 tetap ada. FE-WF-03 tetap relevan.
- **Role registry berubah pada label Admin Sample**; fungsi `role_in` dan dukungan role acuan tidak berubah. FE-WF-04 tetap berlaku.
- **Helper frontend baru `canCurrent` dan `canSeeGrade` tersedia**, tetapi berkas yang menyebabkan FE-WF-02/03/04 tidak menggunakannya. Ketersediaan helper belum membuktikan seluruh kontrol telah mengikuti izin efektif.
- **AppViewRouter merutekan retur antar-PT secara terpadu**; rute `interco-transactions` masih membuka IntercoView yang mengandung form bermasalah. Tidak ada dasar menandai form sebagai tidak terpakai.
- **Berkas frontend Export tidak berubah**. Addendum ini tidak menjalankan kembali job export backend dan tidak menutup temuan export lama dari audit induk.

## Kandidat yang tetap dikecualikan

- Pembatasan device RFID hanya untuk Admin tidak dinyatakan sebagai bug role kustom, karena `custom_role_service.py:193–195` masih melarang Admin sebagai template.
- Missing dependency `selectedEntity` pada komponen tidak otomatis berarti data basi: remount view berdasarkan entitas masih ada pada `App.js:542–546`.

Rencana perbaikan dan titik selesai tiap temuan tetap mengikuti `REVIEW_FRONTEND_WMS_FINANCE_EXPORT.md`; gunakan referensi terbaru dalam addendum ini. Penyelesaian harus dibuktikan dengan interaksi browser dan pengujian izin, pemulihan error, serta keluaran Finance. Kelulusan render saja belum menyatakan seluruh layar atau alur WMS/Finance tuntas.
