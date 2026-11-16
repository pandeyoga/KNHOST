# F — Pesanan sesudah POS — audit §8

HEAD: `91a3ec0`. Backend hidup + 8 SO seed. F-S3 diuji runtime (4 modul pemenuhan).

## Peta sumber kebenaran: ketersediaan untuk pemenuhan SO

```
grep -n 'stock_figures' backend/services/fulfillment_service.py backend/services/fulfillment_decision_service.py
grep -nE 'inventory_balances|inventory_rolls' backend/services/fulfillment_plan_service.py backend/services/fulfillment_wizard_service.py
```
Sumber: `backend/services/fulfillment_service.py:59` & `backend/services/fulfillment_decision_service.py:62` (SSOT `stock_figures`) vs `backend/services/fulfillment_plan_service.py:25` & `backend/services/fulfillment_wizard_service.py:20` (koleksi mentah).

## Pintu ganda

| Pekerjaan | Pintu | Seharusnya |
|---|---|---|
| Angka ketersediaan SO | fulfillment_service+decision (stock_figures) vs plan+wizard (mentah) | satu sumber stock_figures |
| Katalog jual stage | `is_orderable` lifecycle saja | aturan stage |

## Matriks skenario

| Skenario | Status | Bukti/alasan |
|---|---|---|
| F-S1 | lulus | bukti/runtime/F-S1.txt — SO roll utuh 236 yard → ambil wajib pindai → kirim → jurnal pendapatan Rp6.549.000 = total SO, HPP terpisah; catatan SO-04. Mode potong (panjang ≠ pesanan) belum dijalankan |
| F-S2 | lulus | bukti/runtime/F-S2.txt — DP 50% lalu ganti 2 roll (260,48) dengan 1 roll (136,44): total tagihan & DP tetap, kekurangan 124,04 jadi backorder; sesudah kirim sebagian DP direklas (2-1400→1-1200) |
| F-S3 | gagal | bukti/runtime/F-S3-S8.txt — SO-00009: rencana pemenuhan = kurang 124,04; wizard = butuh 260,48; meja pemenuhan = 260,48 `stock_ok` (SO-01 terbukti runtime) |
| F-S4 | terhambat | kedaluwarsa reservasi tidak tersimulasi (tanggal batas tidak boleh diubah lewat API; penulisan langsung ke DB uji tidak mengenai dokumen) — bukti/runtime/F-S4.txt; yang terbukti: job hanya menyentuh `reserved`/`waiting_approval` |
| F-S5 | gagal | bukti/runtime/F-S2.txt + bukti/runtime/F-S4.txt — SO terkirim sebagian tidak bisa dibatalkan/ditutup (SO-02); SO ber-DP dibatalkan → DP Rp3.163.611 tetap menempel di SO batal, deposit 0 (SO-03) |
| F-S6 | terhambat | harga khusus lalu alokasi berubah: butuh approval harga |
| F-S7 | terhambat | SO→PR/PO→datang→alokasi: butuh backorder+PO datang |
| F-S8 | gagal | bukti/runtime/F-S3-S8.txt — angka kebutuhan pesanan yang sama berbeda antar pintu (124,04 vs 260,48); layar belum dipotret |

## Inventaris form & dropdown

| Form | Field | Sumber pilihan | Saringan | Ditegakkan server? | Masalah |
|---|---|---|---|---|---|
| CheckoutDrawer.jsx | customer (318) | pelanggan | — | ya | — |
| CheckoutDrawer.jsx | address (331) | alamat pelanggan | per pelanggan | ya | — |
| CheckoutDrawer.jsx | payment-term (455) | `termOptions` | — | ya | — |
| CheckoutStep3.jsx | (ikuti anak) | ringkasan/alokasi | — | ya | tak ada dropdown sendiri |
| ReallocateRollsModal.jsx | (ikuti anak) | pilih roll realokasi | per produk | ya | tak ada dropdown; pencari roll |
| PriceApprovals.jsx | customer (328) | `customers` | — | ya | — |
| PriceApprovals.jsx | product (335) | `products` | — | ya | — |

## Temuan

