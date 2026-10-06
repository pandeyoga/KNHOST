# Gelombang 3 · Fase 02 — Hak akses, kepemilikan, RFID/WMS, dan alur lintas entitas

Kerjakan Gelombang 3 dari commit repo saat ini. Baca README, findings-tracker.json, laporan detail, dan source terkait sebelum mengubah kode. Catat actual HEAD; commit audit hanya baseline bukti, bukan asumsi bahwa repo belum berubah. Periksa dulu apakah kasus sudah diperbaiki untuk menghindari patch ganda. Jangan menimpa dokumen Gelombang 1/2 atau mengubah hasil audit historis.

Untuk setiap ID: telusuri input UI → request/schema → permission/entity/lini → service → persist/ledger → projection/report → frontend, termasuk retry, concurrency, pembatalan dan reversal yang relevan. Pertahankan kuantitas fisik, unit, pemilik barang, source document, harga/HPP serta legal entity. Jangan mengubah expected menjadi hasil bug, menyembunyikan warning, atau menyimpulkan fixed hanya dari HTTP 200. Keputusan definisi bisnis yang belum tegas harus dicatat sebagai needs_business_decision.

Setelah implementasi, isi implementation_commit, implementation_evidence, daftar file, perbandingan expected/actual sebelum-sesudah, perintah uji, batas pengujian, dan risiko migrasi. Status agent paling jauh implemented_pending_validation; reviewer independen yang menetapkan verified_fixed setelah seluruh acceptance dan flow terkait lulus. Simpan proof baru terpisah, tanpa menimpa evidence baseline.

Prasyarat: 01. Jumlah ID: 23.

## V3-MRES-01 — Dua PR mencadangkan bahan lebih banyak daripada stok

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/material_reservation_service.py#L79). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-MRES-01`.

**Penyebab:** free_for_commitment dibaca lalu material_reservations diinsert tanpa claim capacity atau unique reservation logical key. Dua PR dapat membaca jumlah bebas sama.

**Prompt perbaikan:** Serialisasi commitment pada key product+owner+unit dan dimensi gudang bila relevan. Reservasi harus CAS terhadap ledger kapasitas yang konsisten dengan sales/MKO; unique PR line/version untuk retry; shortage dilaporkan eksplisit.

**Kriteria validasi:** Parallel700+700 atas1000 tidak pernah reserved>1000. Remaining400 harus shortage/backorder/approval sesuai policy, tidak dianggap tersedia. Uji race dengan SO, issue/cancel/replan dan input UOM berbeda.

## V3-WEIGHT-01 — Split bersamaan menggandakan berat walaupun panjang benar

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L163). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-WEIGHT-01`.

**Penyebab:** insert_child_roll menghitung berat dari snapshot parent lama dan menulis sisa dengan $set; length CAS terpisah tidak menjaga weight total.

**Prompt perbaikan:** Simpan reservasi/split berat dan panjang dalam satu conditional update berdimensi version atau ledger cut dengan snapshot terkini. Tidak boleh menulis derived parent weight dari snapshot lama. Tandai estimated_proportional sebagai estimasi, bukan penimbangan aktual.

**Kriteria validasi:** Parallel split2+2: parent6m/1.8kg dan children0.6+0.6kg. Uji split QC/retur/cut, decimal rounding dan actual reweigh; conservation kg dan meter diuji terpisah.

## V3-RFID-01 — Read green dari passage lama dipakai kembali pada passage baru

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L149). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-RFID-01`.

**Penyebab:** Cache dwell120detik mengembalikan verdict read sebelumnya sebelum evaluator dijalankan. Passage window10detik; event_id baru20detik kemudian membentuk passage baru tetapi tetap memakai verdict lama.

**Prompt perbaikan:** Bedakan replay event ID dan noisy repeated sensor read dari otorisasi passage baru. Cache tidak boleh melintasi passage atau versi shipment/QC/tag; evaluasi ulang current state untuk event baru yang memulai passage.

**Kriteria validasi:** Same-gate event berbeda pada+20detik harus red ketika replay exit/SO cancelled/tag retired/QC hold. Repeated event_id tetap idempoten. Dwell dalam passage tidak menggandakan mutation/incident; worst verdict passage tetap red.

## V3-WMS-02 — Loading gudang siap ditahan oleh pending cut gudang lain

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/loading_check_service.py#L38). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-WMS-02`.

**Penyebab:** Start loading check memanggil guard atas seluruh SO dan API tidak memberi warehouse/shipment subset. SO-wide session mencampurkan readiness shipment yang berbeda.

**Prompt perbaikan:** Bentuk loading session per shipment/task group+warehouse+manifest version. Expected EPC dan cut guard hanya untuk shipment itu; perubahan manifest mengharuskan check ulang. Parent SO menampilkan agregat progres, bukan satu clean global.

