# D — Retur (jual & beli) — audit §8

HEAD: `91a3ec0`. Data acuan: 0 `sales_returns`, 0 `purchase_returns` → alur retur E2E `terhambat`; RT-01 terbukti tingkat kode.

## Peta sumber kebenaran: status & penyelesaian retur

```
grep -rnE 'TRANSITIONS|assert_transition|FAMILY_STATE' backend/services/return_state.py backend/services/sales_return_transition.py backend/services/return_roll_settlement_service.py
grep -rnE 'SUPPLIER_STATES|TRANSITIONS' backend/services/purchase_return_state.py backend/services/purchase_return_doc_state.py
```
Penulis: `backend/services/return_state.py` (tabel transisi tunggal) · `backend/services/sales_return_transition.py:38` (assert_transition) · `backend/services/return_roll_settlement_service.py:31` (FAMILY_STATE→return_state) · `backend/services/purchase_return_state.py:27` (RMA supplier) · `backend/services/purchase_return_doc_state.py:28` (status dokumen).

## Pintu ganda

| Pekerjaan | Pintu | Seharusnya |
|---|---|---|
| Status retur jual | satu tabel `return_state.TRANSITIONS` (SAH) | — (bukan duplikat) |
| Penyelesaian retur | roll_settlement / compensation / replacement / cutloss_split | satu pintu penyelesaian (perlu verifikasi data) |

## Matriks skenario

| Skenario | Status | Bukti/alasan |
|---|---|---|
| D-S1 | gagal | bukti/runtime/D-S1.txt + bukti/runtime/D-S1b.txt — alur ACC→scan terima→QC→refund→reverse berjalan dan jurnal seimbang; cacat: RT-03 (batas nominal mati), RT-04 (pintu inspeksi lama), RT-05 (reverse mengembalikan roll ke `delivered`) |
| D-S2 | lulus | bukti/runtime/D-S2-S3.txt — scrap (Dr 5-9500/Cr 1-1300) lalu batal scrap (jurnal balik, panggilan kedua 400); catatan RT-07 |
| D-S3 | terhambat | roll hasil migrasi tanpa PO/supplier asal → disposisi `no_internal_origin`, kedua tahap menolak 400 — bukti/runtime/D-S2-S3.txt; butuh roll ber-PO yang sudah terjual lalu diretur |
| D-S4 | lulus | bukti/runtime/D-S4.txt — cutloss 15 yard: nominal diisi 99 juta dihitung ulang server jadi 375.000; pecah roll 10/15/96,58; jurnal masuk penuh lalu keluar saat kirim balik (neto 15 yard); catatan RT-08 |
| D-S5 | gagal | bukti/runtime/D-S5.txt — tukar barang → pesanan pengganti KSC/SO-00008 (qty 2× kewajiban diterima); reverse retur tidak menyentuh pesanan pengganti (RT-06) |
| D-S6 | lulus | bukti/runtime/D-S6.txt — retur beli dari tolak QC: ACC → jurnal Dr 2-1150/Cr 1-1300 Rp1.400.000; tagihan 300 yard ditolak 3-way match, 200 yard diterima; reverse membalik jurnal |
| D-S7 | terhambat | retur antar-PT: butuh retur |
| D-S8 | gagal | bukti/runtime/D-S8.txt — tolak saat menunggu ACC & buang draf benar; tolak SESUDAH barang diterima gudang: roll kembali `delivered`, SPK QC tetap `draft`, tak ada tugas kirim balik (RT-05) |

## Inventaris form & dropdown

| Form | Field | Sumber pilihan | Saringan | Ditegakkan server? | Masalah |
|---|---|---|---|---|---|
| CreateReturnForm.jsx | order-select (194) | SO terkirim | — | ya | — |
| CreateReturnForm.jsx | type-select (220) | jenis retur | — | ya | — |
| CreateReturnForm.jsx | condition (312) | `CONDITION_OPTIONS` | — | ya | — |
| CreateReturnForm.jsx | reason (332) | `reasons` | — | ya | — |
| ReturnDispositionPanel.jsx | (ikuti anak) | aksi disposisi | per status | ya | tak ada dropdown sendiri |
| ReturnRollClaims.jsx | condition (71) | `CONDITION_OPTIONS` | — | ya | — |
| PurchaseReturns.jsx | supplier (377) | `suppliers` | — | ya | tak per aktif/PT |
| PurchaseReturns.jsx | po-select (381) | PO supplier | per supplier | ya | — |
| PurchaseReturns.jsx | warehouse (385) | `warehouses` | — | ya | tak per PT |
| PurchaseReturns.jsx | product (401) | `products` | — | ya | — |
| PurchaseReturns.jsx | reason (409) | `REASONS` | — | ya | — |
| PurchaseReturns.jsx | basis (414) | opsi basis | — | ya | — |

