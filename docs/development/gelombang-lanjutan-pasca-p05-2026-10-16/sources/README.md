# Snapshot sumber dan batas penggunaannya

Semua file dalam folder ini adalah referensi historis yang dibekukan saat plan disusun. Status aktif gelombang baru ada pada BACKLOG.json di root paket. Jawaban terbaru mengalahkan dokumen sebelumnya pada topik sama; lihat BASELINE_DAN_PLAN_LAMA.

- REGISTER_PERNYATAAN_126_HISTORIS.json: seluruh statement awal, termasuk status pending yang sebagian sudah dijawab kemudian.
- REGISTER_JAWABAN_2026_10_16.json: keputusan dan usulan lanjutan non-retur.
- KEPUTUSAN_RETUR_SETELAH_JAWABAN_PEMILIK.json: 13 jawaban retur terbaru, prioritas pada topik retur.
- PERTANYAAN_CLIENT_TERKINI.json dan 09_Pertanyaan_Client_Retur_dan_Pendukung.md: 14 topik client yang masih aktif, belum dikirim.
- PLAN_LAMA_* dan old-phases/: snapshot plan P00–P10; dipakai memetakan carry-over, bukan mengaktifkan lagi rule yang diganti.
- P05_REPORT_SNAPSHOT.md: klaim implementasi dan open issue P05, belum final owner validation.
- 01/02/03/05/08_*: analisis, rekomendasi dan bukti source terdahulu. Bagian berlabel usulan tidak menjadi keputusan owner otomatis.
- VERIFIKASI_TERFOKUS.json: hanya pemeriksaan fungsi terisolasi yang pernah dilakukan; bukan integration test ERP atau hardware.
- middleware/: referensi kontrak dan UAT middleware; ketersediaan endpoint diasumsikan hanya dalam manual itu. Gap ERP berasal snapshot lebih lama dan harus direbase pada L12.
- rfid-plan/: rencana integrasi perangkat terdahulu. Tidak memerintahkan membangun APK pada lingkup ERP ini.

Beberapa link di snapshot historis menunjuk lokasi/paket terdahulu. Jangan menganggap link historis sebagai file evidence baru. Gunakan COVERAGE di root untuk penempatan requirement aktif dan dokumen lokal yang tersedia.
