# Rencana Perbaikan — Audit UI Tahap 2 (ERP Kain Nusantara)

Disusun 25 Okt 2026 dari review crawl yang benar (c1_0, c1_1, c2_0, c2_1, c2_2, c3_0, c3_1, c3_2, c3_3), klaim crawl lama (b1_0, b1_1) yang dinyatakan terkonfirmasi oleh review c* atau yang tidak bergantung pada entitas aktif, dan `early_findings.md`. Berkas:baris diverifikasi ulang terhadap kode di HEAD `e5b2579` (Grep/Read). Pasangan berkas ini: `fixplan.json` (isi sama, terstruktur).

Cara baca: **T** = rusak/menyesatkan, kerjakan dulu · **S** = sedang · **R** = ringan. Kolom *Terverifikasi* = berkas:baris & penyebab sudah dicek di kode; “belum terverifikasi” berarti lokasi benar tetapi penyebab (biasanya logika backend/data) masih harus dibuktikan dulu sebelum diubah. Id layar memakai nama view crawler (mis. `ar-aging #4` = keadaan #4).

## 1. Ringkasan angka

| Grup | Cakupan | T | S | R | Total |
|---|---|---:|---:|---:|---:|
| G0 | Komponen bersama (KNSelect, DetailModal, konfirmasi, format, label status, kerangka App) | 3 | 15 | 3 | 21 |
| G1 | Keuangan & akuntansi (GL, kas-bank, piutang/hutang, pajak, konsolidasi, antar-PT, Control Tower) | 13 | 31 | 8 | 52 |
| G2 | Penjualan, CRM, harga, retur jual, POS, sample order + aplikasi HP Sales / Admin Sales | 3 | 24 | 6 | 33 |
| G3 | Gudang/WMS, inventori & lot, logistik, RFID, inspeksi/QC, GRN, transfer, permintaan internal + aplikasi HP Gudang | 8 | 25 | 4 | 37 |
| G4 | Pembelian, RFQ/PR/PO, kontrak & harga internal, makloon, master produk/kategori/satuan/domain, produksi | 4 | 21 | 5 | 30 |
| G5 | R&D/desain/sample, SDM, marketing, dokumen-PDF/ekspor, pengaturan-entitas-izin-persetujuan + aplikasi HP Ops & MD | 16 | 47 | 7 | 70 |
| **Jumlah** | | **47** | **163** | **33** | **243** |

Di luar agen: 29 kandidat duplikasi (keputusan pemilik), 10 pekerjaan tata letak besar, 16 keputusan bisnis, 6 catatan data uji, 8 catatan artefak/perlu tangkap ulang. Pola lintas layar: 13. Butir dengan penyebab belum terverifikasi: 31.

## 2. Aturan kerja untuk agen perbaikan

1. **Himpunan berkas tiap grup tidak beririsan** (daftar di tiap grup; pemeriksaan otomatis: lulus — setiap berkas di butir dimiliki tepat satu grup). Jangan mengedit berkas milik grup lain; bila butir butuh perubahan di sana, tulis catatan untuk pemilik berkas.
2. **G0 dulu untuk API baru**: commit pertama G0 kecil & aditif (G0-14 formatter, G0-15 label status/strip kode, G0-03 pesan 403). API yang SUDAH ada boleh langsung dipakai semua grup: `askConfirm/askReason/askText` (services/confirmService.js), `docStatusLabel` (utils/docStatus.js), `stripInternalCodes` (utils/cleanText.js), `apiErrorText` (utils/apiError.js), `formatDate/formatDateTime/formatQty` (utils/formatters.js), `KNDatePicker/KNMonthPicker/MoneyInput/DecimalInput`, `DetailModal/FormModal`.
3. Gejala KNSelect (✓ pada placeholder, sorot hijau, menu sempit, nilai tak dikenal) **hanya** diperbaiki G0 — jangan ditambal per layar.
4. Butir bertanda “belum terverifikasi” atau yang merujuk keputusan **K-xx**: buktikan penyebab dulu; bila ternyata beda definisi, cukup beri label sumber dan catat untuk pemilik.
5. Ikuti AGENTS.md: Bahasa Indonesia, LF, `git status` sebelum mulai & sebelum commit, jalankan gate relevan dari `docs/KN_00_AGENT_QUICK_START.md` (uji frontend/backend yang menyentuh berkas), laporkan merah apa adanya. Satu commit per butir/kelompok kecil, pesan commit menyebut id butir.
6. Cara cek setiap butir ada di kolom *Cek*; data acuan = `bash scripts/dev_restore_demo.sh`, login `admin@kainnusantara.id` / `demo12345`, entitas Sukacita; HP = lebar 390 px.

## 3. Pola lintas layar (satu pendekatan, satu pemilik)

### P-01 — Aksi berdampak dijalankan sekali klik tanpa dialog konfirmasi aplikasi
- **Pemilik:** G0 menyediakan (askConfirm/askReason/askText SUDAH ada di services/confirmService.js; G0-11 memperbaiki adminDelete). Tiap grup memasang di berkasnya.
- **Pendekatan tunggal:** `await askConfirm({title:'<Aksi> <nomor/objek>?', message:'<akibat>', danger:<membuat/membalik jurnal/menghapus>, confirmLabel:'<kata kerja>'})` sebelum POST/PATCH/DELETE; aksi yang mengubah status dengan alasan → askReason (alasan dikirim ke server). Jangan pakai window.confirm.
- **Lokasi utama:** Tutup Buku, Jalankan Penyusutan, Posting GL & Sahkan gaji, Auto-Encode/Pensiunkan tag, hapus/hentikan kontrak, Setujui retur/transfer antar-PT, Konfirmasi transaksi antar-PT, Sinkron konsolidasi/GL, Jalankan pengingat kontrabon, Pindai temuan, Tutup yang kedaluwarsa, Ulang Posting, Nonaktifkan (master data, gudang, aturan konversi, grade, aturan persetujuan), Konfirmasi Potong, ACC desain HP, Setujui cuti/PR, Kirim peringatan SLA.
- **Butir terkait:** G0-11, G1-03, G1-16, G1-20, G1-25, G1-29, G1-32, G3-01, G3-11, G3-21, G3-25, G3-26, G4-01, G4-11, G4-20, G5-20, G5-26, G5-27, G5-29, G5-33, G5-38, G5-56

### P-02 — Status, kode, id & kunci internal tampil mentah (Inggris/snake_case/kode keputusan)
- **Pemilik:** G0 (utils/docStatus.js, utils/cleanText.js, config/auditLabels.js — G0-15/G0-16); penerapan per grup; teks yang dirakit server diperbaiki pemilik berkas backend.
- **Pendekatan tunggal:** Semua status lewat `docStatusLabel` (perluas peta, bukan `.replace(/_/g,' ')`); kode keputusan/fase lewat `stripInternalCodes`; id teknis (ent_*, wh_*, wms_*, icp_*, so_*) tidak pernah dirender bila ada nomor/nama; enum domain (tahap, jenis kain) lewat registri/useDomainEnums.
- **Lokasi utama:** Jejak Audit, Cek Peran, Master per BU, Konsolidasi, Rekonsiliasi persediaan, Antar-PT (received, KLX-03, pair icp_), Lot (ent_ksc, wh_jakarta), Transfer (Waiting Approval), Scan Terima & HP Gudang, ekspor SO, PDF makloon, notifikasi HP (tahap: shipped, oleh all), panel Alur Dokumen/Referensi (CANCELLED · AKTIF, qc_pending).
- **Butir terkait:** G0-02, G0-15, G0-16, G1-05, G1-06, G1-07, G1-10, G1-11, G1-23, G1-28, G2-02, G2-08, G2-13, G3-03, G3-04, G3-05, G3-08, G3-13, G3-28, G3-31, G4-19, G4-21, G5-01, G5-02, G5-03, G5-10, G5-13, G5-14, G5-16, G5-49, G5-51, G5-55, G5-61

### P-03 — KNSelect: placeholder tampil sebagai pilihan ✓, sorot keyboard = gaya terpilih (hijau), menu selebar pemicu, nilai tak dikenal tampil kosong
- **Pemilik:** G0 sepenuhnya (G0-04, G0-05, G0-06). Grup lain TIDAK menambal per layar; hanya memperbaiki isi opsi yang salah (G4-02, G5-43).
- **Pendekatan tunggal:** Perbaikan di KNSelect.jsx + ui/command.jsx + ui/select.jsx; satu kali, berlaku ke ±200 pemakaian.
- **Lokasi utama:** Lihat daftar di G0-04/G0-05/G0-06.
- **Butir terkait:** G0-04, G0-05, G0-06

### P-04 — KPI/lencana/hitungan tab ikut tersaring tab; hitungan tab = jumlah baris termuat; pesan kosong generik untuk filter
- **Pemilik:** Per grup (G1-45, G2-05, G2-14, G3-29, G4-07, G5-37, G5-41, G5-44).
- **Pendekatan tunggal:** Ringkasan/statistik diambil TANPA param status/tab (atau dari endpoint stats); hitungan per tab dari stats, bukan `rows.length`; pesan kosong saat filter aktif: “Tidak ada <dokumen> berstatus <X>” + “Tampilkan semua”.
- **Lokasi utama:** Pusat Amandemen, Permintaan Desain (desktop & HP), Permintaan Internal, Kontrak, Desain & Pattern, Handfeel/Labdip/Proofing, Pesanan (Backorder), Persetujuan Harga Khusus, Galeri Desain, Pusat Kasus Keuangan, Rekonsiliasi Bank & Antar-PT (lencana hanya di tab aktif).
- **Butir terkait:** G1-45, G2-05, G2-14, G3-29, G4-07, G5-37, G5-41, G5-44

### P-05 — Tabel/grid lebar tetap terpotong (HP 390 px & sebagian 1440 px): aksi/pager/status di luar layar, pesan kosong terpusat ikut terpotong
- **Pemilik:** Per grup untuk butir T/S yang terdaftar (G0-01, G1-21, G1-35, G2-01, G2-03, G2-25, G3-07, G3-30, G4-03, G4-04, G4-14, G5-07). Pola umum ‘halaman desktop di HP’ → L-04 (tidak dikerjakan agen).
- **Pendekatan tunggal:** Pesan kosong & pager di luar wadah `overflow-x-auto`; kolom aksi `sticky right-0` atau aksi di kolom pertama; grid form `grid-cols-1 sm:grid-cols-2`; baris item 2 baris di < 640px; KPI `grid-cols-2`.
- **Lokasi utama:** RFQ, Inspeksi, Pesanan Khusus, Pelacak SO, Pesanan Sample, Riwayat Perubahan pengaturan, Proyeksi Arus Kas, Pusat Kasus Keuangan, Papan PO per Lini, Master Gudang.
- **Butir terkait:** G0-01, G1-21, G1-35, G2-01, G2-03, G2-25, G3-30, G4-03, G4-04, G4-14, G5-07

### P-06 — Format tanggal/angka mentah: ISO & potongan UTC, bulan Inggris di PDF, desimal titik (toFixed), angka tanpa pemisah ribuan
- **Pemilik:** G0 (formatter baru G0-14; formatDate/formatDateTime/formatQty sudah ada); backend PDF → G5-11; tiap grup mengganti pemakaian.
- **Pendekatan tunggal:** Tampilan: `formatDate/formatDateTime` (WIB), `formatPeriod`, `formatPct`, `formatCompactIDR`, `formatQty`; jangan `String(ts).slice()`; PDF: nama bulan Indonesia & angka id-ID.
- **Lokasi utama:** Pengiriman (UTC −7 jam, T), Keuangan (32.4%, 2026-10-01 s/d …), PDF (25 Oct 2026, PPN 12.0%), Analitik Stok, KPI Karyawan, Cuti, Penggajian, Pesanan Sample, Satuan & Konversi, notifikasi stok.
- **Butir terkait:** G0-14, G1-14, G1-15, G2-06, G2-18, G2-33, G3-06, G3-09, G3-24, G5-11, G5-35, G5-66

### P-07 — Galat izin dipamerkan mentah atau ditelan jadi “kosong”; tab/menu tampil untuk peran tanpa izin
- **Pemilik:** G0-03 (apiErrorText 403 → kalimat Indonesia); G5-08, G5-15, G5-21 (sembunyikan tab/vonis); G5-35 (galat muat ditelan).
- **Pendekatan tunggal:** Tab/menu dibentuk dari `can(perms, modul, aksi)`; 403 → pesan akses yang ramah, BUKAN daftar kosong dan BUKAN ‘semua beres’.
- **Lokasi utama:** HP Antrean/Persetujuan (desainer, admin sample, finance), Kesehatan Konfigurasi (MD), Pusat Persetujuan (sales), KPI Karyawan (catch noop).
- **Butir terkait:** G0-03, G5-08, G5-15

### P-08 — Pop-up rincian tanpa tombol × / isi menempel tepi
- **Pemilik:** G0-07 (DetailModal framed); G1-04 (tab melayang), G3-07 (padding panel SPK).
- **Pendekatan tunggal:** DetailModal framed selalu punya × sticky; panel di dalamnya tidak memakai kartu bermargin negatif.
- **Lokasi utama:** Showcase galeri, detail sample R&D (desktop & HP), SPK inspeksi, detail DSR.
- **Butir terkait:** G0-07, G1-04, G3-07

### P-09 — Gambar/lampiran gagal dimuat tanpa fallback teks; lightbox tetap menawarkan “Perbesar”
- **Pemilik:** G0-18 (ProductGallery, MediaLightbox); G5-05, G5-06, G5-39 (desain).
- **Pendekatan tunggal:** Satu perilaku: gagal → teks “Gambar tidak dapat dimuat” + sembunyikan zoom. Berkas 404 di DB uji sendiri = data uji (bukan bug).
- **Lokasi utama:** Permintaan Desain (thumbnail tanpa header), Linked designs, Galeri/Desain & Pattern, Produk (lightbox), lampiran retur.
- **Butir terkait:** G0-18, G5-05, G5-06, G5-39

### P-10 — Notifikasi HP mengarah ke tempat yang salah, dobel, atau tidak membuka dokumen
- **Pemilik:** G5 (G5-09, G5-10, G5-57).
- **Pendekatan tunggal:** Lencana “Putuskan di HP” hanya untuk tipe yang bisa diputus di HP; klik membuka dokumen; dedupe eskalasi; teks server berlabel.
- **Lokasi utama:** hp-admin/manager/finance/designer/sample_admin-notifikasi.
- **Butir terkait:** G5-09, G5-57

### P-11 — Form: isian tanpa label (placeholder sebagai label), `<input type=date>` bawaan, penanda wajib tak seragam, tombol simpan aktif walau wajib kosong, galat validasi tampil sebelum interaksi
- **Pemilik:** Per grup (G0-08 untuk blok alamat).
- **Pendekatan tunggal:** Label di atas setiap isian; * untuk wajib & “(opsional)” untuk opsional; tombol utama nonaktif sampai valid; galat setelah touched/submit di dekat isian; KNDatePicker/KNMonthPicker/MoneyInput/DecimalInput.
- **Lokasi utama:** Lihat butir ber-pola P-11 di tiap grup.
- **Butir terkait:** G0-08, G1-27, G1-30, G1-34, G1-36, G1-42, G2-09, G2-10, G2-17, G2-21, G2-22, G2-24, G2-26, G3-16, G3-20, G3-22, G4-06, G4-10, G4-16, G4-22, G4-23, G5-18, G5-24, G5-25, G5-28, G5-31, G5-59

### P-12 — Angka yang sama berbeda antar layar/tab atau total tidak cocok rincian
- **Pemilik:** Bug → grup pemilik (G1-01, G1-02, G1-13, G1-31, G2-04, G2-05, G2-15, G3-02, G3-17, G3-19, G3-32, G3-33, G4-08, G4-12, G4-24, G5-50). Beda definisi yang disengaja → Keputusan K-01…K-07.
- **Pendekatan tunggal:** Sebelum mengubah rumus, pastikan apakah dua angka memang beda definisi; bila ya, cukup beri label sumber/cakupan di layar dan tunggu keputusan.
- **Lokasi utama:** Piutang, kas, stok tersedia, menunggu persetujuan, backorder, utang antar-PT, harga internal, grade retur, coverage.
- **Butir terkait:** G1-13, G1-31, G2-04, G2-15, G3-02, G3-17, G3-19, G3-32, G3-33, G4-08, G4-12, G4-24, G5-50

### P-13 — Satu konsep banyak nama & istilah Inggris di judul/label
- **Pemilik:** Keputusan glosarium K-13 lebih dulu; G0-17 hanya menyelaraskan judul yang jelas tidak sama; grup memperbaiki ketidakkonsistenan di layar yang sama (Edit vs Ubah, dua nama dalam satu layar).
- **Pendekatan tunggal:** Satu nama per konsep di judul, tombol, pop-up, pesan kosong; “Ubah …” untuk judul form ubah.
- **Lokasi utama:** PO Custom/pesanan khusus/OD, Harga per Pelanggan/Harga Langganan, ronde/round/putaran, sample/sampel, Catalogue/Katalog, Rate/Tarif, Resigned/Keluar, Vendor Bill/Tagihan Supplier, Blanket/Contract PO.
- **Butir terkait:** G0-17, G2-11, G2-19, G4-09, G4-13, G5-23, G5-40, G5-46

## 4. Grup perbaikan

### G0 — Komponen bersama (KNSelect, DetailModal, konfirmasi, format, label status, kerangka App)

T 3 · S 15 · R 3

**Berkas milik grup (hanya grup ini yang boleh mengedit):**

- `frontend/src/components/**  (termasuk components/ui/**)`
- `frontend/src/utils/**`
- `frontend/src/hooks/**`
- `frontend/src/config/**  (navMeta, hubTabs, navStructure, waitingBoards, auditLabels, roles)`
- `frontend/src/services/**  (confirmService, apiClient)`
- `frontend/src/App.js, frontend/src/AppViewRouter.jsx, frontend/src/index.css, frontend/src/App.css, frontend/src/styles/**`
- `frontend/src/features/sales/mobile/MobilePwa.jsx  (dipakai semua aplikasi HP)`
- `frontend/src/features/mobile/MobileShell.jsx`

> Commit pertama G0 WAJIB kecil & aditif: G0-15 (format) + G0-16 (label status/strip kode) + G0-03 (pesan 403). Grup lain boleh langsung memakai API yang SUDAH ada (askConfirm/askReason/askText, docStatusLabel, stripInternalCodes, apiErrorText, formatDate/formatDateTime/formatQty, KNDatePicker, KNMonthPicker); fungsi baru G0 dipakai setelah commit pertama G0 masuk. Gejala KNSelect (✓ placeholder, sorot hijau, menu sempit) TIDAK boleh ditambal per layar — cukup G0-04/05/06.

#### G0-01 [T] · pola P-05
Papan antrean (WaitingQueueBoard) di HP memotong nomor dokumen sampai tak terbaca (“SORD-26(”, “SORD-261”, “KSC/ICR-000”) dan judul papan; tombol aksi “Setujui” memakai warna aksen papan (ungu #6C3FD1) sehingga beda dari papan lain/dialog.

- **Lokasi layar / jalur klik:** HP admin/manager › Ringkas › Buka Tampilan Desktop (Control Tower, Dasbor Manajer) › Papan PO Custom / Retur antar-PT / Barang ditahan QC; pop-up “Lihat semua”. Juga Beranda Sales.
- **Berkas:baris:** `frontend/src/components/WaitingQueueBoard.jsx:41,148-154,170-176,186-192`; `frontend/src/config/waitingBoards.js:13-29`
- **Perbaikan:** Baris papan: nomor dokumen `whitespace-nowrap shrink-0` di baris sendiri, judul/pihak `line-clamp-2` (bukan `truncate` satu baris) di layar < 640px; judul papan `line-clamp-2`. Tombol aksi pakai kelas `.primary-button` (biru) — aksen papan hanya untuk ikon/garis kiri.
- **Cek:** Di 390 px: “SORD-261023-0005” terbaca utuh di papan & pop-up “Lihat semua”; tombol Setujui biru di semua papan; di 1440 tampilan tidak berubah.
- **Terverifikasi:** ya

#### G0-02 [T] · pola P-02
Klik kartu KPI global (Produk Aktif/Jml Tersedia/Jml Dipesan/Pesanan Aktif/Gudang) langsung memindah halaman, lalu laci “DETAIL INSIGHT” menjumlah kg+meter+yard+tanpa satuan jadi satu angka (“JML TERSEDIA 1.376.770,06”) dengan teks Inggris (“inspect produk”, “Review orders”, “Guidance”, “payment simulation”); CTA “Buka Sales POS” padahal sudah pindah.

- **Lokasi layar / jalur klik:** Operasi Gudang / Dasbor & Analitik / POS › klik kartu KPI kepala (operations #128–#144, reports #162–#166).
- **Berkas:baris:** `frontend/src/hooks/useAppActions.js:114-127`; `frontend/src/components/DetailDrawer.jsx:11,18`; `frontend/src/App.js:507-514`
- **Perbaikan:** Hapus perpindahan halaman otomatis (baris 124-126) — pindah hanya lewat tombol CTA laci. Fakta stok memakai `formatUnitTotals(metric.available_by_unit / reserved_by_unit)` per satuan. Tulis ulang body/cta dalam Bahasa Indonesia (mis. “Buka katalog”, “Lihat pesanan”). Kicker DetailDrawer “Detail Insight” → “Rincian”.
- **Cek:** Klik kartu Jml Tersedia di Operasi Gudang: halaman tetap, laci menampilkan “60.883,83 kg · 106 meter · … yard”, tanpa kata Inggris; tombol CTA baru memindah halaman.
- **Terverifikasi:** ya

#### G0-03 [T] · pola P-07
Pesan galat 403 dari server tampil mentah ke pengguna: “Permission ditolak: approval.view”, “Permission ditolak: settings.view” (kode izin + Inggris).

- **Lokasi layar / jalur klik:** HP Desainer/Admin Sample › tab Antrean; HP MD › Spesifikasi Produk › Kebijakan R&D › Kesehatan Konfigurasi.
- **Berkas:baris:** `frontend/src/utils/apiError.js:69-80`
- **Perbaikan:** Di `apiErrorText`: bila status 403 (atau detail cocok `/^Permission ditolak:\s*([\w.]+)/`) kembalikan “Anda tidak punya akses ke <label modul>.” (label dari `config/auditLabels.moduleLabel` atau peta kecil; kode izin hanya ke `console.debug`). Tambahkan uji unit.
- **Cek:** apiErrorText({response:{status:403,data:{detail:'Permission ditolak: approval.view'}}}) → kalimat Indonesia tanpa “approval.view”; layar yang memakai apiErrorText ikut berubah.
- **Terverifikasi:** ya

#### G0-04 [S] · pola P-03
KNSelect: (a) opsi placeholder/bernilai kosong tampil sebagai opsi TERPILIH ✓ hijau (Radix: item sentinel; combobox: opsi value "" saat value ""); (b) sorotan keyboard hijau penuh (`--accent` 144 67% 46%) sama dengan gaya terpilih — butir pertama tampak terpilih padahal ✓ di butir lain; (c) daftar tidak bergulir/menyorot nilai aktif; (d) daftar kosong tanpa pesan “belum ada data”.

- **Lokasi layar / jalur klik:** Pola lintas layar: closing › Bulan (“Januari” hijau padahal Oktober), expense-categories › akun, incentive-rates › Satuan (sorot Meter, ✓ Yard), rnd-divisions, RFQ › Pilih gudang, interco › PT, orders › Status rinci, internal-requests › barang, HP Stok & ATP › Pilih barang, document-center › Entitas; placeholder ✓: blanket-po › Produk, Buat Labdip › handfeel, cs-rfid-lokasi › Pilih reader, cs-design-gallery › Semua tag, designer-kpi › Semua divisi, documents › Pilih produk, operations › Tambah Stok Awal, HP MD Meja › Pilih desainer, rnd-proofing › desain ACC, supplier-contracts › supplier.
- **Berkas:baris:** `frontend/src/components/KNSelect.jsx:51-130 (Check :116-120), :204-227 (sentinel)`; `frontend/src/components/ui/command.jsx:86`; `frontend/src/components/ui/select.jsx:85-99`; `frontend/src/index.css:21`
- **Perbaikan:** (a) Jalur Radix: render item sentinel tersembunyi dari daftar (mis. `className="hidden"`, tetap terdaftar agar SelectValue menampilkan placeholder abu); jalur combobox: opsi bernilai "" tidak diberi ✓ dan ditampilkan sebagai teks petunjuk abu/“— kosongkan —” hanya bila value terisi. (b) Ganti `data-[selected=true]:bg-accent` & `focus:bg-accent` dengan sorot netral (#F2F2F7, teks tetap gelap); nilai terpilih = ✓ + teks tebal biru. (c) Set `value`/`defaultValue` cmdk ke opsi terpilih + `scrollIntoView` saat buka; Radix sudah menggulir ke item terpilih bila sentinel tidak dipakai. (d) Prop `emptyText` (bawaan “Belum ada pilihan”) bila opsi nyata kosong. Jangan ubah kontrak prop.
- **Cek:** closing › Bulan: dibuka dengan sorotan di “Oktober” dan tidak ada butir hijau penuh; blanket-po › Produk & rnd-proofing › desain: placeholder tidak bercentang; pemilih tanpa data menampilkan “Belum ada pilihan”; uji `frontend` KNSelect lama tetap hijau.
- **Terverifikasi:** ya

#### G0-05 [S] · pola P-03
Menu KNSelect selebar pemicunya (`w-[var(--radix-popover-trigger-width)]`) → opsi patah 3–4 baris/terpotong (“Rancamala / · Gudang / Knitting”, “Retur (grac B/BS/C)”, “Pelanggan salah transfer …”).

- **Lokasi layar / jalur klik:** cs-rfid-lokasi/devices/gate/tags › Semua Gudang; cs-stock-analytics › Gudang/Kategori; finance-cases › Jenis kasus; hr-visits › Semua Karyawan; inventory-lots › 4 filter; RFQ › Pilih gudang (desktop & HP); returns › filter status; orders › Status rinci; hr-leave/overtime › Semua Periode; HP MD Semua › Pilih gudang.
- **Berkas:baris:** `frontend/src/components/KNSelect.jsx:106-110`; `frontend/src/components/ui/select.jsx:66-67`
- **Perbaikan:** PopoverContent: `min-w-[var(--radix-popover-trigger-width)] w-max max-w-[min(26rem,calc(100vw-1.5rem))]`; SelectContent sama (min-w pemicu, lebar mengikuti isi, batas viewport). Opsi boleh 2 baris hanya bila melewati batas maksimum.
- **Cek:** Semua menu di daftar lokasi menampilkan nama gudang “Rancamalang · Gudang Knitting” satu baris di 1440 dan tidak keluar layar di 390.
- **Terverifikasi:** ya

#### G0-06 [S] · pola P-03
KNSelect diam-diam menampilkan kosong/“Pilih…” bila nilai tersimpan tidak ada di daftar opsi → pengguna tak tahu nilai sebenarnya (dan bisa menimpa data saat simpan).

- **Lokasi layar / jalur klik:** rnd-divisions (Rina Merchandiser, Yoga Admin Sample “Pilih…”); supplier-contracts › Ubah KSC/SCT-00261 (Jenis Kontrak kosong); design-requests › Sumber Permintaan (b1).
- **Berkas:baris:** `frontend/src/components/KNSelect.jsx:51 (selected), :204-227`
- **Perbaikan:** Bila `value` non-kosong tak ditemukan di `options`: tampilkan nilai mentah dengan gaya peringatan “<nilai> (tidak ada di daftar)” + `console.warn` di dev; tambahkan prop opsional `unknownLabel(value)`. Perbaikan isi opsi dikerjakan pemilik layar (G4-02, G5-43).
- **Cek:** Buka Ubah KSC/SCT-00261 sebelum G4-02: Jenis Kontrak menampilkan “internal (tidak ada di daftar)”, bukan kotak kosong.
- **Terverifikasi:** ya

#### G0-07 [S] · pola P-08
Pop-up rincian `DetailModal framed` tidak punya tombol tutup ×; penutupan hanya lewat Esc/klik latar atau tombol “Tutup” di dasar setelah gulir panjang (±2.600–2.900 px di HP).

- **Lokasi layar / jalur klik:** Galeri Desain › kartu (Showcase); Handfeel/Labdip/Proofing › kartu sample (desktop & HP MD); SPK Inspeksi (qc-inspection › Putuskan di SPK, returns › SPK, inspections › Buka SPK).
- **Berkas:baris:** `frontend/src/components/DetailModal.jsx:51-90`
- **Perbaikan:** Saat `framed` (prop baru `showClose`, bawaan true) render tombol × `sticky top-0` di pojok kanan atas kartu (aria-label “Tutup”, memanggil onClose). Pastikan tidak menimpa tombol aksi kepala panel (beri `pr-10` pada kepala pertama atau letakkan di luar kartu).
- **Cek:** Buka pop-up sample KSC/SMP-00017 di 1440 & 390: tombol × terlihat tanpa menggulir dan menutup pop-up.
- **Terverifikasi:** ya

#### G0-08 [S] · pola P-11
LocationFields (alamat): label MAJUSCULE 10px beda dari form induk; dua isian kode pos (“ISI CEPAT DARI KODE POS” + “KODE POS”); `col-span-2` di grid satu kolom → isian alamat setengah lebar; galat “Pilih kode pos.” langsung tampil saat form ubah dibuka dan diletakkan di bawah KECAMATAN.

- **Lokasi layar / jalur klik:** CRM › Pelanggan Baru/Edit Pelanggan; POS & HP Sales › Pelanggan baru; SDM › Tambah/Edit Karyawan; Mitra Makloon › Buat/Edit; Tambah Badan Usaha.
- **Berkas:baris:** `frontend/src/components/LocationFields.jsx:25-35,79-88`
- **Perbaikan:** Prop `labelStyle` ("caps"|"sentence", bawaan mengikuti mayoritas form = sentence + *); gabungkan “isi cepat dari kode pos” menjadi tombol cari di isian KODE POS; `col-span-2` hanya bila induk memberi `inGrid`; validasi tampil setelah `touched`/submit dan ditempel di isian KODE POS.
- **Cek:** Edit Pelanggan QA Cust B: tidak ada teks merah saat dibuka; pop-up Pelanggan Baru HP: isian alamat selebar penuh; hanya satu isian kode pos.
- **Terverifikasi:** ya

#### G0-09 [S]
Bilah biru berisi ikon ✨ saja (teks kosong) di atas setiap layar desktop-di-HP.

- **Lokasi layar / jalur klik:** HP semua peran › Tampilan Desktop / Tampilan lengkap (Control Tower, Labdip, Desain & Pattern, RFQ, Inspeksi, Pesanan, Meja Admin Sample, Barang Masuk).
- **Berkas:baris:** `frontend/src/App.js:518-523`; `frontend/src/components/CoreWidgets.jsx:336-342`
- **Perbaikan:** Render `system-notice-mobile` hanya bila `notice` berisi teks (sama seperti versi desktop di CoreWidgets).
- **Cek:** HP › Buka Tampilan Desktop: tidak ada bilah biru kosong; bila ada pesan sistem, bilah tampil dengan teks.
- **Terverifikasi:** ya

#### G0-10 [S]
Ajakan notifikasi HP: dalam keadaan izin diblokir kartu menampilkan empat pesan sekaligus (“Diblokir…”, penjelasan lama + Nanti/Lanjutkan, cara membuka pengaturan, galat merah) dan langkah 3 menyuruh mengetuk “Aktifkan notifikasi” yang sudah tidak ada; “Pasang sekarang” tanpa umpan balik bila prompt tidak tersedia.

- **Lokasi layar / jalur klik:** HP Sales/MD › Lainnya › Aktifkan notifikasi › Lanjutkan (› Cara membuka pengaturan notifikasi); › Pasang sekarang.
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobilePwa.jsx:96,118-228 (138,177,182,186,199)`
- **Perbaikan:** Satu state machine (default → penjelasan → meminta → aktif | diblokir). Saat diblokir: sembunyikan penjelasan lama & galat ganda, tampilkan satu panduan 3 langkah dengan langkah 3 “ketuk ‘Sudah diizinkan? Periksa lagi’”. “Pasang sekarang” tanpa `beforeinstallprompt` → toast “Pemasangan dari menu peramban: ⋮ › Tambahkan ke layar utama”.
- **Cek:** Tolak izin di peramban: kartu hanya menampilkan status “Diblokir” + panduan 3 langkah; tidak ada tombol yang dirujuk tapi tak ada.
- **Terverifikasi:** ya (kode); perilaku prompt perlu dicek di HP nyata

#### G0-11 [S] · pola P-01
Nonaktifkan di Master Data (pelanggan, template dokumen, satuan) langsung DELETE tanpa konfirmasi; pesan memakai nama resource mentah (“customers dinonaktifkan.”, “Gagal deactivate customers.”).

- **Lokasi layar / jalur klik:** Pengaturan › Master Data (customers-master), Template Dokumen Dasar, Satuan & Konversi › tombol merah “Nonaktifkan” di baris.
- **Berkas:baris:** `frontend/src/hooks/useAppActions.js:561-568`
- **Perbaikan:** `adminDelete`: `askConfirm({title:`Nonaktifkan ${label}?`, message:'…tidak bisa dipakai di transaksi baru…', danger:true, confirmLabel:'Nonaktifkan'})` sebelum DELETE; peta RESOURCE_LABEL (customers→pelanggan, document-templates→template dokumen, uoms→satuan, dst.) untuk pesan sukses/gagal.
- **Cek:** Klik Nonaktifkan di baris pelanggan → dialog aplikasi merah muncul; batal tidak mengirim apa pun; pesan sukses “Pelanggan … dinonaktifkan.”
- **Terverifikasi:** ya

#### G0-12 [S]
Tombol melayang kembali ke HP berbeda per peran (“Tampilan HP” biru di tengah vs “← Kembali ke aplikasi HP” hitam di kiri) dan menutupi isi (kolom ITEM Pesanan Sample, kaki pop-up “Batal” di Sample Proofing Baru, “ROP 30…”).

- **Lokasi layar / jalur klik:** HP admin/manager/sample_admin vs MD/Sales/Gudang › Tampilan Desktop.
- **Berkas:baris:** `frontend/src/App.js:461,634-640`
- **Perbaikan:** Satu gaya & posisi (kiri bawah, kecil), disembunyikan saat ada pop-up terbuka (cek `document.body.style.overflow === 'hidden'` atau konteks overlayStack) dan beri `padding-bottom` pada `main` saat tombol tampil.
- **Cek:** Di 390: tombol sama untuk semua peran; saat pop-up terbuka tombol tidak terlihat; baris terakhir tabel tidak tertutup.
- **Terverifikasi:** ya

#### G0-13 [S]
Kalender KNDatePicker di HP menutupi judul & tombol × pop-up atau tombol kaki (“Buat RFQ”); di desktop menjulur keluar pop-up.

- **Lokasi layar / jalur klik:** HP Sales › Stok & ATP › kartu › Minta › Dibutuhkan Sebelum; HP MD › Semua › RFQ › Buat RFQ › Dibutuhkan Sebelum; desktop: Buat Kontrak Blanket, Buat Labdip.
- **Berkas:baris:** `frontend/src/components/KNDatePicker.jsx:42`
- **Perbaikan:** PopoverContent: `side="bottom" avoidCollisions collisionPadding={12} sticky="partial"`, batasi tinggi (`max-h-[min(22rem,70dvh)] overflow-auto`) dan versi ringkas di < 400px.
- **Cek:** Di 390 kalender tidak menutupi judul/× maupun tombol kaki; di 1440 tetap di dalam viewport.
- **Terverifikasi:** ya

#### G0-14 [S] · pola P-06
Belum ada formatter bersama untuk persen/periode/ringkas Rupiah → layar memakai `toFixed` (titik desimal) & ISO mentah (“32.4%”, “0.75%”, “2026-10”, “150.0 jt”, “1.4 M”).

- **Lokasi layar / jalur klik:** Fondasi untuk P-06 (dipakai G1–G5).
- **Berkas:baris:** `frontend/src/utils/formatters.js`
- **Perbaikan:** Tambah (aditif): `formatPct(v, digits=1)` (id-ID, koma), `formatPeriod('2026-10')` → “Oktober 2026”, `formatCompactIDR(v)` → “1,4 M”/“150 jt” (tanpa “.0”), `formatDecimal(v, max=2)`. Sertakan uji unit di `__tests__`.
- **Cek:** Uji: formatPct(32.4)==='32,4%'; formatPeriod('2026-10')==='Oktober 2026'; formatCompactIDR(150000000)==='150 jt'.
- **Terverifikasi:** ya

#### G0-15 [S] · pola P-02
Label status bersama belum mencakup kode yang bocor ke layar (waiting_goods, qc_pending, created, waiting_stock, siap_disahkan, posted, staging, receiving, …) dan `stripInternalCodes` belum mengenal kode keputusan (KLX-03, KLR-05, P7-K1, KN-D16, G-6, INV-IC-02, KN_17 §…).

- **Lokasi layar / jalur klik:** Fondasi untuk P-02 (dipakai G1–G5).
- **Berkas:baris:** `frontend/src/utils/docStatus.js:4-45`; `frontend/src/utils/cleanText.js:2-15`
- **Perbaikan:** Tambah ke DOC_STATUS_LABEL: waiting_goods “Menunggu barang”, receiving “Sedang diterima”, qc_check “Cek QC”, qc_pending “Menunggu QC”, qc_rejected “Ditolak QC”, put_away “Disimpan ke rak”, escalated “Dieskalasi”, created “Dibuat”, confirmed “Dikonfirmasi”, waiting_stock “Menunggu stok”, siap_disahkan “Siap disahkan”, posted “Terposting”, staging “Disiapkan”, picked “Diambil”, packed “Dikemas”, committed “Terikat”, expired “Kedaluwarsa”, partial “Sebagian”. Perluas regex stripInternalCodes untuk pola di atas (dengan/ tanpa kurung). Uji unit.
- **Cek:** docStatusLabel('waiting_goods')==='Menunggu barang'; stripInternalCodes('diputus sistem (KLR-05)')==='diputus sistem'.
- **Terverifikasi:** ya

#### G0-16 [S] · pola P-02
Label aksi jejak audit jatuh ke `humanize` Inggris (“Reservation Expired”, “Login”).

- **Lokasi layar / jalur klik:** Pengaturan › Integrasi & Audit › Jejak Audit (admin #6/#9).
- **Berkas:baris:** `frontend/src/config/auditLabels.js:64-73`
- **Perbaikan:** Tambah label Indonesia untuk kunci yang muncul (reservation_expired → “Reservasi kedaluwarsa”, login → “Masuk”, logout → “Keluar”, …) dan fallback humanize → “Aksi lain (<kode>)” hanya di tooltip. Bagian tampilan baris dikerjakan G5-01.
- **Cek:** Jejak Audit tidak menampilkan “Reservation Expired”.
- **Terverifikasi:** ya

#### G0-17 [S] · pola P-13
Judul metadata navigasi tidak sama dengan label sidebar/kartu di layar yang sama (tanpa menunggu glosarium): “Impor Dataset Client” vs kartu “Klien”; “Dashboard Keuangan” vs sidebar “Dasbor Keuangan”; “PPh & Rekap Pajak” padahal tab pertama PPN; “Riwayat Persetujuan PO” berisi antrean; “SLA Round” vs isi “Ronde”.

- **Lokasi layar / jalur klik:** Header halaman client-dataset-import, finance-tower, cs-pajak, purchase-approval, rnd-reports.
- **Berkas:baris:** `frontend/src/config/navMeta.js:13,61,69,138,161,…`; `frontend/src/config/hubTabs.js:18,163,187`
- **Perbaikan:** Selaraskan judul dengan label sidebar/kartu: “Impor Dataset Klien”, “Dasbor Keuangan”, “Pajak (PPN & PPh)”, “Persetujuan Pembelian”, “Laporan R&D · SLA Ronde”. Istilah yang masuk daftar glosarium (K-13) jangan diganti sebelum keputusan.
- **Cek:** Kelima layar: judul kepala = label sidebar/kartu.
- **Terverifikasi:** ya

#### G0-18 [S] · pola P-09
Galeri foto produk & lightbox: gambar gagal dimuat tetap menawarkan “Perbesar foto”/“Perbesar”; lightbox membuka gambar rusak dengan navigasi “1 / 2”.

- **Lokasi layar / jalur klik:** Produk & Varian › kartu (⤢) TEST_iter4…; detail desain › thumbnail; retur › lampiran.
- **Berkas:baris:** `frontend/src/components/ProductGallery.jsx:18-30`; `frontend/src/components/MediaLightbox.jsx:19,57`
- **Perbaikan:** Simpan status galat gambar → sembunyikan tombol zoom & lightbox, tampilkan “Gambar tidak dapat dimuat” (teks, bukan hanya ikon); MediaLightbox: sembunyikan tombol “Perbesar” saat status error.
- **Cek:** Kartu dengan foto 404: tidak ada tombol ⤢; lightbox lampiran 404 hanya menampilkan pesan + Tutup.
- **Terverifikasi:** ya

#### G0-19 [R]
PaginationBar: ukuran halaman di luar `pageSizeOptions` (25) → tidak ada pilihan “Per halaman” yang aktif.

- **Lokasi layar / jalur klik:** inspections (25), CostingView, InventoryStatusBoard, ReorderSuggestions, SupplierItemsView, PricelistView, DataHygienePanel.
- **Berkas:baris:** `frontend/src/components/PaginationBar.jsx:61,166`
- **Perbaikan:** Gabungkan `pageSize` aktif ke daftar opsi (unik, urut) sebelum render.
- **Cek:** Inspeksi: “Per halaman 25” tampil terpilih.
- **Terverifikasi:** ya

#### G0-20 [R]
Petunjuk alasan minimal di dialog alasan tampil oranye sebelum pengguna mengetik dan kalimatnya menggurui (“Alasan yang tidak bisa dipakai orang lain sama saja dengan kolom kosong.”).

- **Lokasi layar / jalur klik:** Semua askReason ber-reasonMinLength (mis. Antar-PT › Batalkan draf retur, Buka kembali SPK).
- **Berkas:baris:** `frontend/src/components/ConfirmModal.jsx:173-183`
- **Perbaikan:** Sebelum ada input: hint abu netral “Minimal N huruf”; setelah mengetik: hitung mundur oranye/hijau; hapus kalimat kedua.
- **Cek:** Buka “Batalkan draf retur”: tidak ada teks oranye sebelum mengetik.
- **Terverifikasi:** ya

#### G0-21 [R]
Pesan sistem awal “Sistem siap. Stok reservation dikunci 3 hari.” (campur Inggris) dengan tombol “Selesaikan” ambigu; mendesak pemilih badan usaha.

- **Lokasi layar / jalur klik:** Bilah atas desktop semua layar (escalations, internal-requests).
- **Berkas:baris:** `frontend/src/App.js:111`; `frontend/src/components/CoreWidgets.jsx:336-342`
- **Perbaikan:** Nilai awal `notice` kosong (atau “Stok yang dipesan dikunci 3 hari.”); label CTA “Tutup”.
- **Cek:** Saat masuk tidak ada pesan campur Inggris; pemilih badan usaha tidak terdesak.
- **Terverifikasi:** ya

### G1 — Keuangan & akuntansi (GL, kas-bank, piutang/hutang, pajak, konsolidasi, antar-PT, Control Tower)

T 13 · S 31 · R 8

**Berkas milik grup (hanya grup ini yang boleh mengedit):**

- `frontend/src/features/finance/**  (termasuk finance/interco/**, finance/amendments/**, finance/cases/**, finance/glmapping/**, finance/payments/**)`
- `frontend/src/features/pettycash/**`
- `frontend/src/features/costing/**`
- `frontend/src/features/home/**`
- `frontend/src/features/purchasing/CashManagementView.jsx`
- `frontend/src/features/purchasing/InputTaxView.jsx`
- `frontend/src/features/purchasing/InputTaxCreateModal.jsx`
- `frontend/src/features/purchasing/contrabon/**`
- `backend/services/finance_tower_service.py`
- `backend/services/gl_service.py`
- `backend/services/gl_mapping_registry.py`
- `backend/services/gl_mapping_service.py`
- `backend/services/consolidation_service.py`
- `backend/services/payment_variance_service.py`
- `backend/services/tax_center_service.py`
- `backend/services/home_service.py`
- `backend/services/contra_bon_service.py`
- `backend/services/contra_bon_reminder.py`
- `backend/services/interco_service.py`
- `backend/services/interco_margin.py`
- `backend/services/interco_money_service.py`
- `backend/services/interco_return_service.py`
- `backend/services/interco_loan_service.py`
- `backend/routers/cash.py`

> Jangan menyentuh ReturnChainMap (G2), pdf_resolvers (G5), interco_price_service (G4).

#### G1-01 [T]
AR / Piutang & Umur: baris TOTAL tidak ikut filter — dengan “Hanya Lewat Jatuh Tempo ✓” hanya Toko Kain Sejahtera tampil (Rp 37.188.287) tetapi TOTAL tetap Rp 407.850.942.

- **Lokasi layar / jalur klik:** Keuangan › AR / Piutang & Umur › chip “Hanya Lewat Jatuh Tempo” (ar-aging #4).
- **Berkas:baris:** `frontend/src/features/finance/ARAgingView.jsx:119,126-127,286-302`
- **Perbaikan:** Saat cari/filter aktif, footer menjumlah `rows` terfilter per bucket (current, b1_30, …, penalty) — `totals` server hanya dipakai tanpa filter; atau beri label “Total semua pelanggan” + baris kedua “Total yang tampil”.
- **Cek:** Chip aktif: TOTAL = jumlah baris tampil; chip mati: TOTAL kembali Rp 407.850.942.
- **Terverifikasi:** ya

#### G1-02 [T]
Kontrabon: tab Jadwal Tukar Faktur menulis “BELUM DITAGIH SUPPLIER Rp 0” dan tiap supplier “Belum ditagih Rp 0 · 0 PO”, padahal KPI atas & tab GR “Rp 54.400.000 · 24 PO”.

- **Lokasi layar / jalur klik:** Hutang Pemasok › Kontrabon › tab Jadwal Tukar Faktur vs tab GR Belum Ditagih (contra-bons #28 vs #32).
- **Berkas:baris:** `frontend/src/features/purchasing/contrabon/ExchangeSchedulesTab.jsx:46-49,137`; `backend/services/contra_bon_reminder.py:124-154`; `backend/services/contra_bon_service.py:442`
- **Perbaikan:** Telusuri `schedules()`: `unbilled_receipts(entity_ids, supplier_id, entity_id=sup.entity_id or …)` — kandidat penyebab: filter entitas pemasok global/kosong sehingga 0. Samakan parameter dengan endpoint tab GR; tambah uji backend (jumlah per supplier = total tab GR).
- **Cek:** Jumlah “Belum ditagih supplier” = Rp 54.400.000 dan baris supplier menampilkan nilai/PO yang sama dengan tab GR.
- **Terverifikasi:** lokasi ya; penyebab backend belum terverifikasi

#### G1-03 [T] · pola P-01
Tutup Buku: tombol “Tutup Buku” langsung POST /finance/closing/close tanpa dialog, padahal periode menjadi terkunci penuh dan pratinjau sedang memperingatkan “Saldo Suspense (1-9999) belum nol”.

- **Lokasi layar / jalur klik:** Keuangan › Tutup Buku › Tutup Buku (closing #17).
- **Berkas:baris:** `frontend/src/features/finance/ClosingView.jsx:97,207`
- **Perbaikan:** `askConfirm({danger:true, title:`Tutup buku ${bulan} ${tahun} — ${entitas}?`, message: akibat (terkunci; buka lagi lewat Buka Periode) + daftar peringatan pratinjau, confirmLabel:'Tutup Buku'})`. Apakah suspense ≠ 0 harus memblokir = keputusan K-15.
- **Cek:** Klik Tutup Buku → dialog merah menyebut periode, entitas, dan peringatan suspense; Batal tidak mengirim permintaan.
- **Terverifikasi:** ya

#### G1-04 [T] · pola P-08
Rekening & Saldo: di pop-up rekening, tab “Mutasi / Riwayat Perubahan” melayang di luar panel putih di atas latar buram.

- **Lokasi layar / jalur klik:** Kas & Bank › Rekening & Saldo › klik kartu BCA Operasional KSC › Mutasi (bank-accounts #17/#18).
- **Berkas:baris:** `frontend/src/features/finance/BankAccountsView.jsx:238-246`
- **Perbaikan:** Pakai `<DetailModal framed>` atau bungkus tab-bar + isi tab dalam satu `section-card`.
- **Cek:** Tab Mutasi/Riwayat berada di dalam kartu putih yang sama dengan isinya.
- **Terverifikasi:** ya

#### G1-05 [T] · pola P-02
Pusat Amandemen › JEJAK DOKUMEN mencetak kode mentah `APPLIED_TO`, `AMENDS`, `(sales_order)`.

- **Lokasi layar / jalur klik:** Penjualan › Koreksi & Amandemen › klik KSC/AMD-00022 (amendments #11).
- **Berkas:baris:** `frontend/src/features/finance/amendments/AmendmentDetailPanel.jsx:177-178`
- **Perbaikan:** Peta REL_LABEL {APPLIED_TO:“Diterapkan ke”, AMENDS:“Mengoreksi”, …} dan DOC_TYPE_LABEL (sales_order→“Pesanan Penjualan”, …); fallback `docStatusLabel`-gaya humanize, bukan kode.
- **Cek:** Jejak dokumen berbunyi “Mengoreksi KSC/SO-… (Pesanan Penjualan)”.
- **Terverifikasi:** ya

#### G1-06 [T] · pola P-02
Konsolidasi › Eliminasi menampilkan kode fase/invarian internal: “Auto G-6: Eliminasi antar-PT…”, lencana “AUTO G-6”/“Balanced”, tombol “Sinkron Antar-PT (G-6)”, catatan “Auto-generated … (FASE G-6) … (INV-IC-02/INV-IC-03)”.

- **Lokasi layar / jalur klik:** Laporan › Konsolidasi Grup › tab Eliminasi (consolidation #21).
- **Berkas:baris:** `frontend/src/features/finance/GroupConsolidationView.jsx:111-130,269,292,297,319`; `backend/services/consolidation_service.py:448-700 (teks note/judul entri)`
- **Perbaikan:** Judul “Eliminasi otomatis antar-PT KSC/IC-00016”, lencana “Otomatis” & “Seimbang”, tombol “Sinkron Antar-PT”, pesan sukses/galat tanpa “(G-6)”; backend menulis note tanpa kode fase/invarian (atau frontend `stripInternalCodes` saat render — keduanya).
- **Cek:** Tab Eliminasi tidak memuat “G-6”, “FASE”, “INV-IC”, “Balanced”, “Auto-generated”.
- **Terverifikasi:** ya

#### G1-07 [T] · pola P-02
Buku Besar › Rekonsiliasi Persediaan › “Kenapa berselisih?” menampilkan kode mentah sebagai label baris (initial, inbound, subcon_receipt, cycle_count_found, shipment_cogs, interco_transaction, …), kalimat “Roll dengan asal 'cycle_count_found'”, dan catatan kaki status available/reserved/committed/picked/packed/quarantine/hold.

- **Lokasi layar / jalur klik:** Buku Besar › tab Rekonsiliasi Persediaan › baris Sukacita Textile › Kenapa berselisih? (general-ledger #64).
- **Berkas:baris:** `frontend/src/features/finance/InventoryReconTab.jsx:226-228,241-243,378`; `backend/services/gl_service.py:3445`
- **Perbaikan:** Peta ORIGIN_LABEL/SOURCE_LABEL Indonesia (initial→Saldo awal, inbound→Barang masuk, subcon_receipt→Terima dari makloon, cycle_count_found→Temuan stock opname, shipment_cogs→HPP pengiriman, interco_transaction→Transaksi antar-PT, …); status via docStatusLabel; backend memakai label yang sama di kalimat dugaan.
- **Cek:** Panel penjelasan tidak memuat satu pun kode snake_case.
- **Terverifikasi:** ya

#### G1-08 [T]
Pemetaan Akun: “Ubah akun · Pendapatan penjualan” — isian akun kosong & daftar “Tidak ada hasil”, sehingga akun Pendapatan (4-xxxx) tidak bisa dipilih. Penyebab: registri memakai tipe `revenue`, COA memakai `income`; `candidates()` menyaring `allowed_types` → kosong untuk SEMUA kebutuhan pendapatan.

- **Lokasi layar / jalur klik:** Pengaturan › Pemetaan Akun › baris Pendapatan penjualan › Ubah (gl-account-mappings #35/#36); juga Pendapatan denda/lain-lain/klaim makloon.
- **Berkas:baris:** `backend/services/gl_mapping_registry.py:14-21`; `backend/services/gl_service.py:40-46`; `backend/services/gl_mapping_service.py:123-129`; `frontend/src/features/finance/glmapping/MappingEditDialog.jsx:13-16,29-30`
- **Perbaikan:** Samakan tipe: registri `"4": "income"` (+ TYPE_LABEL) atau normalisasi revenue↔income di `candidates()`/`_status`; dialog menampilkan pesan bila kandidat kosong (“Tidak ada akun berjenis Pendapatan yang aktif & bisa dijurnal”). Uji backend kandidat untuk penjualan.pendapatan tidak kosong.
- **Cek:** Dialog Ubah akun Pendapatan penjualan menampilkan 4-1000 terpilih dan daftar akun 4-xxxx.
- **Terverifikasi:** ya

#### G1-09 [T]
Antar-PT › Rapor Margin: kartu “DIELIMINASI DI KONSOLIDASI Rp 0” berketerangan “sama dengan angka belum terealisasi” padahal kartu sebelahnya −Rp 180.000.

- **Lokasi layar / jalur klik:** Akuntansi & Pajak › Antar Entitas › tab Rapor Margin (interco-transactions #48).
- **Berkas:baris:** `frontend/src/features/finance/interco/IntercoMarginPanel.jsx:21,67-70`; `backend/services/interco_margin.py`
- **Perbaikan:** Teks bantu dihitung dari dua angka yang tampil (|dieliminasi − belum terealisasi| > 0,01 → “berbeda Rp X”); periksa kenapa nilai dieliminasi 0 (tanda/arah `elimination_gap`).
- **Cek:** Kartu tidak lagi menyatakan “sama dengan” bila angkanya berbeda.
- **Terverifikasi:** teks ya; penyebab angka 0 belum terverifikasi

#### G1-10 [T] · pola P-02
Antar-PT › Jadwal Bayar: kolom STATUS mentah “received”; PERIODE BAYAR “Menunggu KLX-03” dan banner “…per PT pembayar, KLX-03”.

- **Lokasi layar / jalur klik:** Antar Entitas › tab Jadwal Bayar (interco #40–#43).
- **Berkas:baris:** `frontend/src/features/finance/interco/IntercoPaymentSchedule.jsx:77,100,107`; `backend/services/interco_service.py:1159 (payment_schedule note)`
- **Perbaikan:** `docStatusLabel(r.status)`; hapus kode keputusan dari teks (frontend `stripInternalCodes`, backend note tanpa “KLX-03”).
- **Cek:** Tab Jadwal Bayar tanpa “received”/“KLX-03”.
- **Terverifikasi:** ya

#### G1-11 [T] · pola P-02
Detail Transaksi Antar-PT: subjudul “CST/IC-00007 ↔ KSC/IC-00007 · pair icp_cffcba4ad711” (id teknis).

- **Lokasi layar / jalur klik:** Antar Entitas › ikon mata baris KSC/IC-00007 (interco #31).
- **Berkas:baris:** `frontend/src/features/finance/interco/IntercoDetailPanel.jsx:86`
- **Perbaikan:** Hapus “pair <id>” dari teks (boleh di `title` untuk admin).
- **Cek:** Subjudul hanya nomor kedua dokumen.
- **Terverifikasi:** ya

#### G1-12 [T]
Rencana Pembayaran › “Selisih Pembayaran · Kurang bayar” bertentangan: kalimat “seharusnya Rp 0 … Kurang Rp 166.499”, rincian “Selisih Rp 3.331 LEBIH bayar”, tabel “Seharusnya Rp 169.830 · −Rp 166.499”.

- **Lokasi layar / jalur klik:** Keuangan › Rencana Pembayaran & Denda › Selisih Bayar › Putuskan (KSC/AR-00043) (payment-plans #141).
- **Berkas:baris:** `frontend/src/features/finance/payments/PaymentVarianceDialog.jsx:35-48`; `backend/services/payment_variance_service.py:340-362`
- **Perbaikan:** Satu sumber angka: `expected` & `delta` dari server; kalimat memakai `boundary` hanya bila > 0, kalau tidak `expected`; arah (kurang/lebih) dari delta yang sama dengan tabel. Uji backend kasus boundary 0.
- **Cek:** Dialog KSC/AR-00043: kalimat, rincian, dan tabel menyebut angka & arah yang sama.
- **Terverifikasi:** lokasi ya; penyebab backend belum terverifikasi

#### G1-13 [T] · pola P-12
Control Tower: “Piutang Lewat Tempo Rp 0” & panel “Tidak ada tagihan lewat tempo 🎉”, padahal layar Piutang “JATUH TEMPO Rp 1.193.250” (telat 1 hari); “Belum Lunas Rp 79,5 jt” vs Piutang “Rp 407,9 jt”.

- **Lokasi layar / jalur klik:** Beranda admin (Control Tower) vs Keuangan › AR / Piutang & Umur (admin-home #1 vs ar-aging #2).
- **Berkas:baris:** `frontend/src/features/home/AdminHome.jsx:69,131-132,267`; `backend/services/home_service.py:380-415`
- **Perbaikan:** (1) Investigasi `overdue_total` papan sales (kemungkinan masa tenggang/ cakupan pelanggan ber-sales) — bila bug, perbaiki; (2) apa pun hasilnya, sub-teks KPI menyebut cakupan & sumber (“pelanggan dengan sales · sub-buku”) dan tautan ke layar Piutang. Definisi utama → K-01.
- **Cek:** Lewat tempo tidak 0 selama ada tagihan telat; KPI menyebut cakupannya.
- **Terverifikasi:** lokasi ya; penyebab belum terverifikasi

#### G1-14 [S] · pola P-06
Format persen & sumbu keuangan campur: “32.4%” vs “32,4%”, “0.00%”, “26.72%”, sumbu “150.0 jt”/“1.4 M”/“900.0 jt”, “383.4 jt”, “Rp0”.

- **Lokasi layar / jalur klik:** BI Keuangan, Dasbor Keuangan, Laporan Keuangan (Laba-Rugi), Pusat Amandemen (Dampak), Margin & HPP, Profitabilitas, Proyeksi Arus Kas.
- **Berkas:baris:** `frontend/src/features/finance/financeShared.jsx:26-37`; `frontend/src/features/finance/BiFinanceView.jsx:37-39,99,234`; `frontend/src/features/finance/FinanceTowerView.jsx:76`; `frontend/src/features/finance/FinancialStatementsView.jsx:157,235-236`; `frontend/src/features/finance/amendments/AmendmentImpactCard.jsx:46`; `frontend/src/features/costing/CostingView.jsx:18-20`; `frontend/src/features/finance/ProfitabilityView.jsx`; `frontend/src/features/finance/CashFlowForecastView.jsx`
- **Perbaikan:** Ubah `compactIDR`/`fmtPct` di financeShared ke id-ID (tanpa “.0”), hapus salinan lokal di BiFinanceView, pakai fmtPctId/`formatPct` (G0-14) untuk semua persen; badge margin 2 desimal → 1 desimal koma.
- **Cek:** Tidak ada titik desimal pada persen/sumbu di layar keuangan; “32,4%” konsisten di KPI & kartu rasio.
- **Terverifikasi:** ya

#### G1-15 [S] · pola P-06
Tanggal ISO mentah/format campur di keuangan: “2026-10-01 s/d 2026-10-31”, “Neraca Konsolidasi per 2026-10-25”, “Efektif 2026-10-25”, GL “25 Okt 26” vs “22 Okt 2026” vs “2026-10-23”, opsi “Ubah jadwal 2026-11-08”, periode “2026-10”.

- **Lokasi layar / jalur klik:** Laporan Keuangan, Konsolidasi, Buku Besar (Jurnal/Suspense/true-up), Rencana Pembayaran › Putuskan.
- **Berkas:baris:** `frontend/src/features/finance/FinancialStatementsView.jsx:212`; `frontend/src/features/finance/GroupConsolidationView.jsx:226,237`; `frontend/src/features/finance/GeneralLedger.jsx`; `frontend/src/features/finance/SuspensePanel.jsx`; `frontend/src/features/finance/InventoryReconTab.jsx`; `frontend/src/features/finance/payments/PaymentVarianceDialog.jsx`
- **Perbaikan:** Semua tanggal tampilan lewat `formatDate`/`formatDateTime` (utils/formatters, sudah ada); periode lewat `formatPeriod` (G0-14).
- **Cek:** Layar-layar tersebut memakai format “25 Okt 2026”.
- **Terverifikasi:** ya

#### G1-16 [S] · pola P-01
Aksi berdampak keuangan tanpa dialog konfirmasi: Sinkron Pasangan Jurnal & Sinkron Antar-PT (konsolidasi), Sinkronkan (GL), Jalankan pengingat sekarang (kontrabon), Pindai temuan (kasus keuangan), Tutup yang kedaluwarsa (Buka Periode; aktif walau 0 jendela), Ulang Posting (Posting Gagal), ganti akun/aktif kategori beban (langsung PATCH tanpa simpan).

- **Lokasi layar / jalur klik:** consolidation #22/#24; general-ledger #56; contra-bons #34; finance-cases #39; period-unlock #156; posting-failures; expense-categories #7–#12.
- **Berkas:baris:** `frontend/src/features/finance/GroupConsolidationView.jsx:111-130`; `frontend/src/features/finance/GeneralLedger.jsx (sync)`; `frontend/src/features/purchasing/contrabon/ExchangeSchedulesTab.jsx:60-63`; `frontend/src/features/finance/cases/FinanceCasesView.jsx:169-171,205`; `frontend/src/features/finance/PeriodUnlockView.jsx:164,191-193`; `frontend/src/features/finance/PostingFailuresView.jsx`; `frontend/src/features/pettycash/ExpenseCategoriesView.jsx:49-52,96-108`
- **Perbaikan:** Bungkus tiap aksi dengan `askConfirm` (judul menyebut objek & akibat; danger untuk yang membuat/ membalik jurnal); Tutup yang kedaluwarsa nonaktif bila jendela aktif 0; kategori beban: ubah ke mode sunting baris dengan Simpan/Batal (atau askConfirm saat ganti akun).
- **Cek:** Setiap tombol di daftar memunculkan dialog aplikasi; Batal tidak mengirim permintaan (cek tab Network).
- **Terverifikasi:** ya untuk konsolidasi/kontrabon/kasus/Buka Periode/kategori beban; baris tombol Sinkronkan GL & Ulang Posting belum dipastikan

#### G1-17 [S]
Pusat Amandemen › rincian perubahan sulit dibaca: “Stok sendiri ~~Kekurangan~~ → 1,35” (teks lama vs angka baru tanpa satuan), dampak “↗ Rp 0”, “0.00% dari nilai dokumen”.

- **Lokasi layar / jalur klik:** Koreksi & Amandemen › detail KSC/AMD-00022 (amendments #11).
- **Berkas:baris:** `frontend/src/features/finance/amendments/AmendmentChangeList.jsx:36-44`; `frontend/src/features/finance/amendments/AmendmentImpactCard.jsx:46`
- **Perbaikan:** `renderValue` menampilkan nilai lama & baru dengan jenis & satuan yang sama (mis. “Kekurangan 0 yard → 1,35 yard”); sembunyikan panah/arah bila dampak 0; persen id-ID.
- **Cek:** Rincian menulis kedua nilai dengan satuan; dampak 0 tanpa panah.
- **Terverifikasi:** ya

#### G1-18 [S]
Rekonsiliasi Bank: pemilih rekening memuat akun nonaktif tanpa tanda (dua “TEST_Bank Updated” kembar).

- **Lokasi layar / jalur klik:** Kas & Bank › Rekonsiliasi Bank Otomatis › pemilih akun (bank-reconciliation #9).
- **Berkas:baris:** `frontend/src/features/finance/BankReconciliationView.jsx:130,153`
- **Perbaikan:** Saring akun nonaktif (atau label “(nonaktif)” & urut paling bawah).
- **Cek:** Daftar hanya rekening aktif / nonaktif ditandai.
- **Terverifikasi:** ya

#### G1-19 [S]
Anggaran: kartu “Komitmen Tanpa Anggaran” menulis “1-1300 · akun” tanpa nama akun; KPI “KOMITMEN Rp 0” sementara kartu memuat Rp 148.000.000.

- **Lokasi layar / jalur klik:** Keuangan › Anggaran vs Realisasi (budget #4/#6).
- **Berkas:baris:** `frontend/src/features/finance/BudgetParts.jsx:292-300`; `frontend/src/features/finance/BudgetView.jsx:68,122`
- **Perbaikan:** Tampilkan “1-1300 · Persediaan” (nama dari data/ COA); KPI komitmen ikut menghitung komitmen tanpa anggaran atau sub-teks “+ Rp 148 jt di luar pagu”.
- **Cek:** Kartu menampilkan nama akun; KPI tidak bertentangan dengan kartu.
- **Terverifikasi:** nama akun ya; logika KPI belum terverifikasi

#### G1-20 [S] · pola P-01
Transaksi Kas: dialog “Anulir KSC/CASH-00078” (penerimaan pelunasan AR) tidak meminta alasan dan tidak menyebut dampak ke piutang.

- **Lokasi layar / jalur klik:** Kas & Bank › Transaksi Kas › ikon ⊘ baris KSC/CASH-00078 (cash-management #9).
- **Berkas:baris:** `frontend/src/features/purchasing/CashManagementView.jsx:42,95,287-289`
- **Perbaikan:** Ganti ke `askReason({danger:true, message:'Pelunasan KSC/AR-00043 (Toko Kain Sejahtera) akan dibalik; piutangnya terbuka lagi.'})` dan kirim alasan ke `POST /cash-transactions/{id}/void` (backend/routers/cash.py:189-191 — tambahkan penerimaan & pencatatan `reason` bila belum ada).
- **Cek:** Anulir meminta alasan wajib & menyebut dokumen yang terdampak.
- **Terverifikasi:** ya

#### G1-21 [S] · pola P-05
Proyeksi Arus Kas: tabel “Piutang (AR) Jatuh Tempo” bergulir samping di 1440 (min-w-[460px]) sehingga kolom JATUH TEMPO tersembunyi.

- **Lokasi layar / jalur klik:** Keuangan › Proyeksi Arus Kas (cashflow-forecast #30).
- **Berkas:baris:** `frontend/src/features/finance/CashFlowForecastView.jsx:90-91,109`
- **Perbaikan:** Hapus `min-w-[460px]` / kolom nama `truncate` agar 4 kolom muat seperti tabel AP.
- **Cek:** Kolom JATUH TEMPO terlihat tanpa gulir di 1440.
- **Terverifikasi:** ya

#### G1-22 [S]
Bagan Akun: pop-up “Ubah Akun 1-0000/2-0000” (akun kelompok) menampilkan “Akun aktif (dapat dijurnal)”, padahal detail “Kelompok (tidak dijurnal)”.

- **Lokasi layar / jalur klik:** Bagan Akun › ikon pensil baris 1-0000 / 2-0000 (chart-of-accounts #12/#15).
- **Berkas:baris:** `frontend/src/features/finance/ChartOfAccounts.jsx:388,459`
- **Perbaikan:** Label checkbox mengikuti `is_postable`: kelompok → “Akun aktif”; detail → “Akun aktif (dapat dijurnal)”.
- **Cek:** Ubah 1-0000 tidak lagi menyebut “dapat dijurnal”.
- **Terverifikasi:** ya

#### G1-23 [S] · pola P-02
Kontrabon › tab GR Belum Ditagih: teks mentah “status completed” & “tugas gudang 245183” (potongan id); rincian “BELUM DITAGIH 200” tanpa satuan.

- **Lokasi layar / jalur klik:** Kontrabon › tab GR Belum Ditagih (contra-bons #28/#31).
- **Berkas:baris:** `frontend/src/features/purchasing/contrabon/UnbilledReceiptsTab.jsx:40,89,95`
- **Perbaikan:** `docStatusLabel(r.po_status)`; tampilkan nomor GRN/ tugas (nomor dokumen) alih-alih potongan id; satuan pada semua qty.
- **Cek:** Baris GR berbunyi “PO Selesai · KSC/GRN-…”.
- **Terverifikasi:** ya

#### G1-24 [S]
Kontrabon: “+ Buat kontrabon” dari baris GR (faktur belum datang) membuka wizard langkah 2 yang buntu (“Tagihan harus berstatus “posted”…”), supplier terpilih tak tampil; tombol “Kembali” sudah tampil di langkah 1.

- **Lokasi layar / jalur klik:** Kontrabon › GR Belum Ditagih › Buat kontrabon (contra-bons #30); Kontrabon baru (#26).
- **Berkas:baris:** `frontend/src/features/purchasing/contrabon/UnbilledReceiptsTab.jsx:110-111`; `frontend/src/features/purchasing/contrabon/ContraBonCreateWizard.jsx:258-262,437`
- **Perbaikan:** Dari baris GR tanpa tagihan: tombol jadi “Catat tagihan supplier” (ke Vendor Bill) atau sembunyikan; teks “berstatus Terposting”; tampilkan supplier terpilih di kepala langkah; sembunyikan “Kembali” di langkah 1.
- **Cek:** Tidak ada jalur yang berakhir di langkah buntu; langkah 1 tanpa tombol Kembali.
- **Terverifikasi:** ya

#### G1-25 [S] · pola P-01
Aset Tetap: “Simpan Aset” aktif walau Nama & Harga Perolehan (wajib) kosong; “Jalankan Penyusutan” langsung POST tanpa konfirmasi periode/jumlah dan tetap aktif saat 0 aset.

- **Lokasi layar / jalur klik:** Keuangan › Aset Tetap › Tambah Aset / Jalankan Penyusutan (fixed-assets #70/#72).
- **Berkas:baris:** `frontend/src/features/finance/FixedAssetsParts.jsx:80,187`; `frontend/src/features/finance/FixedAssetsView.jsx:126-131,219`
- **Perbaikan:** disabled bila nama/harga kosong; `askConfirm` “Jalankan penyusutan Oktober 2026 untuk N aset (jurnal Rp …)?”; nonaktif bila 0 aset.
- **Cek:** Simpan nonaktif sampai wajib terisi; penyusutan meminta konfirmasi & nonaktif tanpa aset.
- **Terverifikasi:** ya

#### G1-26 [S]
Buku Besar: KPI “TOTAL JURNAL 562” vs “563 jurnal” di daftar; filter “Semua sumber” hanya Manual/Penjualan/Kas padahal ada sumber lain; detail jurnal memuat “Payment Voucher” dan “Received Voucher” (keduanya untuk jurnal “Kas in”).

- **Lokasi layar / jalur klik:** Buku Besar › Jurnal (general-ledger #53/#55/#57).
- **Berkas:baris:** `frontend/src/features/finance/GeneralLedger.jsx:25-60,153,251,263,410-411`
- **Perbaikan:** KPI & daftar dari hitungan yang sama (atau sub-teks yang dikecualikan); opsi sumber dari peta SOURCE (baris 25-60) / data; tombol cetak “Bukti Kas Masuk”/“Bukti Kas Keluar” sesuai arah kas saja.
- **Cek:** KPI = jumlah di kaki tabel; filter memuat semua sumber yang tampil; hanya satu tombol bukti kas.
- **Terverifikasi:** lokasi ya; selisih 562/563 belum terverifikasi

#### G1-27 [S] · pola P-11
Buku Besar › Suspense: “Reklasifikasi” aktif tanpa akun tujuan; galat validasi tampil sebagai pita merah halaman dengan “Coba lagi”; NOMINAL mentah “12000000”.

- **Lokasi layar / jalur klik:** Buku Besar › tab Suspense › Reklasifikasi (general-ledger #65/#69).
- **Berkas:baris:** `frontend/src/features/finance/SuspensePanel.jsx:23,50,66-68,131`
- **Perbaikan:** Tombol nonaktif sampai akun dipilih; galat di bawah isian AKUN TUJUAN; nominal pakai MoneyInput/format id-ID.
- **Cek:** Tidak ada pita galat halaman untuk validasi isian.
- **Terverifikasi:** ya

#### G1-28 [S] · pola P-02
Pemetaan Akun: baris diperluas menampilkan kunci internal “Kode kebutuhan: kas_bank.kas_besar”; label kebutuhan campur Inggris (landed cost, GR/IR, customer, petty cash, store credit, cutloss).

- **Lokasi layar / jalur klik:** Pengaturan › Pemetaan Akun (gl-account-mappings #21/#34/#42).
- **Berkas:baris:** `frontend/src/features/finance/glmapping/MappingRow.jsx:48`; `backend/services/gl_mapping_registry.py:43-120`
- **Perbaikan:** Hapus baris kode (atau pindah ke `title`); label registri Indonesia (istilah baku mengikuti glosarium K-13).
- **Cek:** Baris pemetaan tidak memuat kunci titik-titik.
- **Terverifikasi:** ya

#### G1-29 [S] · pola P-01
Antar-PT: “Konfirmasi” baris (jurnal terbit di kedua buku) langsung POST; pop-up batal untuk dokumen Draf bertombol “Batalkan & Balik Jurnal” padahal belum ada jurnal.

- **Lokasi layar / jalur klik:** Antar Entitas › baris KSC/IC-00007 › Konfirmasi / ikon ↺ (interco #32/#33).
- **Berkas:baris:** `frontend/src/features/finance/interco/IntercoView.jsx:151-172`; `frontend/src/features/finance/interco/IntercoCancelModal.jsx:104`
- **Perbaikan:** `askConfirm` sebelum `confirm` (sebut nominal & dua PT); label tombol batal “Batalkan draf” bila status draft.
- **Cek:** Konfirmasi memunculkan dialog; batal draf tidak menyebut balik jurnal.
- **Terverifikasi:** ya

#### G1-30 [S] · pola P-11
Antar-PT (form): daftar PT lawan memuat PT sendiri (Sukacita) di urutan pertama; “Terbitkan” aktif walau PT/Produk kosong; baris barang tanpa kepala kolom; “Perkiraan subtotal … (final dihitung backend)”; centang “Langsung dikonfirmasi (post jurnal…)” tercentang bawaan.

- **Lokasi layar / jalur klik:** Antar Entitas › Transaksi Baru / Kontrak Internal / Buat Settlement / Pinjaman Baru (interco #29/#30/#35/#46).
- **Berkas:baris:** `frontend/src/features/finance/interco/IntercoSettlementModal.jsx:32,63,111`; `frontend/src/features/finance/interco/InternalContractWizardModal.jsx:40-41,104`; `frontend/src/features/finance/interco/IntercoLoansPanel.jsx:229-230,269`; `frontend/src/features/finance/interco/IntercoCreateModal.jsx:26,177`
- **Perbaikan:** Kecualikan PT pemberi/pembayar dari opsi lawan; tombol utama nonaktif sampai isian wajib lengkap; kepala kolom Produk/Qty/Harga; “(final dihitung sistem)”; bawaan centang mengikuti keputusan K-10 (usulan: tidak tercentang).
- **Cek:** PT sendiri tidak muncul sebagai lawan; tombol nonaktif pada form kosong.
- **Terverifikasi:** ya

#### G1-31 [S] · pola P-12
Antar-PT: angka utang Sukacita → Cipta Sandang berbeda antar tab (KPI & Saldo Rp 7.015.200 umur 0 hari vs Jadwal Bayar Rp 6.993.000 umur 3 hari); KPI “DOKUMEN TERBUKA 1” padahal 4 transaksi belum lunas; nomor transaksi berganti KSC/IC (Daftar) vs CST/IC (Jadwal, Rapor).

- **Lokasi layar / jalur klik:** Antar Entitas › KPI kepala, tab Saldo Antar-PT, Jadwal Bayar, Daftar (interco #27/#38/#40).
- **Berkas:baris:** `backend/services/interco_service.py:1159 (payment_schedule)`; `backend/services/interco_money_service.py (summary)`; `frontend/src/features/finance/interco/IntercoPaymentSchedule.jsx`; `frontend/src/features/finance/interco/IntercoMarginPanel.jsx`
- **Perbaikan:** Investigasi basis (netting dua arah vs per dokumen; draf tidak dihitung) lalu beri label sumber di tiap angka; nomor dokumen selalu dari sudut pandang entitas aktif. Bila beda definisi → K-07.
- **Cek:** Angka yang sama-sama berlabel “utang” cocok, atau masing-masing menyebut dasar hitungnya.
- **Terverifikasi:** belum terverifikasi (logika backend)

#### G1-32 [S] · pola P-01
Retur Antar-PT: “Setujui” (menerbitkan nota retur + nota kredit di dua buku) langsung POST; sub-tab “Retur Antar-PT” vs “Retur Masuk” (nama sama dengan judul halaman); NOMOR patah 2 baris, BARANG hanya kode SKU, teks “belum dikirim balik” #C9C9CE nyaris tak terbaca; tab Retur Masuk tanpa kartu.

- **Lokasi layar / jalur klik:** Antar Entitas › Retur Antar-PT › baris KSC/ICR-00016 › Setujui; tab Retur Masuk (interco-returns #72/#74/#77).
- **Berkas:baris:** `frontend/src/features/finance/interco/IntercoView.jsx:47-48,331`; `frontend/src/features/finance/interco/IntercoReturnsPanel.jsx:102,146,153-157`; `frontend/src/features/finance/interco/IntercoReturnInbox.jsx:88`
- **Perbaikan:** `askConfirm` sebelum approve; sub-tab “Retur Keluar” / “Retur Masuk”; nomor `whitespace-nowrap`; tampilkan nama barang + SKU kecil; warna teks sekunder #6B6B73; bungkus Retur Masuk dalam section-card.
- **Cek:** Setujui memunculkan dialog; kolom terbaca tanpa patah.
- **Terverifikasi:** ya

#### G1-33 [S]
Konsolidasi: entri eliminasi mengkredit Piutang IC Rp 7.023.414 & Persediaan Dalam Perjalanan Rp 70.000, melebihi saldo IC (Rp 6.995.442 / Rp 32.200) sehingga akun IC tidak nol setelah konsolidasi.

- **Lokasi layar / jalur klik:** Konsolidasi › Eliminasi vs Deteksi Otomatis (consolidation #21 vs #25).
- **Berkas:baris:** `backend/services/consolidation_service.py:448-520 (eliminasi G-6)`
- **Perbaikan:** Telusuri pembentukan entri eliminasi otomatis (kemungkinan entri ganda per sinkron/ retur belum dikurangi); tambah uji: setelah eliminasi saldo IC konsolidasi = 0.
- **Cek:** Neraca konsolidasi: akun 1-1250/1-1310 = 0 setelah eliminasi.
- **Terverifikasi:** belum terverifikasi (logika)

#### G1-34 [S] · pola P-11
Konsolidasi › Tambah Eliminasi: ENTITAS DARI/KE bernilai “—” tanpa placeholder; baris jurnal tanpa kepala kolom (hanya placeholder); tanpa penanda wajib; status “Belum balanced”.

- **Lokasi layar / jalur klik:** Konsolidasi › Eliminasi › Tambah Eliminasi (consolidation #23).
- **Berkas:baris:** `frontend/src/features/finance/GroupConsolidationView.jsx:348,386-387,399-402,410`
- **Perbaikan:** Placeholder “Pilih badan usaha”; kepala kolom Akun/Debit/Kredit/Keterangan; * pada isian wajib; “Belum seimbang”.
- **Cek:** Form dapat dibaca tanpa menebak kolom.
- **Terverifikasi:** ya

#### G1-35 [S] · pola P-05
Pusat Kasus Keuangan: tabel dalam panel setengah lebar `overflow-hidden` memotong kolom PENANGGUNG JAWAB & aksi; nomor “KSC/CASE-00001” patah; filter jenis menggeser isi.

- **Lokasi layar / jalur klik:** Keuangan › Pusat Kasus Keuangan (finance-cases #38/#43).
- **Berkas:baris:** `frontend/src/features/finance/cases/CaseInboxTable.jsx:43-55`; `frontend/src/features/finance/cases/FinanceCasesView.jsx:316`
- **Perbaikan:** `overflow-x-auto` + nomor `whitespace-nowrap`, atau grid `xl:grid-cols-[3fr_2fr]`.
- **Cek:** Semua kolom & aksi terlihat di 1440.
- **Terverifikasi:** ya

#### G1-36 [S] · pola P-11
Laporkan kasus keuangan: tanpa penanda wajib; “Buat kasus” aktif dengan isian kosong; nominal 0 bawaan; daftar pelanggan hanya nama sehingga nama kembar (QA Cust A/B ×2) tak bisa dibedakan.

- **Lokasi layar / jalur klik:** Pusat Kasus Keuangan › Kasus baru › Pilih pelanggan (finance-cases #40/#41).
- **Berkas:baris:** `frontend/src/features/finance/cases/CaseCreateModal.jsx:34-36,93,137-139`
- **Perbaikan:** Label opsi “Nama · CUST-xxxx · Kota”; * pada isian wajib; tombol nonaktif sampai valid.
- **Cek:** Pelanggan kembar bisa dibedakan; tombol nonaktif pada form kosong.
- **Terverifikasi:** ya

#### G1-37 [S]
Faktur Pajak Masukan › Catat: isian NSFP/Tanggal/Kode Transaksi tetap bisa diisi saat tidak ada tagihan (tombol pasti mati); pesan “Posting tagihannya dulu…” tanpa tautan.

- **Lokasi layar / jalur klik:** Faktur Masukan › Catat Faktur Masukan (input-tax #88).
- **Berkas:baris:** `frontend/src/features/purchasing/InputTaxCreateModal.jsx:53-75,112`
- **Perbaikan:** Bila tidak ada tagihan: sembunyikan/disable isian dan tampilkan tautan “Buka Tagihan Supplier”.
- **Cek:** Tanpa tagihan, form tidak bisa diisi dan ada tautan jalan keluar.
- **Terverifikasi:** ya

#### G1-38 [S]
Dasbor Keuangan: panel “Hutang Terbesar” per tagihan (CV Printing Sablon Cimahi muncul 4×) padahal “Piutang Terbesar” per pelanggan.

- **Lokasi layar / jalur klik:** Keuangan › Dasbor Keuangan (finance-tower #20).
- **Berkas:baris:** `frontend/src/features/finance/FinanceTowerParts.jsx:139-152`
- **Perbaikan:** Kelompokkan per pemasok (jumlah + “N tagihan”), seperti panel piutang.
- **Cek:** Setiap pemasok muncul sekali.
- **Terverifikasi:** ya

#### G1-39 [S]
Profitabilitas: kartu “HPP (saat kirim) — tanpa landed cost” bertentangan dengan catatan tabel “…termasuk landed cost”.

- **Lokasi layar / jalur klik:** Keuangan › Profitabilitas & Margin (profitability #183).
- **Berkas:baris:** `frontend/src/features/finance/ProfitabilityView.jsx:76,169-188`
- **Perbaikan:** Satu kalimat mengikuti `tot.landed_included` di kartu & catatan kaki.
- **Cek:** Kartu dan catatan kaki menyatakan hal yang sama.
- **Terverifikasi:** ya

#### G1-40 [S]
PPh & Rekap Pajak: judul kartu “PPh & Rekap Pajak” padahal tab bawaan “PPN (SPT Masa)”; tab PPh “0 payroll run (PPh21 aktual/TER)”; angka PPh ungu sedangkan PPN hitam.

- **Lokasi layar / jalur klik:** Akuntansi & Pajak › PPh & Rekap Pajak (cs-pajak #19/#21).
- **Berkas:baris:** `frontend/src/features/finance/TaxCenterView.jsx:35,81,247,259,281,296`; `backend/services/tax_center_service.py:104`
- **Perbaikan:** Judul kartu “Pajak (PPN & PPh)” (judul kepala di G0-17); teks “0 penggajian terposting (PPh 21 tarif efektif/TER)”; angka hitam.
- **Cek:** Judul sesuai isi; tidak ada “payroll run”.
- **Terverifikasi:** ya

#### G1-41 [S]
LPJ Baru: tanggal baris pengeluaran terpotong “Min, 25 Okt…” (kolom 120 px) sehingga tahun tak terlihat.

- **Lokasi layar / jalur klik:** Kas & Petty Cash › Pertanggungjawaban (LPJ) › LPJ Baru (settlements #209).
- **Berkas:baris:** `frontend/src/features/pettycash/SettlementForm.jsx:106-111`
- **Perbaikan:** Kolom tanggal ≥ 150 px atau format pendek “25/10/26” di KNDatePicker baris.
- **Cek:** Tanggal terbaca lengkap.
- **Terverifikasi:** ya

#### G1-42 [S] · pola P-11
Label Alasan Amandemen: form tambah tanpa label (placeholder sebagai label) dan placeholder terpotong “Kode singkat, mis. sal”.

- **Lokasi layar / jalur klik:** Pengaturan › Label Alasan Amandemen (amendment-reasons #1).
- **Berkas:baris:** `frontend/src/features/finance/amendments/AmendmentReasonsPanel.jsx:131-133`
- **Perbaikan:** Label di atas isian (“Kode”, “Nama”, “Penjelasan”), placeholder pendek.
- **Cek:** Isian berlabel dan placeholder tidak terpotong.
- **Terverifikasi:** ya

#### G1-43 [S]
Control Tower di HP: kartu KPI tidak muat (“Rp / 4.292.925” patah, angka menyentuh tepi).

- **Lokasi layar / jalur klik:** HP admin › Ringkas › Buka Tampilan Desktop (hp-admin-ringkas #10).
- **Berkas:baris:** `frontend/src/features/home/AdminHome.jsx:17-36`
- **Perbaikan:** Angka `text-xl md:text-2xl whitespace-nowrap`; grid 1 kolom < 400px.
- **Cek:** Di 390 angka Rp satu baris dan tidak menyentuh tepi.
- **Terverifikasi:** ya

#### G1-44 [S]
Tautan “Tugas gudang terbuka > 2 hari · 25” (Terlambat Hari Ini) membuka Operasi Gudang tab Stok, bukan daftar tugas terbuka.

- **Lokasi layar / jalur klik:** Dasbor Manajer › Terlambat Hari Ini › Tugas gudang terbuka (hp-manager-ringkas #29).
- **Berkas:baris:** `backend/services/home_service.py:320`
- **Perbaikan:** Arahkan ke tampilan tugas gudang yang benar (cek id view/tab di config/viewAlias & hubTabs — mis. view tugas WMS/ barang masuk dengan saringan terbuka) tanpa mengubah berkas config (milik G0).
- **Cek:** Klik baris membuka daftar tugas gudang terbuka.
- **Terverifikasi:** lokasi ya; id view tujuan belum dipastikan

#### G1-45 [R] · pola P-04
Pusat Amandemen: lencana “Daftar Amandemen” ikut filter status (22→0) sementara KPI total tetap; lencana “DITERAPKAN OTOMATIS” patah 2 baris.

- **Lokasi layar / jalur klik:** Koreksi & Amandemen › tab status (amendments #10/#12).
- **Berkas:baris:** `frontend/src/features/finance/amendments/AmendmentCenterView.jsx:130`
- **Perbaikan:** Lencana memakai `stats.total`; lencana status `whitespace-nowrap`.
- **Cek:** Lencana tetap 22 di semua tab status.
- **Terverifikasi:** ya

#### G1-46 [R]
Buku Besar › Rekonsiliasi: judul “TRUE-UP TERAKHIR (5 JURNAL)” padahal 3 baris; dialog true-up tanpa nominal/entitas; “Kenapa berselisih?” di baris selisih 0; Jurnal Manual kosong menampilkan “Selisih Rp 0” merah.

- **Lokasi layar / jalur klik:** Buku Besar › Rekonsiliasi Persediaan; Jurnal Baru (general-ledger #54/#62/#63).
- **Berkas:baris:** `frontend/src/features/finance/InventoryReconTab.jsx:384`; `frontend/src/features/finance/JournalEntryModal.jsx:148-149`
- **Perbaikan:** Judul = jumlah baris; dialog menyebut Rp & badan usaha; sembunyikan tombol bila selisih 0; lencana netral saat 0.
- **Cek:** Judul & lencana sesuai isi.
- **Terverifikasi:** ya

#### G1-47 [R]
Pemetaan Akun: “Alasan perubahan (wajib)” bukan *, placeholder sama untuk semua akun, riwayat tidak menyebut akun, klik “BELUM DIATUR 0” → “Tidak ada baris yang cocok.”

- **Lokasi layar / jalur klik:** Pemetaan Akun (gl-account-mappings #22–#24).
- **Berkas:baris:** `frontend/src/features/finance/glmapping/MappingEditDialog.jsx:32-35`; `frontend/src/features/finance/glmapping/MappingHistory.jsx:13`; `frontend/src/features/finance/GLAccountMappingView.jsx:72,89-92`
- **Perbaikan:** * pada label; placeholder per kebutuhan; judul riwayat menyebut kebutuhan; kartu 0 nonaktif atau pesan “Semua kebutuhan sudah diatur”.
- **Cek:** Tidak ada pesan kosong menyesatkan.
- **Terverifikasi:** ya

#### G1-48 [R]
Rekening & Saldo: akun nonaktif tidak diredupkan, “Bank · - · nonaktif” (tanda “-” kosong), ikon KPI lingkaran kosong, rekening BCA berlencana “Kas besar”; pop-up Tambah Akun menyisipkan SALDO AWAL di antara Jenis dan detail bank.

- **Lokasi layar / jalur klik:** Kas & Bank › Rekening & Saldo (bank-accounts #15/#16).
- **Berkas:baris:** `frontend/src/features/finance/BankAccountsView.jsx:207`
- **Perbaikan:** Redupkan nonaktif, sembunyikan bagian kosong, ikon KPI, lencana sesuai jenis, urutan isian Jenis → Bank → No. Rek → Saldo awal.
- **Cek:** Kartu & form rapi sesuai daftar.
- **Terverifikasi:** ya

#### G1-49 [R]
Grafik garis `type="monotone"` membentuk lengkung semu antar bulan.

- **Lokasi layar / jalur klik:** BI Keuangan (Laba Bersih), Proyeksi Arus Kas.
- **Berkas:baris:** `frontend/src/features/finance/BiFinanceView.jsx:152`; `frontend/src/features/finance/CashFlowForecastView.jsx:83`
- **Perbaikan:** `type="linear"`.
- **Cek:** Garis lurus antar titik.
- **Terverifikasi:** ya

#### G1-50 [R]
Laporan Keuangan › Perubahan Ekuitas: “3-2900 Ekuitas Saldo Awal” tampil SALDO AWAL Rp 0 & seluruh nilai sebagai pergerakan; label sumbu-X terpotong.

- **Lokasi layar / jalur klik:** Laporan Keuangan › tab Perubahan Ekuitas (financial-statements #24).
- **Berkas:baris:** `frontend/src/features/finance/EquityChangesTab.jsx:103`
- **Perbaikan:** Saldo awal ekuitas dari akun 3-2900 dimasukkan ke kolom saldo awal (cek layanan laporan); label sumbu `angle`/`tickFormatter` pendek.
- **Cek:** Ekuitas awal ≠ 0 bila ada saldo awal.
- **Terverifikasi:** belum terverifikasi (logika)

#### G1-51 [R]
AR / Piutang: KPI “JATUH TEMPO (0%)” untuk Rp 1.193.250 (pembulatan); placeholder cari Uang Muka terpotong “Cari pelanggan / no. pesa”.

- **Lokasi layar / jalur klik:** ar-aging #2; advance-report #1.
- **Berkas:baris:** `frontend/src/features/finance/ARAgingView.jsx:131`; `frontend/src/features/finance/AdvanceReportView.jsx:72`
- **Perbaikan:** Persen < 1 tampil “<1%”; placeholder pendek “Cari pelanggan/pesanan”.
- **Cek:** Tidak ada “0%” untuk nilai > 0.
- **Terverifikasi:** ya

#### G1-52 [R]
Margin & HPP: ikon KPI “MARGIN RENDAH” sama dengan “TANPA BIAYA”; lencana 28% oranye peringatan.

- **Lokasi layar / jalur klik:** Analitik › Margin & HPP (costing #18).
- **Berkas:baris:** `frontend/src/features/costing/CostingView.jsx:18-20,70-71`
- **Perbaikan:** Ikon berbeda; ambang warna sesuai kebijakan margin (oranye hanya di bawah target).
- **Cek:** Ikon unik; 28% tidak berwarna peringatan bila di atas target.
- **Terverifikasi:** ya

### G2 — Penjualan, CRM, harga, retur jual, POS, sample order + aplikasi HP Sales / Admin Sales

T 3 · S 24 · R 6

**Berkas milik grup (hanya grup ini yang boleh mengedit):**

- `frontend/src/features/sales/**  (KECUALI sales/mobile/MobileMdApp.jsx & MobileMdViews.jsx → G5, sales/mobile/MobilePwa.jsx → G0)`
- `frontend/src/features/crm/**`
- `frontend/src/features/pos/**`
- `frontend/src/features/orders/**`
- `frontend/src/features/sales_admin/**`
- `frontend/src/features/pricing/**`
- `frontend/src/features/samples/**`
- `frontend/src/features/desks/**`
- `backend/services/price_guard_service.py`
- `backend/services/customer_service.py`
- `backend/services/customer_price_service.py`

> MobileExtraViews.jsx (dipakai MD & Sales) milik G2. SoStatusBadges & LocationFields milik G0.

#### G2-01 [T] · pola P-05
Pop-up “Pelanggan Baru” (POS/HP) lebih tinggi dari layar 390×820: judul & tombol × terpotong di atas, “Batal”/“Buat Customer” terpotong di bawah (wadah `fixed inset-0 flex items-center` tanpa batas tinggi).

- **Lokasi layar / jalur klik:** HP Sales › Katalog › Pelanggan baru; Keranjang › Mulai Belanja › Pelanggan baru (hp-sales-katalog #46, keranjang #49).
- **Berkas:baris:** `frontend/src/features/pos/CreateCustomerModal.jsx:29-31`
- **Perbaikan:** Kartu `max-h-[calc(100dvh-2rem)] overflow-y-auto` dengan kepala & kaki `sticky`; overlay `items-start sm:items-center`.
- **Cek:** Di 390×820 judul, ×, Batal dan tombol simpan terlihat; isi digulir di dalam kartu.
- **Terverifikasi:** ya

#### G2-02 [T] · pola P-02
Pengajuan Harga Khusus (HP): “Rp 39 → Rp 1.234 (−-3064%)” — tanda minus ganda & arah salah untuk harga di atas normal; “diputus sistem (KLR-05)”; “min 0” / “min 0 yard”.

- **Lokasi layar / jalur klik:** HP MD › Lainnya › Pengajuan Harga Khusus; HP Sales › Harga Khusus Saya (hp-md-lainnya #4, hp-md-pengajuan-harga-khusus #140).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileExtraViews.jsx:50,54-55`
- **Perbaikan:** discount_percent > 0 → “(−X%)”; < 0 → “(+X% di atas harga normal)” warna berbeda; `stripInternalCodes(approved_by_name)` atau label “diputus sistem (kedaluwarsa)”; sembunyikan “min” bila 0.
- **Cek:** Baris DENIM TENCEL HITAM A menulis “(+3.064% di atas harga normal)”; tidak ada “KLR-05”.
- **Terverifikasi:** ya

#### G2-03 [T] · pola P-05
Tabel Pesanan Khusus (OD) dibuka di HP: kolom ke-3 dst. dan pager “Sebelumnya/Berikutnya” di luar layar (gulir samping), tab status patah 4 baris.

- **Lokasi layar / jalur klik:** HP admin › Ringkas › Buka Tampilan Desktop › Buka PO Custom → (hp-admin-ringkas #12).
- **Berkas:baris:** `frontend/src/features/sales/SpecialOrders.jsx:240`
- **Perbaikan:** Bungkus tabel dengan wadah `overflow-x-auto` yang TIDAK memuat pager (pager di bawah wadah, selebar layar); kolom nomor `sticky left-0`; di < 640px tampilkan versi kartu (nomor, pelanggan, nilai, status, aksi).
- **Cek:** Di 390 pager dan status terlihat tanpa gulir samping.
- **Terverifikasi:** ya

#### G2-04 [S] · pola P-12
Dasbor Pesanan: KPI “MENUNGGU 29 · Butuh persetujuan” menghitung waiting_approval+reserved+approved, sedangkan “Status Distribution › Menunggu Persetujuan 0”; layar penuh istilah Inggris (Monitoring & analytics, REVENUE, EXPIRING/Expires < 24h, Top Customers, Status Distribution, Recent Orders, DATE, “1 orders”, “ter-scope”); tanggal “24/10/2026”.

- **Lokasi layar / jalur klik:** Pesanan (SO) › Dasbor & Analitik (orders #138; HP sales #85).
- **Berkas:baris:** `frontend/src/features/orders/OrderDashboard.jsx:24,55,90,111,118-127,137,159,183-194,225`
- **Perbaikan:** KPI “Menunggu persetujuan” = waiting_approval saja (sama dengan distribusi) — atau ganti label sesuai isi (“Belum dikirim”); terjemahkan seluruh label; tanggal `formatDate`.
- **Cek:** Angka “Menunggu” sama di KPI & distribusi; tidak ada label Inggris.
- **Terverifikasi:** ya

#### G2-05 [S] · pola P-04
Pesanan: kartu & tab “BACKORDER 8 · Rp 1.110.000” tetapi daftar “Menampilkan 1–5 dari 5”; jumlah kartu status 376 ≠ TOTAL 373.

- **Lokasi layar / jalur klik:** Pesanan (SO) › tab Backorder 8 (orders #128/#144).
- **Berkas:baris:** `frontend/src/features/orders/OrdersView.jsx:52,162,253`
- **Perbaikan:** Hitungan kartu dari kriteria yang sama dengan daftar (has_backorder), atau keterangan “satu SO bisa di lebih dari satu status”.
- **Cek:** Kartu Backorder = jumlah baris daftar.
- **Terverifikasi:** lokasi ya; penyebab belum terverifikasi

#### G2-06 [S] · pola P-06
Pop-up detail SO: dua tombol tutup (× modal + ⊗ kartu), nomor & pelanggan ditulis dua kali, status “Dibatalkan · Dibatalkan”, tanggal ungu tanpa label “28/10/2026, 12.53.59”, tiga gaya tombol utama; Alokasi Stok “Single Lot 1,09” tanpa satuan & “1.09 dari Lot…” pada pesanan batal.

- **Lokasi layar / jalur klik:** Pesanan › KSC/SO-00505 › Lihat detail & aksi (orders #134/#150/#152).
- **Berkas:baris:** `frontend/src/features/orders/OrderDetailPanel.jsx:379-389`
- **Perbaikan:** Saat dibungkus modal sembunyikan ⊗ & kepala kartu ganda; status satu kali; tanggal berlabel + `formatDateTime`; satu gaya tombol utama; qty pakai formatQty + satuan; sembunyikan alokasi pada SO batal.
- **Cek:** Detail SO batal: satu tombol tutup, status sekali, tanpa alokasi aktif.
- **Terverifikasi:** ya

#### G2-07 [S]
Rencana pemenuhan: baris “Ambil dari stok sendiri” — petunjuk gudang panjang menurunkan isian qty + “maks” ke kiri bawah; isian qty tanpa satuan.

- **Lokasi layar / jalur klik:** Pesanan › Dipesan › KSC/SO-00405 › Rencana pemenuhan (orders #142).
- **Berkas:baris:** `frontend/src/features/sales_admin/FulfillmentLineCard.jsx:6-20`
- **Perbaikan:** `grid grid-cols-[1fr_auto]` (bukan flex-wrap) sehingga isian selalu di kanan; tampilkan satuan di samping isian.
- **Cek:** Semua baris rencana sejajar kanan dengan satuan.
- **Terverifikasi:** ya

#### G2-08 [S] · pola P-02
CRM › Riwayat 360°: kode mentah “KSC/SO-00505 · cancelled · pending”, “Default: TEMPO”, “Metode: tunai, tempo”; “1 order · LTV Rp 224.573” ikut menghitung pesanan batal.

- **Lokasi layar / jalur klik:** Pelanggan & CRM › klik QA Cust B (customers-crm #63).
- **Berkas:baris:** `frontend/src/features/crm/Customer360Panel.jsx:115-116,158,215`; `backend/services/customer_service.py:372`
- **Perbaikan:** Status via docStatusLabel/label bayar; metode bayar berlabel (Tunai, Tempo); `lifetime_value` & jumlah pesanan mengecualikan SO berstatus cancelled.
- **Cek:** Riwayat tanpa kata Inggris; LTV tidak memasukkan SO batal.
- **Terverifikasi:** ya

#### G2-09 [S] · pola P-11
CRM form pelanggan: “Edit Pelanggan” tanpa isian Alamat Toko; judul “Edit” vs tombol “Ubah”; label campur (Title Case, “Segment”, MAJUSCULE); Profil Pembayaran: lepas “Tempo” → Metode Default kosong, Termin 30 & DP 30% tetap tampil walau tidak dipakai.

- **Lokasi layar / jalur klik:** Pelanggan & CRM › Pelanggan Baru / detail › Ubah (customers-crm #58/#61/#64).
- **Berkas:baris:** `frontend/src/features/crm/CustomerFormModal.jsx:24,142,154,159-163,223-237,252-263`
- **Perbaikan:** Tampilkan Alamat Toko juga saat ubah; judul “Ubah Pelanggan”; label sentence case + “Segmen”; Metode Default otomatis pindah ke metode yang tersisa; Termin/DP hanya tampil bila opsinya dicentang. (Galat kode pos saat dibuka → G0-08.)
- **Cek:** Form ubah = form buat; isian yang tidak berlaku tersembunyi.
- **Terverifikasi:** ya

#### G2-10 [S] · pola P-11
CRM › Ajukan Override Kredit: tiga isian tanpa label; deskripsi memuat rujukan spesifikasi “(KN_17 §5.2)”; tombol di badan tanpa kaki; tetap ditawarkan untuk pelanggan “Tanpa limit / ∞”.

- **Lokasi layar / jalur klik:** Pelanggan › detail › Ajukan Override Kredit (customers-crm #68).
- **Berkas:baris:** `frontend/src/features/crm/Customer360Panel.jsx:94,305-315`
- **Perbaikan:** Label “Nilai pesanan”, “Alasan *”, “Tautan bukti (opsional)”; hapus “(KN_17 …)”; kaki Batal/Ajukan; sembunyikan tombol bila pelanggan tanpa limit.
- **Cek:** Pop-up berlabel; tidak muncul untuk pelanggan tanpa limit.
- **Terverifikasi:** ya

#### G2-11 [S] · pola P-13
Harga per Pelanggan: satu konsep dua nama (“Harga per Pelanggan/HARGA PELANGGAN” vs “Harga Langganan” di pop-up & kosong); banner kurung ganda “(harga PT & HPP (dipakai yang lebih tinggi))”.

- **Lokasi layar / jalur klik:** Penjualan › Harga per Pelanggan › Atur harga / Riwayat (cs-price-list #54–#56).
- **Berkas:baris:** `frontend/src/features/sales/customerPricelist/SetCustomerPriceModal.jsx:78,105`; `frontend/src/features/sales/customerPricelist/CustomerPriceParts.jsx:43-45`; `backend/services/price_guard_service.py:39`
- **Perbaikan:** Satu istilah (usulan “Harga Pelanggan”, ikuti K-13) di judul pop-up, label isian, kosong; label server tanpa kurung (“harga PT & HPP, dipakai yang lebih tinggi”).
- **Cek:** Layar & pop-up memakai satu istilah; banner tanpa kurung ganda.
- **Terverifikasi:** ya

#### G2-12 [S]
Pustaka Warna › “Buat Labdip” memindah pengguna ke halaman R&D dan membuka pop-up berjudul “R&D Produk Baru”; pop-up ubah berjudul “Edit Warna”; label “FAMILY/Semua Family”.

- **Lokasi layar / jalur klik:** Pustaka Warna › kartu KN-BLK-01 › Buat Labdip; ikon pensil (color-library #34/#37/#36).
- **Berkas:baris:** `frontend/src/features/sales/ColorLibraryView.jsx:100,195-203,292`
- **Perbaikan:** Buka SampleFormModal sebagai pop-up di layar Pustaka (tanpa setActiveView) dengan `lockType` labdip & warna terisi → judul “Sample Labdip Baru”; “Ubah Warna”; “Keluarga warna”. (Alur buntu handfeel ACC → G5-44.)
- **Cek:** Klik Buat Labdip: tetap di Pustaka Warna, pop-up berjudul Sample Labdip Baru dengan warna terisi.
- **Terverifikasi:** ya

#### G2-13 [S] · pola P-02
Meja Saya: lencana & chip “warning · 84”, “info · 14” (BADGE_LABEL tanpa warning/info/critical).

- **Lokasi layar / jalur klik:** Penjualan › Meja Saya (my-desk #119/#120).
- **Berkas:baris:** `frontend/src/features/sales_admin/workDeskApi.js:122,178-182`
- **Perbaikan:** Tambah warning→“Perlu perhatian”, info→“Info”, critical→“Mendesak”; fallback docStatusLabel. (Teks “tahap: …” dari server → G5-10.)
- **Cek:** Tidak ada lencana Inggris di Meja Saya.
- **Terverifikasi:** ya

#### G2-14 [S] · pola P-04
Persetujuan Harga Khusus: kaki pop-up “Ajukan” tiga tombol penuh sama besar; bukti wajib hanya lewat teks “(WAJIB SAAT DIAJUKAN)”; pemilih pelanggan memuat nama kembar tanpa kode/kota; semua kartu “Pengaju: —”; tab kosong berpesan “Belum ada pengajuan harga khusus.” walau ada 33.

- **Lokasi layar / jalur klik:** Inbox Persetujuan › Harga Khusus › Ajukan › Pilih Pelanggan; tab Menunggu/Draf (price-approvals #158–#162).
- **Berkas:baris:** `frontend/src/features/pricing/SpecialPriceRequestForm.jsx:127-133`; `frontend/src/features/sales/PriceApprovals.jsx:326-330,384`; `frontend/src/features/sales/priceApprovals/PriceApprovalCard.jsx:99`
- **Perbaikan:** Kaki: Batal kiri, Simpan Draf + Ajukan kanan; * pada bukti; opsi pelanggan “Nama · CUST-xxxx · Kota”; perbaiki sumber nama pengaju (field `requested_by_name` kosong — cek nama field dari API); pesan kosong per status (“Tidak ada pengajuan berstatus Menunggu”).
- **Cek:** Pengaju tampil; pelanggan kembar dapat dibedakan; pesan kosong spesifik.
- **Terverifikasi:** lokasi ya; sumber “Pengaju: —” belum terverifikasi

#### G2-15 [S] · pola P-12
Retur Pelanggan: grade roll bertentangan antar tab detail SRET-00005 (Ringkasan/SPK/Stok “A”, tab Logistik “GRADE B”); kondisi RL-31985-1 “Baik” vs tabel QC “Cacat ringan”.

- **Lokasi layar / jalur klik:** Retur Pelanggan & Barang Sisa › Detail → › tab Logistik & perjalanan (returns #194/#201/#203).
- **Berkas:baris:** `frontend/src/features/sales/ReturnDetail.jsx (tab logistik; ±160-380)`
- **Perbaikan:** Tampilkan grade dengan sumbernya (“grade awal A · QC aktual B”) di semua tab dari field yang sama; kondisi mengikuti hasil QC terakhir.
- **Cek:** Grade & kondisi roll sama di semua tab atau diberi label sumber.
- **Terverifikasi:** belum terverifikasi (sumber field)

#### G2-16 [S]
Retur Pelanggan: kolom STATUS memakai jenis penyelesaian (“Store Credit”) untuk retur selesai; filter “2 · Menunggu ACC (0)” vs KPI; kolom UMUR berisi “selesai”; menu filter sempit.

- **Lokasi layar / jalur klik:** Retur Pelanggan & Barang Sisa (returns #190/#215).
- **Berkas:baris:** `frontend/src/features/sales/ReturnShared.jsx:18-25`; `frontend/src/features/sales/SalesReturns.jsx:31-32,135`
- **Perbaikan:** Status “Selesai” + lencana kecil jenis (store credit/refund/nego); filter tanpa nomor urut; UMUR “—” untuk selesai.
- **Cek:** Kolom status hanya berisi status.
- **Terverifikasi:** ya

#### G2-17 [S] · pola P-11
Buat Retur / Barang Sisa: “PESANAN (SO) *” terdiri dari kotak cari + dropdown bertumpuk; label “ITEM YANG DIRETUR *” menempel pada bantuan; “SEBAB KELUHAN” tanpa penanda; placeholder “-- Pilih … --”.

- **Lokasi layar / jalur klik:** Retur Pelanggan › Buat Retur (returns #191/#192).
- **Berkas:baris:** `frontend/src/features/sales/CreateReturnForm.jsx:126,188-197`
- **Perbaikan:** Satu KNSelect searchable untuk SO; jarak label; tanda wajib/opsional; placeholder “— Pilih pesanan —”.
- **Cek:** Satu kontrol pemilih SO; penanda konsisten.
- **Terverifikasi:** ya

#### G2-18 [S] · pola P-06
Pesanan Sample: SO “Dibatalkan” masih “1 yard · menunggu potong · saran roll RL-00007”; RIWAYAT kosong tanpa teks; “Rp 15.000/yard → Rp 15.000” tetapi “Total Rp 16.650” (PPN tak ditulis); cap waktu “2026-10-24 02:02”, “16.67%”.

- **Lokasi layar / jalur klik:** Penjualan › Pesanan Sample (SOS) › klik baris KSC/SOS-00075 / -00055 (sample-orders #196/#203/#205).
- **Berkas:baris:** `frontend/src/features/samples/SampleOrdersView.jsx:30,179-184,195,213-215`
- **Perbaikan:** Status potong disembunyikan/“dibatalkan” untuk SO batal; riwayat kosong “Belum ada riwayat”; baris subtotal + PPN + total; tanggal `formatDateTime`; persen id-ID.
- **Cek:** Detail SOS batal tidak menyebut “menunggu potong”; total = subtotal + PPN tertulis.
- **Terverifikasi:** ya

#### G2-19 [S] · pola P-13
Sample Catalogue: tombol “+ Buat Sample Katalog” membuka pop-up “Sample Catalogue” bertombol “Buat Pesanan Catalogue”; label MAJUSCULE tanpa wajib; pil kuning Gratis/Berbayar buatan sendiri; kolom “HANGER/CATALOGUE”.

- **Lokasi layar / jalur klik:** Pesanan Sample › + Buat Sample Katalog; tab Lokasi Cutting (sample-orders #198/#199).
- **Berkas:baris:** `frontend/src/features/samples/CatalogueCreateModal.jsx:11-65`; `frontend/src/features/samples/SampleOrdersView.jsx:31,93`
- **Perbaikan:** Satu istilah “Katalog”; * pada Pelanggan/Artikel; segmented standar.
- **Cek:** Tidak ada “Catalogue” di layar.
- **Terverifikasi:** ya

#### G2-20 [S]
HP Pesanan Saya: KSC/SO-00159 berstatus “Disetujui ✓” sementara langkah sebelumnya “Diverifikasi Admin Sales — Belum diperiksa” masih aktif; SO batal menampilkan “Dibatalkan” dua kali + “1 item • Belum bayar” dan progres 11%.

- **Lokasi layar / jalur klik:** HP Sales › Pesanan › kartu KSC/SO-00159 / KSC/SO-00420 (hp-sales-pesanan #50/#51/#54).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileOrders.jsx:28,110-114`
- **Perbaikan:** SO batal: sembunyikan SubStatusChips & status bayar, progres “Dibatalkan”; urutan langkah ikut status server (bila verifikasi dilewati tampilkan “dilewati”).
- **Cek:** Kartu SO batal hanya satu status tanpa “Belum bayar”.
- **Terverifikasi:** tampilan ya; urutan verifikasi vs setuju belum terverifikasi

#### G2-21 [S] · pola P-11
HP Catat pembayaran: dibuka dari KSC/SO-00164 tetapi alokasi FIFO dimulai dari KSC/SO-00002 (tidak ada di Pesanan Saya), SO yang dibuka di urutan terakhir; kotak alokasi tanpa label; “Jumlah diterima” hanya placeholder; ringkasan “Teralokasi Rp 0 · pas” saat kosong.

- **Lokasi layar / jalur klik:** HP Sales › Pesanan › KSC/SO-00164 › Catat bayar (hp-sales-pesanan #58).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileArReceipt.jsx:9,43-57`
- **Perbaikan:** SO asal di urutan pertama & teralokasi lebih dulu; label per isian; status “Isi jumlah dulu” saat 0.
- **Cek:** Alokasi pertama = SO yang dibuka.
- **Terverifikasi:** ya

#### G2-22 [S] · pola P-11
HP Pelanggan Baru: gaya label campur (sentence + * vs MAJUSCULE), No. HP & “Jalan, nomor, patokan” tanpa label, “Buat Customer”, “Segment (untuk BI)”.

- **Lokasi layar / jalur klik:** HP Sales › Katalog › Pelanggan baru (hp-sales-katalog #46).
- **Berkas:baris:** `frontend/src/features/pos/CreateCustomerModal.jsx:43-57`
- **Perbaikan:** Label untuk semua isian; “Buat Pelanggan”; “Segmen”. (Blok alamat → G0-08.)
- **Cek:** Semua isian berlabel; tidak ada “Customer”.
- **Terverifikasi:** ya

#### G2-23 [S]
HP Beranda Sales: papan “PO Custom — menunggu keputusan (9)” berisi pesanan pelanggan lain, semua “perlu Manajer” tanpa aksi bagi sales.

- **Lokasi layar / jalur klik:** HP Sales › Beranda (hp-sales-beranda #38/#41).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileSalesHome.jsx:35,107`
- **Perbaikan:** Saat memilih papan untuk peran sales: saring ke pelanggan miliknya atau sembunyikan papan yang hanya bisa diputus manajer (keputusan K-11 bila ragu).
- **Cek:** Beranda sales hanya menampilkan pesanan miliknya atau tidak menampilkan papan PO Custom.
- **Terverifikasi:** ya

#### G2-24 [S] · pola P-11
HP Ajukan permintaan internal: placeholder dipakai sebagai label (“Jumlah”, “Alasan permintaan *”, “Catatan”), tanggal `<input type=date>` bawaan, “Memuat barang…” statis saat daftar produk kosong.

- **Lokasi layar / jalur klik:** HP Sales › Lainnya › Permintaan Internal (PIN) › + Ajukan (hp-sales-permintaan-internal #66).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileInternalRequests.jsx:151-168`
- **Perbaikan:** Label di atas isian; KNDatePicker; bedakan memuat vs kosong (“Belum ada barang di badan usaha lain”).
- **Cek:** Form berlabel & tanggal berformat Indonesia.
- **Terverifikasi:** ya

#### G2-25 [S] · pola P-05
Pelacak SO aktif di HP: tabel `min-w-[760px]` memotong pesan kosong jadi “Tida…”.

- **Lokasi layar / jalur klik:** HP Admin Sample › Desktop › Meja Admin Sample (hp-sample_admin-desktop #103).
- **Berkas:baris:** `frontend/src/features/sales_admin/SoTrackerCard.jsx:63,70`
- **Perbaikan:** Render pesan kosong di luar wadah gulir (sebelum `<table>`), selebar kartu.
- **Cek:** Pesan kosong terbaca utuh di 390.
- **Terverifikasi:** ya

#### G2-26 [S] · pola P-11
Tarif Insentif: isian “Faktor (tier)” & “Potong Rp/unit” selalu tampil apa pun mekanik; daftar Satuan memuat Centimeter/Milimeter/Kilometer; “Rate”/“Tarif” & “Simpan Rate”/“Update Rate” bercampur.

- **Lokasi layar / jalur klik:** Pengaturan › Rate Insentif Sales › form tarif (incentive-rates #20/#22/#24/#26).
- **Berkas:baris:** `frontend/src/features/crm/IncentiveRatesEditor.jsx:28-29,54,174,179-183,188`
- **Perbaikan:** Tampilkan isian sesuai mekanik (Faktor → faktor; Potong → Rp/unit; Cutoff → keduanya tersembunyi); satuan dibatasi meter/yard/kg/roll; satu istilah “Tarif” (“Simpan Tarif”/“Simpan Perubahan”).
- **Cek:** Mekanik Cutoff tidak menampilkan Faktor/Potong; tidak ada “Rate”.
- **Terverifikasi:** ya

#### G2-27 [S]
Rantai Retur (dipakai Retur Antar-PT): lencana “DOKUMEN INI” menumpuk di atas label tahap & ikon kartu simpul.

- **Lokasi layar / jalur klik:** Antar Entitas › Retur Antar-PT › Jejak Retur (interco-returns #76).
- **Berkas:baris:** `frontend/src/features/sales/ReturnChainMap.jsx:42-47`
- **Perbaikan:** Lencana di dalam kepala kartu (bukan `absolute -top-2`) atau beri `pt-3` pada kartu.
- **Cek:** Lencana tidak menutupi teks tahap.
- **Terverifikasi:** ya

#### G2-28 [R]
Retur selesai: tab Logistik menampilkan 3 blok × 6 isian ongkir yang tampak bisa diubah tanpa tombol simpan; “PT PEMBEBAN” kosong polos; tombol merah “Batal / Pembalikan” sejajar status selesai.

- **Lokasi layar / jalur klik:** Retur › detail SRET-00005 › Logistik (returns #194/#201).
- **Berkas:baris:** `frontend/src/features/sales/LogisticsCostRow.jsx:30-33`
- **Perbaikan:** Mode baca saat `locked` (teks, bukan input); placeholder “Pilih PT”.
- **Cek:** Retur selesai menampilkan ongkir sebagai teks.
- **Terverifikasi:** ya

#### G2-29 [R]
Keep & Pending: nomor SO di tab Keep bukan tautan; tiap baris Pending mengulang “putuskan di ‘Putuskan Pemenuhan’” tanpa tautan.

- **Lokasi layar / jalur klik:** Pesanan (SO) › Keep & Pending (keep-pending #81/#83).
- **Berkas:baris:** `frontend/src/features/sales_admin/KeepPendingPanel.jsx:61-62,109`
- **Perbaikan:** Nomor SO bisa diklik di kedua tab; kalimat jadi tautan ke layar Putuskan Pemenuhan.
- **Cek:** Semua nomor SO bertaut.
- **Terverifikasi:** ya

#### G2-30 [R]
HP Stok & ATP: kartu tanpa stok di PT sendiri tidak memberi tanda (hanya total grup); deskripsi menu “Daftar Harga — Lihat harga per entitas” tidak sesuai isi (pilih pelanggan).

- **Lokasi layar / jalur klik:** HP Sales › Stok & ATP; Lainnya (hp-sales-stok-atp #53, hp-sales-fitur-lainnya #80).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileStockAtp.jsx:9-10,106`; `frontend/src/features/sales/mobile/MobileMore.jsx:46`
- **Perbaikan:** Baris “PT saya: 0 (stok di PT lain)” bila own kosong; deskripsi “Harga efektif per pelanggan”.
- **Cek:** Kartu tanpa stok sendiri bertanda jelas.
- **Terverifikasi:** ya

#### G2-31 [R]
Harga per Pelanggan: produk tanpa kategori menampilkan pemisah yatim “· /meter”; KPI “PRODUK TERDAFTAR 410” bersubjudul nama pelanggan.

- **Lokasi layar / jalur klik:** Harga per Pelanggan (cs-price-list #54).
- **Berkas:baris:** `frontend/src/features/sales/customerPricelist/CustomerPriceParts.jsx:78`; `frontend/src/features/sales/CustomerPricelistView.jsx:137`
- **Perbaikan:** Gabung bagian dengan filter(Boolean).join(' · '); sub KPI sesuai isi.
- **Cek:** Tidak ada pemisah yatim.
- **Terverifikasi:** ya

#### G2-32 [R]
Lokasi Cutting: semua baris “belum diatur (semua jenis)” padahal kotak tercentang; centang cokelat `accent-[#9A5B00]`.

- **Lokasi layar / jalur klik:** Pesanan Sample › tab Lokasi Cutting (sample-orders #198).
- **Berkas:baris:** `frontend/src/features/samples/CuttingLocations.jsx:28-32`
- **Perbaikan:** Keterangan dari status centang; warna aksen standar.
- **Cek:** Baris tercentang tidak berbunyi “belum diatur”.
- **Terverifikasi:** ya

#### G2-33 [R] · pola P-06
HP Pesanan: istilah “Stok siap — bisa di-confirm”, “Siap pick”, “Kredit NET 30”; qty “× 24.78” (titik) & harga koreksi “225000” tanpa pemisah ribuan.

- **Lokasi layar / jalur klik:** HP Sales › Pesanan › kartu / Koreksi (hp-sales-pesanan #50/#53/#56/#57).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileOrders.jsx`
- **Perbaikan:** Terjemahkan; formatQty & MoneyInput.
- **Cek:** Tidak ada titik desimal/angka tanpa pemisah.
- **Terverifikasi:** ya

### G3 — Gudang/WMS, inventori & lot, logistik, RFID, inspeksi/QC, GRN, transfer, permintaan internal + aplikasi HP Gudang

T 8 · S 25 · R 4

**Berkas milik grup (hanya grup ini yang boleh mengedit):**

- `frontend/src/features/inventory/**`
- `frontend/src/features/wms/**  (termasuk wms/grn/**, wms/inbound/**, wms/transfer/**, wms/warehouses/**, wms/repair/**)`
- `frontend/src/features/logistics/**`
- `frontend/src/features/rfid/**`
- `frontend/src/features/inspections/**`
- `frontend/src/features/transfers/**`
- `frontend/src/features/internal_requests/**`
- `frontend/src/features/manager/**`
- `frontend/src/features/mobile/MobileWarehouseApp.jsx`
- `frontend/src/features/mobile/MobileTaskActions.jsx`
- `frontend/src/features/mobile/OfflineBanner.jsx`
- `backend/routers/dashboard.py`
- `backend/routers/reporting.py`
- `backend/services/inspection_service.py`
- `backend/services/approval_backlog_service.py`
- `backend/services/alert_ops_service.py`
- `backend/services/stock_analytics_service.py`

> Laporan stok “Tersedia” berbeda definisi antar layar → keputusan K-04 sebelum mengubah rumus.

#### G3-01 [T] · pola P-01
Tag RFID: “Auto-Encode Semua” (tab Belum Ber-tag, 5.000+ roll seluruh gudang) dan “Pensiunkan” langsung POST/DELETE tanpa dialog — aksi massal tak bisa dibatalkan.

- **Lokasi layar / jalur klik:** Pengaturan › Tag RFID › tab Belum Ber-tag › Auto-Encode Semua; tab Tag Aktif › Pensiunkan (cs-rfid-tags #64).
- **Berkas:baris:** `frontend/src/features/rfid/RfidTagsView.jsx:58-66,124-127,138-141`
- **Perbaikan:** `askConfirm({danger:true, title:`Encode otomatis ${n} roll di ${gudang}?`, message:'Tag baru dibuat untuk setiap roll tanpa tag; tidak bisa dibatalkan massal.'})`; Pensiunkan: `askConfirm` menyebut EPC & roll; pesan “Tag dipensiunkan”.
- **Cek:** Kedua tombol memunculkan dialog aplikasi; Batal tidak mengirim permintaan.
- **Terverifikasi:** ya

#### G3-02 [T] · pola P-12
Analitik Stok: kolom COVERAGE berisi angka mustahil (“2.708.316,9 hr” ≈ 7.400 tahun) pada SKU berlabel “Cepat Laku” — klasifikasi hanya dari “jual terakhir ≤ 30 hari” dan days_of_supply ditampilkan tanpa batas.

- **Lokasi layar / jalur klik:** Analitik › Analitik Stok › klik kartu KPI Cepat Laku (cs-stock-analytics #8).
- **Berkas:baris:** `frontend/src/features/inventory/StockAnalyticsView.jsx:256-262`; `backend/services/stock_analytics_service.py:60-70`
- **Perbaikan:** Tampilan: days_of_supply > 365 → “> 1 tahun”, > 3650 → “> 10 tahun”; label kolom “Cukup untuk”. Klasifikasi Cepat/Lambat yang memperhitungkan coverage menunggu keputusan K-05 (jangan ubah rumus sebelum diputuskan).
- **Cek:** Tidak ada coverage > 1 tahun ditulis dalam hari.
- **Terverifikasi:** ya

#### G3-03 [T] · pola P-02
Scan Terima per PO: lencana mentah “cancelled” (huruf kecil) di daftar tugas & kepala panel “SCAN RECEIVE cancelled”; chip/lencana Inggris “Waiting / Receiving / Escalated”, “Put Away”, “Complete”.

- **Lokasi layar / jalur klik:** Barang Masuk › tab Scan Terima per PO (goods-receipts #43/#45; HP Gudang › Masuk › Scan Terima #114).
- **Berkas:baris:** `frontend/src/features/wms/inbound/InboundTaskPanel.jsx:18-29,220`; `frontend/src/features/wms/InboundScanInterface.jsx:297-298`
- **Perbaikan:** STATUS_MAP lengkap & Indonesia (+cancelled “Dibatalkan”), fallback `docStatusLabel`; FILTER_LABELS: Semua/Menunggu barang/Sedang diterima/Cek QC/Dieskalasi; kepala panel “Terima per scan”.
- **Cek:** Tidak ada label Inggris/huruf kecil mentah di tab Scan Terima.
- **Terverifikasi:** ya

#### G3-04 [T] · pola P-02
Lot & Silsilah: id teknis tampil — PEMILIK “ent_ksc”, GUDANG “wh_jakarta”, BIN “bin_sim_wh_jkt_w11_l1_01”, DOKUMEN SUMBER “cycle_count_found”, peringatan “(supplier_lot)”, status roll “Available”, status pesanan Recall “Siap_disahkan”.

- **Lokasi layar / jalur klik:** Lot & Silsilah › Detail KSC/LOT-2610-0201 › Ringkasan/Roll/Recall (inventory-lots #107/#111/#113).
- **Berkas:baris:** `frontend/src/features/inventory/lots/LotDetailPanel.jsx:140-143,276,280`; `frontend/src/features/inventory/lots/LotRecallPanel.jsx:86,106`; `frontend/src/features/inventory/lots/LotActionModals.jsx:79,246`
- **Perbaikan:** Tampilkan nama badan usaha/gudang/bin (resolve dari daftar entitas & gudang yang sudah dimuat, atau field *_name dari API); sumber dokumen berlabel (“Temuan stock opname”); “Nomor lot supplier belum diisi”; status lewat docStatusLabel.
- **Cek:** Detail lot tanpa id ber-garis-bawah maupun status Inggris.
- **Terverifikasi:** ya

#### G3-05 [T] · pola P-02
Transfer Antar-Entitas: lencana status = kode mentah dengan garis bawah diganti spasi (“Waiting Approval”, “Rejected”, “Completed”), padahal tab filter berbahasa Indonesia.

- **Lokasi layar / jalur klik:** Operasi Gudang › Transfer › Antar entitas (PT) (interco-transfers #94/#101, operations #141).
- **Berkas:baris:** `frontend/src/features/transfers/InterCompanyTransfers.jsx:171-174`
- **Perbaikan:** `docStatusLabel(t.status)` (waiting_approval sudah dipetakan).
- **Cek:** Lencana “Menunggu persetujuan/Ditolak/Selesai”.
- **Terverifikasi:** ya

#### G3-06 [T] · pola P-06
Pengiriman: keterangan foto muat/POD “10-25 05:24 · Hendr…” adalah potongan stempel UTC (−7 jam) sementara baris di bawahnya “Diterima … 25 Okt 2026, 12.24 WIB” — bukti tampak diambil 7 jam sebelum diterima; riwayat posisi & peta memakai potongan yang sama.

- **Lokasi layar / jalur klik:** Pengiriman & Pelacakan › Dasbor › Baru selesai › KSC/LG-00004 (logistics #69).
- **Berkas:baris:** `frontend/src/features/logistics/DeliveryDetailModal.jsx:178,209,238`; `frontend/src/features/logistics/PositionMap.jsx:30`
- **Perbaikan:** Ganti semua `String(x).slice(...)` dengan `formatDateTime` (WIB) dari utils/formatters.
- **Cek:** Jam foto, posisi, dan penerimaan sama-sama WIB dan berurutan wajar.
- **Terverifikasi:** ya

#### G3-07 [T] · pola P-08
SPK Inspeksi: (a) detail SPK di DetailModal framed — kartu `section-card` dalam tanpa padding sehingga huruf awal terpotong (“INDAKAN”, “IWAYAT”, “ARANG YANG DIPERIKSA”) dan di HP nilai terpotong di kanan; (b) tabel SPK di HP: kolom PETUGAS terpotong & tombol “Buka SPK” di luar layar; 5 KPI bertumpuk satu kolom; “Tanggal SPK 2026-10-25”.

- **Lokasi layar / jalur klik:** Kualitas › SPK Inspeksi & QC › Buka SPK; Antrean QC Kedatangan › Putuskan di SPK; Retur › SPK; HP MD › Lainnya › Inspeksi (acuan sample) (inspections #65, qc-inspection #159, returns #197, hp-md-lainnya #25/#26, hp-md-pasang-sekarang #58/#59).
- **Berkas:baris:** `frontend/src/features/inspections/InspectionDetailPanel.jsx:222,260,277,290,335,476`; `frontend/src/features/inspections/InspectionsView.jsx:181,271,358`
- **Perbaikan:** Kartu dalam panel: padding & tanpa margin negatif (atau render panel tanpa `section-card` saat di dalam framed); tombol “Buka SPK” dipindah ke kolom pertama (nomor bertaut) atau kolom aksi `sticky right-0`; KPI `grid-cols-2 sm:grid-cols-5`; tanggal formatDate. (Tombol × → G0-07.)
- **Cek:** Detail SPK di 1440 & 390 tanpa huruf terpotong; di 390 setiap baris SPK bisa dibuka tanpa gulir samping.
- **Terverifikasi:** ya

#### G3-08 [T] · pola P-02
HP Admin Gudang: status tugas tampil mentah “Waiting_goods”, “Qc_pending” (Masuk), “Created” (Keluar, Sample) — STATUS_ID tak punya kode tersebut.

- **Lokasi layar / jalur klik:** HP Gudang › Masuk / Keluar / Sample (hp-warehouse_admin #116/#117/#118).
- **Berkas:baris:** `frontend/src/features/mobile/MobileWarehouseApp.jsx:25,70`
- **Perbaikan:** Lengkapi STATUS_ID (waiting_goods, qc_pending, qc_rejected, created, …) dan fallback `docStatusLabel` (bukan kode).
- **Cek:** Daftar Masuk/Keluar/Sample tanpa label Inggris/garis bawah.
- **Terverifikasi:** ya

#### G3-09 [S] · pola P-06
Analitik Stok: kolom “TERJUAL (90H)” tanpa satuan padahal STOK FISIK ber-yard; NILAI mencampur “Rp 1,4 M” & “Rp 928,8 jt”; “0 hr lalu”; sumbu “Rp 24,0 / M” patah; istilah COVERAGE, landed, di-aging.

- **Lokasi layar / jalur klik:** Analitik Stok › Rincian per SKU (cs-stock-analytics #5/#8).
- **Berkas:baris:** `frontend/src/features/inventory/StockAnalyticsView.jsx:163,196,202,232-234,256-259`
- **Perbaikan:** Satuan pada qty; satu skala Rupiah (formatCompactIDR); “hari ini”/“kemarin”; label Indonesia (“Cukup untuk”, “biaya penuh”).
- **Cek:** Kolom angka bersatuan & seragam.
- **Terverifikasi:** ya

#### G3-10 [S]
Monitor Gerbang: “Layar penuh” tanpa gerbang menampilkan alarm besar “TIDAK TERHUBUNG — TAHAN · jangan loloskan barang” (status jatuh ke unknown karena polling tak jalan tanpa gateId); “Pantau langsung” menyala merah dengan “Pilih gate…” padahal tidak ada pemilih; kartu “Kesehatan Device (0 stale)” kosong total.

- **Lokasi layar / jalur klik:** Pengaturan › Monitor Gerbang › Layar penuh / Pantau langsung / tab Alarm & Keamanan (cs-rfid-gate #53/#54/#55).
- **Berkas:baris:** `frontend/src/features/rfid/RfidGateMonitorView.jsx:17,51-55,120-131,170-182`; `frontend/src/features/rfid/GateLiveVerdict.jsx:44,53`; `frontend/src/features/rfid/RfidSecurityPanel.jsx:136-137`
- **Perbaikan:** Tanpa gateId: tombol Layar penuh & Pantau langsung nonaktif dengan alasan “Belum ada gerbang di gudang ini”; verdict state `no_gate` (abu, bukan alarm); Kesehatan Device menampilkan “Belum ada perangkat”.
- **Cek:** Gudang tanpa gerbang tidak pernah menampilkan alarm TIDAK TERHUBUNG.
- **Terverifikasi:** ya (kode); skenario dengan gerbang nyata belum teruji

#### G3-11 [S] · pola P-01
Perangkat RFID: tombol “Tambah Perangkat/Simpan” biru #0058CC buatan sendiri; form inline “Perangkat Baru” mendorong daftar, urutan Simpan→Batal di kiri, tanpa penanda wajib, placeholder campur; galat “Gagal seed devices”, “Gagal buat device”; “Buat Perangkat Bawaan” langsung POST.

- **Lokasi layar / jalur klik:** Pengaturan › Perangkat RFID › Tambah Perangkat / Buat Perangkat Bawaan (cs-rfid-devices #1–#3).
- **Berkas:baris:** `frontend/src/features/rfid/RfidDevicesView.jsx:31,72-73,102,133-172`
- **Perbaikan:** `.primary-button`/`.secondary-button`; Batal kiri, Simpan kanan; * pada Kode/Nama/Gudang; placeholder “mis. GATE-JKT-OUT”; pesan Indonesia; askConfirm untuk Buat Perangkat Bawaan (sebut jumlah gudang).
- **Cek:** Form & pesan konsisten; Buat Perangkat Bawaan meminta konfirmasi.
- **Terverifikasi:** ya

#### G3-12 [S]
Lokasi RFID: “Pilih reader” hanya berisi placeholder tanpa pesan “belum ada reader — buat di Perangkat RFID”; tombol Pindai mati tanpa alasan; tabel lokasi tag (31 baris) di dalam kartu berjudul “Simulasi Pindai Area”.

- **Lokasi layar / jalur klik:** Pengaturan › Lokasi RFID (cs-rfid-lokasi #22/#23).
- **Berkas:baris:** `frontend/src/features/rfid/RfidLocationsView.jsx:43,54,61,87-93`
- **Perbaikan:** Bila tidak ada reader: teks + tautan ke Perangkat RFID, alasan pada tombol Pindai; pisahkan kartu “Lokasi tag” dari kartu simulasi.
- **Cek:** Tanpa reader layar menjelaskan langkah berikutnya.
- **Terverifikasi:** ya

#### G3-13 [S] · pola P-02
Tag RFID: daftar “Roll Fisik Belum Ber-tag” mencetak status mentah “available”; tab Belum Ber-tag 500 kartu tanpa cari/paginasi (tab Tag Aktif bertabel + paginasi); judul header “Tags (tag↔item)” vs h1 “Tag RFID (tag ↔ roll)”.

- **Lokasi layar / jalur klik:** Tag RFID › tab Belum Ber-tag / Tag Aktif (cs-rfid-tags #60/#63).
- **Berkas:baris:** `frontend/src/features/rfid/RfidTagsView.jsx:65,71,101-162 (150)`
- **Perbaikan:** docStatusLabel; cari + paginasi (PagedRows/usePagedList) di tab Belum Ber-tag; judul seragam “Tag RFID”.
- **Cek:** Tidak ada “available”; tab Belum Ber-tag berpaginasi.
- **Terverifikasi:** ya

#### G3-14 [S]
Barang Masuk: dokumen Dibatalkan/Ditutup tetap menampilkan form kepala SJ yang bisa diedit dengan “Simpan kepala SJ” aktif; tugas PO “cancelled” tetap menawarkan “Eskalasi” & “Scan Label Supplier / Input Manual”.

- **Lokasi layar / jalur klik:** Barang Masuk › kartu KSC/GRN-00022 / -00023 / -00004 › tab Surat jalan; Scan Terima › KSC/PO-00138 (goods-receipts #30/#34/#45; HP Gudang #112).
- **Berkas:baris:** `frontend/src/features/wms/grn/GrnReviewPanel.jsx:30-41`; `frontend/src/features/wms/inbound/InboundTaskPanel.jsx:223-226`
- **Perbaikan:** Mode baca (input disabled, tombol simpan disembunyikan) bila status cancelled/closed; aksi tugas disembunyikan untuk tugas batal.
- **Cek:** GRN batal/ditutup tidak bisa diubah; tugas batal tanpa tombol aksi.
- **Terverifikasi:** ya

#### G3-15 [S]
GRN batal tanpa baris: tab Hitung hanya judul + kartu kosong; Rekonsiliasi berpesan hijau “Tidak ada selisih — surat jalan cocok …”; stepper tanpa tanda “Dibatalkan”, langkah “5 Ditutup” tampil sebagai langkah aktif (bukan selesai).

- **Lokasi layar / jalur klik:** Barang Masuk › KSC/GRN-00022 › tab Hitung / Rekonsiliasi; KSC/GRN-00023 (goods-receipts #31–#33).
- **Berkas:baris:** `frontend/src/features/wms/grn/GrnReconPanel.jsx:96-98`; `frontend/src/features/wms/grn/GrnReviewPanel.jsx (stepper)`
- **Perbaikan:** Dokumen 0 baris → pesan netral “Belum ada baris untuk direkonsiliasi”; stepper menampilkan status Dibatalkan; langkah terakhir dokumen Ditutup bertanda selesai.
- **Cek:** GRN batal tidak menampilkan “cocok” hijau.
- **Terverifikasi:** ya

#### G3-16 [S] · pola P-11
Isian tanggal memakai `<input type=date>` / `type=month` bawaan peramban (“dd/mm/yyyy”, “October 2026”) — Tanggal kirim SJ, Biaya OCR.

- **Lokasi layar / jalur klik:** Barang Masuk › Surat jalan (goods-receipts #30); Pengaturan › Penerimaan & OCR › Biaya OCR (settings-receiving-ocr #241).
- **Berkas:baris:** `frontend/src/features/wms/grn/GrnReviewPanel.jsx:33`; `frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx:7,34`
- **Perbaikan:** KNDatePicker / KNMonthPicker; uang USD `toLocaleString('id-ID',{style:'currency',currency:'USD'})` tanpa font mono.
- **Cek:** Tidak ada pemilih tanggal bawaan peramban di layar gudang.
- **Terverifikasi:** ya

#### G3-17 [S] · pola P-12
Inspeksi: status bertentangan (🔒 “1 Ditahan” pada SPK “Selesai · Diterima seluruhnya”; SPK Selesai dengan petugas “Belum ditugaskan”); filter LINI Woven/Knit membuat semua KPI 0 & “Belum ada SPK inspeksi” padahal ada SPK kain tenun/rajut.

- **Lokasi layar / jalur klik:** Kualitas › SPK Inspeksi & QC › tab Selesai / pil LINI (inspections #62/#67/#68/#75).
- **Berkas:baris:** `frontend/src/features/inspections/InspectionsView.jsx:65,81,155-156,262`; `backend/services/inspection_service.py (hitungan hold & kode lini)`
- **Perbaikan:** Telusuri: hitungan “Ditahan” harus 0 setelah keputusan diterima; SPK lama tanpa kode lini → turunkan lini dari produk atau tampilkan pesan “filter lini tidak berlaku untuk SPK lama”; pesan kosong menyebut filter aktif.
- **Cek:** SPK diterima tidak berlencana Ditahan; filter Woven menampilkan SPK kain tenun.
- **Terverifikasi:** lokasi ya; penyebab data/backend belum terverifikasi

#### G3-18 [S]
Detail SPK draf: “Mulai periksa” aktif padahal pita kuning “SPK belum ditugaskan — tugaskan petugas dulu”; Pratinjau/Unduh PDF/TTD/Kirim WA aktif untuk draf; “Tutup” terselip di antara aksi; pemilih petugas memuat semua pengguna (Admin, Gudang, …).

- **Lokasi layar / jalur klik:** Kualitas › SPK Inspeksi › Buka SPK KSC/INS-00126 › Tugaskan / Random check stok (inspections #65/#66/#69/#71).
- **Berkas:baris:** `frontend/src/features/inspections/InspectionDetailPanel.jsx:503-510`; `frontend/src/features/inspections/InspectionsView.jsx (random check)`
- **Perbaikan:** Nonaktifkan “Mulai periksa” sampai ada petugas (alasan di tooltip); aksi dokumen hanya setelah terbit; pemilih petugas disaring peran QC/inspeksi (fallback semua dengan grup “Peran lain”); “Ambil roll & tahan” nonaktif bila gudang kosong.
- **Cek:** SPK draf tak bisa dimulai tanpa petugas; daftar petugas hanya QC.
- **Terverifikasi:** ya

#### G3-19 [S] · pola P-12
Operasi Gudang › Stok: angka tak bisa dicocokkan (BTK-MEGA-001 “STOK FISIK 562 · DIPESAN 8 · TERSEDIA 4”; ULS-BTK-001 “55 · 0 · 0 · Habis”) — selisih (ditahan QC/karantina/diblokir) tidak punya kolom/keterangan.

- **Lokasi layar / jalur klik:** Operasi Gudang › Stok, Transfer & Opname › tab Stok (operations #127).
- **Berkas:baris:** `frontend/src/features/wms/InventoryStockView.jsx (kolom ringkasan stok)`
- **Perbaikan:** Tambah kolom/tooltip “Ditahan/karantina/diblokir” sehingga Fisik = Tersedia + Dipesan + Ditahan; definisi tunggal “Tersedia” → K-04.
- **Cek:** Setiap baris menjumlah tanpa selisih misterius.
- **Terverifikasi:** belum terverifikasi (lokasi kolom)

#### G3-20 [S] · pola P-11
Tambah Stok Awal (Roll): “HPP / satuan” berplaceholder “wajib untuk migrasi” tanpa *; “Unit” teks bebas “meter” (bukan dari produk); “Batch” tanpa petunjuk; label 10px.

- **Lokasi layar / jalur klik:** Operasi Gudang › Stok › Tambah Stok (operations #134).
- **Berkas:baris:** `frontend/src/features/wms/inventory/InitialStockForm.jsx:30-78 (50,71,78)`; `frontend/src/features/wms/InventoryStockView.jsx:427`
- **Perbaikan:** Satuan diambil dari master produk (read-only); HPP wajib ber-* bila mode migrasi; teks bantu Batch; ukuran label standar.
- **Cek:** Form stok awal tidak bisa menyimpan satuan berbeda dari produk.
- **Terverifikasi:** ya

#### G3-21 [S] · pola P-01
Transfer: “Items:”, “Requested by:”, chip “Staging”, “Approve & Pindahkan Kepemilikan” (hijau #126E2C, Inggris, tanpa konfirmasi); detail transfer Selesai: “Jurnal Antar-PT · NOT POSTED · JE tidak di-post — alasan tidak diketahui.”; tolak inline tanpa label/minimal alasan.

- **Lokasi layar / jalur klik:** Operasi Gudang › Transfer › kartu KSC/TRF-0000x / detail CST/TRF-00002 (operations #137/#151, interco-transfers #95/#98).
- **Berkas:baris:** `frontend/src/features/wms/TransferManagement.jsx:324-326`; `frontend/src/features/wms/transfer/transferConstants.jsx:7`; `frontend/src/features/wms/transfer/TransferDetailModal.jsx:119-121,146-153,206-210`; `frontend/src/features/transfers/InterCompanyTransfers.jsx:219-256`
- **Perbaikan:** Label Indonesia (Barang, Diajukan oleh, Disiapkan); tombol `.primary-button` “Setujui & pindahkan kepemilikan” + askConfirm (asal → tujuan, qty); jurnal tidak terposting → “Belum terposting — lihat Posting Gagal” + tautan; tolak pakai askReason (min. huruf).
- **Cek:** Tidak ada label Inggris; persetujuan meminta konfirmasi.
- **Terverifikasi:** ya

#### G3-22 [S] · pola P-11
Transfer Gudang Baru: label tanpa *; “Pilih Produk” aktif sebelum gudang asal dipilih (hanya teks oranye); “Buat Transfer” aktif pada form kosong.

- **Lokasi layar / jalur klik:** Operasi Gudang › Transfer › Buat Transfer (operations #138).
- **Berkas:baris:** `frontend/src/features/wms/transfer/TransferCreateForm.jsx:22,56-64,95-98`
- **Perbaikan:** * pada gudang asal/tujuan & item; pemilih produk nonaktif sampai gudang asal; tombol nonaktif sampai valid.
- **Cek:** Form kosong tidak bisa dikirim.
- **Terverifikasi:** ya

#### G3-23 [S]
Dasbor & Analitik: label sumbu X “Utilisasi Gudang” (17 gudang) saling menimpa; tabel Umur Stok memuat produk “Unknown” (Rp 0).

- **Lokasi layar / jalur klik:** Laporan › Dasbor & Analitik (reports #161).
- **Berkas:baris:** `frontend/src/features/manager/ManagerDashboard.jsx:210,244-245,303`; `backend/routers/reporting.py:62,66`
- **Perbaikan:** XAxis `interval="preserveStartEnd"`/label miring + tickFormatter pendek, atau grafik batang horizontal; backend: produk/gudang tak ditemukan → lewati baris atau “Produk tidak ditemukan (<sku/id>)”.
- **Cek:** Label sumbu terbaca; tidak ada “Unknown”.
- **Terverifikasi:** ya

#### G3-24 [S] · pola P-06
Pengiriman: baris aksi cepat KSC/SJ-00068 kosong “Kirim · · · 0” (juga di pop-up); daftar SJ di pop-up “Buat Pengiriman” “12.5 yard/477.46 yard” (titik); kepala tabel campur Title case & MAJUSCULE; pop-up: “Biaya Kirim” Rp 0 dua kali, “Jenis Pengiriman” abu seperti placeholder, tinggi isian beda, 61 SJ tanpa cari.

- **Lokasi layar / jalur klik:** Pengiriman & Pelacakan › Dasbor › Aksi cepat / Buat Pengiriman; tab Daftar pengiriman (logistics #61/#62/#74).
- **Berkas:baris:** `frontend/src/features/logistics/DispatchDashboard.jsx:68`; `frontend/src/features/logistics/DeliveryCreateModal.jsx:93,117-140`; `frontend/src/features/logistics/DeliveryTable.jsx:11-19,44-50`
- **Perbaikan:** Fallback “Data SJ tidak lengkap” bila pesanan/pelanggan kosong; formatQty; satu gaya kepala kolom; satu teks bantu biaya; isian `.field` seragam; daftar SJ searchable.
- **Cek:** Tidak ada baris “· · ·”; qty berkoma.
- **Terverifikasi:** ya

#### G3-25 [S] · pola P-01
Master Gudang: saringan “Boleh dipakai” & KPI “BOLEH DIPAKAI 15” ikut menghitung gudang NONAKTIF (tanpa label status); tabel min-w 980 px bergulir di 1440 dan nama patah 3–5 baris; “Nonaktifkan” gudang langsung tanpa konfirmasi.

- **Lokasi layar / jalur klik:** Pengaturan › Gudang (Master) · Lokasi & Bin (md-warehouses #113/#116).
- **Berkas:baris:** `frontend/src/features/wms/warehouses/WarehouseMasterView.jsx:55,117-128,163-172,374`
- **Perbaikan:** Saringan “Boleh dipakai” mengecualikan nonaktif + lencana “Nonaktif”; lebar kolom/`min-w` disesuaikan agar muat 1440; askConfirm danger untuk nonaktifkan (sebut saldo stok bila ada).
- **Cek:** Gudang nonaktif tidak terhitung; nonaktifkan meminta konfirmasi.
- **Terverifikasi:** ya

#### G3-26 [S] · pola P-01
Cutting: 52 baris antrean dengan isian tanpa label (placeholder terpotong “aktual 0.3…”, “waste”, desimal titik) dan 52 tombol “Konfirmasi Potong” #0058CC buatan sendiri yang langsung POST.

- **Lokasi layar / jalur klik:** Operasi Gudang › Cutting › Antrean Potong Roll (wms-cutting #224/#226).
- **Berkas:baris:** `frontend/src/features/wms/PendingCutsPanel.jsx:33,64-86`
- **Perbaikan:** Kepala kolom “Panjang aktual / Sisa terbuang (waste → susut)”; DecimalInput id-ID; `.primary-button`; askConfirm ringkas (“Potong RL-… 12,5 yard?”).
- **Cek:** Isian berlabel; potong meminta konfirmasi.
- **Terverifikasi:** ya

#### G3-27 [S]
Penerimaan & OCR › Mode Penerimaan: konfirmasi inline “Beralih ke Kedatangan” dengan isian alasan tanpa label, Batal berupa teks polos; 6 tombol utama sekaligus; istilah “MKO”.

- **Lokasi layar / jalur klik:** Pengaturan › Penerimaan & OCR › Mode Penerimaan (settings-receiving-ocr #242/#243).
- **Berkas:baris:** `frontend/src/features/wms/grn/GrnModePanel.jsx:63-75`
- **Perbaikan:** `askReason` dengan judul menyebut badan usaha & mode; tombol per badan usaha `.secondary-button`; “MKO” → “order makloon”.
- **Cek:** Ganti mode lewat dialog alasan standar.
- **Terverifikasi:** ya

#### G3-28 [S] · pola P-02
Perbaikan (repair): teks bantu memuat kode keputusan “(keputusan pemilik P7-K1)” dan “Vendor Bill”.

- **Lokasi layar / jalur klik:** Gudang › Perbaikan › Perbaikan baru (repair-orders #200).
- **Berkas:baris:** `frontend/src/features/wms/repair/RepairCreateModal.jsx:119`
- **Perbaikan:** Hapus kode; “Tagihan Supplier”.
- **Cek:** Pop-up tanpa “P7-K1”.
- **Terverifikasi:** ya

#### G3-29 [S] · pola P-04
Permintaan Internal (PIN): KPI “Jadi Transaksi Antar-PT” & lencana “Semua” ikut tersaring tab (0 di tab Ditolak); tab kosong memakai pesan “Belum ada permintaan internal…” walau ada 1; catatan kaki “permintaan ngawur”; riwayat ISO; kolom tanpa satuan.

- **Lokasi layar / jalur klik:** Antar Entitas › Permintaan Internal (PIN) › tab Ditolak/Antrean; Detail KSC/PIN-00001 (internal-requests #78/#82–#84).
- **Berkas:baris:** `frontend/src/features/internal_requests/InternalRequestsView.jsx:55,137-158,177,369,396`
- **Perbaikan:** Statistik diambil tanpa param status; pesan kosong per status; bahasa formal; formatDateTime; satuan.
- **Cek:** KPI tetap sama di semua tab.
- **Terverifikasi:** ya

#### G3-30 [S] · pola P-05
Pop-up “Minta Barang dari Badan Usaha Lain” di HP: grid `1.6fr_110px_1fr_36px` memotong nama & SKU (“KNKNT0005- •-10XX-•…”), placeholder “opsio”, Jumlah tanpa satuan.

- **Lokasi layar / jalur klik:** HP Sales › Stok & ATP › kartu ALICE KNIT › Minta (hp-sales-stok-atp #54).
- **Berkas:baris:** `frontend/src/features/internal_requests/InternalRequestCreateModal.jsx:164-191,213`
- **Perbaikan:** Di < 640px baris barang jadi dua baris (nama penuh; jumlah + satuan + hapus); placeholder pendek.
- **Cek:** Di 390 nama barang & SKU terbaca.
- **Terverifikasi:** ya

#### G3-31 [S] · pola P-02
Papan & pop-up “Barang ditahan QC”: setiap baris “KSC/INS-00072 · —” + “Bagian Inspect” (bawaan server setengah Inggris), tanpa produk/roll/gudang.

- **Lokasi layar / jalur klik:** Dasbor Manajer / Operasi Gudang › Barang ditahan QC › Lihat semua (operations #133, hp-manager-ringkas #28/#37).
- **Berkas:baris:** `backend/services/approval_backlog_service.py:414-416`; `backend/services/inspection_service.py:554,859`
- **Perbaikan:** Note papan = produk · roll · gudang; bawaan bagian “Bagian Inspeksi” (atau kosong); hilangkan “ · —” saat kosong.
- **Cek:** Baris papan menyebut barang yang ditahan.
- **Terverifikasi:** ya

#### G3-32 [S] · pola P-12
KPI “Jml Tersedia/Dipesan” memuat kelompok “1.503 tanpa satuan” (produk tanpa base_unit/unit), bertentangan dengan Stok gudang “1.609 meter”.

- **Lokasi layar / jalur klik:** Kartu KPI global & HP Ringkas (operations #127, reports #161, hp-*-ringkas).
- **Berkas:baris:** `backend/routers/dashboard.py:108-120`
- **Perbaikan:** Fallback satuan: unit produk induk/kategori; bila tetap kosong label “satuan belum diisi (N produk)” dan catat daftar produknya untuk perbaikan data (lihat Data uji).
- **Cek:** KPI tidak lagi menulis “tanpa satuan” untuk produk yang satuannya bisa diturunkan.
- **Terverifikasi:** ya

#### G3-33 [S] · pola P-12
Lot & Silsilah: KPI “SISA DALAM LOT 1.381.852,24 — satuan dasar produk” menjumlah kg+yard+meter; detail lot dibuka di bawah daftar (±1.500 px, harus digulir); 4 filter 150 px dengan teks 10,5 px.

- **Lokasi layar / jalur klik:** Lot & Silsilah (inventory-lots #102/#107/#116).
- **Berkas:baris:** `frontend/src/features/inventory/lots/LotParts.jsx:15,51-55`; `frontend/src/features/inventory/lots/LotDetailPanel.jsx`
- **Perbaikan:** KPI per satuan (formatUnitTotals); detail dalam DetailModal; lebar filter mengikuti isi.
- **Cek:** KPI menampilkan “… kg · … yard”; klik lot membuka pop-up.
- **Terverifikasi:** ya

#### G3-34 [R]
Status Stok & ATP: rumus ATP ditulis dua kali dengan kata berbeda; panel per gudang (36+1.004 = 1.040) tidak menjelaskan “− tertunda 6” pada total 1.034; ATP negatif hitam; angka 0 berwarna.

- **Lokasi layar / jalur klik:** Status Stok & ATP (inventory-board #53/#57).
- **Berkas:baris:** `frontend/src/features/inventory/InventoryStatusBoard.jsx:121,165-166,256,268-271`
- **Perbaikan:** Satu kalimat rumus; baris “− permintaan tertunda” di panel; ATP < 0 merah; 0 abu.
- **Cek:** Panel gudang menjumlah ke total.
- **Terverifikasi:** ya

#### G3-35 [R]
Lot › Status Mutu: “Simpan Status” aktif walau status sama & alasan kosong; label MAJUSCULE 9,5 px di pop-up lot.

- **Lokasi layar / jalur klik:** Lot › Status Mutu / Buat Lot Manual / Rework (inventory-lots #103/#108/#110).
- **Berkas:baris:** `frontend/src/features/inventory/lots/LotActionModals.jsx:229,278,287`
- **Perbaikan:** Nonaktif bila status tidak berubah atau alasan kosong; ukuran label standar.
- **Cek:** Tidak bisa menyimpan tanpa perubahan.
- **Terverifikasi:** ya

#### G3-36 [R]
Notifikasi stok pendingan: “sudah tersedia 0.02 di gudang”, “50.39”, “tersedia 1” (titik & tanpa satuan).

- **Lokasi layar / jalur klik:** HP manager › Notifikasi (hp-manager-notifikasi #24).
- **Berkas:baris:** `backend/services/alert_ops_service.py:200-208`
- **Perbaikan:** `_qty` memakai format id-ID + satuan produk.
- **Cek:** Teks notifikasi “tersedia 0,02 yard”.
- **Terverifikasi:** ya

#### G3-37 [R]
Barang Masuk › Hitung: “109.36 yard (= 100 meter) · 21 kg” untuk barang bersatuan meter; kepala “SJ -” menggantung; HP Gudang daftar Masuk 100+ kartu tanpa judul/jumlah/cari; Belum Tag “500+” vs “30 + 470 tersisa”.

- **Lokasi layar / jalur klik:** goods-receipts #35; HP Gudang #116/#120.
- **Berkas:baris:** `frontend/src/features/wms/grn/GrnCountPanel.jsx:11-17`; `frontend/src/features/mobile/MobileWarehouseApp.jsx`
- **Perbaikan:** Satuan utama = satuan PO; sembunyikan “SJ -”; judul + jumlah + cari; hitungan konsisten.
- **Cek:** Satuan sesuai PO; daftar HP berjudul.
- **Terverifikasi:** berkas ya; baris pasti teks “(= 100 meter)” belum dipastikan

### G4 — Pembelian, RFQ/PR/PO, kontrak & harga internal, makloon, master produk/kategori/satuan/domain, produksi

T 4 · S 21 · R 5

**Berkas milik grup (hanya grup ini yang boleh mengedit):**

- `frontend/src/features/purchasing/**  (KECUALI CashManagementView.jsx, InputTaxView.jsx, InputTaxCreateModal.jsx, contrabon/** → G1)`
- `frontend/src/features/catalog/**`
- `frontend/src/features/production/**`
- `frontend/src/features/interco_prices/**`
- `frontend/src/features/admin/CategoryManager.jsx`
- `frontend/src/features/admin/PurchaseOrderManagement.jsx`
- `frontend/src/features/admin/uom/**`
- `frontend/src/features/admin/domain/**`
- `frontend/src/features/admin/po/**`
- `frontend/src/features/admin/products/**`
- `backend/services/purchase_requisition_service.py`
- `backend/services/pr_sourcing_service.py`
- `backend/services/makloon_order_service.py`
- `backend/services/contract_service.py`
- `backend/services/interco_price_service.py`

> AdminView.jsx (Daftar Satuan, Master Data) milik G5; ProductGallery milik G0.

#### G4-01 [T] · pola P-01
Kontrak: ikon tempat sampah langsung DELETE kontrak tanpa konfirmasi; “Hentikan/Aktifkan” langsung mengubah status dengan alasan otomatis “Diubah dari layar kontrak oleh …”.

- **Lokasi layar / jalur klik:** Pembelian › Kontrak Mitra & Supplier › ikon hapus / Hentikan (supplier-contracts #212/#219).
- **Berkas:baris:** `frontend/src/features/purchasing/contracts/ContractsView.jsx:104-117,237-245`
- **Perbaikan:** `remove`: askConfirm danger (nomor kontrak, akibat); `changeStatus`: askReason (alasan pengguna dikirim ke setContractStatus).
- **Cek:** Hapus & Hentikan meminta konfirmasi/alasan; riwayat status berisi alasan pengguna.
- **Terverifikasi:** ya

#### G4-02 [T]
Ubah kontrak harga internal (KSC/SCT-00261, Sukacita → Kanda Fabric): “Jenis Kontrak” kosong & “Supplier *” “Pilih…” — tipe `internal` tidak ada di TYPE_OPTS dan PT mitra tidak ada di daftar supplier, sehingga form tidak bisa disimpan benar.

- **Lokasi layar / jalur klik:** Kontrak › klik KSC/SCT-00261 › Ubah (supplier-contracts #214/#215).
- **Berkas:baris:** `frontend/src/features/purchasing/contracts/ContractFormModal.jsx:19-22,82-84,153-175`
- **Perbaikan:** Tambah opsi {value:'internal', label:'Kontrak Harga Internal (antar-PT)'} (read-only saat ubah); untuk internal tampilkan pemilih badan usaha mitra (bukan supplier) atau arahkan ke editor Harga Internal.
- **Cek:** Ubah KSC/SCT-00261 menampilkan jenis & mitra yang benar dan bisa disimpan tanpa mengubah mitra.
- **Terverifikasi:** ya

#### G4-03 [T] · pola P-05
Buat RFQ di HP: grid 2 kolom dan baris item `1fr_90px_80px_32px` tetap di 390 px — placeholder terpotong (“mis. Pengadaan ka”, “Pilih gudang…”), ikon hapus baris keluar tepi, daftar supplier 2 kolom memotong nama sampai satu huruf (“F”/“P” + “Entitas grup”).

- **Lokasi layar / jalur klik:** HP MD › Lainnya › RFQ Supplier › Buat RFQ (hp-md-lainnya #18, hp-md-semua #70, hp-md-cipta-sandang #114, hp-md-kanda-fabric #99).
- **Berkas:baris:** `frontend/src/features/purchasing/RFQCreateModal.jsx:91-163 (104-105,127-133,146-162)`
- **Perbaikan:** `grid-cols-1 sm:grid-cols-2`; baris item dua baris di < 640px (produk penuh; qty + satuan + hapus); daftar supplier 1 kolom di HP.
- **Cek:** Di 390 semua isian & nama supplier terbaca, ikon hapus di dalam kartu.
- **Terverifikasi:** ya

#### G4-04 [T] · pola P-05
RFQ Supplier di HP: tabel `min-w-[700px]` — kolom setelah ITEM dan pesan kosong (“Belum ad…”, “…manual u…”) terpotong di semua tab.

- **Lokasi layar / jalur klik:** HP MD › Lainnya › RFQ Supplier (+ tab Draf/Berjalan/Pemenang/Batal) (hp-md-pasang-sekarang #53–#57).
- **Berkas:baris:** `frontend/src/features/purchasing/RFQView.jsx:103-115`
- **Perbaikan:** Pesan kosong di luar wadah min-w (selebar kartu); di < 640px tampilkan kartu RFQ (nomor, status, item, penawaran).
- **Cek:** Pesan kosong terbaca utuh; status RFQ terlihat tanpa gulir samping.
- **Terverifikasi:** ya

#### G4-05 [S]
Mode “Semua badan usaha” (hanya-lihat) tetapi tombol “+ Buat RFQ” tetap aktif dan membuka form buat.

- **Lokasi layar / jalur klik:** HP MD › Semua › RFQ Supplier (hp-md-semua #69/#70).
- **Berkas:baris:** `frontend/src/features/purchasing/RFQView.jsx:87-89`
- **Perbaikan:** Nonaktifkan bila scope “Semua” (pakai utils/writeScope) dengan tooltip “Pilih satu badan usaha dulu”.
- **Cek:** Di mode Semua tombol Buat RFQ nonaktif.
- **Terverifikasi:** ya

#### G4-06 [S] · pola P-11
Buat RFQ (desktop): pop-up `.modal-card` buatan; baris “Item *” tanpa kepala kolom (“Produk…”, “Qty” hanya placeholder); kotak satuan abu tampak isian padahal hanya-baca; supplier “Entitas grup” dikunci tanpa teks penjelas; segmented sumber #0058CC.

- **Lokasi layar / jalur klik:** Pembelian › RFQ / Penawaran › Buat RFQ (rfq #206).
- **Berkas:baris:** `frontend/src/features/purchasing/RFQCreateModal.jsx:90-103,127-163`
- **Perbaikan:** Kepala kolom Produk/Qty/Satuan; satuan sebagai teks; keterangan “Entitas grup — gunakan menu Antar Entitas”; warna aksen standar. (Konversi ke FormModal = L-03.)
- **Cek:** Item RFQ berkolom jelas.
- **Terverifikasi:** ya

#### G4-07 [S] · pola P-04
Kontrak: KPI & hitungan tab ikut tersaring tab (tab Kontrak Makloon → “TOTAL KONTRAK 8 · PEMBELIAN 0”); form kontrak meminta rumus kode `basis_qty * rate + colors * 150000` dengan daftar variabel teknis; placeholder PPI terpotong.

- **Lokasi layar / jalur klik:** Kontrak › tab Kontrak Makloon; Kontrak Baru (supplier-contracts #211/#220).
- **Berkas:baris:** `frontend/src/features/purchasing/contracts/ContractsView.jsx:100-103`; `frontend/src/features/purchasing/contracts/ContractFormModal.jsx:217`
- **Perbaikan:** Statistik dari seluruh kontrak (tanpa filter tab); variabel rumus diberi label manusia (chip “Qty dasar”, “Tarif”, “Jumlah warna”…) dan contoh; placeholder pendek.
- **Cek:** KPI tetap di semua tab.
- **Terverifikasi:** ya

#### G4-08 [S] · pola P-12
Harga internal: ubin “Sukacita → Kanda Fabric · 21 tanpa harga dari 135 barang ber-stok” vs editor “6 barang belum punya harga · 116 sudah” (6+116 ≠ 135); pasangan “dari 0 barang” berlabel “Lengkap” hijau; pop-up “Isi massal” tanpa kaki.

- **Lokasi layar / jalur klik:** Antar Entitas › Harga Internal; Kontrak › Isi massal harga internal (internal-prices #77/#78, supplier-contracts #217).
- **Berkas:baris:** `frontend/src/features/interco_prices/InternalPricesView.jsx:14-26`; `frontend/src/features/interco_prices/InternalPriceBulkPanel.jsx:85,116`; `backend/services/interco_price_service.py`
- **Perbaikan:** Satu fungsi hitung untuk ubin & editor (filter ber-stok sama); 0 barang → “Tidak ada barang ber-stok” abu; kaki Batal/Simpan.
- **Cek:** Angka ubin = angka editor untuk pasangan yang sama.
- **Terverifikasi:** lokasi ya; penyebab selisih belum terverifikasi

#### G4-09 [S] · pola P-13
Blanket PO: satu fitur empat nama (header, pil, kartu, pop-up); form mencampur gaya label; “Harga sepakat” dipakai untuk dua arti; teks PPN “Ikut pengaturan badan usaha” terpotong chevron; placeholder tak seragam; notasi “Σ qty×harga”.

- **Lokasi layar / jalur klik:** Pembelian › Blanket / Contract PO › Buat Kontrak (blanket-po #19/#20).
- **Berkas:baris:** `frontend/src/features/purchasing/BlanketPOCreateModal.jsx:15-17,161-265 (206,263-265)`
- **Perbaikan:** Nama tunggal di kartu & pop-up (ikut K-13; judul kepala di navMeta G0-17); label seragam; dropdown kedua “Kebijakan harga”; lebar select cukup; “0 = otomatis (jumlah qty × harga)”.
- **Cek:** Pop-up memakai satu nama fitur & label seragam.
- **Terverifikasi:** ya

#### G4-10 [S] · pola P-11
PR: kartu “Saran gabung PR → 1 PO” menampilkan dua saran identik (kunci supplier+gudang, tampil hanya nama situs); pop-up “Gabung 6 PR” dari saran CV Cipta Sandang tetapi SUPPLIER kosong; daftar pemasok tanpa kode & memuat badan usaha uji.

- **Lokasi layar / jalur klik:** Pembelian › Permintaan Pembelian (PR) › Saran gabung › Gabung kelompok ini › Pilih supplier (purchase-requisitions #160/#172/#173).
- **Berkas:baris:** `frontend/src/features/purchasing/PrMergePanel.jsx:27-31,44-46,62,86`; `backend/services/pr_sourcing_service.py:359-`; `frontend/src/features/purchasing/PurchaseRequisitions.jsx:172`
- **Perbaikan:** Tampilkan nama gudang tujuan pembeda (atau gabung saran yang sama); prefill supplier_id dari saran; label opsi “SUP-xxxx · Nama”, kecualikan entitas grup.
- **Cek:** Saran unik terbaca; pop-up gabung terisi supplier.
- **Terverifikasi:** ya

#### G4-11 [S] · pola P-01
Detail PR menunggu: “Batalkan” langsung POST /cancel tanpa konfirmasi/alasan (padahal Tolak wajib alasan); “Setujui” langsung; “DIBUAT OLEH seed”, “Butuh manager”, “2026-12-31”; dua pintu cetak.

- **Lokasi layar / jalur klik:** PR › detail PR menunggu (purchase-requisitions #176/#183).
- **Berkas:baris:** `frontend/src/features/purchasing/PurchaseRequisitionDetailPanel.jsx:86,165,172`
- **Perbaikan:** askReason untuk batal, askConfirm untuk setujui; actorLabel (“Sistem (data awal)”); “Perlu Manajer”; formatDate; satu tombol cetak (Pratinjau/Unduh PDF).
- **Cek:** Batalkan meminta alasan.
- **Terverifikasi:** ya

#### G4-12 [S] · pola P-12
Status PR tidak sinkron dengan PO: PR “Jadi PO” padahal PO-nya Dibatalkan; PR yang sudah punya PO tetap “Disetujui”; “Jadi PO” tanpa nomor PO.

- **Lokasi layar / jalur klik:** HP MD › Lainnya › Permintaan Pembelian vs Pantau PO Bahan (hp-md-aktifkan-notifikasi #28/#29, hp-md-cipta-sandang #107).
- **Berkas:baris:** `backend/services/purchase_requisition_service.py`; `backend/services/pr_sourcing_service.py:352-356`
- **Perbaikan:** Saat PO dibatalkan kembalikan baris PR ke “Disetujui” (catat di riwayat); status PR dihitung dari baris terealisasi; API menyertakan nomor PO agar daftar menampilkannya (tampilan HP → G5-60).
- **Cek:** PR yang PO-nya batal kembali “Disetujui” dengan catatan.
- **Terverifikasi:** belum terverifikasi (alur backend)

#### G4-13 [S] · pola P-13
Detail PO: istilah “Status Penagihan (Vendor Bill)”, “VENDOR BILL”, “Landed cost”, “Dokumen Goods Receipt”; termin ISO “2026-11-23”.

- **Lokasi layar / jalur klik:** Pesanan Pembelian › KSC/PO-00126 › Lihat detail lengkap (purchasing #191).
- **Berkas:baris:** `frontend/src/features/admin/po/PODetailPanel.jsx:68-98,276,384`
- **Perbaikan:** “Tagihan Supplier”, “Biaya Masuk (landed cost)” sesuai K-13, “Dokumen Penerimaan Barang”; formatDate. (Status mentah di panel alur → G5-51.)
- **Cek:** Panel PO tanpa istilah Inggris yang tidak ada di glosarium.
- **Terverifikasi:** ya

#### G4-14 [S] · pola P-05
Papan PO per Lini: tabel 9+ kolom bergulir samping di 1440; kolom pertama “NAMA SALES” bernilai “—” di semua baris; nama barang terpotong tanpa tooltip.

- **Lokasi layar / jalur klik:** Pembelian › Papan PO per Lini (po-board #143/#147).
- **Berkas:baris:** `frontend/src/features/purchasing/PoBoardView.jsx:41,151-160`
- **Perbaikan:** Kolom Nama Sales disembunyikan bila semua kosong / dipindah ke belakang; lebar kolom; `title` pada teks terpotong.
- **Cek:** Tabel muat 1440 tanpa kolom kosong di depan.
- **Terverifikasi:** ya

#### G4-15 [S]
Order Makloon “Dibatalkan” (MKO-00036) masih menampilkan tombol “Issue ke Makloon” di Langkah 1 serta Tanda Tangan/Kirim WA aktif; riwayat “Order dibuat (process_only)”.

- **Lokasi layar / jalur klik:** Makloon › Order Makloon › Detail MKO-00036 (makloon-orders #97/#99).
- **Berkas:baris:** `frontend/src/features/purchasing/MakloonOrderDetailPanel.jsx:39-45,316-322`; `backend/services/makloon_order_service.py:544`
- **Perbaikan:** `canIssue` & aksi dokumen false bila order cancelled; teks riwayat memakai label mode (“Proses saja”). (PDF SPK → G5-13.)
- **Cek:** Order batal tidak menawarkan Issue/TTD/WA.
- **Terverifikasi:** ya

#### G4-16 [S] · pola P-11
Mitra Makloon: form mencampur label biasa 11px dengan blok lokasi MAJUSCULE 10px; judul “Edit Makloon”/“Buat Makloon Baru” vs tombol “Ubah”/“Tambah Mitra Makloon”; “Ubah” dari detail menutup detail dan membuka pop-up di atas daftar.

- **Lokasi layar / jalur klik:** Makloon › Mitra Makloon › Tambah / detail › Ubah (makloons #90–#92).
- **Berkas:baris:** `frontend/src/features/purchasing/MakloonFormModal.jsx:75-88`; `frontend/src/features/purchasing/Makloon360Panel.jsx:14`
- **Perbaikan:** Judul “Ubah Mitra Makloon”/“Tambah Mitra Makloon”; label seragam (blok lokasi lewat prop G0-08); setelah simpan kembali ke detail.
- **Cek:** Ubah dari detail tetap kembali ke detail.
- **Terverifikasi:** ya

#### G4-17 [S]
Kategori Produk: ikon tempat sampah merah membuka “Nonaktifkan kategori …” (ikon bermakna hapus); judul “Edit Kategori”.

- **Lokasi layar / jalur klik:** Master › Kategori Produk (md-categories #122/#127).
- **Berkas:baris:** `frontend/src/features/admin/CategoryManager.jsx:8,84,110,207,242`
- **Perbaikan:** Ikon Power/⏻ seperti layar lain; “Ubah Kategori”.
- **Cek:** Ikon & judul konsisten.
- **Terverifikasi:** ya

#### G4-18 [S]
Produk & Varian › Tambah varian: pop-up “Buat kombinasi” mengusulkan 8 kombinasi yang SEMUANYA sudah ada (kartu “Kombinasi varian 8 SKU”) tanpa tanda “sudah ada”, tombol “Buat 8 kombinasi” tetap aktif.

- **Lokasi layar / jalur klik:** Produk & Varian › detail induk TEST_catalog_family… › Tambah varian (md-products #94/#99).
- **Berkas:baris:** `frontend/src/features/catalog/GenerateVariants.jsx:11-23`
- **Perbaikan:** Bandingkan dengan varian yang ada (kode/kombinasi sumbu); tandai “sudah ada”, hitung hanya yang baru, nonaktifkan bila 0.
- **Cek:** Untuk induk yang lengkap tombol menjadi “Semua kombinasi sudah ada” (nonaktif).
- **Terverifikasi:** ya

#### G4-19 [S] · pola P-02
Produk: jenis kain “woven” huruf kecil mentah di subjudul/kartu/tab Informasi; label sumbu “color × size × material”; satu tahap bernama “Kain Jadi · Woven”/“Finished (Jadi — dyed/printed)”/“Kain jadi”; kategori “Kain (nilai lama)”.

- **Lokasi layar / jalur klik:** Produk & Varian (md-products #91/#94/#95/#112).
- **Berkas:baris:** `frontend/src/features/catalog/CatalogWorkspace.jsx:53,72`; `frontend/src/features/catalog/FamilyInfoTab.jsx:17`; `frontend/src/features/catalog/FamilyHero.jsx:30`
- **Perbaikan:** Label dari registri domain (useDomainEnums / fabricLabel) untuk jenis kain & tahap; sumbu memakai label Indonesia.
- **Cek:** Tidak ada “woven”/“color × size” mentah.
- **Terverifikasi:** ya

#### G4-20 [S] · pola P-01
Satuan & Konversi: jejak konversi “100 meter → 109.36 yard” (titik) di samping faktor “1,093613”; waktu “24/10/2026, 11.22.29”; ⏻ “Nonaktifkan aturan” konversi global langsung POST; pop-up ubah aturan “0.01”.

- **Lokasi layar / jalur klik:** Master › Satuan & Konversi (md-uoms #108/#112/#113).
- **Berkas:baris:** `frontend/src/features/admin/uom/UomConversionParts.jsx:17,167-172`; `frontend/src/features/admin/uom/UomConversionView.jsx:90-96`
- **Perbaikan:** fmtNum untuk semua angka; formatDateTime; askConfirm danger untuk aturan global (sebut “dipakai PR/PO/penerimaan”); isian faktor id-ID.
- **Cek:** Angka berkoma seragam; nonaktifkan aturan meminta konfirmasi.
- **Terverifikasi:** ya

#### G4-21 [S] · pola P-02
Registri Domain: sel Matriks Transisi mencetak kode tahap mentah (“Grey · Woven”, “Pfd · Dye”, “Pfp · Print”, “Finished”, “Remnant”); petunjuk KPI “yarn → grey → pfd/pfp → finished”; istilah “Registry/ENUM/STAGE ASAL”.

- **Lokasi layar / jalur klik:** Pengaturan › Registri Domain Tekstil (domain-registry #1).
- **Berkas:baris:** `frontend/src/features/admin/domain/DomainRegistryParts.jsx:136-144`; `frontend/src/features/admin/domain/DomainRegistryView.jsx:96`
- **Perbaikan:** Pakai label tahap/tujuan/jenis kain dari registri (sama dengan kepala baris); petunjuk rantai berlabel Indonesia.
- **Cek:** Matriks memakai label yang sama dengan kepala baris.
- **Terverifikasi:** ya

#### G4-22 [S] · pola P-11
Produksi: “Buat Perintah Kerja” aktif walau belum ada BOM → pop-up “Perintah Kerja Baru” hanya berisi pesan + Tutup (buntu); form BOM Baru tanpa penanda wajib, isian berbentuk pil.

- **Lokasi layar / jalur klik:** Produksi In-House › Buat Perintah Kerja / BOM Baru (production #170/#172).
- **Berkas:baris:** `frontend/src/features/production/ProductionView.jsx:215-220`; `frontend/src/features/production/ProductionWO.jsx:135`
- **Perbaikan:** Nonaktifkan tombol dengan alasan + tautan “Buat BOM dulu”; * pada isian wajib; kelas `.field`.
- **Cek:** Tanpa BOM tombol nonaktif & menjelaskan langkah.
- **Terverifikasi:** ya

#### G4-23 [S] · pola P-11
Resep Proses: label campur sentence/MAJUSCULE; dua pemilih di bawah satu label; teks bantu “Rp 0” ganda; kotak rumus menyebut variabel `input_qty, yield_factor, waste_pct, byproduct_pct`; judul ubah “Edit Resep”.

- **Lokasi layar / jalur klik:** Makloon › Resep Proses › Buat Resep (process-recipes #153).
- **Berkas:baris:** `frontend/src/features/purchasing/RecipeFormModal.jsx:46,78,130`
- **Perbaikan:** Label seragam; variabel diberi nama manusia (“jumlah bahan”, “rendemen”…); satu teks bantu; “Ubah Resep”.
- **Cek:** Form tanpa nama variabel snake_case.
- **Terverifikasi:** ya

#### G4-24 [S] · pola P-12
Saran Reorder: Ulos Batak Ragidup “TERSEDIA 29” sementara Operasi Gudang “STOK FISIK 55 · TERSEDIA 0 · Habis” (roll RL-00015 diblokir) — reorder memakai `inventory_balances.available_qty`.

- **Lokasi layar / jalur klik:** Pembelian › Saran Reorder vs Operasi Gudang (reorder #188, operations #127).
- **Berkas:baris:** `backend/services/purchase_requisition_service.py:414-422`; `frontend/src/features/purchasing/ReorderSuggestions.jsx:155,196,245`
- **Perbaikan:** Setelah K-04 diputuskan: kurangi qty roll diblokir/karantina dari “Tersedia” reorder (atau tampilkan kolom “diblokir”); sampai itu, beri keterangan sumber di kolom.
- **Cek:** Angka Tersedia Ulos sama di dua layar atau berlabel beda.
- **Terverifikasi:** lokasi ya; definisi menunggu K-04

#### G4-25 [S]
Rekap Susut & Klaim Mitra Makloon: kerangka beda dari tab saudara (judul 15px sejajar toolbar, label “Dari/Sampai tanggal” melayang, dropdown “Semua mitra” tampak nonaktif); KPI Rp 0 merah/hijau.

- **Lokasi layar / jalur klik:** Makloon › Rekap Susut & Klaim (makloon-claim-recap #118).
- **Berkas:baris:** `frontend/src/features/purchasing/makloon/MakloonClaimRecapView.jsx:65-86`
- **Perbaikan:** Pakai PageHeader/kartu seperti tab Klaim; toolbar dalam kartu; 0 warna netral.
- **Cek:** Tab-tab makloon sekerangka.
- **Terverifikasi:** ya

#### G4-26 [R]
Landed Cost: KPI “SISA HUTANG BIAYA Rp 0” & kolom Sisa selalu merah; pemilihan PO di pop-up berupa daftar centang 140 px tanpa cari; tiga nama satu layar.

- **Lokasi layar / jalur klik:** Pembelian › Landed Cost (landed-cost #86/#87).
- **Berkas:baris:** `frontend/src/features/purchasing/LandedCostView.jsx:121,131,156-178`; `frontend/src/features/purchasing/LandedCostCreateModal.jsx:152-173`
- **Perbaikan:** Warna hanya bila > 0; kotak cari PO; satu nama (K-13).
- **Cek:** Nol tidak merah; PO bisa dicari.
- **Terverifikasi:** ya

#### G4-27 [R]
Retur ke Supplier: kolom AKSI berganti gaya per status (ikon tanpa label); detail tabel roll 7 kolom untuk baris tanpa roll; “Simpan keputusan roll (0)” di draf; dua dasar nilai berdampingan.

- **Lokasi layar / jalur klik:** Pembelian › Retur ke Supplier (purchase-returns #173/#179).
- **Berkas:baris:** `frontend/src/features/purchasing/PurchaseReturns.jsx:517`; `frontend/src/features/purchasing/ReturnDetailPanel.jsx:193`
- **Perbaikan:** Aksi berlabel konsisten; sembunyikan tabel roll bila tanpa roll; satu dasar nilai berlabel.
- **Cek:** Kolom aksi seragam.
- **Terverifikasi:** ya

#### G4-28 [R]
Order Makloon wizard: “Batal” kiri & “Lanjut” kanan (beda pola); isian wajib “Alasan qty bahan manual” muncul sebelum produk dipilih; nomor “MKO-00036” tanpa prefiks entitas & mono; “Scorecard”.

- **Lokasi layar / jalur klik:** Makloon › Order Makloon › Wizard (makloon-orders #96, makloons #96).
- **Berkas:baris:** `frontend/src/features/purchasing/makloon/MakloonWizard.jsx`; `frontend/src/features/purchasing/Makloon360Panel.jsx:14`
- **Perbaikan:** Kaki standar; isian alasan muncul setelah produk tanpa resep dipilih; “Skor Mitra”. (Prefiks nomor → K-09.)
- **Cek:** Wizard mengikuti pola kaki standar.
- **Terverifikasi:** ya

#### G4-29 [R]
Produk: form “SKU baru” tanpa kotak “Produk Unggulan…” yang ada di “Ubah SKU”; “Kode SKU” wajib tanpa *; harga mentah “12000”; pop-up “Induk produk baru” dengan tombol “+ Asal/+ Warna…” ganda; “Mockup dengan Gemini”.

- **Lokasi layar / jalur klik:** Produk & Varian › SKU baru / Ubah SKU / Produk baru (md-products #92/#108/#111).
- **Berkas:baris:** `frontend/src/features/catalog/VariantEditor.jsx:30-44`; `frontend/src/features/catalog/FamilyForm.jsx`; `frontend/src/features/catalog/AxisEditor.jsx`
- **Perbaikan:** Form buat = ubah; * ; MoneyInput; hapus tombol sumbu ganda; “Buat mockup (AI)”.
- **Cek:** Form SKU buat & ubah sama.
- **Terverifikasi:** ya

#### G4-30 [R]
Daftar PO: chip “Belum Bayar 30” ikut menghitung PO Ditolak/Dibatalkan.

- **Lokasi layar / jalur klik:** Pembelian › Pesanan Pembelian (PO) (purchasing #188).
- **Berkas:baris:** `frontend/src/features/admin/PurchaseOrderManagement.jsx (filter bayar)`
- **Perbaikan:** Kecualikan PO batal/ditolak dari chip Belum Bayar.
- **Cek:** Chip hanya menghitung PO aktif.
- **Terverifikasi:** lokasi chip belum dipastikan

### G5 — R&D/desain/sample, SDM, marketing, dokumen-PDF/ekspor, pengaturan-entitas-izin-persetujuan + aplikasi HP Ops & MD

T 16 · S 47 · R 7

**Berkas milik grup (hanya grup ini yang boleh mengedit):**

- `frontend/src/features/rnd/**`
- `frontend/src/features/design/**`
- `frontend/src/features/designer/**`
- `frontend/src/features/hr/**`
- `frontend/src/features/marketing/**`
- `frontend/src/features/documents/**`
- `frontend/src/features/pdf/**`
- `frontend/src/features/export/**`
- `frontend/src/features/settings/**`
- `frontend/src/features/approvals/**`
- `frontend/src/features/tanya/**`
- `frontend/src/features/admin/AdminView.jsx`
- `frontend/src/features/admin/IntegrationsPanel.jsx`
- `frontend/src/features/admin/GeminiIntegrationPanel.jsx`
- `frontend/src/features/admin/OpenAiIntegrationPanel.jsx`
- `frontend/src/features/admin/scheduler/**`
- `frontend/src/features/mobile/MobileOpsApp.jsx`
- `frontend/src/features/mobile/MobileApprovalInbox.jsx`
- `frontend/src/features/sales/mobile/MobileMdApp.jsx`
- `frontend/src/features/sales/mobile/MobileMdViews.jsx`
- `backend/services/pdf_resolvers.py`
- `backend/services/pdf_engine.py`
- `backend/services/escalation_service.py`
- `backend/services/turn_notification_service.py`
- `backend/services/notification_service.py`
- `backend/services/rnd_sample_service.py`
- `backend/services/design_request_service.py`
- `backend/services/hr_payroll_service.py`
- `backend/services/export_registry.py`
- `backend/services/export_registry_more.py`
- `backend/services/export_engine.py`

> Grup terbesar — bila perlu dipecah dua agen, pecah per folder: (G5a) rnd/design/designer/hr/marketing + backend rnd/design/hr; (G5b) documents/pdf/export/settings/approvals/tanya/admin/mobile Ops & MD + backend pdf/export/notifikasi. Jangan memecah satu berkas ke dua agen.

#### G5-01 [T] · pola P-02
Jejak Audit: baris menampilkan kunci aksi mono (`login`, `reservation_expired`), “user • user_09145fb56bb0”, “system • sales_order • so_ccce17337008”, JSON mentah `{"email":…,"role":"designer"}`; laci rincian berbunyi “Dicatat oleh … pada user”, PERAN “system/demo” (padahal JSON designer), tombol “Tetap di Audit”.

- **Lokasi layar / jalur klik:** Pengaturan › Integrasi & Audit › tab Jejak Audit (+ klik baris, Tampilkan 50 lagi) (admin #6/#7/#9).
- **Berkas:baris:** `frontend/src/features/admin/AdminView.jsx:479 (baris & facts/cta)`
- **Perbaikan:** Tampilkan hanya `auditActionLabel(key)`; aktor = nama; sumber daya = label modul + nomor dokumen (bukan id); data tambahan diringkas (“Email: …, Peran: Desainer”) atau di balik “Lihat data teknis” (admin); peran di laci dari data yang sama; tombol “Tutup”. (Label Indonesia baru → G0-16.)
- **Cek:** Jejak audit tanpa id/JSON mentah di tampilan bawaan.
- **Terverifikasi:** ya

#### G5-02 [T] · pola P-02
Cek Peran: paragraf ±30 baris teks 10px “Catatan kejujuran cakupan: 283 jenis kegiatan belum dipetakan ke izin (approval_matrix_approve, …)” di SEMUA filter, sementara kartu vonis (Sesuai/Kuasa Berlebih) tanpa peringatan bahwa hanya 50/333 kegiatan dinilai; “Lihat bukti” memuat izin mentah “wms.update/order.deliver” & id “wms_d67d0d53980b · so_854aa6b2bc83”.

- **Lokasi layar / jalur klik:** Badan Usaha & Akses › Cek Peran (› Lihat bukti) (entities-access #50/#51, permission-matrix #170/#171).
- **Berkas:baris:** `frontend/src/features/settings/entities/RoleRealityPanel.jsx:273-277,385-395,468-474`
- **Perbaikan:** Banner peringatan ringkas di atas kartu (“Vonis dihitung dari 50 dari 333 jenis kegiatan”); daftar kode di `<details>` “Lihat daftar teknis”; Lihat bukti: label izin (peta modul/aksi) + nomor dokumen saja; perbaiki key fragment di rows.map (peringatan React).
- **Cek:** Tab Cek Peran tanpa dinding kode; Lihat bukti tanpa id teknis; konsol tanpa peringatan key.
- **Terverifikasi:** ya

#### G5-03 [T] · pola P-02
Master per Badan Usaha: kode internal di tabel & banner — Aturan Persetujuan `discount`/`purchase_order`/`sales_order` + “manager”, batas diskon persen dicetak “Rp 0 – Rp 10”; Tahapan Proses `tenun/rajut/pre_treatment` + banner `process_type`, `changes_stage=false`, `material_flow`; Alasan Keluhan banner `needs_inspection`, `claimable`; Template Dokumen `invoice`, `surat_jalan`; Lini Produk “benang · tenun · celup · inspect”.

- **Lokasi layar / jalur klik:** Pengaturan › Master per Badan Usaha › kelompok di kartu kiri (entity-masters #29–#31, #36, #37).
- **Berkas:baris:** `frontend/src/features/settings/masters/masterFieldsConfig.js:80-125,275-289`; `frontend/src/features/settings/masters/EntityMastersView.jsx:435`
- **Perbaikan:** Kolom berjenis enum diberi peta label (jenis dokumen, peran via roleLabel, proses, tahap); banner tanpa backtick/kode; kolom persen diformat “%”.
- **Cek:** Tidak ada kode snake_case/backtick di kelompok tersebut.
- **Terverifikasi:** ya

#### G5-04 [T]
Presensi › Impor Sidik Jari: placeholder textarea menampilkan “\n” mentah (“user_id,timestamp\n1001,…”) karena string atribut JSX.

- **Lokasi layar / jalur klik:** SDM › Presensi & Kehadiran › tab Impor Sidik Jari (hr-attendance #75).
- **Berkas:baris:** `frontend/src/features/hr/AttendanceView.jsx:317`
- **Perbaikan:** `placeholder={"user_id,timestamp\n1001,2026-05-04 08:01:00\n…"}` (ekspresi JS) agar baris baru nyata.
- **Cek:** Placeholder tampil tiga baris tanpa “\n”.
- **Terverifikasi:** ya

#### G5-05 [T] · pola P-09
Permintaan Desain: thumbnail kartu Papan memakai `<img src>` polos (tanpa header badan usaha & tanpa onError) → ikon gambar rusak bawaan peramban / kotak putih kosong; “Gambar referensi · 1 gambar” di pop-up rincian kotak abu kosong — padahal ReferenceGallery sudah lewat axios.

- **Lokasi layar / jalur klik:** Desain › Permintaan Desain › Papan (KSC/DSR-00053/-00043) › Detail (design-requests #1/#4).
- **Berkas:baris:** `frontend/src/features/design/DesignRequestsView.jsx:61-64`; `frontend/src/features/design/ReferenceGallery.jsx:40-52 (acuan)`
- **Perbaikan:** Thumbnail memakai mekanisme yang sama dengan ReferenceGallery (unduh blob via axios ber-header / `useBlobUrl`) + fallback teks “Gambar tidak dapat dimuat”.
- **Cek:** Thumbnail tampil bila berkas ada; bila 404 tampil teks fallback, bukan ikon peramban.
- **Terverifikasi:** ya

#### G5-06 [T] · pola P-09
Detail DSR › desain tertaut: `<img>` sampul tanpa onError → teks alt “Kawung Navy” tumpah di kotak thumbnail.

- **Lokasi layar / jalur klik:** HP Desainer › Desktop › Permintaan Desain › Daftar › Detail KSC/DSR-00001 (hp-designer-desktop #11).
- **Berkas:baris:** `frontend/src/features/design/LinkedDesignsPanel.jsx:21`
- **Perbaikan:** Pakai DesignImage (atau onError → fallback) sehingga alt tidak tumpah.
- **Cek:** Sampul 404 menampilkan fallback rapi.
- **Terverifikasi:** ya

#### G5-07 [T] · pola P-05
Detail desain di HP: kepala 3 kolom tanpa tata letak HP — kode “DS / GEN- / 001” pecah per huruf dan tertutup tombol ⟳/“Ubah”; metadata turun satu kata per baris; tab detail patah 3 baris.

- **Lokasi layar / jalur klik:** HP MD › Lainnya › Galeri & Studio Desain › kartu DSN-GEN-001 / INT-ABS-AO-001 (hp-md-lainnya #16, hp-md-pasang-sekarang #51/#52).
- **Berkas:baris:** `frontend/src/features/rnd/design/DesignDetailPage.jsx:76-118,126-131`
- **Perbaikan:** `flex-col sm:flex-row`; kolom aksi turun di bawah info di < 640px; kode `whitespace-nowrap`; tab detail bergulir horizontal dengan penanda.
- **Cek:** Di 390 kode desain terbaca utuh dan tidak tertutup tombol.
- **Terverifikasi:** ya

#### G5-08 [T] · pola P-07
HP Ops: tab Persetujuan & Antrean diberikan ke SEMUA peran — Desainer/Admin Sample melihat “Permission ditolak: approval.view” mentah di Antrean; 403 price-approvals/special-orders di Persetujuan disamarkan jadi “Tidak ada … yang menunggu”.

- **Lokasi layar / jalur klik:** HP Desainer/Admin Sample/Finance › Antrean & Persetujuan (hp-designer-antrean #5, hp-sample_admin-antrean #100, hp-designer-persetujuan #3, hp-finance-persetujuan).
- **Berkas:baris:** `frontend/src/features/mobile/MobileOpsApp.jsx:22-27,101-112`; `frontend/src/features/mobile/MobileApprovalInbox.jsx:16-17,30`
- **Perbaikan:** Bentuk daftar tab dari izin (`can(perms,'approval','view')`, `can(perms,'price_approval','approve') || can(perms,'special_order','approve')`); QueuePanel memakai `apiErrorText`; MobileApprovalInbox membedakan 403 (“Anda tidak punya akses ke harga khusus”) dari daftar kosong.
- **Cek:** Login desainer HP: tab Antrean/Persetujuan tidak tampil; peran ber-izin tetap melihat daftar.
- **Terverifikasi:** ya

#### G5-09 [T] · pola P-10
Notifikasi HP: lencana “Putuskan di HP” dipasang dari regex teks dan selalu membuka tab Persetujuan yang tidak memuat dokumennya (PO custom SORD lain, “Persetujuan ulang bayar sample KSC/SOS-00054”, “Harga menunggu persetujuan”); notifikasi lain hanya ditandai dibaca tanpa membuka dokumen.

- **Lokasi layar / jalur klik:** HP admin/manager/finance/sample_admin › Notifikasi › klik kartu (hp-admin-notifikasi #7, hp-manager-notifikasi #25, hp-finance-notifikasi #18, hp-sample_admin-notifikasi #99).
- **Berkas:baris:** `frontend/src/features/mobile/MobileOpsApp.jsx:86-100`
- **Perbaikan:** Lencana hanya bila `action_type` ∈ {price_approval, special_order} DAN dokumennya ada di daftar Persetujuan; klik notifikasi lain membuka dokumen lewat `link`/utils/docLink (atau “Buka di tampilan desktop” ke view terkait); lencana dihapus untuk notifikasi yang tak bisa diputus di HP.
- **Cek:** Setiap notifikasi berlencana bisa diputus di tab tujuan; notifikasi lain membuka dokumennya.
- **Terverifikasi:** ya

#### G5-10 [T] · pola P-02
Notifikasi: kode mentah “tahap: shipped” / “tahap: refund_settled” (STAGE_LABEL HP tak lengkap; teks dirakit server), eskalasi “Belum ditindak 55 jam … oleh all.”, Meja Saya “tahap: cancelled/rejected”.

- **Lokasi layar / jalur klik:** HP Notifikasi (admin/finance/manager), Meja Saya (my-desk #119, hp-finance-notifikasi #17, hp-admin-notifikasi #6).
- **Berkas:baris:** `frontend/src/features/mobile/MobileOpsApp.jsx:13-20`; `backend/services/turn_notification_service.py:140`; `backend/services/escalation_service.py:115-116`
- **Perbaikan:** Server: `tahap: <label Indonesia>` (peta status bersama) dan peran dengan label (“all” → “semua peran”, pakai label peran); HP: humanizeNotif memakai docStatusLabel sebagai fallback.
- **Cek:** Tidak ada “shipped/refund_settled/all” di teks notifikasi baru.
- **Terverifikasi:** ya

#### G5-11 [T] · pola P-06
PDF dokumen (Pratinjau/Unduh): bulan Inggris “25 Oct 2026”; label “PPN 12.0%” pada nominal 11% efektif tanpa baris DPP nilai lain; qty “353.79 yard”; teks QR “Atau buka localhost:3063 › Jejak Dokumen”.

- **Lokasi layar / jalur klik:** Pusat Dokumen › ikon mata KSC/SO-00505; Pengaturan › Desainer Template PDF › pratinjau (document-center #21, pdf-templates #133/#149).
- **Berkas:baris:** `backend/services/pdf_resolvers.py:12-16,218`; `backend/services/pdf_engine.py:174-180`
- **Perbaikan:** `fmt_date` dengan nama bulan Indonesia; total: baris “DPP nilai lain (11/12)” + “PPN 12%” (format sesuai K-03); qty id-ID; host QR dari pengaturan publik (sembunyikan bila localhost).
- **Cek:** PDF SO menampilkan “25 Okt 2026”, DPP & PPN yang menjumlah benar, tanpa “localhost”.
- **Terverifikasi:** ya

#### G5-12 [T]
PDF Surat Jalan Transfer Antar-PT: “PT Asal: Jakarta · Gudang Sukacita” dan “PT Tujuan: Jakarta · Gudang Sukacita” (nama gudang, sama) padahal transfer Sukacita → Kanda Fabric; “Dibuat oleh -”; “23 Oct 2026”.

- **Lokasi layar / jalur klik:** Operasi Gudang › Transfer › KSC/TRF-00003 › Pratinjau (operations #149).
- **Berkas:baris:** `backend/services/pdf_resolvers.py:552-571`
- **Perbaikan:** PT dari entitas sumber/tujuan; gudang di baris tersendiri; dibuat oleh = nama pengaju; tanggal Indonesia.
- **Cek:** PDF menyebut Sukacita → Kanda Fabric dan pembuatnya.
- **Terverifikasi:** ya

#### G5-13 [T] · pola P-02
PDF SPK Makloon (untuk mitra): “Mode process_only”, “24 Oct 2026”, “5337.91” tanpa pemisah, kolom PROSES “-” padahal langkahnya printing.

- **Lokasi layar / jalur klik:** Makloon › Order Makloon › Detail MKO-00036 › Pratinjau (makloon-orders #98).
- **Berkas:baris:** `backend/services/pdf_resolvers.py:504 (±490-530)`
- **Perbaikan:** Label mode (“Proses saja”), tanggal Indonesia, angka id-ID, isi kolom proses dari langkah.
- **Cek:** PDF SPK makloon tanpa kode/format Inggris.
- **Terverifikasi:** ya

#### G5-14 [T] · pola P-02
Pratinjau ekspor (dan berkas unduhan) Pesanan Penjualan: STATUS “shipped/confirmed/cancelled/reserved/waiting_stock/approved”, TAHAP “Shipped/Reserved…”, JENIS “regular/sample”; SO-00295 “waiting_stock” bertahap “Reserved”.

- **Lokasi layar / jalur klik:** Laporan › Pusat Export › Buat ekspor › Pesanan Penjualan (SO) › Pratinjau (export-center #66).
- **Berkas:baris:** `backend/services/export_registry.py:47-61`; `frontend/src/features/export/PreviewTable.jsx:30-36`
- **Perbaikan:** Kolom status/tahap/jenis pakai peta label Indonesia di registri ekspor (berlaku untuk pratinjau & berkas); periksa sumber kolom Tahap vs Status.
- **Cek:** Pratinjau & CSV berlabel Indonesia.
- **Terverifikasi:** lokasi ya; kontradiksi status/tahap belum terverifikasi

#### G5-15 [T] · pola P-07
Kesehatan Konfigurasi (MD): galat “Permission ditolak: settings.view” lalu tepat di bawahnya kartu hijau “Semua setting aktif benar-benar tersambung … Diperiksa 0 setting … Tidak ada tombol palsu” + 4 KPI 0 — vonis sukses walau data gagal.

- **Lokasi layar / jalur klik:** HP MD › Spesifikasi Produk › Kebijakan R&D › Kesehatan Konfigurasi (hp-md-spesifikasi-produk #159–#163).
- **Berkas:baris:** `frontend/src/features/settings/config/ConfigHealthPanel.jsx:74-92`
- **Perbaikan:** Bila `err` (atau data null) jangan render vonis & KPI; sembunyikan tab untuk peran tanpa settings.view.
- **Cek:** MD tidak melihat vonis hijau tanpa data.
- **Terverifikasi:** ya

#### G5-16 [T] · pola P-02
Detail sample › tab Proofing: catatan memuat kode keputusan “(keputusan pemilik, MD-05)” — penyaring stripCodes hanya dipakai di galeri.

- **Lokasi layar / jalur klik:** R&D › Labdip/Handfeel/Proofing › kartu KSC/SMP-00017 › tab Proofing (hp-md-lainnya #11, rnd-handfeel #223).
- **Berkas:baris:** `frontend/src/features/rnd/SampleTypeTabs.jsx:97-99`; `frontend/src/features/rnd/SampleTypeGalleryView.jsx:39`
- **Perbaikan:** Pakai `stripInternalCodes` (utils/cleanText) di tab & galeri (hapus stripCodes lokal).
- **Cek:** Tab Proofing tanpa “MD-05”.
- **Terverifikasi:** ya

#### G5-17 [S]
Master Data: klik baris (Pelanggan, Template Dokumen, Satuan) membuka laci “DETAIL INSIGHT” berbunyi “gunakan tombol di baris ini untuk mengubah atau menonaktifkan” padahal baris hanya punya “Nonaktifkan”; isi hanya MODUL & STATUS “aktif”; satuan nonaktif tanpa status & tanpa “Aktifkan”.

- **Lokasi layar / jalur klik:** Pengaturan › Master Data (customers-master #28–#31), Template Dokumen Dasar (#77), Satuan & Konversi (md-uoms #114).
- **Berkas:baris:** `frontend/src/features/admin/AdminView.jsx:521,553-562`
- **Perbaikan:** Klik baris membuka tempat kerja yang bermakna (pelanggan → CRM 360; template → pratinjau/ubah; satuan → aturan konversi) atau tidak membuka apa pun; status berlabel; baris nonaktif punya “Aktifkan”.
- **Cek:** Tidak ada laci yang menyuruh memakai tombol yang tidak ada.
- **Terverifikasi:** ya

#### G5-18 [S] · pola P-11
Master Data › Buat Pelanggan: Kota bawaan “Jakarta” untuk setiap pelanggan baru; placeholder mengulang label; “Rp 0” ganda pada batas kredit; hanya Nama bertanda *. (Keberadaan form ini menunggu keputusan duplikasi D-05.)

- **Lokasi layar / jalur klik:** Pengaturan › Master Data › Buat Pelanggan (customers-master #27).
- **Berkas:baris:** `frontend/src/features/admin/AdminView.jsx:91,228,353-360`
- **Perbaikan:** Kota kosong bawaan; placeholder contoh “mis. …”; satu teks bantu; * sesuai aturan backend.
- **Cek:** Form baru tidak berisi Jakarta otomatis.
- **Terverifikasi:** ya

#### G5-19 [S]
Template Dokumen Dasar: tidak ada cara mengubah template; pop-up “Buat Template Dokumen” — deskripsi generik “Isian Template Dokumen baru.”, “Kolom (pisahkan koma)” teks bebas, URL logo teks, Orientasi sendirian, ▲ baris pertama aktif, “Catatan kaki” terpotong kaki pop-up.

- **Lokasi layar / jalur klik:** Pengaturan › Template Dokumen Dasar › Buat Template Dokumen (doc-templates-basic #76).
- **Berkas:baris:** `frontend/src/features/admin/AdminView.jsx:326,389-411,561-562`
- **Perbaikan:** Tambahkan aksi Ubah; deskripsi spesifik; pemilih kolom (chip) atau minimal contoh; ▲ nonaktif di baris pertama/▼ di terakhir; daftar urutan di dalam area gulir.
- **Cek:** Template bisa diubah; daftar urutan tidak terpotong.
- **Terverifikasi:** ya

#### G5-20 [S] · pola P-01
Aturan Persetujuan: “PERAN PENYETUJU *” wajib tetapi teks bantu “Kosong = … lolos tanpa persetujuan” dan opsi “Tanpa persetujuan (lolos otomatis)”; badge “Aktif” langsung PATCH tanpa konfirmasi sementara ikon tempat sampah membuka “Nonaktifkan aturan”; istilah “Manager”, “mesin approval”, “Gagal toggle status”.

- **Lokasi layar / jalur klik:** Pengaturan › Aturan Persetujuan › Buat/ikon pensil; badge Aktif; ikon sampah (approval-rules #2–#6).
- **Berkas:baris:** `frontend/src/features/settings/ApprovalRuleForm.jsx:42-52`; `frontend/src/features/settings/ApprovalRulesSettings.jsx:9,122-125,145,257,266-272`; `frontend/src/features/settings/approvalRulesConstants.js:15`
- **Perbaikan:** Hapus * (isian boleh kosong = lolos) atau hapus opsi kosong — pilih satu sesuai backend; badge Aktif → askConfirm (atau jadikan label saja dan pakai satu tombol ⏻); ikon ⏻; “Manajer”, “mesin persetujuan”, “Gagal mengubah status”.
- **Cek:** Satu cara menonaktifkan aturan, dengan konfirmasi; penanda wajib konsisten.
- **Terverifikasi:** ya

#### G5-21 [S]
Pusat Persetujuan: ringkasan “4 di daftar bawah · 65 di layar lain” padahal daftar 5 baris; untuk Sales: banner “belum lengkap: 5 kategori tidak bisa ditampilkan” + kosong “Semua keputusan sudah ditindaklanjuti” + tab 0 (7 GET 403), padahal Beranda menunjukkan 2 pesanan menunggu; payroll “KSC/PR-00002 · Payroll” bentrok awalan PR- dan periode mentah “2026-08”.

- **Lokasi layar / jalur klik:** Inbox Persetujuan (approval-inbox #2); HP Sales › Beranda › Buka Pusat Persetujuan (hp-sales-beranda #42).
- **Berkas:baris:** `frontend/src/features/approvals/ApprovalInbox.jsx:310,344-347,402,435`; `backend/services/hr_payroll_service.py:375`
- **Perbaikan:** Hitungan dari daftar yang dirender; bila ada kategori tak terbaca jangan tampilkan “semua beres” (“Sebagian kategori tidak bisa ditampilkan untuk peran Anda”); label jenis “Penggajian” + formatPeriod. Ganti awalan nomor payroll baru → keputusan K-09.
- **Cek:** Ringkasan = jumlah baris; sales tidak melihat pesan kontradiktif.
- **Terverifikasi:** ya

#### G5-22 [S]
Persetujuan Saya: kolom TINGKAT dua gaya untuk hal sama (“Tingkat 1/1 · Manager” pil abu vs “○ 1. Manager” oranye); PENGAJU berupa email mentah “admin@kainnusantara.id”.

- **Lokasi layar / jalur klik:** Persetujuan Saya · Matriks Divisi (my-approvals #130).
- **Berkas:baris:** `frontend/src/features/approvals/MyApprovalsView.jsx:96-117,308-311`
- **Perbaikan:** Satu komponen pil tingkat; pengaju = nama (actorLabel/nama pengguna), email hanya di tooltip; “Manajer”.
- **Cek:** Kolom tingkat seragam; tidak ada email sebagai nama.
- **Terverifikasi:** ya

#### G5-23 [S] · pola P-13
Akun & Akses: tiap baris menumpuk 3–4 tombol vertikal (Ubah/Reset/Cabut sesi/Nonaktifkan, baris 100–130 px), “Reset” ambigu, PERAN patah 4 baris; nama peran beda antar tab (dua ROLE_OPTIONS: “Sales (lapangan)” vs “Sales”); warna chip aktif berbeda dalam satu bilah (biru #007AFF vs ungu #6B219A vs hitam).

- **Lokasi layar / jalur klik:** Badan Usaha & Akses › Akun & Akses / Badan Usaha / Cek Peran (entities-access #34/#39/#42/#50, permission-matrix #159/#164).
- **Berkas:baris:** `frontend/src/features/settings/entities/AccountList.jsx:18,117,146,179,188-208,344-365`; `frontend/src/features/settings/entities/EntityList.jsx:99,114,126`; `frontend/src/features/settings/entities/RoleRealityPanel.jsx:23,203-217`
- **Perbaikan:** Aksi baris: “Ubah” + menu ⋯ (Reset sandi, Cabut sesi, Nonaktifkan); satu sumber nama peran (config/roles roleLabel + label pendek untuk tabel); satu warna chip aktif (biru).
- **Cek:** Baris akun satu tinggi baris normal; nama peran sama di semua tab.
- **Terverifikasi:** ya

#### G5-24 [S] · pola P-11
Buat Akun Baru: kotak merah “Nama wajib diisi / Email wajib diisi” sudah tampil saat dibuka; tanpa satu pun penanda *; istilah “PASSWORD AWAL”, “(HOME)”, “EMAIL (UNTUK MASUK)”; Ubah Akun tidak menyorot karyawan tertaut.

- **Lokasi layar / jalur klik:** Akun & Akses › Buat Akun / Ubah (entities-access #40/#41, permission-matrix #165/#166).
- **Berkas:baris:** `frontend/src/features/settings/entities/AccountFormDrawer.jsx:74-83,192,263,375-380`
- **Perbaikan:** Galat setelah submit/touched; * pada Nama/Email/Sandi awal; “Sandi awal”, “Badan usaha utama”; tampilkan karyawan tertaut terpilih.
- **Cek:** Form baru bersih saat dibuka; wajib bertanda.
- **Terverifikasi:** ya

#### G5-25 [S] · pola P-11
Detail Badan Usaha (ubah): “Simpan Perubahan” di tengah kartu; isian “NAMA PEMILIK/LABEL USAHA (PERORANGAN)” tampil untuk PT; “AWAL TAHUN FISKAL (MM-DD)” teks bebas; KOTA teks bebas (wizard buat memakai kaskade wilayah); “Contoh nomor berikutnya: KSC/SO-00001” padahal sudah KSC/SO-00505.

- **Lokasi layar / jalur klik:** Badan Usaha & Akses › Badan Usaha › klik Sukacita Textile (entities-access #37, permission-matrix #162).
- **Berkas:baris:** `frontend/src/features/settings/entities/EntityDetailDrawer.jsx:15-27,185,239-240`
- **Perbaikan:** Tombol simpan di kaki; isian perorangan hanya untuk jenis perorangan; pemilih bulan-tanggal; LocationFields seperti wizard; contoh nomor dari penghitung nyata (atau hapus).
- **Cek:** Form ubah sejalan dengan wizard buat.
- **Terverifikasi:** ya

#### G5-26 [S] · pola P-01
Master per Badan Usaha: tabel Tahapan Proses & Alasan Keluhan lebih lebar dari kartu (tombol “Buat khusus Sukacita” di luar layar); banner bertentangan soal letak Tarif Insentif (“Pengaturan › Rate Insentif” vs “CRM › Tarif Insentif”); “Simpan baris” aktif walau Kode*/Nama* kosong; “Jadikan Global” tanpa peringatan; “Buat khusus …” langsung POST.

- **Lokasi layar / jalur klik:** Master per Badan Usaha (entity-masters #27–#34).
- **Berkas:baris:** `frontend/src/features/settings/masters/EntityMastersView.jsx:17,51-52,300-375`
- **Perbaikan:** Tabel `overflow-x-auto` dengan aksi `sticky right-0`; satu banner yang benar; tombol nonaktif sampai wajib terisi; “Jadikan Global” dengan teks peringatan + askConfirm; askConfirm untuk Buat khusus.
- **Cek:** Aksi baris selalu terlihat; tidak ada banner kontradiktif.
- **Terverifikasi:** ya

#### G5-27 [S] · pola P-01
Master Grade Mutu: ubah baris inline mengganti “Ubah” jadi “Simpan” tanpa Batal (kolom bergeser ±50px); setiap baris memuat isian permanen “Alasan aktif/nonaktif”; placeholder “1 = tert” terpotong.

- **Lokasi layar / jalur klik:** Pengaturan › Master Grade Mutu (grade-master #73/#74).
- **Berkas:baris:** `frontend/src/features/settings/masters/GradeMasterView.jsx:27-41,91`
- **Perbaikan:** Tambah Batal & lebar kolom tetap; alasan diminta lewat askReason saat Nonaktifkan/Aktifkan; isian urutan lebih lebar.
- **Cek:** Ubah bisa dibatalkan; tabel tanpa isian alasan permanen.
- **Terverifikasi:** ya

#### G5-28 [S] · pola P-11
Form SDM berbentuk Sheet (Shift/Geofence/Perangkat, Tambah/Edit Karyawan): kaki terbalik (tombol utama lebar penuh di kiri, Batal kanan), judul “Edit …”, tanpa penanda wajib, placeholder mirip nilai (“Shift Reguler”, “-6.917464”, “Bank BCA”, “1234567890”); istilah “Salin device_token”, endpoint `/api/hr/attendance/ingest`, “Serial Number”; status satu nilai tiga nama (“Keluar (resign)”/“Resigned”/“Tandai Resigned”).

- **Lokasi layar / jalur klik:** Pengaturan › Shift & Geofence (hr-attendance-setup #45–#51); SDM › Karyawan › Tambah/Edit/Resign (hr-employees #47/#49/#56).
- **Berkas:baris:** `frontend/src/features/hr/AttendanceSetupView.jsx:140-205`; `frontend/src/features/hr/EmployeeFormDrawer.jsx:15-16,106-108`; `frontend/src/features/hr/Employee360Panel.jsx:101`; `frontend/src/features/hr/EmployeesView.jsx:236-238`
- **Perbaikan:** Kaki: Batal kiri, utama kanan (ukuran normal); “Ubah …”; * pada isian wajib; placeholder “mis. …”; “Salin token perangkat”, sembunyikan endpoint di teks bantu admin; status “Keluar” di semua tempat (“Tandai Keluar”).
- **Cek:** Form SDM berpola kaki standar; tidak ada “Resigned/device_token”.
- **Terverifikasi:** ya

#### G5-29 [S] · pola P-01
Cuti & Lembur: pemilih “KARYAWAN *” memuat karyawan yang sudah Keluar di urutan teratas; dialog Batalkan Cuti bertombol “Batal” vs “Batalkan” (mudah tertukar) dengan alasan tak wajib; ✓ Setujui langsung POST (✗ Tolak berdialog); periode ISO “2026-10-26 → …”, filter “2026-10”; tab Ditolak/Dibatalkan berpesan umum.

- **Lokasi layar / jalur klik:** SDM › Kehadiran › Cuti & Izin / Lembur › Ajukan untuk Karyawan, ikon ✓/⊘ (hr-leave #3–#6/#12/#13, hr-overtime #16/#17).
- **Berkas:baris:** `frontend/src/features/hr/LeaveView.jsx:56,133-134,204,211,217-218,238,279-280,292`; `frontend/src/features/hr/OvertimeView.jsx:49,151`
- **Perbaikan:** Saring karyawan aktif; tombol tutup “Kembali”, eksekusi “Batalkan cuti” (danger, alasan wajib); askConfirm untuk Setujui; formatDate/formatPeriod/KNMonthPicker; pesan kosong per status; 0 tanpa warna peringatan.
- **Cek:** Karyawan keluar tidak bisa dipilih; Setujui meminta konfirmasi.
- **Terverifikasi:** ya

#### G5-30 [S]
Profil Saya (ESS): pop-up “Ajukan Cuti / Lembur” `.modal-card` polos (tanpa ×, deskripsi, penanda wajib) berbeda dari versi admin; kartu “KPI Saya (R&D)” desainer tampil untuk Direktur.

- **Lokasi layar / jalur klik:** SDM › Profil Saya › Cuti & Lembur Saya › Ajukan (hr-my-profile #53/#54).
- **Berkas:baris:** `frontend/src/features/hr/MyLeaveCard.jsx:114-126`; `frontend/src/features/hr/EmployeeSelfService.jsx:199-209`
- **Perbaikan:** Pakai FormModal + * (seperti hr-leave #2); render MyDesignerKpiCard hanya bila peran desainer/R&D.
- **Cek:** ESS memakai pop-up standar; Direktur tidak melihat kartu KPI desainer.
- **Terverifikasi:** ya

#### G5-31 [S] · pola P-11
Presensi: panel inline “Entry Manual” — 5 isian tanpa label, tanggal/jam terpotong, tanpa Batal; validasi “Import” kosong jadi banner galat global dengan “Coba lagi” (memuat ulang data harian); tombol Import aktif walau kosong; input berkas bawaan “Choose File”; istilah “Entry Manual/Perlu Review/Alpha/Import/Multi-punch/Idempoten”.

- **Lokasi layar / jalur klik:** SDM › Presensi & Kehadiran › Entry Manual; Impor Sidik Jari › Import (hr-attendance #70/#71/#75/#76).
- **Berkas:baris:** `frontend/src/features/hr/AttendanceView.jsx:19-22,143,167,199,204,209-215,279,312,323,330-332`
- **Perbaikan:** Entry manual sebagai FormModal berlabel (KNDatePicker/KNTimePicker lebar cukup, Batal); validasi inline di dekat form; Import nonaktif bila kosong; tombol unggah berlabel Indonesia; istilah “Input manual”, “Perlu ditinjau”, “Alpa”, “Impor”.
- **Cek:** Tidak ada banner global untuk validasi impor.
- **Terverifikasi:** ya

#### G5-32 [S]
Struktur Organisasi: konfirmasi “Nonaktifkan · Gudang & Operasional” memakai kalimat umum lalu tetap menyalakan tombol merah, padahal unit punya 2 jabatan & 3 karyawan (pasti gagal).

- **Lokasi layar / jalur klik:** SDM › Struktur Organisasi › ikon ⏻ (hr-org-units #63–#65).
- **Berkas:baris:** `frontend/src/features/hr/OrgUnitsView.jsx:183,202,216-224`
- **Perbaikan:** Bila sub-unit/karyawan > 0: dialog menyebut hambatannya (“3 karyawan aktif”) dan tombol nonaktif.
- **Cek:** Unit berisi tidak bisa dicoba dinonaktifkan.
- **Terverifikasi:** ya

#### G5-33 [S] · pola P-01
Penggajian: “Posting GL” (jurnal gaji Rp 45,3 jt) dan “Sahkan” langsung POST; tombol berwarna sendiri (cokelat #B7791F, hijau #1F7A45); istilah “Run/Hitung Run/payslip/Take-Home”, pesan “Gagal posting gl.”.

- **Lokasi layar / jalur klik:** SDM › Penggajian › KSC/PR-00001 › Posting GL / Sahkan (hr-payroll-runs #82/#83).
- **Berkas:baris:** `frontend/src/features/hr/PayrollRunsView.jsx:67-68,111-161`
- **Perbaikan:** askConfirm (periode, total, akibat jurnal); `.primary-button`; istilah Indonesia (“Hitung gaji Oktober 2026”, “slip gaji”, “Gaji bersih”).
- **Cek:** Posting & Sahkan meminta konfirmasi.
- **Terverifikasi:** ya

#### G5-34 [S]
Kunjungan Sales: filter Status (OptionTabs) dijejalkan ke kolom ¼ sehingga tab patah tiga baris; KPI memakai “Periode KPI: Oktober 2026” sementara tabel “Dari/Sampai 25 Okt” → “Belum ada kunjungan” tanpa keterangan.

- **Lokasi layar / jalur klik:** SDM › Kunjungan Sales (hr-visits #67).
- **Berkas:baris:** `frontend/src/features/hr/VisitsView.jsx:93-115`
- **Perbaikan:** OptionTabs di baris sendiri/selebar kartu; KPI mengikuti rentang tabel atau diberi label “Periode KPI” yang jelas terpisah.
- **Cek:** Tab status satu baris; KPI & tabel tidak tampak bertentangan.
- **Terverifikasi:** ya

#### G5-35 [S] · pola P-06
KPI Karyawan: pop-up Tambah/Edit `.modal-card` polos tanpa ×; “Edit KPI”; desimal campur (“107,4” vs kolom SKOR “94.4”); periode mentah “2026-10”; galat muat karyawan ditelan (`catch (_) { /* noop */ }`); rumus “min(aktual/target, 1.5) × 100”.

- **Lokasi layar / jalur klik:** SDM › KPI Karyawan › Tambah KPI / pensil (cs-kpi #43–#48).
- **Berkas:baris:** `frontend/src/features/hr/KpiView.jsx:39,91,124,159,163,184-185,209`
- **Perbaikan:** FormModal; “Ubah KPI”; skor formatDecimal; formatPeriod; tampilkan galat muat; rumus jadi kalimat (“Skor otomatis = capaian ÷ target, maks 150%”).
- **Cek:** Tidak ada titik desimal/periode ISO; galat muat terlihat.
- **Terverifikasi:** ya

#### G5-36 [S]
Dasbor BI SDM: tanpa data absensi KPI “Kehadiran 0%” & “Ketepatan 0%” (terbaca semua absen) padahal sub-teks “0 hari hadir” dan panel “Belum ada data absensi”.

- **Lokasi layar / jalur klik:** SDM › Dasbor BI SDM (cs-bi-hrd #52).
- **Berkas:baris:** `frontend/src/features/hr/HrAnalyticsView.jsx:116-117`
- **Perbaikan:** Tampilkan “—” bila tidak ada hari kerja tercatat (seperti KPI gaji).
- **Cek:** Periode tanpa absensi menampilkan “—”.
- **Terverifikasi:** ya

#### G5-37 [S] · pola P-04
Permintaan Desain: KPI TOTAL & badge “Semua” ikut tersaring tab status/lini (Draf → “TOTAL 0 · Semua 0”); tab/lini kosong berpesan “Belum ada permintaan desain…”; Rapor Desainer memperlakukan “Belum ditugaskan” sebagai desainer (DITUGASKAN 8, % ACC 0%) dan menumpuk dua deret KPI; kolom ACC papan terpotong di kanan; detail tanpa ×; konfirmasi “Batalkan permintaan desain” biru.

- **Lokasi layar / jalur klik:** Desain › Permintaan Desain › tab status, LINI Woven, Rapor Desainer, Papan › Disetujui (ACC), Detail (design-requests #1/#7/#10/#12/#18, hp-designer-desktop #14/#20).
- **Berkas:baris:** `frontend/src/features/design/DesignRequestsView.jsx:126-151,229-233,279-313`; `frontend/src/features/design/DesignerReportPanel.jsx:65,110`; `backend/services/design_request_service.py:764-772`; `frontend/src/features/design/DesignRequestDetailPanel.jsx:100,278-281`
- **Perbaikan:** Ringkasan diambil tanpa param status/lini; pesan kosong per filter; baris tanpa penugasan dipisah sebagai “Belum ditugaskan” (bukan desainer, tanpa % ACC); kolom ACC dapat dicapai (lebar kolom/ gulir dengan penanda); askReason `danger:true`.
- **Cek:** TOTAL tetap 9 di semua tab; rapor tanpa baris “Belum ditugaskan” sebagai desainer.
- **Terverifikasi:** ya

#### G5-38 [S] · pola P-01
KPI Desainer: panel “Cara nilai dihitung” menjumlah bobot 40% + 40% + 20% + 20% = 120%; tabel peringkat 15+ kolom bergulir di 1440 tanpa kolom DESAINER beku; “Semua divisi” hanya placeholder; “Kirim peringatan sekarang” (WA ke manajer) tanpa konfirmasi; round/ronde campur.

- **Lokasi layar / jalur klik:** Desain › KPI Desainer (designer-kpi #9–#16).
- **Berkas:baris:** `frontend/src/features/designer/designerMeta.js:50-58`; `frontend/src/features/designer/DesignerKpiView.jsx:105,137-138,157,331`
- **Perbaikan:** Periksa sumber bobot (report.weights) — normalisasi/penjelasan sesuai K-08; kolom DESAINER `sticky left-0`; sembunyikan filter divisi bila kosong; askConfirm sebelum eskalasi; istilah “ronde”.
- **Cek:** Total bobot 100% (atau dijelaskan); nama desainer tetap terlihat saat tabel digulir.
- **Terverifikasi:** lokasi ya; sumber bobot backend belum terverifikasi

#### G5-39 [S] · pola P-09
Gambar desain gagal dimuat hanya berupa ikon 14px tanpa teks (berbeda dengan kartu tanpa sampul “Tanpa gambar”); berkas desain “1 berkas” tetapi sampul ikon rusak.

- **Lokasi layar / jalur klik:** Galeri Desain, Desain & Pattern (cs-design-gallery #26/#27, rnd-designs #169/#171).
- **Berkas:baris:** `frontend/src/features/rnd/design/DesignImage.jsx:8`
- **Perbaikan:** Fallback: ikon + teks “Gambar tidak dapat dimuat” mengikuti ukuran wadah.
- **Cek:** Kartu dengan berkas 404 menampilkan teks fallback.
- **Terverifikasi:** ya

#### G5-40 [S] · pola P-13
Galeri Desain › Showcase: istilah campur (“Kategori design”, “Tetapkan customer label”, “White label”, “0 repeat”), “Spesifikasi cetak: Repeat — · 0 screen”; tab status dianggap filter (“× Hapus 1 filter”) dengan pesan umum.

- **Lokasi layar / jalur klik:** Galeri Desain › kartu INT-ABS-AO-001; tab ACC (cs-design-gallery #27/#31–#35).
- **Berkas:baris:** `frontend/src/features/hr/DesignShowcaseModal.jsx:28,114,120`; `frontend/src/features/hr/DesignOwnershipPanel.jsx:111`; `frontend/src/features/hr/DesignGalleryView.jsx:75,108-113,127-131`
- **Perbaikan:** Istilah Indonesia (K-13); sembunyikan bagian kosong; tab status tidak dihitung sebagai filter; pesan kosong per status. (Tombol × → G0-07.)
- **Cek:** Showcase tanpa tanda pisah menggantung.
- **Terverifikasi:** ya

#### G5-41 [S] · pola P-04
Desain & Pattern: navigasi tanggal `<input type=date>` bawaan (“dd/mm/yyyy”, 10,5px) yang patah 4 baris di HP; 11 dropdown filter tanpa label (sebagian abu tampak nonaktif); hitungan tab status = semua baris termuat (`rows.length`).

- **Lokasi layar / jalur klik:** Desain › Desain & Pattern (rnd-designs #169; HP MD #49).
- **Berkas:baris:** `frontend/src/features/rnd/design/DateQuickNav.jsx:48-63`; `frontend/src/features/rnd/RndDesignsView.jsx:125,195-211`
- **Perbaikan:** KNDatePicker; label ringkas/aria + warna teks seragam; hitungan per status dari ringkasan server (bukan rows.length).
- **Cek:** Tab status menampilkan jumlah masing-masing status.
- **Terverifikasi:** ya

#### G5-42 [S]
Detail desain: dialog “Setujui (ACC) + nilai akhir” menampilkan nilai “0” sudah terpilih (`Number(null) === 0`), lalu galat “Beri nilai akhir…”; dua tombol utama berdampingan (“Mulai review” & “Setujui”); “Ajukan untuk review” bisa dijalankan dengan 0 berkas; badge “Finished · …/On progress”; dialog siklus tanpa × & deskripsi.

- **Lokasi layar / jalur klik:** Desain & Pattern › detail DSN-GEN-001 / INT-BTK-PG-004 / INT-ABS-AO-001 (rnd-designs #176/#181/#184/#194).
- **Berkas:baris:** `frontend/src/features/rnd/design/ScoreInput.jsx:9,33`; `frontend/src/features/rnd/design/LifecycleActions.jsx:12-14,95-149`; `frontend/src/features/rnd/design/ProofingPanel.jsx:58`
- **Perbaikan:** `active = value !== null && value !== undefined && Number(value) === s`; satu tombol primary (yang lain secondary); nonaktifkan Ajukan bila 0 berkas (alasan terlihat); “Selesai/Berjalan”; dialog berkepala standar.
- **Cek:** Dialog ACC terbuka tanpa nilai terpilih; Ajukan nonaktif tanpa berkas.
- **Terverifikasi:** ya

#### G5-43 [S]
Divisi & Persetujuan R&D: anggota dengan divisi tersimpan (Rina Merchandiser, Yoga Admin Sample) tampil “Pilih…” abu; judul “R&D” tapi tabel memuat semua karyawan; “APPROVER/Manager” vs “Manajer”; dropdown per baris langsung menyimpan.

- **Lokasi layar / jalur klik:** R&D › Divisi & Persetujuan R&D (rnd-divisions #189/#193).
- **Berkas:baris:** `frontend/src/features/designer/DivisionsView.jsx:68-72,90-91,187,257-293`
- **Perbaikan:** Tambahkan opsi untuk divisi yang tersimpan tapi tak ada di daftar (atau “Divisi tidak dikenal: X”); judul sesuai isi (“Divisi & Persetujuan”); “Penyetuju”, “Manajer”; simpan dengan konfirmasi/umpan balik.
- **Cek:** Tidak ada anggota bertanda “Pilih…” padahal punya divisi.
- **Terverifikasi:** ya

#### G5-44 [S] · pola P-04
Sample R&D: hitungan tab aktif = jumlah semua sample (“Gagal — menunggu PIC 12” pada daftar kosong); form Handfeel/Proofing/Uji Ulang memakai contoh labdip (“Labdip Katun Combed…”, “ΔE 1.5”); “Sample Labdip Baru” buntu — isian wajib handfeel induk hanya “— belum ada handfeel ACC —” tanpa tautan; subjudul uji ulang “saat ACC … SKU lahir” bertentangan dengan isi.

- **Lokasi layar / jalur klik:** R&D › Handfeel/Labdip/Proofing/Uji Ulang SKU › Filter, Sample … Baru (rnd-handfeel #217/#243, rnd-labdip #214, rnd-proofing #198, rnd-revalidation #253; Pustaka Warna › Buat Labdip).
- **Berkas:baris:** `frontend/src/features/rnd/SampleTypeGalleryView.jsx:174-175`; `frontend/src/features/rnd/SampleFormModal.jsx:153-156,208,224,235,253`
- **Perbaikan:** Hitungan per status dari ringkasan; contoh placeholder per jenis; tautan “Buat sample handfeel dulu” di isian kosong; subjudul per tujuan (uji ulang: “tidak membuat SKU/spesifikasi baru”).
- **Cek:** Tab kosong tidak berhitungan 12; form labdip menunjukkan jalan keluar.
- **Terverifikasi:** ya

#### G5-45 [S]
Detail sample: kepala “dari KSC/SPEC-00430” tetapi kartu “Belum ada spesifikasi — data lama”; “Ubah spesifikasi” hanya 6 isian (konstruksi, warna, desain, induk tak bisa diubah); “Dibuat oleh: Ayu Marketing” vs riwayat “dibuat … Dewi Manager”; “Dikirim: Belum” padahal stepper “2. Terkirim ✓”; “Terima sampel fisik” → pop-up “Tandai Sample Jadi” → “Tandai Jadi”; “Batalkan permintaan” biru; tombol utama “Pilih pemenang” (nonaktif) lebih menonjol dari langkah yang disarankan.

- **Lokasi layar / jalur klik:** R&D › Labdip/Handfeel/Proofing › kartu KSC/SMP-00451/-00454/-00017/-00018 (rnd-handfeel #219–#226, hp-md-proofing #196, hp-md-riwayat-labdip #166/#169/#174).
- **Berkas:baris:** `frontend/src/features/rnd/SampleDetailPanel.jsx:120,171,174-187,279-308,316-365`; `frontend/src/features/rnd/SampleSpecPanel.jsx:37-40,122-148`; `frontend/src/features/rnd/SampleFinishModal.jsx:28`
- **Perbaikan:** Satu sumber spesifikasi (bila spec_number ada, muat kartunya); form ubah spesifikasi = form buat (isian sama); “Diajukan oleh” vs “Dibuat oleh” jelas; ringkasan pengiriman dari ronde; satu nama aksi (“Terima sampel fisik”); askReason `danger:true`; primary = langkah berikutnya.
- **Cek:** Detail sample tidak saling bertentangan.
- **Terverifikasi:** lokasi ya; sumber “Dikirim: Belum” belum terverifikasi

#### G5-46 [S] · pola P-13
Riwayat sample memuat teks mentah backend: “Round 1 (labdip · CV Grey Mandiri Majalaya) → acc · skor 92”, “QC acc”, “dibuat (draft)”, “Dikirim: 1 round dibuka … target 2026-10-30”; satu konsep disebut ronde/round/putaran.

- **Lokasi layar / jalur klik:** Detail sample › Riwayat; Kirim Permintaan ke Supplier (rnd-labdip #216, rnd-proofing #202, hp-md-proofing #196, hp-md-riwayat-labdip #173).
- **Berkas:baris:** `backend/services/rnd_sample_service.py:818-822,1045-1047`; `frontend/src/features/rnd/SampleRoundList.jsx:180`; `frontend/src/features/rnd/SampleSendModal.jsx:64,122`
- **Perbaikan:** Teks timeline server memakai “Ronde”, label hasil (“ACC”, “revisi”), tanggal Indonesia; frontend “ronde” di semua tempat.
- **Cek:** Riwayat & pop-up kirim hanya memakai “ronde”.
- **Terverifikasi:** ya

#### G5-47 [S]
Kirim Permintaan ke Supplier: “PT Uji Provisioning …” (entitas grup) tampil sebagai supplier biasa yang bisa dipilih, padahal di Buat RFQ dikunci berlencana “Entitas grup”.

- **Lokasi layar / jalur klik:** Detail sample › Kirim ke supplier (rnd-handfeel #224).
- **Berkas:baris:** `frontend/src/features/rnd/SampleSendModal.jsx:91-122`
- **Perbaikan:** Tandai/ kecualikan entitas grup seperti RFQ.
- **Cek:** Entitas grup tidak bisa dipilih sebagai supplier sample.
- **Terverifikasi:** ya

#### G5-48 [S]
Riwayat Labdip per warna: KPI “PERMINTAAN 10” tetapi tabel “Belum ada putaran labdip untuk warna KN-BLU-01” — 10 permintaan tak terlihat & tak bisa dibuka.

- **Lokasi layar / jalur klik:** Pustaka Warna › ikon riwayat kartu KN-BLU-01 (color-library #41).
- **Berkas:baris:** `frontend/src/features/rnd/LabdipHistoryModal.jsx:40-57`
- **Perbaikan:** Tampilkan daftar permintaan (bukan hanya putaran) atau KPI hanya menghitung yang tampil; baris bisa dibuka; kolom “RND” → “Sample”.
- **Cek:** KPI = jumlah baris yang bisa dibuka.
- **Terverifikasi:** lokasi ya; penyebab data belum terverifikasi

#### G5-49 [S] · pola P-02
Detail Spesifikasi Produk: “Woven (tenun) · finished” (kode tahap mentah), “0 gsm · 0 cm” & “Target harga Rp 0” untuk nilai kosong.

- **Lokasi layar / jalur klik:** R&D › Spesifikasi Produk › klik KSC/SPEC-00751 (rnd-specs #235).
- **Berkas:baris:** `frontend/src/features/rnd/SpecDetailPanel.jsx:88-92`
- **Perbaikan:** Label tahap dari registri; nilai kosong “—”.
- **Cek:** Detail spesifikasi tanpa “finished”/“0 gsm” untuk kosong.
- **Terverifikasi:** ya

#### G5-50 [S] · pola P-12
Pusat Dokumen: kolom NILAI KSC/SO-00505 “Rp 202.318” (subtotal sebelum PPN) sementara PDF & CRM “Rp 224.573”, tanpa keterangan; Tanda Tangan Elektronik & Kirim via WhatsApp tetap ditawarkan untuk dokumen “Dibatalkan”; pop-up WA/TTD/Kirim tanpa Batal & kaki.

- **Lokasi layar / jalur klik:** Laporan › Pusat Dokumen (document-center #19–#23).
- **Berkas:baris:** `frontend/src/features/documents/DocumentCenter.jsx:181,211-217`; `frontend/src/features/documents/ESignModal.jsx:166`; `frontend/src/features/documents/WhatsAppSettings.jsx:103`
- **Perbaikan:** Kolom berlabel “Nilai (DPP)” atau tampilkan grand total sesuai K-03; sembunyikan TTD/WA untuk status batal; kaki Batal/aksi.
- **Cek:** Nilai berlabel jelas; dokumen batal tanpa TTD/WA.
- **Terverifikasi:** ya

#### G5-51 [S] · pola P-02
Panel dokumen bersama “Alur Dokumen Terkait” & “Referensi Dokumen”: status mentah UPPERCASE (CANCELLED/COMPLETED/DONE) + lencana “AKTIF” (terbaca kontradiktif untuk SO batal), “posted”, “qc_pending”, “closed”, “draft”, id `wms_6870951e5c`, “sales_order / sales_cogs”.

- **Lokasi layar / jalur klik:** Pesanan › detail SO › Alur dokumen (orders #134/#150/#152); Pesanan Pembelian › Lihat detail lengkap (purchasing #191).
- **Berkas:baris:** `frontend/src/features/documents/ProcessTimeline.jsx:72-75`; `frontend/src/features/documents/trace/DocRefsPanel.jsx:50-55`
- **Perbaikan:** docStatusLabel untuk status; lencana anchor “Dokumen ini”; label jenis dokumen/sumber jurnal; sembunyikan id teknis bila ada nomor.
- **Cek:** Panel alur & referensi tanpa kode mentah di SO & PO.
- **Terverifikasi:** ya

#### G5-52 [S]
Pusat Export: admin melihat “TIDAK TERSEDIA UNTUK PERAN ANDA: Amandemen Dokumen, Mutasi Kredit Toko Pelanggan”; kolom teknis “ID badan usaha”/“ID roll” terpilih bawaan; pratinjau “405 baris cocok” vs 150 SO di Pusat Dokumen.

- **Lokasi layar / jalur klik:** Laporan › Pusat Export (export-center #55/#56/#59/#66).
- **Berkas:baris:** `frontend/src/features/export/DatasetPicker.jsx:41-43`; `backend/services/export_registry.py`; `backend/services/export_registry_more.py`
- **Perbaikan:** Periksa izin dataset untuk admin (registri); kolom ID tidak terpilih bawaan; label cakupan (termasuk SO sample/badan usaha lain?).
- **Cek:** Admin melihat semua dataset; kolom ID tidak terpilih bawaan.
- **Terverifikasi:** belum terverifikasi (izin dataset)

#### G5-53 [S]
Desainer Template PDF: dua tombol simpan berbeda cakupan (“Simpan Template” vs “Simpan Branding”) tanpa penjelasan & pratinjau tidak memperlihatkan kop sebelum Simpan Branding; isian Field Tambahan/Slot TTD tanpa label (placeholder terpotong); “Sembunyikan Field (meta)” teks bebas; “Disimpan sebagai base64”.

- **Lokasi layar / jalur klik:** Pengaturan › Template PDF › tab Kop Surat / Field Tambahan (pdf-templates #140/#142/#148/#150).
- **Berkas:baris:** `frontend/src/features/pdf/PdfTemplateDesigner.jsx:249`; `frontend/src/features/pdf/PdfEditorTabs.jsx:116-118,213,231,278-306`
- **Perbaikan:** Teks penjelas cakupan di dekat kedua tombol (atau satu tombol Simpan semua); pratinjau memakai draf branding; label kolom; hapus “base64”.
- **Cek:** Pengguna tahu apa yang disimpan tiap tombol.
- **Terverifikasi:** ya

#### G5-54 [S]
Dashboard Sosmed: grafik “Tren 6 bulan · jangkauan (batang)” tanpa satu batang pun (tinggi persen di kolom flex tanpa tinggi).

- **Lokasi layar / jalur klik:** Marketing › Dashboard Sosmed (mkt-analytics #118).
- **Berkas:baris:** `frontend/src/features/marketing/MarketingAnalytics.jsx:46-52`
- **Perbaikan:** Wadah batang `flex-1 w-full flex items-end` dengan tinggi tetap (mis. h-28) di antara label.
- **Cek:** Batang Okt 26 (100) terlihat.
- **Terverifikasi:** ya

#### G5-55 [S] · pola P-02
Kalender Konten › PIC: opsi menampilkan kode peran mentah “(sales)”, “(admin)”, “(designer)”, “(sales_admin)”.

- **Lokasi layar / jalur klik:** Marketing › Kalender Konten › Konten baru › PIC (mkt-calendar #124).
- **Berkas:baris:** `frontend/src/features/marketing/PostFormModal.jsx:88`
- **Perbaikan:** `roleLabel(u.role)`.
- **Cek:** PIC “Nadia Putri (Admin Sales)”.
- **Terverifikasi:** ya

#### G5-56 [S] · pola P-01
HP Persetujuan: dialog Setujui generik (“Setujui pesanan khusus …?”, deskripsi “x”, tombol “Konfirmasi”, tanpa nilai Rp & catatan) berbeda dari papan desktop (Setujui + catatan + Rp); dialog Tolak “Alasan penolakan pesanan khusus” tanpa nomor/pelanggan, tombol biru “Konfirmasi”; kartu “target Rp 45.000” tanpa satuan.

- **Lokasi layar / jalur klik:** HP admin/finance/manager/sample_admin › Persetujuan › Setujui/Tolak (hp-admin-persetujuan #2/#3/#5, sample_admin #93/#94).
- **Berkas:baris:** `frontend/src/features/mobile/MobileApprovalInbox.jsx:21-24,45-46`
- **Perbaikan:** askConfirm: judul nomor dokumen, message pelanggan + Rp, `confirmLabel:'Setujui'`, catatan opsional (askText/withReason opsional); askReason: judul “Tolak <nomor> · <pelanggan>”, `confirmLabel:'Tolak'`, danger; “target Rp 45.000/meter”.
- **Cek:** Dialog HP setara papan desktop.
- **Terverifikasi:** ya

#### G5-57 [S] · pola P-10
HP Notifikasi: setiap eskalasi tampil 2× berurutan; satu SORD muncul dengan dua pelanggan; nomor dokumen patah di tengah (“SRET-/00158”, “KSC/SOS-/00014”); tidak ada judul/jumlah/“Tandai semua dibaca” untuk 1.259 notifikasi.

- **Lokasi layar / jalur klik:** HP admin/manager/sample_admin › Notifikasi (hp-admin-notifikasi #6, hp-manager-notifikasi #24, hp-sample_admin-notifikasi #98).
- **Berkas:baris:** `backend/services/escalation_service.py:108-126`; `frontend/src/features/mobile/MobileOpsApp.jsx:86-100`
- **Perbaikan:** Dedupe eskalasi per notifikasi sumber (bukan per depth+hari) — periksa `dedupe_scope`; judul `break-words` diganti pembungkus yang menjaga token nomor (`whitespace-nowrap` per nomor); kepala daftar dengan jumlah & “Tandai semua dibaca”. Dua pelanggan per SORD → cek data (lihat Data uji).
- **Cek:** Satu eskalasi per dokumen; nomor tidak patah.
- **Terverifikasi:** lokasi ya; penyebab dobel belum terverifikasi

#### G5-58 [S]
HP Ops: tab Ringkas untuk Desainer & Admin Sample berisi angka gudang/penjualan (stok 4 satuan, Roll, Pelanggan) tanpa angka pekerjaannya; bilah bawah 7 tab di 390 px (label tepi terpotong); tab “Desktop” hanya satu tombol.

- **Lokasi layar / jalur klik:** HP Desainer/Admin Sample › Ringkas; HP admin › bilah bawah (hp-designer-ringkas #6, hp-sample_admin-ringkas #101, hp-admin-antrean #8).
- **Berkas:baris:** `frontend/src/features/mobile/MobileOpsApp.jsx:53-68,101-125`
- **Perbaikan:** KPI Ringkas per peran (desainer: DSR berjalan/tenggat; admin sample: antrean SOS/menunggu bayar) — isi menunggu K-12; maksimal 5 tab (gabung Desktop ke app bar); label ≥ 11px.
- **Cek:** Bilah bawah ≤ 5 tab tanpa label terpotong.
- **Terverifikasi:** ya

#### G5-59 [S] · pola P-11
HP MD: form “Permintaan desain baru” & “Buat PR bahan” memakai placeholder sebagai label (Kategori, Brief *, Jumlah, Est. harga, Alasan *), `<input type=date>` bawaan, Jumlah tanpa satuan & harga tanpa Rp, dua tautan kembali; Meja: tanggal tanpa label, dialog “Batalkan KSC/DSR-00004?” bertombol generik “Konfirmasi”, “ACC desain” langsung menulis.

- **Lokasi layar / jalur klik:** HP MD › Desain › Permintaan desain baru; Permintaan Pembelian › Buat PR bahan; Meja › KSC/DSR-00004 (hp-md-desain #38, hp-md-permintaan-pembelian #123, hp-md-meja #32–#36).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileMdViews.jsx:131-142,156-160,181,197,493-509`
- **Perbaikan:** Label di atas isian + *; KNDatePicker; satuan & “Rp”; satu tautan kembali + judul form; askReason dengan `confirmLabel:'Batalkan permintaan'`; askConfirm untuk ACC desain.
- **Cek:** Form HP MD berlabel; ACC meminta konfirmasi.
- **Terverifikasi:** ya

#### G5-60 [S]
HP MD › Permintaan Pembelian: judul kartu terpotong tepat di nomor pembeda (“Pemenuhan Pesanan Khusus SORD-261024-0…”, 12 dari 17 kartu tak terbedakan); “Jadi PO” tanpa nomor PO; “Pantau PO Bahan” “kirim - ·” saat tanggal kosong; chip status bergulir tanpa penanda.

- **Lokasi layar / jalur klik:** HP MD › Lainnya › Permintaan Pembelian (PR) / Pantau PO Bahan (hp-md-lainnya #2/#3, hp-md-permintaan-pembelian #122).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileMdViews.jsx:536-546,578`
- **Perbaikan:** Judul `line-clamp-2` atau nomor SORD di baris sendiri; tampilkan nomor PO terkait (data dari G4-12); sembunyikan “kirim -”; penanda gulir chip.
- **Cek:** Setiap kartu PR bisa dibedakan dan menyebut PO-nya.
- **Terverifikasi:** ya

#### G5-61 [S] · pola P-02
Pengaturan (dibuka dari Kebijakan R&D): kartu setting menampilkan kunci teknis (`rnd.lifecycle_enforcement`), backtick markdown literal & kode “(KN-D16)”; setting “(Lama) … TIDAK DIPAKAI LAGI” berlencana hijau “Aktif & tersambung”; tombol “Kebijakan R&D” membuka SELURUH Pusat Pengaturan untuk MD; Riwayat Perubahan berkolom “entity: ent_ks…”.

- **Lokasi layar / jalur klik:** HP MD › Spesifikasi Produk › Kebijakan R&D (hp-md-spesifikasi-produk #148/#153/#164).
- **Berkas:baris:** `frontend/src/features/settings/config/SettingCard.jsx:57-105`; `frontend/src/features/settings/config/ConfigDrawers.jsx:86,323,386`; `frontend/src/features/rnd/RndSpecsView.jsx:114-116`
- **Perbaikan:** Sembunyikan kunci (tooltip admin); render teks bantu dengan pembersih backtick + stripInternalCodes; setting usang berlencana abu “Tidak dipakai”; deep link membuka kelompok R&D saja (filter grup); cakupan pakai nama badan usaha.
- **Cek:** MD hanya melihat kelompok R&D tanpa kode/backtick.
- **Terverifikasi:** ya

#### G5-62 [S]
Tanya KN di HP: bilah tab Tanya/Laporan/Peringatan/Riwayat/Jadwal/Biaya bergulir tanpa penanda (label terpotong di kedua tepi); tombol saran ke-3 tertutup kotak input chat.

- **Lokasi layar / jalur klik:** HP Finance › Tanya (hp-finance-tanya #21–#26).
- **Berkas:baris:** `frontend/src/features/tanya/TanyaKnView.jsx:116`; `frontend/src/features/tanya/TanyaChatPane.jsx:26-28`; `frontend/src/features/tanya/TanyaChatBox.jsx:34`
- **Perbaikan:** Penanda gulir (bayangan tepi) atau tab 2 baris ikon; area saran diberi `padding-bottom` setinggi kotak input.
- **Cek:** Semua saran dapat diketuk; tab terbaca.
- **Terverifikasi:** ya

#### G5-63 [S]
HP MD mode “Semua badan usaha” (hanya-lihat) tetapi “+ Sample Labdip Baru” tetap aktif.

- **Lokasi layar / jalur klik:** HP MD › Lainnya (Semua) › Riwayat Labdip (hp-md-semua #64).
- **Berkas:baris:** `frontend/src/features/rnd/SampleTypeGalleryView.jsx (tombol buat)`
- **Perbaikan:** Nonaktifkan tombol buat bila scope Semua (utils/writeScope).
- **Cek:** Di mode Semua tidak bisa membuka form buat.
- **Terverifikasi:** berkas ya; baris tombol belum dipastikan

#### G5-64 [R]
Integrasi AI: checkbox auto-tag biru vs Gemini ungu; “Simpan Konfigurasi” vs “Simpan Kunci” beda kelas; “Filter Jejak Audit” melayang di luar kartu; tiga judul satu layar.

- **Lokasi layar / jalur klik:** Pengaturan › Integrasi & Audit (admin #1/#4/#6).
- **Berkas:baris:** `frontend/src/features/admin/IntegrationsPanel.jsx:76`; `frontend/src/features/admin/GeminiIntegrationPanel.jsx:85`; `frontend/src/features/admin/OpenAiIntegrationPanel.jsx:43`; `frontend/src/features/admin/AdminView.jsx:276-281`
- **Perbaikan:** Aksen & kelas tombol seragam; tombol filter di kepala kartu; satu judul.
- **Cek:** Panel integrasi seragam.
- **Terverifikasi:** ya

#### G5-65 [R]
Lacak Lapangan: “3 hari lalu · 70% · 12m” (akurasi GPS terbaca menit); lencana “Realtime” walau 0 online; tautan “Bersihkan” terdengar menghapus.

- **Lokasi layar / jalur klik:** SDM › Lacak Lapangan (hr-live-tracking #78/#79).
- **Berkas:baris:** `frontend/src/features/hr/LiveTrackingView.jsx:176-180,213-226`
- **Perbaikan:** “akurasi ±12 m”; lencana “Terhubung”; “Sembunyikan jejak”.
- **Cek:** Teks tidak ambigu.
- **Terverifikasi:** ya

#### G5-66 [R] · pola P-06
Slip Gaji/Penggajian: “PPh 21 (0.75%)” titik desimal & tanpa dasar pengenaan; periode “2026-09”.

- **Lokasi layar / jalur klik:** SDM › Slip Gaji; Penggajian (hr-payslips #60, hr-payroll-runs #82).
- **Berkas:baris:** `frontend/src/features/hr/payrollUtils.js:6`
- **Perbaikan:** Persen id-ID + keterangan “tarif efektif × bruto”; formatPeriod.
- **Cek:** “PPh 21 (0,75% × bruto)”.
- **Terverifikasi:** ya

#### G5-67 [R]
Kampanye: “Nominal (Rp) *” input number bawaan (panah putar); subjudul “Dr Beban Pemasaran / Cr Kas-Bank”; kartu “· 2026-10-01 → 2026-10-31” (titik menggantung, ISO).

- **Lokasi layar / jalur klik:** Marketing › Kampanye › Biaya kampanye (mkt-campaigns #122/#127).
- **Berkas:baris:** `frontend/src/features/marketing/CampaignCostsModal.jsx:35,73`; `frontend/src/features/marketing/Campaigns.jsx:49,91`
- **Perbaikan:** MoneyInput; kalimat awam (“dicatat sebagai beban pemasaran”); formatDate & join tanpa pemisah kosong.
- **Cek:** Form biaya memakai input uang.
- **Terverifikasi:** ya

#### G5-68 [R]
Detail desain: teks tanpa spasi “belum ditetapkanatur peruntukan”; “Pattern — · Design — · desainer …”; langkah aktif stepper ungu (1–3 hijau); kepala menumpuk 3 lencana (“Pengajuan awal” + “ACC · Berkas Final” + “2/2 ACC”).

- **Lokasi layar / jalur klik:** Desain & Pattern › detail INT-ABS-AO-001 / DSN-GEN-001 (rnd-designs #171/#181).
- **Berkas:baris:** `frontend/src/features/rnd/design/DesignDetailPage.jsx:85-92,102,107,126-131,224-236`
- **Perbaikan:** Spasi/tautan; sembunyikan bagian kosong; warna langkah aktif standar; satu lencana status.
- **Cek:** Kepala detail tanpa “—” menggantung.
- **Terverifikasi:** ya

#### G5-69 [R]
Menu HP MD: label tidak sama dengan layar tujuan (“Riwayat Labdip” → “Labdip (Master)”, juga nama pop-up per warna; “Galeri & Studio Desain” → “Desain & Pattern”; “Inspeksi (acuan sample)” → “SPK Inspeksi & QC (INS)”; “Satuan (UoM)”).

- **Lokasi layar / jalur klik:** HP MD › Lainnya (hp-md-cipta-sandang #106, hp-md-riwayat-labdip #165).
- **Berkas:baris:** `frontend/src/features/sales/mobile/MobileMdApp.jsx:35,39,43,46`
- **Perbaikan:** Label menu = judul layar (“Labdip”, “Desain & Pattern”, “SPK Inspeksi”, “Satuan”).
- **Cek:** Menu & judul layar sama.
- **Terverifikasi:** ya

#### G5-70 [R]
Jejak Dokumen: istilah “Purchase Order”, “Tagihan Supplier”, penekanan huruf besar; kartu alat admin “Susun Ulang Relasi Dokumen Lama” selalu tampil di layar kerja harian.

- **Lokasi layar / jalur klik:** Laporan › Jejak Dokumen (doc-trace #32).
- **Berkas:baris:** `frontend/src/features/documents/trace/DocTraceView.jsx:163,174`; `frontend/src/features/documents/trace/TraceSearch.jsx:54,58`; `frontend/src/features/documents/trace/TraceBackfill.jsx:45`
- **Perbaikan:** Istilah sesuai menu; kartu backfill hanya untuk admin di bagian terlipat.
- **Cek:** Layar harian tanpa kartu alat admin.
- **Terverifikasi:** ya

## 5. Tidak dikerjakan agen

### 5.1 Kandidat duplikasi layar/menu → keputusan pemilik

| Id | Kandidat | Rincian |
|---|---|---|
| D-01 | Template dokumen di 4 tempat | Pengaturan › Template Dokumen Dasar (AdminView) · Pengaturan › Template PDF · Pusat Cetak › Template aktif (hanya baca) · Master per Badan Usaha › Template Dokumen & Kop Surat. |
| D-02 | Kategori beban dua editor | Kategori Beban → Akun COA (expense-categories) ≈ Master per BU › Kategori Biaya (8 baris & akun sama); mirip Pemetaan Akun; kategori kembar “Office Supplies” & “ATK” → 6-4100. |
| D-03 | Tarif insentif tiga tempat | Pengaturan › Rate Insentif Sales ≈ CRM › Tarif Insentif ≈ Pusat Pengaturan “Strategi & mekanik komisi” (ambang/mekanik/batas margin ada di dua tempat). |
| D-04 | Aturan persetujuan dua tampilan + dua cara nonaktif | Master per BU › Aturan Persetujuan (baca, kode mentah) ≈ Pengaturan › Aturan Persetujuan; di layar itu badge Aktif (toggle) ≈ ikon sampah “Nonaktifkan”. |
| D-05 | Tiga form pelanggan | Master Data › Buat Pelanggan (8 isian datar) ≈ CRM › Pelanggan Baru ≈ POS/HP › Pelanggan baru. |
| D-06 | Antrean persetujuan berlapis | HP Antrean ≈ HP Persetujuan (isi sama + PR-00002, tanpa aksi); Control Tower “Antrean Persetujuan (69)” ≈ Pusat Persetujuan; Persetujuan Saya ≈ Pusat Persetujuan; Pusat Persetujuan tab Amandemen ≈ Pusat Amandemen. |
| D-07 | Papan PO Custom di 4 tempat | Control Tower, Dasbor Manajer, Beranda Sales ≈ Pesanan Khusus (OD) tab Menunggu ≈ HP Persetujuan — dua dialog Setujui berbeda. |
| D-08 | Rapor desainer di 3 tempat | Permintaan Desain › Rapor Desainer ≈ KPI Desainer ≈ Profil Saya › KPI Saya (R&D). |
| D-09 | Dua “galeri” desain | Galeri Desain (Showcase) ≈ Desain & Pattern; menu HP “Galeri & Studio Desain” membuka Desain & Pattern. |
| D-10 | Ringkasan laba-rugi berulang | Dasbor Keuangan (MARJIN BERSIH & POSISI KAS masing-masing 2×) ≈ Laporan Keuangan › Laba-Rugi ≈ BI Keuangan ≈ Konsolidasi/pratinjau Tutup Buku. |
| D-11 | Margin di beberapa layar | Analitik › Margin & HPP ≈ Keuangan › Profitabilitas & Margin ≈ Dasbor & Analitik tab Margin & HPP. |
| D-12 | Umur piutang dua layar | Uang Muka Pelanggan (bucket ≤30/31-60/…) ≈ AR / Piutang & Umur (Lancar/1-30/…). |
| D-13 | Ringkasan kas tiga layar | Rekening & Saldo ≈ Transaksi Kas ≈ Proyeksi Arus Kas; kartu “KAS KECIL PER ENTITAS” = “KAS KECIL” saat satu entitas. |
| D-14 | Pemilih badan usaha lokal menduplikasi header | Tutup Buku (header + KPI + kartu), Buka Periode, Harga per Badan Usaha. |
| D-15 | Dua alur stock opname | Lokasi RFID › Stock Opname (RFID)/Cycle Count ≈ Operasi Gudang › Stock Opname. |
| D-16 | Transfer tampil di dua sub-tab | Operasi Gudang › Transfer › Antar gudang ≈ Antar entitas (PT) — dokumen KSC/TRF yang sama, status & tombol setuju berbeda. |
| D-17 | Dua dasbor pesanan + tiga kontrol filter | Pesanan › Dasbor & Analitik ≈ Dasbor & Analitik › Ringkasan (angka beda); di daftar SO: kartu KPI status ≈ tab status ≈ dropdown “Status rinci”. |
| D-18 | Dua tingkat detail & dua pintu cetak | Pesanan Pembelian: panel kanan ≈ pop-up “Lihat detail lengkap”; PR: “Cetak PR” ≈ bilah Pratinjau/Unduh PDF. |
| D-19 | Pengiriman | tab Daftar pengiriman ≈ tab Riwayat; tiga jalan “Buat pengiriman” di Dasbor. |
| D-20 | PPN berulang | Faktur Pajak Masukan: kartu ringkasan atas ≈ tab Rekap PPN (urutan terbalik); PPh & Rekap Pajak › PPN “Rincian Pajak Masukan” ≈ hub Faktur Masukan. |
| D-21 | Satuan dua daftar | Satuan & Konversi: Daftar Satuan (UOM) ≈ tabel Aturan Konversi (faktor sama, aksi beda, nama satuan beda). |
| D-22 | Kinerja mitra makloon tiga tempat | Rekap Susut & Klaim ≈ Skor Mitra Makloon ≈ tab Scorecard detail mitra. |
| D-23 | Harga internal dua tampilan | Antar Entitas › Harga Internal (kartu pasangan + editor massal) ≈ Kontrak › tab Harga Internal + “Isi massal”. |
| D-24 | Sample & spesifikasi | Pesanan Sample › Meja Cutting ≈ Cutting (gudang) › Paket potong sample; Uji Ulang SKU (RndSamplesView) ≈ Labdip/Handfeel/Proofing (SampleTypeGalleryView); form Spesifikasi (lengkap) ≈ “Ubah spesifikasi” (6 isian). |
| D-25 | Dua konsep resep | Resep Proses (konversi makloon) ≈ Produksi › BOM/Resep — nama mirip tanpa saling menautkan. |
| D-26 | Pintu ke tampilan desktop di HP | Tab “Desktop” ≈ ikon monitor ≈ tombol “Buka Tampilan Desktop” (Ringkas); Sales › Lainnya: “Hub lengkap · setara desktop” ≈ “Fitur lainnya · tampilan penuh” ≈ “Tampilan Desktop” (butir sama muncul 2×). |
| D-27 | Form ganda HP vs desktop | HP Permintaan Internal ≈ pop-up “Minta Barang dari Badan Usaha Lain”; form DSR HP ≈ “Permintaan Desain Baru” desktop; dialog Setujui HP ≈ papan desktop. |
| D-28 | Stok HP dua daftar | MD Status Stok ≈ Sales Stok & ATP (angka beda untuk produk sama); “Barang ditahan QC” di Dasbor Manajer ≈ Stok gudang ≈ Inspeksi › Hanya Ditahan. |
| D-29 | Lain-lain | Bagan Akun: ikon riwayat di baris ≈ tab Riwayat Perubahan; Barang Masuk: Selisih Supplier ≈ Kualitas Label Supplier; Posting Gagal ≈ blok “Jurnal Antar-PT · NOT POSTED” di detail transfer; dua menu “Perangkat” di Pengaturan (mesin absen vs RFID); notifikasi “Barang PO datang” ≈ “Penerimaan selesai” (b1, belum terlihat ulang). |

### 5.2 Pekerjaan tata letak besar (butuh desain/keputusan pola, bukan tambalan agen)

| Id | Pekerjaan | Lingkup |
|---|---|---|
| L-01 | Navigasi berlapis 3–6 tingkat & tab buatan sendiri | Pil hitam hub + pil/segmented biru/ungu + chip + tab garis: admin, amendments, bank-reconciliation, contra-bons, budget, chart-of-accounts, consolidation, financial-statements, general-ledger, hr-attendance, design-requests, entities-access/permission-matrix, operations, orders, pdf-templates, input-tax, keep-pending, inventory-lots, rnd-revalidation, inspections, rnd-specs. Butuh satu pola `.tab-bar` baku + aturan maksimal 2 tingkat. |
| L-02 | Kepala halaman tanpa kartu/PageHeader | approval-rules, bank-reconciliation, contra-bons, cs-rfid-devices/gate/tags/lokasi, cs-stock-analytics, escalations, finance-cases, export-center, mkt-accounts, repair-orders, product-templates (h1 28px). |
| L-03 | Pop-up/form buatan sendiri → FormModal/DetailModal | `.modal-card` polos / `div fixed` / Sheet kaki terbalik / form inline / halaman penuh: blanket-po, contra-bons Jadwal, Riwayat Labdip & Tambah/Edit Warna, cs-kpi, cs-price-list, consolidation (2), interco (4 gaya, tombol hitam), fixed-assets, RFQ, LifecycleActions, document-center (WA/TTD/Kirim), Sheet SDM, ESS cuti, chart-of-accounts (buat inline), cash-advances (halaman penuh), incentive-rates (panel tetap), md-categories, md-warehouses (4 pola), settlements, PR Baru, budget inline, cs-rfid-devices inline, makloons, process-recipes, input-tax, Buat Template Dokumen. |
| L-04 | Halaman desktop dirender mentah di HP | Control Tower/Dasbor Manajer, Permintaan Desain, Labdip/Desain & Pattern/Proofing, RFQ, Inspeksi, Pesanan SO, Meja Admin Sample & Pesanan Sample, Barang Masuk, Pengaturan: KPI satu kolom panjang, tab 3–4 baris, kepala detail 3 kolom, tabel min-w. Perlu keputusan halaman mana yang mendapat versi HP dan mana cukup “buka di desktop”. (Butir T spesifik sudah diambil per grup.) |
| L-05 | Navigasi Pengaturan & sidebar | ±20 pil dalam 4–5 baris dengan label grup disisipkan di tengah baris; sidebar memotong label (“AKUNTANSI & PAJ…”, “Uang Muka Pelan…”); breadcrumb tak cocok dengan sorotan sidebar (amendments, cs-stock-analytics, costing, consolidation, financial-statements, profitability, interco). |
| L-06 | Tabel lebar di desktop 1440 yang perlu desain ulang kolom | designer-kpi (15+ kolom), purchasing (2/3 + panel kanan kosong), returns (tabel item & roll), entity-masters, operations (BTK patah 6 baris KPI). |
| L-07 | `<table>`/grid mentah vs `.data-table` | KpiView, ARAging, RfidTags, StockAnalytics, DivisionsView, InspectionsView, AttendanceView, Settlements, consolidation. |
| L-08 | Gaya KPI & bilah alat | Kartu KPI bergaris kiri warna-warni (budget, Arus Kas, Perubahan Ekuitas) vs berbingkai; nilai 0 berwarna peringatan (landed-cost, makloon-claim-recap, logistics, inventory-board, hr-leave); bilah alat padat (designer-kpi 8 kontrol, mkt-calendar, consolidation 4 tombol); aksen ungu #6B219A/#6C3FD1 di luar biru standar. |
| L-09 | Tiga gaya aplikasi HP per peran | MD (kepala ungu), Sales, Ops/Gudang (bel pil merah) — perlu satu kerangka HP. (Tombol kembali ke HP diambil G0-12.) |
| L-10 | Rombak form panjang | Induk produk baru (±1.600 px, sumbu terbuka semua), Buat Template Dokumen, form Karyawan, form Pelanggan CRM, form Kontrak (rumus), Wizard Order Makloon. |

### 5.3 Keputusan bisnis (definisi angka/aturan yang mungkin sengaja berbeda)

| Id | Topik | Pilihan / dua definisi |
|---|---|---|
| K-01 | Definisi piutang | A) Sub-buku/papan dokumen (Dasbor Keuangan Rp 407,9 jt; layar Piutang total belum lunas; Control Tower papan per sales Rp 79,5 jt hanya pelanggan ber-sales) vs B) GL 1-1200 Piutang Usaha (Neraca Rp 189,3 jt, hanya yang sudah diposting). Juga: “lewat tempo” Control Tower Rp 0 vs Piutang Rp 1.193.250 (masa tenggang?). Putuskan angka utama tiap layar + wajib label sumber. |
| K-02 | Definisi kas | A) Kas saat ini = saldo GL kas+bank (Proyeksi Arus Kas Rp 913,6 jt) vs B) saldo rekening terdaftar (Rekening & Saldo Rp 775 jt) vs C) kas besar + kas kecil transaksi kas (Rp 915,7 jt). Rekening “0 transaksi” vs Rekonsiliasi “20 transaksi belum tertaut” (buku vs mutasi bank). |
| K-03 | Nilai dokumen DPP vs bruto & tampilan PPN | A) DPP/subtotal (Pusat Dokumen Rp 202.318; Persetujuan Pembelian Rp 120 jt; kolom “TOTAL (DPP)”) vs B) termasuk PPN (PDF/CRM Rp 224.573; Meja Saya Rp 133,2 jt). Format PPN 12% × DPP nilai lain 11/12: tampilkan baris DPP nilai lain di layar & PDF? |
| K-04 | Definisi stok “Tersedia” & “Stok rendah” | A) papan stok berbasis roll (roll diblokir/karantina dikeluarkan → Ulos 0) vs B) inventory_balances.available_qty (Saran Reorder → 29). Stok Rendah 7 (Control Tower) vs 32 (Stok gudang). |
| K-05 | Klasifikasi Analitik Stok | A) Cepat laku = penjualan terakhir ≤ 30 hari (sekarang) vs B) berdasarkan perputaran/coverage (mis. ≤ 90 hari stok). Ambang yang dipakai? |
| K-06 | Hitungan “Menunggu” & corong pesanan | KPI Menunggu = waiting_approval saja vs waiting_approval+reserved+approved; Corong 405 (termasuk SO sample/badan usaha lain?) vs daftar Pesanan 373. |
| K-07 | Utang antar-PT | A) Saldo antar-PT netting dua arah (Rp 7.015.200) vs B) jadwal bayar per dokumen diterima (Rp 6.993.000). |
| K-08 | Bobot nilai desainer | 40% + 40% + 20% + 20% = 120% — komponen “nilai versi desain” tambahan (bonus) atau harus dinormalisasi ke 100%? |
| K-09 | Penomoran dokumen | Payroll run memakai awalan “PR-” yang sama dengan Permintaan Pembelian; nomor MKO & CASH lama tanpa prefiks badan usaha — ganti awalan untuk dokumen baru? |
| K-10 | Bawaan “Langsung dikonfirmasi (post jurnal)” | Transaksi Antar-PT Baru: centang bawaan aktif (jurnal langsung) atau tidak. |
| K-11 | Wewenang & visibilitas per peran | Admin Sample boleh memutus pesanan khusus (SORD) di HP? Sales perlu melihat papan PO Custom pelanggan lain? Admin tidak melihat dataset ekspor Amandemen/Mutasi Kredit Toko — disengaja? MD boleh membaca seluruh Pusat Pengaturan? Baris KANDA/SO di inbox Sukacita (lintas entitas) disengaja? |
| K-12 | Isi tab Ringkas HP per peran | Angka apa untuk Desainer (DSR berjalan, tenggat) dan Admin Sample (antrean SOS, menunggu bayar). |
| K-13 | Glosarium istilah | Daftar istilah Inggris yang dipertahankan vs diterjemahkan dan SATU nama per konsep: Control Tower, Chart of Accounts, Landed Cost/Biaya Masuk, WAC, Blanket/Contract PO/Call-off, Commitment Control, Cash Advance/Pengajuan Dana, Sales Force, Keep/Pending, Payroll Run/Payslip/Overtime/ESS/Clock In, Reader/Gate/Tag/Encode, Cycle Count/Stock Opname, round/ronde/putaran, sample/sampel, Catalogue/Katalog, PO Custom/Pesanan Khusus (OD), Harga per Pelanggan/Harga Langganan, Rate/Tarif, Vendor Bill/Tagihan Supplier, Store Credit, Settlement/netting, BOM/Work Order, Scorecard, Approver, Pattern/Design. |
| K-14 | Ambang alasan minimum | 3 huruf (Persetujuan Saya), 5 (retur antar-PT, tagihan kampanye), 15 (SPK) — diseragamkan atau per jenis aksi? |
| K-15 | Tutup buku saat Suspense ≠ 0 | Diblokir atau cukup peringatan di dialog konfirmasi (G1-03)? |
| K-16 | Klaim Labdip tanpa handfeel ACC | Labdip produk baru wajib induk handfeel ACC (form buntu tanpa itu) — tetap wajib, atau boleh tanpa induk? |

### 5.4 Data uji (bukan temuan UI)

- Nama data uji (TEST_/Test_/QA/E2E/“x”, PT Uji Provisioning F77512/F10873/F5880, TEST_SITE, TEST_Bank Updated kembar) — bukan temuan; tetapi daftar pemilih yang tidak membedakan nama kembar tetap ditangani (G1-36, G2-14).
- Berkas lampiran/gambar 404 di DB acuan (/api/design-gallery/…/files, /api/rnd/samples/…/attachments, foto roll retur, POD) — cek apakah scripts/dev_restore_demo.sh ikut memulihkan berkas unggahan; perilaku fallback UI tetap ditangani (P-09).
- Produk tanpa base_unit/unit (“1.503 tanpa satuan”) — lengkapi data master (skrip perbaikan data terpisah); fallback tampilan di G3-32.
- Nomor CASH-0000x tanpa prefiks entitas (data lama) — lihat K-09.
- SORD-261024-0013…0015 / SORD-261023-0006 muncul dengan dua pelanggan berbeda di notifikasi — kemungkinan bentrok penomoran data uji F4 atau notifikasi basi; perlu dicek sebelum dianggap bug (G5-57).
- Pesanan uji ber-sales “—”, harga “Rp 0/” pada item uji, gudang Rp 0 entitas uji di matriks konsolidasi.

### 5.5 Artefak crawl yang dibuang & yang perlu tangkap ulang

- KNSelect jalur Radix di dalam pop-up/laci “tidak membuka daftar” (Jenis Kelamin di Tambah Karyawan, “— Pilih Sales —” di Pelanggan Baru, “Jenis” di Baris Baru entity-masters, “Pilih gudang…” hp-md-cipta-sandang #115) — SUDAH diuji manual dengan klik mouse CDP: daftar terbuka normal. Artefak crawler (daftar Radix item-aligned tak terdeteksi sebagai popover). Dibuang.
- Klaim crawl lama b1 akibat sesi tanpa entitas aktif: dropdown/daftar kosong (rekening, gudang, periode, karyawan, provinsi, Negara kosong), kepala “Badan usaha”, KPI “Rp 0/0/0.0%” saat skeleton, “Memuat…” berkepanjangan, badge basi — dibuang (kecuali yang dikonfirmasi c*).
- Galat setelah tombol aksi simpan (“Network Error”, “Gagal menyimpan”, “Gagal posting gl.”, “Template gagal dijalankan”) — akibat crawler memblokir penyimpanan. Yang dicatat hanya ketiadaan konfirmasi/teks.
- Ajakan notifikasi “dobel” (bilah lalu kartu) — c3_3: kartu MENGGANTIKAN bilah saat izin diblokir (alur 2 langkah wajar). Yang tetap temuan: tumpukan 4 pesan dalam keadaan diblokir (G0-10).
- Klik tanpa efek karena keterbatasan peramban crawler: “Pasang sekarang”, “Salin device_token”, “Lihat Slip (PDF)”, tombol Unggah berkas (pemilih berkas) — perlu dicek di perangkat nyata, bukan butir agen.
- Penanda otomatis keliru: chip {{variabel}} di Template PDF, angka kalender 29/30/31 (“kaki pop-up tak jelas”), tumpang-tindih latar modal, “kode mentah” pada email/slug/nama berkas (artwork_kawung.png), “isian tanpa label” pada kotak cari berikon.
- Perlu tangkap ulang (bukan temuan): advance-report #1, amendment-reasons #1, ar-aging › Rincian Piutang, bank-recon-rules › tab Template Bank & pop-up Template bank baru, domain-registry bagian bawah (>2.600 px), finance-cases › detail kasus, cs-rfid-gate dengan gerbang nyata, hp-finance-ringkas, hp-md-produk, hp-md-desain #41, hp-sample_admin-desktop detail (>3.200 px), hp-warehouse_admin-masuk #108 (401 saat muat pertama), document-center tab Jejak/Cetak, notifikasi panjang terpotong 3.200 px (refund settled, PO datang dobel).
- early_findings #2 (HP Ops tab macet “Memuat…” > 25 dtk dengan 12–34 permintaan menggantung saat backend sibuk) — perlu cek terpisah saat backend senggang (kemungkinan polling menumpuk); belum terverifikasi, tidak dijadikan butir agen. early_findings #1 sudah tercakup di G5-08; #3 = positif palsu.

## 6. Butir yang penyebabnya belum terverifikasi

- G0-10: ya (kode); perilaku prompt perlu dicek di HP nyata
- G1-02: lokasi ya; penyebab backend belum terverifikasi
- G1-09: teks ya; penyebab angka 0 belum terverifikasi
- G1-12: lokasi ya; penyebab backend belum terverifikasi
- G1-13: lokasi ya; penyebab belum terverifikasi
- G1-16: ya untuk konsolidasi/kontrabon/kasus/Buka Periode/kategori beban; baris tombol Sinkronkan GL & Ulang Posting belum dipastikan
- G1-19: nama akun ya; logika KPI belum terverifikasi
- G1-26: lokasi ya; selisih 562/563 belum terverifikasi
- G1-31: belum terverifikasi (logika backend)
- G1-33: belum terverifikasi (logika)
- G1-44: lokasi ya; id view tujuan belum dipastikan
- G1-50: belum terverifikasi (logika)
- G2-05: lokasi ya; penyebab belum terverifikasi
- G2-14: lokasi ya; sumber “Pengaju: —” belum terverifikasi
- G2-15: belum terverifikasi (sumber field)
- G2-20: tampilan ya; urutan verifikasi vs setuju belum terverifikasi
- G3-10: ya (kode); skenario dengan gerbang nyata belum teruji
- G3-17: lokasi ya; penyebab data/backend belum terverifikasi
- G3-19: belum terverifikasi (lokasi kolom)
- G3-37: berkas ya; baris pasti teks “(= 100 meter)” belum dipastikan
- G4-08: lokasi ya; penyebab selisih belum terverifikasi
- G4-12: belum terverifikasi (alur backend)
- G4-24: lokasi ya; definisi menunggu K-04
- G4-30: lokasi chip belum dipastikan
- G5-14: lokasi ya; kontradiksi status/tahap belum terverifikasi
- G5-38: lokasi ya; sumber bobot backend belum terverifikasi
- G5-45: lokasi ya; sumber “Dikirim: Belum” belum terverifikasi
- G5-48: lokasi ya; penyebab data belum terverifikasi
- G5-52: belum terverifikasi (izin dataset)
- G5-57: lokasi ya; penyebab dobel belum terverifikasi
- G5-63: berkas ya; baris tombol belum dipastikan

## 7. Pemeriksaan kepemilikan berkas

Lulus: setiap berkas yang dirujuk butir mana pun dimiliki tepat satu grup, dan grup itu adalah grup butirnya.
