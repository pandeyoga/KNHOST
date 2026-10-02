> Pembaruan: [retur pembelian, refund dan reversal — sembilan skenario beserta prompt](28_AUDIT_RETUR_BELI_DAN_PROMPT.md). [Checklist baseline 96 skenario](29_CHECKLIST_SKENARIO_COVERAGE.md). Total runtime sekarang 59 skenario; belum seluruh flow tercakup.

> Pembaruan GRN/QC: [12 skenario dan dua temuan beserta prompt](26_AUDIT_GRN_FINANCE_QC_DAN_PROMPT.md). [Matriks 35 direktori fitur dan alur lintas modul](27_MATRIKS_CAKUPAN_FLOW.md). Seluruh flow belum dinyatakan tercakup.

> Pembaruan 30 September: [audit produksi, penerimaan dan RFID](24_AUDIT_PRODUKSI_PENERIMAAN_RFID.md), sepuluh skenario tambahan, tiga temuan tambahan dan pendalaman GN-06. [Prompt perbaikan](25_PROMPT_PRODUKSI_PENERIMAAN_RFID.md). Belum seluruh flow teruji.

> Pembaruan putaran 5: [kontrol periode, scope dan inspeksi](22_AUDIT_PERIODE_SCOPE_DAN_INSPEKSI.md), empat cacat baru terkonfirmasi, satu gap kebijakan, sembilan skenario tambahan dan 19 test bawaan lulus. [Prompt perbaikan](23_PROMPT_PERBAIKAN_PERIODE_SCOPE_INSPEKSI.md).

> **Pembaruan integrasi:** MongoDB lokal dan ASGI sudah dijalankan untuk skenario pada [18](18_HASIL_PENGUJIAN_INTEGRASI.md); lihat [21](21_CAKUPAN_RUNTIME_DAN_ENDPOINT.md) untuk endpoint dan baris yang dieksekusi. Status belum menyeluruh pada tabel ini tetap berlaku untuk varian yang belum diuji.

# Status cakupan dan pekerjaan yang belum selesai

Snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`, tanggal perluasan 29 September 2026.

**Jawaban langsung: belum semua kode dan semua flow telah direview mendalam ataupun diuji end-to-end.** Register seluruh berkas adalah cakupan inventaris, bukan bukti seluruh perilaku benar. Kalimat pada laporan04 lama yang menyamakan “semua tercover” dengan peta/register telah dikoreksi. Pengujian tambahan sekarang menemukan cacat nyata pada flow di luar fokus awal, sehingga pembatasan ini material.

## Apa yang sudah bertambah

- 13 temuan terurai dengan lokasi kode, pemicu, dampak lintas flow dan acceptance criteria dalam [13](13_AUDIT_LANJUTAN_FLOW.md).
- 14 skenario baru: 13 reproduksi perilaku cacat dan1 kontrol benar; dua skenario membuktikan satu isu e-sign. Temuan concurrency makloon masih analisis statis. Lihat [16](16_BUKTI_UJI_LANJUTAN.md).
- Registrasi router ditelusuri statis: 135 router, 1353 endpoint HTTP pada router. Pemetaan prefix dan urutan tidak menemukan kandidat shadow pada checker terbatas (0). Ini bukan hasil startup FastAPI/OpenAPI, bukan hitungan WebSocket/server route di luar router, dan bukan bukti semua endpoint aman.
- Register backend (termasuk tests dan helper) sekarang sampai tingkat 8749 fungsi/metode, dengan penanda kedalaman dan write calls langsung. Ada 34 fungsi dipilih oleh harness baru dan 30 fungsi tambahan diberi penanda pembacaan terbatas. Di antaranya 3103 fungsi/metode berada pada services dan1564 pada routers; sisanya termasuk tests, scripts dan helper. Angka ini bukan jumlah semua fungsi yang pernah dibaca, bukan branch coverage, dan bukan jumlah seluruh fungsi frontend. Lihat [17](17_REGISTER_FUNGSI_BACKEND.md).
- Baseline audit lama tetap1857 berkas sumber terinventarisasi, 1353 decorator endpoint,36 kelompok fitur frontend. Seluruh65 temuan awal sudah diberi verdict; ini tidak sama dengan seluruh endpoint telah diverifikasi.

## Tingkat bukti yang harus dibedakan

| Tingkat | Makna | Status |
|---|---|---|
| Inventaris | Berkas/route/fungsi tercatat | Luas;05 dan17 |
| Pemeriksaan struktur | Syntax, mounting, pencarian mutation/scope | Luas tetapi tidak membuktikan perilaku |
| Telusur statis | Baca predicate, caller, efek samping dan downstream | Selektif per flow/temuan |
| Reproduksi fungsi | Jalankan fungsi asli dengan fixture/model terkontrol | Ada pada06/12/16; bukan DB asli |
| Integrasi aplikasi | HTTP+auth+Mongo+worker dengan fixture utuh | Belum dilakukan menyeluruh |
| UI/UAT | Interaksi aktual tiap persona serta recovery | Belum dilakukan seluruh layar |
| Perangkat/lapangan | Reader, antena, gate, PLC, printer dan lingkungan RF | Belum dilakukan |
| Rekonsiliasi data riil | Opening→transaksi→closing, subledger→GL→bank | Belum dilakukan |

Tidak tersedia denominator “seluruh flow” yang tervalidasi. Kombinasi status, owner, UOM, partial, retry, cancellation, permission dan konkurensi menghasilkan banyak varian; jumlah endpoint tidak dapat dijadikan persentase coverage bisnis.

## Matriks flow: hasil dan batas yang masih terbuka

| Rumpun flow | Bukti yang tersedia | Varian yang belum dapat dinyatakan selesai |
|---|---|---|
| RFID commissioning/encode/verify/retag | RF/AX dan blueprint10; fungsi terpilih diuji | Reader/printer nyata, lock tag, duplicate EPC lapangan, retag ketika offline |
| RFID gate/loading/count | RF/AX, review2, blueprint10 | Antena bersebelahan, arah bolak-balik, reader reconnect, duplicate events multi-device, PLC interlock, blind count UAT |
| WMS inbound/QC/putaway | WM/RF/AX; scope, PA, transfer, lifecycle ditelusuri | ASN over/short receipt, semua QC override, returns intake, semua role/bypass API |
| WMS split/reserve/pick/dispatch | WM/AX; kuantitas dan identitas diuji terisolasi | Mongo concurrency, seluruh partial/backorder/cancel/repick/reverse combinations |
| Makloon/GRN | Jalur final receive, partial staging, claim, bill, output, GL ditelusuri;CX-13 | Race asli final receipt, semua kontrak/tarif/UOM, jasa murni, retur subcon, multi-stage reverse |
| Manufacturing/BOM | GN terdahulu; consume/complete dan plan | Capacity/scheduling, yield/byproduct real, rework/scrap, worker crash lintas bahan |
| Delivery/POD/pickup | Transition+parent callback diperluas;CX-12 | Semua delivery API, fleet double-booking, multiple SJ, cancellation/replacement dan UI sopir |
| SO/pricing/discount/return | Lama ditambahCX-11 | Semua kombinasi tax/discount/currency/UOM, refund dan exchange, return eligible per shipment |
| Store credit/AR | CX-01–03+kontrol validator | Refund cash, expiry kredit, adjust bersamaan redeem, seluruh kanal pembayaran dan HTTP ownership tests |
| Cash advance/petty cash | CX-04–05; posting settlement dibaca | Currency, attachment fraud checks, employee termination, historical recovery dan seluruh approval role |
| Bank reconciliation | CX-06–07 | Auto/group/unmatch/holding/import duplicate secara utuh, split lintas currency, match-vs-pay concurrency |
| Payment plan | CX-08 | Semua receipt amendment/reversal dan denda kalender, migrasi seq lama, multi-plan policy |
| GL/COA/valuation/assets/closing | FN dan review2 | Buku riil, account mapping lengkap, closing-open races Mongo, saldo awal/migrasi/restatement |
| Intercompany/consolidation | GN/FN ditambahCX-09 | Semua pair settlement, tax intercompany, transfer profit, ownership perimeter lengkap, historical snapshot |
| HR/payroll | HR lama; run submit/approve/post/pay dan config reader/writer diperiksa statis | Kalkulasi tiap komponen, regulasi terbaru, attendance→payroll, cuti/overtime, double-run dan payroll payment fault injection |
| Approvals/config | Rules CRUD dibaca; source menjelaskan backlog read-only | Seluruh threshold-gap/overlap, role escalation, approve-vs-reject race di setiap jenis dokumen |
| R&D/design/samples | GN lama; beberapa material/owner flow | Seluruh request→design→sample→customer approval→SKU, version approval dan gallery access |
| CRM/marketing/omnichannel | GN lama pada scope/ownership | Delivery webhook, consent/config, dedup, retry dan provider integration nyata |
| POS | Scope agregasi lama | Offline queue, receipt/refund, cash drawer, price override dan shift reconciliation |
| E-sign/PDF | CX-10; OTP claim positif | HTTP owner/actor binding, template setiap jenis dokumen, render artifact final, key/OTP provider lifecycle |
| Auth/users/storage | Login/session/storage guards ditelusuri terbatas | Matriks permission seluruh endpoint, XSS/CSRF paths, reset/revocation, seluruh upload callers, proxy configuration |
| Admin/settings/integrations/AI/notification | Inventaris dan temuan GN terkait | Semua external callbacks, retry/outbox, secret lifecycle, AI tool permissions dan broadcast audience |
| Dashboard/desk/home/mobile/report | Inventaris dan beberapa aggregation/caller | Seluruh filter/pagination/cap, loading/error/empty states, konsistensi KPI terhadap source, responsif dan aksesibilitas |

## Kandidat tindak lanjut: belum dihitung sebagai temuan terkonfirmasi

- HR settings: GET memakai entity overlay, PUT router payroll menulis scope hr global. Kontrak edit-global vs edit-entitas serta caller UI perlu dituntaskan sebelum menyimpulkan celah akses; statutory rate belum divalidasi terhadap aturan terkini.
- E-sign: request/signatures menggunakan ID sumber tanpa konteks objek pada service; perlu uji HTTP dengan user A dan source B untuk menutup analisis generic middleware/permission. Respons list_signatures mengecualikan signature_b64; jangan mengeklaim gambar tanda tangan bocor melalui endpoint itu.
- Bank line dipakai untuk membayar kontrabon: urutan payment sebelum manual match perlu fault/concurrency fixture lintas dua dokumen; claim pada kontrabon sendiri tidak otomatis mengunci bank line.
- Makloon issue, allocation delivery dan payroll create: pola read→write perlu diuji dengan barrier asli dan indeks database aktual; keberadaan komentar atomic bukan bukti aman maupun bukti bug.

## Kriteria penutupan audit menyeluruh

1. Untuk setiap command bisnis, catat owner/input/state/invariant, side effects dan terminal state; hubungkan API serta UI yang memanggilnya. Setiap flow mempunyai happy path, invalid transition, authorization, retry/crash, concurrency, cancellation/reversal dan partial completion yang relevan.
2. Jalankan matriks tersebut pada fixture Mongo terpisah, dengan indeks yang sama dengan deployment. Jangan memakai produksi untuk fault injection. Simpan hasil per skenario, bukan hanya total test lulus.
3. UAT per persona: purchasing, QC, receiving, picker, gate operator, driver, sales, finance, approver dan administrator; jejak error dan recovery sama penting dengan happy path.
4. Uji perangkat RFID/gate pada layout fisik proyek; baca gate bukan release authorization sampai bukti fisik/identitas/task/QC/owner cocok.
5. Rekonsiliasi finance dengan dataset acuan: kuantitas, valuation, AR/AP, customer credit, advances, cash/bank, GL, laporan dan closing. Rate pajak/payroll memerlukan validasi aturan berlaku secara terpisah.

Hingga pekerjaan tersebut memiliki bukti, statusnya **audit diperluas dengan cacat terkonfirmasi; belum full-code/full-flow sign-off**. Tidak ada perubahan aplikasi atau data produksi dalam pekerjaan ini.
