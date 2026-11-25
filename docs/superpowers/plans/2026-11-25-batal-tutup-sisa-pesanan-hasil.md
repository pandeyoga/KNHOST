# Hasil — Tutup sisa pesanan & persetujuan pembatalan (A1/A2)

Tanggal: 25 Nov 2026 · Cabang: `claude/nifty-carson-jjx3c8` · Garis dasar: `f14b559` (HEAD sebelum Tugas 1).
Spesifikasi: `docs/superpowers/specs/2026-11-25-batal-tutup-sisa-pesanan-design.md` · Rencana:
`docs/superpowers/plans/2026-11-25-batal-tutup-sisa-pesanan.md`.

Status: **selesai, menunggu pemeriksaan pemilik**. Belum digabung ke `main`.

## 1. Tugas → commit → uji

| Tugas | Isi | Commit | Uji resmi |
|---|---|---|---|
| BTP-1 Fondasi | izin `order.approve_cancel` (admin/manager/finance), jenis persetujuan `sales_order.batal` (antrean `so_cancel`, satu jenjang), pengaturan `sales.cancel_approval_when` | `51095b7`, `1b7bfbe`, `5146d11` | `test_BTP1_fondasi.py` (5), PRT9, KFT1, KFT4, KPT4a |
| BTP-2 Permintaan batal | `so_cancel_service`: ajukan / putus / tarik, 202 bila perlu persetujuan, penyetuju bukan sales pesanan, notifikasi per izin | `20be50b`, `f7647fa` | `test_BTP2_permintaan_batal.py` (33) |
| BTP-3 Tahan gudang | kirim/ambil/kemas/eskalasi/batal baris ditolak 409 selama ada permintaan; tanda `held_reason` di tugas gudang | `3565c8e` | `test_BTP3_tahan_gudang.py` (10) |
| BTP-4 Tutup sisa | jumlah pesanan = terkirim, nilai = yang dibukukan per Surat Jalan, kelebihan uang → titipan, jadwal tagihan ikut nilai baru, penolak kasus langka | `ebc4862`, `0cd9e11` | `test_BTP4_tutup_sisa.py` (31) |
| BTP-5 Koreksi komisi | koreksi di bulan penutupan, bulan final memakai dasar asli, saldo potongan terbawa (`commission_carry_balances`) | `f45ebc5`, `a5c999d`, `a57cadb`, `965ca11` | `test_BTP5_komisi_koreksi.py` (25) |
| BTP-6 Layar pesanan | dialog ajukan batal, dialog tutup sisa (ringkasan sebelum → sesudah), bilah menunggu persetujuan | `0d2eb4c`, `28c4e9e` | jest `btpBatalTutupSisa.test.js` (14) |
| BTP-7 Pusat Persetujuan | tab antrean pembatalan, tanda "ditahan" di gudang desktop & HP, teks berbasis izin | `f22279b`, `94452c9` | jest `btpInboxBatal.test.js` (6) |
| Tinjauan akhir | C1 roll `committed` bukan "disiapkan"; I1 bulan final pra-rilis dibaca dari jurnal; I2 satu jenjang; I3 hasil eksekusi tampil + galat langkah 6 ke Finance; I4 umur antrean; M6/M8/T4 | `e0d9e9a`, `173902c`, `7a6315a`, `7dd4eba`, `21d494c`, `f6b0dcc` | tambahan di BTP2/BTP4/BTP5 + jest |
| BTP-8 | uji penuh, gate, laporan ini | (commit laporan) | — |

## 2. Angka uji (apa adanya)

* **Backend** `tests_mem` penuh di `5146d11`: **2809 passed, 2 skipped, 3 xfailed, 0 failed** (539 detik).
  Commit sesudahnya (`28c4e9e`) hanya mengubah satu berkas layar.
* **Jest** penuh di `5146d11`: **1830 dari 1832 lulus**. Gagalnya:
  * `odItemCancel`: juga gagal di garis dasar `f14b559` (plugin babel penyunting visual menyisipkan `x-file-name` yang memecah teks). Penyebabnya lingkungan.
  * `phase4R2` (FilterBuilder): suite gagal dimuat karena babel "Maximum call stack size exceeded". Juga terjadi di garis dasar; lingkungan.
  * `masukan16Nov` M3: lulus 9/9 dua kali bila dijalankan sendiri, dan lulus di garis dasar. Tidak stabil di jalan penuh, bukan regresi.
