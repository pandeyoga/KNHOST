# Cakupan Gelombang 2

## Pembaruan 2026-10-03 — jawaban kebutuhan klien

[Memo 12 poin](25_MEMO_JAWABAN_KEBUTUHAN_KLIEN.md) · [bug dan register kebutuhan](26_TAMBAHAN_KLIEN_DAN_W2_025.md) · [prompt enam fase](27_PROMPT_TINDAK_LANJUT_KEBUTUHAN_KLIEN.md) · [tracker kebutuhan](client-requirements-tracker.json).

**Total 242 checkpoint: 174 kontrol, 36 reproduksi cacat W2, 26 pendalaman Wave1, 6 observasi kebijakan; 25 ID W2.** W2-025 membuktikan pembatasan lini daftar R&D tidak berlaku pada detail/patch sample. Empat probe penjelasan roll/lot/lini tidak menambah hitungan. Sembilan W2-REQ memisahkan kebutuhan fitur/SOP dari bug. Sampling mengikuti lini untuk SKU hasil MD; bahan standar dapat dibuat langsung. Ini penelusuran snapshot, bukan validasi deployment/fix atau pernyataan seluruh flow sudah tercover. Subtotal di bawah merupakan histori.


## Pembaruan 2026-10-03 — recovery dan kapasitas produksi

[Laporan detail](23_AUDIT_RECOVERY_DAN_KAPASITAS_PRODUKSI.md) · [prompt fase perbaikan](24_PROMPT_RECOVERY_PRODUKSI.md) · [matriks](18_MATRIKS_FLOW_KRITIS.md).

**Total239 checkpoint:173 kontrol,34 reproduksi cacat W2,6 observasi kebijakan,26 pendalaman Wave1;24 ID W2.** Tambahan13. W2-024: WO menghasilkan5.001 setelah hanya mengonsumsi5.000 roll bahan. GN-06 diperdalam dengan kegagalan GL akibat periode tertutup asli, reopen/retry menghasilkan dua output, concurrent completion menghapus je_id, dan cancel meninggalkan stok output. Semua source/flow belum tercover; tidak ada validasi fix atau perubahan source aplikasi. Subtotal di bawah adalah histori.


## Pembaruan 2026-10-03 — produksi, payroll dan rekening

[Laporan dan lokasi kode](21_AUDIT_PRODUKSI_PAYROLL_BANK.md) · [prompt empat fase](22_PROMPT_PRODUKSI_PAYROLL_BANK.md) · [matriks](18_MATRIKS_FLOW_KRITIS.md).

**Total226 checkpoint:169 kontrol,32 reproduksi cacat W2,6 observasi kebijakan,19 pendalaman Wave1;23 ID W2.** Tambahan30 pada produksi, payroll dan bank. W2-022: payroll paid tanpa buku kas. W2-023: akun beban diterima sebagai payout. W2-021 diperluas ke limit5.000 transaksi bank. GN-06 terbukti fault/retry mengonsumsi bahan dua kali dan mengikuti BOM terbaru; FN-08 terbukti runtime opening rekening tanpa GL. Bukti lama tidak ditimpa, source aplikasi/Wave1 tracker tidak diubah. Belum seluruh flow tercover; bukan validasi fix. Payroll tanpa BPJS/PPh hanya fixture pencatatan, bukan validasi perpajakan. Angka berikutnya merupakan subtotal historis.


## Pembaruan 2026-10-03 — refund, multi-PO, uang muka dan laporan besar

[Laporan detail dan lokasi kode](19_AUDIT_REFUND_ADVANCE_MULTI_PO_GL.md) · [prompt empat fase](20_PROMPT_REFUND_LAPORAN_DAN_PENDALAMAN.md) · [matriks cakupan](18_MATRIKS_FLOW_KRITIS.md).

**Total196 checkpoint:149 kontrol,28 reproduksi cacat W2,6 observasi kebijakan,13 pendalaman Wave1;21 ID W2.** Tambahan41 checkpoint pada lima harness; replay fixture sales tidak dihitung ulang. W2-020: refund final walau buku kas gagal, retry tidak memperbaiki. W2-021: neraca saldo/buku besar terpotong pada50.000 jurnal dan laba rugi pada100.000. CX-04/CX-05/FN-09 diperdalam tanpa tiket duplikat. Multi-PO dan close/reopen dataset kecil menambah kontrol positif.

