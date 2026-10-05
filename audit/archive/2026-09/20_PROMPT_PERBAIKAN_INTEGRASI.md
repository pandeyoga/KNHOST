# Prompt perbaikan temuan integrasi

Baca [19 — temuan](19_TEMUAN_INTEGRASI_LANJUTAN.md). Validasi ulang pada HEAD yang akan diperbaiki. Baseline audit: d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467.

## IX-01 — Jatah cuti nol berubah kembali menjadi jatah default

- [backend/services/hr_leave_service.py:128 — set_entitlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L128)
- [backend/services/hr_leave_service.py:86 — recompute_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L86)

```text
Perbaiki IX-01 di KNHOST. Baca seluruh caller dan validasi ulang temuan pada HEAD aktual sebelum mengedit.

Pemicu dan hasil: Set entitlement=0 secara eksplisit, lalu jalankan recompute_balance. Hasil MongoDB: entitlement kembali menjadi 12.

Akar kesalahan: Penggunaan existing.get("entitlement") or entitlement memperlakukan nol sebagai tidak diisi. entitlement_override tetap true, tetapi nilai override nol hilang saat perhitungan berikutnya.

Perbaikan: Pisahkan missing/None dari angka nol. Baca override hanya jika flag berlaku dan field valid; pertahankan nol. Validasi bilangan bulat nonnegatif dan audit perubahan.

Acceptance criteria: Override 0 bertahan setelah submit/cancel/recompute dan restart; override 5 tetap 5; missing override mengikuti default; nilai negatif ditolak.

Telusuri router, schema, UI, permission, identitas event, projection dan downstream payroll/GL. Pertahankan guard yang sudah benar. Tambahkan pengujian integrasi Mongo dengan fixture mandiri dan expectation perilaku yang benar. Harness audit mengkarakterisasi bug; assertion lama yang lulus bukan kriteria keberhasilan patch.

Siapkan query pendeteksi data historis, dry-run perbaikan, serta reversal/adjustment untuk dokumen posted bila perlu. Jangan menghapus histori atau memutasi produksi secara otomatis. Laporkan perubahan file, hasil test aktual, dampak migrasi dan bagian yang belum terverifikasi.
```


## IX-02 — Pembatalan satu cuti menghapus absensi milik cuti lain yang masih disetujui