* Sesudah `28c4e9e`: jest `btpBatalTutupSisa` + `latihS3BatalUangMuka` lulus (16), dan penjaga `verify_custom_modals` PASS.
* **Gate `--quick`** dibanding garis dasar `f14b559` (`scripts/blueprint/bandingkan_pelanggaran_gate.py`):
  * jalan pertama di `5146d11`: 1 pelanggaran baru, `guard:custom_modals` (dialog tutup sisa merakit pop-up sendiri). Diperbaiki di `28c4e9e` (FormModal).
  * jalan ulang di pohon akhir: lihat §2a.
* **Tidak dijalankan:** uji live-server `backend/tests` (admin sebagai `sales_id`) dan uji balapan nyata dua penyetuju (R6). Belum ada server uji di jalur tugas; tidak menyentuh data nyata.

### 2a. Gate ulang di pohon akhir

`bash scripts/gate.sh --quick` di `28c4e9e`: **MERAH** (exit 1, 111 detik), sama seperti garis dasar.

* Hitungan baris merah: 91 di garis dasar `f14b559`, 91 di pohon akhir. Baris lulus: 210 dan 210.
* `bandingkan_pelanggaran_gate.py`: **"tidak ada pelanggaran baru"**.
* Merahnya pra-ada dan di luar lingkup ini, antara lain:
  * batas angka skema (INV-NUM-01), cakupan auth `handheld`/`design_gallery` (INV-AUTH-01);
  * tombol buat inline (INV-UI-05), awalan uang di idempotensi, `to_list` besar (INV-PERF-01);
  * hapus dokumen ber-tautan (INV-REF-04), label i18n, cakupan gudang.
* `memory/GATE_RECEIPT.md` dipulihkan (tidak di-commit).

## 3. Keputusan yang diambil selama pelaksanaan (bukan dari pemilik — periksa)

Lengkap di spesifikasi §7. Ringkas:

