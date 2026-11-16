# E — QC & MD Quality — audit §8

HEAD: `91a3ec0`. Data acuan: 0 `grade_history` di roll → alur QC E2E `terhambat`; QM-01 dinilai tingkat kode (satu penulis grade).

## Peta sumber kebenaran: grade & keputusan roll

```
grep -rn 'set_roll_grade(' backend --include=*.py | grep -v 'def '
grep -rnE 'grade_history|\$set.*grade' backend/services/grade_service.py
```
Penulis grade (tunggal): `backend/services/grade_service.py:64` (`set_roll_grade`, tulis `grade_history` `backend/services/grade_service.py:95`). Pemanggil: `backend/services/qc_inspection_service.py:341` (SPK 4-point) · `backend/routers/qc_inspection.py:183` (grade-override berizin).

## Pintu ganda

| Pekerjaan | Pintu | Seharusnya |
|---|---|---|
| Tetapkan grade roll | SPK 4-point & grade-override — keduanya lewat `set_roll_grade` (satu penulis) | sudah satu penulis (baca kode) |
| Keputusan terima/tolak/karantina | qc_service / inspection_service / makloon_receipt_qc | perlu verifikasi runtime satu penulis |

## Matriks skenario

| Skenario | Status | Bukti/alasan |
|---|---|---|
| E-S1 | terhambat | penerimaan PO ber-QC: butuh PO+penerimaan+QC berjalan |
| E-S2 | terhambat | QC 4-point→grade→harga/stok: 0 grade_history di seed |
| E-S3 | terhambat | SPK inspeksi MD Quality: butuh tugas inspeksi |
| E-S4 | terhambat | QC hasil makloon: butuh SPK makloon selesai |
| E-S5 | terhambat | pemeriksaan retur jual: 0 retur |
| E-S6 | terhambat | izin qc/mdquality/warehouse/manager: butuh jalankan endpoint grade/override per akun (data 0) |

## Inventaris form & dropdown

| Form | Field | Sumber pilihan | Saringan | Ditegakkan server? | Masalah |
|---|---|---|---|---|---|
| QCInspection.jsx | accept-grade (335) | `gradeOptions` | — | ya | — |
| QCInspection.jsx | disposition (355) | `DISPOSITION_OPTIONS` | — | ya | — |
| InspectLineModal.jsx | grade (200) | opsi grade | — | ya | — |
| InspectLineModal.jsx | grade-line (208) | `grades` | — | ya | — |
| InspectLineModal.jsx | return-condition (224) | `RETURN_CONDITIONS` | — | ya | — |
| InspectLineModal.jsx | color (238) | `colorOptions` | — | ya | — |
| InspectLineModal.jsx | handfeel (244) | `handfeelOptions` | — | ya | — |
| InspectSheetGrid.jsx | grade-rule (182) | opsi grade sheet | — | ya | — |

## Temuan

### QM-01 — pintu keputusan grade roll (baca kode: satu penulis; butuh uji runtime)
- Keparahan: belum ditetapkan
- Jenis akar: pintu ganda (dugaan)
- Tingkat bukti: dugaan (baca kode)
- Bukti: `backend/services/grade_service.py:64` (`set_roll_grade`, satu penulis) + `grade_history` `backend/services/grade_service.py:95`; pemanggil `backend/services/qc_inspection_service.py:341` & `backend/routers/qc_inspection.py:183`.
- Reproduksi: uji runtime yang dibutuhkan — grade satu roll via 4-point lalu ubah via grade-override sebagai qc@/mdquality@/warehouse@/manager@; cek `grade_history` memuat semua perubahan; cari jalur lain yang menulis grade tanpa history. Data acuan 0 grade → belum dijalankan.
- Dampak: bila ada penulis grade kedua tanpa history, grade bisa tak konsisten dgn pemeriksaan.
- Arah perbaikan: pastikan satu penulis + jejak; batasi override dgn izin.
- Keputusan pemilik: siapa (izin apa) boleh override grade & wajib jejak?
- Sudah ada: —.
