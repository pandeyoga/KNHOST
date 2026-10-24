# UAT 24 Okt — F0, F1, F2 (bug pasti · lokasi · alur barang)

- Commit: `663745a` (implementasi F0–F2) · `5f52372` (perbaikan regresi) · branch `main` (sudah di-push).
- Sumber: [`ANALISIS_TEMUAN_UAT_23OKT.md`](../ANALISIS_TEMUAN_UAT_23OKT.md) §3 fase F0–F2; keputusan pemilik = usulan
  bawaan §4 (dikonfirmasi 24 Okt), P14-K1: 3 pelanggan KSC tanpa sales → **Bima (sales2)**.
- Lingkungan: stack uji `kn-uji-backend` (DB `kn_test_trial`), simulasi `kn-sim-*` (DB `kn_uat_sim`, klon UAT),
  regresi pada dua container + worktree dengan DB klon identik. **DB UAT `kn_uat_23okt` sudah dimigrasi** (skrip data
  di bawah) dan `kn-verify-backend`/`kn-verify-frontend` sudah di-restart.

## F0 — bug pasti
| Butir | Sebelum → sesudah |
|---|---|
| P11.5 | Simpan 4-point menimpa objek `inspection` → jejak MD Quality hilang. Kini ditulis per field; jejak MD tetap. |
| P16.2 | GRN baru tidak bisa dicetak (resolver PDF lama membaca PO). Kini `goods_receipt` (GRN) + `po_receipt` (Bukti Terima per PO) terpisah. |
| P14 | Sales melihat semua pelanggan lewat `for_order`, dasbor, retur. Kini hanya pelanggan miliknya (`assigned_sales_id`/tim) + **Pelanggan Umum (Walk-in)** per PT; retur hanya atas SO miliknya; antrean Meja Admin Sales **"Pelanggan tanpa sales"**. |
| P9 | Gudang nonaktif bisa dipilih/dipakai PO; gudang bawaan reorder = gudang pertama. Kini gudang nonaktif ditolak (400 "NONAKTIF"); reorder memakai gudang penerimaan lokasi PT. |
| P4.8 | Kain dasar di form sampel tersimpan sebagai objek (layar galat). Diperbaiki. |
| P16.1b | Rekonsiliasi GRN menulis "Tidak ada selisih — cocok" sebelum hitung selesai. Kini "dihitung sesudah Selesai hitung" + kekurangan sementara. |
| Lain | Label seksi Pengaturan dobel; `_realize_po` OD membaca `type`/`kind`. |

## F1 — lokasi (site) sebagai tujuan & konteks jualan
* PO / PR / realisasi PR / harga OD memilih **Lokasi kirim**; gudang penerimaan diturunkan server (peran
  `central_inbound`/`transit`). Klien lama yang mengirim gudang simpan dialihkan ke gudang penerimaan lokasinya.
* GRN dari PO selalu di gudang penerimaan PO (dulu pilihan layar disimpan tetapi diabaikan saat posting).
* Tahap awal roll mengikuti peran gudang (transit → `received_transit`, gudang simpan → `stored`).
* POS & HP: gerbang **Mulai jualan** (lokasi + pelanggan wajib, walk-in tersedia, pelanggan baru), stok **per lokasi**
  di kartu produk + saring "hanya yang ada di lokasi ini"; SO menyimpan `fulfillment_site_id`.
* Putaway Order & daftar GRN ikut cakupan lokasi.

## F2 — alur barang
* **P9.3b** label QR setara RFID: pindai nomor roll di transit → `label_verified` → Putaway Order → konfirmasi tiba
  dengan nomor roll. GRN selalu menyiapkan data tag; label QR tetap jalan resmi.
* **P9.4/P9.4b** putaway hanya ke gudang simpan **di lokasi yang sama**; roll yang langsung tercadang ke SO saat tiba
  ditandai **cross-dock**.
* **P9.6** alokasi: gudang lokasi pesanan dulu, lalu kota; FIFO **tanggal masuk** (bawaan `lot_selection=fifo`).
* **P10** antar-PT: roll pilihan Admin Sales ikut sampai tugas gudang & dikirim **utuh** (qty transaksi = total roll);
  hanya stok di gudang yang boleh dipakai PT pembeli — roll di gudang khusus penjual ditandai "pindahkan dulu" dan
  ditolak dengan pesan jelas; barang pindahan dicadangkan ke **SO peminta** dulu.
* **P11** penanda datar `md_quality_checked` / `md_quality_via_sampling` / `inspected_4point` (+ backfill); sampling
  MD (`qc.md_sampling_pct/min`) & 4-point (`qc.sampling_pct/min`); SPK 4-point untuk **sebagian** roll; MD Quality
  boleh menutup SPK MD-nya (P11-K1); chip MDQ/4-pt & filter stok.

## Bukti
* Uji: `test_uat24_f0/f1/f2` **27 lulus** (termasuk gabungan dengan F3: 64 lulus, 1 dilewati); Jest
  `uat24F0/F1/F2` lulus; Jest penuh **34 suite / 146 uji lulus**; ESLint 0 error.
* **Regresi penuh** 113 berkas uji, DB klon identik, baseline `945fa56` vs `663745a`: **4 gagal baru, 1 pulih**.
  Ketiganya uji lama yang menyandi aturan lama (putaway lintas lokasi ×2, sales melihat pelanggan tanpa sales) →
  disesuaikan aturan baru; satu bug nyata (gudang bawaan OD untuk PT tanpa lokasi bawaan) → diperbaiki. Sesudahnya
  berkas-berkas itu lulus (48 lulus, 2 dilewati). Kegagalan lain (179 gagal / 170 error) **sudah ada di baseline**.
* Alur nyata DB simulasi: PO ke Rancamalang → GRN di RCM-TRANSIT → SPK MD 2/5 dicek, **ditutup MD Quality** →
  2 roll "MDQ ✓", 3 "MDQ sampling", semua lepas karantina → SPK 4-point 2 dari 5 roll → label QR 2 roll → Putaway
  Order PA00002. Rencana pemenuhan antar-PT (KSC/SO-00013): 200 roll Kanda di gudang khusus Soreang ditandai
  "pindahkan dulu", stok Cipta Sandang di gudang bersama bisa diambil.
* UAT (sesudah migrasi): sales2 → gerbang lokasi Jakarta + pelanggan; kartu "Di Jakarta: 550 yard · 5 roll".

## Data (sudah dijalankan di `kn_uat_23okt` & `kn_uat_sim`, idempoten)
* `uat24_f0_data.py` — 3 pelanggan KSC → Bima (SO terbuka ikut), walk-in per PT.
* `uat24_f1_data.py` — SRG-01 & WH-JKT merangkap transit + penerimaan; lokasi bawaan PT (KSC Jakarta, KANDA Soreang,
  CST Rancamalang); lokasi akun sales/Admin Sales.
* `uat24_f2_data.py` — backfill penanda MDQ (4 roll) & `four_point_pending` (4 roll), indeks.

## Catatan / sisa
* Jakarta & Soreang hanya punya satu gudang → tidak ada putaway di sana (barang langsung tersimpan); itu sesuai model.
* Sampling bawaan: MD 0% (cukup 1 roll), 4-point 100% — ubah di Pengaturan › Kualitas bila perlu.
