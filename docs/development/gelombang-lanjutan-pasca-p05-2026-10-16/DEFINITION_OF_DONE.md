# Titik selesai yang dapat diverifikasi

## Per requirement

- Perilaku sesuai keputusan owner yang berlaku, termasuk otorisasi dan scope data.
- UI, API, data dan dokumen terkait konsisten; bukti dipilih sesuai dampak requirement.
- Semua acceptance required pass pada commit kandidat yang dapat ditelusuri; fail/blocked/not_run bukan pass.
- Pending decision yang memengaruhi requirement sudah dijawab dengan sumber persetujuan. Kode independen boleh selesai lebih dahulu tetapi requirement penuh belum validated.
- Tidak ada duplikasi SSOT, reservation/stock/financial posting atau side effect akibat retry/concurrency; recovery teruji pada batas yang berisiko.
- Perubahan schema memiliki migrasi/backfill yang tidak menebak fakta; data yang perlu rekonsiliasi ditandai.
- Implementer menyerahkan evidence; reviewer terpisah memeriksa dan owner memberi approval ref. Status baru kemudian validated.

## Per fase

Seluruh requirement fase validated dan dependency fase validated, phase report lengkap, implementasi+commit verifikasi tercatat, issue terbuka mempunyai keputusan penyelesaian yang disetujui dan tidak menghalangi skenario required. Fase bisa memiliki pekerjaan implementasi selesai sambil menunggu keputusan/hardware, namun belum tervalidasi penuh.

## Seluruh gelombang

1. Semua requirement dan acceptance dalam lingkup asli tuntas; seluruh fase validated.
2. Kandidat final punya full SHA, verifikasi chain lintas modul, rekonsiliasi stok per unit/owner/lokasi dan Finance, migrasi serta recovery.
3. Semua keputusan blocker resolved. Pilihan device absensi dan kebijakan HR yang dibutuhkan sudah dibuktikan; RFID/printing diuji unit nyata, bukan sekadar kontrak/simulator.
4. Owner menyetujui kandidat final dan bukti UAT; reviewer berbeda dari implementer tercatat.
5. `validate_package.py --closure` lulus. Kelulusan skrip memeriksa kelengkapan metadata, tetap memerlukan pemeriksaan substansi evidence oleh reviewer.

Jika masih ada satu cabang pending, hasil yang benar adalah laporan kemajuan dengan daftar blocker. Penutupan lingkup lebih sempit memerlukan keputusan owner tertulis dan label lingkup revisi. Tidak ada kebijakan “skip dianggap pass”.

## Batas klaim

Paket planning siap dipakai tidak berarti implementasi aplikasi lulus. Skenario pure function dari analisis terdahulu hanya bukti terbatas. Persentase statement yang dipetakan bukan persentase code coverage atau jaminan bebas bug. Penutupan plan pasca-P05 juga bukan penutupan otomatis audit wave 1–3.

## Tambahan implementasi revisi 1.2 — produksi supplier dan makloon

Wajib baca [rancangan implementasi produksi](IMPLEMENTASI_PRODUKSI_SUPPLIER_MAKLOON.md). LN-033 ditambahkan pada L03 dan LN-143 pada L14, dengan 18 skenario acceptance baru. Total paket: 54 requirement, 214 acceptance, 15 fase; 24 topik pending lama tetap dipertahankan.

Urutan dependency berubah: fondasi L04 harus tervalidasi sebelum L03 ditutup. Pekerjaan desain/round L03 dapat dipersiapkan sebelumnya. Rilis master bukan order produksi; kedua sumber pemenuhan wajib memiliki hubungan dokumen yang benar sampai penerimaan dan pengiriman. Penambahan ini disetujui owner dalam chat 16 Oktober 2026. Semua status lama dipertahankan; requirement baru belum diimplementasikan.

## Revisi 1.3 — hak akses rinci dan pengujian ulang R&D

Wajib baca [rancangan custom role dan revalidasi R&D](CUSTOM_ROLE_DAN_REVALIDASI_RND_REV1_3.md). Tambahan LN-015 (L01) dan LN-034 (L03), 16 acceptance baru; total 56 requirement dan 230 acceptance. Keputusan owner: hasil uji ulang gagal menunggu keputusan PIC; tidak otomatis menghentikan produksi atau membatalkan stok lama. L14 wajib membuktikan integrasi kedua tambahan ini. Hak akses mencakup aktivitas, scope dan field, bukan hanya menu terlihat. Versi ini menggantikan paket 1.2 untuk import baru; status lama dan 24 topik pending tetap dipertahankan.
