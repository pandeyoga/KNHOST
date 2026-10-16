# Addendum Development Plan RFID Chainway

**Tanggal:** 12 Oktober 2026. **Versi:** v2 dengan printer. **Perangkat dari pengguna:** UR300 fixed reader/gate, C72 handheld, dan printer CP30EN. Nama printer telah dipilih; varian/firmware/koneksi/media aktual masih perlu PoC.

Addendum ini melengkapi plan 35 IMP sebelumnya dengan 15 kebutuhan integrasi hardware RFID, 6 tahap RF00–RF04 serta RF-P, dan 30 skenario penerimaan. Nomor IMP/P00–P10 tetap; fingerprint P09 merupakan integrasi berbeda. [Perubahan dari v1](CHANGELOG.md) mempertahankan ID lama.

## Isi dan cara pakai

1. [Rencana RFID](DEVELOPMENT_PLAN_RFID.md).
2. [Kondisi kode dan kontrak API](API_CONTRACT.md).
3. [Hubungan dengan plan utama](INTEGRATION_WITH_MAIN_PLAN.md).
4. [Tracker](TRACKER.md) dan [RFID_BACKLOG.json](RFID_BACKLOG.json).
5. Prompt [RF00](prompts/RF00.md), [RF01](prompts/RF01.md), [RF02](prompts/RF02.md), [RF03](prompts/RF03.md), [RF-P printer](prompts/RF-P.md), [RF04](prompts/RF04.md).
6. [Acceptance](ACCEPTANCE_RFID.md).
7. [Rencana printer CP30EN](PRINTER_CP30EN_PLAN.md).

Gunakan v2 ini sebagai addendum RFID yang aktif di docs/development di samping plan utama; arsip v1 boleh disimpan sebagai histori. Pertahankan struktur relatif. Jika v1 sudah mempunyai progress, merge perubahan sesuai CHANGELOG.md dan jangan menimpa status/evidence. BACKLOG.json utama tetap; status hardware ada pada RFID_BACKLOG.json. P10 menambahkan gate RF04 yang mencakup CP30EN.

Ubah status dalam RFID_BACKLOG.json kemudian jalankan `python scripts/render_tracker.py`; TRACKER.md merupakan hasil render. Semua kebutuhan awal not_started dan acceptance awal not_run. Paket berisi rencana; belum menghasilkan APK atau adapter siap pakai.
