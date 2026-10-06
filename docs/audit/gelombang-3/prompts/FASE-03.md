# Gelombang 3 · Fase 03 — Master data, procurement, harga, dan aturan komersial

Kerjakan Gelombang 3 dari commit repo saat ini. Baca README, findings-tracker.json, laporan detail, dan source terkait sebelum mengubah kode. Catat actual HEAD; commit audit hanya baseline bukti, bukan asumsi bahwa repo belum berubah. Periksa dulu apakah kasus sudah diperbaiki untuk menghindari patch ganda. Jangan menimpa dokumen Gelombang 1/2 atau mengubah hasil audit historis.

Untuk setiap ID: telusuri input UI → request/schema → permission/entity/lini → service → persist/ledger → projection/report → frontend, termasuk retry, concurrency, pembatalan dan reversal yang relevan. Pertahankan kuantitas fisik, unit, pemilik barang, source document, harga/HPP serta legal entity. Jangan mengubah expected menjadi hasil bug, menyembunyikan warning, atau menyimpulkan fixed hanya dari HTTP 200. Keputusan definisi bisnis yang belum tegas harus dicatat sebagai needs_business_decision.

Setelah implementasi, isi implementation_commit, implementation_evidence, daftar file, perbandingan expected/actual sebelum-sesudah, perintah uji, batas pengujian, dan risiko migrasi. Status agent paling jauh implemented_pending_validation; reviewer independen yang menetapkan verified_fixed setelah seluruh acceptance dan flow terkait lulus. Simpan proof baru terpisah, tanpa menimpa evidence baseline.

Prasyarat: 01. Jumlah ID: 22.

## V3-PO-01 — Task selisih PO tidak refresh dan kehilangan identitas baris

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/po_variance_task_service.py#L51). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-PO-01`.

**Penyebab:** Key task memakai product_id, bukan line_id, dan existing task langsung continue. Received yang berubah tidak memperbarui task/suggested qty. Duplicate product pada PO baru diblokir KN-B15, tetapi dokumen historis masih dapat memiliki dua baris.

**Prompt perbaikan:** Key task harus stable PO line ID/version. Refresh ordered/received/short dan close task bila selesai; keputusan memakai revalidation PO terkini. Migrasi legacy duplicate secara eksplisit, jangan menggabungkan dua harga.

**Kriteria validasi:** Terima90 lalu95: open task received95/short5, amendment suggestion95. Terima100 menutup obsolete task. Dua legacy line memberi dua task. Race receipt vs decide tidak memakai qty lama.

## V3-CF-01 — Jurnal campuran kas/nonkas menghasilkan klasifikasi arus kas salah

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cash_flow_service.py#L84). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-CF-01`.

**Penyebab:** Bila satu jurnal menyentuh kas, semua contra line dimasukkan bucket aktivitas. Aset yang sebagian dibayar kas dan sebagian AP dianggap seluruhnya cash investing serta AP dianggap cash operating.

**Prompt perbaikan:** Klasifikasi sumber harus membawa settlement cash portion yang eksplisit. Pecah source/mixed journal secara traceable; jangan memperkirakan aktivitas dari seluruh contra balance. Reconcile total kas dan disclosure noncash terpisah.

**Kriteria validasi:** Fixture asset cash40+credit60 harus CFI−40/CFO0/noncash60. Tambahkan asset penuh kredit, cash penuh, bank-to-bank, depreciation, sale credit+receipt dan mixed multiple assets/liabilities. Persetujuan policy akuntan diperlukan untuk metode alokasi ambigu.

## V3-DATE-01 — Jurnal date-only pada awal periode hilang dari laporan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L31). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-DATE-01`.

**Penyebab:** Insert jurnal mempertahankan date yang dikirim, termasuk YYYY-MM-DD. Query start membuat string YYYY-MM-DDT00:00:00; lexical compare mengeluarkan date-only hari pertama.

