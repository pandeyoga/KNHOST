# Meja gelombang 2 — Admin Sales + Keuangan di tempat, rincian dokumen Keuangan — Rencana Kerja

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Setiap baris Meja Admin Sales dan Meja Keuangan membuka pop-up berisi rincian dokumen yang benar (barang, jumlah, harga) dan aksi yang bisa diselesaikan di tempat; setiap nomor nota di layar Keuangan bisa diklik untuk melihat rincian barangnya.

**Architecture:** Satu registri **pratinjau dokumen** (`docType → muat + isi`) dipakai tiga jalur: pop-up meja (`DeskRowDetail` via registri panel meja), tautan nomor dokumen di layar daftar Keuangan (`DocLink` → `DocPreviewModal` yang di-host sekali di `AppViewRouter`, pola `PartyCardHost`), dan pratinjau bertumpuk (kwitansi → pesanan). Isi pratinjau baru, hanya-baca, token penuh; aksi tetap memakai dialog yang sudah ada (diekstrak bila logikanya masih tertanam di layar).

**Tech Stack:** React 18 + Tailwind (token `text-fs-*`, warna `kn-*`), axios, Jest + RTL (`frontend/src/features/__tests__/`); FastAPI + pytest `backend/tests_mem`.

**Spec:** `docs/superpowers/specs/2026-11-25-meja-kerja-di-tempat-design.md` (disetujui pemilik 25 Nov) — §5.3, §5.4, §5.5, §5.7 (baris Admin Sales & Keuangan), §5.7a, §6 gelombang 2. Inventaris faktual: `/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/mg2_inventaris.md` (pengendali menyalinnya ke ruang kerja SDD sebagai `inventaris.md`).

## Global Constraints

- Bahasa Indonesia untuk UI, komentar, pesan commit. Line ending LF.
- Pop-up hanya `DetailModal` / `FormModal` / `ConfirmModal` (`askConfirm`/`askReason`). **Tidak** memakai `DetailPopup` di berkas baru (ia overlay sendiri, ratchet `custom_modals`). Tidak ada `alert/confirm/prompt`, tidak ada `keydown/Escape` sendiri.
- Aksi di pop-up memakai endpoint dan pemeriksaan yang sama dengan layar asalnya. **Tidak ada endpoint baru untuk aksi yang sudah ada**; isi pratinjau memakai endpoint baca yang sudah ada (`GET /sales-orders/{id}`, `/vendor-bills/{id}`, `/purchase-orders/{id}`, `/ar-receipts/{id}`, `/contra-bons/{id}`, `/sales-returns/{id}`, `/special-orders/{id}`, `/internal-requests/{id}`).
- Wewenang dari **izin** (`can(perms, resource, action)`), bukan nama peran. Tombol/aksi yang bisa 403 dipagari izin di kode.
- Huruf: hanya `text-fs-12/13/14/16/20`, minimal 12 px. Peran: judul kartu 14/600; nomor dokumen 13/600; nama pihak 13/400; nilai 13/600; lencana & umur 12/500; label kolom tabel 12/600 tanpa huruf besar; teks lain 12–13/400. Maksimal dua unsur semi-tebal per baris.
- Berkas BARU: nol `text-[Npx]`, nol hex mentah, nol `<button>` bergaya sendiri (`primary-button`/`secondary-button`/`link-button`/`icon-button`), nol `|| x.id` sebagai label.
- Jejak Dokumen tetap tersedia dari pop-up (tautan "Jejak").
- Aksi yang masih harus pindah halaman: tombolnya bertanda ikon `ExternalLink` (pola `DeskRowDetail`), alasannya dicatat di laporan tugas.
- Uji hemat: uji terarah selama bekerja; suite penuh + gate sekali di Tugas 10.
- Jangan sentuh `deploy/`, `.env`, `memory/GATE_RECEIPT.*`, `frontend/yarn.lock`, arsip `docs/reviews/*/`. Jangan push.

## Review Focus

