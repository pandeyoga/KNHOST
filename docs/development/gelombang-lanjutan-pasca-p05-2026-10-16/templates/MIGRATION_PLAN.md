# Migrasi dan pemulihan <fase>

Baseline dan kandidat SHA; environment; owner data; scope collection/table:

1. Perubahan schema/index/constraint dan invariant yang dilindungi.
2. Backup serta cara memulihkan pada environment uji.
3. Mapping record existing: valid, ambiguous, orphan, duplicate; jangan menebak provenance.
4. Dry-run, jumlah input/output/reject dan saldo pembanding per unit/owner/lokasi.
5. Idempotency/resume bila job berhenti di tengah; strategi rollback dan batas irreversible.
6. Verifikasi dokumen terpakai, grade historis, permission, roll/child, source links, nilai stok dan ledger.
7. Bukti hasil dan persetujuan owner sebelum eksekusi produksi. Perintah destructive/deploy mengikuti otorisasi yang berlaku, tidak otomatis diizinkan oleh plan ini.
