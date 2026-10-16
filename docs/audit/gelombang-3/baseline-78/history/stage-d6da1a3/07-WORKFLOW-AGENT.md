# Workflow perbaikan dan validasi

1. Import folder `docs/audit/data-flow-2026-10-05` ke repo. Pertahankan audit W1/W2 sebagai histori; jangan menimpa evidence lama.
2. Baca ringkasan, findings tracker dan dependency phases. Fase01durability dikerjakan dahulu agar source stock/finance tidak rusak sebelum projection dibenahi. Scope/commission dan partialreservation bernilaiP1, kerjakan secepat mungkin tanpa melewati uji failure/retry.
3. Agent mengisi `implementation_commit`, `implementation_evidence`, dan status `implemented_pending_validation`. Business-definition findings harus memiliki keputusan definisi eksplisit, bukan asumsi agent.
4. Jalankan fixture independen serta uji regression terkait. Catat unit, owner/legalentity, tanggalbusiness, statusdocument, denominator, price/costbasis, freshness, redaction/nullpolicy.
5. Reviewer menjalankan kembali counterexampleoriginal dan jalur terkait, memeriksa diff/source serta angkaAPI/consumer. Baru beri `verified_fixed` bila acceptance terpenuhi; gunakan `partial` jika hanya sebagianwindow tertutup.
6. Closure tidak boleh didasarkan pada kodekomentar, dokumenimplementation, parse/buildpass, endpoint200 atau test yang tidak mempunyai assertionangka. Sertakan hasilbefore/after.

Evidence dan skriprepro dilampirkan untukaudit, bukan untukdijalankan terhadapproduksi. Bootstraplokal membatasi socket ke loopback dan memakai databasebernamaaudit; janganmenghapusguard saatportingkeCI.
