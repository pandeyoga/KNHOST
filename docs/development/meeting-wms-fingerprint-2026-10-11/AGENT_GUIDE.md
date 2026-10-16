# Panduan Agent Development

## Cara mulai

1. Baca `README.md`, `DEVELOPMENT_PLAN.md`, `BACKLOG.json`, `DECISIONS.md`, dan daftar kebutuhan pada `sources/`.
2. Baca instruksi repo dan kondisi kerja aktual. Catat branch/commit serta perubahan pengguna; jangan menimpa pekerjaan lain.
3. Kerjakan P00 dahulu. Pilih prompt fase berikutnya sesuai dependensi, bukan hanya nomor urut. P09-A boleh dimulai setelah P00.
4. Gunakan ID IMP dan DEV-F/DEV-G lama agar perbaikan dapat dilacak. Verifikasi apakah gap masih berlaku sebelum mengubah kode.
5. Implementasikan seluruh consumer relevan pada scope fase; jalankan tes yang tepat, dokumentasikan migrasi, dan serahkan evidence.
6. Perbarui `BACKLOG.json`; render `TRACKER.md` melalui skrip yang disertakan. Jangan menulis status langsung pada Markdown lalu membiarkan JSON berbeda.

## Data acuan

Data VPS = data seed repo. Gunakan urutan skrip `deploy/setup_demo_lengkap.sh` (termasuk `seed_simulasi_bin_kn.py`, bin MOCK) sebagai data acuan semua fase; dry-run dijalankan di preview. Data tambahan untuk fase baru ditambahkan sebagai skrip seed idempoten ke `setup_demo_lengkap.sh`, bukan diubah manual. Detail: `evidence/P00/report.md` bagian "Data acuan development".

## Aturan implementasi

- Pertahankan sumber kebenaran existing yang sah; gunakan kontrak bersama untuk UI/API/proyeksi/dokumen. Jangan membuat layanan/counter/enum paralel tanpa alasan dan migrasi.
- Perubahan harus mencakup server, UI, permissions, schema/migration, error/empty/loading states, histori, ekspor atau dokumen turunannya jika terdampak.
- Kualitas, unit, owner, lokasi, reservasi, physical receipt, dan status shipment tidak boleh digabung menjadi satu status/angka.
- Gunakan operasi atomik/idempotensi sesuai platform aktual dan uji race/retry/partial failure. Jangan memakai update langsung untuk melepas reservasi atau menutupi selisih.
- Keputusan yang belum final tidak boleh ditebak. Buat konfigurasi dan jalur review; pertahankan perilaku legacy yang sah sampai aktivasi perubahan disetujui.
- Tulis tes yang memeriksa perilaku dan invariant, bukan tes yang sekadar menyalin implementasi. Pilih meaningful tests untuk perubahan stok, status, uang, akses, dan ingestion.
- Jangan mengubah konfigurasi tes, menambah bypass, atau menghapus guardrail agar acceptance terlihat lulus. Pisahkan baseline failures dari regression.
- UI tetap menggunakan bahasa bisnis. Detail teknis receiver/database tidak perlu ditampilkan dalam pekerjaan harian pengguna.
- Template fingerprint tidak diperlukan di ERP untuk kebutuhan absensi. Jangan menambah penyimpanan biometrik atau fungsi kontrol pintu di luar scope.

## Status dan evidence

Status requirement/phase: `not_started`, `in_progress`, `waiting_decision`, `waiting_hardware`, `implemented_pending_validation`, `validated`, atau `reopened`.

`validated` memerlukan `verified_commit` dan evidence yang dapat diperiksa. Keputusan menggunakan `open`, `proposed`, `confirmed`, atau `not_applicable`; confirmed mencatat sumber persetujuan, not_applicable mempunyai alasan yang dapat direview. Jangan mengisi persetujuan klien berdasarkan dugaan.

Simpan laporan di `evidence/Pxx/report.md` dengan template. Bukti kode/tes dapat ditulis sebagai path relatif repo dan commit; screenshot/log hasil disimpan sebagai artifact atau link yang dapat diakses. Redaksi secret/config token dari evidence.

`BACKLOG.json` memuat fase, kebutuhan, keputusan, dan acceptance results. Agent boleh mengubah status sampai `implemented_pending_validation` setelah pekerjaan dan pengujian developer selesai. Validator menutup `validated` setelah review bukti pada commit yang sama. Hasil pass pada tes tidak otomatis berarti keputusan bisnis sudah dikonfirmasi.

Jika ada blocker, catat item spesifik dan lanjutkan pekerjaan independen; jangan menandai semua fase blocked. Temuan baru dicatat dengan kebutuhan terkait, dampak, bukti, dan usulan scope, tanpa menghilangkan temuan lama.

## Format laporan akhir setiap fase

Laporkan: kebutuhan yang selesai diimplementasikan, commit, perubahan perilaku, file/kontrak terdampak, migrasi, tes dan hasil, screenshot/input-output, issue terbuka, keputusan yang diperlukan, serta fase yang kini siap dimulai. Jangan menggunakan istilah complete jika hardware/UAT atau consumer relevan belum diuji.

Plan bukan instruksi membeli hardware, menghubungi pihak luar, push ke repo, atau deployment produksi otomatis. Ikuti otorisasi langsung pengguna serta aturan repo yang berlaku saat implementasi.
