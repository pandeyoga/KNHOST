# Gelombang 2, W2-04 — transfer gudang dan reservasi roll

Snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63` diuji dengan ASGI HTTP dan Mongo lokal sintetis. Bukti: [transfer-results.json](transfer-results.json), [harness](repro/wave2_transfer.py), [prompt develop](09_PROMPT_TRANSFER_STOK.md).

Sembilan skenario baru: enam kontrol sesuai ekspektasi, tiga reproduksi cacat. Dua ID baru W2-008 dan W2-009. Reproduksi ketiga W2-T-F03 memperluas W2-006 (resolver owner otomatis) ke transfer gudang dan **tidak dihitung sebagai ID bug unik**. Kumulatif Gelombang 2: **39 skenario unik, 28 kontrol, 11 reproduksi cacat, sembilan ID temuan**. INV-02 tetap parsial karena belum semua transfer lintas gudang, stock cutoff dan UI diuji.

## W2-008 — roll pilihan manual tidak divalidasi terhadap owner transfer

**P1 · API+Mongo terkonfirmasi · W2-T-F02.**

### Lokasi kode

- [transfers.py:174](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/transfers.py#L174): `prefer_owner` diambil dari payload atau entitas aktif.
- [transfers.py:203](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/transfers.py#L203): owner hasil resolver diteruskan bersama roll_ids pilihan operator ke reserve_rolls_for_wh_transfer.
- [roll_service.py:1335](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L1335): query pemilihan roll memfilter id, produk dan status, tetapi **tidak** owner_entity_id yang dikirim dan tidak membatasi akses pengguna. Validasi tambahan hanya memeriksa gudang asal.
- [roll_service.py:1343](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L1343): update status reserved berdasarkan ID/status, kemudian item transfer diberi label owner hasil resolver di [transfers.py:224](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/transfers.py#L224).

### Reproduksi dan implikasi

User hanya berwenang atas A. Gudang W1 dan W2 sama-sama shared. Produk punya stok A20 dan B10 di W1. Payload transfer intra milik A memilih roll_id B secara eksplisit, qty10. API menjawab200. Dokumen transfer entity_id A dan item owner A, tetapi roll terpilih sebenarnya owner B dan menjadi reserved. Balance B pada saat ini tetap melaporkan available10 (juga efek W2-009).

Ini bukan transfer ownership antar-PT yang sah: jalurnya `/api/transfers` dengan transfer_kind=intra_entity dan tidak membuat dokumen inter-company. Jika dilanjutkan sampai dispatch/receive, dokumen dan roll memiliki sumber kepemilikan yang bertentangan; pengujian ini hanya membuktikan reservasi awal, belum ledger/GL intercompany di tahap lanjut.

Kontrol: roll yang dipilih dari gudang W3 sementara source W1 ditolak400 dan status roll tidak berubah. Cancel transfer uji mengembalikan roll B menjadi available. Auto reserve untuk stok A20 qty10 juga benar menahan10 milik A; jalur eksplisit memiliki validasi berbeda.

UI [TransferCreateForm.jsx:81](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/wms/transfer/TransferCreateForm.jsx#L81) mengirim daftar roll_ids operator. Dropdown UI mungkin menyaring kandidat, tetapi permintaan langsung diterima dan kontrak backend harus tetap menjaga owner. Browser UAT belum dilakukan.

### Perbaikan

Validasi **setiap** roll_id terhadap product, source warehouse, owner efektif, status, panjang, dan scope actor sebelum mutasi. Guard update harus mempertahankan precondition owner/gudang/qty, bukan hanya status. Bila payload mencampur roll owner atau gudang, tolak seluruh transfer tanpa reservasi sebagian. Pastikan entitas dokumen, owner item, owner roll dan sumber jurnal konsisten. Jalur intercompany tetap memakai workflow khusus dengan kedua sisi berizin.

Kriteria: A memilih roll B ditolak tanpa efek; A memilih roll A berhasil; daftar campuran A+B all-or-none; race reservation tetap menghasilkan satu pemenang; reject/cancel memulihkan stock bucket yang benar. Uji user multi-entitas serta dedicated/shared warehouse yang sah.

## W2-009 — reservasi roll pilihan manual tidak menyegarkan saldo tersedia

**P1 · API+Mongo terkonfirmasi · W2-T-F01.**

### Lokasi kode

- [roll_service.py:1333](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L1333): cabang roll_ids langsung mengubah setiap roll dari available ke reserved.
- [roll_service.py:1350](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L1350): cabang ini `return out` sebelum mencapai rebuild_balance pada [roll_service.py:1394](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/roll_service.py#L1394).

### Reproduksi dan dampak

Roll A10 available; balance available10/reserved0. POST transfer dengan roll_ids=[roll A] berhasil; roll fisik menjadi reserved, tetapi inventory_balances tetap available10/reserved0. Dengan demikian ATP, dashboard dan keputusan yang membaca projection dapat menganggap10 masih bebas saat transaksi transfer sudah menahannya. Pembaca roll langsung melihat reserved, sehingga UI/flow berbeda bisa menghasilkan jawaban berbeda. Saat transfer dibatalkan, helper release memanggil rebuild; saldo kembali valid available10, tetapi **selama transfer aktif** projection salah.

Kontrol pembeda: transfer tanpa roll_ids, qty10 dari stok20, memakai cabang auto dan langsung menghasilkan balance available10/reserved10. Lifecycle auto hingga completed menghasilkan available0 di asal, available10 di tujuan. Temuan ini spesifik cabang pilihan manual, bukan semua reservasi transfer.

Perbaikan: setelah seluruh roll berhasil diklaim, refresh projection segmen yang benar (product×warehouse×owner), termasuk bila daftar multi-owner ditemukan sebagai error. Integrasikan kompensasi ketika roll ke-n gagal atau rebuild gagal sehingga roll, dokumen dan projection tidak bertentangan. Gunakan operasi idempotent/transactional yang sejalan dengan pekerjaan P02 Gelombang1 dan GN-13; jangan mengandalkan rebuild berkala sebagai sumber kebenaran segera.

Kriteria: available/reserved/ATP selalu mengikuti roll status setelah create transfer eksplisit, reject, cancel, dispatch dan receive; tidak ada window sukses API dengan saldo usang yang menetap. Uji roll tunggal, beberapa roll, kegagalan di tengah, multi-request dan status concurrent. GN-13 membahas stale rebuild out-of-order; kasus ini adalah **rebuild yang sama sekali dilewati** pada cabang eksplisit.

## Pendalaman W2-006 — owner resolver juga memengaruhi transfer otomatis

W2-T-F03: user hanya A, gudang shared, produk memiliki stok available **hanya B10**. POST transfer tanpa owner dan tanpa roll_ids menjawab200, dokumen transfer entity_id A tetapi item owner B. Kode memilih owner melalui `resolve_stock_owner` pada [transfers.py:203](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/transfers.py#L203). Ini memperluas akar masalah W2-006 yang ditemukan pada cycle count. Prompt W2-006 kini harus mencakup seluruh pemanggil resolver, terutama transfer. Jangan membuat ID baru hanya untuk perilaku fallback yang sama.

## Batas coverage

Tes memakai gudang shared sintetis, API dan database nyata, tanpa app lifespan/scheduler. Tidak menjalankan hardware RFID, UI browser, full transfer intercompany, GRN, penjualan setelah ATP stale, crash recovery, atau seluruh kombinasi warehouse policy. Tidak ada perubahan source aplikasi. Temuan Gelombang1 terkait putaway WM-04, root provenance AX-05 dan rebuild GN-13 tetap terbuka dan tidak dihitung ulang.
