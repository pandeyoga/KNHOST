# Hasil — Meja gelombang 1 (kerangka meja kerja di tempat)

Tanggal: 25 Nov 2026 · Cabang: `claude/nifty-carson-jjx3c8` · Garis dasar: `b78d0bf` · Pohon akhir: `b88a649`.
Rancangan: `docs/superpowers/specs/2026-11-25-meja-kerja-di-tempat-design.md` (disetujui pemilik, A0–A9) · Rencana:
`docs/superpowers/plans/2026-11-25-meja-gelombang-1.md` (17 tugas) · Audit awal: `docs/audit/meja-2026-11-25/`.

Status: **selesai**. Belum digabung ke `main`. Atas perintah pemilik ("langsung lanjut kerjakan saja semua"), pekerjaan
lanjut ke gelombang berikutnya tanpa menunggu validasi; tangkapan di bawah dikirim untuk diperiksa.

## 1. Yang berubah untuk pengguna

| Keluhan pemilik | Sekarang |
|---|---|
| Bertumpuk | Satu kepala (judul + ikon ?); tab **Antrean** / **Pantau**. Kartu angka, paragraf, dan kotak "bukan wewenang" hilang (pindah ke ?). Pelacak SO, Keep & Pending, Aturan Grade, kartu retur pindah ke Pantau. Tinggi halaman: Keuangan 2,5→1,7 layar, Meja Saya manajer 2,1→1,7, Sample 1,5→1,0, Admin Sales 3,3→3,1. MD dan Gudang naik (1,9→2,2 dan 1,7→2,2) karena kartu kosong kini setinggi 5 baris sesuai keputusan P3. |
| Klik tidak membuka rincian | **Klik baris membuka pop-up rincian** di semua meja + HP. Teks utuh, PT, status, nilai, waktu masuk nyata, daftar barang, lalu "Buka layar penuh". Keyboard: tombol nomor dokumen. |
| Harus pindah halaman | Aksi di tempat lewat pop-up: periksa & lepas, pemenuhan, lepas/teruskan ke gudang, terbit faktur pajak, setujui bayar sample, terima pembayaran (juga dari kartu Piutang), cetak dokumen pesanan, buat SPK QC dengan pesanan terpilih, terima hasil potong. Panel per jenis dokumen untuk aksi lain = gelombang 2–3. |
| Aksi berbahaya sekali klik | **Selalu pratinjau + konfirmasi**, juga di layar asalnya: terbit faktur pajak (pop-up Faktur Keluaran yang sama), setujui bayar sample (pemeriksaan uang masuk yang sama dengan daftar), lepas/teruskan ke gudang (pesanan, PT, gudang, barang; terkunci bila data gagal dimuat). Tinjauan akhir memastikan tak ada lagi jalur sekali-klik di seluruh aplikasi. |
| Isi kurang | PT di baris (mode Semua PT) dan pop-up, waktu masuk nyata (bukan tebakan), teks tak lagi dipotong server, semua barang kurang, batas cadangan, pelanggan & SKU di Meja Cutting, waktu tunggu Cutting. |
| Huruf tidak konsisten | Kerangka meja hanya `text-fs-12/13/14/16/20`, minimal 12 px, peran huruf tetap. Panel rincian yang dipakai ulang diseragamkan di gelombang 2–3 (A7). |
| Duplikasi | Satu nama per meja: **Meja Admin Sales · Meja Keuangan · Meja Gudang · Meja Sample · Meja MD · Meja Saya**. Piutang lewat tempo tidak lagi dobel di "Uang masuk"; "Giliran saya" tidak mengulang antrean lain. Pesanan sample bukan giliran Manajer lagi. |

Tangkapan sesudah: folder `2026-11-25-meja-gelombang-1-hasil/` (`sesudah_<meja>_antrean|popup|pantau.jpg`, HP).
Bandingkan dengan sebelum: `docs/audit/meja-2026-11-25/tangkapan/01–10`.

## 2. Tugas → commit

| Tugas | Commit |
|---|---|
| T1–T3 Server: PT/waktu/teks utuh; sample bukan giliran manajer; isian pratinjau aksi | `c8045d3`, `907a00f`, `ad222b6`, `135c060` |
| T4 Pop-up rincian umum + registri panel | `1ff973d` |
| T5 Kartu antrean ukuran tetap, baris ringkas, status tersimpan | `8823236`, `2b31127` |
| T6 Kerangka meja (kepala, ?, Antrean/Pantau, toast, gulir) | `e5fec68`, `3f26e42` |
| T7 Isi Pantau, Pelacak SO bisa dibuka | `a44d6be`, `185620d` |
| T8 Satu nama per meja | `83f6d6c`, `b88a649` |
| T9 Konfirmasi faktur pajak | `72f38fb` |
| T10 Konfirmasi lepas/teruskan ke gudang | `c7203d7` |
| T11 Setujui bayar sample | `d732d21` |
| T12 Pop-up periksa & pemenuhan → FormModal | `6a8a7cd`, `c46a94d` |
| T13 Hapus ganda antar kartu | `f4f31c2` |
| T14 Cetak di tempat, SPK QC terpilih | `f9d1493` |
| T15 Meja Cutting | `74e3502`, `1596454` |
| T16 HP | `8bdfa9a`, `4529852` |
| T17 Standar `04_POLA_UI.md`; perbaikan tinjauan akhir | `cecf47f`, `f0b4e1f` |

