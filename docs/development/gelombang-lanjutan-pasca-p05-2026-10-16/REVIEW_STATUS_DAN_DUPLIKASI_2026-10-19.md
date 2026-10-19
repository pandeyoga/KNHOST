# Review status plan & cek duplikasi — 2026-10-19 (agent E1)

Basis: repo `pandeyoga/KNHOST` main `a323e48`, BACKLOG.json (SSOT), evidence/L00–L14.

## A. Diselesaikan sesi ini
| Item | Perubahan | Bukti |
|---|---|---|
| Statistik "belum dibaca" penjadwal | `scheduler_service.summary`: hitung `read≠true` DAN `read_by` kosong (= belum dibaca siapa pun, sama dengan definisi eskalasi). Label kartu "belum dibaca siapa pun". | testing agent: API = hitungan Mongo, UI cocok |
| Sorotan tab alias | Entri `hidden` di hubTabs punya `aliasOf`; `hubForView` mengembalikan `activeTab`. `?view=permission-matrix` → "Badan Usaha & Akses" tersorot; juga `inspections` → QC & Inspeksi, `interco-transfers` → Stok, Transfer & Opname. | testing agent lulus |
| POS 3 jenis sample (desktop+HP) | Dites. Bug: modal Catalogue dari POS kehilangan pelanggan & artikel terisi (Radix memanggil `onValueChange('')` saat opsi belum dimuat). Diperbaiki + respons preview basi diabaikan + toast nomor SOS setelah dibuat. | iteration_sched_sample_returns_1 + retest |
| Menu Retur terpadu | Dites: 4 tab, deep-link lama, akses per peran (sales hanya Retur Pelanggan; finance + Retur Antar-PT). | lulus |
| Retur draf | `POST /sales-returns/{id}/reject` pada draf dulu 500 → kini 400. Baru: `POST /sales-returns/{id}/cancel-draft` + tombol "Buang Draf" (`cancel-draft-return-btn`), hanya status draf, tanpa efek stok/jurnal. | retest |

## B. Kenapa plan belum selesai
Semua 56 requirement masih `in_progress`/`not_started` (0/56 tervalidasi, 0/230 acceptance PASS). Tiga penyebab:

1. **Aturan paket, bukan kode kurang** — DEFINITION_OF_DONE melarang self-claim. `implemented_pending_validation` butuh SHA commit; `validated`/`pass` butuh reviewer terpisah + referensi persetujuan owner. Belum ada reviewer/owner_approval di BACKLOG. Contoh: L06 (8/8 + 1/1 tes), L07 (5/5), L10, L11, L14 LN-140 (46/46) sudah diimplementasi, tapi status tetap `in_progress`.
2. **Keputusan pending (23 dari 24)** — bagian yang memengaruhi nominal/grade/deadline sengaja tidak diisi asumsi:

| Keputusan | Memblok | Yang belum dibuat karenanya |
|---|---|---|
| KLR-01, KLR-02, KLR-06, KLR-07 | LN-092 | Cutloss & discount (hanya parameter "asumsi" di Kebijakan Retur, tanpa posting) |
| KLR-03, KLR-04, KLR-05 | LN-090 T02/T03 | Order pengganti nyata, qty pengganti, selisih harga |
| KLR-08 | LN-083 | Perlakuan hangtag hilang/kain dipotong (sekarang lewat pengecualian manual, settle 409) |
| KLR-09 | LN-083, LN-093 T03 | End-event batas 21 hari |
| KLR-10, KLR-11 | LN-091 | Potong tagihan SO lain, penanggung ongkir retur |
| KLX-01 | LN-014, LN-040 | Aturan LOT pabrik vs LOT KN |
| KLX-02 | LN-052 | Kamus cacat & rumus resmi (hasil inspect masih "kandidat") |
| KLX-03 | LN-024 | Cutoff & tanggal bayar interco (pengingat tidak jalan sebelum dikonfigurasi) |
| DATA-01 | LN-011 | Migrasi master bahan/supplier/warna |
| DES-02 / DES-03 / DES-04 | LN-071 / LN-112 / LN-013 T02 | Persetujuan contoh dokumen leg, format rapor, konteks entitas MD |
| OPS-01 | LN-101 | Batas nilai kerugian opname (sebagian sudah dijawab owner 2026-10-18 tetapi status BACKLOG masih pending) |
| HW-01, HW-02, HR-01 | L12 (LN-121/122), L13 (LN-130/131) | Butuh perangkat Chainway/absensi nyata & aturan HR — belum dikerjakan sama sekali |
| UAT-01 | LN-141/142/143 (L14) | Lingkungan pilot & persetujuan akhir |

