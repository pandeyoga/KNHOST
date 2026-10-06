# Dampak yang terlihat pada rantai bisnis besar

## Sales demand → keputusan pemenuhan → supply

```text
SO demand100
  → plan stock / interco / supplier PR / wait incoming
  → qty efektif + reference supply + remaining demand
  → reserve stock / PO / makloon
  → receiving aktual dan RFID
  → picking / cut / staging / loading perwarehouse
  → SJ / dispatch / AR-COGS-GL
  → payment / deposit / bank reconciliation / reversal
```

Rantai ini belum aman hanya karena dialog berhasil disimpan. PLAN-01 dapat mencatat 100 supply ketika PR hanya 20; PLAN-03 memberi scope full ketika yang berhasil 30; PLAN-05 menawarkan PO100 bagi demand 200. BACKORDER-01 dapat menulis allocations 160 sementara item menunjukkan reserved 80/backorder 20. Akibatnya masing-masing tampilan dapat terlihat masuk akal, tetapi supply, demand dan state operasional tidak konservatif.

Perbaikan harus mengikat order line, effective quantity, operation/reference identity, supply claim dan state per bagian. Setelah satu bagian berhasil, retry bagian lain tidak boleh reserve atau membeli ulang bagian pertama. Nilai yang belum eksklusif harus ditampilkan sebagai perkiraan, bukan janji pemenuhan pasti.

## Procurement → receiving → incoming badges

```text
PO quantity100 yard
  → producer quantity_base91.44 meter
  → receipt aktual perroll
  → remaining base qty
  → PO partial/completed/closed_short
  → ATP / global incoming / pending SO / reorder / payment variance
```

Public producer benar mengonversi yard ke meter. Consumer global mengambil 100 quantity mentah dan memberi label meter. Pada contoh PO100 diterima 90, producer menjadi partial dan incoming helper menghilangkan sisa 10. Kedua masalah harus diperbaiki bersama: canonical unit, eligible lifecycle dan outstanding quantity. V3-PO variance/amendment tetap perlu ditutup supaya dokumen dan kewajiban pembayaran konsisten dengan penerimaan fisik.

## Inventory ownership → sales aggregate → valuation

Sales memang membutuhkan gabungan tersedia/reserved/coming dari semua entitas, sesuai penjelasan pengguna. Aggregation harus terjadi sesudah grain product+warehouse+owner benar; join yang menghilangkan owner dapat menggandakan nilai/velocity. Pembelian antarentitas dan ledger masih membutuhkan kepemilikan legal, kontrak harga internal serta dokumen yang saling merujuk. Angka global tidak menggantikan transfer ownership.

MD/R&D role lini dan jenis sampling, approval hasil/spec/final, SKU/material stage serta flow makloon tetap mengikuti kebutuhan yang sudah dijelaskan. Barang stok bertag menuju storage; barang untuk SO bertag dapat melalui transit/cross-dock. Semua barang wajib tag. Arti C/H tidak diasumsikan. Requirement historis dicatat dengan verdict lama, bukti current dan bagian yang belum mempunyai runtime acceptance unik.

## Frontend angka → keputusan manajemen

Revenue total benar tidak cukup bila rata-rata memakai 20 baris. Availability benar tidak cukup bila badge incoming memakai unit lain. Grafik periode 90 tidak benar bila data 30 yang terlambat menimpa state atau hanya 14 titik ditampilkan tanpa label. Analitik reserve harus memakai free length/quantity yang sama dengan operasional, dan meter+kg tidak boleh dijumlah menjadi satu quantity.

Validasi setiap metrik harus mengikuti source producer → canonical persisted field → projection/query → API payload → UI expression/render → export. Laporan ini memiliki counterexample terarah pada rantai tersebut, tetapi belum mengklaim semua rendered UI/export telah diuji.