Setiap tugas: pelaksana → tinjauan tugas (spesifikasi + mutu) → putaran perbaikan bila perlu; lalu tinjauan seluruh
cabang (0 Critical, 3 Important — skrip latihan, lepas tanpa pratinjau, rantai pajak mati — diperbaiki di `f0b4e1f`).

## 3. Uji (apa adanya)

- **Backend** `tests_mem` penuh di `f0b4e1f`: 2837 passed, 2 skipped, 3 xfailed, **1 failed**. Yang gagal `test_PRT4_sapuan::U13`: data acuannya masih memuat judul meja lama. Diperbaiki di `b88a649`: 7 nilai `judul` diganti → "Meja Saya", jumlah antrean/item tidak berubah. Sesudah itu PRT4 17/17 lulus.
- **Jest** penuh di `f0b4e1f`: 1936/1937 lulus, 253/255 suite. Gagal `odItemCancel` dan `phase4R2`. Keduanya kendala lingkungan wadah yang sama dengan garis dasar sebelum pekerjaan ini (plugin babel `x-file-name` memecah teks; stack babel di FilterBuilder).
- **Gate:** lihat §3a.
- **Skrip latihan** (`docs/pelatihan/2026-11-18_keuangan/uji/`) disesuaikan dengan dialog baru dan lolos `node --check`. Belum dijalankan di lingkungan hidup.

### 3a. Gate

(diisi sesudah gate selesai)

## 4. Keputusan pelaksanaan (di luar rancangan — periksa)

Lengkap di buku catatan pengendali; yang mengubah perilaku:

- **Tinggi kartu.** Ditetapkan 412 px, diukur di Chrome; rencana menulis 404.
- **Baris kartu.** Baris bisa diklik mouse; untuk keyboard, tombolnya adalah nomor dokumen. Baris tidak dijadikan tombol karena berisi tombol lain (aturan aksesibilitas).
- **Meja Keuangan.** "Pantau" adalah tab hub saudara di Beranda Keuangan, bukan tab ketiga.
- **Penjaga INV-UI-08.** Perubahan logika penjaga dibatalkan; meja yang membuka pop-up rincian didaftarkan sebagai pengecualian beralasan (`DIBOLEHKAN`).
- **Satuan barang.** Satu aturan: jumlah + satuan jual pesanan, sama dengan Faktur Komersial.
- **Meja Cutting.**
  - Info tunggu lama dikembalikan: "menunggu …", "diterima setelah …", lencana Terlambat.
  - Aksi terima hanya untuk baris yang menunggu diterima dan pengguna berizin.
- **HP.**
  - Tujuan layar HP boleh langsung dari tombol aksi.
  - Tujuan layar desktop membuka pop-up dulu.
  - Kartu tetap bisa dibuka-tutup.
- **"Setujui Ulang" sample** kini juga memperingatkan kurang bayar (tombol "Tetap setujui"). Bayar lunas = satu klik konfirmasi tambahan.
- **Konfirmasi faktur pajak** juga dipasang di rincian pesanan; tombol lama yang sekali-klik dihapus.

## 5. Catatan kecil yang ditunda (tidak memblokir)

- **Meja Keuangan:**
  - dua tab hub berbagi kunci "finance" untuk pemulihan gulir;
  - Pantau memuat data meja penuh hanya untuk teks ?;
  - di pop-up "lewat tempo", "Keterangan" mengulang "Lewat jatuh tempo".
- **Pop-up dan formulir:**
  - tombol nomor belum punya gaya fokus eksplisit;
  - formulir SPK QC: bila pesanan di luar 150 opsi terbaru, pilihan tampil kosong.
- **Hapus ganda Giliran saya** sebaiknya hanya terhadap kartu tab Antrean.
- **Kartu retur internal:** ukuran huruf lama di isinya; berkedip saat muat ulang.
- **Materi pelatihan** (`Panduan_*.html`, `LEMBAR_LATIHAN.md`) masih menyebut "Perlu Tindakan".

## 6. Gelombang berikutnya (urutan G1)

Lanjut tanpa menunggu: **gelombang 2**:
- Admin Sales + Meja Keuangan dengan panel per jenis dokumen dan aksinya di pop-up;
- rincian barang saat nomor nota diklik di semua layar Keuangan (§5.7a);
- penyeragaman huruf panel yang dipakai ulang (A7);
- lalu **Lapor Bayar CBD**.

Sesudah itu: kwitansi otomatis dari mutasi bank → paket Kas & Bank (menunggu jawaban C4 dan H5) → gelombang 3.
