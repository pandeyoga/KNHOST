# Keputusan yang dipakai blueprint

Daftar pertanyaan asalnya ada di `docs/finance/rencana-2026-11-13/10_KEPUTUSAN_PEMILIK.md` (K-01 … K-46). Dokumen ini
mencatat **jawaban yang dipakai agen pelaksana**. Unit merujuk nomor di sini.

## Jawaban pemilik, 13 Nov 2026

> "Secara garis besar saya setuju, namun untuk beberapa hal seperti aturan buka butuh dua orang itu bisa dikonfigurasi
> dengan default 1 orang karena belum tentu finance ada dua orang."

Cara jawaban itu diterjemahkan (tafsir perancang, ditandai supaya pemilik bisa mengoreksi):

1. Setiap usulan di kolom "Usulan" daftar K-01 … K-46 **dipakai**.
2. Setiap aturan "harus dua orang" atau "pembuat ≠ penyetuju" menjadi **pengaturan per PT** (`02_STANDAR.md` §2.3):
   - **Buka periode** (disebut pemilik) dan semua aturan dua-orang yang **baru diusulkan** rencana (K-04, K-11, K-17,
     K-25, K-28, K-41, K-44): bawaan **satu orang**.
   - Aturan dua-orang yang **sudah berjalan hari ini** di tempat lain (persetujuan PO, tagihan pemasok, kontrabon,
     voucher biaya masuk, dan lain-lain — 12 titik ditulis mati + 2 sakelar; daftar di
     `docs/audit/konfigurasi-peran-2026-11-13/lampiran/C_konfigurasi_perusahaan.md` Lampiran C): dijadikan **bisa
     diatur**, dengan nilai awal **sama seperti hari ini**, supaya tidak ada kontrol yang melonggar diam-diam saat
     pemasangan. Layar pengaturnya menyediakan satu tombol "Tim kecil — semua cukup satu orang" untuk mengubah
     semuanya sekaligus.
   Bila pemilik menghendaki **semua** langsung berbawaan satu orang, cukup ubah nilai awal di unit KF-T6; tidak ada
   pekerjaan lain yang berubah.
3. Setiap aturan baru yang membatasi pengguna dibuat sebagai pengaturan, supaya persetujuan "garis besar" tidak
   mengunci sesuatu yang ternyata tidak cocok di lapangan. Nilai bawaan mengikuti kolom "Bawaan" di bawah.
4. Pertanyaan yang jawabannya **fakta perusahaan** (rekening, komponen gaji, PT mana yang PKP) tidak menahan
   pembangunan: sistemnya dibangun, datanya diisi pemilik lewat layar (§C).

## A. Fondasi

| No | Dipakai | Bawaan saat dipasang | Diubah lewat |
|---|---|---|---|
| K-01 | Tetap MongoDB → replica set satu anggota → perkeras buku besar | — | Titik henti H2 sebelum dijalankan |
| K-02 | Akun kontrol (piutang, hutang, persediaan, antar-PT) menolak jurnal manual | Menolak | `gl.jurnal_manual_akun_kontrol` (tolak · izinkan) |
| K-03 | Periode tertutup mengunci dokumen, pembayaran, mutasi stok bertanggal di periode itu | Mengunci | `periode.kunci_dokumen` |
| K-04 | Buka periode, buka kembali tutup buku, jurnal manual: **bisa diatur, bawaan satu orang** | 1 orang | `kontrol.buka_periode.min_orang`, `kontrol.jurnal_manual.min_orang` |
| K-05 | Landed cost untuk barang yang sudah terjual → HPP periode berjalan | HPP | `inventory.landed_cost_porsi_terjual` (hpp · varians) |
| K-06 | True-up persediaan hanya untuk saldo awal | Hanya saldo awal | `inventory.trueup_hanya_saldo_awal` |
| K-07 | Antar-PT, roll lebih panjang dari pesanan: dokumen menyesuaikan panjang aktual | Menyesuaikan | `antar_entitas.selisih_panjang` (sesuaikan · tolak) |
| K-08 | Status PKP per PT = master badan usaha (sudah ada). Ekspor Coretax dan PPh 23: **di luar blueprint** sampai diminta | — | Unit TX-T3 `tahan` |
| K-09 | Finance: Rekonsiliasi Bank ya; Buku Besar lihat saja; Hutang mengikuti K-17 | Lihat tabel izin di unit MN-T1 | Peran & Hak Akses |
| K-10 | Konsolidasi memakai persen kepemilikan per PT | 100 % | Master badan usaha |
| K-11 | Satu batas nominal untuk semua pengurang piutang tanpa kas; pembuat ≠ penyetuju **bisa diatur** | Batas = nilai hapus-sisa yang berlaku hari ini; 1 orang | `kontrol.pengurang_piutang.batas_nominal`, `.min_orang` |
| K-12 | Anggaran memperingatkan; mencakup PO, faktur non-PO, kas, LPJ | Memperingatkan | `budget.mode` (peringatan · blokir) |
| K-13 | Jurnal periodik (penyusutan, gaji, insentif, LPJ) bertanggal akhir periodenya | Akhir periode | `gl.tanggal_jurnal_periodik` (akhir_periode · hari_posting) |
| K-14 | Kenaikan harga ditagih sebagai baris tagihan baru; ganti termin ke yang lebih longgar butuh izin setara pelepasan | Seperti usulan | Izin `order.release_unpaid` |
| K-15 | Mode "Semua PT": penjumlahan berlabel "belum dieliminasi"; beralih ke konsolidasi setelah PK-31 | Berlabel | — |
| K-16 | Jatuh tempo: per surat jalan; per baris rencana untuk cicilan; DP sebelum kirim | Seperti usulan | — |
| K-17 | Membayar hutang dan mencairkan uang muka = pemegang izin bayar (bawaan: Finance dan Manajer); orang kedua bisa diatur | 1 orang | `kontrol.bayar_hutang.min_orang`, `kontrol.cairkan_uang_muka.min_orang` |
| K-18 | Peran tanpa izin keuangan tidak melihat nominal di Jejak Dokumen | Disembunyikan | Izin modul sumber |

