# IMPLEMENTATION

Commit sumber diuji: patch di atas `39c387b93ce476ab4bcb4cfcb864361e9fe4247c` (working tree; SHA kandidat diisi setelah commit platform).
ID/fase: WM-02 (verifikasi identitas roll anak lewat label), CX-05 (bayar Hutang Reimburse 2-1650), FN-02 (match per baris PO + serialisasi tagihan bersamaan), lencana Posting Gagal.

Reproduksi HEAD sebelum patch: `git worktree add .head_wt 39c387b && cd .head_wt/backend && python ../../audit/iterations/2026-10-04-label-reimburse-poline-badge/repro_followup2.py` → [head_before_patch.txt](head_before_patch.txt) `crashed=1` di `hutang_reimburse` (LPJ tidak mencatat hutang reimburse; tidak ada alur bayar). Catatan: 4 cek label pada run HEAD lolos karena memanggil server yang berjalan (sudah terpatch) lewat HTTP — bukan bukti HEAD.

Perubahan:
- WM-02: `roll_service.verify_cut_identity_by_label` + `POST /api/inventory/rolls/{id}/verify-identity {scanned_code}` (kode label = nomor roll, tidak peka huruf/spasi; salah → 400; sudah sah → 409; `cut.verified_via=label_scan`, journey `label_verified`). `GET /api/inventory/cut-children-unverified`. FE Antrean Potong: daftar "Roll anak menunggu verifikasi identitas" (`unverified-kid-<id>`, `label-scan-input-<id>`, `label-verify-btn-<id>`).
- CX-05: approve LPJ menyimpan `hutang_reimburse {amount, status open|none}`; `pay_reimburse` + `POST /api/cash-advance-settlements/{id}/pay-reimburse` (accounting.create): klaim saga, kas keluar `ref_type=reimburse_payable` (Dr 2-1650 / Cr Kas lewat `post_cash_durable`), resume kas yang sama bila GL gagal, status `paid`. FE detail LPJ: tombol `stl-pay-reimburse-btn`, label `stl-reimburse-paid`.
- FN-02: `VendorBillItemInput.po_line_code`; router memetakan tiap baris tagihan ke SATU baris PO (`line_code`), wajib pilih bila produk ada di >1 baris, tolak baris PO ganda; `evaluate_match` & `already_billed_map` memakai kunci baris PO (`line_key`); create + submit diklaim per PO (saga `purchase_orders`) sehingga tagihan bersamaan tidak membaca sisa yang sama.
- Lencana: `GET /api/finance/posting-failures/count`; Sidebar menampilkan badge di grup Keuangan (`nav-badge-keuangan`) dan item Posting Gagal (`nav-badge-posting-failures`), polling 60 dtk + refresh setelah ulang posting.

Regression test: `cd backend && python ../audit/iterations/2026-10-04-label-reimburse-poline-badge/repro_followup2.py` → [after_patch.txt](after_patch.txt) `pass=12 fail=0` (termasuk HTTP 2 tagihan 60 bersamaan + 1 berurutan atas diterima 100 → 200/400/400, Σ aktif 60). `repro_p04.py` cek statis FN-02 disesuaikan ke pesan baru → 7/7. Integritas PASS 248 · FAIL 0.
Batas pengujian: fixture 3-way memakai harga besar agar selisih melampaui toleransi rupiah (KN-D16); tagihan lama tanpa `po_line_code` dipetakan ke baris tunggal produknya (PO lama dengan produk ganda tetap per produk); approve (bukan submit) tidak diklaim ulang per PO; lencana hanya admin/manager.
ID: WM-02, CX-05, FN-02 in_progress (menunggu SHA).