**Kriteria validasi:** SO woven/knit/printing tiga gudang: WHwoven dapat check/dispatch/SJ sendiri saat cut WHknit tertunda. Check A tidak membuka B. Shipment parsial dan driver gabungan tetap mempunyai manifest dokumen yang konsisten.

## V3-MRES-02 — Total cadangan maklon tetap terpotong pada batas query

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/material_reservation_service.py#L44). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-MRES-02`.

**Penyebab:** reserved_by_others memakai2000, _on_hand_available500 dan apply_to_products5000 untuk total bisnis, bukan daftar berhalaman. Cadangan yang dilewatkan dapat dijanjikan lagi ke sales.

**Prompt perbaikan:** Gunakan aggregate/kursor penuh untuk seluruh total. Batasi hanya endpoint list berhalaman dengan total terpisah. Harmonisasi owner, product, unit, warehouse dan exclusion ref agar sales dan PR memakai angka sama.

**Kriteria validasi:** Cap−1/cap/cap+1 pada2000reservations,500balances,5000catalog reservations serta>10000roll allocation harus konsisten. Test total/UI/guard commit dan cancellation tidak memakai subset sebagai SSOT.

## D4-STOCK-01 — Nilai dan kecepatan stok terhitung dua kali ketika pemilik berbagi SKU dan gudang

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/stock_analytics_service.py#L137). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-STOCK-01`.

**Penyebab:** Roll dan movement diagregasikan menurut product_id + warehouse_id tanpa owner_entity_id, lalu hasil gabungan ditambahkan lagi untuk setiap balance pemilik. On-hand balance sendiri benar; nilai dan velocity salah.

**Prompt perbaikan:** Gunakan grain product + warehouse + owner sampai tahap agregasi akhir. Jangan join aggregate dengan grain yang lebih kasar ke beberapa balance lalu menjumlahkannya lagi. Terapkan pola yang sama untuk movement, oldest-age dan WAC.

**Kriteria validasi:** SKU/gudang sama dengan dua pemilik: qty30, nilai500 dan sold10; filter A=100/3, B=400/7. Tambahkan gudang kedua dan movement reversal; grouped total harus sama dengan penjumlahan partisi yang sah.

## D4-AI-05 — Stok tersedia dan reserved di live analytics serta snapshot mengabaikan reservasi parsial

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_snapshots.py#L18). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-AI-05`.

**Penyebab:** Live _src_stock dan snapshot_stock menggolongkan seluruh length_remaining menurut status roll. Roll available dengan length_reserved3 tetap dihitung available10/reserved0.

**Prompt perbaikan:** Gunakan canonical physical/free/reserved definition yang mengakomodasi whole-roll dan partial-length. Pisahkan availability fisik vs ATP vs ready-to-dispatch; jangan memperbaiki hanya snapshot sementara live tetap berbeda.

**Kriteria validasi:** Available roll10 reservedlength3 → free7/reserved3; whole reserved10→free0/reserved10. Hold/quarantine, makloon-reserved, cut complete/release dan snapshotday diuji live=historical snapshot saat titik waktu sama.

## D4-AI-06 — Total quantity lintas produk menjumlahkan meter dengan kilogram

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L565). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-AI-06`.

**Penyebab:** Unit guard hanya menambahkan unit ketika group_by tidak memuat product/unit. Mixed-unit detection hanya berjalan jika unit menjadi dimensi. Group product dapat mengembalikan meter/kg dengan total tunggal.

**Prompt perbaikan:** Lacak unit fisik dari metadata row walau dimensi product dipilih. Quantity mixed tidak memiliki grand total; kelompokkan per unit atau konversi eksplisit hanya dalam dimensi kompatibel dengan faktor tersimpan.

**Kriteria validasi:** Product10m+5kg → total null/N/A dan per-unit10m/5kg;10m+5m→15m. Shares mixed quantity tidak dihitung silang unit; salesmoney tetap boleh dijumlah.

## D4-DASH-01 — Batas katalog 3.000 SKU masih menghilangkan master dan cadangan pada KPI

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/dashboard.py#L37). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-DASH-01`.

**Penyebab:** Patch menaikkan batas master dari100 ke3000. KPI balance menghitung semua3003 SKU, tetapi pengurangan material reservation hanya menjelajah3000 master yang dimuat. Respons tidak menyediakan continuation untuk master yang hilang.

**Prompt perbaikan:** Agregasi summary harus memakai seluruh scope yang sama dan sumber reservasi kanonis. Pagination untuk daftar tidak boleh mempengaruhi total. Uji semua bounded helper yang dipakai metrik.

