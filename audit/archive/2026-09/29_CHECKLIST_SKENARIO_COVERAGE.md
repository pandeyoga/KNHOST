# Checklist baseline pengujian: 96 skenario lintas alur

30 September 2026, `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Dokumen ini membuat lingkup kerja berikutnya dapat dihitung. **96 adalah baseline prioritas audit, bukan seluruh kemungkinan input/state, seluruh test yang dibutuhkan, atau ukuran coverage semua kode.** Setiap kasus luas perlu dipecah lagi saat ditemukan variasi penting. Checklist bukan janji bahwa 96 test cukup untuk menyatakan enterprise-ready.

Matriks direktori di [27](27_MATRIKS_CAKUPAN_FLOW.md) tetap digunakan agar fitur tidak hilang. Status di sini memetakan bukti yang tersedia; belum menggantikan coverage baris/cabang, pengujian UI atau perangkat. Semua temuan merujuk snapshot yang belum diperbaiki, sehingga **cacat teruji berarti audit menemukan kegagalan, bukan aplikasi lulus**.

Ringkasan baseline: 6 kontrol teruji, 15 kasus dengan cacat teruji, 7 parsial, 68 belum diuji sesuai checklist. Kasus teruji berlaku pada fixture yang disebut; seluruh variasi tidak otomatis tercakup. Jumlah kasus checklist berbeda dari 59 skenario harness karena satu kasus dapat membutuhkan beberapa reproduksi dan kontrol.

| ID | Kelompok alur | Skenario/invariant yang harus diverifikasi | Status baseline | Bukti |
|---|---|---|---|---|
| AUTH-01 | Akun dan scope | Login valid/invalid, expiry dan revoke sesi | Belum diuji sesuai checklist | — |
| AUTH-02 | Akun dan scope | User A membaca/mengubah objek B melalui ID, query dan body | Belum diuji sesuai checklist | — |
| AUTH-03 | Akun dan scope | Role custom dengan modul diizinkan tetapi action ditolak | Belum diuji sesuai checklist | — |
| AUTH-04 | Akun dan scope | Entitas diarsipkan saat operasi sedang berjalan | Belum diuji sesuai checklist | — |
| AUTH-05 | Akun dan scope | Dua perubahan permission bersamaan dan invalidasi cache | Belum diuji sesuai checklist | — |
| AUTH-06 | Akun dan scope | UAT pergantian entitas, refresh dan link unduhan | Belum diuji sesuai checklist | — |
| MASTER-01 | Master dan konfigurasi | CRUD produk/supplier/UOM dengan referensi aktif | Belum diuji sesuai checklist | — |
| MASTER-02 | Master dan konfigurasi | Pengaturan entity A tidak mengubah entity B | Cacat teruji | IX07 / I5-SEC01 |
| MASTER-03 | Master dan konfigurasi | Global override → entity override → clear layer | Belum diuji sesuai checklist | — |
| MASTER-04 | Master dan konfigurasi | Alias/satuan tak dikenal ditolak sebelum mutasi | Belum diuji sesuai checklist | — |
| MASTER-05 | Master dan konfigurasi | Archive/merge master yang masih dipakai dokumen | Belum diuji sesuai checklist | — |
| MASTER-06 | Master dan konfigurasi | UAT dropdown, pencarian, paginasi dan pesan scope | Belum diuji sesuai checklist | — |
| GRN-01 | Penerimaan supplier | Manual satu PO/satu roll sampai karantina dan jurnal | Kontrol teruji | I7-C01 |
| GRN-02 | Penerimaan supplier | Cancel counting lalu cancel ulang tanpa efek tambahan | Kontrol teruji | I7-C03/C04 |
| GRN-03 | Penerimaan supplier | Versi basi, entitas asing dan DN duplikat ditolak | Kontrol teruji | I7-C06/C07/C08 |
| GRN-04 | Penerimaan supplier | Receipt multi-line/partial membentuk remainder task benar | Belum diuji sesuai checklist | — |
| GRN-05 | Penerimaan supplier | Closed-period posting gagal lalu pemulihan tanpa stok ganda | Cacat teruji | I7-F01/F02 |
| GRN-06 | Penerimaan supplier | OCR, packing list, timbang dan override discrepancy lewat UI | Belum diuji sesuai checklist | — |
| QC-01 | Inspeksi dan QC | Keputusan sebagian menyisakan task yang dapat dilanjutkan | Cacat teruji | I7-W01/W02 |
| QC-02 | Inspeksi dan QC | Hold melarang konsumsi produksi dan putaway | Cacat teruji | I6-P03; putaway kontrol I6-C04 |
| QC-03 | Inspeksi dan QC | Finish inspeksi → reopen memperbarui milestone retur | Cacat teruji | I5-WM02 |
| QC-04 | Inspeksi dan QC | Accept/reject semua qty lalu supplier return sampai AP | Belum diuji sesuai checklist | — |
| QC-05 | Inspeksi dan QC | Dua inspector memutuskan qty yang sama bersamaan | Belum diuji sesuai checklist | — |
| QC-06 | Inspeksi dan QC | UAT sampling, hold release, sisa karantina dan genealogy | Belum diuji sesuai checklist | — |
| PRET-01 | Retur pembelian | Direct non-PPN mengubah stok, PO dan jurnal konsisten | Kontrol teruji | I8-C01 |
| PRET-02 | Retur pembelian | Reversal lalu retry memulihkan stok/AP dan net akun nol | Kontrol teruji | I8-C02/C03 |
| PRET-03 | Retur pembelian | Retur dengan PPN: AP credit dan cash refund cocok dokumen | Cacat teruji | I8-F01/F02 |
| PRET-04 | Retur pembelian | RMA ditolak supplier lalu goods_back tanpa settlement | Kontrol teruji | I8-C04 |
| PRET-05 | Retur pembelian | Shortage/closed period ditolak atau dapat dipulihkan aman | Cacat teruji | I8-F03/F04/F05 |
| PRET-06 | Retur pembelian | Retur partial/multi-item, owner mismatch dan concurrent approve | Belum diuji sesuai checklist | — |
| PROD-01 | Produksi dan makloon | BOM dirilis tidak berubah saat master BOM direvisi | Cacat teruji | I6-P04 |
| PROD-02 | Produksi dan makloon | Complete gagal GL lalu retry tidak menggandakan hasil | Cacat teruji | I6-P01/P02 |
| PROD-03 | Produksi dan makloon | Bahan held/reserved tidak dikonsumsi tanpa otorisasi | Parsial | Hold I6-P03; reserved belum diuji |
| PROD-04 | Produksi dan makloon | Multi-komponen shortage pada item akhir tanpa efek parsial | Belum diuji sesuai checklist | — |
| PROD-05 | Produksi dan makloon | Makloon issue→partial receipt→final receipt→biaya→retur | Belum diuji sesuai checklist | — |
| PROD-06 | Produksi dan makloon | UAT operator dan recovery sesudah worker/process mati | Belum diuji sesuai checklist | — |
| INV-01 | Stok, transfer dan count | Split serentak mempertahankan total panjang/nilai | Parsial | I4-WM01; nilai total semua interleaving belum diuji |
| INV-02 | Stok, transfer dan count | Transfer antarbin/gudang memiliki lokasi asal/tujuan tepat | Belum diuji sesuai checklist | — |
| INV-03 | Stok, transfer dan count | Cycle count menjaga cutoff, recount dan approval adjustment | Belum diuji sesuai checklist | — |
| INV-04 | Stok, transfer dan count | Antarentitas transfer/retur direkonsiliasi kedua buku | Belum diuji sesuai checklist | — |
| INV-05 | Stok, transfer dan count | Rebuild balance tidak menimpa proyeksi dengan snapshot lama | Belum diuji sesuai checklist | — |
| INV-06 | Stok, transfer dan count | UAT scan lokasi, exception, partial quantity dan undo | Belum diuji sesuai checklist | — |
| RFID-01 | RFID dan gate | Encode→ZPL→raw EPC ingest memakai identitas konsisten | Parsial | I4-RF01 simulasi software; printer belum |
| RFID-02 | RFID dan gate | Gate memvalidasi dokumen, status, roll dan tujuan | Parsial | I4-RF02 cabang putaway; seluruh gate belum |
| RFID-03 | RFID dan gate | Loading tidak clean jika roll wajib belum bertag | Cacat teruji | I4-RF04 |
| RFID-04 | RFID dan gate | Gagal attach/undo roll tidak meninggalkan tag aktif yatim | Cacat teruji | I6-R01/C03 |
| RFID-05 | RFID dan gate | Offline replay, duplicate read, passage direction dan reconnect | Belum diuji sesuai checklist | — |
| RFID-06 | RFID dan gate | UAT perangkat reader/printer/PLC dan alarm gate fisik | Belum diuji sesuai checklist | — |
| SALE-01 | Sales, POS dan logistik | Order→allocation→pick→ship→invoice pada dataset acuan | Belum diuji sesuai checklist | — |
| SALE-02 | Sales, POS dan logistik | POS split tender, shift close, void dan refund | Belum diuji sesuai checklist | — |
| SALE-03 | Sales, POS dan logistik | Partial shipment/cancel tidak melepas reservasi salah | Belum diuji sesuai checklist | — |
| SALE-04 | Sales, POS dan logistik | Store credit tidak melebihi request/balance atau lintas owner | Parsial | I4-FN01; scope dibuktikan harness lama |
| SALE-05 | Sales, POS dan logistik | Return/refund/reversal sesuai item, pajak dan receipt asli | Belum diuji sesuai checklist | — |
| SALE-06 | Sales, POS dan logistik | UAT backorder, delivery proof dan recovery transaksi gagal | Belum diuji sesuai checklist | — |
| APAR-01 | AP, AR, bank dan petty cash | Bill matching receipt/PO lalu bayar AP dan reversal | Belum diuji sesuai checklist | — |
| APAR-02 | AP, AR, bank dan petty cash | AR receipt allocation/deposit/plan reschedule terjaga | Belum diuji sesuai checklist | — |
| APAR-03 | AP, AR, bank dan petty cash | Bank match menolak arah/akun salah dan alokasi ganda | Cacat teruji | I4-FN02/FN03 |
| APAR-04 | AP, AR, bank dan petty cash | Advance→payout→settlement→refund tanpa retry ganda | Belum diuji sesuai checklist | — |
| APAR-05 | AP, AR, bank dan petty cash | Failed GL mempertahankan recovery state yang konsisten | Belum diuji sesuai checklist | — |
| APAR-06 | AP, AR, bank dan petty cash | UAT rekonsiliasi, bukti transfer dan laporan saldo | Belum diuji sesuai checklist | — |
| GL-01 | Akuntansi dan laporan | Opening balance→posting semua sumber→trial balance | Belum diuji sesuai checklist | — |
| GL-02 | Akuntansi dan laporan | Close periode memblokir posting/void tanpa otorisasi | Belum diuji sesuai checklist | — |
| GL-03 | Akuntansi dan laporan | Approve/reject unlock bersamaan hanya satu keputusan menang | Cacat teruji | I5-FN01 |
| GL-04 | Akuntansi dan laporan | User A tidak membaca/menyetujui unlock B | Cacat teruji | I5-SEC02/SEC03 |
| GL-05 | Akuntansi dan laporan | Consolidation/interco elimination dan multi-periode rekonsiliasi | Belum diuji sesuai checklist | — |
| GL-06 | Akuntansi dan laporan | UAT laporan besar, export, tanggal WIB/UTC dan rounding | Belum diuji sesuai checklist | — |
| HR-01 | HR dan payroll | Leave overlap/cancel/cross-year menjaga entitlement dan attendance | Parsial | I4-HR01–04; seluruh variasi belum |
| HR-02 | HR dan payroll | Shift overnight dan approval overtime dihitung tepat | Cacat teruji | I4-HR05/HR06 |
| HR-03 | HR dan payroll | Payroll satu periode sampai GL dan pembayaran | Belum diuji sesuai checklist | — |
| HR-04 | HR dan payroll | Year-end/termination tax/BPJS dengan dataset acuan | Belum diuji sesuai checklist | — |
| HR-05 | HR dan payroll | Payroll void/retry dan perubahan setting lintas entitas | Belum diuji sesuai checklist | — |
| HR-06 | HR dan payroll | UAT employee self-service, akses PII dan approval manager | Belum diuji sesuai checklist | — |
| COMM-01 | CRM, marketing dan pricing | Lead→customer→order menjaga owner dan duplicate merge | Belum diuji sesuai checklist | — |
| COMM-02 | CRM, marketing dan pricing | Campaign metrics partial update menjaga nilai sebelumnya | Belum diuji sesuai checklist | — |
| COMM-03 | CRM, marketing dan pricing | Special price approval, expiry dan scope order vs standing | Belum diuji sesuai checklist | — |
| COMM-04 | CRM, marketing dan pricing | Commission/campaign cost sampai settlement dan reversal | Belum diuji sesuai checklist | — |
| COMM-05 | CRM, marketing dan pricing | Concurrent edit/delete/import menjaga sumber data kanonik | Belum diuji sesuai checklist | — |
| COMM-06 | CRM, marketing dan pricing | UAT dashboard role, pencarian, export dan empty state | Belum diuji sesuai checklist | — |
| DESIGN-01 | Design, R&D dan sample | Request→assignment→revision→approval→produksi | Belum diuji sesuai checklist | — |
| DESIGN-02 | Design, R&D dan sample | Sample versi yang disetujui menjadi acuan QC tepat | Belum diuji sesuai checklist | — |
| DESIGN-03 | Design, R&D dan sample | Cancel/reopen menjaga dokumen turunan dan file | Belum diuji sesuai checklist | — |
| DESIGN-04 | Design, R&D dan sample | Pemindahan designer/role tidak membocorkan file/PII | Belum diuji sesuai checklist | — |
| DESIGN-05 | Design, R&D dan sample | Biaya trial/sample dan stock sample direkonsiliasi | Belum diuji sesuai checklist | — |
| DESIGN-06 | Design, R&D dan sample | UAT upload, preview, revisi, mobile dan notifikasi | Belum diuji sesuai checklist | — |
| DOC-01 | Dokumen, approval dan AI | E-sign metadata/version/sumber dokumen terikat owner | Parsial | I4-SEC01 metadata; seluruh versi belum |
| DOC-02 | Dokumen, approval dan AI | PDF/Excel konsisten dengan source dan hak akses | Belum diuji sesuai checklist | — |
| DOC-03 | Dokumen, approval dan AI | Approval berjenjang/delegasi menolak stale decision | Belum diuji sesuai checklist | — |
| DOC-04 | Dokumen, approval dan AI | Tanya/analytics/export/scheduled report menjaga scope | Belum diuji sesuai checklist | — |
| DOC-05 | Dokumen, approval dan AI | Notifikasi/digest hanya kepada penerima yang sah | Belum diuji sesuai checklist | — |
| DOC-06 | Dokumen, approval dan AI | UAT file rusak, timeout, hasil kosong dan navigasi dokumen | Belum diuji sesuai checklist | — |
| OPS-01 | Operasional lintas modul | Bootstrap dan seluruh indeks deployment tervalidasi | Belum diuji sesuai checklist | — |
| OPS-02 | Operasional lintas modul | Scheduler restart/retry/outbox tidak mengulang efek bisnis | Belum diuji sesuai checklist | — |
| OPS-03 | Operasional lintas modul | Import/migration dapat dilanjutkan dan direkonsiliasi | Belum diuji sesuai checklist | — |
| OPS-04 | Operasional lintas modul | Crash pada setiap tahap mutasi memiliki recovery terukur | Belum diuji sesuai checklist | — |
| OPS-05 | Operasional lintas modul | Backup/restore dan data historis mempertahankan referensi | Belum diuji sesuai checklist | — |
| OPS-06 | Operasional lintas modul | UAT seluruh shell desktop/mobile dan integrasi eksternal | Belum diuji sesuai checklist | — |

## Aturan menutup kasus

Kasus dicatat telah diuji hanya dengan hasil tersimpan, data/role/state yang jelas dan assertion terhadap efek bisnis. Jika ada bug, penutupan pengujian bukan sign-off kelayakan; tiket perbaikan dan regression test tetap terbuka. Kasus yang mencakup beberapa cabang hanya diberi status parsial jika salah satu belum diuji. Uji mock/AST tetap dilabeli terpisah dari Mongo/HTTP.

Untuk milestone lebih luas, seluruh variasi yang disepakati pada keluarga kasus harus diuji, bug blocker diperbaiki/divalidasi ulang, dan sumber angka Finance direkonsiliasi. Perangkat fisik serta dataset akuntansi acuan membutuhkan lingkungan yang sesuai. Pekerjaan lokal lainnya tetap dapat diteruskan tanpa perangkat tersebut.