Belum semua kode/flow tercover. Bukti ini bukan validasi fix: snapshot tetap sama. POS cashier/tender, seluruh posting subledger, multi-entitas, modul pendukung, browser dan hardware masih mempunyai batas yang dicatat dalam matriks. Angka pada bagian lama merupakan subtotal historis.


## Pembaruan 2026-10-03 — audit lintas flow

[Laporan dan lokasi kode](16_AUDIT_LINTAS_FLOW_QC_SALES_STOK_AR.md) · [prompt enam fase](17_PROMPT_LINTAS_FLOW.md) · [matriks96 kasus luas dan sisa kritis](18_MATRIKS_FLOW_KRITIS.md).

**Total klasifikasi terbaru155 checkpoint:117 kontrol,23 reproduksi cacat W2,6 observasi kebijakan,9 pendalaman Wave1;19 ID W2.** Tambahan56 terdiri dari41 checkpoint baru pada QC/sales/projection dan15 AR yang dahulu tertunda, kini direview dan direplay. Replay tidak dihitung dua kali. Status pending AR pada bagian lama sudah digantikan review ini.

Enam temuan baru: unit/nilai retur QC salah (W2-014), pure deposit tanpa reklasifikasi GL (015), void sumber deposit parsial (016), pemakaian deposit bersamaan meninggalkan payment tanpa dana (017), void menghapus payment baru (018), split QC menggandakan berat (019). GN-13 kini terbukti runtime lewat hold/rebuild, tanpa ID duplikat.19 kontrol sales menelusuri order hingga delivery, retur store credit dan reversal.

Semua source/flow kritis **belum** tercover.155 bukan155 business flow independen atau persentase coverage. Sisa dan batas kini dipetakan pada satu matriks, termasuk full Finance close, POS/refund tunai, multi-PO/gudang, concurrency/recovery menyeluruh, modul pendukung, browser dan hardware. Source aplikasi/trackers Wave1 tidak diubah. Angka di bawah adalah subtotal historis.

## Pembaruan 2026-10-02 — GRN parsial, kapasitas dan recovery

[Hasil detail](14_UJI_GRN_PARSIAL_KAPASITAS_RECOVERY.md) · [prompt perbaikan](15_PROMPT_GRN_KAPASITAS_RECOVERY.md).

20 checkpoint tambahan:15 kontrol, dua reproduksi cacat W2-013, tiga pendalaman GN-11. W2-013:501roll dihitung tetapi hanya500 difinalkan, GRN tetap closed. Pendalaman GN-11: setelah kegagalan roll kedua dan pelepasan lock, retry menghasilkan stok10 tetapi PO/QC6 dan task sisa4 palsu. Tidak menggandakan ID GN-11 atau mengubah tracker Gelombang1.

**Total klasifikasi terbaru:99 checkpoint skenario (69 kontrol,16 reproduksi cacat W2,6 observasi kebijakan,8 pendalaman Gelombang1),13 ID W2.** Ini bukan99 flow independen atau persentase coverage kode.15 skenario AR belum ditriase dan tetap tidak dihitung. Angka di bagian terdahulu adalah subtotal historis. GRN-04 bertambah bukti, tetap parsial; browser/hardware dan keseluruhan aplikasi belum tercover.

## Uji WMS UOM — 16 kontrol tambahan

[Konversi satuan, gramasi/lebar, roll, alias dan toleransi](13_UJI_WMS_UOM.md):16 kontrol service+Mongo sesuai ekspektasi. Tidak menguji full penerimaan HTTP/browser. Total klasifikasi menjadi79 skenario (54 kontrol,14 reproduksi defect W2,6 observasi kebijakan,5 pendalaman Gelombang1),12 ID temuan. Bukti Finance `ar-results.json` belum masuk total karena review/report tertunda saat fokus dialihkan pengguna.

## Pembaruan W2-05: RFID gate, ingest dan insiden

24 skenario melalui ASGI/service asli + MongoDB sintetis. Setelah [review](12_VALIDASI_ULANG_W2_05.md):10 kontrol, tiga reproduksi cacat W2-010–012, enam observasi kebijakan akses, dan lima pendalaman Gelombang1 RF-02/03/13/16. Kumulatif63 skenario,12 ID W2; ini **bukan** persentase cakupan aplikasi. Replay24 skenario dan10 probe review tidak dihitung ulang. [Detail lengkap](10_TEMUAN_RFID_GATE_DAN_INSIDEN.md).

