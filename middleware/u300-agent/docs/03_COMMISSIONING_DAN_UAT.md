# Commissioning dan pengujian penerimaan

ERP Kain Nussantara · PT Kubus Teknologi Indonesia

Dokumen ini adalah daftar uji yang harus dijalankan; bukan pernyataan bahwa perangkat sudah lulus. Sampai 18 Oktober 2026, belum ada U300 atau emulator yang terhubung pada pemeriksaan ADB.

## 1. Peralatan dan informasi

- U300 dengan firmware/Android yang sesuai, catu daya, jaringan, antena dan kabel RF.
- Tag uji valid, tag tidak dikenal, tag malformed bila tersedia, barang uji dengan beberapa roll.
- Sensor A/B jika arah dua jalur diperlukan; lampu/relay yang sesuai rating GPIO vendor. Wiring, isolasi dan perilaku saat listrik mati diperiksa sebelum disambungkan.
- ERP staging: device registration, key, gate/site/warehouse, manifest uji, role supervisor, dan keenam kontrak terkait konfigurasi/events/close/gate-state/telemetry/acknowledge.
- Identitas model, firmware, SDK, jumlah port antena, kode region dan power setiap antena.
- Keputusan operasional: idle timeout, maksimal durasi lintasan, completion basis, kebijakan offline, batas antrean, dan retensi.

Laptop hanya diperlukan untuk build, pemasangan/pemeriksaan awal bila menggunakan ADB, dan debugging. Layanan agent berjalan pada Android U300; laptop bukan komponen runtime gate.

## 2. Urutan commissioning

1. Catat perangkat dan SDK yang dipakai; cocokkan hash AAR.
2. Jalankan aplikasi demo resmi vendor untuk membuktikan radio/antena dapat membaca tag. Catat kode region dan power; jangan memilih kode berdasarkan perkiraan.
3. Pasang APK agent, jalankan simulasi, lalu periksa pemasangan dan izin notifikasi/foreground service.
4. Siapkan konfigurasi staging dengan indikator disabled; konfigurasi commissioned baru true setelah parameter dasar dikonfirmasi.
5. Uji inventory dan pemetaan tiap antena satu per satu. Antena tidak terpetakan harus menghentikan capture.
6. Uji GPI, polaritas, bouncing, urutan A/B, lintasan lambat/cepat, dan dua objek berdekatan. Profil idle tidak boleh menyatukan dua pengiriman atau memecah satu pengiriman secara salah.
7. Sambungkan indikator sesuai diagram vendor yang sudah diperiksa. Uji output tanpa pergerakan barang lebih dahulu.
8. Jalankan kasus positif/negatif ERP. Green fisik harus cocok dengan keputusan dan tidak hidup saat tidak ada clearance.
9. Uji gangguan jaringan, reboot, proses mati, waktu berubah, penyimpanan penuh dan pemulihan. Perilaku GPIO saat process crash/listrik mati memerlukan fail-safe fisik; software saja tidak membuktikan hal tersebut.
10. Jalankan soak test dengan volume pembacaan yang mewakili operasi. Tetapkan kapasitas dan durasi simpan berdasarkan hasilnya.

## 3. Matriks penerimaan

Semua baris berikut berstatus **BELUM DIJALANKAN di Android/perangkat nyata**. Isi tanggal, perangkat, hasil, bukti log dan penanggung jawab pada salinan pelaksanaan.

| ID | Skenario | Hasil yang harus dibuktikan |
|---|---|---|
| U01 | Instal dan buka aplikasi | Tidak crash; tampil label LAB dan identitas proyek |
| U02 | PIN salah lima kali | Tindakan pemeliharaan ditolak sementara |
| U03 | Buka aplikasi lain/tutup layar | Layanan tetap aktif sesuai policy Android |
| U04 | Reboot dengan autostart aktif | Service mulai; tidak memberi clearance lama |
| U05 | SDK init gagal | Radio tidak dianggap ready; tidak ada green |
| U06 | Region/power tidak cocok | Capture ditolak sebelum inventory operasi |
| U07 | Antena benar/salah | Antena benar tercatat; mapping salah menghentikan capture |
| U08 | EPC berulang pada satu lintasan | Raw observations lengkap; dedup bisnis dilakukan ERP |
| U09 | EPC sama pada lintasan baru | Passage ID baru; tidak hilang karena dedup global |
| U10 | EPC tidak valid | Raw EPC tersimpan, canonical null; tidak clearance |
| U11 | ACK parsial | Hanya event dengan ACK durable berubah acked |
| U12 | Timeout setelah server menyimpan | Retry ID/body sama; tidak menggandakan mutasi ERP |
| U13 | Accepted tanpa durable / retry | Tetap pending |
| U14 | Rejected/quarantined | Capture dianggap tidak lengkap; tidak green |
| U15 | 413 batch | Batch diperkecil, ID event dipertahankan |
| U16 | 429 | Hormati Retry-After dan backoff |
| U17 | 401/403 | Stop capture, blok transport, antrean tidak hilang |
| U18 | 400/409 / versi berubah | Blok untuk rekonsiliasi; jangan rebind data lama |
| U19 | Offline sebelum lintasan | Backfill; sinkronisasi setelah pulih tanpa green |
| U20 | Offline di tengah live passage | Eligibility green hilang, termasuk setelah pulih |
| U21 | Restart saat OPEN | INTERRUPTED/incomplete, tidak replay green |
| U22 | Keputusan gate/passage/version salah | Tidak menyalakan green |
| U23 | Keputusan pending/expired/REVIEW | Tidak menyalakan green |
| U24 | Final GREEN manifest_full lengkap | Green terbatas waktu hanya pada passage terkait |
| U25 | Polling keputusan GREEN yang sama | Tidak memperpanjang masa lampu |
| U26 | manifest_subset/per_epc_only | Tidak menganggap seluruh lintasan cleared |
| U27 | RED lalu acknowledge di ERP | Red bertahan sebelum persetujuan; tidak replay green lama |
| U28 | Sensor A→B / B→A / bouncing/timeout | Arah sesuai bukti; ambigu tidak memberikan clearance |
| U29 | Jam Android dimajukan/dimundurkan | Tidak memperpanjang green |
| U30 | Ruang disk/antrean penuh | Capture berhenti, tidak membuang pending event |
| U31 | Hentikan/mulai cepat | Tidak terjadi dua service/radio yang berjalan bersamaan |
| U32 | Export diagnosis | File terbuka, tidak mengandung device key/PIN |
| U33 | Perubahan origin/gate setelah ada data | Tidak merutekan histori ke konteks lain |
| U34 | Soak test dan beban maksimum | Tidak ANR, backlog terukur, latensi output memenuhi SOP |
| U35 | Power loss/SDK hang/GPO error | Perilaku fisik fail-safe dibuktikan, bukan diasumsikan |

## 4. Titik selesai menuju produksi

Release produksi baru dapat disetujui setelah: seluruh kasus wajib lulus; tidak ada cacat kritis yang belum ditangani; endpoint ERP staging terbukti; profil/wiring dicatat; satu logical gate dan SOP lintasan disepakati; signing key produksi disimpan oleh pemilik aplikasi; backup/recovery, monitoring dan retensi diputuskan; serta bukti uji ditandatangani tim terkait.

Jika UAT menemukan perbedaan firmware, callback, polaritas GPIO atau kontrak ERP, source harus disesuaikan dan APK dibangun ulang. Build berhasil tidak menjamin tidak diperlukan penyesuaian saat commissioning.
