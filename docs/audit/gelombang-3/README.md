# KNHOST — Paket perbaikan Gelombang 3

Audit dihentikan atas permintaan pengguna pada 6 Oktober 2026. Paket ini memuat **101 catatan perbaikan: 78 dari checkpoint sebelumnya + 23 tambahan lanjutan**. Angka ini tidak berarti 101 bug baru muncul setelah patch: 19 dari checkpoint sebelumnya berasal dari temuan lama yang masih terbuka; label asal dan bukti ada pada tracker. Seluruh ID dipertahankan agar mudah ditautkan saat validasi berikutnya. Prioritas seluruh register: {'P1': 63, 'P2': 37, 'P3': 1}; tambahan: {'P2': 12, 'P1': 11}.

Snapshot source yang diaudit: `a904d989b622f7da14c4892d03cf6ef0c43f3084`. **Target 90% belum tercapai.** Cakupan eksekusi backend runtime/startup ketika dihentikan: **82.52% statement** (59,594/72,221) dan **68.35% cabang** (15,727/23,008), denominator tetap 480 berkas. Ini bukan persentase kebenaran bisnis atau jaminan semua flow telah diuji. Register cakupan mencatat pekerjaan yang masih terbuka.

## Cara import dan mulai

1. Ekstrak ZIP ke root repo sehingga folder baru menjadi `docs/audit/gelombang-3/`. Pertahankan folder Gelombang 1 dan 2. Tidak ada patch kode aplikasi di paket ini.
2. Baca [register](DAFTAR_TEMUAN.md), [laporan lengkap](LAPORAN_LENGKAP.md), dan [batas cakupan](CAKUPAN_DAN_BATAS.md).
3. Berikan [prompt awal](PROMPT_MULAI_AGENT.md) ke agent; kerjakan [fase 01](prompts/FASE-01.md) lebih dulu, kemudian fase 02–04 dengan prasyarat yang tercatat. Fase 05 menutup regresi dan bukti validasi.
4. Agent memperbarui `findings-tracker.json` dan bukti implementasi per ID. Gunakan `implemented_pending_validation`, lalu kirim repo/commit dan template permintaan validasi kepada reviewer. `verified_fixed` memerlukan verifikasi independen.

## Isi paket

- `TEMUAN_TAMBAHAN_23.md`: lokasi kode, sebab, rantai masalah, bukti expected/actual, batas klaim, prompt dan acceptance bagi 23 tambahan.
- `baseline-78/`: paket checkpoint sebelumnya beserta 78 detail, 137 register revalidasi Gelombang 1/2, bukti dan skrip; dipertahankan sebagai referensi historis. README/count di subfolder itu hanya menjelaskan checkpoint lama.
- `findings-tracker.json` / CSV, `repair-phases.json`, lima prompt fase, dan template status/validasi: sumber kendali kerja Gelombang 3.
- `evidence/repro/`: hasil counterexample dan kontrol tambahan; `evidence/continuation-90/`: hasil suite native, adapters, hipotesis ditolak, dan cakupan. Nonpass suite lama tidak otomatis dimasukkan sebagai temuan baru.
- `repro/`: skrip counterexample/runner dan petunjuk rerun. Gunakan database audit lokal; jangan jalankan pada produksi. Bukti historis tidak boleh ditimpa.
- `manifest.json` dan `VERIFY_PACKAGE.md`: identitas snapshot, hash file, dan hasil pemeriksaan paket.