| Kelompok | Skenario | Hasil utama |
|---|---|---|
| Autentikasi dan gate | C01–C08, E01–E05 | Key salah ditolak; available/quarantine red; PA benar diperiksa; empat bug lama tetap tereproduksi dan RF-16 memiliki dua kasus. |
| Entity scope | F01–F07, C09 | F01 adalah defect reads; F02–F07 observasi kebijakan karena incidents/device infra SHARED. C09 hanya kontrol warehouse filter. |
| Lifecycle alarm | C10, F08–F09 | Serial ack→resolve benar; race dapat memundurkan status dan menggandakan alarm. |

RFID-05 kini lebih dalam tetapi **parsial**: replay lintas batch dan race dedupe telah diuji; direction/perangkat, offline replay hardware dan browser UAT belum. W2-010 berkaitan dengan scope reads P01; W2-011/012 dengan state/alarm, keduanya P2. Kebijakan insiden global tidak diubah otomatis. Tidak menutup RF-02/03/13/16 Gelombang1 atau klaim sertifikasi GS1/SAP.

## Pembaruan W2-04: transfer gudang

| Skenario | Hasil ASGI API + Mongo |
|---|---|
| W2-T-C01 auto reserve A20 qty10 | Balance available10/reserved10 |
| W2-T-C02 reject auto transfer | Available kembali20 |
| W2-T-C03 pilih roll gudang W3 dari source W1 | 400, roll tetap available |
| W2-T-F01 pilih roll A10 manual | W2-009: roll reserved tetapi balance available10/reserved0 |
| W2-T-C04 cancel transfer manual A | Balance kembali available10 |
| W2-T-F02 pilih roll B pada transfer A | W2-008: HTTP200, roll B reserved, dokumen ownerA |
| W2-T-C05 cancel transfer yang memilih roll B | Roll B kembali available |
| W2-T-F03 auto-owner saat hanya B punya stok | Perluasan W2-006: dokumen A memiliki item ownerB |
| W2-T-C06 transfer otomatis sampai completed | Semua langkah200, available asal0/tujuan10 |

Sembilan skenario baru, enam kontrol dan tiga reproduksi cacat. Dua ID baru karena F03 berbagi akar masalah dengan W2-006. Kumulatif39 skenario, sembilan ID temuan. INV-02 masih parsial; full intercompany, race split dan perangkat belum diuji. [Detail](08_TEMUAN_TRANSFER_STOK.md).

## Pembaruan W2-03: opname

| Skenario | Hasil ASGI API + Mongo |
|---|---|
| W2-C-C01 approve normal | 200, stok100→90 |
| W2-C-C02 retry approve | 400, stok tetap90 |
| W2-C-C03 baca session B sebagai user A | 404 |
| W2-C-C08 explicit owner B sebagai user A | 403, stok B tetap10 |
| W2-C-F02 owner kosong, hanya stok B tersedia | W2-006: sessionA memilihB dan mengubah B10→8 |
| W2-C-C04 stok A dan B tersedia | TargetA, A20→18, B100 tetap |
| W2-C-C05 drift stok sebelum approve | 409, stok110 tetap, lock dilepas |
| W2-C-C06 reject lalu approve serial | 200/400, stok100 tetap |
| W2-C-C07 submit item belum dihitung | 400 |
| W2-C-F03 reject read→approve selesai→reject write | W2-007: dua200, status rejected, stok90 |

10 skenario baru, delapan kontrol dan dua cacat. Kumulatif30 skenario, tujuh ID temuan. F01 tidak dipakai: hipotesis explicit ownerB dibantah runtime dan dicatat sebagai kontrolC08. INV-03 menjadi lebih teruji tetapi tetap parsial. Recount/reopen, cutoff concurrent/ABA, semua bucket dan INV-05 rebuild belum dibuktikan. Temuan lama tentang bin, GL dan residual adjustment tidak dicatat ulang. [Detail](06_TEMUAN_CYCLE_COUNT.md).

## Pembaruan W2-02: klaim dan pembayaran