**Prompt perbaikan:** Gunakan representasi tanggal kanonik di seluruh entry/create/autopost/import dan query, dengan timezone bisnis disepakati. Migration preview tanggal lama dan conflict report; hindari mengubah label saja atau memperlebar cutoff tanpa aturan.

**Kriteria validasi:** Date-only/ISO/tz-offset hari awal dan hari akhir periode masuk tepat sekali. Neraca default, ledger, cash flow, closing, unlock dan konsolidasi memakai cutoff sama. Uji jurnal masa depan tetap tidak masuk hari ini.

## V3-PO-02 — Pilihan amend ke jumlah diterima bertentangan dengan guard PO lama

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/po_amendment_service.py#L103). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-PO-02`.

**Penyebab:** Task baru menjanjikan amendment qty aktual, tetapi guard lama mengunci quantity setiap baris yang received_qty>0. Ini gap integrasi dua aturan bisnis, bukan alasan untuk menghapus guard seluruh field finansial.

**Prompt perbaikan:** Tetapkan flow dedicated receiving-variance amendment atau perbaiki CTA menjadi short-close sesuai policy disepakati. Jika amendment dipilih, target tidak kurang dari received, snapshot/bill/DP dilindungi dan reapproval/credit adjustment eksplisit; jangan rewrite posted GL.

**Kriteria validasi:** Kasus1000→960 memiliki jalur selesai yang nyata dan tidak buntu. Received tetap960; PO version/approval terdokumentasi; vendor bill/AP/DP diperhitungkan terpisah. Jika hanya short-close diperbolehkan, UI tidak menjanjikan amend unsupported.

## V3-PO-03 — Tugas selisih selesai meski amendment belum disetujui dan qty belum berubah

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/purchase_orders.py#L751). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-PO-03`.

**Penyebab:** Router menyelesaikan seluruh pending_amendment segera sesudah amend_po, sebelum reapproval. Fungsi juga tidak memeriksa apakah perubahan berkaitan dengan shortage line.

**Prompt perbaikan:** Selesaikan task hanya setelah amendment version/line yang ditautkan approved dan acceptance shortage direvalidasi. Notes-only amendment tidak menutup qty task. Rejection/cancel amendment memulihkan action pending yang benar.

**Kriteria validasi:** Amend notes saja atau awaiting approval: task pending. Approved qty960/reconciled policy: task selesai. Rejection tetap memerlukan keputusan. Beberapa task/line/versi tidak tertutup sekaligus oleh perubahan unrelated.

## D4-FIN-01 — Control Tower menggabungkan AR semua entitas ketika parameter entitas dihilangkan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/finance_analytics.py#L68). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-FIN-01`.

**Penyebab:** Scope journal menggunakan konteks aktif, tetapi ent=None diteruskan ke aging_report, dan comparison memakai semua allowed_entity_ids. Scope komponen dalam satu respons berbeda.

**Prompt perbaikan:** Resolve effective scope sekali dan teruskan ke setiap service. Bedakan active, selected dan all secara eksplisit. All harus tetap dibatasi allowed entity set dan tidak memakai None ambigu.

**Kriteria validasi:** Default/header A sama dengan explicit A; B dan all memiliki angka terpisah yang benar. Rekonsiliasi cash+AR−AP dalam scope identik. Uji allowed subset.

## D4-SALES-01 — Target penjualan dan penagihan tidak mengikuti scope entitas

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L155). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-SALES-01`.

**Penyebab:** Lookup target hanya sales_id dan period, tanpa entity_id. Target A dapat menjadi pembagi KPI B. Probe menggunakan satu target sah di A, tidak mengasumsikan public API mampu membuat dua target paralel yang tidak didukung.

**Prompt perbaikan:** Tentukan kontrak target per-entity/global; selaraskan schema, uniqueness/upsert dan query untuk target_sales serta target_collection. Nilai tidak dikonfigurasi harus dibedakan dari nol.

**Kriteria validasi:** Target A100; B tidak ada → B tidak memakai100. A/B/all, period month/quarter/year, fallback legacy dan tier boundary diuji tanpa penggandaan target.

## D4-SALES-02 — Sales Home masih menampilkan order dan piutang lintas entitas di kartu pelanggan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/home_service.py#L59). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-SALES-02`.

