# UAT 24 Okt — Audit UI tahap 2 · Fase 4 (sisa fase 3 & audit tahap 2)

- Commit (branch `main`): `a9948ba` (R1 form HP) · `868dce4` (R2 keuangan & dokumen) · `2e46167` (R3 rantai pasok) ·
  `d814e0a` (R4 R&D/SDM/katalog/retur) · `ef6caf8` (R5 antrean, backorder, akses) · `2b49c82` (R6 sisa backend audit 2)
  · `f7fb56b` (R7 skrip data lama) · `d8015f9` (R8 label SO, SO mati, QC) · `3047e50` (integrasi koordinator) ·
  `b9777cc` & `9e43876` (R9 skrip sisa data uji). Baseline fase 4: `5110452` (akhir fase 3).
- Dasar: "Belum dikerjakan" di [UAT24-AUDIT-UI-2-FASE3.md](UAT24-AUDIT-UI-2-FASE3.md) &
  [UAT24-AUDIT-UI-2.md](UAT24-AUDIT-UI-2.md); keputusan pemilik yang tetap mengikat (form input HP tidak diringkas,
  istilah tidak diubah — K-13) + keputusan baru 26 Okt di bawah.
- Laporan per paket: [`audit-ui-2/fase4/`](audit-ui-2/fase4/) (`R1.md` … `R9.md`, `COORD.md`).

## Keputusan pemilik 26 Okt (fase 4)
1. Pintu keputusan tanpa antrean & antrean bayangan **masuk Pusat Persetujuan & KPI Beranda**; yang otomatis dibebaskan
   beralasan.
2. "Backorder" di layar Pesanan = **hanya status Menunggu stok**; SO lain bersisa = "Sebagian menunggu stok".
3. Panel kecepatan pesanan **boleh untuk sales, hanya data miliknya**.
4. Perbaikan data lama **di DB uji dulu, lalu DB UAT setelah dicadangkan**; data "test" UAT tidak dihapus.
5. Sisa data uji (eliminasi antar-PT basi, penanda SO mati, PR yatim) **dibersihkan di DB uji**.
6. **Crawl verifikasi fase 4 dilewati** (pemilik) — verifikasi lewat Jest, uji HTTP, POC & cek peramban tiap paket.

## Yang dikerjakan
| Paket | Hasil utama |
|---|---|
| R1 Form HP | Kwitansi, Amandemen, PR bahan MD, Ubah SKU, alamat kirim, tindak lanjut di HP memakai form desktop lengkap (FormModal layar penuh); PR HP menyebut nomor PO/Order Makloon; menu MD Labdip/Handfeel/Proofing → satu "R&D Produk Baru" |
| R2 Keuangan & dokumen | 23 pop-up → standar (jurnal, saldo kredit, faktur pajak, rekonsiliasi ×6, selisih bayar, denda, kendaraan, kontrabon, kasus, WhatsApp, dokumen); 6 konfirmasi baru untuk aksi uang/jurnal; kepala halaman & tab baku di Rekonsiliasi Bank, Kontrabon, Kasus Keuangan, Pusat Export, Amandemen; peringatan eliminasi basi di Konsolidasi |
| R3 Rantai pasok | 38 pola pop-up → standar (PR, Kedatangan, OCR, Inspeksi 4-Point, langkah makloon, Lot, QC, eskalasi, pengiriman, produksi); tata letak RFID/Analitik Stok/Eskalasi/Perbaikan; KPI baku; SPK Inspeksi < 500 baris |
| R4 R&D, SDM, katalog, retur | Form Desain, Master Kategori, katalog varian/SKU, pop-up retur → standar; KPI Desainer kolom prioritas + Rincian; Saring (n); aksen ungu → biru baku; form Induk produk bernomor; 85 grid HP tidak melebar |
| R5 Antrean & akses | 6 antrean baru (KPI 95 → 100 di data acuan), antrean HP hanya yang bisa diputus, Backorder = Menunggu stok, kecepatan pesanan untuk sales, tab Lot disembunyikan untuk peran tanpa izin lot, nama pengaju di Matriks divisi |
| R6 Sisa backend audit 2 | Nomor dokumen di Jejak Audit & Cek Peran, QR PDF dari URL publik, kode wilayah badan usaha, langkah journey dilewati/sebagian, notifikasi ke dokumen, saran Tanya KN, deteksi eliminasi basi |
| R7 Data lama | DB uji: 5 PR dari PO batal dilepas, 28 riwayat sample dinormalkan, 6 segmen saldo di-rebuild; UAT (dicadangkan dulu): 14 riwayat sample; PR & saldo UAT sudah bersih |
| R8 SO & QC | Label "Sebagian menunggu stok"; SO mati tak lagi di persetujuan SO (keputusan ditolak 409); batal/kedaluwarsa membersihkan persetujuan pending & penanda backorder; QC Hub "ditahan" satu definisi |
| Koordinator | Esc di pop-up bertingkat stabil (urutan lapisan), klik notifikasi membuka dokumen (desktop & HP), gaya journey, galat kwitansi tak ganda, KPI global tak lagi di Operasi Gudang, POC E-8 menyetel akun ujinya sendiri, ratchet, peta kode |

