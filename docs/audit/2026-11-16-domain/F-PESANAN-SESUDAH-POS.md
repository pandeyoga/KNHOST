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
| F-S1 | terhambat | POS→SO→alokasi→faktur E2E, panjang roll≠pesanan: butuh checkout berjalan |
| F-S2 | terhambat | realokasi sesudah DP: butuh pembayaran DP |
| F-S3 | lulus | bukti/F-S3.txt — 4 modul pemenuhan; plan==wizard di SO-00006 (divergensi kode nyata, laten) |
| F-S4 | terhambat | keep→pending→buka lagi: butuh jalankan siklus umur |
| F-S5 | terhambat | batal baris sesudah alokasi/bayar: butuh SO beralokasi+bayar |
| F-S6 | terhambat | harga khusus lalu alokasi berubah: butuh approval harga |
| F-S7 | terhambat | SO→PR/PO→datang→alokasi: butuh backorder+PO datang |
| F-S8 | terhambat | angka pesanan sama antar layar: butuh banding UI 4 layar |

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
