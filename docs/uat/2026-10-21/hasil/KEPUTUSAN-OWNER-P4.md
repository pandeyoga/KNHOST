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

## 2. Akses lintas badan usaha dapat dikonfigurasi per peran (ROLE-01 lintas PT)
- Akar masalah: akses lintas PT = himpunan statis `role_registry.CROSS_ENTITY_ROLES` (admin & manager bawaan);
  peran kustom selalu `cross_entity=False`, peran bawaan lain tidak bisa dinyalakan.
- Perubahan perilaku: pengaturan per peran `permission_settings.cross_entity.<peran>` (bawaan & kustom) lewat layar
  **Peran & Hak Akses** (sakelar "Akses semua badan usaha (lintas PT)" + tercantum di konfirmasi simpan + penanda
  *Semua PT* di kartu peran) / `PATCH /api/access/roles/{id}` `cross_entity`. Bawaan: peran bawaan → registry
  (Admin, Manager); peran kustom → nilai EFEKTIF peran acuannya (turunan Manager otomatis lintas PT, sesuai jawaban
  owner). Nilai sama dengan bawaan disimpan sebagai "ikut bawaan"; *Kembalikan ke bawaan* / hapus peran membersihkan
  pengaturan. Admin dikunci selalu lintas PT (403). Registry menerapkan pengaturan saat startup & setiap perubahan
  peran (`sync_registry`) dengan mengubah `CROSS_ENTITY_ROLES` DI TEMPAT sehingga semua pemakai (konteks badan usaha,
  daftar PT boleh dibuka, header `X-Entity-Id`) ikut. Mematikan akses → PT lain ditolak 403 "tidak ditugaskan".
  Versi peran (deteksi konflik simpan) ikut memuat nilai ini. Self-test registry: "BAWAAN hanya admin & manager".
- Berkas: `backend/role_registry.py`, `backend/services/custom_role_service.py`, `backend/routers/access_roles.py`,
  `frontend/src/features/settings/entities/RoleEditorDrawer.jsx`, `RoleAccessPanel.jsx`.
- Pengujian: `test_role_cross_entity_config.py` (3 — turunan Manager ikut lintas PT lalu dimatikan → PT lain 403;
  Finance dinyalakan → semua PT, dikembalikan; Admin dikunci; Sales tidak boleh mengubah). **Merah dulu**
  (3 berkas versi `a00b4a5`): **2 gagal**, 1 lulus (penjaga izin). **Sesudah: 3/3.** Jest `roleCrossEntity.test.js`
  (2). Seluruh Jest **67/67**. Regresi area peran/akses (23 berkas tes lama): himpunan gagal **sama dengan HEAD**
  kecuali `test_iter291::test_create_two_orders_rejected` (bergantung data: butuh SJ belum ditugaskan dari 2 pesanan —
  dijalankan sendiri dilewati; aturan logistik "satu pesanan", tidak terkait peran).

## Keputusan owner Q-01..Q-06 (rencana perbaikan UAT) — dicatat 2026-10-21
| Kode | Temuan | Jawaban owner |
|---|---|---|
| Q-01 | F-06 | (a) SO otomatis *Terkirim* saat semua Surat Jalan ber-POD |
| Q-02 | F-10 | Blok keras: CBD wajib lunas, DP minimal = persen DP termin; pengecualian oleh pemegang izin (Finance/Manager), alasan wajib & teraudit — **harus ada, jelas, dan dapat dikonfigurasi** |
| Q-03 | F-14 | (a) Satu keputusan: keputusan SPK melepas/menahan karantina |
| Q-04 | F-15 | Toleransi ±5% menyesuaikan tagihan otomatis; di atasnya persetujuan ulang Finance/Admin Sample |
| Q-05 | F-16 | (a) Jatuh tempo dihitung dari **Surat Jalan pertama**; SO belum dikirim tidak masuk daftar jatuh tempo |
| Q-06 | F-13 | (b) MD Quality baru boleh mengisi sesudah SPK ditugaskan |

## Arahan berikutnya (owner 2026-10-21)
Setelah semua perbaikan selesai: revisi dokumen UAT menjadi **alur end-to-end per cabang** (setiap kombinasi cabang
= satu alur lurus dari awal sampai lunas, tanpa bolak-balik) dan **cek setiap langkah lewat antarmuka** (tombol/menu
benar-benar ada untuk peran itu), bukan hanya backend.