## Temuan

### RT-01 — pembagian state retur SAH (bukan duplikat)
- Keparahan: Rendah
- Jenis akar: status
- Tingkat bukti: dugaan (baca kode)
- Bukti: `backend/services/sales_return_transition.py:38` (satu tabel `return_state`); `backend/services/purchase_return_state.py:27` vs `backend/services/purchase_return_doc_state.py:28` (dua sumbu).
- Reproduksi: baca kode; uji runtime butuh retur (0 di seed).
- Dampak: — (menutup kecurigaan duplikasi).
- Arah perbaikan: —.
- Keputusan pemilik: —.
- Sudah ada: —.

### RT-02 — banyak sub-service penyelesaian retur (risiko uang/stok ganda)
- Keparahan: Rendah
- Jenis akar: duplikasi (dugaan)
- Tingkat bukti: dugaan (baca kode)
- Bukti: `backend/services/return_roll_settlement_service.py:31` + `backend/services/return_compensation_service.py` + `backend/services/return_replacement_service.py`.
- Reproduksi: butuh retur per-roll melewati penyelesaian (0 di seed) — uji runtime yang dibutuhkan untuk membuktikan/menggugurkan.
- Dampak: potensi kompensasi/stok ganda bila >1 pintu menyelesaikan satu retur.
- Arah perbaikan: satu pintu penyelesaian + satu status.
- Keputusan pemilik: —.
- Sudah ada: —.

### RT-03 — Batas nominal kontrol dua orang retur penjualan tidak pernah aktif (nilai retur selalu 0)
- Keparahan: Sedang
- Jenis akar: cacat logika
- Tingkat bukti: baca kode + data runtime (aturan dua orang belum diaktifkan untuk diuji)
- Bukti: `backend/routers/sales_returns.py:344` (`_nilai_retur` membaca `line_total`/`quantity`/`unit_price`) · `backend/services/dual_control.py:63` · `bukti/runtime/D-S1.txt` (baris retur hanya punya `quantity_returned`, tanpa harga)
- Reproduksi: Buat retur → lihat baris: `unit_price: None, line_total: None`. `_nilai_retur` = 0 untuk retur mana pun, sehingga `nominal > batas` tidak pernah benar.
- Dampak: Bila pemilik menyetel "retur di atas Rp X butuh orang kedua", aturan itu diam-diam tidak berlaku. Bawaan saat ini satu orang, jadi belum terasa.
- Arah perbaikan: Hitung nilai retur dari harga SO asal (fungsi yang sama dengan `settle-preview`).
- Keputusan pemilik: —
- Sudah ada: —

### RT-04 — Pintu inspeksi retur lama masih hidup di server dan menutup SPK QC tanpa hasil per roll
- Keparahan: Sedang
- Jenis akar: duplikasi
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/routers/sales_returns.py:451` · `backend/routers/sales_returns.py:468` · `backend/services/return_roll_settlement_service.py:79` · `bukti/runtime/D-S1.txt`
- Reproduksi: Retur disetujui + scan terima → akun qc `POST /sales-returns/{id}/inspect/start` lalu `/inspect/complete` (grade A). Hasil: retur `inspected`, SPK KSC/INS-00001 `closed` dengan baris kosong; panel per roll berkata "QC roll ini belum selesai" untuk semua pilihan, tetapi `POST /settle` (refund) → 200.
- Dampak: Dua cara menyelesaikan QC retur dengan hasil berbeda; lewat pintu lama, pemeriksaan 4-point per roll terlewati dan layar penyelesaian per roll buntu. Layar tidak memanggil pintu ini (`frontend/src/features/sales/` tanpa `inspect/complete`).
- Arah perbaikan: Matikan pintu lama atau arahkan ke SPK.
- Keputusan pemilik: —
- Sudah ada: RT-02

### RT-05 — Retur ditolak atau dibalik sesudah barang diterima gudang: roll dicatat kembali di pelanggan, tanpa tugas kirim balik
- Keparahan: Tinggi
- Jenis akar: status
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/services/return_service.py:2156` (`reject_return`) · `backend/services/return_service.py:1932` (`reverse_settlement`) · `bukti/runtime/D-S8.txt` · `bukti/runtime/D-S1b.txt`
- Reproduksi: Retur disetujui → gudang scan terima (roll `quarantine`) → manager `reject`. Hasil: roll `delivered`, SPK QC tetap `draft`, `back-shipment` → 400 "Tidak ada roll … menunggu dikirim balik". Sama pada `reverse` sesudah refund.
- Dampak: Kain pelanggan ada di gudang tetapi sistem mencatatnya di pelanggan; tidak ada dokumen keluar; SPK yatim tertinggal di antrean QC; roll bisa diklaim retur lagi.
- Arah perbaikan: Tolak/balik sesudah scan terima harus melahirkan kiriman balik (atau menahan roll di karantina) dan menutup SPK.
- Keputusan pemilik: Barang retur yang ditolak: dikirim balik atau disimpan?
- Sudah ada: —