**Penyebab:** Home memfilter customer menurut A, tetapi memanggil compute_customer_credit tanpa entity dan mengambil recent SO customer tanpa entity. Perbaikan KPI di sales_force tidak menyelesaikan consumer home ini.

**Prompt perbaikan:** Teruskan effective entity ke credit helper dan query recent orders. Selaraskan home/KPI/aging sehingga konteks aktif bermakna sama, serta lindungi all dengan allowed scope.

**Kriteria validasi:** Home A AR100 dan hanya SO A; Home B700; all800 bila diizinkan. Customer dengan assigned-sales berubah dan SO tim lintas entitas tidak menghasilkan salah atribusi.

## D4-SALES-03 — Komisi per-SKU memasukkan SO tim sales milik entitas lain

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L253). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-SALES-03`.

**Penyebab:** Query komisi OR customer assigned / sales_team tidak menambahkan entity_id pada SO. KPI dan rate scoped A, tetapi basis commission dapat berasal dari B.

**Prompt perbaikan:** Gunakan satu eligible-order scope untuk KPI, collection allocation dan komisi. Query OR attribution harus dibungkus scope entity/status/period. Hitung cost per SO owner; jangan rate A mengalikan transaksi B.

**Kriteria validasi:** A tanpa SO memperoleh0 walau S masuk tim B. A/B/all, shared customer, split team, partial receipt, return/void dan accrual ulang harus memenuhi konservasi serta idempotensi.

## D4-FIN-02 — Forecast kas memakai basis AR dan termin berbeda dari AR kanonis

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cashflow_forecast_service.py#L66). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-FIN-02`.

**Penyebab:** NON_AR_METHODS didefinisikan tetapi tidak dipakai, projection tidak memuat payment_profile_method. Due date dihitung dari default pelanggan terkini, mengabaikan payment_term_days snapshot SO; term0 juga berubah30 karena or30.

**Prompt perbaikan:** Reuse sumber AR kanonis untuk eligibility, net outstanding, method dan due date. Forecast boleh punya skenario sendiri hanya jika dipisahkan dari confirmed receivables dan diberi label/asumsi.

**Kriteria validasi:** Tunai tidak masuk AR forecast; tempo90 mengikuti SO meski profile diubah30; termin0 tetap0. Return/credit note, DP, partial receipt dan closing/reversal harus cocok dengan aging pada snapshot yang sama.

## D4-FIN-03 — Revenue profitabilitas memasukkan PPN included dan mengabaikan diskon header legacy

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/profitability_service.py#L118). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-FIN-03`.

**Penyebab:** Revenue langsung menjumlahkan line_total. Pada harga tax included, field ini masih memuat PPN; revenue kanonis adalah grand_total−ppn_amount. Shape legacy dengan diskon order terpisah juga tidak dialokasikan. Current create_order memaksa manual order discount=0, sehingga contoh diskon header tidak digeneralisasi sebagai alur SO baru.

**Prompt perbaikan:** Gunakan shared net revenue allocation seperti fact sales dengan residual rounding yang terkontrol. Ambil grand_total−ppn_amount sesuai kontrak kanonis, dan jangan mengurangi diskon item dua kali ketika line_total sudah net. Jelaskan return/void dan legacy header discount.

**Kriteria validasi:** Harga included1000: Σrevenue harus grand_total−ppn_amount dari producer pricing; excluded dan non-PKP tetap benar. Legacy ordergross1000−headerdisc100=net900 bila shape masih didukung. Semua dimensi, residual cent dan credit return direkonsiliasi.

