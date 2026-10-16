# Laporan Audit UX & IA Menyeluruh — 2026-10-05 (BELUM ADA PERBAIKAN)

Status: **audit saja**. Belum ada kode yang diubah. Perbaikan dijalankan setelah laporan ini disetujui.

## 0. Cakupan & cara audit

| Bagian | Cakupan | Bukti |
|---|---|---|
| Penelusuran browser (admin) | 135 halaman (`view`) × semua tab di dalamnya = **336 keadaan layar** | `admin/crawl.json`, `admin/shots/*.jpg` |
| Penelusuran per peran (menu sidebar → halaman → tab hub) | sales (28 halaman), gudang (31), admin sales (37), finance (20), manajer (52 item menu) | `<peran>/menu.json`, `<peran>/crawl.json` |
| Uji filter chip sungguhan (klik → isi daftar harus berubah) | 12 grup chip yang dicurigai, diuji ulang satu per satu dengan reset di antaranya | `verify/verify.json`, `verify/*.jpg` |
| Uji filter dropdown (pilih opsi ke-2/ke-3) | 60 dropdown di 37 halaman | `verify/selects.json` |
| Uji search (ketik kata acak → daftar harus kosong) | semua kolom search yang ditemukan | `*/crawl.json` → `search_test` |
| Cek ulang "tanpa search" (input apa pun yang terlihat) | 72 halaman | `verify/inputs.json` |
| Pola tiap halaman daftar (kartu KPI, lebar/posisi search, jenis filter status, paginasi) | 121 halaman berisi daftar | `pola_halaman_daftar.md` |

Alat audit: `scripts/audit_ux_crawl.py`, `audit_ux_analyze.py`, `audit_ux_verify.py`, `audit_ux_verify2.py`, `audit_ux_selects.py`, `audit_ux_inputs.py`. Semua hanya-baca: klik tab/filter dan ketik search, tanpa menyimpan data.

**Batasan (jujur):** tampilan HP belum ditelusuri di putaran ini. Isi pop-up/form juga tidak dibuka ulang (sudah di putaran sebelumnya). Peran MD tidak bisa dicek karena akunnya tidak ada di DB preview. Kecocokan kartu angka dicek otomatis hanya bila labelnya sama dengan tab/chip berangka.

---

## 1. Stok di Kasir/POS & layar sales — **SALAH KONSEP** (temuan Anda, terkonfirmasi)

- **T1.1** Kartu produk POS menghitung stok **per entitas aktif**. Akibatnya pilihan entitas di header dipakai sebagai syarat, sehingga produk tampil "Habis" (contoh ALICE KNIT, AUDIA KNIT, BAMBU KNIT) walau stoknya ada di entitas lain. Catatan di panel kiri juga berbunyi "Ketersediaan dihitung per entitas aktif". Sumber: `SalesPortal.jsx` (`catalogEntityId`, filter `available_qty`), `FacetRail.jsx:120`.
- **Keputusan Anda:** sales hanya melihat **stok global**. Cara memenuhinya (transfer antar-entitas atau PO ke supplier) diputuskan admin, bukan sales.
- **T1.2** "Barang akan datang" belum dipisah. Saat ini PO terbuka dan transaksi antar-PT digabung jadi satu angka `incoming` (`stock_bucket_service._incoming_supply`). Datanya sebenarnya sudah ada untuk memisah: PO/PR menyimpan `source_so_ids` (`pr_sourcing_service`), dan antar-PT menyimpan `source_order_id`.
  Usulan: **Datang untuk SO** (sudah terikat pesanan, tidak bisa dijanjikan lagi) dan **Datang untuk Restock** (bebas dijanjikan sales).
- Layar sales yang harus diseragamkan ke aturan ini: kartu & detail produk POS, panel kiri POS (catatan + filter "Ketersediaan"), form buat SO, layar Stok & ATP versi sales, aplikasi sales HP.

## 2. Pola halaman daftar tidak seragam — **TERKONFIRMASI di 121 halaman**

Perbandingan langsung tiga halaman Penjualan yang Anda tunjuk:

| Elemen | Pesanan | Pesanan Khusus | Pesanan Sampel |
|---|---|---|---|
| Kepala halaman | judul di topbar saja + tab hub | judul + deskripsi + tombol "Buat" di kanan | kartu bergaya "PENJUALAN › Pesanan Sampel" + deskripsi panjang |
| Kartu KPI | 7 kartu berwarna + nilai Rp | 5 kartu putih berikon, tanpa Rp | 4 kotak abu datar |
| Search | lebar penuh 1292 px, di atas daftar | 292 px, di atas tab | **tidak ada** |
| Filter status | dropdown "Semua Status" di kepala tabel | **tab bergaris bawah** | **chip** |
| Filter lini | chip Woven/Knit/Printing | tidak ada | tidak ada |
| Detail | panel kanan (split) | kolom "Detail →" | panel kanan (split) |
| Paginasi | ada | **tidak ada** | **tidak ada** |

