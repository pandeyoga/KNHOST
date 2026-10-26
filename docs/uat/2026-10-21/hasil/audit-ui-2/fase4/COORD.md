# Fase 4 — catatan koordinator

## Dari R7 (data lama) — selesai
* Skrip: `scripts/fix_data_2026_10_26_pr_po_batal.py`, `..._riwayat_sample.py`, `..._saldo_basi.py` (dry-run bawaan,
  `--apply`, jejak di koleksi `migrations`). DB uji: 5 PR dilepas, 28 riwayat dinormalkan, 6 segmen saldo di-rebuild.
  UAT: 14 riwayat dinormalkan (cadangan `db_backup/kn_uat_23okt_pre_fase4.archive.gz`), PR & saldo sudah bersih.
* Penugasan akun POC: koordinator MENGUBAH pendekatan — POC e8 kini menyetel penugasan sendiri & memulihkan
  (data acuan sah E8.10b#1: salesadmin@ KSC, finance@ 3 PT); akun DB uji dikembalikan (`--revert`), skrip akun dihapus.
  Asersi izin Finance pesanan disesuaikan dengan matriks sah (approve_price_edit 2026-10, release_unpaid F-10).
  POC e8: 65/65 (sebelumnya 56/64).
* Sisa dicatat (tidak diubah): 4 PR dari Pesanan Khusus terhapus (PR-00106/151/174/179, DB uji) kini "Disetujui" &
  bisa direalisasi lagi — membatalkan = keputusan; DB uji `has_mixed_lot` FAIL untuk KSC/SO-00045.
* G5-60 bukan data: PR-00005 direalisasi ke Order Makloon → teks HP diteruskan ke R1.

## Dari R4 — selesai
* custom_modals R4 8 → 0 (`--update` di akhir); page_tabs R4 tetap 2 = positif palsu heuristik (PostDetailModal tombol
  status, SampleDetailPanel sorotan langkah) — pertimbangkan pengecualian beralasan di guardrail.
* verify_error_notice merah 1: baseline basi `purchasing/LandedCostDetailPanel.jsx` & `VendorBillDetailPanel.jsx`
  (koordinator hapus dari MODAL_BASELINE setelah R2/R3 selesai).
* Berkas yatim (tak diimpor): `hr/DesignShowcaseModal.jsx`, `hr/AiIllustrationPanel.jsx` — panel Ilustrasi AI tak
  terjangkau UI. Dibiarkan (keputusan hapus nanti).
* R4 menyentuh `designer/DivisionsView.jsx` 1 baris (grid-cols-1). Aksen ungu → biru 26 berkas (warna semantik tetap).
* Perilaku: pop-up retur kini bisa ditutup Esc/klik latar (FormModal).

## Dari R5 — selesai (backend belum di-restart)
* Setelah restart: `tests/test_phase4_r5_http.py` (kini merah 5/5 = bukti merah), `test_core_role_access_poc.py`,
  `test_core_f6_approval_coverage_poc.py`, `verify_home_kpi`, `test_core_inspeksi_poc.py`, `test_core_design_request_poc.py`;
  peramban sales (tab Lot hilang, panel kecepatan "Pesanan milik Anda") & Admin Sales (tanpa /config/health).
* Berkas bersama (koordinator): `utils/soStatus.js` + `services/so_status.py` label "Menunggu stok (backorder)" untuk
  SO tahap lain → "Sebagian menunggu stok"; `config/roles.js::accessBlocks` belum bisa izin per aksi.
* Diteruskan ke R1: `sales/mobile/MobileOrders.jsx:150` pakai isBackorderSo/hasPartialBackorder.
* Sisa backend (koordinator/berikut): `inspection_service` hitungan hold QC Hub masih menghitung baris ditolak;
  `so_approvals.py` sembunyikan/tolak entri SO mati; alur kedaluwarsa/batal bersihkan `pending_approvals` &
  `has_backorder` basi.
* `verify_aging_fields` merah 2 (kontrabon `match_summary.status`) — sudah ada di HEAD, cek.
* Backlog total data acuan 95 → 100 (−3 SO mati, +8 nota kredit OD).

## Dari R6 — selesai (backend belum di-restart)
* Setelah restart: uji HTTP di R6.md (audit-logs, role-reality, PDF Origin lain, PATCH lokasi BU uji, journey,
  ringkasan konsolidasi, notifikasi finance); POC E4 SENDIRIAN.
* Koordinator: `App.js` onNavigate notifikasi → `if (openNotifDocument(n, openDocument)) return;` (contoh di R6.md);
  generate ulang peta kode (`verify_codebase_map`, 4 servis baru); rapikan MODAL_BASELINE verify_error_notice.
* Guardrail backend merah (di luar R6): verify_codebase_map, verify_to_list_bound, verify_auth_coverage,
  verify_ref_unlink — bandingkan dengan HEAD.
* Sisa (R5 selesai → koordinator): NotifPanel `MobileOpsApp` pakai `n.doc`; gaya `skipped`/`partial` di
  `OrderJourneyPanel`; hapus `HINT_OVERRIDE` di `EntityMastersView`. R1 opsional: `MobileOrderJourney` pakai state server.
* Diteruskan ke R2: peringatan `eliminations_stale` di layar Konsolidasi.
* KEPUTUSAN: G1-33 — 15 eliminasi otomatis basi (Rp 7.112.214 IC-AR): 10 tanpa dokumen & jurnal, 5 jurnal masih ada
  (akar: pembersihan data uji menghapus dok antar-PT langsung di DB). Usulan pembersihan + invarian di R6.md.

## SUDAH dikerjakan koordinator (26 Okt, saat R1/R2/R3/R8 berjalan)
* `App.js` onNavigate notifikasi → `openNotifDocument` (G5-09); `features/mobile/MobileOpsApp.jsx` lonceng HP →
  dokumen (link) lewat `onOpenDocument`; `features/orders/OrderJourneyPanel.jsx` gaya `skipped`/`partial`.
  ESLint 0; Jest f08CommercialInvoice + phase4R6 + mobileShell 23/23.
* Tertunda sampai restart: hapus `HINT_OVERRIDE` di `EntityMastersView`.

## Dari R2 — selesai
* custom_modals R2 21 → 0, page_tabs 7 → 0 (`--update` di akhir). R2 juga menyentuh `features/export/**` (Pusat
  Export, ditugaskan) — masuk commit R2.
* 6 konfirmasi baru (askConfirm) untuk aksi uang/jurnal; rincian Kasus Keuangan (< 1280 px) & Amandemen (< 1024 px)
  kini DetailModal; peringatan `cons-stale-elims` di Konsolidasi (cek setelah restart: 15 entri, Rp 7.112.214).
* MODAL_BASELINE verify_error_notice: hapus LandedCostDetailPanel & VendorBillDetailPanel (koordinator, setelah R3).

## Dari R1 — selesai
* custom_modals turun 6 (`--update`); MODAL_BASELINE (sama).
* Koordinator: `memory/test_credentials.md` testid amandemen HP lama (`m-amd-item-<pid>-plus`, `m-amd-submit`,
  `m-amd-result`) → perbarui; `onError` ARReceiptModal di `CollectionWorklist`, `FinanceDesk`,
  `DispatchPaymentGatePanel` (galat ganda di belakang pop-up) → cabut setelah R3 selesai; risiko `useEscapeClose`
  dengan `onClose` inline (urutan lapisan) — perbaikan umum di hooks bersama.
* Perubahan perilaku HP (mengikuti desktop, sesuai keputusan "HP pakai form desktop"): PR — isian Catatan hilang
  (desktop tak punya), Alasan opsional, kotak "Langsung ajukan" (centang bawaan); kwitansi — kelebihan bayar kini
  diminta keputusan selisih (dulu otomatis titipan); MD "Ubah SKU" = VariantEditor (bug lama harga efektif PT
  tersimpan sebagai harga dasar tertutup); menu MD satu baris "R&D Produk Baru".
* G5-60: PR HP tampil nomor PO/Order Makloon dari data realisasi (PR-00005 → MKO-00005).
* Koordinator: `utils/escapeLayers.js` `useEscapeClose` membaca onClose/busy lewat ref (urutan lapisan stabil walau
  onClose inline) + uji `utils/__tests__/escapeLayers.test.js` (lulus; bukti merah dengan kode lama). 
  `memory/test_credentials.md` testid amandemen HP diperbarui.

## Dari R3 — selesai
* custom_modals R3 38 → 1 (kios Monitor Gerbang, bukan pop-up); page_tabs 18 → 0; InspectionDetailPanel 658 → 463.
* Koordinator SUDAH: MODAL_BASELINE (LandedCost/VendorBill) dihapus → verify_error_notice PASS; `onError` ganda
  ARReceiptModal dicabut di CollectionWorklist/FinanceDesk/DispatchPaymentGatePanel; HOME_VIEWS tanpa "operations"
  (KPI global tak lagi di Operasi Gudang).
* Perilaku: alasan Tolak PR & pembalikan retur beli min 5 huruf (K-14); galat Konversi/Tolak PR, Tahan/WIP, GR,
  realisasi PR, Landed Cost, Tagihan Supplier kini di dalam pop-up.
* Masih > 500 baris sejak sebelum fase 4: MakloonWizard 542, OutboundScanInterface 603, InventoryStockView 559.

## INTEGRASI (status saat batas pemakaian, 26 Okt malam)
* SUDAH: backend uji & UAT di-restart; uji HTTP fase 4 16 berkas/126 lulus; POC role_access 43/43, f6 38/38, e4 57/57,
  e8 65/65, reminder 26/26; verify_home_kpi PASS; ratchet --update (custom_modals 112→49 berkas, page_tabs 16→6);
  CODEBASE_MAP.md digenerate ulang (LF, verify_codebase_map PASS); HINT_OVERRIDE dicabut; LotRecallPanel label sub-status.
* POC merah = identik/lebih baik dari baseline 5110452 (kn-base-backend :8065): e8_desk 4 (baseline 8), e1e2 6 (6),
  inspeksi exit 1 (sama), design_request 1 (1).
* Guardrail merah (perlu dibandingkan dgn baseline 5110452): verify_atomic_claim 6, verify_auth_coverage 8,
  verify_line_scope 15, verify_numeric_bounds 3, verify_qty_dual 5, verify_ref_unlink 3, verify_state_machine (SKIP 1),
  verify_to_list_bound 6.
* BELUM: bandingkan guardrail di atas dgn baseline; Jest penuh; crawl ulang desktop+HP; commit per paket (R1..R8 +
  koordinator, ~290 berkas belum di-commit); laporan fase 4 + tracker; push. Keputusan pemilik tertunda: G1-33
  pembersihan 15 eliminasi basi (DB uji), patch SO mati/has_backorder basi (R8 butir 2), 4 PR OD terhapus.
* Kontainer kn-base-backend (:8065, baseline 5110452) masih hidup — hentikan bila tidak dipakai.