1. Pengguna tanpa izin baca jenis dokumen itu: `DocLink` menampilkan teks biasa (bukan tautan yang berujung 403); bila tetap 403 (izin berubah), pop-up menampilkan pesan, bukan kosong — uji di Tugas 1.
2. Dokumen tidak ditemukan / dihapus (404) atau jaringan gagal → `ErrorNotice` di dalam pop-up dengan "Coba lagi" — uji di Tugas 1.
3. Baris tanpa id dokumen (alokasi kwitansi lama tanpa `order_id`, baris rekening koran ber-jenis yang tak punya pratinjau) → teks biasa atau "Jejak", tidak ada tautan mati — uji di Tugas 4.
4. Mode "Semua PT": dokumen milik PT lain yang diizinkan tetap termuat di pratinjau (header PT dokumen), dokumen PT yang tidak diizinkan tidak — uji backend+frontend di Tugas 1.
5. Pratinjau bertumpuk: dari kwitansi membuka pesanan lalu "Kembali" kembali ke kwitansi; Esc / klik latar menutup seluruh pop-up; membuka dari meja tidak menumpuk dua `DetailModal` — uji di Tugas 2 dan 6.

---

### Task 1: Fondasi pratinjau dokumen + pratinjau pesanan penjualan

**Files:**
- Create: `frontend/src/features/documents/preview/docPreviewRegistry.js`
- Create: `frontend/src/features/documents/preview/DocPreviewModal.jsx`
- Create: `frontend/src/features/documents/preview/DocLink.jsx`
- Create: `frontend/src/features/documents/preview/bodies/SalesOrderPreview.jsx`
- Create: `frontend/src/features/documents/preview/previewParts.jsx` (tabel barang, baris fakta, ringkasan total — dipakai semua isi)
- Modify: `frontend/src/context/AppNavContext.jsx` (state + `openDocPreview`/`closeDocPreview`, `previewsEnabled`)
- Modify: `frontend/src/AppViewRouter.jsx` (render `<DocPreviewHost>` di samping `PartyCardHost`, ±baris 469)
- Test: `frontend/src/features/__tests__/mejaG2DocPreview.test.js`

**Interfaces:**
- Produces:
  - `DOC_PREVIEWS: { [docType]: { label: string, perm: [resource, action], load: (id, {entityId}) => Promise<doc>, Body: Component<{doc, push(target), currentUser}>, full: (doc) => link } }`, `previewFor(docType) → entry|null`, `canPreview(perms, docType) → boolean` (registri ada **dan** `can(perms, ...perm)`).
  - Target: `{ docType: string, docId: string, number?: string, entityId?: string }`.
  - `useAppNav().openDocPreview(target)`, `closeDocPreview()`, `previewsEnabled` (false di `NOOP_NAV`).
  - `<DocPreviewModal target onClose currentUser />` — `DetailModal framed size="md"`, tumpukan target internal (`push(target)`; tombol "‹ Kembali" bila tumpukan > 1), muat via registri, `ErrorNotice` (prop `message`, `onRetry`) bila gagal; kaki: "Jejak" (`openTrace({docType, docId, number})`) + "Buka layar penuh" (`nav.openDocument(entry.full(doc))`, lalu tutup).
  - `<DocPreviewHost currentUser />` — merender `DocPreviewModal` untuk `nav.docPreview`.
  - `<DocLink docType docId number entityId testId className />` — `link-button` yang memanggil `openDocPreview` bila `previewsEnabled && docId && canPreview(perms, docType)`; selain itu `<span>` teks biasa (pola `CardLink` di `features/finance/cards/partyCards.jsx:88`). Izin dibaca dari `currentUser` lewat konteks yang sama dengan `CardLink`.
  - `previewParts.jsx`: `PreviewFacts({ items:[{key,label,content}] , testId })`, `PreviewLines({ columns:[{key,label,align?,render?}], rows, testId })`, `PreviewTotals({ rows:[{label,value,strong?}], testId })`.
  - `sales_order`: `perm ["order","view"]`, muat `GET /sales-orders/{id}`, `full = ({...ROW_TARGET.sales_order, focus_id: doc.id, number: doc.number})` (`ROW_TARGET` dari `features/sales_admin/workDeskApi.js`).

- [ ] **Step 1: Tulis uji gagal** di `mejaG2DocPreview.test.js`:
  - `pratinjau pesanan menampilkan baris barang`: mock `GET /sales-orders/so1` → `{id:"so1", number:"KSC/SO-00001", customer_name:"Toko A", entity_id:"ent_ksc", status:"confirmed", items:[{product_name:"Katun A", sku:"KA-01", quantity:10, unit:"meter", price:25000, subtotal:250000}], grand_total:277500, ppn_amount:27500, paid_total:0}`; render `DocPreviewModal` target `{docType:"sales_order", docId:"so1"}` → teks "Katun A", "10 meter", "Rp 25.000", "Rp 277.500" tampil; `data-testid="doc-preview-lines"` ada.
  - `galat muat menampilkan ErrorNotice dan coba lagi`: GET menolak 404 → `doc-preview-error` tampil; klik "Coba lagi" memanggil GET dua kali.
  - `DocLink tanpa izin = teks biasa`: perms tanpa `order.view` → tidak ada `button`, teks nomor tampil.
  - `DocLink dengan izin membuka pratinjau`: klik → `openDocPreview` dipanggil dengan `{docType:"sales_order", docId:"so1", number:"KSC/SO-00001"}`.
  - `tumpukan: push lalu Kembali`: Body uji memanggil `push({docType:"sales_order", docId:"so2"})` → tombol `doc-preview-back` muncul; klik → kembali ke target pertama.
  - `berkas baru bebas px & hex`: baca isi berkas-berkas di `features/documents/preview/**` → tidak cocok `/text-\[\d/` maupun `/#[0-9A-Fa-f]{3,6}\b/`.
