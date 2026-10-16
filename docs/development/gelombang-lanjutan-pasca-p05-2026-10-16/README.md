# Gelombang Lanjutan Pasca-P05

ERP Kain Nussantara · Produksi IT PT Kubus Teknologi Indonesia · 2026-10-16

Paket kerja untuk perbaikan berdasarkan keputusan owner dan pembahasan client sampai 16 Oktober 2026. Paket ini berisi rencana, prompt fase, acceptance, pending decision dan sumber; belum berisi implementasi ERP baru.

**Baseline:** `main` `64d81f29577dae4daa86ddc64689dec7243804f2` (commit 14 Oktober 2026), snapshot terakhir yang diperiksa. P01–P05 berstatus `implemented_pending_validation`, bukan tervalidasi final. P06–P10 masih `not_started`. HEAD repo saat mulai kerja wajib dicatat ulang di L00.

## Urutan membaca dan memakai

1. [Rencana utama](DEVELOPMENT_PLAN.md) dan [hubungan plan lama](BASELINE_DAN_PLAN_LAMA.md).
   Ringkasan [keputusan aktif](KEPUTUSAN_AKTIF_RINGKAS.md) membantu membaca aturan yang sudah jelas.
2. [Prompt mulai untuk agent](PROMPT_MULAI.md) dan [panduan pengerjaan](AGENT_GUIDE.md).
3. [Tracker](TRACKER.md), [acceptance](ACCEPTANCE_MATRIX.md), [coverage sumber](COVERAGE.md) dan [keputusan pending](DECISIONS_PENDING.md).
4. Kerjakan [L00](phases/L00.md), lalu fase yang dependensinya terpenuhi. Setiap fase mempunyai prompt mandiri.
5. Catat bukti di `evidence/<fase>/`, ubah status hanya di [BACKLOG.json](BACKLOG.json), lalu jalankan validator dan renderer sesuai panduan.

Import manual folder ini ke `docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/`. Tidak perlu menimpa source code atau tracker wave lama. Snapshot sumber dalam `sources/` bersifat historis; status aktif gelombang ini hanya di BACKLOG.json.

ZIP sudah memuat struktur `docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/`; ekstrak pada folder sementara lalu salin subtree tersebut ke repo. [PACKAGE_QA.json](PACKAGE_QA.json) mencatat pemeriksaan paket, dan [SOURCE_MANIFEST.json](SOURCE_MANIFEST.json) menyimpan hash sumber historis.

Lihat [cara handoff dan validasi ulang](HANDOFF_DAN_VALIDASI_ULANG.md) untuk workflow implementasi → report → review → koreksi → validasi.

**Selesai berarti:** seluruh requirement required tervalidasi, skenario lulus dengan bukti pada kandidat final, keputusan blocker terselesaikan, migrasi dan perangkat nyata diuji, serta ada persetujuan owner. `Build lulus`, `implemented`, atau dokumentasi lengkap belum memenuhi batas selesai itu.

Revisi historis **1.1** sudah melalui [crosscheck isi dan koreksi](CROSSCHECK_DAN_KOREKSI_REV_1_1.md). Gunakan ZIP revisi terbaru.

Lihat [penutupan](DEFINITION_OF_DONE.md) dan [pertanyaan client lengkap](sources/09_Pertanyaan_Client_Retur_dan_Pendukung.md). Pertanyaan belum dikirim kepada pihak lain.

## Tambahan implementasi revisi 1.2 — produksi supplier dan makloon

Wajib baca [rancangan implementasi produksi](IMPLEMENTASI_PRODUKSI_SUPPLIER_MAKLOON.md). LN-033 ditambahkan pada L03 dan LN-143 pada L14, dengan 18 skenario acceptance baru. Total paket: 54 requirement, 214 acceptance, 15 fase; 24 topik pending lama tetap dipertahankan.

Urutan dependency berubah: fondasi L04 harus tervalidasi sebelum L03 ditutup. Pekerjaan desain/round L03 dapat dipersiapkan sebelumnya. Rilis master bukan order produksi; kedua sumber pemenuhan wajib memiliki hubungan dokumen yang benar sampai penerimaan dan pengiriman. Penambahan ini disetujui owner dalam chat 16 Oktober 2026. Semua status lama dipertahankan; requirement baru belum diimplementasikan.

## Revisi 1.3 — hak akses rinci dan pengujian ulang R&D

Wajib baca [rancangan custom role dan revalidasi R&D](CUSTOM_ROLE_DAN_REVALIDASI_RND_REV1_3.md). Tambahan LN-015 (L01) dan LN-034 (L03), 16 acceptance baru; total 56 requirement dan 230 acceptance. Keputusan owner: hasil uji ulang gagal menunggu keputusan PIC; tidak otomatis menghentikan produksi atau membatalkan stok lama. L14 wajib membuktikan integrasi kedua tambahan ini. Hak akses mencakup aktivitas, scope dan field, bukan hanya menu terlihat. Versi ini menggantikan paket 1.2 untuk import baru; status lama dan 24 topik pending tetap dipertahankan.
