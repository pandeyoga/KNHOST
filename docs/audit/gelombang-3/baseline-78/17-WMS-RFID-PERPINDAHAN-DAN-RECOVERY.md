# Pengujian lanjutan WMS/RFID: klaim roll, perpindahan, identitas dan recovery

Tujuh temuan tambahan pada source `a904d989b622f7da14c4892d03cf6ef0c43f3084` memperluas pemeriksaan dari angka stok ke hubungan antarproses yang memakai roll yang sama. Empat berprioritas P1 dan tiga P2. Laporan rinci, potongan kode, prompt perbaikan dan acceptance masing-masing tetap tersedia pada dokumen 02 dan tracker; bab ini menjelaskan akibat pada rantai bisnis.

Pengujian memakai original public API untuk print job, pengakuan cetak manual, verifikasi EPC, routing, Putaway Order, pembuatan SO, device ingest, cycle count dan recovery admin. Roll dibuat oleh original inbound writer. Master produk, pelanggan, gudang, aktor dan sesi login adalah fixture sintetis yang sah. Startup indexes asli dipasang: 212 performance dan 25 unique, tanpa kegagalan.

**Batas bukti:** input scan dan pengakuan cetak dibuat sebagai input operator manual pada database localhost. Ini bukan pengujian RFID reader/printer/gate fisik. SO producer dan dokumen alokasinya benar-benar dieksekusi; seluruh approval/picking/cutting/loading/shipping berikutnya belum disertifikasi. Consumer UI ditelusuri dari source, tanpa DOM karena hambatan lingkungan browser yang dijelaskan pada dokumen 13. Clock kunci saga di-aging secara eksplisit untuk menguji recovery tanpa menunggu batas waktu; efek/retry/release memakai fitur asli.

Terdapat **49 observasi: 26 perbedaan state/angka dan 23 kontrol lulus**. Ini bukan 49 bug. Setiap perbedaan dikelompokkan ke akar masalah pada tujuh ID; harness errors 0 dan koneksi eksternal 0.

| Temuan | Seharusnya | Teramati melalui producer/API asli | Dampak dan batas |
|---|---|---|---|
| PA-01: klaim PA lalu SO | Tidak ada klaim yang konflik; perpindahan/reservasi terkoordinasi | SO qty dan explicit-roll menerima 10/6 pada roll yang diklaim PA | Status available saja tidak mencerminkan siapa yang memakai roll |
| PA-01: reservasi parsial 6 pada roll 10 | PA berhenti atau melakukan rebinding alokasi/task yang sah | Dispatch/arrival berhasil; roll tujuan, SO allocation tetap gudang asal | Source pemenuhan dokumen tertinggal dari SSOT roll; fulfillment berikutnya belum diuji penuh |
| PA-02: fault setelah lokasi roll berubah | Recovery melengkapi tag/mutasi/saldo/parent | Roll tujuan, tag asal, mutasi 0, saldo asal 10/tujuan 0; retry/accept tetap exception | Inspector efek kosong; release lock tidak menyelesaikan operasi |
| PA-03: 10 meter + 10 yard |19.144 meter atau breakdown per unit | Saran dan total PA 20 meter | Per-item benar, total/label salah; dua desimal 19.14 boleh bila policy jelas |
| WMS-04: roll sudah reserved | Ready 0 atau queue dengan blocked 1 yang jelas | Suggest 0/create 400, health ready 1 | Dua layar memberi arti kesiapan berbeda untuk stock yang sama |
| RFID-01: observation durable/read gagal | Event yang sama melanjutkan langkah tersisa | Replay count 0/read 0; event baru REPLAY_EXIT | Tidak ada green read awal untuk merekonsiliasi exit stamp |
| RFID-01: red read durable/incident gagal | Recovery membentuk incident dan red passage/latch | Red read 1, incident 0, passage info/latched=False | Salah state pada gate-status API; bukan klaim kondisi lampu fisik |
| CC-01: result durable/parent gagal | Satu result/nomor per session/revision | Admin release+retry menciptakan dua laporan/nomor untuk session sama | Histori count terduplikasi; stock memang tidak diubah oleh laporan |
| TAG-01: retire atau EPC baru pending | Bukti identitas lama tidak mengesahkan current tag | PA menerima current tag=None atau pending_print | Empty/new EPC dapat masuk manifest tanpa verifikasi current identity |

## Kontrol normal dan alur yang sudah bekerja

```text
Original inbound roll10 + lot
  → public create RFID print job: pending_print
  → operator mark-printed: tag active
  → start verify → manual scan EPC → complete: clean/tag_verified
  → routing SIMPAN
  → PA create: klaim active_movement
  → PA dispatch: in_transit_transfer
  → confirm-arrival dengan EPC
  → PA completed dan BTG
  → roll/tag gudang tujuan
  → dua mutasi dan rebuild asal0/tujuan10
```

