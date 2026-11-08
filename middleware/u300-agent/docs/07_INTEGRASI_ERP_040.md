# Integrasi U300 dan ERP — versi 0.4

ERP Kain Nussantara · Production IT PT Kubus Teknologi Indonesia

> **Historis (0.4 / kontrak 2.0).** Patch ERP sudah diterapkan dan diperbaiki (PREP-D1, kontrak 2.1). Untuk 0.5.0 lihat
> [08 Perubahan 0.5.0](08_PERUBAHAN_050.md) dan [05 Validasi](05_VALIDASI.md); uji integrasi 0.5 =
> `tests/run_erp_local_v2.py`. `backend/tests/run_u300_https.py` (0.4) perlu daftar kompilasi baru sebelum dipakai lagi.  
19 Oktober 2026 · LAB, belum produksi

## Perubahan reader

Pesan HTTP dari ERP kini menampilkan kode dan penjelasan terstruktur (maksimal 500 karakter), sehingga operator dapat membedakan konflik event, profil belum tersedia, atau passage sudah ditutup. Pembacaan body error dibatasi 8 KiB; respons bukan JSON tetap menggunakan status HTTP. Algoritme retry dan autentikasi tidak diubah. Test-only certificate trust hanya ada pada program tes komputer, tidak dimasukkan ke APK.

## Alur operasional

1. Admin membuat perangkat gate/fixed reader pada menu RFID > Perangkat dan menerbitkan device key satu kali.
2. Admin menyiapkan profil JSON dari template: device, site, warehouse, logical gate, SDK, region, power, sensor dan indikator. Nilai commissioning hanya dinyatakan benar setelah pemeriksaan unit.
3. Buka “Operasional U300 / V2” pada kartu perangkat, lalu unggah profil. Versi yang pernah diterbitkan tidak dapat ditimpa dengan isi berbeda.
4. Operator memilih SJ aktif, transfer fisik yang sudah dikirim, atau putaway yang sedang transit; pilih arah; klik “Gunakan manifest”. Daftar roll berasal dari dokumen ERP, bukan diketik pada reader.
5. Reader mengambil konfigurasi lewat HTTPS. Device key mengidentifikasi reader; izin operator ERP tidak diberikan kepada device key.
6. Setiap tag masuk disimpan dahulu di SQLite. Agent mengirim batch; ERP menyimpan event dengan write concern journaled majority sebelum memberikan ACK durable.
7. Penutupan lintasan membekukan kumpulan event. Server membandingkan event terhadap snapshot manifest dan memeriksa ulang dokumen aktif. Event yang sama tidak dihitung dua kali.
8. GREEN hanya untuk manifest penuh yang sesuai, waktu valid, arah valid, capture lengkap, profil aktif, tanpa alarm sebelumnya, dan mode live. Reader tetap memeriksa sendiri identitas/freshness keputusan sebelum menyalakan indikator.
9. Salah manifest, unknown EPC, barang kurang/lebih, capture terputus, konfigurasi lama, backfill, atau crossing ulang menghasilkan penahanan/pemeriksaan. Operator mencatat pemeriksaan melalui panel ERP. Reset alarm tidak mengubah keputusan lama menjadi GREEN.
10. Receiving, perpindahan stok, kepemilikan, SJ, serta pembukuan tetap dilakukan oleh flow ERP masing-masing. Gate tidak melakukan mutasi tersebut.

## Bukti validasi

- 53 assertion router/service ERP menggunakan MongoDB nyata lokal.
- 9 assertion Java–ERP melalui HTTPS lokal memakai `Api`, `Config`, dan `DecisionPolicy` dari source reader.
- 121 assertion host reader, 6 jenis payload schema, 2 pemeriksaan schema negatif, 5 kasus integritas snapshot.
- APK debug dan APK instrumentation dibangun; lint 0 error, 1 warning kompatibilitas API 30/31.
- Belum menjalankan instrumentation di Android atau menguji U300 fisik.

## Pengujian ulang integrasi

Gunakan Python dengan dependency backend ERP, Java 17, dan `org.json:json:20240303` untuk tes host. Jalankan MongoDB khusus lokal, lalu set `MONGO_URL=mongodb://127.0.0.1:<port>`. Skrip integrasi menolak URL nonlokal dan membuat database test unik; tidak membaca database bisnis.

`backend/tests/run_rfid_v2_integration.py` menjalankan tes router/service. `backend/tests/run_u300_https.py <folder-agent> <folder-jdk> <json-jar> <folder-hasil-test>` menyiapkan sertifikat lokal sementara, menjalankan API HTTPS lokal, lalu menjalankan Java test. Private key sertifikat tes tidak disertakan dalam paket serah-terima.

Lihat dokumen 04 untuk batas implementasi yang masih terbuka. Angka tes bukan klaim coverage 100%.