### RT-06 — Membalik retur tukar-barang tidak menyentuh pesanan pengganti
- Keparahan: Sedang
- Jenis akar: cacat logika
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/services/return_service.py:1932` · `backend/routers/sales_return_exceptions.py:177` · `bukti/runtime/D-S5.txt`
- Reproduksi: Retur → tukar barang → `replacement-order` (KSC/SO-00008, 258,54 yard dicadangkan) → `reverse` retur. Hasil: retur `cancelled`, roll asal kembali `delivered`, SO-00008 tetap `reserved` dan muncul di daftar Keep.
- Dampak: Pesanan pengganti tanpa dasar tetap mengunci stok dan bisa terkirim. Di kasus uji pesanan itu ditagih penuh (kredit 0), jadi risikonya stok dan kebingungan, bukan uang hilang.
- Arah perbaikan: Tolak `reverse` bila ada pesanan pengganti aktif, atau batalkan bersamaan.
- Keputusan pemilik: —
- Sudah ada: —

### RT-07 — Grade roll berubah lewat retur dan cutloss tanpa riwayat; BS bisa masuk stok tersedia dengan HPP penuh
- Keparahan: Tinggi
- Jenis akar: duplikasi
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/services/return_identity_service.py:115` · `backend/services/return_service.py:1374` · `backend/services/return_cutloss_split_service.py:126` · `backend/services/return_service.py:2063` · `bukti/runtime/D-S2-S3.txt` · `bukti/runtime/E-S1.txt`
- Reproduksi: Retur roll A → SPK QC grade BS → refund → `quarantine/release` scrap → `reverse-writeoff`. Hasil: roll `available`, grade BS, `unit_cost` 13.680 (penuh), `grade_history: []`, `grade-impairments` kosong. Pembanding: `grade-override` dan SPK 4-point mengisi `grade_history`.
- Dampak: Ada penulis grade di luar `grade_service.set_roll_grade`; turun grade lewat retur tidak terlacak dan penurunan nilai persediaan tidak dijurnal bila lewat jalur scrap→batal scrap.
- Arah perbaikan: Semua perubahan grade lewat satu fungsi; batal scrap kembali ke karantina, bukan ke stok tersedia.
- Keputusan pemilik: Stok BS hasil retur dinilai berapa?
- Sudah ada: QM-01 (kini terbukti: lebih dari satu penulis)

### RT-08 — Kirim balik potongan cutloss dilakukan satu klik tanpa tugas gudang, pindai, atau cek muat
- Keparahan: Rendah
- Jenis akar: aturan tidak ditegakkan
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/routers/sales_return_exceptions.py:239` · `bukti/runtime/D-S4.txt`
- Reproduksi: Sesudah pecah roll, akun md `POST /sales-returns/{id}/cutloss/{ctl}/return-shipment` → Surat Jalan KSC/SJ-00007 langsung `dispatched`, roll `delivered`; tidak ada `wms_tasks`. Akun gudang 403.
- Dampak: Barang keluar gudang dicatat oleh MD, bukan gudang; aturan "ambil wajib pindai" tidak berlaku di jalur ini.
- Arah perbaikan: Lewatkan ke tugas keluar gudang yang sama.
- Keputusan pemilik: —
- Sudah ada: —
