# 01 — Panduan operasional KN Handheld C72 (0.1.0-lab)

Untuk operator gudang, supervisor, dan admin gudang. Istilah layar mengikuti ERP (Putaway Order, Final Loading Check,
Stock Opname, Daftar Awal, roll, EPC). **LAB:** perilaku perangkat belum terbukti di C72 — lihat dokumen 03.

## 1. Sekali per unit — admin ERP (provisioning)
1. ERP → perangkat handheld: buat perangkat (`POST /api/handheld/devices`, admin) — nama, **gudang induk**, cakupan:
   `site` (bawaan: semua gedung di site gudang itu, mis. seluruh Rancamalang) atau `warehouse` (gedung itu saja).
   Alternatif: menu RFID › perangkat yang sudah ada (tipe *handheld*) lalu terbitkan key.
2. Key tampil **sekali** bersama teks QR provisioning `{"kn":"c72","url":…,"key":…}` — tampilkan sebagai QR di layar,
   jangan dicetak/disimpan. Periksa `url` = alamat ERP yang dipakai C72.
3. Di C72: buka aplikasi → **Provisioning** → *Pindai QR provisioning* (atau ketik alamat & key) → *Uji & simpan*.
   Saat pertama, buat **PIN pemeliharaan** 6–12 angka (untuk diagnostik, setelan lokal, peninjauan antrean). PIN tidak
   dikirim ke ERP; jangan tulis di dokumen.
4. Unit hilang/rusak: ERP → *Cabut* (`/revoke`, admin/admin gudang, alasan) — key langsung tidak berlaku, sesi operator
   ditutup. Unit kembali: *Aktifkan* lalu *Rotasi key* dan provisioning ulang (antrean di HP tidak hilang).

## 2. Login & ganti operator
- Login dengan akun ERP biasa. Aplikasi mengikat **operator ↔ perangkat** (jejak siapa memakai unit mana kapan).
- Hanya tugas di **lokasi kerja operator** (penugasan site/gudang di ERP) **dan** gedung perangkat yang muncul.
- **Ganti operator:** Beranda › *Ganti operator / keluar*. Antrean yang belum terkirim **tetap tersimpan** dan hanya
  dikirim saat **pemiliknya** login lagi (bukti tidak pindah pemilik). Layar login menampilkan antrean milik siapa saja.

## 3. Alur kerja per dokumen (inti)
**Buka dokumen → baca massal → lihat Diharapkan / Terbaca / Kurang / Lebih → konfirmasi sekali.**
1. Beranda → pilih jenis tugas → pilih dokumen (✓ "tersimpan di HP" = bisa dikerjakan offline).
2. Arahkan C72 ke tumpukan roll, **tahan tombol pemicu** (atau tombol besar *MULAI PINDAI*), sapu pelan; lepas = berhenti.
   Mode *toggle* (tekan sekali mulai, sekali berhenti) bisa dipilih di Diagnostik.
3. Panel atas: **≡ Diharapkan · ✓ Terbaca · ○ Kurang · + Lebih**. Daftar per roll memakai tanda + teks:
   `✓ TERBACA`, `✓✓ SUDAH` (sudah diterima ERP), `⟳ ANTRE KIRIM`, `○ BELUM TERBACA`, `! KONFLIK`, `+ LEBIH` (EPC bukan
   dokumen ini — tag rak tetangga/roll lain; diabaikan, tidak dicatat sebagai salah kirim).
4. Roll kurang: tahan lama baris → **Cari tag** (angka 0–100 + bunyi makin rapat = makin dekat; bukan jarak).
5. Tekan tombol konfirmasi (sekali): *KONFIRMASI TIBA* (Putaway), *KONFIRMASI TERIMA* (Transfer), *KIRIM HASIL PINDAI*
   (cek muat, opname, verifikasi cetak). Boleh bertahap: roll yang belum terbaca tetap menunggu trip berikutnya.
6. Cek muat / opname / verifikasi cetak: setelah semua kiriman diterima ERP, tekan **SELESAIKAN DOKUMEN** — hasil final
   (bersih / bermasalah) ditentukan ERP. Hitungan di HP hanya perkiraan.

