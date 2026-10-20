# Menjalankan ulang reproduksi

File Python di folder ini adalah salinan harness audit, bukan patch aplikasi. Path di dalamnya mengikuti workspace audit asal. Untuk menjalankan ulang, tempatkan harness pada folder `work/` sejajar folder snapshot `work/KNHOST-plan-audit-2026-10-19/`, dengan output pada `output/audit-plan-2026-10-19/evidence/`.

Snapshot harus menggunakan commit `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`, termasuk folder root `scripts/`. Gunakan lingkungan Python yang memiliki dependensi backend. MongoDB lokal memakai port 27138; backend pengujian port 8019. Detail koneksi dan nama database ada di masing-masing harness.

Harness fault, migration dan consistency membuat database audit berawalan `kn_*` dengan suffix unik. Harness HTTP dan volume membutuhkan database contoh `kn_plan_audit_20261019` serta akun demo lokal; volume test menambahkan lalu membersihkan movement sintetis. Gunakan lingkungan audit terisolasi, bukan data operasional.

Mengubah path/port untuk lingkungan lain diperbolehkan, tetapi catat perubahan lingkungan tersebut dan jangan mengganti expected behavior agar hasil menjadi lulus. Bukti JSON/XML dalam paket adalah hasil eksekusi asli sebelum ada perbaikan kode aplikasi.