- [ ] **Step 2: Jalankan, pastikan gagal** — `cd frontend && CI=true yarn test --watchAll=false src/features/__tests__/mejaG2DocPreview.test.js` → FAIL (modul tidak ada).
- [ ] **Step 3: Implementasi** berkas di atas. `SalesOrderPreview`: fakta (Pelanggan + `CustomerCardLink` bila tersedia, Sales, PT pendek via `entityShortById`, Status, Pembayaran, Tanggal, Batas cadangan bila `booking_until`), tabel barang (Barang+SKU, Jumlah = `formatQty(quantity)` + satuan jual, Harga, Diskon bila ada, Subtotal), total (Subtotal, PPN, Total, Sudah dibayar, Sisa). Muat dokumen lintas PT: bila `target.entityId` ada, kirim header `X-Entity-Id: <entityId>` pada GET (pola header entitas yang dipakai axios aplikasi — cek interceptor di `frontend/src/` sebelum menulis).
- [ ] **Step 4: Uji backend isolasi** (Review Focus 4) di `backend/tests_mem/test_MEJA_G2_pratinjau.py`: `test_pesanan_pt_lain_diizinkan_termuat` (pengguna ber-`allowed_entity_ids` [ksc, kanda], header `X-Entity-Id: ent_kanda`, GET pesanan kanda → 200) dan `test_pesanan_pt_tak_diizinkan_ditolak` (pengguna hanya ksc, header kanda → 403). Bila keduanya sudah hijau tanpa perubahan server, catat di laporan — tidak ada perubahan server di tugas ini.
- [ ] **Step 5: Jalankan uji** jest berkas ini + pytest berkas baru → PASS; `python scripts/guardrails/verify_ui_standard.py` dan `verify_custom_modals.py` tidak menambah merah.
- [ ] **Step 6: Commit** `feat(dokumen): pratinjau dokumen di pop-up — registri, DocLink, pesanan penjualan`.

### Task 2: Isi pratinjau dokumen keuangan — tagihan pemasok, PO, kwitansi, kontrabon

**Files:**
- Create: `frontend/src/features/documents/preview/bodies/VendorBillPreview.jsx`, `PurchaseOrderPreview.jsx`, `ArReceiptPreview.jsx`, `ContraBonPreview.jsx`
- Modify: `frontend/src/features/documents/preview/docPreviewRegistry.js`
- Test: `frontend/src/features/__tests__/mejaG2DocPreviewKeuangan.test.js`

**Interfaces:**
- Consumes: Tugas 1 (`DOC_PREVIEWS`, `previewParts`, `push`).
- Produces entri registri: `vendor_bill` (`["vendor_bill","view"]`, `GET /vendor-bills/{id}`), `purchase_order` (`["purchase_order","view"]`, `GET /purchase-orders/{id}`), `ar_receipt` (`["ar_receipt","view"]`, `GET /ar-receipts/{id}`), `contra_bon` (`["contra_bon","view"]`, `GET /contra-bons/{id}`). Nama aksi izin persis seperti di `backend/permissions_config.py` — periksa dan sesuaikan bila berbeda, catat di laporan. `full` memakai `ROW_TARGET`/target navigasi yang sudah ada untuk jenis itu (cari di `workDeskApi.js`, `config/waitingBoards.js`); bila tak ada, `full = null` dan tombol "Buka layar penuh" tidak dirender.

