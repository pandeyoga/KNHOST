# Coverage retur pembelian: approval, RMA, refund dan reversal

30 September 2026. Snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. **Sembilan skenario baru selesai: empat kontrol bekerja, lima reproduksi mendukung dua temuan tambahan dan pendalaman GN-07.** Source aplikasi tidak diubah.

[Harness](integration_repro/integration_round8.py) · [Hasil JSON](integration_repro/integration_round8.json) · [Log](integration_repro/integration_round8.log) · [Checklist skenario](29_CHECKLIST_SKENARIO_COVERAGE.md)

## Metode

Fungsi asli create_purchase_return → submit → approve dipanggil dengan MongoDB lokal. Variasi RMA menjalankan approve → ship → supplier_accept(refund), atau supplier_reject → goods_back. Reversal memakai reverse_settlement asli. Master, PO, stok pembukaan dan marker vendor_bill posted adalah fixture; pembuatan invoice/bill dan pelunasan PO bukan bagian uji ini. Keputusan periode tertutup berasal dari GL guard asli. Tidak ada stub GL maupun akses bank/produksi.

## Hasil

| ID | Kasus | Hasil |
|---|---|---|
| I8-C01 | Direct return non-PPN | Roll keluar; returned_amount PO=100; satu jurnal debit 100 |
| I8-C02 | Reversal atas retur tersebut | Roll available; returned_amount=0; jurnal asli+reversal net nol **per akun** |
| I8-C03 | Reversal ulang | Snapshot tidak berubah |
| I8-C04 | RMA ditolak supplier → goods_back | Roll available; AP tidak dikurangi; tidak ada jurnal retur |
| I8-F01 | Retur barang 100 + PPN 11, bill posted | PO berkurang 111 tetapi Dr Hutang 100 dan Cr Persediaan 89 |
| I8-F02 | RMA refund atas 100 + PPN 11 | Dokumen gross 111; cash ledger dan debit kas GL hanya 100 |
| I8-F03 | Approval saat periode tertutup | Exception, tetapi retur approved, stok keluar, AP berubah, jurnal nol |
| I8-F04 | Retry approve sesudah hambatan dilepas | Ditolak karena sudah approved; jurnal tetap nol |
| I8-F05 | Stok 10, permintaan FIFO 15 | ValueError setelah roll 10 menjadi returned_supplier; dokumen tetap pending |

Pada reversal, jumlah total debit dua jurnal adalah 200 karena jurnal asli dan pembalik masing-masing 100; itu bukan duplikasi nilai. Assertion tambahan memeriksa net debit-kredit setiap akun = 0. Pengujian ini juga menunjukkan mengapa jumlah jurnal saja bukan ukuran kebenaran Finance.

## IX-16 — P1 — Kontrak nilai net/gross retur beli membuat AP, persediaan dan kas tidak cocok

**Lokasi:** [backend/services/purchase_return_service.py:322](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L322) · [backend/services/purchase_return_service.py:339](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L339) · [backend/services/purchase_return_service.py:350](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L350) · [backend/services/gl_service.py:2148](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L2148)

**Bukti:** I8-F01: barang bernilai 100 dan PPN fixture 11 menghasilkan grand_total=111. Setelah approve, returned_amount PO naik 111, tetapi journal Dr Hutang hanya 100, Cr Persediaan 89 dan Cr PPN Masukan 11. Roll senilai 100 dikeluarkan. Fixture vendor_bill berstatus posted dipasang untuk memastikan akun debit adalah Hutang. I8-F02 menjalankan jalur RMA approve → ship → supplier_accept dengan outcome refund: grand_total=111, tetapi debit kas GL dan cash_transactions masing-masing 100.

**Akar kesalahan:** Pemanggil mengirim fresh.total_amount (net barang) sebagai amount ke post_purchase_return. Helper menganggap amount sudah gross, mengurangi ppn sekali lagi untuk menghitung net dan memakai amount sebagai debit. Jalur cash ledger juga menerima total_amount tanpa ppn. Jurnal tetap debit=credit, sehingga balance check jurnal tidak menangkap perbedaan terhadap dokumen dan subledger.

