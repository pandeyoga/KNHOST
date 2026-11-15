# E — QC & MD Quality

HEAD: `91a3ec0`.

---

## QM-01 — DITARIK (false positive): grade roll sudah satu penulis

- **Status:** ditarik setelah verifikasi. Bukan temuan.
- **Bukti kebersihan:**
  - **Satu penulis** grade: `backend/services/grade_service.py:64` `set_roll_grade(...)` — satu-satunya yang menulis `{"$set": {"grade": …, "grade_source": …}}` + `{"$push": {"grade_history": entry}}` (`:95-97`).
  - Pemanggil: inspeksi 4-point `qc_inspection_service.py:341`, koreksi `routers/qc_inspection.py:183`; `inspection_service.py:14` (docstring) juga mengarah ke `set_roll_grade(source="qc_inspection")`.
  - `grade-override` (`routers/qc_inspection.py:169-191`) adalah jalur koreksi **terkendali**: izin `require_permission("wms","approve")` (admin/manager), `reason` wajib (D-23), menulis `grade_history` + audit, `source="manager_override"`. Jadi **bukan** pintu liar; justru teladan SSOT + jejak.
- **Catatan:** klaim pass awal ("dua pintu keputusan grade / aturan tak ditegakkan") salah dan dikoreksi di sini demi jejak audit jujur.

---

## Cakupan yang BELUM dituntaskan (jujur — bukan "bersih")

Domain QC/MDQ belum diaudit tuntas tingkat-alur di sesi ini. Yang perlu pass berikut (butuh data acuan untuk reproduksi):

1. **Pintu keputusan terima/tolak/karantina satu roll** di `qc_service.py` (karantina penerimaan) vs `inspection_service.py`/`inspection_state.py` (SPK inspeksi/PA) vs `makloon_receipt_qc.py`/`inbound_qc_common.py` — apakah "terima/tolak" juga punya satu penulis seperti grade, atau tersebar.
2. **Izin vs nama peran** per endpoint `routers/inspections.py` & `qc_inspection.py` (ukur ke `docs/KN_08_UI_UX_STANDARDS.md`: izin, bukan nama peran).
3. **Rantai hasil QC → stok/harga/retur beli** — apakah grade/tolak/retur sampai ke tiga tempat dengan satu cara.

Tidak dibuat temuan baru tanpa bukti. Modul relevan: `qc_service`, `qc_inspection_service`, `inspection_service`+`inspection_state`,
`makloon_receipt_qc`, `inbound_qc_common`, `grade_service`, `grade_master_service`, `return_grade_impairment`.

---

## Verifikasi runtime (sesi backend hidup)

Status: **kode decisive; runtime TERHAMBAT-DATA**. `db.inventory_rolls.countDocuments({grade_history:{$exists:true,$ne:[]}})` = **0** di data acuan (seed belum menjalankan inspeksi/override), jadi jalur grade belum bisa dipicu lewat data. Namun QM-01 ditarik atas dasar **kode decisive** (satu penulis `grade_service.set_roll_grade`, `grade_history` wajib, override berizin) — tidak bergantung data. Cakupan terima/tolak/karantina (pintu keputusan selain grade) perlu seed inspeksi untuk reproduksi runtime; dicatat sebagai pendalaman lanjutan, bukan temuan tanpa bukti.
