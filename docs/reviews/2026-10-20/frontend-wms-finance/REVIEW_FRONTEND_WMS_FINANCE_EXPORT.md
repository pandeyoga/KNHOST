# Audit frontend WMS, Finance, RFID, dan Export

**ERP Kain Nussantara — verifikasi perubahan dan kelengkapan kontrol layar**  
Tanggal finalisasi: 20 Oktober 2026. Baseline: `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`.  
Sumber: `work/KNHOST-plan-audit-2026-10-19`, tanpa mengubah kode aplikasi atau data operasional.

## Cara membaca hasil

Audit ini menelusuri kontrol layar ke fungsi penanganan dan kontrak API. Sejumlah kondisi diuji dengan menjalankan JSX asli yang ditranspilasi, menggunakan state terkontrol. Efek jaringan dan komponen pendukung diganti stub untuk mengisolasi keputusan render. Ini membuktikan kondisi tombol dan formatter, **bukan bukti klik browser atau transaksi ujung ke ujung**. Parent audit melakukan pengujian browser terpisah.

`render-results.json` berisi hasil eksekusi; `render_checks.cjs` adalah harness yang dapat diulang. `select-contract-results.json` berasal dari pemeriksaan AST seluruh `frontend/src` untuk satu kontrak khusus, yaitu penggunaan `onChange` pada `KNSelect`. Pemindaian tersebut tidak menandakan seluruh logika setiap file telah diaudit.

## Ringkasan

Terdapat **7 temuan lokal**, terdiri dari satu cacat kontrak komponen yang mengenai 9 kontrol, tiga temuan konsistensi wewenang, satu kegagalan pemulihan tampilan, dan dua kesalahan penyajian informasi Finance. Temuan wewenang memiliki pola akar masalah yang sama dan boleh dikonsolidasikan pada tracker utama. Tidak ditemukan tombol tanpa handler pada berkas yang diperiksa, tetapi ada handler yang tidak pernah dipanggil dan tombol yang tidak ditampilkan kepada pengguna berwenang.

| ID | Prioritas | Dampak |
|---|---|---|
| FE-WF-01 | P1 | Sembilan pilihan di transaksi antar-PT tidak mengubah state; pembuatan transaksi manual dan settlement dari tombol utama terhambat. |
| FE-WF-02 | P2 | Admin dan role berizin selain literal `manager` tidak mendapat tombol Setujui/Tolak pada detail transfer. |
| FE-WF-03 | P2 | Role Finance memiliki `payment_variance.decide` tetapi tombol Putuskan disembunyikan. |
| FE-WF-04 | P2 | Beberapa kontrol WMS dan saldo pelanggan mengabaikan peran kustom yang sah. |
| FE-WF-05 | P2 | Kegagalan pertama memuat penerimaan transfer berubah menjadi indikator memuat tanpa akhir. |
| FE-WF-06 | P2 | Status Neraca menunjukkan Seimbang ketika hasil belum tersedia atau permintaan gagal. |
| FE-WF-07 | P2 | Tooltip proyeksi kas menghilangkan tanda minus pada defisit kas. |

## FE-WF-01 — Pilihan transaksi antar-PT tidak bekerja

**Letak:**

- `frontend/src/features/finance/interco/IntercoCreateModal.jsx:109`, `:112`, `:115`, `:118`, `:137`: PT penjual, PT pembeli, mode harga, mode PPN, dan produk.
- `frontend/src/features/finance/interco/IntercoPanels.jsx:32`: filter peran transaksi.
- `frontend/src/features/finance/interco/IntercoSettlementModal.jsx:107`, `:111`, `:115`: PT pembayar, PT penerima, metode pembayaran.
- Kontrak komponen: `frontend/src/components/KNSelect.jsx:149` menerima `onValueChange`; `:189` hanya memanggil callback tersebut. Jalur combobox di `:49`–`:55` juga hanya mengenal `onValueChange`.

