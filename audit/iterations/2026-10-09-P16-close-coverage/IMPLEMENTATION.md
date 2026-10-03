# P16 — Tutup cakupan: transfer, penjualan → faktur, alur desain

Permintaan: "lanjutkan uji hingga semua selesai" (stok antargudang, penjualan sampai faktur, alur desain + pembatalan transfer yang tertunda).

Lingkungan: repo pandeyoga/KNHOST di-clone ulang ke /app, `seed_realistic.py`, data uji `TEST_P16_*` dibersihkan otomatis (roll di-restore dari snapshot, saldo dibangun ulang).

## Bukti
- `head_before_patch.txt` — kode HEAD GitHub: **24/35** (skenario transfer berhenti karena `/status approved` lolos).
- `after_patch.txt` — sesudah perbaikan: **43/43**.
- `uat_iteration_125.json` — agen uji: API 100%, UI Manajemen Transfer (Batalkan + alur penuh) 100%.
- Jalankan ulang: `cd /app/backend && python ../audit/iterations/2026-10-09-P16-close-coverage/repro_p16.py [--only=trf,sale,design]`.

## Temuan & perbaikan
| ID | Temuan | Perbaikan |
|---|---|---|
| INV-02 | `POST /transfers/{id}/status` menerima `approved`/`rejected`/`cancelled` → approve tanpa izin `transfer.approve`, tolak/batal tanpa melepas roll. | `STATUS_TRANSITIONS` hanya transisi operasional (approved→picking→staging→dispatched→completed); status khusus ditolak 400 dengan petunjuk endpoint yang benar (`routers/transfers.py`). |
| INV-04 | `POST /transfers/inter-company` tidak pernah menyimpan dokumen: roll entitas asal tertahan ber-ref transfer yang tidak ada (stok bocor, GET/DELETE 404). | `insert_one` di dalam blok saga (gagal → reservasi dilepas). |
| SALE-03 | SO yang sudah punya Faktur Pajak aktif bisa dibatalkan → PPN Keluaran tanpa transaksi. | `POST /sales-orders/{id}/cancel` 409 sampai Faktur Pajak dibatalkan (`routers/sales_orders_extra.py`). |
| DESIGN-01 | Jalur lama `POST /design-gallery/{id}/submit|reject|approve` melewati Studio: desainer bisa meng-ACC desainnya sendiri tanpa nilai, permintaan desain tidak ikut. | Ketiganya diteruskan ke `_do_transition` Studio (izin `rnd.assess`, nilai wajib, sinkron permintaan). `DesignApproveIn.score` opsional. |

## Terverifikasi tanpa perubahan
- Batal transfer via DELETE (alasan tersimpan + audit), juga sesudah dispatched (mutasi `transfer_cancelled` menyeimbangkan `transfer_out`); tolak melepas roll; roll ganda ditolak 409; total panjang & `inventory_balances` konsisten.
- O2C: total/PPN (DPP 11/12 × 12%), Faktur Pajak & dokumen Faktur = SO, jurnal Piutang/Pendapatan/PPN/HPP, kiriman parsial pro-rata & Σ akhir = grand, sisa tagihan setelah penerimaan AR.
- Desain: serah final wajib mockup + source, aktivasi hanya penilai, arsip wajib alasan, reopen menjaga berkas/versi.

## Sisa (tidak diubah)
- Integritas: 2 FAIL `KANDA/SO-00001` (backorder seed, sudah tercatat sejak P05).
- INV-04 rekonsiliasi dua buku saat approve belum diuji ulang; 17 kasus `planned` di luar cakupan putaran ini.
- Dokumen Faktur komersial selalu memuat nilai pesanan penuh (bukan per kiriman) — perilaku saat ini, keputusan pemilik bila ingin faktur per surat jalan.
