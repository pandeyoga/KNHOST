# Brief implementasi keputusan pemilik (26 Okt) — audit UI tahap 2

Repo: `C:\Users\abc\Documents\Codex\KNHOST`. Bahasa: Indonesia. Aturan kerja SAMA dengan `fix_brief.md` (folder ini):
baca AGENTS.md/CLAUDE.md; jangan menyentuh git; jangan restart kontainer; LF; Jest `--maxWorkers=1` & hanya uji
relevan; ESLint 0 error; pyflakes; uji backend yang butuh HTTP → tulis & catat untuk koordinator; jangan ubah istilah
UI (keputusan K-13: bahasa dibiarkan apa adanya); hanya edit berkas di wilayah Anda (lihat pembagian di bawah); bila
perlu berkas di luar wilayah → catat di laporan "Butuh agen lain". Latar setiap keputusan: `fixplan.md` §5.3
(K-xx) dan laporan grup `fixes/*.md` (butir terkait, berkas:baris). PENTING: setiap angka yang definisinya berubah
harus tetap diberi label sumber/cakupan di layar; perubahan perilaku dicatat di laporan.

## Keputusan (semua = rekomendasi koordinator, kecuali K-05 & K-13)
* **K-01 Piutang.** Layar operasional (Piutang/AR Aging, Dasbor Keuangan, Control Tower, Beranda) memakai sub-buku
  (dokumen belum lunas) sebagai angka utama; Laporan Keuangan/Neraca memakai GL 1-1200. Control Tower & papan
  piutang Beranda menghitung **semua pelanggan** (bukan hanya pelanggan ber-sales aktif). "Lewat tempo" = sama dengan
  layar Piutang. Label sumber di tiap kartu.
* **K-02 Kas.** Angka utama "Kas & Bank" = saldo GL akun kas+bank; Rekening & Saldo = rincian per rekening (label
  selisih bila ada transaksi belum tertaut).
* **K-03 Nilai dokumen & PPN.** "Total" pada dokumen penjualan/pembelian = termasuk PPN; DPP tampil sebagai rincian
  (kolom/ baris "DPP"). Untuk PPN 12% atas DPP nilai lain (11/12): tampilkan baris "DPP nilai lain (11/12)" di layar
  dokumen & PDF faktur/SO/PO. Konsistenkan Pusat Dokumen, Persetujuan Pembelian, Meja Saya (kolom diberi label).
* **K-04 Stok "Tersedia".** Definisi tunggal berbasis roll: roll available yang tidak diblokir/karantina/di-hold
  (= papan stok). Saran Reorder & layar lain yang memakai `inventory_balances.available_qty` diselaraskan atau
  menghitung dari sumber yang sama; "Stok rendah" memakai definisi yang sama.
* **K-05 Cepat laku / Slow moving (KHUSUS pemilik):** klasifikasi **hanya dari moving average penjualan**.
  Rancangan (dasar: analisis ABC/Pareto & FSN — Fast/Slow/Non-moving — yang baku dalam manajemen persediaan, dan
  moving average sebagai ukuran laju permintaan):
  - Ukuran: rata-rata bergerak qty terjual per hari (satuan dasar) dalam jendela **90 hari** (setelan), dihitung dari
    SO hidup (tanpa batal/draf/sample bila sample dipisah); tampil juga MA 30 hari untuk arah tren (naik/turun).
  - Peringkat **persentil di dalam satuan yang sama** (yard, meter, kg dipisah — tidak dibandingkan lintas satuan).
  - Kelas: **Best seller** = 20% teratas (setelan); **Normal** = tengah; **Slow moving** = 20% terbawah di antara SKU
    yang terjual; **Tidak bergerak (dead stock)** = punya stok tetapi tidak terjual dalam jendela; **Baru** = SKU
    berumur < jendela (dikecualikan dari peringkat supaya tidak dinilai tidak adil).
  - Coverage (hari persediaan = stok ÷ MA harian) ditampilkan terpisah, tidak menentukan kelas; nilai ekstrem dibatasi
    tampilannya (mis. "> 365 hr").
  - Setelan baru di Pusat Pengaturan (kelompok stok/analitik): jendela hari, % best seller, % slow moving, umur SKU
    baru. Layar Analitik Stok menjelaskan dasar kelas (tooltip/keterangan singkat) & menampilkan MA, persentil, kelas.
* **K-06 + B2 Menunggu.** KPI "Menunggu"/"Belum diproses" di Pesanan = SO menunggu persetujuan (`waiting_approval`)
  saja, label "Menunggu persetujuan"; corong pesanan memakai populasi yang sama dengan daftar (sebut bila sample/
  badan usaha lain dikecualikan).
