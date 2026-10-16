# Gelombang 2, W2-03 — ownership dan keputusan stock opname

Snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. [Bukti runtime](count-results.json) · [Harness](repro/wave2_count.py) · [Prompt perbaikan](07_PROMPT_CYCLE_COUNT.md).

Sepuluh skenario baru melalui ASGI API dan Mongo lokal: delapan kontrol sesuai ekspektasi, dua cacat terkonfirmasi. Kumulatif Gelombang 2: **30 skenario unik, 22 kontrol, delapan reproduksi cacat untuk tujuh temuan**. Run ulang tidak dihitung ulang. Tidak mengubah source aplikasi atau status Gelombang 1.

## W2-006 — resolver owner otomatis dapat memilih stok entitas di luar akses pengguna

**P1 · Runtime HTTP terkonfirmasi · W2-C-F02.**

### Letak dan kontrak yang terputus

- [cycle_count.py:106](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/cycle_count.py#L106): entitas aktif/payload dijadikan `prefer`, lalu diteruskan ke resolve_stock_owner.
- [roll_service.py:1307](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L1307): resolver mencari semua roll available produk/gudang tanpa batas allowed owners. Jika prefer tidak mempunyai available stock, memilih owner dengan stok terbesar.
- [cycle_count.py:108](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/cycle_count.py#L108): expected dibaca dari owner hasil resolver tanpa pemeriksaan hak atas owner itu.
- [cycle_count.py:230](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/cycle_count.py#L230): approval memakai owner pada discrepancy untuk mengubah roll.

Session memiliki entity_id A dan akses session diperiksa, tetapi item di dalamnya dapat menunjuk owner B. Izin menggunakan gudang shared bukan izin mengubah seluruh pemilik stok yang berada di gudang tersebut. Resolver stok diperlakukan sebagai resolver otorisasi, padahal ia hanya memilih segmen stok.

### Reproduksi

1. User U hanya allowed_entity_ids=[A], aktif di A, memiliki inventory.cycle_count dan inventory.approve_count.
2. Gudang SHARED memang boleh dipakai bersama. Produk fixture memiliki stok10 milik B; tidak ada available stock A.
3. Buat sesi A melalui API, tambahkan produk **tanpa owner_entity_id**.
4. Respons item200 mengandung owner_entity_id B dan expected_qty10.
5. PATCH actual_qty8, submit, lalu approve: seluruhnya berhasil; stok B berubah10→8.

**Kontrol yang penting:** payload yang secara eksplisit mengirim owner_entity_id B ditolak403; membaca session B ditolak404. Jika produk punya stok A20 dan B100, resolver memilih A dan penyesuaian A20→18 tidak mengubah B100. Jadi ini bukan bypass universal terhadap scope: cacatnya ada pada owner yang ditentukan otomatis setelah pemeriksaan input.

Percobaan awal yang memperkirakan explicit B akan lolos dibantah oleh runtime dan diubah menjadi kontrol W2-C-C08. Tidak ada temuan bahwa explicit B berhasil. ID skenario F01 tidak dipakai dalam hasil final; bukan kasus tambahan yang hilang dari total.

### UI dan dampak flow

Form menggunakan state product_id/bin_id/notes tanpa owner pada [CycleCount.jsx:33](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/inventory/CycleCount.jsx#L33), lalu mengirim state tersebut di [CycleCount.jsx:93](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/inventory/CycleCount.jsx#L93). Dengan demikian payload tanpa owner sesuai pola source UI, bukan hanya parameter tersembunyi. Belum browser UAT.

Hasil count mengekspos expected stock B dan approval mengubah stok B lewat dokumen milik A. Jejak sesi dan kepemilikan stok menjadi tidak konsisten. Hubungannya ke Finance harus ditangani bersama FN-14 Gelombang1, tetapi cacat jurnal opname tersebut tidak dihitung ulang sebagai W2 baru.

### Perbaikan dan acceptance

Tetapkan owner count dari scope yang berwenang. Jika memilih owner otomatis, kandidat hanya boleh berasal dari owner yang sah untuk sesi dan pengguna; tidak adanya stok A tidak boleh memindahkan target ke B. Lakukan validasi hasil resolver di service boundary, serta ulangi pemeriksaan seluruh item pada submit/approve untuk menangani sesi lama. Tentukan kontrak count lintas-entitas eksplisit bila memang dibutuhkan; jangan menyamakan shared warehouse dengan akses lintas-entitas.

Uji user A saja, A+B, entitas aktif A dengan owner kosong, explicit B, stock A nol/reserved-only, stock A dan B tersedia, surplus dengan stok awal nol, dan sesi lama yang sudah berisi item owner asing. Penolakan harus terjadi sebelum membaca expected owner asing atau mengubah roll. Kontrol gudang shared yang sah dan transaksi owner A tetap lulus.

## W2-007 — penolakan terlambat menimpa approval setelah adjustment sudah diterapkan

**P1 · Runtime HTTP dengan barrier penjadwalan · W2-C-F03.**

### Letak kode

- [cycle_count.py:197](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/cycle_count.py#L197): approve mengambil saga claim untuk submitted, memeriksa drift, menerapkan adjustment, dan menulis approved.
- [cycle_count.py:253](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/cycle_count.py#L253): reject memeriksa status dari snapshot yang sudah dibaca.
- [cycle_count.py:259](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/cycle_count.py#L259): update reject hanya memfilter id, tidak submitted/version dan tidak menghormati saga lock approval.

### Reproduksi interleaving

Sesi memiliki expected100, actual90, discrepancy−10. Request reject membaca session submitted lalu dijeda. Request approve berjalan lengkap: HTTP200, stok turun100→90, session approved. Request reject dilanjutkan memakai snapshot submitted: HTTP200, status akhir rejected, stok tetap90. Dokumen akhir memuat approved_at **dan** rejected_at.

Barrier hanya membungkus `_load_session`, memanggil fungsi aslinya termasuk pemeriksaan akses, lalu menunda pengembalian snapshot untuk request reject. Tidak mengganti status, query, hasil stock adjustment atau respons aplikasi. Ini bukti satu interleaving konkret, bukan klaim sudah menjalankan seluruh kombinasi concurrency.

Kontrol serial: reject dahulu lalu approve ditolak400 dan stok tetap100. Approval normal100→90 berhasil; retry approval ditolak400 dan stok tetap90. Jadi masalahnya bukan dua approval serial, melainkan dua keputusan terminal dengan protokol concurrency berbeda.

### Dampak dan perbaikan

Operator/reviewer membaca opname ditolak padahal koreksi stok sudah berjalan. Ini membuat status keputusan tidak dapat diandalkan sebagai bukti apakah adjustment berlaku. Menambahkan mekanisme pembalik otomatis pada reject tanpa membedakan race juga berbahaya: request kalah seharusnya conflict, bukan membuat transaksi reversal tak diminta.

Approve dan reject harus berkompetisi pada transisi yang sama, menggunakan status/version serta ownership lock yang konsisten. Hanya satu keputusan boleh menang. Reject yang kalah tidak boleh menulis metadata rejected atau menghasilkan audit sukses. Jika bisnis membutuhkan pembatalan approval, buat operasi reversal eksplisit dengan otorisasi dan bukti tersendiri.

Acceptance: kedua urutan approve/reject, reject saat approval terkunci, double reject, retry setelah respons hilang, dan kegagalan setelah adjustment sebelum finalisasi. Pastikan status, metadata keputusan, stock movement dan respons HTTP sepakat. Tidak boleh status rejected dengan adjustment baru dari approval yang kalah secara administratif.

## Kontrol cutoff dan batas coverage

Guard drift yang ada **berfungsi pada fixture serial**: snapshot100, count90, inbound tambahan10 sebelum approve menghasilkan409; stok tetap110, session submitted dan saga lock dilepas. Ini tidak membuktikan cutoff aman terhadap pergerakan sesudah precheck atau ABA (stok berubah lalu kembali ke angka sama).

Submit dengan item belum dihitung ditolak400. Pengujian ini belum menguji recount/reopen lengkap, bin scope, concurrent balance rebuild, semua stock bucket, RFID count, jurnal adjustment atau perangkat. WM-07, WM-08, FN-14 dan RF-08 Gelombang1 tidak ditutup, tidak diduplikasi, dan tidak dinyatakan fixed. INV-03 masih parsial; INV-05 tetap belum diuji dalam putaran ini.
