# Tracker Temuan Review — KNHOST

Satu tracker untuk semua paket review. ID tidak pernah diganti atau dipakai ulang.
Arti status & aturan: [`README.md`](README.md).

**Review aktif:** [`2026-10-20/`](2026-10-20/) — mulai dari `2026-10-20/README.md`,
lalu `AUDIT_FRONTEND_2026-10-20.md` dan `PROMPT_PERBAIKAN_FRONTEND_2026-10-20.md`.

| Paket | Baseline review | Posisi terhadap `f4e8f0b` (HEAD saat paket diterima) |
|---|---|---|
| Frontend (FE-xx) | `8dab383` | 17 commit di belakang — wajib cek ulang |
| Backend (AUD-xx) | `63c38bd` | 42 commit di belakang — wajib cek ulang |

## Frontend — paket 2026-10-20 (baseline `8dab383`)

| ID | Judul | Prio | Fase | Status | Berlaku di HEAD | Commit perbaikan | Laporan |
|---|---|---|---|---|---|---|---|
| FE-01 | Special Order multi-produk kehilangan item/qty saat pricing dan konversi | P1 | UI-01 | implemented_pending_review | ya — jalur kode deterministik | `cc4d13a` · batal per item `13c64d8` | [UI-01](2026-10-20/hasil/UI-01.md) · [KEPUTUSAN](2026-10-20/hasil/KEPUTUSAN-2026-10-21.md) |
| FE-02 | Kontrol pilihan Interco tidak memperbarui nilai | P1 | UI-02 | implemented_pending_review | ya — direproduksi runtime | `0d8e202` `6350391` `621f50b` | [UI-02](2026-10-20/hasil/UI-02.md) |
| FE-03 | Peta modul akses tidak mengikuti menu/hub terbaru | P1 | UI-03 | implemented_pending_review | ya — jalur kode deterministik | `9289e26` | [UI-03](2026-10-20/hasil/UI-03.md) |
| FE-04 | Tombol/petugas dibatasi nama role meski izin efektif berbeda | P2 | UI-03 | implemented_pending_review | ya — jalur kode deterministik | `859a087` | [UI-03](2026-10-20/hasil/UI-03.md) |
| FE-05 | Data Gudang menolak Admin Gudang yang berizin | P2 | UI-03 | implemented_pending_review | ya — direproduksi runtime | `859a087` | [UI-03](2026-10-20/hasil/UI-03.md) |
| FE-06 | Target Harga Khusus dari Meja Saya tidak dirender | P2 | UI-04 | implemented_pending_review | ya — jalur kode deterministik | `c5fd627` | [UI-04](2026-10-20/hasil/UI-04.md) |
| FE-07 | Error retur tidak terlihat dan modal menutup saat gagal | P2 | UI-04 | implemented_pending_review | ya — jalur kode deterministik | `c5fd627` | [UI-04](2026-10-20/hasil/UI-04.md) |
| FE-08 | Respons SO lama menimpa pilihan SO baru di form retur | P2 | UI-04 | implemented_pending_review | ya — kode (kelas ketahanan) | `c5fd627` | [UI-04](2026-10-20/hasil/UI-04.md) |
| FE-09 | Pemilih SO retur diam-diam terbatas 200 pesanan | P2 | UI-04 | implemented_pending_review | ya — jalur kode deterministik | `c5fd627` | [UI-04](2026-10-20/hasil/UI-04.md) |
| FE-10 | Antrean QC salah label satuan dan agregasi campuran | P2 | UI-05 | implemented_pending_review | ya — direproduksi runtime | `85ddd1c` | [UI-05](2026-10-20/hasil/UI-05.md) |
| FE-11 | Error awal penerimaan transfer tertutup loading | P2 | UI-05 | implemented_pending_review | ya — jalur kode deterministik | `85ddd1c` | [UI-05](2026-10-20/hasil/UI-05.md) |
| FE-12 | Neraca unknown ditampilkan Seimbang | P2 | UI-05 | implemented_pending_review | ya — jalur kode deterministik | `85ddd1c` | [UI-05](2026-10-20/hasil/UI-05.md) |
| FE-13 | Tooltip defisit kas menghapus tanda negatif | P2 | UI-05 | implemented_pending_review | ya — jalur kode deterministik | `85ddd1c` | [UI-05](2026-10-20/hasil/UI-05.md) |

## Backend — paket 2026-10-19 (baseline `63c38bd`, ikut dalam folder 2026-10-20)