## Perubahan perilaku yang perlu diketahui saat UAT
- **Pusat Persetujuan & KPI Beranda** memuat antrean baru: klaim desain, override kredit (tanpa SO), nota kredit dari
  pembatalan Pesanan Khusus (Finance), susut bahan makloon, selisih PO, pengecualian retur.
- **Backorder** = hanya SO "Menunggu stok" (data acuan 23 → 14); SO lain bersisa berlabel "Sebagian menunggu stok".
- **Sales** melihat panel kecepatan pesanan (pesanan miliknya) dan **tidak lagi** melihat tab Lot & Silsilah.
- **Form HP** = form desktop: kwitansi meminta keputusan bila kelebihan bayar (dulu otomatis titipan); PR HP tanpa
  isian Catatan (desktop tidak punya), Alasan opsional, kotak "Langsung ajukan" tercentang bawaan.
- Alasan Tolak PR & pembalikan retur beli minimal 5 huruf (K-14). Pop-up retur bisa ditutup Esc/klik latar.
- SO yang sudah batal/kedaluwarsa tidak bisa lagi "disetujui" (dulu 200 & menulis "approved").
- Operasi Gudang tidak lagi menampilkan deretan KPI global (KPI ada di tab Stok).

## Bukti uji
- **Jest penuh** `--maxWorkers=1`: **71 suite / 506 uji lulus** (fase 3: 63/437). ESLint 0 error di berkas berubah.
- **Uji HTTP fase 4** (setelah restart backend): 16 berkas / **126 lulus** — termasuk bukti-merah R5 (5) & R8 (4) yang
  merah terhadap backend lama.
- **POC** (DB uji): akses peran **43/43** (sebelum 41/43), cakupan antrean **38/38** (37/38), master per PT **57/57**
  (55/56), aturan peran **65/65** (56/64), pengingat **26/26**. Merah yang tersisa identik/lebih baik dibanding
  baseline `5110452` di DB yang sama: meja peran 4 (baseline 8), entitas 6 (6), inspeksi (sama), permintaan desain 1 (1).
- **Guardrail**: semua guardrail UI hijau; `verify_approval_queues`, `verify_home_kpi`, `verify_codebase_map`,
  `verify_aging_fields`, `verify_error_notice` kini hijau. Ratchet: pop-up buatan sendiri **112 → 49 berkas**, tab
  buatan sendiri **16 → 6**. Merah lama identik dengan baseline `5110452`: `verify_atomic_claim` 6,
  `verify_auth_coverage` 8, `verify_line_scope` 15, `verify_numeric_bounds` 3, `verify_qty_dual` 5,
  `verify_ref_unlink` 3, `verify_to_list_bound` 6 (`verify_state_machine` tidak dijalankan — ia membatalkan SO data).