Alur tersebut lulus sebagai kontrol. Normal device ingest keluar dengan PA aktif juga memberikan MOVEMENT_OUT dan tepat satu read; replay event ID yang sudah lengkap menjadi duplicate tanpa read kedua. Normal count menghasilkan accuracy 100/satu laporan; complete ulang ditolak 400. Original SO mode pilih roll mengisi qty reservasi sesuai 10 atau 6, bukan salah kuantitas. Temuan menguji konflik/recovery/identitas/label di luar kontrol itu.

## Hubungan putaway dengan reservasi penjualan

PA open membiarkan roll available sambil menulis active_movement. SO qty memakai _available_rolls_for_order dan CAS reservasi; SO explicit roll memakai reserve_roll_mode_item/reserve_specific_rolls. Kedua jalur menerima roll itu. Artinya klaim pada satu modul belum menjadi kontrak yang dihormati modul lain.

```text
PA open: roll10 available + active_movement PA
  → SO qty6 / pilih roll exact_cut6
  → parent tetap available, length_reserved6
  → persisted SO allocation: warehouse ASAL, pending_cut
  → PA dispatch hanya memeriksa status + movement + asal
  → PA arrival: parent dipindah ke TUJUAN
  → persisted SO allocation masih ASAL
```

Ini request berurutan biasa, tanpa fault atau race buatan. Reservasi utuh 10 mengubah status reserved, sehingga dispatch 409; guard ini benar tetapi operator menghadapi konflik yang seharusnya dikoordinasikan lebih awal. Reservasi parsial menjaga status available, sehingga dispatch masih 200. Memperbaiki hanya guard dispatch belum menghilangkan offer/claim konflik di sales; memperbaiki hanya daftar candidate juga belum melindungi CAS saat race.

Kebijakan bisnis dapat memilih menunda SO sampai PA selesai, atau membolehkan reservasi sambil mengatur ulang source/task secara eksplisit. Pilihan kedua membutuhkan koordinasi dan audit trail, bukan sekadar menyaring active_movement. Prompt tidak memaksakan bahwa semua perpindahan dengan reservasi selamanya dilarang.

## Recovery perpindahan tidak selesai dengan melepas kunci

Fault ditempatkan sesudah update roll asli sudah tersimpan dan sebelum update tag. _land_items sudah menghapus active_movement dan mengubah warehouse. Parent PA masih in_transit, tag/balance belum mengikuti. Guard kunci langsung menolak retry 409 adalah kontrol yang benar.

Inspector kemudian tidak menemukan efek, karena memeriksa sumber inventory_rolls berdasarkan source_ref/created_at, bukan transition pada existing roll. Setelah release yang sah, confirm retry gagal mengadopsi roll tujuan: syarat CAS masih asal+active_movement. Accept exception memakai jalur yang sama, sehingga mengulang ketidakcocokan tersebut. Hasil final tetap completed_with_exception, tanpa dua mutasi, BTG yang benar atau saldo tujuan.

Perbaikannya memerlukan operation/checkpoint yang menjelaskan roll mana sudah berpindah, dari/ke mana, atas dokumen/version apa, dan langkah mana belum lengkap. Rebuild balance adalah proyeksi dari roll, bukan pengganti penyelesaian manifest, tag dan audit trail. Rebuild manual saja tidak menutup temuan.

## Identitas fisik dan bukti verifikasi harus merujuk tag saat ini

Client menetapkan semua roll harus bertag, termasuk stock dan transit untuk SO. Pengujian TAG-01 tidak memakai barang tanpa tag secara arbitrer: roll awal sudah melalui print/verify asli, lalu public retire membuat tag=None. Journey lama tetap tag_verified. PA memakai stage itu sebagai izin dan menerima EPC kosong.

Pada skenario penggantian, print job baru membuat pending_print; tag tersebut belum diakui tercetak dan belum discan, tetapi PA tetap diterima memakai stage verifikasi lama. Stage perjalanan fisik dan identity readiness perlu dipisahkan agar retag tidak mengubah lokasi/transit dengan keliru. Bukti harus menunjuk current tag ID/EPC/version yang sesuai roll; active tag saja belum membuktikan EPC baru sudah diverifikasi.

## Ketahanan ingest: observation bukan bukti seluruh proses sudah selesai

Pipeline menyimpan raw observation, menentukan keputusan, menulis exit stamp/read, membentuk incident merah, kemudian mengagregasi passage dan latch. Event ID hanya menjaga insert observation. Jika read atau incident gagal, event yang sama dianggap duplicate sehingga tidak melanjutkan efek. EPC baru dalam dwell mengambil cached read dan juga melewati efek insiden/passage yang belum selesai.

```text
GREEN: observation + exit stamp durable
  → read insert gagal
  → event sama: duplicate / no decision
  → event baru: REPLAY_EXIT, bukan recovery original green

RED: observation + red read durable
  → incident creation gagal
  → event sama: duplicate
  → event baru dalam dwell: cached red, tanpa incident/passage posting
  → gate-status passage info, latchedFalse
```

Tidak ada stock mutation oleh ingest; kontrol ini lulus dan harus dipertahankan. Temuan baru adalah ketahanan checkpoint event/decision/incident. V3-RFID-01 yang lebih dahulu dicatat membahas keputusan cache yang menjadi basi saat movement berubah; kedua akar masalah berhubungan tetapi tidak disamakan.

