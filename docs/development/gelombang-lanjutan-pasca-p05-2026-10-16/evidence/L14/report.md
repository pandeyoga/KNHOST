# Laporan L14 · LN-140 — Uji rantai bisnis Sukacita ← CST (2026-10-18, agent E1)

Status: `in_progress` (bukti teknis lulus; validasi owner/reviewer belum).

## Cara menjalankan
`cd /app && python backend/test_core_rantai_retur_poc.py` (HTTP nyata, data uji sendiri `FASEE9POC`, nol residu).
Entitas/gudang/supplier bisa dialihkan: `POC_ENT_B`, `POC_WH_B`, `POC_SUP_B`.

## Rantai yang dibuktikan (46/46 PASS)
1. CST PO ke supplier luar grup (PT Kain Jadi Nusantara) → penerimaan dengan **SJ supplier** & **lot supplier 234** → inspeksi 4-point per roll → keputusan QC.
2. Pesanan Sukacita (stok kosong, backorder) → beli internal CST → tugas gudang di gudang bersama → pesanan terpenuhi otomatis + notifikasi.
3. **Pengiriman**: submit → ACC → verifikasi → konfirmasi → reservasi potong dikonfirmasi (roll anak + verifikasi label) → scan-pick per roll → final loading check (override beralasan) → dispatch (Surat Jalan) → terkirim.
4. Retur pelanggan → inspeksi grade B → karantina → nota kredit → release.
5. Retur antar-PT KSC→CST (roll hasil retur, bukan FEFO; jalur at-cost ditolak) → saldo antar-PT turun tepat.
6. CST retur ke supplier asli (jejak supplier/PO utuh) → Jejak Retur satu layar dari tiga titik masuk.

## Temuan & perbaikan
| # | Temuan | Perbaikan |
|---|---|---|
| T1 | Supplier grup (`entity_id="all"`) tidak muncul di `/api/suppliers` & ditolak detailnya untuk setiap PT → PO CST ke supplier luar buntu | `suppliers` masuk `INHERITED_GLOBAL_VALUES`; daftar memakai `resolve_list_scope_inherit`; akses detail mengizinkan baris global |
| T2 | Gudang retur pelanggan dicari dengan `type="outbound"` (field sebenarnya `flow_type`) → retur selalu jatuh ke gudang PERTAMA grup (Jakarta·Sukacita), lalu retur antar-PT terblokir aturan gudang | `_resolve_return_warehouse`: `flow_type` → alokasi SO → gudang default entitas |
| T3 | `patch_lot` (LN-014) menolak "tanpa perubahan" → inspeksi roll dengan lot supplier yang sama gagal 400 | No-op mengembalikan lot apa adanya |
| T4 | SJ supplier hanya tersimpan di tugas GR, tidak di lot/roll/label | `supplier_dn_number` di roll & `supplier_dn_numbers` di lot saat GR + backfill boot; tampil di detail lot & label "SJ sup." |
| T5 | POC lama basi (sandi akun demo, Toba Craft/wh_tangerang hilang, sumber restock P05 wajib, rencana QC "cek semua", tanpa langkah kirim) | POC diperbarui mengikuti aturan bisnis yang berlaku (bukan melonggarkan aturan) |

Catatan desain (bukan bug): gudang khusus (dedicated) PT tidak boleh menampung barang PT lain; perpindahan antar-PT tanpa pindah fisik hanya sah di gudang bersama, selain itu butuh pengecualian supervisor beralasan.

Tes regresi: `tests/test_ln140_chain_fixes.py` (3), `tests/test_ln014_lot_identity.py`, `tests/test_ln091t02_ln093_chain.py`.