**Pemicu dan hasil:** Buka Transaksi Antar-PT → transaksi baru. Pilih PT pembeli atau produk. Parent mengirim `onChange`, tetapi komponen tidak mengambil prop itu. State pembeli tetap kosong dan validasi submit di `IntercoCreateModal.jsx:66` menghentikan transaksi dengan pesan PT wajib dipilih. Produk juga tidak bisa dipilih. Di settlement, tombol utama `IntercoView.jsx:209` membuka dialog tanpa preset penerima; `:312` mengirim penerima kosong sehingga pengguna tidak dapat melengkapinya. Filter peran juga tidak pernah berubah.

**Bukti eksekusi:** Harness memanggil handler pilihan dari `KNSelect` asli untuk kontrol pembeli dan penerima. Prop parent `onChange` adalah function; prop yang diterima komponen `onValueChange` adalah `undefined`; jumlah perubahan state yang tercatat adalah nol. AST menemukan sembilan lokasi dan tidak mengalami kesalahan parse.

**Yang diharapkan:** Pilihan mengubah state dan kandidat/dokumen mengikuti pilihan tersebut. Pemilihan kontrol belum boleh menerbitkan dokumen; penulisan baru terjadi setelah submit.

**Rencana perbaikan:** Gunakan kontrak callback yang benar di sembilan lokasi, lalu uji klik pilihan nyata dalam browser. Uji transaksi baru sampai preview/submit lokal yang sah, settlement dari tombol utama, settlement dengan preset, dan filter penjual/pembeli. Pertahankan aturan bayar penuh per transaksi dan larangan netting.

**Titik selesai:** Semua pilihan bertahan setelah dipilih; payload submit memuat pihak, produk, harga, dan mode pajak yang dipilih; filter benar-benar mengubah daftar. Tidak cukup hanya mengganti nama prop tanpa pengujian browser. Berkaitan dengan LN-024-T02 dan konsistensi layar pada LN-010-T01.

## FE-WF-02 — Tombol persetujuan transfer hilang untuk pengguna berwenang

**Letak:** `frontend/src/features/wms/transfer/TransferDetailModal.jsx:219` membatasi Setujui/Tolak ke `user.role === "manager"`. Handler berada di `TransferManagement.jsx:136` dan `:161`. Backend `backend/routers/transfers.py:523` memakai `transfer.approve`; penolakan di `:633` memakai `transfer.reject`.

**Pemicu dan hasil:** Admin membuka transfer berstatus `waiting_approval`. Tombol persetujuan dan penolakan tidak tampil, meskipun izin API tersedia. Role kustom atau role lain yang diberi izin yang sama mengalami hal serupa. Sebaliknya, literal manager tetap ditawari tombol meskipun izin terkait dicabut.

**Bukti eksekusi:** Render detail transfer yang sama dengan izin `transfer.approve`/`reject`: manager menampilkan Setujui; admin dan custom manager tidak. Ini bukti kondisi render, bukan eksekusi approval melalui API.

**Rencana perbaikan:** Gunakan izin efektif masing-masing aksi untuk tombol Setujui dan Tolak. Jangan menggabungkan dua aksi jika izinnya berbeda. Pengecualian aturan penyimpanan tetap diperiksa sesuai authority supervisor backend. UI perlu menampilkan hasil penolakan server jika izin berubah saat dialog terbuka.

**Titik selesai:** Admin, manager, dan role kustom dengan izin yang sama memiliki kontrol yang sama; pengguna tanpa izin tidak melihat aksi tersebut; API langsung tetap memeriksa izin dan scope. LN-010-T01 belum boleh dinyatakan selesai untuk halaman ini.

## FE-WF-03 — Finance tidak dapat menekan Putuskan pada antrean selisih pembayaran

**Letak:** `frontend/src/features/finance/payments/PaymentVarianceQueue.jsx:53` dan `:54` menggunakan daftar nama role untuk `canDecide` dan `canReverse`. Tombol keputusan berada di `:215`–`:219`. Backend `backend/routers/payment_variance.py:144` dan `:170` meminta `payment_variance.decide`. Default role Finance memang memiliki izin tersebut pada `backend/permissions_config.py:377`.

**Pemicu dan hasil:** Finance masuk ke Rencana Pembayaran → Selisih Pembayaran dengan sebuah penerimaan yang masih perlu keputusan. Baris muncul, tetapi tombol Putuskan tidak ada. Ini bukan permintaan menambah hak baru: hak tersebut sudah diberikan oleh konfigurasi backend.

