# IMPLEMENTATION

Commit sumber diuji: patch di atas `32b3d19` (memuat iterasi P08). SHA kandidat diisi setelah commit platform.
ID/fase: P09 — RF-02, RF-03, RF-16, UX-01 (+ fitur pendukung: status klaim printer di panel cetak, riwayat scan loading check).

Reproduksi HEAD: worktree `32b3d19` → `python ../audit/iterations/2026-10-08-P09-gate-contract/repro_p09.py` → [head_before_patch.txt](head_before_patch.txt) `pass=3 fail=19` (OUT hijau berbasis status, IN transit hijau di gudang mana pun, replay/tag diam menggandakan read & insiden, batch >500 dipotong, tidak ada passage/latched).

## Perubahan

- Satu evaluator `services/gate_evaluator.evaluate(direction, warehouse, roll)` dipakai ingest perangkat, simulator Gate Monitor (`gate_simulate` kini lewat `ingest`, source=simulated) dan kiosk. Keputusan dari MOVEMENT aktif yang memuat roll: PA (`in_transit`, anggota items), transfer gudang (`dispatched`, roll `in_transit_transfer`), surat jalan SO (shipment aktif memuat roll, SO tidak batal). Kode alasan: MOVEMENT_OUT/IN, NO_DOCUMENT, DOC_MISSING, NOT_RELEASED, NOT_IN_MANIFEST, WRONG_WAREHOUSE, WRONG_DESTINATION, MOVEMENT_NOT_ACTIVE, SO_CANCELLED, ALREADY_OUT, REPLAY_EXIT, QUARANTINE, SALES_TRANSIT_NOT_INBOUND, UNKNOWN_EPC. Daftar GREEN_OUT berbasis status dihapus.
- RF-02: OUT hijau hanya bila gudang gate = asal movement, roll tercantum, movement sudah di-dispatch; keluar hijau dicap `inventory_rolls.gate_exit` → keluar ulang untuk movement sama = REPLAY_EXIT.
- RF-03: IN hijau hanya di gudang tujuan movement aktif; transit tanpa dokumen = exception merah; transit penjualan tidak dianggap transfer internal.
- RF-16: kontrak `POST /api/rfid/ingest {events:[{epc,event_id,captured_at,antenna,rssi}], epcs?, batch_id?}`. Observasi mentah `rfid_observations` (_id = device:event_id → replay idempoten). Event bisnis `rfid_reads` satu per EPC per device dalam dwell 120 dtk (tag diam = `observation_count++`, tanpa insiden baru). Batas eksplisit 500 → 413 BATCH_TOO_LARGE (tidak ada yang diproses). Passage `rfid_passages` (jendela 10 dtk) dengan verdict red-dominant.
- UX-01: `GET /api/rfid/gate/{id}/status` (umur heartbeat, passage terakhir + read, latched, TTL 30 dtk); `POST /api/rfid/passages/{id}/acknowledge {note≥5}` (audit; read & insiden sumber tidak diubah). `GET /api/rfid/reads?read_type=gate&device_id=&before=` difilter di server + cursor. Komponen `GateLiveVerdict` (kiosk & panel live): MERAH terkunci sampai diakui, data >15 dtk / gagal ambil → "TIDAK TERHUBUNG — TAHAN", heartbeat >120 dtk → "GATE OFFLINE — TAHAN", hijau kedaluwarsa setelah TTL.
- Fitur: panel Cetak & Verifikasi menampilkan printer pemilik klaim + hitung mundur sisa klaim (`rfid-job-lease-<id>`, `rfid-job-detail-lease`); LoadingCheckPanel "Riwayat scan" (`lc-scan-history`, sumber/pelaku/perangkat/jumlah/waktu) untuk sesi terbuka & hasil terakhir (`last_scan_log`).

## Regression

- `repro_p09.py` → [after_patch.txt](after_patch.txt) `pass=22 fail=0`. Ulang `repro_p08.py` 43/43, `repro_p07.py` 18/18.

## Batas

- Arah gate masih dari konfigurasi device (belum ada sensor arah/confidence dari middleware); antenna/RSSI hanya disimpan.
- Surat jalan lama tanpa `rolls[].roll_id` → roll SO dianggap NOT_IN_MANIFEST (merah) — perlu dispatch ulang/eksepsi manual.
- Dead-letter untuk event rusak belum terpisah: EPC tak valid dicatat sebagai read merah UNKNOWN_EPC.
- Middleware perlu mengirim `event_id` agar retry idempoten; tanpa itu hanya dedup dwell yang berlaku.
