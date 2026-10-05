> Pembaruan: [retur pembelian, refund dan reversal — sembilan skenario beserta prompt](28_AUDIT_RETUR_BELI_DAN_PROMPT.md). [Checklist baseline 96 skenario](29_CHECKLIST_SKENARIO_COVERAGE.md). Total runtime sekarang 59 skenario; belum seluruh flow tercakup.

# Matriks cakupan: semua kelompok fitur harus tetap terlihat

30 September 2026; snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Ini register pekerjaan audit, **bukan sertifikasi semua kode telah diperiksa atau semua alur lulus**.

## Cara membaca

Kolom bukti menunjuk nomor laporan yang berisi eksekusi integrasi terarah. Tanda — berarti belum dipetakan ke bukti integrasi paket 18–26; bukan berarti source belum pernah dibaca pada audit awal. Bukti AST/model database dari laporan awal tetap berguna, tetapi tidak diubah menjadi klaim integrasi nyata.

Ada **35 direktori langsung** pada frontend/src/features di snapshot ini. Itu hitungan folder dengan metode eksplisit, bukan jumlah seluruh kapabilitas aplikasi atau penyebut coverage. Komponen bersama, frontend lain, backend-only, jobs, migrations, deployment dan pengujian perangkat perlu register terpisah. Angka kelompok fitur dalam laporan lama tidak dipakai untuk menghitung persentase selesai.

**Tidak ada baris yang diberi status seluruh flow selesai.** Semua UAT browser masih terbuka; inspeksi source UI bukan UAT. Probe 1.353 endpoint menguji batas autentikasi, tidak mencakup semua payload/state/business outcome.

| Kelompok source | Laporan bukti integrasi | Lingkup yang benar-benar disentuh | Cabang utama yang masih terbuka |
|---|---|---|---|
| `admin` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Matriks role/user/session, custom permission dan lifecycle entitas |
| `approvals` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Approve/reject/delegasi/escalation bersama dan seluruh terminal state |
| `catalog` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | CRUD master, alias UOM, merge/archive dan referensi lintas modul |
| `costing` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Landed cost, WAC, pembagian biaya, rerun/reversal |
| `crm` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Lead→customer, import/merge, aktivitas dan akses objek |
| `design` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Request→assignment→revision→approval→production handoff |
| `designer` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Antrean tugas, upload revisi, perubahan penugasan dan akses file |
| `desks` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Agregasi antrean per role/entitas dan navigasi ke tindakan |
| `documents` | 19 | Metadata e-sign lintas entitas | Signature version, invalidation, PDF final, upload/download dan expiry |
| `finance` | 18, 22, 26 | Store credit, bank match, period decision, posting GRN; belum rekonsiliasi buku lengkap | AP/AR settlement, reversal, laporan GL, closing dan konsolidasi pada dataset acuan |
| `home` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Kartu ringkasan dengan fixture lintas entitas dan status kosong |
| `hr` | 19 | Cuti, attendance, overtime dan setting payroll terarah | Payroll periode penuh, koreksi/void, pajak/BPJS dan rekonsiliasi bank |
| `inspections` | 22, 24, 26 | Finish/reopen, QC hold dan keputusan sebagian | Sampling policy, multi-SPK, release hold, return/disposal dan retry |
| `internal_requests` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Request→approval→fulfillment→cancel dan scope |
| `inventory` | 18, 24, 26 | Roll, split, valuation delta, receiving/quarantine | Count approval, transfer, reserved stock, ancestry dan valuation seluruh status |
| `logistics` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Shipment, partial delivery, proof of delivery, return dan biaya |
| `manager` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Inbox persetujuan, scope, stale action dan indikator keputusan |
| `marketing` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Campaign, metrics partial update, biaya dan attribution |
| `mobile` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Responsive flows, scan/focus, koneksi putus, permission dan recovery |
| `orders` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Lifecycle order dan lintas modul sampai settlement |
| `pdf` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Seluruh template, page break, nilai/tanggal, akses dan versi dokumen |
| `pettycash` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Advance→pencairan→settlement→refund dengan retry dan GL |
| `pos` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Sale, tender campuran, void, retur, cash shift dan sinkronisasi |
| `pricing` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Harga efektif, override, expiry, quantity break dan approval |
| `production` | 24 | BOM→WO→release→complete, gagal GL/retry, QC hold | Concurrent complete, multi-komponen, cancellation race dan crash recovery |
| `purchasing` | 26 | PO received_qty diperiksa dari lifecycle GRN; PO awal fixture | Pembuatan/persetujuan PO, partial receipt, bill matching, retur dan pembayaran AP |
| `rfid` | 18, 24 | Encode/ingest, device heartbeat, gate decision, loading, kompensasi tag | Replay/reconnect, portal direction, passage, PLC, printer dan hardware UAT |
| `rnd` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Request/sample, trial, cost dan handoff produksi |
| `sales` | 18, 22 | Store credit serta proyeksi milestone retur; belum order-to-cash | Order→alokasi→pick→ship→invoice→receipt→return/refund lengkap |
| `sales_admin` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Validasi order, perubahan harga/kredit, partial fulfillment |
| `samples` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Sample approval, versi, tag, custody dan linkage QC |
| `settings` | 19, 22 | Scope pengaturan payroll dan Finance | Seluruh configuration keys, inheritance, clear override dan cache invalidation |
| `tanya` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Scope query, agregat, export, schedule dan recipient |
| `transfers` | — | Belum ada bukti integrasi terarah yang dipetakan pada paket 18–26 | Transfer antarbin/gudang/entitas, in-transit, accept dan reversal |
| `wms` | 18, 24, 26 | Split, loading, penerimaan manual, cancel, QC parsial | Multi-line receipt, putaway→pick→ship, partial/reversal dan recovery |