## B. Modul

| No | Dipakai | Bawaan saat dipasang | Diubah lewat |
|---|---|---|---|
| K-19 | Omzet insentif = barang terkirim, tanpa PPN, dikurangi retur | Terkirim | `insentif.dasar_omzet` (pesanan · terkirim · lunas) per PT |
| K-20 | Pencairan = uang yang benar-benar masuk dan sudah dialokasikan; giro saat cair | Seperti usulan | `insentif.isi_pencairan` |
| K-21 | Pemilik angka = sales pada pesanan (dengan pembagian tim) | Sales pada pesanan | `insentif.pemilik_angka` |
| K-22 | Komisi otomatis dimatikan per PT saat PT itu memakai lembar insentif; beban diakui saat lembar disahkan | Komisi otomatis **tetap hidup** sampai PT dialihkan (H5) | `hr.payroll_commission_mode` |
| K-23 | Harga acuan = harga daftar PT pada tanggal pesanan | Seperti usulan | `insentif.harga_acuan` |
| K-24 | Triwulan mengikuti tahun buku; target triwulan dan tahun angka tersendiri | Seperti usulan | — |
| K-25 | Penyiap dan pemutus lembar insentif: **bisa diatur** | 1 orang | `kontrol.lembar_insentif.min_orang` |
| K-26 | Sales multi-PT: lembar per PT; dibayar gaji PT induk; selisih lewat dokumen antar-PT | Lembar per PT; penagihan antar-PT dibangun di KM-T4 | — |
| K-27 | Hari telat yang menahan pesanan diatur per PT, bisa ditimpa per pelanggan; pesanan tunai pelanggan tertahan boleh, barang ditahan sampai lunas | 14 hari (nilai hari ini) | `ar.overdue_block_days`, profil kredit |
| K-28 | Plafon dan status blokir hanya berubah lewat pemegang izin kredit; orang kedua bisa diatur | 1 orang; Sales tidak memegang izinnya | `kontrol.ubah_profil_kredit.min_orang` |
| K-29 | Plafon per PT; kelompok kredit lintas PT opsional | Per PT | Profil kredit |
| K-30 | Denda: mode per PT; dasar = sisa baris tagihan yang telat | Usulan (nota draf) — sama dengan hari ini | `payment.penalty_mode` |
| K-31 | Eksposur memuat pesanan belum dikirim dan giro belum cair; titipan mengurangi | Seperti usulan | `ar.eksposur_*` |
| K-32 | Saat faktur pajak terbit **dijadikan pengaturan**; isinya perlu konfirmasi konsultan pajak | Per pesanan, manual (perilaku hari ini) | `tax.pemicu_faktur` (pesanan · surat_jalan · uang_muka) |
| K-33 | Data pajak pelanggan (NPWP/NIK, alamat pajak, kode transaksi) dan barang disediakan sebagai isian; pesanan non-PPN butuh izin khusus | Isian opsional sampai diisi | Master pelanggan/barang |
| K-34 | Rekening penerimaan per PT = data master (§C) | — | Master rekening |
| K-35 | Tahap 1 tanpa penyedia pembayaran; VA/QRIS di luar blueprint | — | Unit PM-T5 `tahan` |
| K-36 | Sales tetap boleh mencatat kwitansi dari HP seperti hari ini (izin itu diberikan saat server dinyalakan — temuan PR-14); alur titipan dan setoran tunai dibangun di PM-T4 supaya tunai di tangan sales tidak tercatat sebagai kas | Seperti hari ini | Peran & Hak Akses; `pembayaran.sales_terima_tunai` setelah PM-T4 |
| K-37 | Komponen gaji per PT = data (§C); THR proses terpisah; insentif ikut proses bulanan periode bayarnya | — | Layar Komponen & Masukan |
| K-38 | Prorata dan potongan = pengaturan per PT | **Mati** (perilaku hari ini: gaji penuh) | `hr.prorata_*`, `hr.potongan_*` |
| K-39 | Lembur wajib pengajuan | Wajib pengajuan | `hr.overtime.sumber` (pengajuan · absensi) |
| K-40 | Kasbon dipotong gaji lewat antrean masukan | — | — |
| K-41 | Menyiapkan, mengesahkan, membayar gaji = tiga izin terpisah; orang kedua bisa diatur | 1 orang | `kontrol.proses_gaji.min_orang` |
| K-42 | Tabel tarif PPh 21 **tidak diisi agen** | — | Titik henti H4 (PK-46 `tahan`) |
| K-43 | Lapisan penyedia yang bisa berganti; nama pihak disamarkan | Disamarkan | `ai.samarkan_nama` per PT |
| K-44 | Tindakan lewat asisten mengikuti tahap di rancangan; orang kedua untuk uang keluar dan jurnal **bisa diatur** | 1 orang (yang menyetujui kartu) | `kontrol.asisten_uang_keluar.min_orang`, `.batas_nominal` |
| K-45 | Asisten keuangan mati per akun sampai dinyalakan pemilik | Mati | Akun & Akses |
| K-46 | Susunan menu baru dipakai | — | — |

