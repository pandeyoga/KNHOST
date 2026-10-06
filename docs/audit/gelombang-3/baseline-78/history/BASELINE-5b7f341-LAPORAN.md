# REFERENSI HISTORIS — bukan verdict current commit

# Laporan validasi lengkap KNHOST

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

**Semua137 catatan selesai direview; perbaikan sistem belum semuanya tuntas.**

# Hasil dan kelayakan sistem sekarang

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

**Sistem mengalami perbaikan nyata, tetapi belum layak dinyatakan tuntas untuk flow stok kritis dan akurasi Finance secara menyeluruh.** Seluruh 137 catatan gelombang 1/2 telah diberi verdict; tidak ada catatan berstatus `pending` review. Temuan terbuka di bawah berasal dari kode kandidat, bukan sekadar pengulangan dugaan baseline.

| Hasil validasi | Jumlah | Makna |
|---|---:|---|
| Tertutup spesifik | 106 | Defect original tertutup pada skenario yang diverifikasi |
| Sebagian | 25 | Perbaikan sebagian / acceptance end-to-end belum tuntas |
| Source/UI belum UAT | 3 | Source/build sesuai; interaksi UI belum diverifikasi |
| Konfirmasi bisnis | 2 | Implementasi ada; kontrak bisnis perlu diratifikasi |
| Duplikat | 1 | Duplikat yang tetap diperiksa |

Gelombang 1 terdiri dari 103 record termasuk IX-02 duplikat HR-03. Gelombang 2 terdiri dari 25 defect dan 9 kebutuhan bisnis. Jumlah record tidak sama dengan jumlah bug unik: beberapa ID berbagi akar masalah, dan kebutuhan bisnis bukan selalu defect.

## Perbaikan yang berhasil

- Entity/owner guard diperkuat pada operasi berdasarkan ID, termasuk R&D lintas lini, e-sign, bank, raw RFID, transfer dan cycle count. Scope tidak lagi cukup dijaga di daftar saja.
- Identitas roll hasil picking dipakai untuk shipment/HPP. Manifest yang berubah membuat loading check lama tidak valid. Tag simulated dibedakan dari verifikasi operasional.
- EPC dinormalisasi; printer pull/ack memakai lease/attempt. Gate evaluator memeriksa shipment aktif, QC, gudang dan replay exit. Cycle count membedakan expected, extra dan untagged.
- Financial posting memvalidasi balance/akun/finite numbers; effective COA mengikuti entitas. Kas manual, deposit-only reclass, payroll cash dan refund retry memiliki perbaikan yang lulus skenario terkait.
- Probe kapasitas aktual menunjukkan close GRN 501 roll bekerja, konsumsi WO 5.001 roll bekerja, serta regression laporan 50.001 jurnal dan bank 5.001 mutasi lulus.
- Maklon normal menggunakan panjang output terukur sebagai basis biaya, mempertahankan gudang partial receipt, dan menolak warehouse tidak sah sebelum output/jurnal.

## Celah yang menentukan keputusan rilis

| Flow | Bukti aktual | Implikasi |
|---|---|---|
| WO consumption/reversal | Output5 bisa menghabiskan10 ketika movement insert gagal; reversal dapat selesai tanpa restore | Stok/movement/cost tidak mempunyai pemulihan tepat sekali |
| Maklon receipt | Retry setelah output kedua gagal menghasilkan15 untuk order10, stok180 vs GL120 | Stok dan nilai persediaan berlebih |
| Cut & secondary weight | Parent berkurang3 tanpa child dan retry404; split paralel membuat total3.6kg dari3kg | Quantity dan gramasi tidak konservatif pada failure/race |
| Material commitment | Dua PR700+700 atas stok1000 menghasilkan reserved1400/shortage0; 2001 reservations dihitung2000 | ATP dapat menjanjikan bahan yang sudah dialokasikan |
| AR receipt | SO paid100, deposit kembali100, receipt0 setelah insert gagal | Deposit yang sama dapat dipakai lagi; saldo AR salah |
| Bank matching | Statement100 terhubung ke dua cash100; total cash reconciled200 | Rekonsiliasi dua sisi tidak konsisten |
| Cash flow & cutoff | Asset100/cash40/AP60 menjadi CFI−100/CFO+60; date-only awal periode hilang | Net cash seimbang belum berarti laporan benar |
| RFID ingest | Event baru20detik kemudian mengembalikan read green lama walau evaluator saat ini red | Hasil otorisasi read dapat basi lintas passage |
| Loading/SJ multi-gudang | Gudang siap tertahan pending cut gudang lain di SO sama | Fulfillment per gudang belum independen |
| PO variance & master migration | Amend qty diterima buntu; notes-only amendment menutup task sebelum approval; batch master berubah tanpa snapshot | Pekerjaan MD/Finance dapat dianggap selesai sebelum proses nyata selesai |

Detail root cause, baris kode dan counterexample terdapat pada [temuan lanjutan](04_TEMUAN_LANJUTAN.md). Terdapat 17 counterexample runtime dan 2 observasi kualitas; jumlah ini tidak dijumlahkan dengan 25 record sebagian seolah semuanya bug berbeda.

**Residual vs masalah baru:** Material-reservation dan governance/task variance adalah service baru dibanding baseline W2; cut/reversal/weight mempunyai helper baru. Cutoff tanggal dan guard received-line mempunyai body AST yang tetap sama, sehingga masalahnya residual atau integrasi CTA baru dengan guard lama. Fungsi produksi, receipt, bank, RFID dan cash flow berubah; laporan menyatakan failure kandidat yang terbukti tanpa mengarang commit pertama penyebabnya. Setiap temuan mencatat asal perubahan ini. Tidak semua17 counterexample dianggap regression yang sebelumnya tidak pernah ada.

## Penilaian per domain

| Domain | Penilaian saat ini | Dasar |
|---|---|---|
| RFID | Kontrol inti membaik; belum diterima penuh untuk otorisasi gate produksi | V3-RFID-01, policy all-tag vs exception, belum UAT reader/alarm/printer |
| WMS/produksi/maklon | Jalur normal banyak yang benar; ketahanan failure dan commitment belum aman | V3-CUT/PROD/MKO/MRES/WEIGHT serta V3-WMS-02 |
| Finance | Posting normal lebih kuat; belum dapat menyatakan seluruh angka akurat | V3-AR/BANK/CF/DATE, rekonsiliasi data lama belum dilakukan |
| Purchasing/MD | Variance task dan alternatif switch entitas sudah ada; acceptance penuh belum tuntas | V3-PO-01/02/03, keputusan kontrak R&D |
| Master/R&D | Struktur stage/lini lebih jelas; rollout governance dan policy ACC perlu diselesaikan | V3-MASTER-01, REQ-01/03, kode warna customer belum diputuskan |
| HR/CRM/marketing/interco/logistics/ops | Perbaikan spesifik diterima menurut record dan uji terkait | Detail per ID; bukan sertifikasi seluruh data atau seluruh branch domain |

## Yang tidak boleh disimpulkan dari audit ini

Audit ini bukan bukti 100% branch/statement coverage. Parser memeriksa 798 file Python dan 855 source frontend yang terlacak; telaah semantik berfokus seluruh 137 catatan, perubahan kandidat, helper SSOT dan flow terkait. Tidak semua baris unrelated memiliki satu eksekusi runtime. Audit selesai berarti seluruh catatan telah dinilai, termasuk yang belum selesai atau belum dapat diverifikasi secara fisik.

Kode aplikasi terlacak tidak diubah selama validasi. Synthetic fixture, build output, dependency runtime dan test copies berada di lingkungan audit. Tidak ada pengujian terhadap database produksi atau pengiriman notifikasi ke pihak eksternal.


---

# Validasi gelombang 1: 103 catatan

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

Setiap record di bawah telah dibandingkan dengan source kandidat dan bukti pengujian terkait. Status `ready_for_validation` dari agent merupakan klaim implementasi; verdict di laporan ini merupakan hasil review terpisah.

Hasil: 84 Tertutup spesifik, 15 Sebagian, 3 Source/UI belum UAT, 1 Duplikat.

| ID | Catatan original | Verdict | Temuan lanjutan terkait |
|---|---|---|---|

