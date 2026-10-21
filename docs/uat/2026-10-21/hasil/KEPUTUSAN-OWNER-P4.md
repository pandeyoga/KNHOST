# Keputusan owner 2026-10-21 (putaran 4)

- Commit awal: `15c63f6`        - Branch: `main`
- Jawaban owner:
  1. Harga khusus untuk baris yang dihapus → **setuju** usulan: entri harga khusus produk itu otomatis dibatalkan.
  2. Akses lintas badan usaha untuk peran kustom → **perlu**, dan dapat **dikonfigurasi per peran** (bukan hanya
     turunan Manager).
  3. Batal item OD pada SO yang sudah dibayar/berfaktur → **nota kredit otomatis**, tetap bisa dikoreksi Finance.
  4. Pertanyaan Q-01..Q-06 (rencana perbaikan UAT) → diminta ditampilkan.
  5. Restore DB dev → **tidak dulu**, fokus development & perbaikan.
  6. Bersihkan container/worktree/cabang sesi yang selesai → **boleh** (dikerjakan: 4 worktree, 4 cabang lokal
     yang sudah termuat di `main`, 4 container `kn-wt-*`, 3 DB `kn_wt_*`; cabang tidak pernah di-push).

## 1. Baris dihapus → entri harga khusus produk itu dibatalkan (lanjutan F-09)
- Akar masalah: Override SO (hapus baris) dan batal item OD sesudah SO (FE-01) membuang baris dari `items` tanpa
  menyentuh `pending_approvals`. Entri harga khusus produk itu yang menunggu tak bisa disetujui ("produk sudah tidak
  ada"); yang ditolak mengunci SO selamanya (produknya tak bisa diajukan ulang).
- Perubahan perilaku: kedua jalur memanggil `so_approvals.cancel_for_removed_products` — entri harga khusus produk
  baris yang dihapus berstatus *menunggu*/*ditolak* → `cancelled` (+ `previous_status`, `cancel_reason`, pelaku,
  waktu; keputusan lama tidak ditimpa); entri yang sudah disetujui dibiarkan; dokumen persetujuan harga yang masih
  menunggu ikut `cancelled`, yang sudah ditolak tetap `rejected` (riwayat, sama dengan F-09). Field persetujuan SO
  dihitung ulang. Override mencatat perubahan "Pengajuan harga khusus dibatalkan (baris dihapus)" di amandemen.
  Panel Persetujuan SO menampilkan status *Dibatalkan — baris dihapus* beserta alasannya.
- Berkas: `backend/services/so_approvals.py`, `backend/services/so_override_service.py`,
  `backend/services/so_line_cancel_service.py`, `frontend/src/features/orders/SoApprovalsPanel.jsx`.
- Pengujian (backend & DB terpisah, data acuan seed baru): `test_f09_baris_dihapus.py` (2 — Override: entri ditolak
  → dibatalkan & SO bisa disetujui; entri menunggu → dokumen harga ikut batal, baris lain tak tersentuh) dan
  `test_fe01_cancel_special_price.py` (1 — OD → SO → harga khusus ditolak → batal item OD → entri dibatalkan).
  **Merah dulu** (3 berkas layanan versi `15c63f6`): **3 gagal**. **Sesudah: 3/3.** Regresi F-09, FE-01 (batal item,
  multi-item), LN-022 harga khusus, override SO: **34/34 lulus**.