**Bukti eksekusi:** Baris pending yang sama dengan izin `payment_variance.decide`: admin menampilkan tombol; Finance dan custom Finance tidak.

**Rencana perbaikan:** Tentukan visibilitas dari izin efektif, lalu tetap hormati pembatasan jenis keputusan dan batas nominal dari kebijakan backend. Cocokkan pula tombol anulir dengan authority sebenarnya; jangan hanya memperluas daftar nama role.

**Titik selesai:** Finance dapat membuka dialog keputusan yang memang diizinkan, pilihan sensitif mengikuti kebijakan, dan backend masih menolak keputusan di luar kewenangan. Uji izin dicabut saat dialog terbuka dan hindari klaim lulus hanya dari render tombol.

## FE-WF-04 — Peran kustom yang sah kehilangan kontrol WMS dan saldo pelanggan

**Letak dan hubungan:**

| Layar | Kondisi frontend | Kontrak backend |
|---|---|---|
| Lokasi & Penempatan | `LocationPutawayView.jsx:18`, `:37`, `:141`, `:150` memakai literal Admin Gudang/Manager/Admin | `routers/warehouses.py:136` meminta `warehouse.update`; `:140` memeriksa supervisor; `services/placement_rules.py:49`–`:51` memakai `role_in`, yang mengenali `base_role`. |
| Penerimaan transfer | `transfer/TransferReceiptPanel.jsx:13`, `:25`, `:86`, `:103` membatasi alasan pengecualian dan penyelesaian exception dengan literal role | Backend transfer memeriksa izin aksi dan supervisor yang mengenali role acuan. |
| Store Credit | `finance/StoreCreditView.jsx:37`, `:202`, `:244` membatasi penyesuaian dan pembalikan pada literal admin/manager | `routers/store_credit.py:118`, `:131` memakai `ar_receipt.void`. |

**Pemicu dan hasil:** Buat role kustom dari `warehouse_admin` atau `manager` yang sah dengan izin yang relevan. Pengguna tersebut dapat memenuhi kontrak API, tetapi editor struktur menjadi baca saja, kontrol pengecualian tidak muncul, atau tombol penyesuaian saldo tidak muncul. `backend/role_registry.py:293`–`:299` secara eksplisit mendukung pencocokan role acuan.

**Bukti eksekusi:** Editor struktur dengan `warehouse.update`: role standar `warehouse_admin` mendapat `canEdit=true`, role kustom mendapat `false`. Ledger saldo dengan `ar_receipt.void`: manager mendapat `canAdjust=true`, custom manager mendapat `false`. Cabang penerimaan transfer dibuktikan melalui penelusuran kode, belum melalui transaksi/browser tersendiri.

**Rencana perbaikan:** Selaraskan kontrol dengan izin efektif dan authority server. Untuk aksi yang memang memerlukan supervisor, gunakan informasi authority yang konsisten dengan server dan tidak hanya nama role. Jangan meniadakan pagar scope lokasi atau authority pengecualian. Tambahkan pasangan uji role standar dan role kustom yang izinnya identik.

**Titik selesai:** Role kustom dengan izin/authority ekuivalen mendapat kemampuan layar ekuivalen; pencabutan izin menghilangkan aksi. Uji gabungan bukan hanya izin menu, tetapi tab, kontrol, dan endpoint terkait. Ini langsung terkait LN-010-T01.

**Kandidat yang ditolak:** Pengelolaan device RFID dibatasi literal Admin di layar, tetapi Admin memang dilarang sebagai template role kustom pada `custom_role_service.py:193`–`:195`. Karena itu kasus sintetis `custom_admin` **tidak dihitung sebagai temuan**. Perlu keputusan bisnis tersendiri bila reserved authority tersebut ingin diubah.

## FE-WF-05 — Error pertama penerimaan transfer tidak terlihat dan tidak bisa dicoba ulang