## D4-FIN-04 — Label pendapatan realisasi sebenarnya memakai pesanan reserved dan WAC terkini

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/profitability_service.py#L19). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-FIN-04`.

**Penyebab:** SOLD_STATUSES memasukkan confirmed dan reserved, tanggal memakai created_at SO, biaya dihitung dari WAC saat query. Ini analisis nilai pesanan dengan biaya kini, bukan otomatis realisasi shipment/GL historis.

**Prompt perbaikan:** Pilih dan dokumentasikan metrik booked-order estimate vs realised revenue/margin. Jika realisasi, gunakan shipped/recognized amount serta cost snapshot yang sesuai. Jika tetap SO/WAC kini, ubah label/basis dan pisahkan estimator dari GL.

**Kriteria validasi:** Reserved menunjukkan estimasi100 dan realisasi0 dalam metrik berbeda. Partial shipment, tanggal order vs dispatch, return, landed adjustment dan perubahan WAC memiliki perilaku terdefinisi.

## D4-AI-01 — Analytics AP mengabaikan fallback vendor bill yang masih dipakai sumber kanonis

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/analytics_engine.py#L288). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-AI-01`.

**Penyebab:** AP analytics hanya grand_total−amount_paid. bill_financials mendukung grand_total0 dengan total_amount fallback. Dokumen legacy yang sah jadi hilang dari analytics.

**Prompt perbaikan:** Normalisasi amount melalui satu kontrak bill financials yang juga dapat dieksekusi agregasi. Jangan membuat fallback berbeda antar aging, forecast, BI dan Tanya.

**Kriteria validasi:** Grand_total positif, grand_total0 dengan total_amount, paid partial, legacy missing field, posted/void dan multicurrency jika didukung: outstanding konsisten dengan canonical.

## D4-CASH-01 — Saldo awal kas kecil berpindah menjadi kas besar setelah transaksi terakhir di-void

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/cash.py#L103). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-CASH-01`.

**Penyebab:** Jenis saldo awal ditentukan oleh account_id yang muncul pada transaksi kas kecil aktif. Master tidak memiliki field cash_type untuk klasifikasi tetap; void transaksi terakhir membuat account keluar dari kecil_ids.

**Prompt perbaikan:** Tetapkan account classification atau mapping eksplisit yang tidak bergantung ada/tidak transaksi. Rancang migration/legacy unknown; jangan menebak dari transaksi terkini atau mengarang field schema sudah ada.

**Kriteria validasi:** Void/delete transaksi terakhir tidak mengubah jenis opening. Account tanpa transaksi, legacy tanpa mapping, beberapa entitas, cash deposit transfer dan preview compare harus konsisten.

## D4-DATE-01 — Penjualan dan Home menggunakan bulan/tahun UTC yang berbeda dari periode bisnis WIB

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_force_service.py#L27). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-DATE-01`.

**Penyebab:** _in_period memotong tanggal string tanpa konversi timezone. Home _current_month/_today_prefix juga memakai UTC. Transaksi normal pada tujuh jam pertama WIB di awal bulan/tahun dapat masuk periode sebelumnya. Analytics engine memiliki konversi WIB tersendiri, sehingga metrik antarmodul dapat berbeda.

**Prompt perbaikan:** Tentukan timezone bisnis/per-entity dan gunakan helper periode bersama untuk timestamp serta date-only. Buat range UTC dari batas periode WIB. Jangan hanya mengubah bulan default Home sementara filterSO/payment masih memotong stringUTC. Telusuri profitability monthly grouping dan Finance Tower period sebagai related static candidates.

**Kriteria validasi:** Batas23:59:59WIB dan00:00WIB di awalbulan, kuartal dan tahun masuk periodeyangbenar; timestamp Z/+00/+07 serta date-only memiliki aturanjelas. KPI, target, commissionhistory, snapshot dan export pada filter sama harusrekonsiliasi.

