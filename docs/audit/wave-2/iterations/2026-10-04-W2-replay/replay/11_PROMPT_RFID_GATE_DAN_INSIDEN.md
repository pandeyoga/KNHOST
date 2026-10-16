# Prompt implementasi berurutan — W2-010–012

Gunakan [laporan W2-05](10_TEMUAN_RFID_GATE_DAN_INSIDEN.md), [bukti runtime](rfid-results.json), dan [harness](repro/wave2_rfid.py). Kerjakan dari kode terkini karena Gelombang 1 sedang diperbaiki paralel; jangan me-reset atau menimpa perubahan RF-02/03/13/16, RF-08, GN-01–04 dan P01/P09. Bukti historis mengacu commit `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`; jangan ubah hasil lama. Untuk tiap item, tulis commit implementasi, bukti tes pada commit tersebut, dan ubah status tracker dari `open` menjadi `ready_for_validation`. Validator independen kemudian memutus `verified_fixed` atau membuka ulang. Jangan menandai fixed dari review kode saja.

**Koreksi validasi:** baca [review W2-05](12_VALIDASI_ULANG_W2_05.md) dahulu. W2-010 dipersempit ke histori reads; incidents/device infra memang SHARED. W2-011 menjadi P2. Jangan menerapkan instruksi versi awal yang secara otomatis memblokir semua aksi insiden lintas owner.

## Fase R1 — W2-010 (P1), isolasi histori pembacaan RFID

Reproduksi dengan user A-only, roll/tag B yang dibuat service asli, gudang shared dan gudang dedicated B (`sharing_mode=dedicated, entity_ids=[B]`). API tags mengembalikan nol tag B, header B ditolak403, tetapi `GET /rfid/reads?warehouse_id=...` mengembalikan EPC/roll/owner B. Registry `entity_scope.py:38` menetapkan reads memakai `owner_entity_id`. Terapkan scope server pada route dan service `list_reads`; filter warehouse/device/result/read_type dari caller hanya boleh mempersempit hasil di dalam scope sah. Uji query kosong, filter asing, mode entitas aktif/gabungan, dan akses admin yang sah. Uji unknown EPC dengan kebijakan eksplisit karena owner null tidak sama dengan semua entitas.

Jangan memperluas patch ini dengan mengganti registry `rfid_incidents: SHARED` atau melarang semua device lintas owner. Insiden dan infra bersama punya kontrak berbeda dari raw reads. Catat keputusan terpisah bila bisnis ingin membatasi operator keamanan per gudang/entitas, termasuk operator pusat dan gudang dedicated; perubahan tersebut membutuhkan kontrak produk yang eksplisit. Label scope UI laporan harus menjelaskan apakah panel bersifat pusat atau mengikuti filter. Selesaikan defect reads yang terkonfirmasi terlebih dahulu, catat commit/bukti, lalu `ready_for_validation` W2-010.

## Fase R2 — W2-011 (P2), transisi insiden atomik

Reproduksi W2-R-F08: ack membaca `open`; resolve menyelesaikan; ack tertunda menulis `acknowledged` dan menimpa status terminal. Ubah transition menjadi compare-and-set pada status/versi yang dibaca. `resolved` terminal sampai ada operasi reopen tersendiri yang beralasan dan teraudit. Update yang tidak match harus mengembalikan konflik, bukan sukses palsu. Notes, `ack_by/at`, `resolved_by/at`, audit log dan response API harus cocok dengan state final. Hindari kondisi `status=acknowledged` sekaligus `resolved_at` terisi karena race.

Uji open→ack→resolve serial; ack ganda; resolve ganda; dua aksi serentak dari operator berbeda; interleaving ack-read/resolve-write/ack-write; retry HTTP. Otorisasi incident mengikuti kebijakan keamanan yang berlaku, bukan otomatis scope raw reads dari Fase R1. Asersi state final, jumlah audit event sukses, notes, dan tampilan pill UI. Catat commit/bukti dan tandai `ready_for_validation` W2-011.

## Fase R3 — W2-012 (P2), identitas alarm dan dedupe atomik

Reproduksi W2-R-F09 dengan dua `create_from_read` EPC+device yang sama serentak; keduanya `find_one` kosong dan membuat dua open incident. Susun kontrak kunci alarm: satu passage atau jendela waktu aktif yang sama menghasilkan satu incident dengan hits sesuai jumlah read yang ingin dihitung; setelah resolve, passage baru dapat membuat incident baru sesuai kebijakan. Terapkan claim/upsert atomik dan constraint yang menopang kunci tersebut. Hindari dedupe hanya pada cache proses atau transaksi dua langkah tanpa unique guard karena worker lain akan tetap berlomba. Ciptakan notifikasi hanya untuk insert incident baru; aksi ack/resolve pada incident yang sama tidak boleh menciptakan duplikat tersembunyi.

Uji dua dan puluhan ingest bersamaan, beberapa worker/proses bila harness mendukung, EPC sama pada device berbeda, jendela waktu bergeser, resolve lalu passage baru, retry request, dan kegagalan di tengah notifikasi. Pastikan satu insiden aktif per kunci, hits/last_at dan jumlah notifikasi benar. Koordinasikan kunci passage/event dengan RF-16 Gelombang 1; selesaikan W2-012 tersendiri karena race check-then-insert tetap ada meski format event baru ditambahkan. Catat commit/bukti dan tandai `ready_for_validation` W2-012.

## Urutan verifikasi lintas fase

Jalankan ulang kontrol W2-R-C01–C10 serta reproduksi W2-R-E01–E05. Pada kode yang sudah diperbaiki, ubah assertion lama yang memang mengharapkan bug menjadi expected behavior baru dan simpan hasil di direktori iterasi baru. Validasi RF-02/03/13/16 memakai tracker Gelombang 1 secara terpisah; statusnya tidak ikut selesai hanya karena W2-010–012 lulus. Setelah API/lifecycle aman, lakukan browser UAT pada panel alarm dan gate kiosk serta uji middleware/perangkat di lingkungan staging sebelum menyatakan gate layak produksi.
