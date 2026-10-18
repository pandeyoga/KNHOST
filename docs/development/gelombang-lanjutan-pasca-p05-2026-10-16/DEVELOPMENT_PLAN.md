# Rencana perbaikan gelombang lanjutan pasca-P05

ERP Kain Nussantara · PT Kubus Teknologi Indonesia · 2026-10-16

## Sasaran dan batas pekerjaan

Menuntaskan kebutuhan yang telah diputuskan dalam diskusi pasca-P05, memvalidasi dampak terhadap fungsi existing, dan melanjutkan sisa P06–P10. Tidak semua catatan client harus menjadi fitur baru: cek reuse, konfigurasi dan alur existing lebih dahulu. Perubahan business rule hanya mengikuti keputusan yang jelas. Hal yang belum dijawab tetap dicatat dan tidak diberi default buatan agent.

Lingkup mencakup custom role, master, Sales/Finance terkait alokasi, Special Order/desain, receiving/MDQ/makloon, QC, sampel/ecer, WMS/logistik, retur, export/rapor, kontrak ERP RFID dan absensi. Pembangunan APK/middleware bukan instruksi paket ini; gunakan dokumentasi workstream middleware terpisah. Audit seluruh repo wave 1–3 tidak otomatis selesai karena plan ini selesai.

## Urutan fase dan keluaran

| Fase | Hasil yang harus bisa direview | Prasyarat |
|---|---|---|
| [L00](phases/L00.md) | Baseline, penyelarasan keputusan, dan kontrak perubahan | — |
| [L01](phases/L01.md) | Custom role, master data, grade, dan konfigurasi visibilitas | L00 |
| [L02](phases/L02.md) | Penjualan, alokasi roll, harga khusus dan konsistensi Finance | L01 |
| [L03](phases/L03.md) | Special Order, Designer, uji kain dan rute supplier/makloon | L01, L02, L04 |
| [L04](phases/L04.md) | Receiving, RFID identity, MD Quality, UOM dan material makloon | L01 |
| [L05](phases/L05.md) | Meja QC dan form inspect tiga sumber | L01, L04 |
| [L06](phases/L06.md) | Sampel, Admin Cutting dan penjualan ecer | L01, L02, L04 |
| [L07](phases/L07.md) | Picking, transit, multi-SO dispatch dan perjalanan antar lokasi | L01, L02, L04 |
| [L08](phases/L08.md) | Menu Retur terpadu, penerimaan, QC dan lineage roll | L01, L04, L05, L07 |
| [L09](phases/L09.md) | Tukar, kompensasi, retur interco dan supplier end-to-end | L02, L08 |
| [L10](phases/L10.md) | Putaway, stock opname, dashboard dan Meja User | L01, L04, L07, L08 |
| [L11](phases/L11.md) | Pusat export, join bisnis dan rapor staf | L01, L02, L03, L05, L09, L10 |
| [L12](phases/L12.md) | Kesiapan ERP untuk middleware Chainway dan UAT tiga perangkat | L01, L04, L07, L10 |
| [L13](phases/L13.md) | Absensi langsung perangkat ke ERP | L00, L01 |
| [L14](phases/L14.md) | Integrasi, migrasi, UAT dan penutupan gelombang | L02, L03, L04, L05, L06, L07, L08, L09, L10, L11, L12, L13 |

Kerjakan satu fase atau bagian independen yang jelas. Sesudah L01, beberapa domain dapat dikembangkan pada branch/worktree sesuai aturan repo, tetapi kontrak roll/owner/UOM/approval harus tetap satu. Nomor fase memberi urutan review; dependency menyatakan syarat validasi penuh. Pending hanya memblok cabang terkait, tidak semua pekerjaan.

## Titik penyerahan tiap fase

1. Jelaskan kondisi existing dan keputusan yang dipakai; pilih reuse, konfigurasi, perbaikan atau fitur tambahan.
2. Serahkan perubahan UI/API/data dan migrasi yang diperlukan, beserta dampak modul lain.
3. Jalankan acceptance fase dengan fixture dan bukti hasil aktual. Tambahkan regression hanya pada perilaku yang berisiko berubah, terutama saldo, kewenangan, concurrency dan lintas modul.
4. Catat commit implementasi dan commit verifikasi. Jika ada perubahan setelah pengujian, evaluasi dampak dan ulangi pengujian terkait.
5. Status menjadi `implemented_pending_validation` setelah kode dan bukti developer lengkap. Reviewer/owner memvalidasi hasil. Bagian pending tidak boleh dihitung selesai.

## Kontrak lintas modul yang harus dijaga

