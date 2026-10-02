# IMPLEMENTATION

Commit sumber diuji: patch di atas `b7b4184` (memuat iterasi P09). SHA kandidat diisi setelah commit platform.
ID/fase: P10 — FN-14, RF-17, WM-07, WM-08 (+ fitur pendukung: saran tindakan gate, peringatan klaim printer, riwayat passage gate).

Reproduksi HEAD: worktree `b7b4184` → `cd .head_wt/backend && python ../audit/iterations/2026-10-08-P10-opname-financial/repro_p10.py` → [head_before_patch.txt](head_before_patch.txt) `pass=0 fail=19` (expected dari balance gudang bukan bin, duplikat/negatif/NaN diterima, tidak ada jurnal selisih, surplus HPP kosong, picked tidak dipotong, approve palsu, roll WIP tidak bisa di-tag/dihitung).

## Kebijakan valuasi (DEFAULT — menunggu konfirmasi pemilik buku)

- Kekurangan: nilai = Σ(panjang dipotong × unit_cost roll yang dipotong) → **Dr 5-9500 Beban Kerugian/Penghapusan Persediaan / Cr 1-1300 Persediaan**.
- Kelebihan: roll baru dinilai WAC segmen (produk×gudang×pemilik → produk×pemilik → biaya standar produk) → **Dr 1-1300 / Cr 4-9000 Pendapatan Lain-lain**.
- Biaya acuan 0 → approve 409 kecuali `zero_cost_reason` diisi (tersimpan di baris & sesi; tanpa jurnal karena nilai 0).
- Jurnal idempoten per baris hitung (`source_type=cycle_count_variance`, `source_id=<sesi>:<baris>`), terhubung di `items[].adjustment.journal_id`.

## Perubahan

- `services/stock_count_service.py` — scope hitung, adjustment per baris, valuasi, feasibility. `apply_cycle_count_adjustment` lama (agregat, read→set, hanya sebagian bucket) dihapus; satu jalur.
- WM-07: expected = Σ roll fisik (`PHYSICAL_ROLL_STATUSES`) pada scope produk×pemilik×**bin** (snapshot `expected_snapshot_at`). Count key unik (409, juga lewat CAS `$elemMatch` saat push); campur level gudang + bin untuk produk sama → 409. `actual_qty` divalidasi ≥0 & finite (400; NaN tidak lagi lolos/500). Drift check approve memakai scope bin yang sama.
- WM-08: potong roll dengan CAS (`length_remaining` + `status` saat dibaca; balapan → baca ulang, maks 3 putaran), urutan available → hold/QC/blocked/damaged/wip → reserved/committed → picked/packed (semua bucket on_hand). Feasibility sebelum mutasi (409 + lepas kunci). Hasil per baris `items[].adjustment {requested, applied, unresolved, value, unit_cost, cost_basis, journal_id, status}` ditulis durable per baris; retry melewati baris yang sudah applied. Sisa tak terterapkan → status `approved_with_exceptions` + `exceptions[]` (bukan approved palsu). Reservasi yang tersentuh → notifikasi sales (seperti sebelumnya).
- FN-14: jurnal selisih per baris (lihat kebijakan). `gl_service.post_cycle_count_variance`.
- RF-17: cycle count RFID memakai `PHYSICAL_ROLL_STATUSES` (WIP/blocked/damaged ikut; transit keluar). Kandidat tag `rfid_service.PHYSICAL_STATUSES` diturunkan dari definisi yang sama + transit/receiving. Hasil memuat `eligible_count, tagged_count, untagged_count, tag_coverage_pct, read_recall_pct, extra_rate_pct, unresolved_count`; `accuracy_pct = ditemukan / (eligible + extra)`; untagged menjadikan hasil `with_issues`.
- UI: Stock Opname menampilkan per item diminta/diterapkan/belum terterapkan/nilai/HPP/jurnal (`cc-adj-<id>`), input alasan biaya nol (`cc-zero-cost-reason-input`), status "Disetujui — ada exception" (`cc-exceptions`). Panel RFID cycle count menampilkan metrik terpisah (`cc-metrics`).
- Fitur gate/printer: `gate_evaluator.ACTIONS` — saran tindakan satpam per kode (field `action` di read/hasil, tampil di kiosk `rfid-passage-action-<id>`, hasil simulasi `rfid-gate-result-action`, daftar aktivitas). `GET /api/rfid/passages?device_id|warehouse_id&before` + panel `GatePassageHistory` (`rfid-passage-history`, siapa/kapan mengakui + catatan). Panel cetak: klaim ≤60 dtk "HAMPIR HABIS" (`data-low=1`), `print_attempts > 2` → badge `rfid-job-retry-<id>`.

## Regression

- `repro_p10.py` → [after_patch.txt](after_patch.txt) `pass=21 fail=0`. Ulang `repro_p09.py` 22/22, `repro_p08.py` 43/43.

## Batas

- Kebijakan valuasi di atas adalah default teknis; akun/klasifikasi surplus perlu konfirmasi pemilik buku (policy, bukan bug).
- Blind count (menyembunyikan expected dari penghitung) & freeze gudang selama hitung belum diterapkan — keputusan operasional.
- Konkurensi paralel count vs reservasi dijaga CAS per roll; belum ada uji beban paralel.
- Shortage yang memotong roll picked/packed hanya memberi notifikasi ke sales — realokasi pesanan tetap manual.