| Skenario | Lapisan | Hasil |
|---|---|---|
| W2-B-C01 pembayaran jasa penuh100.000 | ASGI API + Mongo | Bill paid, AP GL nol, kas100.000 |
| W2-B-C02 cancel bill dibayar | ASGI API + Mongo | 400, state tidak berubah |
| W2-B-C03 potong bon40.000 | Claim service + Mongo | Grand dan AP60.000 |
| W2-B-C04 approve klaim ulang | Claim service + Mongo | Ditolak, state tidak berubah |
| W2-B-C05 bayar60.000 setelah klaim | ASGI API + Mongo | Paid dan AP nol |
| W2-B-C06 klaim40.000 setelah bayar80.000 | API lalu claim service + Mongo | Ditolak, outstanding20.000 |
| W2-B-F01 cancel bill jasa belum dibayar | ASGI API + Mongo | W2-004: cancelled, AP GL masih100.000 |
| W2-B-F02 payment read→claim→payment write | API/service + scheduling barrier + Mongo | W2-005: paid80.000>grand60.000 |
| W2-B-F03 claim read→payment→claim write | API/service + scheduling barrier + Mongo | W2-005: paid80.000>grand60.000 |
| W2-B-C07 dua payment80.000, grand100.000 | ASGI API + barrier + Mongo | 200/409, kas hanya80.000 |
| W2-B-C08 cancel bill supplier umum | Bill fixture + GL asli + API + Mongo | Dua jurnal, AP net nol |

11 skenario baru; delapan kontrol dan tiga reproduksi cacat untuk dua ID baru. Kumulatif20 skenario, lima ID temuan. APAR-01 dan PROD-05 tetap parsial: tidak mengklaim seluruh bill matching, approval, reversal dan seluruh GRN sudah diuji. Barrier hanya mengatur urutan await dan tetap memanggil fungsi bisnis asli. Lihat [laporan](04_TEMUAN_KLAIM_DAN_PEMBAYARAN.md).

## Putaran W2-01

Putaran W2-01 menyasar PROD-05 pada checklist Gelombang 1. Statusnya sekarang **parsial**, bukan selesai. Tidak mengubah file coverage Gelombang1.

| Skenario | Lapisan | Hasil |
|---|---|---|
| W2-M-C01 issue→receive normal | Service + Mongo | Stok dan jurnal sama-sama120 |
| W2-M-C02 receive ulang | Service + Mongo | 409, state tidak berubah |
| W2-M-F01 toleransi9,5 versus10 | ASGI API + Mongo | Bug W2-001: stok114, jurnal120 |
| W2-M-F02 gudang tidak ada | ASGI API + Mongo | Bug W2-002:200 dan roll di ID invalid |
| W2-M-C03 selisih0,51 | Service + Mongo | 400 sebelum output/jurnal receipt |
| W2-M-C04 absorb partial4+final6 | Service + Mongo, partial fixture | Dua roll, total10, nilai120 |
| W2-M-C05 cancel partial | Service + Mongo, GRN fixture | Partial dihapus, GRN cancelled |
| W2-M-C06 retry cancel partial | Service + Mongo | 404 |
| W2-M-F03 partial WH→final WH2 | Helper posting GRN + Mongo | Bug W2-003: kedua roll di WH2 |

Enam kontrol lulus berarti perilaku fixture sesuai ekspektasi. Tiga assertion cacat lulus berarti cacat berhasil direproduksi, bukan aplikasi bebas bug. Sembilan skenario baru tidak setara sembilan kasus checklist tertutup.

## Antrean audit berikutnya

1. Lengkapi PROD-05: full HTTP partial GRN, multi-step, byproduct, kontrak jasa, klaim/pembayaran, pembatalan dan recovery setelah kegagalan GL.
2. INV-03/INV-05: cutoff count, recount dan rebuild balance saat mutasi berjalan.
3. APAR-01/02/04: pembayaran bill, alokasi receipt/deposit, advance-settlement-refund dan retry.
4. SALE-01/02/03/05: order sampai invoice, split tender, cancel parsial dan return/refund.
5. RFID-05: duplicate events, offline replay, direction dan reconnect; hardware tetap memerlukan lingkungan fisik.
6. AUTH/MASTER, CRM/R&D/design, dokumen/AI dan OPS mengikuti checklist baseline tanpa menandai flow selesai dari pembacaan source saja.

UI makloon diperiksa source pada validasi jumlah; belum browser UAT. Tidak ada coverage persentase seluruh kode/flow yang diklaim. Run tidak menyalakan scheduler/lifespan aplikasi. Harness tidak membangun semua indeks deployment. Audit tetap memakai database sintetis lokal dan pemblokiran socket eksternal.