**Kriteria validasi:** Kasus103 serta3003 SKU lengkap lewat pagination/search yang benar; KPI30022 dihitung independen dari window master. Uji juga lebih dari5000 balance agar agregasi tidak bergantung batas client list.

## D4-WMS-03 — Utilisasi gudang mengabaikan struktur Rack→Level→Bin yang didukung master

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/reporting.py#L203). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-WMS-03`.

**Penyebab:** Producer warehouse_structure menyimpan bins di rack.levels[].bins. Consumer reporting hanya rack.bins legacy, sehingga capacity0 dan utilization0 meski lokasi punya capacity.

**Prompt perbaikan:** Reuse canonical location traversal yang mendukung legacy dan level. Tegaskan unit kapasitas dan pisahkan mixedunitstock; jangan membagi meter+kg terhadap denominator yang tidak jelas.

**Kriteria validasi:** Rack→Level→Bins100 tampilcapacity100; legacyrack.bins tetap benar dan tidak dihitungdua kali. Multiunit/capacity0/owner shares/locationinactive diuji.

## D4-PLAN-05 — Pasokan masuk yang sama dapat direncanakan penuh untuk beberapa SO

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L139). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-PLAN-05`.

**Penyebab:** pending_so_board mencocokkan incoming penuh secara independen untuk tiap demand. Jalur wait pada planner hanya menambah narasi parts; tidak mencadangkan qty pasokan per PO/SO atau mengurangi remaining supply yang ditawarkan.

**Prompt perbaikan:** Bentuk pegging supply/demand per document line dengan remaining qty, entity, unit dan ETA, atau labelkan sebagai availability forecast non-exclusive. Untuk janji pemenuhan pasti, validasi dan claim supply harus atomik serta reversible.

**Kriteria validasi:** PO100 dan dua SO100 hanya mengalokasikan100 total. SO kedua menyisakan shortage100 atau forecast yang jelas tidak dijamin. Receive/cancel/amend/reorder/transfer harus merekonsiliasi claim tanpa menjanjikan supply dua kali.

## D4-GLOBAL-01 — Barang datang 100 yard dilabelkan 100 meter pada katalog stok global

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_stock_service.py#L44). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-GLOBAL-01`.

**Penyebab:** apply_global menjumlahkan quantity dan received_qty dokumen secara mentah. Consumer memberi label product.base_unit. quantity_base/uom_trail yang benar dari producer PO tidak dipakai.

**Prompt perbaikan:** Gunakan outstanding dalam satuan dasar dari conversion trail producer dan konversi received quantity dengan unit yang sama. Terapkan ke SO-bound/restock, PO manual/PR/call-off dan interco. Jangan memakai angka fallback1 untuk unit yang tidak bisa dikonversi.

**Kriteria validasi:** PO100 yard pada SKU meter → incoming91.44 meter; setelah menerima40 yard → remaining54.864 meter sesuai presisi kanonis. Uji kg/gram, roll dengan document factor, landed/cost tidak tercampur qty, dan semua badge mobile/desktop.

## D4-SUPPLY-01 — Sisa PO diterima sebagian hilang dari incoming karena definisi status berbeda

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L173). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-SUPPLY-01`.

**Penyebab:** Producer recompute_po_status menetapkan partial untuk PO yang baru diterima sebagian. OPEN_PO_STATUSES yang diimpor stock_bucket_service dan sales_stock_service tidak memasukkan partial. Normalisasi status tidak mengikuti state machine kanonis.

**Prompt perbaikan:** Satukan definisi status open dengan producer lifecycle; hitung remaining qty dalam unit dasar, bukan ordered qty. Review seluruh importer OPEN_PO_STATUSES dan pembelian/GRN/reorder/forecast/ATP, dengan guard terminal dan tolerance policy.

**Kriteria validasi:** PO100 received90 → incoming10; received100/completed →0; closed_short/cancelled/rejected →0; receiving legacy tidak menambah seluruh ordered qty. Uji partial receipt, variance amend/close dan qty per roll.

## D4-CAP-01 — SKU yang benar-benar ada ditolak saat membuat PO setelah 1.000 master pertama

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/purchase_orders.py#L407). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-CAP-01`.

**Penyebab:** Producer membangun lookup dari first1000 product docs tanpa filter ID payload. Produk yang ada di luar window dianggap tidak ditemukan; cap3000 pada dashboard tidak menutup batas1000 producer.

**Prompt perbaikan:** Ambil master berdasarkan himpunan ID yang benar-benar diminta, lalu bandingkan missing IDs. Gunakan paginated search untuk UI dan aggregate independen untuk KPI. Review lookup sejenis pada SO/PR/amendment/receiving, bukan mengganti1000 menjadi angka lebih besar.