**Letak:** `frontend/src/features/wms/transfer/TransferReceiptPanel.jsx:27`–`:33` menyimpan error ketika GET `/transfers/{id}/receipt` gagal. Namun `:55` langsung mengembalikan indikator Memuat jika `data` kosong. `ErrorNotice` baru berada di `:101`, setelah early return tersebut.

**Pemicu dan hasil:** Buka transfer yang sudah dikirim ketika permintaan pertama penerimaan gagal, misalnya server sementara tidak tersedia atau akses sumber berubah. `err` terisi dan `data` tetap null. Layar terus menampilkan “Memuat penerimaan…”; pesan error dan tombol coba ulang tidak ada. Load tidak dijadwalkan ulang karena dependency transfer ID tetap sama.

**Bukti eksekusi:** Render dengan `data=null` dan pesan error terisi menghasilkan elemen `transfer-receipt-loading`; elemen `transfer-receipt-error` tidak ada.

**Rencana perbaikan:** Pisahkan state loading, data kosong, dan error. Render error serta aksi retry sebelum early return atau gabungkan tiga keadaan secara eksplisit. Saat data pernah berhasil dimuat, tandai bila pembaruan berikutnya gagal agar data lama tidak dianggap baru.

**Titik selesai:** Pada kegagalan pertama, operator melihat sebab dan dapat menekan Coba lagi di panel yang sama. Retry sukses menampilkan roll aktual tanpa membuka ulang halaman dan tanpa menggandakan penerimaan.

## FE-WF-06 — Neraca dinyatakan seimbang tanpa hasil perhitungan

**Letak:** `frontend/src/features/finance/FinancialStatementsParts.jsx:113` menggunakan `const ok = balanced !== false`; `:122` menampilkan “Seimbang”. Parent `FinancialStatementsView.jsx:293`–`:294` merender kartu dengan `data?.balanced`, sementara `data` dimulai null dan gagal muat tidak mengisinya.

**Pemicu dan hasil:** Buka Neraca sebelum hasil pertama tiba, atau saat permintaan pertama gagal. `balanced` menjadi undefined; kartu berwarna hijau dan bertuliskan Seimbang. Dismissing error tidak meniadakan status itu. Tidak ada dasar menyatakan neraca seimbang ketika hasil belum ada.

**Bukti eksekusi:** `undefined → Seimbang`, `null → Seimbang`, `false → Tidak Seimbang`, `true → Seimbang`.

**Rencana perbaikan:** Gunakan tiga keadaan: belum diketahui/memuat, seimbang, tidak seimbang. Sembunyikan hasil atau tandai data lama saat permintaan baru gagal. Kartu jumlah sebaiknya juga membedakan belum dimuat dari nol yang benar-benar dihitung.

**Titik selesai:** Sebelum respons sah, status netral; hanya boolean true dari hasil yang tampil sebagai Seimbang. Uji loading, error, retry, dan perubahan periode/entitas. Temuan ini mengenai tampilan, tidak menyatakan mesin neraca salah menghitung.

## FE-WF-07 — Tooltip mengubah defisit kas menjadi angka positif

**Letak:** `frontend/src/features/finance/CashFlowForecastView.jsx:38` menyimpan `cumulative_cash` dengan tandanya. `:70` memakai `formatCurrency(Math.abs(v))` untuk **semua** seri, termasuk garis “Posisi Kas Kumulatif” di `:75`.

**Pemicu dan hasil:** Posisi kas kumulatif suatu bucket adalah minus Rp100. Grafik tetap berada di bawah nol, tetapi tooltip menampilkan `Rp100`, bukan `-Rp100`. Untuk kolom outflow, magnitude positif bisa disengaja, tetapi tidak berlaku pada saldo kumulatif.

**Bukti eksekusi:** Formatter Tooltip asli diberi `-100` dengan nama seri Posisi Kas Kumulatif dan menghasilkan `Rp100`; formatter uang standar dengan nilai yang sama menghasilkan `-Rp100`.

**Rencana perbaikan:** Bedakan formatter saldo dari formatter arus keluar. Pertahankan tanda saldo kas. Uji nilai negatif, nol, positif, serta tooltip dan sumbu terhadap kartu ringkasan dan tabel sumber.

