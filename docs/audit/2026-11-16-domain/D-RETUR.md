# D — Retur (jual & beli)

HEAD: `91a3ec0`. Pemilik ragu. Perintah: pasangan state jangan langsung dituduh duplikat — periksa.


> **Status domain: BELUM DIKERJAKAN.** Skenario wajib §8 dan inventaris form domain ini belum dijalankan. Semua isi di bawah berlabel **dugaan (baca kode)** sampai diuji lewat layar/API pada sesi domainnya.
---

## RT-01 — Pembagian state retur terverifikasi SAH (bukan duplikat)

- **Keparahan:** — (informasi; menutup kecurigaan duplikasi)
- **Tingkat bukti:** dugaan (baca kode)
- **Bukti:**
  - `backend/services/sales_return_transition.py:3` menegaskan "Tabel transisinya tetap **SATU**: `services/return_state.TRANSITIONS`"; `:38` memanggil `st.assert_transition`. Jadi `return_state` = tabel, `sales_return_transition` = penulis tipis. Bukan dua tabel.
  - `purchase_return_state.py:27` `SUPPLIER_STATES` (status RMA supplier) vs `purchase_return_doc_state.py:28` `TRANSITIONS` (status dokumen: draft/pending_approval/approved/rejected) — dua **sumbu** berbeda, sah berdampingan.
- **Kesimpulan:** kecurigaan duplikasi tidak terbukti. Tidak dibuat ID perbaikan.

---

## RT-02 — Banyak sub-service penyelesaian retur (perlu bukti data acuan)

- **Keparahan:** Rendah (dugaan — belum terbukti) · **Jenis akar:** duplikasi (dugaan) / efek uang-stok
- **Tingkat bukti:** dugaan (baca kode)
- **Fakta terverifikasi sejauh ini:** 27 modul `*return*`. Penyelesaian: `return_roll_settlement_service.py` memakai state tunggal — `FAMILY_STATE` memetakan ke `return_state.REFUND_SETTLED/CREDIT_SETTLED/NEGO_SETTLED` (`:31-32`), jadi settlement tampak **lewat satu state machine**. Sub-service lain (`return_compensation_service`, `return_replacement_service`, `return_cutloss_split_service`) adalah bagian-bagian (nego/tukar/potong-rugi), belum terbukti menghasilkan uang/stok ganda.
- **Kejujuran:** risiko "uang/stok ganda" **tidak terbukti** di sesi ini dan tidak bisa dibuktikan tanpa dataset acuan. Diturunkan dari "temuan" menjadi **pertanyaan untuk diverifikasi**.
- **Langkah verifikasi (pelaksana, data acuan):** telusuri satu retur per-roll inspeksi → disposisi → penyelesaian; petakan semua penulis field settlement/jurnal (rujuk `docs/finance/AUDIT_KEUANGAN_2026-11-13.md`); pastikan dua sub-service tak bisa menyelesaikan retur yang sama dua kali.
- **Arah (bila terbukti):** satu pintu penyelesaian yang memanggil sub-service; satu status + satu penulis.

---

## Verifikasi runtime (sesi backend hidup)

Status: **TERHAMBAT-DATA**. `db.sales_returns.countDocuments({})` = **0** dan `db.purchase_returns` = **0** di data acuan (seed tidak membuat retur). Maka RT-02 (risiko uang/stok ganda) **tidak bisa diuji runtime** di sesi ini — tetap sebagai pertanyaan-perlu-data. RT-01 (pembagian state SAH) sudah terkonfirmasi tingkat kode (`sales_return_transition.py:3` satu tabel; dua sumbu status beli). Untuk pendalaman runtime perlu seed retur (mis. `seed_sample_returns`) atau membuat retur baru (mutasi — di luar sesi baca-saja).