## Alur lintas modul dan syarat selesai

| Alur | Bukti saat ini | Syarat penutupan audit |
|---|---|---|
| Procure-to-stock-to-GL | GRN manual satu baris/satu roll, cancel/retry, period failure; PO/task awal fixture | Create/approve PO, receiving multi-satuan/partial, QC dan putaway, return, AP matching/payment, ledger reconciliation |
| Order-to-cash | Temuan dan reproduksi terarah pada allocation/loading/credit/return | Dataset utuh order→shipment→invoice→receipt→refund dengan seluruh dokumen/saldo diperiksa |
| Manufacture-to-stock | BOM/WO, konsumsi/output/GL retry dan hold | Frozen recipe, multi-input, concurrent changes, recovery/crash, overhead dan stok direkonsiliasi |
| RFID/gate | Jalur software encode, ingest, keputusan gate dan lifecycle tag terarah | Reader/printer/PLC, arah passage, overlap, stray reads, offline replay, alarm dan audit fisik |
| Record-to-report | Posting dan guard tertentu; banyak cacat terkonfirmasi | Opening→seluruh sumber jurnal→reversal→closing→laporan, imbalance/orphan checks dan periode acuan |
| Hire-to-pay | Leave/attendance/overtime sebagian | Payroll penuh, tax/BPJS tervalidasi, adjustment, bank payment dan GL |

## Komponen di luar direktori fitur

Masih perlu penutupan eksplisit untuk scheduler/worker; queue/retry/outbox; import/migration; indeks dan transaksi deployment; cache; backup/restore; upload/file export; permissions seluruh objek; API integrations; notifications/recipient; konfigurasi lintas entitas; serta kesesuaian runtime dependency produksi. Import 246 modul berhasil tidak memverifikasi perilaku komponen tersebut.

## Bukti yang dapat dihitung, tanpa persentase semu

Paket runtime putaran 4–7: 50 skenario terarah. Test bawaan terpilih: 19 lulus. Router: 1.353 template mendapat probe autentikasi. Daftar 2.133 fungsi bernama test adalah inventaris, bukan jumlah test yang telah dieksekusi. Angka trace laporan 21 hanya menunjukkan setidaknya satu baris terlewati pada putaran 4; tidak menyatakan semua cabang fungsi teruji.

Kebutuhan lingkungan yang belum tersedia dalam bukti saat ini: perangkat RFID/gate fisik dan dataset akuntansi acuan yang disetujui pemilik proses. Sisa pengujian lokal tidak dinyatakan terblokir oleh kebutuhan perangkat tersebut; keduanya merupakan pekerjaan berbeda.