Pola yang sama berulang di seluruh aplikasi:
- **Lebar search ada 4 macam:** penuh (4 halaman), sedang 384–954 px (15), kecil 161–293 px (30). Posisinya kadang di atas tab, kadang di bawah tab, kadang di kanan baris chip (Barang Masuk).
- **Filter status ada 3 bentuk:** tab (16 halaman), chip (12), dropdown (18).
- **Paginasi** hanya ada di 15 halaman daftar.
- Rincian per halaman ada di `pola_halaman_daftar.md`.

**T2 Usulan satu pola baku "Halaman Daftar":** kepala (judul + deskripsi singkat + aksi utama di kanan) → baris kartu KPI (satu komponen, bisa diklik sebagai filter) → toolbar (search baku lebar penuh di kiri, filter di kanan) → tab status satu gaya → tabel + paginasi → detail di panel kanan.

## 3. Halaman daftar tanpa search — **31 halaman**

Pesanan Sampel, Permintaan Internal (PIN), Kebijakan Retur, RFQ, Blanket/Kontrak, Landed Cost, Saran Reorder, Riwayat Persetujuan PO, Inbox Persetujuan, Persetujuan Saya, Antrean QC Kedatangan, Produksi, Pengiriman, Kendaraan, Lokasi RFID, Tag RFID, Rekening & Saldo, Transaksi Kas, Pengajuan Dana, Pertanggungjawaban, Kategori Beban, Kasus Keuangan, Faktur Masukan, Antar Entitas (Grup), Bagan Akun (76 baris), Cuti & Izin, Lembur, Slip Gaji, Kunjungan Sales, Kampanye, Buka Kunci Periode.

Tidak dihitung sebagai temuan: dasbor, laporan keuangan, meja kerja, dan halaman pengaturan berbentuk formulir.

## 4. Filter & search — hasil uji sungguhan

- **Search:** semua search yang ditemukan bekerja, kecuali **T4.1 Desainer › Rapor Desainer**: kata acak tidak mengubah isi (search milik tab lain ikut tampil di tab Rapor).
- **Filter chip & dropdown:** 25 dari 60 dropdown mengubah daftar sesuai opsi. Sisanya ternyata kolom isian form (bukan filter), atau isinya memang sama untuk opsi itu (dicek ke API: `status=reserved,waiting_approval,approved` → 20 dari 24 pesanan). Kecurigaan pada filter POS, R&D Sampel, Permintaan Desain, Retur, dan tab status PO terbukti **bekerja benar**.
- Yang perlu diperbaiki:
  - **T4.2 Operasi Gudang:** chip gudang (Jakarta/Bandung/Surabaya) hanya menyaring daftar bawah. Panel antrean ACC di atas (transfer, opname, QC ditahan) tetap menampilkan semua gudang.
  - **T4.3 Saran Reorder:** dropdown "Gudang tujuan" terlihat seperti filter daftar, padahal itu gudang tujuan PR. Labelnya menyesatkan.
- **Saya belum menemukan filter yang benar-benar mati.** Mohon sebutkan halaman tempat Anda melihatnya supaya saya reproduksi tepat di sana.

## 5. IA Operasi Gudang — **3 level & konsep ganda** (temuan Anda, terkonfirmasi)

Struktur sekarang (`?view=operations`):
- **L1 (tab hub):** Operasi WMS · Barang Masuk (SJ & OCR) · Antrean QC Kedatangan · Dokumen Inspeksi (INS) · Transfer Antar-Entitas
- **L2 (di dalam Operasi WMS):** Stok · Terima Cepat (mode lama) · Barang Keluar · Transfer · Stock Opname · Kesehatan
- **L3 (di dalam Stok):** Stok · Roll · Mutasi + chip gudang

Masalahnya:
- **T5.1** Barang Masuk ada di L1, sedangkan Barang Keluar di L2.
- **T5.2** Penerimaan muncul dua kali (L1 "Barang Masuk" dan L2 "Terima Cepat (mode lama)"). Transfer juga dua kali (L1 "Transfer Antar-Entitas" dan L2 "Transfer").
- **T5.3** QC tersebar di tiga tempat: L1 Antrean QC, L1 Dokumen Inspeksi, dan panel "Barang ditahan QC".
- **T5.4** Kartu "Tersedia" tampil dobel (kartu atas dan kartu di tab Stok).
- **T5.5** Ada tab "Stok" di dalam tab "Stok", padahal menu "Stok & ATP" sudah ada.