Detail & arahan perbaikan: `2026-10-20/TEMUAN_TERVERIFIKASI.md`,
`2026-10-20/LANJUTAN_WMS_SPECIAL_ORDER_MIGRASI.md`. Arahan owner 2026-10-21: dikerjakan sesuai
urutan paket — hasil di [BE-AUD](2026-10-20/hasil/BE-AUD.md).

| ID | Judul | Fase | Status | Berlaku di HEAD | Commit perbaikan | Laporan |
|---|---|---|---|---|---|---|
| AUD-RND-01 | ACC labdip dapat meluluskan siklus yang handfeel-nya ditolak | BE | implemented_pending_review | ya — jalur kode deterministik | `c56a988` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-RND-02 | Versi artwork yang tidak ada diterima sebagai referensi proofing ulang | BE | implemented_pending_review | ya — jalur kode deterministik | `c56a988` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-RND-03 | Referensi kontrak terminated diterima `_validate_contract_ref` tetapi tidak muncul di daftar pilihan | BE | implemented_pending_review | ya — jalur kode deterministik (owner: boleh) | `af24f9c` | [KEPUTUSAN](2026-10-20/hasil/KEPUTUSAN-2026-10-21.md) |
| AUD-EXP-01 | Ekspor berkelompok selesai tetapi unduhan ditolak 403 | BE | implemented_pending_review | ya — direproduksi runtime | `db25c74` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-EXP-02 | Ekspor dapat menggandakan baris saat sumber berubah, jumlah baris tetap cocok | BE | implemented_pending_review | ya — kode (kelas ketahanan) | `1e275ca` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-SO-01 | Proses lama dapat melepas kunci realisasi milik proses baru | BE | implemented_pending_review | ya — kode (kelas ketahanan) | `193c048` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-WMS-01 | Stok opname berubah sebelum jurnal berhasil; retry tidak memulihkan | BE | implemented_pending_review | ya — kode (kelas ketahanan) | `6974dd9` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-MKL-01 | Excel rekap klaim makloon gagal saat memiliki baris mitra | BE | implemented_pending_review | sebagian — bagian 2 false positive | `ae4e1b3` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-MKL-02 | Rincian rekap klaim dipotong 1.000 baris, berbeda dari total | BE | implemented_pending_review | ya — jalur kode deterministik | `ae4e1b3` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-MIG-01 | Apply migrasi menyatakan matched tetapi melewatkan fulfillment kosong | BE | implemented_pending_review | ya — jalur kode deterministik | `8d6df8f` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-MIG-02 | Rollback menghapus perubahan operasional setelah migrasi | BE | implemented_pending_review | ya — jalur kode deterministik | `8d6df8f` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| AUD-RET-01 | Pembuangan BS gagal di tengah proses dan retry tidak memulihkan | BE | implemented_pending_review | ya — kode (kelas ketahanan) | `28d53c7` | [BE-AUD](2026-10-20/hasil/BE-AUD.md) · [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |

## Uji pra-UAT — paket 2026-10-21

Sumber: `docs/uat/2026-10-21/RENCANA_PERBAIKAN_TEMUAN_UAT.md` (17 temuan F-01..F-17); laporan hasil di
`docs/uat/2026-10-21/hasil/`.

| ID | Judul | Prio | Status | Berlaku di HEAD | Commit perbaikan | Laporan |
|---|---|---|---|---|---|---|
| F-07 | Perjalanan SO: "Disiapkan gudang 0/1", Disetujui/Dikonfirmasi tanpa waktu & pelaku | P3 | implemented_pending_review | ya — direproduksi di `bcca39a` | `262ec12` | [gelombang 3](../uat/2026-10-21/hasil/F-07-F-04-F-17-F-02-F-08.md) |
| F-04 | KPI POS "Jml Tersedia" menjumlahkan yard + kg | P3 | implemented_pending_review | ya — direproduksi di `bcca39a` | `5735cfb`, `8a23e16` | [gelombang 3](../uat/2026-10-21/hasil/F-07-F-04-F-17-F-02-F-08.md) |
| F-17 | Antrean retur bernilai Rp0 (Admin Sales & Manajer) | P3 | implemented_pending_review | ya — direproduksi di `bcca39a` | `9020042` | [gelombang 3](../uat/2026-10-21/hasil/F-07-F-04-F-17-F-02-F-08.md) |
| F-02 | Strip "Sering dibeli" menulis "0 roll tersedia" | P3 | implemented_pending_review | ya — direproduksi di `bcca39a` | `f322a71` | [gelombang 3](../uat/2026-10-21/hasil/F-07-F-04-F-17-F-02-F-08.md) |
| F-08 | Dokumen tagihan resmi; "Ditagih" = Faktur Pajak — default implementer: Faktur Komersial | P2 | implemented_pending_review | ya — direproduksi di `bcca39a` | `ac9e59c` | [gelombang 3](../uat/2026-10-21/hasil/F-07-F-04-F-17-F-02-F-08.md) |
| F-13 | MD Quality bisa mengisi saat SPK *Draf* — keputusan owner Q-06 (b): hanya sesudah SPK ditugaskan | P3 | implemented_pending_review | ya — direproduksi runtime di `20f356c` (INS-00063 draft, MDQ 200) | `debc38a` | [F-13](../uat/2026-10-21/hasil/F-13.md) |
| F-15 | Sample berbayar: tagihan berubah sesudah potong tanpa persetujuan ulang — keputusan owner Q-04 (±5% otomatis, di atasnya persetujuan ulang) | P2 | implemented_pending_review | ya — direproduksi runtime di `393af78` (SOS-00029 +16,7% tetap approved, terkirim) | `049c8ab` | [F-15](../uat/2026-10-21/hasil/F-15.md) |
| F-14 | SPK kedatangan ditutup *terima*, roll tetap karantina sampai keputusan kedua — keputusan owner Q-03 (a): satu keputusan SPK | P2 | implemented_pending_review | ya — direproduksi runtime di `6879aba` (INS-00029 done, roll quarantine) | `22b0d1b` | [F-14](../uat/2026-10-21/hasil/F-14.md) |
| F-16 | Jatuh tempo dihitung dari tanggal SO; SO belum dikirim & CBD tampil "30 hari lagi" — keputusan owner Q-05 (a): dari SJ pertama | P2 | implemented_pending_review | ya — direproduksi runtime di `c9fca2a` | `4cc39f7` | [F-16](../uat/2026-10-21/hasil/F-16.md) |
| F-06 | POD *Terkirim* tidak menutup SO — keputusan owner Q-01 (a): SO otomatis Terkirim saat semua SJ ber-POD | P2 | implemented_pending_review | ya — direproduksi runtime di `f856193` (SO-00208 tetap shipped sesudah LG-00008 Terkirim) | `1312fa1` | [F-06](../uat/2026-10-21/hasil/F-06.md) |
| F-10 | Termin CBD/DP tidak menahan pengiriman — keputusan owner Q-02 (blok keras + pengecualian berizin, dapat dikonfigurasi) | P1 | implemented_pending_review | ya — direproduksi runtime di `e20b149` (SJ terbit tanpa bayar) | `a039932` | [F-10](../uat/2026-10-21/hasil/F-10.md) |
| F-11 | Gudang & QC tidak bisa memproses perjalanan & QC retur (403 `sales_return.update`) | P1 | implemented_pending_review | ya — direproduksi runtime di `193c048` | `6e1112b` | [F-11-F-12](../uat/2026-10-21/hasil/F-11-F-12.md) |
| F-12 | QC retur bisa dimulai & diselesaikan tanpa barang diterima | P1 | implemented_pending_review | ya — direproduksi runtime di `193c048` | `6e1112b` | [F-11-F-12](../uat/2026-10-21/hasil/F-11-F-12.md) |
| F-11-layar | Gudang & QC tidak bisa membuka layar retur (daftar/detail/timeline 403, tab & menu tersembunyi) — keputusan owner opsi (b) terbatas | P1 | implemented_pending_review | ya — direproduksi runtime di `68e4449` | `a7c08c3` | [F-11-layar](../uat/2026-10-21/hasil/F-11-layar.md) |
| F-09 | Entri persetujuan yang ditolak mengunci SO selamanya (harga khusus & kredit) | P1 | implemented_pending_review | ya — direproduksi runtime (SO-00039, SO-00083) | `627a4c1` | [F-09](../uat/2026-10-21/hasil/F-09.md) |
| F-05 | Alokasi SO tidak mengikuti roll anak setelah potong (pick dari daftar ditolak) | P1 | implemented_pending_review | ya — direproduksi runtime di `193c048` | `98695cf` | [F-05-F-03-F-01](../uat/2026-10-21/hasil/F-05-F-03-F-01.md) |
| F-03 | Grade & LOT bocor ke Sales lewat `variant_label` | P1 | implemented_pending_review | ya — direproduksi runtime di `193c048` | `3f8ce21` | [F-05-F-03-F-01](../uat/2026-10-21/hasil/F-05-F-03-F-01.md) |
| F-01 | Login cepat per peran gagal (seed `demo1234` vs tombol `demo12345`) | P1* | implemented_pending_review | ya — direproduksi runtime di `193c048` (data acuan restore) | `941a9c2` | [F-05-F-03-F-01](../uat/2026-10-21/hasil/F-05-F-03-F-01.md) |

## UAT 24 Okt — paket 2026-10-21 (analisis temuan UAT 23 Okt)

Sumber: `docs/uat/2026-10-21/ANALISIS_TEMUAN_UAT_23OKT.md` (P1..P17, fase F0..F5; keputusan pemilik = usulan bawaan §4,
P14-K1 → Bima). Laporan hasil di `docs/uat/2026-10-21/hasil/UAT24-*.md`.

| ID | Judul | Fase | Status | Berlaku di HEAD | Commit perbaikan | Laporan |
|---|---|---|---|---|---|---|
| P1 | Produk eksklusif & galeri desain: white/customer label, klaim diputus Manajer | F3 | implemented_pending_review | ya — analisis 23 Okt §5 | `e8c7739` | [F3](../uat/2026-10-21/hasil/UAT24-F3.md) |
| P2 | Harga OD: Grade A induk / harga PIC (SO-12), nego lewat harga khusus SO, kunci ≠ pengadaan, biaya tersembunyi | F4 | implemented_pending_review | ya — kode (SO-12 tak pernah diterapkan) | `272575a` | [F4](../uat/2026-10-21/hasil/UAT24-F4.md) |
| P3 | Surat perintah kerja R&D per supplier, PNG cetak, Pantone wajib | F3 | implemented_pending_review | ya — analisis 23 Okt | `e8c7739` | [F3](../uat/2026-10-21/hasil/UAT24-F3.md) |
| P4 | R&D dua pintu (produk baru / uji ulang), rantai tahap, labdip multi-warna, Pustaka dari labdip | F0 (P4.8), F3 | implemented_pending_review | ya — analisis 23 Okt | `663745a`, `e8c7739` | [F0–F2](../uat/2026-10-21/hasil/UAT24-F0-F2.md) · [F3](../uat/2026-10-21/hasil/UAT24-F3.md) |
| P5 | Galat buntu "Kombinasi ini sudah memiliki SKU…" | F3 | implemented_pending_review | ya — analisis 23 Okt | `e8c7739` | [F3](../uat/2026-10-21/hasil/UAT24-F3.md) |
| P6 | Kode/pattern/kategori/tag desain di master produk, POS, Pusat Export | F3 | implemented_pending_review | ya — analisis 23 Okt | `e8c7739` | [F3](../uat/2026-10-21/hasil/UAT24-F3.md) |
| P7 | Menu baru "Perbaikan" (repair & celup ulang) | F5 | implemented_pending_review | ya — fitur belum ada | `2d4d108` | [F5](../uat/2026-10-21/hasil/UAT24-F5.md) |
| P8 | POS/HP sadar lokasi + pelanggan wajib di awal | F1 | implemented_pending_review | ya — analisis 23 Okt | `663745a` | [F0–F2](../uat/2026-10-21/hasil/UAT24-F0-F2.md) |
| P9 | Model lokasi (site → gudang ber-peran), PO ke lokasi, label QR, putaway satu lokasi | F0–F2 | implemented_pending_review | ya — uji alur 23 Okt | `663745a`, `5f52372` | [F0–F2](../uat/2026-10-21/hasil/UAT24-F0-F2.md) |
| P10 | Transfer antar-PT sadar gudang bersama, roll pilihan utuh, barang ke SO peminta | F2 | implemented_pending_review | ya — uji alur 23 Okt | `663745a` | [F0–F2](../uat/2026-10-21/hasil/UAT24-F0-F2.md) |
| P11 | Penanda roll MD Quality / 4-point + sampling | F0, F2 | implemented_pending_review | ya — uji alur 23 Okt | `663745a` | [F0–F2](../uat/2026-10-21/hasil/UAT24-F0-F2.md) |
| P12 | Sorotan POS (Terlaris / Unggulan / Rekomendasi) bisa dinyalakan-dimatikan | F5 | implemented_pending_review | ya — kode | `2d4d108`, `ce7cce4` | [F5](../uat/2026-10-21/hasil/UAT24-F5.md) |
| P13 | Keep & Pending juga terlihat oleh sales (bukti UI + tautan menu) | F5 | implemented_pending_review | sebagian — fitur ada, bukti UI & tautan menu belum | `2d4d108` | [F5](../uat/2026-10-21/hasil/UAT24-F5.md) |
| P14 | Sales hanya melihat pelanggannya sendiri + walk-in | F0 | implemented_pending_review | ya — uji alur 23 Okt | `663745a`, `5f52372` | [F0–F2](../uat/2026-10-21/hasil/UAT24-F0-F2.md) |
| P15 | Gabung beberapa PR (supplier & lokasi sama) → 1 PO + saran untuk MD; OD supplier sama → 1 PO | F0 (bug `kind`), F4 | implemented_pending_review | ya — kode | `663745a`, `272575a` | [F4](../uat/2026-10-21/hasil/UAT24-F4.md) |
| P16 | UI rusak: GRN tanpa kartu, unduh di Jejak Dokumen, Pengaturan berantakan + sapuan 147 layar + audit UI tahap 2 (semua tab/detail/pop-up/HP) | F0, F5 | implemented_pending_review — P16.3 susunan Pengaturan menunggu P16-K1 (mock di laporan) | ya — analisis 23 Okt | `663745a`, `2d4d108`, `ce7cce4`, `78b14b6`, `fb0d069`…`ddad3bc` | [F0–F2](../uat/2026-10-21/hasil/UAT24-F0-F2.md) · [F5](../uat/2026-10-21/hasil/UAT24-F5.md) · [Audit UI 2](../uat/2026-10-21/hasil/UAT24-AUDIT-UI-2.md) |
| P17 | Semua foto yang diunggah bisa dipratinjau tanpa unduh (tanpa token di URL) | F5 | implemented_pending_review | ya — analisis 23 Okt | `2d4d108`, `ce7cce4` | [F5](../uat/2026-10-21/hasil/UAT24-F5.md) |

## Temuan tambahan dari implementer (menunggu konfirmasi reviewer)

| ID usulan | Judul | Status | Laporan |
|---|---|---|---|
| ENV-01 | Data acuan `restore_local_demo.sh` gagal di 3/12 skrip pada HEAD (403 izin/penugasan) | implemented_pending_review (`6e64b2c`) | [ENV](2026-10-20/hasil/ENV.md) |
| ENV-02 | Skrip restore terikat lingkungan Emergent (`supervisorctl`, `localhost`) — perlu varian Docker | implemented_pending_review (`6e64b2c`) | [ENV](2026-10-20/hasil/ENV.md) |
| ENV-03 | `seed_realistic.py` melewati data Interco & SPK printing | open | [validasi](2026-10-20/hasil/VALIDASI_TEMUAN.md) |
| ROLE-01 | 83 gerbang nama peran frontend di luar daftar FE-04 (kelas yang sama) — tombol tidak mengikuti izin efektif server | implemented_pending_review (`ac62dc3`; default matriks `af24f9c`) | [ROLE-GATE-SWEEP](2026-10-20/hasil/ROLE-GATE-SWEEP.md) · [KEPUTUSAN](2026-10-20/hasil/KEPUTUSAN-2026-10-21.md) |

## Keputusan yang ditunggu

| ID | Pertanyaan untuk owner | Dicatat |
|---|---|---|
| AUD2-K | 16 keputusan bisnis audit UI tahap 2 (K-01 definisi piutang, K-02 kas, K-03 DPP vs bruto & tampilan PPN, K-04 stok tersedia, K-05 "Cepat laku", K-06 hitungan Menunggu, K-07 utang antar-PT, K-08 bobot desainer 120 %, K-09 awalan PR- ganda, K-10 bawaan "Langsung dikonfirmasi", K-11 wewenang per peran, K-12 tab Ringkas HP, K-13 glosarium, K-14 ambang alasan, K-15 tutup buku saat Suspense ≠ 0, K-16 Labdip tanpa handfeel) — rincian di [Audit UI 2](../uat/2026-10-21/hasil/UAT24-AUDIT-UI-2.md) › rencana-perbaikan §5.3 | 2026-10-26 |
| AUD2-D | 29 kandidat duplikasi layar & 10 pekerjaan tata letak besar dari audit UI tahap 2 (rencana-perbaikan §5.1–5.2) | 2026-10-26 |
| P16-K1 | Setujui susunan baru menu Pengaturan (7 kelompok, mock di [F5](../uat/2026-10-21/hasil/UAT24-F5.md)) sebelum menu dipindah | 2026-10-24 |
| UI-DUP | Kandidat layar duplikat dari sapuan UI (daftar di [F5](../uat/2026-10-21/hasil/UAT24-F5.md) › "Kandidat duplikasi") — gabung/jadikan alias? | 2026-10-24 |

## Riwayat perubahan tracker

| Tanggal | Oleh | Perubahan |
|---|---|---|
| 2026-10-26 | Claude Code | Audit UI tahap 2 ([Audit UI 2](../uat/2026-10-21/hasil/UAT24-AUDIT-UI-2.md)): crawler mendalam 156 layar desktop + 117 titik awal aplikasi HP (2.395 keadaan, 388 pop-up unik, 255 detail, 442 tab), 243 butir perbaikan (47 T/163 S/33 R) dikerjakan 7 grup paralel (`fb0d069`…`ddad3bc`) + perbaikan hasil verifikasi; verifikasi desktop 73/80 butir terverifikasi; P16 tetap implemented_pending_review; keputusan AUD2-K/AUD2-D dicatat |
| 2026-10-25 | Claude Code | UAT 24 Okt lanjutan sapuan UI (`78b14b6`, [F5 › Lanjutan](../uat/2026-10-21/hasil/UAT24-F5.md)): ATP 057=058, saldo rekening vs kas, qty profitabilitas per satuan, Beranda Bulan Ini vs Hari Ini, label Tagihan HP, akun teknis keluar dari KPI desainer, status & petunjuk PDF, pelacak SO meja Admin Sample, ikon KNSelect, pemilih tanggal/jam, chip filter Barang Masuk — status P16 tetap implemented_pending_review |
| 2026-10-24 | Claude Code | UAT 24 Okt F5 implemented_pending_review ([F5](../uat/2026-10-21/hasil/UAT24-F5.md)): P7 menu Perbaikan, P12 sorotan POS, P13 tab Keep & Pending, P16.1 GRN, P16.2 PDF di Jejak Dokumen, P17 pratinjau lampiran (`2d4d108`) + sapuan UI 147 layar (`ce7cce4`); P16-K1 & kandidat duplikasi dicatat sebagai keputusan yang ditunggu |
| 2026-10-24 | Claude Code | Paket UAT 24 Okt dicatat (P1..P17): F0–F3 implemented_pending_review (`663745a`, `5f52372`, `e8c7739`; laporan [F0–F2](../uat/2026-10-21/hasil/UAT24-F0-F2.md), [F3](../uat/2026-10-21/hasil/UAT24-F3.md)); F4 P2 + P15 implemented_pending_review (`272575a`, [F4](../uat/2026-10-21/hasil/UAT24-F4.md)); P7, P12, P13, P16 (sisa), P17 open (F5) |
| 2026-10-21 | Claude Code | F-07/F-04/F-17/F-02/F-08 implemented_pending_review ([laporan](../uat/2026-10-21/hasil/F-07-F-04-F-17-F-02-F-08.md)): stempel waktu & pelaku transisi SO + "Disiapkan" menghitung tugas terkirim; KPI POS per satuan; nilai antrean retur; stok strip Sering dibeli = katalog; Faktur Komersial sebagai dokumen tagihan di Perjalanan (default implementer, mohon review Finance) — semua dicek di UI. Seluruh 17 temuan UAT kini berstatus implemented_pending_review |
| 2026-10-21 | Claude Code | F-13 implemented_pending_review (`debc38a`, [F-13](../uat/2026-10-21/hasil/F-13.md)): keputusan Q-06b — hasil SPK (MD Quality/QC/umum) hanya sesudah SPK ditugaskan; tombol di SPK draft disembunyikan + petunjuk — dicek di UI |
| 2026-10-21 | Claude Code | F-15 implemented_pending_review (`049c8ab`, [F-15](../uat/2026-10-21/hasil/F-15.md)): keputusan Q-04 — toleransi selisih tagihan sample (`sales.sample_payment_tolerance_pct`, 5%) otomatis, di atasnya persetujuan ulang + kiriman ditahan; cek UI: tautan ?doc=SOS- kini membuka Pesanan Sample |
| 2026-10-21 | Claude Code | F-14 implemented_pending_review (`22b0d1b`, [F-14](../uat/2026-10-21/hasil/F-14.md)): keputusan Q-03a — menutup SPK penerimaan PO sekaligus memutus karantina (roll per baris, grade 4-point, retur/rusak), antrean karantina menunjuk SPK (keputusan kedua 409), seed data acuan lewat SPK (restore 9/9 OK) — dicek di UI |
| 2026-10-21 | Claude Code | F-16 implemented_pending_review (`4cc39f7`, [F-16](../uat/2026-10-21/hasil/F-16.md)): keputusan Q-05a — jatuh tempo = SJ pertama + kode termin SO (SSOT `due_context`) di status kredit, daftar tagih/Meja Finance, umur piutang, pengingat, Tanya KN, proyeksi kas; SO belum dikirim tidak masuk daftar — dicek di UI |
| 2026-10-21 | Claude Code | F-06 implemented_pending_review (`1312fa1`, [F-06](../uat/2026-10-21/hasil/F-06.md)): keputusan Q-01a — POD semua Surat Jalan (kurir/sopir/serah terima ambil sendiri) menutup SO otomatis; progres POD di detail SO; tombol pelacak "Catat POD" membuka Logistik tersaring — dicek di UI |
| 2026-10-21 | Claude Code | F-10 implemented_pending_review (`a039932`, [F-10](../uat/2026-10-21/hasil/F-10.md)): keputusan Q-02 — termin CBD/DP menahan kirim di semua jalur (409), pengecualian berizin `order.release_unpaid` beralasan & teraudit (dapat dicabut), setting Pusat Pengaturan `finance.dispatch_payment_gate`; status tahan di Barang Keluar, meja Gudang, pelacak SO, detail SO — dicek di UI. Cek UI putaran 3–4 (`e20b149`): tombol Tinjau nota kredit Meja Finance diperbaiki |
| 2026-10-21 | Claude Code | Keputusan owner putaran 4 #3 ([laporan](../uat/2026-10-21/hasil/KEPUTUSAN-OWNER-P4.md)): batal item OD pada SO terbit → nota kredit otomatis menunggu Finance (koreksi/terbit/batal, izin `finance_amendment.review_credit_note`, antrean Meja Finance); pertanyaan "FE-01 SO terbit" selesai |
| 2026-10-21 | Claude Code | Keputusan owner putaran 4 #2 ([laporan](../uat/2026-10-21/hasil/KEPUTUSAN-OWNER-P4.md)): akses lintas badan usaha dapat diatur per peran (bawaan & kustom; kustom ikut peran acuan; Admin dikunci); pertanyaan "ROLE-01 lintas PT" selesai; jawaban Q-01..Q-06 (UAT) dicatat |
| 2026-10-21 | Claude Code | Keputusan owner putaran 4 #1 ([laporan](../uat/2026-10-21/hasil/KEPUTUSAN-OWNER-P4.md)): baris dihapus (Override SO / batal item OD) → entri harga khusus produk itu otomatis dibatalkan, riwayat tetap; pertanyaan "F-09 baris dihapus" selesai |
| 2026-10-21 | Claude Code | Keputusan owner putaran 3 ([laporan](../uat/2026-10-21/hasil/KEPUTUSAN-OWNER-P3.md)): antrean "Retur menunggu terima / QC" di Meja Operator & Admin Gudang, Gudang/QC mengunduh foto/video bukti, perbaikan data F-09 sebagai migrasi startup sekali jalan (produksi ikut saat deploy); 3 pertanyaan terjawab, 3 jawaban putaran 4 dicatat (sedang dikerjakan) |
| 2026-10-21 | Claude Code | Cabang uji pra-UAT digabung ke `main` (F-11/F-12 + F-11-layar, F-09, F-05/F-03/F-01) + dokumen UAT v2.0 di-commit; penyelarasan pasca-gabung: tes F-09 memakai sandi tunggal F-01, tes layanan memakai loop bersama `tests/_shared_loop.py`. Uji gabungan di backend & DB terpisah (data acuan seed baru): 201 lulus; gagal tersisa = sama di kode pra-gabung. Status temuan tidak diubah |
| 2026-10-21 | Claude Code | F-11-layar implemented_pending_review (`a7c08c3`, [F-11-layar](../uat/2026-10-21/hasil/F-11-layar.md)): keputusan owner opsi (b) — Gudang/QC (`wms.scan`/`qc.inspect` tanpa `sales_return.view`) membuka daftar approved/inspecting, detail/timeline tanpa field uang, tab & menu Retur; matriks izin tidak diubah; 2 pertanyaan owner baru |
| 2026-10-21 | Claude Code | F-11/F-12 implemented_pending_review (`6e1112b`, [F-11-F-12](../uat/2026-10-21/hasil/F-11-F-12.md)): scan perjalanan retur menerima `wms.scan`, QC retur menerima `qc.inspect`; QC hanya sesudah semua roll klaim diterima/tiba (baris tanpa roll: tonggak Barang sampai); diskon foto KLR-06 tetap. Catatan: Gudang/QC belum punya akses layar retur (`sales_return.view`) |
| 2026-10-21 | Claude Code | 11 temuan AUD backend implemented_pending_review sesuai urutan paket ([BE-AUD](2026-10-20/hasil/BE-AUD.md)): RND-01/02 `c56a988`, EXP-01 `db25c74`, SO-01 `193c048`, WMS-01 `6974dd9`, MKL-01/02 `ae4e1b3`, EXP-02 `1e275ca`, MIG-01/02 `8d6df8f`, RET-01 `28d53c7`; guardrail INV-ATOMIC-01 kembali ke baseline `8dab383` (`1dcd37e`) |
| 2026-10-21 | Claude Code | Uji pra-UAT F-09 implemented_pending_review (`627a4c1`, [F-09](../uat/2026-10-21/hasil/F-09.md)): pengajuan ulang harga khusus/kredit menggantikan penolakan lama, submit ulang diarahkan ke Pusat Persetujuan, skrip perbaikan data lama; 2 pertanyaan baru |
| 2026-10-21 | Claude Code | F-05/F-03/F-01 implemented_pending_review (`98695cf`, `3f8ce21`, `941a9c2`, [F-05-F-03-F-01](../uat/2026-10-21/hasil/F-05-F-03-F-01.md)): alokasi SO ditautkan ke roll anak saat potong + sidik harga khusus stabil; segmen asal/grade/LOT `variant_label` disaring per field_visibility; satu sandi demo `demo12345` untuk semua akun seed (93 tes lama disesuaikan) |
| 2026-10-21 | Claude Code | Jawaban owner putaran 2 ([laporan](2026-10-20/hasil/KEPUTUSAN-2026-10-21.md#bagian-2--jawaban-owner-putaran-kedua-2026-10-21)): kontrak kedaluwarsa/batal (`1ad79cb`), batal item sesudah SO + notifikasi MD (`a3f7936`), backend role_in (`b69fe0d`), sisir lanjutan FE (`fc477ce`); 3 pertanyaan lama terjawab, 2 baru |
| 2026-10-21 | Claude Code | FE-10..13 implemented_pending_review (`85ddd1c`, [UI-05](2026-10-20/hasil/UI-05.md)): satuan sumber antrean QC, status muat penerimaan transfer, neraca belum diketahui netral, tanda saldo kumulatif |
| 2026-10-21 | Claude Code | FE-06..09 implemented_pending_review (`c5fd627`, [UI-04](2026-10-20/hasil/UI-04.md)): target antrean harga khusus + fokus dokumen + guardrail desk_targets, error aksi retur di layar aktif, form retur aman balapan, pemilih SO retur server-side |
| 2026-10-21 | Claude Code | Jawaban owner dicatat & dikerjakan ([laporan](2026-10-20/hasil/KEPUTUSAN-2026-10-21.md)): AUD-RND-03 implemented_pending_review (`af24f9c`); FE-01 + batal per item (`13c64d8`); ROLE-01 default matriks izin QC/retur/master entitas (`af24f9c`); 3 pertanyaan lanjutan dicatat |
| 2026-10-20 | Claude Code | Tracker dibuat dari paket 2026-10-20 (13 FE + 12 AUD); semua `open` kecuali AUD-RND-03 `pending_decision` |
| 2026-10-21 | Claude Code | ROLE-01 (usulan) implemented_pending_review (`ac62dc3`): 83 gerbang peran disisir — 70 ke izin endpoint, 4 peringkat penyetuju, 3 peran acuan, 2 kode mati dihapus, 8 tetap (aturan peran server/teks); perubahan tampilan peran bawaan & yang perlu direview di laporan |
| 2026-10-20 | Claude Code | FE-03/04/05 implemented_pending_review (`9289e26`, `859a087`): menu peran kustom, tombol per izin, petugas inspeksi per kemampuan+scope, Data Gudang scope sah; 81 gerbang peran lain dicatat sebagai keterbatasan |
| 2026-10-20 | Claude Code | FE-02 implemented_pending_review (`0d8e202`, `6350391`, `621f50b`): 9 kontrol Interco + bentuk prop selectedEntity + guardrail |
| 2026-10-20 | Claude Code | FE-01 implemented_pending_review (`cc4d13a`): harga & konversi per item, 7 tes baru; usul `pending_decision` batal per item OD |
| 2026-10-20 | Claude Code | ENV-01/02 implemented_pending_review (`6e64b2c`): akar ENV-01 = cookie jar klien seed menimpa Bearer, bukan regresi izin |
| 2026-10-20 | Claude Code | Validasi benar/false positive: 24 benar (4 direproduksi runtime), AUD-MKL-01 bagian 2 false positive, AUD-RND-03 menunggu keputusan; usulan ENV-01..03 ([laporan](2026-10-20/hasil/VALIDASI_TEMUAN.md)) |
| 2026-10-20 | Claude Code | Cek ulang tingkat kode di `f4e8f0b`: 25/25 masih berlaku, 0 sudah diperbaiki ([laporan](2026-10-20/hasil/CEK_ULANG_HEAD.md)); reproduksi runtime per fase |
