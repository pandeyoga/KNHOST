# D — Retur (jual & beli)

HEAD: `91a3ec0`. Pemilik menyatakan masih ragu. Perintah: pasangan state **jangan langsung dituduh duplikat** — periksa pembagiannya.

---

## RT-01 — Pembagian state retur: terverifikasi SAH (bukan duplikat)

- **Keparahan:** — (informasi; menutup kecurigaan duplikasi)
- **Jenis akar:** (tidak ada — pembagian benar)
- **Bukti:**
  - `backend/services/sales_return_transition.py:3` menyatakan eksplisit: "Tabel transisinya tetap **SATU**: `services/return_state.TRANSITIONS`". Jadi `return_state` = tabel transisi, `sales_return_transition` = penulis (modul tipis) yang memakai tabel itu. **Bukan** dua tabel.
  - `backend/services/purchase_return_state.py:27` `SUPPLIER_STATES` (status RMA ke supplier) vs `backend/services/purchase_return_doc_state.py:28` `TRANSITIONS` (status **dokumen**: draft/pending_approval/approved/rejected). Dua **sumbu** berbeda (hubungan supplier vs persetujuan dokumen), sah berdampingan.
- **Kesimpulan:** kecurigaan duplikasi pada dua pasangan ini **tidak terbukti**. Tidak dibuat ID perbaikan untuk ini.

---

## RT-02 — Banyak pintu penyelesaian retur: risiko uang/stok ganda (perlu bukti data acuan)

- **Keparahan:** Sedang
- **Jenis akar:** duplikasi (dugaan) / efek uang-stok
- **Bukti:** terdapat 27 modul `*return*` di `backend/services/`. Khusus penyelesaian terdapat beberapa pintu:
  `return_roll_settlement_service.py`, `return_settlement_policy.py`, `return_compensation_service.py`,
  `return_replacement_service.py`, `return_cutloss_split_service.py`. Tiap pintu berpotensi menulis efek uang (refund/kredit/
  nego) dan/atau stok.
- **Akibat (dugaan):** bila lebih dari satu pintu bisa menyelesaikan satu retur, ada risiko kompensasi/stok ganda atau
  retur macet di antara pintu. Inilah sumber keraguan pemilik.
- **Langkah reproduksi (butuh data acuan):** telusuri satu retur per-roll melewati inspeksi → disposisi → penyelesaian;
  petakan **semua penulis** field settlement/refund/credit dan cek apakah dua pintu bisa jalan untuk retur yang sama.
- **Arah perbaikan:** peta sumber kebenaran penyelesaian (satu field status + satu penulis); pintu lain memanggil pintu tunggal.
- **Catatan jujur:** skala (berapa retur acuan sudah ganda/macet) belum dihitung karena tidak ada stack acuan di sesi ini.
  Dirujuk ke audit keuangan `docs/finance/AUDIT_KEUANGAN_2026-11-13.md` untuk efek jurnal.