- [ ] **Step 1: Tulis uji gagal:**
  - `tagihan pemasok: kolom barang` — `items[]` `{product_name, sku, billed_qty, price, line_total}` → tampil; total = `grand_total`.
  - `PO: baris barang + status terima` — `items[]` `{product_name, quantity, unit, price, received_qty}`.
  - `kwitansi: alokasi bisa dibuka` — `allocations:[{order_id:"so1", order_number:"KSC/SO-00001", applied:100000}, {order_number:"LAMA-1", applied:5000}]` → baris pertama tombol yang memanggil `push({docType:"sales_order", docId:"so1", ...})`; baris kedua (tanpa `order_id`) teks biasa (Review Focus 3).
  - `kontrabon: gabungan baris faktur` — `GET /contra-bons/cb1` → `bills:[{bill_id:"b1", bill_number:"VB-1"}, {bill_id:"b2", bill_number:"VB-2"}]`; isi memuat `GET /vendor-bills/b1` dan `/b2` (paralel, paling banyak 20 faktur; lebih dari itu tampil pesan "Tampil 20 faktur pertama") dan menampilkan satu tabel barang berkelompok per faktur; nomor faktur memanggil `push({docType:"vendor_bill", docId})`; satu faktur gagal dimuat → baris kelompoknya menampilkan galat, faktur lain tetap tampil.
- [ ] **Step 2: Jalankan → FAIL.**
- [ ] **Step 3: Implementasi** empat isi + entri registri.
- [ ] **Step 4: Jalankan → PASS** (+ uji Tugas 1 tetap hijau).
- [ ] **Step 5: Commit** `feat(dokumen): pratinjau tagihan pemasok, PO, kwitansi (alokasi bisa dibuka), kontrabon (gabungan baris faktur)`.

### Task 3: Isi pratinjau dokumen penjualan lain — retur, pesanan khusus, permintaan internal

**Files:**
- Create: `frontend/src/features/documents/preview/bodies/SalesReturnPreview.jsx`, `SpecialOrderPreview.jsx`, `InternalRequestPreview.jsx`
- Modify: `docPreviewRegistry.js`
- Test: `frontend/src/features/__tests__/mejaG2DocPreviewPenjualan.test.js`

**Interfaces:**
- Produces entri: `sales_return` (`["sales_return","view"]`, `GET /sales-returns/{id}`), `special_order` (`["special_order","view"]` — cek nama sumber daya di `permissions_config.py`, `GET /special-orders/{id}`), `internal_request` (`["internal_request","view"]`, `GET /internal-requests/{id}`).

- [ ] **Step 1: Tulis uji gagal:** masing-masing menampilkan fakta inti (pihak, status berlabel Indonesia — pakai pemetaan label yang sudah ada di layar asalnya, jangan menulis ulang kamus), alasan/keterangan utuh, dan tabel barang (`items[]`: barang, jumlah + satuan, untuk retur juga kondisi/alasan per baris bila ada); pesanan asal retur (`order_id`) bisa dibuka (`push` sales_order).
- [ ] **Step 2: → FAIL.** **Step 3: Implementasi.** **Step 4: → PASS.**
- [ ] **Step 5: Commit** `feat(dokumen): pratinjau retur, pesanan khusus, permintaan internal`.

### Task 4: §5.7a sisi piutang — nomor dokumen bisa diklik

**Files (Modify):**
- `frontend/src/features/finance/ARAgingDetail.jsx` (nomor pesanan ±:171 dan jadwal tagihan ±:429)
- `frontend/src/features/crm/CollectionWorklist.jsx` (±:117, tautan mati)
- `frontend/src/features/crm/ARReceiptsHistory.jsx` (nomor kwitansi ±:255, pesanan teralokasi ±:225 — tiap nomor jadi `DocLink` sendiri)
- `frontend/src/features/crm/CustomerBillingTab.jsx` (±:96-100), `CustomerStatementTab.jsx` (±:55-58: `sales_order`, `ar_receipt` → `DocLink`; jenis lain tetap tombol Jejak)
- `frontend/src/features/finance/TaxInvoices.jsx` (`TaxInvoiceDetail` ±:530: tabel barang dari `fkt.items` dengan `PreviewLines`; `SourceCell` nomor pesanan → `DocLink`, bukan pindah layar)
- `frontend/src/features/finance/payments/PaymentVarianceQueue.jsx` (nomor kwitansi → `DocLink ar_receipt`), `PenaltyPanel.jsx` (dasar denda `doc_type==="sales_order"` → `DocLink`; jenis lain tetap Jejak)
- Test: `frontend/src/features/__tests__/mejaG2KeuanganPiutang.test.js`

**Interfaces:** Consumes `DocLink` (Tugas 1), entri `ar_receipt` (Tugas 2). Tombol "Jejak" yang sudah ada **dipertahankan** di samping (Jejak tetap tersedia).

