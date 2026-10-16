# Workflow iterasi develop → validasi

## Satu sumber status

tracker.json adalah SSOT status temuan. coverage.json adalah SSOT status kasus pengujian saat ini. Kartu findings, tabel domain, fase dan laporan arsip bukan tracker status kedua. ID permanen; jangan renumber, menghapus bukti gagal, atau menghitung AX/alias sebagai bug unik.

Status: needs_revalidation → open → in_progress → ready_for_validation → verified_fixed. Validator boleh mengembalikan ready_for_validation/verified_fixed → reopened jika invariant gagal, branch berubah atau regresi muncul. Jalur tambahan: needs_policy_decision, blocked, deferred, not_reproducible, duplicate. Deferred/not_reproducible bukan sinonim fixed dan memerlukan alasan/bukti/reviewer; duplicate memerlukan duplicate_of. Field history append-only.

## Tanggung jawab

Agent develop: rebaseline, implementasi, regression test, catatan risiko/migrasi, commit implementasi, evidence dan ready_for_validation. Jika kode sudah diperbaiki orang lain, implementasi baru tidak diperlukan; sertakan commit kandidat dan bukti. Tidak menandai verified_fixed sendiri.

Validator pada sesi berikutnya: fetch commit candidate, baca diff seluruh caller dan periksa invariant; jalankan reproduksi/regression di lingkungan sesuai; verifikasi angka dan role/state yang diklaim. Isi validator, validation_commit, validation_evidence; verified_fixed hanya berlaku pada commit itu. Merge/rebase atau edit code terdampak sesudah validasi memerlukan keputusan apakah perlu revalidasi. Laporan gagal memuat expected/actual dan sisa dampak.

Pemilik proses: memutuskan gap bisnis, exception, prioritas, data repair/deploy dan readiness operasional. Review manusia terpisah diperlukan untuk kebijakan akuntansi/pajak maupun hardware acceptance yang belum dibuktikan.

## Handoff yang praktis

Satu branch/PR per kelompok perbaikan koheren. Sertakan ID di judul/deskripsi dan commit. Agent menambahkan iterations/<tanggal>-<fase>-<slug>/IMPLEMENTATION.md beserta hasil test yang aman dipublikasikan. Validator menambahkan VALIDATION.md. Bukti menunjuk SHA kode yang benar-benar diuji; commit dokumentasi sesudahnya boleh berbeda.

Jangan menyimpan credential, .env, database dump, identitas pelanggan/karyawan, atau token perangkat. Fixture menggunakan data sintetis. Reproduksi arsip tidak otomatis aman terhadap server nonlokal; baca README dan target DB sebelum menjalankan. Tidak ada deployment/pembayaran atau instruksi mengirim pesan eksternal dalam workflow ini.

Prompt validasi:
```text
Validasi fase/ID berikut pada commit kandidat yang dicatat tracker.json. Baca kartu, koreksi historis, implementation report dan diff. Reproduksi invariant dengan fixture aman; periksa caller lain, authorization, retry/reversal dan saldo lintas ledger. Bedakan coverage dari kelulusan. Jangan percaya status implementer tanpa bukti. Isi VALIDATION.md dan update tracker hanya untuk ID yang diverifikasi; failed menjadi reopened, belum dapat diuji tetap pending/blocked dengan alasan. Jangan menandai seluruh domain fixed dari test satu jalur.
```