## D4-PLAN-01 — Rencana pembelian mencatat qty yang berbeda dari PR yang dirujuk

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L133). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-PLAN-01`.

**Penyebab:** Helper lama menegaskan ulang PR yang masih terbuka berdasarkan product_id tanpa menambah qty. Planner baru tetap menulis qty permintaan sebagai qty pembelian baru dan _planned menjumlahkan setiap keputusan.

**Prompt perbaikan:** Pisahkan reaffirmation dari penambahan supply; pakai qty efektif dan per-line reference aktual. Jika perlu tambah80, lakukan amendment atau PR delta terkontrol. Rekonsiliasikan planned_qty dari supply aktif per referensi unik, bukan penjumlahan narasi histori.

**Kriteria validasi:** PR20 lalu permintaan80 tidak boleh memberi kesan supply100 bila PR tetap20. Reaffirm20 berulang tidak meningkatkan planned_qty. Cancel/convert/receive/amend PR harus memperbarui remaining supply; uji multi-SKU saat sebagian SKU sudah punya PR.

## D4-PLAN-02 — Baris produk ganda pada API rencana dapat membuat pembelian melebihi kekurangan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L76). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-PLAN-02`.

**Penyebab:** Validasi mengecek setiap raw row terhadap shortage yang sama. Tidak ada unique product guard atau akumulasi total lintas baris. Dua row100 masing-masing lolos pada shortage100.

**Prompt perbaikan:** Tolak duplikasi product_id atau gabungkan baris sebelum memvalidasi kapasitas/demand. Akumulasikan pula per product + source entity dan validasi finite positive quantities. Jangan memindahkan guard hanya ke UI.

**Kriteria validasi:** Duplicate product100+100 ditolak tanpa side effect; duplicate source allocations juga tidak melewati batas. Uji semua endpoint planner dan PR realization; request invalid tidak membuat PR/transfer/reservation.

## D4-PLAN-03 — Riwayat mengatakan pemenuhan penuh walaupun sebagian eksekusi gagal

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fulfillment_plan_service.py#L160). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-PLAN-03`.

**Penyebab:** full dihitung dari seluruh qty permintaan pada plan, setelah _execute menangkap kegagalan yang hanya menyelesaikan sebagian done. Qty yang gagal tetap berkontribusi pada scope full.

**Prompt perbaikan:** Hitung execution outcome dari hasil nyata tiap bagian; pisahkan planned coverage dari executed coverage. Simpan per-part succeeded/failed/pending beserta effective qty dan reference. Kegagalan parsial harus dapat dilanjutkan tanpa menjalankan ulang bagian yang sukses.

**Kriteria validasi:** Fixture stock30/interco70 fail mencatat partial30, sisa70 belum terpenuhi, dan error tetap terlihat. Retry hanya menjalankan sisa. Uji exception infrastruktur, failure sebelum record, dan zero actual stock setelah concurrent consumption.

## D4-COA-01 — Mode Semua Entitas pada laporan keuangan menghilangkan akun khusus entitas yang sah

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/financial_statement_service.py#L54). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-COA-01`.

**Penyebab:** scope_entity mengembalikan None untuk scope multi-entitas. _accounts_map lalu meminta effective_accounts hanya untuk global template. Producer mendukung akun khusus entitas dengan kode yang tidak ada global; akun sah tersebut hilang dari dimensi multi-entity sehingga debit kas masih dihitung tetapi pendapatan lawannya tidak diklasifikasi. Ini berbeda dari memilih override nama akun yang nondeterministik.

**Prompt perbaikan:** Resolve account dimension pada grain entity+account sebelum agregasi, lalu roll-up lewat mapping COA grup yang eksplisit. Akun khusus entitas tidak boleh hilang; bila belum dipetakan ke COA grup, tampilkan error/rekonsiliasi yang actionable, bukan silently drop. Jangan memilih override PT pertama secara acak untuk semua PT. Audit P&L/BS/comparative/equity/cashflow, ledger/trial balance dan export dengan resolver yang sesuai scope; pertahankan legal-entity permissions dan policy untuk kode sama dengan klasifikasi berbeda.