### SO-01 — plan/wizard hitung ketersediaan dari koleksi mentah (lewati SSOT)
- Keparahan: Tinggi
- Jenis akar: duplikasi / cacat logika (risiko laten)
- Tingkat bukti: dugaan (baca kode) — runtime: 3 pintu SETUJU di SO-00006 (tak tereproduksi di seed)
- Bukti: `backend/services/fulfillment_plan_service.py:25` & `backend/services/fulfillment_wizard_service.py:20` (mentah) vs `backend/services/fulfillment_service.py:59` (stock_figures); `bukti/F-S3.txt`.
- Reproduksi: SO kurang stok dgn roll di gudang tak-dihitung / cadangan makloon sebagian; bandingkan ATP/decision/plan/wizard. `bukti/F-S3.txt`.
- Dampak: layar berbeda bisa menampilkan ketersediaan berbeda untuk SO sama.
- Arah perbaikan: arahkan plan & wizard ke `stock_figures`.
- Keputusan pemilik: tagihan ikut alokasi terakhir atau terkunci nilai bayar?
- Sudah ada: MS-05.

### SO-02 — Pesanan terkirim sebagian dengan backorder tidak punya jalan keluar
- Keparahan: Tinggi
- Jenis akar: status
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/routers/sales_orders_extra.py:913` (batal ditolak) · `backend/routers/sales_orders.py:903` (PATCH hanya catatan) · `backend/routers/special_orders.py:926` (batal baris hanya Pesanan Khusus) · `bukti/runtime/F-S2.txt`
- Reproduksi: SO-00009 terkirim 136,44 dari 260,48. `cancel` → 409; `mark-delivered` → 409; `release-reservation` → 409; `reallocate` hanya sebelum konfirmasi. Stok sendiri 24.128 yard tersedia, backorder tetap `waiting_stock`.
- Dampak: Pesanan menggantung selamanya, sisa nilainya terus dihitung sebagai pesanan terbuka (memakan plafon kredit).
- Arah perbaikan: Sediakan "tutup sisa" (batal baris/qty sisa) untuk SO biasa dengan aturan yang sama dengan Pesanan Khusus.
- Keputusan pemilik: Sisa backorder boleh ditutup Admin Sales sendiri atau perlu persetujuan?
- Sudah ada: —

### SO-03 — Membatalkan pesanan yang sudah menerima DP meninggalkan uang muka menempel di pesanan batal
- Keparahan: Tinggi
- Jenis akar: cacat logika
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/routers/sales_orders_extra.py:888` (hanya menangani pembayaran sample, baris 955-966) · `bukti/runtime/F-S4.txt`
- Reproduksi: SO-00010 Rp6.327.222 → kwitansi DP Rp3.163.611 → verifikasi → `cancel` → 200. Hasil: kwitansi tetap `posted` teralokasi ke SO batal, `deposit_balance` 0, tidak ada kewajiban refund/kasus/notifikasi; saldo 2-1400 tetap memuatnya. Akun finance `void` kwitansi → 403.
- Dampak: Uang pelanggan ada di buku besar tetapi tidak muncul sebagai deposit yang bisa dipakai atau dikembalikan; hanya ketahuan bila pelanggan menagih.
- Arah perbaikan: Batal SO ber-pembayaran: wajib memilih jadi deposit atau refund, atau tolak batal sampai kwitansi dilepas.
- Keputusan pemilik: DP pesanan batal: otomatis jadi deposit, atau dikembalikan?
- Sudah ada: —

### SO-04 — Pengecualian cek muat bisa diberikan sebelum ada roll yang diambil
- Keparahan: Rendah
- Jenis akar: aturan tidak ditegakkan
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/routers/outbound_picking.py:671` · `bukti/runtime/F-S1.txt`
- Reproduksi: SO `confirmed`, tugas `created`, belum ada pindai → manager `POST /outbound/so/{id}/loading-check/override` → 200.
- Dampak: Pengecualian tercatat untuk muatan yang belum ada; nilai kontrolnya turun.
- Arah perbaikan: Terima pengecualian hanya sesudah semua roll terambil.
- Keputusan pemilik: —
- Sudah ada: —
