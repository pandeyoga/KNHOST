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
| F-11 | Gudang & QC tidak bisa memproses perjalanan & QC retur (403 `sales_return.update`) | P1 | implemented_pending_review | ya — direproduksi runtime di `193c048` | `6e1112b` | [F-11-F-12](../uat/2026-10-21/hasil/F-11-F-12.md) |
| F-12 | QC retur bisa dimulai & diselesaikan tanpa barang diterima | P1 | implemented_pending_review | ya — direproduksi runtime di `193c048` | `6e1112b` | [F-11-F-12](../uat/2026-10-21/hasil/F-11-F-12.md) |
| F-11-layar | Gudang & QC tidak bisa membuka layar retur (daftar/detail/timeline 403, tab & menu tersembunyi) — keputusan owner opsi (b) terbatas | P1 | implemented_pending_review | ya — direproduksi runtime di `68e4449` | `a7c08c3` | [F-11-layar](../uat/2026-10-21/hasil/F-11-layar.md) |
| F-09 | Entri persetujuan yang ditolak mengunci SO selamanya (harga khusus & kredit) | P1 | implemented_pending_review | ya — direproduksi runtime (SO-00039, SO-00083) | `627a4c1` | [F-09](../uat/2026-10-21/hasil/F-09.md) |
| F-05 | Alokasi SO tidak mengikuti roll anak setelah potong (pick dari daftar ditolak) | P1 | implemented_pending_review | ya — direproduksi runtime di `193c048` | `98695cf` | [F-05-F-03-F-01](../uat/2026-10-21/hasil/F-05-F-03-F-01.md) |
| F-03 | Grade & LOT bocor ke Sales lewat `variant_label` | P1 | implemented_pending_review | ya — direproduksi runtime di `193c048` | `3f8ce21` | [F-05-F-03-F-01](../uat/2026-10-21/hasil/F-05-F-03-F-01.md) |
| F-01 | Login cepat per peran gagal (seed `demo1234` vs tombol `demo12345`) | P1* | implemented_pending_review | ya — direproduksi runtime di `193c048` (data acuan restore) | `941a9c2` | [F-05-F-03-F-01](../uat/2026-10-21/hasil/F-05-F-03-F-01.md) |

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
| ROLE-01 lintas PT | Peran kustom turunan Manager perlu ikut akses lintas badan usaha seperti Manager bawaan? Sekarang hanya PT yang ditugaskan. | 2026-10-21 |
| FE-01 SO terbit | Batal item OD pada SO yang sudah dibayar/berfaktur: jalur nota kredit otomatis, atau tetap ditolak (koreksi manual Finance)? | 2026-10-21 |
| F-11-layar antrean | Perlu antrean "Retur menunggu terima/QC" (status approved/inspecting) di Meja Operator Gudang? (langkah opsional, belum dikerjakan) | 2026-10-21 |
| F-11-layar foto | QC/Gudang boleh mengunduh foto bukti keluhan retur? Sekarang hanya nama berkas (unduh tetap `sales_return.view`). | 2026-10-21 |
| F-09 baris dihapus | Harga khusus yang ditolak untuk produk yang kemudian dihapus dari pesanan tetap memblokir (tidak bisa diajukan ulang). Saat baris dihapus, entrinya ikut digantikan/dibatalkan? | 2026-10-21 |
| F-09 data lama | Jalankan `backend/scripts/repair_f09_superseded_rejections.py --apply` di produksi untuk SO yang terlanjur terkunci? (dry-run lokal: SO-00039, SO-00083) | 2026-10-21 |

## Riwayat perubahan tracker

| Tanggal | Oleh | Perubahan |
|---|---|---|
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
