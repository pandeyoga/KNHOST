# Handoff sesi 2026-10-19C (lanjutan, sisa kerja independen)

Lingkungan dipulihkan: clone → rsync ke /app (.env dipertahankan), `scripts/restore_local_demo.sh`, `scripts/rebuild_frontend.sh`. Riwayat git lokal di-reset ke `origin/main` (push fast-forward biasa).

| Fase | Commit | Isi |
|---|---|---|
| 1 | dec97ee | LN-090 — SO pengganti retur wajib grade yang sama dengan saat dijual (`required_grade` di baris SO; alokasi FEFO & Ganti Roll hanya grade itu). Grade jual = `regraded_from` roll retur atau grade roll. Pesan faktor yard↔kg lebih lunak; KNSelect di logistik retur & grade QC. |
| 2 | 04efcff | LN-033 T08 — `POST /api/special-orders/{id}/fulfillment/{key}/cancel` {reason≥5}, izin `od_fulfillment.cancel`; membatalkan PO/MKO aktif lewat aturan modul asal; tombol di panel pemenuhan. |
| 3 | 0960a34 | LN-012-T04 — greige selalu tersembunyi dari Sales (tidak bisa dibuka lewat setting); bawaan `catalog.sales_hidden_stages` = [grey, yarn] → PFD/PFP boleh dijual. LN-102-T02 — kartu Meja Saya = isi daftar (diuji), tugas terima membuka Barang Masuk. |
| 4 | 701fe1e | Perbaikan hasil uji: batal dokumen OD mengarsip PO+PR (PR #retired) sehingga realisasi ulang jalur sama berhasil; batal SO pengganti → pemakaian saldo retur dibalik & retur boleh membuat pengganti baru (`replacement_history`). |

Uji: `test_ln090_replacement_order.py` 4/4, `test_l03_ln033_fulfillment.py` 9/9, `test_t1_ln033_cancel_edges.py` 2/2, `test_t1_phase123_extra.py` 9/9, `test_ln102_t02_desk_cards.py` 7/7, `test_p01_imp_12_13_14_15_20.py -k Imp12` lulus. Testing agent: `test_reports/iteration_ln090_ln033_ln012_ln102_1.json` (+ retest).

Status BACKLOG tidak diubah (DEFINITION_OF_DONE: butuh reviewer terpisah + owner).

Masih terbuka:
- Pemecahan fisik roll cutloss di stok & posting otomatis ongkir retur — butuh keputusan owner (akun GL ongkir; potongan cacat 15 yd masuk stok BS atau dibuang).
- `tests/test_p03_p04_e2e.py` TestKeepPending (sales 403) gagal sebelum sesi ini — perlu dicek apakah tes basi.
- Filter `?stage=` di `GET /api/products?paginate=true` tidak menyaring (temuan sampingan).
- Keputusan pending: DATA-01, DES-02..04, HW-01/02, HR-01, UAT-01. Duplikasi D1–D8 menunggu persetujuan.
