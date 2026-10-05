# Gelombang 2 — paket agent development

Mulai dengan [prompt pembuka](PROMPT_MULAI.md), [workflow](WORKFLOW.md), lalu [P00](phases/P00.md). Paket2026-10-03; snapshot audit `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Repo saat implementasi mungkin sudah berubah. Tidak ada kode aplikasi atau perbaikan baru dalam paket ini.

## Isi dan sumber kebenaran

- [tracker.json](tracker.json): status aktif25 temuan W2, dengan kartu di findings/ dan fase masing-masing.
- [Indeks25 temuan](FINDINGS_INDEX.md): daftar domain/fase dan tautan kartu.
- [requirements-tracker.json](requirements-tracker.json): sembilan kebutuhan klien; bukan sembilan bug baru.
- [phase-tracker.json](phase-tracker.json): urutan P00–P09 dan dependensi.
- [wave1-extensions.json](wave1-extensions.json):26 acceptance pendalaman; tidak menggantikan tracker Wave1.
- [baseline/](baseline/README.md): seluruh91 berkas audit lama, laporan27, hasil dan reproducer; jangan diedit.
- [memo12 poin](baseline/25_MEMO_JAWABAN_KEBUTUHAN_KLIEN.md): jawaban kebutuhan klien, fitur tersedia dan batasnya.
- [test plan](TEST_PLAN.md), [UAT](UAT.md), templates/ dan iterations/: bukti implementasi/validasi baru.
- tools/: persiapan iterasi dan pemeriksa integritas paket/status; bukan pengujian aplikasi.

Baseline242 checkpoint terdiri174 kontrol,36 reproduksi cacat W2,26 pendalaman Wave1 dan6 observasi kebijakan. Empat probe penjelasan tidak dihitung. Angka ini bukan coverage seluruh code/flow. Subtotal dalam laporan lama adalah histori; review RFID12 dan klasifikasi koreksinya mengungguli interpretasi awal.

## Urutan

P00 rekonsiliasi → P01 scope → P02 stok/QC → P03 makloon → P04 produksi → P05 AR/refund → P06 laporan/payroll → P07 RFID → P08 kebutuhan klien → P09 validasi gabungan. Dependensi minimal ada di phase-tracker; urutan ini default praktis. Jangan membuka pekerjaan paralel yang mengubah file sama tanpa koordinasi.

Agent implementasi mengisi ready_for_validation, bukan verified_fixed. Auditor memeriksa kandidat dan menetapkan hasil. Status kebutuhan/policy dan batas browser/hardware tetap eksplisit. Jangan menggabungkan status selesai implementasi dengan kesiapan produksi.