3. **Sisa kerja independen yang masih bisa dikerjakan tanpa keputusan baru**
   - LN-012-T04 (PFD/PFP vs greige) belum diverifikasi; LN-015-T05/T08 belum diuji khusus.
   - L03: endpoint batal khusus OD belum dibuat; konversi kg↔yard pada prefill makloon.
   - L10: LN-102-T02 (kartu Meja User → dokumen) belum diverifikasi.
   - L11: ±70 koleksi belum dipetakan ke Pusat Export.
   - L09 LN-093-T01/T04: alur interco return belum diuji ulang terhadap acceptance.
   - Tracker: status fase di TRACKER (mis. L06/L07 `not_started`) tidak sinkron dengan requirement (`in_progress`); laporan L08 masih menulis LN-081 "belum dikerjakan" padahal sudah diuji (iteration_208).

## C. Temuan duplikasi (selain Matriks Izin vs Peran & Hak Akses yang sudah dihapus)
Belum ada yang digabung — menunggu persetujuan.

| # | Duplikasi | Lokasi | Risiko | Rekomendasi |
|---|---|---|---|---|
| D1 | **Jendela retur di 4 tempat**: kebijakan per scope `sales_return_policies.window_days` (bawaan kode 30 hari), "Asumsi sementara" `settings.returns.customer_window_days/supplier_window_days` (21), kebijakan retur per supplier di master Supplier, dan opsi lama `link_to_supplier_window` yang bertentangan dengan LN-083 (customer independen dari supplier) | `return_policy_service.py`, `ReturnAssumptionsPanel.jsx`, `SuppliersView` ReturnPolicyEditor, `entity_master_service` | Admin mengubah satu tempat, angka lain yang berlaku | Satu sumber bawaan (settings.returns), kebijakan per scope hanya override; pensiunkan `link_to_supplier_window` |
| D2 | **Batas poin grade di 2 tempat**: `max_points` di Master Grade dan `settings.qc.grade_thresholds` (a_max/a1_max/a2_max/b_max) sebagai cadangan | `qc_inspection_service.grade_from_points` | Hasil grade berbeda tergantung field mana terisi | Master Grade jadi satu-satunya; migrasi nilai settings lalu sembunyikan |
| D3 | **Daftar grade di-hardcode** di FE padahal grade dinamis (LN-012) | `purchasing/ReturnDetailPanel.jsx` (`["A","B","C"]`), `sales/ReturnAssumptionsPanel.jsx`, `catalog/AxisEditor.jsx`, prediksi di RollInspectionModal | Grade baru/nonaktif tidak tercermin | Ambil dari `/api` Master Grade |
| D4 | **Default sumber restock di 2 tempat**: Sumber Restock per artikel (LN-013, supplier/makloon) vs `product.supplier` (teks) yang dipakai Saran Reorder | `purchase_requisition_service._supplier_lead` | Saran Reorder bisa menyarankan supplier berbeda dari default MD | Saran Reorder membaca `restock_source_service` |
| D5 | **Perjalanan barang retur ganda**: panel lama "Perjalanan Barang" (tombol tandai manual) berdampingan dengan timeline scan LN-081 | Detail retur pelanggan | Dua cara mencatat posisi fisik, bisa tidak konsisten | Jadikan panel lama read-only atau hapus |
| D6 | **Meja Sample vs Meja Cutting**: antrean "Sedang dipotong / disiapkan gudang" di Meja Sample tumpang tindih dengan antrean Meja Cutting (L06) | `sample_orders.py` desk, `cutting_service.desk` | Dua tempat memantau tahap yang sama | Antrean di Meja Sample menautkan ke Meja Cutting, bukan daftar sendiri |
| D7 | **Dua kotak persetujuan**: "Inbox Persetujuan" dan "Persetujuan Saya" (keduanya admin/manager), plus dua konfigurasi aturan: "Aturan Persetujuan" (`approval_rules`, ambang nominal) dan Matriks Persetujuan R&D (`approval_matrix_service`) | hub approval-inbox, Pengaturan | Pengguna bingung harus membuka yang mana (asal sebelum plan L, bukan dari plan ini) | Satu inbox dengan filter jenis; pertahankan dua konfigurasi tapi beri label jelas |
| D8 | Dokumentasi basi (bukan duplikasi kode): docstring `routers/sample_sales.py` menyebut sample "bukan dokumen terpisah", padahal sekarang Pesanan Sample `order_type=sample` | — | Menyesatkan developer | Perbarui docstring |

Dicek dan **bukan** duplikasi: penyimpanan custom role (satu `custom_roles` + `permission_settings.matrix`), visibilitas field Sales (satu `field_visibility`), alur sample POS (satu jalur SO `order_type=sample`), picking trip (memakai tugas outbound yang sama), transit Jakarta (memakai transfer P03).