| Data/peristiwa | Sumber kebenaran dan invariant |
|---|---|
| Roll dan EPC | Roll identity unik, EPC identitas tag aktif. Reprint teks tidak membuat roll baru; retag berbeda dari retry jaringan. |
| Qty | Receiving bruto adalah fakta masuk; pemakaian MDQ/cutting/waste, issue, stock balance dan shipment merupakan fakta terpisah yang direkonsiliasi. Yard dan kg tidak dijumlahkan. |
| Owner dan posisi | Pemilik entitas terpisah dari lokasi/gudang/node dan status perjalanan. Shared warehouse tidak menjadi shared pembukuan. |
| Material produksi | Forecast/reserved/issued/at partner/returned/consumed/output actual berbeda; yield estimasi tidak menimpa fisik. |
| Alokasi dan harga | Approval terkait item/versi alokasi yang tepat. Perubahan roll/grade tidak boleh memakai harga approval basi atau membiarkan loading lama tetap sah. |
| Return | Pengajuan, penerimaan, QC, disposition, replacement dan settlement mempunyai referensi dan status masing-masing dalam satu kasus. |
| Finance | Operational exposure, invoice/AR ledger, revenue, cash dan customer credit dibedakan. Gerak transit internal tidak memicu penjualan customer. |
| Export | Grain, relasi, basis tanggal, attribution dan hak kolom menjadi bagian definisi dataset. Preview dan file memakai kontrak yang sama. |
| Device | ACK setelah durable commit; read bukan mutasi bisnis; physical print outcome unknown tidak dicetak ulang otomatis. |

## Jalur besar yang wajib terbukti

- SO normal, genapkan yard/roll, Admin Sales ganti alokasi/harga, request Special Price ulang, customer grade minimum dan Finance hingga pelunasan.
- SO lintas entitas: stok gabungan, pembelian internal, receipt/owner, picking multi-gudang, satu trip multi-SO, transit Jakarta, customer leg, SJ/POD dan rekonsiliasi ledger.
- Special Order multi-produk: existing parent/artwork/customer reference, HOLD/release, paper checklist dan proofing berulang untuk printing, labdip/handfeel sesuai lini lainnya, satu ACC PIC, produksi/SKU final tanpa duplikat.
- Receiving supplier/makloon: OCR/qty per roll, tag, MDQ pilihan roll, pemakaian 0,25 yard termasuk basis kg, putaway; komitmen material, issue, cancel, return/loss dan output actual.
- Sampel hanger/catalogue/standar dan ecer berbayar: komponen catalogue, warna soft berubah, sumber lintas lokasi/entitas, cutting, Admin Cutting dan kirim.
- Retur: sumber roll benar-benar terkirim, Jakarta–Rancamalang QC, identity/child lineage, larangan kirim ke customer asal, replacement atau credit/refund, keep/retur CST dan supplier berdasarkan provenance.
- Opname dengan gerak stok saat hitung, stock dashboards, clickable Meja; export joins/rapor tanpa perkalian nilai atau kebocoran grade.
- Printer–C72–UR300 dengan offline/retry/unknown print nyata; absensi raw punch langsung perangkat dan attendance berdasarkan aturan HR.

## Pending dan batas rilis

Ada 14 topik client aktif (KLR-01–11 dan KLX-01–03), ditambah dataset, review desain, SOP opname, hardware, aturan HR dan UAT. Lihat [register pending](DECISIONS_PENDING.md). Review desain bukan pertanyaan bisnis yang sama diulang; isinya contoh layar/dokumen untuk disetujui sebelum dianggap final.

Cabang cutloss, dasar qty/harga pengganti, discount tanpa physical QC, deadline end-event, formula inspect, dual LOT dan cutoff tidak difinalkan dengan asumsi. Kode independen tetap dapat dibuat. Jika butuh pilot sebagian, sebut “pilot lingkup X”; tidak menutup seluruh gelombang dan tidak menghapus item pending.

Tidak diberikan durasi hari buatan tanpa mengetahui jumlah pengembang dan kesiapan data/perangkat. Estimasi diminta dari agent setelah L00, berdasarkan gap actual, perubahan schema dan ketergantungan luar.

## Tambahan implementasi revisi 1.2 — produksi supplier dan makloon

Wajib baca [rancangan implementasi produksi](IMPLEMENTASI_PRODUKSI_SUPPLIER_MAKLOON.md). LN-033 ditambahkan pada L03 dan LN-143 pada L14, dengan 18 skenario acceptance baru. Total paket: 54 requirement, 214 acceptance, 15 fase; 24 topik pending lama tetap dipertahankan.

Urutan dependency berubah: fondasi L04 harus tervalidasi sebelum L03 ditutup. Pekerjaan desain/round L03 dapat dipersiapkan sebelumnya. Rilis master bukan order produksi; kedua sumber pemenuhan wajib memiliki hubungan dokumen yang benar sampai penerimaan dan pengiriman. Penambahan ini disetujui owner dalam chat 16 Oktober 2026. Semua status lama dipertahankan; requirement baru belum diimplementasikan.

## Revisi 1.3 — hak akses rinci dan pengujian ulang R&D

Wajib baca [rancangan custom role dan revalidasi R&D](CUSTOM_ROLE_DAN_REVALIDASI_RND_REV1_3.md). Tambahan LN-015 (L01) dan LN-034 (L03), 16 acceptance baru; total 56 requirement dan 230 acceptance. Keputusan owner: hasil uji ulang gagal menunggu keputusan PIC; tidak otomatis menghentikan produksi atau membatalkan stok lama. L14 wajib membuktikan integrasi kedua tambahan ini. Hak akses mencakup aktivitas, scope dan field, bukan hanya menu terlihat. Versi ini menggantikan paket 1.2 untuk import baru; status lama dan 24 topik pending tetap dipertahankan.