**Batas bukti/dampak:** Ini uji aritmetika dan kontrak field, bukan penetapan tarif pajak yang sah atau penilaian kepatuhan perpajakan. Nilai 11 dipilih sebagai fixture. Tidak ada pembayaran bank aktual. Opening stock dan vendor bill dibuat sebagai fixture, sehingga bukti merupakan delta retur, bukan rekonsiliasi buku perusahaan lengkap.

**Perbaikan:** Gunakan kontrak nominal eksplisit net_amount, tax_amount dan gross_amount. Pastikan caller/helper sepakat; jangan hanya menambah PPN di satu lokasi. Pada fixture ini, delta stok 100 dan PPN 11 harus sesuai gross 111 menurut kontrak dokumen. Sinkronkan returned_amount PO, jurnal, refund cash dan reversal. Cari seluruh caller post_purchase_return sebelum mengganti signature.

**Acceptance criteria:** Test non-PPN dan PPN dengan AP credit maupun refund; cocokkan dokumen, stok, AP, GL dan cash ledger. Uji rounding, retur parsial, sudah ditagih/belum ditagih, serta reversal per akun. Seimbang debit-kredit saja tidak cukup; semua subledger harus sesuai. Sediakan dry-run daftar retur historis dengan nilai tidak cocok.

### Prompt develop IX-16

```text
Perbaiki IX-16 pada KNHOST.

Reproduksi: I8-F01: barang bernilai 100 dan PPN fixture 11 menghasilkan grand_total=111. Setelah approve, returned_amount PO naik 111, tetapi journal Dr Hutang hanya 100, Cr Persediaan 89 dan Cr PPN Masukan 11. Roll senilai 100 dikeluarkan. Fixture vendor_bill berstatus posted dipasang untuk memastikan akun debit adalah Hutang. I8-F02 menjalankan jalur RMA approve → ship → supplier_accept dengan outcome refund: grand_total=111, tetapi debit kas GL dan cash_transactions masing-masing 100.

Akar: Pemanggil mengirim fresh.total_amount (net barang) sebagai amount ke post_purchase_return. Helper menganggap amount sudah gross, mengurangi ppn sekali lagi untuk menghitung net dan memakai amount sebagai debit. Jalur cash ledger juga menerima total_amount tanpa ppn. Jurnal tetap debit=credit, sehingga balance check jurnal tidak menangkap perbedaan terhadap dokumen dan subledger.

Tugas: Gunakan kontrak nominal eksplisit net_amount, tax_amount dan gross_amount. Pastikan caller/helper sepakat; jangan hanya menambah PPN di satu lokasi. Pada fixture ini, delta stok 100 dan PPN 11 harus sesuai gross 111 menurut kontrak dokumen. Sinkronkan returned_amount PO, jurnal, refund cash dan reversal. Cari seluruh caller post_purchase_return sebelum mengganti signature.

Acceptance: Test non-PPN dan PPN dengan AP credit maupun refund; cocokkan dokumen, stok, AP, GL dan cash ledger. Uji rounding, retur parsial, sudah ditagih/belum ditagih, serta reversal per akun. Seimbang debit-kredit saja tidak cukup; semua subledger harus sesuai. Sediakan dry-run daftar retur historis dengan nilai tidak cocok.

Gunakan integration_round8.py pada database sintetis. Setelah patch, ganti assertion karakterisasi cacat menjadi ekspektasi invariant benar. Pertahankan kontrol positif, uji semua caller, jelaskan recovery data historis dengan dry-run. Jangan mengubah data produksi otomatis atau menyatakan seluruh Finance lulus dari test ini.
```

## IX-17 — P1 — Retur menjadi approved dan mengubah stok/AP sebelum jurnal ditolak

**Lokasi:** [backend/services/purchase_return_service.py:283](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L283) · [backend/services/purchase_return_service.py:309](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L309) · [backend/services/purchase_return_service.py:254](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L254)

**Bukti:** I8-F03: approve retur non-PPN 100 pada periode tertutup menghasilkan ClosedPeriodError asli. Namun dokumen sudah approved/accepted_supplier, stok returned_supplier dan returned_amount PO=100; journal_count=0. Setelah fixture periode dibuka, approve ulang ditolak karena status sudah approved (I8-F04); jurnal tetap nol.