**Kriteria validasi:** Akun khususA income77 danB kosong: A dan all sama-samaincome77, allBS balanced dan selisih0; total all merekonsiliasi partisi legal entity. Uji akun khusus dua PT dengan kode unik, override nama/kategori/type berbeda pada kode sama, global disabled/entity active, unmapped group code, pagination COA besar, comparative, CSV serta entity access. Fitur Konsolidasi Grup yang memakai helper lain harus diuji sebagai kontrol terpisah.

## D4-COMM-BOUNDS-01 — Perubahan master komersial melewati batas angka dan dapat menghasilkan ongkos makloon negatif

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Barang Supplier dan Kontrak Supplier → perubahan data → simulasi tarif makloon.

**Rantai kejadian:** Create menolak tarif -5 → PATCH menerimanya → tariff-preview qty 10 menghasilkanamount -50; barang supplier PATCH harga/MOQ/lead negatifjuga diterima.

**Letak kesalahan dan penyebab:** Create schemas menetapkan ge/le, Patch optional types tidak mempertahankannya. Service patch tidak mengulangi validasi domain numerik; kalkulator menggunakan nilai tersimpan.

**Dampak, hasil reproduksi, dan batas klaim:** Original API kontrol create negative/percentage 101 → 422 dan normal create200. PATCH contract menerima tarif/mincharge/yield/MOQ/leadnegative serta shrinkage/tolerance/byproduct101. Tarif negatif memberi pratinjauamount -50. SupplierItem PATCH menerima harga/MOQ/lead-1 walaupun create menolak422 dan CSVharga-1 dinyatakaninvalid. Tidak ada klaim jurnal negatif sudah terposting dari kasus ini.

**Lokasi source pada commit audit:**