**Titik selesai:** Defisit kas selalu dikenali sebagai negatif pada tooltip; nominal outflow tetap jelas sebagai uang keluar. Ini tidak mengubah proyeksi backend, hanya menyelaraskan penyajiannya.

## Inventaris pemeriksaan dan batasnya

| Area/berkas | Kontrol/relasi yang diperiksa | Kedalaman |
|---|---|---|
| `App.js`, `AppViewRouter.jsx` | Props user/entity, routing layar WMS/Finance/RFID, remount saat entity berubah | Penelusuran integrasi terarah |
| `components/KNSelect.jsx` | Kontrak callback Select/Combobox | Kode lengkap + eksekusi handler asli |
| `wms/OperationsView.jsx` | Tab, permission opname, navigasi transfer | Kode lengkap |
| `wms/InventoryStockView.jsx`, `hooks/usePagedList.js` | Filter, refresh, stok awal, pegging, paginasi dan unduh | Pembacaan terarah; belum semua interaksi tabel |
| `wms/LocationPutawayView.jsx`, `location/PutawayRow.jsx`, `location/StructureEditor.jsx` | Pilih gudang, evaluasi/saran bin, simpan, override, perubahan struktur | Kode lengkap, authority diuji render |
| `location/StockTreePanel.jsx` | Expand tingkat, filter owner, satuan terpisah | Kode lengkap; kandidat stale entity dibatalkan karena remount global |
| `wms/PutawayOrdersPanel.jsx` | Buat, dispatch, arrival, manual/simulated scan, exception | Pemetaan handler/API; belum semua kondisi render |
| `wms/TransferManagement.jsx`, `transfer/TransferCreateForm.jsx`, `TransferDetailModal.jsx` | Pilihan gudang/SO/roll, create, approve/reject, picking, staging, dispatch, cancel | Kode/handler terarah; approval dirender |
| `transfer/TransferReceiptPanel.jsx`, `ReceiptExceptions.jsx` | Scan/terima roll, bin, kerusakan, alasan pengecualian, lapor hilang, penyelesaian exception | Kode lengkap; error awal dirender |
| `inventory/CycleCount.jsx` | Buat, count, submit, approval, reopen, deep-link | Pembacaan terarah; UI legacy perlu uji browser tambahan |
| `wms/OutboundView.jsx`, `OutboundScanInterface.jsx`, `LoadingCheckPanel.jsx` | Resolve roll, scan pick, pengiriman parsial/penuh, loading check, simulasi dan override | Handler/API dan kondisi utama; perangkat/kamera belum diuji |
| `wms/inbound/InboundTaskPanel.jsx` | Scan label/manual, batas penerimaan, selesai dan override | Pembacaan terarah; bukan UAT OCR/perangkat |
| `wms/WmsHealthDashboard.jsx` | KPI, tabel per gudang, status printer, akurasi cycle count | Kode lengkap; angka API belum direkonsiliasi ulang oleh subtugas ini |
| `rfid/RfidTagsView.jsx`, `RfidPrintVerifyPanel.jsx` | Encode/retire/reprint, job cetak, ZPL, mark printed, scan/complete, routing | Handler dan status utama; tidak ada cetak fisik |
| `rfid/RfidDevicesView.jsx`, `rfidShared.jsx` | Tambah/aktivasi/device status/key/copy/location options | Kode lengkap; Admin reserved dinilai eksplisit |
| `rfid/CycleCountPanel.jsx`, `RfidGateMonitorView.jsx` | Cycle count, riwayat, kontrol monitor | Pembacaan terarah; alarm/gate nyata belum diuji |
| `finance/FinancialStatementsView.jsx`, `FinancialStatementsParts.jsx` | Periode, tab, CSV, neraca komparatif, status neraca | Kode lengkap; status unknown diuji render |
| `finance/CashFlowTab.jsx`, `CashFlowForecastView.jsx`, `ProfitabilityView.jsx` | Rentang tanggal, KPI, grafik, tooltip, rincian dan unduhan | Kode lengkap; tanda deficit diuji; sumber backend tidak direkonsiliasi ulang di subtugas ini |
| `finance/StoreCreditView.jsx` | Detail ledger, redeem, adjust, reversal | Kode/handler lengkap; authority diuji render |
| `finance/payments/PaymentVarianceQueue.jsx` | Keputusan/anulir, dialog, navigasi trace | Kode lengkap; role Finance diuji render |
| `finance/interco/IntercoCreateModal.jsx`, `IntercoSettlementModal.jsx`, `IntercoPanels.jsx`, `IntercoPaymentSchedule.jsx` | Pihak, produk, harga/PPN, filter, pembayaran penuh, jadwal | Form utama lengkap; callback diuji; jadwal hanya kontrak layar |
| `finance/interco/IntercoView.jsx`, `BankReconciliationView.jsx`, `BankAccountsView.jsx`, `PostingFailuresView.jsx` | Pembukaan dialog, permission, refresh, posting retry | Pembacaan terarah; belum semua dialog Bank/rekonsiliasi |
| `export/ExportCenterView.jsx`, `JobsPanel.jsx`, `TemplatesPanel.jsx`, `ScheduleForm.jsx` | Dataset/kolom/filter/periode/sort/group, preview, job polling, download/retry, template dan jadwal | Kode lengkap empat berkas; bug backend grouping/export dari audit induk tidak dihitung ulang |

