# KEPUTUSAN-2026-10-21 — Tindak lanjut jawaban owner

- Commit awal: `59be2da` · Commit perbaikan: `af24f9c` (default izin + AUD-RND-03), `13c64d8` (batal per item OD) · Branch: `main`
- ID ditangani: AUD-RND-03, FE-01 (lanjutan: batal per item), ROLE-01 (lanjutan: default matriks izin)
- Jawaban owner (2026-10-21, dicatat apa adanya):
  1. Batal per item Pesanan Khusus: **perlu**.
  2. Kontrak yang sudah dihentikan masih boleh dipakai sebagai referensi: **bisa**.
  3. QC/Manager vs matriks izin: **dapat dikonfigurasi di matriks izin; default dipilih implementer
     "secara teori baiknya"**.
- Lingkungan uji: Docker lokal, data acuan `scripts/dev_restore_demo.sh`, matriks izin dari DB, browser bawaan.

## AUD-RND-03 — Referensi kontrak dihentikan diterima backend, tidak muncul di daftar pilihan
- **Berlaku di HEAD:** ya — `contract_options` menyaring `terminated`, `_validate_contract_ref` menerimanya.
- **Perubahan perilaku:** daftar pilihan referensi uji ulang kini memuat kontrak **dihentikan** (label
  "dihentikan (referensi historis)"); validator tidak diubah. Kontrak batal/kedaluwarsa tetap disaring
  (belum diputuskan — lihat pertanyaan baru di bawah).
- **Berkas:** `backend/services/rnd_revalidation_service.py`, `frontend/src/features/rnd/RevalDecideModal.jsx`.
- **Pengujian:** `test_l03_ln034_revalidation_edges.py::test_contract_reference_options` diperluas (kontrak
  `terminated` muncul + status terkirim); gagal di kode lama, lulus sesudahnya. Revalidasi 9/9.
- **Status:** implemented_pending_review

## ROLE-01 lanjutan — Default matriks izin (QC, kebijakan retur, master entitas)
Prinsip yang dipakai: (a) **izin domain, bukan izin sistem** — pemilik proses memegang izinnya;
(b) **satu data → satu izin** (layar mana pun yang menulis data yang sama menuntut izin yang sama);
(c) **hak minimum** — tidak memberi `settings.manage`/`entity.update` (pengaturan sistem & aturan
persetujuan tetap Admin, menjaga pemisahan tugas). Semua tetap dapat diubah di matriks izin.

| Aksi | Sebelum | Sesudah (default) | Pemegang bawaan |
|---|---|---|---|
| Lihat antrean QC kedatangan | `wms.view` | `wms.view` **atau** `qc.view` | + QC, MD |
| Putus karantina (terima/tolak) | `wms.update` | `wms.update` **atau** `qc.release` (= putusan dokumen inspeksi) | + QC, MD |
| Kebijakan Retur Jual (buat/ubah/hapus) | `settings.manage` | `sales_return.policy` (izin yang sudah dipakai setelan retur di Pusat Pengaturan) | Admin, Manager |
| Asumsi Retur (`PUT /settings` bagian `returns`) | `entity.update` | `sales_return.policy`; bagian lain tetap `entity.update`; payload campuran menuntut semuanya | Admin, Manager |
| Master Entitas — Kategori Biaya | `settings.manage` | `cash_settlement.manage` (= `PATCH /expense-categories`) | Admin, Manager |
| Master Entitas — Alasan Keluhan Retur | `settings.manage` | `sales_return.policy` | Admin, Manager |
| Master Entitas — Tahapan Proses | `settings.manage` | `process_recipe.create/update/delete` | Admin, Manager, MD |
| Master Entitas — Jenis Sampling | `settings.manage` | `rnd.manage` | Admin, Manager, MD |
| Master Entitas — Lini Produk | `settings.manage` | `product.create/update/delete` (master produk milik MD) | Admin, MD |
| Master Entitas — Syarat Pembayaran | `settings.manage` | `entity.create/update/delete` (= `/payment-terms`) | Admin |
| Master Entitas — Template Dokumen | `settings.manage` | `template.create/update/delete` (= `/document-templates`) | Admin |

- Daftar `GET /entity-masters/{kind}` kini mengirim `can.{create,update,override,revert}` untuk akun itu;
  layar Master Entitas memakai nilai server itu (tidak menebak). QC hub menampilkan antrean bila
  `wms.view` atau `qc.view`.
- **Berkas:** `backend/routers/{inbound_receiving_extra,return_policies,settings,entity_masters}.py`,
  `backend/services/entity_master_service.py`; FE `QcHubView`, `ReturnPoliciesView`, `EntityMastersView`,
  `config/auditLabels.js` (label aksi "Atur Kebijakan").