**Kriteria validasi:** PO untuk SKU pertama dan SKU1003 sama-sama dibuat dengan source FK yang sah; SKU benar-benar tidak ada ditolak. Uji catalog3003/large, PR→PO, call-off, same-SKU concurrency, grade/UOM/lifecycle guard tetap berlaku.

## D4-PA-01 — Reservasi SO mengambil roll yang sudah diklaim putaway dan meninggalkan lokasi alokasi lama

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L792). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-PA-01`.

**Penyebab:** PA mengklaim active_movement tetapi status roll tetap available. Candidate dan CAS reservasi utuh/panjang mengabaikan klaim tersebut. Reservasi parsial mempertahankan status available sambil menambah length_reserved; dispatch PA tidak memeriksa length_reserved. Tidak ada koordinasi atau rebinding alokasi SO setelah roll berpindah.

**Prompt perbaikan:** Definisikan kebijakan kompatibilitas reservasi/perpindahan. Bila klaim PA eksklusif, filter candidate dan CAS seluruh jalur reservasi dengan active_movement kosong; dispatch memeriksa reservasi live sebelum efek. Jika bisnis mengizinkan reservasi pada PA bergerak, koordinasikan per roll/demand dan rebind warehouse/task/alokasi secara auditable. Audit qty mode, explicit roll, reallocate, backorder, raw/makloon, release dan cancel PA. ATP/available-for-sale mengikuti kebijakan sama; jangan hanya menyaring UI.

**Kriteria validasi:** PA roll10 lalu SO10/SO6 tidak menghasilkan klaim konflik: ditolak/defer tanpa efek atau lewat koordinasi yang menjaga source/task. Partial reserved tidak ikut bergerak tanpa rebinding. Uji urutan terbalik, race PA/SO, cut, release/cancel, arrival/retry dan qty/explicit-roll public producers. Demand, roll, balance, lokasi dan task tetap rekonsiliasi.

## D4-PA-03 — Total putaway menjumlahkan meter dan yard lalu memberi satu label satuan

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L49). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-PA-03`.

**Penyebab:** Group key tidak memuat unit; qty mentah dijumlahkan dan unit diambil dari roll pertama. create_order menjumlahkan item menjadi total_qty tanpa konversi/breakdown. Frontend memberi label g.unit atau items[0].unit pada total campuran.

**Prompt perbaikan:** Pisahkan total per unit atau konversi ke unit tujuan yang dinyatakan dengan faktor kanonis/precision eksplisit. Unit tak kompatibel kg/meter memakai breakdown dan jumlah roll. Snapshot faktor bila menjadi dokumen historis. Review saran, PA/BTG print, movement summary/export; jangan memakai unit item pertama atau mengganti label saja.

**Kriteria validasi:** 10meter+10yard tidak tampil20meter; gunakan19.144/19.14meter dengan precision eksplisit atau breakdown. Reorder item tidak mengubah makna total. Uji kg+meter, multi-SKU, conversion missing, faktor per dokumen, export/print. Per-item dan saldo base-unit tetap benar.