- **Peramban**: tiap paket memeriksa layarnya di 1440 & 390 px (`scrollWidth` = lebar layar, pop-up layar penuh di HP;
  pop-up hanya dibuka lalu dibatalkan). Beberapa pop-up hanya teruji Jest karena data acuan kosong (kontrabon, faktur
  pajak, denda, Issue/Terima makloon, karantina QC, eskalasi, chip backorder HP). Crawl penuh dilewati (keputusan 6).

## Data
- R7 (izin pemilik): skrip `scripts/fix_data_2026_10_26_{pr_po_batal,riwayat_sample,saldo_basi}.py` (dry-run bawaan,
  `--apply`, jejak `migrations`). Cadangan UAT sebelum apply: `kn_uat_23okt_pre_fase4.archive.gz` (folder kerja).
- R9 (izin pemilik, HANYA DB uji `kn_test_trial`; cadangan 10 koleksi sebelum apply):
  `scripts/fix_data_2026_10_26_{eliminasi_basi,so_mati,pr_yatim}.py`.
  * Eliminasi antar-PT basi (G1-33): **13 dari 15** dihapus (10 tanpa jurnal + 3 pair bersama 6 jurnal yatimnya);
    neraca konsolidasi & neraca saldo ketiga PT tetap seimbang; INV-IC-03 15 → 2; IC bersih 44.400 → 0.
    **KSC/IC-00039 & KSC/IC-00052 dilewati** (pair lunas: IC-00039 masih dirujuk pelunasan hidup KANDA/ICS-00002;
    IC-00052 punya jurnal pelunasan yatim) — keduanya konsisten dengan GL, angka grup tidak salah saji.
  * 9 SO mati dirapikan (3 persetujuan pending → batal, 1 override kredit batal, 6 penanda backorder).
  * PR-00106/151/174/179 dibatalkan (alasan "Residu uji").
  * **Lanjutan (pemilik: "setuju semua usulan")** — `scripts/fix_data_2026_10_26_ic_yatim.py` + perluasan `pr_yatim`:
    KSC/IC-00052 dibersihkan (2 jurnal transaksi + 2 jurnal pelunasan yatim + entri eliminasi); 8 jurnal retur
    antar-PT yatim (ICR-00010/14/15/23) dihapus → IC-AR/IC-AP bersih 0; cache `interco_accounts` KSC↔CST 22.200 → 0
    dihitung ulang; 6 PR yatim lain (PR-00032/048/055/070/072/087) dibatalkan. Neraca konsolidasi & neraca saldo
    tiap PT tetap seimbang; INV-IC-02 & INV-IC-04 PASS; INV-IC-03 tinggal 1 = **KSC/IC-00039 sengaja dibiarkan**
    (dirujuk pelunasan hidup KANDA/ICS-00002, konsisten dengan GL). Sisa di luar izin: INV-IC-06 (CST/TRF-00002 menaut
    pair yang sudah terhapus), backorder 76 item + KSC/SO-00162, PR-00005.

## Belum dikerjakan / catatan
- Pop-up buatan sendiri tersisa 49 berkas (ratchet), tab buatan sendiri 6 (2 di antaranya positif palsu heuristik:
  tombol status PostDetailModal, sorotan langkah SampleDetailPanel).
- Berkas > 500 baris sejak sebelum fase 4: `MakloonWizard` 542, `OutboundScanInterface` 603, `InventoryStockView` 559.
- Berkas tak terpakai: `hr/DesignShowcaseModal.jsx`, `hr/AiIllustrationPanel.jsx` (panel Ilustrasi AI tak terjangkau UI).
- `config/roles.js::accessBlocks` belum bisa memeriksa izin per aksi; label `siap_confirm`/`siap_pick` backend vs
  frontend berbeda bunyi (K-13, dibiarkan).
- Kebersihan uji (R6): beberapa uji menghapus `interco_transactions` langsung tanpa entri eliminasinya — sumber
  eliminasi basi; usulan invarian INV-IC-03b di `audit-ui-2/fase4/R6.md`.
