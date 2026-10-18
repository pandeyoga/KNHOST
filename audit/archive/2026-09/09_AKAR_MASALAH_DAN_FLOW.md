# Akar masalah dan flow lintas modul — review Astra

Baseline `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467` · 29 September 2026.

## Kesimpulan teknis

Temuan awal sebagian besar bertahan, tetapi masalah terpenting bukan jumlah endpoint yang bermasalah. **Tidak ada kontrak kuat yang mengikat barang fisik yang dipilih, bukti identifikasi, otorisasi perpindahan, mutasi inventori, dan pengakuan nilai sebagai satu operasi bisnis.** Sejumlah fungsi sudah memakai CAS atau saga claim. Kontrol itu tetap dapat gagal ketika snapshot dibaca sebelum claim, lock dilepas sebelum seluruh efek persisten, atau dokumen parent terkunci sementara roll child tidak memiliki precondition.

“Roll adalah SSOT” baru berguna apabila penulis roll mematuhi invariant yang sama dan setiap projection, manifest serta cost layer dapat ditelusuri ke versi roll/event yang sah. Saat ini beberapa data menjadi sumber kebenaran bersaing: task quantity, roll status, journey, SO loading_check, shipment.rolls, inventory_balances dan journal_entries.

## Peta tanggung jawab yang disarankan

| Fakta bisnis | Sumber otoritatif yang disarankan | Yang tidak cukup untuk membuktikannya |
|---|---|---|
| Roll fisik dan panjang aktual | Physical roll + cut/measurement event, unit base dan version | Reservasi qty atau EPC |
| Tag milik roll | Tag binding version, lifecycle active/retired/replaced | Label tercetak di layar |
| Stok dapat dijual | Policy atas posisi, QC, commitment dan movement aktif | Status available saja |
| Roll benar sudah diambil | Pick confirmation terikat work line, roll, bin dan quantity | Counter picked_qty |
| Barang boleh keluar | Released manifest versi tertentu dan movement authorization | Tag terbaca atau status committed |
| Barang benar melewati gate | Passage evidence reader/edge terikat lane dan waktu | Satu raw EPC read |
| Barang resmi berpindah | Movement committed dengan operation_id dan precondition | Lampu hijau |
| Nilai persediaan/HPP | Cost layer/subledger policy dan posting event | Unit cost master terbaru |
| Laporan keuangan | Jurnal posted, effective COA, period dan reconciliation | Angka report yang totalnya seimbang |

## Catatan prioritas

AX adalah penjelasan lintas-flow/temuan lanjutan, bukan tambahan buta terhadap 65 temuan. Sebagian memperluas ID lama; jangan menjumlahkannya menjadi 73 bug independen. P1 perlu diselesaikan sebelum flow tersebut menjadi kontrol produksi yang diandalkan. P2 penting untuk correctness/traceability. Tidak ada penetapan P0 berdasarkan bukti kerusakan produksi karena data produksi tidak diperiksa.

<a id="ax-01"></a>

## AX-01 — Roll yang dipindai tidak menjadi identitas yang wajib dikirim

**Prioritas:** P1. **Hubungan audit:** Perluasan WM-06, RF-06, FN-11; celah pemilihan roll pada dispatch dipertegas oleh pengujian baru.

