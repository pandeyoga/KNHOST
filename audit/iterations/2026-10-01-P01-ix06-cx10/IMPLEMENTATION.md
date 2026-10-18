# IMPLEMENTATION

Commit sumber diuji: patch di atas `0076f7ea16ddc93d5b01f480768418464c5c3347` (working tree; SHA kandidat diisi setelah commit platform). Diff gabungan sesi: [../2026-10-01-P02-core-roll/session2_combined.diff](../2026-10-01-P02-core-roll/session2_combined.diff).
ID/fase: IX-06, CX-10 — P01 (sisa).

Reproduksi HEAD sebelum patch:
- IX-06 `repro_ix06.py` (HTTPS preview, role sintetis hr.view+hr.manage_payroll, user hanya A) → [head_before_patch_ix06.txt](head_before_patch_ix06.txt) `pass=4 fail=7`. PUT `/hr/payroll/settings` dari A mengubah B 1.5→2.75; A-only menulis global (200) dan lapisan entitas B via `PUT /config/values` (200); nilai invalid/leaf tak dikenal diterima 200.
- CX-10 `repro_cx10.py` (fungsi asli, SO klon sintetis) → [head_before_patch_cx10.txt](head_before_patch_cx10.txt) `pass=1 fail=9`: PDF isi baru tetap membawa tanda tangan lama, kode verifikasi dipakai ulang untuk versi baru, penanda tangan versi berbeda tercampur dalam satu kode.

Perubahan dan kontrak lintas caller:
- IX-06 `PUT /hr/payroll/settings`: body `scope` = `entity` (default, badan usaha aktif) | `global` (hanya peran lintas-PT); ditulis lewat `config_resolver.set_value` per kunci registry `hr.*`; semua leaf divalidasi (`registry.coerce`) sebelum satu pun ditulis; leaf tak dikenal → 400; respons = GET (setelan efektif entitas aktif) + `saved_scope`.
- IX-06/IX-07 `routers/config.py` (`/config/values`, `/values/reset`, `/values/clear`): lapisan `entity` wajib dalam penugasan (`resolve_requested_entity`); lapisan `global` untuk setting yang punya lapisan entitas hanya peran lintas-PT. `GET /config/registry` → `caps.global_write`.
- UI Pusat Pengaturan: opsi "Global" dinonaktifkan ("khusus peran lintas PT") bila `caps.global_write=false`; default otomatis ke badan usaha aktif.
- CX-10: hash versi = SHA-256 isi kanonik output resolver (tanpa stempel "Dicetak", refs, esign, field `_*`) — `pdf_service.canonical_content/content_hash`, `hash_version=2`. Signature menyimpan `doc_snapshot` (isi yang ditandatangani) + `hash_version`. Kode verifikasi hanya dipakai ulang untuk hash yang sama. `_attach_esign` hanya menempel tanda tangan dengan hash sama; bila ada tanda tangan lama → `esign_superseded` + teks "BELUM DITANDATANGANI (versi baru)" di PDF. `public_verify` → `version_status` current/superseded/legacy_unbound; halaman verifikasi menampilkan status versi. Surat Jalan: tanggal = `dispatched_at` (dulu tanggal cetak → hash berubah tiap hari).

Regression test: IX-06 11/11 [after_patch_ix06.txt](after_patch_ix06.txt); CX-10 10/10 [after_patch_cx10.txt](after_patch_cx10.txt) termasuk stabilitas hash lintas cetak.
Kontrol yang dipertahankan: A-only tetap bisa menulis lapisan A; admin global memengaruhi entitas pewaris, override A tetap; tanda tangan versi sama tetap tampil.
Data historis/migration dry-run: DB sintetis 0 signature. Produksi: signature lama (tanpa `hash_version`) = `legacy_unbound` → TIDAK lagi ditempel ke PDF baru dan halaman verifikasi menyatakan versi tidak dapat dipastikan (keputusan pemilik: minta tanda tangan ulang bila perlu). Konfigurasi `system_settings{scope:hr}` lama tetap dibaca sebagai lapisan global.
Batas pengujian: hash atas isi resolver, bukan byte PDF; tidak ada tanda tangan kriptografis/legal. Lapisan customer/supplier/product/document di `/config/values` belum dibatasi entitas (di luar IX-06).
ID siap divalidasi / tertunda: IX-06, CX-10 siap divalidasi setelah SHA tercatat.
