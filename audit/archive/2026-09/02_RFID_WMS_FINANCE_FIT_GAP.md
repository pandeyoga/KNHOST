> **Review lanjutan 29 September 2026:** baca [hasil validasi Astra](07_REVIEW_ASTRA_MULAI_DI_SINI.md) dan [koreksi per temuan](08_VALIDASI_65_TEMUAN.md) sebelum memakai laporan/prompt awal ini. Sebagian klaim telah dipersempit atau dikoreksi.

# Analisis fitur, UI/UX, bisnis proses, dan pembanding enterprise

Repo: KNHOST, snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`, 28 September 2026. Semua penilaian “ada” di bawah berarti implementasi terlihat dalam kode; bukan bukti sudah bekerja pada reader, printer, data produksi, atau pengguna nyata. Pembanding dipilih berdasarkan dokumentasi vendor/standar primer. Ini bukan klaim bahwa fitur seluruh vendor identik atau harus ditiru semuanya.

## 1. Kebutuhan proyek yang digunakan

Konteks dari chat **“RFID untuk WMS Enterprise”** dan **“Recall RFID gate discussion”** dibaca untuk menghubungkan audit dengan proyek ini:

- Bisnis tekstil, roll dapat diambil sebagian; jumlah meter/yard harus tetap berasal dari transaksi pengukuran/pemotongan, bukan jumlah EPC yang terbaca.
- Gudang terdiri dari beberapa bangunan menurut jenis kain. Gate harus membedakan masuk/keluar dan menahan roll yang salah bangunan atau tidak mempunyai dokumen perjalanan.
- Identitas RFID melekat pada satu roll fisik. Hasil potongan memerlukan identitas baru dan genealogy parent–child.
- Gate IN/OUT untuk D/H, reader Chainway UR300, enam antena per lane dan tunnel yang pernah dibahas sekitar 2,5 m digunakan sebagai konteks rancangan, bukan kondisi instalasi yang telah diverifikasi.

**Kesesuaian terpenting:** KNHOST sudah berorientasi roll dan read RFID tidak langsung menambah/mengurangi stok. Prinsip ini tepat. Celahnya berada pada pemecahan roll saat reservasi, validasi perjalanan, bukti pembacaan, dan konsistensi status lokasi/transit. Menambah antena atau memperpanjang tunnel tidak memperbaiki keputusan server yang memberikan green pada roll yang salah.

## 2. Peta SSOT yang seharusnya ditegakkan

| Domain | Sumber kebenaran | Turunan/observasi | Invariant wajib | Masalah snapshot |
|---|---|---|---|---|
| Identitas fisik | Roll fisik dengan ID permanen dan genealogy | Tag aktif/barcode, label | Satu tag aktif menunjuk tepat satu roll fisik; identitas tidak dibuat sebelum fisiknya ada | RF-01, RF-11, RF-15, WM-02 |
| Kuantitas | Kejadian receive/measure/cut/consume/ship/count yang disahkan | `length_remaining`, balance dan ATP | Kuantitas konservatif, unit jelas, tidak negatif; retry tidak mencipta stok | WM-01, WM-07/08, GN-06/07/13 |
| Lokasi dan perjalanan | Movement aktif yang mengikat roll/source/destination | Journey, reads, last_seen, kiosk | Read bukan bukti bahwa stock posting telah selesai; hanya satu perjalanan aktif per roll | RF-02/03/06, WM-03/04/05/09 |
| Otorisasi fisik | Manifest shipment/transfer/PA yang released dan terversi | Green/red, alarm | Gate menguji roll yang benar pada perjalanan dan lane yang benar | RF-02–07, UX-01 |
| Nilai persediaan | Cost layer/snapshot per roll dan transaksi aktual | WAC, margin, GL inventory | Nilai voucher/cost event konservatif; biaya per unit sesuai unit kuantitas | FN-01/03/11/14 |
| Keuangan | Journal posted dan subledger sumber dengan lifecycle selaras | Neraca, P&L, cashflow, aging, dashboard | Debit=kredit diperlukan, tetapi juga source/date/account/entity/classification harus benar | FN-04–16 |
| Izin data | User ID, permission, entity scope, row ownership | Filter UI/header/entity label | Filter list dan guard per-ID identik; context tidak bisa dipalsukan body atau replay | RF-08/12/13, GN-01–04/09/10 |

`inventory_rolls` bisa tetap menjadi materialized current state utama untuk operasi. Tetapi mutation history, operation ID, version, dan invariant harus cukup kuat untuk membangun ulang state serta projection. Sebutan SSOT pada komentar tidak menggantikan penjagaan di seluruh jalur tulis.

## 3. Seluruh kelompok fitur RFID yang terlihat

| Fitur dan layar | Implementasi terlihat | Nilai untuk bisnis | Kekurangan dan keputusan |
|---|---|---|---|
| Tags/untagged rolls — `RfidTagsView` | Daftar tag owner-scoped, kandidat encode, retire dan lookup roll | Identifikasi roll, penggantian tag, pencarian barang | Canonical EPC, uniqueness dan physical cut wajib diperbaiki. Retire memiliki CAS yang baik; jangan hilangkan saat refactor. RF-01/11/16/17 |
| Cetak RFID/QR — `RfidPrintVerifyPanel` | Bulk job, ZPL, antrean, manual printed, sesi verify, expected/missing/extra | Menghubungkan penerimaan dengan label fisik | Print queue ownership, read-after-write, retry dan reprint journey belum kokoh. RF-10/14/15, UX-02 |
| Devices — `RfidDevicesView` | Gate/fixed/handheld/printer, warehouse, direction, heartbeat, key provisioning | Mengelola infrastruktur per gudang | Key bocor di DTO list; disable bukan revoke; belum ada commissioning profile terversi di kontrak ingest. RF-12/13/16 |
| Reader ingest | Device-key auth, batch EPC, decision per tag, last_seen, log, incident | Pintu integrasi middleware hardware | Raw EPC tidak cocok format default; tidak memiliki event/passage identity, timestamp capture, antenna/RSSI atau lane correlation. Middleware Kotlin aktual tidak ditemukan pada snapshot repo sehingga behavior deployed belum dapat diperiksa. RF-01/16 |
| Gate monitor/kiosk — `RfidGateMonitorView` | Polling, pilihan gudang/gate, green/red/info, fullscreen, siren browser, simulasi | Memberi sinyal operator dekat pintu | Status alone mengizinkan keluar; tujuan transit bisa salah; green lama tidak kedaluwarsa; verdict satu tag. RF-02/03/07, UX-01 |
| Lokasi RFID — `RfidLocationsView` | Last seen, lokasi device dan data roll/bin | Membantu mencari keberadaan terakhir | Last_seen reader adalah observation, bukan lokasi bin pasti atau bukti bahwa roll ada sekarang. Perlu usia data, read point, confidence dan current movement; jangan menimpa lokasi fisik dari satu read |
| Security/incidents — `RfidSecurityPanel` | Insiden dari read red, tindak lanjut dan ringkasan keamanan | Menangani EPC asing/keluar salah | Dedup dan passage alarm perlu menghindari flooding; scope reads/incidents harus ditinjau konsisten dengan RF-08. Alarm acknowledge harus terpisah dari approval stock movement |
| Count RFID — `CycleCountPanel` | Snapshot expected bertag, scan, missing/extra, hasil count | Mempercepat deteksi roll yang belum ditemukan | Count ini laporan identitas tag, bukan pengukuran meter atau adjustment GL. Scope, status eligibility, coverage dan simulasi bermasalah. RF-07–10/17 |
| Final Loading Check — `LoadingCheckPanel` di WMS | Sweep vs expected SO, status terakhir dan dispatch guard | Mencegah salah muat | Tidak mandatory, tidak mencakup seluruh untagged, tidak mengikat shipment version. RF-04/05/06 |
| Roll scan/QR lookup | Identitas roll dari label dan catatan scan | Alternatif handheld/browser bagi barang non-RFID | Perlu canonical identity dan sumber scan/override yang diaudit; idempotency cookie cacat GN-01; scan teks tidak sama dengan proof hardware |

## 4. Seluruh kelompok fitur WMS yang terlihat

| Proses/fungsi UI | Implementasi terlihat | Penilaian dan gap utama |
|---|---|---|
| Warehouse/site/profile/mode | Master site/gudang, profil jenis penyimpanan, pilihan mode dan struktur zone/rack/level/bin | Struktur dasar sesuai multi-bangunan. Profile/rules harus dipanggil pada setiap movement, bukan hanya saat create PA; capability rack/bin belum setara directed work engine |
| Stok dan roll | `InventoryStockView`, summary, balances/rolls/ledger/history, initial stock dan opening cost warning | Fondasi roll/owner/bucket cukup kaya. Cap/rebuild concurrency, UOM fallback dan cost valuation belum aman pada skala enterprise. GN-12/13, FN-03/14 |
| GRN/penerimaan | Wizard/detail, supplier profile, OCR surat jalan, packing checklist, photos, review/reconciliation/variance, count dan mode | Ada dukungan operasional penerimaan yang luas. OCR merupakan usulan yang perlu review; bukti fisik quantity/UOM/lot/roll dan source PO line tetap perlu invariant. Belum diuji end-to-end dengan surat jalan/data supplier nyata |
| Scan inbound | Supplier label decoding, unreadable-label fallback, scan rows/statistics, measure confirmation/catch weight, UOM, receive trail | Mendekati kebutuhan tekstil. Label supplier tidak boleh menjadi stock posting tanpa validasi product/owner/duplicate/actual measure; uniqueness/movement cost harus konsisten dengan roll core |
| QC dan inspeksi | QC inspection, grade, roll inspection, hold/release, R&D sample comparison | Hold pada `location_service.putaway_roll` sudah memblok inspeksi yang ditahan. Perlu audit parity pada PA transfer, dispatch, regrade/return dan source status; tidak semua bucket dapat dihitung RFID RF-17 |
| Putaway intra gudang | `LocationPutawayView`, bin existence check, movement bernilai qty0 | Mampu menetapkan lokasi manual. Belum ada keputusan bin berdasarkan capacity/category/compatibility, reserve bin capacity atau scan source→destination yang wajib pada helper. Perlu directed putaway untuk gudang besar |
| PA Transit→gudang simpan | `PutawayOrdersPanel`, routing store/cross-dock, dispatch, arrival, exceptions dan BTG | Cocok dengan staging sebelum bangunan D/H, tetapi empty scan, transit available, duplicate PA dan exception ledger adalah blocker. WM-03/04/05/09 |
| Picking outbound | Scan qty/lot/roll/bin, scheduled release, escalation, resolve, packing/dispatch | CAS progress sudah ada. Validasi actual roll/bin/document dan positif quantity belum lengkap pada endpoint scan-pick. WM-06 |
| Alokasi/reservasi | Owner-aware, lot/location/roll-efficiency policies, partial allocation, FEFO/FIFO style rules, earmarking/backorders | Kuat sebagai pondasi demand allocation. “FEFO” yang menggunakan created_at perlu dibedakan dari expiry date bila produk perlu expiry. Reservasi parsial jangan menciptakan physical child sebelum cut. WM-01/02 |
| Cutting/sample | Sample cut panel, child/remnant genealogy, roll labels, sample sale/R&D material | Identitas potongan harus melalui cutting work dan aktual waste/yield. R&D issue cross-owner dan rollback unsafe. GN-04/05/07 |
| Packing/loading/shipment | Outbound badges/task panel, loading check, dispatch, shipment/delivery support | Packing dan loading harus membangun manifest shipment yang sama dengan cost/stock event. Container/cart/pallet hierarchy dan seal/loading proof perlu diputuskan menurut operasi; RF-04–06, FN-11 |
| Transfer antar lokasi/gudang/owner | Transfer management dan detail/create forms; intra_entity berbeda intercompany | Jalur transfer memakai reservation compensation; bagus untuk lifecycle. PA perlu memakai domain transfer yang sama. Intercompany quantity/value/tax pairing harus fault-tested; GN-11 |
| Stock buckets | Available/reserved/committed/picked/packed/hold/WIP/quarantine/blocked/damaged/transit/subcon | Ragam status cukup kaya, tetapi definisi eligibility di berbagai modul belum tunggal. Perlu invariant matrix setiap status terhadap on_hand/owned/ATP/count/gate/valuation. RF-17 |
| Opname dan RFID count | Opname approve/reject dan sweep RFID report | Tidak otomatis menyamakan missing read dengan stock loss, prinsip tepat. Count bin serta shortage application dan financial variance perlu perbaikan WM-07/08 dan FN-14 |
| Return/regrade/writeoff | Sales/purchase returns, return chain, regrade, supplier RMA/debit note | Fitur bisnis tersedia; partial physical return dan concurrent consume harus melalui core yang sama. GN-07; valuation harus mengacu event cost snapshot, bukan WAC berubah |
| Operations/health | `OperationsView`, task queues, `WmsHealthDashboard`, journeys/timelines | Bagus untuk visibilitas. Health harus mengukur failed operation, unresolved variance, projection lag, event age dan device enabled/heartbeat; badge online tidak boleh dianggap read quality |

## 5. Pembanding enterprise yang relevan

### 5.1 Directed work dan slotting

Dynamics 365 memakai **location directives** untuk memilih lokasi pick/put/stage berdasarkan work type dan rules. Ini mendukung kebutuhan putaway serta pengambilan yang dipandu sistem. KNHOST mempunyai struktur bin dan assignment manual, tetapi helper putaway hanya memeriksa keberadaan bin serta inspection hold; belum terlihat mesin directive setara pada jalur yang diperiksa. [Microsoft — location directives](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/create-location-directive).

Target KNHOST: rule kategori kain/grade, kapasitas fisik yang jelas satuannya (roll/volume/berat/panjang sesuai kebutuhan), lokasi quarantine, kedekatan staging, larangan campur lot/owner bila diperlukan, serta reservation kapasitas saat work dikeluarkan. Aturan harus bisa di-override berizin dan tetap memberi alasan pilihan bin. Ini gap fitur, bukan alasan mengganti seluruh WMS.

### 5.2 Replenishment dan wave/zone picking

Dynamics 365 mendokumentasikan replenishment min/max, wave demand, load demand dan immediate replenishment. Oracle WMS mendokumentasikan RF zone tasks yang dihasilkan melalui task/wave templates. KNHOST mempunyai task dan demand/ATP, tetapi belum ditemukan engine replenishment pick-face dan wave/zone orchestration yang sebanding pada flow yang ditelusuri. [Microsoft — replenishment](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/replenishment), [Oracle WMS — zone picking](https://docs.oracle.com/en/cloud/saas/warehouse-management/26a/owmol/executing-pick-zone-tasks-in-the-rf.html).

Target sesuai bisnis: utamakan system-directed single-order roll picking dan replenishment area picking terlebih dahulu; wave/batch/zone picking bernilai bila volume dan jarak antarbangunan membenarkannya. Jangan memprioritaskan optimasi rute sebelum wrong-roll validation dan manifest dispatch benar.

### 5.3 Count terjadwal, blind count dan review

Dynamics 365 mendukung count work dari threshold/plan, input mobile per lokasi, blind expected quantity dan pending review untuk selisih. KNHOST memiliki approval stock opname dan RFID sweep, tetapi bin scope salah, expected terlihat pada sweep, untagged coverage hilang, dan adjustment belum tervaluasi/berjurnal. [Microsoft — cycle counting](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/cycle-counting).

Target: ABC/threshold/scheduled count, count scope/location lock atau movement-aware reconciliation, blind quantity bagi petugas, recount oleh petugas berbeda, deviation tolerances, manager approval, dan GL variance. Untuk RFID, tampilkan tag recall dan unresolved identity; tidak menyatakan jumlah meter terukur hanya karena EPC ditemukan.

### 5.4 Observasi RFID vs event bisnis

GS1 EPCIS/CBV menyediakan model event traceability dengan dimensi apa/kapan/di mana/konteks bisnis; read point tidak sama dengan business location. KNHOST menyimpan reads dan last_seen, tetapi metadata passage, event identity, capture time dan business movement binding belum mencukupi untuk traceability setara. Kepatuhan EPCIS penuh tidak wajib bagi sistem internal, tetapi model semantiknya berguna. [GS1 — EPCIS](https://www.gs1.org/standards/epcis), [EPCIS 2.0.1](https://ref.gs1.org/standards/epcis/2.0.1/), [pedoman EPCIS/CBV](https://ref.gs1.org/guidelines/epcis-cbv/2.0.0/).

Target: simpan raw observations; bentuk passage event setelah korelasi antena/sensor/time window; evaluasi manifest; kirim disposition green/red/unknown; posting movement tetap melalui dokumen yang valid. Simpan operator override dan reason tanpa menulis ulang event asli. EPC internal tidak boleh disebut encoding GS1/SGTIN standar hanya karena panjangnya 96 bit.

### 5.5 Gate D/H dan reader Chainway

Dokumentasi Impinj menjelaskan konfigurasi daya pemancar dengan menguji orientasi tag terburuk dan menghindari pembacaan liar. Ini prinsip commissioning, bukan nilai daya/antena yang otomatis berlaku pada UR300. [Impinj — contoh konfigurasi inventory](https://support.impinj.com/hc/en-us/articles/32153110595219-Impinj-IoT-Device-Interface-API-Example-Inventory-Configurations).

Tunnel ACP dan antena lebih banyak tetap memerlukan pengujian di site. Mulut tunnel, rak dekat pintu, multipath dan dua lane berdekatan dapat membuat tag diam/salah lane terbaca. Audit ini tidak mempunyai middleware Kotlin atau pengukuran radio aktual, sehingga tidak menyatakan tunnel 2,5 m maupun enam antena pasti cukup.

Kontrak yang dibutuhkan untuk gate proyek:

1. Lane/gate ID terpisah untuk D-IN, D-OUT, H-IN, H-OUT; arah benar dari sensor/antenna correlation atau desain lane yang tervalidasi.
2. Passage ID dengan awal/akhir, daftar EPC union, capture timestamps, antenna/read count/RSSI bila reader menyediakan, dan dedup retry.
3. Satu verdict passage: satu roll salah membuat keseluruhan passage TAHAN; green hanya setelah seluruh identitas expected/observed tervalidasi sesuai policy.
4. Alarm fisik reader/middleware bekerja meskipun browser mati; kiosk hanya menampilkan status yang sama, umur data dan kesehatan koneksi. Wiring/alarm middleware belum diverifikasi dari repo ini.
5. Offline buffer dengan event ID, urutan dan acknowledgement; jangan memberi silent green ketika layanan authorization tidak dapat dihubungi.
6. Profile commissioning terversi per gate: antena, power, region legal dan certified reader profile, read window, adjacent lane filtering, sensor dan commissioning date. Pembahasan EU sebelumnya bukan validasi frekuensi untuk lokasi instalasi aktual.

Uji penerimaan hardware harus menggunakan roll/tag/orientasi dan kecepatan trolley sebenarnya, batch rapat, roll kecil/remnant, rak di sekitar mulut, dua lane bersamaan, stop/reverse di tunnel, reader/network restart, duplikat EPC dan wrong manifest. Ukur read recall per passage, stray-read false positive, wrong-lane/direction rate, missed unauthorized roll, latensi alarm dan recovery backlog. Ambang angka harus disepakati dari risiko/throughput site; audit ini tidak mengarang SLA read rate 99,9%.

## 6. Penilaian UI/UX operasional

Penilaian ini dari komponen, conditional rendering, tombol, transport API dan business state. Tidak ada klaim uji pixel, aksesibilitas penuh, ergonomi perangkat atau usability study; aplikasi belum dijalankan dengan Mongo dan hardware.

| Area | Yang sudah membantu | Masalah pengguna | Desain yang diminta |
|---|---|---|---|
| Gate kiosk | Huruf verdict besar, fullscreen, kode gate, timestamp dan siren toggle | Green lama tetap tampak LIVE; satu tag terakhir mewakili batch; history gate dapat tenggelam | Tampilan per passage, green sementara, red latched, OFFLINE/UNKNOWN mencolok, usia event, ACK terpisah dari override |
| Cetak/verifikasi | Pilih roll, status job, missing/extra dan download | Simulasi menyatu produksi; queued disebut printed pada journey; gagal verify sulit diulang | Pisahkan setup/test dari operasi, status hardware perlabel, tombol retry missing, replacement flow tanpa mengubah lokasi |
| Count RFID | Expected/found/missing/extra mudah dipahami | 100% bisa hanya subset bertag; multi-owner 403; count tidak meter | Tampilkan coverage tag, read recall, unresolved/extra, actual count scope dan pintu recount/manual follow-up |
| Loading | Check berada dekat outbound | “Clean/dispatch dibuka” tidak menjamin seluruh roll/shipment tervalidasi | Ringkasan manifest shipment/version, tagged/untagged unresolved, checklist identity lengkap, blocker tepat dan override manager beralasan |
| Putaway PA | Source/destination dan status perjalanan terlihat | Empty scan dianggap semua tiba; status transit tidak sama dengan ATP | Wajib mode scan/manual eksplisit, expected vs observed perroll, partial arrival, scan tujuan/bin, tampil stock bucket transit |
| Picking handheld | Task panel dan scan trail | Endpoint menerima roll/bin arbitrary; qty negatif; operator bisa mencatat salah tanpa teguran | Server-resolved identity, wrong SKU/owner/bin haptic/beep dan reason, satu aksi utama, keyboard focus tetap, undo event explicit |
| Stok/health | Detail roll/journey/grade/ledger memudahkan investigasi | SSOT/projection/metrik scope dapat berbeda tanpa peringatan | Tampilkan owner dan unit base/native, snapshot time/revision, drift dan pending operations; zero-cost inventory diberi blocker yang actionable |
| Scope badan usaha | Entity selector dan header API tersedia | Direct download kehilangan selected scope; beberapa by-ID bypass | Banner entity+warehouse konsisten; transport context tunggal; server menjaga izin bahkan bila UI kehilangan filter |
| Failure/recovery | Error notice, saga-lock monitor dan beberapa CAS | Lock release tidak menjelaskan efek yang sudah terjadi | Recovery panel dengan operation stage/effects, resume/compensate terkontrol dan instruksi petugas yang tidak menyuruh “coba lagi” sembarangan |

## 7. Rancangan business process minimal yang layak

### Receiving sampai stored

PO line approved → receipt actual measure/UOM/lot/owner → roll physical identity → QC disposition → queued label → printer write/readback → tag verified → destination work → OUT origin authorized → transit bucket → IN destination authorized → arrival subset → scan bin → stored. Setiap tahap memiliki operation ID dan version, quantity/value conservation dan exception yang dapat dipulihkan. Cross-dock menggunakan jalur tersendiri yang tidak memaksa PA storage atau mengganti owner tanpa intercompany event.

### Reserve sampai shipment

SO approved/credit/pricing valid → quantity reservation → roll selection → actual cut bila perlu → verify identity child/remnant → pick dari bin yang benar → pack manifest shipment terversi → sweep seluruh identitas/override terkontrol → gate OUT terhadap manifest tersebut → stock dispatch dan frozen cost snapshot → revenue/COGS source-linked → delivery/return handling. Physical gate read sendiri tidak boleh langsung menambah/mengurangi stock.

### Transfer bangunan D/H

Request movement → roll claim tunggal → destination/category rules → manifest release → source OUT → at-transit → destination IN → partial receipt dan exception → bin confirmation. Salah lane/bangunan, unknown EPC, stale document dan duplicate passage ditahan. Pemindahan intra-owner tidak melahirkan penjualan antar-PT; ownership transfer mempunyai proses finansial terpisah.

### Partial cutting

Roll parent aktual 100 → reservation 30 tanpa mengubah identitas fisik → cut work actual 30, remainder 70, waste bila ada → parent/child genealogy → tag/label anak unik → balance/cost konservatif → manifest membawa anak 30. Panjang bukan derived dari EPC count. Reservasi yang dibatalkan sebelum cut tidak perlu menciptakan/menghapus fisik baru.

### Opname dan penyesuaian

Scheduled/spot work per owner/location → snapshot/version atau reconciliation movements selama count → blind measured quantity dan RFID identity sweep → recount/deviation review → manager approve → exact roll adjustment → inventory value variance JE → reconciliation. Missing RFID hanya indikasi tidak ditemukan, bukan otomatis hilang stok; extra RFID harus diperiksa destination/owner dan duplicate tag.

## 8. Finance: apa yang benar arah desainnya, dan apa yang belum akurat

Implementasi mempunyai GL double-entry, source-linked autoposting, laporan dari journal, opening balance, period close/unlock, inventory reconciliation, AR receipts/deposits, AP/vendor bill matching, bank reconciliation, landed cost, fixed assets, tax, payroll dan intercompany/consolidation. Ini cakupan fitur yang luas; ketersediaan menu bukan bukti angka benar.

Kontrol positif yang terlihat: manual journal minimal dua baris, active/postable account global, source dedup journal index di bootstrap, period guard saat insert, scope journal detail/void, CAS beberapa receipt/stock/task, dan projection inventory dari rolls. Beberapa index failures hanya dilog saat bootstrap sehingga keberadaan index deployed masih perlu diverifikasi. Jangan melemahkan kontrol yang benar ketika memperbaiki temuan.

| Area Finance | Masalah akurasi yang ditemukan | Pemeriksaan selesai yang diperlukan |
|---|---|---|
| Nilai inventory/HPP | Landed cost parent–child double apply; mixed-UOM WAC; shipment cost rata-rata SO; count surplus0cost dan shortage tanpaJE | FN-01/03/11/14, voucher value conservation dan GL inventory = cost layers |
| Kas/bank | Cash manual tidak langsung post, void tanpareversal, openingrekening editable tanpaJE, receipt financialfailure swallowed | FN-07/08/10, perrekening cashledger=GL dan sourceallocation reversal |
| AP/pembelian | Duplicate line 3-way match overbill; concurrent billing perlu validate receipt capacity | FN-02, line-ID + aggregate prior/current/pending dan fault recovery |
| Laporan | COA lintasentity last-write-wins, cashflow noncashclassification, cap100kJE, futuredate defaultneraca | FN-04/05/16, GN-12; independent fixture dan fullaggregation |
| Tutup buku | Void melewati lock; close race; stale periods dan unsafe recovery | FN-09/13, GN-11; unique logical revision dan guard semua mutations |
| Aset | Masterfinancial amendment tidak menyelaraskan acquisitionJE | FN-12; register, originalcost, dep dan JE reconciliation |
| Pajak payroll | TER lastperiod, annual reconciliation missing, flat OT dan sourceoverlap | HR-01/02; perhitungan regulasi independent dan policy effective-date |
| Tax PPN/intercompany | Mesin tax/config dan paired docs terlihat, tetapi tidak diberi sertifikat compliance dalam audit ini | Uji PKP/nonPKP, included/excluded, DPP policy/effective-date, return/credit note, Faktur Pajak, pair elimination dan rounding |
| Revenue/AR | Recognition per shipment dan advance/AR helpers terlihat | Partialshipments, source timestamp, discount/PPN allocation, returns/storecredit/refunds, overpayment/deposit reallocation, lockedperiod dan multientity tests |

IAS7 mengharuskan indirect cashflow menyesuaikan item nonkas dan membedakan aktivitas operasi/investasi/pendanaan; balanced identity saja tidak cukup. Dua reproduksi FN-04 menunjukkan kegagalan prinsip tersebut. [IFRS — IAS7](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/).

DJP menjelaskan TER bulanan dipakai selain masa pajak terakhir; masa terakhir memakai tarif Pasal17 dan rekonsiliasi penghasilan setahun/bagian tahun. Formula payroll snapshot tidak menunjukkan jalur itu. [DJP — skema TER dan masa terakhir](https://www.pajak.go.id/index.php/id/artikel/tarif-efektif-rata-rata-penyempurnaan-perhitungan-pph-pasal-21).

PP35/2021 membedakan multiplier lembur jam pertama dan berikutnya pada hari kerja, serta ketentuan hari istirahat/libur. Formula satu multiplier untuk totalminutes tidak mewakili pembagian itu. Audit belum menilai seluruh pengecualian sektor/jenispegawai; policy harus diperiksa sesuai pekerjaannya. [PP35/2021 — naskah resmi](https://peraturan.bpk.go.id/Download/154582/PP%20Nomor%2035%20Tahun%202021.pdf).

## 9. Urutan prioritas dan syarat layak

**Tahap A — integritas dan akses:** canonical EPC, device credentials, scope perID/replay/WS, roll mutation/compensation dan movement claim. Prioritaskan RF-01/02/03/08/12/13, WM-01/03/04/05/06, GN-01–07/09/11. Jangan memperbaiki tampilan agar seolah berhasil dengan melonggarkan guard server.

**Tahap B — correctness Finance:** landed/WAC/shipmentcost/countvaluation, cashbank/sourceJE lifecycle, effectiveCOA, cashflow, closing/lock dan payroll. Migrasi harus dimulai read-only discrepancy report, approved accounting correction, reversal/adjustment dengan jejak; jangan rebuild history atau mengisi opening equity untuk menyembunyikan drift operasional.

**Tahap C — workflow dan UX:** shipmentmanifest version, mandatory loading policy, print lease/readback/retry, scanphysical identity, count scope/coverage, gate stale/offline UI dan safe recovery.

**Tahap D — enterprise efficiency:** directed putaway, capacity reservation, scheduled/blind count, replenishment, zone/wave work, container/pallet/cart hierarchy dan labor/throughput KPI bila volume menuntut. Ini enhancement terpisah dari pembuktian data benar.

Sistem layak untuk pilot terbatas setelah seluruh blocker pada flow pilot ditutup dan integration tests lulus. Layak enterprise setelah invariant stok/nilai, negative cases, fault/retry/restart, concurrency, full-size aggregation, isolation, commissioning hardware dan rekonsiliasi akuntan terverifikasi. Audit source ini tidak menyatakan tahap-tahap tersebut sudah lulus.
