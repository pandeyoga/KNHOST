# UAT — P14 (browser)

- Lingkungan: preview `knhost-audit-1` (DB sintetis `test_database`, seed `seed_realistic.py`), bundle statis hasil `scripts/rebuild_frontend.sh`.
- Basis kode: `8fcb9dc9588cf14d9eeb534be38168a1c50f23d3` + patch P14 (belum di-commit saat uji).
- Pelaksana: agen uji otomatis (Playwright) — laporan `test_reports/iteration_122.json` di root repo. **Bukan UAT pengguna bisnis**; UAT manusia tetap diperlukan untuk sign-off.

| Kasus | Hasil | Bukti singkat |
|---|---|---|
| AUDIT-01 | PASS | Bagan Akun → `coa-detail-<kode>` → tab Riwayat Perubahan; ubah nama → baris "Diubah", nilai lama dicoret → nilai baru, lencana "Utuh", lapisan "Template global". Pelanggan 360 → tab `customer-360-tab-changes` tampil untuk admin, tersembunyi untuk sales. |
| AUTH-06 | PASS (sebagian skenario) | Ganti entitas Sukacita/Kanda/Cipta + refresh: `?entity` dipertahankan, data ter-scope. Link unduhan belum. |
| MASTER-06 | PASS (sebagian skenario) | Pencarian Master Produk menyaring daftar; paginasi tampil; KNSelect. |
| COMM-06 | PASS (sebagian skenario) | Pencarian pelanggan, empty state berbahasa Indonesia, tombol Export ada. |
| HR-06 | PARTIAL | Manager (punya `hr.view_pii`) melihat gaji; tidak ada akun demo `hr.view` tanpa `view_pii`. Redaksi di audit dibuktikan backend (AUDIT-02). |
| OPS-06 | PASS (sebagian skenario) | Shell desktop 1920 & mobile 390 tampil tanpa layar kosong. |

Kasus UAT lain (QC-06, PROD-06, INV-06, SALE-06, APAR-06, GL-06, DESIGN-06, DOC-06, GRN-06) belum dijalankan → `planned` di coverage.json. RFID-06 `blocked` (butuh perangkat fisik).