### Pemeriksaan kandidat yang tidak menjadi temuan

- Pergantian entitas tidak dianggap menyebabkan stale data hanya karena suatu effect tidak memiliki dependency `selectedEntity`: `App.js:530`–`:534` melakukan remount view berdasarkan entitas.
- Simulasi RFID cetak/loading check ditandai tidak sah sebagai bukti fisik oleh frontend; keberadaan tombol simulasi sendiri tidak dianggap bug.
- Tombol device RFID yang hanya untuk Admin tidak dianggap bug custom role karena aturan template Admin memang terkunci.
- Pengunduhan CSV/XLSX/ZPL menggunakan API client untuk membawa konteks header; tidak ditemukan raw href pada kontrol unduh yang diperiksa di sini.
- `CycleCount.jsx:80`–`:84` memuat sesi dari deep-link tanpa langsung mengganti `view` menjadi detail. Ini dicatat untuk uji navigasi browser tambahan; tidak dimasukkan ke tujuh temuan terverifikasi render di atas.

### Yang belum dibuktikan oleh subtugas ini

Semua tombol semua role, seluruh respons error API, seluruh layar responsif, kamera/keyboard/peripheral, print fisik, jumlah KPI terhadap GL, dan rantai transaksi dari penerimaan hingga laporan keuangan belum dapat dinyatakan selesai dari bukti ini. Halaman yang hanya dibaca terarah perlu bukti klik browser dan transaksi lokal sebelum diberi status lulus acceptance menyeluruh.

## Prompt perbaikan untuk agent development

> Acuan commit audit `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`. Perbaiki FE-WF-01 sampai FE-WF-07 sesuai laporan ini. Dahulukan sembilan callback KNSelect pada tiga berkas interco karena memblokir input transaksi, lalu konsistensi izin efektif pada TransferDetailModal, PaymentVarianceQueue, LocationPutawayView/TransferReceiptPanel, dan StoreCreditView. Jangan menambah hak akses baru hanya untuk membuat tombol berfungsi; authority, kebijakan keputusan, scope badan usaha/lokasi, dan pemeriksaan backend harus tetap berlaku. Perbaiki state error awal penerimaan transfer agar pesan dan retry tersedia. Gunakan status netral saat hasil neraca belum diketahui dan pertahankan tanda negatif posisi kas pada tooltip. Tambahkan verifikasi komponen yang bermakna, lalu lakukan uji browser lokal untuk pilihan PT/produk/mode, settlement utama/preset, izin standar/kustom/ditolak, error→retry, neraca loading/gagal/sukses, serta tooltip defisit. Lampirkan expected/actual, file:line perubahan, dan bukti hasil. Jangan menandai seluruh modul Finance/WMS lulus hanya karena tujuh temuan ini sudah diperbaiki. Pengelolaan device Admin yang reserved tidak termasuk perintah perubahan ini.
