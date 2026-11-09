# Keputusan yang diambil koordinator atas mandat pemilik (9 Nov 2026)

Pemilik (9 Nov, sebelum AFK): *"jika ada yang butuh keputusan saya, saya percayakan pada rekomendasi anda, report saja
di akhir"*. Semua butir di bawah **diambil koordinator (Claude Code) mengikuti rekomendasi auditor**, kecuali yang
ditandai **TIDAK diambil** / **ditunda**. Pemilik dapat membalik butir mana pun; lokasi perubahan tercantum di laporan
perbaikan `hasil/FIX-*.md`.

## Cakupan lokasi & PT (FIX-1)
| Butir | Keputusan |
|---|---|
| K-B1-01 | Semua akun operasional punya **lokasi kerja** (site, opsional gedung) sebagai saringan bawaan; peran `warehouse` tetap dibatasi keras; supervisor & peran non-gudang boleh memilih "Semua lokasi" lewat aksi eksplisit; cakupan selalu terlihat ("Lokasi: … ▾"); akun tanpa lokasi melihat peringatan, bukan diam-diam semua. |
| K-B1-02 · B2a D1 · B3a #6 · K-B2b-11 | Pekerjaan fisik (masuk/putaway/keluar/ambil/potong/muat/transfer/opname/pengiriman) dilihat **per gedung dalam lokasi kerja, lintas PT** yang ditugaskan, dengan label PT & jenis tugas; validasi kepemilikan tetap di server. Gedung `dedicated` yang bertentangan dengan K-GDG-07 (SRG-01, WH-JKT) diubah ke `shared` lewat skrip data (belum dijalankan ke DB bersama). |
| K-B1-07 | Operasional gate (panel U300 & buka kunci) terjangkau dari menu RFID untuk Admin Gudang (tab "Operasional Gate"); manajer akses baca. |
| K-B1-08 | Aplikasi HP sopir hanya berisi Pengiriman. |
| K-B1-10 | Data uji **disembunyikan** (penanda `is_test`, bisa dibalik) — **tidak dihapus**. |

## Angka stok (FIX-2)
| Butir | Keputusan |
|---|---|
| Satu definisi | "Tersedia" (K-04) = roll `available` − panjang dipesan potong − reservasi − tahan QC/karantina/MD Quality − cadangan makloon, gedung aktif saja — satu layanan `stock_figures` untuk semua layar. |
| Dua angka | LOKAL (PT aktif × lokasi kerja) + GLOBAL ("Total grup (semua PT)"), roll lalu panjang; rincian saat diklik (site/gedung, PT, status, barang akan datang, ATP). |
| B3a #1 | Cadangan makloon dikunci per roll — **sebagian**: dikurangi konsisten lewat satu aturan; kunci per roll = langkah lanjut. |
| B3a #2 | Tahan MD Quality → status roll `blocked` (dibalik saat lepas). |
| B3a #3 | Site POS pilihan sales disimpan di server. |
| B3a #4 | Horizon ATP = setelan `stock.atp_horizon_days`, bawaan 14 hari. |
| B3a #7 · K-B1-12 | Rincian lintas PT hanya angka & identitas roll (tanpa harga pokok/dokumen); peran gudang melihat angka grup berlabel "Total grup (semua PT)". |

## Alur masuk & opname (FIX-3a)
D2 tolak QC+retur ("ganti barang" → tugas sisa; "potong tagihan" → tutup kurang) — **ditunda** (butuh rancangan jurnal
pembalik GR-IR dari Finance). D3 roll ditahan tetap ditahan & boleh ditolak. D4 konversi satuan baku SJ vs PO. **D5
(retur masuk stok saat dipindai) — ditunda** (risiko selisih persediaan vs GL tanpa rancangan Finance). D6 roll retur →
draf putaway sesuai grade. D7 "Kirim" PA opsional. D8 roll tanpa bin ikut potret opname. **D9 — ditunda.** D10 transfer
0 roll diterima → `returned`. Pendaftaran awal **dua langkah** (hitungan gudang + nilai Finance, izin
`inventory.approve_value`, orang berbeda; setelan bawaan aktif). K-14 dihitung **huruf**, di server (`ReasonStr`).
PT per baris Daftar Awal HP. Fitur simulasi hanya di mode simulasi. `POST /inventory/initial-stock` ditutup (410)
untuk gedung yang memakai pendaftaran awal.