- [backend/schemas_contracts.py:62](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_contracts.py#L62) — `class SupplierContractPatch`.
- [backend/schemas_contracts.py:28](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_contracts.py#L28) — `class SupplierContractCreate`.
- [backend/schemas_supplier_items.py:41](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/schemas_supplier_items.py#L41) — `class SupplierItemPatch`.
- [backend/services/contract_service.py:246](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contract_service.py#L246) — `async def patch_contract`.
- [backend/services/supplier_item_service.py:232](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/supplier_item_service.py#L232) — `async def patch_item`.
- [backend/services/contract_service.py:530](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contract_service.py#L530) — `"amount": total`.

```python
60: 
61: 
62: class SupplierContractPatch(BaseModel):
63:     title: Optional[str] = None
64:     partner_name: Optional[str] = None
65:     process_type: Optional[str] = None
66:     product_id: Optional[str] = None
67:     input_product_id: Optional[str] = None
68:     tariff_basis: Optional[str] = None
```

**Bukti asli:** [evidence/repro/commercial-patch-bounds90-results.json](evidence/repro/commercial-patch-bounds90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| bounds.item_patch_reject_last_price | true | false | observed_difference |
| bounds.item_patch_reject_moq | true | false | observed_difference |
| bounds.item_patch_reject_lead_time_days | true | false | observed_difference |
| bounds.contract_patch_reject_tariff_rate | true | false | observed_difference |
| bounds.contract_patch_reject_min_charge | true | false | observed_difference |
| bounds.contract_patch_reject_shrinkage_pct | true | false | observed_difference |
| bounds.contract_patch_reject_tolerance_pct | true | false | observed_difference |
| bounds.contract_patch_reject_byproduct_pct | true | false | observed_difference |
| bounds.contract_patch_reject_yield_factor | true | false | observed_difference |
| bounds.contract_patch_reject_moq | true | false | observed_difference |

**Prompt agent development:**

Pertahankan constraint producer pada patch dan validasi service sebelum persist/calculation. Definisikan validator domain bersama bagi CRUD/import/snapshot/override. Data lama invalid harus diidentifikasi dan ditangani tanpa mengubah dokumen posted secara senyap.

**Kriteria penerimaan untuk reviewer:**

Invalid numericpatch ditolak400/422 dan DB tidak berubah. Normal patch tetap berfungsi; semua tarif/resultfinite dan valid. Uji negative, 0, percentage100/101, null/empty, currencyprecision, CSV/XLSX, contract override, mincharge, biaya tambahan dan seluruh consumer PR/PO/MKO/HPP.

## D4-BUD-EDIT-01 — Perubahan anggaran melewati keunikan periode/kunci dan batas tahun

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_public_api_counterexample`.

**Layar/alur:** Finance → Anggaran → ubah tahun/bulan → kontrol PO dan laporan anggaran.

**Rantai kejadian:** Create dua anggaran Januari150 dan Februari200 untuk kunci yang sama → PATCH Februari menjadi Januari diterima → dua envelope pada kombinasi yang seharusnya tunggal; PATCH year1900 juga diterima.

**Letak kesalahan dan penyebab:** Create memeriksa duplikasi entity/year/month/dimension/key dan tahun 2000–2999. Update hanya memeriksa batas bulan dan amount, tidak memeriksa kombinasi hasil merge atau batas tahun; indeks unik komposit tidak ditemukan pada indeks bootstrap.

**Dampak, hasil reproduksi, dan batas klaim:** Original API menolak duplicate create dan tahun1900/3000. PATCH month menjadi1 pada anggaran Februari mengembalikan200 dan query DB menemukan dua anggaran Januari pada kunci yang sama; PATCH year1900 juga200. Laporan menjumlahkan setiap baris, sementara check_budget menggunakan find_one untuk envelope bulanan: duplicate membuat SSOT budget tidak lagi tunggal. Tidak diklaim ada PO over-budget yang benar-benar terposting pada skenario ini.

**Lokasi source pada commit audit:**

- [backend/services/budget_service.py:209](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L209) — `async def update_budget(`.
- [backend/services/budget_service.py:175](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L175) — `if year < 2000 or year > 2999:`.
- [backend/services/budget_service.py:183](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L183) — `dupe = await db.budgets.find_one(`.
- [backend/services/budget_service.py:434](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L434) — `monthly = await db.budgets.find_one(`.
- [backend/services/budget_service.py:352](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/budget_service.py#L352) — `for b in budgets:`.

```python
207: 
208: 
209: async def update_budget(budget_id: str, patch: Dict[str, Any],
210:                         scope: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
211:     q = {"id": budget_id, **(scope or {})}
212:     upd: Dict[str, Any] = {"updated_at": now_iso()}
213:     if patch.get("amount") is not None:
214:         amount = _r(patch["amount"])
215:         if amount <= 0:
```

**Bukti asli:** [evidence/repro/budget-ledger-policy90-results.json](evidence/repro/budget-ledger-policy90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| budget.patch_duplicate_rejected | true | false | observed_difference |
| budget.single_envelope_per_key | 1 | 2 | observed_difference |
| budget.patch_invalid_year_rejected | true | false | observed_difference |

**Prompt agent development:**

Validasi hasil merge patch dengan invariant create, termasuk rentang tahun dan keunikan komposit. Tambahkan constraint database yang sesuai setelah konflik lama direkonsiliasi; buat respons 400/409 yang dapat dipahami pengguna. Jangan diam-diam menjumlahkan atau menghapus anggaran konflik. Pastikan report dan check_budget memakai envelope kanonik yang sama.

**Kriteria penerimaan untuk reviewer:**

PATCH konflik ditolak dan kedua anggaran asli tetap utuh; year1900/3000 ditolak. Uji concurrent create/update, annual month0 dan monthly1–12, rename periode, filter entitas/dimensi, rollback kegagalan DB dan kesesuaian laporan vs enforcement PO.

## D4-UOM-BF-01 — Backfill jumlah roll memakai panjang daftar ID mentah, berbeda dari resolver roll nyata

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_scanner_or_migration_with_explicit_legacy_fixture`.

**Layar/alur:** Migrasi dua satuan → dokumen retur/transfer/SJ lama → kolom jumlah roll.

**Rantai kejadian:** roll_ids R1,R1,MISSING → helper actual-roll1 → backfill qty_rolls3.

**Letak kesalahan dan penyebab:** Backfill menganggap setiap elemen daftar mewakili satu roll, tanpa deduplikasi/verifikasi, sedangkan rolls_of_ids memakai count_documents atas ID nyata.

**Dampak, hasil reproduksi, dan batas klaim:** Terbukti pada fixture data lama yang sengaja memiliki referensi duplikat/hilang; tidak ada klaim producer normal menghasilkan referensi tersebut. Ini kegagalan alat pemulihan data untuk mendeteksi/menandai data lama tidak valid; hasil3 dapat terlihat sebagai angka roll pasti.

**Lokasi source pada commit audit:**

- [backend/services/dual_qty_service.py:169](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/dual_qty_service.py#L169) — `async def backfill(`.
- [backend/services/dual_qty_service.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/dual_qty_service.py#L129) — `async def rolls_of_ids`.
- [scripts/migrate_qty_rolls.py:54](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/scripts/migrate_qty_rolls.py#L54) — `backfill`.

```python
167: 
168: 
169: async def backfill(dbx, *, demo_plan: bool = False, dry_run: bool = False) -> Dict[str, int]:
170:     """Isi `qty_rolls` (dan `secondary_measures`) DARI ROLL NYATA — bukan menebak.
171: 
172:     Aturan (dan alasan tiap aturan):
173:       * `inventory_movements` : baris yang menunjuk satu `roll_id` = **1 roll**.
174:       * `wms_tasks`           : jumlah roll yang lahir dari tugas itu (`grn_task_id`).
175:       * `purchase_orders`     : `items[].received_rolls` = roll nyata ber-`po_id` + produk.
```

**Bukti asli:** [evidence/repro/quantity-provenance90-results.json](evidence/repro/quantity-provenance90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| backfill.dry_run_has_no_write | false | false | pass |
| backfill.dry_run_matches_write_counts | {"inventory_movements": 1, "wms_tasks": 1, "purchase_orders": 1, "sales_returns": 1, "purchase_returns": 1, "interco_returns": 1, "warehouse_transfers": 1, "shipments": 1, "makloon_orders": 1, "inventory_rolls": 1} | {"inventory_movements": 1, "wms_tasks": 1, "purchase_orders": 1, "sales_returns": 1, "purchase_returns": 1, "interco_returns": 1, "warehouse_transfers": 1, "shipments": 1, "makloon_orders": 1, "inventory_rolls": 1} | pass |
| backfill.movement_is_single_roll | 1 | 1 | pass |
| backfill.task_real_count | 2 | 2 | pass |
| backfill.received_real_count | 2 | 2 | pass |
| backfill.production_plan_not_guessed | false | false | pass |
| backfill.actual_weight | 12.346 | 12.346 | pass |
| backfill.preserve_existing_count | 7 | 7 | pass |
| backfill.no_rolls_no_task_guess | false | false | pass |
| backfill.shipment_actual_rolls | 2 | 2 | pass |

**Prompt agent development:**

Satukan derivasi jumlah roll dan aturan ID unik. Untuk referensi hilang/arsip yang tidak bisa dibuktikan, jangan menebak: laporkan conflict/incomplete dan butuh keputusan. Jangan mengganti jumlah historis sah tanpa bukti rekonsiliasi.

**Kriteria penerimaan untuk reviewer:**

Dry-run tidak menulis; duplikat tidak dihitung dua kali; dangling/archived references dilaporkan jelas. Dokumen historis valid tetap benar; migration berulang idempoten, qty_rolls yang sudah diketahui tidak ditimpa.