| Jenis | Catatan khusus |
|---|---|
| Masuk · Putaway | Roll tanpa tag (label QR) boleh dipindai labelnya (*Pindai label*). Sisa yang tak pernah terbaca diputuskan supervisor di ERP (kembali ke transit / pengecualian). |
| Keluar · SO / Sampel | Sesi cek muat dibuka dengan **MULAI SESI** (tidak pernah otomatis). Roll tanpa tag hanya lolos lewat pengecualian supervisor (izin `wms.untagged_override` + alasan). |
| Transfer masuk | Hanya roll transfer itu yang diterima; aturan gudang tujuan dievaluasi ulang ERP (ditolak → konflik per roll). |
| Potong sampel | Pindai roll induk (tag terkuat / label), isi panjang (+ alasan bila bukan saran FIFO), *POTONG* (butuh sambungan). Roll potongan lahir **tanpa tag** → aplikasi menawarkan *Tulis tag*. |
| Stock Opname RFID | Sapu seluruh gudang; *Lebih* = salah lokasi / EPC asing. Opname tidak mengubah stok otomatis. |
| Verifikasi cetak | Cocokkan EPC chip label tercetak dengan print job. Teks label yang benar ≠ chip benar. |

## 4. Tulis / ganti tag (EPC dibuat sistem)
1. Beranda › *Tulis / ganti tag* → pindai label roll, ketik nomor roll, *Baca tag lama*, atau pilih dari *Daftar roll
   belum bertag*.
2. *TULIS TAG BARU / GANTI TAG* → ERP membuat EPC (butuh sambungan saat langkah ini).
3. **Tempel tag di roll dulu**, dekatkan C72 (±5–10 cm), jauhkan tag lain → *Tulis sekarang*. Aplikasi menurunkan daya,
   memilih tag **RSSI terkuat** (menolak bila dua tag sinyalnya mirip), menulis, lalu **membaca ulang**.
4. Berhasil → konfirmasi masuk antrean (boleh offline). Tag lama tetap berlaku sampai ERP menerima konfirmasi.
   Gagal → *Ulangi* (EPC sama) atau *Batalkan niat tulis* (dicatat gagal; EPC tidak dipakai).

## 5. Daftar Awal (pendaftaran ulang stok lama)
Form lengkap sama dengan HP/desktop: **bin** (pindai label bin / pilih), **produk** (cari SKU/nama di katalog yang
tersimpan di HP, atau *Pindai label supplier*), **produk belum dikenali** + keterangan + **foto kain**, **panjang +
satuan**, *panjang dari label*, **lot, dye lot, grade, PT pemilik, nomor roll lama**.
- **Mode EPC sistem** (bawaan K-OPN-05): HP menyimpan **cadangan EPC** dari ERP (diisi ulang otomatis saat tersambung,
  ±50). Tempel tag → *TULIS TAG & SIMPAN* (atau pemicu) → tulis + baca ulang → baris masuk antrean sebagai "tag sudah
  ditulis". Bisa offline selama cadangan masih ada; layar memperingatkan bila hampir habis.
- **Mode EPC bawaan** (bila sesi diatur begitu): *BACA TAG* (tag terkuat) → *SIMPAN BARIS*.
- Bin, produk, satuan, PT, lot tetap terisi untuk roll berikutnya. *Rak bin ini selesai* menandai progres rak (online).
- Baris ditolak ERP (mis. EPC bentrok, produk nonaktif) tampil `!` dengan pesan; isi ulang roll itu.

## 6. Offline & antrean
- Garis status: `● Online` / `○ OFFLINE — hasil disimpan di HP`, `⟳ N antre`, `! N konflik/ditolak`, `⏸ tertahan`.
- Semua kiriman disimpan di HP **sebelum** dikirim, lalu dikirim otomatis (coba ulang bertahap 2 dtk → 5 mnt) dengan
  **ID yang sama** — kirim ulang tidak menggandakan efek di ERP.
- **Konflik** = ERP menolak karena keadaan berubah saat offline (dokumen sudah ditutup, roll sudah pindah/status
  berubah). Tidak diulang; tindak lanjut lewat supervisor/ERP. Item *tertahan* ditinjau di *Antrean sinkron* (PIN):
  kirim ulang dengan ID sama atau arsipkan (bukti tidak dihapus).
- Daftar yang diharapkan di HP adalah **salinan baca** (bukan stok). Muat ulang saat tersambung; layar memperingatkan
  bila sudah lebih tua dari profil (bawaan 12 jam).

## 7. Diagnostik (PIN)
Uji meja (init SDK, baca, tulis, barcode, daya, session, cari tag, baterai, kode tombol), ekspor JSON, mode simulasi,
penimpaan daya/session/mode pemicu lokal, ambil ulang profil ERP, provisioning ulang. **Mode simulasi**: tanpa radio;
bukti berlabel simulasi; ERP menolak simulasi untuk tiba/terima/daftar (mutasi stok).
