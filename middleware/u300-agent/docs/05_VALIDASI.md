# Validasi versi 0.4

ERP Kain Nussantara · PT Kubus Teknologi Indonesia

Ringkasan dan batas pengujian terbaru ada di [Integrasi ERP 0.4](07_INTEGRASI_ERP_040.md). Bukti build ada di `build-debug.log`; bukti host dan lint ada di `tests/`. Bukti integrasi ERP/Java disertakan pada paket gabungan ERP–reader.

Tidak ada pengujian perangkat fisik, runtime Android, staging, atau produksi yang diklaim. APK instrumentation hanya berhasil dikompilasi. Keberhasilan Java HTTPS membuktikan kompatibilitas transport dan payload dengan router ERP lokal, bukan wiring atau pembacaan radio.