## D4-TAG-01 — Verifikasi tag lama tetap berlaku setelah tag dihapus atau diganti dengan tag pending

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L132). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-TAG-01`.

**Penyebab:** Retire menghapus current tag tetapi tidak menginvalidasi evidence identitas lama. PA percaya journey tag_verified dan lookup tag tanpa active/current verification version. Re-encode lewat print job menghasilkan pending_print yang belum dicetak/verifikasi, tetapi journey lama membuatnya siap bergerak.

**Prompt perbaikan:** Identity readiness harus terikat roll/current live tag ID/EPC/version dan matching verification evidence. Terapkan konsisten pada suggest/create/dispatch/arrival/loading/gate. Retire/re-encode menginvalidasi readiness tanpa memundurkan physical journey secara keliru. Tag harus active, current, linked correctly, EPC kanonis dan verified sesuai policy. Perubahan identity pada active movement ditolak sebelum efek atau lewat workflow retag/manifest update/reverification yang auditable.

**Kriteria validasi:** Verified→retire menolak PA tanpa claim dan tidak masuk ready. Pending_print baru belum lolos; sesudah ack/verifikasi sah boleh PA. Uji retire saat PAopen/transit, reprint sama, EPCbaru, wrong-link, cut child, tagrevision, race movement dan loading/gate/CC. Override eksplisit tidak menganggap bukti identitas lama sebagai current.

## D4-ICLOAN-01 — Akun Finance dapat mengubah pinjaman entitas yang tidak ditugaskan kepadanya

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Keuangan → Antar Entitas → Pinjaman Uang; API repay/cancel.

**Rantai kejadian:** Finance hanyaA → detail pinjamanB/C ditolak → repayB/C diterima → kedua sisi kas dan saldo berubah.

**Letak kesalahan dan penyebab:** Mutating handlers memeriksa izin fitur tetapi tidak memagari dokumen pinjaman memakai konteks entitas. Layanan mengambil loan berdasarkan ID, tanpa verifikasi bahwa pihak transaksi berada dalam penugasan actor.

**Dampak, hasil reproduksi, dan batas klaim:** Akun Finance allowed_entity_ids=[A]: GET loan B/C404 sebagai kontrol. Public repay10 pada loan50 memberi200, outstanding40 dan2 transaksi kas baru. Public cancel draftB/C juga200. Akun manager tidak dipakai sebagai bukti bypass karena role itu memang diizinkan lintas entitas oleh desain sistem; hipotesis awal manager ditarik.

**Lokasi source pada commit audit:**

- [backend/routers/interco_loans.py:96](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L96) — `async def repay_loan(`.
- [backend/routers/interco_loans.py:71](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L71) — `async def get_loan(`.
- [backend/routers/interco_loans.py:109](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/interco_loans.py#L109) — `async def cancel_loan(`.
- [backend/services/interco_loan_service.py:200](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/interco_loan_service.py#L200) — `async def repay(`.

```python
94: 
95: @router.post("/interco/loans/{loan_id}/repay")
96: async def repay_loan(loan_id: str, payload: IntercoLoanRepay, request: Request) -> Dict[str, Any]:
97:     actor = await require_permission(request, "interco", "settle")
98:     try:
99:         res = await svc.repay(loan_id, actor, float(payload.amount or 0), payload.note)
100:     except (svc.LoanError, money.IntercoMoneyError) as exc:
101:         raise _fail(exc) from exc
102:     await audit(actor.get("name", ""), "interco_loan_repaid", "interco_loan",
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Terapkan aturan akses yang sama untuk pasangan lender/borrower pada seluruh mutasi dan layer layanan bila dipanggil lewat jalur lain. Gunakan resolver dokumen/policy yang konsisten dengan GET dan penugasan, tanpa memblokir role lintas entitas yang sah. Audit disburse, repay, cancel, list/detail dan side effects.

**Kriteria penerimaan untuk reviewer:**

Finance hanyaA tidak dapat repay/cancel/disburse loanB/C; tidak ada perubahan saldo/kas/jurnal/timeline ketika ditolak. Lender/borrower yang sah dan manager/admin lintas entitas tetap bekerja; uji akses melalui kedua paired IDs, closed entity dan concurrency.

## D4-RFQ-01 — Award RFQ tetap membuat PO untuk item yang dinyatakan tidak tersedia

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Pembelian → RFQ → perbandingan supplier → Award & Buat PO.

**Rantai kejadian:** Quote availableFalse/price20 → compare tidak lengkap → full award hanya membaca harga → PO dibuat.

**Letak kesalahan dan penyebab:** Perbandingan dan supplier_total menolak baris unavailable, tetapi pemilihan harga award mengabaikan flag available. Sisa harga lama yang positif menjadi dasar PO walaupun supplier menyatakan tidak dapat memasok.

**Dampak, hasil reproduksi, dan batas klaim:** Public quote dua baris: L1 availableTrue/price10, L2 availableFalse/price20. Public compare completeFalse sebagai kontrol. Public award full tetap200 dan membuat1 PO yang mencakup L2. Kontrol quote kedua baris availableTrue memberi full PO50 dan split termurah menghasilkan2 PO total46. UI saat ini membentuk available dari harga; skenario flagFalse dengan retained price terutama kontrak API/data, bukan klaim pengguna UI dapat mengetik kombinasi itu.

**Lokasi source pada commit audit:**

- [backend/services/rfq_service.py:296](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfq_service.py#L296) — `def _price_of(sid: str, lid: str)`.
- [backend/services/rfq_service.py:90](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfq_service.py#L90) — `if ln.get("available", True) and float(ln.get("price", 0) or 0) > 0:`.
- [backend/routers/rfq.py:184](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L184) — `async def award(`.
- [frontend/src/features/purchasing/RFQDetailPanel.jsx:77](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/purchasing/RFQDetailPanel.jsx#L77) — `async function doAward()`.

```python
294:     grouped: Dict[str, List[Dict[str, Any]]] = {}
295: 
296:     def _price_of(sid: str, lid: str) -> float:
297:         s = sup_by_id.get(sid, {})
298:         for ln in s.get("lines", []):
299:             if ln["line_id"] == lid:
300:                 return float(ln.get("price", 0) or 0)
301:         return 0.0
302: 
```

**Bukti asli:** [evidence/repro/procurement-lifecycle90-results.json](evidence/repro/procurement-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| rfq.full_unavailable_rejected | 400 | 200 | observed_difference |
| rfq.full_unavailable_no_po | 0 | 1 | observed_difference |
| rfq.foreign_compare_denied | true | false | observed_difference |
| rfq.foreign_cancel_denied | true | false | observed_difference |
| rfq.foreign_state_preserved | "draft" | "cancelled" | observed_difference |

**Prompt agent development:**

Gunakan satu resolusi kelayakan quote untuk compare, rekomendasi dan award. Supplier/baris harus quoted, availableTrue dan harga valid. Cek validitas quote/masa berlaku serta duplicate line; line override harga tidak boleh memulihkan availability tanpa keputusan eksplisit yang tercatat.

**Kriteria penerimaan untuk reviewer:**

Full/line award atas unavailable ditolak sebelum PO/price-list/PR berubah; status RFQ dan saga tetap dapat diperbaiki. Quote valid full50/split46 tetap lolos. Uji harga lama positif, unavailable0, missing quote, expiry, override, duplicate quote lines dan multi-supplier partial failure.

## D4-RFQ-02 — Perbandingan dan pembatalan RFQ tidak mengikuti pembatasan entitas pada halaman detail

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Pembelian → RFQ → perbandingan harga dan aksi status.

**Rantai kejadian:** Finance hanyaKSC → detail RFQ entitaslain404 → compare200 → cancel200 dan status cancelled.

**Letak kesalahan dan penyebab:** GET detail memanggil entity_ctx/assert_entity_access. Compare dan beberapa mutasi langsung _get(id) setelah izin fitur, sehingga aturan penugasan dokumen tidak diterapkan konsisten.

**Dampak, hasil reproduksi, dan batas klaim:** Akun Finance ditugaskan hanya ent_ksc. RFQ fixture yang awalnya lahir dari producer publik diberi owner entitaslain yang memang ada. Detail ditolak403/404, tetapi compare diterima dan cancel200 mengubah draft menjadi cancelled. Izin fitur sengaja diberikan lewat matriks; role lintas entitas tidak dipakai untuk membuktikan penolakan.

**Lokasi source pada commit audit:**

- [backend/routers/rfq.py:56](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L56) — `return build_compare(await _get(rfq_id))`.
- [backend/routers/rfq.py:49](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L49) — `assert_entity_access(rfq, "rfqs", ctx)`.
- [backend/routers/rfq.py:205](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L205) — `async def cancel_rfq(`.
- [backend/routers/rfq.py:135](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfq.py#L135) — `async def send_rfq(`.

```python
54: async def compare_rfq(rfq_id: str, request: Request) -> Dict[str, Any]:
55:     await require_permission(request, "rfq", "view")
56:     return build_compare(await _get(rfq_id))
57: 
58: 
59: @router.post("/rfqs")
60: async def create_rfq(payload: RFQCreate, request: Request) -> Dict[str, Any]:
61:     """Buat RFQ dari PR approved (tarik item) atau standalone manual."""
62:     actor = await require_permission(request, "rfq", "create")
```

**Bukti asli:** [evidence/repro/procurement-lifecycle90-results.json](evidence/repro/procurement-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| rfq.foreign_detail_denied_control | true | true | pass |
| rfq.foreign_compare_denied | true | false | observed_difference |
| rfq.foreign_cancel_denied | true | false | observed_difference |
| rfq.foreign_state_preserved | "draft" | "cancelled" | observed_difference |

**Prompt agent development:**

Gunakan _get_scoped atau guard bersama pada compare/send/quote/award/cancel serta validasi entitas saat create dari PR. Verifikasi scope sebelum state/price-list/PO/PR/saga/timeline berubah. Pertahankan akses role lintas entitas yang sah dan penugasan MD multi-entitas.

**Kriteria penerimaan untuk reviewer:**

Detail/compare dan semua mutasi harus menolak actor di luar penugasan; status dan seluruh side effects tidak berubah. Positive control entitas milik actor tetap berfungsi. Uji foreign PR→RFQ, explicit entity_id, supplier entity sharing, line scope dan kedua policy aktor multi-entitas/lintas entitas.

## D4-PRICE-SCOPE-01 — Scope harga khusus berbeda antara detail, perubahan, harga efektif dan ringkasan

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Persetujuan Harga Khusus → daftar, statistik, detail dan keputusan.

**Rantai kejadian:** Sales dengan kemampuan custom hanyaA → detailB ditolak → patch/submit/approve/deleteB diterima; stats/effective juga membacaB.

**Letak kesalahan dan penyebab:** Sebagian handler hanya memeriksa permission dan requested_by. entity_ctx/assert_entity_access yang dipakai GET detail tidak diterapkan pada mutasi/resolver/statistik.

**Dampak, hasil reproduksi, dan batas klaim:** Original ASGI: user Sales onlyA diberi capability yang diuji. Create asing ditolak sebagai kontrol; foreign fixtureB ownerU disiapkan eksplisit. GET B ditolak, listA benar, tetapi PATCH/SUBMIT/DELETEB200; distinct approver onlyA menyetujuiB200; effectiveB mengembalikan hargaB dan statsA menghitung2 alih-alih1. Manager/admin cross-entity tidak dipakai sebagai bypass.

**Lokasi source pada commit audit:**

- [backend/routers/price_approvals.py:263](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L263) — `async def patch_price_approval(`.
- [backend/routers/price_approvals.py:182](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L182) — `async def price_approval_stats`.
- [backend/routers/price_approvals.py:157](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L157) — `async def effective_price`.
- [backend/routers/price_approvals.py:257](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L257) — `assert_entity_access(doc, "price_approvals", ctx)`.
- [backend/routers/price_approvals.py:331](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/price_approvals.py#L331) — `async def approve_price_approval`.

```python
261: 
262: @router.patch("/price-approvals/{approval_id}")
263: async def patch_price_approval(approval_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
264:     user = await require_permission(request, "price_approval", "update")
265:     doc = await _get_or_404(approval_id)
266:     _ensure_owner_or_privileged(doc, user)
267:     if doc["status"] not in EDITABLE_STATUSES:
268:         raise HTTPException(status_code=409, detail=f"Pengajuan status '{doc['status']}' tidak dapat diubah")
269:     allowed = {"requested_price", "min_quantity", "reason", "valid_until"}
```

**Bukti asli:** [evidence/repro/price-approval-scope90-results.json](evidence/repro/price-approval-scope90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| price.foreign_create_rejected | true | true | pass |
| price.foreign_get_control | true | true | pass |
| price.stats_scope | 1 | 2 | observed_difference |
| price.foreign_patch_rejected | true | false | observed_difference |
| price.foreign_submit_rejected | true | false | observed_difference |
| price.foreign_approve_rejected | true | false | observed_difference |
| price.foreign_effective_hidden | false | true | observed_difference |
| price.foreign_delete_rejected | true | false | observed_difference |

**Prompt agent development:**

Pusatkan scoped document resolver, terapkan sebelum setiap read/mutation/attachment/status effect dan supersede. Effective/stats harus mengikuti active/allowed entity scope; permission fitur bukan izin semua dokumen. Pertahankan custom capabilities sah, SOD dan role cross-entity.

**Kriteria penerimaan untuk reviewer:**

Detail/list/effective/stats/mutasi sepakat pada scope; ditolak tanpa perubahan harga,status,customer-price,SO,supersede,notifikasi atau file. Own-entity lifecycle draft→evidence→submit→distinct approval→effective tetap lulus, minqty4/5 dan approved edit/delete guards tetap benar.

## D4-ALERT-WMS-01 — Notifikasi tugas WMS mencampur pesanan dua entitas yang memakai gudang sama

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** WMS multi-entitas/shared warehouse → scheduler ops_stalled → bell gudang.

**Rantai kejadian:** SO-A ownerKSC +SO-B ownerlain, warehouse/flow sama → satu bucket entityKSC berisi2 tugas dan nomorSO-B.

**Letak kesalahan dan penyebab:** Pengelompokan tidak memasukkan entity_id. Entitas bucket ditetapkan dari tugas pertama, sedangkan hitungan dan daftar order mencakup pemilik lain.

**Dampak, hasil reproduksi, dan batas klaim:** Pada dua business_entities yang nyata di fixture, original generator membuat satu notifikasi entitas pertama, memuat nomor pesanan kedua; owner kedua tidak mendapat kelompoknya sendiri. Ini selain salah hitung juga mengaburkan batas tugas entitas. Kontrol dua flow milik satu entitas menghasilkan dua kelompok dengan dedupe harian.

**Lokasi source pada commit audit:**

- [backend/services/alert_service.py:286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L286) — `key = (t.get("warehouse_id", ""), t.get("flow_type", ""))`.
- [backend/services/alert_service.py:302](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L302) — `ref=f"task_stalled:{wid}:{flow}"`.
- [backend/services/alert_service.py:289](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/alert_service.py#L289) — `"entity_id": t.get("entity_id")`.

```python
284:     groups: Dict[tuple, Dict[str, Any]] = {}
285:     for t in tasks:
286:         key = (t.get("warehouse_id", ""), t.get("flow_type", ""))
287:         g = groups.setdefault(key, {"count": 0, "oldest": None, "orders": [],
288:                                     "warehouse_name": t.get("warehouse_name", ""),
289:                                     "entity_id": t.get("entity_id")})
290:         g["count"] += 1
291:         dt = _parse(t.get("created_at"))
292:         if dt and (g["oldest"] is None or dt < g["oldest"]):
```

**Bukti asli:** [evidence/repro/alert-numeric90-results.json](evidence/repro/alert-numeric90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| alerts.ops_shared_warehouse_separate_owners | 2 | 1 | observed_difference |
| alerts.ops_foreign_order_not_in_owner_notice | false | true | observed_difference |

**Prompt agent development:**

Kelompokkan berdasarkan entity_id+warehouse_id+flow dan masukkan entity pada ref/dedupe. Pertahankan gudang bersama, tentukan audience sesuai penugasan pengguna dan line/warehouse role; jangan mengandalkan nama gudang sebagai pemilik.

**Kriteria penerimaan untuk reviewer:**

Dua owner satu gudang menghasilkan notifikasi masing-masing dengan count/order sendiri. Actor entitasA tidak memperoleh nomorSO-B dari notifikasiA. User multi-entitas/lintas-entitas sah tetap dapat melihat kelompok yang diizinkan; rerun harian tidak duplikat.

## D4-RET-POLICY-01 — Deadline retur dapat berubah karena PO terbaru entitas lain dengan produk yang sama

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `direct_original_service_with_explicit_linked_fixture`.

**Layar/alur:** Retur Jual → evaluasi kelayakan → policy link_to_supplier_window → deadline dan status eligible.

**Rantai kejadian:** SO A memakai roll dari PO A/supplierA (window30) → eligible pada hari kedua; PO terbaru B/supplierB pada SKU sama (window1, receipt lama) → deadline A berubah dan retur yang sama menjadi tidak eligible.

**Letak kesalahan dan penyebab:** Resolver linked-supplier memilih PO terbaru berdasarkan product_id dan status tanpa membatasi entitas atau menelusuri asal roll yang memenuhi SO. Proxy produk sama tidak setara dengan asal fisik barang yang diretur.

**Dampak, hasil reproduksi, dan batas klaim:** Original service dengan policy A dan roll milik A yang mengacu OWN-PO menghasilkan supplierSA dan eligibleTrue. Penambahan FOREIGN-PO milik B mengubah supplier menjadiSB, deadline dan eligibleFalse, meski SO/roll/PO A tidak berubah. Fixture provenance dinyatakan eksplisit; tidak diklaim seluruh producer normal menghasilkan hubungan salah atau bahwa browser telah diuji. Mode linked bersifat opsional; mode nonlinked tidak terdampak oleh jalur ini.

**Lokasi source pada commit audit:**

- [backend/services/return_policy_service.py:241](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L241) — `po = await db.purchase_orders.find_one(`.
- [backend/services/return_policy_service.py:242](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L242) — `"items.product_id": {"$in": product_ids}`.
- [backend/services/return_policy_service.py:299](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L299) — `deadline = min(d1, d2).isoformat()`.
- [backend/services/return_policy_service.py:327](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/return_policy_service.py#L327) — `blocked = bool(enforce and dl is not None and not within_window)`.

```python
239: 
240:     # Cari PO terbaru yang memuat produk-produk ini (sebagai proxy asal beli).
241:     po = await db.purchase_orders.find_one(
242:         {"items.product_id": {"$in": product_ids},
243:          "status": {"$in": ["receiving", "partial", "completed", "closed", "closed_short"]}},
244:         {"_id": 0}, sort=[("created_at", -1)])
245:     if not po or not po.get("supplier_id"):
246:         return {"deadline": "", "supplier_id": "", "window_days": window_fallback, "source": "none"}
247: 
```

**Bukti asli:** [evidence/repro/budget-ledger-policy90-results.json](evidence/repro/budget-ledger-policy90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| return_policy.foreign_unrelated_po_not_selected | "SA" | "SB" | observed_difference |
| return_policy.eligibility_not_changed_by_foreign_po | true | false | observed_difference |
| return_policy.deadline_not_changed_by_foreign_po | "2026-01-31T00:00:00+00:00" | "2025-12-02T00:00:00+00:00" | observed_difference |

**Prompt agent development:**

Telusuri source PO/receipt/supplier dari roll atau shipment yang benar-benar memenuhi SO, termasuk lineage intercompany. Untuk item bersumber majemuk, hitung deadline per asal dan jelaskan basis penggabungannya. Jangan memakai PO terbaru SKU sebagai sumber keputusan blokir. Jika provenance belum tersedia, tampilkan unresolved/advisory sesuai keputusan bisnis; jangan mengarang deadline.

**Kriteria penerimaan untuk reviewer:**

Menambah/mengubah PO yang tidak terkait, termasuk entitas lain dan PO baru SKU yang sama, tidak mengubah eligibility SO A. Uji mixed suppliers, partial shipment, intercompany chain, retur sebagian roll, supplier window0, missing provenance, import/local, tenant boundary dan mode linked/nonlinked.