* **K-07 Utang antar-PT.** Saldo netting dua arah = angka utama; jadwal bayar per dokumen = rincian (label).
* **K-08 Bobot desainer.** Normalisasi ke 100% (nilai versi desain jadi bagian dari 100%, bukan bonus); layar & setelan
  menampilkan total 100%.
* **K-09 Penomoran.** Payroll run BARU memakai awalan `PAY-` (dokumen lama tidak diubah); nomor MKO/CASH baru ikut
  prefiks badan usaha bila mekanisme penomoran mendukung.
* **K-10** Transaksi antar-PT baru: centang "Langsung dikonfirmasi (post jurnal)" **mati** bawaan.
* **K-11 Wewenang.** Admin Sample tidak bisa memutus pesanan khusus (SORD) di HP (tab/aksi disembunyikan + server
  menolak bila belum); Sales hanya melihat papan PO Custom untuk pelanggannya sendiri (pelanggan ber-sales dia /
  dokumen buatannya); MD hanya membaca kelompok pengaturan R&D (bukan seluruh Pusat Pengaturan) — server & layar.
* **K-12 Tab Ringkas HP.** Desainer: DSR berjalan, tenggat dekat/terlambat, revisi menunggu. Admin Sample: antrean
  sample (SOS) per tahap, menunggu persetujuan bayar. Peran lain tetap.
* **K-13** Glosarium: **TIDAK diubah** (istilah campur seperti R&D, POS dibiarkan).
* **K-14** Panjang alasan minimum seragam **5 huruf** (layar & server) untuk dialog alasan; kecuali aturan yang jelas
  butuh lebih panjang secara bisnis (sebut di laporan bila ada yang dipertahankan).
* **K-15 Tutup buku saat Suspense ≠ 0:** diblokir; admin bisa menembus dengan alasan (askReason, tercatat audit).
* **K-16 Labdip tanpa handfeel ACC:** boleh, dengan peringatan + alasan wajib (tercatat), bukan form buntu.
* **B1 SPK QC** ditutup "Diterima seluruhnya" saat masih ada roll ditahan: **peringatan saja** (dialog), dengan setelan
  di Pusat Pengaturan untuk mengubahnya menjadi blokir nanti (bawaan: peringatan).
* **B3** Timeline retur menampilkan **grade per roll** (bukan hanya grade baris).
* **B4** "Buat kasus" keuangan: **nominal opsional** (boleh 0/kosong) — validasi layar dilonggarkan, cerita tetap ≥ 5 huruf.
* (B5 akun wajib sandi awal — sudah berlaku, tidak perlu kerja.)

## Pembagian wilayah (berkas tidak beririsan)
* **D1 Keuangan:** K-01, K-02, K-03 (termasuk `backend/services/pdf_resolvers.py`/`pdf_engine.py` & layar dokumen
  keuangan/penjualan yang menampilkan total), K-07, K-10, K-15, B4. Wilayah: `features/finance/**`, `features/home/**`,
  `features/documents/**`, backend keuangan/GL/AR/PDF, `home_service.py`.
* **D2 Stok & penjualan:** K-04, K-05, K-06+B2, B1, B3. Wilayah: `features/inventory/**`, `features/wms/**`,
  `features/inspections/**`, `features/orders/**`, `features/returns/**`/`features/sales/Return*`, `features/purchasing/Reorder*`,
  backend stok/ATP/analitik/inspeksi/retur/pesanan, `purchase_requisition_service` (saran reorder). Setelan baru K-05
  & B1 lewat registri konfigurasi backend (config_catalog*) — D2 pemilik penambahan kunci setelan.
* **D3 Peran, SDM, R&D, HP:** K-08, K-09, K-11, K-12, K-14, K-16. Wilayah: `features/rnd/**`, `features/design/**`,
  `features/hr/**`, `features/settings/**` (akses pengaturan MD), `features/mobile/MobileOpsApp.jsx`,
  `MobileApprovalInbox.jsx`, `features/sales/mobile/**` (papan PO Custom sales), `services/confirmService.js`
  (K-14 bawaan), backend peran/izin/HR/payroll/R&D/numbering, `approval_backlog_service`.
  K-14 di berkas wilayah D1/D2 → catat di laporan (koordinator menyelaraskan).

## Laporan
`decisions/<D1|D2|D3>.md` (folder ini): per keputusan — status, berkas:baris, cara cek, uji, perubahan perilaku,
"Butuh agen lain". Tulis bertahap.