## C. Data yang diisi pemilik (tidak menahan pembangunan)

| Data | Di layar mana (setelah unitnya selesai) | Dipakai oleh |
|---|---|---|
| Rekening penerimaan tiap PT, atas nama, peruntukan, bawaan per cara bayar | Keuangan › Kas & Bank › Rekening & Saldo | PM-T1, PM-T2 |
| Cara bayar yang sah per PT | Pengaturan › Keuangan | PM-T1 |
| Termin yang diizinkan dan plafon per pelanggan | Kartu pelanggan › Kredit | CR-T1 |
| Target omzet dan pencairan per sales | Kinerja & Insentif › Target & Aturan | KM-T1 |
| Komponen gaji per PT; aturan prorata dan potongan | Penggajian › Komponen & Masukan; Pengaturan › SDM | PY-T1, PY-T3 |
| Persen kepemilikan tiap PT | Pengaturan › Perusahaan | PK-31 |
| Data pajak pelanggan | Kartu pelanggan | TX-T1 |
| Tabel tarif PPh 21 terverifikasi | Diserahkan ke pelaksana sebagai berkas | PK-46 |

## D. Keputusan tambahan dari audit konfigurasi dan peran (K-47 …)

Tidak ada yang menahan; semuanya mengikuti permintaan pemilik agar pengaturan dan peran kustom "benar-benar bekerja".

| No | Hal | Dipakai | Mengapa aman |
|---|---|---|---|
| K-47 | Wewenang ditentukan izin, bukan nama peran acuan | Ya (`02_STANDAR.md` §3) | Saat dipasang, peran bawaan dan peran kustom yang ada diberi izin baru yang setara dengan akses yang selama ini mereka dapat lewat nama peran — tidak ada yang kehilangan akses; bedanya kini terlihat dan bisa dicabut di layar peran |
| K-48 | Izin "kelola pengaturan" benar-benar berfungsi | Ya | Bawaan hanya Admin yang memegangnya — sama dengan hari ini |
| K-49 | Membaca Pusat Pengaturan butuh izin lihat pengaturan | Ya | Menu Pengaturan memang hanya tampil untuk Admin dan Manajer; yang ditutup hanya akses langsung ke API oleh peran lain. Nilai yang dibutuhkan semua layar tetap tersedia lewat daftar putih |
| K-50 | Tidak bisa memberi atau mengubah akun/peran yang izinnya melebihi milik sendiri | Ya | Bawaan hanya Admin yang mengelola akun dan peran — tidak ada perubahan bagi Admin |
| K-51 | Persetujuan mengikuti izin setujui + batas nominal per peran | Ya | Saat dipasang, batas tiap peran diisi setara peringkatnya hari ini |