- [backend/services/hr_leave_service.py:146 — submit_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L146)
- [backend/services/hr_leave_service.py:180 — _mark_attendance_for_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L180)
- [backend/services/hr_leave_service.py:193 — _clear_attendance_for_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L193)
- [backend/services/hr_leave_service.py:231 — cancel_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L231)
- [backend/services/hr_attendance_service.py:193 — upsert_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_attendance_service.py#L193)

```text
Perbaiki IX-02 di KNHOST. Baca seluruh caller dan validasi ulang temuan pada HEAD aktual sebelum mengedit.

Pemicu dan hasil: Buat dua izin pada tanggal yang sama, approve keduanya, lalu batalkan satu. Dokumen izin lain tetap approved, tetapi record absensi pada tanggal tersebut menjadi 0.

Akar kesalahan: Tidak ada penjaga overlap dokumen. Absensi di-upsert menurut employee+date tanpa ownership leave_id; cancel menghapus seluruh method=leave pada tanggal itu tanpa memastikan dokumen sumber yang dimiliki record.

Perbaikan: Tetapkan aturan overlap; reject atau merge dengan hubungan sumber eksplisit. Simpan provenance leave_request_id pada projection absensi dan rekalkulasi dari seluruh event sah ketika pembatalan. Jangan delete hanya berdasarkan tanggal/method.

Acceptance criteria: Dua pengajuan overlap ditolak sesuai policy atau hanya satu projection teragregasi; cancel A tidak menghilangkan izin B; clock-in/out asli tidak hilang; cancel/retry dan concurrent approval konsisten.

Telusuri router, schema, UI, permission, identitas event, projection dan downstream payroll/GL. Pertahankan guard yang sudah benar. Tambahkan pengujian integrasi Mongo dengan fixture mandiri dan expectation perilaku yang benar. Harness audit mengkarakterisasi bug; assertion lama yang lulus bukan kriteria keberhasilan patch.

Siapkan query pendeteksi data historis, dry-run perbaikan, serta reversal/adjustment untuk dokumen posted bila perlu. Jangan menghapus histori atau memutasi produksi secara otomatis. Laporkan perubahan file, hasil test aktual, dampak migrasi dan bagian yang belum terverifikasi.
```


## IX-03 — Shift malam menghasilkan durasi standar negatif dan lembur palsu

- [backend/services/hr_attendance_service.py:76 — compute_metrics](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_attendance_service.py#L76)
- [backend/services/hr_payroll_service.py:127 — _period_overtime_min](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L127)
- [backend/services/hr_payroll_service.py:174 — compute_payslip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L174)

```text
Perbaiki IX-03 di KNHOST. Baca seluruh caller dan validasi ulang temuan pada HEAD aktual sebelum mengedit.

Pemicu dan hasil: Shift 22:00–06:00; clock-in 5 Oktober pukul 22:00 dan clock-out 6 Oktober pukul 06:00. Hasil: work_min=480, std_min=-960, overtime_min=1440.

Akar kesalahan: Durasi standar mengurangkan jam keluar dan masuk pada hari yang sama; tidak menambah satu hari untuk shift lintas tengah malam. Payroll menjumlahkan overtime_min tersimpan. Schema shift menerima jam tersebut; belum ada UAT layar untuk memastikan seluruh pintu konfigurasi malam.

Perbaikan: Bangun planned_start/planned_end bertanggal dan timezone konsisten, aturan overnight eksplisit, pemisahan break/actual duration, serta validasi shift nol/lebih dari batas. Bila shift malam belum didukung, tolak input secara eksplisit daripada menyimpan angka negatif.

Acceptance criteria: Shift 22–06 menghasilkan standard 480 menit dan overtime 0 untuk kehadiran tepat jadwal; kelebihan 60 menit dihitung sesuai kebijakan istirahat. Uji lintas bulan/tahun, clock-out sebelum masuk, clock-out kosong, dan variasi offset zona waktu.

Telusuri router, schema, UI, permission, identitas event, projection dan downstream payroll/GL. Pertahankan guard yang sudah benar. Tambahkan pengujian integrasi Mongo dengan fixture mandiri dan expectation perilaku yang benar. Harness audit mengkarakterisasi bug; assertion lama yang lulus bukan kriteria keberhasilan patch.

Siapkan query pendeteksi data historis, dry-run perbaikan, serta reversal/adjustment untuk dokumen posted bila perlu. Jangan menghapus histori atau memutasi produksi secara otomatis. Laporkan perubahan file, hasil test aktual, dampak migrasi dan bagian yang belum terverifikasi.
```


## IX-04 — Lembur absensi yang belum disetujui tetap dibayar payroll

- [backend/services/hr_attendance_service.py:193 — upsert_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_attendance_service.py#L193)
- [backend/services/hr_payroll_service.py:127 — _period_overtime_min](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L127)
- [backend/services/hr_payroll_service.py:174 — compute_payslip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L174)

```text
Perbaiki IX-04 di KNHOST. Baca seluruh caller dan validasi ulang temuan pada HEAD aktual sebelum mengedit.

Pemicu dan hasil: Seed absensi overtime 120 menit, status flagged, approved=false. Compute payslip pada gaji 17.300.000 dengan multiplier 1,5 memberi overtime 120 menit dan nilai 300.000.

Akar kesalahan: _period_overtime_min hanya menyaring employee, period dan entity; tidak mensyaratkan approved atau mengecualikan flagged. Marker persetujuan yang ditulis attendance tidak menjadi pagar konsumsi payroll.

Perbaikan: Definisikan sumber waktu eligible untuk payroll beserta approval/finalization. Filter hanya event sah; snapshot event IDs pada payroll. Koreksi approval sesudah payroll posted harus melalui adjustment terhubung, bukan silently mengubah slip historis.

Acceptance criteria: Flagged/unapproved tidak dihitung; setelah approval dihitung satu kali. Penolakan berikutnya tidak mengubah payroll posted tanpa adjustment. Formal dan automatic yang merujuk event sama tidak dihitung dua kali.

Telusuri router, schema, UI, permission, identitas event, projection dan downstream payroll/GL. Pertahankan guard yang sudah benar. Tambahkan pengujian integrasi Mongo dengan fixture mandiri dan expectation perilaku yang benar. Harness audit mengkarakterisasi bug; assertion lama yang lulus bukan kriteria keberhasilan patch.

Siapkan query pendeteksi data historis, dry-run perbaikan, serta reversal/adjustment untuk dokumen posted bila perlu. Jangan menghapus histori atau memutasi produksi secara otomatis. Laporkan perubahan file, hasil test aktual, dampak migrasi dan bagian yang belum terverifikasi.
```


## IX-05 — Metadata e-sign lintas badan usaha dapat dibaca lewat HTTP

- [backend/services/esign_service.py:162 — list_signatures](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/esign_service.py#L162)
- [backend/routers/esign.py:61 — signatures](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/esign.py#L61)

```text
Perbaiki IX-05 di KNHOST. Baca seluruh caller dan validasi ulang temuan pada HEAD aktual sebelum mengedit.

Pemicu dan hasil: User finance A dengan allowed_entity_ids=[A] dan permission esign.view memanggil GET /api/esign/signatures/invoice/INVB untuk signatures milik B. Respons 200 mengembalikan satu signature B.

Akar kesalahan: Router memeriksa permission fungsi, tetapi service mengambil berdasarkan doc_type/source_id tanpa scope/guard dokumen. Query mengecualikan signature_b64: gambar tanda tangan tidak ikut keluar melalui endpoint yang diuji.

Perbaikan: Resolve sumber dan owner, terapkan guard akses objek, kemudian query signature dengan versi sumber dan entity. Periksa create_request dan verify untuk binding owner/actor; jangan menganggap perbaikan list menutup lifecycle lainnya.

Acceptance criteria: User A ke source B menghasilkan 403/404 tanpa metadata; user A ke source A dengan permission berhasil; tanpa esign.view tetap 403. Verifikasi publik berbasis kode dibahas dengan kontrak artifact terpisah.

Telusuri router, schema, UI, permission, identitas event, projection dan downstream payroll/GL. Pertahankan guard yang sudah benar. Tambahkan pengujian integrasi Mongo dengan fixture mandiri dan expectation perilaku yang benar. Harness audit mengkarakterisasi bug; assertion lama yang lulus bukan kriteria keberhasilan patch.

Siapkan query pendeteksi data historis, dry-run perbaikan, serta reversal/adjustment untuk dokumen posted bila perlu. Jangan menghapus histori atau memutasi produksi secara otomatis. Laporkan perubahan file, hasil test aktual, dampak migrasi dan bagian yang belum terverifikasi.
```


## IX-06 — Edit payroll settings dari entitas A mengubah konfigurasi efektif B

- [backend/services/hr_service.py:92 — get_hr_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_service.py#L92)
- [backend/services/config_resolver.py:495 — entity_overlay](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L495)
- [backend/routers/hr_payroll.py:31 — get_payroll_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L31)
- [backend/routers/hr_payroll.py:40 — update_payroll_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L40)

```text
Perbaiki IX-06 di KNHOST. Baca seluruh caller dan validasi ulang temuan pada HEAD aktual sebelum mengedit.

Pemicu dan hasil: User hanya ditugaskan di A, konteks aktif A, memiliki hr.manage_payroll. PUT /api/hr/payroll/settings mengubah overtime.multiplier menjadi 3. Hasil 200; effective setting B berubah 1,5→3.

Akar kesalahan: GET payroll settings menggunakan entity_ctx+overlay. PUT endpoint yang sama tidak mengambil konteks entitas, membaca global dan menulis system_settings{scope:hr}. Kontrak pembacaan per entitas dan penulisan global berbeda. Pusat config juga memiliki lapisan entitas sehingga nilai yang terlihat dapat berbeda dari nilai yang baru disimpan.

Perbaikan: Pisahkan edit baseline global dari override entitas. Edit pada konteks A menulis lapisan A lewat resolver kanonik. Edit global memerlukan hak grup yang jelas, label UI dan preview dampak. GET, PUT dan respons memakai scope yang sama.

Acceptance criteria: Edit A tidak mengubah B. Edit global oleh pengguna yang berwenang memengaruhi hanya entitas pewaris; entitas dengan override tetap benar. Respons setelah save sama dengan reload; history mencatat scope dan pemilik.

Telusuri router, schema, UI, permission, identitas event, projection dan downstream payroll/GL. Pertahankan guard yang sudah benar. Tambahkan pengujian integrasi Mongo dengan fixture mandiri dan expectation perilaku yang benar. Harness audit mengkarakterisasi bug; assertion lama yang lulus bukan kriteria keberhasilan patch.

Siapkan query pendeteksi data historis, dry-run perbaikan, serta reversal/adjustment untuk dokumen posted bila perlu. Jangan menghapus histori atau memutasi produksi secara otomatis. Laporkan perubahan file, hasil test aktual, dampak migrasi dan bagian yang belum terverifikasi.
```
