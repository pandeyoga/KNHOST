# Rerun counterexample

Hasil historis tetap di evidence/repro; skrip kerja terpisah di folder ini. Pada repo yang sudah diperbaiki, gunakan Python dan dependency repo, MongoDB audit terpisah pada localhost:27919, serta --repo untuk checkout yang benar. Runner merekam actual-run-context.json; SHA tertanam pada script adalah baseline historis, bukan SHA patch. Contoh dari root repo:

```text
python docs/audit/gelombang-3/repro/run_local.py --repo . --script hr_kpi_projection90.py
```

Wave2_env memakai database UUID baru serta synthetic entity A/B. Service_env90 juga memakai database UUID baru, tetapi beberapa probe require template knhost_audit_native90_template berisi master demo asli. Untuk template, reviewer perlu menyiapkan seed_realistic.seed_all pada database audit baru dengan dependency repo dan konfigurasi demo yang diizinkan; jangan menyalin produksi atau menghapus guard database kosong. Tidak semua script adalah satu perintah mandiri; jika fixture/dependency belum tersedia, catat environment prerequisite unresolved, bukan klaim test pass atau bug produk.

Hasil baru ditulis di folder repro ini. Setelah selesai, salin hasil ke evidence implementasi terpisah dengan actual SHA. Jangan menimpa evidence baseline. Native batch scripts di evidence/continuation-90 menyimpan adapters lingkungan Windows/path/loop dan hasil assertion asli; beberapa path task-local perlu disesuaikan secara eksplisit sebelum rerun. Socket outbound dibatasi loopback. Tidak ada provider AI, email, WhatsApp, printer atau gate fisik yang divalidasi oleh runner ini.