- **Pengujian:** pytest baru `test_role01_matrix_defaults.py` **11/11** (QC lihat/putus via qc.*, Finance 403;
  kebijakan retur Manager lolos/Sales 403; Asumsi Retur Manager 200, bagian pajak & payload campuran 403;
  7 jenis master: `can.update` & hasil PATCH sesuai pemegang izin). **Bukti-merah:** semua 11 + 1
  (AUD-RND-03) gagal di kode lama. Regresi 7 berkas tes area terkait (settings/retur/QC/master): tidak ada
  gagal baru (9 gagal + 35 error sudah ada sebelumnya). Jest: QC hub (MD Quality → dokumen saja; QC qc.view →
  antrean). ESLint ketat: tanpa temuan baru.
- **Status:** implemented_pending_review

## FE-01 lanjutan — Batal per item Pesanan Khusus
- **Aturan (default dipilih implementer; lihat pertanyaan di bawah):**
  - Endpoint `POST /special-orders/{id}/items/{item_id}/cancel`, izin `order.update`, alasan wajib (≥5 karakter).
  - Boleh selama OD belum batal/terkirim/selesai **dan belum dikonversi ke SO** (sesudah SO: koreksi SO).
  - Harus tersisa ≥1 item aktif (item terakhir → batalkan seluruh OD).
  - Semua syarat dicek **sebelum** ada perubahan. PO/MKO aktif item dibatalkan lewat aturan modulnya
    (butuh `od_fulfillment.cancel`; ditolak bila sudah ada penerimaan/bahan terkirim). PR yang belum jadi
    PO dipensiunkan. Sample R&D & permintaan desain item yang masih berjalan ikut dibatalkan (sample yang
    sudah diputus tetap sebagai jejak; sample menunggu keputusan PIC → ditolak 409).
  - Item **tidak dihapus**: status batal + alasan + oleh + waktu; total header & ringkasan dihitung ulang.
    Bila harga sudah dikunci: baris item batal dibuang, **harga item lain tidak berubah**, total kunci
    dihitung ulang.
  - Item batal tidak ikut: kebutuhan pemenuhan, rincian harga, penahan ACC pelanggan, perutean saat
    approve, proofing otomatis, konversi SO.
- **Berkas:** `backend/routers/special_orders.py` (endpoint + inti batal dokumen dipakai bersama LN-033 T08),
  `backend/services/special_order_{items,fulfillment,phase2,routing}.py`; FE `SpecialOrderItemsPanel.jsx`,
  `SpecialOrderDetail.jsx`.
- **Pengujian:**
  - pytest baru `test_fe01_od_cancel_item.py` **4/4**: (1) batal sebelum ACC → sample item batal, ACC tidak
    tertahan, kunci & SO hanya item aktif, batal sesudah SO 409; (2) batal sesudah kunci → harga item lain
    sama, total = jumlah sisa; (3) penolakan: alasan pendek 422, Finance 403, item tak dikenal 400, sudah
    batal 409, item aktif terakhir 400; (4) PO/MKO aktif ikut batal, Admin Sales tanpa
    `od_fulfillment.cancel` ditolak, item keluar dari kebutuhan pemenuhan, riwayat dokumen tersimpan.
  - **Bukti-merah:** 4/4 gagal di kode lama. Regresi 13 berkas tes OD/LN-030..033/FE-01: tidak ada gagal
    baru (gagal/error lama sama persis sebelum & sesudah, mayoritas `iter49` login/fixture lama).
  - Jest `odItemCancel.test.js` 3/3; semua jest **34/34**.
- **Bukti UI (browser, akun admin demo):** OD uji 2 item (dibuat lewat API, dihapus sesudah uji) → tombol
  "Batalkan item" di kedua item → batalkan item 2 dengan alasan → item 2 dicoret + "Dibatalkan oleh … —
  alasan", judul "1 aktif · 1 batal", tombol batal hilang (item aktif terakhir), pesan "Ikut dibatalkan:
  KSC/SMP-00169"; panel keputusan pelanggan hanya menunggu sample item 1; total OD = 50 × Rp25.000.
- **Fixture vs proses nyata:** hasil R&D per item (sample `decided` + harga kontrak) disiapkan langsung
  (sama dengan tes FE-01); sisanya lewat API resmi.
- **Status:** FE-01 tetap implemented_pending_review (kini termasuk batal per item).

## Keterbatasan / belum diuji
- Batal item **sesudah SO** sengaja ditolak (pakai koreksi SO) — belum ada sinkron otomatis OD↔SO.
- Pembatalan berantai memanggil layanan sample/desain/MKO langsung (wewenang = pembatal item OD), tidak
  menuntut `rnd.manage`/izin desain terpisah; PO memakai endpoint PO sehingga izinnya tetap diperiksa.
- Dokumen PDF/cetak OD belum diperiksa untuk penandaan item batal.
- Tes LN-032 lama meninggalkan 5 spesifikasi R&D uji di DB lokal (bukan dari tes fase ini).
- Notifikasi ke pihak terkait (MD/pengadaan) saat item batal belum ada.

## Yang perlu direview
- Default izin di tabel ROLE-01 lanjutan (terutama MD ikut memutus karantina karena sudah memegang `qc.release`).
- Aturan batal per item (lihat pertanyaan untuk owner).