**Letak kode:** [backend/routers/outbound_picking.py:82](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L82); [backend/services/shipment_service.py:31](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/shipment_service.py#L31); [backend/services/roll_service.py:963](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L963); [backend/services/loading_check_service.py:17](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L17).

**Skenario dan bukti:** Dua roll OLD dan NEW, masing-masing 50 m, sama-sama committed untuk SO yang sama di W1. Task dan scan_log menunjukkan NEW 50 m, picked_qty=50. Dispatch 50 m memilih OLD. V2-13 menghasilkan picked_roll=NEW dan shipped_roll=OLD.

**Kesalahan logika:** dispatch_task hanya mengirim order_id/product_id/warehouse_id/qty ke ship_order_rolls. Helper mencari ulang roll berdasarkan reserved_ref dan status, lalu mengurutkan created_at/ukuran. task.roll_id, scan_log, allocation identity dan manifest yang dipindai tidak menjadi filter. Urutan itu tidak otomatis FEFO karena tidak menggunakan expiration date.

**Dampak bisnis:** Surat jalan dapat menunjuk benda berbeda dari barang di truk. Stok roll yang masih di rak dianggap keluar, sedangkan roll yang benar-benar keluar masih tersedia untuk proses lain. Tag loading/gate dan HPP kemudian mengacu pada identitas berbeda. Ini bukan sekadar salah tampilan picking.

**Arah perbaikan:** Persist pick lines dengan physical roll_id, qty base, source bin, allocation_id dan roll version. Bentuk shipment manifest dari pick lines terkonfirmasi. Release/dispatch harus mengonsumsi manifest tersebut tanpa memilih ulang roll. Reallocation harus perintah eksplisit yang membatalkan bukti loading lama.

**Acceptance criteria:** Dengan OLD/NEW berbeda cost, lot dan tag: pick NEW harus menghasilkan shipment NEW, movement NEW dan cost menurut policy untuk NEW; scan OLD harus ditolak atau membutuhkan reallocation terotorisasi. Partial dispatch menyisakan tepat pick line yang belum dikirim.

<a id="ax-02"></a>

## AX-02 — Task dispatch dianggap selesai sebelum surat jalan tersimpan

**Prioritas:** P1. **Hubungan audit:** Perluasan GN-11 dan FN-10; failure window baru yang spesifik dan direproduksi.

**Letak kode:** [backend/services/shipment_service.py:71](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/shipment_service.py#L71); [backend/services/shipment_service.py:94](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/shipment_service.py#L94); [backend/services/atomic_claim.py:48](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/atomic_claim.py#L48).

**Skenario dan bukti:** Pengiriman 100 m memindahkan roll ke in_transit_sales dan task ke dispatched. Insert shipments sengaja gagal. V2-14: task dispatched, tidak ada saga_lock, dua roll transit, shipments=0.

**Kesalahan logika:** finish_set melepas lock pada update task sebelum nomor/record shipment dan efek terkait tersimpan. Exception handler hanya mengelilingi ship_order_rolls. Kegagalan sesudah task update tidak mempertahankan state recoverable. Komentar “SSOT-safe” tidak membuktikan atomicity lintas koleksi.

**Dampak bisnis:** UI/task dapat mengatakan sudah dikirim tanpa surat jalan yang bisa ditelusuri. Retry ditolak karena task dispatched, sementara worker stuck-saga tidak melihat lock. Revenue/COGS sesudah insert juga belum dijalankan. Memaksa unlock tidak menyelesaikan kondisi ini.

**Arah perbaikan:** Buat operation_id yang persisten sebelum efek stok. Commit roll changes, movement, shipment dan task progress dalam transaksi bila deployment mendukung; jika saga, simpan step dan deterministic shipment identity, lanjutkan secara idempotent. Finish hanya setelah durable business effects dan kewajiban outbox tercatat. Recovery harus mencari orphan berdasarkan operation_id, bukan keberadaan lock saja.

**Acceptance criteria:** Matikan proses setelah setiap write dan ulangi request dengan key sama/berbeda: tepat satu shipment untuk operation, task sama dengan sum shipment valid, tidak ada qty tanpa movement, GL pending terlihat atau posted sekali. Transaksi committed tetapi HTTP response hilang harus mengembalikan hasil lama.

<a id="ax-03"></a>

## AX-03 — Claim bergantian masih membolehkan progres partial shipment ditimpa

**Prioritas:** P1. **Hubungan audit:** Perluasan GN-11 dan kontrol concurrency outbound; bukan duplikat kegagalan insert AX-02.

**Letak kode:** [backend/services/shipment_service.py:41](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/shipment_service.py#L41); [backend/services/shipment_service.py:60](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/shipment_service.py#L60); [backend/services/shipment_service.py:68](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/shipment_service.py#L68).

**Skenario dan bukti:** Dua request membaca task quantity=100, picked=100, shipped=0. Request pertama dispatch 30 lalu selesai. Request kedua memegang snapshot lama dan setelah lock bebas dispatch 30. V2-15: sum shipment=60, task shipped_qty=30.

**Kesalahan logika:** already/picked dihitung sebelum claim. Precondition claim hanya melarang beberapa status final; partially_shipped masih sah. Setelah memperoleh lock fungsi tidak membaca ulang quantity/progress. new_shipped menggunakan already lama dan ditulis $set.

**Dampak bisnis:** Remaining task dan status SO dapat salah meski semua response sukses dan lock tidak pernah aktif ganda. Perhitungan boleh-kirim berikutnya terlalu besar terhadap progres task. Menaikkan durasi lock atau memasang debounce tombol tidak menghilangkan stale snapshot.

**Arah perbaikan:** Claim harus memeriksa version dan membaca state otoritatif setelah acquire. Jadikan shipped progress derivasi shipment committed atau atomic increment dengan invariant picked_remaining dan work version. Operation ID menghindari replay request sama; version menghindari konflik dua request berbeda.

**Acceptance criteria:** Barrier dua pembaca → claim bergantian. Hasil sah: satu request conflict dan reload, atau keduanya sukses dengan task shipped=60. Tidak boleh dua shipment total60 dengan task30. Tes melebihi remaining serta request response-lost.

<a id="ax-04"></a>

## AX-04 — Transfer roll eksplisit melewati owner filter dan rebuild balance

**Prioritas:** P1. **Hubungan audit:** Temuan baru pada jalur alternatif reservasi; terkait GN-04, GN-13 dan prinsip scope roll.

**Letak kode:** [backend/services/roll_service.py:1326](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L1326); [backend/routers/transfers.py:203](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L203); [backend/routers/transfers.py:206](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L206).

**Skenario dan bukti:** Gudang W1 dipakai A dan B. Caller memilih owner A tetapi memasukkan ID roll B untuk product sama. V2-17 memanggil service dengan parameter itu: roll B reserved, rebuild dipanggil 0 kali. Router me-resolve owner lalu meneruskan ID pilihan tanpa validasi owner per roll.

**Kesalahan logika:** Cabang if roll_ids mencari id/product/status, memeriksa warehouse, tetapi tidak owner_entity_id. Setelah update ia return sebelum loop rebuild yang ada di cabang quantity. Availability projection bisa tetap lama bahkan ketika roll sudah reserved.

**Dampak bisnis:** Dokumen transfer dapat berowner A sementara roll aktual B ikut terikat. UI balance menjanjikan stok yang sudah dibooking. Pagar warehouse yang sah untuk A tidak cukup karena warehouse fisik bersama dapat menyimpan beberapa owner.

**Arah perbaikan:** Validasi seluruh pilihan sekaligus terhadap owner/product/source/status/positive qty dan roll version sebelum mutation. Setiap reservation memakai conditional update dimensi sama; semua branch menuju projection update/outbox yang sama. Bila satu gagal, recovery tidak boleh melepas reservasi milik operation lain.

**Acceptance criteria:** A-only caller + roll B ditolak sebelum side effect; creator A+B tetap tidak boleh menaruh B pada dokumen intra-A. Pemilihan ID dan auto quantity memberi balance yang identik. Uji satu roll konflik di tengah batch dan rollback milik operasi sendiri.

<a id="ax-05"></a>

## AX-05 — Penerimaan transfer menghilangkan asal PO dan membawa bin gudang lama

**Prioritas:** P1. **Hubungan audit:** Temuan baru lintas WMS–Finance; memperluas FN-01 dan masalah lokasi/provenance.

**Letak kode:** [backend/services/roll_service.py:1429](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L1429); [backend/services/landed_cost_service.py:57](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/landed_cost_service.py#L57).

**Skenario dan bukti:** Roll dari PO, bin BIN-W1, dikirim TR dari W1 ke W2. V2-12: warehouse berubah W2, bin tetap BIN-W1, acquired.ref_id menjadi TR. Query biaya masuk memakai acquired.ref_id=PO tidak lagi memilih roll tersebut.

**Kesalahan logika:** Satu field acquired dipakai untuk asal perolehan dan perpindahan terakhir. Receipt transfer menimpa metadata perolehan, sementara tidak mengosongkan atau mengganti bin. Dua konsep lokasi dan satu konsep biaya asal berubah tanpa invariant bersama.

**Dampak bisnis:** Peta lokasi menunjukkan pasangan warehouse/bin yang tidak valid. Biaya freight/import yang datang terlambat dapat melewatkan roll yang sudah dipindah. Genealogy dari PO ke stok/COGS terputus. Tag warehouse sebenarnya sudah di-update oleh fungsi ini; itu bukan defek yang dituduhkan.

**Arah perbaikan:** Simpan acquisition/receipt_line/cost_layer asal immutable, movement history terpisah. Receipt masuk receiving/staging bin tujuan yang valid, atau bin=None sampai putaway; jangan retain source bin. Migrasikan acquired legacy dengan bukti movement, bukan menebak PO dari field terakhir.

**Acceptance criteria:** PO receipt → transfer W1→W2 → late landed cost tetap mencakup qty/cost layer yang tepat; warehouse/bin valid. Transfer dua kali tidak mengubah acquisition origin. Cek persediaan per entity sebelum/sesudah transfer intra tidak berubah nilai tanpa biaya baru.

<a id="ax-06"></a>

## AX-06 — Print job multi-owner membocorkan item melalui owner header pertama

**Prioritas:** P1. **Hubungan audit:** Temuan baru pada authorization agregat; tidak sama dengan masalah count RF-08.

**Letak kode:** [backend/services/rfid_print_service.py:113](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L113); [backend/services/rfid_print_service.py:125](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L125); [backend/services/rfid_print_service.py:166](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L166).

**Skenario dan bukti:** Creator yang sah melihat A+B membuat satu job untuk dua roll di gudang sama. Header owner=A karena roll pertama A. V2-18: caller berscope [A] dapat get_print_job dan melihat item B.

**Kesalahan logika:** Create memeriksa scope setiap roll tetapi tidak mensyaratkan satu owner. Detail mengotorisasi parent berdasarkan satu owner saja, lalu mengembalikan semua item termasuk ZPL. Urutan query menentukan owner header.

**Dampak bisnis:** Akses yang sah saat create menjadi akses terlalu luas saat job dibaca, dicetak atau diverifikasi kemudian oleh user lain. Scope parent tidak mewakili sensitivitas seluruh child.

**Arah perbaikan:** Pilihan sederhana: satu job per owner+warehouse, pecah batch multi-owner secara eksplisit. Alternatif harus menyimpan scope anggota dan mensyaratkan akses seluruh anggota; jangan sekadar filter sebagian items karena expected verification berubah. Audit QR label job untuk pola sama. Validasi semua anggota sebelum encode agar kegagalan satu item tidak meninggalkan tag orphan.

**Acceptance criteria:** A+B boleh membuat batch yang menghasilkan dua job; A-only tidak pernah menerima item B atau ZPL-nya. Tes urutan item dibalik, route download, list/detail/verify, job legacy campuran, serta gagal validasi item terakhir.

<a id="ax-07"></a>

## AX-07 — Potongan generasi kedua mencatat kakek sebagai parent langsung

**Prioritas:** P2. **Hubungan audit:** Temuan baru tentang genealogy roll; terkait WM-02 dan FN-01.

**Letak kode:** [backend/services/roll_service.py:93](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L93); [backend/services/roll_service.py:111](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L111); [backend/services/roll_service.py:511](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L511).

**Skenario dan bukti:** ROOT dipotong menjadi CHILD; CHILD dipotong lagi menjadi GRANDCHILD. Caller menyalin parent seperti _split_roll. V2-19 menghasilkan GRANDCHILD.parent_roll_id=ROOT meski parent aktual CHILD; root_roll_id=ROOT tetap benar.

**Kesalahan logika:** insert_child_roll memakai setdefault untuk parent_roll_id, sehingga nilai warisan dari dict(parent) tidak diganti. Direct parent dan root mempunyai aturan berbeda tetapi diperlakukan sama.

**Dampak bisnis:** Timeline pemotongan, tracing reject/recall, rekonstruksi panjang dan audit asal biaya dapat melewatkan generasi tengah. Ini tidak otomatis menggandakan kuantitas; jangan mencampurnya dengan race WM-01.

**Arah perbaikan:** Saat membuat physical child baru, set parent_roll_id=parent.id secara eksplisit dan root_roll_id=parent.root_roll_id atau parent.id. Simpan cut_event_id berisi input/output/loss. Untuk data lama, rekonstruksi hanya jika ada bukti; tandai lineage uncertain jika tidak cukup.

**Acceptance criteria:** Tiga generasi, beberapa sibling, split remnant dan return: direct parent benar, root tetap, tidak ada cycle, tiap cut mempertahankan qty+loss dan cost total. Perbaikan tidak mengubah historical data tanpa dry-run diff.

<a id="ax-08"></a>

## AX-08 — Verifikasi tag dianggap cukup untuk memindahkan roll QC hold

**Prioritas:** P1. **Hubungan audit:** Perluasan RF-02, RF-14, WM-04 dan WM-05; bukan dihitung lagi sebagai delapan bug berbeda.

**Letak kode:** [backend/services/putaway_order_service.py:73](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L73); [backend/services/rfid_ingest_service.py:47](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L47); [backend/services/rfid_print_service.py:31](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L31).

**Skenario dan bukti:** Roll quarantine tetapi journey tag_verified dapat masuk PA open (V2-09). Pada skenario terpisah, PA cancelled dengan journey putaway_in_transit memperoleh green OUT sebelum quarantine diperiksa (V2-02). Reprint/verify juga dapat menulis tag_verified pada roll yang sudah menjalani proses lain.

**Kesalahan logika:** Tag readiness, business document status, quality disposition, reservation dan physical location dicampurkan ke satu journey/status yang dapat ditulis oleh beberapa modul. Prasyarat berbeda-beda: PA memeriksa tag stage/category, gate cabang PA mengabaikan QC, location putaway justru memeriksa hold.

**Dampak bisnis:** Satu modul mengatakan barang ditahan sementara modul lain mengizinkan perjalanan. Mengubah satu daftar status belum menyelesaikan konflik karena sumber authorization tetap berbeda.

**Arah perbaikan:** Pisahkan state tag, QC, physical position, commitment, movement work dan posting. Semua movement authorization memanggil evaluator policy yang sama dengan precedence hold/block → owner/source/version → active document membership → destination. Izin memindahkan quarantine ke area QC harus movement type khusus, bukan blanket green outbound.

**Acceptance criteria:** Tag verified tidak dapat menghapus QC hold. Reprint tidak mengubah operational stage. PA cancelled/completed tidak memberi izin. QC relocation yang sah tetap boleh lewat command khusus dan reason, sementara shipment pelanggan diblokir.

## Flow 1 — PO sampai pemotongan, picking, loading, dispatch dan HPP

Ambil roll fisik 100 m, tag T, cost Rp10.000/m. Order membutuhkan 30 m. Sistem dapat membuat child 30 m saat reservasi sebelum potongan fisik dikonfirmasi; child tidak memiliki tag. Bila shipment hanya sebagian dari roll committed, helper pengiriman juga dapat membuat child baru pada saat dispatch. Dua jalur split ini berbeda dan tidak harus terjadi bersamaan; keduanya memperlihatkan bahwa identitas barang bisa berubah pada waktu yang tidak tepat bagi verifikasi fisik.

Loading saat ini mengambil roll SO yang memiliki tag aktif. Untagged bisa tidak masuk expected; hasil clean memberi kesan semua barang telah diperiksa. Dispatch kemudian memilih kembali roll berdasarkan qty, bahkan membuat child yang belum menjadi anggota bukti loading. Surat jalan menyimpan hasil pemilihan itu. Posting HPP menggunakan rata-rata roll order, bukan otomatis biaya roll yang tersimpan dalam shipment. Jadi memperbaiki loading agar untagged diblokir saja belum menjamin barang pick=barang ship=barang cost.

Flow yang diperlukan: demand 30 m → reservasi logical 30 m pada roll100 → work pemotongan → ukur hasil child30 dan remnant70/loss aktual → konfirmasi identitas/tag child → pick child dari bin valid → freeze shipment manifest → loading bukti physical child → release gate → commit shipment/movement dan kewajiban posting. Jika tidak ada pemotongan, roll utuh tetap satu physical identity. Meter berasal dari pengukuran/pencatatan WMS, tidak dari jumlah read RFID.

Invariant nominal: sebelum dan setelah cut, input100 = output30 + remnant70 + loss0; nilai Rp1.000.000 = Rp300.000 + Rp700.000 menurut specific-cost tanpa biaya tambahan. Jika memakai WAC, fixture biaya menggunakan policy WAC yang sama pada subledger dan GL. Policy biaya harus dipilih eksplisit sebelum mengubah rumus.

## Flow 2 — gudang transit menuju bangunan penyimpanan

Receiving/QC → print/verify → PA → OUT asal → perjalanan → IN tujuan → staging → scan bin → stored. Implementasi memiliki bagian-bagian tersebut, tetapi journey tag_verified dapat meloloskan quarantine, dispatch PA tidak selalu mengubah bucket ATP, dan arrival dapat menerima [] sebagai semua barang. Arrival normal langsung menandai stored meski bin belum dikonfirmasi.

Akibat gabungan: barang yang sudah dibawa masih berstatus dapat dialokasikan di asal; order lain bisa mengikatnya; arrival PA lalu menulis warehouse baru berdasarkan snapshot item lama. Claim PA hanya mencegah dua completion PA sama, bukan mencegah SO atau transfer lain mengubah roll tersebut. Kebijakan HOLD/QC dapat dilewati gate PA OUT.

Perbaikan harus menambah hak eksklusif movement atas roll dan state posisi yang jelas: receiving/quarantine, available-in-bin, allocated, picked, staged, in-transit, received-unlocated, stored. Ini contoh state domain, bukan usulan menambah satu enum campur-aduk. QC disposition dan ownership tetap dimensi tersendiri. IN tujuan memberi bukti tiba; scan bin memberi bukti lokasi akhir. Wrong-building read membuat incident tanpa memindahkan inventory ke bangunan salah.

## Flow 3 — transfer internal dan invoice biaya yang terlambat

PO1 menerima roll100 di W1/BIN1. Transfer ke W2 tidak mengubah owner atau acquisition origin. Freight 100 kemudian disetujui untuk PO1. Kode receipt transfer menimpa acquired menjadi TR, sehingga pemilihan landed-cost berbasis PO tidak menemukannya. Bila roll dipecah, sebagian child tetap berreferensi PO dan sebagian sudah TR; coverage costing menjadi parsial.

Jika parent70 dan child30 sama-sama masih dipilih, alokasi dan propagasi descendant dapat pula menghasilkan biaya tambahan dua kali pada child tergantung urutan. Ini bukan satu masalah yang selesai dengan unique voucher_id: perlu menentukan cost layer asal, kuantitas basis immutable, bagian masih on-hand, bagian sudah consumed/shipped, serta koreksi nilai yang dibukukan.

Pagar penerimaan: warehouse/bin harus satu struktur valid, acquisition origin tidak berubah, biaya total voucher dibagi tepat sekali, dan dampak stock/COGS sesuai status serta policy periode. Transfer intra tidak menciptakan laba atau mengubah total nilai entity tanpa biaya tambahan yang sah.

## Flow 4 — stock opname dan Finance

RFID hanya memastikan identitas tag teramati. Dua roll ditemukan tidak membuktikan keduanya masih 100 m. Count quantity perlu pengukuran/konfirmasi meter, unit yang konsisten, scope bin/owner, cutoff dan aturan movement selama count. Selisih stok tidak boleh diselesaikan dengan mengurangi roll lain secara arbitrer sampai jumlah aggregate cocok.

Pada kode sekarang, count bin dapat mengambil expected seluruh warehouse, shortage bisa diterapkan parsial tetapi sesi disetujui, dan jurnal variance belum mengikuti adjustment. Koreksi audit awal: surplus memang bisa mengambil harga_pokok produk, jadi tidak selalu bernilai nol. Harga fallback itu tetap perlu dievaluasi kebijakannya dan bukan pengganti jurnal.

Target: count task immutable snapshot atau movement-aware cutoff → blind count sesuai kebutuhan → discrepancy per roll/bin/owner → recount/approval terpisah → adjustment atomik yang menyebut roll tepat → valuation → posting variance → rekonsiliasi. Jika target shortage tidak dapat dipenuhi, hasil harus blocked/partial-visible, tidak approved seolah lengkap.

## Flow 5 — uang diterima, subledger, bank dan tutup buku

Pembayaran AR, kas manual, opening bank, aset dan stock adjustment mempunyai jalur persistence berbeda. Sebagian GL dipanggil best-effort, sebagian tidak langsung; void dan perubahan master tidak selalu menghasilkan reversal. Chart of accounts juga di-resolve berbeda antara manual journal dan laporan. Menambahkan satu retry tidak cukup bila source identity dan account identity tetap berbeda.

Rancang posting contract per domain: source operation → amount/unit/currency/tax basis → effective account IDs → period → expected debit/credit → posting state. Simpan kewajiban posting secara durable dengan source commit. Dashboard finance harus menampilkan pending/failed posting dan rekonsiliasi, bukan hanya saldo yang sudah posted. Closing tidak boleh dilanjutkan jika ada residual material yang tidak dijelaskan. Ini rekomendasi kontrol; batas materialitas dan metode biaya memerlukan policy bisnis yang terdokumentasi.

## Flow 6 — shared warehouse, multi-owner dan scope dokumen

Gudang bersama tidak membuat seluruh stok menjadi milik entity aktif. Pagar harus memeriksa empat hal terpisah: user boleh operasi entity, entity boleh menggunakan warehouse, roll dimiliki entity yang dimaksud, dan dokumen memang mengizinkan movement barang tersebut. Transfer explicit-ID melupakan pemeriksaan ketiga; print job multi-owner menyederhanakan anggota menjadi owner pertama; count dan rekomendasi mempunyai scope berbeda.

Jangan mengandalkan frontend dropdown atau user role “admin”. Service yang mutasi roll harus menerima scope tervalidasi dan memeriksa semua anggota. Bulk operation harus gagal sebelum efek jika ada anggota ilegal, atau memiliki hasil parsial eksplisit yang tidak merusak atomicity bisnis.

## Rencana rekonsiliasi data sebelum migrasi

Jalankan read-only dry-run pada salinan data dengan cutoff. Laporkan per entity/warehouse: task shipped_qty versus sum shipments; shipment tanpa movement atau roll tidak cocok; roll transit tanpa dokumen aktif; PA stored tanpa bin; warehouse/bin beda struktur; tag active tidak cocok binding roll; child dengan parent/root tidak konsisten; multi-owner print jobs; roll transfer yang acquisition origin hilang; uplift landed-cost total versus voucher; inventory valuation versus GL; cash/AR/bank versus GL; operasi failed/pending yang sudah mempunyai sebagian efek.

Jangan menghapus dokumen untuk membuat angka cocok. Klasifikasikan setiap anomaly: bukti cukup untuk auto-repair, perlu approval accounting, atau perlu hitung ulang fisik. Simpan sebelum/sesudah, operation repair ID, dasar bukti, actor dan reversal path. Backfill yang menulis ulang semua saldo tanpa cutoff dapat menambah inkonsistensi pada operasi aktif.
