# Integrasi ERP dan pekerjaan tersisa (0.5.0-lab)

ERP Kain Nussantara · Production IT PT Kubus Teknologi Indonesia · status 9 November 2026

## Sisi ERP yang sudah ada (PREP-D1, kontrak 2.1.0)

Patch Kubus 0.5.0 sudah diterapkan ke backend KNHOST dan diperbaiki sesuai keputusan pemilik: alarm merah hanya
pelanggaran + satu kunci per gate (K-RFID-09), sesi dokumen bertahap (K-RFID-10), kelas sinyal EPC (kuat/lemah/latar),
lintasan kosong/mundur = CANCELLED, luapan = ACK karantina + REVIEW, auto-cocok dokumen, parameter lintasan berversi,
galat terstruktur `detail.code`, alert kesehatan reader. Rincian: `docs/rfid/hasil/PREP-D1-GATE-V2.md`.
Agent 0.5 memakai semua field 2.1 itu (ringkasan, tepi sinar, `open_reason`/`close_reason`, `seq`/`boot_id`,
`document_session`, kuning).

## Di luar agent (paket lain)

- **D2**: gate → transaksi (gate IN konfirmasi tiba putaway/transfer, gate OUT bukti kirim), antrean periksa dengan
  bukti per roll, koreksi klaim beraudit, penutupan sesi dokumen otomatis, izin pengakuan terpisah.
- Uji beban server 2.000 roll / 10.000 ringkasan (AUD-MW-07).
- Usulan kontrak dari paket E (penanda lintasan digabung, penilaian `t_peak` vs `beam_times`, posisi antena,
  kunci baku kesehatan) — [08 §9](08_PERUBAHAN_050.md#9-usulan-kontrak-untuk-koordinator-diselaraskan-dengan-d2--kontrak-tidak-diubah-di-paket-ini).

## Belum dinyatakan selesai

- Runtime Android/SQLite/service/boot belum dijalankan; APK dan APK instrumentasi hanya dikompilasi.
- Uji meja K-RFID-03, region, daya, sensor, relay, indikator, kalibrasi lintasan — wajib di U300 & lokasi.
- Satu logical gate per reader (IN/OUT terpisah = dua reader). Interlock pasangan gate berdampingan (K-RFID-04) belum.
- Retensi histori menunggu keputusan; tidak ada penghapusan otomatis.
- Signing produksi, URL staging, provisioning kredensial, dan acceptance operasional belum tersedia.
- Handheld C72 dan printer CP30EN tetap modul berbeda.

Tidak ada status "production ready" yang diberikan oleh hasil build, tes host, atau simulasi.