**Akar kesalahan:** Status final, stock_adjusted dan pengurangan AP ditulis sebelum pemanggilan GL. Exception tidak membatalkan efek tersebut dan status tidak menunjukkan posting gagal. Guard approve menolak dokumen yang sudah final, sehingga jalur pengguna yang sama tidak dapat melanjutkan pekerjaan yang belum selesai. Ini pola sejenis IX-14 pada GRN, tetapi lokasi dan efek retur berbeda.

**Batas bukti/dampak:** Bukti tidak menyatakan tidak ada koreksi manual di seluruh sistem. Yang terkonfirmasi adalah partial failure dan ketidakmampuan retry melalui approve. Mengulang operasi dengan dokumen retur baru justru berisiko menghasilkan efek stok/AP tambahan.

**Perbaikan:** Pisahkan persetujuan bisnis, efek stok, settlement AP dan status posting, atau lakukan transaksi/saga dengan checkpoint dan effect key. Recovery harus mengenali efek yang sudah ada dan hanya menyelesaikan yang belum. Jaga otorisasi periode/tanggal; jangan membuka periode otomatis. Audit semua jalur direct dan supplier_accept.

**Acceptance criteria:** Closed period dan kegagalan DB tidak boleh meninggalkan status finansial sukses palsu. Retry sesudah hambatan dilepas menghasilkan satu jurnal tanpa mengurangi stok/AP lagi. Uji crash tiap tahap, concurrent approval/acceptance dan reversal atas operasi yang belum lengkap. Tampilkan status recovery pada UI.

### Prompt develop IX-17

```text
Perbaiki IX-17 pada KNHOST.

Reproduksi: I8-F03: approve retur non-PPN 100 pada periode tertutup menghasilkan ClosedPeriodError asli. Namun dokumen sudah approved/accepted_supplier, stok returned_supplier dan returned_amount PO=100; journal_count=0. Setelah fixture periode dibuka, approve ulang ditolak karena status sudah approved (I8-F04); jurnal tetap nol.

Akar: Status final, stock_adjusted dan pengurangan AP ditulis sebelum pemanggilan GL. Exception tidak membatalkan efek tersebut dan status tidak menunjukkan posting gagal. Guard approve menolak dokumen yang sudah final, sehingga jalur pengguna yang sama tidak dapat melanjutkan pekerjaan yang belum selesai. Ini pola sejenis IX-14 pada GRN, tetapi lokasi dan efek retur berbeda.

Tugas: Pisahkan persetujuan bisnis, efek stok, settlement AP dan status posting, atau lakukan transaksi/saga dengan checkpoint dan effect key. Recovery harus mengenali efek yang sudah ada dan hanya menyelesaikan yang belum. Jaga otorisasi periode/tanggal; jangan membuka periode otomatis. Audit semua jalur direct dan supplier_accept.

Acceptance: Closed period dan kegagalan DB tidak boleh meninggalkan status finansial sukses palsu. Retry sesudah hambatan dilepas menghasilkan satu jurnal tanpa mengurangi stok/AP lagi. Uji crash tiap tahap, concurrent approval/acceptance dan reversal atas operasi yang belum lengkap. Tampilkan status recovery pada UI.

Gunakan integration_round8.py pada database sintetis. Setelah patch, ganti assertion karakterisasi cacat menjadi ekspektasi invariant benar. Pertahankan kontrol positif, uji semua caller, jelaskan recovery data historis dengan dry-run. Jangan mengubah data produksi otomatis atau menyatakan seluruh Finance lulus dari test ini.
```

## GN-07/E1 — P1 — Penolakan stok tidak cukup terjadi setelah stok sudah dikeluarkan

**Lokasi:** [backend/services/purchase_return_service.py:295](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L295) · [backend/services/purchase_return_service.py:301](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L301) · [backend/services/purchase_return_service.py:621](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L621)

**Bukti:** I8-F05: retur FIFO meminta 15 ketika tersedia satu roll 10. approve mengeluarkan roll 10 menjadi returned_supplier, kemudian melempar ValueError stok tidak cukup. Dokumen tetap pending_approval, returned_amount=0 dan tidak ada jurnal. Tidak ada fault injection; penolakan berasal dari hasil konsumsi asli.