## Metric dan duplikasi yang melanjutkan dampak ke UI

Saran putaway dan PA menyimpan qty per roll yang benar. Namun grain group hanya owner/kategori/grade, sehingga base units dua SKU berbeda dijumlahkan mentah. UI memberi satu label unit pertama. Jangan menyelesaikan dengan mengubah label produk atau memaksa semua data unit sama; tampilkan per-unit breakdown atau konversi sah.

Warehouse Health menghitung old tag_verified pada roll yang sudah direservasi oleh SO, sementara actual suggestion/creation menolaknya. Jika pelanggan membutuhkan antrean fisik termasuk blocked, kontrak harus membedakan pending/ready/blocked dan alasan, bukan menyebut semua ready. Resolver eligibility bersama tetap perlu CAS pada saat aksi.

RFID cycle count memang laporan saja. Lost acknowledgment setelah result insert membuat parent masih open/locked; release dan retry membuat nomor/result baru. Satu scan session bisa tampil sebagai dua kegiatan opname. Unique session+revision serta adoption existing result menjaga recount yang disengaja tetap terpisah dari retry akibat gangguan.

## Kode, bukti dan fase perbaikan

- [D4-PA-01 — backend/services/roll_service.py:792](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L792); terkait: [backend/services/putaway_order_service.py:152](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L152), [backend/services/putaway_order_service.py:200](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L200), [backend/services/roll_service.py:736](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L736), [backend/services/roll_service.py:549](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L549), [backend/routers/sales_orders.py:421](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/sales_orders.py#L421), [backend/services/sales_order_helpers.py:123](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/sales_order_helpers.py#L123)
- [D4-PA-02 — backend/services/putaway_order_service.py:232](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L232); terkait: [backend/services/putaway_order_service.py:280](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L280), [backend/services/putaway_order_service.py:329](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L329), [backend/services/roll_service.py:233](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L233), [backend/routers/saga_locks.py:42](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L42), [backend/routers/putaway_orders.py:74](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/putaway_orders.py#L74)
- [D4-PA-03 — backend/services/putaway_order_service.py:49](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L49); terkait: [backend/services/putaway_order_service.py:166](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L166), [frontend/src/features/wms/PutawayOrdersPanel.jsx:104](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/PutawayOrdersPanel.jsx#L104), [frontend/src/features/wms/PutawayOrdersPanel.jsx:144](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/PutawayOrdersPanel.jsx#L144), [backend/services/roll_service.py:1890](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L1890)
- [D4-WMS-04 — backend/services/wms_health_service.py:42](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/wms_health_service.py#L42); terkait: [backend/services/putaway_order_service.py:19](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L19), [backend/services/putaway_order_service.py:113](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L113), [frontend/src/features/wms/WmsHealthDashboard.jsx:16](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/wms/WmsHealthDashboard.jsx#L16)
- [D4-RFID-01 — backend/services/rfid_ingest_service.py:138](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L138); terkait: [backend/services/rfid_ingest_service.py:190](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L190), [backend/services/rfid_ingest_service.py:194](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L194), [backend/services/rfid_ingest_service.py:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L151), [backend/services/rfid_ingest_service.py:214](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L214), [backend/services/gate_evaluator.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gate_evaluator.py#L129), [backend/routers/rfid.py:551](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfid.py#L551)
- [D4-CC-01 — backend/services/cycle_count_service.py:124](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L124); terkait: [backend/services/cycle_count_service.py:129](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L129), [backend/routers/saga_locks.py:33](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/saga_locks.py#L33), [backend/routers/rfid.py:650](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/rfid.py#L650)
- [D4-TAG-01 — backend/services/putaway_order_service.py:132](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L132); terkait: [backend/services/rfid_service.py:151](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_service.py#L151), [backend/services/rfid_print_service.py:130](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_print_service.py#L130), [backend/services/rfid_print_service.py:327](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_print_service.py#L327), [backend/services/putaway_order_service.py:108](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L108)

FASE-01 menangani PA-02, RFID-01 dan CC-01 karena ketahanan posting/recovery harus stabil sebelum projection diperbaiki. FASE-02 menangani PA-01, PA-03 dan TAG-01 sebagai kontrak roll/perpindahan/identity/unit. WMS-04 berada pada FASE-04; bergantung pada kebijakan dan resolver eligibility yang disepakati di FASE-02.

Bukti: [skrip original-chain](latest/repro/wms_movement_probes.py), [expected/actual dan persisted context](latest/repro/wms-movement-results.json), serta [log eksekusi](latest/evidence/wms-movement-probes.log). Setiap source permalink menuju SHA yang diperiksa. Agent tidak boleh menutup temuan hanya karena endpoint 200, lock berhasil dilepas atau stok pada satu layar terlihat benar.

Bab ini tidak menyatakan coverage 100%. Gate/printer fisik, offline middleware, seluruh state multiwarehouse dan seluruh kombinasi source/role/error tetap memerlukan pengujian sebagaimana register dokumen 13.