| [AX-01](#ax-01) | Roll yang dipindai tidak menjadi identitas yang wajib dikirim | Tertutup spesifik | — |

| [AX-02](#ax-02) | Task dispatch dianggap selesai sebelum surat jalan tersimpan | Tertutup spesifik | — |

| [AX-03](#ax-03) | Claim bergantian masih membolehkan progres partial shipment ditimpa | Tertutup spesifik | — |

| [AX-04](#ax-04) | Transfer roll eksplisit melewati owner filter dan rebuild balance | Tertutup spesifik | — |

| [AX-05](#ax-05) | Penerimaan transfer menghilangkan asal PO dan membawa bin gudang lama | Tertutup spesifik | — |

| [AX-06](#ax-06) | Print job multi-owner membocorkan item melalui owner header pertama | Tertutup spesifik | — |

| [AX-07](#ax-07) | Potongan generasi kedua mencatat kakek sebagai parent langsung | Tertutup spesifik | — |

| [AX-08](#ax-08) | Verifikasi tag dianggap cukup untuk memindahkan roll QC hold | Tertutup spesifik | — |

| [CX-01](#cx-01) | Penebusan store credit dapat melampaui nominal permintaan dan saldo | Tertutup spesifik | — |

| [CX-02](#cx-02) | Store credit dapat dialokasikan ke pelanggan atau badan usaha yang berbeda | Tertutup spesifik | — |

| [CX-03](#cx-03) | Gagal posting store credit meninggalkan AR terbayar tetapi kredit belum terpotong | Tertutup spesifik | — |

| [CX-04](#cx-04) | Retry pencairan uang muka membuat transaksi kas keluar kedua | Tertutup spesifik | — |

| [CX-05](#cx-05) | Uang muka yang telah selesai dapat dipertanggungjawabkan penuh lagi | Tertutup spesifik | — |

| [CX-06](#cx-06) | Manual bank matching menerima arah dan rekening yang tidak cocok | Tertutup spesifik | V3-BANK-01 |

| [CX-07](#cx-07) | Split bank reconciliation menghitung target yang sama lebih dari kapasitasnya | Sebagian | V3-BANK-01 |

| [CX-08](#cx-08) | Reschedule cicilan mengubah arti referensi pembayaran historis | Tertutup spesifik | — |

| [CX-09](#cx-09) | Konsolidasi memakai eliminasi di luar entitas yang dilaporkan | Tertutup spesifik | — |

| [CX-10](#cx-10) | E-sign tidak terikat pada versi dokumen yang ditampilkan | Tertutup spesifik | — |

| [CX-11](#cx-11) | Retur dua baris produk yang sama memakai harga baris terakhir | Tertutup spesifik | — |

| [CX-12](#cx-12) | Pengiriman pertama menutup special order sebelum pengiriman lain selesai | Tertutup spesifik | — |

| [CX-13](#cx-13) | Makloon receive mengunci order tanpa mengikat versi step yang sudah dibaca | Sebagian | V3-MKO-01 |

| [FN-01](#fn-01) | Landed cost menghitung anak split dua kali | Tertutup spesifik | — |

| [FN-02](#fn-02) | 3-way match lolos overbilling dari baris produk duplikat | Tertutup spesifik | V3-PO-01 |

| [FN-03](#fn-03) | WAC menjumlah panjang dan cost lintas unit tanpa konversi | Tertutup spesifik | — |

| [FN-04](#fn-04) | Arus kas seimbang tetapi klasifikasi transaksi nonkas salah | Sebagian | V3-CF-01 |

| [FN-05](#fn-05) | Master akun laporan menggabungkan override entitas dengan last-write-wins | Tertutup spesifik | — |

| [FN-06](#fn-06) | Jurnal manual menolak akun custom entitas dan mengabaikan override | Tertutup spesifik | — |

| [FN-07](#fn-07) | Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal | Tertutup spesifik | — |

| [FN-08](#fn-08) | Opening balance rekening dan perubahan rekening tidak tersambung GL | Tertutup spesifik | — |

| [FN-09](#fn-09) | Void jurnal manual melewati penguncian periode | Tertutup spesifik | — |

| [FN-10](#fn-10) | Pembayaran AR dapat sukses walau jurnal kas gagal | Sebagian | V3-AR-01 |

| [FN-11](#fn-11) | HPP per shipment memakai rata-rata semua roll pesanan | Tertutup spesifik | — |

| [FN-12](#fn-12) | Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan | Tertutup spesifik | — |

| [FN-13](#fn-13) | Close periode dapat berjalan dua kali secara bersamaan | Tertutup spesifik | — |

| [FN-14](#fn-14) | Stock opname tidak memposting variance GL dan surplus dibuat tanpa cost | Tertutup spesifik | — |

| [FN-15](#fn-15) | Helper autopost tidak menegakkan invariant jurnal di pintu insert | Tertutup spesifik | — |

| [FN-16](#fn-16) | Neraca default tidak membatasi tanggal meski diberi label hari ini | Sebagian | V3-DATE-01 |

| [GN-01](#gn-01) | Idempotency tidak terikat user cookie, entitas dan payload | Tertutup spesifik | — |

| [GN-02](#gn-02) | WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope | Tertutup spesifik | — |

| [GN-03](#gn-03) | Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen | Tertutup spesifik | — |

| [GN-04](#gn-04) | R&D dapat mengambil bahan dari roll badan usaha lain | Tertutup spesifik | — |

| [GN-05](#gn-05) | Rollback pengambilan bahan R&D dapat menimpa pemakaian roll lain | Tertutup spesifik | — |

| [GN-06](#gn-06) | Produksi menyelesaikan WO tanpa claim dan memakai BOM terbaru | Sebagian | V3-PROD-01, V3-PROD-02 |

| [GN-07](#gn-07) | Retur supplier mengurangi roll dengan read-set dan partial return kehilangan identitas fisik | Tertutup spesifik | — |

| [GN-08](#gn-08) | Konversi permintaan internal dapat melahirkan transaksi antar-PT ganda | Tertutup spesifik | — |

| [GN-09](#gn-09) | CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID | Tertutup spesifik | — |

| [GN-10](#gn-10) | Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global | Tertutup spesifik | — |

| [GN-11](#gn-11) | Saga release menghapus lock tanpa mengecek efek yang sudah terposting | Sebagian | V3-PROD-01, V3-PROD-02, V3-MKO-01, V3-CUT-01 |

| [GN-12](#gn-12) | Agregasi kritis berhenti pada batas to_list tanpa penanda truncation | Sebagian | V3-MRES-02 |

| [GN-13](#gn-13) | Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit | Tertutup spesifik | — |

| [GN-14](#gn-14) | Audit log selalu before=None dan source secrets tersimpan dalam repo publik | Sebagian | — |

| [GN-15](#gn-15) | Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten | Sebagian | V3-DUP-01, V3-BUILD-01 |

| [GN-16](#gn-16) | Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas | Tertutup spesifik | — |

| [HR-01](#hr-01) | PPh21 memakai TER bahkan pada masa pajak terakhir | Tertutup spesifik | — |

| [HR-02](#hr-02) | Lembur memakai multiplier flat dan dua sumber menit berpotensi tumpang tindih | Tertutup spesifik | — |

| [HR-03](#hr-03) | Persetujuan cuti tidak mengecek ulang saldo dan cuti lintas tahun salah pembebanan | Tertutup spesifik | — |

| [IX-01](#ix-01) | Jatah cuti nol berubah kembali menjadi jatah default | Tertutup spesifik | — |

| [IX-02](#ix-02) | Pembatalan satu cuti menghapus absensi milik cuti lain yang masih disetujui | Duplikat | — |

| [IX-03](#ix-03) | Shift malam menghasilkan durasi standar negatif dan lembur palsu | Tertutup spesifik | — |

| [IX-04](#ix-04) | Lembur absensi yang belum disetujui tetap dibayar payroll | Tertutup spesifik | — |

| [IX-05](#ix-05) | Metadata e-sign lintas badan usaha dapat dibaca lewat HTTP | Tertutup spesifik | — |

| [IX-06](#ix-06) | Edit payroll settings dari entitas A mengubah konfigurasi efektif B | Tertutup spesifik | — |

| [IX-07](#ix-07) | Pengaturan Finance entitas lain dapat diubah melalui scope | Tertutup spesifik | — |

| [IX-08](#ix-08) | Approval basi dapat menimpa penolakan buka periode dan mengaktifkan izin posting | Tertutup spesifik | — |

| [IX-09](#ix-09) | Membuka kembali inspeksi tidak membatalkan indikator selesai pada retur | Tertutup spesifik | — |

| [IX-10](#ix-10) | Baca dan keputusan buka periode tidak memeriksa penugasan entitas | Tertutup spesifik | — |

| [IX-11](#ix-11) | Produksi mengonsumsi roll yang masih ditahan QC | Tertutup spesifik | — |

| [IX-12](#ix-12) | Kompensasi gagal menempelkan roll ke tugas meninggalkan tag RFID aktif tanpa roll | Tertutup spesifik | — |

| [IX-13](#ix-13) | Konversi hitung manual penerimaan menyimpang dari mesin UOM utama | Tertutup spesifik | — |

| [IX-14](#ix-14) | GRN dinyatakan closed walau jurnal penerimaan gagal | Tertutup spesifik | — |

| [IX-15](#ix-15) | Keputusan QC sebagian menutup tugas dan mengunci sisa karantina | Tertutup spesifik | — |

| [IX-16](#ix-16) | Kontrak nilai net/gross retur beli membuat AP, persediaan dan kas tidak cocok | Tertutup spesifik | — |

| [IX-17](#ix-17) | Retur menjadi approved dan mengubah stok/AP sebelum jurnal ditolak | Tertutup spesifik | — |

| [MK-01](#mk-01) | Input metrik marketing parsial mengganti seluruh metrik sebelumnya | Tertutup spesifik | — |

| [RF-01](#rf-01) | Format EPC database berbeda dari EPC yang ditulis ke chip | Tertutup spesifik | — |

| [RF-02](#rf-02) | Gate OUT menganggap status sebagai izin keluar | Sebagian | V3-RFID-01 |

| [RF-03](#rf-03) | Gate IN menerima transit di gudang mana pun | Tertutup spesifik | — |

| [RF-04](#rf-04) | Final Loading Check belum menjadi prasyarat dispatch | Tertutup spesifik | — |

| [RF-05](#rf-05) | Loading Check clean walaupun sebagian roll tidak punya tag | Tertutup spesifik | — |

| [RF-06](#rf-06) | Hasil loading melekat pada SO, tidak pada versi shipment aktual | Sebagian | V3-WMS-02 |

| [RF-07](#rf-07) | Tombol simulasi dapat mengisi bukti verifikasi operasional | Tertutup spesifik | — |

| [RF-08](#rf-08) | Sesi dan histori Cycle Count RFID tidak terisolasi entitas | Tertutup spesifik | — |

| [RF-09](#rf-09) | Cycle count lintas entitas dibuat tetapi tidak dapat dipindai | Tertutup spesifik | — |

| [RF-10](#rf-10) | Mesin sesi bersama tidak memvalidasi jenis sesi dan kehilangan scan konkuren | Tertutup spesifik | — |

| [RF-11](#rf-11) | Payload ZPL dan custom EPC tidak divalidasi aman | Tertutup spesifik | — |

| [RF-12](#rf-12) | Daftar device membocorkan API key hardware | Tertutup spesifik | — |

| [RF-13](#rf-13) | Device dinonaktifkan masih diterima autentikasi | Tertutup spesifik | — |

| [RF-14](#rf-14) | Lifecycle cetak mengklaim tag tercetak terlalu dini dan retry verifikasi buntu | Tertutup spesifik | — |

| [RF-15](#rf-15) | Antrean printer tidak memiliki claim dan ack tidak membatasi tipe device | Tertutup spesifik | — |

| [RF-16](#rf-16) | Ingest belum mempunyai event identity, passage window dan deduplikasi lintas batch | Sebagian | V3-RFID-01 |

| [RF-17](#rf-17) | Definisi stok fisik RFID berbeda dari SSOT dan metrik count mengabaikan extra | Tertutup spesifik | — |

| [UX-01](#ux-01) | Gate kiosk menampilkan hasil lama sebagai LIVE dan tidak mengagregasi satu passage | Source/UI belum UAT | — |

| [UX-02](#ux-02) | Unduhan ZPL lewat tautan tidak membawa konteks entitas yang dipilih | Source/UI belum UAT | — |

| [UX-03](#ux-03) | Panel biaya OCR menampilkan ID entitas mentah | Source/UI belum UAT | — |

| [WM-01](#wm-01) | Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil | Sebagian | V3-WEIGHT-01, V3-CUT-01 |

| [WM-02](#wm-02) | Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik | Sebagian | V3-CUT-01 |

| [WM-03](#wm-03) | Konfirmasi tiba dengan scan kosong memindahkan semua roll | Tertutup spesifik | — |

| [WM-04](#wm-04) | Putaway antar-gudang in-transit tidak mengubah bucket stok roll | Tertutup spesifik | — |

| [WM-05](#wm-05) | PA dapat berebut roll dan arrival menulis lokasi tanpa prasyarat roll | Tertutup spesifik | — |

| [WM-06](#wm-06) | Scan picking tidak memvalidasi identitas roll dan menerima qty negatif | Tertutup spesifik | — |

| [WM-07](#wm-07) | Stock opname per bin memakai expected seluruh gudang dan membolehkan duplikasi | Tertutup spesifik | — |

| [WM-08](#wm-08) | Adjustment shortage dapat parsial tetapi sesi tetap approved | Tertutup spesifik | — |

| [WM-09](#wm-09) | Penerimaan exception PA tidak menulis mutasi transfer | Tertutup spesifik | — |


## AX-01

**Catatan:** Roll yang dipindai tidak menjadi identitas yang wajib dikirim. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Picking menulis identitas roll tervalidasi; dispatch meneruskan manifest roll tersebut. Uji OLD/NEW dan biaya roll aktual lulus. Hambatan loading lintas gudang dibahas terpisah pada RF-06/REQ-08.

**Lokasi source kandidat:** [backend/services/roll_service.py:1310](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L1310) (`ship_order_rolls`); [backend/services/shipment_service.py:42](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/shipment_service.py#L42) (`dispatch_task`); [backend/routers/outbound_picking.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/outbound_picking.py); [backend/services/loading_check_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/loading_check_service.py).

**Bukti positif:** [followup-suite-results.json](evidence/followup-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/AX-01.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `1ea1dd82bd19cf36304c9a1cbef735a74f72b932`.


## AX-02

**Catatan:** Task dispatch dianggap selesai sebelum surat jalan tersimpan. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Shipment identity dan progres operasi disimpan sebelum task dianggap selesai. Fault setelah perubahan stok dapat melanjutkan shipment yang sama pada regression P03; pemeriksaan saga P07b juga lulus.

**Lokasi source kandidat:** [backend/services/shipment_service.py:42](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/shipment_service.py#L42) (`dispatch_task`); [backend/services/atomic_claim.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/atomic_claim.py).

**Uji flow tambahan:** `audit/iterations/2026-10-02-P03-durable-posting/repro_p03.py`, `audit/iterations/2026-10-07-P07-fulfillment-saga-loading/repro_p07b.py`. Lihat tabel hasil/log; nama helper/skenario tidak selalu memakai ID temuan sebagai label.

**Batas bukti runtime:** Tidak ada assertion PASS dengan label ID ini pada parser hasil script. Penerimaan didasarkan pada telaah source dan/atau uji flow berkelompok yang disebut di laporan pengujian; bukan klaim setiap branch ID dieksekusi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/AX-02.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## AX-03

**Catatan:** Claim bergantian masih membolehkan progres partial shipment ditimpa. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Setelah claim task, state/progres dibaca kembali; dua dispatch parsial tidak lagi menulis shipped_qty dari snapshot sebelum claim. Uji konkurensi dan partial fulfillment lulus.

**Lokasi source kandidat:** [backend/services/shipment_service.py:42](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/shipment_service.py#L42) (`dispatch_task`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [followup-suite-results.json](evidence/followup-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/AX-03.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `1ea1dd82bd19cf36304c9a1cbef735a74f72b932`.


## AX-04

**Catatan:** Transfer roll eksplisit melewati owner filter dan rebuild balance. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Pemilihan roll eksplisit menyaring owner dan gudang sumber serta melakukan rebuild. Pengujian akses entitas dan W2-008/009 mengonfirmasi cabang pilihan ID.

**Lokasi source kandidat:** [backend/services/roll_service.py:1698](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L1698) (`reserve_rolls_for_wh_transfer`); [backend/routers/transfers.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/transfers.py).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/AX-04.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## AX-05

**Catatan:** Penerimaan transfer menghilangkan asal PO dan membawa bin gudang lama. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Transfer mempertahankan provenance perolehan dan menghapus bin asal. Landed cost masih dapat mengikuti receipt asal setelah transfer.

**Lokasi source kandidat:** [backend/services/landed_cost_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/landed_cost_service.py); [backend/services/roll_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/AX-05.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## AX-06

**Catatan:** Print job multi-owner membocorkan item melalui owner header pertama. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Print job dibatasi ke satu owner; job legacy campuran mendapat guard anggota. Pemilihan urutan owner dan detail/download tidak memberikan item owner lain.

**Lokasi source kandidat:** [backend/services/rfid_print_service.py:130](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py#L130) (`create_print_job`).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/AX-06.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## AX-07

**Catatan:** Potongan generasi kedua mencatat kakek sebagai parent langsung. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Child menetapkan parent_roll_id langsung dan root_roll_id terpisah. Tiga generasi lulus. Konservasi berat saat dua split bersamaan masih gagal pada W2-019.

**Lokasi source kandidat:** [backend/services/roll_service.py:93](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L93) (`insert_child_roll`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/AX-07.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## AX-08

**Catatan:** Verifikasi tag dianggap cukup untuk memindahkan roll QC hold. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Tag readiness tidak menghapus QC hold. Putaway dan evaluator gate memeriksa quality/movement aktif; reprint tidak menulis ulang lokasi operasional.

**Lokasi source kandidat:** [backend/services/putaway_order_service.py:83](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/putaway_order_service.py#L83) (`create_order`); [backend/services/rfid_ingest_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py); [backend/services/rfid_print_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/AX-08.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## CX-01

**Catatan:** Penebusan store credit dapat melampaui nominal permintaan dan saldo. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Jumlah alokasi dinormalisasi dan dibatasi terhadap nominal penebusan serta saldo. Request10/alokasi150 atas kredit100 ditolak tanpa efek.

**Lokasi source kandidat:** [backend/services/store_credit_service.py:161](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/store_credit_service.py#L161) (`redeem`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-01.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## CX-02

**Catatan:** Store credit dapat dialokasikan ke pelanggan atau badan usaha yang berbeda. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Validator alokasi menerima customer dan entity sumber; alokasi otomatis dibatasi owner yang sama. Positive control serta tujuan customer/entity lain diuji.

**Lokasi source kandidat:** [backend/services/store_credit_service.py:161](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/store_credit_service.py#L161) (`redeem`); [backend/services/ar_receipt_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ar_receipt_service.py).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-02.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## CX-03

**Catatan:** Gagal posting store credit meninggalkan AR terbayar tetapi kredit belum terpotong. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Penebusan kredit memiliki state operasi dan penanganan kegagalan GL; regression P03 menunjukkan AR/kredit tidak tertinggal pada fault GL. Celah receipt insert V3-AR-01 berada pada pembayaran deposit, bukan bukti penebusan kredit ini gagal lagi.

**Lokasi source kandidat:** [backend/services/store_credit_service.py:161](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/store_credit_service.py#L161) (`redeem`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-03.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## CX-04

**Catatan:** Retry pencairan uang muka membuat transaksi kas keluar kedua. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Pencairan mengikat cash transaction yang sama sebelum melanjutkan jurnal; retry setelah kegagalan GL menghasilkan satu kas keluar.

**Lokasi source kandidat:** [backend/services/cash_advance_service.py:288](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/cash_advance_service.py#L288) (`disburse_cash_advance`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-04.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## CX-05

**Catatan:** Uang muka yang telah selesai dapat dipertanggungjawabkan penuh lagi. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Settlement advance terminal tidak dapat dipertanggungjawabkan lagi; klaim dan identitas sumber jurnal menjaga retry alur yang diuji.

**Lokasi source kandidat:** [backend/services/cash_advance_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/cash_advance_service.py); [backend/services/gl_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [extended-suite-results.json](evidence/extended-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-05.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`, `39c387b93ce476ab4bcb4cfcb864361e9fe4247c`, `1a2c33a43e5ca4841c95422593aa2a258298dee3`.


## CX-06

**Catatan:** Manual bank matching menerima arah dan rekening yang tidak cocok. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Manual matching menolak arah dan rekening tidak cocok. Kontrol normal lulus. Kekurangan claim pada statement line ditemukan pada V3-BANK-01 dan menjadi blocker domain bank, meskipun validasi arah/rekening sudah benar.

**Lokasi source kandidat:** [backend/services/bank_recon_service.py:725](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/bank_recon_service.py#L725) (`manual_match`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-BANK-01](04_TEMUAN_LANJUTAN.md#v3-bank-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-06.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## CX-07

**Catatan:** Split bank reconciliation menghitung target yang sama lebih dari kapasitasnya. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Duplikasi txn_id dalam payload sudah dijumlah/dibatasi dan sisi cash mempunyai CAS. Sisi statement line belum diklaim: dua matching paralel atas line100 menghasilkan cash reconciled200. Lihat V3-BANK-01.

**Lokasi source kandidat:** [backend/services/bank_recon_service.py:588](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/bank_recon_service.py#L588) (`_link`); [backend/services/bank_recon_service.py:759](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/bank_recon_service.py#L759) (`match_split`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-BANK-01](04_TEMUAN_LANJUTAN.md#v3-bank-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-07.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## CX-08

**Catatan:** Reschedule cicilan mengubah arti referensi pembayaran historis. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Payment plan memakai identitas installment stabil; reschedule mempertahankan referensi pembayaran lama dan menghitung outstanding dari pembayaran aktual.

**Lokasi source kandidat:** [backend/services/payment_plan_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/payment_plan_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-08.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## CX-09

**Catatan:** Konsolidasi memakai eliminasi di luar entitas yang dilaporkan. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Elimination dibatasi perimeter entitas laporan; laporan subset tidak memakai eliminasi entitas luar. Regression konsolidasi serta interco P20d lulus.

**Lokasi source kandidat:** [backend/services/consolidation_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/consolidation_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-09.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `6240190c1496165f70d2919add1bbf2d167d082e`.


## CX-10

**Catatan:** E-sign tidak terikat pada versi dokumen yang ditampilkan. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Signature mengikat hash/version dokumen dan payload PDF yang ditandatangani. Edit dokumen menghasilkan versi berbeda; source dan HTTP e-sign scope lulus.

**Lokasi source kandidat:** [backend/services/esign_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/esign_service.py); [backend/services/pdf_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/pdf_service.py).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 10 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-10.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## CX-11

**Catatan:** Retur dua baris produk yang sama memakai harga baris terakhir. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Harga retur memakai sales line identity dan snapshot harga baris sumber, bukan map product terakhir. Dua baris SKU sama dengan harga berbeda diuji.

**Lokasi source kandidat:** [backend/services/return_service.py:389](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/return_service.py#L389) (`create_return`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [followup-suite-results.json](evidence/followup-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-11.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `1ea1dd82bd19cf36304c9a1cbef735a74f72b932`.


## CX-12

**Catatan:** Pengiriman pertama menutup special order sebelum pengiriman lain selesai. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Special order baru selesai saat seluruh shipment terkait benar-benar delivered. Pengujian service dan HTTP iter115 mengonfirmasi shipment pertama tidak menutup order.

**Lokasi source kandidat:** [backend/services/special_order_phase2.py:446](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/special_order_phase2.py#L446) (`on_delivered`); [backend/services/logistics_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/logistics_service.py); [backend/services/special_order_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/special_order_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [followup-suite-results.json](evidence/followup-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-12.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `cc744854e1af92c8c4bac32c792159caa5892fa9`.


## CX-13

**Catatan:** Makloon receive mengunci order tanpa mengikat versi step yang sudah dibaca. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Claim receive mengikat versi step yang dibaca dan menahan konkurensi normal. Recovery output belum idempoten per roll: gagal sebelum output kedua lalu retry menghasilkan15 untuk order10. V3-MKO-01.

**Lokasi source kandidat:** [backend/services/makloon_order_service.py:880](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/makloon_order_service.py#L880) (`receive_step`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-MKO-01](04_TEMUAN_LANJUTAN.md#v3-mko-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/CX-13.md); fase sebelumnya `P11`. Commit implementasi yang diklaim: .


## FN-01

**Catatan:** Landed cost menghitung anak split dua kali. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Landed cost tidak menggandakan parent dan child; allocation mengikuti provenance/root quantity. Uji split dan transfer asal PO lulus.

**Lokasi source kandidat:** [backend/services/landed_cost_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/landed_cost_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-01.md); fase sebelumnya `P04`. Commit implementasi yang diklaim: `39c387b93ce476ab4bcb4cfcb864361e9fe4247c`.


## FN-02

**Catatan:** 3-way match lolos overbilling dari baris produk duplikat. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Three-way match memakai line identity, agregat alokasi current bill dan serialized approval PO. Overbilling duplikat dan bill bersamaan dalam regression P04 diblokir.

**Lokasi source kandidat:** [backend/routers/vendor_bills.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/vendor_bills.py); [backend/services/vendor_bill_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/vendor_bill_service.py); [backend/services/po_variance_task_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/po_variance_task_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-PO-01](04_TEMUAN_LANJUTAN.md#v3-po-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-02.md); fase sebelumnya `P04`. Commit implementasi yang diklaim: `39c387b93ce476ab4bcb4cfcb864361e9fe4247c`, `1a2c33a43e5ca4841c95422593aa2a258298dee3`, `6240190c1496165f70d2919add1bbf2d167d082e`.


## FN-03

**Catatan:** WAC menjumlah panjang dan cost lintas unit tanpa konversi. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** WAC mengonversi kuantitas native ke base unit dengan resolver UOM; nilai roll tetap dihitung dengan cost native. Missing conversion tidak diasumsikan faktor1.

**Lokasi source kandidat:** [backend/services/costing_service.py:45](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/costing_service.py#L45) (`wac_for_product`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-03.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## FN-04

**Catatan:** Arus kas seimbang tetapi klasifikasi transaksi nonkas salah. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Jurnal murni nonkas sudah dipisahkan. Jurnal campuran pembelian aset100, kas40, AP60 masih dilaporkan CFI−100/CFO+60, padahal kas keluar40. Net cash yang seimbang tidak membuktikan klasifikasi benar. V3-CF-01.

**Lokasi source kandidat:** [backend/services/cash_flow_service.py:55](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/cash_flow_service.py#L55) (`cash_flow_statement`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-CF-01](04_TEMUAN_LANJUTAN.md#v3-cf-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-04.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `6240190c1496165f70d2919add1bbf2d167d082e`.


## FN-05

**Catatan:** Master akun laporan menggabungkan override entitas dengan last-write-wins. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** COA laporan memakai effective global+override entitas deterministik; override entitas lain tidak mengubah laporan entitas aktif.

**Lokasi source kandidat:** [backend/services/financial_statement_service.py:50](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/financial_statement_service.py#L50) (`_accounts_map`); [backend/services/gl_service.py:507](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L507) (`effective_accounts`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 5 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-05.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `6240190c1496165f70d2919add1bbf2d167d082e`.


## FN-06

**Catatan:** Jurnal manual menolak akun custom entitas dan mengabaikan override. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Manual entry dan autopost memvalidasi COA efektif entitas, active dan postable. Akun custom A diterima A dan tidak dapat dipakai B.

**Lokasi source kandidat:** [backend/services/gl_service.py:524](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L524) (`_validate_entry_lines`); [backend/services/gl_service.py:640](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L640) (`create_manual_entry`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 5 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-06.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `6240190c1496165f70d2919add1bbf2d167d082e`.


## FN-07

**Catatan:** Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Manual cash memiliki jurnal dan reversal; generic void dibatasi untuk cash turunan dokumen sumber. Pengujian kas/GL create-void-retry lulus.

**Lokasi source kandidat:** [backend/routers/cash.py:110](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/cash.py#L110) (`create_cash_transaction`); [backend/routers/cash.py:171](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/cash.py#L171) (`void_cash_transaction`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-07.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## FN-08

**Catatan:** Opening balance rekening dan perubahan rekening tidak tersambung GL. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Opening balance rekening diikat jurnal pembukaan; perubahan field finansial setelah posting dikunci atau melalui adjustment. Saldo buku bank dan GL pada fixture normal sesuai.

**Lokasi source kandidat:** [backend/services/bank_service.py:68](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/bank_service.py#L68) (`create_account`); [backend/services/bank_service.py:120](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/bank_service.py#L120) (`update_account`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-08.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## FN-09

**Catatan:** Void jurnal manual melewati penguncian periode. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Void manual entry melewati closed-period guard dan CAS status. Uji periode tertutup menolak mutasi tanpa unlock yang sah.

**Lokasi source kandidat:** [backend/services/gl_service.py:755](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L755) (`void_entry`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-09.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `6240190c1496165f70d2919add1bbf2d167d082e`.


## FN-10

**Catatan:** Pembayaran AR dapat sukses walau jurnal kas gagal. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Kegagalan GL tidak lagi ditelan; receipt menampilkan gl_status failed dan repost dapat memulihkan. Tetapi gagal insert receipt setelah SO dialokasikan meninggalkan SO terbayar, deposit dipulihkan, receipt nihil. V3-AR-01.

**Lokasi source kandidat:** [backend/services/ar_receipt_service.py:71](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ar_receipt_service.py#L71) (`_post_cash_in`); [backend/services/ar_receipt_service.py:413](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ar_receipt_service.py#L413) (`create_receipt`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-AR-01](04_TEMUAN_LANJUTAN.md#v3-ar-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-10.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## FN-11

**Catatan:** HPP per shipment memakai rata-rata semua roll pesanan. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Shipment menyimpan extended cost roll aktual dan jurnal HPP memakai manifest shipment. Dua shipment dengan roll biaya berbeda lulus P04; shipment HTTP iter114 juga lulus.

**Lokasi source kandidat:** [backend/services/gl_service.py:1116](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L1116) (`post_shipment_cogs`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-11.md); fase sebelumnya `P04`. Commit implementasi yang diklaim: `39c387b93ce476ab4bcb4cfcb864361e9fe4247c`.


## FN-12

**Catatan:** Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Register aset melarang perubahan biaya/tanggal/akun finansial sesudah kapitalisasi tanpa jalur koreksi. Edit nonfinansial tetap tersedia.

**Lokasi source kandidat:** [backend/services/fixed_asset_service.py:141](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/fixed_asset_service.py#L141) (`update_asset`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-12.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## FN-13

**Catatan:** Close periode dapat berjalan dua kali secara bersamaan. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Close/reclose memakai claim per entitas sehingga close normal paralel tidak menggandakan jurnal. Ini menerima skenario yang dieksekusi; lease stale600detik belum diuji dengan proses nyata yang hidup lebih dari10menit. Risiko fencing dicatat, bukan diklaim telah terbukti.

**Lokasi source kandidat:** [backend/services/closing_service.py:253](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/closing_service.py#L253) (`close_period`); [backend/services/closing_service.py:269](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/closing_service.py#L269) (`_acquire_close_lock`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-13.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `6240190c1496165f70d2919add1bbf2d167d082e`.


## FN-14

**Catatan:** Stock opname tidak memposting variance GL dan surplus dibuat tanpa cost. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Variance opname mempunyai biaya dan GL; surplus tanpa biaya ditolak atau membutuhkan kebijakan eksplisit. Stok, movement dan jurnal pada P10 sesuai.

**Lokasi source kandidat:** [backend/routers/cycle_count.py:253](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/cycle_count.py#L253) (`approve_session`); [backend/services/roll_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 7 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-14.md); fase sebelumnya `P10`. Commit implementasi yang diklaim: .


## FN-15

**Catatan:** Helper autopost tidak menegakkan invariant jurnal di pintu insert. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Pintu insert jurnal memvalidasi balance, finite numbers, nonnegative, dual-sided serta kelayakan akun sebelum menulis. Uji negative/NaN/Infinity/invalid account dan positive control lulus.

**Lokasi source kandidat:** [backend/services/gl_service.py:524](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L524) (`_validate_entry_lines`); [backend/services/gl_service.py:580](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L580) (`_insert_entry`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 7 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-15.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## FN-16

**Catatan:** Neraca default tidak membatasi tanggal meski diberi label hari ini. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Neraca default sudah memakai cutoff hari ini. Namun journal.date yang sah berupa YYYY-MM-DD pada awal periode tidak lolos filter YYYY-MM-DDT00:00:00; laporan periodik kehilangan baris itu. V3-DATE-01.

**Lokasi source kandidat:** [backend/services/financial_statement_service.py:28](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/financial_statement_service.py#L28) (`_day_start`); [backend/services/financial_statement_service.py:57](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/financial_statement_service.py#L57) (`_aggregate`); [backend/services/financial_statement_service.py:185](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/financial_statement_service.py#L185) (`balance_sheet`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-DATE-01](04_TEMUAN_LANJUTAN.md#v3-date-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/FN-16.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `6240190c1496165f70d2919add1bbf2d167d082e`.


## GN-01

**Catatan:** Idempotency tidak terikat user cookie, entitas dan payload. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Idempotency memakai identitas autentikasi cookie/bearer, entity dan hash payload; replay memvalidasi sesi. Uji HTTP cookie pada localhost dengan Secure=false untuk lingkungan uji lulus.

**Lokasi source kandidat:** [backend/dependencies.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/dependencies.py); [backend/idempotency.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/idempotency.py).

**Bukti positif:** [followup-suite-results.json](evidence/followup-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [final-fixture-suite-results.json](evidence/final-fixture-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-01.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## GN-02

**Catatan:** WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** WebSocket GPS memeriksa expiry, peran dan owner scope pada snapshot/broadcast. Uji sesi expired dan manager A/B lulus; socket eksternal tidak digunakan.

**Lokasi source kandidat:** [backend/services/tracking_service.py:65](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/tracking_service.py#L65) (`auth_ws_token`); [backend/server.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/server.py).

**Bukti positif:** [followup-suite-results.json](evidence/followup-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [final-fixture-suite-results.json](evidence/final-fixture-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-02.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## GN-03

**Catatan:** Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Ledger bank dan reconcile kas berdasarkan ID memanggil entity guard dokumen, bukan hanya permission modul.

**Lokasi source kandidat:** [backend/routers/bank.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/bank.py).

**Bukti positif:** [final-fixture-suite-results.json](evidence/final-fixture-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-03.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## GN-04

**Catatan:** R&D dapat mengambil bahan dari roll badan usaha lain. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Pengambilan bahan R&D memeriksa owner roll terhadap entitas sample sebelum CAS/movement/GL. Sample A tidak dapat memakai roll B.

**Lokasi source kandidat:** [backend/routers/rnd.py:596](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/rnd.py#L596) (`issue_material`); [backend/services/rnd_sample_service.py:1207](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_sample_service.py#L1207) (`issue_material`).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-04.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## GN-05

**Catatan:** Rollback pengambilan bahan R&D dapat menimpa pemakaian roll lain. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Kompensasi pemakaian bahan R&D mengembalikan kontribusi operasinya dengan increment, tidak menimpa seluruh snapshot roll. Fault GL bersama pemakaian lain lulus.

**Lokasi source kandidat:** [backend/services/rnd_sample_service.py:1207](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_sample_service.py#L1207) (`issue_material`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-05.md); fase sebelumnya `P11`. Commit implementasi yang diklaim: .


## GN-06

**Catatan:** Produksi menyelesaikan WO tanpa claim dan memakai BOM terbaru. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** WO released memakai BOM snapshot dan claim; bahan memakai CAS, cursor utuh serta shortage postcondition. Tetapi decrement bahan→movement insert belum satu operasi durable, dan reversal menandai selesai sebelum restore fisik. V3-PROD-01/02.

**Lokasi source kandidat:** [backend/services/production_service.py:331](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py#L331) (`_consume_material`); [backend/services/production_service.py:383](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py#L383) (`reverse_operation`); [backend/services/production_service.py:410](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py#L410) (`complete_work_order`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 7 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-PROD-01](04_TEMUAN_LANJUTAN.md#v3-prod-01), [V3-PROD-02](04_TEMUAN_LANJUTAN.md#v3-prod-02). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-06.md); fase sebelumnya `P11`. Commit implementasi yang diklaim: .


## GN-07

**Catatan:** Retur supplier mengurangi roll dengan read-set dan partial return kehilangan identitas fisik. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Retur supplier memakai CAS qty/status/owner dan child fisik untuk potongan retur. Uji sales vs return, partial return serta rollback GL lulus.

**Lokasi source kandidat:** [backend/services/purchase_return_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/purchase_return_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 6 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-07.md); fase sebelumnya `P11`. Commit implementasi yang diklaim: .


## GN-08

**Catatan:** Konversi permintaan internal dapat melahirkan transaksi antar-PT ganda. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Request internal mengklaim conversion dan mempertahankan source_request_id/hasil pair. Dua request tidak membuat transaksi interco ganda pada skenario P11.

**Lokasi source kandidat:** [backend/routers/internal_requests.py:177](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/internal_requests.py#L177) (`convert_request`); [backend/services/internal_request_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/internal_request_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-08.md); fase sebelumnya `P11`. Commit implementasi yang diklaim: .


## GN-09

**Catatan:** CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** CRM lead, interaction dan conversion berdasarkan ID memeriksa entity selain sales owner; customer tujuan harus berada dalam owner yang sesuai.

**Lokasi source kandidat:** [backend/routers/crm_omnichannel.py:126](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/crm_omnichannel.py#L126) (`_guard_lead_owner`); [backend/services/crm_omnichannel_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/crm_omnichannel_service.py).

**Batas bukti runtime:** Tidak ada assertion PASS dengan label ID ini pada parser hasil script. Penerimaan didasarkan pada telaah source dan/atau uji flow berkelompok yang disebut di laporan pengujian; bukan klaim setiap branch ID dieksekusi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-09.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## GN-10

**Catatan:** Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** POS recommendation memakai resolver scope server dan stock summary owner-scoped; query entity tidak sah ditolak.

**Lokasi source kandidat:** [backend/routers/pos.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/pos.py); [backend/services/pos_recommendation_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/pos_recommendation_service.py).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-10.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## GN-11

**Catatan:** Saga release menghapus lock tanpa mengecek efek yang sudah terposting. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Admin release kini memeriksa lock aktif dan business effects; regression P07b/iter115 lulus. Namun recoverability masih bergantung bukti yang ditulis sesudah efek fisik pada produksi/maklon/cut, sehingga safe release saja belum menjamin recovery. V3-PROD-01/V3-MKO-01/V3-CUT-01.

**Lokasi source kandidat:** [backend/routers/saga_locks.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/saga_locks.py); [backend/services/atomic_claim.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/atomic_claim.py); [backend/services/production_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py); [backend/services/makloon_order_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/makloon_order_service.py); [backend/services/roll_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py).

**Bukti positif:** [followup-suite-results.json](evidence/followup-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-PROD-01](04_TEMUAN_LANJUTAN.md#v3-prod-01), [V3-PROD-02](04_TEMUAN_LANJUTAN.md#v3-prod-02), [V3-MKO-01](04_TEMUAN_LANJUTAN.md#v3-mko-01), [V3-CUT-01](04_TEMUAN_LANJUTAN.md#v3-cut-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-11.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `cc744854e1af92c8c4bac32c792159caa5892fa9`.


## GN-12

**Catatan:** Agregasi kritis berhenti pada batas to_list tanpa penanda truncation. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Cap lama di WAC, balance, cash summary dan laporan inti dihapus. Cap baru reserved_by_others2000 mengurangi cadangan2001 menjadi2000; ATP/guard bahan dapat meloloskan stok yang dicadangkan. V3-MRES-02. Cursor UI berhalaman bukan masalah bila total terpisah.

**Lokasi source kandidat:** [backend/services/financial_statement_service.py:57](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/financial_statement_service.py#L57) (`_aggregate`); [backend/services/roll_service.py:233](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L233) (`rebuild_balance`); [backend/services/material_reservation_service.py:40](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/material_reservation_service.py#L40) (`reserved_by_others`); [backend/routers/cash.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/cash.py); [backend/services/costing_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/costing_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-MRES-02](04_TEMUAN_LANJUTAN.md#v3-mres-02). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-12.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## GN-13

**Catatan:** Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Projection rebuild memakai tiket urutan sebelum membaca sumber dan conditional write; UOM tidak terkonversi menandai projection_valid=false, bukan menambah qty native.

**Lokasi source kandidat:** [backend/services/roll_service.py:233](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L233) (`rebuild_balance`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-13.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## GN-14

**Catatan:** Audit log selalu before=None dan source secrets tersimpan dalam repo publik. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Audit snapshots/redaction/hash dan penghapusan secret dari source aktif lolos P13. Bukti rotasi credential historis serta pembersihan history tidak tersedia. Penghapusan file pada HEAD tidak membuktikan credential lama telah tidak berlaku.

**Lokasi source kandidat:** [backend/dependencies.py:155](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/dependencies.py#L155) (`audit`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 8 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-14.md); fase sebelumnya `P13`. Commit implementasi yang diklaim: .


## GN-15

**Catatan:** Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Resolver UOM, status fisik, COA dan gate utama telah dipusatkan. Scan seluruh backend masih menemukan _clean_perms identik didefinisikan dua kali, baris60/67. Ini duplikasi P3, bukan dua kebijakan berbeda. V3-DUP-01.

**Lokasi source kandidat:** [backend/services/custom_role_service.py:60](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/custom_role_service.py#L60) (`_clean_perms`); [backend/services/custom_role_service.py:67](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/custom_role_service.py#L67) (`_clean_perms`); [backend/services/contract_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/contract_service.py); [backend/services/lot_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/lot_service.py); [backend/services/receiving_uom_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/receiving_uom_service.py); [backend/services/uom_rules_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/uom_rules_service.py); [frontend/package.json](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/package.json).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 21 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-DUP-01](04_TEMUAN_LANJUTAN.md#v3-dup-01), [V3-BUILD-01](04_TEMUAN_LANJUTAN.md#v3-build-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-15.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: .


## GN-16

**Catatan:** Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Notifikasi laporan AI pribadi mengosongkan recipient_role dan digest memakai entity/user relevance. Uji user2 dan entitas lain tidak menerima judul/body pribadi.

**Lokasi source kandidat:** [backend/services/ai_schedules.py:74](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ai_schedules.py#L74) (`run_schedule`); [backend/services/digest_service.py:103](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/digest_service.py#L103) (`summarize_for`); [backend/services/notification_scope.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/notification_scope.py); [backend/services/notification_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/notification_service.py).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/GN-16.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## HR-01

**Catatan:** PPh21 memakai TER bahkan pada masa pajak terakhir. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Payroll membedakan masa terakhir dan merekonsiliasi Pasal17 dengan prior withholding; lebih potong dapat negatif pada slip terakhir. Fixture bulanan/Desember/termination P12 lulus. Ini tidak menyertifikasi seluruh kasus perpajakan atau data payroll produksi.

**Lokasi source kandidat:** [backend/services/hr_payroll_service.py:84](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_payroll_service.py#L84) (`annual_pph21`); [backend/services/hr_payroll_service.py:238](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_payroll_service.py#L238) (`_is_final_tax_period`); [backend/services/hr_payroll_service.py:258](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_payroll_service.py#L258) (`compute_payslip`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [final-fixture-suite-results.json](evidence/final-fixture-suite-results.json) — 6 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/HR-01.md); fase sebelumnya `P12`. Commit implementasi yang diklaim: .


## HR-02

**Catatan:** Lembur memakai multiplier flat dan dua sumber menit berpotensi tumpang tindih. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Lembur dihitung sebagai event bertanggal dengan tier jam normal/libur dan pairing sumber attendance/formal. Dua jam hari normal serta overlap fixture P12 lulus.

**Lokasi source kandidat:** [backend/services/hr_payroll_service.py:211](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_payroll_service.py#L211) (`_overtime_amount`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/HR-02.md); fase sebelumnya `P12`. Commit implementasi yang diklaim: .


## HR-03

**Catatan:** Persetujuan cuti tidak mengecek ulang saldo dan cuti lintas tahun salah pembebanan. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Approval membaca ulang saldo di bawah claim pegawai dan membebankan setiap work_date ke tahun benar. Overlap dicegah, projection attendance terikat leave_id.

**Lokasi source kandidat:** [backend/services/hr_leave_service.py:86](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_leave_service.py#L86) (`recompute_balance`); [backend/services/hr_leave_service.py:250](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_leave_service.py#L250) (`approve_leave`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 5 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [final-fixture-suite-results.json](evidence/final-fixture-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/HR-03.md); fase sebelumnya `P12`. Commit implementasi yang diklaim: .


## IX-01

**Catatan:** Jatah cuti nol berubah kembali menjadi jatah default. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Override entitlement0 dibedakan dari field missing; recompute mempertahankan nol. Override positif dan saldo lintas tahun diuji.

**Lokasi source kandidat:** [backend/services/hr_leave_service.py:86](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_leave_service.py#L86) (`recompute_balance`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-01.md); fase sebelumnya `P12`. Commit implementasi yang diklaim: .


## IX-02

**Catatan:** Pembatalan satu cuti menghapus absensi milik cuti lain yang masih disetujui. **Verdict:** Duplikat yang tetap diperiksa.

**Hasil telaah dan dampak:** Tracker menggabungkan masalah attendance cancellation ini ke HR-03. Tetap diperiksa: leave_id/overlap guard menjaga pembatalan satu izin tidak menghapus absensi izin lain. Tidak dihitung sebagai bug unik tambahan.

**Lokasi source kandidat:** [backend/services/hr_leave_service.py:297](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_leave_service.py#L297) (`cancel_leave`); [backend/services/hr_attendance_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_attendance_service.py).

**Batas bukti runtime:** Tidak ada assertion PASS dengan label ID ini pada parser hasil script. Penerimaan didasarkan pada telaah source dan/atau uji flow berkelompok yang disebut di laporan pengujian; bukan klaim setiap branch ID dieksekusi.

**Penghitungan:** Tetap masuk coverage record; tidak dihitung sebagai defect unik tambahan.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-02.md); fase sebelumnya `P12`. Commit implementasi yang diklaim: .


## IX-03

**Catatan:** Shift malam menghasilkan durasi standar negatif dan lembur palsu. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Durasi shift yang melintasi tengah malam ditambah satu hari; 22–06 memberi480menit, bukan durasi negatif. Payroll tidak menambah overtime palsu.

**Lokasi source kandidat:** [backend/services/hr_attendance_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_attendance_service.py); [backend/services/hr_payroll_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_payroll_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-03.md); fase sebelumnya `P12`. Commit implementasi yang diklaim: .


## IX-04

**Catatan:** Lembur absensi yang belum disetujui tetap dibayar payroll. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Payroll hanya memakai overtime attendance approved/unflagged dan memadankan filed event agar tidak dihitung dua kali. Slip posted memerlukan adjustment untuk perubahan berikutnya.

**Lokasi source kandidat:** [backend/services/hr_attendance_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_attendance_service.py); [backend/services/hr_payroll_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_payroll_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-04.md); fase sebelumnya `P12`. Commit implementasi yang diklaim: .


## IX-05

**Catatan:** Metadata e-sign lintas badan usaha dapat dibaca lewat HTTP. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Metadata e-sign berdasarkan source_id mendapat entity guard dokumen. A tidak membaca source B meski mempunyai esign.view.

**Lokasi source kandidat:** [backend/routers/esign.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/esign.py); [backend/services/esign_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/esign_service.py).

**Bukti positif:** [final-fixture-suite-results.json](evidence/final-fixture-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-05.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## IX-06

**Catatan:** Edit payroll settings dari entitas A mengubah konfigurasi efektif B. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** PUT payroll settings menulis scope entity yang sama dengan GET; global override tetap jalur tersendiri. Uji A/B serta reload config lulus.

**Lokasi source kandidat:** [backend/routers/hr_payroll.py:40](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/hr_payroll.py#L40) (`update_payroll_settings`); [backend/services/config_resolver.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/config_resolver.py); [backend/services/hr_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_service.py).

**Bukti positif:** [followup-suite-results.json](evidence/followup-suite-results.json) — 11 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-06.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## IX-07

**Catatan:** Pengaturan Finance entitas lain dapat diubah melalui scope. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Settings scope diresolusikan terhadap entitas yang boleh diakses; permission entity.update tidak memberikan scope B secara otomatis.

**Lokasi source kandidat:** [backend/routers/settings.py:45](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/settings.py#L45) (`update_settings`); [backend/services/entity_lifecycle_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/entity_lifecycle_service.py).

**Bukti positif:** [followup-suite-results.json](evidence/followup-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [final-fixture-suite-results.json](evidence/final-fixture-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-07.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## IX-08

**Catatan:** Approval basi dapat menimpa penolakan buka periode dan mengaktifkan izin posting. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Approve/reject period unlock memakai CAS status pending; reject yang menang tidak dapat ditimpa stale approval. Closed-period guard membaca unlock valid dan expiry.

**Lokasi source kandidat:** [backend/services/period_unlock_service.py:189](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/period_unlock_service.py#L189) (`approve_request`); [backend/services/period_unlock_service.py:222](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/period_unlock_service.py#L222) (`reject_request`); [backend/services/gl_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-08.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `6240190c1496165f70d2919add1bbf2d167d082e`.


## IX-09

**Catatan:** Membuka kembali inspeksi tidak membatalkan indikator selesai pada retur. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Inspection reopen menghapus milestone inspected aktif pada retur sambil mempertahankan history keputusan lama; finish ulang memakai versi/timestamp baru.

**Lokasi source kandidat:** [backend/services/inspection_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/inspection_service.py); [backend/services/return_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/return_service.py); [frontend/src/features/sales/ReturnJourneyPanel.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/sales/ReturnJourneyPanel.jsx).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-09.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## IX-10

**Catatan:** Baca dan keputusan buka periode tidak memeriksa penugasan entitas. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** List/active/approve/reject unlock memakai resolver dan document owner guard. Uji scope query/header dan dual control lulus.

**Lokasi source kandidat:** [backend/routers/period_unlocks.py:84](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/period_unlocks.py#L84) (`approve_unlock`); [backend/routers/period_unlocks.py:100](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/period_unlocks.py#L100) (`reject_unlock`); [backend/services/period_unlock_service.py:68](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/period_unlock_service.py#L68) (`list_requests`).

**Bukti positif:** [final-fixture-suite-results.json](evidence/final-fixture-suite-results.json) — 5 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-10.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## IX-11

**Catatan:** Produksi mengonsumsi roll yang masih ditahan QC. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Preflight produksi dan CAS konsumsi mengecualikan inspection.hold.held. Roll held tidak dipakai meski status available.

**Lokasi source kandidat:** [backend/services/production_service.py:179](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py#L179) (`_available_qty`); [backend/services/production_service.py:331](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py#L331) (`_consume_material`); [backend/services/location_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/location_service.py); [backend/services/qc_inspection_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/qc_inspection_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-11.md); fase sebelumnya `P11`. Commit implementasi yang diklaim: .


## IX-12

**Catatan:** Kompensasi gagal menempelkan roll ke tugas meninggalkan tag RFID aktif tanpa roll. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Failure attach receiving roll menonaktifkan tag serta menghapus roll; cleanup orphan idempoten. Service P08 dan HTTP iter116 lulus.

**Lokasi source kandidat:** [backend/services/receiving_roll_service.py:268](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/receiving_roll_service.py#L268) (`create_counted_roll`); [backend/services/rfid_service.py:468](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_service.py#L468) (`retire_orphan_tags`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-12.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: .


## IX-13

**Catatan:** Konversi hitung manual penerimaan menyimpang dari mesin UOM utama. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Count receiving memakai canonical UOM resolver, bukan tabel lokal/fallback1. Unknown unit ditolak sebelum roll/tag/counter; cm/yard dan jalur GRN diuji.

**Lokasi source kandidat:** [backend/services/receiving_roll_service.py:268](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/receiving_roll_service.py#L268) (`create_counted_roll`); [backend/services/goods_receipt_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/goods_receipt_service.py); [backend/services/uom_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/uom_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-13.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## IX-14

**Catatan:** GRN dinyatakan closed walau jurnal penerimaan gagal. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** GRN yang gagal GL tetap dapat dilanjutkan dengan status posting visible; close tidak diam-diam final. Retry normal memberi satu jurnal dan tidak menggandakan qty.

**Lokasi source kandidat:** [backend/services/goods_receipt_close_service.py:372](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/goods_receipt_close_service.py#L372) (`close_grn`); [backend/services/inbound_complete_service.py:30](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/inbound_complete_service.py#L30) (`complete_task`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-14.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## IX-15

**Catatan:** Keputusan QC sebagian menutup tugas dan mengunci sisa karantina. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** QC parsial mempertahankan qc_pending/residual; task baru terminal setelah semua karantina diputuskan. P06 dan HTTP scopeQC lulus.

**Lokasi source kandidat:** [backend/services/qc_service.py:341](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/qc_service.py#L341) (`_apply_qc_decision`); [backend/routers/inbound_receiving_extra.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/inbound_receiving_extra.py).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-15.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## IX-16

**Catatan:** Kontrak nilai net/gross retur beli membuat AP, persediaan dan kas tidak cocok. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Kontrak purchase return membedakan net, PPN dan grand_total; kas/AP/GL memakai gross yang sama. Fixture ber-PPN P04 lulus. Retur QC unit kg juga diuji W2-014.

**Lokasi source kandidat:** [backend/services/gl_service.py:2358](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L2358) (`post_purchase_return`); [backend/services/purchase_return_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/purchase_return_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-16.md); fase sebelumnya `P04`. Commit implementasi yang diklaim: `39c387b93ce476ab4bcb4cfcb864361e9fe4247c`.


## IX-17

**Catatan:** Retur menjadi approved dan mengubah stok/AP sebelum jurnal ditolak. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Retur supplier mempunyai posting progress/retry dan lock; kegagalan GL tidak menjadi final sukses palsu. P03 fault/period/retry lulus.

**Lokasi source kandidat:** [backend/services/purchase_return_service.py:444](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/purchase_return_service.py#L444) (`supplier_accept`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 5 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/IX-17.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## MK-01

**Catatan:** Input metrik marketing parsial mengganti seluruh metrik sebelumnya. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Metrics menggunakan $set metrics.<field> dan history snapshot, sehingga patch parsial dan dua field bersamaan tidak menghapus nilai lain. Nol tetap nilai sah.

**Lokasi source kandidat:** [backend/services/marketing_service.py:243](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/marketing_service.py#L243) (`record_metrics`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/MK-01.md); fase sebelumnya `P12`. Commit implementasi yang diklaim: .


## RF-01

**Catatan:** Format EPC database berbeda dari EPC yang ditulis ke chip. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Encode, ZPL, ingest dan scan memakai EPC24hex uppercase yang sama; separator/lowercase dinormalisasi, duplicate representation tidak melahirkan tag kedua.

**Lokasi source kandidat:** [backend/services/rfid_service.py:92](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_service.py#L92) (`encode_tag`); [backend/services/epc.py:19](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/epc.py#L19) (`canonical_epc`); [backend/services/rfid_ingest_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py); [backend/services/rfid_print_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 6 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-01.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: .


## RF-02

**Catatan:** Gate OUT menganggap status sebagai izin keluar. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Evaluator OUT memeriksa shipment/movement aktif, owner, gudang, QC dan replay. Ingest same-gate masih mengembalikan green cached120detik untuk event baru/passage baru meski evaluator kini red. V3-RFID-01.

**Lokasi source kandidat:** [backend/services/rfid_ingest_service.py:118](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py#L118) (`ingest`); [backend/services/rfid_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 10 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-RFID-01](04_TEMUAN_LANJUTAN.md#v3-rfid-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-02.md); fase sebelumnya `P09`. Commit implementasi yang diklaim: .


## RF-03

**Catatan:** Gate IN menerima transit di gudang mana pun. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Gate IN memerlukan transfer/PA aktif dan destination warehouse tepat; transit_sales tidak menjadi izin masuk gudang mana saja. P09 serta HTTP iter117 lulus.

**Lokasi source kandidat:** [backend/services/rfid_ingest_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 5 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-03.md); fase sebelumnya `P09`. Commit implementasi yang diklaim: .


## RF-04

**Catatan:** Final Loading Check belum menjadi prasyarat dispatch. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Policy loading_check required menolak dispatch tanpa check; exception memerlukan permission/alasan dan audit. Hasil simulated tidak diterima sebagai bukti loading.

**Lokasi source kandidat:** [backend/services/loading_check_service.py:165](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/loading_check_service.py#L165) (`dispatch_guard`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [followup-suite-results.json](evidence/followup-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-04.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `cc744854e1af92c8c4bac32c792159caa5892fa9`.


## RF-05

**Catatan:** Loading Check clean walaupun sebagian roll tidak punya tag. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Untagged/dangling/retired tags tidak masuk hasil clean; pengecualian memerlukan reason dan permission. Old test tanpa reason gagal karena guard diperketat. Kontrak all-tag user vs exception bawaan dibahas pada REQ-08.

**Lokasi source kandidat:** [backend/services/loading_check_service.py:71](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/loading_check_service.py#L71) (`complete`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [followup-suite-results.json](evidence/followup-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-05.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `1ea1dd82bd19cf36304c9a1cbef735a74f72b932`.


## RF-06

**Catatan:** Hasil loading melekat pada SO, tidak pada versi shipment aktual. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Hash manifest invalidates hasil bila roll/qty berubah. Sesi masih SO-wide; start tidak menerima warehouse/shipment subset dan pending cut gudang lain memblokir shipment lokal. Acceptance sesi independen belum terpenuhi. V3-WMS-02.

**Lokasi source kandidat:** [backend/services/loading_check_service.py:26](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/loading_check_service.py#L26) (`start`); [backend/services/loading_check_service.py:165](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/loading_check_service.py#L165) (`dispatch_guard`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [followup-suite-results.json](evidence/followup-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-WMS-02](04_TEMUAN_LANJUTAN.md#v3-wms-02). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-06.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `cc744854e1af92c8c4bac32c792159caa5892fa9`.


## RF-07

**Catatan:** Tombol simulasi dapat mengisi bukti verifikasi operasional. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Source simulated dipersistenkan dan tidak menghasilkan clean operasional, tag verified atau dispatch. UI menyatakan simulasi. P08 dan HTTP iter116 menguji pemisahan tersebut.

**Lokasi source kandidat:** [backend/services/rfid_print_service.py:268](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py#L268) (`scan_verify`); [backend/services/rfid_print_service.py:327](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py#L327) (`complete_verify`); [frontend/src/features/rfid/CycleCountPanel.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/rfid/CycleCountPanel.jsx); [frontend/src/features/rfid/RfidPrintVerifyPanel.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/rfid/RfidPrintVerifyPanel.jsx); [frontend/src/features/wms/LoadingCheckPanel.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/wms/LoadingCheckPanel.jsx).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 6 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-07.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: .


## RF-08

**Catatan:** Sesi dan histori Cycle Count RFID tidak terisolasi entitas. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** RFID cycle-count menyimpan scope owner dan menguji seluruh anggota pada read/reuse/scan/complete/history. P01 history serta kontrol type sesi lulus.

**Lokasi source kandidat:** [backend/services/cycle_count_service.py:144](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/cycle_count_service.py#L144) (`get_count`).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-08.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## RF-09

**Catatan:** Cycle count lintas entitas dibuat tetapi tidak dapat dipindai. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Scope multi-owner disimpan sebagai kumpulan owner; caller harus memiliki seluruh scope sesi. Old replay yang tidak mengirim kind cycle_count ditolak sesuai typed-session guard; replay P14 menggunakan kind benar lulus.

**Lokasi source kandidat:** [backend/services/rfid_print_service.py:268](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py#L268) (`scan_verify`); [backend/services/cycle_count_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/cycle_count_service.py).

**Bukti positif:** [extended-suite-results.json](evidence/extended-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-09.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## RF-10

**Catatan:** Mesin sesi bersama tidak memvalidasi jenis sesi dan kehilangan scan konkuren. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Scan memakai union atomik dan status open; complete memvalidasi kind endpoint. Dua batch paralel mempertahankan EPC dan session completed menolak scan.

**Lokasi source kandidat:** [backend/services/rfid_print_service.py:268](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py#L268) (`scan_verify`); [backend/services/rfid_print_service.py:327](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py#L327) (`complete_verify`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 5 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-10.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: .


## RF-11

**Catatan:** Payload ZPL dan custom EPC tidak divalidasi aman. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** ZPL meng-escape command karakter teks dan EPC custom wajib canonical24hex. Test injection/length/nonhex positif-negatif lulus.

**Lokasi source kandidat:** [backend/services/rfid_print_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py); [backend/services/rfid_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 7 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-11.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: .


## RF-12

**Catatan:** Daftar device membocorkan API key hardware. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** API key perangkat disimpan hashed/redacted dan tidak hadir pada list/detail/update biasa; rotasi hanya melalui endpoint berizin. HTTP device tests lulus.

**Lokasi source kandidat:** [backend/services/rfid_service.py:189](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_service.py#L189) (`list_devices`); [backend/services/rfid_ingest_service.py:26](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py#L26) (`ensure_api_key`); [backend/routers/rfid.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/rfid.py).

**Uji flow tambahan:** `audit/iterations/2026-09-30-P01-device-credentials/repro_rf12_rf13.py`. Lihat tabel hasil/log; nama helper/skenario tidak selalu memakai ID temuan sebagai label.

**Batas bukti runtime:** Tidak ada assertion PASS dengan label ID ini pada parser hasil script. Penerimaan didasarkan pada telaah source dan/atau uji flow berkelompok yang disebut di laporan pengujian; bukan klaim setiap branch ID dieksekusi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-12.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## RF-13

**Catatan:** Device dinonaktifkan masih diterima autentikasi. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Authentication device memeriksa enabled sebelum heartbeat/ingest/pull/ack; disabled tidak dapat menghidupkan dirinya dengan heartbeat.

**Lokasi source kandidat:** [backend/services/rfid_ingest_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py).

**Uji flow tambahan:** `audit/iterations/2026-09-30-P01-device-credentials/repro_rf12_rf13.py`. Lihat tabel hasil/log; nama helper/skenario tidak selalu memakai ID temuan sebagai label.

**Batas bukti runtime:** Tidak ada assertion PASS dengan label ID ini pada parser hasil script. Penerimaan didasarkan pada telaah source dan/atau uji flow berkelompok yang disebut di laporan pengujian; bukan klaim setiap branch ID dieksekusi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-13.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `522e28258d1f6dfa9eabc354fd3f034c8225d8dd`.


## RF-14

**Catatan:** Lifecycle cetak mengklaim tag tercetak terlalu dini dan retry verifikasi buntu. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Queued belum printed; ack/mark-printed baru mengubah print stage. Verify dengan issues dapat membuat revisi baru; reprint roll stored tidak memindahkan lokasi.

**Lokasi source kandidat:** [backend/services/rfid_print_service.py:216](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py#L216) (`mark_printed`); [backend/services/rfid_print_service.py:299](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_print_service.py#L299) (`start_verify`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 8 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-14.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: .


## RF-15

**Catatan:** Antrean printer tidak memiliki claim dan ack tidak membatasi tipe device. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Printer pull mengklaim lease/attempt atomik; ack mensyaratkan type printer, owner lease, attempt dan expiry. Parallel pull dan stale ack lulus.

**Lokasi source kandidat:** [backend/services/rfid_ingest_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 6 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-15.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: .


## RF-16

**Catatan:** Ingest belum mempunyai event identity, passage window dan deduplikasi lintas batch. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Event identity dan passage window sudah ada, oversized batch diblokir serta replay event idempotent. Dwell cache tetap melintasi passage sehingga event baru memakai keputusan lama tanpa evaluasi business state. V3-RFID-01.

**Lokasi source kandidat:** [backend/services/rfid_ingest_service.py:118](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py#L118) (`ingest`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-RFID-01](04_TEMUAN_LANJUTAN.md#v3-rfid-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-16.md); fase sebelumnya `P09`. Commit implementasi yang diklaim: .


## RF-17

**Catatan:** Definisi stok fisik RFID berbeda dari SSOT dan metrik count mengabaikan extra. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Expected fisik mengikuti registry status stok; extra dan untagged tercakup dalam discrepancy/denominator. Semua expected plus extra tidak lagi dilabeli akurasi100% inventory.

**Lokasi source kandidat:** [backend/services/cycle_count_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/cycle_count_service.py); [backend/services/rfid_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/RF-17.md); fase sebelumnya `P10`. Commit implementasi yang diklaim: .


## UX-01

**Catatan:** Gate kiosk menampilkan hasil lama sebagai LIVE dan tidak mengagregasi satu passage. **Verdict:** Source/build sesuai; interaksi UI belum diverifikasi.

**Hasil telaah dan dampak:** Gate status/passages terpisah dari reads biasa; GateLiveVerdict menghitung heartbeat/poll TTL dan passage worst verdict. API TTL/latch diuji; source/build UI lulus. Browser lokal gagal inisialisasi kernel sehingga visual/UAT disconnect hardware belum terbukti.

**Lokasi source kandidat:** [frontend/src/features/rfid/RfidGateMonitorView.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/rfid/RfidGateMonitorView.jsx).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Batas verifikasi:** Source dan build diperiksa; tindakan browser, reload/draft, download atau interaksi fisik belum dilakukan karena runtime UI tidak dapat diinisialisasi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/UX-01.md); fase sebelumnya `P09`. Commit implementasi yang diklaim: .


## UX-02

**Catatan:** Unduhan ZPL lewat tautan tidak membawa konteks entitas yang dipilih. **Verdict:** Source/build sesuai; interaksi UI belum diverifikasi.

**Hasil telaah dan dampak:** Unduh ZPL memakai apiClient blob dengan X-Entity-Id, object URL kemudian direvoke. Source dan build lulus, tetapi interaksi download di browser tidak dapat dieksekusi pada runtime UI sesi ini.

**Lokasi source kandidat:** [frontend/src/features/rfid/RfidPrintVerifyPanel.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/rfid/RfidPrintVerifyPanel.jsx).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Batas verifikasi:** Source dan build diperiksa; tindakan browser, reload/draft, download atau interaksi fisik belum dilakukan karena runtime UI tidak dapat diinisialisasi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/UX-02.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: .


## UX-03

**Catatan:** Panel biaya OCR menampilkan ID entitas mentah. **Verdict:** Source/build sesuai; interaksi UI belum diverifikasi.

**Hasil telaah dan dampak:** Panel biaya OCR memakai entityShortById, fallback badan usaha tidak dikenal dan ID hanya tooltip. Source/build lulus; validasi visual browser belum dilakukan.

**Lokasi source kandidat:** [frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Batas verifikasi:** Source dan build diperiksa; tindakan browser, reload/draft, download atau interaksi fisik belum dilakukan karena runtime UI tidak dapat diinisialisasi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/UX-03.md); fase sebelumnya `P13`. Commit implementasi yang diklaim: .


## WM-01

**Catatan:** Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Update panjang parent kini satu pipeline atomik dan konkurensi panjang lulus. Crash di antara decrement parent dan child insert pada cut baru menghilangkan qty3 serta reservasi; retry404. V3-CUT-01. Konservasi berat juga belum aman paralel.

**Lokasi source kandidat:** [backend/services/roll_service.py:573](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L573) (`confirm_cut`); [backend/services/roll_service.py:745](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L745) (`_split_roll`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-WEIGHT-01](04_TEMUAN_LANJUTAN.md#v3-weight-01), [V3-CUT-01](04_TEMUAN_LANJUTAN.md#v3-cut-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-01.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `49b177090d57a1d349830c83f7f53c119cb17631`.


## WM-02

**Catatan:** Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Reservasi parsial memakai length_reservations dan belum melahirkan child fisik; cut/tag/identity menjadi tahap nyata. Fault child insert pada confirm_cut menghapus reservasi dan mengurangi parent tanpa child, gagal recovery. V3-CUT-01.

**Lokasi source kandidat:** [backend/services/roll_service.py:549](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L549) (`_reserve_length`); [backend/services/roll_service.py:573](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L573) (`confirm_cut`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 11 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-CUT-01](04_TEMUAN_LANJUTAN.md#v3-cut-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-02.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`, `39c387b93ce476ab4bcb4cfcb864361e9fe4247c`, `1a2c33a43e5ca4841c95422593aa2a258298dee3`.


## WM-03

**Catatan:** Konfirmasi tiba dengan scan kosong memindahkan semua roll. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Explicit epcs=[] tidak memindahkan roll; subset hanya memindahkan subset. All-arrival membutuhkan command override beralasan.

**Lokasi source kandidat:** [backend/services/putaway_order_service.py:280](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/putaway_order_service.py#L280) (`confirm_arrival`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-03.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## WM-04

**Catatan:** Putaway antar-gudang in-transit tidak mengubah bucket stok roll. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Dispatch PA mengubah roll ke transit dan rebuild lokasi asal; arrival memperbarui tujuan sekali. ATP source tidak lagi tetap available.

**Lokasi source kandidat:** [backend/services/putaway_order_service.py:280](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/putaway_order_service.py#L280) (`confirm_arrival`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-04.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## WM-05

**Catatan:** PA dapat berebut roll dan arrival menulis lokasi tanpa prasyarat roll. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** PA mengklaim active_movement per roll; arrival memeriksa PA/source/status yang sama. Dua PA dan stale arrival tidak dapat sama-sama memakai roll.

**Lokasi source kandidat:** [backend/services/putaway_order_service.py:83](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/putaway_order_service.py#L83) (`create_order`); [backend/services/putaway_order_service.py:280](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/putaway_order_service.py#L280) (`confirm_arrival`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-05.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


## WM-06

**Catatan:** Scan picking tidak memvalidasi identitas roll dan menerima qty negatif. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Scan picking memeriksa product/owner/warehouse/bin/reserved_ref serta finite positive qty sebelum increment. HTTP iter114 dan P07 dengan autentikasi yang benar lulus.

**Lokasi source kandidat:** [backend/routers/wms.py:158](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/wms.py#L158) (`scan_task`); [backend/routers/outbound_picking.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/outbound_picking.py).

**Bukti positif:** [followup-suite-results.json](evidence/followup-suite-results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-06.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `1ea1dd82bd19cf36304c9a1cbef735a74f72b932`.


## WM-07

**Catatan:** Stock opname per bin memakai expected seluruh gudang dan membolehkan duplikasi. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Expected opname dihitung dari roll dengan bin/owner/status fisik, duplicate count key dan invalid qty ditolak. P10 dan HTTP iter118 lulus.

**Lokasi source kandidat:** [backend/routers/cycle_count.py:106](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/cycle_count.py#L106) (`add_item`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 7 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-07.md); fase sebelumnya `P10`. Commit implementasi yang diklaim: .


## WM-08

**Catatan:** Adjustment shortage dapat parsial tetapi sesi tetap approved. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Shortage adjustment memakai CAS dan postcondition; residual tidak ditandai approved. Stock drift setelah cutoff membutuhkan recount, bukan adjustment berdasarkan snapshot lama.

**Lokasi source kandidat:** [backend/routers/cycle_count.py:253](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/cycle_count.py#L253) (`approve_session`); [backend/services/roll_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-08.md); fase sebelumnya `P10`. Commit implementasi yang diklaim: .


## WM-09

**Catatan:** Penerimaan exception PA tidak menulis mutasi transfer. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Exception accept PA menulis pasangan transfer movement dan rebuild sumber/tujuan, dengan retry tidak menggandakan perpindahan.

**Lokasi source kandidat:** [backend/services/putaway_order_service.py:329](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/putaway_order_service.py#L329) (`resolve_exception`).

**Bukti positif:** [core-suite-results.json](evidence/core-suite-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/audit/findings/WM-09.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `b25ff3bfe3b6c5c65664e8dae32c85a0a667b942`.


---

# Validasi gelombang 2: 34 catatan

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

Setiap record di bawah telah dibandingkan dengan source kandidat dan bukti pengujian terkait. Status `ready_for_validation` dari agent merupakan klaim implementasi; verdict di laporan ini merupakan hasil review terpisah.

Hasil: 22 Tertutup spesifik, 10 Sebagian, 2 Konfirmasi bisnis.

| ID | Catatan original | Verdict | Temuan lanjutan terkait |
|---|---|---|---|

| [W2-001](#w2-001) | Toleransi jumlah receipt menyebabkan drift nilai roll terhadap GL | Sebagian | V3-MKO-01 |

| [W2-002](#w2-002) | Receipt menerima output warehouse tidak terdaftar | Tertutup spesifik | — |

| [W2-003](#w2-003) | Partial receipt kehilangan lokasi asal saat finalisasi | Tertutup spesifik | — |

| [W2-004](#w2-004) | Cancel bill jasa makloon tidak membalik utang GL | Tertutup spesifik | — |

| [W2-005](#w2-005) | Race potong bon dan pembayaran meloloskan paid melebihi grand | Tertutup spesifik | — |

| [W2-006](#w2-006) | Owner otomatis opname dapat memilih stok entitas di luar scope | Tertutup spesifik | — |

| [W2-007](#w2-007) | Reject stale menimpa approved setelah adjustment stok | Tertutup spesifik | — |

| [W2-008](#w2-008) | Transfer manual A dapat mereservasi roll milik B | Tertutup spesifik | — |

| [W2-009](#w2-009) | Reservasi transfer pilihan roll tidak rebuild balance | Tertutup spesifik | — |

| [W2-010](#w2-010) | Histori pembacaan RFID tidak menerapkan scope owner roll | Tertutup spesifik | — |

| [W2-011](#w2-011) | Race acknowledge versus resolve dapat memundurkan status insiden | Tertutup spesifik | — |

| [W2-012](#w2-012) | Concurrent red reads membuat dua insiden open untuk EPC dan device sama | Tertutup spesifik | — |

| [W2-013](#w2-013) | GRN closed meskipun finalisasi hanya memproses500 dari501 roll | Tertutup spesifik | — |

| [W2-014](#w2-014) | Qty dasar QC dipakai sebagai unit harga PO pada retur supplier | Tertutup spesifik | — |

| [W2-015](#w2-015) | Pelunasan murni deposit melewati posting reklasifikasi GL | Tertutup spesifik | — |

| [W2-016](#w2-016) | Void sumber deposit gagal setelah payment dan kas dibalik | Tertutup spesifik | — |

| [W2-017](#w2-017) | CAS deposit terlambat meninggalkan pembayaran tanpa dana | Sebagian | V3-AR-01 |

| [W2-018](#w2-018) | Void menimpa pembayaran baru dengan snapshot array lama | Tertutup spesifik | — |

| [W2-019](#w2-019) | Split QC menggandakan berat aktual tersimpan | Sebagian | V3-WEIGHT-01 |

| [W2-020](#w2-020) | Refund jual final meskipun buku kas gagal dan retry tidak melengkapi efek | Tertutup spesifik | — |

| [W2-021](#w2-021) | Batas query5000/50000/100000 memotong saldo rekening dan laporan keuangan | Tertutup spesifik | V3-DATE-01 |

| [W2-022](#w2-022) | Payroll paid mengkredit kas GL tanpa transaksi buku kas | Tertutup spesifik | — |

| [W2-023](#w2-023) | Payroll menerima akun beban sebagai sumber pembayaran | Tertutup spesifik | — |

| [W2-024](#w2-024) | WO completed dengan konsumsi bahan terpotong pada5000 roll | Tertutup spesifik | V3-PROD-01 |

| [W2-025](#w2-025) | Scope lini R&D hanya membatasi daftar; detail dan patch sample lintas lini tetap diterima | Tertutup spesifik | — |

| [W2-REQ-01](#w2-req-01) | Histori pelaksana dan hak jenis sampling | Konfirmasi bisnis | — |

| [W2-REQ-02](#w2-req-02) | Tata kelola master, stage, warna dan lot | Sebagian | V3-MASTER-01 |

| [W2-REQ-03](#w2-req-03) | Penegakan seluruh uji wajib untuk SKU hasil MD | Konfirmasi bisnis | — |

| [W2-REQ-04](#w2-req-04) | Angka utama stok grup untuk sales | Sebagian | V3-MRES-01, V3-MRES-02 |

| [W2-REQ-05](#w2-req-05) | Meja kerja MD dengan buyer eksplisit lintas entitas | Sebagian | — |

| [W2-REQ-06](#w2-req-06) | Keputusan selisih penerimaan, notifikasi MD dan rekonsiliasi PO | Sebagian | V3-PO-01, V3-PO-02, V3-PO-03 |

| [W2-REQ-07](#w2-req-07) | Reservasi material sebelum issue makloon | Sebagian | V3-MRES-01, V3-MRES-02 |

| [W2-REQ-08](#w2-req-08) | RFID wajib, cross-dock dan SJ multi-gudang | Sebagian | V3-WMS-02 |

| [W2-REQ-09](#w2-req-09) | Urutan roll, pembulatan dan izin potong | Sebagian | V3-CUT-01 |


## W2-001

**Catatan:** Toleransi jumlah receipt menyebabkan drift nilai roll terhadap GL. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Costing receipt memakai jumlah panjang roll terukur, sehingga declared10/roll9.5 bernilai120.0002 vs GL120, selisih sub-sen. Namun retry output parsial membuat stok15 senilai180 vs GL120. V3-MKO-01.

**Lokasi source kandidat:** [backend/services/makloon_order_service.py:880](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/makloon_order_service.py#L880) (`receive_step`).

**Bukti positif:** [positive-capacity-makloon-results.json](evidence/positive-capacity-makloon-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-MKO-01](04_TEMUAN_LANJUTAN.md#v3-mko-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-001.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-002

**Catatan:** Receipt menerima output warehouse tidak terdaftar. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Warehouse efektif/fallback dan setiap partial arrival divalidasi assert_usable sebelum efek. Warehouse tidak dikenal menghasilkan404, output0 dan jurnal0 pada probe mandiri.

**Lokasi source kandidat:** [backend/services/makloon_order_service.py:880](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/makloon_order_service.py#L880) (`receive_step`); [backend/services/warehouse_scope_service.py:155](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/warehouse_scope_service.py#L155) (`assert_usable`).

**Bukti positif:** [positive-capacity-makloon-results.json](evidence/positive-capacity-makloon-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-002.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-003

**Catatan:** Partial receipt kehilangan lokasi asal saat finalisasi. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Partial receipts menyimpan warehouse kedatangan; final receive membuat roll4 di WH dan roll6 di WH2. Legacy tanpa warehouse/GRN ditolak, bukan dipindahkan berdasarkan asumsi.

**Lokasi source kandidat:** [backend/services/makloon_order_service.py:880](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/makloon_order_service.py#L880) (`receive_step`); [backend/services/goods_receipt_close_service.py:323](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/goods_receipt_close_service.py#L323) (`_post_mko`).

**Bukti positif:** [positive-capacity-makloon-results.json](evidence/positive-capacity-makloon-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-003.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-004

**Catatan:** Cancel bill jasa makloon tidak membalik utang GL. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Generic cancel bill jasa makloon posted diblokir409; AP tetap100000. Koreksi lewat sumber/claim, bukan membatalkan metadata bill tanpa reversal. HTTP positif diuji.

**Lokasi source kandidat:** [backend/routers/vendor_bills.py:669](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/vendor_bills.py#L669) (`cancel_vendor_bill`).

**Bukti positif:** [regression_http_results.json](evidence/w2/regression_http_results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [positive-finance-interleavings-results.json](evidence/positive-finance-interleavings-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-004.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-005

**Catatan:** Race potong bon dan pembayaran meloloskan paid melebihi grand. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Payment CAS membaca grand_total terkini; claim deduction mengurangi bill atomik sebelum GL dan mengompensasi fault. Dua interleaving nyata menolak pembayaran80000 setelah total turun60000; AP tetap60000.

**Lokasi source kandidat:** [backend/routers/vendor_bills.py:491](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/vendor_bills.py#L491) (`pay_vendor_bill`); [backend/services/makloon_claim_service.py:140](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/makloon_claim_service.py#L140) (`approve_claim`).

**Bukti positif:** [positive-finance-interleavings-results.json](evidence/positive-finance-interleavings-results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-005.md); fase sebelumnya `P03`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-006

**Catatan:** Owner otomatis opname dapat memilih stok entitas di luar scope. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Stock owner resolver mempertahankan explicit/preferred owner sah meski kosong dan tidak fallback ke entitas luar allowed_owners. Sesi lama owner asing juga ditolak sebelum adjustment.

**Lokasi source kandidat:** [backend/services/roll_service.py:1668](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L1668) (`resolve_stock_owner`); [backend/routers/cycle_count.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/cycle_count.py).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-006.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-007

**Catatan:** Reject stale menimpa approved setelah adjustment stok. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Reject memakai CAS status submitted dan no saga_lock. Probe HTTP membaca snapshot submitted, proses lain approve, lalu reject409; status tetap approved.

**Lokasi source kandidat:** [backend/routers/cycle_count.py:319](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/cycle_count.py#L319) (`reject_session`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [positive-finance-interleavings-results.json](evidence/positive-finance-interleavings-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-007.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-008

**Catatan:** Transfer manual A dapat mereservasi roll milik B. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Transfer A dengan explicit roll B ditolak oleh owner guard; resolver tidak mengganti owner ke B di luar scope. Diuji bersama AX-04/W2-006.

**Lokasi source kandidat:** [backend/services/roll_service.py:1698](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L1698) (`reserve_rolls_for_wh_transfer`); [backend/routers/transfers.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/transfers.py).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-008.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-009

**Catatan:** Reservasi transfer pilihan roll tidak rebuild balance. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Cabang transfer roll IDs memanggil rebuild; reserved20/available0 sesuai fisik sesudah reservasi, sama dengan cabang quantity.

**Lokasi source kandidat:** [backend/services/roll_service.py:1698](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L1698) (`reserve_rolls_for_wh_transfer`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-009.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-010

**Catatan:** Histori pembacaan RFID tidak menerapkan scope owner roll. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Raw RFID reads mendapat owner scope server yang tidak dapat diganti query caller. HTTP user A tidak membaca row B; admin mengikuti explicit allowed scope.

**Lokasi source kandidat:** [backend/routers/rfid.py:348](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/rfid.py#L348) (`get_reads`); [backend/services/rfid_service.py:271](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_service.py#L271) (`list_reads`).

**Bukti positif:** [regression_http_results.json](evidence/w2/regression_http_results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-010.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-011

**Catatan:** Race acknowledge versus resolve dapat memundurkan status insiden. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Incident acknowledge/resolve memakai conditional status; stale acknowledge tidak menurunkan resolved. Uji konkurensi transition lulus.

**Lokasi source kandidat:** [backend/services/rfid_incident_service.py:110](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_incident_service.py#L110) (`_transition`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-011.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-012

**Catatan:** Concurrent red reads membuat dua insiden open untuk EPC dan device sama. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Open incident memakai dedupe_key EPC/device dan unique partial index; parallel red reads menghasilkan satu open incident. Deployment wajib memastikan indeks dibuat; bootstrap lokal melakukannya.

**Lokasi source kandidat:** [backend/services/rfid_incident_service.py:35](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_incident_service.py#L35) (`create_from_read`); [backend/indexes.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/indexes.py).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-012.md); fase sebelumnya `P07`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-013

**Catatan:** GRN closed meskipun finalisasi hanya memproses500 dari501 roll. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Manifest close memakai cursor utuh. Probe mandiri501 add_counted_roll + close menghasilkan PO received501 dan0 roll receiving; seluruh501 masuk quarantine.

**Lokasi source kandidat:** [backend/services/inbound_complete_service.py:30](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/inbound_complete_service.py#L30) (`complete_task`); [backend/services/goods_receipt_close_service.py:276](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/goods_receipt_close_service.py#L276) (`_post_task`).

**Bukti positif:** [positive-capacity-makloon-results.json](evidence/positive-capacity-makloon-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-013.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-014

**Catatan:** Qty dasar QC dipakai sebagai unit harga PO pada retur supplier. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Qty QC base dikonversi kembali ke unit harga PO; kg memakai berat aktual proporsional dan menyimpan qty_base/unit_base. Original regression meter→kg retur bernilai benar.

**Lokasi source kandidat:** [backend/services/qc_service.py:341](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/qc_service.py#L341) (`_apply_qc_decision`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-014.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-015

**Catatan:** Pelunasan murni deposit melewati posting reklasifikasi GL. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Pelunasan deposit murni menghasilkan reklas Dr uang muka/Cr piutang tanpa kas fiktif; void membaliknya. Service regression dan HTTP targeted lulus.

**Lokasi source kandidat:** [backend/services/gl_service.py:2187](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L2187) (`post_deposit_only_receipt`); [backend/services/gl_service.py:2213](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L2213) (`reverse_deposit_only_receipt`); [backend/services/ar_receipt_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ar_receipt_service.py).

**Uji flow tambahan:** `backend/tests/test_w2_targeted.py`. Lihat tabel hasil/log; nama helper/skenario tidak selalu memakai ID temuan sebagai label.

**Batas bukti runtime:** Tidak ada assertion PASS dengan label ID ini pada parser hasil script. Penerimaan didasarkan pada telaah source dan/atau uji flow berkelompok yang disebut di laporan pengujian; bukan klaim setiap branch ID dieksekusi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-015.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-016

**Catatan:** Void sumber deposit gagal setelah payment dan kas dibalik. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Void sumber deposit melakukan CAS ketersediaan deposit sebelum membalik pembayaran/kas. Deposit terpakai menolak409 tanpa write reversal parsial.

**Lokasi source kandidat:** [backend/services/ar_receipt_service.py:607](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ar_receipt_service.py#L607) (`void_receipt`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-016.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-017

**Catatan:** CAS deposit terlambat meninggalkan pembayaran tanpa dana. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Deposit CAS kini mendahului alokasi SO dan dua receipt bersamaan tidak menghabiskan saldo dua kali. Akan tetapi compensator pada fault insert receipt hanya mengembalikan deposit, SO tetap paid. V3-AR-01. HTTP400 atau409 untuk loser tergantung apakah read sudah melihat saldo terbaru.

**Lokasi source kandidat:** [backend/services/ar_receipt_service.py:413](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ar_receipt_service.py#L413) (`create_receipt`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-AR-01](04_TEMUAN_LANJUTAN.md#v3-ar-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-017.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-018

**Catatan:** Void menimpa pembayaran baru dengan snapshot array lama. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Void pembayaran memakai CAS array payments dengan retry; pembayaran baru yang ditambahkan setelah snapshot tidak hilang.

**Lokasi source kandidat:** [backend/services/ar_receipt_service.py:607](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ar_receipt_service.py#L607) (`void_receipt`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-018.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-019

**Catatan:** Split QC menggandakan berat aktual tersimpan. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Split berurutan membagi berat secara proporsional. Dua split2 dari parent10/3kg memakai snapshot parent sama: berat total3.6kg. Length CAS tidak mengamankan weight snapshot. V3-WEIGHT-01.

**Lokasi source kandidat:** [backend/services/roll_service.py:93](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L93) (`insert_child_roll`); [backend/services/roll_service.py:138](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L138) (`_split_weight`); [backend/services/roll_service.py:155](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L155) (`_set_parent_weight`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-WEIGHT-01](04_TEMUAN_LANJUTAN.md#v3-weight-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-019.md); fase sebelumnya `P02`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-020

**Catatan:** Refund jual final meskipun buku kas gagal dan retry tidak melengkapi efek. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Refund settlement menyimpan progress stock/CN; gagal buku kas menghasilkan409 dengan pending state. Retry melengkapi kas tanpa CN/stok/jurnal ganda; targeted fault test lulus.

**Lokasi source kandidat:** [backend/services/return_service.py:1231](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/return_service.py#L1231) (`settle_return`).

**Uji flow tambahan:** `backend/tests/test_w2_targeted.py`. Lihat tabel hasil/log; nama helper/skenario tidak selalu memakai ID temuan sebagai label.

**Batas bukti runtime:** Tidak ada assertion PASS dengan label ID ini pada parser hasil script. Penerimaan didasarkan pada telaah source dan/atau uji flow berkelompok yang disebut di laporan pengujian; bukan klaim setiap branch ID dieksekusi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-020.md); fase sebelumnya `P05`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-021

**Catatan:** Batas query5000/50000/100000 memotong saldo rekening dan laporan keuangan. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Trial balance, account ledger, bank balance dan financial aggregation memakai seluruh cursor; kapasitas5001 cash/50001 jurnal diuji. Tanggal awal periode tetap bug terpisah V3-DATE-01.

**Lokasi source kandidat:** [backend/services/gl_service.py:2974](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L2974) (`trial_balance`); [backend/services/gl_service.py:3029](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/gl_service.py#L3029) (`account_ledger`); [backend/services/bank_service.py:23](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/bank_service.py#L23) (`_txns_for`); [backend/services/bank_service.py:151](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/bank_service.py#L151) (`account_ledger`); [backend/services/financial_statement_service.py:57](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/financial_statement_service.py#L57) (`_aggregate`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-DATE-01](04_TEMUAN_LANJUTAN.md#v3-date-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-021.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-022

**Catatan:** Payroll paid mengkredit kas GL tanpa transaksi buku kas. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** pay_run menghasilkan cash_transactions idempoten terkait payroll_run selain jurnal GL. Fault buku kas kembali posted untuk retry; pembayaran normal dan saldo ledger diuji.

**Lokasi source kandidat:** [backend/services/hr_payroll_service.py:533](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/hr_payroll_service.py#L533) (`pay_run`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-022.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-023

**Catatan:** Payroll menerima akun beban sebagai sumber pembayaran. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Sumber pembayaran payroll harus akun cash/bank aktif yang memenuhi parent/type efektif. Akun beban ditolak sebelum jurnal/kas.

**Lokasi source kandidat:** [backend/routers/hr_payroll.py:198](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/hr_payroll.py#L198) (`pay_payroll_run`).

**Bukti positif:** [regression_results.json](evidence/w2/regression_results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-023.md); fase sebelumnya `P06`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-024

**Catatan:** WO completed dengan konsumsi bahan terpotong pada5000 roll. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** Probe actual WO menggunakan5001 material rolls dan5001 movements: output5001, consume5001, cost50010. Cap lama5000 benar-benar hilang; durability bahan terpisah masih V3-PROD-01.

**Lokasi source kandidat:** [backend/services/production_service.py:331](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py#L331) (`_consume_material`).

**Bukti positif:** [positive-capacity-makloon-results.json](evidence/positive-capacity-makloon-results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-PROD-01](04_TEMUAN_LANJUTAN.md#v3-prod-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-024.md); fase sebelumnya `P04`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-025

**Catatan:** Scope lini R&D hanya membatasi daftar; detail dan patch sample lintas lini tetap diterima. **Verdict:** Defect original tertutup pada skenario yang diverifikasi.

**Hasil telaah dan dampak:** R&D detail/patch/aksi sample dan spec memakai line_scope.assert_can_touch, bukan hanya filter list. HTTP woven→printing ditolak; akun legacy tanpa scope tetap mengikuti kontrak legacy yang harus dibatasi saat provisioning.

**Lokasi source kandidat:** [backend/routers/rnd.py:101](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/rnd.py#L101) (`_spec_guard`); [backend/routers/rnd.py:111](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/rnd.py#L111) (`_sample_guard`); [backend/services/line_scope.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/line_scope.py).

**Bukti positif:** [regression_http_results.json](evidence/w2/regression_http_results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun); [regression_p08_fase1_results.json](evidence/w2/regression_p08_fase1_results.json) — 3 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/findings/W2-025.md); fase sebelumnya `P01`. Commit implementasi yang diklaim: `uncommitted@base-8934e12`.


## W2-REQ-01

**Catatan:** Histori pelaksana dan hak jenis sampling. **Verdict:** Implementasi ada; kontrak bisnis perlu diratifikasi.

**Hasil telaah dan dampak:** performed_by_user_id/performed_by dibedakan dari recorded_by pada setiap round dan wajib diisi; histori Wiwi/Tita terakomodasi. Permission custom modul+line ada, permission per jenis labdip/proofing/handfeel sengaja tidak ditambahkan menurut DECISIONS repo. Penyesuaian tersebut belum dikonfirmasi oleh user di chat ini.

**Lokasi source kandidat:** [backend/routers/rnd.py:57](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/rnd.py#L57) (`_performer_for`); [backend/routers/rnd.py:111](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/rnd.py#L111) (`_sample_guard`); [backend/routers/rnd.py:535](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/rnd.py#L535) (`submit_round`); [backend/services/rnd_sample_service.py:864](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_sample_service.py#L864) (`submit_round`); [backend/services/custom_role_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/custom_role_service.py); [backend/services/line_scope.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/line_scope.py).

**Bukti positif:** [regression_p08_fase1_results.json](evidence/w2/regression_p08_fase1_results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Kontrak bisnis:** DECISIONS repo menyatakan pilihan implementasi, tetapi belum ada persetujuan human user di sesi ini atas perubahan tersebut. Pertahankan catatan terbuka sampai ratifikasi tercatat.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


## W2-REQ-02

**Catatan:** Tata kelola master, stage, warna dan lot. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Registry membedakan stage yarn/grey/pfd/pfp/finished dari fabric_type/line, internal lot berbeda factory lot, rename beralasan dan preview/apply/rollback master tersedia. Governance batch tidak durable sebelum perubahan produk; gagal insert batch membuat perubahan tanpa snapshot rollback. Mapping kode warna supplier/customer lengkap dan standar naming organisasi masih belum selesai. V3-MASTER-01.

**Lokasi source kandidat:** [backend/services/master_governance_service.py:76](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/master_governance_service.py#L76) (`apply_batch`); [backend/services/master_governance_service.py:118](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/master_governance_service.py#L118) (`rename_product`); [backend/routers/products.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/products.py); [backend/services/lot_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/lot_service.py); [backend/domain_registry.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/domain_registry.py); [backend/services/color_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/color_service.py); [backend/services/supplier_item_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/supplier_item_service.py).

**Bukti positif:** [regression_p08_fase2_6_results.json](evidence/w2/regression_p08_fase2_6_results.json) — 5 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-MASTER-01](04_TEMUAN_LANJUTAN.md#v3-master-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


## W2-REQ-03

**Catatan:** Penegakan seluruh uji wajib untuk SKU hasil MD. **Verdict:** Implementasi ada; kontrak bisnis perlu diratifikasi.

**Hasil telaah dan dampak:** SKU hasil MD memakai required types menurut lini dan ACC; bahan standar create SKU boleh bypass. Sistem mengizinkan uji belum ACC dengan reason5huruf melalui warning override, sesuai DECISIONS repo. User menyebut wajib untuk SKU hasil MD; belum ada persetujuan di chat ini atas kelonggaran tersebut. Jangan tandai kebutuhan wajib tuntas hanya karena uji warn lulus.

**Lokasi source kandidat:** [backend/services/rnd_required_tests.py:54](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_required_tests.py#L54) (`for_sample`); [backend/services/rnd_required_tests.py:61](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_required_tests.py#L61) (`for_spec`); [backend/services/rnd_required_tests.py:73](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_required_tests.py#L73) (`resolve`); [backend/services/rnd_sample_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_sample_service.py); [backend/services/rnd_spec_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_spec_service.py); [backend/services/rnd_catalog_validation.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_catalog_validation.py).

**Bukti positif:** [regression_p08_fase1_results.json](evidence/w2/regression_p08_fase1_results.json) — 8 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Kontrak bisnis:** DECISIONS repo menyatakan pilihan implementasi, tetapi belum ada persetujuan human user di sesi ini atas perubahan tersebut. Pertahankan catatan terbuka sampai ratifikasi tercatat.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


## W2-REQ-04

**Catatan:** Angka utama stok grup untuk sales. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Sales mendapat aggregate grup available/reserved/incoming/ATP tanpa owner labels; eksekusi alokasi tetap owner/interco. Namun cadangan makloon dipotong dengan cap5000 dan guard2000; ATP commitment tidak dapat dinyatakan akurat pada kapasitas/race bahan baru. V3-MRES-01/02. Incoming bukan janji tanggal otomatis.

**Lokasi source kandidat:** [backend/services/material_reservation_service.py:24](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/material_reservation_service.py#L24) (`apply_to_products`); [backend/services/inventory_service.py:14](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/inventory_service.py#L14) (`product_summary`); [backend/routers/products.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/products.py); [backend/services/catalog_access.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/catalog_access.py).

**Bukti positif:** [regression_p08_fase2_6_results.json](evidence/w2/regression_p08_fase2_6_results.json) — 2 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-MRES-01](04_TEMUAN_LANJUTAN.md#v3-mres-01), [V3-MRES-02](04_TEMUAN_LANJUTAN.md#v3-mres-02). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


## W2-REQ-05

**Catatan:** Meja kerja MD dengan buyer eksplisit lintas entitas. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Form PO menampilkan entitas pembeli dan menyediakan switch entitas sah; sessionStorage menyimpan draft lalu remount memulihkan items serta mengosongkan gudang. Ini masih mengganti konteks aplikasi. API owner guard lulus; browser draft/reload nyata tidak berhasil diuji karena runtime browser tidak tersedia. Buyer independen dari konteks global belum dibangun.

**Lokasi source kandidat:** [frontend/src/features/admin/po/POBuyerEntitySwitch.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/admin/po/POBuyerEntitySwitch.jsx); [frontend/src/features/admin/PurchaseOrderManagement.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/features/admin/PurchaseOrderManagement.jsx); [backend/routers/purchase_orders.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/purchase_orders.py).

**Bukti positif:** [regression_p08_fase2_6_results.json](evidence/w2/regression_p08_fase2_6_results.json) — 1 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Batas verifikasi:** Source dan build diperiksa; tindakan browser, reload/draft, download atau interaksi fisik belum dilakukan karena runtime UI tidak dapat diinisialisasi.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


## W2-REQ-06

**Catatan:** Keputusan selisih penerimaan, notifikasi MD dan rekonsiliasi PO. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Task selisih dan notifikasi MD/Finance tersedia; wait dan short-close memiliki jalur. Amend ke960 dari ordered1000/received960 ditolak guard baris diterima. Task juga bisa selesai oleh notes-only amendment meski PO masih waiting_approval. Task lama tidak refresh received dan legacy line duplicate menyatu. V3-PO-01/02/03.

**Lokasi source kandidat:** [backend/services/po_variance_task_service.py:35](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/po_variance_task_service.py#L35) (`ensure_for_po`); [backend/services/po_variance_task_service.py:110](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/po_variance_task_service.py#L110) (`decide`); [backend/services/po_variance_task_service.py:155](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/po_variance_task_service.py#L155) (`close_amendment_tasks`); [backend/services/po_amendment_service.py:225](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/po_amendment_service.py#L225) (`amend_po`); [backend/routers/purchase_orders.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/purchase_orders.py).

**Bukti positif:** [regression_p08_fase2_6_results.json](evidence/w2/regression_p08_fase2_6_results.json) — 7 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-PO-01](04_TEMUAN_LANJUTAN.md#v3-po-01), [V3-PO-02](04_TEMUAN_LANJUTAN.md#v3-po-02), [V3-PO-03](04_TEMUAN_LANJUTAN.md#v3-po-03). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


## W2-REQ-07

**Catatan:** Reservasi material sebelum issue makloon. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Approved PR makloon membuat soft reservation dari recipe yield; PR→MKO memindahkan, issue consumes dan cancel releases. Sales stock protection normal termasuk qty/roll mode ada. Dua reserve_for_pr bersamaan overcommit1400 dari1000, serta sum reservation2001 terpotong2000. Gap keputusan SO→PR tetap belum dijamin oleh reservasi otomatis saat memilih fulfillment. V3-MRES-01/02.

**Lokasi source kandidat:** [backend/services/material_reservation_service.py:54](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/material_reservation_service.py#L54) (`reserve_for_pr`); [backend/services/material_reservation_service.py:94](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/material_reservation_service.py#L94) (`transfer_to_mko`); [backend/services/material_reservation_service.py:102](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/material_reservation_service.py#L102) (`consume_for_issue`); [backend/services/roll_service.py:991](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L991) (`makloon_guard`); [backend/services/makloon_order_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/makloon_order_service.py); [backend/services/purchase_requisition_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/purchase_requisition_service.py).

**Bukti positif:** [regression_p08_fase2_6_results.json](evidence/w2/regression_p08_fase2_6_results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-MRES-01](04_TEMUAN_LANJUTAN.md#v3-mres-01), [V3-MRES-02](04_TEMUAN_LANJUTAN.md#v3-mres-02). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


## W2-REQ-08

**Catatan:** RFID wajib, cross-dock dan SJ multi-gudang. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** RFID required, cross-dock staging dan SJ per shipment tersedia; barang SO-tagged dapat menuju transit tanpa putaway storage. Loading check masih SO-wide, sehingga satu gudang tertahan cut gudang lain. Untagged exception berizin tersedia walau user menyatakan semua barang wajib tag. Perlu ratifikasi policy dan uji fisik printer/driver per gudang. V3-WMS-02.

**Lokasi source kandidat:** [backend/services/loading_check_service.py:26](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/loading_check_service.py#L26) (`start`); [backend/services/loading_check_service.py:165](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/loading_check_service.py#L165) (`dispatch_guard`); [backend/services/shipment_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/shipment_service.py); [backend/services/putaway_order_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/putaway_order_service.py); [backend/services/pdf_service.py](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/pdf_service.py).

**Bukti positif:** [regression_p08_fase2_6_results.json](evidence/w2/regression_p08_fase2_6_results.json) — 4 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-WMS-02](04_TEMUAN_LANJUTAN.md#v3-wms-02). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


## W2-REQ-09

**Catatan:** Urutan roll, pembulatan dan izin potong. **Verdict:** Perbaikan sebagian / acceptance end-to-end belum tuntas.

**Hasil telaah dan dampak:** Preview roll prefix/FEFO memperlihatkan qty akhir/selisih; choice naik/turun/pas eksplisit dan exact_cut membutuhkan permission. Qty faktur mengikuti total roll terpilih. Fault confirm_cut kehilangan qty/reservasi dan retry404, sehingga pilihan potong belum aman end-to-end. V3-CUT-01.

**Lokasi source kandidat:** [backend/services/roll_service.py:573](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L573) (`confirm_cut`); [backend/services/sales_order_helpers.py:77](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/sales_order_helpers.py#L77) (`assert_roll_rounding`); [frontend/src/components/RollPicker.jsx](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/src/components/RollPicker.jsx).

**Bukti positif:** [regression_p08_fase2_6_results.json](evidence/w2/regression_p08_fase2_6_results.json) — 13 assertion positif berlabel terkait (bisa mencakup pengulangan pada rerun). Jumlah assertion bukan coverage seluruh branch.

**Masih terbuka:** [V3-CUT-01](04_TEMUAN_LANJUTAN.md#v3-cut-01). Acceptance terkait harus dijalankan ulang sesudah patch.

**Jejak original:** [catatan/keputusan di repo kandidat](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/docs/audit/wave-2/iterations/2026-10-04-W2-P08-decisions/DECISIONS.md); fase sebelumnya `P08`. Commit implementasi yang diklaim: `1bafcda+P08-fase2-6 (working tree)`.


---

# Temuan terbuka dari validasi kandidat

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

**17 counterexample runtime dan 2 observasi kualitas source/build.** Counterexample memakai service asli dan Mongo sintetis dengan indeks kandidat. Fault injection sengaja menggagalkan write sebelum write terjadi; bukan mock hasil bisnis, bukan data produksi. Barrier menyelaraskan dua worker agar failure window terukur.

Prioritas P1: berpotensi mengubah stok, otorisasi, saldo atau laporan finansial pada flow yang direproduksi. P2: integrasi alur/recovery/reproducibility yang perlu diselesaikan. P3: duplikasi maintainability tanpa perbedaan perilaku saat ini.

| ID | Prioritas | Temuan | Bukti |
|---|---|---|---|

| [V3-PROD-01](#v3-prod-01) | P1 | Konsumsi bahan dapat berulang setelah movement insert gagal | Runtime |

| [V3-PROD-02](#v3-prod-02) | P1 | Reversal dianggap selesai sebelum panjang roll dipulihkan | Runtime |

| [V3-MRES-01](#v3-mres-01) | P1 | Dua PR mencadangkan bahan lebih banyak daripada stok | Runtime |

| [V3-AR-01](#v3-ar-01) | P1 | Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh | Runtime |

| [V3-BANK-01](#v3-bank-01) | P1 | Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh | Runtime |

| [V3-WEIGHT-01](#v3-weight-01) | P1 | Split bersamaan menggandakan berat walaupun panjang benar | Runtime |

| [V3-PO-01](#v3-po-01) | P2 | Task selisih PO tidak refresh dan kehilangan identitas baris | Runtime |

| [V3-MKO-01](#v3-mko-01) | P1 | Retry penerimaan maklon menambah output fisik dan nilai stok | Runtime |

| [V3-RFID-01](#v3-rfid-01) | P1 | Read green dari passage lama dipakai kembali pada passage baru | Runtime |

| [V3-CF-01](#v3-cf-01) | P1 | Jurnal campuran kas/nonkas menghasilkan klasifikasi arus kas salah | Runtime |

| [V3-DATE-01](#v3-date-01) | P1 | Jurnal date-only pada awal periode hilang dari laporan | Runtime |

| [V3-WMS-02](#v3-wms-02) | P1 | Loading gudang siap ditahan oleh pending cut gudang lain | Runtime |

| [V3-MASTER-01](#v3-master-01) | P2 | Apply master mengubah produk sebelum snapshot batch durable | Runtime |

| [V3-PO-02](#v3-po-02) | P2 | Pilihan amend ke jumlah diterima bertentangan dengan guard PO lama | Runtime |

| [V3-CUT-01](#v3-cut-01) | P1 | Gagal membuat child cut menghilangkan stok dan reservasi | Runtime |

| [V3-MRES-02](#v3-mres-02) | P1 | Total cadangan maklon tetap terpotong pada batas query | Runtime |

| [V3-PO-03](#v3-po-03) | P1 | Tugas selisih selesai meski amendment belum disetujui dan qty belum berubah | Runtime |

| [V3-DUP-01](#v3-dup-01) | P3 | Helper _clean_perms didefinisikan dua kali | Statis |

| [V3-BUILD-01](#v3-build-01) | P2 | Dependency build frontend tidak mempunyai lockfile terlacak | Statis |


## V3-PROD-01

**P1 — Konsumsi bahan dapat berulang setelah movement insert gagal**

**Kaitan catatan lama:** GN-06, GN-11, W2-024. Status: **open / confirmed**.

**Lokasi:** [backend/services/production_service.py:363](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py#L363); fungsi `_consume_material` mulai baris 331.

**Potongan kode kandidat:**

```python
 360:             if not won:
 361:                 continue  # roll berubah/di-hold bersamaan — dicoba lagi di putaran berikut
 362:             uc = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
 363:             await db.inventory_movements.insert_one({
 364:                 "id": new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
 365:                 "owner_entity_id": owner_entity_id, "movement_type": "production_consume",
 366:                 "quantity": -take, "unit": r.get("unit", "meter"), "lot": r.get("lot", ""),
 367:                 "lot_id": r.get("lot_id", ""), "roll_id": r["id"], "unit_cost": uc,
 368:                 "qty_rolls": 1, "source_document": wo_id, "operation_id": op_id, "timestamp": now_iso(),
 369:             })
 370:             value += take * uc
 371:             if r.get("lot_id") and r["lot_id"] not in lot_ids:
```

**Kesalahan/akar masalah:** CAS mengurangi roll sebelum journal inventory_movements ditulis. Recovery menghitung konsumsi dari movement; write yang gagal tidak tercatat, sehingga retry mengonsumsi lagi.

**Asal perubahan vs baseline W2:** Fungsi berubah terhadap baseline W2. Failure window kandidat dikonfirmasi; tanpa differential runtime pada tiap commit, perubahan ini belum membuktikan bug pertama kali lahir pada satu commit tertentu.

**Reproduksi dan dampak:** Stok20→15 saat gagal insert movement; retry20→10 untuk output5, sementara movement/reported consumption hanya5. Tidak ada crash sesudah commit yang diasumsikan: fault terjadi sebelum insert.

**Output aktual tersimpan:**

```json
{
  "error": "RuntimeError",
  "before_qty": 20,
  "after_fault_qty": 15.0,
  "after_retry_qty": 10.0,
  "output": 5.0,
  "reported_consumed": 5.0,
  "movement_qty": 5.0
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-PROD-01 tanpa merusak invariant gelombang 1/2. Buat operasi konsumsi per material/roll dengan identity stabil dan state durable sebelum efek, lalu lakukan perubahan fisik dan ledger dalam transaksi atau step idempoten yang dapat direkonsiliasi. Jangan menyelesaikan recovery hanya dari movement yang mungkin belum lahir. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Fault sebelum/sesudah tiap write, retry key sama/berbeda dan dua worker: stok20→15, output5, movement5 tepat sekali. Recovery harus bekerja melalui endpoint sah; penghapusan lock di probe hanya kontrol pemulihan lokal.


## V3-PROD-02

**P1 — Reversal dianggap selesai sebelum panjang roll dipulihkan**

**Kaitan catatan lama:** GN-06, GN-11. Status: **open / confirmed**.

**Lokasi:** [backend/services/production_service.py:389](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/production_service.py#L389); fungsi `reverse_operation` mulai baris 383.

**Potongan kode kandidat:**

```python
 386:     async for m in db.inventory_movements.find(
 387:             {"operation_id": op_id, "movement_type": "production_consume", "reversed": {"$ne": True}}, {"_id": 0}):
 388:         mark = await db.inventory_movements.update_one(
 389:             {"id": m["id"], "reversed": {"$ne": True}}, {"$set": {"reversed": True, "reversed_at": now_iso()}})
 390:         if mark.modified_count != 1:
 391:             continue
 392:         qty = -float(m["quantity"])
 393:         await db.inventory_rolls.update_one({"id": m["roll_id"]}, [
 394:             {"$set": {"status": {"$cond": [{"$eq": ["$status", "consumed"]}, "available", "$status"]},
 395:                       "length_remaining": {"$round": [{"$add": ["$length_remaining", qty]}, 2]},
 396:                       "updated_at": now_iso()}}])
 397:         await db.inventory_movements.insert_one({
```

**Kesalahan/akar masalah:** Movement ditandai reversed sebelum update stok. Kalau update stok gagal, retry mengecualikan movement tersebut dan tidak melakukan restore.

**Asal perubahan vs baseline W2:** Fungsi ini belum ada di baseline W2; failure berada pada helper/alur baru kandidat.

**Reproduksi dan dampak:** Roll tersisa5 dari awal10; restore gagal sebelum update. Retry restored0, roll tetap5 dan movement reversed=true.

**Output aktual tersimpan:**

```json
{
  "retry_restored": 0.0,
  "remaining": 5,
  "movement_reversed": true
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-PROD-02 tanpa merusak invariant gelombang 1/2. Claim reversal dengan token/stage dan stable operation ID. Commit restore stock dengan marker yang sama secara atomik, atau simpan progress yang membedakan claimed dari applied; retry memeriksa kontribusi aktual. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Restore operasi5 selalu menghasilkan roll10, satu reversal movement dan projection10, termasuk fault restore dan dua worker; jangan double-increment saat response hilang.


## V3-MRES-01

**P1 — Dua PR mencadangkan bahan lebih banyak daripada stok**

**Kaitan catatan lama:** W2-REQ-07, W2-REQ-04. Status: **open / confirmed**.

**Lokasi:** [backend/services/material_reservation_service.py:79](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/material_reservation_service.py#L79); fungsi `reserve_for_pr` mulai baris 54.

**Potongan kode kandidat:**

```python
  76:         if not pid or need <= 0:
  77:             continue
  78:         entity_id = pr.get("entity_id") or ""
  79:         free = await free_for_commitment(pid, entity_id)
  80:         qty = round(min(need, free), 3)
  81:         doc = {"id": new_id("mres"), "product_id": pid, "owner_entity_id": entity_id,
  82:                "ref_type": "purchase_requisition", "ref_id": pr_id, "pr_id": pr_id, "pr_number": pr.get("number"),
  83:                "pr_line_no": line_no, "output_product_id": line["product_id"],
  84:                "target_output_qty": pre.get("target_output_qty"), "recipe": pre.get("recipe"),
  85:                "required_qty": need, "qty": qty, "shortage_qty": round(need - qty, 3),
  86:                "source_ref_id": pr.get("source_ref_id") or "", "status": ACTIVE,
  87:                "created_by": actor_name, "created_at": now_iso(), "history": [
```

**Kesalahan/akar masalah:** free_for_commitment dibaca lalu material_reservations diinsert tanpa claim capacity atau unique reservation logical key. Dua PR dapat membaca jumlah bebas sama.

**Asal perubahan vs baseline W2:** File/service belum ada di baseline W2; failure berasal dari alur yang ditambahkan pada kandidat.

**Reproduksi dan dampak:** Dua approved PR masing-masing700, recipe yield1 dan stok1000 menghasilkan active reservation1400; shortage0 pada kedua PR. Barrier hanya menyelaraskan read, tetap memanggil helper asli.

**Output aktual tersimpan:**

```json
{
  "on_hand_available": 1000,
  "reserved": 1400.0,
  "shortage": 0.0,
  "pr_count": 2
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-MRES-01 tanpa merusak invariant gelombang 1/2. Serialisasi commitment pada key product+owner+unit dan dimensi gudang bila relevan. Reservasi harus CAS terhadap ledger kapasitas yang konsisten dengan sales/MKO; unique PR line/version untuk retry; shortage dilaporkan eksplisit. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Parallel700+700 atas1000 tidak pernah reserved>1000. Remaining400 harus shortage/backorder/approval sesuai policy, tidak dianggap tersedia. Uji race dengan SO, issue/cancel/replan dan input UOM berbeda.


## V3-AR-01

**P1 — Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh**

**Kaitan catatan lama:** FN-10, W2-017. Status: **open / confirmed**.

**Lokasi:** [backend/services/ar_receipt_service.py:448](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/ar_receipt_service.py#L448); fungsi `create_receipt` mulai baris 413.

**Potongan kode kandidat:**

```python
 445:     receipt_id = new_id("arc")
 446:     number = await next_doc_number("ar_receipts", "number", "AR-", entity_id=entity_id)
 447:     # W2-017 — dana deposit DIRESERVASI (CAS) sebelum alokasi SO; gagal → 409 tanpa efek apa pun.
 448:     await _adjust_deposit(customer["id"], -use_deposit_amount)
 449:     try:
 450:         return await _create_receipt_after_reserve(payload, actor, customer, amount, use_deposit_amount,
 451:                                                    total_funds, method, receipt_date, entity_id,
 452:                                                    receipt_id, number)
 453:     except BaseException:
 454:         if not await db.ar_receipts.find_one({"id": receipt_id}, {"_id": 1}):
 455:             await _adjust_deposit(customer["id"], use_deposit_amount)   # kompensasi reservasi
 456:         raise
```

**Kesalahan/akar masalah:** Receipt mengurangi deposit, mengalokasikan payments ke SO, baru insert receipt. Except mengembalikan deposit tetapi tidak membatalkan alokasi SO. Tidak ada receipt durable untuk resume.

**Asal perubahan vs baseline W2:** Fungsi berubah terhadap baseline W2. Failure window kandidat dikonfirmasi; tanpa differential runtime pada tiap commit, perubahan ini belum membuktikan bug pertama kali lahir pada satu commit tertentu.

**Reproduksi dan dampak:** Saldo deposit100; fault sebelum insert ar_receipts: SO paid_total100/payments1, customer deposit100, receipt count0. Saldo yang sama bisa dipakai lagi.

**Output aktual tersimpan:**

```json
{
  "error": "RuntimeError('Synthetic receipt insert fault BEFORE write')",
  "paid_total": 100.0,
  "payments": 1,
  "deposit": 100.0,
  "receipts": 0
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-AR-01 tanpa merusak invariant gelombang 1/2. Persist receipt operation sebelum allocations. Setiap alokasi harus terkait stable receipt ID dan dapat resume/compensate tanpa menghapus payment milik operasi lain. Tangani insert/GL/cash/deposit sebagai satu protokol durable. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Fault sebelum receipt insert, setelah SO allocation, sebelum/sesudah GL dan saat rollback. Akhir harus semua effect100 tepat sekali atau semua batal; tidak ada SO paid tanpa receipt/deposit konsumsi. Uji multi-SO dan pembayaran bersamaan.


## V3-BANK-01

**P1 — Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh**

**Kaitan catatan lama:** CX-07, CX-06. Status: **open / confirmed**.

**Lokasi:** [backend/services/bank_recon_service.py:614](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/bank_recon_service.py#L614); fungsi `_link` mulai baris 588.

**Potongan kode kandidat:**

```python
 611:             raise ValueError("Sisa transaksi buku tidak cukup (baru saja dipakai proses lain / alokasi ganda).")
 612:         claimed.append({"txn_id": a["txn_id"], "amount": amt})
 613:     txn_ids = [a["txn_id"] for a in allocations]
 614:     await db.bank_statement_lines.update_one({"id": line["id"]}, {"$set": {
 615:         "status": "matched", "match_kind": match_kind,
 616:         "matched_txn_id": txn_ids[0] if len(txn_ids) == 1 else "",
 617:         "matched_txn_ids": txn_ids, "allocations": allocations,
 618:         "match_type": match_type, "matched_at": now, "matched_by": actor,
 619:         "updated_at": now}})
 620:     for a in allocations:
 621:         t = await db.cash_transactions.find_one({"id": a["txn_id"]}, {"_id": 0})
 622:         if not t:
```

**Kesalahan/akar masalah:** CAS membatasi capacity cash transaction, tetapi statement line ditulis berdasarkan ID tanpa claim status/version/capacity yang sama. Dua transaksi berbeda dapat sama-sama mengklaim line bank.

**Asal perubahan vs baseline W2:** Fungsi berubah terhadap baseline W2. Failure window kandidat dikonfirmasi; tanpa differential runtime pada tiap commit, perubahan ini belum membuktikan bug pertama kali lahir pada satu commit tertentu.

**Reproduksi dan dampak:** Statement100; dua manual_match berbeda100+100: line allocated100, cash reconciled200, kedua cash mencantumkan matched_line_ids BL.

**Output aktual tersimpan:**

```json
{
  "statement_amount": 100,
  "statement_allocated": 100.0,
  "cash_reconciled": 200.0,
  "linked_cash_count": 2
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-BANK-01 tanpa merusak invariant gelombang 1/2. Claim kedua sisi allocation dengan stable match operation dan transaksi/compensation idempoten. Revalidate statement remaining setelah claim; jangan hanya melindungi tiap cash record. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Dua matching paralel atas line100: satu sukses dan satu conflict atau total allocated100. Jumlah dari statement links harus sama dengan cash links. Uji split, duplicate payload, unlink/rerun/fault antar-write.


## V3-WEIGHT-01

**P1 — Split bersamaan menggandakan berat walaupun panjang benar**

**Kaitan catatan lama:** W2-019, WM-01. Status: **open / confirmed**.

**Lokasi:** [backend/services/roll_service.py:163](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L163); fungsi `_set_parent_weight` mulai baris 155.

**Potongan kode kandidat:**

```python
 160:         s["secondary_measures.kg"] = weight
 161:         parent["secondary_measures"] = {**parent["secondary_measures"], "kg": weight}
 162:     parent["weight_kg"] = weight
 163:     await db.inventory_rolls.update_one({"id": parent.get("id")}, {"$set": s})
 164: 
 165: 
 166: # ── Taksonomi status (KN_15 §3.4) ────────────────────────────────────────────
 167: # Bucket FISIK di gudang (menyusun on_hand)
 168: from services.tolerances import QTY_EPS  # KN-A13 — toleransi bersama
 169: 
 170: # KN-A11 — SATU definisi "PO masih terbuka / stok dalam perjalanan" untuk papan Stok/ATP,
 171: # Fulfillment Wizard, dan stock_bucket. `waiting_approval` sengaja TIDAK dihitung (belum
```

**Kesalahan/akar masalah:** insert_child_roll menghitung berat dari snapshot parent lama dan menulis sisa dengan $set; length CAS terpisah tidak menjaga weight total.

**Asal perubahan vs baseline W2:** Fungsi ini belum ada di baseline W2; failure berada pada helper/alur baru kandidat.

**Reproduksi dan dampak:** Parent10m/3kg dipotong2m dua kali: parent6m/2.4kg, dua child masing-masing0.6kg; total3.6kg, seharusnya3kg. Panjang6+2+2 tetap10.

**Output aktual tersimpan:**

```json
{
  "initial_length": 10,
  "remaining_length": 6.0,
  "initial_weight": 3,
  "parent_weight": 2.4,
  "child_weights": [
    0.6,
    0.6
  ],
  "total_weight": 3.5999999999999996
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-WEIGHT-01 tanpa merusak invariant gelombang 1/2. Simpan reservasi/split berat dan panjang dalam satu conditional update berdimensi version atau ledger cut dengan snapshot terkini. Tidak boleh menulis derived parent weight dari snapshot lama. Tandai estimated_proportional sebagai estimasi, bukan penimbangan aktual. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Parallel split2+2: parent6m/1.8kg dan children0.6+0.6kg. Uji split QC/retur/cut, decimal rounding dan actual reweigh; conservation kg dan meter diuji terpisah.


## V3-PO-01

**P2 — Task selisih PO tidak refresh dan kehilangan identitas baris**

**Kaitan catatan lama:** W2-REQ-06, FN-02. Status: **open / confirmed**.

**Lokasi:** [backend/services/po_variance_task_service.py:51](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/po_variance_task_service.py#L51); fungsi `ensure_for_po` mulai baris 35.

**Potongan kode kandidat:**

```python
  48:         short = round(ordered - received, 2)
  49:         if received <= 0 or short <= ordered * tol / 100 + 1e-6:
  50:             continue
  51:         key = {"po_id": po_id, "product_id": it.get("product_id"), "status": "open"}
  52:         if await db.po_variance_tasks.find_one(key, {"_id": 1}):
  53:             continue
  54:         task = {
  55:             "id": new_id("pvt"), **key, "entity_id": po.get("entity_id"),
  56:             "po_number": po.get("po_number"), "supplier_name": po.get("supplier_name"),
  57:             "product_name": it.get("product_name") or it.get("name") or "", "unit": it.get("unit", ""),
  58:             "ordered_qty": ordered, "received_qty": received, "short_qty": short, "tolerance_pct": tol,
  59:             "unit_price": float(it.get("unit_price") or it.get("price") or 0),
```

**Kesalahan/akar masalah:** Key task memakai product_id, bukan line_id, dan existing task langsung continue. Received yang berubah tidak memperbarui task/suggested qty. Duplicate product pada PO baru diblokir KN-B15, tetapi dokumen historis masih dapat memiliki dua baris.

**Asal perubahan vs baseline W2:** File/service belum ada di baseline W2; failure berasal dari alur yang ditambahkan pada kandidat.

**Reproduksi dan dampak:** Task awal received90/short10; setelah received95 task tetap90/10. Fixture legacy dua line MAT dengan shortage5 dan100 menghasilkan satu task. Staleness berlaku juga PO satu line biasa.

**Output aktual tersimpan:**

```json
{
  "actual_shortages": [
    5,
    100
  ],
  "task_count": 1,
  "task_received": 90.0,
  "task_short": 10.0,
  "live_first_received": 95
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Data legacy:** Duplicate product dalam PO baru sudah ditolak guard kandidat. Counterexample duplicate line menyasar dokumen historis; task stale setelah receipt95 menyasar PO biasa satu baris.

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-PO-01 tanpa merusak invariant gelombang 1/2. Key task harus stable PO line ID/version. Refresh ordered/received/short dan close task bila selesai; keputusan memakai revalidation PO terkini. Migrasi legacy duplicate secara eksplisit, jangan menggabungkan dua harga. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Terima90 lalu95: open task received95/short5, amendment suggestion95. Terima100 menutup obsolete task. Dua legacy line memberi dua task. Race receipt vs decide tidak memakai qty lama.


## V3-MKO-01

**P1 — Retry penerimaan maklon menambah output fisik dan nilai stok**

**Kaitan catatan lama:** CX-13, W2-001, GN-11. Status: **open / confirmed**.

**Lokasi:** [backend/services/makloon_order_service.py:1093](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/makloon_order_service.py#L1093); fungsi `receive_step` mulai baris 880.

**Potongan kode kandidat:**

```python
1090:     _mko_ref = {"type": "makloon_order", "id": mko_id,
1091:                 "number": f"{order.get('mko_number')} step{seq}"}
1092:     _last = len(rolls_in) - 1
1093:     for _i, r in enumerate(rolls_in if not prog.get("lots") else []):
1094:         _len = round(float(r["length"]), 2)
1095:         _uc = out_uc
1096:         if _i == _last and _len > 0:
1097:             _prior = sum(round(round(float(x["length"]), 2) * out_uc, 2) for x in rolls_in[:_last])
1098:             _uc = round((output_value - _prior) / _len, 6)
1099:         roll = await create_inbound_roll(
1100:             out_pid, r.get("warehouse_id") or out_wh, entity_id, _len,
1101:             lot=str(r["lot"]).strip(), unit=step.get("output_unit") or "meter",
```

**Kesalahan/akar masalah:** Progress lots disimpan sesudah seluruh loop output. Output pertama yang sudah dibuat tidak tersimpan dalam progress jika pembuatan kedua gagal. Retry membuat seluruh roll lagi.

**Asal perubahan vs baseline W2:** Fungsi berubah terhadap baseline W2. Failure window kandidat dikonfirmasi; tanpa differential runtime pada tiap commit, perubahan ini belum membuktikan bug pertama kali lahir pada satu commit tertentu.

**Reproduksi dan dampak:** Input10, dua output5; fault sebelum create output kedua:1roll. Retry:3roll=15; inventory value180 sedangkan jurnal receipt120 untuk output10.

**Output aktual tersimpan:**

```json
{
  "error": "RuntimeError('Synthetic second output failure BEFORE write')",
  "rolls_after_fault": 1,
  "rolls_after_retry": 3,
  "expected_output": 10,
  "actual_output": 15.0,
  "roll_value": 180.0,
  "journal_value": 120.0
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-MKO-01 tanpa merusak invariant gelombang 1/2. Beri deterministic roll identity per operation+receipt line/index sebelum loop. Persist plan dan state tiap output sebelum/bersama creation; resume harus reconcile actual roll dan movement sebelum membuat lagi. Simpan original warehouse/lot/cost snapshot. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Fault pada output1/2/N serta setelah jurnal/status: output total10 dan dua roll saja, inventory value sama GL120. Uji partial multi-gudang, duplicate lot input, response-lost dan authorized saga recovery.


## V3-RFID-01

**P1 — Read green dari passage lama dipakai kembali pada passage baru**

**Kaitan catatan lama:** RF-02, RF-16. Status: **open / confirmed**.

**Lokasi:** [backend/services/rfid_ingest_service.py:149](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rfid_ingest_service.py#L149); fungsi `ingest` mulai baris 118.

**Potongan kode kandidat:**

```python
 146:     dwell_cut = (_ts(now) - timedelta(seconds=DWELL_S)).isoformat()
 147:     results, reads = [], []
 148:     for raw in fresh:
 149:         prev = await db.rfid_reads.find_one({"device_id": device["id"], "epc": raw, "timestamp": {"$gte": dwell_cut}},
 150:                                             {"_id": 0}, sort=[("timestamp", -1)])
 151:         if prev:  # tag diam / passage sama — bukan event bisnis baru (tanpa insiden baru)
 152:             await db.rfid_reads.update_one({"id": prev["id"]}, {"$set": {"last_observed_at": now},
 153:                                                                "$inc": {"observation_count": 1}})
 154:             results.append({"epc": raw, "result": prev["result"], "code": prev.get("code"), "reason": prev["reason"],
 155:                             "action": prev.get("action"),
 156:                             "roll_no": prev.get("roll_no"), "sku": prev.get("sku"),
 157:                             "product_name": prev.get("product_name"), "duplicate": True, "read_id": prev["id"]})
```

**Kesalahan/akar masalah:** Cache dwell120detik mengembalikan verdict read sebelumnya sebelum evaluator dijalankan. Passage window10detik; event_id baru20detik kemudian membentuk passage baru tetapi tetap memakai verdict lama.

**Asal perubahan vs baseline W2:** Fungsi berubah terhadap baseline W2. Failure window kandidat dikonfirmasi; tanpa differential runtime pada tiap commit, perubahan ini belum membuktikan bug pertama kali lahir pada satu commit tertentu.

**Reproduksi dan dampak:** Event pertama green dan mencatat gate_exit. Sesudah SO cancelled, event UUID baru pada gate sama+20detik tetapgreen duplicate=true dan passage ID berbeda; evaluator state sekarang red REPLAY_EXIT.

**Output aktual tersimpan:**

```json
{
  "first": "green",
  "fresh_event_after_seconds": 20,
  "second": "green",
  "duplicate": true,
  "current_evaluator_result": "red",
  "current_evaluator_code": "REPLAY_EXIT",
  "different_passage": true
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Batas interpretasi:** Yang terukur adalah `results[].result=green` dan `duplicate=true` untuk event baru. Source passage counter hanya menambah read baru, sehingga ini tidak membuktikan siren/barrier fisik membuka atau UI passage baru menampilkan green. Ketiadaan evaluasi ulang dan disagreement dengan evaluator merupakan bug yang terbukti.

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-RFID-01 tanpa merusak invariant gelombang 1/2. Bedakan replay event ID dan noisy repeated sensor read dari otorisasi passage baru. Cache tidak boleh melintasi passage atau versi shipment/QC/tag; evaluasi ulang current state untuk event baru yang memulai passage. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Same-gate event berbeda pada+20detik harus red ketika replay exit/SO cancelled/tag retired/QC hold. Repeated event_id tetap idempoten. Dwell dalam passage tidak menggandakan mutation/incident; worst verdict passage tetap red.


## V3-CF-01

**P1 — Jurnal campuran kas/nonkas menghasilkan klasifikasi arus kas salah**

**Kaitan catatan lama:** FN-04. Status: **open / confirmed**.

**Lokasi:** [backend/services/cash_flow_service.py:84](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/cash_flow_service.py#L84); fungsi `cash_flow_statement` mulai baris 55.

**Potongan kode kandidat:**

```python
  81:     noncash: Dict[str, float] = {}
  82:     async for je in db.journal_entries.find(q, {"_id": 0, "lines": 1}):
  83:         lines = [ln for ln in je.get("lines", []) if ln.get("account_code")]
  84:         touches_cash = any(ln["account_code"] in cash for ln in lines)
  85:         for ln in lines:
  86:             code = ln["account_code"]
  87:             if code in cash:
  88:                 continue
  89:             eff = -(float(ln.get("debit", 0) or 0) - float(ln.get("credit", 0) or 0))
  90:             sec = _section(amap.get(code, {}).get("type", ""), code)
  91:             if touches_cash:
  92:                 buckets[sec][code] = buckets[sec].get(code, 0.0) + eff
```

**Kesalahan/akar masalah:** Bila satu jurnal menyentuh kas, semua contra line dimasukkan bucket aktivitas. Aset yang sebagian dibayar kas dan sebagian AP dianggap seluruhnya cash investing serta AP dianggap cash operating.

**Asal perubahan vs baseline W2:** Fungsi berubah terhadap baseline W2. Failure window kandidat dikonfirmasi; tanpa differential runtime pada tiap commit, perubahan ini belum membuktikan bug pertama kali lahir pada satu commit tertentu.

**Reproduksi dan dampak:** Jurnal Dr aset100/Cr kas40/Cr AP60 menghasilkan investing−100, operating+60, net−40 dan noncash disclosure kosong. Seharusnya investing−40, operating0 dan noncash asset60.

**Output aktual tersimpan:**

```json
{
  "expected_investing": -40,
  "expected_operating": 0,
  "expected_noncash_asset": 60,
  "actual_investing": -100.0,
  "actual_operating": 60.0,
  "net_change": -40.0,
  "noncash": []
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-CF-01 tanpa merusak invariant gelombang 1/2. Klasifikasi sumber harus membawa settlement cash portion yang eksplisit. Pecah source/mixed journal secara traceable; jangan memperkirakan aktivitas dari seluruh contra balance. Reconcile total kas dan disclosure noncash terpisah. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Fixture asset cash40+credit60 harus CFI−40/CFO0/noncash60. Tambahkan asset penuh kredit, cash penuh, bank-to-bank, depreciation, sale credit+receipt dan mixed multiple assets/liabilities. Persetujuan policy akuntan diperlukan untuk metode alokasi ambigu.


## V3-DATE-01

**P1 — Jurnal date-only pada awal periode hilang dari laporan**

**Kaitan catatan lama:** FN-16, W2-021. Status: **open / confirmed**.

**Lokasi:** [backend/services/financial_statement_service.py:31](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/financial_statement_service.py#L31); fungsi `_day_start` mulai baris 28.

**Potongan kode kandidat:**

```python
  28: def _day_start(d: Optional[str]) -> Optional[str]:
  29:     if not d:
  30:         return None
  31:     return d if "T" in d else f"{d}T00:00:00"
  32: 
  33: 
  34: def _day_end(d: Optional[str]) -> Optional[str]:
  35:     if not d:
  36:         return None
  37:     return d if "T" in d else f"{d}T23:59:59.999999"
  38: 
  39: 
```

**Kesalahan/akar masalah:** Insert jurnal mempertahankan date yang dikirim, termasuk YYYY-MM-DD. Query start membuat string YYYY-MM-DDT00:00:00; lexical compare mengeluarkan date-only hari pertama.

**Asal perubahan vs baseline W2:** Body fungsi tetap sama menurut AST terhadap baseline W2; masalah ini residual atau konflik integrasi baru, bukan bukti fungsi lama berubah menjadi salah.

**Reproduksi dan dampak:** Valid journal beban10 pada2026-09-01, laporan2026-09-01..30: opex0, seharusnya10. Nilai tersimpan masih date-only; probe CF lain memakai ISO timestamp agar kesalahan klasifikasi tidak tercampur.

**Output aktual tersimpan:**

```json
{
  "expected_opex": 10,
  "actual_opex": 0,
  "stored_date": "2026-09-01",
  "filter_start": "2026-09-01T00:00:00"
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-DATE-01 tanpa merusak invariant gelombang 1/2. Gunakan representasi tanggal kanonik di seluruh entry/create/autopost/import dan query, dengan timezone bisnis disepakati. Migration preview tanggal lama dan conflict report; hindari mengubah label saja atau memperlebar cutoff tanpa aturan. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Date-only/ISO/tz-offset hari awal dan hari akhir periode masuk tepat sekali. Neraca default, ledger, cash flow, closing, unlock dan konsolidasi memakai cutoff sama. Uji jurnal masa depan tetap tidak masuk hari ini.


## V3-WMS-02

**P1 — Loading gudang siap ditahan oleh pending cut gudang lain**

**Kaitan catatan lama:** RF-06, W2-REQ-08. Status: **open / confirmed**.

**Lokasi:** [backend/services/loading_check_service.py:38](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/loading_check_service.py#L38); fungsi `start` mulai baris 26.

**Potongan kode kandidat:**

```python
  35:     if existing:
  36:         return safe_doc(existing)
  37:     from services.roll_service import assert_cut_identity_ready
  38:     await assert_cut_identity_ready(order_id)  # WM-02 — potong dikonfirmasi & tag anak terverifikasi
  39:     rolls = await _expected_rolls(order_id)
  40:     if not rolls:
  41:         raise HTTPException(status_code=400, detail="Tidak ada roll ter-alokasi untuk SO ini (pick dulu).")
  42:     tag_ids = [r["rfid_tag_id"] for r in rolls if r.get("rfid_tag_id")]
  43:     tags = {t["id"]: t for t in await db.rfid_tags.find(
  44:         {"id": {"$in": tag_ids}, "status": "active"}, {"_id": 0}).to_list(2000)}
  45:     expected, untagged = [], []
  46:     for r in rolls:
```

**Kesalahan/akar masalah:** Start loading check memanggil guard atas seluruh SO dan API tidak memberi warehouse/shipment subset. SO-wide session mencampurkan readiness shipment yang berbeda.

**Asal perubahan vs baseline W2:** Fungsi berubah terhadap baseline W2. Failure window kandidat dikonfirmasi; tanpa differential runtime pada tiap commit, perubahan ini belum membuktikan bug pertama kali lahir pada satu commit tertentu.

**Reproduksi dan dampak:** Satu tagged committed roll diWH siap; pending cut product lain diWH2. Guard local WH lulus, start loading check SO409: satu reservasi potong belum dikonfirmasi di gudang lain.

**Output aktual tersimpan:**

```json
{
  "local_ready_tagged_rolls": 1,
  "local_cut_guard": "passed",
  "pending_cuts_other_warehouse": 1,
  "loading_check_start_error": "409: 1 reservasi potong belum dikonfirmasi (roll induk RL-00010). Potong fisik & konfirmasi dulu."
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-WMS-02 tanpa merusak invariant gelombang 1/2. Bentuk loading session per shipment/task group+warehouse+manifest version. Expected EPC dan cut guard hanya untuk shipment itu; perubahan manifest mengharuskan check ulang. Parent SO menampilkan agregat progres, bukan satu clean global. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** SO woven/knit/printing tiga gudang: WHwoven dapat check/dispatch/SJ sendiri saat cut WHknit tertunda. Check A tidak membuka B. Shipment parsial dan driver gabungan tetap mempunyai manifest dokumen yang konsisten.


## V3-MASTER-01

**P2 — Apply master mengubah produk sebelum snapshot batch durable**

**Kaitan catatan lama:** W2-REQ-02. Status: **open / confirmed**.

**Lokasi:** [backend/services/master_governance_service.py:96](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/master_governance_service.py#L96); fungsi `apply_batch` mulai baris 76.

**Potongan kode kandidat:**

```python
  93:                             "before": p["from"], "after": p["to"]})
  94:     batch = {"id": batch_id, "status": "applied", "note": (note or "").strip(), "changes": changes,
  95:              "preview_signature": signature, "applied_by": actor.get("name", ""), "applied_at": now_iso()}
  96:     await db.master_governance_batches.insert_one(dict(batch))
  97:     return safe_doc(batch)
  98: 
  99: 
 100: async def rollback_batch(batch_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
 101:     if len((reason or "").strip()) < 5:
 102:         raise HTTPException(status_code=422, detail="Alasan rollback wajib (min. 5 karakter).")
 103:     b = await db.master_governance_batches.find_one_and_update(
 104:         {"id": batch_id, "status": "applied"}, {"$set": {"status": "rolling_back"}})
```

**Kesalahan/akar masalah:** Apply mengubah produk dan last_governance_batch lalu insert dokumen batch before/after. Jika insert gagal, perubahan tidak mempunyai snapshot rollback.

**Asal perubahan vs baseline W2:** File/service belum ada di baseline W2; failure berasal dari alur yang ditambahkan pada kandidat.

**Reproduksi dan dampak:** Stage produk greige→grey dan last_governance_batch terisi; fault sebelum insert batch: durable_batch_count0. Rollback batch yang dijanjikan tidak tersedia.

**Output aktual tersimpan:**

```json
{
  "error": "RuntimeError('Synthetic batch journal failure BEFORE write')",
  "original_stage": "greige",
  "current_stage": "grey",
  "batch_reference": "mgb_c02f8c920134",
  "durable_batch_count": 0
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-MASTER-01 tanpa merusak invariant gelombang 1/2. Persist batch plan/hash/before snapshots dan stage prepared sebelum produk diubah; pakai CAS version tiap produk dan idempoten operation. Progress parsial harus bisa resume/rollback tanpa menimpa edit sesudahnya. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Fault sebelum/antara product update dan batch insert menghasilkan batch recoverable atau tidak ada perubahan. Uji multi-produk, edits concurrent, dry-run signature stale, rollback conflict dan retry identitas sama.


## V3-PO-02

**P2 — Pilihan amend ke jumlah diterima bertentangan dengan guard PO lama**

**Kaitan catatan lama:** W2-REQ-06. Status: **open / confirmed**.

**Lokasi:** [backend/services/po_amendment_service.py:103](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/po_amendment_service.py#L103); fungsi `_assert_received_line_locked` mulai baris 97.

**Potongan kode kandidat:**

```python
 100:     if not old:
 101:         return
 102:     changed = []
 103:     if abs(float(item_in.quantity or 0) - float(old.get("quantity") or 0)) > 0.001:
 104:         changed.append(f"qty {float(old.get('quantity') or 0):g}→{float(item_in.quantity):g}")
 105:     old_unit = str(old.get("unit") or "").strip().lower()
 106:     new_unit = str(item_in.unit or old.get("unit") or "").strip().lower()
 107:     if new_unit != old_unit:
 108:         changed.append(f"satuan {old.get('unit')}→{item_in.unit}")
 109:     new_price = float(item_in.price or 0)
 110:     if new_price > 0 and abs(new_price - float(old.get("price") or 0)) > 0.001:
 111:         changed.append(f"harga {float(old.get('price') or 0):,.0f}→{new_price:,.0f}".replace(",", "."))
```

**Kesalahan/akar masalah:** Task baru menjanjikan amendment qty aktual, tetapi guard lama mengunci quantity setiap baris yang received_qty>0. Ini gap integrasi dua aturan bisnis, bukan alasan untuk menghapus guard seluruh field finansial.

**Asal perubahan vs baseline W2:** Body fungsi tetap sama menurut AST terhadap baseline W2; masalah ini residual atau konflik integrasi baru, bukan bukti fungsi lama berubah menjadi salah.

**Reproduksi dan dampak:** Ordered1000/received960; suggested amendment960. amend_po menolak400 qty1000→960 walaupun tidak kurang dari received dan tujuannya menutup kekurangan.

**Output aktual tersimpan:**

```json
{
  "ordered": 1000,
  "received": 960,
  "suggested_amendment": 960,
  "error": "400: Baris MAT sudah diterima 960 — terkunci dari revisi (qty 1000→960). Barang yang sudah masuk gudang tidak bisa diubah qty/satuan/harga/diskonnya; buat PO baru untuk tambahan, atau retur beli bila ada selisih."
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-PO-02 tanpa merusak invariant gelombang 1/2. Tetapkan flow dedicated receiving-variance amendment atau perbaiki CTA menjadi short-close sesuai policy disepakati. Jika amendment dipilih, target tidak kurang dari received, snapshot/bill/DP dilindungi dan reapproval/credit adjustment eksplisit; jangan rewrite posted GL. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Kasus1000→960 memiliki jalur selesai yang nyata dan tidak buntu. Received tetap960; PO version/approval terdokumentasi; vendor bill/AP/DP diperhitungkan terpisah. Jika hanya short-close diperbolehkan, UI tidak menjanjikan amend unsupported.


## V3-CUT-01

**P1 — Gagal membuat child cut menghilangkan stok dan reservasi**

**Kaitan catatan lama:** WM-01, WM-02, W2-REQ-09, GN-11. Status: **open / confirmed**.

**Lokasi:** [backend/services/roll_service.py:614](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/roll_service.py#L614); fungsi `confirm_cut` mulai baris 573.

**Potongan kode kandidat:**

```python
 611:         "status": rsv.get("status") or "reserved", "reserved_ref": rsv["ref"], "earmarked_for": None,
 612:         "is_remnant": False, "cut": cut, "journey": {"stage": "cut_pending_tag", "updated_at": now_iso()},
 613:         "created_at": now_iso(), "updated_at": now_iso()})
 614:     child = await insert_child_roll(child, parent)
 615:     await db.inventory_movements.insert_one({
 616:         "id": new_id("mov"), "product_id": parent["product_id"], "warehouse_id": parent["warehouse_id"],
 617:         "owner_entity_id": parent.get("owner_entity_id"), "movement_type": "roll_cut",
 618:         "quantity": 0, "unit": parent.get("unit", "meter"), "lot": parent.get("lot", ""),
 619:         "roll_id": child["id"], "parent_roll_id": roll_id, "qty_rolls": 1,
 620:         "source_document": rsv["ref"]["id"], "cut": cut, "timestamp": now_iso()})
 621:     if waste > 0:
 622:         await db.inventory_movements.insert_one({
```

**Kesalahan/akar masalah:** Parent decrement dan pull reservation dilakukan sebelum child insert. Bila insert gagal sebelum write, tidak ada durable cut command yang dapat melanjutkan dan reservation telah hilang.

**Asal perubahan vs baseline W2:** Fungsi ini belum ada di baseline W2; failure berada pada helper/alur baru kandidat.

**Reproduksi dan dampak:** Awal10/reserve3; fault child insert: parent7, reserved0, child0. Retry confirm_cut404 reservasi tidak ditemukan/sudah dipotong. Stok fisik total data berkurang3 tanpa child.

**Output aktual tersimpan:**

```json
{
  "before_length": 10,
  "after_length": 7.0,
  "length_reserved": 0,
  "child_count": 0,
  "error": "Synthetic cut child insert fault BEFORE write",
  "retry_error": "404: Reservasi potong tidak ditemukan / sudah dipotong"
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-CUT-01 tanpa merusak invariant gelombang 1/2. Persist cut operation dan output identity stabil sebelum mutation; parent/reservation/child/movement/weight/tag lifecycle satu transaksi atau recoverable state machine. Retry mencari cut operation lama, bukan hanya reservation yang sudah dipull. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Fault setiap tahap cut100→70+30 selalu conservation quantity/value/weight+documented waste; retry menghasilkan satu child dan satu movement, tag identity baru harus diverifikasi sebelum loading. Tidak boleh menambah kembali parent bila child sudah ada.


## V3-MRES-02

**P1 — Total cadangan maklon tetap terpotong pada batas query**

**Kaitan catatan lama:** GN-12, W2-REQ-07, W2-REQ-04. Status: **open / confirmed**.

**Lokasi:** [backend/services/material_reservation_service.py:44](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/material_reservation_service.py#L44); fungsi `reserved_by_others` mulai baris 40.

**Potongan kode kandidat:**

```python
  41:     q: Dict[str, Any] = {"product_id": product_id, "owner_entity_id": entity_id, "status": ACTIVE}
  42:     if exclude_ref_id:
  43:         q["ref_id"] = {"$ne": exclude_ref_id}
  44:     rows = await db.material_reservations.find(q, {"_id": 0, "qty": 1}).to_list(2000)
  45:     return round(sum(float(r.get("qty") or 0) for r in rows), 3)
  46: 
  47: 
  48: async def free_for_commitment(product_id: str, entity_id: str, exclude_ref_id: str = "",
  49:                               warehouse_id: str = "") -> float:
  50:     return round(max(await _on_hand_available(product_id, entity_id, warehouse_id)
  51:                      - await reserved_by_others(product_id, entity_id, exclude_ref_id), 0.0), 3)
  52: 
```

**Kesalahan/akar masalah:** reserved_by_others memakai2000, _on_hand_available500 dan apply_to_products5000 untuk total bisnis, bukan daftar berhalaman. Cadangan yang dilewatkan dapat dijanjikan lagi ke sales.

**Asal perubahan vs baseline W2:** File/service belum ada di baseline W2; failure berasal dari alur yang ditambahkan pada kandidat.

**Reproduksi dan dampak:** 2001 active reservation masing-masing1 menghasilkan reserved_by_others2000. Selisih1 terukur; batas500/5000 lain dikonfirmasi statis, belum diuji runtime pada probe ini.

**Output aktual tersimpan:**

```json
{
  "expected_reserved": 2001,
  "actual_reserved": 2000.0,
  "document_count": 2001
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-MRES-02 tanpa merusak invariant gelombang 1/2. Gunakan aggregate/kursor penuh untuk seluruh total. Batasi hanya endpoint list berhalaman dengan total terpisah. Harmonisasi owner, product, unit, warehouse dan exclusion ref agar sales dan PR memakai angka sama. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Cap−1/cap/cap+1 pada2000reservations,500balances,5000catalog reservations serta>10000roll allocation harus konsisten. Test total/UI/guard commit dan cancellation tidak memakai subset sebagai SSOT.


## V3-PO-03

**P1 — Tugas selisih selesai meski amendment belum disetujui dan qty belum berubah**

**Kaitan catatan lama:** W2-REQ-06. Status: **open / confirmed**.

**Lokasi:** [backend/routers/purchase_orders.py:751](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/purchase_orders.py#L751); fungsi `amend_purchase_order` mulai baris 733.

**Potongan kode kandidat:**

```python
 748:     result = await amend_po_service(po_id, payload, actor)
 749:     updated = result["po"]
 750:     from services import po_variance_task_service as _pvt
 751:     await _pvt.close_amendment_tasks(po_id, actor["name"])  # W2-REQ-06
 752:     if result["needs_approval"]:
 753:         from services.notification_service import notify_po_awaiting_approval
 754:         await notify_po_awaiting_approval(updated)
 755:     else:
 756:         await _create_inbound_tasks_for_po(updated)
 757:     return safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))
 758: 
 759: 
```

**Kesalahan/akar masalah:** Router menyelesaikan seluruh pending_amendment segera sesudah amend_po, sebelum reapproval. Fungsi juga tidak memeriksa apakah perubahan berkaitan dengan shortage line.

**Asal perubahan vs baseline W2:** Fungsi berubah terhadap baseline W2. Failure window kandidat dikonfirmasi; tanpa differential runtime pada tiap commit, perubahan ini belum membuktikan bug pertama kali lahir pada satu commit tertentu.

**Reproduksi dan dampak:** HTTP notes-only amend200: PO quantity1000 tetap dan statuswaiting_approval; task shortage received960 menjadi decided. Persetujuan kuantitas belum terjadi.

**Output aktual tersimpan:**

```json
{
  "http_status": 200,
  "po_status": "waiting_approval",
  "po_quantity": 1000,
  "task_status": "decided",
  "detail": null
}
```

Bukti: [new-failure-probes.json](evidence/new-failure-probes.json) dan [script reproduksi](repro/new_failure_probes.py).

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-PO-03 tanpa merusak invariant gelombang 1/2. Selesaikan task hanya setelah amendment version/line yang ditautkan approved dan acceptance shortage direvalidasi. Notes-only amendment tidak menutup qty task. Rejection/cancel amendment memulihkan action pending yang benar. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Amend notes saja atau awaiting approval: task pending. Approved qty960/reconciled policy: task selesai. Rejection tetap memerlukan keputusan. Beberapa task/line/versi tidak tertutup sekaligus oleh perubahan unrelated.


## V3-DUP-01

**P3 — Helper _clean_perms didefinisikan dua kali**

**Kaitan catatan lama:** GN-15. Status: **open / confirmed**.

**Lokasi:** [backend/services/custom_role_service.py:60](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/custom_role_service.py#L60); fungsi `_clean_perms` mulai baris 60.

**Potongan kode kandidat:**

```python
  57:     return out
  58: 
  59: 
  60: def _clean_perms(perms: Any) -> Dict[str, List[str]]:
  61:     try:
  62:         return clean_permissions(perms)
  63:     except ValueError as exc:
  64:         raise HTTPException(status_code=400, detail=str(exc)) from exc
  65: 
  66: 
  67: def _clean_perms(perms: Any) -> Dict[str, List[str]]:
  68:     try:
```

**Kesalahan/akar masalah:** AST seluruh backend menemukan dua definisi top-level identik pada baris60 dan67. Definisi kedua menimpa pertama; body kini sama sehingga ini maintainability debt, bukan beda perilaku akses.

**Asal perubahan vs baseline W2:** Body fungsi tetap sama menurut AST terhadap baseline W2; masalah ini residual atau konflik integrasi baru, bukan bukti fungsi lama berubah menjadi salah.

**Reproduksi dan dampak:** Dua definisi identik pada file yang sama; syntax parser tidak menolaknya.

**Bukti statis:** [inventory AST](evidence/python-static-inventory.json). Tidak dihitung sebagai counterexample runtime.

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-DUP-01 tanpa merusak invariant gelombang 1/2. Hapus definisi identik dengan satu canonical helper; tambahkan deteksi duplicate top-level definition dalam quality check yang sesuai, tanpa menggandakan business-rule tests. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Satu definisi, custom permission normal/error contract tetap sama. Jangan menjadikan ini P1 atau menghitungnya sebagai bug akses yang sudah terbukti.


## V3-BUILD-01

**P2 — Dependency build frontend tidak mempunyai lockfile terlacak**

**Kaitan catatan lama:** GN-15. Status: **open / confirmed**.

**Lokasi:** [frontend/package.json:151](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/frontend/package.json#L151); fungsi `(konfigurasi dependency)`.

**Potongan kode kandidat:**

```text
 148:     "**/tinyglobby/picomatch": "4.0.4",
 149:     "http-proxy-middleware": "2.0.10"
 150:   },
 151:   "packageManager": "yarn@1.22.22+sha512.a6b2f7906b721bba3d67d4aff083df04dad64c399707841b7acf00f6b133b7ac24255f2652fa22ae3534329dc6180534e98d17432037ff6fd140556e2bb3137e"
 152: }
```

**Kesalahan/akar masalah:** Repo mendeklarasikan Yarn1.22.22 tetapi tidak melacak yarn.lock, package-lock.json atau pnpm-lock.yaml. Fresh install harus meresolusikan dependency transitive; dua build tidak mempunyai dependency graph terkunci.

**Asal perubahan vs baseline W2:** File konfigurasi berubah terhadap baseline W2; observasi ini kualitas/reproducibility, bukan runtime regression yang terbukti.

**Reproduksi dan dampak:** Install lokal melaporkan No lockfile found; build berhasil dengan warnings memakai dependency graph yang diselesaikan hari audit. Ini risiko reproducibility, bukan bukti frontend gagal build.

**Bukti statis:** [fresh install log](evidence/frontend-install.log), [build berhasil dengan warnings](evidence/frontend-build.log), dan pemeriksaan file lock terlacak pada manifest. Tidak dihitung sebagai counterexample runtime.

**Prompt perbaikan untuk agent:**

> Pada kandidat `5b7f34122bd104f4426ccd7f72b38fb7969eda8f`, perbaiki V3-BUILD-01 tanpa merusak invariant gelombang 1/2. Commit satu lockfile canonical sesuai packageManager; pipeline harus gagal jika lock tidak ada/berbeda dan memakai frozen/immutable install. Simpan runtime versions dan dependency integrity. Jangan commit node_modules/build/.env. Catat commit, perubahan skema/index, backfill yang diperlukan, hasil test dan batasnya. Jangan menandai verified_fixed dari assertion implementasi sendiri.

**Acceptance:** Fresh isolated install pada dua runner memakai graph/integrity sama. Build smoke lulus dari lock, lint warning relevan ditinjau; packageManager dan pipeline tidak saling memilih manager berbeda.


---

# Pengujian, validitas bukti dan coverage

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

## Lingkungan dan metode

Baseline W1 `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`; baseline W2 `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Kandidat adalah worktree detached dari main publik yang telah di-fetch; 782 path berubah dibanding baseline W2. Review menyandingkan catatan original, diff, helper/current callers, test perbaikan agent dan counterexample independen.

Mongo berjalan hanya di loopback port27919, HTTP kandidat localhost8001, frontend build disajikan127.0.0.1:3000. Database uji `knhost_validation_20261005_suite` dan database independen `knhost_audit_<uuid>`; semua seed sintetis. Dotenv dinonaktifkan dan socket nonloopback diblokir dalam proses pengujian. Tidak memakai credential eksternal atau database produksi.

Backend memakai Motor/Mongo serta ASGI/service asli. Indeks performa/unique kandidat dipasang sebelum counterexample concurrency. Uvicorn memakai lifespan off setelah seed/index/RFID migration eksplisit. Environment `SESSION_COOKIE_SECURE=false` hanya untuk HTTP localhost sintetis agar cookie dapat diuji; bukan perubahan konfigurasi produksi yang direkomendasikan.

Test copies mengganti path `/app`, URL/DB hardcoded dan fixture yang tidak tersedia. Source aplikasi kandidat dan assertion bisnis yang tetap relevan tidak diubah. Serial pytest dipakai karena pytest-xdist tidak terpasang; ini tidak mengubah source pytest.ini repo. Modifikasi fixture/oracle dijelaskan di bawah, bukan disembunyikan sebagai pass original.

## Inventaris source dan build

- Seluruh 798 file Python terlacak diparse: 0 syntax error; fungsi dan baris tersimpan di [inventory](evidence/python-static-inventory.json).
- Seluruh 855 source JS/JSX/TS frontend terlacak diparse dengan Babel: 0 syntax error; [hasil](evidence/frontend-static-results.json) dan [daftar](evidence/frontend-source-files.json).
- Fresh dependency install dan full production frontend build selesai. Build mengeluarkan warning ESLint/React hook; ini bukan build bersih dari warning. [Log build](evidence/frontend-build.log).
- Tidak ada frontend lockfile terlacak pada kandidat. Dependency graph fresh install belum reproducible (V3-BUILD-01). Syntax/build pass tidak membuktikan perilaku UI benar.

## Hasil batch — jangan dijumlahkan sebagai test unik

Tabel menyimpan setiap putaran, termasuk fail awal. Rerun mengulang banyak assertion; jumlah ini bukan persentase coverage atau jumlah skenario independen.

| Putaran | Script/module | Assertion yang terparse | Pass / fail | Makna |
|---|---:|---:|---|---|
| Core awal | 15 | 310 | 301 / 9 | Sebagian HTTP menggunakan auth/fixture lama; diuji ulang |
| Extended awal | 41 | 420 | 391 / 29 | Ada script crash sebelum assertion, timeout dan fixture Linux/legacy |
| Follow-up fresh DB | 13 | 218 | 181 / 37 | Menyelesaikan auth; beberapa failure baru atau fixture lama tetap dicatat |
| Fixture final | 4 | 72 | 70 / 2 | P01 22/22, P17e 7/7, P20e 13/13; P16 terhambat loading multi-gudang dan cascade design |
| W2 regresi agent, 4 batch | 4 | 82 | 82 / 0 | Dibaca dari JSON hasil script, bukan parser stdout yang kosong |
| Pytest: 10 module, hasil terakhir | 10 | 120 | 118 pass, 1 status-oracle fail, 1 skip | Scope hasil latest per module; failed attempts tidak dihitung ulang |
| Probe acceptance tambahan | 2 script | 9 | 9 / 0 | Kapasitas/maklon5 dan interleaving Finance4 |
| Counterexample independen | 1 script | 17 observasi | 17 tereproduksi | Membuktikan masalah terbuka, bukan test produk pass |

W2:25/25 service,6/6 HTTP,15/15 P08 fase1,36/36 fase2–6. Detail pada [evidence/w2](evidence/w2/README.md).

Pytest hasil terakhir: iter1436pass1skip; iter1442pass; iter11419pass; iter11519pass; iter11618pass; iter11718pass; iter1188pass; iter11910pass; iter12011pass; targeted W2 7pass1fail. Total118pass+1fail+1skip. Satu skip roll-mode pada fixture iter143 tidak dianggap pass; roll rounding juga diperiksa pada P08/service, tetapi bukan pengganti UAT browser.

## Probe positif yang penting

- Maklon declared10/output roll9.5: total roll120.0002 vs GL120; residual di bawah sen, sesuai policy rounding yang diterapkan. Bukan lagi drift baseline material.
- Warehouse tidak dikenal:404 sebelum output/jurnal; partial receive4 diWH lalu6 diWH2 tetap terpisah.
- GRN501 roll:PO received501;0 roll receiving;501 quarantine. WO5001 roll:5001 consumed movements;qty5001;cost50010.
- Generic cancel bill jasa maklon:409; AP100000 tetap. Sesudah claim mengurangi bill100000→60000, payment80000 ditolak; cash0, paid0, AP60000. Dua urutan worker diuji.
- Stale reject cycle count lewat HTTP:loader membaca submitted, worker lain approve, reject409 dan status tetap approved.

Bukti: [kapasitas](evidence/positive-capacity-makloon-results.json), [Finance interleavings](evidence/positive-finance-interleavings-results.json), [counterexamples](evidence/new-failure-probes.json).

## Fail awal yang tidak otomatis merupakan bug aplikasi

| Hasil awal | Penjelasan dan tindak lanjut |
|---|---|
| HTTP scope/cookie gagal | Secure cookie tidak terkirim lewat HTTP localhost. Setelah config lokal dan autentikasi test disesuaikan, P01 scope22/22 lulus. Produksi harus HTTPS dan Secure sesuai deployment. |
| RF05 untagged exception tanpa reason | Guard baru sengaja meminta reason/permission; payload lama tidak sah. Konflik policy semua wajib tag dibahas sebagai kebutuhan bisnis, bukan menghapus guard reason. |
| RF09 replay tidak mengirim kind cycle_count | Typed-session guard menolak endpoint generic. P14 history dengan kind sah lulus. |
| W2 targeted mengharapkan loser409, mendapat400 | Jika loser membaca saldo deposit terbaru20 setelah winner, validasi insufficient balance400 benar. Jika kedua membaca saldo lama, CAS409. Tidak ada double spending pada test ini; assertion status terlalu sempit, tetapi V3-AR-01 tetap bug terpisah. |
| iter143 gagal sebelum alur yang diuji | Mixed-lot guard kini meminta confirm_mixed_lot. Salinan fixture menambahkan konfirmasi eksplisit; oracle kuantitas/bisnis tidak diubah. Hasil6pass1skip. |
| iter115–120 mencari Mongo27017/test_database | Hardcoded environment test lama diganti DB sintetis lokal. Source aplikasi tidak diubah. Hasil latest masing-masing tercatat. |
| P17e precedence harga customer | Seed memiliki harga berlaku lebih baru; expected lama salah. Fixture harga diisolasi tanpa mengubah source;7/7 lulus. |
| P20e HR memakai employee tidak ada | Seed pegawai sintetis aktif dengan entitas/salary valid ditambahkan;13/13 lulus. |
| P18c/18e retur memakai ID PO/supplier hardcoded | ID legacy tidak ada pada seed sekarang, sehingga404 dan flow berikutnya tidak terbentuk. Tidak dipromosikan sebagai bug retur baru; kontrol P04 dan HTTP opname/cutoff terkait lulus. |
| Rename product via generic PATCH400 | Candidate mengharuskan governance rename beralasan. Payload harga/nama lama bukan oracle route governance yang baru. V3-MASTER-01 diuji lewat service governance sebenarnya. |
| P20f approve [403,200] | Request kedua melihat tahap approval selanjutnya dengan role berbeda; bukan bukti CAS gagal. Dua amendment sukses serial/version3 juga bukan bukti dua worker membaca snapshot sama. |
| P21 finance notification1 pada scan kedua | Eskalasi manager level1→admin level2 mempunyai target/dedupe berbeda. Tidak sama dengan duplikasi kas/jurnal. Interval eskalasi perlu UAT operasional. |
| P16 outbound fixture tanpa RFID, lalu cascade design | Fixture diperbaiki memakai tag/loading asli; blockage multi-gudang V3-WMS-02 tetap nyata. Design error setelah flow berhenti tidak dijadikan bug design mandiri. |
| Broad auth sweep timeout240detik | Suite luas tidak selesai; targeted scope test dan source guard diperiksa. Tidak dicatat sebagai broad suite pass. |
| Backup/OCR font failure di Windows | Path/font Linux tidak tersedia. Source/lifecycle diperiksa; backup-restore Linux dan output OCR/PDF visual yang bergantung font belum certified. |
| Pytest cache permission warning | Runtime Windows gagal menulis cache; hasil test tetap sah. Tidak dianggap defect business code. |

## Batas dan risiko yang belum menjadi counterexample confirmed

- UI automation gagal sebelum tab/browser dapat dipakai: initialization gagal menulis kernel assets, os error3. Tidak ada UAT visual, download interaktif atau draft switching live; UX01–03 tetap source-only.
- Hardware RFID melibatkan arah/antena/read overlap, missed/stray reads, printer ack/verified tag, siren/barrier offline dan driver per gudang; belum diuji dengan perangkat fisik.
- Closing lock600detik memakai stale takeover dan release tanpa fencing token kuat pada seluruh path. Proses pertama yang masih hidup >10menit dapat berisiko menghapus lease penerus. Ini telaah kondisional, belum counterexample runtime; jangan dicampur dengan19 temuan confirmed.
- PO amendment server-side CAS tidak otomatis memberi stale-screen protection dari client jika expected_version tidak disyaratkan. Kebijakan conflict UX perlu diputuskan; dua request serial bukan bukti lost update.
- Data historis, secret rotation/revocation, deployment index/replica set, restart/crash nyata proses/DB dan restore backup produksi belum tersedia untuk validasi.

## Peta bukti per script

Status dan tail mentah tersimpan agar fail awal dapat ditelusuri. Kolom pass/fail adalah assertion yang parser berhasil baca; exit0 sendiri bukan bukti seluruh acceptance lolos.

| Putaran | Script | Exit | Pass | Fail | Log |
|---|---|---:|---:|---:|---|

| core | `audit/iterations/2026-10-01-P02-core-roll/repro_p02.py` | 0 | 13 | 0 | [log](evidence/test-logs/core-00-repro_p02.log) |

| core | `audit/iterations/2026-10-02-P02-wm02-reservation/repro_wm02.py` | 0 | 11 | 0 | [log](evidence/test-logs/core-01-repro_wm02.log) |

| core | `audit/iterations/2026-10-02-P03-durable-posting/repro_p03.py` | 0 | 43 | 0 | [log](evidence/test-logs/core-02-repro_p03.log) |

| core | `audit/iterations/2026-10-03-P04-costing/repro_p04.py` | 0 | 7 | 0 | [log](evidence/test-logs/core-03-repro_p04.log) |

| core | `audit/iterations/2026-10-05-P05-coa-reports-close/repro_p05.py` | 0 | 29 | 0 | [log](evidence/test-logs/core-04-repro_p05.log) |

| core | `audit/iterations/2026-10-02-P06-receiving/repro_p06.py` | 0 | 12 | 0 | [log](evidence/test-logs/core-05-repro_p06.log) |

| core | `audit/iterations/2026-10-06-P07-dispatch-identity-reversal/repro_p07.py` | 0 | 13 | 5 | [log](evidence/test-logs/core-06-repro_p07.log) |

| core | `audit/iterations/2026-10-07-P07-fulfillment-saga-loading/repro_p07b.py` | 0 | 12 | 4 | [log](evidence/test-logs/core-07-repro_p07b.log) |

| core | `audit/iterations/2026-10-08-P08-tag-printer-verify/repro_p08.py` | 0 | 43 | 0 | [log](evidence/test-logs/core-08-repro_p08.log) |

| core | `audit/iterations/2026-10-08-P09-gate-contract/repro_p09.py` | 0 | 22 | 0 | [log](evidence/test-logs/core-09-repro_p09.log) |

| core | `audit/iterations/2026-10-08-P10-opname-financial/repro_p10.py` | 0 | 21 | 0 | [log](evidence/test-logs/core-10-repro_p10.log) |

| core | `audit/iterations/2026-10-02-P11-mutasi-konversi/repro_p11.py` | 0 | 21 | 0 | [log](evidence/test-logs/core-11-repro_p11.log) |

| core | `audit/iterations/2026-10-02-P12-payroll-hr-marketing/repro_p12.py` | 0 | 23 | 0 | [log](evidence/test-logs/core-12-repro_p12.log) |

| core | `audit/iterations/2026-10-02-P13-audit-secret-label/repro_p13.py` | 0 | 10 | 0 | [log](evidence/test-logs/core-13-repro_p13.log) |

| core | `audit/iterations/2026-10-02-P15-gn15-ssot/repro_gn15.py` | 0 | 21 | 0 | [log](evidence/test-logs/core-14-repro_gn15.log) |

| extended | `audit/iterations/2026-09-30-P01-device-credentials/repro_rf12_rf13.py` | 1 | 0 | 0 | [log](evidence/test-logs/extended-00-repro_rf12_rf13.log) |

| extended | `audit/iterations/2026-09-30-P01-scope-batch1/repro_p01_scope.py` | 1 | 0 | 0 | [log](evidence/test-logs/extended-01-repro_p01_scope.log) |

| extended | `audit/iterations/2026-09-30-P01-scope-batch2/repro_p01_batch2.py` | 1 | 12 | 1 | [log](evidence/test-logs/extended-02-repro_p01_batch2.log) |

| extended | `audit/iterations/2026-10-01-P01-ix06-cx10/repro_cx10.py` | 0 | 10 | 0 | [log](evidence/test-logs/extended-03-repro_cx10.log) |

| extended | `audit/iterations/2026-10-01-P01-ix06-cx10/repro_ix06.py` | 1 | 0 | 0 | [log](evidence/test-logs/extended-04-repro_ix06.log) |

| extended | `audit/iterations/2026-10-01-P06-qc-sampling/repro_pg01_ix15.py` | 0 | 13 | 0 | [log](evidence/test-logs/extended-05-repro_pg01_ix15.log) |

| extended | `audit/iterations/2026-10-02-P14-coverage-uat/repro_p14b_cases.py` | 0 | 23 | 0 | [log](evidence/test-logs/extended-06-repro_p14b_cases.log) |

| extended | `audit/iterations/2026-10-02-P14-coverage-uat/repro_p14_history.py` | 0 | 17 | 2 | [log](evidence/test-logs/extended-07-repro_p14_history.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17a.py` | 0 | 10 | 0 | [log](evidence/test-logs/extended-08-repro_p17a.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17b.py` | 0 | 8 | 0 | [log](evidence/test-logs/extended-09-repro_p17b.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17c.py` | 0 | 13 | 0 | [log](evidence/test-logs/extended-10-repro_p17c.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17d.py` | 0 | 7 | 0 | [log](evidence/test-logs/extended-11-repro_p17d.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17e.py` | 0 | 6 | 1 | [log](evidence/test-logs/extended-12-repro_p17e.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17f.py` | 0 | 6 | 0 | [log](evidence/test-logs/extended-13-repro_p17f.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17g.py` | 0 | 6 | 0 | [log](evidence/test-logs/extended-14-repro_p17g.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17h.py` | 0 | 6 | 0 | [log](evidence/test-logs/extended-15-repro_p17h.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17i.py` | 1 | 0 | 0 | [log](evidence/test-logs/extended-16-repro_p17i.log) |

| extended | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17j.py` | 0 | 0 | 1 | [log](evidence/test-logs/extended-17-repro_p17j.log) |

| extended | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18a.py` | timeout | 0 | 0 | [log](evidence/test-logs/extended-18-repro_p18a.log) |

| extended | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18b.py` | 0 | 12 | 2 | [log](evidence/test-logs/extended-19-repro_p18b.log) |

| extended | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18c.py` | 0 | 9 | 2 | [log](evidence/test-logs/extended-20-repro_p18c.log) |

| extended | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18d.py` | 0 | 8 | 0 | [log](evidence/test-logs/extended-21-repro_p18d.log) |

| extended | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18e.py` | 0 | 3 | 3 | [log](evidence/test-logs/extended-22-repro_p18e.log) |

| extended | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18f.py` | 0 | 7 | 0 | [log](evidence/test-logs/extended-23-repro_p18f.log) |

| extended | `audit/iterations/2026-10-03-P19-uat-receiving/repro_p19_receiving.py` | 0 | 30 | 0 | [log](evidence/test-logs/extended-24-repro_p19_receiving.log) |

| extended | `audit/iterations/2026-10-03-WM02-identity-CX05-panel/repro_followup.py` | 0 | 10 | 3 | [log](evidence/test-logs/extended-25-repro_followup.log) |

| extended | `audit/iterations/2026-10-04-label-reimburse-poline-badge/repro_followup2.py` | 0 | 1 | 2 | [log](evidence/test-logs/extended-26-repro_followup2.log) |

| extended | `audit/iterations/2026-10-04-P20-partial-api/repro_p20a.py` | 0 | 14 | 0 | [log](evidence/test-logs/extended-27-repro_p20a.log) |

| extended | `audit/iterations/2026-10-04-P20-partial-api/repro_p20b.py` | 0 | 16 | 0 | [log](evidence/test-logs/extended-28-repro_p20b.log) |

| extended | `audit/iterations/2026-10-04-P20-partial-api/repro_p20c.py` | 0 | 13 | 0 | [log](evidence/test-logs/extended-29-repro_p20c.log) |

| extended | `audit/iterations/2026-10-04-P20-partial-api/repro_p20d.py` | 0 | 15 | 0 | [log](evidence/test-logs/extended-30-repro_p20d.log) |

| extended | `audit/iterations/2026-10-04-P20-partial-api/repro_p20e.py` | 0 | 0 | 2 | [log](evidence/test-logs/extended-31-repro_p20e.log) |

| extended | `audit/iterations/2026-10-04-P20-partial-api/repro_p20f.py` | 0 | 12 | 2 | [log](evidence/test-logs/extended-32-repro_p20f.log) |

| extended | `audit/iterations/2026-10-04-P21-partial-api/repro_p21.py` | 0 | 36 | 2 | [log](evidence/test-logs/extended-33-repro_p21.log) |

| extended | `audit/iterations/2026-10-05-P05-coa-reports-close/repro_followup3.py` | 1 | 0 | 0 | [log](evidence/test-logs/extended-34-repro_followup3.log) |

| extended | `audit/iterations/2026-10-09-P16-close-coverage/repro_p16.py` | 0 | 37 | 6 | [log](evidence/test-logs/extended-35-repro_p16.log) |

| extended | `audit/iterations/2026-10-09-P16-close-coverage/repro_p16b.py` | 0 | 12 | 0 | [log](evidence/test-logs/extended-36-repro_p16b.log) |

| extended | `audit/iterations/2026-10-09-P16-close-coverage/repro_p16c.py` | 0 | 7 | 0 | [log](evidence/test-logs/extended-37-repro_p16c.log) |

| extended | `audit/iterations/2026-10-09-P16-close-coverage/repro_p16d.py` | 0 | 4 | 0 | [log](evidence/test-logs/extended-38-repro_p16d.log) |

| extended | `audit/iterations/2026-10-09-P16-close-coverage/repro_p16e.py` | 0 | 5 | 0 | [log](evidence/test-logs/extended-39-repro_p16e.log) |

| extended | `audit/iterations/2026-10-09-P16-close-coverage/repro_p16f.py` | 0 | 3 | 0 | [log](evidence/test-logs/extended-40-repro_p16f.log) |

| followup | `audit/iterations/2026-10-06-P07-dispatch-identity-reversal/repro_p07.py` | 0 | 17 | 1 | [log](evidence/test-logs/followup-00-repro_p07.log) |

| followup | `audit/iterations/2026-10-07-P07-fulfillment-saga-loading/repro_p07b.py` | 0 | 16 | 0 | [log](evidence/test-logs/followup-01-repro_p07b.log) |

| followup | `audit/iterations/2026-09-30-P01-device-credentials/repro_rf12_rf13.py` | 0 | 16 | 0 | [log](evidence/test-logs/followup-02-repro_rf12_rf13.log) |

| followup | `audit/iterations/2026-09-30-P01-scope-batch1/repro_p01_scope.py` | 1 | 6 | 16 | [log](evidence/test-logs/followup-03-repro_p01_scope.log) |

| followup | `audit/iterations/2026-10-01-P01-ix06-cx10/repro_ix06.py` | 0 | 11 | 0 | [log](evidence/test-logs/followup-04-repro_ix06.log) |

| followup | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17e.py` | 0 | 6 | 1 | [log](evidence/test-logs/followup-05-repro_p17e.log) |

| followup | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18b.py` | 0 | 12 | 2 | [log](evidence/test-logs/followup-06-repro_p18b.log) |

| followup | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18c.py` | 0 | 9 | 2 | [log](evidence/test-logs/followup-07-repro_p18c.log) |

| followup | `audit/iterations/2026-10-03-P18-partial-coverage/repro_p18e.py` | 0 | 3 | 3 | [log](evidence/test-logs/followup-08-repro_p18e.log) |

| followup | `audit/iterations/2026-10-04-P20-partial-api/repro_p20e.py` | 0 | 0 | 2 | [log](evidence/test-logs/followup-09-repro_p20e.log) |

| followup | `audit/iterations/2026-10-09-P16-close-coverage/repro_p16.py` | 0 | 37 | 6 | [log](evidence/test-logs/followup-10-repro_p16.log) |

| followup | `audit/iterations/2026-10-04-P20-partial-api/repro_p20f.py` | 0 | 12 | 2 | [log](evidence/test-logs/followup-11-repro_p20f.log) |

| followup | `audit/iterations/2026-10-04-P21-partial-api/repro_p21.py` | 0 | 36 | 2 | [log](evidence/test-logs/followup-12-repro_p21.log) |

| final-fixture | `audit/iterations/2026-09-30-P01-scope-batch1/repro_p01_scope.py` | 0 | 22 | 0 | [log](evidence/test-logs/final-fixture-00-repro_p01_scope.log) |

| final-fixture | `audit/iterations/2026-10-03-P17-planned-coverage/repro_p17e.py` | 0 | 7 | 0 | [log](evidence/test-logs/final-fixture-01-repro_p17e.log) |

| final-fixture | `audit/iterations/2026-10-04-P20-partial-api/repro_p20e.py` | 0 | 13 | 0 | [log](evidence/test-logs/final-fixture-02-repro_p20e.log) |

| final-fixture | `audit/iterations/2026-10-09-P16-close-coverage/repro_p16.py` | 0 | 28 | 2 | [log](evidence/test-logs/final-fixture-03-repro_p16.log) |


---

# Prompt agent development per fase

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

Paket ini adalah satu iterasi validasi gelombang1/2. Pertahankan ID lama dan jangan overwrite klaim `ready_for_validation` sebagai `verified_fixed` tanpa validator terpisah. `V3-*` memetakan failure window kandidat; 19 ID tidak selalu19 root cause independen.

## Prompt pembuka siap dipakai

```text
Baca seluruh docs/audit/validation-2026-10-05/README.md, review-register.json,
04_TEMUAN_LANJUTAN.md, 05_PENGUJIAN_DAN_CAKUPAN.md dan 08_DATA_HISTORIS_DAN_RELEASE.md.
Cocokkan HEAD saat ini dengan kandidat5b7f34122bd104f4426ccd7f72b38fb7969eda8f.
Jika HEAD berbeda, catat diff dan rebase bukti sebelum mengklaim temuan sudah tertutup.
Kerjakan fase V00→V07 mengikuti dependencies. Jangan ubah policy owner secara diam-diam.
Sebelum patch, reproduce failure terbuka dengan source asli pada database sintetis.
Sesudah patch, counterexample yang sama harus menjadi assertion acceptance, bukan dihapus.
Untuk tiap ID simpan commit implementasi, test per-ID, raw results, dampak lintas flow,
perubahan schema/index, migration preview dan rollback/recovery behavior.
Gunakan status open→in_progress→implemented_pending_validation.
Validator terpisah yang boleh menetapkan verified_fixed atau reopened.
Jangan push atau deploy tanpa mandat dari pemilik; tugas perbaikan lokal dan bukti harus
dibuat konkret lebih dahulu. Jangan memakai data/credential produksi untuk reproducibility.
```

## Urutan dan dependency

V00 lebih dahulu. V01–V03 menyelesaikan integritas fisik/commitment/pembayaran. V04 bergantung pada kontrak transaksi sumber dan tanggal; V05 pada aturan PO/bill. V06 harus mempertahankan identity hasil V01. V07 dan rekonsiliasi data merupakan gerbang penerimaan, bukan pengganti perbaikan. Jika dikerjakan beberapa agent, shared helper/schema/roll/GL harus mempunyai satu penanggung jawab agar patch tidak saling menimpa.


## V00 — Baseline, kontrak bisnis dan inventaris data

ID kebutuhan bisnis dan historical-data verification.

```text
Kerjakan V00: Baseline, kontrak bisnis dan inventaris data.
Bekukan SHA kandidat dan dokumentasikan lingkungan. Ratifikasi REQ01/03/08 serta buyer-context REQ05 dengan user; jangan menganggap DECISIONS repo otomatis bukti persetujuan. Berdasarkan user saat ini: SKU hasil MD wajib uji per lini; semua barang wajib tag. Buat inventory read-only data historis dan baseline conservation qty/weight/value serta GL/subledger. Jangan memutasi jurnal posted atau melakukan bulk data rewrite dari dugaan.

Deliverable: commit, IMPLEMENTATION.md, evidence JSON/log, regression lintas flow,
serta status per ID implemented_pending_validation. Catat acceptance yang tidak
bisa dijalankan; jangan mengubahnya menjadi pass atau menghapus guard.
```


## V01 — Operasi fisik durable: produksi, cut, maklon dan berat

ID: V3-PROD-01, V3-PROD-02, V3-CUT-01, V3-MKO-01, V3-WEIGHT-01.

```text
Kerjakan V01: Operasi fisik durable: produksi, cut, maklon dan berat.
Rancang operasi stable identity + step/progress durable/fencing sebelum efek. Terapkan per flow dalam patch reviewable: production consume/reversal, cut, lalu receipt maklon. Perubahan helper roll harus mempertahankan owner/UOM/lot/weight/tag genealogy dan manifest. Transaksi Mongo hanya bila deployment mendukung replica set; jika tidak, state machine harus benar pada BEFORE/AFTER-write faults. Jangan selesai dengan unlock manual atau unconditional rollback snapshot. Jalankan semua regression stok/picking/COGS/receiving sesudah helper berubah.
V3-PROD-01: Buat operasi konsumsi per material/roll dengan identity stabil dan state durable sebelum efek, lalu lakukan perubahan fisik dan ledger dalam transaksi atau step idempoten yang dapat direkonsiliasi. Jangan menyelesaikan recovery hanya dari movement yang mungkin belum lahir.
V3-PROD-02: Claim reversal dengan token/stage dan stable operation ID. Commit restore stock dengan marker yang sama secara atomik, atau simpan progress yang membedakan claimed dari applied; retry memeriksa kontribusi aktual.
V3-CUT-01: Persist cut operation dan output identity stabil sebelum mutation; parent/reservation/child/movement/weight/tag lifecycle satu transaksi atau recoverable state machine. Retry mencari cut operation lama, bukan hanya reservation yang sudah dipull.
V3-MKO-01: Beri deterministic roll identity per operation+receipt line/index sebelum loop. Persist plan dan state tiap output sebelum/bersama creation; resume harus reconcile actual roll dan movement sebelum membuat lagi. Simpan original warehouse/lot/cost snapshot.
V3-WEIGHT-01: Simpan reservasi/split berat dan panjang dalam satu conditional update berdimensi version atau ledger cut dengan snapshot terkini. Tidak boleh menulis derived parent weight dari snapshot lama. Tandai estimated_proportional sebagai estimasi, bukan penimbangan aktual.
Deliverable: commit, IMPLEMENTATION.md, evidence JSON/log, regression lintas flow,
serta status per ID implemented_pending_validation. Catat acceptance yang tidak
bisa dijalankan; jangan mengubahnya menjadi pass atau menghapus guard.
```

**Acceptance per ID:**

- **V3-PROD-01:** Fault sebelum/sesudah tiap write, retry key sama/berbeda dan dua worker: stok20→15, output5, movement5 tepat sekali. Recovery harus bekerja melalui endpoint sah; penghapusan lock di probe hanya kontrol pemulihan lokal.
- **V3-PROD-02:** Restore operasi5 selalu menghasilkan roll10, satu reversal movement dan projection10, termasuk fault restore dan dua worker; jangan double-increment saat response hilang.
- **V3-CUT-01:** Fault setiap tahap cut100→70+30 selalu conservation quantity/value/weight+documented waste; retry menghasilkan satu child dan satu movement, tag identity baru harus diverifikasi sebelum loading. Tidak boleh menambah kembali parent bila child sudah ada.
- **V3-MKO-01:** Fault pada output1/2/N serta setelah jurnal/status: output total10 dan dua roll saja, inventory value sama GL120. Uji partial multi-gudang, duplicate lot input, response-lost dan authorized saga recovery.
- **V3-WEIGHT-01:** Parallel split2+2: parent6m/1.8kg dan children0.6+0.6kg. Uji split QC/retur/cut, decimal rounding dan actual reweigh; conservation kg dan meter diuji terpisah.


## V02 — Komitmen bahan dan ATP yang konsisten

ID: V3-MRES-01, V3-MRES-02.

```text
Kerjakan V02: Komitmen bahan dan ATP yang konsisten.
Bangun satu ledger capacity/claim menurut product+owner+UOM dan warehouse dimensions. Harmonisasikan sales qty/roll mode, PR approval, SO fulfillment decision, PR→MKO, issue, cancel/replan dan rebuild. Tidak boleh menurunkan fisik/GL hanya karena soft reserve. Recipe/yield harus eksplisit. Total harus aggregate/kursor penuh; endpoint list boleh berhalaman dengan total terpisah.
V3-MRES-01: Serialisasi commitment pada key product+owner+unit dan dimensi gudang bila relevan. Reservasi harus CAS terhadap ledger kapasitas yang konsisten dengan sales/MKO; unique PR line/version untuk retry; shortage dilaporkan eksplisit.
V3-MRES-02: Gunakan aggregate/kursor penuh untuk seluruh total. Batasi hanya endpoint list berhalaman dengan total terpisah. Harmonisasi owner, product, unit, warehouse dan exclusion ref agar sales dan PR memakai angka sama.
Deliverable: commit, IMPLEMENTATION.md, evidence JSON/log, regression lintas flow,
serta status per ID implemented_pending_validation. Catat acceptance yang tidak
bisa dijalankan; jangan mengubahnya menjadi pass atau menghapus guard.
```

**Acceptance per ID:**

- **V3-MRES-01:** Parallel700+700 atas1000 tidak pernah reserved>1000. Remaining400 harus shortage/backorder/approval sesuai policy, tidak dianggap tersedia. Uji race dengan SO, issue/cancel/replan dan input UOM berbeda.
- **V3-MRES-02:** Cap−1/cap/cap+1 pada2000reservations,500balances,5000catalog reservations serta>10000roll allocation harus konsisten. Test total/UI/guard commit dan cancellation tidak memakai subset sebagai SSOT.


## V03 — Receipt/deposit dan rekonsiliasi bank dua sisi

ID: V3-AR-01, V3-BANK-01.

```text
Kerjakan V03: Receipt/deposit dan rekonsiliasi bank dua sisi.
Persist operation sebelum efek, tautkan tiap payment/deposit/cash/GL/allocation ke operation stable ID. Final state semua effect tepat sekali atau semuanya dibatalkan secara kontribusi. Bank harus melindungi kapasitas statement DAN cash, bukan satu sisi saja. Jalankan receipt cash/deposit/multi-SO/void/store-credit dan matching/split/unlink/fault races.
V3-AR-01: Persist receipt operation sebelum allocations. Setiap alokasi harus terkait stable receipt ID dan dapat resume/compensate tanpa menghapus payment milik operasi lain. Tangani insert/GL/cash/deposit sebagai satu protokol durable.
V3-BANK-01: Claim kedua sisi allocation dengan stable match operation dan transaksi/compensation idempoten. Revalidate statement remaining setelah claim; jangan hanya melindungi tiap cash record.
Deliverable: commit, IMPLEMENTATION.md, evidence JSON/log, regression lintas flow,
serta status per ID implemented_pending_validation. Catat acceptance yang tidak
bisa dijalankan; jangan mengubahnya menjadi pass atau menghapus guard.
```

**Acceptance per ID:**

- **V3-AR-01:** Fault sebelum receipt insert, setelah SO allocation, sebelum/sesudah GL dan saat rollback. Akhir harus semua effect100 tepat sekali atau semua batal; tidak ada SO paid tanpa receipt/deposit konsumsi. Uji multi-SO dan pembayaran bersamaan.
- **V3-BANK-01:** Dua matching paralel atas line100: satu sukses dan satu conflict atau total allocated100. Jumlah dari statement links harus sama dengan cash links. Uji split, duplicate payload, unlink/rerun/fault antar-write.


## V04 — Laporan Finance dan kontrak tanggal

ID: V3-CF-01, V3-DATE-01.

```text
Kerjakan V04: Laporan Finance dan kontrak tanggal.
Tetapkan kontrak tanggal kanonik serta settlement cash portion yang traceable. Reconcile source/subledger/bank dan laporan per periode. Asset mixed cash-credit membutuhkan cash activity40 dan noncash disclosure60, bukan sekadar net cash−40. Buat migration preview date lama sebelum apply; jangan memaksa semua contra balance menjadi cash. Minta validasi akuntan hanya untuk aturan alokasi ambigu, setelah bukti contoh/perhitungan konkret disiapkan.
V3-CF-01: Klasifikasi sumber harus membawa settlement cash portion yang eksplisit. Pecah source/mixed journal secara traceable; jangan memperkirakan aktivitas dari seluruh contra balance. Reconcile total kas dan disclosure noncash terpisah.
V3-DATE-01: Gunakan representasi tanggal kanonik di seluruh entry/create/autopost/import dan query, dengan timezone bisnis disepakati. Migration preview tanggal lama dan conflict report; hindari mengubah label saja atau memperlebar cutoff tanpa aturan.
Deliverable: commit, IMPLEMENTATION.md, evidence JSON/log, regression lintas flow,
serta status per ID implemented_pending_validation. Catat acceptance yang tidak
bisa dijalankan; jangan mengubahnya menjadi pass atau menghapus guard.
```

**Acceptance per ID:**

- **V3-CF-01:** Fixture asset cash40+credit60 harus CFI−40/CFO0/noncash60. Tambahkan asset penuh kredit, cash penuh, bank-to-bank, depreciation, sale credit+receipt dan mixed multiple assets/liabilities. Persetujuan policy akuntan diperlukan untuk metode alokasi ambigu.
- **V3-DATE-01:** Date-only/ISO/tz-offset hari awal dan hari akhir periode masuk tepat sekali. Neraca default, ledger, cash flow, closing, unlock dan konsolidasi memakai cutoff sama. Uji jurnal masa depan tetap tidak masuk hari ini.


## V05 — Variance PO dan governance master

ID: V3-PO-01, V3-PO-02, V3-PO-03, V3-MASTER-01.

```text
Kerjakan V05: Variance PO dan governance master.
Task shortage memakai PO line/version dan live received, keputusan terkait approval nyata. Tetapkan dedicated amendment/short-close yang sah bagi received lines dan lindungi bill/DP/GL posted. Master batch plan/snapshot harus durable sebelum product update, mempunyai resume/rollback dengan CAS edit berikutnya. Jangan sekaligus memigrasikan legacy tanpa dry-run signoff dan reconciliation.
V3-PO-01: Key task harus stable PO line ID/version. Refresh ordered/received/short dan close task bila selesai; keputusan memakai revalidation PO terkini. Migrasi legacy duplicate secara eksplisit, jangan menggabungkan dua harga.
V3-PO-02: Tetapkan flow dedicated receiving-variance amendment atau perbaiki CTA menjadi short-close sesuai policy disepakati. Jika amendment dipilih, target tidak kurang dari received, snapshot/bill/DP dilindungi dan reapproval/credit adjustment eksplisit; jangan rewrite posted GL.
V3-PO-03: Selesaikan task hanya setelah amendment version/line yang ditautkan approved dan acceptance shortage direvalidasi. Notes-only amendment tidak menutup qty task. Rejection/cancel amendment memulihkan action pending yang benar.
V3-MASTER-01: Persist batch plan/hash/before snapshots dan stage prepared sebelum produk diubah; pakai CAS version tiap produk dan idempoten operation. Progress parsial harus bisa resume/rollback tanpa menimpa edit sesudahnya.
Deliverable: commit, IMPLEMENTATION.md, evidence JSON/log, regression lintas flow,
serta status per ID implemented_pending_validation. Catat acceptance yang tidak
bisa dijalankan; jangan mengubahnya menjadi pass atau menghapus guard.
```

**Acceptance per ID:**

- **V3-PO-01:** Terima90 lalu95: open task received95/short5, amendment suggestion95. Terima100 menutup obsolete task. Dua legacy line memberi dua task. Race receipt vs decide tidak memakai qty lama.
- **V3-PO-02:** Kasus1000→960 memiliki jalur selesai yang nyata dan tidak buntu. Received tetap960; PO version/approval terdokumentasi; vendor bill/AP/DP diperhitungkan terpisah. Jika hanya short-close diperbolehkan, UI tidak menjanjikan amend unsupported.
- **V3-PO-03:** Amend notes saja atau awaiting approval: task pending. Approved qty960/reconciled policy: task selesai. Rejection tetap memerlukan keputusan. Beberapa task/line/versi tidak tertutup sekaligus oleh perubahan unrelated.
- **V3-MASTER-01:** Fault sebelum/antara product update dan batch insert menghasilkan batch recoverable atau tidak ada perubahan. Uji multi-produk, edits concurrent, dry-run signature stale, rollback conflict dan retry identitas sama.


## V06 — Gate passage dan loading independen per gudang

ID: V3-RFID-01, V3-WMS-02.

```text
Kerjakan V06: Gate passage dan loading independen per gudang.
Dedup event/raw noisy reads tidak boleh menggantikan current authorization pada passage baru. Loading identity per shipment/task group+warehouse+manifest version; guard dan expected EPC hanya subset tersebut. SJ mengikuti shipment actual dari gudang sumber. Policy all-tag berdasarkan user; exception hanya jika perubahan rule diratifikasi, bukan default tersembunyi.
V3-RFID-01: Bedakan replay event ID dan noisy repeated sensor read dari otorisasi passage baru. Cache tidak boleh melintasi passage atau versi shipment/QC/tag; evaluasi ulang current state untuk event baru yang memulai passage.
V3-WMS-02: Bentuk loading session per shipment/task group+warehouse+manifest version. Expected EPC dan cut guard hanya untuk shipment itu; perubahan manifest mengharuskan check ulang. Parent SO menampilkan agregat progres, bukan satu clean global.
Deliverable: commit, IMPLEMENTATION.md, evidence JSON/log, regression lintas flow,
serta status per ID implemented_pending_validation. Catat acceptance yang tidak
bisa dijalankan; jangan mengubahnya menjadi pass atau menghapus guard.
```

**Acceptance per ID:**

- **V3-RFID-01:** Same-gate event berbeda pada+20detik harus red ketika replay exit/SO cancelled/tag retired/QC hold. Repeated event_id tetap idempoten. Dwell dalam passage tidak menggandakan mutation/incident; worst verdict passage tetap red.
- **V3-WMS-02:** SO woven/knit/printing tiga gudang: WHwoven dapat check/dispatch/SJ sendiri saat cut WHknit tertunda. Check A tidak membuka B. Shipment parsial dan driver gabungan tetap mempunyai manifest dokumen yang konsisten.


## V07 — Kualitas source, reproducible build dan verifikasi operasional

ID: V3-DUP-01, V3-BUILD-01.

```text
Kerjakan V07: Kualitas source, reproducible build dan verifikasi operasional.
Satu canonical permission helper, satu lockfile sesuai packageManager, frozen install dan lint triage. Lakukan UAT browser tiga UX, entity draft switch, roll rounding, R&D performer, PO variance dan master rollback. Lanjut hardware reader/printer/alarm, multi-warehouse driver/SJ, Linux backup-restore dan recovery process. Ini gerbang pembuktian setelah patch, bukan menyatakan lulus dari build.
V3-DUP-01: Hapus definisi identik dengan satu canonical helper; tambahkan deteksi duplicate top-level definition dalam quality check yang sesuai, tanpa menggandakan business-rule tests.
V3-BUILD-01: Commit satu lockfile canonical sesuai packageManager; pipeline harus gagal jika lock tidak ada/berbeda dan memakai frozen/immutable install. Simpan runtime versions dan dependency integrity. Jangan commit node_modules/build/.env.
Deliverable: commit, IMPLEMENTATION.md, evidence JSON/log, regression lintas flow,
serta status per ID implemented_pending_validation. Catat acceptance yang tidak
bisa dijalankan; jangan mengubahnya menjadi pass atau menghapus guard.
```

**Acceptance per ID:**

- **V3-DUP-01:** Satu definisi, custom permission normal/error contract tetap sama. Jangan menjadikan ini P1 atau menghitungnya sebagai bug akses yang sudah terbukti.
- **V3-BUILD-01:** Fresh isolated install pada dua runner memakai graph/integrity sama. Build smoke lulus dari lock, lint warning relevan ditinjau; packageManager dan pipeline tidak saling memilih manager berbeda.


## Format catatan implementasi / validasi

```json
{
  "id": "V3-AR-01",
  "status": "implemented_pending_validation",
  "implementation_commit": "SHA penuh",
  "implementation_evidence": ["iterations/<tanggal-fase>/results.json"],
  "scope": "create receipt, allocations, deposit, void dan GL/cash retry",
  "migration": "none atau preview/apply/reconcile SHA + bukti",
  "limitations": ["sebutkan yang belum dibuktikan"],
  "validation_verdict": null
}
```

Setelah agent selesai, validator menjalankan failure/race/capacity serta positive control pada HEAD baru. Data lama dipisahkan dari correctness kode baru. Tidak perlu menghapus baseline yang pernah gagal; ia menjadi bukti mengapa patch diperlukan.


---

# Memo kebutuhan klien dan pembanding enterprise

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

Memo memakai penjelasan user di sesi ini, bukan asumsi atas singkatan C/H. `DECISIONS.md` kandidat menjelaskan implementasi agent, tetapi perubahan rule tidak otomatis dianggap disetujui human user.

## 1. MD dibagi menurut lini dan tugas; siapa mengerjakan hasil R&D

**Interpretasi:** MD printing/woven/knit mempunyai lini kerja dan hak akses yang dapat dikustomisasi. Printing terkait proofing, woven labdip, handfeel sesuai kebutuhan lini/spec. Wiwi menginput hasil Tita harus tetap menunjukkan Tita sebagai pelaksana.

**Sistem sekarang:** Custom role memberikan aksi modul dan line scope; detail/patch/sample/spec sudah mendapat guard lini, bukan hanya list. Round menyimpan penginput (`recorded_by`) dan pelaksana (`performed_by`) terpisah; pelaksana wajib dipilih dan harus sah di entitas/lini. Regression P08 menunjukkan submit tanpa pelaksana422, woven-only tidak membaca/patch printing403.

**Belum tuntas:** Repo memilih tidak menambah permission per jenis sampling; ini memadai bila pembatasan lini+aksi cukup, tetapi tidak bisa menggambarkan contoh Wiwi boleh labdip dan Tita boleh handfeel saja dalam lini sama. User belum meratifikasi penyederhanaan tersebut. UI histori dibaca di source; belum live UAT dengan dua akun nyata.

**Jawaban memo:** Riwayat siapa mengerjakan terakomodasi. Kemampuan custom role ada, batas granularitas perlu disepakati. Catatan W2-025 diterima spesifik; REQ-01 perlu konfirmasi bisnis, bukan otomatis bug akses.

## 2. Penamaan item, warna dan bahan standar

**Interpretasi:** Nama/SKU/kode warna harus konsisten tanpa mengarang standar perusahaan yang belum ditentukan. Benang/greige/PFD/PFP adalah master bahan/SKU yang dapat ada tanpa R&D produk MD.

**Sistem sekarang:** SKU menjadi identitas stabil. Stage (yarn/grey/pfd/pfp/finished), fabric type/lini, warna dan lot merupakan atribut berbeda. Ada rename beralasan/histori, preview legacy untuk atribut tidak kanonik/duplikasi, serta apply/rollback batch. Greige user dipetakan kanonik ke `grey`; jangan mencampur stage dengan woven/knit/printing.

**Belum tuntas:** Apply batch mengubah product sebelum snapshot durable; fault insert batch membuat perubahan tidak mempunyai batch rollback (V3-MASTER-01). Standar naming perusahaan belum ditetapkan. Mapping/alias warna customer belum lengkap/ditetapkan menurut keputusan repo; jangan menyamakan kode supplier, internal dan customer.

**Warna lahir di mana:** Pustaka `color_library` adalah master warna internal. `color_service.create_color` menerima kode internal+nama+hex dan menolak kode duplikat; bukan memakai supplier code sebagai primary key. Sample menautkan `color_target.color_id`. Pada keputusan R&D, kode/nama warna supplier disimpan sebagai `supplier_variants`, kemudian disinkronkan ke product (`color_ref`, `supplier_colors`, supplier pemenang). Special/customer-exclusive color dapat ditandai milik customer dan mempunyai kontrol penggunaan; ini berbeda dari alias kode warna customer yang belum ditetapkan. [Create master warna](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/color_service.py#L178), [sinkronisasi keputusan R&D](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_sample_service.py#L1119).

**Jawaban memo:** Struktur master lebih baik dan dapat mewakili bahan. Tata kelola belum aman untuk bulk migration. Perlu stable product/color identity, canonical attribute, alias supplier/customer dengan scope partner dan audit; bukan membuat SKU baru setiap rename. REQ-02 sebagian.

## 3. Add/delete master langsung atau master yang lahir dari R&D

**Interpretasi:** SKU bahan standar boleh langsung dibuat tanpa labdip/proofing/handfeel. SKU hasil pengembangan MD harus memenuhi uji yang berlaku per lini, spesifikasi dan persetujuan akhir dalam satu flow. Tidak berarti seluruh SKU wajib tiga uji sekaligus.

**Sistem sekarang:** Jalur create product langsung tersedia. R&D sample→hasil round→keputusan→spec→approve/release→master memakai required types per lini. Woven/knit labdip+handfeel, printing proofing dan handfeel bila spec mewajibkan. Pembentukan master bersamaan keputusan sample bersifat pilihan `approve_spec` dan memerlukan spec terkait yang masih draft/review; bila approval spec gagal, decision dapat membawa `master_error`, sehingga status sample decided saja belum menjamin SKU sudah lahir. Spec/product harus dicek di tahap akhir. Supplier/factory color merupakan metadata sumber, bukan identitas warna internal pengganti. [Keputusan sample dan approval spec](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/rnd_sample_service.py#L1133).

**Belum tuntas:** Kandidat memakai warning override: uji belum ACC dapat diteruskan dengan alasan minimal5karakter dan audit. Ini berbeda dari user yang menyebut wajib untuk SKU hasil MD. Tidak ada bukti user sesi ini menyetujui pengecualian. Jangan menandai REQ-03 tuntas hanya karena test override berhasil.

**Delete saat ini:** Endpoint DELETE products menjalankan soft deactivate (`status=inactive`) dengan permission `product.delete`, document access guard dan audit; `saga_lock` aktif memblokir. Ia tidak menghapus referensi fisik atau jurnal lama. DELETE warna juga mengubah inactive. Merge master duplikat masih memerlukan rencana referensi/migrasi tersendiri; deactivate bukan merge. [Deactivate product](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/routers/products.py#L237), [deactivate warna](https://github.com/pandeyoga/KNHOST/blob/5b7f34122bd104f4426ccd7f72b38fb7969eda8f/backend/services/color_service.py#L244).

**Jawaban memo:** Pemisahan bahan standar vs SKU hasil MD benar. Untuk kontrak user saat ini, uji wajib semestinya memblokir finalisasi SKU MD sampai ACC, atau ada pengecualian yang benar-benar disetujui. Referensi transaksi tetap dipertahankan pada deactivate. Tidak ada klaim semua referensi master legacy sudah direkonsiliasi.

## 4. Sales melihat stok grup tanpa kepemilikan; transaksi tetap antar entitas

**Interpretasi:** Sales melihat available/reserved/incoming/ATP seluruh grup tanpa harus mengetahui owner. SO entitasA yang memakai stokB tetap harus melalui pembelian/interco dan dokumen pemindahan kepemilikan yang sah.

**Sistem sekarang:** Board sales memakai `global_total` dan menyembunyikan owner/biaya dari role sales; kapasitas siap dijanjikan dari entitas aktif dipisah. Alokasi fisik masih memeriksa owner. Internal request/interco conversion dan elimination subset mempunyai perbaikan yang lulus. Incoming+available bukan janji tanggal pengiriman otomatis.

**Belum tuntas:** Ledger material reservation baru bisa overcommit dan totalnya terpotong (V3-MRES-01/02). Karena material turut memengaruhi available-to-promise maklon, angka grup belum dapat dianggap benar pada semua kapasitas/race. Group available juga harus mengecualikan hold, staged/reserved dan movement fisik sesuai definisi; jumlah incoming tidak boleh digandakan dengan barang yang sudah diterima.

**Jawaban memo:** POV sales sudah terakomodasi secara tampilan/payload. Kepemilikan tidak boleh dihapus dari source transaksi. REQ-04 sebagian karena sumber commitment belum kuat; UAT sales perlu membedakan on-hand, reserved, incoming berstatus/date dan sellable/ATP.

## 5. MD membuat PO tanpa kehilangan pekerjaan ketika pindah entitas

**Interpretasi:** Jobdesk lini MD berbeda dari entitas pembeli. MD berizin perlu dapat membeli untuk beberapa entitas tanpa mencari ulang draft/SO/PR.

**Sistem sekarang:** Form menunjukkan buyer entity dan quick switch hanya ke entitas yang boleh diakses. Draft disimpan sessionStorage; remount mengambil draft items dan mengosongkan gudang agar gudang lama tidak terbawa. Backend tetap memakai entitas aktif dan document owner guard.

**Belum tuntas:** Ini alternatif switch konteks aplikasi, bukan buyer context independen dalam satu form. Draft/reload/select buyer belum dieksekusi live browser. Bila user menerima alternatif ini, harus UAT kegagalan reload/multi-tab/storage, attachment, SO/PR link, supplier context dan permission setelah switch. Bila harus benar-benar tanpa switch global, desain buyer eksplisit masih diperlukan.

**Jawaban memo:** Alternatif tersedia; REQ-05 sebagian sampai UX dan pilihan kontrak diterima. Jangan mengklaim pengadaan grup sepenuhnya selesai hanya karena selector tersedia.

## 6. PO10 roll×100 yard, diterima total960

**Interpretasi:** Warehouse mencatat panjang/berat aktual per roll. MD diberi tahu shortage. Keputusan bisa menunggu sisa, amendment jumlah aktual, atau short-close. Nilai invoice/DP/payment harus ditangani sesuai dokumen yang benar, bukan otomatis menulis ulang GL posted.

**Sistem sekarang:** Receiving/count roll memakai UOM resmi dan actual length. Variance task memberi notifikasi MD/Finance, pilihan wait/amend/short-close serta reason. Wait mempertahankan remainder. Short-close menyelesaikan kuantitas sisa dengan jejak; tidak otomatis mengubah nilai PO/bill/DP.

**Belum tuntas:** Task tidak refresh setelah received90→95 (V3-PO-01). Amend1000→960 setelah received960 ditolak received-line guard (V3-PO-02), sehingga pilihan CTA belum nyata end-to-end. Notes-only amendment menutup task meski qty tetap1000 dan waiting_approval (V3-PO-03). PO legacy dua baris SKU sama kehilangan identitas task; PO baru duplikat produk sudah diblokir.

**Jawaban memo:** Notifikasi/alur awal ada, tetapi keputusan belum tuntas. Perlu dedicated variance amendment/credit-adjustment yang melindungi received/billed/paid snapshot, atau pilihan short-close dijelaskan sesuai policy. Pembayaran mengikuti bill/AP dan perjanjian vendor; PO short-close bukan otomatis refund. REQ-06 sebagian.

## 7. SO600 dipenuhi maklon, bahan greige1000

**Interpretasi:** Pemilihan maklon harus membedakan komitmen bahan dan keluarnya fisik. Kebutuhan dihitung dari recipe/yield/UOM; tidak otomatis600greige untuk600finished.

**Sistem sekarang:** Approved PR maklon membuat soft reservation; fisik tetap1000, available commitment turun menurut resep. PR→MKO memindahkan referensi, issue mengonsumsi material/memindahkan WIP, cancel melepaskan. Qty/roll sales guard normal memperhitungkan cadangan maklon. Reservasi yang pasti terlihat di kode dimulai approved PR, bukan otomatis pada setiap keputusan SO memilih maklon.

**Belum tuntas:** Gap SO decision→PR approval belum seluruhnya dijamin. Dua PR700+700 menghasilkan reserved1400 dari1000/shortage0;2001 reservations dihitung2000. Output production/maklon juga mempunyai failure-window yang memengaruhi nilai/fisik (V3-PROD/MKO).

**Jawaban memo:** Konsep reserve dulu, physical issue kemudian sudah ada; ketepatan commitment/recovery belum aman. REQ-07 sebagian. Acceptance harus menghitung available/reserved/subcon/WIP dan reversal, bukan sekadar field status reservation.

## 8. LOT internal, factory lot dan perubahan

**Interpretasi:** LOT internal adalah identitas traceability; factory/dye lot merupakan referensi asal. KodeA/B atau artiC/H tidak diasumsikan karena belum dijelaskan.

**Sistem sekarang:** lot_service dan roll creation membentuk lot internal/lot_id; factory/dye lot disimpan sebagai atribut sumber. Penerimaan/produksi mengikat provenance, genealogy dan parent lot; transfer mempertahankan asal, child memakai parent/root roll terpisah. Partial receive warehouse juga dipertahankan.

**Belum tuntas:** Rename item bukan rename identity lot. Jika factory lot harus dikoreksi, perlu aksi berizin beralasan, histori dan perubahan label yang mengikat roll/tag yang benar. Belum ada UAT print sticker fisik dan workflow admin gudang yang menerima notifikasi. V3-MASTER-01 menghalangi penerimaan governance bulk penuh.

**Jawaban memo:** SSOT lot internal/provenance lebih jelas; jangan menerapkan mapping pabrik123→internalA berdasarkan asumsi. Traceability harus tetap dapat menelusuri parent input→output→shipment/retur. Mismatch label fisik perlu SOP koreksi, bukan mengubah lot_id diam-diam.

## 9. Order yard vs roll dan pembulatan

**Interpretasi:** UI menunjukkan jumlah roll dan total panjang aktual pada dua mode. Whole-roll order dalam yard tidak selalu tepat; pengguna memilih naik/turun atau potong berizin secara eksplisit.

**Sistem sekarang:** Preview memakai prefix FEFO dan actual lengths. Finalisasi mensyaratkan choice round_up/round_down/exact, serta exact_cut hanya dengan permission. Qty invoice mengikuti total akhir. Contoh9×100+1×105 bisa memberi down900 atau905 menurut roll105 berada di posisi mana; jangan hard-code905.

**Belum tuntas:** Confirm cut mengurangi parent dan melepas reservation sebelum child durable. Fault membuat parent10→7 tanpa child, retry404 (V3-CUT-01). Split berat paralel juga tidak konservatif (V3-WEIGHT-01). Build/source UI lulus, choice interaction live belum UAT.

**Jawaban memo:** Mode order dan preview telah mengakomodasi perbedaan roll/yard secara konsep. Pilihan potong belum aman end-to-end; REQ-09 sebagian. Tag child, residual parent, label, qty/value/weight dan loading manifest harus selesai sebelum dispatch.

## 10. SO tiga jenis barang dari tiga gudang sampai driver

**Interpretasi:** Woven/knit/printing dapat dikerjakan masing-masing gudang. Driver mengambil shipment dengan SJ dari gudang asal; tidak perlu kembali ke entitas/gudang tertentu untuk mencetak ringkasan SO.

**Sistem sekarang:** Picking/task→manifest roll→loading check→dispatch/shipment→SJ mencerminkan dokumen yang lebih lengkap. Shipment menyimpan roll/cost/source; SJ tersedia per shipment, bukan hanya SO. Logistics delivered mencatat penyelesaian; special order menunggu seluruh shipment delivered.

**Belum tuntas:** Loading check masih satu scopeSO. Pending cut gudangknit menahan start gudangwoven siap (V3-WMS-02). Karena itu ketersediaan PDF SJ per shipment belum membuktikan fulfillment independen tiga gudang selesai. Printing printer lokal, petugas, copy driver dan tanda terima fisik belum UAT.

**Jawaban memo:** Struktur shipment/SJ tepat, pelaksanaan per gudang belum memenuhi acceptance. Loading harus scoped warehouse+shipment/task-group+manifest-version; parentSO hanya agregat progress. Jika driver menggabungkan muatan, manifest konsolidasi harus menautkanSJ masing-masing dan aktual load, bukan mengubah owner/dokumen sumber.

## 11. Semua barang bertag: stock putaway vs barang SO cross-dock

**Interpretasi:** Tidak ada bisnis barang tanpa tag menurut user. Barang untuk stock: terima/QC/tag/verify→putaway storage. Barang untuk SO: terima/QC/tag/verify→transit staging→loading/dispatch; tidak perlu dua kali penyimpanan.

**Sistem sekarang:** RFID required dan cross-dock/transit_sales tersedia. Simulated tidak menjadi verified; loading/picking mengikat roll dan manifest. Receiving goods tetap mengikuti owner/GRN/QC; jalur cross-dock tidak membebaskan kontrol itu.

**Belum tuntas:** Repo tetap menyediakan untagged exception berizin+alasan, termasuk untuk role tertentu. Secara teknis guard alasan/permission sudah berfungsi, tetapi berbeda dari kontrak all-tag user. Loading SO-wide juga menghambat jalur independen; cache gate baru dapat mengembalikan verdict lama. Belum diuji tag fisik/reader di gudang transit.

**Jawaban memo:** Kedua jalur tersedia; kontrak all-tag harus ditegakkan atau perubahan policy diratifikasi. Jangan memakai exception sebagai cara normal agar pengiriman lolos. REQ-08 sebagian mencakup poin10/11; RF05 diterima hanya untuk defect guard yang spesifik, bukan persetujuan bisnis untagged.

## 12. Tahap bahan greige/PFD/PFP dan maklon

**Interpretasi:** Stage bahan menunjukkan tahapan transformasi, terpisah dari jenis kain/lini. Maklon dapat mempunyai recipe bertahap dan genealogy dari bahan ke produk dijual.

**Sistem sekarang:** Stage yarn/grey/pfd/pfp/finished dipisahkan dari fabric_type/line_code. Recipe/step memiliki input-output, UOM, yield dan biaya. Lot genealogy serta WIP/service absorption mendukung traceability bertahap. `grey` adalah kode kanonik greige, bukan otomatis kain woven atau sebuah warna.

**Belum tuntas:** Master legacy kosong/tidak kanonik belum dapat dinyatakan sudah dimigrasikan; apply batch belum durable. Material commitment serta output/reversal harus direkonsiliasi per tahap dan unit. Tahap jasa murni tidak boleh dianggap perpindahan material tanpa output/issue yang sesuai.

**Jawaban memo:** Pengkategorian sudah dapat mewakili kebutuhan, tetapi data/master recipe dan recovery belum diterima penuh. Filter/list/UI harus menunjukkan stage dan lini secara terpisah; jangan mengandalkan naming item untuk menentukan stage.

## Perbandingan dengan praktik enterprise

Pembanding berikut dipakai sebagai kriteria fungsional, bukan klaim KNHOST mempunyai seluruh fitur produk tersebut atau harus meniru semua fitur enterprise. SAP RF handheld tidak diperlakukan sebagai bukti perilaku gate RFID.

| Kemampuan | Pembanding primer | KNHOST saat ini | Gap yang relevan |
|---|---|---|---|
| Cross-dock barang untuk demand | Microsoft mendokumentasikan alokasi received qty ke demand/staging; sisa tetap mengikuti putaway | Transit sales/cross-dock ada; user mensyaratkan seluruh barang tagged | Loading per shipment/gudang, peg qty dan tag verification perlu dibuktikan end-to-end. [Dokumentasi](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/planned-cross-docking) |
| Allocation konkurensi | Microsoft memakai locking saat wave allocation agar proses yang berebut resource tidak mengalokasikan kapasitas yang sama | Roll CAS sudah ada; material soft reservation read→insert belum aman | V3-MRES-01; qty/roll/material perlu satu definition commitment dan shortage. [Dokumentasi](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/wave-allocation-method) |
| Actual measure/catch weight | Microsoft membedakan nominal/tolerance dan actual measure/tag processing pada operasi warehouse | Roll length aktual, weight_kg dan estimated proportional split tersedia | Total weight paralel bisa naik; actual reweigh vs estimated harus jelas di UI/ledger. [Dokumentasi](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/catch-weight-processing) |
| Work/load/shipment release | Microsoft menyediakan wave processing yang membentuk dan melepas work terkait shipment/load | KNHOST mempunyai task/picking/shipment; LC masih scopeSO | Work gudangA jangan tertahan readiness gudangB; dokumen driver per actual shipment. [Dokumentasi](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/wave-processing) |
| Cash vs noncash disclosure | IAS7 mengecualikan noncash investing/financing dari cash-flow statement dan mewajibkan disclosure terpisah | Pure noncash dipisah; mixed cash-credit masih salah bucket | V3-CF-01; metode alokasi settlement harus traceable. [IAS7](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/) |

Untuk RFID enterprise, kriteria audit yang langsung relevan adalah current authorization per passage, sensor noise berbeda dari replay bisnis, manifest version, status tag/QC aktif, offline/heartbeat fail-safe, alarm yang tidak hilang karena read green terakhir, serta traceable printer/verification. KNHOST sudah memiliki bagian-bagian ini, tetapi V3-RFID-01 dan UAT hardware terbuka mencegah klaim setara enterprise operasional.

## UI/UX yang harus diterima sebelum menutup catatan

1. Gate menampilkan perangkat/direction/warehouse, heartbeat stale, passage aktif dan alasan/action per exception; red worst verdict tidak tertimpa noisy green. Uji disconnect, reconnect, browser tab background dan perubahan shipment.
2. Print/verify membedakan queued/printed/verified, manual input/simulated/device dan isu yang belum selesai. Unduh ZPL memakai entitas benar; print per gudang dan label child/parent nyata.
3. WMS memperlihatkan parent reservation vs child fisik, kg measured vs estimated, lokasi/bin/owner sesuai izin, actual receipt vs ordered serta status QC/storage/transit.
4. Sales memperlihatkan group available/reserved/incoming dengan label ATP yang benar, tanpa bocor owner/cost. MD melihat buyer yang akan dibebaniPO dan draft context setelah switch.
5. Variance task menampilkan current received, pilihan yang benar-benar dapat diselesaikan, approval state dan dampak bill/DP/AP. Catatan R&D menampilkan pelaksana dan penginput.

Semua ini merupakan daftar acceptance UI/operasional, bukan hasil UAT yang telah lulus. Source/build dan API yang sudah lulus dicatat terpisah agar status tidak menyesatkan.


---

# Data historis, kontrak bisnis dan gerbang rilis

Kandidat: `5b7f34122bd104f4426ccd7f72b38fb7969eda8f` · Validasi: 5 Oktober 2026 · Repo: [pandeyoga/KNHOST](https://github.com/pandeyoga/KNHOST).

**Fix source tidak mengoreksi otomatis dokumen dan saldo yang sudah terlanjur salah.** Laporan implementasi Wave2 mengakui beberapa data historis belum dimigrasikan. Tidak tersedia database produksi dalam audit ini; angka produksi dan keberhasilan backfill belum dapat diverifikasi.

## Rekonsiliasi read-only yang diperlukan

| Kelompok | Cari dan cocokkan | Tindakan setelah bukti tersedia |
|---|---|---|
| QC retur kg/meter | PO pricing UOM, roll actual weight, returned_qty/value, AP/cash/GL | Hitung expected net/tax/gross dan native/base qty; adjustment dokumen/jurnal yang sah, bukan rewrite diam-diam |
| Legacy split weight | Parent/root tree, cut qty, initial/remaining kg, actual weigh dan estimasi | Conservation total; jangan invent kg dari gramasi tanpa policy dan sumber ukur |
| Payroll paid tanpa cash book | Run/slip status, source_gl/cash_txn, saldo bank dan cash ledger | Stable-source repair yang tidak membayar atau mempostingGL dua kali |
| Deposit-only receipt | Receipt source, allocations/SOpaid, deposit movement, Drdeposit/CrAR, void | Backfill reklas yang missing dengan idempotency dan closed-period controls |
| Refund final tanpa cash | Stock/CN/progress, return settlement, cash transaction, GL | Resume missing cash step; jangan gandakan stock/CN/payment |
| Partial maklon warehouse legacy | Receipt step progress, roll/GRN source, gudang aktual dari bukti | Dokumen ambiguous memerlukan keputusan pemilik; jangan asumsikan current defaultwarehouse |
| Production/maklon/cut recovery | Operation/stable roll IDs, inventory_movements, qty/value, WIP/COGS/GL | Cari effects tanpa progress/movement dan output duplikat; perbaiki lewat operation recovery sesuai bukti |
| Bank allocations | Statement amount vs sum links; cash amount vs reconciled amount; unlink history | Rekonsiliasi dua sisi; jangan sekadar overwrite allocated_amount agar tampak100 |
| Material reservations | Per product+owner+UOM stock/reserved/SO/PR/MKO/cancelled | Temukan overcommit dan stale references; shortage/replan eksplisit |
| Date format | YYYY-MM-DD, ISO UTC/offset, invalid date, source date vs posting date | Preview canonical migration dan laporan sebelum/sesudah setiap cutoff |
| Governance master | Product last_governance_batch vs durable batch/history, SKU references | Temukan orphan batch markers; rekonstruksi hanya dari bukti, bukan menebak before snapshot |

## Prompt agent untuk data historis

```text
Sesudah source fix selesai, buat audit read-only pada salinan database yang diizinkan.
Jangan mulai dari bulk UPDATE. Keluarkan exception register per source document:
entity, quantity/UOM, weight, amount/tax, original GL/cash/ref, expected vs actual,
dan bukti derivasi. Pisahkan missing effect, duplicate effect dan ambiguous legacy.
Usulkan repair plan per stable operation/source ID, dry-run, closed-period behavior,
backup checkpoint serta rollback/compensating entry. Jurnal posted tidak ditulis ulang.
Mutasi data hanya setelah cakupan dataset dan concrete repair preview disetujui
oleh pemilik sesuai mandat agent. Setelah apply, reconcile seluruh subledger,
inventory value/WIP/COGS, trial balance, bank/deposit/AR/AP dan report cutoffs.
Simpan before/after hash/count, source IDs dan run id; retry tidak mengulang adjustment.
Ambiguous legacy tetap exception untuk keputusan manusia, bukan diberi angka rekaan.
```

## Keputusan bisnis yang belum dibuktikan persetujuannya

| ID | User dalam sesi ini | Implementasi/keputusan repo | Penutupan yang diperlukan |
|---|---|---|---|
| REQ-01 | MD custom role menurut lini/tugas | Lini+aksi modul, tanpa permission jenis uji | Ratifikasi bahwa granularitas ini cukup; performer vs recorder sudah berfungsi |
| REQ-03 | Uji wajib untuk SKU hasil MD; bahan standar boleh bypass | Warning+reason override mengizinkan incomplete ACC | Tegakkan wajib atau ratifikasi pengecualian formal; alasan5huruf bukan bukti persetujuan policy |
| REQ-05 | MD pengadaan lintas entitas tanpa kesulitan | Global entity quick-switch dengan draft | UAT dan persetujuan alternatif, atau buyer context eksplisit |
| REQ-08 | Semua barang bertag, termasuk SO cross-dock | Untagged exception berizin masih tersedia | Policy all-tag atau ratifikasi exception; jangan jadikan normal shortcut |

Tidak ada pertanyaan yang menghentikan audit ini. Kebutuhan ratifikasi dicatat agar agent mengajukan keputusan dengan contoh konkret, bukan mengubah fakta requirement.

## GN-14: secret dan audit evidence

Source aktif menghapus/redact credential dan audit before/after diperbaiki. Ini tidak membuktikan secret yang pernah publik sudah dirotasi/revoked. Perlu bukti revocation/rotation dari pemilik layanan, pemeriksaan riwayat sesuai scope dan deployment menggunakan credential baru. Jangan memasukkan nilai credential ke laporan/commit/log. Audit ini tidak mencoba memakai credential lama.

## Payroll: hasil test bukan sertifikasi pajak penuh

Scenario masa terakhir/Desember/termination dan prior withholding pada payroll telah diperiksa; kontrak ini selaras dengan penjelasan resmi DJP mengenai rekonsiliasi masa terakhir. Kasus karyawan nyata, komponen penghasilan/deduction, status PTKP, masa kerja dan bukti potong tetap harus dicocokkan dengan data perusahaan. [Penjelasan DJP](https://www.pajak.go.id/index.php/id/siaran-pers/perhitungan-pph-21-lebih-mudah-berikut-ketentuannya), [panduan A1 masa pajak terakhir](https://pajak.go.id/sites/default/files/2025-12/Pembuatan%20Bukti%20Pemotongan%20PPh%20Pasal%2021-Tahunan%20A1%20%20%281%29.pdf).

## Gerbang penerimaan setelah patch

1. Semua17 counterexample berubah menjadi acceptance assertion yang lulus pada SHA baru, termasuk BEFORE/AFTER-write, response lost, retry dan dua worker. Tidak ada manual unlock yang menggantikan recovery sah.
2. Positive regression gelombang1/2 tetap lulus; fixture/oracle yang berubah dijelaskan. 500/501,5000/5001,2000/2001 dan50.000/50.001 diuji pada total SSOT yang relevan.
3. Manifest/lot/tag/QC/owner/UOM/quantity/weight/value terjaga lintas receiving→putaway/cross-dock→picking/loading→shipment→SJ→delivered/return. Gudang independen mempunyai loading dan SJ independen.
4. Reconciliation Finance menyamakan source dengan AR/AP/deposit/cash/bank/GL dan cash-flow classification/cutoff. Net balance saja tidak cukup.
5. Bulk/historical repair mempunyai preview, approval cakupan, audit dan hasil reconciliation tanpa ambiguous data yang ditutup paksa.
6. UAT browser dan fisik RFID/printer/alarm/driver, restart recovery serta Linux backup-restore memiliki bukti. Lock/index/schema dan support replica-set deployment dipastikan.
7. Dependency frontend terkunci; clean install/build repeatable. Credential lama dirotasi sesuai bukti pemilik. Validator terpisah menerima setiap ID dan mencatat SHA/evidence final.

Gerbang ini menjelaskan apa yang diperlukan untuk menyatakan sistem tuntas setelah audit. Audit kandidat sekarang selesai, tetapi tidak memberi signoff produksi tanpa bukti-bukti tersebut.
