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
| E-S1 | gagal | bukti/runtime/E-S1.txt — 6 roll dipindai jadi 1 roll 300 yard (QM-02); satu penerimaan butuh tugas + SPK penerimaan (MD Quality) + SPK 4-point (QC), keputusan tolak diisi dua kali (QM-03); QC tolak vs MD Quality terima → roll `blocked` tanpa tindak lanjut (QM-04) |
| E-S2 | terhambat | bagian grade→stok dijalankan (SPK 4-point: A/BS, riwayat grade tercatat) — bukti/runtime/E-S1.txt; bagian grade→harga jual belum dijalankan |
| E-S3 | terhambat | SPK inspeksi MD Quality: butuh tugas inspeksi |
| E-S4 | terhambat | QC hasil makloon: butuh SPK makloon selesai |
| E-S5 | gagal | bukti/runtime/D-S2-S3.txt + bukti/runtime/E-S1.txt — roll retur turun A→BS dan potongan cutloss BS tanpa `grade_history` (RT-07) |
| E-S6 | gagal | bukti/runtime/E-S1.txt — `grade-override`: qc/warehouse/mdquality 403 (izin), whadmin ditolak dengan pesan berbasis NAMA peran; mdquality `start` 403 tetapi `inspect`+`finish` 200 (QM-05) |

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

### QM-02 — Penerimaan lewat scan-receive melebur banyak roll fisik menjadi satu roll sistem
- Keparahan: Tinggi
- Jenis akar: pintu ganda
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/services/inbound_complete_service.py:58` · `backend/routers/inbound_receiving.py:129` · `bukti/runtime/E-S1.txt`
- Reproduksi: PO 300 yard → 6× `scan-receive` @50 yard dengan `roll_id` berbeda → `complete` tanpa `rolls`. Hasil: satu roll RL-46493 300 yard, SPK 1 baris. Dengan `rolls[]` di `complete` → 6 roll.
- Dampak: QC per roll dan tolak sebagian mustahil; panjang roll di stok tidak sama dengan fisik. Skrip data contoh memakai jalur ini.
- Arah perbaikan: `complete` menolak bila jumlah pindaian > 1 tetapi roll tidak dirinci, atau membuat roll per pindaian.
- Keputusan pemilik: —
- Sudah ada: —

### QM-03 — Satu penerimaan PO butuh tiga dokumen dan keputusan tolak diisi dua kali
- Keparahan: Tinggi
- Jenis akar: duplikasi
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/services/inspection_service.py:1024` · `backend/routers/inspections.py:94` · `backend/routers/inspections.py:315` · `bukti/runtime/E-S1.txt`
- Reproduksi: Tugas terima → SPK penerimaan: QC mengisi baris → 400 "QC 4-point dikerjakan di SPK tersendiri"; `finish` → 400 "belum ada baris diperiksa". Buat SPK 4-point, QC menolak 2 roll dan menutup dengan `rejected_roll_ids` + retur potong tagihan → 200 tetapi roll tetap karantina. Baru sesudah MD Quality mengisi warna/handfeel dan menutup SPK penerimaan dengan daftar tolak yang sama, roll lepas dan retur beli lahir.
- Dampak: Pekerjaan macet bila salah satu bagian tidak tahu gilirannya; isian tolak QC diterima server lalu diabaikan; MD Quality yang akhirnya memutus retur atas temuan QC.
- Arah perbaikan: Satu keputusan karantina per penerimaan yang membaca hasil kedua bagian; SPK 4-point menolak isian yang tidak dipakainya.
- Keputusan pemilik: Siapa pemutus akhir tolak/retur: QC atau MD Quality?
- Sudah ada: QM-01

### QM-04 — QC menolak roll, MD Quality menerima: roll berakhir `blocked` tanpa dokumen tindak lanjut
- Keparahan: Sedang
- Jenis akar: status
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/services/inspection_service.py:184` · `backend/routers/inspections.py:315` · `bukti/runtime/E-S1.txt`
- Reproduksi: PO-00003: SPK 4-point grade BS + tolak + "ganti barang" → SPK penerimaan ditutup MD Quality `terima`. Hasil: tugas `completed`, roll RL-46493 `blocked` grade BS 300 yard, retur beli 0, PO selesai.
- Dampak: Rp4.200.000 persediaan tertahan tanpa retur, tanpa antrean keputusan; permintaan ganti barang QC hilang.
- Arah perbaikan: Tutup SPK penerimaan dengan `terima` ditolak bila ada roll yang ditolak QC dan belum diputus.
- Keputusan pemilik: —
- Sudah ada: —

### QM-05 — Izin QC tidak konsisten dan sebagian berbasis nama peran
- Keparahan: Rendah
- Jenis akar: aturan tidak ditegakkan
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/routers/qc_inspection.py:169` · `backend/routers/inspections.py:247` · `backend/services/return_grade_impairment.py:1` · `bukti/runtime/E-S1.txt` · `bukti/runtime/D-S2-S3.txt`
- Reproduksi: `grade-override` oleh whadmin → 403 "Hanya manager/admin …"; mdquality `POST /inspections/{id}/start` → 403 tetapi `inspect` dan `finish` di SPK yang sama → 200; faktor turun grade memuat A2/B1/C padahal grade aktif hanya A, A1, B, BS.
- Dampak: Aturan tidak bisa diatur lewat izin; pemakai bingung mengapa bisa menutup SPK yang tak bisa dimulainya.
- Arah perbaikan: Pakai izin; samakan daftar grade dengan master.
- Keputusan pemilik: —
- Sudah ada: —
