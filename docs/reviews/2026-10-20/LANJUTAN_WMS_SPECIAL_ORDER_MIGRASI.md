# Hasil lanjutan — WMS, Special Order, migrasi, dan pemulihan retur

Acuan tetap main `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`. Pengujian dilakukan lokal, tanpa perubahan kode aplikasi atau push.

## Hasil yang sekarang dapat dibuktikan

### WMS: 27 kasus unik lulus setelah fixture dilengkapi

Tiga tes stock tree dan delapan tes OPS-01 lulus di `evidence/wms-run/`. Dua modul lain semula terhambat site, gudang shared dan zona QC yang belum ada. Setelah struktur itu disiapkan dari generator demo repository, pengulangan menghasilkan 16 tes lulus (`evidence/wms-extra-run.xml`). Total akhir empat modul tersebut adalah 27 kasus unik lulus; angka pengulangan tidak dijumlahkan dua kali.

Yang diperiksa mencakup:

- Total stok bertingkat dan pemisahan yard/kg serta pemilik.
- Stok karantina tidak menjadi stok available.
- Alamat lengkap, perubahan struktur dengan alasan migrasi, dan kapasitas di bawah isi.
- Aturan woven-only pada gudang shared menolak knit.
- Putaway tanpa membuat jurnal penjualan/pembelian dan tanpa menggandakan total stok.
- Scan duplikat, roll hilang, salah alamat, kode tidak dikenal dan tag bermasalah.
- Hitung ulang roll hilang sebelum write-off; perlindungan roll yang masih dialokasikan.
- Pemisahan koreksi rak dalam gudang dari transfer antar-gudang.
- Hak counter versus approver, perubahan stok setelah scan, dan sejumlah kondisi race.
- Konsistensi beberapa hitungan Meja Saya dan penghilangan notifikasi duplikat.

**Batas:** semua ini fixture lokal. Temuan AUD-WMS-01 tentang kegagalan jurnal di tengah opname tetap berlaku. Lulus tes normal tidak menutup temuan recovery. Penelusuran visual semua layar dan UAT handheld belum selesai.

### Special Order: 18 kasus unik lulus, dry-run migrasi juga dapat dijalankan

Dua modul fulfillment menghasilkan 17 passed dan dua kegagalan awal. Pengujian guard produk belum dirilis kemudian lulus setelah varian kedua ditambahkan. Tes wrapper migrasi masih memanggil executable `python` berbeda yang tidak memiliki dotenv; ini masalah lingkungan tes. Skrip migrasi asli dijalankan langsung memakai interpreter audit yang benar dan berhasil menghasilkan JSON dry-run (`evidence/migration-dry-run.json`). Jangan mengubah hasil wrapper menjadi pass.

Kasus yang telah lulus mencakup rute campuran per item, default supplier/makloon/both, alasan penyimpangan, PR ke PO/MKO, guard harga belum terkunci, guard produk belum dirilis, sejumlah retry/concurrency dan pembatasan izin. Bukti: `so-run.xml` dan `so-extra-run.xml`.

**Batas penting:** fixture tes repository memasukkan hasil R&D yang sudah diputus serta harga terkunci langsung ke database. Maka hasil tersebut membuktikan lapisan realisasi pemenuhan, bukan seluruh flow dari desain, approval customer, R&D, penerimaan, Finance sampai pengiriman. AUD-SO-01 tetap terbuka.

### Export volume: pengujian pembagian sheet lulus

Sebanyak 5.001 movement sintetis ditambahkan khusus pengujian, kemudian dihapus kembali. Tes export XLSX dengan 5.000 baris per sheet berhasil: written rows cocok dengan sumber, jumlah partisi sesuai, dan seluruh baris worksheet terhitung. Bukti: `export-volume.xml`, `export-volume-fixture.json`.

Ini mengatasi hambatan fixture pada tes volume sebelumnya. Tidak menutup AUD-EXP-01 atau AUD-EXP-02: masalah izin kolom grouping dan konsistensi ketika sumber berubah tetap terpisah. Pengujian tidak menggunakan satu juta baris atau membuktikan performa produksi pada volume tersebut.

## Tiga temuan tambahan

1. **AUD-MIG-01:** apply migrasi melaporkan matched untuk order ber-fulfillment kosong tetapi tidak menulis relasinya.
2. **AUD-MIG-02:** rollback dapat menghapus state dan relasi operasional yang sudah berubah setelah migrasi.
3. **AUD-RET-01:** pembuangan BS yang gagal pada pencatatan movement meninggalkan jurnal dan stok sudah berubah, lalu retry ditolak.

Detail reproduksi dan perbaikan berada di `TEMUAN_TERVERIFIKASI.md`. Total catatan terbukti kini 11. Observasi kontrak terminated tetap terpisah karena masih membutuhkan kepastian aturan bisnis.

## Status keseluruhan

Audit belum ditutup. Cakupan runtime bertambah nyata, tetapi seluruh rantai lintas modul, UI per role, migrasi produksi dan perangkat fisik belum terverifikasi penuh. Tidak ada angka persentase cakupan kode yang diberikan karena pengujian ini belum mengumpulkan coverage instrumentasi baris/cabang seluruh aplikasi.