- [ ] **Step 1: Tulis uji gagal** per layar: render dengan data contoh (bentuk baris persis dari inventaris §3), klik nomor → `openDocPreview` dipanggil dengan `{docType, docId, number}` yang benar; baris tanpa id → teks biasa; Faktur Keluaran: rincian menampilkan "Katun A" dari `fkt.items`.
- [ ] **Step 2: → FAIL. Step 3: Implementasi.** Berkas yang disentuh: ukuran huruf yang disentuh baris itu memakai token; jangan menambah hex/px.
- [ ] **Step 4: → PASS**; uji jest lama berkas-berkas ini (`grep -l` nama komponen di `__tests__`) tetap hijau; `verify_ui_standard.py`, `verify_detail_modal.py` tidak menambah merah.
- [ ] **Step 5: Commit** `feat(keuangan): nomor nota di Piutang, Penagihan, Kwitansi, Kartu pelanggan, Faktur Keluaran, Selisih & Denda membuka rincian barang`.

### Task 5: §5.7a sisi hutang & kas

**Files (Modify):**
- `frontend/src/features/finance/ap/APSupplierDetail.jsx` (tagihan ±:166 → `DocLink vendor_bill`; kontrabon ±:209 → `DocLink contra_bon`; Jejak tetap)
- `frontend/src/features/purchasing/contrabon/ContraBonParts.jsx` (±:84 nomor faktur → `DocLink vendor_bill`)
- `frontend/src/features/purchasing/Supplier360Panel.jsx` (`openBill` ±:141 dan `openReturn` ±:156: isi `itemColumns` — tagihan: Barang, SKU, Ditagih, Harga, Jumlah; retur beli: Barang, SKU, Jumlah + satuan, Harga, Subtotal)
- `frontend/src/features/purchasing/CashManagementView.jsx` (±:395-425: kolom "Sumber" — `t.ref_type` + `t.ref_id` → `DocLink` bila registri punya jenis itu (peta `ar_receipt`→`ar_receipt`, `vendor_bill_payment`→`vendor_bill` hanya bila `ref_id` adalah id tagihan — periksa `cash_ledger.py` dan isi `ref_id` tiap kategori sebelum memetakan; jenis yang tak pasti → teks `REF_LABEL` + Jejak); "Jurnal" → `JournalDetailModal` (`features/finance/JournalDetailModal.jsx`) bila `journal_entry_id` ada)
- Test: `frontend/src/features/__tests__/mejaG2KeuanganHutangKas.test.js`

- [ ] **Step 1: Tulis uji gagal** (pola Tugas 4) + `Supplier360Panel` `itemColumns` tagihan ber-5 kolom dan retur ber-5 kolom.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS** (+ uji lama berkas itu).
- [ ] **Step 5: Commit** `feat(keuangan): Hutang per pemasok, Kontrabon, Kartu pemasok, Transaksi Kas — nomor membuka rincian barang & jurnal`.

### Task 6: Registri panel meja per antrean + pratinjau di pop-up meja

**Files:**
- Modify: `frontend/src/features/desks/deskPanels.js` (kunci `queue:<id>` didahulukan, lalu `<ref_type>`; `panelFor(row, queue)`)
- Modify: `frontend/src/features/desks/DeskRowDetail.jsx` (panggil `panelFor(row, queue)`)
- Create: `frontend/src/features/desks/DeskDocPanel.jsx`
- Modify: `backend/services/work_desk_service.py` (baris `denda_draft` ±:586 membawa `doc_type`, `doc_id` dari dokumen denda; baris `selisih_bayar` ±:568 membawa `order_ids` dari `target_order_ids`)
- Test: `frontend/src/features/__tests__/mejaG2DeskPanels.test.js`, `backend/tests_mem/test_MEJA_G2_baris.py`

**Interfaces:**
- Produces: `panelFor(row, queue) → Component|null`; `DeskDocPanel({ row, queue, docType, docId })` = fakta ringkas baris (Keterangan utuh, nilai, umur — tanpa mengulang judul/subjudul pop-up) + `Body` registri untuk dokumen itu (dimuat di dalam panel; galat → `ErrorNotice` di panel, fakta baris tetap tampil). Pemetaan (satu tabel `DESK_DOC_OF` di `deskPanels.js`):

