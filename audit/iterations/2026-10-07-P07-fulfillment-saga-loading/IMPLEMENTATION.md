# IMPLEMENTATION

Commit sumber diuji: patch di atas `d60a1f2` (memuat iterasi 2026-10-06). SHA kandidat diisi setelah commit platform.
ID/fase: P07 sisa — CX-12, GN-11, RF-04, RF-06.

Reproduksi HEAD: `git worktree add .head_wt HEAD && cp backend/.env .head_wt/backend/ && cp frontend/.env .head_wt/frontend/ && cd .head_wt/backend && python ../../audit/iterations/2026-10-07-P07-fulfillment-saga-loading/repro_p07b.py` → [head_before_patch.txt](head_before_patch.txt) `pass=9 fail=6`: CX-12 OD menjadi done walau D2 masih jalan / gagal; RF-04 gudang wajib tetap meloloskan dispatch tanpa check, tanpa override berizin; RF-06 roll baru atau panjang berubah sesudah check tetap lolos. Catatan: bagian GN-11 memanggil server berjalan (sudah terpatch) lewat HTTP — **bukan bukti HEAD**; bukti statis = `release_saga_lock` lama langsung `$unset` tanpa body/alasan/cek efek/fencing.

## Perubahan

- CX-12: `special_order_phase2.fulfillment_complete(so_id)` — OD `done` hanya bila SEMUA surat jalan SO (bukan cancelled/void) termasuk dalam pengiriman berstatus delivered/completed. Gagal kirim tanpa penjadwalan ulang = belum. `on_delivered` memakai kebijakan itu; dipanggil dari transisi delivered/completed DAN serah terima pickup (`pickup_handover`). Replay idempoten (transisi done→done ditolak & diabaikan).
- RF-04: field gudang `loading_check_policy` ("optional" bawaan | "required"), bisa diubah di Master Gudang (`wh-lc-policy-<id>`). `dispatch_guard(order, warehouse)` menolak dispatch tanpa check di gudang "required". `POST /api/outbound/so/{id}/loading-check/override {reason≥5}` (izin wms.approve) — tercatat audit dan terikat manifest. UI panel loading check: tombol Override + alasan, verifikasi label roll tanpa tag (RF-05).
- RF-06: hasil check (clean/override) menyimpan `manifest` = roll + panjang saat check. Guard dispatch menolak bila roll siap kirim sekarang bukan subset manifest (roll baru / panjang berubah) atau hasil lama tanpa manifest; roll yang sudah terkirim (partial dispatch) tidak membatalkan hasil.
- GN-11: klaim saga menyimpan `token` (fencing). `GET /api/saga-locks/{coll}/{id}/inspect` menampilkan efek hilir sesudah kunci diklaim (jurnal, mutasi stok, surat jalan, kas, roll) + status aktif. Release wajib alasan ≥10, ditolak bila kunci masih aktif (<5 menit & belum gagal), ditolak bila ada efek tanpa `acknowledge_effects`, dan CAS pada started_at+token (kunci baru tidak ikut terlepas). Audit mencatat efek, pengakuan dan alasan. Panel Kunci Saga memeriksa dulu lalu menampilkan efek sebelum meminta alasan.

## Regression

- `repro_p07b.py` → [after_patch.txt](after_patch.txt) `pass=16 fail=0`.
- Ulang: `repro_p07.py` 18/18. Guardrail `verify_atomic_claim.py` sama dengan HEAD (2 ✗ lama: inbound scan label CAS + 70 endpoint belum ditinjau — bukan dari patch ini).

## Batas

- CX-12: kelengkapan dihitung per surat jalan (bukan per qty diterima pelanggan / retur saat terima); pengganti pengiriman gagal = delivery baru yang memuat surat jalan sama.
- RF-04: bawaan semua gudang "optional" (perilaku lama); mengaktifkan "required" per gudang adalah keputusan operasional.
- RF-06: hasil check SO lama tanpa manifest kini harus diulang sebelum dispatch berikutnya.
- GN-11: belum ada operation ledger per tahap / resume otomatis; pemulihan tetap manual tetapi kini berbasis bukti efek dan fencing. Sumber efek dicocokkan lewat id/nomor dokumen induk — efek yang dirujuk dengan kunci lain tidak terdeteksi.