## Alur keluar, potong & RFID (FIX-3b)
K-B2b-01 eskalasi pada tugas terkirim sebagian hanya "tutup sisa". K-B2b-02 POD per SJ (istilah layar tidak diubah).
K-B2b-03 batal di jalan → dokumen `returning` + terima kembali (roll tidak langsung `available`). **K-B2b-04 TIDAK
diambil** — keputusan pemilik K-GDG-09 (stok transit boleh dijual) tetap berlaku. K-B2b-05 sisa potong → remnant/BS
dengan ambang & grade dari setelan. K-B2b-06 susut potong dijurnal; batas % dari setelan (bawaan 3 %) + alasan.
K-B2b-07 Gedung Retur keluar dari alokasi otomatis. K-B2b-09 simulator hanya perangkat bertanda uji + PT mode simulasi;
klaim simulasi tidak memengaruhi lintasan nyata. K-B2b-10 serah-terima Cutting lintas gedung wajib dokumen transfer.
K-B2b-12 kedaluwarsa reservasi tidak untuk SO `approved`/`waiting_stock`; GET tidak menulis (job penjadwal). K-B2b-13
tandai-tercetak manual hanya untuk label teks. K-B1-05/K-B3b-01 **ambil wajib pindai roll** (ketik qty = darurat berizin
`wms.approve` + alasan). K-B3b-02 EPC cek muat manual bukan bukti sah. K-B3b-08 `ScannerTaskPanel` dihapus; ambil alih
di detail tugas. RFID-2 EPC tidak pernah dipakai ulang. RFID-5 key handheld ditolak di ingest lama. RFID-12 bebas cek
muat hanya bila reader OUT sehat.

## Standar UI (FIX-4) — dari B4 & B1
K-B4-01 standar wajib menggantikan bagian KN_08 yang bertentangan, ditegakkan ratchet. K-B4-02 skala huruf 12/13/14/
16/20/24 (bertahap). K-B4-03 warna aksi/teks/batas lolos kontras AA. K-B4-04 uji 360 & 390 px. K-B4-06 komponen baru
memakai KN_32, layar lama tidak diganti istilah (K-13). K-B4-07/K-B3b-04 ekspor **Excel (XLSX) + CSV** lewat satu
komponen & Pusat Export. K-B4-11 tanda `*` wajib. K-B1-06 kelas tombol baku + varian `touch` ≥ 48 px. K-B1-09 huruf
minimum. K-B4-12 tampilan tersimpan — **ditunda** (di luar tahap 1).

## Masih butuh pemilik (tidak diputuskan koordinator)
- **Push ke GitHub** — ditolak pemeriksa izin otomatis; menunggu "push" dari pemilik.
- **Menjalankan skrip perbaikan data** ke DB bersama/produksi (semua dry-run bawaan; daftar di ringkasan).
- **Pengisian lokasi kerja** akun non-gudang & penugasan PT petugas Soreang (tindakan admin).
- D2/D5 (Finance), D9, K-B4-12, kunci makloon per roll, kapasitas penyimpanan klaim/keputusan gate jangka panjang.
- Gelombang 1 yang belum dijawab: izin unduh lembar master MD, waktu perbaikan master, roll lama yang masih dipesan
  saat pendaftaran, gate Gedung Retur RCM, penanda "minta inspeksi". (Persetujuan Finance pendaftaran awal kini
  diputuskan: dua langkah, bawaan aktif.)