| Kunci | docType | docId |
|---|---|---|
| `sales_order` (semua antrean SO + Pelacak SO + HP) | `sales_order` | `row.ref_id` |
| `queue:uang_masuk`, `queue:bayar_sebelum_kirim` | `sales_order` | `row.order_id` |
| `queue:selisih_bayar` | `ar_receipt` | `row.ref_id` |
| `queue:denda_draft` | `row.doc_type` bila `sales_order`, selain itu panel umum | `row.doc_id` |
| `purchase_order` | `purchase_order` | `row.ref_id` |
| `sales_return` | `sales_return` | `row.ref_id` |
| `special_order` | `special_order` | `row.ref_id` |
| `internal_request` | `internal_request` | `row.ref_id` |
| papan kontrabon (`contra_bon_verify/approve/dispute`) | `contra_bon` | `row.ref_id` |

  Baris tanpa `docId` atau pengguna tanpa izin baca jenis itu → panel umum (gelombang 1). Kunci `customer` **tidak** dipetakan (dua arti; ditangani Tugas 8).
- Server: `denda_draft` → `doc_type`, `doc_id` ditambahkan ke baris; `selisih_bayar` → `order_ids: list[str]`. Tanpa mengubah isian lain.

- [ ] **Step 1: Tulis uji gagal:**
  - jest `baris SO membuka pratinjau pesanan di pop-up meja` (mock GET pesanan; `DeskRowDetail` row `{ref_type:"sales_order", ref_id:"so1"}` → "Katun A" tampil, kaki pop-up tetap punya tombol aksi + "Buka layar penuh").
  - jest `uang masuk memakai order_id, bukan ref_id pelanggan`.
  - jest `tanpa izin baca → panel umum`.
  - jest `Pelacak SO ikut pratinjau` (row dari `trackerRowToDeskRow`).
  - jest `satu DetailModal` — membuka pop-up meja tidak merender `DocPreviewModal` kedua (Review Focus 5).
  - pytest `test_denda_draft_membawa_dokumen_dasar`, `test_selisih_bayar_membawa_order_ids` (pola fixture `backend/tests_mem/test_MEJA3*.py`).
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS** (+ `test_MEJA*.py`, `meja*.test.js` lama).
- [ ] **Step 5: Commit** `feat(meja): pop-up meja memuat rincian dokumen per antrean (registri panel per antrean)`.

### Task 7: Aksi di tempat Meja Keuangan — selisih bayar, denda, bayar sample, tagih

**Files:**
- Create: `frontend/src/features/finance/payments/PaymentVarianceDecideDialog.jsx` (muat penilaian + kirim keputusan; diekstrak dari `PaymentVarianceQueue.jsx` `openDecide` ±:88-107 dan `confirm` ±:109-120; merender `PaymentVarianceDialog` yang sudah ada)
- Create: `frontend/src/features/finance/payments/penaltyIssue.js` (`useIssuePenalty()` → `issue(row)`: `askConfirm` dengan teks yang sama dengan `CreditDeskView.jsx:150-158` + `issuePenalty(row.id, key)` lewat `useIntentKey("pnl-terbit")`)
- Create: `frontend/src/features/crm/collectionMark.js` (`markReminded({customer_id, order_id, order_number})` → `POST /collection-reminders/mark`, catatan `Pengingat penagihan <nomor>` — teks sama dengan `CollectionWorklist.jsx:62`)
- Modify: `PaymentVarianceQueue.jsx`, `CreditDeskView.jsx`, `PenaltyPanel.jsx` (memakai komponen/hook bersama — satu sumber), `CollectionWorklist.jsx`, `MobileCollectionTargets.jsx` (memakai `markReminded`)
- Modify: `frontend/src/features/finance/FinanceDesk.jsx` (`IN_PLACE` ±:133 + `handleAction`)
- Test: `frontend/src/features/__tests__/mejaG2KeuanganAksi.test.js`

**Interfaces:**
- `PaymentVarianceDecideDialog({ receiptId, receiptNumber, onClose, onDone(msg) })`.
- `useIssuePenalty() → { issue(row): Promise<boolean>, busy }`.
- `markReminded(row) → Promise<void>`.
- Meja Keuangan, aksi baru di tempat:
  - `decide_variance` → `PaymentVarianceDecideDialog` (izin `payment_variance.decide`);
  - `issue_penalty` → `useIssuePenalty` (izin `penalty.issue`);
  - antrean `sample_acc_bayar` → `SamplePaymentApproveDialog` (gelombang 1, `features/samples/`; izin `sample_order.approve_payment`);
  - antrean `jatuh_tempo` (Piutang lewat tempo): aksi utama "Catat sudah ditagih" → `markReminded` (izin `order.update`; tanpa izin → navigasi lama), aksi tambahan "Terima pembayaran" tetap (`_moreActions`).
