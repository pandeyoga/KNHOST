# Prompt mulai — salin ke agent development

Kerjakan paket “Gelombang Lanjutan Pasca-P05” ERP Kain Nussantara produksi IT PT Kubus Teknologi Indonesia di `docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/`.

Baseline yang pernah diperiksa adalah main `64d81f29577dae4daa86ddc64689dec7243804f2`. Jangan mengasumsikan HEAD sekarang sama atau P05 sudah tervalidasi; tracker sumber menyatakan implemented_pending_validation. Baca README, DEVELOPMENT_PLAN, BASELINE_DAN_PLAN_LAMA, AGENT_GUIDE dan BACKLOG. Ikuti AGENTS repo target.

Mulai L00. Catat SHA aktual dan delta, validasi status pekerjaan existing, petakan dampak keputusan terbaru, siapkan fixture dan rencana migrasi. Sesudah L00, kerjakan fase menurut dependency. Untuk setiap kebutuhan, cek apakah sudah terakomodasi melalui alur atau konfigurasi existing; gunakan kembali yang benar sebelum menambah fitur.

Keputusan owner terbaru mengalahkan catatan lama. Pending dicatat dan hanya memblok cabang terkait. Jangan menentukan sendiri cutloss, basis selisih replacement, rumus inspect, dual LOT atau cutoff. Jangan menambah toleransi otomatis untuk qty roll. Semua authority harus melalui custom role dan scope, grade tersembunyi bagi Sales termasuk trial, owner berbeda dari lokasi fisik.

Titik selesai tiap fase ada pada phase prompt dan acceptance. Jangan berhenti pada kode terbuat atau unit test lulus. Serahkan perubahan konkret, tes UI/API/data yang relevan, dampak antarmodul, migrasi, evidence dan commit. Status implementasi lengkap adalah implemented_pending_validation; validated memerlukan review terpisah dan persetujuan owner.

Update hanya BACKLOG sebagai SSOT status, render dokumen turunannya, jalankan validator. Jangan menandai gelombang complete sebelum --closure lulus dengan evidence yang benar dan kandidat final disetujui owner. Pembangunan middleware/APK tidak termasuk tugas ERP ini; kontrak dan integrasi tetap harus dibuktikan dengan unit UR300, C72 dan CP30EN.

## Tambahan implementasi revisi 1.2 — produksi supplier dan makloon

Wajib baca [rancangan implementasi produksi](IMPLEMENTASI_PRODUKSI_SUPPLIER_MAKLOON.md). LN-033 ditambahkan pada L03 dan LN-143 pada L14, dengan 18 skenario acceptance baru. Total paket: 54 requirement, 214 acceptance, 15 fase; 24 topik pending lama tetap dipertahankan.

Urutan dependency berubah: fondasi L04 harus tervalidasi sebelum L03 ditutup. Pekerjaan desain/round L03 dapat dipersiapkan sebelumnya. Rilis master bukan order produksi; kedua sumber pemenuhan wajib memiliki hubungan dokumen yang benar sampai penerimaan dan pengiriman. Penambahan ini disetujui owner dalam chat 16 Oktober 2026. Semua status lama dipertahankan; requirement baru belum diimplementasikan.

## Revisi 1.3 — hak akses rinci dan pengujian ulang R&D

Wajib baca [rancangan custom role dan revalidasi R&D](CUSTOM_ROLE_DAN_REVALIDASI_RND_REV1_3.md). Tambahan LN-015 (L01) dan LN-034 (L03), 16 acceptance baru; total 56 requirement dan 230 acceptance. Keputusan owner: hasil uji ulang gagal menunggu keputusan PIC; tidak otomatis menghentikan produksi atau membatalkan stok lama. L14 wajib membuktikan integrasi kedua tambahan ini. Hak akses mencakup aktivitas, scope dan field, bukan hanya menu terlihat. Versi ini menggantikan paket 1.2 untuk import baru; status lama dan 24 topik pending tetap dipertahankan.
