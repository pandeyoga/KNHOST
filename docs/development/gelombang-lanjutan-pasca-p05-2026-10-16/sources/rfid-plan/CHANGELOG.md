# Perubahan Addendum v2 — Printer CP30EN

## Scope baru

Pengguna menambahkan printer dan memilih model CP30EN. Scope perangkat sekarang UR300, C72 dan CP30EN. Profil varian/firmware/koneksi/media printer masih diverifikasi melalui PoC.

- ID RFID-01–RFID-10 dipertahankan. RFID-10/RF04/RACC-20 diperluas agar UAT meliputi printer.
- Tambah RFID-11–RFID-15, tahap RF-P, prompt printer, PRINTER_CP30EN_PLAN.md dan RACC-21–RACC-30.
- RF00 mencakup profil serta PoC printer; RF01 menambahkan contract review lease/result/recovery. RF04 sekarang bergantung RF-P.
- Total addendum: 15 kebutuhan, 6 tahap, 30 acceptance. Plan utama tetap 35 IMP dan P00–P10.

## Import jika v1 sudah dikerjakan

Gunakan satu addendum aktif, jangan mempertahankan dua tracker yang berbeda untuk ID hardware yang sama. Merge status/commit/evidence RFID-01–RFID-10 serta acceptance lama dari tracker v1 ke v2; jangan overwrite dengan not_started.

Tambahkan ID baru beserta dependensi. UAT RFID-10/RF04/RACC-20 memerlukan verifikasi ulang scope printer yang baru; evidence lama tetap disimpan, sedangkan status baru hanya ditutup setelah bukti tambahan lulus. Bagian metadata/lease/recovery di RF00/RF01 ditinjau sesuai perubahan, bukan dianggap complete otomatis dari hasil lama.

BACKLOG.json plan 35 IMP tidak diganti. P10 memakai tracker hardware v2 dan gate RF04 yang telah diperluas. Paket v1 di workspace disimpan sebagai arsip, sedangkan v2 ini dipakai untuk pekerjaan selanjutnya.