- Tetap pindah layar (ikon + alasan di laporan): `nota_batal_item` (tinjau nota kredit bertahap), `retur_putus_nilai` (keputusan kompensasi bertahap di Retur), papan kontrabon (verifikasi/setujui/sengketa bertahap), `posting_gagal`.
- Sukses: toast + muat ulang kartu (pola gelombang 1); galat: di dalam dialog.

- [ ] **Step 1: Tulis uji gagal:** keputusan selisih dari meja memanggil endpoint keputusan yang sama dengan antrean (`decideVariance`) dengan kunci intent; denda dari meja menampilkan `askConfirm` lalu `issuePenalty`, batal = tidak ada panggilan; bayar sample membuka dialog konfirmasi; "Catat sudah ditagih" memanggil `POST /collection-reminders/mark` dengan `customer_id`, `order_id`; tanpa izin `order.update` tombol menavigasi seperti dulu; layar asal (`PaymentVarianceQueue`, `CreditDeskView`, `PenaltyPanel`, `CollectionWorklist`) tetap lulus uji lamanya.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS.**
- [ ] **Step 5: Commit** `feat(meja-keuangan): putuskan selisih, terbitkan denda, setujui bayar sample, catat sudah ditagih — di tempat`.

### Task 8: Aksi di tempat Meja Admin Sales — tetapkan sales, pengingat, tolak PIN, lihat

**Files:**
- Create: `frontend/src/features/sales_admin/AssignSalesDialog.jsx` (`FormModal`: pilih sales dari `GET /sales-users`, alasan wajib; kirim `POST /customers/{id}/reassign` body `{assigned_sales_id, reason}` — sama dengan `ReassignModal` di `crm/Customer360Panel.jsx:~385-410`)
- Create: `frontend/src/features/desks/CustomerQueuePanel.jsx` (panel antrean `pelanggan_tanpa_sales`: fakta pelanggan dari baris + `CustomerCardLink`)
- Modify: `frontend/src/features/sales_admin/SalesAdminDesk.jsx` (`IN_PLACE` ±:35, `handleAction` ±:107), `deskPanels.js` (`queue:pelanggan_tanpa_sales` → `CustomerQueuePanel`), `frontend/src/features/sales/mobile/MobileSalesAdminDesk.jsx` (aksi sama di HP)
- Modify: `scripts/audit_sales_roles_ux.py` `TERGATED_DI_KODE` hanya untuk panggilan yang benar-benar dipagari izin di kode baru (alamat pagar ditulis)
- Test: `frontend/src/features/__tests__/mejaG2AdminSalesAksi.test.js`

**Interfaces / perilaku:**
- `pelanggan_tanpa_sales` "Tetapkan sales" → `AssignSalesDialog` **hanya bila** `can(perms,"sales_force","assign")`; selain itu navigasi lama (ikon). Matriks bawaan tidak memberi izin ini ke Admin Sales — **jangan mengubah matriks izin**; pengendali menanyakannya ke pemilik.
- `jatuh_tempo` "Follow-up" → "Catat sudah diingatkan" via `markReminded` (Tugas 7) bila `can(perms,"order","update")`; selain itu navigasi lama.
- `permintaan_internal`: aksi tambahan "Tolak" → `askReason` lalu `POST /internal-requests/{id}/reject` (izin `internal_request.reject`; body persis seperti layar asal — lihat `internalRequestsApi.js`); "Tindak" (konversi ke transfer/PO, bertahap) tetap pindah layar.
- `menunggu_manajer`, `harga_ditolak`: tombol "Lihat" membuka pop-up rincian saja (pratinjau Tugas 6 adalah tujuannya); mengubah harga = "Buka layar penuh".
- Tetap pindah layar (ikon + alasan): `retur`, `retur_tukar` (proses retur bertahap: penerimaan barang, penyelesaian), `od_*` (catat ACC/kunci harga/siapkan memakai formulir OD bertahap).

- [ ] **Step 1: Tulis uji gagal:** tetapkan sales di tempat (izin ada → dialog, kirim body benar, toast, muat ulang kartu; izin tidak ada → navigasi); pengingat; tolak PIN (batal di `askReason` = tidak ada panggilan); "Lihat" tidak memanggil navigasi; HP memakai aksi yang sama.
- [ ] **Step 2: → FAIL. Step 3: Implementasi. Step 4: → PASS.**
- [ ] **Step 5: Commit** `feat(meja-admin-sales): tetapkan sales (berizin), catat pengingat, tolak permintaan internal, lihat pesanan — di tempat`.