**Usulan satu level:** Ringkasan & Antrean ACC · Barang Masuk (SJ/OCR; terima cepat jadi pilihan cara terima) · QC & Inspeksi · Barang Keluar · Transfer (internal + antar-entitas) · Stock Opname · Kesehatan. Stok/Roll/Mutasi dipindah ke menu **Stok & ATP**.

Level ganda serupa juga ada di Pelanggan (Pelanggan/Leads/…/Rate Insentif → sub-status) dan Permintaan Pembelian. Keduanya akan ditinjau dengan aturan yang sama.

## 6. Pengaturan yang nyasar ke menu operasional — **13 lokasi**

| # | Lokasi sekarang | Isi | Usulan pindah ke Pengaturan › |
|---|---|---|---|
| T6.1 | Barang Masuk › Profil SJ / Sampel Uji OCR / Biaya OCR / Mode Penerimaan | pengaturan OCR & penerimaan | Gudang & Penerimaan |
| T6.2 | Operasi WMS › "Terima Cepat (mode lama)" | label memperlihatkan mode sistem ke operator | ganti label; mode di Pengaturan |
| T6.3 | Pesanan › tab hub "Kebijakan Retur" | aturan retur | Penjualan |
| T6.4 | Koreksi & Amandemen › Label Alasan | kamus alasan | Penjualan (kamus) |
| T6.5 | Pelanggan › Rate Insentif | tarif insentif sales | Penjualan |
| T6.6 | Kas Kecil › tab hub "Kategori Beban" | master kategori beban | Keuangan |
| T6.7 | Rekonsiliasi Bank › Aturan Pembelajaran / Template Bank | aturan & format mutasi bank | Keuangan |
| T6.8 | Pajak › PPh & Rekap › Konfigurasi | konfigurasi pajak | Pajak |
| T6.9 | Kehadiran › Shift & Geofence (+ Perangkat) | pengaturan presensi | SDM |
| T6.10 | RFID › Perangkat | registrasi perangkat | Perangkat & RFID |
| T6.11 | Desainer › Divisi & Persetujuan | struktur & alur persetujuan | Organisasi & Akses |
| T6.12 | Produk & Harga › Kategori / Pustaka Warna / Satuan | master data | tetap master data, tapi dikelompokkan "Master" (admin), terpisah dari menu kerja |
| T6.13 | Saran Reorder (ambang) & Lot (mode penegakan) | pengaturan kecil di halaman kerja | tautan "Atur di Pengaturan" saja |

Tidak ada fitur yang dihapus; semuanya hanya dipindah. Hak akses tetap sama.

## 7. Daftar panjang tanpa paginasi

Bagan Akun (76), Daftar Harga per Badan Usaha (40), Lokasi RFID (47), Pustaka Warna (28), Label Alasan (33), Daftar Dokumen (24), Barang Supplier (21), Harga per Pelanggan (20), Persetujuan Kredit (20), Stok & ATP (20), Operasi WMS › Stok (22), Peran & Hak Akses (55), Penjadwal (31/80), Pusat Pengaturan (72), Kesehatan Konfigurasi (265), Kebersihan Data (78), Meja Saya/Admin Sales (22–25), Margin & HPP (20), Divisi (20).

Laporan keuangan (Neraca, Arus Kas, Neraca Saldo) sengaja tidak dipaginasi.

## 8. Angka & kartu

Tidak ada selisih antara angka kartu KPI dan jumlah di tab/chip berlabel sama. Contoh yang dicek:
- PO: Total 12, Menunggu 2, Proses Terima 7, Selesai 3 → isi tab Selesai = 3.
- Pesanan Khusus: Draf 1, Menunggu 2, Produksi 2.

Hasil verifikasi angka sebelumnya (piutang = aging, Stok/ATP 0 selisih) tetap berlaku.

Yang **belum** tercakup otomatis: kartu yang labelnya tidak punya padanan tab. Akan dicek manual per halaman saat perbaikan pola (T2).

---

## Rencana perbaikan (setelah disetujui)

1. **Fase A — Stok sales global + pemisahan barang datang (T1).** Backend: ATP global, incoming untuk SO vs restock. Frontend: POS, form SO, Stok & ATP sales, aplikasi HP.
2. **Fase B — IA Operasi Gudang satu level (T5) + pindahkan 13 pengaturan (T6).** Tanpa menghapus fitur.
3. **Fase C — Komponen "Halaman Daftar" baku (T2).** Diterapkan ke semua halaman daftar transaksi & master, termasuk search di 31 halaman (T3), paginasi (T7), dan T4.1–T4.3.
4. **Fase D — Audit ulang dengan alat yang sama.** Target: 0 halaman daftar tanpa search, 1 pola search, 1 bentuk filter status, 0 pengaturan di menu operasional. Ditambah tampilan HP dan testing agent independen.
