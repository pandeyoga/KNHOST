# IMPLEMENTATION

Commit sumber diuji: `1ea1dd8` (checkpoint; patch di atas `42c97b3` yang memuat iterasi 2026-10-05).
ID/fase: P07 sebagian — WM-06, AX-03, AX-01, RF-05, CX-11. Fitur kebijakan PG02 (FN-09 lanjutan): jurnal pembalik periode berjalan.
Tertunda (status tetap needs_revalidation): CX-12, GN-11, RF-04, RF-06.

Reproduksi HEAD: `git worktree add .head_wt HEAD && cp backend/.env .head_wt/backend/ && cp frontend/.env .head_wt/frontend/ && cd .head_wt/backend && python ../../audit/iterations/2026-10-06-P07-dispatch-identity-reversal/repro_p07.py` → [head_before_patch.txt](head_before_patch.txt) `pass=4 fail=6`: AX-01 mengirim roll OLD padahal NEW yang dipindai; AX-03 shipped_qty 30 vs Σ surat jalan 60; RF-05 sesi "clean" walau satu roll tanpa tag; CX-11/REV/scan_label belum ada (crash = fungsi belum ada). Catatan: bagian WM-06 memanggil server berjalan (sudah terpatch) lewat HTTP — **bukan bukti HEAD**; bukti statis WM-06 = `scan_pick_item` lama tidak memuat roll dan tidak menolak qty ≤ 0.

## Perubahan

- WM-06: `scan-pick` menolak qty NaN/inf/≤0; kode scan (id roll / no. roll / EPC tag aktif) di-resolve server dan wajib cocok produk, gudang, pemilik, `reserved_ref`=order task, status siap kirim, bin (bila dipindai), qty ≤ panjang roll. Scan tanpa kode roll tetap diizinkan (alur cepat HP & uji lama) — mewajibkan scan per roll adalah keputusan kebijakan gudang yang belum ada.
- AX-03: `dispatch_task` membaca ulang quantity/picked/shipped dari dokumen hasil klaim saga; qty melebihi sisa terbaru → 409 dan kunci dilepas.
- AX-01: `ship_order_rolls(roll_ids=…)` — dispatch hanya mengirim roll hasil scan pick yang belum terkirim (urut scan); kurang → 409. Entri scan dispatch menyimpan `rolls`. Task tanpa scan roll memakai pemilihan lama.
- RF-05: sesi loading check mencatat `untagged` (tanpa tag / tag nonaktif / tag_id menggantung); clean hanya bila missing, extra dan untagged-yang-belum-diverifikasi kosong. `POST /api/outbound/loading-check/{sid}/scan-label {code}` memverifikasi roll tanpa tag lewat label no. roll. Order tanpa roll bertag kini bisa di-check lewat label. Guard dispatch menyebut jumlah roll tanpa tag yang belum diverifikasi.
- CX-11: nilai credit note retur dihitung dari baris SO produk itu berurutan (FIFO), dikurangi qty yang sudah dikreditkan CN lain atas order yang sama; tidak lagi memakai harga baris terakhir.
- PG02 (jurnal pembalik): `gl_service.reverse_entry` + `POST /api/gl/journal/{id}/reverse {date, reason}` (izin accounting.void). Tanggal wajib periode terbuka (`can_backdate=False`, jendela unlock ditolak), ≥ tanggal jurnal asli, alasan ≥3 karakter; manual & otomatis; jurnal penutup/pembalik ditolak; CAS satu pembalik per jurnal (`reversed_by_entry_id`). Jurnal asli tetap posted; closing periode lama tidak menjadi stale. UI Buku Besar → detail jurnal: tombol **Balik Jurnal** (`gl-journal-reverse`, form `gl-reverse-date`/`gl-reverse-reason`/`gl-reverse-submit`), catatan tautan dua arah.

## Regression

- `repro_p07.py` → [after_patch.txt](after_patch.txt) `pass=18 fail=0`.
- Ulang: `repro_p05.py` 29/29, `repro_followup2.py` 12/12.
- `tests/test_iter292_f01_dispatch_gl.py` gagal karena data demo (so_006 sudah confirmed oleh run sebelumnya; entitas ent_kanda) — bukan karena patch; seed ulang dijalankan.

## Batas

- WM-06: undo pick (event koreksi terpisah) belum dibuat; qty negatif cukup ditolak.
- AX-01: bila roll yang dipindai dipecah sebagian sebelum dispatch, anak hasil pecah tidak otomatis ikut daftar scan.
- RF-05: pengecualian berizin (override tanpa scan) belum dibuat; jalur resminya scan label.
- CX-11: retur belum menunjuk baris SO eksplisit (FIFO per produk); diskon/pajak per baris memakai neto baris yang sudah ada.
- Pembalik: dokumen sumber jurnal otomatis tidak diberi tanda; backfill/autopost ulang dicegah karena jurnal asli tetap posted.
ID: WM-06, AX-03, AX-01, RF-05, CX-11 → ready_for_validation pada `1ea1dd8`. CX-12, GN-11, RF-04, RF-06 tertunda (needs_revalidation).