### Task 9: Huruf & warna panel yang dipakai ulang (A7)

**Files (Modify):** `features/sales_admin/VerifyOrderDialog.jsx`, `features/sales_admin/OrderPreviewCard.jsx`, `features/sales_admin/FulfillmentDecisionDialog.jsx`, `features/sales_admin/FulfillmentLineCard.jsx`, `features/finance/payments/PaymentVarianceDialog.jsx`, `features/samples/SamplePaymentApproveDialog.jsx` bila ada sisa, `scripts/guardrails/baselines/custom_modals.json` + `ui_standard` baseline (dikencangkan dengan `--update` hanya bila angkanya TURUN).

- Peta ukuran: `text-[9px]`–`text-[12px]` → `text-fs-12`; `12.5`–`13px` → `text-fs-13`; `13.5`–`14px` → `text-fs-14`; `15`–`17px` → `text-fs-16`; `18px`+ → `text-fs-20`. `uppercase` pada label kolom/kicker dihapus (peran: label 12/600 tanpa huruf besar).
- Warna hex → kelas `kn-*` yang sudah ada di `frontend/tailwind.config.js` (teks utama `text-kn-text`, sekunder `text-kn-text-2`, tautan `text-kn-action`, garis `border-kn-divider`, dst.) — susun peta dari konfigurasi; hex yang tak punya padanan token dibiarkan dan dicatat di laporan (jangan membuat token baru).
- Batas semi-tebal: maksimal dua unsur `font-semibold|font-bold` per baris tampilan.

- [ ] **Step 1: Uji** di `frontend/src/features/__tests__/mejaG2Huruf.test.js`: baca isi kelima berkas → nol `/text-\[\d/`; jumlah hex turun (angka per berkas dicatat dari baseline sebelum mengubah).
- [ ] **Step 2: → FAIL. Step 3: Konversi. Step 4: → PASS** + uji lama dialog-dialog itu (`grep -l` di `__tests__`) + `verify_ui_standard.py` + `verify_custom_modals.py` hijau.
- [ ] **Step 5: Commit** `style(meja): huruf & warna token di dialog periksa, pemenuhan, selisih bayar (A7)`.

### Task 10: Uji penuh, gate, tangkapan, laporan

**Files:** Create `docs/superpowers/plans/2026-11-25-meja-gelombang-2-hasil.md` + folder `2026-11-25-meja-gelombang-2-hasil/` (tangkapan); Modify `docs/blueprint/04_POLA_UI.md` (§1.6 atau bagian rincian: "nomor dokumen di daftar Keuangan = `DocLink` → pratinjau; Jejak tetap") dan `CODEBASE_MAP.md` (berkas baru di `features/documents/preview/`, `DeskDocPanel`, dialog baru).

- [ ] **Step 1:** Suite penuh di pohon akhir, di latar: `backend/tests_mem` dan jest penuh; bandingkan dengan gelombang 1 (gagal yang sama = kendala lingkungan `odItemCancel`, `phase4R2`).
- [ ] **Step 2:** Gate `--quick` + `--ci` sekali; nilai dengan `docs/reviews/2026-11-13/garis-dasar/bandingkan_gate.py` dan `scripts/blueprint/bandingkan_pelanggaran_gate.py docs/blueprint/garis-dasar-gate/2026-11-15_gate_ci.log <log>`; pelanggaran baru dari gelombang ini = penghalang. Bandingkan juga dengan gate pohon akhir gelombang 1.
- [ ] **Step 3:** Tangkapan sesudah (Playwright, data acuan): Meja Admin Sales & Meja Keuangan — pop-up per jenis antrean (SO, uang masuk, selisih, denda, hutang, retur, PIN, pelanggan tanpa sales), aksi di tempat; layar Keuangan §5.7a: klik nomor → pratinjau barang (Piutang rincian umur, Penagihan, Kwitansi + alokasi bertumpuk, Faktur Keluaran, Hutang per pemasok, Kontrabon gabungan, Transaksi Kas); HP Admin Sales.
- [ ] **Step 4:** Laporan hasil (pola `2026-11-25-meja-gelombang-1-hasil.md`): yang berubah untuk pengguna, tugas → commit, uji apa adanya, gate, keputusan pelaksanaan, aksi yang masih pindah layar + alasannya, pertanyaan untuk pemilik (izin tetapkan sales untuk Admin Sales).
- [ ] **Step 5: Commit** `docs(meja): hasil gelombang 2`.
