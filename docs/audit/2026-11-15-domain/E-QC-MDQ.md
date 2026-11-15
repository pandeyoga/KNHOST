# E — QC & MD Quality

HEAD: `91a3ec0`.

---

## QM-01 — Dua pintu menetapkan grade/keputusan satu roll

- **Keparahan:** Tinggi
- **Jenis akar:** pintu ganda + aturan tidak ditegakkan
- **Bukti (berkas:baris):**
  - Pintu SPK inspeksi: `backend/routers/inspections.py:94` `POST /inspections/qc-4point`, `:257` `.../lines/{line_id}/inspect` (grade per roll), `:530` `.../mdq-cut`.
  - Pintu inbound roll: `backend/routers/qc_inspection.py:71` `POST /inbound/rolls/{roll_id}/inspect`, `:122` `/inventory/rolls/{roll_id}/hold`, `:137` `/release`, dan terutama `:169` `POST /inventory/rolls/{roll_id}/grade-override`.
- **Akibat:** satu roll bisa memperoleh/berubah grade dari dua tempat berbeda. `grade-override` adalah pintu kedua yang mengubah grade **di luar** SPK 4-point, sementara seed gagal karena aturan "QC 4-point wajib SPK terpisah" (dicatat di perintah §6). Jadi aturan ditegakkan di satu pintu tetapi dilewati pintu lain → pengalaman QC membingungkan dan hasil grade bisa tidak konsisten dengan pemeriksaan.
- **Langkah reproduksi (data acuan):** grade satu roll lewat SPK 4-point, lalu ubah grade roll yang sama lewat `grade-override`; amati grade terakhir menimpa tanpa jejak ke SPK.
- **Dampak uang/stok:** grade memengaruhi harga (grade A/B), impairment retur (`return_grade_impairment`), dan nilai stok; dua pintu = nilai bisa berubah tanpa dokumen pemeriksaan.
- **Arah perbaikan:** satu pintu keputusan grade; `grade-override` harus menulis jejak ke SPK dan dibatasi izin tertentu (izin, bukan nama peran — `docs/KN_08_UI_UX_STANDARDS.md`).
- **Keputusan pemilik:** Pertanyaan #4 (siapa boleh override & wajib jejak?).

---

## Catatan (tindak lanjut)

Jumlah pintu keputusan QC untuk satu roll dan "siapa boleh memutuskan apa" perlu dipetakan penuh terhadap izin
(`require_permission`) per endpoint di `inspections.py` & `qc_inspection.py`; apakah hasil QC (grade/tolak/retur) sampai
ke stok, harga, dan retur beli dengan **satu** cara. Modul: `qc_service`, `qc_inspection_service`, `inspection_service` +
`inspection_state`, `makloon_receipt_qc`, `inbound_qc_common`, `grade_service`, `grade_master_service`.
