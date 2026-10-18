# Workflow iterasi

1. Import hanya folder wave-2 pada docs/audit/. Bila folder sudah ada, bandingkan dahulu dan gabungkan tanpa menimpa tracker/evidence iterasi yang sudah berjalan. Baseline versi ini dapat dibandingkan lewat manifest SHA256.
2. Baca aturan repo; catat SHA kandidat dan perubahan lokal. Lakukan P00, cocokkan Wave1 dan baseline.
3. Pilih fase/ID, tandai in_progress, buat direktori iterasi unik. Gunakan templates/IMPLEMENTATION.md dan tools/prepare_iteration.py.
4. Reproduksi pada copy baseline dalam iterasi. Jika assertion lama gagal, investigasi perubahan bisnis/schema/fixture; bukan otomatis fixed. Adaptasi regression di area iterasi/test repo, baseline tetap utuh.
5. Implementasikan perbaikan, jalankan test relevan dan controls. Status final bisnis hanya setelah efek wajib lengkap. Sertakan UI, migrasi dan rekonsiliasi bila terdampak.
6. Isi implementation_commits dan implementation_evidence (path relatif folder wave-2), history, serta laporan iterasi. Agent implementasi berhenti pada ready_for_validation. Periksa paket dengan tools/check_package.py.
7. Auditor memakai commit kandidat yang persis sama, mengisi validation_commit/evidence, lalu verified_fixed, partially_fixed atau reopened. Jika belum dapat diuji, tetap terbuka dengan alasan.
8. Kirim Handoff beserta kandidat terintegrasi. Perubahan source berikutnya yang menyentuh flow terkait perlu impact review; hasil validasi SHA lama tidak otomatis berlaku untuk SHA baru.

Status finding: open → in_progress → ready_for_validation → verified_fixed / partially_fixed / reopened. blocked wajib alasan dan dependensi; tidak berarti selesai. Kebutuhan dapat deferred dengan alasan/persetujuan pemilik yang dicatat; jangan menghapus record. Status phase: not_started, in_progress, ready_for_validation, validated, blocked. Fase validated mensyaratkan semua ID wajib sudah divalidasi atau pengecualian tertulis yang tidak menyembunyikan risiko.

Status aktif hanya tracker root paket; tracker di baseline merupakan arsip. Laporan fase/kartu tidak menjadi status kedua. Jangan mengubah root AGENTS.md, status Wave1 atau kebijakan bisnis hanya untuk membuat test lulus. Jangan menjalankan migrasi/koreksi data nyata otomatis dari fixture audit.