**Akar kesalahan:** Fungsi konsumsi memutasi roll/movement semampunya lalu mengembalikan consumed. Pemanggil baru memeriksa consumed < requested setelah perubahan tersebut. Ia tidak mengembalikan stok dan tidak menandai operasi parsial untuk dipulihkan. Ini pendalaman GN-07 tentang keamanan konsumsi retur, tidak dihitung ulang sebagai akar cacat independen.

**Batas bukti/dampak:** Barang sudah keluar dari bucket available tetapi dokumen belum disetujui dan nilai keuangan belum berubah. Pada kasus beberapa item, risiko juga mencakup item awal yang sudah diproses sebelum item berikutnya gagal; variasi multi-item belum diuji pada putaran ini.

**Perbaikan:** Periksa seluruh kebutuhan sebelum mutasi, lalu claim konsumsi secara atomik agar precheck tidak bisa dibatalkan race. Sediakan rollback/resume yang memiliki ownership efek. Gunakan ledger konsumsi per item/roll dan catat kegagalan secara eksplisit. Jangan membuat compensation yang menimpa pemakaian roll oleh transaksi lain.

**Acceptance criteria:** Stok 10 untuk permintaan 15 harus ditolak tanpa movement atau perubahan roll, atau memasuki recovery eksplisit yang menjaga invariant. Uji beberapa roll/item, stock shortage pada item terakhir, concurrent reservation/return serta crash sesudah konsumsi. Tinjau projection balance dan relasi tag/roll pada compensation.

### Prompt develop GN-07/E1

```text
Perbaiki GN-07/E1 pada KNHOST.

Reproduksi: I8-F05: retur FIFO meminta 15 ketika tersedia satu roll 10. approve mengeluarkan roll 10 menjadi returned_supplier, kemudian melempar ValueError stok tidak cukup. Dokumen tetap pending_approval, returned_amount=0 dan tidak ada jurnal. Tidak ada fault injection; penolakan berasal dari hasil konsumsi asli.

Akar: Fungsi konsumsi memutasi roll/movement semampunya lalu mengembalikan consumed. Pemanggil baru memeriksa consumed < requested setelah perubahan tersebut. Ia tidak mengembalikan stok dan tidak menandai operasi parsial untuk dipulihkan. Ini pendalaman GN-07 tentang keamanan konsumsi retur, tidak dihitung ulang sebagai akar cacat independen.

Tugas: Periksa seluruh kebutuhan sebelum mutasi, lalu claim konsumsi secara atomik agar precheck tidak bisa dibatalkan race. Sediakan rollback/resume yang memiliki ownership efek. Gunakan ledger konsumsi per item/roll dan catat kegagalan secara eksplisit. Jangan membuat compensation yang menimpa pemakaian roll oleh transaksi lain.

Acceptance: Stok 10 untuk permintaan 15 harus ditolak tanpa movement atau perubahan roll, atau memasuki recovery eksplisit yang menjaga invariant. Uji beberapa roll/item, stock shortage pada item terakhir, concurrent reservation/return serta crash sesudah konsumsi. Tinjau projection balance dan relasi tag/roll pada compensation.

Gunakan integration_round8.py pada database sintetis. Setelah patch, ganti assertion karakterisasi cacat menjadi ekspektasi invariant benar. Pertahankan kontrol positif, uji semua caller, jelaskan recovery data historis dengan dry-run. Jangan mengubah data produksi otomatis atau menyatakan seluruh Finance lulus dari test ini.
```

## Cakupan dan cabang tersisa

Paket runtime putaran 4–8 kini **59 skenario**, terpisah dari 19 test bawaan dan probe autentikasi 1.353 endpoint. Return service memperoleh bukti normal, reversal, RMA refusal, refund, kegagalan GL dan shortage. Belum mencakup seluruh owner/supplier/warehouse mismatch, konkurensi, partial physical return, semua tax mode, bill matching/AP payment, browser, atau crash recovery. Checklist 29 merupakan baseline rencana yang dapat dilacak; bukan penyebut seluruh kombinasi aplikasi.