| # | Keputusan | Alasan | Akibat bila salah |
|---|---|---|---|
| R1 | Bentuk butir daftar permintaan pembatalan (nomor, pelanggan, aksi, nilai, alasan, pengaju, dasar) | dibutuhkan layar Pusat Persetujuan | pemetaan layar menyesuaikan |
| R2 | Garis dasar gate `f14b559`, bukan `25078cf` | pelanggaran lama tidak boleh tercatat "baru" | perbandingan gate diulang |
| R3 | Jest dijalankan dengan batas stack dibesarkan | kendala wadah, bukan kode | tidak ada |
| R4 | Antrean & putusan memakai cakupan data penyetuju | konsisten dengan izin lihat | penyetuju bercakupan "milik sendiri" tidak melihat antrean |
| R5 | Persetujuan ditegakkan langsung, tidak memakai `dual_control` | `dual_control` punya sakelar & jalan pintas admin | tidak ada |
| R6 | Uji live-server & balapan nyata tidak dijalankan | tidak ada server uji | lihat §2 |
| R7 | Semua penyelesaian eskalasi gudang ditahan selama permintaan | "gudang ditahan" (A2-4) | manajer menunggu keputusan dulu |
| R8 | Trailer commit subagen lama dibiarkan | riwayat sudah di-push | hanya inkonsistensi trailer |
| R9 | Jadwal tagihan pesanan tutup sisa ikut nilai baru | tidak menagih melebihi barang terkirim | jadwal salah hitung untuk termin DP |
| R10, R12 | Tolak tutup sisa bila ada rencana cicilan manual aktif | kasus langka, jangan menebak | Finance menyesuaikan cicilan dulu |
| R11, R22 | Jumlah jual disimpan 6 desimal, tampil maks 2 desimal | pembagian nilai per Surat Jalan | selisih pembulatan tampilan |
| R13 | Satu catatan saldo potongan per (sales, PT, bulan), ditulis dari semua jalur finalisasi | "sisa terbawa sampai habis" (A1-6) | koleksi/indeks perlu diubah |
| R14 | Bulan berakrual tidak bergeser di batas margin/pita harga | menjaga angka yang sudah dibayar | — |
| R15 | Pengali capaian bulan penutupan dipakai untuk koreksi | **batasan versi pertama**; pengali masih nonaktif bawaan | potongan berbeda faktor saat pengali dinyalakan |
| R16–R19 | Bulan yang sudah final sebelum peristiwa memakai dasar asli; yang belum final memakai dasar baru; nilai baru = satu batas; waktu final = waktu hitung | §5.9 spesifikasi | koreksi komisi berbeda |
| R20, R25, R28 | Tanpa backfill data. Bulan pra-rilis dianggap final bila ada jurnal akrual hidup / jurnal gaji terposting untuk PT·bulan itu (dibaca saat menghitung) | tidak menulis data nyata | bulan pra-rilis yang diakru dianggap final (sesuai maksud A1-6) |
| R21 | `cancel-check?action=close_remaining` mengembalikan 200 + daftar penghalang saat terblok | dialog perlu menampilkan alasan | satu cabang di endpoint |
| R23 | Prop `userId` tambahan di bilah permintaan | menyembunyikan tombol putus bagi pengaju | tidak ada |
| R24, R32 | Uji penuh & gate sekali di pohon akhir; laporan ditulis pengendali | uji hemat | tidak ada |
| R26 | Pembatalan hanya satu jenjang persetujuan (jenjang 2 ditolak saat disimpan) | penyetuju tunggal (A2-2) | pemilik tidak bisa memasang dua jenjang untuk pembatalan |
| R27 | "Barang sudah disiapkan" = roll `picked`/`packed` (atau bukti ambil/kemas/staging di tugas); `committed` tidak dihitung | maksud A2-1 | tidak ada |
| R29 | Uji "disiapkan" hanya dari bukti tugas belum ada | kode benar menurut pembacaan | regresi tak terdeteksi bila cabang itu diubah |
| R30 | Baris kebijakan jenjang ≥ 2 tanpa jenjang 1 (hanya bila disisipkan manual) membuat permintaan tak bisa diputus | simpan lewat layar kini ditolak | Admin membersihkan baris manual |
| R31 | Baris "potongan terbawa" bertanda minus membuat Σ rincian ≠ total tampil | label menjelaskan | sales bisa salah baca bulan bersaldo |
| R33 | Pelanggaran gate baru diperbaiki sebelum laporan | gate dinilai per pelanggaran | satu putaran kecil |

## 4. Sebelum rilis ke VPS

* **Tidak ada migrasi data.** Pesanan lama tanpa `closed_short` / `cancel_request` berperilaku sama. Indeks baru `uq_commission_carry` dibuat otomatis saat backend mulai.
* **Izin baru** `order.approve_cancel`: bawaan untuk admin, manager, finance. **Peran kustom** yang harus bisa memutus pembatalan perlu diberi izin ini lewat Pengaturan Peran.
* **Pengaturan** `sales.cancel_approval_when` bawaan `dibayar_atau_disiapkan` per PT. Ubah bila PT ingin `selalu` / `tidak_pernah`.
* **Keputusan pemilik sebelum rilis:**
  1. R15: pengali capaian bulan penutupan dipakai untuk koreksi. Periksa sebelum menyalakan pengali capaian.
  2. R20/R25: tidak ada backfill catatan finalisasi. Bulan pra-rilis dibaca final dari jurnal akrual/gaji yang hidup.
  3. Run gaji **draf** yang dibuat sebelum deploy sebaiknya **dihitung ulang** sesudah deploy (saldo potongan baru tercatat saat hitung).
  4. Disarankan perbandingan komisi sebelum/sesudah pada data acuan sebelum rilis.

## 5. Tindak lanjut (di luar lingkup ini)

* Uji live-server & balapan dua penyetuju (R6); uji "disiapkan" dari bukti tugas (R29).
* Tampilan sisa potongan di bawah total, bukan baris penjumlah (R31).
* Balapan penyelesaian eskalasi vs pengajuan (R11, risiko diketahui).
* `OrdersView.onCancel` (tombol batal di daftar) masih mengirim tanpa alasan. Hanya pesan 202 yang diperbaiki.
* Perombakan notifikasi: rancangan terpisah (audit `docs/audit/notifikasi-2026-11-25/`).
